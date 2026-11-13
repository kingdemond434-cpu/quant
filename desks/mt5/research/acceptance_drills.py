#!/usr/bin/env python3
"""THE EIGHT ACCEPTANCE DRILLS, RUN IN SHADOW AND PUBLISHED AS ACCEPTANCE EVIDENCE.

    python desks/mt5/research/acceptance_drills.py           # hourly leg `acceptance_drills`
    python desks/mt5/research/acceptance_drills.py --json

WHY (ARCH-18, principal 2026-10-07): "per requirement publish implementation path, runtime
identity, tested behaviour, evidence timestamp, remaining blocker and research/production impact;
run acceptance drills (replay, fresh/stale/revised info, model-to-decision, no duplicate
execution, reconciliation, rollback+restore, research under load, latency without excess
trading) in shadow".

The drills themselves already run, each on its own organ's clock and none on the money path:
the gateway under a faulty MT5 double, the sandbox rollback, the off-site restore, the PIT
canaries, the replay parity audit, the order door's duplicate guard, the reconciliation join and
the load drill. `recovery_drills` grades every one of them into a row of RECOVERY_DRILLS.json.
What was missing is the ACCEPTANCE half: no drill was a requirement of the acceptance package, so
GLOBAL_RESEARCH_ACCEPTANCE could read every function CURRENT_VERIFIED while the drill that proves
it had never run.

WHAT THIS DOES. Each of the eight drills is mapped to the scorecard rows that prove it
(`DRILLS`). A drill is PASS only when every one of its rows PASSED on a fresh scorecard; FAIL when
any row failed; UNMEASURED otherwise, naming the rows (a row this tree does not yet grade is
UNMEASURED by name, never skipped). It writes:

    reports/ACCEPTANCE_DRILLS.json                one row per drill, with the publication fields
    reports/acceptance_drills/<drill>.json        a runtime proof per drill, read by
                                                  global_research_acceptance through the addendum
                                                  docs/research/acceptance_drills_v1.json

A proof carries the release it ran on and `completed_work` = rows measured. It never claims
`tests_passed`: this organ runs no tests, and the box must not run pytest against its own state
(the suite's integrity guard restores git HEAD over tracked files), so the acceptance row stays
PARTIAL on `tests_not_attested` until something that runs the tests attests them -- the honest
reading, not a gap in this file.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
REPORTS = DESK / "reports"
SCORECARD = REPORTS / "RECOVERY_DRILLS.json"
OUT = REPORTS / "ACCEPTANCE_DRILLS.json"
PROOFS = REPORTS / "acceptance_drills"
MAX_SCORECARD_AGE_H = 3.0
PASS, FAIL, UNMEASURED = "PASS", "FAIL", "UNMEASURED"

#: drill -> (the principal's words, the scorecard rows that prove it, impact lane, the code that
#: runs it). The rows are recovery_drills' own ids.
DRILLS: dict[str, dict[str, Any]] = {
    "replay": {
        "title": "replay: a decision reproduced from its recorded state",
        "rows": ("reproducibility", "journal_replay"), "impact": "production",
        "implementation": ("desks/mt5/research/state_replay_audit.py",
                           "desks/mt5/research/ops_redundancy.py")},
    "information_freshness": {
        "title": "fresh, stale and revised information handled point in time",
        "rows": ("stale_data", "stale_quote", "revision_leakage"), "impact": "research",
        "implementation": ("scripts/check_pit_canaries.py",
                           "desks/mt5/mt5desk/desk_staleness.py")},
    "model_to_decision": {
        "title": "model to decision: malformed beliefs refused, missing quote refused",
        "rows": ("malformed_forecast", "no_quote"), "impact": "production",
        "implementation": ("desks/mt5/research/forecast_contract.py",
                           "desks/mt5/mt5desk/gateway.py")},
    "no_duplicate_execution": {
        "title": "no duplicate execution: in-doubt resend refused, one order authority",
        "rows": ("duplicate_delivery", "duplicate_positions", "missing_ack"),
        "impact": "production",
        "implementation": ("desks/mt5/mt5desk/order_door.py",
                           "desks/mt5/research/ops_redundancy.py")},
    "reconciliation": {
        "title": "reconciliation: positions, deals and the internal ledger agree",
        "rows": ("reconciliation", "account_ledger", "restore_reconcile"),
        "impact": "production",
        "implementation": ("desks/mt5/research/execution_reconcile.py",
                           "desks/mt5/research/recovery_drills.py")},
    "rollback_restore": {
        "title": "rollback to the last sealed release and restore from backup",
        "rows": ("rollback", "backup_restore", "offbox_restore"), "impact": "production",
        "implementation": ("libs/tiers/rollback.py", "desks/mt5/scripts/offsite_backup.py")},
    "research_under_load": {
        "title": "research under load leaves the trading path its latency and priority",
        "rows": ("load", "workload_separation"), "impact": "production",
        "implementation": ("desks/mt5/research/load_isolation_drill.py",)},
    "latency_without_excess_trading": {
        "title": "latency without excess trading: the trading path stays fast and sends no "
                 "duplicate or unintended order",
        "rows": ("load", "duplicate_positions", "reconciliation"), "impact": "production",
        "implementation": ("desks/mt5/research/load_isolation_drill.py",
                           "desks/mt5/research/execution_reconcile.py")},
}


#: Implementation files that land with a sibling branch, not this one. Until they merge the
#: acceptance audit reports them as missing implementation -- evidence debt, by name.
PENDING_ON: dict[str, str] = {
    "desks/mt5/research/execution_reconcile.py": "PR #853 (ARCH-06 execution reconciliation)",
    "desks/mt5/research/load_isolation_drill.py": ("branch claude/truth-arch07-ops-drills "
                                                   "(ARCH-07 load and separation drills)"),
}


def _release() -> str:
    named = os.environ.get("QUANT_RELEASE_ID", "").strip()
    if named:
        return named
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                                       stderr=subprocess.DEVNULL, timeout=5).strip()
    except (OSError, subprocess.SubprocessError):
        return "UNMEASURED"


def _ts(x: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _scorecard(now: datetime, path: Path | None = None) -> tuple[dict[str, dict[str, Any]],
                                                                 str | None, str | None]:
    """(rows by drill id, scorecard stamp, why it cannot be used)."""
    p = path or SCORECARD
    try:
        doc = json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return {}, None, "RECOVERY_DRILLS.json absent or unreadable on this host"
    stamp = _ts((doc or {}).get("generated_utc"))
    if stamp is None:
        return {}, None, "RECOVERY_DRILLS.json carries no generated_utc"
    age = (now - stamp).total_seconds() / 3600.0
    if age > MAX_SCORECARD_AGE_H:
        return {}, stamp.isoformat(), (f"RECOVERY_DRILLS.json is {age:.1f}h old "
                                       f"(> {MAX_SCORECARD_AGE_H}h): recovery_drills stopped")
    rows = {str(r.get("drill")): r for r in (doc or {}).get("drills") or []
            if isinstance(r, dict)}
    return rows, stamp.isoformat(), None


def grade(now: datetime | None = None, *, scorecard: Path | None = None,
          release: str | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    rows, stamp, why = _scorecard(now, scorecard)
    rel = release or _release()
    out: list[dict[str, Any]] = []
    for did, spec in DRILLS.items():
        got = {r: rows.get(r) for r in spec["rows"]}
        verdicts = {r: (g or {}).get("verdict", "ABSENT") for r, g in got.items()}
        if why:
            verdict, reason = UNMEASURED, why
        elif any(v == FAIL for v in verdicts.values()):
            verdict = FAIL
            reason = "; ".join(f"{r}: {(got[r] or {}).get('why')}" for r, v in verdicts.items()
                               if v == FAIL)[:600]
        elif all(v == PASS for v in verdicts.values()):
            verdict, reason = PASS, "every proving row passed on a fresh scorecard"
        else:
            verdict = UNMEASURED
            reason = "not yet proven: " + ", ".join(f"{r}={v}" for r, v in verdicts.items()
                                                    if v != PASS)
        measured = sum(v in (PASS, FAIL) for v in verdicts.values())
        blocker = None if verdict == PASS else reason
        out.append({
            "drill": did, "title": spec["title"], "verdict": verdict, "why": reason,
            "rows": verdicts,
            # THE PUBLICATION FIELDS ARCH-18 NAMES, per requirement:
            "implementation_path": list(spec["implementation"]),
            "runtime_identity": {"release": rel, "scorecard": "reports/RECOVERY_DRILLS.json"},
            "tested_behaviour": {r: (got[r] or {}).get("why") for r in spec["rows"]},
            "evidence_timestamp": stamp,
            "remaining_blocker": blocker,
            "impact": spec["impact"],
            "completed_work": measured,
        })
    counts = {k: sum(r["verdict"] == k for r in out) for k in (PASS, FAIL, UNMEASURED)}
    return {"generated_utc": now.isoformat(timespec="seconds"), "release": rel,
            "mode": "shadow: grades drills that run against doubles, sandboxes and copies; "
                    "nothing here sends an order or touches a live process",
            "drills": out, "counts": counts, "n": len(out),
            "verdict": FAIL if counts[FAIL] else PASS if counts[PASS] == len(out) else UNMEASURED,
            "valid_until": (now + timedelta(hours=3)).isoformat(timespec="seconds")}


def proof(row: dict[str, Any], doc: dict[str, Any]) -> dict[str, Any]:
    """The runtime proof global_research_acceptance verifies for one drill."""
    return {"status": row["verdict"], "drill": row["drill"], "at": doc["generated_utc"],
            "release": doc["release"], "completed_work": row["completed_work"],
            # Never claimed here: this organ runs no tests (see module docstring).
            "tests_passed": None, "why": row["why"], "rows": row["rows"]}


def _atomic(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str) + "\n", "utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = grade()
    if not a.dry_run:
        _atomic(OUT, doc)
        for r in doc["drills"]:
            _atomic(PROOFS / f"{r['drill']}.json", proof(r, doc))
    if a.json:
        print(json.dumps(doc, default=str))
    else:
        print(f"acceptance_drills: {doc['verdict']} {doc['counts']}")
        for r in doc["drills"]:
            print(f"  {r['verdict']:<10} {r['drill']:<32} {str(r['why'])[:100]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
