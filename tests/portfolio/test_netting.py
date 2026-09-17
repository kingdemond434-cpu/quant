"""Netting as an execution economy: what it must save, and what it must never quietly take.

What is pinned, and each item is a way netting could have become a risk decision by accident:

  * two sleeves pointing opposite ways net to ZERO and the ratio reads `inf` -- the whole case
    for the module, and the case a per-symbol order log cannot show;
  * BOTH contributors survive on the target. The sleeve that was right while the book was flat
    still has a row, because a netted order carries no sleeve identity at the venue and its
    forward evidence is promotion-firewall ground;
  * rounding is TOWARD ZERO, always, so the venue is never sent more than the sleeves asked for,
    and the residue that rounding removes is REPORTED rather than silently dropped;
  * `0.03 / 0.01` is 2.9999999999999996 in IEEE 754 and must still round to 0.03 -- an epsilon
    repairs the representation and can never add a whole step;
  * a missing volume step REFUSES. Netting against an assumed 0.01 at a venue that steps in 1.0
    would send a hundredth of the intended order;
  * a confidence outside [0, 1] REFUSES: above 1 it would lever a sleeve's own target inside a
    module that is not allowed to size, below 0 it would silently flip its side.
"""
from __future__ import annotations

import math

import pytest

from libs.portfolio.errors import PortfolioError
from libs.portfolio.netting import (
    NettedTarget,
    SleeveIntent,
    attribute_fill,
    net_intents,
    netting_summary,
    round_toward_zero,
)

STEPS = {"EURCHF": 0.01, "AUDCAD": 0.01, "XAUUSD": 0.01, "WHEAT": 1.0}


# ------------------------------------------------------------------------------------ the object
def test_an_intent_refuses_an_empty_name_or_symbol() -> None:
    with pytest.raises(PortfolioError):
        SleeveIntent(sleeve="", symbol="EURCHF", target_lots=1.0)
    with pytest.raises(PortfolioError):
        SleeveIntent(sleeve="a", symbol="  ", target_lots=1.0)


@pytest.mark.parametrize("confidence", [-0.001, 1.001, 2.0, float("nan"), float("inf")])
def test_an_intent_refuses_a_confidence_outside_zero_to_one(confidence: float) -> None:
    with pytest.raises(PortfolioError, match="confidence"):
        SleeveIntent(sleeve="a", symbol="EURCHF", target_lots=1.0, confidence=confidence)


def test_an_intent_refuses_a_non_finite_target() -> None:
    with pytest.raises(PortfolioError, match="target_lots"):
        SleeveIntent(sleeve="a", symbol="EURCHF", target_lots=float("nan"))


def test_confidence_scales_the_contribution_and_nothing_else() -> None:
    intent = SleeveIntent(sleeve="a", symbol="EURCHF", target_lots=0.40, confidence=0.5)
    assert intent.target_lots == 0.40          # the sleeve's own ask is preserved verbatim
    assert intent.contribution == pytest.approx(0.20)


# ---------------------------------------------------------------------------------- the netting
def test_two_opposite_intents_net_to_zero_with_an_infinite_ratio() -> None:
    targets = net_intents([
        SleeveIntent("long_sleeve", "EURCHF", 0.30),
        SleeveIntent("short_sleeve", "EURCHF", -0.30),
    ], volume_step=STEPS)
    assert len(targets) == 1
    target = targets[0]
    assert target.target_lots == 0.0
    assert target.gross_lots == pytest.approx(0.60)
    assert target.netting_ratio == math.inf
    assert target.lots_not_sent == pytest.approx(0.60)
    assert target.orders_saved == 2            # both orders avoided; the venue sees nothing


def test_both_contributors_survive_the_netting() -> None:
    """Attribution must still see the sleeve that was right while the book was flat."""
    targets = net_intents([
        SleeveIntent("long_sleeve", "EURCHF", 0.30),
        SleeveIntent("short_sleeve", "EURCHF", -0.30),
    ], volume_step=STEPS)
    contributors = targets[0].contributors
    assert [c.sleeve for c in contributors] == ["long_sleeve", "short_sleeve"]
    assert [c.target_lots for c in contributors] == [0.30, -0.30]
    assert targets[0].n_contributors == 2


def test_partial_cancellation_leaves_a_ratio_above_one() -> None:
    targets = net_intents([
        SleeveIntent("a", "EURCHF", 0.30),
        SleeveIntent("b", "EURCHF", 0.30),
        SleeveIntent("c", "EURCHF", -0.20),
    ], volume_step=STEPS)
    target = targets[0]
    assert target.target_lots == pytest.approx(0.40)
    assert target.gross_lots == pytest.approx(0.80)
    assert target.netting_ratio == pytest.approx(2.0)
    assert target.orders_saved == 2


def test_a_book_that_never_cancels_nets_at_ratio_one() -> None:
    targets = net_intents([
        SleeveIntent("a", "EURCHF", 0.30),
        SleeveIntent("b", "EURCHF", 0.20),
    ], volume_step=STEPS)
    assert targets[0].netting_ratio == pytest.approx(1.0)
    assert targets[0].lots_not_sent == pytest.approx(0.0)


def test_an_empty_symbol_has_no_motion_to_be_wasteful_with() -> None:
    """Ratio 0.0, not inf: `inf` next to a symbol nobody traded would advertise the largest
    possible saving on a row where nothing was ever at stake."""
    target = NettedTarget(symbol="EURCHF", target_lots=0.0, gross_lots=0.0)
    assert target.netting_ratio == 0.0
    assert target.orders_saved == 0


def test_targets_are_grouped_by_symbol_and_sorted() -> None:
    targets = net_intents([
        SleeveIntent("x", "XAUUSD", 0.02),
        SleeveIntent("a", "AUDCAD", 0.10),
        SleeveIntent("b", "AUDCAD", 0.10),
    ], volume_step=STEPS)
    assert [t.symbol for t in targets] == ["AUDCAD", "XAUUSD"]
    assert targets[0].target_lots == pytest.approx(0.20)


def test_confidence_weights_the_net_but_not_the_recorded_ask() -> None:
    targets = net_intents([
        SleeveIntent("sure", "EURCHF", 1.00, confidence=1.0),
        SleeveIntent("unsure", "EURCHF", -1.00, confidence=0.25),
    ], volume_step=STEPS)
    assert targets[0].target_lots == pytest.approx(0.75)
    assert targets[0].gross_lots == pytest.approx(1.25)
    assert [c.target_lots for c in targets[0].contributors] == [1.00, -1.00]


def test_a_zero_confidence_intent_still_keeps_its_row() -> None:
    targets = net_intents([
        SleeveIntent("live", "EURCHF", 0.10),
        SleeveIntent("muted", "EURCHF", 5.00, confidence=0.0),
    ], volume_step=STEPS)
    assert targets[0].target_lots == pytest.approx(0.10)
    assert targets[0].n_contributors == 2
    assert targets[0].orders_saved == 0        # only one sleeve was actually sending


# ---------------------------------------------------------------------------------- the rounding
@pytest.mark.parametrize(("lots", "step", "expected"), [
    (0.03, 0.01, 0.03),          # 0.03/0.01 == 2.9999999999999996; the epsilon repairs it
    (0.029, 0.01, 0.02),
    (-0.029, 0.01, -0.02),
    (0.009, 0.01, 0.0),
    (-0.009, 0.01, 0.0),
    (2.7, 1.0, 2.0),
    (-2.7, 1.0, -2.0),
    (0.0, 0.01, 0.0),
])
def test_rounding_is_toward_zero_at_the_venue_step(lots: float, step: float,
                                                   expected: float) -> None:
    assert round_toward_zero(lots, step) == pytest.approx(expected)


def test_rounding_never_holds_more_than_the_sleeves_asked_for() -> None:
    for thousandths in range(0, 500):
        lots = thousandths / 1000.0
        rounded = round_toward_zero(lots, 0.01)
        assert rounded <= lots + 1e-12
        assert rounded >= lots - 0.01


def test_the_epsilon_cannot_add_a_whole_step() -> None:
    assert round_toward_zero(0.0199999, 0.01) == pytest.approx(0.01)
    assert round_toward_zero(0.9999, 1.0) == 0.0


def test_the_step_residue_is_reported_not_silently_dropped() -> None:
    targets = net_intents([SleeveIntent("a", "WHEAT", 2.7)], volume_step=STEPS)
    assert targets[0].target_lots == pytest.approx(2.0)
    assert targets[0].residual_lots == pytest.approx(0.7)


@pytest.mark.parametrize("step", [0.0, -0.01, float("nan"), float("inf")])
def test_a_bad_step_refuses(step: float) -> None:
    with pytest.raises(PortfolioError):
        round_toward_zero(1.0, step)


def test_a_missing_step_refuses_rather_than_assuming_a_hundredth() -> None:
    with pytest.raises(PortfolioError, match="no volume step"):
        net_intents([SleeveIntent("a", "GBPMXN", 0.10)], volume_step=STEPS)


def test_a_single_step_may_be_given_for_every_symbol() -> None:
    targets = net_intents([SleeveIntent("a", "ANYTHING", 0.35)], volume_step=0.1)
    assert targets[0].target_lots == pytest.approx(0.3)


def test_net_intents_refuses_anything_that_is_not_an_intent() -> None:
    with pytest.raises(PortfolioError, match="SleeveIntent"):
        net_intents([{"sleeve": "a", "symbol": "EURCHF", "target_lots": 1.0}],  # type: ignore[list-item]
                    volume_step=STEPS)


# ------------------------------------------------------------------------------- the attribution
def test_a_fill_is_split_back_across_the_sleeves_that_asked_for_it() -> None:
    targets = net_intents([
        SleeveIntent("big", "EURCHF", 0.30),
        SleeveIntent("small", "EURCHF", 0.10),
    ], volume_step=STEPS)
    share = attribute_fill(targets[0], 0.40)
    assert share["big"] == pytest.approx(0.30)
    assert share["small"] == pytest.approx(0.10)
    assert sum(share.values()) == pytest.approx(0.40)


def test_attribution_keeps_each_sleeves_own_side() -> None:
    """A sleeve that asked SHORT is credited short even when the net order was long."""
    targets = net_intents([
        SleeveIntent("long_one", "EURCHF", 0.30),
        SleeveIntent("short_one", "EURCHF", -0.10),
    ], volume_step=STEPS)
    share = attribute_fill(targets[0], 0.20)
    assert share["long_one"] > 0 and share["short_one"] < 0
    assert share["long_one"] == pytest.approx(0.20 * 0.75)
    assert share["short_one"] == pytest.approx(-0.20 * 0.25)


def test_attributing_nothing_returns_nothing() -> None:
    targets = net_intents([SleeveIntent("a", "EURCHF", 0.30)], volume_step=STEPS)
    assert attribute_fill(targets[0], 0.0) == {}
    assert attribute_fill(NettedTarget("EURCHF", 0.0, 0.0), 1.0) == {}


def test_attribute_fill_refuses_a_non_finite_fill() -> None:
    targets = net_intents([SleeveIntent("a", "EURCHF", 0.30)], volume_step=STEPS)
    with pytest.raises(PortfolioError):
        attribute_fill(targets[0], float("nan"))


# ----------------------------------------------------------------------------------- the summary
def test_the_book_summary_counts_orders_and_lots_that_never_crossed() -> None:
    targets = net_intents([
        SleeveIntent("a", "EURCHF", 0.30),
        SleeveIntent("b", "EURCHF", -0.30),
        SleeveIntent("c", "AUDCAD", 0.20),
    ], volume_step=STEPS)
    summary = netting_summary(targets)
    assert summary["gross_lots"] == pytest.approx(0.80)
    assert summary["net_lots"] == pytest.approx(0.20)
    assert summary["lots_not_sent"] == pytest.approx(0.60)
    assert summary["orders_gross"] == 3.0
    assert summary["orders_saved"] == 2.0
    assert summary["netting_ratio"] == pytest.approx(4.0)


def test_an_empty_book_summarises_to_zeros_rather_than_infinities() -> None:
    summary = netting_summary(())
    assert summary["gross_lots"] == 0.0
    assert summary["netting_ratio"] == 0.0
