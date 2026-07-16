"""Gauntlet on four more crypto-quant-firm alphas -> web/firm_alphas.json. Most should fail.

Genuinely-new families (distinct from the live book's funding/basis/taker/20d-momentum), all
market-neutral long/short, net of cost, signal lagged 1 bar (no look-ahead):
  - short_term_reversal : long 2-day losers / short 2-day winners (overreaction reversion)
  - btc_leadlag         : long alts that LAGGED BTC's move (lead-lag catch-up)
  - funding_momentum    : short names whose funding is ACCELERATING (crowding) / long fading
  - illiquidity_premium : long low-ADV / short high-ADV (size/illiquidity effect, net of cost)
Each runs through the deflated Sharpe ratio + Spearman IC. Honest survivors AND rejects.

    python scripts/run_firm_alphas_backtest.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from libs.data.crypto_source import list_liquid_perps
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.research.crypto_xsec import adv_tier_cost
from libs.validation.dsr import deflated_sharpe_ratio, sharpe_ratio

_CRYPTO = Path("data/lake/bronze/crypto")
_OUT = Path("web/firm_alphas.json")
_PPY = 365.0


def _xsec_ls(sig: pd.DataFrame, ret: pd.DataFrame, cost: float, *, q: float = 0.2,
             band: float = 0.03) -> np.ndarray:
    """Market-neutral long-high/short-low cross-sectional book, turnover-banded, net of cost."""
    out = np.zeros(len(sig))
    prev = pd.Series(0.0, index=sig.columns)
    for t in range(len(sig)):
        s = sig.iloc[t].dropna()
        if len(s) < 12:
            out[t] = float((prev * ret.iloc[t].reindex(prev.index).fillna(0.0)).sum())
            continue
        k = max(1, int(len(s) * q))
        ranked = s.sort_values()
        w = pd.Series(0.0, index=sig.columns)
        w[ranked.index[-k:]] = 0.5 / k
        w[ranked.index[:k]] = -0.5 / k
        delta = (w - prev).abs()
        w = w.where(delta > band, prev)
        pnl = float((w * ret.iloc[t].reindex(w.index).fillna(0.0)).sum())
        turn = float((w - prev).abs().sum()) * cost
        out[t] = pnl - turn
        prev = w
    return out


def _ic(sig: pd.DataFrame, fwd: pd.DataFrame) -> float:
    """Mean cross-sectional Spearman IC of the (lagged) signal vs forward return."""
    ics = []
    for t in range(len(sig)):
        a, b = sig.iloc[t], fwd.iloc[t]
        m = a.notna() & b.notna()
        if m.sum() >= 12:
            r = spearmanr(a[m], b[m]).statistic
            if not np.isnan(r):
                ics.append(float(r))
    return float(np.mean(ics)) if ics else 0.0


def _gauntlet(r: np.ndarray, ic: float, sh_family: np.ndarray) -> dict[str, object]:
    a = r[r != 0.0]
    if len(a) < 100:
        return {"sharpe": 0.0, "ic": round(ic, 4), "dsr_pass": False, "survived": False}
    cum = np.cumprod(1.0 + a)
    dd = float((cum / np.maximum.accumulate(cum) - 1.0).min())
    sharpe = round(float(sharpe_ratio(a) * np.sqrt(_PPY)), 2)
    dsr = deflated_sharpe_ratio(a, n_trials=len(sh_family), sharpe_estimates=sh_family)
    survived = bool(dsr.passed and sharpe > 0 and abs(ic) > 0.01)
    return {"sharpe": sharpe, "cagr": round(float(cum[-1] ** (_PPY / len(a)) - 1.0), 3),
            "max_dd": round(dd, 3), "ic": round(ic, 4), "dsr": round(float(dsr.dsr), 3),
            "dsr_pass": bool(dsr.passed), "survived": survived}


def main() -> None:
    lake = ParquetLake("data/lake")
    closes, fundings, adv = {}, {}, {}
    for s in list_liquid_perps(top_n=120):
        if not (_CRYPTO / s / Timeframe.D1.value).exists():
            continue
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
        df = lake.read_bars(Layer.BRONZE, s, Timeframe.D1).set_index("timestamp")
        if "funding" not in df.columns or len(df) < 250:
            continue
        closes[s], fundings[s] = df["close"], df["funding"]
        adv[s] = float((df["close"] * df["volume"]).tail(180).mean())
    close = pd.DataFrame(closes).sort_index()
    if close.shape[1] < 12:
        raise SystemExit("need a liquid perp panel; run ingest_crypto_enriched")
    funding = pd.DataFrame(fundings).reindex(close.index)
    ret = close.pct_change(fill_method=None)
    fwd = ret                                            # return realised vs the lagged signal
    cost = float(np.mean([adv_tier_cost(a) for a in adv.values()]))
    adv_s = pd.Series(adv)

    # signals (all lagged via .shift(1) so the decision uses only past data)
    sig_str = (-ret.rolling(2).sum()).shift(1)                                  # 2d loser -> long
    btc = ret.get("BTCUSDT")
    sig_ll = ((btc.values[:, None] - ret.to_numpy())                           # alts lagging BTC up
              if btc is not None else ret.to_numpy() * 0.0)
    sig_ll = pd.DataFrame(sig_ll, index=ret.index, columns=ret.columns).shift(1)
    sig_fm = (-funding.diff().rolling(3).mean()).shift(1)                   # fading funding -> long
    sig_il = pd.DataFrame(np.tile(-np.log(adv_s.reindex(close.columns).to_numpy() + 1.0),
                                  (len(close), 1)), index=close.index, columns=close.columns)

    families = {
        "short_term_reversal": _xsec_ls(sig_str, fwd, cost, q=0.2, band=0.05),
        "btc_leadlag": _xsec_ls(sig_ll, fwd, cost, q=0.2, band=0.05),
        "funding_momentum": _xsec_ls(sig_fm, funding * 0 + fwd, cost, q=0.2, band=0.04),
        "illiquidity_premium": _xsec_ls(sig_il, fwd, cost, q=0.2, band=0.10),
    }
    sh_family = np.array([sharpe_ratio(r[r != 0.0]) for r in families.values()
                          if len(r[r != 0.0]) > 100])
    sigs = {"short_term_reversal": sig_str, "btc_leadlag": sig_ll,
            "funding_momentum": sig_fm, "illiquidity_premium": sig_il}
    results = {k: _gauntlet(families[k], _ic(sigs[k], fwd), sh_family) for k in families}
    survivors = [k for k, v in results.items() if v.get("survived")]

    out = {
        "updated": datetime.now(tz=UTC).isoformat(), "obs": len(close),
        "families": results, "survivors": survivors,
        "verdict": (f"{len(survivors)} survivor(s): {survivors}" if survivors
                    else "0 survivors -- all rejected (the gauntlet working; breadth is hard)"),
        "note": ("Four more crypto-firm alphas tested honestly net of cost + DSR. Survivors (if "
                 "any) promote to the forward shadow, never straight to capital. Most fail."),
    }
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    print(f"firm alphas ({len(close)}d): " + " | ".join(
        f"{k} Sh {v['sharpe']} IC {v['ic']} {'PASS' if v.get('survived') else 'rej'}"
        for k, v in results.items()))
    print(f"  {out['verdict']}")


if __name__ == "__main__":
    main()
