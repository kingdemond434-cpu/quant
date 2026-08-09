from __future__ import annotations

from libs.research.search_strategy import SEARCH_METHODS, evolve_search_strategies


def test_missing_methods_and_bounded_serendipity_remain_visible() -> None:
    report = evolve_search_strategies([], as_of="2026-08-09")
    assert report["status"] == "UNMEASURED"
    assert report["coverage"]["ratio"] == 0
    assert set(report["coverage"]["missing"]) == set(SEARCH_METHODS)
    channel = report["serendipity_channel"]
    assert channel["status"] == "ACTIVE"
    assert channel["bounded_concurrent_missions"] == 1
    assert channel["fixed_allocation_percentage"] is False
    assert channel["promotion_authority"] is False


def test_explicit_method_provenance_and_fractional_credit() -> None:
    report = evolve_search_strategies(
        [
            {
                "search_methods": ["causal", "participant_first"],
                "useful_information": True,
                "independent_survivor": True,
                "realized_value": 4.0,
                "contributors": {"agent": ["cold_a", "cold_b"], "language": "zh"},
            }
        ],
        as_of="2026-08-09",
    )
    by_method = {row["method"]: row for row in report["methods"]}
    assert by_method["causal"]["attempts"] == 0.5
    assert by_method["participant_first"]["independent_survivors"] == 0.5
    assert report["coverage"]["explicit_provenance_ratio"] == 1.0
    credit = {row["contributor"]: row for row in report["discovery_credit"]}
    assert credit["agent:cold_a"]["fractional_downstream_value"] == 2.5
    assert credit["language:zh"]["fractional_downstream_value"] == 5.0


def test_concentration_fires_starvation_without_a_fixed_quota() -> None:
    events = [
        {"search_method": "data_first", "useful_information": i == 0}
        for i in range(20)
    ]
    report = evolve_search_strategies(events, as_of="2026-08-09")
    assert report["concentration"]["exploration_starvation"] is True
    assert report["concentration"]["effective_method_count"] == 1.0
    assert report["mutations_and_combinations"]


def test_measured_stagnation_changes_method_not_just_query() -> None:
    history = [{"total_value": x} for x in (4.0, 3.0, 0.0, 0.0, 0.0)]
    report = evolve_search_strategies(
        [{"search_method": "mechanism_first", "useful_information": True}],
        history,
        as_of="2026-08-09",
    )
    assert report["stagnation"]["stagnating"] is True
    first = report["mutations_and_combinations"][0]
    assert "search_method_discovery" in first["candidate"]
    assert first["status"] == "PREREGISTRATION_REQUIRED"


def test_keyword_inference_is_labelled_not_treated_as_explicit() -> None:
    report = evolve_search_strategies(
        [{"hypothesis": "reverse engineer a public strategy"}], as_of="2026-08-09"
    )
    assert report["coverage"]["represented"] == 1
    assert report["coverage"]["explicit_provenance_ratio"] == 0.0
