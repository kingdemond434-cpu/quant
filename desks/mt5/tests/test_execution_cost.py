"""Execution cost as an allocator input -- and the four refusals that keep it honest.

THE DEFECT IT WAS BUILT FOR. `pf_allocator` handed every sleeve the literal `cost_r=0.05` -- one
constant for a session breakout on EURZAR filling at 01:00 and for a gold bracket on an
administered spread -- while `research/cost_surface.py` had already measured that the pooled
scalar those returns were charged at is 6.16x too small on USDZAR's own fill bars, on a LIVE
CERTIFIED sleeve.

THE DEFECT IT FOUND, which is worse. Wiring the correction naively priced 28 sleeves and made
every one of them 11-16x more expensive. Checking the inputs first showed why that was wrong:

    * 23 of 195 symbols carry `median_spread_pts = 0.0` -- the registry says they are free
    * GBPJPY carries 1.0 pt against measured hourly medians of 13-50 and a
      `spread_pts_at_collection` of 7.0 -- three numbers, one field, no agreement
    * 241 of 251 symbols have NO `_provenance` entry for `median_spread_pts` at all

`universe_registry.py` already documents the cause: three producers write that field with three
different meanings, and a point-in-time `symbol_info.spread` snapshot is not a median. So the
ratio against it is not a cost error, it is two different quantities divided -- and applying it
would have shifted 28 posterior means down on a producer inconsistency.

WHAT SHIPPED FIRST WAS THE WIRING PLUS THE REFUSAL: on the data as it stood the instrument
priced ZERO of 76 sleeves and said so, which was the measurement.

THEN THE BLOCKER WAS REPAIRED. `scripts/repair_universe_spreads.py` recomputes
`median_spread_pts` from each symbol's own H1 spread column -- the value was on disk the whole
time; EURUSD's registry said 0.0 and its own bars said 12.0 -- and stamps the provenance. With
the registry read LIVE as the denominator rather than the surface's build-time snapshot, 12
sleeves now price, and the true error on the priceable live book is SMALL:

    GBPJPY_asia        1.15x     USDJPY_* / EURGBP   1.00x      the CHF crosses   0.53-0.65x

which is the corrective that matters: the 11-16x under-charges the first naive wiring produced
were the broken registry, not the market. Refusing them was right, and repairing the input --
rather than tuning the instrument -- is what turned the refusal into a measurement.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio.execution_cost import (  # noqa: E402
    BASE_COST_R,
    MAX_RATIO,
    MEASURED,
    REGISTRY_DEFECT,
    UNMEASURED,
    cost_ratio,
    costs_for,
    fill_hour,
)

#: A symbol whose spread the registry CAN attribute, priced 3x higher at its own fill hour than
#: the pooled number the replay charged.
GOOD_SURFACE = {"symbols": {"EURZAR": {
    "pooled_median_spread_pts": 300.0,
    "administered": "False",
    "hours": {str(h): {"status": MEASURED, "p50": (900.0 if h == 0 else 300.0)}
              for h in range(24)},
}}}
GOOD_REGISTRY = {"EURZAR": {"median_spread_pts": 300.0,
                            "_provenance": {"median_spread_pts": {"source": "realized_fills"}}}}


def _sleeve(name: str = "EURZAR_overnight_gap_decay_asia", symbol: str = "EURZAR"):
    return [{"name": name, "symbol": symbol, "selector": name}]


# --------------------------------------------------------------------------------- the fill hour
def test_the_fill_hour_comes_from_the_session_token_and_is_never_guessed() -> None:
    assert fill_hour("asia")[0] == 1
    assert fill_hour(None, "EURZAR_overnight_gap_decay_asia")[0] == 0   # 'overnight' wins, first
    assert fill_hour("london_am")[0] == 8
    h, why = fill_hour("something_unnamed")
    assert h is None and "unpriced" in why


def test_an_unknown_fill_hour_prices_nothing() -> None:
    """A guessed hour prices the sleeve at an hour it does not trade and produces a confident
    correction in an arbitrary direction. `cost_surface.spread_pts` refuses for the same reason."""
    d = costs_for(_sleeve("EURZAR_mystery", "EURZAR"), GOOD_SURFACE, registry=GOOD_REGISTRY)
    row = d["sleeves"]["EURZAR_mystery"]
    assert row["source"] == UNMEASURED
    assert row["cost_bias_r"] == 0.0


# ------------------------------------------------------------------------------- it does its job
def test_a_priceable_sleeve_is_charged_what_its_own_fill_hour_costs() -> None:
    d = costs_for(_sleeve(), GOOD_SURFACE, registry=GOOD_REGISTRY)
    row = d["sleeves"]["EURZAR_overnight_gap_decay_asia"]
    assert row["source"] == MEASURED
    assert row["ratio"] == pytest.approx(3.0)                      # 900 / 300 at hour 00
    assert row["cost_bias_r"] == pytest.approx(BASE_COST_R * 2.0)  # base * (ratio - 1)
    assert row["cost_r"] == pytest.approx(BASE_COST_R * 3.0)       # uncertainty scales too
    assert d["summary"]["n_undercharged"] == 1


def test_the_applied_ratio_is_clipped_and_the_raw_one_is_reported() -> None:
    """The RATIO is measured on both sides; the BASE is a desk-wide scalar nobody measured per
    sleeve. Multiplying a measured 12.8 by an unmeasured base produces a correction larger than
    most of this desk's edges on the strength of the unmeasured half."""
    s = {"symbols": {"EURZAR": {**GOOD_SURFACE["symbols"]["EURZAR"],
                                "hours": {str(h): {"status": MEASURED,
                                                   "p50": (3900.0 if h == 0 else 300.0)}
                                          for h in range(24)}}}}
    row = costs_for(_sleeve(), s, registry=GOOD_REGISTRY)["sleeves"][
        "EURZAR_overnight_gap_decay_asia"]
    assert row["ratio_raw"] == pytest.approx(13.0)
    assert row["ratio"] == pytest.approx(MAX_RATIO)
    assert row["clipped"] is True
    assert row["cost_bias_r"] == pytest.approx(BASE_COST_R * (MAX_RATIO - 1.0))


def test_an_over_charged_sleeve_is_reported_and_never_credited() -> None:
    """Raising a sleeve's mean on the strength of a cost model is sizing up on an assumption.
    Correcting an over-charge belongs in the replay, at source."""
    s = {"symbols": {"EURZAR": {**GOOD_SURFACE["symbols"]["EURZAR"],
                                "hours": {str(h): {"status": MEASURED, "p50": 150.0}
                                          for h in range(24)}}}}
    row = costs_for(_sleeve(), s, registry=GOOD_REGISTRY)["sleeves"][
        "EURZAR_overnight_gap_decay_asia"]
    assert row["ratio"] == pytest.approx(0.5)
    assert row["cost_bias_r"] == 0.0, "an over-charge must never become a credit"
    assert costs_for(_sleeve(), s, registry=GOOD_REGISTRY)["summary"]["n_overcharged"] == 1


# ------------------------------------------------------------------------- the four refusals
def test_a_zero_registry_spread_is_a_defect_not_a_free_instrument() -> None:
    """23 of 195 symbols on this desk read 0.0. `universe_registry` already flags them: '0 while
    this desk's OWN fills measured a positive spread'."""
    reg = {"EURZAR": {"median_spread_pts": 0.0,
                      "_provenance": {"median_spread_pts": {"source": "realized_fills"}}}}
    row = costs_for(_sleeve(), GOOD_SURFACE, registry=reg)["sleeves"][
        "EURZAR_overnight_gap_decay_asia"]
    assert row["source"] == REGISTRY_DEFECT
    assert row["cost_bias_r"] == 0.0
    assert "not a free instrument" in row["why"]


def test_the_denominator_is_todays_registry_not_the_surfaces_snapshot() -> None:
    """`cost_surface` copies `pooled_median_spread_pts` out of the registry AT BUILD TIME, so the
    surface on disk carries whatever the registry said the day it was built.

    THIS COST A WHOLE REPAIR ITS EFFECT. On 2026-09-07 the registry's spreads were recomputed from
    the H1 bars for 27 symbols, and every ratio kept comparing against the pre-repair snapshot --
    the correction was invisible and the instrument still priced zero sleeves. The question is
    "how wrong is the charge TODAY", so today's registry is the only correct denominator.
    """
    stale = {"symbols": {"EURZAR": {**GOOD_SURFACE["symbols"]["EURZAR"],
                                    "pooled_median_spread_pts": 100.0}}}   # the old, wrong value
    reg = {"EURZAR": {"median_spread_pts": 300.0,                          # today's, repaired
                      "_provenance": {"median_spread_pts": {"source": "h1_spread_median"}}}}
    row = costs_for(_sleeve(), stale, registry=reg)["sleeves"][
        "EURZAR_overnight_gap_decay_asia"]
    assert row["pooled_spread_pts"] == pytest.approx(300.0)
    assert row["pooled_source"] == "registry (live)"
    assert row["ratio"] == pytest.approx(3.0)      # 900 / 300, not 900 / 100


def test_the_snapshot_is_the_fallback_when_the_registry_cannot_answer() -> None:
    """A registry row with no spread at all still lets the surface's copy stand, so a host with a
    partial registry degrades rather than losing the measurement entirely."""
    reg = {"EURZAR": {"_provenance": {"median_spread_pts": {"source": "realized_fills"}}}}
    row = costs_for(_sleeve(), GOOD_SURFACE, registry=reg)["sleeves"][
        "EURZAR_overnight_gap_decay_asia"]
    assert row["pooled_source"] == "cost surface snapshot"
    assert row["ratio"] == pytest.approx(3.0)


def test_a_pooled_scalar_below_every_measured_hour_is_a_scale_flip() -> None:
    """GBPJPY: 1.0 pt registry against 13-50 pts measured. A median cannot sit under every value
    it is the median of, so the two numbers are not the same quantity -- and reading it as a 15x
    under-charge on a MAJOR cross flatly contradicts `cost_surface`'s own finding that the error
    concentrates in the exotics while the majors return clean."""
    s = {"symbols": {"GBPJPY": {"pooled_median_spread_pts": 1.0,
                                "hours": {str(h): {"status": MEASURED, "p50": 15.0}
                                          for h in range(24)}}}}
    reg = {"GBPJPY": {"_provenance": {"median_spread_pts": {"source": "realized_fills"}}}}
    row = costs_for(_sleeve("GBPJPY_asia", "GBPJPY"), s, registry=reg)["sleeves"]["GBPJPY_asia"]
    assert row["source"] == REGISTRY_DEFECT
    assert row["cost_bias_r"] == 0.0
    assert "scale flip" in row["why"]


def test_no_spread_provenance_means_no_correction() -> None:
    """THE REFUSAL THAT ACTUALLY BINDS ON THIS DESK. 241 of 251 symbols carry no `_provenance`
    entry for `median_spread_pts`, so the number the replay charged cannot be attributed to a
    producer -- and `universe_registry` documents three producers writing it with three different
    meanings. Without provenance the ratio is two different quantities divided."""
    row = costs_for(_sleeve(), GOOD_SURFACE, registry={"EURZAR": {"median_spread_pts": 300.0}}
                    )["sleeves"]["EURZAR_overnight_gap_decay_asia"]
    assert row["source"] == UNMEASURED
    assert row["cost_bias_r"] == 0.0
    assert "NO provenance" in row["why"]


def test_an_unreadable_registry_corrects_nothing() -> None:
    """The conservative direction: no registry is 'no provenance for anything', not 'trust it'."""
    row = costs_for(_sleeve(), GOOD_SURFACE, registry={})["sleeves"][
        "EURZAR_overnight_gap_decay_asia"]
    assert row["cost_bias_r"] == 0.0


def test_omitting_the_registry_entirely_keeps_the_old_ungated_behaviour() -> None:
    """`registry=None` means the caller is not running the provenance gate at all -- used by the
    diagnostic that MEASURES how much the gate is refusing."""
    row = costs_for(_sleeve(), GOOD_SURFACE)["sleeves"]["EURZAR_overnight_gap_decay_asia"]
    assert row["source"] == MEASURED


def test_an_unmeasured_hour_prices_nothing() -> None:
    s = {"symbols": {"EURZAR": {**GOOD_SURFACE["symbols"]["EURZAR"],
                                "hours": {"0": {"status": UNMEASURED, "n_bars": 12}}}}}
    row = costs_for(_sleeve(), s, registry=GOOD_REGISTRY)["sleeves"][
        "EURZAR_overnight_gap_decay_asia"]
    assert row["cost_bias_r"] == 0.0


def test_no_surface_at_all_prices_nothing() -> None:
    r, why, _ = cost_ratio(None, "EURZAR", 0)
    assert r is None and "no cost surface" in why


# ------------------------------------------------------------------- the state of THIS desk
def test_the_summary_counts_the_gap_rather_than_hiding_it() -> None:
    """A run that prices three of sixty has not measured execution, it has measured three
    sleeves. The COUNT is what decides whether the instrument is working."""
    d = costs_for(_sleeve(), GOOD_SURFACE, registry={"EURZAR": {}})
    s = d["summary"]
    assert s["n_sleeves"] == 1 and s["n_measured"] == 0 and s["n_unpriced"] == 1
    assert s["n_no_spread_provenance"] == 1
    assert "UNMEASURED" in s["verdict"]


def test_the_allocator_carries_a_cost_bias_field_and_defaults_it_to_zero() -> None:
    """The wire between this module and the growth arithmetic. Zero is 'unpriced', never 'cheap'."""
    import numpy as np

    from libs.portfolio.robust_elog import SleeveEvidence
    e = SleeveEvidence(name="x", daily_r=np.zeros(10))
    assert e.cost_bias_r == 0.0
    assert SleeveEvidence(name="y", daily_r=np.zeros(10), cost_bias_r=0.2).cost_bias_r == 0.2


def test_a_cost_bias_lowers_the_posterior_mean_and_can_unfund_a_sleeve() -> None:
    """AUTHORITY-BEARING, in one assertion. There is no rule about spreads and no veto: the mean
    simply gets the right number, and an optimiser maximising E[log W] stops funding a sleeve
    whose edge does not survive its own fill hour."""
    import numpy as np

    from libs.portfolio.robust_elog import SleeveEvidence, WorldConfig, sample_worlds
    rng = np.random.default_rng(0)
    r = rng.normal(0.05, 1.0, size=600)
    cfg = WorldConfig(n_worlds=64, n_rows=250, seed=1)
    cheap = [SleeveEvidence(name="a", daily_r=r, cost_r=0.05),
             SleeveEvidence(name="b", daily_r=r, cost_r=0.05)]
    dear = [SleeveEvidence(name="a", daily_r=r, cost_r=0.05, cost_bias_r=0.30),
            SleeveEvidence(name="b", daily_r=r, cost_r=0.05)]
    w_cheap = sample_worlds(cheap, cfg)
    w_dear = sample_worlds(dear, cfg)
    # sleeve "a" must be strictly worse once its true cost is charged; "b" is untouched
    assert w_dear.r[:, :, 0].mean() < w_cheap.r[:, :, 0].mean()
    assert w_dear.r[:, :, 1].mean() == pytest.approx(w_cheap.r[:, :, 1].mean(), abs=1e-6)
