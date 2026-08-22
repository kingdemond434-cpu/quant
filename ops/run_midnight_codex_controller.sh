#!/usr/bin/env bash
# Nightly Codex reasoner over the same durable Claude/Codex research state.
# Missing CLI/auth/lease never stops deterministic collectors or the completed research cycle.
set -uo pipefail
cd "$(dirname "$0")/.."

MODE="${1:-run}"
if [ "$MODE" = "--pipeline-start" ]; then
    PIPELINE_RC=-1
else
    PIPELINE_RC="${1:-0}"
fi
LOG_DIR="data/cro_ai_logs"
STATUS="data/intelligence/midnight_codex_status.json"
LAST_MESSAGE="data/intelligence/midnight_codex_last_message.md"
mkdir -p "$LOG_DIR" "$(dirname "$STATUS")"
LOG="$LOG_DIR/midnight_codex_$(date -u +%Y%m%dT%H%M%SZ).log"

PY=""
for _candidate in "$PWD/.venv/bin/python" .venv/bin/python python3; do
    if [ -x "$_candidate" ] || command -v "$_candidate" >/dev/null 2>&1; then
        PY="$_candidate"
        break
    fi
done
[ -n "$PY" ] || { echo "FATAL: no interpreter"; exit 1; }

write_status() {
    local state="$1"
    local reason="$2"
    local rc="$3"
    "$PY" - "$STATUS" "$state" "$reason" "$rc" "$PIPELINE_RC" <<'PYEOF'
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

path = Path(sys.argv[1])
row = {
    "updated_at": datetime.now(tz=UTC).isoformat(),
    "status": sys.argv[2],
    "reason": sys.argv[3],
    "controller_rc": int(sys.argv[4]),
    "pipeline_rc": int(sys.argv[5]),
    "persistent_workers_controller_independent": True,
}
tmp = path.with_suffix(".tmp")
tmp.write_text(json.dumps(row, indent=1), "utf-8")
os.replace(tmp, path)
PYEOF
}

if [ "$MODE" = "--pipeline-start" ]; then
    write_status "RUNNING_PIPELINE" "Deterministic frontier is running; controller has not started" -1
    exit 0
fi

if ! "$PY" scripts/check_constitution_core.py >>"$LOG" 2>&1; then
    write_status "CONSTITUTION_BREACH" "Sealed master/core verification failed; controller mutation refused" 125
    echo "midnight-codex: constitution verification failed; deterministic machinery remains active" | tee -a "$LOG"
    exit 4
fi

if ! command -v codex >/dev/null 2>&1; then
    write_status "UNAVAILABLE" "Codex CLI is not installed on the VPS; deterministic cycle preserved" 127
    echo "midnight-codex: CLI unavailable; deterministic machinery remains active" | tee -a "$LOG"
    exit 3
fi
if ! codex login status >>"$LOG" 2>&1; then
    write_status "AUTH_REQUIRED" "Run codex login --device-auth once on the VPS; no repository state reset" 126
    echo "midnight-codex: authentication unavailable; deterministic machinery remains active" | tee -a "$LOG"
    exit 3
fi

# Codex 0.147 exposes the unattended policy as a GLOBAL option (before `exec`); newer builds
# may expose it on `exec`. Detect the parser surface instead of pinning a flag that silently
# moved. `--approve-for-me` remains a sandboxed, automatic-review compatibility fallback.
CODEX_GLOBAL_ARGS=()
CODEX_EXEC_APPROVAL_ARGS=()
CODEX_HELP=$(codex --help 2>&1)
CODEX_EXEC_HELP=$(codex exec --help 2>&1)
if grep -q -- "--ask-for-approval" <<<"$CODEX_HELP"; then
    CODEX_GLOBAL_ARGS=(--ask-for-approval never)
elif grep -q -- "--ask-for-approval" <<<"$CODEX_EXEC_HELP"; then
    CODEX_EXEC_APPROVAL_ARGS=(--ask-for-approval never)
elif grep -q -- "--approve-for-me" <<<"$CODEX_EXEC_HELP"; then
    CODEX_EXEC_APPROVAL_ARGS=(--approve-for-me)
else
    write_status "CLI_INCOMPATIBLE" "Installed Codex has no supported unattended approval mode" 124
    echo "midnight-codex: installed CLI lacks an unattended approval mode" | tee -a "$LOG"
    exit 3
fi

CLAIM_FILE="$(mktemp)"
PROMPT_FILE="$(mktemp)"
HEARTBEAT_PID=""
cleanup() {
    if [ -n "$HEARTBEAT_PID" ]; then
        kill "$HEARTBEAT_PID" >/dev/null 2>&1 || true
        wait "$HEARTBEAT_PID" 2>/dev/null || true
    fi
    rm -f -- "$CLAIM_FILE" "$PROMPT_FILE"
}
trap cleanup EXIT

CLAIM_RC=0
"$PY" scripts/controller_checkpoint.py claim --controller codex-midnight --ttl-seconds 900 \
    >"$CLAIM_FILE" || CLAIM_RC=$?
if [ "$CLAIM_RC" -ne 0 ]; then
    CLAIM_REASON=$("$PY" -c 'import json,sys
try: print(json.load(open(sys.argv[1], encoding="utf-8")).get("reason", "unknown claim failure"))
except Exception: print("unreadable claim response")' "$CLAIM_FILE")
    write_status "LEASE_ERROR" "Controller lease claim failed: $CLAIM_REASON" "$CLAIM_RC"
    echo "midnight-codex: lease claim failed closed: $CLAIM_REASON" | tee -a "$LOG"
    exit "$CLAIM_RC"
fi
CLAIM_PARSE_RC=0
CLAIM_STATUS=$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("status", ""))' "$CLAIM_FILE") || CLAIM_PARSE_RC=$?
if [ "$CLAIM_PARSE_RC" -ne 0 ] || { [ "$CLAIM_STATUS" != "LEASED" ] && [ "$CLAIM_STATUS" != "LEASE_HELD" ]; }; then
    write_status "LEASE_ERROR" "Controller lease claim returned malformed or unknown state" 2
    echo "midnight-codex: malformed/unknown lease response; failing closed" | tee -a "$LOG"
    exit 2
fi
if [ "$CLAIM_STATUS" = "LEASE_HELD" ]; then
    HOLDER=$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("controller", "unknown"))' "$CLAIM_FILE" 2>/dev/null || echo unknown)
    write_status "LEASE_HELD" "Controller lease already held by $HOLDER; duplicate mutation refused" 0
    echo "midnight-codex: lease held by $HOLDER; duplicate controller refused" | tee -a "$LOG"
    exit 0
fi
export QUANT_CONTROLLER="codex-midnight"
export QUANT_CONTROLLER_EPOCH
export QUANT_CONTROLLER_TOKEN
QUANT_CONTROLLER_EPOCH=$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["epoch"])' "$CLAIM_FILE")
QUANT_CONTROLLER_TOKEN=$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["fencing_token"])' "$CLAIM_FILE")
write_status "RUNNING_CONTROLLER" "Codex holds the fenced lease and is processing the current frontier" -1

{
    printf '=== SEALED MASTER STATUS ===\n'
    printf 'docs/MASTER_QUANT_CONSTITUTION.md passed scripts/check_constitution_core.py. '
    printf 'It remains authoritative; inspect only the relevant clauses on demand.\n'
    printf '\n=== SINGLE MT5-ONLY MIDNIGHT OPERATING BRIEF ===\n'
    cat ops/midnight_codex_prompt.txt
    printf '\nRUNTIME STATE: deterministic pipeline exit code=%s; controller epoch=%s.\n' \
        "$PIPELINE_RC" "$QUANT_CONTROLLER_EPOCH"
} >"$PROMPT_FILE"

heartbeat_loop() {
    while true; do
        sleep 300
        "$PY" scripts/controller_checkpoint.py heartbeat --ttl-seconds 900 >>"$LOG" 2>&1 || exit 0
    done
}
heartbeat_loop &
HEARTBEAT_PID=$!

# Precedence: an explicit _OVERRIDE beats everything, then whatever the unit file
# exports, then the pinned default. The pre-merge form read ONLY _OVERRIDE, which
# silently discarded the Environment= lines in quant-midnight-frontier.service --
# the unit's model pin had no effect on the process the unit itself started.
CODEX_NIGHTLY_MODEL="${CODEX_NIGHTLY_MODEL_OVERRIDE:-${CODEX_NIGHTLY_MODEL:-gpt-5.6-terra}}"
CODEX_NIGHTLY_REASONING_EFFORT="${CODEX_NIGHTLY_REASONING_EFFORT_OVERRIDE:-${CODEX_NIGHTLY_REASONING_EFFORT:-medium}}"
CODEX_ARGS=(exec -C "$PWD" --sandbox workspace-write "${CODEX_EXEC_APPROVAL_ARGS[@]}"
    --output-last-message "$LAST_MESSAGE"
    --config "model_reasoning_effort=${CODEX_NIGHTLY_REASONING_EFFORT}"
    --model "$CODEX_NIGHTLY_MODEL")
CODEX_RC=0
timeout --signal=TERM --kill-after=60 "${CODEX_NIGHTLY_TIMEOUT_SECONDS:-10800}" \
    codex "${CODEX_GLOBAL_ARGS[@]}" "${CODEX_ARGS[@]}" - <"$PROMPT_FILE" >>"$LOG" 2>&1 \
    || CODEX_RC=$?
kill "$HEARTBEAT_PID" >/dev/null 2>&1 || true
wait "$HEARTBEAT_PID" 2>/dev/null || true
HEARTBEAT_PID=""

CHECKPOINT_RC=0
"$PY" scripts/controller_checkpoint.py checkpoint \
    --note "midnight Codex finished rc=$CODEX_RC after deterministic pipeline rc=$PIPELINE_RC" \
    >>"$LOG" 2>&1 || CHECKPOINT_RC=$?

TRANSFER_RC=0
if [ "$CHECKPOINT_RC" -eq 0 ]; then
    "$PY" scripts/controller_checkpoint.py transfer --successor claude-primary --ttl-seconds 60 \
        --note "resume exact improved state; midnight Codex rc=$CODEX_RC" \
        >>"$LOG" 2>&1 || TRANSFER_RC=$?
else
    TRANSFER_RC=125
fi

if [ "$CODEX_RC" -eq 0 ] && [ "$CHECKPOINT_RC" -eq 0 ] && [ "$TRANSFER_RC" -eq 0 ]; then
    write_status "CHECKPOINTED_FOR_CLAUDE" "Midnight controller completed, checkpointed, and atomically transferred" 0
    FINAL_RC=0
elif [ "$CHECKPOINT_RC" -eq 0 ] && [ "$TRANSFER_RC" -eq 0 ]; then
    write_status "CONTROLLER_FAILED_CHECKPOINTED" "Controller rc=$CODEX_RC; exact state checkpointed and transferred; inspect $LOG" "$CODEX_RC"
    FINAL_RC="$CODEX_RC"
else
    FINAL_RC="$CHECKPOINT_RC"
    [ "$FINAL_RC" -ne 0 ] || FINAL_RC="$TRANSFER_RC"
    write_status "HANDOFF_INCOMPLETE" "controller_rc=$CODEX_RC checkpoint_rc=$CHECKPOINT_RC transfer_rc=$TRANSFER_RC; deterministic state remains active; inspect $LOG" "$FINAL_RC"
fi
echo "midnight-codex: controller_rc=$CODEX_RC checkpoint_rc=$CHECKPOINT_RC transfer_rc=$TRANSFER_RC; log=$LOG; last-message=$LAST_MESSAGE"
exit "$FINAL_RC"
