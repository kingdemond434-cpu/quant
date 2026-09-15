"""THE DELIBERATE RE-ENROLMENT `shadow_forward` ASKS FOR, PERFORMED -- and never guessed.

WHAT THIS IS FOR. `shadow_forward` refuses a cell whose symbol the universe policy will not let
the desk hypothesise in, and it makes that verdict TERMINAL on purpose:

    "TERMINAL, because this is not a transient. A symbol's lane changes only when the registry
     learns its asset class, and at that point the certificate can be RE-ENROLLED DELIBERATELY
     rather than drifting back in."                          -- shadow_forward.py, at the refusal

That is the right design. A clock that quietly un-refuses itself whenever a registry file changes
is a clock nobody can audit. But the deliberate step it names has no organ, so it never happened:
measured 2026-09-15, 161 of 460 shadow cells sat REFUSED_BY_UNIVERSE_POLICY -- 35% of the forward
clock -- and ALL 161 classify as `hypothesis` today. 23 of them carry n>=8 with positive forward
expectancy, including GBPNOK.overnight_gap_decay.asia at +1.765R over 10 trades and USDJPY.asia at
+0.815R over 14. The desk's own evidence was frozen behind a refusal that is no longer true of a
single one of them.

WHAT IT WILL AND WILL NOT DO. It re-enrols a cell ONLY when `universe_policy.may_hypothesise`
says yes for that symbol TODAY. It never invents a verdict, never touches a cell refused for any
other reason, and never re-enrols a symbol the policy still refuses -- equities stay refused,
which is the mandate the policy exists to enforce (`Apple` and `Coca-Cola` measure
`may_hypothesise=False` and are left exactly as they are).

It is also NOT a promotion. Re-enrolment returns a cell to ACTIVE so its clock runs again; the
promoter still decides, on its own gates, whether anything is ever traded. All this restores is
the right to be considered.

Every change is written to the artifact with the symbol, its lane, and the evidence the cell was
holding when it was unfrozen, so the decision is auditable after the fact rather than inferred
from a diff.

    python desks/mt5/research/reenrol_universe_refused.py            # report only
    python desks/mt5/research/reenrol_universe_refused.py --apply    # write it

Artifact: desks/mt5/reports/UNIVERSE_REENROLMENT.json
"""
from __future__ import annotations

import argparse
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

STATE = DESK / "reports" / "shadow" / "shadow_state.json"
OUT = DESK / "reports" / "UNIVERSE_REENROLMENT.json"

#: The status a re-enrolled cell returns to. ACTIVE is what an enrolled, unjudged clock carries;
#: anything else would be inventing a verdict this organ has no standing to give.
REENROLLED_STATUS = "ACTIVE"

REFUSED = "REFUSED_BY_UNIVERSE_POLICY"


def _symbol_of(key: str) -> str:
    """The instrument a shadow key names. Keys look like `USDJPY.asia#rr=2.5`."""
    return str(key).split(".", 1)[0].split("#", 1)[0].strip()


def measure() -> dict[str, Any]:
    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"status": "UNMEASURED",
                "why": f"shadow_state.json unreadable ({type(exc).__name__})"}
    try:
        from universe_policy import lane, may_hypothesise
    except Exception as exc:                                        # noqa: BLE001
        # NO POLICY MODULE MEANS NO AUTHORITY TO RE-ENROL. Failing closed here matters more than
        # usual: the alternative reads "the policy could not be loaded, so everything is allowed".
        return {"status": "UNMEASURED",
                "why": f"universe_policy unavailable ({type(exc).__name__}: {exc}); "
                       f"refusing to re-enrol without the rule that would justify it"}

    refused = {k: v for k, v in state.items()
               if isinstance(v, dict) and str(v.get("status")) == REFUSED}
    eligible, still_refused = [], []
    for key, st in sorted(refused.items()):
        sym = _symbol_of(key)
        try:
            ok, ln = bool(may_hypothesise(sym)), str(lane(sym))
        except Exception:                                           # noqa: BLE001
            ok, ln = False, "ERROR"
        row = {"cell": key, "symbol": sym, "lane": ln,
               "n": st.get("n"), "exp_r": st.get("exp_r"),
               "days_active": st.get("days_active"),
               "last_entry": st.get("last_entry")}
        (eligible if ok else still_refused).append(row)

    eligible.sort(key=lambda r: -(r.get("exp_r") or 0.0))
    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "status": "OK",
        "n_cells": len(state),
        "n_refused": len(refused),
        "n_eligible": len(eligible),
        "n_still_refused": len(still_refused),
        "n_eligible_with_evidence": sum(1 for r in eligible
                                        if (r.get("n") or 0) >= 8 and (r.get("exp_r") or 0) > 0),
        "eligible": eligible,
        "still_refused": still_refused[:40],
        "rule": (
            "A cell is re-enrolled iff universe_policy.may_hypothesise is TRUE for its symbol "
            "today. Re-enrolment returns the clock to ACTIVE and restores nothing else: the "
            "promoter still decides, on its own gates, whether the cell ever trades."),
    }


def apply(doc: dict[str, Any]) -> int:
    """Return the cells named in `doc['eligible']` to ACTIVE. Returns how many changed."""
    if doc.get("status") != "OK" or not doc.get("eligible"):
        return 0
    state = json.loads(STATE.read_text(encoding="utf-8"))
    stamp = datetime.now(tz=UTC).isoformat(timespec="seconds")
    n = 0
    for row in doc["eligible"]:
        st = state.get(row["cell"])
        if not isinstance(st, dict) or str(st.get("status")) != REFUSED:
            continue
        st["status"] = REENROLLED_STATUS
        # THE AUTHORITY FLAGS ARE NOT RESTORED HERE. The refusal cleared them and only the
        # promoter's own gates may grant them again; handing them back would be this organ
        # promoting, which is exactly what it must not do.
        st["reenrolled_at"] = stamp
        st["reenrolled_why"] = (
            f"{row['symbol']} is in the {row['lane']} lane today, so universe_policy."
            f"may_hypothesise permits it. The refusal was correct when written and is stale: "
            f"it is cleared deliberately, as shadow_forward's terminal-status note asks.")
        state[row["cell"]] = st
        n += 1
    if n:
        STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")
    return n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the re-enrolment")
    a = ap.parse_args(argv)
    doc = measure()
    if doc.get("status") != "OK":
        print(f"universe re-enrolment: {doc['status']} -- {doc['why']}")
        return 0
    print(f"universe re-enrolment: {doc['n_refused']} refused cell(s); "
          f"{doc['n_eligible']} now permitted, {doc['n_still_refused']} correctly still refused")
    print(f"  of the permitted, {doc['n_eligible_with_evidence']} carry n>=8 and positive "
          f"forward expectancy")
    for r in doc["eligible"][:12]:
        print(f"   {r['cell'][:38]:40} n={r['n'] or 0:>3} exp_r={(r['exp_r'] or 0):+.3f} "
              f"lane={r['lane']}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    if not a.apply:
        print(f"-> {OUT}  (--apply not given; shadow_state.json unchanged)")
        return 0
    n = apply(doc)
    print(f"RE-ENROLLED {n} cell(s) -> {REENROLLED_STATUS}; their clocks run again on the next "
          f"shadow pass. Promotion remains the promoter's decision.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
