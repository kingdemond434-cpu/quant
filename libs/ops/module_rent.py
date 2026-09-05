"""MODULE RENT -- Elog_with - Elog_without for EVERY component, and a RETIRE list a person reads.

    "Module Rent = Elog_with - Elog_without for every component; if persistently <= 0, retire it.
     This includes AI. No sacred modules."                          -- the principal, 2026-09-05

WHY A SECOND LEDGER WHEN MISSED_GROWTH EXISTS. `research/missed_growth.py` bills the RAILS -- every
veto, cap, shrinkage and gate registered in `libs.portfolio.rails` -- and nothing else. Measured on
this tree 2026-09-05: no miner, proposer arm, state dimension, execution algorithm, allocator
component, data source or AI organ carried an Elog_with / Elog_without line anywhere, and nothing
on the desk retires at <= 0. A component nothing bills is a component nothing can retire, which is
how a desk accumulates organs that compute and cost and are never asked what they are for.

THE REGISTRY declares, per module, WHICH ledger measures it and BY WHAT RULE. Nothing here is
recomputed from raw evidence when the desk already keeps the number:

    rail                  MISSED_GROWTH.json, reused verbatim (the rail's own daily ledger line)
    proposer              RESEARCH_PNL.json per bandit arm: the growth its certificates carry in
                          the funded book, spend in DECLARED cost units beside it
    state_dimension       STATE_ADMISSION.json (out-of-sample gain of conditioning on the
                          dimension) and the conditioning ledger (heat the modifier moved x what
                          that heat then earned: with vs without the modifier, realised daily)
    execution_algo        execution_algo_outcomes.jsonl through `execution_registry.scoreboard`:
                          each algorithm's realised cost against the market baseline's, per fill
    allocator_component   pf_allocation.json: the dynamic weights against the best baseline the
                          proof scored, the posterior book against the funded one, the Kelly
                          surface's tail bound against the unbounded book
    data_source           the dimension a source feeds (admission + conditioning ledger) or the
                          RESEARCH_PNL source row its hypotheses land on
    ai_organ              the AI capital modifier's conditioning ledger, and the LLM-driven miners'
                          RESEARCH_PNL rows. "This includes AI."

UNITS ARE NAMED, NEVER ASSUMED. `rent_logw_per_day` is filled only where the ledger prices the
module in log-wealth per day; where the ledger's unit is something else (an out-of-sample MSE
gain, a fraction of price per fill) `rent` and `unit` carry the number and `rent_logw_per_day`
is None. A verdict is still owed in every unit -- the principal's question is the sign.

VERDICTS
    EARNS        rent > 0, with n >= MIN_N and (where the ledger gives daily samples) t > T_LINE
    COSTS        rent < 0 on the same terms
    NOT_BINDING  the module did not fire, had no trials, or IS the baseline it would be measured
                 against (the market algorithm)
    UNMEASURED   the ledger is absent on this host, thin, or the sign is not distinguishable from
                 zero. Said, with the path and the count -- never folded into a pass (L1.28a)

THE RETIRE LIST NAMES; IT DOES NOT RETIRE. A module is listed when it has read COSTS with
n >= MIN_N in K_WINDOWS consecutive weekly windows of its own history (`data/module_rent.jsonl`,
one row per module per day, appended once). Retirement is a person's decision or the capability
graph's check; this report is the evidence, and the evidence carries the ledger it came from so
the decision can be audited against the number rather than the verdict.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from libs.portfolio.rails import RAILS
from libs.research.bandit import ARMS, SOURCE_ARM

ROOT = Path(__file__).resolve().parents[2]

KINDS: tuple[str, ...] = ("rail", "proposer", "state_dimension", "execution_algo",
                          "allocator_component", "data_source", "ai_organ", "organ")
EARNS, COSTS, NOT_BINDING, UNMEASURED = "EARNS", "COSTS", "NOT_BINDING", "UNMEASURED"

#: Samples (days, trials, fills, test trades) before a verdict is a verdict.
MIN_N = 10
#: |t| a daily ledger must clear before its mean is called a sign rather than noise.
T_LINE = 2.0
#: Consecutive weekly windows of COSTS (each with n >= MIN_N) before a module is NAMED for
#: retirement.
K_WINDOWS = 3
#: A conditioning multiplier below this has no finite "without" heat under the linearisation
#: (heat proportional to the posterior mean); the row is priced at the floor rather than skipped.
MULT_FLOOR = 0.05

# Every ledger this reads, repo-relative, so `measure(root)` can be pointed at a fixture tree.
MISSED_GROWTH = "desks/mt5/reports/MISSED_GROWTH.json"
RESEARCH_PNL = "desks/mt5/reports/RESEARCH_PNL.json"
STATE_ADMISSION = "desks/mt5/reports/STATE_ADMISSION.json"
CAPITAL_MODIFIERS = "desks/mt5/reports/CAPITAL_MODIFIERS.json"
ALLOCATION = "desks/mt5/reports/pf_allocation.json"
MODIFIER_LEDGER = "desks/mt5/data/capital_modifier_ledger.jsonl"
ALGO_OUTCOMES = "desks/mt5/data/execution_algo_outcomes.jsonl"
SHADOW_DIR = "desks/mt5/reports/shadow/"          # trailing slash: the graph names dirs so
LIVE_LEDGER = "desks/mt5/data/live_ledger.jsonl"
HISTORY = "desks/mt5/data/module_rent.jsonl"
REPORT = "desks/mt5/reports/MODULE_RENT.json"
#: THE EXECUTION-LEARNING LINE (2026-09-05). The fill corpus and the two models built on it.
ALPHA_CAPTURE = "desks/mt5/reports/ALPHA_CAPTURE.json"
CAPTURE_HISTORY = "desks/mt5/data/alpha_capture_history.jsonl"
EXECUTION_TWIN = "desks/mt5/reports/EXECUTION_TWIN.json"

#: The execution algorithms the registry competes (mt5desk.execution_registry). `market` is the
#: baseline every other one is measured against, so its own rent is zero by definition.
EXECUTION_ALGOS: tuple[str, ...] = ("market", "twap", "iceberg", "sniper", "pullback")
BASELINE_ALGO = "market"
#: State dimensions the admission gauntlet judges on this desk, and the data source each one is
#: read from. A dimension the report judges that is not listed here is discovered at measure time.
DIMENSION_SOURCE: dict[str, str] = {"session": "broker_clock", "event": "event_calendar",
                                    "weekday": "weekday_calendar"}
#: LLM-driven organs, by the RESEARCH_PNL source prefixes their hypotheses carry.
AI_ORGANS: dict[str, tuple[str, ...]] = {
    "deepening_worker": ("deepening", "mutation"),
    "deep_forest_miner": ("deep_forest",),
    "repo_miner": ("repo_miner",),
    "world_crawler": ("world_crawler", "crawler"),
}
#: Hypothesis sources that ARE data sources (a prospector row names data the desk lacks).
DATA_HYPOTHESIS_SOURCES: tuple[str, ...] = ("data_prospector", "world")


@dataclass(frozen=True)
class Module:
    """One billable component: what it is, where its ledger is, and the with/without rule."""

    name: str
    kind: str
    ledger: str
    rule: str
    measure: str
    where: str = ""
    #: The row this module is looked up under in its ledger (rail name, arm, algo, dimension...).
    key: str = ""
    #: Prefixes of RESEARCH_PNL source names that roll up to this module.
    sources: tuple[str, ...] = ()


def _rail_modules() -> tuple[Module, ...]:
    return tuple(Module(r.name, "rail", MISSED_GROWTH,
                        "E[log W without the rail] - E[log W with it], billed daily by "
                        "missed_growth; reused verbatim, never recomputed",
                        "measure_rail", r.where, key=r.name) for r in RAILS)


def _proposer_modules() -> tuple[Module, ...]:
    return tuple(Module(a, "proposer", RESEARCH_PNL,
                        "expected log-wealth per day the arm's certificates carry in the funded "
                        "book (the allocator's own claim), spend in declared cost units beside; "
                        "no exchange rate from cost units to log-wealth exists, so the verdict is "
                        "on gross survivor growth and the spend is reported, not netted",
                        "measure_proposer", "libs.research.bandit.ARMS -> research_pnl arms",
                        key=a) for a in ARMS)


# ------------------------------------------------------------------- the organs, billed by use
#
# THE RULE, AND IT IS THE ONE THAT MAKES THE REST OF THIS FILE FINITE. A module's rent is measured
# WHERE IT CHANGES A DECISION. A rail changes the size of a trade, so `missed_growth` prices it; a
# proposer changes what is in the book, so `research_pnl` prices it. But 27 decision-affecting
# organs on this desk -- the gauntlets, the forward clock, the promoter, the execution twin, the
# tape recorder, the counterfactual ledgers, the macro layer -- produce a REPORT, and a report has
# no price of its own. Billing them by their own output would price effort, not value.
#
# So an organ is billed through its CONSUMER, and the chain is read off the capability graph
# rather than restated here: organ -> artifact -> the node that reads the artifact -> that node's
# own rent. Three outcomes, and the middle one is the reason this is worth building:
#
#   NOTHING READS IT   NOT_BINDING, with the artifact named. An organ whose output changes no
#                      decision has zero rent BY CONSTRUCTION, and that is the retire signal the
#                      principal asked for -- "if persistently <= 0, retire it". This is the only
#                      verdict here that can be reached without any live evidence at all, which
#                      is exactly right: it is a wiring fact, not a market fact.
#   READ, PRICED       the consumer carries its own rent line, so the organ inherits the verdict
#                      and the number, with the consumer named. No new arithmetic: two modules in
#                      one chain must never produce two different answers about the same value.
#   READ, UNPRICED     UNMEASURED, naming the consumer AND the ledger that would price it. Never
#                      folded into a pass (L1.28a): "something reads it" is not "it earns".
#
# WHY THE GRAPH RATHER THAN A TABLE HERE. The reader/writer relation already exists, is already
# fenced (`check_read_without_writer`, `check_reachability`), and is already how the desk decides
# whether a producer reaches a decision. A second hand-maintained copy of it in this file would
# drift the moment an organ gained a consumer, and the drift would show up as an organ billed for
# work nobody uses -- the precise failure this whole ledger exists to catch.

#: Organs whose rent is inherited from a consumer, and the artifact the chain runs through. The
#: artifact is named here (rather than taken as "the node's first write") because an organ often
#: writes several and only one of them is the thing a decision is made from.
ORGAN_OUTPUT: dict[str, str] = {
    # -- admission: what reaches the book at all
    "external_gauntlet": "desks/mt5/reports/UNIVERSAL_SURVIVORS.json",
    "universal_gate": "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
    "scalp_gauntlet": "desks/mt5/reports/SCALP_GAUNTLET.json",
    "recertify_canon": "desks/mt5/reports/recertification_audit.json",
    "shadow_forward": "desks/mt5/reports/shadow/",
    "promoter": "desks/mt5/data/sleeves.json",
    "miner_candidate_compiler": "desks/mt5/data/hypotheses/miner_candidates.json",
    # -- execution: what a filled order costs
    "markout": "desks/mt5/reports/markout.json",
    "fill_surface": "desks/mt5/reports/FILL_SURFACE.json",
    "execution_intelligence": "desks/mt5/reports/NETTING.json",
    "execution_twin": "desks/mt5/reports/EXECUTION_TWIN.json",
    "counterfactual_markout": "desks/mt5/reports/FILTER_VALUE.json",
    "counterfactual_replay": "desks/mt5/reports/COUNTERFACTUAL_WORLD.json",
    "action_counterfactuals": "desks/mt5/reports/ACTION_COUNTERFACTUALS.json",
    # -- the tape and the features built on it
    "tick_recorder": "desks/mt5/reports/TAPE_RECORDER.json",
    "tick_integrity": "desks/mt5/reports/TICK_INTEGRITY.json",
    "tape_features": "desks/mt5/data/tape/ticks/",
    "state_vector_build": "desks/mt5/data/state_vector.json",
    # -- learning about the desk itself
    "alpha_genome": "desks/mt5/reports/ALPHA_GENOME.json",
    "feature_roi": "desks/mt5/reports/FEATURE_ROI.json",
    "drift_monitor": "desks/mt5/reports/DRIFT.json",
    "allocator_attribution": "desks/mt5/reports/GROWTH_ATTRIBUTION_WEEKLY.json",
    "research_pnl": "desks/mt5/reports/RESEARCH_PNL.json",
    "macro_intel": "desks/mt5/data/macro/allocator_interrupt.json",
}

#: Organs that ARE the money path or the release gate rather than an input to it. Their rent is
#: not separable and pretending otherwise would be theatre: without `gateway` there are no orders
#: to price, without `release` and `immutable_evaluator` there is no authority to place one, so
#: "E[logW] without it" is not a smaller number -- it is a desk that does not trade. Declared here
#: so they are BILLED AND ANSWERED rather than silently unbillable, which is the state this ledger
#: exists to end. They are not retire candidates and the verdict says why.
INFRASTRUCTURE: dict[str, str] = {
    "gateway": "the order path itself: without it no intent becomes a fill, so there is no "
               "counterfactual book to compare against -- only no book",
    "release": "the release identity that authorises a live order; without it the deadman "
               "refuses to arm and the desk is flat by construction",
    "immutable_evaluator": "the signature that makes a judge's verdict admissible; without it "
                           "no certificate carries authority, so nothing reaches capital to bill",
}


MODULES: tuple[Module, ...] = (
    *_rail_modules(),
    *_proposer_modules(),
    Module("state_posterior", "state_dimension", MODIFIER_LEDGER,
           "heat the state modifier moved x what that heat then earned, realised per day: "
           "sum_s h_s (1 - 1/mult_s) r_s, i.e. E[log W with the modifier] - E[log W without it] "
           "under heat proportional to the posterior mean",
           "measure_conditioning", "libs/portfolio/robust_elog._posterior_mu (state level)"),
    *(Module(f"state_dimension:{d}", "state_dimension", STATE_ADMISSION,
             "walk-forward gain from conditioning on the dimension against not conditioning "
             "(unit: out-of-sample MSE gain, t deflated for the dimensions tried)",
             "measure_admission", "libs/regime/state_admission", key=d)
      for d in DIMENSION_SOURCE),
    *(Module(f"execution_algo:{a}", "execution_algo", ALGO_OUTCOMES,
             "market baseline's mean realised cost minus the algorithm's, per filled plan, as a "
             "fraction of price against the reference quote (execution_registry.scoreboard)",
             "measure_execution_algo", "mt5desk.execution_registry.scoreboard", key=a)
      for a in EXECUTION_ALGOS),
    Module("pf_allocator:dynamic_weights", "allocator_component", ALLOCATION,
           "proof scores: mean log growth per day of the dynamic book minus the best baseline "
           "book at the same total heat on the same sampled worlds",
           "measure_dynamic_weights", "libs/portfolio/allocator_proof.contest"),
    Module("pf_allocator:posterior_growth", "allocator_component", ALLOCATION,
           "posterior multi-period book minus the funded book on identical sampled paths, "
           "bootstrap CI (posterior_growth.compare)",
           "measure_posterior_growth", "libs/portfolio/posterior_growth"),
    Module("pf_allocator:kelly_surface", "allocator_component", ALLOCATION,
           "mean growth at the tail-bounded fraction minus at the book's own fraction, when the "
           "tail bound binds (f_tail < 1)", "measure_kelly_surface",
           "libs/portfolio/kelly_surface.surface"),
    Module("pf_allocator:marginal_admission", "allocator_component", ALLOCATION,
           "dE[log W] of the candidates the criterion ADMITTED, each re-solved into the held book "
           "at the same total heat on the same sampled worlds: E[logW | book + i] - E[logW | book]"
           " summed over the admitted set (pf_allocator.marginal_admission)",
           "measure_marginal_admission", "desks/mt5/research/pf_allocator.marginal_admission"),
    Module("pf_allocator:regime_conditioning", "allocator_component", ALLOCATION,
           "needs the book scored on unconditioned worlds beside the conditioned ones; the "
           "artifact carries regime.conditioned but no with/without score",
           "measure_regime_conditioning", "libs/portfolio/robust_elog regime tilt"),
    *(Module(f"data_source:{src}", "data_source", STATE_ADMISSION,
             "the dimension this source feeds: admission gain (with vs without conditioning on "
             "it, out of sample) and its share of the conditioning ledger",
             "measure_admission", f"state dimension {d}", key=d)
      for d, src in DIMENSION_SOURCE.items()),
    *(Module(f"data_source:{src}", "data_source", RESEARCH_PNL,
             "expected log-wealth per day the source's certificates carry in the funded book, "
             "trials beside; <= 0 over the window with trials is dead information",
             "measure_research_source", "research_pnl sources", key=src, sources=(src,))
      for src in DATA_HYPOTHESIS_SOURCES),
    # THE BREADTH LANE'S RENT LINES (2026-09-05). Three producers whose entire output is research
    # instructions, so the only honest ledger is the growth their instructions eventually carry in
    # the funded book -- RESEARCH_PNL, by the source name each one stamps on the tasks it queues
    # (`libs.research.bandit.SOURCE_ARM` maps the same three names to arms). Like the vol archive
    # above, these read UNMEASURED until a queued task becomes a certificate and that certificate
    # carries heat: a research organ cannot be billed for growth before its first hypothesis has
    # been through the gauntlet, and an UNMEASURED row here is the rule working rather than a gap.
    # The measurement is FORWARD by construction, and it arrives without anyone remembering to add
    # a line later.
    Module("alpha_breadth", "proposer", RESEARCH_PNL,
           "expected log-wealth per day carried in the funded book by certificates whose "
           "hypothesis came from an EMPTY-CLUSTER task -- the first sleeve of a phenomenon the "
           "book did not occupy. 'Without' is genuinely nothing: nothing else on the desk names "
           "an unoccupied cluster, so a certificate traced to this source would not exist",
           "measure_research_source", "desks/mt5/research/alpha_breadth.py",
           key="alpha_breadth", sources=("alpha_breadth",)),
    Module("drawdown_alpha", "proposer", RESEARCH_PNL,
           "expected log-wealth per day carried by certificates whose hypothesis came from a "
           "drawdown-state task. THE RENT IS UNDERSTATED BY THIS LEDGER AND THAT IS DELIBERATE: "
           "a tail-positive sleeve's real contribution is the leverage the whole book can then "
           "carry, which shows up as everyone else's growth, not its own. Billing it on its own "
           "growth is the conservative reading and cannot flatter it",
           "measure_research_source", "desks/mt5/research/drawdown_alpha.py",
           key="drawdown_alpha", sources=("drawdown_alpha",)),
    Module("survivor_neighbourhood", "proposer", RESEARCH_PNL,
           "expected log-wealth per day carried by certificates whose hypothesis came from a "
           "survivor-state task -- a state where an existing edge is stronger, or one where it "
           "pays nothing and the heat should go elsewhere",
           "measure_research_source", "desks/mt5/research/survivor_neighbourhood.py",
           key="survivor_neighbourhood", sources=("survivor_neighbourhood",)),
    # THE DATA MOAT'S OWN RENT LINES. A recorder is a component like any other and the principal's
    # rule admits no exception: E[log W] with it minus E[log W] without it, measured forward, or
    # it is retired. That is deliberately an uncomfortable line to write for an asset whose whole
    # argument is that it cannot be re-acquired later -- but "unbuyable" is a reason to start
    # capture TODAY, not a licence to skip the billing. If the tape's certificates carry no
    # growth after a fair window, the correct response is to stop mining it harder, not to keep
    # paying for a disk because the bytes felt precious.
    Module("data_source:tick_tape", "data_source", RESEARCH_PNL,
           "expected log-wealth per day carried in the funded book by certificates whose "
           "mechanism needs the tick tape -- the liquidity_regime and orderflow_imbalance "
           "families, which read data/tape/ticks through orthogonal_sweep._tape_series, plus any "
           "moat-mined candidate. Without the tape those families produce nothing at all, so "
           "'without' is genuinely zero rather than a counterfactual that has to be modelled",
           "measure_research_source", "desks/mt5/recorders/tick_recorder.py",
           key="tick_tape", sources=("liquidity_regime", "orderflow_imbalance", "tape", "moat")),
    Module("data_source:vol_archive", "data_source", RESEARCH_PNL,
           "expected log-wealth per day carried by certificates conditioned on the implied-vol / "
           "term-structure archive. READS UNMEASURED BY CONSTRUCTION UNTIL IT HAS VINTAGES: the "
           "archive is forward-only, holds no promotion authority in any lane, and cannot have "
           "produced a certificate before its own series is long enough (vol_archive.MIN_VINTAGES"
           "). An UNMEASURED row here is the module working, not a gap -- and it becomes a real "
           "verdict on its own, without anyone having to remember to add the line later",
           "measure_research_source", "desks/mt5/recorders/vol_archive.py",
           key="vol_archive", sources=("vol_archive", "vol_term", "variance_premium",
                                       "implied_vol")),
    # ------------------------------------------------------------------------------------------
    # NINE DISCOVERY ORGANS THE RENT LEDGER COULD NOT NAME (2026-09-05).
    #
    # Measured that day: of 62 rent modules and 71 capability-graph nodes, exactly SIX names
    # coincided. The ledger bills MECHANISMS; the graph names ORGANS. So 51 decision-affecting
    # organs were unpriceable BY CONSTRUCTION -- the MEASURED rung was unreachable for them however
    # long the desk ran, and that read in every report as "not enough evidence yet" rather than as
    # the wiring defect it was.
    #
    # These nine are added because each one's source string was CONFIRMED in the producers rather
    # than guessed: a grep for `source[:=]"<name>"` finds 5 sites for excursions, 8 for
    # regime_coverage, 5 for opportunity_curve, 3 for alpha_evolution, and 2 each for the rest, so
    # RESEARCH_PNL will key on exactly these names when the hypotheses land. The remaining organs
    # (alpha_genome, anomaly_factory, microstructure_miner, tail_alpha_search, transition_alpha,
    # style_premia_sweep, cross_asset_graph, weak_signal_compiler, survivor_distiller,
    # world_causal_graph, macro_intel, mutation_yield, factor_model_coevolution) stamp NO source
    # string, so a line here would name a row that never appears. That is worse than the honest
    # gap: it would make the node read `billable` while nothing could ever price it, which is the
    # measurement theatre this whole ledger exists to prevent. Their fix is a change to each
    # PRODUCER -- stamp a source -- and it is tracked as the remaining ratchet, not faked here.
    *(Module(name, "proposer", RESEARCH_PNL,
             "expected log-wealth per day carried in the funded book by certificates whose "
             "hypotheses this organ sourced, against the declared cost of running it; the "
             "allocator's own claim, never recomputed here",
             "measure_research_source", where, key=key, sources=(key,))
      for name, key, where in (
          ("excursions", "excursions", "desks/mt5/research/excursions.py"),
          ("exit_accounts", "exit_accounts", "desks/mt5/research/exit_accounts.py"),
          ("factor_residual_engine", "factor_residual",
           "desks/mt5/research/factor_residual_engine.py"),
          ("missed_growth", "missed_growth", "desks/mt5/research/missed_growth.py"),
          ("opportunity_curve", "opportunity_curve", "desks/mt5/research/opportunity_curve.py"),
          ("regime_coverage", "regime_coverage", "desks/mt5/research/regime_coverage.py"),
          ("revival_engine", "revival_engine", "desks/mt5/research/revival_engine.py"),
          ("plumbing_miner", "plumbing_miner", "desks/mt5/research/plumbing_miner.py"),
          ("alpha_evolution", "alpha_evolution", "desks/mt5/research/alpha_evolution.py"),
          # TWELVE MORE, FOUND BY READING THE SOURCE CONSTANT RATHER THAN GREPPING FOR A LITERAL.
          # The first pass looked for `source[:=]"<organ name>"` and missed every organ that
          # stamps its source through a module-level `SOURCE = "..."`, which is the more common
          # idiom here -- so twelve organs were filed as "stamps no source" when they stamp one on
          # every row they write. The lesson is the same one the dead-wire fence learned: a
          # vocabulary search finds the phrasing you thought of, and the thing you are looking for
          # is a CAPABILITY. Re-run as an AST-anchored regex over each node's declared module, it
          # is twelve for twelve.
          #
          # FOUR OF THEM BILL UNDER A NAME THAT IS NOT THE NODE'S, which is precisely why the
          # graph needed `billed_as`: microstructure_miner stamps "microstructure",
          # style_premia_sweep stamps "style_premia", tail_alpha_search stamps "tail_alpha", and
          # weak_signal_compiler stamps "weak_signal_ensemble". Keying these on the node name
          # would have produced four lines that never match a row -- billable in appearance,
          # unpriceable in fact.
          ("anomaly_factory", "anomaly_factory", "desks/mt5/research/anomaly_factory.py"),
          ("cross_asset_graph", "cross_asset_graph", "desks/mt5/research/cross_asset_graph.py"),
          ("factor_model_coevolution", "factor_model_coevolution",
           "desks/mt5/research/factor_model_coevolution.py"),
          ("fund_playbook", "fund_playbook", "desks/mt5/research/fund_playbook.py"),
          ("microstructure_miner", "microstructure",
           "desks/mt5/research/microstructure_miner.py"),
          ("mutation_yield", "mutation_yield", "desks/mt5/research/mutation_yield.py"),
          ("style_premia_sweep", "style_premia", "desks/mt5/research/style_premia_sweep.py"),
          ("survivor_distiller", "survivor_distiller",
           "desks/mt5/research/survivor_distiller.py"),
          ("tail_alpha_search", "tail_alpha", "desks/mt5/research/tail_alpha_search.py"),
          ("transition_alpha", "transition_alpha", "desks/mt5/research/transition_alpha.py"),
          ("weak_signal_compiler", "weak_signal_ensemble",
           "desks/mt5/research/weak_signal_compiler.py"),
          ("world_causal_graph", "world_causal_graph",
           "desks/mt5/research/world_causal_graph.py"),
      )),
    # THE EXECUTION-LEARNING LINES (2026-09-05, the principal's order). One billable quantity --
    # R per filled trade recovered from execution leakage -- and three claimants. The corpus
    # bills the leakage trend because it is what made leakage decomposable at all; the two models
    # bill nothing until they are MEASURED on their own power gate AND wired to something that
    # changes an order. Both currently read UNMEASURED WITH THE SHORTFALL, which is the rule
    # working: a model that cannot yet be fitted must not be billed for what a measurement bought.
    Module("data_source:fill_corpus", "data_source", CAPTURE_HISTORY,
           "leakage per fill in the FIRST half of the alpha-capture history minus the SECOND: "
           "E[R kept with the corpus] - E[R kept without it], where 'without' is genuinely "
           "nothing because leakage could not be decomposed before a joined fill record existed",
           "measure_execution_learning", "libs/execution/fill_corpus.py", key="fill_corpus"),
    Module("execution_choice_model", "execution_algo", ALPHA_CAPTURE,
           "R per fill saved by routing to the style the conditional surface names instead of "
           "the market baseline; unbillable until the surface is MEASURED on its own power gate "
           "and a consumer that changes an order is declared",
           "measure_execution_learning", "libs/execution/execution_choice_model.py",
           key="execution_choice_model"),
    Module("meta_labeler", "allocator_component", ALPHA_CAPTURE,
           "R per fill of the meta-sized book minus the 1x book on the same signals; unbillable "
           "until the labeler is MEASURED and wired. It can never re-admit a signal a gate "
           "refused, so its downside is bounded at SKIP and its upside is zero while UNMEASURED",
           "measure_execution_learning", "libs/execution/meta_label.py", key="meta_labeler"),
    Module("ai_capital_modifier", "ai_organ", MODIFIER_LEDGER,
           "the AI capital modifier's own conditioning ledger: heat its categories moved x what "
           "that heat earned, realised per day (the same rows as state_posterior, read as the "
           "modifier's rent; CAPITAL_MODIFIERS.json category verdicts beside)",
           "measure_conditioning", "libs/portfolio/capital_modifiers"),
    *(Module(organ, "ai_organ", RESEARCH_PNL,
             "expected log-wealth per day the organ's certificates carry in the funded book, "
             "trials and declared spend beside", "measure_research_source",
             f"desks/mt5/research/{organ}.py", key=organ, sources=prefixes)
      for organ, prefixes in AI_ORGANS.items()),
    # THE 27 DECISION-AFFECTING ORGANS THAT CARRIED NO RENT LINE AT ALL (2026-09-05). Measured on
    # the capability ladder that day: 71 nodes, 57 of them DECISION_AFFECTING, 1 MEASURED, 0
    # LIVE_LEARNING -- and 27 of the decision-affecting ones were not billable, meaning nothing
    # could ever retire them however long they cost. A component nothing bills is a component
    # nothing can retire, which is precisely how a desk accumulates organs that compute forever.
    #
    # They are billed THROUGH WHAT THEY CHANGE (see `measure_organ`), so this list adds no new
    # arithmetic to the desk -- only the chain from an organ to a priced decision, and a NAMED
    # verdict where that chain is not closed.
    *(Module(organ, "organ", "capability graph -> the consumer's own ledger",
             "rent of the decision this organ's output changes, inherited from the consumer that "
             "reads it; NOT_BINDING with the artifact named when nothing reads it at all",
             "measure_organ", f"writes {artifact}", key=artifact)
      for organ, artifact in ORGAN_OUTPUT.items()),
    *(Module(organ, "organ", "n/a -- the money path itself", why, "measure_organ",
             "libs.ops.module_rent.INFRASTRUCTURE", key=organ)
      for organ, why in INFRASTRUCTURE.items()),
)

#: Name -> Module, for `measure_organ`'s inheritance lookup. Built once from the registry rather
#: than passed around, because the chain is organ -> artifact -> consumer NAME and the consumer's
#: own line has to be found by that name.
MODULES_BY_NAME: dict[str, Module] = {m.name: m for m in MODULES}


# --------------------------------------------------------------------------- ledgers
class Ledgers:
    """Every ledger under one root, read once and lazily. A missing file reads as an empty
    document and the measure says so; nothing here invents a row."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._json: dict[str, dict[str, Any]] = {}
        self._rows: dict[str, list[dict[str, Any]]] = {}
        self._realised: dict[tuple[str, str], float] | None = None

    def exists(self, rel: str) -> bool:
        return (self.root / rel).exists()

    def json(self, rel: str) -> dict[str, Any]:
        if rel not in self._json:
            try:
                doc = json.loads((self.root / rel).read_text("utf-8"))
            except (OSError, ValueError):
                doc = {}
            self._json[rel] = doc if isinstance(doc, dict) else {}
        return self._json[rel]

    def rows(self, rel: str) -> list[dict[str, Any]]:
        if rel not in self._rows:
            out: list[dict[str, Any]] = []
            try:
                for ln in (self.root / rel).read_text("utf-8").splitlines():
                    if not ln.strip():
                        continue
                    try:
                        r = json.loads(ln)
                    except ValueError:
                        continue
                    if isinstance(r, dict):
                        out.append(r)
            except OSError:
                pass
            self._rows[rel] = out
        return self._rows[rel]

    def realised(self) -> dict[tuple[str, str], float]:
        """Realised R per (sleeve, day): live fills first, forward-phase shadow rows beside.

        Both are read because the conditioning ledger is written for whichever book the
        allocator funded, and off-box the only realised evidence is shadow. A row is attributed
        to the day its trade was ENTERED (shadow) or CLOSED (live) -- the ledger's own keys.
        """
        if self._realised is not None:
            return self._realised
        out: dict[tuple[str, str], float] = defaultdict(float)
        for r in self.rows(LIVE_LEDGER):
            day = str(r.get("close_time") or r.get("time") or "")[:10]
            v = _num(r.get("r_multiple"))
            if r.get("sleeve") and day and v is not None:
                out[(str(r["sleeve"]), day)] += v
        shadow = self.root / SHADOW_DIR
        if shadow.is_dir():
            for f in sorted(shadow.glob("ledger_*.json")):
                try:
                    rows = json.loads(f.read_text("utf-8"))
                except (OSError, ValueError):
                    continue
                if not isinstance(rows, list):
                    continue
                name = f.stem.removeprefix("ledger_")
                for row in rows:
                    if not isinstance(row, dict) or str(row.get("phase") or "") != "forward":
                        continue
                    day = str(row.get("entry_time") or "")[:10]
                    v = _num(row.get("r_multiple"))
                    if day and v is not None:
                        out[(name, day)] += v
        self._realised = dict(out)
        return self._realised


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _row(m: Module, verdict: str, *, rent: float | None = None, unit: str = "log-wealth/day",
         n: int = 0, ci: list[float] | None = None, window: str = "", why: str = "",
         **extra: Any) -> dict[str, Any]:
    logw = rent if unit == "log-wealth/day" else None
    return {"kind": m.kind, "ledger": m.ledger, "rule": m.rule, "where": m.where,
            "rent_logw_per_day": (round(logw, 10) if logw is not None else None),
            "rent": (round(rent, 10) if rent is not None else None), "unit": unit,
            "n": int(n), "ci": ci, "verdict": verdict, "window": window, "why": why, **extra}


def verdict_from_samples(samples: list[float]) -> tuple[str, dict[str, Any]]:
    """Daily with/without samples -> a sign the desk can act on, or an honest refusal.

    Same line as missed_growth (t = mean / se against T_LINE) so a rail read here and a rail
    read there cannot disagree; the CI is reported so a reader can see how far from the line
    the evidence sits rather than just which side.
    """
    n = len(samples)
    if n < MIN_N:
        return UNMEASURED, {"n": n, "why": f"{n} daily sample(s), need {MIN_N}"}
    if all(abs(x) < 1e-15 for x in samples):
        return NOT_BINDING, {"n": n, "rent": 0.0, "why": "every sample is zero: did not bind"}
    mean = statistics.fmean(samples)
    sd = statistics.stdev(samples) if n > 1 else 0.0
    se = sd / math.sqrt(n)
    t = (mean / se) if se > 0 else (math.inf if mean > 0 else -math.inf)
    ci = [mean - 1.96 * se, mean + 1.96 * se]
    v = EARNS if t > T_LINE else (COSTS if t < -T_LINE else UNMEASURED)
    why = ("" if v != UNMEASURED else
           f"|t| = {abs(t):.2f} < {T_LINE}: the sign is not distinguishable from zero on {n} days")
    return v, {"n": n, "rent": mean, "t": round(t, 3) if math.isfinite(t) else None,
               "ci": [round(ci[0], 10), round(ci[1], 10)], "why": why}


def _sign_verdict(value: float | None, n: int, *, min_n: int = MIN_N) -> tuple[str, str]:
    """For ledgers that carry one number rather than samples: the sign, once n clears the bar."""
    if value is None:
        return UNMEASURED, "no number on the ledger"
    if n < min_n:
        return UNMEASURED, f"n = {n} < {min_n}"
    if value > 0:
        return EARNS, ""
    if value < 0:
        return COSTS, ""
    return NOT_BINDING, "exactly zero"


# --------------------------------------------------------------------------- measures
def measure_rail(m: Module, led: Ledgers) -> dict[str, Any]:
    doc = led.json(MISSED_GROWTH)
    if not doc:
        return _row(m, UNMEASURED, why=f"{MISSED_GROWTH} absent on this host")
    rail = (doc.get("rails") or {}).get(m.key)
    if not isinstance(rail, dict):
        return _row(m, UNMEASURED, why=f"rail {m.key} not on {MISSED_GROWTH}")
    v_raw = str(rail.get("verdict") or UNMEASURED)
    verdict = {"EARNS_ITS_PLACE": EARNS, "COSTS_GROWTH": COSTS, "NOT_BINDING": NOT_BINDING,
               "SAMPLE": UNMEASURED}.get(v_raw, UNMEASURED)
    n = int(_num(rail.get("n")) or 0)
    rent = _num(rail.get("mean_logw_per_day"))
    unit = "log-wealth/day"
    if rent is None:
        rent = _num(rail.get("value_logw_per_day"))
    if rent is None and _num(rail.get("value_logw_per_veto")) is not None:
        rent, unit = _num(rail.get("value_logw_per_veto")), "log-wealth/veto"
    t = _num(rail.get("t"))
    ci = None
    if rent is not None and t not in (None, 0.0) and n > 1 and t is not None:
        se = abs(rent / t)
        ci = [round(rent - 1.96 * se, 10), round(rent + 1.96 * se, 10)]
    return _row(m, verdict, rent=rent, unit=unit, n=n, ci=ci,
                window=f"{n} daily sample(s) on missed_growth's ledger",
                why=str(rail.get("why") or ""), missed_growth_verdict=v_raw,
                rail_kind=rail.get("kind"))


def _pnl_sources(led: Ledgers, prefixes: tuple[str, ...]) -> dict[str, Any] | None:
    """Roll every RESEARCH_PNL source row whose name starts with one of `prefixes` into one
    module. Prefix matching, not equality, because the world forest splits one organ across a
    source per region cluster and the organ is the thing being billed."""
    doc = led.json(RESEARCH_PNL)
    if not doc:
        return None
    growth, cost = 0.0, 0.0
    trials, certified = 0, 0
    names: list[str] = []
    for src, c in (doc.get("sources") or {}).items():
        if not isinstance(c, dict) or not any(str(src).startswith(p) for p in prefixes):
            continue
        growth += _num(c.get("growth_per_day")) or 0.0
        trials += int(_num(c.get("trials")) or 0)
        certified += int(_num(c.get("certified")) or 0)
        cost += _num(c.get("cost_units")) or 0.0
        names.append(str(src))
    return {"growth_per_day": growth, "trials": trials, "certified": certified,
            "cost_units": cost, "sources": names}


def _pnl_row(m: Module, led: Ledgers, agg: dict[str, Any] | None, basis: str) -> dict[str, Any]:
    if agg is None:
        return _row(m, UNMEASURED, why=f"{RESEARCH_PNL} absent on this host")
    trials, growth = int(agg["trials"]), float(agg["growth_per_day"])
    if trials == 0 and growth == 0.0:
        return _row(m, NOT_BINDING, rent=0.0, n=0, window="whole research history",
                    why=f"no trials and no funded certificate from {basis}",
                    spend_cost_units=0.0, certified=0, sources=agg.get("sources", []))
    verdict, why = _sign_verdict(growth, trials)
    if verdict == COSTS or (growth <= 0.0 and trials >= MIN_N):
        verdict, why = COSTS, (f"{trials} trial(s) and the funded book carries no growth from "
                               f"{basis}: dead information on this ledger")
    return _row(m, verdict, rent=growth, n=trials, window="whole research history",
                why=why, spend_cost_units=round(float(agg["cost_units"]), 2),
                certified=int(agg["certified"]),
                roi_growth_per_cost_unit=(round(growth / float(agg["cost_units"]), 12)
                                          if agg["cost_units"] else None),
                sources=agg.get("sources", []),
                note="growth is the allocator's EXPECTED log-wealth per day for the funded "
                     "certificates, not realised; spend is in the bandit's declared cost units")


def measure_proposer(m: Module, led: Ledgers) -> dict[str, Any]:
    doc = led.json(RESEARCH_PNL)
    if not doc:
        return _row(m, UNMEASURED, why=f"{RESEARCH_PNL} absent on this host")
    arm = (doc.get("arms") or {}).get(m.key)
    if not isinstance(arm, dict):
        return _row(m, UNMEASURED, why=f"arm {m.key} not on {RESEARCH_PNL}")
    agg = {"growth_per_day": float(_num(arm.get("growth_per_day")) or 0.0),
           "trials": int(_num(arm.get("trials")) or 0),
           "certified": int(_num(arm.get("certified")) or 0),
           "cost_units": float(_num(arm.get("cost_units")) or 0.0),
           "sources": list(arm.get("sources") or [])}
    return _pnl_row(m, led, agg, f"arm {m.key}")


def measure_research_source(m: Module, led: Ledgers) -> dict[str, Any]:
    return _pnl_row(m, led, _pnl_sources(led, m.sources or (m.key,)), f"source(s) {m.sources}")


def conditioning_samples(led: Ledgers) -> tuple[list[float], dict[str, Any]]:
    """Per day: sum over ledger rows of h x (1 - 1/mult) x realised R -- the growth the modifier's
    heat move earned or lost against the un-modified book. Linearised: heat proportional to the
    posterior mean, so 'without' heat is h / mult, floored at MULT_FLOOR for vetoes."""
    rows = led.rows(MODIFIER_LEDGER)
    if not rows:
        return [], {"why": f"{MODIFIER_LEDGER} absent or empty on this host", "ledger_rows": 0}
    realised = led.realised()
    by_day: dict[str, float] = defaultdict(float)
    joined = 0
    for r in rows:
        day = str(r.get("t") or "")[:10]
        h, mult = _num(r.get("heat")), _num(r.get("multiplier"))
        key = (str(r.get("sleeve")), day)
        if h is None or mult is None or key not in realised:
            continue
        joined += 1
        by_day[day] += h * (1.0 - 1.0 / max(mult, MULT_FLOOR)) * realised[key]
    return [by_day[d] for d in sorted(by_day)], {"ledger_rows": len(rows), "joined_rows": joined,
                                                 "why": ("" if joined else
                                                         "no ledger row joins a realised R")}


def measure_conditioning(m: Module, led: Ledgers) -> dict[str, Any]:
    samples, meta = conditioning_samples(led)
    cats = (led.json(CAPITAL_MODIFIERS).get("categories") or {})
    extra = {"categories": {c: v.get("verdict") for c, v in cats.items() if isinstance(v, dict)},
             **{k: v for k, v in meta.items() if k != "why"}}
    if not samples:
        return _row(m, UNMEASURED, why=str(meta.get("why") or "no samples"), **extra)
    v, st = verdict_from_samples(samples)
    return _row(m, v, rent=st.get("rent"), n=int(st["n"]), ci=st.get("ci"),
                window=f"{len(samples)} ledger day(s)", why=str(st.get("why") or ""),
                t=st.get("t"), **extra)


def measure_admission(m: Module, led: Ledgers) -> dict[str, Any]:
    adm = led.json(STATE_ADMISSION)
    if not adm:
        return _row(m, UNMEASURED, unit="oos_mse_gain",
                    why=f"{STATE_ADMISSION} absent on this host")
    gap = (adm.get("gaps") or {}).get(m.key)
    row = (adm.get("verdicts") or {}).get(m.key)
    if not isinstance(row, dict):
        return _row(m, UNMEASURED, unit="oos_mse_gain",
                    why=str(gap or f"dimension {m.key} not judged on {STATE_ADMISSION}"))
    v_raw = str(row.get("verdict") or "")
    gain, t = _num(row.get("mse_gain")), _num(row.get("t_deflated", row.get("t_paired")))
    n = int(_num(row.get("n_test")) or 0)
    if v_raw == "GRAVEYARD" or (t is not None and t < -T_LINE and n >= MIN_N):
        verdict, why = COSTS, "measurably worse out of sample: conditioning on it adds noise"
    elif v_raw.startswith("ADMIT") or (t is not None and t > T_LINE and n >= MIN_N):
        verdict, why = EARNS, "improved out-of-sample prediction of unseen trades"
    elif v_raw == "UNJUDGED":
        verdict, why = UNMEASURED, str(row.get("why") or "unjudged")
    else:
        verdict, why = UNMEASURED, (f"{v_raw}: {row.get('why') or 'kept by shrinkage only'}"
                                    if v_raw else "no verdict")
    joint, _ = conditioning_samples(led)
    return _row(m, verdict, rent=gain, unit="oos_mse_gain", n=n, window=f"{n} test trade(s)",
                why=why, t=t, admission_verdict=v_raw, dimension=m.key,
                conditioning_logw_per_day=(round(statistics.fmean(joint), 10) if joint else None),
                conditioning_days=len(joint))


def _scoreboard(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """`execution_registry.scoreboard(rows=...)` when the desk is importable, else the same
    aggregation in place -- the numbers must not depend on which host runs this."""
    desk = ROOT / "desks" / "mt5"
    if str(desk) not in sys.path:
        sys.path.insert(0, str(desk))
    try:
        from mt5desk.execution_registry import scoreboard  # type: ignore[import-not-found]
        out = scoreboard(rows=rows)
        return dict(out) if isinstance(out, dict) else {}
    except Exception:
        pass
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if r.get("algo"):
            by[str(r["algo"])].append(r)
    algos: dict[str, Any] = {}
    for algo, rs in sorted(by.items()):
        real = [float(r["realised_cost"]) for r in rs if r.get("realised_cost") is not None]
        algos[algo] = {"n": len(rs), "n_filled": len(real),
                       "mean_realised_cost": (statistics.fmean(real) if real else None),
                       "mean_filled_frac": statistics.fmean(
                           float(r.get("filled_frac") or 0.0) for r in rs)}
    return {"n": len(rows), "algos": algos}


def measure_execution_algo(m: Module, led: Ledgers) -> dict[str, Any]:
    rows = led.rows(ALGO_OUTCOMES)
    if not rows:
        return _row(m, UNMEASURED, unit="price_frac/fill",
                    why=f"{ALGO_OUTCOMES} absent or empty on this host")
    board = _scoreboard(rows).get("algos") or {}
    mine, base = board.get(m.key), board.get(BASELINE_ALGO)
    if m.key == BASELINE_ALGO:
        return _row(m, NOT_BINDING, rent=0.0, unit="price_frac/fill",
                    n=int((mine or {}).get("n_filled") or 0),
                    why="the market algorithm IS the baseline every other one is measured "
                        "against; its rent against itself is zero by definition")
    if not mine:
        return _row(m, NOT_BINDING, rent=0.0, unit="price_frac/fill", n=0,
                    why=f"{m.key} executed no plan in the ledger")
    if not base or base.get("mean_realised_cost") is None:
        return _row(m, UNMEASURED, unit="price_frac/fill", n=int(mine.get("n_filled") or 0),
                    why="no filled market-baseline plan to measure against")

    def costs(algo: str) -> list[float]:
        return [float(r["realised_cost"]) for r in rows
                if r.get("algo") == algo and r.get("realised_cost") is not None]

    a, b = costs(m.key), costs(BASELINE_ALGO)
    n = len(a)
    if n < MIN_N or len(b) < MIN_N:
        return _row(m, UNMEASURED, unit="price_frac/fill", n=n,
                    why=f"{n} filled plan(s) against {len(b)} baseline fill(s); need {MIN_N} each")
    ff_mine, ff_base = float(mine.get("mean_filled_frac") or 0.0), float(
        base.get("mean_filled_frac") or 0.0)
    if ff_mine < ff_base - 0.2:
        return _row(m, UNMEASURED, unit="price_frac/fill", n=n,
                    why=(f"fills {ff_mine:.0%} of its lots against the baseline's {ff_base:.0%}: "
                         "a cost advantage on the subset that filled is not comparable"),
                    mean_filled_frac=ff_mine, baseline_filled_frac=ff_base)
    rent = statistics.fmean(b) - statistics.fmean(a)
    se = math.sqrt(statistics.variance(a) / n + statistics.variance(b) / len(b))
    t = rent / se if se > 0 else (math.inf if rent > 0 else (-math.inf if rent < 0 else 0.0))
    verdict = EARNS if t > T_LINE else (COSTS if t < -T_LINE else UNMEASURED)
    ci = [round(rent - 1.96 * se, 12), round(rent + 1.96 * se, 12)]
    return _row(m, verdict, rent=rent, unit="price_frac/fill", n=n, ci=ci,
                window=f"{n} filled plan(s) vs {len(b)} baseline fill(s)",
                why=("" if verdict != UNMEASURED else f"|t| = {abs(t):.2f} < {T_LINE}"),
                t=(round(t, 3) if math.isfinite(t) else None),
                mean_realised_cost=round(statistics.fmean(a), 10),
                baseline_mean_realised_cost=round(statistics.fmean(b), 10),
                mean_filled_frac=ff_mine, baseline_filled_frac=ff_base)


def measure_execution_learning(m: Module, led: Ledgers) -> dict[str, Any]:
    """Rent for the fill corpus and the two models built on it. Unit: R per filled trade.

    ONE BILLABLE QUANTITY, THREE CLAIMANTS. All three exist to recover execution leakage -- the
    gap between the predicted frictionless edge and the realised one -- so all three bill on the
    SAME number: the R per fill the desk stopped losing, measured FORWARD across the alpha
    capture ledger's own history. `with` is the second half of that history, `without` the first.

    THE CORPUS BILLS FIRST BECAUSE IT IS WHAT MAKES THE OTHERS MEASURABLE AT ALL. Its "without"
    is genuinely nothing: before a joined fill record existed, leakage could not be decomposed
    into spread, slippage, commission and residual, so no execution decision could be aimed. The
    two MODELS bill only once they are (a) MEASURED on their own power gate and (b) declared as
    the consumer of an order-changing decision. Until both hold, this returns UNMEASURED WITH THE
    SHORTFALL -- which is the module working, not a gap. Attributing the corpus's leakage
    improvement to an unwired model would be billing a model for what a measurement bought.

    THIS IS DELIBERATELY AN UNCOMFORTABLE LINE for an asset whose whole argument is that it
    cannot be re-acquired later. "Unbuyable" is a reason to start capture TODAY, not a licence to
    skip the billing: if the corpus's leakage line does not improve after a fair window, the
    right response is to stop building models on it, not to keep paying because the rows felt
    precious.
    """
    cap = led.json(ALPHA_CAPTURE)
    hist = led.rows(CAPTURE_HISTORY)
    twin = led.json(EXECUTION_TWIN)
    n_exec = int(_num((cap.get("corpus") or {}).get("unique_executions")) or 0)
    if m.key in ("execution_choice_model", "meta_labeler"):
        block = (twin.get("execution_choice") if m.key == "execution_choice_model"
                 else twin.get("meta_label")) or {}
        status = str(block.get("status") or UNMEASURED)
        raw_power = block.get("power")
        power: dict[str, Any] = raw_power if isinstance(raw_power, dict) else {}
        raw_gate = power.get("gate")
        gate: dict[str, Any] = raw_gate if isinstance(raw_gate, dict) else power
        short = _num(gate.get("shortfall_per_arm"))
        need = _num(gate.get("n_required_per_arm")) or _num(
            power.get("n_required_per_bucket"))
        return _row(m, UNMEASURED, unit="R/fill", n=n_exec,
                    why=(f"{m.key} is {status} and wired to nothing that sends an order; it "
                         "cannot bill a leakage improvement a measurement bought. "
                         f"corpus holds {n_exec} execution(s)"
                         + (f"; needs {need:.0f} per arm" if need else "")
                         + (f", short {short:.0f}" if short else "")),
                    model_status=status,
                    n_required_per_arm=(int(need) if need else None),
                    shortfall_per_arm=(int(short) if short else None))
    leaks = [v for v in (_num(r.get("leakage_r")) for r in hist) if v is not None]
    if len(leaks) < 2 * MIN_N:
        return _row(m, UNMEASURED, unit="R/fill", n=n_exec,
                    why=(f"{len(leaks)} alpha-capture point(s) on {CAPTURE_HISTORY}; a forward "
                         f"with/without split needs {2 * MIN_N}. The corpus holds {n_exec} "
                         "execution(s); a point is only written when the capture ratio is "
                         "MEASURED, so this reads UNMEASURED until the desk has fills"),
                    capture_points=len(leaks))
    half = len(leaks) // 2
    before, after = leaks[:half], leaks[half:]
    rent = statistics.fmean(before) - statistics.fmean(after)   # leakage FELL => positive rent
    se = math.sqrt(statistics.variance(before) / len(before)
                   + statistics.variance(after) / len(after))
    t = rent / se if se > 0 else (math.inf if rent > 0 else (-math.inf if rent < 0 else 0.0))
    verdict = EARNS if t > T_LINE else (COSTS if t < -T_LINE else UNMEASURED)
    return _row(m, verdict, rent=rent, unit="R/fill", n=n_exec,
                ci=[round(rent - 1.96 * se, 12), round(rent + 1.96 * se, 12)],
                window=f"{len(before)} point(s) before vs {len(after)} after",
                why=("" if verdict != UNMEASURED else f"|t| = {abs(t):.2f} < {T_LINE}"),
                t=(round(t, 3) if math.isfinite(t) else None), capture_points=len(leaks))


def measure_dynamic_weights(m: Module, led: Ledgers) -> dict[str, Any]:
    alloc = led.json(ALLOCATION)
    if not alloc:
        return _row(m, UNMEASURED, why=f"{ALLOCATION} absent: no allocator pass on this host")
    proof = alloc.get("proof") or {}
    scores = proof.get("scores") or {}
    dyn = _num(scores.get("dynamic"))
    best_name = str(proof.get("best_baseline") or "")
    best = _num(scores.get(best_name)) if best_name else None
    if dyn is None or best is None:
        return _row(m, UNMEASURED, why="proof scores (dynamic, best_baseline) not on the artifact")
    n = int(_num((alloc.get("evidence") or {}).get("worlds")) or 0)
    rent = dyn - best
    verdict = (EARNS if proof.get("passed") else
               (COSTS if rent < 0 else UNMEASURED))
    return _row(m, verdict, rent=rent, n=n, window=f"{n} sampled world(s), one pass",
                why=("" if proof.get("passed") else str(proof.get("why") or "")),
                best_baseline=best_name, proof_passed=bool(proof.get("passed")))


def measure_posterior_growth(m: Module, led: Ledgers) -> dict[str, Any]:
    alloc = led.json(ALLOCATION)
    if not alloc:
        return _row(m, UNMEASURED, why=f"{ALLOCATION} absent: no allocator pass on this host")
    cmp_ = (alloc.get("posterior_growth") or {}).get("vs_funded") or {}
    delta = _num(cmp_.get("delta_elogw_per_day"))
    if delta is None:
        return _row(m, UNMEASURED, why="no posterior_growth.vs_funded on the artifact")
    lo, hi = _num(cmp_.get("ci_lo")), _num(cmp_.get("ci_hi"))
    ci = [lo, hi] if lo is not None and hi is not None else None
    verdict = (EARNS if cmp_.get("beats") else
               (COSTS if hi is not None and hi < 0 else UNMEASURED))
    return _row(m, verdict, rent=delta, n=int(_num(cmp_.get("n_paths")) or 0) or MIN_N, ci=ci,
                window="one pass, bootstrap over sampled paths",
                why=("" if verdict != UNMEASURED else "the CI straddles zero"),
                adopted=bool((alloc.get("posterior_growth") or {}).get("adopted")))


def measure_kelly_surface(m: Module, led: Ledgers) -> dict[str, Any]:
    alloc = led.json(ALLOCATION)
    if not alloc:
        return _row(m, UNMEASURED, why=f"{ALLOCATION} absent: no allocator pass on this host")
    ks = alloc.get("kelly_surface") or {}
    rows = ks.get("rows") or []
    f_tail = _num(ks.get("f_tail"))
    if f_tail is None or not rows:
        return _row(m, UNMEASURED, why="no kelly_surface rows on the artifact")
    if f_tail >= 1.0 - 1e-9:
        return _row(m, NOT_BINDING, rent=0.0, window="one pass",
                    why="the tail bound sits at or above the book's own fraction")
    growth = {float(r["f"]): _num(r.get("mean_growth")) for r in rows
              if isinstance(r, dict) and _num(r.get("f")) is not None}
    g_tail, g_book = growth.get(f_tail), growth.get(1.0)
    if g_tail is None or g_book is None:
        return _row(m, UNMEASURED, why="surface rows do not cover f_tail and f = 1")
    rent = g_tail - g_book
    verdict = EARNS if rent > 0 else (COSTS if rent < 0 else NOT_BINDING)
    return _row(m, verdict, rent=rent, n=MIN_N, window="one pass over the sampled worlds",
                why="", f_tail=f_tail,
                note="binding this pass: the bound's growth against the unbounded book; a "
                     "negative number is growth the tail bound declined and must be weighed "
                     "against the ruin it refused")


def measure_marginal_admission(m: Module, led: Ledgers) -> dict[str, Any]:
    """What the dE[log W] admission criterion is worth: the growth its admitted set adds.

    THE UNIT IS THE OBJECTIVE ITSELF, which is the whole reason this criterion replaced a Sharpe
    ranking: each admitted candidate's rent IS `E[logW | book + i] - E[logW | book]`, measured on
    one world population at one total heat. A scan that admits nothing is NOT_BINDING (it changed
    no allocation and cost no growth), not a failure -- a book that already holds everything worth
    holding is the criterion working.
    """
    alloc = led.json(ALLOCATION)
    if not alloc:
        return _row(m, UNMEASURED, why=f"{ALLOCATION} absent: no allocator pass on this host")
    adm = alloc.get("admission") or {}
    if str(adm.get("status") or "") != "MEASURED":
        return _row(m, UNMEASURED,
                    why=f"no measured admission scan on the artifact (status "
                        f"{adm.get('status', 'ABSENT')!r})")
    rent = _num((adm.get("rent") or {}).get("sum_admitted_delta_elogw_per_day"))
    n_scored = int(_num(adm.get("n_scored")) or 0)
    n_admitted = int(_num(adm.get("n_admitted")) or 0)
    if rent is None:
        return _row(m, UNMEASURED, why="the scan carries no rent line")
    if not n_admitted:
        return _row(m, NOT_BINDING, rent=0.0, n=n_scored,
                    window=f"one pass, {n_scored} candidate(s) scored",
                    why="the criterion admitted nothing this pass: it changed no allocation")
    verdict = EARNS if rent > 0 else (COSTS if rent < 0 else NOT_BINDING)
    return _row(m, verdict, rent=rent, n=max(n_scored, MIN_N),
                window=f"one pass, {n_admitted}/{n_scored} candidate(s) admitted",
                why="", n_admitted=n_admitted, n_scored=n_scored,
                unscored=len(adm.get("unscored") or {}), basis=str(adm.get("basis") or ""),
                note=("a sum of separately-measured marginals against the same held book; the "
                      "joint delta of admitting all of them at once is smaller"))


def measure_regime_conditioning(m: Module, led: Ledgers) -> dict[str, Any]:
    alloc = led.json(ALLOCATION)
    if not alloc:
        return _row(m, UNMEASURED, why=f"{ALLOCATION} absent: no allocator pass on this host")
    reg = alloc.get("regime") or {}
    if not reg.get("conditioned"):
        return _row(m, NOT_BINDING, rent=0.0, why="regime conditioning INACTIVE this pass")
    return _row(m, UNMEASURED, why=("conditioned, but the artifact carries no score of the "
                                    "same book on unconditioned worlds; needs "
                                    "growth.mean_log_per_day_unconditioned beside "
                                    "growth.mean_log_per_day"))


def _graph_consumers(artifact: str) -> tuple[list[str], str, str]:
    """(node readers, external reader, terminal state) for `artifact`, from the capability graph.

    THE GRAPH KNOWS THREE WAYS AN ARTIFACT IS CONSUMED and this reads all three, because reading
    only the first gets the answer confidently wrong:

      NODES[].reads     a graph node consumes it -- the chain continues to that node's rent
      EXTERNAL_READERS  a consumer that is not a graph node (`research_supervisor` is a process
                        manager, not a node), declared with its reason. Missing this reported
                        `macro_intel` as reading NOT_BINDING when its interrupt is in fact the one
                        artifact of that whole layer which reaches a decision.
      HUMAN_READ        advisory BY DESIGN: a person reads it and no automated decision turns on
                        it. That is a legitimate terminal state the desk has already reasoned
                        about, not an unwired defect, and calling it one would put correct
                        designs on a retire list.

    Imported LAZILY: `capability_graph` reads this module's registry to decide what is billable,
    so a module-level import here is a cycle. Prefix matching runs both ways -- the graph's own
    convention, since a node may declare a directory where the writer names a file inside it.
    """
    try:
        from libs.ops.capability_graph import EXTERNAL_READERS, HUMAN_READ, NODES
    except Exception:
        return [], "", ""
    nodes = sorted(n.name for n in NODES
                   if any(r.startswith(artifact) or artifact.startswith(r) for r in n.reads))
    external = ""
    for path, who in EXTERNAL_READERS.items():
        if path.startswith(artifact) or artifact.startswith(path):
            external = str(who)
            break
    human = "HUMAN_READ" if any(h.startswith(artifact) or artifact.startswith(h)
                                for h in HUMAN_READ) else ""
    return nodes, external, human


def measure_organ(m: Module, led: Ledgers, _chain: tuple[str, ...] = ()) -> dict[str, Any]:
    """An organ's rent, inherited from whatever its output actually changes.

    `_chain` carries the organs already visited on this inheritance walk. The desk's artifact
    graph has genuine cycles -- `miner_candidate_compiler` writes the candidates the gauntlet
    reads and reads the gate report the gauntlet writes -- so a walk without it recurses until
    the stack ends. A cycle is not an error either: it is a research LOOP, and the honest verdict
    names it rather than crashing on it or silently picking one arbitrary direction.
    """
    if m.name in INFRASTRUCTURE:
        return _row(m, NOT_BINDING, rent=0.0, unit="log-wealth/day",
                    why=f"MONEY PATH, not an input to it -- {INFRASTRUCTURE[m.name]}",
                    infrastructure=True)
    artifact = ORGAN_OUTPUT.get(m.name, m.key)
    nodes, external, human = _graph_consumers(artifact)
    readers = [r for r in nodes if r != m.name]
    if human and not readers and not external:
        return _row(m, NOT_BINDING, rent=0.0,
                    why=(f"{artifact} is declared HUMAN_READ: advisory by design, a person reads "
                         f"it and no automated decision turns on it. Rent is zero because it "
                         f"changes no sizing -- that is the intended terminal state here, NOT an "
                         f"unwired organ, and it becomes billable the day a consumer is declared"),
                    artifact=artifact, readers=[], terminal="HUMAN_READ")
    if external and not readers:
        return _row(m, UNMEASURED,
                    why=(f"{artifact} is consumed OUTSIDE the graph -- {external[:180]} -- so the "
                         f"consumer carries no rent line to inherit. What would price it is the "
                         f"decision that consumer changes, measured against the same decision "
                         f"taken on its own clock"),
                    artifact=artifact, readers=[], external_reader=external)
    if not readers:
        return _row(m, NOT_BINDING, rent=0.0,
                    why=(f"nothing on this tree reads {artifact}: this organ's output changes no "
                         f"decision, so its rent is zero by construction. Either wire a consumer "
                         f"or retire it -- the one thing it must not stay is unbilled"),
                    artifact=artifact, readers=[])
    # THE MONEY PATH IS NOT AN INHERITABLE PRICE. An organ feeding `gateway`, `release` or the
    # evaluator feeds something whose own rent is NOT_BINDING by construction, and inheriting that
    # would report "this organ does not bind" about an organ that decides what the desk holds.
    # What prices it is the realised growth of what it put there.
    infra = [r for r in readers if r in INFRASTRUCTURE]
    priced = {r: MODULES_BY_NAME[r] for r in readers
              if r in MODULES_BY_NAME and r not in INFRASTRUCTURE and r not in _chain}
    if not priced and infra:
        return _row(m, UNMEASURED,
                    why=(f"{artifact} feeds the money path directly ({', '.join(infra)}), whose "
                         f"own rent is not separable. What prices this organ is the realised "
                         f"growth of what it put in the book -- {LIVE_LEDGER} joined to the "
                         f"sleeves it admitted -- not an inherited NOT_BINDING"),
                    artifact=artifact, readers=readers, feeds_money_path=infra)
    if not priced:
        looped = [r for r in readers if r in _chain]
        return _row(m, UNMEASURED,
                    why=((f"{artifact} is read by {', '.join(readers)}, which is already on this "
                          f"inheritance chain ({' -> '.join(_chain)}): a research LOOP, so no "
                          f"consumer outside it prices this organ yet")
                         if looped else
                         (f"{artifact} is read by {', '.join(readers)}, and none of those carries "
                          f"a rent line either -- so the chain from this organ to a priced "
                          f"decision is not closed. 'Something reads it' is not 'it earns'")),
                    artifact=artifact, readers=readers)
    # INHERITED, NEVER RECOMPUTED. Two modules in one chain must not produce two different
    # answers about the same value; the consumer owns the arithmetic and this reports its verdict.
    rows: dict[str, dict[str, Any]] = {}
    for name, mod in priced.items():
        fn = MEASURES[mod.measure]
        rows[name] = (fn(mod, led, (*_chain, m.name)) if fn is measure_organ  # type: ignore[call-arg]
                      else fn(mod, led))
    earns = [n for n, r in rows.items() if r["verdict"] == EARNS]
    costs = [n for n, r in rows.items() if r["verdict"] == COSTS]
    best = (earns or costs or sorted(rows))[0]
    row = rows[best]
    verdict = row["verdict"] if (earns or costs) else UNMEASURED
    return _row(m, verdict, rent=row.get("rent"), unit=str(row.get("unit") or "log-wealth/day"),
                n=int(row.get("n") or 0), ci=row.get("ci"), window=str(row.get("window") or ""),
                why=(f"inherited from {best}, which this organ's {artifact} feeds"
                     + (f": {row['why']}" if row.get("why") else "")),
                artifact=artifact, readers=readers, priced_through=best)


MEASURES = {name: fn for name, fn in globals().items() if name.startswith("measure_")}


def discover(led: Ledgers, modules: tuple[Module, ...] = MODULES) -> tuple[Module, ...]:
    """Ledger rows the registry does not name yet: judged dimensions, executed algorithms and
    alt-data sources present on this host. Reported under the registry's rules rather than left
    unbilled, and listed so the registry can be extended by name."""
    have = {m.name for m in modules}
    extra: list[Module] = []
    adm = led.json(STATE_ADMISSION)
    for d in sorted((adm.get("verdicts") or {}).keys()):
        name = f"state_dimension:{d}"
        if name not in have:
            extra.append(Module(name, "state_dimension", STATE_ADMISSION,
                                "walk-forward gain from conditioning on the dimension (unit: "
                                "out-of-sample MSE gain)", "measure_admission",
                                "discovered on STATE_ADMISSION.json", key=str(d)))
    for r in led.rows(ALGO_OUTCOMES):
        algo = str(r.get("algo") or "")
        name = f"execution_algo:{algo}"
        if algo and name not in have and all(e.name != name for e in extra):
            extra.append(Module(name, "execution_algo", ALGO_OUTCOMES,
                                "market baseline's mean realised cost minus the algorithm's",
                                "measure_execution_algo", "discovered on the outcomes ledger",
                                key=algo))
    pnl = led.json(RESEARCH_PNL)
    covered = tuple(p for m in modules for p in m.sources)
    for src in sorted((pnl.get("sources") or {}).keys()):
        base = str(src).split(":")[0]
        if SOURCE_ARM.get(base) != "alt_data_hypothesis" or any(
                str(src).startswith(p) for p in covered):
            continue
        name = f"data_source:{src}"
        if name not in have:
            extra.append(Module(name, "data_source", RESEARCH_PNL,
                                "growth the source's certificates carry in the funded book",
                                "measure_research_source", "discovered on RESEARCH_PNL.json",
                                key=str(src), sources=(str(src),)))
    return (*modules, *extra)


def measure(root: Path | None = None,
            modules: tuple[Module, ...] | None = None) -> dict[str, dict[str, Any]]:
    """Every module's rent from the desk's own ledgers under `root`. Reads only."""
    led = Ledgers(ROOT if root is None else Path(root))
    mods = discover(led) if modules is None else modules
    out: dict[str, dict[str, Any]] = {}
    for m in mods:
        fn = MEASURES[m.measure]
        try:
            out[m.name] = fn(m, led)
        except Exception as exc:                     # a broken ledger is a reading, not a crash
            out[m.name] = _row(m, UNMEASURED, why=f"{type(exc).__name__}: {exc}")
    return out


# --------------------------------------------------------------------------- history and RETIRE
def _window_id(day: str) -> str:
    """The Monday of the ISO week the day falls in: one window per week, whatever the cadence."""
    d = date.fromisoformat(day)
    return d.fromordinal(d.toordinal() - d.weekday()).isoformat()


def retire_list(history: list[dict[str, Any]], *, k: int = K_WINDOWS,
                min_n: int = MIN_N) -> dict[str, dict[str, Any]]:
    """Modules that read COSTS with n >= min_n in the last k consecutive weekly windows.

    The LAST reading in a window speaks for it (a rerun on the same day supersedes, never
    accumulates). A window without a reading breaks the run: silence is not a COSTS verdict.
    """
    by_mod: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in history:
        name, day = str(r.get("module") or ""), str(r.get("day") or "")
        if not name or not day:
            continue
        try:
            wid = _window_id(day)
        except ValueError:
            continue
        cur = by_mod[name].get(wid)
        if cur is None or str(cur.get("day")) <= day:
            by_mod[name][wid] = r
    out: dict[str, dict[str, Any]] = {}
    for name, wins in by_mod.items():
        ordered = sorted(wins.items(), reverse=True)
        run = 0
        for i, (wid, r) in enumerate(ordered):
            if i > 0:
                prev_w = date.fromisoformat(ordered[i - 1][0])
                if (prev_w - date.fromisoformat(wid)).days != 7:
                    break                                    # a gap in the record ends the run
            if r.get("verdict") == COSTS and int(_num(r.get("n")) or 0) >= min_n:
                run += 1
            else:
                break
        if run >= k:
            out[name] = {"kind": ordered[0][1].get("kind"), "windows_costs": run,
                         "since_window": ordered[run - 1][0],
                         "latest": {key: ordered[0][1].get(key)
                                    for key in ("day", "rent", "unit", "n", "ci")},
                         "ledger": ordered[0][1].get("ledger")}
    return out


def run(root: Path | None = None, write: bool = True, today: str | None = None) -> dict[str, Any]:
    """Measure, remember today's readings once, name what has cost growth for K windows."""
    base = ROOT if root is None else Path(root)
    day = today or datetime.now(tz=UTC).date().isoformat()
    modules = measure(base)
    led = Ledgers(base)
    history = led.rows(HISTORY)
    have = {(str(r.get("module")), str(r.get("day"))) for r in history}
    new: list[dict[str, Any]] = []
    for name, row in modules.items():
        if (name, day) in have:
            continue
        new.append({"day": day, "module": name, "kind": row["kind"], "verdict": row["verdict"],
                    "rent": row["rent"], "unit": row["unit"], "n": row["n"], "ci": row["ci"],
                    "ledger": row["ledger"], "at": datetime.now(tz=UTC).isoformat()})
    if write and new:
        p = base / HISTORY
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            for r in new:
                fh.write(json.dumps(r) + "\n")
    history = history + new
    retire = retire_list(history)
    by_verdict: dict[str, list[str]] = defaultdict(list)
    for name, row in modules.items():
        by_verdict[str(row["verdict"])].append(name)
    doc: dict[str, Any] = {
        "generated_utc": datetime.now(tz=UTC).isoformat(), "day": day,
        "n_modules": len(modules),
        "modules": modules,
        "retire": retire,
        "costs": sorted(by_verdict[COSTS]), "earns": sorted(by_verdict[EARNS]),
        "not_binding": sorted(by_verdict[NOT_BINDING]),
        "unmeasured": sorted(by_verdict[UNMEASURED]),
        "by_kind": {k: {v: sum(1 for r in modules.values() if r["kind"] == k and r["verdict"] == v)
                        for v in (EARNS, COSTS, NOT_BINDING, UNMEASURED)} for k in KINDS},
        "registry": [asdict(m) for m in MODULES],
        "history_rows": len(history), "new_rows": len(new),
        "lines": {"min_n": MIN_N, "t_line": T_LINE, "k_windows": K_WINDOWS},
        "rule": ("rent = Elog_with - Elog_without on the module's own ledger; a module that reads "
                 f"COSTS with n >= {MIN_N} in {K_WINDOWS} consecutive weekly windows is NAMED "
                 "under `retire`. This report names; a person or the capability-graph check "
                 "retires. No sacred modules -- the AI organs are on the same list."),
        "consumers": ("libs/ops/capability_graph.stages (MEASURED evidence), "
                      "scripts/check_reachability (warns on a node whose rent is COSTS), "
                      "the principal"),
    }
    if write:
        p = base / REPORT
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def main() -> int:
    d = run()
    print(f"MODULE RENT  {d['n_modules']} modules  costs={d['costs']}  earns={d['earns']}  "
          f"retire={sorted(d['retire'])}")
    for name, r in d["modules"].items():
        rent = "" if r["rent"] is None else f" rent={r['rent']:+.3e} {r['unit']}"
        print(f"  {name:36s} {r['kind']:20s} {r['verdict']:12s} n={r['n']:<5d}{rent}")
        if r["verdict"] == UNMEASURED and r.get("why"):
            print(f"      {r['why']}")
    print(f"written: {ROOT / REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
