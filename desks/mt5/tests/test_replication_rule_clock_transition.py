"""The written replication rule for `clock_transition` (2026-11-05: 127 certificates held
HELD_UNREPLICATED because the spec book had no rule, the second-largest block after `formula`).

FIDELITY: the lane's rebuild, written from the rule text, emits exactly the desk family's orders
(the test may import the implementation; the lane may not)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import replication_civilization as rc  # noqa: E402
from mt5desk.family_clock_transition import CATALOGUE, MODES, family_clock_transition  # noqa: E402


def _frame(days: int = 120, seed: int = 5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=24 * days, freq="h", tz="UTC")
    c = 1.1 + np.cumsum(rng.normal(0, 0.0015, len(idx)))
    df = pd.DataFrame({"open": c, "close": c + rng.normal(0, 0.0005, len(idx))}, index=idx)
    df["high"] = df[["open", "close"]].max(axis=1) + rng.uniform(0, 0.0015, len(idx))
    df["low"] = df[["open", "close"]].min(axis=1) - rng.uniform(0, 0.0015, len(idx))
    return df


def _bars(df: pd.DataFrame) -> rc.Bars:
    return rc.bars_from_arrays(df.index.as_unit("ns").asi8, df["open"].to_numpy(),
                               df["high"].to_numpy(), df["low"].to_numpy(),
                               df["close"].to_numpy())


def _same(orig: list, ours: list) -> bool:
    return len(orig) == len(ours) and all(
        pd.Timestamp(o.time).value == q.t_ns and int(o.side) == q.side
        and abs(float(o.stop) - q.stop) < 1e-9 and abs(float(o.target) - q.target) < 1e-9
        and int(o.ttl_bars) == q.ttl_bars for o, q in zip(orig, ours, strict=True))


def test_the_lane_knows_every_catalogue_moment_and_mode() -> None:
    assert set(CATALOGUE) == rc.CLOCK_LABELS and tuple(MODES) == rc.CLOCK_MODES


@pytest.mark.parametrize("mode", ["into", "out_of", "fade"])
@pytest.mark.parametrize("side", [1, -1])
def test_rule_matches_the_registered_family(mode: str, side: int) -> None:
    df = _frame()
    params = {"label": "london_fix", "stamp_hour": 18, "mode": mode, "side": side,
              "lead_bars": 3, "hold_bars": 5, "atr_n": 14, "stop_atr": 1.5, "rr": 2.0}
    orig = family_clock_transition(df, **params)
    p, why = rc.resolve_spec("clock_transition", params, None, None, symbol="TESTFX")
    assert p is not None, why
    ours = rc.SPEC_BOOK["clock_transition"].build(_bars(df), p)
    assert orig and _same(orig, ours)
    if mode == "fade":
        assert {int(o.side) for o in orig} == {1, -1}


def test_a_fade_keeps_both_sides_whatever_side_the_certificate_records() -> None:
    df = _frame()
    params = {"label": "ny_option_cut", "stamp_hour": 17, "mode": "fade", "side": 1}
    p, _ = rc.resolve_spec("clock_transition", params, None, "LONG", symbol="TESTFX")
    orders, _fills = rc.rebuild("clock_transition", _bars(df), p, 0.0)
    assert {o.side for o in orders} == {1, -1}
    assert _same(family_clock_transition(df, **params), orders)


def test_it_stands_aside_where_the_family_does() -> None:
    short = _frame(days=30)
    base = {"label": "london_fix", "stamp_hour": 18, "mode": "out_of", "side": 1}
    for params, df in ((base, short), ({**base, "label": "lunch"}, _frame()),
                       ({**base, "stamp_hour": 24}, _frame())):
        p, _ = rc.resolve_spec("clock_transition", params, None, None, symbol="X")
        assert family_clock_transition(df, **params) == []
        assert rc.SPEC_BOOK["clock_transition"].build(_bars(df), p) == []
