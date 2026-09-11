@echo off
rem ===================================================================================
rem SSH FORCED-COMMAND GATE for the VPS key `claude-hetzner-to-contabo-mt5`.
rem
rem WHY THIS EXISTS. One key carries two opposite things over the same channel:
rem
rem   READ  (keep)  ops/pull_desk_state.sh -- every line is `scp -pq REMOTE:C:/opt/... local`,
rem                 the dashboard's freshness pull. Nothing it does writes to this box.
rem   WRITE (deny)  heal_forward_lane._ship / check_desk_module_drift -- `scp local REMOTE:...`,
rem                 which ships the VPS's copy of a module ONTO this box. Their stated safety
rem                 property is "never ship what does not match HEAD", but HEAD there is the
rem                 VPS's own checkout, which is behind -- so a stale-but-clean tree passes the
rem                 check and last week's engine lands on the box that trades. Measured
rem                 2026-09-10: 24 trample events in 33 minutes after a clean seal, gateway.py
rem                 reverted 3000 -> 2127 lines, allows_new_risk flipping true->false, and
rem                 kelly_surface.py gutted 341 -> 80 lines, which broke the allocator outright.
rem
rem Disabling the key stopped the trampling AND the dashboard pull (AUTHENTICATION_FAILED).
rem This gate separates them by DIRECTION, which is the only thing that actually differs.
rem
rem HOW. In the scp protocol the far side runs `scp -f <path>` to SEND a file (from) and
rem `scp -t <path>` to RECEIVE one (to). A pull makes this box run `-f`; a push makes it run
rem `-t`. So `-t` is refused and everything else is passed through untouched.
rem
rem FAIL OPEN, DELIBERATELY. Only a clearly-identified write is refused; any command this gate
rem does not recognise RUNS. A gate that failed closed on an unfamiliar command would break the
rem dashboard pull again the first time the puller changed, which is the failure this is fixing.
rem
rem cmd.exe, not PowerShell: scp streams binary over stdio and PowerShell re-encodes it.
rem
rem To remove the gate entirely, drop the command="..." prefix from the key's line in
rem C:\ProgramData\ssh\administrators_authorized_keys.
rem ===================================================================================

if not defined SSH_ORIGINAL_COMMAND goto :interactive

rem `scp ... -t` in any flag position (scp -t, scp -p -d -t, scp -pdt) is a WRITE INTO this box.
echo(%SSH_ORIGINAL_COMMAND%| findstr /I /R /C:"scp .*-[dpqrvC]*t[dpqrvC]* " >nul && goto :deny
echo(%SSH_ORIGINAL_COMMAND%| findstr /I /R /C:"rsync .*--server.*\." >nul && goto :deny

%SSH_ORIGINAL_COMMAND%
exit /b %errorlevel%

:deny
echo REFUSED by ssh_pull_gate: this key may READ from the box, never WRITE to it. 1>&2
echo The VPS-side module healers ship a stale checkout's copy over the sealed money path 1>&2
echo (GAP_REGISTER 212). Fix the VPS's checkout, do not re-open the write path. 1>&2
exit /b 1

:interactive
echo REFUSED by ssh_pull_gate: no interactive shell on this key. 1>&2
exit /b 1
