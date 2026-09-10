"""What was built and is unreachable, and what to do about each one -- mechanically.

THE DESK'S DOMINANT FAILURE MODE, MEASURED 2026-09-10: 121 library modules that nothing imports,
plus 11 scripts that are the SOLE importer of a libs module and are themselves never invoked. That
second class is the nastier one -- the orphan check goes green because a caller exists, and the
caller is as unreachable as the module.

Seven instances were found by hand in a single session (account_profile written for the prop/live
split with the money path never reading it; analyst_rank's cross-section never registered as a
family; task_queue durable and event-triggered with nothing claiming from it; alpha_rl with no
consumer; release_identity's verdict written every pass and never carried to the dashboard;
stall_watch reporting failing tasks with nothing ranking them; a ledger next_step instructing a
reader to build what was already registered). Seven by hand, 132 by machine. That ratio is the
argument for this file.

WHY A FOCUSED MODULE RATHER THAN scripts/max_audit.check_unwired_modules. That check is the CI
gate and stays exactly where it is; it is one function inside an 8,000-line script that exits on
import, so nothing can consume its findings. This produces the same evidence as DATA -- typed
records with a verdict and the reason for it -- so a queue can carry it, a worker can act on it,
and a test can assert on it.

THE VERDICT IS DERIVED, NOT JUDGED, because a classifier that needed an opinion could not run
unattended:

    EXEMPT   declared, with a reason, in `_EXEMPT`. The list is the argument.
    WIRE     nothing imports it AND it has tests. Someone invested enough to prove it works and
             then nothing called it -- the exact "built, tested, unreachable" class, and the one
             where the value is already paid for and merely unclaimed.
    RETIRE   nothing imports it and NOTHING TESTS IT either. No caller and no proof; wiring it
             would place unverified code on a clock, which is worse than deleting it.

TESTS DO NOT COUNT AS WIRING, and the distinction is the whole point: a test importing a module
proves it works, not that anything uses it. Counting tests as callers would make every orphan look
connected, which is precisely the failure being detected. They are read here only to tell WIRE
from RETIRE.

A MODULE THIS FILE CANNOT SEE A CALLER FOR MAY STILL HAVE ONE. `python -m libs.x.y` in a shell or
a crontab is a real caller that no AST scan of .py files can see, so the shell surface is scanned
for `-m` targets. That can only ever ADD callers, never hide an orphan.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Directories whose .py files are searched for imports. `tests` is deliberately absent -- see the
#: header: a test is proof of correctness, never evidence of use.
_CALLER_AREAS: tuple[str, ...] = ("libs", "scripts", "desks", "api", "app", "ops", "deploy")

#: Where a `python -m libs.x.y` invocation can hide. Shell, cron and unit files are read as text.
_SHELL_AREAS: tuple[str, ...] = ("scripts", "ops", "deploy")
_SHELL_SUFFIXES: tuple[str, ...] = (".sh", ".ps1", ".service", ".timer", ".manifest", ".env", "")

_MODULE_M = re.compile(r"-m\s+(libs(?:\.[A-Za-z_][A-Za-z0-9_]*)+)")

#: A leg that runs a module BY PATH is a caller too, and neither an import nor a `-m` target.
#: `hourly_cycle` dispatches its subprocess legs as `_producer("name", "libs/ops/x.py")`, which
#: resolves the string against the repo root and runs it -- so the module is invoked hourly and
#: an AST import scan sees nothing. Found by wiring this file's own leg and watching the auditor
#: go on listing itself: the same blind spot the `-m` scan was added to close, in the other
#: spelling. Like that one, this can only ADD callers, never hide an orphan.
_MODULE_PATH = re.compile(
    r"['\"](libs/(?:[A-Za-z_][A-Za-z0-9_]*/)*[A-Za-z_][A-Za-z0-9_]*\.py)['\"]")

#: Modules that are unreachable ON PURPOSE, each with the reason. This list is the argument for
#: leaving them alone, so an entry without a reason is not an entry.
_EXEMPT: dict[str, str] = {
    "libs": "package root",
}

#: Trees whose modules can reach live capital if wired wrongly. A finding here is not treated
#: differently by the CLASSIFIER -- the evidence is the same -- but the applier gates it on the
#: full desk suite rather than the module's own tests.
_MONEY_TREES: tuple[str, ...] = ("libs.portfolio", "libs.risk", "libs.execution", "libs.ops")


@dataclass(frozen=True)
class Finding:
    """One unreachable module and the verdict derived from its own evidence."""

    module: str
    kind: str                      # no_importer | sole_importer_unreachable
    verdict: str                   # WIRE | RETIRE | EXEMPT
    why: str
    lines: int = 0
    has_tests: bool = False
    public: tuple[str, ...] = ()
    money_path: bool = False
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dict(vars(self)) | {"public": list(self.public)}


@dataclass
class Graph:
    """The import graph, kept so callers can ask questions this module does not answer."""

    modules: dict[str, Path] = field(default_factory=dict)
    importers: dict[str, set[str]] = field(default_factory=dict)
    shell_targets: set[str] = field(default_factory=set)
    tested: set[str] = field(default_factory=set)


def _dotted(root: Path, path: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    name = ".".join(rel.parts)
    return name[: -len(".__init__")] if name.endswith(".__init__") else name


def _imports_of(path: Path) -> set[str]:
    """Every `libs.*` module a file imports, absolute form only.

    RELATIVE IMPORTS ARE RESOLVED AGAINST NOTHING and are skipped deliberately: inside `libs` they
    connect siblings, and a sibling importing a sibling does not make either reachable from
    outside. Counting them would let a cluster of orphans vouch for each other.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return set()
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names if a.name.startswith("libs.")}
        elif (isinstance(node, ast.ImportFrom) and node.level == 0 and node.module
              and node.module.startswith("libs")):
            out.add(node.module)
            out |= {f"{node.module}.{a.name}" for a in node.names}
    return out


def build_graph(root: Path) -> Graph:
    """The whole picture in one pass: what exists, who imports it, what a shell runs, what tests."""
    g = Graph()
    lib_root = root / "libs"
    if lib_root.is_dir():
        for p in sorted(lib_root.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            g.modules[_dotted(root, p)] = p

    for area in _CALLER_AREAS:
        base = root / area
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.py")):
            if "__pycache__" in p.parts or "tests" in p.parts:
                continue
            self_name = _dotted(root, p) if area == "libs" else ""
            # A MODULE RUN BY PATH IS RUN. See `_MODULE_PATH`.
            try:
                for rel in _MODULE_PATH.findall(p.read_text(encoding="utf-8", errors="replace")):
                    named = rel[: -len(".py")].replace("/", ".")
                    if named != self_name:
                        g.shell_targets.add(named)
            except OSError:
                pass
            for target in _imports_of(p):
                # SELF IS EXCLUDED PER FILE, NEVER GLOBALLY. Removing the name from a shared set
                # is the bug that made an earlier walker report 241 of 244 modules as orphans:
                # each file erased the record that anything else had imported it.
                if target == self_name:
                    continue
                g.importers.setdefault(target, set()).add(self_name or str(p.relative_to(root)))

    for area in _SHELL_AREAS:
        base = root / area
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix not in _SHELL_SUFFIXES:
                continue
            try:
                g.shell_targets |= set(_MODULE_M.findall(p.read_text(encoding="utf-8",
                                                                     errors="replace")))
            except OSError:
                continue

    tests = root / "tests"
    if tests.is_dir():
        for p in sorted(tests.rglob("*.py")):
            if "__pycache__" not in p.parts:
                g.tested |= _imports_of(p)
    for p in sorted(root.glob("desks/*/tests/*.py")):
        g.tested |= _imports_of(p)
    return g


def _public(path: Path) -> tuple[str, ...]:
    """Top-level names a caller could use. What a wiring proposal has to work with."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return ()
    out = [n.name for n in tree.body
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
           and not n.name.startswith("_")]
    return tuple(sorted(out))


def findings(root: Path, graph: Graph | None = None) -> list[Finding]:
    """Every unreachable module, worst first, each carrying the evidence for its verdict."""
    g = graph or build_graph(root)
    # A PACKAGE IS REACHED THROUGH ITS CONTENTS. `libs/regime/__init__.py` is never imported by
    # name, but `from libs.regime.asset_state import ...` executes it -- so flagging it as an
    # orphan is a false positive, and one that would send a wirer to write a caller for a file
    # that already runs. Measured on this tree: libs.models, libs.regime, libs.alpha_factory,
    # libs.autodiscovery and libs.ict were all reported this way.
    reached = set(g.importers) | g.shell_targets
    packages = {n for n in g.modules if any(m.startswith(f"{n}.") for m in reached)}
    out: list[Finding] = []
    for name, path in sorted(g.modules.items()):
        if name in _EXEMPT or name in packages:
            continue
        if g.importers.get(name) or name in g.shell_targets:
            continue
        tested = name in g.tested
        try:
            lines = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            lines = 0
        verdict = "WIRE" if tested else "RETIRE"
        why = ("nothing imports it and it HAS tests: the value is already paid for and merely "
               "unclaimed" if tested else
               "nothing imports it and nothing tests it: no caller and no proof, so wiring it "
               "would put unverified code on a clock")
        out.append(Finding(module=name, kind="no_importer", verdict=verdict, why=why,
                           lines=lines, has_tests=tested, public=_public(path),
                           money_path=name.startswith(_MONEY_TREES)))
    out.extend(_one_link_short(root, g))
    order = {"WIRE": 0, "RETIRE": 1, "EXEMPT": 2}
    out.sort(key=lambda f: (order.get(f.verdict, 3), -f.lines, f.module))
    return out


def _one_link_short(root: Path, g: Graph) -> list[Finding]:
    """A module whose only importer is a script nothing ever runs.

    THE HOLE IN THE ORPHAN CHECK. A libs module counts as wired the moment ANY file imports it --
    including an entrypoint nothing invokes. So the honest fix for an orphan ("write it a caller")
    is satisfied by a file that is itself an orphan: the check goes green and the module is
    exactly as unreachable as before. A wiring fix one link short reports success, which is worse
    than no fix, because it also removes the alarm.
    """
    runnable = set(g.shell_targets)
    for area in _SHELL_AREAS:
        base = root / area
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if p.is_file() and p.suffix in _SHELL_SUFFIXES:
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                runnable |= set(re.findall(r"scripts/[A-Za-z0-9_./-]+\.py", text))
    out: list[Finding] = []
    for name, importers in sorted(g.importers.items()):
        if name not in g.modules or name in _EXEMPT:
            continue
        script_only = [i for i in importers if i.startswith("scripts/")]
        if len(importers) != len(script_only) or not script_only:
            continue
        if any(s in runnable for s in script_only):
            continue
        # SAME EVIDENCE AS AN ORPHAN, because it is one. The first draft left lines/public empty
        # here, which made every one-link-short finding render as a 0-line module -- so the
        # report sorted the largest of them last and read as though they were stubs.
        path = g.modules[name]
        try:
            lines = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            lines = 0
        out.append(Finding(
            module=name, kind="sole_importer_unreachable", verdict="WIRE",
            why=("its only importer is a script nothing invokes, so the orphan check is green "
                 "and the module is exactly as unreachable as an orphan"),
            lines=lines, has_tests=name in g.tested, public=_public(path),
            money_path=name.startswith(_MONEY_TREES),
            detail="; ".join(sorted(script_only))))
    return out


#: Where the census lands so the dashboard and the wirer can both read it. Relative to the repo
#: root, beside the desk's other reports -- `libs.ops.release` already spells a desk path this way.
REPORT_REL = "desks/mt5/reports/WIRING_AUDIT.json"


def census(root: Path) -> dict[str, Any]:
    """The counts an operator reads, and the list a queue consumes."""
    found = findings(root)
    by = {v: [f.module for f in found if f.verdict == v] for v in ("WIRE", "RETIRE", "EXEMPT")}
    return {"total": len(found),
            "wire": len(by["WIRE"]), "retire": len(by["RETIRE"]),
            "money_path": sum(1 for f in found if f.money_path),
            "one_link_short": sum(1 for f in found
                                  if f.kind == "sole_importer_unreachable"),
            "by_verdict": by,
            "findings": [f.to_dict() for f in found]}


def main(argv: list[str] | None = None) -> int:
    """Write the census and say what it found. The leg that makes this module its own first fix.

    THE AUDITOR WAS IN ITS OWN REPORT, which is the only honest way to start a wiring campaign:
    on the run that produced the first census, `libs.ops.wiring_audit` appeared under RETIRE --
    no caller, no tests. This function and the hourly leg that calls it are what took it off its
    own list, and the shape is the one every other fix on that list has to take.

    EXIT 0 WHATEVER IT FINDS. A cycle leg that fails the pass when the repo has orphans would be
    removed within a week, correctly -- the census is evidence for the wirer to act on, not a gate.
    The gate this desk already has for that is scripts/max_audit.check_unwired_modules, and it
    stays exactly where it is.
    """
    import argparse
    import json

    ap = argparse.ArgumentParser(description="census the modules nothing calls")
    ap.add_argument("--root", default=None, help="repository root (default: this file's repo)")
    ap.add_argument("--json", action="store_true", help="print the census instead of a summary")
    args = ap.parse_args(argv)

    root = Path(args.root) if args.root else Path(__file__).resolve().parents[2]
    c = census(root)
    out = root / Path(*REPORT_REL.split("/"))
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(c, indent=1), encoding="utf-8")
    except OSError as exc:
        print(f"wiring audit: could not write {REPORT_REL} ({exc.__class__.__name__})")

    if args.json:
        print(json.dumps(c, indent=1))
    else:
        print(f"wiring audit: {c['total']} unreachable -- {c['wire']} WIRE, {c['retire']} RETIRE, "
              f"{c['money_path']} in money-path trees, {c['one_link_short']} one link short")
        for f in c["findings"][:10]:
            print(f"  {f['verdict']:7s} {f['module']:46s} {f['lines']:>4}L  {f['kind']}")
    return 0


if __name__ == "__main__":       # pragma: no cover - entrypoint
    raise SystemExit(main())
