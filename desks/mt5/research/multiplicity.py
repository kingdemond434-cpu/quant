"""Multiplicity correction (deflated Sharpe / family-level PBO proxy).

With thousands of tests across families, raw t-stats overstate expected
forward performance: the best of N tests is expected to look good under the
null. We haircut every survivor's t-stat by the expected maximum of N
independent standard normals, computed per family group.

    t_deflated = t_obs - E[max_{N} Z],   Z ~ N(0,1)

E[max_N Z] ~ sqrt(2 ln N) - (ln(ln N) + ln(4 pi)) / (2 sqrt(2 ln N))

A survivor needs t_deflated > 2 to keep gate status under multiplicity.

SINCE THE T8 RULING (principal, 2026-10-13) `annotate_report` does not use the two functions
below: it deflates by `gate_policy.fixed_bar_deflation()` (fixed N=5, the judge's Bailey form,
1.193) and requires the judge's margin z(0.95) = 1.645, so gate_ds means t > 2.837, the Tier-S
bar. `expected_max_z` / `deflate_t` stay for their other importers (non-sealed miners).
"""

from __future__ import annotations

import json
from math import log, pi, sqrt
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent.parent


def expected_max_z(n_tests: int) -> float:
    if n_tests <= 1:
        return 0.0
    ln = log(n_tests)
    if ln <= 0:
        return 0.0
    return sqrt(2 * ln) - (log(ln) + log(4 * pi)) / (2 * sqrt(2 * ln))


def deflate_t(t_obs: float, n_tests: int) -> float:
    return float(t_obs - expected_max_z(n_tests))


def annotate_report(path: str) -> dict:
    """Annotate a hunt report JSON: per-family test counts + deflated t for every result;
    survivors flagged gate_ds (original gate AND t clears the Tier-S bar, t > 2.837)."""
    # THE T8 BAR (principal, 2026-10-13): the deflation is gate_policy's ONE fixed-bar deflation
    # (E[max Z] at the fixed N=`DSR_FIXED_TRIALS`, the judge's Bailey form) and the margin is the
    # judge's z at DSR 0.95 -- never the family or total test count, which are still REPORTED
    # (n_tests_family / n_tests_total). Imported here, not at module top, so the many importers
    # of `deflate_t` alone do not load the gate spec.
    from research.gate_policy import (
        DSR_FIXED_TRIALS,
        fixed_bar_deflation,
        fixed_bar_margin,
        fixed_bar_t,
    )
    e_bar = fixed_bar_deflation()
    margin = fixed_bar_margin()
    report = json.loads((BASE / path).read_text(encoding="utf-8"))
    all_tests = report.get("all", [])
    family_counts: dict[str, int] = {}
    for r in all_tests:
        fam = r.get("family", "unknown")
        family_counts[fam] = family_counts.get(fam, 0) + 1
    total = len(all_tests)
    for r in all_tests:
        fam = r.get("family", "unknown")
        r["n_tests_family"] = family_counts[fam]
        r["n_tests_total"] = total
        r["t_deflated_family"] = float(r.get("t_stat", 0.0) - e_bar)
        r["t_deflated_total"] = float(r.get("t_stat", 0.0) - e_bar)
        r["gate_ds"] = bool(r.get("gate", False) and r["t_deflated_family"] > margin
                            and r["t_deflated_total"] > margin)
    report["survivors"] = [r for r in all_tests if r.get("gate_ds", False)]
    report["multiplicity"] = {
        "expected_max_z_family_max": e_bar if family_counts else 0.0,
        "expected_max_z_total": e_bar,
        "total_tests": total,
        "trials_charged": DSR_FIXED_TRIALS,
        "bar_t": fixed_bar_t(),
        "method": (f"deflated t = t - E[max_N Z] at fixed N={DSR_FIXED_TRIALS} "
                   f"(gate_policy.fixed_bar_deflation); gate_ds = gate AND deflated > "
                   f"{margin:.3f} (t > {fixed_bar_t():.3f}, the Tier-S bar)"),
    }
    (BASE / path).write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        rep = annotate_report(p)
        print(f"{p}: {len(rep['all'])} tests, "
              f"{len(rep['survivors'])} multiplicity-verified survivors "
              f"(E[max Z] total={rep['multiplicity']['expected_max_z_total']:.3f})")