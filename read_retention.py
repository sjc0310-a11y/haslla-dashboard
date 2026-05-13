"""
OK차트 DB → 원장별 주별 재진/삼진률 계산
출력: data/retention.csv

계산 원칙:
  · 재초진 기준: 전체 내원 공백 45일 초과
  · 에피소드 귀속: 에피소드 시작일(첫 내원일, 모든 원장 기준)의
                  첫 번째 진료 원장(Detail_PK 순) 기준
  · 재진률: 코호트 중 기준일까지 2회 이상 내원 비율
  · 삼진률: 코호트 중 기준일까지 3회 이상 내원 비율
"""

import csv
from pathlib import Path
from datetime import date, timedelta

try:
    import pyodbc
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyodbc"])
    import pyodbc

CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=(local)\\OKCHART;"
    "DATABASE=MasterDB;"
    "UID=members;"
    "PWD=msp1234;"
)
CSV_PATH = Path(r"C:\Users\하슬라한의원\한의원지표\data\retention.csv")
GAP_DAYS = 45


def get_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def compute_week(cursor, ref_monday: date) -> dict:
    cohort_start = ref_monday - timedelta(days=21)
    cohort_end   = ref_monday - timedelta(days=15)
    track_end    = ref_monday - timedelta(days=1)

    sql = f"""
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
        WHERE visit_date BETWEEN '{cohort_start}' AND '{cohort_end}'
          AND (prev_visit IS NULL OR DATEDIFF(day, prev_visit, visit_date) > {GAP_DAYS})
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
        -- 비급여 전용 환자 제외: 코호트 시작일에 건보/자보 항목(InsuYes=1)이 있어야 함
        -- (한약, 다이어트, 감기 비급여 약만 받은 환자 제외)
        WHERE EXISTS (
            SELECT 1 FROM Detail d2
            WHERE d2.Customer_PK = es.Customer_PK
              AND CONVERT(DATE, d2.TxDate) = es.visit_date
              AND d2.InsuYes = 1
        )
    ),
    visit_counts AS (
        SELECT c.Customer_PK, c.first_doctor,
               COUNT(DISTINCT CONVERT(DATE, d.TxDate)) AS visit_count
        FROM cohort c
        JOIN Detail d ON d.Customer_PK = c.Customer_PK
        WHERE CONVERT(DATE, d.TxDate) BETWEEN c.cohort_date AND '{track_end}'
        GROUP BY c.Customer_PK, c.first_doctor
    )
    SELECT
        first_doctor,
        COUNT(*)                                                                   AS 코호트,
        SUM(CASE WHEN visit_count >= 2 THEN 1 ELSE 0 END)                         AS 재진,
        SUM(CASE WHEN visit_count >= 3 THEN 1 ELSE 0 END)                         AS 삼진,
        ROUND(100.0 * SUM(CASE WHEN visit_count >= 2 THEN 1 ELSE 0 END)
              / NULLIF(COUNT(*), 0), 1)                                            AS 재진률,
        ROUND(100.0 * SUM(CASE WHEN visit_count >= 3 THEN 1 ELSE 0 END)
              / NULLIF(COUNT(*), 0), 1)                                            AS 삼진률
    FROM visit_counts
    WHERE first_doctor != N'선주천'
    GROUP BY first_doctor
    ORDER BY first_doctor
    """

    cursor.execute(sql)
    results = {}
    for row in cursor.fetchall():
        doc = str(row[0])
        results[doc] = {
            "cohort":       int(row[1] or 0),
            "revisit":      int(row[2] or 0),
            "third":        int(row[3] or 0),
            "revisit_rate": float(row[4] or 0),
            "third_rate":   float(row[5] or 0),
        }
    return results


def main():
    print("OK차트 DB 연결 중...")
    conn = pyodbc.connect(CONN_STR, timeout=30)
    cursor = conn.cursor()

    today        = date.today()
    start_monday = get_monday(today - timedelta(weeks=29))
    end_monday   = get_monday(today)

    rows = []
    ref = start_monday
    while ref <= end_monday:
        cohort_s = ref - timedelta(days=21)
        cohort_e = ref - timedelta(days=15)
        print(f"  {ref} 기준 (코호트 {cohort_s}~{cohort_e})", end=" ... ", flush=True)

        week_data = compute_week(cursor, ref)
        if week_data:
            for doc, v in week_data.items():
                rows.append({
                    "날짜":   str(ref),
                    "원장명":  doc,
                    "코호트": v["cohort"],
                    "재진":   v["revisit"],
                    "삼진":   v["third"],
                    "재진률": v["revisit_rate"],
                    "삼진률": v["third_rate"],
                })
            print(", ".join(
                f"{d}({v['revisit_rate']}%/{v['third_rate']}%)"
                for d, v in week_data.items()
            ))
        else:
            print("데이터 없음")

        ref += timedelta(weeks=1)

    conn.close()

    FIELDS = ["날짜", "원장명", "코호트", "재진", "삼진", "재진률", "삼진률"]
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(rows)

    print(f"\n완료: {len(rows)}행 → {CSV_PATH}")


if __name__ == "__main__":
    main()
