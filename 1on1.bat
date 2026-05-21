@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [1on1] 로컬 서버 시작 중... (브라우저가 자동으로 열립니다)
python serve_1on1.py
