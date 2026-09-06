"""Where the cross-asset ceiling actually is -- measured, not assumed.

    python research/breadth_frontier.py
    python research/breadth_frontier.py --max-n 30 --json reports/breadth_frontier.json

THE QUESTION THIS ANSWERS, AND WHY SYMBOL COUNT IS THE WRONG ANSWER TO IT

"Trade every symbol" and "maximise cross-asset" sound like the same instruction. They are not,
and the arithmetic that separates them is the whole of this file.

The desk's total risk budget scales with sqrt(k_eff) (`gateway.heat_budget`), and

    k_eff = N / (1 + (N-1) * rho_bar)

is a function of CORRELATION, not of N. Push N up while rho stays high and k_eff barely moves:

     n    rho=0.6        rho=0.2
    20    1.6 (1.27x)    4.2 (2.04x)
   100    1.7 (1.29x)    4.8 (2.19x)

rho=0.6 is what USD-quoted FX majors actually look like -- twenty tickers expressing one
short-USD bet. The rho=0.6 column is FLAT: a hundred correlated instruments buy 1.29x where
twenty decorrelated ones buy 2.04x. Symbol count is not breadth. Breadth is what survives
correlation.

So the useful question is not "how many can we trade" but "which subset maximises k_eff, and
where does adding more stop paying". This greedily builds that subset and prints the frontier,
so the ceiling is a measured number with a named composition rather than an aspiration.

WHY GREEDY, AND WHAT IT IS NOT

Maximising k_eff over subsets is combinatorial; greedy forward selection is the standard
tractable approximation and is honest about being one. It is NOT claimed optimal. What it does
give -- and what actually matters here -- is the SHAPE: the point where marginal k_eff per added
instrument collapses, which is the point past which more symbols are multiplicity cost with no
diversification return.

IT MEASURES INSTRUMENT RETURNS, NOT STRATEGY RETURNS, AND THAT IS A REAL LIMITATION

Two instruments can be highly correlated while two STRATEGIES on them are not -- a breakout on
gold and a mean-reversion on gold are close to uncorrelated despite sharing every bar. So this
is an upper bound on the correlation the book will actually run, and therefore a LOWER bound on
achievable k_eff. It is the right tool for choosing which instruments to admit to the hunt; it
is the wrong tool for sizing a live book. `independence.measure_from_ledger` does that, from
realised sleeve returns, and stays the authority once sleeves exist.

MACRO DOES NOT APPEAR HERE, DELIBERATELY

Macro conditioning can raise a sleeve's edge. It cannot raise the CEILING, because the ceiling
is breadth x edge and macro is not breadth -- a macro overlay applied across a correlated book
moves every leg the same way and can REDUCE k_eff. Macro belongs downstream, as a per-cell
conditioning hypothesis facing the same gate as everything else, and the same t ~ 5 bar after
deflation. Adding it here would be adding a feature to a question about covariance.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mt5desk.independence import _Z, MIN_PAIRS, effective_bets
from mt5desk.universe import asset_class

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"

#: Minimum overlapping days before a pair contributes a correlation. Matches the module the
#: live book is sized by, so the frontier and the heat budget cannot disagree about what counts
#: as measured.
MIN_OVERLAP = 60


def _pairwise_z(series: dict[str, dict[str, float]],
                min_overlap: int) -> dict[tuple[str, str], tuple[float, int]]:
    """Every pair's Fisher-z and overlap, computed ONCE.

    The greedy loop below evaluates O(n) candidates at each of O(n) steps, and each evaluation
    needs the mean correlation over a subset. Calling `mean_pairwise_corr` there recomputes every
    pair from raw returns every time -- O(n^4) date-set intersections, which on 23 instruments
    ran for minutes without producing a line. The pair values do not change as the subset grows,
    so they are computed once here and the subset means become lookups.

    Same arithmetic as `independence.mean_pairwise_corr`, deliberately: z-space averaging because
    correlation is not additive, and the conservative bound taken from the THINNEST contributing
    overlap. It is duplicated rather than imported only because that function returns the
    aggregate and this needs the components.
    """
    import math
    out: dict[tuple[str, str], tuple[float, int]] = {}
    names = sorted(series)
    for i, a in enumerate(names):
        sa = series[a]
        for b in names[i + 1:]:
            sb = series[b]
            common = sorted(set(sa) & set(sb))
            if len(common) < min_overlap:
                continue                              # absent overlap, not zero correlation
            xs = [sa[d] for d in common]
            ys = [sb[d] for d in common]
            n = len(xs)
            mx, my = sum(xs) / n, sum(ys) / n
            vx = sum((x - mx) ** 2 for x in xs)
            vy = sum((y - my) ** 2 for y in ys)
            if vx <= 0 or vy <= 0:
                continue
            cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
            r = max(min(cov / (vx ** 0.5 * vy ** 0.5), 0.999999), -0.999999)
            # ABSOLUTE correlation, and this is the whole correction. A STRATEGY chooses its own
            # direction, so two instruments at rho=-0.8 carry exactly the information of two at
            # rho=+0.8 -- flip one leg and they are the same bet. Averaging SIGNED correlations
            # lets a near-inverse pair cancel a redundant one and report independence that does
            # not exist; the first version of this file did that and its greedy selector went
            # hunting for inverse pairs, seeding on a rho of -0.818 and calling it maximally
            # diversified. For instrument selection the quantity is |rho|.
            out[(a, b)] = (math.atanh(abs(r)), n)
    return out


def _subset_rho(chosen: list[str],
                zmat: dict[tuple[str, str], tuple[float, int]]) -> tuple[float | None, int, int]:
    """Upper-95% mean correlation over `chosen`, from the precomputed pair table."""
    import math
    zs: list[float] = []
    smallest = 0
    ordered = sorted(chosen)
    for i, a in enumerate(ordered):
        for b in ordered[i + 1:]:
            hit = zmat.get((a, b))
            if hit is None:
                continue
            z, n = hit
            zs.append(z)
            smallest = n if smallest == 0 else min(smallest, n)
    if len(zs) < MIN_PAIRS:
        return None, 0, 0
    se = 1.0 / math.sqrt(max(smallest - 3, 1))
    return math.tanh(sum(zs) / len(zs) + _Z * se), len(zs), smallest


def daily_returns(path: Path) -> dict[str, float] | None:
    """Close-to-close daily log returns for one instrument, keyed by ISO date.

    Log returns because they aggregate across time and are closer to symmetric than simple
    returns -- the correlation is being estimated for a covariance argument, not reported as
    performance.
    """
    import pandas as pd
    try:
        df = pd.read_parquet(path)
    except Exception:
        return None
    if "close" not in df or len(df) < 200:
        return None
    if "time" in df:
        idx = pd.to_datetime(df["time"], unit="s", utc=True)
    else:
        idx = pd.to_datetime(df.index, utc=True)
    s = pd.Series(df["close"].to_numpy(), index=idx).sort_index()
    daily = s.resample("1D").last().dropna()
    import numpy as np
    r = np.log(daily / daily.shift(1)).dropna()
    if len(r) < MIN_OVERLAP * 2:
        return None
    return {d.date().isoformat(): float(v) for d, v in r.items()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--max-n", type=int, default=0,
                    help="stop after N instruments (0 = run the full frontier)")
    ap.add_argument("--json", default="", help="also write the frontier to this path")
    args = ap.parse_args(argv)

    files = sorted(UNI.glob("*_H1.parquet"))
    if not files:
        print(f"REFUSED: no *_H1.parquet under {UNI}. Fetch history first.")
        return 2

    series: dict[str, dict[str, float]] = {}
    unusable: list[str] = []
    for f in files:
        sym = f.name.replace("_H1.parquet", "")
        r = daily_returns(f)
        if r is None:
            unusable.append(sym)
            continue
        series[sym] = r

    if len(series) < 3:
        print(f"REFUSED: only {len(series)} instrument(s) have usable return series; a frontier "
              f"needs at least three to have a shape.")
        return 3

    print(f"{len(series)} instruments with usable daily returns"
          + (f"; {len(unusable)} skipped ({', '.join(unusable[:6])}"
             + ("..." if len(unusable) > 6 else "") + ")" if unusable else ""))
    print()

    names = sorted(series)
    zmat = _pairwise_z(series, MIN_OVERLAP)
    print(f"{len(zmat)} instrument pairs clear the {MIN_OVERLAP}-day overlap floor", flush=True)

    # Seed with the pair that is LEAST correlated -- the frontier's shape is set early, and
    # seeding on anything else (longest history, alphabetical) builds the whole selection on an
    # arbitrary first choice.
    best_pair, best_rho = None, 2.0
    for (a, b) in zmat:
        rho, pairs, _ = _subset_rho([a, b], zmat)
        if rho is None or pairs == 0:
            continue
        if rho < best_rho:                    # rho is already |rho| -- see _pairwise_z
            best_pair, best_rho = (a, b), rho
    if best_pair is None:
        print("REFUSED: no instrument pair clears the overlap floor; correlations are UNMEASURED "
              "and a frontier built on absent data would be fiction.")
        return 4

    chosen = list(best_pair)
    frontier: list[dict] = []
    limit = args.max_n or len(series)

    print(f"{'n':>3} {'added':<10} {'class':<10} {'rho_bar':>8} {'k_eff':>7} "
          f"{'sqrt(k)':>8} {'d k_eff':>8}")
    prev_k = 1.0
    while True:
        rho, pairs, overlap = _subset_rho(chosen, zmat)
        if rho is None:
            break
        k = effective_bets(len(chosen), rho)
        frontier.append({"n": len(chosen), "added": chosen[-1],
                         "asset_class": asset_class(chosen[-1]),
                         "rho_bar_upper95": rho, "k_eff": k,
                         "sharpe_multiplier": k ** 0.5, "pairs": pairs,
                         "thinnest_overlap_days": overlap})
        print(f"{len(chosen):3d} {chosen[-1]:<10} {asset_class(chosen[-1]):<10} "
              f"{rho:8.3f} {k:7.2f} {k ** 0.5:8.2f} {k - prev_k:+8.2f}")
        prev_k = k
        if len(chosen) >= limit:
            break

        # Add whichever remaining instrument maximises k_eff of the resulting set. Selecting on
        # k_eff itself rather than on "lowest correlation to the set" is the point: the two
        # differ once N grows, and k_eff is the quantity the heat budget actually spends.
        best, best_k = None, -1.0
        for cand in names:
            if cand in chosen:
                continue
            r2, p2, _ = _subset_rho([*chosen, cand], zmat)
            if r2 is None or p2 == 0:
                continue
            k2 = effective_bets(len(chosen) + 1, r2)
            if k2 > best_k:
                best, best_k = cand, k2
        if best is None:
            break
        chosen.append(best)

    if not frontier:
        print("REFUSED: frontier is empty -- no subset cleared the overlap floor.")
        return 4

    peak = max(frontier, key=lambda r: r["k_eff"])
    print(f"\nCEILING: k_eff peaks at {peak['k_eff']:.2f} with {peak['n']} instruments "
          f"-> risk budget multiplier {peak['k_eff'] ** 0.5:.2f}x")
    comp: dict[str, int] = {}
    for row in frontier[:peak["n"]]:
        comp[row["asset_class"]] = comp.get(row["asset_class"], 0) + 1
    print(f"  composition: {', '.join(f'{c} x{n}' for c, n in sorted(comp.items()))}")
    if len(comp) <= 2:
        print("  ONE OR TWO CLASSES ONLY. This ceiling is capped by what the universe CONTAINS, "
              "not by what selection can achieve -- run research/discover_universe.py and see "
              "whether Fusion offers classes this desk has never held.")
    print("  NOTE: instrument correlation is an UPPER bound on strategy correlation, so this is "
          "a LOWER bound on achievable k_eff. Sizing authority stays with "
          "independence.measure_from_ledger once sleeves exist.")

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(
            {"frontier": frontier, "peak": peak, "min_overlap_days": MIN_OVERLAP,
             "n_instruments_available": len(series), "skipped": unusable}, indent=2),
            encoding="utf-8")
        print(f"\n-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
