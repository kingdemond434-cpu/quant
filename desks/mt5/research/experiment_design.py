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
#: The gauntlet's own report: every cell it judged this sweep and every cell its fresh-build
#: budget did not reach, the latter published as `NOT_RUN_BUILD_BUDGET_DEFERRED` verdicts
#: (desks/mt5/scripts/external_gauntlet.py:1561-1570). Those deferred cells ARE the desk's real
#: experiment queue, and until 2026-09-09 this module scored four hand-typed rows instead.
GATES_EXTERNAL = BASE / "reports" / "universal_gates_external.json"
DEFERRED_STATUS = "NOT_RUN_BUILD_BUDGET_DEFERRED"

#: Seconds one UNCACHED gauntlet cell costs to build. Not measured here and not invented here:
#: it is the figure `external_gauntlet.py` records in its own budget derivation -- "At ~22
#: seconds per uncached cell and ~3,700 uncached cells, a full cold sweep is roughly 22 hours"
#: (external_gauntlet.py:66-67) and "the build is ~22s a cell" (:188). When the report's own
#: `prewarm` summary carries warmed cells and the seconds they took, THAT measurement is used
#: and the basis says so; this constant is the cited fallback.
GAUNTLET_CELL_BUILD_S = 22.0
#: Rows of the EVSI-ordered docket published in the report. The docket has run to 7,648 deferred
#: cells (external_gauntlet.py:1438-1439); the full ranking is computed and its size stated, the
#: head is published. A reader wants the front of the queue, not a 2MB artifact.
PUBLISHED_ROWS = 400
#: How far into each ordering the head comparison looks.
HEAD = 20

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


#: The four hand-typed standing questions. The FALLBACK when the gauntlet report is absent,
#: labelled as such in the artifact; never the queue when the real docket is on disk.
HAND_TYPED: tuple[Experiment, ...] = (
    Experiment("recertify_unrunnable_certificates", 0.9, 0.20, 2.0,
               falsifies="that the certificates carry a runnable parameterisation"),
    Experiment("widen_timeframe_ladder_to_M5", 0.6, 0.15, 6.0,
               falsifies="that sub-hourly mechanisms survive the ten gates"),
    Experiment("re_backtest_every_certificate_again", 0.02, 0.30, 40.0),
    Experiment("measure_markout_on_recorded_fills", 0.8, 0.25, 1.0,
               falsifies="that execution gives back less than the edge"),
)


def _json(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def deferred_cells(report: dict[str, Any]) -> list[dict[str, Any]]:
    """The cells the last sweep's build budget did not reach, IN THE SWEEP'S OWN ORDER.

    The gauntlet defers in its starvation-rotation order (longest-unbuilt symbol first,
    external_gauntlet.py:1453-1458), so the position here is the cell's place in the existing
    rotation and is kept beside its EVSI rank rather than replaced by it.
    """
    return [v for v in (report.get("verdicts") or [])
            if isinstance(v, dict) and v.get("downstream_status") == DEFERRED_STATUS]


def family_rates(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """P(certify | family) and the mean expected value of a family's survivors, from the cells
    the SAME report judged. Laplace-smoothed: (k + 1) / (n + 2), so a family with no judged
    cell reads as the uninformed 0.5 rather than as certain either way, and `_pooled` carries
    the report-wide rate for cells whose family has nothing judged."""
    judged: dict[str, list[dict[str, Any]]] = {}
    for v in report.get("verdicts") or []:
        if not isinstance(v, dict) or not isinstance(v.get("passed"), bool) or v.get("unmeasured"):
            continue
        judged.setdefault(str(v.get("family") or ""), []).append(v)
    out: dict[str, dict[str, Any]] = {}
    all_rows: list[dict[str, Any]] = []
    for fam, rows in judged.items():
        all_rows.extend(rows)
        out[fam] = _rate(rows)
    out["_pooled"] = _rate(all_rows)
    return out


def _rate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    k = sum(1 for r in rows if r.get("passed") is True)
    evs = []
    for r in rows:
        if r.get("passed") is True:
            ev = ((r.get("stages") or {}).get("expected_value") or {}).get("ev")
            if isinstance(ev, (int, float)) and math.isfinite(float(ev)):
                evs.append(float(ev))
    return {"judged": n, "passed": k, "p_certify": round((k + 1) / (n + 2), 6),
            "mean_ev": (round(sum(evs) / len(evs), 6) if evs else None)}


def cell_cost_seconds(report: dict[str, Any]) -> tuple[float, str]:
    """Seconds per fresh cell: the report's own prewarm measurement when it carries one, else the
    figure the gauntlet cites for itself."""
    pw = report.get("prewarm") or {}
    try:
        warmed, secs = int(pw.get("warmed") or 0), float(pw.get("seconds") or 0.0)
    except (TypeError, ValueError):
        warmed, secs = 0, 0.0
    if warmed > 0 and secs > 0:
        return secs / warmed, (f"measured: {secs:.0f}s over {warmed} cell(s) warmed by this "
                               f"report's own prewarm pool")
    return GAUNTLET_CELL_BUILD_S, (f"cited: ~{GAUNTLET_CELL_BUILD_S:.0f}s per uncached cell, "
                                   "external_gauntlet.py:66-67 and :188; no prewarm measurement "
                                   "in the report")


def docket_experiments(report: dict[str, Any]) -> tuple[list[Experiment], dict[str, Any]]:
    """One Experiment per deferred gauntlet cell, priced at the gauntlet's own cost per cell.

    P(changes the decision) is P(certify | family): a cell that fails changes nothing the desk
    does (it is already not traded), a cell that certifies enters the canon. The decision's
    value is the mean expected value of the family's survivors in the same report -- the
    report-wide mean when the family has none, and UNMEASURED (scored at 0) when no survivor in
    the report carries one, which the basis says out loud rather than inventing a figure.
    """
    cells = deferred_cells(report)
    rates = family_rates(report)
    pooled = rates.get("_pooled") or _rate([])
    cost_s, cost_basis = cell_cost_seconds(report)
    hours = cost_s / 3600.0
    value_unmeasured = 0
    exps: list[Experiment] = []
    for v in cells:
        fam = str(v.get("family") or "")
        r = rates.get(fam) or {}
        p = float(r.get("p_certify") if r.get("judged") else pooled["p_certify"])
        value = r.get("mean_ev") if r.get("mean_ev") is not None else pooled.get("mean_ev")
        if value is None:
            value_unmeasured += 1
            value = 0.0
        exps.append(Experiment(
            name=f"gauntlet_cell:{v.get('cell')}", p_changes_decision=p,
            decision_value=float(value), cost_hours=hours,
            falsifies=f"that {v.get('sym')} {fam} survives the ten gates"))
    meta = {
        "n_deferred": len(cells), "cost_s_per_cell": round(cost_s, 3), "cost_basis": cost_basis,
        "p_basis": ("P(certify | family) = (passed + 1) / (judged + 2) over the cells this "
                    "report judged; the report-wide rate when the family has none judged"),
        "value_basis": ("mean stages.expected_value.ev of the family's survivors in this report; "
                        "report-wide mean when the family has none"
                        + (f"; {value_unmeasured} cell(s) scored at 0.0 because no survivor "
                           f"carries an ev -- UNMEASURED, not worthless" if value_unmeasured
                           else "")),
        "family_rates": {k: v for k, v in rates.items() if k != "_pooled"},
        "pooled_rate": pooled,
    }
    return exps, meta


def docket_view(cells: list[dict[str, Any]], scored: list[dict[str, Any]],
                exps: list[Experiment]) -> dict[str, Any]:
    """The EVSI order beside the rotation order: every row carries both ranks."""
    by_name = {e.name: (i, e) for i, e in enumerate(exps)}
    rows = []
    for r in scored:
        i, e = by_name[r["name"]]
        rows.append({"cell": cells[i].get("cell"), "sym": cells[i].get("sym"),
                     "family": cells[i].get("family"), "evsi": r["evsi"], "queue": r["queue"],
                     "p_changes_decision": round(e.p_changes_decision, 6),
                     "decision_value": round(e.decision_value, 6),
                     "cost_hours": round(e.cost_hours, 8), "rotation_rank": i})
    rows.sort(key=lambda x: (-x["evsi"], x["rotation_rank"]))
    for j, row in enumerate(rows):
        row["evsi_rank"] = j
    head_evsi = {row["cell"] for row in rows[:HEAD]}
    head_rot = {c.get("cell") for c in cells[:HEAD]}
    return {
        "order": "EVSI descending, ties by rotation rank",
        "n_rows": len(rows), "n_published": min(len(rows), PUBLISHED_ROWS),
        "n_queued": sum(1 for r in rows if r["queue"]),
        "head_overlap": {"head": HEAD, "cells_in_both_heads": len(head_evsi & head_rot),
                         "why": ("how many of the next HEAD cells the rotation would build are "
                                 "also in the EVSI head; the rotation stays the builder's order "
                                 "(frame-cache locality, anti-starvation) and this is the view "
                                 "beside it")},
        "rows": rows[:PUBLISHED_ROWS],
    }


def run() -> dict[str, Any]:
    """A worked pass over the desk's REAL experiment queue, with the standing questions as the
    labelled fallback when the gauntlet report is not on disk."""
    report = _json(GATES_EXTERNAL)
    cells = deferred_cells(report)
    if cells:
        queue, docket_meta = docket_experiments(report)
        queue_basis = "GAUNTLET_DEFERRED_CELLS"
        queue_why = (f"{len(cells)} cell(s) published as {DEFERRED_STATUS} in "
                     f"{GATES_EXTERNAL.name} (swept {report.get('swept_at')})")
    else:
        queue, docket_meta = list(HAND_TYPED), {}
        queue_basis = "HAND_TYPED_FALLBACK"
        queue_why = (f"{GATES_EXTERNAL.name} is absent or unreadable; the four standing "
                     "questions are scored instead and this label says so"
                     if not report else
                     f"{GATES_EXTERNAL.name} carries no {DEFERRED_STATUS} cell (swept "
                     f"{report.get('swept_at')}); the four standing questions are scored instead")
    scored = [evsi(e) for e in queue]
    ranked = sorted(scored, key=lambda r: -r["evsi"])
    docket: dict[str, Any] = {"status": "MEASURED" if cells else "FALLBACK", "basis": queue_basis,
                              "why": queue_why, "report": str(GATES_EXTERNAL), **docket_meta}
    if cells:
        docket.update(docket_view(cells, scored, queue))
    return {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "queue_basis": queue_basis,
        "queue_why": queue_why,
        "n_scored": len(scored),
        "evsi": ranked[:PUBLISHED_ROWS],
        "queued": [r["name"] for r in ranked if r["queue"]][:PUBLISHED_ROWS],
        "n_queued": sum(1 for r in scored if r["queue"]),
        "docket": docket,
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
    print(f"experiment design [{doc['queue_basis']}]: {doc['n_queued']} of {doc['n_scored']} "
          f"experiment(s) queued -- {doc['queue_why'][:90]}")
    for r in doc["evsi"][:8]:
        print(f"   {'QUEUE ' if r['queue'] else 'drop  '} {r['name'][:56]:56} "
              f"EVSI {r['evsi']:+.4f}  {r['why'][:50]}")
    dk = doc["docket"]
    if dk.get("status") == "MEASURED":
        print(f"   docket: {dk['n_deferred']} deferred cell(s) at {dk['cost_s_per_cell']}s each "
              f"({dk['cost_basis'][:60]}); EVSI head shares "
              f"{dk['head_overlap']['cells_in_both_heads']}/{dk['head_overlap']['head']} cells "
              f"with the rotation head")
    d = doc["design"]
    print(f"   cheapest falsifier: {str(d.get('choice', d['status']))[:70]}")
    if d.get("excluded_confirming"):
        print(f"   excluded as confirming: {', '.join(d['excluded_confirming'])}")
    cap = doc["capacity"]["example_small_edge"]
    print(f"   at our capital ({DESK_CAPITAL:.0f}): {cap['verdict'][:78]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
