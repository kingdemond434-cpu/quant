"""Cross-sectional funding -- the consolidated MAX run (all 4 legitimate free levers).

  L1 Liquid universe  : only top-N perps by 24h volume (tradeable, realistic-cost names).
  L2 Per-symbol cost  : ADV-tiered taker+slippage (not a flat optimistic bp).
  L3 Risk-parity size : inverse-vol weighting within each leg + book vol-target (drawdown control).
  L4 Turnover control : a rebalance band so positions only change on a material rank shift.

No parameter mining, no test-set optimization -- those would inflate backtest Sharpe and destroy the
real edge. This is the honest ceiling of the best signal. Survivors reported straight.

    python scripts/run_xsec_funding_max.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import campaign_pbo_rc, validate
from libs.data.crypto_source import list_liquid_perps
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.research.crypto_xsec import xsec_funding_returns
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_CRYPTO = Path("data/lake/bronze/crypto")
_OUT = Path("reports/xsec_funding_max")
_MIN_NAMES = 12
_FAIL = ["funding dispersion compresses", "liquidity/borrow constraints",
         "correlated crypto crash", "edge decay"]


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


def main() -> None:
    universe = list_liquid_perps(top_n=100)
    close, funding, adv = _panels(universe)
    if close.shape[1] < _MIN_NAMES:
        raise SystemExit("need a liquid panel; run: ingest_crypto.py --universe liquid")
    print(f"LIQUID panel: {close.shape[1]} perps x {close.shape[0]} days "
          f"({close.index[0].date()}..{close.index[-1].date()})")

    variants = [("lb3_q20_b02", 3, 0.2, 0.02), ("lb7_q20_b02", 7, 0.2, 0.02),
                ("lb3_q15_b03", 3, 0.15, 0.03)]
    series = [(n, xsec_funding_returns(close, funding, adv, lookback=lb, q=q, band=b))
              for n, lb, q, b in variants]
    min_len = min(len(r) for _, r in series)
    matrix = np.column_stack([r[-min_len:] for _, r in series])
    sharpes = np.array([sharpe_ratio(r[r != 0.0]) for _, r in series], dtype="float64")
    pbo, rc = campaign_pbo_rc(matrix)

    survivors = 0
    results = []
    for (name, rets), spr in zip(series, sharpes, strict=True):
        active = rets[rets != 0.0]
        v = validate(active, hypothesis=Hypothesis(
            family=Family.CARRY, subtype=f"xsec_max_{name}", symbol="CRYPTO_XSEC", params={},
            mechanism=MechanismType.RISK_PREMIUM, edge_source="x-sec funding (risk-parity, costed)",
            failure_modes=_FAIL), n_trials=len(series), sharpe_estimates=sharpes,
            returns_matrix=matrix, pbo=pbo, rc=rc) if len(active) >= 250 else None
        survived = bool(v.survived) if v else False
        survivors += int(survived)
        ann = round(float(spr) * np.sqrt(365), 2)
        results.append({"variant": name, "days": len(active),
                        "ann_sharpe": ann, "survived": survived,
                        "reason": v.rejection_reason if v else "n<250"})

    _OUT.mkdir(parents=True, exist_ok=True)
    payload = {"perps": close.shape[1], "survivors": survivors, "variants": results}
    (_OUT / "report.json").write_text(json.dumps(payload, indent=2), "utf-8")
    print(f"\n[xsec-funding MAX] tested={len(series)} survivors={survivors}")
    for r in results:
        print(f"  {r['variant']}: days={r['days']} ann_sharpe~{r['ann_sharpe']} "
              f"survived={r['survived']} {r['reason']}")
    if survivors == 0:
        print("ZERO survivors net-of-cost after all 4 levers (honest).")


if __name__ == "__main__":
    main()
