"""Integrated validation diagnostics for the research completion programme.

These diagnostics answer four different questions without changing a validation threshold:

* sensitivity -- would a small, *pre-declared* perturbation flip many verdicts?
* ablation -- which gates provide unique protection and which merely duplicate another gate?
* failure structure -- are nominal failures independent, or repetitions of one mechanism?
* conditional validation -- can a regime-dependent claim be tested without post-hoc rescue?

The module has no promotion authority.  Its outputs are measurements consumed by the research
review and max-push queue.  A high false-negative estimate is a reason to preregister a competing
gate design on untouched evidence, never to lower the existing bar.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from statistics import NormalDist
from typing import cast

import numpy as np

from libs.core.coerce import finite_float, integer

__all__ = [
    "ConditionalClaim",
    "ablate_gates",
    "cluster_failures",
    "conditional_validation",
    "semantic_label_integrity",
    "sequential_experiment_design",
    "threshold_sensitivity",
]


def _finite(values: Iterable[float]) -> np.ndarray:
    arr = np.asarray(tuple(values), dtype="float64")
    return cast("np.ndarray", arr[np.isfinite(arr)])


def threshold_sensitivity(
    statistics: Sequence[float],
    threshold: float,
    *,
    perturbations: Sequence[float] = (-0.10, -0.05, 0.0, 0.05, 0.10),
) -> dict[str, object]:
    """Measure verdict stability over justified relative perturbations.

    The function deliberately returns no recommended threshold.  It reports the surface and the
    maximum flip share, which is the quantity needed to distinguish a robust bar from a knife edge.
    Empty or non-finite input is UNMEASURED rather than a zero-sensitivity success.
    """
    x = _finite(statistics)
    if x.size == 0 or not math.isfinite(threshold):
        return {
            "status": "UNMEASURED",
            "n": int(x.size),
            "surface": [],
            "reason": "no finite statistics or threshold",
        }
    base = x >= threshold
    rows: list[dict[str, float | int]] = []
    max_flip = 0.0
    for p in perturbations:
        tested = threshold * (1.0 + float(p))
        verdict = x >= tested
        flips = int(np.count_nonzero(verdict != base))
        share = flips / x.size
        max_flip = max(max_flip, share)
        rows.append(
            {
                "perturbation": float(p),
                "threshold": float(tested),
                "passed": int(verdict.sum()),
                "flips": flips,
                "flip_share": float(share),
            }
        )
    return {
        "status": "MEASURED",
        "n": int(x.size),
        "baseline_threshold": float(threshold),
        "baseline_passed": int(base.sum()),
        "max_flip_share": float(max_flip),
        "knife_edge": bool(max_flip >= 0.10),
        "surface": rows,
        "authority": "MEASUREMENT_ONLY -- never selects or loosens a threshold",
    }


def ablate_gates(
    gate_results: Mapping[str, Sequence[bool]],
    *,
    planted_positive: Sequence[bool] | None = None,
) -> dict[str, object]:
    """Unique-kill, overlap and planted-edge destruction for every gate.

    ``True`` means a candidate passed that gate.  All gate vectors must cover the same candidates.
    A gate with zero unique kills is *redundant on this sample*, not globally redundant; the output
    therefore never recommends deletion.  Planted positives make false-negative exposure visible.
    """
    if not gate_results:
        return {"status": "UNMEASURED", "gates": {}, "reason": "no gate rows"}
    names = tuple(sorted(gate_results))
    arrays = {k: np.asarray(gate_results[k], dtype=bool) for k in names}
    lengths = {len(v) for v in arrays.values()}
    if len(lengths) != 1 or not lengths or next(iter(lengths)) == 0:
        raise ValueError("all gate vectors must have the same non-zero length")
    n = next(iter(lengths))
    planted = (
        np.asarray(planted_positive, dtype=bool)
        if planted_positive is not None
        else np.zeros(n, dtype=bool)
    )
    if planted.shape != (n,):
        raise ValueError("planted_positive must align with gate rows")

    rows: dict[str, dict[str, object]] = {}
    overlap: dict[str, int] = {}
    for name in names:
        failed = ~arrays[name]
        other_failed = np.zeros(n, dtype=bool)
        for other in names:
            if other != name:
                other_failed |= ~arrays[other]
        unique = failed & ~other_failed
        rows[name] = {
            "evaluated": n,
            "kills": int(failed.sum()),
            "unique_kills": int(unique.sum()),
            "planted_edges_killed": int(np.count_nonzero(failed & planted)),
            "planted_edges_seen": int(planted.sum()),
            "sample_redundant": bool(failed.any() and not unique.any()),
        }
    for i, left in enumerate(names):
        for right in names[i + 1 :]:
            overlap[f"{left}|{right}"] = int(np.count_nonzero(~arrays[left] & ~arrays[right]))
    all_pass = np.logical_and.reduce(tuple(arrays.values()))
    return {
        "status": "MEASURED",
        "candidates": n,
        "survivors": int(all_pass.sum()),
        "gates": rows,
        "kill_overlap": overlap,
        "authority": "DIAGNOSTIC_ONLY -- ablation never deletes or lowers a gate",
    }


def cluster_failures(records: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Collapse nominal failures into deterministic mechanism archetypes.

    The cluster key uses economic family, kill reason, regime and horizon.  Formula names and
    parameter values are intentionally excluded: threshold variants of one idea are inventory,
    not independent discoveries or failures.
    """
    if not records:
        return {"status": "UNMEASURED", "nominal": 0, "clusters": []}
    grouped: dict[tuple[str, str, str, str], list[str]] = defaultdict(list)
    for i, rec in enumerate(records):
        family = str(rec.get("family") or rec.get("feature_family") or "UNKNOWN_FAMILY")
        kill = str(rec.get("kill") or rec.get("kill_criterion") or "UNKNOWN_KILL")
        regime = str(rec.get("regime") or "ALL")
        horizon = str(rec.get("horizon") or "UNKNOWN_HORIZON")
        grouped[(family, kill, regime, horizon)].append(str(rec.get("key") or f"row-{i}"))
    clusters = [
        {
            "cluster_id": "::".join(key),
            "family": key[0],
            "kill": key[1],
            "regime": key[2],
            "horizon": key[3],
            "members": members,
            "n": len(members),
        }
        for key, members in grouped.items()
    ]
    clusters.sort(key=lambda row: (-integer(row.get("n")), str(row.get("cluster_id"))))
    counts = Counter(str(r.get("kill")) for r in clusters for _ in range(integer(r.get("n"))))
    return {
        "status": "MEASURED",
        "nominal": len(records),
        "independent_archetypes": len(clusters),
        "kill_tally": dict(counts),
        "clusters": clusters,
        "note": "multiplicity follows the selection path; clustering never erases trials",
    }


@dataclass(frozen=True)
class ConditionalClaim:
    """Preconditions that make a conditional branch an honest new hypothesis."""

    claim_id: str
    state_name: str
    state_declared_before_results: bool
    state_observable_at_decision: bool
    untouched_oos: bool
    ancestry_trials: int
    returns: tuple[float, ...]
    state_mask: tuple[bool, ...]


def conditional_validation(claim: ConditionalClaim, *, min_state_n: int = 30) -> dict[str, object]:
    """Evaluate a preregistered state branch without rescuing a failed global result post hoc."""
    if not claim.state_declared_before_results:
        return {"status": "REFUSED", "reason": "state was defined after observing results"}
    if not claim.state_observable_at_decision:
        return {"status": "REFUSED", "reason": "state is not causally observable at decision time"}
    if not claim.untouched_oos:
        return {"status": "REFUSED", "reason": "no untouched out-of-sample evidence"}
    r = _finite(claim.returns)
    mask = np.asarray(claim.state_mask, dtype=bool)
    if r.size != mask.size:
        raise ValueError("returns and state_mask must align and returns must be finite")
    active = r[mask]
    inactive = r[~mask]
    if active.size < min_state_n or inactive.size < min_state_n:
        return {
            "status": "UNMEASURED",
            "active_n": int(active.size),
            "inactive_n": int(inactive.size),
            "min_state_n": min_state_n,
            "reason": "both state and transition/control samples must be powered",
        }

    def stats(x: np.ndarray) -> dict[str, float | int]:
        sd = float(np.std(x, ddof=1))
        mean = float(np.mean(x))
        t = mean / (sd / math.sqrt(x.size)) if sd > 0 else 0.0
        return {"n": int(x.size), "mean": mean, "t": t}

    a, b = stats(active), stats(inactive)
    # Bonferroni is deliberately conservative here: the branch is a new preregistered family and
    # inherits every ancestry trial.  This measurement does not promote it.
    inherited_hurdle = math.sqrt(2.0 * math.log(max(2, claim.ancestry_trials + 1)))
    return {
        "status": "MEASURED",
        "claim_id": claim.claim_id,
        "state": claim.state_name,
        "active": a,
        "inactive_control": b,
        "inherited_trials": max(1, claim.ancestry_trials),
        "diagnostic_hurdle": inherited_hurdle,
        "screen_pass": bool(float(a["t"]) >= inherited_hurdle and float(a["mean"]) > 0),
        "authority": "SCREEN_ONLY -- requires the ordinary forward/Holm promotion path",
    }


def sequential_experiment_design(
    *,
    minimum_effect: float,
    noise_sd: float,
    available_n: int,
    alpha: float = 0.05,
    power: float = 0.8,
    planned_looks: int = 1,
    observed_effect: float | None = None,
    standard_error: float | None = None,
    additional_information_value: float | None = None,
    additional_cost: float | None = None,
) -> dict[str, object]:
    """Power-aware sequential decision that controls repeated looks and false negatives.

    Bonferroni spending is conservative but explicit.  A non-significant underpowered experiment
    is labelled absence of evidence, never evidence of absence, and this diagnostic has no power to
    promote or weaken an existing validator.
    """
    if (
        minimum_effect <= 0
        or noise_sd <= 0
        or available_n < 0
        or not 0 < alpha < 1
        or not 0 < power < 1
        or planned_looks < 1
    ):
        return {"status": "UNMEASURED", "reason": "invalid design inputs"}
    per_look_alpha = alpha / planned_looks
    z_alpha = NormalDist().inv_cdf(1 - per_look_alpha / 2)
    z_power = NormalDist().inv_cdf(power)
    required_n = math.ceil(((z_alpha + z_power) * noise_sd / minimum_effect) ** 2)
    detectable = (z_alpha + z_power) * noise_sd / math.sqrt(max(available_n, 1))
    powered = available_n >= required_n
    decision = "PREREGISTER_AND_COLLECT"
    evidence_class = "INSUFFICIENT_SAMPLE" if not powered else "TEST_READY"
    interval = None
    if observed_effect is not None and standard_error is not None and standard_error > 0:
        lo = observed_effect - z_alpha * standard_error
        hi = observed_effect + z_alpha * standard_error
        interval = [lo, hi]
        if lo > 0:
            decision, evidence_class = "STOP_SUCCESS_SCREEN", "EVIDENCE_OF_EFFECT"
        elif powered and hi < minimum_effect:
            decision, evidence_class = "STOP_FUTILITY", "EVIDENCE_OF_ECONOMIC_ABSENCE"
        else:
            worth_more = (
                additional_information_value is not None
                and additional_cost is not None
                and additional_information_value > additional_cost
            )
            decision = "CONTINUE" if worth_more or not powered else "REVIEW_INCONCLUSIVE"
            evidence_class = "ABSENCE_OF_EVIDENCE"
    return {
        "status": "MEASURED",
        "minimum_economically_meaningful_effect": minimum_effect,
        "available_n": available_n,
        "required_n": required_n,
        "powered": powered,
        "minimum_detectable_effect": detectable,
        "planned_looks": planned_looks,
        "per_look_alpha": per_look_alpha,
        "confidence_interval": interval,
        "decision": decision,
        "evidence_class": evidence_class,
        "authority": "DIAGNOSTIC_ONLY -- ordinary multiplicity and forward validation remain",
    }


def semantic_label_integrity(
    records: Sequence[Mapping[str, object]],
    *,
    inferred_field: str,
    authoritative_field: str,
    authoritative_source: str,
    outcome_field: str | None = None,
    min_ground_truth: int = 30,
    min_preregistered_kappa: float | None = None,
) -> dict[str, object]:
    """Audit inferred market labels against independently authoritative semantic truth.

    An agreement estimate may reduce confidence, but never creates alpha or rescues a strategy.
    Any validation threshold must be supplied before this comparison is inspected.
    """
    if min_ground_truth < 2:
        raise ValueError("min_ground_truth must be at least 2")
    if min_preregistered_kappa is not None and not -1 <= min_preregistered_kappa <= 1:
        raise ValueError("min_preregistered_kappa must lie in [-1, 1]")
    if not authoritative_source.strip():
        return {
            "status": "GROUND_TRUTH_SOURCE_REQUIRED",
            "confidence_multiplier": None,
            "authority": "DIAGNOSTIC_ONLY",
        }
    paired = [
        row
        for row in records
        if row.get(inferred_field) is not None and row.get(authoritative_field) is not None
    ]
    if not paired:
        return {
            "status": "UNMEASURED",
            "compared": 0,
            "total": len(records),
            "authoritative_source": authoritative_source,
            "confidence_multiplier": None,
        }
    inferred = [str(row[inferred_field]) for row in paired]
    truth = [str(row[authoritative_field]) for row in paired]
    labels = sorted(set(inferred) | set(truth))
    confusion = {
        actual: {
            predicted: sum(
                a == actual and p == predicted for p, a in zip(inferred, truth, strict=True)
            )
            for predicted in labels
        }
        for actual in labels
    }
    size = len(paired)
    agreement = sum(p == a for p, a in zip(inferred, truth, strict=True)) / size
    inferred_share = {label: inferred.count(label) / size for label in labels}
    truth_share = {label: truth.count(label) / size for label in labels}
    expected = sum(inferred_share[label] * truth_share[label] for label in labels)
    kappa = (agreement - expected) / (1 - expected) if expected < 1 else 1.0
    effects = []
    sign_flips = []
    if outcome_field:
        for label in labels:
            inferred_outcomes = [
                finite_float(row.get(outcome_field))
                for row in paired
                if str(row[inferred_field]) == label
                and isinstance(row.get(outcome_field), (int, float))
            ]
            truth_outcomes = [
                finite_float(row.get(outcome_field))
                for row in paired
                if str(row[authoritative_field]) == label
                and isinstance(row.get(outcome_field), (int, float))
            ]
            inferred_mean = (
                sum(inferred_outcomes) / len(inferred_outcomes) if inferred_outcomes else None
            )
            truth_mean = sum(truth_outcomes) / len(truth_outcomes) if truth_outcomes else None
            flipped = bool(
                inferred_mean is not None
                and truth_mean is not None
                and inferred_mean * truth_mean < 0
            )
            if flipped:
                sign_flips.append(label)
            effects.append(
                {
                    "label": label,
                    "inferred_mean_outcome": inferred_mean,
                    "truth_mean_outcome": truth_mean,
                    "sign_flipped": flipped,
                }
            )
    powered = size >= min_ground_truth
    if not powered:
        status = "UNDERPOWERED"
    elif min_preregistered_kappa is None:
        status = "MEASURED_NOT_VALIDATED"
    elif kappa >= min_preregistered_kappa:
        status = "SEMANTICS_VALIDATED"
    else:
        status = "SEMANTICS_FAILED"
    return {
        "status": status,
        "total": len(records),
        "compared": size,
        "coverage": size / len(records) if records else None,
        "labels": labels,
        "confusion": confusion,
        "agreement": agreement,
        "expected_agreement": expected,
        "cohen_kappa": kappa,
        "min_ground_truth": min_ground_truth,
        "min_preregistered_kappa": min_preregistered_kappa,
        "authoritative_source": authoritative_source,
        "confidence_multiplier": max(0.0, min(1.0, kappa)) if powered else None,
        "outcome_effects": effects,
        "outcome_sign_flips": sign_flips,
        "authority": "SEMANTIC VALIDATION ONLY -- cannot promote alpha or change labels in place",
    }
