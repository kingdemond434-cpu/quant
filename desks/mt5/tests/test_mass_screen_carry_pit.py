"""The mass screen's carry grammar reads the swap KNOWABLE AT EACH BAR, never today's.

Before 2026-10-07 `carry_side(meta)` took today's registry swap and applied its side to every
past bar, and the rebuild fired at the carry hour whatever the swap was then. Pinned here: the
per-bar side, the side chosen from the training window only, the screen's fires and the
gauntlet's rebuild agreeing bar for bar, and a pre-fix carry cell rebuilding to nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parent.parent
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(DESK / "tests"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import mass_screen as MS  # noqa: E402
from mt5desk import families_carry as FC  # noqa: E402
from mt5desk import families_orthogonal as FO  # noqa: E402
from mt5desk import mass_screen_rules as MR  # noqa: E402
from mt5desk.engine import SWAP_MAX_AGE_H  # noqa: E402
from test_mass_screen import META, bars  # noqa: E402

DAY = pd.Timedelta(days=1)
T0 = pd.Timestamp("2019-01-01", tz="UTC")
LEAD = pd.Timedelta(hours=3)


@pytest.fixture
def tape(tmp_path, monkeypatch):
    terms = tmp_path / "terms"
    terms.mkdir()
    monkeypatch.setattr(FC, "TERMS_DIR", terms)
    monkeypatch.setattr(FC, "PANEL_DIR", tmp_path / "no_panel")
    monkeypatch.setattr(FC, "UNITS", tmp_path / "none.json")
    monkeypatch.setattr(FC, "_CACHE", {"key": None, "hist": None, "stats": None,
                                       "ceiling": None})

    def write(spans: list[tuple[int, int, float, float]]) -> None:
        rows = [{"observed_at": (T0 + d * DAY).isoformat(), "symbol": "SYN", "swap_long": lo,
                 "swap_short": sh, "swap_mode": 1, "point": 1e-5}
                for a, b, lo, sh in spans for d in range(a, b)]
        pd.DataFrame(rows).to_parquet(terms / "tape.parquet", index=False)
        FC._CACHE["key"] = None

    return write


# long pays on days 50..109 (inside the 30% training window of 400 days); short pays from 110
# to 299 -- so TODAY's swap says short, and reading it onto the past was the lookahead
FLIP = [(50, 110, 2.0, -5.0), (110, 300, -5.0, 2.0)]


def test_the_per_bar_side_is_the_side_knowable_then(tape) -> None:
    tape(FLIP)
    P = MS.Prepared("SYN", bars(400), META, {})
    t = pd.DatetimeIndex(P.df.index)
    first, flip = T0 + 50 * DAY + LEAD, T0 + 110 * DAY + LEAD
    stale = T0 + 299 * DAY + LEAD + pd.Timedelta(hours=SWAP_MAX_AGE_H)
    assert (P.carry_pit[t < first] == 0).all(), "nothing before the first stamped row"
    assert (P.carry_pit[(t >= first) & (t < flip)] == 1).all()
    assert (P.carry_pit[(t >= flip) & (t <= stale)] == -1).all()
    assert (P.carry_pit[t > stale] == 0).all(), "a stale row is no swap"
    assert FC.PIT_MAX_AGE_H == SWAP_MAX_AGE_H


def test_the_side_comes_from_the_training_window_never_from_today(tape) -> None:
    tape(FLIP)
    P = MS.Prepared("SYN", bars(400), META, {})
    today = {**META, "swap_long": -5.0, "swap_short": 2.0}          # what the registry says now
    assert MS.carry_side(P) == 1
    carry = [c for c in MS.conditions(P, today) if c["grammar"] == "carry"]
    assert carry and {c["carry_side"] for c in carry} == {1}
    assert {c["op"] for c in carry if c["feat"]} == {"gt"}


def test_no_knowable_swap_in_the_training_window_screens_no_carry(tape) -> None:
    tape([(200, 300, 2.0, -5.0)])
    P = MS.Prepared("SYN", bars(400), META, {})
    assert MS.carry_side(P) == 0
    assert not [c for c in MS.conditions(P, META) if c["grammar"] == "carry"]


def test_screen_fires_equal_the_gauntlets_rebuild_bar_for_bar(tape) -> None:
    tape(FLIP)
    df = bars(400)
    P = MS.Prepared("SYN", df, META, {})
    cond = next(c for c in MS.conditions(P, META)
                if c["grammar"] == "carry" and not c["cond_feat"] and not c["feat"])
    mask = P.mask(cond)
    assert mask.any() and (P.carry_pit[mask] == 1).all(), "fires only where long paid then"
    hold = 8
    kept = MR.thin(np.flatnonzero(mask), hold, P.entry_day)
    cand = {"symbol": "SYN", "grammar": "carry", "cond": MS._public(cond), "hold": hold,
            "direction": 1, "stop_atr": MS.VARIANTS[0][1]}
    params = MS.params_of(cand)
    assert params["symbol"] == "SYN" and params["carry_side"] == 1
    fn = FO.ORTHOGONAL_FAMILIES["mass_screen_carry"]
    sigs = fn(MR._h1(df), side=1, **params)            # exactly how build_cell calls a family
    assert [s.time for s in sigs] == list(P.df.index[kept])
    assert "mt5:broker_swaps" in FO.FAMILY_INPUTS["mass_screen_carry"][0]


def test_a_pre_fix_carry_cell_rebuilds_to_nothing_and_keys_apart(tape) -> None:
    tape(FLIP)
    df = MR._h1(bars(400))
    old = {"feat": "", "op": "gt", "thr": 0.0, "direction": 1, "hold": 8, "stop_atr": 1.0,
           "cond_feat": "", "cond_lo": -MR.OPEN_BOUND, "cond_hi": MR.OPEN_BOUND, "hour": 8,
           "weekday": -1, "leader": "", "atr_n": 20, "gv": MR.GRAMMAR_VERSION}
    fn = FO.ORTHOGONAL_FAMILIES["mass_screen_carry"]
    assert fn(df, side=1, **old) == []
    assert fn(df, side=1, **old, symbol="SYN", carry_side=1)
    assert FO.ORTHOGONAL_FAMILIES["mass_screen_clock"] is MR.family_mass_screen_rule
    base = {"symbol": "SYN", "cond": {"hour": 8}, "hold": 8, "direction": 1, "stop_atr": 1.0}
    assert MS.structural_key({**base, "grammar": "carry"}).endswith("|pit")
    assert not MS.structural_key({**base, "grammar": "clock"}).endswith("|pit")


def test_an_unreadable_history_fails_closed(monkeypatch) -> None:
    def boom(*a, **k):
        raise OSError("no tape")

    monkeypatch.setattr(FC, "paying_side_at", boom)
    idx = pd.date_range("2020-01-01", periods=10, freq="h", tz="UTC")
    assert not MR.carry_mask(idx, "SYN", 1).any()
    assert not MR.carry_mask(idx, "", 1).any()
