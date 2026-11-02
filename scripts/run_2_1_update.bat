@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
cd /d C:\Users\Admin\workspace\mkt_dashboard
echo [%date% %time%] 2.1 유입현황 업데이트 시작 >> logs\update_2_1.log
python -u scripts\update_2_1_channels.py --apply >> logs\update_2_1.log 2>&1
set RESULT=%errorlevel%
REM 시트 갱신 직후 대시보드용 BigQuery 테이블 갱신
python -u scripts\export_inflow_to_bq.py >> logs\update_2_1.log 2>&1
if not %errorlevel%==0 set RESULT=1
echo [%date% %time%] 2.1 유입현황 업데이트 종료 (exit %RESULT%) >> logs\update_2_1.log
if %RESULT%==0 (set SYNC_STATUS=success) else (set SYNC_STATUS=failure)
python scripts\notify_email.py --title "2.1 유입현황 업데이트 (PC)" --status %SYNC_STATUS% --detail "로그 파일: C:\Users\Admin\workspace\mkt_dashboard\logs\update_2_1.log" >> logs\update_2_1.log 2>&1
