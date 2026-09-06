#!/usr/bin/env python3
"""THE COMPLETION AUDITOR -- every capability the principal's ceiling mandate specifies, and the
stage each one has actually reached, COMPUTED from this tree rather than claimed by anybody.

    "Do not rely on humans remembering this mandate."   -- the ceiling mandate, 2026-09-05

WHY THIS FILE IS THE FIRST THING BUILT FROM AN 84-PHASE MANDATE, and not the last. A mandate that
long cannot be held in a head, a commit message or a session. Without a registry, "is the desk
finished?" is answered by whoever is asked, from memory, and the answer drifts optimistic --
because every phase has a module that could plausibly be its owner, and a module existing is the
single most common false positive on this desk. The auditor turns the mandate from prose somebody
remembers into a number CI can fail on.

STAGES ARE DERIVED, NEVER DECLARED. A capability may not tell this file what stage it is at. Each
rung is a separate question asked of the repository:

    MISSING             no owner module on disk
    CODED               the module exists                     <- where most things stop, silently
    WIRED               something other than its own tests imports it
    SCHEDULED           a scheduler surface names it
    RUNNING             its artifact exists on this host
    DECISION_AFFECTING  the capability graph routes it into a decision
    MEASURED            MODULE_RENT carries a verdict for it
    PROVEN              forward/live evidence, not backtest, has priced its rent

The ladder is strict and monotone: a capability cannot be SCHEDULED without being WIRED, because a
cron line pointing at a module nobody imports runs code that changes nothing.

WHAT `MEASURING` MEANS, AND WHY IT IS NOT A FAILURE. Some capabilities are correct, running and
deciding, and simply have not yet accumulated the forward observations that would let their rent be
priced. That is reality being slow, not the desk being incomplete, and the mandate says so
explicitly. They read MEASURING with the missing evidence NAMED. What is forbidden is the other
thing: reporting such a capability as complete, or as zero.

THIS HOST SEES NO LIVE ARTIFACTS. The lake and the reports live on the VPS and the box. Run here,
every RUNNING/PROVEN test that depends on an artifact answers honestly in the negative, and the
report says so rather than pretending. The registry, the wiring and the schedule are all readable
from the tree and are graded fully wherever this runs.

    python scripts/check_absolute_ceiling.py [--json] [--gaps] [--phase P17]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT = ROOT / "desks" / "mt5" / "reports" / "ABSOLUTE_CEILING_STATUS.json"

STAGES = ("MISSING", "CODED", "WIRED", "SCHEDULED", "RUNNING", "DECISION_AFFECTING",
          "MEASURED", "PROVEN")

#: Every place on this tree that can make code run on a clock. Same list as
#: `scripts/check_producer_schedules.py` -- deliberately duplicated rather than imported, because
#: that fence grades the capability GRAPH and this one grades the MANDATE, and coupling them means
#: a change made for one silently re-grades the other.
SCHEDULER_SURFACES = (
    "ops/crontab.manifest",
    "desks/mt5/ops/box_tasks.manifest",
    "desks/mt5/research/research_supervisor.py",
    "desks/mt5/research/hourly_cycle.py",
    "desks/mt5/research/daily_cycle.py",
)


@dataclass(frozen=True)
class Capability:
    """One requirement from the mandate, and where its answer would have to live.

    `owner` EMPTY IS A LEGITIMATE AND IMPORTANT STATE. It means the mandate asks for something this
    desk has not built, and writing a speculative path here to make the row look populated would be
    the exact failure the mandate names: claiming a capability because a filename exists.
    """
    id: str
    requirement: str
    owner: str = ""
    artifact: str = ""
    rent_metric: str = ""
    depends_on: tuple[str, ...] = ()
    #: Set when a capability legitimately cannot reach PROVEN yet, naming what reality still owes.
    awaiting: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------- the registry
#
# ORDERED BY THE MANDATE'S OWN PHASE NUMBERS so a reader can hold the two side by side. The owner
# column is the desk's REAL module where one exists and empty where it does not; nothing here is
# aspirational, because an aspirational owner turns MISSING into CODED and hides the work.

REGISTRY: tuple[Capability, ...] = (
    # ---- Phase 0: one source of truth
    Capability("P0.1", "release identity matches across research, validation, forward, allocator, "
                       "gateway and live; no match = no new capital authority",
               "desks/mt5/data/release_identity.json", "desks/mt5/data/release_identity.json",
               "capital authority is refused under ambiguous lineage", tags=("P0", "identity")),
    Capability("P0.2", "20% nominal heat floor, flat -- no readiness/evidence mechanism may "
                       "reduce it; above it stays evidence-determined through 45%",
               "desks/mt5/research/heat_policy.py", "desks/mt5/reports/HEAT_POLICY.json",
               "floor_binding + missed-growth attribution when unsatisfiable",
               tags=("P0", "policy", "FIXED")),
    Capability("P0.3", "capability status regenerated from the current SHA over the full ladder",
               "libs/ops/capability_graph.py", "desks/mt5/reports/CAPABILITY_STATUS.json",
               "unbillable count", tags=("P0",)),

    # ---- Phase 1-3: close the loops
    Capability("P1", "every organ proves producer -> artifact -> consumer -> decision -> "
                     "telemetry -> counterfactual -> rent",
               "libs/ops/module_rent.py", "desks/mt5/data/module_rent.jsonl",
               "EARNS/COSTS/NOT_BINDING per module", tags=("P1",)),
    Capability("P2", "macro event -> structured information -> forecast -> portfolio delta -> "
                     "dE[logW] -> interrupt -> rebalance, closed",
               "desks/mt5/research/macro_desk.py", "desks/mt5/reports/MACRO_DESK.json",
               "measured portfolio gain attributable to the interrupt", tags=("P2", "macro")),
    Capability("P3", "one-minute heartbeat and event triggers re-evaluate Elog optimality; "
                     "rebalance only when dElog > execution cost + uncertainty", "",
               "", "turnover cost vs realised gain", tags=("P3",)),

    # ---- Phase 4-5: forecast marketplace
    Capability("P4", "universal forecast contract; models publish beliefs, own no positions",
               "desks/mt5/research/forecast_contract.py",
               "desks/mt5/reports/FORECAST_CONTRACT.json",
               "belief weight earned per model", tags=("P4", "forecast")),
    Capability("P5", "forecast calibration marketplace: every model scored forecast -> realized, "
                     "biased predictors recalibrated automatically",
               "desks/mt5/research/model_self_improvement.py",
               "desks/mt5/reports/MODEL_SELF_IMPROVEMENT.json",
               "Brier/MAE skill vs a named baseline, per predictor",
               tags=("P5", "forecast", "self_improvement")),

    # ---- Phase 6-10: the AI layer
    Capability("P6", "learned multi-horizon representation layer, challenger-only", "desks/mt5/research/ml_layer.py", "desks/mt5/reports/ML_LAYER.json",
               "OOS dElog of representation-derived heads", tags=("P6", "ml")),
    Capability("P7", "model zoo benchmarked on dElog after cost and complexity rent",
               "desks/mt5/research/model_zoo.py", "desks/mt5/reports/MODEL_ZOO.json",
               "dElog per model per compute hour", tags=("P7", "ml")),
    Capability("P8", "self-supervised and contrastive learning on unlabelled history", "desks/mt5/research/ml_layer.py", "desks/mt5/reports/ML_LAYER.json",
               "downstream OOS improvement", tags=("P8", "ml")),
    Capability("P9", "financial mixture of experts with an OOS-admitted gate", "desks/mt5/research/ml_layer.py", "desks/mt5/reports/ML_LAYER.json",
               "gate-weighted OOS skill", tags=("P9", "ml")),
    Capability("P10", "live dynamic market graph with state-dependent edges",
               "desks/mt5/research/world_causal_graph.py",
               "desks/mt5/reports/CROSS_ASSET_GRAPH.json",
               "dElog of graph-conditioned forecasts", tags=("P10", "graph")),

    # ---- Phase 11-16: information
    Capability("P11", "information-first discovery: search incremental mutual information, "
                      "reward dN_eff and dElog rather than more transforms of one price",
               "desks/mt5/research/edge_search.py", "desks/mt5/reports/EDGE_SEARCH.json",
               "dN_eff and dElog per search hour", tags=("P11", "discovery")),
    Capability("P12", "data genome and Data ROI with with/without ablations",
               "desks/mt5/research/data_prospector.py", "desks/mt5/reports/DATA_PROSPECTOR.json",
               "dElog / total data cost", tags=("P12", "data")),
    Capability("P13", "residual -> missing information loop, repeated to noise",
               "desks/mt5/research/factor_residual_engine.py",
               "desks/mt5/reports/RESIDUAL_ALPHA.json",
               "dElog of information added by residual clustering", tags=("P13", "data")),
    Capability("P14", "options intelligence: surface, skew, term structure, implied tails", "desks/mt5/research/market_intelligence.py",
               "desks/mt5/reports/MARKET_INTELLIGENCE.json", "dElog of options-derived features", tags=("P14", "data")),
    Capability("P15", "exchange futures information -- never MT5 tick volume as a substitute",
               "desks/mt5/research/fetch_futures_curves.py", "",
               "dElog of exchange-flow features", tags=("P15", "data")),
    Capability("P16", "physical commodity intelligence, point-in-time only", "desks/mt5/research/market_intelligence.py",
               "desks/mt5/reports/MARKET_INTELLIGENCE.json",
               "dElog of physical features", tags=("P16", "data")),

    # ---- Phase 17-21: the creative organs
    Capability("P17", "market ecology brain: latent participant pressure inferred, never claimed",
               "desks/mt5/research/market_intelligence.py",
               "desks/mt5/reports/MARKET_INTELLIGENCE.json", "OOS predictive value of ecology state", tags=("P17", "ceiling")),
    Capability("P18", "active learning / EVSI drives dataset, experiment and probe choice", "desks/mt5/research/experiment_design.py",
               "desks/mt5/reports/EXPERIMENT_DESIGN.json", "EVSI realised vs predicted", tags=("P18", "ceiling")),
    Capability("P19", "measurement-design brain: cheapest falsifying experiment",
               "desks/mt5/research/experiment_design.py",
               "desks/mt5/reports/EXPERIMENT_DESIGN.json", "compute-hours per survivor", tags=("P19", "ceiling")),
    Capability("P20", "decision regret engine attributing regret to its cause",
               "desks/mt5/research/action_counterfactuals.py",
               "desks/mt5/reports/ACTION_COUNTERFACTUALS.json",
               "regret in Elog by source", tags=("P20", "ceiling")),
    Capability("P21", "distribution-shift sentinel over latent state; never lowers the 20% floor",
               "desks/mt5/research/drift_monitor.py", "desks/mt5/reports/DRIFT.json",
               "loss avoided under shift", tags=("P21", "ceiling")),

    # ---- Phase 22-27: mechanism and market memory
    Capability("P22", "mechanism transfer engine -- transfer mechanism, never configuration",
               "desks/mt5/research/alpha_genome.py", "desks/mt5/reports/ALPHA_GENOME.json",
               "survivors per transfer hypothesis", tags=("P22",)),
    Capability("P23", "market-memory retrieval of nearest historical worlds, PIT only", "desks/mt5/research/market_intelligence.py",
               "desks/mt5/reports/MARKET_INTELLIGENCE.json",
               "dElog of retrieval-conditioned decisions", tags=("P23",)),
    Capability("P24", "'what changed' engine ranking standardized cross-asset surprise", "desks/mt5/research/market_intelligence.py",
               "desks/mt5/reports/MARKET_INTELLIGENCE.json",
               "hit rate of anomaly -> interpretation", tags=("P24",)),
    Capability("P25", "expectations engine: actual vs market-implied as the primary surprise",
               "desks/mt5/research/news_desk.py", "desks/mt5/reports/NEWS_DESK.json",
               "dElog of surprise-conditioned forecasts", tags=("P25", "macro")),
    Capability("P26", "event response surfaces across horizons: shock, discovery, drift, reversal",
               "desks/mt5/research/market_intelligence.py",
               "desks/mt5/reports/MARKET_INTELLIGENCE.json", "dElog by horizon", tags=("P26", "macro")),
    Capability("P27", "expression optimizer: best market to express one information event",
               "desks/mt5/research/execution_resolver.py", "",
               "post-cost alpha per unit risk by expression", tags=("P27",)),

    # ---- Phase 28-33: capacity, scale and lifecycle
    Capability("P28", "capacity engine binding mu(q) and Cost(q) into the optimizer",
               "desks/mt5/research/cost_surface.py", "desks/mt5/reports/COST_SURFACE.json",
               "dElog lost to capacity", tags=("P28", "capital")),
    Capability("P29", "capital-scale morphing: strategy universe as a function of q", "desks/mt5/research/experiment_design.py",
               "desks/mt5/reports/EXPERIMENT_DESIGN.json",
               "dElog by operating tier", tags=("P29", "capital")),
    Capability("P30", "small-capacity alpha desk scored at OUR capital", "desks/mt5/research/experiment_design.py",
               "desks/mt5/reports/EXPERIMENT_DESIGN.json",
               "dElog of sub-scale edges", tags=("P30",)),
    Capability("P31", "tail-alpha desk: E[R | book stress] > 0",
               "desks/mt5/research/tail_alpha_search.py", "desks/mt5/reports/TAIL_ALPHA.json",
               "extra normal growth its diversification permits", tags=("P31",)),
    Capability("P32", "alpha mortality and crowding: shrink before realised alpha dies",
               "desks/mt5/research/decay_monitor.py", "desks/mt5/reports/DECAY.json",
               "loss avoided by early hibernation", tags=("P32",)),
    Capability("P33", "complete evidence-triggered alpha lifecycle",
               "desks/mt5/research/promoter.py", "desks/mt5/reports/PROMOTION.json",
               "live retention per promotion", tags=("P33",)),

    # ---- Phase 34-39: execution and compute
    Capability("P34", "execution intelligence predicting cost, fill probability, adverse selection",
               "desks/mt5/research/execution_intelligence.py",
               "desks/mt5/reports/EXECUTION_INTELLIGENCE.json",
               "alpha captured / alpha available", tags=("P34", "execution")),
    Capability("P35", "execution RL as a challenger, only after the twin is calibrated",
               "", "", "dElog vs champion execution policy",
               depends_on=("P34",), tags=("P35", "execution")),
    Capability("P36", "alpha capture OS decomposing leakage",
               "desks/mt5/research/missed_growth.py", "desks/mt5/reports/MISSED_GROWTH.json",
               "leakage in Elog by cause", tags=("P36", "execution")),
    Capability("P37", "multi-venue abstraction: forecast -> intent -> order -> venue adapter",
               "desks/mt5/research/execution_resolver.py", "",
               "cost of a venue change to alpha intelligence", tags=("P37", "execution")),
    Capability("P38", "compute allocator scheduling by marginal compute value",
               "libs/ops/compute_ledger.py", "data/compute_ledger.jsonl",
               "dElog per CPU/GPU hour", tags=("P38", "allocator")),
    Capability("P39", "distributed experiment cache keyed on data/feature/model/code/seed",
               "desks/mt5/research/experiment_cache.py",
               "desks/mt5/reports/EXPERIMENT_CACHE.json",
               "cache hit rate, hours saved", tags=("P39", "compute")),

    # ---- Phase 40-46: scaling and model governance
    Capability("P40", "financial scaling-law lab: OOS = f(data, model size, compute)",
               "desks/mt5/research/experiment_cache.py",
               "desks/mt5/reports/EXPERIMENT_CACHE.json",
               "marginal value of data vs model vs compute", tags=("P40", "ml")),
    Capability("P41", "model-size efficient frontier; smallest model at equal rent",
               "desks/mt5/research/model_zoo.py", "desks/mt5/reports/MODEL_ZOO.json",
               "rent per unit inference cost", tags=("P41", "ml")),
    Capability("P42", "distillation: student independently retains the required dElog", "desks/mt5/research/ml_layer.py", "desks/mt5/reports/ML_LAYER.json",
               "student dElog vs teacher", tags=("P42", "ml")),
    Capability("P43", "guarded online learning: champion authoritative, challenger updates, "
                      "promotion on measured evidence, no silent live mutation",
               "desks/mt5/research/model_self_improvement.py",
               "desks/mt5/data/model_skill_track.jsonl",
               "out-of-sample skill gain at promotion", tags=("P43", "self_improvement")),
    Capability("P44", "population-based training selected on hostile OOS evaluation",
               "desks/mt5/research/alpha_evolution.py", "desks/mt5/reports/ALPHA_EVOLUTION.json",
               "survivors per mutation generation", tags=("P44", "ml")),
    Capability("P45", "generative stress worlds -- risk falsification only, never alpha proof",
               "libs/research/counterfactual_world.py",
               "desks/mt5/reports/COUNTERFACTUAL_WORLD.json",
               "risk discovered per synthetic world", tags=("P45", "risk")),
    Capability("P46", "model uncertainty ensemble widening the posterior on disagreement",
               "libs/self_improvement/ensemble_optimizer.py", "",
               "calibration improvement from disagreement", tags=("P46", "ml")),

    # ---- Phase 47-50: adversaries
    Capability("P47", "independent validator/killer agents; research does not grade itself",
               "libs/validation/__init__.py", "desks/mt5/reports/VALIDATION.json",
               "false discoveries caught per validation hour", tags=("P47", "adversary")),
    Capability("P48", "internal bug-bounty / fraud agent rewarded for finding silent defects",
               "desks/mt5/research/adversary.py", "desks/mt5/reports/ADVERSARY.json", "defects found before capital", tags=("P48", "adversary", "ceiling")),
    Capability("P49", "permanent poison canaries continuously rejected by validation",
               "desks/mt5/research/adversary.py", "desks/mt5/reports/ADVERSARY.json", "canary rejection rate (must stay 100%)", tags=("P49", "adversary")),
    Capability("P50", "model of the desk: digital twin of the research organisation itself",
               "desks/mt5/research/opportunity_gap.py",
               "desks/mt5/reports/OPPORTUNITY_GAP.json", "dElog of an organisational change", tags=("P50", "ceiling")),

    # ---- Phase 51-55: research governance
    Capability("P51", "research capital governor allocating across all action types by RROI",
               "desks/mt5/research/research_bandit.py", "desks/mt5/reports/RESEARCH_BANDIT.json",
               "RROI realised vs predicted", tags=("P51", "allocator")),
    Capability("P52", "research program competition on survivors per unit research cost",
               "desks/mt5/research/research_productivity.py",
               "desks/mt5/reports/RESEARCH_PRODUCTIVITY.json",
               "forward survivors per research cost", tags=("P52", "research")),
    Capability("P53", "AI scientist organisation with tracked reputation per agent", "desks/mt5/research/research_org.py",
               "desks/mt5/reports/RESEARCH_ORG.json",
               "net dElog per agent", tags=("P53", "research")),
    Capability("P54", "advocate / skeptic / replicator / validator roles kept separate", "desks/mt5/research/research_org.py",
               "desks/mt5/reports/RESEARCH_ORG.json", "proposals overturned by independent review", tags=("P54", "adversary")),
    Capability("P55", "permanent unknown-unknown budget that expands the ontology",
               "desks/mt5/frontier_intel/unknowns.py", "desks/mt5/reports/FRONTIER_GAPS.json",
               "ontology terms added that later pay rent", tags=("P55", "frontier")),

    # ---- Phase 56-64: the frontier miner
    Capability("P56", "institutional frontier miner: hourly scan -> extract -> gap -> ROI -> "
                      "build -> test -> measure, separate from alpha miners",
               "desks/mt5/frontier_intel/frontier_supervisor.py",
               "desks/mt5/reports/FRONTIER_INTELLIGENCE.json",
               "capabilities replicated that pay rent", tags=("P56", "frontier")),
    Capability("P57", "maximally permissive discovery, strict authority: any public claim may "
                      "inspire a hypothesis, none may bypass independent validation",
               "desks/mt5/frontier_intel/roi.py", "",
               "hypotheses per source vs survivors per source", tags=("P57", "frontier")),
    Capability("P58", "claim genealogy and anti-echo: ten reposts are one lineage",
               "desks/mt5/research/adversary.py", "desks/mt5/reports/ADVERSARY.json",
               "corroboration count corrected for lineage", tags=("P58", "frontier")),
    Capability("P59", "multilingual regional scouts with native-context queries",
               "desks/mt5/frontier_intel/registry.py", "",
               "survivors per region per scout hour", tags=("P59", "frontier")),
    Capability("P60", "frontier-of-frontiers: transferable methods from adjacent sciences",
               "desks/mt5/research/research_org.py",
               "desks/mt5/reports/RESEARCH_ORG.json", "cross-domain hypotheses that survive", tags=("P60", "frontier")),
    Capability("P61", "institutional gap graph firm -> process -> capability -> gap -> rent",
               "desks/mt5/frontier_intel/ontology.py", "desks/mt5/reports/FRONTIER_GAPS.json",
               "gaps closed that pay rent", tags=("P61", "frontier")),
    Capability("P62", "frontier autonomous implementer: gap -> branch -> build -> tests -> "
                      "canaries -> zero-authority challenger -> rent -> promote or graveyard",
               "desks/mt5/research/research_org.py",
               "desks/mt5/reports/RESEARCH_ORG.json", "capabilities autonomously landed that pay rent",
               depends_on=("P56", "P61"), tags=("P62", "frontier")),
    Capability("P63", "complexity rent: net dElog = gross - compute - latency - maintenance",
               "libs/ops/module_rent.py", "desks/mt5/data/module_rent.jsonl",
               "net dElog after complexity rent", tags=("P63",)),
    Capability("P64", "frontier source / firm / agent ROI tracked separately from truth",
               "desks/mt5/frontier_intel/roi.py", "desks/mt5/reports/FRONTIER_INTELLIGENCE.json",
               "idea yield vs truth rate per source", tags=("P64", "frontier")),

    # ---- Phase 65-69: arbitration and portfolio
    Capability("P65", "theory vs empirics arbitrator over P(mechanism) and P(empirical edge)",
               "desks/mt5/research/experiment_design.py",
               "desks/mt5/reports/EXPERIMENT_DESIGN.json", "survival rate by quadrant", tags=("P65", "ceiling")),
    Capability("P66", "opportunity-gap monitor decomposing G by cause",
               "desks/mt5/research/opportunity_gap.py",
               "desks/mt5/reports/OPPORTUNITY_GAP.json",
               "largest G component, and its closure", tags=("P66", "ceiling")),
    Capability("P67", "missing-sleeve generator targeting uncovered states",
               "desks/mt5/research/portfolio_gap.py", "desks/mt5/reports/PORTFOLIO_GAP.json",
               "dElog of newly covered states", tags=("P67",)),
    Capability("P68", "effective breadth as a first-class KPI over covariance, factor and tail",
               "desks/mt5/research/alpha_breadth.py", "desks/mt5/reports/EFFECTIVE_BREADTH.json",
               "dN_eff per research unit", tags=("P68",)),
    Capability("P69", "portfolio alpha, not strategy alpha: score by dElog of the BOOK",
               "desks/mt5/research/pf_allocator.py", "desks/mt5/reports/ALLOCATOR_STACK.json",
               "dElog_book per candidate", tags=("P69", "allocator")),

    # ---- Phase 70-77: worlds, counterfactuals, reproducibility
    Capability("P70", "full world simulator jointly carrying edge, state, cost and broker risk",
               "libs/research/counterfactual_world.py",
               "desks/mt5/reports/COUNTERFACTUAL_WORLD.json",
               "E_{Theta,S,E,C}[log W]", tags=("P70", "risk")),
    Capability("P71", "structural counterfactuals: World|event vs World|not-event",
               "desks/mt5/research/counterfactual_replay.py", "",
               "event causal contribution separated from drift", tags=("P71", "macro")),
    Capability("P72", "full counterfactual decision ledger over every alternative action",
               "desks/mt5/research/action_counterfactuals.py",
               "desks/mt5/reports/ACTION_COUNTERFACTUALS.json",
               "regret by alternative", tags=("P72",)),
    Capability("P73", "exit / re-entry / pyramid researched as separate alpha domains",
               "desks/mt5/research/exit_study.py", "desks/mt5/reports/EXIT_STUDY.json",
               "incremental Elog of the exit rule", tags=("P73",)),
    Capability("P74", "research reproducibility: every experiment hashed and never overwritten",
               "desks/mt5/research/registry.py", "desks/mt5/reports/EXPERIMENT_LEDGER.json",
               "reproducible fraction of experiments", tags=("P74", "research")),
    Capability("P75", "graveyard meta-learning: P(pass | hypothesis DNA) from failures",
               "libs/research/graveyard_model.py", "docs/graveyard.md",
               "precision gain from learned taste", tags=("P75", "research")),
    Capability("P76", "alpha genome complete; multiplicity operates on mechanism ancestry",
               "desks/mt5/research/alpha_genome.py", "desks/mt5/reports/ALPHA_GENOME.json",
               "family-corrected discovery rate", tags=("P76",)),
    Capability("P77", "research throughput KPIs including cost per survivor",
               "desks/mt5/research/research_productivity.py",
               "desks/mt5/reports/RESEARCH_PRODUCTIVITY.json",
               "survivors per compute and engineering hour", tags=("P77", "research")),

    # ---- Phase 78-84: the closed flywheel
    Capability("P78", "daily autonomous retrospective feeding the governor",
               "desks/mt5/research/daily_cycle.py", "desks/mt5/reports/DAILY.json",
               "actions taken from the retrospective", tags=("P78",)),
    Capability("P79", "permanent challenge league on equal evidence, dates, costs, heat, worlds",
               "desks/mt5/research/model_zoo.py", "desks/mt5/reports/CHALLENGE_LEAGUE.json",
               "champion changes justified by measured gain", tags=("P79", "ceiling")),
    Capability("P80", "organisation KPIs: alpha/data/compute yield, live retention, capture",
               "desks/mt5/research/research_productivity.py",
               "desks/mt5/reports/RESEARCH_PRODUCTIVITY.json",
               "the KPI set itself", tags=("P80", "research")),
    Capability("P81", "quant intelligence score, reporting-only, never a capital input",
               "desks/mt5/research/opportunity_gap.py",
               "desks/mt5/reports/OPPORTUNITY_GAP.json",
               "reporting only -- must never route to capital", tags=("P81",)),
    Capability("P82", "information provenance graph from position back to raw observation",
               "libs/ops/input_provenance.py", "docs/research/data_provenance.json",
               "forecasts identified per broken feed", tags=("P82", "data")),
    Capability("P83", "P&L attribution back through forecast, model, feature, dataset",
               "desks/mt5/research/allocator_attribution.py",
               "desks/mt5/reports/ALLOCATOR_ATTRIBUTION.json",
               "wealth earned per dataset", tags=("P83", "data")),
    Capability("P84", "the complete discovery flywheel, closed continuously",
               "desks/mt5/research/hourly_cycle.py", "desks/mt5/reports/HOURLY_CYCLE.json",
               "cycle throughput and its dElog",
               depends_on=("P11", "P13", "P51"), tags=("P84",)),

    # ---- the seven allocators
    Capability("A1", "frontier allocator: which observable capability deserves replication",
               "desks/mt5/frontier_intel/queue.py", "desks/mt5/reports/FRONTIER_INTELLIGENCE.json",
               "dElog per replication effort", tags=("allocator",)),
    Capability("A2", "information allocator: which data deserves acquisition",
               "desks/mt5/research/data_prospector.py", "desks/mt5/reports/DATA_PROSPECTOR.json",
               "dElog per data cost", tags=("allocator",)),
    Capability("A3", "research allocator: which question deserves investigation",
               "desks/mt5/research/research_bandit.py", "desks/mt5/reports/RESEARCH_BANDIT.json",
               "survivors per research unit", tags=("allocator",)),
    Capability("A4", "compute allocator: which job deserves CPU/GPU",
               "libs/ops/compute_ledger.py", "data/compute_ledger.jsonl",
               "dElog per compute hour", tags=("allocator",)),
    Capability("A5", "forecast allocator: which model deserves belief weight",
               "desks/mt5/research/model_self_improvement.py",
               "desks/mt5/reports/MODEL_SELF_IMPROVEMENT.json",
               "skill-weighted belief", tags=("allocator",)),
    Capability("A6", "capital allocator: which opportunity deserves money",
               "desks/mt5/research/pf_allocator.py", "desks/mt5/reports/ALLOCATOR_STACK.json",
               "dElog per unit capital", tags=("allocator",)),
    Capability("A7", "execution allocator: how an intended position is implemented",
               "desks/mt5/research/execution_resolver.py",
               "desks/mt5/reports/EXECUTION_INTELLIGENCE.json",
               "alpha captured / alpha available", tags=("allocator",)),
)


# ---------------------------------------------------------------- stage derivation


def _read(rel: str) -> str:
    p = ROOT / rel
    try:
        return p.read_text("utf-8", errors="ignore") if p.is_file() else ""
    except OSError:
        return ""


_SURFACE_TEXT: str | None = None


def _surfaces() -> str:
    global _SURFACE_TEXT
    if _SURFACE_TEXT is None:
        _SURFACE_TEXT = "\n".join(_read(rel) for rel in SCHEDULER_SURFACES)
    return _SURFACE_TEXT


_IMPORTS: dict[str, int] | None = None


def _import_counts() -> dict[str, int]:
    """How many PRODUCTION files REACH each module. Tests deliberately excluded.

    A module reached only by its own tests is CODED, not WIRED, and conflating the two is how a
    package of twenty carefully-tested modules can sit in a repository changing nothing -- which
    is measurably what happened to libs/self_improvement.

    REACHED, NOT IMPORTED, and the distinction was a false negative worth 34 rows. The first
    version counted `import` statements only, and this desk runs its heavy producers as
    SUBPROCESSES -- `hourly_cycle._producer("world_causal_graph", "research/world_causal_graph.py")`
    launches a module it never imports. Grading those as unwired would have had the auditor
    reporting a third of the desk as dead code, and an auditor that cries wolf is one nobody
    reads, which is the failure mode it exists to prevent in everything else.
    """
    global _IMPORTS
    if _IMPORTS is not None:
        return _IMPORTS
    counts: dict[str, int] = {}
    for p in ROOT.rglob("*.py"):
        rel = p.relative_to(ROOT).as_posix()
        if "/tests/" in f"/{rel}" or rel.startswith("tests/") or "__pycache__" in rel:
            continue
        try:
            src = p.read_text("utf-8", errors="ignore")
        except OSError:
            continue
        for mod in re.findall(r"(?:from|import)\s+([a-zA-Z_][\w.]*)", src):
            leaf = mod.split(".")[-1]
            counts[leaf] = counts.get(leaf, 0) + 1
            counts[mod] = counts.get(mod, 0) + 1
        # Subprocess and CLI references: "research/world_causal_graph.py", 'scripts/x.py'.
        for ref in re.findall(r"['\"][\w/]*?([a-zA-Z_][\w]*)\.py['\"]", src):
            counts[ref] = counts.get(ref, 0) + 1
    _IMPORTS = counts
    return counts


def _graph_stage(module_stem: str) -> str:
    """What the capability graph says about the node owning this module, if any."""
    try:
        from libs.ops.capability_graph import NODES, stages
    except Exception:
        return ""
    st = stages()
    for n in NODES:
        mod = str(getattr(n, "module", "") or "")
        if module_stem and (module_stem in mod or mod.endswith(f"{module_stem}.py")):
            return str((st.get(n.name) or {}).get("stage", "") or "")
    return ""


def _rent_verdict(module_stem: str) -> str:
    try:
        from libs.ops import module_rent as mr
    except Exception:
        return ""
    for m in getattr(mr, "MODULES", ()):
        if module_stem and module_stem in str(getattr(m, "name", "")):
            return "MEASURED"
    return ""


def stage_of(cap: Capability) -> tuple[str, list[str]]:
    """The rung this capability has actually reached, and every rung it failed to clear.

    STRICT AND MONOTONE. Each test is only asked once its predecessor passed, because the rungs
    are not independent claims: a cron line naming a module nobody imports schedules code that
    changes nothing, and reporting that as SCHEDULED would be worse than reporting CODED.
    """
    gaps: list[str] = []
    if not cap.owner:
        return "MISSING", ["no owner module exists on this tree"]
    owner = ROOT / cap.owner
    if not owner.exists():
        return "MISSING", [f"owner {cap.owner} does not exist"]

    stem = Path(cap.owner).stem
    if owner.suffix != ".py":
        # A data artifact (release_identity.json, module_rent.jsonl) is its own producer's output;
        # its rungs are existence and being read, not import and schedule.
        return ("RUNNING" if owner.stat().st_size > 2 else "CODED"), []

    imports = _import_counts().get(stem, 0)
    if imports < 2:                      # its own definition counts once
        gaps.append(f"no production module imports {stem} -- CODED but unwired")
        return "CODED", gaps

    if stem not in _surfaces() and f"{stem}.py" not in _surfaces():
        gaps.append(f"no scheduler surface names {stem} -- it is wired but nothing runs it")
        return "WIRED", gaps

    art = (ROOT / cap.artifact) if cap.artifact else None
    if art is None or not art.exists():
        gaps.append(f"artifact {cap.artifact or '(undeclared)'} absent on this host -- "
                    f"scheduled, but no evidence it has produced anything here")
        return "SCHEDULED", gaps

    gstage = _graph_stage(stem)
    if gstage not in ("DECISION_AFFECTING", "MEASURED", "LIVE_LEARNING"):
        gaps.append(f"capability graph reports {gstage or 'no node'} -- running, but no proven "
                    f"route from this artifact into a decision")
        return "RUNNING", gaps

    if _rent_verdict(stem) != "MEASURED":
        gaps.append(f"no MODULE_RENT line prices {stem} -- decision-affecting but unpriced")
        return "DECISION_AFFECTING", gaps

    if cap.awaiting:
        gaps.append(f"MEASURING: {cap.awaiting}")
        return "MEASURED", gaps
    return "PROVEN", gaps


def audit() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for cap in REGISTRY:
        stage, gaps = stage_of(cap)
        blocked = [d for d in cap.depends_on
                   if STAGES.index(stage_of(next(c for c in REGISTRY if c.id == d))[0])
                   < STAGES.index("SCHEDULED")]
        rows.append({
            "capability_id": cap.id,
            "requirement": cap.requirement,
            "owner_module": cap.owner or None,
            "artifact": cap.artifact or None,
            "rent_metric": cap.rent_metric,
            "current_stage": stage,
            "open_gap": gaps[0] if gaps else "",
            "all_gaps": gaps,
            "blocking_dependencies": blocked,
            "tags": list(cap.tags),
        })
    counts = {s: sum(1 for r in rows if r["current_stage"] == s) for s in STAGES}
    problems: list[str] = []

    # THE MANDATE'S OWN CI CONDITIONS, each one checked rather than described.
    floor = _read("desks/mt5/research/heat_policy.py")
    if "floor = target if mandate else 0.0" not in floor:
        problems.append(
            "the 20% nominal heat floor is no longer flat in heat_policy.resolve -- the "
            "principal's ONE fixed policy. Whatever mechanism now scales it must be removed.")
    if re.search(r"floor\s*=\s*[^\n]*readiness", floor):
        problems.append("readiness appears in the floor expression -- it may gate composition "
                        "and authority ABOVE the floor, never the floor itself")
    for r in rows:
        if r["current_stage"] == "MEASURED" and not r["rent_metric"]:
            problems.append(f"{r['capability_id']} reads MEASURED with no rent metric declared")

    return {
        "at": datetime.now(UTC).isoformat(),
        "total_capabilities": len(rows),
        **{s.lower(): counts[s] for s in STAGES},
        "blocked": sum(1 for r in rows if r["blocking_dependencies"]),
        "capabilities": rows,
        "problems": problems,
        "status": "BREACH" if problems else ("INCOMPLETE" if counts["MISSING"] or
                                             counts["CODED"] else "COMPLETE"),
        "host_note": ("artifact-dependent rungs (RUNNING and above) can only be graded where the "
                      "artifacts live. On a host without the lake every such rung answers in the "
                      "negative, which is honest rather than green."),
        "law": ("stages are DERIVED from this tree, never declared. A capability is not complete "
                "at CODED or WIRED; PROVEN requires forward evidence and a priced rent."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--gaps", action="store_true", help="only capabilities with an open gap")
    ap.add_argument("--phase", default="", help="one capability id, e.g. P17")
    args = ap.parse_args(argv)
    doc = audit()
    try:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    except OSError:
        pass
    if args.json:
        print(json.dumps(doc, indent=1, default=str))
        return 2 if doc["problems"] else 0
    print(f"ABSOLUTE CEILING: {doc['total_capabilities']} capabilities -- {doc['status']}")
    print("  " + "  ".join(f"{s}={doc[s.lower()]}" for s in STAGES))
    rows = doc["capabilities"]
    if args.phase:
        rows = [r for r in rows if r["capability_id"] == args.phase]
    elif args.gaps:
        rows = [r for r in rows if r["open_gap"]]
    for r in rows:
        print(f"  {r['current_stage']:18s} {r['capability_id']:5s} {r['requirement'][:78]}")
        if r["open_gap"]:
            print(f"                     GAP: {r['open_gap']}")
        if r["blocking_dependencies"]:
            print(f"                     BLOCKED BY: {r['blocking_dependencies']}")
    for p in doc["problems"]:
        print(f"  BREACH {p}")
    return 2 if doc["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
