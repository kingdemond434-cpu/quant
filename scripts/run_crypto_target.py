"""Emit today's crypto target portfolio -- the brain's per-perp decision for the testnet executor.

Combines the FOUR most decorrelated crypto sleeves -- funding carry, basis carry, taker flow, and
cross-sectional price momentum (the most orthogonal of all, ~-0.06 corr to carry) -- into ONE net
dollar-neutral target weight per perp, gross-normalized to 1. Equal sleeve weight (no fitting,
robust, ~= equal-risk for weakly-correlated sleeves). More decorrelated sleeves => lower portfolio
variance (sigma_port ~ sigma/sqrt(N)) => a smoother equity curve and less MTM giveback, the
diversification benefit -- NOT new validated edge, just variance reduction. data/crypto_target.json.

    python scripts/run_crypto_target.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from libs.data.crypto_source import list_liquid_perps
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.research.crypto_sleeves import latest_weights

_CRYPTO = Path("data/lake/bronze/crypto")
_OUT = Path("data/crypto_target.json")
_SLEEVE_W = Path("data/sleeve_weights.json")     # cross-sleeve allocation (HRP-or-equal, gated)


def _sleeve_weights(names: list[str]) -> dict[str, float]:
    """Per-sleeve capital weights from run_sleeve_alloc (HRP if it beat equal), else equal."""
    try:
        cfg = json.loads(_SLEEVE_W.read_text("utf-8")).get("weights", {})
        if all(k in cfg for k in names):           # only use if it covers exactly this sleeve set
            tot = sum(float(cfg[k]) for k in names)
            if tot > 0:
                return {k: float(cfg[k]) / tot for k in names}
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    return {k: 1.0 / len(names) for k in names}    # robust fallback: equal weight


def merge_sleeve_books(
    named: dict[str, dict[str, float]], sleeve_w: dict[str, float]
) -> dict[str, float]:
    """Combine per-sleeve target books into ONE gross-normalized (sum|w| = 1) net book.

    Each sleeve's per-symbol weight is scaled by its cross-sleeve capital weight and summed per
    symbol; the net book is then normalized so gross exposure is 1. Dust positions (|w| <= 1e-6)
    are dropped. Returns ``{}`` when the combined gross is 0. Pure function (extracted from ``main``
    for testability) — the live per-perp decision the testnet executor consumes.
    """
    merged: dict[str, float] = {}
    for name, book in named.items():
        for sym, w in book.items():
            merged[sym] = merged.get(sym, 0.0) + w * sleeve_w[name]
    gross = sum(abs(v) for v in merged.values())
    if gross <= 0:
        return {}
    return {k: round(v / gross, 5) for k, v in merged.items() if abs(v) > 1e-6}


def _panels() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    lake = ParquetLake("data/lake")
    closes, fundings, bases, takers = {}, {}, {}, {}
    for s in list_liquid_perps(top_n=120):
        if not (_CRYPTO / s / Timeframe.D1.value).exists():
            continue
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
        df = lake.read_bars(Layer.BRONZE, s, Timeframe.D1).set_index("timestamp")
        if "funding" not in df.columns or len(df) < 250:
            continue
        closes[s] = df["close"]
        fundings[s] = df["funding"]
        if "basis" in df.columns:
            bases[s] = df["basis"]
        if "taker_buy_frac" in df.columns:
            takers[s] = df["taker_buy_frac"]
    close = pd.DataFrame(closes).sort_index()
    f = pd.DataFrame(fundings).reindex(close.index)
    basis = pd.DataFrame(bases).reindex(close.index) if bases else pd.DataFrame()
    taker = pd.DataFrame(takers).reindex(close.index) if takers else pd.DataFrame()
    return close, f, basis, taker


def main() -> None:
    close, funding, basis, taker = _panels()
    if close.shape[1] < 12:
        raise SystemExit("need a liquid perp panel; run ingest_crypto + ingest_crypto_enriched")

    named: dict[str, dict[str, float]] = {
        "funding": latest_weights(close, funding.rolling(7).mean(), q=0.2, long_low=True),
        # cross-sectional price momentum -- the most orthogonal sleeve (decorrelates the book)
        "momentum": latest_weights(close, close / close.shift(20) - 1.0, q=0.2, long_low=False),
    }
    if not basis.empty and basis.shape[1] >= 12:
        named["basis"] = latest_weights(close[basis.columns], basis.rolling(3).mean(),
                                        q=0.2, long_low=True)
    if not taker.empty and taker.shape[1] >= 12:
        named["taker"] = latest_weights(close[taker.columns], taker.rolling(5).mean(),
                                        q=0.2, long_low=False)

    sleeve_w = _sleeve_weights(list(named))            # HRP if it beat equal (gated), else equal
    target = merge_sleeve_books(named, sleeve_w)

    payload = {"generated": datetime.now(tz=UTC).isoformat(),
               "as_of": close.index[-1].date().isoformat(), "sleeves": len(named),
               "sleeve_weights": {k: round(sleeve_w[k], 4) for k in named},
               "n_positions": len(target), "weights": dict(sorted(
                   target.items(), key=lambda kv: -abs(kv[1])))}
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(payload, indent=2), "utf-8")
    print(f"crypto target: {len(target)} perps from {len(named)} sleeves "
          f"(weights {payload['sleeve_weights']}) -> {_OUT}")
    for k, v in list(payload["weights"].items())[:12]:
        print(f"  {k:14} {v:+.4f}")


if __name__ == "__main__":
    main()
