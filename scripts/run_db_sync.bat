@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
cd /d C:\Users\Admin\workspace\mkt_dashboard
echo [%date% %time%] DB 추출 시작 >> logs\db_sync.log
python scripts\sync_applicants_from_db.py --apply >> logs\db_sync.log 2>&1
echo [%date% %time%] DB 추출 종료 >> logs\db_sync.log
