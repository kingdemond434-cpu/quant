"""THE NET-EDGE FUNCTION'S OWN FENCES.

Every assertion here is a property the principal's order depends on: net is the currency, an
UNMEASURED cost never reads as zero, capacity falls as size rises, and the heat total is
preserved by every reallocation the module can produce.
"""
from __future__ import annotations

import math

import pytest

from libs.research import net_edge as NE


def _cell(gross: float, *, spread: float | None = 0.01, impact: float | None = 0.0,
          financing: float | None = 0.0, commission: float | None = 0.0,
          multiplicity: float | None = 0.0, key: str = "cell", **kw) -> NE.NetEdge:
    def t(name: str, value: float | None) -> NE.CostTerm:
        return (NE.measured(name, value, "test") if value is not None
                else NE.unpriced(name, "planted UNMEASURED"))
    return NE.net_edge(key, gross, spread_slippage=t("spread_slippage", spread),
                       impact=t("impact", impact), financing=t("financing", financing),
                       commission=t("commission", commission),
                       multiplicity=t("multiplicity", multiplicity), **kw)


# ------------------------------------------------------------------ a planted COST_DEAD cell


def test_gross_positive_cost_negative_cell_is_cost_dead_with_a_missed_growth_line() -> None:
    """The headline property: a cell that looks good gross and is dead net says so, and the
    refusal is BILLED. A COST_DEAD verdict with no missed-growth line is a silent rail."""
    row = _cell(0.10, spread=0.04, impact=0.02, financing=0.01, commission=0.02,
                multiplicity=0.05, key="planted", symbol="EURUSD", family="carry",
                n=180)
    assert row.gross is not None and row.gross > 0
    assert row.net is not None and row.net < 0
    assert row.verdict == NE.COST_DEAD
    assert NE.sign_flips([row]) == 1
    assert NE.cost_dead([row]) == [row]

    line = NE.missed_growth_line(row, heat_share=0.05, trades_per_day=2.0)
    assert line["rail"] == "net_edge_cost_dead"
    assert line["verdict"] == "EARNS_ITS_PLACE"          # refusing a negative-net cell earns it
    assert line["two_sided"] is True
    assert line["avoided_loss_per_day"] == pytest.approx(-row.net * 2.0)
    assert line["delta_elogw_per_day"] == pytest.approx(-row.net * 2.0 * 0.05)

    # ...and it is ROUTED, not dropped: the child is the same idea at lower turnover.
    req = NE.descendant_request(row)
    assert req["gross_gain"] > 0 >= req["net_gain"]
    from libs.research.coevolution_lab import FAILURE_RULES, classify_failure
    assert classify_failure(req) == "cost_dead"
    assert FAILURE_RULES["cost_dead"][1] == "lower_turnover_descendant"


def test_a_gross_positive_cell_that_survives_its_costs_is_not_cost_dead() -> None:
    row = _cell(0.50, spread=0.04, impact=0.02, financing=-0.01, commission=0.02,
                multiplicity=0.05)
    assert row.verdict == NE.NET_POSITIVE
    assert row.net == pytest.approx(0.50 - (0.04 + 0.02 - 0.01 + 0.02 + 0.05))
    assert NE.sign_flips([row]) == 0


# ------------------------------------------------------------------ UNMEASURED is not zero


def test_an_unmeasured_cost_term_never_reads_as_zero() -> None:
    priced = _cell(0.10, multiplicity=0.0)
    unknown = _cell(0.10, multiplicity=None)
    # The two nets can coincide arithmetically -- what must NOT coincide is the claim.
    assert priced.status == NE.MEASURED
    assert priced.verdict == NE.NET_POSITIVE
    assert unknown.status == "PARTIAL"
    assert unknown.verdict == NE.NET_POSITIVE_UNCONFIRMED
    assert unknown.unpriced_terms == ("multiplicity",)
    assert unknown.term("multiplicity").value is None
    assert unknown.as_dict()["net_is_bound"] is True
    assert unknown.as_dict()["terms"]["multiplicity"]["status"] == NE.UNMEASURED


def test_an_unmeasured_signed_term_downgrades_the_cost_dead_verdict() -> None:
    """Financing is the one term that can be a CREDIT, so a negative bound with financing
    unpriced is COST_DEAD_UNCONFIRMED: the desk may not claim a cell is dead on a term that
    could have paid it."""
    conservative = _cell(0.05, spread=0.06, multiplicity=None)
    assert conservative.conservative is True
    assert conservative.verdict == NE.COST_DEAD
    signed = _cell(0.05, spread=0.06, financing=None)
    assert signed.conservative is False
    assert signed.verdict == NE.COST_DEAD_UNCONFIRMED
    assert NE.cost_dead([signed]) == []                       # not routed on an unproven kill
    assert NE.cost_dead([signed], include_unconfirmed=True) == [signed]


def test_a_row_with_no_gross_is_unmeasured_and_not_a_net_of_zero() -> None:
    row = _cell(None)  # type: ignore[arg-type]
    assert row.net is None
    assert row.status == NE.UNMEASURED
    assert row.verdict == NE.UNMEASURED
    assert NE.missed_growth_line(row)["verdict"] == NE.UNMEASURED


def test_rescale_to_a_per_day_unit_without_a_trade_rate_unprices_every_term() -> None:
    row = _cell(0.30)
    joined = NE.rescale_to_unit(row, unit=NE.R_PER_DAY, per_trade_to_unit=None)
    assert joined.unit == NE.R_PER_DAY
    assert set(joined.unpriced_terms) == set(NE.TERMS)
    assert joined.net == pytest.approx(0.30)        # a BOUND, and the status says so
    assert joined.status == NE.UNMEASURED
    scaled = NE.rescale_to_unit(row, unit=NE.R_PER_DAY, per_trade_to_unit=3.0)
    assert scaled.cost_priced == pytest.approx(row.cost_priced * 3.0)


def test_multiplicity_without_a_sigma_is_unmeasured_not_free() -> None:
    assert NE.multiplicity_charge(0.13, None).status == NE.UNMEASURED
    assert NE.multiplicity_charge(0.13, None).value is None
    charged = NE.multiplicity_charge(0.131, 1.2373, n_trials=3001)
    assert charged.status == NE.MEASURED
    assert charged.value == pytest.approx(0.131 * 1.2373)
    assert "3001 trials" in charged.note


def test_multiplicity_from_trials_records_a_verdict_on_a_host_without_the_judge() -> None:
    term = NE.multiplicity_from_trials(1, 0.05, 1.0)
    assert term.status == NE.UNMEASURED and term.value is None
    got = NE.multiplicity_from_trials(500, 0.05, 1.0)
    assert got.status in (NE.MODELLED, NE.UNMEASURED)
    if got.status == NE.MODELLED:
        assert got.value is not None and got.value > 0


# ------------------------------------------------------------------ capacity


def test_capacity_falls_as_size_rises_and_is_zero_where_net_is_already_gone() -> None:
    row = _cell(0.20, impact=None)   # impact is charged by size below, not planted
    sizes = [0.1, 0.5, 1.0, 2.0, 5.0, 20.0]
    nets = [NE.net_at_size(row, q, ref_lots=1.0, ref_impact_r=0.05) for q in sizes]
    assert all(n is not None for n in nets)
    assert all(nets[i] > nets[i + 1] for i in range(len(nets) - 1)), nets  # type: ignore[operator]

    cap = NE.capacity_size(row, ref_lots=1.0, ref_impact_r=0.05)
    assert cap["status"] == NE.MODELLED
    # gross 0.20 less the planted 0.01 spread = 0.19 of headroom; sqrt law at 0.05R per lot.
    assert cap["lots"] == pytest.approx(1.0 * (0.19 / 0.05) ** 2.0)
    # net at exactly the capacity is zero, which is what the number MEANS.
    at_cap = NE.net_at_size(row, cap["lots"], ref_lots=1.0, ref_impact_r=0.05)
    assert at_cap == pytest.approx(0.0, abs=1e-9)
    # and one lot past it is negative
    past = NE.net_at_size(row, cap["lots"] * 1.5, ref_lots=1.0, ref_impact_r=0.05)
    assert past is not None and past < 0

    dead = _cell(0.02, spread=0.05, impact=None)
    assert NE.capacity_size(dead, ref_lots=1.0, ref_impact_r=0.05)["lots"] == 0.0


def test_capacity_without_a_measured_impact_reference_is_unmeasured_not_unlimited() -> None:
    row = _cell(0.20, impact=None)
    cap = NE.capacity_size(row, ref_lots=None, ref_impact_r=None)
    assert cap["status"] == NE.UNMEASURED
    assert cap["lots"] is None
    assert "not the same as unlimited" in cap["why"]
    assert NE.impact_charge(3.0, ref_lots=None, ref_impact_r=None).status == NE.UNMEASURED


def test_impact_charge_follows_the_declared_square_root_law() -> None:
    at1 = NE.impact_charge(1.0, ref_lots=1.0, ref_impact_r=0.04)
    at4 = NE.impact_charge(4.0, ref_lots=1.0, ref_impact_r=0.04)
    assert at1.value == pytest.approx(0.04)
    assert at4.value == pytest.approx(0.08)          # 4x the size, 2x the impact


# ------------------------------------------------------------------ growth governance


def test_reweighting_toward_net_never_reduces_the_total_heat() -> None:
    book = {"a": 0.10, "b": 0.06, "c": 0.04}
    rows = [_cell(0.30, key="a"), _cell(0.10, key="b"), _cell(0.02, key="c")]
    tilt = NE.net_tilt(rows)
    after = NE.reweight_preserving_heat(book, tilt)
    assert sum(after.values()) == pytest.approx(sum(book.values()), abs=1e-12)
    assert after["a"] > book["a"]                    # the best net gets MORE, not everyone less
    assert all(v >= 0 for v in after.values())
    assert set(after) == set(book)


@pytest.mark.parametrize("scores", [{}, {"a": 0.0, "b": 0.0}, {"a": float("nan")}])
def test_an_unscorable_book_is_returned_unchanged_and_never_shrunk(scores: dict) -> None:
    book = {"a": 0.12, "b": 0.08}
    after = NE.reweight_preserving_heat(book, scores)
    assert sum(after.values()) == pytest.approx(sum(book.values()), abs=1e-12)


def test_the_tilt_is_bounded_two_sided_and_never_a_veto() -> None:
    rows = [_cell(10.0, key="huge"), _cell(0.001, key="tiny"), _cell(-1.0, key="negative")]
    tilt = NE.net_tilt(rows)
    assert all(0.5 <= v <= 2.0 for v in tilt.values())
    assert max(tilt.values()) > 1.0 and min(tilt.values()) < 1.0
    assert all(v > 0 for v in tilt.values())         # nothing is ever zeroed out


# ------------------------------------------------------------------ backward attribution


def test_the_cost_model_is_judged_by_the_tape_and_an_absent_reading_is_unmeasured() -> None:
    row = _cell(0.30)
    assert NE.prediction_error(row, None)["status"] == NE.UNMEASURED
    err = NE.prediction_error(row, 0.20, realised_cost=0.05)
    assert err["status"] == NE.MEASURED
    assert err["error"] == pytest.approx(row.net - 0.20)
    assert err["direction"] == "OVER_PREDICTED"
    assert err["cost_error"] == pytest.approx(row.cost_priced - 0.05)

    assert NE.calibration([])["status"] == NE.UNMEASURED
    cal = NE.calibration([NE.prediction_error(row, 0.20), NE.prediction_error(row, 0.40)])
    assert cal["n"] == 2 and cal["status"] == NE.MEASURED
    assert math.isfinite(cal["mae"])


def test_ranking_is_by_net_and_an_unpriceable_row_sorts_last() -> None:
    rows = [_cell(0.05, key="low"), _cell(0.90, key="high"), _cell(None, key="none")]  # type: ignore[arg-type]
    assert [r.key for r in NE.rank_by_net(rows)] == ["high", "low", "none"]
