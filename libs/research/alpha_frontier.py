"""Additional alpha-factory controls recovered from the external-strategy mandate.

The functions measure mechanisms and process economics.  They generate priors and candidates only;
none can promote an alpha, alter a validator, set leverage, or place an order.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence

import numpy as np

from libs.core.coerce import finite_float, object_sequence

TRANSFER_CLASSES = frozenset(
    {
        "UNIVERSAL",
        "ASSET_FAMILY",
        "VENUE_SPECIFIC",
        "PROTOCOL_SPECIFIC",
        "EVENT_SPECIFIC",
        "MICROSTRUCTURE_SPECIFIC",
    }
)


def alpha_reproduction(
    events: Sequence[Mapping[str, object]], *, window_days: float
) -> dict[str, object]:
    if window_days <= 0:
        raise ValueError("window_days must be positive")
    counts = Counter(str(e.get("event", "UNKNOWN")) for e in events)
    born, decayed = counts["BORN"], counts["DECAYED"]
    retired, replaced = counts["RETIRED"], counts["REPLACED"]
    lost = max(decayed, retired)
    replacement_times = [
        finite_float(e.get("replacement_days"))
        for e in events
        if isinstance(e.get("replacement_days"), (int, float))
    ]
    return {
        "birth_rate_per_day": born / window_days,
        "decay_rate_per_day": decayed / window_days,
        "retirement_rate_per_day": retired / window_days,
        "replacement_ratio": replaced / lost if lost else None,
        "net_alpha_reproduction": born - lost,
        "median_days_to_replace": float(np.median(replacement_times))
        if replacement_times
        else None,
        "objective": "economic contribution replaced, not strategy count",
    }


def validation_evig(
    *,
    probability_changes_decision: float,
    economic_value_if_resolved: float,
    test_cost: float,
    delay_cost: float = 0.0,
) -> dict[str, object]:
    p = max(0.0, min(1.0, probability_changes_decision))
    net = p * economic_value_if_resolved - max(0.0, test_cost) - max(0.0, delay_cost)
    return {
        "expected_information_value": p * economic_value_if_resolved,
        "net_evig": net,
        "run": bool(net > 0),
        "guard": "a negative EVIG defers one test; it never caps research breadth globally",
    }


def mechanism_transfer(
    mechanism_id: str,
    transfer_class: str,
    target: Mapping[str, str],
    constraints: Mapping[str, Sequence[str]],
) -> dict[str, object]:
    if transfer_class not in TRANSFER_CLASSES:
        raise ValueError("unknown transfer class")
    failures = [
        {"field": field, "actual": target.get(field), "allowed": list(allowed)}
        for field, allowed in constraints.items()
        if target.get(field) not in allowed
    ]
    return {
        "mechanism_id": mechanism_id,
        "transfer_class": transfer_class,
        "eligible": not failures,
        "constraint_failures": failures,
        "note": "specialization is not failure on an irrelevant market",
    }


def mechanism_eligibility(
    state_probabilities: Mapping[str, float],
    conditional_economics: Mapping[str, Mapping[str, float]],
) -> dict[str, object]:
    if not state_probabilities or abs(sum(state_probabilities.values()) - 1) > 1e-6:
        return {"status": "UNMEASURED"}
    rows = {}
    for mechanism, by_state in conditional_economics.items():
        edge = sum(
            float(p) * float(by_state.get(state, 0.0)) for state, p in state_probabilities.items()
        )
        positive_p = sum(
            float(p)
            for state, p in state_probabilities.items()
            if float(by_state.get(state, 0.0)) > 0
        )
        rows[mechanism] = {
            "forward_net_elog": edge,
            "positive_state_probability": positive_p,
            "eligible": edge > 0,
        }
    return {"status": "MEASURED", "mechanisms": rows}


def multi_timescale_state(
    *,
    structural: Mapping[str, object],
    tactical: Mapping[str, object],
    fast: Mapping[str, object],
    microstructure: Mapping[str, object],
    as_of: object,
) -> dict[str, object]:
    layers = {
        "structural": dict(structural),
        "tactical": dict(tactical),
        "fast": dict(fast),
        "microstructure": dict(microstructure),
    }
    return {
        "as_of": as_of,
        "layers": layers,
        "measured_layers": sum(bool(v) for v in layers.values()),
        "selection_accounting_required": True,
    }


def mechanism_half_life(edge_history: Sequence[float], times: Sequence[float]) -> dict[str, object]:
    edge, t = np.asarray(edge_history, dtype="float64"), np.asarray(times, dtype="float64")
    mask = np.isfinite(edge) & np.isfinite(t) & (edge > 0)
    edge, t = edge[mask], t[mask]
    if edge.size < 3 or np.ptp(t) <= 0:
        return {"status": "UNMEASURED"}
    slope, intercept = np.polyfit(t - t.min(), np.log(edge), 1)
    if slope >= 0:
        return {"status": "MEASURED", "half_life": None, "decaying": False}
    half_life = math.log(2) / -float(slope)
    fitted = intercept + slope * (t - t.min())
    ss_res = float(((np.log(edge) - fitted) ** 2).sum())
    ss_tot = float(((np.log(edge) - np.log(edge).mean()) ** 2).sum())
    return {
        "status": "MEASURED",
        "half_life": half_life,
        "decaying": True,
        "fit_r2": 1 - ss_res / ss_tot if ss_tot else None,
    }


def tail_complementarity(
    left: Sequence[float], right: Sequence[float], *, tail_quantile: float = 0.1
) -> dict[str, object]:
    a, b = np.asarray(left, dtype="float64"), np.asarray(right, dtype="float64")
    if a.shape != b.shape or a.size < 20:
        return {"status": "UNMEASURED"}
    ordinary = float(np.corrcoef(a, b)[0, 1])
    tail = (a <= np.quantile(a, tail_quantile)) | (b <= np.quantile(b, tail_quantile))
    tail_corr = float(np.corrcoef(a[tail], b[tail])[0, 1]) if tail.sum() >= 3 else None
    left_crash_help = float(b[a <= np.quantile(a, tail_quantile)].mean())
    right_crash_help = float(a[b <= np.quantile(b, tail_quantile)].mean())
    return {
        "status": "MEASURED",
        "ordinary_correlation": ordinary,
        "tail_correlation": tail_corr,
        "right_return_in_left_tail": left_crash_help,
        "left_return_in_right_tail": right_crash_help,
        "genuine_tail_complement": left_crash_help > 0 or right_crash_help > 0,
    }


def online_strategy_population(rows: Sequence[Mapping[str, float]]) -> dict[str, object]:
    out = []
    for row in rows:
        mean = float(row.get("edge_mean", 0.0))
        uncertainty = max(0.0, float(row.get("edge_uncertainty", 0.0)))
        decay = max(0.0, min(1.0, float(row.get("decay_hazard", 0.0))))
        reality = max(0.0, min(1.0, float(row.get("reality_retention", 1.0))))
        marginal = (mean - uncertainty) * (1 - decay) * reality
        out.append(
            {
                "strategy": row.get("strategy"),
                "marginal_elog": marginal,
                "revival_probability": row.get("revival_probability", 0.0),
            }
        )
    out.sort(key=lambda r: -finite_float(r.get("marginal_elog")))
    return {"population": out, "capital_competes_continuously": True}


def crowding_hazard(history: Sequence[Mapping[str, float]]) -> dict[str, object]:
    if len(history) < 3:
        return {"status": "UNMEASURED"}
    keys = (
        "spread_compression",
        "fill_deterioration",
        "impact_growth",
        "public_diffusion",
        "repo_replication",
        "basis_compression",
    )
    latest = history[-1]
    z = []
    components = {}
    for key in keys:
        values = np.asarray([float(r.get(key, 0.0)) for r in history], dtype="float64")
        sd = float(values[:-1].std(ddof=1)) if len(values) > 2 else 0.0
        score = (float(latest.get(key, 0.0)) - float(values[:-1].mean())) / sd if sd > 0 else 0.0
        components[key] = score
        z.append(max(0.0, score))
    hazard = 1 - math.exp(-sum(z) / max(len(z), 1))
    return {"status": "MEASURED", "crowding_decay_hazard": hazard, "components": components}


def null_factory_calibration(
    null_results: Sequence[Mapping[str, object]], *, expected_false_positive_rate: float
) -> dict[str, object]:
    if not null_results:
        return {"status": "UNMEASURED", "promotion_blocked": True}
    survived = sum(bool(r.get("survived")) for r in null_results)
    observed = survived / len(null_results)
    # Three-sigma binomial alarm, with a small-sample floor rather than pretending precision.
    se = math.sqrt(
        max(expected_false_positive_rate * (1 - expected_false_positive_rate), 1e-9)
        / len(null_results)
    )
    alarm = observed > expected_false_positive_rate + 3 * se
    return {
        "status": "CONTROL_FAILURE" if alarm else "CALIBRATED",
        "controls": len(null_results),
        "observed_false_positive_rate": observed,
        "expected_false_positive_rate": expected_false_positive_rate,
        "promotion_blocked": alarm,
    }


def family_reality_priors(transitions: Sequence[Mapping[str, object]]) -> dict[str, object]:
    ratios: dict[str, list[float]] = defaultdict(list)
    for row in transitions:
        upstream, downstream = row.get("upstream"), row.get("downstream")
        if isinstance(upstream, (int, float)) and isinstance(downstream, (int, float)) and upstream:
            ratios[str(row.get("family", "UNKNOWN"))].append(float(downstream) / float(upstream))
    return {
        "families": {
            family: {"n": len(v), "median_retention": float(np.median(v))}
            for family, v in ratios.items()
        },
        "use": "shrink new family economics before capital admission",
    }


def useful_disagreement(reviews: Sequence[Mapping[str, object]]) -> dict[str, object]:
    by_case: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in reviews:
        by_case[str(row.get("case", "UNKNOWN"))].append(row)
    disputed = sum(len({str(r.get("verdict")) for r in rows}) > 1 for rows in by_case.values())
    unique = sum(bool(r.get("unique_valid_finding")) for r in reviews)
    descendants = sum(finite_float(r.get("descendant_value")) for r in reviews)
    return {
        "cases": len(by_case),
        "disagreement_rate": disputed / len(by_case) if by_case else None,
        "unique_valid_findings": unique,
        "descendant_value": descendants,
        "assign_challenger": bool(by_case and disputed == 0),
    }


def strategy_dna(experiments: Sequence[Mapping[str, object]]) -> dict[str, object]:
    genes: dict[str, list[float]] = defaultdict(list)
    for row in experiments:
        value = finite_float(row.get("oos_elog"))
        for gene in object_sequence(row.get("components")):
            genes[str(gene)].append(value)
    rows = {
        gene: {
            "uses": len(v),
            "mean_oos_elog": float(np.mean(v)),
            "negative_gene": len(v) >= 3 and float(np.mean(v)) < 0,
        }
        for gene, v in genes.items()
    }
    return {"genes": rows, "selection_path_trials": len(experiments)}


def return_source_decomposition(
    *,
    total_return: float,
    beta_return: float = 0.0,
    leverage_multiplier: float = 1.0,
    carry_return: float = 0.0,
    concentration_return: float = 0.0,
    convexity_return: float = 0.0,
    external_flows: float = 0.0,
) -> dict[str, object]:
    components = {
        "beta": beta_return,
        "carry": carry_return,
        "concentration": concentration_return,
        "convexity": convexity_return,
        "external_flows": external_flows,
    }
    residual = total_return - sum(components.values())
    return {
        "total_return": total_return,
        "leverage_multiplier": leverage_multiplier,
        "components": {**components, "unexplained_alpha_or_luck": residual},
        "warning": "leverage and concentration are return sources, never evidence of alpha",
    }


def edge_npv(
    *,
    edge_per_period: float,
    capacity: float,
    half_life_periods: float,
    implementation_periods: float,
    operating_cost_per_period: float,
    discount_rate: float = 0.0,
) -> dict[str, object]:
    if capacity < 0 or half_life_periods <= 0 or implementation_periods < 0:
        return {"status": "UNMEASURED"}
    retained = 0.5 ** (implementation_periods / half_life_periods)
    decay = math.log(2) / half_life_periods
    pv_factor = 1 / max(decay + max(discount_rate, 0.0), 1e-12)
    gross = edge_per_period * capacity * retained * pv_factor
    cost = operating_cost_per_period * pv_factor
    return {
        "status": "MEASURED",
        "edge_npv": gross - cost,
        "edge_retained_at_launch": retained,
        "implementation_regret": edge_per_period * capacity * (1 - retained) * pv_factor,
    }


def practitioner_frontier(
    items: Sequence[Mapping[str, object]], known_mechanisms: Sequence[str]
) -> dict[str, object]:
    """Unified GPT mission output: transcript, extreme-return and public-strategy discoveries."""
    known = {str(x).casefold() for x in known_mechanisms}
    evidence_classes = {
        "MARKETING",
        "SELF_REPORTED",
        "BACKTEST",
        "PAPER",
        "PUBLIC_DASHBOARD",
        "COMPETITION_RECORD",
        "BROKER_VERIFIED",
        "PARTIALLY_VERIFIABLE",
        "VERIFIED",
        "AUDITED",
    }
    rows, new = [], []
    for item in items:
        mechanism = str(item.get("mechanism", "")).strip()
        evidence = str(item.get("evidence_class", "UNCLASSIFIED")).upper()
        novelty = (
            "GENUINELY_NEW" if mechanism and mechanism.casefold() not in known else "DUPLICATE"
        )
        row = {
            **dict(item),
            "evidence_class": evidence,
            "evidence_class_valid": evidence in evidence_classes,
            "novelty": novelty,
            "authority": "EXTERNAL_PRIOR_ONLY",
        }
        rows.append(row)
        if novelty == "GENUINELY_NEW":
            new.append(mechanism)
            known.add(mechanism.casefold())
    by_mission = Counter(str(r.get("mission", "UNCLASSIFIED")) for r in rows)
    return {
        "items": rows,
        "new_mechanisms": new,
        "mission_counts": dict(by_mission),
        "missions": ["VIDEO_TRANSCRIPT", "EXTREME_RETURN", "PUBLIC_STRATEGY"],
        "shared_downstream": (
            "ontology -> dedupe -> hypothesis family -> selection ledger -> validation"
        ),
        "k_miner_replaced": False,
    }
