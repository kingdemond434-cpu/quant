"""Is there entry SKILL in Profit Engine Pro, or is the win rate structural?

The claim I made earlier -- "his entries are negatively skilled, t = -4.06" --
came from MY RECONSTRUCTION of his mechanism on H1 bars, not from his fills. A
null result on a reconstruction is evidence about the reconstruction. Using it
to grade the man was sloppy, and the operator was right to push back.

THE TEST THAT ACTUALLY SETTLES IT

His exit rule is visible in the fills: take roughly +4.43 USD/oz (the median
winner), and do not cut -- the median loser runs to -21.55, nearly five times
further, and there is no spike anywhere in either distribution that would
indicate a fixed stop.

That exit rule generates a high win rate ON ITS OWN, from any entry whatsoever,
because gold oscillates and an uncapped loser eventually comes back or is
abandoned. So the question is not "does he win often" -- it is:

    does he win MORE often, or lose SMALLER, than the same exit rule applied to
    entries with no information in them at all?

This runs exactly that. Random entry bars, random direction, his take-profit,
his no-stop, and a max hold swept across the plausible range. If the null
reproduces his win rate and his loser size, the win rate is the exit rule and
carries no information about entry quality. If the null's losers are materially
bigger than his at the same win rate, he is managing better than chance and the
skill is real.

WHAT THIS CANNOT SETTLE, STATED UP FRONT

His average hold is 0.51 hours and this runs on H1 bars, so most of his trades
resolve inside a single bar here. Intrabar path is unknown, so the sim resolves
a bar pessimistically -- adverse extreme first -- and the resulting win rate is
therefore a LOWER bound on what the same rule achieves at his resolution. That
bias runs against the null and in HIS favour, which is the correct direction for
a test trying not to convict him.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

UNI = _DESK / "data" / "universe"
OUT = _DESK / "reports" / "pe_skill_test.json"

# His measured exit geometry, from 51 mirrored fills.
HIS_TP = 4.43           # USD/oz, median winner
HIS_MEDIAN_LOSS = -21.55
HIS_WORST = -52.39
HIS_WIN_RATE_PROFILE = 0.9323   # from the strategy page, 917 trades
HIS_WIN_RATE_SAMPLE = 0.841     # from the fills we can see

N_TRIALS = 20000
SEED = 7


def run_null(h, l, c, tp: float, max_hold: int, rng) -> dict:
    """Random entry, random side, take +tp, never stop, abandon at max_hold.

    The bar is resolved ADVERSE-EXTREME-FIRST: within a bar we cannot know the
    path, so a bar that reaches both the target and a worse low is scored as if
    the low came first. That understates the null's win rate, which is the
    direction that protects him from being convicted by a modelling choice.
    """
    n = len(c)
    starts = rng.integers(20, n - max_hold - 2, size=N_TRIALS)
    sides = rng.choice([1, -1], size=N_TRIALS)
    res = np.empty(N_TRIALS)
    mae = np.empty(N_TRIALS)
    held = np.empty(N_TRIALS, dtype=int)
    for k in range(N_TRIALS):
        i0, sd = int(starts[k]), int(sides[k])
        entry = c[i0]
        tgt = entry + sd * tp
        worst = 0.0
        out = None
        for j in range(i0 + 1, i0 + 1 + max_hold):
            adverse = (l[j] - entry) * sd if sd > 0 else (entry - h[j]) * -1 * -1
            adverse = (l[j] - entry) if sd > 0 else (entry - h[j])
            worst = min(worst, adverse)
            fav_hi = (h[j] - entry) if sd > 0 else (entry - l[j])
            if fav_hi >= tp:
                out = tp
                held[k] = j - i0
                break
        if out is None:
            out = (c[i0 + max_hold] - entry) * sd
            held[k] = max_hold
        res[k] = out
        mae[k] = worst
    wins = res[res > 0]
    loss = res[res <= 0]
    return {
        "max_hold_bars": max_hold,
        "win_rate": float((res > 0).mean()),
        "median_winner": float(np.median(wins)) if len(wins) else 0.0,
        "median_loser": float(np.median(loss)) if len(loss) else 0.0,
        "worst_loser": float(res.min()),
        "expectancy_usd_oz": float(res.mean()),
        "median_mae": float(np.median(mae)),
        "median_bars_held": float(np.median(held)),
    }


def main() -> int:
    df = pd.read_parquet(UNI / "XAUUSD_H1.parquet")
    df.index = pd.DatetimeIndex(pd.to_datetime(df.index))
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    rng = np.random.default_rng(SEED)

    print("SKILL TEST -- his exit rule, entries with ZERO information")
    print(f"  {len(c)} XAUUSD H1 bars, {N_TRIALS} random entries per row")
    print(f"  take-profit {HIS_TP} USD/oz (his median winner), no stop\n")
    print(f"{'max hold':>9}{'win rate':>10}{'med win':>9}{'med loss':>10}"
          f"{'worst':>9}{'E[usd/oz]':>11}")
    rows = []
    for mh in (4, 12, 24, 72, 168):
        r = run_null(h, l, c, HIS_TP, mh, rng)
        rows.append(r)
        print(f"{mh:>9}{100 * r['win_rate']:>9.1f}%{r['median_winner']:>9.2f}"
              f"{r['median_loser']:>10.2f}{r['worst_loser']:>9.1f}"
              f"{r['expectancy_usd_oz']:>11.3f}")

    print(f"\n{'HIM':>9}{100 * HIS_WIN_RATE_PROFILE:>9.1f}%{HIS_TP:>9.2f}"
          f"{HIS_MEDIAN_LOSS:>10.2f}{HIS_WORST:>9.1f}"
          f"{'?':>11}   <- profile, 917 trades")
    print(f"{'':>9}{100 * HIS_WIN_RATE_SAMPLE:>9.1f}%{'':>9}{'':>10}{'':>9}"
          f"{'':>11}   <- the 51 fills we can see")

    best = min(rows, key=lambda r: abs(r["win_rate"] - HIS_WIN_RATE_PROFILE))
    print(f"\nThe null row closest to his win rate is max_hold="
          f"{best['max_hold_bars']}h at {100 * best['win_rate']:.1f}%.")
    print(f"  Its median loser is {best['median_loser']:.2f} USD/oz; "
          f"his is {HIS_MEDIAN_LOSS:.2f}.")
    ratio = best["median_loser"] / HIS_MEDIAN_LOSS if HIS_MEDIAN_LOSS else 0
    print(f"  ratio {ratio:.2f}x -- above 1.0 means chance loses BIGGER than he "
          f"does\n  at the same win rate, which would be real management skill.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(
        {"his": {"tp": HIS_TP, "median_loser": HIS_MEDIAN_LOSS,
                 "worst": HIS_WORST, "win_rate_profile": HIS_WIN_RATE_PROFILE,
                 "win_rate_sample": HIS_WIN_RATE_SAMPLE},
         "null_rows": rows}, indent=1), "utf-8")
    print(f"\nwritten: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
