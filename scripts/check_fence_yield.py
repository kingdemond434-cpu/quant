#!/usr/bin/env python3
"""FENCE YIELD (L1.43) -- a fence that has never caught anything is decoration, and this desk
just built fifteen of them in one day.

THE SELF-APPLYING QUESTION NOBODY WAS ASKING. This desk hunts welded gates: a validation gate
that accepts ~100% or rejects ~100% carries zero information, however rigorous it looks. That
exact logic was never turned on the GOVERNANCE layer -- and on 2026-07-31 the desk added roughly
fifteen laws and a dozen fences in a single session. L1.26 is blunt about what that means: tooling
and architecture are NEVER objectives, they compete for resources against every alternative use
on expected contribution to compounding. A fence nobody's behaviour changes for is brain-cycle
cost with a governance costume on.

WHAT A FENCE IS WORTH, measured rather than asserted:
  FIRED      it has produced a non-OK verdict at least once -- it caught something real. This is
             the only positive evidence a fence can generate. Every fence built on 07-31 fired on
             its FIRST run (calibration UNFORECASTING, exploration DARK, replacement UNMEASURED-
             BIRTHS, build-standard 5 violations, law-families UNREACHED). That is the bar.
  QUIET      it runs and has only ever said OK. Two readings, and the fence cannot distinguish
             them: the desk is genuinely clean in that dimension, or the check is inert. Reported,
             never auto-retired -- a quiet survival rail is exactly what you want (L1.23), so
             silence is only suspicious for DETECTORS, not for RAILS.
  NEVER-RUN  it has no artifact at all: built, possibly scheduled, and never actually executed.
             This is the built-never-wired defect inside the governance layer itself.

DELIBERATELY NOT A KILL LIST. This fence proposes no retirements and fails no build. Its output
is EVIDENCE for the weekly sweep's recursive-meta section, which is where retirement decisions
belong -- and the honest asymmetry is that a rail's silence is worth paying for while a
detector's silence may not be. Reporting is the whole job; acting on it is a judgement with
context this script does not have.

    python scripts/check_fence_yield.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

#: fence -> (artifact, the JSON key holding its verdict, values that mean "caught something",
#:           kind). kind=RAIL means silence is the DESIRED state (L1.23) and is never a demerit;
#:           kind=DETECTOR means silence is ambiguous and worth reporting.
_FENCES: dict[str, tuple[str, str, tuple[str, ...], str]] = {
    "conversion": ("data/conversion_status.json", "status", ("FLATLINE", "REPAIR-MODE"),
                   "DETECTOR"),
    "calibration": ("data/calibration_status.json", "status",
                    ("OVERDUE", "MISCALIBRATED", "BLIND", "UNFORECASTING"), "DETECTOR"),
    "replacement_rate": ("data/replacement_rate.json", "status",
                         ("DYING", "UNMEASURED-BIRTHS", "UNMEASURED"), "DETECTOR"),
    "exploration": ("data/exploration_status.json", "status", ("DARK", "STALE", "THIN"),
                    "DETECTOR"),
    "law_families": ("data/law_families.json", "status", ("FAILING",), "DETECTOR"),
    "build_standard": ("data/build_standard.json", "status", ("BELOW-STANDARD",), "DETECTOR"),
    "excitation": ("data/excitation_status.json", "status",
                   ("NO-DATA", "NO-EXCITATION", "ABSORBING", "UNIDENTIFIED"), "DETECTOR"),
    "utilisation": ("data/utilisation.json", "status", ("OVER-LIMIT", "IDLE"), "DETECTOR"),
    "clock_provenance": ("data/clock_provenance_status.json", "status",
                         ("NO-DATA", "UNMEASURED", "MIXED-CLOCK", "RECV-ONLY", "PERIOD-DRIFT"),
                         "DETECTOR"),
    "law_gate": ("data/law_gate.json", "ok", ("False", "false"), "RAIL"),
    "change_window": ("data/change_window.json", "status", ("STERILE", "UNMEASURED"), "RAIL"),
    "moat_backup": ("data/backup_status.json", "status",
                    ("DISK-FUSE", "DRILL-FAILED", "NOTHING-REPLICATED"), "RAIL"),
}

#: Append-only history of observed verdicts, so "has it EVER fired" survives a fresh artifact.
_HISTORY = "data/fence_yield_history.json"

#: SEEDED FIRINGS -- the honest fix for this fence's own blind spot. History begins at first
#: observation, so a fence that FIRED, got its defect FIXED, and then re-ran clean reads QUIET
#: forever after: the artifact only ever holds the latest verdict. That is exactly what happened
#: on 2026-07-31 -- law_families caught L2.3 fenced-but-never-in-the-doctrine, and build_standard
#: caught 5 violations including three in itself -- and both were repaired within the hour, so
#: their artifacts say OK. Recording those firings from the commit record is not cheating; NOT
#: recording them would make this fence understate the yield of the only fences whose catches are
#: already proven. Each entry cites where the evidence lives.
_SEEDED: dict[str, tuple[str, str]] = {
    "law_families": ("FAILING", "2026-07-31 first run: conversion family UNREACHED -- L2.3 was "
                                "in the constitution and in the matrix but ABSENT from the "
                                "doctrine, so no organ had ever been told it (commit b3a70eb)"),
    "build_standard": ("BELOW-STANDARD", "2026-07-31 first run: 5 violations incl. 3 in itself "
                                         "(own except:pass, own missing test, own missing matrix "
                                         "mapping) + 2 unmapped screens (commit 57a4f48)"),
    "utilisation": ("OVER-LIMIT", "2026-07-30 first run: deployed capital read 13,155/4,500 -- "
                                  "OVER 100% -- exposing two sources of truth for desk equity"),
}


def _observe(root: Path) -> dict[str, str]:
    """Today's verdict per fence -- ABSENT when the fence has produced no artifact at all."""
    out: dict[str, str] = {}
    for name, (rel, key, _fire, _kind) in _FENCES.items():
        try:
            doc = json.loads((root / rel).read_text("utf-8"))
            out[name] = str(doc.get(key, "?"))
        except (OSError, ValueError):
            out[name] = "ABSENT"
    return out


def _load_history(root: Path) -> dict[str, list[str]]:
    try:
        h = json.loads((root / _HISTORY).read_text("utf-8"))
        return {k: list(v) for k, v in h.get("seen", {}).items()}
    except (OSError, ValueError):
        return {}


def build_report(root: Path | None = None, *, record: bool = True) -> dict[str, Any]:
    root = root or _ROOT
    today = _observe(root)
    hist = _load_history(root)
    for name, (verdict, _why) in _SEEDED.items():          # proven catches predating this fence
        if verdict not in hist.setdefault(name, []):
            hist[name].append(verdict)
    for name, verdict in today.items():
        if verdict != "ABSENT" and verdict not in hist.setdefault(name, []):
            hist[name].append(verdict)

    fences: dict[str, Any] = {}
    fired = quiet = never = 0
    for name, (rel, _k, fire_values, kind) in _FENCES.items():
        seen = hist.get(name, [])
        if not seen and today[name] == "ABSENT":
            state, note = "NEVER-RUN", ("no artifact has ever existed -- built, perhaps "
                                        "scheduled, never actually executed")
            never += 1
        elif any(v in fire_values for v in seen):
            state, note = "FIRED", f"has produced {sorted(set(seen) & set(fire_values))}"
            fired += 1
        else:
            state = "QUIET"
            note = ("only ever OK. For a RAIL that is the DESIRED state and costs nothing to "
                    "keep (L1.23); for a DETECTOR it is ambiguous -- clean desk, or inert check"
                    if kind == "RAIL" else
                    "only ever OK -- either this dimension is genuinely clean or the check is "
                    "inert, and this fence cannot tell you which")
            quiet += 1
        fences[name] = {"state": state, "kind": kind, "artifact": rel,
                        "verdicts_ever_seen": sorted(set(seen)), "note": note}
        if name in _SEEDED:
            fences[name]["seeded_evidence"] = _SEEDED[name][1]

    if record:
        try:
            (root / _HISTORY).parent.mkdir(parents=True, exist_ok=True)
            (root / _HISTORY).write_text(json.dumps(
                {"seen": hist, "updated": datetime.now(tz=UTC).isoformat()}, indent=2), "utf-8")
        except OSError as exc:
            fences["_history_write"] = {"state": "UNMEASURED", "note": str(exc)}

    n = len(_FENCES)
    quiet_detectors = [k for k, v in fences.items()
                       if v.get("state") == "QUIET" and v.get("kind") == "DETECTOR"]
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.43 -- a fence that never catches anything is decoration; governance competes "
               "for resources like everything else (L1.26). Evidence only: this proposes no "
               "retirements and fails no build.",
        "status": ("NEVER-RUN-PRESENT" if never else
                   "QUIET-DETECTORS" if quiet_detectors else "ALL-EARNING"),
        "n_fences": n, "n_fired": fired, "n_quiet": quiet, "n_never_run": never,
        "quiet_detectors": quiet_detectors,
        "fences": fences,
        "detail": f"{fired}/{n} fences have caught something real; {quiet} quiet, {never} never run",
        "next_action": (
            "route QUIET DETECTORS to the weekly sweep's recursive-meta section, which owns "
            "retirement decisions. NEVER auto-retire: a quiet RAIL is what you are paying for "
            "(L1.23), and a quiet detector may simply mean the desk is clean in that dimension. "
            "A NEVER-RUN fence is the built-never-wired defect inside governance itself -- "
            "schedule it or record why it should not exist."),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / "data/fence_yield.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"fence yield (L1.43): {rep['status']} -- {rep['detail']}")
        for name, f in rep["fences"].items():
            if f.get("state") in ("QUIET", "NEVER-RUN") and f.get("kind") == "DETECTOR":
                print(f"  {f['state']:<10} {name}: {f['note']}")
    return 0                                   # evidence organ: never fails a build (L1.26)


if __name__ == "__main__":
    sys.exit(main())
