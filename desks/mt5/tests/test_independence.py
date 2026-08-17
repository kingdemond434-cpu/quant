"""The heat budget's breadth term was dead code. Nothing ever measured k_eff.

`heat_budget(k_eff)` scales total risk with sqrt(k_eff) so the book widens as it earns
independence. The gateway called `cap_by_heat(sleeves, equity)` with no k_eff, nothing in the
repo computed one, and so the budget returned its base 3.81% on every call forever -- a book
permanently pinned to a three-leg measurement no matter how many independent edges it earned.
A scaling term nothing supplies is a constant with extra steps.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.independence import (  # noqa: E402
    daily_returns, effective_bets, mean_pairwise_corr, measure_k_eff)

_GW = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")


def _rows(sleeve, rs, start_day=1):
    return [{"sleeve": sleeve, "r_multiple": r, "time": f"2026-08-{start_day + i:02d}T10:00:00"}
            for i, r in enumerate(rs)]


# ---------------------------------------------------------------- effective_bets

def test_independent_sleeves_count_as_themselves():
    assert effective_bets(5, 0.0) == pytest.approx(5.0)


def test_perfectly_correlated_sleeves_are_one_bet():
    assert effective_bets(5, 1.0) == pytest.approx(1.0)


def test_the_armed_gold_books_measured_correlation_reproduces_its_calibration():
    """0.165 across three legs is where _HEAT_BASE_KEFF = 2.26 came from."""
    assert effective_bets(3, 0.165) == pytest.approx(2.26, abs=0.01)


def test_k_eff_never_exceeds_the_sleeve_count():
    assert effective_bets(4, -0.3) <= 4.0


# ------------------------------------------------------------------ no zero-fill

def test_a_day_a_sleeve_did_not_trade_is_absent_not_zero():
    """THE FABRICATION THIS PREVENTS. Writing 0.0 for absent days deflates every correlation and
    manufactures diversification -- it inflated k_eff by 1.36x when it happened for real."""
    got = daily_returns(_rows("a", [1.0, -1.0]) + _rows("b", [0.5], start_day=1))
    assert set(got["a"]) == {"2026-08-01", "2026-08-02"}
    assert set(got["b"]) == {"2026-08-01"}, "an absent day was materialised"


def test_same_day_trades_in_one_sleeve_are_summed():
    rows = [{"sleeve": "a", "r_multiple": 1.0, "time": "2026-08-01T07:00:00"},
            {"sleeve": "a", "r_multiple": -0.5, "time": "2026-08-01T13:00:00"}]
    assert daily_returns(rows)["a"]["2026-08-01"] == pytest.approx(0.5)


def test_a_pair_without_enough_overlap_contributes_nothing():
    """Not a convenient zero correlation -- nothing. Below the floor the estimate is noise, and a
    noisy correlation near zero is indistinguishable from real independence, which is the error
    that raises leverage."""
    rho, pairs, _ = mean_pairwise_corr(
        {"a": {f"d{i}": 1.0 * i for i in range(5)}, "b": {f"d{i}": 1.0 * i for i in range(5)}},
        min_overlap=20)
    assert rho is None and pairs == 0


def test_only_overlapping_days_are_correlated():
    a = {f"2026-08-{i:02d}": float(i % 5) for i in range(1, 26)}
    b = dict(a)
    b["2026-09-01"] = 99.0                      # a day 'a' never traded
    rho, pairs, overlap = mean_pairwise_corr({"a": a, "b": b}, min_overlap=20)
    assert pairs == 1 and overlap == 25, "the non-overlapping day entered the correlation"


# ----------------------------------------------------------------- conservatism

def test_the_upper_bound_is_used_not_the_point_estimate():
    """Correlations rise in exactly the regime where the budget gets spent, and a sample mean is
    a point estimate from whatever regime happened to be sampled. Taking the pessimistic end is
    the difference between aggression and optimism."""
    day = lambda i: f"2026-{8 + i // 28:02d}-{1 + i % 28:02d}"                    # noqa: E731
    a = {day(i): float(i % 7) for i in range(40)}
    b = {day(i): float(i % 7) + 0.01 * (i % 3) for i in range(40)}
    rho_upper, _, _ = mean_pairwise_corr({"a": a, "b": b}, min_overlap=20)
    from mt5desk.independence import _pearson
    common = sorted(set(a) & set(b))
    point = _pearson([a[d] for d in common], [b[d] for d in common])
    assert rho_upper > point, "the point estimate was used; the interval is being ignored"


def test_fewer_than_two_sleeves_is_unmeasured_not_independent():
    """FAILS CLOSED. 'Not yet measured' must never read as 'independent' -- that is how a
    correlated book comes to size like a diversified one."""
    k, why = measure_k_eff(_rows("only", [1.0] * 40))
    assert k is None and "UNMEASURED" in why


def test_a_measured_book_reports_its_number_and_its_provenance():
    day = lambda i: f"2026-{8 + i // 28:02d}-{1 + i % 28:02d}"                    # noqa: E731
    rows = ([{"sleeve": "a", "r_multiple": float(i % 5), "time": day(i)} for i in range(40)] +
            [{"sleeve": "b", "r_multiple": float((i + 2) % 5), "time": day(i)} for i in range(40)])
    k, why = measure_k_eff(rows)
    assert k is not None and 1.0 <= k <= 2.0
    assert "rho<=" in why and "upper bound" in why


# ----------------------------------------------------------------------- wiring

def test_the_gateway_actually_measures_and_passes_k_eff():
    """THE DEFECT. cap_by_heat(sleeves, equity) with no k_eff meant heat_budget returned base on
    every call and the sqrt(k_eff) ladder never ran."""
    assert "measure_from_ledger" in _GW, "the gateway never measures independence"
    # Code lines only -- the prose above the call site quotes the old form to explain the defect.
    code = [ln.split("#")[0] for ln in _GW.splitlines()]
    calls = [ln for ln in code if "cap_by_heat(" in ln and "def " not in ln]
    assert calls, "cap_by_heat is never called in the trading path"
    for ln in calls:
        assert "k_eff" in ln, (
            f"cap_by_heat called without a breadth term -- the ladder is dead again: {ln.strip()}")


def test_the_reason_is_logged_whether_or_not_it_measured():
    """A budget that silently widened would be indistinguishable from one never measured."""
    assert "log(k_why)" in _GW or "log(f\"{k_why}" in _GW or "log(k_eff_why)" in _GW
