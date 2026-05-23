# -*- coding: utf-8 -*-
"""1on1 면담 대시보드 빌더.

두 종류의 산출물을 만든다:

1) 1on1_local.html  — 한의원 PC 전용 편집 화면. 평문 데이터를 직접 인라인.
                       .gitignore 대상이라 절대 GitHub Pages로 새어 나가지 않음.
                       serve_1on1.py 와 짝지어 자동 저장.

2) 1on1.html + 1on1.enc.json
                     — GitHub Pages publish 대상. 회의록은 AES-256-GCM 으로
                       암호화되어 1on1.enc.json 에 들어 있고, 1on1.html 은
                       비밀번호 입력 → 브라우저 SubtleCrypto 로 복호화 → 읽기 전용
                       표시. 비번 모르면 환자가 URL 알아도 내용 못 봄.

비번은 한의원 PC의 환경변수 HASLLA_1ON1_PASSWORD 에서 읽는다.

데이터 스키마 (data/1on1.json):
  {
    "doctors": ["이문환", ...],
    "projects": {
      "이문환": [
        {
          "id": "p_xxxx", "name": "...",
          "priority": "High|Mid|Low",
          "status":   "Inbox|In Progress|Done",
          "mood":     "😎|😀|😇|" (현재 전체적인 분위기),
          "created":  "YYYY-MM-DD",
          "memo":     "...",
          "learnings": [
            {"date": "YYYY-MM-DD", "text": "...", "meeting_id": "m_xxxx" or null}
          ]
        }
      ]
    },
    "notes": {
      "이문환": [
        {
          "id": "m_xxxx",
          "date": "YYYY-MM-DD", "month": "YYYY-MM",
          "done": false,
          "mood": "😎|😀|😇|" (그 면담의 전반 분위기),
          "work":   "...",
          "career": "...",
          "topic_projects": ["p_xx", "p_yy"],   # Conversation Topic — 다룰 프로젝트
          "support": [
            {"id":"s_xxxx", "type":"Alignment|Decision|Help",
             "need":"...", "reviewed": false,
             "project_id": "p_xx" or null}      # null = 일반 Support
          ]
        }
      ]
    }
  }
"""
from __future__ import annotations

import base64
import io
import json
import os
import secrets
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# pythonw.exe 실행 시 stdout/stderr None — print 시 죽음 방지
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# Windows 한글 콘솔(cp949) 대응
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "cryptography"])
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes

# 템플릿은 별도 파일 — UI 수정 시 generate_1on1.py 안 건드려도 됨
from templates_1on1 import PAGE_TEMPLATE, PUBLIC_TEMPLATE

# ─── 경로 ────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parent
LOCAL_DIR  = ROOT / "data"
DATA_JSON  = LOCAL_DIR / "1on1.json"
OUT_LOCAL  = ROOT / "1on1_local.html"
OUT_PUBLIC = ROOT / "1on1.html"
OUT_ENC    = ROOT / "1on1.enc.json"

PBKDF2_ITER = 200_000

# ─── 대상 부원장 (입사·퇴사 시 이 줄만 수정) ─────────────
VICE_DOCTORS = ["이문환", "방민준", "선주천(예시)"]

DOC_COLORS = {
    "이문환": "#10b981",
    "방민준": "#f59e0b",
    "선주천(예시)": "#a78bfa",   # 보라 — 예시용임을 시각적으로 구분
    "_default": "#64748b",
}


# ─── 데이터 로드 ─────────────────────────────────────────
def load_doc_revenue():
    path = LOCAL_DIR / "원장별현황.csv"
    cols = ["날짜","원장명","건보매출","자보매출","비급여매출","린다이어트",
            "TA초진","건보초진","재초진","재진"]
    if not path.exists():
        return pd.DataFrame(columns=cols)
    df = pd.read_csv(path, encoding="utf-8-sig")
    df["날짜"] = pd.to_datetime(df["날짜"])
    for col in cols[2:]:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    return df


def load_retention():
    path = LOCAL_DIR / "retention.csv"
    cols = ["날짜","원장명","코호트","재진","삼진","재진률","삼진률"]
    if not path.exists():
        return pd.DataFrame(columns=cols)
    df = pd.read_csv(path, encoding="utf-8-sig")
    df["날짜"] = pd.to_datetime(df["날짜"])
    for col in ["코호트","재진","삼진"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    for col in ["재진률","삼진률"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(float)
    return df


def load_chuna():
    path = LOCAL_DIR / "추나현황.csv"
    if not path.exists():
        return pd.DataFrame(columns=["날짜","원장명","건보추나","TA추나"])
    df = pd.read_csv(path, encoding="utf-8-sig")
    df["날짜"] = pd.to_datetime(df["날짜"])
    df["건보추나"] = pd.to_numeric(df["건보추나"], errors="coerce").fillna(0).astype(int)
    df["TA추나"]   = pd.to_numeric(df["TA추나"],   errors="coerce").fillna(0).astype(int)
    return df


def _new_id(prefix):
    return f"{prefix}_{secrets.token_hex(4)}"


def _migrate_note(n):
    n.setdefault("id", _new_id("m"))
    n.setdefault("mood", "")
    n.setdefault("topic_projects", [])
    for s in n.get("support", []):
        s.setdefault("id", _new_id("s"))
        s.setdefault("project_id", None)
    return n


def _migrate_project(p):
    p.setdefault("id", _new_id("p"))
    p.setdefault("learnings", [])
    p.setdefault("created", "")
    p.setdefault("memo", "")
    return p


def load_notes():
    if not DATA_JSON.exists():
        return {"doctors": list(VICE_DOCTORS), "notes": {}, "projects": {}}
    raw = json.loads(DATA_JSON.read_text(encoding="utf-8"))
    raw.setdefault("doctors", list(VICE_DOCTORS))
    raw.setdefault("notes", {})
    raw.setdefault("projects", {})
    for doc in VICE_DOCTORS:
        raw["notes"].setdefault(doc, [])
        raw["projects"].setdefault(doc, [])
        raw["notes"][doc]    = [_migrate_note(n)    for n in raw["notes"][doc]]
        raw["projects"][doc] = [_migrate_project(p) for p in raw["projects"][doc]]
    return raw


# ─── 월간 지표 계산 ──────────────────────────────────────
def _month_key(d):
    return f"{d.year:04d}-{d.month:02d}"


def calc_monthly_metrics(df_doc, df_ret, df_chuna, n_months=6):
    today  = pd.Timestamp.today().normalize()
    cutoff = (today - pd.DateOffset(months=n_months-1)).replace(day=1)

    months = []
    cur = cutoff
    while cur <= today:
        months.append(_month_key(cur))
        cur = (cur + pd.DateOffset(months=1)).replace(day=1)

    by_doc = {}
    for doc in VICE_DOCTORS:
        ddoc = df_doc[df_doc["원장명"] == doc].copy() if not df_doc.empty else df_doc.copy()
        dret = df_ret[df_ret["원장명"] == doc].copy() if not df_ret.empty else df_ret.copy()
        dchu = df_chuna[df_chuna["원장명"] == doc].copy() if not df_chuna.empty else df_chuna.copy()

        rows = []
        for mk in months:
            y, m = map(int, mk.split("-"))
            start = pd.Timestamp(year=y, month=m, day=1)
            end   = (start + pd.DateOffset(months=1))

            d_m = ddoc[(ddoc["날짜"] >= start) & (ddoc["날짜"] < end)]
            r_m = dret[(dret["날짜"] >= start) & (dret["날짜"] < end)]
            c_m = dchu[(dchu["날짜"] >= start) & (dchu["날짜"] < end)]

            kbo_rev = int(d_m["건보매출"].sum())
            jbo_rev = int(d_m["자보매출"].sum())
            nin_rev = int(d_m["비급여매출"].sum())
            linda   = int(d_m["린다이어트"].sum())
            ta_n    = int(d_m["TA초진"].sum())
            kbo_n   = int(d_m["건보초진"].sum())
            fol_n   = int(d_m["재초진"].sum())
            re_n    = int(d_m["재진"].sum())

            work_days = int(d_m["날짜"].dt.normalize().nunique()) if not d_m.empty else 0

            if not r_m.empty:
                tot_co = int(r_m["코호트"].sum())
                tot_re = int(r_m["재진"].sum())
                tot_th = int(r_m["삼진"].sum())
                rev_rate   = round(tot_re / tot_co * 100, 1) if tot_co > 0 else 0.0
                third_rate = round(tot_th / tot_co * 100, 1) if tot_co > 0 else 0.0
                n_weeks    = int(r_m.shape[0])
            else:
                rev_rate, third_rate, n_weeks = 0.0, 0.0, 0

            chuna_kbo = int(c_m["건보추나"].sum())
            chuna_ta  = int(c_m["TA추나"].sum())

            rows.append({
                "month": mk,
                "revenue": {
                    "건보": kbo_rev, "자보": jbo_rev, "비급여": nin_rev,
                    "린다이어트": linda, "total": kbo_rev + jbo_rev + nin_rev,
                },
                "first": {
                    "ta": ta_n, "kbo": kbo_n, "follow": fol_n,
                    "초진합계": ta_n + kbo_n,
                    "전체": ta_n + kbo_n + fol_n + re_n,
                },
                "visits": ta_n + kbo_n + fol_n + re_n,
                "retention": {
                    "revisit_rate": rev_rate, "third_rate": third_rate,
                    "n_weeks": n_weeks,
                },
                "chuna": {
                    "건보": chuna_kbo, "TA": chuna_ta,
                    "총합": chuna_kbo + chuna_ta,
                },
                "work_days": work_days,
            })
        by_doc[doc] = rows

    return {"months": months, "by_doc": by_doc}


# ─── 빌드 ─────────────────────────────────────────────────
def build_html(metrics, state, template, readonly=False):
    now_str = datetime.now().strftime("%Y년 %m월 %d일 %H:%M")
    html = template
    html = html.replace("__GEN_TIME__", now_str)
    html = html.replace("__VICE_DOCTORS__", json.dumps(VICE_DOCTORS, ensure_ascii=False))
    html = html.replace("__DOC_COLORS__",   json.dumps(DOC_COLORS, ensure_ascii=False))
    html = html.replace("__METRICS__",      json.dumps(metrics, ensure_ascii=False))
    html = html.replace("__STATE__",        json.dumps(state, ensure_ascii=False))
    html = html.replace("__READONLY__",     "true" if readonly else "false")
    return html


def encrypt_payload(payload: dict, password: str) -> dict:
    salt = secrets.token_bytes(16)
    iv   = secrets.token_bytes(12)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                     iterations=PBKDF2_ITER)
    key = kdf.derive(password.encode("utf-8"))
    aes = AESGCM(key)
    plaintext = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ct_and_tag = aes.encrypt(iv, plaintext, None)
    return {
        "version": 1,
        "kdf": "PBKDF2-SHA256",
        "iterations": PBKDF2_ITER,
        "salt": base64.b64encode(salt).decode(),
        "iv":   base64.b64encode(iv).decode(),
        "data": base64.b64encode(ct_and_tag).decode(),
        "generated": datetime.now().isoformat(timespec="seconds"),
    }


def decrypt_payload(blob: dict, password: str) -> dict:
    salt = base64.b64decode(blob["salt"])
    iv   = base64.b64decode(blob["iv"])
    ct   = base64.b64decode(blob["data"])
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                     iterations=blob["iterations"])
    key = kdf.derive(password.encode("utf-8"))
    aes = AESGCM(key)
    pt  = aes.decrypt(iv, ct, None)
    return json.loads(pt.decode("utf-8"))


def main():
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    df_doc   = load_doc_revenue()
    df_ret   = load_retention()
    df_chuna = load_chuna()
    metrics  = calc_monthly_metrics(df_doc, df_ret, df_chuna)
    state    = load_notes()

    # 1) 로컬 편집용 — 평문 인라인, readonly=false
    local_html = build_html(metrics, state, PAGE_TEMPLATE, readonly=False)
    OUT_LOCAL.write_text(local_html, encoding="utf-8")
    print(f"[ok] {OUT_LOCAL.name} 생성 — 부원장 {len(VICE_DOCTORS)}명, 최근 {len(metrics['months'])}개월 지표")
    for doc in VICE_DOCTORS:
        rows = metrics["by_doc"].get(doc, [])
        if rows:
            last = rows[-1]
            print(f"  · {doc}: {last['month']} 매출 {last['revenue']['total']:,}원 · 재진율 {last['retention']['revisit_rate']}%")

    # 2) 공개 빌드 — 환경변수 HASLLA_1ON1_PASSWORD 있을 때만
    password = os.environ.get("HASLLA_1ON1_PASSWORD", "").strip()
    if not password:
        print("[skip] 공개 빌드 건너뜀 — 환경변수 HASLLA_1ON1_PASSWORD 미설정")
        return
    if len(password) < 8:
        print("[error] HASLLA_1ON1_PASSWORD 가 8자 미만입니다.")
        sys.exit(2)

    payload = {"metrics": metrics, "state": state, "vice_doctors": VICE_DOCTORS,
               "doc_colors": DOC_COLORS}
    enc = encrypt_payload(payload, password)
    try:
        rt = decrypt_payload(enc, password)
        assert rt == payload, "round-trip mismatch"
    except Exception as e:
        print(f"[error] 암호화 자체 검증 실패: {e}")
        sys.exit(3)

    OUT_ENC.write_text(json.dumps(enc, ensure_ascii=False, indent=2), encoding="utf-8")
    # 공개 페이지는 PUBLIC_TEMPLATE — 비번 화면 + 복호화 → 동일 PAGE 렌더링(readonly=true)
    public_html = build_html(metrics, state, PUBLIC_TEMPLATE, readonly=True)  # state는 사용 안 함 (enc.json 통해 옴)
    OUT_PUBLIC.write_text(public_html, encoding="utf-8")
    print(f"[ok] {OUT_PUBLIC.name} + {OUT_ENC.name} 생성 — 비번 길이 {len(password)}자, "
          f"암호문 {len(enc['data'])}자")


if __name__ == "__main__":
    main()
