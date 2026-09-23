@echo off
rem ===================================================================================
rem DASHBOARD RELAY: mirror the trading box's published state onto this box.
rem
rem WHY THIS EXISTS. The public dashboard (dash.quanttt.xyz) is served from the Hetzner
rem VPS, and the VPS PULLS its data from this box over SSH -- this box is the SSH server,
rem the VPS chose the address, and nothing here can change where it looks. On 2026-09-11
rem the desk moved to the big box (96 GB / 18 cores) and every organ here was disabled,
rem so the files the VPS pulls stopped being rebuilt and the dashboard went silent while
rem the desk itself was perfectly healthy on the other box.
rem
rem WHAT THE DASHBOARD WAS MISSING. The VPS has no MT5 terminal and correctly refuses to
rem invent an equity ("a machine that cannot see the account must not print one" -- the last
rem terminal-less writer published 28x the real balance). So the account, shadow, regime and
rem equity panels are fed ONLY by files arriving from the trading box, and with the sync off
rem they read 18h stale or ABSENT. Each line below is one of those panels.
rem
rem STRAIGHT LINES, NO :LABEL. A `call :grab` helper failed with "cannot find the batch label"
rem partway through a pass and silently skipped the rest -- a relay that half-runs is worse
rem than one that does not, because the dashboard then shows some panels fresh and some stale
rem with nothing saying why. A missing source is still not an error: scp writes nothing, the
rem previous file stands with its own timestamp, and staleness stays visible.
rem
rem DELETE THIS ONCE THE VPS PULLS FROM THE BOX DIRECTLY. It is a bridge, and a
rem bridge that outlives its crossing becomes the thing everyone forgets is load-bearing.
rem ===================================================================================

rem A KEY THE TASK CAN ACTUALLY READ. The relay runs as SYSTEM and ssh silently refused the
rem key under the Administrator profile -- no error reached the log, the transfers simply did
rem not happen, and the relay kept printing 'pass complete' over a file that had not moved in
rem 149 minutes. That is the same failure shape as every other one found today: a green run is
rem weak evidence that anything happened. The copy under data\secrets is gitignored and ACL'd
rem to SYSTEM and Administrators only, and it is readable by the identity that actually runs.
set "SCP=C:\Windows\System32\OpenSSH\scp.exe"
set "KEY=C:\opt\quant\data\secrets\relay_key"
rem THE HOST IS NOT COMMITTED. A tracked file naming the box that carries live risk is
rem a targeting detail, and the desk had no gate against publishing one until
rem tests/ops/test_live_infrastructure_is_not_published.py. Set QUANT_BOX_HOST in the
rem machine environment (it already holds the QUANT_* settings) or in a gitignored file.
if not defined QUANT_BOX_HOST (
    echo QUANT_BOX_HOST is not set; refusing to guess the trading box address
    exit /b 2
)
set "SRC=administrator@%QUANT_BOX_HOST%"
set "LOG=C:\opt\quant\desks\mt5\logs\dashboard_relay.log"
if not exist "C:\Windows\System32\OpenSSH\scp.exe" set "SCP=scp"
set "OPTS=-i %KEY% -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -o BatchMode=yes -o ConnectTimeout=20"

if not exist "C:\opt\quant\desks\mt5\reports\shadow" mkdir "C:\opt\quant\desks\mt5\reports\shadow"

"%SCP%" %OPTS% -q "%SRC%:C:/opt/quant/web/desk_state.json"                              "C:\opt\quant\web\desk_state.json" 2>>"%LOG%"
"%SCP%" %OPTS% -q "%SRC%:C:/opt/quant/web/equity_history.jsonl"                         "C:\opt\quant\web\equity_history.jsonl" 2>>"%LOG%"
"%SCP%" %OPTS% -q "%SRC%:C:/opt/quant/desks/mt5/data/account_state.json"                "C:\opt\quant\desks\mt5\data\account_state.json" 2>>"%LOG%"
"%SCP%" %OPTS% -q "%SRC%:C:/opt/quant/desks/mt5/data/gateway_state.json"                "C:\opt\quant\desks\mt5\data\gateway_state.json" 2>>"%LOG%"
"%SCP%" %OPTS% -q "%SRC%:C:/opt/quant/desks/mt5/data/release_identity.json"             "C:\opt\quant\desks\mt5\data\release_identity.json" 2>>"%LOG%"
"%SCP%" %OPTS% -q "%SRC%:C:/opt/quant/desks/mt5/data/regime_state.json"                 "C:\opt\quant\desks\mt5\data\regime_state.json" 2>>"%LOG%"
"%SCP%" %OPTS% -q "%SRC%:C:/opt/quant/desks/mt5/data/stall_watch.json"                  "C:\opt\quant\desks\mt5\data\stall_watch.json" 2>>"%LOG%"
"%SCP%" %OPTS% -q "%SRC%:C:/opt/quant/desks/mt5/reports/shadow/shadow_health.json"      "C:\opt\quant\desks\mt5\reports\shadow\shadow_health.json" 2>>"%LOG%"
"%SCP%" %OPTS% -q "%SRC%:C:/opt/quant/desks/mt5/reports/shadow/scalp_shadow_state.json" "C:\opt\quant\desks\mt5\reports\shadow\scalp_shadow_state.json" 2>>"%LOG%"
"%SCP%" %OPTS% -q "%SRC%:C:/opt/quant/desks/mt5/reports/shadow/shadow_state.json"       "C:\opt\quant\desks\mt5\reports\shadow\shadow_state.json" 2>>"%LOG%"
"%SCP%" %OPTS% -q "%SRC%:C:/opt/quant/desks/mt5/reports/UNIVERSAL_SURVIVORS.json"       "C:\opt\quant\desks\mt5\reports\UNIVERSAL_SURVIVORS.json" 2>>"%LOG%"

if errorlevel 1 (echo %DATE% %TIME% relay pass FAILED>>"%LOG%") else (echo %DATE% %TIME% relay pass complete>>"%LOG%")
exit /b 0
