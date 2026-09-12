"""Every organ declares what it must PRODUCE, and is judged on that, not on exit code 0.

WHY THIS EXISTS. Four separate failures on 2026-09-11, all with the same shape -- the organ
reported success and did nothing, and no artifact contradicted it:

  * MT5-Universe returned result 1 on every run for an unknown number of days; the expander
    never completed and the registry repair chained behind it never ran at all.
  * dashboard_relay logged "relay pass complete" every three minutes over a desk_state.json
    that had not moved in 149 minutes -- the scp was failing and the error went to a log
    another instance held open.
  * shadow_health reported `missing_sleeves: 0` while 87 lanes sat retired, because from its
    own point of view nothing was missing: it had retired them.
  * MT5-Gateway, MT5-DeskState and MT5-Healers all returned 0xC0000142 with no log at all,
    because the process never started.

And the same thing measured in the wild: in AI-Hypercomputer/xpk an hourly triage workflow
logged 6,290 successful runs and zero agent executions. Its gating search matched nothing,
every time. Green pipeline, no work.

THE RULE. "It ran" and "it did something" are different facts, and a task result only ever
answers the first. So each organ names an ARTIFACT and a MAX AGE: the contract is satisfied
when that file exists and is younger than the age its own cadence implies. A task that exits 0
without refreshing its artifact is FAILING and says so, and a task that exits non-zero while
its artifact is current is fine -- which matters, because several organs here legitimately
return non-zero as a verdict rather than as an error.

WHAT THIS IS NOT. It is not a scheduler and it does not restart anything: it is a VERIFIER, and
keeping it separate from the thing it judges is the whole point. It writes
`desks/mt5/reports/organ_contract.json` and prints a table.

    python ops/organ_contract.py            # report
    python ops/organ_contract.py --json     # the artifact only
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
OUT = DESK / "reports" / "organ_contract.json"

#: organ -> (artifact it must refresh, max age in minutes, what the artifact is FOR)
#: The age is the organ's cadence with room for one missed run: an organ on a 15-minute clock
#: is late at 40, not at 16, because a single slow pass is not a defect and an alarm that cries
#: at every slow pass gets muted, which is how a real one goes unseen.
CONTRACTS: dict[str, tuple[str, int, str]] = {
    "MT5-Gateway":        ("desks/mt5/data/gateway_state.json", 10,
                           "the pass state the executor writes every loop"),
    "MT5-AccountState":   ("desks/mt5/data/account_state.json", 45,
                           "the live equity the dashboard's account panel reads"),
    "MT5-DeskState":      ("web/desk_state.json", 45,
                           "the dashboard payload itself"),
    "MT5-AllocatorFast":  ("desks/mt5/reports/pf_allocation.json", 90,
                           "the book the gateway sizes from"),
    "MT5-StallWatch":     ("desks/mt5/data/stall_watch.json", 90,
                           "the organ-health snapshot"),
    "MT5-Shadow":         ("desks/mt5/reports/shadow/shadow_health.json", 180,
                           "forward-lane health and enrolment counts"),
    "MT5-Gauntlet":       ("desks/mt5/reports/UNIVERSAL_SURVIVORS.json", 240,
                           "the certificate registry"),
    # MIS-ATTRIBUTED UNTIL 2026-09-11, and the mistake was mine. `gauntlet_build_cursor.json` is
    # written by scripts/external_gauntlet.py -- MT5-Gauntlet -- not by the hourly cycle, so this
    # row held MT5-Hourly responsible for an artifact it does not produce and reported it FAILING
    # at 357m while the cycle was running normally. A contract that names the wrong artifact
    # manufactures a defect, which is worse than having no contract: it spends attention and
    # teaches the reader to distrust the board.
    #
    # The cursor's staleness WAS a real signal, just about a different organ -- the gauntlet was
    # re-testing one head of the docket forever because the rotation key never advanced. That is
    # now its own row below, where it can be read as what it is.
    "MT5-Hourly":         ("desks/mt5/data/events.jsonl", 180,
                           "every research leg appends here; silence means no leg ran"),
    # NOT A TASK, AND NAMING IT LIKE ONE COST A PERMANENT FALSE ALARM. There is no
    # `MT5-Gauntlet-Rotation` in the scheduler and there never was: rotation is a PROPERTY of
    # MT5-Gauntlet, measured by whether its build cursor advances. Because process_health joins
    # contracts to scheduled tasks by name, this row reported NOT_SCHEDULED -- "this organ cannot
    # run at all" -- on every single pass, about an organ that runs hourly and is healthy.
    #
    # The suffix makes the ownership explicit while keeping the signal, which is real and was
    # being drowned by the false half: a cursor that stops advancing means the docket has stopped
    # rotating and the tail is never reached, which is how 11,146 cells sat deferred forever.
    "MT5-Gauntlet (rotation)": ("desks/mt5/data/hypotheses/gauntlet_build_cursor.json", 240,
                                "which symbols the gauntlet last BUILT -- a stale cursor means "
                                "the docket has stopped rotating and the tail is never reached. "
                                "Owned by MT5-Gauntlet; this is not a task of its own"),
    "MT5-Universe":       ("desks/mt5/data/universe/universe.json", 1440,
                           "the symbol registry the whole hypothesis lane reads"),
    "MT5-LocalConvert":   ("desks/mt5/data/hypotheses/local_candidates.json", 180,
                           "deterministic row -> candidate conversion"),
    # THE ORGANS BUILT 2026-09-12. Every one was UNCONTRACTED on the day it was written, which is
    # the gap that lets a new organ stop without anyone noticing -- exactly the class the
    # principal asked to end. A contract is the difference between an organ and a hope.
    "MT5-DataAxis":       ("desks/mt5/reports/DATA_AXES.json", 180,
                           "which free data axes this box can actually reach"),
    "MT5-AxisIngest":     ("desks/mt5/reports/AXIS_INGEST.json", 1560,
                           "reachable axes turned into dated series a family can condition on"),
    "MT5-CEODocket":      ("desks/mt5/reports/CEO_DOCKET.json", 1560,
                           "the daily ranked proposals the frontier scout produced"),
    "MT5-NeverStale":     ("desks/mt5/reports/NEVER_STALE.json", 60,
                           "the watchdog's own reading -- if THIS goes stale nothing is watching"),
    "MT5-ProcessHealth":  ("desks/mt5/reports/process_health.json", 60,
                           "every process, its last run and whether it is healthy"),
    "MT5-Healers":        ("desks/mt5/logs/MT5-Healers.log", 180,
                           "proof the standing fixers actually ran"),
    "MT5-MoatRecorder":   ("desks/mt5/data/moat_coverage.json", 180,
                           "moat capture coverage"),
    # THE FOURTEEN UNCONTRACTED ORGANS (2026-09-12). Every one appeared on the board as
    # "no artifact contract: this process could stop and nothing would notice" -- which is
    # exactly the gap that lets a new organ die quietly, and the principal asked for it closed.
    #
    # EACH PATH WAS VERIFIED TO EXIST ON THE TRADING BOX BEFORE IT WAS WRITTEN HERE, with its
    # real age read at the same time. That check is not ceremony: this file already carries a
    # scar from naming an artifact its organ does not produce, which reported a healthy organ
    # FAILING at 357m and taught the reader to distrust the whole board. A contract pointed at
    # the wrong file manufactures a defect, and that is worse than having no contract.
    #
    # A LOG IS A LEGITIMATE ARTIFACT for an organ whose product is an ACTION rather than a
    # document -- the healer, the boot check, the deadman. MT5-Healers already worked this way.
    # What a log must never do is stand in for a document the organ genuinely writes.
    "MT5-Frontier":       ("desks/mt5/reports/FRONTIER_INTELLIGENCE.json", 180,
                           "the frontier scout's hourly intelligence sweep"),
    "MT5-MoatMiner":      ("desks/mt5/data/moat_miner_state.json", 180,
                           "which slice of the 245-symbol moat the miner last profiled"),
    "MT5-MoatSilver":     ("desks/mt5/logs/MT5-MoatSilver.log", 180,
                           "bronze -> silver day-file conversion for the moat tape"),
    "MT5-QQuantGatesCertify": ("desks/mt5/reports/QQUANT_GATES.json", 180,
                               "the qquant lane's gate verdicts"),
    "MT5-QQuantShadow":   ("desks/mt5/reports/shadow/qquant_shadow_state.json", 180,
                           "the qquant forward lane's clocks"),
    "MT5-RiskUnitsFence": ("data/risk_units.json", 180,
                           "the risk-unit fence -- what one R is worth per instrument"),
    "MT5-UniversalGate":  ("desks/mt5/logs/MT5-UniversalGate.log", 180,
                           "the ten-gate certifier; UNIVERSAL_SURVIVORS.json is MT5-Gauntlet's "
                           "row, so this watches that the gate RAN rather than its shared output"),
    "MT5-CacheWarm":      ("desks/mt5/logs/MT5-CacheWarm.log", 180,
                           "pre-warms the gauntlet's bar cache; when it stops, every sweep pays "
                           "the fetch cost again and the docket's tail is never reached"),
    "MT5-IdentityHealer": ("desks/mt5/logs/MT5-IdentityHealer.log", 180,
                           "clears IDENTITY_BROKEN clocks. It had NEVER ONCE RUN before "
                           "2026-09-12 and nothing noticed, which is this row's whole reason"),
    "MT5-TerminalBoot":   ("desks/mt5/logs/MT5-TerminalBoot.log", 180,
                           "keeps the MT5 terminal up -- without it every other organ's "
                           "market data goes stale while each reports success"),
    # DAILY OR EVENT-DRIVEN, so the age is generous on purpose. An alarm that fires on a
    # legitimately quiet organ is the cry-wolf failure, and these three are quiet by design.
    "MT5-ResearchReports": ("desks/mt5/reports/RESEARCH_REPORT_CLOCK.json", 1560,
                            "the research report clock"),
    "MT5-NewsDesk":       ("desks/mt5/logs/MT5-NewsDesk.log", 1440,
                           "the news daemon; its log moves when news moves, so a quiet window "
                           "is not a defect and only a silent DAY is"),
    "MT5-FusionDeadman":  ("desks/mt5/logs/fusion_deadman.log", 1440,
                           "the Fusion dead-man watch"),
    # THE ONLY LOSS ON THIS DESK THAT CANNOT BE UNDONE. Every other defect costs time; an
    # unrecorded day costs the thing the time was buying, because 2029 cannot re-record 2026.
    # 90 minutes against a 30-minute clock: this must be noticed inside the window the broker
    # still serves tick history for, not on a daily review.
    # WIRED 2026-09-12, after check_enforcement_execution measured libs/research/dist_shift.py
    # DECORATIVE: built 2026-07-29 and never called from outside its own module or its tests. A
    # detector that runs nowhere has detected nothing. Its first live pass flagged EURUSD DRIFT
    # with two funded sleeves riding on it.
    "MT5-ShiftWatch":     ("desks/mt5/reports/DIST_SHIFT.json", 180,
                           "whether each live sleeve's symbol still trades in the distribution "
                           "its thresholds were calibrated in"),
    "MT5-MoatCapture":    ("desks/mt5/reports/MOAT_CAPTURE.json", 90,
                           "per-day capture completeness -- which SYMBOLS a short day is "
                           "missing, while a targeted re-pull can still recover them"),
}


def _age_min(p: Path, now: datetime) -> float | None:
    try:
        return (now - datetime.fromtimestamp(p.stat().st_mtime, UTC)).total_seconds() / 60.0
    except OSError:
        return None


def check() -> dict:
    now = datetime.now(UTC)
    rows = []
    for organ, (rel, max_age, what) in sorted(CONTRACTS.items()):
        p = ROOT / rel
        age = _age_min(p, now)
        if age is None:
            verdict, why = "ABSENT", f"{rel} does not exist -- the organ has never produced it"
        elif age > max_age:
            verdict, why = "STALE", f"{age:.0f} min old against a {max_age} min contract"
        else:
            verdict, why = "OK", f"{age:.0f} min old"
        rows.append({"organ": organ, "artifact": rel, "max_age_min": max_age,
                     "age_min": None if age is None else round(age, 1),
                     "verdict": verdict, "why": why, "artifact_is": what})
    bad = [r for r in rows if r["verdict"] != "OK"]
    return {
        "measured_at": now.isoformat(timespec="seconds"),
        "contracts": len(rows),
        "ok": len(rows) - len(bad),
        "failing": len(bad),
        # STATUS IS THE WORST ROW, never an average. An average would let eleven healthy organs
        # hide the one that stopped, which is the failure this file exists to make impossible.
        "status": "OK" if not bad else "FAILING",
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rep = check()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rep, indent=1), encoding="utf-8")
    if a.json:
        print(json.dumps(rep, indent=1))
        return 0 if rep["status"] == "OK" else 1
    print(f"organ contracts: {rep['ok']}/{rep['contracts']} OK   status {rep['status']}")
    print(f"{'organ':<22}{'verdict':<9}{'age':>8}  artifact")
    print("-" * 96)
    for r in rep["rows"]:
        age = "-" if r["age_min"] is None else f"{r['age_min']:.0f}m"
        print(f"{r['organ']:<22}{r['verdict']:<9}{age:>8}  {r['artifact']}")
    if rep["failing"]:
        print()
        print("FAILING -- each of these reported success while producing nothing:")
        for r in rep["rows"]:
            if r["verdict"] != "OK":
                print(f"  {r['organ']:<22} {r['why']}")
                print(f"  {'':<22} the artifact is {r['artifact_is']}")
    print(f"\n-> {OUT}")
    return 0 if rep["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
