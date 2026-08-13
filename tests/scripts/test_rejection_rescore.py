"""The reject forward-scorer: the half of the gate-leak recovery loop that was a stub.

`run_rejection_shadow.py` has always been able to REPORT on forward scores; nothing produced
them, because `_forward_score` returned None unconditionally under a docstring claiming it was
"wired here via the crypto adapter". These tests pin the three ways a scorer like this quietly
lies: scoring on a warm-up-starved window, scoring a strategy that never traded, and reporting a
broken reader as an honest zero.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scripts.run_rejection_rescore import _forward_score, _spec_for


class _Rec:
    def __init__(self, family, subtype, symbol, created_at, params):
        self.family, self.subtype, self.symbol = family, subtype, symbol
        self.created_at, self.params = created_at, params


def _frame(n: int = 800, *, start: str = "2024-01-01", trending: bool = True):
    idx = pd.date_range(start, periods=n, freq="D")
    if trending:
        close = np.linspace(100.0, 400.0, n) + np.sin(np.arange(n) / 7.0) * 3.0
    else:
        close = np.full(n, 100.0)
    return pd.DataFrame(
        {"close": close, "high": close * 1.01, "low": close * 0.99,
         "volume": np.full(n, 1000.0)}, index=idx,
    ).rename_axis("timestamp")


def _rec(created_at: str = "2025-06-01T00:00:00Z"):
    return _Rec("trend", "ma_cross", "TESTUSDT", created_at, {"fast": 20.0, "slow": 50.0})


def test_generator_lookup_is_by_stored_string_not_enum() -> None:
    """The store holds `family.value`; a lookup on the enum's repr would match nothing."""
    assert _spec_for("trend", "ma_cross") is not None
    assert _spec_for("Family.TREND", "ma_cross") is None
    assert _spec_for("trend", "no_such_subtype") is None


def test_a_real_forward_window_produces_a_real_score() -> None:
    got = _forward_score(_rec(), {"TESTUSDT": _frame()}, min_forward_bars=30)
    assert got is not None
    sharpe, n = got
    assert abs(sharpe) > 0.0


def test_THE_SAMPLE_SIZE_TRAVELS_WITH_THE_SCORE() -> None:
    """R0439: an annualized Sharpe stripped of its n is unjudgeable.

    At n=31 its standard error is ~3.4, so a bare float hands the shadow audit a number it cannot
    distinguish from noise -- which is how it was structurally guaranteed to brand noise a leaked
    survivor. The return type was widened to carry n; this asserts the n is REAL rather than a
    placeholder riding along, because a constant in that slot would restore the original defect
    while passing any test that merely unpacks two values.
    """
    frame = _frame()
    early = _forward_score(_rec("2024-06-01T00:00:00Z"), {"TESTUSDT": frame}, min_forward_bars=30)
    late = _forward_score(_rec("2025-06-01T00:00:00Z"), {"TESTUSDT": frame}, min_forward_bars=30)
    assert early is not None and late is not None
    assert early[1] > late[1], "a later cutoff leaves fewer forward bars; n must track the window"
    assert late[1] >= 30, "n must be the count actually scored, never the requirement"


def test_too_short_a_forward_window_scores_none_not_zero() -> None:
    """A Sharpe on a handful of bars is noise; reporting it as a number invites acting on it."""
    frame = _frame()
    late = str(frame.index[-10])          # only ~9 bars after the cutoff
    assert _forward_score(_rec(late), {"TESTUSDT": frame}, min_forward_bars=30) is None


def test_a_rule_that_never_traded_scores_none_not_zero() -> None:
    """`sharpe_ratio` returns 0.0 for zero variance -- which would read as a measured flat result.

    'Never in the market' is not evidence of no leak, and letting it through as a real 0.0 biases
    the gate-leak audit toward finding nothing.
    """
    assert _forward_score(_rec(), {"TESTUSDT": _frame(trending=False)},
                          min_forward_bars=30) is None


def test_a_missing_symbol_scores_none() -> None:
    assert _forward_score(_rec(), {}, min_forward_bars=30) is None


@pytest.mark.parametrize("cutoff_iso", ["2025-06-01T00:00:00Z", "2025-06-01T00:00:00+00:00",
                                        "2025-06-01T00:00:00.123456Z"])
def test_every_stored_timestamp_format_parses(cutoff_iso: str) -> None:
    """The candidate ledger has written all three shapes; a parse failure would score nothing."""
    assert _forward_score(_rec(cutoff_iso), {"TESTUSDT": _frame()}, min_forward_bars=30) is not None


def test_the_score_only_reflects_bars_after_the_rejection() -> None:
    """A cutoff late in the series must not produce the same number as a cutoff early in it."""
    frame = _frame()
    early = _forward_score(_rec("2024-06-01T00:00:00Z"), {"TESTUSDT": frame}, min_forward_bars=30)
    late = _forward_score(_rec("2025-06-01T00:00:00Z"), {"TESTUSDT": frame}, min_forward_bars=30)
    assert early is not None and late is not None
    assert early != late
