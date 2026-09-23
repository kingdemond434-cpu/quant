"""Two tickers, one bet. The orthogonality hole a parameter-hash quota cannot see.

THE DESK ALREADY GUARDS THE WRONG HALF OF THIS. The param-hash quota catches the SAME PARAMETERS
ON DIFFERENT SYMBOLS -- four `overnight_gap_decay` sleeves sharing one hash across four
instruments. It cannot catch DIFFERENT SYMBOLS THAT ARE THE SAME UNDERLYING, and a currency peg
makes them exactly that.

MEASURED 2026-09-15, on a sleeve the allocator FUNDS:

    CHFDKK vs EURCHF     rho = -0.874 over 37,316 hourly returns
    CHFDKK vs EURDKK     rho = +0.108
    EURDKK hourly sd     0.49 bp

The Danish krone is pegged to the euro and managed far tighter than its ERM II band, so DKK is a
euro with a different name: EURDKK barely moves, the DKK leg of CHFDKK contributes essentially
nothing, and CHFDKK is approximately CHFEUR wearing a different ticker -- with a wider spread and
worse financing than the pair it duplicates.

AND THEN THE MEASUREMENT CORRECTED THE STORY, which is the reason to run it rather than reason
about it. The funded book does NOT hold CHFEUR, so CHFDKK double-counts nothing today: across the
eleven funded sleeves there is NO pair above 0.85 at all. The strongest are EURNOK~GBPNOK at
+0.791, GBPMXN~USDMXN at +0.722 and CADJPY~USDJPY at +0.707 -- high, and none of them a duplicate.

WHAT IS ACTUALLY CONCENTRATING IS THE LEG, NOT THE TICKER. Four of eleven funded sleeves carry a
CHF leg; three carry CAD, three JPY, three GBP. Sleeves sharing a leg share that leg's factor
whatever their pairwise return correlation says, which is exactly why `EFFECTIVE_BREADTH` takes
the WORSE of its return-correlation and currency-exposure readings. So this report prints both:
the duplicate pairs it was written to find, and the leg census that turned out to be the binding
shape. A clean duplication result is not a clean breadth result, and printing only breaches would
have made the two indistinguishable.

WHY THIS IS A BREADTH PROBLEM AND NOT A TIDINESS PROBLEM. `pf_allocation` fails its own proof --
the dynamic book scores a worse robust tail than the `robust_kelly` baseline, so the gateway
deploys the baseline and every piece of allocator machinery is inert. The reason the tail is bad
is concentration: n_eff ~5.7 against 50 nominal sleeves, p_dd_over_tolerance 0.4375. Each pair of
tickers that is secretly one bet is a piece of that gap, and it is the cheapest piece to find.

MEASURED FROM BARS, NEVER FROM A LIST OF PEGS. A hardcoded peg table is wrong the day a peg
breaks -- and a peg breaking is precisely the day the duplication stops being duplication and the
position becomes something else entirely. The correlation is the measurement; the peg is only the
explanation.

    python scripts/check_pegged_duplicates.py
    python scripts/check_pegged_duplicates.py --threshold 0.9
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

ALLOCATION = DESK / "reports" / "pf_allocation.json"
OUT = DESK / "reports" / "PEGGED_DUPLICATES.json"

#: |rho| on hourly returns above which two instruments are one bet for breadth purposes. 0.85 is
#: deliberately below the measured CHFDKK/EURCHF 0.874: the point is to catch the class, and a
#: threshold set just above the one case that prompted it would catch exactly that case forever.
DUPLICATE_RHO = 0.85
#: Overlapping observations before a correlation is a correlation.
MIN_OBS = 2000


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default if default is not None else {}


def _instrument(sleeve: str, universe: set[str]) -> str | None:
    """The instrument a sleeve name carries. Registry-checked, never guessed from a prefix."""
    head = str(sleeve).split("_")[0].upper()
    if head in universe:
        return head
    folded = {s.upper(): s for s in universe}
    return folded.get(head)


def check(threshold: float = DUPLICATE_RHO) -> dict[str, Any]:
    import numpy as np
    import pandas as pd

    from research import proposer_common as pc

    universe = set(_read(DESK / "data" / "universe" / "universe.json", {}))
    book = (_read(ALLOCATION, {}) or {}).get("book") or {}
    funded: dict[str, str] = {}
    unresolved: list[str] = []
    for sleeve in book:
        sym = _instrument(sleeve, universe)
        if sym:
            funded[str(sleeve)] = sym
        else:
            unresolved.append(str(sleeve))

    rets: dict[str, Any] = {}
    for sym in sorted(set(funded.values())):
        d = pc.bars(sym)
        if d is None or len(d) < MIN_OBS:
            continue
        rets[sym] = np.log(d["close"].astype(float)).diff()

    pairs: list[dict[str, Any]] = []
    for a, b in combinations(sorted(rets), 2):
        j = pd.concat([rets[a], rets[b]], axis=1, join="inner").dropna()
        if len(j) < MIN_OBS:
            continue
        rho = float(j.corr().iloc[0, 1])
        if not np.isfinite(rho) or abs(rho) < threshold:
            continue
        sleeves_a = sorted(s for s, v in funded.items() if v == a)
        sleeves_b = sorted(s for s, v in funded.items() if v == b)
        heat = sum(float(book.get(s) or 0.0) for s in sleeves_a + sleeves_b)
        pairs.append({
            "symbols": [a, b], "rho": round(rho, 4), "n_obs": len(j),
            "sleeves": sleeves_a + sleeves_b,
            "book_heat_involved": round(heat, 6),
            "verdict": "ONE_BET",
            "why": (f"|rho| {abs(rho):.3f} over {len(j)} hourly returns. These are two tickers "
                    f"and approximately one bet; the allocator counts them as two, and the "
                    f"parameter-hash quota cannot see it because the parameters differ."),
        })
    pairs.sort(key=lambda p: -abs(float(p["rho"])))

    # THE TOP PAIRS REGARDLESS OF THE THRESHOLD, and the currency LEG census beside them.
    # Reporting only breaches makes a clean run indistinguishable from a run that measured
    # nothing, and it hides the shape that is actually binding here: the funded book holds no
    # pair above 0.85, and four of its eleven sleeves share a CHF leg. Duplication by TICKER is
    # not the concentration -- duplication by LEG is.
    top: list[dict[str, Any]] = []
    for a, b in combinations(sorted(rets), 2):
        j = pd.concat([rets[a], rets[b]], axis=1, join="inner").dropna()
        if len(j) < MIN_OBS:
            continue
        rho = float(j.corr().iloc[0, 1])
        if np.isfinite(rho):
            top.append({"symbols": [a, b], "rho": round(rho, 4), "n_obs": len(j)})
    top.sort(key=lambda r: -abs(float(r["rho"])))

    legs: dict[str, list[str]] = {}
    for sleeve, sym in sorted(funded.items()):
        if len(sym) == 6 and sym.isalpha():
            for leg in (sym[:3].upper(), sym[3:].upper()):
                legs.setdefault(leg, []).append(sleeve)
    shared = {k: v for k, v in sorted(legs.items(), key=lambda kv: -len(kv[1])) if len(v) > 1}

    return {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "rule": ("measured from BARS, never from a peg table: a hardcoded peg list is wrong on "
                 "the day a peg breaks, and that is precisely the day the duplication stops "
                 "being duplication. The correlation is the measurement; the peg is only the "
                 "explanation."),
        "threshold": threshold,
        "min_obs": MIN_OBS,
        "n_funded_sleeves": len(funded),
        "n_instruments": len(rets),
        "unresolved_sleeves": unresolved,
        "n_duplicate_pairs": len(pairs),
        "duplicate_pairs": pairs,
        "top_pairs_measured": top[:12],
        "shared_currency_legs": shared,
        "leg_note": ("a clean ticker-duplication result is not a clean breadth result. The "
                     "funded book holds no pair above the threshold and still concentrates: "
                     "sleeves sharing a currency LEG share that leg's factor whatever their "
                     "pairwise return correlation says, which is why EFFECTIVE_BREADTH takes the "
                     "WORSE of the return-correlation and currency-exposure readings."),
        "why_it_matters": ("pf_allocation fails its own proof because the dynamic book's robust "
                           "tail is worse than the robust_kelly baseline, so the gateway deploys "
                           "the BASELINE and the allocator is inert. The tail is bad because "
                           "n_eff is ~5.7 against 50 nominal sleeves. Every pair here is a piece "
                           "of that gap, and the cheapest piece to find."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--threshold", type=float, default=DUPLICATE_RHO)
    args = ap.parse_args(argv)

    doc = check(threshold=args.threshold)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")

    print(f"pegged duplicates: {doc['n_funded_sleeves']} funded sleeve(s) over "
          f"{doc['n_instruments']} instrument(s) -> {doc['n_duplicate_pairs']} pair(s) at "
          f"|rho| >= {args.threshold}")
    for p in doc["duplicate_pairs"]:
        print(f"  {p['symbols'][0]:8} ~ {p['symbols'][1]:8} rho={p['rho']:+.3f} "
              f"n={p['n_obs']:6}  heat={p['book_heat_involved']:.4f}")
        for s in p["sleeves"]:
            print(f"      {s}")
    if not doc["duplicate_pairs"] and doc["top_pairs_measured"]:
        print("  none above the bar. The strongest measured pairs in the FUNDED book:")
        for t in doc["top_pairs_measured"][:5]:
            print(f"    {t['symbols'][0]:8} ~ {t['symbols'][1]:8} rho={t['rho']:+.3f} "
                  f"n={t['n_obs']}")
    if doc["shared_currency_legs"]:
        print("  shared currency LEGS (concentration a ticker correlation does not show):")
        for leg, sleeves in list(doc["shared_currency_legs"].items())[:5]:
            print(f"    {leg}: {len(sleeves)} sleeve(s)  {', '.join(s[:26] for s in sleeves[:3])}")
    if doc["unresolved_sleeves"]:
        print(f"  {len(doc['unresolved_sleeves'])} sleeve(s) name no registry instrument: "
              f"{', '.join(doc['unresolved_sleeves'][:4])}")
    print(f"  -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
