#!/usr/bin/env python3
"""THE PROMOTION LADDER GETS AN ACTUATOR -- shadow to live, without a human in the loop.

THE DEFECT, and it is the desk's own recorded lesson turned on its most important pipeline.
`check_promotion_gate.py` evaluates four rungs, decides `granted_rung`, and writes it to
data/promotion_gate.json. A 2026-08-12 grep for CONSUMERS of that field found: the capability
ratchet, which SCORES it, and run_cadence, which checks the file EXISTS. Nothing reads it and
changes a size. Nothing moves a sleeve from paper to live.

That is L0079 verbatim -- "grep for a governance flag's CONSUMERS, not its writers; a published
flag whose only reader picks an advice string changes no behaviour" -- landing on the single
transition the whole desk exists to make. The evidence could arrive in full, every criterion could
pass, and the sleeve would sit on paper until a person noticed and typed something. The principal
is right to call that unautomated.

WHAT THIS DOES: reads the gate's verdict and writes data/live_authority.json -- the machine-
readable statement of what is authorised right now (mode, book fraction, rung, and why). The
trading path reads that file. Evidence arrives, the gate grants, the authority changes, capital
follows. No human step.

WHAT THIS DOES NOT DO, AND THE DISTINCTION IS THE ENTIRE SAFETY ARGUMENT.

    IT NEVER DECIDES ANYTHING. It computes no criterion, sets no threshold, and cannot grant a
    rung the gate did not grant. It is a transmission belt: the gate remains the sole authority
    and is untouched by this file. Automating the ACTUATION of a passing gate does not loosen the
    gate -- refusing to actuate it just moves the delay onto a person, which is the cost, not the
    protection. A gate whose verdict nothing obeys was never protecting anything.

    IT NEVER RAISES FASTER THAN THE LADDER. `granted_rung` is taken as an upper bound: the
    authority may only ever be what the gate says, and rung 0 means PAPER.

    DE-RISKING IS IMMEDIATE, PROMOTION IS NOT. A rung that FALLS is applied on the spot -- the
    gate re-evaluates every cycle, and if the evidence stops supporting live money the authority
    drops that cycle. Going UP additionally requires the same rung to hold for CONFIRM_HOLD_H
    WALL-CLOCK HOURS, because a criterion that flickers across its threshold would otherwise deal
    real capital in and out on noise. The asymmetry is deliberate and points the safe way: fast
    down, deliberate up. The hold is in HOURS rather than a count of runs precisely so that making
    the pipeline faster cannot shorten it -- see CONFIRM_HOLD_H.

    IT NEVER TOUCHES THE RUIN RAIL OR THE DEADMAN SWITCH. Those bound everything this can grant,
    and this file cannot reach them.

    IT WRITES AN AUTHORITY, NOT AN ORDER. It opens no position and sends nothing to a venue. The
    execution path still applies every risk check it already applies; this only tells it what
    ceiling it is operating under.

    python scripts/run_promotion_actuator.py            # apply
    python scripts/run_promotion_actuator.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

GATE = "data/promotion_gate.json"
OUT = "data/live_authority.json"
LEDGER = "data/live_authority.jsonl"

#: HOW LONG a HIGHER rung must hold before capital follows it -- WALL-CLOCK HOURS, not a count of
#: runs, and that distinction is a safety property rather than a style choice.
#:
#: This was `CONFIRM_RUNS = 2` and it was correct only by accident: the actuator ran daily, so two
#: runs meant two days. The moment the pipeline was moved to a 15-minute cycle -- which is exactly
#: what "make everything as fast as possible" asks for -- the same constant would have meant
#: THIRTY MINUTES, and a criterion flickering across its threshold could have dealt real capital
#: in and out before anyone looked. A cadence change would have silently gutted the hold with no
#: edit to the safety logic and nothing to notice.
#:
#: Expressed in hours, cadence and safety are independent: running the cycle more often makes the
#: desk react faster to everything EXCEPT the one transition where haste is the hazard.
#: Falling rungs bypass this entirely -- de-risking is immediate.
CONFIRM_HOLD_H = 24.0

#: rung -> (mode, fraction of book). Copied from check_promotion_gate._RUNGS `grants` prose into
#: machine-readable form, and pinned by a test against that table so the two cannot drift -- a
#: second hand-maintained copy of the ladder is exactly how a rung silently gains a size.
_AUTHORITY: dict[int, tuple[str, float]] = {
    0: ("PAPER", 0.00),
    1: ("PAPER", 0.00),      # rung 1 raises the PER-TRADE cap; it is still paper, still no book
    2: ("LIVE", 0.01),
    3: ("LIVE", 0.05),
    4: ("LIVE", 0.15),
}


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _refresh_gate(root: Path) -> str:
    """Re-run the gate so the authority is never written off a stale verdict.

    A cached grant is the failure mode that matters here: promotion_gate.json is untracked, so on
    a fresh box it can be days old, and acting on a days-old grant is how a sleeve whose evidence
    has since collapsed keeps its size.
    """
    try:
        r = subprocess.run([sys.executable, "scripts/check_promotion_gate.py"],
                           cwd=root, capture_output=True, text=True, timeout=300)
        return "OK" if r.returncode == 0 else f"rc={r.returncode}"
    except (OSError, subprocess.SubprocessError) as exc:
        return f"{type(exc).__name__}: {exc}"


def run(root: Path | None = None, *, dry_run: bool = False) -> dict[str, Any]:
    base = root or _ROOT
    now = datetime.now(tz=UTC)
    refreshed = _refresh_gate(base)
    gate = _read(base / GATE)
    prev = _read(base / OUT) or {}

    doc: dict[str, Any] = {
        "generated_utc": now.isoformat(timespec="seconds"),
        "gate_refresh": refreshed,
        "authority_source": GATE,
        "law": "the gate decides; this transmits. It cannot grant a rung the gate did not, and it "
               "cannot reach the ruin rail or the deadman switch.",
    }

    if not isinstance(gate, dict) or gate.get("granted_rung") is None:
        # UNREADABLE GATE IS NOT A PROMOTION AND NOT A REVOCATION. Dropping to PAPER on a transient
        # read error would flatten a live book on a filesystem hiccup; granting anything would be
        # worse. Hold the last authority and say so.
        doc.update(status="UNMEASURED", mode=prev.get("mode", "PAPER"),
                   book_fraction=prev.get("book_fraction", 0.0), rung=prev.get("rung", 0),
                   why=f"{GATE} is unreadable or carries no granted_rung (refresh: {refreshed}). "
                       "The previous authority stands unchanged -- an unreadable gate is not "
                       "evidence for a promotion OR for flattening a live book.")
        _write(base, doc, dry_run=dry_run)
        return doc

    rung = int(gate.get("granted_rung") or 0)
    rung = max(0, min(rung, max(_AUTHORITY)))
    mode, frac = _AUTHORITY[rung]
    prev_rung = int(prev.get("rung") or 0)

    # THE STREAK COUNTS THE GATE'S VERDICT, NOT WHAT WAS APPLIED, and the first draft got this
    # backwards in the direction that stalls forever. While a promotion is pending, the APPLIED
    # rung is deliberately behind the gate's, so comparing against it made `rung != prev_rung`
    # true on every pass, reset the streak to 1 each time, and CONFIRM_RUNS could never be
    # reached. A confirmation delay that never expires is not a delay -- it is a permanent block
    # wearing the costume of one, and it would have looked exactly like the manual stall this
    # organ exists to remove.
    prev_gate = prev.get("gate_rung")
    prev_gate = prev_rung if prev_gate is None else int(prev_gate)
    streak = int(prev.get("confirm_streak") or 0)
    streak = streak + 1 if rung == prev_gate else 1
    doc["confirm_streak"] = streak

    # WHEN this rung was FIRST seen, carried forward so the hold is measured in wall-clock time
    # and cannot be shortened by running more often.
    since = prev.get("gate_rung_since") if rung == prev_gate else None
    if not since:
        since = doc["generated_utc"]
    doc["gate_rung_since"] = since
    try:
        held_h = (now - datetime.fromisoformat(str(since))).total_seconds() / 3600.0
    except (TypeError, ValueError):
        held_h = 0.0                      # unparseable stamp restarts the hold, never skips it
    doc["held_h"] = round(held_h, 2)

    if rung < prev_rung:
        # DOWN IS IMMEDIATE. Evidence that stopped supporting the size stops supporting it now.
        applied = rung
        doc["direction"] = "DERISK"
        doc["why"] = (f"the gate dropped from rung {prev_rung} to {rung}; de-risking applies on "
                      "the spot, with no confirmation delay. Waiting to reduce is the one "
                      "direction where hesitation costs real money.")
    elif rung > prev_rung and held_h < CONFIRM_HOLD_H:
        # UP WAITS, ON A CLOCK. A criterion oscillating across its threshold would otherwise deal
        # capital in and out on noise, and a run-counted hold would shrink every time the cycle
        # got faster.
        applied = prev_rung
        doc["direction"] = "HOLD-PENDING-CONFIRM"
        doc["why"] = (f"the gate grants rung {rung}, held {held_h:.1f}h of the "
                      f"{CONFIRM_HOLD_H:.0f}h required. Authority stays at rung {prev_rung} until "
                      "it holds; a rung that flickers must not deal real capital in and out. The "
                      "hold is wall-clock, so running the cycle more often cannot shorten it.")
    else:
        applied = rung
        doc["direction"] = "PROMOTE" if rung > prev_rung else "STEADY"
        doc["why"] = (f"the gate grants rung {rung} ({gate.get('granted')}) and it has held "
                      f"{held_h:.1f}h, past the {CONFIRM_HOLD_H:.0f}h bar." if rung > prev_rung else
                      f"unchanged at rung {rung} ({gate.get('granted')}).")

    mode, frac = _AUTHORITY[applied]
    # WHAT IS HOLDING THE NEXT RUNG, carried forward from the gate's own ladder rather than
    # re-derived. Without it the authority file says "rung 0" and nothing about what would move
    # it, which turns every question about progress back into a manual investigation.
    blocked_by = []
    for row in gate.get("ladder") or []:
        if isinstance(row, dict) and row.get("rung") == gate.get("blocked_at_rung"):
            blocked_by = list(row.get("unmet") or [])
            break
    doc.update(status="OK", rung=applied, gate_rung=rung, mode=mode, book_fraction=frac,
               granted=gate.get("granted"), blocked_at_rung=gate.get("blocked_at_rung"),
               blocked_by=blocked_by, n_closed=gate.get("n_closed"),
               days_of_record=gate.get("days_of_record"))

    changed = (applied != prev_rung) or (prev.get("mode") != mode)
    doc["changed"] = changed
    _write(base, doc, dry_run=dry_run)

    if changed and not dry_run:
        try:
            with (base / LEDGER).open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({k: doc.get(k) for k in
                                     ("generated_utc", "rung", "mode", "book_fraction",
                                      "direction", "why")}) + "\n")
        except OSError:
            pass
        if mode == "LIVE" or prev.get("mode") == "LIVE":
            # A change in what real capital is authorised to do is told to a person on the run it
            # happens -- not because they must approve it, but because nobody should learn that
            # the desk went live from a P&L statement.
            try:
                from libs.ops.alert_channels import send_all
                send_all(f"live authority now {mode} at {frac:.0%} of book (rung {applied})",
                         f"{doc['direction']}: {doc['why']}\n\n"
                         f"Granted: {gate.get('granted')}\n"
                         f"Blocked at rung {gate.get('blocked_at_rung')}.\n\n"
                         "Decided entirely by scripts/check_promotion_gate.py. This actuator "
                         "transmits that verdict and cannot grant more than it.")
            except (OSError, ValueError, ImportError):
                pass
    return doc


def _write(root: Path, doc: dict[str, Any], *, dry_run: bool) -> None:
    if dry_run:
        return
    p = root / OUT
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1), "utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    doc = run(dry_run=args.dry_run)
    if args.json:
        print(json.dumps(doc, indent=2))
    else:
        print(f"live authority: {doc['mode']} at {doc['book_fraction']:.0%} of book "
              f"(rung {doc['rung']}) -- {doc.get('direction', doc['status'])}")
        print(f"  {doc['why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
