#!/usr/bin/env python3
"""Replay-shadow's RESEARCH REACH: measure research closure files the E8 grid never runs.

replay_shadow.compare() marks a changed money-path file UNMEASURED when neither replay imported it.
Research registries (alpha_clusters, orthogonal_sweep, ...) are in the static closure of the box's
entry points, but the E8 grid never executes them, so every new strategy family took the manual
path. This module MEASURES MORE AND EXEMPTS NOTHING: a file leaves UNMEASURED only by one of two
proofs, both recorded in the report (ops/release spec REPLAY_RESEARCH_REACH, the Auditor's six
conditions of 2026-11-03 18:20Z):

1. SUPERSET (AST proof, then the slice). The file's module body is AST-identical to the base's
   except for module-level registry literals that only GREW: new dict keys, new set members,
   members appended to a tuple or list, with every existing key and value byte-identical (as an
   ast). Every added key and value is a plain literal. No added key may collide with any other key
   of the same literal (an override), every key of the literal must be statically visible, and no
   file in the head's closure may mutate or rebind the name (`.update()`, `NAME[k] =`, `|=`, a
   second binding). No other file this PR changes may mention the name (code that reads the
   registry). Lane-policy sets never qualify: universe_policy.py as a whole, any name that reads as
   a symbol, class, lane, sleeve, account, book, market, session or routing table (LANE_WORDS, as
   substrings), and any added key or member that is a symbol or asset class of either tree's
   universe.json (or reads as one). Adding to one of those is a principal-order lane boundary: a
   measured scenario or a ceilings row. Deny, exclude and retire registries (DENY_WORDS) never
   qualify either: adding to one REMOVES behaviour. A proven file is covered only if the
   allocator's money outputs on the pinned slice are also identical, base against head (its line
   trace is waived: a literal runs at import, so no line of it can be traced).

2. LINE TRACE on the pinned slice. research_child.py runs the capital allocator on the pinned tape
   slice (ops/release/research_slice, its manifest's sha256 pinned in SLICE_SHA256 here) once on
   the base tree and once on the head, each in a sandbox holding only the tree's Python and the
   slice. The file is covered only if (a) every changed or added code line of the head file ran
   inside a function frame that was not part of an import (an import alone, or a module or class
   body, never counts), a pure deletion counting through the head line that now stands in its
   place, and (b) the allocator's money outputs (the book, the proposed book, the heat, the trade
   verdict, the fallback, the zeroed sleeves, the aggression) are identical field by field. If no
   changed line ran, the file stays UNMEASURED however identical the decisions were.

SCOPE. Only closure files under desks/mt5/research/ and libs/research/ can qualify, and never the
box's entry points or anything named for the gateway, the decision core, sizing, allocation, heat,
an executor, a rail, a guard, a kill switch or a venue: those keep the manual path.

A file covered by SUPERSET has the registry names it grew excused from replay_shadow's knob rule
(the AST proof is the stronger check for exactly those names); every other knob rule still binds.
A file covered by LINE TRACE excuses nothing: its knobs are still held to the ceilings.
"""

from __future__ import annotations

import ast
import difflib
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CHILD = HERE / "research_child.py"
SLICE = HERE / "research_slice"
#: sha256 of research_slice/SLICE.sha256. The slice and this pin are PROTECTED (ops/release/), and a
#: PR's run always uses the base checkout's harness, so a PR can never move its own slice.
SLICE_SHA256 = "026528f039522fc431c261510fd56bd9c7625585385482ed7c648a7ccb28be1f"
TIMEOUT_S = 600

#: Condition 5: the only directories a file can qualify from.
SCOPE = ("desks/mt5/research/", "libs/research/")
#: Condition 5: never through this path, whatever directory it sits in (matched on the file stem).
NEVER = re.compile(
    r"gateway|decision_core|sizing|alloc|heat|kelly|executor|rail|guard|kill|e8|ftmo|fusion"
    r"|venue|order|deadman|live_door|promot|cert|ceiling"
    # #reach audit SF: stems in research/ that feed the money side (decay and retirement, the loss
    # loop, execution cost). Substrings on purpose: a false hit only costs the manual path.
    r"|risk|stop|exit|lot|margin|leverage|exposure|capital|position|execut|fill|slip|cost"
    r"|decay|retire|sleeve|book|clock|live|loss|modifier|survival|drawdown",
    re.IGNORECASE,
)
#: Condition 4: whole files that are lane policy.
LANE_FILES = frozenset({"desks/mt5/research/universe_policy.py"})
#: Condition 4: a name CONTAINING any of these (as a substring, so SYMBOLMAP and PEERCLASSES
#: match too) is a symbol, class or lane routing table. Over-matching only costs the trace.
LANE_WORDS = (
    "LANE", "ROUTE", "ROUTING", "SYMBOL", "CLASS", "KLASS", "UNIVERSE", "SLEEVE", "ACCOUNT",
    "BOOK", "VENUE", "BROKER", "DESK", "INSTRUMENT", "PAIR", "CROSS_SECTIONAL", "ALLOW", "LIVE",
    "MARKET", "TICKER", "ASSET", "PEER", "MEMBER", "SESSION", "WINDOW", "HOUR", "REGION",
    "CURRENC", "CCY", "EXCHANGE", "EQUIT", "FX", "METAL", "INDEX", "INDIC", "CFD",
)  # fmt: skip
#: #reach audit MF1: a member added to a deny, exclude or retire registry REMOVES something from
#: what the desk does; it is never a pure addition. Substrings of the registry's name.
DENY_WORDS = (
    "NOT", "EXCLUDE", "SKIP", "BLOCK", "DENY", "RETIRE", "DISABLE", "IGNORE", "BAN", "VETO",
    "KILL", "STOP", "FORBID", "OFF",
)  # fmt: skip
#: Condition 4 backstop: an added member that reads as an instrument (EURUSD, XAUUSD.m, US500).
#: The authority is the universe itself (`lane_values`): every symbol and asset class it lists.
INSTRUMENT = re.compile(r"^(?:[A-Z]{6}|XA[UG][A-Z]{3}|[A-Z]{2,5}\d{2,4})(?:[._-]\w+)?$")
UNIVERSE_JSON = "desks/mt5/data/universe/universe.json"
#: Asset-class words, whatever the universe calls them: a member made of one is a lane boundary.
CLASS_TOKENS = frozenset(
    {
        "fx", "forex", "exotic", "exotics", "equity", "equities", "stock", "stocks", "share",
        "shares", "metal", "metals", "index", "indices", "crypto", "commodity", "commodities",
        "energy", "energies", "bond", "bonds", "soft", "softs", "rates", "cfd", "cfds",
    }
)  # fmt: skip
#: Methods that change a container in place.
MUTATORS = frozenset(
    {
        "update", "setdefault", "pop", "popitem", "clear", "add", "discard", "remove", "append",
        "extend", "insert", "sort", "reverse", "difference_update", "intersection_update",
        "symmetric_difference_update", "__setitem__", "__delitem__", "__ior__", "__iand__",
        "__isub__", "__ixor__", "__iadd__",
    }
)  # fmt: skip
#: The allocator's money outputs: compared field by field (research-side artifacts never count).
MONEY_KEYS = (
    "armed", "advisory", "book", "proposed_book", "book_fallback", "floor_fill", "heat",
    "no_trade", "aggression", "exchange_zero", "trade_value_worlds",
)  # fmt: skip


class NotSuperset(Exception):
    """The change is not a pure addition; the message says where."""


def in_scope(path: str, entry_points: Iterable[str] = ()) -> tuple[bool, str]:
    if not path.endswith(".py"):
        return False, "not Python"
    if not path.startswith(SCOPE):
        return False, "outside desks/mt5/research/ and libs/research/ (condition 5)"
    if path in set(entry_points):
        return False, "a box entry point (condition 5)"
    if NEVER.search(Path(path).stem):
        return False, "named for the gateway, decision core, sizing or a rail (condition 5)"
    return True, ""


# ---------------------------------------------------------------- SUPERSET (condition 3 and 4)
def _d(node: ast.AST | None) -> str:
    return "" if node is None else ast.dump(node, include_attributes=False)


def _literal(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError) as exc:
        raise NotSuperset(f"an added member is not a plain literal ({_d(node)[:80]})") from exc


def _fromkeys(node: ast.AST) -> ast.Call | None:
    """`dict.fromkeys(<literal container>, <value>)`, the one splat whose keys are static."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "fromkeys"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "dict"
        and 1 <= len(node.args) <= 2
        and not node.keywords
    ):
        return node
    return None


def _keys(node: ast.Dict) -> list[Any]:
    """Every key the dict literal produces, in order; raises if one cannot be seen statically."""
    out: list[Any] = []
    for k, v in zip(node.keys, node.values, strict=True):
        if k is not None:
            out.append(_literal(k))
        elif isinstance(v, ast.Dict):
            out += _keys(v)
        elif (fk := _fromkeys(v)) is not None:
            members = fk.args[0]
            if not isinstance(members, ast.Tuple | ast.List | ast.Set):
                raise NotSuperset("a dict.fromkeys splat whose keys are not a literal")
            out += [_literal(e) for e in members.elts]
        else:
            raise NotSuperset(f"a ** splat whose keys cannot be seen statically ({_d(v)[:60]})")
    return out


def _grow(b: ast.AST, h: ast.AST, added: list[str]) -> None:
    """Raises unless `h` is `b` with members added; appends a repr of each added member."""
    if _d(b) == _d(h):
        return
    if type(b) is not type(h):
        raise NotSuperset(f"{type(b).__name__} became {type(h).__name__}")
    if isinstance(b, ast.Dict) and isinstance(h, ast.Dict):
        bi = 0
        pairs_b = list(zip(b.keys, b.values, strict=True))
        for hk, hv in zip(h.keys, h.values, strict=True):
            if bi < len(pairs_b):
                bk, bv = pairs_b[bi]
                if (bk is None) == (hk is None) and _d(bk) == _d(hk):
                    if bk is not None:
                        if _d(bv) != _d(hv):
                            raise NotSuperset(f"the value of existing key {_d(bk)[:60]} changed")
                    else:
                        _grow_splat(bv, hv, added)
                    bi += 1
                    continue
            if any(
                (bk is None) == (hk is None) and (hk is None or _d(bk) == _d(hk))
                for bk, _ in pairs_b[bi + 1 :]
            ):
                raise NotSuperset("an existing key was removed or reordered")
            if hk is None:
                raise NotSuperset("a ** splat was added")
            added.append(repr(_literal(hk)))
            _literal(hv)
        if bi != len(pairs_b):
            raise NotSuperset("an existing key was removed or reordered")
        keys = _keys(h)
        dup = sorted({repr(k) for k in keys if keys.count(k) > 1})
        if dup:
            raise NotSuperset(f"key {dup[0]} is given twice in the literal: an override")
        return
    if isinstance(b, ast.Set) and isinstance(h, ast.Set):
        have = [_d(e) for e in b.elts]
        rest = [_d(e) for e in h.elts]
        for x in have:
            if x not in rest:
                raise NotSuperset("an existing member was removed")
            rest.remove(x)
        vals = [_literal(e) for e in h.elts]
        for x in h.elts:
            if _d(x) in rest:
                added.append(repr(_literal(x)))
        if len({repr(v) for v in vals}) != len(vals):
            raise NotSuperset("a member is given twice")
        return
    if isinstance(b, ast.Tuple | ast.List) and isinstance(h, ast.Tuple | ast.List):
        if [_d(e) for e in h.elts[: len(b.elts)]] != [_d(e) for e in b.elts]:
            raise NotSuperset("existing members changed or moved (only appending qualifies)")
        new = [_literal(e) for e in h.elts[len(b.elts) :]]
        vals = [_literal(e) for e in h.elts]
        if len({repr(v) for v in vals}) != len(vals):
            raise NotSuperset("a member is given twice")
        added += [repr(v) for v in new]
        return
    if (
        isinstance(b, ast.Call)
        and isinstance(h, ast.Call)
        and isinstance(b.func, ast.Name)
        and b.func.id in {"frozenset", "set", "tuple", "list"}
        and _d(b.func) == _d(h.func)
        and len(b.args) == len(h.args) == 1
        and not b.keywords
        and not h.keywords
    ):
        _grow(b.args[0], h.args[0], added)
        return
    raise NotSuperset(f"a {type(b).__name__} changed, which is not a registry literal")


def _grow_splat(b: ast.AST, h: ast.AST, added: list[str]) -> None:
    """Inside `**...`: a nested dict literal, or dict.fromkeys whose value stays identical."""
    if _d(b) == _d(h):
        return
    fb, fh = _fromkeys(b), _fromkeys(h)
    if fb is not None and fh is not None:
        if [_d(a) for a in fb.args[1:]] != [_d(a) for a in fh.args[1:]]:
            raise NotSuperset("the shared value of a dict.fromkeys splat changed")
        _grow(fb.args[0], fh.args[0], added)
        return
    if isinstance(b, ast.Dict) and isinstance(h, ast.Dict):
        _grow(b, h, added)
        return
    raise NotSuperset("a ** splat changed")


def _target(stmt: ast.stmt) -> tuple[str, ast.AST, str] | None:
    """(name, value, annotation dump) of a plain module-level `NAME = literal` binding."""
    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
        t = stmt.targets[0]
        if isinstance(t, ast.Name):
            return t.id, stmt.value, ""
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value:
        return stmt.target.id, stmt.value, _d(stmt.annotation)
    return None


def is_lane_name(name: str) -> bool:
    up = name.upper()
    return any(w in up for w in LANE_WORDS)


def is_deny_name(name: str) -> bool:
    up = name.upper()
    return any(w in up for w in DENY_WORDS)


def lane_values(texts: Iterable[str | None]) -> frozenset[str]:
    """Every symbol and asset class the universe lists (lower case), from each tree's
    universe.json. An unreadable universe adds nothing; the regex and CLASS_TOKENS still bind."""
    out: set[str] = set()
    for text in texts:
        try:
            doc = json.loads(text or "{}")
        except ValueError:
            continue
        if not isinstance(doc, dict):
            continue
        for sym, row in doc.items():
            out.add(str(sym).lower())
            if isinstance(row, dict):
                for k in ("symbol", "asset_class", "class", "path"):
                    v = row.get(k)
                    if isinstance(v, str) and v.strip():
                        out.add(v.strip().lower())
                        out.add(re.sub(r"\W+", "_", v.strip().lower()))
    return frozenset(out)


def lane_member(text: str, lanes: frozenset[str]) -> bool:
    """Whether an added key or member reads as a symbol or an asset class."""
    low = text.lower()
    if INSTRUMENT.match(text) or low in lanes or re.sub(r"\W+", "_", low) in lanes:
        return True
    tokens = [t for t in re.split(r"[^a-z0-9]+", low) if t]
    if any(t in CLASS_TOKENS for t in tokens):
        return True
    return any(len(t) >= 4 and t in lanes for t in tokens)


def superset(
    path: str, base_src: str, head_src: str, lanes: frozenset[str] = frozenset()
) -> dict[str, list[str]]:
    """{registry name: [added members]} when the change is a pure addition; raises NotSuperset.
    `lanes` is `lane_values` of both trees' universe."""
    if path in LANE_FILES:
        raise NotSuperset("lane policy (condition 4): a measured scenario or a ceilings row")
    try:
        bt, ht = ast.parse(base_src), ast.parse(head_src)
    except SyntaxError as exc:
        raise NotSuperset(f"cannot be parsed ({exc.msg})") from exc
    if len(bt.body) != len(ht.body):
        raise NotSuperset("statements were added or removed")
    grown: dict[str, list[str]] = {}
    for bs, hs in zip(bt.body, ht.body, strict=True):
        if _d(bs) == _d(hs):
            continue
        bt_, ht_ = _target(bs), _target(hs)
        if bt_ is None or ht_ is None or bt_[0] != ht_[0] or bt_[2] != ht_[2]:
            raise NotSuperset(f"line {hs.lineno}: a change that is not a registry literal")
        name = ht_[0]
        if is_lane_name(name):
            raise NotSuperset(f"{name} is a symbol, class or lane table (condition 4)")
        if is_deny_name(name):
            raise NotSuperset(f"{name} is a deny or exclude registry: adding removes behaviour")
        added: list[str] = []
        _grow(bt_[1], ht_[1], added)
        for a in added:
            text = a.strip("'\"")
            if lane_member(text, lanes):
                raise NotSuperset(f"{name} gains {a}, a symbol or asset class (condition 4)")
        grown.setdefault(name, []).extend(added)
    if not grown:
        raise NotSuperset("no registry literal grew")
    return grown


def _refs(node: ast.AST, name: str) -> bool:
    return (isinstance(node, ast.Name) and node.id == name) or (
        isinstance(node, ast.Attribute) and node.attr == name
    )


def mutations(src: str, name: str, *, defining: bool) -> list[str]:
    """Every way `src` can change or rebind `name` after its literal is built."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return ["cannot be parsed"]
    out: list[str] = []
    binds = 0
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            if n.func.attr in MUTATORS and _refs(n.func.value, name):
                out.append(f"line {n.lineno}: .{n.func.attr}()")
        elif isinstance(n, ast.Subscript) and isinstance(n.ctx, ast.Store | ast.Del):
            if _refs(n.value, name):
                out.append(f"line {n.lineno}: item assignment")
        elif isinstance(n, ast.AugAssign) and _refs(n.target, name):
            out.append(f"line {n.lineno}: augmented assignment")
        elif isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Store | ast.Del):
            binds += 1
        elif isinstance(n, ast.Attribute) and n.attr == name and isinstance(n.ctx, ast.Store):
            out.append(f"line {n.lineno}: rebinds .{name}")
        elif isinstance(n, ast.Global | ast.Nonlocal) and name in n.names:
            out.append(f"line {n.lineno}: global {name}")
        elif isinstance(n, ast.alias) and (n.asname or n.name) == name and defining:
            binds += 1
    if binds > (1 if defining else 0):
        out.append(f"{name} is bound {binds} times")
    return out


# ------------------------------------------------------------ LINE TRACE (condition 1 and 2)
def changed_lines(base_src: str, head_src: str) -> tuple[set[int], set[int]]:
    """(head lines added or rewritten, head lines standing where base lines were deleted)."""
    b, h = base_src.splitlines(), head_src.splitlines()
    added: set[int] = set()
    stand_in: set[int] = set()
    for tag, _i1, _i2, j1, j2 in difflib.SequenceMatcher(None, b, h, autojunk=False).get_opcodes():
        if tag in ("replace", "insert"):
            added.update(range(j1 + 1, j2 + 1))
        elif tag == "delete":
            stand_in.add(j1 + 1)  # the head line now in the deleted lines' place
    return added, stand_in


def _functions(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)]


def _span(n: ast.AST) -> tuple[int, int]:
    return n.lineno, getattr(n, "end_lineno", None) or n.lineno


def unexecuted(head_src: str, added: set[int], stand_in: set[int], hits: set[int]) -> list[str]:
    """The changed lines no traced run executed, each with why. Empty means every one ran."""
    tree = ast.parse(head_src)
    lines = head_src.splitlines()
    fns = _functions(tree)
    stmts = [n for n in ast.walk(tree) if isinstance(n, ast.stmt)]
    misses: list[str] = []

    def code_line(n: int) -> int | None:
        while 1 <= n <= len(lines):
            s = lines[n - 1].strip()
            if s and not s.startswith("#"):
                return n
            n += 1
        return None

    def check(n: int, what: str) -> None:
        inner = [f for f in fns if _span(f)[0] - len(f.decorator_list) <= n <= _span(f)[1]]
        if not inner:
            misses.append(f"line {n} ({what}) runs only at import: a module or class body")
            return
        fn = min(inner, key=lambda f: _span(f)[1] - _span(f)[0])
        body_lo = fn.body[0].lineno
        if n < body_lo:  # the def line, its decorators or its signature: did its body run?
            if not any(body_lo <= x <= _span(fn)[1] for x in hits):
                misses.append(f"line {n} ({what}): {fn.name} never ran")
            return
        own = [
            s for s in stmts
            if s is not fn and _span(s)[0] <= n <= _span(s)[1] and _span(fn)[0] < s.lineno
        ]  # fmt: skip
        if not own:
            misses.append(f"line {n} ({what}): not inside a statement of {fn.name}")
            return
        s = min(own, key=lambda x: _span(x)[1] - _span(x)[0])
        body = getattr(s, "body", None)
        if isinstance(body, list) and body and n < body[0].lineno:
            lo, hi = s.lineno, body[0].lineno - 1  # a compound statement's header
        elif isinstance(body, list) and body:
            lo, hi = n, _span(s)[1]  # `else:` / `finally:` / `except` lines: the block after
        else:
            lo, hi = _span(s)
        if isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant):
            misses.append(f"line {n} ({what}): a docstring or bare constant never executes")
        elif not any(lo <= x <= hi for x in hits):
            misses.append(f"line {n} ({what}): never executed on the slice")

    for n in sorted(added):
        c = lines[n - 1].strip() if n <= len(lines) else ""
        if c and not c.startswith("#"):
            check(n, "changed")
    for n in sorted(stand_in):
        c = code_line(n)
        if c is None:
            misses.append("a deletion at the end of the file: nothing stands in its place")
        else:
            check(c, "after a deletion")
    return misses


def money(doc: dict[str, Any], canon: Callable[[Any], Any]) -> dict[str, Any]:
    """The allocator's decisions, through replay_shadow's own `canon` (prose and times dropped)."""
    out = {k: doc.get(k) for k in MONEY_KEYS}
    out["book_zeroed"] = sorted((doc.get("book_zeroed") or {}).keys())
    out["constrained_adopted"] = (doc.get("constrained_book") or {}).get("adopted")
    return canon(out)


def run_slice(tree: Path, targets: list[str]) -> dict[str, Any]:
    """The allocator on the pinned slice in `tree`, in a fresh process and an empty directory."""
    with tempfile.TemporaryDirectory(prefix=secrets.token_hex(4)) as tmp:
        work = Path(tmp)
        (work / "spec.json").write_text(
            json.dumps({"slice_sha256": SLICE_SHA256, "targets": targets}), "utf-8"
        )
        out = work / "out.json"
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(work),
            "PYTHONHASHSEED": "0",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "TZ": "UTC",
        }
        try:
            p = subprocess.run(
                [sys.executable, "-I", str(CHILD), str(tree.resolve()), str(SLICE), "spec.json",
                 str(out)],
                cwd=work, env=env, capture_output=True, text=True, timeout=TIMEOUT_S,
                check=False,
            )  # fmt: skip
        except subprocess.TimeoutExpired:
            return {"crash": f"timed out after {TIMEOUT_S}s"}
        if p.returncode != 0 or not out.exists():
            return {"crash": f"rc {p.returncode}: {(p.stderr or p.stdout)[-600:]}"}
        return json.loads(out.read_text("utf-8"))


# ------------------------------------------------------------------------------ the reach
def reach(
    base: Path,
    head: Path,
    changed: list[str],
    uncovered: list[str],
    read: Callable[[Path, str], str | None],
    closure: set[str],
    entry_points: Iterable[str] = (),
    *,
    canon: Callable[[Any], Any],
    run: Callable[[Path, list[str]], dict[str, Any]] = run_slice,
) -> dict[str, Any]:
    """{"covered": {file: how}, "unmeasured": {file: why}, "excused_knobs": {file: [names]},
    "problems": [...], "slice_sha256", "ran"} for the files replay-shadow left UNMEASURED."""
    entry = tuple(entry_points)
    covered: dict[str, dict[str, Any]] = {}
    unmeasured: dict[str, str] = {}
    excused: dict[str, list[str]] = {}
    problems: list[str] = []
    others = [f for f in changed if f.endswith(".py") and not _is_test(f)]
    lanes = lane_values([read(base, UNIVERSE_JSON), read(head, UNIVERSE_JSON)])
    trace: list[str] = []
    proven: dict[str, dict[str, list[str]]] = {}
    for f in uncovered:
        ok, why = in_scope(f, entry)
        if not ok:
            unmeasured[f] = why
            continue
        b, h = read(base, f), read(head, f)
        if b is None or h is None:
            unmeasured[f] = "added or deleted: nothing to compare against"
            continue
        try:
            grown = superset(f, b, h, lanes)
            for name in grown:
                for g in others:
                    if g == f:
                        continue
                    text = (read(base, g) or "") + "\n" + (read(head, g) or "")
                    if re.search(rf"\b{re.escape(name)}\b", text):
                        raise NotSuperset(f"{g} reads {name} and changes in this PR")
                for g in sorted(closure | {f}):
                    src = read(head, g) if g.endswith(".py") else None
                    if src and name in src:
                        bad = mutations(src, name, defining=(g == f))
                        if bad:
                            raise NotSuperset(f"{g} changes {name}: {bad[0]}")
            proven[f] = grown
            unmeasured[f] = "a pure addition, not yet measured on the slice"
        except NotSuperset as exc:
            trace.append(f)
            unmeasured[f] = f"not a pure addition: {exc}"
    ran = False
    # #reach audit MF2: a superset proof never stands alone. The slice runs whenever anything is
    # proven or traced, and a proven file is covered only if the money outputs are identical (its
    # line trace is waived: a literal runs at import, so no line of it can be traced).
    if trace or proven:
        ran = True
        rb, rh = run(base, trace), run(head, trace)
        if "crash" in rb or rb.get("error"):
            why = rb.get("crash") or rb.get("error")
            for f in [*trace, *proven]:
                unmeasured[f] += f"; the base tree cannot run the slice ({why})"[:400]
        elif "crash" in rh or rh.get("error"):
            why = rh.get("crash") or rh.get("error")
            problems.append(f"research reach: the PR's tree fails on the slice ({why})"[:500])
            for f in [*trace, *proven]:
                unmeasured[f] += "; the PR's tree fails on the slice"
        else:
            mb = money(rb.get("doc") or {}, canon)
            mh = money(rh.get("doc") or {}, canon)
            differs = sorted(k for k in set(mb) | set(mh) if mb.get(k) != mh.get(k))
            if differs:
                was = json.dumps({k: mb.get(k) for k in differs})[:400]
                now = json.dumps({k: mh.get(k) for k in differs})[:400]
                problems.append(
                    f"research reach: the PR's allocator decides differently on the slice on "
                    f"{', '.join(differs)}: base {was} PR {now}"
                )
            for f, grown in proven.items():
                if differs:
                    unmeasured[f] = "a pure addition, but the money outputs differ on the slice"
                else:
                    covered[f] = {"how": "superset", "added": grown, "money_identical": True}
                    excused[f] = sorted(grown)
                    unmeasured.pop(f, None)
            for f in trace:
                added, stand_in = changed_lines(read(base, f) or "", read(head, f) or "")
                misses = unexecuted(read(head, f) or "", added, stand_in,
                                    set((rh.get("hits") or {}).get(f, [])))  # fmt: skip
                if misses:
                    unmeasured[f] += "; line trace: " + "; ".join(misses[:5])
                elif differs:
                    unmeasured[f] += "; its lines ran but the money outputs differ"
                else:
                    covered[f] = {
                        "how": "line_trace",
                        "changed_lines": sorted(added),
                        "after_deletions": sorted(stand_in),
                        "executed": len((rh.get("hits") or {}).get(f, [])),
                    }
                    unmeasured.pop(f, None)
    return {
        "slice_sha256": SLICE_SHA256,
        "ran": ran,
        "covered": covered,
        "unmeasured": unmeasured,
        "excused_knobs": excused,
        "problems": problems,
    }


def _is_test(path: str) -> bool:
    p = Path(path)
    return "tests" in p.parts or p.name.startswith("test_") or p.name == "conftest.py"
