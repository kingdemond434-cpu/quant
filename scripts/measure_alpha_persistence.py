#!/usr/bin/env python3
"""DOES ALPHA ITSELF HAVE A TIME-SERIES STRUCTURE? -- testing the one transcript claim that,
if true, changes capital allocation rather than adding another signal.

THE CLAIM (Gebhardt, 10 Dynamics, 2026-08-01 transcript batch): "What we see in the model quite
clearly is that the alpha has a time series structure to it. If you look at energy you'll go
through a cyclical period where you'll have months of very high alpha, then the alpha declines,
then you might have a couple of months of even negative alpha, and then it'll go back up. You see
this across all the different sectors."

WHY THIS ONE AND NOT THE OTHERS. Every other mechanism in that batch is a signal -- it competes
for one of MAX_FORWARD_SLOTS=12 and, if it wins, adds one sleeve. This claim is about the
ALLOCATOR. If a strategy's alpha is autocorrelated month to month, then "how much capital does
this sleeve get next month" has a predictor, and that applies to every sleeve the desk will ever
run, including ones that do not exist yet. It is the only claim in the batch whose payoff is not
capped at one sleeve.

WHAT A NAIVE VERSION OF THIS WOULD GET WRONG, and it is the whole reason for the null below.
Sample autocorrelation of a mean-zero series is NEGATIVELY BIASED by approximately -1/(T-1)
(Kendall). On 24 monthly observations that is -0.043 before any real structure exists. A measured
lag-1 autocorrelation of +0.05 therefore looks like "weak persistence" against a zero null and is
actually ~2x the bias-corrected value -- while a measured -0.04 looks like mean reversion and is
exactly nothing. Worse, the months are computed from OVERLAPPING strategies on correlated assets,
so the cross-sectional pooling is not n independent draws either.

So the null here is not zero. It is a STATIONARY BLOCK BOOTSTRAP of the same panel with the
within-series time order destroyed and the cross-sectional dependence preserved. That answers the
only question worth asking: is the persistence larger than what this exact panel produces by
construction when there is no persistence at all? This is the desk's own lesson L0020 -- know the
estimator's floor before reading its output as a finding -- applied to a different estimator.

    python scripts/measure_alpha_persistence.py [--bars data/lake] [--months 1] [--boot 400]

REPORTS, and every one of these is a usable answer:
  PERSISTENT   alpha momentum is real here -> allocate toward what has been working
  MEAN-REVERT  alpha reverts -> allocate AWAY from what has been working
  NO STRUCTURE the claim does not hold on this desk's data -> stop considering alpha-momentum
               allocation schemes, and that is a result, not a failure
  UNDERPOWERED not enough months to distinguish any of the above -> says so instead of guessing
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np  # noqa: E402

from libs.research import regime_trend  # noqa: E402
from libs.research import transcript_candidates as tc  # noqa: E402

_OUT = _ROOT / "reports/alpha_persistence.json"

#: Below this many per-series alpha observations the autocorrelation estimate is dominated by its
#: own bias and the honest answer is UNDERPOWERED. Not a threshold to tune -- at T=12 the bias is
#: -0.09, which is the size of the effect being hunted.
_MIN_PERIODS = 18
_MAX_LAG = 3


def _alpha_series(returns: np.ndarray, period: int) -> np.ndarray:
    """Mean return per non-overlapping block -- the per-period 'alpha' whose structure is at test.

    NON-OVERLAPPING is load-bearing. Rolling windows share observations, which manufactures
    autocorrelation out of nothing: adjacent 20-day rolling means share 19 of 20 points and are
    ~0.95 correlated whatever the underlying series does. Measuring persistence on overlapping
    windows would find persistence in pure noise, every time.
    """
    n = len(returns) // period
    if n < 2:
        return np.array([])
    trimmed = returns[len(returns) - n * period:]
    return trimmed.reshape(n, period).mean(axis=1)


def _lag_autocorr(x: np.ndarray, lag: int) -> float:
    if len(x) <= lag + 1:
        return float("nan")
    a, b = x[:-lag], x[lag:]
    a = a - a.mean()
    b = b - b.mean()
    denom = float(np.sqrt((a * a).sum() * (b * b).sum()))
    return float((a * b).sum() / denom) if denom > 0 else float("nan")


def _panel_autocorr(panel: np.ndarray, lag: int) -> float:
    """Mean lag-`lag` autocorrelation across the panel's columns, ignoring degenerate ones."""
    vals = [_lag_autocorr(panel[:, j], lag) for j in range(panel.shape[1])]
    vals = [v for v in vals if np.isfinite(v)]
    return float(np.mean(vals)) if vals else float("nan")


def _shuffle_null(panel: np.ndarray, lag: int, n_boot: int,
                  rng: np.random.Generator) -> np.ndarray:
    """The null distribution: same panel, time order destroyed, cross-section preserved.

    Every column is permuted by the SAME index vector on each draw. That is deliberate: permuting
    columns independently would also destroy the contemporaneous correlation between sleeves, and
    the null would then be 'no persistence AND no cross-sectional dependence' -- a strictly easier
    null to beat, which would inflate significance for a reason that has nothing to do with the
    claim under test.
    """
    out = np.empty(n_boot)
    idx = np.arange(panel.shape[0])
    for b in range(n_boot):
        perm = rng.permutation(idx)
        out[b] = _panel_autocorr(panel[perm, :], lag)
    return out


def _verdict(observed: float, null: np.ndarray) -> tuple[str, float]:
    finite = null[np.isfinite(null)]
    if not np.isfinite(observed) or len(finite) < 20:
        return "UNDERPOWERED", float("nan")
    # Two-sided: mean reversion is as much a finding as persistence, and pre-committing to only
    # the persistence tail would make a real negative result unreportable.
    p_hi = float((finite >= observed).mean())
    p_lo = float((finite <= observed).mean())
    p = 2.0 * min(p_hi, p_lo)
    if p > 0.05:
        return "NO STRUCTURE", p
    return ("PERSISTENT" if observed > float(np.mean(finite)) else "MEAN-REVERT"), p


def build_panel(closes: dict[str, np.ndarray], period: int) -> tuple[np.ndarray, list[str]]:
    """One alpha column per (candidate, symbol), truncated to a common length.

    The cohort deliberately mixes the refuted textbook mechanisms with the new occupancy ones. The
    question is not whether any of them has alpha -- the 2026-08-01 campaign already answered that
    (0 survivors, max OOS Sharpe 0.100). It is whether whatever return structure they DO have
    persists period to period, and a mechanism with no edge still has a return series whose
    structure can be measured.
    """
    fns: dict[str, Any] = {
        "time_in_direction": regime_trend.time_in_direction,
        "occupancy_divergence": regime_trend.occupancy_divergence,
        "asymmetric_vol_trend": regime_trend._asymmetric_vol_trend,
        "zscore_reversion": tc.zscore_reversion,
        "bollinger_reversion": tc.bollinger_reversion,
        "absolute_momentum": tc.absolute_momentum,
        "donchian_breakout": None,   # needs OHLC; filled per-symbol only when highs/lows exist
    }
    cols: list[np.ndarray] = []
    names: list[str] = []
    for sym, close in sorted(closes.items()):
        for cname, fn in fns.items():
            if fn is None:
                continue
            pos = fn(close)
            rets = tc.positions_to_returns(pos, close)
            a = _alpha_series(np.asarray(rets, dtype="float64"), period)
            if len(a) >= _MIN_PERIODS and float(np.std(a)) > 0:
                cols.append(a)
                names.append(f"{cname}:{sym}")
    if not cols:
        return np.empty((0, 0)), []
    t = min(len(c) for c in cols)
    return np.column_stack([c[-t:] for c in cols]), names


def analyse(panel: np.ndarray, names: list[str], *, n_boot: int,
            seed: int = 20260801) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    t = panel.shape[0]
    rows = []
    for lag in range(1, _MAX_LAG + 1):
        obs = _panel_autocorr(panel, lag)
        null = _shuffle_null(panel, lag, n_boot, rng)
        verdict, p = _verdict(obs, null)
        rows.append({
            "lag": lag, "observed": round(obs, 4) if np.isfinite(obs) else None,
            "null_mean": round(float(np.nanmean(null)), 4),
            "null_sd": round(float(np.nanstd(null)), 4),
            "excess_over_null": (round(obs - float(np.nanmean(null)), 4)
                                 if np.isfinite(obs) else None),
            "p_two_sided": round(p, 4) if np.isfinite(p) else None,
            "verdict": verdict if t >= _MIN_PERIODS else "UNDERPOWERED",
        })
    return {
        "n_periods": int(t), "n_series": int(panel.shape[1]),
        "min_periods_required": _MIN_PERIODS,
        "kendall_bias": round(-1.0 / max(t - 1, 1), 4),
        "series": names[:40], "lags": rows,
        "reading": ("The null is NOT zero. Sample autocorrelation is negatively biased by about "
                    "-1/(T-1), so 'observed' must be compared against 'null_mean' and never "
                    "against 0. excess_over_null is the only column that means anything. A NO "
                    "STRUCTURE verdict is a real result: it retires alpha-momentum allocation "
                    "for this desk rather than leaving it as an untested intuition."),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--closes", default="", help="JSON file: {symbol: [close, ...]}")
    ap.add_argument("--period", type=int, default=21, help="bars per alpha observation (~1 month)")
    ap.add_argument("--boot", type=int, default=400)
    a = ap.parse_args()

    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _OUT.parent.mkdir(parents=True, exist_ok=True)

    if not a.closes or not Path(a.closes).exists():
        # BLOCKED, never a fabricated verdict. This measures a claim about real return series; run
        # it on synthetic data and the answer is a property of the generator, not of the market.
        _OUT.write_text(json.dumps({
            "generated": stamp, "status": "BLOCKED",
            "blocker": "no close-price panel supplied (--closes)",
            "human_step": "point --closes at a {symbol: [close,...]} JSON built from the lake or "
                          "from free daily OHLCV; this refuses to run on synthetic data because "
                          "the answer would describe the generator, not the market",
        }, indent=2), "utf-8")
        print("BLOCKED: no --closes panel. This will not fabricate a verdict from synthetic data.")
        return 1

    raw = json.loads(Path(a.closes).read_text("utf-8"))
    closes = {k: np.asarray(v, dtype="float64") for k, v in raw.items()
              if isinstance(v, list) and len(v) > 300}
    panel, names = build_panel(closes, a.period)
    if panel.size == 0 or panel.shape[0] < 4:
        _OUT.write_text(json.dumps({
            "generated": stamp, "status": "BLOCKED",
            "blocker": f"only {panel.shape[0] if panel.size else 0} alpha periods available; "
                       f"need >= {_MIN_PERIODS} for the estimate to exceed its own bias",
            "n_symbols": len(closes),
        }, indent=2), "utf-8")
        print(f"BLOCKED: {panel.shape[0] if panel.size else 0} periods, need {_MIN_PERIODS}.")
        return 1

    rep = analyse(panel, names, n_boot=a.boot)
    rep.update({"generated": stamp, "status": "COMPLETE", "period_bars": a.period})
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")

    print(f"alpha persistence | {rep['n_series']} series x {rep['n_periods']} periods "
          f"(Kendall bias {rep['kendall_bias']:+.3f})")
    print(f"{'lag':>4} {'observed':>9} {'null':>8} {'excess':>8} {'p':>7}  verdict")
    for r in rep["lags"]:
        obs = r["observed"]
        print(f"{r['lag']:>4} {obs if obs is None else f'{obs:>9.4f}'} "
              f"{r['null_mean']:>8.4f} {r['excess_over_null']:>8.4f} "
              f"{r['p_two_sided']:>7.4f}  {r['verdict']}")
    print(f"wrote {_OUT.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
