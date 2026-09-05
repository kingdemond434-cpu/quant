"""The desk's producers, artifacts and consumers, as a graph a machine can check.

THE DEFECT CLASS THIS EXISTS FOR, in this repository's own words from one afternoon:

    the deepening queue had no reader
    session state was computed and not passed to the solve
    the optimiser's per-sleeve weights were solved and not what sized the book
    factor exposure was measured and did not bind breadth
    execution slippage was captured and the attribution never read it
    the shadow sync committed and did not push
    coverage measured the old money path

Not one of those was a missing capability. Every one was a capability that existed and could not
be reached from a decision. A reviewer can find that class once; a graph can find it every
commit.

WHAT A NODE DECLARES. Each component names the artifacts it WRITES and READS, and whether it
holds AUTHORITY -- can change a position, a size, a certificate, or what may condition capital.
Artifacts are file paths. Declarations are checked against the code: a node that declares a
write must contain the path literal, and a path literal in a node's source that no node declares
is reported as UNDECLARED so the graph cannot drift silently from the code it describes.

THE CHECKS, each of which has already cost this desk something:

    DEAD_PRODUCER        an artifact is written and nothing reads it
    DEAD_CONSUMER        an artifact is read and nothing writes it
    ADVISORY_ONLY        a node writes artifacts that only report-writers read; it computes and
                         nothing decides on it
    UNMEASURED_AUTHORITY a node conditions capital on a state dimension the admission report has
                         not judged, or that it has buried
    STALE_DECISION       an authority node reads an artifact older than its freshness SLA
    UNDECLARED           a path literal in the source that the graph does not know

The checker runs in CI and fails on any of the first four. Freshness is checked at runtime by
`generate_status`, which writes the generated-truth files the audit asked for:

    reports/CAPABILITY_STATUS.json   every node, its edges, its check results
    reports/LIVE_REACHABILITY.json   which artifacts reach an authority node, and by what path
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"

#: Artifacts whose only purpose is to be read by a person. A node that feeds only these is
#: ADVISORY_ONLY unless it also holds authority itself.
REPORT_PREFIXES = ("reports/",)


@dataclass(frozen=True)
class Node:
    name: str
    module: str                        # path relative to ROOT
    writes: tuple[str, ...] = ()
    reads: tuple[str, ...] = ()
    #: What this node may change. Empty means it decides nothing on its own.
    authority: tuple[str, ...] = ()
    #: Seconds an authority node may tolerate on an input before its decision is STALE.
    freshness_s: dict[str, int] = field(default_factory=dict)
    #: State dimensions this node conditions capital on; each must be admitted.
    conditions_on: tuple[str, ...] = ()


#: THE GRAPH. Every path is relative to ROOT. Adding a component means adding it here, and the
#: UNDECLARED check is what forces that: a new writer of a new path shows up red until named.
NODES: tuple[Node, ...] = (
    Node("miner_candidate_compiler", "desks/mt5/research/miner_candidate_compiler.py",
         writes=("desks/mt5/data/hypotheses/miner_candidates.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json",
                 "desks/mt5/data/hypothesis_graph.jsonl"),
         reads=("desks/mt5/data/intelligence/", "desks/mt5/reports/universal_gates_external.json")),
    Node("deepening_worker", "desks/mt5/research/deepening_worker.py",
         writes=("desks/mt5/data/hypotheses/deepening_worked.jsonl",
                 "desks/mt5/data/hypotheses/deepened_candidates.json"),
         reads=("desks/mt5/data/hypotheses/miner_deepening_queue.json",
                "desks/mt5/data/hypothesis_graph.jsonl")),
    Node("factor_residual_engine", "desks/mt5/research/factor_residual_engine.py",
         writes=("desks/mt5/data/intelligence/", "desks/mt5/reports/factor_residual.json"),
         reads=("desks/mt5/data/universe/",)),
    Node("plumbing_miner", "desks/mt5/research/plumbing_miner.py",
         writes=("desks/mt5/data/intelligence/", "desks/mt5/reports/plumbing_miner.json"),
         reads=("desks/mt5/data/universe/",)),
    Node("transition_alpha", "desks/mt5/research/transition_alpha.py",
         writes=("desks/mt5/data/intelligence/", "desks/mt5/reports/transition_alpha.json"),
         reads=("desks/mt5/data/universe/",)),
    Node("weak_signal_compiler", "desks/mt5/research/weak_signal_compiler.py",
         writes=("desks/mt5/data/intelligence/", "desks/mt5/reports/weak_signal_compiler.json"),
         reads=("desks/mt5/reports/universal_gates_external.json", "desks/mt5/data/universe/")),
    Node("fund_playbook", "desks/mt5/research/fund_playbook.py",
         writes=("desks/mt5/data/intelligence/", "desks/mt5/reports/FUND_PLAYBOOK.json",
                 "desks/mt5/data/hypothesis_graph.jsonl")),
    Node("external_gauntlet", "desks/mt5/scripts/external_gauntlet.py",
         # the authority file itself: every certificate the ten gates minted, which the canon
         # copy floors and the recertification audit re-judges
         writes=("desks/mt5/reports/universal_gates_external.json",
                 "desks/mt5/reports/UNIVERSAL_SURVIVORS.json"),
         reads=("desks/mt5/data/hypotheses/miner_candidates.json", "desks/mt5/data/universe/",
                "desks/mt5/reports/SCALP_GAUNTLET.json",
                # THE TICK TAPE REACHES A CERTIFICATE THROUGH HERE, and it always has --
                # external_gauntlet.py:329 calls `inputs._tape_series(sym, h1.index)`, which
                # reads data/tape/ticks/<SYM>/<DAY>.parquet and hands the spread and flow series
                # to the liquidity_regime and orderflow_imbalance families. The edge was real
                # and undeclared, so the graph could not see that a starved tape starves two
                # families of the gauntlet.
                "desks/mt5/data/tape/ticks/"),
         authority=("certificate",)),
    Node("scalp_gauntlet", "desks/mt5/scripts/scalp_gauntlet.py",
         # the scalp lane's ten-gate verdicts and certificates; external_gauntlet merges the
         # passes into the canon under `scalp.<candidate>` (certificate authority stays there)
         writes=("desks/mt5/reports/SCALP_GAUNTLET.json",),
         reads=("desks/mt5/data/universe/",)),
    Node("universal_gate", "desks/mt5/research/universal_gate.py",
         writes=("desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",),
         reads=("desks/mt5/data/universe/",), authority=("certificate",)),
    Node("shadow_forward", "desks/mt5/research/shadow_forward.py",
         writes=("desks/mt5/reports/shadow/",),
         reads=("desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json", "desks/mt5/data/universe/")),
    Node("promoter", "desks/mt5/research/promoter.py",
         # sleeves.json is the LIVE roster the gateway trades from; the promoter writes a
         # matured candidate there on the run its clock matures (automatic, principal 2026-09-04).
         writes=("desks/mt5/data/sleeve_registry.json", "desks/mt5/data/sleeves.json"),
         reads=("desks/mt5/reports/shadow/", "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
                # the daily re-judge of every certificate at today's costs: a fresh
                # COST_REGRADE_FAIL refuses promotion (BLOCKED_COST_REGRADE)
                "desks/mt5/reports/recertification_audit.json",
                # THE CAPITAL DOOR (principal 2026-09-05). `admission.candidates[*]` is the
                # dE[log W] of adding each candidate to the book the desk holds, and the
                # promoter gives capital to nothing that fails it; `book` and `book_zeroed`
                # are the current reading a LIVE sleeve is demoted on. A scan older than
                # `promoter.ADMISSION_MAX_AGE_H` may neither add risk nor remove it.
                "desks/mt5/reports/pf_allocation.json"),
         freshness_s={"desks/mt5/reports/pf_allocation.json": 26 * 3600},
         authority=("promotion",)),
    Node("recertify_canon", "desks/mt5/scripts/recertify_canon.py",
         reads=("desks/mt5/reports/UNIVERSAL_SURVIVORS.json", "desks/mt5/data/universe/"),
         writes=("desks/mt5/reports/recertification_audit.json",)),
    # THE WORLD'S CLOCK, and note what it does NOT claim. Its authority is over WHEN the
    # allocator solves, never over what the allocator decides -- so it is wired here as a
    # timing organ, not a sizing one. Every fitted quantity it owns reads UNMEASURED until its
    # ledger holds real events, and it refuses capital authority to every category until then.
    Node("macro_intel", "desks/mt5/macro/run_macro_intel.py",
         # reads its OWN prior state back -- the taxonomy centroids, the credibility
         # posteriors, the factor basis and the multiplicity charge are all cumulative. That
         # self-edge is the thing that makes this learn rather than restate.
         # Named one by one, not as a directory: the fence checks artifacts, and a directory
         # prefix let three of these read as DEAD_PRODUCER while they were in fact this node's
         # own memory. `multiplicity.json` is the cumulative Bonferroni charge -- re-read every
         # pass precisely so re-testing a cell makes admission HARDER, never easier -- and
         # `event_attribution.jsonl` is where the measured decay half-lives come back from,
         # which is the loop that lets the interrupt gate ever fire.
         reads=("desks/mt5/data/universe/", "desks/mt5/data/macro/",
                "desks/mt5/data/macro/taxonomy.json",
                "desks/mt5/data/macro/source_credibility.json",
                "desks/mt5/data/macro/factor_basis.json",
                "desks/mt5/data/macro/exposures.json",
                "desks/mt5/data/macro/multiplicity.json",
                "desks/mt5/data/macro/event_attribution.jsonl",
                "desks/mt5/data/macro/event_ledger.jsonl"),
         writes=("desks/mt5/data/macro/event_ledger.jsonl",
                 "desks/mt5/data/macro/allocator_interrupt.json",
                 "desks/mt5/data/macro/interrupt_log.jsonl",
                 "desks/mt5/data/macro/taxonomy.json",
                 "desks/mt5/data/macro/source_credibility.json",
                 "desks/mt5/data/macro/factor_basis.json",
                 "desks/mt5/data/macro/exposures.json",
                 "desks/mt5/data/macro/multiplicity.json",
                 "desks/mt5/data/macro/event_attribution.jsonl",
                 "desks/mt5/reports/MACRO_INTEL.json"),
         # ITS AUTHORITY IS THE CLOCK, NOT THE BOOK. `research_supervisor.tick_periodic` reads
         # `allocator_interrupt.json` and may bring the allocator's fast leg forward; nothing
         # here ever reaches a weight. Declared so the fence measures what this actually
         # decides -- without it the node reads as ADVISORY_ONLY, which would be wrong in the
         # dangerous direction: a timing organ that silently gained sizing authority would look
         # identical to one that never had any.
         authority=("allocator_solve_timing",)),
    Node("world_causal_graph", "desks/mt5/research/world_causal_graph.py",
         reads=("desks/mt5/data/universe/", "desks/mt5/data/deep_forest_claims.jsonl",
                "desks/mt5/reports/CROSS_ASSET_GRAPH.json",
                "desks/mt5/data/world_causal_graph.json"),
         writes=("desks/mt5/data/world_causal_graph.json",
                 "desks/mt5/reports/WORLD_CAUSAL_GRAPH.json")),
    Node("state_vector_build", "desks/mt5/research/state_vector_build.py",
         writes=("desks/mt5/data/state_vector.json", "desks/mt5/data/state_fits.json"),
         reads=("desks/mt5/data/universe/", "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
                "desks/mt5/data/intelligence/ff_calendar_vintage",
                "desks/mt5/data/state_fits.json",
                # the admitted upstream nodes it turns into conditioning hints, and the graph
                # itself as the fallback when reports/ has not been written on this box
                "desks/mt5/reports/WORLD_CAUSAL_GRAPH.json",
                "desks/mt5/data/world_causal_graph.json")),
    Node("state_admission_run", "desks/mt5/research/state_admission_run.py",
         writes=("desks/mt5/reports/STATE_ADMISSION.json",),
         reads=("backups/moat/shadow_ledgers/", "desks/mt5/data/live_ledger.jsonl"),
         authority=("conditioning",)),
    Node("pf_allocator", "desks/mt5/research/pf_allocator.py",
         writes=("desks/mt5/reports/ALLOCATOR_PROOF.json", "desks/mt5/data/pf_forecast_log.jsonl",
                 "desks/mt5/reports/pf_allocator.json", "desks/mt5/reports/pf_allocation.json",
                 "desks/mt5/data/capital_modifier_ledger.jsonl"),
         reads=("desks/mt5/data/state_vector.json", "desks/mt5/reports/STATE_ADMISSION.json",
                "backups/moat/shadow_ledgers/", "desks/mt5/data/universe/",
                "desks/mt5/reports/hunt12_partial.json", "desks/mt5/data/rail_calibration.json"),
         authority=("sizing",),
         freshness_s={"desks/mt5/data/state_vector.json": 2 * 3600,
                      "desks/mt5/reports/STATE_ADMISSION.json": 3 * 24 * 3600},
         conditions_on=("session", "event", "weekday")),
    Node("gateway", "desks/mt5/mt5desk/gateway.py",
         writes=("desks/mt5/data/gateway_state.json", "desks/mt5/data/order_intents.jsonl",
                 "desks/mt5/data/live_ledger.jsonl", "desks/mt5/data/decision_ledger.jsonl",
                 # via research.session_phase._record_broker_clock, from the live terminal
                 "desks/mt5/data/broker_clock.json",
                 # via mt5desk.netting.TheoreticalBook and execution_registry.record_outcome:
                 # every sleeve's desired position and fill, and what each fill cost against
                 # what the market plan expected
                 "desks/mt5/data/theoretical_positions.jsonl",
                 "desks/mt5/data/execution_algo_outcomes.jsonl"),
         reads=("desks/mt5/reports/ALLOCATOR_PROOF.json", "desks/mt5/data/sleeve_registry.json",
                "desks/mt5/data/state_vector.json", "desks/mt5/data/regime_state.json",
                "desks/mt5/reports/pf_allocation.json", "desks/mt5/data/RELEASE.json",
                "desks/mt5/data/theoretical_positions.jsonl", "desks/mt5/data/sleeves.json"),
         authority=("position", "size"),
         freshness_s={"desks/mt5/reports/ALLOCATOR_PROOF.json": 26 * 3600}),
    # THE GROWTH GOVERNANCE LOOP: every rail billed daily, tunable rails calibrated toward
    # growth, the AI capital modifier's categories scored against what they claimed.
    Node("missed_growth", "desks/mt5/research/missed_growth.py",
         reads=("desks/mt5/reports/pf_allocation.json", "desks/mt5/reports/FILTER_VALUE.json",
                "desks/mt5/reports/STATE_ADMISSION.json",
                # VETO_ALPHA: the counterfactual world's per-reason table, which `_veto_evidence`
                # merges over FILTER_VALUE's rows -- the veto rails' better evidence.
                "desks/mt5/reports/COUNTERFACTUAL_WORLD.json"),
         writes=("desks/mt5/reports/MISSED_GROWTH.json", "desks/mt5/data/missed_growth.jsonl",
                 "desks/mt5/data/rail_calibration.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("capital_modifier_score", "desks/mt5/research/capital_modifier_score.py",
         reads=("desks/mt5/data/capital_modifier_ledger.jsonl", "backups/moat/shadow_ledgers/"),
         writes=("desks/mt5/reports/CAPITAL_MODIFIERS.json",)),
    # EXECUTION INTELLIGENCE AND THE RELEASE: the learned fill/slip surface every cost consumer
    # shares, the netting measurement, and the one live SHA every decision is stamped with.
    Node("fill_surface", "desks/mt5/mt5desk/fill_surface.py",
         reads=("desks/mt5/data/order_intents.jsonl", "desks/mt5/reports/markout.json"),
         writes=("desks/mt5/reports/FILL_SURFACE.json",)),
    # THE THEORETICAL-POSITION LEDGER (2026-09-05): the gateway asserts every sleeve's desired
    # signed position and records every fill into `netting.TheoreticalBook`; `netting.route`
    # then computes the ONE order the venue would see per symbol. The gateway logs that order as
    # NET WOULD SEND -- measured, never placed -- and the algorithm registry's expected-vs-realised
    # ledger feeds the daily execution report. Both ledgers are written FROM the gateway process,
    # which is why the gateway node declares them; this module owns the replay and the report.
    Node("netting", "desks/mt5/mt5desk/netting.py",
         reads=("desks/mt5/data/order_intents.jsonl",
                "desks/mt5/data/theoretical_positions.jsonl"),
         writes=("desks/mt5/reports/NETTING.json", "desks/mt5/reports/NETTING_BOOK.json")),
    # ALPHA CAPTURE (2026-09-05, the principal's order): realised edge over predicted
    # FRICTIONLESS edge, per sleeve, session and symbol, trended over its own history. The one
    # number that separates a strategy that stopped working from a strategy being taken apart
    # between the decision and the fill. Reads the fill corpus the hourly twin assembles.
    Node("execution_intelligence", "desks/mt5/research/execution_intelligence.py",
         reads=("desks/mt5/data/order_intents.jsonl",
                "desks/mt5/data/theoretical_positions.jsonl",
                "desks/mt5/data/execution_algo_outcomes.jsonl", "desks/mt5/reports/markout.json",
                "desks/mt5/data/fill_corpus.jsonl",
                "desks/mt5/data/alpha_capture_history.jsonl"),
         writes=("desks/mt5/reports/FILL_SURFACE.json", "desks/mt5/reports/NETTING.json",
                 "desks/mt5/reports/NETTING_BOOK.json", "desks/mt5/reports/ALPHA_CAPTURE.json",
                 "desks/mt5/data/alpha_capture_history.jsonl")),
    # THE EXECUTION DIGITAL TWIN (2026-09-05): every live intent joined to what the venue did,
    # calibrated, and turned into the correction the simulator should apply. ADVISORY until
    # engine.Costs / external_gauntlet.costs_for read EXECUTION_TWIN.json: when that wiring
    # lands, add the report to the external_gauntlet node's `reads` and drop it from HUMAN_READ
    # so the graph shows the Live -> Simulator path instead of a report a person reads.
    # THE FILL CORPUS (2026-09-05, the principal's order) is assembled on the SAME clock, because
    # it is a join over the ledgers this node already reads plus four that resolve late (the
    # decision ledger, the counterfactual dataset, the excursions and the tick tape). It is the
    # desk's one unrebuildable asset -- an unrecorded fill cannot be recovered -- and it is
    # HUMAN_READ on purpose: `execution_intelligence` prices the alpha capture ratio off it, but
    # neither the conditional execution-choice model nor the meta-labeler is wired to anything
    # that sends an order, and both are UNMEASURED until the corpus reaches their required n.
    # When one of them is wired, drop the corpus from HUMAN_READ and declare the consumer here.
    Node("execution_twin", "desks/mt5/research/execution_twin.py",
         reads=("desks/mt5/data/order_intents.jsonl",
                "desks/mt5/data/execution_algo_outcomes.jsonl",
                "desks/mt5/data/live_ledger.jsonl", "desks/mt5/data/universe/",
                "desks/mt5/data/execution_twin_state.json",
                "desks/mt5/data/execution_twin_cases.jsonl",
                "desks/mt5/data/decision_ledger.jsonl",
                "desks/mt5/data/decision_dataset.jsonl",
                "desks/mt5/data/excursions.jsonl",
                "desks/mt5/data/tape/",
                "desks/mt5/data/fill_corpus.jsonl"),
         writes=("desks/mt5/reports/EXECUTION_TWIN.json",
                 "desks/mt5/data/execution_twin_cases.jsonl",
                 "desks/mt5/data/execution_twin_state.json",
                 "desks/mt5/data/fill_corpus.jsonl")),
    # THE PORTFOLIO GAP (scheduled 2026-09-05; it existed with no clock): what the book cannot
    # fill and where research should point. ADVISORY until the research bandit reads it.
    # THE COUNTERFACTUAL WORLD (2026-09-05, the principal's order): every decision minute joined
    # from the eleven ledgers and priced against every alternative -- entered/skipped,
    # 0.5x/1x/1.5x, market/limit/delayed, fixed TP/trail/hold/partial -- with the desk's own cost
    # posterior, named on every row. ADVISORY until missed_growth reads VETO_ALPHA off
    # COUNTERFACTUAL_WORLD.json; when that wiring lands, add the report to the missed_growth
    # node's `reads` and drop it from HUMAN_READ, so the graph shows the Behaviour -> Rail path
    # instead of a report a person reads.
    Node("counterfactual_replay", "desks/mt5/research/counterfactual_replay.py",
         reads=("desks/mt5/data/decision_ledger.jsonl", "desks/mt5/data/order_intents.jsonl",
                "desks/mt5/data/live_ledger.jsonl",
                "desks/mt5/data/theoretical_positions.jsonl",
                "desks/mt5/data/execution_algo_outcomes.jsonl",
                "desks/mt5/data/broker_clock.json", "desks/mt5/data/pf_forecast_log.jsonl",
                "desks/mt5/data/capital_modifier_ledger.jsonl",
                "desks/mt5/data/counterfactuals.jsonl",
                "desks/mt5/data/action_counterfactuals.jsonl",
                "desks/mt5/data/excursions.jsonl",
                "desks/mt5/reports/EXECUTION_TWIN.json", "desks/mt5/reports/FILL_SURFACE.json",
                "desks/mt5/data/universe/", "desks/mt5/data/decision_dataset.jsonl",
                "desks/mt5/data/decision_dataset_watermark.json"),
         writes=("desks/mt5/reports/COUNTERFACTUAL_WORLD.json",
                 "desks/mt5/data/decision_dataset.jsonl",
                 "desks/mt5/data/decision_dataset_watermark.json")),
    Node("portfolio_gap", "desks/mt5/research/portfolio_gap.py",
         reads=("desks/mt5/reports/pf_allocation.json",
                "desks/mt5/reports/UNIVERSAL_SURVIVORS.json"),
         writes=("desks/mt5/reports/portfolio_gap.json",)),
    Node("release", "libs/ops/release.py",
         reads=("desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
                "desks/mt5/data/IMMUTABLE_MANIFEST.json", "desks/mt5/data/sleeves.json"),
         writes=("desks/mt5/data/RELEASE.json",)),
    # RELEASE IDENTITY (2026-09-05): the running SHA measured against the sealed release. The
    # gateway asks `release_identity.verdict()` every pass and opens nothing new on a refusal;
    # the verdict file rides the box's git sync so every brain can read it, and the hourly smoke
    # test proves the money-path modules on the box import and match the seal.
    # The signed money-path manifest: `--sign` is a person's act after a reviewed change; the
    # release seal and the box smoke test both verify against it.
    Node("immutable_evaluator", "scripts/check_immutable_evaluator.py",
         writes=("desks/mt5/data/IMMUTABLE_MANIFEST.json",)),
    Node("release_identity", "desks/mt5/mt5desk/release_identity.py",
         reads=("desks/mt5/data/RELEASE.json",),
         writes=("desks/mt5/data/release_identity.json",)),
    Node("smoke_release", "desks/mt5/scripts/smoke_release.py",
         reads=("desks/mt5/data/RELEASE.json",),
         writes=("desks/mt5/reports/release_smoke.json",)),
    # THE PROPRIETARY-DATA FLYWHEEL: every decision the desk made, taken or not, priced after the
    # fact and fed back as research targets. None of these nodes has authority; each feeds one.
    Node("counterfactual_markout", "desks/mt5/research/counterfactual_markout.py",
         reads=("desks/mt5/data/decision_ledger.jsonl", "desks/mt5/data/universe/"),
         writes=("desks/mt5/data/counterfactuals.jsonl", "desks/mt5/reports/FILTER_VALUE.json")),
    Node("excursions", "desks/mt5/research/excursions.py",
         reads=("backups/moat/shadow_ledgers/", "desks/mt5/data/universe/"),
         writes=("desks/mt5/data/excursions.jsonl", "desks/mt5/reports/EXCURSIONS.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("alpha_genome", "desks/mt5/research/alpha_genome.py",
         reads=("desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",),
         writes=("desks/mt5/reports/ALPHA_GENOME.json",)),
    Node("opportunity_curve", "desks/mt5/research/opportunity_curve.py",
         reads=("backups/moat/shadow_ledgers/", "desks/mt5/data/broker_clock.json"),
         writes=("desks/mt5/reports/OPPORTUNITY_CURVE.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("microstructure_miner", "desks/mt5/research/microstructure_miner.py",
         reads=("desks/mt5/data/universe/",),
         writes=("desks/mt5/data/intelligence/", "desks/mt5/reports/MICROSTRUCTURE_SURFACES.json",
                 "desks/mt5/reports/microstructure_miner.json")),
    Node("markout", "desks/mt5/mt5desk/markout.py",
         reads=("desks/mt5/data/order_intents.jsonl", "desks/mt5/data/live_ledger.jsonl"),
         writes=("desks/mt5/reports/markout.json",)),
    Node("allocator_attribution", "desks/mt5/research/allocator_attribution.py",
         reads=("desks/mt5/data/pf_forecast_log.jsonl", "desks/mt5/data/live_ledger.jsonl",
                "desks/mt5/data/order_intents.jsonl",
                # the growth decomposition (2026-09-04) reads every term's own ledger
                "desks/mt5/reports/ALLOCATOR_PROOF.json", "desks/mt5/reports/pf_allocation.json",
                "desks/mt5/reports/EXIT_ACCOUNTS.json", "desks/mt5/reports/FILL_SURFACE.json",
                "desks/mt5/reports/FILTER_VALUE.json", "desks/mt5/reports/MISSED_GROWTH.json",
                # the ENTRY term's ledger (nothing read it before) and research P&L per source
                "desks/mt5/reports/EXCURSIONS.json", "desks/mt5/reports/RESEARCH_PNL.json"),
         writes=("desks/mt5/reports/allocator_attribution.json",
                 "desks/mt5/reports/GROWTH_ATTRIBUTION_WEEKLY.json")),
    Node("regime_monitor", "desks/mt5/research/regime_monitor.py",
         reads=("desks/mt5/data/live_ledger.jsonl", "desks/mt5/reports/shadow/",
                "desks/mt5/reports/FILTER_VALUE.json"),
         writes=("desks/mt5/data/regime_state.json",), authority=("hibernate",)),
    Node("regime_coverage", "desks/mt5/research/regime_coverage.py",
         reads=("backups/moat/shadow_ledgers/", "desks/mt5/reports/STATE_ADMISSION.json",
                "desks/mt5/reports/ALPHA_GENOME.json"),
         writes=("desks/mt5/reports/REGIME_COVERAGE.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    # THE BREADTH LANE (2026-09-05). Three producers answering the principal's three questions --
    # how many independent bets the book actually is, what pays inside its own worst periods, and
    # which states of a surviving edge deserve capital. Each reaches a decision the same way
    # regime_coverage and opportunity_curve do: through the deepening queue, which the worker
    # reads hourly and whose deepened candidates the gauntlet certifies.
    Node("alpha_breadth", "desks/mt5/research/alpha_breadth.py",
         reads=("backups/moat/shadow_ledgers/", "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
                "desks/mt5/data/universe/"),
         writes=("desks/mt5/reports/EFFECTIVE_BREADTH.json",
                 "desks/mt5/data/effective_breadth.jsonl",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    # The lane is a CHAIN, not three parallel reports: the breadth ledger owns cluster occupancy
    # and the drawdown factory reads it rather than recomputing a second answer to the same word;
    # the survivor miner reads the drawdown's state signature, because a state where a surviving
    # edge is stronger AND the rest of the book is losing is drawdown alpha the desk already owns.
    Node("drawdown_alpha", "desks/mt5/research/drawdown_alpha.py",
         reads=("backups/moat/shadow_ledgers/", "desks/mt5/reports/EFFECTIVE_BREADTH.json"),
         writes=("desks/mt5/reports/DRAWDOWN_ALPHA.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("survivor_neighbourhood", "desks/mt5/research/survivor_neighbourhood.py",
         reads=("backups/moat/shadow_ledgers/", "desks/mt5/reports/DRAWDOWN_ALPHA.json"),
         writes=("desks/mt5/reports/SURVIVOR_NEIGHBOURHOOD.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("resurrection", "desks/mt5/research/resurrection.py",
         reads=("desks/mt5/data/regime_state.json", "desks/mt5/data/state_vector.json",
                "backups/moat/shadow_ledgers/"),
         writes=("desks/mt5/reports/RESURRECTION.json",)),
    Node("data_prospector", "desks/mt5/research/data_prospector.py",
         reads=("desks/mt5/reports/REGIME_COVERAGE.json", "desks/mt5/data/state_vector.json"),
         writes=("desks/mt5/reports/DATA_PROSPECTOR.json",
                 "desks/mt5/data/prospector_targets.json")),
    Node("research_productivity", "desks/mt5/research/research_productivity.py",
         reads=("desks/mt5/data/hypotheses/deepening_worked.jsonl",
                "desks/mt5/data/hypotheses/miner_candidates.json",
                "desks/mt5/data/hypotheses/miner_deepening_queue.json",
                "desks/mt5/reports/universal_gates_external.json",
                "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json"),
         writes=("desks/mt5/reports/RESEARCH_PRODUCTIVITY.json",)),
    Node("live_manifest", "desks/mt5/research/live_manifest.py",
         reads=("desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
                "desks/mt5/reports/ALLOCATOR_PROOF.json", "desks/mt5/data/gateway_state.json",
                "desks/mt5/data/state_vector.json", "desks/mt5/reports/STATE_ADMISSION.json",
                "desks/mt5/data/pf_forecast_log.jsonl"),
         writes=("desks/mt5/data/LIVE_MANIFEST.jsonl",)),
    # THE HOURLY DISCOVERY PASS (2026-09-05): every miner, proposer and data organ once an hour,
    # each in its own subprocess on a bandit-weighted budget. It decides nothing itself -- the
    # organs donate through the proposer contract as before -- so its own artifacts are the
    # per-organ status the fence reads and the ordering state the next pass reads.
    Node("hourly_discovery", "desks/mt5/research/hourly_discovery.py",
         reads=("desks/mt5/data/hourly_discovery_state.json",),
         writes=("desks/mt5/reports/HOURLY_DISCOVERY.json",
                 "desks/mt5/data/hourly_discovery_state.json")),
    # ---- THE DISCOVERY LOOP (2026-09-04): proposers, miners, feedback engines -----------------
    # Every proposer donates through proposer_common.donate into the intelligence intake the
    # compiler merges; every miner writes deepening tasks; every feedback engine writes a report
    # a person reads AND a queue row the worker reads. Declared so a producer nobody consumes
    # shows up red rather than looking busy.
    Node("alpha_evolution", "desks/mt5/research/alpha_evolution.py",
         reads=("desks/mt5/data/universe/", "backups/moat/shadow_ledgers/",
                "desks/mt5/data/generator_weights.json",
                # 2026-09-05: the three derived populations mine these ledgers, and the
                # portfolio-aware fitness prices a candidate against the book it would join.
                "desks/mt5/data/hypothesis_graph.jsonl",
                "desks/mt5/data/world_causal_graph.json",
                "desks/mt5/data/deep_forest_claims.jsonl",
                "desks/mt5/reports/pf_allocation.json"),
         writes=("desks/mt5/reports/alpha_evolution.json",
                 "desks/mt5/data/intelligence/alpha_evolution/")),
    Node("style_premia_sweep", "desks/mt5/research/style_premia_sweep.py",
         reads=("desks/mt5/data/universe/",),
         writes=("desks/mt5/reports/style_premia_sweep.json",
                 "desks/mt5/data/intelligence/style_premia/")),
    Node("cross_asset_graph", "desks/mt5/research/cross_asset_graph.py",
         reads=("desks/mt5/data/universe/",),
         writes=("desks/mt5/reports/CROSS_ASSET_GRAPH.json",
                 "desks/mt5/data/intelligence/cross_asset_graph/")),
    Node("tail_alpha_search", "desks/mt5/research/tail_alpha_search.py",
         reads=("desks/mt5/data/universe/", "backups/moat/shadow_ledgers/"),
         writes=("desks/mt5/reports/tail_alpha_search.json",
                 "desks/mt5/data/intelligence/tail_alpha/")),
    Node("anomaly_factory", "desks/mt5/research/anomaly_factory.py",
         reads=("desks/mt5/data/universe/", "desks/mt5/data/hypothesis_graph.jsonl",
                "desks/mt5/data/intelligence/anomalies/",
                "desks/mt5/data/intelligence/anomaly_cursor.json", "desks/mt5/data/acquired/"),
         writes=("desks/mt5/reports/ANOMALY_FACTORY.json",
                 "desks/mt5/data/intelligence/anomaly_factory/",
                 "desks/mt5/data/intelligence/anomalies/",
                 "desks/mt5/data/intelligence/anomaly_cursor.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("survivor_distiller", "desks/mt5/research/survivor_distiller.py",
         reads=("desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
                "desks/mt5/data/hypothesis_graph.jsonl",
                "desks/mt5/data/mutation_operator_weights.json"),
         writes=("desks/mt5/reports/SURVIVOR_DISTILLER.json",
                 "desks/mt5/data/intelligence/survivor_distiller/",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("factor_model_coevolution", "desks/mt5/research/factor_model_coevolution.py",
         reads=("desks/mt5/data/universe/", "desks/mt5/data/features/",
                "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json"),
         writes=("desks/mt5/reports/COEVOLUTION.json", "desks/mt5/data/coevolution_trials.jsonl",
                 "desks/mt5/data/features/",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("repo_miner", "desks/mt5/research/repo_miner.py",
         reads=("desks/mt5/data/repo_watchlist.json", "desks/mt5/data/repo_cache/"),
         writes=("desks/mt5/reports/REPO_MINER.json", "desks/mt5/data/repo_cache/",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("deep_forest_miner", "desks/mt5/research/deep_forest_miner.py",
         reads=("desks/mt5/data/deep_forest_sources.json",
                "desks/mt5/data/deep_forest_claims.jsonl",
                "desks/mt5/data/deep_forest_seen.json", "desks/mt5/data/universe/universe.json",
                "desks/mt5/data/hypotheses/deepening_worked.jsonl"),
         writes=("desks/mt5/reports/DEEP_FOREST.json", "desks/mt5/data/deep_forest_claims.jsonl",
                 "desks/mt5/data/deep_forest_seen.json",
                 "desks/mt5/data/intelligence/world/frontier.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("revival_engine", "desks/mt5/research/revival_engine.py",
         reads=("desks/mt5/data/hypothesis_graph.jsonl", "desks/mt5/reports/DRIFT.json",
                "desks/mt5/reports/REGIME_COVERAGE.json", "desks/mt5/reports/FILL_SURFACE.json"),
         writes=("desks/mt5/reports/REVIVAL.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("drift_monitor", "desks/mt5/research/drift_monitor.py",
         reads=("desks/mt5/data/universe/", "backups/moat/shadow_ledgers/",
                "desks/mt5/reports/shadow/", "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
                # the hazard channels: admission verdicts, realised execution cost, edge signs
                "desks/mt5/reports/STATE_ADMISSION.json", "desks/mt5/reports/EXECUTION_TWIN.json",
                "desks/mt5/reports/CROSS_ASSET_GRAPH.json"),
         writes=("desks/mt5/reports/DRIFT.json",)),
    Node("exit_accounts", "desks/mt5/research/exit_accounts.py",
         reads=("backups/moat/shadow_ledgers/", "desks/mt5/data/excursions.jsonl",
                "desks/mt5/data/live_ledger.jsonl", "desks/mt5/data/pf_forecast_log.jsonl"),
         writes=("desks/mt5/reports/EXIT_ACCOUNTS.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("action_counterfactuals", "desks/mt5/research/action_counterfactuals.py",
         reads=("backups/moat/shadow_ledgers/", "desks/mt5/data/live_ledger.jsonl",
                "desks/mt5/data/pf_forecast_log.jsonl", "desks/mt5/data/universe/"),
         writes=("desks/mt5/reports/ACTION_COUNTERFACTUALS.json",
                 "desks/mt5/data/action_counterfactuals.jsonl",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("research_pnl", "desks/mt5/research/research_pnl.py",
         reads=("desks/mt5/data/hypothesis_graph.jsonl",
                "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
                "desks/mt5/data/pf_forecast_log.jsonl"),
         writes=("desks/mt5/reports/RESEARCH_PNL.json", "desks/mt5/data/research_marginal.json")),
    Node("mutation_yield", "desks/mt5/research/mutation_yield.py",
         reads=("desks/mt5/data/hypothesis_graph.jsonl",
                "desks/mt5/data/intelligence/survivor_distiller/"),
         writes=("desks/mt5/reports/MUTATION_YIELD.json",
                 "desks/mt5/data/mutation_operator_weights.json",
                 "desks/mt5/data/generator_weights.json")),
    Node("research_memory", "libs/research/memory.py",
         reads=("desks/mt5/data/hypothesis_graph.jsonl",
                "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
                "desks/mt5/reports/FILL_SURFACE.json", "desks/mt5/reports/NETTING.json",
                "desks/mt5/reports/REGIME_COVERAGE.json", "docs/graveyard.md",
                "docs/research/search_operator_library.md", "docs/GROWTH_GOVERNANCE.md"),
         writes=("desks/mt5/data/memory/",)),
    Node("feature_roi", "desks/mt5/research/feature_roi.py",
         reads=("desks/mt5/data/capital_modifier_ledger.jsonl",
                "desks/mt5/reports/CAPITAL_MODIFIERS.json",
                "desks/mt5/reports/allocator_attribution.json",
                "desks/mt5/reports/RESEARCH_PNL.json",
                "desks/mt5/reports/STATE_ADMISSION.json",
                "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json"),
         # It rewrites the sidecars' `status`/`roi` in place: the warehouse is both its input
         # population and where its verdict lands.
         writes=("desks/mt5/reports/FEATURE_ROI.json", "desks/mt5/data/features/"),
         # It DECIDES: `feature_lifecycle.withdraw` reads the status it writes, and an organ that
         # honours it stops spending compute. That is authority, not advice.
         authority=("feature_effort",)),
    Node("module_rent", "libs/ops/module_rent.py",
         reads=("desks/mt5/reports/MISSED_GROWTH.json", "desks/mt5/reports/RESEARCH_PNL.json",
                "desks/mt5/reports/STATE_ADMISSION.json",
                "desks/mt5/reports/CAPITAL_MODIFIERS.json",
                "desks/mt5/reports/pf_allocation.json",
                "desks/mt5/data/capital_modifier_ledger.jsonl",
                "desks/mt5/data/execution_algo_outcomes.jsonl",
                "desks/mt5/data/live_ledger.jsonl", "desks/mt5/reports/shadow/",
                "desks/mt5/data/module_rent.jsonl"),
         writes=("desks/mt5/reports/MODULE_RENT.json", "desks/mt5/data/module_rent.jsonl")),
    Node("research_bandit", "desks/mt5/research/research_bandit.py",
         reads=("desks/mt5/data/hypothesis_graph.jsonl", "desks/mt5/data/research_marginal.json",
                # dElog per data source and the DEAD INFORMATION list: the budget is where
                # naming becomes a decision.
                "desks/mt5/reports/allocator_attribution.json"),
         writes=("desks/mt5/data/research_budget.json",
                 "desks/mt5/reports/RESEARCH_BANDIT.json")),

    # ----------------------------------------------------------- THE DATA MOAT --
    # Three nodes forming one chain, and the chain is the argument: the recorder captures what
    # cannot be recaptured, the checker proves what was captured, and only proven days become
    # features. Each reads the one before it, so a break anywhere is visible as a break rather
    # than as a quiet decline in coverage.
    #
    # THE TAPE ITSELF IS NOT A GRAPH ARTIFACT and cannot be: it lives at MT5_TAPE_ROOT
    # (C:\mt5tape by default), outside the git tree, because a directory growing by gigabytes a
    # year has no business in a repository. `reports/TAPE_RECORDER.json` is the recorder's one
    # in-repo output and exists precisely so the tape is observable from a box with no shell on
    # the Windows machine -- the reachability problem AGENTS.md names.
    Node("tick_recorder", "desks/mt5/recorders/tick_recorder.py",
         writes=("desks/mt5/reports/TAPE_RECORDER.json",)),
    Node("tick_integrity", "desks/mt5/recorders/tick_integrity.py",
         writes=("desks/mt5/reports/TICK_INTEGRITY.json",),
         reads=("desks/mt5/reports/TAPE_RECORDER.json",)),
    Node("tape_features", "desks/mt5/recorders/tape_features.py",
         # data/tape/ticks/ is the silver layer external_gauntlet already reads (see its node);
         # the rest are measured surfaces whose consumers are NAMED in the module's CONSUMERS
         # map and not yet wired, which is why they sit in HUMAN_READ rather than claiming a
         # decision path they do not have.
         writes=("desks/mt5/data/tape/ticks/", "desks/mt5/data/tape/intrabar/",
                 "desks/mt5/data/cost_surface_tick.json",
                 "desks/mt5/data/tape/slippage_surface.json",
                 "desks/mt5/data/tape_features_state.json",
                 "desks/mt5/reports/TAPE_FEATURES.json"),
         reads=("desks/mt5/reports/TICK_INTEGRITY.json",
                "desks/mt5/data/universe/universe.json")),
    # The vol archive is ADVISORY BY CONSTRUCTION and its node says so: it holds no authority,
    # reaches no decision, and every one of its outputs is human-read. That is not a gap to close
    # later -- a forward-only dataset with no backtest may not condition capital, and the node is
    # where that claim is checkable rather than merely written in a docstring.
    Node("vol_archive", "desks/mt5/recorders/vol_archive.py",
         writes=("desks/mt5/data/vol_archive/observations.jsonl",
                 "desks/mt5/reports/VOL_ARCHIVE.json"),
         reads=("desks/mt5/data/universe/universe.json", "desks/mt5/data/universe/")),
)

#: Artifacts a person is expected to read. Being the ONLY reader of a node's output makes that
#: node advisory. Listed so the check has a definition rather than an opinion.
HUMAN_READ = frozenset({
    # The macro layer's report. Read by a person; the layer's one decision edge is the
    # interrupt above, declared in EXTERNAL_READERS with its reader named.
    "desks/mt5/reports/MACRO_INTEL.json",
    "desks/mt5/reports/markout.json", "desks/mt5/reports/allocator_attribution.json",
    "desks/mt5/reports/RESURRECTION.json", "desks/mt5/reports/DATA_PROSPECTOR.json",
    "desks/mt5/data/LIVE_MANIFEST.jsonl", "desks/mt5/reports/factor_residual.json",
    "desks/mt5/reports/plumbing_miner.json", "desks/mt5/reports/transition_alpha.json",
    "desks/mt5/reports/weak_signal_compiler.json", "desks/mt5/reports/FUND_PLAYBOOK.json",
    "desks/mt5/reports/pf_allocator.json", "desks/mt5/reports/REGIME_COVERAGE.json",
    "desks/mt5/reports/RESEARCH_PRODUCTIVITY.json", "desks/mt5/reports/FILTER_VALUE.json",
    "desks/mt5/reports/EXCURSIONS.json", "desks/mt5/reports/ALPHA_GENOME.json",
    "desks/mt5/reports/OPPORTUNITY_CURVE.json", "desks/mt5/reports/MICROSTRUCTURE_SURFACES.json",
    "desks/mt5/reports/microstructure_miner.json", "desks/mt5/reports/MISSED_GROWTH.json",
    "desks/mt5/reports/CAPITAL_MODIFIERS.json", "desks/mt5/reports/FILL_SURFACE.json",
    "desks/mt5/reports/NETTING.json", "desks/mt5/reports/NETTING_BOOK.json",
    # The execution twin's report, private dataset and watermark: advisory until the cost
    # model reads the report (see the execution_twin node). The portfolio gap likewise until
    # the research bandit reads it.
    "desks/mt5/reports/EXECUTION_TWIN.json", "desks/mt5/data/execution_twin_cases.jsonl",
    # THE FILL CORPUS and the alpha-capture ratio it prices. Human-read is the HONEST state
    # today, not a placeholder: the corpus is the collection asset, `ALPHA_CAPTURE.json` is the
    # measurement a person acts on, and the two models built on it (conditional execution choice,
    # meta-labeler) are UNMEASURED harnesses wired to nothing that sends an order. The day one of
    # them is wired, its consumer is declared and the corpus leaves this set.
    "desks/mt5/data/fill_corpus.jsonl", "desks/mt5/reports/ALPHA_CAPTURE.json",
    "desks/mt5/data/alpha_capture_history.jsonl",
    # The counterfactual world's report, its versioned dataset and its watermark: advisory
    # until missed_growth reads VETO_ALPHA off the report (see the counterfactual_replay node).
    "desks/mt5/reports/FEATURE_ROI.json", "desks/mt5/reports/MODULE_RENT.json",
    "desks/mt5/reports/GROWTH_ATTRIBUTION_WEEKLY.json",
    "desks/mt5/data/decision_dataset.jsonl",
    "desks/mt5/data/decision_dataset_watermark.json",
    "desks/mt5/data/execution_twin_state.json", "desks/mt5/reports/portfolio_gap.json",
    # THE DATA MOAT'S MEASURED SURFACES, advisory until their named consumers are switched.
    # `data/cost_surface_tick.json` is byte-compatible with what research/cost_surface.py writes,
    # so cost_surface.spread_pts() reads it with no code change -- but nothing points at it YET,
    # and claiming a decision path before the switch is made would be exactly the producer/
    # consumer collapse this graph exists to catch. Same for the slippage surface, whose consumer
    # (mt5desk/fill_surface.py's below-MIN_FILLS fallback constant) is named in
    # recorders/tape_features.CONSUMERS. Both switches deserve a before/after, not a silent edit.
    "desks/mt5/data/cost_surface_tick.json", "desks/mt5/data/tape/slippage_surface.json",
    "desks/mt5/reports/TAPE_FEATURES.json", "desks/mt5/reports/TICK_INTEGRITY.json",
    "desks/mt5/data/tape_features_state.json",
    # The vol archive: forward-only, no backtest, no promotion authority in any lane until its
    # own vintages are long enough. Human-read is the CORRECT terminal state for it today, not a
    # placeholder -- see recorders/vol_archive.py's MOAT CLAIM.
    "desks/mt5/reports/VOL_ARCHIVE.json",
    # The release-identity verdict and the box smoke test: read by every brain through the
    # box's git sync and by the dashboard; the gateway consumes the verdict in-process.
    "desks/mt5/data/release_identity.json", "desks/mt5/reports/release_smoke.json",
    # The hourly discovery pass's own bookkeeping: per-organ status for the fence and a person,
    # and the staleness order the next pass reads. The organs' donations reach decisions through
    # the compiler; this pass only schedules them.
    "desks/mt5/reports/HOURLY_DISCOVERY.json", "desks/mt5/data/hourly_discovery_state.json",
    "desks/mt5/reports/alpha_evolution.json", "desks/mt5/reports/style_premia_sweep.json",
    "desks/mt5/reports/CROSS_ASSET_GRAPH.json", "desks/mt5/reports/tail_alpha_search.json",
    "desks/mt5/reports/ANOMALY_FACTORY.json", "desks/mt5/reports/SURVIVOR_DISTILLER.json",
    "desks/mt5/reports/COEVOLUTION.json", "desks/mt5/reports/REPO_MINER.json",
    "desks/mt5/reports/DEEP_FOREST.json", "desks/mt5/reports/REVIVAL.json",
    "desks/mt5/reports/EXIT_ACCOUNTS.json", "desks/mt5/reports/ACTION_COUNTERFACTUALS.json",
    "desks/mt5/reports/RESEARCH_PNL.json", "desks/mt5/reports/MUTATION_YIELD.json",
    "desks/mt5/reports/RESEARCH_BANDIT.json",
    # THE BREADTH LANE'S REPORTS. Each producer's DECISION path is the deepening queue it also
    # writes; these three files are the evidence a person reads beside it -- nominal against
    # effective breadth with every reading's status, the book's own drawdown windows and what
    # earns inside them, and where a surviving edge is stronger or absent. None of them
    # conditions capital, and listing them here is the claim that they do not.
    "desks/mt5/reports/EFFECTIVE_BREADTH.json", "desks/mt5/reports/DRAWDOWN_ALPHA.json",
    "desks/mt5/reports/SURVIVOR_NEIGHBOURHOOD.json",
})

#: Consumers outside this graph that are known to read an artifact -- the crawler reads the
#: prospector's targets, the box's PowerShell reads the manifest. DECLARED, so a DEAD_PRODUCER
#: verdict cannot be silenced by an unnamed "something reads it".
EXTERNAL_READERS = {
    "desks/mt5/data/prospector_targets.json": "world_crawler (side_channels)",
    "desks/mt5/data/hypotheses/deepened_candidates.json": "external_gauntlet via compiler merge",
    "desks/mt5/data/state_fits.json": "state_vector_build (its own cache)",
    "desks/mt5/data/module_rent.jsonl": "module_rent (its own append-only window history)",
    "desks/mt5/data/vol_archive/observations.jsonl": ("vol_archive (its own append-only vintage "
                                                     "series; the archive IS the asset and is "
                                                     "read back to count desk vintages)"),
    "desks/mt5/data/tape/intrabar/": ("read per bar by whatever revalues the engine's fill "
                                      "semantics; NOT wired into mt5desk/engine.py, because "
                                      "every live certificate was minted under its current "
                                      "assumption and re-pricing the canon is a deliberate act"),
    # Append-only ledgers that are their own memory: each engine reads back what it wrote so
    # a decision is priced exactly once. Self-reads are not counted as readers by `check`.
    "desks/mt5/data/counterfactuals.jsonl": "counterfactual_markout (its own append-only memory)",
    "desks/mt5/data/excursions.jsonl": "excursions (its own append-only memory)",
    "desks/mt5/data/missed_growth.jsonl": "missed_growth (its own append-only memory)",
    "desks/mt5/data/action_counterfactuals.jsonl": "action_counterfactuals (its own memory)",
    "desks/mt5/data/deep_forest_claims.jsonl": "deep_forest_miner (its own append-only memory)",
    # THE MACRO LAYER'S MEMORY. Each of these is read back by `macro_intel` on its next pass and
    # by nothing else, which is precisely what makes the layer LEARN rather than restate: the
    # taxonomy's centroids move with the instances assigned to them, the credibility posteriors
    # accumulate a source's record, the factor basis is refitted, and the multiplicity charge
    # only ever grows so that re-testing a cell makes admission harder. Declared here with the
    # reason rather than left to read as DEAD_PRODUCER, because "nothing reads it" and "only its
    # own author reads it" are different facts and only one of them is a defect.
    "desks/mt5/data/macro/taxonomy.json": "macro_intel (its own category centroids)",
    "desks/mt5/data/macro/source_credibility.json": "macro_intel (its own Beta posteriors)",
    "desks/mt5/data/macro/factor_basis.json": "macro_intel (its own discovered factor basis)",
    "desks/mt5/data/macro/exposures.json": "macro_intel (its own admitted category->factor edges)",
    "desks/mt5/data/macro/multiplicity.json": ("macro_intel (its own never-shrinking Bonferroni "
                                               "charge; monotone by design)"),
    "desks/mt5/data/macro/event_attribution.jsonl": ("macro_intel (its own append-only memory; "
                                                     "the measured decay half-lives come back "
                                                     "from here, which is the loop that lets the "
                                                     "interrupt gate ever fire)"),
    "desks/mt5/data/macro/event_ledger.jsonl": "macro_intel (its own append-only event record)",
    "desks/mt5/data/macro/allocator_interrupt.json": ("research_supervisor.tick_periodic -- it "
                                                      "reads this to bring the allocator's fast "
                                                      "leg forward. The supervisor is a process "
                                                      "manager, not a graph node, so the edge is "
                                                      "declared here rather than left to read as "
                                                      "DEAD_PRODUCER. This is the ONLY artifact "
                                                      "of this layer that reaches a decision, and "
                                                      "the decision it reaches is WHEN to solve, "
                                                      "never what to hold."),
    "desks/mt5/data/macro/interrupt_log.jsonl": ("macro_intel (its own rate-limit window; an "
                                                 "interrupt that fires constantly is an "
                                                 "expensive clock)"),
    "desks/mt5/data/deep_forest_seen.json": "deep_forest_miner (its own seen-ledger)",
    "desks/mt5/data/intelligence/anomaly_cursor.json": "anomaly_miner (its own rotation cursor)",
    "desks/mt5/data/memory/": "deepening_worker.task_text (memory.prompt_context on every prompt)",
    "desks/mt5/data/research_budget.json": ("daily_cycle proposer budgets and deepening_worker "
                                            "voi_order, through bandit.arm_weight"),
    "desks/mt5/data/coevolution_trials.jsonl": "experiment_ledger (lifetime multiplicity)",
    "desks/mt5/data/intelligence/world/frontier.json": "world_crawler (side_channels)",
    "desks/mt5/data/repo_cache/": "repo_miner (its own cache)",
    "desks/mt5/data/intelligence/alpha_evolution/": "miner_candidate_compiler intake glob",
    "desks/mt5/data/intelligence/style_premia/": "miner_candidate_compiler intake glob",
    "desks/mt5/data/intelligence/cross_asset_graph/": "miner_candidate_compiler intake glob",
    "desks/mt5/data/intelligence/tail_alpha/": "miner_candidate_compiler intake glob",
    "desks/mt5/data/intelligence/anomaly_factory/": "miner_candidate_compiler intake glob",
    "desks/mt5/data/intelligence/survivor_distiller/": "miner_candidate_compiler intake glob",
    "desks/mt5/data/features/": "feature_store (content-addressed cache)",
    "desks/mt5/data/effective_breadth.jsonl": ("alpha_breadth (its own append-only series; a "
                                               "breadth number with no history cannot say whether "
                                               "the desk is widening or only adding names)"),
}

_PATH_RE = re.compile(r"[\"']((?:desks/mt5/|backups/|reports/|data/)[A-Za-z0-9_./-]+)[\"']")


def _covers(declared: str, path: str) -> bool:
    return path == declared or (declared.endswith("/") and path.startswith(declared))


#: Hand-maintained inputs: written by a person (or by the box's universe fetch), read by nodes.
#: Declared so a DEAD_CONSUMER verdict cannot be silenced by an unnamed "somebody writes it".
CONFIG_INPUTS = frozenset({
    "desks/mt5/data/repo_watchlist.json", "desks/mt5/data/deep_forest_sources.json",
    "desks/mt5/data/universe/universe.json",
    # Box-produced inputs: acquire_datasets fills this from the prospector's targets.
    "desks/mt5/data/acquired/",
    # Hand-written doctrine the research memory ingests as method and failure memories.
    "docs/graveyard.md", "docs/research/search_operator_library.md", "docs/GROWTH_GOVERNANCE.md",
})

MAX_DECISION_DEPTH = 5


def _decision_paths(start: Node, nodes: tuple[Node, ...],
                    read_by: Any) -> set[str]:
    """Chains from `start`'s outputs to an authority node or a declared external reader."""
    by_name = {x.name: x for x in nodes}
    found: set[str] = set()
    frontier: list[tuple[Node, str]] = [(start, start.name)]
    seen: set[str] = {start.name}
    depth = 0
    while frontier and depth < MAX_DECISION_DEPTH:
        nxt: list[tuple[Node, str]] = []
        for node, path in frontier:
            for w in node.writes:
                if w in EXTERNAL_READERS:
                    found.add(f"{path}->{EXTERNAL_READERS[w]}")
                for name in read_by(w):
                    reader = by_name.get(name)
                    if reader is None or name == node.name:
                        continue
                    if reader.authority:
                        found.add(f"{path}->{name}")
                    elif name not in seen:
                        seen.add(name)
                        nxt.append((reader, f"{path}->{name}"))
        frontier = nxt
        depth += 1
    return found


def check(nodes: tuple[Node, ...] = NODES) -> dict[str, Any]:
    writers: dict[str, list[str]] = {}
    readers: dict[str, list[str]] = {}
    for n in nodes:
        for w in n.writes:
            writers.setdefault(w, []).append(n.name)
        for r in n.reads:
            readers.setdefault(r, []).append(n.name)

    def _read_by(artifact: str) -> list[str]:
        out = []
        for r, names in readers.items():
            if _covers(r, artifact) or _covers(artifact, r):
                out.extend(names)
        return sorted(set(out))

    def _written_by(artifact: str) -> list[str]:
        out = []
        for w, names in writers.items():
            if _covers(w, artifact) or _covers(artifact, w):
                out.extend(names)
        return sorted(set(out))

    findings: list[dict[str, str]] = []
    for n in nodes:
        for w in n.writes:
            rd = [x for x in _read_by(w) if x != n.name]
            if not rd and w not in HUMAN_READ and w not in EXTERNAL_READERS:
                findings.append({"check": "DEAD_PRODUCER", "node": n.name, "artifact": w,
                                 "why": "written and read by nothing in the graph"})
        for r in n.reads:
            box_only = ("desks/mt5/data/universe/", "backups/moat/shadow_ledgers/",
                        "desks/mt5/data/intelligence/",
                        "desks/mt5/data/intelligence/ff_calendar_vintage",
                        "desks/mt5/reports/hunt12_partial.json")
            if (not _written_by(r) and not (r.endswith("/") and (ROOT / r).exists())
                    and r not in box_only and r not in CONFIG_INPUTS):
                findings.append({"check": "DEAD_CONSUMER", "node": n.name, "artifact": r,
                                 "why": "read and written by nothing in the graph"})
        if n.writes and not n.authority:
            # A producer reaches a decision when some chain of readers ends at an authority
            # node or at a declared EXTERNAL reader (regime_coverage -> deepening queue ->
            # deepening_worker -> deepened_candidates -> external_gauntlet is a real path, and
            # drift_monitor -> revival_engine -> deepening queue -> deepening_worker -> gauntlet
            # is one hop longer). Walked breadth-first over non-authority nodes to a bounded
            # depth, with the path recorded, so the verdict names the chain rather than a hop
            # count that happened to fit yesterday's graph.
            decision_readers = _decision_paths(n, nodes, _read_by)
            if not decision_readers and not all(w in HUMAN_READ for w in n.writes):
                findings.append({"check": "ADVISORY_ONLY", "node": n.name,
                                 "artifact": ", ".join(n.writes),
                                 "why": "computes artifacts that reach no decision"})

    # UNMEASURED_AUTHORITY: conditioning dimensions must be judged, and not buried.
    try:
        adm = json.loads((DESK / "reports" / "STATE_ADMISSION.json").read_text("utf-8"))
        judged = set((adm.get("verdicts") or {}).keys()) | set(adm.get("gaps") or {})
        buried = set(adm.get("graveyard") or [])
    except (OSError, ValueError):
        judged, buried = set(), set()
    for n in nodes:
        for dim in n.conditions_on:
            if dim in buried:
                findings.append({"check": "UNMEASURED_AUTHORITY", "node": n.name,
                                 "artifact": dim, "why": "conditions on a BURIED dimension"})
            elif judged and dim not in judged:
                findings.append({"check": "UNMEASURED_AUTHORITY", "node": n.name,
                                 "artifact": dim, "why": "conditions on a dimension never judged"})

    # UNDECLARED: path literals in a node's source that the graph does not know about.
    known = {p for n in nodes for p in (*n.writes, *n.reads)}
    for n in nodes:
        try:
            src = (ROOT / n.module).read_text("utf-8")
        except OSError:
            findings.append({"check": "MISSING_MODULE", "node": n.name, "artifact": n.module,
                             "why": "declared module does not exist"})
            continue
        for m in _PATH_RE.finditer(src):
            lit = m.group(1)
            if lit.endswith(".py"):
                continue                       # a module reference (release manifest), not data
            if lit.startswith("desks/mt5/") or lit.startswith("backups/"):
                full = lit
            else:
                full = f"desks/mt5/{lit}"
            if not any(_covers(k, full) or _covers(full, k) for k in known):
                findings.append({"check": "UNDECLARED", "node": n.name, "artifact": full,
                                 "why": "path literal in source not declared on any node"})

    fatal = [f for f in findings if f["check"] in
             ("DEAD_PRODUCER", "DEAD_CONSUMER", "ADVISORY_ONLY", "UNMEASURED_AUTHORITY",
              "MISSING_MODULE")]
    return {"generated_utc": datetime.now(tz=UTC).isoformat(), "nodes": len(nodes),
            "artifacts": len(set(writers) | set(readers)), "findings": findings,
            "fatal": fatal, "ok": not fatal}


def freshness(nodes: tuple[Node, ...] = NODES) -> list[dict[str, Any]]:
    """STALE_DECISION: an authority node's input older than its SLA. Runtime, not CI."""
    out = []
    now = datetime.now(tz=UTC).timestamp()
    for n in nodes:
        for art, sla in n.freshness_s.items():
            p = ROOT / art
            if not p.exists():
                out.append({"check": "STALE_DECISION", "node": n.name, "artifact": art,
                            "why": "input absent", "age_s": None, "sla_s": sla})
                continue
            age = now - p.stat().st_mtime
            if age > sla:
                out.append({"check": "STALE_DECISION", "node": n.name, "artifact": art,
                            "why": f"{age / 3600:.1f}h old, SLA {sla / 3600:.1f}h",
                            "age_s": int(age), "sla_s": sla})
    return out


def reachability(nodes: tuple[Node, ...] = NODES) -> dict[str, Any]:
    """For every artifact: which authority nodes it reaches, and through what path."""
    by_write: dict[str, list[Node]] = {}
    for n in nodes:
        for r in n.reads:
            by_write.setdefault(r, []).append(n)

    def _readers_of(art: str) -> list[Node]:
        out = []
        for r, ns in by_write.items():
            if _covers(r, art) or _covers(art, r):
                out.extend(ns)
        return out

    result: dict[str, Any] = {}
    all_arts = sorted({w for n in nodes for w in n.writes})
    for art in all_arts:
        paths: list[str] = []
        seen: set[str] = set()
        stack = [(art, [art])]
        while stack:
            cur, path = stack.pop()
            for n in _readers_of(cur):
                if n.name in seen:
                    continue
                seen.add(n.name)
                if n.authority:
                    paths.append(" -> ".join([*path, f"{n.name}[{','.join(n.authority)}]"]))
                for w in n.writes:
                    stack.append((w, [*path, n.name, w]))
        result[art] = {"reaches_authority": bool(paths), "paths": paths[:6],
                       "human_read": art in HUMAN_READ,
                       "external_reader": EXTERNAL_READERS.get(art)}
    return result


STAGES = ("CODED", "WIRED", "RUNNING", "DECISION_AFFECTING", "MEASURED", "LIVE_LEARNING")
RUNNING_WINDOW_S = 3 * 24 * 3600

#: Artifacts carrying REALISED outcomes -- what the market actually did with the desk's money.
#: A module reading one of these is reading consequences, not its own opinion. Prefix-matched.
OUTCOME_ARTIFACTS: tuple[str, ...] = (
    "desks/mt5/data/fills", "desks/mt5/data/execution_algo_outcomes.jsonl",
    "desks/mt5/data/forward", "desks/mt5/data/shadow", "desks/mt5/data/trades",
    "desks/mt5/reports/RESEARCH_PNL.json", "desks/mt5/reports/pf_allocation.json",
    "desks/mt5/data/gateway_state.json", "desks/mt5/data/decision_ledger.jsonl",
    "desks/mt5/data/counterfactual", "desks/mt5/data/module_rent.jsonl",
)


def stages(nodes: tuple[Node, ...] = NODES) -> dict[str, dict[str, Any]]:
    """Per node: CODED -> WIRED -> RUNNING -> DECISION_AFFECTING -> MEASURED -> LIVE_LEARNING.

    CODED               the module exists
    WIRED               every declared read has a producer (or is box data) and every write a
                        reader -- the check() has no fatal finding naming this node
    RUNNING             at least one of its written artifacts was refreshed inside the window
    DECISION_AFFECTING  a path from one of its writes reaches an authority node
    MEASURED            a ledger PRICES THIS MODULE BY NAME: a MODULE_RENT verdict of EARNS or
                        COSTS, a rail in MISSED_GROWTH, a filter in FILTER_VALUE, a term in the
                        attribution. Not "it exists and matters" -- somebody put a number on it.
    LIVE_LEARNING       the loop closes back onto the module: it reads a REALISED-OUTCOME artifact
                        and updates state it later consumes itself, so what the market did changes
                        what it does next

    TWO FREE PASSES WERE REMOVED HERE, 2026-09-05, AND THEY MATTERED MORE THAN THE MISSING RUNG.

    1. `measured = bool(n.authority) or ...`. Authority was being read as measurement, which is
       exactly backwards: authority is what makes a node DECISION_AFFECTING, and the more capital a
       node moves the MORE it needs a number on it, not less. Measured on this tree before the fix:
       all ten MEASURED nodes were free passes and not one appeared in any ledger -- seven via this
       line (gateway, pf_allocator, promoter, universal_gate, state_admission_run, regime_monitor,
       feature_roi).
    2. A node's own output carrying a `verdict` / `rails` / `categories` key counted as its
       measurement. That is self-certification: a module that writes a report saying it has a
       verdict was thereby credited with having been measured. The remaining three MEASURED nodes
       (capital_modifier_score, counterfactual_markout, missed_growth) came in this way.

    So the repo's headline "7 MEASURED" -- quoted approvingly in an outside audit as evidence the
    desk measures its organs -- was an artifact of the instrument, not a reading of the desk. The
    count drops when this runs, and the drop IS the finding: it is the distance between the
    architecture and the evidence, which is the whole thing the ladder exists to show. A number
    that only ever goes up is not a measurement.

    An absent ledger reads UNMEASURED, never MEASURED (L1.28a). MODULE_RENT.json is written by the
    daily cycle on the trading host, so in a container it is simply absent and every node honestly
    reads below MEASURED rather than being credited by default.
    """
    findings = check(nodes)["findings"]
    named = {f["node"] for f in findings if f["check"] in
             ("DEAD_PRODUCER", "DEAD_CONSUMER", "ADVISORY_ONLY", "UNMEASURED_AUTHORITY")}
    reach = reachability(nodes)
    measured_names: set[str] = set()
    for rel in ("reports/MISSED_GROWTH.json", "reports/FILTER_VALUE.json",
                "reports/allocator_attribution.json", "reports/CAPITAL_MODIFIERS.json",
                # MODULE_RENT is deliberately NOT in this list: the generic loop reads a report's
                # KEYS, which would credit a module whose rent row says UNMEASURED. It is read
                # verdict-aware just below.
                "reports/RESEARCH_PRODUCTIVITY.json"):
        try:
            doc = json.loads((DESK / rel).read_text("utf-8"))
            measured_names |= set(map(str, (doc.get("rails") or doc.get("filters") or
                                            doc.get("terms") or doc.get("categories") or
                                            doc.get("modules") or doc.get("stages")
                                            or {}).keys()))
        except (OSError, ValueError):
            continue
    # MODULE_RENT is the ledger built for exactly this question, so its VERDICT is read rather
    # than its mere presence: a row reading UNMEASURED or NOT_BINDING is the rent ledger saying it
    # could not price the module, and crediting that as MEASURED would re-introduce the free pass
    # through the one report that explicitly refuses to fold UNMEASURED into a pass.
    rent_priced: set[str] = set()
    try:
        rent = json.loads((DESK / "reports" / "MODULE_RENT.json").read_text("utf-8"))
        rows = rent.get("modules") or {}
        it = rows.items() if isinstance(rows, dict) else (
            (r.get("module"), r) for r in rows if isinstance(r, dict))
        for mod, row in it:
            if isinstance(row, dict) and str(row.get("verdict", "")).upper() in {"EARNS", "COSTS"}:
                rent_priced.add(str(mod))
    except (OSError, ValueError, AttributeError):
        pass
    measured_names |= rent_priced
    now = datetime.now(tz=UTC).timestamp()
    out: dict[str, dict[str, Any]] = {}
    for n in nodes:
        coded = (ROOT / n.module).exists()
        wired = coded and n.name not in named
        running = False
        for w in n.writes:
            p = ROOT / w
            try:
                if p.is_dir():
                    newest = max((f.stat().st_mtime for f in p.rglob("*") if f.is_file()),
                                 default=0.0)
                else:
                    newest = p.stat().st_mtime
                if now - newest < RUNNING_WINDOW_S:
                    running = True
                    break
            except OSError:
                continue
        decision = bool(n.authority) or any(
            (reach.get(w) or {}).get("reaches_authority") for w in n.writes)
        # A LEDGER PRICES THIS MODULE BY NAME. No authority pass, no self-certification.
        measured = (n.name in measured_names) or any(k.startswith(n.name) for k in measured_names)
        # LIVE_LEARNING: the loop closes back onto the module. It must read something the market
        # actually did, AND carry that into state it consumes itself -- a module that reads fills
        # and writes a report nobody feeds back has learned nothing, it has only reported.
        reads_outcome = any(r.startswith(o) or o.startswith(r)
                            for r in n.reads for o in OUTCOME_ARTIFACTS)
        feeds_itself = bool(set(n.writes) & set(n.reads))
        live_learning = measured and reads_outcome and feeds_itself
        if not coded:
            stage = "MISSING"
        elif not wired:
            # Previously this branch read WIRED whenever the node was merely not running, so an
            # unwired node with a fatal DEAD_PRODUCER finding still reported WIRED. Nothing is
            # currently mislabelled by it, which is exactly why it would have gone unnoticed.
            stage = "CODED"
        elif not running:
            stage = "WIRED"
        elif not decision:
            stage = "RUNNING"
        elif not measured:
            stage = "DECISION_AFFECTING"
        elif not live_learning:
            stage = "MEASURED"
        else:
            stage = "LIVE_LEARNING"
        out[n.name] = {"coded": coded, "wired": wired, "running": running,
                       "decision_affecting": decision, "measured": measured,
                       "live_learning": live_learning,
                       "reads_outcome": reads_outcome, "feeds_itself": feeds_itself,
                       "stage": stage}
    return out


def generate_status(out_dir: Path = DESK / "reports") -> dict[str, Any]:
    status = check()
    status["stale"] = freshness()
    status["stages"] = stages()
    status["stage_counts"] = {s: sum(1 for v in status["stages"].values() if v["stage"] == s)
                              for s in ("MISSING", *STAGES)}
    reach = reachability()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "CAPABILITY_STATUS.json").write_text(json.dumps(status, indent=1), "utf-8")
    (out_dir / "LIVE_REACHABILITY.json").write_text(json.dumps(
        {"generated_utc": status["generated_utc"], "artifacts": reach}, indent=1), "utf-8")
    return status
