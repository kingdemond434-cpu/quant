"""Evolution and coverage control for methods that discover alpha.

This module allocates no capital and promotes no strategy.  It measures downstream discovery
value, exposes missing search methodologies, and preserves one bounded distant-domain probe so an
incumbent ontology cannot silently assign zero probability to every unfamiliar frontier.
"""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import TypedDict

from libs.core.coerce import finite_float

SEARCH_METHODS = (
    "mechanism_first",
    "data_first",
    "anomaly_first",
    "participant_first",
    "constraint_first",
    "causal",
    "statistical",
    "graph_based",
    "residual_based",
    "cross_domain",
    "adversarial",
    "generative",
    "reverse_engineering",
    "execution_derived",
    "incident_derived",
    "independent_blind_rediscovery",
    "automated_feature_discovery",
    "search_method_discovery",
)

_KEYWORDS: dict[str, tuple[str, ...]] = {
    "mechanism_first": ("mechanism", "forced flow", "incentive"),
    "data_first": ("new data", "new axis", "dataset", "collector", "reconstruct"),
    "anomaly_first": ("anomaly", "outlier", "seasonal", "pattern"),
    "participant_first": ("participant", "whale", "market maker", "retail", "miner"),
    "constraint_first": ("constraint", "capital control", "margin", "settlement", "forced"),
    "causal": ("causal", "confound", "invariant", "mediator"),
    "statistical": ("statistical", "residual", "factor", "cluster", "regression"),
    "graph_based": ("graph", "network", "wallet", "entity link"),
    "residual_based": ("residual", "unexplained", "orthogonalise", "orthogonalize"),
    "cross_domain": ("cross-domain", "analogy", "epidemiolog", "insurance", "ecolog"),
    "adversarial": ("adversarial", "red team", "falsif", "challenge"),
    "generative": ("generative", "combine", "fusion", "mutation"),
    "reverse_engineering": ("reverse engineer", "replicate", "public strategy", "reproduction"),
    "execution_derived": ("execution", "fill", "slippage", "latency", "order book"),
    "incident_derived": ("incident", "outage", "post-mortem", "postmortem", "failure"),
    "independent_blind_rediscovery": ("blind rediscovery", "independent map", "cold agent"),
    "automated_feature_discovery": ("feature discovery", "symbolic", "representation search"),
    "search_method_discovery": ("search method", "research method", "meta-search"),
}

_DISTANT_DOMAINS = (
    "ecological regime shifts",
    "epidemiological contagion",
    "reliability engineering and hazard models",
    "auction design and matching markets",
    "supply-chain bottleneck propagation",
    "adversarial cybersecurity telemetry",
    "queueing networks and congestion control",
    "insurance reserving and ruin theory",
    "linguistic diffusion and narrative mutation",
    "information theory and active learning",
    "control theory and partially observed systems",
    "biological evolution and niche construction",
)


def _explicit_methods(row: Mapping[str, object]) -> list[str]:
    raw = row.get("search_methods", row.get("search_method", ()))
    values = [raw] if isinstance(raw, str) else list(raw) if isinstance(raw, Sequence) else []
    return sorted({str(value) for value in values if str(value) in SEARCH_METHODS})


class SearchClassification(TypedDict):
    methods: list[str]
    provenance: str


def classify_search_methods(row: Mapping[str, object]) -> SearchClassification:
    """Prefer explicit provenance; keyword inference is labelled and never treated as fact."""
    methods = _explicit_methods(row)
    if methods:
        return {"methods": methods, "provenance": "EXPLICIT"}
    blob = " ".join(
        str(row.get(key, ""))
        for key in (
            "id",
            "decision",
            "hypothesis",
            "success_metric",
            "flagged_gap",
            "observation",
        )
    ).casefold()
    inferred = sorted(
        method for method, words in _KEYWORDS.items() if any(word in blob for word in words)
    )
    return {"methods": inferred, "provenance": "INFERRED" if inferred else "UNMEASURED"}


def _outcomes(row: Mapping[str, object]) -> dict[str, float]:
    def flag(name: str) -> float:
        value = row.get(name, 0.0)
        return float(value) if isinstance(value, (int, float)) else float(bool(value))

    realised = row.get("realized_value", row.get("realised_value", 0.0))
    return {
        "novel_mechanisms": flag("novel_mechanism"),
        "useful_information": flag("useful_information"),
        "near_survivors": flag("near_survivor"),
        "independent_survivors": flag("independent_survivor"),
        "realized_value": float(realised) if isinstance(realised, (int, float)) else 0.0,
    }


def _history_stagnation(history: Sequence[Mapping[str, object]]) -> dict[str, object]:
    usable: list[float] = []
    for row in history[-6:]:
        value = row.get("total_value")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            usable.append(float(value))
    if len(usable) < 3:
        return {"status": "UNMEASURED", "stagnating": None, "windows": len(usable)}
    recent = usable[-3:]
    prior = usable[:-3]
    stagnating = max(recent) <= 0 or (prior and sum(recent) / 3 <= sum(prior) / len(prior))
    return {
        "status": "MEASURED",
        "stagnating": bool(stagnating),
        "windows": len(usable),
        "recent_mean_value": sum(recent) / len(recent),
        "prior_mean_value": sum(prior) / len(prior) if prior else None,
    }


def _serendipity(as_of: str, history: Sequence[Mapping[str, object]]) -> dict[str, object]:
    used = {
        str(row.get("serendipity_domain"))
        for row in history[-len(_DISTANT_DOMAINS) :]
        if row.get("serendipity_domain")
    }
    available = [domain for domain in _DISTANT_DOMAINS if domain not in used] or list(
        _DISTANT_DOMAINS
    )
    digest = hashlib.sha256(as_of.encode("utf-8")).digest()
    domain = available[int.from_bytes(digest[:4], "big") % len(available)]
    return {
        "status": "ACTIVE",
        "bounded_concurrent_missions": 1,
        "fixed_allocation_percentage": False,
        "domain": domain,
        "mission": (
            f"Extract one falsifiable market mechanism or a justified null from {domain}; "
            "record the analogy breakpoints and route any candidate through ordinary validation"
        ),
        "promotion_authority": False,
        "expiry": "one completed experiment; rotate after disposition",
    }


def evolve_search_strategies(
    events: Sequence[Mapping[str, object]],
    history: Sequence[Mapping[str, object]] = (),
    *,
    as_of: str | None = None,
) -> dict[str, object]:
    """Measure, mutate, combine and conservatively nominate retirement of search methods."""
    day = as_of or datetime.now(tz=UTC).date().isoformat()
    stats: dict[str, dict[str, float]] = {
        method: defaultdict(float, attempts=0.0, explicit_attempts=0.0) for method in SEARCH_METHODS
    }
    unattributed = 0
    credit: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in events:
        classified = classify_search_methods(row)
        methods = list(classified["methods"])
        if not methods:
            unattributed += 1
            continue
        outcomes = _outcomes(row)
        method_weight = 1.0 / len(methods)
        for method in methods:
            stats[method]["attempts"] += method_weight
            if classified["provenance"] == "EXPLICIT":
                stats[method]["explicit_attempts"] += method_weight
            for key, value in outcomes.items():
                stats[method][key] += value * method_weight
        contributors = row.get("contributors", {})
        if isinstance(contributors, Mapping):
            for kind, raw_values in contributors.items():
                values = (
                    [raw_values]
                    if isinstance(raw_values, str)
                    else (list(raw_values) if isinstance(raw_values, Sequence) else [])
                )
                if values:
                    value = outcomes["realized_value"] + outcomes["independent_survivors"]
                    for contributor in values:
                        credit[f"{kind}:{contributor}"]["fractional_downstream_value"] += (
                            value / len(values)
                        )
                        credit[f"{kind}:{contributor}"]["traces"] += 1

    rows: list[dict[str, object]] = []
    for method in SEARCH_METHODS:
        method_stats = dict(stats[method])
        attempts = method_stats.get("attempts", 0.0)
        useful = method_stats.get("useful_information", 0.0) + method_stats.get(
            "independent_survivors", 0.0
        )
        alpha = 1.0 + useful
        beta = 1.0 + max(0.0, attempts - useful)
        mean = alpha / (alpha + beta)
        sd = math.sqrt(alpha * beta / ((alpha + beta) ** 2 * (alpha + beta + 1)))
        rows.append(
            {
                "method": method,
                **{key: round(value, 6) for key, value in method_stats.items()},
                "useful_yield_posterior": round(mean, 6),
                "useful_yield_upper_approx_95": round(min(1.0, mean + 2 * sd), 6),
            }
        )
    covered = [row for row in rows if finite_float(row.get("attempts")) > 0]
    missing = [str(row["method"]) for row in rows if finite_float(row.get("attempts")) == 0]
    total = sum(finite_float(row.get("attempts")) for row in rows)
    hhi = sum((finite_float(row.get("attempts")) / total) ** 2 for row in rows) if total else None
    effective = (1.0 / hhi) if hhi else None
    starvation = bool(
        total and effective is not None and effective < max(2.0, math.sqrt(len(SEARCH_METHODS)))
    )
    stagnation = _history_stagnation(history)
    ranked = sorted(
        covered,
        key=lambda row: (
            -finite_float(row.get("useful_yield_posterior")),
            str(row.get("method", "")),
        ),
    )
    anchor = str(ranked[0]["method"]) if ranked else "mechanism_first"
    mutations = [
        {
            "candidate": f"{anchor}+{method}",
            "status": "PREREGISTRATION_REQUIRED",
            "reason": (
                "test a missing methodology through a measured incumbent without "
                "multiplying queries"
            ),
        }
        for method in missing[:3]
    ]
    if stagnation.get("stagnating") is True:
        mutations.insert(
            0,
            {
                "candidate": "search_method_discovery+independent_blind_rediscovery",
                "status": "PREREGISTRATION_REQUIRED",
                "reason": (
                    "measured yield stagnated; change the search process, not merely the query"
                ),
            },
        )
    retire = [
        {
            "method": row["method"],
            "status": "REVIEW_FOR_RETIREMENT",
            "reason": (
                ">=10 fractionally credited attempts, no independent survivor, "
                "low posterior ceiling"
            ),
        }
        for row in rows
        if finite_float(row.get("attempts")) >= 10
        and finite_float(row.get("independent_survivors")) == 0
        and finite_float(row.get("useful_yield_upper_approx_95")) < 0.2
    ]
    return {
        "status": "MEASURED" if total else "UNMEASURED",
        "method_taxonomy": list(SEARCH_METHODS),
        "methods": rows,
        "coverage": {
            "represented": len(covered),
            "total": len(SEARCH_METHODS),
            "ratio": len(covered) / len(SEARCH_METHODS),
            "missing": missing,
            "unattributed_events": unattributed,
            "explicit_provenance_ratio": (
                sum(finite_float(row.get("explicit_attempts")) for row in rows) / total
                if total
                else None
            ),
        },
        "concentration": {
            "hhi": hhi,
            "effective_method_count": effective,
            "exploration_starvation": starvation if total else None,
            "rule": "no fixed exploration percentage; investigate measured concentration",
        },
        "stagnation": stagnation,
        "mutations_and_combinations": mutations,
        "retirement_candidates": retire,
        "discovery_credit": [
            {"contributor": name, **dict(values)} for name, values in sorted(credit.items())
        ],
        "serendipity_channel": _serendipity(day, history),
        "recursive_question": "What method could discover a new method of discovering alpha?",
        "authority": "RESEARCH ALLOCATION PRIOR ONLY; no survivor promotion or capital authority",
    }


__all__ = ["SEARCH_METHODS", "classify_search_methods", "evolve_search_strategies"]
