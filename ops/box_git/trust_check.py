"""THE TRUST-BOUNDARY CHECKER: which merges need the owner, decided by code, never by an AI.

WHY (principal 2026-11-19 20:22Z): one stable standing policy authorizes routine merge-gate,
deployment and recovery changes; an independent deterministic checker verifies compliance; only
changes to trusted signers, verification rules or AI authority need the owner. Governance owns
the policy (ops/box_git/TRUST_SET.json); journal D-20261119-TRUSTSET.

HOW IT IS INDEPENDENT. The gate loads this module and TRUST_SET.json from a box-local folder only
Administrators and SYSTEM can write (C:\\ProgramData\\QuantBox\\trust), never from the checkout or
a PR. That copy moves only after a merge the owner authorized or this checker proved tightens.
Pure stdlib, no network, no model.

THE TRUST SET T, measured at a commit:
  * every file matching `files` (whole content);
  * for each `symbols` file, the STATIC CALL CLOSURE of the named symbols: every module-level
    binding they reference, transitively, across repository modules they import, compared as ASTs
    (comments and formatting are not trust). In any file holding frozen symbols, `global`
    statements and calls to setattr / globals / exec / eval / __import__ / importlib are part of T.
  * TRUST_SET.json itself.

CLASSES (classify):
  ORDINARY  T is byte-for-byte the same AST at head as at base.
  TIGHTEN   T changed only by: lines appended or inserted into a `grow_only` list (plain paths,
            globs or comments; nothing removed or reordered); TRUST_SET.json gaining entries in
            `files` / `symbols` (more frozen, never less); new test files.
  TRUST     anything else in T, and anything this module cannot measure (fails closed).
"""
from __future__ import annotations

import ast
import fnmatch
import hashlib
import json
import re
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

POLICY_PATH = "ops/box_git/TRUST_SET.json"
HAZARD_CALLS = frozenset({"setattr", "delattr", "globals", "exec", "eval", "__import__",
                          "compile", "vars"})
HAZARD_MODULES = frozenset({"importlib"})
PLAIN_LINE = re.compile(r"[A-Za-z0-9_./*?\[\]{},@+-]+")

#: git(*args) -> stdout; raises on failure (the gate's own _git).
Git = Callable[..., str]


class Unmeasured(Exception):
    """Anything the checker cannot measure: the caller treats it as TRUST / refuses."""


def load_policy(text: str | None = None) -> dict[str, Any]:
    raw = text if text is not None else Path(__file__).with_name("TRUST_SET.json").read_text(
        encoding="utf-8")
    doc = json.loads(raw)
    for k in ("files", "grow_only", "symbols"):
        if k not in doc:
            raise Unmeasured(f"policy lacks {k}")
    return doc


class Tree:
    """Read-only view of one commit through git."""

    def __init__(self, git: Git, ref: str) -> None:
        self.git, self.ref = git, ref
        self._names: list[str] | None = None
        self._ast: dict[str, ast.Module] = {}

    def names(self) -> list[str]:
        if self._names is None:
            self._names = self.git("ls-tree", "-r", "--name-only", self.ref).splitlines()
        return self._names

    def has(self, path: str) -> bool:
        return path in set(self.names())

    def text(self, path: str) -> str | None:
        if not self.has(path):
            return None
        return self.git("show", f"{self.ref}:{path}")

    def module(self, path: str) -> ast.Module:
        if path not in self._ast:
            src = self.text(path)
            if src is None:
                raise Unmeasured(f"{path} is missing at {self.ref}")
            try:
                self._ast[path] = ast.parse(src)
            except SyntaxError as exc:
                raise Unmeasured(f"{path} does not parse at {self.ref}") from exc
        return self._ast[path]

    def module_path(self, dotted: str) -> str | None:
        base = dotted.replace(".", "/")
        for cand in (f"{base}.py", f"{base}/__init__.py"):
            if self.has(cand):
                return cand
        return None


def _top_bindings(mod: ast.Module) -> dict[str, list[ast.AST]]:
    """name -> every module-level statement binding it (into if/try/with blocks, not functions)."""
    out: dict[str, list[ast.AST]] = {}

    def bind(name: str, node: ast.AST) -> None:
        out.setdefault(name, []).append(node)

    def walk(body: Iterable[ast.stmt]) -> None:
        for st in body:
            if isinstance(st, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                bind(st.name, st)
            elif isinstance(st, ast.Assign | ast.AnnAssign | ast.AugAssign):
                targets = st.targets if isinstance(st, ast.Assign) else [st.target]
                for t in targets:
                    for n in ast.walk(t):
                        if isinstance(n, ast.Name):
                            bind(n.id, st)
            elif isinstance(st, ast.Import | ast.ImportFrom):
                for a in st.names:
                    bind((a.asname or a.name).split(".")[0], st)
            elif isinstance(st, ast.If | ast.Try | ast.With | ast.For | ast.While):
                for field in ("body", "orelse", "finalbody"):
                    walk(getattr(st, field, []) or [])
                for h in getattr(st, "handlers", []) or []:
                    walk(h.body)
    walk(mod.body)
    return out


def _imports(mod: ast.Module) -> dict[str, tuple[str, str | None]]:
    """local name -> (module, attribute or None) for module-level imports."""
    out: dict[str, tuple[str, str | None]] = {}
    for st in ast.walk(mod):
        if isinstance(st, ast.Import):
            for a in st.names:
                out[a.asname or a.name.split(".")[0]] = (a.name if a.asname else
                                                         a.name.split(".")[0], None)
        elif isinstance(st, ast.ImportFrom) and st.module and not st.level:
            for a in st.names:
                out[a.asname or a.name] = (st.module, a.name)
    return out


def _hazards(mod: ast.Module) -> list[ast.AST]:
    found: list[ast.AST] = []
    for n in ast.walk(mod):
        if isinstance(n, ast.Global):
            found.append(n)
        elif isinstance(n, ast.Call):
            f = n.func
            name = f.id if isinstance(f, ast.Name) else None
            root = f
            while isinstance(root, ast.Attribute):
                root = root.value
            if name in HAZARD_CALLS or (isinstance(root, ast.Name) and root.id in HAZARD_MODULES):
                found.append(n)
    return found


def _dump(nodes: Iterable[ast.AST]) -> str:
    return hashlib.sha256("\n".join(ast.dump(n, include_attributes=False) for n in nodes)
                          .encode()).hexdigest()


def closure(tree: Tree, roots: dict[str, list[str]]) -> dict[str, str]:
    """{"path::name": digest} for the static closure of `roots` ({path: [names]})."""
    out: dict[str, str] = {}
    todo = [(p, n) for p, names in roots.items() for n in names]
    whole: set[str] = set()
    seen: set[tuple[str, str]] = set()
    while todo:
        path, name = todo.pop()
        if (path, name) in seen or path in whole:
            continue
        seen.add((path, name))
        mod = tree.module(path)
        binds = _top_bindings(mod)
        if name not in binds:
            raise Unmeasured(f"{path}: frozen name {name} is not bound at {tree.ref}")
        nodes = binds[name]
        out[f"{path}::{name}"] = _dump(nodes)
        if f"{path}::__hazards__" not in out:
            out[f"{path}::__hazards__"] = _dump(_hazards(mod))
        imps = _imports(mod)
        for node in nodes:
            if isinstance(node, ast.Import | ast.ImportFrom):
                continue
            for ref in ast.walk(node):
                if isinstance(ref, ast.Attribute) and isinstance(ref.value, ast.Name):
                    imp = imps.get(ref.value.id)
                    if imp:
                        dotted = imp[0] if imp[1] is None else f"{imp[0]}.{imp[1]}"
                        target = tree.module_path(dotted)
                        if target:
                            todo.append((target, ref.attr))
                            continue
                if (isinstance(ref, ast.Name) and isinstance(ref.ctx, ast.Load)
                        and ref.id in binds and ref.id != name):
                    imp = imps.get(ref.id)
                    if imp is None:
                        todo.append((path, ref.id))
                        continue
                    mod_name, attr = imp
                    as_module = tree.module_path(f"{mod_name}.{attr}" if attr else mod_name)
                    if as_module and _used_bare(node, ref.id):
                        whole.add(as_module)
                    elif attr and not as_module and (target := tree.module_path(mod_name)):
                        todo.append((target, attr))
                    out[f"{path}::{ref.id}"] = _dump(binds[ref.id])
    for path in sorted(whole):
        out[f"{path}::*"] = hashlib.sha256((tree.text(path) or "").encode()).hexdigest()
    return out


def _used_bare(node: ast.AST, name: str) -> bool:
    """`name` appears other than as `name.attr` inside node (the module object escapes)."""
    attr_bases = {id(a.value) for a in ast.walk(node)
                  if isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name)}
    return any(isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load)
               and id(n) not in attr_bases for n in ast.walk(node))


def measure(git: Git, ref: str, policy: dict[str, Any]) -> dict[str, str]:
    """T at `ref`: {key: digest}."""
    tree = Tree(git, ref)
    out: dict[str, str] = {}
    for path in tree.names():
        if path == POLICY_PATH or any(fnmatch.fnmatchcase(path, g) for g in policy["files"]):
            out[f"{path}::*"] = hashlib.sha256((tree.text(path) or "").encode()).hexdigest()
    roots = {p: list(v) for p, v in policy["symbols"].items() if tree.has(p)}
    missing = [p for p in policy["symbols"] if not tree.has(p)]
    if missing:
        raise Unmeasured(f"frozen symbol files missing at {ref}: {missing}")
    out.update(closure(tree, roots))
    return out


def t_hash(git: Git, ref: str, policy: dict[str, Any] | None = None) -> str:
    m = measure(git, ref, policy or load_policy())
    return hashlib.sha256(json.dumps(m, sort_keys=True).encode()).hexdigest()


def _grows(base: str, head: str) -> bool:
    """head keeps every base line in order and adds only plain path/glob lines or comments."""
    b, h = base.splitlines(), head.splitlines()
    i = 0
    for line in h:
        if i < len(b) and line == b[i]:
            i += 1
            continue
        s = line.strip()
        if s and not s.startswith("#") and not PLAIN_LINE.fullmatch(s):
            return False
    return i == len(b)


def _policy_grows(base: str, head: str) -> bool:
    try:
        b, h = json.loads(base), json.loads(head)
    except ValueError:
        return False
    if set(b) != set(h) or b.get("grow_only") != h.get("grow_only"):
        return False
    for k in b:
        if k == "files":
            if [x for x in h[k] if x in b[k]] != b[k]:
                return False
        elif k == "symbols":
            for p, names in b[k].items():
                if [x for x in h[k].get(p, []) if x in names] != names:
                    return False
        elif b[k] != h[k]:
            return False
    return True


def is_new_test(base: Tree, path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return (path.startswith(("tests/", "desks/mt5/tests/")) and name.startswith("test_")
            and name.endswith(".py") and not base.has(path))


def classify(git: Git, base: str, head: str, changed: list[str],
             policy: dict[str, Any] | None = None) -> tuple[str, str]:
    pol = policy or load_policy()
    try:
        mb, mh = measure(git, base, pol), measure(git, head, pol)
    except Exception as exc:  # anything unmeasured is TRUST (Unmeasured included)
        return "TRUST", f"unmeasured: {exc}"[:300]
    moved = sorted(k for k in set(mb) | set(mh) if mb.get(k) != mh.get(k))
    if not moved:
        return "ORDINARY", "the trust set is unchanged"
    tb, th = Tree(git, base), Tree(git, head)
    for key in moved:
        path, _, what = key.partition("::")
        if what != "*":
            return "TRUST", f"{path}: frozen code {what} changed"
        old, new = tb.text(path), th.text(path)
        if old is None and new is not None and is_new_test(tb, path):
            continue
        if old is None or new is None:
            return "TRUST", f"{path} added or removed inside the trust set"
        if path in pol["grow_only"] and _grows(old, new):
            continue
        if path == POLICY_PATH and _policy_grows(old, new):
            continue
        return "TRUST", f"{path} changed inside the trust set"
    return "TIGHTEN", "only grow-only additions inside the trust set: " + ", ".join(
        sorted({k.partition("::")[0] for k in moved}))[:250]
