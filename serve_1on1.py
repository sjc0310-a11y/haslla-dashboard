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
OUT_HTML  = ROOT / "1on1_local.html"

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
        self._serve_bytes(html.encode("utf-8"), "text/html; charset=utf-8")

    def _set_auth_cookie(self):
        c = cookies.SimpleCookie()
        c[COOKIE_NAME] = _expected_cookie()
        c[COOKIE_NAME]["max-age"] = COOKIE_MAX_AGE
        c[COOKIE_NAME]["path"] = "/"
        c[COOKIE_NAME]["httponly"] = True
        c[COOKIE_NAME]["samesite"] = "Lax"
        # Secure: HTTPS 환경에서만 보내짐. Cloudflare Tunnel 통과 시 HTTPS, 로컬은 HTTP.
        # 로컬 사용을 위해 Secure 는 일부러 안 붙임 — Tunnel 통과 시에도 작동.
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
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path == "/login":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8", errors="replace")
            # form url-encoded 파싱
            from urllib.parse import parse_qs
            qs = parse_qs(body)
            pw = (qs.get("pw") or [""])[0]
            expected_pw = _get_password()
            if not expected_pw:
                self._serve_error(503, "서버에 비번이 설정되지 않았습니다 (HASLLA_1ON1_PASSWORD)")
                return
            if hmac.compare_digest(pw, expected_pw):
                # 비번 맞음 — cookie 발급 후 / 로 리다이렉트
                self.send_response(303)
                self.send_header("Location", "/")
                self.send_header("Set-Cookie", self._set_auth_cookie())
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            # 비번 틀림 — 잠깐 sleep 으로 brute force 완화
            time.sleep(0.5)
            self._serve_login("비밀번호가 틀렸습니다.")
            return

        if self.path != "/save":
            self.send_response(404); self.end_headers(); return
        # 저장 요청은 반드시 인증 필요
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

    # ── 헬퍼 ───────────────────────────────────
    def _serve_file(self, path: Path, ctype: str):
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _serve_bytes(self, data: bytes, ctype: str):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _serve_error(self, code: int, msg: str):
        body = msg.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
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
