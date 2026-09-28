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

rem Keep PowerShell in its own file.  Escaped pipes in the old multiline `-Command` reached
rem PowerShell as literal `^|`, failed to parse, and the fallback launched another terminal every
rem ten minutes.  The script fails closed if duplicate cleanup fails; it never answers an error by
rem spawning one more process.
powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "C:\opt\quant\ops\ensure_terminal.ps1"
exit /b %ERRORLEVEL%
