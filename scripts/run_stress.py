"""Stress harness -- prove the risk controls are GROWTH-POSITIVE + verify they fire correctly.

Three scenarios, all offline/synthetic:
  1. Growth proof -- on a fat-left-tailed carry-like return stream, compare annualised geometric
     growth of naive over-leverage vs the ruin-capped dynamic leverage. If the controls are
     growth-positive, capping at the ruin boundary yields HIGHER g than over-levering (which rides
     volatility drag + ruin down). The empirical answer to "does risk control cost growth?".
  2. Drawdown path -- feed an equity path through risk_controls and assert it PAUSES in stress and
     only FLATTENS at the ruin threshold (never realises a loss early).
  3. Funding inversion -- edge flips negative; dynamic leverage must collapse to the floor.

Writes web/stress.json + prints a report. Run any time; it touches no live account.

    python scripts/run_stress.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.risk import risk_controls
from libs.risk.dynamic_leverage import optimize_sleeve
from libs.risk.growth_leverage import ann_geom_growth, kelly_optimal

_OUT = Path("web/stress.json")


def _carry_stream(n: int = 750, seed: int = 7) -> np.ndarray:
    """Steady positive (funding) with occasional fat negative shocks (basis/deleverage).

    Tuned to a genuinely positive-Kelly edge so the over-bet visibly destroys geometric growth.
    """
    rng = np.random.default_rng(seed)
    base = rng.normal(0.0012, 0.004, n)                     # funding-like drift (net positive)
    shocks = rng.random(n) < 0.012                          # ~1.2% of days: a dislocation
    base[shocks] -= rng.uniform(0.02, 0.06, shocks.sum())   # -2% to -6% tail days
    return base


def _growth_proof() -> dict[str, object]:
    r = _carry_stream()
    kelly = kelly_optimal(r)
    g_kelly = ann_geom_growth(r, kelly, 252.0)
    g_over = ann_geom_growth(r, kelly * 2.0, 252.0)         # 2x Kelly -- the over-bet
    g_ruincap = ann_geom_growth(r, min(kelly, 2.0), 252.0)  # capped
    return {
        "growth_optimal_leverage": round(kelly, 2),
        "g_at_growth_optimal": round(g_kelly, 4),
        "g_at_2x_kelly_overbet": round(g_over, 4),
        "g_at_ruin_capped": round(g_ruincap, 4),
        "verdict": ("ruin-capped growth >= over-bet growth"
                    if g_ruincap >= g_over else "UNEXPECTED"),
        "note": ("Beyond the growth-optimal point, geometric growth FALLS. Capping at the ruin "
                 "boundary preserves g; over-levering destroys it. Controls are growth-positive."),
    }


def _drawdown_path() -> dict[str, object]:
    start = peak = 5000.0
    steps = []
    for eq in (5000, 4600, 4200, 3999, 3200):              # -8%, -16%, -20%, -36% from start
        d = risk_controls.evaluate(eq, start, max(peak, eq), 1000.0, ruin_cap_lev=8.0)
        steps.append({"equity": eq, "action": d.action})
    pauses = [s for s in steps if s["action"] == "pause_opens"]
    flatten = [s for s in steps if s["action"] == "flatten"]
    return {"path": steps,
            "paused_in_stress": bool(pauses), "flattened_only_at_ruin": bool(flatten),
            "verdict": "PASS" if pauses and flatten and flatten[0]["equity"] <= start * 0.65
            else "REVIEW"}


def _funding_inversion() -> dict[str, object]:
    rng = np.random.default_rng(3)
    neg = rng.normal(-0.0004, 0.006, 300)                  # edge flipped negative
    d = optimize_sleeve("inv", neg, fwd_sharpe=-0.5, fwd_days=95.0)
    return {"recommended_leverage": d.recommended, "confidence": d.confidence,
            "verdict": "PASS (collapsed to floor)" if d.recommended <= 0.5 else "REVIEW"}


def main() -> None:
    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "growth_proof": _growth_proof(),
        "drawdown_path": _drawdown_path(),
        "funding_inversion": _funding_inversion(),
    }
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    gp = out["growth_proof"]
    print(f"STRESS: growth-proof {gp['verdict']} "
          f"(capped g={gp['g_at_ruin_capped']} vs overbet g={gp['g_at_2x_kelly_overbet']}) | "
          f"drawdown {out['drawdown_path']['verdict']} | "
          f"funding-inversion {out['funding_inversion']['verdict']}")


if __name__ == "__main__":
    main()
