"""GARCH(1,1) VOLATILITY FORECASTS PER INSTRUMENT, SCORED AGAINST THE EWMA BASELINE THEY MUST BEAT.

    python desks/mt5/research/garch_vol.py --once --budget-s 600

WHY THIS ORGAN EXISTS (backlog N16, 2026-10-13: "wire the EXISTS-UNWIRED organs"). The GARCH
fit was already in the tree -- `libs.research.stationarity.garch_conditional_vol`, a thin wrapper
over `arch`, the constitution's required backend -- and so was the baseline it has to beat,
`libs.research.volatility_signals.ewma_variance` (RiskMetrics, lambda 0.94). Neither ran on any
clock, so the question `volatility_signals` itself raises ("if the premium carries signal under
EWMA, the GARCH upgrade becomes a measured improvement over a recorded baseline") had no
recorded baseline and no measurement. This organ is that measurement, hourly, per instrument.

WHAT IS MEASURED, AND HOW IT CANNOT CHEAT. Daily log returns from the desk's own H1 bars. The
last `HOLDOUT_DAYS` are held out; GARCH(1,1) is fitted on the days BEFORE them only, then run
forward over the holdout with its parameters FIXED (`arch`'s `last_obs` + `forecast(start=...)`),
so every holdout forecast is built from returns strictly before the day it forecasts. EWMA's
recursion has the same property by construction. Both are scored with QLIKE,

    mean( log h_t + r_t^2 / h_t )

the loss that is robust to the noise in squared returns as a variance proxy (Patton 2011), so the
ranking says which forecast is closer to the truth, not which one is closer to the noise.

WHAT IT CLAIMS, AND NO MORE. A per-instrument verdict (GARCH_BEATS_EWMA / EWMA_HOLDS) and the
next-day volatility forecast from each. It sizes nothing and gates nothing: a consumer that wants
GARCH vol as an input (the allocator's input ablation arms, a vol-target) must earn that
authority on its own evidence, two-sided, per GROWTH_GOVERNANCE. A missing `arch` backend, a
symbol with too few days, or a fit that does not converge is UNMEASURED with its reason -- never
a silent fallback to EWMA dressed as GARCH.

ROTATION. Symbols are visited in a cursor order under `--budget-s`; a pass that runs out of time
resumes where it stopped, and rows from earlier passes are kept with their own `at` so the
artifact always covers the whole universe it has reached.
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

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNIVERSE = BASE / "data" / "universe"
REPORT = BASE / "reports" / "GARCH_VOL.json"
CURSOR = BASE / "data" / "garch_vol_cursor.json"

#: Days held out for the out-of-sample score. Sixty trading days is roughly a quarter: long
#: enough that QLIKE's mean is not one shock, short enough that the training set is most of the
#: history.
HOLDOUT_DAYS = 60
#: Fewer than this many TRAINING days and a GARCH(1,1) fit is mostly its starting values.
MIN_TRAIN_DAYS = 250
#: The most recent days used at all. Older regimes add fit time and little forecast skill.
MAX_DAYS = 1500
#: GARCH is fitted on percent returns (x100): `arch`'s optimiser is scaled for that, and fitting
#: raw log returns (~1e-2) is the documented cause of non-convergence warnings.
SCALE = 100.0
DEFAULT_BUDGET_S = 600.0

GARCH_BEATS_EWMA, EWMA_HOLDS, UNMEASURED = "GARCH_BEATS_EWMA", "EWMA_HOLDS", "UNMEASURED"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def daily_returns(bars: Any) -> np.ndarray:
    """Daily log returns from an H1 frame (last close per UTC day). Empty when unusable."""
    try:
        close = bars["close"].astype("float64")
        daily = close.groupby(close.index.normalize()).last()
        daily = daily[np.isfinite(daily.to_numpy()) & (daily.to_numpy() > 0)]
        r = np.diff(np.log(daily.to_numpy(dtype="float64")))
    except Exception:
        return np.array([], dtype="float64")
    r = r[np.isfinite(r)]
    return r[-MAX_DAYS:]


def qlike(var_forecast: np.ndarray, returns: np.ndarray) -> float | None:
    """mean(log h + r^2/h) over the days where the forecast is a usable variance."""
    h = np.asarray(var_forecast, dtype="float64")
    r = np.asarray(returns, dtype="float64")
    ok = np.isfinite(h) & (h > 0) & np.isfinite(r)
    if ok.sum() < max(10, len(r) // 2):
        return None
    return float(np.mean(np.log(h[ok]) + r[ok] ** 2 / h[ok]))


def garch_holdout(returns: np.ndarray, holdout: int = HOLDOUT_DAYS) -> dict[str, Any]:
    """Fit GARCH(1,1) on the training days, forecast the holdout one step at a time with fixed
    parameters. Variances are returned in RAW return units (the x100 scale removed)."""
    try:
        from arch import arch_model
    except ImportError:
        return {"status": UNMEASURED, "why": "arch is not installed on this host; GARCH is "
                                              "not substituted by anything else"}
    r = np.asarray(returns, dtype="float64") * SCALE
    n_train = len(r) - holdout
    if n_train < MIN_TRAIN_DAYS:
        return {"status": UNMEASURED,
                "why": f"{n_train} training days < {MIN_TRAIN_DAYS}"}
    import warnings
    try:
        am = arch_model(r, vol="GARCH", p=1, q=1, mean="Zero", rescale=False)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = am.fit(last_obs=n_train, disp="off", show_warning=False)
            # One-step forecasts for every holdout day, each from the data strictly before it.
            fc = res.forecast(start=n_train - 1, horizon=1, reindex=False)
            # One-step forecast for the day after the last observation, on the full sample
            # filtered with the SAME parameters.
            nxt = am.fix(res.params).forecast(horizon=1, reindex=False)
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"fit failed: {type(exc).__name__}: {exc}"[:240]}
    if int(getattr(res, "convergence_flag", 0) or 0) != 0:
        return {"status": UNMEASURED, "why": "the optimiser did not converge"}
    hv = np.asarray(fc.variance.to_numpy(dtype="float64")[:, 0])[:holdout] / SCALE ** 2
    params = {k: float(v) for k, v in res.params.items()}
    alpha, beta = params.get("alpha[1]", float("nan")), params.get("beta[1]", float("nan"))
    next_var = float(np.asarray(nxt.variance.to_numpy(dtype="float64"))[-1, 0]) / SCALE ** 2
    return {"status": "MEASURED", "holdout_var": hv,
            "params": {"omega": params.get("omega"), "alpha": alpha, "beta": beta},
            "persistence": alpha + beta,
            "next_day_vol": math.sqrt(next_var) if next_var > 0 else None}


def score_symbol(returns: np.ndarray, holdout: int = HOLDOUT_DAYS) -> dict[str, Any]:
    """One instrument's GARCH-vs-EWMA verdict on the held-out days."""
    from libs.research.volatility_signals import ewma_variance

    r = np.asarray(returns, dtype="float64")
    if len(r) < MIN_TRAIN_DAYS + holdout:
        return {"verdict": UNMEASURED, "n_days": int(len(r)),
                "why": f"{len(r)} daily returns < {MIN_TRAIN_DAYS + holdout} needed"}
    test = r[-holdout:]
    ew = ewma_variance(r)
    ew_hold = ew[-holdout:]
    # EWMA's forecast for the day AFTER the last return, by one more step of its own recursion.
    from libs.research.volatility_signals import EWMA_LAMBDA
    ew_next = EWMA_LAMBDA * float(ew[-1]) + (1.0 - EWMA_LAMBDA) * float(r[-1]) ** 2
    q_ewma = qlike(ew_hold, test)
    g = garch_holdout(r, holdout)
    row: dict[str, Any] = {"n_days": int(len(r)), "holdout_days": holdout,
                           "qlike_ewma": None if q_ewma is None else round(q_ewma, 6),
                           "ewma_next_day_vol": (round(math.sqrt(ew_next), 8)
                                                 if ew_next > 0 else None)}
    if g.get("status") != "MEASURED":
        row.update({"verdict": UNMEASURED, "why": g.get("why")})
        return row
    q_garch = qlike(g["holdout_var"], test)
    row.update({"qlike_garch": None if q_garch is None else round(q_garch, 6),
                "garch_params": {k: (None if v is None else round(float(v), 8))
                                 for k, v in g["params"].items()},
                "garch_params_scale": "omega in percent-return squared units (returns x100)",
                "persistence": round(float(g["persistence"]), 6),
                "garch_next_day_vol": (None if g["next_day_vol"] is None
                                       else round(float(g["next_day_vol"]), 8))})
    if q_garch is None or q_ewma is None:
        row.update({"verdict": UNMEASURED, "why": "too few usable holdout forecasts to score"})
    else:
        row["verdict"] = GARCH_BEATS_EWMA if q_garch < q_ewma else EWMA_HOLDS
        row["qlike_gain"] = round(q_ewma - q_garch, 6)
    return row


def symbols(universe: Path = UNIVERSE) -> list[str]:
    return sorted(p.name[:-len("_H1.parquet")] for p in universe.glob("*_H1.parquet"))


def _load(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def run(budget_s: float = DEFAULT_BUDGET_S, universe: Path = UNIVERSE,
        report: Path = REPORT, cursor: Path = CURSOR) -> dict[str, Any]:
    import pandas as pd

    t0 = time.monotonic()
    syms = symbols(universe)
    prior = _load(report).get("symbols") or {}
    rows: dict[str, Any] = {k: v for k, v in prior.items() if k in set(syms)}
    start = 0
    last = str(_load(cursor).get("last") or "")
    if last in syms:
        start = syms.index(last) + 1
    order = syms[start:] + syms[:start]
    visited: list[str] = []
    for sym in order:
        if time.monotonic() - t0 > budget_s:
            break
        try:
            bars = pd.read_parquet(universe / f"{sym}_H1.parquet")
            row = score_symbol(daily_returns(bars))
        except Exception as exc:
            row = {"verdict": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"[:240]}
        row["at"] = _now()
        rows[sym] = row
        visited.append(sym)
    verdicts = [str(r.get("verdict")) for r in rows.values()]
    n_meas = sum(v in (GARCH_BEATS_EWMA, EWMA_HOLDS) for v in verdicts)
    n_g = verdicts.count(GARCH_BEATS_EWMA)
    try:
        import arch  # noqa: F401
        backend = "arch"
    except ImportError:
        backend = None
    doc = {
        "at": _now(),
        "status": ("MEASURED" if n_meas else UNMEASURED),
        "why": (None if n_meas else
                ("arch is not installed on this host" if backend is None
                 else "no instrument had enough history to score")),
        "backend": backend,
        "method": ("GARCH(1,1) zero-mean on daily log returns x100, fitted on all but the last "
                   f"{HOLDOUT_DAYS} days, run forward with fixed parameters; EWMA lambda 0.94 "
                   "baseline; both scored by QLIKE on the held-out days"),
        "universe": len(syms), "covered": len(rows), "visited_this_pass": len(visited),
        "measured": n_meas, "garch_beats_ewma": n_g, "ewma_holds": n_meas - n_g,
        "garch_win_share": (round(n_g / n_meas, 4) if n_meas else None),
        "consumer": ("none with capital authority: an input arm must earn it two-sided "
                     "(GROWTH_GOVERNANCE); this artifact is the measured baseline it starts from"),
        "symbols": rows,
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    if visited:
        cursor.parent.mkdir(parents=True, exist_ok=True)
        cursor.write_text(json.dumps({"last": visited[-1], "at": _now()}), encoding="utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s)
    print(f"GARCH VOL  {doc['at']}  status={doc['status']}  covered={doc['covered']}/"
          f"{doc['universe']}  measured={doc['measured']}  garch_beats_ewma="
          f"{doc['garch_beats_ewma']}  -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
