"""Program search must refuse future shifts and rank the actual candidate factor."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from libs.research_os import dsl as D


def frame(n=180):
    return pd.DataFrame({"close": np.arange(n, dtype=float) + 1,
                         "volume": np.arange(n, dtype=float) + 100},
                        index=pd.date_range("2026-01-01", periods=n, freq="h"))


@pytest.mark.parametrize("op", ["lag", "diff", "pct", "roll_mean", "roll_std",
                                "roll_max", "roll_min", "zscore", "decay"])
@pytest.mark.parametrize("window", [-1, 0, -1., "-1", "1", True, False, 501,
                                    float("nan"), float("inf"), ["const", -1]])
def test_every_window_operator_refuses_lookahead_and_untyped_parameters(op, window):
    with pytest.raises(D.DslError, match=r"POSITIVE|bounded"):
        D.compile_factor([op, ["col", "close"], window], frame())


@pytest.mark.parametrize("op", ["lag", "diff", "pct", "roll_mean", "roll_std",
                                "roll_max", "roll_min", "zscore", "decay"])
def test_future_data_cannot_change_a_trailing_factor_prefix(op):
    before = frame()
    after = before.copy()
    after.loc[after.index[100]:, "close"] *= 10000
    original = D.compile_factor([op, ["col", "close"], 5], before)
    changed = D.compile_factor([op, ["col", "close"], 5], after)
    pd.testing.assert_series_equal(original.iloc[:100], changed.iloc[:100])
    assert original.notna().any()


def test_rank_uses_the_named_factor_and_changes_with_primary_rank():
    primary = pd.DataFrame({"close": [2., 4.], "volume": [300., 100.]})
    a = pd.DataFrame({"close": [1., 2.], "volume": [100., 200.]})
    b = pd.DataFrame({"close": [3., 3.], "volume": [200., 300.]})
    universe = {"self": primary, "a": a, "b": b}
    assert D.compile_factor(["rank", ["col", "close"]], primary,
                            universe).tolist() == pytest.approx([2 / 3, 1])
    assert D.compile_factor(["rank", ["col", "volume"]], primary,
                            universe).tolist() == pytest.approx([1, 1 / 3])
    with pytest.raises(D.DslError, match="universe"):
        D.compile_factor(["rank", ["col", "close"]], primary)


@pytest.mark.parametrize("op,expected", [("spread", [-1., 0.]), ("add", [3., 4.]),
                                         ("mul", [2., 4.]), ("gt", [0., 0.]),
                                         ("lt", [1., 0.]), ("ratio", [.5, 1.])])
def test_binary_factor_arithmetic_has_independent_expected_values(op, expected):
    primary = frame(2)
    result = D.compile_factor([op, ["col", "close"], ["const", 2]], primary)
    assert result.tolist() == expected


def test_zero_denominator_is_missing_not_an_infinite_edge():
    primary = frame(2)
    assert D.compile_factor(["ratio", ["col", "close"], ["const", 0]], primary).isna().all()


def test_conditional_gating_preserves_both_declared_branches():
    result = D.compile_factor(["cond", ["gt", ["col", "close"], 1], 7, -2], frame(2))
    assert result.tolist() == [-2., 7.]


def test_peer_data_is_reindexed_without_borrowing_future_rows():
    primary = frame(4)
    peer = pd.DataFrame({"close": [9.]}, index=primary.index[2:3])
    result = D.compile_factor(["sym", "peer", "close"], primary, {"peer": peer})
    assert result.iloc[:2].isna().all()
    assert result.iloc[2:].eq(9).all()
    with pytest.raises(D.DslError, match="symbol"):
        D.compile_factor(["sym", "missing", "close"], primary)
    with pytest.raises(D.DslError, match="column"):
        D.compile_factor(["sym", "peer", "wrong"], primary, {"peer": peer})


def test_residual_and_session_are_nonanticipating():
    primary = frame()
    result = D.compile_factor(["resid", ["col", "close"], ["col", "volume"]], primary)
    assert result.iloc[:119].isna().all()
    assert result.iloc[119:].notna().all()
    session = D.compile_factor(["session", ["col", "close"], "overlap"], primary)
    assert session.iloc[:24].tolist() == [float(15 <= h < 17) for h in range(24)]
    with pytest.raises(D.DslError, match="session"):
        D.compile_factor(["session", ["col", "close"], "missing"], primary)


@pytest.mark.parametrize("tree", [None, [], {}, ["exec", "os"], ["col"],
                                   ["col", "close", 2], ["const", {}], ["const", 501]])
def test_invalid_programs_are_refused_before_data_is_touched(tree):
    with pytest.raises(D.DslError):
        D.compile_factor(tree, None)


def test_complexity_limits_and_missing_columns_fail_loudly():
    tree = ["col", "close"]
    for _ in range(10):
        tree = ["lag", tree, 1]
    with pytest.raises(D.DslError, match="deeper"):
        D.validate(tree)
    with pytest.raises(D.DslError, match="larger"):
        D.validate(["const", 1], seen=[D.MAX_NODES])
    with pytest.raises(D.DslError, match="column"):
        D.compile_factor(["col", "missing"], frame())
