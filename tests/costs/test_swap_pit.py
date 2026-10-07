"""The engine charges each night the swap KNOWABLE AT THAT NIGHT, never today's swap backdated.

`Costs.from_symbol` used to read today's `swap_long`/`swap_short` from universe.json and the engine
applied it to every bar since 2018: a look-ahead on the cost side. These pin the repair:

* a night is priced from the newest `families_carry.swap_history` row knowable at its rollover
  (`observed_at` + 3 h, the reader #166/#269 use on the signal side);
* a night with no knowable swap is charged a stand-in -- today's registry value as the floor, or
  the worst side any row KNOWABLE UP TO THAT NIGHT showed, whichever is larger -- and is counted
  UNMEASURED; a later, larger row never reaches an earlier night;
* the run names its swap status, PENDING_HISTORY below the judgeable floor, by name, and UNPRICED
  only when nothing at all prices a night.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

BASE = Path(__file__).resolve().parents[2] / "desks" / "mt5"
for p in (str(BASE), str(BASE.parents[1])):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import engine, families_carry  # noqa: E402
from mt5desk.engine import (  # noqa: E402
    Costs,
    Signal,
    rollover_instants,
    rollovers_between,
    run_backtest,
)

HOUR = 3_600_000_000_000
META = {"symbol": "TESTFX", "contract_size": 100_000.0, "tick_size": 1e-5, "tick_value": 1.0,
        "median_spread_pts": 0.0, "swap_long": -10.0, "swap_short": 2.0}


def _frame(start: str = "2026-09-01", days: int = 20) -> pd.DataFrame:
    idx = pd.date_range(start, periods=24 * days, freq="h")
    return pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}, index=idx)


def _hist(rows: list[tuple[str, float, float]], mode: float = 1.0) -> dict[str, np.ndarray]:
    t = np.array([pd.Timestamp(s).value + families_carry.BROKER_LEAD_NS for s, _, _ in rows],
                 dtype="int64")
    return {"t": t, "lo": np.array([r[1] for r in rows]), "sh": np.array([r[2] for r in rows]),
            "mode": np.full(len(rows), mode), "point": np.full(len(rows), 1e-5)}


@pytest.fixture
def tape(monkeypatch: pytest.MonkeyPatch):
    state: dict[str, Any] = {"hist": {}}
    monkeypatch.setattr(families_carry, "swap_history", lambda: (state["hist"], {}))
    return state


def _rt(costs: Costs) -> float:
    return costs.per_oz_roundtrip() / costs.contract_oz


def _hold(df: pd.DataFrame, at: str, bars: int, costs: Costs):
    sig = Signal(time=pd.Timestamp(at), side=1, stop=0.5, target=2.0, ttl_bars=bars, tag="t")
    return run_backtest(df, [sig], costs)


def test_rollover_instants_list_exactly_what_rollovers_between_counts():
    rng = np.random.default_rng(7)
    base = pd.Timestamp("2026-09-01")
    for _ in range(200):
        a = base + pd.Timedelta(minutes=int(rng.integers(0, 60 * 24 * 30)))
        b = a + pd.Timedelta(minutes=int(rng.integers(0, 60 * 24 * 12)))
        inst, w = rollover_instants(a, b)
        assert float(w.sum()) == rollovers_between(a, b)
        assert all(pd.Timestamp(int(t)).hour == engine.ROLLOVER_HOUR_UTC for t in inst)


def test_a_night_before_any_knowable_row_is_charged_todays_floor_never_zero(tape):
    """No history at all: every night is the stand-in, which is then today's registry value."""
    costs = Costs.from_symbol(META)
    assert costs.swap_symbol == "TESTFX" and costs.swap_registry_known
    assert costs.swap_per_lot_per_night == pytest.approx(10.0 * 1e-5 * 1e5)     # today's
    res = _hold(_frame(), "2026-09-07 10:00", 48, costs)        # Mon -> Wed 10:00: 2 nights
    (t,) = res.trades
    nights = rollovers_between(t.entry_time, t.exit_time)
    assert nights == 2.0
    assert t.r_multiple == pytest.approx(-(_rt(costs) + 10.0e-5 * nights) / 0.5, rel=1e-9)
    assert t.swap_nights_unmeasured == nights
    rep = res.swap_report()
    assert rep["nights_unmeasured"] == nights and rep["nights_unpriced"] == 0.0
    assert rep["status"] in ("PENDING_HISTORY", "UNMEASURED")


def test_the_stand_in_is_the_worst_row_knowable_so_far_never_a_later_one(tape):
    # 30 points observed Tue 2026-09-01 (knowable 03:00), then nothing fresh; a 50-point row is
    # knowable only on Wed 2026-09-16 at 03:00 -- AFTER the Tuesday night being priced.
    tape["hist"] = {"TESTFX": _hist([("2026-09-01 00:00", -30.0, 1.0),
                                     ("2026-09-16 00:00", -50.0, 1.0)])}
    costs = Costs.from_symbol(META)
    res = _hold(_frame(), "2026-09-15 09:00", 24, costs)     # Tue 09-15 night: row 1 is stale
    (t,) = res.trades
    assert t.r_multiple == pytest.approx(-(_rt(costs) + 30.0e-5) / 0.5, rel=1e-9)
    assert res.swap_nights_unmeasured == 1.0


def test_the_stand_in_never_falls_below_todays_registry_value(tape):
    tape["hist"] = {"TESTFX": _hist([("2026-09-01 00:00", -4.0, 1.0)])}     # less than today
    costs = Costs.from_symbol(META)
    res = _hold(_frame(), "2026-09-15 09:00", 24, costs)
    (t,) = res.trades
    assert t.r_multiple == pytest.approx(-(_rt(costs) + 10.0e-5) / 0.5, rel=1e-9)


def test_each_night_is_priced_from_the_row_knowable_at_it_and_not_before(tape):
    # Observed Tue 2026-09-08 17:00 UTC -> knowable 20:00, before that night's 21:00 rollover.
    # Observed Wed 2026-09-09 19:00 UTC -> knowable 22:00, AFTER Wednesday's rollover: Wednesday
    # (triple) must still be priced from Tuesday's row.
    tape["hist"] = {"TESTFX": _hist([("2026-09-08 17:00", -3.0, 1.0),
                                     ("2026-09-09 19:00", -7.0, 1.0)])}
    costs = Costs.from_symbol(META)
    # Enter Mon 10:00, hold to Fri 10:00: Mon (no row yet: today's 10), Tue (3), Wed x3 (still
    # 3), Thu (7).
    res = _hold(_frame(), "2026-09-07 09:00", 96, costs)
    (t,) = res.trades
    expected = 10.0e-5 * 1 + 3.0e-5 * 1 + 3.0e-5 * 3 + 7.0e-5 * 1
    assert t.r_multiple == pytest.approx(-(_rt(costs) + expected) / 0.5, rel=1e-9)
    assert res.swap_nights_unmeasured == 1.0 and res.swap_nights_measured == 5.0


def test_a_stale_row_is_unmeasured(tape):
    tape["hist"] = {"TESTFX": _hist([("2026-09-01 12:00", -3.0, 1.0)])}
    costs = Costs.from_symbol(META)
    res = _hold(_frame(), "2026-09-14 09:00", 30, costs)     # 13 days after the only row
    assert res.swap_nights_measured == 0.0 and res.swap_nights_unmeasured > 0


def test_percent_mode_is_priced_on_the_entry_price(tape):
    tape["hist"] = {"TESTFX": _hist([("2026-09-07 00:00", -3.6, 1.0)], mode=5.0)}
    costs = Costs.from_symbol(META)
    res = _hold(_frame(), "2026-09-08 09:00", 24, costs)     # one Tuesday night
    (t,) = res.trades
    assert t.r_multiple == pytest.approx(-(_rt(costs) + 3.6 / 100 / 360) / 0.5, rel=1e-9)


def test_measured_only_when_every_night_is_knowable_over_the_judgeable_floor(tape, monkeypatch):
    rows = [(str(pd.Timestamp("2026-09-01") + pd.Timedelta(days=d)), -3.0, 1.0)
            for d in range(19)]
    tape["hist"] = {"TESTFX": _hist(rows)}
    costs = Costs.from_symbol(META)
    res = _hold(_frame(), "2026-09-15 09:00", 24, costs)
    assert res.swap_nights_unmeasured == 0.0 and res.swap_nights_measured == 1.0
    monkeypatch.setattr(families_carry, "judgeable_floor", lambda: 19, raising=False)
    assert res.swap_report()["status"] == "MEASURED"
    monkeypatch.setattr(families_carry, "judgeable_floor", lambda: 20, raising=False)
    rep = res.swap_report()
    assert rep["status"] == "PENDING_HISTORY" and rep["honest_days"] == 19
    assert rep["floor_days"] == 20


def test_a_hand_built_cost_keeps_todays_arithmetic_and_reports_unmeasured(tape):
    costs = Costs(spread_per_lot=0.05, commission_per_lot=0.0, contract_oz=1e5,
                  swap_per_lot_per_night=1.0)
    res = _hold(_frame(), "2026-09-07 09:00", 24, costs)
    (t,) = res.trades
    assert t.r_multiple == pytest.approx(-(0.05 / 1e5 + 1.0 / 1e5) / 0.5, rel=1e-9)
    assert res.swap_report()["status"] == "UNMEASURED"


def test_an_intraday_run_has_nothing_to_measure(tape):
    res = _hold(_frame(), "2026-09-07 09:00", 4, Costs.from_symbol(META))
    assert res.swap_report()["status"] == "NO_OVERNIGHT"


def test_the_stressed_variant_keeps_the_point_in_time_fields(tape):
    c = Costs.from_symbol({k: v for k, v in META.items() if k != "swap_long"}).stressed(3.0)
    assert c.swap_symbol == "TESTFX" and c.swap_registry_known


def test_a_night_nothing_can_price_is_unpriced_and_only_that_is_named_so(tape, monkeypatch):
    """No registry swap and no knowable row: no stand-in exists, and the run says UNPRICED.
    With a registry value, or a row knowable before the night, it is evidence, never UNPRICED."""
    monkeypatch.setattr(families_carry, "judgeable_floor", lambda: 100, raising=False)
    bare = {k: v for k, v in META.items() if k not in ("swap_long", "swap_short")}
    costs = Costs.from_symbol(bare)
    assert not costs.swap_registry_known
    rep = _hold(_frame(), "2026-09-07 09:00", 24, costs).swap_report()
    assert rep["status"] == "UNPRICED" and rep["nights_unpriced"] == 1.0
    rep = _hold(_frame(), "2026-09-07 09:00", 24, Costs.from_symbol(META)).swap_report()
    assert rep["status"] == "PENDING_HISTORY" and rep["nights_unpriced"] == 0.0
    tape["hist"] = {"TESTFX": _hist([("2026-08-20 00:00", -5.0, 1.0)])}   # knowable, now stale
    rep = _hold(_frame(), "2026-09-07 09:00", 24, Costs.from_symbol(bare)).swap_report()
    assert rep["status"] == "PENDING_HISTORY" and rep["nights_unpriced"] == 0.0
    tape["hist"] = {"TESTFX": _hist([("2026-09-20 00:00", -5.0, 1.0)])}   # knowable only LATER
    rep = _hold(_frame(), "2026-09-07 09:00", 24, Costs.from_symbol(bare)).swap_report()
    assert rep["status"] == "UNPRICED"


def test_the_cache_stamp_moves_only_when_a_row_that_matters_arrives(tape, monkeypatch):
    tape["hist"] = {"TESTFX": _hist([("2026-09-01 12:00", -3.0, 1.0)])}
    a = engine.swap_cache_stamp("TESTFX", "2026-09-05")
    tape["hist"] = {"TESTFX": _hist([("2026-09-01 12:00", -3.0, 1.0),
                                     ("2026-09-06 12:00", -9.0, 1.0)])}
    assert engine.swap_cache_stamp("TESTFX", "2026-09-05") == a      # knowable after the series
    tape["hist"] = {"TESTFX": _hist([("2026-09-01 12:00", -3.0, 1.0),
                                     ("2026-09-03 12:00", -9.0, 1.0)])}
    assert engine.swap_cache_stamp("TESTFX", "2026-09-05") != a      # inside it
    b = engine.swap_cache_stamp("TESTFX", "2026-09-05")
    monkeypatch.setattr(engine, "ENGINE_COST_VERSION", "next")
    assert engine.swap_cache_stamp("TESTFX", "2026-09-05") != b


# ------------------------------------------------------------- the other readers of the swap
def test_the_carry_side_is_the_side_knowable_at_each_bar(tape):
    tape["hist"] = {"TESTFX": _hist([("2026-09-03 00:00", 2.0, -5.0),
                                     ("2026-09-06 00:00", -5.0, 3.0)])}
    t = pd.date_range("2026-09-01", periods=24 * 12, freq="h")
    side = families_carry.carry_side_asof("TESTFX", t.as_unit("ns").asi8)
    k1 = pd.Timestamp("2026-09-03 03:00")
    k2 = pd.Timestamp("2026-09-06 03:00")
    gone = pd.Timestamp("2026-09-10 03:00")          # 96 h after the last row: stale
    assert (side[t < k1] == 0).all()                       # never today's side backdated
    assert (side[(t >= k1) & (t < k2)] == 1).all()
    assert (side[(t >= k2) & (t <= gone)] == -1).all()
    assert (side[t > gone] == 0).all()                    # a stale row names no side


def test_mass_screen_charges_and_sides_point_in_time(tape):
    from research import mass_screen as ms
    tape["hist"] = {"TESTFX": _hist([("2026-09-05 00:00", 2.0, -30.0)])}
    t = pd.date_range("2026-09-01", periods=24 * 20, freq="h")
    rate, side = ms.swap_pit_arrays("TESTFX", t.as_unit("ns").asi8, np.ones(t.size), 10.0e-5)
    knowable = t >= pd.Timestamp("2026-09-05 03:00")
    stale = t > pd.Timestamp("2026-09-09 03:00")
    assert np.allclose(rate[~knowable], 10.0e-5)                         # today's floor
    assert np.allclose(rate[knowable & ~stale], 30.0e-5)                 # the knowable row
    assert np.allclose(rate[stale], 30.0e-5)                             # worst knowable so far
    assert (side[~knowable] == 0).all() and (side[knowable & ~stale] == 1).all()

    class _P:
        cut = int(np.searchsorted(t.as_unit("ns").asi8, pd.Timestamp("2026-09-04").value))
        carry_pit = side
    assert ms.carry_sides(_P()) == []           # the training window never saw a paying side
    _P.cut = t.size
    assert ms.carry_sides(_P()) == [1]
