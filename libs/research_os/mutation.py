"""A diagnosis that produces no child is advice. This turns the diagnosis into the next candidate.

WHY THIS EXISTS (2026-08-30)

The hourly loop already diagnoses every failure into one of six states and prints its
`next_action` -- `mutate_measurement`, `mutate_horizon_or_venue`, `fix_implementation`. Nothing
acted on any of it. The desk was correctly identifying which link of the chain broke and then
doing nothing with the answer, which is the same as not diagnosing at all: the loop terminated in
a recommendation nobody read.

SURGICAL MUTATION IS THE WHOLE POINT. A research trajectory is a chain --

    mechanism -> observable -> timing -> implementation -> parameters -> market

-- and a failure indicts ONE link. Re-rolling the whole candidate throws away the five links that
were fine, which is precisely how `discovered` generated 10,624 candidates for 7 certificates:
blind re-rolls of an idea whose mechanism was never the problem. Changing only the indicted link
is the difference between ten thousand cousins of one idea and a handful of genuine descendants.

WHAT EACH STATE PRODUCES, and why:

    MEASUREMENT_FAILED    a child with a BETTER OBSERVABLE, same mechanism. If the adapter
                          registry has an attributable adapter that the parent did not use, that
                          is the child. This is the highest-value mutation the desk has, because
                          it is how a mechanism measured by a heuristic gets a real test.
    COST_FAILED           a child at a LONGER HORIZON, same everything else. The effect was real
                          and the spread ate it; more time per trade is the direct answer.
    IMPLEMENTATION_FAILED no child. A bug is fixed, not bred -- generating a descendant from
                          broken code propagates the bug and hides it behind a new id.
    DATA_UNAVAILABLE      no child. The parent is PARKED against the observable it needs, and is
                          revived automatically when that data arrives.
    REDUNDANT             no child. The mechanism is valid and the book already holds it; a
                          descendant would be a second copy of a duplicate.
    MECHANISM_REFUTED     no child IN THIS BRANCH. The indictment is the mechanism itself, so the
                          correct move is to explore a different region -- which is the search
                          controller's job, not a mutation.

CHILDREN INHERIT ZERO CREDIBILITY. Every child starts at IDEA and faces the full bar. An
evolutionary search that lets descendants inherit parental standing is how one mediocre strategy
becomes five hundred "discoveries".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Diagnosis state -> whether a child is the right response, and which link it changes.
#: Three of the six deliberately produce NOTHING, and that is a design decision rather than a
#: gap: breeding from a bug, from missing data, or from a duplicate all create work that cannot
#: pay.
MUTATION_FOR_STATE: dict[str, str | None] = {
    "MEASUREMENT_FAILED": "observable",
    "COST_FAILED": "horizon",
    "IMPLEMENTATION_FAILED": None,
    "DATA_UNAVAILABLE": None,
    "REDUNDANT": None,
    "MECHANISM_REFUTED": None,
}

#: Horizon ladder for a cost failure. A cost is paid per TRADE, so the direct remedy is fewer,
#: longer trades -- and the steps are coarse because a 10% horizon change does not move a cost
#: that took the whole edge.
_HORIZON_LADDER = ("1h", "4h", "daily")


@dataclass
class Child:
    """A mutated descendant. Starts at IDEA with no inherited standing whatsoever."""

    parent_id: str
    mutation: str
    changed: dict[str, Any]
    params: dict[str, Any]
    rationale: str
    starts_at: str = "IDEA"
    inherited_credibility: float = 0.0
    parent_ids: tuple[str, ...] = field(default_factory=tuple)


def _better_observable(mechanism: str, current_status: str,
                       spec: dict[str, Any] | None = None) -> tuple[str, str] | None:
    """An adapter for this mechanism that would measure it BETTER than the parent did.

    Returns (adapter_name, status) or None. "Better" means attributable when the parent's was
    not -- a lateral move between two heuristics is not a mutation, it is a coin flip wearing a
    new id.
    """
    try:
        from libs.research_os.adapters import REGISTRY
    except ImportError:
        return None
    adapter = REGISTRY.get(mechanism)
    if adapter is None:
        return None
    # PASS THE PARENT'S FULL SPEC, not just the mechanism. A first version called
    # `compatibility({"mechanism": ...})` with no symbol, so CotPositioningAdapter could not
    # resolve a currency, scored 0.0, and the mutator refused to breed a child that would have
    # measured positioning with REAL COT instead of a price proxy. The one mutation with the
    # highest value on this desk was silently declining itself.
    #
    # `compatibility` is evaluated against the data present RIGHT NOW, so an adapter unusable
    # last week may be usable today -- exactly what a parked candidate is waiting for.
    probe = {"mechanism": mechanism, **(spec or {})}
    score = adapter.compatibility(probe)
    if score <= 0:
        return None

    rank = {"UNAVAILABLE": 0, "HEURISTIC_PROXY": 1, "VALIDATED_PROXY": 2, "DIRECT": 3}
    if rank.get(current_status, 0) >= 2:
        return None                       # already attributable; a better observable is not the fix

    # A LATERAL MOVE IS NOT A MUTATION. `compatibility` below this means the adapter is running
    # in its DEGRADED mode -- LiquidityAdapter without a spread surface, CotPositioning with no
    # matching currency -- so the child would be measured by the same kind of stand-in that
    # produced the parent's failure, and would fail the same way for the same reason.
    #
    # Caught by breeding exactly that: a liquidity_shock parent measured HEURISTIC by
    # LiquidityAdapter produced a "child" measured HEURISTIC by LiquidityAdapter. A new id and
    # nothing else. The docstring above already called this a coin flip; the code was making it.
    if score < _ATTRIBUTABLE_COMPATIBILITY:
        return None
    if params_use_same_adapter(spec, adapter.__class__.__name__):
        return None
    return adapter.__class__.__name__, "candidate"


#: Compatibility at or above which an adapter is running on its REAL observable rather than a
#: degraded fallback. Below this the adapter still measures something, but not the thing that
#: would make the child a genuine improvement over its parent.
_ATTRIBUTABLE_COMPATIBILITY = 0.7


def params_use_same_adapter(spec: dict[str, Any] | None, adapter_name: str) -> bool:
    """Was the parent already measured by this adapter? Then the child changes nothing."""
    if not spec:
        return False
    return str(spec.get("measured_by") or "") == adapter_name


def mutate(diagnosis: Any, parent_id: str, parent_params: dict[str, Any]) -> Child | None:
    """Turn one diagnosis into one child, or None when breeding is the wrong response.

    Returning None is a real answer and the common one. Three of the six states should produce
    no descendant at all, and a mutator that always returns something would fill the docket with
    children of bugs, of missing data, and of duplicates.
    """
    state = getattr(diagnosis, "state", "")
    mech = getattr(diagnosis, "mechanism", "")
    kind = MUTATION_FOR_STATE.get(state)
    if kind is None:
        return None

    params = dict(parent_params or {})

    if kind == "observable":
        better = _better_observable(mech, getattr(diagnosis, "measurement_class", ""), params)
        if better is None:
            # NO BETTER OBSERVABLE EXISTS. Mutating to another heuristic would produce a child
            # that fails the same way for the same reason, so the honest output is a data need
            # rather than a candidate.
            return None
        adapter_name, _ = better
        params["measured_by"] = adapter_name
        return Child(
            parent_id=parent_id, parent_ids=(parent_id,), mutation="observable",
            changed={"measured_by": adapter_name},
            params=params,
            rationale=(f"parent was {getattr(diagnosis, 'measurement_class', 'un')}measured, so "
                       f"its failure refuted the STAND-IN rather than {mech}. This child uses "
                       f"{adapter_name}, which measures the mechanism's own observable. The "
                       f"mechanism is untouched -- only how it is seen."))

    if kind == "horizon":
        cur = str(params.get("output") or "1h")
        try:
            nxt = _HORIZON_LADDER[_HORIZON_LADDER.index(cur) + 1]
        except (ValueError, IndexError):
            # ALREADY AT THE LONGEST HORIZON. A cost that survives a daily hold is a cost this
            # venue simply charges, and no further stretching fixes it.
            return None
        params["output"] = nxt
        return Child(
            parent_id=parent_id, parent_ids=(parent_id,), mutation="horizon",
            changed={"output": f"{cur} -> {nxt}"},
            params=params,
            rationale=(f"gross positive, net negative: the effect is real and the spread took it. "
                       f"Cost is paid per TRADE, so the direct remedy is fewer and longer trades "
                       f"-- {cur} to {nxt}. Mechanism, measurement and direction all unchanged."))
    return None


def mutate_batch(diagnoses: list[Any], parents: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Mutate a batch, and report what was DELIBERATELY not bred.

    The refusals matter as much as the children: a run that produces two children from forty
    failures is working correctly if thirty-eight of those failures were bugs, missing data or
    duplicates. Reporting only the children would make a healthy run look barren.
    """
    children: list[Child] = []
    refused: dict[str, int] = {}
    for d in diagnoses:
        pid = getattr(d, "hypothesis_id", "") or getattr(d, "mechanism", "unknown")
        child = mutate(d, pid, parents.get(pid, {}))
        if child is None:
            key = getattr(d, "state", "unknown")
            refused[key] = refused.get(key, 0) + 1
            continue
        children.append(child)
    return {
        "children": [
            {"parent": c.parent_id, "mutation": c.mutation, "changed": c.changed,
             "params": c.params, "starts_at": c.starts_at,
             "inherited_credibility": c.inherited_credibility, "rationale": c.rationale}
            for c in children],
        "n_children": len(children),
        "not_bred": refused,
        "why_not_bred": ("IMPLEMENTATION_FAILED is fixed not bred; DATA_UNAVAILABLE parks the "
                         "parent until the observable arrives; REDUNDANT already exists in the "
                         "book; MECHANISM_REFUTED indicts the branch itself, so the answer is to "
                         "explore elsewhere rather than to breed here."),
    }
