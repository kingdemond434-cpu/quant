#!/usr/bin/env bash
# Smoke test for brain_reset_wait_s (work order run-reset-aware-retry).
#
# The order required a smoke run before this ships, and the function is where the whole decision
# lives: it converts a CLI failure message into "how long to sleep, if at all". It is pure text ->
# number precisely so this can be exhaustive without spending a call.
#
# The safety property under test is asymmetric and worth stating: printing NOTHING is always safe
# (the caller pages and aborts, exactly as before the change), while printing a number too large
# would sleep through the next scheduled slot. So every ambiguous case must print nothing.
set -uo pipefail
cd "$(dirname "$0")/../.."

# shellcheck disable=SC1091
_BRAIN_NO_DOCTRINE=1 source ops/brain_env.sh 2>/dev/null || source ops/brain_env.sh

pass=0; fail=0
check() {  # check <label> <expected: NUM|EMPTY|RANGE lo hi> <actual>
    local label="$1" kind="$2" actual="${!#}"
    case "$kind" in
        EMPTY) if [ -z "$actual" ]; then pass=$((pass+1)); echo "  ok   $label (empty)";
               else fail=$((fail+1)); echo "  FAIL $label: expected empty, got '$actual'"; fi ;;
        RANGE) local lo="$3" hi="$4"
               if [ -n "$actual" ] && [ "$actual" -ge "$lo" ] && [ "$actual" -le "$hi" ]; then
                   pass=$((pass+1)); echo "  ok   $label ($actual in [$lo,$hi])";
               else fail=$((fail+1)); echo "  FAIL $label: expected [$lo,$hi], got '$actual'"; fi ;;
    esac
}

echo "brain_reset_wait_s smoke:"

# 1. THE REAL MESSAGE, verbatim from data/cro_ai_logs/recommendation_worker_20260804T2220.log.
#    Must yield a bounded positive wait -- this is the case the whole change exists for.
now_h=$(date -u +%-H)
real="You've hit your session limit · resets $(( (now_h + 1) % 12 == 0 ? 12 : (now_h + 1) % 12 ))$( [ $(( (now_h + 1) % 24 )) -ge 12 ] && echo pm || echo am ) (UTC)"
check "real message, ~1h out" RANGE 1 3660 "$(brain_reset_wait_s "$real")"

# 2. NO parseable reset -> nothing. Behaviour must be identical to before the change.
check "no reset stated"        EMPTY "$(brain_reset_wait_s "You've hit your session limit")"
check "unrelated failure"      EMPTY "$(brain_reset_wait_s "Error: invalid API key")"
check "empty string"           EMPTY "$(brain_reset_wait_s "")"

# 3. BOUNDED. A tiny cap must refuse rather than sleep; this is the guard that stops a reset
#    ~23h away (i.e. one already past today) from sleeping through the next slot.
check "cap refuses long wait"  EMPTY "$(brain_reset_wait_s "$real" 5)"

# 4. Nonsense clock values are rejected, not coerced into a wait.
check "hour 99"                EMPTY "$(brain_reset_wait_s "resets 99am")"
check "minute 88"              EMPTY "$(brain_reset_wait_s "resets 3:88am")"

# 5. 12am/12pm are the two cases a naive +12 gets backwards. Both must parse to a bounded wait
#    or to empty (if out of cap) -- never to a wrong-by-12-hours number inside the cap.
for t in "resets 12am" "resets 12pm" "resets 12:30am"; do
    v="$(brain_reset_wait_s "$t" 86400)"
    if [ -z "$v" ] || { [ "$v" -gt 0 ] && [ "$v" -le 86460 ]; }; then
        pass=$((pass+1)); echo "  ok   '$t' -> '${v:-empty}' (sane)"
    else fail=$((fail+1)); echo "  FAIL '$t' -> '$v'"; fi
done

echo "brain_reset_wait_s: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
