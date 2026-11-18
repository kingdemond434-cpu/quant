"""The published-formula operators, each pinned against a value computed BY HAND.

Every expected number below is worked out on paper from the operator's published definition
(GTJA-191's appendix; Qlib's `ops.py` / `rolling.pyx`), never by calling the code under test.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from libs.research import formula_ops as fo

IDX = pd.date_range("2024-01-01", periods=4, freq="h", tz="UTC")


def _panel(*cols: list[float], names: str = "ABCDEFG") -> pd.DataFrame:
    return pd.DataFrame({names[i]: c for i, c in enumerate(cols)}, index=IDX[:len(cols[0])],
                        dtype=float)


def _one(x: list[float]) -> dict[str, pd.DataFrame]:
    p = _panel(x)
    return {"open": p, "high": p, "low": p, "close": p, "volume": p}


def _g(text: str, x: list[float]) -> list[float]:
    return fo.Evaluator(_one(x), "gtja").evaluate(text)["A"].tolist()


def _q(text: str, x: list[float]) -> list[float]:
    return fo.Evaluator(_one(x), "qlib").evaluate(text)["A"].tolist()


def _same(got: list[float], want: list[float]) -> None:
    assert len(got) == len(want)
    for g, w in zip(got, want, strict=True):
        if isinstance(w, float) and math.isnan(w):
            assert math.isnan(g), (got, want)
        else:
            assert g == pytest.approx(w, abs=1e-12), (got, want)


NAN = float("nan")


# ---------------------------------------------------------------- the parser
def test_precedence_and_associativity() -> None:
    _same(_g("1+2*3^2", [1.0, 2, 3]), [19.0] * 3)
    _same(_g("2^3^2", [1.0, 2, 3]), [512.0] * 3)          # right-associative
    _same(_g("-2^2", [1.0, 2, 3]), [-4.0] * 3)            # unary minus below ^
    _same(_g("(1<2)?5:7", [1.0, 2, 3]), [5.0] * 3)        # ternary, lowest
    _same(_g("CLOSE=2", [1.0, 2, 3]), [0.0, 1.0, 0.0])    # GTJA's `=` is equality


def test_unbalanced_text_is_a_formula_error() -> None:
    with pytest.raises(fo.FormulaError):
        fo.parse("MEAN(CLOSE,5")


# ---------------------------------------------------------------- GTJA time-series operators
def test_gtja_delay_delta_and_one_argument_delay() -> None:
    _same(_g("DELAY(CLOSE,2)", [1.0, 2, 4, 7]), [NAN, NAN, 1, 2])
    _same(_g("DELAY(CLOSE)", [1.0, 2, 4, 7]), [NAN, 1, 2, 4])
    _same(_g("DELTA(CLOSE,1)", [1.0, 2, 4, 7]), [NAN, 1, 2, 3])


def test_gtja_windows_need_a_full_window() -> None:
    _same(_g("SUM(CLOSE,3)", [1.0, 2, 4, 7]), [NAN, NAN, 7, 13])
    _same(_g("MEAN(CLOSE,2)", [1.0, 2, 4, 7]), [NAN, 1.5, 3, 5.5])
    # sample std of (2, 4) = sqrt(2); of (4, 7) = sqrt(4.5)
    _same(_g("STD(CLOSE,2)", [1.0, 2, 4, 7]), [NAN, math.sqrt(0.5), math.sqrt(2), math.sqrt(4.5)])
    _same(_g("TSMAX(CLOSE,2)", [3.0, 1, 4, 2]), [NAN, 3, 4, 4])
    _same(_g("TSMIN(CLOSE,2)", [3.0, 1, 4, 2]), [NAN, 1, 1, 2])
    _same(_g("PROD(CLOSE,2)", [1.0, 2, 4, 7]), [NAN, 2, 8, 28])


def test_gtja_elementwise_max_min() -> None:
    _same(_g("MAX(CLOSE,2)", [1.0, 2, 4, 1]), [2, 2, 4, 2])
    _same(_g("MIN(CLOSE,2)", [1.0, 2, 4, 1]), [1, 2, 2, 1])


def test_gtja_tsrank_is_one_based_with_ties_averaged() -> None:
    # windows of 3: (1,3,2) -> 2 is 2nd of 3; (3,2,2) -> 2 ties for 1st/2nd -> 1.5
    _same(_g("TSRANK(CLOSE,3)", [1.0, 3, 2, 2]), [NAN, NAN, 2.0, 1.5])


def test_gtja_sma_is_the_recursive_average() -> None:
    # Y0 = 1; Y1 = (2*1 + 1*2)/3 = 4/3; Y2 = (3*1 + (4/3)*2)/3 = 17/9
    _same(_g("SMA(CLOSE,3,1)", [1.0, 2, 3]), [1.0, 4 / 3, 17 / 9])


def test_gtja_wma_and_decaylinear_weights() -> None:
    # WMA(.,3): weights 0.9^2, 0.9, 1 (oldest -> now), normalised
    _same(_g("WMA(CLOSE,3)", [1.0, 2, 3]), [NAN, NAN, (0.81 * 1 + 0.9 * 2 + 3) / 2.71])
    # DECAYLINEAR(.,3): weights 1, 2, 3 (oldest -> now), normalised
    _same(_g("DECAYLINEAR(CLOSE,3)", [1.0, 2, 3]), [NAN, NAN, (1 + 4 + 9) / 6])


def test_gtja_regression_on_sequence() -> None:
    # (1,3,2) on x = 1,2,3: slope = sum((x-2)(y-2))/2 = (1 + 0 + 0)/2 = 0.5
    _same(_g("REGBETA(CLOSE,SEQUENCE(3))", [1.0, 3, 2]), [NAN, NAN, 0.5])
    # residual of the last bar: 2 - (mean 2 + 0.5*(3-2)) = -0.5
    _same(_g("REGRESI(CLOSE,SEQUENCE(3))", [1.0, 3, 2]), [NAN, NAN, -0.5])


def test_gtja_regbeta_on_a_series() -> None:
    # y = 2x + 1 exactly: beta 2 on every full window
    x = [1.0, 2, 4, 7]
    p = _panel(x)
    f = {"close": p * 2 + 1, "open": p, "high": p, "low": p}
    got = fo.Evaluator(f, "gtja").evaluate("REGBETA(CLOSE,OPEN,3)")["A"].tolist()
    _same(got, [NAN, NAN, 2.0, 2.0])


def test_gtja_count_sumif_filter_sumac() -> None:
    _same(_g("COUNT(CLOSE>2,2)", [1.0, 3, 4, 2]), [NAN, 1, 2, 1])
    _same(_g("SUMIF(CLOSE,2,CLOSE>2)", [1.0, 3, 4, 2]), [NAN, 3, 7, 4])
    _same(_g("FILTER(CLOSE,CLOSE>2)", [1.0, 3, 4, 2]), [NAN, 3, 4, NAN])
    _same(_g("SUMAC(CLOSE)", [1.0, 3, 4, 2]), [1, 4, 8, 10])


def test_gtja_highday_lowday_count_bars_since_the_extreme() -> None:
    _same(_g("HIGHDAY(CLOSE,3)", [1.0, 3, 2, 0]), [NAN, NAN, 1, 2])
    _same(_g("LOWDAY(CLOSE,3)", [1.0, 3, 2, 0]), [NAN, NAN, 2, 0])


def test_gtja_correlation_and_covariance() -> None:
    a = [1.0, 2, 3, 5]
    p = _panel(a)
    f = {"close": p, "open": -p, "high": p * 3, "low": p}
    ev = fo.Evaluator(f, "gtja")
    _same(ev.evaluate("CORR(CLOSE,OPEN,3)")["A"].tolist(), [NAN, NAN, -1.0, -1.0])
    # cov(x, 3x) over (2,3,5): 3 * var(2,3,5) = 3 * (7/3) = 7
    _same(ev.evaluate("COVIANCE(CLOSE,HIGH,3)")["A"].tolist(), [NAN, NAN, 3.0, 7.0])


def test_gtja_rank_is_cross_sectional_with_average_ties() -> None:
    p = _panel([1.0, 5], [3.0, 5], [2.0, 1])
    f = {"close": p, "open": p, "high": p, "low": p}
    out = fo.Evaluator(f, "gtja").evaluate("RANK(CLOSE)")
    assert out.iloc[0].tolist() == pytest.approx([1 / 3, 1.0, 2 / 3])
    assert out.iloc[1].tolist() == pytest.approx([2.5 / 3, 2.5 / 3, 1 / 3])


def test_gtja_macros_expand_from_the_appendix() -> None:
    _same(_g("RET", [1.0, 2, 3]), [NAN, 1.0, 0.5])


def test_gtja_division_by_zero_is_absent_not_infinite() -> None:
    _same(_g("1/(CLOSE-2)", [1.0, 2, 3]), [-1.0, NAN, 1.0])


# ---------------------------------------------------------------- Qlib operators
def test_qlib_rolling_ops_take_partial_windows() -> None:
    _same(_q("Mean($close,2)", [1.0, 2, 4]), [1.0, 1.5, 3.0])
    _same(_q("Sum($close,2)", [1.0, 2, 4]), [1.0, 3.0, 6.0])
    _same(_q("Max($close,2)", [3.0, 1, 4]), [3.0, 3.0, 4.0])
    _same(_q("Min($close,2)", [3.0, 1, 4]), [3.0, 1.0, 1.0])
    _same(_q("Ref($close,1)", [1.0, 2, 4]), [NAN, 1.0, 2.0])


def test_qlib_quantile_rank_and_idx() -> None:
    # quantile 0.5 (linear) of (1,3,2) = 2; rank pct of 2 in (1,3,2) = 2/3
    _same(_q("Quantile($close,3,0.5)", [1.0, 3, 2]), [1.0, 2.0, 2.0])
    _same(_q("Rank($close,3)", [1.0, 3, 2]), [1.0, 1.0, 2 / 3])
    _same(_q("IdxMax($close,3)", [1.0, 3, 2]), [1.0, 2.0, 2.0])
    _same(_q("IdxMin($close,3)", [1.0, 3, 2]), [1.0, 1.0, 1.0])


def test_qlib_regression_family() -> None:
    # (1,3,2) on position 1..3: slope 0.5, residual -0.5, r^2 = 1 / (2 * 2) = 0.25
    got = _q("Slope($close,3)", [1.0, 3, 2])
    assert math.isnan(got[0]) and got[1] == pytest.approx(2.0) and got[2] == pytest.approx(0.5)
    assert _q("Resi($close,3)", [1.0, 3, 2])[2] == pytest.approx(-0.5)
    assert _q("Rsquare($close,3)", [1.0, 3, 2])[2] == pytest.approx(0.25)


def test_qlib_corr_is_absent_where_a_window_is_flat() -> None:
    p = _panel([1.0, 1, 1, 2])
    f = {"close": p, "volume": _panel([1.0, 2, 3, 4])}
    got = fo.Evaluator(f, "qlib").evaluate("Corr($close,$volume,3)")["A"].tolist()
    assert all(math.isnan(v) for v in got[:3])
    assert got[3] == pytest.approx(np.corrcoef([1, 1, 2], [2, 3, 4])[0, 1])


def test_qlib_comparison_with_absent_operand_is_false() -> None:
    _same(_q("$close>Ref($close,1)", [1.0, 2, 1]), [0.0, 1.0, 0.0])
    _same(_q("Greater($close,2)", [1.0, 2, 3]), [2.0, 2.0, 3.0])
    _same(_q("Less($close,2)", [1.0, 2, 3]), [1.0, 2.0, 2.0])


# ---------------------------------------------------------------- fields and panels
def test_missing_field_is_named() -> None:
    p = _panel([1.0, 2, 3])
    with pytest.raises(fo.MissingField):
        fo.Evaluator({"close": p}, "gtja").evaluate("VWAP/CLOSE")


def test_required_fields_expand_macros_and_alias_volume() -> None:
    assert fo.required_fields("SUM(TR,14)", "gtja") == {"high", "low", "close"}
    assert fo.required_fields("Mean($volume,5)/$close", "qlib") == {"volume", "close"}
    assert fo.needs_panel("RANK(CLOSE)", "gtja")
    assert not fo.needs_panel("Rank($close,5)", "qlib")


def test_panel_from_bars_reindexes_without_filling_and_reads_tick_volume() -> None:
    a = pd.DataFrame({"open": [1.0, 2, 3], "high": [1.0, 2, 3], "low": [1.0, 2, 3],
                      "close": [1.0, 2, 3], "tick_volume": [10.0, 20, 30]}, index=IDX[:3])
    b = a.iloc[[0, 2]] * 2
    fields = fo.panel_from_bars({"A": a, "B": b}, index=a.index)
    assert fields["volume"]["A"].tolist() == [10.0, 20, 30]
    assert math.isnan(fields["close"]["B"].iloc[1])        # no bar -> absent, never filled
    no_vol = fo.panel_from_bars({"A": a, "B": b.drop(columns=["tick_volume"])}, None)
    assert "volume" not in no_vol                          # volume only when every member has it


def test_gtja_rank_of_a_lone_finite_member_is_nan_not_one() -> None:
    """Audit 2026-10-14 SF: a cross-section with one finite member has no rank."""
    p = _panel([1.0, NAN, 2], [NAN, NAN, 1])
    f = {"close": p, "open": p, "high": p, "low": p}
    out = fo.Evaluator(f, "gtja").evaluate("RANK(CLOSE)")
    assert out.iloc[0].isna().all()
    assert out.iloc[1].isna().all()
    assert out.iloc[2].tolist() == pytest.approx([1.0, 0.5])
