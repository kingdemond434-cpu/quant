#!/usr/bin/env python3
"""MONEY-PATH SOVEREIGNTY FENCE -- the four invariants, mirrored and wired at every placement site.

THE PRINCIPAL'S AUDIT (2026-09-30) of the committed `desks/mt5/data/sleeves.json`: 40 LIVE
sleeves, 24 of the banned `discovered` family, 31 with an UNMEASURED admission, 40 of 40 with
`artifact.ok` false, 7 principal overrides, and a minimum-ticket path that could send an order
the allocator had sized at zero. `desks/mt5/mt5desk/money_path.py` holds the four invariants and
`gateway.money_path_guard` applies them. This fence is what keeps them applied:

  S1  EVERY NEW-RISK `order_send` IS GUARDED. It AST-walks `desks/mt5/mt5desk/gateway.py`, finds
      each `mt5.order_send(...)` whose request opens risk -- `TRADE_ACTION_DEAL` or
      `TRADE_ACTION_PENDING` with no `position` key (a `position` key is a close; REMOVE, SLTP
      and CLOSE_BY reduce or amend) -- and fails unless the enclosing function calls
      `money_path_guard(` on a line before it. It also fails if fewer than the three known lanes
      are found, because a walk that finds nothing proves nothing.
  S2  EVERY CALL THAT REACHES A GUARDED SENDER IS GUARDED TOO: each call to `place_bracket(`
      sits after a `money_path_guard(` call in its own function.
  S3  THE INVARIANTS HOLD AS BEHAVIOUR, not only as text: allocator zero / absent / NaN is
      refused, an UNMEASURED or absent admission is refused, a family on the DECLARED ban list is
      refused, an UNMEASURED cost is refused, and a sleeve that satisfies all four is admitted.
  S4  ZERO IS NO LOT. `decision_core.promoted_lot` and `gold_book_lot` return 0.0 for a zero,
      absent or non-finite allocator fraction, and still at least the floor above zero -- the
      0.02 gold floor and the venue minimum are untouched for every fraction > 0.
  S5  THE BAN LIST IS READ, NEVER RESTATED: `money_path.py` carries no string literal naming a
      banned family, and its `banned_families()` returns the union of the two declared sources.
  S6  EVERY REFUSAL LEAVES ITS ROWS: `money_path_guard` calls `_record_decision` (the decision
      ledger) and `append_missed_growth` (the growth-governance line).
  S7  EVERY NEW ORDER CARRIES ITS IDENTITY: each new-risk request's comment is the
      identity-tagged `_ident["comment"]` from `gateway.new_order_identity` (the pre-trade chain
      head, `libs/research/trade_identity.tag`).

S3 also covers the blueprint additions: I5 (an UNMEASURED marginal dE[log W] is refused), I6 (a
principal override outside the declared experimental budget is refused) and that I4 is decided by
`research/cost_surfaces.cost_for` rather than a parallel reader.

It also REPORTS -- never fails on -- the measured count of committed LIVE rows that remain
tradable under the four invariants, so the number the principal asked for is on every run.

    python scripts/check_money_path_sovereignty.py [--json]
"""
from __future__ import annotations

import argparse
import ast
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

GATEWAY = DESK / "mt5desk" / "gateway.py"
MONEY_PATH = DESK / "mt5desk" / "money_path.py"
SLEEVES = DESK / "data" / "sleeves.json"
GUARD = "money_path_guard"
#: The three lanes that open risk today. A new one is welcome and is guarded by S1 like these;
#: fewer than these means the walk broke, not that the desk stopped trading.
KNOWN_SITES = frozenset({"place_bracket", "run_family_sleeves", "run_scalp_sleeves"})
NEW_RISK_ACTIONS = frozenset({"TRADE_ACTION_DEAL", "TRADE_ACTION_PENDING"})
#: What every new-risk request's comment must be: the identity-tagged comment
#: `gateway.new_order_identity` built for this order (chain head in the comment).
IDENTITY_COMMENT = "_ident['comment']"


# ------------------------------------------------------------------------------ S1 / S2
def _dict_of(call: ast.Call, fn: ast.FunctionDef) -> ast.Dict | None:
    """The request dict an order_send receives: a literal, or the literal a local name holds."""
    if not call.args:
        return None
    arg = call.args[0]
    if isinstance(arg, ast.Dict):
        return arg
    if isinstance(arg, ast.Name):
        found: ast.Dict | None = None
        for node in ast.walk(fn):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict) \
                    and node.lineno < call.lineno \
                    and any(isinstance(t, ast.Name) and t.id == arg.id for t in node.targets):
                found = node.value
        return found
    return None


def _is_new_risk(req: ast.Dict | None) -> bool | None:
    """True for an opening request, False for a reducing one, None when unreadable."""
    if req is None:
        return None
    keys = {k.value for k in req.keys if isinstance(k, ast.Constant)}
    action = None
    for k, v in zip(req.keys, req.values, strict=True):
        if isinstance(k, ast.Constant) and k.value == "action" and isinstance(v, ast.Attribute):
            action = v.attr
    if action is None:
        return None
    return action in NEW_RISK_ACTIONS and "position" not in keys


def _calls(fn: ast.AST, name: str) -> list[int]:
    out = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            f = node.func
            if (isinstance(f, ast.Name) and f.id == name) or \
                    (isinstance(f, ast.Attribute) and f.attr == name):
                out.append(node.lineno)
    return sorted(out)


def placement_sites(src: str) -> list[dict[str, Any]]:
    """Every order_send in the gateway, classified, with the guard lines of its function."""
    tree = ast.parse(src)
    sites: list[dict[str, Any]] = []
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        guards = _calls(fn, GUARD)
        for node in ast.walk(fn):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "order_send":
                kind = _is_new_risk(_dict_of(node, fn))
                req = _dict_of(node, fn)
                comment = None
                if req is not None:
                    for k, v in zip(req.keys, req.values, strict=True):
                        if isinstance(k, ast.Constant) and k.value == "comment":
                            comment = ast.unparse(v)
                sites.append({"function": fn.name, "line": node.lineno, "new_risk": kind,
                              "guarded": any(g < node.lineno for g in guards),
                              "comment": comment})
    return sites


def check_sites(src: str) -> list[dict[str, str]]:
    f: list[dict[str, str]] = []
    sites = placement_sites(src)
    for s in sites:
        if s["new_risk"] is None:
            f.append({"check": "S1_UNCLASSIFIABLE_SEND",
                      "why": f"order_send at gateway.py:{s['line']} in {s['function']} has a "
                             f"request this fence cannot read; it cannot be shown to reduce risk"})
        elif s["new_risk"] and not s["guarded"]:
            f.append({"check": "S1_UNGUARDED_PLACEMENT",
                      "why": f"new-risk order_send at gateway.py:{s['line']} in "
                             f"{s['function']} is not preceded by {GUARD}()"})
        if s["new_risk"] and s.get("comment") != IDENTITY_COMMENT:
            f.append({"check": "S7_IDENTITY_TAG",
                      "why": f"new-risk order_send at gateway.py:{s['line']} in "
                             f"{s['function']} sends comment {s.get('comment')!r}, not the "
                             f"identity-tagged {IDENTITY_COMMENT}"})
    found = {s["function"] for s in sites if s["new_risk"]}
    missing = KNOWN_SITES - found
    if missing:
        f.append({"check": "S1_SITES_FOUND",
                  "why": f"the walk did not find the known placement lanes {sorted(missing)}; "
                         f"a fence that finds nothing proves nothing"})
    tree = ast.parse(src)
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef) or fn.name == "place_bracket":
            continue
        guards = _calls(fn, GUARD)
        for line in _calls(fn, "place_bracket"):
            if not any(g < line for g in guards):
                f.append({"check": "S2_UNGUARDED_CALLER",
                          "why": f"{fn.name} calls place_bracket at gateway.py:{line} without "
                                 f"a prior {GUARD}()"})
    # S6 -- the guard writes both rows
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef) and fn.name == GUARD:
            for need in ("_record_decision", "append_missed_growth"):
                if not _calls(fn, need):
                    f.append({"check": "S6_REFUSAL_ROWS",
                              "why": f"{GUARD} no longer calls {need}: a refusal would leave "
                                     f"no row"})
            break
    else:
        f.append({"check": "S6_REFUSAL_ROWS", "why": f"gateway.py has no {GUARD}"})
    return f


# ------------------------------------------------------------------------------ S3 / S4 / S5
def _base_row(**kw: Any) -> dict[str, Any]:
    row = {"name": "fence_probe", "symbol": "XAUUSD", "family": "session_range_breakout",
           "origin": "registry", "sized_by": "allocator_book", "risk_frac": 0.01,
           "admission": {"status": "LIVE", "risk_frac": 0.01, "heat_earned": 0.01}}
    row.update(kw)
    return row


def check_behaviour() -> list[dict[str, str]]:
    f: list[dict[str, str]] = []
    try:
        from mt5desk import decision_core as dc
        from mt5desk import money_path as mp
    except Exception as exc:
        return [{"check": "S3_IMPORT", "why": f"money_path/decision_core unimportable: {exc}"}]
    banned, bwhy = mp.banned_families()
    if not banned:
        f.append({"check": "S5_BAN_LIST_READ", "why": f"no declared ban list readable: {bwhy}"})
        banned = frozenset()
    measured = {"status": mp.MEASURED, "source": "fence"}
    unmeasured = {"status": mp.UNMEASURED, "why": "fence"}

    def refused(row: dict[str, Any], cost: dict[str, Any], inv: str) -> bool:
        v = mp.verdict(row, banned=banned, cost=cost)
        return (not v["ok"]) and inv in {r["invariant"] for r in v["refusals"]}

    if not mp.verdict(_base_row(), banned=banned, cost=measured)["ok"]:
        f.append({"check": "S3_ADMITS_CLEAN", "why": "a sleeve satisfying all four is refused"})
    for frac in (0.0, None, float("nan"), -0.01):
        if not refused(_base_row(risk_frac=frac), measured, mp.ALLOCATOR_ZERO):
            f.append({"check": "S3_I1_ALLOCATOR_ZERO",
                      "why": f"allocator fraction {frac!r} is not refused"})
    if not refused(_base_row(sized_by=None, admission={"status": "LIVE"}), measured,
                   mp.ALLOCATOR_ZERO):
        f.append({"check": "S3_I1_ALLOCATOR_ZERO", "why": "an ABSENT fraction is not refused"})
    for adm in ({"status": "UNMEASURED", "risk_frac": 0.01}, None):
        if not refused(_base_row(admission=adm), measured, mp.ADMISSION_UNMEASURED):
            f.append({"check": "S3_I2_ADMISSION", "why": f"admission {adm!r} is not refused"})
    for fam in sorted(banned):
        if not refused(_base_row(family=fam.upper()), measured, mp.BANNED_FAMILY):
            f.append({"check": "S3_I3_BANNED", "why": f"banned family {fam!r} is not refused"})
    if not refused(_base_row(), unmeasured, mp.COST_UNMEASURED) or \
            not refused(_base_row(), None, mp.COST_UNMEASURED):  # type: ignore[arg-type]
        f.append({"check": "S3_I4_COST", "why": "an UNMEASURED cost is not refused"})
    if not refused(_base_row(admission={"status": "LIVE", "risk_frac": 0.01}), measured,
                   mp.MARGINAL_UNMEASURED):
        f.append({"check": "S3_I5_MARGINAL",
                  "why": "a LIVE admission with no marginal reading is not refused"})
    if not refused(_base_row(principal_override={"by": "fence"}), measured,
                   mp.OVERRIDE_OUTSIDE_BUDGET):
        f.append({"check": "S3_I6_OVERRIDE_BUDGET",
                  "why": "an override sleeve with no experimental budget is not refused"})
    # I4 IS DECIDED BY cost_surfaces.cost_for, not by a parallel reader
    try:
        mp_src = MONEY_PATH.read_text("utf-8")
        body = mp_src[mp_src.index("def cost_basis("):mp_src.index("def load_cost_surface(")]
        if "cost_for(" not in body:
            f.append({"check": "S3_I4_COST_FOR",
                      "why": "money_path.cost_basis no longer asks cost_surfaces.cost_for"})
    except (OSError, ValueError) as exc:
        f.append({"check": "S3_I4_COST_FOR", "why": f"cost_basis unreadable: {exc}"})
    # S4 -- zero is no lot, and the floor still binds above zero
    for frac in (0.0, None, float("nan"), -1.0):
        lot = dc.promoted_lot(10_000.0, 0, 0.005, "EURUSD", None, frac, None, from_book=True)
        if lot != 0.0:
            f.append({"check": "S4_ZERO_IS_NO_LOT",
                      "why": f"promoted_lot(from_book, h_i={frac!r}) = {lot}, not 0.0"})
        glot, _ = dc.gold_book_lot(10_000.0, 19.1, None, frac)
        if glot != 0.0:
            f.append({"check": "S4_ZERO_IS_NO_LOT",
                      "why": f"gold_book_lot(h_i={frac!r}) = {glot}, not 0.0"})
    tiny = 1e-6
    if dc.promoted_lot(10_000.0, 0, 5.0, "EURUSD", None, tiny, None, from_book=True) \
            < dc.venue_min_lot("EURUSD") - 1e-12:
        f.append({"check": "S4_FLOOR_ABOVE_ZERO",
                  "why": "a fraction > 0 no longer reaches the venue minimum"})
    glot, _ = dc.gold_book_lot(10_000.0, 19.1, None, tiny)
    if glot < dc.gold_min_lot() - 1e-12:
        f.append({"check": "S4_FLOOR_ABOVE_ZERO",
                  "why": f"a gold fraction > 0 sized {glot} under the gold floor"})
    # S5 -- no restated ban list in the module
    try:
        tree = ast.parse(MONEY_PATH.read_text("utf-8"))
        docs = {id(n.body[0].value) for n in ast.walk(tree)
                if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
                and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        lits = {str(n.value).strip().lower() for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs}
        restated = sorted(lits & {b.lower() for b in banned})
        if restated:
            f.append({"check": "S5_BAN_LIST_RESTATED",
                      "why": f"money_path.py hard-codes banned family literal(s) {restated}"})
    except OSError as exc:
        f.append({"check": "S5_BAN_LIST_RESTATED", "why": f"money_path.py unreadable: {exc}"})
    return f


# ------------------------------------------------------------------------------ report
def measure(path: Path = SLEEVES) -> dict[str, Any]:
    try:
        from mt5desk import money_path as mp
        from mt5desk.live_policy import refuse
        rows = json.loads(path.read_text("utf-8")).get("sleeves") or []
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}
    banned, _ = mp.banned_families()
    surface, source = mp.load_cost_surface()
    rep = mp.measure_registry(rows, banned=banned, surface=surface,
                              budget=mp.load_experimental_budget(),
                              live_policy_refuse=refuse)
    rep.pop("rows", None)
    rep["cost_surface"] = source
    return rep


def run() -> dict[str, Any]:
    try:
        src = GATEWAY.read_text("utf-8")
    except OSError as exc:
        return {"ok": False, "findings": [{"check": "S1_READ", "why": str(exc)}]}
    findings = check_sites(src) + check_behaviour()
    sites = [s for s in placement_sites(src) if s["new_risk"]]
    return {"ok": not findings, "findings": findings,
            "new_risk_sites": [f"{s['function']}:{s['line']}" for s in sites],
            "measured": measure()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rep = run()
    if a.json:
        print(json.dumps(rep, indent=1, default=str))
    else:
        m = rep.get("measured") or {}
        print(f"money-path sovereignty: {'OK' if rep['ok'] else 'FAIL'} -- "
              f"{len(rep.get('new_risk_sites') or [])} new-risk site(s) guarded; committed LIVE "
              f"{m.get('live')}, tradable under the money-path invariants "
              f"{m.get('tradable_under_invariants')} "
              f"(and under the live policy {m.get('tradable_under_invariants_and_live_policy')})")
        for x in rep["findings"]:
            print(f"  [{x['check']}] {x['why']}")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["check_behaviour", "check_sites", "main", "math", "measure", "placement_sites", "run"]
