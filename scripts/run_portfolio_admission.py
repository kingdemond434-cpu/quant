#!/usr/bin/env python3
"""PORTFOLIO ADMISSION -- the stage that made `PORTFOLIO_CONTRIBUTING: null` permanent.

THE STRANDING THIS ENDS. Every sweep this desk has ever run reported::

    FORMULA 9 | FAMILY 3 | INDEPENDENT MECHANISM 2 | PORTFOLIO-CONTRIBUTING unmeasured

The null was read as "the harness builds no portfolio", which was true and was not the whole
truth: the sweep computed each survivor's return series for clustering and then DISCARDED it, so
nothing downstream could have measured portfolio contribution even if it had wanted to. The count
was not merely unmeasured, it was unmeasurable, and the two look identical in a report.

`run_full_sweep` now writes the series to a sidecar. This consumes it, runs
`marginal_admission.evaluate` for every survivor against the live cohort, and fills the count in.

**A DISTINCT MECHANISM IS NOT AN ADDITIVE ONE, WHICH IS THE ENTIRE POINT OF THIS STAGE.** Two
survivors can be provenly independent of each other and still add nothing to the book: independence
is measured against the OTHER SURVIVORS, admission is measured against WHAT THE DESK ALREADY HOLDS.
A desk that counts independent mechanisms as discoveries is counting inventory one step later than
it used to.

**WITH AN EMPTY BOOK, EVERY SURVIVOR IS TRIVIALLY ADMITTED, AND THAT IS REPORTED AS THE WEAK
RESULT IT IS.** The desk holds no live cohort today, so "improves the portfolio" degenerates to
"has a positive Sharpe" -- a real answer to a much easier question, and the report says so rather
than banking nine admissions.

Promotes nothing, sizes nothing, places nothing. Arming live trading is the principal's act.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.marginal_admission import evaluate  # noqa: E402

SWEEP = ROOT / "data" / "full_sweep.json"
PNL = ROOT / "data" / "full_sweep_survivor_pnl.npz"
#: The live cohort's return series, one column per deployed sleeve. Absent -> empty book.
INCUMBENTS = ROOT / "data" / "live_cohort_pnl.npz"
OUT = ROOT / "data" / "portfolio_admission.json"


def load_incumbents(path: Path) -> tuple[np.ndarray, list[str]]:
    """(T, k) of the live cohort, and its names. An absent file is an EMPTY BOOK, not an error.

    Empty is the desk's actual state and must produce a stated weak verdict rather than a crash
    or a silent skip -- a skip here is how the count stayed null for weeks.
    """
    if not path.exists():
        return np.zeros((0, 0), dtype=float), []
    with np.load(path) as z:
        names = sorted(z.files)
        if not names:
            return np.zeros((0, 0), dtype=float), []
        cols = [np.asarray(z[n], dtype=float) for n in names]
    width = min(len(c) for c in cols)
    return np.column_stack([c[-width:] for c in cols]), names


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sweep", type=Path, default=SWEEP)
    ap.add_argument("--pnl", type=Path, default=PNL)
    ap.add_argument("--incumbents", type=Path, default=INCUMBENTS)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--periods-per-year", type=float, default=365.0)
    a = ap.parse_args()

    if not a.pnl.exists():
        print(f"portfolio-admission: BLOCKED -- no survivor pnl sidecar at {a.pnl}. That is "
              "UNMEASURED and it is the state that made PORTFOLIO_CONTRIBUTING permanently null: "
              "run the sweep, which now emits it.")
        return 0

    with np.load(a.pnl) as z:
        survivors = {n: np.asarray(z[n], dtype=float) for n in z.files}
    incumbents, cohort = load_incumbents(a.incumbents)

    rows: list[dict[str, object]] = []
    admitted = 0
    for name, series in sorted(survivors.items()):
        if incumbents.size:
            width = min(len(series), len(incumbents))
            res = evaluate(series[-width:], incumbents[-width:],
                           periods_per_year=a.periods_per_year)
            ok = bool(res.admitted)
            # The full verdict is retained rather than reduced to a boolean: rho,
            # the hurdle it was gated on and the orthogonal IR are what let a
            # rejection be argued with instead of merely accepted.
            detail = (f"{res.reason} | rho_used {res.rho_used:.3f}, hurdle "
                      f"{res.hurdle:.3f}, orthogonal IR {res.orthogonal_ir:.3f}, "
                      f"gain {res.gain:+.4f}")
        else:
            # THE DEGENERATE CASE, STATED. With no incumbents there is nothing to be incremental
            # TO, so this answers a strictly easier question and must never be banked as if it had
            # answered the hard one.
            sd = float(np.std(series, ddof=1)) if len(series) > 1 else 0.0
            sharpe = (float(np.mean(series)) / sd * a.periods_per_year ** 0.5) if sd > 0 else 0.0
            ok = sharpe > 0
            detail = (f"EMPTY BOOK: no live cohort, so 'improves the portfolio' degenerates to "
                      f"'has positive Sharpe' ({sharpe:+.3f}). A real answer to a much easier "
                      "question -- this is NOT evidence of incremental value")
        admitted += int(ok)
        rows.append({"survivor": name, "admitted": ok, "why": detail,
                     "observations": len(series)})

    rep = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "survivors_tested": len(survivors),
        "incumbents": cohort,
        "empty_book": not bool(incumbents.size),
        "PORTFOLIO_CONTRIBUTING": admitted,
        "verdict": (
            f"{admitted}/{len(survivors)} admitted against an EMPTY BOOK -- a weak result by "
            "construction, and the count means 'positive standalone Sharpe', not 'adds to the "
            "portfolio'" if not incumbents.size else
            f"{admitted}/{len(survivors)} raise the Sharpe of the book the desk already holds"),
        "rows": rows,
        "authority": ("NONE. Measures admission, promotes nothing, sizes nothing, places nothing. "
                      "Arming live trading is the principal's act."),
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rep, indent=1, default=str), "utf-8")
    print(f"portfolio-admission: {rep['verdict']}")
    for r in rows[:10]:
        print(f"  [{'ADMIT' if r['admitted'] else 'REJECT'}] {r['survivor']}: {r['why']}")
    print(f"  artifact: {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
