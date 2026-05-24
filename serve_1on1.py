# -*- coding: utf-8 -*-
"""1on1 대시보드 로컬 서버.

기능
- GET /            → 매번 generate_1on1.py 를 다시 호출해 최신 객관 지표가
                     반영된 1on1.html 을 반환한다.
- POST /save       → 본문(JSON)을 data/1on1.json 에 그대로 덮어쓴다.
                     덮어쓰기 직전 .bak 백업을 한 번 떠둔다.
- 127.0.0.1 에서 listen. Cloudflare Tunnel 이 외부 트래픽을 여기로 forward.
- 한의원 PC에서 1on1.bat 더블클릭 → 자동으로 브라우저 열림.

공유 비번 인증
- 환경변수 HASLLA_1ON1_PASSWORD 의 값으로 인증.
- 첫 방문은 /login → 비번 입력 → cookie 발급 (1년 만료, HttpOnly + Secure 옵션).
- 이후 모든 요청은 cookie 검증 통과 시에만 처리.
- 한의원 PC localhost 접속은 인증 우회 (편집 편의).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import sys
import threading
import time
import webbrowser
from datetime import datetime
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# pythonw.exe 실행 시 stdout/stderr 가 None — print 호출 시 ValueError 방지
import io as _io
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8") if hasattr(os, "devnull") else _io.StringIO()
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8") if hasattr(os, "devnull") else _io.StringIO()

# Windows 한글 콘솔 호환
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT      = Path(__file__).resolve().parent
DATA_DIR  = ROOT / "data"
DATA_JSON = DATA_DIR / "1on1.json"
RETRO_JSON = DATA_DIR / "retro.json"        # 주간 회고 (이전 노션 동기화 → 이제 대시보드 직접 편집)
OUT_HTML  = ROOT / "1on1_local.html"

# 회고 대상 원장 — 한 곳에서 관리. 추후 변경 시 generate_dashboard.py 의 ACTIVE_DOCTORS 와 일치시키면 됨
RETRO_DOCTORS = ["이문환", "방민준", "김한중"]

# 외부 경영 대시보드 URL (GitHub Pages)
DASHBOARD_URL = "https://sjc0310-a11y.github.io/haslla-dashboard/"

HOST = "127.0.0.1"
PORT = 7711

COOKIE_NAME = "haslla_1on1_auth"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365   # 1년

sys.path.insert(0, str(ROOT))
import generate_1on1  # noqa: E402

def rebuild():
    generate_1on1.main()


def _get_password() -> str:
    pw = os.environ.get("HASLLA_1ON1_PASSWORD", "").strip()
    return pw


def _expected_cookie() -> str:
    """비번에서 deterministic cookie 값 유도. 비번 변경되면 자동 무효."""
    pw = _get_password()
    if not pw:
        return ""
    # HMAC(pw, "verified") — 비번 자체가 secret 이라 별도 secret 불필요
    return hmac.new(pw.encode("utf-8"), b"verified", hashlib.sha256).hexdigest()


HOME_HTML = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>🏥 하슬라한의원 대시보드 허브</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<style>
  :root {
    --bg:#0f172a; --panel:#1e293b; --panel2:#273449; --border:#334155;
    --text:#e2e8f0; --muted:#94a3b8; --accent:#38bdf8;
  }
  * { box-sizing:border-box; }
  body { margin:0; font-family:'Pretendard','Apple SD Gothic Neo',sans-serif;
         background:var(--bg); color:var(--text);
         min-height:100vh; display:flex; flex-direction:column; }
  header { padding:24px 24px 12px; }
  header h1 { margin:0; font-size:24px; font-weight:700; }
  header .sub { color:var(--muted); font-size:13px; margin-top:6px; }
  main { flex:1; padding:20px 24px 40px; max-width:1100px; width:100%; margin:0 auto; }

  .doctor-chips { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:24px;
                   padding:14px 16px; background:var(--panel); border:1px solid var(--border);
                   border-radius:12px; align-items:center; }
  .doctor-chips .label { font-size:13px; color:var(--muted); margin-right:6px; }
  .chip { background:var(--panel2); color:var(--muted); border:1px solid var(--border);
          padding:8px 18px; border-radius:18px; font-size:14px; cursor:pointer;
          font-weight:500; transition:all .15s; }
  .chip:hover { color:var(--text); border-color:var(--accent); }
  .chip.active { background:var(--accent); color:#0f172a; border-color:var(--accent); font-weight:700; }

  .card-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:18px; }
  .card { background:var(--panel); border:1px solid var(--border); border-radius:14px;
          padding:24px 22px; text-decoration:none; color:var(--text);
          transition:all .2s; display:flex; flex-direction:column; gap:8px; }
  .card:hover { border-color:var(--accent); transform:translateY(-2px); }
  .card .icon { font-size:32px; }
  .card .title { font-size:18px; font-weight:700; }
  .card .desc { font-size:13px; color:var(--muted); line-height:1.5; }
  .card .badge-row { margin-top:auto; padding-top:12px; font-size:11px; color:var(--muted);
                      border-top:1px solid var(--border); display:flex; gap:8px; flex-wrap:wrap; }
  .card .badge { background:var(--panel2); padding:3px 8px; border-radius:6px; }
  .card.dash .icon { color:#3b82f6; }
  .card.one .icon { color:#10b981; }
  .card.retro .icon { color:#a78bfa; }

  footer { text-align:center; padding:18px; color:var(--muted); font-size:11px; }
</style>
</head>
<body>
<header>
  <h1>🏥 하슬라한의원 대시보드 허브</h1>
  <div class="sub">부원장 선택 후 원하는 화면으로 이동하세요. 선택한 원장은 모든 화면에 자동 적용됩니다.</div>
</header>
<main>
  <div class="doctor-chips" id="docChips">
    <span class="label">부원장 선택:</span>
  </div>

  <div class="card-grid">
    <a class="card dash" id="cardDash" href="https://sjc0310-a11y.github.io/haslla-dashboard/">
      <div class="icon">📊</div>
      <div class="title">경영 대시보드</div>
      <div class="desc">매출·재진율·추나·신환 등 객관 지표. 부원장 개인 뷰 또는 전체 뷰.</div>
      <div class="badge-row"><span class="badge">매주 일요일 자동 갱신</span><span class="badge">회고 인라인 편집</span></div>
    </a>

    <a class="card one" id="cardOne" href="/">
      <div class="icon">📋</div>
      <div class="title">1on1 면담</div>
      <div class="desc">월 1회 면담 노트·프로젝트 추적·Conversation Topic·Follow-up 자동 관리.</div>
      <div class="badge-row"><span class="badge">프로젝트 보드</span><span class="badge">6개월 history 모달</span></div>
    </a>

    <a class="card retro" id="cardRetro" href="/retro">
      <div class="icon">📝</div>
      <div class="title">주간 회고 일람</div>
      <div class="desc">전체 회고 검색·필터·통계. 작성은 경영 대시보드에서 박스 직접 클릭.</div>
      <div class="badge-row"><span class="badge">전문 검색</span><span class="badge">최근 4주 작성률</span></div>
    </a>
  </div>
</main>
<footer>cookie 인증 1년 · 같은 도메인 공유 · 한의원 PC가 켜져 있을 때 동작</footer>

<script>
const DOCTORS = __RETRO_DOCTORS_JSON__;
const LS_KEY = "haslla_selected_doctor";
let activeDoc = "전체";
try { activeDoc = localStorage.getItem(LS_KEY) || "전체"; } catch(_) {}
// URL 쿼리에서 doctor= 있으면 우선
const qDoc = new URLSearchParams(location.search).get("doctor");
if (qDoc) activeDoc = qDoc;

const $chips = document.getElementById("docChips");
function renderChips() {
  // "전체" + 모든 부원장
  const labels = ["전체"].concat(DOCTORS);
  $chips.querySelectorAll(".chip").forEach(n => n.remove());
  labels.forEach(name => {
    const b = document.createElement("button");
    b.className = "chip" + (name === activeDoc ? " active" : "");
    b.textContent = name;
    b.addEventListener("click", () => {
      activeDoc = name;
      try { localStorage.setItem(LS_KEY, name); } catch(_) {}
      renderChips();
      updateLinks();
    });
    $chips.appendChild(b);
  });
}
function updateLinks() {
  const param = activeDoc === "전체" ? "" : "?doctor=" + encodeURIComponent(activeDoc);
  document.getElementById("cardDash").href  = "https://sjc0310-a11y.github.io/haslla-dashboard/" + param;
  document.getElementById("cardOne").href   = "/" + param;
  document.getElementById("cardRetro").href = "/retro" + param;
}
renderChips(); updateLinks();
</script>
</body>
</html>
""".replace("__RETRO_DOCTORS_JSON__", json.dumps(RETRO_DOCTORS, ensure_ascii=False))


# 공통 상단 nav — 모든 페이지 헤더에 들어가는 작은 HTML 조각
TOPNAV_HTML = """<nav style="background:rgba(15,23,42,0.85); border-bottom:1px solid #334155;
                         padding:8px 16px; display:flex; gap:14px; align-items:center;
                         font-size:13px; flex-wrap:wrap; backdrop-filter:blur(6px); z-index:100;
                         position:relative;">
  <a href="/home" style="text-decoration:none; color:#38bdf8; font-weight:700;">🏥 허브</a>
  <span style="color:#475569;">·</span>
  <a href="__DASHBOARD_URL__" style="text-decoration:none; color:#cbd5e1;" id="navDash">📊 경영</a>
  <a href="/" style="text-decoration:none; color:#cbd5e1;" id="navOne">📋 1on1</a>
  <a href="/retro" style="text-decoration:none; color:#cbd5e1;" id="navRetro">📝 회고</a>
  <span style="margin-left:auto; color:#475569; font-size:11px;" id="navDocBadge"></span>
</nav>
<script>
(function() {
  // ?doctor= 가 있으면 모든 nav 링크에 같이 전달
  const q = new URLSearchParams(location.search).get("doctor");
  if (q) {
    try { localStorage.setItem("haslla_selected_doctor", q); } catch(_) {}
    ["navDash","navOne","navRetro"].forEach(id => {
      const a = document.getElementById(id);
      if (a) { const sep = a.href.includes("?") ? "&" : "?"; a.href = a.href + sep + "doctor=" + encodeURIComponent(q); }
    });
    const b = document.getElementById("navDocBadge");
    if (b) b.textContent = "선택된 부원장: " + q;
  }
})();
</script>
""".replace("__DASHBOARD_URL__", DASHBOARD_URL)


RETRO_HTML = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>📚 주간 회고 일람</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<style>
  :root {
    --bg:#0f172a; --panel:#1e293b; --panel2:#273449; --border:#334155;
    --text:#e2e8f0; --muted:#94a3b8; --accent:#38bdf8;
    --good:#22c55e; --warn:#f59e0b; --bad:#ef4444;
  }
  * { box-sizing:border-box; }
  body { margin:0; font-family:'Pretendard','Apple SD Gothic Neo',sans-serif;
         background:var(--bg); color:var(--text); }
  header { padding:18px 24px; border-bottom:1px solid var(--border);
           display:flex; align-items:center; gap:16px; flex-wrap:wrap; }
  header h1 { margin:0; font-size:20px; font-weight:700; }
  .meta { color:var(--muted); font-size:13px; }
  .save-status { margin-left:auto; padding:6px 12px; border-radius:6px;
                 font-size:12px; background:var(--panel); color:var(--muted); }
  .save-status.ok { background:#064e3b; color:#86efac; }
  .save-status.err { background:#7f1d1d; color:#fecaca; }
  .save-status.dirty { background:#78350f; color:#fed7aa; }
  .nav-link { color:var(--accent); text-decoration:none; font-size:13px; }
  .nav-link:hover { text-decoration:underline; }
  main { padding:24px; max-width:1000px; margin:0 auto; }
  .controls { background:var(--panel); border:1px solid var(--border);
              border-radius:12px; padding:16px; margin-bottom:20px;
              display:flex; gap:12px; flex-wrap:wrap; align-items:center; }
  .controls label { display:flex; align-items:center; gap:6px;
                     font-size:13px; color:var(--muted); }
  .controls select, .controls input[type=date] {
    background:var(--panel2); color:var(--text); border:1px solid var(--border);
    padding:7px 10px; border-radius:6px; font-size:14px; }
  .hint { color:var(--muted); font-size:12px; margin-left:auto; }
  .form { background:var(--panel); border:1px solid var(--border);
          border-radius:12px; padding:20px; }
  .field { margin-bottom:18px; }
  .field-label { color:var(--muted); font-size:13px; margin-bottom:6px;
                  display:flex; justify-content:space-between; align-items:center; }
  .field-label .badge { font-size:11px; padding:2px 8px; border-radius:10px;
                         background:var(--panel2); color:var(--muted); }
  textarea { width:100%; min-height:120px; background:var(--panel2);
             color:var(--text); border:1px solid var(--border);
             border-radius:6px; padding:10px; font-size:14px;
             font-family:inherit; line-height:1.6; resize:vertical; }
  textarea:focus { outline:1px solid var(--accent); border-color:var(--accent); }
  .field.bad .badge { background:#7f1d1d; color:#fecaca; }
  .field.good .badge { background:#064e3b; color:#86efac; }
  .field.plan .badge { background:#1e3a8a; color:#bfdbfe; }
  .past { margin-top:30px; background:var(--panel); border:1px solid var(--border);
          border-radius:12px; padding:20px; }
  .past h2 { font-size:15px; margin:0 0 14px; padding-bottom:10px;
              border-bottom:1px solid var(--border); }
  .past details { border:1px solid var(--border); border-radius:6px;
                   padding:10px 12px; margin-bottom:6px; background:var(--panel2); font-size:13px; }
  .past summary { cursor:pointer; color:var(--muted); }
  .past summary strong { color:var(--text); }
  .past .body { margin-top:8px; }
  .past .body .heading { color:var(--accent); font-weight:600;
                           margin-top:10px; display:block; }
  .past .body p { white-space:pre-wrap; line-height:1.6; margin:4px 0 0; }
  #manualDlBtn { background:transparent; color:var(--accent);
                  border:1px dashed var(--border); padding:6px 12px;
                  border-radius:6px; cursor:pointer; font-size:12px; }
</style>
</head>
<body>
__TOPNAV__
<header id="pageHeader">
  <h1>📚 주간 회고 일람</h1>
  <span class="meta" style="margin-left:auto; font-size:12px;">작성·수정은 경영 대시보드 회고 박스 직접 클릭</span>
</header>
<script>
  // iframe 임베드 모드 — ?embedded=1 이면 header 숨기고 컴팩트하게
  if (new URLSearchParams(location.search).get("embedded") === "1") {
    document.getElementById("pageHeader").style.display = "none";
    document.body.style.background = "transparent";
  }
</script>
<style>
  /* 일람 추가 스타일 */
  .toolbar { background:var(--panel); border:1px solid var(--border);
              border-radius:12px; padding:14px 16px; margin-bottom:18px;
              display:flex; flex-wrap:wrap; gap:14px; align-items:center; }
  .doc-chips { display:flex; gap:6px; flex-wrap:wrap; }
  .chip { background:var(--panel2); color:var(--muted); border:1px solid var(--border);
          padding:6px 14px; border-radius:18px; font-size:13px; cursor:pointer;
          font-weight:500; transition:all .15s; }
  .chip:hover { color:var(--text); border-color:var(--accent); }
  .chip.active { background:var(--accent); color:#0f172a; border-color:var(--accent); font-weight:700; }
  .chip .count { font-size:11px; margin-left:4px; opacity:.7; }
  .search-input { background:var(--panel2); color:var(--text);
                   border:1px solid var(--border); padding:7px 12px;
                   border-radius:6px; font-size:14px; min-width:240px; flex:1; }
  .search-input:focus { outline:1px solid var(--accent); border-color:var(--accent); }
  .stats { font-size:12px; color:var(--muted); margin-left:auto; }
  .stats strong { color:var(--text); }

  .card-grid { display:grid; grid-template-columns:1fr; gap:14px; }
  @media (min-width:1100px) { .card-grid { grid-template-columns:1fr 1fr; } }
  .retro-card { background:var(--panel); border:1px solid var(--border);
                 border-radius:12px; padding:16px 18px; display:flex; flex-direction:column; gap:10px; }
  .retro-card:hover { border-color:var(--border2); }
  .card-header { display:flex; align-items:center; gap:10px;
                  padding-bottom:8px; border-bottom:1px solid var(--border);
                  font-size:13px; }
  .card-header .date { font-weight:700; color:var(--text); }
  .card-header .doctor { padding:2px 10px; border-radius:10px;
                          background:var(--panel2); color:var(--accent); font-weight:600; }
  .card-header .meta { color:var(--muted); margin-left:auto; font-size:11px; }
  .card-section { font-size:13px; line-height:1.6; }
  .card-section .head { font-size:11px; color:var(--muted); font-weight:600;
                          margin-bottom:4px; text-transform:uppercase; letter-spacing:0.5px; }
  .card-section.good .head { color:#86efac; }
  .card-section.bad  .head { color:#fca5a5; }
  .card-section.plan .head { color:#bfdbfe; }
  .card-section p { white-space:pre-wrap; margin:0; }
  .card-section .empty { color:var(--muted); font-style:italic; font-size:12px; }
  mark { background:#facc15; color:#0f172a; padding:0 2px; border-radius:2px; }
  .empty-state { text-align:center; padding:60px 20px; color:var(--muted);
                  font-size:14px; background:var(--panel); border:1px dashed var(--border);
                  border-radius:12px; }
</style>
<main>
  <div class="toolbar">
    <div class="doc-chips" id="docChips"></div>
    <input type="text" class="search-input" id="searchInput" placeholder="🔍 잘한 점·아쉬웠던 점·계획 본문 검색...">
    <div class="stats" id="statsBar">로딩 중…</div>
  </div>

  <div id="cardGrid" class="card-grid"></div>
</main>

<script>
const DOCTORS = __RETRO_DOCTORS_JSON__;
let ALL = [];               // 전체 retro 배열
let activeDoctor = "전체";  // chip 필터
let searchQ = "";
// URL ?doctor= 또는 localStorage 우선
(function() {
  const q = new URLSearchParams(location.search).get("doctor");
  let pref = q;
  if (!pref) { try { pref = localStorage.getItem("haslla_selected_doctor"); } catch(_) {} }
  if (pref && (pref === "전체" || DOCTORS.includes(pref))) activeDoctor = pref;
})();

const $chips  = document.getElementById("docChips");
const $search = document.getElementById("searchInput");
const $stats  = document.getElementById("statsBar");
const $grid   = document.getElementById("cardGrid");

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"})[c]);
}
function highlight(s, q) {
  if (!q) return esc(s);
  const re = new RegExp("(" + q.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\\\$&") + ")", "gi");
  return esc(s).replace(re, "<mark>$1</mark>");
}

function renderChips() {
  const labels = ["전체"].concat(DOCTORS);
  $chips.innerHTML = labels.map(name => {
    const n = name === "전체" ? ALL.length : ALL.filter(r => r.doctor === name).length;
    return `<button class="chip${name===activeDoctor?" active":""}" data-doc="${esc(name)}">${esc(name)}<span class="count">(${n})</span></button>`;
  }).join("");
  $chips.querySelectorAll(".chip").forEach(btn => {
    btn.addEventListener("click", () => {
      activeDoctor = btn.dataset.doc;
      renderChips(); renderCards();
    });
  });
}

function renderStats() {
  const docCount = DOCTORS.length;
  const total = ALL.length;
  // 최근 4주 작성률 — DOCTORS × 4주 = 기대값
  const last4 = lastNMondays(4);
  const expected = docCount * 4;
  const got = ALL.filter(r => last4.includes(r.week_label)).length;
  const pct = expected ? Math.round((got / expected) * 100) : 0;
  $stats.innerHTML = `전체 <strong>${total}</strong>건 · 최근 4주 작성률 <strong>${got}/${expected} (${pct}%)</strong>`;
}

function lastNMondays(n) {
  const out = [];
  const t = new Date();
  const day = t.getDay() || 7;
  t.setDate(t.getDate() - (day - 1));   // 이번 주 월요일
  for (let i=0; i<n; i++) {
    out.push(t.toISOString().slice(0,10));
    t.setDate(t.getDate() - 7);
  }
  return out;
}

function renderCards() {
  let list = ALL.slice();
  if (activeDoctor !== "전체") list = list.filter(r => r.doctor === activeDoctor);
  const q = searchQ.trim().toLowerCase();
  if (q) {
    list = list.filter(r =>
      (r.good||"").toLowerCase().includes(q) ||
      (r.bad ||"").toLowerCase().includes(q) ||
      (r.plan||"").toLowerCase().includes(q) ||
      (r.doctor||"").toLowerCase().includes(q));
  }
  list.sort((a,b) => (b.week_label||"").localeCompare(a.week_label||""));

  if (list.length === 0) {
    $grid.innerHTML = `<div class="empty-state">해당 조건의 회고가 없습니다.<br><span style="font-size:12px;">대시보드의 회고 영역에서 박스 클릭으로 직접 작성하세요.</span></div>`;
    return;
  }
  $grid.innerHTML = list.map(r => {
    const dateLabel = formatDate(r.week_label);
    return `
      <div class="retro-card">
        <div class="card-header">
          <span class="date">${esc(dateLabel)}</span>
          <span class="doctor">${esc(r.doctor||"-")}</span>
          <span class="meta">good ${(r.good||"").length}자 · bad ${(r.bad||"").length}자 · plan ${(r.plan||"").length}자</span>
        </div>
        <div class="card-section good">
          <div class="head">✅ 잘한 점</div>
          ${r.good ? `<p>${highlight(r.good, q)}</p>` : `<span class="empty">(비어있음)</span>`}
        </div>
        <div class="card-section bad">
          <div class="head">🔶 아쉬웠던 점</div>
          ${r.bad ? `<p>${highlight(r.bad, q)}</p>` : `<span class="empty">(비어있음)</span>`}
        </div>
        <div class="card-section plan">
          <div class="head">📌 다음 주 실행 계획</div>
          ${r.plan ? `<p>${highlight(r.plan, q)}</p>` : `<span class="empty">(비어있음)</span>`}
        </div>
      </div>`;
  }).join("");
}

function formatDate(weekLabel) {
  // weekLabel = "YYYY-MM-DD" (월요일)
  if (!weekLabel) return "(날짜 없음)";
  const d = new Date(weekLabel);
  if (isNaN(d)) return weekLabel;
  const end = new Date(d); end.setDate(end.getDate() + 6);
  const mm = d.getMonth()+1, dd = d.getDate(), em = end.getMonth()+1, ed = end.getDate();
  return `${d.getFullYear()}-${String(mm).padStart(2,"0")}-${String(dd).padStart(2,"0")} ~ ${String(em).padStart(2,"0")}-${String(ed).padStart(2,"0")}`;
}

$search.addEventListener("input", e => { searchQ = e.target.value; renderCards(); });

(async () => {
  try {
    const r = await fetch("/retro/data", {cache:"no-store"});
    ALL = r.ok ? await r.json() : [];
  } catch(e) { ALL = []; }
  renderChips(); renderStats(); renderCards();
})();
</script>
</body>
</html>
""".replace("__RETRO_DOCTORS_JSON__", json.dumps(RETRO_DOCTORS, ensure_ascii=False)) \
   .replace("__TOPNAV__", TOPNAV_HTML)


LOGIN_HTML = """<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8">
<title>🔒 1:1 면담</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<style>
  body { margin:0; font-family:'Pretendard','Apple SD Gothic Neo',sans-serif;
         background:#0f172a; color:#e2e8f0; display:flex; align-items:center;
         justify-content:center; min-height:100vh; }
  .box { text-align:center; max-width:380px; padding:20px; }
  h1 { font-size:24px; margin:0 0 6px; }
  .sub { color:#94a3b8; margin-bottom:24px; font-size:14px; }
  form { display:flex; gap:8px; }
  input { background:#1e293b; color:#e2e8f0; border:1px solid #334155;
          border-radius:6px; padding:10px 14px; font-size:15px;
          flex:1; min-width:0; }
  input:focus { outline:1px solid #38bdf8; border-color:#38bdf8; }
  button { background:#38bdf8; color:#0f172a; border:none;
           padding:10px 20px; border-radius:6px; font-weight:700;
           cursor:pointer; font-size:15px; }
  .err { color:#ef4444; margin-top:14px; min-height:18px; font-size:13px; }
  .hint { color:#94a3b8; font-size:12px; margin-top:24px; }
</style></head>
<body>
<div class="box">
  <h1>🔒 1:1 면담</h1>
  <div class="sub">비밀번호를 입력하세요</div>
  <form method="POST" action="/login" autocomplete="on">
    <input type="password" name="pw" autocomplete="current-password" placeholder="비밀번호" autofocus>
    <button type="submit">열기</button>
  </form>
  <div class="err">__ERR__</div>
  <div class="hint">한 번 입력하면 1년간 자동 인증됩니다.</div>
</div>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write(f"[{datetime.now():%H:%M:%S}] {fmt%args}\n")

    # ── 인증 ─────────────────────────────────────
    def _is_external(self) -> bool:
        """Cloudflare Tunnel 통과 요청이면 X-Forwarded-For 또는 CF-Connecting-IP 헤더가 옴.
        그 헤더 없으면 진짜 localhost 직접 접속."""
        return bool(
            self.headers.get("X-Forwarded-For")
            or self.headers.get("CF-Connecting-IP")
            or self.headers.get("Cf-Ray")
        )

    def _is_authed(self) -> bool:
        # 1) 진짜 localhost 직접 접속(한의원 PC에서 1on1.bat 실행)은 면제
        client_ip = self.client_address[0] if self.client_address else ""
        if client_ip in ("127.0.0.1", "::1") and not self._is_external():
            return True
        # 2) cookie 검증
        expected = _expected_cookie()
        if not expected:
            return True   # 비번 미설정 시 인증 자체 비활성 (개발용)
        raw = self.headers.get("Cookie", "")
        if not raw:
            return False
        try:
            jar = cookies.SimpleCookie(raw)
            got = jar[COOKIE_NAME].value if COOKIE_NAME in jar else ""
        except Exception:
            return False
        return hmac.compare_digest(got, expected)

    def _serve_login(self, err: str = ""):
        html = LOGIN_HTML.replace("__ERR__", err)
        # iframe 내부에서도 로그인 화면이 보이도록 frame-ancestors 허용
        self._serve_bytes(
            html.encode("utf-8"), "text/html; charset=utf-8",
            extra_headers=[
                ("Content-Security-Policy",
                 "frame-ancestors 'self' https://sjc0310-a11y.github.io https://*.github.io"),
            ],
        )

    def _set_auth_cookie(self):
        c = cookies.SimpleCookie()
        c[COOKIE_NAME] = _expected_cookie()
        c[COOKIE_NAME]["max-age"] = COOKIE_MAX_AGE
        c[COOKIE_NAME]["path"] = "/"
        c[COOKIE_NAME]["httponly"] = True
        # iframe(cross-site) 안에서도 cookie 전송되어야 하므로 None + Secure.
        # Cloudflare Tunnel 통과 시 HTTPS이라 Secure 만족. 한의원 PC localhost 직접 접속은
        # 인증 면제(localhost bypass)라 cookie 자체 불필요.
        c[COOKIE_NAME]["samesite"] = "None"
        c[COOKIE_NAME]["secure"] = True
        return c.output(header="").strip()

    def do_GET(self):
        if self.path == "/health":
            self._serve_bytes(b"ok", "text/plain; charset=utf-8")
            return
        if self.path == "/login":
            self._serve_login()
            return
        if not self._is_authed():
            # 로그인 페이지로 안내 (redirect 보다 직접 표시가 UX 좋음)
            self._serve_login()
            return
        if self.path in ("/", "/1on1.html", "/index"):
            try:
                rebuild()
            except Exception as e:
                self._serve_error(500, f"rebuild 실패: {e}")
                return
            self._serve_file(OUT_HTML, "text/html; charset=utf-8")
        elif self.path == "/raw.json":
            if DATA_JSON.exists():
                self._serve_file(DATA_JSON, "application/json; charset=utf-8")
            else:
                self._serve_bytes(b"{}", "application/json; charset=utf-8")
        elif self.path == "/home" or self.path.startswith("/home?"):
            self._serve_bytes(HOME_HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif self.path == "/retro" or self.path.startswith("/retro?"):
            # GitHub Pages index.html iframe 임베드 허용
            self._serve_bytes(
                RETRO_HTML.encode("utf-8"),
                "text/html; charset=utf-8",
                extra_headers=[
                    ("Content-Security-Policy",
                     "frame-ancestors 'self' https://sjc0310-a11y.github.io https://*.github.io"),
                ],
            )
        elif self.path == "/retro/data":
            if RETRO_JSON.exists():
                self._serve_file(RETRO_JSON, "application/json; charset=utf-8")
            else:
                self._serve_bytes(b"[]", "application/json; charset=utf-8")
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path == "/login":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8", errors="replace")
            ctype = (self.headers.get("Content-Type") or "").lower()
            # form url-encoded 와 JSON 둘 다 허용 — fetch는 JSON, form 제출은 url-encoded
            pw = ""
            if "application/json" in ctype:
                try:
                    pw = (json.loads(body) or {}).get("pw", "")
                except Exception:
                    pw = ""
            else:
                from urllib.parse import parse_qs
                qs = parse_qs(body)
                pw = (qs.get("pw") or [""])[0]
            expected_pw = _get_password()
            if not expected_pw:
                self._serve_error(503, "서버에 비번이 설정되지 않았습니다 (HASLLA_1ON1_PASSWORD)")
                return
            if hmac.compare_digest(pw, expected_pw):
                # 비번 맞음 — cookie 발급. form 제출이면 303 redirect, fetch면 200 JSON.
                if "application/json" in ctype:
                    body_out = b'{"ok":true}'
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(body_out)))
                    self.send_header("Set-Cookie", self._set_auth_cookie())
                    for k, v in self._cors_headers():
                        self.send_header(k, v)
                    self.end_headers()
                    self.wfile.write(body_out)
                else:
                    self.send_response(303)
                    self.send_header("Location", "/")
                    self.send_header("Set-Cookie", self._set_auth_cookie())
                    self.send_header("Content-Length", "0")
                    for k, v in self._cors_headers():
                        self.send_header(k, v)
                    self.end_headers()
                return
            # 비번 틀림 — 잠깐 sleep 으로 brute force 완화
            time.sleep(0.5)
            if "application/json" in ctype:
                body_out = b'{"ok":false,"error":"wrong_password"}'
                self.send_response(401)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body_out)))
                for k, v in self._cors_headers():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body_out)
            else:
                self._serve_login("비밀번호가 틀렸습니다.")
            return

        if self.path == "/save":
            # 1on1 저장
            if not self._is_authed():
                self._serve_error(401, "인증 필요")
                return
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
            except Exception as e:
                self._serve_error(400, f"JSON 파싱 실패: {e}"); return
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            if DATA_JSON.exists():
                shutil.copy2(DATA_JSON, DATA_JSON.with_suffix(".json.bak"))
            DATA_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            self._serve_bytes(b'{"ok":true}', "application/json; charset=utf-8")
            return

        if self.path == "/retro/save":
            # 주간 회고 저장 — 본문은 전체 retro 배열
            if not self._is_authed():
                self._serve_error(401, "인증 필요")
                return
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                if not isinstance(data, list):
                    raise ValueError("expected JSON array")
            except Exception as e:
                self._serve_error(400, f"JSON 파싱 실패: {e}"); return
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            if RETRO_JSON.exists():
                shutil.copy2(RETRO_JSON, RETRO_JSON.with_suffix(".json.bak"))
            RETRO_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            self._serve_bytes(b'{"ok":true}', "application/json; charset=utf-8")
            return

        self.send_response(404); self.end_headers()

    # ── 헬퍼 ───────────────────────────────────
    def _serve_file(self, path: Path, ctype: str):
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in self._cors_headers():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    # ── CORS — index.html(github.io)이 직접 fetch 호출하도록 허용 ──
    CORS_ALLOWED = {
        "https://sjc0310-a11y.github.io",
        "http://localhost",
        "http://127.0.0.1",
    }
    def _cors_headers(self):
        origin = self.headers.get("Origin", "")
        if origin in self.CORS_ALLOWED:
            return [
                ("Access-Control-Allow-Origin", origin),
                ("Access-Control-Allow-Credentials", "true"),
                ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
                ("Access-Control-Allow-Headers", "Content-Type"),
                ("Vary", "Origin"),
            ]
        return []

    def do_OPTIONS(self):
        """Preflight CORS — 모든 경로 일괄 허용"""
        self.send_response(204)
        for k, v in self._cors_headers():
            self.send_header(k, v)
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def _serve_bytes(self, data: bytes, ctype: str, extra_headers=None):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in self._cors_headers():
            self.send_header(k, v)
        for k, v in (extra_headers or []):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _serve_error(self, code: int, msg: str):
        body = msg.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for k, v in self._cors_headers():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)


def open_browser_when_ready():
    import socket
    for _ in range(40):
        try:
            with socket.create_connection((HOST, PORT), timeout=0.2):
                webbrowser.open(f"http://{HOST}:{PORT}/")
                return
        except OSError:
            time.sleep(0.1)


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_JSON.exists():
        DATA_JSON.write_text(json.dumps({
            "doctors": [], "notes": {}, "projects": {},
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    pw = _get_password()
    if not pw:
        print("[1on1] 경고 — HASLLA_1ON1_PASSWORD 환경변수 미설정. 인증 비활성!")
    else:
        print(f"[1on1] 공유 비번 {len(pw)}자 활성 — cookie 1년 만료")
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    threading.Thread(target=open_browser_when_ready, daemon=True).start()
    print(f"[1on1] http://{HOST}:{PORT}/ — Ctrl+C 로 종료")
    print(f"[1on1] 데이터 파일: {DATA_JSON}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[1on1] 종료")


if __name__ == "__main__":
    main()
