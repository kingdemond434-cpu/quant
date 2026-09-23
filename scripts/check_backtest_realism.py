"""A published framework's bug list, run as a standing audit against our own engine.

WHY THIS EXISTS (2026-08-29, from inspecting alpha-search v0.2.2's release notes)

`alpha-search` ships a five-agent swarm -- DataEngineer, QuantEngineer, RiskManager, Research,
Opportunity -- with critique loops and consensus sign-off. Its v0.2.2 fixes are the interesting
part, and they are not sophisticated at all:

    "costs now use portfolio notional value (was per-share, underestimating costs ~1000x)"
    "QuantEngineerAgent now runs real BacktestEngine backtests (was random simulation)"
    "position signals clipped to [-1, 1] (prevents >100% leverage)"
    "RSI now uses Wilder's EMA" with divide-by-zero guards
    "drawdown unified to negative convention"

A thousand-fold cost error and an agent grading RANDOM NUMBERS, underneath a multi-agent
architecture. Every result that framework produced before v0.2.2 was noise wearing a consensus
sign-off, and no amount of orchestration above it could have noticed -- the agents were arguing
about fabricated evidence.

THAT IS THE STEAL. Not their architecture: their failure list, turned into assertions about OUR
engine. These are the cheapest possible checks and they guard the load-bearing floor everything
else stands on. This desk has already been bitten by two of the five -- the `spread_per_lot` unit
trap is documented in `engine.py` as "THE WHOLE TRAP, AND IT COST THIS DESK A LOT", and the
fill-hour cost defect found earlier today was the same family of error one level up.

WHY IT RUNS ON A CLOCK rather than being a one-off review: a cost model is edited more often than
it is audited, and the failure is silent by construction. A backtest with 1000x-understated costs
does not crash, does not warn, and produces beautiful equity curves -- it is indistinguishable
from success until real money meets it.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
OUT = ROOT / "data" / "backtest_realism.json"
sys.path.insert(0, str(DESK))


def _check_cost_scales_with_notional() -> dict[str, Any]:
    """Doubling contract size must roughly double the round-trip cost.

    alpha-search's headline bug: costs charged per SHARE rather than on notional, which is a
    ~1000x understatement on any instrument whose contract is not one unit. On this desk the same
    error appears as `spread_per_lot` holding raw points instead of points x contract size.
    """
    try:
        from mt5desk.engine import Costs
    except Exception as exc:
        return {"check": "cost_scales_with_notional", "verdict": "UNMEASURED",
                "detail": f"cannot import Costs: {type(exc).__name__}: {exc}"}

    small = Costs(spread_per_lot=16.0, commission_per_lot=2.25, contract_oz=100.0)
    big = Costs(spread_per_lot=160.0, commission_per_lot=22.5, contract_oz=1000.0)
    try:
        cs, cb = small.per_oz_roundtrip(), big.per_oz_roundtrip()
    except Exception as exc:
        return {"check": "cost_scales_with_notional", "verdict": "UNMEASURED",
                "detail": f"per_oz_roundtrip raised {type(exc).__name__}: {exc}"}
    if cs <= 0:
        return {"check": "cost_scales_with_notional", "verdict": "FAIL",
                "detail": f"a round trip costs {cs} -- a free trade is the 1000x error's endpoint"}
    ratio = cb / cs
    ok = 5.0 <= ratio <= 20.0
    return {"check": "cost_scales_with_notional",
            "verdict": "PASS" if ok else "FAIL",
            "detail": (f"10x the per-lot figures gives {ratio:.2f}x the round-trip cost "
                       f"({cs:.4f} -> {cb:.4f}). A ratio near 1 means cost is not tracking "
                       f"notional, which is exactly alpha-search's ~1000x understatement.")}


def _check_costs_are_charged() -> dict[str, Any]:
    """A zero-cost run must beat a costed run. If it does not, costs are not reaching the P&L.

    This is the quiet form of alpha-search's "agent grades random simulation": a cost model that
    is computed and then never subtracted looks identical to a correct one in every log line.
    """
    try:
        import numpy as np
        import pandas as pd
        from mt5desk.engine import Costs, Signal, run_backtest
    except Exception as exc:
        return {"check": "costs_reach_pnl", "verdict": "UNMEASURED",
                "detail": f"import failed: {type(exc).__name__}: {exc}"}

    n = 600
    idx = pd.date_range("2025-01-01", periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(11)
    close = pd.Series(2000 + np.cumsum(rng.normal(0, 2.0, n)), index=idx)
    df = pd.DataFrame({"open": close, "high": close + 3.0, "low": close - 3.0,
                       "close": close}, index=idx)
    sigs = [Signal(time=idx[i], side=1, stop=float(close.iloc[i]) - 5.0,
                   target=float(close.iloc[i]) + 5.0, ttl_bars=6, tag="realism")
            for i in range(0, n - 10, 20)]

    try:
        free = run_backtest(df, sigs, Costs(spread_per_lot=0.0, commission_per_lot=0.0,
                                            contract_oz=100.0))
        paid = run_backtest(df, sigs, Costs(spread_per_lot=4000.0, commission_per_lot=2000.0,
                                            contract_oz=100.0))
    except Exception as exc:
        return {"check": "costs_reach_pnl", "verdict": "UNMEASURED",
                "detail": f"run_backtest raised {type(exc).__name__}: {str(exc)[:110]}"}

    f_exp = free.stats()["expectancy_r"]
    p_exp = paid.stats()["expectancy_r"]
    if free.n == 0:
        return {"check": "costs_reach_pnl", "verdict": "UNMEASURED",
                "detail": "the synthetic frame produced no fills; the check proved nothing"}
    ok = p_exp < f_exp
    return {"check": "costs_reach_pnl", "verdict": "PASS" if ok else "FAIL",
            "detail": (f"over {free.n} fills: zero-cost exp_r {f_exp:+.5f} vs heavily-costed "
                       f"{p_exp:+.5f}. Costs that do not reduce expectancy are computed and "
                       f"discarded -- indistinguishable from correct in every log line.")}


def _check_drawdown_sign() -> dict[str, Any]:
    """Drawdown must be negative everywhere. A mixed convention silently inverts comparisons."""
    hits, mixed = [], []
    for p in (DESK / "mt5desk" / "engine.py", DESK / "research" / "forward_verdict.py"):
        if not p.exists():
            continue
        src = p.read_text("utf-8")
        if "max_dd" not in src:
            continue
        hits.append(str(p.relative_to(ROOT)))
        if "abs(max_dd" in src or "max_dd = abs(" in src:
            mixed.append(str(p.relative_to(ROOT)))
    return {"check": "drawdown_sign_convention",
            "verdict": "FAIL" if mixed else ("PASS" if hits else "UNMEASURED"),
            "detail": (f"abs() applied to a drawdown in {mixed}" if mixed else
                       f"negative convention held across {len(hits)} module(s): {hits}. A mixed "
                       f"convention makes `dd > -25` true for a 30R loss.")}


def _check_single_position_discipline() -> dict[str, Any]:
    """No overlapping positions -- the desk's equivalent of clipping signals to [-1, 1]."""
    p = DESK / "mt5desk" / "engine.py"
    if not p.exists():
        return {"check": "no_leverage_stacking", "verdict": "UNMEASURED",
                "detail": "engine.py absent"}
    src = p.read_text("utf-8")
    ok = "last_exit_idx" in src and "single-position" in src
    return {"check": "no_leverage_stacking", "verdict": "PASS" if ok else "FAIL",
            "detail": ("engine enforces single-position discipline (`last_exit_idx`), so signals "
                       "cannot stack into >100% exposure -- alpha-search shipped unclipped "
                       "positions until v0.2.2"
                       if ok else
                       "no single-position guard found; overlapping entries can compound exposure")}


def _check_no_random_evaluation() -> dict[str, Any]:
    """Nothing in the validation path may fabricate results.

    alpha-search's QuantEngineerAgent returned RANDOM NUMBERS where a backtest belonged, and a
    five-agent consensus signed off on them. Any `random` in a validator is that bug's habitat.
    """
    offenders = []
    for rel in ("desks/mt5/mt5desk/engine.py", "desks/mt5/scripts/external_gauntlet.py",
                "desks/mt5/research/forward_verdict.py", "desks/mt5/research/shadow_forward.py"):
        p = ROOT / rel
        if not p.exists():
            continue
        src = p.read_text("utf-8")
        for marker in ("random.random(", "np.random.rand", "default_rng().normal",
                       "random.gauss("):
            if marker in src:
                offenders.append({"file": rel, "marker": marker})
    return {"check": "no_fabricated_evaluation",
            "verdict": "FAIL" if offenders else "PASS",
            "detail": (offenders if offenders else
                       "no random generator in the validation path. A validator that can "
                       "fabricate a result produces beautiful curves and is indistinguishable "
                       "from success until real money meets it.")}


def main() -> int:
    now = datetime.now(tz=UTC)
    checks = [
        _check_cost_scales_with_notional(),
        _check_costs_are_charged(),
        _check_drawdown_sign(),
        _check_single_position_discipline(),
        _check_no_random_evaluation(),
    ]
    failed = [c for c in checks if c["verdict"] == "FAIL"]
    unmeasured = [c for c in checks if c["verdict"] == "UNMEASURED"]

    print(f"BACKTEST REALISM {now.isoformat(timespec='seconds')}")
    print("  source: alpha-search v0.2.2 release notes, turned into assertions about OUR engine")
    for c in checks:
        mark = {"PASS": "ok  ", "FAIL": "FAIL", "UNMEASURED": "????"}[c["verdict"]]
        print(f"  {mark} {c['check']}")
        if c["verdict"] != "PASS":
            print(f"       {str(c['detail'])[:150]}")
    OUT.write_text(json.dumps({"checked_at": now.isoformat(timespec="seconds"),
                               "checks": checks}, indent=1, default=str), "utf-8")
    print(f"\n  {len(checks) - len(failed) - len(unmeasured)} pass, {len(failed)} fail, "
          f"{len(unmeasured)} unmeasured")
    print(f"  -> {OUT}")
    # UNMEASURED counts as failure here. A realism check that cannot run is the same blind spot,
    # and "the signature changed so we skipped it" is how the floor rots unnoticed.
    return 1 if (failed or unmeasured) else 0


if __name__ == "__main__":
    raise SystemExit(main())
