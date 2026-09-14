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

#: The last catalogue the venue actually reported. Written whenever the live call succeeds, read
#: when it does not. A prop venue's instrument list changes on the order of months; a connection
#: fails on the order of minutes, and the desk must not lose rule 1 for the length of an outage.
CATALOGUE_CACHE = DESK / "data" / "e8_catalogue.json"


def _cache_catalogue(keys: set[str]) -> None:
    """Remember what the venue lists, so an outage costs freshness and not the rule."""
    try:
        CATALOGUE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        CATALOGUE_CACHE.write_text(json.dumps({
            "measured_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "n": len(keys),
            "instruments": sorted(keys),
        }, indent=1), encoding="utf-8")
    except OSError:
        pass


def _cached_catalogue() -> set[str] | None:
    """The last measured catalogue, or None. None is 'I do not know', never 'no restriction'."""
    try:
        doc = json.loads(CATALOGUE_CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    rows = doc.get("instruments")
    if not isinstance(rows, list) or not rows:
        return None
    return {str(r) for r in rows}

#: HOW MANY SLEEVES, and it is a breadth decision rather than a taste one. Every certified sleeve
#: fires in the asia window, so the whole book lands at once into a 2.5% daily floor; widening the
#: book at a smaller per-sleeve size is what raises pass probability, and 24 x 0.05% keeps gross
#: simultaneous exposure at 1.2% -- under half the daily wall, before any stand-down.
MAX_SLEEVES = 24

#: RISK PER TRADE, as a fraction of the $100,000 initial balance. 0.15%, i.e. $150.
#:
#: RAISED FROM 0.05% ON 2026-09-14, on the principal's decision, against a measured sweep of the
#: real barrier -- `research/prop_barrier.py` over 4,000 paths per cell at the book actually
#: fielded (24 sleeves, rr 1.5, 0.64 trades per sleeve per day) and expectancy NET of cost at
#: +0.135R, which is the honest reading of the desk's +0.20 gross replay figure.
#:
#: WHAT 0.05% WAS COSTING, at tail-implied rho 0.58:
#:
#:     risk     P(pass)   median days   p90
#:     0.050%    99.6%         91       146
#:     0.075%   100.0%         61       106
#:     0.100%    99.9%         45        87
#:     0.125%    98.2%         37        74      <- here
#:     0.150%    88.3%         31        65
#:     0.200%    47.4%         20        37
#:
#: Fifty-four days bought one and a half points of pass probability. That is not a conservative
#: trade, it is an expensive one: E8 publishes no time limit on Pro, but every extra day is a day
#: of daily-floor exposure that the 2.5% rule can end, so a slower pass is not a monotonically
#: safer pass. The earlier 0.05% reading compared 0.05% against 0.07% only, where the difference
#: really was 96.3% against 84.0%; it never priced the speed being given up, because the sweep it
#: cited did not report days.
#:
#: WHY NOT FURTHER. Above 0.15% the curve falls off a cliff -- 47.4% at 0.20% -- because this
#: account truncates the right tail at +2% a day and leaves the left free to -2.5%. The pass-
#: optimal size is therefore well below the growth-optimal one, and 0.125% is the last point
#: where P(pass) is still near the ceiling while the median more than halves.
#:
#: This is an INCREASE in size and that is deliberate (growth governance Rule 2: a strong
#: opportunity must be allowed more capital when the evidence supports it). Nothing here lowers
#: any limit on the live MT5 book, which solves a different problem on a different venue --
#: `mt5desk/account_profile.py` is where that line is drawn.
#:
#: RAISED AGAIN TO 0.15% THE SAME NIGHT, once the venue's spreads were measured LIVE rather than
#: over a closed weekend. The first sample had every symbol frozen (min == max == median across
#: 11 draws); with the session open the same instruments quote EURUSD 0.431 bps and XAUUSD 1.175,
#: which on a 20-pip stop is a haircut of ~0.025R, not the ~0.065R the cost note assumed. Net
#: expectancy is therefore nearer +0.175 than +0.135 and the whole curve shifts.
#:
#: THE BINDING CONSTRAINT IS THE DAILY FLOOR, NOT THE STATIC ONE. At net +0.175, rho 0.58:
#:
#:     risk     P(pass)   median   p_fail_daily   worst_dd_p90
#:     0.125%    99.9%      35          0.1%          2.75%
#:     0.150%    98.3%      30          1.6%          3.30%     <- here
#:     0.175%    91.7%      26          8.0%          3.76%
#:     0.200%    78.0%      22         21.9%          3.90%
#:
#: Between 0.15% and 0.175% the daily-breach probability QUINTUPLES to buy four days. Worst
#: drawdown at p90 is 3.3% against a 10% static floor, so the $90,000 line is not what ends these
#: accounts -- the 2.5% daily one is.
#:
#: AND IT IS THE LAST SIZE THAT SURVIVES BEING WRONG. Across net +0.175 / +0.135 / +0.100:
#:     0.125%  ->  99.9 / 99.6 / 98.5
#:     0.150%  ->  98.3 / 97.1 / 93.6
#:     0.175%  ->  91.7 / 87.6 / 79.6
#: 0.175% collapses on the pessimistic leg; 0.15% does not. `rho` 0.58 is TAIL-IMPLIED and has
#: never been measured on live fills (`matched_fills` is still 0), and correlation error is what
#: larger size punishes hardest -- which is the whole reason the ceiling is here and not higher.
RISK_FRAC = 0.0015


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
    # THE CHART IS PART OF THE IDENTITY (fixed 2026-09-14).
    #
    # This keyed on (mechanism, symbol) alone, so a session_range_breakout on M15 and its H1
    # sibling were ONE row and the later one was discarded as a duplicate. That was correct while
    # H1 was the only chart the desk collected -- two certificates differing in nothing but a
    # parameter hash really are one bet with two names -- and it becomes wrong the moment the
    # collector writes M30/M15/M5/M1: an M15 breakout reads different bars, sets a different stop
    # and fills at different times from the H1 one.
    #
    # IT WOULD HAVE CANCELLED THE DIVERSITY IT WAS MEANT TO ENFORCE, silently. The measured case
    # for collecting intraday at all is that rho falls from 0.58 toward ~0.29 as charts are added,
    # which on the barrier is worth four days AND takes daily-breach risk from 1.8% to 1.1%.
    # Collapsing the charts back into one row would have kept the book at 20 H1 sleeves while the
    # report cheerfully counted the rest as duplicates.
    #
    # A DIFFERENT CHART IS NOT A FULLY INDEPENDENT BET and this does not pretend otherwise: the
    # round-robin below still spreads across MECHANISMS first, so charts of one family can only
    # fill slots the other mechanisms have not claimed. The chart widens the identity; it does not
    # promote a family.
    def _tf(row: dict[str, Any]) -> str:
        return str((row.get("params") or {}).get("timeframe") or "H1").upper()

    best: dict[tuple[str, str, str], dict[str, Any]] = {}
    dupes = []
    for r in sorted(live, key=lambda x: -(x["ev"] or -9)):
        k = (r["family"], r["symbol"], _tf(r))
        if k in best:
            dupes.append({**r, "why": f"duplicate of {best[k]['key']} "
                                      "on the same mechanism+symbol+chart"})
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
        "by_chart": {tf: sum(1 for x in chosen if str((x.get("params") or {}).get(
            "timeframe") or "H1").upper() == tf)
            for tf in sorted({str((x.get("params") or {}).get("timeframe") or "H1").upper()
                              for x in chosen})},
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
    ap.add_argument("--no-live-venue", action="store_true",
                    help="do NOT ask the venue what it lists. The book is then written only if a "
                         "previously measured catalogue is on disk; with neither, nothing is "
                         "written, because an unfiltered book is not a safer book.")
    args = ap.parse_args(argv)

    # RULE 1 OF THIS FILE WAS OPTIONAL, AND OFF BY DEFAULT (fixed 2026-09-14).
    #
    # The docstring's first selection rule is THE VENUE MUST LIST IT. The implementation asked
    # for the catalogue only under `--live-venue`, and the scheduled task runs
    # `python e8_book.py` with no arguments -- so `tradeable` was None, `select()` reads None as
    # "apply no filter", and the rule that leads the file was never applied on any scheduled
    # pass. `n_blocked_by_venue` then published 0, which is not "nothing was blocked" but "I did
    # not look".
    #
    # MEASURED ON THE LIVE $100k ACCOUNT TONIGHT: of the 24 sleeves in the book, EIGHT were Scandi
    # and EM crosses -- EURNOK, CHFNOK, GBPMXN and siblings -- that E8's 46-instrument catalogue
    # does not carry. The executor caught every one and refused it as NOT_LISTED, so no bad order
    # was sent; the cost was worse than an error. A third of the book's slots were spent on
    # instruments that cannot trade, on an account whose pass probability is a function of how
    # many INDEPENDENT mechanisms are actually running, with a five-day hard speed floor and a
    # right tail that is confiscated at 2% a day. Those eight slots were unavailable to the
    # certified sleeves that E8 does list.
    #
    # ABSENCE IS NOT PERMISSION (LAWS). `None` meaning "no filter" is that violation in one
    # sentinel: the failure to measure and the decision not to restrict were the same value.
    # They are now different values and the failure fails CLOSED.
    tradeable: set[str] | None = None
    source = ""
    if not args.no_live_venue:
        try:
            from prop.tradelocker_venue import TradeLockerVenue
            tradeable = set(TradeLockerVenue().connect()._by_key)
            source = f"live venue ({len(tradeable)} instruments)"
            _cache_catalogue(tradeable)
        except Exception as exc:
            print(f"live venue UNREACHABLE ({type(exc).__name__}: {exc}); falling back to the "
                  f"last measured catalogue")
    if tradeable is None:
        cached = _cached_catalogue()
        if cached:
            tradeable, source = cached, f"cached catalogue ({len(cached)} instruments)"

    if tradeable is None:
        # NOT AN ERROR TO SWALLOW. Writing an unfiltered book here would republish the exact
        # defect this fix removes, and silently: the artifact would look complete. Keeping the
        # last good book is the conservative act -- it was written when the catalogue WAS known.
        print("REFUSING to write the book: the venue's catalogue is unknown and no cached one "
              "exists, so rule 1 (the venue must list it) cannot be applied. The previous book "
              "stands.")
        return 1

    doc = select(tradeable)
    doc["catalogue_source"] = source
    write(doc)
    print(f"E8 book: {doc['n_selected']} sleeve(s) at {RISK_FRAC:.2%} "
          f"= {doc['gross_exposure_if_all_fire']:.2%} gross if every one fires")
    print(f"  catalogue: {source}")
    print(f"  by mechanism: {doc['by_mechanism']}")
    print(f"  mean ev {doc['mean_ev']} | {doc['n_blocked_by_venue']} blocked by the venue, "
          f"{doc['n_duplicate_mechanism_symbol']} duplicate (mechanism, symbol)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
