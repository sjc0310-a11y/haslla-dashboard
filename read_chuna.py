"""
OK차트 DB → 일별 원장별 건보추나/TA추나 건수 (data/추나현황.csv)

기존엔 구글 시트(원장이 수동 입력)에서 가져왔는데, 입력 누락 시 데이터가
실제보다 적게 잡힘. 대신 OK차트의 Detail 테이블에서 직접 카운트한다.

  건보추나 = Detail.PxName LIKE '%추나%' AND TxItem = '보험치료'
  TA추나   = Detail.PxName LIKE '%추나%' AND TxItem = '자동차보험'

OK차트의 추나 항목: 단순추나(PxCode 40710), 복잡추나(40721) 등.
"""

import csv, sys, subprocess
from pathlib import Path
from collections import defaultdict

try:
    import pyodbc
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyodbc"])
    import pyodbc

from read_okchart import CONN_STR

CSV_PATH = Path(r"C:\Users\하슬라한의원\한의원지표\data\추나현황.csv")

SQL_CHUNA = """
SELECT
    CONVERT(DATE, TxDate) AS 날짜,
    TxDoctor              AS 원장명,
    SUM(CASE WHEN TxItem = N'보험치료'    THEN 1 ELSE 0 END) AS 건보추나,
    SUM(CASE WHEN TxItem = N'자동차보험' THEN 1 ELSE 0 END) AS TA추나
FROM Detail
WHERE TxDate >= DATEADD(month, -6, GETDATE())
  AND PxName LIKE N'%추나%'
  AND TxDoctor != N'선주천'
GROUP BY CONVERT(DATE, TxDate), TxDoctor
ORDER BY 날짜, 원장명
"""


def main():
    print("OK차트 DB 연결 중...")
    conn = pyodbc.connect(CONN_STR, timeout=20)
    cur = conn.cursor()
    cur.execute(SQL_CHUNA)
    rows = []
    for 날짜, 원장명, 건보, ta in cur.fetchall():
        if not 원장명:
            continue
        rows.append({
            "날짜":     str(날짜),
            "원장명":   str(원장명),
            "건보추나": int(건보 or 0),
            "TA추나":   int(ta   or 0),
        })
    conn.close()

    CSV_PATH.parent.mkdir(exist_ok=True)
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["날짜","원장명","건보추나","TA추나"],
                           quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(rows)

    print(f"완료: {len(rows)}행 → {CSV_PATH}")

    # 최근 1주 미리보기
    if rows:
        last_dates = sorted({r["날짜"] for r in rows})[-7:]
        print(f"\n[최근 진료일별 추나]")
        by_date = defaultdict(list)
        for r in rows:
            if r["날짜"] in last_dates:
                by_date[r["날짜"]].append(r)
        for d in last_dates:
            recs = by_date[d]
            parts = [f"{r['원장명']} 건보{r['건보추나']}/TA{r['TA추나']}" for r in recs]
            print(f"  {d}  " + ", ".join(parts))


if __name__ == "__main__":
    main()
