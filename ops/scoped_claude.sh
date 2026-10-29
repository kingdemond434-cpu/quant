# shellcheck shell=bash
# SCOPED CLAUDE FOR THE VPS SHELL AGENT LANES -- sourced by the ten ops/run_*.sh launchers that
# used to pass the blanket permission-bypass flag (tests/ops/test_no_permission_bypass.py).
#
#     scoped_claude <lane> <log> <effort> [wrapper words...] < prompt
#
# e.g.  scoped_claude cro_ai "$LOG" "${BRAIN_EFFORT:-low}" <<<"$PROMPT"
#       scoped_claude recommendation_worker "$LOG" max timeout 3000 <<<"$PROMPT"
#       scoped_claude prospector_dig "$LOG" low < <(dig_prompt ops/prospector_dig_prompt.txt)
#
# 1. libs/ops/vps_lane_scopes.py builds the lane's arguments from the prompt on stdin: the
#    lane's --allowedTools, NEVER_RULES + the lane-self rules as --disallowedTools, stream-json
#    output, the allowlist stated at the end of the prompt, and --settings carrying the
#    libs/ops/lane_guard.py PreToolUse hook (the whole-command fence: no forced / deleting /
#    box-branch push, no read of data/secrets by any program; it fails closed). If that cannot be built the run
#    does NOT start (and never falls back to a bypass): the log says UNMEASURED and we return 2.
# 2. claude runs (behind any wrapper words, e.g. `timeout 3000`) with the stream going to
#    data/cro_ai_logs/.streams/ and stderr to the log, stdin closed so -p never swallows it.
# 3. scripts/record_agent_denials.py appends the run's result text to the log -- so the log reads
#    as it did in text mode, and the today-guards' size checks still see real output -- plus one
#    "PERMISSION DENIED (counts as MISSED ...)" line per refused call, and one UNMEASURED/MISSED
#    row per refused call to data/cro_ai_logs/agent_denials.jsonl. The stream is removed once it
#    has been recorded; a stream the recorder could not read is KEPT as the evidence.
#
# Returns the lane's own exit code: the recorder never hides the pass's result behind its own.
scoped_claude() {
    local lane="$1" log="$2" effort="$3"
    shift 3
    local py="${QUANT_PY:-.venv/bin/python}"
    local claude_bin="${CLAUDE_BIN:-claude}"
    local sdir="data/cro_ai_logs/.streams"
    local stream rc rec
    local -a args=()
    mkdir -p "$sdir"
    stream="$sdir/${lane}_$(date -u +%Y%m%dT%H%M%S)_$$.jsonl"
    mapfile -d '' args < <("$py" -m libs.ops.vps_lane_scopes argv "$lane" ${effort:+--effort "$effort"} 2>>"$log")
    if [ "${#args[@]}" -lt 4 ]; then
        echo "=== $lane: SCOPE UNAVAILABLE -- libs/ops/vps_lane_scopes.py built no arguments; run NOT started; verdict UNMEASURED, counts as MISSED ($(date -u)) ===" >> "$log"
        return 2
    fi
    "$@" "$claude_bin" --append-system-prompt "${_DOCTRINE:-}" "${args[@]}" \
        < /dev/null > "$stream" 2>> "$log"
    rc=$?
    rec="$("$py" scripts/record_agent_denials.py --stream "$stream" \
            --ledger data/cro_ai_logs/agent_denials.jsonl --log "$log" \
            --surface vps_agent --lane "$lane" --agent claude --date "$(date -u +%F)" 2>>"$log")"
    if [ $? -eq 0 ]; then
        echo "=== $lane: denials recorded $rec ===" >> "$log"
        rm -f "$stream"
    else
        echo "=== $lane: refusals UNMEASURED -- the recorder could not read $stream (kept); counts as MISSED: $rec ===" >> "$log"
    fi
    return "$rc"
}
