"""Crypto portfolio forward SHADOW -- the 90-day out-of-sample validation run (zero capital).

Freezes the deployable crypto book (funding carry + basis carry + taker flow + price momentum +
trend, combined with the robust flat trailing-Sharpe allocator -- NO re-selection, so the forward
track is honest) and tracks LIVE out-of-sample performance vs backtest from a fixed shadow-start
date. This is the only legitimate way to certify the edge that the in-sample gauntlet correctly
withholds. Decision rule is pre-committed (docs/KILL_THESIS.md): accumulate 90d, then promote / kill
/ hold -- never re-tune to pass. Runs daily on the refreshed lake; needs no exchange keys.

    python scripts/run_crypto_shadow.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from libs.data.crypto_source import list_liquid_perps
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.data.universe import RESEARCH_TOP_N
from libs.research.crossasset import trend_basket_returns, xsec_momentum_returns
from libs.research.crypto_sleeves import basis_carry_returns, taker_flow_returns
from libs.research.crypto_xsec import adv_tier_cost, xsec_funding_returns
from libs.research.event_density import forward_verdict
from libs.validation.dsr import sharpe_ratio

_CRYPTO = Path("data/lake/bronze/crypto")
_STATE = Path("data/crypto_shadow_state.json")
_WEB = Path("web/crypto_shadow.json")
_PPY = 365.0
# REWORKED book (ONE principled change, not a search): DROP funding_carry. Rationale is economic
# + statistical, not fitting -- (1) the DEPLOYED book is already delta-neutral funding carry, so a
# second sleeve must not double up on the same funding factor; (2) funding_carry also had the
# clearest negative marginal contribution (incr -0.02). Keeping momentum/trend/basis/taker preserves
# breadth. The forward shadow (90d, out-of-sample) is the honest judge -- we do NOT re-tune to pass.
_DROP = ("funding_carry", "funding_momentum")     # funding overlap w/ deployed carry + top dragger
_FROZEN = "REWORKED: full book minus funding_carry (decorrelate from the deployed funding carry)"


def _panels() -> tuple[pd.DataFrame, ...]:
    lake = ParquetLake("data/lake")
    closes, fundings, bases, takers, adv = {}, {}, {}, {}, {}
    for s in list_liquid_perps(top_n=RESEARCH_TOP_N):
        if not (_CRYPTO / s / Timeframe.D1.value).exists():
            continue
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
        df = lake.read_bars(Layer.BRONZE, s, Timeframe.D1).set_index("timestamp")
        if "funding" not in df.columns or len(df) < 250:
            continue
        closes[s] = df["close"]
        fundings[s] = df["funding"]
        adv[s] = float((df["close"] * df["volume"]).tail(180).mean())
        if "basis" in df.columns:
            bases[s] = df["basis"]
        if "taker_buy_frac" in df.columns:
            takers[s] = df["taker_buy_frac"]
    close = pd.DataFrame(closes).sort_index()
    f = pd.DataFrame(fundings).reindex(close.index)
    basis = pd.DataFrame(bases).reindex(close.index) if bases else pd.DataFrame()
    taker = pd.DataFrame(takers).reindex(close.index) if takers else pd.DataFrame()
    return close, f, basis, taker, adv


def _combine(df: pd.DataFrame) -> np.ndarray:
    """Flat trailing-Sharpe-tilted risk parity (frozen, robust, lagged -> no look-ahead)."""
    masked = df.replace(0.0, np.nan)
    vol = masked.rolling(252, min_periods=60).std().shift(1)
    mean = masked.rolling(252, min_periods=60).mean().shift(1)
    inv = (1.0 / vol) * (mean / vol).clip(lower=0.0)
    w = inv.div(inv.sum(axis=1), axis=0).fillna(0.0)
    return (w.to_numpy() * df.to_numpy()).sum(axis=1)


def _ann(r: np.ndarray) -> float:
    a = r[r != 0.0]
    return round(float(sharpe_ratio(a) * np.sqrt(_PPY)), 2) if len(a) > 5 else 0.0


def _verdict(days: int, fwd: float, bt: float) -> str:
    """EVIDENCE, NOT CALENDAR (L1.48) -- shared gate, so five runners cannot drift apart."""
    return forward_verdict(days, fwd, bt, periods_per_year=_PPY)


def main() -> None:
    close, funding, basis, taker, adv = _panels()
    if close.shape[1] < 12:
        raise SystemExit("need a liquid perp panel; run ingest_crypto + ingest_crypto_enriched")
    cost = {s: adv_tier_cost(a) for s, a in adv.items()}
    sleeves = {
        "funding_carry": xsec_funding_returns(close, funding, adv, lookback=7, q=0.2, band=0.02),
        "xsec_price_mom": xsec_momentum_returns(close, cost, lookback=20, q=0.3, band=0.05),
        "ts_trend": trend_basket_returns(close, cost, lookback=30, band=0.05),
    }
    if not basis.empty and basis.shape[1] >= 12:
        sleeves["basis_carry"] = basis_carry_returns(close[basis.columns], funding[basis.columns],
                                                     basis, adv, lookback=3, q=0.2, band=0.02)
    if not taker.empty and taker.shape[1] >= 12:
        sleeves["taker_flow"] = taker_flow_returns(close[taker.columns], funding[taker.columns],
                                                   taker, adv, lookback=5, q=0.2, band=0.02)
    full = pd.DataFrame({k: v for k, v in sleeves.items() if np.isfinite(v).all()},
                        index=close.index)
    # REWORK: drop the funding overlap with the deployed carry; keep the rest for breadth
    core_cols = [c for c in full.columns if c not in _DROP] or ["xsec_price_mom"]
    df = full[core_cols]
    port = _combine(df)
    dates = close.index

    state = json.loads(_STATE.read_text("utf-8")) if _STATE.exists() else {}
    comp = list(df.columns)
    if "shadow_start" not in state or state.get("composition") != comp:
        state["shadow_start"] = dates[-1].isoformat()    # reworked book -> fresh clock
        state["composition"] = comp
        _STATE.parent.mkdir(parents=True, exist_ok=True)
        _STATE.write_text(json.dumps(state), "utf-8")
    shadow_start = pd.Timestamp(state["shadow_start"])
    is_fwd = dates >= shadow_start
    bt_sharpe, fwd_sharpe = _ann(port[~is_fwd]), _ann(port[is_fwd])
    fwd = port[is_fwd]
    fwd_days = int(np.sum(fwd != 0.0))
    fwd_cum = float(np.prod(1.0 + fwd) - 1.0) if len(fwd) else 0.0

    equity = np.cumprod(1.0 + port)
    n = len(equity)
    step = max(1, n // 300)
    curve = [{"t": dates[i].date().isoformat(), "v": round(float(equity[i]), 4),
              "fwd": bool(is_fwd[i])} for i in range(0, n, step)]
    payload = {
        "strategy": _FROZEN, "shadow_start": state["shadow_start"], "perps": close.shape[1],
        "sleeves": list(df.columns), "backtest_ann_sharpe": bt_sharpe,
        "forward_ann_sharpe": fwd_sharpe, "forward_days": fwd_days,
        "forward_cum_return": round(fwd_cum, 4),
        "verdict": _verdict(fwd_days, fwd_sharpe, bt_sharpe),
        "updated": datetime.now(tz=UTC).isoformat(), "equity": curve,
    }
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps(payload, indent=2), "utf-8")
    print(f"crypto shadow: start={state['shadow_start'][:10]} fwd_days={fwd_days} "
          f"bt_sharpe={bt_sharpe} fwd_sharpe={fwd_sharpe}")
    print(f"verdict: {payload['verdict']}")


if __name__ == "__main__":
    main()
