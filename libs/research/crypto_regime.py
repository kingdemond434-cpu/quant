"""DOMINATED (2026-08-23): the MT5 desk has its own regime module,
desks/mt5/mt5desk/macro_regime.py, built independently during the migration. Native-crypto
machinery stays in the repo per standing instruction, but is retired from any live schedule.

Crypto regime detection + per-regime sleeve performance.

Many crypto edges only work in specific environments (funding carry shines in funding-rich,
leveraged markets; trend in directional regimes; everything correlates in a crash). This labels each
day by three orthogonal regime axes -- trend (bull/bear), volatility (high/low), funding
(rich/poor) -- from lagged BTC/aggregate signals (no look-ahead), and measures each sleeve's Sharpe
within each regime so the portfolio can lean on edges only where they actually pay.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from libs.validation.dsr import sharpe_ratio

_PPY = 365.0


def regime_labels(close: pd.DataFrame, funding: pd.DataFrame, *,
                  btc: str = "BTCUSDT") -> pd.DataFrame:
    """Per-day regime labels (lagged): trend (bull/bear), vol (high/low), funding (rich/poor)."""
    ref = close[btc] if btc in close.columns else close.mean(axis=1)
    ret = ref.pct_change(fill_method=None)
    trend = np.sign(ref / ref.shift(50) - 1.0).shift(1)
    rv = ret.rolling(30).std().shift(1)
    agg_funding = funding.mean(axis=1).rolling(7).mean().shift(1)
    out = pd.DataFrame(index=close.index)
    out["trend"] = np.where(trend > 0, "bull", "bear")
    out["vol"] = np.where(rv > rv.rolling(180, min_periods=60).median(), "high_vol", "low_vol")
    out["funding"] = np.where(agg_funding > agg_funding.rolling(180, min_periods=60).median(),
                              "funding_rich", "funding_poor")
    return out


def _sh(r: np.ndarray) -> float:
    a = r[r != 0.0]
    return round(float(sharpe_ratio(a) * np.sqrt(_PPY)), 2) if len(a) > 5 else 0.0


def regime_performance(
    sleeves: dict[str, np.ndarray], labels: pd.DataFrame, port: np.ndarray,
) -> dict[str, dict[str, float]]:
    """Sharpe of each sleeve + the portfolio within each regime bucket (diagnostic, in-sample)."""
    series = {**sleeves, "portfolio": port}
    out: dict[str, dict[str, float]] = {}
    for axis in labels.columns:
        for bucket in sorted(labels[axis].dropna().unique()):
            mask = (labels[axis] == bucket).to_numpy()
            key = f"{axis}:{bucket}"
            out[key] = {name: _sh(r[mask]) for name, r in series.items()}
            out[key]["_days"] = int(mask.sum())
    return out
