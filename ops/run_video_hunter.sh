#!/usr/bin/env bash
# Daily creator/video hunter -- SCHEDULED 2026-08-25 by principal order after the source audit
# measured this pipeline as the desk's best: its creator corpora (DaviddTech hunt16, RFT hunt19,
# Saleh hunt20) produced 94 stage-A survivors and the ONLY exact ten-gate certificate. It had
# never been on a clock -- the top source ran only when someone remembered (III.16).
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
if find data/cro_ai_logs -name "video_hunter_$(date -u +%Y%m%d)T*.log" -size +1500c 2>/dev/null | grep -q .; then
    echo "video_hunter: already produced today -- skipping (chain/timer no-op)"
    exit 0
fi

dig_dry_run video-hunter ops/gpt_video_hunter_prompt.txt && exit 0
mkdir -p data/cro_ai_logs
LOG="data/cro_ai_logs/video_hunter_$(date -u +%Y%m%dT%H%M).log"
echo "=== video-hunter attempt $(date -u) ===" >> "$LOG"
export BRAIN_MUTEX_LOGFILE="$LOG"
brain_mutex video-hunter
brain_auth_check || { echo "auth unavailable -- next run resumes ($(date -u))" >> "$LOG"; exit 1; }
# YouTube Data API key, if the principal has dropped it at the standard path. The prompt treats
# video as the index and text/code as the corpus either way; the key just makes enumeration cheap.
if [ -f data/secrets/youtube_api_key ]; then
    YT_API_KEY="$(tr -d '[:space:]' < data/secrets/youtube_api_key)"
    export YT_API_KEY
    echo "youtube api key: PRESENT (data/secrets/youtube_api_key)" >> "$LOG"
else
    echo "youtube api key: absent -- metadata routes only" >> "$LOG"
fi
claude --effort "${BRAIN_EFFORT:-low}" --append-system-prompt "$_DOCTRINE" -p "$(dig_prompt ops/gpt_video_hunter_prompt.txt)" --dangerously-skip-permissions >> "$LOG" 2>&1
echo "=== video-hunter exit $? at $(date -u) ===" >> "$LOG"

exit $?
}
