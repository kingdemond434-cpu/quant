"""Which REUSABLE decision earned the outcome -- not which strategy id happened to hold it.

WHY THIS EXISTS (2026-08-30)

`lineage_dag.assign_credit` already names the failing STEP of one candidate. That is per-candidate
blame. It answers "which link broke here" and cannot answer the question the allocator actually
asks every hour: WHICH GENERATOR, WHICH MECHANISM, WHICH OBSERVABLE is worth more budget. Those
are the reusable assets. A strategy id is consumed the moment it fails; the mechanism behind it is
tried again next week under a new id, and nothing was learning across that boundary.

THE SPARSE-REWARD PROBLEM IS THE WHOLE DIFFICULTY. `forward_survived = 0`. A credit scheme that
only pays out on terminal success divides by zero forever: every asset scores 0.0, the ranking is
arbitrary, and the allocator is steered by noise while believing it is steered by evidence. Two
things fix it, and both are needed:

    SHAPED DEPTH   reaching the forward lane is worth more than compiling, which is worth more
                   than an idea. Partial credit for depth is a potential function over the
                   pipeline, so the ranking is informative long before the first survivor and
                   converges to the terminal ranking once survivors exist.
    ADVANTAGE      credit is scored against the MEAN trajectory value, not against zero. An asset
                   is not "good" because it reached backtest -- almost everything reaches
                   backtest. It is good because it reached FURTHER THAN THE TYPICAL CANDIDATE.
                   The baseline is computed from the data, so it re-centres itself as the desk
                   improves and cannot be gamed by a generator that floods the docket.

DISCOUNTING BACKWARD IS NOT DECORATION. A child's success is mostly the child's; the
great-grandparent contributed the mechanism and little else. Undiscounted credit makes the root of
the largest subtree the highest-scoring asset in the desk regardless of merit, which is a fertility
count wearing the word "credit".

THE ATTRIBUTABILITY RULE IS LOAD-BEARING AND IT IS THE SAME RULE AS `failure_states`.
Credit reaches a MECHANISM only when the measurement was attributable. When a candidate was
measured by a heuristic stand-in, the outcome -- good OR bad -- is evidence about THE STAND-IN, so
the credit goes to the adapter and never to the mechanism. Skipping this is how a desk concludes
"positioning does not work" after testing a price proxy for positioning, and then never tries the
COT data sitting on its own disk. The rule is symmetric on purpose: a heuristic that gets lucky
must not promote a mechanism either.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

#: Depth reached -> value. The ladder IS the shaping: each rung is a strictly harder filter than
#: the one below it, so a higher value cannot be reached by an easier path. Terminal success is
#: 1.0 and everything below it is a fraction of a survivor, which is the honest way to say
#: "promising" without letting promising masquerade as proven.
STAGE_VALUE: dict[str, float] = {
    "IDEA": 0.00,
    "COMPILED": 0.05,
    "MEASURED_HEURISTIC": 0.08,
    "MEASURED_ATTRIBUTABLE": 0.15,
    "BACKTEST_POSITIVE": 0.30,
    "COST_SURVIVED": 0.45,
    "FORWARD_ENROLLED": 0.60,
    "FORWARD_SURVIVED": 1.00,
    "CERTIFIED": 1.00,
    "LIVE": 1.00,
}

#: Stages that are real evidence rather than shaped progress. While NO trajectory has reached one
#: of these, every credit number below is a PRIOR over an unfinished search and the report says so
#: in as many words -- a shaped ranking read as a proven one is exactly the overclaim this desk
#: exists to avoid.
TERMINAL_STAGES = frozenset({"FORWARD_SURVIVED", "CERTIFIED", "LIVE"})

#: Per-generation discount walking BACK from the outcome. 0.7 means a grandparent receives about
#: half of what the parent receives: enough that a mechanism which repeatedly seeds deep
#: descendants rises, little enough that a large family cannot out-score a good one.
GAMMA = 0.7

#: Measurement classes that may move a MECHANISM's credit. Below this the outcome is evidence
#: about the stand-in and is booked against the adapter instead.
ATTRIBUTABLE = frozenset({"VALIDATED_PROXY", "DIRECT"})

#: Asset kinds credit is assigned to. Each is REUSABLE -- it outlives the candidate that carried
#: it, which is the entire reason it is worth scoring. `strategy_id` is deliberately absent.
ASSET_KINDS = ("generator", "mechanism", "adapter", "mutation", "coordinate")

#: Below this many trajectories an asset's score is noise. It is still reported -- suppressing it
#: would hide young assets entirely -- but flagged, so the allocator can widen rather than back a
#: single lucky trajectory.
MIN_TRAJECTORIES_FOR_CONFIDENCE = 5


@dataclass
class Trajectory:
    """One candidate's path, plus the ancestry it inherited."""

    hypothesis_id: str
    stage: str = "IDEA"
    generation: int = 0
    generator: str = ""
    mechanism: str = ""
    adapter: str = ""
    mutation: str = ""
    coordinate: str = ""
    measurement_class: str = ""
    arm: str = ""
    parent_ids: tuple[str, ...] = field(default_factory=tuple)

    @property
    def value(self) -> float:
        return STAGE_VALUE.get(self.stage, 0.0)

    @property
    def attributable(self) -> bool:
        return self.measurement_class in ATTRIBUTABLE


@dataclass
class Credit:
    """An asset's advantage over the typical candidate, and how much to trust it."""

    kind: str
    name: str
    advantage: float
    n_trajectories: int
    best_stage: str
    attributable_share: float

    @property
    def confident(self) -> bool:
        return self.n_trajectories >= MIN_TRAJECTORIES_FOR_CONFIDENCE


def _assets(t: Trajectory) -> list[tuple[str, str]]:
    """The reusable assets this trajectory used, with the attributability rule applied.

    A mechanism is only listed when the measurement could speak about it. That single condition
    is what stops a heuristic's failure from burying a mechanism the desk has never actually
    tested.
    """
    out: list[tuple[str, str]] = []
    if t.generator:
        out.append(("generator", t.generator))
    if t.adapter:
        out.append(("adapter", t.adapter))
    if t.mutation:
        out.append(("mutation", t.mutation))
    if t.coordinate:
        out.append(("coordinate", t.coordinate))
    if t.mechanism and t.attributable:
        out.append(("mechanism", t.mechanism))
    return out


def assign(trajectories: list[Trajectory]) -> dict[str, Any]:
    """Advantage-weighted credit for every reusable asset, discounted back along ancestry.

    Pure: takes trajectories, returns a report. Every number is derivable from the input, which
    is what makes the result auditable rather than merely produced.
    """
    if not trajectories:
        return {"assets": [], "baseline": 0.0, "n": 0,
                "basis": "NO TRAJECTORIES -- nothing has been recorded, so there is no ranking",
                "terminal_evidence": False}

    by_id = {t.hypothesis_id: t for t in trajectories}
    baseline = sum(t.value for t in trajectories) / len(trajectories)

    # ADVANTAGE, not raw value. Subtracting the mean is what turns "reached backtest" (which
    # nearly everything does) into a statement about being better than the alternative.
    scores: dict[tuple[str, str], float] = defaultdict(float)
    counts: dict[tuple[str, str], int] = defaultdict(int)
    best: dict[tuple[str, str], float] = defaultdict(float)
    attributable_hits: dict[tuple[str, str], int] = defaultdict(int)

    for t in trajectories:
        advantage = t.value - baseline

        # Walk BACK through ancestry, discounting. A cycle or a missing parent stops the walk
        # rather than looping: a truncated chain under-credits an ancestor, an infinite one hangs
        # the hourly loop.
        seen: set[str] = {t.hypothesis_id}
        frontier = [(t, 0)]
        while frontier:
            node, depth = frontier.pop()
            weight = GAMMA ** depth
            for kind, name in _assets(node):
                key = (kind, name)
                scores[key] += advantage * weight
                if depth == 0:
                    counts[key] += 1
                    best[key] = max(best[key], t.value)
                    if node.attributable:
                        attributable_hits[key] += 1
            for pid in node.parent_ids:
                parent = by_id.get(pid)
                if parent is not None and pid not in seen:
                    seen.add(pid)
                    frontier.append((parent, depth + 1))

    stage_of = {v: k for k, v in sorted(STAGE_VALUE.items(), key=lambda kv: kv[1])}
    assets = [
        Credit(kind=kind, name=name,
               advantage=round(score, 5),
               n_trajectories=counts[(kind, name)],
               best_stage=stage_of.get(best[(kind, name)], "IDEA"),
               attributable_share=round(
                   attributable_hits[(kind, name)] / counts[(kind, name)], 3)
               if counts[(kind, name)] else 0.0)
        for (kind, name), score in scores.items()
    ]
    assets.sort(key=lambda c: -c.advantage)

    terminal = any(t.stage in TERMINAL_STAGES for t in trajectories)
    return {
        "n": len(trajectories),
        "baseline": round(baseline, 5),
        "terminal_evidence": terminal,
        "basis": ("TERMINAL: at least one trajectory reached a survivor stage, so this ranking "
                  "rests on outcomes"
                  if terminal else
                  "SHAPED: no trajectory has survived forward yet, so every score below is depth "
                  "reached rather than money made. Use it to ALLOCATE SEARCH, never to promote."),
        "gamma": GAMMA,
        "assets": [
            {"kind": c.kind, "name": c.name, "advantage": c.advantage,
             "n": c.n_trajectories, "best_stage": c.best_stage,
             "attributable_share": c.attributable_share, "confident": c.confident}
            for c in assets],
        "note": ("credit reaches a MECHANISM only through an attributable measurement; heuristic "
                 "outcomes are booked against the ADAPTER, because that is what was tested"),
    }


def _stage_for(hid: str, conn: Any) -> tuple[str, str, str]:
    """Deepest stage this hypothesis reached, its measurement class and its adapter.

    Read from what actually happened -- measurements, experiments, forward enrolment -- rather
    than from a status field somebody might forget to update. A stage nobody can evidence is not
    a stage the desk reached.
    """
    mcls = adapter = ""
    row = conn.execute(
        "SELECT status, adapter FROM measurements WHERE hypothesis_id=? "
        "ORDER BY id DESC LIMIT 1", (hid,)).fetchone()
    if row:
        mcls, adapter = str(row[0] or ""), str(row[1] or "")

    stage = "IDEA"
    if mcls:
        stage = "MEASURED_ATTRIBUTABLE" if mcls in ATTRIBUTABLE else "MEASURED_HEURISTIC"

    exp = conn.execute(
        "SELECT exp_r_gross, exp_r_net, stage, passed FROM experiments WHERE hypothesis_id=? "
        "ORDER BY id DESC LIMIT 1", (hid,)).fetchone()
    if exp:
        gross, net, exp_stage, passed = exp
        if (gross or 0.0) > 0:
            stage = "BACKTEST_POSITIVE"
        if (net or 0.0) > 0:
            stage = "COST_SURVIVED"
        named = str(exp_stage or "").upper()
        if named in STAGE_VALUE and STAGE_VALUE[named] > STAGE_VALUE[stage]:
            stage = named
        if passed and STAGE_VALUE.get(stage, 0.0) < STAGE_VALUE["FORWARD_ENROLLED"]:
            stage = "FORWARD_ENROLLED"
    return stage, mcls, adapter


def from_store() -> dict[str, Any]:
    """Build trajectories from the research store and assign credit over them."""
    from libs.research_os import store

    with store.connect() as conn:
        rows = conn.execute(
            "SELECT hypothesis_id, generator, mechanism, coordinate, parent_ids, generation, "
            "brain_version, spec FROM hypotheses").fetchall()
        trajectories = []
        for hid, gen_name, mech, coord, parents, generation, arm, spec in rows:
            try:
                pids = tuple(json.loads(parents or "[]"))
            except (json.JSONDecodeError, TypeError):
                pids = ()
            try:
                spec_d = json.loads(spec or "{}")
            except (json.JSONDecodeError, TypeError):
                spec_d = {}
            stage, mcls, adapter = _stage_for(str(hid), conn)
            trajectories.append(Trajectory(
                hypothesis_id=str(hid), stage=stage, generation=int(generation or 0),
                generator=str(gen_name or ""), mechanism=str(mech or ""),
                adapter=adapter or str(spec_d.get("measured_by") or ""),
                mutation=str(spec_d.get("mutation") or ""),
                coordinate=str(coord or ""), measurement_class=mcls,
                arm=str(arm or ""), parent_ids=tuple(str(p) for p in pids)))
    return assign(trajectories)
