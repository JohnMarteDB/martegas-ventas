@echo off
REM ============================================================
REM  MarteGas - nightly sales update
REM  Parses new reports, rebuilds the dashboard, and publishes.
REM  Run by Windows Task Scheduler (see setup_task.ps1) or by
REM  double-clicking this file to refresh manually.
REM ============================================================
cd /d "%~dp0.."
py -u src\update.py
echo.
echo Done. See data\update.log for details.
REM Pause only when run interactively (double-click), not from Task Scheduler.
if "%1"=="" if "%SESSIONNAME%"=="Console" pause
