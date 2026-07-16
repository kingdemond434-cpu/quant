"""NEW ALPHA FAMILY -- options volatility risk premium (Deribit DVOL vs realised vol).

ECONOMIC HYPOTHESIS: when implied vol (DVOL) is rich relative to realised vol, the market pays a
fear premium that tends to mean-revert -> mildly bullish forward (capitulation marks local bottoms).
This is an OPTIONS-derived signal, structurally orthogonal to every perp/funding/flow sleeve. Tested
on BTC + ETH (the only deep DVOL markets) at 12h, by TIME-SERIES IC (the right IC for a low-asset
signal) and the return gauntlet. HONESTY: only 2 assets = low breadth; this is a market-timing-style
overlay, not a broad cross-sectional alpha. ~120-day window = ~1 regime -> PRELIMINARY. Nothing
fabricated. Writes web/options_vrp_backtest.json.

    python scripts/run_options_vrp_backtest.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import campaign_pbo_rc, validate
from libs.data.crypto_source import fetch_klines
from libs.data.deribit import fetch_dvol
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_OUT = Path("web/options_vrp_backtest.json")
_PPY = 2 * 365.0                              # 12h bars per year (Deribit DVOL resolution)
_COST = 0.0004
_ASSETS = ["BTC", "ETH"]
_FAIL = ["vol regime shift", "premium compresses", "low breadth (2 assets)", "cost exceeds edge"]


def _series(cur: str) -> pd.DataFrame:
    """Align DVOL (implied vol) with realised vol + forward return on a 12h grid for one asset."""
    dv = fetch_dvol(cur, days=200)                        # 12h DVOL, 200d -> ~400 bars clears 250
    if dv.empty:
        return pd.DataFrame()
    start_ms = int((pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=200)).timestamp() * 1000)
    k = fetch_klines(f"{cur}USDT", interval="12h", start_ms=start_ms)
    if k.empty:
        return pd.DataFrame()
    px = k.set_index("timestamp")["close"].astype(float)
    ret = px.pct_change()
    rv = ret.rolling(14).std() * np.sqrt(_PPY)            # annualised realised vol
    dvi = dv.set_index("timestamp")["dvol"] / 100.0       # annualised implied vol (decimal)
    idx = px.index
    df = pd.DataFrame({"iv": dvi.reindex(idx).ffill(), "rv": rv.reindex(idx),
                       "fwd": ret.shift(-1).reindex(idx)}).dropna()
    df["vrp"] = df["iv"] - df["rv"]                        # the volatility risk premium
    return df


def main() -> None:
    panels = {c: _series(c) for c in _ASSETS}
    panels = {c: d for c, d in panels.items() if not d.empty and len(d) > 60}
    if not panels:
        raise SystemExit("no DVOL/price panel")

    ics, rets = [], []
    for d in panels.values():
        z = (d["vrp"] - d["vrp"].mean()) / (d["vrp"].std() + 1e-9)   # long when VRP rich
        ic = spearmanr(d["vrp"], d["fwd"]).correlation              # time-series IC vs fwd ret
        ics.append(float(ic) if ic == ic else 0.0)
        cost = _COST * z.diff().abs()
        rets.append((z * d["fwd"] - cost).dropna().to_numpy())

    n = min(len(r) for r in rets)
    asset_mat = np.column_stack([r[-n:] for r in rets])   # (n, n_assets) -- BTC + ETH legs
    book = asset_mat.mean(axis=1)                          # equal-weight VRP book
    ann = round(float(sharpe_ratio(book[book != 0.0]) * np.sqrt(_PPY)), 2) if n > 5 else 0.0
    mean_ic = round(float(np.mean(ics)), 4)
    sharpes = np.array([sharpe_ratio(asset_mat[:, i][asset_mat[:, i] != 0.0])
                        for i in range(asset_mat.shape[1])])
    pbo, rc = campaign_pbo_rc(asset_mat) if asset_mat.shape[1] >= 2 else (None, None)
    v = validate(book[book != 0.0], hypothesis=Hypothesis(
        family=Family.CARRY, subtype="options_vrp", symbol="CRYPTO", params={},
        mechanism=MechanismType.RISK_PREMIUM, edge_source="options_vrp", failure_modes=_FAIL),
        n_trials=asset_mat.shape[1], sharpe_estimates=sharpes, returns_matrix=asset_mat,
        pbo=pbo, rc=rc) if n >= 250 else None

    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "family": "options volatility risk premium (Deribit DVOL)", "source": "deribit",
        "assets": list(panels), "frequency": "12h", "bars": n,
        "calendar_days": round(n / 2, 1),
        "ann_sharpe": ann, "time_series_ic": mean_ic,
        "per_asset_ic": {c: round(float(spearmanr(d["vrp"], d["fwd"]).correlation or 0.0), 4)
                         for c, d in panels.items()},
        "gates": f"{sum(v.gates.values())}/{len(v.gates)}" if v else "n<250",
        "survived": bool(v.survived) if v else False,
        "failed_gates": [k for k, ok in v.gates.items() if not ok] if v else [],
        "honesty": ("2 assets = LOW breadth (a vol-timing overlay, not a broad alpha). ~120-day "
                    "window = ~1 regime; PRELIMINARY. The DVOL feed is the NEW orthogonal source."),
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    print(f"options VRP: annSharpe~{ann} IC={mean_ic} gates={out['gates']} "
          f"survived={out['survived']} over {out['calendar_days']}d (PRELIMINARY, low breadth)")


if __name__ == "__main__":
    main()
