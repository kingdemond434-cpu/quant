"""ALPHAEVOLVE BEYOND STRATEGIES: portfolio, execution, regime-detector, scheduler and
search-policy PROGRAMS (Tier S layers 5 and 33).

`libs/tiers/evolution.py` evolves researcher genomes -- programs that PROPOSE strategies. The
rest of the desk is programs too: how a book is weighted, how an entry is worked, how a regime is
named, how an hour's research compute is split between producers, how the generator splits its
draws between families. Each is evolved here as a population of genomes over its own gene set,
with a fitness computed OFFLINE on the desk's own artifacts:

    portfolio       weighting rule x lookback x rebalance x shrink-to-equal, walked forward on
                    timestamp-aligned H1 returns; fitness = annualised Sharpe net of turnover
                    cost (scale-free, so every program is judged at equal heat)
    execution       market vs limit, limit offset in ATR, wait bars, ATR window; each bar is a
                    symmetric unit intent (buy AND sell, so no directional luck); fitness =
                    minus the mean implementation shortfall in ATR units, where an unfilled
                    limit chases at market at the end of its wait (the non-fill is charged)
    regime          feature x window x number of states; thresholds are fitted on the train
                    span only; fitness = share of the variance of the NEXT 24h realised
                    volatility the label explains (eta squared) -- a detector that names
                    nothing predictive scores zero
    scheduler       allocation rule over PRODUCERS (proportional, UCB, posterior mean, greedy,
                    uniform) x prior x half-life x exploration floor, replayed day by day over
                    the hypothesis graph: each day's split is decided from earlier days only;
                    fitness = certified per judged hypothesis the split would have bought
    search_policy   the same rule family over FAMILIES: which families the generator should
                    draw from

Every population is scored on the TRAIN span (the oldest 70% of the evidence); the champion and
the desk's INCUMBENT program (equal weight, market orders, 24h realised-vol median split, the
split the desk actually spent) are then scored on the HELD-OUT span the evolution never saw.
That held-out lift is the only number a challenger is judged on.

RESEARCH SIDE ONLY. Nothing here is read by the gateway, the allocator, the promoter or any
order path; the programs are scored, never deployed. An absent input is UNMEASURED with a reason.
"""
from __future__ import annotations

import math
import warnings
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np

from libs.tiers import evolution
from libs.tiers.evolution import Gene, Genome

TRAIN_SHARE = 0.7
HALF_SPREAD_ATR = 0.05          # market-order cost proxy in ATR units (spread column is points)
TURNOVER_COST = 0.00005         # 0.5 bp per unit of gross turnover

GENES: dict[str, tuple[Gene, ...]] = {
    "portfolio": (
        Gene("weighting", ("equal", "inverse_vol", "inverse_var", "min_corr", "momentum_tilt",
                           "reversal_tilt")),
        Gene("lookback", (120, 240, 500, 1000)),
        Gene("rebalance", (24, 120, 500)),
        Gene("shrink", lo=0.0, hi=1.0),
        Gene("mutation_rate", lo=0.05, hi=0.5),
    ),
    "execution": (
        Gene("order", ("market", "limit")),
        Gene("offset_atr", lo=0.0, hi=0.6),
        Gene("wait_bars", (1, 2, 3, 6)),
        Gene("atr_n", (14, 24, 48)),
        Gene("mutation_rate", lo=0.05, hi=0.5),
    ),
    "regime": (
        Gene("feature", ("realized_vol", "abs_trend", "range_ratio", "autocorr")),
        Gene("window", (12, 24, 72, 168)),
        Gene("n_states", (2, 3)),
        Gene("mutation_rate", lo=0.05, hi=0.5),
    ),
    "scheduler": (
        Gene("rule", ("proportional", "ucb", "posterior_mean", "greedy", "uniform")),
        Gene("prior", lo=0.5, hi=20.0),
        Gene("half_life_days", lo=1.0, hi=30.0),
        Gene("explore_floor", lo=0.0, hi=0.5),
        Gene("mutation_rate", lo=0.05, hi=0.5),
    ),
}
GENES["search_policy"] = GENES["scheduler"]

INCUMBENT: dict[str, Genome] = {
    "portfolio": {"weighting": "equal", "lookback": 240, "rebalance": 24, "shrink": 0.0},
    "execution": {"order": "market", "offset_atr": 0.0, "wait_bars": 1, "atr_n": 24},
    "regime": {"feature": "realized_vol", "window": 24, "n_states": 2},
    # the split the desk actually spent (arm weight = its judged share that day)
    "scheduler": {"rule": "as_spent"},
    "search_policy": {"rule": "as_spent"},
}


# ------------------------------------------------------------------------------------------------
# portfolio programs
# ------------------------------------------------------------------------------------------------

def _weights(g: Genome, hist: np.ndarray) -> np.ndarray:
    with warnings.catch_warnings(), np.errstate(invalid="ignore", divide="ignore"):
        warnings.simplefilter("ignore", RuntimeWarning)
        return _weights_raw(g, hist)


def _weights_raw(g: Genome, hist: np.ndarray) -> np.ndarray:
    n = hist.shape[1]
    eq = np.full(n, 1.0 / n)
    rule = str(g.get("weighting"))
    sd = np.nanstd(hist, axis=0)
    sd = np.where(np.isfinite(sd) & (sd > 0), sd, np.nan)
    if rule == "inverse_vol":
        w = 1.0 / sd
    elif rule == "inverse_var":
        w = 1.0 / sd ** 2
    elif rule == "min_corr":
        with np.errstate(invalid="ignore", divide="ignore"):
            c = np.corrcoef(np.nan_to_num(hist).T)
        c = np.where(np.isfinite(c), np.abs(c), 1.0)
        w = 1.0 / np.maximum(1e-6, c.mean(axis=0)) / sd
    elif rule in ("momentum_tilt", "reversal_tilt"):
        mu = np.nanmean(hist, axis=0)
        s = np.sign(mu) * (1 if rule == "momentum_tilt" else -1)
        w = s / sd
    else:
        w = eq.copy()
    w = np.where(np.isfinite(w), w, 0.0)
    gross = float(np.abs(w).sum())
    w = w / gross if gross > 0 else eq
    shrink = float(g.get("shrink", 0.0))
    w = (1 - shrink) * w + shrink * eq
    gross = float(np.abs(w).sum())
    return w / gross if gross > 0 else eq


def portfolio_score(g: Genome, R: np.ndarray, start: int, end: int) -> dict[str, Any]:
    """R: T x N aligned returns (NaN = no bar). Walk forward on [start, end)."""
    lb, rb = int(g.get("lookback", 240)), max(1, int(g.get("rebalance", 24)))
    start = max(start, lb)
    if end - start < 50 or R.shape[1] < 2:
        return {"status": "UNMEASURED", "why": "span or symbols too short", "fitness": None}
    out = []
    w_prev = np.zeros(R.shape[1])
    turnover = 0.0
    w = w_prev
    for t in range(start, end):
        if (t - start) % rb == 0:
            w = _weights(g, R[t - lb:t])
            turnover += float(np.abs(w - w_prev).sum())
            w_prev = w
        out.append(float(np.nansum(w * np.nan_to_num(R[t]))))
    r = np.asarray(out)
    r_net = r - TURNOVER_COST * turnover / len(r)
    sd = float(np.std(r_net))
    sharpe = float(np.mean(r_net) / sd * math.sqrt(24 * 260)) if sd > 0 else 0.0
    return {"status": "MEASURED", "fitness": round(sharpe, 4), "bars": len(r),
            "turnover": round(turnover, 3)}


# ------------------------------------------------------------------------------------------------
# execution programs
# ------------------------------------------------------------------------------------------------

def _atr(h: np.ndarray, lo: np.ndarray, c: np.ndarray, n: int) -> np.ndarray:
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - lo, np.maximum(np.abs(h - pc), np.abs(lo - pc)))
    k = np.ones(n) / n
    a = np.convolve(tr, k, mode="full")[: len(tr)]
    a[: n] = np.nan
    # the ATR known at bar t is from bars BEFORE t
    return np.concatenate([[np.nan], a[:-1]])


def execution_score(g: Genome, ohlc: Mapping[str, Mapping[str, np.ndarray]], lo_frac: float,
                    hi_frac: float) -> dict[str, Any]:
    """Mean implementation shortfall (ATR units) over symmetric unit intents in the span."""
    costs: list[float] = []
    wait = max(1, int(g.get("wait_bars", 1)))
    off = float(g.get("offset_atr", 0.0))
    limit = str(g.get("order")) == "limit" and off > 0
    for d in ohlc.values():
        o, h, lo, c = (np.asarray(d[k], dtype=float) for k in ("open", "high", "low", "close"))
        atr = _atr(h, lo, c, int(g.get("atr_n", 24)))
        n = len(o)
        a, b = int(n * lo_frac), min(int(n * hi_frac), n - wait)
        for t in range(max(a, 1), b, 3):
            A = atr[t]
            if not np.isfinite(A) or A <= 0:
                continue
            if not limit:
                costs.append(HALF_SPREAD_ATR)
                continue
            lo_w, hi_w = float(np.min(lo[t:t + wait])), float(np.max(h[t:t + wait]))
            end_px = float(c[t + wait - 1])
            # buy intent
            costs.append(-off if lo_w <= o[t] - off * A
                         else (end_px - o[t]) / A + HALF_SPREAD_ATR)
            # sell intent
            costs.append(-off if hi_w >= o[t] + off * A
                         else (o[t] - end_px) / A + HALF_SPREAD_ATR)
    if len(costs) < 50:
        return {"status": "UNMEASURED", "why": f"{len(costs)} intents", "fitness": None}
    arr = np.asarray(costs)
    return {"status": "MEASURED", "fitness": round(-float(arr.mean()), 5),
            "shortfall_atr": round(float(arr.mean()), 5), "intents": len(arr)}


# ------------------------------------------------------------------------------------------------
# regime-detector programs
# ------------------------------------------------------------------------------------------------

def _feature(g: Genome, d: Mapping[str, np.ndarray]) -> np.ndarray:
    c = np.asarray(d["close"], dtype=float)
    r = np.concatenate([[0.0], np.diff(np.log(c))])
    w = int(g.get("window", 24))
    import pandas as pd
    s = pd.Series(r)
    feat = str(g.get("feature"))
    if feat == "abs_trend":
        x = s.rolling(w).sum().abs() / (s.rolling(w).std() * math.sqrt(w))
    elif feat == "range_ratio":
        h = pd.Series(np.asarray(d["high"], dtype=float))
        lo = pd.Series(np.asarray(d["low"], dtype=float))
        x = (h.rolling(w).max() - lo.rolling(w).min()) / pd.Series(c)
    elif feat == "autocorr":
        x = s.rolling(w).corr(s.shift(1))
    else:
        x = s.rolling(w).std()
    return np.asarray(x.to_numpy(), dtype=float)


def regime_score(g: Genome, ohlc: Mapping[str, Mapping[str, np.ndarray]], lo_frac: float,
                 hi_frac: float, *, horizon: int = 24) -> dict[str, Any]:
    """eta^2 of the next-`horizon` realised vol on the label, thresholds from the train span."""
    k = int(g.get("n_states", 2))
    etas: list[float] = []
    for d in ohlc.values():
        c = np.asarray(d["close"], dtype=float)
        r = np.concatenate([[0.0], np.diff(np.log(c))])
        fut = np.full(len(r), np.nan)
        cs = np.concatenate([[0.0], np.cumsum(r ** 2)])
        n = len(r)
        fut[: n - horizon] = np.sqrt(cs[horizon + 1: n + 1] - cs[1: n - horizon + 1])
        x = _feature(g, d)
        cut = int(n * TRAIN_SHARE)
        tr = x[:cut][np.isfinite(x[:cut])]
        if len(tr) < 100:
            continue
        qs = np.quantile(tr, [i / k for i in range(1, k)])
        a, b = int(n * lo_frac), int(n * hi_frac)
        xs, ys = x[a:b], fut[a:b]
        m = np.isfinite(xs) & np.isfinite(ys)
        if m.sum() < 100:
            continue
        lab = np.searchsorted(qs, xs[m])
        y = ys[m]
        tot = float(((y - y.mean()) ** 2).sum())
        if tot <= 0:
            continue
        between = sum(float((lab == j).sum()) * (float(y[lab == j].mean()) - float(y.mean())) ** 2
                      for j in range(k) if (lab == j).any())
        etas.append(between / tot)
    if not etas:
        return {"status": "UNMEASURED", "why": "no symbol with enough bars", "fitness": None}
    return {"status": "MEASURED", "fitness": round(float(np.mean(etas)), 5),
            "symbols": len(etas)}


# ------------------------------------------------------------------------------------------------
# scheduler / search-policy programs (bandits replayed over the hypothesis graph)
# ------------------------------------------------------------------------------------------------

def arm_days(rows: Iterable[Mapping[str, Any]], arm_of: Any) -> dict[str, dict[str, list[int]]]:
    """day -> arm -> [judged, succeeded] from gate verdicts (`passed`) or hypothesis-graph fate
    events (FAILED / CERTIFIED). Rows that carry neither are not judgements and are skipped."""
    out: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for r in rows:
        if "passed" in r:
            ok = bool(r.get("passed"))
        elif r.get("fate") in ("FAILED", "CERTIFIED"):
            ok = r.get("fate") == "CERTIFIED"
        else:
            continue
        day = str(r.get("at") or "")[:10]
        arm = arm_of(r)
        if not day or not arm:
            continue
        out[day][arm][0] += 1
        out[day][arm][1] += int(ok)
    return {d: {a: list(v) for a, v in arms.items()} for d, arms in out.items()}


def _allocate(g: Genome, past: Sequence[tuple[int, Mapping[str, Sequence[int]]]],
              arms: Sequence[str], day_idx: int) -> dict[str, float]:
    rule = str(g.get("rule"))
    if rule == "uniform" or not past:
        return {a: 1.0 / len(arms) for a in arms}
    hl = max(0.5, float(g.get("half_life_days", 7.0)))
    prior = float(g.get("prior", 2.0))
    j: dict[str, float] = defaultdict(float)
    s: dict[str, float] = defaultdict(float)
    for i, day in past:
        dec = 0.5 ** ((day_idx - i) / hl)
        for a, (nj, ns) in day.items():
            j[a] += dec * nj
            s[a] += dec * ns
    tot_j = sum(j.values())
    base = (sum(s.values()) + 1.0) / (tot_j + 2.0)
    mean = {a: (s[a] + prior * base) / (j[a] + prior) for a in arms}
    if rule == "ucb":
        score = {a: mean[a] + math.sqrt(2 * math.log(max(2.0, tot_j)) / (j[a] + prior))
                 * base for a in arms}
    elif rule == "greedy":
        best = max(arms, key=lambda a: mean[a])
        score = {a: 1.0 if a == best else 0.0 for a in arms}
    elif rule == "proportional":
        score = {a: j[a] * mean[a] + 1e-9 for a in arms}
    else:
        score = mean
    tot = sum(max(0.0, v) for v in score.values())
    w = {a: (max(0.0, score[a]) / tot if tot > 0 else 1.0 / len(arms)) for a in arms}
    f = float(g.get("explore_floor", 0.0))
    return {a: (1 - f) * w[a] + f / len(arms) for a in arms}


def current_split(g: Genome, days: Mapping[str, Mapping[str, Sequence[int]]]) -> dict[str, float]:
    """The split this program would spend TODAY, decided from every judged day so far -- what an
    adopted scheduler champion hands the real scheduler (`libs/tiers/scheduler_tournament`)."""
    order = sorted(days)
    arms = sorted({a for d in days.values() for a in d})
    if len(arms) < 2 or str(g.get("rule")) == "as_spent":
        return {}
    return _allocate(g, [(i, days[d]) for i, d in enumerate(order)], arms, len(order))


def bandit_score(g: Genome, days: Mapping[str, Mapping[str, Sequence[int]]], lo_frac: float,
                 hi_frac: float) -> dict[str, Any]:
    """Certified per judged hypothesis the program's daily split would have bought."""
    order = sorted(days)
    arms = sorted({a for d in days.values() for a in d})
    if len(order) < 4 or len(arms) < 2:
        return {"status": "UNMEASURED", "why": f"{len(order)} day(s), {len(arms)} arm(s)",
                "fitness": None}
    a, b = max(1, int(len(order) * lo_frac)), int(len(order) * hi_frac)
    vals = []
    for k in range(a, b):
        today = days[order[k]]
        if str(g.get("rule")) == "as_spent":
            w = {x: float(v[0]) for x, v in today.items()}
        else:
            w = _allocate(g, [(i, days[order[i]]) for i in range(k)], arms, k)
        act = [x for x, v in today.items() if v[0] > 0]
        den = sum(w.get(x, 0.0) for x in act)
        if den <= 0:
            continue
        vals.append(sum(w.get(x, 0.0) * today[x][1] / today[x][0] for x in act) / den)
    if not vals:
        return {"status": "UNMEASURED", "why": "no judged day in the span", "fitness": None}
    return {"status": "MEASURED", "fitness": round(float(np.mean(vals)), 6), "days": len(vals),
            "arms": len(arms)}


# ------------------------------------------------------------------------------------------------
# the engine
# ------------------------------------------------------------------------------------------------

def score(kind: str, g: Genome, data: Any, lo_frac: float, hi_frac: float) -> dict[str, Any]:
    if data is None:
        return {"status": "UNMEASURED", "why": "no input", "fitness": None}
    if kind == "portfolio":
        T = data.shape[0]
        return portfolio_score(g, data, int(T * lo_frac), int(T * hi_frac))
    if kind == "execution":
        return execution_score(g, data, lo_frac, hi_frac)
    if kind == "regime":
        return regime_score(g, data, lo_frac, hi_frac)
    return bandit_score(g, data, lo_frac, hi_frac)


def generation(kind: str, population: Sequence[Genome], data: Any, rng: np.random.Generator,
               *, size: int = 10) -> dict[str, Any]:
    """Score on TRAIN, step one generation, score champion + incumbent on HELD-OUT."""
    genes = GENES[kind]
    pop = [evolution.complete(g, rng, genes) for g in population] or \
        [evolution.random_genome(rng, genes) for _ in range(size)]
    rows = []
    for g in pop:
        s = score(kind, g, data, 0.0, TRAIN_SHARE)
        rows.append((g, s))
    measured = [(g, float(s["fitness"])) for g, s in rows if s.get("fitness") is not None]
    if not measured:
        why = next((s.get("why") for _g, s in rows), "no input")
        return {"kind": kind, "status": "UNMEASURED", "why": why,
                "next_population": pop, "diversity": evolution.diversity(pop)}
    champ, champ_train = max(measured, key=lambda gf: gf[1])
    held = score(kind, champ, data, TRAIN_SHARE, 1.0)
    inc = INCUMBENT[kind]
    inc_train = score(kind, inc, data, 0.0, TRAIN_SHARE)
    inc_held = score(kind, inc, data, TRAIN_SHARE, 1.0)
    nxt = evolution.step(measured, rng, size=size, genes=genes)
    lift = None
    if held.get("fitness") is not None and inc_held.get("fitness") is not None:
        lift = round(float(held["fitness"]) - float(inc_held["fitness"]), 6)
    return {"kind": kind, "status": "MEASURED", "population": len(pop),
            "champion": champ, "champion_id": evolution.genome_id(champ),
            "champion_train": champ_train, "champion_heldout": held.get("fitness"),
            "incumbent": inc, "incumbent_train": inc_train.get("fitness"),
            "incumbent_heldout": inc_held.get("fitness"), "heldout_lift": lift,
            "beats_incumbent_heldout": (lift is not None and lift > 0),
            "train_fitness": sorted((round(f, 6) for _g, f in measured), reverse=True),
            "next_population": nxt, "diversity": evolution.diversity(nxt)}


def run(kinds: Sequence[str], state: Mapping[str, Any], data: Mapping[str, Any],
        seed: int, *, size: int = 10) -> tuple[dict[str, Any], dict[str, Any]]:
    """One generation of every kind. -> (report, new state). State: {kind: {generation, pop}}."""
    report: dict[str, Any] = {}
    new_state: dict[str, Any] = {}
    for i, kind in enumerate(kinds):
        st = dict(state.get(kind) or {})
        gen = int(st.get("generation", 0)) + 1
        rng = np.random.default_rng(seed * 101 + i)
        res = generation(kind, st.get("population") or [], data.get(kind), rng, size=size)
        hist = list(st.get("heldout_history") or [])
        if res.get("status") == "MEASURED":
            hist.append({"gen": gen, "champion": res["champion_id"],
                         "heldout": res["champion_heldout"],
                         "incumbent": res["incumbent_heldout"], "lift": res["heldout_lift"]})
        new_state[kind] = {"generation": gen, "population": res.pop("next_population"),
                           "champion": res.get("champion"),
                           "heldout_history": hist[-500:]}
        report[kind] = {"generation": gen, **res}
    return report, new_state


def ohlc_arrays(frames: Mapping[str, Any]) -> dict[str, dict[str, np.ndarray]]:
    return {s: {k: np.asarray(f[k].astype(float).to_numpy()) for k in ("open", "high", "low",
                                                                       "close")}
            for s, f in frames.items()}
