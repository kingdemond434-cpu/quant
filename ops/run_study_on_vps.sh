#!/usr/bin/env bash
# PATH (a): RUN THE STUDIES WHERE THE DATA IS. The other answer to the transport gap, and the one
# that needs no transport at all.
#
# WHICH PATH TO TAKE, stated once so it is not re-argued each time:
#
#   (a) THIS SCRIPT -- run on the box. The full archive is here, including the OLDEST tape, which
#       is the part a competitor most conclusively cannot obtain because unlike a live feed it
#       cannot be bought or backfilled at any price. Nothing leaves the machine. The cost is that
#       the study competes for CPU with the recorders, so it is niced and single-threaded.
#
#   (b) ops/snapshot_research_data.sh -- ship a bounded slice somewhere a clone can fetch. Faster
#       to iterate on, and the only option when the analysis has to happen off-box. The cost is
#       that it carries the last N days rather than the archive, so any result is a result about
#       a window, and the snapshot must be treated as public.
#
# Use (a) for anything that reads the moat tape or claims a span. Use (b) for iterating on harness
# code against real shapes. Do not use (b) for a verdict on a hypothesis whose whole claim is the
# length of the archive.
#
#   bash ops/run_study_on_vps.sh                    # every registered study, in order
#   bash ops/run_study_on_vps.sh failed_breakout    # just one
#
# Read-only over data/. No keys, no order paths, no promotion authority. Safe while the desk runs.
set -euo pipefail
cd "$(dirname "$0")/.."

ONLY="${1:-}"
LOG="${STUDY_LOG:-data/study_runs.log}"
mkdir -p "$(dirname "$LOG")"

# ---------------------------------------------------------------------------------------------
# SURVIVE A DROPPED SSH SESSION. Added 2026-08-08 after it cost a real run.
#
# WHAT HAPPENED. The operator started the full sweep over SSH at 09:56Z. At ~40% -- 359,424 of
# 898,560 candidates evaluated across 8 of 20 cells -- the connection dropped:
#
#     client_loop: send disconnect: Connection reset
#
# The studies run in the FOREGROUND of the invoking shell, so SIGHUP killed the sweep. Afterwards
# there was no process, no OOM line in dmesg, no traceback, and no data/full_sweep.json, because
# the report is only written at the end. The eight cells of results existed solely in terminal
# scrollback. THE FAILURE MODE IS SILENT AND TOTAL: an hour of niced compute produced nothing,
# and every diagnostic the operator could run afterwards showed a clean box.
#
# This is a property of the runner, not operator error. A study that projects 56 minutes and is
# allowed up to 180 CANNOT be tied to the lifetime of a terminal.
#
# THE GUARD: when started from a TTY, re-exec detached and hand back the follow command. cron and
# systemd have no controlling terminal, so they take the normal path and nothing about the
# scheduled runs changes. STUDY_FOREGROUND=1 opts out for debugging.
# THE TEST IS "DO I HAVE A CONTROLLING TERMINAL", NOT "IS STDOUT A TTY", and the difference is
# the whole point: SIGHUP is delivered to the foreground process group of the controlling
# terminal REGARDLESS of where stdout was redirected. `[ -t 1 ]` would take the inline path for
# `bash ops/run_study_on_vps.sh | tee run.log` -- the most natural way an operator would run this
# -- and that invocation is exactly as exposed to a dropped connection as the bare one.
if ( : > /dev/tty ) 2>/dev/null && [ -z "${STUDY_DETACHED:-}" ] && [ -z "${STUDY_FOREGROUND:-}" ]
then
    _runlog="data/study_runs_$(date -u +%Y%m%dT%H%M%SZ).log"
    STUDY_DETACHED=1 setsid nohup bash "$0" "$@" > "$_runlog" 2>&1 < /dev/null &
    echo "detached as pid $! -- this run now survives a dropped SSH session."
    echo "  follow:  tail -f $_runlog"
    echo "  stop:    kill $!"
    echo "  (STUDY_FOREGROUND=1 runs inline instead; cron and systemd already do, having no TTY)"
    exit 0
fi

# THE INTERPRETER IS .venv/bin/python, NOT python3 -- and this script had it wrong until 2026-08-06.
# Every other entry point on this box already knew: the systemd units all ExecStart
# `.venv/bin/python`, ops/deploy_vps.sh hard-FAILS if that binary is absent, and brain_env.sh walks
# the same fallback chain. The deps are installed by `pip install -e '.[dev]'` INTO THE VENV, so a
# bare `python3` is the system interpreter with no pandas and no numpy.
#
# The cost of getting this wrong is not a wrong answer, it is a WASTED SESSION: the operator opens
# an SSH session to run the studies, the first one dies on `ModuleNotFoundError: pandas` before
# reading a single bar, and the traceback names the study rather than the interpreter. Failing here
# instead, with the reason, costs one line.
PY=""
for _c in "$PWD/.venv/bin/python" .venv/bin/python python3; do
    if [ -x "$_c" ] || command -v "$_c" >/dev/null 2>&1; then PY="$_c"; break; fi
done
[ -n "$PY" ] || { echo "FATAL: no python interpreter found (looked for .venv/bin/python, python3)"; exit 1; }
if ! "$PY" -c "import pandas, numpy" >/dev/null 2>&1; then
    echo "FATAL: $PY cannot import pandas/numpy -- the studies would die on the first import."
    echo "       The venv is what carries the dependencies:"
    echo "         python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'"
    echo "       Checked BEFORE any study starts so this costs a second rather than a session."
    exit 1
fi
echo "INTERPRETER $PY"

# THE STUDIES, and each names the pre-registration that binds it. A study with no pre-registration
# in this table cannot be run from here -- that is the point of the table, not an oversight. The
# kill criteria have to exist before the run, or the run is a search.
declare -A STUDIES=(
  ["failed_breakout"]="scripts/run_failed_breakout_study.py|docs/research/FAILED_BREAKOUT_PREREGISTRATION.md"
  ["moat_screen"]="scripts/screen_moat.py --files 200|docs/research/MAX_SURVIVORS_PROGRAM.md"
  ["ethbtc_rotation"]="scripts/run_ethbtc_rotation_study.py|docs/research/ETHBTC_ROTATION_PREREGISTRATION.md"
  # THE WHOLE DECLARED SPACE AT ONCE -- 898,560 candidates, one pass, no sampling decision to
  # justify. It PROJECTS ITS OWN RUNTIME on a calibration batch and refuses past --max-minutes
  # rather than starving the recorders, so running it here is safe by construction.
  ["full_sweep"]="scripts/run_full_sweep.py --max-minutes 180|docs/research/FULL_SWEEP_PREREGISTRATION.md"
)

# EXECUTION ORDER, EXPLICIT. This script's own header promised "every registered study, in order"
# and could not deliver it: bash iterates an associative array in HASH order, so the sequence was
# whatever the hash produced and would change silently when a study was added. That matters here
# because the studies are niced and single-threaded by design -- the order IS the priority. The
# blind sweep runs LAST: it is the widest and the least argued-for, and the mechanism studies must
# not queue behind it.
ORDER=(failed_breakout ethbtc_rotation moat_screen full_sweep)

run_one() {
  local name="$1" spec="${STUDIES[$1]}"
  local cmd="${spec%%|*}" prereg="${spec##*|}"

  echo "──────────────────────────────────────────────────────────────"
  echo "STUDY   $name"
  echo "PREREG  $prereg"
  if [ ! -f "$prereg" ]; then
    echo "REFUSED: the pre-registration is missing. Kill criteria chosen after seeing a result are"
    echo "         not kill criteria, so a study whose document is absent does not run."
    return 1
  fi
  echo "STARTED $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  # niced and single-threaded: the recorders are the irreplaceable process on this box, and a
  # study that starves them costs tape that cannot be re-acquired at any price.
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    nice -n 15 "$PY" $cmd 2>&1 | tee -a "$LOG"
  echo "FINISHED $(date -u +%Y-%m-%dT%H:%M:%SZ)"
}

echo "== data present on this box ==" | tee -a "$LOG"
for d in data/moat data/bars data/lake; do
  if [ -d "$d" ]; then
    printf "  %-16s %8s files, %s\n" "$d" \
      "$(find "$d" -type f | wc -l)" "$(du -sh "$d" 2>/dev/null | cut -f1)"
  else
    printf "  %-16s ABSENT -- this box is not the collecting box\n" "$d"
  fi
done | tee -a "$LOG"

# A study registered but absent from ORDER would never run, and the log would look complete.
for name in "${!STUDIES[@]}"; do
  case " ${ORDER[*]} " in
    *" $name "*) ;;
    *) echo "FATAL: study '$name' is registered but missing from ORDER -- it would silently never"
       echo "       run, and the run log would look complete. Add it to ORDER."; exit 1;;
  esac
done

if [ -n "$ONLY" ]; then
  [ -n "${STUDIES[$ONLY]:-}" ] || {
    echo "unknown study '$ONLY'. Registered: ${ORDER[*]}"; exit 1; }
  run_one "$ONLY"
else
  for name in "${ORDER[@]}"; do run_one "$name" || true; done
fi

echo
echo "Artifacts are under data/. They are gitignored, so to get a VERDICT off the box either read"
echo "it here, or commit the JSON report itself -- reports are small, and a verdict is not a lake."
