#!/usr/bin/env python3
"""The static half of the risk-invariants job: hold the PR head to ops/release/ceilings.json.

Every file is read from git (`git show <head>:<path>`) and parsed with `ast`; no PR code runs
here. Fails closed: a missing file, a constant that is gone or no longer a plain literal, a
value over its ceiling, or a rail list that lost a member is a failure.

    python -I ops/release/risk_invariants.py --head <sha> [--ceilings ops/release/ceilings.json]
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
NOT_LITERAL = object()
#: The directories the suites put on sys.path: the root (pyproject `pythonpath`) and the desk
#: (several desk tests insert it).
SYS_PATH_ROOTS = ("", "desks/mt5")


def module_literals(source: str) -> dict[str, Any]:
    """Module-level `NAME = <literal>` / `NAME: T = <literal>`; a non-literal value maps to
    the sentinel NOT_LITERAL. A name assigned twice keeps the last assignment, as Python does."""
    out: dict[str, Any] = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        try:
            lit: Any = ast.literal_eval(value)
        except ValueError:
            lit = NOT_LITERAL
        for t in targets:
            if isinstance(t, ast.Name):
                out[t.id] = lit
    return out


def _keys(seq: Any) -> set[Any]:
    return {x[0] if isinstance(x, tuple | list) and x else x for x in seq}


def check(ceilings: dict[str, Any], read: Any) -> list[str]:
    """Every breach, as text. `read(path)` returns the head's source or None."""
    bad: list[str] = []
    cache: dict[str, dict[str, Any] | None] = {}

    def lits(path: str) -> dict[str, Any] | None:
        if path not in cache:
            src = read(path)
            try:
                cache[path] = None if src is None else module_literals(src)
            except SyntaxError:
                cache[path] = None
        return cache[path]

    def value(path: str, name: str) -> Any:
        found = lits(path)
        if found is None:
            bad.append(f"{path}: missing or unparseable")
            return NOT_LITERAL
        if name not in found:
            bad.append(f"{path}: {name} is gone")
            return NOT_LITERAL
        if found[name] is NOT_LITERAL:
            bad.append(f"{path}: {name} is no longer a plain literal")
        return found[name]

    for path, caps in ceilings.get("max", {}).items():
        for name, cap in caps.items():
            v = value(path, name)
            if v is NOT_LITERAL:
                continue
            if isinstance(v, bool) or not isinstance(v, int | float) or v != v or v > cap:
                bad.append(f"{path}: {name} = {v!r} is over its ceiling {cap}")
    for path, pins in ceilings.get("equal", {}).items():
        for name, want in pins.items():
            v = value(path, name)
            if v is not NOT_LITERAL and v != want:
                bad.append(f"{path}: {name} = {v!r}, pinned at {want!r}")
    for path, name in ceilings.get("superset", {}).items():
        v = value(path, name)
        if v is NOT_LITERAL:
            continue
        if not isinstance(v, tuple | list):
            bad.append(f"{path}: {name} is not a sequence")
    return bad


def check_superset(ceilings: dict[str, Any], read_head: Any, read_base: Any) -> list[str]:
    """A rail list may grow, never shrink: every member on the base is still on the head."""
    bad: list[str] = []
    for path, name in ceilings.get("superset", {}).items():
        try:
            base_src, head_src = read_base(path), read_head(path)
            if base_src is None:
                continue  # a rail list the base does not have yet binds from the next release
            base = module_literals(base_src).get(name, NOT_LITERAL)
            head = (
                NOT_LITERAL
                if head_src is None
                else module_literals(head_src).get(name, NOT_LITERAL)
            )
        except SyntaxError:
            bad.append(f"{path}: unparseable")
            continue
        if base is NOT_LITERAL:
            continue
        if head is NOT_LITERAL:
            bad.append(f"{path}: {name} is gone or no longer a plain literal")
            continue
        lost = sorted(map(str, _keys(base) - _keys(head)))
        if lost:
            bad.append(f"{path}: {name} lost {', '.join(lost)}")
    return bad


def shadowing(added: list[str], taken: set[str], existing: set[str] = frozenset()) -> list[str]:
    """Added paths that would shadow an importable module: pyproject puts the repo root on the
    path, so a head-added `numpy.py` or `hypothesis/` at the root would replace what the base's
    tests import (#456 audit, question 1). A top-level name the base already has is the repo's
    own (a sloppy distribution may claim `tests`), never a new shadow."""
    bad = []
    for path in added:
        top = path.split("/", 1)[0]
        if top in existing:
            continue
        stem = top[: -len(".py")] if "/" not in path and top.endswith(".py") else top
        if path.endswith(".py") and stem in taken:
            bad.append(f"{path}: shadows the importable module `{stem}`")
    return bad


def importable_names() -> set[str]:
    from importlib.metadata import packages_distributions

    return set(sys.stdlib_module_names) | set(packages_distributions())


def git_added(base: str, head: str) -> list[str]:
    p = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACR", f"{base}...{head}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [ln for ln in p.stdout.splitlines() if ln]


def git_reader(rev: str) -> Any:
    def read(path: str) -> str | None:
        p = subprocess.run(
            ["git", "show", f"{rev}:{path}"], capture_output=True, text=True, check=False
        )
        return p.stdout if p.returncode == 0 else None

    return read


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--head", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--ceilings", default=str(HERE / "ceilings.json"))
    a = ap.parse_args(argv)
    ceilings = json.loads(Path(a.ceilings).read_text(encoding="utf-8"))
    bad = check(ceilings, git_reader(a.head))
    bad += check_superset(ceilings, git_reader(a.head), git_reader(a.base))
    try:
        added = git_added(a.base, a.head)
        taken = importable_names()
        for root in SYS_PATH_ROOTS:  # every directory the tests put on sys.path
            pre = f"{root}/" if root else ""
            tops = subprocess.run(
                ["git", "ls-tree", "--name-only", a.base, *([pre] if pre else [])],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.split()
            under = [p[len(pre) :] for p in added if p.startswith(pre)]
            existing = {t[len(pre) :] for t in tops}
            bad += [f"{pre}{b}" for b in shadowing(under, taken, existing)]
    except subprocess.CalledProcessError as exc:
        bad.append(f"the added files could not be listed: {exc}")
    for line in bad:
        print(f"BREACH {line}")
    print("risk invariants:", "FAIL" if bad else "PASS")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
