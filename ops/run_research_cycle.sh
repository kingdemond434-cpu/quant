#!/usr/bin/env bash
# THE RESEARCH CYCLE -- bars, then studies, then the live ladder. Daily, unattended.
#
# WHY THIS EXISTS. Measured 2026-08-08: the desk had NINE systemd timers and every one of them ran
# a MINER. Nothing scheduled the bar build or a single study. So the generators -- which the desk's
# own funnel diagnosis says are not the constraint -- ran daily and unattended, while the one stage
# the diagnosis names as the bottleneck (EXECUTION) ran only when a human typed it.
#
# That is L1.52(a)'s asymmetry inverted: `queue backlogged -> EXECUTE`, and the desk had automated
# everything except executing. A pipeline whose slowest stage is the only manual one does not have
# a throughput problem, it has a scheduling problem wearing a throughput problem's clothes.
#
# ORDER IS THE POINT: bars must exist before a study reads them, and the ladder must run after the
# sweep so a fresh Stage-A survivor is owed its shadow start the same day it is found -- the
# forward clock is the one input that cannot be bought later.
set -uo pipefail
cd /home/quant/quant-platform
LOG="data/cro_ai_logs/research_cycle_$(date -u +%Y%m%dT%H%M).log"
mkdir -p data/cro_ai_logs

PY=""
for c in "$PWD/.venv/bin/python" .venv/bin/python python3; do
    if [ -x "$c" ] || command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
[ -n "$PY" ] || { echo "FATAL: no interpreter"; exit 1; }

# BUDGET, NOT HEROICS. build_bars streams (memory is O(buckets), not O(trades)) so a large budget
# is safe on RAM -- but it still costs wall time and competes with the recorders, which write the
# one asset that cannot be re-acquired. 20000 is ~10 minutes and reaches back far enough that the
# weekly horizon stops being starved.
export BARS_FILE_BUDGET="${BARS_FILE_BUDGET:-20000}"

{
  echo "=== research cycle start $(date -u) | BARS_FILE_BUDGET=$BARS_FILE_BUDGET ==="
  # niced throughout: the recorders are the irreplaceable process on this box.
  # SURVIVAL PATH FIRST, BEFORE ANY RESEARCH RUNS. The desk hash-locks its constitution and left
  # the kill switch protected by prose comments; this verifies the rails are byte-identical to
  # what the principal last approved. It runs FIRST because a cycle that researched all day and
  # then discovered the dead-man switch had changed would have spent the day on a book with no
  # floor under it.
  "$PY" scripts/check_risk_kernel.py || echo "RISK-KERNEL DRIFT -- review before trusting this cycle"
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 15 "$PY" scripts/build_bars.py
  bash ops/run_study_on_vps.sh
  nice -n 15 "$PY" scripts/study_status.py || true
  # The ladder runs even when the sweep found nothing: it also reports what is ALREADY live, and a
  # cycle that skipped it on a null day would go silent exactly when a live record needs reading.
  # THE REVIEW CONSUMES THE SWEEP: funnel, near-survivor bank, evidence tiers, convergence. Four
  # modules that had zero importers until this line existed -- inventory until something reads them.
  nice -n 15 "$PY" scripts/run_research_review.py || true
  nice -n 15 "$PY" scripts/run_live_ladder.py
  # EXECUTION HEALTH runs every cycle, including days the research half found nothing. The money
  # path is where the desk is currently LOSING (27 closes, all three hold buckets negative net of
  # fees), so a cycle that reported only research would go quiet on the one number costing money.
  # A COMPLETED SWEEP IS A TRIGGER, NOT AN ENDPOINT. Before this line the factory produced
  # "INDEPENDENT MECHANISM 2 | PORTFOLIO-CONTRIBUTING unmeasured" and stopped -- a discovery
  # stranded one stage short of the only count that pays, waiting for a human to notice. Survivor
  # forwarding now runs in the same cycle that produced the survivors.
  nice -n 15 "$PY" scripts/run_portfolio_admission.py || true
  # ZERO-CAPITAL FORWARD CONVERSION, SAME CYCLE. The spawner now consumes both corrected axis
  # screens and the full sweep's measured independent clusters. Waiting for tomorrow's cron
  # throws away the one input that cannot be backfilled: forward time. The runner publishes a
  # day-zero NO-EVIDENCE row immediately, proving every new clock is runnable and cohort-counted.
  nice -n 15 "$PY" scripts/run_paper_sleeve_spawner.py || true
  nice -n 15 "$PY" scripts/run_paper_sleeve_forward.py || true
  nice -n 15 "$PY" scripts/run_promotion_queue.py || true
  nice -n 15 "$PY" scripts/run_trade_forensics.py || true
  nice -n 15 "$PY" scripts/run_exec_monitor.py || true
  # THE LOOP CLOSES HERE. The intelligence cycle re-reads everything this run produced -- kills,
  # survivors, admission, conversion joins, source and cadence yield -- and republishes the ranked
  # gap set, so tomorrow's highest-value work is chosen from today's evidence rather than from
  # whatever was true when the schedule was written.
  nice -n 15 "$PY" scripts/run_intelligence_cycle.py || true
  # Integrated residuals consume this cycle's real evidence; missing inputs remain UNMEASURED and
  # therefore enter max-push above partially measured work rather than disappearing as clean zeros.
  # Evolve the METHOD frontier before the completion report reads it: missing search methods,
  # stagnation, fractional discovery credit and the bounded serendipity mission must affect the
  # same night's priorities rather than appearing one cycle late.
  nice -n 15 "$PY" scripts/research_alpha_optimizer.py || true
  nice -n 15 "$PY" scripts/gpt_hunter.py || true
  # Elite external work converts through the EXISTING hypothesis queue: public claims stay priors,
  # while capability gaps, papers, failures, participant sensors, MEV and white-space coverage
  # become measured frontier work rather than another document archive.
  nice -n 15 "$PY" scripts/run_external_intelligence.py || true
  nice -n 15 "$PY" scripts/run_alpha_frontier.py || true
  # Verify the ledger BEFORE the integrated report and ranker consume it. Publishing gaps after
  # max-push would strand every newly found incomplete capability for an extra day.
  nice -n 15 "$PY" scripts/run_completion_ledger.py || true
  nice -n 15 "$PY" scripts/run_completion_program.py || true
  nice -n 15 "$PY" scripts/run_max_push.py || true
  echo "=== research cycle exit $? at $(date -u) ==="
} 2>&1 | tee -a "$LOG"
