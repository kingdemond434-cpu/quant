"""ADAPTIVE CONFORMAL CALIBRATION -- MAPIE's mechanism rebuilt so it runs today, and its
calibrated intervals handed to the dislocation lab through a guarded hook.

The forecast is a ridge regression of the next-h return on lagged returns and realised vol.
Adaptive conformal inference (Gibbs & Candes: alpha_{t+1} = alpha_t + gamma (alpha - err_t))
keeps the interval's coverage honest under distribution shift by widening after misses and
tightening after hits; MAPIE's split-conformal intervals are used instead when the library is
installed (`libs.research.adapters.mapie`). Per symbol and horizon the cell measures coverage on
the tail, the interval width relative to realised vol, and the last interval.

WHAT LEAVES. Representations (the intervals and their measured coverage), hypotheses for the
gauntlet (a broken exchangeability -- measured coverage far from target -- is a
`vol_transition`; an interval much narrower than realised vol is a `volatility_squeeze`), and
the calibration file `reports/SANDBOX_CONFORMAL.json` that `dislocation_lab._conformal_gap`
reads: the measured coverage gap becomes part of the ensemble's uncertainty term, TWO-SIDED
(it moves the term toward the measured gap whether that tightens or widens the threshold),
which is how a calibrated interval reaches the probabilities without a cap or a veto.
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

from . import CellContext, system_id

CELL = "conformal_calibration"
SYSTEM = system_id(CELL)
CAPABILITY_FAMILY = "conformal_uncertainty"
UPSTREAM = ("mapie",)
FALLBACK = "adaptive conformal inference (ACI) around a ridge forecast, numpy only"
TARGET = 0.9
GAMMA = 0.02
HORIZON_BARS = {"4h": 4, "24h": 24}
MIN_ROWS = 400
CALIBRATION_FILE = "SANDBOX_CONFORMAL.json"
GAP_TRANSITION = 0.08
SQUEEZE_RATIO = 0.6


def aci(X: Any, y: Any, *, target: float = TARGET, gamma: float = GAMMA,
        train: int = 240) -> dict[str, Any]:
    """Adaptive conformal intervals around a rolling ridge forecast. Returns the tail's
    measured coverage, mean width, the last interval and the final alpha."""
    import numpy as np
    n = X.shape[0]
    alpha = 1.0 - target
    scores: list[float] = []
    covered: list[bool] = []
    widths: list[float] = []
    last = (float("nan"), float("nan"), float("nan"))
    lam = 1.0
    for t in range(train, n):
        Xt, yt = X[t - train:t], y[t - train:t]
        w = np.linalg.solve(Xt.T @ Xt + lam * np.eye(Xt.shape[1]), Xt.T @ yt)
        pred = float(X[t] @ w)
        if len(scores) >= 30:
            q_level = min(max(1.0 - alpha, 0.0), 1.0)
            q = float(np.quantile(np.asarray(scores), q_level))
            lo, hi = pred - q, pred + q
            miss = not (lo <= y[t] <= hi)
            covered.append(not miss)
            widths.append(hi - lo)
            alpha = alpha + gamma * ((1.0 - target) - float(miss))
            alpha = min(max(alpha, 0.001), 0.5)
            last = (pred, lo, hi)
        scores.append(abs(y[t] - pred))
        if len(scores) > 500:
            scores.pop(0)
    return {"coverage_measured": float(np.mean(covered)) if covered else float("nan"),
            "n_test": len(covered), "mean_width": float(np.mean(widths)) if widths
            else float("nan"), "last_point": last[0], "last_interval": [last[1], last[2]],
            "alpha_final": alpha}


def _write_calibration(ctx: CellContext, table: dict[str, Any]) -> str:
    if ctx.dry_run:
        return "dry run: calibration file not written"
    path = ctx.reports / CALIBRATION_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                                   "target": TARGET, "source": SYSTEM,
                                   "rule": "coverage_gap = |measured - target|; the dislocation "
                                           "lab blends it into its uncertainty term two-sided",
                                   "by_symbol": table}, indent=1, default=str),
                       encoding="utf-8")
        os.replace(tmp, path)
        return str(path)
    except OSError as exc:
        return f"UNWRITTEN: {type(exc).__name__}: {exc}"


def run(bundle: A.ResearchBundle, ctx: CellContext) -> ExternalResearchPacket:
    import numpy as np
    engine = "ACI (numpy)"
    mapie_reps: dict[tuple[str, float], dict[str, Any]] = {}
    if A.library("mapie.regression") is not None and A.library("sklearn.linear_model") is not None:
        try:
            from libs.research.adapters import mapie as mapie_adapter
            for row in mapie_adapter.run(bundle).representations:
                if row.get("kind") == "conformal_interval":
                    mapie_reps[(str(row["symbol"]), float(row["confidence_level"]))] = dict(row)
            engine = "MAPIE split conformal (adapter) + ACI (numpy) for the adaptive tail"
        except Exception as exc:
            engine = f"ACI (numpy); MAPIE adapter raised {type(exc).__name__}"
    deadline = A.Deadline(min(bundle.compute_budget_s, ctx.budget_s))
    trials = 0
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    table: dict[str, Any] = {}
    for f in bundle.frames("H1"):
        if deadline.expired():
            break
        vol_now = float(np.std(f.log_returns()[-24:])) if len(f) > 25 else float("nan")
        for h, hb in HORIZON_BARS.items():
            X, y, _ = A.lagged_design(f, target_bars=hb)
            if X.shape[0] < MIN_ROWS or deadline.expired():
                continue
            trials += 1
            res = aci(X, y)
            gap = abs(res["coverage_measured"] - TARGET) if np.isfinite(res["coverage_measured"]) \
                else float("nan")
            realised = float(np.std(y[-res["n_test"]:])) if res["n_test"] > 1 else float("nan")
            ratio = (res["mean_width"] / max(realised, 1e-12)) if np.isfinite(realised) \
                and np.isfinite(res["mean_width"]) else float("nan")
            row = {"kind": "conformal_interval", "engine": engine, "symbol": f.symbol,
                   "horizon": h, "confidence_level": TARGET, **res, "coverage_gap": gap,
                   "width_over_realised_vol": ratio, "vol_now": vol_now,
                   "representation": "interval width relative to realised vol is an "
                                     "uncertainty state; the coverage gap says whether "
                                     "exchangeability held on the tail"}
            m = mapie_reps.get((f.symbol, TARGET))
            if m is not None:
                row["mapie_coverage_measured"] = m.get("coverage_measured")
                row["mapie_width_over_vol"] = m.get("width_over_vol")
            reps.append(row)
            table.setdefault(f.symbol, {})[h] = {
                "coverage_measured": res["coverage_measured"], "coverage_gap": gap,
                "n_test": res["n_test"], "width_over_realised_vol": ratio,
                "last_interval": res["last_interval"], "engine": engine}
            if np.isfinite(gap) and gap > GAP_TRANSITION:
                cands.append(A.candidate(
                    "vol_transition", [f.symbol],
                    f"{f.symbol} H1/{h}: adaptive conformal coverage {res['coverage_measured']:.2f}"
                    f" vs target {TARGET:.2f} over {res['n_test']} bars -- exchangeability broke;"
                    f" a volatility-transition hypothesis",
                    horizon=h, source=SYSTEM,
                    evidence={"coverage_measured": res["coverage_measured"], "coverage_gap": gap,
                              "n_test": res["n_test"], "engine": engine}))
            elif np.isfinite(ratio) and ratio < SQUEEZE_RATIO:
                cands.append(A.candidate(
                    "volatility_squeeze", [f.symbol],
                    f"{f.symbol} H1/{h}: the calibrated {TARGET:.0%} interval is {ratio:.2f}x "
                    f"the realised {h} vol -- the forecast is tighter than the tape; a squeeze "
                    f"hypothesis",
                    horizon=h, source=SYSTEM,
                    evidence={"width_over_realised_vol": ratio,
                              "coverage_measured": res["coverage_measured"], "engine": engine}))
    written = _write_calibration(ctx, table) if table else "nothing measured"
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    research_methods=[{"kind": "calibration_feed", "file": written,
                                       "consumer": "desks/mt5/research/dislocation_lab.py "
                                                   "(_conformal_gap hook, two-sided)",
                                       "symbols": sorted(table)}],
                    note=engine)
