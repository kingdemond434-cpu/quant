#!/usr/bin/env bash
# THE FOUR GATES, IN ONE COMMAND, ORDERED CHEAPEST-FIRST.
#
# WHY THIS EXISTS AS A FILE RATHER THAN A PARAGRAPH IN CLAUDE.md. Three consecutive batches
# reached the shared branch green on ruff+mypy with pytest never run, and the suite could not
# even COLLECT: the L1.6 Holm-bar fence ran `m=0 [REFUSED]` for four days, four max_audit checks
# left the CHECKS list, and 61 tests were failing behind two clean gates. Convention demonstrably
# does not hold across seats. A tracked script does: every seat runs the same four checks in the
# same order, and the ordering is most of the value -- collection costs 8 seconds and was being
# discovered last, inside a 7200s step nobody runs before pushing.
#
#   ./ops/gates.sh          the three fast gates (~1 min)  -- run before every push
#   ./ops/gates.sh --full   adds the whole suite + coverage floors (~60-80 min)
#
# Install as a pre-push hook (per clone; .git/hooks is not tracked, so this is opt-in and each
# box does it once):
#
#   git config core.hooksPath ops/githooks
#
# NOT A SUBSTITUTE FOR scripts/run_ci.py, which is the scheduled gate with per-step wall-clock
# bounds and marker writing. This is the pre-push shape of the same checks: no lock, no marker, no
# side effects, so it is safe to run at any time and cannot leave a stale-green artifact behind.
set -uo pipefail
cd "$(dirname "$0")/.."

FULL=0
[ "${1:-}" = "--full" ] && FULL=1

PY="python"
[ -x ".venv/bin/python" ] && PY=".venv/bin/python"

fail=0
run() {
  local name="$1"; shift
  printf '  %-26s ' "$name"
  local out
  if out=$("$@" 2>&1); then
    printf 'ok\n'
  else
    printf 'FAIL\n'
    printf '%s\n' "$out" | tail -25 | sed 's/^/      /'
    fail=1
  fi
}

echo "gates:"
# ruff first: it is the cheapest and its failures are the least interesting, so getting them out
# of the way keeps the expensive output readable.
run "lint (ruff)"          $PY -m ruff check .
# COLLECTION IS ITS OWN GATE. An uncollectable module is not a failing test, it is a test that
# DOES NOT RUN, and pytest reports that as an error count sitting next to a green pass count.
# ruff does not resolve names and mypy's `files` excludes tests/, so a deleted function or a
# widened return type passes both while the suite cannot start.
run "collect (pytest --co)" $PY -m pytest --co -q tests/
run "types (mypy)"          $PY -m mypy

if [ "$FULL" = "1" ]; then
  run "tests (pytest)"      $PY -m pytest -q --cov=libs --cov-branch \
                                --cov-report=json:coverage.json
  run "coverage floors"     $PY scripts/check_coverage_floors.py --report coverage.json
else
  echo "  (--full adds the suite + coverage floors; the floors are a RATCHET and a push that"
  echo "   lowers them is a breach, so run it before any commit that touches libs/)"
fi

if [ "$fail" = "0" ]; then
  echo "gates: all green"
else
  echo "gates: RED -- see above. Do not push."
fi
exit "$fail"
