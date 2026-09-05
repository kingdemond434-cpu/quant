"""How fast can a prop evaluation be passed without lowering the odds of passing at all?

WHY THIS EXISTS (principal, 2026-08-29: "pass as fast as safely possible")

Speed and safety trade off through exactly one dial -- position size -- and the trade is not
linear, so intuition gets it wrong in both directions. This computes the frontier instead of
guessing at it.

THE MODEL. A prop evaluation is a BARRIER problem: the equity path must touch +target before it
touches -drawdown. Treat daily equity as Brownian motion with drift, which is a fair description
of a book of many small bracketed trades:

    mu_daily    = trades_per_day x expectancy_R x risk_frac
    sigma_daily = risk_frac x sqrt(n_eff_daily)

`n_eff_daily` rather than `trades_per_day` is the whole point of the variance term. Eleven trades
that cluster into 5.5 independent bets carry the variance of 5.5, not of 11, and this desk has
measured n_eff ~5.5 across 23 certificates. Using the raw trade count would understate risk by
about 40% and produce a recommendation that quietly breaches.

With lambda = 2*mu/sigma^2, the classical two-barrier result gives

    P(hit +a before -b) = (1 - e^(lambda*b)) / (e^(-lambda*a) - e^(lambda*b))
    E[days]             ~ a / mu_daily          (when drift dominates, which it must to pass)

WHY SMALLER IS SAFER AND SLOWER. Scaling risk by k scales mu by k and sigma by k, so lambda goes
as 1/k. Halving size roughly SQUARES the odds ratio in your favour while doubling the time. There
is no size at which you are both fast and safe; there is only a curve, and the honest job is to
show it rather than to name one number.

THE INPUT NOBODY HAS. Every row below is conditional on `expectancy_R`, and this desk has ZERO
completed forward windows. At 0.05R the frontier is comfortable; at 0.00R it is a coin flip
weighted by the barrier ratio and no sizing saves it. That sensitivity IS the finding -- it is
why the recommendation is to wait for the first cohort rather than to pick a row today.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desks" / "mt5"))
OUT = ROOT / "data" / "prop_settings.json"

#: Trades per day the whole book produces. Measured: ~8 trades per 12 days per sleeve across 17
#: sleeves. Raising this is the ONLY lever that improves speed and safety together, because it
#: lifts drift linearly and variance only as a square root.
TRADES_PER_DAY = 11.0

#: Independent bets per day. NOT the trade count -- see the module docstring. Measured n_eff.
N_EFF_DAILY = 5.5

#: Per-trade R volatility. A bracketed trade lands near -1R or +target, so 1.0 is the right
#: order; the frontier's shape is insensitive to this, its absolute level is not.
R_VOL = 1.0

#: Expectancies to show. 0.0 is included deliberately: it is the honest null, and seeing what the
#: frontier looks like when the edge is absent is more informative than any optimistic row.
EXPECTANCIES = (0.0, 0.02, 0.05, 0.08, 0.12)

#: Risk fractions to evaluate, as fractions of account equity per trade.
RISK_GRID = (0.0010, 0.0015, 0.0018, 0.0025, 0.0030, 0.0035, 0.0040, 0.0050, 0.0070, 0.0100)


def pass_probability(target: float, drawdown: float, mu_d: float, sigma_d: float) -> float:
    """P(reach +target before -drawdown) for a drifting random walk."""
    if sigma_d <= 0:
        return 1.0 if mu_d > 0 else 0.0
    if mu_d == 0:
        # Driftless: the barrier ratio alone decides. This is the floor any sizing converges to,
        # and it is why a system with no edge cannot be saved by risk management.
        return drawdown / (target + drawdown)
    lam = 2.0 * mu_d / (sigma_d ** 2)
    try:
        num = 1.0 - math.exp(lam * drawdown)
        den = math.exp(-lam * target) - math.exp(lam * drawdown)
        if den == 0:
            return 0.0
        return max(0.0, min(1.0, num / den))
    except OverflowError:
        # lambda*drawdown huge means drift utterly dominates: passing is effectively certain.
        return 1.0


def expected_days(target: float, mu_d: float) -> float | None:
    return None if mu_d <= 0 else target / mu_d


def worst_day_fraction(risk_frac: float, drawdown: float) -> float:
    """Fraction of the drawdown buffer a fully correlated day consumes."""
    return (risk_frac * N_EFF_DAILY) / drawdown if drawdown else float("inf")


def frontier(target: float, drawdown: float) -> list[dict]:
    rows = []
    for exp_r in EXPECTANCIES:
        for r in RISK_GRID:
            mu_d = TRADES_PER_DAY * exp_r * r
            sigma_d = r * R_VOL * math.sqrt(N_EFF_DAILY)
            p = pass_probability(target, drawdown, mu_d, sigma_d)
            d = expected_days(target, mu_d)
            rows.append({
                "expectancy_R": exp_r, "risk_frac": r,
                "p_pass": round(p, 4),
                "expected_days": None if d is None else round(d, 1),
                "worst_correlated_day_pct_of_buffer": round(100 * worst_day_fraction(r, drawdown), 1),
            })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", type=float, default=0.06)
    ap.add_argument("--drawdown", type=float, default=0.04)
    ap.add_argument("--min-p", type=float, default=0.90,
                    help="minimum acceptable P(pass); the frontier is read at this level")
    args = ap.parse_args()

    now = datetime.now(tz=UTC)
    rows = frontier(args.target, args.drawdown)

    print(f"PROP SETTINGS  target +{args.target:.0%}  drawdown -{args.drawdown:.0%}  "
          f"{now.isoformat(timespec='seconds')}")
    print(f"  model: {TRADES_PER_DAY:.0f} trades/day, n_eff {N_EFF_DAILY} independent bets/day")
    print()

    best_by_exp: dict[float, dict] = {}
    for exp_r in EXPECTANCIES:
        sub = [r for r in rows if r["expectancy_R"] == exp_r]
        print(f"  expectancy {exp_r:.2f}R")
        print(f"    {'risk':>7s} {'P(pass)':>8s} {'days':>7s} {'worst day':>10s}")
        for r in sub:
            if r["risk_frac"] not in (0.0018, 0.0025, 0.0035, 0.0050, 0.0100):
                continue
            days = "never" if r["expected_days"] is None else f"{r['expected_days']:.0f}"
            print(f"    {r['risk_frac']*100:6.2f}% {r['p_pass']:8.3f} {days:>7s} "
                  f"{r['worst_correlated_day_pct_of_buffer']:9.0f}%")
        # FASTEST setting that still clears the probability floor -- the actual answer to
        # "as fast as safely possible", which is a constrained optimisation and not a preference.
        ok = [r for r in sub if r["p_pass"] >= args.min_p and r["expected_days"] is not None]
        if ok:
            fastest = min(ok, key=lambda r: r["expected_days"])
            best_by_exp[exp_r] = fastest
            print(f"    -> fastest at P>={args.min_p:.0%}: risk "
                  f"{fastest['risk_frac']*100:.2f}%, {fastest['expected_days']:.0f} days")
        else:
            print(f"    -> NO setting reaches P>={args.min_p:.0%}. At this expectancy the "
                  f"evaluation cannot be passed safely at any size.")
        print()

    payload = {"computed_at": now.isoformat(timespec="seconds"),
               "target": args.target, "drawdown": args.drawdown, "min_p": args.min_p,
               "trades_per_day": TRADES_PER_DAY, "n_eff_daily": N_EFF_DAILY,
               "recommended_by_expectancy": {str(k): v for k, v in best_by_exp.items()},
               "frontier": rows,
               "caveat": ("every row is conditional on expectancy_R, and this desk has ZERO "
                          "completed forward windows. The 0.00R row is the honest null: no "
                          "sizing rescues a system with no edge, it only delays the answer.")}
    OUT.write_text(json.dumps(payload, indent=1), "utf-8")
    print(f"  -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
