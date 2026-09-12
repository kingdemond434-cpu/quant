$ErrorActionPreference = "Stop"
schtasks /create /tn MT5-IntelShip /tr "powershell -ExecutionPolicy Bypass -File C:\opt\quant\desks\mt5\scripts\intel_ship_adopt.ps1" /sc HOURLY /mo 1 /ru SYSTEM /rl HIGHEST /f
schtasks /query /tn MT5-IntelShip /v /fo LIST | Select-String "Schedule Type|Repeat: Every|Next Run|Last Result"