"""Forward SHADOW harness for the cross-sectional funding candidate (zero capital).

Runs the FROZEN best variant (lookback=7, q=0.2, band=0.02) on the refreshed liquid lake, splits the
return stream at the shadow-start date, and tracks LIVE out-of-sample performance vs the backtest --
the only honest way to resolve a candidate that fails Reality Check on backtest. Also snapshots open
interest forward (history is 30d-capped, so we accumulate it). No capital is allocated; promotion to
tiny live requires the pre-committed rule in docs/KILL_THESIS.md + human approval.

Schedule daily AFTER a liquid ingest. Writes web/shadow.json for the dashboard.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from libs.data.crypto_source import fetch_open_interest, list_liquid_perps
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.research.crypto_xsec import xsec_funding_returns
from libs.validation.dsr import sharpe_ratio

_CRYPTO = Path("data/lake/bronze/crypto")
_STATE = Path("data/shadow_state.json")
_WEB = Path("web/shadow.json")
_OI_LOG = Path("reports/shadow/oi_log.json")
_PPY = 365.0
_FROZEN = {"lookback": 7, "q": 0.2, "band": 0.02}   # pre-registered; never re-optimized


def _panels(universe: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    lake = ParquetLake("data/lake")
    closes, fundings, adv = {}, {}, {}
    for s in universe:
        if not (_CRYPTO / s / Timeframe.D1.value).exists():
            continue
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
        df = lake.read_bars(Layer.BRONZE, s, Timeframe.D1).set_index("timestamp")
        if "funding" not in df.columns or len(df) < 250:
            continue
        closes[s] = df["close"]
        fundings[s] = df["funding"]
        adv[s] = float((df["close"] * df["volume"]).tail(180).mean())
    close = pd.DataFrame(closes).sort_index()
    return close, pd.DataFrame(fundings).reindex(close.index), adv


def _ann_sharpe(r: np.ndarray) -> float:
    a = r[r != 0.0]
    return float(sharpe_ratio(a) * np.sqrt(_PPY)) if len(a) > 5 else 0.0


def _snapshot_oi(universe: list[str]) -> None:
    snap = {"ts": datetime.now(tz=UTC).isoformat(), "oi": {}}
    for s in universe[:60]:                      # cap calls; forward-accumulating dataset
        try:
            snap["oi"][s] = fetch_open_interest(s)
        except Exception:
            continue
    _OI_LOG.parent.mkdir(parents=True, exist_ok=True)
    log = json.loads(_OI_LOG.read_text("utf-8")) if _OI_LOG.exists() else []
    log.append(snap)
    _OI_LOG.write_text(json.dumps(log[-400:]), "utf-8")


def _verdict(fwd_days: int, fwd_sharpe: float, bt_sharpe: float) -> str:
    if fwd_days < 90:
        return f"ACCUMULATING ({fwd_days}/90+ days of forward evidence)"
    if fwd_sharpe < 0:
        return "FAILING FORWARD -> kill candidate"
    if fwd_sharpe >= 0.5 and fwd_sharpe >= 0.5 * bt_sharpe:
        return "ON TRACK -> eligible for TINY live on human approval (governance gate)"
    return "WEAK forward -> continue shadow, do not deploy"


def main() -> None:
    universe = list_liquid_perps(top_n=100)
    close, funding, adv = _panels(universe)
    if close.shape[1] < 12:
        raise SystemExit("need a liquid panel; run: ingest_crypto.py --universe liquid")

    rets = xsec_funding_returns(close, funding, adv, **_FROZEN)
    dates = close.index

    state = json.loads(_STATE.read_text("utf-8")) if _STATE.exists() else {}
    if "shadow_start" not in state:
        state["shadow_start"] = dates[-1].isoformat()    # forward window begins now
        _STATE.parent.mkdir(parents=True, exist_ok=True)
        _STATE.write_text(json.dumps(state), "utf-8")
    shadow_start = pd.Timestamp(state["shadow_start"])

    is_fwd = dates >= shadow_start
    bt_sharpe = _ann_sharpe(rets[~is_fwd])
    fwd = rets[is_fwd]
    fwd_sharpe = _ann_sharpe(fwd)
    fwd_days = int(np.sum(fwd != 0.0))
    fwd_cum = float(np.prod(1.0 + fwd) - 1.0) if len(fwd) else 0.0

    _snapshot_oi(universe)

    equity = np.cumprod(1.0 + rets)
    n = len(equity)
    step = max(1, n // 300)
    curve = [{"t": dates[i].date().isoformat(), "v": round(float(equity[i]), 4),
              "fwd": bool(is_fwd[i])} for i in range(0, n, step)]
    payload = {
        "strategy": "cross-sectional funding (frozen lb7/q20/b02)",
        "shadow_start": state["shadow_start"], "perps": close.shape[1],
        "backtest_ann_sharpe": round(bt_sharpe, 2),
        "forward_ann_sharpe": round(fwd_sharpe, 2),
        "forward_days": fwd_days, "forward_cum_return": round(fwd_cum, 4),
        "verdict": _verdict(fwd_days, fwd_sharpe, bt_sharpe),
        "updated": datetime.now(tz=UTC).isoformat(), "equity": curve,
    }
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps(payload, indent=2), "utf-8")
    print(f"shadow: start={state['shadow_start'][:10]} fwd_days={fwd_days} "
          f"bt_sharpe={bt_sharpe:.2f} fwd_sharpe={fwd_sharpe:.2f}")
    print(f"verdict: {payload['verdict']}")


if __name__ == "__main__":
    main()
