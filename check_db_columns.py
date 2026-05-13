"""
OK차트 DB 컬럼 진단 스크립트
재진률/삼진률 계산에 필요한 필드 확인용
"""
import pyodbc

CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=(local)\\OKCHART;"
    "DATABASE=MasterDB;"
    "UID=members;"
    "PWD=msp1234;"
)

conn = pyodbc.connect(CONN_STR, timeout=10)
cursor = conn.cursor()

# ── 1. Detail 테이블 컬럼 목록 ────────────────────────────
print("=" * 60)
print("[Detail 테이블 컬럼]")
cursor.execute("""
    SELECT COLUMN_NAME, DATA_TYPE
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'Detail'
    ORDER BY ORDINAL_POSITION
""")
for row in cursor.fetchall():
    print(f"  {row[0]:30s} {row[1]}")

# ── 2. Detail 샘플 1행 (최근 데이터) ─────────────────────
print("\n[Detail 샘플 1행]")
cursor.execute("SELECT TOP 1 * FROM Detail ORDER BY TxDate DESC")
cols = [d[0] for d in cursor.description]
row  = cursor.fetchone()
if row:
    for c, v in zip(cols, row):
        print(f"  {c:30s} = {v}")

# ── 3. 초진/재진 관련 컬럼 값 샘플 ──────────────────────
print("\n[초진 포함 행 샘플 (PxName 기준)]")
try:
    cursor.execute("""
        SELECT TOP 3 TxDate, TxDoctor, Customer_PK, PxName
        FROM Detail
        WHERE PxName LIKE N'%초진%'
        ORDER BY TxDate DESC
    """)
    for r in cursor.fetchall():
        print(f"  {r}")
except Exception as e:
    print(f"  PxName 없음: {e}")

print("\n[초진 포함 행 샘플 (TxItem 기준)]")
try:
    cursor.execute("""
        SELECT TOP 3 TxDate, TxDoctor, Customer_PK, TxItem
        FROM Detail
        WHERE TxItem LIKE N'%초진%'
        ORDER BY TxDate DESC
    """)
    for r in cursor.fetchall():
        print(f"  {r}")
except Exception as e:
    print(f"  TxItem 없음: {e}")

# ── 4. Customer 테이블 컬럼 확인 ─────────────────────────
print("\n[Customer 테이블 컬럼]")
try:
    cursor.execute("""
        SELECT COLUMN_NAME, DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'Customer'
        ORDER BY ORDINAL_POSITION
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]:30s} {row[1]}")
except Exception as e:
    print(f"  Customer 테이블 없음: {e}")

conn.close()
print("\n진단 완료.")
