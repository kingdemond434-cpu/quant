"""Combined book optimiser: perp sleeves + spot sleeves, as ONE account -> web/combined.json.

Answers 'how do both do together, and is the perp book helping or hurting?'. Builds a perp book and
a spot book, then finds the capital split that MAXIMISES geometric growth / Sharpe (the tangency
mix, two-fund separation), compares it to equal-capital and risk-parity, and leverages the optimal
mix to a target vol band -- reporting honest CAGR and the vol that 100% CAGR would actually require.

Everything here is an IN-SAMPLE backtest estimate. The deployed weight + leverage must RAMP from a
conservative split to the optimum only as the forward shadows validate -- optimising weights to a
gaudy in-sample Sharpe is the overfitting trap the mandate forbids. So we report the target, not an
order. Runs on the flywheel so the view stays current 24/7.

    python scripts/run_combined_stats.py
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.data.crypto_source import list_liquid_perps  # noqa: E402
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument  # noqa: E402
from libs.data.lake import Layer, ParquetLake  # noqa: E402
from libs.data.timeframe import Timeframe  # noqa: E402
from libs.data.universe import RESEARCH_TOP_N  # noqa: E402
from libs.research.cashcarry import cashcarry_returns, spot_basis_carry_returns  # noqa: E402
from libs.research.crossasset import xsec_momentum_returns  # noqa: E402
from libs.research.crypto_sleeves import basis_carry_returns, taker_flow_returns  # noqa: E402
from libs.research.crypto_xsec import adv_tier_cost, xsec_funding_returns  # noqa: E402

_CRYPTO = Path("data/lake/bronze/crypto")
_OUT = Path("web/combined.json")
_PPY = 365.0
_VOL_BAND = (0.30, 0.35)                         # target portfolio vol band (user objective)
_LEV_CAP = 8.0                                   # hard leverage ceiling (ruin guard; lower live)


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
        closes[s], fundings[s] = df["close"], df["funding"]
        adv[s] = float((df["close"] * df["volume"]).tail(180).mean())
        if "basis" in df.columns:
            bases[s] = df["basis"]
        if "taker_buy_frac" in df.columns:
            takers[s] = df["taker_buy_frac"]
    c = pd.DataFrame(closes).sort_index()
    f = pd.DataFrame(fundings).reindex(c.index)
    b = pd.DataFrame(bases).reindex(c.index) if bases else pd.DataFrame()
    t = pd.DataFrame(takers).reindex(c.index) if takers else pd.DataFrame()
    return c, f, b, t, adv


def _stats(r: np.ndarray) -> dict[str, float]:
    a = r[r != 0.0]
    if len(a) < 6:
        return {"ann_sharpe": 0.0, "ann_vol": 0.0, "max_dd": 0.0, "cagr": 0.0}
    cum = np.cumprod(1.0 + a)
    dd = float((cum / np.maximum.accumulate(cum) - 1.0).min())
    cagr = float(cum[-1] ** (_PPY / len(a)) - 1.0)
    sharpe = float(np.mean(a) / np.std(a) * np.sqrt(_PPY)) if np.std(a) > 0 else 0.0
    return {"ann_sharpe": round(sharpe, 2), "ann_vol": round(float(np.std(a) * np.sqrt(_PPY)), 3),
            "max_dd": round(dd, 3), "cagr": round(cagr, 3)}


def _sharpe(r: np.ndarray) -> float:
    return float(np.mean(r) / np.std(r) * np.sqrt(_PPY)) if np.std(r) > 0 else 0.0


def _ann_vol(r: np.ndarray) -> float:
    return float(np.std(r) * np.sqrt(_PPY))


def _cagr_at_lev(r: np.ndarray, lev: float) -> float:
    g = 1.0 + lev * r
    if np.any(g <= 0.0):                          # a -100% day at this leverage = ruin
        return float("nan")
    return float(np.prod(g) ** (_PPY / len(r)) - 1.0)


def _safe_lev(r: np.ndarray) -> float:
    worst = float(-r.min())
    return _LEV_CAP if worst <= 0 else min(_LEV_CAP, 0.95 / worst)


def _book(sleeves: list[np.ndarray]) -> np.ndarray:
    n = min(len(s) for s in sleeves)
    return np.mean([s[-n:] for s in sleeves], axis=0)


def main() -> None:
    close, funding, basis, taker, adv = _panels()
    if close.shape[1] < 12:
        raise SystemExit("need a liquid perp panel; run ingest_crypto_enriched")
    cost = {s: adv_tier_cost(a) for s, a in adv.items()}

    perp_sleeves = [xsec_funding_returns(close, funding, adv, lookback=7, q=0.2, band=0.02),
                    xsec_momentum_returns(close, cost, lookback=20, q=0.3, band=0.05)]
    if not basis.empty and basis.shape[1] >= 12:
        perp_sleeves.append(basis_carry_returns(close[basis.columns], funding[basis.columns],
                                                basis, adv, lookback=3, q=0.2, band=0.02))
    if not taker.empty and taker.shape[1] >= 12:
        perp_sleeves.append(taker_flow_returns(close[taker.columns], funding[taker.columns],
                                               taker, adv, lookback=5, q=0.2, band=0.02))
    spot_sleeves = [cashcarry_returns(funding, basis)]
    if not basis.empty and basis.shape[1] >= 12:
        spot_sleeves.append(spot_basis_carry_returns(funding, basis))

    perp, spot = _book(perp_sleeves), _book(spot_sleeves)
    m = min(len(perp), len(spot))
    perp, spot = perp[-m:], spot[-m:]
    mask = (perp != 0.0) | (spot != 0.0)
    corr = float(np.corrcoef(perp[mask], spot[mask])[0, 1]) if mask.sum() > 5 else 0.0

    # --- weighting search: w = perp capital fraction (1-w to spot) ---
    grid = np.linspace(0.0, 1.0, 41)
    blends = {w: w * perp + (1.0 - w) * spot for w in grid}
    w_sharpe = float(max(grid, key=lambda w: _sharpe(blends[w])))      # tangency (max-Sharpe) mix
    vp, vs = _ann_vol(perp), _ann_vol(spot)
    w_invvol = float((1.0 / vp) / (1.0 / vp + 1.0 / vs)) if vp > 0 and vs > 0 else 0.5

    schemes = {"equal_capital": 0.5, "inverse_vol": round(w_invvol, 3), "max_sharpe": w_sharpe}
    scheme_stats = {k: _stats(w * perp + (1.0 - w) * spot) for k, w in schemes.items()}

    # --- leverage the OPTIMAL (max-Sharpe) mix to the vol band; honest CAGR + the 100% tension ---
    opt = w_sharpe * perp + (1.0 - w_sharpe) * spot
    base_vol, cap = _ann_vol(opt), _safe_lev(opt)
    lo_v, hi_v = _VOL_BAND
    lev_lo = min(cap, lo_v / base_vol) if base_vol > 0 else 0.0
    lev_hi = min(cap, hi_v / base_vol) if base_vol > 0 else 0.0
    lev_mid = min(cap, 0.5 * (lo_v + hi_v) / base_vol) if base_vol > 0 else 0.0
    # leverage needed for ~100% CAGR (smallest lev on the grid reaching it, else max achievable)
    levs = np.linspace(0.0, cap, 161)
    cagrs = np.array([_cagr_at_lev(opt, x) for x in levs])
    ok = ~np.isnan(cagrs)
    hit = levs[ok][cagrs[ok] >= 1.0]
    lev_100 = float(hit[0]) if hit.size else float("nan")
    peak_i = int(np.nanargmax(cagrs))

    perp_helps = scheme_stats["max_sharpe"]["ann_sharpe"] - _stats(spot)["ann_sharpe"]
    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "basis": "in-sample backtest; deployed weight+leverage RAMP to optimum as shadows validate",
        "books": {"perp": _stats(perp), "spot": _stats(spot)}, "correlation": round(corr, 3),
        "weighting": {k: {"w_perp": round(schemes[k], 3), **scheme_stats[k]} for k in schemes},
        "optimal_w_perp": round(w_sharpe, 3),
        "perp_marginal_sharpe": round(perp_helps, 2),
        "perp_verdict": ("perp HELPS at the optimal mix" if perp_helps > 0.02
                         else "perp DRAGS -- optimal mix underweights it"),
        "leverage_to_target": {
            "vol_band": list(_VOL_BAND), "base_vol_unlevered": round(base_vol, 3),
            "lev_for_vol_lo": round(lev_lo, 2), "lev_for_vol_hi": round(lev_hi, 2),
            "cagr_at_vol_lo": round(_cagr_at_lev(opt, lev_lo), 3),
            "cagr_at_vol_mid": round(_cagr_at_lev(opt, lev_mid), 3),
            "cagr_at_vol_hi": round(_cagr_at_lev(opt, lev_hi), 3),
            "lev_for_cagr_100": None if np.isnan(lev_100) else round(lev_100, 2),
            "vol_at_cagr_100": None if np.isnan(lev_100) else round(base_vol * lev_100, 3),
            "max_cagr": round(float(cagrs[peak_i]), 3),
            "lev_at_max_cagr": round(float(levs[peak_i]), 2), "ruin_lev_cap": round(cap, 2),
        },
        "note": ("OPTIMAL = max-Sharpe (tangency) mix, then lever to the vol budget = max "
                 "geometric growth for that risk (two-fund separation). IN-SAMPLE: live "
                 "weight+leverage are edge-gated, ramping only as forward shadows prove edge."),
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    lt = out["leverage_to_target"]
    print(f"perp {_stats(perp)['ann_sharpe']} / spot {_stats(spot)['ann_sharpe']} "
          f"(corr {corr:.2f}) | OPTIMAL w_perp={w_sharpe:.2f} -> "
          f"Sharpe {scheme_stats['max_sharpe']['ann_sharpe']} | {out['perp_verdict']}")
    print(f"  lever opt to vol {_VOL_BAND[0]*100:.0f}-{_VOL_BAND[1]*100:.0f}%: "
          f"CAGR {lt['cagr_at_vol_lo']*100:.0f}-{lt['cagr_at_vol_hi']*100:.0f}% "
          f"(lev {lt['lev_for_vol_lo']}-{lt['lev_for_vol_hi']}x) | "
          f"100% CAGR needs vol {lt['vol_at_cagr_100']} | max CAGR {lt['max_cagr']*100:.0f}%")


if __name__ == "__main__":
    main()
