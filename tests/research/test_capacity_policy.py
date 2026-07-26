"""§39 PARITY: capacity is scored as sufficiency, not magnitude, EVERYWHERE.

Removing the flat $100k floor from the survival gate stopped the niche being excluded. It did not
make it equally prioritised, because four separate scorers still rewarded raw size. These lock the
property that actually matters -- above the headroom requirement, capacity stops being a
tiebreaker -- at the policy module AND at each of the scorers that used to carry its own constant,
since a shared helper nobody calls is how the last four copies drifted apart in the first place.
"""

from __future__ import annotations

from libs.research.capacity_policy import (
    DEFAULT_BOOK_USD,
    DEFAULT_SLEEVES,
    capacity_band,
    capacity_fit,
    capacity_required,
    niche_share,
    sleeve_equity,
)

_BOOK = DEFAULT_BOOK_USD


class TestSufficiencyNotMagnitude:
    def test_above_the_requirement_size_stops_mattering(self) -> None:
        # THE parity property: a $200k edge and a $5M edge are identical to a $50k book, because
        # capacity you cannot fill is not an advantage you own.
        assert capacity_fit(200_000.0, _BOOK) == capacity_fit(5_000_000.0, _BOOK) == 1.0

    def test_below_the_requirement_it_ramps_rather_than_cliffs(self) -> None:
        req = capacity_required(_BOOK)
        assert 0.0 < capacity_fit(req * 0.5, _BOOK) < capacity_fit(req * 0.9, _BOOK) < 1.0

    def test_the_niche_is_not_penalised_against_fund_scale(self) -> None:
        # the regression this module exists to prevent: the old scorers gave 1e9 a strictly higher
        # capacity term than a comfortably-sufficient small edge
        assert capacity_fit(300_000.0, _BOOK) >= capacity_fit(1e9, _BOOK)

    def test_fund_scale_is_discounted_but_never_excluded(self) -> None:
        # a bounded tilt is a crowding prior; an unbounded one would just mirror the old bug
        assert 0.5 <= capacity_fit(1e9, _BOOK) < 1.0

    def test_the_discount_is_floored_however_large_the_edge(self) -> None:
        assert capacity_fit(1e12, _BOOK) == capacity_fit(1e15, _BOOK)

    def test_score_is_bounded(self) -> None:
        for cap in (0.0, 1.0, 1e4, 1e6, 1e9, 1e15):
            assert 0.0 <= capacity_fit(cap, _BOOK) <= 1.0

    def test_zero_capacity_scores_zero(self) -> None:
        assert capacity_fit(0.0, _BOOK) == 0.0


class TestSleeves:
    def test_no_single_edge_is_filled_with_the_whole_book(self) -> None:
        assert sleeve_equity(50_000.0, 8) == 6_250.0

    def test_sleeving_lowers_the_requirement(self) -> None:
        # judging every candidate against the FULL book is the flat-floor bug in miniature
        assert capacity_required(_BOOK, DEFAULT_SLEEVES) < capacity_required(_BOOK, 1)

    def test_sleeve_count_is_never_zero_or_negative(self) -> None:
        assert sleeve_equity(50_000.0, 0) == sleeve_equity(50_000.0, 1) == 50_000.0
        assert sleeve_equity(50_000.0, -3) == 50_000.0


class TestBands:
    def test_an_edge_the_desk_would_be_is_unfillable(self) -> None:
        assert capacity_band(1_000.0, _BOOK, DEFAULT_SLEEVES) == "UNFILLABLE"

    def test_the_structural_advantage_band_is_reachable(self) -> None:
        assert capacity_band(120_000.0, _BOOK, DEFAULT_SLEEVES) == "NICHE"

    def test_nine_figures_is_fund_scale(self) -> None:
        assert capacity_band(5e8, _BOOK, DEFAULT_SLEEVES) == "FUND-SCALE"

    def test_the_bands_do_not_move_with_our_book(self) -> None:
        # crowding is a fact about the market. Only UNFILLABLE may depend on our size.
        for cap in (5e6, 5e7, 5e8):   # fillable by both books, so only crowding can differ
            assert capacity_band(cap, 5_000.0, 1) == capacity_band(cap, 500_000.0, 1)

    def test_niche_share_measures_the_funnel(self) -> None:
        assert niche_share([50e3, 120e3, 5e8, 6e8], _BOOK) == 0.5

    def test_niche_share_of_nothing_is_zero_not_a_crash(self) -> None:
        assert niche_share([], _BOOK) == 0.0


class TestScorersActuallyUseIt:
    """A shared policy nobody calls is how the previous four copies drifted apart."""

    def test_ev_score_no_longer_penalises_a_small_capacity_idea(self) -> None:
        from libs.research.alpha_economics import Idea, ev_score
        small = ev_score(Idea("niche", capacity_usd=200_000.0, book_usd=_BOOK))["ev"]
        huge = ev_score(Idea("fund", capacity_usd=5e6, book_usd=_BOOK))["ev"]
        assert small == huge   # identical on every other axis -> identical EV

    def test_discovery_score_no_longer_penalises_a_small_capacity_edge(self) -> None:
        from libs.discovery.objective import discovery_score
        kw = {"log_growth": 0.2, "survival_probability": 0.8,
              "diversification_contribution": 0.1, "average_correlation": 0.1,
              "failure_dependency_score": 10.0, "half_life_days": 200.0,
              "fragility_score": 20.0, "tail_risk_score": 20.0,
              "parameter_plateau_score": 70.0, "deployed_equity_usd": _BOOK}
        assert discovery_score(capacity_usd=200_000.0, **kw) == \
               discovery_score(capacity_usd=5e6, **kw)

    def test_scalability_score_is_about_our_size_not_a_funds(self) -> None:
        from libs.alpha_factory.capacity_intelligence import CapacityIntelligence
        # a thin market that still comfortably absorbs this book must not score near zero
        res = CapacityIntelligence().assess(adv_usd=5e7, edge_bps=15.0)
        assert res.scalability_score > 50.0

    def test_acceptance_no_longer_carries_its_own_flat_floor(self) -> None:
        import inspect

        from libs.discovery import factory
        src = inspect.getsource(factory)
        assert "capacity_usd >= 1e5" not in src, \
            "the flat $100k floor is back in acceptance -- §39 says capacity is a ratio"
