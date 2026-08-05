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
from libs.autodiscovery.validation import campaign_gate_stats, validate
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

    # R0044 (defect #71), the flagged do-by-hand case -- resolved by CONSTRUCTING the proper
    # per-candidate matrix, not by dropping to single-candidate. The validated series is the
    # ROW-MEAN of asset_mat, so it had no column there, and the old code welded the book to a
    # campaign-constant pbo/rc computed once from its own legs: one broadcast verdict whatever
    # the book's merit. The data allows the proper matrix: stack the per-asset legs AND the
    # equal-weight book as its own (last) column -- exactly the shape run_crossasset_shadow.py
    # already uses (combo book = column 2 beside its two sub-books). The book then EARNS its
    # verdict on its own column (CSCV candidate-PBO + Romano-Wolf stepdown) while family-wise
    # error is controlled over ALL series this script examines -- legs included, so the
    # multiplicity of having looked at each leg's IC/Sharpe is paid, not waived. Thresholds
    # unchanged. Degenerate single-asset case (one DVOL feed down): the book IS the lone leg, so
    # the matrix is the book alone, campaign_gate_stats correctly returns None, and validate
    # fails the pbo/reality_check gates CLOSED -- the same fail-closed verdict the old
    # (None, None) branch produced; no campaign constant is ever recomputed from peers.
    matrix = (np.column_stack([asset_mat, book]) if asset_mat.shape[1] >= 2
              else book.reshape(-1, 1))
    book_col = matrix.shape[1] - 1
    # R0044 ACCEPTANCE TEST (mandatory per file): the column index must map to THIS series under
    # the column_stack order above -- a mis-mapped index hands the book a leg's verdict.
    assert np.array_equal(matrix[:, book_col], book), "book_col is not the book's own column"
    sharpes = np.array([sharpe_ratio(matrix[:, i][matrix[:, i] != 0.0])
                        for i in range(matrix.shape[1])])
    campaign = campaign_gate_stats(matrix)            # None when the matrix is the book alone
    v = validate(book[book != 0.0], hypothesis=Hypothesis(
        family=Family.CARRY, subtype="options_vrp", symbol="CRYPTO", params={},
        mechanism=MechanismType.RISK_PREMIUM, edge_source="options_vrp", failure_modes=_FAIL),
        periods_per_year=_PPY,            # 12h DVOL bars, 730/yr (R0086)
        n_trials=matrix.shape[1], sharpe_estimates=sharpes, returns_matrix=matrix,
        campaign=campaign, column=book_col) if n >= 250 else None

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
