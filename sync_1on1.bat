@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo. >> sync_1on1_log.txt
echo ============================================== >> sync_1on1_log.txt
echo %date% %time% sync start >> sync_1on1_log.txt
python read_1on1_from_notion.py >> sync_1on1_log.txt 2>&1
if errorlevel 1 ( echo %date% %time% notion fetch failed >> sync_1on1_log.txt & exit /b 1 )
python generate_1on1.py >> sync_1on1_log.txt 2>&1
if errorlevel 1 ( echo %date% %time% rebuild failed >> sync_1on1_log.txt & exit /b 2 )
git add 1on1.html 1on1.enc.json >> sync_1on1_log.txt 2>&1
git diff --staged --quiet
if errorlevel 1 (
    git commit -m "Sync 1on1 from Notion %date% %time%" >> sync_1on1_log.txt 2>&1
    git push origin main >> sync_1on1_log.txt 2>&1
    echo %date% %time% pushed >> sync_1on1_log.txt
) else (
    echo %date% %time% no-change >> sync_1on1_log.txt
)