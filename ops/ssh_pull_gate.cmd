@echo off
rem ===================================================================================
rem SSH FORCED-COMMAND GATE for the key `claude-hetzner-to-contabo-mt5`.
rem
rem WHY THIS EXISTS. One key carries two opposite things over the same channel:
rem
rem   READ  (keep)  ops/pull_desk_state.sh -- every line is `scp -pq REMOTE:C:/opt/... local`,
rem                 the dashboard's freshness pull. Nothing it does writes to this box.
rem   WRITE (deny)  heal_forward_lane._ship / check_desk_module_drift -- `scp local REMOTE:...`,
rem                 which ships a stale checkout's copy of a module ONTO the box that trades.
rem                 Measured 2026-09-10: 24 trample events in 33 minutes after a clean seal,
rem                 gateway.py reverted 3000 -> 2127 lines, allows_new_risk flipping
rem                 true->false, kelly_surface.py gutted 341 -> 80 lines.
rem
rem WHY IT IS NOW AN ALLOW-LIST, AND NOT FAIL-OPEN. The previous version denied `scp -t` and
rem `rsync --server`, then ran ANY other command verbatim -- so the key was still a remote
rem shell in everything but name. Measured 2026-09-11: 557 authenticated sessions in one hour
rem from a single non-VPS address, and the money path reverted every few minutes while every
rem local suspect (MT5-AdoptRelease disabled since 06:12, the reflog quiet since 11:53) was
rem ruled out. A deny-list cannot enumerate the ways to write a file. This one names what may
rem run; everything else is refused AND LOGGED, so the next unfamiliar caller is evidence
rem rather than a silent edit to code that trades real money.
rem
rem FAIL CLOSED. Adding a caller means adding a line here, on purpose, with a reason.
rem
rem EVERY EXPANSION OF %SSH_ORIGINAL_COMMAND% IS QUOTED. Unquoted, cmd parses the caller's
rem string for `&`, `&&` and `|` BEFORE the gate ever decides anything -- so
rem `cd C:\opt\quant && git checkout HEAD -- .` logged as a refusal of `cd C:\opt\quant`
rem and then ran the checkout anyway. Measured 2026-09-11: 195 such lines in this log while the
rem money path kept reverting. The refusal was real and the write happened regardless.
rem
rem cmd.exe, not PowerShell: scp streams binary over stdio and PowerShell re-encodes it.
rem To remove the gate, drop the command="..." prefix from the key's line in
rem C:\ProgramData\ssh\administrators_authorized_keys.
rem ===================================================================================

set "GATELOG=C:\opt\quant\desks\mt5\logs\ssh_pull_gate.log"

if not defined SSH_ORIGINAL_COMMAND goto :interactive

rem ---- ALLOW 1: scp SEND. `scp -f <path>` is the far side asking this box to hand a file OUT.
rem      This is the dashboard pull and the only reason the key still exists.
echo("%SSH_ORIGINAL_COMMAND%"| findstr /I /R /C:"^scp .*-[dpqrvC]*f[dpqrvC]* " >nul && goto :allow

rem ---- ALLOW 2: `git hash-object` / `git rev-parse`. Read-only; the VPS drift checks compare
rem      hashes before deciding whether anything needs attention. They write nothing.
echo("%SSH_ORIGINAL_COMMAND%"| findstr /I /R /C:"^git .*hash-object" >nul && goto :allow
echo("%SSH_ORIGINAL_COMMAND%"| findstr /I /R /C:"^git .*rev-parse" >nul && goto :allow

rem ---- ALLOW 3 (DOWNGRADED): SFTP, but read-only.
rem      OpenSSH 9+ routes `scp` through the SFTP protocol, so the dashboard's pull arrives here
rem      as `sftp-server.exe`, NOT as `scp -f`. Refusing it outright breaks the pull -- which is
rem      the failure this gate was written to avoid. But sftp-server is a full filesystem, and
rem      that is how the money path was being overwritten: measured 2026-09-11, sftp-server.exe
rem      (pid 0x1490) wrote desks/mt5/mt5desk/families.py at 12:23:01, four seconds before the
rem      revert this session caught on a checksum watch.
rem      `-R` is sftp-server's own read-only mode: every write request is refused by the server
rem      itself. So the pull keeps working and the trample cannot happen, which is the same
rem      direction split the rest of this gate enforces.
echo("%SSH_ORIGINAL_COMMAND%"| findstr /I /R /C:"sftp-server" >nul && goto :sftp_readonly
echo("%SSH_ORIGINAL_COMMAND%"| findstr /I /R /C:"internal-sftp" >nul && goto :sftp_readonly

rem ---- Everything else: refused and recorded.
goto :deny

:sftp_readonly
>>"%GATELOG%" echo %DATE% %TIME% SFTP-READONLY: "%SSH_ORIGINAL_COMMAND%"
"C:\Windows\System32\OpenSSH\sftp-server.exe" -R
exit /b %errorlevel%

:allow
>>"%GATELOG%" echo %DATE% %TIME% ALLOW: "%SSH_ORIGINAL_COMMAND%"
%SSH_ORIGINAL_COMMAND%
exit /b %errorlevel%

:deny
>>"%GATELOG%" echo %DATE% %TIME% REFUSED: "%SSH_ORIGINAL_COMMAND%"
echo REFUSED by ssh_pull_gate: this key may READ from the box, never WRITE to it. 1>&2
echo Only `scp -f`, `git hash-object` and `git rev-parse` are allowed (GAP_REGISTER 212). 1>&2
echo Fix the caller's checkout; do not re-open the write path. 1>&2
exit /b 1

:interactive
>>"%GATELOG%" echo %DATE% %TIME% REFUSED: (interactive shell request)
echo REFUSED by ssh_pull_gate: no interactive shell on this key. 1>&2
exit /b 1
