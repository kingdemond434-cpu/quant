"""Factor x model co-evolution: search (F, M) jointly, score by out-of-sample log score net of tax.

    (F*, M*) = argmax_{F, M}  logscore_OOS(F, M) - baseline - tax(M)

RD-Agent(Q)'s insight, stripped of the agent: a liquidity feature that is useless under ridge
can matter under boosting or under a state router, and a router that adds nothing on raw bars
can earn its tax once structural features exist. So the search is over PAIRINGS. Two populations
-- feature sets drawn from the feature store's vocabulary (including alpha-grammar expressions)
and model names from the zoo -- are bred together: crossover on feature sets, mutation on
params, a random model swap, and every pairing evaluated walk-forward on the same target.

THE OUTPUT IS A CANDIDATE, NOT A POSITION. The best pairing is written with its feature ids,
its model and its measured gain; a family that conditions on it goes to the gauntlet like any
other cell. Every pairing evaluated is counted -- it is a trial.
"""
from __future__ import annotations

import json
import time
from typing import Any

import numpy as np
import pandas as pd

from libs.data.feature_store import FeatureStore
from libs.models.zoo import TAX, compete

#: The vocabulary a feature set is drawn from. (name, params) pairs.
VOCAB: tuple[tuple[str, dict[str, Any]], ...] = (
    ("log_return", {"h": 1}), ("log_return", {"h": 6}), ("log_return", {"h": 24}),
    ("realised_vol", {"w": 24}), ("realised_vol", {"w": 120}),
    ("zscore", {"of": "log_return", "of_params": {"h": 24}, "w": 240}),
    ("zscore", {"of": "range_frac", "w": 120}),
    ("ts_rank", {"of": "range_frac", "w": 240}),
    ("ts_rank", {"of": "column", "of_params": {"col": "spread"}, "w": 240}),
    ("ts_rank", {"of": "column", "of_params": {"col": "tick_volume"}, "w": 240}),
    ("hour", {}),
    ("expr", {"expr": ["delta", "close", 24], "norm": 240}),
    ("expr", {"expr": ["sub", "close", ["max", "high", 48]], "norm": 240}),
    ("expr", {"expr": ["corr", "ret", "range", 48], "norm": 240}),
    # PARTICIPANT FLOW (2026-09-04): who is trading, not only what price did. The first two read
    # the broker's own tick flow off the bars. `swap_diff` and `cot_z` need an INSTRUMENT, and a
    # VOCAB entry is (name, params) with no view of the frame it is applied to, so they are seeded
    # for XAUUSD -- the desk's deepest COT market -- and are a constant / all-NaN block on any
    # other frame (the feature store records the reason in LAST_REASON rather than raising).
    # WIRING: `evolve` needs a `symbol` argument that substitutes into these params for the
    # vocabulary to be instrument-aware; until then the seeded symbol is the only one served.
    ("tick_imbalance", {"w": 24}),
    ("session_participation", {"n": 20}),
    ("swap_diff", {"symbol": "XAUUSD"}),
    ("cot_z", {"symbol": "XAUUSD", "w": 52}),
)


def target(df: pd.DataFrame, horizon: int) -> np.ndarray:
    c = df["close"].to_numpy(dtype=float)
    fwd = np.full(c.size, np.nan)
    with np.errstate(all="ignore"):
        fwd[:-horizon] = np.log(c[horizon:] / c[:-horizon])
    return fwd


def _key(fset: list[int], model: str) -> str:
    return json.dumps({"f": sorted(fset), "m": model})


def _specs(fset: list[int], symbol: str | None) -> list[tuple[str, dict[str, Any]]]:
    """The feature specs, with the instrument substituted into any symbol-bearing entry."""
    out: list[tuple[str, dict[str, Any]]] = []
    for i in sorted(fset):
        name, params = VOCAB[i]
        if symbol and "symbol" in params:
            params = {**params, "symbol": symbol}
        out.append((name, params))
    return out


def evaluate(df: pd.DataFrame, fset: list[int], model: str, store: FeatureStore,
             horizon: int = 6, symbol: str | None = None) -> dict[str, Any]:
    specs = _specs(fset, symbol)
    x = store.matrix(df, [(n, p) for n, p in specs])
    y_raw = target(df, horizon)
    ok = np.isfinite(x).all(axis=1) & np.isfinite(y_raw)
    # Non-overlapping targets: one row per horizon so the folds are not autocorrelated copies.
    rows = np.where(ok)[0][::horizon]
    x, y = x[rows], (y_raw[rows] > 0).astype(float)
    res = compete(x, y, models=(model,))
    r = res["results"][model]
    return {"features": [f"{n}:{json.dumps(p, sort_keys=True)}" for n, p in specs],
            "model": model, **{k: r.get(k) for k in ("n", "gain", "tax", "net_gain", "brier",
                                                       "verdict", "why")}}


def evolve(df: pd.DataFrame, *, store: FeatureStore | None = None, pop: int = 12,
           gens: int = 3, budget_s: float = 300.0, seed: int = 0, horizon: int = 6,
           models: tuple[str, ...] = tuple(TAX), symbol: str | None = None) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    store = store or FeatureStore()
    n_v = len(VOCAB)
    seen: dict[str, dict[str, Any]] = {}

    def _rand_set() -> list[int]:
        k = int(rng.integers(2, 6))
        return sorted(rng.choice(n_v, size=k, replace=False).tolist())

    population = [(_rand_set(), str(rng.choice(models))) for _ in range(pop)]
    started = time.monotonic()
    for _ in range(gens):
        scored = []
        for fset, model in population:
            if time.monotonic() - started > budget_s:
                break
            k = _key(fset, model)
            if k not in seen:
                try:
                    seen[k] = evaluate(df, fset, model, store, horizon, symbol)
                except Exception as exc:
                    seen[k] = {"features": [str(i) for i in fset], "model": model,
                               "verdict": "FAILED", "why": f"{type(exc).__name__}: {exc}",
                               "net_gain": None}
            scored.append((fset, model, seen[k].get("net_gain")))
        scored = [s for s in scored if s[2] is not None]
        if not scored:
            break
        scored.sort(key=lambda s: -float(s[2] or 0.0))
        elite = scored[: max(2, len(scored) // 3)]
        children: list[tuple[list[int], str]] = [(f, m) for f, m, _ in elite]
        while len(children) < pop:
            fa, ma, _ = elite[int(rng.integers(len(elite)))]
            fb, _mb, _ = elite[int(rng.integers(len(elite)))]
            if rng.random() < 0.5:
                cut = int(rng.integers(1, max(2, len(fa))))
                f = sorted(set(fa[:cut]) | set(fb[cut:]))
            else:
                f = sorted(set(fa) ^ {int(rng.integers(n_v))}) or fa
            f = f[:6]
            m = ma if rng.random() < 0.7 else str(rng.choice(models))
            children.append((f, m))
        population = children
    ranked = sorted((v for v in seen.values() if v.get("net_gain") is not None),
                    key=lambda v: -float(v["net_gain"]))
    return {"pairings_evaluated": len(seen), "best": ranked[:5],
            "best_by_model": {m: next((v for v in ranked if v["model"] == m), None)
                              for m in models},
            "n_earning": sum(1 for v in ranked if v.get("verdict") == "EARNS_ITS_PLACE"),
            "trials": len(seen)}
