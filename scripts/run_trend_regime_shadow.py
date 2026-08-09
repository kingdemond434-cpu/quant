"""Regime-gated TREND challenger -- same majors TS-momentum, FLAT in weak-trend regimes.

PRE-REGISTERED CHALLENGER (2026-07-09) to the frozen trend_30d incumbent, per champion/challenger:
identical book (top-15 majors, 30d lookback, banded) but exposure is ON only when the market is in
a TRENDING regime, defined a priori on economics (alts trend when BTC trends): lagged |BTC 30d
return| >= 10%. Constants fixed BEFORE inspecting the incumbent's losing days -- this is a regime
hypothesis, not a fit to last week. HONESTY: (1) the desk's EV gate scored this class LOW
(p_survive ~7%; regime-filtered trend is a classic overfit trap) -- built on explicit principal
instruction, verdict logged in the decision ledger; (2) the incumbent stays FROZEN and unmodified;
both clocks run in parallel and the 90d evidence picks the winner. Zero capital either way.

    python scripts/run_trend_regime_shadow.py
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
from libs.research.crossasset import trend_basket_returns
from libs.research.crypto_xsec import adv_tier_cost
from libs.research.event_density import forward_verdict
from libs.validation.dsr import sharpe_ratio

_CRYPTO = Path("data/lake/bronze/crypto")
_STATE = Path("data/trend_regime_shadow_state.json")
_WEB = Path("web/trend_regime_shadow.json")
_PPY = 365.0
# FROZEN pre-registered spec: incumbent's book + a lagged BTC trend-strength gate. NOT tunable.
_TOP, _LOOKBACK, _BAND = 15, 30, 0.10
_GATE_LOOKBACK, _GATE_MIN_ABS = 30, 0.10          # |BTC 30d return| >= 10% -> trending regime
_FROZEN = ("regime-gated TS-momentum: top-15 majors 30d, FLAT unless lagged |BTC 30d| >= 10% "
           "(pre-registered challenger to trend_30d; incumbent untouched)")


def _majors(top: int) -> tuple[pd.DataFrame, dict[str, float]]:
    closes, adv = {}, {}
    for s in list_liquid_perps(top_n=top * 3):
        if not (_CRYPTO / s / Timeframe.D1.value).exists():
            continue
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
        lake = ParquetLake("data/lake")
        df = lake.read_bars(Layer.BRONZE, s, Timeframe.D1).set_index("timestamp")
        if len(df) < 300:
            continue
        closes[s] = df["close"]
        adv[s] = float((df["close"] * df["volume"]).tail(180).mean())
        if len(closes) >= top:
            break
    return pd.DataFrame(closes).sort_index(), adv


def _ann(r: np.ndarray) -> float:
    a = r[r != 0.0]
    return round(float(sharpe_ratio(a) * np.sqrt(_PPY)), 2) if len(a) > 5 else 0.0


def _verdict(days: int, fwd: float, bt: float) -> str:
    """EVIDENCE, NOT CALENDAR (L1.48) -- shared gate, so five runners cannot drift apart."""
    return forward_verdict(
        days, fwd, bt, periods_per_year=_PPY,
        accruing_tail=" (challenger) -- zero capital until it holds",
        kill_action="kill challenger (regime gate did not help)",
        on_track_action="compare vs incumbent at review; better book wins (governance gate)")


def main() -> None:
    close, adv = _majors(_TOP)
    if close.shape[1] < 6 or "BTCUSDT" not in close.columns:
        raise SystemExit(f"need a majors panel incl. BTCUSDT; got {close.shape[1]}")
    cost = {s: adv_tier_cost(a) for s, a in adv.items()}
    raw = trend_basket_returns(close, cost, lookback=_LOOKBACK, band=_BAND)
    # regime gate: LAGGED BTC 30d absolute move (shift(1) -> no look-ahead); flat when weak-trend.
    btc = close["BTCUSDT"]
    gate = ((btc / btc.shift(_GATE_LOOKBACK) - 1.0).abs() >= _GATE_MIN_ABS).shift(1)
    r = np.where(gate.fillna(False).to_numpy(), raw, 0.0)
    in_market_pct = round(100.0 * float(gate.fillna(False).mean()), 1)
    dates = close.index

    state = json.loads(_STATE.read_text("utf-8")) if _STATE.exists() else {}
    if "shadow_start" not in state or state.get("composition") != _FROZEN:
        state = {"shadow_start": dates[-1].isoformat(), "composition": _FROZEN}
        _STATE.parent.mkdir(parents=True, exist_ok=True)
        _STATE.write_text(json.dumps(state), "utf-8")
    shadow_start = pd.Timestamp(state["shadow_start"])
    is_fwd = dates >= shadow_start
    bt_sharpe, fwd_sharpe = _ann(r[~is_fwd]), _ann(r[is_fwd])
    fwd = r[is_fwd]
    # forward day-count = CALENDAR forward days (a gated-flat day is still evidence)
    fwd_days = int(np.sum(is_fwd)) - 1 if np.sum(is_fwd) else 0
    fwd_cum = float(np.prod(1.0 + fwd) - 1.0) if len(fwd) else 0.0

    equity = np.cumprod(1.0 + r)
    n = len(equity)
    step = max(1, n // 300)
    curve = [{"t": dates[i].date().isoformat(), "v": round(float(equity[i]), 4),
              "fwd": bool(is_fwd[i])} for i in range(0, n, step)]
    payload = {
        "strategy": _FROZEN, "shadow_start": state["shadow_start"], "majors": close.shape[1],
        "backtest_ann_sharpe": bt_sharpe, "forward_ann_sharpe": fwd_sharpe,
        "forward_days": max(fwd_days, 0), "forward_cum_return": round(fwd_cum, 4),
        "in_market_pct": in_market_pct, "directional": True, "challenger_to": "trend_30d",
        "ev_gate_verdict": "REJECT p~7% (built on principal instruction; ledger 2026-07-09)",
        "verdict": _verdict(max(fwd_days, 0), fwd_sharpe, bt_sharpe),
        "updated": datetime.now(tz=UTC).isoformat(), "equity": curve,
    }
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps(payload, indent=2), "utf-8")
    print(f"trend-regime challenger: fwd={payload['forward_days']}d bt_sharpe={bt_sharpe} "
          f"in-market={in_market_pct}% (incumbent bt: see trend_shadow.json)")


if __name__ == "__main__":
    main()
