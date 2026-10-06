#!/usr/bin/env python3
"""DORMANT COMPONENTS (DP2): organs with no clock, no reader and no artifact update in N days,
filed as PROPOSED retirements with their evidence. Nothing is deleted, moved or unscheduled.

    python desks/mt5/research/dormant_components.py            # measure and print, write nothing
    python desks/mt5/research/dormant_components.py --apply    # also file the proposals

WHY THIS DECIDES SOMETHING AND THE CENSUS DID NOT. The dead-architecture census (`check_dead_architecture` in scripts) already
names UNREACHED organs (no clock on any of the four scheduling planes, no detected reader), and
says in its own docstring that UNREACHED is "a list for a person to review, never a death
certificate". Nobody reviewed it: the list was recomputed and discarded. This organ takes that
list, demands two more independent facts before it will say anything, and then WRITES the
decision where the desk records dispositions -- `docs/research/retirements.jsonl` -- as a
PROPOSED row a person accepts (by moving the file to `_retired/` and adding the landed row) or
rejects (by giving the organ a clock or a reader, which withdraws the proposal on the next pass).

THREE FACTS, ALL REQUIRED, EACH FROM ITS OWN SOURCE:

    no clock       check_dead_architecture's scheduler-manifest planes (exact) AND the component
                   registry (`components` in the desk's ops package): no spec that claims the file is
                   scheduled. Two independent readers must both find no clock.
    no reader      check_dead_architecture: no production file reads any artifact it writes and
                   none imports it. That half is a heuristic that UNDER-reports readers, which is
                   why it is never sufficient on its own.
    no update      none of its artifacts changed in DORMANT_DAYS: not on disk here (mtime of
                   every file bearing the artifact's name) and not in git history (any commit in
                   the window touching a path with that name). An artifact that was never
                   written anywhere counts as not updated -- it has no date to be recent on.

PROPOSED IS NOT RETIRED. Every reader of retirements.jsonl that treats a row as a retirement
(`libs/ops/producer_census.retirements`, the batteries fence) skips `status == "PROPOSED"`, so a
proposal never removes an organ from any census. One row per path: a path already proposed or
already retired is not proposed again. Clock: the daily MT5-FrontierAudit lane
(the lane's runner in ops). Artifact: `desks/mt5/reports/DORMANT_COMPONENTS.json`.

The two organs it reads are loaded by file location and named WITHOUT path literals on purpose:
the component registry's reach walk treats a path literal as "this organ invokes that one", and a
second invoker for those two would re-attribute organs they reach to this lane.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RETIREMENTS = ROOT / "docs" / "research" / "retirements.jsonl"
REPORT = DESK / "reports" / "DORMANT_COMPONENTS.json"
DEAD_ARCH = ROOT / "scripts" / "check_dead_architecture.py"
COMPONENTS = DESK / "ops" / "components.py"

#: No artifact update for this long, on top of no clock and no reader.
DORMANT_DAYS = 14
PROPOSED = "PROPOSED"

_WALK_SKIP = frozenset({".git", "__pycache__", "node_modules", "venv", ".venv", "site-packages",
                        ".mypy_cache", ".ruff_cache", ".pytest_cache", "_retired"})


def _load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def artifact_mtimes(root: Path) -> dict[str, float]:
    """basename -> newest mtime of any file bearing it (tests excluded)."""
    out: dict[str, float] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _WALK_SKIP and d != "tests"]
        for fn in filenames:
            try:
                m = os.stat(os.path.join(dirpath, fn)).st_mtime
            except OSError:
                continue
            if m > out.get(fn, 0.0):
                out[fn] = m
    return out


def git_touched(root: Path, days: int) -> tuple[set[str] | None, str]:
    """Basenames of every path any commit in the window touched, or None when git is unreadable."""
    try:
        proc = subprocess.run(["git", "-C", str(root), "log", f"--since={days}.days",
                               "--name-only", "--format="], capture_output=True, text=True,
                              timeout=300, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"git unreadable ({type(exc).__name__}): history half UNMEASURED"
    if proc.returncode != 0:
        return None, f"git log rc={proc.returncode}: history half UNMEASURED"
    return {Path(ln.strip()).name for ln in proc.stdout.splitlines() if ln.strip()}, "git log"


def component_clock(reg: Any, path: str) -> list[str]:
    """Schedules the component registry records for this file (empty = no clock there)."""
    try:
        owners = reg.owners_of(path)
    except Exception:
        return []
    return sorted({str(s.schedule) for s in owners if getattr(s, "scheduled", False)})


def already_filed(path: Path = RETIREMENTS) -> set[str]:
    out: set[str] = set()
    try:
        text = path.read_text("utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("path"):
            out.add(str(row["path"]).replace("\\", "/"))
    return out


def judge(organs: dict[str, dict[str, Any]], *, reg: Any, mtimes: dict[str, float],
          touched: set[str] | None, now: datetime, days: int = DORMANT_DAYS
          ) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Every UNREACHED organ that also has no registry clock and no artifact update."""
    cutoff = (now - timedelta(days=days)).timestamp()
    dormant: list[dict[str, Any]] = []
    spared = {"already_retired_dir": 0, "package_init": 0, "registry_clock": 0,
              "artifact_recent_on_disk": 0, "artifact_recent_in_git": 0,
              "history_unmeasured": 0}
    for path, o in sorted(organs.items()):
        if o.get("verdict") != "UNREACHED":
            continue
        parts = Path(path).parts
        if "_retired" in parts:
            # Already retired: it sits in _retired/ with its landed row. Not a proposal.
            spared["already_retired_dir"] += 1
            continue
        if parts and parts[-1] == "__init__.py":
            # A package runs whenever anything under it is imported; the census cannot see that.
            spared["package_init"] += 1
            continue
        clocks = component_clock(reg, path)
        if clocks:
            spared["registry_clock"] += 1
            continue
        arts = list(o.get("artifacts") or [])
        newest = max((mtimes.get(a, 0.0) for a in arts), default=0.0)
        if newest >= cutoff:
            spared["artifact_recent_on_disk"] += 1
            continue
        if touched is None:
            # No history reading: never propose on half the evidence.
            spared["history_unmeasured"] += 1
            continue
        in_git = sorted(a for a in arts if a in touched)
        if in_git:
            spared["artifact_recent_in_git"] += 1
            continue
        dormant.append({
            "path": path, "artifacts": arts,
            "evidence": {
                "clock": ("none on the four scheduling planes (check_dead_architecture) and no "
                          "scheduled spec in the component registry"),
                "reader": "no production file reads its artifacts or imports it",
                "artifact_last_update": (datetime.fromtimestamp(newest, tz=UTC)
                                         .isoformat(timespec="seconds") if newest else
                                         "never written on this checkout"),
                "git_window_days": days,
                "git_touched_artifacts": [],
            }})
    return dormant, spared


def proposal_row(d: dict[str, Any], now: datetime, days: int) -> dict[str, Any]:
    return {
        "date": now.date().isoformat(), "path": d["path"], "status": PROPOSED,
        "reason": (f"DORMANT {days}d, measured {now.date().isoformat()}: no clock, no reader, "
                   f"and none of its artifacts ({', '.join(d['artifacts'][:6])}) updated in "
                   f"{days} days. PROPOSED, not retired: a person accepts by moving it to "
                   "_retired/ with a landed row, or rejects by giving it a clock or a reader"),
        "evidence": d["evidence"], "replacement": None,
        "by": "desks/mt5/research/dormant_components.py (DP2, daily MT5-FrontierAudit)",
        "at": now.isoformat(timespec="seconds"),
    }


def run(*, apply: bool = False, now: datetime | None = None, days: int = DORMANT_DAYS,
        root: Path = ROOT, retirements: Path = RETIREMENTS, report: Path = REPORT,
        census: dict[str, Any] | None = None, reg: Any = None,
        mtimes: dict[str, float] | None = None,
        touched: set[str] | None = None, read_history: bool = True) -> dict[str, Any]:
    t = now or datetime.now(UTC)
    if census is None:
        census = _load(DEAD_ARCH, "_dormant_dead_arch").census(root)
    if reg is None:
        reg = _load(COMPONENTS, "_dormant_components").registry(root)
    if mtimes is None:
        mtimes = artifact_mtimes(root)
    history_basis = "supplied" if touched is not None else "not read"
    if touched is None and read_history:
        touched, history_basis = git_touched(root, days)
    dormant, spared = judge(census.get("organs") or {}, reg=reg, mtimes=mtimes,
                            touched=touched, now=t, days=days)
    filed = already_filed(retirements)
    new = [d for d in dormant if d["path"] not in filed]
    rows = [proposal_row(d, t, days) for d in new]
    doc = {
        "at": t.isoformat(timespec="seconds"), "dormant_days": days,
        "n_unreached": len(census.get("unreached") or []),
        "n_dormant": len(dormant), "n_newly_proposed": len(rows),
        "n_already_filed": len(dormant) - len(new), "spared": spared,
        "history_basis": history_basis, "applied": bool(apply),
        "dormant": dormant,
        "rule": ("PROPOSED only when three independent facts agree: no clock (two readers), no "
                 "reader, no artifact update in the window (disk and git). Deletes, moves and "
                 "unschedules nothing; one proposal per path"),
    }
    if apply:
        if rows:
            retirements.parent.mkdir(parents=True, exist_ok=True)
            with retirements.open("a", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--days", type=int, default=DORMANT_DAYS)
    a = ap.parse_args(argv)
    doc = run(apply=a.apply, days=a.days)
    print(f"dormant components: {doc['n_dormant']} dormant of {doc['n_unreached']} unreached "
          f"({doc['n_newly_proposed']} newly PROPOSED, {doc['n_already_filed']} already filed); "
          f"spared {doc['spared']}; history={doc['history_basis']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
