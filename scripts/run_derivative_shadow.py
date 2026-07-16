"""Derivative-data shadow sleeves (Phase 5): OI Divergence + Long/Short Contrarian.

ECONOMIC HYPOTHESES (pre-registered, no peeking):
  * OI Divergence  -- price up + OI up = genuine trend participation (follow); price up + OI DOWN =
                      short-covering (weak, fade). Signal = sign(dPrice)*sign(dOI), cross-sectional.
  * L/S Contrarian -- crowded retail positioning mean-reverts. Signal = -zscore(long/short ratio),
                      cross-sectional (fade the crowd).

We have NO usable history for these (the derivative metrics only exist from when our own archiver
started), so we DO NOT fabricate a backtest. Instead we accumulate forward and report progress. The
moment >= MIN_DAYS distinct days exist, this computes real forward sleeve returns + Sharpe and the
discovery gauntlet (CPCV/DSR/PBO) takes over. Writes web/derivative_shadow.json.

    python scripts/run_derivative_shadow.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from libs.data.crypto_source import fetch_klines

_METRICS = Path("data/crypto_metrics.parquet")
_OUT = Path("web/derivative_shadow.json")
_MIN_DAYS = 40


def _sharpe(r: np.ndarray) -> float:
    sd = float(np.std(r))
    return round(float(np.mean(r)) / sd * (365 ** 0.5), 2) if sd else 0.0


def _forward_returns(df: pd.DataFrame) -> dict[str, float]:
    """Compute OI-divergence + L/S-contrarian forward sleeve Sharpes once enough days exist."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["ts"]).dt.date
    piv_oi = df.pivot_table(index="date", columns="symbol", values="open_interest")
    piv_ls = df.pivot_table(index="date", columns="symbol", values="ls_ratio")
    syms = list(piv_oi.columns)
    start_ms = int((pd.Timestamp(min(df["date"])) - pd.Timedelta(days=2)).timestamp() * 1000)
    px = {}
    for s in syms:
        try:
            k = fetch_klines(s, interval="1d", start_ms=start_ms)
            if not k.empty:
                px[s] = k.set_index(k["timestamp"].dt.date)["close"].astype(float)
        except Exception:
            continue
    prices = pd.DataFrame(px).reindex(piv_oi.index).ffill()
    pr_ret = prices.pct_change().shift(-1)                    # next-day return (no lookahead)
    d_price = prices.pct_change()
    d_oi = piv_oi.pct_change()
    oi_sig = np.sign(d_price) * np.sign(d_oi)                 # +1 confirm trend, -1 divergence
    ls_z = (piv_ls.sub(piv_ls.mean(axis=1), axis=0)).div(piv_ls.std(axis=1) + 1e-9, axis=0)
    ls_sig = -ls_z                                            # fade the crowd
    out = {}
    for name, sig in (("oi_divergence", oi_sig), ("ls_contrarian", ls_sig)):
        w = sig.sub(sig.mean(axis=1), axis=0)                 # market-neutral
        w = w.div(w.abs().sum(axis=1) + 1e-9, axis=0)
        r = (w * pr_ret).sum(axis=1).dropna().to_numpy()
        out[name] = _sharpe(r) if len(r) > 5 else 0.0
    return out


def main() -> None:
    now = datetime.now(tz=UTC)
    sleeves = ["oi_divergence", "ls_contrarian"]
    if not _METRICS.exists():
        days, quality = 0, "no archive yet"
        result: dict[str, object] = {}
    else:
        df = pd.read_parquet(_METRICS)
        days = int(pd.to_datetime(df["ts"]).dt.date.nunique())
        nsym = int(df["symbol"].nunique())
        nan_ls = float(df["ls_ratio"].isna().mean())
        quality = f"{nsym} symbols/day, L/S NaN {nan_ls:.0%}"
        result = _forward_returns(df) if days >= _MIN_DAYS else {}
    ready = days >= _MIN_DAYS
    eta = (now + timedelta(days=max(0, _MIN_DAYS - days))).date().isoformat()
    out = {
        "updated": now.isoformat(),
        "sleeves": sleeves,
        "days_accumulated": days,
        "min_days": _MIN_DAYS,
        "data_quality": quality,
        "validation_progress_pct": round(100 * min(1.0, days / _MIN_DAYS), 1),
        "expected_ready_date": eta,
        "status": "VALIDATING" if ready else "ACCUMULATING (no backtest fabricated)",
        "forward_sharpe": result,
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    print(f"derivative shadow: {days}/{_MIN_DAYS} days ({out['validation_progress_pct']}%), "
          f"ETA {eta}, status {out['status']}")


if __name__ == "__main__":
    main()
