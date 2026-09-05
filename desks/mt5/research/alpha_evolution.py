"""Portfolio-aware genetic search over the alpha grammar, proposing formula cells to the gauntlet.

WHAT IS SEARCHED. Expressions from `libs.research.alpha_grammar` -- causal operators over the
instrument's own bars and its economic drivers -- traded by `family_formula` with a fixed
threshold recipe. A population per instrument is evolved by mutation and crossover for a few
generations; every distinct expression evaluated is a trial and is charged as one.

FITNESS IS WHAT THE EXPRESSION DOES FOR THE BOOK, not its standalone t. Until 2026-09-05 that
claim rested on

    fitness = t x (0.5 + 0.5 x stability) - LAMBDA_CORR x relu(corr_survivors) x |t|
            + LAMBDA_NOVEL x novelty - LAMBDA_CX x complexity

-- a standalone t with two haircuts, blind to growth, to the tail, to cost, to capacity, to
fragility, to state breadth and to the trials spent finding it. The fitness is now
`libs.research.alpha_fitness`, which measures every one of those terms or NAMES it unmeasured:

    Fitness = w1 dE[logW_P] + w2 OOS + w3 Novelty + w4 Tail + w5 StateBreadth + w6 Capacity
              - w7 Cost - w8 Fragility - w9 Complexity - w10 Multiplicity

`dE[logW_P]` re-solves the book through the allocator's own optimiser; `Tail` is
`E[R_i | R_P < q10]` on the book's OWN worst decile, so the search's standing question is what
makes money when the current portfolio loses. The two expensive terms (the growth solve and the
+-20% fragility perturbation) are measured only for the finalists -- see `refine` -- because
every candidate paying for a portfolio solve would buy one generation per hour.

THE OLD SCALAR IS STILL COMPUTED AND STILL REPORTED as `fitness_legacy`, beside the new one. A
search whose ordering changed silently is a search nobody can audit.

SUCCESSIVE HALVING. Each new expression is first screened on the most recent STAGE0_FRAC of the
history -- a thirty-times cheaper falsifier -- and only the better half is run on the full
sample. The culled half still counts in the multiplicity: they were tried.

WHAT LEAVES. The best cell per instrument that clears cost and deflation, as an EXACT_RECIPE
under family `formula`, with `describe()`'s mechanism sentence written AFTER the search from the
tree. The gauntlet judges it like everything else; nothing here has authority.

WHERE NEW INDIVIDUALS COME FROM (2026-09-05). NINE POPULATIONS, NOT ONE SEARCH.
`libs.research.search_populations` runs gp (NSGA-II over the fitness components), gflownet,
symreg, program_synthesis (bottom-up enumeration of the typed grammar), bayesian (a TPE
surrogate over expression features), zoo_mutation (the public alpha families as genetic
material, never traded as written), graveyard_derived, causal_derived and claims_derived under
ONE budget, sharing ONE subtree cache, deduping across each other by structural hash. Each
reports proposed / unique / well-formed / passed-the-cheap-falsifier / donated, and the hourly
organ prints that ledger on its YIELD line. This module reads the population weights and never
sets them; the row's `generator` field carries the population that made it, so the ledger
outside can join a survivor's fate back to the population that proposed it.

INVALID ARITHMETIC IS NOT CONSTRUCTIBLE. Every population draws through `alpha_grammar`, whose
production screen is now structure AND type AND units, and the typed samplers intersect their
action mask with the unit algebra -- so no population can propose `add(std(close, 24),
std(ret, 24))`, and none has to be screened for it.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk.family_formula import family_formula  # noqa: E402

from libs.research import alpha_fitness as af  # noqa: E402
from libs.research import alpha_grammar as ag  # noqa: E402
from libs.research import generators as gen  # noqa: E402
from libs.research import search_populations as spop  # noqa: E402
from research import proposer_common as pc  # noqa: E402

SOURCE = "alpha_evolution"
REPORT = _DESK / "reports" / "alpha_evolution.json"
#: `hourly_discovery`'s convention for a child's counter line. Imported by value rather than by
#: module so this proposer stays runnable standalone when the hourly organ is not importable.
YIELD_PREFIX = "YIELD "
#: Generator weights, WRITTEN by the yield ledger and only READ here. Absent -> uniform. The
#: same file now carries POPULATION weights beside the old generator names; an unknown key is
#: ignored by both readers, so the two vocabularies can share one table during the changeover.
GENERATOR_WEIGHTS = _DESK / "data" / "generator_weights.json"
#: Share of each generation's new children drawn fresh from a POPULATION rather than bred from
#: the elite, so the nine searches keep contributing after generation zero.
FRESH_FRAC = 0.25
POP, GENS, ELITE, DEPTH = 40, 5, 8, 3
STAGE0_FRAC = 0.35
LAMBDA_CORR, LAMBDA_NOVEL, LAMBDA_CX = 0.8, 0.5, 0.03
RECIPE = {"norm": 240, "entry_z": 1.5, "hold_bars": 8, "atr_n": 20, "stop_atr": 2.0, "rr": 1.5}
SIDE_MODES = ("follow", "fade")
#: How many finalists per instrument pay for the two EXPENSIVE fitness terms: the portfolio
#: growth solve (two optimisations over a world population) and the +-20% fragility sweep (six
#: re-screens). Everything above them in the ranking is decided on the eight cheap terms, which
#: is the same successive-halving argument the stage-0 screen already makes.
REFINE_TOP = 6
#: A cheaper world population for SEARCH-time growth scoring. The allocator's own pass uses its
#: full draw; this one only has to rank candidates against each other, and a 256-world solve per
#: candidate would buy one generation an hour.
SEARCH_WORLDS, SEARCH_ROWS = 64, 192


def _book_symbols() -> list[str]:
    try:
        from research.state_vector_build import book_symbols
        return book_symbols()
    except Exception:
        return []


def _drivers_for(sym: str, meta: dict) -> dict[str, pd.DataFrame]:
    """The instrument's economic drivers as role -> bars, from the registry's driver sets."""
    out: dict[str, pd.DataFrame] = {}
    try:
        from mt5desk.economic_drivers import ROLES, driver_sets
        have = {p.stem.removesuffix("_H1") for p in pc.UNI.glob("*_H1.parquet")}
        for ds in driver_sets(sym, meta, have):
            for d in ds.drivers:
                for role, cands in ROLES.items():
                    if d in cands and role.lower() not in out:
                        b = pc.bars(d)
                        if b is not None:
                            out[role.lower()] = b
    except Exception:
        pass
    return out


def _survivor_daily_pnl(sym: str) -> pd.Series | None:
    """The desk's own shadow P&L on this instrument by day: what the book already earns here."""
    try:
        from research.state_admission_run import load_trades
        rows = [(t.when, t.r) for t in load_trades("shadow")
                if str(t.sleeve).split("_")[0].upper() == sym.upper()]
    except Exception:
        return None
    if not rows:
        return None
    s = pd.Series({pd.Timestamp(w).tz_convert("UTC").normalize() if pd.Timestamp(w).tzinfo
                   else pd.Timestamp(w).tz_localize("UTC").normalize(): r for w, r in rows})
    return s.groupby(level=0).sum()


def _daily_pnl_proxy(z: pd.Series, ret: pd.Series, entry_z: float, hold: int,
                     risk_frac: pd.Series | None = None) -> pd.Series:
    """Vectorised sign(z)-when-extreme position held `hold` bars, times next-bar return.

    `risk_frac` converts the bar's log return into R MULTIPLES -- the unit the book's own daily
    series is in and the unit `robust_elog.SleeveEvidence` documents. Without it the growth term
    would compare a log-return series against a book of R multiples and report a number in no
    unit at all. The risk per trade is the recipe's own stop: `stop_atr` ATRs of the price, which
    is exactly what the family risks when it enters.
    """
    pos = np.sign(z.where(z.abs() >= entry_z, 0.0)).fillna(0.0)
    held = pos.rolling(hold, min_periods=1).apply(
        lambda w: w[w != 0][-1] if (w != 0).any() else 0.0, raw=True) if hold > 1 else pos
    pnl = held.shift(1) * ret
    if risk_frac is not None:
        pnl = pnl / risk_frac.where(risk_frac > 1e-9)
    return pnl.groupby(pnl.index.normalize()).sum()


def _corr(a: pd.Series | None, b: pd.Series | None) -> float:
    if a is None or b is None:
        return 0.0
    j = pd.concat([a, b], axis=1, join="inner").dropna()
    if len(j) < 20 or j.iloc[:, 0].std() == 0 or j.iloc[:, 1].std() == 0:
        return 0.0
    return float(j.iloc[:, 0].corr(j.iloc[:, 1]))


class _Evaluator:
    def __init__(self, sym: str, d: pd.DataFrame, cost: float, drivers: dict[str, pd.DataFrame],
                 survivors: pd.Series | None, book: af.Book | None = None) -> None:
        self.sym, self.d, self.cost, self.drivers = sym, d, cost, drivers
        self.unfillable = pc.artifact_hours(d)
        # ONE SUBTREE CACHE FOR THE WHOLE INSTRUMENT, shared by all nine populations and by
        # every fitness evaluation on these bars: `delta(close, 24)` is computed once per
        # sweep rather than once per expression that contains it.
        self.cache = ag.SubtreeCache()
        self.frames = ag.terminal_frames(d, raw=d, drivers=drivers)
        self.memo = self.cache.scope(sym, self.frames)
        self.ret = self.frames["ret"]
        atr = self.frames.get("atr")
        # R-multiple denominator: the recipe's own stop, as a fraction of price.
        self.risk_frac = (float(RECIPE["stop_atr"]) * atr / self.frames["close"]
                          if atr is not None else None)
        self.survivors = survivors
        self.book = book if book is not None else af.Book()
        self.canon_z = {k: self._z(ag.evaluate(v, self.frames, self.memo))
                        for k, v in ag.CANON.items()}
        self.cut = int(len(d) * (1.0 - STAGE0_FRAC))
        self.rows: dict[str, dict] = {}                    # key -> row (one per expression)
        self.zs: dict[str, pd.Series] = {}
        self.terms: dict[str, af.FitnessTerms] = {}        # key -> the full term vector
        self.origin: dict[str, str] = {}                   # key -> population that made it
        self.generator_weights: dict = {}
        self.generator_failures: list[str] = []
        self.population_yield: list[dict] = []
        self.sharpes: list[float] = []                     # for the multiplicity charge

    @staticmethod
    def _z(v: pd.Series, norm: int = RECIPE["norm"]) -> pd.Series:
        r = v.rolling(norm, min_periods=norm)
        return (v - r.mean()) / r.std()

    def screen(self, expr: ag.Expr, side_mode: str, stage0: bool) -> dict | None:
        params = {**RECIPE, "expr": expr, "side_mode": side_mode}
        d = self.d.iloc[self.cut:] if stage0 else self.d
        sig = family_formula(d, drivers=self.drivers, **params)
        return pc.screen(d, sig, self.cost, self.unfillable)

    def fitness(self, expr: ag.Expr, side_mode: str, pop_z: list[pd.Series]) -> float:
        k = f"{ag.key(expr)}|{side_mode}"
        if k in self.rows and "fitness" in self.rows[k]:
            return float(self.rows[k]["fitness"])
        base = {"cell": f"{self.sym}.formula.{side_mode}", "symbol": self.sym,
                "params": {**RECIPE, "expr": expr, "side_mode": side_mode},
                "expr": ag.to_str(expr), "complexity": ag.complexity(expr),
                "generator": self.origin.get(k, "unspecified")}
        s0 = self.screen(expr, side_mode, stage0=True)
        if s0 is None:
            self.rows[k] = {**base, "stage": 0, "t_gross": 0.0, "clears_cost": False,
                            "n_independent": 0, "fitness": -9.0}
            return -9.0
        self.rows[k] = {**base, "stage": 0, **s0, "fitness": float(s0["t_gross"]) * 0.5 - 9.0}
        return float(self.rows[k]["fitness"])

    def _candidate(self, expr: ag.Expr, side_mode: str, row: dict, z: pd.Series,
                   pnl: pd.Series, refs: list[pd.Series], *,
                   with_fragility: bool) -> af.Candidate:
        """The candidate record the fitness reads. Everything measurable is passed; anything
        this sweep cannot measure is left None so the fitness NAMES it rather than assuming."""
        activity = self.frames.get("activity")
        return af.Candidate(
            daily=pnl, name=f"{self.sym}.formula.{side_mode}", symbol=self.sym, z=z,
            forward=self.ret.shift(-1), refs=tuple(refs), complexity=int(row["complexity"]),
            cost_frac=float(self.cost), gross_per_trade=row.get("gross_per_trade"),
            spread_frac=float(self.cost) / 2.0,
            activity=(float(activity.median()) if activity is not None
                      and activity.notna().any() else None),
            n_trials=max(1, len(self.rows)), sharpes=tuple(self.sharpes),
            params={k: v for k, v in RECIPE.items() if k in ("norm", "entry_z", "hold_bars")},
            score_fn=(self._rescore(expr, side_mode) if with_fragility else None))

    def _rescore(self, expr: ag.Expr, side_mode: str):
        """A stage-0 re-screen under perturbed recipe parameters, for the fragility sweep.

        Stage 0 rather than the full sample on purpose: fragility asks whether the SHAPE
        survives a parameter move, and the cheap slice answers that at a thirtieth of the price.
        """
        def _score(params: dict) -> float:
            merged = {**RECIPE, **dict(params), "expr": expr, "side_mode": side_mode}
            d = self.d.iloc[self.cut:]
            got = pc.screen(d, family_formula(d, drivers=self.drivers, **merged), self.cost,
                            self.unfillable)
            return float(got["t_gross"]) if got else 0.0
        return _score

    def promote(self, expr: ag.Expr, side_mode: str, pop_z: list[pd.Series], *,
                with_fragility: bool = False) -> float:
        """Full-sample evaluation for an expression that survived stage 0.

        The eight CHEAP fitness terms are measured here for every survivor; the growth solve and
        the fragility sweep are `refine`'s, for the finalists only.
        """
        k = f"{ag.key(expr)}|{side_mode}"
        row = self.rows.get(k)
        if row is None or row.get("stage") == 1:
            return float(row["fitness"]) if row else -9.0
        full = self.screen(expr, side_mode, stage0=False)
        if full is None:
            row.update({"stage": 1, "fitness": -9.0})
            return -9.0
        half = len(self.d) // 2
        t1 = pc.screen(self.d.iloc[:half],
                       family_formula(self.d.iloc[:half], drivers=self.drivers, **row["params"]),
                       self.cost, self.unfillable)
        t2 = pc.screen(self.d.iloc[half:],
                       family_formula(self.d.iloc[half:], drivers=self.drivers, **row["params"]),
                       self.cost, self.unfillable)
        t = float(full["t_gross"])
        th = [float(x["t_gross"]) for x in (t1, t2) if x]
        stability = (min(th) / max(abs(t), 1e-9)) if len(th) == 2 else 0.0
        stability = float(np.clip(stability * np.sign(t), 0.0, 1.0))
        z = self._z(ag.evaluate(expr, self.frames, self.memo))
        self.zs[k] = z
        flip = 1.0 if side_mode == "follow" else -1.0
        pnl = _daily_pnl_proxy(z * flip, self.ret, RECIPE["entry_z"], RECIPE["hold_bars"],
                               self.risk_frac)
        corr_surv = _corr(pnl, self.survivors)
        refs = list(self.canon_z.values()) + pop_z
        novelty = 1.0 - max([abs(_corr(z, r)) for r in refs] or [0.0])
        sd = float(pnl.std(ddof=1)) if pnl.notna().sum() > 1 else 0.0
        if sd > 1e-12:
            self.sharpes.append(float(pnl.mean() / sd))
        terms = af.evaluate(self._candidate(expr, side_mode, {**row, **full}, z, pnl, refs,
                                            with_fragility=with_fragility),
                            self.book, cfg=_search_worlds())
        self.terms[k] = terms
        fit = terms.score()
        legacy = (t * (0.5 + 0.5 * stability) - LAMBDA_CORR * max(0.0, corr_surv) * abs(t)
                  + LAMBDA_NOVEL * novelty - LAMBDA_CX * row["complexity"])
        row.update({"stage": 1, **full, "t_half": th, "stability": round(stability, 3),
                    "corr_survivors": round(corr_surv, 3), "novelty": round(novelty, 3),
                    "fitness": round(float(fit), 4), "fitness_legacy": round(float(legacy), 4),
                    "terms": {n: round(v, 5) for n, v in terms.as_dict().items()},
                    "unmeasured": list(terms.unmeasured),
                    "tail": terms.detail.get("tail", {}),
                    "book": terms.detail.get("book", "")})
        return float(fit)

    def refine(self, top: int = REFINE_TOP) -> list[str]:
        """Re-measure the finalists with the two expensive terms. Returns the keys refined.

        Successive halving applied to the FITNESS rather than to the sample: a portfolio growth
        solve and a six-point parameter sweep are worth paying for the candidates that could be
        proposed and worth nothing for the ones that cannot.
        """
        done: list[str] = []
        ranked = sorted((k for k, r in self.rows.items() if r.get("stage") == 1),
                        key=lambda k: -float(self.rows[k].get("fitness") or -9.0))
        for k in ranked[:top]:
            row = self.rows[k]
            expr, side_mode = row["params"]["expr"], row["params"]["side_mode"]
            z = self.zs.get(k)
            if z is None:
                continue
            flip = 1.0 if side_mode == "follow" else -1.0
            pnl = _daily_pnl_proxy(z * flip, self.ret, RECIPE["entry_z"], RECIPE["hold_bars"],
                                   self.risk_frac)
            refs = list(self.canon_z.values()) + [v for kk, v in self.zs.items() if kk != k]
            terms = af.evaluate(self._candidate(expr, side_mode, row, z, pnl, refs,
                                                with_fragility=True),
                                self.book, cfg=_search_worlds())
            self.terms[k] = terms
            row.update({"fitness": round(terms.score(), 4), "refined": True,
                        "terms": {n: round(v, 5) for n, v in terms.as_dict().items()},
                        "unmeasured": list(terms.unmeasured),
                        "why": {n: terms.why.get(n, "") for n in af.WEIGHTS},
                        "tail": terms.detail.get("tail", {})})
            done.append(k)
        return done


def _search_worlds():
    """The cheap world population for search-time growth scoring, or None if unavailable."""
    try:
        from libs.portfolio.robust_elog import WorldConfig
        return WorldConfig(n_worlds=SEARCH_WORLDS, n_rows=SEARCH_ROWS)
    except Exception:
        return None


def evolve(sym: str, d: pd.DataFrame, cost: float, drivers: dict[str, pd.DataFrame],
           survivors: pd.Series | None, *, seed: int = 0, budget_s: float = 240.0,
           pop: int = POP, gens: int = GENS, book: af.Book | None = None) -> _Evaluator:
    rng = np.random.default_rng(seed)
    ev = _Evaluator(sym, d, cost, drivers, survivors, book)
    allow_drivers = bool(drivers)
    weights, weights_basis = gen.load_weights(GENERATOR_WEIGHTS)
    pop_weights, pop_basis = _population_weights()
    ev.generator_weights = {"weights": weights, "basis": weights_basis,
                            "population_weights": pop_weights, "population_basis": pop_basis}
    ctx = spop.SearchContext(rng=rng, frames=ev.frames, ret=ev.ret, symbol=sym,
                             allow_drivers=allow_drivers, max_depth=DEPTH, cache=ev.cache,
                             seeds=list(ag.CANON.values()))

    def _refresh_context() -> None:
        """The populations learn from what has been scored so far, not from a frozen snapshot."""
        ctx.history = [(r["params"]["expr"], float(r["fitness"])) for r in ev.rows.values()
                       if "fitness" in r]
        ctx.scored = [(ev.rows[k]["params"]["expr"], t) for k, t in ev.terms.items()
                      if k in ev.rows]
        elite = sorted((r for r in ev.rows.values() if r.get("stage") == 1),
                       key=lambda r: -float(r.get("fitness") or -9.0))[:ELITE]
        ctx.seeds = [r["params"]["expr"] for r in elite] or list(ag.CANON.values())

    def _draw(n: int) -> list[tuple[ag.Expr, str]]:
        """`n` fresh individuals from the nine populations, with the yield ledger appended.

        A population that raises is recorded inside `search_populations.run` and costs its own
        share; the sweep continues. An empty draw falls back to the grammar's uniform sampler,
        which is the one generator that cannot fail.
        """
        _refresh_context()
        per = max(1, math.ceil(n / max(1, len(spop.POPULATIONS))))
        res = spop.run(ctx, n_per_population=per, budget_s=max(5.0, budget_s / 4.0),
                       weights=pop_weights)
        ev.population_yield.append({"at_rows": len(ev.rows), **{"rows": res.yield_rows()}})
        ev.generator_failures.extend(res.failures)
        out = [(e, who) for e, who in res.proposals]
        while len(out) < n:
            out.append((random_or_canon(rng, allow_drivers), "random"))
        return out[:n]

    population: list[tuple[ag.Expr, str]] = []
    seen: set[str] = set()
    for e, origin in _draw(pop * 2):
        if len(population) >= pop:
            break
        sm = str(rng.choice(SIDE_MODES))
        k = f"{ag.key(e)}|{sm}"
        if k not in seen:
            seen.add(k)
            ev.origin[k] = origin
            population.append((e, sm))
    while len(population) < pop:
        e = random_or_canon(rng, allow_drivers)
        sm = str(rng.choice(SIDE_MODES))
        k = f"{ag.key(e)}|{sm}"
        if k not in seen:
            seen.add(k)
            ev.origin[k] = "random"
            population.append((e, sm))
    started = time.monotonic()
    for _g in range(gens):
        if time.monotonic() - started > budget_s:
            break
        # Stage 0 for everyone new, full sample for the better half.
        s0 = sorted(population, key=lambda es: -ev.fitness(es[0], es[1], []))
        keep = s0[: max(ELITE, len(s0) // 2)]
        pop_z = list(ev.zs.values())
        for e, sm in keep:
            ev.promote(e, sm, pop_z)
        # SELECTION IS MULTI-OBJECTIVE. The elite is the Pareto front over the fitness terms,
        # ordered by crowding distance, so the candidate that is extraordinary on the tail and
        # ordinary elsewhere is a parent instead of an average.
        elite = _elite(ev, keep)
        children: list[tuple[ag.Expr, str]] = list(elite)
        fresh = _draw(max(1, int(pop * FRESH_FRAC))) if elite else []
        while len(children) < pop and time.monotonic() - started <= budget_s:
            if fresh and rng.random() < FRESH_FRAC:
                e, origin = fresh.pop()
                sm = str(rng.choice(SIDE_MODES))
            else:
                a = elite[int(rng.integers(len(elite)))] if elite else (
                    random_or_canon(rng, allow_drivers), str(rng.choice(SIDE_MODES)))
                if rng.random() < 0.5 and len(elite) > 1:
                    b = elite[int(rng.integers(len(elite)))]
                    e, origin = ag.crossover(a[0], b[0], rng, allow_drivers), "crossover"
                else:
                    e, origin = ag.mutate(a[0], rng, allow_drivers), "mutate"
                sm = a[1] if rng.random() < 0.8 else str(rng.choice(SIDE_MODES))
            k = f"{ag.key(e)}|{sm}"
            if k in seen or ag.complexity(e) > 14 or isinstance(e, str):
                continue
            seen.add(k)
            ev.origin[k] = origin
            children.append((e, sm))
        population = children
    # Final full evaluation of whatever is still only stage-0 in the last generation's elite,
    # then the two expensive terms for the finalists.
    for e, sm in population[:ELITE]:
        ev.promote(e, sm, list(ev.zs.values()))
    ev.refine()
    return ev


def _elite(ev: _Evaluator, keep: list[tuple[ag.Expr, str]]) -> list[tuple[ag.Expr, str]]:
    """The Pareto front of the promoted survivors, crowding-ordered; the scalar as the floor."""
    rows = [(e, sm, ev.terms.get(f"{ag.key(e)}|{sm}")) for e, sm in keep]
    have = [(e, sm, t) for e, sm, t in rows if t is not None]
    if have:
        order = af.nsga2_order([t for _e, _sm, t in have])
        return [(have[i][0], have[i][1]) for i in order[:ELITE]]
    return sorted(keep, key=lambda es: -float(
        ev.rows.get(f"{ag.key(es[0])}|{es[1]}", {}).get("fitness") or -9.0))[:ELITE]


def _population_weights() -> tuple[dict[str, float] | None, str]:
    """Population weights from the same table the generator weights live in. Absent -> uniform.

    Read here, WRITTEN by the yield ledger outside. An unknown key is ignored rather than
    rejected, so the generator names already in that file and the population names added
    2026-09-05 can share one table while the ledger catches up.
    """
    try:
        doc = json.loads(GENERATOR_WEIGHTS.read_text("utf-8"))
    except (OSError, ValueError):
        return None, f"{GENERATOR_WEIGHTS.name} absent or unreadable: uniform populations"
    table = doc.get("populations") if isinstance(doc, dict) else None
    if not isinstance(table, dict):
        return None, f"{GENERATOR_WEIGHTS.name} carries no population table: uniform"
    out: dict[str, float] = {}
    for k, v in table.items():
        try:
            if str(k) in spop.POPULATIONS:
                out[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    if not out:
        return None, f"{GENERATOR_WEIGHTS.name} names no known population: uniform"
    return out, f"{GENERATOR_WEIGHTS.name}: {json.dumps(out, sort_keys=True)}"


def random_or_canon(rng: np.random.Generator, allow_drivers: bool) -> ag.Expr:
    if rng.random() < 0.15:
        return json.loads(json.dumps(list(ag.CANON.values())[int(rng.integers(len(ag.CANON)))]))
    return ag.random_expr(rng, DEPTH, allow_drivers)


def generator_yield(rows: list[dict]) -> dict[str, dict]:
    """Per POPULATION: how many individuals it made, how many went full-sample, how many were
    proposed, and its best fitness. The raw material for the yield ledger that sets the weights;
    reported here so the number exists, decided nowhere here."""
    out: dict[str, dict] = {}
    for r in rows:
        g = str(r.get("generator") or "unspecified")
        row = out.setdefault(g, {"tried": 0, "full": 0, "proposed": 0, "best_fitness": None})
        row["tried"] += 1
        if r.get("stage") == 1:
            row["full"] += 1
        if r.get("proposed"):
            row["proposed"] += 1
        f = r.get("fitness")
        if isinstance(f, (int, float)) and (row["best_fitness"] is None or f > row["best_fitness"]):
            row["best_fitness"] = float(f)
    return out


def population_yield(per_symbol: dict[str, dict]) -> dict[str, dict]:
    """Sweep-wide draw ledger per population: proposed / unique / well-formed / passed.

    Distinct from `generator_yield`, which counts what each population's individuals went on to
    DO. This one counts what each population managed to draw at all, which is the number that
    tells a stalled population (0 proposed, with a note saying why) apart from an unlucky one.
    """
    out: dict[str, dict] = {}
    for info in per_symbol.values():
        for batch in info.get("population_yield") or []:
            for row in batch.get("rows") or []:
                name = str(row.get("population") or "unspecified")
                acc = out.setdefault(name, {"proposed": 0, "unique": 0, "well_formed": 0,
                                            "passed": 0, "seconds": 0.0, "note": ""})
                for k in ("proposed", "unique", "well_formed", "passed"):
                    acc[k] = int(acc[k]) + int(row.get(k) or 0)
                acc["seconds"] = round(float(acc["seconds"]) + float(row.get("seconds") or 0), 2)
                if row.get("note"):
                    acc["note"] = str(row["note"])
    return out


def run(symbols: list[str] | None = None, budget_s: float = 1500.0, seed: int = 0,
        pop: int = POP, gens: int = GENS) -> dict:
    meta = pc.universe_meta()
    have = {p.stem.removesuffix("_H1") for p in pc.UNI.glob("*_H1.parquet")}
    todo = [s for s in (symbols or _book_symbols()) if s in have]
    rows: list[dict] = []
    skipped: dict[str, str] = {}
    per_symbol: dict[str, dict] = {}
    generator_weights: dict = {}
    generator_failures: list[str] = []
    started = time.monotonic()
    # ONE READ OF THE BOOK for the whole sweep: the growth and tail terms measure every
    # instrument's candidates against the SAME book, and re-reading it per symbol would let a
    # mid-sweep allocator write change what a later symbol is scored against.
    book = af.load_book()
    per_sym_budget = max(60.0, budget_s / max(1, len(todo)))
    for sym in sorted(set(todo)):
        if time.monotonic() - started > budget_s:
            skipped[sym] = "sweep budget exhausted"
            continue
        d = pc.bars(sym)
        if d is None or len(d) < 3000:
            skipped[sym] = "under 3000 H1 bars"
            continue
        cost = pc.cost_frac(sym, meta, d["close"])
        if cost is None:
            skipped[sym] = "no contract terms to price the round trip"
            continue
        ev = evolve(sym, d, cost, _drivers_for(sym, meta), _survivor_daily_pnl(sym), seed=seed,
                    budget_s=per_sym_budget, pop=pop, gens=gens, book=book)
        sym_rows = list(ev.rows.values())
        rows.extend(sym_rows)
        full = [r for r in sym_rows if r.get("stage") == 1]
        per_symbol[sym] = {"expressions_tried": len(sym_rows), "full_evaluations": len(full),
                           "best": (max(full, key=lambda r: r["fitness"])["expr"] if full
                                    else None),
                           "drivers": sorted(ev.drivers),
                           "generators": generator_yield(sym_rows),
                           "population_yield": ev.population_yield,
                           "subtree_cache": ev.cache.stats()}
        generator_weights = ev.generator_weights
        generator_failures.extend(f"{sym}: {f}" for f in ev.generator_failures)
    # Every distinct expression tried is a trial; stage-0-only rows may not be proposed.
    rows = pc.deflate(rows)
    for r in rows:
        if r.get("stage") != 1:
            r["proposed"] = False
    proposals = pc.best_per_cell(rows)
    cands = [pc.candidate(
        SOURCE, r["symbol"], "formula", dict(r["params"]),
        mechanism=ag.describe(r["params"]["expr"], r["params"]["side_mode"]),
        title=f"{r['cell']} {r['expr']}",
        # `generator` rides in the evidence so `mutation_yield` can join each proposal's fate
        # back to the generator that made it and write the weights this module reads.
        evidence={k: r.get(k) for k in ("n_independent", "gross_per_trade", "net_per_trade",
                                        "cost_frac", "t_gross", "t_deflated_sweep",
                                        "n_tests_sweep", "stability", "corr_survivors",
                                        "novelty", "fitness", "fitness_legacy", "terms",
                                        "unmeasured", "tail", "generator")},
    ) for r in proposals]
    pops = population_yield(per_symbol)
    report = {"generated_at": datetime.now(tz=UTC).isoformat(), "symbols_swept": len(todo),
              "tests_run": len(rows), "cells_proposed": len(proposals), "skipped": skipped,
              "per_symbol": per_symbol, "proposals": proposals,
              # THE YIELD LEDGER'S INPUT: which population's individuals were tried, went
              # full-sample and were proposed, sweep-wide, beside the weights that were read.
              # Whatever writes data/generator_weights.json reads this.
              "generator_yield": generator_yield(rows),
              "population_yield": pops,
              "generator_weights": generator_weights,
              "generator_failures": generator_failures,
              # THE FITNESS, NAMED. Which terms could be measured this sweep and which could
              # not: a fitness computed on an empty desk must never read like one computed
              # against a full book.
              "fitness_weights": dict(af.WEIGHTS),
              "book": book.source,
              "unmeasured_terms": sorted({u for r in rows for u in (r.get("unmeasured") or [])}),
              "top": sorted((r for r in rows if r.get("stage") == 1
                             and int(r.get("n_independent", 0)) > 0),
                            key=lambda r: -r["fitness"])[:25]}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1, default=str), "utf-8")
    if cands:
        report["donated"] = str(pc.donate(SOURCE, cands, len(rows)))
    # THE LLM AS A FOURTH GENERATOR. One task per swept instrument asks the deepening seat for an
    # expression the grammar search did NOT find, with the terminals it may use and the best
    # expressions already tried; the worker validates the tree structurally (kind
    # alpha_expression) and the compiler admits it as a formula cell like any GP survivor. The
    # seat has no more authority than the random generator -- its output is charged and gated.
    try:
        report["llm_tasks"] = len(_expression_tasks(per_symbol, rows))
    except Exception as exc:
        report["llm_tasks_error"] = f"{type(exc).__name__}: {exc}"
    return report


def _expression_tasks(per_symbol: dict, rows: list[dict], *, top: int = 5) -> list[dict]:
    tasks = []
    for sym, info in sorted(per_symbol.items()):
        tried = sorted((r for r in rows if r.get("symbol") == sym and r.get("stage") == 1),
                       key=lambda r: -float(r.get("fitness") or -9.0))[:top]
        terminals = list(ag.BAR_TERMINALS) + sorted(info.get("drivers") or [])
        tasks.append({
            "source": SOURCE, "kind": "alpha_expression", "symbols": [sym],
            "title": f"{sym}: one formulaic alpha the grammar search has not found",
            "url": "",
            "description": (f"Available terminals: {terminals}. Best expressions already tried "
                            f"(do not return these): {[r.get('expr') for r in tried]}. Windows: "
                            f"{list(ag.WINDOWS)}. Return family 'formula' with a well-typed "
                            "expression, side_mode, entry_z and hold_bars, and the economic "
                            "mechanism it expresses."),
            "tried": [r.get("expr") for r in tried], "status": None,
            "consumer": "deepening_worker (alpha_expression) -> compiler -> gauntlet"})
    if tasks:
        from research.regime_coverage import _merge_into_queue
        _merge_into_queue(tasks, source=SOURCE)
    return tasks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", action="append", default=None)
    ap.add_argument("--budget-s", type=float, default=1500.0)
    ap.add_argument("--pop", type=int, default=POP)
    ap.add_argument("--gens", type=int, default=GENS)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rep = run(symbols=a.symbol, budget_s=a.budget_s, seed=a.seed, pop=a.pop, gens=a.gens)
    print(f"ALPHA EVOLUTION  {rep['symbols_swept']} symbols, {rep['tests_run']} expressions tried, "
          f"{rep['cells_proposed']} proposed")
    for r in rep["top"][:10]:
        print(f"  {r['symbol']:8s} fit={r['fitness']:+6.2f} t={r['t_gross']:+5.2f} "
              f"t_defl={r.get('t_deflated_sweep', 0):+5.2f} n={r['n_independent']:4d} "
              f"stab={r.get('stability', 0):.2f} corr_surv={r.get('corr_survivors', 0):+.2f} "
              f"nov={r.get('novelty', 0):.2f}  {r['params']['side_mode']}  {r['expr']}")
    for k, v in rep["skipped"].items():
        print(f"  skipped {k}: {v}")
    print("populations (proposed/unique/well-formed/passed):")
    for name, y in sorted(rep.get("population_yield", {}).items()):
        print(f"  {name:20s} {y['proposed']:4d}/{y['unique']:4d}/{y['well_formed']:4d}/"
              f"{y['passed']:4d}  {y['seconds']:6.1f}s  {y['note'][:70]}")
    print("outcomes: " + ", ".join(
        f"{g}={y['tried']}/{y['full']}/{y['proposed']}" for g, y in rep["generator_yield"].items())
        + f"  (weights: {rep['generator_weights'].get('population_basis')})")
    print(f"book: {rep.get('book')}   unmeasured terms: "
          f"{', '.join(rep.get('unmeasured_terms') or []) or 'none'}")
    for f in rep["generator_failures"]:
        print(f"  population failed: {f}")
    print(f"written: {REPORT}")
    # THE HOURLY ORGAN'S YIELD LINE. `hourly_discovery` parses the last line beginning with
    # this prefix, so the per-population ledger reaches the hourly report as counters rather
    # than as prose in a truncated tail.
    print(YIELD_PREFIX + json.dumps(yield_line(rep)), flush=True)
    return 0


def yield_line(rep: dict) -> dict[str, int]:
    """The integer counters the hourly pass keeps per organ, plus the per-population draws.

    `cells_proposed`, `candidates` and `tests_run` are `hourly_discovery.YIELD_KEYS`; the
    `pop:<name>` counters ride alongside so an hour's report says WHICH population produced the
    hour's candidates rather than only how many there were.
    """
    out = {"cells_proposed": int(rep.get("cells_proposed") or 0),
           "candidates": int(rep.get("cells_proposed") or 0),
           "tests_run": int(rep.get("tests_run") or 0)}
    for name, y in (rep.get("population_yield") or {}).items():
        out[f"pop:{name}"] = int(y.get("passed") or 0)
    return out


if __name__ == "__main__":
    raise SystemExit(main())
