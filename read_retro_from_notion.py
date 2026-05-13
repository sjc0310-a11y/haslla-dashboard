"""
Notion '원장팀 주간 회고' DB → data/retro.json

매일 update_dashboard.bat 실행 시 같이 돌면서 노션 회고를 로컬 JSON으로 동기화.
generate_dashboard.py가 이 JSON을 읽어 index.html에 임베드한다.
"""

import json
import sys
import subprocess
from pathlib import Path

try:
    import yaml
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyyaml"])
    import yaml

try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests


SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
OUT_PATH = DATA_DIR / "retro.json"

CONFIG_PATH = Path(r"C:\Users\하슬라한의원\하슬라한의원_상담시스템\config.yaml")
DB_ID = "a59dc6c66fe94b31b78fee7770dc12aa"


def get_notion_token() -> str:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg["notion"]["token"]


def headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def fetch_all(token: str) -> list:
    url = f"https://api.notion.com/v1/databases/{DB_ID}/query"
    out, payload = [], {"page_size": 100}
    while True:
        r = requests.post(url, headers=headers(token), json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        out.extend(data["results"])
        if not data.get("has_more"):
            break
        payload["start_cursor"] = data["next_cursor"]
    return out


def plain(prop: dict) -> str:
    if not prop:
        return ""
    items = prop.get("rich_text") or prop.get("title") or []
    return "".join(it.get("plain_text", "") for it in items).strip()


def parse(page: dict) -> dict:
    p = page["properties"]
    # 우선순위: '월요일' DATE → fallback to '주차' TITLE
    week = ""
    monday = (p.get("월요일", {}) or {}).get("date") or {}
    if monday.get("start"):
        week = monday["start"][:10]  # YYYY-MM-DD
    if not week:
        week = plain(p.get("주차"))
    return {
        "week_label": week,
        "doctor": (p.get("원장", {}).get("select") or {}).get("name", ""),
        "good": plain(p.get("잘한 점")),
        "bad": plain(p.get("아쉬웠던 점")),
        "plan": plain(p.get("다음 주 실행 계획")),
        "page_url": page.get("url", ""),
    }


def main():
    print("Notion 회고 데이터 동기화 중...")
    token = get_notion_token()
    pages = fetch_all(token)
    rows = [parse(p) for p in pages if parse(p)["week_label"] and parse(p)["doctor"]]
    rows.sort(key=lambda r: (r["week_label"], r["doctor"]))
    OUT_PATH.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  {len(rows)}건 → {OUT_PATH}")


if __name__ == "__main__":
    main()
