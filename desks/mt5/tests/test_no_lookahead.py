"""No candidate may use information that did not exist when it decided.

This is a permanent invariant, not a regression test for one bug. It exists
because the desk shipped a leak that inflated every limit-entry family and 8-11%
of the breakout families' signals, survived a full 3,168-cell hunt, and was only
caught because a retail chart pattern scored t = +9.16 and that was implausible
enough to look at. Implausibility is not a gate. This is.

TWO SEPARATE LEAKS, TWO SEPARATE TESTS

  SIGNAL leakage -- a generator reads bars after the decision timestamp.
      Detected metamorphically: corrupt everything after bar i, regenerate, and
      demand that every signal dated at or before bar i is byte-identical. A
      generator that peeks changes its mind when the future changes.

  FILL leakage -- the engine resolves an ambiguity inside the entry bar in the
      trade's favour. Detected by widening the fill bar's extremes: a limit
      entry filled by that bar's low must not be paid by that bar's high, so
      stretching the high alone must not turn a loss into a win.

Both are run over EVERY registered family with no exception list. A family added
later is covered the moment it appears in `families`, which is the point -- an
opt-in leak test protects only the code someone remembered to add.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk import families                                  # noqa: E402
from mt5desk.engine import Costs, Signal, run_backtest        # noqa: E402

FREE = Costs(spread_per_lot=0.0, commission_per_lot=0.0, contract_oz=100.0)
SPLIT = 1200          # bars before the corruption point
N_BARS = 2000


def _synthetic(seed: int = 4) -> pd.DataFrame:
    """A random walk with real intrabar structure and a spread column.

    Synthetic on purpose: a leak test must not depend on the market file being
    present, and a random walk has no edge for a peeking generator to hide in.
    """
    rng = np.random.default_rng(seed)
    step = rng.normal(0, 1.2, N_BARS)
    close = 2000.0 + np.cumsum(step)
    open_ = np.concatenate([[2000.0], close[:-1]])
    wick = np.abs(rng.normal(0, 0.9, N_BARS))
    high = np.maximum(open_, close) + wick
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.9, N_BARS))
    idx = pd.date_range("2024-01-01", periods=N_BARS, freq="1h")
    return pd.DataFrame({"open": open_, "high": high, "low": low,
                         "close": close,
                         "spread": rng.integers(10, 40, N_BARS).astype(float)},
                        index=idx)


def _corrupt_future(df: pd.DataFrame, split: int, seed: int = 99) -> pd.DataFrame:
    """Replace everything from `split` onward with a different random walk."""
    rng = np.random.default_rng(seed)
    out = df.copy()
    n = len(df) - split
    base = float(df["close"].iloc[split - 1])
    close = base + np.cumsum(rng.normal(0, 3.0, n))
    open_ = np.concatenate([[base], close[:-1]])
    out.iloc[split:, out.columns.get_loc("open")] = open_
    out.iloc[split:, out.columns.get_loc("close")] = close
    out.iloc[split:, out.columns.get_loc("high")] = (
        np.maximum(open_, close) + np.abs(rng.normal(0, 2.0, n)))
    out.iloc[split:, out.columns.get_loc("low")] = (
        np.minimum(open_, close) - np.abs(rng.normal(0, 2.0, n)))
    return out


def _all_families():
    for name, fn in sorted(vars(families).items()):
        if not name.startswith("family_") or not callable(fn):
            continue
        params = inspect.signature(fn).parameters
        # families needing an external panel (COT and friends) take a second
        # positional argument; they are covered by their own fixtures.
        required = [p for p in params.values()
                    if p.default is inspect.Parameter.empty
                    and p.kind is not inspect.Parameter.VAR_KEYWORD]
        if len(required) != 1:
            continue
        yield name, fn


def _key(sigs):
    return sorted((pd.Timestamp(s.time).value, s.side, round(s.stop, 6),
                   round(s.target, 6), s.tag,
                   None if s.trigger is None else round(s.trigger, 6))
                  for s in sigs)


FAMILIES = list(_all_families())
assert FAMILIES, "no families discovered -- the test would pass vacuously"


@pytest.mark.parametrize("name,fn", FAMILIES, ids=[n for n, _ in FAMILIES])
def test_family_signals_do_not_change_when_the_future_changes(name, fn) -> None:
    """Every signal dated at or before the corruption point must be identical.

    If a generator's output for bar 900 depends on bar 1500, it is reading a bar
    that had not printed when it decided. There is no benign version of that.
    """
    clean = _synthetic()
    dirty = _corrupt_future(clean, SPLIT)
    cutoff = clean.index[SPLIT - 1]
    a = [s for s in fn(clean) if pd.Timestamp(s.time) <= cutoff]
    b = [s for s in fn(dirty) if pd.Timestamp(s.time) <= cutoff]
    assert _key(a) == _key(b), (
        f"{name} changed {len(a)} -> {len(b)} signals at or before {cutoff} "
        f"when only LATER bars were altered: it is reading the future")


def test_the_leak_test_can_actually_fail() -> None:
    """A leak detector that cannot detect a leak is worse than none.

    Plants a deliberate peeker -- it enters only when the NEXT bar closes up --
    and requires the same comparison to catch it.
    """
    def peeking_family(df: pd.DataFrame) -> list[Signal]:
        c = df["close"].to_numpy()
        out = []
        for i in range(20, len(df) - 2):
            if c[i + 1] > c[i]:                       # <- the future
                out.append(Signal(time=df.index[i], side=1,
                                  stop=c[i] - 5, target=c[i] + 5,
                                  ttl_bars=5, tag="peek"))
        return out

    clean = _synthetic()
    dirty = _corrupt_future(clean, SPLIT)
    cutoff = clean.index[SPLIT - 1]
    a = [s for s in peeking_family(clean) if pd.Timestamp(s.time) <= cutoff]
    b = [s for s in peeking_family(dirty) if pd.Timestamp(s.time) <= cutoff]
    assert _key(a) != _key(b), "the leak test failed to catch a planted leak"


def _bars(rows):
    idx = pd.date_range("2024-01-01", periods=len(rows), freq="1h")
    return pd.DataFrame(
        {"open": [r[0] for r in rows], "high": [r[1] for r in rows],
         "low": [r[2] for r in rows], "close": [r[3] for r in rows]}, index=idx)


def test_widening_the_fill_bar_high_cannot_rescue_a_limit_entry() -> None:
    """The engine must not pay a limit entry out of its own fill bar.

    Same path twice; the only difference is that the second version's fill bar
    prints a higher high. We were filled by that bar's LOW, so its HIGH may have
    come first. If stretching the high alone turns the outcome positive, the
    backtest is resolving intrabar order in its own favour -- which is exactly
    the defect that took GBPJPY fair-value-gap from t = -6.18 to t = +9.16.
    """
    narrow = _bars([(100, 100, 100, 100),
                    (100, 100.2, 99.9, 100.1),
                    (100.1, 101.0, 98.9, 99.2),
                    (99.2, 99.4, 96.0, 96.5)])
    wide = narrow.copy()
    wide.iloc[2, wide.columns.get_loc("high")] = 106.0     # only the high moves
    sig = dict(side=1, stop=98.0, target=102.0, trigger=99.0,
               wait_bars=3, ttl_bars=10, tag="t")
    a = run_backtest(narrow, [Signal(time=narrow.index[0], **sig)], FREE).trades[0]
    b = run_backtest(wide, [Signal(time=wide.index[0], **sig)], FREE).trades[0]
    assert a.entry == b.entry == pytest.approx(99.0)
    assert b.r_multiple == pytest.approx(a.r_multiple, abs=1e-9), (
        f"stretching the fill bar's high changed R from {a.r_multiple:.4f} to "
        f"{b.r_multiple:.4f}: the engine is paying a limit entry from the bar "
        f"that filled it")
