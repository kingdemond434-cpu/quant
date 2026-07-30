"""MT5 cross-asset edge search -- the honest maximum on the broker's real multi-asset universe.

Loads every asset class that landed in the lake (FX, metals, energy, indices, crypto CFDs) and tests
the DIVERSIFIED-PORTFOLIO constructions that single-name FX lacked: cross-sectional momentum, its
short-term reversal sibling, and a time-series-momentum (managed-futures) trend basket -- each
net of realistic per-asset-class cost, each through the FULL institutional gauntlet (CPCV, PBO,
trials-deflated DSR, White's Reality Check, walk-forward, capacity, fragility). No parameter mining.

Survivors are reported straight; zero is reported as zero. Writes reports/mt5_crossasset/report.json
for the dashboard scoreboard.

    python scripts/run_mt5_crossasset.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import campaign_gate_stats, validate
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.research.crossasset import trend_basket_returns, xsec_momentum_returns
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_COVERAGE = Path("reports/multiasset_coverage.json")
_OUT = Path("reports/mt5_crossasset")
_PPY = 252.0

# Realistic per-side cost by asset class on a retail MT5 demo broker (spread/2 + slippage), bps/1e4.
_COST = {
    "fx": 1.0e-4, "metal": 2.0e-4, "energy": 2.5e-4,
    "index": 1.0e-4, "crypto": 6.0e-4, "equity": 2.0e-4,
}
_FAIL = ["factor premium compresses / crowds", "regime shift (trend->chop)",
         "correlated cross-asset drawdown", "broker cost/slippage exceeds edge", "edge decay"]


def _load() -> tuple[pd.DataFrame, dict[str, float]]:
    cov = json.loads(_COVERAGE.read_text("utf-8"))
    lake = ParquetLake("data/lake")
    closes: dict[str, pd.Series] = {}
    cost: dict[str, float] = {}
    for c in cov:
        if not c.get("bars"):
            continue
        sym, ac = str(c["symbol"]), str(c["asset_class"])
        register_instrument(InstrumentSpec(symbol=sym, asset_class=AssetClass(ac), description=sym))
        df = lake.read_bars(Layer.BRONZE, sym, Timeframe.D1).set_index("timestamp")
        if len(df) < 250:
            continue
        closes[sym] = df["close"]
        cost[sym] = _COST.get(ac, 2.0e-4)
    close = pd.DataFrame(closes).sort_index()
    return close, cost


def _variants(close: pd.DataFrame, cost: dict[str, float]) -> list[tuple[str, Family, np.ndarray]]:
    out: list[tuple[str, Family, np.ndarray]] = []
    for lb in (60, 120, 250):
        out.append((f"xsec_mom_lb{lb}", Family.MOMENTUM,
                    xsec_momentum_returns(close, cost, lookback=lb, q=0.3, band=0.05)))
    for lb in (5, 10):
        out.append((f"xsec_rev_lb{lb}", Family.MEAN_REVERSION,
                    xsec_momentum_returns(close, cost, lookback=lb, q=0.3, band=0.05,
                                          long_high=False)))
    for lb in (50, 100, 200):
        out.append((f"trend_basket_lb{lb}", Family.TREND,
                    trend_basket_returns(close, cost, lookback=lb, band=0.05)))
    return out


def main() -> None:
    close, cost = _load()
    if close.shape[1] < 6:
        raise SystemExit("need >=6 cross-asset symbols; run scripts/ingest_multiasset.py first")
    print(f"CROSS-ASSET panel: {close.shape[1]} symbols x {close.shape[0]} days "
          f"({close.index[0].date()}..{close.index[-1].date()})")

    series = _variants(close, cost)
    min_len = min(len(r) for _, _, r in series)
    matrix = np.column_stack([r[-min_len:] for _, _, r in series])
    sharpes = np.array([sharpe_ratio(r[r != 0.0]) for _, _, r in series], dtype="float64")
    # per-candidate gates (gap #87 flip, principal-ruled 2026-07-29); thresholds unchanged
    campaign = campaign_gate_stats(matrix)

    survivors, results = 0, []
    # enumerate order == column_stack order over `series`, so `col` is the variant's matrix column
    for col, ((name, fam, rets), spr) in enumerate(zip(series, sharpes, strict=True)):
        active = rets[rets != 0.0]
        v = (
            validate(
                active,
                hypothesis=Hypothesis(
                    family=fam, subtype=name, symbol="MT5_XASSET", params={},
                    mechanism=MechanismType.RISK_PREMIUM,
                    edge_source="cross-asset diversified portfolio (costed)",
                    failure_modes=_FAIL),
                n_trials=len(series), sharpe_estimates=sharpes,
                returns_matrix=matrix, campaign=campaign, column=col)
            if len(active) >= 250 else None
        )
        survived = bool(v.survived) if v else False
        survivors += int(survived)
        ann = round(float(spr) * np.sqrt(_PPY), 2)
        gates = v.gates if v else {}
        results.append({"variant": name, "family": fam.value, "days": len(active),
                        "ann_sharpe": ann, "survived": survived,
                        "gates_passed": f"{sum(gates.values())}/{len(gates)}" if gates else "n<250",
                        "reason": v.rejection_reason if v else "n<250"})

    _OUT.mkdir(parents=True, exist_ok=True)
    payload = {"symbols": close.shape[1], "days": close.shape[0],
               "survivors": survivors, "variants": results}
    (_OUT / "report.json").write_text(json.dumps(payload, indent=2), "utf-8")
    print(f"\n[mt5-crossasset] tested={len(series)} survivors={survivors}")
    for r in results:
        print(f"  {r['variant']:18} {r['family']:14} days={r['days']:4} "
              f"ann_sharpe~{r['ann_sharpe']:6} gates={r['gates_passed']:5} "
              f"survived={r['survived']}  {r['reason']}")
    if survivors == 0:
        print("\nZERO survivors net-of-cost across the MT5 cross-asset universe (honest).")


if __name__ == "__main__":
    main()
