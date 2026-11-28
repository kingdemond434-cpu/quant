"""H5 INFORMATION-GAIN TEST PRIORITISATION: what one more judged cell would teach the desk.

WHY. The judge's docket order is novelty, chart, CEO family, bucket coverage and symbol rotation;
the yield trim then funds families by survivors per ruled cell. None of that asks how much the
desk would LEARN from judging a given cell. A family with 4,000 ruled cells and a family with 3
can carry the same yield estimate and wildly different uncertainty about it, and the next cell of
the second is worth far more information than the 4,001st of the first.

THE SCORE. Each (family, chart) has a Beta posterior over its pass rate -- passes and ruled cells
from the sealed gauntlet's own `universal_gates_external.json` (UNMEASURED verdicts excluded, as
the judge's `_family_yield` excludes them), shrunk hierarchically: the house rate (all ruled
cells) is the prior of each family, and the family posterior is the prior of each (family, chart).
The score is the EXPECTED REDUCTION IN POSTERIOR VARIANCE from ruling one more cell:

    EIG = Var[Beta(a, b)] - ( p * Var[Beta(a+1, b)] + (1-p) * Var[Beta(a, b+1)] ),  p = a/(a+b)

which is large where the estimate is both uncertain and undecided, and shrinks like 1/n^2 as a
family is ruled. Every docket cell maps to exactly one (family, chart) row, so the table scores
every cell; `score` is EIG normalised to [0, 1] over the families on the docket.

REPORT FIRST. INFO_GAIN.json publishes the score; `judge_docket_order.priority_tilt` blends it into
the warm order inside a bounded tilt (a row moves at most `TILT_MAX` of its tier). No gate reads it.
A missing verdict file is UNMEASURED: every score is then the same and the blend moves nothing.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

#: Prior strength (pseudo-cells) at each level of the hierarchy.
FAMILY_PRIOR = 20.0
CHART_PRIOR = 10.0


def beta_var(a: float, b: float) -> float:
    s = a + b
    return (a * b) / (s * s * (s + 1.0)) if s > 0 else 0.0


def expected_gain(a: float, b: float) -> float:
    """Expected posterior-variance reduction from one more Bernoulli observation."""
    if a <= 0 or b <= 0:
        return 0.0
    p = a / (a + b)
    after = p * beta_var(a + 1.0, b) + (1.0 - p) * beta_var(a, b + 1.0)
    return max(0.0, beta_var(a, b) - after)


def chart_of_cell(cell: str) -> str:
    sym = str(cell).split(".", 1)[0]
    return sym.split("@", 1)[1].upper() if "@" in sym else "H1"


def ruled_counts(verdicts: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str], list[int]]:
    """(family, chart) -> [passes, ruled]; UNMEASURED verdicts never count."""
    out: dict[tuple[str, str], list[int]] = {}
    for v in verdicts:
        if not isinstance(v, Mapping) or v.get("unmeasured"):
            continue
        fam = str(v.get("family") or "")
        if not fam:
            continue
        tf = str(v.get("timeframe") or "").upper() or chart_of_cell(str(v.get("cell") or ""))
        slot = out.setdefault((fam, tf), [0, 0])
        slot[0] += int(bool(v.get("passed")))
        slot[1] += 1
    return out


def score_table(counts: Mapping[tuple[str, str], list[int]],
                docket: Mapping[tuple[str, str], int]) -> dict[str, Any]:
    """Score every (family, chart) on the docket. `docket`: (family, chart) -> cells."""
    tot_s = sum(c[0] for c in counts.values())
    tot_r = sum(c[1] for c in counts.values())
    house = (tot_s + 1.0) / (tot_r + 2.0)
    fam_s: dict[str, list[int]] = {}
    for (fam, _tf), (s, r) in counts.items():
        slot = fam_s.setdefault(fam, [0, 0])
        slot[0] += s
        slot[1] += r
    rows: dict[str, dict[str, Any]] = {}
    for (fam, tf), n_cells in docket.items():
        fs, fr = fam_s.get(fam, [0, 0])
        m_f = (fs + house * FAMILY_PRIOR) / (fr + FAMILY_PRIOR)
        s, r = counts.get((fam, tf), [0, 0])
        a = s + m_f * CHART_PRIOR
        b = (r - s) + (1.0 - m_f) * CHART_PRIOR
        rows[f"{fam}|{tf}"] = {"family": fam, "chart": tf, "cells": n_cells,
                               "passes": s, "ruled": r, "family_ruled": fr,
                               "posterior_mean": round(a / (a + b), 6),
                               "posterior_sd": round(beta_var(a, b) ** 0.5, 6),
                               "eig": expected_gain(a, b)}
    top = max((r["eig"] for r in rows.values()), default=0.0)
    for r in rows.values():
        r["score"] = round(r["eig"] / top, 6) if top > 0 else 0.0
        r["eig"] = float(f"{r['eig']:.6g}")
    return {"house_rate": round(house, 6), "ruled_total": tot_r, "passes_total": tot_s,
            "rows": rows}


def report(table: Mapping[str, Any], *, measured: bool, why: str = "") -> dict[str, Any]:
    rows = table.get("rows") or {}
    ranked = sorted(rows.values(), key=lambda r: (-r["score"], -r["cells"]))
    cells = sum(r["cells"] for r in rows.values())
    return {
        "law": "H5: every docket cell is scored by the expected posterior-variance reduction of "
               "its (family, chart) pass-rate estimate; the score is blended into the judge's "
               "warm ORDER inside a bounded tilt, never into a gate.",
        "status": "MEASURED" if measured else "UNMEASURED",
        **({"why": why} if why else {}),
        "cells_scored": cells,
        "families_charts": len(rows),
        "house_rate": table.get("house_rate"),
        "ruled_total": table.get("ruled_total"),
        "passes_total": table.get("passes_total"),
        "prior": {"family": FAMILY_PRIOR, "chart": CHART_PRIOR,
                  "basis": "house rate -> family -> (family, chart), Beta-Binomial"},
        "top": ranked[:40],
        "bottom": ranked[-10:] if len(ranked) > 40 else [],
        "table": {k: {"score": v["score"], "eig": v["eig"], "cells": v["cells"],
                      "ruled": v["ruled"], "posterior_mean": v["posterior_mean"]}
                  for k, v in sorted(rows.items())},
    }
