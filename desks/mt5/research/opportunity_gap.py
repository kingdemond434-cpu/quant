#!/usr/bin/env python3
"""P66 / P81 / P50 -- THE OPPORTUNITY GAP, DECOMPOSED BY CAUSE.

G is the distance between what this desk could be earning and what it is. A single number for G
is useless: it is always large and it never says what to do. The decomposition is the product.

WHY THE CAUSES ARE THESE. Each is a place the chain from "an edge exists in the market" to "the
book earns it" can break, and they demand completely different work:

    SUPPLY      not enough candidates arrive. Fix: mine wider.
    CONVERSION  candidates arrive and die in the funnel. Fix: find which stage kills them.
    BREADTH     candidates survive but are all the same bet, so N_eff does not move however many
                certify. Fix: hunt orthogonal families -- more of the same family cannot help.
    CAPITAL     certified, matured, and no money behind it. Fix: the allocator or the admission.
    EXECUTION   money behind it and the fill gives the edge back. Fix: the execution twin.
    DELIVERY    all of the above fixed, on a branch the trading box never pulled. Fix: the wire.
    LATENCY     the fix exists and arrives too late to matter. Fix: the clock, not the alpha.

DELIVERY IS ON THIS LIST BECAUSE IT WAS THE BINDING ONE. Measured 2026-09-06: the box's sync had
been logging `push rejected, fetch+merge and retry` and then nothing, roughly 800 consecutive
times since 08-26. Every desk fix in that window was real, tested, merged -- and reached no
machine. A desk that only decomposes G into research causes will spend forever improving research
while the binding constraint sits in the wire, and it will never once look there.

P81 -- THE QUANT INTELLIGENCE SCORE is a REPORTING NUMBER AND NEVER A CAPITAL INPUT. It exists so
the desk can see whether it is getting better at being a desk. The moment a score like this is
allowed to size a position it becomes a thing to game, and the desk starts optimising the
scoreboard instead of the book. `capital_input: False` is asserted in the artifact and fenced in
the tests.

P50 -- THE DIGITAL TWIN. The same decomposition read the other way: a model OF the research
organisation, in the organisation's own units. It answers "where does an extra hour go furthest"
rather than "how much did we make", and those have different answers almost always.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
REPORT = BASE / "reports" / "OPPORTUNITY_GAP.json"

#: A cause is BINDING when its own measure says the chain stops there. Ordered as the chain runs,
#: because the earliest broken link is the one to fix -- improving conversion behind a supply
#: famine, or breadth behind a delivery outage, is work that cannot show up in the book.
CAUSES: tuple[str, ...] = (
    "SUPPLY", "CONVERSION", "BREADTH", "CAPITAL", "EXECUTION", "DELIVERY", "LATENCY",
)


@dataclass
class Component:
    """One cause, its measurement, and what it would take to close it."""

    cause: str
    measured: Any
    binding: bool
    why: str
    close_it: str
    unmeasured_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"cause": self.cause, "measured": self.measured, "binding": self.binding,
                "why": self.why, "close_it": self.close_it,
                "status": "UNMEASURED" if self.unmeasured_reason else "MEASURED",
                "unmeasured_reason": self.unmeasured_reason}


def _read(p: Path) -> dict[str, Any]:
    try:
        v = json.loads(p.read_text("utf-8"))
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def decompose() -> list[Component]:
    """Measure every cause from the artifacts that already exist. Never invent a number."""
    state = _read(ROOT / "web" / "desk_state.json")
    pipe = state.get("pipeline") or {}
    breadth = (state.get("breadth") or {}).get("book_breadth") or {}
    box = (state.get("health") or {}).get("box") or {}
    miners = (state.get("breadth") or {}).get("miners") or {}
    out: list[Component] = []

    docket = _num(pipe.get("docket_candidates"))
    out.append(Component(
        "SUPPLY", docket, binding=bool(docket is not None and docket < 200),
        why=("candidates waiting to be judged. At depth, supply is not the constraint -- "
             "throughput is, and mining harder cannot help"),
        close_it="widen the hunt universe and the timeframe ladder",
        unmeasured_reason=None if docket is not None else "no docket count published"))

    judged = _num(pipe.get("gauntlet_last_judged"))
    # `a or b` IS WRONG HERE AND ZERO IS THE CASE THAT MATTERS. `_num(0) or _num(x)` falls
    # through to x, so a genuine "0 certificates" -- the desk's actual state on 2026-09-06 and
    # the single most important reading this decomposition can take -- was silently replaced by
    # whatever the other source said. Falsy-zero turns the alarm into its own opposite.
    certified = _num(pipe.get("certified"))
    if certified is None:
        certified = _num(breadth.get("certificates"))
    conv = (certified / docket) if (certified is not None and docket) else None
    out.append(Component(
        "CONVERSION", None if conv is None else round(conv, 6),
        binding=bool(conv is not None and conv < 0.001),
        why=(f"{int(certified or 0)} certificates from a {int(docket or 0)}-candidate docket; "
             f"the last gauntlet pass judged {int(judged or 0)}. Throughput, not supply, is what "
             "empties a docket this deep"),
        close_it="raise gauntlet throughput; find which of the ten gates kills the most",
        unmeasured_reason=None if conv is not None else "no certificate count to divide by"))

    conc = _num(breadth.get("family_concentration"))
    out.append(Component(
        "BREADTH", conc, binding=bool(conc is not None and conc > 0.8),
        why=("share of certificates in the single largest family. Near 1.0 means every "
             "certificate is one bet and no amount of mining inside that family raises N_eff"),
        close_it="hunt the absent orthogonal families -- carry, relative value, vol transition",
        unmeasured_reason=None if conc is not None else
        "no certificates, so concentration is undefined; it becomes binding the moment "
        "the book is non-empty"))

    ready, live = _num(pipe.get("promotion_ready")), _num(pipe.get("live"))
    out.append(Component(
        "CAPITAL", None if ready is None else (ready - (live or 0)),
        binding=bool(ready and not live),
        why=(f"{int(ready or 0)} sleeve(s) matured and promotable, {int(live or 0)} carrying "
             "capital. A promotable sleeve with no money behind it earns exactly nothing"),
        close_it="pf_allocation fresh and MEASURED, then admission",
        unmeasured_reason=None if ready is not None else "no promotion count published"))

    ex = state.get("execution") or {}
    out.append(Component(
        "EXECUTION", ex.get("matched_fills"),
        binding=ex.get("markout_usable") is not True,
        why=("markout needs matched fills to say whether the fill gives the edge back. Without "
             "it, execution cost is an assumption and the book is sized on gross returns"),
        close_it="record fills against decisions until markout is usable",
        unmeasured_reason=None if ex.get("markout_usable") is True else
        (ex.get("why") or "markout not usable; execution cost is unmeasured, not zero")))

    silent = _num(box.get("silent_seconds"))
    out.append(Component(
        "DELIVERY", None if silent is None else round(silent / 3600, 1),
        binding=bool(silent is not None and silent > 3600),
        why=("hours since the trading box last reported. Every fix in that window is real, "
             "tested, merged -- and on no machine. This cause is on the list because it was the "
             "binding one: ~800 consecutive sync passes published nothing and said nothing"),
        close_it="the box pulls and its sync publishes; verify by a fresh state timestamp",
        unmeasured_reason=None if silent is not None else "box publishes no readable clock"))

    zero = len([m for m in miners.values() if not (m or {}).get("survivors")])
    out.append(Component(
        "LATENCY", zero, binding=bool(zero and zero > len(miners) * 0.5),
        why=(f"{zero} of {len(miners)} miners produced rows and no survivor in the window. "
             "Compute spent on lines that do not convert is capacity not spent on lines that do"),
        close_it="retire or repair zero-yield miners; the register owns that decision",
        unmeasured_reason=None if miners else "no miner conversion measured"))
    return out


def score(components: list[Component]) -> dict[str, Any]:
    """P81. A REPORTING NUMBER. Never an input to sizing, and it says so in its own artifact."""
    measured = [c for c in components if not c.unmeasured_reason]
    binding = [c for c in components if c.binding]
    closed = len(measured) - len(binding)
    return {
        "quant_intelligence_score": (round(100 * closed / len(components), 1)
                                     if components else None),
        "of_possible": 100,
        "measured_causes": len(measured),
        "unmeasured_causes": len(components) - len(measured),
        "binding_causes": [c.cause for c in binding],
        "capital_input": False,
        "why_never_capital": (
            "The moment a score like this can size a position it becomes a thing to game, and "
            "the desk starts optimising the scoreboard instead of the book. It exists so the "
            "desk can see whether it is getting better at being a desk, and for nothing else."),
        "reading": ("the share of the chain from 'an edge exists' to 'the book earns it' that is "
                    "both measured and not currently the binding constraint"),
    }


def run() -> dict[str, Any]:
    comps = decompose()
    binding = [c for c in comps if c.binding]
    return {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "components": [c.as_dict() for c in comps],
        "binding": [c.cause for c in binding],
        "first_binding": binding[0].cause if binding else None,
        "next_action": binding[0].close_it if binding else
        "no cause reports itself binding; the chain's limit is not currently visible here",
        "order_matters": (
            "Causes are listed in the order the chain runs, and the EARLIEST broken link is the "
            "one to fix. Improving conversion behind a supply famine, or breadth behind a "
            "delivery outage, is work that cannot reach the book however well it is done."),
        "intelligence": score(comps),
    }


def main(argv: list[str] | None = None) -> int:
    doc = run()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"opportunity gap: {len(doc['binding'])} binding cause(s) of {len(CAUSES)}")
    for c in doc["components"]:
        mark = "BINDING " if c["binding"] else ("UNMEAS  " if c["status"] == "UNMEASURED"
                                                else "ok      ")
        val = c["measured"] if c["measured"] is not None else "-"
        print(f"   {mark} {c['cause']:11} {val!s:>10}   {c['why'][:76]}")
    if doc["first_binding"]:
        print(f"\n   FIRST BINDING: {doc['first_binding']} -> {doc['next_action']}")
    qis = doc["intelligence"]
    print(f"   quant intelligence score: {qis['quant_intelligence_score']}/100 "
          f"(reporting only; capital_input={qis['capital_input']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
