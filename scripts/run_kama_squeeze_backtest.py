"""KAMA-squeeze backtest -- pre-registered principal-override test (2026-07-11), full gauntlet.

Hypothesis (canonical TTM-squeeze + Kaufman AMA, ALL params fixed a priori -- no tuning):
volatility compression (Bollinger(20,2) inside Keltner(20,1.5xATR)) precedes expansion; on the
squeeze RELEASE, enter in the direction of the adaptive trend (sign(close - KAMA(10,2,30))) and
hold until price crosses back through KAMA. Variant B (kama_trend: always positioned by KAMA side)
isolates whether the squeeze TIMING adds anything over the raw adaptive MA.

HONESTY: EV gate scored this REJECT (EV 0.001, p~1.6%: price_only x crowded_known -- TTM squeeze is
published retail canon). Tested on explicit principal instruction; the gauntlet's verdict is final
and goes to the graveyard either way. Top-15 majors, inverse-vol basket, net of ADV-tiered costs,
lagged signals (no look-ahead).

    python scripts/run_kama_squeeze_backtest.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import campaign_gate_stats, validate
from libs.data.crypto_source import list_liquid_perps
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.research.crypto_xsec import adv_tier_cost
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_CRYPTO = Path("data/lake/bronze/crypto")
_OUT = Path("web/kama_squeeze_backtest.json")
_TOP = 15
_KAMA_N, _KAMA_F, _KAMA_S = 10, 2, 30                 # canonical Kaufman params
_BB_N, _BB_K, _KC_N, _KC_K = 20, 2.0, 20, 1.5        # canonical TTM squeeze params
_FAIL = ["crowded retail signal", "price-only", "regime artifact", "cost exceeds edge"]


def _kama(close: pd.Series) -> pd.Series:
    er = (close.diff(_KAMA_N).abs()
          / close.diff().abs().rolling(_KAMA_N).sum().replace(0, np.nan))
    fast, slow = 2 / (_KAMA_F + 1), 2 / (_KAMA_S + 1)
    sc = ((er * (fast - slow) + slow) ** 2).fillna(slow ** 2)
    out = close.copy().to_numpy(dtype=float)
    vals = close.to_numpy(dtype=float)
    scv = sc.to_numpy(dtype=float)
    for t in range(1, len(vals)):
        out[t] = out[t - 1] + scv[t] * (vals[t] - out[t - 1])
    return pd.Series(out, index=close.index)


def _positions(df: pd.DataFrame) -> pd.Series:
    """Squeeze-release entry in KAMA direction; hold until close crosses back through KAMA."""
    close, high, low = df["close"], df["high"], df["low"]
    kama = _kama(close)
    mid, sd = close.rolling(_BB_N).mean(), close.rolling(_BB_N).std()
    bb_up, bb_lo = mid + _BB_K * sd, mid - _BB_K * sd
    tr = pd.concat([(high - low), (high - close.shift()).abs(),
                    (low - close.shift()).abs()], axis=1).max(axis=1)
    ema, atr = close.ewm(span=_KC_N).mean(), tr.rolling(_KC_N).mean()
    kc_up, kc_lo = ema + _KC_K * atr, ema - _KC_K * atr
    sq_on = ((bb_up < kc_up) & (bb_lo > kc_lo)).fillna(False).to_numpy()
    side = np.sign((close - kama).to_numpy())
    pos = np.zeros(len(df))
    for t in range(1, len(df)):
        if pos[t - 1] == 0:
            if sq_on[t - 1] and not sq_on[t] and side[t] != 0:   # release -> enter w/ trend
                pos[t] = side[t]
        else:
            pos[t] = pos[t - 1] if side[t] == pos[t - 1] else 0.0  # exit on KAMA cross
    return pd.Series(pos, index=df.index)


def _basket(panels: dict[str, pd.DataFrame], adv: dict[str, float],
            pos_fn) -> np.ndarray:
    closes = pd.DataFrame({s: p["close"] for s, p in panels.items()}).sort_index()
    rets = closes.pct_change(fill_method=None)
    inv_vol = (1.0 / rets.rolling(30).std()).shift(1)
    pos = pd.DataFrame({s: pos_fn(p.reindex(closes.index)) for s, p in panels.items()})
    cost = {s: adv_tier_cost(a) for s, a in adv.items()}
    out = np.zeros(len(closes))
    prev = pd.Series(0.0, index=closes.columns)
    for t in range(1, len(closes)):
        raw = (pos.iloc[t - 1] * inv_vol.iloc[t]).fillna(0.0)     # LAGGED position
        gross = raw.abs().sum()
        w = raw / gross if gross > 0 else raw * 0.0
        r = float((w * rets.iloc[t].fillna(0.0)).sum())
        turn = float(sum(abs(w[s] - prev[s]) * cost.get(s, 1.5e-3) for s in w.index))
        out[t] = r - turn
        prev = w
    return out


def main() -> None:
    panels, adv = {}, {}
    for s in list_liquid_perps(top_n=_TOP * 3):
        if not (_CRYPTO / s / Timeframe.D1.value).exists():
            continue
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
        df = ParquetLake("data/lake").read_bars(Layer.BRONZE, s, Timeframe.D1)
        df = df.set_index("timestamp")
        if len(df) < 400:
            continue
        panels[s] = df[["close", "high", "low"]]
        adv[s] = float((df["close"] * df["volume"]).tail(180).mean())
        if len(panels) >= _TOP:
            break
    if len(panels) < 8:
        raise SystemExit(f"need majors panel; got {len(panels)}")

    strat = {
        "kama_squeeze": _basket(panels, adv, _positions),
        "kama_trend": _basket(panels, adv, lambda d: pd.Series(
            np.sign((d["close"] - _kama(d["close"])).to_numpy()), index=d.index)),
    }
    matrix = np.column_stack([strat["kama_squeeze"], strat["kama_trend"]])
    # per-candidate gates (gap #87 flip, principal-ruled 2026-07-29); thresholds unchanged
    campaign = campaign_gate_stats(matrix)
    results = {}
    # enumerate order == column_stack order over `strat`, so `col` is the strategy's matrix column
    for col, (name, r) in enumerate(strat.items()):
        active = r[r != 0.0]
        sh = round(float(sharpe_ratio(active) * np.sqrt(365)), 2) if len(active) > 5 else 0.0
        hyp = Hypothesis(family=Family.BREAKOUT, subtype=name, symbol="CRYPTO", params={},
                         mechanism=MechanismType.BEHAVIORAL, edge_source="vol_compression",
                         failure_modes=_FAIL)
        v = validate(active, hypothesis=hyp, n_trials=2, sharpe_estimates=[sh, -sh],
                     returns_matrix=matrix, campaign=campaign, column=col
                     ) if len(active) >= 250 else None
        gates = f"{sum(v.gates.values())}/{len(v.gates)}" if v else "n<250"
        results[name] = {"ann_sharpe": sh, "n_active_days": len(active), "gates": gates,
                         "pbo": round(float(v.metrics.pbo), 3) if v else None,
                         "rc_p": round(float(v.metrics.reality_p), 3) if v else None,
                         "survived": bool(getattr(v, "survived", False))}

    out = {"updated": datetime.now(tz=UTC).isoformat(), "majors": len(panels),
           "params": "KAMA(10,2,30) BB(20,2) KC(20,1.5) -- canonical, frozen a priori",
           # campaign-level legacy PBO/RC kept as SEARCH-PROCEDURE diagnostics (gap #87); the
           # gate values are per-strategy now -- see results[*].pbo / results[*].rc_p.
           "pbo": (round(float(campaign.legacy_pbo.pbo), 3)
                   if campaign is not None and campaign.legacy_pbo is not None else None),
           "reality_check_p": (round(float(campaign.legacy_rc.p_value), 3)
                               if campaign is not None and campaign.legacy_rc is not None
                               else None),
           "results": results,
           "ev_gate": "REJECT pre-test (EV 0.001, p~1.6%) -- tested on principal override",
           "note": "verdict is final: graveyard on fail, shadow-candidate path on survive"}
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    for n, res in results.items():
        print(f"{n}: annSharpe {res['ann_sharpe']} gates {res['gates']} "
              f"pbo={res['pbo']} rc_p={res['rc_p']} "
              f"survived={res['survived']} ({res['n_active_days']}d active)")
    print(f"campaign diagnostics: pbo {out['pbo']} | rc_p {out['reality_check_p']} "
          f"(search procedure; gates are per-strategy)")


if __name__ == "__main__":
    main()
