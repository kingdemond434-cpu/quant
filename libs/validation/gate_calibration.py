"""Gate-calibration audits -- recover wrongly-rejected survivors and make backfill safe.

Two audits from MAX_SURVIVORS Part 1, both pure gain (no new data, no trading exposure):

  - REJECTION-SHADOW AUDIT. The gauntlet rejects most candidates; that is correct on picked-clean
    price space. But a gate that has drifted OVER-strict silently leaks real edges. Shadow-track a
    sample of rejects forward and, using data that arrived AFTER the rejection (never the in-sample
    metric that got them rejected -- that would be the same garden-of-forking-paths), ask whether a
    non-trivial slice would have been profitable. If so the gate is leaking survivors and must be
    re-calibrated. ``rejection_shadow_audit``.

  - RECONSTRUCTION VERIFIER. Reconstructing an idle axis's history from archives collapses the
    forward clock (a candidate that survives on 200 reconstructed days validates today, not in
    weeks) -- but ONLY if the reconstruction is real. Its one failure mode is leakage: a
    reconstruction that silently disagrees with ground truth fabricates out-of-sample evidence.
    This gate diff-verifies the reconstruction against overlapping ground truth and REFUSES to admit
    any series that disagrees. It only ever rejects bad data, so it has no downside -- it is the
    safety interlock that makes backfill a survivor multiplier instead of a leakage source.
    ``reconstruction_verified``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict


class RejectionShadowReport(BaseModel):
    """Forward audit of rejected candidates: is the gate leaking survivors?"""

    model_config = ConfigDict(frozen=True)

    n_rejects: int  # rejects with a decided forward metric (enough post-rejection data to judge)
    n_would_have_paid: int  # of those, how many cleared the deploy bar out-of-sample
    would_have_paid: tuple[str, ...]  # their ids -- the leaked survivors to re-examine
    leak_frac: float  # n_would_have_paid / n_rejects
    over_strict: bool  # leak_frac past tolerance on a sufficient sample -> re-calibrate the gate
    verdict: str

    def __bool__(self) -> bool:
        return not self.over_strict


def rejection_shadow_audit(
    rejects: Sequence[tuple[str, float | None]],
    *,
    deploy_threshold: float,
    leak_tolerance: float = 0.10,
    min_sample: int = 5,
) -> RejectionShadowReport:
    """Shadow-track rejected candidates forward (MAX_SURVIVORS Part 1.2, rejection audit).

    ``rejects`` is a sequence of ``(candidate_id, forward_metric)`` where ``forward_metric`` is the
    realized out-of-sample metric measured on data that arrived AFTER the rejection (Sharpe / IC on
    the honest holdout), or ``None`` if not enough forward data has accrued to judge yet. A reject
    that clears ``deploy_threshold`` on that forward data is a survivor the gate leaked. If more
    than ``leak_tolerance`` of a sufficient sample (``>= min_sample`` decided rejects) would pay,
    the gate is over-strict and must be re-calibrated -- pure recovery, no new data.
    """
    decided = [(rid, m) for rid, m in rejects if m is not None]
    paid = tuple(rid for rid, m in decided if m >= deploy_threshold)
    n = len(decided)
    frac = round(len(paid) / n, 3) if n else 0.0
    over_strict = n >= min_sample and frac > leak_tolerance
    if n < min_sample:
        verdict = (
            f"only {n} decided rejects (<{min_sample}) -- insufficient forward sample to judge the "
            "gate; keep shadowing"
        )
    elif over_strict:
        verdict = (
            f"OVER-STRICT: {len(paid)}/{n} rejects ({frac:.0%}) would have paid out-of-sample -- "
            "the gate is leaking survivors; re-calibrate (effective-trial count, per-gate bar)"
        )
    else:
        verdict = (
            f"calibrated: {len(paid)}/{n} rejects ({frac:.0%}) would have paid, within the "
            f"{leak_tolerance:.0%} tolerance -- gate is not obviously leaking"
        )
    return RejectionShadowReport(
        n_rejects=n, n_would_have_paid=len(paid), would_have_paid=paid,
        leak_frac=frac, over_strict=over_strict, verdict=verdict,
    )


class ReconstructionCheck(BaseModel):
    """Diff-verify of a reconstructed history against overlapping ground truth."""

    model_config = ConfigDict(frozen=True)

    n_overlap: int  # points where reconstruction and ground truth share a key (timestamp)
    max_abs_err: float  # worst absolute disagreement on the overlap
    max_rel_err: float  # worst relative disagreement (scaled by |ground truth|)
    verified: bool  # overlap sufficient AND every point within tolerance -> admissible as OOS
    verdict: str

    def __bool__(self) -> bool:
        return self.verified


def reconstruction_verified(
    *,
    reconstructed: Mapping[str, float],
    ground_truth: Mapping[str, float],
    rel_tol: float = 0.01,
    abs_tol: float = 1e-9,
    min_overlap: int = 30,
) -> ReconstructionCheck:
    """Backfill safety GATE (MAX_SURVIVORS Part 1.1) -- verify-don't-trust for reconstructions.

    Reconstructed history may be run through the gauntlet as out-of-sample ONLY after it diff-
    verifies against overlapping ground truth. ``reconstructed`` and ``ground_truth`` are maps keyed
    by timestamp (or any stable key); the overlap is the shared keys. Admission requires (a) a
    non-trivial overlap (``>= min_overlap`` shared points -- a reconstruction that overlaps ground
    truth on 3 points has proved nothing) AND (b) every overlapping point agreeing within tolerance
    (``|recon - truth| <= abs_tol + rel_tol * |truth|``). Any disagreement REJECTS the series: an
    unverified reconstruction fabricates out-of-sample evidence, so refusing it is the whole point.
    """
    shared = sorted(set(reconstructed) & set(ground_truth))
    n = len(shared)
    max_abs = 0.0
    max_rel = 0.0
    ok_all = True
    for k in shared:
        r = float(reconstructed[k])
        g = float(ground_truth[k])
        abs_err = abs(r - g)
        rel_err = abs_err / abs(g) if g != 0.0 else (0.0 if abs_err == 0.0 else float("inf"))
        max_abs = max(max_abs, abs_err)
        max_rel = max(max_rel, rel_err)
        if abs_err > abs_tol + rel_tol * abs(g):
            ok_all = False
    verified = n >= min_overlap and ok_all
    if n < min_overlap:
        verdict = (
            f"overlap {n} < {min_overlap} required -- too little ground truth to trust the "
            "reconstruction; do NOT admit as out-of-sample"
        )
    elif not ok_all:
        verdict = (
            f"REJECTED: reconstruction disagrees with ground truth (max rel err {max_rel:.4f} > "
            f"{rel_tol:.4f}) over {n} points -- would fabricate OOS evidence; fix or discard"
        )
    else:
        verdict = (
            f"verified: reconstruction matches ground truth within {rel_tol:.2%} over {n} "
            "points -- admissible as out-of-sample; run the gauntlet on it now"
        )
    return ReconstructionCheck(
        n_overlap=n, max_abs_err=round(max_abs, 6), max_rel_err=round(max_rel, 6),
        verified=verified, verdict=verdict,
    )
