"""DOES THE REAL GATEWAY IMPLEMENT THE PROTOCOL THE MODEL CHECKER PROVED? (Tier S layer: formal)

`libs/tiers/formal.py` model-checks an ABSTRACT order protocol and names the knobs its invariants
depend on (persist the intent before sending, a client id on every order, re-check the
allocator and the certificate at send time, reconcile on restart, act on closed bars only).
Until 2026-09-30 the link to the real code was a keyword grep: a knob counted as implemented
when a word like "reconcile" appeared anywhere in gateway.py. That proves nothing -- the word is
in comments that say the opposite.

This module reads the gateway's SYNTAX TREE instead, and judges every EXPOSURE-OPENING send site
(a `*.order_send(...)` whose request is not a pure REMOVE or SLTP modification) on its own:

  idempotent_client_id   the request dict carries both "magic" and "comment" keys (a literal, or
                         the dict literal assigned to the variable that is sent);
  persist_before_send    a call named like an intent/journal write precedes the send, in the
                         sending function or in a function that calls it;
  recheck_alloc_at_send  a call reading allocator heat/book precedes the send on that path;
  check_cert_at_send     a call reading the sleeve policy/certificate precedes it on that path;

and two whole-module properties:

  reconcile_on_restart   the module's entry functions reach positions_get/orders_get through
                         the call graph (not merely contain the word);
  clamp_data_to_clock    bars are read closed: a `copy_rates_from_pos(..., 1, ...)` start at 1, or
                         an `.iloc[-2]` subscript, exists in executable code.

A knob is CONFORMANT when every opening send site satisfies it. Comments and strings can never
satisfy anything, because only call names, dict keys and subscripts are read.
"""
from __future__ import annotations

import ast
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

PERSIST = ("intent", "journal")
ALLOC = ("alloc", "heat", "book")
CERT = ("sleeve", "policy", "admit", "certif")
READS_BROKER = ("positions_get", "orders_get")
ENTRY = ("main", "run", "start", "boot", "loop", "startup")


def _call_name(node: ast.Call) -> str:
    f = node.func
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return ""


def _dict_keys(d: ast.Dict) -> set[str]:
    return {k.value for k in d.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}


def _is_modify_only(d: ast.Dict) -> bool:
    for k, v in zip(d.keys, d.values, strict=False):
        if isinstance(k, ast.Constant) and k.value == "action":
            name = v.attr if isinstance(v, ast.Attribute) else str(getattr(v, "id", ""))
            return name in ("TRADE_ACTION_REMOVE", "TRADE_ACTION_SLTP", "TRADE_ACTION_MODIFY")
    return False


class _Fn:
    def __init__(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.node = node
        self.calls: list[tuple[int, str]] = sorted(
            (c.lineno, _call_name(c)) for c in ast.walk(node) if isinstance(c, ast.Call))
        self.dicts: dict[str, ast.Dict] = {}
        for a in ast.walk(node):
            if isinstance(a, ast.Assign) and isinstance(a.value, ast.Dict):
                for t in a.targets:
                    if isinstance(t, ast.Name):
                        self.dicts[t.id] = a.value

    def before(self, line: int, toks: Iterable[str]) -> bool:
        toks = tuple(toks)
        return any(ln < line and any(t in name.lower() for t in toks) for ln, name in self.calls)

    def any_call(self, toks: Iterable[str]) -> bool:
        toks = tuple(toks)
        return any(any(t in name.lower() for t in toks) for _ln, name in self.calls)


def check_source(src: str, name: str = "<gateway>") -> dict[str, Any]:
    tree = ast.parse(src, name)
    fns: dict[str, _Fn] = {}
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fns[n.name] = _Fn(n)
    callers: dict[str, set[str]] = defaultdict(set)
    for fname, fn in fns.items():
        for _ln, c in fn.calls:
            if c in fns:
                callers[c].add(fname)

    def on_path(fname: str, line: int, toks: tuple[str, ...]) -> bool:
        if fns[fname].before(line, toks):
            return True
        # one level up: a caller that did it before calling this function
        for up in callers.get(fname, ()):
            ln = min((ln for ln, c in fns[up].calls if c == fname), default=None)
            if ln is not None and fns[up].before(ln, toks):
                return True
        return False

    sites: list[dict[str, Any]] = []
    for fname, fn in fns.items():
        for node in ast.walk(fn.node):
            if not (isinstance(node, ast.Call) and _call_name(node) == "order_send" and node.args):
                continue
            arg = node.args[0]
            d = arg if isinstance(arg, ast.Dict) else (
                fn.dicts.get(arg.id) if isinstance(arg, ast.Name) else None)
            if d is not None and _is_modify_only(d):
                continue
            keys = _dict_keys(d) if d is not None else set()
            # a request naming a `position` CLOSES exposure: re-checking the allocator or the
            # certificate before reducing risk is not part of the protocol, so those two pass
            closing = "position" in keys
            sites.append({
                "function": fname, "line": node.lineno, "closing": closing,
                "idempotent_client_id": {"magic", "comment"} <= keys,
                "persist_before_send": on_path(fname, node.lineno, PERSIST),
                "recheck_alloc_at_send": closing or on_path(fname, node.lineno, ALLOC),
                "check_cert_at_send": closing or on_path(fname, node.lineno, CERT),
                "request_resolved": d is not None})
    # reconcile on restart: an entry function reaches a broker read through the call graph
    reach: set[str] = set()
    frontier = [f for f in fns if any(f.lower().startswith(e) or f.lower() == e for e in ENTRY)]
    while frontier:
        f = frontier.pop()
        if f in reach:
            continue
        reach.add(f)
        frontier.extend(c for _ln, c in fns[f].calls if c in fns)
    reconcile = any(fns[f].any_call(READS_BROKER) for f in reach)
    clamp = False
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and _call_name(n) == "copy_rates_from_pos" and len(n.args) >= 3:
            a = n.args[2]
            if isinstance(a, ast.Constant) and a.value == 1:
                clamp = True
        if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Attribute) and \
                n.value.attr == "iloc":
            s = n.slice
            if isinstance(s, ast.UnaryOp) and isinstance(s.op, ast.USub) and \
                    isinstance(s.operand, ast.Constant) and s.operand.value == 2:
                clamp = True          # .iloc[-2]: the last CLOSED bar
            if isinstance(s, ast.Slice) and s.lower is None and isinstance(s.upper, ast.UnaryOp) \
                    and isinstance(s.upper.op, ast.USub) and \
                    isinstance(s.upper.operand, ast.Constant) and s.upper.operand.value == 1:
                clamp = True          # .iloc[:-1]: the forming bar dropped
    knobs = ("idempotent_client_id", "persist_before_send", "recheck_alloc_at_send",
             "check_cert_at_send")
    per = {k: (all(s[k] for s in sites) if sites else None) for k in knobs}
    per["reconcile_on_restart"] = reconcile
    per["clamp_data_to_clock"] = clamp
    failing = {k: [f"{s['function']}:{s['line']}" for s in sites if not s[k]] for k in knobs}
    return {"send_sites": len(sites), "entry_functions_reached": len(reach),
            "knobs": per, "failing_sites": {k: v for k, v in failing.items() if v},
            "conformant": sum(1 for v in per.values() if v), "of": len(per),
            "conformant_share": sum(1 for v in per.values() if v) / len(per)}


def check_paths(paths: Iterable[Path]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for p in paths:
        try:
            out[p.name] = check_source(p.read_text("utf-8", errors="replace"), str(p))
        except (OSError, SyntaxError) as exc:
            out[p.name] = {"error": f"{type(exc).__name__}: {exc}"}
    return out
