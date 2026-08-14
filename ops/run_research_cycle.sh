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
  # BEFORE ANY ORGAN READS THE COHORT. This box owns the runtime state under data/, and nothing
  # could previously say so: two organs each inferred it from the artifacts, and on a clone the
  # evidence and its absence look identical. `derive_slots` therefore read six missing birth
  # certificates as six clocks never born and published a small Holm m as MEASURED -- a LOOSER
  # bar on the only path to capital -- while a test run recomputed tracked ratchets DOWNWARD from
  # whatever the host could see. Both are the same missing fact, stated once here.
  "$PY" scripts/stamp_desk_host.py || echo "DESK-HOST STAMP FAILED -- the cohort will floor at the cap (safe, but tighter than reality)"
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 15 "$PY" scripts/build_bars.py
  bash ops/run_study_on_vps.sh
  nice -n 15 "$PY" scripts/study_status.py || true
  # The ladder runs even when the sweep found nothing: it also reports what is ALREADY live, and a
  # cycle that skipped it on a null day would go silent exactly when a live record needs reading.
  # THE REVIEW CONSUMES THE SWEEP: funnel, near-survivor bank, evidence tiers, convergence. Four
  # modules that had zero importers until this line existed -- inventory until something reads them.
  nice -n 15 "$PY" scripts/run_research_review.py || true
  # BEFORE the ladder: the ladder recommends which survivors are owed a clock, and that
  # recommendation is worthless while every seat is occupied. Measured 2026-08-13: m=15 against a
  # cap of 12 with ZERO idle, at least one seat held by a DEGENERATE instrument fault that cannot
  # resolve however long it runs. The sweep SURFACES those; retiring one stays a ledgered decision
  # because dropping a row shrinks m and loosens every neighbour's bar.
  # --accept-all: NOTHING IDLES. A dead clock holding a seat blocks a real candidate's forward
  # clock, and forward time is the one input that cannot be bought later, so waiting for a human
  # to approve each reclamation costs exactly the resource the desk is shortest of. This became
  # safe to automate when seats and multiplicity were split: freeing a seat no longer moves any
  # Holm bar, because `m` is now a HIGH-WATER MARK -- a clock that ran and failed consumed a
  # trial, and retiring it does not un-look. BLOCKED clocks are still never touched.
  nice -n 15 "$PY" scripts/run_clock_retirement_sweep.py --accept-all --decided-by cycle || true
  # WHY THE CLOCKS ARE SLOW, ranked, next to the sweep that says which ones are dead. Shortening
  # the clock is forbidden (L1.6) and a cleverer test was built and MEASURED slower (anytime_valid
  # graduated a Sharpe-2 edge at a median 132 days against a fixed 90). The only accelerant left is
  # more effective observations per day, and nothing was computing that rate -- two functions in
  # evidence_clock existed for it with zero callers outside their own module.
  nice -n 15 "$PY" scripts/run_information_rate.py || true
  # THE UNWIRED HUNTER (III.16), daily, so nobody has to remember. A public function that is
  # written, tested, correct and CALLED BY NOTHING is invisible to every other instrument here:
  # ruff sees valid code, mypy valid types, the suite green tests, a module count a module. The
  # only question separating an unwired capability from a working one is WHAT RAN IT, and it is
  # never asked by accident. Four instances were found by hand in one day -- including
  # auto_promotion.decide(), which ruled on live capital and had zero callers on the day capital
  # was deposited. First run: 227 suspects, 203 of them TESTED but wired to nothing.
  # Reports, never blocks: a hunter that failed a push on a false positive would be switched off,
  # and the real instances would return with the alarm already disabled.
  nice -n 15 "$PY" scripts/check_unwired_capability.py || true
  # THE GO-LIVE STATE, PUBLISHED DAILY RATHER THAN REMEMBERED. Advisory by design: every
  # precondition it reports is already ENFORCED independently on the money path (no keys means no
  # authentication, CASHCARRY_KILL forces flatten-only in the executor's own order loop, the ruin
  # rail evaluates every tick, the deadman is independent Tier-3), so this blocks nothing and must
  # not -- a reporting script that can halt the book is a new failure mode bought for a check the
  # book already performs. What it adds is ONE read of all of them together, plus the two figures
  # nothing else reports: whether lcurve has started capturing basis variance, and the closed-trade
  # count that is currently the desk's largest unmeasured risk. `|| true` because a BLOCKED verdict
  # is information, not a cycle failure.
  nice -n 15 "$PY" scripts/run_golive_preflight.py --capital "${GOLIVE_CAPITAL:-200}" || true
  # THE VERB ON THE PROMOTION PATH. Measured 2026-08-14: auto_promotion.decide() had ZERO callers
  # -- `is_armed` and the clip cap were imported by one report and the DECISION function was
  # invoked by nothing, in no cycle, ever. Arming automated promotion would therefore have changed
  # nothing: the marker flips, every gate inside decide() stays unevaluated, and the desk believes
  # its research-to-capital path is automated while the last link does not exist.
  # It publishes verdicts and places nothing; the executor places, the kernel bounds, the deadman
  # stops. Runs AFTER the ladder -- it must see the SAME Stage-B rows the ladder just
  # published, and a promotion decided from a pre-ladder read would cite figures the
  # dashboard never showed, which is how a promotion becomes unauditable after the fact.
  nice -n 15 "$PY" scripts/run_live_ladder.py
  nice -n 15 "$PY" scripts/run_auto_promotion.py --capital "${GOLIVE_CAPITAL:-200}" \
      --min-notional "${VENUE_MIN_NOTIONAL:-10}" || true
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
  # THE ECONOMIC SCOREBOARD, ABOVE THE ARCHITECTURE COUNTS. Everything before this line measures
  # the RESEARCH: kills, survivors, admission, gaps. None of it answers the only question that
  # decides whether this desk is worth running -- is it generating and RETAINING real net wealth.
  # Runs every cycle including the days it can only answer UNMEASURED, because the day it stops
  # being able to say that is the day a live fill happened and nobody wired the report.
  nice -n 15 "$PY" scripts/run_wealth_report.py || true
  # THE BLIND SPOT LEDGER. The Claude-side miners cannot retrieve YouTube transcripts and this
  # clone has no network at all, so a large body of practitioner knowledge -- much of it with no
  # paper, no repo and no article behind it -- is invisible to every collector the desk runs. The
  # GPT seat fetches; this records what was fetched, at what completeness, and what remains, so
  # "we mined that channel" stops being a claim nobody can check.
  nice -n 15 "$PY" scripts/run_external_intel.py || true
  # THE RETURN ENGINES. Everything above measures whether the RESEARCH is healthy; these decide
  # where capital would go if there were any. ELEVEN books; nine correctly report UNMEASURED on a
  # clone with no positions and each names the artifact it needs -- they exist now so that nothing
  # has to be remembered and wired the day a live book appears, which is the failure mode L1.56
  # names. Two produce real output on a network-denied clone: the mechanism ontology (its input is
  # economic reasoning) and agent authority (its input is a policy declaration in git).
  nice -n 15 "$PY" scripts/run_opportunity_books.py || true
  nice -n 15 "$PY" scripts/run_max_push.py || true
  # THE PROGRAMME CANNOT QUIETLY STALL. The ledger verifies every declared capability against the
  # working tree and publishes the unfinished ones as ranked gaps, so an item that stops being
  # worked reappears in tomorrow's priorities by itself. Runs LAST: it measures the cycle that
  # just happened, including whatever this cycle wired.
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
