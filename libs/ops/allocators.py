"""THE SIX NESTED ALLOCATORS, and the one currency all of them spend.

    "All six optimize a common currency: dE[log W] after uncertainty/cost. That is probably the
     most important architectural addition of this entire answer."   -- the principal, 2026-09-05

WHY A SPINE RATHER THAN ANOTHER ORGAN. The desk already allocates in six places and has never
said so in one place, so five of the six are invisible as allocation decisions and none of them
can be compared to the others. `pf_allocator` spends heat and knows it is spending heat;
`libs.research.bandit` spends research effort and thinks of itself as a bandit; the seat spends
tokens and thinks of itself as a budget; `data_prospector` spends acquisition effort and thinks
of itself as a hunter. Same question six times -- WHAT IS THE NEXT UNIT OF THIS RESOURCE WORTH IN
LOG-WEALTH PER DAY -- and six vocabularies, so a euro of compute and a euro of heat could never
be traded against each other.

    0  FRONTIER      which external capability do we replicate?  dElog per unit of build effort
    1  INFORMATION   which data do we acquire?          dElog per unit of acquisition + carry
    2  RESEARCH      which hypothesis do we test?       dElog per unit of research effort
    3  COMPUTE       which experiments get resources?   dElog per CPU/GPU hour
    4  FORECAST      which models influence beliefs?    dElog per unit of belief weight
    5  CAPITAL       which opportunities get money?     dElog per unit of heat
    6  EXECUTION     how is each position implemented?  dElog per unit of alpha capture

THE SEVENTH SITS ABOVE THE OTHER SIX (principal 2026-09-05). Every level below asks how to spend
a resource the desk already has; FRONTIER asks which CAPABILITY the desk should acquire in the
first place -- the only level whose answers come from outside. A desk with all six lower levels
working perfectly still converges on the frontier of what it already knows how to do, and the
seventh is what keeps that from being the ceiling. It is level 0 rather than 7 because it feeds
information: a replicated capability arrives as new data, new method or new machinery, and is
spent by the levels below in their own currencies.

NESTED, NOT PARALLEL, and the order is the dependency: the frontier feeds information, information
feeds research, research consumes compute, compute produces forecasts, forecasts earn capital,
capital is realised through execution. A gain at level k is worthless if level k+1 cannot
carry it -- which is exactly the
failure this desk keeps measuring. 119,902 unread miner rows was an INFORMATION allocator with no
downstream; 65 unexecutable certificates was a CAPITAL decision no EXECUTION allocator could
implement; a deepening queue nothing drained was RESEARCH starved of COMPUTE.

WHAT THIS MODULE DOES AND DOES NOT DO. It does not allocate anything. It declares, for each
level: the question, the currency, the module that actually decides, the ledger that prices the
decision, and -- read live -- whether that ledger exists on this host. That turns "are we
allocating compute well?" from an opinion into a lookup, and it turns every future proposal into
a question with an address: WHICH ALLOCATOR does this improve, and what dElog does it buy? A
feature that cannot name its level does not belong in the machine.

THE HONEST STATE IS THE POINT. Two of the six are wired to a real measured ledger today and four
are not, and this reports that rather than smoothing it. A spine that claimed six healthy
allocators would be worth less than nothing: the desk would stop looking for the four.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

#: The currency every level spends, named once. `dElog` is expected log-wealth per day AFTER
#: uncertainty and cost -- the same quantity `pf_allocator.marginal_admission` computes for a
#: capital candidate, so a research hour and a unit of heat are quoted in comparable units even
#: where one of them is not yet measured.
CURRENCY = "dE[log W] per day, after uncertainty and cost"

WIRED, MEASURED, UNWIRED = "WIRED", "MEASURED", "UNWIRED"


@dataclass(frozen=True)
class Allocator:
    """One level: what it decides, in what units, who decides it, and what prices the decision."""

    level: int
    name: str
    question: str
    #: The resource this level spends. Named, because a level whose resource is vague cannot be
    #: rationed -- "research quality" is not a resource, "research hours" is.
    resource: str
    #: The module that actually makes the decision today. Empty means nothing does, which is the
    #: single most useful thing this file can say about a level.
    decides: str
    #: Artifacts that PRICE the decision in the common currency. All must exist for MEASURED.
    prices: tuple[str, ...]
    #: What is missing before this level is measured, in one sentence a person can act on.
    gap: str = ""
    #: Levels immediately downstream. A gain here is unrealisable if these cannot carry it.
    feeds: tuple[str, ...] = field(default_factory=tuple)


ALLOCATORS: tuple[Allocator, ...] = (
    Allocator(
        0, "frontier", "Which external capability deserves replication effort?",
        "build effort against capabilities the desk does not have at all",
        "desks/mt5/frontier_intel/frontier_supervisor.py",
        ("desks/mt5/reports/FRONTIER_INTELLIGENCE.json", "desks/mt5/reports/FRONTIER_GAPS.json"),
        gap=("the ROI ranking is live and refuses more than it queues -- which is its job -- but "
             "no imported capability has reached PROVEN, so `frontier_intel`'s own rent is "
             "UNMEASURED and the mapping from a replicated capability to realised dE[log W] is "
             "still a claim rather than a measurement. It closes the first time a queued "
             "candidate is built, challenged and beaten or beats its champion"),
        feeds=("information",)),
    Allocator(
        1, "information", "Which data do we acquire next?",
        "acquisition effort and carrying cost per source",
        "desks/mt5/research/data_prospector.py",
        ("desks/mt5/reports/DATA_PROSPECTOR.json", "desks/mt5/reports/MODULE_RENT.json"),
        gap=("a source's rent is billed through the RESEARCH_PNL rows its hypotheses land on, so "
             "a source that has produced no certificate yet is UNMEASURED rather than worthless. "
             "What closes it is the ABLATION the principal asked for: train with and without the "
             "source and difference the two, which needs the source's own feature set versioned"),
        feeds=("research",)),
    Allocator(
        2, "research", "Which hypothesis do we test next?",
        "research passes: gauntlet cells, deepening tasks, sweep cells",
        "libs/research/bandit.py",
        ("desks/mt5/reports/RESEARCH_BANDIT.json", "desks/mt5/reports/RESEARCH_PNL.json"),
        gap=("the arms are billed on the growth their certificates carry in the FUNDED book, so "
             "an arm whose survivors are all still on forward clocks reads UNMEASURED. This is "
             "the level nearest to being measured -- it needs funded survivors, not new code"),
        feeds=("compute",)),
    Allocator(
        3, "compute", "Which experiments and models get the machine?",
        "wall-clock and CPU seconds -- the unit this box actually spends, not GPU hours it has "
        "none of",
        "libs/ops/compute_ledger.py",
        ("desks/mt5/data/compute_ledger.jsonl", "desks/mt5/reports/RESEARCH_PNL.json"),
        gap=("THE DENOMINATOR NOW EXISTS AND THE NUMERATOR DOES NOT YET. Until 2026-09-05 nothing "
             "decided this level and nothing could: the ranking divides by hours and no run had "
             "ever recorded an hour, so shipping the formula would have produced a confident "
             "ordering of made-up numbers. `compute_ledger` costs every leg of the hourly cycle "
             "-- where most of the desk\'s compute is actually spent -- so hours per run "
             "accumulate with no new schedule and no new process. What remains is the join: "
             "`rank()` takes `run -> expected dElog` from whoever knows (RESEARCH_PNL for a "
             "research arm, the rent ledger for an organ) and refuses to invent it, listing a "
             "costed run with no value as UNPRICED rather than ranking it"),
        feeds=("forecast",)),
    Allocator(
        4, "forecast", "Which models are allowed to move a belief?",
        "belief weight in the blended forecast",
        "",
        ("desks/mt5/data/pf_forecast_log.jsonl", "data/forecast_log.json"),
        gap=("FUSED INTO LEVEL 5 ON THIS DESK TODAY, and that is a finding rather than an "
             "omission. A forecast allocator weights PREDICTIVE OBJECTS, and every predictive "
             "object here is itself a sleeve -- a certified edge whose forecast is 'this will "
             "earn mu per day' -- so `pf_allocator` already weights them by measured evidence "
             "and there is no second class of object to weight. The level separates the day a "
             "MODEL predicts a sleeve\'s return rather than being one (a return head, a "
             "conditional forecaster, an ensemble over several), and not before: a marketplace "
             "over one kind of participant is a marketplace in name only. What EXISTS today is "
             "the measurement half -- `pf_forecast_log.jsonl` records the book forecast and "
             "`libs/self_improvement/forecast_calibration.py` scores probability claims -- and "
             "the honest first step is calibrating the allocator\'s OWN forecast against "
             "realised growth, because if `expected_log_per_day` is systematically optimistic "
             "then every heat decision downstream is wrong by the same bias"),
        feeds=("capital",)),
    Allocator(
        5, "capital", "Which opportunities get money, and how much?",
        "heat, inside the mandated floor and the measured ceiling",
        "desks/mt5/research/pf_allocator.py",
        ("desks/mt5/reports/pf_allocation.json", "desks/mt5/reports/ALLOCATOR_PROOF.json"),
        gap="",  # measured when both artifacts are present: this is the level that works
        feeds=("execution",)),
    Allocator(
        6, "execution", "How is each position actually implemented?",
        "alpha capture: the fraction of predicted edge that survives the fill",
        "desks/mt5/mt5desk/execution_registry.py",
        ("desks/mt5/data/execution_algo_outcomes.jsonl", "desks/mt5/reports/ALPHA_CAPTURE.json"),
        gap=("the registry competes algorithms on realised cost against the market baseline, "
             "which IS a measured allocation -- but routing stays MARKET until the fill surface "
             "is fitted on enough of the box's own fills, so today it scores a choice it does "
             "not yet make"),
        feeds=()),
)

#: Level name -> the allocator, for the dependency walk.
BY_NAME: dict[str, Allocator] = {a.name: a for a in ALLOCATORS}


def status(root: Path | None = None) -> dict[str, dict[str, Any]]:
    """Each level's live state on this host. Reads only; invents nothing.

        MEASURED  a decider exists AND every pricing artifact is present
        WIRED     a decider exists, some pricing artifact is not on this host
        UNWIRED   nothing decides this level at all -- the resource is spent by whatever asks

    UNWIRED IS NOT A SEVERE VERSION OF WIRED. A wired level makes a decision the desk can grade
    later; an unwired one makes the decision anyway, by arrival order, and records nothing. The
    second is the one that cannot improve.
    """
    base = ROOT if root is None else Path(root)
    out: dict[str, dict[str, Any]] = {}
    for a in ALLOCATORS:
        decider = (base / a.decides) if a.decides else None
        has_decider = bool(a.decides) and decider is not None and decider.exists()
        present = [p for p in a.prices if (base / p).exists()]
        missing = [p for p in a.prices if p not in present]
        state = (MEASURED if has_decider and not missing
                 else WIRED if has_decider else UNWIRED)
        out[a.name] = {
            "level": a.level, "question": a.question, "resource": a.resource,
            "currency": CURRENCY, "decides": a.decides or None,
            "decider_present": has_decider,
            "prices": list(a.prices), "prices_present": present, "prices_missing": missing,
            "status": state,
            "gap": a.gap,
            "feeds": list(a.feeds),
        }
    # A GAIN AT LEVEL k IS WORTHLESS IF k+1 CANNOT CARRY IT, and that is not a metaphor: it is
    # every large defect this desk has measured. Reported per level so the reader sees which
    # improvements are currently un-bankable rather than having to trace the chain by hand.
    for row in out.values():
        blocked = [f for f in row["feeds"] if out.get(f, {}).get("status") == UNWIRED]
        row["downstream_unwired"] = blocked
        if blocked:
            row["carries"] = (f"a gain here cannot be banked: {', '.join(blocked)} is UNWIRED, so "
                              f"nothing downstream can spend what this level would win")
    return out


def report(root: Path | None = None) -> dict[str, Any]:
    """The artifact a person and the governor both read."""
    rows = status(root)
    counts = {s: sum(1 for r in rows.values() if r["status"] == s)
              for s in (MEASURED, WIRED, UNWIRED)}
    return {
        "currency": CURRENCY,
        "rule": ("every proposal must name the allocator it improves and the dE[log W] it buys; "
                 "one that cannot name a level does not belong in the machine"),
        "levels": rows,
        "counts": counts,
        "weakest_link": next((n for n, r in sorted(rows.items(), key=lambda kv: kv[1]["level"])
                              if r["status"] == UNWIRED), ""),
    }


def main(argv: list[str] | None = None) -> int:
    doc = report()
    out = ROOT / "desks" / "mt5" / "reports" / "ALLOCATOR_STACK.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1), "utf-8")
    for name, row in sorted(doc["levels"].items(), key=lambda kv: kv[1]["level"]):
        print(f"  {row['level']}. {name:12s} {row['status']:9s} {row['resource']}")
        if row["gap"]:
            print(f"       gap: {row['gap'][:150]}")
    print(f"allocator stack: {doc['counts'][MEASURED]} measured, {doc['counts'][WIRED]} wired, "
          f"{doc['counts'][UNWIRED]} unwired -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
