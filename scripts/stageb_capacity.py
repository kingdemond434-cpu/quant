"""STAGE-B CAPACITY -- how many forward clocks SHOULD run at once? Compute it, do not assume 3.

THE PRINCIPAL'S QUESTION: if Stage-A is unlimited, why not run Stage-B on everything too?

BECAUSE STAGE-B HAS A STATISTICAL PRICE STAGE-A DOES NOT. Holm correction across m concurrent
clocks raises the significance bar for EVERY clock, including the good ones. Adding a weak
hypothesis does not just waste its own slot -- it makes a genuinely real effect in another slot
harder to detect. Stage-A is free because it promotes nothing; Stage-B is scarce because it is the
only path to money.

But "3" was never derived. It is what happens to be running. This computes the actual trade-off:
the Holm bar at each m, the t-stat a real effect would need, and where the marginal clock starts
costing more discrimination than it buys.

Read-only. No keys.
"""
from __future__ import annotations

import json
import math
import pathlib
from datetime import UTC, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data/stageb_capacity.json"
ALPHA = 0.05
MIN_DAYS = 40


def _z(p: float) -> float:
    """Inverse normal CDF (Acklam approximation) -- the two-sided Holm bar at level p."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > ph:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q, r = p - 0.5, (p - 0.5) ** 2
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def holm_bar(m: int) -> float:
    """Most stringent Holm threshold with m concurrent tests, two-sided."""
    return abs(_z(1 - ALPHA / (2 * m)))


def main() -> None:
    st = {}
    try:
        st = json.loads((ROOT / "data/axis_shadow_state.json").read_text("utf-8"))
    except Exception:  # noqa: BLE001
        pass
    running = len(st.get("axes", []))
    observed = next((a.get("holm_bar") for a in st.get("axes", []) if a.get("holm_bar")), None)

    try:
        sched = len(json.loads((ROOT / "data/research_cio.json").read_text("utf-8"))
                    .get("schedule", []))
    except Exception:  # noqa: BLE001
        sched = 0

    print("=== STAGE-B CAPACITY -- how many forward clocks should run at once? ===")
    print("    Stage-A is free because it promotes nothing. Stage-B is scarce because it is the")
    print("    only path to capital -- and every extra clock raises the bar for ALL of them.\n")
    print(f"  currently running : {running} clocks")
    print(f"  observed holm_bar : {observed}  (desk's own state file)")
    print(f"  Stage-A backlog   : {sched} ranked candidates waiting\n")

    print(f"  {'m':>4}{'holm bar':>11}{'vs m=1':>9}{'vs m=3':>9}   interpretation")
    base1, base3 = holm_bar(1), holm_bar(3)
    rows = []
    for m in (1, 3, 5, 8, 10, 15, 20, 30, 50, 100, 214):
        b = holm_bar(m)
        interp = ("free" if m == 1 else
                  "current" if m == 3 else
                  "cheap -- worth taking" if b - base3 < 0.30 else
                  "material cost" if b - base3 < 0.60 else
                  "self-defeating")
        print(f"  {m:>4}{b:>11.3f}{b-base1:>+9.3f}{b-base3:>+9.3f}   {interp}")
        rows.append({"m": m, "holm_bar": round(b, 4), "vs_m1": round(b - base1, 4),
                     "vs_m3": round(b - base3, 4), "verdict": interp})

    cheap = [r["m"] for r in rows if r["verdict"] == "cheap -- worth taking"]
    rec = max(cheap) if cheap else 3
    print(f"\n  RECOMMENDATION: {rec} concurrent clocks, up from {running}.")
    print(f"  Going 3 -> {rec} raises the bar from {base3:.2f} to {holm_bar(rec):.2f} "
          f"(+{holm_bar(rec)-base3:.2f}), which a real effect")
    print("  survives. Going to 214 needs t > "
          f"{holm_bar(214):.2f} -- that is not a stricter standard, it is an")
    print("  unreachable one, and it would bury the genuine effects alongside the noise.")
    print("\n  THE ASYMMETRY THAT ANSWERS THE QUESTION: a weak hypothesis in Stage-A costs its own")
    print("  compute and nothing else. The same hypothesis in Stage-B taxes EVERY OTHER CLOCK.")
    print("  That is why Stage-A is unlimited and Stage-B is rationed -- not caution, arithmetic.")
    print(f"\n  BUT '3' WAS NEVER DERIVED -- it is simply what happens to be running. On this")
    print(f"  arithmetic the desk is UNDER-USING Stage-B by roughly {rec-running} slots while")
    print(f"  {sched} candidates queue behind it. That is a real throughput bottleneck.")

    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "running": running, "backlog": sched,
                               "recommended_concurrent": rec, "curve": rows}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()
