#!/usr/bin/env python3
"""GROWTH GOVERNANCE FENCE (portable) -- the two standing rules, enforced at every boundary.

    RULE 1  Every risk-reduction mechanism must prove that it increases robust forward E[log W].
    RULE 2  Every strong opportunity must be allowed to increase capital above normal when the
            evidence supports it.

PRINCIPAL ORDER (2026-09-04): the desk is anti-timid by construction. Timid is not risk-aware:
a timid system sizes smaller because risk looks scary; this desk takes as much risk as the
evidence, diversification, execution quality and ruin probability justify, and more when the
opportunity set is unusually strong. Nothing done today or in the past may hold that back, and
nothing added in future may be misread as licence to do less. This fence makes that mechanical:

  G1  the utilisation floor is FLAT at HEAT_TARGET (20%) and growth is FREE above it to the
      HEAT_HARD_CEILING (30%): `heat_policy.resolve` carries `floor = target if mandate`, the
      allocator calls it with the mandate on, and nothing multiplies the floor by readiness
  G2  the resolved heat is FILLED, never reported short: `pf_allocator` carries the FLOOR FILL
  G3  the gateway is WIRED to the allocator: `cap_by_heat` budgets from `allocator_heat()`,
      `promoted_lot` deploys the book's fraction un-re-shrunk (`from_book`), and
      `allocator_book` falls back to the best baseline at the floor when the proof is stale
  G4  every registered capital modifier is TWO-SIDED (can exceed 1.0) unless it is an integrity
      kill switch or a reduce-only decay signal that is itself a registered, measured rail
  G5  every registered rail has a MEASUREMENT in `missed_growth` (its ledger line)
  G6  no capital-authority module ranks by Sharpe; ranking is marginal dE[log W]
  G7  the two rules are carried verbatim on every surface a future session or organ reads:
      docs/GROWTH_GOVERNANCE.md, CLAUDE.md, desks/mt5/AGENTS.md, and the deepening worker's
      system prompt

    python scripts/check_growth_governance.py [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "desks" / "mt5"))

RULE_1 = ("Every risk reduction mechanism must prove that it increases robust forward "
          "E[log W].")
RULE_2 = ("Every strong opportunity must be allowed to increase capital above normal when the "
          "evidence supports it.")
SURFACES = ("docs/GROWTH_GOVERNANCE.md", "CLAUDE.md", "desks/mt5/AGENTS.md",
            "desks/mt5/research/deepening_worker.py")


def _src(rel: str) -> str:
    try:
        return (ROOT / rel).read_text("utf-8")
    except OSError:
        return ""


def check() -> list[dict[str, str]]:
    f: list[dict[str, str]] = []
    hp = _src("desks/mt5/research/heat_policy.py")
    pa = _src("desks/mt5/research/pf_allocator.py")
    gw = _src("desks/mt5/mt5desk/gateway.py")

    # G1 -- flat floor, growth free above it
    if "floor = target if mandate else 0.0" not in hp:
        f.append({"check": "G1_FLAT_FLOOR", "why": "heat_policy.resolve no longer floors at the target"})
    if re.search(r"floor\s*=\s*target\s*\*", hp):
        f.append({"check": "G1_FLAT_FLOOR", "why": "the floor is multiplied by something (readiness?)"})
    if "elif h > target:" not in hp or "HARD CEILING" not in hp:
        f.append({"check": "G1_GROWTH_FREE_ABOVE", "why": "resolve lost the growth-above-target band"})
    if "mandate=True" not in pa:
        f.append({"check": "G1_MANDATE_ON", "why": "pf_allocator does not call resolve with mandate=True"})
    try:
        from mt5desk.gateway_config_fallback import HEAT_HARD_CEILING, HEAT_TARGET
        if not (abs(HEAT_TARGET - 0.20) < 1e-9 and abs(HEAT_HARD_CEILING - 0.30) < 1e-9):
            f.append({"check": "G1_CONSTANTS", "why": f"target {HEAT_TARGET} ceiling "
                                                       f"{HEAT_HARD_CEILING} (principal: 0.20/0.30)"})
    except Exception as exc:
        f.append({"check": "G1_CONSTANTS", "why": f"cannot import sizing constants: {exc}"})

    # G2 -- the floor is filled
    if "FLOOR FILL" not in pa or "fill_note" not in pa or '"floor_fill": fill_note' not in pa:
        f.append({"check": "G2_FLOOR_FILL", "why": "pf_allocator no longer fills the resolved heat"})

    # G3 -- gateway wiring
    if "solved, why = allocator_heat()" not in gw:
        f.append({"check": "G3_BUDGET_FROM_ALLOCATOR", "why": "cap_by_heat does not budget from allocator_heat()"})
    if "from_book: bool = False" not in gw or "if from_book:" not in gw:
        f.append({"check": "G3_BOOK_FRACTION_DEPLOYED", "why": "promoted_lot re-shrinks the allocator's fraction"})
    if gw.count("from_book=(s.get(\"sized_by\") == \"allocator_book\")") < 2:
        f.append({"check": "G3_BOOK_FRACTION_DEPLOYED", "why": "a promoted_lot call site does not pass from_book"})
    if "book_fallback" not in gw:
        f.append({"check": "G3_FLOOR_FALLBACK", "why": "allocator_book has no baseline fallback at the floor"})

    # G4 -- two-sided modifiers
    try:
        from libs.portfolio.capital_modifiers import REGISTRY
        from libs.portfolio.rails import RAILS
        rail_names = {r.name for r in RAILS}
        for m in REGISTRY:
            if m.kind == "two_sided" and not m.hi > 1.0:
                f.append({"check": "G4_TWO_SIDED", "why": f"modifier {m.name} cannot exceed 1.0"})
            elif m.kind == "reduce_only" and m.name not in rail_names:
                f.append({"check": "G4_REDUCE_ONLY_MEASURED", "why": f"reduce-only modifier {m.name} is not a registered rail"})
            elif m.kind not in ("two_sided", "reduce_only", "integrity"):
                f.append({"check": "G4_KIND", "why": f"modifier {m.name} has unknown kind {m.kind}"})
    except Exception as exc:
        f.append({"check": "G4_TWO_SIDED", "why": f"registry unreadable: {exc}"})

    # G5 -- every rail measured
    try:
        from libs.portfolio.rails import RAILS
        from research import missed_growth
        for r in RAILS:
            if r.measure not in missed_growth.MEASURES:
                f.append({"check": "G5_RAIL_MEASURED", "why": f"rail {r.name} has no measurement {r.measure}"})
    except Exception as exc:
        f.append({"check": "G5_RAIL_MEASURED", "why": f"rails/missed_growth unreadable: {exc}"})

    # G6 -- no Sharpe ranking in capital-authority modules
    for rel in ("desks/mt5/mt5desk/gateway.py", "desks/mt5/research/pf_allocator.py",
                "desks/mt5/research/promoter.py"):
        s = _src(rel)
        for m in re.finditer(r"sort(?:ed)?\([^\n]*sharpe", s, flags=re.IGNORECASE):
            f.append({"check": "G6_NO_SHARPE_RANKING", "why": f"{rel}: {m.group(0)[:80]}"})

    # G7 -- the rules on every surface
    for rel in SURFACES:
        s = _src(rel)
        if RULE_1 not in s or RULE_2 not in s:
            f.append({"check": "G7_RULES_ON_SURFACE", "why": f"{rel} does not carry both rules verbatim"})
    return f


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    findings = check()
    if a.json:
        print(json.dumps({"ok": not findings, "findings": findings}, indent=1))
    else:
        print(f"growth governance: {'OK' if not findings else f'{len(findings)} breach(es)'}")
        for x in findings:
            print(f"  BREACH {x['check']}: {x['why']}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
