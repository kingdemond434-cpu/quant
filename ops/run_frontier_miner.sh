#!/usr/bin/env bash
# Regional frontier miner (principal activation 2026-07-20; ledger #114).
# Lightweight daily dig via Prospector infrastructure -- one region per invocation.
set -uo pipefail
cd /home/quant/quant-platform
source ops/brain_env.sh
# TODAY-GUARD (2026-08-25): one real dig per day; chain and scattered timers cannot double-run.
# SEALED AGAINST MID-RUN REWRITE (2026-08-26). bash reads a script INCREMENTALLY by byte
# offset; this desk commits ~200x/day into the tree these launchers execute from, and a dig
# holds its slot up to 3h, so a commit that changes this file's LENGTH mid-run makes bash
# resume from the middle of a line. Measured on 63680c05: comment text executed as a command,
# then a dangling `fi`, then the script RE-RAN ITSELF FROM THE TOP. A `{ ... }` alone protects
# the body but bash still reads past the closing brace; only the exit INSIDE the group ends the
# process before another byte is read. See ops/run_frontier_rotation.sh for the full account.
# DO NOT UNWRAP THE BRACE AND DO NOT ADD A LINE AFTER THE CLOSING `}`.
{
if [ "${1:-}" = "unified" ] && find data/cro_ai_logs -name "frontier_unified_$(date -u +%Y%m%d)T*.log" -size +1500c 2>/dev/null | grep -q .; then
    echo "unified frontier: already produced today -- skipping (chain/timer no-op)"
    exit 0
fi

REGION="${1:?region arg required (en|cn|ru|kr|jp|ar|br)}"
dig_dry_run "frontier-$REGION" "ops/frontier_${REGION}_prompt.txt" && exit 0
# ATTEMPT-FIRST (2026-08-11): the stub is written BEFORE the mutex/auth exits. organ_catchup
# reads "no logs today" as "timer has not fired -- not ours to start", so a logless deferral made
# the region invisible to its own retry loop: at 15:00 all 7 regions deferred behind the 14:45
# brain run, left zero logs, and the daily timer was the only other invoker -- a silent mutex
# collision cost the entire day, repeatedly (the organ-never-frontier-* fence class).
mkdir -p data/cro_ai_logs
LOG="data/cro_ai_logs/frontier_${REGION}_$(date -u +%Y%m%dT%H%M).log"
echo "=== frontier-$REGION attempt $(date -u) ===" >> "$LOG"
export BRAIN_MUTEX_LOGFILE="$LOG"
# ONE brain desk-wide. Deferring is safe here BY DESIGN: run_frontier_rotation.sh only skips a
# region that produced a real (>=1500b) log today, so a deferred region stays owed and the next
# rotation invocation resumes it -- the mutex composes with the existing resume point.
# MEMORY GATE BEFORE THE MUTEX. `brain_mem_gate` was written 2026-08-31 for exactly the death
# this line prevents -- "a seat that dies between its attempt header and its first claude line is
# a SILENT death, 21 stubs in 7 days, oom_kill counter at 912, 0 swap on 3.8GB" -- and was then
# DEFINED AND NEVER CALLED (III.16: unwired is a defect). Measured 2026-09-02: four
# frontier_unified logs held nothing but their 65-byte header, and the health report read them as
# crashing seats. A starved launcher must DEFER with a logged reason, not die without one.
brain_mem_gate || exit 0
brain_mutex "frontier-${REGION}"
# DUAL-POOL ROUTING (principal 2026-07-25): try the fable-5 METERED pool FIRST, then fall back
# to the Max subscription seat. brain_auth_check walks this chain and exports the winner, so the
# 7 regions AUTO-LOAD-BALANCE -- the first consume fable's ~1-run-per-5h-window, the rest land on
# opus-5 automatically. Safe here and nowhere else: the rotation is RESUMABLE (a region without a
# real log today is re-dug next invocation), so a mid-dig credit death costs nothing, and every
# miner run on fable is Max-seat headroom preserved for the brain cycle and the deep sweep.
#
# The chain itself is NO LONGER re-declared here (2026-07-30). It arrives from brain_env.sh, which
# sources the generated ops/model_chain.env. Re-exporting a literal at this line would silently
# pin the miners to yesterday's models the first time run_model_upgrade.py adopts a newer flagship
# -- the organ doing the most model-bound work would be the last to benefit from a better one.
# The routing INTENT above is unchanged: fable head, walk down, auto-load-balance across regions.
brain_auth_check || { echo "auth unavailable -- next run resumes ($(date -u))" >> "$LOG"; exit 1; }
# §33 CONVERSION PRIORITY. `dig_prompt` (ops/brain_env.sh) prepends the conversion duty
# to this organ's brief so the run spends its FIRST effort disposing of the backlog, then
# mines on in the SAME run -- mining is never throttled. It replaces a `_MINE_PRIORITY`
# variable that was computed here and never referenced, under this exact comment.
# AN IN-FLIGHT SENTINEL, NOT A COMPLETION MARKER. The obvious repair -- write an "exit" line
# after the dig -- was already in this file, unconditionally, and STILL never appeared: measured
# 2026-08-28, not one frontier_unified log on disk carries one. The dig is TERMINATED (session
# limit, seat timeout, watchdog) and the shell never reaches the next statement. A trap does not
# save it either; verified by killing the process group exactly as systemd does, and bash died
# without running its handler.
#
# So do not try to write something at the moment of death. Write it at the START and remove it on
# success. Being killed then needs no cooperation from the dying process: the sentinel simply
# stays, and its PRESENCE is the evidence that this dig did not finish. That is robust to
# SIGKILL, to a seat timeout, and to the box rebooting mid-dig.
#
# This matters because of what the resume gate does with it: the principal's standing instruction
# is that a dig cut off by a session limit must pick up from the same spot once the limit lifts.
# Judged by log SIZE, the 06:20 dig on 2026-08-28 wrote 10,667 bytes of real work, was cut off,
# and counted as "produced today" -- so it never resumed. Bytes are not completion.
RUNMARK="data/.digs/frontier_${REGION}_$(date -u +%Y%m%d).running"
mkdir -p data/.digs
echo "started=$(date -u +%FT%TZ) pid=$$ log=$LOG" > "$RUNMARK"

echo "=== frontier-$REGION start $(date -u) ===" >> "$LOG"
claude --effort "${BRAIN_EFFORT:-low}" --append-system-prompt "$_DOCTRINE" -p "$(dig_prompt ops/frontier_${REGION}_prompt.txt)" --dangerously-skip-permissions >> "$LOG" 2>&1
_rc=$?
echo "=== frontier-$REGION exit $_rc at $(date -u) ===" >> "$LOG"
# Cleared ONLY on a clean return from the dig. A non-zero exit is still a finished attempt for
# the day -- the dig ran and stopped for its own reasons -- but a KILLED run never reaches here,
# which is exactly the case the sentinel exists to catch.
rm -f "$RUNMARK"

exit $?
}
