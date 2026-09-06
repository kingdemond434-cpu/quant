#!/usr/bin/env python3
"""P18 / P19 / P65 / P29 / P30 -- WHICH EXPERIMENT, AT WHAT CAPITAL, AND WHO IS RIGHT.

P18 -- ACTIVE LEARNING / EVSI. The desk cannot run every experiment, so the question is never
"is this worth knowing" (almost everything is) but "what is knowing it WORTH, minus what finding
out COSTS". Expected value of sample information:

    EVSI = P(the answer changes the decision) x (value of the better decision) - cost

The first factor is the one desks skip, and skipping it is why research backlogs fill with
questions whose every possible answer leads to the same action. An experiment that cannot change
what you do is not cheap, it is free of value at positive cost.

P19 -- THE MEASUREMENT-DESIGN BRAIN: the CHEAPEST FALSIFYING experiment, not the most thorough
confirming one. Given a hypothesis, the useful design is the one that could most easily prove it
wrong for the least compute. A confirming test that a false hypothesis would also pass carries no
information however expensive it was (L1.63), and thoroughness is not the same as power.

P65 -- THEORY VS EMPIRICS ARBITRATOR. Two independent probabilities, kept separate on purpose:

    P(mechanism)      is there a reason this SHOULD work -- a structural story about who is on
                      the other side and why they keep losing
    P(empirical)      does the data say it DID work, after multiplicity and cost

They disagree constantly and the disagreement is the signal. High empirics with no mechanism is
the classic overfit: something that worked and nobody can say why. High mechanism with no
empirics is a story: plausible, untested, and the most seductive thing on a research desk. The
arbitrator names which case a candidate is in rather than collapsing both into one score, because
the two demand opposite responses -- one needs a harder test, the other needs a reason.

P29 -- CAPITAL-SCALE MORPHING. The tradeable universe is a FUNCTION OF q. A strategy whose edge
is 8bp per trade on a 0.1-lot fill is not the same strategy at 10 lots; it is usually not a
strategy at all. The desk must know which of its candidates survive at the capital it actually
has, and which only exist on paper at sizes it will never trade.

P30 -- THE SMALL-CAPACITY ALPHA DESK, SCORED AT OUR CAPITAL. The corollary, and the opportunity:
edges too small for an institution are exactly the ones nobody has arbitraged away. At this
desk's size a 40-lot-capacity edge is not "too small to matter", it is a moat -- but only if it
is scored at OUR size rather than at a size that makes it look respectable.
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
REPORT = BASE / "reports" / "EXPERIMENT_DESIGN.json"

#: An experiment whose EVSI is below this is not queued. Not zero: an experiment worth a
#: vanishing amount still costs a slot, and a queue full of near-zero items is a queue nobody
#: reads (L1.37).
MIN_EVSI = 0.01

#: Probabilities this far apart mean theory and empirics genuinely disagree, and the disagreement
#: is the finding. Inside it they are telling the same story and there is nothing to arbitrate.
DISAGREEMENT_GAP = 0.35

#: The desk's own capital, in account currency. EVERY capacity verdict is scored at THIS number.
#: Declared here rather than assumed at each call site, because a capacity study run at a
#: different size than the desk trades is a study of somebody else's desk.
DESK_CAPITAL = 750.0


@dataclass(frozen=True)
class Experiment:
    """One candidate experiment, with what it could change and what it costs."""

    name: str
    #: P(the result changes the decision). The factor desks skip.
    p_changes_decision: float
    #: Value of the better decision, in dElog units.
    decision_value: float
    #: Compute hours.
    cost_hours: float
    #: What the experiment would rule OUT. Empty means it is a confirming test.
    falsifies: str = ""


def evsi(e: Experiment, cost_per_hour: float = 0.02) -> dict[str, Any]:
    """P18. Expected value of sample information, minus its cost.

    `p_changes_decision` is first and it is the whole point. An experiment that cannot change
    what the desk does is not cheap -- it is free of value at positive cost, and a backlog full
    of them looks like a busy research programme.
    """
    gross = max(0.0, e.p_changes_decision) * e.decision_value
    cost = max(0.0, e.cost_hours) * cost_per_hour
    net = gross - cost
    return {
        "name": e.name, "evsi": round(net, 6), "gross": round(gross, 6), "cost": round(cost, 6),
        "queue": bool(net >= MIN_EVSI),
        "why": (f"changes the decision with p={e.p_changes_decision:.2f} at a value of "
                f"{e.decision_value:.3f}, costing {e.cost_hours:.1f}h"
                if net >= MIN_EVSI else
                f"net {net:+.4f} is below {MIN_EVSI}: "
                + ("no possible answer changes what the desk would do, so the experiment is free "
                   "of value at positive cost" if e.p_changes_decision < 0.05 else
                   "the decision it could change is not worth what it costs to run")),
    }


def cheapest_falsifier(candidates: list[Experiment],
                       cost_per_hour: float = 0.02) -> dict[str, Any]:
    """P19. The cheapest experiment that could prove the hypothesis WRONG.

    Confirming tests are excluded outright, not merely ranked last. A test a false hypothesis
    would also pass carries no information however thorough it was, and ranking it below a
    falsifier still leaves it in a queue where a busy week will run it.
    """
    falsifiers = [c for c in candidates if c.falsifies.strip()]
    confirming = [c.name for c in candidates if not c.falsifies.strip()]
    if not falsifiers:
        return {"status": "NONE_FALSIFYING", "excluded_confirming": confirming,
                "why": ("every proposed experiment is CONFIRMING. A test that a false hypothesis "
                        "would also pass carries no information however thorough it is (L1.63), "
                        "so none of these can settle anything")}
    ranked = sorted(falsifiers, key=lambda c: c.cost_hours)
    best = ranked[0]
    return {
        "status": "CHOSEN", "choice": best.name,
        "cost_hours": best.cost_hours, "falsifies": best.falsifies,
        "excluded_confirming": confirming,
        "considered": [{"name": c.name, "cost_hours": c.cost_hours, "falsifies": c.falsifies}
                       for c in ranked],
        "why": (f"{best.name} could rule out '{best.falsifies}' for {best.cost_hours:.1f}h, the "
                f"least of {len(falsifiers)} falsifying design(s). "
                + (f"{len(confirming)} confirming design(s) excluded outright: thoroughness is "
                   "not power." if confirming else "")),
    }


def arbitrate(p_mechanism: float, p_empirical: float) -> dict[str, Any]:
    """P65. Name which of the four cases a candidate is in. Never average them.

    Collapsing two probabilities into one score destroys exactly the information the pair
    carries: high empirics with no mechanism and high mechanism with no empirics average to the
    same middling number, and they demand opposite responses.
    """
    m, e = max(0.0, min(1.0, p_mechanism)), max(0.0, min(1.0, p_empirical))
    gap = e - m
    if abs(gap) < DISAGREEMENT_GAP:
        verdict = "AGREED_STRONG" if min(m, e) > 0.6 else (
            "AGREED_WEAK" if max(m, e) < 0.4 else "AGREED_MIDDLING")
        why = ("theory and empirics tell the same story; there is nothing to arbitrate and the "
               "candidate should be judged on that story's strength")
        action = ("proceed on the shared evidence" if verdict == "AGREED_STRONG"
                  else "drop -- neither the reason nor the data supports it"
                  if verdict == "AGREED_WEAK" else "gather more of both")
    elif gap > 0:
        verdict = "EMPIRICS_WITHOUT_MECHANISM"
        why = ("the data says it worked and nobody can say why. This is the classic overfit "
               "signature, and it is indistinguishable from a real discovery on the evidence "
               "so far")
        action = ("a HARDER TEST, not a bigger position: out-of-sample on an unseen instrument, "
                  "or a period the search never touched")
    else:
        verdict = "MECHANISM_WITHOUT_EMPIRICS"
        why = ("there is a reason it should work and the data does not show it. The most "
               "seductive state on a research desk, because the story survives every failed test")
        action = ("a REASON the effect would be hidden -- costs, capacity, regime -- or the "
                  "mechanism is wrong. Not more of the same test")
    return {"p_mechanism": round(m, 3), "p_empirical": round(e, 3), "gap": round(gap, 3),
            "verdict": verdict, "why": why, "next": action}


# --------------------------------------------------------------------------- P29 / P30
def capacity_curve(edge_bp: float, adv_lots: float,
                   sizes: tuple[float, ...] = (0.1, 0.5, 1, 5, 10, 50)) -> dict[str, Any]:
    """P29. The tradeable universe as a function of q.

    Impact grows superlinearly with participation; a square-root law is the standard first
    approximation and is used here because the alternative -- assuming NO impact -- is the error
    that makes every strategy look infinitely scalable.
    """
    rows = []
    for q in sizes:
        part = q / max(adv_lots, 1e-9)
        impact_bp = 10.0 * math.sqrt(max(part, 0.0))
        net = edge_bp - impact_bp
        rows.append({"lots": q, "participation": round(part, 5),
                     "impact_bp": round(impact_bp, 3), "net_bp": round(net, 3),
                     "viable": bool(net > 0)})
    viable = [r for r in rows if r["viable"]]
    return {"edge_bp": edge_bp, "adv_lots": adv_lots, "curve": rows,
            "max_viable_lots": max((r["lots"] for r in viable), default=0.0),
            "why": ("impact grows with the square root of participation. A strategy earning "
                    f"{edge_bp}bp per trade stops earning anything once impact reaches it, and "
                    "the size at which that happens is a property of the strategy, not a "
                    "detail of execution")}


def at_our_capital(edge_bp: float, adv_lots: float,
                   capital: float = DESK_CAPITAL) -> dict[str, Any]:
    """P30. Score the edge at THE DESK'S size, and say so when a small edge is a moat.

    Edges too small for an institution are exactly the ones nobody has arbitraged away. Scored at
    a size this desk will never trade, such an edge looks like noise; scored at OUR size it can
    be the best thing on the book.
    """
    lots = max(0.01, capital / 10_000.0)     # a conservative lots-per-currency-unit convention
    curve = capacity_curve(edge_bp, adv_lots, sizes=(lots,))
    row = curve["curve"][0]
    headroom = curve["max_viable_lots"] if curve["max_viable_lots"] else 0.0
    return {
        "capital": capital, "lots_at_our_size": round(lots, 4),
        "net_bp_at_our_size": row["net_bp"], "viable_here": row["viable"],
        "institutional_headroom_lots": headroom,
        "verdict": ("MOAT -- viable at our size and capacity-limited well below institutional "
                    "size, which is why nobody has competed it away"
                    if row["viable"] and headroom < 5 else
                    "viable at our size, and also at sizes that attract competition"
                    if row["viable"] else
                    "not viable even at our size; impact exceeds the edge before we reach one lot"),
        "why_our_size": ("An edge scored at a size this desk will never trade is a study of "
                         "somebody else's desk. Capacity is not a footnote to the edge, it is "
                         "part of whether the edge exists for us."),
    }


def run() -> dict[str, Any]:
    """A worked pass over the desk's own standing questions."""
    queue = [
        Experiment("recertify_unrunnable_certificates", 0.9, 0.20, 2.0,
                   falsifies="that the certificates carry a runnable parameterisation"),
        Experiment("widen_timeframe_ladder_to_M5", 0.6, 0.15, 6.0,
                   falsifies="that sub-hourly mechanisms survive the ten gates"),
        Experiment("re_backtest_every_certificate_again", 0.02, 0.30, 40.0),
        Experiment("measure_markout_on_recorded_fills", 0.8, 0.25, 1.0,
                   falsifies="that execution gives back less than the edge"),
    ]
    scored = [evsi(e) for e in queue]
    return {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "evsi": sorted(scored, key=lambda r: -r["evsi"]),
        "queued": [r["name"] for r in scored if r["queue"]],
        "design": cheapest_falsifier(queue),
        "arbitration_examples": {
            "overfit_signature": arbitrate(0.15, 0.85),
            "story_signature": arbitrate(0.85, 0.15),
            "agreed": arbitrate(0.75, 0.80),
        },
        "capacity": {"desk_capital": DESK_CAPITAL,
                     "example_small_edge": at_our_capital(edge_bp=8.0, adv_lots=40.0),
                     "example_crowded_edge": at_our_capital(edge_bp=1.0, adv_lots=100000.0)},
        "min_evsi": MIN_EVSI, "disagreement_gap": DISAGREEMENT_GAP,
    }


def main(argv: list[str] | None = None) -> int:
    doc = run()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"experiment design: {len(doc['queued'])} of {len(doc['evsi'])} experiment(s) queued")
    for r in doc["evsi"]:
        print(f"   {'QUEUE ' if r['queue'] else 'drop  '} {r['name']:38} "
              f"EVSI {r['evsi']:+.4f}  {r['why'][:60]}")
    d = doc["design"]
    print(f"   cheapest falsifier: {d.get('choice', d['status'])}")
    if d.get("excluded_confirming"):
        print(f"   excluded as confirming: {', '.join(d['excluded_confirming'])}")
    cap = doc["capacity"]["example_small_edge"]
    print(f"   at our capital ({DESK_CAPITAL:.0f}): {cap['verdict'][:78]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
