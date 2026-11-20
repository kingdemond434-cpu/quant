"""THE STRATEGY BUILDER: a genetic search over entries x filters x exits, proposing `rule_builder`
cells to the gauntlet -- the StrategyQuant / Adaptrade / retail-builder shape the desk lacked.

WHY A SECOND GENETIC SEARCH (zuck, 2026-11-20: "add every form of generator"). `alpha_evolution`
evolves FORMULAS over `alpha_grammar` (nine populations: NSGA-II GP, GFlowNet, symbolic
regression, program synthesis, TPE, zoo mutation, graveyard/causal/claims-derived). None of them
evolves a RULE STRATEGY: a conjunction of familiar entry blocks, a regime/session/trend gate, and
its own stop, target and hold. That space is discrete and exit-aware, and edges living there
(breakout-in-session-with-trend, oversold-in-low-vol-fade, ...) are invisible to a formula search
whose exit is a fixed threshold recipe. See `mt5desk/family_rule_builder.py` for the cell.

ONE POPULATION PER (symbol, chart), PERSISTED, NEVER RESTARTED. Each pass loads the population,
evolves it inside its time budget (tournament selection, uniform crossover of blocks/filters/exit
genes, point mutation, fresh immigrants), and saves it. So the search keeps compounding 24/7 on
every hypothesis-lane MT5 symbol, least-judged symbols first (`breadth_rotation.orthogonal_ring`).

THE GAUNTLET IS NEVER INFLATED -- four rails, all on by construction:
  1. RESERVED TAIL. The last RESERVE_FRAC of every symbol's bars is cut off BEFORE the search
     sees the frame. The gauntlet's own walk-forward, CPCV and lockbox read the full history; the
     builder can never have fitted the period those gates rule on last.
  2. WALK-FORWARD FITNESS. Inside the visible window, fitness is the worst-fold-weighted Kelly
     growth across WF_FOLDS anchored folds of the TRAIN part only (mean - 0.5 sd). One lucky
     year cannot carry a genome.
  3. VALIDATION READ ONCE, DEFLATED AT THE LINEAGE'S FULL COUNT. The validation slice is read
     only at harvest. A genome is proposed only if its validation trades clear the Deflated
     Sharpe Ratio at n_trials = EVERY genome this lineage has ever evaluated, AND the harvest
     batch clears Benjamini-Hochberg FDR at FDR_Q.
  4. THE SEARCH IS CHARGED DOWNSTREAM. Every proposed row carries `claim_family` (one stable id
     per lineage) and `claim_selection_trials` = the lineage's lifetime evaluated count, and the
     whole lineage is registered through `libs.research.claim_selection.register_grid`, so the
     trial ledger charges the search ONCE to the family and its cells count as ONE breadth unit.

VOLUME FOLLOWS THE JUDGE (`intake_budget`). Searching never stops; what is DONATED per pass is
sized from `reports/JUDGING_RATE.json`: a share of the judge's measured net drain when the
backlog is DRAINING, and only the small exploration floor while it is GROWING or UNMEASURED.
Survivors over the cap stay in the lineage's archive, ranked, and go first next pass -- an order
of service, never a deletion (GROWTH_GOVERNANCE rule 1).

    python desks/mt5/research/strategy_builder.py [--budget-s 240] [--symbols 6] [--dry-run]
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import random
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _p in (str(ROOT), str(BASE), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SEAT = "strategy_builder"
FAMILY = "rule_builder"
STATE = BASE / "data" / "strategy_builder"
REPORT = BASE / "reports" / "STRATEGY_BUILDER.json"
JUDGING_RATE = BASE / "reports" / "JUDGING_RATE.json"
YIELD_PREFIX = "YIELD "

RESERVE_FRAC = 0.30
VALID_FRAC = 0.35
WF_FOLDS = 4
POP = 60
ELITE = 4
TOURNAMENT = 4
MIN_TRAIN_TRADES = 40
MIN_VALID_TRADES = 15
DSR_MIN = 0.95
FDR_Q = 0.10
ARCHIVE = 40
#: Archive niche per mechanism class (MAP-Elites style): the best genomes of EACH class are kept,
#: so the population cannot collapse onto one style.
ARCHIVE_PER_CLASS = 8
#: Charts searched, each wherever `<SYM>_<chart>.parquet` exists.
CHARTS: tuple[str, ...] = ("M15", "M30", "H1", "H4", "D1")
#: Fill-cost gate: a (symbol, chart) whose round trip (2x median spread) exceeds this fraction of
#: its median ATR is not searched -- no exit geometry pays it. Exotics get turns exactly where
#: their real spread allows.
MAX_COST_ATR = 0.25
COVERAGE = STATE / "coverage.json"
DUP_JACCARD = 0.7
#: Donation sizing (see `intake_budget`). Share of the judge's measured net drain per day this
#: seat may claim, spread over the passes in a day, and the floor it always keeps.
DRAIN_SHARE = float(os.environ.get("STRATEGY_BUILDER_DRAIN_SHARE", "0.05"))
PASSES_PER_DAY = 24
EXPLORE_FLOOR = int(os.environ.get("STRATEGY_BUILDER_FLOOR", "6"))
MAX_PER_PASS = 400
EULER = 0.5772156649015329


# --------------------------------------------------------------------------- statistics
def _ncdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _nppf(p: float) -> float:
    """Inverse normal by bisection on erf: exact enough for a hurdle, no scipy."""
    p = min(max(p, 1e-12), 1 - 1e-12)
    lo, hi = -10.0, 10.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if _ncdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def deflated_sharpe(r: np.ndarray, n_trials: int, sr_var: float | None = None) -> float:
    """Bailey & Lopez de Prado DSR on per-trade R: P(true SR > E[max SR of n_trials nulls])."""
    r = np.asarray(r, dtype=float)
    r = r[np.isfinite(r)]
    n = r.size
    if n < 10 or r.std(ddof=1) <= 1e-12:
        return 0.0
    sr = r.mean() / r.std(ddof=1)
    c = r - r.mean()
    m2 = float((c ** 2).mean())
    skew = float((c ** 3).mean() / m2 ** 1.5)
    kurt = float((c ** 4).mean() / m2 ** 2)
    v = sr_var if sr_var and sr_var > 0 else 1.0 / n
    k = max(int(n_trials), 2)
    sr0 = math.sqrt(v) * ((1 - EULER) * _nppf(1 - 1.0 / k) + EULER * _nppf(1 - 1.0 / (k * math.e)))
    den = 1 - skew * sr + (kurt - 1) / 4.0 * sr * sr
    if den <= 0:
        return 0.0
    return _ncdf((sr - sr0) * math.sqrt(n - 1) / math.sqrt(den))


def bh_fdr(pvals: list[float], q: float = FDR_Q) -> list[bool]:
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    k = 0
    for rank, i in enumerate(order, 1):
        if pvals[i] <= q * rank / m:
            k = rank
    keep = [False] * m
    for rank, i in enumerate(order, 1):
        keep[i] = rank <= k
    return keep


def kelly_growth(r: np.ndarray, trades_per_year: float) -> float:
    """Signed annual log growth at Kelly leverage for an R stream: sign(mu) mu^2/(2 var) x rate."""
    r = r[np.isfinite(r)]
    if r.size < 5:
        return 0.0
    var = float(r.var(ddof=1))
    if var <= 1e-12:
        return 0.0
    mu = float(r.mean())
    return math.copysign(mu * mu / (2 * var), mu) * trades_per_year


# --------------------------------------------------------------------------- genome
def _rule_space():
    from mt5desk.family_rule_builder import BLOCKS, FILTERS
    return BLOCKS, FILTERS


EXIT_SPACE = {"stop_atr": [0.75, 1.0, 1.5, 2.0, 2.5, 3.0], "rr": [0.75, 1.0, 1.5, 2.0, 3.0, 4.0],
              "max_hold_bars": [4, 8, 12, 24, 48, 96, 168], "expansion_mult": [0.0, 0.0, 2.0, 4.0],
              "atr_n": [14, 24]}


def mech_class(g: dict) -> str:
    """The genome's primary mechanism: its first entry block's class."""
    from mt5desk.family_rule_builder import MECH_CLASS
    e = g.get("entry") or [{}]
    return MECH_CLASS.get(str(e[0].get("b")), "other")


def _rand_block(rng: random.Random, cls: str | None = None) -> dict:
    blocks, _ = _rule_space()
    names = sorted(blocks)
    if cls:
        from mt5desk.family_rule_builder import MECH_CLASS
        names = [n for n in names if MECH_CLASS.get(n) == cls] or names
    name = rng.choice(names)
    return {"b": name, **{k: rng.choice(v) for k, v in blocks[name][1].items()}}


def _rand_filter(rng: random.Random) -> dict:
    _, filters = _rule_space()
    name = rng.choice(sorted(filters))
    return {"f": name, **{k: rng.choice(v) for k, v in filters[name][1].items()}}


def random_genome(rng: random.Random, cls: str | None = None) -> dict:
    g = {"entry": [_rand_block(rng, cls)] + [_rand_block(rng)
                                              for _ in range(rng.choice((0, 0, 1, 1, 2)))],
         "filters": [_rand_filter(rng) for _ in range(rng.choice((0, 1, 1, 2)))],
         "invert": rng.random() < 0.5}
    g.update({k: rng.choice(v) for k, v in EXIT_SPACE.items()})
    return g


def key(g: dict) -> str:
    return json.dumps(g, sort_keys=True, default=str)


def crossover(rng: random.Random, a: dict, b: dict) -> dict:
    pool_e = a["entry"] + b["entry"]
    pool_f = a["filters"] + b["filters"]
    c = {"entry": rng.sample(pool_e, k=min(len(pool_e), rng.choice((1, 2, 2, 3)))),
         "filters": rng.sample(pool_f, k=min(len(pool_f), rng.choice((0, 1, 1, 2)))),
         "invert": rng.choice((a["invert"], b["invert"]))}
    for k in EXIT_SPACE:
        c[k] = rng.choice((a[k], b[k]))
    return json.loads(key(c))


def mutate(rng: random.Random, g: dict) -> dict:
    c = json.loads(key(g))
    blocks, _filters = _rule_space()
    r = rng.random()
    if r < 0.30:                                           # exit gene
        k = rng.choice(sorted(EXIT_SPACE))
        c[k] = rng.choice(EXIT_SPACE[k])
    elif r < 0.55 and c["entry"]:                          # block parameter
        b = rng.choice(c["entry"])
        space = blocks[b["b"]][1]
        if space:
            p = rng.choice(sorted(space))
            b[p] = rng.choice(space[p])
    elif r < 0.70:                                         # swap / add / drop a block
        if len(c["entry"]) < 3 and rng.random() < 0.5:
            c["entry"].append(_rand_block(rng))
        elif len(c["entry"]) > 1:
            c["entry"].pop(rng.randrange(len(c["entry"])))
        else:
            c["entry"][0] = _rand_block(rng)
    elif r < 0.85:                                         # filter
        if c["filters"] and rng.random() < 0.4:
            c["filters"].pop(rng.randrange(len(c["filters"])))
        elif len(c["filters"]) < 2:
            c["filters"].append(_rand_filter(rng))
        else:
            c["filters"][rng.randrange(2)] = _rand_filter(rng)
    else:
        c["invert"] = not c["invert"]
    return c


# --------------------------------------------------------------------------- evaluation
class Lineage:
    """One persisted population for one (symbol, chart)."""

    def __init__(self, sym: str, chart: str, d: pd.DataFrame, costs: Any, seed: int = 0,
                 state_dir: Path = STATE):
        self.sym, self.chart = sym, chart
        self.path = Path(state_dir) / f"{sym}_{chart}.json"
        self.rng = random.Random(f"{sym}|{chart}|{seed}|{time.time_ns()}")  # noqa: S311 (search, not crypto)
        n = len(d)
        cut = int(n * (1 - RESERVE_FRAC))
        self.visible = d.iloc[:cut]                       # rail 1: the tail is never read
        self.reserved_from = d.index[cut] if cut < n else d.index[-1]
        vis_idx = self.visible.index
        self.valid_from = vis_idx[int(len(vis_idx) * (1 - VALID_FRAC))]
        t_idx = vis_idx[vis_idx < self.valid_from]
        start = int(len(t_idx) * 0.25)
        step = max(1, (len(t_idx) - start) // WF_FOLDS)
        self.fold_edges = [t_idx[min(start + i * step, len(t_idx) - 1)] for i in range(WF_FOLDS)]
        self.fold_edges.append(self.valid_from)
        years = max((t_idx[-1] - t_idx[0]).days / 365.25, 0.25) if len(t_idx) > 1 else 1.0
        self.train_years = years
        self.costs = costs
        self.pop: list[dict] = []
        self.archive: list[dict] = []                      # {"g", "fit", "entries"}
        self.evaluated_total = 0
        self.evaluated_now = 0
        self.proposed: set[str] = set()
        self._cache: dict[str, tuple[float, Any]] = {}
        self._load()

    def _load(self) -> None:
        try:
            st = json.loads(self.path.read_text("utf-8"))
        except (OSError, ValueError):
            st = {}
        self.pop = [g for g in st.get("pop", []) if isinstance(g, dict)]
        self.archive = [a for a in st.get("archive", []) if isinstance(a, dict)]
        self.evaluated_total = int(st.get("evaluated_total") or 0)
        self.proposed = set(st.get("proposed") or [])
        while len(self.pop) < POP:
            self.pop.append(random_genome(self.rng))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        st = {"symbol": self.sym, "chart": self.chart, "pop": self.pop,
              "archive": [{"g": a["g"], "fit": a["fit"], "entries": a.get("entries", [])[:2000]}
                          for a in self.archive],
              "evaluated_total": self.evaluated_total, "proposed": sorted(self.proposed),
              "reserved_from": str(self.reserved_from), "valid_from": str(self.valid_from),
              "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(st, default=str), "utf-8")
        tmp.replace(self.path)

    @property
    def claim_family(self) -> str:
        from libs.research.claim_selection import claim_family_id
        return claim_family_id(SEAT, f"{self.sym}|{self.chart}|{FAMILY}")

    def trades(self, g: dict) -> tuple[np.ndarray, np.ndarray] | None:
        """(entry time ns, R multiple) of every trade on the VISIBLE window."""
        from mt5desk.engine import run_backtest
        from mt5desk.families import get_family_func
        fn = get_family_func(FAMILY)
        try:
            sigs = fn(self.visible, **g)
            res = run_backtest(self.visible, sigs, self.costs)
        except Exception:
            return None
        if not res.trades:
            return np.zeros(0, dtype="int64"), np.zeros(0)
        t = np.array([pd.Timestamp(x.entry_time).value for x in res.trades], dtype="int64")
        r = np.array([x.r_multiple for x in res.trades], dtype=float)
        return t, r

    def fitness(self, g: dict) -> float:
        k = key(g)
        if k in self._cache:
            return self._cache[k][0]
        self.evaluated_now += 1
        tr = self.trades(g)
        if tr is None:
            self._cache[k] = (-1e9, None)
            return -1e9
        t, r = tr
        vf = pd.Timestamp(self.valid_from).value
        train = t < vf
        if int(train.sum()) < MIN_TRAIN_TRADES:
            self._cache[k] = (-1e6 + float(train.sum()), (t, r))
            return self._cache[k][0]
        edges = [pd.Timestamp(e).value for e in self.fold_edges]
        fold_years = self.train_years / WF_FOLDS
        gs = []
        for a, b in itertools.pairwise(edges):
            m = (t >= a) & (t < b)
            gs.append(kelly_growth(r[m], max(m.sum(), 1) / max(fold_years, 1e-3)))
        complexity = len(g["entry"]) + len(g["filters"])
        f = float(np.mean(gs) - 0.5 * np.std(gs)) - 0.002 * complexity   # rail 2
        self._cache[k] = (f, (t, r))
        return f

    def _tour(self, scored):
        return max(self.rng.sample(scored, min(TOURNAMENT, len(scored))), key=lambda x: x[0])[1]

    def evolve(self, deadline: float) -> int:
        gens = 0
        while time.monotonic() < deadline:
            scored = [(self.fitness(g), g) for g in self.pop]
            scored.sort(key=lambda x: -x[0])
            self._archive(scored)
            nxt = [g for _, g in scored[:ELITE]]
            while len(nxt) < POP:
                u = self.rng.random()
                if u < 0.45:
                    child = crossover(self.rng, self._tour(scored), self._tour(scored))
                elif u < 0.90:
                    child = mutate(self.rng, self._tour(scored))
                else:
                    child = random_genome(self.rng, self._scarcest_class())
                if child["entry"]:
                    nxt.append(child)
            self.pop = nxt
            gens += 1
        self.evaluated_total += self.evaluated_now
        return gens

    def _scarcest_class(self) -> str:
        """The mechanism class with the fewest archive members: immigrants are seeded there."""
        from mt5desk.family_rule_builder import MECH_CLASS
        counts = dict.fromkeys(sorted(set(MECH_CLASS.values())), 0)
        for a in self.archive:
            c = mech_class(a["g"])
            counts[c] = counts.get(c, 0) + 1
        low = min(counts.values())
        return self.rng.choice([c for c, n in counts.items() if n == low])

    def _archive(self, scored) -> None:
        vf = pd.Timestamp(self.valid_from).value
        for f, g in scored[:10]:
            if f <= 0:
                break
            k = key(g)
            if any(key(a["g"]) == k for a in self.archive):
                continue
            t, _ = self._cache[k][1]
            ent = {int(x) for x in t[t < vf]}
            dup = None
            for a in self.archive:                       # orthogonality: same trades = same edge
                other = set(a.get("entries") or [])
                j = len(ent & other) / max(1, len(ent | other))
                if j > DUP_JACCARD:
                    dup = a
                    break
            if dup is not None:
                if f > dup["fit"]:
                    self.archive.remove(dup)
                else:
                    continue
            self.archive.append({"g": g, "fit": f, "entries": sorted(ent)})
        self.archive.sort(key=lambda a: -a["fit"])
        kept, per = [], {}
        for a in self.archive:                           # per-class niche, then the global cap
            c = mech_class(a["g"])
            if per.get(c, 0) < ARCHIVE_PER_CLASS:
                per[c] = per.get(c, 0) + 1
                kept.append(a)
        self.archive = kept[:ARCHIVE]

    def harvest(self) -> list[dict]:
        """Validation-gate the archive at the lineage's lifetime trial count (rail 3)."""
        n_trials = max(self.evaluated_total, 1)
        vf = pd.Timestamp(self.valid_from).value
        rows = []
        for a in self.archive:
            k = key(a["g"])
            if k in self.proposed:
                continue
            tr = self._cache.get(k, (None, None))[1] or self.trades(a["g"])
            if tr is None:
                continue
            t, r = tr
            rv = r[t >= vf]
            if rv.size < MIN_VALID_TRADES or rv.mean() <= 0:
                continue
            sd = rv.std(ddof=1)
            sr = rv.mean() / sd if sd > 0 else 0.0
            rows.append({"a": a, "rv": rv, "sr": sr,
                         "p": 1 - _ncdf(sr * math.sqrt(rv.size)),
                         "train_n": int((t < vf).sum())})
        if not rows:
            return []
        srs = [x["sr"] for x in rows]
        sr_var = float(np.var(srs)) if len(srs) > 2 else None
        keep = bh_fdr([x["p"] for x in rows])
        out = []
        for x, ok in zip(rows, keep, strict=False):
            dsr = deflated_sharpe(x["rv"], n_trials, sr_var)
            if not ok or dsr < DSR_MIN:
                continue
            out.append(self._row(x["a"], x["rv"], dsr, x["p"], x["train_n"], n_trials))
        out.sort(key=lambda r: -r["evidence"]["valid_dsr"])
        return out

    def _row(self, a: dict, rv: np.ndarray, dsr: float, p: float, train_n: int,
             n_trials: int) -> dict:
        g = a["g"]
        params = {**g, "timeframe": self.chart}
        blocks = " AND ".join(b["b"] for b in g["entry"])
        flt = ", ".join(f["f"] for f in g["filters"]) or "none"
        note = (f"Genetic rule search (strategy_builder) on {self.sym} {self.chart}: best of "
                f"{n_trials} searched variations in this lineage; the reserved last "
                f"{int(RESERVE_FRAC * 100)}% of history was never read by the search.")
        return {
            "kind": "hypothesis", "source": SEAT, "family": FAMILY, "symbol": self.sym,
            "symbols": [self.sym], "params": params,
            "mechanism": (f"{'fade' if g['invert'] else 'follow'} {blocks} gated by {flt}; "
                          f"{g['stop_atr']} ATR stop, {g['rr']}R target, {g['max_hold_bars']} "
                          "bar hold"),
            "mechanism_status": "GENERATED", "mechanism_note": note,
            "mechanism_class": mech_class(g),
            "title": f"rule_builder {self.sym} {self.chart}: {blocks} | {flt}",
            "url": "", "event_time": None,
            "claim_family": self.claim_family, "claim_selection_trials": int(n_trials),
            "breadth_unit": self.claim_family,
            "evidence": {"train_fitness": round(float(a["fit"]), 6), "train_trades": train_n,
                         "valid_trades": int(rv.size), "valid_mean_r": round(float(rv.mean()), 4),
                         "valid_dsr": round(float(dsr), 4), "valid_p": round(float(p), 6),
                         "search_trials": int(n_trials), "fdr_q": FDR_Q,
                         "valid_from": str(self.valid_from),
                         "reserved_from": str(self.reserved_from),
                         "screen": "walk-forward train folds, validation once, DSR at lifetime "
                                   "lineage trials + BH-FDR; the gauntlet judges"},
        }


# --------------------------------------------------------------------------- volume
def intake_budget(path: Path = JUDGING_RATE) -> dict[str, Any]:
    """Rows this pass may donate, from the judge's own measured rate. Fail closed to the floor."""
    try:
        rate = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {"cap": EXPLORE_FLOOR, "basis": "JUDGING_RATE unreadable: exploration floor"}
    eta = rate.get("eta_to_drain") or {}
    status = eta.get("status")
    if rate.get("status") != "MEASURED" or status in (None, "UNMEASURED"):
        return {"cap": EXPLORE_FLOOR, "basis": "judge rate UNMEASURED: exploration floor"}
    if status == "DRAINED":
        fj = rate.get("first_judged_per_day")
        per_day = float(fj) if isinstance(fj, (int, float)) else 0.0
        cap = int(DRAIN_SHARE * per_day / PASSES_PER_DAY)
        return {"cap": max(EXPLORE_FLOOR, min(MAX_PER_PASS, cap)),
                "basis": f"backlog drained; {DRAIN_SHARE:.0%} of {per_day:.0f} judged/day"}
    if status == "DRAINING":
        net_day = float(eta.get("net_per_hour") or 0.0) * 24.0
        cap = int(DRAIN_SHARE * net_day / PASSES_PER_DAY)
        return {"cap": max(EXPLORE_FLOOR, min(MAX_PER_PASS, cap)),
                "basis": f"draining {net_day:.0f}/day net; {DRAIN_SHARE:.0%} share"}
    return {"cap": EXPLORE_FLOOR,
            "basis": f"backlog {status}: exploration floor only, survivors wait ranked"}


# --------------------------------------------------------------------------- the pass
def _legal_symbols() -> list[str]:
    from htf_anchor_proposer import _legal_symbols as legal
    return legal()


def _costs(sym: str, meta: dict) -> Any:
    from mt5desk.engine import Costs
    src = meta.get("symbols", meta) if isinstance(meta, dict) else {}
    row = src.get(sym) if isinstance(src, dict) else None
    if not isinstance(row, dict):
        return None
    try:
        return Costs.from_symbol(row, mult=2.0)
    except Exception:
        return None


def cost_over_atr(d: pd.DataFrame, costs: Any) -> float | None:
    """Round trip (at the 2x-spread baseline) as a fraction of the chart's median ATR."""
    try:
        from mt5desk.families import _atr
        rt = float(costs.per_oz_roundtrip()) / float(costs.contract_oz)
        atr = float(_atr(d, 14).median())
    except Exception:
        return None
    if not (math.isfinite(rt) and math.isfinite(atr)) or atr <= 0:
        return None
    return rt / atr


def _coverage(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def pick_cells(symbols: list[str], n: int, loader, meta: dict, cov: dict,
               charts: tuple[str, ...] = CHARTS) -> tuple[list[tuple[str, str, Any, Any]], dict]:
    """The (symbol, chart) cells this pass searches: least-searched first, liquid first within a
    tie, never one the fill-cost gate refuses. One chart per symbol per pass, so n cells cover n
    symbols; the least-searched chart of each symbol goes first, so every chart gets turns."""
    passes = cov.get("passes") or {}
    cand = sorted(((passes.get(f"{s}|{c}", 0), s, c) for s in symbols for c in charts),
                  key=lambda x: (x[0], x[1], charts.index(x[2])))
    picked: list[tuple[str, str, Any, Any]] = []
    refused: dict[str, str] = {}
    used: set[str] = set()
    for _, sym, chart in cand:
        if len(picked) >= n:
            break
        if sym in used:
            continue
        d = loader(sym, chart)
        if d is None or len(d) < 2000:
            continue
        costs = _costs(sym, meta)
        if costs is None:
            refused[f"{sym}|{chart}"] = "no cost row"
            continue
        d = d.copy()
        d.index = pd.DatetimeIndex(pd.to_datetime(d.index, utc=True, errors="coerce"))
        d = d[~d.index.isna()]
        ca = cost_over_atr(d, costs)
        if ca is None or ca > MAX_COST_ATR:
            refused[f"{sym}|{chart}"] = f"fill cost {ca if ca is None else round(ca, 3)} x ATR"
            continue
        picked.append((sym, chart, d, costs))
        used.add(sym)
    return picked, refused


def _cost_bps(d: pd.DataFrame, costs: Any) -> float | None:
    try:
        rt = float(costs.per_oz_roundtrip()) / float(costs.contract_oz)
        px = float(d["close"].iloc[-1])
        return rt / px * 1e4 if px > 0 else None
    except Exception:
        return None


def _genome_of(row: dict) -> dict:
    """The genome a donated row carries: its params without the chart."""
    return {k: v for k, v in row["params"].items() if k != "timeframe"}


def interleave(rows: list[dict], cap: int) -> list[dict]:
    """Deal donations round-robin over (symbol, chart, mechanism class) buckets, best first in
    each, so no single cell or style takes the pass's cap."""
    buckets: dict[tuple, list[dict]] = {}
    for r in sorted(rows, key=lambda r: -r["evidence"]["valid_dsr"]):
        k = (r["symbol"], r["params"].get("timeframe"), r.get("mechanism_class"))
        buckets.setdefault(k, []).append(r)
    out: list[dict] = []
    while len(out) < cap and any(buckets.values()):
        for k in sorted(buckets, key=lambda k: -buckets[k][0]["evidence"]["valid_dsr"]
                        if buckets[k] else 0):
            if buckets[k] and len(out) < cap:
                out.append(buckets[k].pop(0))
    return out


def allocate_donations(rows: list[dict], cap: int, cov: dict,
                       cost_bps: dict[str, float]) -> tuple[list[dict], dict[str, Any]]:
    """Choose this pass's donations through the desk's ONE breadth allocator
    (`libs/ops/breadth_allocator`): per-cell / symbol / mechanism / timeframe share caps, a quota
    for cells never donated before, a near-duplicate-of-book penalty and the per-timeframe fill
    cost budget. Falls back to the round-robin `interleave` only if the module is missing."""
    try:
        from libs.ops.breadth_allocator import Candidate, Limits, allocate
    except Exception as exc:
        return interleave(rows, cap), {"allocator": f"fallback interleave: {type(exc).__name__}"}
    by_id: dict[str, dict] = {}
    cands = []
    for r in rows:
        tf = str(r["params"].get("timeframe"))
        cid = f"{r['symbol']}|{tf}|" + key(_genome_of(r))
        by_id[cid] = r
        cands.append(Candidate(cell_id=cid, symbol=r["symbol"], timeframe=tf,
                               family=f"{FAMILY}:{r.get('mechanism_class')}", producer=SEAT,
                               base_score=float(r["evidence"]["valid_dsr"]),
                               corr_to_book=r.get("corr_to_book"),
                               cost_bps=cost_bps.get(f"{r['symbol']}|{tf}")))
    donated = cov.get("donated") or {}
    coverage = {tuple(k.split("|", 2)): int(v) for k, v in donated.items() if k.count("|") == 2}
    dec = allocate(cands, Limits(budget=cap), coverage=coverage)
    why: dict[str, int] = {}
    for _, reason in dec.deferred:
        why[reason] = why.get(reason, 0) + 1
    return [by_id[c.cell_id] for c in dec.selected], {"allocator": "libs.ops.breadth_allocator",
                                                       "deferred_by_reason": why}


def run(budget_s: float = 240.0, n_symbols: int = 6, chart: str | None = None,
        dry_run: bool = False, symbols: list[str] | None = None, state_dir: Path = STATE,
        loader=None, meta: dict | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    if meta is None:
        try:
            meta = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))
        except (OSError, ValueError):
            meta = {}
    if symbols is None:
        symbols = _legal_symbols()
    if loader is None:
        from htf_anchor_proposer import _bars
        loader = _bars
    charts = (chart,) if chart else CHARTS
    cov = _coverage(state_dir / "coverage.json")
    cells, refused = pick_cells(symbols, n_symbols, loader, meta, cov, charts)
    per = max(10.0, budget_s * 0.85 / max(1, len(cells)))
    found: list[dict] = []
    lineages: dict[tuple[str, str], Lineage] = {}
    stats: dict[str, Any] = {}
    for sym, ch, d, costs in cells:
        lin = Lineage(sym, ch, d, costs, state_dir=state_dir)
        gens = lin.evolve(time.monotonic() + per)
        rows = lin.harvest()
        lineages[(sym, ch)] = lin
        found += rows
        classes: dict[str, int] = {}
        for a in lin.archive:
            classes[mech_class(a["g"])] = classes.get(mech_class(a["g"]), 0) + 1
        stats[f"{sym}|{ch}"] = {"generations": gens, "evaluated_pass": lin.evaluated_now,
                                "evaluated_lifetime": lin.evaluated_total,
                                "archive": len(lin.archive), "archive_classes": classes,
                                "best_fit": (round(lin.archive[0]["fit"], 5)
                                             if lin.archive else None),
                                "survivors": len(rows)}
    budget = intake_budget()
    cost_bps = {f"{sym}|{ch}": c for sym, ch, c in
                ((sym, ch, _cost_bps(d, costs)) for sym, ch, d, costs in cells) if c is not None}
    donate_rows, alloc = allocate_donations(found, budget["cap"], cov, cost_bps)
    donated = None
    lineage_reg: Any = None
    if donate_rows and not dry_run:
        try:
            from libs.research.claim_selection import register_grid
            lineage_reg = register_grid(found)
        except Exception as exc:
            lineage_reg = {"status": f"FAILED: {type(exc).__name__}: {exc}"}
        from proposer_common import donate
        tests = sum(int(s.get("evaluated_pass") or 0) for s in stats.values()
                    if isinstance(s, dict))
        donated = donate(SEAT, donate_rows, tests_run=tests)
        if donated is not None:
            for r in donate_rows:
                lineages[(r["symbol"], r["params"]["timeframe"])].proposed.add(
                    key(_genome_of(r)))
    if not dry_run:
        for lin in lineages.values():
            lin.save()
        passes = cov.setdefault("passes", {})
        for (sym, ch) in lineages:
            passes[f"{sym}|{ch}"] = int(passes.get(f"{sym}|{ch}", 0)) + 1
        cov["refused_fill_cost"] = refused
        if donated is not None:
            dn = cov.setdefault("donated", {})
            for r in donate_rows:
                k = f"{r['symbol']}|{r['params']['timeframe']}|{FAMILY}:{r.get('mechanism_class')}"
                dn[k] = int(dn.get(k, 0)) + 1
        cov["at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "coverage.json").write_text(json.dumps(cov, indent=1), "utf-8")
    rep = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "seat": SEAT,
           "family": FAMILY, "cells": stats, "refused_fill_cost": refused,
           "breadth": {"cells_searched_ever": len(cov.get("passes") or {}),
                       "cells_possible": len(symbols) * len(charts),
                       "survivor_classes": sorted({r.get("mechanism_class") for r in found}),
                       "donated_symbols": len({r["symbol"] for r in donate_rows})},
           "tests_run": sum(int(s.get("evaluated_pass") or 0) for s in stats.values()
                            if isinstance(s, dict)),
           "survivors": len(found), "intake_budget": budget, "allocation": alloc,
           "donated": len(donate_rows) if donated is not None else 0,
           "donation_path": str(donated) if donated else None,
           "waiting_ranked": max(0, len(found) - len(donate_rows)),
           "lineage_registration": lineage_reg, "seconds": round(time.monotonic() - t0, 1),
           "rails": {"reserve_frac": RESERVE_FRAC, "valid_frac": VALID_FRAC,
                     "wf_folds": WF_FOLDS, "dsr_min": DSR_MIN, "fdr_q": FDR_Q}}
    if not dry_run:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(rep, indent=1, default=str), "utf-8")
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--symbols", type=int, default=6)
    ap.add_argument("--chart", default=None, help="one chart only (default: every chart)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    rep = run(budget_s=a.budget_s, n_symbols=a.symbols, chart=a.chart, dry_run=a.dry_run)
    print(f"STRATEGY BUILDER  {len(rep['cells'])} symbol x chart cells, "
          f"{rep['tests_run']} genomes tried, "
          f"{rep['survivors']} survived validation, {rep['donated']} donated "
          f"({rep['intake_budget']['basis']})")
    print(YIELD_PREFIX + json.dumps({"cells_proposed": rep["donated"],
                                     "candidates": rep["survivors"],
                                     "tests_run": rep["tests_run"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
