#!/usr/bin/env python3
"""THE RESEARCH-DATA FENCE (Governance, route A, 2026-11-18): no money-path reader of the home.

`desks/mt5/research/data/` (HOME) holds research-only data. It sits outside every MONEY_PATH
prefix and outside SCRIPT_DIRS of ops/release/replay_shadow.py, so a PR that changes a file there
is not a money-path change -- and that is only true while nothing on the money path reads the
home. This fence makes it a checked fact. It FAILS when:

- a module of the money import closure (`replay_shadow.import_closure` of its ENTRY_POINTS, the
  set ops/money_closure.txt pins) names the home or anything under it: a string literal, a
  constant fold of literals (os.path.join, Path / Path, `+`, an f-string's literal parts; a part
  that is not a literal is a wildcard), or a `__file__`-anchored path that resolves into it;
- such a module lists a directory that resolves into the home; a recursive listing (rglob,
  os.walk, a `**` glob) of an ancestor of it is a dynamic site, pinned only once read;
- the same holds for every Python program the money path RUNS (a money script, a script a money
  row runs, a .py that a scanned module's process start or by-path load resolves to) and for
  its own import closure, imported or not, to a fixed point: a program so reached is scanned
  in turn, and so is every program it runs;
- a script the closure names, a money script (`replay_shadow.money_scripts`), a money row of the
  box's task table, or a script such a row runs names the home;
- a DYNAMIC SITE of the closure (a listing whose argument does not resolve, a dynamic import, a
  process start not resolving to covered code) is not pinned in PINS by file, line and sha256 of
  the stripped line: a new site, or a pinned line that changed or moved, fails closed;
- anything it must read cannot be read or parsed (fail closed).

"Names the home" means a path whose segments run `research/data`, preceded by nothing, a
wildcard or `mt5` (itself preceded by nothing, a wildcard or `desks`): the home itself or any
path inside it, relative to the repository, to the desk or to an unknown base.

PINS lives next to this fence and is read from the checked-out tree. The tree is read as
replay_shadow reads it: from git HEAD when the root is a checkout, else from the disk.

    python scripts/check_research_data_fence.py [--root DIR]
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HOME = "desks/mt5/research/data"
PINS = "scripts/check_research_data_fence_sites.json"


def _replay_shadow(root: Path) -> ModuleType:
    """ops/release/replay_shadow.py of `root`: the closure, the tree reader, the task table."""
    spec = importlib.util.spec_from_file_location(
        "_fence_replay_shadow", root / "ops" / "release" / "replay_shadow.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


#: This checkout's replay_shadow, for callers that want its constants. check() never uses it: it
#: loads the replay_shadow of the tree it checks, so `--root DIR` judges DIR by DIR's own rules.
RS = _replay_shadow(ROOT)

_LISTERS = frozenset({"glob", "iglob", "rglob", "iterdir", "listdir", "scandir", "walk"})
_BY_NAME = {"import_module": 0, "__import__": 0, "run_module": 0}  # dotted name: its arg index
_BY_PATH = {"spec_from_file_location": 1, "run_path": 0, "SourceFileLoader": 1, "load_source": 1}
_SPAWN = frozenset({"system", "popen", "startfile", "spawnv", "spawnl", "execv", "execl"})
_SUBPROCESS = frozenset({"run", "Popen", "call", "check_call", "check_output"})
_PATH_FNS = frozenset(
    {"Path", "PurePath", "PosixPath", "WindowsPath", "str", "fspath", "join", "abspath",
     "realpath", "normpath", "joinpath"}
)  # fmt: skip
_TOKEN = re.compile(r"[\s\"'`,;=()\[\]{}<>|&+]+")
_GLOB = re.compile(r"[*?\[]")
_RECURSIVE = frozenset({"rglob", "walk"})
_RUN_EXTS = (".ps1", ".psm1", ".cmd", ".bat", ".sh")


def _resolve(
    e: ast.AST, mod: str, env: dict[str, ast.expr], memo: dict[int, Any] | None = None
) -> Any:
    """`e` read as a path: (True, repo path) when anchored on `__file__`, (False, text) from
    literals alone, None when it cannot be read statically (fail closed at the caller). `memo`
    (per module) remembers each node; a name met again inside its own definition is None."""
    memo = {} if memo is None else memo
    if id(e) not in memo:
        memo[id(e)] = None  # the cycle guard: `X = X / "a"` does not resolve
        memo[id(e)] = _resolve_once(e, mod, env, memo)
    return memo[id(e)]


def _resolve_once(e: ast.AST, mod: str, env: dict[str, ast.expr], memo: dict[int, Any]) -> Any:
    def r(x: ast.AST) -> Any:
        return _resolve(x, mod, env, memo)

    def join(a: Any, s: str) -> Any:
        if a is None:
            return None
        if s.startswith("/") or re.match(r"[A-Za-z]:", s):
            return False, s
        return a[0], f"{a[1]}/{s}" if a[1] else s

    def up(a: Any, n: int) -> Any:
        if a is None or not a[0]:
            return None if a is None else (False, a[1] + "/.." * n)
        p = os.path.normpath(a[1]).replace("\\", "/")
        for _ in range(n):
            if p in ("", ".") or p.startswith(".."):
                return None
            p = os.path.dirname(p)
        return True, p

    if isinstance(e, ast.Constant) and isinstance(e.value, str):
        return False, e.value.replace("\\", "/")
    if isinstance(e, ast.JoinedStr):
        parts = [v.value for v in e.values if isinstance(v, ast.Constant)]
        return (False, "".join(map(str, parts))) if len(parts) == len(e.values) else None
    if isinstance(e, ast.Name):
        return (True, mod) if e.id == "__file__" else r(env[e.id]) if e.id in env else None
    if isinstance(e, ast.BinOp) and isinstance(e.op, (ast.Div, ast.Add)):
        a, b = r(e.left), r(e.right)
        if a is None or b is None or b[0]:
            return None
        return join(a, b[1]) if isinstance(e.op, ast.Div) else (a[0], a[1] + b[1])
    if isinstance(e, ast.Attribute) and e.attr == "parent":
        return up(r(e.value), 1)
    if (
        isinstance(e, ast.Subscript) and isinstance(e.value, ast.Attribute)
        and e.value.attr == "parents" and isinstance(e.slice, ast.Constant)
        and isinstance(e.slice.value, int)
    ):  # fmt: skip
        return up(r(e.value.value), e.slice.value + 1)
    if (
        isinstance(e, ast.Call)
        and not e.keywords
        and not any(isinstance(a, ast.Starred) for a in e.args)
    ):
        fn = e.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        if isinstance(fn, ast.Attribute) and name in ("resolve", "absolute", "expanduser"):
            return r(fn.value) if not e.args else None
        if name == "dirname" and len(e.args) == 1:
            return up(r(e.args[0]), 1)
        if name in _PATH_FNS:
            acc: Any = r(fn.value) if name == "joinpath" and isinstance(fn, ast.Attribute) else None
            for i, arg in enumerate(e.args):
                b = r(arg)
                if b is None or (b[0] and (i or acc is not None)):
                    return None
                acc = b if acc is None else join(acc, b[1])
            return acc if acc is not None else (False, "")
    return None


def _fold(e: ast.AST, env: dict[str, ast.expr], memo: dict[int, str]) -> str:
    """`e` as the path text its literals spell, every part that is not a literal a `*`: a join
    (os.path.join, Path(...), `/`), a concatenation, an f-string, a name bound once."""
    if id(e) in memo:
        return memo[id(e)]
    memo[id(e)] = "*"  # the cycle guard
    out = "*"
    if isinstance(e, ast.Constant) and isinstance(e.value, str):
        out = e.value.replace("\\", "/")
    elif isinstance(e, ast.JoinedStr):
        out = "".join(
            str(v.value).replace("\\", "/") if isinstance(v, ast.Constant) else "*"
            for v in e.values
        )
    elif isinstance(e, ast.Name) and e.id in env:
        out = _fold(env[e.id], env, memo)
    elif isinstance(e, ast.BinOp) and isinstance(e.op, (ast.Div, ast.Add)):
        glue = "/" if isinstance(e.op, ast.Div) else ""
        out = _fold(e.left, env, memo) + glue + _fold(e.right, env, memo)
    elif isinstance(e, ast.Call):
        fn = e.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        if isinstance(fn, ast.Attribute) and name in ("resolve", "absolute", "expanduser"):
            out = _fold(fn.value, env, memo)
        elif name in _PATH_FNS and e.args:
            head = [fn.value] if name == "joinpath" and isinstance(fn, ast.Attribute) else []
            out = "/".join(_fold(a, env, memo) for a in [*head, *e.args])
    memo[id(e)] = out
    return out


def _names_home(text: str) -> bool:
    """A path text naming the home or anything inside it (see the module note)."""
    s = [x for x in text.replace("\\", "/").casefold().split("/") if x not in ("", ".")]
    wild = [x == ".." or bool(_GLOB.search(x)) for x in s]  # `..` climbs to an unknown base
    for i in range(len(s) - 1):
        if (s[i], s[i + 1]) != ("research", "data"):
            continue
        if i == 0 or wild[i - 1]:
            return True
        if s[i - 1] == "mt5" and (i == 1 or wild[i - 2] or s[i - 2] == "desks"):
            return True
    return False


def _text_names_home(text: str) -> bool:
    """Any whitespace- or quote-delimited token of a script or task row naming the home."""
    return any(_names_home(tok) for tok in _TOKEN.split(text) if "/" in tok or "\\" in tok)


def _site_key(line: str) -> str:
    return hashlib.sha256(line.strip().encode("utf-8")).hexdigest()


def module_facts(
    tree: Path, mod: str, files: set[str], rs: ModuleType | None = None
) -> dict[str, Any] | None:
    """A scanned module's references to the home, the scripts it names and its dynamic sites;
    None when it cannot be read or parsed (fail closed). `rs`: the tree's replay_shadow."""
    rs = RS if rs is None else rs
    src = rs.read(tree, mod)
    if src is None:
        return None
    try:
        return _facts(ast.parse(src), mod, files, src.splitlines(), rs)
    except (SyntaxError, ValueError, RecursionError):  # unparseable, or too deep: fail closed
        return None


def _facts(
    node: ast.AST, mod: str, files: set[str], lines: list[str], rs: ModuleType
) -> dict[str, Any]:
    stores: dict[str, int] = {}
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and not isinstance(n.ctx, ast.Load):
            stores[n.id] = stores.get(n.id, 0) + 1
        elif isinstance(n, ast.arg):
            stores[n.arg] = stores.get(n.arg, 0) + 2
    env: dict[str, ast.expr] = {}
    inner: set[int] = set()  # parts of a bigger path expression: only the whole one is read
    for n in ast.walk(node):
        if isinstance(n, ast.Assign) and len(n.targets) == 1:
            tgt, val = n.targets[0], n.value
            if isinstance(tgt, ast.Name) and stores.get(tgt.id) == 1:
                env[tgt.id] = val
        elif isinstance(n, ast.AnnAssign) and n.value is not None:
            if isinstance(n.target, ast.Name) and stores.get(n.target.id) == 1:
                env[n.target.id] = n.value
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Div, ast.Add)):
            inner |= {id(n.left), id(n.right)}
        elif isinstance(n, ast.JoinedStr):
            inner |= {id(v) for v in n.values}
        elif isinstance(n, ast.Call):
            fn = n.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if name in _PATH_FNS or name in ("resolve", "absolute", "expanduser"):
                inner |= {id(a) for a in n.args}
                if isinstance(fn, ast.Attribute):
                    inner.add(id(fn.value))
    out: dict[str, Any] = {"hits": [], "scripts": set(), "py": set(), "sites": []}
    memo: dict[int, Any] = {}
    folds: dict[int, str] = {}

    def hit(n: ast.AST, what: str) -> None:
        out["hits"].append(f"{mod}:{getattr(n, 'lineno', 0)} {what}")

    def runs(got: tuple[bool, str] | None) -> None:  # the .py a process start or a load runs
        for tok in _TOKEN.split((got or (False, ""))[1].replace("\\", "/").casefold()):
            if tok.endswith(".py"):
                out["py"].add(re.sub(r"^(?:\.{1,2}/)+", "", tok))

    def site(n: ast.Call, kind: str) -> None:
        text = lines[n.lineno - 1] if 0 < n.lineno <= len(lines) else ""
        out["sites"].append((n.lineno, _site_key(text), f"{kind} at {mod}:{n.lineno}"))

    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            for tok in _TOKEN.split(n.value.replace("\\", "/").casefold()):
                last = tok.rsplit("/", 1)[-1]
                if last.endswith(_RUN_EXTS):
                    out["scripts"].add(last)
        pathy = isinstance(n, (ast.Constant, ast.JoinedStr, ast.BinOp, ast.Call, ast.Attribute,
                               ast.Subscript))  # fmt: skip
        if pathy and id(n) not in inner:
            if _names_home(_fold(n, env, folds)):
                hit(n, "spells a path into the home")
            got = _resolve(n, mod, env, memo)
            if got is not None and got[0] and _names_home(got[1]):
                hit(n, f"resolves to {got[1]}, inside the home")
        if not isinstance(n, ast.Call):
            continue
        fn = n.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        recv = fn.value if isinstance(fn, ast.Attribute) else None
        if name in _LISTERS and not (isinstance(recv, ast.Name) and recv.id == "ast"):
            on_module = recv is None or (isinstance(recv, ast.Name) and recv.id in ("os", "glob"))
            arg = (n.args[0] if n.args else None) if on_module else recv
            got = None if arg is None else _resolve(arg, mod, env, memo)
            if got is None:
                site(n, "a directory listing whose argument does not resolve")
                continue
            target = got[1]
            pattern = target if on_module else " ".join(_fold(a, env, folds) for a in n.args)
            recursive = name in _RECURSIVE or "**" in pattern
            segs = target.split("/")
            cut = next((i for i, s in enumerate(segs) if _GLOB.search(s)), len(segs))
            where = "/".join(segs[:cut]).strip("/").casefold()
            if _names_home(target):
                hit(n, f"lists {target}, inside the home")
            elif got[0] and recursive and (where in ("", ".") or HOME.startswith(where + "/")):
                # its pattern decides whether it reaches the home: a site to read, then pin
                site(n, f"a recursive listing of {where or '<repository root>'}, an ancestor of "
                        "the home")  # fmt: skip
            elif not got[0] and recursive and where in ("", "."):
                site(n, "a recursive listing of the working directory, which may hold the home")
        elif name in _SPAWN or (
            isinstance(recv, ast.Name) and recv.id == "subprocess" and name in _SUBPROCESS
        ):
            argv = n.args[0] if n.args else None
            parts = argv.elts if isinstance(argv, (ast.List, ast.Tuple)) else [argv]
            got_all = [
                None if p is None else (False, "") if ast.unparse(p) == "sys.executable"
                else _resolve(p, mod, env, memo)
                for p in parts
            ]  # fmt: skip
            for g in got_all:
                runs(g)
            if any(g is None or g[1].endswith(".py") for g in got_all):
                site(n, "a process start that does not resolve to a covered program")
        elif name in _BY_NAME or name in _BY_PATH:
            i = _BY_NAME.get(name, _BY_PATH.get(name, 0))
            got = _resolve(n.args[i], mod, env, memo) if len(n.args) > i else None
            if name in _BY_PATH:
                runs(got)
            if (
                got is not None and name in _BY_NAME and not got[0]
                and not got[1].startswith(".") and not rs._module_files(got[1], files)
            ):  # fmt: skip
                continue  # a module outside the repository: the standard library or a package
            site(n, f"a dynamic import ({name})")
    return out


def _named_py(tok: str, mod: str, files: set[str], by_name: dict[str, set[str]]) -> set[str]:
    """The tree's .py files a literal token names: a path names every file it is a path-suffix
    of; a bare name names its sibling of the naming module, else every file of that name."""
    same = {f for f in by_name.get(tok.rsplit("/", 1)[-1], set())
            if f.casefold() == tok or f.casefold().endswith("/" + tok)}  # fmt: skip
    if "/" in tok:
        return same
    sibling = {f for f in same if f.rsplit("/", 1)[0] == mod.rsplit("/", 1)[0]}
    return sibling or same


def load_pins(root: Path) -> dict[tuple[str, int], str] | None:
    """{(file, line): sha256} from PINS in the checked-out tree; None when unreadable."""
    try:
        rows = json.loads((root / PINS).read_text("utf-8"))["sites"]
        return {(str(r["file"]), int(r["line"])): str(r["sha256"]) for r in rows}
    except (OSError, ValueError, TypeError, KeyError):
        return None


def check(root: Path = ROOT, rs: ModuleType | None = None) -> dict[str, Any]:
    """{"ok", "violations", "closure", "scanned", "sites", "pinned", "stale_pins"} for the tree
    at `root`, judged by that tree's own replay_shadow (`rs`, loaded from `root` when None)."""
    bad: list[str] = []
    if rs is None:
        try:
            rs = _replay_shadow(root)
        except (OSError, ImportError, SyntaxError) as exc:
            msg = f"{root}/ops/release/replay_shadow.py cannot be loaded ({type(exc).__name__})"
            return {"ok": False, "violations": [msg + ": no closure to fence (fail closed)"],
                    "closure": 0, "scanned": 0, "sites": 0, "pinned": 0, "site_rows": [],
                    "stale_pins": []}  # fmt: skip
    pins = load_pins(root)
    if pins is None:
        bad.append(f"{PINS} cannot be read: every dynamic site is unpinned (fail closed)")
        pins = {}
    files = rs.tree_files(root)
    missing = [e for e in rs.ENTRY_POINTS if e not in files]
    bad += [f"entry point {e} is not in the tree: no closure to fence" for e in missing]
    closure = rs.import_closure(root)
    by_name: dict[str, set[str]] = {}
    for f in files:
        by_name.setdefault(Path(f).name.casefold(), set()).add(f)
    # what the money path RUNS, beside what it imports: the money scripts and the money rows
    scripts: set[str] = set(rs.money_scripts((root,), closure))
    manifest = rs.read(root, rs.MANIFEST)
    if manifest is None and rs.MANIFEST in files:
        bad.append(f"{rs.MANIFEST} cannot be read (fail closed)")
    for line in (manifest or "").splitlines():
        attrs, low = dict(rs._ATTR.findall(line)), line.lower()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if (
            line.startswith("TASK ")
            and attrs.get("lane") in rs._FREE_LANES
            and not (rs.MONEY_WORDS.search(low) or rs.STATE_WORDS.search(low))
        ):
            continue  # not a money row
        if _text_names_home(line):
            bad.append(f"{rs.MANIFEST}: a money row names the home: {line.strip()[:120]}")
        for k in ("runs", "also_runs", "installer"):
            scripts |= {p.strip() for p in attrs.get(k, "").split(",") if p.strip() in files}
    # every Python program the money path runs is scanned as a module with its own import
    # closure, whether or not an entry point imports it (Auditor MF, 2026-11-18); a .py that a
    # scanned module runs is such a program too, so the scan runs to a fixed point: each pass
    # adds every newly run .py with its import closure, until nothing new is reached
    scan: set[str] = set()
    pending = set(closure) | {s for s in scripts if s.endswith(".py")}
    seen: set[tuple[str, int]] = set()
    rows: list[tuple[str, int, str, str]] = []  # every site found: (file, line, sha256, what)
    while pending:
        run_py = tuple(sorted(s for s in pending if s not in closure))
        new = (pending | (rs.import_closure(root, run_py) if run_py else set())) - scan
        scan |= new
        named: set[str] = set()
        for m in sorted(new):
            fx = module_facts(root, m, files, rs)
            what_m = "a money-closure module" if m in closure else "a money-run program's module"
            if fx is None:
                bad.append(f"{m}: {what_m} that cannot be read or parsed (fail closed)")
                continue
            bad += [f"{h} ({what_m})" for h in fx["hits"]]
            named |= {f for b in fx["scripts"] for f in by_name.get(b, set())}
            named |= {f for t in fx["py"] for f in _named_py(t, m, files, by_name)}
            for line, key, what in fx["sites"]:
                seen.add((m, line))
                rows.append((m, line, key, what))
                if pins.get((m, line)) != key:
                    bad.append(f"unpinned dynamic site: {what} (new, moved or changed)")
        scripts |= named
        pending = {s for s in named if s.endswith(".py")} - scan
    for s in sorted(scripts):
        if s.endswith(".py"):
            continue  # scanned above, with its import closure
        text = rs.read(root, s)
        if text is None:
            bad.append(f"{s}: a money script that cannot be read (fail closed)")
        elif _text_names_home(text):
            bad.append(f"{s}: a money script names the home")
    return {
        "ok": not bad, "violations": bad, "closure": len(closure), "scanned": len(scan),
        "sites": len(seen), "pinned": len(pins), "site_rows": rows,
        "stale_pins": sorted(f"{f}:{n}" for f, n in set(pins) - seen),
    }  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=Path, default=ROOT)
    a = ap.parse_args(argv)
    rep = check(a.root)
    for v in rep["violations"][:200]:
        print(" -", v)
    for p in rep["stale_pins"]:
        print(f" . stale pin (its site is gone; safe to drop): {p}")
    verdict = "PASS" if rep["ok"] else f"FAIL ({len(rep['violations'])} violations)"
    print(
        f"RESEARCH-DATA FENCE {verdict}: {rep['closure']} money-closure modules, "
        f"{rep['scanned']} scanned with the money-run programs, "
        f"{rep['sites']} dynamic sites, {rep['pinned']} pinned; nothing on the money path may "
        f"read {HOME}/"
    )
    return 0 if rep["ok"] else 1


# No command-line entry yet: until the ROOT half wires this into scripts/run_law_gate.py
# (_LAW_FENCES) with its runtime_state row, its clock is the quality check, which runs
# tests/scripts/test_check_research_data_fence.py::test_todays_tree_is_green on every PR.
