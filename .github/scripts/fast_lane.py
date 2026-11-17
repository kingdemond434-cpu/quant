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
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
#: The promoter writes the LIVE rows the gateway trades (desks/mt5/data/sleeves.json), so its
#: closure is money too, beside replay-shadow's own entry points.
EXTRA_ENTRIES = ("desks/mt5/research/promoter.py",)
#: The directories the money code puts on sys.path and imports bare names from (#1240 audit MF1:
#: prop/ftmo_executor and e8_executor run `from admission_integrity import ...` through research/).
SYS_PATH_DIRS = ("desks/mt5/research", "desks/mt5/prop", "desks/mt5/mt5desk", "desks/mt5/scripts")
#: Box machinery wherever it sits (#1240 audit MF2): anything under ops/, every shell script, and
#: the box's install sets.
BOX_PREFIXES = ("ops/",)
BOX_EXTS = (".ps1", ".psm1", ".cmd", ".bat", ".sh")
BOX_NAMES = ("requirements*.txt", "*/requirements*.txt")
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


def money_closure(rs: ModuleType) -> set[str]:
    """Every file the money path can import (#1240 audit MF1): seeded with the live entry points,
    the promoter AND every .py under the MONEY_PATH folders (an executor that is no entry point is
    still money), with bare names resolved against SYS_PATH_DIRS as well as replay-shadow's own
    roots. `rs` is this module's private copy, so widening its roots changes no other reader."""
    roots = tuple(getattr(rs, "IMPORT_ROOTS"))  # noqa: B009 (a module loaded by path)
    setattr(rs, "IMPORT_ROOTS", (*roots, *(d for d in SYS_PATH_DIRS if d not in roots)))  # noqa: B010
    files = sorted(rs.tree_files(ROOT))
    seeds = [f for f in files if f.endswith(".py") and f.startswith(rs.MONEY_PATH)]
    return set(rs.import_closure(ROOT, (*rs.ENTRY_POINTS, *EXTRA_ENTRIES, *seeds)))


def is_box(path: str) -> bool:
    """Box machinery (#1240 audit MF2)."""
    low = path.lower()
    named = _match(path, BOX_NAMES) is not None
    return low.startswith(BOX_PREFIXES) or low.endswith(BOX_EXTS) or named


#: Calls that write a file (by attribute or function name), for `written_names`.
WRITE_CALLS = frozenset({"write_text", "write_bytes", "dump", "to_json", "to_csv", "to_parquet",
                         "replace", "rename", "writelines", "write"})  # fmt: skip


def _writes(call: ast.Call) -> bool:
    f = call.func
    name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
    low = name.lower()
    if name in WRITE_CALLS or ("write" in low and low != "writer") or low.startswith("atomic"):
        return True
    if name == "open":
        modes = [*call.args[1:2], *(k.value for k in call.keywords if k.arg == "mode")]
        return any(
            isinstance(m, ast.Constant) and isinstance(m.value, str) and set(m.value) & set("wax")
            for m in modes
        )
    return False


def written_names(text: str, path: str) -> set[str]:
    """The file names (base names, lower-cased) a Python file spells inside a scope that writes a
    file -- a function, or a module-level statement -- directly or through a module-level
    constant. A superset of what it writes; none for a non-Python file. Raises on a parse error."""
    if not path.endswith(".py"):
        return set()
    tree = ast.parse(text)
    consts: dict[str, set[str]] = {}
    for st in tree.body:
        if isinstance(st, (ast.Assign, ast.AnnAssign)) and st.value is not None:
            lits = {c.value for c in ast.walk(st.value)
                    if isinstance(c, ast.Constant) and isinstance(c.value, str)}  # fmt: skip
            targets = st.targets if isinstance(st, ast.Assign) else [st.target]
            consts.update({t.id: lits for t in targets if isinstance(t, ast.Name)})
    scopes: list[ast.AST] = [n for n in ast.walk(tree)
                             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]  # fmt: skip
    defs = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    scopes += [st for st in tree.body if not isinstance(st, defs)]
    out: set[str] = set()
    for sc in scopes:
        if not any(isinstance(c, ast.Call) and _writes(c) for c in ast.walk(sc)):
            continue
        for c in ast.walk(sc):
            if isinstance(c, ast.Constant) and isinstance(c.value, str):
                out.add(c.value)
            elif isinstance(c, ast.Name):
                out |= consts.get(c.id, set())
    return {x.lower().replace("\\", "/").rsplit("/", 1)[-1] for x in out if 0 < len(x) < 300}


def money_writes(text: str, path: str, state: set[str]) -> set[str]:
    """The files the money path reads that this file spells where it writes (#1240 audit MF3)."""
    return {b for b in written_names(text, path)
            if "." in b and (b in state or b.rsplit(".", 1)[0] in state)}  # fmt: skip


def producers(state: set[str], closure: set[str], money_path: tuple[str, ...]) -> dict[str, str]:
    """{code path: why} for every component of the desk's registry (desks/mt5/ops/components.py,
    the base's, run in its own isolated interpreter) that DECLARES an output the money path reads
    or a consumer on the money path (#1240 audit MF3). Raises when the registry cannot be built:
    the caller fails closed."""
    code = (
        "import importlib.util, json, sys\n"
        "sys.path.insert(0, '.')\n"
        "s = importlib.util.spec_from_file_location('_c', 'desks/mt5/ops/components.py')\n"
        "m = importlib.util.module_from_spec(s); s.loader.exec_module(m)\n"
        "print(json.dumps([[list(c.code_paths), list(c.outputs), list(c.consumers)]\n"
        "                  for c in m.build_registry()]))\n"
    )
    out = subprocess.run([sys.executable, "-I", "-c", code], cwd=ROOT, capture_output=True,
                         text=True, check=True, timeout=300).stdout  # fmt: skip
    found: dict[str, str] = {}
    for paths, outputs, consumers in json.loads(out.strip().splitlines()[-1]):
        names = [o.split()[0].rsplit("/", 1)[-1].lower() for o in outputs if o.strip()]
        fed = [b for b in names if b in state or b.rsplit(".", 1)[0] in state]
        reads = [c for c in consumers if c in closure or str(c).startswith(money_path)]
        if fed or reads:
            why = f"writes {fed[0]}" if fed else f"feeds {reads[0]}"
            for p in paths:
                found.setdefault(p, why)
    return found


def head_text(head: str | None, path: str) -> str | None:
    """The PR head's copy of `path`, or None when there is no head or it lacks the file."""
    if head is None:
        return None
    p = subprocess.run(["git", "-C", str(ROOT), "show", f"{head}:{path}"], capture_output=True,
                       check=False)  # fmt: skip
    return p.stdout.decode("utf-8", "replace") if p.returncode == 0 else None


def _tree_id() -> str:
    """The checkout's HEAD commit, the cache key below (a moved base is read afresh). Raises."""
    return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
                          check=True, text=True).stdout.strip()  # fmt: skip


@functools.lru_cache(maxsize=2)
def base_facts(root: str, tree: str) -> Any:
    """Everything classify reads from the base, once per base commit (the closure walk costs
    ~10 s): (replay_shadow copy, held patterns, suites, money closure, money state names, roster
    files, registry producers), or a string saying why it cannot be read. `root` and `tree` are
    only the cache key."""
    del root, tree
    ag = _load("_fast_ag", ".github/scripts/audit_gate.py")
    rs = _load("_fast_rs", "ops/release/replay_shadow.py")
    # one ls-tree for the whole PR, not one per file
    rs.tree_files = functools.lru_cache(maxsize=4)(rs.tree_files)  # type: ignore[attr-defined]
    extra = ag.protected_patterns()
    never = ag.never_standing_patterns()
    if extra is None or never is None:
        return "the protected list or the ROOT policy is unreadable"
    held = (*ag.SECRETS, *ag.SEAL_CARRIERS, *ag.PROTECTED, *ag.FORMERLY_PROTECTED, *extra, *never)
    suites: set[str] = set()
    for rel in SUITE_LISTS:
        suites |= _lines(rel)
    closure = money_closure(rs)
    state = {x.lower() for x in rs.state_names(ROOT, closure) if "." in x}
    roster = {*rs.ROSTER_FILES, *rs.ROSTER_HARNESS, rs.MANIFEST}
    made = producers(state, closure, rs.MONEY_PATH)
    return rs, held, suites, closure, state, roster, made


def classify(paths: Iterable[str], head: str | None = None) -> tuple[bool, str]:
    """(fast, why). `head`: the PR head's commit; each changed file's head copy is read through
    git for what it spells (MF3), and the head must be readable when given. Fail closed: an empty
    list, or anything that cannot be read, is not fast."""
    names = sorted({p.strip() for p in paths if p and p.strip()})
    if not names:
        return False, "no changed paths read"
    try:
        facts = base_facts(str(ROOT), _tree_id())
        if isinstance(facts, str):
            return False, facts
        rs, held, suites, closure, state, roster, made = facts
        if head is not None:
            subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{head}^{{commit}}"],
                           capture_output=True, check=True)  # fmt: skip
        files = rs.tree_files(ROOT)
    except Exception as exc:  # any read or import failure: the full path
        return False, f"the classifier could not read the base ({type(exc).__name__}: {exc})"
    for n in names:
        if pat := _match(n, held):
            return False, f"{n} is protected ({pat})"
        if is_box(n):
            return False, f"{n} is box machinery"
        if rs.is_money(n, closure, exempt=set()) or n in roster or n in rs.ENTRY_POINTS:
            return False, f"{n} is on the money path"
        if n in suites:
            return False, f"{n} is a release or risk suite"
        if is_test(n):
            if money_test(rs, n, closure):
                return False, f"{n} tests the money path"
            continue
        if n in made:
            return False, f"{n} {made[n]}, which the money path reads (component registry)"
        try:
            was = money_writes(rs.read(ROOT, n) or "", n, state) if n in files else set()
            text = head_text(head, n)
            now = money_writes(text, n, state) if text is not None else set()
        except (SyntaxError, ValueError):
            return False, f"{n} does not parse"
        # either side: a file that already writes such a name is a producer the PR can change
        # (#1240 audit, second pass), and one the PR makes write it is a new producer
        if hit := sorted(now | was):
            side = "writes" if hit[0] in was else "newly writes"
            return False, f"{n} {side} {hit[0]}, a file the money path reads"
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
        fast, why = classify(changed(a.base, a.head), head=a.head)
    except (subprocess.CalledProcessError, OSError) as exc:
        fast, why = False, f"the diff could not be read ({exc})"
    print(json.dumps({"fast": fast, "why": why}))
    if a.github_output:
        with a.github_output.open("a", encoding="utf-8") as fh:
            fh.write(f"fast={'true' if fast else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
