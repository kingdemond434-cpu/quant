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
        elif b[k] != h[k]:
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
