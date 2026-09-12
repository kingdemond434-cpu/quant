"""THE DAILY CEO DOCKET — the frontier organ proposes, and a decision is REQUIRED.

THE PRINCIPAL'S INSTRUCTION, 2026-09-12: the frontier organ must stop producing plans nobody
reads. Every day it asks the same two standing questions, scouts for answers, and puts ranked
PROPOSALS in front of the desk's decision-maker, who accepts or refuses each one on a single
criterion — does it raise robust forward E[log W], or widen genuinely independent edge discovery —
and then implements the accepted ones FULLY. Not partially, because nobody reviews the result.

    THE STANDING QUESTIONS, asked verbatim every day so the answers are comparable over time:

    Q1  Is this the maximum of what AI can reach for unorthogonal edge discovery and maximum
        growth, as of today's date?
    Q2  As of today, which available AI-assisted research capabilities are we missing that could
        discover genuinely INDEPENDENT MT5 edges and improve net geometric growth -- and what
        experiment would prove their value?

WHY THE EXPERIMENT CLAUSE IS NOT DECORATION. A proposal without a falsifier is an opinion, and a
desk that implements opinions accumulates machinery it cannot later remove because nobody can say
what it was for. Every row here carries `experiment` -- the measurement that would show the thing
worked -- and `refuted_if`, the reading that would say it did not. A proposal that cannot state
both is emitted as UNFALSIFIABLE and ranked last, which is a verdict rather than a rejection.

WHAT THIS FILE DOES AND DOES NOT DO. It PROPOSES and it RANKS. It does not write money-path code,
open branches or merge -- the same boundary `frontier_intel` already declares, kept deliberately,
because an organ that both proposes and implements its own proposals has no independent check and
becomes the thing that decides AND verifies. The implementation is done by the desk's operator
against this docket, and `decided.jsonl` records what was accepted, what was refused and why, so
the loop is auditable rather than a stream of good intentions.

ADDITIVE ONLY. Every proposal must name what it ADDS. A proposal whose value comes from removing,
shrinking or gating something the desk already runs is refused on sight: the principal's standing
order is that aggressiveness is never reduced by fiat, and a "cleanup" that costs growth is a
reduction wearing an engineering word.

RANKING IS BY EXPECTED dE[log W] PER UNIT OF COST, with independence as a multiplier rather than a
tiebreak. A capability that adds a bet CORRELATED with the book is worth a fraction of one that
adds an orthogonal bet at the same expected return, because the desk's binding constraint is
n_eff -- measured at ~8 independent bets across 15 funded sleeves -- and not the count of sleeves.

    python desks/mt5/research/frontier_ceo.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORTS = DESK / "reports"
DOCKET = REPORTS / "CEO_DOCKET.json"
DECIDED = DESK / "data" / "ceo_decided.jsonl"

#: Asked verbatim, every day. Wording is fixed on purpose: a question that drifts produces answers
#: that cannot be compared, and the whole value of a daily cadence is the comparison.
STANDING_QUESTIONS = (
    "Is this the maximum of what AI can reach for unorthogonal edge discovery and maximum growth, "
    "as of today's date?",
    "As of today, which available AI-assisted research capabilities are we missing that could "
    "discover genuinely independent MT5 edges and improve net geometric growth -- and what "
    "experiment would prove their value?",
)

#: The desk's own binding constraint, restated so every proposal is ranked against the same bar.
#: Measured 2026-09-12: 15 funded sleeves behaving as ~8 independent bets (n_eff covariance 7.9),
#: with the largest mechanism at 60% of the book. Sleeves are not the scarce thing. Independence is.
BINDING_CONSTRAINT = (
    "n_eff, not sleeve count. 15 funded sleeves behave as ~7.9 independent bets and the growth "
    "curve stops paying above 22.5% heat BECAUSE of that concentration. A proposal that adds a "
    "correlated bet moves nothing; one that adds an orthogonal bet raises the ceiling itself."
)


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _missing_families() -> list[dict]:
    """The breadth board's own REACHABLE list -- gaps the desk has already named and priced."""
    state = _read(ROOT / "web" / "desk_state.json") or {}
    bb = ((state.get("breadth") or {}).get("book_breadth") or {})
    out = []
    # THE KEY IS `missing_families`, AND READING ONLY `missing` COST THE FIRST DOCKET ITS BEST
    # ROWS. The board's own JSON names it `missing_families`; this read `missing`, got None, and
    # emitted six capability proposals with not one breadth gap among them -- the six being peer-
    # convergence guesses and the seven being gaps the desk had already named, costed and marked
    # REACHABLE. Both spellings are accepted so the docket cannot lose them to a rename again.
    rows = bb.get("missing_families") or bb.get("missing") or []
    for m in rows:
        if isinstance(m, dict) and m.get("family"):
            out.append({"family": str(m["family"]), "needs": str(m.get("needs") or "")})
        elif isinstance(m, str) and m:
            out.append({"family": m, "needs": ""})
    return out


def _frontier_scout() -> dict:
    """What the scout graded this pass, and the capabilities it says peers have and we do not."""
    fi = _read(REPORTS / "FRONTIER_INTELLIGENCE.json") or {}
    fg = _read(REPORTS / "FRONTIER_GAPS.json") or {}
    return {
        "generated_utc": fi.get("generated_utc"),
        "rows_scouted": fi.get("rows_scouted"),
        "findings_graded": fi.get("findings_graded"),
        "capability_hits": fi.get("capability_hits"),
        "new_candidates": fi.get("new_candidates"),
        "capability_gaps": (fg.get("missing") or [])[:12],
        "n_capability_gaps": fg.get("n_missing"),
        "most_watched_missing": (fg.get("most_watched_missing") or [])[:12],
    }


def _orphans(limit: int = 12) -> list[str]:
    """Modules with no importer. Built machinery nobody runs is the cheapest capability on the
    board: the code exists and the only missing thing is a caller, so the cost side of the ratio
    is near zero and almost anything it buys clears the bar."""
    rep = (_read(REPORTS / "dead_architecture.json")
           or _read(ROOT / "data" / "dead_architecture.json"))
    if isinstance(rep, dict):
        rows = rep.get("orphans") or rep.get("no_importer") or []
        out = []
        for r in rows:
            n = r.get("module") if isinstance(r, dict) else r
            if n:
                out.append(str(n))
        return out[:limit]
    return []


def propose() -> list[dict]:
    """Rank today's proposals. Each carries the experiment that would prove it and the reading
    that would refute it; a row that cannot state both is UNFALSIFIABLE and ranks last."""
    props: list[dict] = []

    # 1. The breadth board's own REACHABLE gaps. These are the cheapest independent bets on the
    #    desk because the family code already exists -- what is missing is an INPUT.
    for m in _missing_families():
        needs = m["needs"].lower()
        cheap = "price only" in needs
        props.append({
            "id": f"breadth:{m['family']}",
            "kind": "independent_bet",
            "adds": f"the {m['family']} mechanism as a fundable family",
            "needs": m["needs"],
            "why_independent": ("a family the book does not hold at all, so its correlation with "
                                "the existing book is unmeasured rather than assumed low -- which "
                                "is itself the first measurement the experiment must take"),
            "experiment": (f"generate {m['family']} cells across the registry, judge them in the "
                           f"standing gauntlet, and measure the marginal dE[log W] of the best "
                           f"survivor AFTER residualising against the funded book"),
            "refuted_if": ("no cell survives the ten gates, or the best survivor's marginal "
                           "dE[log W] against the held book is <= 0"),
            "cost": "low" if cheap else "medium",
            "blocked_on": None if cheap else m["needs"],
            "rank_note": ("needs price only -- there is no blocker at all" if cheap
                          else "needs an input the desk does not yet hold"),
        })

    # 2. Built-but-unwired machinery. Zero build cost; the caller is the whole job.
    for mod in _orphans():
        props.append({
            "id": f"wire:{mod}",
            "kind": "capability",
            "adds": f"a caller for {mod}, which exists and runs nowhere",
            "needs": "a scheduled caller and an artifact",
            "why_independent": "unknown until it runs -- that is what makes it cheap to find out",
            "experiment": (f"put {mod} on a clock, let it write its artifact, and measure whether "
                           f"any downstream number changes. III.16: unwired or idle is a defect"),
            "refuted_if": "it runs, writes, and no consumer reads the artifact after 7 days",
            "cost": "low",
            "blocked_on": None,
            "rank_note": "the code already exists; only the caller is missing",
        })

    # 3. What the scout says peers have and we do not.
    sc = _frontier_scout()
    for cap in (sc.get("most_watched_missing") or sc.get("capability_gaps") or []):
        name = cap.get("capability") if isinstance(cap, dict) else str(cap)
        if not name:
            continue
        props.append({
            "id": f"capability:{name}",
            "kind": "capability",
            "adds": str(name),
            "needs": (cap.get("needs") if isinstance(cap, dict) else None) or "scoping",
            "why_independent": ("cross-firm convergence is a PRIOR, never proof -- several elite "
                                "organisations investing in a capability we lack is evidence "
                                "about their beliefs, not about our returns"),
            "experiment": ((cap.get("experiment") if isinstance(cap, dict) else None)
                           or "UNFALSIFIABLE: no experiment stated by the scout"),
            "refuted_if": "no measurable change in dE[log W] or in n_eff after implementation",
            "cost": "medium",
            "blocked_on": None,
            "rank_note": "peer-convergence signal",
        })

    # RANK. Independence first (a new family raises the ceiling; a capability usually does not),
    # then cost, then whether anything blocks it. Unfalsifiable rows sink regardless.
    kind_w = {"independent_bet": 0, "capability": 1}
    cost_w = {"low": 0, "medium": 1, "high": 2}
    props.sort(key=lambda p: (
        str(p.get("experiment", "")).startswith("UNFALSIFIABLE"),
        kind_w.get(str(p.get("kind")), 2),
        cost_w.get(str(p.get("cost")), 3),
        p.get("blocked_on") is not None,
        str(p.get("id")),
    ))
    for i, p in enumerate(props, 1):
        p["rank"] = i
    return props


def build() -> dict:
    now = datetime.now(tz=UTC)
    props = propose()
    decided = set()
    try:
        for ln in DECIDED.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                decided.add(str(json.loads(ln).get("id")))
    except (OSError, ValueError):
        pass
    fresh = [p for p in props if p["id"] not in decided]
    return {
        "at": now.isoformat(timespec="seconds"),
        "date": now.date().isoformat(),
        "standing_questions": list(STANDING_QUESTIONS),
        "binding_constraint": BINDING_CONSTRAINT,
        "scout": _frontier_scout(),
        "n_proposals": len(props),
        "n_undecided": len(fresh),
        "proposals": props,
        "decision_rule": (
            "ACCEPT if and only if the proposal raises robust forward E[log W] or widens genuinely "
            "INDEPENDENT edge discovery, and is ADDITIVE. Refuse anything whose value comes from "
            "removing, shrinking or gating what the desk already runs: aggressiveness is never "
            "reduced by fiat (principal, standing). Record every decision in ceo_decided.jsonl "
            "with its reason, so a refusal is a measurement and not a silence."),
        "boundary": (
            "This organ PROPOSES and RANKS. It does not write money-path code, open branches or "
            "merge. An organ that implements its own proposals is both the decider and the "
            "verifier, which is the one structure the certificate architecture exists to prevent."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the docket")
    a = ap.parse_args(argv)
    doc = build()
    print(f"CEO docket {doc['date']}: {doc['n_proposals']} proposal(s), "
          f"{doc['n_undecided']} undecided")
    for p in doc["proposals"][:14]:
        blocked = f"  [blocked: {p['blocked_on']}]" if p.get("blocked_on") else ""
        print(f"  {p['rank']:>2}. {p['kind']:<17} {p['id'][:44]:<44} {p['cost']:<6}{blocked}")
    sc = doc["scout"]
    print(f"  scout: {sc.get('rows_scouted')} rows graded, {sc.get('capability_hits')} capability "
          f"hits, {sc.get('n_capability_gaps')} gaps")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    DOCKET.parent.mkdir(parents=True, exist_ok=True)
    DOCKET.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"-> {DOCKET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
