"""WHICH TESTS CAN A CHANGE BREAK? The merge check for money-path PRs on the box CI.

WHY (principal 2026-11-19, via the coordinator: "test passing" waits gone; decision journal
D-20261119-BOXGIT). The box runs CI on idle cores only, so a money-path PR is checked against
the tests its change can reach, and the FULL suite runs right after each merge (coalesced) and
nightly. Nothing is promoted to production -- so nothing reaches the trading box -- without a
full-suite pass at that exact commit (box_ci.promotable).

HOW. Every test file's imports are read (AST, never executed) and resolved to files in this
repo, transitively. A test is impacted when its import closure contains a changed file, or it is
itself changed. FAIL WIDE, NEVER NARROW: a change this cannot trace -- configuration, a conftest,
a non-Python file a test may read, a deleted file, an unparseable file -- selects EVERY test. A
wrong guess here can only cost time, never let an unrun test pass for a run one.
"""
from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

ALL = "ALL"

#: A change to any of these can alter every test's behaviour.
WIDE_NAMES = ("conftest.py", "pyproject.toml", "setup.cfg", "setup.py", "pytest.ini", "tox.ini",
              "requirements.txt", "requirements-dev.txt", "uv.lock", "poetry.lock")
#: Changes that no test can observe (the fast lane's own list is the gate's; this is narrower).
INERT_SUFFIXES = (".md", ".png", ".jpg", ".jpeg", ".gif", ".svg")
TEST_ROOTS = ("tests", "desks/mt5/tests")
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", "_retired"}


def _py_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for p in root.rglob("*.py"):
        if not SKIP_DIRS.intersection(p.relative_to(root).parts):
            out.append(p)
    return out


def _module_index(root: Path, files: Iterable[Path]) -> dict[str, str]:
    """dotted name -> repo-relative path, for every importable spelling the repo uses: from the
    root (`libs.ops.x`), from desks/mt5 (`mt5desk.x`, `research.x`) and from a script's folder."""
    idx: dict[str, str] = {}
    bases = [root, root / "desks" / "mt5", root / "desks" / "mt5" / "research",
             root / "desks" / "mt5" / "scripts", root / ".github" / "scripts", root / "scripts"]
    for f in files:
        rel = f.relative_to(root).as_posix()
        for b in bases:
            try:
                parts = list(f.relative_to(b).with_suffix("").parts)
            except ValueError:
                continue
            if parts and parts[-1] == "__init__":
                parts = parts[:-1]
            if parts:
                idx.setdefault(".".join(parts), rel)
    return idx


def _imports(path: Path) -> set[str] | None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError, ValueError):
        return None
    names: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            names.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
            names.add(n.module)
            names.update(f"{n.module}.{a.name}" for a in n.names)
    return names


def graph(root: Path) -> tuple[dict[str, set[str]], list[str]]:
    """(file -> repo files it imports, unparseable files)."""
    files = _py_files(root)
    idx = _module_index(root, files)
    deps: dict[str, set[str]] = {}
    bad: list[str] = []
    for f in files:
        rel = f.relative_to(root).as_posix()
        imps = _imports(f)
        if imps is None:
            bad.append(rel)
            continue
        got: set[str] = set()
        for name in imps:
            parts = name.split(".")
            for i in range(len(parts), 0, -1):
                hit = idx.get(".".join(parts[:i]))
                if hit:
                    got.add(hit)
                    break
        deps[rel] = got - {rel}
    return deps, bad


def is_test(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    return (any(rel.startswith(t + "/") for t in TEST_ROOTS)
            and name.startswith("test_") and name.endswith(".py"))


def select(root: Path, changed: Iterable[str]) -> list[str] | str:
    """The impacted test files, sorted, or ALL. Empty when nothing a test can see changed."""
    changed = [c.replace("\\", "/") for c in changed]
    live = [c for c in changed if not c.endswith(INERT_SUFFIXES)]
    if not live:
        return []
    for c in live:
        name = c.rsplit("/", 1)[-1]
        if name in WIDE_NAMES or not c.endswith(".py") or not (root / c).exists():
            return ALL  # configuration, data a test may read, or a deletion: fail wide
    deps, bad = graph(root)
    if set(live) & set(bad):
        return ALL
    hit: set[str] = set()
    memo: dict[str, bool] = {}
    target = set(live)

    def reaches(f: str, seen: frozenset[str] = frozenset()) -> bool:
        if f in memo:
            return memo[f]
        if f in target:
            memo[f] = True
            return True
        if f in seen:
            return False
        ok = any(reaches(d, seen | {f}) for d in deps.get(f, ()))
        memo[f] = ok
        return ok

    for f in deps:
        if is_test(f) and reaches(f):
            hit.add(f)
    return sorted(hit)
