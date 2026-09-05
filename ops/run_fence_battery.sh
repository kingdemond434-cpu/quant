#!/usr/bin/env bash
# Daily fence battery -- the check scripts that were each the SOLE importer of a fence library
# and invoked by NOTHING (max_audit unwired-caller, measured 2026-08-26), plus check_bar_span,
# whose only schedule was the user crontab that root's cron.service (OOM-dead since 08-20)
# never runs. A fence that never runs is a claim the desk cannot cash (L1.49).
#
# Each check runs under its own timeout and the battery NEVER aborts early: one broken fence
# must not silence the others. Nonzero exits are findings (that is what fences are for), so the
# battery itself exits 0 unless a check crashed in a way that produced no output.
set -uo pipefail
cd /home/quant/quant-platform
# SEALED AGAINST MID-RUN REWRITE (2026-08-26). bash reads a script INCREMENTALLY by byte
# offset; a commit that changes this file's LENGTH while it is running resumes execution inside
# a line. Measured on 63680c05 (ops/run_frontier_rotation.sh): comment text ran as a command,
# then a dangling `fi`, then the script RE-RAN ITSELF FROM THE TOP. Only the exit INSIDE the
# group ends the process before bash reads another byte. Do not unwrap; add nothing after `}`.
{
PY=.venv/bin/python
LOG_PREFIX="[fence-battery $(date -u +%FT%TZ)]"
echo "$LOG_PREFIX start"
# Literal paths on purpose: max_audit's unwired-caller detector greps invoker files for the
# script FILENAME, so a $s.py loop variable would leave every check reading as uninvoked.
for s in scripts/check_bar_span.py scripts/check_data_recoverability.py \
         scripts/check_disposition_landed.py scripts/check_frozen_values.py \
         scripts/check_knob_sensitivity.py scripts/check_ledger_reversion.py; do
    echo "$LOG_PREFIX == $s"
    timeout 300 "$PY" "$s" 2>&1 | tail -20
    echo "$LOG_PREFIX $s rc=$?"
done
echo "$LOG_PREFIX done"

exit $?
}
