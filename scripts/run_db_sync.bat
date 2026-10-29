@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
cd /d C:\Users\Admin\workspace\mkt_dashboard
echo [%date% %time%] DB 추출 시작 >> logs\db_sync.log
python scripts\sync_applicants_from_db.py --apply >> logs\db_sync.log 2>&1
set RESULT=%errorlevel%
REM DB 추출 직후 과정별 시트에 유입 정보 기록 (GitHub 예약 대신 로컬에서 실행)
echo [%date% %time%] 시트 기록 시작 >> logs\db_sync.log
python scripts\sync_ga_channels.py --apply >> logs\db_sync.log 2>&1
if not %errorlevel%==0 set RESULT=1
echo [%date% %time%] DB 추출 종료 (exit %RESULT%) >> logs\db_sync.log
if %RESULT%==0 (set SYNC_STATUS=success) else (set SYNC_STATUS=failure)
python scripts\notify_slack.py --title "DB 추출 (PC)" --status %SYNC_STATUS% --detail "로그 파일: C:\Users\Admin\workspace\mkt_dashboard\logs\db_sync.log" >> logs\db_sync.log 2>&1
