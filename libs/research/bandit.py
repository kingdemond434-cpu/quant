"""The research-direction bandit: which KIND of research deserves the next unit of compute.

RD-Agent(Q)'s one transferable idea beyond "let a model propose factors" is that the loop
Research -> Development -> Evaluation -> Feedback has a SCHEDULER, and the scheduler is a
multi-armed bandit over research directions rather than an equal split. This is that scheduler
for the desk, with the arms the desk actually has:

    new_mechanism           a family never run before, or a formula from the alpha grammar
    mutate_survivor         re-parameterise / re-condition a certified cell
    combine_survivors       ensembles of sub-power cells (weak-signal compiler)
    conditional_state_edge  a cell specific to a state or clock bucket the book is dead in
    execution_improvement   spread / fill / plumbing cells and cost surfaces
    exit_improvement        exit rules from measured excursions
    cross_asset_signal      residual and lead-lag cells across the driver graph
    alt_data_hypothesis     a crawler / prospector row naming data the desk lacks
    failure_derived         a hypothesis mined from the graveyard
    model_architecture      factor x model co-evolution and expert routers
    external_screen         the automated external backtest chain (edge_search primitives) --
                            its own arm, so its tens of thousands of judged screens do not
                            drown the priors of the human-mechanism sources

    score_j = E[dElogW_j] x P(valid survivor_j) / (compute + data + latency + multiplicity)_j

P(valid survivor) is a Beta posterior per arm from the hypothesis graph's fates, shrunk toward
the pooled rate with PSEUDO pseudo-counts so an arm that has never been tried is optimistic,
never certain. E[dElogW] is the mean marginal growth the allocator reports for certified
sleeves that came from the arm, and 1.0 where it has certified nothing yet. Costs are MEASURED
wall-clock and CPU seconds from the compute ledger (`libs.ops.compute_ledger.cost_by_run`)
wherever one of the arm's legs has been costed, re-expressed on the declared table's scale so a
costed arm and an uncosted one stay comparable; the declared table is the fallback, and the
basis -- measured or declared, and why -- is recorded per arm. A declared table is auditable; a
ledger is auditable AND true.

THOMPSON SAMPLING gives each arm the probability that it is the best arm, and EXPLORE of the
budget is spread uniformly on top -- the machine may not become trapped by its own history.
THREE GROUPS SIT OVER THE ARMS -- exploit / adjacent / cold -- and the desk's own allocation
policy (`ops/research_allocation_policy.json`) declares floors for them; `allocate` lifts a
group that Thompson would have starved below its floor and reports every lift. The report also
carries FRONTIER_REGRET: what the top-scoring arm alone would have returned against what the
spread budget returns, measured against the posterior means known at allocation time.
The output is a budget file every consumer reads: the deepening worker weights its VOI order by
it, the daily cycle scales each proposer's time budget by it. The budget names its
`controller_variant` so a second allocation policy can be run beside this one and compared.

A TREE OF BANDITS, NOT ONE FLAT ROW (2026-09-23). The eleven arms were allocated as one flat row
with floors asserted on three groups AFTER the fact, and the arm score was a product of measured
terms with no explicit uncertainty bonus at all -- an arm nothing had ever judged was funded by
whatever its priors happened to multiply out to. The allocation is now a two-level tree,

    GLOBAL -> {exploit, adjacent, cold} -> the arms of that group

and the arm score is written out term by term,

    Score_j = E[dg_j] + BETA_UCB x sqrt(ln N / n_j) + LAMBDA_NOVELTY x Novelty_j

with E[dg] the evidence mixture (worth x survival posterior x breadth credit / measured cost),
n_j the arm's judged hypotheses, N their total, and Novelty read from the novelty gate's own
artifact -- neutral at 0.0 for every arm while the gate publishes no attribution, because one
pooled number added to eleven scores is compression, not information. EVERY NODE CARRIES ITS OWN
PROTECTED FLOOR: the group floors are the policy file's, and the arm floor is the same
`EXPLORE / 11` the flat allocator used to add as a uniform share, now enforced inside its
group's budget so the two levels hold at once. No node carries a ceiling. The split always
totals one: whatever rounding leaves over goes to the highest-scoring node.

AND THE LADDER IS COUNTED. The six discovery temperatures T0..T5 -- exploit, connect, explore
adjacent, explore far, standing questions, unseen/alien -- are declared to run concurrently, and
nothing measured it. `temperature_ladder` maps every PROPOSAL SOURCE to its temperature and
publishes each one's proposals and measured compute seconds for the window, so "all six are
running" is a count with an IDLE verdict available, and a source no table claims is named rather
than bucketed.
"""
from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
BUDGET = DESK / "data" / "research_budget.json"
REPORT = DESK / "reports" / "RESEARCH_BANDIT.json"
#: The desk's declared research allocation policy: portfolio bounds and mode floors.
POLICY = ROOT / "ops" / "research_allocation_policy.json"
#: WHICH ALLOCATION POLICY WROTE THE BUDGET. One controller exists today ("A"). The field is in
#: the budget so that when a second policy is run beside it, every consumer that reads a share
#: can say which controller it was serving, and survivors per compute-hour can be split by it.
CONTROLLER_VARIANT = "A"

ARMS: tuple[str, ...] = (
    "new_mechanism", "mutate_survivor", "combine_survivors", "conditional_state_edge",
    "execution_improvement", "exit_improvement", "cross_asset_signal", "alt_data_hypothesis",
    "failure_derived", "model_architecture", "external_screen",
)

#: Which arm a hypothesis source or task kind belongs to. DECLARED; unknown sources fall to
#: `alt_data_hypothesis`, the arm for "somebody on the internet said".
SOURCE_ARM: dict[str, str] = {
    "alpha_evolution": "new_mechanism", "fund_playbook": "new_mechanism",
    "plumbing_miner": "new_mechanism", "style_premia": "new_mechanism",
    "external": "external_screen", "edge_search": "external_screen",
    "external_discoveries": "external_screen",
    "deepening": "mutate_survivor", "mutation": "mutate_survivor",
    "weak_signal_compiler": "combine_survivors", "survivor_distiller": "mutate_survivor",
    "regime_coverage": "conditional_state_edge", "opportunity_curve": "conditional_state_edge",
    "transition_alpha": "conditional_state_edge", "macro_graph": "conditional_state_edge",
    "microstructure_miner": "execution_improvement", "fill_surface": "execution_improvement",
    "excursions": "exit_improvement", "exit_accounts": "exit_improvement",
    "factor_residual": "cross_asset_signal", "cross_asset_graph": "cross_asset_signal",
    "lead_lag": "cross_asset_signal",
    "data_prospector": "alt_data_hypothesis", "crawler": "alt_data_hypothesis",
    "world": "alt_data_hypothesis",
    "failure_miner": "failure_derived", "graveyard": "failure_derived",
    "revival_engine": "failure_derived",
    "coevolution": "model_architecture", "expert_router": "model_architecture",
    "factor_model_coevolution": "model_architecture",
    # PUBLIC-SYSTEM AND DEEP-FOREST MINING (2026-09-04): claims read off repositories and
    # practitioner stories. They are screened at external-claim volume, so they share the
    # external arm and cannot drown the desk's own mechanism arm.
    "repo_miner": "external_screen", "deep_forest": "external_screen",
    "world_crawler": "external_screen",
    # THE WORLD FOREST, ONE SOURCE PER REGION CLUSTER (2026-09-05). `deep_forest` stays the
    # Chinese founding forest; every other cluster carries its own source name so the research
    # P&L, which censuses hypotheses BY SOURCE before rolling them up to an arm, can learn which
    # forests pay. All of them screen at external-claim volume and share the external arm.
    "deep_forest_jp": "external_screen", "deep_forest_kr": "external_screen",
    "deep_forest_tw_hk": "external_screen", "deep_forest_sea": "external_screen",
    "deep_forest_in": "external_screen", "deep_forest_south_asia": "external_screen",
    "deep_forest_anz": "external_screen", "deep_forest_mena": "external_screen",
    "deep_forest_africa": "external_screen", "deep_forest_west": "external_screen",
    "deep_forest_eu": "external_screen", "deep_forest_nordics": "external_screen",
    "deep_forest_east_eu": "external_screen", "deep_forest_ru": "external_screen",
    "deep_forest_latam": "external_screen", "deep_forest_institutional": "external_screen",
    "tail_alpha": "new_mechanism", "anomaly_factory": "new_mechanism",
    "action_counterfactuals": "exit_improvement",
    "drift_monitor": "conditional_state_edge",
    # THE NINE SEARCH POPULATIONS (2026-09-05, libs/research/search_populations.py). They all
    # run inside `alpha_evolution`, but each is a different KIND of research and the bandit
    # cannot learn which pays if they share one source name. Arms follow what the population
    # DOES, not where it runs: an enumerator and a TPE surrogate are new mechanisms, a GP over
    # the elite is a mutation, the zoo is an external screen, and the three derived populations
    # inherit the arm of the ledger they mine.
    "alpha_evolution:gp": "mutate_survivor",
    "alpha_evolution:gflownet": "new_mechanism",
    "alpha_evolution:symreg": "new_mechanism",
    "alpha_evolution:program_synthesis": "new_mechanism",
    "alpha_evolution:bayesian": "new_mechanism",
    "alpha_evolution:zoo_mutation": "external_screen",
    "alpha_evolution:graveyard_derived": "failure_derived",
    "alpha_evolution:causal_derived": "cross_asset_signal",
    "alpha_evolution:claims_derived": "external_screen",
    # THE BREADTH LANE (2026-09-05). `alpha_breadth` names the alpha clusters nobody in the book
    # occupies, so its yield is a family never run before; the other two condition on a state --
    # the book's own drawdown, and the states in which a surviving edge is stronger or absent --
    # which is what `conditional_state_edge` is for.
    "alpha_breadth": "new_mechanism",
    "drawdown_alpha": "conditional_state_edge",
    "survivor_neighbourhood": "conditional_state_edge",
    # THE ORTHOGONAL SWEEP (hourly leg `sweep`) stamps `orthogonal_sweep:<family>` on every cell
    # it proposes and was falling to the "somebody on the internet said" arm. It sweeps the
    # non-directional families the book does not hold -- a family never run before -- which is
    # what `new_mechanism` is for, and its leg's measured cost is charged there (ARM_RUNS).
    "orthogonal_sweep": "new_mechanism",
}
KIND_ARM: dict[str, str] = {
    "coverage_gap": "conditional_state_edge", "dead_phase": "conditional_state_edge",
    # The breadth lane's task kinds, so a task still routes to an arm when its source name is
    # rewritten. An empty cluster is a new mechanism; a drawdown state and a survivor's state are
    # both a conditional edge.
    "empty_alpha_cluster": "new_mechanism", "drawdown_state_target": "conditional_state_edge",
    "drawdown_alpha_candidate": "conditional_state_edge",
    "survivor_state_strength": "conditional_state_edge",
    "survivor_state_dead": "conditional_state_edge",
    "exit_hypothesis": "exit_improvement", "data_source": "alt_data_hypothesis",
    "fund_claim": "new_mechanism", "alpha_expression": "new_mechanism",
    "failure_lesson": "failure_derived", "model_pairing": "model_architecture",
    "repo_mechanism": "external_screen", "story_mechanism": "external_screen",
    "revival": "failure_derived", "anomaly": "new_mechanism",
    "mutation": "mutate_survivor", "sizing_hypothesis": "execution_improvement",
}

#: Declared unit costs per arm: (compute, data, latency, multiplicity). Multiplicity is the
#: prior number of trials one unit of the arm burns -- a formula search burns hundreds of
#: expressions per proposal, a fund card burns one.
COST: dict[str, tuple[float, float, float, float]] = {
    "new_mechanism": (3.0, 1.0, 1.0, 4.0), "mutate_survivor": (1.0, 0.5, 0.5, 2.0),
    "combine_survivors": (1.0, 0.5, 0.5, 1.0), "conditional_state_edge": (2.0, 1.0, 1.0, 2.0),
    "execution_improvement": (1.0, 2.0, 1.0, 1.0), "exit_improvement": (1.0, 0.5, 0.5, 1.0),
    "cross_asset_signal": (2.0, 1.5, 1.0, 3.0), "alt_data_hypothesis": (1.0, 4.0, 3.0, 1.0),
    "failure_derived": (0.5, 0.5, 0.5, 1.0), "model_architecture": (4.0, 1.0, 1.0, 3.0),
    "external_screen": (2.0, 1.0, 1.0, 6.0),
}
PSEUDO = 20.0
EXPLORE = 0.20
#: An arm with fewer judged hypotheses than this is COLD: its worth/cost ratio is replaced by
#: the pooled ratio so that, before any evidence exists, the declared cost table alone cannot
#: hand half the budget to whichever arm happens to be cheapest. Evidence, not price, allocates.
MIN_JUDGED = 10

#: WHICH COSTED LEG MEASURES WHICH ARM. The compute ledger costs the hourly cycle's legs by name
#: (`hourly_cycle._costed`), never an arm, so the join is DECLARED here and only where the leg's
#: organ is the arm's own generator: `edge_search:*`, the deep-forest miner and the world crawler
#: are the external screen chain; the deepening worker (`deepening`) mutates survivors; the
#: orthogonal sweep proposes families never run; `mine` is the web pass (`crawler`); the exit
#: study, the graveyard model, the execution twin and the ML/ensemble layers are charged by what
#: they DO, as the search populations are. Legs that judge EVERY arm's candidates at once
#: (backtest, external_gauntlet, compile_candidates) belong to no arm and are charged to none.
#: An arm with no leg here, or whose legs carry no row in the window, keeps its declared cost
#: and its `cost_basis` says so.
ARM_RUNS: dict[str, tuple[str, ...]] = {
    "external_screen": ("search", "deep_forest", "world_crawler"),
    "mutate_survivor": ("deepen",),
    "new_mechanism": ("sweep",),
    "alt_data_hypothesis": ("mine",),
    "exit_improvement": ("exit_study",),
    "failure_derived": ("graveyard_model",),
    "execution_improvement": ("execution_twin",),
    "model_architecture": ("ml_layer", "ensemble_optimizer"),
}

#: THE THREE-WAY SPLIT the allocation policy is written in, DECLARED by where an arm starts:
#: an ADJACENT arm starts from a certified cell (mutates it, combines it, conditions it on a
#: state the book is dead in); a COLD arm starts from nothing the book holds (a family never run,
#: data the desk lacks); every other arm works the sleeves and the pipeline the desk already has,
#: which is EXPLOIT. "Exploration" in the policy's sense is adjacent + cold together.
ARM_GROUP: dict[str, str] = {
    "mutate_survivor": "adjacent", "combine_survivors": "adjacent",
    "conditional_state_edge": "adjacent",
    "new_mechanism": "cold", "alt_data_hypothesis": "cold",
}
GROUPS: tuple[str, ...] = ("exploit", "adjacent", "cold")

# --------------------------------------------------------------------- THE TREE OF BANDITS
#: THE PROTECTED EXPLORATION FLOOR AT EVERY NODE. The flat allocator added a uniform
#: `EXPLORE / len(ARMS)` share to every arm after the group floors were enforced, which made the
#: per-arm floor a side effect of an addition rather than a floor anybody could name. In the tree
#: it is the ARM node's own floor, enforced inside its group's budget, so the group floors and
#: the arm floors hold at the same time and neither erodes the other. It is the SAME number the
#: uniform share used to guarantee -- floors ratchet up, never down (L1.50).
ARM_FLOOR = EXPLORE / len(ARMS)
#: Score_j = E[dg_j] + BETA_UCB x sqrt(ln N / n_j) + LAMBDA_NOVELTY x Novelty_j. Both bonus
#: terms are in units of the MEAN expected gain, so the two coefficients are scale-free and an
#: arm can only ever be lifted by them: neither term can subtract from an arm's claim, which is
#: what keeps the tree from becoming a cap on the arms the evidence already likes.
BETA_UCB = 0.25
LAMBDA_NOVELTY = 0.25
#: The novelty gate's artifact (desks/mt5/research/novelty_gate.py OUT). Read, never written.
NOVELTY_REPORT = DESK / "reports" / "NOVELTY_GATE.json"
#: The window the temperature ladder counts proposals over. The compute ledger already keeps its
#: own window (`compute_ledger.WINDOW_DAYS`); this bounds the graph side so a five-year-old
#: proposal cannot make an idle temperature read as running.
TEMPERATURE_WINDOW_H = 24.0 * 7

#: THE DISCOVERY TEMPERATURE LADDER. Six temperatures run CONCURRENTLY -- that is the mandate's
#: claim, and until this table existed nothing measured it. A temperature is not a group and not
#: an arm: it is how far from what the book already holds a PROPOSAL SOURCE starts. T0 re-works a
#: held cell; T5 names a mechanism the desk has no word for. The ladder is published per source
#: with the window's proposals and compute so "all six are running" is a count, not an assertion.
TEMPERATURES: tuple[str, ...] = ("T0", "T1", "T2", "T3", "T4", "T5")
TEMPERATURE_ROLE: dict[str, str] = {
    "T0": "exploit: re-work a cell the book already holds (QD exploiter, deepening, distiller)",
    "T1": "connect: carry an elite across niches or assets (QD connector, recombination)",
    "T2": "explore adjacent: an empty niche one free axis from an occupied one (QD explorer)",
    "T3": "explore far: families the book does not hold at all (sweeps, formula search, screens)",
    "T4": "standing questions: what the desk has DECLARED it cannot explain",
    "T5": "unseen frontier / alien: mechanisms nothing in the library has a name for",
}
#: Which temperature a PROPOSAL SOURCE starts at. Exact source strings win; otherwise the prefix
#: before the first colon. A source in neither is UNCLASSIFIED and counted as such -- absence is
#: not a permission, and a ladder that silently bucketed strangers would report six running
#: temperatures whatever happened.
SOURCE_TEMPERATURE: dict[str, str] = {
    "qd_frontier:exploiter": "T0", "deepening": "T0", "mutation": "T0",
    "survivor_distiller": "T0", "weak_signal_compiler": "T0", "forward_exploitation": "T0",
    "alpha_evolution:gp": "T0", "miner:survivor_distiller": "T0",
    "qd_frontier:connector": "T1", "alpha_recombination": "T1", "cross_asset_graph": "T1",
    "lead_lag": "T1", "factor_residual": "T1", "miner:factor_residual": "T1",
    "event_graph": "T1", "macro_graph": "T1",
    "qd_frontier:explorer": "T2", "alpha_breadth": "T2", "regime_coverage": "T2",
    "drawdown_alpha": "T2", "survivor_neighbourhood": "T2", "opportunity_curve": "T2",
    "transition_alpha": "T2", "drift_monitor": "T2",
    "orthogonal_sweep": "T3", "external": "T3", "edge_search": "T3",
    "external_discoveries": "T3", "alpha_evolution": "T3", "alpha_evolution:gflownet": "T3",
    "alpha_evolution:symreg": "T3", "alpha_evolution:program_synthesis": "T3",
    "alpha_evolution:bayesian": "T3", "alpha_evolution:zoo_mutation": "T3",
    "alpha_evolution:claims_derived": "T3", "alpha_evolution:causal_derived": "T3",
    "anomaly_factory": "T3", "tail_alpha": "T3", "style_premia": "T3",
    "expression_factory": "T3", "plumbing_miner": "T3", "miner:anomalies": "T3",
    "miner:alpha_evolution": "T3", "miner:seasonality": "T3", "miner:microstructure": "T3",
    "miner:plumbing": "T3", "microstructure_miner": "T3", "fill_surface": "T3",
    "excursions": "T3", "exit_accounts": "T3", "coevolution": "T3", "expert_router": "T3",
    "factor_model_coevolution": "T3",
    "standing_questions": "T4", "residual_queue": "T4", "unknown_unknowns": "T4",
    "counterfactual_world": "T4", "research_debt": "T4", "opportunity_gap": "T4",
    "failure_miner": "T4", "graveyard": "T4", "revival_engine": "T4",
    "alpha_evolution:graveyard_derived": "T4", "action_counterfactuals": "T4",
    "unseen_frontier": "T5", "world_crawler": "T5", "world": "T5", "crawler": "T5",
    "deep_forest": "T5", "repo_miner": "T5", "data_prospector": "T5",
    "frontier_unknowns": "T5", "fund_playbook": "T5", "miner": "T5",
}
#: Which COSTED hourly leg spends each temperature's compute. Same discipline as `ARM_RUNS`:
#: only where the leg's organ IS that temperature's generator, and every name here is asserted
#: against hourly_cycle by the tests. `qd_frontier` runs all three of its workers in one leg, so
#: it is shared and its seconds are split by the temperatures' measured proposal counts.
TEMP_RUNS: dict[str, tuple[str, ...]] = {
    "T0": ("deepen", "forward_exploitation"),
    "T1": ("alpha_recombination", "residual_factors", "futures_lead_lag"),
    "T2": ("alpha_breadth", "breadth_sweep", "regime_coverage", "drawdown_alpha_miner"),
    "T3": ("sweep", "search", "alpha_evolution", "expression_factory"),
    "T4": ("standing_questions", "residual_queue", "research_gap_map", "graveyard_model",
           "graveyard_resurrection"),
    "T5": ("unseen_frontier", "world_crawler", "deep_forest", "frontier_unknowns", "mine"),
}
#: A leg whose one pass serves several temperatures at once.
TEMP_SHARED_RUNS: dict[str, tuple[str, ...]] = {"qd_frontier": ("T0", "T1", "T2")}


def arm_of(source: str | None, kind: str | None = None) -> str:
    if kind and str(kind) in KIND_ARM:
        return KIND_ARM[str(kind)]
    src = str(source or "").split(":")[0]
    return SOURCE_ARM.get(src, "alt_data_hypothesis")


def group_of(arm: str) -> str:
    return ARM_GROUP.get(arm, "exploit")


def _in_group(arm: str, group: str) -> bool:
    g = group_of(arm)
    return g == group or (group == "exploration" and g in ("adjacent", "cold"))


def measured_cost(costs: dict[str, dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    """Per-arm compute from the ledger, on the declared table's scale, for arms with a costed leg.

    WHAT IS MEASURED: seconds per pass of the arm's legs -- wall clock, and CPU beside it -- from
    `compute_ledger.cost_by_run` (`costs` is that table, read here when not supplied). WHAT IS
    KEPT FROM THE TABLE: its scale. The declared `compute` column is re-expressed so that its
    mean over the costed arms is unchanged and the costed arms' RELATIVE compute follows their
    measured seconds; the data, latency and multiplicity columns are untouched because the
    ledger does not measure them. A single costed arm therefore keeps its declared compute
    exactly -- one measurement cannot order anything -- and an uncosted arm is absent from the
    result, never priced at zero.
    """
    if costs is None:
        try:
            from libs.ops.compute_ledger import cost_by_run
            costs = cost_by_run()
        except Exception as exc:
            return {"_why": {"status": "UNMEASURED",
                             "why": f"compute ledger unreadable: "
                                    f"{type(exc).__name__}: {exc}"}}
    per_arm: dict[str, dict[str, Any]] = {}
    for arm, legs in ARM_RUNS.items():
        hit = [(leg, costs[leg]) for leg in legs
               if isinstance(costs.get(leg), dict) and int(costs[leg].get("runs") or 0) > 0]
        if not hit:
            continue
        wall = sum(float(c.get("wall_s") or 0.0) / int(c["runs"]) for _, c in hit)
        cpu = sum(float(c.get("cpu_s") or 0.0) / int(c["runs"]) for _, c in hit)
        per_arm[arm] = {
            "wall_s_per_pass": round(wall, 3), "cpu_s_per_pass": round(cpu, 3),
            "runs": sum(int(c["runs"]) for _, c in hit),
            "failures": sum(int(c.get("failures") or 0) for _, c in hit),
            "legs": [leg for leg, _ in hit],
            "legs_uncosted": [leg for leg in legs if leg not in dict(hit)],
        }
    if not per_arm:
        return {}
    decl = float(np.mean([COST[a][0] for a in per_arm]))
    mean_wall = float(np.mean([v["wall_s_per_pass"] for v in per_arm.values()]))
    for a, v in per_arm.items():
        units = decl * v["wall_s_per_pass"] / mean_wall if mean_wall > 0 else COST[a][0]
        v["compute_units"] = round(units, 4)
        v["cost"] = round(units + float(sum(COST[a][1:])), 4)
        v["basis"] = (f"measured: wall {v['wall_s_per_pass']:.1f}s/pass (cpu "
                      f"{v['cpu_s_per_pass']:.1f}s) over {v['runs']} run(s) of "
                      f"{','.join(v['legs'])}, {v['failures']} failed; compute column on the "
                      f"declared scale (mean {decl:.2f} units <-> {mean_wall:.0f}s across "
                      f"{len(per_arm)} costed arm(s))")
    return per_arm


def _declared_basis(arm: str) -> str:
    if arm in ARM_RUNS:
        return (f"declared: legs {','.join(ARM_RUNS[arm])} carry no compute_ledger row in the "
                f"window -- the arm's compute is unmeasured, not zero")
    return "declared: no costed leg is declared for this arm (ARM_RUNS); its compute is unmeasured"


def evidence(graph_rows: Iterable[dict[str, Any]],
             marginal_by_source: dict[str, float] | None = None,
             measured: dict[str, dict[str, Any]] | None = None,
             credit: dict[str, float] | None = None) -> dict[str, dict[str, Any]]:
    """Per-arm counts and the Beta posterior of certification, shrunk to the pooled rate.

    `measured` is `measured_cost()`; an arm found there is priced from the ledger and every
    arm's `cost_basis` says which it was. Callers that pass nothing get the declared table.
    """
    latest: dict[str, dict[str, Any]] = {}
    for r in graph_rows:
        if isinstance(r, dict) and r.get("id"):
            latest[str(r["id"])] = r
    counts = {a: {"born": 0, "failed": 0, "certified": 0} for a in ARMS}
    for r in latest.values():
        a = arm_of(r.get("source"))
        fate = str(r.get("fate"))
        counts[a]["born"] += 1
        if fate in ("FAILED", "BURIED"):
            counts[a]["failed"] += 1
        elif fate == "CERTIFIED":
            counts[a]["certified"] += 1
    tot_c = sum(c["certified"] for c in counts.values())
    tot_f = sum(c["failed"] for c in counts.values())
    pooled = (tot_c + 1.0) / (tot_c + tot_f + 2.0)
    out: dict[str, Any] = {}
    for a in ARMS:
        c = counts[a]
        alpha = 1.0 + PSEUDO * pooled + c["certified"]
        beta = 1.0 + PSEUDO * (1.0 - pooled) + c["failed"]
        worth = float((marginal_by_source or {}).get(a, 1.0))
        rc = float((credit or {}).get(a, 1.0))
        worth = worth * rc
        mc = (measured or {}).get(a)
        if isinstance(mc, dict) and isinstance(mc.get("cost"), (int, float)) and mc["cost"] > 0:
            cost, basis = float(mc["cost"]), str(mc.get("basis") or "measured")
        else:
            cost, basis = float(sum(COST[a])), _declared_basis(a)
        out[a] = {**c, "alpha": round(alpha, 3), "beta": round(beta, 3),
                  "p_survivor": round(alpha / (alpha + beta), 4), "worth": worth,
                  "realised_credit": rc,
                  "cost": cost, "cost_basis": basis, "group": group_of(a),
                  "score_mean": round(worth * alpha / (alpha + beta) / cost, 5)}
    out["_pooled_rate"] = round(pooled, 5)
    return out


def allocation_policy(path: Path | None = None) -> dict[str, Any]:
    """The declared policy, or {} when the file is absent or unreadable -- which `group_floors`
    reports as UNMEASURED rather than treating as 'no floors'."""
    try:
        doc = json.loads((path or POLICY).read_text("utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def group_floors(policy: dict[str, Any]) -> dict[str, Any]:
    """The policy's floors in this module's groups.

    exploit      <- portfolio_bounds.exploitation[0]
    exploration  <- portfolio_bounds.exploration[0]   (adjacent + cold together)
    cold         <- mode_floors.exploration            (search from nothing the book holds)
    adjacent     has no floor: the policy floors no recombination mode
    falsification is UNMAPPED: no arm's kind is falsification, so its floor cannot be asserted
    against a share, and saying so is the measurement.
    """
    if not policy:
        return {"status": "UNMEASURED", "why": f"{POLICY.name} absent or unreadable -- no "
                                               f"floor can be asserted", "floors": {}}

    def _lo(section: str, key: str) -> float | None:
        v = (policy.get(section) or {}).get(key)
        if isinstance(v, (list, tuple)) and v and isinstance(v[0], (int, float)):
            return float(v[0])
        return float(v) if isinstance(v, (int, float)) else None

    floors = {"exploit": _lo("portfolio_bounds", "exploitation"),
              "exploration": _lo("portfolio_bounds", "exploration"),
              "cold": _lo("mode_floors", "exploration"),
              "adjacent": None}
    return {"status": "DECLARED", "floors": floors,
            "unmapped": {"falsification": _lo("mode_floors", "falsification"),
                         "why": "no arm's kind is falsification; the floor has no share to be "
                                "asserted against"}}


def group_shares(shares: dict[str, float]) -> dict[str, float]:
    out = dict.fromkeys(GROUPS, 0.0)
    for a, s in shares.items():
        out[group_of(a)] += float(s)
    out["exploration"] = out["adjacent"] + out["cold"]
    return {k: round(v, 4) for k, v in out.items()}


def enforce_floors(shares: dict[str, float],
                   policy: dict[str, Any]) -> tuple[dict[str, float], dict[str, Any]]:
    """Lift every group the policy floors and Thompson starved, scaling the rest down to fit.

    Groups are nested (exploration contains cold), so the pass repeats until nothing moves;
    the floors are jointly feasible (0.4 + 0.4 + a 0.1 inside the 0.4) so it converges in two.
    Every lift is reported with the share it lifted FROM: enforcement that hides what it
    changed is a policy nobody can audit.
    """
    gf = group_floors(policy)
    floors = gf.get("floors") or {}
    raw = {a: float(s) for a, s in shares.items()}
    s = dict(raw)
    lifted: list[dict[str, Any]] = []
    for _ in range(4):
        moved = False
        for grp in ("cold", "exploration", "exploit"):
            fl = floors.get(grp)
            if fl is None:
                continue
            members = [a for a in s if _in_group(a, grp)]
            others = [a for a in s if a not in members]
            cur = sum(s[a] for a in members)
            if not members or not others or cur + 1e-9 >= fl:
                continue
            for a in members:
                s[a] = s[a] * fl / cur if cur > 0 else fl / len(members)
            rest = sum(s[a] for a in others)
            for a in others:
                s[a] = s[a] * (1.0 - fl) / rest if rest > 0 else (1.0 - fl) / len(others)
            lifted.append({"group": grp, "from": round(cur, 4), "to": fl})
            moved = True
        if not moved:
            break
    status = gf["status"] if gf["status"] != "DECLARED" else (
        "LIFTED_TO_FLOOR" if lifted else "WITHIN_FLOORS")
    check = {"status": status, "policy": str(POLICY.relative_to(ROOT)), "floors": floors,
             "groups_raw": group_shares(raw), "groups": group_shares(s), "lifted": lifted,
             "unmapped": gf.get("unmapped"), "why": gf.get("why", ""),
             "membership": {g: sorted(a for a in ARMS if group_of(a) == g) for g in GROUPS}}
    return s, check


def node_floors(policy: dict[str, Any]) -> dict[str, Any]:
    """Every node's protected floor: the GROUP floors the policy declares, and the ARM floor.

    THE TREE HAS TWO LEVELS AND SO DOES THE FLOOR. `group_floors` reads the policy's portfolio
    bounds and mode floors; the arm level takes an optional `arm_floors` section of the same
    file and, wherever it is silent -- which is everywhere today -- the permanent `ARM_FLOOR`.
    A declared arm floor can only RAISE it: floors ratchet up, never down (L1.50), so a policy
    edit can protect an arm further and can never take the standing protection away.

    No node carries a ceiling. The policy's upper portfolio bounds are read and REPORTED here
    and enforced nowhere: a cap on a group is a cap on the desk's aggressiveness, and adding one
    would need the missed-growth proof the growth governance demands, not a convenient bracket.
    """
    gf = group_floors(policy)
    _declared = policy.get("arm_floors")
    declared: dict[str, Any] = dict(_declared) if isinstance(_declared, dict) else {}
    arms: dict[str, float] = {}
    raised: list[str] = []
    for a in ARMS:
        v = declared.get(a)
        f = float(v) if isinstance(v, (int, float)) and float(v) > ARM_FLOOR else ARM_FLOOR
        if f > ARM_FLOOR:
            raised.append(a)
        arms[a] = f
    ceilings: dict[str, float] = {}
    for key, name in (("exploitation", "exploit"), ("exploration", "exploration")):
        v = (policy.get("portfolio_bounds") or {}).get(key)
        if isinstance(v, (list, tuple)) and len(v) > 1 and isinstance(v[1], (int, float)):
            ceilings[name] = float(v[1])
    return {
        "status": gf["status"],
        "groups": gf.get("floors") or {},
        "arms": arms,
        "arm_floor_default": ARM_FLOOR,
        "arm_floors_raised_by_policy": raised,
        "ceilings_declared_not_enforced": ceilings,
        "why": gf.get("why", ""),
        "unmapped": gf.get("unmapped"),
        "rule": ("a group floor comes from ops/research_allocation_policy.json; an arm floor is "
                 f"max(declared, EXPLORE/{len(ARMS)} = {ARM_FLOOR:.5f}) and is enforced INSIDE "
                 "its group's budget, so both levels hold at once. Declared ceilings are "
                 "reported and never applied -- a cap would need a missed-growth proof"),
    }


def _split_with_floors(weight: Mapping[str, float], total: float,
                       floor: Mapping[str, float]) -> tuple[dict[str, float],
                                                            list[dict[str, Any]]]:
    """Split `total` across nodes proportionally to `weight`, lifting any node below its floor.

    Lifted nodes are pinned and the remainder is re-split among the free ones until nothing is
    below its floor. When the floors alone would exhaust the budget the split is proportional to
    the floors themselves and every node is reported as lifted -- an infeasible floor set is
    reported, never silently dropped.
    """
    keys = list(weight)
    if not keys:
        return {}, []
    fl = {k: max(0.0, float(floor.get(k, 0.0))) for k in keys}
    fl_sum = sum(fl.values())
    if fl_sum >= total - 1e-12:
        denom = fl_sum if fl_sum > 0 else float(len(keys))
        alloc = {k: total * (fl[k] / denom if fl_sum > 0 else 1.0 / len(keys)) for k in keys}
        return alloc, [{"node": k, "from": None, "to": fl[k], "why": "floors exhaust the budget"}
                       for k in keys]
    w = {k: max(0.0, float(weight[k])) for k in keys}
    w_sum = sum(w.values())
    alloc = ({k: total * w[k] / w_sum for k in keys} if w_sum > 0 else
             dict.fromkeys(keys, total / len(keys)))
    lifted: list[dict[str, Any]] = []
    free = set(keys)
    for _ in range(len(keys) + 1):
        below = [k for k in free if alloc[k] < fl[k] - 1e-12]
        if not below:
            break
        for k in below:
            lifted.append({"node": k, "from": round(alloc[k], 6), "to": fl[k]})
            alloc[k] = fl[k]
            free.discard(k)
        if not free:
            break
        rest = total - sum(alloc[k] for k in keys if k not in free)
        fw = sum(w[k] for k in free)
        for k in free:
            alloc[k] = rest * w[k] / fw if fw > 0 else rest / len(free)
    return alloc, lifted


def novelty_by_arm(doc: dict[str, Any] | None = None,
                   path: Path | None = None) -> dict[str, Any]:
    """Novelty_j in [0, 1] per arm, from the novelty gate's artifact -- neutral when unmeasured.

    THE GATE IS THE ONLY ORGAN THAT MEASURES NOVELTY, so the bandit reads it rather than
    inventing a second definition. Three shapes are accepted, in order: an explicit `by_arm`
    block; a `by_source` block, whose source names are routed through `arm_of`; and per-cell rows
    (`rows` / `verdicts` / `sample`) that carry a `source` or `arm`, from which the arm's novel
    rate is counted.

    WHEN NONE OF THEM IS THERE the answer is 0.0 for EVERY arm, and the status says UNMEASURED
    with the pooled rate named beside it. That is the only neutral fallback: the gate's pooled
    `n_novel / n_screened` is one number, and adding one number to all eleven scores compresses
    the differences the evidence measured. A term that cannot tell two arms apart must not be
    allowed to move the budget -- it reports, and nothing else, until the gate publishes an
    attribution.
    """
    if doc is None:
        target = path or NOVELTY_REPORT
        try:
            raw = json.loads(target.read_text("utf-8-sig"))
            doc = raw if isinstance(raw, dict) else {}
        except (OSError, ValueError) as exc:
            return {"status": "UNMEASURED", "basis": "absent",
                    "why": f"{target.name} unreadable ({type(exc).__name__}): every arm carries "
                           f"Novelty 0.0, which changes no allocation",
                    "by_arm": dict.fromkeys(ARMS, 0.0), "pooled_novel_rate": None}
    screened, novel = doc.get("n_screened"), doc.get("n_novel")
    pooled = (float(novel) / float(screened)
              if isinstance(novel, (int, float)) and isinstance(screened, (int, float))
              and float(screened) > 0 else None)

    def _clip(v: Any) -> float | None:
        if isinstance(v, dict):
            v = v.get("novel_rate", v.get("mean"))
        return min(1.0, max(0.0, float(v))) if isinstance(v, (int, float)) else None

    measured: dict[str, float] = {}
    basis = ""
    if isinstance(doc.get("by_arm"), dict):
        for a, v in doc["by_arm"].items():
            got = _clip(v)
            if str(a) in ARMS and got is not None:
                measured[str(a)] = got
        basis = "NOVELTY_GATE.by_arm"
    if not measured and isinstance(doc.get("by_source"), dict):
        acc: dict[str, list[float]] = {}
        for s, v in doc["by_source"].items():
            got = _clip(v)
            if got is not None:
                acc.setdefault(arm_of(str(s)), []).append(got)
        measured = {a: round(float(np.mean(x)), 4) for a, x in acc.items()}
        basis = "NOVELTY_GATE.by_source routed through arm_of"
    if not measured:
        rows: list[Any] = next((doc[k] for k in ("rows", "verdicts", "sample")
                                if isinstance(doc.get(k), list)), [])
        hit: dict[str, list[float]] = {}
        for r in rows:
            if not isinstance(r, dict):
                continue
            src = r.get("source") or r.get("arm")
            if not isinstance(src, str) or not src:
                continue
            a = src if src in ARMS else arm_of(src, r.get("kind"))
            hit.setdefault(a, []).append(
                1.0 if r.get("novel") or str(r.get("verdict")) == "NOVEL" else 0.0)
        measured = {a: round(float(np.mean(x)), 4) for a, x in hit.items()}
        basis = "per-cell novelty verdicts attributed by their row's source"
    if not measured:
        return {"status": "UNMEASURED", "basis": "pooled only",
                "by_arm": dict.fromkeys(ARMS, 0.0), "pooled_novel_rate": pooled,
                "why": (f"{NOVELTY_REPORT.name} publishes no per-arm or per-source novelty and "
                        f"its rows carry no source, so novelty cannot be attributed to an arm; "
                        f"the pooled rate is {pooled if pooled is None else round(pooled, 4)} "
                        f"and every arm carries 0.0, which reorders nothing")}
    fill = pooled if pooled is not None else 0.0
    return {"status": "MEASURED", "basis": basis,
            "by_arm": {a: float(measured.get(a, fill)) for a in ARMS},
            "pooled_novel_rate": pooled,
            "arms_attributed": sorted(measured),
            "arms_on_pooled": sorted(a for a in ARMS if a not in measured),
            "why": (f"{len(measured)} of {len(ARMS)} arm(s) carry a measured novel rate from "
                    f"{basis}; the rest carry the pooled rate, named here rather than hidden")}


def tree_scores(gain: Mapping[str, float], ev: Mapping[str, Mapping[str, Any]],
                novelty: Mapping[str, float] | None = None,
                beta: float = BETA_UCB,
                lam: float = LAMBDA_NOVELTY) -> dict[str, dict[str, Any]]:
    """Score_j = E[dg_j] + beta x sqrt(ln N / n_j) + lambda x Novelty_j, published term by term.

    `gain` is the evidence mixture -- the desk's E[dg]: what one unit of this arm is expected to
    buy, already carrying worth, the survival posterior, the measured cost and the breadth
    credit. `n_j` is the arm's PULLS, meaning hypotheses of that arm the gauntlet has judged;
    `N` is their total. An arm nothing has judged has `n_j = 0` and therefore the largest bonus
    any arm can draw, which is the point: the machine must pay to look where it has not looked.

    BOTH BONUSES ARE IN UNITS OF THE MEAN GAIN, so beta and lambda mean the same thing whatever
    scale the gains arrive on, and both are strictly ADDITIVE -- no term here can lower an arm's
    claim below what the evidence alone would have given it.
    """
    arms = [a for a in ARMS if a in gain]
    if not arms:
        return {}
    pulls = {a: max(0, int(ev.get(a, {}).get("failed") or 0)
                    + int(ev.get(a, {}).get("certified") or 0)) for a in arms}
    total_pulls = sum(pulls.values())
    log_n = math.log(total_pulls) if total_pulls > 1 else 0.0
    gbar = float(np.mean([max(0.0, float(gain[a])) for a in arms])) or 1.0
    out: dict[str, dict[str, Any]] = {}
    for a in arms:
        g = max(0.0, float(gain[a]))
        bonus = beta * math.sqrt(log_n / max(1, pulls[a])) * gbar
        nov = min(1.0, max(0.0, float((novelty or {}).get(a, 0.0))))
        out[a] = {
            "group": group_of(a), "expected_gain": round(g, 6),
            "n_pulls": pulls[a], "never_pulled": pulls[a] == 0, "total_pulls": total_pulls,
            "ucb_bonus": round(bonus, 6), "novelty": round(nov, 4),
            "novelty_bonus": round(lam * nov * gbar, 6),
            "score": round(g + bonus + lam * nov * gbar, 6),
        }
    return out


def allocate_tree(scores: Mapping[str, Mapping[str, Any]], policy: dict[str, Any],
                  *, explore: float = EXPLORE) -> tuple[dict[str, float], dict[str, Any]]:
    """GLOBAL -> group -> arm, every node's floor protected and no budget left unallocated.

    Two splits, never one. The total is divided across the GROUPS by their summed arm scores with
    the policy's group floors enforced (`enforce_floors`, which knows that `exploration` contains
    `cold`); each group's budget is then divided across ITS arms with the arm floors enforced
    inside that budget, so lifting an arm can never pull its group below the floor the policy
    just gave it. Whatever rounding leaves over goes to the highest-scoring node: a budget that
    does not add to one is a budget somebody has to guess about.
    """
    arms = [a for a in ARMS if a in scores]
    if not arms:
        return {}, {"status": "UNMEASURED", "why": "no arm carries a score"}
    nf = node_floors(policy)
    per_arm_explore = explore / len(arms) if explore > 0 else 0.0
    arm_floor = {a: max(float(nf["arms"].get(a, ARM_FLOOR)), per_arm_explore) for a in arms}
    raw = {a: max(0.0, float(scores[a]["score"])) for a in arms}
    tot = sum(raw.values())
    weights = ({a: v / tot for a, v in raw.items()} if tot > 0 else
               dict.fromkeys(arms, 1.0 / len(arms)))
    # LEVEL 1: the groups, floored by the desk's own policy (nested exploration included).
    grouped, check = enforce_floors(weights, policy)
    budget = dict.fromkeys(GROUPS, 0.0)
    for a, v in grouped.items():
        budget[group_of(a)] += float(v)
    # LEVEL 2: the arms inside each group's budget, floored at the arm node.
    share: dict[str, float] = {}
    arm_lifts: list[dict[str, Any]] = []
    nodes: dict[str, Any] = {}
    for g in GROUPS:
        members = [a for a in arms if group_of(a) == g]
        nodes[g] = {"score": round(sum(raw[a] for a in members), 6),
                    "budget": round(budget[g], 6),
                    "floor": (nf["groups"] or {}).get(g), "arms": sorted(members)}
        if not members:
            continue
        alloc, lifts = _split_with_floors({a: raw[a] for a in members}, budget[g],
                                          {a: arm_floor[a] for a in members})
        share.update(alloc)
        arm_lifts.extend({**row, "group": g} for row in lifts)
    # NOTHING IS LEFT OVER. Rounding to the published precision is the only leak, and it goes to
    # the highest-scoring node rather than evaporating.
    out = {a: round(float(share.get(a, 0.0)), 6) for a in arms}
    best = max(arms, key=lambda a: raw[a])
    residual = 1.0 - sum(out.values())
    out[best] = round(out[best] + residual, 6)
    audit: dict[str, Any] = {
        "status": check["status"],
        "rule": ("Score_j = E[dg_j] + beta.sqrt(ln N / n_j) + lambda.Novelty_j; the total is "
                 "split GLOBAL -> group -> arm, each node floored, the residual to the best "
                 "node, so 100% of the budget is always allocated"),
        "beta": BETA_UCB, "lambda": LAMBDA_NOVELTY,
        "total_pulls": next(iter(scores.values())).get("total_pulls"),
        "groups": {g: {**nodes[g],
                       "share": round(sum(out[a] for a in arms if group_of(a) == g), 6)}
                   for g in GROUPS},
        "arms": {a: {**dict(scores[a]), "floor": round(arm_floor[a], 6), "share": out[a],
                     "at_floor": out[a] <= arm_floor[a] + 1e-9} for a in arms},
        "floors": nf,
        "group_lifts": check["lifted"],
        "arm_lifts": arm_lifts,
        "residual_to": best,
        "residual": round(residual, 9),
        "allocated": round(sum(out.values()), 9),
        "policy": check,
    }
    return out, audit


def allocate(ev: dict[str, dict[str, Any]], rng: np.random.Generator, *, draws: int = 400,
             explore: float = EXPLORE,
             credit: dict[str, float] | None = None,
             policy: dict[str, Any] | None = None,
             novelty: Mapping[str, float] | None = None,
             beta: float = BETA_UCB,
             lam: float = LAMBDA_NOVELTY,
             audit: dict[str, Any] | None = None) -> dict[str, float]:
    """Thompson shares: P(arm is best) under sampled survival rates, plus the exploration floor.

    `credit` is `libs.research.breadth_credit` -- what a HIT from this arm is worth to the
    PORTFOLIO, as opposed to on its own. It multiplies the worth/cost ratio AFTER the cold-arm
    clamp below, deliberately: the clamp exists to stop an arm's own thin evidence deciding the
    budget, and the breadth credit is not evidence about an arm at all. It is arithmetic about
    what a hit is worth given where the arm's output lands, and it applies to a cold arm exactly
    as it applies to a warm one. Clamping it away would erase it from the nine arms that carry no
    judged hypotheses -- which is every arm that could raise this book's effective breadth.

    `policy` is the declared allocation policy (read from POLICY when None; pass {} for none).
    Its group floors are the tree's LEVEL-1 floors and the arm floors are its level-2 floors, so
    a group lift can no longer erode the per-arm protection and an arm lift can no longer pull
    its group back under the floor the policy just gave it. `novelty` is the per-arm novelty
    (read from the novelty gate when None; pass {} for none); `beta` and `lam` are the UCB and
    novelty coefficients. `audit`, when a dict, receives the group check under `policy` (same
    shape as before), the whole tree under `tree` and the novelty verdict under `novelty`.
    """
    arms = [a for a in ARMS if a in ev]
    ratio = {a: ev[a]["worth"] / ev[a]["cost"] for a in arms}
    pooled_ratio = float(np.mean(list(ratio.values()))) if ratio else 1.0
    for a in arms:
        if ev[a]["failed"] + ev[a]["certified"] < MIN_JUDGED:
            # ASSIGNED, NOT `min`. The clamp used to be `min(ratio[a], pooled_ratio)`, which
            # removed a cheap arm's price ADVANTAGE and left an expensive arm's price PENALTY
            # untouched -- so with `worth` flat at 1.0 across all eleven arms, as it was measured
            # on 2026-09-07, the budget was still decided by the cost table: corr(share, 1/cost)
            # = 0.87, `new_mechanism` at 5.8% against `combine_survivors` at 13.6%. The comment
            # already said "evidence, not price, allocates" and the asymmetric clamp is what
            # stopped it being true. A cold arm has no price signal in either direction.
            ratio[a] = pooled_ratio
    for a in arms:
        ratio[a] *= float((credit or {}).get(a, 1.0))
    wins = np.zeros(len(arms))
    for _ in range(draws):
        s = np.array([rng.beta(ev[a]["alpha"], ev[a]["beta"]) * ratio[a] for a in arms])
        wins[int(np.argmax(s))] += 1
    p_best = wins / wins.sum()
    # HALF THOMPSON, HALF POSTERIOR MEAN. P(best) alone rewards the arms with the WIDEST
    # posteriors -- ten cold arms each drawing a fat right tail outvote one arm with 50 judged
    # trials -- which is exploration, not allocation. The posterior-mean score is what the
    # evidence actually says; the Thompson half keeps every arm's upside in play.
    mean = np.array([ev[a]["alpha"] / (ev[a]["alpha"] + ev[a]["beta"]) * ratio[a] for a in arms])
    p_mean = mean / mean.sum() if mean.sum() > 0 else np.full(len(arms), 1.0 / len(arms))
    mixture = dict(zip(arms, (0.5 * p_best + 0.5 * p_mean).tolist(), strict=True))
    # THE MIXTURE IS E[dg]; THE TREE IS WHAT SPENDS IT. `tree_scores` adds the two exploration
    # terms the flat allocator never had -- the UCB bonus that pays for an arm nothing has judged
    # and the novelty term the gate measures -- and `allocate_tree` splits the budget GLOBAL ->
    # group -> arm with every node's floor enforced. The uniform `explore / len(arms)` share the
    # old line added is now the ARM node's floor and is the same number, so nothing that was
    # protected lost its protection.
    pol = allocation_policy() if policy is None else policy
    nov: dict[str, Any] = (novelty_by_arm() if novelty is None else
                           {"status": "SUPPLIED", "basis": "caller",
                            "by_arm": dict(novelty),
                            "why": "the caller supplied a per-arm novelty"})
    by_arm = nov.get("by_arm")
    sc = tree_scores(mixture, {a: ev[a] for a in arms},
                     novelty=by_arm if isinstance(by_arm, dict) else None,
                     beta=beta, lam=lam)
    share, tree = allocate_tree(sc, pol, explore=explore)
    if audit is not None:
        check = dict(tree["policy"])
        check["groups"] = group_shares(share)
        check["groups_mixture"] = group_shares(mixture)
        audit["policy"] = check
        audit["tree"] = tree
        audit["novelty"] = nov
    return {a: round(float(x), 4) for a, x in share.items()}


def _research_pnl_worth() -> dict[str, float]:
    """Per-arm worth from the research P&L ledger (research_pnl.py), when it has been written.

    The allocator's marginal dElogW says what a certified sleeve is worth TODAY; the research
    P&L says what an arm's trials have been worth over the desk's whole history. The second is
    the prior for arms whose sleeves are not currently funded, and it never drops below the
    exploration floor's spirit (research_pnl clips it at 0.25).
    """
    try:
        doc = json.loads((DESK / "data" / "research_marginal.json").read_text("utf-8"))
        out = {str(k): float(v) for k, v in (doc.get("worth_by_arm") or {}).items()}
        return {k: v for k, v in out.items() if math.isfinite(v) and v > 0}
    except (OSError, ValueError, TypeError):
        return {}


CREDIT_CLIP = (0.5, 2.0)
CREDIT_N0 = 30.0
CREDIT_K = 2.0


def _credit_factor(realised_r: float, n_trades: int) -> float:
    """Bounded multiplier from realised R: mean R per trade shrunk toward 0 by n/(n+N0),
    then 1 + K x that, clipped. Thirty trades at +0.25R/trade -> x1.25; a thin record -> ~1."""
    n = max(0, int(n_trades))
    if n <= 0:
        return 1.0
    shrunk = (float(realised_r) / n) * (n / (n + CREDIT_N0))
    return float(min(CREDIT_CLIP[1], max(CREDIT_CLIP[0], 1.0 + CREDIT_K * shrunk)))


def realised_credit() -> dict[str, Any]:
    """Per-arm realised-R credit from research/credit_assignment.py (CREDIT_ASSIGNMENT.json).

    DELAYED TRUTH REACHES THE INFORMATION BUDGET HERE (principal F12, 2026-09-12). The credit
    organ publishes what each scientist's certificates went on to EARN -- live deals when the
    live ledger holds at least its floor, forward clocks otherwise, and it says which. Each
    scientist maps to the arm that funds it (`arm_of`), the arm's factor is its trade-weighted
    mean, and the factor multiplies the arm's worth. `basis` is carried onto the report so the
    attestation can tell live credit from forward credit instead of reading a label.
    """
    out: dict[str, Any] = {"basis": "none", "applied": False, "by_arm": {},
                           "why": "no CREDIT_ASSIGNMENT.json: worth unchanged"}
    try:
        doc = json.loads((DESK / "reports" / "CREDIT_ASSIGNMENT.json").read_text("utf-8-sig"))
    except (OSError, ValueError):
        return out
    rows = doc.get("by_scientist") if isinstance(doc.get("by_scientist"), list) else []
    acc: dict[str, list[tuple[float, int]]] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        try:
            rr, n = float(r.get("realised_r") or 0.0), int(r.get("n_trades") or 0)
        except (TypeError, ValueError):
            continue
        if n <= 0:
            continue
        acc.setdefault(arm_of(str(r.get("source") or "")), []).append((rr, n))
    by_arm = {a: round(_credit_factor(sum(x for x, _ in v), sum(n for _, n in v)), 4)
              for a, v in acc.items()}
    basis = str(doc.get("evidence_source") or "none")
    out.update({"basis": basis, "applied": bool(by_arm), "by_arm": by_arm,
                "n_live_deals": doc.get("n_live_deals"), "at": doc.get("at"),
                "why": (f"{len(by_arm)} arm(s) carry realised credit on {basis} evidence; "
                        f"factor = 1 + {CREDIT_K} x (R/trade shrunk by n/(n+{CREDIT_N0:.0f})), "
                        f"clipped to {list(CREDIT_CLIP)}" if by_arm else
                        "CREDIT_ASSIGNMENT.json credits no scientist yet: worth unchanged")})
    return out


def _marginal_by_arm() -> dict[str, float]:
    """Mean allocator marginal dElogW of certified sleeves, grouped by the arm that found them;
    arms without a funded sleeve fall back to the research P&L's lifetime worth."""
    prior = _research_pnl_worth()
    try:
        doc = json.loads((DESK / "reports" / "pf_allocator.json").read_text("utf-8"))
        marg = doc.get("marginal") or (doc.get("book") or {}).get("marginal") or {}
        canon = json.loads((DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json").read_text("utf-8"))
        hunt_of = {k: str((v or {}).get("hunt") or "") for k, v in
                   (canon.get("survivors") or {}).items() if isinstance(v, dict)}
    except (OSError, ValueError):
        return prior
    acc: dict[str, list[float]] = {}
    for name, m in marg.items():
        try:
            v = float(m)
        except (TypeError, ValueError):
            continue
        src = hunt_of.get(name, "")
        acc.setdefault(arm_of(src), []).append(v)
    base = {a: v for a, v in ((a, float(np.mean(x))) for a, x in acc.items()) if v > 0}
    if not base:
        return prior
    scale = float(np.mean(list(base.values())))
    out = {a: v / scale for a, v in base.items()}
    for a, v in prior.items():
        out.setdefault(a, v)
    return out


def _cluster_of(row: Mapping[str, Any]) -> str | None:
    """The alpha cluster a hypothesis row monetises, or None when it cannot be named."""
    try:
        from libs.research.alpha_clusters import UNCLASSIFIED, classify_family, classify_sleeve
    except Exception:
        return None
    for key in ("family", "cell", "name", "id"):
        v = row.get(key)
        if not isinstance(v, str) or not v:
            continue
        lab = classify_family(v) if key == "family" else classify_sleeve(v)
        if lab and lab != UNCLASSIFIED:
            return str(lab)
    return None


def breadth_credit() -> dict[str, Any]:
    """Per-arm portfolio dE[log W] credit, measured where the graph allows and declared elsewhere.

    THE ARM THAT CAN RAISE BREADTH WAS THE ARM BEING STARVED. `new_mechanism` owns
    `empty_alpha_cluster` and therefore every one of the eleven unoccupied alpha clusters, and it
    was receiving 5.8% of research compute because it costs 9 declared units while
    `combine_survivors` costs 3. This is the term that makes the difference between those two
    arms an economic statement rather than a price comparison.
    """
    try:
        from libs.research.breadth_credit import credits, occupied_shares
        from libs.research.hypothesis_graph import Graph
        rows = [r for r in Graph().rows() if isinstance(r, dict)]
        state = None
        try:
            from libs.research.breadth_credit import book_state
            state = book_state()
        except Exception:
            state = None
        occupied = set((state or {}).get("occupied") or [])
        def _arm_of(r: Mapping[str, Any]) -> str | None:
            return arm_of(r.get("source"), r.get("kind"))

        shares_by_arm = occupied_shares(rows, _arm_of, _cluster_of, occupied)
        return credits(ARMS, measured_shares=shares_by_arm)
    except Exception as exc:
        # UNMEASURED means every credit is 1.0, which is exactly the behaviour that existed
        # before this term did. A broken credit must never be able to change an allocation.
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}",
                "credit": dict.fromkeys(ARMS, 1.0)}


def regret(ev: dict[str, dict[str, Any]], shares: dict[str, float],
           worth_unmeasured: Iterable[str] = ()) -> dict[str, Any]:
    """FRONTIER_REGRET of the allocation: the top-scoring arm alone against the spread budget.

    `best_known_surplus` is the largest posterior-mean score any arm carried at allocation time;
    `selected_surplus` is the share-weighted score the budget actually buys. Both are in the
    bandit's own unit (E[dElogW] x P(survivor) / cost per unit of compute), and both are what was
    KNOWN when the shares were set -- never the fate the arms went on to have. A regret above
    zero is expected: the EXPLORE share and the policy floors deliberately spend on arms the
    posterior does not rank first, and this is the measured price of not being trapped by the
    desk's own history. It becomes a finding when it grows while the starved arms keep paying.
    """
    from libs.research.frontier import frontier_regret
    scores = {a: float(ev[a]["score_mean"]) for a in ARMS if a in ev}
    if not scores:
        return {"status": "UNMEASURED", "why": "no arm evidence to score"}
    best_arm = max(scores, key=lambda a: scores[a])
    best = scores[best_arm]
    selected = sum(float(shares.get(a, 0.0)) * scores[a] for a in scores)
    out = frontier_regret(best_known_surplus=best, selected_surplus=selected,
                          by_category={"RESEARCH_REGRET": max(0.0, best - selected)})
    unmeasured = sorted(a for a in worth_unmeasured if a in scores)
    out.update({
        "status": "MEASURED",
        "best_arm": best_arm,
        "unit": "E[dElogW] x P(survivor) / cost, per unit of the arm's compute",
        "worth_unmeasured_arms": unmeasured,
        "basis": (f"scores are posterior means at allocation time; {len(unmeasured)} of "
                  f"{len(scores)} arm(s) carry the 1.0 E[dElogW] default because no certified "
                  f"sleeve of theirs is funded -- their score is P(survivor)/cost, not a "
                  f"measured growth" if unmeasured else
                  "scores are posterior means at allocation time; every arm's E[dElogW] is "
                  "measured from funded sleeves"),
    })
    return out


def temperature_of(source: str | None, kind: str | None = None) -> str | None:
    """The discovery temperature a proposal source starts at, or None when nothing declares it.

    Exact source string first (`qd_frontier:explorer` is not `qd_frontier:exploiter`), then the
    prefix before the first colon, then the forest family. A stranger returns None and is
    counted as UNCLASSIFIED: a ladder that quietly bucketed unknown sources would report six
    running temperatures no matter what the desk actually ran, which is the assertion this table
    exists to replace.
    """
    src = str(source or "").strip()
    if not src:
        return None
    if src in SOURCE_TEMPERATURE:
        return SOURCE_TEMPERATURE[src]
    head = src.split(":")[0]
    if head in SOURCE_TEMPERATURE:
        return SOURCE_TEMPERATURE[head]
    if head.startswith("deep_forest") or head.startswith("forest_"):
        return "T5"
    if kind and str(kind) in KIND_ARM:
        # A task kind with no source name still names what it IS; route it by its arm's group.
        return {"cold": "T3", "adjacent": "T2", "exploit": "T0"}[group_of(KIND_ARM[str(kind)])]
    return None


def _cost_table() -> tuple[dict[str, dict[str, Any]] | None, str]:
    """(compute-ledger table, why-not). One guarded read, shared by the arms and the ladder."""
    try:
        from libs.ops.compute_ledger import cost_by_run
        return dict(cost_by_run()), ""
    except Exception as exc:
        return None, f"compute ledger unreadable: {type(exc).__name__}: {exc}"


def temperature_ladder(graph_rows: Iterable[dict[str, Any]],
                       costs: dict[str, dict[str, Any]] | None = None,
                       window_h: float | None = None) -> dict[str, Any]:
    """WHAT EACH OF THE SIX TEMPERATURES ACTUALLY GOT THIS WINDOW -- proposals and compute.

    The mandate says the six discovery temperatures run CONCURRENTLY. Nothing measured it: the
    bandit published eleven arm shares and no reader could tell whether T4 had produced a single
    proposal this month. This counts both halves of the claim.

    PROPOSALS come from the hypothesis graph, deduplicated by id (the graph is append-only, so
    the last row for an id is its current fate) and filtered to `window_h` by the row's own
    stamp when it carries one. COMPUTE comes from the compute ledger through `TEMP_RUNS`;
    `qd_frontier` runs its exploiter, connector and explorer inside one leg, so its seconds are
    split across T0/T1/T2 by their measured proposal counts, equally when none of the three
    proposed anything, and the basis says which.

    A temperature with no proposals and no seconds reads IDLE, not absent: that is the finding.
    Sources no table claims are counted and NAMED under `unclassified`.
    """
    cutoff = None
    if window_h is not None:
        try:
            from datetime import timedelta
            cutoff = datetime.now(tz=UTC) - timedelta(hours=float(window_h))
        except (TypeError, ValueError):
            cutoff = None
    latest: dict[str, dict[str, Any]] = {}
    for r in graph_rows:
        if isinstance(r, dict) and r.get("id"):
            latest[str(r["id"])] = r
    counts = dict.fromkeys(TEMPERATURES, 0)
    certified = dict.fromkeys(TEMPERATURES, 0)
    sources: dict[str, dict[str, int]] = {t: {} for t in TEMPERATURES}
    unclassified: dict[str, int] = {}
    n_out_of_window = 0
    n_untimed = 0
    for r in latest.values():
        if cutoff is not None:
            stamp = r.get("at") or r.get("ts") or r.get("_t")
            when = None
            if isinstance(stamp, str):
                try:
                    when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                except ValueError:
                    when = None
            if when is None:
                n_untimed += 1
            else:
                if when.tzinfo is None:
                    when = when.replace(tzinfo=UTC)
                if when < cutoff:
                    n_out_of_window += 1
                    continue
        src = str(r.get("source") or "")
        t = temperature_of(src, r.get("kind"))
        if t is None:
            unclassified[src or "(none)"] = unclassified.get(src or "(none)", 0) + 1
            continue
        counts[t] += 1
        sources[t][src] = sources[t].get(src, 0) + 1
        if str(r.get("fate")) == "CERTIFIED":
            certified[t] += 1
    seconds = dict.fromkeys(TEMPERATURES, 0.0)
    legs_costed: dict[str, list[str]] = {t: [] for t in TEMPERATURES}
    legs_uncosted: dict[str, list[str]] = {t: [] for t in TEMPERATURES}
    table = costs if isinstance(costs, dict) else {}
    for t, legs in TEMP_RUNS.items():
        for leg in legs:
            row = table.get(leg)
            if isinstance(row, dict) and int(row.get("runs") or 0) > 0:
                seconds[t] += float(row.get("wall_s") or 0.0)
                legs_costed[t].append(leg)
            else:
                legs_uncosted[t].append(leg)
    shared_basis: list[str] = []
    for leg, temps in TEMP_SHARED_RUNS.items():
        row = table.get(leg)
        if not isinstance(row, dict) or int(row.get("runs") or 0) <= 0:
            for t in temps:
                legs_uncosted[t].append(leg)
            continue
        wall = float(row.get("wall_s") or 0.0)
        denom = sum(counts[t] for t in temps)
        for t in temps:
            frac = (counts[t] / denom) if denom > 0 else 1.0 / len(temps)
            seconds[t] += wall * frac
            legs_costed[t].append(leg)
        shared_basis.append(
            f"{leg}: {wall:.0f}s split across {list(temps)} by "
            + ("their measured proposal counts" if denom > 0 else "an equal share (none of the "
               "three has a proposal in the window, so no split can be measured)"))
    total_props = sum(counts.values())
    total_s = sum(seconds.values())
    ladder = {}
    for t in TEMPERATURES:
        top = sorted(sources[t].items(), key=lambda kv: -kv[1])[:6]
        ladder[t] = {
            "role": TEMPERATURE_ROLE[t],
            "proposals": counts[t],
            "certified": certified[t],
            "proposal_share": round(counts[t] / total_props, 4) if total_props else None,
            "compute_s": round(seconds[t], 1),
            "compute_share": round(seconds[t] / total_s, 4) if total_s > 0 else None,
            "legs_costed": sorted(set(legs_costed[t])),
            "legs_uncosted": sorted(set(legs_uncosted[t])),
            "top_sources": [{"source": s, "n": n} for s, n in top],
            "status": ("RUNNING" if counts[t] > 0 or seconds[t] > 0 else "IDLE"),
            "why": ("" if counts[t] > 0 or seconds[t] > 0 else
                    f"no proposal carried a {t} source and none of "
                    f"{sorted(set(TEMP_RUNS.get(t, ())) | set(TEMP_SHARED_RUNS))} "
                    f"carries a compute row in the window -- idle, which is a measurement"),
        }
    running = [t for t in TEMPERATURES if ladder[t]["status"] == "RUNNING"]
    return {
        "status": "MEASURED" if (total_props or total_s) else "UNMEASURED",
        "window_h": window_h,
        "rows_considered": len(latest),
        "rows_out_of_window": n_out_of_window,
        "rows_without_a_stamp": n_untimed,
        "n_proposals": total_props,
        "compute_s": round(total_s, 1),
        "ladder": ladder,
        "running": running,
        "n_running": len(running),
        "all_six_running": len(running) == len(TEMPERATURES),
        "idle": [t for t in TEMPERATURES if t not in running],
        "shared_leg_basis": shared_basis,
        "unclassified": {"n": sum(unclassified.values()),
                         "sources": [{"source": s, "n": n} for s, n in
                                     sorted(unclassified.items(), key=lambda kv: -kv[1])[:12]],
                         "why": "no entry in SOURCE_TEMPERATURE claims these sources; they are "
                                "counted and named rather than bucketed, so the concurrency "
                                "count cannot be inflated by a stranger"},
        "rule": ("the six discovery temperatures are declared to run concurrently; this counts "
                 "the proposals each produced and the measured seconds each spent, so the claim "
                 "is a count and not an assertion. Compute is the compute ledger's wall seconds "
                 "for TEMP_RUNS, with shared legs split by measured proposals"),
    }


def run(seed: int = 0, write: bool = True,
        variant: str = CONTROLLER_VARIANT) -> dict[str, Any]:
    try:
        from libs.research.hypothesis_graph import Graph
        rows = Graph().rows()
    except Exception:
        rows = []
    marginal = _marginal_by_arm()
    ct, ct_why = _cost_table()
    mc = (measured_cost(ct) if ct is not None else
          {"_why": {"status": "UNMEASURED", "why": ct_why}})
    rcred = realised_credit()
    ev = evidence(rows, marginal, measured=mc, credit=rcred.get("by_arm") or None)
    bc = breadth_credit()
    audit: dict[str, Any] = {}
    shares = allocate({a: v for a, v in ev.items() if a in ARMS}, np.random.default_rng(seed),
                      credit=bc.get("credit"), audit=audit)
    costed = sorted(a for a in ARMS if a in mc)
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "graph_rows": len(rows),
           "controller_variant": variant,
           "explore": EXPLORE, "pseudo_counts": PSEUDO, "shares": shares, "arms": ev,
           "cost_basis": {
               "measured_arms": costed,
               "declared_arms": sorted(a for a in ARMS if a not in mc),
               "source": "libs.ops.compute_ledger.cost_by_run (wall_s, cpu_s per pass of the "
                         "arm's legs in ARM_RUNS), re-expressed on the declared table's scale; "
                         "declared COST elsewhere",
               "why": (mc.get("_why") if isinstance(mc.get("_why"), str) else
                       ("" if costed else "no leg declared in ARM_RUNS carries a compute_ledger "
                                          "row in the window -- every arm is priced from the "
                                          "declared table, and says so in its cost_basis")),
           },
           "groups": audit.get("policy", {}).get("groups"),
           "policy": audit.get("policy"),
           # THE TREE, ITS FLOORS AND THE LADDER. Additive keys: `shares` above is unchanged in
           # shape and meaning, so research_budget.budget_s and every other consumer that reads
           # it keeps reading exactly what it read before.
           "tree": audit.get("tree"),
           "novelty": audit.get("novelty"),
           "temperatures": temperature_ladder(rows, ct, window_h=TEMPERATURE_WINDOW_H),
           "frontier_regret": regret(ev, shares, worth_unmeasured=[a for a in ARMS
                                                                   if a not in marginal]),
           "breadth_credit": bc,
           "realised_credit": rcred,
           # THE JOINT ARMS (Tier-1 D3). `shares` above prices research VERBS; this prices the
           # five-tuple (data axis, factor, model, regime representation, portfolio use) from the
           # co-evolution grid's measured marginal OOS log score. Additive: no existing consumer
           # of `shares` sees any change.
           "joint_arms": joint_shares(),
           # THE PARADIGM VIEW (Tier-1 Q18). The ten search paradigms priced by volume x
           # independence, from the census's own redundancy measure. Additive, like `joint_arms`.
           "paradigms": paradigm_shares(),
           "rule": ("score = E[dElogW] x P(survivor) x breadth_credit / cost, where the credit is "
                    "the marginal dk_eff this arm's output buys the CURRENT book -- dE[log W] is "
                    "proportional to k_eff for a Kelly book, so a duplicate scores below a weaker "
                    "but independent mechanism. Cost is measured seconds where a leg is costed, "
                    "declared units elsewhere (cost_basis per arm). Thompson shares + uniform "
                    f"exploration {EXPLORE:.0%}, with the exploit/adjacent/cold floors of "
                    f"{POLICY.name} enforced on the mixture; consumers: "
                    "deepening_worker.voi_order, daily_cycle proposer budgets")}
    if write:
        BUDGET.parent.mkdir(parents=True, exist_ok=True)
        BUDGET.write_text(json.dumps({"generated_utc": doc["generated_utc"],
                                      "controller_variant": variant,
                                      "shares": shares}, indent=1), "utf-8")
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(doc, indent=1), "utf-8")
    return doc


# ===================================================================== THE JOINT ARMS (D3)
#: THE ARM IS A TUPLE, NOT A VERB (Tier-1 D3). `ARMS` above prices research ACTIONS -- mutate a
#: survivor, screen an external claim. That answers "what shall the desk do next" and never
#: answers "over which (data axis, factor, model, regime representation, portfolio use)", which
#: is the question RD-Agent's factor x model co-evolution actually asks. A joint arm names all
#: five, so the bandit can prefer `residual x state_space` over `session x tree` on measured
#: evidence rather than on which verb happened to be cheap.
#:
#: (name, data_axis, factor tokens, model family, regime representation, portfolio use). The
#: factor tokens are matched against COEVOLUTION.json's `compatibility_matrix.grid` REPRESENTATION
#: keys (which are `+`-joined feature names), and the model family against that grid's model keys.
JOINT_ARMS: tuple[tuple[str, str, tuple[str, ...], str, str, str], ...] = (
    ("crossasset_linear", "cross_asset", ("swap_diff", "log_return"), "linear",
     "unconditional", "diversifier"),
    ("macro_mixture", "macro", ("cot_z", "realised_vol"), "mixture",
     "macro_state", "carry_overlay"),
    ("event_hazard", "event", ("session_participation", "tick_imbalance"), "hazard",
     "event_window", "event_sleeve"),
    ("residual_state_space", "residual", ("ts_rank", "log_return"), "state_space",
     "latent_state", "residual_sleeve"),
    ("session_tree", "session", ("hour", "realised_vol"), "tree",
     "session_state", "intraday_sleeve"),
    ("microstructure_sequence", "microstructure", ("tick_imbalance", "realised_vol"), "sequence",
     "liquidity_state", "execution_overlay"),
)
JOINT_ARM_NAMES: tuple[str, ...] = tuple(a[0] for a in JOINT_ARMS)
#: The co-evolution report the joint arms are priced from. Its `compatibility_matrix.grid` holds
#: the measured OOS net log-score gain per (representation, model) cell -- nats per prediction
#: after the model's own complexity tax, which is the marginal E[log W] this arm earned.
COEVOLUTION_REPORT = DESK / "reports" / "COEVOLUTION.json"
#: Pseudo-count on the joint arms' Beta prior. Smaller than PSEUDO because a joint cell carries
#: far fewer trials than a verb arm and would otherwise never move off the prior.
JOINT_PSEUDO = 4.0
#: The joint arms' own protected floor, the same construction as ARM_FLOOR: exploration is a
#: floor under every arm, never a cap on the arm the evidence likes (L1.50, growth governance).
JOINT_FLOOR = EXPLORE / len(JOINT_ARMS)


def _joint_grid(report: Path | None = None) -> tuple[dict[str, Any], str]:
    """`compatibility_matrix.grid` from COEVOLUTION.json, or ({}, why)."""
    p = report or COEVOLUTION_REPORT
    try:
        doc = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {}, f"{p.name} unreadable ({type(exc).__name__}); joint arms priced from the prior"
    grid = ((doc.get("compatibility_matrix") or {}).get("grid")
            if isinstance(doc.get("compatibility_matrix"), dict) else None)
    if not isinstance(grid, dict) or not grid:
        return {}, f"{p.name} carries no compatibility_matrix.grid; joint arms priced on the prior"
    return grid, ""


def joint_evidence(report: Path | None = None) -> dict[str, dict[str, Any]]:
    """Per joint arm: the measured cells, their pooled net log-score gain and the trials behind it.

    A cell counts for an arm when its representation key contains ANY of the arm's factor tokens
    AND its model key is the arm's model family (or, when the zoo has no such family on this box,
    the arm is UNMEASURED and falls to the prior rather than borrowing another family's number).
    `worth` is the n-weighted mean `net_gain` in nats per prediction -- marginal OOS E[log W] --
    floored at zero for the share draw, because a negative pairing is evidence the arm has not
    earned MORE compute, never evidence it should be starved below its floor.
    """
    grid, why = _joint_grid(report)
    out: dict[str, dict[str, Any]] = {}
    for name, axis, tokens, model, regime, use in JOINT_ARMS:
        num = den = 0.0
        cells = 0
        positive = 0
        for rep, models in grid.items():
            if not isinstance(models, Mapping) or not any(t in str(rep) for t in tokens):
                continue
            cell = models.get(model)
            if not isinstance(cell, Mapping):
                continue
            n = float(cell.get("n") or 0.0)
            gain = float(cell.get("net_gain") or 0.0)
            if n <= 0:
                continue
            num += gain * n
            den += n
            cells += 1
            positive += 1 if gain > 0 else 0
        worth = (num / den) if den > 0 else None
        out[name] = {
            "data_axis": axis, "factors": list(tokens), "model": model,
            "regime_representation": regime, "portfolio_use": use,
            "cells": cells, "trials": int(den), "positive_cells": positive,
            "net_log_score": None if worth is None else round(worth, 6),
            "worth": 0.0 if worth is None else max(0.0, worth),
            "status": "MEASURED" if cells else "UNMEASURED",
            "why": why or (f"{cells} (representation x {model}) cell(s) of the co-evolution grid, "
                           f"{int(den)} predictions pooled"),
        }
    return out


def joint_shares(report: Path | None = None) -> dict[str, Any]:
    """Thompson shares over the joint arms, floored, with the evidence that set them.

    Reward is marginal OOS E[log W] (net log score per prediction, after the model tax), which is
    the item's own objective; an arm with no measured cell keeps the prior and the floor, so a
    region nobody has bred is never priced at zero for having been ignored (L1.28a).
    """
    ev = joint_evidence(report)
    raw: dict[str, float] = {}
    for name, row in ev.items():
        # Beta-style posterior mean on (positive cells + prior) / (cells + prior), scaled by the
        # arm's measured worth so an arm that wins often AND largely outranks one that wins often
        # and barely. Both factors are >= 0 and neither can subtract from another arm's claim.
        rate = (float(row["positive_cells"]) + JOINT_PSEUDO * 0.5) / (
            float(row["cells"]) + JOINT_PSEUDO)
        raw[name] = rate * (1.0 + 100.0 * float(row["worth"]))
    total = sum(raw.values())
    if total <= 0:
        shares_ = {n: 1.0 / len(JOINT_ARMS) for n in JOINT_ARM_NAMES}
    else:
        shares_ = {n: raw[n] / total for n in JOINT_ARM_NAMES}
    # The floor, then renormalise the remainder over what is above it.
    lifted = {n: max(JOINT_FLOOR, v) for n, v in shares_.items()}
    s = sum(lifted.values())
    shares_ = {n: v / s for n, v in lifted.items()}
    n_measured = sum(1 for r in ev.values() if r["status"] == "MEASURED")
    return {
        "shares": {n: round(v, 6) for n, v in shares_.items()},
        "arms": ev, "floor": JOINT_FLOOR, "n_measured": n_measured,
        "status": "MEASURED" if n_measured else "UNMEASURED",
        "rule": ("a joint arm is (data axis, factor, model, regime representation, portfolio "
                 "use); its reward is the n-weighted marginal OOS log score of the co-evolution "
                 "grid cells it spans (nats per prediction after the model tax = marginal "
                 "E[log W]); shares are Thompson-style with a protected floor and are never a "
                 "cap -- an arm below par still runs at JOINT_FLOOR"),
        "consumer": ("desks/mt5/research/factor_model_coevolution.py: `joint_order` REORDERS the "
                     "zoo families it breeds first; it may never widen the option set"),
    }


def joint_order(models: Iterable[str],
                report: Path | None = None) -> tuple[list[str], dict[str, Any]]:
    """Reorder `models` by the joint arms' shares, best first. NEVER widens the option set.

    A family no joint arm names keeps its incumbent position behind the priced ones, so this can
    reorder and can never drop a family the zoo measured as callable on this box.
    """
    opts = [str(m) for m in models]
    doc = joint_shares(report)
    by_model: dict[str, float] = {}
    for name, row in (doc.get("arms") or {}).items():
        by_model[str(row.get("model"))] = max(
            by_model.get(str(row.get("model")), 0.0), float(doc["shares"].get(name, 0.0)))
    ordered = sorted(opts, key=lambda m: (-by_model.get(m, -1.0), opts.index(m)))
    return ordered, {"status": doc["status"], "shares": doc["shares"],
                     "by_model": {k: round(v, 6) for k, v in sorted(by_model.items())},
                     "applied": ordered != opts,
                     "why": "joint arms reorder the zoo; the option set is unchanged"}


# ================================================================= THE PARADIGM VIEW (Q18)
#: The paradigm census: which SEARCH PARADIGM proposed what, and how much of it another paradigm
#: had already proposed (`search_paradigm_census`, hourly leg).
PARADIGM_REPORT = DESK / "reports" / "SEARCH_PARADIGMS.json"
#: Pseudo-count on a paradigm's volume, so one lucky proposal is not a mandate.
PARADIGM_PSEUDO = 5.0
PARADIGM_FLOOR_SHARE = 0.02


def paradigm_shares(report: Path | None = None) -> dict[str, Any]:
    """Shares over SEARCH PARADIGMS, rewarding the ones whose proposals are INDEPENDENT (Q18).

    The desk runs ten-odd paradigms -- symbolic regression, MCTS, GFlowNet, MAP-Elites, Bayesian
    optimisation, causal discovery, residual mining, literature extraction -- on different clocks,
    and `ARMS` above prices research VERBS, not paradigms. `search_paradigm_census` measures what
    each one proposed and `duplicated_share`: the share of its cells some other paradigm also
    proposed. Independence is 1 - that, and a paradigm's claim on the budget is its volume x its
    independence: two paradigms that keep finding each other's cells are one paradigm with two
    bills. A paradigm that proposed nothing is UNMEASURED and keeps the floor, because "produced
    nothing this window" is a measurement about the window, not about the paradigm (L1.28a).
    """
    p = report or PARADIGM_REPORT
    try:
        doc = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {"status": "UNMEASURED", "shares": {}, "arms": {},
                "why": f"{p.name} unreadable ({type(exc).__name__}); no paradigm can be priced"}
    rows = doc.get("paradigms")
    if not isinstance(rows, list) or not rows:
        return {"status": "UNMEASURED", "shares": {}, "arms": {},
                "why": f"{p.name} carries no paradigm rows"}
    arms: dict[str, dict[str, Any]] = {}
    raw: dict[str, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("paradigm") or "")
        if not name:
            continue
        proposals = float(row.get("proposals") or 0.0)
        dup = row.get("duplicated_share")
        independence = 1.0 - float(dup) if isinstance(dup, (int, float)) else None
        arms[name] = {
            "legs": list(row.get("legs") or ()), "proposals": int(proposals),
            "distinct_cells": int(row.get("distinct_cells") or 0),
            "duplicated_share": dup,
            "independence": None if independence is None else round(independence, 4),
            "status": "MEASURED" if proposals > 0 else "UNMEASURED",
            "why": str(row.get("why") or "")[:240],
        }
        ind = 1.0 if independence is None else max(0.0, independence)
        raw[name] = (proposals + PARADIGM_PSEUDO) * ind
    total = sum(raw.values())
    shares_ = ({n: v / total for n, v in raw.items()} if total > 0
               else {n: 1.0 / max(1, len(raw)) for n in raw})
    lifted = {n: max(PARADIGM_FLOOR_SHARE, v) for n, v in shares_.items()}
    s = sum(lifted.values()) or 1.0
    shares_ = {n: v / s for n, v in lifted.items()}
    n_measured = sum(1 for r in arms.values() if r["status"] == "MEASURED")
    return {
        "status": "MEASURED" if n_measured else "UNMEASURED",
        "shares": {n: round(v, 6) for n, v in sorted(shares_.items())},
        "arms": arms, "n_measured": n_measured, "floor": PARADIGM_FLOOR_SHARE,
        "redundancy": doc.get("redundancy"),
        "rule": ("share = (proposals + prior) x (1 - duplicated_share), normalised, with a floor "
                 "-- the budget rewards the paradigms whose survivors are INDEPENDENT, and the "
                 "floor means a quiet window never prices a paradigm at zero"),
        "consumer": ("desks/mt5/research/research_budget.py `_paradigm_factor` -> the leg's "
                     "seconds (one-sided: above par only)"),
    }


_CACHE: dict[str, Any] = {"mtime": None, "shares": None}


def shares() -> dict[str, float]:
    """The current budget shares, uniform when none has been written. Cached on mtime."""
    try:
        m = BUDGET.stat().st_mtime
        if _CACHE["mtime"] != m:
            _CACHE["shares"] = json.loads(BUDGET.read_text("utf-8")).get("shares") or {}
            _CACHE["mtime"] = m
        s = _CACHE["shares"] or {}
    except (OSError, ValueError):
        s = {}
    return {a: float(s.get(a, 1.0 / len(ARMS))) for a in ARMS}


def arm_weight(source: str | None, kind: str | None = None) -> float:
    """Share of the arm this task belongs to, scaled so the uniform budget is 1.0."""
    return shares()[arm_of(source, kind)] * len(ARMS)
