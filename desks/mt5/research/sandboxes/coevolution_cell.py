"""FACTOR <-> MODEL COEVOLUTION CELL -- RD-Agent(Q)'s loop, stripped of the agent and the LLM.

Two populations are evolved AGAINST each other. The FACTOR population is sets of formulaic
factors drawn from a small price-only grammar (returns, EMA differences, z-scores, range
position, vol ratios, volume z, RSI) over the bundle's own bars; the MODEL population is
numpy models (ridge at several ridges, a sign vote, a quantile-bucket model). Each generation
alternates: every factor set is scored against the CURRENT BEST MODEL, then every model against
the CURRENT BEST FACTOR SET, both walk-forward on the sign of the next-h return and scored as
out-of-sample log score minus the base-rate baseline (nats per prediction). Selection keeps the
top third, crossover and mutation refill the rest, and every evaluation is a charged trial.

WHAT LEAVES. Survivors (pairings with positive OOS net gain) become candidates WITH LINEAGE
(factor expressions, model spec, generation, parent ids) under the registered family their
dominant factor names -- an EMA difference is `trend_ma_cross`, a z-score `mean_reversion_
bollinger`, RSI `mean_reversion_rsi`, range position `range_reversion`, a vol ratio
`vol_mean_reversion`, a volume z `volume_spike` -- with the fitted parameters as the recipe.
When `libs.research.coevolution` (the desk's feature-store + model-zoo breeder, pandas) is
importable, a small run of it is added as a research method row for comparison; the numpy
loop is what runs on this box today.
"""
from __future__ import annotations

import json
import math
from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

from . import CellContext, system_id

CELL = "coevolution_cell"
SYSTEM = system_id(CELL)
CAPABILITY_FAMILY = "factor_model_coevolution"
UPSTREAM = ("alphagen", "openevolve", "pyribs")
FALLBACK = "numpy factor grammar x numpy model zoo, alternating coevolution, walk-forward"
HORIZON_BARS = 24
POP_F, POP_M, GENS = 10, 5, 4
MAX_SYMBOLS = 4
MIN_BARS = 800
#: op -> registered family and the parameter names the recipe carries.
FAMILY_OF_OP: dict[str, str] = {
    "ema_diff": "trend_ma_cross", "zscore": "mean_reversion_bollinger", "rsi": "mean_reversion_rsi",
    "range_pos": "range_reversion", "vol_ratio": "vol_mean_reversion", "volume_z": "volume_spike",
    "ret": "momentum_volgate",
}
GRAMMAR: tuple[tuple[str, dict[str, tuple[int, ...]]], ...] = (
    ("ret", {"h": (1, 4, 12, 24, 48)}),
    ("ema_diff", {"fast": (5, 8, 12, 20), "slow": (30, 50, 80, 120)}),
    ("zscore", {"w": (24, 48, 96, 240)}),
    ("rsi", {"w": (7, 14, 21)}),
    ("range_pos", {"w": (24, 48, 120)}),
    ("vol_ratio", {"w1": (12, 24), "w2": (96, 240)}),
    ("volume_z", {"w": (24, 96)}),
)
MODELS: tuple[str, ...] = ("ridge", "sign_vote", "bucket")


# ------------------------------------------------------------------------------- factors

def _ema(x: Any, n: int) -> Any:
    import numpy as np
    out = np.empty_like(x)
    a = 2.0 / (n + 1.0)
    out[0] = x[0]
    for i in range(1, x.shape[0]):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def _roll(x: Any, w: int, fn: str) -> Any:
    import numpy as np
    n = x.shape[0]
    out = np.full(n, np.nan)
    if n < w:
        return out
    view = np.lib.stride_tricks.sliding_window_view(x, w)
    val = {"mean": view.mean(axis=1), "std": view.std(axis=1), "max": view.max(axis=1),
           "min": view.min(axis=1)}[fn]
    out[w - 1:] = val
    return out


def factor(frame: A.BarFrame, op: str, params: dict[str, int]) -> Any:
    """One factor series aligned to the bars (NaN where undefined), numpy only."""
    import numpy as np
    c = np.asarray(frame.close, dtype=float)
    h_, l_ = np.asarray(frame.high, dtype=float), np.asarray(frame.low, dtype=float)
    v = np.asarray(frame.volume, dtype=float)
    lc = np.log(np.maximum(c, 1e-12))
    r = np.diff(lc, prepend=lc[0])
    if op == "ret":
        h = params["h"]
        out = np.full(c.shape[0], np.nan)
        out[h:] = lc[h:] - lc[:-h]
        return out
    if op == "ema_diff":
        return (_ema(c, params["fast"]) - _ema(c, params["slow"])) / np.maximum(c, 1e-12)
    if op == "zscore":
        w = params["w"]
        return (c - _roll(c, w, "mean")) / np.maximum(_roll(c, w, "std"), 1e-12)
    if op == "rsi":
        w = params["w"]
        up, dn = _roll(np.maximum(r, 0.0), w, "mean"), _roll(np.maximum(-r, 0.0), w, "mean")
        return 100.0 - 100.0 / (1.0 + up / np.maximum(dn, 1e-12)) - 50.0
    if op == "range_pos":
        w = params["w"]
        hi, lo = _roll(h_, w, "max"), _roll(l_, w, "min")
        return (c - lo) / np.maximum(hi - lo, 1e-12) - 0.5
    if op == "vol_ratio":
        return _roll(r, params["w1"], "std") / np.maximum(_roll(r, params["w2"], "std"), 1e-12) - 1
    if op == "volume_z":
        w = params["w"]
        return (v - _roll(v, w, "mean")) / np.maximum(_roll(v, w, "std"), 1e-12)
    raise KeyError(op)


def expr(op: str, params: dict[str, int]) -> str:
    return f"{op}({', '.join(f'{k}={v}' for k, v in sorted(params.items()))})"


# ------------------------------------------------------------------------------- models

def fit_predict(model: dict[str, Any], X: Any, y: Any, Xt: Any) -> Any:
    """P(up) on Xt from a model fitted on (X, y in {0,1})."""
    import numpy as np
    kind = model["kind"]
    if kind == "ridge":
        lam = float(model.get("lam", 1.0))
        Xa = np.column_stack([np.ones(X.shape[0]), X])
        w = np.linalg.solve(Xa.T @ Xa + lam * np.eye(Xa.shape[1]), Xa.T @ (y - 0.5))
        z = np.column_stack([np.ones(Xt.shape[0]), Xt]) @ w
        return 1.0 / (1.0 + np.exp(-np.clip(z * float(model.get("gain", 8.0)), -30, 30)))
    if kind == "sign_vote":
        corr = np.asarray([np.corrcoef(X[:, j], y)[0, 1] if X[:, j].std() > 0 else 0.0
                           for j in range(X.shape[1])])
        corr = np.nan_to_num(corr)
        vote = (np.sign(Xt) * np.sign(corr)).mean(axis=1)
        return 0.5 + 0.5 * float(model.get("strength", 0.3)) * vote
    if kind == "bucket":
        nb = int(model.get("bins", 4))
        j = int(model.get("column", 0)) % X.shape[1]
        edges = np.quantile(X[:, j], np.linspace(0, 1, nb + 1)[1:-1])
        b_tr, b_te = np.searchsorted(edges, X[:, j]), np.searchsorted(edges, Xt[:, j])
        base = float(y.mean())
        means = np.asarray([(y[b_tr == k].mean() if (b_tr == k).sum() >= 10 else base)
                            for k in range(nb)])
        return means[b_te]
    raise KeyError(kind)


def evaluate(fset: list[tuple[str, dict[str, int]]], model: dict[str, Any],
             frame: A.BarFrame, *, horizon: int = HORIZON_BARS) -> dict[str, Any]:
    """Walk-forward OOS log score minus the base-rate baseline, nats per prediction."""
    import numpy as np
    cols = [factor(frame, op, p) for op, p in fset]
    X = np.column_stack(cols)
    lc = np.log(np.maximum(np.asarray(frame.close, dtype=float), 1e-12))
    fwd = np.full(lc.shape[0], np.nan)
    fwd[:-horizon] = lc[horizon:] - lc[:-horizon]
    ok = np.isfinite(X).all(axis=1) & np.isfinite(fwd)
    rows = np.flatnonzero(ok)[::horizon]  # non-overlapping targets
    X, y = X[rows], (fwd[rows] > 0).astype(float)
    n = X.shape[0]
    if n < 60:
        return {"net_gain": None, "n": n, "why": "too few non-overlapping rows"}
    sd = np.maximum(X.std(axis=0), 1e-12)
    X = (X - X.mean(axis=0)) / sd
    folds, k = 4, n // 5
    ll_model: list[float] = []
    ll_base: list[float] = []
    for f_ in range(folds):
        cut = k * (f_ + 1)
        te = slice(cut, min(cut + k, n))
        if te.stop <= te.start:
            break
        p = np.clip(fit_predict(model, X[:cut], y[:cut], X[te]), 0.02, 0.98)
        base = float(np.clip(y[:cut].mean(), 0.02, 0.98))
        yt = y[te]
        ll_model.append(float(np.mean(yt * np.log(p) + (1 - yt) * np.log(1 - p))))
        ll_base.append(float(np.mean(yt * np.log(base) + (1 - yt) * np.log(1 - base))))
    if not ll_model:
        return {"net_gain": None, "n": n, "why": "no fold"}
    gain = float(np.mean(ll_model) - np.mean(ll_base))
    return {"net_gain": gain, "n": int(sum(min(k, n - k * (i + 1)) for i in range(len(ll_model)))),
            "folds": len(ll_model), "why": ""}


# ------------------------------------------------------------------------------- evolution

def _rand_factor(rng: Any) -> tuple[str, dict[str, int]]:
    op, grid = GRAMMAR[int(rng.integers(len(GRAMMAR)))]
    params = {k: int(rng.choice(v)) for k, v in grid.items()}
    if op == "ema_diff" and params["slow"] <= params["fast"]:
        params["slow"] = params["fast"] * 3
    return op, params


def _rand_model(rng: Any) -> dict[str, Any]:
    kind = MODELS[int(rng.integers(len(MODELS)))]
    if kind == "ridge":
        return {"kind": kind, "lam": float(rng.choice([0.1, 1.0, 10.0])),
                "gain": float(rng.choice([4.0, 8.0, 16.0]))}
    if kind == "sign_vote":
        return {"kind": kind, "strength": float(rng.choice([0.2, 0.3, 0.5]))}
    return {"kind": kind, "bins": int(rng.choice([3, 4, 5])), "column": int(rng.integers(4))}


def _fkey(fset: list[tuple[str, dict[str, int]]]) -> str:
    return " & ".join(sorted(expr(op, p) for op, p in fset))


def _mkey(model: dict[str, Any]) -> str:
    return json.dumps(model, sort_keys=True)


def coevolve(frame: A.BarFrame, *, seed: int, deadline: A.Deadline) -> dict[str, Any]:
    import numpy as np
    rng = np.random.default_rng(seed)
    factors: list[list[tuple[str, dict[str, int]]]] = [
        [_rand_factor(rng) for _ in range(int(rng.integers(1, 4)))] for _ in range(POP_F)]
    models: list[dict[str, Any]] = [_rand_model(rng) for _ in range(POP_M)]
    seen: dict[str, dict[str, Any]] = {}
    lineage: dict[str, dict[str, Any]] = {}
    trials = 0
    best_m, best_f = models[0], factors[0]
    for gen in range(GENS):
        # factors against the current best model
        scored_f: list[tuple[float, list[tuple[str, dict[str, int]]]]] = []
        for fset in factors:
            if deadline.expired():
                break
            key = f"{_fkey(fset)} | {_mkey(best_m)}"
            if key not in seen:
                seen[key] = evaluate(fset, best_m, frame)
                trials += 1
                lineage.setdefault(_fkey(fset), {"generation": gen, "parents": []})
            g = seen[key].get("net_gain")
            if g is not None:
                scored_f.append((float(g), fset))
        if scored_f:
            scored_f.sort(key=lambda t: -t[0])
            best_f = scored_f[0][1]
            elite = [f for _, f in scored_f[: max(2, len(scored_f) // 3)]]
            children = list(elite)
            while len(children) < POP_F:
                a, b = elite[int(rng.integers(len(elite)))], elite[int(rng.integers(len(elite)))]
                child = list({expr(op, p): (op, p) for op, p in (a[: len(a) // 2 + 1]
                                                               + b[len(b) // 2:])}.values())
                if rng.random() < 0.4:
                    child.append(_rand_factor(rng))
                child = child[:4]
                lineage.setdefault(_fkey(child), {"generation": gen + 1,
                                                  "parents": [_fkey(a), _fkey(b)]})
                children.append(child)
            factors = children
        # models against the current best factor set
        scored_m: list[tuple[float, dict[str, Any]]] = []
        for model in models:
            if deadline.expired():
                break
            key = f"{_fkey(best_f)} | {_mkey(model)}"
            if key not in seen:
                seen[key] = evaluate(best_f, model, frame)
                trials += 1
            g = seen[key].get("net_gain")
            if g is not None:
                scored_m.append((float(g), model))
        if scored_m:
            scored_m.sort(key=lambda t: -t[0])
            best_m = scored_m[0][1]
            keep = [m for _, m in scored_m[: max(2, len(scored_m) // 2)]]
            models = keep + [_rand_model(rng) for _ in range(POP_M - len(keep))]
    survivors = []
    for key, res in seen.items():
        g = res.get("net_gain")
        if g is not None and g > 0:
            fk, mk = key.split(" | ", 1)
            survivors.append({"factors": fk, "model": json.loads(mk), "net_gain_nats": float(g),
                              "n": res.get("n"), **lineage.get(fk, {})})
    survivors.sort(key=lambda s: -s["net_gain_nats"])
    return {"trials": trials, "pairings": len(seen), "survivors": survivors,
            "best_factors": _fkey(best_f), "best_model": best_m}


def _dominant(fk: str) -> tuple[str, dict[str, int]]:
    """The first factor of a factor-set key, parsed back to (op, params)."""
    first = fk.split(" & ")[0]
    op, _, inner = first.partition("(")
    params: dict[str, int] = {}
    for part in inner.rstrip(")").split(", "):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k] = int(v)
    return op, params


def run(bundle: A.ResearchBundle, ctx: CellContext) -> ExternalResearchPacket:
    deadline = A.Deadline(min(bundle.compute_budget_s, ctx.budget_s))
    frames = [f for f in bundle.frames("H1") if len(f) >= MIN_BARS][:MAX_SYMBOLS]
    if not frames:
        return A.unmeasured(SYSTEM, bundle, f"no H1 frame with {MIN_BARS}+ bars")
    trials = 0
    cands: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    reps: list[dict[str, Any]] = []
    for i, f in enumerate(frames):
        if deadline.expired():
            break
        res = coevolve(f, seed=bundle.seed + i, deadline=deadline)
        trials += res["trials"]
        # the measured landscape is a REPRESENTATION of the instrument: which factor grammar
        # and which model class carry any out-of-sample structure now, and how much
        reps.append({"kind": "coevolution_landscape", "symbol": f.symbol,
                     "pairings": res["pairings"], "positive_pairings": len(res["survivors"]),
                     "best_factors": res["best_factors"], "best_model": res["best_model"],
                     "best_net_gain_nats": (res["survivors"][0]["net_gain_nats"]
                                            if res["survivors"] else None),
                     "generations": GENS, "populations": {"factors": POP_F, "models": POP_M},
                     "representation": "no positive pairing is itself a state: the grammar "
                                       "finds nothing the base rate does not already say"})
        for s in res["survivors"][:3]:
            op, params = _dominant(s["factors"])
            family = FAMILY_OF_OP.get(op, "momentum_volgate")
            cands.append(A.candidate(
                family, [f.symbol],
                f"{f.symbol} H1 {family}: coevolved pairing {s['factors']} with model "
                f"{s['model']['kind']} earns {s['net_gain_nats']:+.4f} nats/prediction over "
                f"the base rate walk-forward (n={s['n']}, generation {s.get('generation')}) "
                f"-- a recipe for the ten gates, never a verdict",
                horizon=bundle.horizons[-1], source=SYSTEM,
                evidence={"parameters": params, "factors": s["factors"], "model": s["model"],
                          "net_gain_nats": s["net_gain_nats"], "n": s["n"],
                          "lineage": {"generation": s.get("generation"),
                                      "parents": s.get("parents", []), "cell": CELL}}))
    engine_note = "numpy coevolution"
    coev = A.library("libs.research.coevolution") if ctx.reference_engines else None
    if coev is not None and not deadline.expired() and deadline.left() > 60:
        try:
            pd = A.library("pandas")
            f0 = frames[0]
            if pd is not None:
                df = pd.DataFrame({"open": f0.open, "high": f0.high, "low": f0.low,
                                   "close": f0.close, "tick_volume": f0.volume,
                                   "spread": float("nan")},
                                  index=pd.to_datetime(list(f0.time)))
                up = coev.evolve(df, pop=6, gens=2, budget_s=min(120.0, deadline.left() * 0.5),
                                 seed=bundle.seed, symbol=f0.symbol)
                trials += int(up.get("pairings_evaluated") or 0)
                rows.append({"kind": "coevolution_reference", "engine": "libs.research."
                             "coevolution (feature store + model zoo)", "symbol": f0.symbol,
                             "pairings": up.get("pairings_evaluated"),
                             "n_earning": up.get("n_earning"),
                             "best": [{k: b.get(k) for k in ("features", "model", "net_gain")}
                                      for b in (up.get("best") or [])[:3]]})
                engine_note += " + libs.research.coevolution reference"
        except Exception as exc:
            rows.append({"kind": "UNMEASURED", "engine": "libs.research.coevolution",
                         "why": f"{type(exc).__name__}: {exc}"[:200]})
    _ = math
    return A.packet(SYSTEM, bundle, trials=trials, candidates=cands, representations=reps,
                    research_methods=rows, note=engine_note)
