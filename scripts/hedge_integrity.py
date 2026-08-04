"""HEDGE INTEGRITY RAIL -- the detector that did not exist during incident #6.

On 2026-07-27 COOKIEUSDT futures sat at +916,772 LONG where the carry required -183,140 SHORT,
carrying -$482 with free margin at $110. It then recurred on 1000CATUSDT at +1,138,985. Both ran
UNDETECTED. Nothing on this desk asserted the one invariant that defines a cash-and-carry:

    for every tracked carry:  venue futures position MUST be SHORT and MUST match -spot_qty

The reconciler heals a MISSING short. It has no concept of an INVERTED one, so a long where a
short belongs looked like "no short to fix" and persisted while the loss accumulated.

This is a rail, not a subsystem: one invariant, three failure classes, no model and no judgement.

    INVERTED    futures position is LONG where a SHORT is required  -> the incident-#6 signature,
                the desk is DOUBLE LONG rather than delta-neutral
    MISSING     no futures position at all                          -> naked spot, directional
    MISMATCHED  short exists but size is off by more than tolerance  -> partial hedge

VENUE GROUND TRUTH ONLY. It compares the desk's tracked state AGAINST the exchange and trusts the
exchange. The desk's own state file said "4 delta-neutral carries" throughout the incident -- a
check built on that file would have reported everything healthy.

Read-only: places no orders, cancels nothing, and cannot move money.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, ".")
import scripts.run_deadman_switch as D

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data/cashcarry_positions.json"
OUT = ROOT / "data/hedge_integrity.json"
PAGE = ROOT / "docs/PRINCIPAL_ACTION.md"
TOL = 0.02  # 2% size tolerance; below this is venue rounding, not a broken hedge


def main() -> None:
    creds = D._creds(D._FUT_KEYS)
    if not creds:
        raise SystemExit("no futures credentials")
    venue = {
        p["symbol"]: float(p.get("positionAmt", 0.0))
        for p in D._signed(D._FUT_BASE, "/fapi/v2/positionRisk", creds)
    }
    tracked = json.loads(STATE.read_text("utf-8")).get("positions", {})

    print("=== HEDGE INTEGRITY -- venue ground truth vs tracked carries ===")
    print("    invariant: every tracked carry's futures leg is SHORT and matches -spot_qty\n")
    viol = []
    for sym, p in tracked.items():
        spot_q = float(p.get("spot_qty", 0.0))
        want = -abs(spot_q)
        got = venue.get(sym, 0.0)
        if got > 0:
            cls = "INVERTED"
        elif got == 0:
            cls = "MISSING"
        elif abs(got - want) > abs(want) * TOL:
            cls = "MISMATCHED"
        else:
            cls = "OK"
        flag = "" if cls == "OK" else "  <== VIOLATION"
        print(
            f"  {sym:<14} spot {spot_q:>14,.0f}  want {want:>14,.0f}  got {got:>14,.0f}  "
            f"{cls}{flag}"
        )
        if cls != "OK":
            viol.append(
                {
                    "symbol": sym,
                    "class": cls,
                    "spot_qty": spot_q,
                    "expected_fut": want,
                    "actual_fut": got,
                }
            )

    # An UNTRACKED venue short is the mirror failure: exposure the desk does not know it has.
    for sym, amt in venue.items():
        if amt and sym not in tracked:
            print(
                f"  {sym:<14} {'(untracked)':>14}  {'':>14}  {amt:>14,.0f}  ORPHAN  <== VIOLATION"
            )
            viol.append(
                {
                    "symbol": sym,
                    "class": "ORPHAN",
                    "spot_qty": 0.0,
                    "expected_fut": 0.0,
                    "actual_fut": amt,
                }
            )

    if not tracked and not any(venue.values()):
        print(
            "  book is FLAT -- no tracked carries, no venue positions. Invariant holds trivially."
        )

    inv = [v for v in viol if v["class"] == "INVERTED"]
    print(f"\n  {len(viol)} violation(s); {len(inv)} INVERTED")
    if inv:
        print(
            "  INVERTED is the incident-#6 signature: the desk is DOUBLE LONG, not delta-neutral."
        )
        print("  It cannot be healed by the close path -- a close BUYS futures to cover a short,")
        print("  which on a long only makes it larger. It requires a reduceOnly SELL, chunked to")
        print("  the venue MARKET_LOT_SIZE cap.")
        try:
            with PAGE.open("a", encoding="utf-8") as fh:
                fh.write(f"\n## {datetime.now(tz=UTC).isoformat()} HEDGE INVERTED\n")
                for v in inv:
                    fh.write(
                        f"- {v['symbol']}: futures {v['actual_fut']:+,.0f} where "
                        f"{v['expected_fut']:+,.0f} required (incident-#6 signature)\n"
                    )
            print(f"  -> paged {PAGE}")
        except OSError:
            pass

    OUT.write_text(
        json.dumps(
            {
                "updated": datetime.now(tz=UTC).isoformat(),
                "violations": viol,
                "n_violations": len(viol),
                "n_inverted": len(inv),
                "ok": not viol,
            },
            indent=1,
        ),
        "utf-8",
    )
    print(f"  -> {OUT}")
    sys.exit(1 if inv else 0)


if __name__ == "__main__":
    main()
