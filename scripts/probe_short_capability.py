#!/usr/bin/env python3
"""CAN THIS DESK SHORT? A read-only probe of the one question that caps every return figure.

**WHY THIS IS THE MOST VALUABLE QUESTION ON THE DESK.** Every projection here runs into the same
wall: rho_bar = 0.375, k_eff 2.0, and a ceiling near +17%/yr no number of additional sleeves can
move. rho is that high for one structural reason -- EVERY sleeve the book can hold is LONG CRYPTO,
so they all share one factor. Shorts are what collapse it. `libs/research/sleeve_allocation.py`
measures the same thing from the other side: the book is a cluster of near-redundant longs.

**AND THE DESK MAY HAVE BEEN WRONG THAT IT CANNOT.** Two different restrictions were conflated:

    MiCA / EEA retail   blocks DERIVATIVES. `run_live_guard` records it, measured 2026-08-15:
                        the futures account cannot be read at all. That is why perps and
                        cash-and-carry are untradeable, and that finding stands.

    THE SELL REFUSAL    in `spot_order_path.place_entry` is NOT that. Read its own comment: the
                        order path "has always sent BUY regardless of the side requested", so a
                        SELL was filled as a BUY with a stop above the market. It refuses "until a
                        short path exists that borrows the base asset and inverts the stop".
                        That is an UNBUILT capability, not a banned one.

A cross-margin short borrows the BASE asset and sells it. That is margin lending against spot
collateral -- not a derivative, not the product MiCA blocks on the futures account. Whether the
venue actually offers it, per asset, to this account, is a fact Binance publishes at
`/sapi/v1/margin/maxBorrowable` and which nobody has ever read.

**IT PLACES NOTHING AND AUTHORISES NOTHING.** It answers "is the door open, and what does it cost",
because building a short path before knowing that would be building against an assumption -- which
is exactly the mistake this script exists to correct. Opening the first short is a principal act
and needs its own rail work: a short's loss is unbounded above, its stop is above the entry, and
its liquidation arithmetic is not the mirror of a long's.

    python scripts/probe_short_capability.py [--json]
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_OUT = Path("web/short_capability.json")

#: Base assets to probe -- the ones the live sleeves actually hold. A borrow permitted on an asset
#: the book never trades answers a question nobody asked.
ASSETS = ("BTC", "ETH", "BNB", "SOL", "LINK", "ADA", "XRP", "DOGE", "AVAX", "DOT")


def build(assets: tuple[str, ...] = ASSETS) -> dict[str, Any]:
    from libs.execution import binance_margin_live as m

    rep: dict[str, Any] = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "question": "can this account borrow the BASE asset, i.e. open a cross-margin short?",
        "why_it_matters": (
            "rho_bar 0.375 and the ~+17%/yr ceiling both follow from every sleeve being LONG "
            "crypto. Shorts are the only lever that collapses rho rather than raising n, and the "
            "census shelf of high-orthogonality families is empty -- everything above 0.30 is "
            "already deployed"),
        "not_the_same_as_mica": (
            "MiCA blocks DERIVATIVES; run_live_guard measured the futures account unreadable on "
            "2026-08-15 and that stands. A cross-margin short borrows the base asset against spot "
            "collateral -- margin lending, not a derivative. The SELL refusal in "
            "spot_order_path.place_entry is an UNBUILT path, not a banned product: its own comment "
            "says it refuses 'until a short path exists that borrows the base asset'"),
        "places_nothing": (
            "read-only. Opening the first short is a principal act and needs rail work first: loss "
            "is unbounded above, the stop sits ABOVE entry, and liquidation is not a long's mirror"),
        "assets": {}, "verdict": "UNMEASURED", "why": "",
    }

    armed, why_armed = m.is_armed()
    rep["armed"] = bool(armed)
    if not armed:
        rep["why"] = (f"NOT ARMED -- {why_armed}. maxBorrowable is a signed read, so on an unarmed "
                      "clone the answer is UNKNOWN rather than no")
        return rep

    borrowable = unavailable = unreadable = 0
    for a in assets:
        amount, why = m.max_borrowable(a)
        rate, why_rate = m.borrow_rate(a)
        row: dict[str, Any] = {"max_borrowable": amount, "why": why,
                               "annual_borrow_rate": rate, "rate_why": why_rate[:120]}
        if amount is None:
            row["state"] = "UNREADABLE"
            unreadable += 1
        elif amount <= 0:
            row["state"] = "NOT-LENDABLE"
            unavailable += 1
        else:
            row["state"] = "BORROWABLE"
            borrowable += 1
            # THE COST OF THE SHORT, WHICH IS NOT THE COST OF THE LONG. A short pays interest on
            # the BASE asset it borrowed, and base-asset rates are routinely far above the stable's
            # -- a short that is right about direction can still lose to its own carry.
            if isinstance(rate, (int, float)):
                row["carry_drag_annual"] = round(float(rate), 5)
        rep["assets"][a] = row

    rep["n_borrowable"], rep["n_not_lendable"] = borrowable, unavailable
    rep["n_unreadable"] = unreadable
    if borrowable:
        rep["verdict"] = "SHORTS ARE AVAILABLE"
        rep["why"] = (
            f"{borrowable}/{len(assets)} base assets are borrowable, so a cross-margin short is "
            "placeable on this account. THE CAPABILITY GAP IS A BUILD, NOT A BAN -- the fade "
            "mechanisms H1/H7/H11 journal refusals today for want of an order path, not for want "
            "of permission. Next: a short entry path that borrows the base asset, inverts the "
            "stop, and carries its own liquidation arithmetic")
    elif unavailable and not unreadable:
        rep["verdict"] = "NO SHORTS"
        rep["why"] = ("the venue permits ZERO borrow on every base asset probed. The long-only "
                      "constraint is real and rho stays where it is -- which at least closes the "
                      "question instead of leaving it assumed")
    else:
        rep["verdict"] = "UNMEASURED"
        rep["why"] = (f"{unreadable} asset(s) unreadable. Absence of an answer is not an answer "
                      "(L1.28a) and this must not resolve to 'no shorts' by default")
    return rep


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--assets", default=",".join(ASSETS))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rep = build(tuple(a.strip().upper() for a in args.assets.split(",") if a.strip()))
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=1), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=1))
        return 0
    print(f"=== SHORT CAPABILITY === {rep['verdict']}")
    for a, row in rep["assets"].items():
        rate = row.get("annual_borrow_rate")
        rate_s = "rate UNMEASURED" if rate is None else f"borrow {rate:.2%}/yr"
        print(f"  [{row['state']:<12}] {a:<5} {str(row['why'])[:60]:<62} {rate_s}")
    print(f"  {rep['why']}")
    print(f"-> {_OUT}")
    return 0 if rep["verdict"] == "SHORTS ARE AVAILABLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
