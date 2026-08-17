"""Portfolio robustness: block bootstrap + conditional correlation on stress days
+ Drawdown Complementarity Score.

Uses the shared sleeve loader (portfolio_projection) -> aligned daily-R matrix.

Outputs:
  - block-bootstrapped net Sharpe distribution (blocks: 5d week / 21d month /
    252d year), median + 2.5/97.5 pct
  - per-sleeve correlation with the portfolio: full-sample vs worst-decile days
  - Drawdown Complementarity Score = sleeve mean R on portfolio worst-decile days
    (a sleeve that earns during the book's worst days is worth more than its
    overall expectancy suggests)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from portfolio_projection import build_daily, build_sleeves  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
REPS = 2000


def block_bootstrap(port: pd.Series, block: int, reps: int, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = port.to_numpy()
    n = len(x)
    nblocks = int(np.ceil(n / block))
    out = np.empty(reps)
    for r in range(reps):
        starts = rng.integers(0, n - block + 1, size=nblocks)
        idx = np.concatenate([np.arange(s, s + block) for s in starts])[:n]
        sample = x[idx]
        m, sd = sample.mean(), sample.std(ddof=1)
        out[r] = m / sd * np.sqrt(252) if sd > 0 else 0.0
    return out


def main() -> None:
    sleeves = build_sleeves()
    daily = build_daily(sleeves)
    port = daily.sum(axis=1)
    names = list(daily.columns)

    full_sharpe = port.mean() / port.std(ddof=1) * np.sqrt(252)

    worst_mask = port <= np.quantile(port, 0.10)
    best_mask = port >= np.quantile(port, 0.90)

    print(f"{'sleeve':<26} {'fullCorr':>8} {'worstCorr':>9} {'bestCorr':>8} "
          f"{'worstExp':>8} {'nWorst':>6} {'complement':>10}")
    rows = []
    for c in names:
        s = daily[c]
        full_c = float(s.corr(port))
        wc = float(s[worst_mask].corr(port[worst_mask])) if worst_mask.sum() > 3 else float("nan")
        bc = float(s[best_mask].corr(port[best_mask])) if best_mask.sum() > 3 else float("nan")
        wexp = float(s[worst_mask].mean())
        comp = wexp - float(s.mean())
        rows.append(dict(sleeve=c, full_corr=full_c, worst_corr=wc, best_corr=bc,
                         worst_exp=wexp, n_worst=int(worst_mask.sum()), complement=comp))
        print(f"{c:<26} {full_c:8.3f} {wc:9.3f} {bc:8.3f} {wexp:+8.3f} "
              f"{int(worst_mask.sum()):6d} {comp:+10.3f}")

    rows.sort(key=lambda r: -r["complement"])
    print("\ncomplementarity ranking (worst-decile earners first):")
    for r in rows:
        print(f"  {r['sleeve']:<26} worstExp {r['worst_exp']:+.3f}  "
              f"vs overall, net gain {r['complement']:+.3f}R/day on stress days")

    print(f"\nfull-sample net Sharpe: {full_sharpe:.2f}")
    for block, label in ((5, "week"), (21, "month"), (252, "year")):
        sh = block_bootstrap(port, block, REPS)
        med, lo, hi = np.median(sh), np.percentile(sh, 2.5), np.percentile(sh, 97.5)
        print(f"block bootstrap ({label}, {block}d): Sharpe median {med:.2f} "
              f"[{lo:.2f}, {hi:.2f}] | P(Sharpe<1)={np.mean(sh < 1)*100:.1f}%")

    out = dict(sleeves=rows, full_sharpe=full_sharpe,
               bootstrap={f"{b}d": {"med": float(np.median(
                   block_bootstrap(port, b, REPS, seed=7 + b))),
                   "lo": float(np.percentile(block_bootstrap(port, b, REPS, seed=7 + b), 2.5)),
                   "hi": float(np.percentile(block_bootstrap(port, b, REPS, seed=7 + b), 97.5))}
                   for b in (5, 21, 252)})
    (BASE / "reports" / "portfolio_bootstrap.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    print("\n-> reports/portfolio_bootstrap.json")


if __name__ == "__main__":
    main()