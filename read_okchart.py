"""
OK차트 SQL Server → 원장별현황.csv 자동 업데이트

MasterDB.dbo.Receipt + Detail 조인
원장별 일별 매출 (건보/자보/비급여/린다이어트)
최근 6개월 데이터
"""

import sys, csv
from pathlib import Path
from collections import defaultdict

try:
    import pyodbc
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyodbc"])
    import pyodbc

CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=(local)\\OKCHART;"
    "DATABASE=MasterDB;"
    "UID=members;"
    "PWD=msp1234;"
)

CSV_PATH = Path(r"C:\Users\하슬라한의원\한의원지표\data\원장별현황.csv")

KBO_CODES = {'W','V','1','T','C','M','L','3','4','5','7'}

# 원장별 일별 매출 (건보/자보/비급여)
SQL_REVENUE = """
SELECT
    CONVERT(DATE, r.TxDate)                                  AS 날짜,
    d.TxDoctor                                               AS 원장명,
    r.Calcu_Type                                             AS 구분,
    SUM(CAST(r.Bonin_Money   AS BIGINT)
      + CAST(r.CheongGu_Money AS BIGINT))                    AS 보험매출,
    SUM(CAST(r.General_Money  AS BIGINT))                    AS 비급여매출
FROM Receipt r
INNER JOIN (
    SELECT DISTINCT TxDoctor, Customer_PK, CONVERT(DATE,TxDate) AS TxDate, SN
    FROM Detail
    WHERE TxDate >= DATEADD(month, -6, GETDATE())
) d ON  r.Customer_PK             = d.Customer_PK
    AND CONVERT(DATE, r.TxDate)   = d.TxDate
    AND r.sn                      = d.SN
WHERE r.TxDate >= DATEADD(month, -6, GETDATE())
  AND d.TxDoctor != N'선주천'
GROUP BY CONVERT(DATE, r.TxDate), d.TxDoctor, r.Calcu_Type
ORDER BY 날짜, 원장명, 구분
"""

# 원장별 일별 린다이어트 매출
SQL_LINDA = """
SELECT
    CONVERT(DATE, TxDate)       AS 날짜,
    TxDoctor                    AS 원장명,
    SUM(CAST(TxMoney AS BIGINT)) AS 린다이어트
FROM Detail
WHERE TxDate >= DATEADD(month, -6, GETDATE())
  AND TxDoctor != N'선주천'
  AND (PxName LIKE N'%린다이어트%'
    OR PxName LIKE N'%린프리미엄%'
    OR PxName LIKE N'%린 %')
GROUP BY CONVERT(DATE, TxDate), TxDoctor
ORDER BY 날짜, TxDoctor
"""

# 원장별 일별 TA초진 / 건보초진 / 재초진 / 재진 건수
#   OK차트 PxName은 "진찰료(초진)" / "진찰료(재진)" 뿐이고 자보 환자는 진찰료
#   row가 없다 (약침·물리치료 등 시술만 등록). 그래서 환자 방문 이력 +
#   그 날 진료가 자보였는지(TxItem='자동차보험')로 직접 분류.
#     TA초진   = 첫 방문 + 그 날 자보 진료 row 있음
#     건보초진 = 첫 방문 + 그 날 자보 진료 없음 (=건보 환자)
#     재초진   = 직전 방문 후 45일 이상 간격
#     재진     = 직전 방문 후 45일 미만 간격
SQL_VISIT = """
WITH patient_visits AS (
    SELECT DISTINCT Customer_PK, CONVERT(DATE, TxDate) AS VisitDate
    FROM Detail
    WHERE TxDoctor != N'선주천'
),
visit_with_prev AS (
    SELECT
        Customer_PK,
        VisitDate,
        LAG(VisitDate) OVER (PARTITION BY Customer_PK ORDER BY VisitDate) AS PrevVisitDate
    FROM patient_visits
),
visit_type AS (
    SELECT
        Customer_PK,
        CONVERT(DATE, TxDate) AS VisitDate,
        MAX(CASE WHEN TxItem = N'자동차보험' THEN 1 ELSE 0 END) AS is_ta
    FROM Detail
    WHERE TxDoctor != N'선주천'
    GROUP BY Customer_PK, CONVERT(DATE, TxDate)
)
SELECT
    CONVERT(DATE, d.TxDate)                                          AS 날짜,
    d.TxDoctor                                                       AS 원장명,
    COUNT(DISTINCT CASE WHEN v.PrevVisitDate IS NULL AND vt.is_ta = 1
                          THEN d.Customer_PK END)                    AS TA초진,
    COUNT(DISTINCT CASE WHEN v.PrevVisitDate IS NULL AND vt.is_ta = 0
                          THEN d.Customer_PK END)                    AS 건보초진,
    COUNT(DISTINCT CASE WHEN v.PrevVisitDate IS NOT NULL
                          AND DATEDIFF(day, v.PrevVisitDate, v.VisitDate) >= 45
                          THEN d.Customer_PK END)                    AS 재초진,
    COUNT(DISTINCT CASE WHEN v.PrevVisitDate IS NOT NULL
                          AND DATEDIFF(day, v.PrevVisitDate, v.VisitDate) < 45
                          THEN d.Customer_PK END)                    AS 재진
FROM Detail d
INNER JOIN visit_with_prev v
        ON v.Customer_PK = d.Customer_PK
       AND v.VisitDate    = CONVERT(DATE, d.TxDate)
INNER JOIN visit_type vt
        ON vt.Customer_PK = d.Customer_PK
       AND vt.VisitDate   = CONVERT(DATE, d.TxDate)
WHERE d.TxDate >= DATEADD(month, -6, GETDATE())
  AND d.TxDoctor != N'선주천'
  AND (d.PxName IN (N'진찰료(초진)', N'진찰료(재진)') OR d.TxItem = N'자동차보험')
GROUP BY CONVERT(DATE, d.TxDate), d.TxDoctor
ORDER BY 날짜, 원장명
"""


def main():
    print("OK차트 DB 연결 중...")
    conn = pyodbc.connect(CONN_STR, timeout=10)
    cursor = conn.cursor()

    # ── 매출 집계 ─────────────────────────────────────────
    print("  매출 쿼리 중...")
    cursor.execute(SQL_REVENUE)
    data = defaultdict(lambda: {'건보매출':0,'자보매출':0,'비급여매출':0,'린다이어트':0,'TA초진':0,'건보초진':0,'재초진':0,'재진':0})

    for 날짜, 원장명, 구분, 보험, 비급여 in cursor.fetchall():
        key = (str(날짜), 원장명)
        보험  = int(보험  or 0)
        비급여 = int(비급여 or 0)
        if 구분 == 'B':
            data[key]['자보매출'] += 보험
        elif 구분 in KBO_CODES:
            data[key]['건보매출'] += 보험
        data[key]['비급여매출'] += 비급여

    # ── 린다이어트 집계 ───────────────────────────────────
    print("  린다이어트 쿼리 중...")
    cursor.execute(SQL_LINDA)
    for 날짜, 원장명, 린다 in cursor.fetchall():
        data[(str(날짜), 원장명)]['린다이어트'] += int(린다 or 0)

    # ── TA초진/건보초진/재초진/재진 집계 ─────────────────
    print("  TA초진/건보초진/재초진/재진 쿼리 중...")
    cursor.execute(SQL_VISIT)
    for 날짜, 원장명, ta초진, 건보초진, 재초진, 재진 in cursor.fetchall():
        key = (str(날짜), 원장명)
        data[key]['TA초진']  += int(ta초진  or 0)
        data[key]['건보초진'] += int(건보초진 or 0)
        data[key]['재초진']  += int(재초진  or 0)
        data[key]['재진']    += int(재진    or 0)

    conn.close()

    # ── CSV 저장 ──────────────────────────────────────────
    FIELDS = ['날짜','원장명','건보매출','자보매출','비급여매출','린다이어트','TA초진','건보초진','재초진','재진']
    rows = []
    for (날짜, 원장명), v in sorted(data.items()):
        if v['건보매출'] == 0 and v['자보매출'] == 0 and v['비급여매출'] == 0:
            continue
        rows.append({'날짜':날짜, '원장명':원장명,
                     '건보매출':v['건보매출'], '자보매출':v['자보매출'],
                     '비급여매출':v['비급여매출'], '린다이어트':v['린다이어트'],
                     'TA초진':v['TA초진'], '건보초진':v['건보초진'],
                     '재초진':v['재초진'], '재진':v['재진']})

    with open(CSV_PATH, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(rows)

    print(f"완료: {len(rows)}행 → {CSV_PATH}")

    # ── 결과 미리보기 ─────────────────────────────────────
    from datetime import date
    today = str(date.today())[:7]   # YYYY-MM
    print(f"\n[{today} 원장별 매출 합계]")
    monthly = defaultdict(lambda: {'건보매출':0,'자보매출':0,'비급여매출':0})
    for r in rows:
        if r['날짜'][:7] == today:
            monthly[r['원장명']]['건보매출']  += r['건보매출']
            monthly[r['원장명']]['자보매출']  += r['자보매출']
            monthly[r['원장명']]['비급여매출'] += r['비급여매출']
    for doc, v in sorted(monthly.items()):
        print(f"  {doc}: 건보 {v['건보매출']//10000:,}만  자보 {v['자보매출']//10000:,}만  비급여 {v['비급여매출']//10000:,}만")


if __name__ == "__main__":
    main()
