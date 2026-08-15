#!/usr/bin/env python3
"""LIVE cross-mechanism correlation -- the one number every growth projection rests on.

WHAT THIS MEASURES AND WHY IT IS THE ONLY THING WORTH MEASURING RIGHT NOW

The desk wants combined Sharpe out of several individually-weak edges. Under equicorrelation, N
streams at average pairwise correlation rho are worth

    k_eff = N / (1 + (N-1)*rho)      independent bets
    S_combined = s * sqrt(k_eff)     combined Sharpe

and that expression CONVERGES: as N grows, k_eff -> 1/rho. So the combined Sharpe has a hard
ceiling of `s / sqrt(rho)` NO MATTER HOW MANY SLEEVES ARE ADDED. At the book's measured s = 0.48:

    rho 0.05  ->  k_eff cap 20.0  ->  ceiling S 2.15   -- 40%/yr reachable
    rho 0.10  ->  k_eff cap 10.0  ->  ceiling S 1.52   -- reachable
    rho 0.20  ->  k_eff cap  5.0  ->  ceiling S 1.07   -- 40%/yr UNREACHABLE at any n
    rho 0.375 ->  k_eff cap  2.7  ->  ceiling S 0.78   -- unreachable

ORTHOGONALITY IS THE BINDING CONSTRAINT, NOT SLEEVE COUNT. Past the ceiling, adding sleeves buys
literally nothing, and a desk that keeps adding price-pattern variants is building a large pile of
correlated noise and calling it a portfolio.

WHAT IS ALREADY KNOWN, SO THIS IS NOT STARTING FROM ZERO

`measure_cross_mechanism_corr.py` measured this on 2026-08-05 over 920 BACKTEST return streams
grouped into 19 mechanisms: mean absolute off-diagonal rho 0.375, participation-ratio k_eff 4.08,
ceiling 2.02x. That is a real measurement and it says the ceiling is low.

What it is NOT is a measurement of THESE sleeves, LIVE, on overlapping forward history. Backtest
streams share fitted parameters and a common sample; live streams do not. The number can move.
This script measures the live one so the projections stop resting on the backtest one.

**GO IN EXPECTING TO CONFIRM THE WALL.** The honest success criterion is whether live rho comes in
UNDER 0.10 -- that is the threshold where 40%/yr exists at all. Anything at or above 0.20 settles
the question in the other direction, and settling it is worth as much as opening it.

THE PART THAT MAKES THIS HARD, AND WHY THE REPORT LEADS WITH IT

A correlation estimated from a few weeks of daily returns is extremely noisy. The standard error
of a Pearson correlation is approximately

    se(rho) ~= (1 - rho^2) / sqrt(n - 3)

At n = 20 daily observations and true rho = 0.2, se is 0.23 -- the interval spans "independent" to
"hopeless". This script therefore refuses to publish a verdict below a minimum sample, reports the
interval on every pair, and states how many observations would be needed to separate the measured
value from the decision thresholds. A confident rho from three weeks of data would be exactly the
kind of number that gets acted on and should not be.

    python scripts/track_sleeve_correlation.py
    python scripts/track_sleeve_correlation.py --min-obs 40 --target-sharpe 1.14
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
import sys
from pathlib import Path

# The assignment must not sit BETWEEN the imports: ruff's E402 tolerates a bare sys.path guard
# and not an intervening statement, so `_ROOT` is bound after the import block instead.
if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
import math
from datetime import UTC, datetime
from itertools import combinations
from typing import Any

#: Sleeve/mechanism return streams. One file per mechanism, or one file keyed by mechanism.
#: Gitignored on purpose -- these are live results, not source.
_ROOT = Path(__file__).resolve().parents[1]
_RETURNS = _ROOT / "data" / "sleeve_returns.json"
_OUT = _ROOT / "reports" / "sleeve_correlation.json"

#: Below this many OVERLAPPING observations, a pairwise correlation is not a measurement. At n=20
#: the standard error is around 0.23, which spans every decision threshold that matters.
MIN_OBS = 30

#: The book's measured per-sleeve Sharpe. Not a target -- the observed starting point that the
#: ceiling arithmetic is applied to.
BOOK_SHARPE = 0.48

#: Combined Sharpe required for 40%/yr at the book's vol and borrow rate. Stated so the verdict is
#: against a number fixed in advance rather than one chosen after seeing rho.
TARGET_SHARPE = 1.14


def _pearson(a: list[float], b: list[float]) -> float | None:
    n = len(a)
    if n < 3:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va <= 0 or vb <= 0:
        # A CONSTANT STREAM HAS NO CORRELATION, not zero correlation. A sleeve that never traded
        # returns a flat line, and calling that "uncorrelated" would credit it with diversification
        # it cannot provide -- the single easiest way to manufacture a good-looking k_eff.
        return None
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b, strict=True))
    return cov / math.sqrt(va * vb)


def _se(rho: float, n: int) -> float:
    """Approximate standard error of a Pearson correlation."""
    return (1.0 - rho ** 2) / math.sqrt(max(1, n - 3))


def _fisher_ci(rho: float, n: int, z: float = 1.96) -> tuple[float, float]:
    """Fisher z interval -- correct near +/-1 where the normal approximation is not."""
    if n <= 3 or abs(rho) >= 1.0:
        return (-1.0, 1.0)
    zr = 0.5 * math.log((1 + rho) / (1 - rho))
    se = 1.0 / math.sqrt(n - 3)
    lo, hi = zr - z * se, zr + z * se
    return (math.tanh(lo), math.tanh(hi))


def _align(streams: dict[str, dict[str, float]]) -> tuple[list[str], dict[str, list[float]]]:
    """Restrict every stream to the dates ALL of them share.

    Pairwise-complete correlation on differently-dated streams is how a matrix ends up
    non-positive-definite and k_eff ends up meaningless. Common dates only, and the count is
    reported so a thin overlap is visible rather than inferred.
    """
    if not streams:
        return [], {}
    common = set.intersection(*(set(v.keys()) for v in streams.values()))
    dates = sorted(common)
    return dates, {k: [float(v[d]) for d in dates] for k, v in streams.items()}


def analyse(streams: dict[str, dict[str, float]], *, min_obs: int = MIN_OBS,
            book_sharpe: float = BOOK_SHARPE,
            target_sharpe: float = TARGET_SHARPE) -> dict[str, Any]:
    dates, series = _align(streams)
    n = len(dates)
    names = sorted(series)
    rep: dict[str, Any] = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "mechanisms": names, "n_mechanisms": len(names),
        "overlapping_observations": n,
        "first": dates[0] if dates else None, "last": dates[-1] if dates else None,
        "book_sharpe": book_sharpe, "target_sharpe": target_sharpe,
        "pairs": [], "usable": False,
    }

    if len(names) < 2:
        rep["verdict"] = (f"{len(names)} stream(s). Correlation needs two, and the whole question "
                          "is whether DIFFERENT mechanisms move together.")
        return rep
    if n < min_obs:
        rep["verdict"] = (
            f"UNUSABLE -- {n} overlapping observations, below the {min_obs} floor. "
            f"se(rho) at n={n} is about {_se(0.2, n):.2f}, which spans every threshold that "
            f"matters: 0.10 (40%/yr reachable) and 0.20 (unreachable at any sleeve count). "
            f"A number published here would be acted on and should not be.")
        return rep

    rhos: list[float] = []
    for a, b in combinations(names, 2):
        r = _pearson(series[a], series[b])
        if r is None:
            rep["pairs"].append({"a": a, "b": b, "rho": None,
                                 "why": "a stream is constant -- it never traded, which is not "
                                        "the same as being uncorrelated"})
            continue
        lo, hi = _fisher_ci(r, n)
        rhos.append(r)
        rep["pairs"].append({"a": a, "b": b, "rho": round(r, 4),
                             "ci95": [round(lo, 4), round(hi, 4)],
                             "se": round(_se(r, n), 4)})

    if len(rhos) < 1:
        rep["verdict"] = "no pair had two live streams to compare"
        return rep

    N = len(names)
    mean_rho = sum(rhos) / len(rhos)
    mean_abs = sum(abs(x) for x in rhos) / len(rhos)

    # BOTH are reported, and the gap between them is the finding when it is large. A mean of +0.005
    # across pairs running from -0.85 to +0.96 reads as "independent" and is CANCELLATION, not
    # diversification -- two correlated blocs pointing opposite ways. The absolute mean is the one
    # that governs how much risk actually diversifies.
    def keff(rho: float) -> float:
        d = 1.0 + (N - 1) * rho
        return max(1.0, min(float(N), N / d)) if d > 0 else float(N)

    k_signed, k_abs = keff(mean_rho), keff(mean_abs)
    ceil_signed = book_sharpe * math.sqrt(k_signed)
    ceil_abs = book_sharpe * math.sqrt(k_abs)
    # The asymptote: what no number of sleeves can beat.
    asym = (book_sharpe / math.sqrt(mean_abs)) if mean_abs > 0 else float("inf")

    rep.update({
        "usable": True,
        "mean_rho": round(mean_rho, 4),
        "mean_abs_rho": round(mean_abs, 4),
        "rho_min": round(min(rhos), 4), "rho_max": round(max(rhos), 4),
        "k_eff_signed": round(k_signed, 2), "k_eff_abs": round(k_abs, 2),
        "combined_sharpe_signed": round(ceil_signed, 3),
        "combined_sharpe_abs": round(ceil_abs, 3),
        "ceiling_at_infinite_sleeves": (None if math.isinf(asym) else round(asym, 3)),
        "backtest_reference": {"mean_abs_rho": 0.375, "k_eff": 4.08,
                               "source": "measure_cross_mechanism_corr.py, 2026-08-05, "
                                         "920 backtest streams / 19 mechanisms"},
    })

    reach = "REACHABLE" if (not math.isinf(asym) and asym >= target_sharpe) else "UNREACHABLE"
    need_n = None
    if reach == "REACHABLE":
        # How many sleeves at THIS rho to actually get there.
        want_k = (target_sharpe / book_sharpe) ** 2
        if mean_abs > 0 and want_k < 1.0 / mean_abs:
            need_n = math.ceil(want_k * (1 - mean_abs) / (1 - want_k * mean_abs))
    rep["sleeves_needed"] = need_n
    rep["verdict"] = (
        f"live mean |rho| = {mean_abs:.3f} over {N} mechanisms, {n} overlapping days. "
        f"k_eff {k_abs:.2f}, combined Sharpe {ceil_abs:.2f}. "
        f"Ceiling at infinite sleeves is {'unbounded' if math.isinf(asym) else f'{asym:.2f}'}, so "
        f"S={target_sharpe:.2f} is {reach}"
        + (f" -- about {need_n} sleeves at this rho." if need_n else
           f". Adding sleeves past k_eff {1/mean_abs:.1f} buys nothing." if mean_abs > 0 else "."))
    return rep


def render(rep: dict[str, Any]) -> str:
    L = [f"LIVE CROSS-MECHANISM CORRELATION  ({rep['updated'][:19]}Z)", ""]
    L.append(f"  mechanisms            {rep['n_mechanisms']}  "
             f"{', '.join(rep.get('mechanisms', [])) or '-'}")
    L.append(f"  overlapping days      {rep['overlapping_observations']}"
             + (f"   {rep['first']} .. {rep['last']}" if rep.get("first") else ""))
    if not rep.get("usable"):
        L += ["", "  " + rep.get("verdict", "no verdict")]
        return "\n".join(L)

    L += ["", "PAIRWISE", ""]
    for p in rep["pairs"]:
        if p.get("rho") is None:
            L.append(f"  {p['a'][:26]:<26} {p['b'][:26]:<26}   n/a  {p.get('why','')[:44]}")
            continue
        lo, hi = p["ci95"]
        L.append(f"  {p['a'][:26]:<26} {p['b'][:26]:<26} {p['rho']:>+7.3f}  "
                 f"95% [{lo:+.2f}, {hi:+.2f}]")

    L += ["", "AGGREGATE", "",
          f"  mean rho (signed)     {rep['mean_rho']:+.4f}   k_eff {rep['k_eff_signed']:.2f}   "
          f"-> S {rep['combined_sharpe_signed']:.2f}",
          f"  mean |rho|            {rep['mean_abs_rho']:.4f}   k_eff {rep['k_eff_abs']:.2f}   "
          f"-> S {rep['combined_sharpe_abs']:.2f}   <- THE ONE THAT GOVERNS",
          f"  range                 {rep['rho_min']:+.3f} .. {rep['rho_max']:+.3f}"]
    if abs(rep["mean_rho"]) < 0.5 * rep["mean_abs_rho"]:
        L.append("  NOTE: the signed mean is far below the absolute mean. That is CANCELLATION")
        L.append("  between opposing blocs, not independence, and it does not diversify risk.")
    ref = rep["backtest_reference"]
    L += ["", f"  backtest reference    mean |rho| {ref['mean_abs_rho']:.3f}, k_eff {ref['k_eff']}",
          f"                        {ref['source']}"]
    L += ["", "VERDICT", "", "  " + rep["verdict"], "",
          "  A correlation is not a constant. It rises in exactly the regime where",
          "  diversification is needed -- a liquidation cascade moves every crypto",
          "  mechanism together. Treat this as an upper bound on your independence,",
          "  measured in calm, not a property you own."]
    return "\n".join(L)


def _load(path: Path) -> dict[str, dict[str, float]]:
    if not path.exists():
        return {}
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    if isinstance(doc, dict) and isinstance(doc.get("streams"), dict):
        doc = doc["streams"]
    return {k: v for k, v in doc.items() if isinstance(v, dict) and v}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--returns", default=str(_RETURNS),
                    help="JSON: {mechanism: {YYYY-MM-DD: daily_return}}")
    ap.add_argument("--min-obs", type=int, default=MIN_OBS)
    ap.add_argument("--book-sharpe", type=float, default=BOOK_SHARPE)
    ap.add_argument("--target-sharpe", type=float, default=TARGET_SHARPE)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    streams = _load(Path(a.returns))
    if not streams:
        print(f"no return streams at {a.returns}\n\n"
              "  Expected: {\"mechanism_name\": {\"2026-08-15\": 0.0031, ...}, ...}\n\n"
              "  Nothing to measure yet. Three of the four census families only started\n"
              "  publishing signals recently, so overlapping live history is what this is\n"
              "  waiting on -- and elapsed time is the only thing that produces it.\n\n"
              "  Until then the backtest figure stands: mean |rho| 0.375, k_eff 4.08,\n"
              "  combined Sharpe ceiling 0.78 at the book's s=0.48. On that number,\n"
              "  40%/yr is unreachable at ANY sleeve count.")
        return

    rep = analyse(streams, min_obs=a.min_obs, book_sharpe=a.book_sharpe,
                  target_sharpe=a.target_sharpe)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")
    print(json.dumps(rep, indent=2) if a.json else render(rep))
    print(f"\n-> {_OUT}")


if __name__ == "__main__":
    main()
