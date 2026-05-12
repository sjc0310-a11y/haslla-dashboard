@echo off
cd /d "C:\Users\하슬라한의원\한의원지표"
echo %date% %time% 시작 >> update_log.txt
python read_chuna.py >> update_log.txt 2>&1
python read_okchart.py >> update_log.txt 2>&1
python read_retention.py >> update_log.txt 2>&1
python read_retro_from_notion.py >> update_log.txt 2>&1
python generate_dashboard.py >> update_log.txt 2>&1
echo %date% %time% 완료 >> update_log.txt
