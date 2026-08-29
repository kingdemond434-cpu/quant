"""The schema's whole value is that a coordinate names a CAUSE, not a formula."""
from __future__ import annotations

from libs.research.alpha_schema import (
    EVENTS,
    Coordinate,
    RegionStat,
    coverage,
    describe,
    enumerate_space,
    space_size,
)


def test_every_event_names_a_payer_and_a_falsifier() -> None:
    """An event without a payer is a chart pattern, and `economic_prior` rejects it correctly.

    This is the invariant the whole module exists to hold: 85% of this desk's docket was
    price-shape primitives, and every one of the 816 gate-1 rejections came from that family.
    A coordinate must arrive already answering the question that gate asks.
    """
    for name, ev in EVENTS.items():
        assert ev.get("payer"), f"{name} has no payer"
        assert ev.get("mechanism"), f"{name} has no mechanism"
        assert ev.get("falsifier"), f"{name} has no falsifier"
        assert ev.get("evidence"), f"{name} cites no evidence"
        # A payer must be a counterparty, not a restatement of the price move.
        assert len(ev["payer"].split()) >= 3, f"{name} payer is too vague to attack"


def test_coordinates_are_economic_prior_ready() -> None:
    for coord in enumerate_space()[:50]:
        assert coord.is_named()
        assert describe(coord)["economic_prior_ready"] is True
        assert describe(coord)["payer"] != "UNKNOWN"


def test_unknown_event_is_not_prior_ready() -> None:
    """A coordinate invented outside the registry must NOT claim a mechanism it cannot name."""
    bogus = Coordinate("price_goes_up", "asia_session", "persistence", "continuation", "1h")
    assert bogus.is_named() is False
    assert describe(bogus)["economic_prior_ready"] is False
    assert describe(bogus)["payer"] == "UNKNOWN"


def test_space_is_enumerable_and_consistent() -> None:
    space = enumerate_space()
    assert len(space) == space_size()
    assert len({c.key() for c in space}) == len(space), "coordinates must be unique"


def test_coverage_counts_never_tried_as_the_headline() -> None:
    """Unvisited regions are where an uncorrelated edge can still come from."""
    rep = coverage({})
    assert rep.visited == 0
    assert rep.unvisited == space_size()
    assert rep.never_tried, "an empty desk has everything left to try"


def test_coverage_separates_productive_from_barren() -> None:
    good = "fx_fixing_flow|asia_session|abnormal_magnitude|reversal|15m"
    bad = "volatility_shock|ranging|persistence|continuation|5m"
    thin = "carry_rollover|trending|persistence|continuation|1d"
    stats = {
        good: RegionStat(good, searched=12, survived=3),
        bad: RegionStat(bad, searched=40, survived=0),
        # too few attempts to call barren -- absence of evidence is not evidence of absence
        thin: RegionStat(thin, searched=3, survived=0),
    }
    rep = coverage(stats)
    assert good in rep.productive
    assert bad in rep.barren
    assert thin not in rep.barren, "3 attempts is not enough to declare a region barren"
    assert rep.visited == 3


def test_yield_rate_is_safe_on_empty_regions() -> None:
    assert RegionStat("x").yield_rate == 0.0
    assert RegionStat("x", searched=4, survived=1).yield_rate == 0.25


def test_the_bar_does_not_move_with_sweep_size() -> None:
    """BOTH inputs to the deflated-Sharpe hurdle must be constants.

    Pinning the trial count alone did NOT fix the bar: measured 2026-08-29 with trials already at
    597, sr0 still rose to 2.4523 because the hurdle also scales with the Sharpe DISPERSION of
    whatever else is in the batch (0.0149 at 460 cells, 0.6238 at 1,985). Same candidate, same
    policy, a bar four times higher for being scheduled into a bigger sweep -- the same defect
    through a second door.
    """
    from desks.mt5.research.gate_policy import (  # type: ignore[import-not-found]
        FIXED_VARIANCE_OF_SHARPES,
        charged_trial_count,
    )

    from libs.validation.dsr import expected_max_sharpe

    trials, _basis = charged_trial_count(9999, None, "unmeasurable")
    bar = expected_max_sharpe(trials, float(FIXED_VARIANCE_OF_SHARPES))
    # identical for every sweep size, because neither input depends on the batch
    for cells in (17, 146, 460, 1985, 8375, 99_999):
        t2, _ = charged_trial_count(cells, float(cells) * 0.9,
                                    "null_calibrated_participation_ratio")
        assert expected_max_sharpe(t2, float(FIXED_VARIANCE_OF_SHARPES)) == bar
    assert round(bar, 4) == 0.3786
