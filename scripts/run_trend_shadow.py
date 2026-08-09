"""Forward SHADOW for the refined TREND book -- directional TS-momentum on majors, lookback 30d.

The 90-day OUT-OF-SAMPLE clock for the trend_30d spec that SURVIVED the in-sample gauntlet
(run_trend_gauntlet: net Sharpe ~1.40, PBO 0.079, RC p 0.005, 7y, 3/4 lookbacks passed). FROZEN --
no re-tuning to pass. Splits the daily return series at a fixed shadow_start and reports backtest vs
FORWARD Sharpe + a pre-committed verdict. Directional (real drawdown risk), decorrelated from the
delta-neutral carry -> the reason to want it. ZERO capital until it holds forward. Emits
web/trend_shadow.json + tracks the clock in data/trend_shadow_state.json.

    python scripts/run_trend_shadow.py
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
_STATE = Path("data/trend_shadow_state.json")
_WEB = Path("web/trend_shadow.json")
_PPY = 365.0
# FROZEN spec = the gauntlet survivor. ONE principled config, not a knob to re-tune.
_TOP, _LOOKBACK, _BAND = 15, 30, 0.10
_FROZEN = "directional TS-momentum on top-15 majors, 30d lookback, turnover-banded"


def _majors(top: int) -> tuple[pd.DataFrame, dict[str, float]]:
    closes, adv = {}, {}
    for s in list_liquid_perps(top_n=top * 3):
        if not (_CRYPTO / s / Timeframe.D1.value).exists():
            continue
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
        df = ParquetLake("data/lake").read_bars(Layer.BRONZE, s, Timeframe.D1)
        df = df.set_index("timestamp")
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
        accruing_tail=" -- zero capital until it holds",
        kill_action="kill (trend was a backtest mirage / bull-run artefact)",
        on_track_action="eligible for TINY paper->gated live on human approval (governance gate)")


def main() -> None:
    close, adv = _majors(_TOP)
    if close.shape[1] < 6:
        raise SystemExit(f"need a majors panel; got {close.shape[1]}")
    cost = {s: adv_tier_cost(a) for s, a in adv.items()}
    r = trend_basket_returns(close, cost, lookback=_LOOKBACK, band=_BAND)
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
    fwd_days = int(np.sum(fwd != 0.0))
    fwd_cum = float(np.prod(1.0 + fwd) - 1.0) if len(fwd) else 0.0

    equity = np.cumprod(1.0 + r)
    n = len(equity)
    step = max(1, n // 300)
    curve = [{"t": dates[i].date().isoformat(), "v": round(float(equity[i]), 4),
              "fwd": bool(is_fwd[i])} for i in range(0, n, step)]
    payload = {
        "strategy": _FROZEN, "shadow_start": state["shadow_start"], "majors": close.shape[1],
        "universe": list(close.columns), "backtest_ann_sharpe": bt_sharpe,
        "forward_ann_sharpe": fwd_sharpe, "forward_days": fwd_days,
        "forward_cum_return": round(fwd_cum, 4), "directional": True,
        "verdict": _verdict(fwd_days, fwd_sharpe, bt_sharpe),
        "note": ("passed in-sample gauntlet (Sharpe~1.40/PBO 0.079/RC 0.005); DIRECTIONAL so it "
                 "carries real drawdown risk and trend backtests flatter in bull-heavy history -- "
                 "the forward clock is the honest test."),
        "updated": datetime.now(tz=UTC).isoformat(), "equity": curve,
    }
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps(payload, indent=2), "utf-8")
    print(f"trend shadow: start={state['shadow_start'][:10]} fwd_days={fwd_days} "
          f"bt_sharpe={bt_sharpe} fwd_sharpe={fwd_sharpe}")
    print(f"verdict: {payload['verdict']}")


if __name__ == "__main__":
    main()
