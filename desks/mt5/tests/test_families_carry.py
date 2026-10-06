"""FX carry books: stamped swaps only, never backfilled, ranked on the class, history-gated."""
from __future__ import annotations

import json
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

from mt5desk import families_carry as fc  # noqa: E402
from mt5desk import families_cross_sectional as xs  # noqa: E402
from mt5desk import families_orthogonal as fo  # noqa: E402

from research import axis_registry as ax  # noqa: E402
from research import elitequant_breadth as eb  # noqa: E402
from research import orthogonal_sweep as sw  # noqa: E402

DAYS = 600
MEMBERS = 7
START = 300          # the first day any honest swap row exists


def _frame(seed: int = 3) -> tuple[pd.DataFrame, np.ndarray]:
    rng = np.random.default_rng(seed)
    logv = np.cumsum(rng.normal(0, 0.006, (DAYS, MEMBERS)), axis=0)
    idx = pd.date_range("2024-01-01 22:00", periods=DAYS, freq="D", tz="UTC")
    close = np.exp(logv[:, 0])
    o = np.r_[close[0], close[:-1]]
    d = pd.DataFrame({"open": o, "high": np.maximum(o, close) * 1.001,
                      "low": np.minimum(o, close) * 0.999, "close": close}, index=idx)
    return d, logv


def _names(own: str) -> list[str]:
    return [own] + [f"P{i}" for i in range(MEMBERS - 1)]


@pytest.fixture
def world(monkeypatch, tmp_path):
    """A class panel and a swap tape written as the box writes it, in mode 5 (annual %)."""
    terms, panel = tmp_path / "terms", tmp_path / "panel"
    terms.mkdir()
    panel.mkdir()
    monkeypatch.setattr(fc, "TERMS_DIR", terms)
    monkeypatch.setattr(fc, "PANEL_DIR", panel)
    monkeypatch.setattr(fc, "UNITS", tmp_path / "none.json")
    monkeypatch.setattr(fc, "_CACHE", {"key": None, "hist": None, "stats": None})
    monkeypatch.setattr(xs, "class_of", lambda s: "fx_usd")
    monkeypatch.setattr(xs, "orientation", lambda s, k: 1)
    d, logv = _frame()

    def fake(frame, symbol, *, decision_hour=22, max_stale_h=12.0):
        n = len(frame)
        return {"klass": "fx_usd", "members": _names(symbol), "own": 0, "pos": np.arange(n),
                "logv": logv[:n], "orient": 1, "close": frame["close"].to_numpy(dtype=float)}

    monkeypatch.setattr(xs, "class_panel", fake)

    def write(own: str, carries: list[float], *, start: int = START, stop: int = DAYS) -> None:
        rows = []
        for day in range(start, stop):
            at = (d.index[day] - pd.Timedelta(hours=6)).isoformat()
            for sym, c in zip(_names(own), carries, strict=True):
                rows.append({"observed_at": at, "symbol": sym, "swap_long": c - 0.25,
                             "swap_short": -c - 0.25, "swap_mode": 5, "point": 1e-5})
        pd.DataFrame(rows).to_parquet(terms / "tape.parquet", index=False)
        fc._CACHE["key"] = None

    return d, write


RANKED = [3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 0.5]       # own leg (index 0) pays most


def test_no_carry_before_the_first_stamped_row_and_ranked_long(world):
    d, write = world
    write("EURUSD", RANKED)
    sig = fc.family_fx_swap_carry_rank(d, symbol="EURUSD", quantile=1 / 3, hold_d=5)
    assert sig, "a full class with honest swaps must rank the top payer"
    first_knowable = d.index[START] - pd.Timedelta(hours=6) + pd.Timedelta(hours=3)
    assert min(s.time for s in sig) >= first_knowable
    assert {s.side for s in sig} == {1}
    write("EURUSD", [-c for c in RANKED])
    assert {s.side for s in fc.family_fx_swap_carry_rank(d, symbol="EURUSD")} == {-1}


def test_a_stale_history_stops_the_book(world):
    d, write = world
    write("EURUSD", RANKED, stop=400)
    sig = fc.family_fx_swap_carry_rank(d, symbol="EURUSD", max_panel_age_h=48.0)
    assert sig
    assert max(s.time for s in sig) <= d.index[399] + pd.Timedelta(hours=48)


def test_unstamped_panel_rows_are_never_read(world, tmp_path):
    d, _ = world
    rows = [{"kind": "swap_table", "symbols": [s], "found_at": "2024-01-02T00:00:00+00:00",
             "swap_long": 1.0, "swap_short": -1.0} for s in _names("EURUSD")]
    (fc.PANEL_DIR / "discoveries_20240102_0000.json").write_text(json.dumps(rows))
    assert fc.family_fx_swap_carry_rank(d, symbol="EURUSD") == []
    _, stats = fc.swap_history()
    assert stats["panel_rows_unstamped"] == MEMBERS and stats["panel_rows_honest"] == 0
    stamped = [{**r, "observed_at": r["found_at"], "swap_mode": 5} for r in rows]
    (fc.PANEL_DIR / "discoveries_20240102_0000.json").write_text(json.dumps(stamped))
    fc._CACHE["key"] = None
    assert fc.swap_history()[1]["panel_rows_honest"] == MEMBERS


def test_dollar_basket_follows_the_class_average(world):
    d, write = world
    write("EURUSD", [1.0, 2.0, 0.5, 1.5, 0.2, 3.0, 1.0])
    assert {s.side for s in fc.family_dollar_carry_basket(d, symbol="EURUSD")} == {1}
    write("EURUSD", [-1.0, -2.0, -0.5, -1.5, -0.2, -3.0, -1.0])
    assert {s.side for s in fc.family_dollar_carry_basket(d, symbol="EURUSD")} == {-1}
    write("EURUSD", [0.004, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    assert fc.family_dollar_carry_basket(d, symbol="EURUSD", min_afd=0.01) == []


def test_good_and_bad_books_split_the_class(world, monkeypatch):
    d, write = world
    monkeypatch.setattr(xs, "MIN_MEMBERS", 3)        # each book holds half of a 7-member class
    write("EURUSD", RANKED)
    good = fc.family_good_bad_carry(d, symbol="EURUSD", book="good", quantile=0.5)
    bad = fc.family_good_bad_carry(d, symbol="EURUSD", book="bad", quantile=0.5)
    g, b = {s.time for s in good}, {s.time for s in bad}
    assert g or b
    assert not (g & b), "one leg on one day sits in exactly one book"
    assert fc.family_good_bad_carry(d, symbol="EURUSD", book="ugly") == []


def test_mode_one_points_are_a_yield_on_price():
    y = fc._yield(np.array([-6.35]), np.array([1.0]), np.array([1e-5]), np.array([1.17]))
    assert y[0] == pytest.approx(-6.35e-5 * 360 / 1.17)
    assert np.isnan(fc._yield(np.array([1.0]), np.array([2.0]), np.array([1e-5]),
                              np.array([1.0]))[0])


def test_history_gate_waits_for_the_lockbox_floor(world):
    _, write = world
    write("EURUSD", RANKED, start=DAYS - 30)
    st = fc.history_status(floor_days=40)
    assert st["status"] == "PENDING_HISTORY" and st["honest_days"] == 30
    assert st["data_source"] == "mt5:broker_swaps"
    write("EURUSD", RANKED, start=DAYS - 40)
    assert fc.history_status(floor_days=40)["ready"]


def test_registered_wired_and_gated_in_the_seeder():
    for fam in fc.CARRY_FAMILIES:
        assert fo.ORTHOGONAL_FAMILIES[fam] is fc.CARRY_FAMILIES[fam]
        assert fam in sw.NOT_SOURCED_HERE
        assert eb.HISTORY_GATED[fam] is fc.GATES[fam]
        assert fam in eb.SYMBOL_KEYED and eb.CLASS_ONLY[fam]
        assert eb.SOURCE_ID[fam] == "github:paperswithbacktest/awesome-systematic-trading"
        assert eb.grid(fam)
        assert ax.FAMILY_TABLE[fam] == ("carry_rollover", "carry", "market")


def test_commodity_basis_ranks_the_implied_roll_yield(world, monkeypatch):
    d, write = world
    monkeypatch.setattr(xs, "class_of", lambda s: "commodity")
    write("XTIUSD", RANKED)
    lvl = fc.family_commodity_basis_carry(d, symbol="XTIUSD", mode="level")
    assert lvl and {s.side for s in lvl} == {1}
    # a constant basis has no surprise: the residual book ranks nothing it can trust
    res = fc.family_commodity_basis_carry(d, symbol="XTIUSD", mode="residual")
    assert len(res) < len(lvl)
    assert fc.family_commodity_basis_carry(d, symbol="XTIUSD", mode="spread") == []
    assert fc.GATES["commodity_basis_carry"]()["classes"] == ["commodity"]
