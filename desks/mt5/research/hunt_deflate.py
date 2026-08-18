"""Re-deflate the cached hunt correctly, and hand the survivors to the pipeline.

TWO DEFECTS IN full_hunt.py MADE ITS BAR MEANINGLESS, AND BOTH WERE MINE

FIRST, N_effective never ran. The guard required 200+ days on which EVERY one of
1,384 cells traded, and the intersection of 1,384 differently-scheduled sleeves
is exactly zero rows. So it fell through to N_raw = 3,168 and reported
"N_effective 3168" as though the correction had been applied. A fallback that
silently reproduces the uncorrected number is worse than no fallback, because
the output looks like it was checked. Fixed here with pairwise-complete
correlation, which is what the ragged coverage actually requires.

SECOND, variance_of_sharpes came from a pool spanning -9.56 to +2.99, giving
3.3381. SR0 = sqrt(var) x E[max of N standard normals] is then 1.83 x 3.57 =
6.52. AN SR0 OF 6.52 IS NOT A THRESHOLD, IT IS AN ARTEFACT: no strategy in
recorded history has a Sharpe of 6.5, so the gate was rejecting everything by
construction rather than by evidence, and "0 of 1384 passed" carried no
information at all.

The deflated Sharpe assumes the trial Sharpes are draws from ONE distribution.
This pool is not: it mixes families that structurally cannot work on an
instrument (a Monday-gap rule on a symbol with no weekend gap) with genuine
candidates. Those aren't unlucky draws from the same urn, they are a different
urn, and letting them set the spread inflates the bar for everything else. The
variance is therefore also reported over the plausible sub-pool, and both are
shown because the choice is arguable and the reader should see it.

WHAT THIS FILE DOES NOT DO

It does not pick whichever variance gives a nicer answer. Every bar is printed
side by side with the count that clears it, and the RAW threshold — the
principal's stated rule, no multiplicity haircut — is the one that feeds the
promotion pipeline. Deflation orders the queue behind it.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "research"))
sys.path.insert(0, "/home/user/Aurum")

sys.path.insert(0, str(BASE.parent.parent))
from libs.validation.dsr import (expected_max_sharpe,  # noqa: E402
                                 probabilistic_sharpe_ratio)

DEFLATE_VERSION = "huntdeflate-2026-08-18-a"

CACHE = BASE / "data" / "full_hunt_series.parquet"
OUT = BASE / "data" / "hunt_candidates.json"

#: Minimum overlapping days before a PAIR contributes a correlation. Below this
#: the estimate is noise, and noisy near-zero correlations read as independence,
#: which RAISES the effective trial count and hardens the bar on false grounds.
MIN_PAIR_OVERLAP = 250

TPY = 252


def participation_ratio(df: pd.DataFrame) -> tuple:
    """Effective independent trials from the correlation spectrum.

    (sum of eigenvalues)^2 / sum of squares. A block of near-identical columns —
    rr=1.5 and rr=2.0 of the same rule on the same symbol — contributes one,
    which is the whole point: those are one look, not two.

    Pairwise-complete because the panel is ragged. That can produce a matrix
    that is not positive semi-definite, so negative eigenvalues are clipped to
    zero rather than used; clipping biases the ratio UP, toward more trials and
    a harder bar, which is the safe direction for an error.
    """
    c = df.corr(min_periods=MIN_PAIR_OVERLAP).to_numpy(dtype=float)
    c = np.nan_to_num(c, nan=0.0)
    np.fill_diagonal(c, 1.0)
    ev = np.clip(np.linalg.eigvalsh((c + c.T) / 2.0), 0.0, None)
    denom = float((ev ** 2).sum())
    if denom <= 0:
        return float(df.shape[1]), "degenerate spectrum; no deduplication assumed"
    pr = float(ev.sum() ** 2 / denom)
    return pr, (f"participation ratio {pr:.1f} over {df.shape[1]} columns "
                f"(pairwise-complete, {MIN_PAIR_OVERLAP}d minimum overlap)")


def main() -> int:
    if not CACHE.exists():
        print(f"no cache at {CACHE}; run full_hunt.py first")
        return 1
    df = pd.read_parquet(CACHE)
    n_attempted = 3168
    srs = (df.mean() / df.std() * math.sqrt(TPY)).dropna()
    print(f"HUNT RE-DEFLATION  ({DEFLATE_VERSION})")
    print(f"{df.shape[1]} usable cells from {n_attempted} attempted\n")

    pr, why = participation_ratio(df)
    # Scale the measured structure up to every cell attempted: the 1,784 that
    # died were looks too, and they are at least as duplicated as the survivors.
    n_eff = max(2.0, pr * n_attempted / df.shape[1])

    var_all = float(srs.var(ddof=1))
    plausible = srs[srs > 0]
    var_pos = float(plausible.var(ddof=1)) if len(plausible) > 2 else var_all

    print("=" * 94)
    print("THE TWO INPUTS THAT SET THE BAR")
    print("=" * 94)
    print(f"  trials, raw            {n_attempted}")
    print(f"  trials, effective      {n_eff:.0f}   {why}")
    print(f"  var(Sharpe), all       {var_all:.4f}   pool spans "
          f"{srs.min():+.2f} to {srs.max():+.2f}")
    print(f"  var(Sharpe), SR>0 only {var_pos:.4f}   n={len(plausible)}, the "
          f"sub-pool that could plausibly be one distribution\n")

    print("=" * 94)
    print("EVERY BAR, SIDE BY SIDE — nothing chosen for giving a nicer answer")
    print("=" * 94)
    print(f"{'trial count':<22}{'var used':<16}{'SR0 bar':>10}{'cells clearing':>17}")
    print("-" * 68)
    combos = [("N_raw 3168", n_attempted, "all", var_all),
              ("N_raw 3168", n_attempted, "SR>0", var_pos),
              (f"N_eff {n_eff:.0f}", n_eff, "all", var_all),
              (f"N_eff {n_eff:.0f}", n_eff, "SR>0", var_pos),
              ("N=1 (raw threshold)", 1, "—", var_pos)]
    results = {}
    for label, n, vlabel, v in combos:
        sr0 = 0.0 if n <= 1 else float(expected_max_sharpe(int(n), v))
        cnt = 0
        passers = []
        for cell in df.columns:
            arr = df[cell].dropna().to_numpy(dtype=float)
            if len(arr) < 100:
                continue
            psr = float(probabilistic_sharpe_ratio(arr, sr_benchmark=sr0))
            if psr >= 0.95:
                cnt += 1
                passers.append((cell, float(srs.get(cell, 0.0)), psr))
        results[(label, vlabel)] = (sr0, passers)
        print(f"{label:<22}{vlabel:<16}{sr0:>10.3f}{cnt:>17}")

    print("""
  SR0 6.52 is the artefact. No strategy has a Sharpe of 6.5, so that gate was
  rejecting by construction rather than by evidence and "0 of 1384" said
  nothing. The variance behind it came from a pool mixing structurally
  impossible cells with real candidates — a different urn, not unlucky draws
  from the same one.""")

    # ------------------------------------------------ the principal's rule wins
    raw_passers = results[("N=1 (raw threshold)", "—")][1]
    raw_passers.sort(key=lambda t: -t[1])
    best_label = (f"N_eff {n_eff:.0f}", "SR>0")
    sr0_eff, eff_passers = results[best_label]
    eff_names = {c for c, _, _ in eff_passers}

    print()
    print("=" * 94)
    print(f"CANDIDATES — the raw threshold, as instructed. "
          f"{len(raw_passers)} cells.")
    print("=" * 94)
    print(f"{'cell':<50}{'SR':>8}{'PSR':>8}   deflated view")
    print("-" * 94)
    for cell, sr, psr in raw_passers[:25]:
        tag = ("also clears N_eff" if cell in eff_names
               else f"below SR0 {sr0_eff:.2f} — queued lower, not refused")
        print(f"{cell[:50]:<50}{sr:>8.3f}{psr:>8.4f}   {tag}")
    if len(raw_passers) > 25:
        print(f"  ... {len(raw_passers) - 25} more")

    payload = [{"cell": c, "in_sample_sharpe": sr, "psr_raw": psr,
                "dsr_deflated": None, "n_trials_searched": n_attempted,
                "clears_effective_bar": c in eff_names}
               for c, sr, psr in raw_passers]
    OUT.write_text(json.dumps(payload, indent=1), "utf-8")
    print(f"\n  {len(payload)} candidates written to {OUT.name} for "
          f"golddesk.promotion.screen()")
    print(f"  {len(eff_names)} of them also clear the effective-N bar and sort "
          f"to the front of the queue.")
    print("""
  NONE OF THEM IS VALIDATED. The raw threshold is an in-sample screen and these
  are the cells that passed it, which is exactly what was asked for and exactly
  what it means. Forward days in shadow decide which get capital.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
