"""THE STATISTICAL PROSECUTOR, CENSUSED: which test judges whom, and which judges nobody.

    python scripts/check_prosecutor.py            # census, write the report, print
    python scripts/check_prosecutor.py --strict   # exit 1 if a test the ten gates rely on is dark

MEASURED 2026-09-08 (Tier-1 programme item V7): the desk runs TWO disjoint statistical stacks.
The MT5 ten gates charge a fixed 597-trial DSR, broadcast one PBO and one SPA p-value across a
whole matrix, and run no bootstrap, no permutation and no stepdown. `libs/validation` holds all
of those -- block and stationary bootstrap, bar permutation, Romano-Wolf stepdown, White's
reality check, CPCV, family multiplicity, gate power -- and forty-odd modules besides. Which of
them actually judges a live candidate, and which is a library nobody calls, was not written
down anywhere, so "the desk tests for X" and "X ran on this certificate" were the same sentence.

WHAT THIS COUNTS. Every module under libs/validation (and the autodiscovery validator), and for
each one: which production files import it, whether any of those files is reachable from a
scheduled clock (a VPS timer, a box task, or a leg of the hourly/daily cycle), and which stack
it belongs to. A module imported only by tests is DARK -- it exists, it is correct, and it has
never prosecuted anything.

THE VERDICT IS A CENSUS, NOT A GATE. This script adds no test to any gauntlet and moves no
threshold. It answers "who is on trial, and before which judge" -- and names the judges with an
empty courtroom, which is the finding V7 exists to keep fresh.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
OUT = DESK / "reports" / "prosecutor_census.json"

PACKAGES = ("libs.validation", "libs.autodiscovery")
#: Files under these roots are production; anything under tests/ is a caller that proves nothing
#: about what judges a live candidate.
PROD_ROOTS = ("libs", "scripts", "desks/mt5/research", "desks/mt5/scripts", "desks/mt5/mt5desk",
              "ops")
#: Which stack a caller belongs to: the ten gates, the autodiscovery stack, or neither.
TEN_GATE_FILES = ("desks/mt5/scripts/external_gauntlet.py", "desks/mt5/research/gate_policy.py",
                  "desks/mt5/research/universal_gate.py")
AUTODISCOVERY_FILES = ("libs/autodiscovery/orchestrator.py", "libs/autodiscovery/validation.py")


def _imports(path: Path) -> set[str]:
    """Modules this file imports from the prosecuted packages, by full dotted name."""
    try:
        tree = ast.parse(path.read_text("utf-8"), filename=str(path))
    except (OSError, SyntaxError, ValueError):
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for pkg in PACKAGES:
                if node.module == pkg:
                    found |= {f"{pkg}.{a.name}" for a in node.names}
                elif node.module.startswith(pkg + "."):
                    found.add(node.module)
        elif isinstance(node, ast.Import):
            for a in node.names:
                if any(a.name.startswith(p) for p in PACKAGES):
                    found.add(a.name)
    return found


def _prod_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for rel in PROD_ROOTS:
        base = root / rel
        if not base.exists():
            continue
        out += [p for p in base.rglob("*.py")
                if "__pycache__" not in p.parts and "tests" not in p.parts]
    return out


def scheduled_files(root: Path) -> set[str]:
    """Repo-relative paths a scheduled clock actually runs: timers, box tasks, cycle legs."""
    named: set[str] = set()
    for unit in (root / "ops").glob("*.service"):
        try:
            named |= set(re.findall(r"([\w./-]+\.(?:py|sh))", unit.read_text("utf-8")))
        except OSError:
            continue
    manifest = root / "desks" / "mt5" / "ops" / "box_tasks.manifest"
    if manifest.exists():
        named |= set(re.findall(r"([\w./-]+\.(?:py|ps1|cmd))", manifest.read_text("utf-8")))
    for name in ("hourly_cycle.py", "daily_cycle.py"):
        src = root / "desks" / "mt5" / "research" / name
        if src.exists():
            text = src.read_text("utf-8")
            named |= set(re.findall(r'_producer\(\s*"[^"]+",\s*"([^"]+)"', text))
            named.add(f"desks/mt5/research/{name}")
    out: set[str] = set()
    for n in named:
        n = n.lstrip("./")
        for cand in (n, f"desks/mt5/{n}", f"scripts/{n}", f"libs/{n}"):
            if (root / cand).is_file():
                out.add(cand)
    return out


def _stack(callers: list[str]) -> str:
    if any(c in TEN_GATE_FILES for c in callers):
        return "ten_gates"
    if any(c in AUTODISCOVERY_FILES for c in callers):
        return "autodiscovery"
    return "other" if callers else "none"


def census(root: Path = ROOT) -> dict[str, Any]:
    modules: dict[str, dict[str, Any]] = {}
    for pkg in PACKAGES:
        base = root / Path(pkg.replace(".", "/"))
        for p in sorted(base.glob("*.py")):
            if p.name == "__init__.py":
                continue
            modules[f"{pkg}.{p.stem}"] = {
                "module": f"{pkg}.{p.stem}", "path": p.relative_to(root).as_posix(),
                "callers": [], "scheduled_callers": [], "stack": "none"}
    sched = scheduled_files(root)
    reachable: dict[str, set[str]] = {}
    for f in _prod_files(root):
        rel = f.relative_to(root).as_posix()
        for mod in _imports(f):
            if mod in modules:
                modules[mod]["callers"].append(rel)
                reachable.setdefault(mod, set())
                if rel in sched:
                    modules[mod]["scheduled_callers"].append(rel)
    for m in modules.values():
        m["callers"] = sorted(set(m["callers"]))
        m["scheduled_callers"] = sorted(set(m["scheduled_callers"]))
        m["stack"] = _stack(m["callers"])
        m["verdict"] = ("LIT" if m["scheduled_callers"] else
                        "UNSCHEDULED" if m["callers"] else "DARK")
    by_verdict: dict[str, list[str]] = {"LIT": [], "UNSCHEDULED": [], "DARK": []}
    by_stack: dict[str, int] = {}
    for name, m in modules.items():
        by_verdict[m["verdict"]].append(name)
        by_stack[m["stack"]] = by_stack.get(m["stack"], 0) + 1
    return {
        "modules": modules, "n_modules": len(modules),
        "lit": sorted(by_verdict["LIT"]), "unscheduled": sorted(by_verdict["UNSCHEDULED"]),
        "dark": sorted(by_verdict["DARK"]), "by_stack": by_stack,
        "scheduled_files": len(sched),
        "why": ("LIT = imported by a file a clock runs; UNSCHEDULED = imported only by code "
                "nothing schedules; DARK = no production caller at all. A census, not a gate: "
                "no test is added to any gauntlet and no threshold moves"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 when a module the ten gates import is not on a clock")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    doc = census()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"prosecutor: {doc['n_modules']} modules; LIT {len(doc['lit'])}, "
          f"UNSCHEDULED {len(doc['unscheduled'])}, DARK {len(doc['dark'])}; "
          f"stacks {doc['by_stack']}")
    if doc["dark"]:
        print("  DARK (no production caller): " + ", ".join(doc["dark"][:12]))
    broken = [n for n in doc["unscheduled"]
              if doc["modules"][n]["stack"] == "ten_gates"]
    if broken:
        print("  ten-gate modules with no clock: " + ", ".join(broken))
    return 1 if (args.strict and broken) else 0


if __name__ == "__main__":
    raise SystemExit(main())
