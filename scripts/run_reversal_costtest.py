"""Cost-hypothesis test: do reversal / BTC-lead-lag turn viable at lower turnover + maker fees?

The firm-alpha gauntlet showed both have positive IC but lose net of cost. This sweeps band
(turnover) x cost (taker vs maker ~half) per signal, reporting the FULL grid + the GROSS (cost-free)
Sharpe ceiling -- the decisive number: negative gross Sharpe means cost was never the killer.
Viable only if net Sharpe > 0 at MAKER cost AND survives DSR AND positive across >=2 bands. Not
p-hacking -- a pre-set grid testing one named hypothesis, DSR-deflated. -> web/reversal_cost.json.

    python scripts/run_reversal_costtest.py
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
from libs.research.crypto_xsec import adv_tier_cost
from libs.validation.dsr import deflated_sharpe_ratio, sharpe_ratio

_OUT = Path("web/reversal_cost.json")
_CRYPTO = Path("data/lake/bronze/crypto")
_PPY = 365.0
_BANDS = [0.05, 0.15, 0.30, 0.50]


def _ls(sig: pd.DataFrame, ret: pd.DataFrame, cost: float, band: float
        ) -> tuple[np.ndarray, float]:
    """Long-high/short-low book; returns (net daily returns, annualised turnover)."""
    out = np.zeros(len(sig))
    turn_tot = 0.0
    prev = pd.Series(0.0, index=sig.columns)
    for t in range(len(sig)):
        s = sig.iloc[t].dropna()
        if len(s) < 12:
            out[t] = float((prev * ret.iloc[t].reindex(prev.index).fillna(0.0)).sum())
            continue
        k = max(1, int(len(s) * 0.2))
        ranked = s.sort_values()
        w = pd.Series(0.0, index=sig.columns)
        w[ranked.index[-k:]] = 0.5 / k
        w[ranked.index[:k]] = -0.5 / k
        delta = (w - prev).abs()
        w = w.where(delta > band, prev)
        tn = float((w - prev).abs().sum())
        turn_tot += tn
        out[t] = float((w * ret.iloc[t].reindex(w.index).fillna(0.0)).sum()) - tn * cost
        prev = w
    return out, turn_tot / len(sig) * _PPY


def _sharpe(r: np.ndarray) -> float:
    a = r[r != 0.0]
    return round(float(sharpe_ratio(a) * np.sqrt(_PPY)), 2) if len(a) > 100 else 0.0


def main() -> None:
    lake = ParquetLake("data/lake")
    closes, adv = {}, {}
    for s in list_liquid_perps(top_n=120):
        if not (_CRYPTO / s / Timeframe.D1.value).exists():
            continue
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
        df = lake.read_bars(Layer.BRONZE, s, Timeframe.D1).set_index("timestamp")
        if "funding" not in df.columns or len(df) < 250:
            continue
        closes[s] = df["close"]
        adv[s] = float((df["close"] * df["volume"]).tail(180).mean())
    close = pd.DataFrame(closes).sort_index()
    if close.shape[1] < 12:
        raise SystemExit("need a liquid perp panel")
    ret = close.pct_change(fill_method=None)
    taker = float(np.mean([adv_tier_cost(a) for a in adv.values()]))
    maker = taker * 0.5                                   # maker ~ half taker fee
    btc = ret.get("BTCUSDT")

    sig_rev = (-ret.rolling(2).sum()).shift(1)
    sig_ll = pd.DataFrame((btc.values[:, None] - ret.to_numpy()) if btc is not None
                          else ret.to_numpy() * 0.0, index=ret.index, columns=ret.columns).shift(1)

    grids: dict[str, dict] = {}
    all_maker_sharpes: list[float] = []
    for name, sig in (("short_term_reversal", sig_rev), ("btc_leadlag", sig_ll)):
        gross, _ = _ls(sig, ret, 0.0, 0.15)
        cells = []
        for band in _BANDS:
            r_tk, turn = _ls(sig, ret, taker, band)
            r_mk, _ = _ls(sig, ret, maker, band)
            s_mk = _sharpe(r_mk)
            all_maker_sharpes.append(s_mk)
            cells.append({"band": band, "ann_turnover": round(turn, 1),
                          "sharpe_taker": _sharpe(r_tk), "sharpe_maker": s_mk})
        grids[name] = {"gross_sharpe": _sharpe(gross), "cells": cells}

    # DSR on the single best maker cell across BOTH signals, deflated by the whole grid searched
    best_name, best_cell, best_arr = "", None, np.zeros(1)
    for name, sig in (("short_term_reversal", sig_rev), ("btc_leadlag", sig_ll)):
        for band in _BANDS:
            r_mk, _ = _ls(sig, ret, maker, band)
            if _sharpe(r_mk) > _sharpe(best_arr):
                best_name, best_cell, best_arr = name, band, r_mk
    sh_family = np.array([sharpe_ratio(x) for x in [best_arr]] + [s / np.sqrt(_PPY)
                         for s in all_maker_sharpes if s != 0.0])
    dsr = deflated_sharpe_ratio(best_arr[best_arr != 0.0], n_trials=len(all_maker_sharpes),
                                sharpe_estimates=sh_family)
    pos_bands = sum(1 for c in grids.get(best_name, {}).get("cells", []) if c["sharpe_maker"] > 0)
    viable = bool(dsr.passed and _sharpe(best_arr) > 0 and pos_bands >= 2)

    out = {
        "updated": datetime.now(tz=UTC).isoformat(), "obs": len(close),
        "taker_cost": round(taker, 5), "maker_cost": round(maker, 5),
        "grids": grids,
        "best": {"signal": best_name, "band": best_cell, "sharpe_maker": _sharpe(best_arr),
                 "dsr": round(float(dsr.dsr), 3), "dsr_pass": bool(dsr.passed),
                 "positive_bands": pos_bands},
        "viable": viable,
        "verdict": (f"{best_name} VIABLE at maker cost (band {best_cell})" if viable
                    else "REJECTED -- gross Sharpe NEGATIVE: cost was never the killer, the L/S "
                    "book itself is unprofitable (positive IC did not translate to tradeable P&L)"),
        "note": ("Tests the cost hypothesis the IC raised, not a new alpha. Gross Sharpe = the "
                 "signal's ceiling; the question is whether maker fees + wider bands clear cost. "
                 "Viable only if DSR-robust across >=2 bands, else it stays a reject (honest)."),
    }
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    for name, g in grids.items():
        print(f"{name} (gross {g['gross_sharpe']}): " + " | ".join(
            f"b{c['band']} mkr {c['sharpe_maker']} (turn {c['ann_turnover']})"
            for c in g["cells"]))
    print(f"  best maker: {best_name} band {best_cell} Sharpe {_sharpe(best_arr)} "
          f"DSR {out['best']['dsr']} pass={dsr.passed} -> {out['verdict']}")


if __name__ == "__main__":
    main()
