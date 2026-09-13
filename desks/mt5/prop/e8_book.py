"""WHICH 24 SLEEVES THE E8 ACCOUNT TRADES, chosen from the certified survivors this venue lists.

Not a new hunt and not a new certificate. Every row here already holds a ten-gate universal
certificate; this file only decides which of them the E8 lane runs, and refuses the ones the
venue cannot fill.

THREE FILTERS, IN THIS ORDER, and the order is the point:

  1. THE VENUE MUST LIST IT. E8's catalogue is 46 instruments with no Scandi or EM crosses, so
     ten of the sixty-one certificates are unfillable here -- and they are the ten best by
     expected value, including `carry`'s only certificate (CHFNOK, ev 0.5929). An order on an
     instrument the venue does not list is not a small trade, it is a rejected one.
  2. DIVERSITY BEFORE EXPECTANCY. Taking the top 24 by ev would take 24 `discovered` rows,
     because `discovered` is 33 of the 51 survivors. The pass probability of this account is
     driven by how many INDEPENDENT bets it holds, not by the mean of their expectancies, so the
     selection round-robins across mechanisms and only then ranks within one.
  3. ONE ROW PER (mechanism, symbol). Two certificates on the same mechanism and the same
     instrument are one bet with two names -- exactly the breadth illusion `orthogonality.py`
     measures, bought on purpose.

SIZE IS NOT CHOSEN HERE. `RISK_FRAC` is the principal's decision recorded in docs/PROP_FIRM_E8.md
and re-derived under TAIL-implied correlation, and the executor reads it from this module so
there is one number in one place.

Artifact: desks/mt5/reports/E8_BOOK.json
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
OUT = DESK / "reports" / "E8_BOOK.json"

#: HOW MANY SLEEVES, and it is a breadth decision rather than a taste one. Every certified sleeve
#: fires in the asia window, so the whole book lands at once into a 2.5% daily floor; widening the
#: book at a smaller per-sleeve size is what raises pass probability, and 24 x 0.05% keeps gross
#: simultaneous exposure at 1.2% -- under half the daily wall, before any stand-down.
MAX_SLEEVES = 24

#: RISK PER TRADE, as a fraction of the $100,000 initial balance. 0.05%, i.e. $50.
#:
#: Measured under TAIL-implied correlation, not linear. `orthogonality.py` on sleeve returns
#: reports mean pairwise pearson 0.155 against a tail-implied 0.251 -- a 1.62x multiplier -- so
#: this book's structural rho of 0.357 is about 0.58 in the decile that decides whether the daily
#: floor is touched. At 0.07% the pass probability falls from 95.0% (linear) to 84.0% (tail); at
#: 0.05% it is 96.3% and 91.9%. The smaller size is the one that survives being wrong about the
#: correlation, which is the only assumption here that has never been measured on live fills.
RISK_FRAC = 0.0005


def _load_survivors() -> list[dict[str, Any]]:
    doc = json.loads(SURVIVORS.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for key, val in (doc.get("survivors") or {}).items():
        spec = val.get("shadow_spec") or {}
        sym = str(spec.get("symbol") or val.get("sym") or "").upper()
        fam = str(spec.get("family") or "")
        if not sym or not fam:
            continue
        rows.append({
            "key": key, "symbol": sym, "family": fam,
            "selector": spec.get("selector") or "asia",
            "params": {k: v for k, v in spec.items()
                       if k not in ("symbol", "family", "selector", "is_universe", "hunt")},
            "ev": ((val.get("gates") or {}).get("expected_value") or {}).get("ev"),
            "days": val.get("days"),
            "n_trials": ((val.get("gates") or {}).get("deflated_sharpe") or {}).get("n_trials"),
        })
    return rows


def select(tradeable: set[str] | None = None, max_sleeves: int = MAX_SLEEVES) -> dict[str, Any]:
    """The book, plus everything refused and why. An absence here is always named (L1.28a)."""
    rows = _load_survivors()
    blocked = []
    live = []
    for r in rows:
        if tradeable is not None and r["symbol"] not in tradeable:
            blocked.append({**r, "why": "not listed by the venue"})
        else:
            live.append(r)

    # one row per (mechanism, symbol): the best ev wins, the rest are named as duplicates
    best: dict[tuple[str, str], dict[str, Any]] = {}
    dupes = []
    for r in sorted(live, key=lambda x: -(x["ev"] or -9)):
        k = (r["family"], r["symbol"])
        if k in best:
            dupes.append({**r, "why": f"duplicate of {best[k]['key']} "
                                      "on the same mechanism+symbol"})
            continue
        best[k] = r

    # round-robin across mechanisms, best-first within each
    by_fam: dict[str, list[dict[str, Any]]] = {}
    for r in best.values():
        by_fam.setdefault(r["family"], []).append(r)
    for fam in by_fam:
        by_fam[fam].sort(key=lambda x: -(x["ev"] or -9))
    chosen: list[dict[str, Any]] = []
    i = 0
    while len(chosen) < max_sleeves:
        took = False
        for fam in sorted(by_fam, key=lambda f: -len(by_fam[f])):
            if i < len(by_fam[fam]) and len(chosen) < max_sleeves:
                chosen.append(by_fam[fam][i])
                took = True
        if not took:
            break
        i += 1

    fams: dict[str, int] = {}
    for r in chosen:
        fams[r["family"]] = fams.get(r["family"], 0) + 1
    evs = [r["ev"] for r in chosen if r["ev"] is not None]
    return {
        "generated_utc": datetime.now(UTC).isoformat(),
        "risk_frac": RISK_FRAC,
        "max_sleeves": max_sleeves,
        "n_certified": len(rows),
        "n_tradeable": len(live),
        "n_blocked_by_venue": len(blocked),
        "n_duplicate_mechanism_symbol": len(dupes),
        "n_selected": len(chosen),
        "gross_exposure_if_all_fire": round(len(chosen) * RISK_FRAC, 5),
        "by_mechanism": fams,
        "mean_ev": None if not evs else round(sum(evs) / len(evs), 4),
        "sleeves": chosen,
        "blocked_by_venue": sorted({r["symbol"] for r in blocked}),
        "rule": ("venue-listed first, then diversity across mechanisms, then expectancy within "
                 "one; one row per (mechanism, symbol) because two certificates on the same "
                 "mechanism and instrument are one bet with two names"),
    }


def write(doc: dict[str, Any], path: Path = OUT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--live-venue", action="store_true",
                    help="ask the E8 venue which instruments it lists (needs credentials)")
    args = ap.parse_args(argv)
    tradeable = None
    if args.live_venue:
        from prop.tradelocker_venue import TradeLockerVenue
        tradeable = set(TradeLockerVenue().connect()._by_key)
    doc = select(tradeable)
    write(doc)
    print(f"E8 book: {doc['n_selected']} sleeve(s) at {RISK_FRAC:.2%} "
          f"= {doc['gross_exposure_if_all_fire']:.2%} gross if every one fires")
    print(f"  by mechanism: {doc['by_mechanism']}")
    print(f"  mean ev {doc['mean_ev']} | {doc['n_blocked_by_venue']} blocked by the venue, "
          f"{doc['n_duplicate_mechanism_symbol']} duplicate (mechanism, symbol)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
