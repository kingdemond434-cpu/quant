"""The instrument screen, and the four ways a breadth claim can be a lie.

The claim this module has to keep honest is "the mechanism generalises". It is easy to make that
claim true by accident -- by pooling the symbols the mechanism was CHOSEN on, by counting
parameterisations as breadth, or by dropping symbols that lost and calling it risk management.
Each of those has a test here.
"""
from __future__ import annotations

import numpy as np
import pytest

from libs.portfolio.symbol_breadth import (
    DEFAULT_MAX_COST_RATIO,
    MEASURED,
    UNMEASURED,
    cost_ratio,
    effective_breadth,
    screen,
)


def row(sym, n=2000, exp=0.05, sd=1.0, cost=0.08, stop=1.0):
    return {"symbol": sym, "n": n, "exp": exp, "sd": sd, "cost": cost, "stop": stop}


# ------------------------------------------------------------------------------ the ratio itself
def test_the_ratio_is_the_cost_over_the_stop() -> None:
    assert cost_ratio(0.15, 1.0) == pytest.approx(0.15)
    assert cost_ratio(2.0, 1.0) == pytest.approx(2.0)      # ADAUSD's shape: cost exceeds the bet


def test_a_missing_or_impossible_stop_is_infinite_not_zero() -> None:
    """A zero stop distance dividing into a real cost must never come out as "cheap". Returning
    0.0 there would put the worst instruments at the TOP of the screen."""
    for bad in (0.0, -1.0, float("nan")):
        assert cost_ratio(0.15, bad) == float("inf")
    assert cost_ratio(float("nan"), 1.0) == float("inf")


# ------------------------------------------------------------------- selection is never pooled in
def test_the_chosen_symbols_are_reported_apart_from_the_rest() -> None:
    """Pooling the five symbols a parameterisation was fitted on into the "out-of-sample" number
    scores the selection twice, which is the exact error this module exists to prevent."""
    rows = [row("AAA", exp=0.14), row("BBB", exp=0.14), row("CCC", exp=0.05), row("DDD", exp=0.05)]
    out = screen(rows, in_sample={"AAA", "BBB"})
    assert out["in_sample"]["exp"] == pytest.approx(0.14)
    assert out["out_of_sample"]["exp"] == pytest.approx(0.05)
    assert out["out_of_sample"]["symbols"] == 2


def test_an_all_in_sample_screen_refuses_to_report_an_out_of_sample_verdict() -> None:
    out = screen([row("AAA"), row("BBB")], in_sample={"AAA", "BBB"})
    assert out["out_of_sample"]["status"] == UNMEASURED
    assert out["in_sample"]["status"] == MEASURED


# ------------------------------------------------------------- the screen is ex ante, not a filter
def test_a_losing_symbol_the_desk_CAN_pay_for_is_kept() -> None:
    """The screen may only drop instruments on cost. Dropping them on outcome would be a second
    pass of selection wearing a risk-management hat."""
    out = screen([row("WINNER", exp=+0.20), row("LOSER", exp=-0.20)])
    assert {r["symbol"] for r in out["kept"]} == {"WINNER", "LOSER"}
    assert out["out_of_sample"]["exp"] == pytest.approx(0.0)


def test_a_winning_symbol_the_desk_CANNOT_pay_for_is_dropped() -> None:
    out = screen([row("CHEAP", exp=0.05), row("DEAR", exp=+2.0, cost=3.0, stop=1.0)])
    assert [r["symbol"] for r in out["kept"]] == ["CHEAP"]
    assert out["priced_out"][0]["symbol"] == "DEAR"
    assert "cannot pay" in out["priced_out"][0]["why"]


def test_the_ADAUSD_shape_is_priced_out_at_every_sane_threshold() -> None:
    """cost/stop = 1190%: the round trip is twelve times the thing being bet on."""
    out = screen([row("ADAUSD", exp=-8.29, cost=11.9, stop=1.0)], max_cost_ratio=0.95)
    assert not out["kept"]
    assert out["priced_out"][0]["cost_ratio"] == pytest.approx(11.9)


def test_a_thin_symbol_is_neither_kept_nor_blamed_on_cost() -> None:
    out = screen([row("THIN", n=12)])
    assert not out["kept"] and not out["priced_out"]
    assert out["thin"][0]["why"].startswith("12 trades")


# ------------------------------------------------------------------------------ effective breadth
def test_identical_sleeves_are_worth_one_bet() -> None:
    assert effective_breadth(np.ones((5, 5))) == pytest.approx(1.0)


def test_independent_sleeves_are_worth_their_count() -> None:
    assert effective_breadth(np.eye(7)) == pytest.approx(7.0)


def test_three_parameterisations_of_one_signal_are_not_three_bets() -> None:
    """MEASURED on the box: `X.asia`, `X.asia#rr=1.5` and `X.asia#rr=2.5` correlate at 0.91-0.96,
    because they are one entry with three targets. A breadth number that called them 3 would have
    told the allocator this book was three times as diversified as it is."""
    c = np.array([[1.0, 0.95, 0.93], [0.95, 1.0, 0.91], [0.93, 0.91, 1.0]])
    assert effective_breadth(c) < 1.2


def test_a_mean_correlation_OVERSTATES_breadth_and_the_real_matrix_is_the_bar() -> None:
    """The screened 16-symbol book measured mean pairwise rho = 0.072 and k_eff = 13.26 on
    2026-09-08. Flat-filling that mean gives 14.85 -- 1.6 bets of breadth the book does not have.

    Equicorrelation is the MOST diversifying arrangement of a given average, so summarising a
    book by its mean rho always flatters it; the missing bets are the JPY crosses, which cluster
    at rho up to 0.40 while the average stays low. Anything sizing on the mean is sizing on a
    book that does not exist."""
    n = 16
    flat = np.full((n, n), 0.072)
    np.fill_diagonal(flat, 1.0)
    assert effective_breadth(flat) == pytest.approx(14.85, abs=0.15)

    # a cluster of 5 at 0.40 inside an otherwise-0.03 book: same order of mean, fewer real bets
    c = np.full((n, n), 0.03)
    c[:5, :5] = 0.40
    np.fill_diagonal(c, 1.0)
    assert effective_breadth(c) < effective_breadth(flat)


def test_a_malformed_matrix_is_nan_rather_than_a_confident_number() -> None:
    assert np.isnan(effective_breadth(np.zeros((0, 0))))
    assert np.isnan(effective_breadth(np.array([1.0, 2.0])))


# --------------------------------------------------------------------------------- the default
def test_the_default_threshold_is_the_one_that_was_measured() -> None:
    assert DEFAULT_MAX_COST_RATIO == 0.15


def test_the_pooled_t_statistic_is_a_real_one() -> None:
    """Two symbols, 5000 trades each, exp +0.05 with sd 1.0: se = 1/sqrt(10000) = 0.01, t = 5."""
    out = screen([row("A", n=5000, exp=0.05, sd=1.0), row("B", n=5000, exp=0.05, sd=1.0)])
    assert out["out_of_sample"]["t"] == pytest.approx(5.0, rel=1e-3)
    lo, hi = out["out_of_sample"]["ci95"]
    assert lo == pytest.approx(0.05 - 1.96 * 0.01, rel=1e-3)
    assert hi == pytest.approx(0.05 + 1.96 * 0.01, rel=1e-3)
