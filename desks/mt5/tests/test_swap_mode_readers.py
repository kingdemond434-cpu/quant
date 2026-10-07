"""Every reader of the swap fields prices swap_mode 5 (annual percent) and refuses an unknown unit.

After `engine.Costs.from_symbol` learned swap_mode (2026-10-07), a mode-5 symbol's rate lives in
`swap_per_lot_per_price` and `swap_per_lot_per_night` is 0.0. A reader that only looked at the
latter would have gone from charging too little to charging NOTHING. One mode-5 case per reader,
on GER40's real terms (contract 1, tick 0.01 = 0.01 EUR, worse side 4.40 %/yr): one night at
26,262.76 is 26,262.76 x 4.40 / 100 / 360 = 3.209893 EUR per lot.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk.engine import Costs, Signal, run_backtest  # noqa: E402

PRICE = 26262.76
NIGHT = PRICE * 4.4 / 100.0 / 360.0          # 3.209893 EUR per lot per night
GER40 = {"symbol": "GER40", "contract_size": 1.0, "tick_size": 0.01, "tick_value": 0.01,
         "median_spread_pts": 80.0, "swap_long": -4.4, "swap_short": 0.18,
         "currency_profit": "EUR", "swap_mode": 5}
UNKNOWN = {**GER40, "symbol": "NOT_A_SYMBOL", "swap_mode": None}


def _flat_bars(days: int = 6, price: float = PRICE) -> pd.DataFrame:
    idx = pd.date_range("2026-09-14", periods=24 * days, freq="h", tz="UTC")
    px = np.full(len(idx), price)
    df = pd.DataFrame({"open": px, "high": px + 1.0, "low": px - 1.0, "close": px,
                       "tick_volume": 100.0}, index=idx)
    df.index.name = "time"
    return df


def test_shared_conversion_prices_mode5_and_refuses_without_a_price() -> None:
    from mt5desk.engine import swap_night_points, swap_night_quote
    q, why = swap_night_quote(GER40, -4.4, PRICE)
    assert why is None and q == pytest.approx(-NIGHT)
    assert swap_night_quote(GER40, -4.4, None)[0] is None
    assert "UNMEASURED" in str(swap_night_quote(UNKNOWN, -4.4, PRICE)[1])
    # mode 1: points-equivalent IS the raw number
    xau = {"symbol": "XAUUSD", "contract_size": 100.0, "tick_size": 0.01, "tick_value": 1.0,
           "swap_mode": 1}
    assert swap_night_points(xau, -61.76)[0] == pytest.approx(-61.76)
    assert swap_night_points(GER40, -4.4, PRICE)[0] == pytest.approx(-NIGHT / 0.01)


# --- mass_screen ------------------------------------------------------------------------------
def test_mass_screen_charges_mode5_at_the_bars_own_price() -> None:
    import mass_screen as MS
    cm = MS.cost_model(GER40)
    assert cm["swap_price"] == 0.0 and cm["swap_unmeasured"] is None
    assert cm["swap_rate"] * PRICE == pytest.approx(NIGHT)
    df = _flat_bars(40)
    free = MS.Prepared("GER40", df, {**GER40, "swap_mode": 0}, {}, use_bar_spread=False)
    paid = MS.Prepared("GER40", df, GER40, {}, use_bar_spread=False)
    h = 24                                                     # every 24h fire holds a night
    nights = MS.nights_between(paid.t_ns[1: 101], paid.t_ns[1 + h: 101 + h])
    d = free.R1[h][0, :100] - paid.R1[h][0, :100]
    ok = np.isfinite(d) & (nights > 0)
    assert ok.any()
    # strictly more expensive, and zero on fires that cross no rollover
    assert (d[ok] > 0).all()
    assert np.allclose(d[np.isfinite(d) & (nights == 0)], 0.0)


def test_mass_screen_unknown_unit_is_nan_overnight_never_free() -> None:
    import mass_screen as MS
    cm = MS.cost_model(UNKNOWN)
    assert cm["swap_unmeasured"] and "UNMEASURED" in cm["swap_unmeasured"]
    P = MS.Prepared("X", _flat_bars(40), UNKNOWN, {}, use_bar_spread=False)
    h = 24
    nights = MS.nights_between(P.t_ns[1: 101], P.t_ns[1 + h: 101 + h])
    assert np.isnan(P.R1[h][0, :100][nights > 0]).all()


# --- swap_rejudge -----------------------------------------------------------------------------
def test_swap_rejudge_prices_mode5_and_names_the_unpriceable(monkeypatch) -> None:
    import swap_rejudge as SR
    per_unit, px, why = SR.per_unit_night_swap("GER40", GER40, price=PRICE)
    assert px == PRICE and per_unit == pytest.approx(NIGHT)      # contract 1
    monkeypatch.setattr(SR, "_last_close", lambda _s: None)
    per_unit, px, why = SR.per_unit_night_swap("GER40", GER40)
    assert per_unit is None and "UNMEASURED" in why
    per_unit, _px, why = SR.per_unit_night_swap("NOT_A_SYMBOL", UNKNOWN, price=PRICE)
    assert per_unit is None and "UNMEASURED" in why


# --- synthetic_regimes / swap_world -----------------------------------------------------------
def test_swap_world_stress_charges_the_price_linked_part() -> None:
    from libs.tiers import swap_world
    t = SimpleNamespace(r_multiple=1.0, entry=PRICE, stop=PRICE - 100.0, units=1.0,
                        entry_time=pd.Timestamp("2026-09-14 10:00", tz="UTC"),
                        exit_time=pd.Timestamp("2026-09-16 10:00", tz="UTC"))
    flat, _ = swap_world.stress_r([t], swap_per_lot=0.0, spread_per_lot=0.0, contract=1.0)
    rate, n = swap_world.stress_r([t], swap_per_lot=0.0, spread_per_lot=0.0, contract=1.0,
                                  swap_per_lot_per_price=4.4 / 100.0 / 360.0)
    assert flat == [1.0]
    assert n == 1 and rate[0] < 1.0
    nights = swap_world.stressed_nights(t.entry_time, t.exit_time)
    base = swap_world.baseline_nights(t.entry_time, t.exit_time)
    want = 1.0 - max(0.0, swap_world.SWAP_MULT * nights - base) * NIGHT / 100.0
    assert rate[0] == pytest.approx(want)


def test_synthetic_regimes_swap_world_runs_on_mode5_and_refuses_unknown() -> None:
    import synthetic_regimes as SRG
    df = _flat_bars(6)
    sig = Signal(time=df.index[5], side=1, stop=PRICE - 100.0, target=PRICE + 10_000.0,
                 ttl_bars=60, tag="t")
    world = SRG.World(signal_bars=df, exec_bars=df)
    out = SRG._swap_replay(world, [sig], (run_backtest, Costs), GER40, "GER40")
    assert isinstance(out, list) and out, out           # was "no swap terms" at 0.0
    base = run_backtest(df, [sig], Costs.from_symbol(GER40)).trades[0].r_multiple
    assert out[0] < base
    refused = SRG._swap_replay(SRG.World(signal_bars=df, exec_bars=df), [sig],
                               (run_backtest, Costs), UNKNOWN, "NOT_A_SYMBOL")
    assert isinstance(refused, str) and "UNMEASURED" in refused


# --- execution_resolver -----------------------------------------------------------------------
def test_execution_resolver_swap_is_in_the_modes_unit(monkeypatch) -> None:
    import execution_resolver as ER
    monkeypatch.setattr(ER, "_last_close", lambda _s: PRICE)
    q, why = ER._swap_quote_per_lot(GER40, "GER40", 1)
    assert why is None and q == pytest.approx(-NIGHT)
    # mode 1 is POINTS, not currency: the old currency reading only coincided with the truth
    # on a pair whose tick_size x contract is 1 (EURUSD); on a JPY pair it was 100x out.
    jpy = {"symbol": "X", "contract_size": 100000.0, "tick_size": 0.001, "tick_value": 0.64,
           "swap_long": 20.0, "swap_short": -40.0, "swap_mode": 1}
    q, _w = ER._swap_quote_per_lot(jpy, "X", 1)
    assert q == pytest.approx(20.0 * 0.001 * 100000.0)      # 2,000 JPY, not 20
    monkeypatch.setattr(ER, "_last_close", lambda _s: None)
    q, why = ER._swap_quote_per_lot(GER40, "GER40", 1)
    assert q is None and "UNMEASURED" in str(why)


# --- cost_to_edge -----------------------------------------------------------------------------
def test_cost_to_edge_worse_side_is_points_equivalent() -> None:
    import cost_to_edge as CE
    info = SimpleNamespace(swap_long=-4.4, swap_short=0.18, swap_mode=5, point=0.01,
                           trade_contract_size=1.0, trade_tick_size=0.01, trade_tick_value=0.01,
                           currency_profit="EUR", currency_base="EUR", currency_margin="EUR")
    pts, why = CE._swap_points_worse_side("GER40", info, PRICE)
    assert why is None and pts == pytest.approx(NIGHT / 0.01)     # ~321 points, not 4.4
    mode1 = SimpleNamespace(**{**vars(info), "swap_mode": 1})
    assert CE._swap_points_worse_side("GER40", mode1, PRICE)[0] == pytest.approx(4.4)
    odd = SimpleNamespace(**{**vars(info), "swap_mode": 9})
    pts, why = CE._swap_points_worse_side("GER40", odd, PRICE)
    assert pts is None and "UNMEASURED" in str(why)


# --- actor_pressure ---------------------------------------------------------------------------
def test_actor_pressure_carry_chaser_reads_mode5_in_points_equivalent() -> None:
    import actor_pressure as AP
    trend = {"status": "UNMEASURED"}
    got = AP._carry_chaser("GER40", {"GER40": GER40}, trend, price=PRICE)
    assert got["status"] == "MEASURED"
    assert got["swap_long"] == pytest.approx(-NIGHT / 0.01)
    assert AP._carry_chaser("GER40", {"GER40": GER40}, trend)["status"] == "UNMEASURED"
    m1 = {**GER40, "swap_mode": 1}
    assert AP._carry_chaser("GER40", {"GER40": m1}, trend)["swap_long"] == pytest.approx(-4.4)


# --- exposure_decomposition -------------------------------------------------------------------
def test_exposure_decomposition_carry_is_mode_aware(tmp_path, monkeypatch) -> None:
    import json

    import exposure_decomposition as ed
    monkeypatch.setattr(ed, "DESK", tmp_path)
    ed._BARS.clear()
    uni = tmp_path / "data" / "universe"
    uni.mkdir(parents=True)
    idx = pd.date_range("2025-01-01", periods=200, freq="D", tz="UTC", name="time")
    for sym, px in (("GER40", PRICE), ("PTS", 1.10)):
        c = np.full(len(idx), px)
        pd.DataFrame({"open": c, "high": c, "low": c, "close": c, "tick_volume": 1},
                     index=idx).to_parquet(uni / f"{sym}_H1.parquet")
    pts = {"symbol": "PTS", "contract_size": 1e5, "tick_size": 1e-5, "tick_value": 1.0,
           "swap_long": -6.0, "swap_short": 2.0, "swap_mode": 1, "median_spread_pts": 1.0}
    (uni / "universe.json").write_text(json.dumps({"GER40": GER40, "PTS": pts}), "utf-8")
    carry, _liq, meta = ed._characteristics(["GER40", "PTS"])
    ed._BARS.clear()
    assert set(carry) == {"GER40", "PTS"}
    # raw: PTS -8 points, GER40 -4.58 PERCENT. Points-equivalent: GER40 is ~334 points.
    assert abs(carry["GER40"]) > abs(carry["PTS"])
    assert "swap_mode" in meta["carry"]["basis"]


# --- libs/costs/mt5_calibration ---------------------------------------------------------------
def test_mt5_calibration_modes() -> None:
    from libs.costs.errors import CostError
    from libs.costs.mt5_calibration import calibrate
    from libs.data.instruments import AssetClass
    info = SimpleNamespace(spread=80, point=0.01, trade_contract_size=1.0, swap_long=-4.4,
                           swap_short=0.18, swap_mode=5)
    p = calibrate("GER40", info, asset_class=AssetClass.INDEX, price=PRICE)
    assert p.swap_long_per_lot_per_night == pytest.approx(NIGHT)       # cost = positive
    with pytest.raises(CostError, match="UNMEASURED"):
        calibrate("GER40", info, asset_class=AssetClass.INDEX)
    off = SimpleNamespace(**{**vars(info), "swap_mode": 0})
    assert calibrate("GER40", off, asset_class=AssetClass.INDEX).swap_long_per_lot_per_night == 0
    pts = SimpleNamespace(**{**vars(info), "swap_mode": 1})
    assert calibrate("GER40", pts, asset_class=AssetClass.INDEX
                     ).swap_long_per_lot_per_night == pytest.approx(4.4 * 0.01)
