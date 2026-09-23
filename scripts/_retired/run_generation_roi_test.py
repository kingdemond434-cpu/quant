#!/usr/bin/env python3
"""Monte-Carlo falsification: does batch hypothesis generation over a FIXED data set pay?

Runs synthetic candidate batches of growing size through the REAL novelty gate + DSR gauntlet
(libs/autodiscovery/generation_roi) and prints the survivor rate, the deflated DSR bar, and the cost
per survivor as the batch grows. A few candidates carry a true edge; the rest are noise.

    python scripts/run_generation_roi_test.py

Demonstrates the economics behind the Discovery-Factory deferral: as the batch (and thus the trial
count) grows, the DSR bar rises and the survivor rate collapses — mass generation over the same data
is self-defeating. A SECOND discovery method here shares the same trial ledger, so it deflates both
rather than diversifying. Positive ROI needs a NEW data axis (unexhausted space, low trial count).
"""

from __future__ import annotations

import numpy as np

from libs.autodiscovery.generation_roi import Candidate, generation_roi
from libs.validation.dsr import sharpe_ratio


def _candidate(
    cid: str, rng: np.random.Generator, *, edge_sharpe: float,
    n_periods: int = 500, sigma: float = 0.01,
) -> Candidate:
    mu = edge_sharpe * sigma
    r = rng.normal(mu, sigma, n_periods)
    return Candidate(
        id=cid, statement=f"hypothesis {cid}", features=(f"feat_{cid}",),
        returns=tuple(float(x) for x in r),
    )


def _batch(
    n: int, rng: np.random.Generator, *, edge_frac: float, edge_sharpe: float
) -> list[Candidate]:
    out: list[Candidate] = []
    for i in range(n):
        s = edge_sharpe if rng.random() < edge_frac else 0.0
        out.append(_candidate(f"n{n}_{i}", rng, edge_sharpe=s))
    return out


def main() -> None:
    rng = np.random.default_rng(20260723)
    edge_frac, edge_sharpe = 0.03, 0.15
    print("Generation-ROI Monte-Carlo -- batch generation over a FIXED data set")
    print(f"({edge_frac:.0%} carry a true ~{edge_sharpe}/period Sharpe edge; the rest are null)\n")

    cols = ("batch N", "tested", "survivors", "surv_rate", "DSR_bar", "cost/surv")
    widths = (8, 8, 10, 10, 9, 10)
    print("".join(f"{c:>{w}}" for c, w in zip(cols, widths, strict=True)))
    print("-" * sum(widths))
    for n in (10, 50, 200, 1000):
        batch = _batch(n, rng, edge_frac=edge_frac, edge_sharpe=edge_sharpe)
        sharpes = [sharpe_ratio(np.asarray(c.returns, dtype="float64")) for c in batch]
        rep = generation_roi(batch, variance_of_sharpes=float(np.var(sharpes, ddof=1)))
        cps = "inf" if rep.cost_per_survivor == float("inf") else f"{rep.cost_per_survivor:.1f}"
        vals = (n, rep.backtested, rep.survivors, f"{rep.survivor_rate:.3f}",
                f"{rep.deflated_bar_sr0:.3f}", cps)
        print("".join(f"{v:>{w}}" for v, w in zip(vals, widths, strict=True)))

    print("\nRead: as N grows the DSR bar rises and the survivor rate collapses.")
    print("Mass generation over the SAME data is self-defeating under multiplicity correction.")
    print("A second method shares this SAME trial ledger -- it deflates both, not diversifies.")
    print("Positive ROI needs a NEW data axis (unexhausted space, low trial count).")


if __name__ == "__main__":
    main()
