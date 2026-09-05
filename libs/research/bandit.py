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
sleeves that came from the arm, and 1.0 where it has certified nothing yet. Costs are declared
units, not measured seconds: a declared table is auditable, a timer is not.

THOMPSON SAMPLING gives each arm the probability that it is the best arm, and EXPLORE of the
budget is spread uniformly on top -- the machine may not become trapped by its own history.
The output is a budget file every consumer reads: the deepening worker weights its VOI order by
it, the daily cycle scales each proposer's time budget by it.
"""
from __future__ import annotations

import json
import math
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
BUDGET = DESK / "data" / "research_budget.json"
REPORT = DESK / "reports" / "RESEARCH_BANDIT.json"

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
}
KIND_ARM: dict[str, str] = {
    "coverage_gap": "conditional_state_edge", "dead_phase": "conditional_state_edge",
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


def arm_of(source: str | None, kind: str | None = None) -> str:
    if kind and str(kind) in KIND_ARM:
        return KIND_ARM[str(kind)]
    src = str(source or "").split(":")[0]
    return SOURCE_ARM.get(src, "alt_data_hypothesis")


def evidence(graph_rows: Iterable[dict[str, Any]],
             marginal_by_source: dict[str, float] | None = None) -> dict[str, dict[str, Any]]:
    """Per-arm counts and the Beta posterior of certification, shrunk to the pooled rate."""
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
        cost = float(sum(COST[a]))
        out[a] = {**c, "alpha": round(alpha, 3), "beta": round(beta, 3),
                  "p_survivor": round(alpha / (alpha + beta), 4), "worth": worth,
                  "cost": cost, "score_mean": round(worth * alpha / (alpha + beta) / cost, 5)}
    out["_pooled_rate"] = round(pooled, 5)
    return out


def allocate(ev: dict[str, dict[str, Any]], rng: np.random.Generator, *, draws: int = 400,
             explore: float = EXPLORE) -> dict[str, float]:
    """Thompson shares: P(arm is best) under sampled survival rates, plus the exploration floor."""
    arms = [a for a in ARMS if a in ev]
    ratio = {a: ev[a]["worth"] / ev[a]["cost"] for a in arms}
    pooled_ratio = float(np.mean(list(ratio.values()))) if ratio else 1.0
    for a in arms:
        if ev[a]["failed"] + ev[a]["certified"] < MIN_JUDGED:
            ratio[a] = min(ratio[a], pooled_ratio)              # cold arm: no price advantage
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
    share = (1.0 - explore) * (0.5 * p_best + 0.5 * p_mean) + explore / len(arms)
    return {a: round(float(x), 4) for a, x in zip(arms, share, strict=True)}


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


def run(seed: int = 0, write: bool = True) -> dict[str, Any]:
    try:
        from libs.research.hypothesis_graph import Graph
        rows = Graph().rows()
    except Exception:
        rows = []
    ev = evidence(rows, _marginal_by_arm())
    shares = allocate({a: v for a, v in ev.items() if a in ARMS}, np.random.default_rng(seed))
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "graph_rows": len(rows),
           "explore": EXPLORE, "pseudo_counts": PSEUDO, "shares": shares, "arms": ev,
           "rule": ("score = E[dElogW] x P(survivor) / cost; Thompson shares + uniform "
                    f"exploration {EXPLORE:.0%}; consumers: deepening_worker.voi_order, "
                    "daily_cycle proposer budgets")}
    if write:
        BUDGET.parent.mkdir(parents=True, exist_ok=True)
        BUDGET.write_text(json.dumps({"generated_utc": doc["generated_utc"],
                                      "shares": shares}, indent=1), "utf-8")
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(doc, indent=1), "utf-8")
    return doc


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
