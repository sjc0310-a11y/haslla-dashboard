@echo off
chcp 65001 >nul
cd /d "C:\Users\하슬라한의원\한의원지표"
echo. >> update_log.txt
echo ============================================== >> update_log.txt
echo %date% %time% 시작 >> update_log.txt
python read_chuna.py >> update_log.txt 2>&1
python read_okchart.py >> update_log.txt 2>&1
python read_retention.py >> update_log.txt 2>&1
python read_retro_from_notion.py >> update_log.txt 2>&1
python generate_dashboard.py >> update_log.txt 2>&1

REM ── 자동 commit + push (변경된 index.html이 있을 때만) ──
git add index.html >> update_log.txt 2>&1
git diff --staged --quiet
if errorlevel 1 (
    git commit -m "Auto-update %date% %time%" >> update_log.txt 2>&1
    git push origin main >> update_log.txt 2>&1
    echo %date% %time% push 완료 >> update_log.txt
) else (
    echo %date% %time% 변경 없음, push 생략 >> update_log.txt
)
echo %date% %time% 종료 >> update_log.txt
