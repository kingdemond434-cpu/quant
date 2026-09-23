"""Every capability this repo defines, and whether anything actually runs it.

WHY THIS EXISTS

"Unwired or idle is a defect" is already law here (LAWS III.16), and until now nothing enforced
it. The result is a repo that keeps paying to build things it then cannot use:

  * `libs/alpha_factory/wq_operators.py` -- a complete WorldQuant operator vocabulary with its own
    test file and ZERO importers anywhere outside tests. Built, tested, never called.
  * `libs/validation/reality_check.py` -- imported by the certification sweep itself, and six
    weeks stale on the trading box because no sync list named it.
  * Six separate capabilities written and reverted by the working-tree replayer before their own
    commits landed, each one hash-verified as "deployed" while HEAD was equally empty.

Those are three different diseases with one symptom: nobody could answer "is this thing actually
in the path?" without reading the whole tree. This answers it on a clock.

THE FOUR STATES, and why the boundaries are where they are:

    ORPHANED    defines public surface, imported by NOTHING. Dead weight at best; at worst a
                capability someone believes is protecting them.
    TEST_ONLY   imported only by tests. This is the most DANGEROUS state, not the safest one:
                a green test suite proves the code works, and proves nothing about whether it
                runs. `wq_operators` sat here.
    WIRED       imported by production code, so it is at least reachable.
    ACTIVE      wired AND its importer chain reaches something on a schedule.

A capability is only worth what it changes. This reports; it does not delete, because deleting
code on an import graph's say-so would eventually delete something reached by a path this cannot
see -- a scheduled task's command line, a PowerShell script, a config string.
"""
from __future__ import annotations

import ast
import json
import subprocess
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "capability_registry.json"

#: Scanned for capabilities. Desk-local code is scanned too -- the trading box runs it.
SOURCE_ROOTS = ("libs", "desks/mt5/research", "desks/mt5/mt5desk", "desks/mt5/scripts")

#: A module with fewer public definitions than this is plumbing, not a capability, and listing
#: it would bury the real findings under __init__ shims and one-function helpers.
MIN_PUBLIC_DEFS = 2

#: Modules whose entire job is to be an entry point; nothing imports them BY DESIGN, and calling
#: them orphaned would be the check misunderstanding the codebase rather than finding a defect.
ENTRYPOINT_HINTS = ("__main__", "if __name__")


def _public_defs(path: Path) -> int:
    try:
        tree = ast.parse(path.read_text("utf-8"))
    except (OSError, SyntaxError):
        return 0
    return sum(
        1 for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and not n.name.startswith("_")
    )


def _is_entrypoint(path: Path) -> bool:
    try:
        return any(h in path.read_text("utf-8") for h in ENTRYPOINT_HINTS)
    except OSError:
        return False


def _module_names(rel: Path) -> list[str]:
    """The strings an importer could plausibly use to reach this file."""
    parts = list(rel.with_suffix("").parts)
    names = [".".join(parts), parts[-1]]
    if len(parts) >= 2:
        names.append(".".join(parts[-2:]))
    return sorted(set(names))


def _grep_importers(names: list[str]) -> set[str]:
    """Files that import this module, by any of its plausible names."""
    hits: set[str] = set()
    for name in names:
        for pattern in (f"import {name}", f"from {name} import", f"from {name}."):
            try:
                r = subprocess.run(
                    ["grep", "-rl", "--include=*.py", "--include=*.sh", "--include=*.ps1",
                     "-F", pattern, "."],
                    cwd=ROOT, capture_output=True, text=True, timeout=90, check=False)
            except (subprocess.TimeoutExpired, OSError):
                continue
            for line in (r.stdout or "").splitlines():
                f = line.strip().lstrip("./")
                if f:
                    hits.add(f)
    return hits


def main() -> int:
    now = datetime.now(tz=UTC)
    modules: list[Path] = []
    for root in SOURCE_ROOTS:
        base = ROOT / root
        if base.exists():
            modules.extend(p for p in base.rglob("*.py")
                           if "__pycache__" not in p.parts and p.name != "__init__.py")

    states: dict[str, list[str]] = defaultdict(list)
    detail: dict[str, dict] = {}

    for path in sorted(modules):
        rel = path.relative_to(ROOT)
        defs = _public_defs(path)
        if defs < MIN_PUBLIC_DEFS:
            continue
        importers = {f for f in _grep_importers(_module_names(rel)) if f != str(rel)}
        prod = {f for f in importers if not f.startswith("tests/")}
        tests = {f for f in importers if f.startswith("tests/")}

        if prod:
            state = "WIRED"
        elif tests:
            state = "TEST_ONLY"
        elif _is_entrypoint(path):
            state = "ENTRYPOINT"
        else:
            state = "ORPHANED"

        states[state].append(str(rel))
        detail[str(rel)] = {"state": state, "public_defs": defs,
                            "production_importers": sorted(prod)[:5],
                            "test_importers": sorted(tests)[:3]}

    report = {
        "checked_at": now.isoformat(timespec="seconds"),
        "counts": {k: len(v) for k, v in sorted(states.items())},
        "orphaned": sorted(states.get("ORPHANED", [])),
        "test_only": sorted(states.get("TEST_ONLY", [])),
        "detail": detail,
    }
    OUT.write_text(json.dumps(report, indent=1), "utf-8")

    print(f"CAPABILITY REGISTRY {now.isoformat(timespec='seconds')}")
    for k, v in sorted(report["counts"].items()):
        print(f"  {k:11s} {v}")
    if report["test_only"]:
        print(f"\n  TEST_ONLY ({len(report['test_only'])}) -- proven to work, never run. This is "
              f"the dangerous state: a green suite says nothing about whether it is in the path.")
        for m in report["test_only"][:10]:
            print(f"    {m}")
    if report["orphaned"]:
        print(f"\n  ORPHANED ({len(report['orphaned'])}) -- defines a public surface nothing "
              f"imports:")
        for m in report["orphaned"][:10]:
            print(f"    {m}")
    print(f"\n  -> {OUT}")
    return 1 if (report["orphaned"] or report["test_only"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
