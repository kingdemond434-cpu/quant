@echo off
rem ===================================================================================
rem ENSURE exactly one MT5 terminal. Do not launch a second one.
rem
rem MT5-TerminalBoot ran `terminal64.exe` unconditionally on an HOURLY trigger, so every hour it
rem started another terminal against the same data directory. Measured 2026-09-11 23:39: two
rem terminal64 processes (pid 5392 and 5592), both "responding", and the gateway unable to reach
rem either --
rem
rem     mt5 initialize failed: (-10005, 'IPC timeout')
rem
rem repeating every two minutes from 21:31. The desk was not trading and every task result read
rem 0, because the task DID start a process; it just started the wrong one. The organ contract
rem caught it on its first run: gateway_state.json 84 minutes old against a 10 minute contract.
rem
rem An "ensure" that is not idempotent is not an ensure, it is a spawner.
rem ===================================================================================

set "EXE=C:\Program Files\Fusion Markets MetaTrader 5\terminal64.exe"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-TerminalBoot.log"

rem tasklist is the check the launcher never made.
tasklist /FI "IMAGENAME eq terminal64.exe" 2>nul | find /I "terminal64.exe" >nul
if not errorlevel 1 (
    echo %DATE% %TIME% terminal already running; not launching a second>>"%LOG%"
    exit /b 0
)

echo %DATE% %TIME% no terminal running; launching one>>"%LOG%"
start "" "%EXE%"
exit /b 0
