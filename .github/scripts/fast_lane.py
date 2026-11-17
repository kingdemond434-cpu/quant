"""THE FAST LANE: A PR THAT CANNOT TOUCH LIVE MONEY MERGES ON ONE SMOKE CHECK (zuck, 2026-11-17).

zuck 17:15Z: "You write the code, you do everything ... you remove all the blockers, all the
automatic checks, everything ... It doesn't touch live money anyway." 17:18Z: "Literally strip
all checks of anything that doesn't touch live money or just do this forever."

MEASURED THE SAME HOUR (every PR run since 11-16): the jobs themselves are short (risk-invariants
3 min, replay-shadow 5, independent-review 10, trusted-eval 12, quality 40, money-path 27), but
each WAITED 40-60 min for a runner (median; up to 95), because every PR, money or not, queued
seven jobs on one shared pool. A PR that touches no money now queues one job.

A PR is FAST only when EVERY path it changes (both sides of a rename) is:
  - not a secret, not a seal carrier (those never merge at all);
  - not a check that judges the PR, the release, seal, adopt or box machinery, an agent
    instruction, a rail, a kill switch or a ROOT file (audit_gate's PROTECTED and
    FORMERLY_PROTECTED, ops/release/protected_paths.txt, ROOT_POLICY.json, NEVER_STANDING);
  - not money path as replay-shadow reads it (ops/release/replay_shadow.py: its MONEY_PATH
    folders, every script under desks/mt5/scripts and desks/mt5/ops with NO exemption, the box
    task manifest, the Fusion roster files) and not in the static import closure of the live
    entry points PLUS the promoter, which writes the LIVE rows the gateway trades;
  - not a release or risk suite (every file risk_suites.txt or trusted_eval_suites.txt names),
    and not an existing test whose base copy itself imports money-path code (a NEW test is
    fine: adding a test never weakens one that guards money).
Anything unreadable is NOT fast. Everything here is read from the checkout this runs in, which is
always the BASE (the gate's own checkout, or the base sha a CI lane job checked out), never the PR.

What still guards a fast merge: LIVE's full push run (quality, money-path suite, coverage floors)
on every merge, the seal that only ever names a green LIVE tree, the box adopting only a sealed
release, an AUDIT HOLD, and DEACTIVATE RELEASE CONTROLLER on #453 (it switches this lane off).

    python -I .github/scripts/fast_lane.py --base <sha> --head <sha> [--github-output FILE]
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import functools
import importlib.util
import json
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
#: The promoter writes the LIVE rows the gateway trades (desks/mt5/data/sleeves.json), so its
#: closure is money too, beside replay-shadow's own entry points.
EXTRA_ENTRIES = ("desks/mt5/research/promoter.py",)
#: Release and risk suites: a PR that changes one must take the full path.
SUITE_LISTS = ("ops/release/risk_suites.txt", "ops/release/trusted_eval_suites.txt")
#: The one job a fast PR needs (ci.yml).
SMOKE = "smoke"


def _load(name: str, rel: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    if spec is None or spec.loader is None:
        raise ImportError(rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _lines(rel: str) -> set[str]:
    text = (ROOT / rel).read_text("utf-8")
    return {s for ln in text.splitlines() if (s := ln.split("#", 1)[0].strip())}


def _match(name: str, pats: Iterable[str]) -> str | None:
    low = name.lower()
    return next((p for p in pats if fnmatch.fnmatchcase(low, p.lower())), None)


def is_test(path: str) -> bool:
    """A pytest file or a conftest (conftest is PROTECTED anyway)."""
    name = Path(path).name
    return name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py"))


def direct_imports(rs: ModuleType, path: str) -> set[str]:
    """The repository files this file imports ITSELF (not what those import in turn), resolved
    the way replay-shadow resolves them. Raises on a file that cannot be parsed."""
    files = rs.tree_files(ROOT)
    node = ast.parse(rs.read(ROOT, path) or "")
    pkg = Path(path).parent.as_posix().split("/")
    names: list[str] = []
    for n in ast.walk(node):
        if isinstance(n, ast.Import):
            names += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            mod = n.module or ""
            if n.level:
                up = pkg[: len(pkg) - (n.level - 1)] if n.level > 1 else pkg
                mod = ".".join(x for x in (*up, mod) if x and x != ".")
            names.append(mod)
            names += [f"{mod}.{a.name}" for a in n.names if mod]
    found = {m for name in names for m in rs._module_files(name, files)}
    # a package's __init__ on the way to a module is no import of money code by itself
    return {m for m in found if not m.endswith("/__init__.py")} - {path}


def money_test(rs: ModuleType, path: str, closure: set[str]) -> bool:
    """Does the BASE copy of this test import money-path code DIRECTLY? (A test of research code
    that only reaches the money path through some shared library is not a money test.) A test the
    base does not have yet is new: adding a test can never weaken one that guards money. An
    unreadable one is money (fail closed)."""
    if path not in rs.tree_files(ROOT):
        return False
    try:
        mine = direct_imports(rs, path)
    except Exception:
        return True
    return any(m in closure or m.startswith(rs.MONEY_PATH) for m in mine)


def classify(paths: Iterable[str]) -> tuple[bool, str]:
    """(fast, why). Fail closed: an empty list, or anything that cannot be read, is not fast."""
    names = sorted({p.strip() for p in paths if p and p.strip()})
    if not names:
        return False, "no changed paths read"
    try:
        ag = _load("_fast_ag", ".github/scripts/audit_gate.py")
        rs = _load("_fast_rs", "ops/release/replay_shadow.py")
        # one ls-tree for the whole PR, not one per file
        rs.tree_files = functools.lru_cache(maxsize=4)(rs.tree_files)  # type: ignore[attr-defined]
        extra = ag.protected_patterns()
        never = ag.never_standing_patterns()
        if extra is None or never is None:
            return False, "the protected list or the ROOT policy is unreadable"
        held = (*ag.SECRETS, *ag.SEAL_CARRIERS, *ag.PROTECTED, *ag.FORMERLY_PROTECTED, *extra,
                *never)  # fmt: skip
        suites: set[str] = set()
        for rel in SUITE_LISTS:
            suites |= _lines(rel)
        closure = rs.import_closure(ROOT, (*rs.ENTRY_POINTS, *EXTRA_ENTRIES))
        roster = {*rs.ROSTER_FILES, *rs.ROSTER_HARNESS, rs.MANIFEST}
    except Exception as exc:  # any read or import failure: the full path
        return False, f"the classifier could not read the base ({type(exc).__name__}: {exc})"
    for n in names:
        if pat := _match(n, held):
            return False, f"{n} is protected ({pat})"
        if rs.is_money(n, closure, exempt=set()) or n in roster or n in rs.ENTRY_POINTS:
            return False, f"{n} is on the money path"
        if n in suites:
            return False, f"{n} is a release or risk suite"
        if is_test(n) and money_test(rs, n, closure):
            return False, f"{n} tests the money path"
    return True, f"{len(names)} path(s), none on the money path or the release machinery"


def changed(base: str, head: str) -> list[str]:
    """Every path the PR changes since it forked from `base` (renames as delete + add, so both
    sides are named). Raises on any git error."""
    out = subprocess.run(
        ["git", "-C", str(ROOT), "diff", "--name-only", "--no-renames", "-z", f"{base}...{head}"],
        capture_output=True, check=True,
    ).stdout  # fmt: skip
    return [p for p in out.decode("utf-8", "replace").split("\0") if p]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", required=True)
    ap.add_argument("--github-output", type=Path)
    a = ap.parse_args(argv)
    try:
        fast, why = classify(changed(a.base, a.head))
    except (subprocess.CalledProcessError, OSError) as exc:
        fast, why = False, f"the diff could not be read ({exc})"
    print(json.dumps({"fast": fast, "why": why}))
    if a.github_output:
        with a.github_output.open("a", encoding="utf-8") as fh:
            fh.write(f"fast={'true' if fast else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
