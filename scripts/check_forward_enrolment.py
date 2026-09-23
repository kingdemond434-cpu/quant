"""LAW GATE: no certificate goes a cycle without a forward clock, and no cap ever comes back.

THE ORDER THIS FENCE HOLDS (principal 2026-09-23): "make all certis always receive immediate
clocks at the same time when certified; and remove the slots being scarce by design permanently
so as many certis as possible can be put on forward clocks immediately, no quota or scarcity ever
on forward evidence slots."

Two halves, deliberately split the way `check_strategy_breadth` is split:

  --surfaces-only  THE PORTABLE HALF. AST-walks the enrolment path and fails if a CAP has been
                   re-introduced -- a quota constant, a slice of the certificate list, a
                   `len(enrolled) >= n` gate, or `forward_reconcile.family_budget` going back to
                   declaring itself an enrolment cap. It reads tracked source only, so it means
                   the same in CI, a fresh clone and on the box, and a cap arrives by an EDIT,
                   which makes the commit gate the right place to catch it.

  (no flag)        THE STATE HALF. Reads `desks/mt5/reports/FORWARD_ENROLMENT.json` and fails when
                   any certificate has been CLOCKLESS for longer than one cycle. An absent
                   artifact is UNMEASURED -- a real answer on a clean checkout, never a pass
                   dressed as one and never a failure the checkout cannot fix.

WHY A CAP IS A DEFECT AND NOT A SAFETY MEASURE, stated here because the fence must be able to say
it: a forward clock GATHERS EVIDENCE AND DEPLOYS NO CAPITAL. Enrolling every certificate raises
evidence throughput and touches risk nowhere. The multiplicity and trial accounting are untouched
by any of this -- more clocks make every clock's bar HARDER, automatically, and that price is paid
in full. This fence guards the SLOT QUOTA only; it must never be read as licence to loosen a
statistical floor, and it checks none.
"""

from __future__ import annotations

import argparse
import ast
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
REPORT = DESK / "reports" / "FORWARD_ENROLMENT.json"

#: The files a certificate travels through on its way to a clock. A cap anywhere here rations
#: forward evidence; a cap anywhere else is not this fence's business.
PATROLLED = (
    "desks/mt5/research/shadow_forward.py",
    "desks/mt5/research/forward_enrolment.py",
    "desks/mt5/research/shadow_admission.py",
    "desks/mt5/research/forward_slot_ranker.py",
    "desks/mt5/research/forward_reconcile.py",
)

#: Names whose length or slice IS the enrolment roster. Slicing one of these, or refusing once one
#: of them is long enough, is a quota however it is spelled.
ROSTER_NAMES = frozenset({"enrolled", "certificates", "certified", "runs", "authorized",
                          "authorized_runs", "certified_sleeves", "waiting"})

#: A constant whose NAME declares a cap on enrolment. Matched case-insensitively on the stem so
#: MAX_ENROLMENTS, ENROL_CAP, ENROLMENT_QUOTA and FORWARD_SLOT_QUOTA are all caught.
CAP_NAME_PARTS = ("enrol_cap", "enrolment_cap", "enrollment_cap", "max_enrol", "max_enroll",
                  "enrolment_quota", "enrollment_quota", "forward_slot_quota", "max_clocks",
                  "max_forward_clocks", "clock_quota")

#: What `forward_reconcile.family_budget` must keep saying about itself. The alpha arithmetic it
#: publishes is evidence and stays; the AUTHORITY is what was removed, and this is where the
#: removal is pinned so it cannot be flipped back by accident.
RECONCILE_REQUIRED = ('"decides": "NOTHING__ENROLMENT_IS_UNCAPPED"', '"gates_enrolment": False')

#: The ranker stays a report. Its own docstring is the pin.
RANKER_REQUIRED = ("REPLACEABLE IS A REPORT, NEVER AN ACT",)

#: One cycle. The hourly cycle is what enrols, so one hour is exactly how long enrolment may take.
CYCLE_HOURS = 1.0


def _name_of(target: ast.expr) -> str:
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return ""


def scan_source(text: str, label: str) -> list[str]:
    """Every cap-shaped construct in one module's source, by line, or an empty list.

    AST, not grep: the docstrings in these files DISCUSS caps at length -- that is the record of
    why the quota was removed -- and a text search would fail the fence on its own explanation.
    """
    findings: list[str] = []
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [f"{label}: unparseable ({exc})"]
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                name = _name_of(t).lower()
                if any(part in name for part in CAP_NAME_PARTS):
                    findings.append(
                        f"{label}:{node.lineno}: `{_name_of(t)}` declares a cap on enrolment. "
                        "No quota on forward evidence slots, ever (principal 2026-09-23): a "
                        "forward clock deploys no capital, so a cap buys no safety and costs "
                        "hypotheses the desk can never rule on.")
        if isinstance(node, ast.Subscript):
            base = _name_of(node.value).lower()
            sl = node.slice
            if base in ROSTER_NAMES and isinstance(sl, ast.Slice) and sl.upper is not None:
                findings.append(
                    f"{label}:{node.lineno}: `{_name_of(node.value)}[...]` slices the enrolment "
                    "roster. Every certificate is enrolled; a head-of-queue slice IS the quota.")
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Call):
            fn = node.left.func
            args = node.left.args
            if (_name_of(fn) == "len" and args and _name_of(args[0]).lower() in ROSTER_NAMES
                    and any(isinstance(op, (ast.Gt, ast.GtE)) for op in node.ops)):
                findings.append(
                    f"{label}:{node.lineno}: refuses once `len("
                    f"{_name_of(args[0])})` is large enough -- a count gate on enrolment is a "
                    "quota. Enrol every certificate; the statistics, not a seat count, are what "
                    "make a wide cohort honest.")
    return findings


def check_sources(root: Path | None = None) -> tuple[list[str], list[str]]:
    """(failures, notes) from the portable half: the enrolment path holds no cap."""
    base = Path(root or ROOT)
    fails: list[str] = []
    notes: list[str] = []
    for rel in PATROLLED:
        path = base / rel
        if not path.exists():
            notes.append(f"{rel}: absent from this tree -- UNMEASURED, not a pass")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        fails.extend(scan_source(text, rel))
        if rel.endswith("forward_reconcile.py"):
            for needle in RECONCILE_REQUIRED:
                if needle not in text:
                    fails.append(
                        f"{rel}: `family_budget` no longer publishes {needle}. The per-family "
                        "alpha arithmetic is EVIDENCE and stays; its authority over enrolment "
                        "was removed permanently and must not come back.")
        if rel.endswith("forward_slot_ranker.py"):
            for needle in RANKER_REQUIRED:
                if needle not in text:
                    fails.append(
                        f"{rel}: the ranker has stopped declaring itself a report ({needle!r} is "
                        "gone). It ranks and prices forward slots; it never gates enrolment.")
    return fails, notes


def check_state(report: Path | None = None, now: datetime | None = None
                ) -> tuple[list[str], list[str]]:
    """(failures, notes) from the state half: nothing certified is clockless past a cycle."""
    path = Path(report or REPORT)
    t = now or datetime.now(tz=UTC)
    if not path.exists():
        return [], [f"{path.name} absent: forward enrolment is UNMEASURED on this checkout, "
                    "which is a real answer and not a pass"]
    try:
        doc: Any = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"{path.name} unreadable ({type(exc).__name__}: {exc}): enrolment cannot be "
                "verified, and an unverifiable clock census is a defect, not a pass"], []
    if not isinstance(doc, dict):
        return [f"{path.name} is not an object"], []
    fails: list[str] = []
    notes: list[str] = []
    quota = doc.get("quota") or {}
    if quota.get("capped"):
        fails.append("FORWARD_ENROLMENT.json reports `quota.capped` true: a cap has been "
                     "re-introduced on forward evidence slots, which is forbidden permanently.")
    overdue = doc.get("overdue") or []
    for row in overdue if isinstance(overdue, list) else []:
        if not isinstance(row, dict):
            continue
        fails.append(
            f"CERTIFIED-NOT-ENROLLED {row.get('key')}: clockless for "
            f"{row.get('clockless_hours')}h, over the {CYCLE_HOURS}h cycle -- certified and "
            f"accruing no forward evidence ({row.get('why', '')})")
    n_missing = doc.get("n_missing")
    if isinstance(n_missing, int) and n_missing and not overdue:
        notes.append(f"{n_missing} certificate(s) without a clock, none yet past one cycle: the "
                     "repair sweep has this hour to enrol them")
    stamp = doc.get("at")
    try:
        age_h = (t - datetime.fromisoformat(str(stamp))).total_seconds() / 3600.0
    except Exception:
        age_h = float("nan")
    if age_h == age_h and age_h > 3 * CYCLE_HOURS:
        notes.append(f"artifact is {age_h:.1f}h old: the forward_enrolment leg has not run in "
                     f"{age_h:.1f} hours, so this verdict is about a stale census")
    lat = doc.get("latency_h") or {}
    notes.append(f"certificates={doc.get('n_certificates')} enrolled={doc.get('n_enrolled')} "
                 f"missing={doc.get('n_missing')} latency_max={lat.get('max')} "
                 f"target={lat.get('target')}")
    return fails, notes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="No enrolment cap, and no clockless certificate.")
    ap.add_argument("--surfaces-only", action="store_true",
                    help="the portable half: source only, no live artifact")
    ap.add_argument("--state-only", action="store_true",
                    help="the state half: the live census only")
    args = ap.parse_args(argv)

    fails: list[str] = []
    notes: list[str] = []
    if not args.state_only:
        f, n = check_sources()
        fails += f
        notes += n
    if not args.surfaces_only:
        f, n = check_state()
        fails += f
        notes += n

    print("forward enrolment: NO QUOTA ON FORWARD EVIDENCE SLOTS "
          f"({len(PATROLLED)} file(s) patrolled)")
    for line in notes:
        print(f"  {line}")
    for line in fails:
        print(f"  BREACH {line}")
    if fails:
        print(f"forward enrolment: {len(fails)} breach(es)")
        return 1
    print("forward enrolment: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
