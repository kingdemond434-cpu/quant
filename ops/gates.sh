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
# The trading box is Windows, where the venv lives at .venv/Scripts/python.exe; without this the
# box's pushes ran these gates on whatever bare `python` was on PATH (2026-10-01).
[ "$PY" = "python" ] && [ -x ".venv/Scripts/python.exe" ] && PY=".venv/Scripts/python.exe"

# A full gate owns its test options. Inherited --basetemp lets a nested pytest
# delete its parent's fixtures; inherited -k can turn a full gate into a subset.
unset PYTEST_ADDOPTS
export PYTHONUTF8=1
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
root_test_args=()
desk_test_args=()
if [ -n "${QUANT_TEST_WORKERS:-}" ]; then
  if ! [[ "$QUANT_TEST_WORKERS" =~ ^[1-9][0-9]*$ ]]; then
    echo "gates: QUANT_TEST_WORKERS must be a positive integer" >&2
    exit 2
  fi
  root_test_args+=(-n "$QUANT_TEST_WORKERS" --dist loadfile)
  desk_test_args+=(-n "$QUANT_TEST_WORKERS" --dist loadfile)
fi
if [ -n "${QUANT_GATE_TMPDIR:-}" ]; then
  mkdir -p "$QUANT_GATE_TMPDIR" || exit 2
  root_test_args+=(--basetemp "$QUANT_GATE_TMPDIR/root")
  desk_test_args+=(--basetemp "$QUANT_GATE_TMPDIR/desk")
fi
if [ -n "${QUANT_GATE_EVIDENCE_DIR:-}" ]; then
  mkdir -p "$QUANT_GATE_EVIDENCE_DIR"
  root_test_args+=(--junitxml "$QUANT_GATE_EVIDENCE_DIR/root-junit.xml")
  desk_test_args+=(--junitxml "$QUANT_GATE_EVIDENCE_DIR/desk-junit.xml")
fi
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
  if [ -n "${QUANT_GATE_EVIDENCE_DIR:-}" ]; then
    local slug
    slug=$(printf '%s' "$name" | tr -c 'A-Za-z0-9._-' '_')
    printf '%s\n' "$out" > "$QUANT_GATE_EVIDENCE_DIR/$slug.txt"
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
# B023 (2026-09-30): the project config excludes desks/mt5, so two late-binding loop closures
# (families_orthogonal, acquire_datasets) reached LIVE unseen. Fenced here and by
# desks/mt5/tests/test_b023_loop_closures.py.
run "lint desks/mt5 (bugs)" $PY -m ruff check desks/mt5 --isolated --target-version py311 --select E9,F63,F7,F82,B023
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
  # Match CI's separate Python namespaces, then combine actual branch evidence.
  # A combined collection can resolve the desk's scripts against root scripts.
  run "tests (pytest)"      $PY -m pytest -q tests/ \
                                --cov=libs --cov=desks/mt5/mt5desk --cov=desks/mt5/research --cov-branch \
                                --cov-report= "${root_test_args[@]}"
  run "mt5 tests (pytest)"  $PY -m pytest -q desks/mt5/tests/ \
                                --cov=libs --cov=desks/mt5/mt5desk --cov=desks/mt5/research --cov-branch \
                                --cov-append --cov-report=json:coverage.json "${desk_test_args[@]}"
  run "root coverage population" $PY -m coverage json --include='libs/*' -o coverage-libs.json
  run "coverage floors"     $PY scripts/check_coverage_floors.py --report coverage-libs.json
  # THE MONEY PATH HAS ITS OWN FLOOR, and until 2026-09-23 it ran on no clock at all: the
  # ratchet over the files that move capital was a script nothing invoked (LAWS 7 -- unwired
  # is a defect; L1.49 -- a gate that never ran is a claim the desk cannot cash).
  run "mt5 money-path floor" $PY scripts/check_mt5_coverage_floor.py --report coverage.json
else
  echo "  (--full adds the suite + coverage floors; the floors are a RATCHET and a push that"
  echo "   lowers them is a breach, so run it before any commit that touches libs/)"
fi

# ATTEST WHAT WAS TESTED, AND ON WHICH COMMIT. A release that seals a sha and cannot say what
# passed against it has provenance for the bytes and none for the judgement. Written on RED too:
# "these gates failed on this sha" is a measurement, and suppressing it would leave the last
# green attestation standing as though nothing had happened since.
if [ "$fail" = "0" ]; then
  echo "gates: all green"
  $PY scripts/gate_attestation.py --gates "$([ "$FULL" = "1" ] && echo full || echo fast)" --result pass || true
else
  echo "gates: RED -- see above. Do not push."
  $PY scripts/gate_attestation.py --gates "$([ "$FULL" = "1" ] && echo full || echo fast)" --result fail || true
fi
exit "$fail"
