"""Fail-closed production contracts around the existing execution journal and tape.

These are pure decision records and verifiers.  They do not submit orders, mutate a manifest, or
recover capital-critical services.  The live adapter remains behind the existing risk kernel.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence

from libs.core.coerce import finite_float, integer

_DECISIONS = frozenset(
    {
        "EXECUTED",
        "SIGNAL_REJECTED",
        "RISK_REJECTED",
        "COST_REJECTED",
        "CAPACITY_REJECTED",
        "EXECUTION_REJECTED",
        "VENUE_UNAVAILABLE",
        "MISSED_LATENCY",
    }
)

__all__ = [
    "accounting_from_execution_tape",
    "autonomous_recovery_plan",
    "counterfactual_reality_gap",
    "decision_record",
    "deterministic_hot_path",
    "latency_metrics",
    "preflight_contract",
    "reality_gap",
    "strategy_manifest",
    "venue_eligibility",
]


def _canonical(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _hash(obj: object) -> str:
    return hashlib.sha256(_canonical(obj).encode()).hexdigest()


def decision_record(
    *,
    decision_id: str,
    decision: str,
    strategy_version: str,
    state_snapshot: Mapping[str, object],
    rationale: str,
    desired_order: Mapping[str, object] | None = None,
) -> dict[str, object]:
    if decision not in _DECISIONS:
        raise ValueError(f"decision must be one of {sorted(_DECISIONS)}")
    if not state_snapshot:
        raise ValueError("a non-trade without its contemporaneous state is not evidence")
    row = {
        "decision_id": decision_id,
        "decision": decision,
        "strategy_version": strategy_version,
        "state_snapshot": dict(state_snapshot),
        "rationale": rationale,
        "desired_order": dict(desired_order or {}),
    }
    return {**row, "record_hash": _hash(row)}


def strategy_manifest(
    specification: Mapping[str, object], *, parent_hash: str | None = None, version: str
) -> dict[str, object]:
    """Canonical immutable manifest; modifications create a child by carrying ``parent_hash``."""
    required = ("strategy_id", "signal", "allocator", "risk_policy", "execution_policy")
    missing = [key for key in required if key not in specification]
    if missing:
        raise ValueError(f"manifest missing {missing}")
    body = {"version": version, "parent_hash": parent_hash, "specification": dict(specification)}
    return {**body, "manifest_hash": _hash(body), "immutable": True}


def reality_gap(
    paper: Sequence[Mapping[str, object]],
    canary: Sequence[Mapping[str, object]],
    live: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Compare the same decision IDs across paper/canary/live at every causal stage."""
    modes = {"paper": paper, "canary": canary, "live": live}
    indexed = {mode: {str(r.get("decision_id")): r for r in rows} for mode, rows in modes.items()}
    ids = sorted(set().union(*(set(x) for x in indexed.values())))
    fields = ("signal", "decision", "desired_order", "fill", "cost_bps")
    mismatches = []
    for decision_id in ids:
        for field in fields:
            values = {mode: indexed[mode].get(decision_id, {}).get(field) for mode in modes}
            if len({_canonical(v) for v in values.values()}) > 1:
                mismatches.append({"decision_id": decision_id, "field": field, "values": values})
    denom = max(len(ids) * len(fields), 1)
    return {
        "decisions": len(ids),
        "comparisons": denom,
        "mismatches": mismatches,
        "parity": 1.0 - len(mismatches) / denom,
        "same_engine_required": True,
    }


def preflight_contract(checks: Mapping[str, bool | None]) -> dict[str, object]:
    required = (
        "data_fresh",
        "clock_synchronised",
        "manifest_hash_valid",
        "venue_eligible",
        "auth_valid",
        "reconciled",
        "risk_kernel_valid",
        "journal_writable",
    )
    missing = [name for name in required if name not in checks]
    failed = [name for name in required if checks.get(name) is not True]
    return {
        "status": "ELIGIBLE" if not failed and not missing else "INELIGIBLE",
        "missing": missing,
        "failed_or_unmeasured": failed,
        "checks": {name: checks.get(name) for name in required},
        "fail_closed": True,
    }


def venue_eligibility(
    capabilities: Mapping[str, object], requirements: Mapping[str, object]
) -> dict[str, object]:
    hard_missing: list[dict[str, object]] = []
    degraded: list[dict[str, object]] = []
    for name, requirement in requirements.items():
        hard = True
        expected = requirement
        if isinstance(requirement, Mapping):
            expected, hard = requirement.get("value"), bool(requirement.get("hard", True))
        actual = capabilities.get(name)
        ok = (
            actual == expected
            if not isinstance(expected, (list, tuple, set))
            else actual in expected
        )
        if not ok:
            (hard_missing if hard else degraded).append(
                {"capability": name, "required": expected, "actual": actual}
            )
    status = "INELIGIBLE" if hard_missing else "DEGRADED" if degraded else "ELIGIBLE"
    return {"status": status, "hard_missing": hard_missing, "degraded": degraded}


def accounting_from_execution_tape(records: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Derive positions and cash from immutable execution records; never accept a second ledger."""
    cash = 0.0
    positions: defaultdict[str, float] = defaultdict(float)
    fees = 0.0
    seen: Counter[str] = Counter()
    for row in records:
        event_id = str(row.get("event_id") or row.get("trade_id") or _hash(row))
        occurrence = integer(row.get("occurrence", 1), 1)
        identity = f"{event_id}:{occurrence}"
        if seen[identity]:
            continue
        seen[identity] += 1
        qty = finite_float(row.get("qty"))
        price = finite_float(row.get("price"))
        fee = finite_float(row.get("fee"))
        side = str(row.get("side", "")).upper()
        signed = qty if side == "BUY" else -qty if side == "SELL" else 0.0
        symbol = str(row.get("symbol", "UNKNOWN"))
        positions[symbol] += signed
        cash -= signed * price + fee
        fees += fee
    return {
        "source": "AUTHORITATIVE_EXECUTION_TAPE",
        "records": sum(seen.values()),
        "cash_delta": cash,
        "positions": dict(positions),
        "fees": fees,
        "evidence_authority": True,
    }


def deterministic_hot_path(
    manifest: Mapping[str, object],
    observation: Mapping[str, object],
    signal_engine: Callable[[Mapping[str, object], Mapping[str, object]], object],
    allocator: Callable[[object, Mapping[str, object]], object],
    risk_kernel: Callable[[object, Mapping[str, object]], object],
    adapter: Callable[[object, Mapping[str, object]], object],
) -> dict[str, object]:
    """Frozen manifest -> signal -> allocation -> immutable risk -> adapter, with stage hashes."""
    if not manifest.get("immutable") or not manifest.get("manifest_hash"):
        raise ValueError("hot path requires a frozen, hashed manifest")
    signal = signal_engine(observation, manifest)
    desired = allocator(signal, manifest)
    approved = risk_kernel(desired, manifest)
    order = adapter(approved, manifest)
    stages = {
        "observation": _hash(observation),
        "signal": _hash(signal),
        "desired_order": _hash(desired),
        "risk_output": _hash(approved),
        "adapter_order": _hash(order),
    }
    return {
        "order": order,
        "stage_hashes": stages,
        "path_hash": _hash({"manifest": manifest["manifest_hash"], **stages}),
    }


def latency_metrics(
    timestamps: Mapping[str, float],
    *,
    half_life_seconds: float,
    edge_bps: float,
    venue_available: bool = True,
) -> dict[str, object]:
    pairs = (
        ("signal", "observation"),
        ("observation", "decision"),
        ("decision", "order"),
        ("order", "fill"),
    )
    legs = {
        f"{a}_to_{b}": max(0.0, float(timestamps[b]) - float(timestamps[a]))
        for a, b in pairs
        if a in timestamps and b in timestamps
    }
    if "signal" not in timestamps or "fill" not in timestamps or half_life_seconds <= 0:
        return {"status": "UNMEASURED", "legs": legs}
    total = max(0.0, float(timestamps["fill"]) - float(timestamps["signal"]))
    regret = edge_bps * (1 - 0.5 ** (total / half_life_seconds))
    return {
        "status": "MEASURED",
        "legs": legs,
        "end_to_end_seconds": total,
        "cadence_regret_bps": regret,
        "venue_availability_loss_bps": 0.0 if venue_available else edge_bps,
    }


def autonomous_recovery_plan(
    *,
    component: str,
    failure_class: str,
    capital_critical: bool,
    legal_fallback: str | None,
    attempts: int,
) -> dict[str, object]:
    """Recovery permission boundary. Capital-critical failures always require safe stop."""
    if capital_critical:
        return {
            "action": "SAFE_STOP_AND_ESCALATE",
            "component": component,
            "reason": "autonomous recovery forbidden on capital-critical path",
        }
    if not legal_fallback:
        return {
            "action": "ESCALATE",
            "component": component,
            "reason": "no predeclared legal fallback",
        }
    if attempts >= 3:
        return {
            "action": "ESCALATE",
            "component": component,
            "reason": "bounded recovery attempts exhausted",
        }
    return {
        "action": "APPLY_FALLBACK_VERIFY_RECORD",
        "component": component,
        "failure_class": failure_class,
        "fallback": legal_fallback,
        "attempt": attempts + 1,
        "validation_weakened": False,
    }


def counterfactual_reality_gap(
    real: Sequence[Mapping[str, object]],
    synthetic: Sequence[Mapping[str, object]],
    *,
    features: Sequence[str],
    max_preregistered_gap: float | None = None,
) -> dict[str, object]:
    """Calibrate synthetic market worlds against real observations.

    The caller must declare any acceptable gap before inspecting the comparison.  Synthetic
    evidence never receives promotion authority, even when calibration passes.
    """
    if max_preregistered_gap is not None and max_preregistered_gap < 0:
        raise ValueError("max_preregistered_gap must be non-negative")
    names = tuple(dict.fromkeys(str(name) for name in features if str(name)))
    if not names or not real or not synthetic:
        return {
            "status": "UNMEASURED",
            "reason": "real observations, synthetic observations and features are required",
            "synthetic_alpha_authority": False,
        }

    def values(rows: Sequence[Mapping[str, object]], name: str) -> list[float]:
        measured: list[float] = []
        for row in rows:
            raw = row.get(name)
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                continue
            value = float(raw)
            if math.isfinite(value):
                measured.append(value)
        return measured

    def quantile(sample: Sequence[float], probability: float) -> float:
        ordered = sorted(sample)
        position = probability * (len(ordered) - 1)
        low = math.floor(position)
        high = math.ceil(position)
        if low == high:
            return ordered[low]
        fraction = position - low
        return ordered[low] * (1 - fraction) + ordered[high] * fraction

    def mean_sd(sample: Sequence[float]) -> tuple[float, float]:
        average = sum(sample) / len(sample)
        variance = sum((value - average) ** 2 for value in sample) / max(len(sample) - 1, 1)
        return average, math.sqrt(variance)

    rows: list[dict[str, object]] = []
    gaps: list[float] = []
    paired: dict[str, tuple[list[float], list[float]]] = {}
    for name in names:
        observed, generated = values(real, name), values(synthetic, name)
        if len(observed) < 3 or len(generated) < 3:
            rows.append({"feature": name, "status": "UNMEASURED"})
            continue
        real_mean, real_sd = mean_sd(observed)
        synthetic_mean, _ = mean_sd(generated)
        scale = max(real_sd, 1e-12)
        mean_gap = abs(synthetic_mean - real_mean) / scale
        quantile_gap = max(
            abs(quantile(generated, q) - quantile(observed, q)) / scale for q in (0.1, 0.5, 0.9)
        )
        feature_gap = max(mean_gap, quantile_gap)
        gaps.append(feature_gap)
        paired[name] = (observed, generated)
        feature_row: dict[str, object] = {
            "feature": name,
            "status": "MEASURED",
            "real_n": len(observed),
            "synthetic_n": len(generated),
            "standardized_mean_gap": mean_gap,
            "standardized_quantile_gap": quantile_gap,
            "gap": feature_gap,
        }
        rows.append(feature_row)

    def correlation(left: Sequence[float], right: Sequence[float]) -> float | None:
        size = min(len(left), len(right))
        if size < 3:
            return None
        x, y = list(left[:size]), list(right[:size])
        mx, sx = mean_sd(x)
        my, sy = mean_sd(y)
        if sx <= 1e-12 or sy <= 1e-12:
            return None
        return sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True)) / ((size - 1) * sx * sy)

    correlation_gaps: list[float] = []
    pair_rows: list[dict[str, object]] = []
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            if left not in paired or right not in paired:
                continue
            real_corr = correlation(paired[left][0], paired[right][0])
            synthetic_corr = correlation(paired[left][1], paired[right][1])
            gap = (
                abs(real_corr - synthetic_corr)
                if real_corr is not None and synthetic_corr is not None
                else None
            )
            if gap is not None:
                correlation_gaps.append(gap)
            pair_rows.append(
                {
                    "features": [left, right],
                    "real_correlation": real_corr,
                    "synthetic_correlation": synthetic_corr,
                    "gap": gap,
                }
            )
    worst = max([*gaps, *correlation_gaps], default=None)
    if worst is None:
        status = "UNMEASURED"
    elif max_preregistered_gap is None:
        status = "CALIBRATION_THRESHOLD_REQUIRED"
    elif worst <= max_preregistered_gap:
        status = "CALIBRATED_FOR_ROBUSTNESS_ONLY"
    else:
        status = "REALITY_GAP"
    return {
        "status": status,
        "features": rows,
        "correlations": pair_rows,
        "worst_normalized_gap": worst,
        "max_preregistered_gap": max_preregistered_gap,
        "calibrated": status == "CALIBRATED_FOR_ROBUSTNESS_ONLY",
        "synthetic_alpha_authority": False,
        "authority": "ROBUSTNESS/HYPOTHESIS ONLY -- real untouched evidence remains mandatory",
    }
