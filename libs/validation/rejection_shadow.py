"""Rejection-shadow orchestration -- the audit layer over the EXISTING reject ledger.

The reject ledger already exists: ``CandidateStore`` persists every rejected candidate as a
``survived = 0`` row (id, rejected-at, in-sample metrics). What was missing is the audit that
shadow-tracks a sample of those rejects forward and asks whether the gate has drifted over-strict
-- MAX_SURVIVORS Part 1.2. This module assembles the audit input from the ledger and runs the
tested primitive (``gate_calibration.rejection_shadow_audit``); it does NOT rebuild the ledger.

The one piece that is inherently runtime-heavy -- RE-SCORING each reject on data that arrived
AFTER its rejection -- is injected as ``forward_scores`` (id -> realized forward metric), produced
by the desk's forward evaluator and never fabricated here. A reject too young to have accrued
forward data, or not yet re-scored, is carried as pending, never guessed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from libs.core.time import from_iso8601, utcnow
from libs.validation.gate_calibration import RejectionShadowReport, rejection_shadow_audit


class ShadowRunReport(BaseModel):
    """One rejection-shadow run: the audit verdict plus how much of the ledger needs scoring."""

    model_config = ConfigDict(frozen=True)

    as_of: str
    n_rejects_total: int  # all rejects in the ledger
    n_eligible: int  # old enough (>= min_age_days) to have accrued forward data
    n_pending_rescore: int  # eligible but not yet forward-scored -- the work still to do
    audit: RejectionShadowReport  # the shelf tool's verdict over the scored eligible rejects
    verdict: str

    def __bool__(self) -> bool:
        return not self.audit.over_strict


def build_shadow_report(
    rejects: Sequence[tuple[str, str]],
    forward_scores: Mapping[str, float | Mapping[str, object]],
    *,
    deploy_threshold: float,
    as_of: str | None = None,
    min_age_days: float = 30.0,
    leak_tolerance: float = 0.10,
    min_sample: int = 5,
) -> ShadowRunReport:
    """Assemble the rejection-shadow audit from the reject ledger + injected forward scores.

    ``rejects`` is ``(candidate_id, rejected_at_iso)`` straight from ``CandidateStore.rejects()``.
    ``forward_scores`` maps a candidate id to its realized metric measured on data AFTER rejection
    (the desk's forward evaluator writes this; missing == not yet scored) -- either a bare float
    (judged at the raw deploy bar) or ``{"sharpe": float, "n_fwd_bars": int}`` (judged at the
    noise-adjusted bar for that window). A reject is ELIGIBLE only
    once it is at least ``min_age_days`` old, so an edge rejected yesterday cannot be judged (it has
    no forward data). Eligible-but-unscored rejects are counted as pending work; eligible-and-scored
    rejects feed ``rejection_shadow_audit``. If a non-trivial slice of the scored rejects would have
    paid out-of-sample, the audit flags the gate over-strict -- pure recovery, no new data.
    """
    now = from_iso8601(as_of) if as_of else utcnow()
    eligible: list[tuple[str, float | None, int | None]] = []
    n_eligible = 0
    for cid, rejected_at in rejects:
        try:
            age_days = (now - from_iso8601(rejected_at)).total_seconds() / 86400.0
        except Exception:
            continue
        if age_days < min_age_days:
            continue  # too young to have forward data -- never guess
        n_eligible += 1
        entry = forward_scores.get(cid)
        # Two score forms: the rescorer writes {"sharpe": ..., "n_fwd_bars": ...} so the audit
        # can noise-adjust the pay bar at the entry's actual window; a bare float (legacy, or a
        # caller asserting a judgment-ready metric) keeps the raw threshold.
        if isinstance(entry, Mapping):
            raw_m = entry.get("sharpe")
            raw_n = entry.get("n_fwd_bars")
            if isinstance(raw_m, int | float):
                n_bars = int(raw_n) if isinstance(raw_n, int | float) and raw_n else None
                eligible.append((cid, float(raw_m), n_bars))
            else:
                eligible.append((cid, None, None))  # unreadable score == unscored, never guessed
        elif isinstance(entry, int | float):
            eligible.append((cid, float(entry), None))
        else:
            eligible.append((cid, None, None))
    n_pending = sum(1 for _, m, _ in eligible if m is None)
    audit = rejection_shadow_audit(
        eligible, deploy_threshold=deploy_threshold,
        leak_tolerance=leak_tolerance, min_sample=min_sample,
    )
    if n_eligible and n_pending == n_eligible:
        verdict = (
            f"{n_eligible} eligible rejects, NONE re-scored yet -- the forward evaluator has not "
            "produced scores; the audit cannot judge the gate until it does"
        )
    else:
        verdict = audit.verdict
        if n_pending:
            verdict += f" ({n_pending} eligible rejects still awaiting a forward score)"
    return ShadowRunReport(
        as_of=now.isoformat(),
        n_rejects_total=len(rejects),
        n_eligible=n_eligible,
        n_pending_rescore=n_pending,
        audit=audit,
        verdict=verdict,
    )
