"""Refined TREND-following gauntlet -- directional time-series momentum on liquid MAJORS.

The desk already runs a broad-universe daily trend sleeve (ts_trend) and it contributes ~0.01 to
portfolio Sharpe. This tests ONE principled, pre-registered refinement (NOT a parameter hunt):

  * UNIVERSE: liquid majors only (top-N by volume) -- trend is cleaner on majors than on ~100 alts.
  * SIGNAL:   classic managed-futures TS-momentum (long/short by sign of the lagged lookback return,
              inverse-vol sized) -- reuses the proven trend_basket_returns construction.
  * LOOKBACK: a PRE-REGISTERED set {30,60,90,120}d (crypto trends persist for weeks) -- reported in
              full and penalised for multiple testing (n_trials = len(set)) via DSR, so picking the
              best is NOT p-hacking.
  * COST:     ADV-tiered net-of-cost + a turnover band (hysteresis) to cut the churn that kills the
              broad daily version.

"Growth tweak" = the vol-target CAGR is reported for the SURVIVOR only (sizing is scale-invariant,
so it does NOT change the gauntlet verdict -- Sharpe/DSR/PBO are scale-free). We do NOT deploy: this
emits web/trend_gauntlet.json and the verdict stands (survive -> forward shadow; fail -> graveyard).

    python scripts/run_trend_gauntlet.py --top 15
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import campaign_pbo_rc, validate
from libs.data.crypto_source import list_liquid_perps
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.research.crossasset import trend_basket_returns
from libs.research.crypto_xsec import adv_tier_cost
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_OUT = Path("web/trend_gauntlet.json")
_CRYPTO = Path("data/lake/bronze/crypto")
_PPY = 365.0
_LOOKBACKS = (30, 60, 90, 120)          # PRE-REGISTERED -- crypto trend persistence, not a sweep
_BAND = 0.10                            # turnover band (hysteresis) -> cut churn cost
_VOL_TARGET = 0.20                      # 20% annual vol target for the growth/CAGR readout only
_FAIL = ["whipsaw in ranges", "regime shift (trend->chop)", "cost exceeds edge", "crowding/decay"]


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


def _cagr_at_vol(r: np.ndarray) -> float:
    a = r[r != 0.0]
    if len(a) < 30:
        return 0.0
    realised = float(np.std(a) * np.sqrt(_PPY))
    scale = _VOL_TARGET / realised if realised > 0 else 0.0
    return round((float(np.mean(a)) * scale * _PPY) * 100, 1)   # vol-targeted annual return %


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()

    close, adv = _majors(args.top)
    if close.shape[1] < 6:
        raise SystemExit(f"need a majors panel; got {close.shape[1]} names with history")
    cost = {s: adv_tier_cost(a) for s, a in adv.items()}

    sleeves = {f"trend_{lb}d": trend_basket_returns(close, cost, lookback=lb, band=_BAND)
               for lb in _LOOKBACKS}
    n = min(len(v) for v in sleeves.values())
    matrix = np.column_stack([v[-n:] for v in sleeves.values()])
    sharpes = np.array([sharpe_ratio(v[v != 0.0]) for v in sleeves.values()])
    pbo, rc = campaign_pbo_rc(matrix)

    results = []
    for name, r in sleeves.items():
        active = r[r != 0.0]
        ann = round(float(sharpe_ratio(active) * np.sqrt(_PPY)), 2) if len(active) > 5 else 0.0
        v = (validate(active, hypothesis=Hypothesis(
            family=Family.TREND, subtype=name, symbol="CRYPTO-MAJORS", params={},
            mechanism=MechanismType.BEHAVIORAL, edge_source=name, failure_modes=_FAIL),
            n_trials=len(_LOOKBACKS), sharpe_estimates=sharpes, returns_matrix=matrix,
            pbo=pbo, rc=rc) if len(active) >= 250 else None)
        gates = f"{sum(v.gates.values())}/{len(v.gates)}" if v else "n<250"
        results.append({"sleeve": name, "ann_sharpe": ann, "cagr_at_20pct_vol": _cagr_at_vol(r),
                        "n_obs": len(active), "gates": gates,
                        "survived": bool(v.survived) if v else False,
                        "failed_gates": [k for k, ok in v.gates.items() if not ok] if v else []})

    best = max(results, key=lambda x: x["ann_sharpe"])
    any_survived = any(x["survived"] for x in results)
    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "strategy": "directional TS-momentum (managed-futures) on liquid crypto majors",
        "universe": list(close.columns), "n_majors": int(close.shape[1]),
        "days": int(close.shape[0]), "lookbacks_tested": list(_LOOKBACKS),
        "band": _BAND, "n_trials_penalty": len(_LOOKBACKS),
        "pbo": round(float(pbo.pbo), 3) if pbo else None,
        "reality_check_p": round(float(rc.p_value), 3) if rc else None,
        "results": results, "best": best["sleeve"],
        "verdict": ("SURVIVED gauntlet -> promote to forward shadow (still needs 90d OOS)"
                    if any_survived else
                    "REJECTED -> graveyard (in-sample gauntlet not passed; do not deploy)"),
        "honesty": ("Multiple-testing penalised (DSR n_trials=4). Sharpe/DSR/PBO are scale-free so "
                    "vol-target does not change the verdict -- CAGR shown for context only. A pass "
                    "here is in-sample; forward validation still gates capital."),
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    for r in results:
        print(f"  {r['sleeve']:12} Sharpe~{r['ann_sharpe']:5} cagr@20v={r['cagr_at_20pct_vol']:6}% "
              f"n={r['n_obs']:4} gates={r['gates']:5} survived={r['survived']}")
    print(f"pbo={out['pbo']} rc_p={out['reality_check_p']} over {out['days']}d "
          f"{close.shape[1]} majors -> {out['verdict']}")


if __name__ == "__main__":
    main()
