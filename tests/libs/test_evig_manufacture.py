"""EVIG and proprietary-data manufacturing -- the two Tier-1 levers with no code behind them.

EVIG was GPT's own top correction: "don't optimize for hypotheses/day, optimize for Expected
Validated Information Gain -- one brilliant hypothesis worth 100 mediocre ones should consume the
compute." Without it a funnel producing 20,000 ideas/day hands L4 whatever survives the filters in
ARRIVAL ORDER, and L4 capacity is the scarcest thing the desk has.

MANUFACTURING is the largest lever by the desk's own numbers: owned order books score 1.03 on its
information-advantage ranking and every other source 0.37 or below. The gap is not predictive
power -- funding scores higher there -- it is REPLICATION DIFFICULTY.
"""

from __future__ import annotations

import pytest

from libs.hypmax.evig import EVIG_FLOOR, evig, information_gain, rank_by_evig
from libs.hypmax.manufacture import (
    MODES,
    ManufactureSpec,
    propose_from_owned,
    reverse_engineering_cost,
    score_spec,
)

# ------------------------------------------------------------------ EVIG


def test_information_gain_peaks_at_a_coin_flip() -> None:
    """The term everyone omits. A test certain to CONFIRM teaches as little as one certain to
    fail -- and the confirming one is seductive because it looks like productivity."""
    assert information_gain(0.5) == pytest.approx(1.0)
    assert information_gain(0.99) < 0.1
    assert information_gain(0.01) < 0.1
    assert information_gain(0.5) > information_gain(0.8) > information_gain(0.95)


def test_a_safe_restatement_of_the_deployed_edge_ranks_LAST() -> None:
    """THE BEHAVIOUR THAT MATTERS. P(validate)=0.95 on public data is a research programme
    congratulating itself, and a volume-ranked funnel would spend L4 on it first."""
    ranked = rank_by_evig([
        {"name": "moat", "p_validate": 0.20, "moat_advantage": 1.03},
        {"name": "safe restatement", "p_validate": 0.95, "moat_advantage": 0.06},
    ])
    assert ranked[0]["name"] == "moat"
    assert ranked[-1]["name"] == "safe restatement"


def test_moat_advantage_beats_a_higher_validation_probability() -> None:
    """An edge on public data is one everyone can find, and therefore already priced."""
    ranked = rank_by_evig([
        {"name": "public", "p_validate": 0.35, "moat_advantage": 0.06},
        {"name": "owned", "p_validate": 0.20, "moat_advantage": 1.03},
    ])
    assert ranked[0]["name"] == "owned"


def test_any_zero_term_zeroes_the_score() -> None:
    """Multiplicative by design: an additive score would let a strong moat term rescue a
    hypothesis that cannot validate, which is what fills L4 with expensive nothing."""
    assert evig(p_validate=0.0, moat_advantage=1.03).evig == 0.0
    assert evig(p_validate=0.5, moat_advantage=0.0).evig == 0.0


def test_cost_is_a_denominator() -> None:
    cheap = evig(p_validate=0.3, moat_advantage=1.0, cost=1.0).evig
    dear = evig(p_validate=0.3, moat_advantage=1.0, cost=8.0).evig
    assert cheap > dear * 7


def test_unscored_candidates_never_jump_the_queue() -> None:
    """A REAL BUG THIS SUITE CAUGHT. The first version gave unscored candidates neutral priors
    (p=0.5, moat=0.5) and scored them 0.25 -- above a measured moat candidate at 0.149. Ignorance
    outranked evidence, so the funnel would have spent its scarcest resource on whatever nobody
    had assessed."""
    ranked = rank_by_evig([
        {"name": "unscored"},
        {"name": "measured moat", "p_validate": 0.20, "moat_advantage": 1.03},
    ])
    assert ranked[0]["name"] == "measured moat"
    assert ranked[-1]["evig_scored"] is False


def test_unscored_candidates_are_not_buried_either() -> None:
    """The mirror error. The desk's honest base rate is 0/420, so a truthful default prior would
    defer every unscored candidate permanently -- and a ranking that buries things IS a filter,
    which this has no authority to be."""
    ranked = rank_by_evig([{"name": "unscored"}])
    assert len(ranked) == 1
    assert "evig" not in ranked[0], "it is listed, not scored -- the honest representation"
    assert "needs" in ranked[0]["evig_note"]


def test_below_floor_is_deferred_not_rejected() -> None:
    s = evig(p_validate=0.001, moat_advantage=0.01)
    assert s.worth_compute is False
    assert "DEFERRED, not rejected" in s.note
    assert s.evig < EVIG_FLOOR


# ------------------------------------------------------------------ manufacturing


def test_collection_scores_far_below_every_manufacturing_mode() -> None:
    """The distinction the whole module exists for: downloading a public endpoint yields a
    dataset a competitor rebuilds in an afternoon."""
    collect = MODES["COLLECT"][0]
    for mode, (score, _) in MODES.items():
        if mode != "COLLECT":
            assert score > collect * 10, mode


def test_a_public_collector_is_warned_about_explicitly() -> None:
    d = score_spec(ManufactureSpec("public_ohlcv", "COLLECT", ("exchange_api",)))
    assert "COLLECTION IS NOT MANUFACTURING" in d["warning"]
    assert d["moat_per_day"] < 0.1


def test_time_accruing_data_is_worth_three_times_more() -> None:
    """The only barrier money cannot cross: a rival with unlimited capital still cannot buy last
    month's order book if nobody recorded it."""
    a = reverse_engineering_cost(ManufactureSpec("x", "OBSERVE", ("v",), time_accruing=True))
    b = reverse_engineering_cost(ManufactureSpec("x", "OBSERVE", ("v",), time_accruing=False))
    assert a == pytest.approx(b * 3.0)


def test_time_accruing_specs_carry_an_urgency_note() -> None:
    d = score_spec(ManufactureSpec("x", "OBSERVE", ("v",), time_accruing=True))
    assert "permanently lost" in d["urgency"]


def test_fusion_depth_compounds_rather_than_adds() -> None:
    """A competitor needs ALL the inputs, so each one multiplies the work."""
    one = reverse_engineering_cost(ManufactureSpec("x", "FUSE", ("a",)))
    three = reverse_engineering_cost(ManufactureSpec("x", "FUSE", ("a", "b", "c")))
    assert three > one


def test_every_proposal_is_buildable_from_data_already_owned() -> None:
    """Proposing exotic acquisitions while an un-replicable asset sits at 0.4% exploitation
    would be the expensive way to avoid the obvious."""
    owned = {"moat_depth", "moat_trades", "funding_history", "venue_divergence"}
    specs = propose_from_owned()
    assert specs
    for s in specs:
        assert set(s.inputs) <= owned, f"{s.name} needs data the desk does not hold: {s.inputs}"
        assert s.mode.upper() != "COLLECT"


def test_the_top_proposal_is_the_desks_own_number_one_blind_spot() -> None:
    """M_LIQUIDITY_WITHDRAWAL: advantage 1.03 at 0.4% coverage, zero mechanisms tested. If the
    ranking pointed anywhere else it would be disagreeing with the desk's own measurement."""
    ranked = sorted((score_spec(s) for s in propose_from_owned()),
                    key=lambda d: -d["moat_per_day"])
    assert "liquidity_withdrawal" in ranked[0]["name"] or "replenishment" in ranked[0]["name"]


def test_every_proposal_accrues_with_calendar_time() -> None:
    """Which is why delay is the one cost that cannot be recovered later."""
    assert all(s.time_accruing for s in propose_from_owned())
