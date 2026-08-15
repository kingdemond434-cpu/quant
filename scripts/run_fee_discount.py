#!/usr/bin/env python3
"""THE BNB FEE DISCOUNT: 25% off every commission and off margin interest, for one account toggle.

**WHY A SCRIPT FOR A SETTING.** Because the setting is invisible from inside the desk, and an
invisible cost term is the one that never gets fixed. Every cost forecast, TCA number and net-edge
estimate in this repo is computed from a commission rate; none of them asks the venue whether the
discount that changes that rate by a quarter is switched on. A desk that believes it pays 0.075%
and pays 0.100% is wrong by 25% on its LARGEST cost term, uniformly, in the flattering direction.

**IT IS NOT FREE AND THE CATCH IS THE POINT.** The discount is paid FROM A BNB BALANCE. With the
toggle on and no BNB held, the venue charges the full rate and the toggle changes nothing -- which
is a switch reporting ON while saving zero, the exact shape of a capability that is armed and idle.
So this reports BOTH: the toggle AND the balance funding it, and calls the combination ARMED only
when both are true. Reporting the toggle alone would be the more comfortable and more useless
answer.

**WHAT IT IS WORTH, ARITHMETICALLY.** At VIP0 spot commission is 10bps a side, so a round trip is
20bps and the discount saves 5bps of it. A sleeve turning over its clip 20 times a year saves
20 x 5bps = 1.0% of the traded notional per year. On the margin side the same toggle discounts the
INTEREST, which at 5.1% and f=2.3x is worth about 0.16%/yr of equity. Neither number is large on
its own; both are permanent, both compound, and neither requires being right about anything.

**READING IS AUTOMATIC, WRITING IS NOT.** The daily cycle runs this without `--enable` and records
the state. Switching it ON is an account-level change and stays an explicit act with a flag on it.

    python scripts/run_fee_discount.py              # report only
    python scripts/run_fee_discount.py --enable     # actually switch it on
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

_OUT = Path("web/fee_discount.json")

#: Binance VIP0 spot commission, per side, as a fraction. The discount is 25% OF THIS.
VIP0_SPOT_COMMISSION = 0.001

#: The discount rate the venue applies when the burn is on and BNB is held.
BNB_DISCOUNT = 0.25

#: BNB below this is treated as NOT FUNDING the discount. A dust balance satisfies the toggle and
#: exhausts within days, after which the account silently pays full freight again -- so a floor
#: that reads "on" for a balance that cannot last is a floor that reports the wrong answer most of
#: the time. Denominated in BNB, deliberately small: this is a liveness check, not a target.
MIN_BNB_BALANCE = 0.01


def survey(*, enable: bool = False) -> dict[str, Any]:
    """Read the toggle and the balance behind it; optionally switch the toggle on.

    NEVER REPORTS A DEFAULT. An unreadable venue leaves `spot_burn` as None, because "we could not
    ask" and "it is off" lead to different actions and only one of them is free.
    """
    rep: dict[str, Any] = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "vip0_commission_per_side": VIP0_SPOT_COMMISSION,
        "discount": BNB_DISCOUNT,
        "spot_burn": None, "interest_burn": None, "bnb_balance": None,
        "state": "UNMEASURED", "why": "", "changed": False,
        # DECLARED UP FRONT so every exit path returns the same shape. A key that exists on the
        # measured paths and is absent on the unreadable ones makes the consumer's `.get()` return
        # None for two different facts -- "no discount applies" and "nobody asked".
        "effective_commission_per_side": None,
    }
    try:
        from libs.execution import binance_spot_live as spot
    except Exception as exc:                                   # pragma: no cover - import guard
        rep["why"] = f"connector unavailable ({type(exc).__name__}: {exc})"
        return rep

    armed, why_armed = spot.is_armed()
    if not armed:
        rep["state"] = "UNMEASURED"
        rep["why"] = (f"NOT ARMED -- {why_armed}. The burn state is a signed read, so on an unarmed "
                      "clone it is unknown rather than off")
        return rep

    if enable:
        try:
            got = spot.set_bnb_burn(spot=True, interest=True)
            rep["changed"] = True
            rep["spot_burn"], rep["interest_burn"] = got["spotBNBBurn"], got["interestBNBBurn"]
        except Exception as exc:
            rep["why"] = f"enable FAILED ({type(exc).__name__}: {exc}); "

    if rep["spot_burn"] is None:
        try:
            got = spot.bnb_burn_status()
            rep["spot_burn"], rep["interest_burn"] = got["spotBNBBurn"], got["interestBNBBurn"]
        except Exception as exc:
            rep["why"] += f"burn state unreadable ({type(exc).__name__}: {exc})"
            return rep

    try:
        rep["bnb_balance"] = round(float(spot.balances().get("BNB", 0.0)), 6)
    except Exception as exc:
        rep["why"] += f"; BNB balance unreadable ({type(exc).__name__})"

    bal = rep["bnb_balance"]
    funded = bal is not None and bal >= MIN_BNB_BALANCE
    if rep["spot_burn"] and funded:
        rep["state"] = "ARMED"
        rep["why"] += (f"burn ON with {bal:g} BNB behind it -- commissions are being charged at "
                       f"{VIP0_SPOT_COMMISSION * (1 - BNB_DISCOUNT) * 1e4:.1f}bps a side instead of "
                       f"{VIP0_SPOT_COMMISSION * 1e4:.1f}bps")
    elif rep["spot_burn"] and bal is None:
        rep["state"] = "UNMEASURED"
        rep["why"] += ("burn ON but the BNB balance is unreadable, so whether it is actually being "
                       "applied is unknown. The toggle alone does not discount anything")
    elif rep["spot_burn"]:
        rep["state"] = "TOGGLED-UNFUNDED"
        rep["why"] += (f"burn ON but only {bal:g} BNB is held (floor {MIN_BNB_BALANCE:g}). The "
                       "venue charges the FULL rate when there is no BNB to burn, so this switch "
                       "currently reports on and saves nothing -- armed and idle, on a cost term")
    else:
        rep["state"] = "OFF"
        rep["why"] += (f"burn OFF -- the account is paying {VIP0_SPOT_COMMISSION * 1e4:.1f}bps a "
                       f"side where {VIP0_SPOT_COMMISSION * (1 - BNB_DISCOUNT) * 1e4:.1f}bps is "
                       "available for holding BNB. Run with --enable, and hold BNB")
    rep["effective_commission_per_side"] = (
        VIP0_SPOT_COMMISSION * (1 - BNB_DISCOUNT) if rep["state"] == "ARMED"
        else VIP0_SPOT_COMMISSION if rep["state"] in {"OFF", "TOGGLED-UNFUNDED"} else None)
    return rep


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--enable", action="store_true",
                    help="actually switch the BNB burn ON for spot commission and margin interest. "
                         "An account-level change, so it needs the flag; the read is free and runs "
                         "in the daily cycle without it")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rep = survey(enable=bool(args.enable))
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=1), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=1))
    else:
        print(f"fee-discount: {rep['state']} -- {rep['why']}")
        print(f"-> {_OUT}")
    # A NON-ZERO EXIT FOR "OFF" AND FOR "UNFUNDED", because both are money left on the table that a
    # green exit code would hide. UNMEASURED also exits non-zero: on the box this runs armed, and
    # an unreadable answer there is a fault rather than a clone's ordinary state.
    return 0 if rep["state"] == "ARMED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
