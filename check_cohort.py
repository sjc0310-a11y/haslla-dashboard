"""
재초진 기준: 45일
목적: 통증/TA 침치료 환자(건보/자보)의 반복 내원율 측정
비급여 전용 환자(치료한약, 다이어트 등) 제외 — 코호트 시작일에 건보/자보 항목(InsuYes=1) 없으면 제외
"""
import pyodbc

CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=(local)\\OKCHART;"
    "DATABASE=MasterDB;"
    "UID=members;"
    "PWD=msp1234;"
)

TARGET_DOCTOR = "노왕식"
COHORT_START  = "2026-04-06"
COHORT_END    = "2026-04-12"
GAP_DAYS      = 45

SQL = f"""
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
    WHERE visit_date BETWEEN '{COHORT_START}' AND '{COHORT_END}'
      AND (prev_visit IS NULL OR DATEDIFF(day, prev_visit, visit_date) > {GAP_DAYS})
),
cohort AS (
    SELECT es.Customer_PK, es.visit_date, es.prev_visit, es.gap_days,
           (SELECT TOP 1 TxDoctor
            FROM Detail d
            WHERE d.Customer_PK = es.Customer_PK
              AND CONVERT(DATE, d.TxDate) = es.visit_date
            ORDER BY d.Detail_PK ASC) AS first_doctor
    FROM episode_starts es
    -- 비급여 전용 환자 제외: 코호트 시작일에 건보/자보 항목이 하나라도 있어야 함
    WHERE EXISTS (
        SELECT 1 FROM Detail d2
        WHERE d2.Customer_PK = es.Customer_PK
          AND CONVERT(DATE, d2.TxDate) = es.visit_date
          AND d2.InsuYes = 1
    )
)
SELECT
    co.visit_date  AS 날짜,
    c.sn           AS 차트번호,
    c.name         AS 환자명,
    co.prev_visit  AS 직전내원일,
    co.gap_days    AS 공백일수,
    CASE WHEN co.prev_visit IS NULL THEN '신환' ELSE '재초진' END AS 구분
FROM cohort co
JOIN Customer c ON c.Customer_PK = co.Customer_PK
WHERE co.first_doctor = N'{TARGET_DOCTOR}'
ORDER BY co.visit_date, c.sn
"""

conn = pyodbc.connect(CONN_STR, timeout=30)
cursor = conn.cursor()
cursor.execute(SQL)
rows = cursor.fetchall()
conn.close()

with open("temp_result.txt", "w", encoding="utf-8") as f:
    f.write(f"=== {TARGET_DOCTOR} 코호트 ({COHORT_START}~{COHORT_END}) ===\n")
    f.write(f"재초진 기준: {GAP_DAYS}일 / 비급여 전용 환자 제외\n")
    f.write(f"총 {len(rows)}명\n\n")
    f.write(f"{'날짜':<13}{'차트번호':<10}{'환자명':<10}{'직전내원일':<14}{'공백':<8}{'구분'}\n")
    f.write("-" * 62 + "\n")
    for r in rows:
        prev = str(r[3]) if r[3] else "-"
        gap  = f"{r[4]}일" if r[4] else "-"
        f.write(f"{str(r[0]):<13}{str(r[1]):<10}{str(r[2]):<10}{prev:<14}{gap:<8}{r[5]}\n")
