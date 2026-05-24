@echo off
chcp 65001 >nul
cd /d "C:\Users\하슬라한의원\한의원지표"
echo. >> update_log.txt
echo ============================================== >> update_log.txt
echo %date% %time% 시작 >> update_log.txt
python read_chuna.py >> update_log.txt 2>&1
python read_okchart.py >> update_log.txt 2>&1
python read_retention.py >> update_log.txt 2>&1
REM 노션 회고 인입은 2026-05-22 부로 비활성 — 회고는 https://1on1.haslla-admin.com/retro 에서 직접 작성
REM python read_retro_from_notion.py >> update_log.txt 2>&1
REM 1on1 노션 인입은 2026-05-22 부로 비활성 — 외부 편집은 Cloudflare Tunnel 통해 직접
REM python read_1on1_from_notion.py >> update_log.txt 2>&1
python generate_dashboard.py >> update_log.txt 2>&1
python generate_1on1.py >> update_log.txt 2>&1

REM ── 자동 commit + push (index.html / 1on1 공개 빌드) ──
git add index.html >> update_log.txt 2>&1
if exist 1on1.html     git add 1on1.html     >> update_log.txt 2>&1
if exist 1on1.enc.json git add 1on1.enc.json >> update_log.txt 2>&1
git diff --staged --quiet
if errorlevel 1 (
    git commit -m "Auto-update %date% %time%" >> update_log.txt 2>&1
    git push origin main >> update_log.txt 2>&1
    echo %date% %time% push 완료 >> update_log.txt
) else (
    echo %date% %time% 변경 없음, push 생략 >> update_log.txt
)
echo %date% %time% 종료 >> update_log.txt
