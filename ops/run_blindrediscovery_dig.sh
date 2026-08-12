#!/usr/bin/env bash
set -uo pipefail
cd /home/quant/quant-platform
source ops/brain_env.sh
dig_dry_run blindrediscovery ops/blindrediscovery_dig_prompt.txt && exit 0
brain_mutex blindrediscovery   # ONE brain desk-wide; defers (exit 0) if another organ holds it
# MINER SEAT (principal 2026-08-12): fable head, walk down to the Max seat on
# exhaustion. Resolved from libs.ops.model_chain.MINER_ORGANS, never a literal here --
# a re-declared chain at this line is exactly how the miners got pinned to yesterday's
# models before 07-30.
brain_seat blindrediscovery
brain_auth_check || exit 1
# §33 CONVERSION PRIORITY. `dig_prompt` (ops/brain_env.sh) prepends the conversion duty
# to this organ's brief so the run spends its FIRST effort disposing of the backlog, then
# mines on in the SAME run -- mining is never throttled. It replaces a `_MINE_PRIORITY`
# variable that was computed here and never referenced, under this exact comment.
mkdir -p data/cro_ai_logs
LOG="data/cro_ai_logs/blindrediscovery_$(date -u +%Y%m%dT%H%M).log"
# ALL digs at max effort (principal 2026-07-24: Max plan, max everything).
_DIG_EFFORT=max
claude --effort "$_DIG_EFFORT" --append-system-prompt "$_DOCTRINE" -p "$(dig_prompt ops/blindrediscovery_dig_prompt.txt)" --dangerously-skip-permissions >> "$LOG" 2>&1
