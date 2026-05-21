# -*- coding: utf-8 -*-
"""1on1 대시보드 로컬 서버.

기능
- GET /            → 매번 generate_1on1.py 를 다시 호출해 최신 객관 지표가
                     반영된 1on1.html 을 반환한다.
- POST /save       → 본문(JSON)을 data/1on1.json 에 그대로 덮어쓴다.
                     덮어쓰기 직전 .bak 백업을 한 번 떠둔다.
- 127.0.0.1 에서만 listen. 외부 접근 차단.
- 한의원 PC에서 1on1.bat 더블클릭 → 자동으로 브라우저 열림.
"""
from __future__ import annotations

import json
import shutil
import sys
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Windows 한글 콘솔 호환 (em-dash 등)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT      = Path(__file__).resolve().parent
DATA_DIR  = ROOT / "data"
DATA_JSON = DATA_DIR / "1on1.json"
OUT_HTML  = ROOT / "1on1_local.html"   # generate_1on1.py 가 만든 로컬 편집용

HOST = "127.0.0.1"
PORT = 7711


def rebuild():
    """generate_1on1.py 를 별도 프로세스 부담 없이 같은 인터프리터에서 실행."""
    import importlib
    sys.path.insert(0, str(ROOT))
    if "generate_1on1" in sys.modules:
        importlib.reload(sys.modules["generate_1on1"])
    else:
        import generate_1on1  # noqa: F401
    sys.modules["generate_1on1"].main()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # 콘솔을 너무 시끄럽게 하지 않음
        sys.stderr.write(f"[{datetime.now():%H:%M:%S}] {fmt%args}\n")

    def do_GET(self):
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
        elif self.path == "/health":
            self._serve_bytes(b"ok", "text/plain; charset=utf-8")
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path != "/save":
            self.send_response(404); self.end_headers(); return
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
    import socket, time
    for _ in range(40):  # 최대 ~4초
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
            "doctors": [],   # generate_1on1.py 가 VICE_DOCTORS 기준으로 채움
            "notes": {},
            "projects": {},
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    httpd = HTTPServer((HOST, PORT), Handler)
    threading.Thread(target=open_browser_when_ready, daemon=True).start()
    print(f"[1on1] http://{HOST}:{PORT}/ — Ctrl+C 로 종료")
    print(f"[1on1] 데이터 파일: {DATA_JSON}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[1on1] 종료")


if __name__ == "__main__":
    main()
