"""The engine's exits may never resolve unknown intrabar order in the trade's favour (2026-11-11).

Hourly pass 107 (idea 654) found three biases in an off-box harness with a random-entry positive
control. Two were in this engine too: a stop the bar GAPPED through was paid at the stop level,
and a partial bank was credited (and its stop ratcheted) on a bar the original stop also took.
Pinned: a gap-through stop fills at the open; the bank is never paid on a bar the stop took;
and coin-flip entries through every exit policy carry no gross edge of their own.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_DESK))

from mt5desk.engine import Costs, Signal, Trade, run_backtest  # noqa: E402

FREE = Costs(spread_per_lot=0.0, commission_per_lot=0.0, contract_oz=1.0)


def _frame(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    idx = pd.date_range("2026-01-05", periods=len(rows), freq="1h", tz="UTC")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)


def _one(df: pd.DataFrame, **kw: object) -> Trade:
    base = {"time": df.index[0], "side": 1, "stop": 99.0, "target": 102.0, "ttl_bars": 10,
            "tag": "t"}
    base.update(kw)
    res = run_backtest(df, [Signal(**base)], FREE)  # type: ignore[arg-type]
    assert len(res.trades) == 1, res.trades
    return res.trades[0]


def test_a_long_stop_the_bar_gapped_through_fills_at_the_open() -> None:
    # entry 100 at bar 1's open; bar 2 opens at 97, below the 99 stop.
    df = _frame([(100, 100, 100, 100), (100, 100.5, 99.5, 100), (97, 97.5, 96, 97),
                 (97, 98, 96, 97)])
    t = _one(df)
    assert t.exit == 97.0 and abs(t.r_multiple - (-3.0)) < 1e-9


def test_a_short_stop_the_bar_gapped_through_fills_at_the_open() -> None:
    df = _frame([(100, 100, 100, 100), (100, 100.5, 99.5, 100), (103, 104, 102.5, 103),
                 (103, 104, 102, 103)])
    t = _one(df, side=-1, stop=101.0, target=98.0)
    assert t.exit == 103.0 and abs(t.r_multiple - (-3.0)) < 1e-9


def test_a_stop_touched_without_a_gap_still_fills_at_the_stop() -> None:
    df = _frame([(100, 100, 100, 100), (100, 100.5, 99.5, 100), (99.8, 100, 98.5, 99),
                 (99, 99.5, 98, 99)])
    assert _one(df).exit == 99.0


def test_the_bank_is_never_paid_on_a_bar_the_stop_took() -> None:
    # bar 2 touches BOTH the 102 target and the 99 stop: intrabar order unknown, so no bank.
    df = _frame([(100, 100, 100, 100), (100, 100.5, 99.5, 100), (100, 102.5, 98.5, 100),
                 (100, 101, 99.5, 100)])
    t = _one(df, bank_frac=0.5, bank_protect_k=0.0)
    assert t.exit == 99.0 and abs(t.r_multiple - (-1.0)) < 1e-9


def test_a_bank_on_a_bar_the_stop_survived_is_still_paid() -> None:
    df = _frame([(100, 100, 100, 100), (100, 100.5, 99.5, 100), (100, 102.5, 99.5, 102),
                 (102, 102.2, 99.8, 100), (100, 100.2, 99.8, 100)])
    t = _one(df, bank_frac=0.5, bank_protect_k=0.0)
    # half at the target (+2R), the rest stopped at the protect level (entry): +1R
    assert abs(t.r_multiple - 1.0) < 1e-9


def test_both_sides_retest_the_protect_stop_on_the_bar_that_banked() -> None:
    """A bar that reaches the target and then the protect level (not the original stop) exits the
    runner at protect, long and short alike: neither side lets the runner run on that bar."""
    long_df = _frame([(100, 100, 100, 100), (100, 100.5, 99.5, 100), (100, 102.5, 99.8, 100),
                      (100, 105, 100, 105), (105, 105, 105, 105)])
    lt = _one(long_df, bank_frac=0.5, bank_protect_k=0.1)        # protect at 100.1
    short_df = _frame([(100, 100, 100, 100), (100, 100.5, 99.5, 100), (100, 100.2, 97.5, 100),
                       (100, 100, 95, 95), (95, 95, 95, 95)])
    st = _one(short_df, side=-1, stop=101.0, target=98.0, bank_frac=0.5, bank_protect_k=0.1)
    assert lt.exit == 100.1 and st.exit == 99.9, (lt, st)
    assert abs(lt.r_multiple - st.r_multiple) < 1e-9


def test_coin_flip_entries_never_gain_from_an_exit_rule() -> None:
    """The positive control: random entries on a driftless walk with gaps, zero cost.

    Coin-flip entries have no edge, so no exit policy may show a POSITIVE mean gross R beyond
    noise: a tie rule that favours the trade (a bank paid on a stopped bar, a gapped stop paid at
    its level) shows up exactly there. The stop-first rule on a bar that touched both is
    deliberately pessimistic, so the check is one-sided.
    """
    rng = np.random.default_rng(654)
    n = 30_000
    step = rng.normal(0.0, 0.10, n)
    gap = np.where(rng.random(n) < 0.03, rng.normal(0.0, 0.6, n), 0.0)   # 3% of bars gap
    open_ = np.empty(n)
    close = np.empty(n)
    open_[0], close[0] = 100.0, 100.0 + step[0]
    for k in range(1, n):
        open_[k] = close[k - 1] + gap[k]
        close[k] = open_[k] + step[k]
    hi = np.maximum(open_, close) + np.abs(rng.normal(0.0, 0.05, n))
    lo = np.minimum(open_, close) - np.abs(rng.normal(0.0, 0.05, n))
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    df = pd.DataFrame({"open": open_, "high": hi, "low": lo, "close": close}, index=idx)
    at = np.sort(rng.choice(np.arange(5, n - 40), size=24_000, replace=False))
    side = np.where(rng.random(at.size) < 0.5, 1, -1)

    def mean_r(sd: float, tg: float, bank: float = 0.0) -> tuple[float, float]:
        sigs = [Signal(time=idx[i], side=int(s), stop=float(close[i]) - s * sd,
                       target=float(close[i]) + s * tg, ttl_bars=24, tag="coin",
                       bank_frac=bank, bank_protect_k=0.0)
                for i, s in zip(at, side, strict=True)]
        rs = np.array([t.r_multiple for t in run_backtest(df, sigs, FREE).trades])
        return float(rs.mean()), float(rs.std(ddof=1) / np.sqrt(rs.size))

    for sd, tg, bank in ((1e6, 1e6, 0.0), (0.4, 0.4, 0.0), (0.4, 1.2, 0.0), (0.15, 0.45, 0.0),
                         (0.4, 0.4, 0.5), (0.15, 0.3, 0.5)):
        m, se = mean_r(sd, tg, bank)
        assert m < 4.0 * se + 0.01, ((sd, tg, bank), m, se)
