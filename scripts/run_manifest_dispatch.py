#!/usr/bin/env python3
"""Resurrect allowlisted ops/crontab.manifest rows under a user timer (cron died 08-20).

ROOT CAUSE, measured 2026-08-26: root `cron.service` OOM-died 2026-08-20 and cannot be restarted
without the principal's console (no sudo by design). Every row in ops/crontab.manifest without a
user-timer twin has been silently dead since -- including the hourly law gate, the DAILY RATCHET
RAISER (the direct cause of the 16-day L1.50 coverage-floor stall), the §33 conversion fence and
the deploy puller. This dispatcher runs every 5 minutes from `quant-manifest-dispatch.timer` and
fires the rows on the ALLOWLIST below with exact cron semantics, reading schedule and command
LIVE from the manifest (anti-hardcode law: the manifest stays the single source of truth; the
allowlist only GATES which rows may fire, because most manifest rows are retired-crypto-era
organs that the MT5 mandate forbids resurrecting blindly).

Safety properties:
- Only allowlisted rows fire. Everything else is COUNTED in the state artifact as
  `uncovered_unallowed` so the remaining backlog is measured, never silent (L1.28a).
- A row whose script is referenced by any installed user unit is skipped (twin check at
  runtime) -- building a proper dedicated timer later auto-retires the dispatcher's copy.
- Catch-up window is capped: a row missed by more than CATCHUP_CAP_MIN minutes waits for its
  next scheduled slot instead of thundering after an outage.
- Rows keep their own flock/redirect wrapping; the dispatcher detaches and never blocks on them.
"""
from __future__ import annotations

import contextlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "ops" / "crontab.manifest"
STATE = ROOT / "data" / "manifest_dispatch_state.json"
OUTCOMES = ROOT / "data" / "fence_outcomes.jsonl"
USER_UNITS = Path.home() / ".config" / "systemd" / "user"
CATCHUP_CAP_MIN = 20

#: script token -> why this row is resurrected. Tokens are matched against the manifest at
#: runtime; a token with no surviving manifest row simply never fires. EVERYTHING ELSE in the
#: manifest stays dead until a human moves it here or builds it a real timer -- most rows are
#: crypto-era organs the MT5 mandate (LAWS §1) forbids waking.
#:
#: FIVE TOKENS REMOVED 2026-09-05: check_gate0_ready, run_sleeve_allocator, run_rejection_rescore,
#: run_execution_quality and check_margin_topology. Each named a script deleted with the retired
#: book, and the header above already states the rule -- a token with no file can never fire, so
#: leaving them would have made this allowlist read longer than the set of organs it can actually
#: wake, which is the drift it exists to prevent.
ALLOWLIST: dict[str, str] = {
    "scripts/run_law_gate.py": "hourly law gate -- the enforcement entry point for every organ",
    "scripts/check_conversion.py": "hourly §33 conversion fence",
    "scripts/check_ratchets.py": "daily ratchet raiser (its death caused the L1.50 floor stall)",
    "scripts/check_constitution_core.py": "6-hourly seal verification",
    "scripts/check_utilisation.py": "6-hourly utilisation/timidity fence",
    "scripts/check_fence_yield.py": "daily L1.43 governance-yield measurement",
    "scripts/check_enforcement_execution.py": "daily enforcement-execution fence",
    "scripts/check_campaign_retention.py": "daily campaign-retention fence",
    "scripts/check_repair_capacity.py": "daily repair-capacity fence",
    "scripts/build_event_calendar.py": "monthly macro event calendar (MT5 event guard input)",
    "scripts/run_intelligence_cycle.py": "4-hourly macro collectors (WALCL/RFB vintages feed MT5 axes)",
    "deploy/pull_deploy.sh": "10-min inbound deploy path (dead 126h; fence reads its state)",
    # ------------------------------------------------------------------------------------
    # SECOND WAVE, gap-fixer 2026-08-26. The first wave rescued 12 rows and left 173
    # venue-agnostic ones dead, because the backlog number this script writes was consumed by
    # NOBODY (grep: zero readers of manifest_dispatch_state.json) -- a measurement with no
    # consumer is an opinion, so "216 uncovered" sat in a file for six days and escalated to
    # no one. Every token below was RUN BY HAND on 2026-08-26 before being listed here: each
    # exits 0 or exits 2-with-a-real-finding, and none is crypto-era. rc=2 on a fence is
    # correct behaviour, not a failure -- these organs are supposed to fail loud.
    # Ordered by expected terminal-wealth impact, which is why the liveness fence leads:
    # ITS death is why the other 172 deaths went unnoticed.
    # ------------------------------------------------------------------------------------
    "scripts/check_organ_liveness.py": "hourly dead-organ detector -- ITSELF dead 128h; the "
                                       "reason the 08-20 cron death escalated to nobody",
    "scripts/check_freshness.py": "hourly L1.44 consumption-time freshness contracts",
    "scripts/check_change_window.py": "hourly L1.38 sterile-cockpit window (money-path guard)",
    "scripts/check_promotion_gate.py": "hourly L1.6 promotion-gate rung state",
    "scripts/run_promotion_queue.py": "6-hourly promotion queue -- the forward->live door",
    "scripts/check_risk_units.py": "daily L1.67 risk-UNITS audit (the CADJPY 1.26%-logged/"
                                   "7.41%-run defect class; no other fence asks this)",
    "scripts/run_portfolio_risk.py": "daily portfolio risk aggregation",
    "scripts/max_audit.py": "daily live-defect audit -- the desk's own defect finder was dead",
    "scripts/rerank_gaps.py": "weekly §35 gap re-rank (GAP_REGISTER is the only work driver)",
    "scripts/record_desk_metrics.py": "daily desk metric trend (a snapshot is not a trend)",
    "scripts/check_claim_consistency.py": "daily cross-organ claim contradiction detector",
    "scripts/check_input_provenance.py": "hourly artifact input-provenance declarations",
    "scripts/check_denominators.py": "hourly denominator-declaration fence",
    "scripts/check_idle_cost.py": "hourly idle-capital/timidity meter (LAWS §2a)",
    "scripts/run_stale_daemon_repair.py": "twice-daily stale-daemon actuator",
    "scripts/build_gauntlet_survivors.py": "the eight-gate barrier's MISSING producer -- it had judged zero candidates ever",
    "scripts/promotion_gate.py": "eight-gate screen-side record (capacity+fragility, which the canonical ten do not cover)",
    # ------------------------------------------------------------------------------------
    # THIRD WAVE, gap-fixer 2026-08-26. The law fences. Every token below was RUN BY HAND
    # before being listed, and the reason quotes WHAT IT ACTUALLY PRINTED -- an allowlist entry
    # justified by a filename is a guess wearing a citation. rc=2 on a fence is correct
    # behaviour: these organs exist to fail loud, and a fence never observed failing has had
    # only its passes verified.
    #
    # These enforce NAMED LAWS -- L1.6, L1.29, L1.30, L1.32, L1.36, L1.45, L1.49, L1.54, L1.60,
    # L1.62, L1.68, s42 -- and every one was scheduled by NOTHING since the 08-20 cron death.
    # A law with no running fence is a law the desk cannot cash (L1.49).
    # ------------------------------------------------------------------------------------
    "scripts/check_miner_runway.py": "the discovery engine's own doctor -- repaired this cycle "
                                     "(it graded 118-byte stubs `ok`) and scheduled by nothing",
    "scripts/check_gate_reachability.py": "L1.49; live rc=2 -- 2 dead branch(es), 8 unsatisfiable, "
                                          "2 zero-bit acceptors. 'a gate nobody calls returns "
                                          "True' is a lesson this desk has already paid for",
    "scripts/check_bar_span.py": "L1.68 data integrity; live rc=2 CONTAMINATED across 88/88 "
                                 "series -- the input every backtest on this desk reads",
    "scripts/check_cohort_integrity.py": "L1.6; live rc=2 DIVERGENT -- axis_shadows reports m=13 "
                                         "against the registry. Evidence integrity, not hygiene",
    "scripts/check_calibration.py": "L1.29; live rc=2 OVERDUE -- 20 forecasts past their grading "
                                    "deadline. A desk that never grades its forecasts has no "
                                    "calibration, only opinions",
    "scripts/check_replacement_rate.py": "L1.30; live rc=2 UNMEASURED-BIRTHS (>=21 births vs 23 "
                                         "deaths) -- edges die on their own schedule and only "
                                         "the pipeline decides whether the desk does",
    "scripts/check_law_families.py": "L1.36; live rc=2 -- 0/6 families fully enforced, failing "
                                     "aggression and exploration",
    "scripts/check_exploration.py": "L1.32; live rc=2 STALE -- 4/5 exploration organs in cadence",
    "scripts/check_excitation.py": "L1.45; live rc=2 ABSORBING -- an execution exclusion with NO "
                                   "re-entry condition. A controller that never perturbs cannot "
                                   "identify the surface it sits on",
    "scripts/check_capital_basis.py": "live rc=2 UNDECLARED-RETURNS -- 16 return-reporting "
                                      "artifacts of 198 scanned declare no capital basis",
    "scripts/check_mechanism_attribution.py": "L1.6; live rc=2 UNMEASURED -- names the blindness "
                                              "rather than passing over it",
    "scripts/check_llm_routing.py": "L1.54 compute maximisation; live rc=0 reporting 2/22 organs "
                                    "routed (0.091) -- a throughput gap nothing was watching",
    "scripts/check_cross_section_floor.py": "live rc=0 PARTIAL -- 18/52 collapse sites floored "
                                            "(34.6%); the ratchet that catches breadth regression",
    "scripts/check_denominator_attrition.py": "L1.60; live rc=0 OK over 86 files -- the fence "
                                              "that catches a shrinking denominator faking a rate",
    "scripts/check_strategy_breadth.py": "L1.32; live rc=0 -- 14 hunting surfaces, 8/14 families "
                                         "generating. Directly watches the 0.952 concentration",
    "scripts/check_panel_breadth.py": "L1.62; live rc=0 -- 53/53 panel cells, 0 over-claimed",
    "scripts/check_citation_integrity.py": "L2.3/s42; live rc=0 -- 0 unresolvable of 298 citations",
    # ------------------------------------------------------------------------------------
    # FIFTH WAVE, gap-fixer 2026-08-29. Same standard as the third and fourth: each was RUN BY
    # HAND this cycle and the reason quotes what it actually printed.
    #
    # Both of these were REPAIRED this cycle, and that is precisely why they are listed here:
    # a fixed organ that nothing schedules is the defect this dispatcher exists to close
    # (III.16 -- built is not a status; name the caller).
    # ------------------------------------------------------------------------------------
    "scripts/check_prompt_ratchet.py": "the fence that verifies LAWS actually REACH organs; "
                                       "live rc=0 '31 governed prompts, 334 invariant assertions "
                                       "across 29 defined invariants ... every prompt still "
                                       "asserts every rule it used to'. LAWS.md itself records "
                                       "that five load-bearing rules of the sealed core stopped "
                                       "reaching ANY organ on 2026-08-25 and that this ratchet "
                                       "named all five -- while its own scheduler was dead",
    # ------------------------------------------------------------------------------------
    # FOURTH WAVE, gap-fixer 2026-08-27. Same standard as the third: every token below was RUN
    # BY HAND this cycle and the reason quotes WHAT IT ACTUALLY PRINTED. rc=2 on a fence is
    # correct behaviour. Twelve more candidates were run and DELIBERATELY LEFT OUT -- see the
    # REFUSED block below, because a wave that reports only what it added hides the judgement.
    #
    # These are weighted toward DISCOVERY. The §33 arrivals counter reads 30/week against a
    # 160/week baseline, and the mechanism is visible here: the organs that RAISE findings have
    # had no scheduler since root cron OOM-died on 08-20.
    # ------------------------------------------------------------------------------------
    "scripts/run_fusion_search.py": "MT5/FUSION-NATIVE SEARCH -- the mandated universe's own "
                                    "searcher, scheduled by nothing; live rc=0 -> "
                                    "data/fusion_search.json",
    "scripts/graveyard_resurrect.py": "L1.16a re-open on a NAMED enabling change; live rc=0 -> "
                                      "data/graveyard_resurrection_queue.json",
    "scripts/hunt_source_alternatives.py": "the PERMANENT free-frontier hunt (RESEARCH §3); live "
                                           "rc=2 REGISTRY GAP 'zenn is DEAD with no registered "
                                           "alternatives'. max_audit reports last_free_dig 7.8d "
                                           "against a DAILY cadence -- this is that producer",
    "scripts/blindspot_prober.py": "unknown-unknown probing (L1.32); live rc=0 -> "
                                   "data/blindspot_probes.json",
    "scripts/run_mechanism_census.py": "mechanism supply census; live rc=0, 32 classes over 150 "
                                       "readable records, 0 unclassified",
    "scripts/report_mechanism_supply.py": "the census's report half; live rc=0 -> "
                                          "reports/mechanism_supply.json",
    "scripts/run_generation_diversity.py": "generator concentration (L1.32); live rc=0, most "
                                           "attempted carry/carry/months x20 -> data/gen_diversity.json",
    "scripts/mine_research_queue.py": "daily research-queue miner. NOTE: exceeded a 240s hand-run "
                                      "probe (rc=124), so it is a LONG organ, not a fast one -- "
                                      "the dispatcher detaches and its manifest row holds a flock, "
                                      "so a slow run blocks nothing. Listed with that measured "
                                      "runtime rather than an assumed one",
    "scripts/run_reality_gap.py": "L2.10 backtest->shadow->paper->live->venue-truth comparison; "
                                  "live rc=0, currently NO-DATA on two links and saying so",
    "scripts/run_execution_intel.py": "execution intel roll-up; live rc=0 DEGRADED "
                                      "(cost_drift=NO-DATA, fee_attribution=DEGRADED)",
    "scripts/score_forecasts.py": "L1.29 calibration; live rc=0. max_audit reports 20 forecasts "
                                  "past their grading deadline and this is what grades them",
    "scripts/run_organ_er.py": "the organ emergency room -- on a box with 36 abnormal unit stops "
                               "in 24h this is the triage desk; live rc=2 naming CRASHED "
                               "capability_hunt and BLOCKED kimi_hunter",
    "scripts/meta_research_review.py": "§12 meta-research review; live rc=0",
    "scripts/check_timidity_language.py": "L1.28/LAWS §2a timidity fence, repaired this cycle "
                                          "(it read one of the two files brain_env injects and "
                                          "declared a live law absent every run); live rc=1 now "
                                          "surfacing two REAL quota-caps in prompt surfaces",
    "scripts/check_calendar_gates.py": "L1.48 evidence-is-the-clock fence; live rc=1 with a "
                                       "declared denominator (36286 offered -> 1789 scanned)",
    "scripts/run_strategy_coverage.py": "L1.32 strategy breadth; live rc=0 naming THIN families "
                                        "(STATISTICAL-ARBITRAGE 1 tested, LEAD-LAG 2) -- the "
                                        "direct read on the 0.87 single-family concentration",
    "scripts/run_law_police.py": "law-enforcement audit; live rc=1 'FALL VANISHED "
                                 "test-suite-passfail' -> reports/law_police.json",
    "scripts/daily_research_cycle.py": "THE DAILY RESEARCH CYCLE ITSELF. Its root unit "
                                       "`quant-cro.service` was OOM-killed 2026-08-26 09:05 and "
                                       "is still `failed`; restarting it needs the console. Its "
                                       "cron row (02:00) has been dead since the 08-20 cron "
                                       "death, so NOTHING scheduled the desk's daily cycle at "
                                       "all. Verified running this cycle (110MB RSS) after "
                                       "`watchdog.py` respawned it by hand. The dispatcher's "
                                       "MIN_AVAIL_MB governor is the right home for it: it "
                                       "peaked 1.2G when the kernel took it, and a deferred run "
                                       "is strictly better than an OOM kill that picks a random "
                                       "victim. If the principal revives the root unit its 08:01 "
                                       "slot does not collide with this 02:00 one, and the row "
                                       "keeps its own flock either way",
    # ------------------------------------------------------------------------------------
    # REFUSED THIS WAVE, each with the reason it was refused. Recording these matters as much as
    # the additions: a token that was examined and rejected must not look like one nobody reached.
    #
    #   scripts/watchdog.py            REFUSED, and it is the important one. Its arms spawn
    #                                  `run_cashcarry_executor.py --live --capital 4500` and a
    #                                  public tunnel -- a LIVE CRYPTO EXECUTOR that LAWS §1 bans
    #                                  permanently and that the principal retired by order
    #                                  (b0fe6f50). Scheduling it would have the desk re-arming
    #                                  banned organs every 3 minutes. Its ONE valuable arm
    #                                  (respawning daily_research_cycle after an OOM kill, which
    #                                  it did when run by hand this cycle -- the CRO cycle is
    #                                  alive again because of it) needs extracting into a scoped
    #                                  organ before any of this can be scheduled. Carded.
    #   scripts/check_clock_provenance.py  input retired by the mandate: "Start the recorders:
    #                                  there is no tape to measure". No MT5 tape reaches it.
    #   scripts/check_crowding.py      crypto ground (universe 875 snapshots).
    #   scripts/run_fee_attribution.py crypto-era ledger (COOKIEUSDT, 1000CATUSDT, MOVEUSDT).
    #   (check_margin_topology.py stood here as "crypto venue topology" until wave 4 measured it
    #   live at rc=2 on an MT5 money-path quantity and ALLOWLISTED it above; the two entries then
    #   contradicted each other in one file, which is exactly the clash the wiring test refuses.
    #   The later, measured decision wins; the stale exclusion is gone.)
    #   scripts/check_partition_power.py  its partitions are funding_state/funding_breadth --
    #                                  crypto vocabulary; the FINDING is real but the axes are
    #                                  retired ground, so it needs MT5 partitions first.
    #   scripts/check_coverage_floors.py  precondition unmet standalone: it needs coverage.json
    #                                  from a --cov suite run, so on its own timer it would only
    #                                  ever print FileNotFoundError. Belongs after the suite.
    #                                  RE-EXCLUDED 2026-08-29 after being allowlisted at 01:21 the
    #                                  same day on the note "live rc=1 correctly reporting
    #                                  POPULATION CHANGED". That reading was taken while a --cov
    #                                  run's coverage.json happened to be on disk. Fired from a
    #                                  clean tree it printed `cannot read coverage.json
    #                                  (FileNotFoundError)` -- so the entry would have produced a
    #                                  permanent daily red at 05:22 that raises no floor and
    #                                  trains readers to skim, which is how a real one gets
    #                                  missed. VERIFY AN ORGAN FROM THE STATE ITS TIMER WILL FIND,
    #                                  never from the one your own cycle just built. It is not
    #                                  unscheduled: `quant-coverage-ratchet.timer` (Sun 01:00)
    #                                  runs ops/gates.sh --full, which produces coverage.json and
    #                                  then calls this script at ops/gates.sh:72-73 -- the only
    #                                  order in which it can say anything.
    #   scripts/run_execution_economics.py  exits 1 while still writing its artifact; that
    #                                  disagreement needs diagnosing before it is scheduled.
    # ------------------------------------------------------------------------------------
    "scripts/check_private_bisection.py": "live rc=0 -- guards against a private bar in front of "
                                          "the canonical ten (L1.60; two were deleted on 08-26)",
    "scripts/refresh_panel_roster.py": "live rc=0 -- 416 catalog models recorded. The desk-state "
                                       "hook reports LLM depth under-driven and names this script",
    # ------------------------------------------------------------------------------------
    # FOURTH WAVE, gap-fixer 2026-08-29. Every token below was RUN THIS CYCLE with its TRUE exit
    # code captured from the process -- the first two probe passes read `o=$(cmd|tail); rc=$?`,
    # which reports tail's status and graded a live traceback as rc=0, so the reasons here quote
    # a measurement the earlier method could not have made. Each is venue-agnostic or explicitly
    # MT5: rows whose output named a crypto instrument are listed in the exclusions below rather
    # than woken, because resurrecting a retired-universe organ is negative wiring, not wiring.
    # ------------------------------------------------------------------------------------
    "scripts/run_wiring_agent.py": "the desk's OWN wiring organ, dead 202h -- live rc=0 emitting "
                                   "AUTO-WIRE proposals (it named report_gate_audit.py, which "
                                   "this cycle repaired by hand). Wiring the wirer first is the "
                                   "highest-leverage row in this wave",
    "scripts/verify_backtest_engine.py": "live rc=0 'backtest-verify | PASS over 240 bars' -- the "
                                         "engine every certificate on this desk is computed by, "
                                         "and its verification had not run since 08-20",
    "scripts/run_geometric_review.py": "live rc=0 'GEOMETRIC GROWTH REVIEW -- E[log wealth], not "
                                       "backtest CAGR' over data/shadow. This is the objective "
                                       "function itself, reviewed by nothing for nine days",
    "scripts/run_type2_report.py": "live rc=0 -- ranks the weakest POWERED negatives (type-2 "
                                   "error). A desk that only counts rejections never learns "
                                   "which of them it lacked the power to make",
    "scripts/slot_budget_analysis.py": "live rc=0 'VERDICT: INCONCLUSIVE' over N=1..40, pi in "
                                       "[0.05,0.25], t in [2.5,4.0] -- pure simulation, no venue. "
                                       "It sizes the forward slot budget, and this cycle measured "
                                       "that observation count (not the 14-day clock) is what "
                                       "binds promotion, which is exactly this organ's question",
    "scripts/run_calibration_probe.py": "live rc=0 'UNINFORMATIVE -- Brier 0.2825 >= 0.25' -- the "
                                        "desk's stated probabilities are no better than the base "
                                        "rate, and L1.29 says a desk that never grades its "
                                        "forecasts has no calibration, only opinions",
    "scripts/run_research_lake.py": "live rc=0 '425 lake symbols; testing EURUSD, GBPUSD, USDJPY, "
                                    "USDCHF, USDCAD' -- explicitly MT5 ground",
    "scripts/compute_performance.py": "live rc=0 'wrote web/data.json candidates=308', top by "
                                      "Sharpe USDJPY:mean_reversion:vwap_reversion -- MT5",
    "scripts/measure_admission_power.py": "weekly (Mon 07:30), and the single most "
                                         "decision-relevant number produced this cycle. Run to "
                                         "completion 2026-08-29 after nine days dead: "
                                         "false-admission rate 37.1% on 420 pure nulls -> 155.8 "
                                         "admissible nulls per campaign against 12 forward "
                                         "slots. SATURATED -- the forward stage is occupied by "
                                         "noise and the discovery rate is ~zero however good the "
                                         "candidates are. 41min at nice 19, 350MB peak, weekly",
    "scripts/check_cost_surface.py": "live rc=0 over 3424 measured cells (535 unmeasured): 920 "
                                     "cells materially disperse from the pooled scalar, 676 "
                                     "undercharged and 244 OVERCHARGED. Cost is the bottleneck "
                                     "the objective says to route to, and it drifts both ways",
    "scripts/build_data_registry.py": "live rc=0 -- the registry of what the desk owns. "
                                      "check_claim_consistency reads it, and an unbuilt registry "
                                      "means 'the desk does not know what it owns'",
    "scripts/run_weekly_desk_grade.py": "live rc=0, dead 309h -- the weekly self-grade, including "
                                        "the L1.67 risk-units line. Weekly cadence, so nine days "
                                        "dead is more than a full missed cycle",
    # ------------------------------------------------------------------------------------
    # DELIBERATELY NOT ALLOWLISTED, each with the measurement that decided it. A backlog is only
    # honest when its exclusions are reasoned rather than merely un-chosen:
    #   check_coverage_floors.py -- rc=1 `cannot read coverage.json`. It CONSUMES a --cov run's
    #     output, so on its own timer it is a permanent red that means nothing. Its correct home
    #     is AFTER the suite, not beside it.
    #   check_free_roster.py, check_partition_power.py -- rc=124 at a 70s probe. Runtime is
    #     UNMEASURED, and scheduling an unbounded job on a 4GB no-swap box that OOM-killed cron
    #     is how the next outage starts. Measure first (L1.28a).
    #   check_clock_provenance.py -- rc=2 `no tape under data/moat`: honest, but it reports on
    #     RETIRED crypto ground and needs repointing at the MT5 tape before it says anything.
    #   check_crowding.py -- rc=2 FLAT-BOOK, 331 snapshots against a book holding nothing. Same
    #     class: vacuous until there is a live book, and a vacuous red trains readers to skim.
    #   check_kernel_log.py -- rc=2 UNREADABLE, no kernel-log channel visible to this user. A
    #     genuine finding (every "no OOM" claim on this box is uncheckable) but scheduling it
    #     would page daily about a permission the desk cannot grant itself.
    #   -- measured 2026-08-29, all rc=0 and all reading RETIRED crypto ground. Working code
    #      pointed at a universe LAWS s1 forbids hunting; each needs repointing at the MT5 tape
    #      before it is worth a slot, and waking it meanwhile would spend the box on banned
    #      ground while reporting healthy:
    #   run_decline_detection.py -- 'BNBUSDT 191 declines', 236 classified declines, all crypto.
    #   build_return_panel.py -- rejects BNBUSDT on overlap; the panel is a crypto cross-section.
    #   run_fee_attribution.py -- TSTUSDT fees, 'tape coverage 7.0%' of a retired venue's tape.
    #   screen_moat.py, run_moat_campaign.py, screen_orderbook_state.py -- all three block on
    #     data/moat, which holds only bybit/ and execution_tape/. The MT5 moat lives under
    #     desks/mt5/data (moat_coverage.json rebuilt today over 251 MT5 symbols), so these are
    #     orphaned by the universe migration rather than broken.
    #   snapshot_universe.py -- '882 symbols {TRADING: 751, SETTLING: 130}': venue statuses from
    #     a crypto exchange, against an MT5 registry of 251.
    #   run_paper_sleeve_spawner.py / run_paper_sleeve_forward.py -- a SECOND forward loop, fed
    #     by conv_* crypto screens. L1.58 mandates ONE shadow/forward engine for ALL lanes and
    #     calls a lane that builds its own "a defect on sight"; the MT5 engine is the one.
    #   vault_search.py -- UNRUNNABLE AS SCHEDULED: the manifest fires it with no arguments and
    #     the tool requires a positional query, so every scheduled run since the row was written
    #     has exited 2 on an argparse usage message. A query tool has no cadence to have.
    # ------------------------------------------------------------------------------------
}

#: THE BOX IS THE BINDING CONSTRAINT, AND IT IS NOT TIMIDITY TO SAY SO (measured 2026-08-26:
#: 3814MB total, ZERO swap, ~1660MB available, load 1.9). Three gap-wirer seats and the
#: same-day external pipeline were OOM-killed in the 24h before this was written. Firing a
#: batch of organs into that headroom can take the kernel's OOM killer to `quant-live-guard`
#: or the executor, which is a ruin path, not an inconvenience -- so the governor below names
#: the ruin probability it reduces, as the survival rails require of every clamp.
#: A deferred row is NEVER dropped: it lands in `pending` and fires on a later tick when the
#: headroom returns. Silent truncation would read as "the fleet is covered" when it is not.
def _wrap_for_rc(cmd: str, token: str, at: str) -> str:
    """Append the row's EXIT CODE to data/fence_outcomes.jsonl once it finishes.

    THE DEFECT THIS ENDS (2026-08-29). This dispatcher fires ~30 fences that exit 2 on a real
    finding -- check_organ_liveness DARK, check_bar_span CONTAMINATED, check_calibration
    OVERDUE -- and detaches with stdout/stderr to DEVNULL. Nothing collected the exit codes, so
    every one of those verdicts existed only inside a log that no organ read, and the desk
    learned a fence was red only when a human happened to run it by hand. A fence that fails
    loud into a void is indistinguishable from a fence that passes.

    The row keeps its own flock/redirects untouched; `$?` is captured on the very next line, so
    it is the ROW's status and not the appender's. Token and timestamp are dispatcher-owned
    strings (a repo-relative path and an ISO stamp), so single-quoting them is safe.
    """
    # The row runs in a SUBSHELL. A row sealed with `exit $?` -- the house pattern that stops
    # bash re-reading a rewritten script mid-run (ops/run_recommendation_worker.sh) -- would
    # otherwise terminate this shell BEFORE the appender line, and a row that records no
    # outcome at all reads downstream as "not red", which is absence mistaken for a clean
    # verdict (L1.28a). The subshell makes `exit` end the row, not the recording.
    return (f"( {cmd}\n )\n"
            "__rc=$?\n"
            "printf '{\"token\":\"%s\",\"at\":\"%s\",\"rc\":%s}\\n' "
            f"'{token}' '{at}' \"$__rc\" >> '{OUTCOMES}'\n")


def red_rows(within_h: float = 26.0, now: datetime | None = None) -> dict[str, dict[str, object]]:
    """Latest non-zero exit per token inside the window -- the dispatcher's OWN red list.

    Keyed by token and keeping only the LATEST outcome per token, so a fence that has since
    gone green stops being reported. Absence of the file is UNMEASURED, which reads here as an
    empty dict AND is why the caller reports the file's own age alongside the count (L1.28a).
    """
    now = now or datetime.now(UTC)
    latest: dict[str, dict[str, object]] = {}
    try:
        lines = OUTCOMES.read_text("utf-8").splitlines()[-4000:]
    except OSError:
        return {}
    for line in lines:
        try:
            row = json.loads(line)
            at = datetime.fromisoformat(str(row["at"]))
        except Exception:
            continue
        if (now - at).total_seconds() / 3600.0 > within_h:
            continue
        tok = str(row.get("token", ""))
        prev = latest.get(tok)
        if prev is None or str(prev["at"]) <= str(row["at"]):
            latest[tok] = {"rc": row.get("rc"), "at": row.get("at")}
    return {t: v for t, v in latest.items() if v.get("rc") not in (0, "0")}


def outcome_coverage(within_h: float = 26.0, now: datetime | None = None) -> int:
    """How many DISTINCT tokens reported any outcome in the window -- the red list's denominator.

    Without it `red_rows_n: 0` is ambiguous between "every fence passed" and "nothing has been
    recorded yet", and those two must never render identically (L1.28a). A reader that sees
    0 red over 0 recorded is looking at an UNMEASURED fleet, not a healthy one.
    """
    now = now or datetime.now(UTC)
    seen: set[str] = set()
    try:
        lines = OUTCOMES.read_text("utf-8").splitlines()[-4000:]
    except OSError:
        return 0
    for line in lines:
        try:
            row = json.loads(line)
            at = datetime.fromisoformat(str(row["at"]))
        except Exception:
            continue
        if (now - at).total_seconds() / 3600.0 <= within_h:
            seen.add(str(row.get("token", "")))
    return len(seen)


MIN_AVAIL_MB = 420           # below this, defer rather than fire (kernel OOM territory)
MAX_FIRES_PER_TICK = 4       # burst cap: a 5-minute tick never thunders the whole manifest
PENDING_MAX_AGE_MIN = 180    # past this a deferred row is REPORTED as starved (it is not dropped)
#: A DEFERRAL MUST NEVER BECOME A SILENT DEATH (gap-fixer 2026-08-29). PENDING_MAX_AGE_MIN used
#: to DROP the row -- "wait for its next natural slot, never thunder" -- and for a row that fires
#: every five minutes that is free, because its next slot is five minutes away. For a low-frequency
#: row it is fatal: deferred by the memory governor, dropped after 3h, next slot 24h or 7d later,
#: box still under MIN_AVAIL_MB, deferred and dropped again, forever, leaving no trace anywhere.
#:
#: MEASURED 2026-08-29: exactly 7 allowlisted rows had stale logs, and EVERY ONE was monthly,
#: weekly or daily -- not one high-frequency row was affected. That is the signature of this
#: mechanism, not of a broken schedule: a row with twelve chances an hour eventually finds a tick
#: with memory above the floor; a weekly row gets one chance and never does. The seven were the
#: coverage-floor ratchet raiser (dead 213h -- the L1.50 stall the desk state prints every
#: session), the prompt ratchet (220h), the weekly gap re-ranker (282h), the panel roster
#: refresher (285h -- the "under-driven seats" line), the mechanism-supply report (307h), the
#: graveyard resurrector (310h) and the event-calendar builder, which had NEVER run.
#:
#: A pending row is now retried every tick until it either FIRES or its own next slot arrives
#: (at which point `due` carries it and dropping loses nothing). The governor still delays work;
#: it can no longer destroy it. STARVED_DROP_MIN is a bound on state growth, not a policy, and
#: reaching it is recorded in `starved` rather than swallowed.
STARVED_DROP_MIN = 60 * 24 * 8   # 8 days -- a safety bound so a broken spec cannot pin a row

TOKEN_RE = re.compile(r"(?:scripts|deploy|ops)/[A-Za-z0-9_./-]+\.(?:py|sh)")


def parse_field(expr: str, lo: int, hi: int) -> set[int]:
    """One cron field -> the set of matching values. Supports * a a-b a-b/n */n lists."""
    vals: set[int] = set()
    for part in expr.split(","):
        step = 1
        if "/" in part:
            part, step_s = part.split("/", 1)
            step = int(step_s)
        if part == "*":
            rng = range(lo, hi + 1)
        elif "-" in part:
            a, b = part.split("-", 1)
            rng = range(int(a), int(b) + 1)
        else:
            v = int(part)
            rng = range(v, v + 1)
        vals.update(v for v in rng if (v - rng.start) % step == 0)
    if hi == 7 and 7 in vals:  # cron dow: 7 == Sunday == 0
        vals.discard(7)
        vals.add(0)
    return vals


def cron_matches(spec: str, t: datetime) -> bool:
    """Vixie-cron semantics: if BOTH dom and dow are restricted, either may match."""
    f = spec.split()
    if len(f) != 5:
        return False
    minute, hour, dom, month, dow = f
    if t.minute not in parse_field(minute, 0, 59):
        return False
    if t.hour not in parse_field(hour, 0, 23):
        return False
    if t.month not in parse_field(month, 1, 12):
        return False
    dom_ok = t.day in parse_field(dom, 1, 31)
    dow_ok = ((t.weekday() + 1) % 7) in parse_field(dow, 0, 7)  # cron: 0=Sunday
    if dom != "*" and dow != "*":
        return dom_ok or dow_ok
    return dom_ok and dow_ok


def _avail_mb() -> float:
    """MemAvailable in MB, or +inf when it cannot be read.

    FAILING OPEN IS THE RIGHT DIRECTION HERE and it is a deliberate choice, not an oversight:
    this governor exists to protect a 3.8GB swapless box from an OOM cascade, but a governor
    that cannot read memory and therefore refuses to fire ANYTHING would silently re-create
    the exact outage it was built to end -- 200 organs dead and no one told. An unreadable
    /proc/meminfo is a broken probe, and a broken probe must not be allowed to hold the fleet
    down; the OOM killer is a survivable event, six silent days is not.
    """
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 1024.0
    except (OSError, ValueError, IndexError):
        pass
    return float("inf")


def manifest_rows() -> list[tuple[str, str, str]]:
    """(cron_spec, command, token) for every active manifest row that names a script."""
    rows: list[tuple[str, str, str]] = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" in line.split(" ", 1)[0]:
            continue
        parts = line.split(None, 5)
        if len(parts) < 6:
            continue
        spec, cmd = " ".join(parts[:5]), parts[5]
        m = TOKEN_RE.search(cmd)
        if m:
            rows.append((spec, cmd, m.group(0)))
    return rows


def twinned_tokens() -> set[str]:
    """Script tokens already referenced by an installed user unit -- never double-fire those."""
    tokens: set[str] = set()
    if USER_UNITS.is_dir():
        for unit in USER_UNITS.glob("*.service"):
            try:
                text = unit.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            tokens.update(TOKEN_RE.findall(text))
    return tokens


def due_times(spec: str, since: datetime, until: datetime) -> list[datetime]:
    t = since.replace(second=0, microsecond=0) + timedelta(minutes=1)
    out = []
    while t <= until:
        if cron_matches(spec, t):
            out.append(t)
        t += timedelta(minutes=1)
    return out


#: How far back a missed slot is still worth making up. 35 days covers the monthly rows; past
#: that a "catch-up" is archaeology, not scheduling.
CATCHUP_LOOKBACK_DAYS = 35


def last_slot_at_or_before(spec: str, now: datetime,
                           max_days: int = CATCHUP_LOOKBACK_DAYS) -> datetime | None:
    """The most recent time this spec was due, or None inside the lookback.

    Walks BACKWARDS and stops at the first match, so a daily row costs at most 1440 steps and a
    weekly one 10,080 -- and it is only ever called for a row that already looks overdue, so the
    cost falls to zero as the backlog drains.
    """
    t = now.replace(second=0, microsecond=0)
    for _ in range(max_days * 24 * 60):
        if cron_matches(spec, t):
            return t
        t -= timedelta(minutes=1)
    return None


def main() -> int:
    now = datetime.now(tz=UTC)
    state: dict[str, object] = {}
    if STATE.is_file():
        try:
            state = json.loads(STATE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            state = {}
    last_check = now - timedelta(minutes=5)
    if state.get("last_check"):
        with contextlib.suppress(ValueError):
            last_check = datetime.fromisoformat(state["last_check"])
    last_check = max(last_check, now - timedelta(minutes=CATCHUP_CAP_MIN))

    twins = twinned_tokens()
    fired: list[str] = []
    skipped_twinned: list[str] = []
    deferred: list[str] = []
    uncovered_tokens: set[str] = set()
    rows = manifest_rows()

    # THE TWIN CHECK RUNS FIRST NOW. It used to run AFTER `uncovered += 1`, so any row that
    # already had a real user timer -- run_moat_backup, run_live_guard, run_drills, certify_
    # gauntlet and 11 others -- was counted as part of the dead backlog it had already left.
    # The published figure was 216 uncovered of 228; the true dead set is 201. A backlog gauge
    # that counts healed rows as sick can never reach zero, so the ratchet it feeds could never
    # close (L1.50) and the number could never be trusted enough to act on.
    due: list[tuple[str, str, str]] = []
    for spec, cmd, token in rows:
        if token in twins:
            skipped_twinned.append(token)
            continue
        if token not in ALLOWLIST:
            uncovered_tokens.add(token)
            continue
        try:
            if not due_times(spec, last_check, now):
                continue
        except ValueError:
            continue  # malformed spec on an allowlisted row: never crash the whole dispatcher
        due.append((token, cmd, spec))

    # PERSISTENT=TRUE, WHICH EVERY SYSTEMD TIMER ON THIS BOX HAS AND THIS DISPATCHER DID NOT.
    # `due` only ever looks at the last few minutes (CATCHUP_CAP_MIN=20), so a slot missed while
    # the dispatcher was down -- or missed because the row was not yet ALLOWLISTED -- is never
    # made up: the organ simply waits a full period. For a weekly or monthly row that is the
    # whole defect. MEASURED 2026-08-29: seven organs, dead 213-310h (one had NEVER run), were
    # allowlisted on 08-26/08-27 specifically to resurrect them, and every one had had ZERO
    # slots since, because their next slot was Sunday, Monday or September 1st. The allowlist
    # entry LOOKED like the repair and the register recorded it as one, while the organ stayed
    # dead for up to five more days. An allowlist entry is not a run (III.16, one level up).
    #
    # A row is overdue when its most recent slot has passed and it has not fired since. It is
    # made up ONCE, behind everything genuinely due, and still under the burst cap and the
    # memory governor -- so a long outage drains at 4 per tick instead of thundering.
    fired_at: dict[str, str] = {
        t: str(r.get("last_fired", "")) for t, r in (state.get("rows") or {}).items()
        if isinstance(r, dict)}
    overdue: list[tuple[str, str, str]] = []
    for spec, cmd, token in rows:
        if token in twins or token not in ALLOWLIST or token in {d[0] for d in due}:
            continue
        stamp = fired_at.get(token)
        if stamp:
            try:
                if datetime.fromisoformat(stamp) >= now - timedelta(hours=25):
                    continue          # fired recently: cheap filter before the backwards scan
            except ValueError:
                pass
        slot = last_slot_at_or_before(spec, now)
        if slot is None:
            continue                  # no slot inside the lookback: nothing was missed
        try:
            if stamp and datetime.fromisoformat(stamp) >= slot:
                continue              # already ran for that slot
        except ValueError:
            pass
        overdue.append((token, cmd, spec))

    # Rows deferred by a previous tick's governor come first: they are already late, and the
    # whole point of the pending queue is that a governor delays work rather than losing it.
    pending: dict[str, dict[str, str]] = dict(state.get("pending") or {})
    due_tokens = {t for t, _, _ in due}
    starved: dict[str, float] = dict(state.get("starved") or {})
    held: list[str] = []
    replay: list[tuple[str, str, str]] = []
    for token, row in list(pending.items()):
        try:
            since = datetime.fromisoformat(str(row.get("since")))
        except (TypeError, ValueError):
            pending.pop(token, None)
            continue
        if token in due_tokens:
            pending.pop(token, None)   # its own slot came round; `due` carries it, nothing is lost
            continue
        waited = (now - since).total_seconds() / 60.0
        if waited > STARVED_DROP_MIN:
            # The bound, not the policy. Recorded, never swallowed: nine days of dropped daily
            # organs previously left `deferred_this_run: []` and `pending: {}` -- a healthy-looking
            # artifact over a dead fleet, which is how this went unseen (L1.28a).
            starved[token] = round(waited / 60.0, 1)
            pending.pop(token, None)
            continue
        if waited > PENDING_MAX_AGE_MIN:
            held.append(token)
        replay.append((token, str(row.get("cmd", "")), str(row.get("spec", ""))))
    queue = (replay + [d for d in due if d[0] not in pending]
             + [o for o in overdue if o[0] not in pending])

    for token, cmd, spec in queue:
        if len(fired) >= MAX_FIRES_PER_TICK or _avail_mb() < MIN_AVAIL_MB:
            deferred.append(token)
            pending[token] = {"cmd": cmd, "spec": spec, "since": pending.get(token, {}).get(
                "since", now.isoformat(timespec="seconds"))}
            continue
        subprocess.Popen(["/bin/sh", "-c",
                          _wrap_for_rc(cmd, token, now.isoformat(timespec="seconds"))], cwd=ROOT,
                         env={"PATH": "/usr/bin:/bin", "HOME": str(Path.home()),
                              "QUANT_ROOT": str(ROOT)},
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        fired.append(token)
        pending.pop(token, None)
        row_state = state.setdefault("rows", {}).setdefault(token, {})
        row_state["last_fired"] = now.isoformat(timespec="seconds")
        row_state["fires"] = int(row_state.get("fires", 0)) + 1

    state["last_check"] = now.isoformat(timespec="seconds")
    state["fired_this_run"] = fired
    state["deferred_this_run"] = deferred
    state["pending"] = pending
    state["avail_mb"] = _avail_mb()
    reds = red_rows(now=now)
    state["red_rows"] = reds
    state["red_rows_n"] = len(reds)
    state["outcomes_recorded_n"] = outcome_coverage(now=now)
    state["skipped_twinned"] = sorted(set(skipped_twinned))
    state["uncovered_unallowed"] = len(uncovered_tokens)
    # The COUNT alone is not actionable -- the next seat needs to know WHICH organs are dead
    # without re-deriving it. The list is what turns this artifact from a number into a queue.
    state["uncovered_tokens"] = sorted(uncovered_tokens)
    # A GOVERNOR THAT DELAYS MUST SAY SO. `held` is rows the memory floor has been holding
    # back past PENDING_MAX_AGE_MIN and `starved` is rows it held past the bound -- the two
    # numbers whose absence let a nine-day fleet outage read as a healthy dispatcher.
    state["held_by_governor"] = sorted(held)
    state["overdue_caught_up"] = sorted(o[0] for o in overdue)
    state["starved"] = starved
    state["allowlisted"] = len(ALLOWLIST)
    state["manifest_rows_seen"] = len(rows)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8")
    if fired:
        print(f"manifest-dispatch: fired {fired}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
