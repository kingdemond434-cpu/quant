@echo off
rem ============================================================================================
rem CheckDesk -- "is the desk actually running?", answered in plain English on the box itself.
rem
rem WHY THIS EXISTS. On 2026-09-05 the desk had been producing nothing for days and the only way
rem to find out why was to read artifacts from a container that cannot reach this machine. Every
rem diagnosis from there was an inference from a stale file, and two of them were wrong. The
rem machine knows the answer directly; nobody had written it down as a question it could be
rem asked. Double-click this file and it tells you.
rem
rem It CHANGES NOTHING. It starts nothing, stops nothing, and writes nothing outside the report
rem it prints. Safe to run at any time, including while the desk is trading.
rem ============================================================================================
setlocal
cd /d C:\opt\quant\desks\mt5 2>nul || (
  echo.
  echo   PROBLEM: C:\opt\quant\desks\mt5 does not exist on this machine.
  echo   The desk is not installed where every scheduled task expects it.
  echo.
  pause
  exit /b 1
)
echo.
echo ==================== DESK CHECK ====================
echo.
py -3 -u -W ignore scripts\check_desk_health.py
echo.
echo ====================================================
echo.
echo Copy everything above and send it to Claude.
echo.
pause
