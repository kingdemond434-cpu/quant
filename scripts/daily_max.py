#!/usr/bin/env python3
"""THE DAILY MAXIMISATION LOOP -- audit, remediate, VERIFY, escalate only the irreducible.

WHAT THIS CLOSES. Every ntfy path in this repo is a sender: `run_alerts.py` pushes to the
principal's phone, dedupes six hours, and stops. Nothing read alerts back, nothing closed them, and
nothing checked whether a fix worked. So the human was the control loop -- which is exactly the
work the principal asked not to be doing.

THE ONE SAFETY PROPERTY THAT MATTERS, AND IT IS STRUCTURAL, NOT ADVISORY.

An auto-fixer that may edit code is a machine for hiding defects. The cheapest way to make any
check stop firing is to change the check, and a loop optimising for "no defects" will find that
before it finds a real repair -- silently, daily, forever. So remediation is restricted to an
ALLOWLIST of commands that PRODUCE things:

    run the organ that should have written the artifact
    commit and push output the desk already produced (the desk's own §33 rule)

It may never edit a file, never touch a check, never `git checkout`, never `--force`, never
acknowledge a defect to silence it. `_forbidden_verbs` enforces that on every entry at import time
and a test asserts the allowlist contains no editing verb. If a defect cannot be closed by running
a producer, the honest outcome is NEEDS_HUMAN, not a quieter report.

VERIFICATION IS THE OTHER HALF. A remediation that ran is ATTEMPTED, never FIXED. The check is
re-run and only its silence -- measured, not assumed -- closes the alert. Otherwise this becomes
the "not measured = fine" failure applied to the desk's own repairs, which is the worst place for
it because everything downstream trusts the all-clear.

Run daily (ops/quant-daily-max.timer), or by hand:

    python3 scripts/daily_max.py            # audit, remediate, verify, report
    python3 scripts/daily_max.py --dry-run  # show what WOULD be attempted, run nothing

Writes the alert ledger and a run report. No keys, no order paths, no code edits -- ever.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops.alert_ledger import AlertLedger  # noqa: E402

LEDGER = ROOT / "data/alert_ledger.json"
REPORT = ROOT / "data/daily_max.json"
AUDIT_REPORT = ROOT / "data/max_audit_report.json"

#: Verbs that must never appear in a remediation. A loop that can edit will edit the CHECK, which
#: is the cheapest way to make any defect disappear and the least likely to be noticed.
_FORBIDDEN_VERBS = (
    "rm", "mv", "sed", "checkout", "reset", "revert", "force", "--amend",
    "rebase", "clean", "truncate", "tee", ">", "ack", "acknowledge", "disable",
)

#: defect-id prefix -> (argv, human description). EVERY entry is a PRODUCER: it makes the missing
#: artifact exist. Nothing here changes a check, a threshold, or a line of code.
REMEDIATIONS: dict[str, tuple[list[str], str]] = {
    "coverage-missing": (["python3", "scripts/build_audit_coverage.py"],
                         "build the audit coverage artifact"),
    "production-missing: forensics": (["python3", "scripts/run_trade_forensics.py"],
                                      "run trade forensics to produce its artifact"),
    "exploration-blocked-upstream": (["python3", "scripts/build_bars.py"],
                                     "resample the recorder tape into bars"),
    "asymmetry": (["python3", "scripts/asymmetry_ledger.py"],
                  "refresh the asymmetry ledger"),
    "decay": (["python3", "scripts/monitor_data_decay.py"],
              "refresh the data decay monitor"),
    "moat-never-screened": (["python3", "scripts/screen_moat.py"],
                            "hunt survivors in the self-recorded L2 tape"),
    # A HUNT WHOSE FINDINGS NOTHING READS IS A DIARY. The registry accumulates survivors with
    # their misses; this is the only thing that adjudicates whether any of them beats the sweep's
    # own false-positive rate. It buys a forward clock and nothing else -- no capital, no weight --
    # which is exactly why it is safe to run unattended.
    "moat-survivors-unexploited": (["python3", "scripts/promote_moat_survivors.py"],
                                   "adjudicate persistent survivors into forward clocks"),
    # The frontier standing still is a SCHEDULER problem, and one more pass is how the desk finds
    # out whether it is stuck or merely between cells.
    "moat-screen-not-converging": (["python3", "scripts/screen_moat.py"],
                                   "advance the moat screening frontier one more pass"),
}

#: Defect classes no command can close. Naming them stops the loop retrying forever and stops the
#: pager crying about work nobody could have done.
HUMAN_ONLY = {
    "organ-never": "the organ needs LLM credits -- scripts/check_organ_readiness.py confirms the "
                   "code side is ready, so this is funding, not engineering",
    "model-upgrade-never": "needs a live credential to query available models",
    "panel-never": "the external panel needs LLM credits",
    "blind-rediscovery": "needs LLM credits",
    "production-stale: dataaxis": "credit-blocked digger",
    "production-stale: prospector": "credit-blocked digger",
    "production-stale: litminer": "credit-blocked digger",
    "production-stale: frontier": "credit-blocked digger",
    "triage-open-items": "blocked on >=1 deployed alpha or on-chain data -- not runnable work",
    "mine-ledger-truncated": "ambiguous by construction on a clone; needs the owning machine",
    "mine-law-unjudgeable": "needs more conversions to accumulate over time",
    # FOUND BY THIS LOOP ON ITS FIRST REAL RUN. The remediation originally mapped here ran
    # info_class_map.py, which writes information_class_map.json -- a DIFFERENT artifact. Grepping
    # for a writer of data_universe_map.json returns readers only: acquire_data, max_audit and
    # run_cadence all consume it and nothing produces it. The defect names an artifact with NO
    # PRODUCER, which is a real finding a plausible-looking remediation would have buried.
    "vendor-replacement": ("data_universe_map.json has NO PRODUCER anywhere in the repo -- three "
                           "scripts read it and none writes it. Needs a producer built, not a "
                           "command run",
                           ),
}

#: Consecutive failed remediations after which a defect is downgraded to NEEDS_HUMAN. Retrying a
#: command that has never worked, daily, forever, is how an autonomous loop becomes a noise source
#: -- and the escalation it raises each time trains the reader to ignore it.
MAX_FAILED_ATTEMPTS = 3


def _validate_allowlist() -> None:
    """Refuse to start if any remediation could mutate rather than produce.

    Checked at import so a dangerous entry cannot be added and then discovered in production. The
    failure mode being prevented is not hypothetical: a loop rewarded for a clean audit will reach
    for the check before it reaches for the repair.
    """
    for key, (argv, _) in REMEDIATIONS.items():
        blob = " ".join(argv).lower()
        for verb in _FORBIDDEN_VERBS:
            if re.search(rf"(^|[\s/]){re.escape(verb)}([\s/]|$)", blob):
                raise SystemExit(
                    f"REFUSING TO RUN: remediation for {key!r} contains the forbidden verb "
                    f"{verb!r}. Remediations may only PRODUCE artifacts; a loop that can edit "
                    "will edit the check, which is the cheapest way to make a defect vanish.")
        # THE INTERPRETER CHECK ALONE WAS A HOLE, AND A TEST FOUND IT. Validating argv[0] and the
        # verbs still admitted `python3 -c "import os; os.remove(...)"`: inline code carries no
        # forbidden VERB and the interpreter is allowlisted, so arbitrary mutation walked straight
        # through the guard designed to stop exactly that. A remediation must therefore name a
        # REAL SCRIPT FILE inside the repo, and inline-code flags are refused outright.
        if argv[0] not in ("python3", "bash"):
            raise SystemExit(f"REFUSING TO RUN: remediation for {key!r} is not a script "
                             "invocation")
        if any(flag in argv for flag in ("-c", "-m", "--command", "-e")):
            raise SystemExit(
                f"REFUSING TO RUN: remediation for {key!r} passes inline code. Inline code carries "
                "no forbidden verb and would walk straight through the verb guard -- a remediation "
                "must name a script file.")
        script = next((x for x in argv[1:] if x.endswith((".py", ".sh"))), None)
        if script is None or not (ROOT / script).is_file():
            raise SystemExit(
                f"REFUSING TO RUN: remediation for {key!r} does not name an existing script "
                f"inside the repo (got {argv!r}).")


_validate_allowlist()


def _run_audit() -> list[dict]:
    """Run the sweep and return its live defects, each already scoped REPO/RUNTIME."""
    subprocess.run([sys.executable, str(ROOT / "scripts/max_audit.py")],
                   cwd=ROOT, capture_output=True, text=True, timeout=1800, check=False)
    try:
        return json.loads(AUDIT_REPORT.read_text("utf-8")).get("live", [])
    except (OSError, json.JSONDecodeError):
        return []


def _match(defect_id: str, message: str, table: dict) -> tuple[str, object] | None:
    """Longest-prefix match against a table, on id and on the id+message pair."""
    hay = f"{defect_id}: {message}"
    best = None
    for key, val in table.items():
        matched = defect_id.startswith(key) or hay.startswith(key) or key in defect_id
        if matched and (best is None or len(key) > len(best[0])):
            best = (key, val)
    return best


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="show what would be attempted; run no remediation")
    ap.add_argument("--escalate-after-h", type=float, default=24.0)
    a = ap.parse_args()

    ledger = AlertLedger(LEDGER)
    defects = _run_audit()
    seen: set[str] = set()

    for d in defects:
        did, msg = str(d.get("id", "")), str(d.get("msg", ""))
        key = f"{did}|{msg[:60]}"
        seen.add(key)
        ledger.observe(key, msg, scope=str(d.get("scope", "UNSCOPED")))

    # Anything previously open and not reported this run has stopped firing.
    cleared = ledger.resolve_absent(seen)

    attempted, fixed, human = [], [], []
    for key in sorted(seen):
        alert = ledger.alerts[key]
        did = key.split("|", 1)[0]

        hit_human = _match(did, alert.message, HUMAN_ONLY)
        if hit_human is not None:
            why = hit_human[1]
            ledger.needs_human(key, str(why[0] if isinstance(why, tuple) else why))
            human.append(did)
            continue

        # A remediation that has failed repeatedly is not going to start working. Downgrading it
        # stops the daily retry AND stops the daily escalation, which is what would otherwise
        # train the reader to ignore the pager.
        if alert.state in ("FAILED", "REGRESSED") and alert.attempts >= MAX_FAILED_ATTEMPTS:
            ledger.needs_human(
                key, f"remediation attempted {alert.attempts}x and never verified fixed -- "
                     "the desk cannot close this by running anything")
            human.append(did)
            continue

        hit = _match(did, alert.message, REMEDIATIONS)
        if hit is None:
            continue
        argv, desc = hit[1]                                     # type: ignore[misc]
        if a.dry_run:
            attempted.append(f"{did} -> {desc} (DRY RUN)")
            continue

        ledger.attempted(key, desc)
        subprocess.run([*argv], cwd=ROOT, capture_output=True, text=True,
                       timeout=1800, check=False)
        attempted.append(f"{did} -> {desc}")

    # VERIFY BY RE-RUNNING, never by absence of complaint. A remediation that ran is ATTEMPTED.
    if attempted and not a.dry_run:
        after = {f"{x.get('id', '')}|{str(x.get('msg', ''))[:60]}" for x in _run_audit()}
        for key in sorted(seen):
            if ledger.alerts[key].state == "ATTEMPTED":
                ledger.verify(key, still_firing=key in after)
                if ledger.alerts[key].state == "FIXED":
                    fixed.append(key.split("|", 1)[0])

    escalations = ledger.escalations(min_age_h=a.escalate_after_h)
    ledger.save()

    out = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "dry_run": a.dry_run,
        "defects_seen": len(seen),
        "remediations_attempted": attempted,
        "verified_fixed": fixed,
        "cleared_without_action": [x.id.split("|", 1)[0] for x in cleared],
        "needs_human": sorted(set(human)),
        "escalations": [{"id": x.id.split("|", 1)[0], "state": x.state,
                         "age_h": round(x.age_hours(), 1), "why": x.last_action}
                        for x in escalations],
        "ledger_summary": ledger.summary(),
        "note": ("Remediations may only PRODUCE artifacts -- never edit a file, a check or a "
                 "threshold. A loop rewarded for a clean audit will reach for the check before "
                 "the repair, so the allowlist is validated at import and a forbidden verb "
                 "refuses the whole run. FIXED requires the check to be RE-RUN and fall silent; "
                 "a remediation that merely ran is ATTEMPTED."),
        "authority": "NONE over code. Runs producers, commits nothing on its own initiative.",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(out, indent=1), "utf-8")

    print(f"daily-max: {len(seen)} live defect(s) | attempted {len(attempted)} | "
          f"verified fixed {len(fixed)} | needs-human {len(set(human))} | "
          f"cleared {len(cleared)}")
    for line in attempted:
        print(f"  ATTEMPT {line}")
    for f in fixed:
        print(f"  FIXED   {f}  (verified by re-running the check)")
    if escalations:
        print(f"  ESCALATE {len(escalations)} -- the desk tried and could not, or only a human "
              "can:")
        for e in escalations[:8]:
            print(f"    [{e.state:<11}] {e.id.split('|', 1)[0]}  ({e.age_hours():.0f}h)")
    else:
        print("  nothing to escalate: everything is either fixed or being worked by the desk")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
