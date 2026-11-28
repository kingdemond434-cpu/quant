"""A hunt16 cell's `side` param is a direction (2026-11-05). The docket carries it as "SHORT" /
"LONG"; the sealed gauntlet's fallback handed that string to `side > 0` and 137
`dav_range_filter_adx` cells a sweep died NOT_RUN_BUILD_FAILED. The judge-facing export reads it
as +1/-1 and trades exactly the constructor's signals for that side."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import families  # noqa: E402
from mt5desk.executables import hunt16_families  # noqa: E402


def _h1() -> pd.DataFrame:
    rng = np.random.default_rng(16)
    idx = pd.date_range("2024-01-01", periods=3000, freq="h", tz="UTC")
    c = 1.1 + np.cumsum(rng.normal(0, 1.5e-3, len(idx)))
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) + 8e-4,
                         "low": np.minimum(o, c) - 8e-4, "close": c,
                         "tick_volume": rng.integers(50, 500, len(idx))}, index=idx)


@pytest.mark.parametrize("raw,want", [("SHORT", -1), ("short", -1), ("SELL", -1), ("-1", -1),
                                      (-1, -1), ("LONG", 1), ("BUY", 1), (1, 1), ("1", 1)])
def test_a_side_spelling_reads_as_a_direction(raw, want) -> None:
    assert families.hunt16_side(raw) == want


@pytest.mark.parametrize("raw", ["", "FLAT", 0, None, True])
def test_an_unreadable_side_is_refused(raw) -> None:
    with pytest.raises((TypeError, ValueError)):
        families.hunt16_side(raw)


def test_the_gauntlet_fallback_call_trades_the_constructors_short_signals() -> None:
    h1 = _h1()
    fn = families.family_dav_range_filter_adx
    orig = hunt16_families()["dav_range_filter_adx"]
    assert inspect.signature(fn) == inspect.signature(orig)
    assert families.family_dav_range_filter_adx is fn           # one export per constructor
    with pytest.raises(TypeError):                       # the gauntlet's first call, as before
        fn(h1, side=1, **{"side": "SHORT"})
    got = fn(h1, **{"side": "SHORT"})                    # its fallback: was a TypeError
    want = orig(h1, -1)
    assert [(s.time, s.side) for s in got] == [(s.time, s.side) for s in want]
    assert [(s.time, s.side) for s in fn(h1, side=1)] == [(s.time, s.side) for s in orig(h1, 1)]
