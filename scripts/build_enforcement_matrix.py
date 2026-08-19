"""CONSTITUTION -> ENFORCEMENT MATRIX -- makes every principle auditable (EXECUTION_QUEUE rank 2).

THE GAP THIS CLOSES. The desk carries 42 constitutional principles (L1.x/L2.x) and 57 mechanical
fences in `scripts/max_audit.py`, and NOTHING mapped one to the other. So two failure directions
were both invisible:

  UNENFORCED PRINCIPLE  -- a law with no fence is prose. It cannot fire, cannot fail a cycle, and
                           degrades silently into decoration. Every defect found on 2026-07-30 was
                           of exactly this shape: a principle everyone agreed with, enforced by
                           nobody (capacity parity was written in L1.18 while a $100k floor ran in
                           the gauntlet; L2.9 activate-the-unused was written while 171 capabilities
                           sat dormant).
  UNJUSTIFIED FENCE     -- a check with no governing principle is complexity nobody voted for. It
                           consumes cycle time and its failures have no authority behind them.

This emits `data/enforcement_matrix.json`:
    principle -> requirement -> fences -> code_paths -> scheduler -> tests -> evidence -> status

STATUS is deliberately blunt: ENFORCED (>=1 fence or a named runtime mechanism) / UNENFORCED /
HUMAN-ONLY (a law only a person can satisfy -- key custody, licence rulings; a fence would be
theatre) / STANDING (a review cadence rather than a check).

IT FAILS THE BUILD on an unenforced principle, because a matrix that merely REPORTS gaps is the
same category of decoration it exists to detect.

Pure stdlib. Run from repo root.
    python scripts/build_enforcement_matrix.py [--json] [--report-only]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_CONST = _ROOT / "docs/CONSTITUTION.md"
_MASTER = _ROOT / "docs/MASTER_QUANT_CONSTITUTION.md"
_AUDIT = _ROOT / "scripts/max_audit.py"
_MANIFEST = _ROOT / "ops/crontab.manifest"
_OUT = _ROOT / "data/enforcement_matrix.json"

# principle -> the fences / runtime mechanisms that enforce it. Hand-mapped ONCE because the link
# is semantic (a fence name does not contain its principle id), then kept honest by this script:
# any principle absent from this map with no keyword hit is reported UNENFORCED and fails the run.
_MAP: dict[str, list[str]] = {
    "L1.1": ["check_production", "check_gate_optimality"],
    "L1.2": ["check_directives"],
    "L1.3": ["check_data_utilization", "check_generation"],
    "L1.4": ["run_reality_gap.py", "check_forensics_fresh", "check_carry_funding_measured"],
    # R0276 adds the scheduled-event deferral. L1.5 is EXECUTION PHYSICS: a stop is priced as the
    # loss it caps, and across a scheduled repricing it is not -- the gap jumps straight through
    # the level the whole size was derived from. build_event_calendar.py supplies the windows the
    # conviction sleeve defers entries across. It DEFERS, never kills, so it costs no statistical
    # power and is not a bar.
    "L1.5": ["run_cost_model.py", "check_carry_funding_measured", "run_execution_intel.py",
             "scripts/build_event_calendar.py", "libs/execution/event_guard.py"],
    "L1.6": ["libs/autodiscovery/validation.py", "check_welded_gates", "check_gate_optimality",
             "run_mutation.py"],
    "L1.7": ["check_rubberstamp_detector", "check_rubberstamp_enforcement", "deep_review.py"],
    # R0270 adds the EXTRACTION-side non-regression fence beside the acquisition-side ones. L1.8
    # ends "idle ingested data is a defect", and a campaign that truncates its history to the
    # shortest candidate leaves observations already on disk untested -- idle data manufactured by
    # the validator rather than by a lazy collector. check_campaign_retention.py floors the share
    # a campaign actually tests on, so the 82.9% min-length discard cannot come back in silence.
    # THE `scripts/` PREFIX IS THE HOUSE STYLE AND IS NO LONGER LOAD-BEARING (R0436, fixed).
    # `_exists` used to short-circuit any ref starting with `check_` into max_audit's FUNCTION
    # table, so the bare `check_campaign_retention.py` form resolved against a registry a
    # standalone script can never be in and reported BROKEN-REF without saying why. It now
    # discriminates on the `.py` suffix -- which a function name cannot carry -- so both forms
    # resolve. Path-first is kept everywhere here because it says WHERE the fence lives at a
    # glance; the suffixless `check_campaign_retention` form is still a function-table request
    # and still fails, now with a hint that names the suffix.
    "L1.8": ["check_no_mining_throttle", "check_mining_nonregression", "check_mine_flow",
             "scripts/check_campaign_retention.py", "libs/research/campaign_retention.py"],
    "L1.9": ["check_blind_trigger", "check_interrogation", "check_dig_depth"],
    "L1.10": ["check_mine_conversion", "check_mine_gate"],
    # R0316 adds HISTORICAL MONOPOLISATION, which L1.11 names outright and nothing implemented.
    # A point-in-time history is the cheapest proprietary state available: everyone can fetch M2SL,
    # almost nobody keeps what it SAID last month. FRED serves only the current vintage, so the
    # archive was overwritten AND truncated to a rolling window on every run -- each day destroying
    # a vintage that cannot be re-earned at any price, which is the one currency the desk cannot
    # buy back. Measured on the RFB Brazil panel: 42/42 months revised between vintages, worst
    # +40.9%, systematically upward. The store makes the daily overwrite lossless and turns "this
    # source is revised" from a disqualification into a dataset.
    "L1.11": ["moat_audit.py", "check_vendor_replacement", "run_recorder.py",
              "libs/research/vintage.py", "scripts/collect_fred_macro.py",
              "scripts/harvest_rfb_vintages.py",
              "tests/research/test_vintage.py"],
    # L1.11a ranks ground by REVERSE-ENGINEERING COST PER UNIT OF EFFORT, and delisted rosters are
    # the cheapest high-cost ground the desk had never asked for: R0239's own docstring routed the
    # backward half of survivorship to "a reconstruction from binance.vision archives, a separate
    # and much larger job", while three venues publish their dead instruments outright. One call
    # each returned 4455 names (bitmex 3077 vs 32 live, bybit 936 vs 808, coinbase 315 vs 517) --
    # accessibility was the barrier, and L1.11a says a barrier is a search dimension.
    # The same argument one format across (R0317): a legacy `.xls` is an ACCESSIBILITY barrier, and
    # government, regulator and central-bank publications are disproportionately served as one
    # PRECISELY because they are old institutional pipelines -- which is the same reason they stay
    # under-mined. The desk had recorded "this box cannot read .xls" (no xlrd/openpyxl/olefile,
    # installs frozen) as a fact about the world; it was a fact about a missing library. OLE2+BIFF8
    # are two documented byte-level layers and the stdlib ships `struct`, so the moat here is made
    # of tedium rather than secrecy -- maximum reverse-engineering cost per unit of effort.
    "L1.11a": ["ops/run_frontier_rotation.sh", "kimi_hunter.py",
               "scripts/probe_delisted_instruments.py",
               "tests/scripts/test_probe_delisted_instruments.py",
               "scripts/read_xls.py", "libs/data/xls_reader.py",
               "tests/data/test_xls_reader.py"],
    "L1.12": ["check_orphan_code", "check_idle_capability", "libs/self_improvement/dormancy.py"],
    "L1.13": ["check_gap_register_health", "run_execution_intel.py"],
    "L1.14": ["check_directives", "research_erv.py"],
    "L1.15": ["check_self_application"],
    # L1.16: every edge understood -- mechanism, regime, failure modes -- or it is not durable.
    # screen_carry_basis_path is the attribution instrument for the ONLY deployed sleeve: it
    # measures whether the funding-rank entry selects into a widening or converging basis, which
    # is what decides whether the carry harvest is a cashflow or compensation for a basis loss.
    "L1.16": ["mechanism_board.py", "check_gate_optimality",
              "scripts/screen_carry_basis_path.py"],
    "L1.17": ["negative_knowledge.py", "check_findings_ratchet", "docs/graveyard.md"],
    "L1.18": ["tests/validation/test_capacity_parity.py"],
    "L1.18a": ["tests/validation/test_capacity_parity.py",
               "libs/autodiscovery/validation.py:capacity_status",
               "scripts/run_promotion_queue.py", "libs/research/promotion_latency.py"],
    "L1.16a": ["negative_knowledge.py", "check_findings_ratchet"],
    # L1.19 is "hunt replacements BEFORE advantages die". probe_bybit_archive is that rule applied
    # to an advantage the desk has not yet TAKEN: a free 349-day first-party L2 archive that may
    # or may not be on rolling retention. Whether free history is expiring is a decay question,
    # and it was answered by INFERENCE in a sweep doc until the probe measured it (FIXED, boundary
    # 2025-08-21 unmoved 08-01 -> 08-05 while the span grew 345 -> 349 days).
    "L1.19": ["revalidate_clocks.py", "libs/research/dist_shift.py",
              "scripts/probe_bybit_archive.py",
              "tests/scripts/test_bybit_archive_probe.py"],
    "L1.20": ["check_post_gate0_activation", "check_production"],
    "L1.21": ["check_depth_parity", "check_coverage"],
    "L1.22": ["run_intelligence_cycle.py", "check_self_application", "check_self_sufficiency"],
    "L1.23": ["run_deadman_switch.py (Tier-3)", "libs/risk/gate.py", "check_production",
              "scripts/run_drills.py", "libs/risk/capital_events.py",
              # the moat is capital in information form: replicas drilled on every run, disk
              # fuse fails loud ~14 days before the 80% guard would start eating the moat
              "scripts/run_moat_backup.py"],
    "L1.24": ["run_intelligence_cycle.py", "check_idle_capability", "check_data_utilization"],
    "L1.25": ["check_welded_gates", "check_gate_optimality", "check_rejection_shadow"],
    "L1.26": ["research_erv.py", "check_directives"],
    "L1.27": ["check_verify_lag", "check_carryover_skipped"],
    "L2.1": ["check_prompt_layer", "ops/principal_doctrine.txt"],
    "L2.2": ["scripts/max_audit.py (all 57 fences)"],
    "L2.3": ["recommendations.py", "check_directives"],
    "L2.4": ["check_rubberstamp_detector", "check_rubberstamp_enforcement"],
    "L2.5": ["blind_spot.py", "check_self_sufficiency",
             # R0093: the principal's order channel feeds the origin gauge mechanically --
             # a doctrine edit IS a principal-found gap, logged the day it lands.
             "scripts/check_doctrine_diff.py"],
    "L2.6": ["run_trade_forensics.py", "check_forensics_fresh", "research_autopsy.py"],
    "L2.7": ["recommendations.py", "check_directives"],
    "L2.9": ["libs/self_improvement/dormancy.py", "run_intelligence_cycle.py",
             "check_idle_capability", "check_orphan_code"],
    "L2.10": ["run_reality_gap.py", "libs/research/dist_shift.py"],
    "L2.8a": ["scripts/check_constitution_core.py", "tests/governance/test_constitution_core.py",
              "data/constitution_core.lock"],
    # L1.21a is a bar on the ORGANS' reasoning, not on an artifact, so its enforcement is the
    # injection path: it is in principal_doctrine.txt, which check_prompt_layer proves reaches
    # every claude invocation and check_universal_doctrine proves no organ omits.
    "L1.21a": ["ops/principal_doctrine.txt", "check_prompt_layer", "check_universal_doctrine"],
    # L1.28 fences the CONSTITUTION's own language: every scope restraint must state its non-timid
    # reading, or an organ reading it defaults to doing less.
    "L1.28": ["scripts/check_timidity_language.py", "tests/governance/test_timidity_fence.py",
              "ops/principal_doctrine.txt"],
    # L1.28a is measured, not asserted: every ceiling reports utilisation or counts as zero.
    # R0318 adds the extractor case, where the absence-reads-as-health failure is at its sharpest:
    # `all([])` is True, so a hand-rolled parse that returned nothing but headers scores "0
    # violations" and the report reads as a clean bill. check_identities refuses that -- zero
    # usable rows is UNMEASURED, and the count of rows the law actually closed over is a
    # first-class output rather than a footnote.
    "L1.28a": ["scripts/check_utilisation.py", "check_idle_capability", "check_clock_saturation",
               "check_capacity_runway", "libs/research/conservation.py",
               "tests/research/test_conservation.py",
               "scripts/check_extractor_invariants.py",
               "libs/research/extractor_invariants.py"],
    # L1.28b: conversion hunts 100% daily -- FLATLINE (7d of silence on a non-empty queue) fails.
    # The fence DETECTS the debt; the actuator is what makes the law's own remedy -- (d) "flips
    # the next audit/brain window from finding to fixing" -- actually reach an organ (L1.36).
    # Both are listed because a law enforced only by a detector is half-enforced: the flag was
    # published for weeks with no consumer that changed any behaviour.
    # ship_restart is the REPAIR half of the desk's most expensive detection. max_audit's
    # check_stale_daemons has fired correctly on all three stale-code instances (2026-07-10,
    # 07-26, 08-05) and every one shipped only when a human happened to look, because the
    # restart needs a systemctl this box denies. Detection without an actuator IS the L1.28b
    # defect; this is the actuator.
    "L1.28b": ["scripts/check_conversion.py", "libs/ops/repair_mode.py", "ops/brain_env.sh",
               # run_stale_daemon_repair closes the remaining half-gap: ship_restart was an
               # actuator a HUMAN still had to invoke; this invokes it on the detector's own
               # verdict (cron 2x/day), with TIER_RUIN and the L1.38 sterile window as the two
               # hard skips. Detection -> repair now needs nobody awake.
               "scripts/ship_restart.py", "scripts/run_stale_daemon_repair.py",
               # R0330: check_conversion measures the QUEUE, this measures the CAPACITY that
               # drains it. A long queue is equally consistent with fast repair under heavy
               # arrival and slow repair under light arrival, so queue length alone cannot say
               # whether repair capacity is improving -- which is the comparison L1.28b is
               # written from. MTTR is censoring-aware; P(fix) excludes rejections on purpose.
               "scripts/check_repair_capacity.py", "libs/research/repair_capacity.py"],
    # L1.28c: every cadence hunts its own ceiling. The manifest fence requires a decided cadence
    # with evidence per line; brain_seat_throughput measures the resource they all compete for,
    # so "raise the cron" vs "buy a second seat" is settled by measurement.
    # run_cadence.py IS the cadence engine this law governs, and it was mapped by NOTHING -- so
    # the one organ that decides what fires and enforces the never-sleepier floors was also the
    # one organ outside the build standard and the L1.42 law boundary (R0425).
    "L1.28c": ["scripts/check_scheduler_manifest.py", "scripts/check_utilisation.py",
               "scripts/run_cadence.py"],
    # L1.29: the desk scores its own confidence or its confidence is fiction. The fence fails
    # on ungraded predictions; the shrinkage closes the loop back into sizing/promotion.
    "L1.29": ["scripts/check_calibration.py",
              "libs/self_improvement/forecast_calibration.py"],
    # L1.30: births vs deaths of validated edges -- the number that sets terminal wealth.
    "L1.30": ["scripts/check_replacement_rate.py"],
    # L1.31: two model families hunt the missing capability daily AND one builds it. The organ
    # is the fence: check_organs catches it going quiet, and its artifacts are dated evidence.
    "L1.31": ["scripts/run_capability_hunt.py", "ops/run_capability_hunt.sh", "check_organs"],
    # L1.32: the unknown-unknown organs measured as ONE family -- DARK when any has never
    # produced. L1.33: the GPT seat as standing partner on every one of them.
    "L1.32": ["scripts/check_exploration.py"],
    "L1.33": ["libs/research/second_family.py", "scripts/run_capability_hunt.py"],
    # L1.34: source-class universality reaches the seats through their PROMPTS, so the fence is
    # the prompt-layer wire that proves every brief carries it (same shape as L1.21a).
    "L1.34": ["ops/frontier_en_prompt.txt", "scripts/kimi_hunter.py", "check_prompt_layer",
              "tests/governance/test_source_universality.py"],
    # L1.35: the hunters are the never-finished organ. Fenced by the mandate's presence in every
    # brief, the family-level exploration fence, and the productivity ratchet that catches an
    # organ going quiet whatever reason it gives.
    "L1.35": ["tests/governance/test_source_universality.py", "scripts/check_exploration.py",
              "check_organs", "scripts/check_ratchets.py"],
    # L1.36: families enforced AS families -- complete, fenced per member, reaching every organ
    # via the doctrine, and guarded by a family-level check. A gate, not a report.
    "L1.36": ["scripts/check_law_families.py"],
    # L1.37: the gate itself -- four boundaries (organ spawn, pre-push, CI, hourly cron).
    # L1.37 carries the BOUNDARIES themselves, and check_birth_properties is the §36/L2.9
    # birth-property predicates moved onto them. They ran at 07:00 on cron and nowhere else, so
    # four defect keys (artifact-ungoverned 6x, orphan-scripts 4x, mine-conversion-unbacked 3x,
    # decision-ledger-undated 2x) recurred by construction: the object was authored, committed and
    # pushed, and the question "why does this file exist?" reached a session that had to
    # reconstruct the answer from cold hours later. Same predicates, one source of truth
    # (max_audit's tables are imported, never copied) -- only the boundary is new.
    "L1.37": ["scripts/run_law_gate.py", "deploy/git_hooks/pre-push", "ops/brain_env.sh",
              ".github/workflows/ci.yml", "scripts/check_birth_properties.py",
              "tests/ops/test_birth_properties.py"],
    # L1.38: the money path freezes to IMPROVEMENTS (never repairs) inside launch/first-fills/
    # rail-breach windows. Part of the survival family in spirit; fenced standalone.
    "L1.38": ["scripts/check_change_window.py"],
    # L1.39: zero idle findings -- every finding routes to its next stage immediately. The
    # principle unifies the two existing enforcers (cross-session + same-run); no new fence.
    "L1.39": ["scripts/check_conversion.py", "ops/principal_doctrine.txt",
              "scripts/check_law_families.py"],
    # L1.40: endless generation + defect lenses on the same 6x/day rotation, fixed in-run.
    "L1.40": ["scripts/run_capability_hunt.py", "scripts/check_exploration.py",
              "scripts/run_mutation.py"],
    # L1.41: nothing enters below the build standard -- prevention at the build boundary rather
    # than detection days later. The two Stage-A screens are its first governed non-fence organs.
    "L1.41": ["scripts/check_build_standard.py", "scripts/screen_funding_spread.py",
              "scripts/screen_collateral_allocation.py"],
    # L1.42: the boundary for the 60 python entry points that sourced no shell gate.
    "L1.42": ["libs/ops/lawful.py", "scripts/check_build_standard.py",
              "scripts/run_cashcarry_executor.py"],
    # L1.43: governance measured like everything else -- has each fence ever caught anything?
    # check_free_roster is the same logic pointed at a governance CAPABILITY rather than a fence:
    # the degraded free-seat fallback is only ever exercised while unfunded, so its health was
    # invisible by construction and 2026-08-01 found all four seats dead during the outage they
    # exist for. NEVER-RUN is the status L1.43 already names; this makes it observable on a
    # cadence, for free, because the seats cost nothing to ask.
    "L1.43": ["scripts/check_fence_yield.py", "scripts/check_enforcement_execution.py",
              "scripts/check_free_roster.py"],
    # L1.44: consumption-time freshness -- every decision-path read declares its max tolerated
    # age at the read site; the fence fails on STALE-CONSUMED (a live decision steered by a
    # frozen input) and on UNWIRED (a bootstrap contract deleted from the executor/alerts).
    # L1.44's own class, found four more times on 2026-08-05 and all in the same direction: a
    # state artifact whose AGE nobody checked, where staleness therefore read as health. The CI
    # marker (a wedged run_ci holds the lock, every later run exits 0 "skipping", the marker
    # freezes at ok=true and max_audit only ever raised on ok=false); the alert canary (a canary
    # that dies after a clean run leaves no silence flag, so the pager scored 10/10 for ever);
    # and source_health (a lane probed once successfully and never again read HEALTHY, so the
    # alternatives hunter never hunted it). Every one is a producer-side "did it run?" question
    # that no CONSUMER was asking -- which is precisely what this law was written for.
    "L1.44": ["scripts/check_freshness.py", "libs/ops/fresh.py", "check_ci_gate",
              "libs/research/source_health.py:stale_verdict"],
    # L1.45: execution excitation. Every other fence walks NODES and EDGES; this one looks for a
    # CYCLE (traded -> recorded -> measured -> cheap -> traded) and for exclusions with no path
    # back. It also owns the producer for the three ramp_gate step-up conditions that had none.
    # R0267 joins L1.45 rather than getting its own key: it is the FUNCTIONAL FORM the excitation
    # design has no vocabulary for, and its own-fill half refuses for exactly the reason L1.45
    # names -- an operating point the desk never visits, so go buy the observation.
    # fit_print_impact is the THIRD basis: the counterfactual half is the book walk, the own-fills
    # half is excitation, and neither reads the ~2,500 prints/symbol/hour of OTHER PEOPLE's
    # completed executions sitting on the same tape. It serves L1.45 by refusing above its
    # identified range -- the same "operating point never visited" discipline, applied to its own
    # output -- and it explicitly does NOT claim the causal slope excitation exists to identify.
    "L1.45": ["scripts/check_excitation.py", "scripts/run_cost_identification.py",
              "libs/execution/excitation.py", "scripts/fit_passive_impact.py",
              "libs/execution/passive_impact.py", "scripts/fit_print_impact.py",
              "libs/research/print_impact.py"],
    # L1.46: clock provenance. Every other data fence asks whether the COLLECTOR RAN -- gapless
    # collection was verified GOOD on the same corpus that is not monotonic in its own `t` field.
    # This one asks whether the TIMESTAMPS MEAN WHAT THE SCHEMA IMPLIES, which is the defect class
    # behind kimchi_premium, coinbase_premium_timing and R0060 alike.
    "L1.46": ["scripts/check_clock_provenance.py", "libs/research/clock_provenance.py"],
    # L1.47: funding capture. Funding is a DISCRETE payment booked as a CONTINUOUS accrual, and
    # the accrual is UNBIASED IN EXPECTATION -- which is why it survived every review while being
    # wrong on 41.5% of individual closes. The fence differences the two models, measures the
    # PHASE coordinate the desk has never used, and refuses to call an undifferenced estimate OK.
    "L1.47": ["scripts/check_funding_capture.py", "libs/research/funding_clock.py"],
    # R0119 crowding: the desk's capacity assumption is that its carry names are too small for
    # funds to bother with, and that assumption had never been INSTRUMENTED. The incumbent organ
    # (run_carry_crowding.py) measures the top-20 AVERAGE, which contains our own names -- so a
    # competitor compressing exactly our book is diluted and partly subtracted as its own
    # benchmark, and a regime is indistinguishable from an adversary. This measures the RESIDUAL.
    # The collector ships with the fence because premiumIndex serves no history: an uncollected
    # hour of cross-section is permanently unbuyable (L1.28b(f)).
    "L1.19-r0119": ["scripts/check_crowding.py", "libs/research/crowding.py",
                    "scripts/collect_funding_cross_section.py"],
    # R0118 event-density promotion clock: L1.48 says evidence is the clock, and evidence_clock
    # reached exactly ONE promotion-path file while a `fwd_days >= 30` gate scaled DEPLOYABLE
    # CAPITAL on a bare positive Sharpe (measured 2026-08-05: validated=True at t=0.105). The
    # module counts EFFECTIVE observations -- raw event counts discounted for serial dependence,
    # clamped so the arithmetic can remove evidence and never invent it.
    "L1.48": ["libs/research/evidence_clock.py", "libs/research/event_density.py",
              "scripts/check_calendar_gates.py"],
    # L1.49 and L1.50 were BOTH already enforced and NEITHER was mapped -- not an oversight by
    # whoever wrote them, but a consequence of the parser defect fixed in `_principles()` this
    # commit: laws written as `## L1.49` headings were invisible to this file, so there was
    # nothing here to notice was missing. Their enforcement is the change-detector suite the
    # author shipped alongside each law, which pins the constitutional clauses phrase-by-phrase
    # so a silent deletion fails while a sharper rewrite passes. L1.50's utilisation and queue
    # clauses additionally have live measuring fences, named here because they genuinely measure
    # those clauses rather than merely relating to them.
    "L1.49": ["tests/validation/test_weak_is_not_dead.py",
              "libs/research/cohort_independence.py"],
    "L1.50": ["tests/validation/test_weak_is_not_dead.py", "scripts/check_utilisation.py",
              "scripts/check_conversion.py"],
    # L1.51: a clamp without a price. Every risk breach is priced to the cent and NOT ONE CLAMP
    # ever carried a dollar figure, so the doctrine's "timidity is a REAL COMPOUNDING COST" and
    # L1.27's "protecting capital, or avoiding uncertainty?" were rhetorical every time. It is
    # fenced separately from L1.28a because that fence publishes a RATIO, and a ratio cannot be
    # weighed against a ruin probability -- dollars can. Its own proving instance was L1.28a's
    # gate reporting SATURATED at utilisation 1.0 on a book holding zero positions, because
    # `_capital()`'s numerator was the first rung inside its own denominator.
    "L1.51": ["scripts/check_idle_cost.py", "libs/research/idle_yield.py",
              "scripts/check_utilisation.py"],
    # L1.52: the unknown-unknown hunt reports its OWN health. check_self_sufficiency is the fence
    # AND was the proving instance -- it returned silently on an absent ledger, so skipping the
    # L2.5 logging duty switched off the check on that duty. blind_spot.py is the writer that
    # makes the metric exist at all; the alternatives hunter is the arm that acts on a lane going
    # dark, including one that merely stopped being probed rather than failing outright.
    "L1.52": ["check_self_sufficiency", "scripts/blind_spot.py",
              "scripts/hunt_source_alternatives.py",
              "libs/research/source_health.py:unproven_sources",
              "scripts/blindspot_max.py", "scripts/blindspot_prober.py"],
    # L1.53: conversion measured against ARRIVALS, and the denominator fenced separately so the
    # ratio cannot be improved by finding less. Both halves live in the one fence, deliberately
    # as two statuses -- DEBT-GROWING (convert faster) and ARRIVALS-COLLAPSED (find harder).
    "L1.53": ["scripts/check_conversion.py",
              "tests/governance/test_conversion_fence.py"],
    # L1.54: a shut door is a routing problem. kimi_hunter is both the fence and the proving
    # instance -- its MODEL_CHAIN, per-wave failure isolation and BLOCKED artifact are the law in
    # code. source_alternatives + the hunter are the same rule for data sources: a registered
    # substitute BEFORE the outage, and source_health's unproven_sources is what notices a lane
    # that went quiet without ever failing.
    "L1.54": ["scripts/kimi_hunter.py", "libs/research/source_alternatives.py",
              "scripts/hunt_source_alternatives.py",
              "libs/research/source_health.py:unproven_sources",
              "tests/scripts/test_kimi_hunter_no_giving_up.py",
              "scripts/check_llm_routing.py", "libs/ops/llm_route.py"],
    # L1.44 asks "is the file I am reading current?" -- one hop, age only. It cannot ask whether
    # the PRODUCER of that file could read ITS inputs, so run_live_guard published a ladder
    # constant and six never-evaluated conditions as a measurement, from a path that has never
    # existed, and every gate in the chain reported green. Freshness does not compose.
    "L1.55": ["scripts/check_input_provenance.py", "libs/ops/input_provenance.py",
              "scripts/run_live_guard.py"],
    # L1.56: a screen may not gate its own promotion. The proving instance is the whole point --
    # 120 scored cells, 12 forward slots, ZERO clocks ever started, four breaks each failing
    # CLOSED and each silent, and the accumulated silence read as "no edges exist". The fence is
    # a max_audit check rather than a standalone script, so it ALSO needs its _FENCE_OWNERS row
    # below; the law arrived mapped in neither and the matrix correctly called it UNENFORCED.
    "L1.56": ["check_survivor_pipeline", "tests/research/test_survivor_pipeline.py",
              "scripts/finalize_axis_screens.py", "scripts/run_paper_sleeve_spawner.py"],
    # L1.57: fence_exit fixed the map from status to exit code; it cannot see a status that is
    # honestly OK because the fence examined NOTHING. 18 of 40 fences passed vacuously and 10
    # more published len(<hardcoded literal>) as a denominator. The refusal lives in fence_exit
    # (scanned=), the registry self-builds, and the meta-fence is subject to its own law.
    "L1.57": ["scripts/check_denominators.py", "libs/ops/denominator.py",
              "libs/ops/fence_exit.py", "tests/governance/test_denominators.py",
              "scripts/check_exploration.py", "scripts/check_calendar_gates.py"],
    # L1.58 is the executable edge/P&L waterfall and loss investigation loop.
    "L1.58": ["scripts/run_trade_forensics.py", "scripts/run_trade_review.py",
              "libs/execution/execution_tape.py", "check_forensics_fresh",
              # R0334 (principal 2026-08-01): the sleeve's only scoreboard was a blended win_rate
              # and mean_R, which cannot separate a good thesis exited badly from a bad thesis
              # rescued by the ladder. Six components, each with its own denominator and its own
              # refusal -- target quality is UNMEASURABLE-BY-DESIGN on a sleeve that forbids
              # take-profits, and the stop check reports itself as a constant-pass gate (L1.49).
              "scripts/run_execution_quality.py", "libs/research/execution_quality.py"],
    # L1.59 freezes doctrine growth and makes the mandate answerable to measured value.
    "L1.59": ["scripts/build_enforcement_matrix.py", "scripts/module_justification.py",
              "scripts/check_denominators.py", "scripts/check_ratchets.py",
              "scripts/run_max_push.py", "scripts/check_doctrine_diff.py"],
    # L1.60: L1.57 asks whether the denominator is an int >= 1; nothing asked what it LOST. A
    # fence that reads 1000 files, drops 991 in `except OSError: continue` and declares
    # scanned=9 is recorded DECLARED, non-vacuous and CLEAN. The proving instance is L1.57's own
    # supplier -- check_calendar_gates' `n += 1` sat one line BELOW its handler. Both existing
    # swallow detectors require a Pass body, so the whole `continue`/`return <default>` class was
    # invisible (R0166, prose-only for twelve days). The three repaired fences are listed: each
    # is a regression site, and reverting an `attempted` counter turns the tests red.
    "L1.60": ["scripts/check_denominator_attrition.py", "libs/ops/attrition.py",
              "scripts/check_coverage_floors.py", "scripts/check_calendar_gates.py",
              "scripts/check_llm_routing.py"],
    # L1.61: the desk reconciles its book against the VENUE every cycle and had never once
    # reconciled its own artifacts against EACH OTHER. Every instrument is single-artifact BY
    # CONSTRUCTION -- phantoms asks "does a writer exist", fresh asks "is it old",
    # input_provenance asks "were MY inputs present" -- so contradiction, which exists only in
    # the RELATION between two artifacts, was invisible to all of them. Proving instance was
    # live on the only path to capital: gate0_readiness and live_guard evaluate the same five
    # Gate-0 criteria through the same function and FOUR disagreed. The general index was
    # REFUTED by its own falsifier (418 disagreements, ~0 genuine), so the registry is
    # hand-built and money-path only.
    "L1.61": ["scripts/check_claim_consistency.py", "libs/ops/claim_registry.py"],
    # L1.62: the Stage-A screen's cross-sectional power denominator was an ASSUMPTION at both
    # endpoints, one change apart, and neither was ever measured. Pre-08-11 panel_width was not
    # passed (K symbols = K observations, t inflated sqrt(K)); the fix passed the full width
    # (K symbols = ONE observation). Measured on the desk's own 139-symbol panel the answer is
    # ~93, so the divisor is 1.50 not 139 and the detection floor ran 9.6x high. Invisible
    # because the error ran CONSERVATIVE and its only symptom is SCREEN-UNDERPOWERED -- "could
    # not tell", which writes no graveyard entry, no clock and no alert, and holds 380 of 711
    # verdicts on disk. Both copies of the expression are listed: type2_cost.correlation_n_eff
    # documents itself as a deliberate copy "so the two cannot disagree", so a fix in one file
    # leaves the other authoritative. The screen caller is a regression site -- removing its
    # measure_panel_breadth call turns the tests red.
    # The CROSS-SECTION FLOOR joins this family rather than minting a law of its own (L1.59
    # freezes doctrine expansion; L2.9 says upgrade before building). It is the SAME defect one
    # axis over: L1.62 caught a denominator that ASSUMED how many independent bets a date carries,
    # this catches one that counts the panel's DECLARED WIDTH (`shape[1]`) instead of the finite
    # symbols a date actually has. A 373-column panel clears `shape[1] >= 8` on a date carrying
    # six names. Measured 2026-08-13: 12 of 311 dates carried 98.1% of a lag-1 statistic, reading
    # rho=+0.856 against a floored truth of -0.06. run_derivative_shadow is a regression site --
    # it is the declared locked mirror of backfill_oi_ls_oos and was the unfloored half.
    "L1.63": ["scripts/check_partition_power.py", "libs/validation/partition_power.py",
              "libs/autodiscovery/regime.py", "libs/risk/sleeve_allocation.py",
              "scripts/check_promotion_gate.py", "libs/research/crypto_regime.py",
              "scripts/falsify_funding_state_axis.py"],
    "L1.62": ["scripts/check_panel_breadth.py", "libs/research/panel_breadth.py",
              "libs/research/axis_screen.py", "libs/validation/type2_cost.py",
              "scripts/screen_oi_ls_axes.py",
              "scripts/check_cross_section_floor.py", "libs/research/cross_section_floor.py",
              "scripts/run_derivative_shadow.py"],
    # L1.64: the only deployed sleeve's margin construction (spot wallet + separately-margined
    # USDT-M short) was INHERITED from connector order, never decided. The one place capital
    # efficiency was modelled hardcoded _PM_EFFICIENCY=1.8 and applied it at every equity level
    # including the PM-ineligible seed, while the constructions usable TODAY (Multi-Assets;
    # COIN-M 1x self-collateralised, liq unreachable -- the desk's own mined 8btc card-31
    # evidence) were modelled nowhere. The comparator measures notional_per_equity per
    # construction (inherited: 0.75 at the executor's venue leverage 3; self-collateralised:
    # ~1.0, +33% capacity with liquidation risk FALLING); the fence fails INHERITED /
    # DIVERGED / DECIDED-STALE / UNMEASURED, and a decision against zero measured alternatives
    # is refused as paperwork (L1.28a). run_capital_plan is a regression site -- it now imports
    # CAPITAL_LEVELS + split_wallet_npe from the comparator, and the AST test that pins the
    # deleted constant turns red if the fork returns.
    "L1.64": ["scripts/check_margin_topology.py", "libs/portfolio/margin_topology.py",
              "scripts/run_capital_plan.py"],
    # R0369 (under L2.3/§42): an implemented row's --commit is the ledger's whole proof mechanism,
    # and it was enforced only at WRITE time -- `dispose` refuses an empty field and asks nothing
    # else. A rebase rewrites SHAs and the citation quietly names an object no other clone can
    # resolve. Measured over 227 citing rows: 14 INVALID (10 the literal `HEAD`, 4 `pending`) and
    # 1 ORPHANED. `HEAD` is the half no existence check could ever catch: it resolves everywhere,
    # to a different commit for every reader. The repair is UPWARD and wired -- `repoint` moves a
    # pointer without disturbing the disposition and refuses an unresolvable replacement.
    "L2.3-r0369": ["scripts/check_citation_integrity.py", "libs/research/citation_integrity.py",
                   "scripts/recommendations.py"],
    # R0287 capital-basis invariant (under L1.58's waterfall discipline): a return without its
    # declared denominator is the Quantopian-2019 shape (190% headline, 58% on capital actually
    # drawn) and this desk's own thrice-repeated class (R0234 ~25x equity undercount, R0235
    # testnet-sizing-live, the 13,155/4,500 split). The fence holds the line on NEW artifacts and
    # carries the dated 2026-08-11 bootstrap debt shrink-only.
    "L1.58-r0287": ["scripts/check_capital_basis.py", "libs/research/capital_basis.py",
                    "tests/research/test_capital_basis.py"],
    # R0288 unlock-calendar conversion (L1.8 data-to-alpha): data/unlock_events.json sat with
    # ZERO python readers and an expiring forward window; the collector accrues first-seen events
    # with POINT-IN-TIME pct-of-float (the snapshot's pct_circ_now was a look-ahead in the
    # conditioning variable), the reader gives the snapshot its first consumer, and forward
    # events route through the event-study gate once enough accrue.
    "L1.8-r0288": ["scripts/collect_unlock_calendar.py", "libs/research/unlock_calendar.py",
                   "tests/research/test_unlock_calendar.py",
                   "scripts/collect_circulating_supply.py"],
    # R0371 fee attribution (L1.58 edge preservation / P&L forensics): futures commission is
    # 88.7% of the sleeve's non-funding loss and 0 of 500 trade-tape rows carry a fee field, so
    # the desk could see the dominant loss and not attribute it. binance_testnet.commission_events
    # already answered it and had zero callers; this is the consumer. Per-symbol truth reconciles
    # to the cent ($1,750.878 vs the dashboard's $1,750.88) and four names carry 85.9% of it.
    # Per-round-trip attribution stays REFUSED and the spot leg UNMEASURED -- both are published
    # as refusals rather than zeros, and the 7.1% tape coverage is the defect the surface reports.
    "L1.58-r0371": ["scripts/run_fee_attribution.py", "libs/research/fee_attribution.py",
                    "tests/test_fee_attribution.py", "scripts/run_execution_intel.py"],
    # R0303 Upbit purge-proof snapshot (L1.46 unrecoverable-series duty): the venue erases a
    # market's candle history at delisting (~11.4 KRW markets/yr; AQT/AERGO lost 2026-08-03),
    # and the desk's own >=120-aligned-day panel filter stacks a second survivorship bias on
    # top. The collector holds full daily history for every market plus flagged-market 1m,
    # and its manifest's delist ledger is the treatment group the purge erases.
    "L1.46-r0303": ["scripts/run_upbit_snapshot.py", "libs/research/upbit_data.py",
                    "tests/research/test_upbit_snapshot.py"],
    # R0123 decline grading: L1.29 says an ungraded prediction is a BELIEF that inflates the
    # apparent hit-rate by never counting its misses -- and a sleeve scored only on the trades it
    # CHOOSES to be graded on is that defect with a dominant strategy attached. Nine consecutive
    # PASSes, zero scoreable forecasts. The grader ships with the logging because check_calibration
    # fails on any forecast past its deadline: logging without grading would turn a green survival
    # fence permanently red.
    "L1.29-r0123": ["libs/research/decline_value.py", "scripts/resolve_llm_trader_book.py",
                    "scripts/check_calibration.py"],
    # R0121 settlement-calendar screen (§42 capacity lens, L1.6 zero promotion authority). Tests
    # the PREMISE before the economics: nested grids make the trade geometrically impossible at
    # any funding level, and only a genuine phase offset creates a capture window.
    "L1.6-r0121": ["scripts/screen_funding_interval_mismatch.py"],
    # R0207 the desk's first CAUSAL study. L1.16 (an edge is durable only when its MECHANISM is
    # understood) is the law this serves: every prior hypothesis was observational, and
    # de-contamination plus multiplicity control establish that a relationship is not an ARTIFACT,
    # never that it is CAUSAL. L1.6 governs its authority -- Stage A, zero promotion, a refusal is
    # a first-class result. The rails (parallel trends, placebo, SUTVA) are what separate
    # identification from a correlation with better vocabulary.
    "L1.16-r0207": ["libs/research/natural_experiment.py",
                    "scripts/run_natural_experiment.py"],
    # R0100 axis collectors (2026-08-05): three free, keyless raw-information axes the desk did
    # not hold. Under L1.11 (the moat is the transformation pipeline, never the purchased dataset)
    # and L1.8 (acquisition runs at maximum). collect_perpdex_funding carries the screen-on-
    # discovery duty in-organ -- it screens what it ingests in the SAME run, so an axis cannot be
    # catalogued and abandoned, and it declares clock provenance per L1.46 (venue stamp + receipt).
    "L1.11-r0100": ["scripts/collect_dexscreener.py",
                    "scripts/collect_holder_concentration.py",
                    "scripts/collect_perpdex_funding.py"],
    # R0291 (2026-08-12): wallet-resolved signed DEX flow, the one axis where waiting IS the
    # loss -- venue retention ~300 trades/pool, so capture is forward-only-unrecoverable
    # (L1.28b(f): acquisition never throttled). Dual clocks per L1.46 (chain stamp + receipt),
    # per-pool window-overflow flagged so sampling truncation is measured, never silent.
    "L1.11-r0291": ["scripts/collect_geckoterminal_trades.py"],
    # R0299 (2026-08-12, KR-s1 B): the KR venue flag surface -- Upbit warning + 5 caution flags
    # and Bithumb market_warning + per-asset deposit/withdrawal rails. All three surfaces are
    # SNAPSHOT-ONLY with no history endpoint, so this recorder is the only source of the series
    # (L1.46: recv_only clock declared, unrecorded transitions permanently lost). Bithumb rail
    # state is the independent barrier-height regressor that breaks the KR-premium circularity.
    # A failed fetch is never diffed -- absence must not read as 'all flags cleared' (L1.51).
    "L1.46-r0299": ["scripts/collect_kr_venue_flags.py"],
    # R0375 (2026-08-12): the haircut that decides whether idle dollars may earn was
    # `DEFAULT_HAIRCUT_BPS = 300.0` with no derivation anywhere in the repo, against a measured
    # 5.5bps breakeven -- L1.51's own defect class (a clamp nobody could argue with because
    # nobody had computed it) sitting on the desk's only idle-capital decision. Now derived from
    # net-of-returned-funds exploit losses over integrated TVL-years at a 95% Poisson frequency
    # bound, plus the measured depeg shortfall: 41.7bps. The refusal value is still 300, so an
    # unreadable input keeps the band SHUT rather than opening it on a fabricated small number
    # (L1.55). Risks measured but deliberately unpriced are named, never inferred as zero.
    "L1.51-r0375": ["scripts/collect_lending_risk_base_rates.py",
                    "libs/research/lending_haircut.py",
                    "tests/research/test_lending_haircut.py"],
    # R0102 paper-sleeve auto-spawn: converts corrected Stage-A survivors into costless paper
    # sleeves. L1.6 bounds it (zero promotion authority, zero capital) and L1.18a orders its queue
    # (deployment race -- shortest capacity runway first). It NEVER spawns over the Holm cap: a
    # concurrent clock tightens every standing candidate's bar, so it queues behind retirements.
    "L1.6-r0102": ["scripts/run_paper_sleeve_spawner.py", "libs/research/paper_sleeves.py"],
    # §42 capacity retirement (2026-08-05): 1051 of 1799 scored candidates could not be filled by
    # a $13,151 book at all. Retirement banks the full mechanism (L1.17 research debt, with a
    # named L1.16a resurrection condition) and archives the row; the factory boundary in
    # AutoDiscoveryLab._record_scored stops the backlog re-forming.
    "L1.18a-capacity": ["scripts/retire_unfillable_candidates.py",
                        "libs/autodiscovery/capacity_screen.py"],
    # R0122 LLM discretionary sleeve: paper-only candidate generator whose calls are scored
    # forecasts. Governed by L1.6 (zero promotion authority) and L1.29 (it grades itself).
    "L1.6-llm": ["scripts/run_llm_trader.py"],
    # R0122b: the unstructured feed the sleeve trades. Under L1.11a (information asymmetry as a
    # search dimension) -- its latency measurement IS the asymmetry test.
    "L1.11a-events": ["scripts/collect_announcements.py"],
    # R0125 conviction sleeve: aggression is L1.28 (uncapped conviction), the rail is L1.23
    # (stop on every trade, leverage cap, inside the ruin rail).
    "L1.23-conviction": ["scripts/run_conviction_trader.py"],
    # R0133: the marker. Both paper sleeves wrote books nobody ever read -- the purest L1.28a
    # defect, since an unmarked book accumulates confident rows and reports no failure. This organ
    # walks the recorded ladder against real bars, benchmarks against buy-and-hold (L1.6) and
    # feeds the outcome to calibration (L1.29), which is what makes over-confidence self-shrinking.
    "L1.28a-paper-marks": ["scripts/resolve_paper_book.py"],
    # R0134: the discretionary sleeve was asked to read charts it had never been shown -- an
    # unused information source sitting under a strategy that needs it (L2.9), and a ceiling
    # reported as fine while unmeasured (L1.28a). Multi-timeframe structure, per instrument.
    "L2.9-chart-context": ["scripts/build_chart_context.py"],
    # R0135: four money-path constants were found defective in one session, all round numbers
    # picked by analogy rather than computed. Four of four is a missing mechanism, not bad luck.
    "L1.41-sizing": ["scripts/check_sizing_derivation.py"],
    # R0137: the dashboard showed carry as a SURVIVOR on P&L whose funding term was 3% of it. The
    # desk's own two-sided bleed fence already said "naked leg" -- and gated nothing.
    "L1.6-attribution": ["scripts/check_mechanism_attribution.py",
                         "libs/execution/carry_accounting.py"],
    # R0139: the discretionary desk's learning loop. Lessons climb an evidence ladder before they
    # reach the trader and are retired by their own falsifier -- the same standard L1.6 applies to
    # alpha, applied to the desk's beliefs about its own method.
    "L1.6-playbook": ["scripts/run_trade_review.py", "docs/DISCRETIONARY_DESK.md"],
    # R0140: copytrading, screened. The naive read (copy the leaderboard's best) is the 420/0
    # selection failure in a new costume; the screen computes the tempting number AND disqualifies
    # it, archives the only unbiased design (a forward panel counting exits as failures), and
    # measures the derivative that does not require picking a winner.
    "L1.6-copytrading": ["scripts/screen_copytrading.py"],
    # R0141: more sleeves multiply growth only if INDEPENDENT. Correlated sleeves draw down
    # together -- risk scales with N, growth with 1, and the desk pays N sets of costs for one bet.
    "L1.28b-sleeves": ["scripts/run_sleeve_allocator.py"],
    # R0142: the load-bearing assumption under the whole sizer -- that a stated probability means
    # anything. Zero resolved forecasts existed when this was checked. L1.29 scores it; this poses
    # the questions that give L1.29 something to score without needing capital or venue keys.
    "L1.29-probe": ["scripts/run_calibration_probe.py"],
    # R0143: the desk ruled against CAGR targeting on 2026-07-12, again on 2026-07-16, and a
    # decision-ledger success metric says "no CAGR targeting" -- and a 300% target section still
    # landed on 2026-07-31, caught by the principal rather than by any check.
    "L1.23-no-target": ["scripts/check_return_targeting.py", "docs/PROJECT_HANDOFF.md"],
    # R0144: installed, running and PRODUCING are three different facts. The manifest check proved
    # the LINE existed; nothing proved the organ emitted anything, which is how a miner goes dark
    # with the board still green.
    "L1.28c-liveness": ["scripts/check_organ_liveness.py"],
    # R0150: the symmetric half of the kill condition. The sleeve had a defined way to DIE and no
    # defined way to GROW, which makes expansion an improvised decision taken in the mood of a
    # good week -- the exact moment that decision is worst.
    "L1.6-promotion": ["scripts/check_promotion_gate.py"],
    # R0151: the constitution's ceiling-pushing family applied to the discretionary desk. A HIT
    # RATE is a legal target where a return figure is not -- it cannot be reached by sizing, only
    # by selection, information and filtering, which are exactly the levers to push.
    "L1.28c-discretionary": ["scripts/run_discretionary_max.py"],
    # R0152: the desk had an optimiser and a learner for ONE discretionary edge and nothing that
    # hunted for a SECOND. A single hypothesis is one regime change away from none, and the
    # allocator's own arithmetic says an independent second edge beats improving the first.
    "L1.31-discretionary-hunt": ["scripts/run_discretionary_hunt.py"],
    # R0198: costs are the one growth lever available before any edge is proven -- known BEFORE
    # the trade, and near breakeven a third of the cost stack is worth more than a point of hit
    # rate. Funding is SIGNED and public; the sleeve was blind to which sides get PAID to hold.
    # Selection uses the sign; marking stays always-adverse -- different jobs, different signs.
    "L1.41-cost-hunt": ["scripts/run_cost_hunt.py"],
    # R0200: every coverage organ mapped WHERE the miners look (source families, regions,
    # languages) and none mapped WHAT KIND of edge came back. 42 buried strategies cluster into
    # families, and twelve candidates from one family are correlated by construction -- they die
    # together and the desk learns one thing while reporting twelve tests.
    "L1.32-strategy-coverage": ["scripts/run_strategy_coverage.py"],
    # R0211: the coverage MAP reports and the widened prompts request; neither fails when a miner
    # drifts back to the family it knows, which is how breadth actually dies -- one comfortable
    # session at a time with the volume never dropping. This is the clock behind the rule.
    "L1.32-strategy-breadth": ["scripts/check_strategy_breadth.py"],
    # R0213: "surpass me" is only an instruction if something measures it. The desk already
    # benchmarks every sleeve against buy-and-hold (a levered sleeve that merely tracks the index
    # takes risk for nothing); the human method this sleeve was built to copy is the second
    # benchmark, computed the same way and equally non-optional.
    "L1.6-principal-benchmark": ["scripts/run_principal_benchmark.py"],
    # R0215: the desk DETECTED coma well and TREATED nothing -- three organs reported dark for
    # days, every report correct, no treatment attempted. Detection without treatment is a
    # monitor, not a hospital, and a ward whose alarms nobody answers gets its alarms switched off.
    "L1.32-organ-er": ["scripts/run_organ_er.py"],
    # L1.25a: null streaks throttle nothing -- an organ going quiet is caught by the freshness/
    # productivity wires REGARDLESS of its reason, so "stopped because nothing was working" trips
    # the same fence as "stopped because broken". The pessimism-freeze cannot hide.
    "L1.25a": ["check_organs", "check_stub_deaths", "check_idle_capability",
               "scripts/check_ratchets.py",
               # (b) forward slots fed daily: the WALCL clock (R0031) fills the slot kimchi's
               # retirement freed and accrues via the daily chain's walcl_clock step
               "scripts/derive_walcl_clock.py"],
}

# ---------------------------------------------------------------------------------------------
# SECOND DIRECTION: every FENCE claimed by a law (2026-07-30).
#
# The first pass mapped principles -> fences and left 39 of 71 fences governed by nothing. That is
# the failure mode this script's own docstring names -- "a check with no governing principle is
# complexity nobody voted for" -- and it was sitting in the script's own output, unactioned, which
# is precisely the decoration pattern L2.9 exists to kill. So the reverse index is now explicit.
#
# These are appended into _MAP rather than written inline above so the read direction stays clean:
# above answers "what enforces this law", below answers "why does this check exist at all".
_FENCE_OWNERS: dict[str, str] = {
    # --- RESTORED 2026-08-13, and three of these four had NEVER been mapped even before the
    # merge dropped them. The 8b981a5 resolution took the other branch's max_audit.py wholesale,
    # so all four check_* functions AND their dispatch entries vanished together: no import broke,
    # no test named three of them, and four audits simply stopped running while the auditor kept
    # reporting green. An audit that vanishes is strictly worse than one that fails -- a failure
    # is a signal, an absence is a silence that reads exactly like a pass. The orphan fence caught
    # them the moment they came back, which is the fence doing precisely its job.
    #
    # L1.49 (a gate that never ran is a claim the desk cannot cash) owns two of them, because both
    # assert EXECUTION rather than configuration: one proves the scheduled organ's file exists to
    # be run at all, the other proves the CIO review actually ran rather than being a directive
    # that lives in prose. That is L1.49's exact shape.
    "check_scheduled_scripts": "L1.49",
    # F0011/R0049: a clock may leave the Holm cohort only with a recorded, classifiable
    # mechanism -- the REFUTED-vs-merits distinction is L1.17's structured-knowledge duty
    # applied to the multiplicity denominator.
    "check_clock_retirement_mechanism": "L1.17",
    "check_meta_research": "L1.49",
    # L1.28a: the §35 exclusion for self-disposing dig logs is a CLAIM ABOUT A DOCUMENT, and an
    # unchecked claim is how absence resolves to a clean verdict -- the next session adds an item,
    # forgets the tag, and the item is governed by nothing while the exclusion still says
    # otherwise. The check is what makes the exclusion honest rather than trusted.
    "check_dig_log_disposition": "L1.28a",
    # L1.23, carried from its original mapping: a page is half a channel. The desk verified
    # DELIVERY for weeks and never verified the principal could ANSWER, so when a fork deleted
    # _poll_replies the pager went one-way and four decisions gating the book sat unanswerable.
    "check_principal_page_unanswerable": "L1.23",
    # --- READ-WITHOUT-WRITER (L1.40): the defect lens L1.40 names FIRST and calls this desk's most
    # prolific class -- "the capital-event equity bug was exactly this". check_phantom_paths is its
    # detector: a path read by code, absent from disk, written by nothing. Such a reader does not
    # crash; it takes the empty branch and returns a plausible zero, so the organ reports HEALTHY on
    # data that does not exist. Live instances were all found BY HAND before it existed
    # (research_memory.db with four readers and no writer; cost_ratio, slippage_ks_p and
    # calibration_mae_falling_months as ramp step-up conditions with no producer while the ramp sat
    # pinned at its floor), which is exactly the hand-is-not-a-mechanism gap L1.41 exists to close.
    "check_phantom_paths": "L1.40",
    # --- L1.54 (a shut door is a routing problem, not a verdict). Both fences landed unmapped and
    # therefore REFUSED EVERY PUSH on this branch -- the same failure my own check_paywalls_
    # registered hit at c8983b1, which makes it a class rather than an accident: a max_audit fence
    # is wired by adding the FUNCTION here, and adding the script to `_MAP` does not do it.
    # Mapped from each fence's own docstring, which names L1.54 explicitly, not from a guess:
    # "A blocked route the desk stopped chasing is an accepted loss. L1.54 forbids accepting it."
    # and "the enumerated exhaustion L1.54 demands rather than silence."
    "check_blocked_routes_hunted": "L1.54",
    "check_verified_alternatives_promoted": "L1.54",
    # --- SAME LENS, ONE TURN LATER (L1.40): check_phantom_paths catches a reader whose source was
    # NEVER written; check_dormancy_disarm catches a reader whose source WENT EMPTY. Both take the
    # empty branch and return a plausible healthy answer, but the second is harder to see because
    # the file exists, parses, and carries a young mtime -- only the list inside is empty, so every
    # staleness fence on this desk reads it as fresh. Live instance 2026-08-05: the carry book's
    # structural-bleed denylist read `worst_symbols`, a 14-day rolling window over the book's own
    # closes; the book paused on a drawdown, the window emptied, and the gate began allowing the
    # two incident-#6 symbols its own comment calls "currently-blocked". A pause is CAUSED by
    # losses, so the guard was guaranteed to be disarmed exactly when it was needed.
    "check_dormancy_disarm": "L1.40",
    # --- conversion parity (L1.28b): the repair wire's two halves. check_conversion measures the
    # daily flow (arrival vs disposition, FLATLINE on silence); check_recommendation_rows (§42 X1,
    # built independently by the box the same day) applies per-row carry-over pressure so old
    # rows are seen again. Same law, complementary directions.
    "check_recommendation_rows": "L1.28b",
    # --- capacity (§42 / L1.18a): six fences, one law. Small edges are hunted, filled and RETIRED
    # on arithmetic, never ranked down for being small.
    "check_capacity_hunt": "L1.18a",
    "check_capacity_knobs_are_wired": "L1.18a",
    "check_capacity_governor_reachable": "L1.18a",
    "check_capacity_allocation_honesty": "L1.18a",
    "check_capacity_runway": "L1.18a",
    "check_capacity_single_source": "L1.18a",
    # --- artifact-over-claim (L2.4): a capability exists only if something it wrote is FRESH.
    "check_organs": "L2.4",              # organ never fired / always dies
    "check_stub_deaths": "L2.4",         # runs that died at birth on quota/auth still "ran"
    "check_stale_daemons": "L2.4",       # daemon older than its source = a fix that never shipped
    "check_producer_cadence": "L2.4",    # an inventory-accumulating artifact declares a cadence
    "check_deploy_path": "L2.4",         # code that never reaches the box was never deployed
    # --- forced disposition (L2.3): every finding gets a ruling, and rulings are not allowed to rot.
    "check_findings": "L2.3",
    "check_findings_tracked": "L2.3",
    "check_findings_scope": "L2.3",
    "check_review_risks_tracked": "L2.3",
    "check_decision_ledger_matures": "L2.3",
    # --- execution physics (L1.5): the costs that quietly eat a carry.
    "check_bnb_funded": "L1.5",          # fee-burn discount only applies while BNB is held
    "check_fee_carry_ratio": "L1.5",
    "check_close_retry_loop": "L1.5",    # a carry that cannot close is a churn engine
    # --- survival rails (L1.23): states that read HEALTHY while being terminal.
    "check_book_collapse": "L1.23",
    "check_book_absorbing_state": "L1.23",   # a rail that can never release the book is not safety
    # L1.44 is the freshness law, and this is its sharpest case: the published rail verdict is a
    # produced artifact whose consumers (dashboard, pager, check_idle_cost) cannot see its age,
    # because `_emit` copies `rb['risk']` forward onto a file whose mtime keeps advancing. The
    # feed's own freshness is a heartbeat, and a heartbeat proves the loop is alive, never that
    # the pipe is. Compares the recomputed decision against the published one rather than asking
    # its age -- a fresh-and-wrong verdict passes every age bound there is.
    "check_rail_verdict_published": "L1.44",
    # --- injection + fence integrity (L2.1 / L2.2): the enforcement layer auditing itself.
    "check_constitution": "L2.1",
    "check_universal_doctrine": "L2.1",
    "check_registry_complete": "L2.2",   # an unregistered check is a law believed-but-not-enforced
    "check_artifact_governance": "L2.2",
    "check_ci_scope": "L2.2",            # a CI gate on a hardcoded subset is a map, not a territory
    "check_law_numbers_unique": "L2.8",  # a law number naming two laws breaks amendment itself
    # --- dormancy / reachability (L2.9): built-but-unwired, in three shapes.
    "check_orphan_scripts": "L2.9",
    "check_orphan_modules": "L2.9",
    "check_money_path_wired": "L2.9",    # a money-path module with only a test caller
    # --- discovery duties (L1.8 / L1.9 / L1.11a / L1.24).
    "check_clock_saturation": "L1.8",    # objective-#2 duty: the clock is the scarce resource
    "check_mine_scope": "L1.8",          # a find written somewhere unscanned is outside the law
    "check_mine_scope_vacuous": "L1.57",  # the INWARD leak: a doc IN scope the parser cannot see,
                                          # so §33 reads a clean backlog off an empty set
    "check_feed_inbox_backlog": "L1.8",  # a queue nobody counts becomes an archive (R0269)
    "check_source_backlog": "L1.9",      # a catalogue that grows faster than it is verified
    "check_dig_uncommitted": "L1.9",     # VPS disk is not institutional memory
    "check_paid_target_registry": "L1.11a",
    # Same duty from the other end: the registry fence above asks whether a KNOWN paid target is
    # tracked, this one whether a paywall the desk actually WALKED INTO ever reached the registry.
    "check_paywalls_registered": "L1.11a",
    "check_holdings_never_shrink": "L1.24",  # information advantage measured as a holding, not act
    # --- remaining singletons.
    "check_panel": "L1.7",               # adversarial review capability being DOWN is a defect
    "check_memory_hygiene": "L1.17",     # research debt is only debt if it is written and findable
    "check_mine_evidence_base": "L1.6",  # a ratchet calibrated on n=2 is superstition with a JSON
    # --- THE ECONOMIC OBJECTIVE (L1.57-L1.59, 2026-08-08). These three laws are about WEALTH
    # rather than about process, so their fences are behavioural tests and one report rather than
    # a `check_*` script: there is no pass/fail condition on "the objective is retained log
    # wealth", only a scoreboard that must exist, must refuse to invent numbers, and must rank
    # above the architecture counts.
    "tests/portfolio/test_return_engines.py": "L1.57",
    "tests/scripts/test_wealth_report.py": "L1.57",
    "tests/portfolio/test_wealth_retention.py": "L1.58",
    "tests/research/test_conversion_velocity.py": "L1.59",
    "tests/validation/test_state_conditional.py": "L1.59",
    # --- claimed at the 2026-08-04 merge: both branches' new fences, each under the law it serves.
    "check_asymmetry_ratchet": "L1.24",       # owned-data advantage is a holding that must not shrink
    "check_coexistence": "L1.23",             # sleeves sharing a book must not defeat its rails
    "check_constitution_review": "L2.8",      # the quarterly review is amendment law's own cadence
    "check_data_decay": "L1.19",              # decay is measured on the revalidation clock, not assumed
    "check_dependency_drift": "L2.2",         # a suite green on the wrong pins is not evidence
    "check_evig_ranking": "L1.26",            # research capital is priced by ERV/EVIG, not by recency
    "check_fixers_not_watchers": "L1.13",     # a watcher with no remediation loop is a stale register
    "check_governing_layer_live": "L2.2",     # the enforcement layer auditing that it itself runs
    "check_law_coverage": "L2.2",             # a law with no fence is believed-but-not-enforced
    "check_llm_exhaustion": "L1.28a",         # a seat asked once is paid-for capacity left idle
    "check_moat_screened": "L1.11",           # unscreened moat candidates are vendor data with extra steps
    "check_model_freshness": "L1.12",         # a verified better model unadopted is idle capability
    "check_naive_datetime": "L1.41",          # tz-naive stamps are the build standard's silent-corruption class
    "check_no_ceiling": "L1.28",              # anti-timidity: nothing capped below its measured maximum
    "check_silent_swallows_on_the_rails": "L1.41",  # a bare except on the money path is a refusal-path hole
    "check_survivor_pipeline": "L1.56",       # zero results is a claim about the INSTRUMENT until it is shown to work
    "check_test_suite_collectable": "L2.2",   # a suite that cannot collect enforces nothing
    # Same family as the line above, one cause upstream (R0407a): an OOM-killed probe reports as a
    # broken suite, so the box running out of memory is a condition under which the desk's evidence
    # stops being evidence -- exactly what check_dependency_drift and check_test_suite_collectable
    # each say about their own precondition. Not L1.28a: that law is about running a ceiling AT its
    # limit, and RAM at 100% is the failure, not the goal.
    "check_host_memory_headroom": "L2.2",     # a verdict the box had no memory to produce is not one
    "check_triage_disposition": "L1.17",      # self-dispositioning registers stay honest or lose the exclusion
    "check_under_exploration": "L1.32",       # under-exploration is a breach, not a preference
    "check_unwired_modules": "L2.9",          # built-but-unreachable, the third shape of dormancy
}
for _fence, _pid in _FENCE_OWNERS.items():
    _MAP.setdefault(_pid, []).append(_fence)

# Laws a fence cannot satisfy, each with the reason. Being explicit is the point: an unfenceable law
# recorded as HUMAN-ONLY is a decision; one silently absent from the map is a hole.
_HUMAN_ONLY: dict[str, str] = {
    "L2.8": "the REVIEW is a human judgement (default outcome STABILITY); a fence would either "
            "block legitimate change or rubber-stamp it. Its BOUNDARY is not human-only: L2.8a "
            "hashes the five clauses evolution may never touch (check_constitution_core.py), so "
            "what is unfenced here is the judgement, not the safety margin",
}
_STANDING: dict[str, str] = {
    "L1.0": "ratchet meta-law -- check_ratchets.py enforces the FLOORS across every measured "
            "property, and run_max_push.py enforces the DIRECTION: one ranked queue of everything "
            "not yet at 100%, which never reports done (all-green escalates to "
            "MEASUREMENT-SET-TOO-SMALL). STANDING rather than ENFORCED because the law is a "
            "standing duty on every cycle, not a single pass/fail condition",
    "L2.0": "enforcement meta-law -- satisfied by the existence of this matrix",
}


def _principles() -> dict[str, str]:
    """principle id -> its first sentence (the requirement), read from the constitution.

    TWO HEADING FORMS EXIST AND ONLY ONE WAS PARSED, which made this fence blind to the four
    newest laws on the desk. Everything up to L1.47 is written `**L1.47 TITLE**`; every law from
    L1.48 onward is written `## L1.48 TITLE`. The bold-only pattern silently skipped L1.48, L1.49,
    L1.50 and L1.51 -- so the matrix published `n_principles: 68` and `fences with no governing
    principle: 0` over a set that EXCLUDED them, and a fence could name one of those laws as its
    owner and be counted as governed by a principle this function had never seen.

    That is the L1.43 welded-gate shape one level up: the tally was not wrong about what it
    counted, it was wrong about what it looked at, and a check that reports a clean 0 is exactly
    the one nobody re-reads. Found 2026-08-05 while wiring L1.51 -- the law being added was itself
    invisible to the fence that certifies laws are enforced.
    """
    text = _CONST.read_text("utf-8")
    out: dict[str, str] = {}
    for m in re.finditer(r"^\*\*(L\d+\.\d+[a-z]?)\s+([^*]+)\*\*(.*)$", text, re.MULTILINE):
        pid, title, rest = m.group(1), m.group(2).strip(), m.group(3).strip()
        first = re.split(r"(?<=[.!])\s", rest, maxsplit=1)[0] if rest else ""
        out[pid] = f"{title.rstrip('.')} — {first}".strip(" —")[:400]
    # `## L1.xx TITLE` -- the form every law since L1.48 uses. The requirement sentence lives in
    # the paragraph BELOW the heading rather than on the same line, so it is read from there.
    # The bold form wins on collision: it is the older, denser one and carries the rest inline.
    for m in re.finditer(r"^#{2,}\s*(L\d+\.\d+[a-z]?)\s+(.+?)\s*$", text, re.MULTILINE):
        pid, title = m.group(1), m.group(2).strip()
        if pid in out:
            continue
        para = next((p.strip() for p in text[m.end():].split("\n\n") if p.strip()), "")
        para = re.sub(r"\s+", " ", para)
        first = re.split(r"(?<=[.!])\s", para, maxsplit=1)[0] if para else ""
        out[pid] = f"{title.rstrip('.')} — {first}".strip(" —")[:400]
    return out


def _fence_names() -> set[str]:
    return set(re.findall(r"^def (check_[a-z_0-9]+)", _AUDIT.read_text("utf-8"), re.MULTILINE))


def _exists(ref: str) -> bool:
    """Does the enforcing artifact actually exist? A mapping to a deleted file is worse than none.

    TWO REGISTRIES, AND THE `.py` SUFFIX IS THE ONLY THING THAT SEPARATES THEM (R0436). A ref
    beginning `check_` can mean either of two entirely different objects: a FUNCTION inside
    scripts/max_audit.py, or a standalone fence SCRIPT on disk. This used to short-circuit ANY
    `check_`-prefixed ref into the function table, so `check_denominators.py`, `check_freshness.py`
    and every other standalone fence written in the bare form was resolved against a registry it
    can never appear in -- reported BROKEN-REF, which exits 1 and hard-blocks every push (L1.37),
    with a message naming the ref and nothing about why.

    `_fence_names()` regexes `^def (check_[a-z_0-9]+)`, and `.` is not in that character class, so
    a max_audit function name can NEVER end in `.py`. That makes the suffix an exact discriminator
    rather than a heuristic: with it, the ref means the script; without it, the function. Both
    forms are now askable, which is what the old code had no way to express.

    THE ACCEPT DIRECTION IS THE SAFE ONE and it loosens nothing: the file branch still requires the
    path to EXIST on disk, so a mapping to a deleted or misspelled fence fails exactly as before. A
    max_audit function mistakenly written `check_foo.py` has no `scripts/check_foo.py` behind it
    and still reports BROKEN-REF. What changes is only that a real fence, mapped by its real
    filename, stops being unmappable -- and an unmappable fence is one a future author is cheapest
    to leave unmapped, which is the outcome this matrix exists to prevent (L2.0).
    """
    bare = ref.split(":")[0].split(" ")[0]
    if bare.startswith("check_") and not bare.endswith(".py"):
        return bare in _fence_names()
    return any(cand.exists() for cand in (_ROOT / bare, _ROOT / "scripts" / bare))


def _scheduled(refs: list[str]) -> list[str]:
    man = _MANIFEST.read_text("utf-8") if _MANIFEST.exists() else ""
    return [r for r in refs if Path(r.split(":")[0].split(" ")[0]).name in man]


def _master_authority() -> dict[str, Any]:
    """Expose the limit of this matrix instead of Goodharting its clean companion score."""
    text = _MASTER.read_text("utf-8")
    canonical = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    sections = len(re.findall(r"^# \d+\.", text, re.MULTILINE))
    return {
        "master_path": _MASTER.relative_to(_ROOT).as_posix(),
        "master_sha256": hashlib.sha256(canonical).hexdigest(),
        "master_sections": sections,
        "master_to_code_crosswalk": {
            "status": "UNMEASURED",
            "covered_sections": None,
            "total_sections": sections,
            "owed": True,
            "scope_note": (
                "The executable matrix below covers docs/CONSTITUTION.md companion laws; it is "
                "not yet a section-by-section enforcement crosswalk for the sealed master."
            ),
        },
    }


def build() -> dict[str, Any]:
    principles, fences = _principles(), _fence_names()
    rows: list[dict[str, Any]] = []
    for pid, requirement in sorted(principles.items()):
        refs = _MAP.get(pid, [])
        live = [r for r in refs if _exists(r)]
        broken = [r for r in refs if r not in live]
        if pid in _HUMAN_ONLY:
            status, note = "HUMAN-ONLY", _HUMAN_ONLY[pid]
        elif pid in _STANDING:
            status, note = "STANDING", _STANDING[pid]
        elif live:
            status, note = "ENFORCED", ""
        else:
            status, note = "UNENFORCED", "no fence or runtime mechanism maps to this principle"
        rows.append({"principle": pid, "requirement": requirement, "status": status,
                     "enforced_by": live, "broken_references": broken,
                     "scheduled": _scheduled(live), "note": note})

    # ORPHANS ARE COMPUTED OVER FUNCTION REFS ONLY. `fences` holds max_audit FUNCTION names, which
    # never carry a `.py` suffix, so a script ref could never have cancelled an orphan anyway --
    # but leaving `check_foo.py` in this set would quietly claim it might, and a set whose members
    # cannot match its counterpart is the kind of near-miss that reads as coverage (R0436).
    mapped_fences = {r.split(":")[0] for refs in _MAP.values() for r in refs
                     if r.startswith("check_") and not r.split(":")[0].endswith(".py")}
    orphan_fences = sorted(fences - mapped_fences)
    counts: dict[str, int] = {}
    for r in rows:
        counts[str(r["status"])] = counts.get(str(r["status"]), 0) + 1
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L2.0/L2.2 -- a principle with no enforcement is prose; a fence with no principle "
               "is unvoted complexity. Both directions are engineering gaps.",
        "authority": _master_authority(),
        "counts": counts, "n_principles": len(principles), "n_fences": len(fences),
        "unenforced": [r["principle"] for r in rows if r["status"] == "UNENFORCED"],
        "broken_references": {r["principle"]: r["broken_references"] for r in rows
                              if r["broken_references"]},
        "fences_without_a_principle": orphan_fences,
        "matrix": rows,
    }


#: Where a `check_*` FUNCTION inside scripts/max_audit.py is claimed by a law. Named here as a
#: constant so the failure message and the registry can never drift apart in a rename.
_OWNERS_REGISTRY = "_FENCE_OWNERS in scripts/build_enforcement_matrix.py"


def _orphan_remediation(orphans: list[str]) -> str:
    """The exact line to add, for the exact fence that failed. R0427.

    THE GATE KNEW THE ANSWER AND PRINTED THE QUESTION. This refusal has blocked pushes for
    everyone on a shared branch twice in four commits (c8983b1 check_paywalls_registered;
    cc28734 check_blocked_routes_hunted + check_verified_alternatives_promoted) -- different
    authors, three commits apart, which makes it a class rather than an accident. Both times the
    fix was one line in a registry the message never named, while the trap it is mistaken for
    (adding the SCRIPT PATH to `_MAP`) reads as equivalent in review and does nothing, because
    there is no script path for a function.

    The remediation is emitted as copy-pasteable source rather than prose. An instruction the
    reader has to translate is an instruction they can translate wrongly, and the wrong
    translation here is the exact edit that looks correct and fails.
    """
    lines = [
        f"  HOW TO FIX -- add each fence to {_OWNERS_REGISTRY}, keyed by the law its own",
        "  docstring already names (map from the docstring, never from a guess):",
        "",
    ]
    lines += [f'      "{name}": "L1.x",   # <- replace L1.x with the law this fence enforces'
              for name in orphans]
    lines += [
        "",
        "  A max_audit fence is a FUNCTION, so it is wired by FUNCTION NAME. Adding the script",
        "  path to `_MAP` looks equivalent, reads equivalent in review, and does nothing -- the",
        "  orphan set is computed over refs starting with `check_`, and no script path is one.",
        "  If no existing law covers the fence, THAT is the finding: either the fence is unvoted",
        "  complexity (retire it), or the constitution is missing a principle the fence already",
        "  assumes (raise it). Both need a decision; neither is silence.",
    ]
    return "\n".join(lines)


def _broken_ref_hints(refs: list[str]) -> list[str]:
    """Explain a BROKEN-REF whose artifact is sitting right there on disk (R0427/R0436).

    `_exists` resolves a `check_`-prefixed ref against max_audit's FUNCTION table unless it carries
    a `.py` suffix. That is now an exact rule rather than a short-circuit, but it is still a rule
    the author cannot see from the failure, and the surviving failure mode is the SUFFIXLESS one:
    `check_foo` when the fence is a standalone `scripts/check_foo.py`. The status is correct and
    the reason is invisible, which sends the author hunting a file that already exists.

    The `.py` case is kept because a fence at the REPO ROOT rather than under `scripts/` still
    fails, and because a repo that reverts `_exists` must not silently lose the explanation.
    """
    hints = []
    for ref in refs:
        bare = ref.split(":")[0].split(" ")[0]
        if not bare.startswith("check_"):
            continue
        if bare.endswith(".py"):
            if (_ROOT / "scripts" / bare).exists():
                hints.append(
                    f"{bare} EXISTS at scripts/{bare} -- write it path-first as `scripts/{bare}`. "
                    f"A ref starting with `check_` and carrying no `.py` suffix is resolved "
                    f"against max_audit's FUNCTION table, which a standalone script can never "
                    f"appear in.")
        elif (_ROOT / "scripts" / f"{bare}.py").exists():
            # THE AMBIGUITY R0436 NAMES, from the other side: a bare `check_foo` is a request for
            # the FUNCTION registry, and max_audit has no such function -- but a fence SCRIPT of
            # that name is on disk. Two registries, one spelling, and the author gets a refusal
            # about a fence they can see. Name the suffix that asks for the other one.
            hints.append(
                f"{bare} is not a function in scripts/max_audit.py, but scripts/{bare}.py EXISTS. "
                f"A suffixless `check_` ref asks for max_audit's FUNCTION table; add the suffix "
                f"(`scripts/{bare}.py`) to ask for the standalone fence script instead.")
    return hints


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report-only", action="store_true", help="always exit 0")
    args = ap.parse_args()
    m = build()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(m, indent=2), "utf-8")
    if args.json:
        print(json.dumps(m, indent=2))
    else:
        print(f"enforcement matrix: {m['counts']} over {m['n_principles']} principles / "
              f"{m['n_fences']} fences")
        crosswalk = m["authority"]["master_to_code_crosswalk"]
        print(f"  sealed master: {m['authority']['master_sections']} sections; "
              f"master-to-code crosswalk={crosswalk['status']} (owed={crosswalk['owed']})")
        for pid in m["unenforced"]:
            print(f"  UNENFORCED {pid}")
        for pid, refs in m["broken_references"].items():
            print(f"  BROKEN-REF {pid} -> {refs}")
            for hint in _broken_ref_hints(refs):
                print(f"      {hint}")
        n_orph = len(m["fences_without_a_principle"])
        print(f"  fences with no governing principle: {n_orph}"
              + (f": {m['fences_without_a_principle']}" if n_orph else ""))
        if n_orph:
            print(_orphan_remediation(m["fences_without_a_principle"]))
        print(f"-> {_OUT.relative_to(_ROOT)}")
    if args.report_only:
        return 0
    # Fail on an unenforced principle, a mapping to a missing artifact, OR an unclaimed fence.
    #
    # That last one is a RATCHET (L1.0), turned on the day the backlog hit zero (2026-07-30). While
    # 39 fences predating this map were unclaimed, failing on them would only have taught the desk
    # to run --report-only. Now that every fence is claimed, a NEW unclaimed fence is a real defect
    # and it is exactly one line of work to fix: name the law it serves in _FENCE_OWNERS. If no law
    # covers it, that is the finding -- either the fence is unvoted complexity, or the constitution
    # is missing a principle the fence already assumes. Both need a decision, not silence.
    return 1 if (m["unenforced"] or m["broken_references"]
                 or m["fences_without_a_principle"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
