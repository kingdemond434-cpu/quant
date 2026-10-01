"""The vendored alpha zoo as class books: loads, ranks within class, causal, judged book-first."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import families_cross_sectional as fcs  # noqa: E402
from mt5desk import families_orthogonal as fo  # noqa: E402
from mt5desk import family_zoo_alpha as zoo  # noqa: E402

MEMBERS = [f"S{i}USD" for i in range(8)]


def _h1(seed: int, n_days: int = 700) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-03", periods=24 * n_days, freq="h", tz="UTC")
    close = 1.0 + 0.1 * seed + np.exp(np.cumsum(rng.normal(0, 0.001, len(idx)))) - 1
    open_ = np.concatenate(([close[0]], close[:-1]))
    w = np.abs(rng.normal(0, 0.0004, len(idx)))
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) + w,
                         "low": np.minimum(open_, close) - w, "close": close,
                         "tick_volume": rng.integers(50, 500, len(idx))}, index=idx)


@pytest.fixture()
def store(monkeypatch, tmp_path):
    for i, m in enumerate(MEMBERS):
        _h1(i).to_parquet(tmp_path / f"{m}_H1.parquet")
    monkeypatch.setattr(fcs, "UNIVERSE_DIR", tmp_path)
    monkeypatch.setattr(fcs, "class_of", lambda s: "synthetic" if s in MEMBERS else None)
    monkeypatch.setattr(fcs, "class_symbols", lambda k: list(MEMBERS))
    monkeypatch.setattr(fcs, "orientation", lambda s, k: 1)
    zoo._PANEL_CACHE.clear()
    return tmp_path


def test_catalogue_offers_the_three_zoos_and_nothing_mt5_cannot_feed():
    cat = zoo.catalogue()
    assert len(cat) >= 300
    assert {m["zoo"] for m in cat.values()} >= {"gtja191", "qlib158", "alpha101"}
    for m in cat.values():
        assert set(m.get("columns_required") or []) <= zoo.SUPPLIED
        assert not m.get("requires_sector") and not m.get("extras_required")


def test_registered_and_allowed_for_the_equity_class_books():
    from research import universe_policy as up
    assert fo.ORTHOGONAL_FAMILIES["zoo_alpha_class"] is zoo.family_zoo_alpha_class
    assert "zoo_alpha_class" in up.CROSS_SECTIONAL_FAMILIES


def test_leg_fires_both_ways_and_is_causal(store):
    own = pd.read_parquet(store / f"{MEMBERS[2]}_H1.parquet")
    aid = "gtja191.alpha_003"
    sigs = zoo.family_zoo_alpha_class(own, symbol=MEMBERS[2], alpha_id=aid, hold_d=3)
    assert sigs and {s.side for s in sigs} == {1, -1}
    days = own.index.normalize()
    assert all(s.time == own.index[days == s.time.normalize()][0] for s in sigs)  # day's 1st bar
    cut = len(own) - 24 * 60
    early = own.index[cut - 24 * 3]
    full = {(s.time, s.side) for s in sigs if s.time < early}
    part = {(s.time, s.side) for s in zoo.family_zoo_alpha_class(
        own.iloc[:cut], symbol=MEMBERS[2], alpha_id=aid, hold_d=3) if s.time < early}
    assert full == part
    flipped = {(s.time, -s.side) for s in zoo.family_zoo_alpha_class(
        own, symbol=MEMBERS[2], alpha_id=aid, hold_d=3, direction=-1)}
    assert {(s.time, s.side) for s in sigs} == flipped


def test_unknown_alpha_or_symbol_returns_nothing(store):
    own = pd.read_parquet(store / f"{MEMBERS[0]}_H1.parquet")
    assert zoo.family_zoo_alpha_class(own, symbol=MEMBERS[0], alpha_id="nope.x") == []
    assert zoo.family_zoo_alpha_class(own, symbol="EURUSD", alpha_id="gtja191.alpha_003") == []


def test_book_ic_finds_a_planted_signal_and_not_noise():
    from research import zoo_breadth as zb
    rng = np.random.default_rng(1)
    idx = pd.date_range("2020-01-01", periods=800, freq="D")
    cols = [f"M{i}" for i in range(10)]
    score = pd.DataFrame(rng.normal(size=(800, 10)), idx, cols)
    ret = 0.01 * score.shift(1).fillna(0) + rng.normal(0, 0.01, (800, 10))
    close = np.exp(ret.cumsum())
    panel = {"open": close.shift(1).fillna(1.0), "close": close}
    t_sig, _ = zb.book_ic(score, panel, 1)
    t_null, _ = zb.book_ic(pd.DataFrame(rng.normal(size=(800, 10)), idx, cols), panel, 1)
    assert t_sig > 5 and abs(t_null) < 3.5


def test_leg_is_wired():
    from libs.research.layers import LEG_LAYER
    text = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("zoo_breadth"' in text and LEG_LAYER["zoo_breadth"] == "prediction"
