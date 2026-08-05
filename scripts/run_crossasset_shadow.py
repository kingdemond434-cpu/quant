"""Forward SHADOW + target-portfolio emitter for the MT5 cross-asset book (zero capital).

This is the Python brain executing the architecture end-to-end in shadow: it researches globally
(the full multi-asset lake), builds the most ROBUST MT5-executable book -- an equal-risk combo of
two premia that showed real net-of-cost edge (cross-asset TREND + cross-sectional MOMENTUM) -- runs
it through the FULL gauntlet, tracks live out-of-sample performance vs backtest, and emits today's
TARGET PORTFOLIO (per MT5 instrument). That target file is exactly what the rebalancer + EABridge +
QuantPlatformExecutor.mq5 consume; the EA only executes it. No capital is allocated. Promotion to
tiny live requires the pre-committed rule in docs/KILL_THESIS.md + human approval.

Frozen (pre-registered, never re-optimized): trend lookback=100, momentum lookback=120, q=0.3.

    python scripts/run_crossasset_shadow.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import campaign_gate_stats, validate
from libs.data.cleaning import DEFAULT_CAPS, guard_close
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.research.crossasset import (
    combine_weights,
    trend_basket_returns,
    trend_basket_weights,
    xsec_momentum_returns,
    xsec_momentum_weights,
)
from libs.research.event_density import forward_verdict
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_COVERAGE = Path("reports/multiasset_coverage.json")
_OUT = Path("reports/mt5_crossasset_shadow")
_WEB = Path("web/crossasset_shadow.json")
_TARGET = Path("data/target_portfolio.json")
_STATE = Path("data/crossasset_shadow_state.json")
_PPY = 252.0
_FROZEN = {"trend_lb": 100, "mom_lb": 120, "q": 0.3, "band": 0.05}   # pre-registered
_COST = {"fx": 1.0e-4, "metal": 2.0e-4, "energy": 2.5e-4,
         "index": 1.0e-4, "crypto": 6.0e-4, "equity": 2.0e-4}
_FAIL = ["trend/momentum premia compress or crowd", "regime shift (trend->chop)",
         "correlated cross-asset drawdown", "broker cost exceeds edge", "edge decay"]


def _load() -> tuple[pd.DataFrame, dict[str, float], dict[str, str]]:
    cov = json.loads(_COVERAGE.read_text("utf-8"))
    lake = ParquetLake("data/lake")
    closes, cost, klass = {}, {}, {}
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
        klass[sym] = ac
    close = pd.DataFrame(closes).sort_index()
    caps = {s: DEFAULT_CAPS.get(klass[s], 0.5) for s in close.columns}
    close = guard_close(close, caps)                     # gap-guard before emitting target weights
    return close, cost, klass


def _ann(r: np.ndarray) -> float:
    a = r[r != 0.0]
    return round(float(sharpe_ratio(a) * np.sqrt(_PPY)), 2) if len(a) > 5 else 0.0


def _verdict(fwd_days: int, fwd: float, bt: float) -> str:
    """EVIDENCE, NOT CALENDAR (L1.48) -- shared gate, so five runners cannot drift apart."""
    return forward_verdict(fwd_days, fwd, bt, periods_per_year=_PPY)


def main() -> None:
    close, cost, klass = _load()
    if close.shape[1] < 6:
        raise SystemExit("need the multi-asset lake; run scripts/ingest_multiasset.py first")
    tlb, mlb, q, band = (_FROZEN["trend_lb"], _FROZEN["mom_lb"], _FROZEN["q"], _FROZEN["band"])

    r_trend = trend_basket_returns(close, cost, lookback=tlb, band=band)
    r_mom = xsec_momentum_returns(close, cost, lookback=mlb, q=q, band=band)
    r_combo = 0.5 * r_trend + 0.5 * r_mom

    # Gauntlet on the combo (peers = the two sub-books for the multiplicity stats)
    matrix = np.column_stack([r_trend, r_mom, r_combo])
    sharpes = np.array([sharpe_ratio(x[x != 0.0]) for x in (r_trend, r_mom, r_combo)])
    # per-candidate gates (gap #87 flip, principal-ruled 2026-07-29); thresholds unchanged
    campaign = campaign_gate_stats(matrix)
    active = r_combo[r_combo != 0.0]
    verdict_gauntlet = validate(
        active, hypothesis=Hypothesis(
            family=Family.CROSS_ASSET, subtype="trend+momentum combo", symbol="MT5_XASSET",
            params={}, mechanism=MechanismType.RISK_PREMIUM,
            edge_source="cross-asset trend + x-sec momentum (equal risk, costed)",
            failure_modes=_FAIL), n_trials=3, sharpe_estimates=sharpes,
        returns_matrix=matrix, campaign=campaign, column=2)  # r_combo = matrix column 2

    # Forward shadow split
    dates = close.index
    state = json.loads(_STATE.read_text("utf-8")) if _STATE.exists() else {}
    if "shadow_start" not in state:
        state["shadow_start"] = dates[-1].isoformat()
    # RECORD THE RUN, every pass. The file used to be written only on the first run, so a clock
    # scheduled daily left no trace of having run and check_organ_liveness -- which reads this
    # artifact's mtime against the declared cadence -- reported STALE even immediately after a
    # successful pass. That is how this clock sat dead for 42 days while still consuming one of
    # the 12 capped Holm slots. shadow_start is NOT touched: it anchors the forward/backtest
    # split, so rewriting it would silently move the in-sample boundary.
    state["last_run"] = datetime.now(tz=UTC).isoformat()
    state["last_run_rows"] = len(dates)
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(state, indent=1), "utf-8")
    shadow_start = pd.Timestamp(state["shadow_start"])
    is_fwd = dates >= shadow_start
    bt_sharpe, fwd_sharpe = _ann(r_combo[~is_fwd]), _ann(r_combo[is_fwd])
    fwd_days = int(np.sum(r_combo[is_fwd] != 0.0))

    # Today's TARGET PORTFOLIO (the brain's decision -> executor -> EA). Snapshot each instrument at
    # its latest available close (ffill) so a weekend bar -- when only crypto CFDs trade -- does not
    # collapse the book to crypto-only. ffill is for the as-of snapshot ONLY; returns stay unfilled.
    close_asof = close.ffill()
    w_trend = trend_basket_weights(close_asof, lookback=tlb)
    w_mom = xsec_momentum_weights(close_asof, lookback=mlb, q=q)
    target = combine_weights(w_trend, w_mom)
    target_payload = {
        "strategy": "mt5_crossasset_trend_momentum_combo",
        "as_of": dates[-1].date().isoformat(),
        "generated": datetime.now(tz=UTC).isoformat(),
        "deployable": bool(verdict_gauntlet.survived),
        "note": "SHADOW target weights (zero capital). Execution requires human approval per "
                "docs/KILL_THESIS.md; the EA only executes an approved target.",
        "weights": {k: round(v, 4) for k, v in sorted(target.items(),
                                                       key=lambda kv: -abs(kv[1]))},
    }

    equity = np.cumprod(1.0 + r_combo)
    n = len(equity)
    step = max(1, n // 300)
    curve = [{"t": dates[i].date().isoformat(), "v": round(float(equity[i]), 4),
              "fwd": bool(is_fwd[i])} for i in range(0, n, step)]
    web = {
        "strategy": "MT5 cross-asset (trend+momentum combo, frozen)",
        "shadow_start": state["shadow_start"], "symbols": close.shape[1],
        "backtest_ann_sharpe": bt_sharpe, "forward_ann_sharpe": fwd_sharpe,
        "forward_days": fwd_days,
        "gates_passed": f"{sum(verdict_gauntlet.gates.values())}/{len(verdict_gauntlet.gates)}",
        "deployable": bool(verdict_gauntlet.survived),
        "verdict": _verdict(fwd_days, fwd_sharpe, bt_sharpe),
        "updated": datetime.now(tz=UTC).isoformat(), "equity": curve,
        "target_weights": target_payload["weights"],
    }

    _OUT.mkdir(parents=True, exist_ok=True)
    (_OUT / "report.json").write_text(json.dumps(web, indent=2), "utf-8")
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps(web, indent=2), "utf-8")
    _TARGET.parent.mkdir(parents=True, exist_ok=True)
    _TARGET.write_text(json.dumps(target_payload, indent=2), "utf-8")

    print(f"cross-asset combo: bt_sharpe={bt_sharpe} fwd_sharpe={fwd_sharpe} "
          f"gates={web['gates_passed']} deployable={web['deployable']}")
    print(f"gauntlet: {verdict_gauntlet.rejection_reason or 'PASSED'}")
    print(f"verdict: {web['verdict']}")
    print(f"target weights ({len(target)} instruments) -> {_TARGET}:")
    for k, v in target_payload["weights"].items():
        print(f"  {k:8} {klass.get(k,'?'):7} {v:+.4f}")


if __name__ == "__main__":
    main()
