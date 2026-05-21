# -*- coding: utf-8 -*-
"""노션 1on1 DB → data/1on1.json 동기화.

- 면담노트 DB (b0ab68125d674b4ebd18536459994485)
    면담(title) · 면담일(date) · 부원장(select) · Mood(select) · 완료(checkbox)
    · Work(text) · Career(text) · Support(text)
- 프로젝트 DB  (d05c4a9bd8e1483ea3d770ea0082efd4)
    프로젝트(title) · 부원장(select) · Status(select) · Priority(select)
    · Mood(select) · 메모(text) · Learnings(text) · 생성일(date)

Support 파싱:  `[Type] 내용 — 프로젝트명 (resolved)`  형식 한 줄당 한 건
Learnings 파싱: `YYYY-MM-DD 내용`  형식 한 줄당 한 건

매주 일요일 + 한의원 PC 켜져있는 동안 매 5분마다 update_dashboard.bat 이 이걸 호출.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
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

# Windows 한글 콘솔
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT       = Path(__file__).resolve().parent
DATA_DIR   = ROOT / "data"
OUT_PATH   = DATA_DIR / "1on1.json"
CONFIG_PATH = Path(r"C:\Users\하슬라한의원\하슬라한의원_상담시스템\config.yaml")

DB_NOTES    = "b0ab68125d674b4ebd18536459994485"
DB_PROJECTS = "d05c4a9bd8e1483ea3d770ea0082efd4"

VICE_DOCTORS = ["이문환", "방민준"]


# ─── 노션 API ────────────────────────────────────────────
def get_token() -> str:
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    return cfg["notion"]["token"]


def headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def query_db(token: str, db_id: str) -> list:
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    out, payload = [], {"page_size": 100}
    while True:
        r = requests.post(url, headers=headers(token), json=payload, timeout=30)
        r.raise_for_status()
        d = r.json()
        out.extend(d["results"])
        if not d.get("has_more"):
            break
        payload["start_cursor"] = d["next_cursor"]
    return out


# ─── 노션 속성 추출 ──────────────────────────────────────
def _plain(prop) -> str:
    if not prop:
        return ""
    items = prop.get("rich_text") or prop.get("title") or []
    return "".join(it.get("plain_text", "") for it in items).strip()


def _select(prop) -> str:
    return ((prop or {}).get("select") or {}).get("name", "")


def _date(prop) -> str:
    d = (prop or {}).get("date") or {}
    return (d.get("start") or "")[:10]


def _checkbox(prop) -> bool:
    return bool((prop or {}).get("checkbox"))


# ─── 파서 ────────────────────────────────────────────────
_SUPPORT_LINE_RE = re.compile(
    r"^\s*\[(?P<type>[^\]]+)\]\s*(?P<rest>.+?)\s*$"
)
_LEARNING_LINE_RE = re.compile(
    r"^\s*(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<text>.+?)\s*$"
)


def parse_support_lines(text: str, project_name_to_id: dict) -> list:
    """`[Type] 내용 — 프로젝트명 (resolved)` 한 줄당 한 건.

    프로젝트명 부분이 없으면 project_id=None (일반 Support).
    `(resolved)` 가 있으면 reviewed=True.
    """
    out = []
    if not text:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _SUPPORT_LINE_RE.match(line)
        if not m:
            # type 표시가 없어도 그냥 Help 로 처리해 저장
            need = line
            type_ = "Help"
            reviewed = False
            proj_id = None
            if "(resolved)" in need.lower():
                reviewed = True
                need = re.sub(r"\(resolved\)", "", need, flags=re.IGNORECASE).strip()
            out.append({"id": _id_from(line, "s"), "type": type_, "need": need,
                        "reviewed": reviewed, "project_id": proj_id})
            continue
        type_ = m.group("type").strip()
        rest  = m.group("rest").strip()
        reviewed = False
        if re.search(r"\(resolved\)", rest, re.IGNORECASE):
            reviewed = True
            rest = re.sub(r"\(resolved\)", "", rest, flags=re.IGNORECASE).strip()
        proj_id = None
        # `— 프로젝트명` 또는 `- 프로젝트명` 으로 프로젝트 식별
        sep = re.search(r"\s[—\-]\s", rest)
        if sep:
            need = rest[:sep.start()].strip()
            proj_name = rest[sep.end():].strip()
            proj_id = project_name_to_id.get(proj_name)
        else:
            need = rest
        out.append({"id": _id_from(line, "s"), "type": type_, "need": need,
                    "reviewed": reviewed, "project_id": proj_id})
    return out


def parse_learning_lines(text: str, meeting_id_by_date: dict) -> list:
    """`YYYY-MM-DD 내용` 한 줄당 한 건."""
    out = []
    if not text:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _LEARNING_LINE_RE.match(line)
        if not m:
            # 날짜 없으면 오늘 날짜로 저장 (입력 편의)
            out.append({"date": datetime.now().strftime("%Y-%m-%d"),
                        "text": line, "meeting_id": None})
            continue
        d = m.group("date")
        t = m.group("text").strip()
        out.append({"date": d, "text": t,
                    "meeting_id": meeting_id_by_date.get(d)})
    return out


def _id_from(seed: str, prefix: str) -> str:
    """deterministic id — 같은 텍스트면 같은 id (불필요한 diff 방지)."""
    import hashlib
    h = hashlib.md5(seed.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}_{h}"


def _mood(s: str) -> str:
    """노션 select 값 ("😎 좋음") → 이모지만 ("😎"). 빈 값은 빈 문자열."""
    if not s:
        return ""
    # 첫 이모지만 추출
    return s.split()[0]


# ─── 메인 변환 ───────────────────────────────────────────
def parse_project(page) -> dict:
    p = page["properties"]
    return {
        "id": page["id"].replace("-", ""),
        "name": _plain(p.get("프로젝트")),
        "doctor": _select(p.get("부원장")),
        "priority": _select(p.get("Priority")) or "Mid",
        "status":   _select(p.get("Status"))   or "Inbox",
        "mood":     _mood(_select(p.get("Mood"))),
        "created":  _date(p.get("생성일")) or page.get("created_time", "")[:10],
        "memo":     _plain(p.get("메모")),
        "learnings_raw": _plain(p.get("Learnings")),
    }


def parse_note(page, project_name_to_id: dict, meetings_by_date: dict) -> dict:
    p = page["properties"]
    return {
        "id": page["id"].replace("-", ""),
        "doctor": _select(p.get("부원장")),
        "date":   _date(p.get("면담일")) or page.get("created_time","")[:10],
        "mood":   _mood(_select(p.get("Mood"))),
        "done":   _checkbox(p.get("완료")),
        "work":   _plain(p.get("Work")),
        "career": _plain(p.get("Career")),
        "support_raw": _plain(p.get("Support")),
    }


def build_state(projects_pages, notes_pages):
    # 부원장별로 분류
    projects_by_doc = {d: [] for d in VICE_DOCTORS}
    project_name_to_id = {}  # name → id (전체 부원장 공통, 같은 이름 충돌 시 마지막 것)

    for pg in projects_pages:
        p = parse_project(pg)
        if p["doctor"] not in projects_by_doc:
            continue
        projects_by_doc[p["doctor"]].append(p)
        if p["name"]:
            project_name_to_id[p["name"]] = p["id"]

    notes_by_doc = {d: [] for d in VICE_DOCTORS}
    for pg in notes_pages:
        n = parse_note(pg, project_name_to_id, None)
        if n["doctor"] not in notes_by_doc:
            continue
        notes_by_doc[n["doctor"]].append(n)
    # 날짜 오름차순
    for doc in VICE_DOCTORS:
        notes_by_doc[doc].sort(key=lambda x: x["date"])

    # meeting_id_by_date: 각 부원장별 (date → meeting_id) 매핑
    meeting_id_by_date_by_doc = {
        doc: {n["date"]: n["id"] for n in notes_by_doc[doc]}
        for doc in VICE_DOCTORS
    }

    # 프로젝트의 Learnings 텍스트 파싱
    for doc in VICE_DOCTORS:
        for p in projects_by_doc[doc]:
            learnings = parse_learning_lines(
                p.pop("learnings_raw", ""),
                meeting_id_by_date_by_doc[doc],
            )
            learnings.sort(key=lambda l: l["date"])
            p["learnings"] = learnings

    # 면담의 Support 텍스트 파싱 + topic_projects 자동 유도
    for doc in VICE_DOCTORS:
        for n in notes_by_doc[doc]:
            n["month"] = n["date"][:7] if n["date"] else ""
            supports = parse_support_lines(n.pop("support_raw", ""), project_name_to_id)
            n["support"] = supports
            # topic_projects = Support 에 연결된 프로젝트 + Learnings 에 meeting_id 일치하는 프로젝트
            topic = set(s["project_id"] for s in supports if s["project_id"])
            # 이 부원장 프로젝트 중 이 미팅 ID 가 Learnings 에 들어있는 것
            for p in projects_by_doc[doc]:
                if any(l.get("meeting_id") == n["id"] for l in p["learnings"]):
                    topic.add(p["id"])
            n["topic_projects"] = sorted(topic)

    # 필드 정리 — doctor 컬럼 제거 (이미 그룹화됨)
    for doc in VICE_DOCTORS:
        for p in projects_by_doc[doc]:
            p.pop("doctor", None)
        for n in notes_by_doc[doc]:
            n.pop("doctor", None)

    return {
        "doctors":  list(VICE_DOCTORS),
        "projects": projects_by_doc,
        "notes":    notes_by_doc,
    }


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print("[1on1-sync] 노션 → data/1on1.json 동기화 시작")
    token = get_token()
    projects_pages = query_db(token, DB_PROJECTS)
    notes_pages    = query_db(token, DB_NOTES)
    print(f"  · 프로젝트 {len(projects_pages)}건 · 면담 {len(notes_pages)}건 수신")

    state = build_state(projects_pages, notes_pages)
    OUT_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    for doc in VICE_DOCTORS:
        print(f"  · {doc}: 프로젝트 {len(state['projects'][doc])} · 면담 {len(state['notes'][doc])}")
    print(f"[1on1-sync] 저장 완료 → {OUT_PATH}")


if __name__ == "__main__":
    main()
