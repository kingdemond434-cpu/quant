"""F25 -- THE RESEARCH SYSTEM MAY CHANGE ITSELF, and must beat itself to do it.

THE PRINCIPAL, 2026-09-12:

    The system may modify researcher prompts, role structures, grammar primitives, search
    operators, experiment schedulers, representations and search algorithms -- but every
    meta-version competes against the incumbent on sealed historical traps + synthetic benchmarks
    + prospective campaigns, and only an objectively better research system becomes champion.

THE ARENAS EXIST NOW, WHICH IS WHY THIS IS LAST. It could not be built before today because it
has nothing to judge with otherwise:

    sealed historical traps   `quantbench` -- eleven defects this desk actually survived, each an
                              executable probe against the current tree
    synthetic benchmarks      `adversary_evolution` -- a population of attacks with declared
                              ground truth, plus a reserved control arm that measures the gates'
                              OTHER error
    prospective campaigns     `credit_assignment` -- realised forward R attributed back to the
                              scientist that proposed it

THE ONE RULE THAT MAKES SELF-MODIFICATION SAFE. A system allowed to change itself and graded on
its own score will lower its own bar -- that is not a risk, it is the shortest path to a better
number. So the synthetic arena is the ADVERSARY, and a meta-version that weakens a gate fails it
BY CONSTRUCTION: breaches rise, or the control arm's false rejections fall for the wrong reason.
The judge cannot be improved into agreement with the thing it judges.

AND THE KNOBS IT MAY NOT TOUCH ARE ENUMERATED, not left to taste. Gate thresholds, heat, the
minimum-lot floor and every sizing parameter are REFUSED -- listed by name, with the refusal
recorded on the run. The principal's standing order is that risk is never reduced by fiat, and its
mirror is equally binding here: a research system must not be permitted to raise its own scores by
moving the bar it is scored against.

THE CHAMPION HOLDS BY DEFAULT. A challenger becomes champion only when it is strictly better on a
measurable arena and WORSE ON NONE. Ties go to the incumbent, because the cost of churn in a
research system is paid in every downstream comparison that now spans two regimes -- which is
exactly what F19 found the certificate registry doing.

THE PROSPECTIVE ARM CANNOT BE SETTLED IN ONE RUN and is not pretended otherwise. A challenger is
REGISTERED with the forward evidence it awaits, and the report says what would settle it. A
meta-tournament that declared a winner on two arenas out of three would be doing what the desk's
forward lane is criticised for.

    python desks/mt5/research/meta_rnd.py [--apply] [--propose KNOB=VALUE]
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

CHAMPION = DESK / "data" / "meta_champion.json"
OUT = DESK / "reports" / "META_RND.json"

#: The knobs a meta-version MAY move. Every one is a property of how the desk SEARCHES -- never of
#: what it will risk, and never of the bar it is judged against.
META_KNOBS: dict[str, dict[str, Any]] = {
    "research_tree.BEAM": {
        "module": "research.research_tree", "attr": "BEAM", "lo": 4, "hi": 48,
        "changes": "how many tree nodes are expanded per pass -- the rate at which reach is "
                   "bought"},
    "research_tree.INHERIT": {
        "module": "research.research_tree", "attr": "INHERIT", "lo": 0.0, "hi": 0.9,
        "changes": "how strongly a child node inherits its parent's posterior; 0 flattens the "
                   "tree into a list, 1 makes a cross-market analogue as likely as its parent"},
    "joint_evolution.DRAWS": {
        "module": "research.joint_evolution", "attr": "DRAWS", "lo": 40, "hi": 400,
        "changes": "genomes sampled per surface -- the resolution of the interaction measurement"},
    "representation_discovery.BEAM": {
        "module": "research.representation_discovery", "attr": "BEAM", "lo": 2, "hi": 16,
        "changes": "composite search width, and therefore the trial count it charges the desk"},
    "adversary_evolution.MUT": {
        "module": "research.adversary_evolution", "attr": "MUT", "lo": 0.05, "hi": 0.6,
        "changes": "how far an attack's child moves from its parent -- the adversary's own "
                   "exploration rate"},
    "negative_knowledge.EXPLORE_FLOOR": {
        "module": "research.negative_knowledge", "attr": "EXPLORE_FLOOR", "lo": 0.10, "hi": 0.50,
        "changes": "the share of admissions reserved for the cells the model scores worst"},
}

#: Knobs a meta-version may NEVER move, and why. Enumerated rather than left to judgement: a
#: system graded on its own output will find these if they are merely discouraged.
FORBIDDEN_KNOBS: dict[str, str] = {
    "any gate threshold": (
        "the gates are what a meta-version is JUDGED by. A system permitted to move them would "
        "improve its score by lowering its bar, which is the shortest path to a better number "
        "and the least useful one."),
    "heat floor, heat ceiling, per-sleeve caps": (
        "the principal's standing order: risk is never reduced by fiat, and its mirror binds "
        "equally -- research must not raise its scores by moving what the desk will risk."),
    "minimum lot, daily loss, sizing parameters": (
        "money-path constants. A research tournament has no business near them, and F26's "
        "invariant says exactly one authority sizes."),
    "the trial charge": (
        "F19 measured what happens when it moves: the registry now holds two regimes and 15 of "
        "61 certificates cleared a standard the desk no longer applies. A meta-version moving it "
        "would make every comparison in this report span two worlds."),
}


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _current_value(knob: str) -> Any:
    spec = META_KNOBS.get(knob)
    if not spec:
        return None
    try:
        mod = __import__(spec["module"], fromlist=["*"])
        return getattr(mod, str(spec["attr"]), None)
    except Exception:
        return None


def _arena_traps() -> dict[str, Any]:
    """Sealed historical traps: the bench must not regress. A FAIL here refuses the challenger."""
    try:
        from research.quantbench import build as bench
    except ImportError as exc:
        return {"status": "UNMEASURED", "why": f"quantbench not importable ({exc})"}
    d = bench()
    return {"status": "OK", "n_cases": d.get("n_cases"),
            "n_failed": d.get("n_failed"), "n_unmeasurable": d.get("n_unmeasurable"),
            "verdict": d.get("status"),
            "score": -int(d.get("n_failed") or 0),
            "rule": ("a returned defect is disqualifying, not a deduction. A research system "
                     "that scores better while re-breaking something the desk already paid for "
                     "is not better.")}


def _arena_synthetic() -> dict[str, Any]:
    """Synthetic benchmarks: the adversary. This is the arena that makes self-modification safe."""
    p = DESK / "reports" / "ADVERSARY_EVOLUTION.json"
    d = _read(p)
    if not isinstance(d, dict) or d.get("status") == "BLOCKED":
        return {"status": "UNMEASURED",
                "why": (f"no usable adversary report at {p.name}; the synthetic arena is the one "
                        f"that stops a meta-version improving its score by weakening a gate, so "
                        f"a challenger cannot be judged without it")}
    ctl = d.get("controls") or {}
    return {
        "status": "OK",
        "n_breach": d.get("n_breach"),
        "n_controls": ctl.get("n"), "n_false_rejection": ctl.get("n_false_rejection"),
        "controls_status": ctl.get("status"),
        # A BREACH IS THE DISQUALIFIER. False rejections are reported and do NOT score, because a
        # meta-version could reduce them by making the gates permissive -- which is the failure
        # this arena exists to prevent.
        "score": -int(d.get("n_breach") or 0),
        "rule": ("breaches score; false rejections are REPORTED and do not. A meta-version can "
                 "always cut false rejections by making the gates permissive, and rewarding that "
                 "would hand the system the exact lever it must not have."),
    }


def _arena_prospective() -> dict[str, Any]:
    """Prospective campaigns: realised forward R per scientist. Cannot be settled in one run."""
    d = _read(DESK / "reports" / "CREDIT_ASSIGNMENT.json")
    if not isinstance(d, dict) or d.get("status") != "OK":
        return {"status": "UNMEASURED", "why": "no credit assignment report to read"}
    lanes = d.get("by_representation_lane") or []
    total = round(sum(float(r.get("realised_r") or 0.0) for r in lanes), 4)
    return {
        "status": "OPEN",
        "total_realised_r_now": total,
        "evidence_source": d.get("evidence_source"),
        "silent_certificates": (d.get("silent_certificates") or {}).get("n"),
        "why_open": (
            "a prospective campaign is settled by TIME, not by a run. A challenger is registered "
            "with the forward record as it stands and judged when the record moves; declaring a "
            "winner on two arenas out of three would be doing exactly what this desk criticises "
            "its own forward lane for."),
        "what_would_settle_it": (
            "realised forward R per scientist, measured over a window that begins AFTER the "
            "challenger is seated, against the same window for the incumbent. The credit chain "
            "already produces it; what it needs is elapsed time."),
    }


def build(propose: str | None = None) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    champ = _read(CHAMPION) or {}
    incumbent = champ.get("knobs") or {k: _current_value(k) for k in META_KNOBS}

    traps, synth, pros = _arena_traps(), _arena_synthetic(), _arena_prospective()

    challenger: dict[str, Any] | None = None
    refusal: str | None = None
    if propose:
        if "=" not in propose:
            refusal = f"proposal {propose!r} is not KNOB=VALUE"
        else:
            knob, raw = propose.split("=", 1)
            knob = knob.strip()
            spec = META_KNOBS.get(knob)
            if spec is None:
                refusal = (f"{knob!r} is not a meta knob. The movable set is "
                           f"{sorted(META_KNOBS)}; everything else is refused, and the "
                           f"forbidden classes are enumerated in the report.")
            else:
                try:
                    val: Any = float(raw)
                    if float(val).is_integer() and isinstance(spec["lo"], int):
                        val = int(val)
                except ValueError:
                    refusal = f"{raw!r} is not a number"
                    val = None
                if refusal is None and val is not None:
                    if not (spec["lo"] <= val <= spec["hi"]):
                        refusal = (f"{knob}={val} is outside its declared range "
                                   f"[{spec['lo']}, {spec['hi']}]")
                    else:
                        challenger = {"knob": knob, "from": _current_value(knob), "to": val,
                                      "changes": spec["changes"]}

    # THE CHAMPION HOLDS BY DEFAULT, and a challenger must be strictly better on a measurable
    # arena and worse on none. Ties go to the incumbent: churn in a research system is paid in
    # every downstream comparison that then spans two regimes.
    measurable = [a for a in (traps, synth) if a.get("status") == "OK"]
    verdict = "CHAMPION_HOLDS"
    why = ("no challenger proposed this run" if not challenger else
           "a challenger must be RUN under its own configuration to be scored; this run records "
           "the arena state it must beat")
    if refusal:
        verdict = "CHALLENGER_REFUSED"
        why = refusal

    return {
        "at": now.isoformat(timespec="seconds"),
        "status": "OK",
        "verdict": verdict,
        "why": why,
        "incumbent": {"knobs": incumbent,
                      "seated_at": champ.get("seated_at"),
                      "note": ("the values in force. On the first run these are read from the "
                               "modules themselves, so the champion IS the code as written.")},
        "challenger": challenger,
        "arenas": {"sealed_traps": traps, "synthetic": synth, "prospective": pros},
        "arena_baseline": {a: (v.get("score") if isinstance(v, dict) else None)
                           for a, v in (("sealed_traps", traps), ("synthetic", synth))},
        "movable_knobs": {k: {**{kk: v[kk] for kk in ("lo", "hi", "changes")},
                              "current": _current_value(k)}
                          for k, v in META_KNOBS.items()},
        "forbidden_knobs": FORBIDDEN_KNOBS,
        "champion_rule": (
            "the incumbent holds unless a challenger is STRICTLY BETTER on a measurable arena and "
            "WORSE ON NONE. A returned bench defect or a new adversary breach is disqualifying "
            "rather than a deduction -- a research system that scores better while re-breaking "
            "something the desk already paid for is not better."),
        "why_the_adversary_is_the_safety": (
            "a system allowed to change itself and graded on its own score will lower its own "
            "bar; that is the shortest path to a better number. The synthetic arena is the "
            "adversary, so weakening a gate FAILS by construction -- breaches rise. And false "
            "rejections are reported but never scored, because cutting them by making the gates "
            "permissive is the same lever wearing a friendlier name."),
        "boundary": (
            "NOTHING HERE EDITS A MODULE. It records the arena a challenger must beat and the "
            "knobs it may move. Seating a champion is a decision, and an autonomous research "
            "system that rewrote its own constants between passes is precisely the thing this "
            "enumerated knob list exists to prevent."),
        "measurable_arenas_this_run": len(measurable),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--propose", default=None, help="KNOB=VALUE, from the movable set only")
    a = ap.parse_args(argv)
    doc = build(a.propose)
    print(f"meta R&D: {doc['verdict']}   {doc['measurable_arenas_this_run']} measurable arena(s)")
    print(f"  {doc['why'][:160]}")
    for name, arena in doc["arenas"].items():
        st = arena.get("status")
        if name == "sealed_traps" and st == "OK":
            print(f"  {name:<14} {st}  {arena['n_cases']} case(s), {arena['n_failed']} failed, "
                  f"{arena['n_unmeasurable']} unmeasurable  score {arena['score']}")
        elif name == "synthetic" and st == "OK":
            print(f"  {name:<14} {st}  {arena['n_breach']} breach(es), "
                  f"{arena['n_false_rejection']} false rejection(s) of "
                  f"{arena['n_controls']} control(s)  score {arena['score']}")
        elif name == "prospective":
            print(f"  {name:<14} {st}  realised {arena.get('total_realised_r_now')}R so far, "
                  f"{arena.get('silent_certificates')} certificate(s) still silent")
        else:
            print(f"  {name:<14} {st}  {str(arena.get('why'))[:90]}")
    if doc.get("challenger"):
        c = doc["challenger"]
        print(f"  challenger: {c['knob']} {c['from']} -> {c['to']}  ({c['changes'][:70]})")
    print(f"  movable: {sorted(doc['movable_knobs'])}")
    print(f"  forbidden: {sorted(doc['forbidden_knobs'])}")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    CHAMPION.parent.mkdir(parents=True, exist_ok=True)
    if not CHAMPION.exists():
        CHAMPION.write_text(json.dumps(
            {"seated_at": doc["at"], "knobs": doc["incumbent"]["knobs"],
             "why": "the first champion is the code as written; nothing has beaten it because "
                    "nothing has run against it yet"}, indent=1, default=str), encoding="utf-8")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
