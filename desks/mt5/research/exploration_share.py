"""THE MEASURED EXPLORATION SHARE: what fraction of the judge's docket this hour was NOT yield-chosen.

WHY THIS EXISTS (N9 item 5, unknown-unknown engine; classification 2026-11-10)

The desk declares an exploration budget in seven places, and the seven disagree:

    engine_registry.EXPLORATION_SHARE        0.25   trials split across engines
    trial_allocator.EXPLORE_SHARE            0.30   budget per cell type
    negative_knowledge.EXPLORE_FLOOR         0.20   re-opening the graveyard
    search_controller.EXPLORE_FLOOR          0.35   the search controller's arms
    organ_census.EXPLORATION_FLOOR           0.25   organs that must stay exploratory
    frontier_intel/unknowns.EXPLORATION_FRACTION 0.10  the unknowns frontier
    source_roi.EXPLORATION_FLOOR             0.05   source selection

None of them is the JUDGE. What reaches a verdict is decided inside the sealed sweep
(`external_gauntlet.allocate_by_yield`): a family split blended between survivor yield and a
uniform share, then two floors APPENDED after the trim that take from nobody -- the unmeasured-
axis floor and the orthogonality floor. The sweep publishes all of it, every pass, to
`reports/RESEARCH_ALLOCATION.json`, and nothing on the desk ever turned it into one number. So a
claim that "a quarter of the budget explores" could not be checked, and exploration could decay
to zero while seven constants still read 0.25.

WHAT IT MEASURES, from that file alone (nothing here re-derives the judge's arithmetic):

  appended_share   cells the two floors appended against yield (unmeasured axes + orthogonal
                   families) over cells built. This is the strict number: cells the yield split
                   would never have built.
  uniform_share    the part of each family's share that came from the uniform blend
                   (1 - strength) / n_families rather than from its yield, in cells, over built.
  exploration_share  the two together: everything in the hour's docket not chosen by yield.

and sets it beside every declared constant. Verdicts: UNMEASURED (no allocation file, unreadable,
or older than MAX_AGE_H -- absence is never a clean reading, L1.28a), BELOW_EVERY_DECLARED_FLOOR,
BELOW_SOME_DECLARED_FLOORS, AT_OR_ABOVE_EVERY_DECLARED_FLOOR.

NEVER A THROTTLE. This organ only reports. No verdict here recommends exploring less; a reading
above every declared floor is a fact, not a licence to cut (L1.8, L1.25a). A reading below them is
the measured gap the declared constants were hiding.

Each pass appends one row to `data/exploration_share_history.jsonl`, so a decay shows as a series.

    python desks/mt5/research/exploration_share.py [--dry-run]
"""
from __future__ import annotations

import argparse
import ast
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent

ALLOCATION = BASE / "reports" / "RESEARCH_ALLOCATION.json"
REPORT = BASE / "reports" / "EXPLORATION_SHARE.json"
HISTORY = BASE / "data" / "exploration_share_history.jsonl"

#: The sweep runs hourly; three hours without a fresh allocation means the reading is not about
#: this hour's docket.
MAX_AGE_H = 3.0
MAX_HISTORY = 5_000

#: (name, file under the repo root, constant). Read by parsing the source, never by import: these
#: modules pull heavy dependencies and the reading must cost nothing. Capital-side exploration
#: (`pf_allocator.EXPLORE_SHARE`) is deliberately absent -- it sizes money, not research.
DECLARED: tuple[tuple[str, str, str], ...] = (
    ("engine_registry", "desks/mt5/research/engine_registry.py", "EXPLORATION_SHARE"),
    ("trial_allocator", "desks/mt5/research/trial_allocator.py", "EXPLORE_SHARE"),
    ("negative_knowledge", "desks/mt5/research/negative_knowledge.py", "EXPLORE_FLOOR"),
    ("search_controller", "libs/research/search_controller.py", "EXPLORE_FLOOR"),
    ("organ_census", "libs/ops/organ_census.py", "EXPLORATION_FLOOR"),
    ("frontier_unknowns", "desks/mt5/frontier_intel/unknowns.py", "EXPLORATION_FRACTION"),
    ("source_roi", "libs/research/source_roi.py", "EXPLORATION_FLOOR"),
)


def declared_constant(path: Path, name: str) -> float | None:
    """The literal module-level value of `name` in `path`, or None when it is not a literal."""
    try:
        tree = ast.parse(path.read_text("utf-8"))
    except (OSError, SyntaxError, ValueError):
        return None
    for node in tree.body:
        targets: list[Any] = []
        value = None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        if any(isinstance(t, ast.Name) and t.id == name for t in targets):
            try:
                lit = ast.literal_eval(value) if value is not None else None
            except ValueError:
                return None
            return float(lit) if isinstance(lit, int | float) else None
    return None


def declared(root: Path = ROOT) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for label, rel, name in DECLARED:
        val = declared_constant(root / rel, name)
        out[label] = {"constant": f"{rel}:{name}", "value": val,
                      "state": "READ" if val is not None else "UNREADABLE"}
    return out


def _age_h(stamp: Any, now: datetime) -> float | None:
    try:
        at = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return (now - at).total_seconds() / 3600.0


def measure(alloc: dict[str, Any]) -> dict[str, Any]:
    """The hour's exploration share, read off one published allocation."""
    built = int(alloc.get("built_this_sweep") or 0)
    exp = alloc.get("exploration") if isinstance(alloc.get("exploration"), dict) else {}
    axes_added = int(exp.get("n_cells_added") or 0)
    ortho = exp.get("orthogonality_floor") if isinstance(exp.get("orthogonality_floor"),
                                                          dict) else {}
    ortho_added = int(ortho.get("added_by_floor") or 0)
    strength = float(alloc.get("strength") or 0.0)
    fams = alloc.get("by_family") if isinstance(alloc.get("by_family"), dict) else {}
    n_fam = len(fams)
    uniform_cells = 0.0
    if n_fam and 0.0 <= strength < 1.0:
        uni = (1.0 - strength) / n_fam
        for row in fams.values():
            if not isinstance(row, dict):
                continue
            share = float(row.get("share_of_budget") or 0.0)
            took = float(row.get("built_this_sweep") or 0)
            # A family held by its own floor or capped by the ceiling built a count its share did
            # not set; only the uniform part of a share that actually set the count is counted.
            if share <= 0 or row.get("held_by_floor") or row.get("capped_by_ceiling"):
                continue
            uniform_cells += took * min(1.0, uni / share)
    appended = axes_added + ortho_added
    den = max(built, 1)
    return {
        "built_this_sweep": built, "docket_total": int(alloc.get("docket_total") or 0),
        "appended_unmeasured_axes": axes_added, "appended_orthogonal": ortho_added,
        "uniform_blend_cells": round(uniform_cells, 1), "strength": strength,
        "n_families": n_fam,
        "appended_share": round(appended / den, 4) if built else None,
        "uniform_share": round(uniform_cells / den, 4) if built else None,
        "exploration_share": round((appended + uniform_cells) / den, 4) if built else None,
    }


def verdict(share: float | None, floors: dict[str, dict[str, Any]]) -> tuple[str, list[str]]:
    vals = {k: v["value"] for k, v in floors.items() if v["value"] is not None}
    if share is None or not vals:
        return "UNMEASURED", []
    below = sorted(k for k, v in vals.items() if share < v)
    if len(below) == len(vals):
        return "BELOW_EVERY_DECLARED_FLOOR", below
    if below:
        return "BELOW_SOME_DECLARED_FLOORS", below
    return "AT_OR_ABOVE_EVERY_DECLARED_FLOOR", below


def build(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    floors = declared()
    report: dict[str, Any] = {
        "at": now.isoformat(timespec="seconds"),
        "source": "reports/RESEARCH_ALLOCATION.json (written by the sealed sweep every pass)",
        "declared": floors,
        "rule": "report only; no verdict here ever recommends exploring less (L1.8, L1.25a)",
    }
    try:
        alloc = json.loads(ALLOCATION.read_text("utf-8"))
    except FileNotFoundError:
        report.update(state="ABSENT", verdict="UNMEASURED", below=[], measured=None,
                      exploration_share=None)
        return report
    except (OSError, ValueError):
        report.update(state="UNREADABLE", verdict="UNMEASURED", below=[], measured=None,
                      exploration_share=None)
        return report
    if not isinstance(alloc, dict):
        report.update(state="UNREADABLE", verdict="UNMEASURED", below=[], measured=None,
                      exploration_share=None)
        return report
    age = _age_h(alloc.get("generated_utc"), now)
    m = measure(alloc)
    report["measured"] = m
    # The headline is None unless the reading is about this hour; `measured` keeps the old one.
    report["exploration_share"] = None
    report["allocation_generated_utc"] = alloc.get("generated_utc")
    report["allocation_age_h"] = None if age is None else round(age, 2)
    if age is None or age > MAX_AGE_H or age < -0.1:
        report.update(state="STALE" if age is not None and age > MAX_AGE_H else "UNSTAMPED",
                      verdict="UNMEASURED", below=[])
        return report
    v, below = verdict(m["exploration_share"], floors)
    report.update(state="READ", verdict=v, below=below,
                  exploration_share=m["exploration_share"])
    return report


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write(report: dict[str, Any]) -> Path:
    _atomic_write(REPORT, json.dumps(report, indent=1, default=str))
    m = report.get("measured") or {}
    row = {"at": report["at"], "verdict": report["verdict"], "state": report.get("state"),
           "allocation_generated_utc": report.get("allocation_generated_utc"),
           "exploration_share": m.get("exploration_share"),
           "appended_share": m.get("appended_share"), "built": m.get("built_this_sweep")}
    lines: list[str] = []
    try:
        lines = HISTORY.read_text("utf-8").splitlines()
    except OSError:
        pass
    lines.append(json.dumps(row))
    _atomic_write(HISTORY, "\n".join(lines[-MAX_HISTORY:]) + "\n")
    return REPORT


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the measured exploration share of the judge's docket")
    ap.add_argument("--dry-run", action="store_true", help="print the summary, write nothing")
    args = ap.parse_args(argv)
    rep = build()
    m = rep.get("measured") or {}
    target = "DRY RUN (nothing written)" if args.dry_run else str(write(rep))
    print(f"EXPLORATION SHARE {rep['at']}  {rep['verdict']} ({rep.get('state')})  "
          f"share {m.get('exploration_share')}  appended {m.get('appended_share')}  "
          f"built {m.get('built_this_sweep')}  below {rep.get('below')} -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
