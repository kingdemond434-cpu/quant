"""MAX_FORWARD_SLOTS EV analysis -- is 12 the right number of concurrent confirmation slots?

THE TWO-STAGE DISCOVERY LAW fixes the confirmation bar for life by capping CONCURRENT forward
slots at 12 and Holm-correcting across them. That cap is enforced (run_alerts slot_budget_
exceeded) and saturation is checked both ways (max_audit clock-saturation). What was never
analysed is the NUMBER ITSELF -- 12 arrived as a choice, not as arithmetic, and it sits directly
upstream of geometric growth because the ladder's step 3 gates on ">= 3 orthogonal validated
sleeves".

THE TRADE, precisely. Holm-Bonferroni at family-wise alpha over N concurrent slots requires the
most significant result to beat alpha/N. So raising N buys more shots and simultaneously raises
the bar every shot must clear:

    N=6   ->  p <= 0.00833  ->  z >= 2.39
    N=12  ->  p <= 0.00417  ->  z >= 2.64
    N=24  ->  p <= 0.00208  ->  z >= 2.87

More slots is therefore NOT free, and fewer slots is not automatically safer -- an idle slot is
research capital earning nothing, which max_audit already calls a defect. The optimum depends on
two quantities the desk can estimate from its own history: the base rate of true edges among
screen survivors (pi), and their typical effect size in forward t-units.

E[validated discoveries] = N * pi * Power(z_bar(N), effect)  -  N * c

THE KEY RESULT, and it is not what the author expected. With family-wise alpha HELD FIXED,
expected false discoveries stay bounded by alpha no matter how large N gets, while power decays
only logarithmically in N. So the statistical term N*pi*Power(N) is MONOTONICALLY INCREASING
over any plausible range -- statistics alone does not bound the slot count at all, and a first
version of this script duly reported an "argmax" of 30 that was simply the edge of its own
search window.

That is a modelling artifact, not a recommendation, and shipping it would have been the exact
confident-wrong-number failure this desk's auditor prompt ranks worst. The real bound is the
per-slot COST term c: every concurrent slot consumes research attention, monitoring, and a share
of finite capital. The optimum is therefore set by capital and attention, NOT by multiplicity
maths -- which reframes the question from "is 12 statistically right?" to "what does a slot
actually cost us?"

NO RAIL IS TOUCHED. This computes the curve and names the argmax; changing MAX_FORWARD_SLOTS is
a Tier-3 action requiring principal sign-off. Statistical standards are never reduced -- the
family-wise alpha is held FIXED at every N, which is the whole point.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from math import erf, sqrt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/slot_budget_analysis.json"
CURRENT = 12
ALPHA = 0.05


def _ncdf(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def _z_for_p(p: float) -> float:
    """One-sided normal quantile by bisection -- no scipy, so this stays importable anywhere."""
    lo, hi = 0.0, 12.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if 1.0 - _ncdf(mid) > p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def power(effect_t: float, z_bar: float) -> float:
    """P(observed t beats the bar) for a true edge whose expected t is `effect_t`."""
    return 1.0 - _ncdf(z_bar - effect_t)


def curve(pi: float, effect_t: float, alpha: float = ALPHA, n_max: int = 40,
          cost_per_slot: float = 0.0) -> list[dict[str, float]]:
    """`cost_per_slot` is in units of validated-discoveries-forgone per slot per window.

    It is what makes the optimum interior. Without it the objective is monotone in N and the
    'argmax' is just wherever the loop stopped.
    """
    rows = []
    for n in range(1, n_max + 1):
        z_bar = _z_for_p(alpha / n)          # Holm's most-significant requirement
        pw = power(effect_t, z_bar)
        gross = n * pi * pw
        rows.append({"slots": n, "per_slot_p_bar": round(alpha / n, 5),
                     "z_bar": round(z_bar, 3), "power": round(pw, 4),
                     "expected_validated": round(gross, 4),
                     "net_of_cost": round(gross - n * cost_per_slot, 4)})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--true-rate", type=float, default=0.15,
                    help="pi: fraction of screen survivors that are genuine edges")
    ap.add_argument("--effect-t", type=float, default=3.0,
                    help="expected forward t-stat of a genuine edge")
    ap.add_argument("--cost-per-slot", type=float, default=0.04,
                    help="attention+capital cost of one concurrent slot, in validated-"
                         "discoveries-forgone. THIS is what bounds N; statistics does not.")
    args = ap.parse_args()

    print("=== MAX_FORWARD_SLOTS EV ANALYSIS ===")
    print(f"    family-wise alpha held FIXED at {ALPHA} for every N (standards never reduced)")
    print(f"    assumptions: true-edge rate pi={args.true_rate}, effect t={args.effect_t}\n")

    rows = curve(args.true_rate, args.effect_t, cost_per_slot=args.cost_per_slot)
    best = max(rows, key=lambda r: r["net_of_cost"])
    cur = next(r for r in rows if r["slots"] == CURRENT)

    print(f"  {'slots':>6}{'p bar':>10}{'z bar':>8}{'power':>9}"
          f"{'E[validated]':>14}{'net of cost':>12}")
    for r in rows:
        if r["slots"] in (1, 3, 6, 9, 12, 15, 18, 24, 30) or r["slots"] == best["slots"]:
            mark = "  <- CURRENT" if r["slots"] == CURRENT else ""
            mark += "  <- ARGMAX" if r["slots"] == best["slots"] else ""
            print(f"  {r['slots']:>6}{r['per_slot_p_bar']:>10.5f}{r['z_bar']:>8.3f}"
                  f"{r['power']:>9.4f}{r['expected_validated']:>14.4f}"
                  f"{r['net_of_cost']:>12.4f}{mark}")

    gain = (best["net_of_cost"] - cur["net_of_cost"]) / max(abs(cur["net_of_cost"]), 1e-12)
    print(f"\n  current N={CURRENT}: E[validated]={cur['expected_validated']:.4f} "
          f"(power {cur['power']:.3f} at z>={cur['z_bar']:.2f})")
    print(f"  argmax  N={best['slots']}: net={best['net_of_cost']:.4f}")
    print(f"  headroom from re-slotting: {gain:+.1%}")

    # SENSITIVITY. The argmax moves with pi and effect size, so a single point estimate is not a
    # decision -- if the argmax is unstable across plausible inputs, 12 is defensible and the
    # honest recommendation is to leave the rail alone and go measure pi instead.
    argmaxes = set()
    for p_i in (0.05, 0.10, 0.15, 0.25):
        for e_t in (2.5, 3.0, 3.5, 4.0):
            argmaxes.add(max(curve(p_i, e_t, cost_per_slot=args.cost_per_slot),
                             key=lambda r: r["net_of_cost"])["slots"])
    lo, hi = min(argmaxes), max(argmaxes)
    print(f"  sensitivity: argmax ranges N={lo}..{hi} across pi in [0.05,0.25], t in [2.5,4.0]")

    boundary = best["slots"] >= 39
    if boundary:
        verdict = ("INCONCLUSIVE -- argmax sits at the search boundary, meaning the assumed "
                   "per-slot cost is too low to bind. Statistics does not limit N here; measure "
                   "the real attention+capital cost of a slot before touching the cap.")
    elif lo <= CURRENT <= hi:
        verdict = (f"KEEP {CURRENT} -- inside the stable argmax band N={lo}..{hi}. The binding "
                   "constraint is SATURATION (12/12 slots idle right now), not the cap: the "
                   "desk is not using the slots it already has.")
    else:
        verdict = (f"REVIEW -- argmax band N={lo}..{hi} excludes the current cap of {CURRENT}")
    print(f"\n  VERDICT: {verdict}")
    print("  Tier-3: changing MAX_FORWARD_SLOTS needs principal sign-off. This is analysis only.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(
        {"ran": datetime.now(tz=UTC).isoformat(), "alpha": ALPHA, "current_cap": CURRENT,
         "assumptions": {"true_edge_rate": args.true_rate, "effect_t": args.effect_t},
         "curve": rows, "argmax": best, "at_current": cur,
         "argmax_band_over_sensitivity": [lo, hi], "verdict": verdict,
         "note": ("Family-wise alpha is FIXED across all N -- raising slots raises the per-slot "
                  "bar, it never loosens it. An idle slot is research capital earning nothing.")},
        indent=1), "utf-8")
    print(f"  -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
