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

# WAIT FOR MEMORY, DO NOT RACE INTO AN OOM (2026-08-29). This box has 3814MB and NO SWAP, and
# routinely sits under 1GB available -- over a gigabyte of it held by Claude Code sessions and a
# separate live desk, against 224MB for the whole quant platform. mypy over ~700 files plus a
# pytest collection needs several hundred MB, and this script was killed with signal 9 mid-run.
# A gate run that dies on OOM has burned its full runtime and produced nothing; the same run
# started ninety seconds later completes. So block for headroom rather than racing for it.
#
# Exit 75 (EX_TEMPFAIL) means "not started, box is short" -- a distinct outcome from a red gate,
# and one a caller must not mistake for a passing tree.
if [ -f scripts/memory_guard.py ] && [ -z "${QUANT_SKIP_MEMORY_GUARD:-}" ]; then
  if ! $PY scripts/memory_guard.py --label gates --need-mb 700 --max-wait-s 600 -- true; then
    echo "gates: NOT RUN -- insufficient memory (exit 75). This is not a green tree."
    exit 75
  fi
fi
# Cap glibc per-thread arenas for the gate processes themselves; the default 64MB-per-thread
# arenas cost hundreds of MB of address space this workload never touches.
export MALLOC_ARENA_MAX="${MALLOC_ARENA_MAX:-2}"

echo "gates:"
# ruff first: it is the cheapest and its failures are the least interesting, so getting them out
# of the way keeps the expensive output readable.
run "lint (ruff)"          $PY -m ruff check .
# COMPILE IS ITS OWN GATE, AND RUFF IS NOT A SUBSTITUTE FOR IT (2026-08-26). scripts/
# liquidation_listener.py sat in committed code with `await asyncio.sleep(30)` inside a plain
# `def`, and ruff, mypy AND pytest --co all reported GREEN on it -- for at least 21h, during
# which it was the sole cause of the desk-wide CI red. `await` outside `async` is not a PARSER
# error: CPython accepts it into the AST and rejects it in the symbol-table pass, so every
# AST-level tool (ruff included, and `ast.parse` if you reach for it to check by hand) says the
# file is fine while `import` raises SyntaxError. Collection missed it because the only importer
# does so inside a fixture, so the module is never touched at collection time -- and the four
# tests that would have caught the REAL defect underneath (a non-atomic archive write that had
# already destroyed ~40 days of data) ERRORED on import instead of FAILING on behaviour, which
# is how the lost implementation stayed lost. compileall runs the pass the others skip, over the
# whole tree, in about a second.
run "compile (compileall)" $PY -m compileall -q scripts libs desks tests
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
