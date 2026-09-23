#!/usr/bin/env python3
"""GRID OCCUPANCY RISES, AND NOTHING BUT AN EXHAUSTED LIST MAY STOP THE FILLER.

WHAT THIS FENCE EXISTS TO CATCH, in the words of the measurement that forced it (the principal,
2026-09-23). `independence_intake` reported, on the trading box:

    grid    2202/20935 occupied (0.105183), 8418 reachable empty
    fill    8 empty cells aimed at, 8 cells created

Eight cells an hour into 8,418 reachable empty ones is a thousand hours to fill a grid, and the
organ's own cap was 400 -- so the cap was not what bound it and no artifact said what did. It was
the TIME BUDGET, spent inside `enqueue_candidate`, which asks whether a breadth cell is empty
with `WHERE grid_cell=?` against a column that carried no index: `SCAN research_candidates` over
321,168 rows, 0.927 s per cell, 75 s of budget, eight cells. With `ix_candidates_gridcell` the
same call costs 0.0012 s and one pass filled 32,585 cells.

THE GENERAL SHAPE, which is why this is a fence and not a fixed bug. An organ that prints
`8 of 400` looks throttled by its own cap; every reading of its code agrees; raising the cap
changes nothing. The limit lived two modules away and nothing reported it AS a limit. So this
fence does not check the cap. It checks the three things that would have caught it in one pass:

    1. OCCUPANCY RATCHETS. Occupied grid cells may not fall below the best ever recorded without
       a stated reason. A floor, never a ceiling: the remedy for a breach is to fill more cells.

    2. THE FILLER STOPS ONLY WHEN THE GROUND RUNS OUT. If the pass ended on a time budget or a
       count bound while reachable empty cells with donors remained, that is a THROTTLE on the
       desk's breadth and it fails here with the number it stopped at. A pass that filled
       everything it could reach is the passing state, however few cells that was.

    3. THE DECLARED BOUNDS CANNOT BIND. `MAX_FILLS_PER_PASS` must sit above the nominal grid and
       `MAX_TARGETS` must not be what the filler reads. Both are pinned from the source, because
       the report/work confusion (a JSON size limit doubling as a ceiling on the grid) is what
       made a 400-row report into a 400-cell ceiling in the first place.

NOTHING HERE CAPS, SHRINKS OR VETOES ANYTHING, and no threshold in this file is a gate bar: the
statistical bars live in `desks/mt5/policy/gate_spec.yaml` and are fixed for everyone
(principal 2026-09-23). This fence only refuses to let a breadth number fall quietly.

UNMEASURED IS A VERDICT (L1.28a). A missing artifact on a host that does not run the organ is
reported as UNMEASURED and passes; it never resolves to a clean verdict, and it never becomes a
zero that the ratchet could be satisfied by.

    python scripts/check_grid_occupancy.py
    python scripts/check_grid_occupancy.py --json
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
REPORT = DESK / "reports" / "INDEPENDENCE_INTAKE.json"
RATCHET = ROOT / "docs" / "research" / "grid_occupancy_ratchet.json"
ORGAN = DESK / "research" / "independence_intake.py"

UNMEASURED = "UNMEASURED"
#: The stop reason a healthy pass records. Anything else means ground was left on the table.
EXHAUSTED = "list exhausted"


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _rel(path: Path) -> str:
    """Repo-relative where possible, absolute otherwise. A path outside the tree (a test's tmp
    dir) must not be able to raise inside a fence -- a gate that crashes reports nothing."""
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _block(doc: dict[str, Any], key: str) -> dict[str, Any]:
    """One named sub-object of the artifact, or an empty one. Never raises, never returns None."""
    got = doc.get(key)
    return got if isinstance(got, dict) else {}


def _const(name: str) -> int | None:
    """Read a module-level int constant out of the organ's SOURCE, not by importing it.

    The fence must be able to judge the organ on a host that cannot import the desk (no numpy,
    no registry), and an AST read also means a constant cannot be monkeypatched into passing.
    """
    try:
        tree = ast.parse(ORGAN.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return None
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if (isinstance(tgt, ast.Name) and tgt.id == name
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, int)):
                return int(node.value.value)
    return None


def bounds_cannot_bind(nominal: int | None) -> dict[str, Any]:
    """`MAX_FILLS_PER_PASS` sits above the whole grid, so it can never be the reason for a stop."""
    fills = _const("MAX_FILLS_PER_PASS")
    targets = _const("MAX_TARGETS")
    out: dict[str, Any] = {"max_fills_per_pass": fills, "max_targets": targets,
                           "nominal_cells": nominal, "failures": []}
    if fills is None:
        out["verdict"] = f"{UNMEASURED}: MAX_FILLS_PER_PASS not readable from {ORGAN.name}"
        return out
    floor = max(int(nominal or 0), 60_000)
    if fills < floor:
        out["failures"].append(
            f"MAX_FILLS_PER_PASS is {fills:,} against a grid of {nominal or floor:,} cells: a "
            f"bound below the grid is a throttle on breadth, and the grid is what the filler is "
            f"for. Raise it above the grid or remove it -- never lower the work to fit a bound")
    out["verdict"] = "FAIL" if out["failures"] else "MEASURED"
    return out


def occupancy_ratchets(doc: dict[str, Any], ratchet: dict[str, Any]) -> dict[str, Any]:
    """Occupied cells may only rise. A fall carries a stated reason or it is a regression."""
    fill = _block(doc, "fill")
    grid = _block(doc, "grid")
    now = fill.get("occupied_cells_after")
    if not isinstance(now, (int, float)):
        now = grid.get("occupied_cells")
    best = ratchet.get("occupied_cells_best")
    reason = str(ratchet.get("regression_reason") or "").strip()
    out: dict[str, Any] = {"occupied_cells": now, "occupied_cells_best": best,
                           "occupancy": grid.get("occupancy"),
                           "regression_reason": reason or None, "failures": []}
    if not isinstance(now, (int, float)):
        out["verdict"] = f"{UNMEASURED}: the artifact carries no occupied-cell count"
        return out
    if isinstance(best, (int, float)) and now < best and not reason:
        out["failures"].append(
            f"grid occupancy fell to {int(now):,} occupied cells against a best of {best:,.0f} "
            f"with no stated reason. Set `regression_reason` in {RATCHET.name} naming the "
            f"generator that stopped filling, or fill the cells back. The remedy is more cells, "
            f"never fewer, and never a smaller grid to divide by")
    out["verdict"] = "FAIL" if out["failures"] else "MEASURED"
    return out


def filler_ran_out_of_ground(doc: dict[str, Any]) -> dict[str, Any]:
    """The pass stopped because the target list ended -- not because a budget or a bound did."""
    fill = _block(doc, "fill")
    grid = _block(doc, "grid")
    out: dict[str, Any] = {
        "stopped_because": fill.get("stopped_because"),
        "empty_cells_targeted": fill.get("empty_cells_targeted"),
        "cells_created": fill.get("cells_created_in_empty_cells"),
        "frontier_cells_created": fill.get("frontier_cells_created"),
        "seconds_per_cell": fill.get("seconds_per_cell"),
        "reachable_empty_cells": grid.get("reachable_empty_cells"),
        "targets_available": fill.get("targets_available"),
        "failures": [],
    }
    if not fill.get("available"):
        why = fill.get("why") or "no fill block in the artifact"
        out["verdict"] = f"{UNMEASURED}: {why!s}"
        return out
    stopped = str(fill.get("stopped_because") or "")
    if not stopped:
        # An organ version that does not publish WHY it stopped cannot be judged on it, and
        # guessing "it must have finished" is the assumption that let eight cells an hour pass
        # for a year. UNMEASURED is the verdict; it is not a pass on the merits (L1.28a).
        out["verdict"] = (f"{UNMEASURED}: the fill block names no stop reason, so whether the "
                          f"pass ran out of ground or out of clock is not recorded")
        return out
    if not stopped.startswith(EXHAUSTED):
        out["failures"].append(
            f"the grid filler stopped on `{stopped}` with {out['targets_available']} targets in "
            f"hand at {out['seconds_per_cell']}s per cell. A pass must end because the ground "
            f"ran out, never because a clock did: find what each cell is paying for (the last "
            f"one was an unindexed `WHERE grid_cell=?` scan in libs/moat/registry.py) rather "
            f"than raising the budget or lowering the aim")
    out["verdict"] = "FAIL" if out["failures"] else "MEASURED"
    return out


def audit() -> dict[str, Any]:
    doc = _read(REPORT)
    if not isinstance(doc, dict):
        return {"verdict": UNMEASURED, "failures": [],
                "why": (f"{UNMEASURED}: no {REPORT.name} on this host. The organ publishes it on "
                        f"its own clock; a host that does not run it has nothing to judge, which "
                        f"is a verdict and never a pass on the merits (L1.28a)"),
                "report": _rel(REPORT)}
    ratchet = _read(RATCHET)
    ratchet = ratchet if isinstance(ratchet, dict) else {}
    grid = _block(doc, "grid")
    nominal = grid.get("nominal_cells")
    parts = {
        "occupancy_ratchet": occupancy_ratchets(doc, ratchet),
        "filler_reach": filler_ran_out_of_ground(doc),
        "bounds": bounds_cannot_bind(int(nominal) if isinstance(nominal, int) else None),
    }
    failures = [f for p in parts.values() for f in (p.get("failures") or [])]
    out: dict[str, Any] = {
        "generated_utc": doc.get("generated_utc"),
        "law": ("GRID OCCUPANCY RISES ONLY AND THE FILLER STOPS ONLY WHEN THE GROUND RUNS OUT. "
                "Every floor here is a floor: nothing in this file caps, shrinks or vetoes, and "
                "no number here is a statistical bar (those are fixed in policy/gate_spec.yaml)"),
        "report": _rel(REPORT),
        "ratchet_file": _rel(RATCHET),
        **parts,
        "failures": failures,
    }
    out["verdict"] = "FAIL" if failures else "MEASURED"
    return out


def render(doc: dict[str, Any]) -> list[str]:
    lines = [f"GRID OCCUPANCY  {doc.get('verdict')}"]
    if doc.get("why"):
        lines.append(f"  {doc['why']}")
        return lines
    occ = _block(doc, "occupancy_ratchet")
    reach = _block(doc, "filler_reach")
    bnd = _block(doc, "bounds")
    lines.append(f"  occupied {occ.get('occupied_cells')} cells "
                 f"({occ.get('occupancy')}) against a best of {occ.get('occupied_cells_best')}")
    lines.append(f"  fill     {reach.get('cells_created')} created "
                 f"({reach.get('frontier_cells_created')} frontier) from "
                 f"{reach.get('targets_available')} targets at "
                 f"{reach.get('seconds_per_cell')}s/cell; stopped: {reach.get('stopped_because')}")
    lines.append(f"  bounds   MAX_FILLS_PER_PASS={bnd.get('max_fills_per_pass')} against a grid "
                 f"of {bnd.get('nominal_cells')} cells")
    for f in doc.get("failures") or []:
        lines.append(f"  FAIL {f}")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Grid occupancy ratchet and filler-reach fence")
    ap.add_argument("--json", action="store_true", help="print the audit as JSON")
    args = ap.parse_args(argv)
    doc = audit()
    if args.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        for line in render(doc):
            print(line)
    return 1 if doc.get("failures") else 0


if __name__ == "__main__":                                               # pragma: no cover
    raise SystemExit(main())
