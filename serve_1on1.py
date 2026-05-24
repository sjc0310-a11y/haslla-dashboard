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
RETRO_DOCTORS = ["노왕식", "이문환", "방민준", "김한중"]

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


RETRO_HTML = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>📝 주간 회고 작성</title>
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
<header id="pageHeader">
  <h1>📝 주간 회고 작성</h1>
  <a class="nav-link" href="/">← 1on1 면담으로</a>
  <span id="saveStatus" class="save-status">대기</span>
  <button id="manualDlBtn" style="display:none;">⬇ 백업 다운로드</button>
</header>
<script>
  // iframe 임베드 모드 — ?embedded=1 이면 header 숨기고 컴팩트하게
  if (new URLSearchParams(location.search).get("embedded") === "1") {
    document.getElementById("pageHeader").style.display = "none";
    document.body.style.background = "transparent";
  }
</script>
<main>
  <div class="controls">
    <label>주차 (월요일)
      <input type="date" id="weekInput">
    </label>
    <label>원장
      <select id="doctorSel"></select>
    </label>
    <span class="hint">한 원장 한 주에 1건. 같은 조합 다시 선택하면 그 회고가 열림.</span>
  </div>
  <div class="form">
    <div class="field good">
      <div class="field-label">잘한 점 <span class="badge">good</span></div>
      <textarea id="good" placeholder="• 이번 주 가장 잘 한 진료·운영·환자 케이스
• 본인이 자랑하고 싶은 시도"></textarea>
    </div>
    <div class="field bad">
      <div class="field-label">아쉬웠던 점 <span class="badge">bad</span></div>
      <textarea id="bad" placeholder="• 이번 주 아쉬웠던 점·놓친 부분
• 다시 한다면 다르게 했을 일"></textarea>
    </div>
    <div class="field plan">
      <div class="field-label">다음 주 실행 계획 <span class="badge">plan</span></div>
      <textarea id="plan" placeholder="• 다음 주 구체적 액션 1~3개
• 측정 가능한 목표 형태로"></textarea>
    </div>
  </div>

  <div class="past">
    <h2>📚 과거 회고 (선택된 원장 · 최신순)</h2>
    <div id="pastList"></div>
  </div>
</main>

<script>
const DOCTORS = __RETRO_DOCTORS_JSON__;
const LS_KEY = "haslla_retro_backup";
let ALL = [];     // 전체 retro 배열
let DIRTY = false;
let SAVE_TIMER = null;

const $week   = document.getElementById("weekInput");
const $doc    = document.getElementById("doctorSel");
const $good   = document.getElementById("good");
const $bad    = document.getElementById("bad");
const $plan   = document.getElementById("plan");
const $status = document.getElementById("saveStatus");
const $past   = document.getElementById("pastList");
const $dlBtn  = document.getElementById("manualDlBtn");

// 원장 셀렉터 채우기
DOCTORS.forEach(d => {
  const opt = document.createElement("option");
  opt.value = d; opt.textContent = d;
  $doc.appendChild(opt);
});

// 이번 주 월요일을 default 로
function thisMonday() {
  const t = new Date();
  const day = t.getDay() || 7;  // Sun=0 → 7
  t.setDate(t.getDate() - (day - 1));
  return t.toISOString().slice(0, 10);
}
$week.value = thisMonday();

function key(week, doc) { return `${week}__${doc}`; }
function findEntry(week, doc) { return ALL.find(r => r.week_label === week && r.doctor === doc); }

function loadCurrent() {
  const e = findEntry($week.value, $doc.value);
  $good.value = e?.good || "";
  $bad.value  = e?.bad  || "";
  $plan.value = e?.plan || "";
  renderPast();
}

function renderPast() {
  const list = ALL.filter(r => r.doctor === $doc.value)
                  .sort((a, b) => (b.week_label || "").localeCompare(a.week_label || ""));
  if (list.length === 0) {
    $past.innerHTML = '<div class="meta">아직 회고 없음.</div>';
    return;
  }
  $past.innerHTML = list.map(r => `
    <details ${r.week_label === $week.value ? "open" : ""}>
      <summary><strong>${r.week_label}</strong> · ${r.doctor}
        <span class="meta">(good ${(r.good||"").length}자 · bad ${(r.bad||"").length}자 · plan ${(r.plan||"").length}자)</span>
      </summary>
      <div class="body">
        <span class="heading">잘한 점</span><p>${esc(r.good || "(없음)")}</p>
        <span class="heading">아쉬웠던 점</span><p>${esc(r.bad || "(없음)")}</p>
        <span class="heading">다음 주 실행 계획</span><p>${esc(r.plan || "(없음)")}</p>
      </div>
    </details>
  `).join("");
}
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"})[c]);
}

function markDirty() {
  DIRTY = true;
  $status.textContent = "저장 중…";
  $status.className = "save-status dirty";
  clearTimeout(SAVE_TIMER);
  SAVE_TIMER = setTimeout(doSave, 600);
}

async function doSave() {
  // 현재 입력값으로 ALL 갱신
  const w = $week.value, d = $doc.value;
  if (!w || !d) return;
  let e = findEntry(w, d);
  if (!e) {
    e = { week_label: w, doctor: d, good: "", bad: "", plan: "", page_url: "" };
    ALL.push(e);
  }
  e.good = $good.value;
  e.bad  = $bad.value;
  e.plan = $plan.value;
  // 빈 entry 는 정리
  ALL = ALL.filter(r => (r.good || r.bad || r.plan));
  // POST
  try {
    const res = await fetch("/retro/save", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify(ALL),
    });
    if (!res.ok) throw new Error(res.status);
    DIRTY = false;
    try { localStorage.removeItem(LS_KEY); } catch(_) {}
    $dlBtn.style.display = "none";
    const t = new Date();
    $status.textContent = `저장됨 ${String(t.getHours()).padStart(2,"0")}:${String(t.getMinutes()).padStart(2,"0")}:${String(t.getSeconds()).padStart(2,"0")}`;
    $status.className = "save-status ok";
    renderPast();
  } catch(err) {
    try { localStorage.setItem(LS_KEY, JSON.stringify({state: ALL, ts: Date.now()})); } catch(_) {}
    $status.textContent = "⚠ 오프라인 — 브라우저에 백업됨";
    $status.className = "save-status err";
    $dlBtn.style.display = "inline-block";
  }
}

function manualDownload() {
  const blob = new Blob([JSON.stringify(ALL, null, 2)], {type:"application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `retro_backup_${new Date().toISOString().slice(0,10)}.json`;
  a.click();
}

window.addEventListener("beforeunload", e => {
  if (DIRTY) { e.preventDefault(); e.returnValue = ""; }
});

[$week, $doc].forEach(el => el.addEventListener("change", loadCurrent));
[$good, $bad, $plan].forEach(el => el.addEventListener("input", markDirty));
$dlBtn.addEventListener("click", manualDownload);

(async () => {
  try {
    const r = await fetch("/retro/data", {cache:"no-store"});
    ALL = r.ok ? await r.json() : [];
  } catch(e) { ALL = []; }
  // LocalStorage 백업 우선 적용
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (raw) {
      const b = JSON.parse(raw);
      const ago = Math.round((Date.now() - b.ts) / 60000);
      if (confirm(`브라우저에 저장 실패한 회고 백업이 있습니다 (${ago}분 전).\\n복구할까요?`)) {
        ALL = b.state || ALL;
        markDirty();
      } else {
        localStorage.removeItem(LS_KEY);
      }
    }
  } catch(_) {}
  loadCurrent();
})();
</script>
</body>
</html>
""".replace("__RETRO_DOCTORS_JSON__", json.dumps(RETRO_DOCTORS, ensure_ascii=False))


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
