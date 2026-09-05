"""NINE SEARCH POPULATIONS OVER ONE GRAMMAR, RUN TOGETHER UNDER ONE BUDGET, EACH SCORED BY YIELD.

WHY MORE THAN ONE SEARCH. `libs.research.generators` offers three ways to draw a tree -- uniform,
GFlowNet, symbolic regression -- and `alpha_evolution` picks one per individual. Three samplers
over one grammar is still ONE search: they all start from noise and hill-climb on the same
signal, so they find the same kind of alpha and fail on the same kind. The populations here fail
differently on purpose, and that is the whole design:

    gp                 NSGA-II over the fitness COMPONENTS, not their weighted sum, so the
                       candidate that is best on the tail and worst on cost survives selection
                       instead of being averaged away by whichever exchange rate is in force.
    gflownet           samples in proportion to reward; finds MOTIFS the history rewarded.
    symreg             hill-climbs toward a supervised target; finds FIT.
    program_synthesis  bottom-up enumeration of the typed grammar to a depth bound, deduped by
                       subtree hash: the only population that is EXHAUSTIVE at small depth, so
                       nothing simple is missed because no sampler happened to draw it.
    bayesian           a TPE surrogate over expression FEATURES chooses which children are worth
                       evaluating at all -- the population that spends the evaluation budget
                       rather than the sampling budget.
    zoo_mutation       the public alpha zoos (Alpha158-style price/volume features, WorldQuant
                       101-style rank/ts operators, GTJA-191-style composites) as GENETIC
                       MATERIAL: every template is reimplemented as a typed tree of THIS grammar
                       and emitted only through a named mutation axis. The zoo is never traded.
    graveyard_derived  mutates what DIED, along the axis its recorded fate names.
    causal_derived     builds from the admitted edges of the world causal graph.
    claims_derived     builds from mined mechanism claims by their declared mechanism class.

ONE CACHE, SHARED. Every population evaluates through the same `alpha_grammar.SubtreeCache`, so
a subtree one population paid for is free for the other eight. Trees drawn from one grammar
share their lower halves overwhelmingly, which is exactly what makes the shared unit of work the
subtree rather than the expression.

YIELD IS REPORTED, NEVER SELF-SCORED. Each population reports proposed / unique-by-hash /
well-formed / passed-the-cheap-falsifier / donated. Nothing here reads those numbers back into
its own weights: the ledger that sets weights lives outside, so a population cannot promote
itself.

THE ZOO IS GENETIC MATERIAL, NOT A LIBRARY. No formula from any public set is proposed as
written. Each template below is a SHAPE the desk re-derived in its own operators, on its own
terminals, and it reaches the gauntlet only after a mutation has changed its instrument,
horizon, lag, normalisation, state, session, cross-asset leg, or residualisation. Nothing is
copied: there is no third-party code in this module and no formula is executed as published.

NOTHING HERE HAS AUTHORITY. A population proposes; the fitness ranks; the gauntlet certifies.
"""
from __future__ import annotations

import json
import math
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from libs.research import alpha_grammar as ag
from libs.research import generators as gen
from libs.research.alpha_fitness import FitnessTerms, nsga2_order

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
#: The three ledgers the derived populations mine. Every one is read DEFENSIVELY -- absent,
#: truncated, half-written by a sibling organ, or carrying a schema this module has not seen --
#: because they are written by other engines on their own clocks and a search that dies when a
#: sibling is mid-write is a search that runs only when nothing else does.
HYPOTHESIS_GRAPH = DESK / "data" / "hypothesis_graph.jsonl"
CAUSAL_GRAPH = DESK / "data" / "world_causal_graph.json"
DEEP_FOREST_CLAIMS = DESK / "data" / "deep_forest_claims.jsonl"
#: Rows read from the tail of a ledger. The newest fates and claims are the informative ones and
#: the graveyard is 30k lines: reading it whole every hour would cost more than the search.
LEDGER_TAIL = 4000
#: Enumeration bounds for `program_synthesis`. Depth 2 over the full operator set is already
#: hundreds of thousands of trees, so the pool per level is capped and the cap is declared.
SYNTH_MAX_DEPTH = 2
SYNTH_POOL = 900
#: TPE split: the share of the history treated as the GOOD set whose feature density is chased.
TPE_GAMMA = 0.25
TPE_CANDIDATES = 200
TPE_PRIOR = 1.0

Expr = Any
History = Sequence[tuple[Any, float]]


# --------------------------------------------------------------------------- the context
@dataclass
class SearchContext:
    """Everything a population needs, and nothing it may decide.

    A population reads this and returns expressions. It never screens, never scores, never
    donates and never writes a file -- so a broken population costs its share of one budget and
    can do nothing else.
    """

    rng: np.random.Generator
    frames: dict[str, pd.Series] = field(default_factory=dict)
    ret: pd.Series | None = None
    symbol: str = ""
    allow_drivers: bool = True
    max_depth: int = 3
    cache: ag.SubtreeCache | None = None
    #: (expression, scalar fitness) rows the samplers learn from.
    history: History = ()
    #: (expression, full term vector) rows the multi-objective populations select over.
    scored: Sequence[tuple[Expr, FitnessTerms]] = ()
    #: Trees worth breeding from: the elite, plus the canon.
    seeds: Sequence[Expr] = ()
    #: The cheap falsifier -- one call, one verdict, no side effects. None means "not screened
    #: here", and the yield then says `passed=proposed` rather than pretending to have screened.
    falsifier: Callable[[Expr], bool] | None = None
    #: Terminals a population may draw. Defaults to whatever the frames actually carry.
    terminals: tuple[str, ...] = ()
    #: Driver roles present in the frames, for the cross-asset mutation axis.
    drivers: tuple[str, ...] = ()
    #: Population name -> what it wants said about a draw the counters cannot express ("the
    #: graveyard named no cause", "the causal graph has no admitted edge on a driver I have").
    #: `run` copies these into the yield ledger, so an empty population is never just a zero.
    notes: dict[str, str] = field(default_factory=dict)
    #: Ledger paths, overridable so a test never reads the desk's real ledgers.
    hypothesis_graph: Path = HYPOTHESIS_GRAPH
    causal_graph: Path = CAUSAL_GRAPH
    claims: Path = DEEP_FOREST_CLAIMS

    def __post_init__(self) -> None:
        if not self.terminals:
            self.terminals = ag.available_terminals(self.frames, self.allow_drivers)
        if not self.drivers:
            self.drivers = tuple(t for t in ag.DRIVER_TERMINALS if t in self.terminals)
        # ALLOW-DRIVERS FOLLOWS THE FRAMES, not the caller's optimism. A context that permits
        # driver terminals it has no series for lets every sampler spend its budget on trees
        # that evaluate to NaN -- the flag and the pool must agree, and the pool is the fact.
        self.allow_drivers = bool(self.allow_drivers and self.drivers)

    def memo(self) -> Any:
        """The shared subtree memo for these bars, or a private dict when no cache was given."""
        if self.cache is None:
            return {}
        return self.cache.scope(self.symbol, self.frames)

    def evaluate(self, expr: Expr) -> pd.Series:
        """Evaluate through the SHARED cache, so every population fills one table."""
        return ag.evaluate(expr, self.frames, self.memo())


@dataclass
class PopulationYield:
    """What one population's share of the budget bought. Counted, never self-scored."""

    name: str
    proposed: int = 0
    unique: int = 0
    well_formed: int = 0
    passed: int = 0
    donated: int = 0
    seconds: float = 0.0
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"population": self.name, "proposed": self.proposed, "unique": self.unique,
                "well_formed": self.well_formed, "passed": self.passed,
                "donated": self.donated, "seconds": round(self.seconds, 2), "note": self.note}


@dataclass
class SearchResult:
    """Everything the run produced: the distinct trees, who made each, and the yield ledger."""

    proposals: list[tuple[Expr, str]] = field(default_factory=list)
    yields: dict[str, PopulationYield] = field(default_factory=dict)
    cache_stats: dict[str, Any] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)

    def yield_rows(self) -> list[dict[str, Any]]:
        return [self.yields[k].as_dict() for k in sorted(self.yields)]

    def yield_line(self) -> dict[str, int]:
        """The one-line counter set for the hourly organ's YIELD convention."""
        return {"proposals": len(self.proposals),
                "unique": sum(y.unique for y in self.yields.values()),
                "passed": sum(y.passed for y in self.yields.values()),
                "populations": len(self.yields)}


Population = Callable[[SearchContext, int], list[Expr]]


# --------------------------------------------------------------------------- gp (NSGA-II)
def gp(ctx: SearchContext, n: int) -> list[Expr]:
    """Genetic programming with NSGA-II selection over the FITNESS COMPONENTS.

    WHY MULTI-OBJECTIVE. A scalar fitness is an exchange rate, and selecting on it deletes every
    candidate that is extraordinary on one term and ordinary on the rest -- which is precisely
    the candidate the book is missing (the tail diversifier is usually a poor standalone Sharpe).
    Non-dominated sorting keeps the whole Pareto front, and crowding distance keeps the lonely
    members of it, so the parents are diverse in the terms rather than in their sum.

    Falls back to the seeds when nothing has been scored yet: generation zero has no front.
    """
    parents = _nsga_parents(ctx)
    if not parents:
        parents = [s for s in ctx.seeds if ag.is_valid(s, ctx.allow_drivers)]
    if not parents:
        return [ag.random_expr(ctx.rng, ctx.max_depth, ctx.allow_drivers,
                               terminals=ctx.terminals) for _ in range(n)]
    out: list[Expr] = []
    for _ in range(n):
        a = parents[int(ctx.rng.integers(len(parents)))]
        if len(parents) > 1 and ctx.rng.random() < 0.5:
            b = parents[int(ctx.rng.integers(len(parents)))]
            out.append(ag.crossover(a, b, ctx.rng, ctx.allow_drivers))
        else:
            out.append(ag.mutate(a, ctx.rng, ctx.allow_drivers, terminals=ctx.terminals))
    return out


def _nsga_parents(ctx: SearchContext, keep: int = 12) -> list[Expr]:
    rows = [(e, t) for e, t in ctx.scored if isinstance(t, FitnessTerms)]
    if not rows:
        return []
    order = nsga2_order([t for _e, t in rows])
    return [rows[i][0] for i in order[:keep]]


# --------------------------------------------------------------------------- learned samplers
def gflownet(ctx: SearchContext, n: int) -> list[Expr]:
    """The trained flow network, sampling in proportion to what the history rewarded."""
    net = gen.GFlowNet(max_depth=ctx.max_depth).fit(ctx.history, allow_drivers=ctx.allow_drivers)
    return net.sample_batch(ctx.rng, n, ctx.max_depth, ctx.allow_drivers,
                            terminals=ctx.terminals)


def symreg(ctx: SearchContext, n: int) -> list[Expr]:
    """Symbolic regression toward the NEXT bar's return, restarted per individual.

    The target is forward of the expression's own causal inputs -- a supervised label, not a
    leak -- and the fit slice is the first 70%, with the holdout error reported by the generator
    and never consulted for a choice.
    """
    if ctx.ret is None or not ctx.frames:
        return [ag.random_expr(ctx.rng, ctx.max_depth, ctx.allow_drivers,
                               terminals=ctx.terminals) for _ in range(n)]
    target = pd.Series(ctx.ret).shift(-1)
    return [gen.symbolic_regression(ctx.rng, ctx.frames, target,
                                    allow_drivers=ctx.allow_drivers, max_depth=ctx.max_depth,
                                    terminals=ctx.terminals)
            for _ in range(n)]


# --------------------------------------------------------------------------- program synthesis
def program_synthesis(ctx: SearchContext, n: int) -> list[Expr]:
    """Bottom-up ENUMERATION of the typed grammar to a depth bound, deduped by subtree hash.

    The only exhaustive population. Every other one samples, so a simple tree nobody happened to
    draw is a tree the desk never tried; this builds level 0 (terminals), then every operator
    over what level 0 produced, then every operator over that -- keeping only what the
    production screen accepts and only one representative per structural hash.

    THE DEDUPE IS THE POINT AND IT IS WHY IT FITS IN AN HOUR. Enumeration without it re-derives
    the same subtree under every parent; with it the pool at each level is the set of DISTINCT
    programs, which is what `SYNTH_POOL` caps. Trees already in the history are skipped: the
    enumerator's job is to find what the samplers did not.
    """
    seen: set[str] = {ag.subtree_hash(e) for e, _f in ctx.history}
    windows = tuple(ag.WINDOWS)
    level: list[Expr] = list(ctx.terminals)
    pool: list[Expr] = []
    for _depth in range(max(1, min(int(ctx.max_depth), SYNTH_MAX_DEPTH))):
        nxt: list[Expr] = []
        for child in level:
            for op in ag.UNARY:
                _add(nxt, seen, [op, child], ctx)
            for op in ag.WINDOWED:
                for w in windows:
                    _add(nxt, seen, [op, child, w], ctx)
            if len(nxt) >= SYNTH_POOL:
                break
        for a in level:
            if len(nxt) >= SYNTH_POOL:
                break
            for b in level:
                for op in ag.BINARY:
                    _add(nxt, seen, [op, a, b], ctx)
                for op in ag.BINARY_WINDOWED:
                    for w in windows[::3]:
                        _add(nxt, seen, [op, a, b, w], ctx)
        pool.extend(nxt)
        level = nxt[:SYNTH_POOL]
        if not level:
            break
    if not pool:
        return []
    idx = ctx.rng.permutation(len(pool))[:n]
    return [pool[int(i)] for i in idx]


def _add(out: list[Expr], seen: set[str], expr: Expr, ctx: SearchContext) -> None:
    if len(out) >= SYNTH_POOL or not ag.is_valid(expr, ctx.allow_drivers, ctx.terminals):
        return
    h = ag.subtree_hash(expr)
    if h in seen:
        return
    seen.add(h)
    out.append(expr)


# --------------------------------------------------------------------------- bayesian (TPE)
def bayesian(ctx: SearchContext, n: int) -> list[Expr]:
    """A TPE surrogate over expression FEATURES, choosing which children are worth evaluating.

    Tree-structured Parzen estimation, on a feature space rather than a hyperparameter box: the
    history is split at `TPE_GAMMA` into a good set l(x) and the rest g(x), each feature (an
    operator present, a terminal present, a depth, a window band) gets a Laplace-smoothed
    Bernoulli density under both, and a candidate scores sum log l/g -- the ranking TPE's
    expected improvement reduces to. The population then DRAWS many cheap candidates and
    evaluates only the top `n`.

    WHAT THIS BUYS THAT A SAMPLER DOES NOT. Every other population spends its budget on drawing;
    this one spends it on choosing. With no history it is a uniform draw and says so -- a
    surrogate fitted on nothing is a prior, not a model.
    """
    rows = [(e, float(f)) for e, f in ctx.history
            if isinstance(f, (int, float)) and math.isfinite(float(f))]
    draws = [ag.random_expr(ctx.rng, ctx.max_depth, ctx.allow_drivers, terminals=ctx.terminals)
             for _ in range(max(n, TPE_CANDIDATES))]
    if len(rows) < 8:
        return draws[:n]
    fits = np.array([f for _e, f in rows], dtype=float)
    cut = float(np.quantile(fits, 1.0 - TPE_GAMMA))
    good = [features(e) for e, f in rows if f >= cut]
    bad = [features(e) for e, f in rows if f < cut]
    if not good or not bad:
        return draws[:n]
    lg, gg = _density(good), _density(bad)
    ranked = sorted(draws, key=lambda e: -_tpe_score(features(e), lg, gg, len(good), len(bad)))
    return ranked[:n]


def features(expr: Expr) -> frozenset[str]:
    """The surrogate's view of a tree: which operators, terminals, depth and window band it has.

    Deliberately coarse. A feature the history can only have seen once is a feature the
    surrogate would fit to one lucky tree, so the space is the vocabulary plus two structural
    bands -- things a few dozen observations can actually estimate.
    """
    out: set[str] = set()

    def _walk(x: Expr) -> None:
        if isinstance(x, str):
            out.add(f"t:{x}")
            return
        if not isinstance(x, (list, tuple)) or not x:
            return
        out.add(f"op:{x[0]}")
        for c in x[1:]:
            if isinstance(c, int):
                out.add("w:long" if c >= 48 else ("w:mid" if c >= 12 else "w:short"))
            elif isinstance(c, (str, list, tuple)):
                _walk(c)
    _walk(expr)
    out.add(f"d:{min(ag.depth(expr), 4)}")
    out.add("cx:big" if ag.complexity(expr) > 8 else "cx:small")
    return frozenset(out)


def _density(sets: Sequence[frozenset[str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for s in sets:
        for f in s:
            counts[f] = counts.get(f, 0) + 1
    return counts


def _tpe_score(feat: frozenset[str], good: dict[str, int], bad: dict[str, int],
               n_good: int, n_bad: int) -> float:
    total = 0.0
    for f in feat:
        p_good = (good.get(f, 0) + TPE_PRIOR) / (n_good + 2 * TPE_PRIOR)
        p_bad = (bad.get(f, 0) + TPE_PRIOR) / (n_bad + 2 * TPE_PRIOR)
        total += math.log(p_good / p_bad)
    return total


# --------------------------------------------------------------------------- the alpha zoos
#: PUBLIC ALPHA FAMILIES AS SHAPES, REIMPLEMENTED IN THIS GRAMMAR'S OWN OPERATORS.
#:
#: What transfers from Alpha158, WorldQuant 101 and GTJA 191 to a gold/FX/index desk is not a
#: single formula -- those were fitted to a Chinese equity cross-section a decade ago and the
#: desk has no cross-section -- it is the SHAPES: a normalised momentum, a range position, a
#: price-volume co-movement, a decayed reversal, a rank of a rank. Each entry below is that
#: shape written in this grammar, on this desk's terminals, and typed by this desk's algebra.
#: None is proposed as written: `zoo_mutation` emits a template only after a named mutation.
ZOO_TEMPLATES: dict[str, dict[str, Any]] = {
    # Alpha158-style price/volume features: normalised location, normalised change, activity.
    "a158_close_position": {"family": "alpha158", "expr": ["zscore", "close", 24],
                            "shape": "where price sits in its own recent distribution"},
    "a158_range_position": {"family": "alpha158", "expr": ["div", ["sub", "close", ["min",
                            "low", 24]], ["sub", ["max", "high", 24], ["min", "low", 24]]],
                            "shape": "position inside the recent high-low range"},
    "a158_return_decay": {"family": "alpha158", "expr": ["decay", "ret", 12],
                          "shape": "linearly decayed recent return"},
    "a158_activity_ratio": {"family": "alpha158",
                            "expr": ["div", "activity", ["mean", "activity", 24]],
                            "shape": "this bar's activity against its own normal"},
    "a158_vol_ratio": {"family": "alpha158", "expr": ["div", "vol", ["mean", "vol", 120]],
                       "shape": "short volatility against long volatility"},
    # WorldQuant-101-style rank / time-series operators. The published set ranks
    # CROSS-SECTIONALLY; the desk has one instrument per cell, so the rank is over the series'
    # own history -- the same question asked of time instead of of peers.
    "wq_ts_rank_return": {"family": "wq101", "expr": ["ts_rank", "ret", 48],
                          "shape": "rank of today's return in its own recent history"},
    "wq_corr_price_volume": {"family": "wq101", "expr": ["corr", "close", "activity", 24],
                             "shape": "price-volume co-movement"},
    "wq_neg_delta_close": {"family": "wq101", "expr": ["neg", ["delta", "close", 5]],
                           "shape": "short-horizon reversal"},
    "wq_scaled_range": {"family": "wq101", "expr": ["scale", "range", 48],
                        "shape": "this bar's range as a share of the window's total"},
    "wq_group_rank_state": {"family": "wq101",
                            "expr": ["group_rank", "ret", "vol", 48],
                            "shape": "rank of the return among bars in the same volatility state"},
    # GTJA-191-style composites: signed strength, decayed extremeness, bars since an extreme.
    "gtja_signed_strength": {"family": "gtja191",
                             "expr": ["mul", ["sign", ["delta", "close", 5]],
                                      ["ts_rank", "range", 24]],
                             "shape": "direction of the move times how big the bar was"},
    "gtja_since_high": {"family": "gtja191", "expr": ["bars_since_max", "high", 120],
                        "shape": "how long since the last high"},
    "gtja_decayed_rank": {"family": "gtja191", "expr": ["decay", ["ts_rank", "close", 48], 8],
                          "shape": "a smoothed rank of price"},
    "gtja_residual_to_driver": {"family": "gtja191",
                                "expr": ["residual", "close", "usd", 120],
                                "shape": "the part of price the driver does not explain"},
}
#: THE MUTATION AXES. A template reaches the gauntlet only through one of these, so what is
#: tried is always the desk's variation of a public shape and never the public shape itself.
MUTATION_AXES: tuple[str, ...] = ("instrument", "horizon", "lag", "normalisation", "state",
                                  "session", "cross_asset", "residualisation", "entry_exit")


def zoo_mutation(ctx: SearchContext, n: int) -> list[Expr]:
    """One mutated public-zoo shape per draw, along one NAMED axis. Never the shape as written.

    `_zoo_axis` is what makes this a population rather than a copy: the axis says what was
    changed and the recorded generator says which template it was changed from, so a survivor's
    lineage reads "GTJA-style signed strength, horizon axis" rather than "alpha 47".
    """
    names = [k for k, v in ZOO_TEMPLATES.items()
             if ag.is_valid(v["expr"], ctx.allow_drivers, ctx.terminals)]
    if not names:
        return []
    out: list[Expr] = []
    for _ in range(n):
        tpl = ZOO_TEMPLATES[names[int(ctx.rng.integers(len(names)))]]
        axis = MUTATION_AXES[int(ctx.rng.integers(len(MUTATION_AXES)))]
        cand = _zoo_axis(tpl["expr"], axis, ctx)
        if ag.is_valid(cand, ctx.allow_drivers, ctx.terminals) and ag.key(cand) != ag.key(
                tpl["expr"]):
            out.append(cand)
    return out


def _zoo_axis(expr: Expr, axis: str, ctx: SearchContext) -> Expr:
    """Apply ONE named mutation axis to a template. Unknown axes fall to a structural mutation."""
    rng = ctx.rng
    if axis == "horizon":
        return _rewindow(expr, rng, scale=float(rng.choice([0.25, 0.5, 2.0, 4.0])))
    if axis == "lag":
        return ["delay", expr, int(rng.choice(ag.WINDOWS[:4]))]
    if axis == "normalisation":
        op = str(rng.choice(["zscore", "ts_rank", "scale"]))
        return [op, expr, int(rng.choice(ag.WINDOWS[3:]))]
    if axis == "state":
        gate: Expr = ["sign", ["delta", "vol" if "vol" in ctx.terminals else "range",
                                int(rng.choice(ag.WINDOWS[2:6]))]]
        return ["trade_when", gate, expr]
    if axis == "session":
        # The grammar has no clock terminal, so "session" is expressed as the desk expresses it
        # elsewhere: condition on the ACTIVITY regime, which is what a session IS on H1 bars.
        gate = ["zscore", "activity" if "activity" in ctx.terminals else "range",
                int(rng.choice(ag.WINDOWS[4:]))]
        return ["trade_when", gate, expr]
    if axis == "cross_asset" and ctx.drivers:
        drv = str(rng.choice(list(ctx.drivers)))
        return ["corr", expr, drv, int(rng.choice(ag.WINDOWS[4:]))]
    if axis == "residualisation" and ctx.drivers:
        drv = str(rng.choice(list(ctx.drivers)))
        return ["residual", expr, drv, int(rng.choice(ag.WINDOWS[5:]))]
    if axis == "entry_exit":
        return ["group_zscore", expr, "vol" if "vol" in ctx.terminals else "range",
                int(rng.choice(ag.WINDOWS[4:]))]
    if axis == "instrument":
        # The instrument axis is the SWEEP's, not the tree's: the same shape on another symbol is
        # a different cell, and `alpha_evolution` runs one population per symbol. Inside one
        # symbol the honest reading is "swap the price leg", which is what this does.
        return ag.mutate(expr, rng, ctx.allow_drivers, terminals=ctx.terminals)
    return ag.mutate(expr, rng, ctx.allow_drivers, terminals=ctx.terminals)


def _rewindow(expr: Expr, rng: np.random.Generator, scale: float) -> Expr:
    """Every window in the tree scaled and snapped back onto the grammar's own window ladder."""
    if isinstance(expr, str):
        return expr
    out = [expr[0]]
    for c in expr[1:]:
        if isinstance(c, int):
            target = float(c) * scale
            out.append(min(ag.WINDOWS, key=lambda w: abs(w - target)))
        elif isinstance(c, (str, list, tuple)):
            out.append(_rewindow(c, rng, scale))
        else:
            out.append(c)
    return out


# --------------------------------------------------------------------------- derived populations
#: A recorded fate -> the mutation axis that ATTACKS it. This is the whole value of a graveyard:
#: a cell that died of cost is not re-tried at the same turnover, and one that died of
#: instability is not re-tried on the same window.
FATE_TO_AXIS: dict[str, str] = {
    "cost": "horizon", "net": "horizon", "turnover": "state", "spread": "session",
    "unstable": "horizon", "stability": "horizon", "regime": "state", "state": "state",
    "leak": "lag", "lookahead": "lag", "overlap": "lag",
    "correlat": "residualisation", "crowd": "residualisation", "redundan": "cross_asset",
    "deflat": "normalisation", "multiplicity": "normalisation", "trials": "normalisation",
    "capacity": "session", "liquidity": "session",
}


def graveyard_derived(ctx: SearchContext, n: int) -> list[Expr]:
    """Mutate what DIED, along the axis its recorded reason names.

    A fate with no stated reason is not material: "REJECTED" alone says the desk tried something
    and does not say what to try instead, and mutating on it would be mutating on noise wearing
    the word failure. Only rows whose `why` names a cause the desk knows how to attack are used,
    and the axis is chosen by that cause rather than at random.
    """
    reasons, dead, named = _fates(ctx.hypothesis_graph)
    seeds = [s for s in (ctx.seeds or tuple(ag.CANON.values()))
             if ag.is_valid(s, ctx.allow_drivers, ctx.terminals)]
    if not reasons or not seeds:
        ctx.notes["graveyard_derived"] = (
            f"{dead} dead rows, {named} with a cause this desk knows how to attack: "
            "a fate recorded without a cause is not genetic material")
        return []
    ctx.notes["graveyard_derived"] = f"{named} of {dead} dead rows named an attackable cause"
    out: list[Expr] = []
    for _ in range(n):
        axis = reasons[int(ctx.rng.integers(len(reasons)))]
        seed = seeds[int(ctx.rng.integers(len(seeds)))]
        cand = _zoo_axis(seed, axis, ctx)
        if ag.is_valid(cand, ctx.allow_drivers, ctx.terminals):
            out.append(cand)
    return out


def _fates(path: Path) -> tuple[list[str], int, int]:
    """Mutation axes named by the graveyard's stated reasons, and how many rows named one."""
    axes: list[str] = []
    dead = 0
    for row in _jsonl_tail(path, LEDGER_TAIL):
        if str(row.get("fate") or "").upper() not in ("FAILED", "RETIRED", "KILLED"):
            continue
        dead += 1
        why = str(row.get("why") or "").lower()
        for needle, axis in FATE_TO_AXIS.items():
            if needle in why:
                axes.append(axis)
                break
    return axes, dead, len(axes)


def causal_derived(ctx: SearchContext, n: int) -> list[Expr]:
    """Build from the ADMITTED edges of the world causal graph, at the lag each edge measured.

    Only admitted edges: a recorded-not-admitted edge is a measurement that did not clear its
    own bar, and treating it as a prior would launder a rejection into a hypothesis. The edge
    supplies the driver leg and the LAG; the desk supplies the shape (lead-lag, residual,
    co-movement), because an edge says what moves what, never how to trade it.

    Read defensively: the file is another engine's and may be absent, half-written or new.
    """
    edges = _admitted_edges(ctx.causal_graph, ctx.drivers)
    if not edges:
        ctx.notes["causal_derived"] = (
            f"no admitted edge on a driver these frames carry ({', '.join(ctx.drivers) or 'none'})"
            f": {ctx.causal_graph.name} absent, unreadable or still measuring")
        return []
    out: list[Expr] = []
    for _ in range(n):
        drv, lag = edges[int(ctx.rng.integers(len(edges)))]
        w = int(ctx.rng.choice(ag.WINDOWS[3:]))
        shape = int(ctx.rng.integers(3))
        if shape == 0:
            cand: Expr = ["corr", "ret", ["delta", ["delay", drv, lag], w], w]
        elif shape == 1:
            cand = ["residual", "close", ["delay", drv, lag], w]
        else:
            cand = ["zscore", ["delta", ["delay", drv, lag], w], w]
        if ag.is_valid(cand, ctx.allow_drivers, ctx.terminals):
            out.append(cand)
    return out


def _admitted_edges(path: Path, drivers: Sequence[str]) -> list[tuple[str, int]]:
    """(driver terminal, lag) for every admitted edge whose source the grammar can name."""
    try:
        doc = json.loads(Path(path).read_text("utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(doc, dict):
        return []
    out: list[tuple[str, int]] = []
    for e in doc.get("edges") or []:
        if not isinstance(e, dict) or str(e.get("status") or "").upper() != "ADMITTED":
            continue
        role = _driver_role(str(e.get("src") or ""), drivers)
        lag = e.get("lag")
        if role and isinstance(lag, (int, float)) and 1 <= int(lag) <= max(ag.WINDOWS):
            out.append((role, int(lag) if int(lag) in ag.WINDOWS else
                        min(ag.WINDOWS, key=lambda w: abs(w - int(lag)))))
    return out


def _driver_role(node: str, drivers: Sequence[str]) -> str | None:
    low = node.lower()
    for role in drivers:
        if role in low:
            return role
    return None


#: A mined claim's mechanism class -> the grammar shape that EXPRESSES it. The claim says what
#: the world does; this says how the desk would measure it on its own bars. A class with no
#: shape here is counted as unmapped rather than forced into the nearest one.
CLAIM_SHAPES: dict[str, Callable[[SearchContext, np.random.Generator], Any]] = {
    "momentum": lambda c, r: ["delta", "close", int(r.choice(ag.WINDOWS[4:]))],
    "reversion": lambda c, r: ["neg", ["zscore", "close", int(r.choice(ag.WINDOWS[3:]))]],
    "flow": lambda c, r: ["zscore", "flow" if "flow" in c.terminals else "activity",
                          int(r.choice(ag.WINDOWS[3:]))],
    "microstructure": lambda c, r: ["ts_rank", "spread" if "spread" in c.terminals else "range",
                                    int(r.choice(ag.WINDOWS[4:]))],
    "positioning": lambda c, r: ["zscore",
                                 "positioning" if "positioning" in c.terminals else "activity",
                                 int(r.choice(ag.WINDOWS[4:]))],
    "calendar": lambda c, r: ["group_rank", "ret", "activity" if "activity" in c.terminals
                              else "range", int(r.choice(ag.WINDOWS[4:]))],
    "inventory": lambda c, r: ["delta", "vol" if "vol" in c.terminals else "range",
                               int(r.choice(ag.WINDOWS[3:]))],
    "carry": lambda c, r: ["mean", "ret", int(r.choice(ag.WINDOWS[5:]))],
    "policy": lambda c, r: ["residual", "close", "rates" if "rates" in c.terminals else "close",
                            int(r.choice(ag.WINDOWS[5:]))],
    "cross_asset": lambda c, r: ["corr", "ret", str(r.choice(list(c.drivers) or ["ret"])),
                                 int(r.choice(ag.WINDOWS[4:]))],
}


def claims_derived(ctx: SearchContext, n: int) -> list[Expr]:
    """Build from mined mechanism claims, by the class the miner declared.

    The claim rows carry `channel`, `mechanism_class` and `mechanism_key`; only the class is
    turned into a shape, and only for a class this module knows how to express. `mechanism_key`
    is what keeps one loud story from dominating -- one draw per distinct mechanism, not one per
    telling -- and the channel rides along untouched: a claim reached through an information
    channel is still one claim.

    Read defensively; the miner owns the schema and is widening it.
    """
    classes = _claim_classes(ctx.claims)
    if not classes:
        ctx.notes["claims_derived"] = (
            f"no claim row with a mechanism class this grammar expresses in {ctx.claims.name}")
        return []
    out: list[Expr] = []
    for _ in range(n):
        cls = classes[int(ctx.rng.integers(len(classes)))]
        shape = CLAIM_SHAPES.get(cls)
        if shape is None:
            continue
        base = shape(ctx, ctx.rng)
        axis = MUTATION_AXES[int(ctx.rng.integers(len(MUTATION_AXES)))]
        cand = _zoo_axis(base, axis, ctx) if ctx.rng.random() < 0.5 else base
        if ag.is_valid(cand, ctx.allow_drivers, ctx.terminals):
            out.append(cand)
    return out


def _claim_classes(path: Path) -> list[str]:
    """One mechanism class per DISTINCT mechanism key, so a story told ten times counts once."""
    seen: set[str] = set()
    out: list[str] = []
    for row in _jsonl_tail(path, LEDGER_TAIL):
        cls = str(row.get("mechanism_class") or "").lower()
        key = str(row.get("mechanism_key") or row.get("claim_hash") or "")
        if cls in CLAIM_SHAPES and key and key not in seen:
            seen.add(key)
            out.append(cls)
    return out


def _jsonl_tail(path: Path, limit: int) -> list[dict[str, Any]]:
    """The last `limit` JSON objects of a JSONL ledger. A bad line is skipped, never fatal."""
    try:
        lines = Path(path).read_text("utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines[-int(limit):]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


# --------------------------------------------------------------------------- the registry
POPULATIONS: dict[str, Population] = {
    "gp": gp,
    "gflownet": gflownet,
    "symreg": symreg,
    "program_synthesis": program_synthesis,
    "bayesian": bayesian,
    "zoo_mutation": zoo_mutation,
    "graveyard_derived": graveyard_derived,
    "causal_derived": causal_derived,
    "claims_derived": claims_derived,
}


def run(ctx: SearchContext, *, n_per_population: int = 8, budget_s: float = 120.0,
        names: Iterable[str] | None = None,
        weights: Mapping[str, float] | None = None) -> SearchResult:
    """Every population under ONE budget, deduped across all of them by structural hash.

    THE DEDUPE IS ACROSS POPULATIONS, not within one. Two populations converging on the same
    tree have found one hypothesis, and charging it twice would inflate the multiplicity the
    gauntlet later deflates by. The population that got there FIRST is credited, and the second
    one's yield shows the collision as proposed-but-not-unique, which is exactly the signal a
    weight ledger needs to notice two populations doing one job.

    A population that raises costs its own share and nothing else: the failure is recorded with
    its type and the run continues. Budget is checked between populations, so the last one may
    be skipped rather than truncated mid-draw.
    """
    order = _order(names, weights, ctx.rng)
    result = SearchResult()
    seen: set[str] = set()
    started = time.monotonic()
    for name in order:
        if time.monotonic() - started > budget_s:
            result.yields[name] = PopulationYield(name, note="budget exhausted before it ran")
            continue
        fn = POPULATIONS[name]
        y = PopulationYield(name)
        t0 = time.monotonic()
        try:
            drawn = list(fn(ctx, int(n_per_population)) or [])
        except Exception as exc:
            y.note = f"{type(exc).__name__}: {exc}"
            result.failures.append(f"{name}: {y.note}")
            drawn = []
        y.proposed = len(drawn)
        for e in drawn:
            h = ag.subtree_hash(e)
            if h in seen:
                continue
            seen.add(h)
            y.unique += 1
            # A BARE TERMINAL IS A LEVEL, NOT AN ALPHA -- the same rule the typed samplers
            # enforce at the root. Crossover can return one (swap the whole tree for a leaf of
            # the other parent), and it would otherwise be donated as "close".
            if isinstance(e, str) or not ag.well_formed(e):
                continue
            y.well_formed += 1
            if ctx.falsifier is not None:
                try:
                    if not ctx.falsifier(e):
                        continue
                except Exception as exc:
                    result.failures.append(f"{name} falsifier: {type(exc).__name__}: {exc}")
                    continue
            y.passed += 1
            result.proposals.append((e, name))
        y.seconds = time.monotonic() - t0
        if not y.note:
            y.note = ctx.notes.get(name) or (
                "no falsifier: passed counts the well-formed" if ctx.falsifier is None
                else "screened by the cheap falsifier")
        result.yields[name] = y
    if ctx.cache is not None:
        result.cache_stats = dict(ctx.cache.stats())
    return result


def _order(names: Iterable[str] | None, weights: Mapping[str, float] | None,
           rng: np.random.Generator) -> list[str]:
    """Which populations run, and in what order. Weights shuffle the ORDER, never the budget:
    under a tight budget the last population is the one that does not run, so a weight table
    that starves an arm would silently retire it. Every named population still gets its draw."""
    chosen = [n for n in (names or POPULATIONS) if n in POPULATIONS]
    if not chosen:
        chosen = list(POPULATIONS)
    if not weights:
        return chosen
    w = np.array([max(0.0, float(weights.get(n, 0.0) or 0.0)) for n in chosen], dtype=float)
    if not np.isfinite(w).all() or w.sum() <= 0:
        return chosen
    # Draw the order without replacement in proportion to weight: the arm the ledger favours
    # runs first and is therefore the one that survives a short hour.
    out: list[str] = []
    pool, pw = list(chosen), list(w)
    while pool:
        p = np.array(pw, dtype=float)
        if p.sum() <= 0:
            out.extend(pool)
            break
        i = int(rng.choice(len(pool), p=p / p.sum()))
        out.append(pool.pop(i))
        pw.pop(i)
    return out
