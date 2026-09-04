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
        local msg
        msg="$(date -u +%Y-%m-%dT%H:%M:%SZ) $name DEFERRED -- brain mutex held by $(cat /tmp/quant_brain.owner 2>/dev/null || echo unknown)"
        echo "$msg" >> /home/quant/quant-platform/data/cro_ai_logs/brain_mutex.log 2>/dev/null || true
        # The deferral must ALSO land in the ORGAN'S OWN log (callers set BRAIN_MUTEX_LOGFILE to
        # their attempt stub): organ_catchup.organ_owed treats "no logs today" as "timer has not
        # fired -- not ours to start", so a deferral that leaves no per-organ log makes the organ
        # invisible to its own retry loop. Measured 2026-08-11: all 7 frontier regions deferred
        # behind the 14:45 brain run at 15:00, left zero logs, and catchup reported
        # "nothing owed" while the organ-never fence reported them dead for 36h.
        [ -n "${BRAIN_MUTEX_LOGFILE:-}" ] && echo "$msg" >> "$BRAIN_MUTEX_LOGFILE" 2>/dev/null
        exit 0
    fi
    echo "$name pid=$$ since=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > /tmp/quant_brain.owner 2>/dev/null || true
    return 0
}

# --- MEMORY GATE (2026-08-31) ---
# A seat that dies between its attempt header and its first claude line is a SILENT death --
# 21 stubs in 7 days, cgroup oom_kill counter at 912, 0 swap on 3.8GB. The launcher writes the
# header, then brain_mutex, then brain_auth_check; the probes there spawn claude, and an OOM
# kill of the whole group leaves only the 58-byte header. Hunting harder cannot fix a box that
# cannot hold the launch, so a launcher must DEFER cleanly first instead of dying silently.
# Grace value in MB: a 158-line stub of failed-claude + the seat's own python. Below ~500MB
# available an --effort max seam can push the box over the cliff; defer to the next catchup
# tick (5 min) and it resumes the moment memory frees.
_BRAIN_MEM_FLOOR_MB="${_BRAIN_MEM_FLOOR_MB:-500}"
brain_mem_gate() {
    local avail_mb
    avail_mb="$(awk '/MemAvailable/ {printf "%d", $2/1024}' /proc/meminfo 2>/dev/null)"
    [ -n "$avail_mb" ] || return 0          # cannot read -> do not block, never block the desk
    if [ "$avail_mb" -lt "$_BRAIN_MEM_FLOOR_MB" ]; then
        [ -n "${BRAIN_MUTEX_LOGFILE:-}" ] && \
            echo "=== ${BRAIN_ORGAN:-brain} MEMORY-STARVED only ${avail_mb}MB available DEFERRED -- box at ${_BRAIN_MEM_FLOOR_MB}MB floor; organ_catchup re-fires ===" \
            >> "$BRAIN_MUTEX_LOGFILE" 2>/dev/null || true
        printf 'brain_mem_gate: %d MB available < %s MB floor -- deferring\n' \
            "$avail_mb" "$_BRAIN_MEM_FLOOR_MB" >&2
        return 1
    fi
    printf 'brain_mem_gate: %d MB available >= %s MB floor -- go\n' \
        "$avail_mb" "$_BRAIN_MEM_FLOOR_MB" >&2
    return 0
}

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

# --- BRAIN QUOTA MEMO (2026-08-26) -----------------------------------------------------------
# THE WALL IS RE-DISCOVERED BY EVERY ORGAN, ONE PROBE AT A TIME, AND NEVER WRITTEN DOWN.
#
# MEASURED, not theorised (scripts/check_seat_launch_yield.py --days 7, run 2026-08-26T07:20Z):
# 108 seat launches, 94 billable, 26 produced -- 27.7% yield -- and AUTH_UNAVAILABLE alone
# accounts for 55 of the 94. Every one of those 55 walked the FULL model chain first: a PING per
# model in $_BRAIN_MODEL_CHAIN, then the keyfile branch, then (once) a sleep-to-reset and a
# recursive re-walk. The organ that hit the wall at 15:00 learned the exact reset time, used it
# for one sleep, and threw it away; the organ that fired at 15:10 started from zero and paid for
# the same discovery again. The desk therefore has no answer at all to "when is the brain
# available" -- that is UNMEASURED, which under L1.28a is a real answer and a defect, not a
# clean bill of health.
#
# WHAT THIS ADDS, and deliberately nothing more: the reset stamp brain_reset_wait_s already
# computes is PERSISTED, and brain_auth_check consults it BEFORE spending a probe. It is a memo,
# never a rail:
#   - it can only ever SKIP A PROBE, never skip a dig that would have run (a skipped organ
#     leaves its attempt stub, stays below organ_catchup's success_bytes, and is re-fired by the
#     catchup loop exactly as an auth death is today -- the retry path is unchanged);
#   - it expires by wall clock, is capped at _BRAIN_QUOTA_MEMO_CAP_S so a bad parse cannot
#     silence the desk for a day, and is CLEARED by any successful PING;
#   - BRAIN_IGNORE_QUOTA_MEMO=1 overrides it entirely, so a human or a probe organ is never
#     locked out by the desk's own bookkeeping.
# It is recorded ONLY for genuine limit/credit failures. A missing token or a bad key is not a
# quota event and must keep failing loudly and immediately (that distinction is the whole reason
# the seat-yield fence separates AUTH_UNAVAILABLE from DIED_AT_ATTEMPT).
#
# The jsonl is the point as much as the memo: data/brain_quota_windows.jsonl accrues one row per
# observed open/blocked transition, so a later cycle can schedule seats against a MEASURED quota
# rhythm instead of the current guess. Today the productive hours (05-09 UTC) and the dead ones
# (14, 15, 18, 19) are known only from log forensics done by hand.
# FALSIFIER: if brain_quota_windows.jsonl shows `open` rows recorded inside a window this memo
# was simultaneously reporting blocked, the memo is over-blocking and its cap must shrink.
_BRAIN_QUOTA_MEMO="${_BRAIN_QUOTA_MEMO:-/home/quant/quant-platform/data/brain_quota_state.json}"
_BRAIN_QUOTA_LOG="${_BRAIN_QUOTA_LOG:-/home/quant/quant-platform/data/brain_quota_windows.jsonl}"
_BRAIN_QUOTA_MEMO_CAP_S="${_BRAIN_QUOTA_MEMO_CAP_S:-21600}"   # 6h -- longer than any real window
_BRAIN_QUOTA_SOFT_S="${_BRAIN_QUOTA_SOFT_S:-1200}"            # limit hit, reset time unparseable

# brain_quota_record <open|blocked> <blocked_until_epoch|0> <organ> <reason-text>
brain_quota_record() {
    [ "${BRAIN_DRY_RUN:-0}" = "1" ] && return 0
    BQ_STATE="$1" BQ_UNTIL="${2:-0}" BQ_ORGAN="${3:-brain}" BQ_REASON="${4:-}" \
    BQ_MEMO="$_BRAIN_QUOTA_MEMO" BQ_LOG="$_BRAIN_QUOTA_LOG" \
    python3 - <<'PY' 2>/dev/null || true
import json, os, time
state = os.environ["BQ_STATE"]
until = int(os.environ.get("BQ_UNTIL") or 0)
row = {
    "observed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "observed_at_epoch": int(time.time()),
    "state": state,
    "blocked_until_epoch": until if state == "blocked" else 0,
    "organ": os.environ.get("BQ_ORGAN", "brain"),
    "reason": (os.environ.get("BQ_REASON") or "")[:200],
    "model": os.environ.get("ANTHROPIC_MODEL", ""),
}
memo = os.environ["BQ_MEMO"]
os.makedirs(os.path.dirname(memo), exist_ok=True)
tmp = memo + ".tmp"
with open(tmp, "w", encoding="utf-8") as fh:
    json.dump(row, fh, indent=1)
os.replace(tmp, memo)
# APPEND ONLY ON A TRANSITION. A row per probe would bury the signal under the desk's own
# polling: what a later scheduler needs is when the wall went up and when it came down.
prev = None
try:
    with open(os.environ["BQ_LOG"], encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                prev = line
except OSError:
    pass
prev_state = None
if prev:
    try:
        prev_state = json.loads(prev).get("state")
    except ValueError:
        prev_state = None
if prev_state != state:
    with open(os.environ["BQ_LOG"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
PY
}

# brain_quota_blocked -> 0 (blocked: do not spend a probe), 1 (go)
brain_quota_blocked() {
    [ "${BRAIN_IGNORE_QUOTA_MEMO:-0}" = "1" ] && return 1
    [ "${BRAIN_DRY_RUN:-0}" = "1" ] && return 1
    [ -r "$_BRAIN_QUOTA_MEMO" ] || return 1
    local until now
    until="$(sed -n 's/.*"blocked_until_epoch"[[:space:]]*:[[:space:]]*\([0-9]\{1,\}\).*/\1/p' \
        "$_BRAIN_QUOTA_MEMO" 2>/dev/null | head -1)"
    [ -n "$until" ] || return 1
    case "$until" in (*[!0-9]*) return 1 ;; esac
    now="$(date -u +%s)" || return 1
    [ "$until" -gt "$now" ] || return 1
    # A memo pointing further ahead than any real window is a PARSE FAULT, not a long outage.
    # Distrust it and probe: over-blocking costs digs, and digs are the desk's primary output.
    [ $((until - now)) -le "$_BRAIN_QUOTA_MEMO_CAP_S" ] || return 1
    return 0
}

# How long a successful PING is believed before another organ pays for a fresh one.
# Deliberately short: a quota that closed inside this window costs one organ a wasted attempt,
# which is self-correcting on its next cycle. Longer would risk organs marching into a wall.
_BRAIN_QUOTA_OPEN_TTL_S="${_BRAIN_QUOTA_OPEN_TTL_S:-600}"

# True when another organ measured the quota OPEN recently enough to believe.
#
# THE MEMO WAS ONE-SIDED, AND THE EXPENSIVE HALF WAS MISSING. `brain_quota_blocked` already stops
# an organ probing into a wall someone else measured -- correct, and it saves quota. But the OPEN
# case, which is the normal one, was never cached: every organ spawned its own
# `claude -p 'Reply with exactly: PING-OK'` to re-learn what the previous organ learned minutes
# earlier. That probe is a FULL CLAUDE PROCESS, measured at ~175MB, and brain_env.sh is sourced by
# eight-plus organ scripts on their own timers.
#
# MEASURED 2026-09-04: the box sat at 62MB available, below its own 300MB OOM floor; the research
# gauntlet needs 1,200MB and had not started for 15.3 hours, so no certificate was minted and the
# AFG purge -- which lives in the gauntlet's writer -- never fired for the seventh time. A 175MB
# process to re-answer a question already answered is not a rounding error at that margin.
#
# Same file, same self-healing contract: a blocked observation still clears this instantly,
# because `brain_quota_blocked` is checked first and a wall always wins over a stale open memo.
brain_quota_open_recent() {
    local state epoch now age
    [ -f "$_BRAIN_QUOTA_MEMO" ] || return 1
    state="$(sed -n 's/.*"state"[[:space:]]*:[[:space:]]*"\([a-z]*\)".*/\1/p' \
        "$_BRAIN_QUOTA_MEMO" | tail -1)"
    [ "$state" = "open" ] || return 1
    epoch="$(sed -n 's/.*"observed_at_epoch"[[:space:]]*:[[:space:]]*\([0-9]*\).*/\1/p' \
        "$_BRAIN_QUOTA_MEMO" | tail -1)"
    case "$epoch" in ("" | *[!0-9]*) return 1 ;; esac
    now="$(date -u +%s)" || return 1
    age=$((now - epoch))
    [ "$age" -ge 0 ] && [ "$age" -le "$_BRAIN_QUOTA_OPEN_TTL_S" ]
}

brain_auth_check() {
    # Cheap auth self-test at cycle start: fail LOUD (page), never silently no-op.
    # MODEL FALLBACK CHAIN (principal 2026-07-24): a STARVED MODEL must never kill the organ.
    # fable-5 draws a metered credit pool; on exhaustion we walk _BRAIN_MODEL_CHAIN to the next
    # model (opus-5, then opus-4-8 -- both on the Max subscription seat) and only then try the
    # metered API key. Tonight every organ died out-of-credits because no model fallback existed.
    local out m
    # QUOTA MEMO FIRST -- a probe into a wall another organ already measured buys nothing and
    # costs quota that a dig could have spent. Never a page: this is the EXPECTED state inside a
    # closed window, and paging on it is how a pager gets ignored.
    if brain_quota_blocked; then
        printf '%s brain_auth_check SKIPPED -- quota memo says blocked (see %s)\n' \
            "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$_BRAIN_QUOTA_MEMO" >&2
        return 1
    fi
    # A FRESH OPEN OBSERVATION IS AN ANSWER. Checked AFTER the blocked memo, never before, so a
    # measured wall always beats a stale open note.
    if brain_quota_open_recent; then
        printf '%s brain_auth_check: quota measured OPEN within %ss by another organ -- '\
'skipping a duplicate ~175MB probe\n' \
            "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$_BRAIN_QUOTA_OPEN_TTL_S" >&2
        return 0
    fi
    for m in ${_BRAIN_MODEL_CHAIN:-claude-opus-5 claude-opus-4-8}; do
        export ANTHROPIC_MODEL="$m"
        out="$(claude -p 'Reply with exactly: PING-OK' --dangerously-skip-permissions 2>&1 | tail -3)"
        if printf '%s' "$out" | grep -q "PING-OK"; then
            # An OPEN observation CLEARS the memo -- the wall is only ever believed until the
            # next successful ping, so a stale or wrong memo self-heals on first contact.
            brain_quota_record open 0 "${_BRAIN_ORGAN:-brain}" "PING-OK on $m"
            if [ "$m" != "${_BRAIN_MODEL_CHAIN%% *}" ]; then
                _brain_page "model fallback ACTIVE: primary starved, organs running on $m"
            fi
            return 0
        fi
    done
    # RECORD THE WALL. Only for genuine limit/credit exhaustion: a missing token or a rejected
    # key is an auth defect that must keep failing loudly and immediately, and blocking probes on
    # it would hide the one failure a human has to fix.
    if printf '%s' "$out" | grep -qiE "limit|usage credits"; then
        local _until _w
        _w="$(brain_reset_wait_s "$out" "$_BRAIN_QUOTA_MEMO_CAP_S")"
        if [ -n "$_w" ]; then
            _until=$(( $(date -u +%s) + _w ))
        else
            # The message names a limit but not a reset. A short soft backoff is still strictly
            # better than every later organ re-walking the chain blind; organ_catchup re-fires on
            # a much shorter cycle than this, so nothing is stranded.
            _until=$(( $(date -u +%s) + _BRAIN_QUOTA_SOFT_S ))
        fi
        brain_quota_record blocked "$_until" "${_BRAIN_ORGAN:-brain}" \
            "$(printf '%s' "$out" | head -1 | cut -c1-140)"
    fi
    if printf '%s' "$out" | grep -qiE "limit|usage credits" && [ -f "$_BRAIN_KEYFILE" ]; then
        unset CLAUDE_CODE_OAUTH_TOKEN
        ANTHROPIC_API_KEY="$(cat "$_BRAIN_KEYFILE")"
        export ANTHROPIC_API_KEY
        out="$(claude -p 'Reply with exactly: PING-OK' --dangerously-skip-permissions 2>&1 | tail -3)"
        if printf '%s' "$out" | grep -q "PING-OK"; then
            _brain_page "Brain hit subscription quota -- FELL BACK to metered API key; cycles continue on metered spend"
            return 0
        fi
    elif printf '%s' "$out" | grep -qiE "limit|usage credits"; then
        # R0360: the quota fallback above is gated on a keyfile that HAS NEVER EXISTED
        # (data/secrets/ holds claude_oauth_token and no anthropic_api_key), so on a credit
        # outage the documented escape hatch cannot fire and every claude-invoking organ dies
        # with it. Until now that was SILENT -- the compound `if` simply evaluated false and fell
        # through, so the desk believed it had a fallback and the one event that would disprove
        # that belief produced no signal. A documented fallback that cannot fire is worse than
        # none, because nobody looks for it. Deliberately NOT deleting the branch: it becomes
        # live the moment the principal drops the key at that path, and removing a capability to
        # silence a warning is the wrong direction. Page instead, so the gap is dated and loud.
        _brain_page "Brain hit subscription quota and the metered fallback is UNREACHABLE -- no \
anthropic_api_key at data/secrets/; organs are down until the subscription resets or the key lands (R0360)"
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
# SINGLE SOURCE (2026-07-30): the chain lives in ops/model_chain.env, generated by
# scripts/run_model_upgrade.py, which auto-adopts a newer flagship with no human in the loop. It
# was hardcoded in THREE files until today, so any change -- including an automatic upgrade --
# would update one and leave two stale, and organs would silently disagree about what they run.
# The literals below are the FALLBACK, kept so a missing/corrupt chain file is a downgrade rather
# than an outage: an organ with no model at all is the worse failure.
if [ -f /home/quant/quant-platform/ops/model_chain.env ]; then
    . /home/quant/quant-platform/ops/model_chain.env
fi
export ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-claude-opus-5}"  # primary = OPUS 5 (principal 2026-08-26: Fable removed -- it draws a METERED pool the fleet exhausted; opus sits on the subscription seat). Was: FABLE 5 (principal 2026-07-30); _BRAIN_MODEL_CHAIN below walks to opus-5 on exhaustion and PAGES when it does. Fable draws a pool that CAN exhaust; opus-5/opus-4-8 sit on the Max subscription seat and carry the rest of the week.
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
export _BRAIN_MODEL_CHAIN="${_BRAIN_MODEL_CHAIN:-claude-opus-5 claude-opus-4-8}"

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
# CONSOLIDATION 2026-08-25: the doctrine file is now the slim order channel (sealed core + MT5
# universe mandate); the operative constitution lives in docs/LAWS.md. Both are injected together
# so every organ carries the sealed core AND the full compact law set -- one source, no drift.
# (Total injection SHRANK: the old 227-line doctrine outweighed doctrine+LAWS combined.)
_DOCTRINE="$(cat "$_BRAIN_ROOT/ops/principal_doctrine.txt" "$_BRAIN_ROOT/docs/LAWS.md" 2>/dev/null)"
if [ -z "$_DOCTRINE" ]; then
    printf 'brain_env: DOCTRINE EMPTY (%s + docs/LAWS.md) -- every organ sourcing this would run undirected\n' \
        "$_BRAIN_ROOT/ops/principal_doctrine.txt" >&2
fi
_CONVERSION_CONTROL="$(cat "$_BRAIN_ROOT/ops/shared_conversion_controller.txt" 2>/dev/null)"
if [ -z "$_CONVERSION_CONTROL" ]; then
    printf 'brain_env: SHARED CONVERSION CONTROL EMPTY (%s)\n' \
        "$_BRAIN_ROOT/ops/shared_conversion_controller.txt" >&2
else
    _DOCTRINE="${_DOCTRINE}

${_CONVERSION_CONTROL}"
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
    # RESEARCH-MANDATE LEAD (2026-08-25): every dig opens with the one research mandate, so no
    # organ can run on a stale per-prompt copy of the rules -- docs/RESEARCH.md is the single
    # source and the brief that follows is the dig's SCOPE, never its law.
    local brief prio lead
    lead="STANDING ORDER: read docs/RESEARCH.md before the brief below -- it is the one \
research mandate (MT5/Fusion universe ONLY) and governs this entire dig. \
TOKEN DISCIPLINE (principal 2026-08-25, supersedes max-everything FOR CYCLES): you run at \
reduced reasoning -- be implementation-focused, act, convert, commit; deliberate only where a \
verdict demands it. CORPORA FIRST: consume the pre-fetched collector output under \
data/intelligence/ before any live browsing -- the python miners gather for free; your tokens \
are for JUDGMENT (mechanism extraction, dispositions, verdicts), not for HTML. Route bulk \
extraction/normalization to the free-tier/DeepSeek path or to a python script you write, never \
through your own context. TOOL HYGIENE: targeted reads only; tail logs <=50 lines; grep, never \
cat, a file you can grep."
    brief="$(cat "$1")"
    prio="$(mine_priority)"
    if [ -n "$prio" ]; then
        # §33 keeps the lead position -- dig_dry_run and the readiness probe verify it there.
        printf '%s\n\n%s\n\n%s' "$prio" "$lead" "$brief"
    else
        printf '%s\n\n%s' "$lead" "$brief"
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
