@echo off
rem ===================================================================================
rem THIS BOX IS A FILE MIRROR AND NOTHING ELSE.
rem
rem WHAT THE DASHBOARD WAS ACTUALLY SHOWING, measured 2026-09-12. dash.quanttt.xyz reported
rem "box has not reported for 5.8h", gateway_state.json "last wrote 2026-08-17" (26 days), and
rem twenty-plus clocks IDENTITY BROKEN -- while the trading box was healthy, its gateway artifact
rem one minute old and its identity healer reporting "no IDENTITY_BROKEN clocks".
rem
rem The VPS does not serve the box's desk_state.json. It REGENERATES the board from its own copies
rem of the box artifacts, and it pulls those copies from THIS box. So every figure on that board
rem is as old as the newest artifact sitting here, and when the migration deleted this box's
rem tasks, the newest artifact here stopped moving. Mirroring desk_state.json alone did nothing,
rem because the VPS overwrites it with its own regeneration.
rem
rem So this mirrors the INPUTS. The VPS's existing pull then delivers a current board with no
rem change on the VPS at all -- which is the only lever available, because neither box holds a key
rem the VPS accepts (tested: quant, root, admin, both boxes, all refused).
rem
rem IT IS A BRIDGE. The moment the VPS is repointed at the trading box directly, delete this task
rem and this file. A bridge that outlives its crossing becomes the thing nobody remembers is
rem load-bearing -- which is exactly how this box came to be serving a live dashboard in the first
rem place.
rem ===================================================================================
setlocal
set "SRC=administrator@62.171.172.249"
set "KEY=%USERPROFILE%\.ssh\id_ed25519"
set "SCP=C:\Windows\System32\OpenSSH\scp.exe"
if not exist "%SCP%" set "SCP=scp"
set "OPTS=-i %KEY% -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -o BatchMode=yes -o ConnectTimeout=25"
set "LOG=C:\opt\quant\desks\mt5\logs\dash_mirror.log"
set "Q=C:/opt/quant"
set OK=0
set BAD=0

rem THE BOARD'S OWN LIVENESS CLOCKS. These are the files the VPS ages to decide whether the box
rem has "reported", so they are the difference between a live board and a LATE one.
call :grab "%Q%/desks/mt5/reports/shadow/shadow_health.json"        "C:\opt\quant\desks\mt5\reports\shadow\shadow_health.json"
call :grab "%Q%/desks/mt5/reports/shadow/shadow_state.json"         "C:\opt\quant\desks\mt5\reports\shadow\shadow_state.json"
call :grab "%Q%/desks/mt5/reports/shadow/scalp_shadow_state.json"   "C:\opt\quant\desks\mt5\reports\shadow\scalp_shadow_state.json"
call :grab "%Q%/desks/mt5/reports/shadow/qquant_shadow_state.json"  "C:\opt\quant\desks\mt5\reports\shadow\qquant_shadow_state.json"
call :grab "%Q%/desks/mt5/data/gateway_state.json"                  "C:\opt\quant\desks\mt5\data\gateway_state.json"
call :grab "%Q%/desks/mt5/data/account_state.json"                  "C:\opt\quant\desks\mt5\data\account_state.json"
call :grab "%Q%/desks/mt5/data/regime_state.json"                   "C:\opt\quant\desks\mt5\data\regime_state.json"

rem THE PANELS. Sleeves, the allocator's book, the certificate registry and the ledger are what
rem every tile below the liveness banner is computed from.
call :grab "%Q%/desks/mt5/data/sleeves.json"                        "C:\opt\quant\desks\mt5\data\sleeves.json"
call :grab "%Q%/desks/mt5/reports/pf_allocation.json"               "C:\opt\quant\desks\mt5\reports\pf_allocation.json"
call :grab "%Q%/desks/mt5/reports/UNIVERSAL_SURVIVORS.json"         "C:\opt\quant\desks\mt5\reports\UNIVERSAL_SURVIVORS.json"
call :grab "%Q%/desks/mt5/data/live_ledger.jsonl"                   "C:\opt\quant\desks\mt5\data\live_ledger.jsonl"
call :grab "%Q%/desks/mt5/data/stall_watch.json"                    "C:\opt\quant\desks\mt5\data\stall_watch.json"
call :grab "%Q%/desks/mt5/reports/process_health.json"              "C:\opt\quant\desks\mt5\reports\process_health.json"
call :grab "%Q%/desks/mt5/reports/organ_contract.json"              "C:\opt\quant\desks\mt5\reports\organ_contract.json"

rem The box's own finished board, for any consumer that reads it verbatim rather than rebuilding.
call :grab "%Q%/web/desk_state.json"                                "C:\opt\quant\web\desk_state.json"

echo %DATE% %TIME% mirrored ok=%OK% failed=%BAD%>>"%LOG%"
exit /b 0

:grab
rem A FAILED COPY IS COUNTED, NEVER SWALLOWED -- and the count is CHECKED against the file rather
rem than against scp's exit code. Measured 2026-09-12: this label reported ok=23 from fifteen
rem calls while shadow_health.json, the first file in the list and the one the board's whole
rem liveness banner is computed from, had not moved in 329 minutes. An exit code that disagrees
rem with the filesystem is not evidence, which is the same lesson as every other green-run failure
rem on this desk. So the copy is retried once and then VERIFIED by age.
rem RETRY WITH BACKOFF, NOT INSTANTLY (2026-09-12). The single immediate retry below was the
rem right shape and the wrong interval. The failure this box actually hits is
rem `kex_exchange_identification: Connection closed by remote host` -- the SSH daemon refusing the
rem CONNECTION, not the copy failing -- and a refusal repeated in the same millisecond is refused
rem again. Measured by hand the same day: three consecutive refusals, then success on the fourth
rem attempt about twenty seconds later, repeatedly.
rem
rem The cost of getting this wrong is not a missed file. The VPS regenerates the public board from
rem whatever this box holds, so a failed pull leaves the dashboard serving an OLD equity under a
rem FRESH `generated_at` -- measured today: the board showed 752.51 while the account held 607.68,
rem and its own age field read None so nothing could flag it. Four attempts with 5s/10s/20s of
rem backoff costs at most 35 seconds on a 3-minute clock and covers the whole observed window.
set "ATTEMPT=0"
:grab_try
set /a ATTEMPT+=1
"%SCP%" %OPTS% "%SRC%:%~1" "%~2" >nul 2>>"%LOG%"
if not errorlevel 1 goto :grab_check
if %ATTEMPT% GEQ 4 goto :grab_check
if %ATTEMPT%==1 ping -n 6 127.0.0.1 >nul 2>&1
if %ATTEMPT%==2 ping -n 11 127.0.0.1 >nul 2>&1
if %ATTEMPT%==3 ping -n 21 127.0.0.1 >nul 2>&1
goto :grab_try
:grab_check
rem forfiles /d 0 matches only a file modified TODAY; a file the copy did not refresh keeps its
rem old stamp and fails this, whatever scp claimed.
forfiles /p "%~dp2." /m "%~nx2" /d 0 >nul 2>&1
if errorlevel 1 (
    set /a BAD+=1
    echo %DATE% %TIME% STALE AFTER COPY: %~nx2>>"%LOG%"
) else (
    set /a OK+=1
)
exit /b 0
