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
export ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-claude-fable-5}"  # primary = FABLE 5 (principal 2026-07-30); _BRAIN_MODEL_CHAIN below walks to opus-5 on exhaustion and PAGES when it does. Fable draws a pool that CAN exhaust; opus-5/opus-4-8 sit on the Max subscription seat and carry the rest of the week.
# MODEL ROUTING POLICY (principal 2026-07-30, supersedes the 2026-07-24 ordering):
# "every claude cycle, mining, audit, everything uses FABLE 5 MAXIMUM always initially until the
# full week's sessions of it end, then only OPUS 5 after that in the week."
# So the chain is FABLE-FIRST and the walk-down IS the policy: fable is consumed to exhaustion,
# then opus-5 carries the rest of the week, then opus-4-8. No capability is lost on a downgrade --
# only model availability changes (effort stays --effort xhigh/max per organ).
#
# WHY REVERSING THIS IS NOW SAFE, and it was not on 07-24. The old order existed for a measured
# reason: one max-effort dig drained the whole fable-5 metered pool (frontier-en 23:07-23:29 ->
# out-of-credits) and EVERY organ died, because at that moment NO FALLBACK CHAIN EXISTED. The
# chain above is that fallback: brain_auth_check walks it at cycle start, and pages
# "model fallback ACTIVE: primary starved" the moment it steps past the primary. Exhaustion is
# therefore a logged, paged, self-healing transition instead of an outage -- which is precisely
# the behaviour the principal's policy assumes. The 07-24 evidence is preserved above, not erased:
# it explains the failure this chain now absorbs.
# NOTE the frontier miners already ran fable-first via their own export; this makes the global
# default agree with them instead of contradicting them (the miners were right).
export _BRAIN_MODEL_CHAIN="${_BRAIN_MODEL_CHAIN:-claude-fable-5 claude-opus-5 claude-opus-4-8}"

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
_DOCTRINE="$(cat /home/quant/quant-platform/ops/principal_doctrine.txt 2>/dev/null)"

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
