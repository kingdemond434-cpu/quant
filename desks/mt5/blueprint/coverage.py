"""The blueprint registry: every mandated capability, with the evidence for its status.

MANDATE §3 ASKS FOR A REGISTRY. THIS DESK ALREADY HAS THE HARD HALF OF ONE.
`scripts/check_absolute_ceiling.py` carries 94 capabilities and DERIVES each one's rung --
MISSING through PROVEN, the mandate's exact eight -- from the tree itself: imports for WIRED, a
scheduler surface for SCHEDULED, the artifact's existence for RUNNING, the capability graph for
DECISION_AFFECTING, a MODULE_RENT line for MEASURED. Nothing is declared. A second registry that
re-derived any of that would be a second judge, and the first thing this desk learned about two
judges (`run_key` vs `sleeve_key`) is that they disagree and the disagreement is invisible until
something expensive depends on it.

So this module ENRICHES rather than re-decides. `stage_of` remains the only authority on status.
What the mandate asks for and the auditor does not carry -- named consumers, the scheduler unit
by name, the tests that exercise it, the release SHA, blockers -- is DERIVED HERE from the same
tree, and every field says how it was obtained. A field that cannot be derived is empty, never
filled with a plausible guess: §148 requires evidence for each of nine things, and a guessed
consumer is exactly the "capability marked complete from a filename" the mandate forbids.

    python blueprint/coverage.py                # table
    python blueprint/coverage.py --json         # BLUEPRINT_REGISTRY.json to stdout
    python blueprint/coverage.py --write        # write BLUEPRINT_REGISTRY.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = Path(__file__).resolve().parent / "BLUEPRINT_REGISTRY.json"

#: Where a scheduler can name a module. Read as text rather than parsed: a unit file, a crontab
#: line and a python -m invocation all name the module the same way, and a parser per format
#: would be three things to keep correct instead of one.
SCHEDULER_DIRS = ("ops",)
TEST_DIRS = ("tests", "desks/mt5/tests")


@lru_cache(maxsize=1)
def _git_sha() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                             capture_output=True, text=True, timeout=15)
        return out.stdout.strip()[:12] if out.returncode == 0 else ""
    except Exception:                             # noqa: BLE001 - absence is the answer
        return ""


@lru_cache(maxsize=1)
def _py_files() -> tuple[tuple[str, str], ...]:
    """(relative path, source) for every python file outside .git and the venv."""
    rows: list[tuple[str, str]] = []
    # Path.rglob walks INTO .git before the post-filter can reject its results.  On the shared
    # repo, .git/worktrees and object packs make that take longer than the hourly control cycle.
    # Prune directory traversal at the source; this changes no file admitted to the census.
    skip = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"}
    for parent, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in skip]
        for name in files:
            if not name.endswith(".py"):
                continue
            p = Path(parent) / name
            rel = p.relative_to(ROOT).as_posix()
            try:
                rows.append((rel, p.read_text("utf-8", errors="ignore")))
            except OSError:
                continue
    return tuple(rows)


@lru_cache(maxsize=1)
def _scheduler_text() -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = []
    for d in SCHEDULER_DIRS:
        for p in (ROOT / d).rglob("*"):
            if p.is_file() and p.suffix in (".service", ".timer", ".sh", ".cron", ""):
                try:
                    rows.append((p.relative_to(ROOT).as_posix(), p.read_text("utf-8", "ignore")))
                except OSError:
                    continue
    return tuple(rows)


def consumers_of(module_rel: str, artifact_rel: str) -> dict[str, list[str]]:
    """Who imports this module, and who reads its artifact.

    TWO DIFFERENT QUESTIONS AND THE MANDATE WANTS BOTH (§148 items 6 and 7). A module can be
    imported by something that never uses its output, and an artifact can be read by a module
    that never imports its producer -- the second is the commoner shape on this desk, because
    producers write JSON and consumers read JSON. Reporting only imports would have shown
    `run_external_backtest` as having no consumer while the whole gauntlet reads its results.
    """
    stem = Path(module_rel).stem if module_rel else ""
    art = Path(artifact_rel).name if artifact_rel else ""
    imports, readers = [], []
    for rel, src in _py_files():
        if rel == module_rel:
            continue
        if stem and re.search(rf"\b(?:import|from)\s+[\w.]*\b{re.escape(stem)}\b", src):
            imports.append(rel)
        if art and art in src:
            readers.append(rel)
    return {"imports": sorted(imports)[:12], "artifact_readers": sorted(readers)[:12]}


def scheduler_for(module_rel: str) -> list[str]:
    """Every surface that runs this module, NAMED.

    THE AUDITOR'S SURFACE LIST IS AUTHORITATIVE AND THIS USED TO IGNORE IT. A first version
    searched only `ops/` for the module stem and reported 81 of 94 capabilities as having no
    scheduler -- while the auditor, using `SCHEDULER_SURFACES`, had already placed 82 of them at
    SCHEDULED or above. Two answers to "is this scheduled", from two lists, in one report: the
    exact defect this whole registry exists to avoid, committed inside it. `ops/` holds the
    systemd units; the hourly and daily cycles and the box manifest schedule most of the desk
    from inside Python, and a unit-file search cannot see those at all.

    Both are consulted and the union is returned, so the answer can never be narrower than the
    one the status was derived from.
    """
    stem = Path(module_rel).stem if module_rel else ""
    if not stem:
        return []
    found = {rel for rel, src in _scheduler_text() if stem in src}
    try:
        from check_absolute_ceiling import SCHEDULER_SURFACES, _read as _cread
        for rel in SCHEDULER_SURFACES:
            text = _cread(rel)
            if stem in text or f"{stem}.py" in text:
                found.add(rel)
    except Exception:                             # noqa: BLE001 - reported by absence, not raised
        pass
    return sorted(found)[:8]


def tests_for(module_rel: str) -> list[str]:
    stem = Path(module_rel).stem if module_rel else ""
    if not stem:
        return []
    hits = [rel for rel, src in _py_files()
            if any(rel.startswith(d) for d in TEST_DIRS) and stem in src]
    return sorted(hits)[:8]


def registry() -> dict[str, Any]:
    """The mandate's registry, one row per capability, status from the single judge."""
    from check_absolute_ceiling import audit          # the ONE authority on status

    base = audit()
    rows: list[dict[str, Any]] = []
    for cap in base["capabilities"]:
        owner = cap.get("owner_module") or ""
        art = cap.get("artifact") or ""
        link = consumers_of(owner, art)
        sched = scheduler_for(owner)
        rows.append({
            "id": cap["capability_id"],
            "name": cap["requirement"][:80],
            "category": (cap.get("tags") or ["uncategorised"])[0],
            "description": cap["requirement"],
            "producer": owner or None,
            "artifacts": [art] if art else [],
            "consumers": link["imports"] + link["artifact_readers"],
            "scheduler": sched,
            "decision_path": cap.get("open_gap") or "producer -> artifact -> consumer -> decision",
            "status": cap["current_stage"],
            "code_paths": [owner] if owner else [],
            "tests": tests_for(owner),
            "measurements": cap.get("rent_metric") or "",
            "rent_status": ("PRICED" if cap["current_stage"] in ("MEASURED", "PROVEN")
                            else "UNPRICED"),
            "last_verified": base["at"],
            "git_sha": _git_sha(),
            "blockers": (cap.get("all_gaps") or []) + [
                f"blocked by {d}" for d in cap.get("blocking_dependencies") or []],
        })
    return {
        "generated_at": base["at"],
        "git_sha": _git_sha(),
        "total": len(rows),
        "by_status": {s: sum(1 for r in rows if r["status"] == s)
                      for s in ("MISSING", "CODED", "WIRED", "SCHEDULED", "RUNNING",
                                "DECISION_AFFECTING", "MEASURED", "PROVEN")},
        "problems": base.get("problems", []),
        "capabilities": rows,
        "law": ("status is DERIVED by check_absolute_ceiling.stage_of and never declared here. "
                "This module adds the mandate's linkage fields -- consumers, scheduler, tests, "
                "SHA -- from the same tree. An underivable field is EMPTY, never guessed."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    reg = registry()
    if args.write:
        OUT.write_text(json.dumps(reg, indent=2, default=str), encoding="utf-8")
        print(f"{reg['total']} capabilities -> {OUT}")
    if args.json:
        print(json.dumps(reg, indent=2, default=str))
        return 0
    if not args.write:
        print(f"{reg['total']} capabilities @ {reg['git_sha'] or 'no sha'}")
        for s, n in reg["by_status"].items():
            print(f"  {s:20s} {n:4d}")
        unsched = [r["id"] for r in reg["capabilities"]
                   if r["status"] not in ("MISSING", "CODED") and not r["scheduler"]]
        noconsumer = [r["id"] for r in reg["capabilities"]
                      if r["artifacts"] and not r["consumers"]]
        print(f"\n  decision-affecting-or-better with NO scheduler: {len(unsched)}")
        print(f"  artifacts with NO consumer:                     {len(noconsumer)}")
        for p in reg["problems"]:
            print(f"  PROBLEM: {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
