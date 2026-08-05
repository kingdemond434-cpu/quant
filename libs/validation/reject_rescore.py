"""Reject re-score PLANNING -- the ROI decision of the rejection-shadow feeder.

The feeder that closes the gate-leak loop must re-score rejected candidates on data that arrived
AFTER their rejection. Re-scoring ALL rejects is wasteful, so the ROI is in the NEAR-MISSES --
rejects whose in-sample edge was strong but that failed a multiplicity/robustness gate; those are
the ones a drifted-over-strict gate most plausibly killed by mistake.

PREMISE CORRECTED 2026-08-05 (R0244). This docstring used to justify the ordering with "the 420
picked-clean price rejects are almost all genuinely dead". That claim was RETRACTED by the gate
re-certification: the campaign path now gates per-candidate (cscv PBO + Romano-Wolf stepdown via
campaign_gate_stats) rather than on the welded campaign-wide constants the 420 were judged under,
so "already known dead" is not something this module is entitled to assume about them. The
ordering survives the retraction on its own merits -- near-miss-first is the right spend under a
batch cap whatever the base rate -- and, importantly, the code never encoded the refuted premise:
there is no branch excluding the 420, only a nearness ranking and a cap. They compete for the
batch like everything else, and a high-nearness price reject outranks a low-nearness new one.

So the feeder's intelligence is: take only rejects OLD ENOUGH to have accrued forward data, rank
them by how CLOSE they came to passing (near-miss first), and cap the batch so compute goes to the
recoverable few. This module is that pure, testable planner; the runtime-heavy re-eval itself
(rebuild the candidate's signal, run it on the forward window) is injected by the runner, not faked.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from libs.core.time import from_iso8601, utcnow


class RescorePlan(BaseModel):
    """The prioritized, eligibility-filtered, capped batch of reject ids to re-score this run."""

    model_config = ConfigDict(frozen=True)

    selected: tuple[str, ...]  # reject ids to re-score, near-miss first
    n_eligible: int  # rejects old enough to have forward data
    n_too_young: int  # rejects skipped for having no forward data yet
    n_capped: int  # eligible rejects deferred to a later run by the batch cap
    verdict: str


def plan_rescore(
    rejects: Sequence[tuple[str, str, float]],
    *,
    as_of: str | None = None,
    min_age_days: float = 30.0,
    limit: int = 50,
) -> RescorePlan:
    """Plan which rejects to re-score, near-miss first (MAX-ROI feeder scheduling).

    ``rejects`` is ``(candidate_id, rejected_at_iso, nearness)`` where ``nearness`` is a monotone
    proxy for how close the reject came to passing (e.g. its in-sample / OOS Sharpe at rejection --
    higher = nearer the bar = more likely a gate error worth recovering). Only rejects at least
    ``min_age_days`` old are eligible (younger ones have no post-rejection data to score). The
    eligible set is ranked by ``nearness`` descending and truncated to ``limit`` so compute lands on
    the recoverable few, not the picked-clean many. Deterministic: ties break by id.
    """
    now = from_iso8601(as_of) if as_of else utcnow()
    eligible: list[tuple[str, float]] = []
    too_young = 0
    for cid, rejected_at, nearness in rejects:
        try:
            age_days = (now - from_iso8601(rejected_at)).total_seconds() / 86400.0
        except Exception:
            continue
        if age_days < min_age_days:
            too_young += 1
            continue
        eligible.append((cid, float(nearness)))
    eligible.sort(key=lambda x: (-x[1], x[0]))  # near-miss first, deterministic tie-break
    selected = tuple(cid for cid, _ in eligible[:limit])
    n_capped = max(0, len(eligible) - len(selected))
    if not eligible:
        verdict = f"no eligible rejects (>= {min_age_days:g}d old); {too_young} too young to score"
    else:
        verdict = (
            f"{len(selected)} near-miss rejects queued for re-score (of {len(eligible)} eligible; "
            f"{n_capped} deferred by cap {limit}; {too_young} too young)"
        )
    return RescorePlan(
        selected=selected, n_eligible=len(eligible), n_too_young=too_young,
        n_capped=n_capped, verdict=verdict,
    )
