"""GEOMETRIC GROWTH REVIEW -- wires the desk's stated supreme objective to a runnable entry point.

THE DEFECT THIS CLOSES. The desk's supreme objective is E[log wealth], and `libs/discovery`
ships the engines that optimise exactly that -- objective.py ("expected log utility (geometric
growth), not backtest CAGR"), portfolio_geometry.py ("the portfolio's *geometry* is what
compounds"), cagr_optimizer.py ("maximises geometric growth ... then scales exposure DOWN until
survival > 95%"). All 23 modules were imported by ZERO scripts/ entry points. The objective
function was dead code while every screen ranked on Sharpe, which is not the thing that
compounds: two sleeves with identical Sharpe can have materially different E[log(1+r)] once
drawdown path and convexity differ, and it is the log term that decides terminal wealth.

WHAT THIS DOES, per the GROWTH_UNLOCK_LADDER's own arithmetic ("by STACKING VALIDATED SLEEVES
(sqrt-N Sharpe growth), never by levering one unproven sleeve harder"):
  1. per-sleeve annualised expected log growth          -- objective.expected_log_growth
  2. portfolio compounding geometry of the combined book -- portfolio_geometry (recovery,
     convexity, diversification ratio, geometric growth)
  3. the allocation that maximises SURVIVABLE geometric growth -- cagr_optimizer, which scales
     exposure down until survival > 95% and dd < 20% and never levers past the risk limit
  4. a composite discovery rank -- objective.discovery_score

ZERO PROMOTION AUTHORITY. This reports; the Two-Stage Discovery Law is untouched -- promotion
still happens only from pre-registered FORWARD evidence, Holm-corrected over concurrent slots.
Nothing here loosens a rail: kelly_cap, dd_limit and survival_min are passed through from
config/risk.yaml's stated mandate (kelly_fraction_max 0.25) rather than invented locally.

`--self-test` proves the wiring end-to-end on synthetic sleeves, so the engines are exercised
even on a checkout with no live return series (data/ is gitignored). Run from repo root.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from libs.discovery.cagr_optimizer import optimize_allocation
from libs.discovery.objective import (
    discovery_score,
    expected_log_growth,
)
from libs.discovery.portfolio_geometry import portfolio_geometry

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/geometric_review.json"
SLEEVES = ROOT / "data/shadow_sleeves.json"
PPY = 365.0                      # crypto trades every day; matches the screens' _PPY
KELLY_CAP = 0.25                 # config/risk.yaml kelly_fraction_max -- CRO mandate, not local


def load_sleeves() -> dict[str, np.ndarray]:
    """Return series per live sleeve. Accepts either {id: [...]} or {id: {returns: [...]}}."""
    try:
        raw = json.loads(SLEEVES.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, np.ndarray] = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            series = v.get("returns") if isinstance(v, dict) else v
            if isinstance(series, list) and len(series) >= 10:
                out[str(k)] = np.asarray(series, dtype="float64")
    return out


def synthetic_sleeves(seed: int = 11) -> dict[str, np.ndarray]:
    """Three sleeves with deliberately DIFFERENT geometry at similar Sharpe.

    The point of the self-test is not that numbers appear -- it is that the ranking by log
    growth differs from the ranking by Sharpe. If they never diverged, wiring the objective
    would be ceremony.
    """
    rng = np.random.default_rng(seed)
    n = 600
    smooth = rng.normal(0.0010, 0.010, n)                      # steady
    lumpy = rng.normal(0.0016, 0.020, n)                       # higher mean, twice the vol
    lumpy[rng.integers(0, n, 12)] -= 0.11                      # fat left tail -> log punishes it
    slow = rng.normal(0.0007, 0.008, n)
    return {"carry_smooth": smooth, "momo_lumpy": lumpy, "basis_slow": slow}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true",
                    help="run on synthetic sleeves to prove the engines are wired")
    args = ap.parse_args()

    sleeves = synthetic_sleeves() if args.self_test else load_sleeves()
    src = "SYNTHETIC (self-test)" if args.self_test else str(SLEEVES.relative_to(ROOT))
    print("=== GEOMETRIC GROWTH REVIEW -- E[log wealth], not backtest CAGR ===")
    print(f"    source: {src}\n")
    if not sleeves:
        print("  no sleeve return series available -- nothing to review.")
        print("  (run with --self-test to exercise the engines without live data)")
        return

    # ---- 1. per-sleeve log growth (the quantity that actually compounds)
    rows = []
    for name, r in sorted(sleeves.items()):
        g = expected_log_growth(r, periods_per_year=PPY)
        sharpe = float(np.mean(r) / (np.std(r, ddof=1) + 1e-12) * np.sqrt(PPY))
        eq = np.cumprod(1.0 + r)
        dd = float((1.0 - eq / np.maximum.accumulate(eq)).max())
        rows.append({"sleeve": name, "log_growth": round(g, 4), "sharpe": round(sharpe, 3),
                     "max_dd": round(dd, 4), "n": len(r)})
    by_growth = [x["sleeve"] for x in sorted(rows, key=lambda x: -x["log_growth"])]
    by_sharpe = [x["sleeve"] for x in sorted(rows, key=lambda x: -x["sharpe"])]

    print(f"  {'sleeve':<18}{'log_growth':>12}{'sharpe':>10}{'max_dd':>10}")
    for x in sorted(rows, key=lambda x: -x["log_growth"]):
        print(f"  {x['sleeve']:<18}{x['log_growth']:>12.4f}"
              f"{x['sharpe']:>10.3f}{x['max_dd']:>10.4f}")
    if by_growth != by_sharpe:
        print(f"\n  ** RANKING DIVERGES: by log growth {by_growth} vs by Sharpe {by_sharpe}")
        print("     Sharpe is not what compounds -- this divergence is the whole reason the")
        print("     objective engine exists, and it was previously unreachable.")

    # ---- 2. portfolio compounding geometry (equal-weight book as the baseline)
    length = min(len(r) for r in sleeves.values())
    matrix = np.column_stack([r[-length:] for r in sleeves.values()])
    book = matrix.mean(axis=1)
    geo = portfolio_geometry(book, periods_per_year=PPY)
    print(f"\n  PORTFOLIO GEOMETRY  score={geo.portfolio_geometry_score:.1f}/100  "
          f"growth={geo.geometric_growth:.4f}  dd={geo.max_drawdown:.4f}  "
          f"recovery={geo.recovery_periods:.1f}p  convexity={geo.convexity:.3f}")

    # ---- 3. allocation for maximum SURVIVABLE geometric growth (rails passed through)
    alloc = None
    try:
        opt = optimize_allocation({k: v[-length:] for k, v in sleeves.items()},
                                  periods_per_year=PPY, kelly_cap=KELLY_CAP)
        alloc = json.loads(opt.model_dump_json())
        w = alloc.get("weights") or {}
        print(f"  ALLOCATION (kelly_cap={KELLY_CAP}, survival>=95%, dd<20%): "
              + ", ".join(f"{k}={float(v):.3f}" for k, v in w.items()))
        print(f"    leverage={alloc.get('leverage'):.3f} "
              f"E[log growth]={alloc.get('expected_log_growth'):.4f} "
              f"survival={alloc.get('survival_probability'):.3f} "
              f"worst_dd={alloc.get('worst_case_drawdown'):.4f} passed={alloc.get('passed')}")
        # An all-zero book is a VERDICT, not a null result: the optimiser scales exposure down
        # until survival clears, so zero means no allocation of this book survives the rails.
        # Printing it without the reason would look like a bug and get ignored.
        if all(float(v) == 0.0 for v in w.values()):
            worst = min(rows, key=lambda x: x["log_growth"])
            print("    ALL-ZERO: no exposure to this book survives the rails. Dominant drag is "
                  f"{worst['sleeve']} (log_growth={worst['log_growth']}, "
                  f"max_dd={worst['max_dd']}). Drop or de-weight it and re-run -- this is the "
                  "optimiser refusing ruin, not a failure to solve.")
    except Exception as e:                                     # engines raise on thin/degenerate
        print(f"  ALLOCATION unavailable: {type(e).__name__}: {str(e)[:90]}")

    # ---- 4. composite discovery rank. Unknown robustness inputs are declared NEUTRAL, never
    # guessed favourably -- an optimistic default here would silently inflate the rank of a
    # sleeve nobody has stress-tested.
    for x in rows:
        x["discovery_score"] = round(discovery_score(
            log_growth=x["log_growth"], survival_probability=0.95,
            diversification_contribution=0.0, average_correlation=0.0,
            failure_dependency_score=50.0, half_life_days=90.0, capacity_usd=250_000.0,
            fragility_score=50.0, tail_risk_score=50.0, parameter_plateau_score=50.0), 5)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(
        {"ran": datetime.now(tz=UTC).isoformat(), "source": src, "periods_per_year": PPY,
         "sleeves": rows, "rank_by_log_growth": by_growth, "rank_by_sharpe": by_sharpe,
         "ranking_diverges": by_growth != by_sharpe,
         "portfolio_geometry": json.loads(geo.model_dump_json()), "allocation": alloc,
         "note": ("Reports only. Promotion remains governed by the Two-Stage Discovery Law: "
                  "pre-registered FORWARD evidence, Holm-corrected over concurrent slots.")},
        indent=1), "utf-8")
    print(f"\n  -> {OUT.relative_to(ROOT)}")
    print("  ZERO promotion authority -- forward evidence still decides, this only ranks.")


if __name__ == "__main__":
    main()
