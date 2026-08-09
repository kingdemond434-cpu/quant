"""Honest deployability experiment: can legitimate risk engineering clear the MT5 combo's gates?

The cross-asset trend+momentum combo fails fragility (fat tails) and PBO. This applies ONE
pre-specified, economically-standard upgrade -- time-varying volatility targeting (10% annual,
trailing-vol lagged, leverage-capped) -- and re-runs the FULL gauntlet on both the raw and the
vol-targeted combo, side by side. No parameter mining: the vol-target config is the textbook
managed-futures default, declared before the run. We report whether fragility/PBO flip, honestly.

    python scripts/run_crossasset_robust.py
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
from libs.research.crossasset import trend_basket_returns, vol_target, xsec_momentum_returns
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_COVERAGE = Path("reports/multiasset_coverage.json")
_OUT = Path("reports/mt5_crossasset_robust")
_PPY = 252.0
_FROZEN = {"trend_lb": 100, "mom_lb": 120, "q": 0.3, "band": 0.05}
_VT = {"target_ann_vol": 0.10, "lookback": 30, "max_leverage": 3.0}   # textbook default, declared
_COST = {"fx": 1.0e-4, "metal": 2.0e-4, "energy": 2.5e-4,
         "index": 1.0e-4, "crypto": 6.0e-4, "equity": 2.0e-4}
_FAIL = ["trend/momentum premia compress or crowd", "regime shift (trend->chop)",
         "correlated cross-asset drawdown", "broker cost exceeds edge", "edge decay"]


def _load() -> tuple[pd.DataFrame, dict[str, float]]:
    cov = json.loads(_COVERAGE.read_text("utf-8"))
    lake = ParquetLake("data/lake")
    closes, cost = {}, {}
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
    return pd.DataFrame(closes).sort_index(), cost


def _gate(name: str, r: np.ndarray, matrix: np.ndarray, sharpes: np.ndarray,
          campaign, column: int) -> dict[str, object]:  # type: ignore[no-untyped-def]
    active = r[r != 0.0]
    v = validate(active, hypothesis=Hypothesis(
        family=Family.CROSS_ASSET, subtype=name, symbol="MT5_XASSET", params={},
        mechanism=MechanismType.RISK_PREMIUM, edge_source="cross-asset combo (risk-engineered)",
        failure_modes=_FAIL), periods_per_year=_PPY,      # D1 MT5 session bars, 252/yr (R0086)
        n_trials=matrix.shape[1], sharpe_estimates=sharpes,
        returns_matrix=matrix, campaign=campaign, column=column)
    return {"variant": name, "ann_sharpe": round(float(sharpe_ratio(active) * np.sqrt(_PPY)), 2),
            "survived": bool(v.survived), "gates": v.gates,
            "gates_passed": f"{sum(v.gates.values())}/{len(v.gates)}",
            "reason": v.rejection_reason or "PASSED"}


def main() -> None:
    close, cost = _load()
    tlb, mlb, q, band = (_FROZEN["trend_lb"], _FROZEN["mom_lb"], _FROZEN["q"], _FROZEN["band"])
    r_trend = trend_basket_returns(close, cost, lookback=tlb, band=band)
    r_mom = xsec_momentum_returns(close, cost, lookback=mlb, q=q, band=band)
    r_combo = 0.5 * r_trend + 0.5 * r_mom
    r_combo_vt = vol_target(r_combo, **_VT)

    series = [("combo_raw", r_combo), ("combo_voltarget", r_combo_vt),
              ("trend_only", r_trend), ("mom_only", r_mom)]
    matrix = np.column_stack([s for _, s in series])
    sharpes = np.array([sharpe_ratio(s[s != 0.0]) for _, s in series])
    # per-candidate gates (gap #87 flip, principal-ruled 2026-07-29); thresholds unchanged
    campaign = campaign_gate_stats(matrix)

    # enumerate order == column_stack order over `series`, so `i` is each variant's matrix column
    results = [_gate(n, r, matrix, sharpes, campaign, i) for i, (n, r) in enumerate(series)]
    _OUT.mkdir(parents=True, exist_ok=True)
    (_OUT / "report.json").write_text(json.dumps(results, indent=2), "utf-8")

    print(f"panel: {close.shape[1]} instruments x {close.shape[0]} days\n")
    for r in results:
        fails = [k for k, ok in r["gates"].items() if not ok]  # type: ignore[union-attr]
        print(f"  {r['variant']:16} sharpe~{r['ann_sharpe']:5} gates={r['gates_passed']:5} "
              f"survived={r['survived']}  fails={fails}")
    vt = next(r for r in results if r["variant"] == "combo_voltarget")
    raw = next(r for r in results if r["variant"] == "combo_raw")
    print(f"\nvol-targeting effect: raw {raw['gates_passed']} ({raw['reason']}) "
          f"-> vol-targeted {vt['gates_passed']} ({vt['reason']})")


if __name__ == "__main__":
    main()
