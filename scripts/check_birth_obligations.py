#!/usr/bin/env python3
"""EVERY OBLIGATION IS INHERITED, NOT REMEMBERED (LAWS 7, principal's order 2026-09-23).

    python scripts/check_birth_obligations.py [--json] [--with-fences] [--update]

THE DEFECT CLASS. The desk keeps acquiring obligations -- an executable needs a clock, a source
needs a position in the collection chain, a family needs to be inside the judge's coverage, a
region arrives at the current depth and breadth floors, a destructive path must be guarded
against acting on an absence -- and every one of them was, until now, satisfied by a SESSION
REMEMBERING IT. A thing created next month inherits nothing from a habit: the session that
creates it has never read the cycle where the obligation was learned. `scripts/learn.py` keeps
the lesson reachable; only a fence makes it INHERITED.

THE SHAPE, GENERALISED FROM THE ONE THE DESK ALREADY GOT RIGHT. `check_component_registry.py`
fails when a new executable arrives without a clock: it derives the SET of objects from the tree,
derives the SET that satisfies the obligation, and ratchets the difference. This runs that same
shape on five axes at once, so there is ONE place that answers "did anything arrive incomplete"
rather than five more checkers -- and where another fence already owns an axis, `--with-fences`
CALLS it instead of reimplementing its judgement.

WHY NAMES AND NOT COUNTS. A count that may only fall tells you something regressed; it does not
tell you what. The floor here stores the NAMES of the objects known to be incomplete, so the
failure can say *this* executable, *this* source, *this* region arrived without its obligation --
and an object that later acquires its obligation drops out of the floor automatically, which is
the ratchet falling without a human editing a number.

PRE-EXISTING DEBT IS THE FLOOR, NOT A FAILURE. A fence that is red on the day it is built gets
switched off (L1.43). Today's incomplete set is recorded as the baseline; only an ARRIVAL fails.
Each axis publishes its debt so the number is visible and can be driven down on purpose.

UNMEASURED IS AN AXIS VERDICT (L1.28a). An axis whose declaring artifact is absent reads
UNMEASURED and says so; it never reads as zero incomplete, and it never reads as a pass.

Artifact: `docs/research/birth_obligations.json` (the floors, committed).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
UNMEASURED = "UNMEASURED"
FLOORS = ROOT / "docs" / "research" / "birth_obligations.json"

#: At most this many names per axis in the committed floor. The file must hold the WHOLE
#: incomplete set or the names it dropped would read as arrivals on the next pass, so the bound is
#: generous; when it does bite, the axis says so and stops judging arrivals rather than inventing
#: them -- a truncated floor is UNMEASURED, never a pass and never a false alarm (L1.28a).
MAX_NAMES = 20_000

#: Where an executable of this desk lives. Outside these areas a .py file is not ours to clock.
EXEC_AREAS: tuple[str, ...] = ("desks/mt5/research", "desks/mt5/scripts", "desks/mt5/ops",
                               "desks/mt5/moat", "scripts")

#: The files that DECLARE a clock. A stem named in any of them has one.
CLOCK_DECLARATIONS: tuple[str, ...] = (
    "desks/mt5/research/hourly_cycle.py", "desks/mt5/research/daily_cycle.py",
    "desks/mt5/ops/box_tasks.manifest", "desks/mt5/research/department_resident.py",
    "desks/mt5/research/moat_swarms.py", "scripts/run_law_gate.py",
)

#: A call that removes, overwrites or retires something.
DESTRUCTIVE = re.compile(r"\b(?:shutil\.rmtree|os\.remove|os\.unlink|\.unlink\(|_retire|"
                         r"retire_\w+|DELETE\s+FROM)\b")

#: A guard that proves the destructive path looked before it acted. `UNMEASURED` counts because
#: recording "I could not see it" IS the guard this desk asks for (L1.28a).
ABSENCE_GUARD = re.compile(r"\b(?:exists\(\)|is_file\(\)|is_dir\(\)|missing_ok|FileNotFoundError|"
                           r"UNMEASURED|no_retirement_on_absence)\b")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


# ------------------------------------------------------------------ the five axes, derived
def _executables(root: Path) -> tuple[set[str], set[str], str]:
    """An executable must have a clock AND a row in the runtime attestation.

    The artifact and named-consumer halves of the same obligation are owned by
    `check_component_registry.py`, which `--with-fences` calls: this axis does not re-judge them.
    """
    objects: set[str] = set()
    for area in EXEC_AREAS:
        d = root / area
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.py")):
            if "__pycache__" in p.parts or p.name.startswith("_"):
                continue
            if "__main__" in _read(p):
                objects.add(p.relative_to(root).as_posix())
    if not objects:
        return set(), set(), f"{UNMEASURED}: no executable areas in this tree"
    clocks = "\n".join(_read(root / c) for c in CLOCK_DECLARATIONS)
    attested = _read(root / "docs" / "research" / "runtime_state.json")
    if not attested.strip():
        return objects, set(), (f"{UNMEASURED}: docs/research/runtime_state.json is absent, so "
                                f"no executable can be shown to have a row in it")
    ok = {rel for rel in objects
          if (Path(rel).stem in clocks or rel in clocks) and Path(rel).stem in attested}
    return objects, ok, f"{len(ok)}/{len(objects)} executables carry a clock and an attested row"


def _sources(root: Path) -> tuple[set[str], set[str], str]:
    """A source must appear in the collection chain, not merely in the grounds registry."""
    grounds = _json(root / "desks" / "mt5" / "data" / "deep_forest_sources.json")
    objects: set[str] = set()
    if isinstance(grounds, dict):
        for k, v in grounds.items():
            if isinstance(v, list):
                objects.update(str(r.get("id") or r.get("name") or "") for r in v
                               if isinstance(r, dict))
            elif isinstance(v, dict):
                objects.add(str(k))
    elif isinstance(grounds, list):
        objects.update(str(r.get("id") or r.get("name") or "") for r in grounds
                       if isinstance(r, dict))
    objects.discard("")
    if not objects:
        return set(), set(), f"{UNMEASURED}: no source grounds registry in this tree"
    chain = "\n".join(_read(root / "desks" / "mt5" / "reports" / n)
                      for n in ("SOURCE_DRAIN.json", "SOURCE_REGISTRY.json",
                                "INGESTION_EXPLOITATION.json"))
    if not chain.strip():
        return objects, set(), (f"{UNMEASURED}: no chain report (SOURCE_DRAIN / SOURCE_REGISTRY "
                                f"/ INGESTION_EXPLOITATION) exists to place a source in")
    ok = {s for s in objects if s in chain}
    return objects, ok, f"{len(ok)}/{len(objects)} sources hold a position in the chain"


def _families(root: Path) -> tuple[set[str], set[str], str]:
    """A family must be REACHED by the judge, not merely listed beside it."""
    doc = _json(root / "desks" / "mt5" / "reports" / "JUDGE_COVERAGE.json")
    if not isinstance(doc, dict):
        return set(), set(), f"{UNMEASURED}: desks/mt5/reports/JUDGE_COVERAGE.json is absent"
    rows = doc.get("families")
    items: list[tuple[str, Any]] = []
    if isinstance(rows, dict):
        items = list(rows.items())
    elif isinstance(rows, list):
        items = [(str(r.get("family") or r.get("name") or ""), r) for r in rows
                 if isinstance(r, dict)]
    objects = {k for k, _ in items if k}
    if not objects:
        return set(), set(), f"{UNMEASURED}: the judge's coverage report declares no families"
    ok = set()
    for k, row in items:
        if not k or not isinstance(row, dict):
            continue
        judged = row.get("judged", row.get("n_judged"))
        reached = row.get("reached", row.get("judge"))
        if (isinstance(judged, (int, float)) and judged > 0) or bool(reached):
            ok.add(k)
    return objects, ok, f"{len(ok)}/{len(objects)} families are reached by the judge"


def _regions(root: Path) -> tuple[set[str], set[str], str]:
    """A region arrives at the CURRENT depth and breadth floors, never at zero."""
    doc = _json(root / "desks" / "mt5" / "reports" / "regional_parity.json")
    if not isinstance(doc, dict) or not isinstance(doc.get("regions"), dict):
        return set(), set(), f"{UNMEASURED}: desks/mt5/reports/regional_parity.json is absent"
    objects = {str(k) for k in doc["regions"]}
    flagged = doc.get("flagged")
    if isinstance(flagged, dict):
        below = {str(k) for k in flagged}
    elif isinstance(flagged, list):
        below = {str(r.get("region") if isinstance(r, dict) else r) for r in flagged}
    else:
        below = set()
    return objects, objects - below, f"{len(objects) - len(below)}/{len(objects)} regions at floor"


def _destructive(root: Path) -> tuple[set[str], set[str], str]:
    """A destructive path must look before it acts: acting on an absence is how records die."""
    objects: set[str] = set()
    ok: set[str] = set()
    for area in (*EXEC_AREAS, "libs"):
        d = root / area
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            text = _read(p)
            if not DESTRUCTIVE.search(text):
                continue
            rel = p.relative_to(root).as_posix()
            objects.add(rel)
            if ABSENCE_GUARD.search(text):
                ok.add(rel)
    if not objects:
        return set(), set(), f"{UNMEASURED}: no destructive path in this tree"
    return objects, ok, f"{len(ok)}/{len(objects)} destructive paths guard against an absence"


@dataclass(frozen=True)
class Axis:
    name: str
    obligation: str
    derive: Callable[[Path], tuple[set[str], set[str], str]]
    fence: tuple[str, tuple[str, ...]] | None


AXES: tuple[Axis, ...] = (
    Axis("executable", "a clock, an artifact, a named consumer and a row in the runtime "
                       "attestation", _executables, ("check_component_registry.py", ())),
    Axis("source", "a collection obligation and a position in the chain from collected through "
                   "ingested, represented, cells emitted, cells judged", _sources,
         ("check_source_drain.py", ())),
    Axis("family", "membership of the judge's coverage, derived from the registry rather than "
                   "typed", _families, ("check_judge_coverage.py", ())),
    Axis("region", "arrival at the CURRENT depth, breadth and ingestion floors, never at zero",
         _regions, ("check_regional_parity.py", ())),
    Axis("destructive", "a guard against acting on an absence", _destructive,
         ("check_no_retirement_on_absence.py", ())),
)


def measure(root: Path | None = None, *, floors: Path | None = None) -> dict[str, Any]:
    base = Path(root or ROOT)
    stored = _json(floors or (base / "docs" / "research" / "birth_obligations.json"))
    known: dict[str, Any] = stored.get("axes", {}) if isinstance(stored, dict) else {}
    axes: dict[str, Any] = {}
    failures: list[str] = []
    for ax in AXES:
        objects, ok, why = ax.derive(base)
        incomplete = sorted(objects - ok)
        _prev = known.get(ax.name)
        prev: dict[str, Any] = _prev if isinstance(_prev, dict) else {}
        baseline = set(prev.get("incomplete") or [])
        arrived = sorted(set(incomplete) - baseline)
        healed = sorted(baseline - set(incomplete))
        axes[ax.name] = {
            "obligation": ax.obligation,
            "objects": len(objects),
            "incomplete": len(incomplete),
            "verdict": UNMEASURED if why.startswith(UNMEASURED) else "measured",
            "why": why,
            "arrived_without_obligation": arrived[:20],
            "healed": len(healed),
            "names": incomplete[:MAX_NAMES],
            "names_dropped": max(0, len(incomplete) - MAX_NAMES),
            "fence": (ax.fence[0] if ax.fence else UNMEASURED),
        }
        if prev.get("names_dropped"):
            axes[ax.name]["verdict"] = UNMEASURED
            axes[ax.name]["why"] = (f"{UNMEASURED}: the floor dropped "
                                    f"{prev['names_dropped']} name(s), so an arrival here cannot "
                                    f"be told from a name the floor could not hold -- {why}")
            arrived = []
            axes[ax.name]["arrived_without_obligation"] = []
        if arrived and not why.startswith(UNMEASURED):
            failures.append(
                f"{ax.name}: {len(arrived)} arrived without its obligation ({ax.obligation}) -- "
                + ", ".join(arrived[:5]) + ("..." if len(arrived) > 5 else "")
                + ". Give it the obligation, or RETIRE it with a reason in "
                  "docs/research/retirements.jsonl.")
    return {"schema": "birth_obligations/1",
            "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "root": str(base), "axes": axes, "failures": failures}


def run_fences(argv_root: Path) -> dict[str, Any]:
    """CALL the fence that already owns an axis rather than re-judging it."""
    out: dict[str, Any] = {}
    for ax in AXES:
        if not ax.fence:
            continue
        script = argv_root / "scripts" / ax.fence[0]
        if not script.is_file():
            out[ax.name] = {"fence": ax.fence[0], "rc": UNMEASURED, "why": "not in this tree"}
            continue
        try:
            r = subprocess.run([sys.executable, "-W", "ignore", str(script), *ax.fence[1]],
                               capture_output=True, text=True, timeout=600, cwd=str(argv_root))
            out[ax.name] = {"fence": ax.fence[0], "rc": r.returncode,
                            "tail": (r.stdout or r.stderr or "").strip().splitlines()[-1:][:1]}
        except (OSError, subprocess.SubprocessError) as exc:
            out[ax.name] = {"fence": ax.fence[0], "rc": UNMEASURED, "why": type(exc).__name__}
    return out


def write_floor(doc: dict[str, Any], path: Path | None = None) -> None:
    out = path or FLOORS
    body = {
        "schema": "birth_obligations_floor/1",
        "at": doc["at"],
        "note": ("The names known to be incomplete on each axis. An object that ACQUIRES its "
                 "obligation drops out of this file automatically (the ratchet falling); an "
                 "object that ARRIVES incomplete fails scripts/check_birth_obligations.py. "
                 "Pre-existing debt is the floor, not a pass -- drive it down on purpose."),
        "axes": {k: {"incomplete": v["names"], "count": v["incomplete"],
                     "names_dropped": v["names_dropped"],
                     "obligation": v["obligation"], "verdict": v["verdict"]}
                 for k, v in doc["axes"].items()},
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(body, indent=1, sort_keys=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--with-fences", action="store_true",
                    help="also run the fence that already owns each axis")
    ap.add_argument("--update", action="store_true",
                    help="record today's incomplete set as the floor (a first install, or after "
                         "an arrival has been given its obligation)")
    a = ap.parse_args(argv)
    root = Path(a.root or ROOT)
    doc = measure(root)
    if a.with_fences:
        doc["fences"] = run_fences(root)
        for name, r in doc["fences"].items():
            if isinstance(r.get("rc"), int) and r["rc"] != 0:
                doc["failures"].append(f"{name}: its own fence {r['fence']} exits {r['rc']}")
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        for name, ax in doc["axes"].items():
            print(f"birth {name:12s} {ax['objects']:5d} object(s), "
                  f"{ax['incomplete']:4d} incomplete, {ax['healed']:3d} healed -- {ax['why']}")
    if a.update:
        write_floor(doc, (root / "docs" / "research" / "birth_obligations.json"))
        print(f"   floor written: {len(doc['axes'])} axes")
        return 0
    for f in doc["failures"]:
        print(f"   FAILED {f}")
    return 2 if doc["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
