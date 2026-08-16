"""Multiplicity correction (deflated Sharpe / family-level PBO proxy).

With thousands of tests across families, raw t-stats overstate expected
forward performance: the best of N tests is expected to look good under the
null. We haircut every survivor's t-stat by the expected maximum of N
independent standard normals, computed per family group.

    t_deflated = t_obs - E[max_{N} Z],   Z ~ N(0,1)

E[max_N Z] ~ sqrt(2 ln N) - (ln(ln N) + ln(4 pi)) / (2 sqrt(2 ln N))

A survivor needs t_deflated > 2 to keep gate status under multiplicity.
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
    """Annotate a hunt report JSON: per-family test counts + deflated t for
    every result; survivors flagged gate_ds (t_deflated > 2 and original gate)."""
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
        r["t_deflated_family"] = deflate_t(r.get("t_stat", 0.0), family_counts[fam])
        r["t_deflated_total"] = deflate_t(r.get("t_stat", 0.0), total)
        r["gate_ds"] = bool(r.get("gate", False) and r["t_deflated_family"] > 2.0
                            and r["t_deflated_total"] > 2.0)
    report["survivors"] = [r for r in all_tests if r.get("gate_ds", False)]
    report["multiplicity"] = {
        "expected_max_z_family_max": max(
            (expected_max_z(c) for c in family_counts.values()), default=0.0),
        "expected_max_z_total": expected_max_z(total),
        "total_tests": total,
        "method": "deflated t = t - E[max_N Z]; gate_ds = gate AND deflated>2",
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