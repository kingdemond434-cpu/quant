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
             measured: dict[str, dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
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
        mc = (measured or {}).get(a)
        if isinstance(mc, dict) and isinstance(mc.get("cost"), (int, float)) and mc["cost"] > 0:
            cost, basis = float(mc["cost"]), str(mc.get("basis") or "measured")
        else:
            cost, basis = float(sum(COST[a])), _declared_basis(a)
        out[a] = {**c, "alpha": round(alpha, 3), "beta": round(beta, 3),
                  "p_survivor": round(alpha / (alpha + beta), 4), "worth": worth,
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


def allocate(ev: dict[str, dict[str, Any]], rng: np.random.Generator, *, draws: int = 400,
             explore: float = EXPLORE,
             credit: dict[str, float] | None = None,
             policy: dict[str, Any] | None = None,
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
    Its group floors are enforced on the evidence mixture BEFORE the uniform exploration share
    is added, so the per-arm EXPLORE floor is never eroded by a lift and, because the uniform
    share's own group split (6/11, 3/11, 2/11) clears every declared floor, the final shares
    clear them too. `audit`, when a dict, receives the group check for publication.
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
    mixture, check = enforce_floors(mixture, allocation_policy() if policy is None else policy)
    share = {a: (1.0 - explore) * mixture[a] + explore / len(arms) for a in arms}
    if audit is not None:
        check["groups"] = group_shares(share)
        check["groups_mixture"] = group_shares(mixture)
        audit["policy"] = check
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


def run(seed: int = 0, write: bool = True,
        variant: str = CONTROLLER_VARIANT) -> dict[str, Any]:
    try:
        from libs.research.hypothesis_graph import Graph
        rows = Graph().rows()
    except Exception:
        rows = []
    marginal = _marginal_by_arm()
    mc = measured_cost()
    ev = evidence(rows, marginal, measured=mc)
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
           "frontier_regret": regret(ev, shares, worth_unmeasured=[a for a in ARMS
                                                                   if a not in marginal]),
           "breadth_credit": bc,
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
