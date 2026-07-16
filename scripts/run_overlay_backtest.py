"""Validate the variance-reduction overlays on the REAL perp book -> web/overlays.json.

Rebuilds the live perp book, then applies vol-targeting (constant 35% risk) and a residual BTC-beta
hedge, reporting Sharpe / CAGR / vol / max-DD before vs after. These are pure Sharpe-raisers (no
edge assumed) -- the honest test is whether they lift risk-adjusted return and shrink DD on real
history. Runs on the flywheel.

    python scripts/run_overlay_backtest.py
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
from libs.research.crossasset import xsec_momentum_returns
from libs.research.crypto_sleeves import basis_carry_returns, taker_flow_returns
from libs.research.crypto_xsec import adv_tier_cost, xsec_funding_returns
from libs.risk.overlays import beta_neutralize, vol_target_scale
from libs.validation.dsr import sharpe_ratio

_CRYPTO = Path("data/lake/bronze/crypto")
_OUT = Path("web/overlays.json")
_PPY = 365.0


def _stats(r: np.ndarray) -> dict[str, float]:
    a = r[~np.isnan(r)]
    a = a[a != 0.0]
    if len(a) < 30:
        return {"sharpe": 0.0, "cagr": 0.0, "vol": 0.0, "max_dd": 0.0}
    cum = np.cumprod(1.0 + a)
    dd = float((cum / np.maximum.accumulate(cum) - 1.0).min())
    return {"sharpe": round(float(sharpe_ratio(a) * np.sqrt(_PPY)), 2),
            "cagr": round(float(cum[-1] ** (_PPY / len(a)) - 1.0), 3),
            "vol": round(float(np.std(a) * np.sqrt(_PPY)), 3), "max_dd": round(dd, 3)}


def main() -> None:
    lake = ParquetLake("data/lake")
    closes, fundings, bases, takers, adv = {}, {}, {}, {}, {}
    for s in list_liquid_perps(top_n=120):
        if not (_CRYPTO / s / Timeframe.D1.value).exists():
            continue
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
        df = lake.read_bars(Layer.BRONZE, s, Timeframe.D1).set_index("timestamp")
        if "funding" not in df.columns or len(df) < 250:
            continue
        closes[s], fundings[s] = df["close"], df["funding"]
        adv[s] = float((df["close"] * df["volume"]).tail(180).mean())
        if "basis" in df.columns:
            bases[s] = df["basis"]
        if "taker_buy_frac" in df.columns:
            takers[s] = df["taker_buy_frac"]
    close = pd.DataFrame(closes).sort_index()
    if close.shape[1] < 12:
        raise SystemExit("need a liquid perp panel; run ingest_crypto_enriched")
    funding = pd.DataFrame(fundings).reindex(close.index)
    basis = pd.DataFrame(bases).reindex(close.index) if bases else pd.DataFrame()
    taker = pd.DataFrame(takers).reindex(close.index) if takers else pd.DataFrame()
    cost = {s: adv_tier_cost(a) for s, a in adv.items()}

    sleeves = [xsec_funding_returns(close, funding, adv, lookback=7, q=0.2, band=0.02),
               xsec_momentum_returns(close, cost, lookback=20, q=0.3, band=0.05)]
    if not basis.empty and basis.shape[1] >= 12:
        sleeves.append(basis_carry_returns(close[basis.columns], funding[basis.columns], basis,
                                           adv, lookback=3, q=0.2, band=0.02))
    if not taker.empty and taker.shape[1] >= 12:
        sleeves.append(taker_flow_returns(close[taker.columns], funding[taker.columns], taker,
                                          adv, lookback=5, q=0.2, band=0.02))
    n = min(len(s) for s in sleeves)
    book = np.mean([s[-n:] for s in sleeves], axis=0)            # the live perp book
    btc = close["BTCUSDT"].pct_change().to_numpy()[-n:] if "BTCUSDT" in close else np.zeros(n)

    # vol-target to the book's OWN vol -> leverage-neutral SMOOTHING (avg exposure ~1), no lever-up
    book_vol = float(np.std(book[book != 0.0]) * np.sqrt(_PPY))
    vt, expo = vol_target_scale(book, target_vol=book_vol)
    bh, beta = beta_neutralize(book, btc)
    both, _ = vol_target_scale(bh, target_vol=book_vol)

    raw, s_vt, s_bh, s_both = _stats(book), _stats(vt), _stats(bh), _stats(both)
    out = {
        "updated": datetime.now(tz=UTC).isoformat(), "obs": int(n),
        "target_vol": round(book_vol, 3), "avg_exposure": round(float(np.nanmean(expo)), 2),
        "raw_book": raw, "vol_targeted": s_vt, "beta_hedged": s_bh, "both_overlays": s_both,
        "avg_abs_beta": round(float(np.nanmean(np.abs(beta))), 3),
        "sharpe_uplift_voltarget": round(s_vt["sharpe"] - raw["sharpe"], 2),
        "sharpe_uplift_both": round(s_both["sharpe"] - raw["sharpe"], 2),
        "dd_improvement_both": round(s_both["max_dd"] - raw["max_dd"], 3),
        "verdict": ("overlays LIFT Sharpe / cut DD" if s_both["sharpe"] >= raw["sharpe"]
                    and s_both["max_dd"] >= raw["max_dd"] else "overlays mixed -- see table"),
        "note": ("Pure variance reduction (no new edge). Vol-target holds risk constant -> "
                 "smoother compounding; beta-hedge removes residual BTC leakage. Lower sigma "
                 "raises Sharpe and cuts the leverage drag -> same half-Kelly compounds safer."),
    }
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    print(f"overlays ({n}d): raw Sharpe {raw['sharpe']} DD {raw['max_dd']} | vol-target "
          f"{s_vt['sharpe']} | beta-hedge {s_bh['sharpe']} | BOTH {s_both['sharpe']} "
          f"DD {s_both['max_dd']} (uplift {out['sharpe_uplift_both']:+})")


if __name__ == "__main__":
    main()
