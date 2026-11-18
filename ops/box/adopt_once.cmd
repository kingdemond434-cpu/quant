@echo off
rem ONE RUN OF THE BOX'S OWN ADOPTER, DECIDED BY THE RELEASE'S OWN GUARD (see adopt_once.ps1).
rem Double-click as the box Administrator (or right-click, Run as administrator). It asks for the
rem release tag; it can also be passed as the only argument. Log: C:\ProgramData\QuantBox\logs\adopt_once_*.log
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0adopt_once.ps1" -Tag "%~1"
set RC=%ERRORLEVEL%
echo.
echo Finished with code %RC%. Full log: C:\ProgramData\QuantBox\logs\adopt_once_*.log
pause
exit /b %RC%
