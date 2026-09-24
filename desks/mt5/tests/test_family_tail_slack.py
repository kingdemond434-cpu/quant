"""THE ONE BAR THAT KEPT EVERY `families.py` SLEEVE OUT OF THE MARKET.

`family_signal_step` filters the family's signals to `g.time == last_bar`, so the family must be
ABLE to emit on `last_bar`. The 2026-09-15 fix appended the forming bar, which reaches a family
whose loop ends at `len(d) - 1` -- `families_orthogonal.py`, and those sleeves do place. Every
family in `families.py` ends at `len(h1) - 2` and needs one more, so `session_range_breakout` --
the only `families.py` family ever promoted LIVE -- could never emit on the bar it was asked
about. Measured on the box 2026-09-24 over 240 hourly passes of real XAUUSD H1 bars: the family
emitted on 240/240 passes and matched `last_bar` on 0; with one more trailing bar, 10.
"""
from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

BASE = Path(__file__).resolve().parents[1]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from mt5desk import families, families_orthogonal  # noqa: E402
from mt5desk.decision_core import (  # noqa: E402
    FAMILY_TAIL_SLACK,
    extend_signal_tail,
    family_signal_step,
)

_BOUND = re.compile(r"for\s+i\s+in\s+range\([^)]*len\(\s*[A-Za-z_][A-Za-z0-9_]*\s*\)\s*-\s*(\d+)\)")


def _frame(n: int = 400, start: str = "2026-01-01 00:00") -> pd.DataFrame:
    idx = pd.date_range(start, periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(11)
    close = 2000.0 + np.cumsum(rng.normal(0, 1.5, n))
    return pd.DataFrame({"open": close + rng.normal(0, 0.2, n),
                         "high": close + np.abs(rng.normal(1.0, 0.4, n)),
                         "low": close - np.abs(rng.normal(1.0, 0.4, n)),
                         "close": close,
                         "tick_volume": rng.integers(50, 500, n),
                         "spread": rng.integers(10, 30, n),
                         "real_volume": 0}, index=idx)


def _trailing_margins(module: object) -> dict[str, int]:
    out: dict[str, int] = {}
    for name, fn in vars(module).items():
        if not (name.startswith("family_") and callable(fn)):
            continue
        try:
            src = inspect.getsource(fn)
        except (OSError, TypeError):            # pragma: no cover - defensive
            continue
        found = [int(m) for m in _BOUND.findall(src)]
        if found:
            out[name] = max(found)
    return out


def test_no_family_needs_more_trailing_bars_than_the_slack_provides() -> None:
    """The constant cannot rot: adding a family with a deeper bound fails here, not in the book."""
    margins = {**_trailing_margins(families), **_trailing_margins(families_orthogonal)}
    assert margins, "no family loop bounds were parsed; the guard would pass vacuously"
    worst = max(margins.values())
    assert worst <= FAMILY_TAIL_SLACK, (
        f"{[k for k, v in margins.items() if v > FAMILY_TAIL_SLACK]} need {worst} trailing bars "
        f"and FAMILY_TAIL_SLACK is {FAMILY_TAIL_SLACK}; such a sleeve can never emit on the bar "
        f"the gateway asks about")
    assert max(_trailing_margins(families).values()) == 2, (
        "families.py is the module that needs TWO; if that changed, re-measure the slack")


def test_extend_signal_tail_leaves_room_after_the_asked_bar() -> None:
    f = _frame(120)
    last_bar = f.index[-2]                       # the last CLOSED bar; f[-1] is the forming one
    out = extend_signal_tail(f, last_bar)
    assert len(out) - 1 - out.index.get_loc(last_bar) >= FAMILY_TAIL_SLACK
    assert out.index.is_monotonic_increasing
    # the real bars are returned untouched, value for value (`check_freq=False`: concatenating
    # drops the synthetic index's `freq`, which a live MT5 frame does not carry in the first place)
    pd.testing.assert_frame_equal(out.iloc[:len(f)], f, check_freq=False)


def test_extend_signal_tail_is_a_no_op_when_there_is_already_room() -> None:
    f = _frame(120)
    last_bar = f.index[-(FAMILY_TAIL_SLACK + 1)]
    assert extend_signal_tail(f, last_bar) is f


def test_session_range_breakout_can_now_emit_on_the_bar_the_gateway_asks_about() -> None:
    """The measurement that names the defect, as a test."""
    f = _frame(400)
    closed = f.iloc[:-1]
    hits_today = hits_fixed = 0
    for end in range(300, len(f)):
        frame = f.iloc[:end + 1]
        closed = frame.iloc[:-1]
        last_bar = closed.index[-1]
        today = families.family_session_range_breakout(frame, rr=1.5, wait_bars=12)
        fixed = families.family_session_range_breakout(
            extend_signal_tail(frame, last_bar), rr=1.5, wait_bars=12)
        hits_today += any(pd.Timestamp(g.time) == last_bar for g in today)
        hits_fixed += any(pd.Timestamp(g.time) == last_bar for g in fixed)
    assert hits_today == 0, "the defect is gone from the family itself; re-read this test"
    assert hits_fixed > 0, "padding did not make the asked-about bar reachable"


@pytest.mark.parametrize("fam_name", ["family_overnight_gap_decay", "family_carry"])
def test_padding_changes_nothing_for_a_family_that_already_traded(fam_name: str) -> None:
    """The families that DO place must be byte-identical at `last_bar` after the change."""
    fn = getattr(families_orthogonal, fam_name)
    f = _frame(400)
    for end in (350, 375, 399):
        frame = f.iloc[:end + 1]
        last_bar = frame.index[-2]
        try:
            a = [g for g in fn(frame) if pd.Timestamp(g.time) == last_bar]
            b = [g for g in fn(extend_signal_tail(frame, last_bar))
                 if pd.Timestamp(g.time) == last_bar]
        except TypeError:
            pytest.skip(f"{fam_name} needs inputs this frame does not carry")
        assert [(g.side, g.stop, g.target) for g in a] == [(g.side, g.stop, g.target) for g in b]


def test_the_agreeing_leg_is_placed_and_only_the_opposing_one_is_skipped() -> None:
    """An OCO breakout emits both sides on one bar; the book's own direction picks the leg."""
    # 393 bars from midnight puts the last CLOSED bar on hour 7, which is this family's default
    # `range_start` and therefore its signal hour: the bar that emits BOTH legs.
    f = _frame(393)
    closed = f.iloc[:-1]
    last_bar = closed.index[-1]
    assert last_bar.hour == 7, "the frame must end on the family's signal hour for this test"
    call = {"closed": closed, "last_bar": last_bar, "last_signal_bar": None, "want_state": None,
            "side": 1, "family_fn": families.family_session_range_breakout,
            "day_states_fn": lambda _d: {}, "call_params": {"rr": 1.5, "wait_bars": 12},
            "signal_bars": f}
    base = family_signal_step(**call)
    assert base.signal is not None, (
        "the padded frame must reach the signal hour; if this fails the fix is not wired")
    longer = family_signal_step(**call, prefer_side=1)
    shorter = family_signal_step(**call, prefer_side=-1)
    assert longer.signal is not None and shorter.signal is not None, (
        "the directional rule must choose a leg, never skip the trade")
    assert int(longer.signal.side) == 1
    assert int(shorter.signal.side) == -1
    # and with no held direction the old choice is preserved exactly
    assert family_signal_step(**call, prefer_side=None).signal.side == base.signal.side
