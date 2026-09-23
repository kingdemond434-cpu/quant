"""THE PHYSICS LAB: the mathematics + physics scientific alpha factory as an institution on a
clock -- the second leg of the `mathlab` department.

`math_lab` is the population: forty-seven traditions (twenty-eight mathematical, nineteen
physical) proposing objects over the world model's residual, every object charged its search
burden. THIS LEG IS THE INSTITUTION AROUND THEM. One pass:

  1. builds the same panels `math_lab` builds and SEALS THE LOCKBOX -- the last 15% of every
     panel is hashed and cut off before any scientist or judge sees it; after the pass the seal
     is verified and every card is checked against the working row count;
  2. splits the budget by DEPARTMENT (physics, mathematics, engines) two-sided by measured ROI
     with a floor, and runs TWO INDEPENDENT CIVILIZATIONS with disjoint seeds over the same
     panels -- every physics tradition in both, a rotating slice of the mathematical ones --
     compared only through the judge;
  3. turns every judged object into a HYPOTHESIS CARD (claim, domain, mechanism, units,
     predicted consequences, falsifier, cost, multiplicity charge, lineage), derives and tests
     its consequences, prices it through the effective-trial ledger, stamps its PIT, submits it
     to PEER REVIEW (a discoverer and a destroyer on independent streams), requires a SECOND
     INDEPENDENT RUN before it may be FORWARD, computes the Pareto front of evidence against
     complexity, measures cross-market transfer, discovers the residual's states and reads the
     card per state, and runs the desk's own causal adjudicator over the strongest;
  4. manufactures planted nulls the judge must reject, records every card in the theorem memory
     (proven / failed / negative knowledge, jsonl under data/mathlab/), mines the failures for
     exhausted regions, and credits every survivor back to its METHOD so the method allocation
     evolves;
  5. runs the fifteen engines (law discovery to primitive invention) on the first panel, chooses
     the next experiment where the reviewers and the models disagree most, donates the
     FORWARD/PROVISIONAL cards' executable objects to the compiler through the SAME door as
     math_lab, records discoveries in the registry with provenance, writes an event row, and
     publishes a WIRING PROOF naming every scientist and engine that ran this hour with counts.

Nothing is certified, no capital is allocated, and every donated object meets the ten gates in
`scripts/external_gauntlet.py` with every other hypothesis.

    python research/physics_lab.py --once --budget-s 600
    python research/physics_lab.py --once --budget-s 60 --dry-run     # writes nothing
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import math_lab as ML  # noqa: E402
from research.mathlab import burden as B  # noqa: E402
from research.mathlab import engines as E  # noqa: E402
from research.mathlab import institution as I  # noqa: E402
from research.mathlab import scientists as S  # noqa: E402
from research.mathlab.objects import MathObject, Panel  # noqa: E402
from research.mathlab.physics import PHYSICS_CORE_REGISTRY  # noqa: E402
from research.mathlab.physics_ext import PHYSICS_EXT_REGISTRY  # noqa: E402

PHYSICS_REGISTRY: dict[str, type[Any]] = {**PHYSICS_CORE_REGISTRY, **PHYSICS_EXT_REGISTRY}
PHYSICS_TRADITIONS: tuple[str, ...] = tuple(PHYSICS_REGISTRY)

DATA = DESK / "data"
OUT = DESK / "reports" / "PHYSICS_LAB.json"
MEMORY_DIR = I.MEMORY_DIR
METHODS = DATA / "mathlab" / "method_allocation.json"
DONATED = DATA / "physics_lab_donated.json"
SOURCE = "physics_lab"
SEED = 20260922
CIVILIZATIONS: dict[str, int] = {"A": SEED + 101, "B": SEED + 202}
#: Mathematical traditions per civilization per pass, rotated so all twenty-eight are reached.
MATHS_PER_PASS = 4
MAX_TARGETS = 2
MAX_CARDS_REVIEWED = 60
MAX_CAUSAL = 6
MAX_DONATIONS = 30
UNMEASURED = "UNMEASURED"

RULE = ("two independent civilizations with disjoint seeds over lockboxed panels; every object "
        "becomes a hypothesis card with a falsifier; consequences derived and tested; peer "
        "review by a discoverer and a destroyer; multiplicity charged through the effective-trial "
        "ledger; a second independent run before FORWARD; Pareto front of evidence vs "
        "complexity; credit back to the method; planted nulls must die; the wiring proof names "
        "every organ that ran")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def rotation(pass_index: int, per_pass: int = MATHS_PER_PASS) -> list[str]:
    """The mathematical traditions this pass reaches: a window over the twenty-eight."""
    names = list(S.TRADITIONS)
    if not names:
        return []
    start = (pass_index * per_pass) % len(names)
    return [names[(start + i) % len(names)] for i in range(min(per_pass, len(names)))]


def populations(pass_index: int, physics: list[str] | None = None,
                maths: list[str] | None = None) -> dict[str, list[str]]:
    phys = [t for t in (physics if physics is not None else list(PHYSICS_TRADITIONS))
            if t in PHYSICS_REGISTRY]
    math_ = [t for t in (maths if maths is not None else rotation(pass_index)) if t in S.REGISTRY]
    out: dict[str, list[str]] = {}
    for name in CIVILIZATIONS:
        out[name] = [*phys, *math_]
    return out


def _copy(panel: Panel) -> Panel:
    return Panel(target=panel.target, times=panel.times, epsilon=panel.epsilon,
                 columns=dict(panel.columns), meta=dict(panel.meta), regime=panel.regime,
                 session=panel.session, peers=panel.peers, horizon=panel.horizon,
                 source=panel.source, residual_discovery_id=panel.residual_discovery_id)


def _run_tradition(civ: str, tradition: str, panels: list[Panel], budget_s: float, seed: int
                   ) -> dict[str, Any]:
    """One tradition of one civilization over every working panel. Never raises."""
    started = time.monotonic()
    result: dict[str, Any] = {"civilization": civ, "tradition": tradition, "objects": [],
                              "evaluated": 0, "distinct": set(), "unmeasured": [],
                              "status": "OK", "panels": []}
    try:
        scientist = S.build(tradition)
    except Exception as exc:
        result.update({"status": "FAILED", "why": f"{type(exc).__name__}: {exc}",
                       "compute_s": round(time.monotonic() - started, 3)})
        return result
    per_panel = max(1.0, budget_s / max(1, len(panels)))
    for panel in panels:
        view = _copy(panel)
        rng = np.random.default_rng(seed + (abs(hash((tradition, panel.target))) % 100_000))
        try:
            objects = scientist.propose(view, per_panel, rng)
        except Exception as exc:
            result["status"] = "FAILED"
            result["why"] = f"{type(exc).__name__}: {exc}"
            result["unmeasured"].append(f"panel {panel.target}: {type(exc).__name__}")
            continue
        for obj in objects:
            obj.provenance.residual_target = panel.target
            obj.provenance.residual_discovery_id = panel.residual_discovery_id
            obj.provenance.panel_source = panel.source
            obj.provenance.datasets = sorted({v.dataset for v in obj.variables})
            obj.provenance.seed = seed
        result["objects"].extend([(obj, view) for obj in objects])
        result["panels"].append(panel.target)
        result["evaluated"] += scientist.evaluated
        result["distinct"] |= scientist.distinct
        result["unmeasured"].extend(scientist.unmeasured)
    result["compute_s"] = round(time.monotonic() - started, 3)
    return result


def department_roi() -> dict[str, float | None]:
    """Mean measured ROI per department from generator_yield, UNMEASURED (None) when no
    tradition of the department has compute on record."""
    out: dict[str, float | None] = {"physics": None, "mathematics": None, "engines": None}
    try:
        roi, _detail = ML.tradition_roi(traditions=(*S.TRADITIONS, *PHYSICS_TRADITIONS))
    except Exception:
        return out
    for dept, names in (("physics", PHYSICS_TRADITIONS), ("mathematics", S.TRADITIONS)):
        measured = [v for t, v in roi.items() if t in names and isinstance(v, (int, float))]
        out[dept] = float(np.mean(measured)) if measured else None
    return out


def run(*, budget_s: float = 600.0, dry_run: bool = False, max_targets: int = MAX_TARGETS,
        permutations: int = B.PERMUTATIONS, physics: list[str] | None = None,
        maths: list[str] | None = None) -> dict[str, Any]:
    """One pass of the institution. Returns the report it also writes."""
    started = time.monotonic()
    unmeasured: list[str] = []
    previous = _read_json(METHODS) or {}
    pass_index = int(previous.get("pass_index", 0))
    memory = I.TheoremMemory(MEMORY_DIR)
    full_panels, panel_status = ML.build_panels(max_targets)
    unmeasured.extend(panel_status.get("unmeasured") or [])
    workers, memory_status = ML.max_workers()

    # ---- the lockbox is sealed before anyone reads a row
    working: list[Panel] = []
    boxes: list[I.Lockbox] = []
    for panel in full_panels:
        w, box = I.Lockbox.seal(panel)
        working.append(w)
        boxes.append(box)
    if not working:
        report = _report(started, dry_run, panel_status, memory_status,
                         [*unmeasured, "panel: no target produced a usable residual panel this "
                                       "pass"],
                         lockbox=[], departments={}, civilizations={}, cards=[],
                         nulls=[], multiplicity={}, pareto=[], engines={}, design={},
                         memory_graph=memory.graph(), negative=[], credit={}, allocation=previous,
                         registry={}, donation={}, event=None, wiring=I.wiring_proof(
                             {}, {}, list(populations(pass_index, physics, maths)["A"]),
                             list(E.ENGINE_NAMES)))
        if not dry_run:
            I.atomic_json(OUT, report)
        return report

    # ---- department budgets, two-sided by ROI with a floor
    split = E.run_engine("distributed_science", E.distributed_science, budget_s,
                         department_roi())
    budgets = split.summary.get("budgets") or {"physics": budget_s / 3,
                                               "mathematics": budget_s / 3,
                                               "engines": budget_s / 3}
    pops = populations(pass_index, physics, maths)
    civ_results: dict[str, dict[str, dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {}
        for civ, traditions in pops.items():
            for tradition in traditions:
                dept = "physics" if tradition in PHYSICS_REGISTRY else "mathematics"
                n_dept = max(1, sum(1 for t in traditions
                                    if (t in PHYSICS_REGISTRY) == (dept == "physics")))
                share = float(budgets.get(dept, budget_s / 3)) / (len(pops) * n_dept)
                futures[(civ, tradition)] = pool.submit(_run_tradition, civ, tradition, working,
                                                        max(2.0, share), CIVILIZATIONS[civ])
        for (civ, tradition), fut in futures.items():
            try:
                civ_results.setdefault(civ, {})[tradition] = fut.result()
            except Exception as exc:
                civ_results.setdefault(civ, {})[tradition] = {
                    "civilization": civ, "tradition": tradition, "objects": [], "evaluated": 0,
                    "distinct": set(), "unmeasured": [], "status": "FAILED",
                    "why": f"{type(exc).__name__}: {exc}", "compute_s": 0.0, "panels": []}

    # ---- judge every object inside its civilization, then card it
    lifetime = {m: int((previous.get("methods", {}).get(m) or {}).get("lifetime_trials", 0))
                for m in {t for ts in pops.values() for t in ts}}
    # THE WALL CLOCK GOVERNS THE WHOLE PASS, not only the proposal phase. The department split
    # above budgets the SCIENTISTS; judging and review are unbounded loops over whatever they
    # produced, and on a 50,000-row panel they cost more than every scientist together.
    # MEASURED 2026-09-23 at --budget-s 420: elapsed 846 s -- scientists 145 s, engines 75 s,
    # panels 33 s, and the remaining ~590 s the judge and the reviewers. The leg's cap is 700 s,
    # so an ungoverned pass is a leg that is killed before it writes its artifact, which is the
    # same thing as an organ that never ran. Each later phase therefore gets a share of the SAME
    # clock and stops at it, and everything it did not reach is named UNMEASURED by count --
    # never silently dropped, and never promoted unreviewed (a card that misses the reviewers
    # stays PROPOSED, and PROPOSED is not FORWARD).
    judge_deadline = started + 0.72 * budget_s
    review_deadline = started + 0.90 * budget_s
    unjudged = 0
    unreviewed = 0
    cards: list[I.MathHypothesisCard] = []
    objects_by_card: dict[str, tuple[MathObject, Panel]] = {}
    passed_by_civ: dict[str, set[str]] = {}
    scientists_ran: dict[str, dict[str, Any]] = {}
    evaluated_by_method: dict[str, int] = {}
    compute_by_method: dict[str, float] = {}
    civ_summary: dict[str, Any] = {}
    for civ, results in civ_results.items():
        rng = np.random.default_rng(CIVILIZATIONS[civ] + 7)
        passed_here: set[str] = set()
        rows: dict[str, Any] = {}
        for tradition, result in results.items():
            objects = result.get("objects") or []
            distinct = len(result.get("distinct") or set())
            passed = 0
            for obj, view in objects:
                if time.monotonic() > judge_deadline:
                    unjudged += 1
                    continue
                try:
                    B.judge(obj, view, distinct_forms=distinct,
                            lifetime_trials=lifetime.get(tradition, 0), rng=rng,
                            peers=[p for p in working if p.target != obj.target][:2],
                            permutations=permutations)
                except Exception as exc:
                    obj.notes.append(f"{UNMEASURED}: burden.judge raised {type(exc).__name__}")
                    continue
                passed += int(obj.passed)
                if obj.passed:
                    passed_here.add(obj.canonical)
                card = I.card_from_object(
                    obj, domain="physics" if tradition in PHYSICS_REGISTRY else "mathematics",
                    method=tradition, civilization=civ, seed=CIVILIZATIONS[civ],
                    compute_s=float(result.get("compute_s", 0.0)) / max(1, len(objects)))
                cards.append(card)
                objects_by_card[card.card_id] = (obj, view)
            rows[tradition] = {"status": result.get("status"), "why": result.get("why"),
                               "proposed": len(objects), "distinct": distinct,
                               "evaluated": int(result.get("evaluated", 0)), "passed": passed,
                               "compute_s": float(result.get("compute_s", 0.0)),
                               "unmeasured": result.get("unmeasured") or []}
            agg = scientists_ran.setdefault(tradition, {"proposed": 0, "evaluated": 0,
                                                        "passed": 0, "compute_s": 0.0,
                                                        "status": "OK", "civilizations": []})
            agg["proposed"] += len(objects)
            agg["evaluated"] += int(result.get("evaluated", 0))
            agg["passed"] += passed
            agg["compute_s"] += float(result.get("compute_s", 0.0))
            agg["civilizations"].append(civ)
            if result.get("status") != "OK":
                agg["status"] = str(result.get("status"))
            evaluated_by_method[tradition] = evaluated_by_method.get(tradition, 0) + distinct
            compute_by_method[tradition] = compute_by_method.get(tradition, 0.0) + float(
                result.get("compute_s", 0.0))
        passed_by_civ[civ] = passed_here
        civ_summary[civ] = {"seed": CIVILIZATIONS[civ], "traditions": list(results),
                            "objects": sum(r["proposed"] for r in rows.values()),
                            "passed": len(passed_here), "per_tradition": rows}
    replicated_across = set.intersection(*passed_by_civ.values()) if passed_by_civ else set()

    # ---- THE PROPOSER SEAT, OPTIONAL: candidate mechanism names for uninterpreted cards.
    # A card whose mechanism still reads "uninterpreted:" carries a measured relation with no
    # named cause, which the desk's own rule says may not trade. The seat proposes a CAUSE to
    # test; it never sets a status, never clears a gate and never supplies a number -- the
    # proposal lands in `notes`, which no gate reads, and the card is judged exactly as before.
    # Returns {} on a box with no panel, so this whole block is a no-op there.
    seat_named = 0
    try:
        from libs.research import proposer_seat as _ps
        _unnamed = [c for c in cards if str(c.mechanism).startswith("uninterpreted")][:12]
        _names = _ps.names_for("physics_lab",
                               [{"key": c.card_id, "claim": c.claim[:200],
                                 "tradition": c.tradition, "target": c.target} for c in _unnamed])
        for _c in _unnamed:
            _hit = _names.get(_c.card_id)
            if _hit:
                _c.notes.append(f"proposer_seat CANDIDATE mechanism (untested, not an "
                                f"interpretation): {_hit['mechanism']} | falsifier: "
                                f"{_hit['falsifier']} | by {_hit['by'].get('model')}")
                seat_named += 1
    except Exception as _exc:                             # pragma: no cover - optional seat
        seat_named = 0
        del _exc

    # ---- the institution's work on the cards
    first = working[0]
    labels = I.state_discovery(first)
    nulls = I.null_factory(first, np.random.default_rng(SEED + 5), n=6,
                           permutations=max(20, permutations // 4))
    multiplicity = I.multiplicity_ledger(cards, evaluated_by_method)
    cards.sort(key=lambda c: -(c.value if c.value is not None else -9e9))
    reviewed = 0
    for i, card in enumerate(cards):
        obj, view = objects_by_card[card.card_id]
        if time.monotonic() > review_deadline:
            unreviewed += 1
            card.status = "FAILED" if not card.passed else card.status
            continue
        I.pit_check(card, view)
        if not card.passed and i >= MAX_CARDS_REVIEWED:
            card.status = "FAILED"
            continue
        I.consequence_engine(card, view)
        if card.passed and reviewed < MAX_CARDS_REVIEWED:
            reviewed += 1
            I.peer_review(card, view, seed=SEED + i, permutations=max(20, permutations // 4))
            if card.status == "REVIEWED":
                other = [c for c in passed_by_civ if c != card.lineage["civilization"]]
                I.replicate(card, view, seed=SEED + 1000 + i,
                            permutations=max(20, permutations // 4),
                            other_civilization_passed=set.union(*(passed_by_civ[c] for c in other))
                            if other else set())
                I.cross_market(card, [p for p in working if p.target != card.target])
                I.states_of(card, view, labels if view.target == first.target
                            else I.state_discovery(view))
        else:
            card.status = "FAILED" if not card.passed else card.status
    front = I.pareto_front([c for c in cards if c.status != "FAILED"] or cards)
    for card in [c for c in cards if c.status in ("FORWARD", "PROVISIONAL")][:MAX_CAUSAL]:
        I.causal_scientist(card, objects_by_card[card.card_id][1], seed=SEED,
                           n_perm=max(20, permutations // 4))

    # ---- engines on the first panel, with the civilizations' own scientists
    admitted_objects = [objects_by_card[c.card_id][0] for c in cards]
    credit = I.credit_methods(cards, evaluated_by_method, compute_by_method)
    engine_pops = {civ: [S.build(t) for t in pops[civ][:3]] for civ in pops}
    engine_budget = max(10.0, min(float(budgets.get("engines", 60.0)),
                                  started + 0.98 * budget_s - time.monotonic()))
    engines = E.run_all(first, admitted_objects, budget_s=engine_budget,
                        rng=np.random.default_rng(SEED + 9), populations=engine_pops,
                        seeds=dict(CIVILIZATIONS), method_stats=credit,
                        department_roi=department_roi(),
                        permutations=max(20, permutations // 4))
    design = I.experiment_design(cards, (engines["experimental_discrimination"].summary
                                         or {}).get("next_experiment"))

    # ---- memory, credit, allocation
    negative: list[dict[str, Any]] = []
    if not dry_run:
        for card in cards:
            memory.record(card)
        negative = I.failure_scientist(memory)
    allocation = I.evolve_methods(credit, previous)
    allocation["pass_index"] = pass_index + 1
    allocation["rotation_next"] = rotation(pass_index + 1)
    if not dry_run:
        I.atomic_json(METHODS, allocation)

    # ---- registry, donation, events
    forward_objects = [objects_by_card[c.card_id][0] for c in cards
                       if c.status in ("FORWARD", "PROVISIONAL")]
    seen: set[str] = set()
    unique_forward: list[MathObject] = []
    for obj in forward_objects:
        if obj.object_id not in seen:
            seen.add(obj.object_id)
            unique_forward.append(obj)
    already = set((_read_json(DONATED) or {}).get("object_ids") or [])
    donation_rows, refused = ML.donation_rows(unique_forward[:MAX_DONATIONS], already)
    for row in donation_rows:
        row["source"] = SOURCE
        row["kind"] = "hypothesis"
    donation: dict[str, Any] = {"donated": 0, "path": None, "refused_untradeable": len(refused),
                                "already_donated_in_a_previous_pass":
                                    len([o for o in unique_forward if o.object_id in already]),
                                "rule": "only FORWARD/PROVISIONAL cards' objects are donated; "
                                        "a card on one run is never FORWARD"}
    donated_by_tradition: dict[str, int] = {}
    if donation_rows and not dry_run:
        try:
            from research import proposer_common as PC
            path = PC.donate(SOURCE, donation_rows,
                             tests_run=sum(evaluated_by_method.values()))
            donation.update({"path": str(path) if path else None, **PC.donation_counts()})
            for row in donation_rows:
                t = str(row.get("evidence", {}).get("tradition") or "")
                donated_by_tradition[t] = donated_by_tradition.get(t, 0) + 1
            I.atomic_json(DONATED, {"at": I.now_iso(), "object_ids": sorted(
                already | {r["mathlab_object_id"] for r in donation_rows})})
        except Exception as exc:
            donation["status"] = f"{UNMEASURED}: donate raised {type(exc).__name__}: {exc}"
    elif donation_rows:
        donation["status"] = "SKIPPED_DRY_RUN"
    donation["by_tradition"] = donated_by_tradition
    per_tradition_registry = {t: {"proposed": v["proposed"], "distinct": v.get("evaluated", 0),
                                  "evaluated": v["evaluated"], "passed": v["passed"],
                                  "compute_s": v["compute_s"],
                                  "target": working[0].target}
                              for t, v in scientists_ran.items()}
    seen.clear()
    unique_admitted = [o for o in admitted_objects
                       if not (o.object_id in seen or seen.add(o.object_id))]  # type: ignore[func-returns-value]
    registry = ({"status": "SKIPPED_DRY_RUN"} if dry_run
                else ML.record_registry(unique_admitted, per_tradition_registry,
                                        donated_by_tradition))
    event = None if dry_run else I.event_row(
        "MATH_CARDS_JUDGED", leg="physics_lab", cards=len(cards),
        forward=sum(1 for c in cards if c.status == "FORWARD"),
        provisional=sum(1 for c in cards if c.status == "PROVISIONAL"),
        nulls_rejected=sum(1 for n in nulls if n.get("passed") is False))

    if unjudged:
        unmeasured.append(f"budget: {unjudged} proposed objects were not judged this pass "
                          f"(judge deadline {0.72 * budget_s:.0f}s of a {budget_s:.0f}s budget)")
    if unreviewed:
        unmeasured.append(f"budget: {unreviewed} cards did not reach the reviewers this pass "
                          f"(review deadline {0.90 * budget_s:.0f}s); a card that misses review "
                          f"stays PROPOSED and cannot be FORWARD")
    if not seat_named:
        unmeasured.append("proposer_seat: no candidate mechanism name was proposed this pass "
                          "(no panel resolves, or no card was uninterpreted) -- UNMEASURED, and "
                          "every card was judged exactly as it is without the seat")
    lockbox = [box.verify(panel) for box, panel in zip(boxes, full_panels, strict=False)]
    wiring = I.wiring_proof(scientists_ran, engines, list(pops["A"]), list(E.ENGINE_NAMES))
    report = _report(started, dry_run, panel_status, memory_status, unmeasured, lockbox=lockbox,
                     departments={"budgets": budgets, "shares": split.summary.get("shares"),
                                  "roi": {r["department"]: r.get("roi") for r in split.findings}},
                     civilizations={**civ_summary,
                                    "replicated_across_civilizations": sorted(replicated_across),
                                    "compared_by": "the judge only"},
                     cards=cards, nulls=nulls, multiplicity=multiplicity, pareto=front,
                     engines=engines, design=design, memory_graph=memory.graph(),
                     negative=negative, credit=credit, allocation=allocation, registry=registry,
                     donation=donation, event=event, wiring=wiring,
                     working_rows={p.target: p.n for p in working})
    if not dry_run:
        I.atomic_json(OUT, report)
    return report


def _report(started: float, dry_run: bool, panel_status: dict[str, Any],
            memory_status: dict[str, Any], unmeasured: list[str], *, lockbox: list[Any],
            departments: dict[str, Any], civilizations: dict[str, Any],
            cards: list[I.MathHypothesisCard], nulls: list[dict[str, Any]],
            multiplicity: dict[str, Any], pareto: list[dict[str, Any]],
            engines: dict[str, Any], design: dict[str, Any], memory_graph: dict[str, Any],
            negative: list[dict[str, Any]], credit: dict[str, Any], allocation: dict[str, Any],
            registry: dict[str, Any], donation: dict[str, Any], event: Any,
            wiring: dict[str, Any], working_rows: dict[str, int] | None = None
            ) -> dict[str, Any]:
    by_status = {s: sum(1 for c in cards if c.status == s) for s in I.STATUSES}
    by_domain = {d: sum(1 for c in cards if c.domain == d) for d in ("mathematics", "physics")}
    engine_rows = {k: (v.to_row() if hasattr(v, "to_row") else v) for k, v in engines.items()}
    for row in engine_rows.values():
        if isinstance(row, dict):
            row.get("summary", {}).pop("predictions", None)
    top = sorted(cards, key=lambda c: -(c.value if c.value is not None else -9e9))
    shown = [c for c in top if c.status == "FORWARD"] + [c for c in top
                                                          if c.status != "FORWARD"][:30]
    nulls_judged = [n for n in nulls if "passed" in n]
    return {
        "at": I.now_iso(), "rule": RULE, "dry_run": dry_run,
        "elapsed_s": round(time.monotonic() - started, 2),
        "panel": panel_status, "memory": memory_status,
        "lockbox": {"share": I.LOCKBOX_SHARE, "panels": lockbox,
                    "untouched": all(b.get("untouched") for b in lockbox) if lockbox else None,
                    "cards": I.lockbox_respected(cards, working_rows or {})},
        "departments": departments, "civilizations": civilizations,
        "cards": {"total": len(cards), "by_status": by_status, "by_domain": by_domain,
                  "with_falsifier": sum(1 for c in cards if c.falsifier.strip()),
                  "reviewed_accept": sum(1 for c in cards
                                         if c.review.get("verdict") == "ACCEPT"),
                  "replicated": sum(1 for c in cards if c.replication.get("replicated")),
                  "pit_clean": sum(1 for c in cards if c.pit.get("clean")),
                  "rows": [c.to_row() for c in shown]},
        "null_factory": {"planted": len(nulls_judged),
                         "rejected": sum(1 for n in nulls_judged if n["passed"] is False),
                         "rejection_rate": (round(sum(1 for n in nulls_judged
                                                      if n["passed"] is False)
                                                  / len(nulls_judged), 4)
                                            if nulls_judged else None),
                         "rows": nulls},
        "multiplicity": multiplicity, "pareto_front": pareto,
        "engines": engine_rows, "experiment_design": design,
        "theorem_memory": {"path": str(MEMORY_DIR), **memory_graph,
                           "negative_knowledge_new": negative},
        "method_credit": credit, "method_allocation": allocation,
        "registry": registry, "donation": donation, "event": event,
        "wiring_proof": wiring,
        "unmeasured": unmeasured + [f"{t}/{u}" for civ in civilizations.values()
                                    if isinstance(civ, dict)
                                    for t, row in (civ.get("per_tradition") or {}).items()
                                    for u in row.get("unmeasured", [])],
        "allocates_capital": False,
        "gauntlet": ("every donated object meets the ten gates in scripts/external_gauntlet.py "
                     "with every other hypothesis; this organ certifies nothing"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass, then exit (the only mode)")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--dry-run", action="store_true", help="measure and write nothing")
    ap.add_argument("--max-targets", type=int, default=MAX_TARGETS)
    ap.add_argument("--physics", default="", help="comma-separated subset of physics traditions")
    ap.add_argument("--maths", default="", help="comma-separated subset of maths traditions")
    a = ap.parse_args(argv)
    physics = [t.strip() for t in a.physics.split(",") if t.strip()] or None
    maths = [t.strip() for t in a.maths.split(",") if t.strip()] or None
    report = run(budget_s=a.budget_s, dry_run=a.dry_run, max_targets=a.max_targets,
                 physics=physics, maths=maths)
    print(json.dumps({"at": report["at"], "elapsed_s": report["elapsed_s"],
                      "cards": report["cards"]["total"],
                      "by_status": report["cards"]["by_status"],
                      "nulls_rejected": report["null_factory"].get("rejected"),
                      "lockbox_untouched": report["lockbox"].get("untouched"),
                      "wiring_complete": report["wiring_proof"].get("complete"),
                      "donated": report["donation"].get("donated"),
                      "unmeasured": len(report["unmeasured"])}, indent=1, default=str))
    return 0


if __name__ == "__main__":                                                # pragma: no cover
    with contextlib.suppress(KeyboardInterrupt):
        raise SystemExit(main())
