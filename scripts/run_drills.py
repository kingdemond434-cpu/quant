"""SAFETY DRILLS -- the evidence `s2_entry_met` demands and has never been given.

GAP_REGISTER row #2 lists this as STILL OPEN for Gate 0: *"monthly host-death and ladder DRILLS
have never been run."* The S2 gate reads `critical_drill_failures`, and that field defaults to the
REFUSING sentinel (-1) precisely because no drill has ever produced a record. So the gate is
correctly closed, and it stays closed until something actually exercises the rails.

WHY A DRILL AND NOT A UNIT TEST, since the rails already have tests. A unit test asks "does this
function return the right value?". A drill asks "does the INVARIANT survive the event it exists
for?" -- process death mid-position, a pager that goes unanswered for four hours, a clock that
moves backwards. Those cross function boundaries and persisted state, which is exactly where the
2026-07-11 false-fire and the crash-loop-resets-the-timer class of bug live.

SAFETY, and it is absolute here: NO DRILL PLACES OR CANCELS A LIVE ORDER. Every drill runs against
the pure decision functions and against COPIES of the persisted state, in a temp directory. A
drill that could move money would be a larger risk than the one it certifies, which is the same
reasoning that keeps the canary a signed read pre-Gate-0.

    python scripts/run_drills.py            # run all drills, write the evidence record
    python scripts/run_drills.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_LOG = _ROOT / "data/drill_log.jsonl"
_OUT = _ROOT / "data/drill_report.json"


@dataclass
class Drill:
    name: str
    critical: bool
    passed: bool = False
    detail: str = ""
    checks: list[str] = field(default_factory=list)

    def check(self, ok: bool, what: str) -> bool:
        self.checks.append(f"{'PASS' if ok else 'FAIL'} {what}")
        return ok


def drill_host_death() -> Drill:
    """THE INVARIANT: a naked position's 60s clock must SURVIVE process death.

    The failure it exists for is not exotic -- a process that dies and respawns every 45s would
    reset the timer forever and never breach, so a crash-loop would defeat the rail silently while
    every individual restart looked healthy. This kills the process (by discarding the in-memory
    object) mid-clock and reloads from disk, which is what a real host death does.
    """
    from libs.execution.protective_stops import NAKED_GRACE_S, NakedWatch
    d = Drill("host_death_naked_clock", critical=True)
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "naked_watch.json"
        t0 = time.time()

        w = NakedWatch.load(p)
        w.observe({"BTCUSDT": 1.0}, t0)
        w.save()
        d.check(not w.breaches(t0 + 30.0), "no breach inside the 60s grace")

        # HOST DEATH: the in-memory object is gone. Only what reached disk survives.
        del w
        revived = NakedWatch.load(p)
        d.check(revived.first_seen.get("BTCUSDT") == t0,
                "first-seen timestamp survived process death")

        # The clock must keep running from the ORIGINAL sighting, not from the restart.
        breaches = revived.breaches(t0 + NAKED_GRACE_S + 5.0)
        d.check("BTCUSDT" in breaches,
                f"breach fires {NAKED_GRACE_S}s after FIRST sighting, not after restart")

        # A crash loop must not launder the clock: repeated reload+observe cannot reset it.
        for i in range(5):
            w2 = NakedWatch.load(p)
            w2.observe({"BTCUSDT": 1.0}, t0 + 10.0 * (i + 1))
            w2.save()
        final = NakedWatch.load(p)
        d.check(final.first_seen.get("BTCUSDT") == t0,
                "5 restart cycles did NOT reset the clock (crash-loop defeat blocked)")

        # Covering the position clears it -- otherwise a stale entry breaches forever.
        w3 = NakedWatch.load(p)
        w3.observe({}, t0 + 100.0)
        w3.save()
        d.check(not NakedWatch.load(p).breaches(t0 + 200.0),
                "clock clears once the position is covered")

    d.passed = all(c.startswith("PASS") for c in d.checks)
    d.detail = f"{sum(c.startswith('PASS') for c in d.checks)}/{len(d.checks)} checks"
    return d


def drill_derisk_ladder() -> Drill:
    """THE INVARIANT: the ladder is MONOTONE, and its top rung latches.

    A ladder that can step DOWN on its own turns an unanswered page into a self-clearing incident.
    A ladder that skips rungs flattens a book that only needed its resting orders cancelled.
    """
    from libs.ops.derisk_ladder import (
        LADDER,
        RUNG_CANCEL_HALVE_S,
        RUNG_FLATTEN_S,
        RUNG_FULL_FLATTEN_S,
        rung_for,
    )
    d = Drill("derisk_ladder", critical=True)

    d.check(rung_for(0.0).is_floor, "silent pager at t=0 is nominal")
    d.check(rung_for(RUNG_CANCEL_HALVE_S - 1).is_floor, "one second short of rung 1 is nominal")
    d.check(rung_for(RUNG_CANCEL_HALVE_S).name == "cancel_and_halve", "rung 1 fires exactly at its threshold")
    d.check(rung_for(RUNG_FLATTEN_S).name == "flatten_to_neutral", "rung 2 fires at its threshold")
    d.check(rung_for(RUNG_FULL_FLATTEN_S).name == "full_flatten_disarmed", "rung 3 fires at its threshold")

    # MONOTONE: severity may never fall as silence grows.
    sev = [LADDER.index(rung_for(t)) for t in
           (0, 60, RUNG_CANCEL_HALVE_S, RUNG_FLATTEN_S - 1, RUNG_FLATTEN_S,
            RUNG_FULL_FLATTEN_S, RUNG_FULL_FLATTEN_S * 10)]
    d.check(sev == sorted(sev), f"severity never decreases as silence grows: {sev}")

    # Rung 3 latches: it demands a human, and no amount of further time undoes that.
    top = rung_for(RUNG_FULL_FLATTEN_S * 100)
    d.check(top.requires_manual_rearm and not top.entries_allowed,
            "top rung latches -- entries stay disabled until a human re-arms")

    # CLOCK SKEW: a page stamped in the future must NOT wrap to a high rung and flatten the book.
    d.check(rung_for(-3600.0).is_floor, "negative age (NTP moved) reads nominal, never flatten")

    # Escalation implies the lower rung's actions too -- no gaps in what is switched off.
    d.check(all(r.cancel_resting for r in LADDER if not r.is_floor),
            "every non-nominal rung cancels resting orders")
    d.check(rung_for(RUNG_FLATTEN_S).size_multiplier == 0.0, "flatten rung sizes to zero")

    d.passed = all(c.startswith("PASS") for c in d.checks)
    d.detail = f"{sum(c.startswith('PASS') for c in d.checks)}/{len(d.checks)} checks"
    return d


def drill_ruin_rail_reentry() -> Drill:
    """THE INVARIANT (added 2026-07-30): the desk cannot clear its own ruin stop.

    The absorbing state found today is the reason this drill exists -- 113 consecutive flattens
    with no defined way back. The re-entry path must require real capital or a signed override,
    and must never be reachable from automation.
    """
    from libs.risk import capital_events as CE
    d = Drill("ruin_rail_reentry", critical=True)
    eq, start = 3139.86, 5000.0
    with tempfile.TemporaryDirectory() as td:
        ledger = Path(td) / "capital_events.jsonl"
        orig, CE.LEDGER = CE.LEDGER, ledger
        try:
            for kind, by, why in (("RESTART", "the executor", "clear the stop so we can trade"),
                                  ("RESTART", "cron", "automated maintenance rebase now")):
                try:
                    CE.rebase(equity_now=eq, start_equity=start, deposit_usd=0.0, kind=kind,
                              authorised_by=by, reason=why)
                    d.check(False, f"automation cleared the stop as {by} -- RAIL DEFEATED")
                except CE.CapitalEventRefused:
                    d.check(True, f"refused an unfunded re-base authorised by {by!r}")
            ev = CE.rebase(equity_now=eq, start_equity=start, deposit_usd=2000.0,
                           authorised_by="principal", reason="drill: funded re-base path")
            d.check(ev.start_equity_after == eq + 2000.0, "a funded deposit re-bases the inception")
            d.check(ledger.exists() and ledger.read_text().count("\n") == 1,
                    "exactly one event recorded -- refusals write nothing")
        finally:
            CE.LEDGER = orig
    d.passed = all(c.startswith("PASS") for c in d.checks)
    d.detail = f"{sum(c.startswith('PASS') for c in d.checks)}/{len(d.checks)} checks"
    return d


DRILLS = (drill_host_death, drill_derisk_ladder, drill_ruin_rail_reentry)


def run() -> dict[str, Any]:
    results = []
    for fn in DRILLS:
        try:
            results.append(fn())
        except Exception as exc:
            # A drill that CRASHES is a failed drill, never a skipped one. Treating an exception
            # as "inconclusive" is how a broken rail passes a safety review.
            bad = Drill(fn.__name__.replace("drill_", ""), critical=True)
            bad.detail = f"drill CRASHED: {type(exc).__name__}: {exc}"
            results.append(bad)
    critical_failures = sum(1 for r in results if r.critical and not r.passed)
    return {
        "at": datetime.now(tz=UTC).isoformat(),
        "n_drills": len(results),
        "passed": sum(1 for r in results if r.passed),
        # THE FIELD s2_entry_met READS. It defaults to the refusing sentinel elsewhere precisely
        # because an absent drill record must never satisfy a safety gate.
        "critical_drill_failures": critical_failures,
        "drills": [{"name": r.name, "critical": r.critical, "passed": r.passed,
                    "detail": r.detail, "checks": r.checks} for r in results],
        "safety": "No drill places or cancels a live order. Every drill runs pure decision "
                  "functions against temp-directory copies of persisted state.",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = run()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")
    with _LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({k: rep[k] for k in
                            ("at", "n_drills", "passed", "critical_drill_failures")}) + "\n")
    if args.json:
        print(json.dumps(rep, indent=2))
        return 0
    print(f"DRILLS {rep['passed']}/{rep['n_drills']} passed | "
          f"critical_drill_failures={rep['critical_drill_failures']}")
    for dr in rep["drills"]:
        print(f"  {'PASS' if dr['passed'] else 'FAIL'} {dr['name']:24} {dr['detail']}")
        for c in dr["checks"]:
            if c.startswith("FAIL"):
                print(f"        {c}")
    print(f"-> {_OUT.relative_to(_ROOT)}  (+ {_LOG.relative_to(_ROOT)})")
    return 0 if rep["critical_drill_failures"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
