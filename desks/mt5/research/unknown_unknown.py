"""UNKNOWN-UNKNOWN MINING: open-ended search over features, transforms and conditioning nobody named.

THE PRINCIPAL, 2026-09-30: "maximise them all fr breadth and unknown unknown minings all". Every
other producer on this desk starts from a NAME -- a family somebody wrote, a claim somebody made,
a feature set somebody chose (`mass_screen`'s returns, z-scores, range position, vol ratio,
range/ATR, clock, leader, carry). This one starts from a LANGUAGE (`mt5desk.uu_grammar`): leaves
(price, volume, calendar, a cross-asset reference) combined by transforms (lags, rolling sums,
z-scores, ranks, EMAs, differences, realised vol) and combinators (differences, ratios, products,
extremes, rolling correlation), and searches it three ways:

    enumerate   `uu_unary`, `uu_binary`, `uu_cross`: the finite depth-1/2 spaces, sampled by a
                seed that rotates daily, so across days the whole space is visited;
    condition   `uu_cond`: an expression beyond a quantile INSIDE a second expression's tercile
                (a regime nobody named) or inside a clock bucket (time of day);
    evolve      `uu_gp`: random typed trees of depth <= 4, then one generation of mutation of
                the ones the TRAINING window liked best -- genetic programming, fully charged.

THE SCREEN IS THE MASS SCREEN'S, EXTENDED, NOT DUPLICATED. Each expression is evaluated on the
symbol's H1 bars and inserted into `mass_screen.Prepared`'s feature table under its own text;
from there `mass_screen.screen_symbol` screens it with the same net-of-cost R (the engine's
entry, stop, time exit, spread x commission x swap), the same training window (clipped per cell
to the start of the sealed gauntlet's walk-forward region, so the out-of-sample gates are never
screened on), the same 60-day floor, the same one-a-day thinning law. Then:

    FDR          Benjamini-Hochberg at FDR_Q over EVERY cell screened in the run (m counts the
                 cells that never reached 60 days too -- the conservative direction);
    stress       positive net R at 1x and at the gauntlet's 3x spread;
    NOVELTY      1 - max |rank correlation| between the expression and every NAMED feature
                 (`mass_screen_rules.base_feature_names()` -- the proxies of the desk's named
                 families -- and the calendar), on the training window. The named feature it is
                 closest to names its nearest cluster. A survivor below NOVELTY_MIN is a known
                 feature in disguise: counted, never donated (the mass screen already covers it);
    dedup        Jaccard on trading days against a stronger survivor on the same symbol and side;

and only what is left is donated, through the registry's one door
(`libs.moat.registry.enqueue_candidate` -> `libs.moat.docket_feed` -> external_survivors.json),
as a cell of family `uu_<grammar>` that the sealed gauntlet rebuilds through
`uu_grammar.family_uu_rule` -- the same `evaluate` on the same bars.

MULTIPLICITY IS CHARGED ON THE FULL SCREENED WIDTH. Every cell screened -- the degenerate
thresholds and the GP population included -- is a trial, appended per grammar to
`data/UNKNOWN_UNKNOWN_TRIALS.jsonl`, which `libs.research.experiment_ledger` sums into the
lifetime and per-family trial counts. Nothing is judged for free.

    python desks/mt5/research/unknown_unknown.py --once --budget-s 900
    python desks/mt5/research/unknown_unknown.py --once --dry-run --symbols EURUSD --out-dir X
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import sys
import time
import uuid
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import mass_screen_rules as MR  # noqa: E402
from mt5desk import uu_grammar as UG  # noqa: E402

from research import mass_screen as MS  # noqa: E402

DATA = DESK / "data"
UNIVERSE = DATA / "universe"
REPORT = DESK / "reports" / "UNKNOWN_UNKNOWN.json"
#: THE TRIAL LEDGER (read by libs/research/experiment_ledger::_unknown_unknown_counts).
TRIALS = DATA / "UNKNOWN_UNKNOWN_TRIALS.jsonl"
RUNS = DATA / "unknown_unknown_runs.jsonl"
CURSOR = DATA / "unknown_unknown_cursor.json"
FORWARDED = DATA / "unknown_unknown_forwarded.json"
UNMEASURED = "UNMEASURED"
ORIGIN = "unknown_unknown"

FDR_Q = MS.FDR_Q
#: Holds screened (a subset of mass_screen.HORIZONS): the width goes to expressions, not holds.
UU_HORIZONS = (2, 8, 24)
#: Expressions drawn per symbol per UTC day, per grammar. The seed rotates daily, so the
#: enumerable spaces are walked across days rather than re-screened.
PER_GRAMMAR = {"unary": 60, "binary": 60, "cross": 40, "cond": 40, "gp": 40}
#: GP: the population above is generation 0; this many of its best (training window only) are
#: mutated this many times each into generation 1.
GP_ELITE = 10
GP_CHILDREN = 3
GP_MAX_DEPTH = 4
#: A survivor whose expression has |rank correlation| >= 1 - NOVELTY_MIN with a named feature is
#: that feature in disguise.
NOVELTY_MIN = 0.2
#: Rows sampled (every NOVELTY_STRIDE-th training bar) for the novelty correlation.
NOVELTY_STRIDE = 4
#: An expression must be finite on this share of the training window and take this many
#: distinct values to be screened at all (a constant or empty series tests nothing).
MIN_FINITE_SHARE = 0.5
MIN_DISTINCT = 10
#: Transforms used inside binary / cross combinations (a small set, so the pair space stays
#: enumerable): identity plus the five most distinct re-expressions.
PAIR_TRANSFORMS = ("", "z120", "rank120", "sum24", "ema8", "vol24")
#: The named features' nearest clusters (`libs.research.alpha_clusters` keys).
NAMED_CLUSTER = {"ret_1": "mean_reversion", "ret_2": "mean_reversion", "ret_4": "mean_reversion",
                 "ret_8": "trend", "ret_12": "trend", "ret_24": "trend", "ret_48": "trend",
                 "ret_120": "trend", "z_24": "mean_reversion", "z_72": "mean_reversion",
                 "z_240": "mean_reversion", "volratio": "volatility_transition",
                 "rpos_24": "mean_reversion", "rpos_120": "trend",
                 "rngatr": "volatility_transition", "hod": "session_liquidity",
                 "dow": "fixing_roll_calendar", "mend": "fixing_roll_calendar"}


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _rng(*parts: Any) -> np.random.Generator:
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "little"))


# --------------------------------------------------------------------------------------------
# the spaces
# --------------------------------------------------------------------------------------------
def _unary_ops() -> list[tuple[str, int]]:
    return [(op, k) for op, ks in UG.UNARY.items() for k in (ks or (0,))]


def _wrap(op: str, k: int, inner: str) -> str:
    return f"{op}{k if k else ''}({inner})"


def _apply_t(t: str, inner: str) -> str:
    return f"{t}({inner})" if t else inner


def unary_space() -> list[str]:
    """Every primitive through one or two unary transforms (idempotent repeats dropped)."""
    ops = _unary_ops()
    one = [_wrap(op, k, leaf) for leaf in UG.PRICE_LEAVES for op, k in ops]
    two: list[str] = []
    for inner in one:
        inner_op = UG.parse(inner)[1]
        for op, k in ops:
            if op == inner_op and op in ("abs", "sign", "neg"):
                continue
            two.append(_wrap(op, k, inner))
    return one + two


def binary_space() -> list[str]:
    out: list[str] = []
    leaves = UG.PRICE_LEAVES
    for i, a in enumerate(leaves):
        for b in leaves[i + 1:]:
            for ta in PAIR_TRANSFORMS:
                for tb in PAIR_TRANSFORMS:
                    for op, ks in UG.BINARY.items():
                        for k in (ks or (0,)):
                            out.append(f"{op}{k if k else ''}({_apply_t(ta, a)},"
                                       f"{_apply_t(tb, b)})")
    return out


def cross_space(refs: list[str]) -> list[str]:
    out: list[str] = []
    for ref in refs:
        for leaf in UG.CROSS_LEAVES:
            x = f"{leaf}@{ref}"
            for t in PAIR_TRANSFORMS:
                out.append(_apply_t(t, x))
            for op, k in (("lag", 1), ("lag", 2), ("sum", 4), ("z", 120)):
                out.append(_wrap(op, k, x))
            for own in UG.PRICE_LEAVES:
                for t in PAIR_TRANSFORMS:
                    for op, ks in UG.BINARY.items():
                        for k in (ks or (0,)):
                            out.append(f"{op}{k if k else ''}({_apply_t(t, own)},"
                                       f"{_apply_t(t, x)})")
    return out


def random_tree(rng: np.random.Generator, refs: list[str], max_depth: int = GP_MAX_DEPTH) -> str:
    """A random typed tree over every leaf and operator of the language."""
    leaves = list(UG.PRICE_LEAVES) + list(UG.CALENDAR_LEAVES) + [
        f"{leaf}@{r}" for r in refs for leaf in UG.CROSS_LEAVES]
    uops = _unary_ops()
    bops = [(op, k) for op, ks in UG.BINARY.items() for k in (ks or (0,))]

    def grow(d: int) -> str:
        if d <= 0 or (d < max_depth and rng.random() < 0.3):
            return str(leaves[int(rng.integers(len(leaves)))])
        if rng.random() < 0.6:
            op, k = uops[int(rng.integers(len(uops)))]
            return _wrap(op, k, grow(d - 1))
        op, k = bops[int(rng.integers(len(bops)))]
        return f"{op}{k if k else ''}({grow(d - 1)},{grow(d - 1)})"
    # a bare calendar leaf is not a feature worth a threshold; the root is always an operator
    while True:
        e = grow(max_depth)
        if UG.parse(e)[0] == "op":
            return e


def mutate(expr: str, rng: np.random.Generator, refs: list[str]) -> str:
    """One genetic move: swap an operator's window, wrap in a transform, or replace a subtree."""
    node = UG.parse(expr)
    nodes: list[tuple[tuple[int, ...], tuple]] = []

    def walk(n: tuple, path: tuple[int, ...]) -> None:
        nodes.append((path, n))
        if n[0] == "op":
            for i, a in enumerate(n[3]):
                walk(a, (*path, i))
    walk(node, ())
    path, target = nodes[int(rng.integers(len(nodes)))]
    move = int(rng.integers(3))
    if move == 0 and target[0] == "op":
        table = UG.UNARY if target[1] in UG.UNARY else UG.BINARY
        ks = table[target[1]]
        new = ("op", target[1], int(ks[int(rng.integers(len(ks)))]) if ks else 0, target[3])
    elif move == 1:
        op, k = _unary_ops()[int(rng.integers(len(_unary_ops())))]
        new = ("op", op, k, (target,))
    else:
        new = UG.parse(random_tree(rng, refs, max_depth=2))

    def put(n: tuple, p: tuple[int, ...]) -> tuple:
        if not p:
            return new
        args = list(n[3])
        args[p[0]] = put(args[p[0]], p[1:])
        return ("op", n[1], n[2], tuple(args))
    out = put(node, path)
    if UG.depth(out) > GP_MAX_DEPTH + 1 or out[0] != "op":
        return random_tree(rng, refs)
    return UG.render(out)


def _sample(space: list[str], k: int, rng: np.random.Generator) -> list[str]:
    if len(space) <= k:
        return list(space)
    idx = rng.choice(len(space), size=k, replace=False)
    return [space[int(i)] for i in sorted(idx)]


# --------------------------------------------------------------------------------------------
# novelty against the named features
# --------------------------------------------------------------------------------------------
def named_basis(P: MS.Prepared) -> dict[str, np.ndarray]:
    basis = {f: P.feats[f] for f in MR.base_feature_names() if f in P.feats}
    basis["hod"] = P.hour.astype("float64")
    basis["dow"] = P.wd.astype("float64")
    import pandas as pd
    idx = pd.DatetimeIndex(P.df.index)
    basis["mend"] = np.asarray(idx.days_in_month - idx.day, dtype="float64")
    return basis


def _ranks(a: np.ndarray) -> np.ndarray:
    from scipy.stats import rankdata
    out = np.full(a.shape, np.nan)
    ok = np.isfinite(a)
    if ok.any():
        out[ok] = rankdata(a[ok])
    return out


class Novelty:
    """1 - max |rank correlation| with any named feature, on the training window, subsampled."""

    def __init__(self, P: MS.Prepared) -> None:
        sl = slice(0, P.cut, NOVELTY_STRIDE)
        self.sl = sl
        self.basis = {k: _ranks(v[sl]) for k, v in named_basis(P).items()}
        self.cache: dict[str, tuple[float, str]] = {}

    def of(self, name: str, arr: np.ndarray) -> tuple[float, str]:
        if name in self.cache:
            return self.cache[name]
        x = _ranks(arr[self.sl])
        best, near = 0.0, ""
        for k, b in self.basis.items():
            m = np.isfinite(x) & np.isfinite(b)
            if m.sum() < 50:
                continue
            xs, bs = x[m], b[m]
            sx, sb = xs.std(), bs.std()
            if sx <= 0 or sb <= 0:
                continue
            r = abs(float(np.mean((xs - xs.mean()) * (bs - bs.mean())) / (sx * sb)))
            if r > best:
                best, near = r, k
        out = (round(1.0 - best, 4), NAMED_CLUSTER.get(near, "unclassified") if near else "")
        self.cache[name] = out
        return out


# --------------------------------------------------------------------------------------------
# one symbol
# --------------------------------------------------------------------------------------------
def reference_symbols(symbol: str) -> list[str]:
    return [s for s in MS.LEADERS if s.upper() != symbol.upper()
            and (UNIVERSE / f"{s}_H1.parquet").exists()]


def _admit(P: MS.Prepared, expr: str) -> np.ndarray | None:
    """The expression's values, or None when it is degenerate on the training window."""
    try:
        a = UG.evaluate(expr, P.df)
    except UG.GrammarError:
        return None
    tr = a[: P.cut]
    fin = np.isfinite(tr)
    if tr.size == 0 or fin.mean() < MIN_FINITE_SHARE:
        return None
    if np.unique(tr[fin][: 20_000]).size < MIN_DISTINCT:
        return None
    return a


def _threshold_conds(P: MS.Prepared, grammar: str, expr: str) -> list[dict[str, Any]]:
    a = P.feats[expr][: P.cut]
    out = []
    for q, op in MS.QUANTILES:
        thr = MS._q(a, q)
        if thr is not None:
            out.append({"grammar": grammar, "feat": expr, "op": op, "thr": thr, "_q": q})
    return out


def _cond_conds(P: MS.Prepared, a_expr: str, b_expr: str) -> list[dict[str, Any]]:
    base = _threshold_conds(P, "cond", a_expr)
    bands: list[tuple[str, float, float, str]] = []
    if b_expr == "hour":
        bands = [("hour", float(lo), float(hi), f"s{lo}") for lo, hi in MS.SESSIONS]
    else:
        b = P.feats[b_expr][: P.cut]
        lo_q, hi_q = MS._q(b, MS.TERCILE_Q[0]), MS._q(b, MS.TERCILE_Q[1])
        if lo_q is None or hi_q is None or not lo_q < hi_q:
            return []
        bands = [(b_expr, -MR.OPEN_BOUND, lo_q, "t1"), (b_expr, lo_q, hi_q, "t2"),
                 (b_expr, hi_q, MR.OPEN_BOUND, "t3")]
    out = []
    for c in base:
        for cf, lo, hi, lab in bands:
            out.append({**c, "cond_feat": cf, "cond_lo": lo, "cond_hi": hi, "_band": lab})
    return out


def _merge_counts(into: dict[str, dict[str, int]], add: dict[str, dict[str, int]]) -> None:
    for g, v in (add or {}).items():
        a = into.setdefault(g, {"cells": 0, "testable": 0, "candidates": 0})
        for k in a:
            a[k] += int(v.get(k) or 0)


def screen_symbol(symbol: str, df, meta: dict[str, Any] | None, *, day: str,
                  q: float = FDR_Q, per_grammar: dict[str, int] | None = None,
                  refs: list[str] | None = None) -> dict[str, Any]:
    """Generate, evaluate, screen and novelty-score every grammar on one symbol."""
    t0 = time.monotonic()
    per = dict(PER_GRAMMAR, **(per_grammar or {}))
    P = MS.Prepared(symbol, df, meta or {}, None)
    nov = Novelty(P)
    refs = reference_symbols(symbol) if refs is None else refs
    exprs: dict[str, list[str]] = {g: [] for g in UG.GRAMMARS}
    stats = {g: {"expressions": 0, "degenerate": 0, "novelty": []} for g in UG.GRAMMARS}
    novelty_of: dict[str, tuple[float, str]] = {}

    def admit(g: str, e: str) -> bool:
        stats[g]["expressions"] += 1
        if e in P.feats:
            return True
        a = _admit(P, e)
        if a is None:
            stats[g]["degenerate"] += 1
            return False
        P.feats[e] = a
        novelty_of[e] = nov.of(e, a)
        return True

    conds: list[dict[str, Any]] = []
    for g, space in (("unary", unary_space()), ("binary", binary_space()),
                     ("cross", cross_space(refs) if refs else [])):
        for e in _sample(space, per[g], _rng(day, symbol, g)):
            if admit(g, e):
                exprs[g].append(e)
                stats[g]["novelty"].append(novelty_of[e][0])
                conds += _threshold_conds(P, g, e)
    # regime / clock conditioning: A beyond a quantile inside B's tercile or a session bucket
    rng = _rng(day, symbol, "cond")
    pool = [e for e in unary_space() if UG.depth(UG.parse(e)) == 1]
    for _ in range(per["cond"]):
        a_e = pool[int(rng.integers(len(pool)))]
        b_e = "hour" if rng.random() < 0.25 else pool[int(rng.integers(len(pool)))]
        if a_e == b_e or not admit("cond", a_e) or (b_e != "hour" and not admit("cond", b_e)):
            continue
        n_a = novelty_of[a_e][0]
        n_ab = max(n_a, novelty_of[b_e][0]) if b_e != "hour" else n_a
        stats["cond"]["novelty"].append(n_ab)
        conds += _cond_conds(P, a_e, b_e)
    res = MS.screen_symbol(P, meta, q=q, conds=conds, horizons=UU_HORIZONS)
    by_grammar = dict(res["by_grammar"])
    cands = list(res["candidates"])
    # genetic programming: generation 0 random, generation 1 mutated from the training-best
    rng = _rng(day, symbol, "gp")
    gen0 = []
    for _ in range(per["gp"]):
        e = random_tree(rng, refs)
        if admit("gp", e):
            gen0.append(e)
            stats["gp"]["novelty"].append(novelty_of[e][0])
    gp_conds = [c for e in gen0 for c in _threshold_conds(P, "gp", e)]
    r0 = MS.screen_symbol(P, meta, q=q, conds=gp_conds, horizons=UU_HORIZONS)
    _merge_counts(by_grammar, r0["by_grammar"])
    cands += r0["candidates"]
    best: dict[str, float] = {}
    for c in r0["candidates"]:
        e = str(c["cond"].get("feat"))
        best[e] = min(best.get(e, 1.0), float(c["p"]))
    elite = sorted(gen0, key=lambda e: (best.get(e, 1.0), e))[:GP_ELITE]
    gen1 = []
    for e in elite:
        for _ in range(GP_CHILDREN):
            child = mutate(e, rng, refs)
            if child not in P.feats and admit("gp", child):
                gen1.append(child)
                stats["gp"]["novelty"].append(novelty_of[child][0])
    g1_conds = [c for e in gen1 for c in _threshold_conds(P, "gp", e)]
    r1 = MS.screen_symbol(P, meta, q=q, conds=g1_conds, horizons=UU_HORIZONS)
    _merge_counts(by_grammar, r1["by_grammar"])
    cands += r1["candidates"]
    exprs["gp"] = gen0 + gen1
    for c in cands:
        cd = c["cond"]
        if c["grammar"] == "cond":
            a_n = novelty_of.get(str(cd.get("feat")), (0.0, ""))
            b_key = str(cd.get("cond_feat") or "")
            b_n = novelty_of.get(b_key, (0.0, "")) if b_key != "hour" else (0.0, "")
            c["novelty"], c["nearest"] = max(a_n, b_n)
        else:
            c["novelty"], c["nearest"] = novelty_of.get(str(cd.get("feat")), (0.0, ""))
    return {"symbol": symbol, "cells": int(sum(v["cells"] for v in by_grammar.values())),
            "testable": int(sum(v["testable"] for v in by_grammar.values())),
            "by_grammar": by_grammar, "candidates": cands,
            "expressions": {g: {"generated": stats[g]["expressions"],
                                "degenerate": stats[g]["degenerate"],
                                "novelty": [float(x) for x in stats[g]["novelty"]]}
                            for g in UG.GRAMMARS},
            "seconds": round(time.monotonic() - t0, 3), "n_bars": P.n}


# --------------------------------------------------------------------------------------------
# forward
# --------------------------------------------------------------------------------------------
def params_of(c: dict[str, Any]) -> dict[str, Any]:
    cd = c["cond"]
    return {"expr": str(cd.get("feat", "")), "op": str(cd.get("op", "gt")),
            "thr": float(cd.get("thr", 0.0)), "direction": int(c["direction"]),
            "hold": int(c["hold"]), "stop_atr": float(c["stop_atr"]),
            "cond_expr": str(cd.get("cond_feat", "")),
            "cond_lo": float(cd.get("cond_lo", -MR.OPEN_BOUND)),
            "cond_hi": float(cd.get("cond_hi", MR.OPEN_BOUND)),
            "hour": int(cd.get("hour", -1)), "weekday": int(cd.get("weekday", -1)),
            "atr_n": 20, "gv": UG.GRAMMAR_VERSION}


def structural_key(c: dict[str, Any]) -> str:
    cd = c["cond"]
    return "|".join(str(x) for x in (
        c["symbol"], c["grammar"], cd.get("feat", ""), cd.get("op", ""), c.get("qlevel", ""),
        cd.get("cond_feat", ""), c.get("band", ""), cd.get("hour", -1), cd.get("weekday", -1),
        c["hold"], c["direction"], c["stop_atr"], UG.GRAMMAR_VERSION))


def mechanism_of(c: dict[str, Any]) -> str:
    cd = c["cond"]
    side = "long" if c["direction"] > 0 else "short"
    rule = (f"{cd.get('feat')} {cd.get('op')} {cd.get('thr')}"
            + (f" | {cd['cond_feat']} in [{cd.get('cond_lo'):.6g},{cd.get('cond_hi'):.6g})"
               if cd.get("cond_feat") else ""))
    return (f"UNKNOWN: an unnamed relationship found by open-ended search "
            f"(unknown_unknown/{c['grammar']}): {rule} -> {side}, hold {c['hold']}h, stop "
            f"{c['stop_atr']}ATR. Novelty {c.get('novelty', 0):.2f} against the named features "
            f"(nearest cluster {c.get('nearest') or 'none'}). Screened in-sample only (train "
            f"t={c['t']:.2f} over {c['n_days']} days, net R/day {c['mean_r']:.4f}, x3 "
            f"{c['mean_r_x3']:.4f}); selected from {c.get('_m', 0)} cells at BH "
            f"q={c.get('_q', FDR_Q)}.")


def forward(cells: list[dict[str, Any]], *, conn=None) -> dict[str, Any]:
    """Through the registry's one door. Returns counts; never raises."""
    out = {"attempted": 0, "created": 0, "already_present": 0, "failed": 0, "why": None}
    if not cells:
        return out
    try:
        from libs.moat.registry import connect, enqueue_candidate
    except Exception as exc:
        out["why"] = f"{UNMEASURED}: registry door unimportable ({type(exc).__name__}: {exc})"
        out["failed"] = len(cells)
        return out
    own = conn is None
    try:
        con = conn or connect()
    except Exception as exc:
        out["why"] = f"{UNMEASURED}: registry unopenable ({type(exc).__name__}: {exc})"
        out["failed"] = len(cells)
        return out
    try:
        for c in cells:
            out["attempted"] += 1
            try:
                _id, made = enqueue_candidate(
                    family=f"uu_{c['grammar']}", symbol=c["symbol"], params=params_of(c),
                    origin=ORIGIN, mechanism=mechanism_of(c), conn=con, chart="H1",
                    horizon=f"{c['hold']}h",
                    p_edge=round(max(0.5, min(0.99, 1.0 - float(c.get("_qvalue", 1.0)))), 4),
                    producer="desks/mt5/research/unknown_unknown.py", generator=ORIGIN)
            except Exception:
                out["failed"] += 1
                continue
            out["created" if made else "already_present"] += 1
    finally:
        if own:
            with contextlib.suppress(Exception):
                con.close()
    return out


# --------------------------------------------------------------------------------------------
# the run
# --------------------------------------------------------------------------------------------
def _worker(symbol: str, q: float, day: str) -> dict[str, Any]:
    t0 = time.monotonic()
    try:
        df = MR.load_bars(symbol)
        if df is None or len(df) < 2000:
            return {"symbol": symbol, "error": "no or too few H1 bars", "cells": 0,
                    "seconds": round(time.monotonic() - t0, 3)}
        meta = MS.universe_meta().get(symbol) or {}
        return screen_symbol(symbol, df, meta, day=day, q=q)
    except Exception as exc:
        return {"symbol": symbol, "error": f"{type(exc).__name__}: {str(exc)[:200]}",
                "cells": 0, "seconds": round(time.monotonic() - t0, 3)}


def run(*, budget_s: float = 900.0, workers: int | None = None, symbols: list[str] | None = None,
        q: float = FDR_Q, dry_run: bool = False, out_dir: Path | None = None,
        conn=None, day: str | None = None) -> dict[str, Any]:
    started = time.monotonic()
    run_id = f"uu_{datetime.now(tz=UTC).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:6]}"
    report = (out_dir / "UNKNOWN_UNKNOWN.json") if out_dir else REPORT
    trials_p = (out_dir / "UNKNOWN_UNKNOWN_TRIALS.jsonl") if out_dir else TRIALS
    runs_p = (out_dir / "unknown_unknown_runs.jsonl") if out_dir else RUNS
    cursor_p = (out_dir / "unknown_unknown_cursor.json") if out_dir else CURSOR
    fwd_p = (out_dir / "unknown_unknown_forwarded.json") if out_dir else FORWARDED
    universe = symbols if symbols else MS.hypothesis_symbols()
    today = day or datetime.now(tz=UTC).date().isoformat()
    if not universe:
        doc = {"generated_utc": _now(), "status": UNMEASURED, "run_id": run_id,
               "why": "no hypothesis-lane symbol with H1 bars (universe_policy / parquets)"}
        MS._write_json(report, doc)
        return doc
    cursor = MS._read_json(cursor_p, {}) if not symbols else {}
    screened_on: dict[str, str] = dict(cursor.get("screened_on") or {})
    # ONCE PER SYMBOL PER UTC DAY, and each day's draw is a NEW sample of the grammar spaces
    # (the seed is the day), so the daily width is fresh expressions, never a repeat.
    order = (list(universe) if symbols else
             sorted((s for s in universe if screened_on.get(s) != today),
                    key=lambda s: (screened_on.get(s, ""), universe.index(s))))
    w, winfo = MS.derive_workers(workers)
    results: list[dict[str, Any]] = []
    per_s: list[float] = []

    def left() -> float:
        return budget_s - (time.monotonic() - started)

    if w <= 1:
        for s in order:
            if results and left() < (np.median(per_s) if per_s else 0):
                break
            r = _worker(s, q, today)
            results.append(r)
            per_s.append(float(r.get("seconds") or 0))
            if left() <= 0:
                break
    else:
        with ProcessPoolExecutor(max_workers=w) as ex:
            it = iter(order)
            live: dict[Any, str] = {}
            for s in it:
                live[ex.submit(_worker, s, q, today)] = s
                if len(live) >= w:
                    break
            while live:
                fin, _ = wait(list(live), timeout=max(1.0, left()), return_when=FIRST_COMPLETED)
                if not fin:
                    break
                for f in fin:
                    live.pop(f)
                    r = f.result()
                    results.append(r)
                    per_s.append(float(r.get("seconds") or 0))
                    if left() > (float(np.median(per_s)) if per_s else 0.0):
                        nxt = next(it, None)
                        if nxt is not None:
                            live[ex.submit(_worker, nxt, q, today)] = nxt
            for f in live:
                f.cancel()
    wall = time.monotonic() - started
    for r in results:
        if not r.get("error"):
            screened_on[r["symbol"]] = today

    # ---- FDR over the FULL screened width --------------------------------------------------
    m = int(sum(int(r.get("cells") or 0) for r in results))
    cands = [c for r in results for c in (r.get("candidates") or [])]
    cut = MS.bh_threshold(np.array([c["p"] for c in cands]), m, q)
    rejected = [c for c in cands if cut > 0 and c["p"] <= cut]
    ranked = sorted(c["p"] for c in cands)
    for c in rejected:
        rank = int(np.searchsorted(ranked, c["p"], side="right"))
        c["_qvalue"] = min(1.0, c["p"] * m / max(rank, 1))
        c["_m"], c["_q"] = m, q
    stressed = [c for c in rejected if c["mean_r_x3"] > 0 and c["mean_r"] > 0]
    novel = [c for c in stressed if float(c.get("novelty") or 0.0) >= NOVELTY_MIN]
    kept, dup_dropped = MS.dedup(novel)
    already = set(MS._read_json(fwd_p, []))
    fresh = [c for c in kept if structural_key(c) not in already]
    fwd = ({"attempted": 0, "created": 0, "already_present": 0, "failed": 0,
            "why": "dry run: nothing forwarded"} if dry_run else forward(fresh, conn=conn))
    if not dry_run and fresh and not fwd.get("why"):
        already |= {structural_key(c) for c in fresh}
        MS._write_json(fwd_p, sorted(already))

    # ---- per grammar: width, survivors, novelty ---------------------------------------------
    by_g: dict[str, dict[str, Any]] = {}
    for g in UG.GRAMMARS:
        a: dict[str, Any] = {"cells_screened": 0, "cells_testable": 0, "candidates_p_le_q": 0,
                             "expressions": 0, "degenerate_expressions": 0}
        nov: list[float] = []
        for r in results:
            v = (r.get("by_grammar") or {}).get(g) or {}
            a["cells_screened"] += int(v.get("cells") or 0)
            a["cells_testable"] += int(v.get("testable") or 0)
            a["candidates_p_le_q"] += int(v.get("candidates") or 0)
            e = (r.get("expressions") or {}).get(g) or {}
            a["expressions"] += int(e.get("generated") or 0)
            a["degenerate_expressions"] += int(e.get("degenerate") or 0)
            nov += [float(x) for x in e.get("novelty") or []]
        a["fdr_rejected"] = sum(1 for c in rejected if c["grammar"] == g)
        a["stress_pass"] = sum(1 for c in stressed if c["grammar"] == g)
        a["novel_survivors"] = sum(1 for c in novel if c["grammar"] == g)
        a["known_in_disguise"] = a["stress_pass"] - a["novel_survivors"]
        a["forwarded"] = 0 if dry_run else sum(1 for c in fresh if c["grammar"] == g)
        surv_nov = [float(c.get("novelty") or 0) for c in stressed if c["grammar"] == g]
        a["novelty"] = {
            "expressions_mean": round(float(np.mean(nov)), 4) if nov else UNMEASURED,
            "expressions_median": round(float(np.median(nov)), 4) if nov else UNMEASURED,
            "expressions_novel_share": (round(float(np.mean(np.array(nov) >= NOVELTY_MIN)), 4)
                                        if nov else UNMEASURED),
            "survivors_mean": round(float(np.mean(surv_nov)), 4) if surv_nov else UNMEASURED,
        }
        by_g[g] = a
    ts = _now()
    trial_rows = [{"ts": ts, "run_id": run_id, "family": f"uu_{g}", "grammar": g,
                   "cells_screened": a["cells_screened"], "cells_testable": a["cells_testable"],
                   "fdr_q": q, "fdr_rejected": a["fdr_rejected"],
                   "novel_survivors": a["novel_survivors"], "forwarded": a["forwarded"],
                   "epoch": today, "dry_run": bool(dry_run)}
                  for g, a in by_g.items() if a["cells_screened"]]
    if not dry_run or out_dir is not None:
        MS._append(trials_p, trial_rows)
    worker_s = sum(float(r.get("seconds") or 0) for r in results)
    run_row = {"ts": ts, "run_id": run_id, "symbols": len(results), "cells": m,
               "candidates": len(cands), "fdr_rejected": len(rejected),
               "stress_pass": len(stressed), "novel": len(novel), "dedup_dropped": dup_dropped,
               "forwarded": int(fwd.get("created", 0)) + int(fwd.get("already_present", 0)),
               "wall_s": round(wall, 2), "worker_s": round(worker_s, 2), "workers": w,
               "dry_run": bool(dry_run)}
    new_cursor = {"epoch": today, "updated_utc": ts, "universe": len(universe),
                  "screened_today": sum(1 for s in universe if screened_on.get(s) == today),
                  "screened_on": screened_on}
    if not dry_run or out_dir is not None:
        MS._append(runs_p, [run_row])
        if not symbols:
            MS._write_json(cursor_p, new_cursor)
    doc = {
        "generated_utc": ts,
        "status": ("MEASURED" if results else "NOTHING_DUE" if not order else UNMEASURED),
        "why": None if results else (
            f"every one of {len(universe)} symbols already mined on {today}" if not order
            else "no symbol finished inside the budget"),
        "run_id": run_id, "dry_run": bool(dry_run),
        "law": ("expressions from a typed grammar over price/volume/calendar/cross-asset "
                "primitives (enumerated, conditioned, evolved), screened by mass_screen's own "
                "cheap screen on the TRAINING window only; BH at q over the FULL screened width; "
                "3x-spread stress; novelty = 1 - max |rank corr| with every named feature, "
                f"survivors below {NOVELTY_MIN} counted as known-in-disguise and never donated; "
                "Jaccard dedup; donated through the registry door as uu_<grammar> cells the "
                "sealed gauntlet rebuilds; every screened cell charged in "
                "UNKNOWN_UNKNOWN_TRIALS.jsonl"),
        "run": {**run_row, "symbols_screened": [r["symbol"] for r in results],
                "errors": {r["symbol"]: r["error"] for r in results if r.get("error")},
                "cursor": {k: v for k, v in new_cursor.items() if k != "screened_on"}},
        "per_day": MS._day_totals(runs_p),
        "fdr": {"method": "benjamini_hochberg", "q": q, "m_full_screened_width": m,
                "p_cut": cut, "rejected": len(rejected), "candidates_p_le_q": len(cands)},
        "by_grammar": by_g,
        "forward": {**fwd, "survivors_after_dedup": len(kept),
                    "skipped_already_forwarded": len(kept) - len(fresh),
                    "door": "libs.moat.registry.enqueue_candidate -> libs.moat.docket_feed -> "
                            "external_survivors.json (read by the sealed gauntlet)"},
        "trials_recorded": {"ledger": str(trials_p.relative_to(DESK) if trials_p.is_relative_to(
                                DESK) else trials_p), "rows": trial_rows,
                            "reader": "libs/research/experiment_ledger.py::"
                                      "_unknown_unknown_counts"},
        "throughput": {"cells_per_core_sec": round(m / worker_s, 1) if worker_s else UNMEASURED,
                       "distinct_cells_per_day_one_pass_per_symbol": (
                           int(m / len(results) * len(universe)) if results else UNMEASURED),
                       "workers": w, "wall_s": round(wall, 2)},
        "workers": winfo,
        "forwarded_sample": [{"symbol": c["symbol"], "family": f"uu_{c['grammar']}",
                              "params": params_of(c), "t": round(c["t"], 3), "p": c["p"],
                              "novelty": c.get("novelty"), "nearest_cluster": c.get("nearest"),
                              "n_days": c["n_days"], "mean_r": round(c["mean_r"], 5)}
                             for c in (fresh if not dry_run else kept)[:25]],
    }
    MS._write_json(report, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true", help="one bounded run (the hourly leg)")
    ap.add_argument("--budget-s", type=float, default=900.0)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--symbols", default="")
    ap.add_argument("--q", type=float, default=FDR_Q)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out-dir", type=Path, default=None)
    a = ap.parse_args(argv)
    syms = [s.strip() for s in a.symbols.split(",") if s.strip()] or None
    doc = run(budget_s=a.budget_s, workers=a.workers, symbols=syms, q=a.q, dry_run=a.dry_run,
              out_dir=a.out_dir)
    r = doc.get("run") or {}
    print(f"unknown_unknown {doc.get('status')}: {r.get('symbols', 0)} symbol(s), "
          f"{r.get('cells', 0):,} cells screened; FDR rejected {r.get('fdr_rejected')}, novel "
          f"{r.get('novel')}, forwarded {r.get('forwarded')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

