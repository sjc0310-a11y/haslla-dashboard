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
"""
from __future__ import annotations

import base64
import io
import json
import os
import secrets
import sys
from datetime import datetime, date
from pathlib import Path

import pandas as pd

# Windows 한글 콘솔(cp949) 대응 — em-dash 등 출력 시 깨짐 방지
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 암호화 — cryptography 패키지 (없으면 자동 설치)
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

# ─── 경로 ────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parent
LOCAL_DIR  = ROOT / "data"
DATA_JSON  = LOCAL_DIR / "1on1.json"          # 평문 회의록 (gitignore)
OUT_LOCAL  = ROOT / "1on1_local.html"          # 편집용 (gitignore)
OUT_PUBLIC = ROOT / "1on1.html"                # 공개 (암호화 화면, publish 대상)
OUT_ENC    = ROOT / "1on1.enc.json"            # 암호화 데이터 (publish 대상)

PBKDF2_ITER = 200_000   # 브라우저에서도 1초 안에 도는 수치

# ─── 대상 부원장 (입사·퇴사 시 이 줄만 수정) ─────────────
VICE_DOCTORS = ["이문환", "방민준"]

# 부원장 카드 색상 — 기존 대시보드와 톤 맞춤
DOC_COLORS = {
    "이문환": "#10b981",
    "방민준": "#f59e0b",
    # 새 부원장 추가 시 여기에 색만 등록하면 됨
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


def load_notes():
    """data/1on1.json 로드. 없으면 빈 스켈레톤 반환."""
    if not DATA_JSON.exists():
        return {"doctors": list(VICE_DOCTORS), "notes": {}, "projects": {}}
    raw = json.loads(DATA_JSON.read_text(encoding="utf-8"))
    raw.setdefault("doctors", list(VICE_DOCTORS))
    raw.setdefault("notes", {})
    raw.setdefault("projects", {})
    for doc in VICE_DOCTORS:
        raw["notes"].setdefault(doc, [])
        raw["projects"].setdefault(doc, [])
    return raw


# ─── 월간 지표 계산 ──────────────────────────────────────
def _month_key(d):
    return f"{d.year:04d}-{d.month:02d}"


def calc_monthly_metrics(df_doc, df_ret, df_chuna, n_months=6):
    """부원장별 최근 N개월 객관 지표.

    Returns
    -------
    dict
      {
        "months": ["2026-05", ...],
        "by_doc": {
            "이문환": [
                {"month": "2026-05",
                 "revenue": {"건보":..., "자보":..., "비급여":..., "린다이어트":..., "total":...},
                 "first":  {"ta":..., "kbo":..., "follow":..., "초진합계":..., "전체":...},
                 "visits": int,            # 재진+초진+재초진 (Detail 진찰료 기준 아님, 일별 합)
                 "retention": {"revisit_rate": float, "third_rate": float, "n_weeks": int},
                 "chuna": {"건보":..., "TA":..., "총합":...},
                 "work_days": int,
                },
                ...
            ]
        }
      }
    """
    today  = pd.Timestamp.today().normalize()
    cutoff = (today - pd.DateOffset(months=n_months-1)).replace(day=1)

    # 월 라벨
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

            # 출근일 = 해당 월 데이터가 있는 unique 날짜 수
            work_days = int(d_m["날짜"].dt.normalize().nunique()) if not d_m.empty else 0

            # 재진/삼진율 — 해당 월 안에 있는 모든 코호트의 환자 합으로 가중평균
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
                    "건보": kbo_rev,
                    "자보": jbo_rev,
                    "비급여": nin_rev,
                    "린다이어트": linda,
                    "total": kbo_rev + jbo_rev + nin_rev,
                },
                "first": {
                    "ta": ta_n,
                    "kbo": kbo_n,
                    "follow": fol_n,
                    "초진합계": ta_n + kbo_n,
                    "전체": ta_n + kbo_n + fol_n + re_n,
                },
                "visits": ta_n + kbo_n + fol_n + re_n,
                "retention": {
                    "revisit_rate": rev_rate,
                    "third_rate": third_rate,
                    "n_weeks": n_weeks,
                },
                "chuna": {
                    "건보": chuna_kbo,
                    "TA":   chuna_ta,
                    "총합": chuna_kbo + chuna_ta,
                },
                "work_days": work_days,
            })
        by_doc[doc] = rows

    return {"months": months, "by_doc": by_doc}


# ─── HTML 빌드 ────────────────────────────────────────────
PAGE_TEMPLATE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>부원장 1:1 면담 대시보드</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root {
    --bg: #0f172a;
    --panel: #1e293b;
    --panel2: #273449;
    --border: #334155;
    --text: #e2e8f0;
    --muted: #94a3b8;
    --accent: #38bdf8;
    --good: #22c55e;
    --warn: #f59e0b;
    --bad: #ef4444;
  }
  * { box-sizing: border-box; }
  body { margin:0; font-family:'Pretendard','Apple SD Gothic Neo',sans-serif;
         background:var(--bg); color:var(--text); }
  header { padding:18px 24px; border-bottom:1px solid var(--border);
           display:flex; align-items:center; gap:16px; flex-wrap:wrap; }
  h1 { margin:0; font-size:20px; font-weight:700; }
  .meta { color:var(--muted); font-size:13px; }
  .save-status { margin-left:auto; padding:6px 12px; border-radius:6px;
                 font-size:12px; background:var(--panel); color:var(--muted); }
  .save-status.ok { background:#064e3b; color:#86efac; }
  .save-status.err { background:#7f1d1d; color:#fecaca; }
  .save-status.dirty { background:#78350f; color:#fed7aa; }

  .tabs { padding:0 24px; display:flex; gap:4px; border-bottom:1px solid var(--border);
          background:var(--bg); position:sticky; top:0; z-index:10; }
  .tab { padding:12px 22px; cursor:pointer; border-bottom:3px solid transparent;
         color:var(--muted); font-weight:600; font-size:15px;
         transition:all .15s; }
  .tab:hover { color:var(--text); }
  .tab.active { color:var(--text); border-bottom-color:var(--doc-color, var(--accent)); }

  main { padding:24px; max-width:1400px; margin:0 auto; }
  .doc-page { display:none; }
  .doc-page.active { display:block; }

  /* 섹션 카드 */
  .section { background:var(--panel); border:1px solid var(--border);
             border-radius:12px; padding:20px; margin-bottom:20px; }
  .section h2 { margin:0 0 14px; font-size:16px; font-weight:700;
                display:flex; align-items:center; gap:10px;
                padding-bottom:10px; border-bottom:1px solid var(--border); }
  .section h2 .badge { font-size:11px; padding:2px 8px; border-radius:10px;
                       background:var(--panel2); color:var(--muted);
                       font-weight:500; }

  /* 객관 지표 — 카드 그리드 */
  .kpi-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
              gap:12px; margin-bottom:14px; }
  .kpi { background:var(--panel2); border-radius:8px; padding:14px;
         border-left:3px solid var(--doc-color,var(--accent)); }
  .kpi .label { color:var(--muted); font-size:12px; }
  .kpi .value { font-size:24px; font-weight:700; margin-top:4px; }
  .kpi .delta { font-size:12px; margin-top:4px; }
  .kpi .delta.up { color:var(--good); }
  .kpi .delta.down { color:var(--bad); }
  .kpi .delta.flat { color:var(--muted); }

  /* 미니 차트 */
  .chart-row { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr));
               gap:12px; margin-top:14px; }
  .chart-box { background:var(--panel2); border-radius:8px; padding:12px; }
  .chart-box .title { color:var(--muted); font-size:12px; margin-bottom:6px; }
  .chart-box canvas { width:100%!important; height:140px!important; }

  /* 프로젝트 */
  .proj-table { width:100%; border-collapse:collapse; font-size:14px; }
  .proj-table th { text-align:left; color:var(--muted); font-weight:500;
                   padding:6px 8px; border-bottom:1px solid var(--border); }
  .proj-table td { padding:8px; border-bottom:1px solid var(--border); }
  .proj-table input[type=text] { width:100%; background:transparent;
                                  color:var(--text); border:none; outline:none;
                                  font-size:14px; padding:4px; border-radius:4px; }
  .proj-table input[type=text]:focus { background:var(--panel2); }
  .proj-table select { background:var(--panel2); color:var(--text);
                        border:1px solid var(--border); border-radius:4px; padding:4px; }
  .pill { display:inline-block; padding:2px 8px; border-radius:10px; font-size:11px;
          font-weight:600; }
  .pill.high { background:#7f1d1d; color:#fecaca; }
  .pill.mid  { background:#78350f; color:#fed7aa; }
  .pill.low  { background:#1e3a8a; color:#bfdbfe; }
  .pill.done { background:#064e3b; color:#86efac; }
  .pill.prog { background:#1e3a8a; color:#bfdbfe; }
  .pill.inbox{ background:#374151; color:#d1d5db; }

  .add-btn { background:transparent; color:var(--accent); border:1px dashed var(--border);
             padding:8px 14px; border-radius:6px; cursor:pointer;
             font-size:13px; margin-top:8px; }
  .add-btn:hover { background:var(--panel2); }
  .del-btn { background:transparent; color:var(--bad); border:none; cursor:pointer;
             font-size:14px; padding:4px 8px; }
  .del-btn:hover { color:var(--text); }

  /* 어젠다 textarea */
  textarea.agenda { width:100%; min-height:120px; background:var(--panel2);
                    color:var(--text); border:1px solid var(--border);
                    border-radius:6px; padding:10px; font-size:14px;
                    font-family:inherit; resize:vertical; }
  textarea.agenda:focus { outline:1px solid var(--accent); border-color:var(--accent); }
  .agenda-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
  @media (max-width: 900px) { .agenda-grid { grid-template-columns:1fr; } }
  .agenda-label { color:var(--muted); font-size:13px; margin-bottom:6px;
                   display:flex; justify-content:space-between; align-items:center; }
  .agenda-label .hint { font-size:11px; color:var(--muted); font-weight:400; }

  /* 면담 회차 선택 */
  .meeting-bar { display:flex; gap:8px; align-items:center; flex-wrap:wrap;
                  margin-bottom:14px; }
  .meeting-bar input[type=date] { background:var(--panel2); color:var(--text);
                                    border:1px solid var(--border); padding:6px 10px;
                                    border-radius:6px; font-size:14px; }
  .meeting-bar select { background:var(--panel2); color:var(--text);
                         border:1px solid var(--border); padding:6px 10px;
                         border-radius:6px; font-size:14px; min-width:200px; }
  .new-meeting-btn { background:var(--accent); color:#0f172a; border:none;
                      padding:6px 14px; border-radius:6px; font-weight:600;
                      cursor:pointer; font-size:13px; }
  .new-meeting-btn:hover { opacity:.85; }

  /* Support / Follow-up 리스트 */
  .item-list { list-style:none; padding:0; margin:0; }
  .item-list li { display:flex; align-items:flex-start; gap:10px;
                   padding:8px; border-bottom:1px solid var(--border); }
  .item-list li:last-child { border-bottom:none; }
  .item-list input[type=checkbox] { margin-top:4px; cursor:pointer; }
  .item-list input[type=text] { flex:1; background:transparent; color:var(--text);
                                  border:none; outline:none; font-size:14px; padding:2px; }
  .item-list input[type=text]:focus { background:var(--panel2); border-radius:4px; padding:4px; }
  .type-select { background:var(--panel2); color:var(--text);
                  border:1px solid var(--border); border-radius:4px; padding:2px 6px;
                  font-size:12px; }

  /* 이력 */
  .history { font-size:13px; }
  .history details { border:1px solid var(--border); border-radius:6px;
                       padding:8px 12px; margin-bottom:6px; background:var(--panel2); }
  .history summary { cursor:pointer; color:var(--muted); }
  .history summary strong { color:var(--text); }
  .history .body { margin-top:8px; white-space:pre-wrap; line-height:1.6; }
  .history .body .heading { color:var(--accent); font-weight:600; margin-top:8px; }
</style>
</head>
<body>
<header>
  <h1>📋 부원장 1:1 면담 대시보드</h1>
  <span class="meta">__GEN_TIME__ 기준</span>
  <span id="saveStatus" class="save-status">대기</span>
</header>

<div class="tabs" id="tabs"></div>
<main id="main"></main>

<script>
// ───── 정적 데이터 (generate_1on1.py가 주입) ─────
const VICE_DOCTORS = __VICE_DOCTORS__;
const DOC_COLORS   = __DOC_COLORS__;
const METRICS      = __METRICS__;   // {months, by_doc}
let   STATE        = __STATE__;     // {doctors, notes, projects}

// ───── 유틸 ─────
const fmt = (n) => (n >= 100000) ? (Math.round(n/10000)).toLocaleString() + "만" :
                   (n >= 10000)  ? (n/10000).toFixed(1) + "만" :
                   n.toLocaleString();
const fmtPct = (v) => (v == null) ? "-" : v.toFixed(1) + "%";
const todayStr = () => new Date().toISOString().slice(0,10);
const monthLabel = (mk) => mk.replace("-",".");
const currentMonth = () => {
  const t = new Date();
  return `${t.getFullYear()}-${String(t.getMonth()+1).padStart(2,"0")}`;
};

// ───── 자동 저장 ─────
let saveTimer = null;
let saveDirty = false;
const $status = document.getElementById("saveStatus");
function markDirty() {
  saveDirty = true;
  $status.textContent = "저장 중…";
  $status.className = "save-status dirty";
  clearTimeout(saveTimer);
  saveTimer = setTimeout(doSave, 600);
}
async function doSave() {
  try {
    const res = await fetch("/save", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify(STATE),
    });
    if (!res.ok) throw new Error(res.status);
    saveDirty = false;
    const t = new Date();
    $status.textContent = `저장됨 ${String(t.getHours()).padStart(2,"0")}:${String(t.getMinutes()).padStart(2,"0")}:${String(t.getSeconds()).padStart(2,"0")}`;
    $status.className = "save-status ok";
  } catch(e) {
    $status.textContent = "저장 실패 (로컬 서버 미실행?) — JSON 다운로드";
    $status.className = "save-status err";
    // fallback: 다운로드
    const blob = new Blob([JSON.stringify(STATE, null, 2)], {type:"application/json"});
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "1on1.json";
    a.click();
    URL.revokeObjectURL(url);
  }
}
window.addEventListener("beforeunload", (e) => {
  if (saveDirty) { e.preventDefault(); e.returnValue = ""; }
});

// ───── 탭 렌더 ─────
function renderTabs() {
  const $t = document.getElementById("tabs");
  $t.innerHTML = "";
  VICE_DOCTORS.forEach((doc, i) => {
    const el = document.createElement("div");
    el.className = "tab" + (i===0 ? " active" : "");
    el.textContent = doc + " 원장";
    el.style.setProperty("--doc-color", DOC_COLORS[doc] || DOC_COLORS._default);
    el.dataset.doc = doc;
    el.onclick = () => switchTab(doc);
    $t.appendChild(el);
  });
}

let activeDoc = VICE_DOCTORS[0];
function switchTab(doc) {
  activeDoc = doc;
  document.querySelectorAll(".tab").forEach(el =>
    el.classList.toggle("active", el.dataset.doc === doc));
  document.querySelectorAll(".doc-page").forEach(el =>
    el.classList.toggle("active", el.dataset.doc === doc));
  // chart redraw (탭 활성화 시 캔버스 크기 보정)
  renderCharts(doc);
}

// ───── 페이지 렌더 ─────
function renderPages() {
  const $m = document.getElementById("main");
  $m.innerHTML = "";
  VICE_DOCTORS.forEach((doc, i) => {
    const page = document.createElement("div");
    page.className = "doc-page" + (i===0 ? " active" : "");
    page.dataset.doc = doc;
    page.style.setProperty("--doc-color", DOC_COLORS[doc] || DOC_COLORS._default);
    page.innerHTML = renderPageHTML(doc);
    $m.appendChild(page);
    wireUpPage(doc, page);
  });
}

function renderPageHTML(doc) {
  const months = METRICS.months;
  const rows = METRICS.by_doc[doc] || [];
  const curIdx = rows.length - 1;
  const cur = rows[curIdx] || null;
  const prev = curIdx > 0 ? rows[curIdx-1] : null;

  const kpis = cur ? renderKPIs(cur, prev) : '<div class="meta">데이터 없음</div>';
  const trendCharts = renderTrendChartsHTML(doc);

  return `
    <section class="section">
      <h2>📊 객관 지표 <span class="badge">${months[curIdx] ? monthLabel(months[curIdx]) : "이번 달"}</span></h2>
      ${kpis}
      ${trendCharts}
    </section>

    <section class="section">
      <h2>🗓️ 면담 회차 <span class="badge" id="meetCount-${doc}"></span></h2>
      <div class="meeting-bar">
        <select id="meetSel-${doc}"></select>
        <input type="date" id="meetDate-${doc}">
        <label style="font-size:13px; color:var(--muted);">
          <input type="checkbox" id="meetDone-${doc}"> 완료
        </label>
        <button class="new-meeting-btn" data-action="new-meeting" data-doc="${doc}">+ 새 면담</button>
        <button class="del-btn" data-action="del-meeting" data-doc="${doc}" title="현재 면담 삭제">🗑</button>
      </div>
      <div class="agenda-grid">
        <div>
          <div class="agenda-label">💼 Work Session
            <span class="hint">업무 진행·이슈·R&R</span></div>
          <textarea class="agenda" id="work-${doc}" placeholder="• 이번 달 주요 업무
• 어려움/걸림돌
• 협업 이슈"></textarea>
        </div>
        <div>
          <div class="agenda-label">🌱 Career Session
            <span class="hint">성장·학습·중장기 목표</span></div>
          <textarea class="agenda" id="career-${doc}" placeholder="• 성장 포인트
• 학습/스터디
• 커리어 목표"></textarea>
        </div>
      </div>

      <div style="margin-top:16px;">
        <div class="agenda-label">🤝 Support 필요
          <span class="hint">Alignment(방향 맞추기) / Decision(결정 요청) / Help(도와줘)</span></div>
        <ul class="item-list" id="support-${doc}"></ul>
        <button class="add-btn" data-action="add-support" data-doc="${doc}">+ Support 추가</button>
      </div>
    </section>

    <section class="section">
      <h2>📌 진행 프로젝트</h2>
      <table class="proj-table">
        <thead><tr>
          <th style="width:36%;">프로젝트</th>
          <th style="width:14%;">우선순위</th>
          <th style="width:14%;">상태</th>
          <th style="width:8%;">기분</th>
          <th>한 줄 메모</th>
          <th style="width:40px;"></th>
        </tr></thead>
        <tbody id="proj-${doc}"></tbody>
      </table>
      <button class="add-btn" data-action="add-proj" data-doc="${doc}">+ 프로젝트 추가</button>
    </section>

    <section class="section">
      <h2>↩️ 지난 면담 Follow-up <span class="badge">직전 1회 미해결</span></h2>
      <ul class="item-list" id="followup-${doc}"></ul>
      <div class="meta" id="followup-empty-${doc}" style="display:none; padding:8px;">
        지난 면담 메모가 없거나 모두 완료됨.
      </div>
    </section>

    <section class="section history">
      <h2>📚 과거 면담 기록</h2>
      <div id="history-${doc}"></div>
    </section>
  `;
}

function renderKPIs(cur, prev) {
  const items = [
    { label: "총 매출", value: fmt(cur.revenue.total) + "원",
      delta: deltaPct(cur.revenue.total, prev?.revenue?.total),
      sub: `건보 ${fmt(cur.revenue.건보)} · 자보 ${fmt(cur.revenue.자보)} · 비급 ${fmt(cur.revenue.비급여)}` },
    { label: "재진율", value: fmtPct(cur.retention.revisit_rate),
      delta: deltaPP(cur.retention.revisit_rate, prev?.retention?.revisit_rate),
      sub: `삼진율 ${fmtPct(cur.retention.third_rate)}` },
    { label: "초진 (TA+건보)", value: cur.first.초진합계 + "명",
      delta: deltaPct(cur.first.초진합계, prev?.first?.초진합계),
      sub: `TA ${cur.first.ta} · 건보 ${cur.first.kbo} · 재초진 ${cur.first.follow}` },
    { label: "건보추나", value: cur.chuna.건보 + "건",
      delta: deltaPct(cur.chuna.건보, prev?.chuna?.건보),
      sub: `TA추나 ${cur.chuna.TA}건` },
    { label: "출근일", value: cur.work_days + "일",
      delta: prev ? deltaRaw(cur.work_days, prev.work_days, "일") : { html:"-", cls:"flat" },
      sub: `진료 합계 ${cur.first.전체}회` },
  ];
  return `<div class="kpi-grid">` + items.map(it => `
    <div class="kpi">
      <div class="label">${it.label}</div>
      <div class="value">${it.value}</div>
      <div class="delta ${it.delta.cls}">${it.delta.html}</div>
      <div class="meta" style="font-size:11px; margin-top:4px;">${it.sub}</div>
    </div>
  `).join("") + `</div>`;
}

function deltaPct(cur, prev) {
  if (prev == null || prev === 0) return { html:"전월 데이터 없음", cls:"flat" };
  const d = (cur - prev) / prev * 100;
  const arrow = d > 0 ? "▲" : d < 0 ? "▼" : "—";
  const cls = Math.abs(d) < 1 ? "flat" : (d > 0 ? "up" : "down");
  return { html: `${arrow} ${Math.abs(d).toFixed(1)}% vs 전월`, cls };
}
function deltaPP(cur, prev) {
  if (prev == null) return { html:"전월 데이터 없음", cls:"flat" };
  const d = cur - prev;
  const arrow = d > 0 ? "▲" : d < 0 ? "▼" : "—";
  const cls = Math.abs(d) < 0.5 ? "flat" : (d > 0 ? "up" : "down");
  return { html: `${arrow} ${Math.abs(d).toFixed(1)}p vs 전월`, cls };
}
function deltaRaw(cur, prev, unit) {
  const d = cur - prev;
  const arrow = d > 0 ? "▲" : d < 0 ? "▼" : "—";
  const cls = d === 0 ? "flat" : (d > 0 ? "up" : "down");
  return { html: `${arrow} ${Math.abs(d)}${unit} vs 전월`, cls };
}

function renderTrendChartsHTML(doc) {
  return `<div class="chart-row">
    <div class="chart-box"><div class="title">월별 매출 추이 (만원)</div>
      <canvas id="ch-rev-${doc}"></canvas></div>
    <div class="chart-box"><div class="title">월별 초진·재초진</div>
      <canvas id="ch-first-${doc}"></canvas></div>
    <div class="chart-box"><div class="title">월별 재진율·삼진율 (%)</div>
      <canvas id="ch-ret-${doc}"></canvas></div>
    <div class="chart-box"><div class="title">월별 건보추나 (건)</div>
      <canvas id="ch-chuna-${doc}"></canvas></div>
  </div>`;
}

const charts = {};
function renderCharts(doc) {
  const rows = METRICS.by_doc[doc] || [];
  const labels = rows.map(r => monthLabel(r.month));
  const color = DOC_COLORS[doc] || DOC_COLORS._default;
  const baseOpts = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { labels: { color: "#cbd5e1", font:{size:11} } } },
    scales: {
      x: { ticks: { color:"#94a3b8", font:{size:10} }, grid:{ color:"#1e293b" } },
      y: { ticks: { color:"#94a3b8", font:{size:10} }, grid:{ color:"#1e293b" }, beginAtZero:true },
    },
  };
  // 매출
  destroyIf(`rev-${doc}`);
  charts[`rev-${doc}`] = new Chart(document.getElementById(`ch-rev-${doc}`), {
    type:"bar",
    data:{ labels, datasets:[
      { label:"건보", data: rows.map(r => Math.round(r.revenue.건보/10000)), backgroundColor: color+"99" },
      { label:"자보", data: rows.map(r => Math.round(r.revenue.자보/10000)), backgroundColor: color+"66" },
      { label:"비급여", data: rows.map(r => Math.round(r.revenue.비급여/10000)), backgroundColor: color+"33" },
    ]},
    options: { ...baseOpts, scales:{ ...baseOpts.scales, x:{...baseOpts.scales.x, stacked:true}, y:{...baseOpts.scales.y, stacked:true} } },
  });
  // 초진/재초진
  destroyIf(`first-${doc}`);
  charts[`first-${doc}`] = new Chart(document.getElementById(`ch-first-${doc}`), {
    type:"bar",
    data:{ labels, datasets:[
      { label:"TA초진", data: rows.map(r => r.first.ta), backgroundColor: color },
      { label:"건보초진", data: rows.map(r => r.first.kbo), backgroundColor: color+"99" },
      { label:"재초진", data: rows.map(r => r.first.follow), backgroundColor: color+"55" },
    ]},
    options: baseOpts,
  });
  // 재진율
  destroyIf(`ret-${doc}`);
  charts[`ret-${doc}`] = new Chart(document.getElementById(`ch-ret-${doc}`), {
    type:"line",
    data:{ labels, datasets:[
      { label:"재진율", data: rows.map(r => r.retention.revisit_rate), borderColor:color, backgroundColor:color+"33", tension:.3, fill:false },
      { label:"삼진율", data: rows.map(r => r.retention.third_rate), borderColor:"#94a3b8", borderDash:[4,4], tension:.3, fill:false },
    ]},
    options: { ...baseOpts, scales:{ ...baseOpts.scales, y:{...baseOpts.scales.y, max:100} } },
  });
  // 추나
  destroyIf(`chuna-${doc}`);
  charts[`chuna-${doc}`] = new Chart(document.getElementById(`ch-chuna-${doc}`), {
    type:"bar",
    data:{ labels, datasets:[
      { label:"건보추나", data: rows.map(r => r.chuna.건보), backgroundColor: color },
      { label:"TA추나",   data: rows.map(r => r.chuna.TA),   backgroundColor: color+"55" },
    ]},
    options: baseOpts,
  });
}
function destroyIf(key) { if (charts[key]) { charts[key].destroy(); delete charts[key]; } }

// ───── 면담 노트 관리 ─────
function getNotes(doc) { return STATE.notes[doc] || (STATE.notes[doc] = []); }
function getProjects(doc) { return STATE.projects[doc] || (STATE.projects[doc] = []); }

function ensureCurrentMeeting(doc) {
  const notes = getNotes(doc);
  if (notes.length === 0) {
    notes.push(newMeeting());
  }
  return notes[notes.length - 1];
}
function newMeeting() {
  return {
    id: "m" + Date.now() + Math.floor(Math.random()*1000),
    date: todayStr(),
    month: currentMonth(),
    done: false,
    work: "",
    career: "",
    support: [],
  };
}

function wireUpPage(doc, page) {
  // 면담 회차 셀렉터 채우기
  refreshMeetingSelector(doc);
  // 텍스트 영역 / 체크박스 / 셀렉터 핸들러
  page.querySelectorAll("[data-action]").forEach(btn => {
    btn.addEventListener("click", () => handleAction(btn.dataset.action, btn.dataset.doc, btn));
  });
  document.getElementById(`meetDate-${doc}`).addEventListener("change", e => {
    const m = currentMeeting(doc); if (!m) return;
    m.date = e.target.value; m.month = e.target.value.slice(0,7);
    markDirty(); refreshMeetingSelectorLabels(doc);
  });
  document.getElementById(`meetDone-${doc}`).addEventListener("change", e => {
    const m = currentMeeting(doc); if (!m) return;
    m.done = e.target.checked; markDirty(); refreshMeetingSelectorLabels(doc);
  });
  document.getElementById(`meetSel-${doc}`).addEventListener("change", e => {
    setCurrentMeetingIndex(doc, parseInt(e.target.value));
    loadMeetingIntoUI(doc);
  });
  document.getElementById(`work-${doc}`).addEventListener("input", e => {
    const m = currentMeeting(doc); if (!m) return;
    m.work = e.target.value; markDirty();
  });
  document.getElementById(`career-${doc}`).addEventListener("input", e => {
    const m = currentMeeting(doc); if (!m) return;
    m.career = e.target.value; markDirty();
  });
  loadMeetingIntoUI(doc);
  renderProjects(doc);
  renderCharts(doc);
}

const currentIdx = {};
function currentMeeting(doc) {
  const notes = getNotes(doc);
  if (notes.length === 0) ensureCurrentMeeting(doc);
  let idx = currentIdx[doc];
  if (idx == null || idx >= notes.length) idx = notes.length - 1;
  currentIdx[doc] = idx;
  return notes[idx];
}
function setCurrentMeetingIndex(doc, idx) {
  const notes = getNotes(doc);
  if (idx < 0 || idx >= notes.length) idx = notes.length - 1;
  currentIdx[doc] = idx;
}

function refreshMeetingSelector(doc) {
  const notes = getNotes(doc);
  if (notes.length === 0) ensureCurrentMeeting(doc);
  const sel = document.getElementById(`meetSel-${doc}`);
  sel.innerHTML = "";
  notes.forEach((m, i) => {
    const opt = document.createElement("option");
    opt.value = i;
    opt.textContent = `${m.date} ${m.done ? "✅" : "📝"}`;
    sel.appendChild(opt);
  });
  sel.value = currentIdx[doc] ?? (notes.length - 1);
  document.getElementById(`meetCount-${doc}`).textContent = `${notes.length}회`;
}
function refreshMeetingSelectorLabels(doc) {
  const notes = getNotes(doc);
  const sel = document.getElementById(`meetSel-${doc}`);
  Array.from(sel.options).forEach((opt, i) => {
    const m = notes[i];
    if (m) opt.textContent = `${m.date} ${m.done ? "✅" : "📝"}`;
  });
}

function loadMeetingIntoUI(doc) {
  const m = currentMeeting(doc);
  document.getElementById(`meetDate-${doc}`).value = m.date;
  document.getElementById(`meetDone-${doc}`).checked = !!m.done;
  document.getElementById(`work-${doc}`).value = m.work || "";
  document.getElementById(`career-${doc}`).value = m.career || "";
  renderSupport(doc);
  renderFollowup(doc);
  renderHistory(doc);
  refreshMeetingSelector(doc);
  document.getElementById(`meetSel-${doc}`).value = currentIdx[doc];
}

function renderSupport(doc) {
  const m = currentMeeting(doc);
  const ul = document.getElementById(`support-${doc}`);
  ul.innerHTML = "";
  (m.support || []).forEach((s, i) => {
    const li = document.createElement("li");
    li.innerHTML = `
      <input type="checkbox" ${s.reviewed?"checked":""} data-i="${i}" data-act="sup-rev">
      <select class="type-select" data-i="${i}" data-act="sup-type">
        <option value="Alignment" ${s.type==="Alignment"?"selected":""}>Alignment</option>
        <option value="Decision"  ${s.type==="Decision"?"selected":""}>Decision</option>
        <option value="Help"      ${s.type==="Help"?"selected":""}>Help</option>
      </select>
      <input type="text" value="${escapeHtml(s.need || "")}" placeholder="필요한 지원 사항"
             data-i="${i}" data-act="sup-need">
      <button class="del-btn" data-i="${i}" data-act="sup-del">✕</button>
    `;
    ul.appendChild(li);
  });
  ul.querySelectorAll("[data-act]").forEach(el => {
    el.addEventListener(el.tagName === "SELECT" || el.type === "checkbox" ? "change" : "input", () => {
      const m = currentMeeting(doc);
      const i = parseInt(el.dataset.i);
      const act = el.dataset.act;
      if (act === "sup-rev")  m.support[i].reviewed = el.checked;
      if (act === "sup-type") m.support[i].type = el.value;
      if (act === "sup-need") m.support[i].need = el.value;
      if (act === "sup-del")  { m.support.splice(i, 1); renderSupport(doc); }
      markDirty();
    });
  });
}

function renderProjects(doc) {
  const projects = getProjects(doc);
  const tbody = document.getElementById(`proj-${doc}`);
  tbody.innerHTML = "";
  projects.forEach((p, i) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><input type="text" value="${escapeHtml(p.name||"")}" placeholder="프로젝트명"
                  data-i="${i}" data-act="proj-name"></td>
      <td><select data-i="${i}" data-act="proj-prio">
        <option value="High" ${p.priority==="High"?"selected":""}>High</option>
        <option value="Mid"  ${p.priority==="Mid"?"selected":""}>Mid</option>
        <option value="Low"  ${p.priority==="Low"?"selected":""}>Low</option>
      </select></td>
      <td><select data-i="${i}" data-act="proj-stat">
        <option value="Inbox"       ${p.status==="Inbox"?"selected":""}>Inbox</option>
        <option value="In Progress" ${p.status==="In Progress"?"selected":""}>In Progress</option>
        <option value="Done"        ${p.status==="Done"?"selected":""}>Done</option>
      </select></td>
      <td><select data-i="${i}" data-act="proj-mood">
        <option value="" ${!p.mood?"selected":""}>–</option>
        <option value="😎" ${p.mood==="😎"?"selected":""}>😎</option>
        <option value="😀" ${p.mood==="😀"?"selected":""}>😀</option>
        <option value="😇" ${p.mood==="😇"?"selected":""}>😇</option>
      </select></td>
      <td><input type="text" value="${escapeHtml(p.memo||"")}" placeholder="한 줄 메모/학습"
                  data-i="${i}" data-act="proj-memo"></td>
      <td><button class="del-btn" data-i="${i}" data-act="proj-del">✕</button></td>
    `;
    tbody.appendChild(tr);
  });
  tbody.querySelectorAll("[data-act]").forEach(el => {
    el.addEventListener(el.tagName === "SELECT" ? "change" : "input", () => {
      const i = parseInt(el.dataset.i);
      const act = el.dataset.act;
      const projects = getProjects(doc);
      if (act === "proj-name") projects[i].name = el.value;
      if (act === "proj-prio") projects[i].priority = el.value;
      if (act === "proj-stat") projects[i].status = el.value;
      if (act === "proj-mood") projects[i].mood = el.value;
      if (act === "proj-memo") projects[i].memo = el.value;
      if (act === "proj-del")  { projects.splice(i, 1); renderProjects(doc); }
      markDirty();
    });
  });
}

function renderFollowup(doc) {
  const notes = getNotes(doc);
  const ul = document.getElementById(`followup-${doc}`);
  const empty = document.getElementById(`followup-empty-${doc}`);
  ul.innerHTML = "";
  // 직전 면담(현재 면담의 이전 1회)에서 미해결 Support 끌어오기
  const idx = currentIdx[doc] ?? notes.length - 1;
  const prev = (idx > 0) ? notes[idx - 1] : null;
  const items = [];
  if (prev) {
    (prev.support || []).forEach((s, i) => {
      if (!s.reviewed) items.push({ from: prev.date, type: s.type, need: s.need, sup_idx: i, mid: prev.id });
    });
  }
  if (items.length === 0) {
    empty.style.display = "block";
    return;
  }
  empty.style.display = "none";
  items.forEach((it) => {
    const li = document.createElement("li");
    li.innerHTML = `
      <input type="checkbox" data-mid="${it.mid}" data-sidx="${it.sup_idx}" data-act="fu-done">
      <span style="color:var(--muted); font-size:12px; min-width:90px;">${it.from} · ${it.type}</span>
      <span style="flex:1;">${escapeHtml(it.need || "(내용 없음)")}</span>
    `;
    ul.appendChild(li);
  });
  ul.querySelectorAll("[data-act=fu-done]").forEach(el => {
    el.addEventListener("change", () => {
      const mid = el.dataset.mid;
      const sidx = parseInt(el.dataset.sidx);
      const note = notes.find(n => n.id === mid);
      if (note) note.support[sidx].reviewed = el.checked;
      markDirty();
      renderFollowup(doc);
    });
  });
}

function renderHistory(doc) {
  const notes = getNotes(doc);
  const idx = currentIdx[doc] ?? notes.length - 1;
  const past = notes.slice(0, idx).reverse();   // 현재 회차 이전만, 최신순
  const $h = document.getElementById(`history-${doc}`);
  if (past.length === 0) {
    $h.innerHTML = '<div class="meta">아직 과거 면담 기록 없음.</div>';
    return;
  }
  $h.innerHTML = past.map(n => {
    const supList = (n.support || []).map(s =>
      `&nbsp;&nbsp;[${s.reviewed?"✅":"⬜"} ${s.type}] ${escapeHtml(s.need||"")}`
    ).join("\n") || "(없음)";
    return `<details>
      <summary><strong>${n.date}</strong> ${n.done ? "✅" : "📝"}
        &nbsp;<span class="meta">(work ${(n.work||"").length}자 · career ${(n.career||"").length}자 · support ${(n.support||[]).length}건)</span>
      </summary>
      <div class="body"><span class="heading">💼 Work</span>
${escapeHtml(n.work || "(없음)")}
<span class="heading">🌱 Career</span>
${escapeHtml(n.career || "(없음)")}
<span class="heading">🤝 Support</span>
${supList}</div>
    </details>`;
  }).join("");
}

function handleAction(act, doc, btn) {
  if (act === "new-meeting") {
    const notes = getNotes(doc);
    notes.push(newMeeting());
    currentIdx[doc] = notes.length - 1;
    loadMeetingIntoUI(doc);
    markDirty();
  } else if (act === "del-meeting") {
    const notes = getNotes(doc);
    if (notes.length === 0) return;
    if (!confirm("현재 면담 회차를 삭제할까요?")) return;
    const idx = currentIdx[doc] ?? notes.length - 1;
    notes.splice(idx, 1);
    if (notes.length === 0) notes.push(newMeeting());
    currentIdx[doc] = notes.length - 1;
    loadMeetingIntoUI(doc);
    markDirty();
  } else if (act === "add-support") {
    const m = currentMeeting(doc);
    (m.support = m.support || []).push({ type:"Help", need:"", reviewed:false });
    renderSupport(doc); markDirty();
  } else if (act === "add-proj") {
    const projects = getProjects(doc);
    projects.push({ name:"", priority:"Mid", status:"Inbox", mood:"", memo:"" });
    renderProjects(doc); markDirty();
  }
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, c =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[c]);
}

// 부트
renderTabs();
renderPages();
</script>
</body>
</html>
"""


def build_html(metrics, state):
    now_str = datetime.now().strftime("%Y년 %m월 %d일 %H:%M")
    html = PAGE_TEMPLATE
    html = html.replace("__GEN_TIME__", now_str)
    html = html.replace("__VICE_DOCTORS__", json.dumps(VICE_DOCTORS, ensure_ascii=False))
    html = html.replace("__DOC_COLORS__",   json.dumps(DOC_COLORS, ensure_ascii=False))
    html = html.replace("__METRICS__",      json.dumps(metrics, ensure_ascii=False))
    html = html.replace("__STATE__",        json.dumps(state, ensure_ascii=False))
    return html


# ─── 공개 페이지 (비번 입력 + 복호화 + 읽기 전용) ────────
PUBLIC_TEMPLATE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>부원장 1:1 면담</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root {
    --bg:#0f172a; --panel:#1e293b; --panel2:#273449; --border:#334155;
    --text:#e2e8f0; --muted:#94a3b8; --accent:#38bdf8;
    --good:#22c55e; --warn:#f59e0b; --bad:#ef4444;
  }
  * { box-sizing:border-box; }
  body { margin:0; font-family:'Pretendard','Apple SD Gothic Neo',sans-serif;
         background:var(--bg); color:var(--text); }

  /* 잠금 화면 */
  #lock { position:fixed; inset:0; display:flex; flex-direction:column;
          align-items:center; justify-content:center; background:var(--bg); z-index:100; }
  #lock h1 { font-size:24px; margin:0 0 6px; }
  #lock .sub { color:var(--muted); margin-bottom:24px; font-size:14px; }
  #lock form { display:flex; gap:8px; }
  #lock input { background:var(--panel); color:var(--text);
                border:1px solid var(--border); border-radius:6px;
                padding:10px 14px; font-size:15px; min-width:240px; }
  #lock input:focus { outline:1px solid var(--accent); border-color:var(--accent); }
  #lock button { background:var(--accent); color:#0f172a; border:none;
                  padding:10px 20px; border-radius:6px; font-weight:700;
                  cursor:pointer; font-size:15px; }
  #lock .err { color:var(--bad); margin-top:14px; min-height:18px; font-size:13px; }
  #lock .hint { color:var(--muted); font-size:12px; margin-top:24px; max-width:380px; text-align:center; }

  /* 본문 (잠금 해제 후) */
  header { padding:18px 24px; border-bottom:1px solid var(--border);
           display:flex; align-items:center; gap:16px; flex-wrap:wrap; }
  h1 { margin:0; font-size:20px; font-weight:700; }
  .meta { color:var(--muted); font-size:13px; }
  .ro-badge { margin-left:auto; padding:6px 12px; border-radius:6px;
              font-size:12px; background:#1e293b; color:var(--muted); }
  .tabs { padding:0 24px; display:flex; gap:4px; border-bottom:1px solid var(--border);
          background:var(--bg); position:sticky; top:0; z-index:10; }
  .tab { padding:12px 22px; cursor:pointer; border-bottom:3px solid transparent;
         color:var(--muted); font-weight:600; font-size:15px; }
  .tab:hover { color:var(--text); }
  .tab.active { color:var(--text); border-bottom-color:var(--doc-color, var(--accent)); }
  main { padding:24px; max-width:1400px; margin:0 auto; }
  .doc-page { display:none; }
  .doc-page.active { display:block; }
  .section { background:var(--panel); border:1px solid var(--border);
             border-radius:12px; padding:20px; margin-bottom:20px; }
  .section h2 { margin:0 0 14px; font-size:16px; font-weight:700;
                display:flex; align-items:center; gap:10px;
                padding-bottom:10px; border-bottom:1px solid var(--border); }
  .section h2 .badge { font-size:11px; padding:2px 8px; border-radius:10px;
                       background:var(--panel2); color:var(--muted); font-weight:500; }
  .kpi-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
              gap:12px; margin-bottom:14px; }
  .kpi { background:var(--panel2); border-radius:8px; padding:14px;
         border-left:3px solid var(--doc-color,var(--accent)); }
  .kpi .label { color:var(--muted); font-size:12px; }
  .kpi .value { font-size:24px; font-weight:700; margin-top:4px; }
  .kpi .delta { font-size:12px; margin-top:4px; }
  .kpi .delta.up { color:var(--good); }
  .kpi .delta.down { color:var(--bad); }
  .kpi .delta.flat { color:var(--muted); }
  .chart-row { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr));
               gap:12px; margin-top:14px; }
  .chart-box { background:var(--panel2); border-radius:8px; padding:12px; }
  .chart-box .title { color:var(--muted); font-size:12px; margin-bottom:6px; }
  .chart-box canvas { width:100%!important; height:140px!important; }

  .proj-table { width:100%; border-collapse:collapse; font-size:14px; }
  .proj-table th, .proj-table td { padding:8px; border-bottom:1px solid var(--border); text-align:left; }
  .proj-table th { color:var(--muted); font-weight:500; }
  .pill { display:inline-block; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:600; }
  .pill.high { background:#7f1d1d; color:#fecaca; }
  .pill.mid  { background:#78350f; color:#fed7aa; }
  .pill.low  { background:#1e3a8a; color:#bfdbfe; }
  .pill.done { background:#064e3b; color:#86efac; }
  .pill.prog { background:#1e3a8a; color:#bfdbfe; }
  .pill.inbox{ background:#374151; color:#d1d5db; }

  .agenda-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
  @media (max-width:900px){ .agenda-grid { grid-template-columns:1fr; } }
  .agenda-block { background:var(--panel2); border-radius:8px; padding:12px;
                   white-space:pre-wrap; line-height:1.6; font-size:14px; min-height:80px; }
  .agenda-label { color:var(--muted); font-size:13px; margin-bottom:6px; }

  .item-list { list-style:none; padding:0; margin:0; }
  .item-list li { padding:8px; border-bottom:1px solid var(--border);
                   display:flex; gap:10px; font-size:14px; }
  .item-list li:last-child { border-bottom:none; }

  .meeting-bar { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:14px; }
  .meeting-bar select { background:var(--panel2); color:var(--text);
                         border:1px solid var(--border); padding:6px 10px;
                         border-radius:6px; font-size:14px; min-width:200px; }

  .history details { border:1px solid var(--border); border-radius:6px;
                       padding:8px 12px; margin-bottom:6px; background:var(--panel2); font-size:13px; }
  .history summary { cursor:pointer; color:var(--muted); }
  .history summary strong { color:var(--text); }
  .history .body { margin-top:8px; white-space:pre-wrap; line-height:1.6; }
  .history .body .heading { color:var(--accent); font-weight:600; margin-top:8px; }
</style>
</head>
<body>

<div id="lock">
  <h1>🔒 1:1 면담</h1>
  <div class="sub">비밀번호를 입력하세요</div>
  <form id="lockForm" onsubmit="return false;">
    <input type="password" id="pw" autocomplete="current-password" placeholder="비밀번호" autofocus>
    <button id="unlockBtn">열기</button>
  </form>
  <div class="err" id="lockErr"></div>
  <div class="hint">이 페이지는 부원장 1:1 면담 기록입니다.<br>
    환자·외부인 열람 금지. 비밀번호는 원장만 알고 있습니다.</div>
</div>

<div id="app" style="display:none;">
  <header>
    <h1>📋 부원장 1:1 면담 (읽기 전용)</h1>
    <span class="meta" id="genTime"></span>
    <span class="ro-badge">읽기 전용 · 편집은 한의원 PC에서</span>
  </header>
  <div class="tabs" id="tabs"></div>
  <main id="main"></main>
</div>

<script>
const ENC_URL = "1on1.enc.json";

const $lock = document.getElementById("lock");
const $err  = document.getElementById("lockErr");
const $pw   = document.getElementById("pw");
const $app  = document.getElementById("app");

document.getElementById("unlockBtn").addEventListener("click", unlock);
$pw.addEventListener("keydown", e => { if (e.key === "Enter") unlock(); });

let ENC_BLOB = null;

async function fetchBlob() {
  if (ENC_BLOB) return ENC_BLOB;
  const res = await fetch(ENC_URL + "?_=" + Date.now(), {cache:"no-store"});
  if (!res.ok) throw new Error(`enc 다운로드 실패: ${res.status}`);
  ENC_BLOB = await res.json();
  return ENC_BLOB;
}

async function deriveKey(pw, salt, iter) {
  const enc = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey(
    "raw", enc.encode(pw), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey(
    { name:"PBKDF2", salt, iterations:iter, hash:"SHA-256" },
    keyMaterial,
    { name:"AES-GCM", length:256 },
    false, ["decrypt"]);
}

function b64(s) { return Uint8Array.from(atob(s), c => c.charCodeAt(0)); }

async function unlock() {
  $err.textContent = "";
  const pw = $pw.value;
  if (!pw) { $err.textContent = "비밀번호를 입력하세요."; return; }
  try {
    const blob = await fetchBlob();
    const salt = b64(blob.salt);
    const iv   = b64(blob.iv);
    const ct   = b64(blob.data);
    const key  = await deriveKey(pw, salt, blob.iterations);
    const ptBuf = await crypto.subtle.decrypt({name:"AES-GCM", iv}, key, ct);
    const payload = JSON.parse(new TextDecoder().decode(ptBuf));
    document.getElementById("genTime").textContent = blob.generated + " 생성";
    $lock.style.display = "none";
    $app.style.display  = "block";
    boot(payload);
  } catch (e) {
    console.warn(e);
    $err.textContent = "비밀번호가 틀렸거나 데이터를 가져오지 못했습니다.";
    $pw.select();
  }
}

// ───── 잠금 해제 후 본문 렌더 (편집 핸들러 제거된 읽기 전용 버전) ─────
let VICE_DOCTORS, DOC_COLORS, METRICS, STATE;
const charts = {};

function boot(payload) {
  VICE_DOCTORS = payload.vice_doctors;
  DOC_COLORS   = payload.doc_colors;
  METRICS      = payload.metrics;
  STATE        = payload.state;
  renderTabs();
  renderPages();
}

const monthLabel = (mk) => mk.replace("-",".");
const fmt = (n) => (n >= 100000) ? (Math.round(n/10000)).toLocaleString() + "만" :
                   (n >= 10000)  ? (n/10000).toFixed(1) + "만" :
                   n.toLocaleString();
const fmtPct = (v) => (v == null) ? "-" : v.toFixed(1) + "%";
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, c =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[c]);
}
function deltaPct(cur, prev) {
  if (prev == null || prev === 0) return { html:"전월 데이터 없음", cls:"flat" };
  const d = (cur - prev) / prev * 100;
  const arrow = d > 0 ? "▲" : d < 0 ? "▼" : "—";
  const cls = Math.abs(d) < 1 ? "flat" : (d > 0 ? "up" : "down");
  return { html: `${arrow} ${Math.abs(d).toFixed(1)}% vs 전월`, cls };
}
function deltaPP(cur, prev) {
  if (prev == null) return { html:"전월 데이터 없음", cls:"flat" };
  const d = cur - prev;
  const arrow = d > 0 ? "▲" : d < 0 ? "▼" : "—";
  const cls = Math.abs(d) < 0.5 ? "flat" : (d > 0 ? "up" : "down");
  return { html: `${arrow} ${Math.abs(d).toFixed(1)}p vs 전월`, cls };
}
function deltaRaw(cur, prev, unit) {
  const d = cur - prev;
  const arrow = d > 0 ? "▲" : d < 0 ? "▼" : "—";
  const cls = d === 0 ? "flat" : (d > 0 ? "up" : "down");
  return { html: `${arrow} ${Math.abs(d)}${unit} vs 전월`, cls };
}

function renderTabs() {
  const $t = document.getElementById("tabs");
  $t.innerHTML = "";
  VICE_DOCTORS.forEach((doc,i) => {
    const el = document.createElement("div");
    el.className = "tab" + (i===0?" active":"");
    el.textContent = doc + " 원장";
    el.style.setProperty("--doc-color", DOC_COLORS[doc] || DOC_COLORS._default);
    el.dataset.doc = doc;
    el.onclick = () => switchTab(doc);
    $t.appendChild(el);
  });
}
function switchTab(doc) {
  document.querySelectorAll(".tab").forEach(el =>
    el.classList.toggle("active", el.dataset.doc === doc));
  document.querySelectorAll(".doc-page").forEach(el =>
    el.classList.toggle("active", el.dataset.doc === doc));
  renderCharts(doc);
}

function renderPages() {
  const $m = document.getElementById("main");
  $m.innerHTML = "";
  VICE_DOCTORS.forEach((doc,i) => {
    const page = document.createElement("div");
    page.className = "doc-page" + (i===0?" active":"");
    page.dataset.doc = doc;
    page.style.setProperty("--doc-color", DOC_COLORS[doc] || DOC_COLORS._default);
    page.innerHTML = renderPageHTML(doc);
    $m.appendChild(page);
    wireUp(doc);
    renderCharts(doc);
  });
}

function renderPageHTML(doc) {
  const months = METRICS.months;
  const rows = METRICS.by_doc[doc] || [];
  const curIdx = rows.length - 1;
  const cur = rows[curIdx] || null;
  const prev = curIdx > 0 ? rows[curIdx-1] : null;
  const notes = (STATE.notes||{})[doc] || [];
  const projects = (STATE.projects||{})[doc] || [];

  return `
    <section class="section">
      <h2>📊 객관 지표 <span class="badge">${months[curIdx]?monthLabel(months[curIdx]):"이번 달"}</span></h2>
      ${cur ? renderKPIs(cur, prev) : '<div class="meta">데이터 없음</div>'}
      <div class="chart-row">
        <div class="chart-box"><div class="title">월별 매출 추이 (만원)</div><canvas id="ch-rev-${doc}"></canvas></div>
        <div class="chart-box"><div class="title">월별 초진·재초진</div><canvas id="ch-first-${doc}"></canvas></div>
        <div class="chart-box"><div class="title">월별 재진율·삼진율 (%)</div><canvas id="ch-ret-${doc}"></canvas></div>
        <div class="chart-box"><div class="title">월별 건보추나 (건)</div><canvas id="ch-chuna-${doc}"></canvas></div>
      </div>
    </section>

    <section class="section">
      <h2>🗓️ 면담 회차 <span class="badge">${notes.length}회</span></h2>
      <div class="meeting-bar">
        <select id="meetSel-${doc}">
          ${notes.map((m,i)=>`<option value="${i}">${m.date} ${m.done?"✅":"📝"}</option>`).join("")}
        </select>
      </div>
      <div id="meetBody-${doc}"></div>
    </section>

    <section class="section">
      <h2>📌 진행 프로젝트 <span class="badge">${projects.length}건</span></h2>
      ${projects.length === 0 ? '<div class="meta">등록된 프로젝트 없음.</div>' : `
        <table class="proj-table">
          <thead><tr><th>프로젝트</th><th>우선순위</th><th>상태</th><th>기분</th><th>메모</th></tr></thead>
          <tbody>
          ${projects.map(p => `
            <tr>
              <td>${escapeHtml(p.name||"-")}</td>
              <td><span class="pill ${(p.priority||"").toLowerCase()}">${escapeHtml(p.priority||"-")}</span></td>
              <td><span class="pill ${pillCls(p.status)}">${escapeHtml(p.status||"-")}</span></td>
              <td>${escapeHtml(p.mood||"-")}</td>
              <td>${escapeHtml(p.memo||"")}</td>
            </tr>`).join("")}
          </tbody>
        </table>`}
    </section>
  `;
}

function pillCls(status) {
  if (status === "Done") return "done";
  if (status === "In Progress") return "prog";
  return "inbox";
}

function renderKPIs(cur, prev) {
  const items = [
    { label:"총 매출", value: fmt(cur.revenue.total) + "원",
      delta: deltaPct(cur.revenue.total, prev?.revenue?.total),
      sub: `건보 ${fmt(cur.revenue.건보)} · 자보 ${fmt(cur.revenue.자보)} · 비급 ${fmt(cur.revenue.비급여)}` },
    { label:"재진율", value: fmtPct(cur.retention.revisit_rate),
      delta: deltaPP(cur.retention.revisit_rate, prev?.retention?.revisit_rate),
      sub: `삼진율 ${fmtPct(cur.retention.third_rate)}` },
    { label:"초진 (TA+건보)", value: cur.first.초진합계 + "명",
      delta: deltaPct(cur.first.초진합계, prev?.first?.초진합계),
      sub: `TA ${cur.first.ta} · 건보 ${cur.first.kbo} · 재초진 ${cur.first.follow}` },
    { label:"건보추나", value: cur.chuna.건보 + "건",
      delta: deltaPct(cur.chuna.건보, prev?.chuna?.건보),
      sub: `TA추나 ${cur.chuna.TA}건` },
    { label:"출근일", value: cur.work_days + "일",
      delta: prev ? deltaRaw(cur.work_days, prev.work_days, "일") : {html:"-", cls:"flat"},
      sub: `진료 합계 ${cur.first.전체}회` },
  ];
  return `<div class="kpi-grid">` + items.map(it => `
    <div class="kpi">
      <div class="label">${it.label}</div>
      <div class="value">${it.value}</div>
      <div class="delta ${it.delta.cls}">${it.delta.html}</div>
      <div class="meta" style="font-size:11px; margin-top:4px;">${it.sub}</div>
    </div>`).join("") + `</div>`;
}

function wireUp(doc) {
  const notes = (STATE.notes||{})[doc] || [];
  const sel = document.getElementById(`meetSel-${doc}`);
  if (!sel) return;
  if (notes.length === 0) {
    document.getElementById(`meetBody-${doc}`).innerHTML =
      '<div class="meta">아직 면담 기록 없음.</div>';
    return;
  }
  const showMeeting = (idx) => {
    const m = notes[idx];
    const supList = (m.support||[]).map(s =>
      `<li>${s.reviewed?"✅":"⬜"} <strong style="color:var(--muted); margin:0 8px;">${escapeHtml(s.type||"")}</strong> ${escapeHtml(s.need||"")}</li>`
    ).join("");
    const past = notes.slice(0, idx).reverse();
    const historyHtml = past.length === 0 ? "" : `
      <div class="history" style="margin-top:18px;">
        <div class="agenda-label">과거 면담 (최신순)</div>
        ${past.map(n => `
          <details>
            <summary><strong>${n.date}</strong> ${n.done?"✅":"📝"}
              &nbsp;<span class="meta">(work ${(n.work||"").length}자 · career ${(n.career||"").length}자 · support ${(n.support||[]).length}건)</span>
            </summary>
            <div class="body">
              <span class="heading">💼 Work</span>
${escapeHtml(n.work||"(없음)")}
<span class="heading">🌱 Career</span>
${escapeHtml(n.career||"(없음)")}
<span class="heading">🤝 Support</span>
${(n.support||[]).map(s=>`&nbsp;&nbsp;[${s.reviewed?"✅":"⬜"} ${s.type}] ${escapeHtml(s.need||"")}`).join("\n") || "(없음)"}
            </div>
          </details>`).join("")}
      </div>`;
    document.getElementById(`meetBody-${doc}`).innerHTML = `
      <div style="font-size:13px; color:var(--muted); margin-bottom:14px;">
        ${m.date} · ${m.done ? "<span style='color:var(--good)'>완료</span>" : "<span style='color:var(--warn)'>예정</span>"}
      </div>
      <div class="agenda-grid">
        <div><div class="agenda-label">💼 Work Session</div>
          <div class="agenda-block">${escapeHtml(m.work||"(작성 안 됨)")}</div></div>
        <div><div class="agenda-label">🌱 Career Session</div>
          <div class="agenda-block">${escapeHtml(m.career||"(작성 안 됨)")}</div></div>
      </div>
      <div style="margin-top:14px;">
        <div class="agenda-label">🤝 Support 필요</div>
        ${supList ? `<ul class="item-list">${supList}</ul>` : '<div class="meta">없음</div>'}
      </div>
      ${historyHtml}
    `;
  };
  sel.value = notes.length - 1;
  showMeeting(notes.length - 1);
  sel.addEventListener("change", e => showMeeting(parseInt(e.target.value)));
}

function destroyIf(key) { if (charts[key]) { charts[key].destroy(); delete charts[key]; } }

function renderCharts(doc) {
  const rows = METRICS.by_doc[doc] || [];
  const labels = rows.map(r => monthLabel(r.month));
  const color = DOC_COLORS[doc] || DOC_COLORS._default;
  const baseOpts = {
    responsive:true, maintainAspectRatio:false,
    plugins:{ legend:{ labels:{ color:"#cbd5e1", font:{size:11} } } },
    scales:{
      x:{ ticks:{ color:"#94a3b8", font:{size:10} }, grid:{color:"#1e293b"} },
      y:{ ticks:{ color:"#94a3b8", font:{size:10} }, grid:{color:"#1e293b"}, beginAtZero:true },
    },
  };
  destroyIf(`rev-${doc}`);
  charts[`rev-${doc}`] = new Chart(document.getElementById(`ch-rev-${doc}`), {
    type:"bar",
    data:{ labels, datasets:[
      { label:"건보", data: rows.map(r=>Math.round(r.revenue.건보/10000)), backgroundColor: color+"99" },
      { label:"자보", data: rows.map(r=>Math.round(r.revenue.자보/10000)), backgroundColor: color+"66" },
      { label:"비급여", data: rows.map(r=>Math.round(r.revenue.비급여/10000)), backgroundColor: color+"33" },
    ]},
    options:{ ...baseOpts, scales:{ ...baseOpts.scales,
      x:{...baseOpts.scales.x, stacked:true}, y:{...baseOpts.scales.y, stacked:true} } },
  });
  destroyIf(`first-${doc}`);
  charts[`first-${doc}`] = new Chart(document.getElementById(`ch-first-${doc}`), {
    type:"bar",
    data:{ labels, datasets:[
      { label:"TA초진", data: rows.map(r=>r.first.ta), backgroundColor: color },
      { label:"건보초진", data: rows.map(r=>r.first.kbo), backgroundColor: color+"99" },
      { label:"재초진", data: rows.map(r=>r.first.follow), backgroundColor: color+"55" },
    ]}, options: baseOpts,
  });
  destroyIf(`ret-${doc}`);
  charts[`ret-${doc}`] = new Chart(document.getElementById(`ch-ret-${doc}`), {
    type:"line",
    data:{ labels, datasets:[
      { label:"재진율", data: rows.map(r=>r.retention.revisit_rate), borderColor:color, backgroundColor:color+"33", tension:.3, fill:false },
      { label:"삼진율", data: rows.map(r=>r.retention.third_rate), borderColor:"#94a3b8", borderDash:[4,4], tension:.3, fill:false },
    ]}, options:{ ...baseOpts, scales:{ ...baseOpts.scales, y:{...baseOpts.scales.y, max:100} } },
  });
  destroyIf(`chuna-${doc}`);
  charts[`chuna-${doc}`] = new Chart(document.getElementById(`ch-chuna-${doc}`), {
    type:"bar",
    data:{ labels, datasets:[
      { label:"건보추나", data: rows.map(r=>r.chuna.건보), backgroundColor: color },
      { label:"TA추나",   data: rows.map(r=>r.chuna.TA),   backgroundColor: color+"55" },
    ]}, options: baseOpts,
  });
}
</script>
</body>
</html>
"""


def build_public_html():
    return PUBLIC_TEMPLATE


def encrypt_payload(payload: dict, password: str) -> dict:
    """payload(dict) 를 비번으로 AES-256-GCM 암호화. 브라우저 SubtleCrypto 가
    그대로 복호화할 수 있도록 PBKDF2(SHA-256, iter=200k) → AES-GCM 12-byte IV
    포맷으로 반환."""
    salt = secrets.token_bytes(16)
    iv   = secrets.token_bytes(12)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                     iterations=PBKDF2_ITER)
    key = kdf.derive(password.encode("utf-8"))
    aes = AESGCM(key)
    plaintext = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ct_and_tag = aes.encrypt(iv, plaintext, None)   # tag 가 마지막 16바이트
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
    """round-trip 검증용. 클라이언트 JS 와 동일한 알고리즘으로 복호화."""
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

    # 1) 로컬 편집용 — 평문 인라인
    local_html = build_html(metrics, state)
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
        print("       (로컬 편집만 사용한다면 그대로 둬도 됨. 외부 접근 활성화 절차는 README 참고)")
        return
    if len(password) < 8:
        print("[error] HASLLA_1ON1_PASSWORD 가 8자 미만입니다. 더 긴 비번을 사용하세요.")
        sys.exit(2)

    payload = {"metrics": metrics, "state": state, "vice_doctors": VICE_DOCTORS,
               "doc_colors": DOC_COLORS}
    enc = encrypt_payload(payload, password)

    # round-trip 검증 — 실수로 깨진 enc.json 을 publish 하지 않도록
    try:
        rt = decrypt_payload(enc, password)
        assert rt == payload, "round-trip mismatch"
    except Exception as e:
        print(f"[error] 암호화 자체 검증 실패: {e}")
        sys.exit(3)

    OUT_ENC.write_text(json.dumps(enc, ensure_ascii=False, indent=2), encoding="utf-8")
    public_html = build_public_html()
    OUT_PUBLIC.write_text(public_html, encoding="utf-8")
    print(f"[ok] {OUT_PUBLIC.name} + {OUT_ENC.name} 생성 — 비번 길이 {len(password)}자, "
          f"암호문 {len(enc['data'])}자")


if __name__ == "__main__":
    main()
