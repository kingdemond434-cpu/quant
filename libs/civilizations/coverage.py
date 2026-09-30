"""THE COVERAGE TENSOR, and the mining missions its empty cells issue.

    zuck, 2026-09-30: "source type x data category x operator class x representation x mechanism
    x horizon x neutralization x conditioning x search algorithm x validation method x public
    ecosystem ... If one category is empty, the system automatically issues a mining mission."

The full product of eleven axes is ~10^9 cells and nearly all of them are meaningless, so the
tensor is kept SPARSE (only observed coordinates are stored) and "empty" is judged on the
MARGINALS and on the civilization x axis-value PAIRS the blueprint names: a civilization with no
item on a source type, an operator class no public expression used, a data category nothing
mined, a validation method no lane produced. Each empty pair becomes a mission row the source
frontier (Python) and the LLM hunter (semantic lane) both read; the mission names its axis, value
and civilization so the next pass targets it instead of re-reading the same ground.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

AXES: dict[str, tuple[str, ...]] = {
    "source_type": ("official_docs", "public_papers", "alpha101_lineage", "education",
                    "competition", "videos", "public_repositories", "simulators", "alpha_miners",
                    "research_playbooks", "postmortems", "community_discussion",
                    "authors_citations", "alternative_implementations", "datasets",
                    "engine_code", "engine_tests", "issues_prs", "docs_changes"),
    "data_category": ("price_volume", "fundamental", "analyst", "model", "news", "sentiment",
                      "social", "option", "risk", "short_interest", "insider", "institutional",
                      "macro", "flows", "alt_data", "group"),
    "operator_class": ("time_series", "cross_sectional", "group", "vector", "arithmetic",
                       "logical"),
    "representation": ("expression", "rule_code", "prose", "component", "dataset_metadata",
                       "failure_report"),
    "horizon": ("intraday", "daily", "weekly", "monthly_plus"),
    "neutralization": ("none", "market", "sector", "industry", "subindustry", "country"),
    "conditioning": ("none", "regime", "volatility", "event", "session", "trade_when"),
    "search_algorithm": ("genetic_programming", "mcts", "bayesian_optimisation",
                         "llm_generation", "grid", "manual"),
    "validation_method": ("walk_forward", "cross_validation", "out_of_sample", "deflated_sharpe",
                          "pbo", "reality_check", "bootstrap", "regression_test"),
    "ontology": ("ALPHA_MECHANISM", "FEATURE_PRIMITIVE", "DATA_IDEA", "EXECUTION_IDEA",
                 "PORTFOLIO_IDEA", "RISK_IDEA", "UNIVERSE_IDEA", "VALIDATION_IDEA",
                 "FAILURE_KNOWLEDGE", "RESEARCH_METHOD", "INFRASTRUCTURE_PATTERN"),
}
#: which axes each civilization is expected to populate (its native comparative advantage);
#: an empty expected pair is a mission, an empty unexpected one is not.
EXPECTED: dict[str, tuple[str, ...]] = {
    "worldquant": ("source_type", "data_category", "operator_class", "neutralization",
                   "search_algorithm", "validation_method", "ontology"),
    "quantconnect": ("source_type", "representation", "validation_method", "ontology"),
    "man_ahl": ("horizon", "ontology"),
    "bridgewater": ("data_category", "conditioning", "ontology"),
    "aqr": ("data_category", "validation_method", "ontology"),
    "two_sigma": ("search_algorithm", "ontology"),
    "deshaw": ("ontology",),
    "winton": ("horizon", "ontology"),
    "market_makers": ("ontology",),
    "renaissance": ("ontology",),
}
#: values a civilization cannot be expected to hold (nobody publishes Bridgewater GP code).
NOT_EXPECTED: dict[str, frozenset[str]] = {
    "bridgewater": frozenset({"FEATURE_PRIMITIVE", "INFRASTRUCTURE_PATTERN", "UNIVERSE_IDEA"}),
    "renaissance": frozenset({"INFRASTRUCTURE_PATTERN", "UNIVERSE_IDEA", "DATA_IDEA"}),
    "deshaw": frozenset({"INFRASTRUCTURE_PATTERN", "UNIVERSE_IDEA"}),
    "winton": frozenset({"INFRASTRUCTURE_PATTERN", "UNIVERSE_IDEA"}),
    "man_ahl": frozenset({"UNIVERSE_IDEA"}),
    "market_makers": frozenset({"UNIVERSE_IDEA", "FEATURE_PRIMITIVE"}),
}


class Tensor:
    def __init__(self) -> None:
        self.cells: Counter[str] = Counter()
        self.marg: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))

    def add(self, civilization: str, coords: Mapping[str, Iterable[str] | str]) -> None:
        norm: dict[str, list[str]] = {}
        for axis, v in coords.items():
            if axis not in AXES:
                continue
            vals = [v] if isinstance(v, str) else list(v or [])
            vals = [x for x in vals if x in AXES[axis]]
            if vals:
                norm[axis] = vals
                for x in vals:
                    self.marg[civilization][axis][x] += 1
        key = json.dumps({"civ": civilization, **{a: sorted(v) for a, v in norm.items()}},
                         sort_keys=True)
        self.cells[key] += 1

    def empties(self) -> list[dict[str, Any]]:
        out = []
        for civ, axes in EXPECTED.items():
            skip = NOT_EXPECTED.get(civ, frozenset())
            for axis in axes:
                seen = self.marg.get(civ, {}).get(axis, Counter())
                for val in AXES[axis]:
                    if val in skip or seen.get(val):
                        continue
                    out.append({"civilization": civ, "axis": axis, "value": val})
        return out

    def summary(self) -> dict[str, Any]:
        filled = {civ: {a: dict(c) for a, c in axes.items()} for civ, axes in self.marg.items()}
        expected_pairs = sum(len(AXES[a]) - len([v for v in AXES[a]
                                                 if v in NOT_EXPECTED.get(c, frozenset())])
                             for c, axs in EXPECTED.items() for a in axs)
        empt = self.empties()
        return {"observed_cells": len(self.cells), "expected_pairs": expected_pairs,
                "empty_pairs": len(empt),
                "coverage": round(1 - len(empt) / expected_pairs, 4) if expected_pairs else None,
                "marginals": filled}


#: axis/value -> the query words a mission hands the frontier and the LLM hunter.
MISSION_WORDS: dict[str, str] = {
    "alpha101_lineage": "alpha101 implementation", "competition": "IQC competition alpha",
    "videos": "video lecture", "postmortems": "postmortem failed strategy",
    "simulators": "alpha simulator backtester open source", "alpha_miners": "alpha miner",
    "research_playbooks": "research playbook process", "authors_citations": "paper citations",
    "vector": "vector_neut regression_neut", "logical": "trade_when if_else",
    "group": "group_neutralize group_rank sector", "option": "implied volatility",
    "short_interest": "short interest", "insider": "insider transactions",
    "institutional": "13F institutional holdings", "flows": "fund flows", "macro": "macro",
    "mcts": "monte carlo tree search", "bayesian_optimisation": "bayesian optimization",
    "genetic_programming": "genetic programming", "llm_generation": "LLM agent",
    "pbo": "probability of backtest overfitting", "deflated_sharpe": "deflated sharpe",
    "reality_check": "white reality check SPA", "regression_test": "regression test",
}


def missions(empties: Iterable[Mapping[str, Any]], *, max_n: int = 200) -> list[dict[str, Any]]:
    out = []
    for e in list(empties)[:max_n]:
        civ, axis, val = e["civilization"], e["axis"], e["value"]
        words = MISSION_WORDS.get(val, val.replace("_", " ").lower())
        out.append({"mission_id": f"m:{civ}:{axis}:{val}", "civilization": civ, "axis": axis,
                    "value": val,
                    "query": f"{civ.replace('_', ' ')} {words}".strip(),
                    "for": ["source_frontier", "llm_brain_hunter"],
                    "why": f"no mined item of {civ} has {axis}={val}"})
    return out
