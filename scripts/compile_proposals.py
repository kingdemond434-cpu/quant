"""Proposals and audits become runnable cells, or a named refusal. Nothing sits in a queue.

WHY THIS EXISTS (principal, 2026-08-29)

    "so all research proposals -- who will implement them"
    "and all audits and recommendations by the openrouters -- who will"

Nobody, and that was the honest answer. The free panel writes `NAME | MECHANISM | PAYER | TEST |
KILL` into `hypothesis_queue.jsonl` and audit recommendations into a report, and both were
terminal: a human read them or nothing happened. A research role whose output nobody consumes is
the same defect as a role that never runs, wearing a more convincing artifact.

THIS IS THE CONSUMER. Two paths, and a proposal takes exactly one:

    COMPILED   the proposal maps onto a semantic coordinate `family_generic` can execute, so it
               becomes a docket cell today. No code is generated, nothing a model returned is
               executed -- the mapping picks five axis values and the family is already written.
    REFUSED    the proposal needs something the generic family cannot express (a cross-sectional
               rank, a multi-leg spread, options data the desk does not have). It is recorded
               with the reason and the missing capability NAMED, which is a research finding in
               itself: a queue of refusals is a list of what to build next.

REFUSING BY NAME IS THE LOAD-BEARING PART. An approximation would enter the docket as if it were
the proposal, and the gauntlet would judge something nobody meant to test -- then the result would
be attributed to the mechanism. That is worse than not testing it, because it produces a
confident wrong answer about an idea that was never tried.

AUDIT RECOMMENDATIONS BECOME EXPLORATION PRIORS, not prose. When the cold auditor names a region
worth searching, that region's coordinates are enumerated and queued. A recommendation that stays
a paragraph changes nothing; a recommendation that becomes cells changes where the next trials go.

NOTHING COMPILED HERE HAS ANY AUTHORITY. Cells enter the docket where every other candidate does
and face the identical gauntlet. A free model's idea is exactly as unprivileged as a parameter
sweep's, which is what makes running weak models safe.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DESK = ROOT / "desks" / "mt5"
sys.path.insert(0, str(DESK))

QUEUE = ROOT / "data" / "hypothesis_queue.jsonl"
FREE = ROOT / "data" / "free_research.json"
COMPILED = DESK / "data" / "hypotheses" / "compiled_proposals.json"
OUT = ROOT / "data" / "proposal_compiler.json"

#: Words in a proposal that map to a semantic EVENT. Matched against the whole record, because a
#: model names the mechanism in the text rather than in a field.
_EVENT_WORDS: dict[str, tuple[str, ...]] = {
    "benchmark_flow": ("fix", "fixing", "benchmark", "rebalanc", "index", "close auction"),
    "options_hedging": ("gamma", "vega", "option", "hedg", "expiry", "dealer"),
    "liquidity_shock": ("liquidity", "spread", "depth", "illiquid", "thin"),
    "volatility_shock": ("volatility", "vol spike", "variance", "realized vol"),
    "forced_deleveraging": ("margin", "liquidation", "deleverag", "forced", "stop-out"),
    "inventory_rebalance": ("inventory", "imbalance", "flow", "positioning pressure"),
    "macro_release": ("macro", "cpi", "nfp", "central bank", "release", "announcement"),
    "carry_change": ("carry", "swap", "rate differential", "roll", "basis"),
    "cross_market_move": ("cross", "lead", "lag", "correlat", "spillover", "transmission"),
    "positioning_extreme": ("cot", "positioning", "crowd", "extreme", "sentiment"),
    "session_transition": ("session", "open", "handoff", "asia", "tokyo", "london", "overnight"),
}

_CONTEXT_WORDS: dict[str, tuple[str, ...]] = {
    "asia": ("asia", "tokyo", "overnight"),
    "london": ("london", "european", "euro session"),
    "new_york": ("new york", "us session", "ny ", "comex", "cme"),
    "overlap": ("overlap",),
    "high_vol": ("high volatility", "elevated vol", "stressed"),
    "low_vol": ("low volatility", "quiet", "calm"),
    "month_end": ("month-end", "month end", "quarter-end", "dividend record"),
    "high_liquidity": ("liquid", "deep"),
    "low_liquidity": ("thin", "illiquid"),
}

_DIRECTION_WORDS: dict[str, tuple[str, ...]] = {
    "reversal": ("revers", "mean revert", "decay", "unwind", "correct", "fade", "pressure clears"),
    "continuation": ("continu", "momentum", "persist", "drift", "trend", "extend"),
    "convergence": ("converg", "narrow", "spread compress"),
    "divergence": ("diverg", "widen", "decoupl"),
}

#: Capabilities the generic family cannot express. Naming them turns a refusal into a build list.
_UNSUPPORTED: dict[str, tuple[str, ...]] = {
    "cross_sectional_rank": ("rank", "cross-section", "universe-wide", "percentile across"),
    "multi_leg_spread": ("spread between", "pair trade", "leg", "basket", "relative value"),
    "options_data": ("implied vol", "iv ", "skew", "open interest", "gamma exposure"),
    "order_flow_data": ("order book", "depth of book", "tick flow", "aggressor"),
    "sub_hourly": ("1m", "5m", "15m", "minute bar", "30-minute", "final 30"),
}


def _match(text: str, table: dict[str, tuple[str, ...]]) -> str | None:
    t = text.lower()
    best, best_hits = None, 0
    for key, words in table.items():
        hits = sum(1 for w in words if w in t)
        if hits > best_hits:
            best, best_hits = key, hits
    return best


def _unsupported(text: str) -> list[str]:
    t = text.lower()
    return [k for k, words in _UNSUPPORTED.items() if any(w in t for w in words)]


def compile_proposal(rec: dict[str, Any], supported: dict[str, list[str]]) -> dict[str, Any]:
    """One proposal -> a runnable cell spec, or a refusal that names what is missing."""
    text = " ".join(str(rec.get(f, "")) for f in ("name", "mechanism", "payer", "test", "kill"))
    missing = _unsupported(text)
    if missing:
        return {"name": rec.get("name"), "compiled": False, "missing_capability": missing,
                "why": (f"needs {', '.join(missing)}, which family_generic cannot express. "
                        f"Recorded rather than approximated: an approximation would enter the "
                        f"docket as if it were this proposal and the gauntlet would judge "
                        f"something nobody meant to test.")}

    event = _match(text, _EVENT_WORDS)
    context = _match(text, _CONTEXT_WORDS)
    direction = _match(text, _DIRECTION_WORDS)
    unresolved = [n for n, v in (("event", event), ("direction", direction)) if not v]
    if unresolved:
        return {"name": rec.get("name"), "compiled": False, "missing_capability": [],
                "why": (f"could not resolve {unresolved} from the proposal text. The axis is the "
                        f"claim: guessing 'continuation' for a mechanism that never said so would "
                        f"test the opposite of the hypothesis half the time.")}

    context = context or "asia"
    if event not in supported["event"] or direction not in supported["direction"]:
        return {"name": rec.get("name"), "compiled": False,
                "missing_capability": [f"event:{event}"],
                "why": f"{event}/{direction} is outside family_generic's vocabulary"}

    return {"name": rec.get("name"), "compiled": True,
            "family": "generic",
            "params": {"event": event, "context": context, "direction": direction,
                       "output": "1h", "quality_atr": 1.0},
            "coordinate": f"{event}|{context}|magnitude|{direction}|1h",
            "payer": rec.get("payer"), "kill": rec.get("kill"),
            "promotion_authority": False}


def main() -> int:
    from mt5desk.family_generic import supported as generic_supported

    now = datetime.now(tz=UTC)
    sup = generic_supported()

    props: list[dict[str, Any]] = []
    if QUEUE.exists():
        for line in QUEUE.read_text("utf-8").splitlines():
            try:
                props.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    # AUDIT RECOMMENDATIONS BECOME CELLS, NOT PROSE. A named region is enumerated into the same
    # coordinate shape a proposal compiles to, so a recommendation changes where trials go.
    audit_cells: list[dict[str, Any]] = []
    try:
        free = json.loads(FREE.read_text("utf-8"))
        for res in free.get("results", []):
            for row in res.get("regions", []) or []:
                region = str(row.get("region", "")).strip()
                m = re.match(r"^([a-z_]+)\s*\|?\s*([a-z_]*)", region.lower())
                if not m:
                    continue
                ev, dr = m.group(1), (m.group(2) or "continuation")
                if ev in sup["event"] and dr in sup["direction"]:
                    audit_cells.append({
                        "name": f"audit:{ev}|{dr}", "compiled": True, "family": "generic",
                        "params": {"event": ev, "context": "asia", "direction": dr,
                                   "output": "1h", "quality_atr": 1.0},
                        "coordinate": f"{ev}|asia|magnitude|{dr}|1h",
                        "source": "cold_audit_recommendation",
                        "promotion_authority": False})
    except (OSError, json.JSONDecodeError):
        pass

    results = [compile_proposal(p, sup) for p in props]
    ok = [r for r in results if r.get("compiled")] + audit_cells
    refused = [r for r in results if not r.get("compiled")]

    print(f"PROPOSAL COMPILER {now.isoformat(timespec='seconds')}")
    print(f"  queue: {len(props)} proposal(s), audit regions: {len(audit_cells)}")
    print(f"  COMPILED {len(ok)}   REFUSED {len(refused)}")
    for r in ok[:10]:
        print(f"    ok   {str(r.get('name'))[:34]:36s} {r['coordinate']}")
    for r in refused[:10]:
        miss = ",".join(r.get("missing_capability") or []) or "axis unresolved"
        print(f"    --   {str(r.get('name'))[:34]:36s} [{miss}]")
        print(f"         {r['why'][:120]}")

    COMPILED.parent.mkdir(parents=True, exist_ok=True)
    COMPILED.write_text(json.dumps({"built_at": now.isoformat(timespec="seconds"),
                                    "cells": ok}, indent=1), "utf-8")
    OUT.write_text(json.dumps({"ran_at": now.isoformat(timespec="seconds"),
                               "compiled": len(ok), "refused": len(refused),
                               "refusals": refused,
                               "missing_capabilities": sorted({m for r in refused
                                                               for m in (r.get("missing_capability")
                                                                         or [])}),
                               "note": ("a refusal names the capability to build next; "
                                        "approximating would put a wrong answer in the docket "
                                        "under the proposal's name")}, indent=1), "utf-8")
    print(f"\n  -> {COMPILED}")
    print(f"  -> {OUT}")
    if refused:
        gaps = sorted({m for r in refused for m in (r.get("missing_capability") or [])})
        if gaps:
            print(f"\n  BUILD LIST (capabilities refusals are waiting on): {gaps}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
