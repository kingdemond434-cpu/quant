"""Gate items 17/18: lineage reconstructed, and five dashboards on one feed counted as one."""
from __future__ import annotations

from libs.research.source_lineage import (
    DERIVATION_LAYERS,
    DESK_FIELDS,
    REDUNDANCY_USES,
    Field,
    effective_independent_sources,
    reconstruct,
    upstream_vs_aggregator,
)

_RAW = Field(terminal="binance", data_field="price", upstream_source_id="binance",
             derivation_layer="RAW_OBSERVATION")
_DASH = Field(terminal="dashboard_a", data_field="price", upstream_source_id="binance",
              derivation_layer="AGGREGATED", redistribution_chain=("binance", "dashboard_a"))
_DASH2 = Field(terminal="dashboard_b", data_field="price", upstream_source_id="binance",
               derivation_layer="TERMINAL_VISUALIZATION",
               redistribution_chain=("binance", "vendor", "dashboard_b"))
_OTHER = Field(terminal="bybit", data_field="price", upstream_source_id="bybit",
               derivation_layer="RAW_OBSERVATION")


# ------------------------------------------------------------------ item 17: reconstruction
def test_item17_a_terminals_fields_are_walked_through_the_stations() -> None:
    out = reconstruct(list(DESK_FIELDS))
    assert out["status"] == "MEASURED" and out["n_fields"] == len(DESK_FIELDS)
    assert "binance_spot" in out["terminals"]


def test_item17_an_incomplete_field_is_kept_with_its_gaps_named_never_dropped() -> None:
    """Dropping half-reconstructed fields would hide the terminal's LEAST understood ones --
    exactly the ones worth understanding."""
    out = reconstruct([_RAW])
    f = out["fields"][0]
    assert f["station_status"] == "INCOMPLETE" and "rights" in f["missing_stations"]
    assert out["n_fields"] == 1, "the field is still counted"


def test_item17_no_fields_is_unmeasured_not_an_empty_terminal() -> None:
    assert reconstruct([])["status"] == "UNMEASURED"


def test_item17_an_unknown_derivation_layer_ranks_worst_not_best() -> None:
    f = Field(terminal="t", data_field="d", upstream_source_id="u", derivation_layer="INVENTED")
    assert f.fidelity_rank() == len(DERIVATION_LAYERS)


def test_derivation_layers_run_best_to_worst() -> None:
    assert DERIVATION_LAYERS[0] == "RAW_OBSERVATION"
    assert DERIVATION_LAYERS[-1] == "TERMINAL_VISUALIZATION"


# ------------------------------------------------------------------ item 18: no false diversity
def test_item18_three_routes_to_one_upstream_count_as_one_source() -> None:
    """THE POINT. Five dashboards consuming Binance data are one observation of the world."""
    out = effective_independent_sources([_RAW, _DASH, _DASH2])
    assert out["source_count"] == 3
    assert out["effective_independent_information_source_count"] == 1
    assert out["false_diversity"] == 2 and out["inflation_factor"] == 3.0


def test_item18_genuinely_separate_venues_are_counted_separately() -> None:
    out = effective_independent_sources([_RAW, _OTHER])
    assert out["effective_independent_information_source_count"] == 2
    assert out["false_diversity"] == 0


def test_item18_the_retained_route_is_the_highest_fidelity_one() -> None:
    out = effective_independent_sources([_DASH2, _DASH, _RAW])
    assert out["independent"][0]["retained_route"] == "binance:price"
    assert out["independent"][0]["derivation_layer"] == "RAW_OBSERVATION"


def test_item18_a_duplicate_loses_information_credit_not_its_place() -> None:
    """XIX-B is explicit that redundant routes stay useful. An independence test read as a delete
    order would cause the very loss this module exists to prevent."""
    out = effective_independent_sources([_RAW, _DASH])
    dup = out["redundant"][0]
    assert dup["classification"] == "USEFUL_BUT_NOT_INDEPENDENT"
    assert set(dup["still_good_for"]) == set(REDUNDANCY_USES)
    assert "NOT its place on the desk" in dup["why"]


def test_item18_the_real_desk_routes_are_inflated_and_the_count_says_so() -> None:
    """RUNTIME EVIDENCE on the desk's own collectors: 8 routes, 4 upstream observations.
    The three llama subdomains are one provider, and coingecko's price is Binance's."""
    out = effective_independent_sources(list(DESK_FIELDS))
    assert out["source_count"] == 8
    assert out["effective_independent_information_source_count"] == 4
    assert out["false_diversity"] == 4
    upstreams = {r["upstream_source_id"] for r in out["independent"]}
    assert upstreams == {"binance", "bybit", "defillama", "ethereum_l1"}


def test_item18_nothing_examined_is_unmeasured_never_zero() -> None:
    out = effective_independent_sources([])
    assert out["status"] == "UNMEASURED" and "never zero" in out["why"]


# ------------------------------------------------------------------ XIX-A upstream-first
def test_upstream_first_prefers_the_raw_route_over_a_derived_copy() -> None:
    out = upstream_vs_aggregator(direct=_RAW, aggregator=_DASH)
    assert out["verdict"] == "PREFER_DIRECT_UPSTREAM" and "downgrade" in out["why"]


def test_an_aggregator_with_stated_incremental_value_can_win() -> None:
    """Neither side wins by default -- an aggregator earns its place through unique normalisation,
    difficult integrations or derived measurements it alone provides."""
    agg = Field(terminal="llama", data_field="tvl", upstream_source_id="defillama",
                derivation_layer="RAW_OBSERVATION",
                unique_incremental_information="cross-protocol TVL the desk does not compute")
    out = upstream_vs_aggregator(direct=_RAW, aggregator=agg)
    assert out["verdict"] == "PREFER_AGGREGATOR"


def test_same_layer_with_no_incremental_value_prefers_direct() -> None:
    agg = Field(terminal="mirror", data_field="price", upstream_source_id="binance",
                derivation_layer="RAW_OBSERVATION")
    assert upstream_vs_aggregator(direct=_RAW, aggregator=agg)["verdict"] == \
        "PREFER_DIRECT_UPSTREAM"


def test_no_known_direct_route_is_a_research_gap_not_an_endorsement() -> None:
    """'We only know the aggregator' must never harden into 'the aggregator is the right route'."""
    out = upstream_vs_aggregator(direct=None, aggregator=_DASH)
    assert out["verdict"] == "AGGREGATOR_ONLY_ROUTE_KNOWN"
    assert "RESEARCH GAP" in out["why"] and out["next_action"]
