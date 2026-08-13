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

# --- GLOBAL BRAIN MUTEX (2026-07-30) ---
# ONE claude brain at a time, desk-wide. Every organ launcher calls this immediately after
# sourcing this file and BEFORE brain_auth_check, so a deferred organ costs ZERO quota and
# writes no log file (it looks like "not run yet", which is the truth, not like a death).
#
# WHY THIS DID NOT EXIST AND HAD TO. Mutual exclusion lived only in the CRON LINES, and each
# organ carried its OWN lock path (/tmp/cro_ai.cron.lock, /tmp/deep_sweep.lock, ...). So
# cro_ai could not overlap cro_ai -- but cro_ai could overlap deep_sweep, and NO lock covered
# the other launch paths at all: organ_catchup's bare Popen, the systemd timers, a manual fire.
# organ_catchup's own "field busy" guard is a check-then-act race: it samples the field, then
# spawns, and anything launched in between is invisible to it.
# MEASURED 2026-07-30: catchup re-fired deep_sweep at 17:00:03 (its log line) and the CRO brain
# started at 17:00:20 -- two full --effort max brains on one working tree and one quota.
# Observed damage, not theoretical: scripts/max_audit.py mutated underneath a read in progress,
# and `git status` went from 4 dirty files to clean mid-cycle -- one agent committed a working
# tree it did not author. That contention is also the quota-famine engine behind the 7
# stub-deaths/48h and the 12 lost cycles: brains drain the shared pool in parallel, both die,
# more organs fall owed, and catchup then fires more of them.
#
# flock on a HELD FD, never a lockfile-with-pid: the KERNEL drops it when the holder dies, so a
# crashed / OOM-killed / quota-killed brain can never leave a stale lock that starves the desk.
# Non-blocking -- losing the race is NORMAL, not a failure (exit 0, so systemd and cron do not
# mark it failed and thrash). organ_catchup re-fires owed organs every 5 min, so the loser
# simply resumes in the next free window.
# FALSIFIER: if brain_mutex.log shows the daily CRO cycle repeatedly deferred behind long
# digs (starvation rather than protection), this needs organ priority, not a plain mutex.
brain_mutex() {
    if [ "${BRAIN_DRY_RUN:-0}" = "1" ]; then return 0; fi   # CI shell-hygiene path: no real lock
    local name="${1:-brain}"
    # append-mode open: must NOT truncate, or we would erase the current holder's identity
    exec 9>>"/tmp/quant_brain.lock" 2>/dev/null || return 0  # cannot lock -> never block the desk
    if ! flock -n 9; then
        mkdir -p /home/quant/quant-platform/data/cro_ai_logs 2>/dev/null || true
        echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $name DEFERRED -- brain mutex held by $(cat /tmp/quant_brain.owner 2>/dev/null || echo unknown)" \
            >> /home/quant/quant-platform/data/cro_ai_logs/brain_mutex.log 2>/dev/null || true
        exit 0
    fi
    echo "$name pid=$$ since=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > /tmp/quant_brain.owner 2>/dev/null || true
    return 0
}

# --- D3 self-healing (founders directive, principal 2026-07-19) ---
_brain_page() {
    # page the principal via the desk pager topic (ntfy.sh); never fails the caller
    local topic
    topic="$(python3 -c "import json;d=json.load(open('/home/quant/quant-platform/data/secrets/ntfy.json'));print(d.get('topic') or d.get('ntfy_topic') or '')" 2>/dev/null)"
    if [ -n "$topic" ]; then
        curl -fsS -m 10 -H "Title: BRAIN" -H "Priority: high" -H "Tags: robot" \
            -d "$1" "https://ntfy.sh/$topic" >/dev/null 2>&1 || true
    fi
    return 0
}
brain_auth_check() {
    # Cheap auth self-test at cycle start: fail LOUD (page), never silently no-op.
    # MODEL FALLBACK CHAIN (principal 2026-07-24): a STARVED MODEL must never kill the organ.
    # fable-5 draws a metered credit pool; on exhaustion we walk _BRAIN_MODEL_CHAIN to the next
    # model (opus-5, then opus-4-8 -- both on the Max subscription seat) and only then try the
    # metered API key. Tonight every organ died out-of-credits because no model fallback existed.
    # SEAT-AWARE (principal 2026-08-12). An organ on the miner seat exports _ORGAN_MODEL_CHAIN
    # (via brain_seat below) before calling this; everything else walks the default Opus chain.
    # Reading the override HERE rather than in each organ is what stops the seat policy drifting
    # per-script the way the model chain itself drifted across three files before 07-30.
    local out m _chain _head
    _chain="${_ORGAN_MODEL_CHAIN:-${_BRAIN_MODEL_CHAIN:-claude-opus-5 claude-opus-4-8 claude-fable-5}}"
    # PAGE AGAINST THIS ORGAN'S OWN HEAD, not the brain chain's. Comparing a miner (correct head
    # fable-5) against the default head (opus-5) would fire "primary starved" on EVERY miner run
    # -- a pager storm that trains the principal to ignore the one alert that means a pool died.
    _head="${_chain%% *}"
    for m in $_chain; do
        export ANTHROPIC_MODEL="$m"
        out="$(claude -p 'Reply with exactly: PING-OK' --dangerously-skip-permissions 2>&1 | tail -3)"
        if printf '%s' "$out" | grep -q "PING-OK"; then
            if [ "$m" != "$_head" ]; then
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
# SINGLE SOURCE (2026-07-30): the chain lives in ops/model_chain.env, generated by
# scripts/run_model_upgrade.py, which auto-adopts a newer flagship with no human in the loop. It
# was hardcoded in THREE files until today, so any change -- including an automatic upgrade --
# would update one and leave two stale, and organs would silently disagree about what they run.
# The literals below are the FALLBACK, kept so a missing/corrupt chain file is a downgrade rather
# than an outage: an organ with no model at all is the worse failure.
if [ -f /home/quant/quant-platform/ops/model_chain.env ]; then
    . /home/quant/quant-platform/ops/model_chain.env
fi
export ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-claude-opus-5}"  # primary = OPUS 5 (principal 2026-08-12). Fable is no longer the global head: it is PINNED to the miner seat below.
# MODEL ROUTING POLICY (principal 2026-08-12, supersedes the 2026-07-30 single-chain ordering):
# "do opus 5 for all things always instead of fable except for miners locally -- miners, data,
#  all similar families do fable."
#
# TWO SEATS, SPENT IN PARALLEL:
#   _BRAIN_MODEL_CHAIN  opus-5 -> opus-4-8 -> fable-5   (everything: CRO, capability hunt,
#                                                        recommendation worker, deep sweep,
#                                                        audits, interactive sessions)
#   _MINER_MODEL_CHAIN  fable-5 -> opus-5 -> opus-4-8   (the mining / data-collection family;
#                                                        membership is DATA in
#                                                        libs.ops.model_chain.MINER_ORGANS)
#
# WHY THIS IS THE RIGHT SPLIT, not merely the ordered one. Fable and Opus are PEERS at the
# flagship tier, so this is a POOL decision rather than a capability one. Fable draws a metered
# credit pool that CAN exhaust; opus-5/opus-4-8 sit on the Max subscription seat. Under the old
# single fable-first chain BOTH families queued behind one pool, so whichever drained first
# starved everything -- which is literally what happened on 07-24 (one max-effort frontier dig
# drained fable at 23:07-23:29 and every organ died, because no fallback chain existed yet).
#
# The miners take the metered pool because their work is RESUMABLE BY CONSTRUCTION: a region
# without a real log today is re-dug on the next rotation invocation, so a mid-dig credit death
# costs a retry and nothing else. The reasoning organs are not resumable in that sense -- a
# starved CRO or capability-hunt cycle is a LOST cycle -- so they take the seat that does not run
# out. The 07-24 and 07-30 evidence above is preserved, not erased: it is why the walk-down exists
# on both chains, and brain_auth_check still PAGES the moment either steps past its head.
export _BRAIN_MODEL_CHAIN="${_BRAIN_MODEL_CHAIN:-claude-opus-5 claude-opus-4-8 claude-fable-5}"
export _MINER_MODEL_CHAIN="${_MINER_MODEL_CHAIN:-claude-fable-5 claude-opus-5 claude-opus-4-8}"

# brain_seat <organ-label> -- put THIS organ on its policy seat before brain_auth_check.
# Resolution is delegated to libs.ops.model_chain.chain_for() so shell and python agree by
# construction; if python is unavailable the organ keeps the default chain rather than guessing,
# because a mis-seated organ on Opus costs headroom while one mis-seated onto Fable can silently
# drain the pool the miners depend on. The cheaper mistake is the fallback.
brain_seat() {
    local organ="${1:?organ label required}" chain
    chain="$(PYTHONPATH=/home/quant/quant-platform python3 -c \
        'import sys; from libs.ops.model_chain import chain_for; print(" ".join(chain_for(sys.argv[1])))' \
        "$organ" 2>/dev/null)" || chain=""
    if [ -n "$chain" ]; then
        export _ORGAN_MODEL_CHAIN="$chain"
        export ANTHROPIC_MODEL="${chain%% *}"
    fi
    return 0
}

# LAW GATE AT ORGAN SPAWN (L1.37, principal order 2026-07-31 "enforced 24/7 with every
# interaction"). Every organ sources this file, so this is the one place that runs before ALL of
# them. The FAST gate only (~1s, no full battery): the sealed constitutional core is intact, and
# the doctrine still carries every law family. Those are the two conditions under which an organ
# must never start -- an organ running on a tampered core, or one that will never be told the
# laws it is meant to obey, is worse than no organ at all.
# NON-BLOCKING BY DESIGN: it PAGES and marks the breach rather than killing the cycle. A gate
# that silently stops the whole desk on a governance fault would trade a research outage for a
# paperwork fault, and the outage is the bigger loss (L1.2). The breach is loud, dated, and in
# the artifact -- never silent.
_law_gate_fast() {
    local out
    out="$(.venv/bin/python /home/quant/quant-platform/scripts/run_law_gate.py --fast 2>&1)" || {
        _brain_page "LAW GATE BREACH at organ spawn: $(printf '%s' "$out" | tail -2 | head -c 200)"
        printf '%s\n' "$out" >&2
        echo "LAW-GATE-BREACH $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            >> /home/quant/quant-platform/data/law_gate_breaches.log 2>/dev/null || true
    }
    return 0
}
_law_gate_fast

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

# DESK MEMORY (2026-08-01): the lessons this desk has PAID for -- ranked by what ignorance cost
# x how many times it has had to re-learn them -- appended to the same injection every organ
# already receives. This is the ONLY thing on the desk that compounds across sessions: model
# weights do not update between runs, so a lesson lives exactly as long as something reads it at
# runtime. docs/institutional_knowledge.md held 67,802 chars of hard-won incident knowledge and
# was cited only from Python comments -- it reached no organ, ever, and therefore changed no
# behaviour, ever. This closes that path.
#
# HARD-BUDGETED at 12k chars by libs/research/desk_memory.py, deliberately: doctrine reached
# 95,204 chars (6.0x max_audit's own 16k dilution threshold) precisely because nothing ever said
# no. Adding lessons past the budget DISPLACES weaker ones rather than growing the context, so
# organs get smarter over time without getting slower. Overflow goes to stderr, never silently.
#
# `|| true` is load-bearing: a broken memory layer must never stop an organ from running. The
# corpus is an improvement to a working organ, not a precondition for one.
_MEMORY="$(cd /home/quant/quant-platform 2>/dev/null && \
    .venv/bin/python scripts/learn.py render 2>/dev/null || true)"
_DOCTRINE="${_DOCTRINE}
${_MEMORY}"

# --- L1.28b(d) CONVERSION ACTUATOR --------------------------------------------------------------
#
# THE SAME DEFECT AS THE §33 BLOCK ABOVE, ONE LAW OVER. L1.28b(d) says the backlog "FLIPS the next
# audit/brain window from finding to fixing -- when data/conversion_status.json says repair_mode".
# check_conversion.py computed that flag on every run and published it; a grep for its consumers
# on 2026-08-05 found exactly one, run_max_push.py:249, where it selects a different ADVICE
# STRING. Nothing flipped. The remedy was legislated, fenced, and had no actuator -- which is why
# `rec-ledger-backlog` recurred 3x in 5.2d over 13 sightings while each cycle dutifully disposed
# the specific rows it named. Servicing the items a queue names does not drain a queue whose
# arrival rate exceeds its service rate (measured that day: 54.4/day in, 30.0/day out).
#
# INJECTED HERE, INTO `_DOCTRINE`, FOR THE REASON L1.36 GIVES: a law that never reaches an organ
# cannot change behaviour however well it is fenced. Every organ sources this file, so present and
# future organs inherit the duty and the next one cannot be written without it.
#
# IT ADDS WORK AND REMOVES NONE. libs/ops/repair_mode.py has no vocabulary for stopping -- the
# excitation.py precedent (L1.45) -- and its emitted text is asserted against a banned-verb list
# by tests/governance/test_repair_actuator.py. L1.28b(f) is untouched and carried verbatim INTO
# the block: collectors, recorders, miners, diggers, screens, forward clocks and fences run at
# FULL CADENCE regardless. When the artifact says ARRIVALS-COLLAPSED the block says FIND HARDER,
# never drain -- the opposite defect deserves the opposite duty.
#
# `|| true` matches _MEMORY and is load-bearing for the same reason: L1.37's spawn gate PAGES, it
# does not KILL. A governance fault must never silently stop the desk (L1.2). Unlike _MEMORY,
# though, an unreadable artifact is not silence here -- repair_mode.duty() returns UNMEASURED,
# which emits a duty of its own, so a broken conversion fence reads as OWING WORK rather than as
# nothing owing (L1.28a). Only a dead interpreter yields an empty string.
_REPAIR_DUTY="$(cd "$_BRAIN_ROOT" 2>/dev/null && \
    .venv/bin/python -m libs.ops.repair_mode 2>/dev/null || true)"
if [ -n "$_REPAIR_DUTY" ]; then
    _DOCTRINE="${_DOCTRINE}

${_REPAIR_DUTY}"
fi

# --- PART III-31 EDGE INTAKE ACTUATOR -----------------------------------------------------------
#
# THE SAME SHAPE OF DEFECT AS THE BLOCK ABOVE, ONE LAW OVER (2026-08-13, found while tracing why
# ARRIVALS-COLLAPSED wasn't draining). libs.research.edge_intake.next_batch() (gate item 31) is
# named in its own module docstring as "the real consumer" for NEXT_BATCH_TEST rows -- but its
# only caller anywhere in the tree was scripts/run_edge_intake.py, which printed the batch to
# data/cro_ai_logs/edge_intake.log inside a once-daily cron run and nothing else ever read that
# log. admit() -- the function that marks a row genuinely picked up -- had exactly one caller in
# the whole repo: its own unit test. A queue whose "scheduled" state has a consumer that writes
# only to a file nobody opens is the graveyard the module's own docstring says item 31 prevents.
#
# INJECTED HERE for the identical reason L1.36 gives the repair-mode block above: a duty that
# never reaches an organ cannot change behaviour however well it is fenced. Every organ sources
# this file, so present and future organs inherit it.
#
# ADDS WORK, REMOVES NONE, NEVER AUTO-ADMITS. libs.research.edge_intake.intake_duty() does not
# call admit() itself -- marking a row admitted without a real experiment behind it would shrink
# the backlog by pretending, which is the principal's own standing instruction (2026-08-13): "do
# not delete, suppress, or deprioritize candidates just to make the backlog look smaller."
_INTAKE_DUTY="$(cd "$_BRAIN_ROOT" 2>/dev/null && \
    .venv/bin/python -m libs.research.edge_intake 2>/dev/null || true)"
if [ -n "$_INTAKE_DUTY" ]; then
    _DOCTRINE="${_DOCTRINE}

${_INTAKE_DUTY}"
fi
