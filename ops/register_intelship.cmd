@echo off
schtasks /Create /TN "MT5-IntelShip" /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\opt\quant\desks\mt5\scripts\intel_ship_adopt.ps1" /SC HOURLY /ST 23:55 /RU SYSTEM /RL HIGHEST /F
schtasks /Run /TN "MT5-IntelShip"
schtasks /Query /TN "MT5-IntelShip" /V /FO LIST