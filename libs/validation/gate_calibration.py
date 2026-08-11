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

import math
from collections.abc import Mapping, Sequence
from statistics import NormalDist

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
    #: decided entries dropped because their forward metric was BIT-IDENTICAL to another's --
    #: the same position series scored under two ids is one bet, not two (R0439 evidence:
    #: two DOGE rejects shared forward Sharpe 1.2429320833719768 to the last digit).
    n_duplicates_collapsed: int = 0
    #: True when at least one entry carried its forward sample size and was judged against the
    #: noise-adjusted bar rather than the raw deploy threshold.
    noise_adjusted: bool = False

    def __bool__(self) -> bool:
        return not self.over_strict


def _pay_bar(
    deploy_threshold: float, n_obs: int | None, leak_tolerance: float, periods_per_year: float
) -> float:
    """The forward metric a reject must clear to count as PAID, at its actual sample size.

    An annualized Sharpe over n periods has standard error ~ sqrt(periods_per_year / n) under
    the zero-edge null, so at short windows the raw deploy threshold is deep inside the noise:
    measured on the live artifact (2026-08-11), a bar of 0.5 at n=31 daily bars sat 0.15 SE
    above zero and PURE NOISE cleared it ~44% of the time -- the audit was structurally
    guaranteed to cry over-strict at any realistic window. Raising the per-entry bar to the
    (1 - leak_tolerance) quantile of that null holds the false-pay rate at exactly the
    tolerance the verdict tests against, which is what makes the comparison valid at every n:
    the bar decays toward the raw threshold as the window grows (reaching it near
    n = periods_per_year * (z / threshold)^2) instead of branding noise a leaked survivor at
    short ones. This TIGHTENS the pay criterion and moves no gauntlet bar."""
    if n_obs is None or n_obs <= 1:
        return deploy_threshold
    z = NormalDist().inv_cdf(1.0 - leak_tolerance)
    return max(deploy_threshold, z * math.sqrt(periods_per_year / float(n_obs)))


def rejection_shadow_audit(
    rejects: Sequence[tuple[str, float | None] | tuple[str, float | None, int | None]],
    *,
    deploy_threshold: float,
    leak_tolerance: float = 0.10,
    min_sample: int = 5,
    periods_per_year: float = 365.0,
) -> RejectionShadowReport:
    """Shadow-track rejected candidates forward (MAX_SURVIVORS Part 1.2, rejection audit).

    ``rejects`` items are ``(candidate_id, forward_metric)`` or ``(candidate_id,
    forward_metric, n_forward_obs)``, where ``forward_metric`` is the realized out-of-sample
    metric measured on data that arrived AFTER the rejection (annualized Sharpe on the honest
    holdout), or ``None`` if not enough forward data has accrued to judge yet.

    A reject counts as PAID when its forward metric clears the pay bar. With a sample size
    supplied, the bar is noise-adjusted (see ``_pay_bar``); the bare two-tuple form keeps the
    raw threshold and is for callers whose metric is already judgment-ready. Bit-identical
    forward metrics are collapsed to one entry -- the same forward series under two ids is one
    bet. If more than ``leak_tolerance`` of a sufficient sample (``>= min_sample`` decided,
    deduped rejects) would pay, the gate is over-strict and must be re-calibrated -- pure
    recovery, no new data.
    """
    norm: list[tuple[str, float, int | None]] = []
    for item in rejects:
        rid, m = item[0], item[1]
        if m is None:
            continue
        n_obs = item[2] if len(item) > 2 else None
        norm.append((rid, float(m), n_obs))
    seen: set[float] = set()
    decided: list[tuple[str, float, int | None]] = []
    n_dupes = 0
    for rid, m, n_obs in norm:
        if m in seen:
            n_dupes += 1
            continue
        seen.add(m)
        decided.append((rid, m, n_obs))
    noise_adjusted = any(n_obs is not None for _, _, n_obs in decided)
    paid = tuple(
        rid for rid, m, n_obs in decided
        if m >= _pay_bar(deploy_threshold, n_obs, leak_tolerance, periods_per_year)
    )
    n = len(decided)
    frac = round(len(paid) / n, 3) if n else 0.0
    over_strict = n >= min_sample and frac > leak_tolerance
    dup_note = f"; {n_dupes} duplicate forward series collapsed" if n_dupes else ""
    if n < min_sample:
        verdict = (
            f"only {n} decided rejects (<{min_sample}) -- insufficient forward sample to judge the "
            f"gate; keep shadowing{dup_note}"
        )
    elif over_strict:
        verdict = (
            f"OVER-STRICT: {len(paid)}/{n} rejects ({frac:.0%}) would have paid out-of-sample -- "
            f"the gate is leaking survivors; re-calibrate (effective-trial count, per-gate bar)"
            f"{dup_note}"
        )
    else:
        verdict = (
            f"calibrated: {len(paid)}/{n} rejects ({frac:.0%}) would have paid, within the "
            f"{leak_tolerance:.0%} tolerance -- gate is not obviously leaking{dup_note}"
        )
    if noise_adjusted:
        known_n = [n_obs for _, _, n_obs in decided if n_obs]
        if known_n:
            worst = _pay_bar(deploy_threshold, min(known_n), leak_tolerance, periods_per_year)
            verdict += (
                f" [pay bar noise-adjusted per entry; at the shortest window "
                f"(n={min(known_n)}) it is {worst:.2f}]"
            )
    return RejectionShadowReport(
        n_rejects=n, n_would_have_paid=len(paid), would_have_paid=paid,
        leak_frac=frac, over_strict=over_strict, verdict=verdict,
        n_duplicates_collapsed=n_dupes, noise_adjusted=noise_adjusted,
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
