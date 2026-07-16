"""Alpha Campaign 1 — run the pre-registered hypotheses on real MT5 demo data.

Connects to the MetaTrader5 terminal READ-ONLY (demo accounts only; aborts on a real account),
pulls real history per symbol, backtests each pre-registered strategy with pessimistic costs and
strict lag-1 (no lookahead), then runs the full validation stack: Sharpe, Deflated Sharpe (trials-
deflated), PBO, White's Reality Check, and Walk-Forward governance. Writes the five campaign
reports. NO orders, NO capital, NO threshold weakening, NO manual intervention, NO survivorship
bias (every candidate is reported). Survivors, if any, are only flagged for shadow/paper.

Usage: python scripts/run_campaign.py [--bars 6000] [--symbols EURUSD,XAUUSD,US500]
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from app.signal_builder import STRATEGIES, Bars, strategy_returns
from libs.validation.dsr import deflated_sharpe_ratio, sharpe_ratio
from libs.validation.pbo import probability_backtest_overfitting
from libs.validation.reality_check import whites_reality_check
from libs.validation.revalidation import WalkForwardEngine, WalkForwardStatus

_PERIODS_PER_YEAR = 24 * 260  # H1 bars
_COST_PER_TURNOVER = 0.0003   # pessimistic round-turn friction (~3 bps)
_DSR_THRESHOLD = 0.95
_MIN_OOS_STABILITY = 0.5
_OUT = Path("reports/campaign1")


def _connect_demo() -> object:
    import MetaTrader5 as mt5

    if not mt5.initialize():
        raise SystemExit(f"MT5 initialize failed: {mt5.last_error()}")
    acct = mt5.account_info()
    if acct is None:
        raise SystemExit("MT5 account_info unavailable; log into a DEMO account first")
    if int(acct.trade_mode) != 0:  # 0 = ACCOUNT_TRADE_MODE_DEMO
        mt5.shutdown()
        raise SystemExit(f"refusing to run on non-demo account (trade_mode={acct.trade_mode})")
    print(f"connected: server={acct.server} trade_mode=DEMO currency={acct.currency}")
    return mt5


def _fetch(mt5: object, symbol: str, count: int) -> Bars | None:
    mt5.symbol_select(symbol, True)  # type: ignore[attr-defined]
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, count)  # type: ignore[attr-defined]
    if rates is None or len(rates) < 500:
        return None
    return Bars(
        close=np.array([r["close"] for r in rates], dtype="float64"),
        high=np.array([r["high"] for r in rates], dtype="float64"),
        low=np.array([r["low"] for r in rates], dtype="float64"),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=int, default=6000)
    parser.add_argument("--symbols", default="EURUSD,XAUUSD,US500")
    args = parser.parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]

    mt5 = _connect_demo()
    bars_by_symbol: dict[str, Bars] = {}
    for sym in symbols:
        b = _fetch(mt5, sym, args.bars)
        if b is None:
            print(f"  [skip] {sym}: no data on this terminal")
        else:
            bars_by_symbol[sym] = b
            print(f"  [data] {sym}: {len(b)} H1 bars")
    mt5.shutdown()  # type: ignore[attr-defined]
    if not bars_by_symbol:
        raise SystemExit("no data for any requested symbol")

    # --- backtest every pre-registered (strategy x symbol) candidate ---
    candidates: list[dict[str, object]] = []
    return_series: list[np.ndarray] = []
    for sym, bars in bars_by_symbol.items():
        for name, (fn, mechanism, why) in STRATEGIES.items():
            rets = strategy_returns(bars, fn(bars), cost_per_turnover=_COST_PER_TURNOVER)
            return_series.append(rets)
            candidates.append({
                "id": f"{name}:{sym}", "strategy": name, "symbol": sym,
                "mechanism": mechanism.value, "why": why, "returns": rets,
            })

    n_trials = len(candidates)
    min_len = min(len(r) for r in return_series)
    matrix = np.column_stack([r[-min_len:] for r in return_series])  # T x N, aligned
    per_trial_sharpes = np.array([sharpe_ratio(r) for r in return_series], dtype="float64")

    # --- program-level guards (selection-aware) ---
    pbo = probability_backtest_overfitting(matrix) if n_trials >= 2 else None
    reality = whites_reality_check(matrix) if n_trials >= 2 else None
    pbo_ok = pbo is None or not pbo.overfit
    reality_ok = reality is not None and reality.significant_at_5pct

    wfe = WalkForwardEngine()
    survivors: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []
    for cand in candidates:
        rets = cand["returns"]  # type: ignore[assignment]
        ann_sharpe = float(sharpe_ratio(rets) * np.sqrt(_PERIODS_PER_YEAR))
        ev = float(np.mean(rets))
        test_size = max(20, len(rets) // 6)
        wf = wfe.evaluate(rets, n_splits=4, test_size=test_size,
                          min_oos_sharpe=0.0, min_stability=_MIN_OOS_STABILITY)
        dsr = deflated_sharpe_ratio(rets, n_trials=n_trials, sharpe_estimates=per_trial_sharpes,
                                    threshold=_DSR_THRESHOLD)
        gates = {
            "ev_positive": ev > 0,
            "walk_forward_passed": wf.status is WalkForwardStatus.PASSED,
            "dsr_passed": dsr.passed,
            "reality_check_passed": reality_ok,
            "pbo_acceptable": pbo_ok,
        }
        record = {
            "id": cand["id"], "strategy": cand["strategy"], "symbol": cand["symbol"],
            "mechanism": cand["mechanism"], "why": cand["why"],
            "annual_sharpe": round(ann_sharpe, 3), "expected_value_per_bar": ev,
            "oos_sharpe": round(wf.oos_sharpe, 3), "oos_stability": round(wf.stability, 3),
            "dsr": round(dsr.dsr, 3), "gates": gates, "survived": all(gates.values()),
        }
        (survivors if record["survived"] else rejected).append(record)

    _write_reports(candidates, survivors, rejected, pbo, reality, n_trials)
    print(f"\nCAMPAIGN 1 COMPLETE: {len(survivors)} survivors / {n_trials} candidates")
    if not survivors:
        print("ZERO SURVIVORS — no pre-registered hypothesis cleared institutional validation.")
    for s in survivors:
        print(f"  SURVIVOR: {s['id']} annual_sharpe={s['annual_sharpe']} dsr={s['dsr']}")


def _write_reports(
    candidates: list[dict[str, object]], survivors: list[dict[str, object]],
    rejected: list[dict[str, object]], pbo: object, reality: object, n_trials: int,
) -> None:
    _OUT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).isoformat()

    def clean(recs: list[dict[str, object]]) -> list[dict[str, object]]:
        return [{k: v for k, v in r.items() if k != "returns"} for r in recs]

    reality_sig = reality.significant_at_5pct if reality is not None else None
    reality_p = round(reality.p_value, 4) if reality is not None else None
    summary = {
        "generated_at": ts, "n_candidates": n_trials, "n_survivors": len(survivors),
        "n_rejected": len(rejected),
        "pbo": round(pbo.pbo, 3) if pbo is not None else None,
        "pbo_overfit": (pbo.overfit if pbo is not None else None),
        "reality_check_p_value": reality_p,
        "reality_check_significant": reality_sig,
        "cost_per_turnover": _COST_PER_TURNOVER, "dsr_threshold": _DSR_THRESHOLD,
    }
    all_recs = clean(survivors + rejected)
    (_OUT / "research_report.json").write_text(json.dumps(
        {"generated_at": ts, "candidates": [
            {"id": c["id"], "strategy": c["strategy"], "symbol": c["symbol"],
             "mechanism": c["mechanism"], "rationale": c["why"]} for c in candidates]},
        indent=2), "utf-8")
    (_OUT / "alpha_registry_report.json").write_text(json.dumps(
        {"generated_at": ts, "registered": all_recs}, indent=2), "utf-8")
    (_OUT / "survivors_report.json").write_text(json.dumps(
        {"generated_at": ts, "survivors": clean(survivors)}, indent=2), "utf-8")
    (_OUT / "rejected_report.json").write_text(json.dumps(
        {"generated_at": ts, "rejected": clean(rejected)}, indent=2), "utf-8")
    (_OUT / "campaign_summary.json").write_text(json.dumps(summary, indent=2), "utf-8")
    print(f"reports written to {_OUT}/")


if __name__ == "__main__":
    main()
