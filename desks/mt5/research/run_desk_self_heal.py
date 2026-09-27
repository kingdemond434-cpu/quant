"""Run the MT5 evidence-pipeline self-heal and publish its measured result.

This is deliberately separate from :mod:`desk_self_heal`: the audit module is kept incapable of
process launch or file mutation by an AST fence.  This thin actuator may only re-run the existing
producer task named by that audit.  It cannot promote, size, arm, edit a gate, or place an order.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import desk_self_heal as heal

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
REPORT = DESK / "reports" / "DESK_SELF_HEAL.json"


def _run_task(name: str) -> bool:
    if os.name != "nt":
        return False
    try:
        proc = subprocess.run(["schtasks", "/Run", "/TN", name], capture_output=True,
                              text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def run(*, root: Path = ROOT, apply: bool = False,
        out: Path = REPORT) -> dict[str, Any]:
    findings = heal.audit(root)
    remedies, escalations = heal.plan(findings, run_task=_run_task if apply else None)
    outcomes: list[tuple[str, bool]] = []
    if apply:
        for remedy in remedies:
            outcomes.append((remedy.action, bool(remedy.apply())))
    doc = {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "status": "OK" if all(f.ok for f in findings) else "DEGRADED",
        "applied": apply,
        "findings": [{"check": f.check, "ok": f.ok, "detail": f.detail,
                      "fixable": f.fixable} for f in findings],
        "repairs": [{"action": action, "ok": ok} for action, ok in outcomes],
        "unrepaired": [{"check": f.check, "detail": f.detail} for f in escalations],
        "boundary": ("research evidence producers may be re-run; promotion, capital, gates, "
                     "deadman state and orders are outside this actuator"),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str) + "\n", "utf-8")
    os.replace(tmp, out)
    return doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, default=REPORT)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    doc = run(root=args.root, apply=args.apply, out=args.out)
    print(f"desk self-heal: {doc['status']}; repairs={len(doc['repairs'])}; "
          f"unrepaired={len(doc['unrepaired'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
