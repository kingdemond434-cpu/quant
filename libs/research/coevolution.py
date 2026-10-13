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

from libs.data.feature_lifecycle import withdraw
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


def live_vocab(store: FeatureStore | None = None
               ) -> tuple[tuple[tuple[str, dict[str, Any]], ...], list[str]]:
    """VOCAB minus every feature the ledger has withdrawn effort from, and the names dropped.

    CO-EVOLUTION IS WHERE FEATURE EFFORT IS ACTUALLY SPENT: every pairing bred here computes the
    whole feature set, so a DEAD or REDUNDANT column costs that compute on every generation while
    contributing a column `research/feature_roi.py` has already measured as worthless or as a
    duplicate of one already in the matrix. The vocabulary is therefore filtered BEFORE the search
    starts rather than the results filtered after it. A feature the ledger has never judged is NEW
    and stays in -- an unmeasured feature is UNMEASURED, not dead.
    """
    status: dict[str, str] = {}
    try:
        for doc in (store or FeatureStore()).sidecars():
            st = str(doc.get("status") or "")
            if st:
                status[str(doc.get("name"))] = st
    except Exception:
        return VOCAB, []                                     # no ledger is not a dead vocabulary
    keep: list[tuple[str, dict[str, Any]]] = []
    dropped: list[str] = []
    for name, params in VOCAB:
        if withdraw(status.get(name, "NEW")).may_spend:
            keep.append((name, params))
        else:
            dropped.append(f"{name} ({status.get(name)})")
    return tuple(keep), sorted(set(dropped))


def _key(fset: list[int], model: str) -> str:
    return json.dumps({"f": sorted(fset), "m": model})


def _specs(fset: list[int], symbol: str | None,
           vocab: tuple[tuple[str, dict[str, Any]], ...] = VOCAB
           ) -> list[tuple[str, dict[str, Any]]]:
    """The feature specs, with the instrument substituted into any symbol-bearing entry."""
    out: list[tuple[str, dict[str, Any]]] = []
    for i in sorted(fset):
        name, params = vocab[i]
        if symbol and "symbol" in params:
            params = {**params, "symbol": symbol}
        out.append((name, params))
    return out


def evaluate(df: pd.DataFrame, fset: list[int], model: str, store: FeatureStore,
             horizon: int = 6, symbol: str | None = None,
             vocab: tuple[tuple[str, dict[str, Any]], ...] = VOCAB,
             from_row: int = 0) -> dict[str, Any]:
    """`from_row` scores only bars at or after that position. The features are still computed on
    the whole frame -- they are trailing, so the earlier bars are warm-up and never the target."""
    specs = _specs(fset, symbol, vocab)
    x = store.matrix(df, [(n, p) for n, p in specs])
    y_raw = target(df, horizon)
    ok = np.isfinite(x).all(axis=1) & np.isfinite(y_raw)
    # Non-overlapping targets: one row per horizon so the folds are not autocorrelated copies.
    rows = np.where(ok)[0]
    rows = rows[rows >= from_row][::horizon]
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
    vocab, dropped = live_vocab(store)
    if not vocab:
        return {"pairings_evaluated": 0, "best": [], "trials": 0, "n_earning": 0,
                "best_by_model": dict.fromkeys(models),
                "vocab_size": 0, "vocab_dropped": dropped,
                "why": "every vocabulary entry has had its effort withdrawn by the feature ledger"}
    n_v = len(vocab)
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
                    seen[k] = evaluate(df, fset, model, store, horizon, symbol, vocab)
                except Exception as exc:
                    seen[k] = {"features": [str(i) for i in fset], "model": model,
                               "verdict": "FAILED", "why": f"{type(exc).__name__}: {exc}",
                               "net_gain": None}
                seen[k]["fset"] = list(fset)
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
            "vocab_size": n_v, "vocab_dropped": dropped,
            "best_by_model": {m: next((v for v in ranked if v["model"] == m), None)
                              for m in models},
            "n_earning": sum(1 for v in ranked if v.get("verdict") == "EARNS_ITS_PLACE"),
            "trials": len(seen)}


def sequential(df: pd.DataFrame, *, store: FeatureStore | None = None, n_evals: int = 36,
               budget_s: float = 300.0, horizon: int = 6,
               models: tuple[str, ...] = tuple(TAX), symbol: str | None = None
               ) -> dict[str, Any]:
    """THE CHALLENGER'S BASELINE: features first, model afterwards -- the conventional pipeline
    `evolve` claims to beat. Greedy forward selection of a feature set under ONE reference model
    (the cheapest by tax), then every model tried on the chosen set. It is given exactly
    `n_evals` evaluations -- the joint search's own count -- so the comparison is matched on
    compute, and it spends them the way a features-then-model researcher would."""
    store = store or FeatureStore()
    vocab, _dropped = live_vocab(store)
    if not vocab or not models:
        return {"pairings_evaluated": 0, "best": None, "why": "no vocabulary or no model"}
    ref = min(models, key=lambda m: float(TAX.get(m, 0.0)))
    stage2 = len(models)
    budget1 = max(1, n_evals - stage2)
    seen: dict[str, dict[str, Any]] = {}
    started = time.monotonic()

    def _eval(fset: list[int], model: str) -> float | None:
        k = _key(fset, model)
        if k not in seen:
            try:
                seen[k] = evaluate(df, fset, model, store, horizon, symbol, vocab)
            except Exception as exc:
                seen[k] = {"model": model, "verdict": "FAILED", "net_gain": None,
                           "why": f"{type(exc).__name__}: {exc}"}
            seen[k]["fset"] = list(fset)
        g = seen[k].get("net_gain")
        return None if g is None else float(g)

    chosen: list[int] = []
    best_g = -float("inf")
    while len(chosen) < 6 and len(seen) < budget1 and time.monotonic() - started < budget_s:
        step = None
        for j in range(len(vocab)):
            if j in chosen or len(seen) >= budget1:
                continue
            g = _eval(sorted([*chosen, j]), ref)
            if g is not None and g > best_g:
                best_g, step = g, j
        if step is None:
            break
        chosen = sorted([*chosen, step])
    for m in models:
        if chosen and len(seen) < n_evals and time.monotonic() - started < budget_s:
            _eval(chosen, m)
    # MATCHED COMPUTE MEANS EQUAL, NOT AT MOST (audit, 2026-10-06). A greedy pass that stops early
    # spends what is left the way the same researcher would next: every model on the runner-up
    # feature sets, best first, until the joint arm's count is reached or nothing is left to try.
    while len(seen) < n_evals and time.monotonic() - started < budget_s:
        sets = sorted((v for v in list(seen.values()) if v.get("net_gain") is not None),
                      key=lambda v: -float(v["net_gain"]))
        todo = [(list(v["fset"]), m) for v in sets for m in models
                if _key(list(v["fset"]), m) not in seen]
        if not todo:
            break
        _eval(*todo[0])
    ranked = sorted((v for v in seen.values() if v.get("net_gain") is not None),
                    key=lambda v: -float(v["net_gain"]))
    return {"pairings_evaluated": len(seen), "best": ranked[0] if ranked else None,
            "reference_model": ref, "chosen": chosen,
            "seconds": round(time.monotonic() - started, 3)}


def head_to_head(df: pd.DataFrame, *, store: FeatureStore | None = None, pop: int = 8,
                 gens: int = 2, budget_s: float = 90.0, seed: int = 0, horizon: int = 6,
                 models: tuple[str, ...] = tuple(TAX), symbol: str | None = None,
                 dev_frac: float = 0.6, progress: dict[str, int] | None = None
                 ) -> dict[str, Any]:
    """RESEARCH THE RESEARCHER: joint (F, M) search against features-then-model, on the SAME
    bars, the SAME target and the SAME number of evaluations. Both arms select on the first
    `dev_frac` of the bars only; each arm's single winner is then scored ONCE on the untouched
    tail, which neither arm saw while choosing. One run is one paired trial; the verdict across
    runs is the arena's (`libs/research/arena.judge`), never this function's.

    `progress`, when given, holds an upper bound on the evaluations spent so far at every point,
    so a run that raises is still charged (`spent_bound`): the stage in flight at its cap."""
    prog = progress if progress is not None else {}
    prog["spent_bound"] = pop * gens                    # the joint stage's most, before it runs
    store = store or FeatureStore()
    cut = int(len(df) * dev_frac)
    dev, test = df.iloc[:cut], df.iloc[cut:]           # test: scored once, never selected on
    vocab, _dropped = live_vocab(store)
    t0 = time.monotonic()
    joint = evolve(dev, store=store, pop=pop, gens=gens, budget_s=budget_s / 2, seed=seed,
                   horizon=horizon, models=models, symbol=symbol)
    t_joint = time.monotonic() - t0
    n = int(joint.get("pairings_evaluated") or 0)
    prog["spent_bound"] = n + max(n, 1)                 # the sequential stage at its cap
    t1 = time.monotonic()
    seq = sequential(dev, store=store, n_evals=max(n, 1), budget_s=budget_s / 2,
                     horizon=horizon, models=models, symbol=symbol)
    t_seq = time.monotonic() - t1

    def _oos(best: dict[str, Any] | None) -> dict[str, Any]:
        if not best or best.get("fset") is None:
            return {"net_gain": None, "why": "the arm produced no scored pairing"}
        try:
            r = evaluate(df, list(best["fset"]), str(best["model"]), store, horizon, symbol,
                         vocab, from_row=cut)
        except Exception as exc:
            return {"net_gain": None, "why": f"{type(exc).__name__}: {exc}"}
        return {"net_gain": r.get("net_gain"), "n": r.get("n"), "model": best["model"],
                "features": best.get("features"), "dev_net_gain": best.get("net_gain")}

    jb = (joint.get("best") or [None])[0]
    tail = [0]

    n_seq0 = int(seq.get("pairings_evaluated") or 0)
    prog["spent_bound"] = n + n_seq0 + 2                # both tail scorings at their cap

    def _scored(best: dict[str, Any] | None) -> dict[str, Any]:
        if best and best.get("fset") is not None:
            tail[0] += 1                    # each tail scoring is an evaluation: charged
        return _oos(best)
    a, b = _scored(jb), _scored(seq.get("best"))
    ga, gb = a.get("net_gain"), b.get("net_gain")
    winner = None
    if ga is not None and gb is not None:
        winner = "joint" if float(ga) > float(gb) else "sequential" if float(gb) > float(ga) \
            else "tie"
    n_seq = n_seq0
    prog["spent_bound"] = n + n_seq + tail[0]
    return {"symbol": symbol, "bars_dev": len(dev), "bars_test": len(test),
            "evals": {"joint": n, "sequential": n_seq, "tail_scorings": tail[0]},
            "matched_compute": n_seq == n,
            "seconds": {"joint": round(t_joint, 3), "sequential": round(t_seq, 3)},
            "joint": a, "sequential": b, "winner": winner,
            "trials": n + n_seq + tail[0]}
