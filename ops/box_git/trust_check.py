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
  REFUSE    a file named in `hard_caps` (the prop firms' own published limits) loses a capped row
            or sets it above its cap. Checked FIRST and never overridable: not by the Auditor, not
            by the owner's AUTHORIZE TRUST. Everything else in that file (the desk's own risk
            limits) is ordinary, set autonomously on an Auditor CLEAR (RISK AUTONOMY).
"""
from __future__ import annotations

import ast
import fnmatch
import hashlib
import json
import re
import subprocess
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

POLICY_PATH = "ops/box_git/TRUST_SET.json"
HAZARD_CALLS = frozenset({"setattr", "delattr", "globals", "exec", "eval", "__import__",
                          "compile", "vars"})
HAZARD_MODULES = frozenset({"importlib"})
PLAIN_LINE = re.compile(r"[A-Za-z0-9_./*?\[\]{},@+][A-Za-z0-9_./*?\[\]{},@+-]*")
MUTATORS = frozenset({"append", "extend", "insert", "remove", "pop", "clear", "update", "add",
                      "discard", "setdefault", "popitem", "sort", "reverse", "__setitem__",
                      "__delitem__", "__setattr__", "__iadd__", "difference_update",
                      "intersection_update", "symmetric_difference_update"})

#: git(*args) -> stdout; raises on failure (the gate's own _git).
Git = Callable[..., str]


class Unmeasured(Exception):
    """Anything the checker cannot measure: the caller treats it as TRUST / refuses."""


def strict_git(*prefix: str, timeout: float = 300) -> Callable[..., str]:
    """The only git reader for trust measurements: bytes in, strict UTF-8 out. A failed command,
    a missing stdout or one undecodable byte raises Unmeasured (callers treat it as TRUST), never a
    replacement character or a truncated read (the Windows box once pinned cp1252 output)."""
    def run(*a: str) -> str:
        p = subprocess.run([*prefix, *a], capture_output=True, timeout=timeout, check=False)
        if p.returncode != 0 or p.stdout is None:
            raise Unmeasured(f"git {' '.join(a[:2])} failed (exit {p.returncode})")
        try:
            return p.stdout.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise Unmeasured(f"git {' '.join(a[:2])}: not UTF-8 at byte {exc.start}") from exc
    return run


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


def _unsafe_imports(mod: ast.Module, path: str) -> None:
    for n in ast.walk(mod):
        if isinstance(n, ast.ImportFrom) and (n.level or any(a.name == "*" for a in n.names)):
            raise Unmeasured(f"{path}: star or relative import (line {n.lineno})")


def _toplevel_effects(mod: ast.Module) -> list[ast.AST]:
    """Module-level statements that are not a def, class, assignment or import: calls, if/try
    blocks and the like can change a frozen value at import time."""
    plain = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Assign, ast.AnnAssign,
             ast.Import, ast.ImportFrom)
    return [st for st in mod.body if not isinstance(st, plain)
            and not (isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant))]


def _mutations(mod: ast.Module, names: set[str]) -> list[ast.AST]:
    """Every store, delete, augmented assignment or mutating call on a frozen name, anywhere in
    the file (inside functions too): `GATING.remove(x)`, `FROZEN[k] = v`, `del OWNERS[0]`."""
    found: list[ast.AST] = []

    def base(n: ast.AST) -> str | None:
        while isinstance(n, ast.Attribute | ast.Subscript):
            n = n.value
        return n.id if isinstance(n, ast.Name) else None
    for n in ast.walk(mod):
        if isinstance(n, ast.Assign | ast.AugAssign | ast.AnnAssign | ast.Delete):
            targets = (n.targets if isinstance(n, ast.Assign | ast.Delete) else [n.target])
            for t in targets:
                deep = isinstance(t, ast.Attribute | ast.Subscript) and base(t) in names
                aug = isinstance(n, ast.AugAssign) and isinstance(t, ast.Name) and t.id in names
                if deep or aug:
                    found.append(n)
        elif (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and n.func.attr in MUTATORS and base(n.func.value) in names):
            found.append(n)
    return found


def foreign_stores(mod: ast.Module, frozen: dict[str, set[str]], tree: Tree) -> list[str]:
    """In any module: `audit_gate.TRUSTED = ...`, setattr(mod, ...) or a mutating call on a frozen
    name reached through an imported frozen-symbol module."""
    imps = _imports(mod)
    by_local: dict[str, set[str]] = {}
    for local, (m, attr) in imps.items():
        target = tree.module_path(f"{m}.{attr}" if attr else m)
        if target in frozen:
            by_local[local] = frozen[target]
    if not by_local:
        return []
    out = []
    for n in ast.walk(mod):
        if (isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store | ast.Del)
                and isinstance(n.value, ast.Name) and n.value.id in by_local):
            out.append(f"stores {n.value.id}.{n.attr}")
        elif isinstance(n, ast.Call):
            f = n.func
            if (isinstance(f, ast.Name) and f.id in ("setattr", "delattr") and n.args
                    and isinstance(n.args[0], ast.Name) and n.args[0].id in by_local):
                out.append(f"{f.id} on {n.args[0].id}")
            elif (isinstance(f, ast.Attribute) and f.attr in MUTATORS
                  and isinstance(f.value, ast.Attribute) and isinstance(f.value.value, ast.Name)
                  and f.value.value.id in by_local
                  and f.value.attr in by_local[f.value.value.id]):
                out.append(f"mutates {f.value.value.id}.{f.value.attr}")
    return out


def _strip_docstrings(node: ast.AST) -> ast.AST:
    """A copy with docstrings removed: a doc edit is SAME-CODE, never trust."""
    import copy
    n = copy.deepcopy(node)
    for x in ast.walk(n):
        body = getattr(x, "body", None)
        doc = (isinstance(body, list) and bool(body) and isinstance(body[0], ast.Expr)
               and isinstance(body[0].value, ast.Constant)
               and isinstance(body[0].value.value, str))
        scoped = isinstance(x, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        if scoped and doc:
            x.body = body[1:] or [ast.Pass()]
    return n


def _dump(nodes: Iterable[ast.AST]) -> str:
    return hashlib.sha256("\n".join(ast.dump(_strip_docstrings(n), include_attributes=False)
                                    for n in nodes).encode()).hexdigest()



# ---------------------------------------------------------------------------------------------
# KNOBS (boot r17, zuck 2026-11-26 17:33Z "cut every protected change possible all except core";
# Audit pre-read TRUST_SHRINK_AUDIT_PREREAD.md, 23 items). A knob is a name inside a symbols
# file's closure whose change can only delay, re-run or resize work: the closure CUTS at it (not
# recorded, not traversed) once the checker has proved, at the measured commit, that it still is
# one. The knob list is read from the policy THE CALLER PASSES (the installed/base policy, never
# the head's, item 17). Anything that fails a rule raises Unmeasured, so the change is TRUST
# (item 18).
#   constant: exactly ONE module-level binding, a plain `NAME = <literal>` (int/float/bool, or
#             `re.compile("<literal>")` when the spec says "regex"), inside its [min, max]
#             (None = open on that side; one-sided ranges pin today's value as the floor or cap).
#   function: a PURE def: no decorators, literal defaults, `from __future__ import annotations`
#             in the file, and a body that can only compute from its arguments (see _Pure).
#             Its callers in every symbols file are only the named T functions or other knobs.
# ---------------------------------------------------------------------------------------------
SAFE_BUILTINS = frozenset({"len", "sum", "any", "all", "min", "max", "sorted", "int", "float",
                           "str", "bool", "dict", "list", "set", "tuple", "isinstance",
                           "enumerate", "zip", "range", "round", "abs", "ValueError",
                           "TypeError", "KeyError"})
_BANNED_NODES = (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.Yield, ast.YieldFrom,
                 ast.Await, ast.AsyncFunctionDef, ast.ClassDef, ast.With, ast.AsyncWith,
                 ast.Delete)
_LITERAL = (int, float, bool)


def _literal_default(n: ast.AST) -> bool:
    if isinstance(n, ast.Constant):
        return n.value is None or isinstance(n.value, int | float | bool | str)
    return isinstance(n, ast.Tuple) and all(_literal_default(e) for e in n.elts)


def knobs_of(pol: dict[str, Any], path: str) -> dict[str, Any]:
    spec = (pol.get("knobs") or {}).get(path) or {}
    return spec if isinstance(spec, dict) else {}


def _knob_names(spec: dict[str, Any]) -> set[str]:
    return set(spec.get("constants") or {}) | set(spec.get("functions") or {})


def _check_constant(mod: ast.Module, path: str, name: str, rule: Any) -> None:
    binds = _top_bindings(mod).get(name) or []
    if len(binds) != 1 or not isinstance(binds[0], ast.Assign):
        raise Unmeasured(f"{path}: knob {name} is not one plain assignment")
    st = binds[0]
    if len(st.targets) != 1 or not isinstance(st.targets[0], ast.Name):
        raise Unmeasured(f"{path}: knob {name} is not a single-name assignment")
    for n in ast.walk(mod):
        if isinstance(n, ast.Global) and name in n.names:
            raise Unmeasured(f"{path}: knob {name} is declared global")
    v = st.value
    if isinstance(rule, dict) and rule.get("regex"):
        ok = (isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute)
              and isinstance(v.func.value, ast.Name) and v.func.value.id == "re"
              and v.func.attr == "compile" and not v.keywords and len(v.args) == 1
              and isinstance(v.args[0], ast.Constant) and isinstance(v.args[0].value, str))
        if not ok:
            raise Unmeasured(f"{path}: knob {name} is not re.compile(<literal>)")
        return
    if not (isinstance(v, ast.Constant) and isinstance(v.value, _LITERAL)):
        raise Unmeasured(f"{path}: knob {name} is not a numeric literal")
    lo, hi = [*list(rule), None, None][:2] if isinstance(rule, list | tuple) else (None, None)
    x = v.value
    if (lo is not None and x < lo) or (hi is not None and x > hi):
        raise Unmeasured(f"{path}: knob {name} = {x!r} is outside [{lo}, {hi}]")


class _Pure(ast.NodeVisitor):
    """Proves one function body can only compute from its arguments (Audit pre-read A1-A6)."""

    def __init__(self, path: str, fn: str, allowed: set[str], calls: set[str],
                 methods: set[str], attrs: set[str]) -> None:
        self.path, self.fn = path, fn
        self.allowed, self.calls, self.methods, self.attrs = allowed, calls, methods, attrs
        self.local_fns: set[str] = set()
        self.frozen_calls: set[str] = set()

    def bad(self, n: ast.AST, why: str) -> None:
        raise Unmeasured(f"{self.path}: knob {self.fn} is not pure ({why}, line "
                         f"{getattr(n, 'lineno', '?')})")

    def check_args(self, a: ast.arguments, n: ast.AST) -> None:
        for d in [*a.defaults, *[k for k in a.kw_defaults if k is not None]]:
            if not _literal_default(d):
                self.bad(n, "a non-literal default")

    def generic_visit(self, node: ast.AST) -> None:
        if isinstance(node, _BANNED_NODES):
            self.bad(node, type(node).__name__)
        super().generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.decorator_list:
            self.bad(node, "a decorator")
        self.check_args(node.args, node)
        self.local_fns.add(node.name)
        for st in node.body:
            self.visit(st)
        # annotations are inert under `from __future__ import annotations` (checked by caller)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self.check_args(node.args, node)
        self.visit(node.body)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # (Audit r17 MF1) a WHITELIST, not an underscore ban: gi_frame, f_builtins, cr_frame,
        # tb_frame ... carry no underscore. Calls are checked in visit_Call against `methods`;
        # a plain load must be in `attrs`.
        if node.attr.startswith("_") or node.attr not in self.attrs:
            self.bad(node, f"attribute .{node.attr}")
        self.visit(node.value)

    def callable_arg(self, n: ast.AST) -> None:
        """A value a callee may CALL (key=): only a lambda, a local def or a knob function."""
        ok = isinstance(n, ast.Lambda) or (isinstance(n, ast.Name) and (
            n.id in self.local_fns or n.id in self.calls - self.frozen_calls))
        if not ok:
            self.bad(n, "a callable argument that is not a lambda, local def or knob")

    def visit_Call(self, node: ast.Call) -> None:
        f = node.func
        if isinstance(f, ast.Name):
            if f.id not in SAFE_BUILTINS and f.id not in self.calls \
                    and f.id not in self.local_fns:
                self.bad(node, f"a call to {f.id}")
        elif isinstance(f, ast.Attribute):
            if f.attr.startswith("_") or f.attr not in self.methods:
                self.bad(node, f"method .{f.attr}")
            self.visit(f.value)
        else:
            self.bad(node, "a call through an expression")
        for k in node.keywords:
            if k.arg is None:
                self.bad(node, "a ** argument")
            if k.arg == "key":
                self.callable_arg(k.value)
        for a in node.args:
            if isinstance(a, ast.Starred):
                self.bad(node, "a * argument")
        for a in [*node.args, *[k.value for k in node.keywords]]:
            self.visit(a)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load) and node.id not in self.allowed:
            self.bad(node, f"name {node.id}")


def _local_names(fn: ast.FunctionDef) -> set[str]:
    out: set[str] = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.arg):
            out.add(n.arg)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            out.add(n.id)
        elif isinstance(n, ast.FunctionDef | ast.Lambda) and n is not fn:
            if isinstance(n, ast.FunctionDef):
                out.add(n.name)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
    return out


def _check_function(mod: ast.Module, path: str, name: str, spec: dict[str, Any]) -> None:
    binds = _top_bindings(mod).get(name) or []
    if len(binds) != 1 or not isinstance(binds[0], ast.FunctionDef):
        raise Unmeasured(f"{path}: knob {name} is not one plain def")
    fn = binds[0]
    future = any(isinstance(st, ast.ImportFrom) and st.module == "__future__"
                 and any(a.name == "annotations" for a in st.names) for st in mod.body)
    if not future:
        raise Unmeasured(f"{path}: knob {name}: annotations are live (no __future__ import)")
    knobs = _knob_names(spec)
    calls = set(spec.get("frozen_calls") or []) | set(spec.get("functions") or {})
    allowed = (_local_names(fn) | knobs | set(spec.get("frozen_refs") or []) | SAFE_BUILTINS
               | {"True", "False", "None"})
    v = _Pure(path, name, allowed, calls, set(spec.get("methods") or []),
              set(spec.get("attrs") or []))
    v.frozen_calls = set(spec.get("frozen_calls") or [])
    if fn.decorator_list:
        v.bad(fn, "a decorator")
    v.check_args(fn.args, fn)
    for st in fn.body:
        v.visit(st)


def _check_callers(tree: Tree, pol: dict[str, Any]) -> None:
    """Every load of a knob FUNCTION inside a symbols file sits in a named caller or a knob."""
    for path in pol.get("symbols") or {}:
        if not tree.has(path):
            continue
        mod = tree.module(path)
        imps = _imports(mod)
        for top, nodes in _top_bindings(mod).items():
            for node in nodes:
                if isinstance(node, ast.Import | ast.ImportFrom):
                    continue
                for ref in ast.walk(node):
                    owner, fname = None, None
                    if isinstance(ref, ast.Name) and isinstance(ref.ctx, ast.Load):
                        owner, fname = path, ref.id
                    elif isinstance(ref, ast.Attribute) and isinstance(ref.value, ast.Name) \
                            and ref.value.id in imps:
                        m, attr = imps[ref.value.id]
                        owner = tree.module_path(f"{m}.{attr}" if attr else m)
                        fname = ref.attr
                    if owner is None or fname is None:
                        continue
                    spec = knobs_of(pol, owner)
                    funcs = spec.get("functions") or {}
                    if fname not in funcs or (owner == path and top == fname):
                        continue
                    callers = set((funcs.get(fname) or {}).get("callers") or [])
                    if owner != path or (top not in callers and top not in funcs):
                        raise Unmeasured(f"{path}::{top} uses knob {owner}::{fname} "
                                         "outside its named callers")
        for st in ast.walk(mod):
            if isinstance(st, ast.ImportFrom) and st.module and not st.level:
                owner = tree.module_path(st.module)
                if owner and owner != path:
                    funcs = knobs_of(pol, owner).get("functions") or {}
                    hit = [a.name for a in st.names if a.name in funcs]
                    if hit:
                        raise Unmeasured(f"{path} imports knob {owner}::{hit[0]}")


def check_knob(tree: Tree, pol: dict[str, Any], path: str, name: str) -> None:
    spec = knobs_of(pol, path)
    mod = tree.module(path)
    if name in (spec.get("constants") or {}):
        _check_constant(mod, path, name, spec["constants"][name])
    else:
        _check_function(mod, path, name, spec)


def closure(tree: Tree, roots: dict[str, list[str]],
            pol: dict[str, Any] | None = None) -> dict[str, str]:
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
        if pol is not None and name in _knob_names(knobs_of(pol, path)):
            check_knob(tree, pol, path, name)   # proved a knob here, or Unmeasured -> TRUST
            out[f"{path}::{name}"] = "KNOB"
            continue
        mod = tree.module(path)
        binds = _top_bindings(mod)
        if name not in binds:
            raise Unmeasured(f"{path}: frozen name {name} is not bound at {tree.ref}")
        nodes = binds[name]
        out[f"{path}::{name}"] = _dump(nodes)
        if f"{path}::__hazards__" not in out:
            _unsafe_imports(mod, path)
            out[f"{path}::__hazards__"] = _dump(_hazards(mod))
            out[f"{path}::__toplevel__"] = _dump(_toplevel_effects(mod))
            out[f"{path}::__mutations__"] = _dump(_mutations(mod, set(binds)))
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
                    if pol is None or ref.id not in _knob_names(knobs_of(pol, path)):
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
    for key in list(out):
        path = key.partition("::")[0]
        if path.endswith(".py") and path != POLICY_PATH and "/tests/" not in f"/{path}":
            names = [n for n in _top_bindings(tree.module(path))
                     if not isinstance(_top_bindings(tree.module(path))[n][0],
                                       ast.Import | ast.ImportFrom)]
            roots[path] = sorted({*roots.get(path, []), *names})
    missing = [p for p in policy["symbols"] if not tree.has(p)]
    if missing:
        raise Unmeasured(f"frozen symbol files missing at {ref}: {missing}")
    pol = policy
    if pol.get("knobs"):
        for p, spec in pol["knobs"].items():  # what a knob may read or call stays frozen itself
            if p.startswith("_") or not isinstance(spec, dict) or not tree.has(p):
                continue
            binds = _top_bindings(tree.module(p))
            extra = [n for n in [*(spec.get("frozen_refs") or []),
                                 *(spec.get("frozen_calls") or [])] if n in binds]
            roots[p] = sorted({*roots.get(p, []), *extra})
        missing_k = [f"{p}::{n}" for p, spec in pol["knobs"].items() if not p.startswith("_")
                     for n in _knob_names(spec if isinstance(spec, dict) else {})
                     if not tree.has(p) or n not in _top_bindings(tree.module(p))]
        if missing_k:  # item 18: a policy knob absent at this commit fails closed
            raise Unmeasured(f"knobs missing at {ref}: {missing_k[:5]}")
        for p, spec in pol["knobs"].items():  # EVERY knob is proved, reached or not: a knob a
            if p.startswith("_") or not isinstance(spec, dict):  # knob calls must be pure too
                continue
            for n in sorted(_knob_names(spec)):
                check_knob(tree, pol, p, n)
        _check_callers(tree, pol)
    out.update(closure(tree, roots, pol if pol.get("knobs") else None))
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
    if (set(b) != set(h) or b.get("grow_only") != h.get("grow_only")
            or b.get("hard_caps") != h.get("hard_caps")):
        return False
    for k in b:
        if k == "files":
            if [x for x in h[k] if x in b[k]] != b[k]:
                return False
        elif k == "symbols":
            for p, names in b[k].items():
                if [x for x in h[k].get(p, []) if x in names] != names:
                    return False
        elif k == "knobs":
            if not _knobs_tighten(b[k], h[k]):
                return False
        elif b[k] != h[k]:
            return False
    return True


def _narrower(b: Any, h: Any) -> bool:
    """A head knob rule at least as tight as the base's (item 19)."""
    if isinstance(b, dict) or isinstance(h, dict):
        return bool(b == h)
    if not (isinstance(b, list | tuple) and isinstance(h, list | tuple) and len(b) == len(h) == 2):
        return False
    (blo, bhi), (hlo, hhi) = b, h
    lo_ok = blo is None or (hlo is not None and hlo >= blo)
    hi_ok = bhi is None or (hhi is not None and hhi <= bhi)
    return bool(lo_ok and hi_ok)


def _knobs_tighten(b: Any, h: Any) -> bool:
    """Removing a knob, narrowing a range or a whitelist is TIGHTEN; anything else is not."""
    if not isinstance(b, dict) or not isinstance(h, dict) or not set(h) <= set(b):
        return False
    for path, hs in h.items():
        bs = b[path]
        if path.startswith("_"):
            continue
        if not isinstance(hs, dict) or not isinstance(bs, dict) or not set(hs) <= set(bs):
            return False
        hc, bc = hs.get("constants") or {}, bs.get("constants") or {}
        if not set(hc) <= set(bc) or not all(_narrower(bc[n], hc[n]) for n in hc):
            return False
        hf, bf = hs.get("functions") or {}, bs.get("functions") or {}
        if not set(hf) <= set(bf):
            return False
        for n, rule in hf.items():
            hcall = set((rule or {}).get("callers") or [])
            if not hcall <= set((bf[n] or {}).get("callers") or []):
                return False
        for lst in ("frozen_refs", "frozen_calls", "methods", "attrs"):
            if not set(hs.get(lst) or []) <= set(bs.get(lst) or []):
                return False
    return True


def cap_breaches(text: str | None, caps: list[list[Any]]) -> list[str]:
    """Rows of a JSON file (section, path, name, cap) that are missing or above their cap."""
    try:
        doc = json.loads(text or "")
    except ValueError:
        return ["unreadable"]
    out = []
    for section, path, name, cap in caps:
        v = ((doc.get(section) or {}).get(path) or {}).get(name)
        if isinstance(v, bool) or not isinstance(v, int | float) or v > cap:
            out.append(f"{path} {name} = {v!r} (published limit {cap})")
    return out


def is_new_test(base: Tree, path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return (path.startswith(("tests/", "desks/mt5/tests/")) and name.startswith("test_")
            and name.endswith(".py") and not base.has(path))


NEVER_CONTRACT = ("ops/box_git/trust_check.py", "ops/box_git/pin_writer.py",
                  "ops/box_git/protect.py", POLICY_PATH)


def _areas_for(path: str, contracts: dict[str, Any]) -> list[str]:
    if path in NEVER_CONTRACT:
        return []
    return [a for a, spec in contracts.items() if not a.startswith("_")
            and any(fnmatch.fnmatchcase(path, g) for g in spec.get("modules", []))]


def authority(git: Git, ref: str, spec: dict[str, Any]) -> str:
    """Hash of one area's authority constants (their static closure) at `ref`."""
    tree = Tree(git, ref)
    roots = {p: list(v) for p, v in (spec.get("authority") or {}).items()}
    for p in roots:
        if not tree.has(p):
            raise Unmeasured(f"authority file {p} missing at {ref}")
    return hashlib.sha256(json.dumps(closure(tree, roots), sort_keys=True).encode()).hexdigest()


def classify_full(git: Git, base: str, head: str, changed: list[str],
                  pol: dict[str, Any]) -> tuple[str, str, dict[str, str], list[str]]:
    """(class, why, T measured at head, contract areas). Measures each commit once."""
    try:
        changed = sorted({*changed, *git("diff", "--name-only", base, head).split()})
    except Exception as exc:  # an unreadable diff is unmeasured
        return "TRUST", f"unmeasured diff: {exc}"[:300], {}, []
    caps = {k: v for k, v in (pol.get("hard_caps") or {}).items() if not k.startswith("_")}
    try:
        head_tree = Tree(git, head)
        for path, rows in caps.items():
            bad = cap_breaches(head_tree.text(path), rows)
            if bad:
                return ("REFUSE", f"over a prop firm's published limit: {'; '.join(bad)}"[:300],
                        {}, [])
    except Exception as exc:  # unreadable caps refuse
        return "REFUSE", f"prop-firm caps unmeasured: {exc}"[:300], {}, []
    try:
        mb, mh = measure(git, base, pol), measure(git, head, pol)
    except Exception as exc:  # anything unmeasured is TRUST (Unmeasured included)
        return "TRUST", f"unmeasured: {exc}"[:300], {}, []
    moved = sorted(k for k in set(mb) | set(mh) if mb.get(k) != mh.get(k))
    try:  # another module reaching into a frozen one (`audit_gate.TRUSTED = ...`)
        frozen = {p: set(v) for p, v in pol["symbols"].items()}
        for k in mh:
            p, _, n = k.partition("::")
            if p.endswith(".py") and not n.startswith("__"):
                frozen.setdefault(p, set()).add(n)
        for path in changed:
            if path.endswith(".py") and head_tree.has(path):
                bad = foreign_stores(head_tree.module(path), frozen, head_tree)
                if bad:
                    return ("TRUST", f"{path} reaches into frozen code: {', '.join(bad)[:200]}",
                            mh, [])
    except Exception as exc:  # anything unmeasured is TRUST (Unmeasured included)
        return "TRUST", f"unmeasured: {exc}"[:300], mh, []
    if not moved:
        return "ORDINARY", "the trust set is unchanged", mh, []
    tb = Tree(git, base)
    contracts = pol.get("contracts") or {}
    code_moves: list[str] = []
    for key in moved:
        path, _, what = key.partition("::")
        if what == "*":
            old, new = tb.text(path), head_tree.text(path)
            if old is None and new is not None and is_new_test(tb, path):
                continue
            if old is not None and new is not None:
                if path in pol["grow_only"] and _grows(old, new):
                    continue
                if path == POLICY_PATH and _policy_grows(old, new):
                    continue
        code_moves.append(key)
    if not code_moves:
        return "TIGHTEN", "only grow-only additions inside the trust set: " + ", ".join(
            sorted({k.partition("::")[0] for k in moved}))[:250], mh, []
    areas: set[str] = set()
    for key in code_moves:
        path = key.partition("::")[0]
        hit = _areas_for(path, contracts) if path.endswith(".py") else []
        if not hit:
            return "TRUST", f"{key} changed inside the trust set", mh, []
        areas.update(hit)
    try:
        for a in sorted(areas):
            if authority(git, base, contracts[a]) != authority(git, head, contracts[a]):
                return "TRUST", f"area {a}: an authority constant changed", mh, []
    except Exception as exc:
        return "TRUST", f"unmeasured authority: {exc}"[:300], mh, []
    return ("CONTRACT", f"enforcement code of {', '.join(sorted(areas))} changed; authority "
            "constants identical; the pinned contract suites must pass", mh, sorted(areas))


def classify(git: Git, base: str, head: str, changed: list[str],
             policy: dict[str, Any] | None = None) -> tuple[str, str]:
    cls, why, _m, _a = classify_full(git, base, head, changed, policy or load_policy())
    return cls, why


def digest(m: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(m, sort_keys=True).encode()).hexdigest()


def verdict(git: Git, base: str, head: str, pin: dict[str, Any],
            policy: dict[str, Any] | None = None, changed: list[str] | None = None
            ) -> tuple[bool, str, str, str | None]:
    """THE ONE DECISION, used by the gate, the forge hook and the pin writer alike:
    (allowed, class, why, T hash at head). Owner authorizations and passed contract suites are
    read from the PIN (written only by the SYSTEM pin writer), keyed by the T hash they cover."""
    pol = policy or load_policy()
    pinned = str(pin.get("t_hash") or "")
    try:
        boot = pin.get("bootstrap_head") and head == pin["bootstrap_head"]
        boot_merge = pin.get("bootstrap_base") and base == pin["bootstrap_base"]
        if boot or boot_merge:
            ht = digest(measure(git, head, pol))
            if ht == pinned:
                return True, "BOOTSTRAP", "the install the owner requested", ht
        base_t = digest(measure(git, base, pol))
    except Exception as exc:
        return False, "TRUST", f"unmeasured: {exc}"[:300], None
    if base_t != pinned:
        return (False, "TRUST", f"the base's trust set {base_t[:12]} is not the pin "
                f"{pinned[:12]}", None)
    cls, why, mh, areas = classify_full(git, base, head, changed or [], pol)
    ht = digest(mh) if mh else None
    if cls == "REFUSE":
        return False, cls, why, ht
    if cls in ("ORDINARY", "TIGHTEN"):
        return True, cls, why, ht
    history = {str(h.get("t_hash")) for h in pin.get("history") or []}
    if ht and ht in history:
        return True, "RESTORE", f"returns to an already-pinned trust set {ht[:12]}", ht
    if cls == "CONTRACT" and ht and set(areas) <= set((pin.get("contract_ok") or {}).get(ht, [])):
        return True, cls, why + " (pinned suites passed)", ht
    if ht and ht in (pin.get("authorized") or {}):
        return True, "AUTHORIZED", f"the owner's AUTHORIZE TRUST covers {ht[:12]}", ht
    return False, cls, why, ht


def main(argv: list[str] | None = None) -> int:
    """`--classify REPO OLD NEW`: one JSON line {"class", "why"} for the boot mover (r18).

    The mover runs THIS file as copied from the CURRENT boot (never the packet's), against the
    policy beside it, so a packet can neither choose its checker nor its knobs (items 17, 21). Any
    error prints nothing and exits non-zero; the mover reads that as REFUSE."""
    import sys
    a = list(sys.argv[1:] if argv is None else argv)
    if len(a) != 4 or a[0] != "--classify":
        print("usage: trust_check.py --classify REPO OLD NEW", file=sys.stderr)
        return 2
    repo, old, new = a[1:]
    git = strict_git("git", "-c", "safe.directory=*", "-c", "core.fsmonitor=false",
                     "-c", "core.hooksPath=NUL", "-C", repo)
    changed = git("diff", "--no-renames", "--name-only", old, new).split()
    cls, why = classify(git, old, new, changed, load_policy())
    print(json.dumps({"class": cls, "why": why}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
