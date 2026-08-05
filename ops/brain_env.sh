# Shared brain auth environment -- sourced by EVERY claude-invoking script
# (run_cro_ai.sh + all 4 digger scripts). See ledgers #101/#102.
#
# Auth precedence (first file found wins; both 600-perm, gitignored, read at spawn
# time -- NEVER systemd Environment=, which is /proc-visible):
#   1. data/secrets/anthropic_api_key      -> ANTHROPIC_API_KEY (Option A, DORMANT
#      escape hatch: metered Console billing if the Max pool ever starves the brain)
#   2. data/secrets/claude_oauth_token     -> CLAUDE_CODE_OAUTH_TOKEN (Option B,
#      CURRENT: `claude setup-token` output from the principal's Max account.
#      setup-token does NOT update ~/.claude/.credentials.json -- the token only
#      works via this env var, which also outranks any stale stored login)
#   3. neither file -> whatever OAuth login exists in ~/.claude (legacy fallback)
export PATH="$HOME/.local/bin:$PATH"
# Repo root. Overridable so the readiness checker and its tests can exercise these helpers
# without pretending to be the VPS. Existing absolute paths below are left alone deliberately:
# they demonstrably work on the machine that runs them, and rewriting them to chase tidiness
# would put every organ's auth at risk to fix nothing.
_BRAIN_ROOT="${_BRAIN_ROOT:-/home/quant/quant-platform}"
_BRAIN_KEYFILE="/home/quant/quant-platform/data/secrets/anthropic_api_key"
_BRAIN_TOKENFILE="/home/quant/quant-platform/data/secrets/claude_oauth_token"
if [ -f "$_BRAIN_KEYFILE" ]; then
    ANTHROPIC_API_KEY="$(cat "$_BRAIN_KEYFILE")"
    export ANTHROPIC_API_KEY
elif [ -f "$_BRAIN_TOKENFILE" ]; then
    CLAUDE_CODE_OAUTH_TOKEN="$(tr -d '[:space:]' < "$_BRAIN_TOKENFILE")"
    export CLAUDE_CODE_OAUTH_TOKEN
fi

# --- D3 self-healing (founders directive, principal 2026-07-19) ---
_brain_page() {
    # page the principal via the desk pager topic (ntfy.sh); never fails the caller
    #
    # PER-MESSAGE DEDUPE (2026-08-05). This bypassed run_alerts' entire dedupe discipline -- no
    # state, no throttle -- and sent 191 near-identical "LAW GUARD: DOCTRINE-GAP" pages in 24h,
    # ~1/min for hours. 180 of them landed AFTER the 22:03 principal page that asked four
    # decisions gating the book, burying it. Two costs, both already paid once: a pager that
    # cries wolf is worse than none (run_alerts.py:36-38), and sustained volume on free ntfy.sh
    # is exactly what exhausted the quota 07-11 -> 07-16 and silently dropped EVERY page for five
    # days including a dead-man fire (run_alerts.py:332-335). Same 6h window run_alerts uses for
    # slow-moving conditions; identical text inside it is dropped, changed text pages immediately.
    local topic stampdir stamp
    topic="$(python3 -c "import json;d=json.load(open('/home/quant/quant-platform/data/secrets/ntfy.json'));print(d.get('topic') or d.get('ntfy_topic') or '')" 2>/dev/null)"
    [ -n "$topic" ] || return 0
    stampdir="/home/quant/quant-platform/data/.brain_page_stamps"
    mkdir -p "$stampdir" 2>/dev/null || true
    stamp="$stampdir/$(printf '%s' "$1" | sha1sum | cut -c1-16)"
    # -mmin -360 = pushed within the last 6h; suppress the repeat, keep the caller's contract
    if [ -n "$(find "$stamp" -mmin -360 2>/dev/null)" ]; then
        return 0
    fi
    if curl -fsS -m 10 -H "Title: BRAIN" -H "Priority: high" -H "Tags: robot" \
        -d "$1" "https://ntfy.sh/$topic" >/dev/null 2>&1; then
        : > "$stamp" 2>/dev/null || true    # stamp ONLY on success, so a failed page retries
    fi
    # prune stamps older than a week so the dir cannot grow without bound
    find "$stampdir" -type f -mmin +10080 -delete 2>/dev/null || true
    return 0
}
# RESET-AWARE RETRY (work order run-reset-aware-retry). Seconds to wait for a session limit's
# STATED reset time, or empty when there is nothing safe to wait for.
#
# WHY THIS EXISTS. Scheduled organs die at second zero on a session limit and the whole slot is
# lost -- 10 organ runs died at birth in 48h on this box. The CLI tells us exactly when the wall
# lifts ("You've hit your session limit - resets 1am (UTC)"), and the diggers/miners fire
# post-cycle, so a single reset-aware sleep recovers most of them instead of skipping a day.
#
# PURE TEXT -> NUMBER, deliberately: it is the whole decision, and keeping it free of side effects
# means it can be smoke-tested exhaustively without burning a single call. Prints nothing when the
# message has no parseable reset, when the wait exceeds the cap, or when the clock is unusable --
# the caller then pages exactly as it did before, so an unparseable message can only ever leave
# behaviour unchanged. NEVER an unbounded sleep: the cap defaults to 3600s, half of systemd's
# TimeoutStartSec=7200, so a woken organ still has an hour to do real work.
brain_reset_wait_s() {
    local text="$1" cap="${2:-${_BRAIN_RESET_CAP_S:-3600}}"
    local frag hh mm ampm now target wait
    frag="$(printf '%s' "$text" \
        | grep -oiE 'resets[[:space:]]+[0-9]{1,2}(:[0-9]{2})?[[:space:]]*(am|pm)' | head -1)"
    [ -n "$frag" ] || return 0
    hh="$(printf '%s' "$frag" | grep -oE '[0-9]{1,2}' | head -1)"
    mm="$(printf '%s' "$frag" | grep -oE ':[0-9]{2}' | head -1 | tr -d ':')"
    ampm="$(printf '%s' "$frag" | grep -oiE '(am|pm)' | head -1 | tr '[:upper:]' '[:lower:]')"
    [ -n "$hh" ] && [ -n "$ampm" ] || return 0
    [ -n "$mm" ] || mm=00
    hh=$((10#$hh)); mm=$((10#$mm))
    [ "$hh" -le 12 ] && [ "$mm" -le 59 ] || return 0
    # 12am is midnight and 12pm is noon -- the two cases a naive +12 gets exactly backwards.
    [ "$ampm" = "pm" ] && [ "$hh" -ne 12 ] && hh=$((hh + 12))
    [ "$ampm" = "am" ] && [ "$hh" -eq 12 ] && hh=0
    now="$(date -u +%s)" || return 0
    target="$(date -u -d "today $(printf '%02d:%02d' "$hh" "$mm")" +%s 2>/dev/null)" || return 0
    [ -n "$target" ] || return 0
    # A reset already past today means tomorrow -- which is ~23h away and so will exceed the cap
    # and correctly decline to wait, rather than sleeping through the next scheduled slot.
    [ "$target" -le "$now" ] && target=$((target + 86400))
    wait=$((target - now + 60))            # +60s so we wake just AFTER the wall lifts, not on it
    [ "$wait" -gt 0 ] && [ "$wait" -le "$cap" ] || return 0
    printf '%s' "$wait"
}

brain_auth_check() {
    # Cheap auth self-test at cycle start: fail LOUD (page), never silently no-op.
    # MODEL FALLBACK CHAIN (principal 2026-07-24): a STARVED MODEL must never kill the organ.
    # fable-5 draws a metered credit pool; on exhaustion we walk _BRAIN_MODEL_CHAIN to the next
    # model (opus-5, then opus-4-8 -- both on the Max subscription seat) and only then try the
    # metered API key. Tonight every organ died out-of-credits because no model fallback existed.
    local out m
    for m in ${_BRAIN_MODEL_CHAIN:-claude-fable-5 claude-opus-5 claude-opus-4-8}; do
        export ANTHROPIC_MODEL="$m"
        out="$(claude -p 'Reply with exactly: PING-OK' --dangerously-skip-permissions 2>&1 | tail -3)"
        if printf '%s' "$out" | grep -q "PING-OK"; then
            if [ "$m" != "${_BRAIN_MODEL_CHAIN%% *}" ]; then
                _brain_page "model fallback ACTIVE: primary starved, organs running on $m"
            fi
            return 0
        fi
    done
    if printf '%s' "$out" | grep -qiE "limit|usage credits" && [ -f "$_BRAIN_KEYFILE" ]; then
        unset CLAUDE_CODE_OAUTH_TOKEN
        ANTHROPIC_API_KEY="$(cat "$_BRAIN_KEYFILE")"
        export ANTHROPIC_API_KEY
        out="$(claude -p 'Reply with exactly: PING-OK' --dangerously-skip-permissions 2>&1 | tail -3)"
        if printf '%s' "$out" | grep -q "PING-OK"; then
            _brain_page "Brain hit subscription quota -- FELL BACK to metered API key; cycles continue on metered spend"
            return 0
        fi
    fi
    # LAST RESORT BEFORE GIVING THE SLOT AWAY: if the failure names its own reset time, wait for
    # it once and re-run the whole chain. Strictly after every existing fallback has been tried,
    # so this can only convert an abort into an attempt -- never pre-empt a model fallback that
    # would have worked immediately. Guarded to ONE retry per process: the recursive call sees
    # _BRAIN_RESET_RETRIED=1 and falls straight through to the page, so a wall that does not
    # actually lift costs one wait, not a loop.
    if [ "${_BRAIN_RESET_RETRIED:-0}" != "1" ]; then
        local _wait
        _wait="$(brain_reset_wait_s "$out")"
        if [ -n "$_wait" ]; then
            _BRAIN_RESET_RETRIED=1
            _brain_page "session limit -- sleeping ${_wait}s to the stated reset, then ONE retry"
            sleep "$_wait"
            brain_auth_check && return 0
            return 1
        fi
    fi
    _brain_page "BRAIN AUTH DOWN, cycle aborted: $(printf '%s' "$out" | head -1 | cut -c1-140)"
    return 1
}

# Model policy (principal 2026-07-20): the brain, diggers, and audits run the most
# capable model available -- Claude Fable 5 first. If the CLI/plan rejects it, flip
# this line to claude-opus-4-8 (failures surface via brain_auth_check pages + noop
# alerts, never silently). EFFORT: set explicitly per-invocation via --effort xhigh in each
# organ script (was an UNVERIFIED assumption of 'CLI-managed max default' until 2026-07-21).
# xhigh = documented best for agentic/coding work on Opus 4.8; max is reserved for
# risk-path depth reviews (correctness over cost) since max can overthink general work.
export ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-claude-opus-5}"  # primary; _BRAIN_MODEL_CHAIN below auto-falls-back at runtime (principal 2026-07-24: fable starves -> opus-5). Fable draws a metered credit pool that CAN exhaust; opus-5/opus-4-8 sit on the Max subscription seat.
# EVIDENCE 2026-07-24: one max-effort dig drained the whole fable-5 METERED pool
# (frontier-en 23:07-23:29 -> out-of-credits). Max-seat models lead; fable is last.
export _BRAIN_MODEL_CHAIN="claude-opus-5 claude-opus-4-8 claude-fable-5"

# PRINCIPAL DOCTRINE (2026-07-21): the desk's permanent max-ROI personality, injected
# into every claude organ via --append-system-prompt. Read once here; every organ script
# sources this file, so all present AND future organs inherit it. Read at spawn time.
#
# IT WAS A SILENT FAIL-OPEN. The path was hardcoded and the read was `2>/dev/null`, so ANY change
# to where the repo lives -- a move, a rename, a second checkout, a restore onto a fresh box --
# left `_DOCTRINE` empty and every organ ran with an empty `--append-system-prompt`, undirected,
# forever, with nothing in any log to say so. The desk's "permanent max-ROI personality" was one
# `mv` away from silently ceasing to exist. Found 2026-08-03 by scripts/check_organ_readiness.py
# on its first run, which is what a pre-flight is for.
#
# `_BRAIN_ROOT` defaults to the same absolute path, so the VPS behaviour is byte-identical; what
# changes is that the failure is now LOUD and the file is findable from a relocated checkout.
_DOCTRINE="$(cat "$_BRAIN_ROOT/ops/principal_doctrine.txt" 2>/dev/null)"
if [ -z "$_DOCTRINE" ]; then
    printf 'brain_env: DOCTRINE EMPTY (%s) -- every organ sourcing this would run undirected\n' \
        "$_BRAIN_ROOT/ops/principal_doctrine.txt" >&2
fi

# --- §33 CONVERSION PRIORITY -------------------------------------------------------------------
#
# THIS WAS COMPUTED AND THROWN AWAY IN ALL SIX DIG SCRIPTS. Each one ran
#
#     _MINE_PRIORITY="$(.venv/bin/python scripts/mine_gate.py 2>/dev/null || true)"
#
# under fourteen lines of comment explaining that the result is "prepended to this run's
# instructions so the dig spends its FIRST effort converting" -- and then invoked claude with
# `-p "$(cat ops/<organ>_dig_prompt.txt)"`, which does not reference the variable. The gate was
# real, its output was well-formed, and nothing consumed it. Every dig therefore mined new ground
# while the conversion backlog it was supposed to work went untouched, which is precisely what
# `mine-conversion-unbacked` and `mine-law-unjudgeable` have been reporting.
#
# It is fixed HERE rather than six times, for the same reason `_DOCTRINE` lives here: every organ
# script sources this file, so present and future organs inherit it and the next one cannot be
# written without it.
#
# THE GATE'S FAILURE IS NOT SILENT ANY MORE. The old `2>/dev/null || true` meant a missing venv, a
# broken import or a traceback all produced an empty string indistinguishable from "nothing owes a
# disposition" -- fail-open, on the organ whose whole job is to stop the desk mining faster than it
# converts. A failure now emits a visible marker into the prompt so the dig, the log and the
# operator all see that the conversion duty could not be computed.
mine_priority() {
    local py out rc
    for py in "$_BRAIN_ROOT/.venv/bin/python" .venv/bin/python python3; do
        [ -x "$py" ] || command -v "$py" >/dev/null 2>&1 || continue
        out="$("$py" "$_BRAIN_ROOT/scripts/mine_gate.py" 2>&1)"; rc=$?
        if [ $rc -eq 0 ]; then
            printf '%s' "$out"
            return 0
        fi
    done
    printf '%s' "[§33] CONVERSION GATE UNAVAILABLE -- scripts/mine_gate.py could not be run on \
this host, so the conversion backlog for this run is UNKNOWN. Treat that as owing work, not as \
nothing owing: check docs/research/ for items claiming a terminal disposition without a backing \
artifact before mining new ground. (last error: ${out:-no interpreter found})"
    return 1
}

# Prompt actually handed to an organ: the conversion duty FIRST, then the organ's own brief.
# Order is the point -- the gate's instruction is to spend this run's first effort converting.
dig_prompt() {
    local brief prio
    brief="$(cat "$1")"
    prio="$(mine_priority)"
    if [ -n "$prio" ]; then
        printf '%s\n\n%s' "$prio" "$brief"
    else
        printf '%s' "$brief"
    fi
}

# BRAIN_DRY_RUN=1 -- PROVE AN ORGAN CAN FIRE WITHOUT SPENDING A SINGLE CREDIT.
#
# `run_cro_ai.sh` already had this; the six dig scripts did not, which meant the only way to find
# out whether a dig would work was to spend credits and read the log afterwards. That is the wrong
# order when credits are the binding constraint: a missing prompt file, an empty doctrine or a
# broken conversion gate should be discoverable for free.
#
# It deliberately runs BEFORE brain_auth_check, because that check itself burns a `claude -p PING`
# per model in the fallback chain. A pre-flight that costs credits is not a pre-flight.
dig_dry_run() {                       # $1 = organ label, $2 = prompt file
    [ "${BRAIN_DRY_RUN:-0}" = "1" ] || return 1
    local p rc=0
    if [ ! -r "$2" ]; then
        printf 'DRY-RUN %s: FAIL -- prompt file %s missing or unreadable\n' "$1" "$2"
        return 0
    fi
    p="$(dig_prompt "$2")"
    printf 'DRY-RUN %s: prompt %s chars (brief %s, doctrine %s) model=%s\n' \
        "$1" "${#p}" "$(wc -c < "$2" | tr -d ' ')" "${#_DOCTRINE}" "${ANTHROPIC_MODEL:-unset}"
    case "$p" in
        "[§33]"*) printf '  conversion duty PRESENT and leads the prompt\n' ;;
        *)        printf '  FAIL: conversion duty absent -- the dig would mine without converting\n'
                  rc=1 ;;
    esac
    [ -n "$_DOCTRINE" ] || { printf '  FAIL: doctrine is EMPTY -- organ would run undirected\n'
                             rc=1; }
    [ "$rc" = 0 ] && printf '  READY\n'
    return 0
}
