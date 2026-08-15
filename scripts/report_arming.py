#!/usr/bin/env python3
"""IS EVERYTHING ACTUALLY ARMED -- every switch on the money path, in one read.

**THE QUESTION HAD NO SINGLE ANSWER AND IT IS ASKED CONSTANTLY.** Arming this desk is nine
independent facts: a keyfile, three live-enable markers, a margin flag, a promotion marker, a wallet
selection, an exception ledger, and three ruin rails whose sense is INVERTED (present = frozen).
They live in three directories, two of them gitignored, and `run_golive_preflight` checked exactly
one of them. So "is it armed?" was answered by running four scripts and reading their prose, which
is how a desk ends up believing a switch is on because it was on last week.

**EVERY UNKNOWN IS REPORTED AS UNKNOWN.** An unreadable marker is never counted as absent and never
counted as present: a permissions error on `data/LIVE_ENABLE` and a missing `data/LIVE_ENABLE` are
different facts with different fixes, and collapsing them is the defect class this desk names most
often. Absent IS a measurement here -- these markers are created by an explicit act, so a file that
is not there records an act that did not happen. Unreadable records nothing at all.

**IT ARMS NOTHING AND IT NEVER WILL.** Every marker below is the principal's to write. This reads
mode bits and existence, prints the exact command for each gap, and stops. A reporter that could
arm the desk would be a fourth path to live trading, wearing the name of a status check.

**NO SECRET IS EVER READ, LET ALONE PRINTED.** The keyfile is checked with `.exists()` and
`stat()`. Its contents are not opened, not parsed, not length-checked and not summarised, because a
"safe" summary of a key is still a function of the key.

    python scripts/report_arming.py [--json]
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))

import argparse
import json
import os
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_OUT = Path("web/arming.json")

#: (key, path, what it unlocks, the command that creates it). `inverted` markers are RAILS: their
#: PRESENCE stops trading, so "armed" for a rail means the file is absent.
_SWITCHES: tuple[dict[str, Any], ...] = (
    {"key": "spot_keyfile", "path": "data/secrets/binance_live_spot.json",
     "unlocks": "authentication against the venue at all -- without it every order is unsigned",
     "fix": "place the keyfile (NEVER through this repo, NEVER echoed to a terminal)",
     "secret": True},
    {"key": "live_enable", "path": "data/LIVE_ENABLE",
     "unlocks": "the spot connector's arming contract",
     "fix": "echo '{\"armed_by\":\"principal\"}' > data/LIVE_ENABLE"},
    {"key": "vps_verified", "path": "data/LIVE_VPS_VERIFIED",
     "unlocks": "the box-identity half of the arming contract -- a laptop must not place orders",
     "fix": "echo '{\"verified_by\":\"principal\"}' > data/LIVE_VPS_VERIFIED"},
    {"key": "margin_enable", "path": "data/MARGIN_ENABLE",
     "unlocks": "cross-margin orders and every borrowing leg. Absent = the margin executor is inert",
     "fix": "echo '{\"armed_by\":\"principal\"}' > data/MARGIN_ENABLE"},
    {"key": "auto_promotion", "path": "data/auto_promotion_armed.json",
     "unlocks": "research-to-capital promotion. Absent = every candidate refused, forever",
     "fix": "echo '{\"armed\":true,\"armed_by\":\"principal\"}' > data/auto_promotion_armed.json"},
    {"key": "rail_cashcarry_kill", "path": "data/CASHCARRY_KILL", "inverted": True,
     "unlocks": "nothing -- PRESENT means the executor is flatten-only and opens no position",
     "fix": "clearing a latched rail is a deliberate act; inspect why it latched before removing"},
    {"key": "rail_deadman", "path": "data/DEADMAN_FIRED", "inverted": True,
     "unlocks": "nothing -- PRESENT means the Tier-3 equity rail fired and latched",
     "fix": "the deadman is never cleared autonomously; this is the principal's call alone"},
    {"key": "rail_freeze", "path": "data/FREEZE", "inverted": True,
     "unlocks": "nothing -- PRESENT means a manual freeze is in place",
     "fix": "rm data/FREEZE once the reason it was set no longer holds"},
)


def _probe(rel: str, *, secret: bool = False) -> dict[str, Any]:
    """Existence and mode. ABSENT and UNREADABLE are different answers and stay different."""
    p = _ROOT / rel
    row: dict[str, Any] = {"path": rel}
    try:
        st = p.stat()
    except FileNotFoundError:
        row["state"] = "ABSENT"
        row["why"] = ("the file is not there. These markers are created by an explicit act, so "
                      "absence records an act that did not happen -- which IS a measurement")
        return row
    except OSError as exc:
        row["state"] = "UNREADABLE"
        row["why"] = (f"{type(exc).__name__}: {exc} -- NOT the same as absent. A permissions "
                      "error and a missing file have different fixes, and collapsing them is how "
                      "a desk decides it is armed because nothing said otherwise")
        return row
    row["state"] = "PRESENT"
    row["mode"] = stat.filemode(st.st_mode)
    row["age_h"] = round((datetime.now(tz=UTC).timestamp() - st.st_mtime) / 3600.0, 1)
    if secret:
        # NOT OPENED. Not parsed, not length-checked, not summarised: a "safe" summary of a key is
        # still a function of the key, and this artifact is published to web/.
        row["contents"] = "NOT READ -- existence and mode only, by design"
        if st.st_mode & (stat.S_IRGRP | stat.S_IROTH):
            row["warning"] = (f"mode {row['mode']} is group/world readable. Every other account on "
                              "this box can read the key. chmod 600")
    return row


def _wallet() -> dict[str, Any]:
    env = (os.environ.get("DESK_WALLET") or "").strip().lower()
    row: dict[str, Any] = {"env_DESK_WALLET": env or None}
    try:
        row["file_data_DESK_WALLET"] = (_ROOT / "data" / "DESK_WALLET").read_text(
            "utf-8").strip().lower()
    except OSError:
        row["file_data_DESK_WALLET"] = None
    row["effective"] = env or row["file_data_DESK_WALLET"] or "spot"
    row["why"] = ("env wins, then data/DESK_WALLET, then 'spot'. THIS IS WHICH WALLET THE DAILY "
                  "CYCLE TRADES: pointed at a wallet the capital has left, every sleeve places "
                  "nothing, raises nothing, and writes a row identical to a quiet market")
    return row


def _exception() -> dict[str, Any]:
    try:
        doc = json.loads((_ROOT / "docs/research/LIVE_EXCEPTION_LEDGER.json").read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {"state": "UNREADABLE", "why": f"{type(exc).__name__}: {exc}"}
    rows = [r for r in (doc.get("exceptions") or []) if isinstance(r, dict) and r.get("active")]
    return {"state": "ACTIVE" if rows else "NONE-ACTIVE",
            "active": [{"id": r.get("id"), "law_suspended": r.get("law_suspended"),
                        "granted_by": r.get("granted_by"), "granted": r.get("granted")}
                       for r in rows],
            "why": ("a suspended law that is not on record is indistinguishable from a law that "
                    "never applied. Code running under one fails closed without its row")}


def _connectors() -> dict[str, Any]:
    """The connectors' OWN verdict, not a re-derivation of it.

    Deliberately asks the modules that gate the orders rather than re-reading their markers here. A
    status report holding its own opinion of whether the venue is armed is how two answers come to
    exist, and the one that disagrees quietly is the one that spends money.
    """
    out: dict[str, Any] = {}
    for name in ("spot", "margin"):
        try:
            from libs.execution.wallet import connector

            armed, why = connector(name).is_armed()
            out[name] = {"armed": bool(armed), "why": why}
        except Exception as exc:
            out[name] = {"armed": None, "why": f"{type(exc).__name__}: {exc} -- UNKNOWN, not off"}
    return out


def _cost_levers() -> dict[str, Any]:
    """The two switches that change what the desk PAYS rather than what it may do.

    **DELIBERATELY NOT COUNTED IN `fully_armed`.** An unclaimed fee discount does not risk the
    account and must not block a report whose job is to say whether trading is permitted; conflating
    "costs more than it should" with "must not trade" would make the one number this file exists to
    publish mean two different things. They are here because they are otherwise invisible: nothing
    else on the desk ever asks whether the commission it assumes is the commission it is charged.
    """
    out: dict[str, Any] = {}
    try:
        doc = json.loads((_ROOT / "web/fee_discount.json").read_text("utf-8"))
        out["bnb_burn"] = {"state": doc.get("state"), "why": str(doc.get("why", ""))[:180],
                           "effective_commission_per_side":
                               doc.get("effective_commission_per_side")}
    except (OSError, ValueError) as exc:
        out["bnb_burn"] = {"state": "UNMEASURED",
                           "why": f"web/fee_discount.json unreadable ({type(exc).__name__}) -- run "
                                  "scripts/run_fee_discount.py. Unmeasured, not off"}
    # MAKER ROUTING IS A PROPERTY OF THE CODE, so it is asserted from the module rather than from an
    # artifact: if `maker_first` is importable, both money paths route through it by default.
    try:
        from libs.execution import maker_first

        out["maker_routing"] = {
            "state": "ON", "wait_s": maker_first.DEFAULT_WAIT_S,
            "why": ("entries quote passively before crossing on both the discretionary and margin "
                    "paths. Measured per run as `maker_share` in each executor's artifact -- if "
                    "that stays near zero the routing is falling back and the reason is in `why`")}
    except Exception as exc:
        out["maker_routing"] = {"state": "UNKNOWN", "why": f"{type(exc).__name__}: {exc}"}
    return out


def build() -> dict[str, Any]:
    switches = {}
    for sw in _SWITCHES:
        row = _probe(str(sw["path"]), secret=bool(sw.get("secret")))
        inverted = bool(sw.get("inverted"))
        row["inverted"] = inverted
        if row["state"] == "UNREADABLE":
            row["armed"] = None
        elif inverted:
            row["armed"] = row["state"] == "ABSENT"
        else:
            row["armed"] = row["state"] == "PRESENT"
        row["unlocks"] = sw["unlocks"]
        row["fix"] = sw["fix"]
        switches[str(sw["key"])] = row

    from libs.execution.ruin_rail import frozen

    rail_frozen, rail_why = frozen(_ROOT)
    blocking = [k for k, v in switches.items() if v["armed"] is False]
    unknown = [k for k, v in switches.items() if v["armed"] is None]
    return {
        "updated": datetime.now(tz=UTC).isoformat(),
        "switches": switches,
        "wallet": _wallet(),
        "exception_ledger": _exception(),
        "connectors": _connectors(),
        # COST, NOT PERMISSION. Reported beside the switches and excluded from `fully_armed` --
        # see `_cost_levers` for why merging the two would spoil the one number this file publishes.
        "cost_levers": _cost_levers(),
        "rail_frozen": rail_frozen, "rail_why": rail_why,
        "n_not_armed": len(blocking), "not_armed": blocking,
        "n_unknown": len(unknown), "unknown": unknown,
        "fully_armed": not blocking and not unknown and not rail_frozen,
        "arms_nothing": ("this organ READS. Every marker above is the principal's to write, and a "
                         "reporter that could arm the desk would be a fourth path to live trading "
                         "wearing the name of a status check"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rep = build()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=1), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=1))
        return 0

    verdict = "FULLY ARMED" if rep["fully_armed"] else "NOT FULLY ARMED"
    print(f"=== ARMING === {verdict}: {rep['n_not_armed']} switch(es) off, "
          f"{rep['n_unknown']} UNKNOWN, rail_frozen={rep['rail_frozen']}")
    for key, row in rep["switches"].items():
        mark = {True: "ARMED  ", False: "OFF    ", None: "UNKNOWN"}[row["armed"]]
        tag = " (rail: present = frozen)" if row["inverted"] else ""
        print(f"  [{mark}] {key:<20} {row['state']:<10} {row['path']}{tag}")
        if row["armed"] is not True:
            print(f"            {row['unlocks']}")
            print(f"            FIX: {row['fix']}")
        if row.get("warning"):
            print(f"            WARNING: {row['warning']}")

    w = rep["wallet"]
    print(f"\n  wallet: EFFECTIVE={w['effective']} (env={w['env_DESK_WALLET']}, "
          f"file={w['file_data_DESK_WALLET']})")
    for name, c in rep["connectors"].items():
        print(f"  connector {name:<7} armed={c['armed']} -- {str(c['why'])[:110]}")
    # COST LEVERS, PRINTED SEPARATELY FROM THE SWITCHES so nobody reads an unclaimed fee discount
    # as a reason the desk may not trade. They are here because nothing else asks the question.
    cl = rep.get("cost_levers") or {}
    for name, row in cl.items():
        print(f"  cost {name:<14} {row.get('state')} -- {str(row.get('why', ''))[:110]}")
    e = rep["exception_ledger"]
    print(f"  exception ledger: {e['state']}")
    for row in e.get("active", []):
        print(f"    {row['id']} suspends {row['law_suspended']} (granted {row['granted']})")
    if rep["rail_frozen"]:
        print(f"\n  RUIN RAIL LATCHED -- {rep['rail_why']}")
    print(f"\n-> {_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
