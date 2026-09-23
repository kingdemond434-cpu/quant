#!/usr/bin/env python3
"""FINDING LIFECYCLE LEDGER (build #1, principal 2026-07-21).

THE HOLE THIS CLOSES: panels produced 27 rulings on 2026-07-20 -- 7 rejected, 20 ACCEPTED --
and nothing tracked what happened to those 20. An accepted finding could sit unbuilt forever
with nothing flagging it (GAP #37, an unbounded market-order path on the risk lane, is exactly
this shape). Worse, ledger #115 declares that panel seats are governed by scorecard hit-rates,
but panel_scorecard.json tracks only whether a model RESPONDED -- never whether it was RIGHT.
That made the governance policy unenforceable: a rule with no data behind it.

WHAT THIS ADDS: an explicit lifecycle per finding -- raised -> triaged -> fixed -> verified --
with the model that raised it recorded. From that falls out (a) accepted-but-unfixed findings
as a REPORTED DEFECT with an age, and (b) a real per-seat hit-rate (raised & accepted & fixed)
which is the number seat swaps were always supposed to use.

Usage:
  track_findings.py add   --model M --summary S [--severity high] [--ruling accepted]
  track_findings.py fix   --id F --commit SHA
  track_findings.py verify --id F
  track_findings.py report            # defect view: accepted & unfixed, oldest first
  track_findings.py scorecard         # per-seat hit-rates (the governance data)
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

LEDGER = Path(__file__).resolve().parent.parent / "data/findings_ledger.json"
UNFIXED_DEFECT_D = 14.0          # accepted+unfixed beyond this is a reported defect

#: How long an escalation silences `findings-rotting` before it must be renewed or resolved.
#: THE HOLD IS THE WHOLE POINT. An escalation stops a fence firing, so it is exactly the exit an
#: inconvenient finding would hide behind; with no clock it is an amnesty, not a routing decision.
#: Same number as UNFIXED_DEFECT_D on purpose -- one bar for "this has been owed too long",
#: whether the debtor is a seat or a person.
ESCALATION_HOLD_D = 14.0
#: Ceiling on a hand-set hold. A caller may shorten the clock (a fast decision is owed sooner);
#: lengthening it past a month is the amnesty arriving by way of a flag, so it is refused.
ESCALATION_MAX_HOLD_D = 30.0
#: An escalation must NAME a person and say why the repair is theirs. Measured against the
#: thin forms actually seen in review ("not mine", "tier 3"), which say nothing a reader can act
#: on and would let the exit become a shrug.
ESCALATION_MIN_REASON = 40


def _load() -> dict:
    if LEDGER.exists():
        try:
            return json.loads(LEDGER.read_text("utf-8"))
        except Exception:
            pass
    return {"findings": [], "next_id": 1}


def _save(d: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(d, indent=1), "utf-8")


def _age_d(iso: str | None) -> float:
    if not iso:
        return 0.0
    try:
        return (datetime.now(tz=UTC) - datetime.fromisoformat(iso)).total_seconds() / 86400
    except Exception:
        return 0.0


def add(a) -> None:
    d = _load()
    fid = f"F{d['next_id']:04d}"
    d["next_id"] += 1
    d["findings"].append({
        "id": fid, "model": a.model, "summary": a.summary[:400],
        "severity": a.severity, "ruling": a.ruling,
        "raised": datetime.now(tz=UTC).isoformat(),
        "fixed": None, "fix_commit": None, "verified": None,
    })
    _save(d)
    print(f"{fid} recorded ({a.ruling}, {a.severity}, {a.model})")


def _set(a, field: str, extra: dict | None = None) -> None:
    d = _load()
    for f in d["findings"]:
        if f["id"] == a.id:
            f[field] = datetime.now(tz=UTC).isoformat()
            if extra:
                f.update(extra)
            _save(d)
            print(f"{a.id} -> {field}")
            return
    raise SystemExit(f"{a.id} not found")


def supersede(a) -> None:
    """A finding whose MECHANISM was later refuted, closed by the finding that replaced it.

    THE MISSING EXIT. The lifecycle was raised -> fixed -> verified, and `ruling` is set once at
    `add` time, so a finding that a later panel proves WRONG had nowhere to go. Both available
    moves were bad: leave it accepted-and-unfixed, where it rots and fires `findings-rotting`
    forever on work nobody should do; or mark it `fix`ed, which is a false claim that removes it
    from view permanently AND credits the seat that raised it with a hit it did not earn -- the
    scorecard is the desk's per-seat calibration, so a fake fix corrupts the number governance
    uses to decide which models to keep.

    MEASURED 2026-08-13: F0004 ("carry book in ABSORBING risk state, ruin-floor -37.2%") is
    superseded by F0020, which read the live risk file and found action=pause_opens at -17.65%
    against a -35% bar -- "whose mechanism and number are WRONG" in its own words. F0004 had been
    accepted-and-unfixed for 14.6d with no legal way to close it.

    SUPERSESSION IS NOT A FIX AND IS SCORED AS NEITHER. It does not set `fixed`, so the seat gets
    no hit; it does not delete the row, so the history stays auditable. It REQUIRES the successor
    id, because "this was wrong" with no pointer to what replaced it is how a real problem gets
    closed by assertion -- the successor carries the live version of the concern, and if there
    genuinely is none, the finding is not superseded and must be argued on its own terms.
    """
    d = _load()
    ids = {f["id"] for f in d["findings"]}
    if a.by not in ids:
        raise SystemExit(f"successor {a.by} not found -- supersession needs the row that "
                         f"replaced this one, or it is just a deletion with a reason attached")
    if a.by == a.id:
        raise SystemExit("a finding cannot supersede itself")
    _set(a, "superseded", {"superseded_by": a.by, "supersede_reason": a.reason[:400]})


def escalation_lapsed(f: dict) -> bool:
    """Has this row's escalation hold expired? False when it was never escalated.

    THE DIRECTION OF EVERY DOUBT IS "LAPSED". A row with no `escalated` stamp is not covered by
    this exit at all, so it returns False and the ordinary rot clock keeps running on it -- the
    absence resolves to the COUNTED side (L1.28a), never to a silent exemption. But a stamp that
    is PRESENT and unreadable, or a hold that is present and not a sane number of days, returns
    True: an escalation that cannot prove its clock is still running has stopped running. That
    asymmetry is the whole guard. A corrupt value reading as an indefinite hold is how an amnesty
    arrives by way of a typo, and it would be invisible precisely because nothing fires.
    """
    stamp = f.get("escalated")
    if not stamp or not isinstance(stamp, str):
        return False                       # never escalated -- not covered, not exempt
    try:
        age_d = (datetime.now(tz=UTC) - datetime.fromisoformat(stamp)).total_seconds() / 86400.0
    except (TypeError, ValueError):
        return True                        # unreadable stamp: cannot prove the hold is live
    hold = f.get("escalation_hold_d", ESCALATION_HOLD_D)
    if isinstance(hold, bool) or not isinstance(hold, int | float):
        return True                        # corrupt hold: never an indefinite exemption
    if not (0 < float(hold) <= ESCALATION_MAX_HOLD_D):
        return True
    return age_d > float(hold)


def escalate(a) -> None:
    """A finding proved RIGHT whose repair is legally reserved to a HUMAN, routed to that human.

    THE MISSING EXIT, one state over from `supersede`. F0025 asks for a change to
    `scripts/run_deadman_switch.py` -- the Tier-3 ruin rail, which every worker prompt on this
    desk forbids editing, principal sign-off only. Both available moves were bad in exactly
    supersede's way: leave it accepted-and-unfixed, where `findings-rotting` fires forever
    demanding work nobody is permitted to do, or `fix` it, a false claim that removes it from
    view permanently AND credits the seat with a hit it did not earn.

    ESCALATION IS NOT A FIX AND IS SCORED AS NEITHER. It never sets `fixed`, so the scorecard --
    the desk's per-seat calibration -- stays honest; it deletes no row, so the history stays
    auditable; and it carries a CLOCK, because an exit that stops a fence firing and never
    expires is an amnesty. When the hold lapses the fence fires a DIFFERENT, louder defect
    naming the person it is owed by, rather than folding back into generic rot: those two states
    want different responses from whoever reads them.
    """
    to = str(getattr(a, "to", "") or "").strip()
    if not to:
        raise SystemExit("escalation must NAME the person it is owed by -- an escalation to "
                         "nobody is an accepted finding with a nicer label")
    reason = str(getattr(a, "reason", "") or "").strip()
    if len(reason) < ESCALATION_MIN_REASON:
        raise SystemExit(
            f"escalation reason is {len(reason)} chars, under the {ESCALATION_MIN_REASON} "
            "minimum. Say WHY the repair is reserved to a human and what they must decide -- "
            "'not mine' stops a fence firing while telling the next reader nothing")
    hold = a.hold_days if getattr(a, "hold_days", None) is not None else ESCALATION_HOLD_D
    try:
        hold = float(hold)
    except (TypeError, ValueError):
        raise SystemExit(f"--hold-days {a.hold_days!r} is not a number of days") from None
    if not (0 < hold <= ESCALATION_MAX_HOLD_D):
        raise SystemExit(
            f"--hold-days must be >0 and <={ESCALATION_MAX_HOLD_D:.0f}; got {hold:g}. A hold "
            "past a month is not a routing decision, it is an amnesty with a flag on it")
    # Validated BEFORE any write: a refused escalation must leave the row exactly as it was,
    # or a rejected attempt would still have silenced the fence.
    _set(a, "escalated", {"escalated_to": to, "escalation_reason": reason[:400],
                          "escalation_hold_d": hold})


def report(_a) -> None:
    d = _load()
    acc = [f for f in d["findings"] if f["ruling"] == "accepted"]
    superseded = [f for f in acc if f.get("superseded_by")]
    unfixed = sorted((f for f in acc if not f["fixed"] and not f.get("superseded_by")),
                     key=lambda f: f["raised"])
    print(f"ACCEPTED: {len(acc)} | FIXED: {sum(1 for f in acc if f['fixed'])} | "
          f"SUPERSEDED: {len(superseded)} | UNFIXED: {len(unfixed)}")
    overdue = [f for f in unfixed if _age_d(f["raised"]) > UNFIXED_DEFECT_D]
    if overdue:
        print(f"\n!! {len(overdue)} ACCEPTED FINDINGS UNFIXED >{UNFIXED_DEFECT_D:.0f}d "
              "-- these are DEFECTS, name them in the cycle report:")
    for f in unfixed:
        # An escalated row is LISTED, never hidden -- it is still owed, just owed by a named
        # person on their own clock. LAPSED is the loud state and reads as one.
        if f.get("escalated"):
            flag = "LAPSED" if escalation_lapsed(f) else " esc"
        else:
            flag = "DEFECT" if _age_d(f["raised"]) > UNFIXED_DEFECT_D else "open"
        print(f"  [{flag:>6}] {f['id']} {_age_d(f['raised']):>5.1f}d {f['severity']:<6} "
              f"{f['model'][:22]:<22} {f['summary'][:70]}")
    # Listed, never silently dropped: a closed-as-wrong finding leaving no trace in the report is
    # the same disappearance the ledger exists to prevent, one state over.
    for f in superseded:
        print(f"  [ super] {f['id']} -> {f['superseded_by']:<6} {f['summary'][:70]}")


def scorecard(_a) -> None:
    """The number seat governance was always supposed to use: was the model RIGHT?"""
    d = _load()
    by: dict[str, dict] = {}
    for f in d["findings"]:
        s = by.setdefault(f["model"], {"raised": 0, "accepted": 0, "fixed": 0, "rejected": 0})
        s["raised"] += 1
        s["accepted" if f["ruling"] == "accepted" else "rejected"] += 1
        if f["fixed"]:
            s["fixed"] += 1
    print(f"{'MODEL':<44} {'RAISED':>6} {'ACC':>5} {'FIXED':>6} {'HIT%':>6}")
    print("-" * 72)
    for m, s in sorted(by.items(), key=lambda kv: -(kv[1]["fixed"] / max(1, kv[1]["raised"]))):
        hit = 100.0 * s["fixed"] / max(1, s["raised"])
        print(f"{m:<44} {s['raised']:>6} {s['accepted']:>5} {s['fixed']:>6} {hit:>5.1f}%")
    if not by:
        print("(empty -- the brain populates this during panel triage)")


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--model", required=True)
    a.add_argument("--summary", required=True)
    a.add_argument("--severity", default="med")
    a.add_argument("--ruling", default="accepted", choices=["accepted", "rejected"])
    a.set_defaults(fn=add)
    fx = sub.add_parser("fix")
    fx.add_argument("--id", required=True)
    fx.add_argument("--commit", default=None)
    fx.set_defaults(fn=lambda x: _set(x, "fixed", {"fix_commit": x.commit}))
    v = sub.add_parser("verify")
    v.add_argument("--id", required=True)
    v.set_defaults(fn=lambda x: _set(x, "verified"))
    sp = sub.add_parser("supersede")
    sp.add_argument("--id", required=True)
    sp.add_argument("--by", required=True, help="the finding that replaced this one")
    sp.add_argument("--reason", required=True, help="what was refuted, and by what evidence")
    sp.set_defaults(fn=supersede)
    es = sub.add_parser("escalate")
    es.add_argument("--id", required=True)
    es.add_argument("--to", required=True, help="the person the repair is reserved to")
    es.add_argument("--reason", required=True,
                    help="why a human must decide, and what they must decide")
    es.add_argument("--hold-days", type=float, default=None,
                    help=f"shorten the hold (default {ESCALATION_HOLD_D:g}d, "
                         f"max {ESCALATION_MAX_HOLD_D:g}d)")
    es.set_defaults(fn=escalate)
    sub.add_parser("report").set_defaults(fn=report)
    sub.add_parser("scorecard").set_defaults(fn=scorecard)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
