@echo off
rem THE BOX GIT FORGE, ONCE (see install_box_forge.ps1). Right-click, Run as administrator.
rem Log: C:\ProgramData\QuantBox\logs\install_box_forge_*.log
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_box_forge.ps1"
set RC=%ERRORLEVEL%
echo.
echo Finished with code %RC%. Full log: C:\ProgramData\QuantBox\logs\install_box_forge_*.log
pause
exit /b %RC%
