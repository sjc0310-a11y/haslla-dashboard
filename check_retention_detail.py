import pyodbc

CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=(local)\\OKCHART;"
    "DATABASE=MasterDB;"
    "UID=members;"
    "PWD=msp1234;"
)

# ── 코호트 + 내원 횟수 ────────────────────────────────────
SQL_COUNT = """
WITH dated_visits AS (
    SELECT DISTINCT Customer_PK, CONVERT(DATE, TxDate) AS visit_date
    FROM Detail
),
visits_with_gap AS (
    SELECT Customer_PK, visit_date,
           LAG(visit_date) OVER (PARTITION BY Customer_PK ORDER BY visit_date) AS prev_visit
    FROM dated_visits
),
episode_starts AS (
    SELECT Customer_PK, visit_date, prev_visit,
           DATEDIFF(day, prev_visit, visit_date) AS gap_days
    FROM visits_with_gap
    WHERE visit_date BETWEEN '2026-04-06' AND '2026-04-12'
      AND (prev_visit IS NULL OR DATEDIFF(day, prev_visit, visit_date) > 45)
),
cohort AS (
    SELECT es.Customer_PK,
           es.visit_date AS cohort_date,
           (SELECT TOP 1 TxDoctor
            FROM Detail d
            WHERE d.Customer_PK = es.Customer_PK
              AND CONVERT(DATE, d.TxDate) = es.visit_date
            ORDER BY d.Detail_PK ASC) AS first_doctor
    FROM episode_starts es
    WHERE EXISTS (
        SELECT 1 FROM Detail d2
        WHERE d2.Customer_PK = es.Customer_PK
          AND CONVERT(DATE, d2.TxDate) = es.visit_date
          AND d2.InsuYes = 1
    )
),
visit_counts AS (
    SELECT c.Customer_PK, c.cohort_date,
           COUNT(DISTINCT CONVERT(DATE, d.TxDate)) AS visit_count
    FROM cohort c
    JOIN Detail d ON d.Customer_PK = c.Customer_PK
    WHERE c.first_doctor = N'노왕식'
      AND CONVERT(DATE, d.TxDate) BETWEEN c.cohort_date AND '2026-04-26'
    GROUP BY c.Customer_PK, c.cohort_date
)
SELECT vc.cohort_date, c2.Customer_PK, c2.sn, c2.name, vc.visit_count
FROM visit_counts vc
JOIN Customer c2 ON c2.Customer_PK = vc.Customer_PK
ORDER BY vc.cohort_date, c2.sn
"""

# ── 각 환자 내원일 목록 ───────────────────────────────────
SQL_DATES = """
WITH dated_visits AS (
    SELECT DISTINCT Customer_PK, CONVERT(DATE, TxDate) AS visit_date
    FROM Detail
),
visits_with_gap AS (
    SELECT Customer_PK, visit_date,
           LAG(visit_date) OVER (PARTITION BY Customer_PK ORDER BY visit_date) AS prev_visit
    FROM dated_visits
),
episode_starts AS (
    SELECT Customer_PK, visit_date
    FROM visits_with_gap
    WHERE visit_date BETWEEN '2026-04-06' AND '2026-04-12'
      AND (prev_visit IS NULL OR DATEDIFF(day, prev_visit, visit_date) > 45)
),
cohort AS (
    SELECT es.Customer_PK, es.visit_date AS cohort_date,
           (SELECT TOP 1 TxDoctor FROM Detail d
            WHERE d.Customer_PK = es.Customer_PK
              AND CONVERT(DATE, d.TxDate) = es.visit_date
            ORDER BY d.Detail_PK ASC) AS first_doctor
    FROM episode_starts es
    WHERE EXISTS (
        SELECT 1 FROM Detail d2
        WHERE d2.Customer_PK = es.Customer_PK
          AND CONVERT(DATE, d2.TxDate) = es.visit_date
          AND d2.InsuYes = 1
    )
)
SELECT c.Customer_PK, CONVERT(DATE, d.TxDate) AS vdate
FROM cohort c
JOIN Detail d ON d.Customer_PK = c.Customer_PK
WHERE c.first_doctor = N'노왕식'
  AND CONVERT(DATE, d.TxDate) BETWEEN c.cohort_date AND '2026-04-26'
GROUP BY c.Customer_PK, CONVERT(DATE, d.TxDate)
ORDER BY c.Customer_PK, vdate
"""

conn = pyodbc.connect(CONN_STR, timeout=30)
cursor = conn.cursor()

cursor.execute(SQL_COUNT)
count_rows = cursor.fetchall()

cursor.execute(SQL_DATES)
date_rows = cursor.fetchall()
conn.close()

# 환자별 내원일 딕셔너리
from collections import defaultdict
date_map = defaultdict(list)
for pk, vdate in date_rows:
    date_map[pk].append(vdate.strftime("%m/%d"))

revisit = sum(1 for r in count_rows if r[4] >= 2)
third   = sum(1 for r in count_rows if r[4] >= 3)
total   = len(count_rows)

with open("temp_result.txt", "w", encoding="utf-8") as f:
    f.write("=== 노왕식 재진/삼진 상세 (코호트 4/6~12, 추적 ~4/26) ===\n")
    f.write(f"코호트 {total}명 | 재진 {revisit}명({round(revisit/total*100,1)}%) | 삼진 {third}명({round(third/total*100,1)}%)\n\n")
    f.write(f"{'코호트일':<10}{'차트번호':<10}{'환자명':<10}{'횟수':<6}{'구분':<8}{'내원일'}\n")
    f.write("-" * 95 + "\n")
    for r in count_rows:
        cohort_d, pk, sn, name, cnt = r[0], r[1], r[2], r[3], r[4]
        구분 = "삼진✓" if cnt >= 3 else ("재진✓" if cnt >= 2 else "1회만")
        dates = ", ".join(date_map[pk])
        f.write(f"{str(cohort_d):<10}{str(sn):<10}{str(name):<10}{str(cnt)+'회':<6}{구분:<8}{dates}\n")
