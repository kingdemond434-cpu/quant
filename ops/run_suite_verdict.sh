#!/bin/sh
# R0555/R0564: ONE uninterrupted whole-suite verdict, taken in MAIN (the only tree whose data/
# is the desk's), banked into docs/research/test_suite_record.json via
# scripts/record_suite_run.py -- the producer that check_test_suite_pass_fail reads. Adapted
# from the one-shot /home/quant/run_suite_verdict.sh (which waited on a since-dead sibling PID
# and was scheduled by nothing) into the weekly quant-suite-verdict.timer.
LOG=/home/quant/suite_verdict_$(date -u +%Y%m%dT%H%M%SZ).log
AVAIL=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
echo "MemAvailable=${AVAIL}MB at launch" >> "$LOG"
if [ "$AVAIL" -lt 500 ]; then
  # A suite launched under memory pressure on this swapless 3.8GB box is the OOM behaviour
  # R0407 warns against -- it would kill research organs mid-dig to buy a test run.
  echo "REFUSED: MemAvailable ${AVAIL}MB < 500MB floor" >> "$LOG"
  exit 3
fi
cd /home/quant/quant-platform || exit 1
echo "HEAD=$(git rev-parse HEAD)" >> "$LOG"
# NO `-q` (R0564): pyproject addopts already carries -q; a second one reaches pytest as -qq and
# suppresses the counts line record_suite_run.py needs.
.venv/bin/python -m pytest tests/ -rf --tb=short >> "$LOG" 2>&1
echo "PYTEST_RC=$?" >> "$LOG"
.venv/bin/python scripts/record_suite_run.py --log "$LOG" --source quant-suite-verdict >> "$LOG" 2>&1
echo "$LOG" > /home/quant/suite_verdict_latest.path
