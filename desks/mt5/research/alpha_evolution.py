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
from typing import Any

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
#: THE REST OF THE GENOME, AND ITS RANGE (Tier-1 B5). Every bound BRACKETS the standing default
#: on both sides: a variant may hold four times as long or a quarter as long, stop twice as wide
#: or half as wide, target 4R or 1R. Nothing here is a risk cap -- the stop is the definition of
#: the R unit, so a wider stop is the same heat measured against a larger denominator, and a
#: bound that only shrank would be exactly the timid modifier the standing order forbids.
RECIPE_BOUNDS: dict[str, tuple[float, float]] = {
    "hold_bars": (2.0, 48.0), "stop_atr": (1.0, 4.0), "rr": (1.0, 4.0), "entry_z": (0.75, 3.0),
}
#: Multiplicative hill-climb steps, both directions. Six screens per parameter at most.
RECIPE_STEPS: tuple[float, ...] = (0.5, 0.75, 1.5, 2.0)
SIDE_MODES = ("follow", "fade")
#: How many finalists per instrument pay for the two EXPENSIVE fitness terms: the portfolio
#: growth solve (two optimisations over a world population) and the +-20% fragility sweep (six
#: re-screens). Everything above them in the ranking is decided on the eight cheap terms, which
#: is the same successive-halving argument the stage-0 screen already makes.
REFINE_TOP = 6
#: The meta-evolution layer's active variants (LAWS 5m): a `grammar_evolution` variant sets the
#: fresh-immigrant share this run breeds with, clamped into the range the search was designed
#: for, and its id is recorded on the report so the run's yield can be credited back to it.
ACTIVE_VARIANTS = _DESK / "data" / "research_evolution" / "active_variants.json"


def search_policy(path: Path | None = None) -> dict:
    """{fresh_frac, refine_top, variant, basis}: the module defaults or the activated variant."""
    pol: dict = {"fresh_frac": FRESH_FRAC, "refine_top": REFINE_TOP, "variant": None,
                 "basis": "module defaults (no active grammar_evolution variant)"}
    try:
        doc = json.loads((path or ACTIVE_VARIANTS).read_text(encoding="utf-8-sig"))
        var = ((doc.get("variants") or {}).get("grammar_evolution")
               if isinstance(doc, dict) else None)
    except (OSError, ValueError, AttributeError):
        var = None
    if not isinstance(var, dict) or not isinstance(var.get("config"), dict):
        # THE PROGRAM DATABASE FILLS THE DEFAULT THE ARCHIVE DID NOT SET (Tier-1 Q3).
        # `algorithm_db` evolves parameterised SEARCH-POLICY configs and scores each against this
        # organ's own report (proposals per expression tried). The research-evolution archive
        # still wins wherever it names a variant -- this only replaces the module constants, and
        # only with a config that has a MEASURED score. An unevaluated champion changes nothing.
        try:
            import algorithm_db
            ch = algorithm_db.champion("search_policy")
            cfg2 = ch.get("params") if ch.get("score") is not None else None
            if isinstance(cfg2, dict):
                if isinstance(cfg2.get("fresh_frac"), (int, float)):
                    pol["fresh_frac"] = float(min(0.6, max(0.05, cfg2["fresh_frac"])))
                if isinstance(cfg2.get("refine_top"), (int, float)):
                    pol["refine_top"] = int(min(12, max(2, cfg2["refine_top"])))
                pol["variant"] = str(ch.get("program_id") or "")
                pol["basis"] = (f"algorithm_db champion {ch.get('program_id')} "
                                f"(score {ch.get('score')} from {ch.get('evaluator')})")
        except Exception:
            pass
        return pol
    cfg = var["config"]
    ff, rt = cfg.get("fresh_frac"), cfg.get("refine_top")
    if isinstance(ff, (int, float)):
        pol["fresh_frac"] = float(min(0.6, max(0.05, ff)))
    if isinstance(rt, (int, float)):
        pol["refine_top"] = int(min(12, max(2, rt)))
    pol["variant"] = str(var.get("id")) if var.get("id") else None
    pol["basis"] = f"active_variants.json grammar_evolution ({var.get('basis')})"
    return pol

#: A cheaper world population for SEARCH-time growth scoring. The allocator's own pass uses its
#: full draw; this one only has to rank candidates against each other, and a 256-world solve per
#: candidate would buy one generation an hour.
SEARCH_WORLDS, SEARCH_ROWS = 64, 192

# ==============================================================================================
# THE ARCHIVE (Tier-1 audit G16, 2026-09-08): a descriptor-keyed MAP-Elites grid beside ELITE.
#
# The elite was ONE Pareto front of eight. A tree that is the best thing this desk has ever
# found in "reversal x intraday x bull/high_vol x fx_major" was discarded the moment eight
# globally-better trees existed, and the search forgot it had ever illuminated that cell. The
# archive keeps the best expression PER CELL, where a cell is
#
#     (mechanism_class, horizon bucket, top regime label, symbol asset class)
#
# and its champions breed beside the elite (`_parents`). Occupancy -- cells filled over cells
# possible -- is published in the report so "how much of the descriptor space has the search
# ever lit" is a number rather than an impression. Nothing here has authority: an archive
# champion is a parent and a row in a report; the gauntlet certifies.
# ==============================================================================================
STATE_VECTOR = _DESK / "data" / "state_vector.json"
#: hold_bars -> horizon bucket, upper bounds inclusive; above the last is "position".
HORIZON_BUCKETS: tuple[tuple[int, str], ...] = ((4, "scalp"), (24, "intraday"), (120, "swing"))
HORIZON_NAMES: tuple[str, ...] = (*(n for _b, n in HORIZON_BUCKETS), "position")
#: The SHAPES `alpha_grammar.describe` distinguishes, each on both sides: what the tree measures
#: and whether it is followed or faded. "momentum" faded is a reversal and is named as one.
SHAPES: tuple[str, ...] = ("state_conditional", "momentum", "normalised_extreme", "co_movement",
                           "distance_from_extreme", "level")
MECHANISM_CLASSES: tuple[str, ...] = tuple(
    ("reversal" if (s == "momentum" and side == "fade") else f"{s}:{side}")
    for s in SHAPES for side in SIDE_MODES)
UNLABELLED = "UNLABELLED"


def mechanism_class(expr: ag.Expr, side_mode: str) -> str:
    """The tree's mechanism class from its structure -- the same op-set reading `describe` makes,
    so the archive's rows and the mechanism sentence on a proposal can never disagree."""
    ops: set[str] = set()

    def _walk(x: ag.Expr) -> None:
        if isinstance(x, (list, tuple)) and x:
            ops.add(str(x[0]))
            for c in x[1:]:
                _walk(c)
    _walk(expr)
    if ops & {"group_rank", "group_zscore"}:
        shape = "state_conditional"
    elif ops & {"delta", "decay", "sum"} and "zscore" not in ops:
        shape = "momentum"
    elif ops & {"zscore", "ts_rank", "scale"}:
        shape = "normalised_extreme"
    elif ops & {"corr", "residual", "cov"}:
        shape = "co_movement"
    elif ops & {"bars_since_max", "bars_since_min", "max", "min"}:
        shape = "distance_from_extreme"
    else:
        shape = "level"
    side = side_mode if side_mode in SIDE_MODES else SIDE_MODES[0]
    return "reversal" if (shape == "momentum" and side == "fade") else f"{shape}:{side}"


def horizon_bucket(hold_bars: int) -> str:
    h = int(hold_bars)
    for bound, name in HORIZON_BUCKETS:
        if h <= bound:
            return name
    return "position"


def _read_state_vector() -> dict:
    try:
        doc = json.loads(STATE_VECTOR.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def regime_label(sym: str, doc: dict | None = None) -> str:
    """The top regime label for `sym` from data/state_vector.json: the instrument's own H1 fit
    when the vector carries one, else the global fit, else UNLABELLED -- which is a real answer,
    never a guessed regime."""
    d = _read_state_vector() if doc is None else doc
    assets = d.get("assets") if isinstance(d.get("assets"), dict) else {}
    for key in (f"{sym}@H1", f"{sym}@daily", f"{sym}@M15", f"{sym}@M5"):
        row = assets.get(key)
        if isinstance(row, dict) and row.get("top"):
            return str(row["top"])
    g = d.get("global")
    if isinstance(g, dict) and g.get("top"):
        return str(g["top"])
    return UNLABELLED


def regime_labels_known(doc: dict | None = None) -> tuple[str, ...]:
    """Every regime label the state vector names, for the denominator of occupancy."""
    d = _read_state_vector() if doc is None else doc
    out: set[str] = set()
    g = d.get("global")
    if isinstance(g, dict):
        out.update(str(x) for x in (g.get("labels") or []))
    assets = d.get("assets") if isinstance(d.get("assets"), dict) else {}
    for row in assets.values():
        if isinstance(row, dict):
            out.update(str(x) for x in (row.get("labels") or []))
    return tuple(sorted(out)) or (UNLABELLED,)


def _asset_class(sym: str) -> str:
    try:
        from mt5desk.universe import asset_class
        return str(asset_class(sym) or "unknown")
    except Exception:
        return "unknown"


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


def _position_path(z: pd.Series, entry_z: float, hold: int) -> pd.Series:
    """The position the P&L proxy holds bar by bar: sign(z) when extreme, held `hold` bars.

    Factored out so the SAME path the P&L was computed on is what the fitness charges turnover
    for (`alpha_fitness.turnover_term`); a rate inferred from the signal's threshold elsewhere
    would be a second definition of what was traded.
    """
    pos = np.sign(z.where(z.abs() >= entry_z, 0.0)).fillna(0.0)
    if hold > 1:
        return pos.rolling(hold, min_periods=1).apply(
            lambda w: w[w != 0][-1] if (w != 0).any() else 0.0, raw=True)
    return pos


def _daily_pnl_proxy(z: pd.Series, ret: pd.Series, entry_z: float, hold: int,
                     risk_frac: pd.Series | None = None,
                     held: pd.Series | None = None) -> pd.Series:
    """Vectorised sign(z)-when-extreme position held `hold` bars, times next-bar return.

    `risk_frac` converts the bar's log return into R MULTIPLES -- the unit the book's own daily
    series is in and the unit `robust_elog.SleeveEvidence` documents. Without it the growth term
    would compare a log-return series against a book of R multiples and report a number in no
    unit at all. The risk per trade is the recipe's own stop: `stop_atr` ATRs of the price, which
    is exactly what the family risks when it enters. `held` is the position path when the caller
    already built it (so turnover and P&L are read off one object).
    """
    if held is None:
        held = _position_path(z, entry_z, hold)
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


#: THE IC PRE-SCREEN (2026-09-16). A formulaic expression is the one candidate shape that HAS a
#: continuous predictor before any replay, so the Chinese-practice report card applies to it:
#: rank-IC of the expression against the forward return over K disjoint time folds, its
#: dispersion, and the share of folds agreeing in sign. A proposal whose IC flips sign across
#: folds is UNSTABLE and is not handed to the gauntlet -- it is still COUNTED as a trial in
#: `pc.deflate`, so screening never lowers the multiplicity charge the survivors pay.
IC_FOLDS = 4
IC_MIN_ABS = 0.005
IC_SIGN_MIN = 0.75


def ic_folds(z: pd.Series, ret: pd.Series, hold: int, k: int = IC_FOLDS) -> dict[str, float]:
    """Rank-IC per fold of `z` against the `hold`-bar forward return; mean, IR, sign consistency."""
    try:
        fwd = ret.rolling(int(hold)).sum().shift(-int(hold))
        j = pd.concat([z.rename("z"), fwd.rename("f")], axis=1).dropna()
    except Exception:
        return {"ic_mean": 0.0, "ic_ir": 0.0, "ic_sign": 0.0, "ic_n": 0}
    n = len(j)
    if n < 40 * k:
        return {"ic_mean": 0.0, "ic_ir": 0.0, "ic_sign": 0.0, "ic_n": int(n)}
    ics: list[float] = []
    for i in range(k):
        part = j.iloc[i * n // k:(i + 1) * n // k]
        if len(part) < 40:
            continue
        ic = part["z"].rank().corr(part["f"].rank())
        if ic == ic:                                                 # not NaN
            ics.append(float(ic))
    if len(ics) < 2:
        return {"ic_mean": 0.0, "ic_ir": 0.0, "ic_sign": 0.0, "ic_n": int(n)}
    arr = np.asarray(ics, dtype=float)
    mean = float(arr.mean())
    sd = float(arr.std(ddof=1)) if arr.size > 1 else 0.0
    sign = float((np.sign(arr) == np.sign(mean)).mean()) if mean != 0.0 else 0.0
    return {"ic_mean": round(mean, 5), "ic_ir": round(mean / sd, 3) if sd > 1e-12 else 0.0,
            "ic_sign": round(sign, 3), "ic_n": int(n), "ic_folds": [round(x, 4) for x in ics]}


def ic_screen(row: dict) -> str | None:
    """None when the row may be proposed; else the reason it is screened out."""
    if row.get("stage") != 1:
        return None
    ic, sign = float(row.get("ic_mean") or 0.0), float(row.get("ic_sign") or 0.0)
    if abs(ic) < IC_MIN_ABS:
        return f"IC_WEAK: |ic_mean| {abs(ic):.4f} < {IC_MIN_ABS}"
    if sign < IC_SIGN_MIN:
        return f"IC_UNSTABLE: sign agreement {sign:.2f} < {IC_SIGN_MIN} across {IC_FOLDS} folds"
    return None


class _Evaluator:
    def __init__(self, sym: str, d: pd.DataFrame, cost: float, drivers: dict[str, pd.DataFrame],
                 survivors: pd.Series | None, book: af.Book | None = None,
                 regime: str | None = None, asset_class: str | None = None) -> None:
        self.sym, self.d, self.cost, self.drivers = sym, d, cost, drivers
        self.unfillable = pc.artifact_hours(d)
        # THE ARCHIVE'S TWO FIXED AXES for this instrument. The regime is the state vector's top
        # label at sweep time and the asset class the registry's; both are read once so every
        # cell of one sweep is keyed on one reading.
        self.regime = regime if regime is not None else regime_label(sym)
        self.asset_class = asset_class if asset_class is not None else _asset_class(sym)
        #: descriptor cell -> (fitness, row key): the best expression per cell, kept beside ELITE.
        self.archive: dict[tuple[str, str, str, str], tuple[float, str]] = {}
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
        #: key -> daily P&L proxy of every promoted expression: the PEER POPULATION the
        #: crowding term measures each candidate's edge against (alpha_fitness.crowding_term).
        self.pnls: dict[str, pd.Series] = {}
        self.terms: dict[str, af.FitnessTerms] = {}        # key -> the full term vector
        self.origin: dict[str, str] = {}                   # key -> population that made it
        self.generator_weights: dict = {}
        self.generator_failures: list[str] = []
        self.population_yield: list[dict] = []
        #: What `evolve_recipe` changed for each finalist: the rest of the genome, and by how
        #: much its marginal dE[log W] moved (Tier-1 B5).
        self.recipe_evolution: list[dict] = []
        #: Recipe variants that could not be screened, by name. Reported, never silent.
        self.recipe_failures: list[str] = []
        self.sharpes: list[float] = []                     # for the multiplicity charge

    @staticmethod
    def _z(v: pd.Series, norm: int = RECIPE["norm"]) -> pd.Series:
        r = v.rolling(norm, min_periods=norm)
        return (v - r.mean()) / r.std()

    # ------------------------------------------------------------------ the archive
    def descriptor(self, expr: ag.Expr, side_mode: str,
                   hold_bars: int | None = None) -> tuple[str, str, str, str]:
        """The cell an expression lives in: (mechanism class, horizon bucket, regime, asset)."""
        hold = int(RECIPE["hold_bars"]) if hold_bars is None else int(hold_bars)
        return (mechanism_class(expr, side_mode), horizon_bucket(hold), self.regime,
                self.asset_class)

    def _archive_put(self, key: str, fitness: float) -> bool:
        """Keep `key` as its cell's champion if it beats the incumbent. True when it did."""
        row = self.rows.get(key)
        if row is None or not math.isfinite(float(fitness)):
            return False
        params = row.get("params") or {}
        cell = self.descriptor(params.get("expr"), str(params.get("side_mode") or "follow"),
                               params.get("hold_bars"))
        have = self.archive.get(cell)
        if have is None or float(fitness) > have[0]:
            self.archive[cell] = (float(fitness), key)
            return True
        return False

    def champions(self) -> list[tuple[ag.Expr, str]]:
        """Every cell's best expression, best cell first -- the archive's contribution to the
        next generation's parents."""
        out: list[tuple[ag.Expr, str]] = []
        for _cell, (_fit, key) in sorted(self.archive.items(), key=lambda kv: -kv[1][0]):
            row = self.rows.get(key)
            if row is None:
                continue
            p = row.get("params") or {}
            out.append((p.get("expr"), str(p.get("side_mode") or "follow")))
        return out

    def archive_report(self) -> dict:
        """The archive as rows, keyed cell by cell, with the axes this instrument was keyed on."""
        cells = []
        for cell, (fit, key) in sorted(self.archive.items(), key=lambda kv: -kv[1][0]):
            row = self.rows.get(key) or {}
            cells.append({"mechanism_class": cell[0], "horizon": cell[1], "regime": cell[2],
                          "asset_class": cell[3], "fitness": round(float(fit), 4),
                          "expr": row.get("expr"), "side_mode": (row.get("params") or {}
                                                                  ).get("side_mode")})
        return {"regime": self.regime, "asset_class": self.asset_class,
                "cells_filled": len(cells), "cells": cells}

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
                   with_fragility: bool, key: str = "",
                   position: pd.Series | None = None) -> af.Candidate:
        """The candidate record the fitness reads. Everything measurable is passed; anything
        this sweep cannot measure is left None so the fitness NAMES it rather than assuming.

        The three search-side pressures (2026-09-08) read: `position`, the path the P&L was
        computed on; `peer_daily`, every OTHER promoted expression's P&L on this instrument --
        the cross-section crowding is measured against; and `family`, which is `formula` for
        everything this proposer emits, so the existing-exposure charge is the canon's own count
        of formula sleeves."""
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
            score_fn=(self._rescore(expr, side_mode) if with_fragility else None),
            position=position,
            peer_daily=tuple(v for kk, v in self.pnls.items() if kk != key),
            family="formula",
            # THE DECLARED GENOME SLOTS the two breadth credits are measured on (Tier-1 D5).
            # `asset_class` comes from MetaTrader's own registry through `universe_policy`, never
            # a symbol list, so a name the registry has not classified reads UNCLASSIFIED and the
            # scarcity term measures the cell it actually lands in rather than a guessed one.
            slots=self._slots(side_mode))

    def _slots(self, side_mode: str) -> dict[str, str]:
        """The candidate's genome slots for `alpha_fitness`' breadth credits (Tier-1 D5)."""
        try:
            from research.universe_policy import asset_class_of
            klass = str(asset_class_of(self.sym))
        except Exception:
            klass = ""
        return {k: v for k, v in (("instrument", self.sym), ("mechanism", "formula"),
                                  ("asset_class", klass), ("horizon", "H1"),
                                  ("regime", str(side_mode))) if v}

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
        held = _position_path(z * flip, RECIPE["entry_z"], RECIPE["hold_bars"])
        pnl = _daily_pnl_proxy(z * flip, self.ret, RECIPE["entry_z"], RECIPE["hold_bars"],
                               self.risk_frac, held=held)
        self.pnls[k] = pnl
        # The IC report card, on the expression's own z against the recipe's hold horizon.
        row.update(ic_folds(z * flip, self.ret, int(RECIPE["hold_bars"])))
        corr_surv = _corr(pnl, self.survivors)
        refs = list(self.canon_z.values()) + pop_z
        novelty = 1.0 - max([abs(_corr(z, r)) for r in refs] or [0.0])
        sd = float(pnl.std(ddof=1)) if pnl.notna().sum() > 1 else 0.0
        if sd > 1e-12:
            self.sharpes.append(float(pnl.mean() / sd))
        terms = af.evaluate(self._candidate(expr, side_mode, {**row, **full}, z, pnl, refs,
                                            with_fragility=with_fragility, key=k,
                                            position=held),
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
        self._archive_put(k, float(fit))
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
            held = _position_path(z * flip, RECIPE["entry_z"], RECIPE["hold_bars"])
            pnl = _daily_pnl_proxy(z * flip, self.ret, RECIPE["entry_z"], RECIPE["hold_bars"],
                                   self.risk_frac, held=held)
            self.pnls[k] = pnl
            refs = list(self.canon_z.values()) + [v for kk, v in self.zs.items() if kk != k]
            terms = af.evaluate(self._candidate(expr, side_mode, row, z, pnl, refs,
                                                with_fragility=True, key=k, position=held),
                                self.book, cfg=_search_worlds())
            self.terms[k] = terms
            row.update({"fitness": round(terms.score(), 4), "refined": True,
                        "terms": {n: round(v, 5) for n, v in terms.as_dict().items()},
                        "unmeasured": list(terms.unmeasured),
                        "why": {n: terms.why.get(n, "") for n in af.WEIGHTS},
                        "tail": terms.detail.get("tail", {})})
            self._archive_put(k, float(terms.score()))
            done.append(k)
        return done

    # ------------------------------------------------- the rest of the genome (Tier-1 B5)
    def evolve_recipe(self, top: int = REFINE_TOP, deadline: float | None = None,
                      ) -> list[dict[str, Any]]:
        """Evolve HOLD, STOP and REWARD:RISK with the expression, scored on marginal E[log W].

        THE GAP THIS CLOSES, in the ledger's words: "the genome evolves the expression and side
        mode under a FIXED recipe (hold, stop, rr)". It did: every candidate this organ has ever
        proposed held for 8 bars, stopped at 2 ATR and targeted 1.5R, because `RECIPE` is a
        module constant. An expression whose edge lives at a 24-bar horizon was being scored at
        8 bars and discarded for not having one -- the search was over a slice of the genome and
        reported as a search over the genome.

        COORDINATE ASCENT, NOT A SECOND POPULATION. The expression search runs first and this
        hill-climbs the recipe of each FINALIST, which is the cheap half of a joint search: the
        expensive object is the expression (thousands evaluated), the recipe is three numbers
        with a small feasible range, and sweeping it for the handful of survivors buys most of
        the joint optimum for a few dozen extra screens. Every variant is charged as a trial.

        SCORED ON MARGINAL dE[log W], not on the composite. `alpha_fitness.evaluate` already
        computes `delta_elog` through `robust_elog.marginal_delta_elog` -- the same solver the
        allocator runs -- so the recipe that WINS is the one that adds most growth to the book
        in hand, with the composite score as the tiebreak when the growth term is unmeasured.

        THE BOUNDS ONLY WIDEN. `RECIPE_BOUNDS` brackets the standing defaults on both sides; a
        variant may hold longer or shorter, stop wider or tighter, target more or less. Nothing
        here caps risk: the stop is a MEASUREMENT of the risk unit, and a wider stop with a
        proportionally larger R denominator is the same heat expressed differently.
        """
        import time as _time
        out: list[dict[str, Any]] = []
        ranked = sorted((k for k, r in self.rows.items() if r.get("refined")),
                        key=lambda k: -float(self.rows[k].get("fitness") or -9.0))
        for k in ranked[:top]:
            if deadline is not None and _time.monotonic() > deadline:
                break
            row = self.rows[k]
            expr, side_mode = row["params"]["expr"], row["params"]["side_mode"]
            z = self.zs.get(k)
            if z is None:
                continue
            base = {p: float(RECIPE[p]) for p in RECIPE_BOUNDS}
            best = {"params": dict(base), "delta_elog": None, "score": float(
                row.get("fitness") or -9.0), "n_variants": 0}
            for param, (lo, hi) in RECIPE_BOUNDS.items():
                for mult in RECIPE_STEPS:
                    if deadline is not None and _time.monotonic() > deadline:
                        break
                    trial = dict(best["params"])
                    val = float(np.clip(trial[param] * mult, lo, hi))
                    if abs(val - trial[param]) < 1e-9:
                        continue
                    trial[param] = val
                    try:
                        got = self._score_recipe(expr, side_mode, z, trial, row, k)
                    except Exception as exc:
                        # ONE VARIANT MAY FAIL WITHOUT COSTING THE SEARCH THAT FOUND IT. The
                        # expression population is already evaluated by the time this stage runs;
                        # a screen that raises on one hold length must not discard it.
                        self.recipe_failures.append(f"{k}|{param}={val}: {type(exc).__name__}")
                        continue
                    if got is None:
                        continue
                    best["n_variants"] = int(best["n_variants"]) + 1
                    better = ((got["delta_elog"] or 0.0) > (best["delta_elog"] or 0.0)
                              if (got["delta_elog"] or best["delta_elog"]) is not None
                              else got["score"] > best["score"])
                    if better:
                        best = {**got, "params": trial,
                                "n_variants": int(best["n_variants"])}
            if best["n_variants"]:
                row["params"] = {**row["params"], **{p: (int(v) if p == "hold_bars" else v)
                                                     for p, v in best["params"].items()}}
                row["recipe_evolved"] = {
                    "from": base, "to": best["params"], "n_variants": best["n_variants"],
                    "delta_elog": best["delta_elog"], "score": best["score"],
                    "scored_on": ("marginal_delta_elog against the book in hand"
                                  if best["delta_elog"] is not None else
                                  "composite fitness (the growth term was unmeasured)"),
                    "bounds": {p: list(v) for p, v in RECIPE_BOUNDS.items()}}
                out.append({"key": k, **row["recipe_evolved"]})
                self._archive_put(k, float(best["score"]))
        self.recipe_evolution = out
        return out

    def _score_recipe(self, expr: ag.Expr, side_mode: str, z: pd.Series,
                      trial: dict[str, float], row: dict, key: str) -> dict[str, Any] | None:
        """One recipe variant of one expression, through the same measurement as everything else."""
        merged = {**RECIPE, **trial, "expr": expr, "side_mode": side_mode}
        got = pc.screen(self.d, family_formula(self.d, drivers=self.drivers, **merged),
                        self.cost, self.unfillable)
        if got is None:
            return None
        flip = 1.0 if side_mode == "follow" else -1.0
        hold = max(1, round(float(trial.get("hold_bars", RECIPE["hold_bars"]))))
        entry_z = float(trial.get("entry_z", RECIPE["entry_z"]))
        # The R denominator IS the stop: a wider stop is a larger risk unit, not more risk.
        risk = self.risk_frac * (float(trial.get("stop_atr", RECIPE["stop_atr"]))
                                 / float(RECIPE["stop_atr"]))
        held = _position_path(z * flip, entry_z, hold)
        pnl = _daily_pnl_proxy(z * flip, self.ret, entry_z, hold, risk, held=held)
        refs = [v for kk, v in self.zs.items() if kk != key]
        terms = af.evaluate(self._candidate(expr, side_mode, {**row, **got, "params": merged},
                                            z, pnl, refs, with_fragility=False, key=key,
                                            position=held),
                            self.book, cfg=_search_worlds())
        d_elog = float(terms.as_dict().get("delta_elog") or 0.0)
        return {"delta_elog": (d_elog if d_elog != 0.0 else None),
                "score": float(terms.score())}


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
    #: The dE[logW] ordering this sweep has earned so far. A one-element list because `_draw`
    #: rebinds it; empty until something has been scored, and the file's table stands until then.
    live_weights: list[dict[str, float] | None] = [None]
    ctx = spop.SearchContext(rng=rng, frames=ev.frames, ret=ev.ret, symbol=sym,
                             allow_drivers=allow_drivers, max_depth=DEPTH, cache=ev.cache,
                             seeds=list(ag.CANON.values()))

    def _refresh_context() -> None:
        """The populations learn from what has been scored so far, not from a frozen snapshot."""
        ctx.history = [(r["params"]["expr"], float(r["fitness"])) for r in ev.rows.values()
                       if "fitness" in r]
        ctx.scored = [(ev.rows[k]["params"]["expr"], t) for k, t in ev.terms.items()
                      if k in ev.rows]
        # WHAT EACH POPULATION'S DRAWS WERE WORTH, not how many it drew: the term vector of
        # every scored expression, tagged with the population that made it. `search_populations`
        # turns this into the next pass's ordering (`SearchResult.elog_weights`).
        ctx.attributed = [(ev.origin.get(k, "unspecified"), t) for k, t in ev.terms.items()]
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
        # THE WEIGHTS ARE THE REALISED GROWTH OF WHAT EACH POPULATION PRODUCED once anything has
        # been scored, and the file's table only until then. `live_weights` is rebound after
        # every draw, so the ordering tracks the sweep rather than yesterday's certify counts.
        res = spop.run(ctx, n_per_population=per, budget_s=max(5.0, budget_s / 4.0),
                       weights=live_weights[0] if live_weights[0] else pop_weights)
        got, basis = res.elog_weights()
        if got:
            live_weights[0] = got
            ev.generator_weights["population_weights_live"] = {k: round(v, 5)
                                                               for k, v in sorted(got.items())}
        ev.generator_weights["population_basis_live"] = basis
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
        # THE ARCHIVE BREEDS BESIDE THE ELITE. The elite survives into the next generation as
        # before; the archive's champions are ADDITIONAL parents, so a cell the front no longer
        # holds keeps contributing its genetic material rather than being forgotten.
        parents = _parents(ev, elite)
        children: list[tuple[ag.Expr, str]] = list(elite)
        _pol = search_policy()
        fresh = _draw(max(1, int(pop * _pol["fresh_frac"]))) if elite else []
        while len(children) < pop and time.monotonic() - started <= budget_s:
            if fresh and rng.random() < _pol["fresh_frac"]:
                e, origin = fresh.pop()
                sm = str(rng.choice(SIDE_MODES))
            else:
                a = parents[int(rng.integers(len(parents)))] if parents else (
                    random_or_canon(rng, allow_drivers), str(rng.choice(SIDE_MODES)))
                if rng.random() < 0.5 and len(parents) > 1:
                    b = parents[int(rng.integers(len(parents)))]
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
    # THE REST OF THE GENOME (Tier-1 B5): hold, stop and reward:risk hill-climbed for the
    # finalists on marginal dE[log W], inside bounds that widen the standing recipe in both
    # directions. Bounded by whatever is left of this instrument's budget, and skipped entirely
    # when there is none -- a joint search that overran its clock would cost the cycle the legs
    # after it, which is the failure mode `_producer`'s timeout exists to contain.
    try:
        ev.evolve_recipe(deadline=started + budget_s)
    except Exception as exc:
        ev.recipe_failures.append(f"evolve_recipe: {type(exc).__name__}: {exc}")
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


def _parents(ev: _Evaluator, elite: list[tuple[ag.Expr, str]]) -> list[tuple[ag.Expr, str]]:
    """The elite plus every archive champion the elite does not already hold, in that order."""
    have = {f"{ag.key(e)}|{sm}" for e, sm in elite}
    out = list(elite)
    for e, sm in ev.champions():
        k = f"{ag.key(e)}|{sm}"
        if k not in have:
            have.add(k)
            out.append((e, sm))
    return out


def map_elites_summary(per_symbol: dict[str, dict], regimes_known: tuple[str, ...]) -> dict:
    """Sweep-wide occupancy: cells filled over cells possible, with every axis's cardinality.

    Possible = |mechanism classes| x |horizon buckets| x |regime labels the state vector names|
    x |asset classes swept|. The regime axis is the STATE VECTOR's own vocabulary rather than
    the labels that happened to be filled, so an occupancy of 100% means the search has lit
    every regime the desk can name, not every regime it happened to see this hour.
    """
    filled: set[tuple[str, str, str, str]] = set()
    classes: set[str] = set()
    for info in per_symbol.values():
        me = info.get("map_elites") or {}
        if me.get("asset_class"):
            classes.add(str(me["asset_class"]))
        for c in me.get("cells") or []:
            filled.add((str(c["mechanism_class"]), str(c["horizon"]), str(c["regime"]),
                        str(c["asset_class"])))
    possible = (len(MECHANISM_CLASSES) * len(HORIZON_NAMES) * max(1, len(regimes_known))
                * max(1, len(classes)))
    return {"cells_filled": len(filled), "cells_possible": possible,
            "occupancy": round(len(filled) / possible, 4) if possible else 0.0,
            "axes": {"mechanism_classes": list(MECHANISM_CLASSES),
                     "horizons": list(HORIZON_NAMES), "regimes": list(regimes_known),
                     "asset_classes": sorted(classes)},
            "note": ("one Pareto front forgot every cell it left; the archive keeps the best "
                     "expression per cell and its champions breed beside the elite")}


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


def reward_term_shares(rows: list[dict]) -> dict[str, object]:
    """Per FITNESS TERM: its share of the sweep's total positive credit, and per POPULATION the
    mean of the two breadth terms (Tier-1 D5).

    THE REWARD IS THE FITNESS. `generators.GFlowNet` maps the scored history's fitness to
    R(x) = exp(beta x (f - f_max)) and samples trajectories in proportion to it, so a term added
    to `alpha_fitness.WEIGHTS` is a term the sampler is trained on. This is the measurement that
    the two breadth credits actually moved reward mass: an empty `by_term` means nothing was
    scored this sweep (UNMEASURED), never that the terms are inert.
    """
    scored = [r for r in rows if isinstance(r.get("terms"), dict)]
    if not scored:
        return {"status": "UNMEASURED", "why": "no scored row carries a term vector this sweep"}
    credit: dict[str, float] = {}
    mean: dict[str, float] = {}
    for name, w in af.WEIGHTS.items():
        vals = [float(r["terms"].get(name) or 0.0) for r in scored]
        mean[name] = sum(vals) / len(vals)
        if name not in af.PENALTIES:
            credit[name] = max(0.0, w * sum(vals))
    total = sum(credit.values())
    by_pop: dict[str, dict[str, float]] = {}
    for r in scored:
        pop = str(r.get("population") or "unspecified")
        slot = by_pop.setdefault(pop, {"n": 0.0, "mechanism_distance": 0.0, "axis_scarcity": 0.0})
        slot["n"] += 1.0
        for name in ("mechanism_distance", "axis_scarcity"):
            slot[name] += float(r["terms"].get(name) or 0.0)
    for slot in by_pop.values():
        n = max(1.0, slot["n"])
        for name in ("mechanism_distance", "axis_scarcity"):
            slot[name] = round(slot[name] / n, 4)
    return {"status": "MEASURED", "n_scored": len(scored),
            "by_term": {k: round((v / total) if total > 0 else 0.0, 4)
                        for k, v in sorted(credit.items())},
            "mean_term": {k: round(v, 5) for k, v in sorted(mean.items())},
            "breadth_by_population": by_pop,
            "rule": ("share of the sweep's total positive weighted credit per term; the GFlowNet "
                     "is trained on exactly this fitness, so these ARE the sampler's reward "
                     "proportions (Tier-1 D5)")}


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
                                            "passed": 0, "seconds": 0.0, "note": "",
                                            "scored": 0, "delta_elog_mean": None})
                for k in ("proposed", "unique", "well_formed", "passed"):
                    acc[k] = int(acc[k]) + int(row.get(k) or 0)
                acc["seconds"] = round(float(acc["seconds"]) + float(row.get("seconds") or 0), 2)
                # THE LAST BATCH'S REALISED GROWTH IS THE SWEEP'S: each batch's mean is over
                # every draw scored SO FAR, so the final one already pools the earlier ones and
                # averaging the batches again would weight the early, thin means equally.
                if row.get("delta_elog_mean") is not None:
                    acc["delta_elog_mean"] = float(row["delta_elog_mean"])
                    acc["scored"] = int(row.get("scored") or 0)
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
                           "subtree_cache": ev.cache.stats(),
                           "map_elites": ev.archive_report()}
        generator_weights = ev.generator_weights
        generator_failures.extend(f"{sym}: {f}" for f in ev.generator_failures)
    # Every distinct expression tried is a trial; stage-0-only rows may not be proposed.
    rows = pc.deflate(rows)
    n_screened = 0
    for r in rows:
        if r.get("stage") != 1:
            r["proposed"] = False
        why = ic_screen(r)
        if why is not None and r.get("proposed"):
            r["proposed"] = False
            r["screened"] = why
            n_screened += 1
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
                                        "ic_mean", "ic_ir", "ic_sign", "ic_n",
                                        "unmeasured", "tail", "generator")},
    ) for r in proposals]
    pops = population_yield(per_symbol)
    report = {"generated_at": datetime.now(tz=UTC).isoformat(), "symbols_swept": len(todo),
              "tests_run": len(rows), "cells_proposed": len(proposals), "skipped": skipped,
              "ic_screened": n_screened,
              "ic_screen_rule": (f"|ic_mean| >= {IC_MIN_ABS} and sign agreement >= "
                                 f"{IC_SIGN_MIN} over {IC_FOLDS} disjoint folds; screened rows "
                                 "stay counted as trials"),
              "per_symbol": per_symbol, "proposals": proposals,
              # THE YIELD LEDGER'S INPUT: which population's individuals were tried, went
              # full-sample and were proposed, sweep-wide, beside the weights that were read.
              # Whatever writes data/generator_weights.json reads this.
              "generator_yield": generator_yield(rows),
              "population_yield": pops,
              "generator_weights": generator_weights,
              "search_policy": search_policy(),
              "generator_failures": generator_failures,
              # THE FITNESS, NAMED. Which terms could be measured this sweep and which could
              # not: a fitness computed on an empty desk must never read like one computed
              # against a full book.
              "fitness_weights": dict(af.WEIGHTS),
              # WHICH TERM BOUGHT THE SAMPLING (Tier-1 D5). The GFlowNet's reward IS this
              # fitness -- R(x) = exp(beta x (f - f_max)) over the scored history -- so adding
              # `mechanism_distance` and `axis_scarcity` to the fitness IS training the sampler
              # on the augmented reward. This says by how much: each term's share of the total
              # positive credit, and each POPULATION's mean on the two breadth terms, so a
              # generation that converged on one mode is visible as a number rather than a
              # suspicion.
              "reward_terms": reward_term_shares(rows),
              # THE ARCHIVE'S OCCUPANCY: how much of the descriptor space the search has lit.
              "map_elites": map_elites_summary(per_symbol, regime_labels_known()),
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
    print("populations (proposed/unique/well-formed/passed  dE[logW] over scored):")
    for name, y in sorted(rep.get("population_yield", {}).items()):
        el = ("     --" if y.get("delta_elog_mean") is None
              else f"{y['delta_elog_mean']:+6.3f}")
        print(f"  {name:20s} {y['proposed']:4d}/{y['unique']:4d}/{y['well_formed']:4d}/"
              f"{y['passed']:4d}  {y['seconds']:6.1f}s  {el} over {y.get('scored', 0):3d}"
              f"  {y['note'][:44]}")
    print(f"  population ordering: {rep['generator_weights'].get('population_basis_live') or ''}")
    print("outcomes: " + ", ".join(
        f"{g}={y['tried']}/{y['full']}/{y['proposed']}" for g, y in rep["generator_yield"].items())
        + f"  (weights: {rep['generator_weights'].get('population_basis')})")
    print(f"book: {rep.get('book')}   unmeasured terms: "
          f"{', '.join(rep.get('unmeasured_terms') or []) or 'none'}")
    me = rep.get("map_elites") or {}
    print(f"archive: {me.get('cells_filled', 0)} / {me.get('cells_possible', 0)} descriptor "
          f"cells lit ({100 * float(me.get('occupancy') or 0):.1f}%)")
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
