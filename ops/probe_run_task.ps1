Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"
schtasks /query /tn MT5-IntelShip /v /fo LIST | Select-String "Start Time|Start Date|Next Run|Last Run|Repeat:"
echo "---RUN---"
schtasks /run /tn MT5-IntelShip
Start-Sleep -Seconds 25
echo "---ADOPT-TAIL---"
Get-Content "C:\opt\quant\desks\mt5\logs\intel_ship_adopt.log" -Tail 3
echo "---TASK-LASTRUN---"
schtasks /query /tn MT5-IntelShip /v /fo LIST | Select-String "Last Run|Last Result"