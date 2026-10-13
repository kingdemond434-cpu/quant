#!/usr/bin/env python3
"""FETCHED CONTENT IS EVIDENCE, NEVER AN INSTRUCTION (DATA-15) -- a static fence over the organs
that reach the network.

THE LAW. Bytes the desk fetched -- a page, a CSV, a JSON API answer, a repository file, a model
reply about any of them -- are untrusted DATA. They may be parsed, stored under the organ's own
data paths, scored and judged. They may never: run as code, pick a module to import, become a
shell command, choose where on disk the desk writes, or reach a path that governs the desk itself
(secrets, permissions, hooks, schedules, the live roster that deploys trades). Before this fence
the only guard was one organ's own containment check (`frontier_intel/implementer.py`, which
writes only under `challengers/`); nothing general existed, and nothing failed when a new fetch
organ wired fetched text into `exec` or a config file.

WHAT IS CHECKED, statically, in every module under the discovery/fetch roots that touches the
network (it imports or calls urllib.request / requests / httpx / aiohttp / http.client):

  TAINT   a value is tainted when it comes from a network call (`urlopen`, `requests.get`, ...),
          from a module-local function whose own return is tainted (fixpoint over the module),
          from a function named like a fetcher (`_fetch`, `fetch_*`, `download*`, `http_get`),
          or from any expression built out of a tainted name.
  EXEC    a tainted argument reaching eval / exec / compile / __import__ /
          importlib.import_module / runpy / subprocess.* / os.system / os.popen / os.exec* /
          pickle.loads / marshal.loads / pd.read_pickle / joblib.load /
          np.load(allow_pickle=True) is a breach.
  WRITE   a write whose PATH is tainted is a breach (fetched bytes chose the destination), and so
          is any write, chmod or replace by one of these organs onto a PROTECTED path -- whatever
          the data -- because a discovery organ has no business there at all.

Intra-module and conservative by construction: it can miss a flow that crosses modules through a
file (the next organ then reads data, and is itself checked), and it never passes a flow it can
see. There is NO allowlist: a breach is fixed in the organ, never excused here.

    python scripts/check_untrusted_content.py [--json] [--root PATH]
"""
from __future__ import annotations

import argparse
import ast
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

#: The discovery and fetch organs: every network-touching module under these roots is checked.
SCAN_ROOTS: tuple[str, ...] = (
    "desks/mt5/research", "desks/mt5/frontier_intel", "libs/data", "libs/research", "libs/moat",
)
_NET_MARKER = re.compile(r"^\s*(?:import|from)\s[^\n]*\b(?:requests|httpx|aiohttp|urllib3|"
                         r"urllib\.request|http\.client)\b|\burlopen\(|"
                         r"\b_fetch\w*\(|\bfetch_(?:url|page|bytes|json|text)\w*\(|"
                         r"\bhttp_get\(|\bget_url\(", re.MULTILINE)
#: A path whose joined string constants contain one of these is PROTECTED: secrets, permission
#: and settings files, hooks, schedules, governing documents, and the roster that deploys trades.
PROTECTED_FRAGMENTS: tuple[str, ...] = (
    "data/secrets", "secrets/", ".claude/", "settings.json", "settings.local.json", "CLAUDE.md",
    "ops/", ".github/", "githooks", "crontab", "principal_doctrine", "LAWS.md", ".env",
    "sleeves.json", "ALLOCATOR_SOVEREIGN", "MARGIN_CLAUSE_DISABLED", "RECORDERS_OFF",
    "authorized_keys", ".ssh/", ".gitconfig", "pyproject.toml",
)

_NET_ATTR_OWNERS = frozenset({"requests", "httpx", "aiohttp", "urllib3"})
_NET_CALLS = frozenset({"urlopen", "urlretrieve"})
_FETCHER_NAME = re.compile(r"^_*(fetch|download|http_get|get_url|read_url|scrape|crawl)"
                           r"(_|$|[a-z])", re.IGNORECASE)
_EXEC_NAMES = frozenset({"eval", "exec", "compile", "__import__"})
_EXEC_ATTRS: dict[str, frozenset[str]] = {
    "importlib": frozenset({"import_module"}),
    "runpy": frozenset({"run_path", "run_module"}),
    "subprocess": frozenset({"run", "Popen", "call", "check_call", "check_output",
                             "getoutput", "getstatusoutput"}),
    "os": frozenset({"system", "popen", "execv", "execve", "execvp", "execl", "execlp",
                     "spawnv", "spawnl", "startfile"}),
    "pickle": frozenset({"loads", "load"}),
    "marshal": frozenset({"loads", "load"}),
    "builtins": frozenset({"eval", "exec", "compile", "__import__"}),
}
#: Modules whose attributes `getattr(<module>, "<name>")` can turn into code execution. A dynamic
#: lookup on one of them hides the callee from a check keyed on names, so it is resolved when the
#: name is a constant and is a breach on its own when it is not (the name could be fetched).
_DYNAMIC_OWNERS = frozenset({"builtins", "__builtins__", "os", "subprocess", "importlib",
                             "runpy", "pickle", "marshal"})
_WRITE_METHODS = frozenset({"write_text", "write_bytes", "touch", "mkdir", "chmod",
                            "symlink_to", "hardlink_to"})
_WRITE_FUNCS_FIRST_ARG = re.compile(r"(^|_)(atomic|write|dump|save|persist)", re.IGNORECASE)
_PATH_SECOND_ARG = {("os", "replace"), ("os", "rename"), ("shutil", "copy"),
                    ("shutil", "copy2"), ("shutil", "copyfile"), ("shutil", "move")}
_PATH_FIRST_ARG = {("os", "chmod"), ("os", "chown"), ("os", "remove"), ("os", "unlink"),
                   *((np_, f) for np_ in ("numpy", "np")
                     for f in ("save", "savez", "savez_compressed", "savetxt"))}
#: DataFrame / array writers whose FIRST argument (or path keyword) is the destination (auditor
#: MUST on #292: `df.to_csv(fetched_path)` and `arr.tofile(...)` were not seen as writes).
_FIRST_ARG_WRITE_METHODS = frozenset({"to_csv", "to_parquet", "to_pickle", "to_json",
                                      "to_feather", "to_excel", "to_hdf", "to_stata", "tofile"})
_PATH_KEYWORDS = ("path_or_buf", "path", "fname", "file", "filename", "excel_writer")
#: Memory maps opened for writing create or overwrite their file: `mode` w / w+ / r+ / c.
_MEMMAP_CALLS = frozenset({"open_memmap", "memmap"})
#: Deserialisers that run code from the bytes they read: a fetched argument is an EXEC.
_PICKLE_READERS = frozenset({"read_pickle"})
_PICKLE_LOAD_OWNERS = frozenset({"joblib", "dill", "cloudpickle", "shelve"})


def _dotted(node: ast.AST) -> tuple[str, str]:
    """(owner, attr) for `owner.attr(...)`, ("", name) for `name(...)`."""
    if isinstance(node, ast.Name):
        return "", node.id
    if isinstance(node, ast.Attribute):
        base = node.value
        owner = base.id if isinstance(base, ast.Name) else (
            base.attr if isinstance(base, ast.Attribute) else "")
        return owner, node.attr
    return "", ""


def _is_exec(owner: str, attr: str, call: ast.Call | None = None) -> bool:
    if (not owner and attr in _EXEC_NAMES) or attr in _EXEC_ATTRS.get(owner, ()):
        return True
    # PICKLE BY ANOTHER NAME (auditor MUST on #292): `pd.read_pickle`, `joblib.load` and
    # `np.load(..., allow_pickle=True)` all execute code carried in the bytes they read.
    if attr in _PICKLE_READERS or (attr in ("load", "loads", "open")
                                   and owner in _PICKLE_LOAD_OWNERS):
        return True
    if call is not None and attr == "load" and owner in ("numpy", "np"):
        ap = next((k.value for k in call.keywords if k.arg == "allow_pickle"), None)
        return ap is not None and not (isinstance(ap, ast.Constant) and ap.value is False)
    return False


def _dynamic_lookup(node: ast.Call, mod: _Module) -> str | None:
    """`getattr(<exec-capable module>, name)`: the reason it is a breach, or None.

    A CONSTANT naming an exec-capable attribute is a breach on sight (there is no reason for a
    fetch organ to reach `exec` by string); a NON-constant name on one of these modules is a
    breach too, because the static view cannot rule out that fetched text chose it."""
    if _dotted(node.func) not in (("", "getattr"), ("builtins", "getattr")) or len(node.args) < 2:
        return None
    owner = mod._module_of(node.args[0])
    if owner not in _DYNAMIC_OWNERS:
        return None
    name = node.args[1]
    if isinstance(name, ast.Constant) and isinstance(name.value, str):
        key = "builtins" if owner == "__builtins__" else owner
        if _is_exec(key, name.value):
            return f"getattr({owner}, {name.value!r}) reaches an exec-capable callee by string"
        return None
    return f"getattr({owner}, <non-constant>) lets a computed name choose the callee"


def _names(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _target_names(t: ast.AST) -> set[str]:
    """The names an assignment target binds. `cache[key] = v` taints `cache`, never `key`."""
    if isinstance(t, ast.Name):
        return {t.id}
    if isinstance(t, (ast.Tuple, ast.List)):
        return set().union(*(_target_names(e) for e in t.elts)) if t.elts else set()
    if isinstance(t, ast.Starred):
        return _target_names(t.value)
    if isinstance(t, (ast.Subscript, ast.Attribute)):
        base: ast.AST = t
        while isinstance(base, (ast.Subscript, ast.Attribute)):
            base = base.value
        return {base.id} if isinstance(base, ast.Name) else set()
    return set()


_SANITISER = re.compile(r"(slug|safe_?name|sanitis|sanitiz|(^|_)stem$|hexdigest|^quote|"
                        r"basename|secure_filename|^sha\d*$|^md5$)", re.IGNORECASE)


def _strings(node: ast.AST, consts: dict[str, str]) -> str:
    """Every string constant inside a path expression, joined, with module constants resolved
    one hop -- `SECRETS / "key"` reads as `data/secrets/key` when SECRETS is a module constant."""
    parts: list[str] = []
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            parts.append(n.value)
        elif isinstance(n, ast.Name) and n.id in consts:
            parts.append(consts[n.id])
    return "/".join(parts).replace("\\", "/").replace("//", "/")


def _protected(text: str) -> str | None:
    """The protected fragment a path's text carries, anchored at a path-segment boundary so
    `federation_ops/` is not `ops/` and `my.envoy` is not `.env`."""
    for frag in PROTECTED_FRAGMENTS:
        if re.search(r"(^|/)" + re.escape(frag) + (r"" if frag.endswith("/") else r"($|/|\b)"),
                     text):
            return frag
    return None


#: Reported by name, never failing: a fixed directory with a fetched-derived leaf stays inside the
#: organ's own store unless the leaf carries a separator, which the static view cannot rule out.
WARNINGS = frozenset({"LEAF_FROM_FETCHED"})


def _import_aliases(tree: ast.AST) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    """(module aliases, imported names) from every Import / ImportFrom in the module.

    ALIASES DEFEATED THE FIRST BUILD (auditor HOLD on #292): the callee was keyed on the literal
    owner name, so `import subprocess as sp; sp.run(x)` and `from subprocess import run; run(x)`
    were invisible. `import a.b as c` maps c -> "a.b" (its last part is the owner the tables key
    on); `import a.b` binds `a`; `from m import f as g` maps g -> ("m", "f")."""
    mods: dict[str, str] = {}
    names: dict[str, tuple[str, str]] = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.asname:
                    mods[a.asname] = a.name
                else:
                    head = a.name.split(".", 1)[0]
                    mods.setdefault(head, head)
        elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
            for a in n.names:
                if a.name == "*":
                    continue
                names[a.asname or a.name] = (n.module, a.name)
    return mods, names


def _owner_key(module: str) -> str:
    """The table key for a dotted module: `urllib.request` -> `request` is wrong for the net
    tables, so a few dotted owners keep their full name; everything else keys on its last part."""
    return module.rsplit(".", 1)[-1] if module not in ("urllib.request", "http.client") \
        else module


class _Module:
    def __init__(self, tree: ast.Module) -> None:
        self.tree = tree
        self.mod_alias, self.name_alias = _import_aliases(tree)
        #: local names bound to an exec-capable callee: `run = subprocess.run`,
        #: `f = getattr(builtins, "exec")`, `x = sp.Popen` -- filled below, after resolution.
        self.callee_alias: dict[str, tuple[str, str]] = {}
        self.consts: dict[str, str] = {}
        for _ in range(2):                                   # resolve chained constants
            for stmt in tree.body:
                if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                    targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                    if stmt.value is None:
                        continue
                    text = _strings(stmt.value, self.consts)
                    for t in targets:
                        if isinstance(t, ast.Name) and text:
                            self.consts[t.id] = text
        for n in ast.walk(tree):
            if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                    and isinstance(n.targets[0], ast.Name):
                owner, attr = self.resolve(n.value)
                if attr and (owner, attr) != ("", "") and _is_exec(owner, attr):
                    self.callee_alias[n.targets[0].id] = (owner, attr)
        self.funcs = {n.name: n for n in ast.walk(tree)
                      if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.tainted_funcs: set[str] = {f for f in self.funcs if _FETCHER_NAME.match(f)}
        for _ in range(4):                                   # return-taint fixpoint
            grew = False
            for name, fn in self.funcs.items():
                if name in self.tainted_funcs:
                    continue
                tainted = self.taint_of(fn)
                for r in ast.walk(fn):
                    if isinstance(r, ast.Return) and r.value is not None \
                            and self.is_tainted(r.value, tainted):
                        self.tainted_funcs.add(name)
                        grew = True
                        break
            if not grew:
                break

    def resolve(self, func: ast.AST) -> tuple[str, str]:
        """(owner, attr) of a callee with import aliases, local callee aliases and constant
        `getattr(<module>, "<name>")` resolved. ("", name) for a plain builtin name."""
        if isinstance(func, ast.Call) and _dotted(func.func) in (("", "getattr"),
                                                                  ("builtins", "getattr")) \
                and len(func.args) >= 2:
            owner = self._module_of(func.args[0])
            name = func.args[1]
            if owner and isinstance(name, ast.Constant) and isinstance(name.value, str):
                return owner, name.value
            return "", ""
        if isinstance(func, ast.Name):
            if func.id in self.callee_alias:
                return self.callee_alias[func.id]
            if func.id in self.name_alias:
                module, attr = self.name_alias[func.id]
                return _owner_key(module), attr
            return "", func.id
        if isinstance(func, ast.Attribute):
            owner = self._module_of(func.value)
            if owner:
                return owner, func.attr
            return _dotted(func)
        return "", ""

    def _module_of(self, node: ast.AST) -> str:
        """The module key a name or dotted expression denotes, through import aliases."""
        if isinstance(node, ast.Name):
            if node.id in self.mod_alias:
                return _owner_key(self.mod_alias[node.id])
            if node.id in self.name_alias:          # `from os import path` -> os.path
                module, attr = self.name_alias[node.id]
                return _owner_key(f"{module}.{attr}")
            return node.id if node.id == "__builtins__" else ""
        if isinstance(node, ast.Attribute):
            base = self._module_of(node.value)
            if base:
                return _owner_key(f"{base}.{node.attr}")
        return ""

    def source_call(self, node: ast.Call) -> bool:
        owner, attr = self.resolve(node.func)
        if attr in _NET_CALLS:
            return True
        if owner in _NET_ATTR_OWNERS:
            return True
        raw_owner, raw_attr = _dotted(node.func)
        return raw_attr in self.tainted_funcs and (not raw_owner or raw_owner in ("self", "cls"))

    def is_tainted(self, node: ast.AST, tainted: set[str]) -> bool:
        """Does fetched content flow into this expression? A sanitiser call (`_slug`, `_stem`,
        `hexdigest`, `quote`, ...) ends the flow: what comes out of it cannot carry a separator."""
        stack = [node]
        while stack:
            n = stack.pop()
            if isinstance(n, ast.Call):
                if _SANITISER.search(_dotted(n.func)[1] or ""):
                    continue
                if self.source_call(n):
                    return True
            if isinstance(n, ast.Name) and n.id in tainted:
                return True
            stack.extend(ast.iter_child_nodes(n))
        return False

    def taint_of(self, fn: ast.AST) -> set[str]:
        tainted: set[str] = set()
        for _ in range(3):                                   # loops carry taint backwards
            before = len(tainted)
            for n in ast.walk(fn):
                value: ast.AST | None = None
                targets: list[ast.AST] = []
                if isinstance(n, ast.Assign):
                    value, targets = n.value, list(n.targets)
                elif isinstance(n, (ast.AnnAssign, ast.AugAssign)) and n.value is not None:
                    value, targets = n.value, [n.target]
                elif isinstance(n, (ast.For, ast.AsyncFor)):
                    if _elementwise(n.target, n.iter, self, tainted):
                        continue
                    value, targets = n.iter, [n.target]
                elif isinstance(n, ast.withitem) and n.optional_vars is not None:
                    value, targets = n.context_expr, [n.optional_vars]
                elif isinstance(n, ast.NamedExpr):
                    value, targets = n.value, [n.target]
                elif isinstance(n, ast.comprehension):
                    value, targets = n.iter, [n.target]
                if value is not None and self.is_tainted(value, tainted):
                    for t in targets:
                        tainted |= _target_names(t)
            if len(tainted) == before:
                break
        return tainted


def _elementwise(target: ast.AST, it: ast.AST, mod: _Module, tainted: set[str]) -> bool:
    """`for a, b in ((X, y), (Z, w))`: taint position by position, not the whole tuple. Returns
    True when it handled the loop (so the coarse rule is skipped)."""
    if not (isinstance(target, ast.Tuple) and isinstance(it, (ast.Tuple, ast.List))):
        return False
    rows = it.elts
    if not rows or not all(isinstance(r, ast.Tuple) and len(r.elts) == len(target.elts)
                           for r in rows):
        return False
    for i, t in enumerate(target.elts):
        if any(mod.is_tainted(r.elts[i], tainted) for r in rows):  # type: ignore[attr-defined]
            tainted |= _target_names(t)
    return True


def _path_like(node: ast.AST, consts: dict[str, str]) -> bool:
    """Does this argument look like a PATH rather than a payload? A module path constant, a
    `/`-joined expression, a `Path(...)`/`os.path.join(...)` call, or a string with a separator
    or a file extension."""
    if isinstance(node, ast.Name):
        return node.id in consts and ("/" in consts[node.id] or "." in consts[node.id])
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return True
    if isinstance(node, ast.Call):
        owner, attr = _dotted(node.func)
        return attr in ("Path", "with_suffix", "with_name", "PurePath") or (
            attr == "join" and owner == "path")
    if isinstance(node, (ast.Constant, ast.JoinedStr)):
        text = _strings(node, consts)
        return "/" in text or bool(re.search(r"\.[a-z]{2,5}$", text))
    return False


def _bases_of(node: ast.AST) -> list[ast.AST]:
    """The ROOT of a path expression: the leftmost operand of a `/` chain or the first argument
    of Path(...)/os.path.join(...), through both branches of a conditional expression."""
    if isinstance(node, ast.IfExp):
        return [*_bases_of(node.body), *_bases_of(node.orelse)]
    return [_base_of(node)]


def _assignments(scope: ast.AST) -> dict[str, list[ast.AST]]:
    out: dict[str, list[ast.AST]] = {}
    for n in ast.walk(scope):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    out.setdefault(t.id, []).append(n.value)
        elif isinstance(n, ast.AnnAssign) and n.value is not None \
                and isinstance(n.target, ast.Name):
            out.setdefault(n.target.id, []).append(n.value)
    return out


def _root_tainted(path: ast.AST, scope: ast.AST, mod: _Module, tainted: set[str],
                  depth: int = 0) -> bool:
    """Is the ROOT of this path fetched? A local name is followed to what it was assigned
    (`ledger = SHADOW_DIR / f"..."` has a fixed root even when its leaf is fetched)."""
    assigned = _assignments(scope) if depth < 3 else {}
    for base in _bases_of(path):
        if isinstance(base, ast.Name) and base.id in assigned:
            if any(_root_tainted(v, scope, mod, tainted, depth + 1)
                   for v in assigned[base.id]):
                return True
        elif mod.is_tainted(base, tainted):
            return True
    return False


def _base_of(node: ast.AST) -> ast.AST:
    while True:
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            node = node.left
        elif isinstance(node, ast.Call) and node.args and (
                _dotted(node.func)[1] in ("Path", "PurePath")
                or _dotted(node.func) == ("path", "join")):
            node = node.args[0]
        else:
            return node


def _write_path(call: ast.Call, mod: _Module | None = None) -> tuple[ast.AST | None, str]:
    """The PATH expression a call writes to, with the kind of write, or (None, "").
    `mod` resolves import aliases (`from os import replace`, `import shutil as sh`)."""
    raw_owner, raw_attr = _dotted(call.func)
    owner, attr = mod.resolve(call.func) if mod is not None else (raw_owner, raw_attr)
    if (owner, attr) not in _PATH_SECOND_ARG | _PATH_FIRST_ARG:
        owner, attr = raw_owner, raw_attr          # everything else keys on the written name
    if not owner and attr == "open" and len(call.args) >= 1:
        mode = call.args[1] if len(call.args) > 1 else next(
            (k.value for k in call.keywords if k.arg == "mode"), None)
        if isinstance(mode, ast.Constant) and isinstance(mode.value, str) \
                and set(mode.value) & set("wax+"):
            return call.args[0], "open-for-write"
        return None, ""
    if (owner, attr) in _PATH_SECOND_ARG:
        return (call.args[1], f"{owner}.{attr}") if len(call.args) >= 2 else (None, "")
    if (owner, attr) in _PATH_FIRST_ARG:
        return (call.args[0], f"{owner}.{attr}") if call.args else (None, "")
    if attr in _MEMMAP_CALLS:
        mode = next((k.value for k in call.keywords if k.arg == "mode"),
                    call.args[1] if len(call.args) > 1 else None)
        writes = mode is not None and not (
            isinstance(mode, ast.Constant) and isinstance(mode.value, str)
            and not set(mode.value) & set("wc+"))
        target = call.args[0] if call.args else next(
            (k.value for k in call.keywords if k.arg in _PATH_KEYWORDS), None)
        return (target, f"{attr}(mode=w)") if writes and target is not None else (None, "")
    if isinstance(call.func, ast.Attribute) and attr in _FIRST_ARG_WRITE_METHODS:
        target = call.args[0] if call.args else next(
            (k.value for k in call.keywords if k.arg in _PATH_KEYWORDS), None)
        return (target, f".{attr}()") if target is not None else (None, "")
    if isinstance(call.func, ast.Attribute):
        if attr == "open":
            mode = call.args[0] if call.args else next(
                (k.value for k in call.keywords if k.arg == "mode"), None)
            if isinstance(mode, ast.Constant) and isinstance(mode.value, str) \
                    and set(mode.value) & set("wax+"):
                return call.func.value, "Path.open-for-write"
            return None, ""
        if attr in _WRITE_METHODS:
            return call.func.value, f"Path.{attr}"
    if (owner, attr) in _PATH_SECOND_ARG and len(call.args) >= 2:
        return call.args[1], f"{owner}.{attr}"
    if (owner, attr) in _PATH_FIRST_ARG and call.args:
        return call.args[0], f"{owner}.{attr}"
    if not owner and _WRITE_FUNCS_FIRST_ARG.search(attr) and call.args:
        return call, f"{attr}()"            # helper: its path-like arguments are resolved below
    return None, ""


def check_source(text: str, rel: str) -> list[dict[str, Any]]:
    """Every breach in one module's source. Pure: no I/O."""
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [{"file": rel, "line": exc.lineno or 0, "kind": "UNPARSEABLE", "severity": "breach",
                 "detail": f"cannot be checked: {exc.msg} -- counts as a breach, never a pass"}]
    mod = _Module(tree)
    out: list[dict[str, Any]] = []
    scopes: list[ast.AST] = [*mod.funcs.values(), tree]
    seen: set[tuple[int, str]] = set()
    for scope in scopes:
        tainted = mod.taint_of(scope) if scope is not tree else set()
        body = scope.body if isinstance(scope, ast.Module) else [scope]
        for node in (n for b in body for n in ast.walk(b)):
            if not isinstance(node, ast.Call):
                continue
            dyn = _dynamic_lookup(node, mod)
            if dyn:
                key = (node.lineno, "DYN")
                if key not in seen:
                    seen.add(key)
                    out.append({"file": rel, "line": node.lineno, "kind": "DYNAMIC_EXEC_LOOKUP",
                                "severity": "breach", "detail": dyn})
                continue
            owner, attr = mod.resolve(node.func)
            if owner == "__builtins__":
                owner = "builtins"
            args = [*node.args, *(k.value for k in node.keywords)]
            is_exec = _is_exec(owner, attr, node)
            if is_exec and any(mod.is_tainted(a, tainted) for a in args):
                key = (node.lineno, "EXEC")
                if key not in seen:
                    seen.add(key)
                    out.append({"file": rel, "line": node.lineno, "kind": "FETCHED_TO_EXEC", "severity": "breach",
                                "detail": f"fetched content reaches {owner + '.' if owner else ''}"
                                          f"{attr}(): it would run as code or a command"})
                continue
            path, how = _write_path(node, mod)
            if path is None:
                continue
            # a write helper (path is the call itself): resolve its path-like arguments
            paths = [a for a in args if _path_like(a, mod.consts)] if path is node else [path]
            for pth in paths:
                frag = _protected(_strings(pth, mod.consts))
                if frag:
                    kind, detail = "PROTECTED_PATH_WRITE", (
                        f"{how} onto a protected path (matched {frag!r}): a fetch organ never "
                        "writes secrets, permissions, hooks, schedules or the live roster")
                elif not mod.is_tainted(pth, tainted):
                    continue
                elif _root_tainted(pth, scope, mod, tainted):
                    kind, detail = "FETCHED_CHOOSES_PATH", (
                        f"{how} to a destination whose ROOT is computed from fetched content: "
                        "the bytes would choose where the desk writes")
                else:
                    kind, detail = "LEAF_FROM_FETCHED", (
                        f"{how} under a fixed directory with a file name derived from fetched "
                        "content; it must be sanitised (no separator, no '..') before the join")
                key = (node.lineno, kind)
                if key not in seen:
                    seen.add(key)
                    out.append({"file": rel, "line": node.lineno, "kind": kind,
                                "severity": "warning" if kind in WARNINGS else "breach",
                                "detail": detail})
    return out


#: THE LLM SEATS' PROMPT BUILDERS THAT CARRY FETCHED TEXT (auditor HOLD on #292: the fence
#: checked code paths and never reached prompt construction). Each must route that text through
#: `libs.research.untrusted` (`wrap` for bodies, `fenced_line` for short fields): delimited,
#: labelled as data, control sequences neutralised. A builder that stops doing so -- or that is
#: renamed or moved without this list following -- is a breach, never a silent pass.
SEAT_PROMPT_BUILDERS: tuple[tuple[str, str], ...] = (
    ("libs/research/public_strategy_hunter.py", "extraction_prompt"),
    ("libs/research/event_factors_llm.py", "llm_tags"),
    ("libs/ops/deepseek_cycle.py", "_build_prompt"),
    ("libs/research/proposer_seat.py", "build_prompt"),
    # auditor MUST on #292: forum claims of up to 1,200 chars and frontier cards reached a seat
    # bare; the collector author's reply is code this desk executes.
    ("desks/mt5/research/deepening_worker.py", "task_text"),
    ("desks/mt5/frontier_intel/implementer.py", "specification"),
    ("scripts/collector_author.py", "author_prompt"),
)

#: EVERY OTHER MODULE THAT CALLS AN LLM SEAT, with the reason no fetched text reaches its prompt.
#: `check_seat_call_sites` fails on a module that calls a seat and is neither a builder's home
#: above nor named here: a new seat caller must be classified before it ships.
SEAT_CALL_EXCLUSIONS: dict[str, str] = {
    "desks/mt5/research/scientist_tournament.py":
        "evidence blocks are desk artifacts (cells, verdicts, ledgers) and other seats' replies",
    "libs/research/second_family.py":
        "family briefs and the desk's own candidate rows; nothing fetched",
    "scripts/breadth_expander.py": "desk coverage state and the miners' own inventory",
    "scripts/capacity_test.py": "a synthetic payload sized to probe a seat's context window",
    "scripts/check_free_roster.py": "a fixed canary prompt",
    "scripts/deep_review.py": "one file of this repository for a code review",
    "scripts/hypothesis_generator.py": "the graveyard and family registry: desk-authored",
    "scripts/kimi_hunter.py": ("desk-authored wave briefs, coverage state and the previous "
                               "wave's model output; no page text is fetched into the prompt"),
    "scripts/meta_architect.py": "the desk's organ inventory and its own reports",
    "scripts/model_upgrade.py": "fixed capability probes",
    "scripts/run_external_panel.py": ("the sanitized cold-audit dossier of this repository; "
                                      "its prompt already labels replies untrusted"),
    "scripts/run_micro_audit.py": "the last 24 h of this repository's diff",
    "scripts/run_strategic_director.py": "a dossier assembled from the desk's own artifacts",
    "scripts/run_survivor_panel.py": "the desk's measured negative-result ledger",
}
#: Roots scanned for seat call sites, and the callee names that reach a seat.
SEAT_CALL_ROOTS: tuple[str, ...] = ("libs", "desks/mt5", "scripts")
_SEAT_CALL_NAMES = frozenset({"_ask", "chat"})


def seat_call_sites(root: Path = ROOT) -> dict[str, list[int]]:
    """rel path -> lines of every `llm_seat.chat` / `<seat>.chat` / `chat(...)` / `_ask(...)`
    call outside tests and retired code."""
    out: dict[str, list[int]] = {}
    for r in SEAT_CALL_ROOTS:
        base = root / r
        if not base.exists():
            continue
        for p in sorted(base.rglob("*.py")):
            rel = p.relative_to(root).as_posix()
            parts = set(p.relative_to(root).parts)
            if parts & {"tests", "_retired", "__pycache__"} or p.name.startswith("test_"):
                continue
            try:
                text = p.read_text("utf-8", errors="ignore")
            except OSError:
                continue
            if "chat(" not in text and "_ask(" not in text:
                continue
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            lines = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Call)
                     and _dotted(n.func)[1] in _SEAT_CALL_NAMES]
            if lines:
                out[rel] = lines
    return out


def check_seat_call_sites(root: Path = ROOT) -> list[dict[str, Any]]:
    """A breach for every seat-calling module that is neither home to a listed prompt builder
    nor a declared exclusion with its reason."""
    homes = {rel for rel, _ in SEAT_PROMPT_BUILDERS} | {"libs/ops/llm_seat.py"}
    return [{"file": rel, "line": lines[0], "kind": "UNCLASSIFIED_SEAT_CALL",
             "severity": "breach",
             "detail": (f"{len(lines)} LLM seat call(s) in a module that is neither a listed "
                        f"SEAT_PROMPT_BUILDERS home nor in SEAT_CALL_EXCLUSIONS with a reason")}
            for rel, lines in sorted(seat_call_sites(root).items())
            if rel not in homes and rel not in SEAT_CALL_EXCLUSIONS]
_FENCE_CALLS = frozenset({"wrap", "fenced_line"})
UNMEASURED_SEATS = "UNMEASURED: no seat prompt builder under this root"


def check_seat_prompts(root: Path = ROOT,
                       builders: Iterable[tuple[str, str]] = SEAT_PROMPT_BUILDERS
                       ) -> list[dict[str, Any]]:
    """A breach for every listed seat prompt builder that does not fence the text it carries."""
    out: list[dict[str, Any]] = []
    builders = list(builders)
    if not any((root / rel).exists() for rel, _ in builders):
        return out          # a fixture tree, not a checkout: `check` reports this UNMEASURED
    for rel, fn_name in builders:
        p = root / rel
        try:
            tree = ast.parse(p.read_text("utf-8"))
        except (OSError, SyntaxError) as exc:
            out.append({"file": rel, "line": 0, "kind": "UNFENCED_SEAT_PROMPT",
                        "severity": "breach",
                        "detail": f"{fn_name}: builder unreadable ({type(exc).__name__}); an "
                                  f"unchecked prompt counts as unfenced"})
            continue
        fn = next((n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef,
                                                                 ast.AsyncFunctionDef))
                   and n.name == fn_name), None)
        if fn is None:
            out.append({"file": rel, "line": 0, "kind": "UNFENCED_SEAT_PROMPT",
                        "severity": "breach",
                        "detail": f"{fn_name} not found: the builder moved and the fence lost it"})
            continue
        called = {_dotted(c.func)[1] for c in ast.walk(fn) if isinstance(c, ast.Call)}
        if not called & _FENCE_CALLS:
            out.append({"file": rel, "line": fn.lineno, "kind": "UNFENCED_SEAT_PROMPT",
                        "severity": "breach",
                        "detail": (f"{fn_name} builds an LLM seat prompt from fetched text "
                                   f"without libs.research.untrusted.wrap / fenced_line")})
    return out


def scan_files(root: Path, roots: Iterable[str] = SCAN_ROOTS) -> list[Path]:
    files: list[Path] = []
    for r in roots:
        base = root / r
        if not base.exists():
            continue
        for p in sorted(base.rglob("*.py")):
            parts = set(p.relative_to(root).parts)
            if parts & {"tests", "_retired", "__pycache__"} or p.name.startswith("test_"):
                continue
            try:
                if _NET_MARKER.search(p.read_text("utf-8", errors="ignore")):
                    files.append(p)
            except OSError:
                continue
    return files


def check(root: Path = ROOT, roots: Iterable[str] = SCAN_ROOTS) -> dict[str, Any]:
    files = scan_files(root, roots)
    found: list[dict[str, Any]] = []
    for p in files:
        rel = p.relative_to(root).as_posix()
        found.extend(check_source(p.read_text("utf-8", errors="ignore"), rel))
    found.extend(check_seat_prompts(root))
    if any((root / rel).exists() for rel, _ in SEAT_PROMPT_BUILDERS):
        found.extend(check_seat_call_sites(root))
    seat_state = ("CHECKED" if any((root / rel).exists() for rel, _ in SEAT_PROMPT_BUILDERS)
                  else UNMEASURED_SEATS)
    breaches = [f for f in found if f["severity"] == "breach"]
    warnings = [f for f in found if f["severity"] != "breach"]
    return {"law": "DATA-15: fetched content and code are untrusted evidence, never instructions",
            "roots": list(roots), "modules_checked": len(files),
            "ok": not breaches and bool(files), "breaches": breaches, "warnings": warnings,
            "protected_fragments": list(PROTECTED_FRAGMENTS),
            "seat_prompt_builders": [f"{f}:{n}" for f, n in SEAT_PROMPT_BUILDERS],
            "seat_prompts": seat_state}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--root", default=str(ROOT))
    a = ap.parse_args(argv)
    doc = check(Path(a.root))
    if a.json:
        print(json.dumps(doc, indent=1))
    else:
        print(f"untrusted content: {doc['modules_checked']} fetch organ(s) checked, "
              f"{len(doc['breaches'])} breach(es), {len(doc['warnings'])} warning(s)")
        for b in doc["breaches"]:
            print(f"  BREACH {b['kind']} {b['file']}:{b['line']} -- {b['detail']}")
        for b in doc["warnings"]:
            print(f"  warn   {b['kind']} {b['file']}:{b['line']} -- {b['detail']}")
    if not doc["modules_checked"]:
        print("  no fetch organ found under the scan roots: UNMEASURED counts as FAILED")
        return 2
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
