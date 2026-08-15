#!/usr/bin/env bash
# Nightly Codex reasoner over the same durable Claude/Codex research state.
# Missing CLI/auth/lease never stops deterministic collectors or the completed research cycle.
set -uo pipefail
cd "$(dirname "$0")/.."

PIPELINE_RC="${1:-0}"
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

CLAIM_FILE="$(mktemp)"
PROMPT_FILE="$(mktemp)"
cleanup() {
    rm -f -- "$CLAIM_FILE" "$PROMPT_FILE"
}
trap cleanup EXIT

"$PY" scripts/controller_checkpoint.py claim --controller codex-midnight --ttl-seconds 900 >"$CLAIM_FILE"
CLAIM_STATUS=$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("status", ""))' "$CLAIM_FILE")
if [ "$CLAIM_STATUS" != "LEASED" ]; then
    HOLDER=$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("controller", "unknown"))' "$CLAIM_FILE")
    write_status "LEASE_HELD" "Controller lease already held by $HOLDER; duplicate mutation refused" 0
    echo "midnight-codex: lease held by $HOLDER; duplicate controller refused" | tee -a "$LOG"
    exit 0
fi
export QUANT_CONTROLLER="codex-midnight"
export QUANT_CONTROLLER_EPOCH
export QUANT_CONTROLLER_TOKEN
QUANT_CONTROLLER_EPOCH=$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["epoch"])' "$CLAIM_FILE")
QUANT_CONTROLLER_TOKEN=$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["fencing_token"])' "$CLAIM_FILE")

{
    printf '=== SEALED AUTHORITATIVE MASTER CONSTITUTION (verified before lease claim) ===\n'
    cat docs/MASTER_QUANT_CONSTITUTION.md
    printf '\n=== MIDNIGHT CONTROLLER OPERATING BRIEF ===\n'
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

CODEX_NIGHTLY_MODEL="${CODEX_NIGHTLY_MODEL:-gpt-5.6-sol}"
CODEX_ARGS=(exec -C "$PWD" --sandbox workspace-write --ask-for-approval never
    --output-last-message "$LAST_MESSAGE"
    --config "model_reasoning_effort=${CODEX_NIGHTLY_REASONING_EFFORT:-max}")
if [ -n "${CODEX_NIGHTLY_MODEL:-}" ]; then
    CODEX_ARGS+=(--model "$CODEX_NIGHTLY_MODEL")
fi
codex "${CODEX_ARGS[@]}" - <"$PROMPT_FILE" >>"$LOG" 2>&1
CODEX_RC=$?
kill "$HEARTBEAT_PID" >/dev/null 2>&1 || true
wait "$HEARTBEAT_PID" 2>/dev/null || true

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
