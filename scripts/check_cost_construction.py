#!/usr/bin/env python3
"""EVERY PLACE A COST OBJECT IS BUILT BY HAND, and the two unit traps that live there.

`engine.Costs.from_symbol` is the only correct constructor and its docstring says so. It handles
two conversions that a hand-rolled `Costs(...)` silently skips, and this desk has paid for both:

  QUOTE_PER_ACCOUNT -- "PRICE UNITS PER UNIT OF ACCOUNT CURRENCY, per lot -- the second unit
  trap, found 2026-08-26 ... On a EUR account, CADJPY prices in yen: one yen of price is worth
  0.005418 EUR, so a 7.00 EUR round-turn commission is 0.01292 yen of price -- and the engine
  was charging 7.00/100000 = 0.00007. 184x too little, ON THE JPY CROSSES WHERE THIS DESK'S
  SURVIVING EDGES ACTUALLY LIVE, in the direction that manufactures survivors."

  It defaults to 1.0 so no existing call site changed silently when it was added -- which is the
  right default and also the reason 75 call sites still carry the bug.

  PER-SIDE VERSUS ROUND-TURN -- `orthogonal_sweep.py:761` records the other one:
  "commission_per_lot=3.50, a ROUND-TURN figure in a PER-SIDE field ($7.00 charged)". Fusion
  Zero's contract is USD 2.25 per lot per side. A 3.50 in that field bills $7.00 a round trip
  against a true $4.50 -- 1.56x, in the direction that KILLS survivors.

SO THE TWO TRAPS PUSH IN OPPOSITE DIRECTIONS and a site can carry both at once. That is why this
counts them separately and never nets them: a module undercharging commission 184x on a JPY
cross while overcharging it 1.56x in nominal terms is not "roughly right".

IT IS A CENSUS AND IT FIXES NOTHING. Most of these sites are research scripts, and whether a
given one still runs is a fact about the schedule rather than about the code -- so each row
carries whether anything reachable from a CLOCK can call it. Rewriting seventy-five call sites
blind, on the money path, to chase a trap that only bites non-account-currency quotes, is how a
desk turns one bug into seventy-five.

    python scripts/check_cost_construction.py
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]

TREES = ("desks/mt5", "libs", "scripts")

#: Fusion Zero's contract, USD per lot PER SIDE. A larger value in that field is a round-turn
#: figure in a per-side slot. Mirrors `libs.portfolio.fusion_cost.COMMISSION_PER_LOT_PER_SIDE`.
COMMISSION_PER_SIDE = 2.25

OUT_REL = "desks/mt5/reports/COST_CONSTRUCTION.json"

CORRECT = "USES_FROM_SYMBOL"
UNKNOWN = "KWARGS_UNPACKED_NOT_STATICALLY_READABLE"
NO_QPA = "MISSING_QUOTE_PER_ACCOUNT"
ROUND_TURN = "ROUND_TURN_IN_A_PER_SIDE_FIELD"
BOTH = "BOTH_TRAPS"
DERIVED = "DERIVED_FROM_ANOTHER_COSTS"
FIXTURE = "LITERAL_FIXTURE_NOT_A_PRICED_INSTRUMENT"
STRESSED_COMMISSION = "STRESS_WIDENS_A_CONTRACTUAL_COMMISSION"


@dataclass(frozen=True)
class Site:
    module: str
    line: int
    func: str
    verdict: str
    commission: float | None
    live: bool
    why: str

    def to_dict(self) -> dict[str, Any]:
        return dict(vars(self))


def _live_modules(root: Path) -> set[str]:
    """Module stems reachable from a clock: the two cycles and the shipped schedulers.

    REACHABILITY IS ONE HOP, deliberately shallow. A deep import walk would mark almost
    everything live and the flag would stop discriminating; one hop answers the question a
    reader actually has -- "does a scheduled thing name this file".
    """
    names: set[str] = set()
    for rel in ("desks/mt5/research/hourly_cycle.py", "scripts/daily_research_cycle.py",
                "ops/crontab.manifest", "desks/mt5/recorders/install_tape_tasks.ps1"):
        p = root / Path(*rel.split("/"))
        if not p.exists():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for token in text.replace('"', " ").replace("'", " ").split():
            if token.endswith(".py"):
                names.add(Path(token).stem)
    return names


def _kwargs(node: ast.Call) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for kw in node.keywords:
        if kw.arg is None:
            continue
        try:
            out[kw.arg] = ast.literal_eval(kw.value)
        except (ValueError, SyntaxError):
            out[kw.arg] = "<expr>"
    return out


def scan_module(path: Path, root: Path, live: set[str]) -> list[Site]:
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
    except (OSError, SyntaxError):
        return []
    where: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for ln in range(node.lineno, (node.end_lineno or node.lineno) + 1):
                where[ln] = node.name
    rel = str(path.relative_to(root))
    is_live = path.stem in live
    out: list[Site] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Attribute) and fn.attr == "from_symbol":
            out.append(Site(rel, node.lineno, where.get(node.lineno, "<module>"),
                            CORRECT, None, is_live,
                            "the only constructor that converts both units"))
            continue
        if not (isinstance(fn, ast.Name) and fn.id == "Costs"):
            continue

        seg = (ast.get_source_segment(text, node) or "")
        # `Costs(**mapping)` CANNOT BE READ STATICALLY, and guessing costs a false positive on
        # the most important path there is: `shadow_forward.frozen_costs` builds exactly that way
        # and DOES pass quote_per_account -- it lists it in a `required` set. Reporting the
        # forward ledger as mispriced when it is correct is worse than reporting nothing.
        if any(k.arg is None for k in node.keywords):
            out.append(Site(rel, node.lineno, where.get(node.lineno, "<module>"),
                            UNKNOWN, None, is_live,
                            "built from an unpacked mapping, so the kwargs cannot be read from "
                            "the source. Open it rather than trusting a static verdict"))
            continue
        kw = _kwargs(node)
        # A Costs built FROM another Costs inherits its conversions; flagging it would report the
        # same defect twice and point at the wrong line.
        if "costs." in seg or "self." in seg or ".spread_per_lot" in seg:
            # A DERIVED Costs INHERITS THE CONVERSIONS -- but only if it is built by keyword.
            # `Costs(costs.spread_per_lot * 2, costs.commission_per_lot * 2, costs.contract_oz)`
            # is positional over three fields, so `quote_per_account` silently reverts to 1.0:
            # exactly the trap `engine.py:71` records. And doubling the commission stresses a
            # CONTRACTUAL number -- "stressing it models nothing that happens". `Costs.stressed`
            # is the constructor for this and scales the spread alone.
            widened = "commission_per_lot * 2" in seg or "commission_per_lot=costs." in seg
            out.append(Site(rel, node.lineno, where.get(node.lineno, "<module>"),
                            STRESSED_COMMISSION if widened else DERIVED, None, is_live,
                            "a stress that widens a contractual commission; use Costs.stressed, "
                            "which scales the spread only" if widened else
                            "derived from an existing Costs, so it inherits its conversions"))
            continue

        # A CALL WITH NO SYMBOL METADATA IN IT IS NOT PRICING AN INSTRUMENT. `check_backtest_
        # realism` builds `Costs(spread_per_lot=16.0, ...)` beside `Costs(spread_per_lot=160.0,
        # commission_per_lot=22.5, ...)` to assert the engine scales cost with notional -- the
        # 22.5 is deliberately ten times, not a round-turn figure in a per-side field. Flagging a
        # test fixture as a mispriced instrument is how a census loses its reader.
        if not any(t in seg for t in ("meta", "m[", "m.get", "info", "symbol", "sym")):
            out.append(Site(rel, node.lineno, where.get(node.lineno, "<module>"),
                            FIXTURE, None, is_live,
                            "every argument is a literal and no symbol metadata is referenced, "
                            "so this is a fixture rather than a priced instrument"))
            continue

        comm = kw.get("commission_per_lot")
        comm = float(comm) if isinstance(comm, (int, float)) else None
        no_qpa = "quote_per_account" not in kw
        round_turn = comm is not None and comm > COMMISSION_PER_SIDE

        verdict = (BOTH if (no_qpa and round_turn) else
                   NO_QPA if no_qpa else ROUND_TURN if round_turn else CORRECT)
        reasons = []
        if no_qpa:
            reasons.append("no quote_per_account, so commission stays in ACCOUNT CURRENCY and is "
                           "divided by contract_size as if it were PRICE -- 184x too little on a "
                           "JPY cross")
        if round_turn:
            reasons.append(f"commission_per_lot={comm} exceeds the {COMMISSION_PER_SIDE} per-SIDE "
                           f"contract, so it bills {comm * 2:.2f} a round trip")
        out.append(Site(rel, node.lineno, where.get(node.lineno, "<module>"), verdict, comm,
                        is_live, "; ".join(reasons) or "both units handled"))
    return out


def census(root: Path | None = None) -> dict[str, Any]:
    root = Path(root or _ROOT)
    live = _live_modules(root)
    sites: list[Site] = []
    for tree in TREES:
        base = root / Path(*tree.split("/"))
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if path.name.startswith("test_") or "engine.py" in path.name:
                continue
            sites.extend(scan_module(path, root, live))

    broken = [s for s in sites if s.verdict in (NO_QPA, ROUND_TURN, BOTH, STRESSED_COMMISSION)]
    on_clock = [s for s in broken if s.live]
    return {
        "at": datetime.now(tz=UTC).isoformat(),
        "commission_per_side": COMMISSION_PER_SIDE,
        "n_sites": len(sites),
        "by_verdict": {v: sum(1 for s in sites if s.verdict == v)
                       for v in (CORRECT, NO_QPA, ROUND_TURN, BOTH, DERIVED, UNKNOWN, FIXTURE,
                                 STRESSED_COMMISSION)},
        "n_broken": len(broken),
        # THE ONLY NUMBER THAT IS A WORK-LIST. A trap in a script no clock can reach costs
        # nothing until someone runs it; one on a scheduled path is charging wrong money now.
        "n_broken_on_a_clock": len(on_clock),
        "broken_on_a_clock": [s.to_dict() for s in on_clock],
        "broken_off_clock": [s.to_dict() for s in broken if not s.live],
        "rule": (
            "the two traps push in OPPOSITE directions and a site can carry both, so they are "
            "counted separately and never netted: undercharging commission 184x on a JPY cross "
            "while overcharging it 1.56x in nominal terms is not roughly right. This fixes "
            "nothing -- rewriting seventy-five money-path call sites blind to chase a trap that "
            "only bites non-account-currency quotes is how one bug becomes seventy-five"),
    }


def render(doc: dict[str, Any]) -> str:
    b = doc["by_verdict"]
    lines = [f"COST CONSTRUCTION  {doc['n_sites']} sites: {b[CORRECT]} via from_symbol, "
             f"{b[DERIVED]} derived, {b[UNKNOWN]} unreadable, {b[FIXTURE]} fixtures, "
             f"{b[STRESSED_COMMISSION]} stress a contractual commission, "
             f"{doc['n_broken']} hand-rolled and missing a conversion",
             f"  ON A CLOCK: {doc['n_broken_on_a_clock']}  "
             f"(missing quote_per_account {b[NO_QPA]}, round-turn-in-per-side {b[ROUND_TURN]}, "
             f"both {b[BOTH]})"]
    for s in doc["broken_on_a_clock"]:
        lines.append(f"  LIVE  {s['module']}:{s['line']}  {s['func']}()  {s['verdict']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="where a cost object is built without its conversions")
    ap.add_argument("--root", default=str(_ROOT))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.root)
    doc = census(root)
    out = root / Path(*OUT_REL.split("/"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(json.dumps(doc, indent=1, default=str) if args.json else render(doc))
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
