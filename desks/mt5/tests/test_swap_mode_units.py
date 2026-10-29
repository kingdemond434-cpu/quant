"""Every MT5 swap_mode is priced in its own unit (2026-10-07).

`engine.Costs.from_symbol` read every registry swap as POINTS. 138 of the 248 swap-carrying
symbols are swap_mode 5, where the number is an ANNUAL PERCENT of notional: GER40's 4.40 was
charged as 4.40 points x 0.01 x 1 = 0.044 EUR a night against a real 3.21. These pin one case per
mode, with hand-computed numbers on real registry contract terms, and the whole registry.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

BASE = Path(__file__).resolve().parents[1]
for _p in (str(BASE), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import engine  # noqa: E402
from mt5desk.engine import Costs, Signal, rollover_price_nights, rollovers_between  # noqa: E402

#: GER40 as the registry and the venue's contract terms carry it: contract 1, tick 0.01 = 0.01 EUR,
#: swap_long -4.40 / swap_short +0.18, mode 5. The price is carry_state.json's `price_used`.
GER40 = {"symbol": "GER40", "contract_size": 1.0, "tick_size": 0.01, "tick_value": 0.01,
         "median_spread_pts": 80.0, "swap_long": -4.4, "swap_short": 0.18,
         "currency_profit": "EUR"}
GER40_PRICE = 26262.76
#: XAUUSD: contract 100, tick 0.01, swap_long -61.76 points, mode 1.
XAU = {"symbol": "XAUUSD", "contract_size": 100.0, "tick_size": 0.01,
       "tick_value": 0.8620763972103207, "median_spread_pts": 29.0, "swap_long": -61.76,
       "swap_short": 29.45, "currency_profit": "USD"}


def _with(meta: dict, **kw) -> dict:
    return {**meta, **kw}


def test_mode0_disabled_charges_nothing() -> None:
    c = Costs.from_symbol(_with(XAU, swap_mode=0))
    assert c.swap_per_lot_per_night == 0.0 and c.swap_per_lot_per_price is None
    assert c.swap_unmeasured is None and not c.charges_swap


def test_mode1_points_is_points_times_point_times_contract() -> None:
    c = Costs.from_symbol(_with(XAU, swap_mode=1))
    # 61.76 points x 0.01 x 100 oz = 61.76 USD per lot per night: unchanged from before the fix.
    assert c.swap_per_lot_per_night == pytest.approx(61.76)
    assert c.swap_per_lot_per_price is None
    assert c.financing(3.0) == pytest.approx(185.28)


def test_mode2_base_currency_money() -> None:
    # EURUSD-like pair: 5.0 EUR a night is 5.0 x price USD, price-linked.
    pair = {"symbol": "X", "contract_size": 1e5, "tick_size": 1e-5, "tick_value": 1.0,
            "swap_long": -5.0, "swap_short": 1.0, "currency_base": "EUR",
            "currency_profit": "USD", "swap_mode": 2}
    c = Costs.from_symbol(pair)
    assert c.swap_per_lot_per_night == 0.0 and c.swap_per_lot_per_price == pytest.approx(5.0)
    assert c.financing(1.0, price_nights=1.10) == pytest.approx(5.5)
    # A CFD whose base IS the profit currency: the money is already in quote.
    cfd = _with(pair, currency_base="USD")
    assert Costs.from_symbol(cfd).swap_per_lot_per_night == pytest.approx(5.0)


def test_mode3_margin_currency_money() -> None:
    m = {"symbol": "X", "contract_size": 1.0, "tick_size": 0.01, "tick_value": 0.01,
         "swap_long": -2.0, "swap_short": 0.5, "currency_margin": "EUR",
         "currency_profit": "EUR", "swap_mode": 3}
    assert Costs.from_symbol(m).swap_per_lot_per_night == pytest.approx(2.0)
    # Margin in a currency neither profit nor a pair's base: no route to quote -> UNMEASURED.
    odd = Costs.from_symbol(_with(m, currency_margin="JPY"))
    assert odd.swap_unmeasured and "UNMEASURED" in odd.swap_unmeasured
    assert not odd.charges_swap


def test_mode4_deposit_currency_money_is_carried_into_quote() -> None:
    # 10 account-ccy per night on a symbol whose quote_per_account is 0.01*100/0.8620... USD/EUR.
    c = Costs.from_symbol(_with(XAU, swap_long=-10.0, swap_short=1.0, swap_mode=4))
    qpa = 100.0 * 0.01 / 0.8620763972103207
    assert c.swap_per_lot_per_night == pytest.approx(10.0 * qpa)
    # ... and back out through quote_per_account it is exactly 10 in account currency.
    assert c.swap_per_lot_per_night / c.quote_per_account == pytest.approx(10.0)
    no_tv = Costs.from_symbol(_with(XAU, tick_value=0.0, swap_mode=4))
    assert no_tv.swap_unmeasured and not no_tv.charges_swap


def test_mode5_annual_percent_of_the_current_price_hand_computed() -> None:
    """GER40: 26,262.76 x 1 x 4.40 / 100 / 360 = 3.209893 EUR per lot per night."""
    c = Costs.from_symbol(_with(GER40, swap_mode=5))
    assert c.swap_per_lot_per_night == 0.0
    assert c.swap_per_lot_per_price == pytest.approx(4.4 / 100.0 / 360.0)
    assert c.swap_price_basis == "rollover"
    one = c.financing(1.0, price_nights=GER40_PRICE)
    assert one == pytest.approx(3.209893, abs=1e-6)
    # The OLD reading -- 4.40 points x 0.01 x 1 -- was 0.044: 73x too cheap.
    assert one / (4.4 * 0.01 * 1.0) == pytest.approx(72.95, abs=0.01)
    # In account currency it agrees with carry_state's own mode-5 conversion to the cent.
    from carry_state import DAY_COUNT, money_per_lot_night
    assert DAY_COUNT == engine.SWAP_DAY_COUNT
    money, _why = money_per_lot_night(-4.4, {"swap_mode": 5, "tick_value": 0.01,
                                             "tick_size": 0.01}, GER40_PRICE)
    assert money is not None and -money == pytest.approx(one / c.quote_per_account)
    with pytest.raises(ValueError):
        c.financing(1.0)          # a percent of nothing is refused, never charged as zero


def test_mode6_interest_on_the_open_price() -> None:
    c = Costs.from_symbol(_with(GER40, swap_mode=6))
    assert c.swap_price_basis == "open"
    assert c.swap_per_lot_per_price == pytest.approx(4.4 / 100.0 / 360.0)


@pytest.mark.parametrize("mode", [7, 8])
def test_modes7_8_reopen_is_a_points_move(mode: int) -> None:
    c = Costs.from_symbol(_with(XAU, swap_mode=mode))
    assert c.swap_per_lot_per_night == pytest.approx(61.76)


@pytest.mark.parametrize("mode", [9, -1, "x"])
def test_unknown_mode_is_unmeasured_by_name_never_points(mode: object) -> None:
    c = Costs.from_symbol(_with(XAU, swap_mode=mode))
    assert c.swap_unmeasured and "UNMEASURED" in c.swap_unmeasured
    assert c.swap_per_lot_per_night == 0.0 and c.swap_per_lot_per_price is None


def test_absent_mode_unrecorded_symbol_is_unmeasured_not_points() -> None:
    meta = {k: v for k, v in XAU.items() if k != "symbol"}
    c = Costs.from_symbol(meta)
    assert c.swap_unmeasured and "unit unknown" in c.swap_unmeasured
    assert c.swap_per_lot_per_night == 0.0


def test_absent_mode_falls_back_to_the_recorded_contract_terms() -> None:
    mode, src = engine.swap_mode_of({"symbol": "GER40"})
    if mode is None:
        pytest.skip("carry_state.json is not on this box")
    assert mode == 5 and "contract_terms" in src
    assert engine.swap_mode_of({"symbol": "GER40", "swap_mode": 1}) == (1, "registry")


def test_cost_hash_is_unchanged_for_points_symbols() -> None:
    """New fields are None on a mode-1 symbol, so no forward clock on one re-identifies."""
    import sleeve_registry as reg
    new = Costs.from_symbol(_with(XAU, swap_mode=1))
    legacy = Costs(spread_per_lot=new.spread_per_lot, commission_per_lot=new.commission_per_lot,
                   contract_oz=new.contract_oz, quote_per_account=new.quote_per_account,
                   swap_per_lot_per_night=61.76 * 0.01 * 100.0)
    assert reg.cost_hash(new) == reg.cost_hash(legacy)


def test_price_nights_uses_each_nights_price_and_counts_triples() -> None:
    idx = pd.date_range("2026-09-14 00:00", periods=24 * 4, freq="h")   # Mon..Thu
    px = np.arange(len(idx), dtype=float) + 100.0
    idx_ns = np.asarray(idx.as_unit("ns").asi8, dtype="int64")
    t0, t1 = idx[10], idx[-1]                    # Mon 10:00 -> Thu 23:00
    got = rollover_price_nights(idx_ns, px, 10, len(idx) - 1, t0, t1)
    # Rollovers Mon/Tue/Wed/Thu 21:00; the bar that opened before each is 20:00 of that day.
    want = sum(w * px[24 * d + 20] for d, w in enumerate([1, 1, 3, 1]))
    assert got == pytest.approx(want)
    assert rollovers_between(t0, t1) == 6.0
    flat = np.full(len(idx), 7.0)
    assert rollover_price_nights(idx_ns, flat, 10, len(idx) - 1, t0, t1) == pytest.approx(42.0)


def test_backtest_charges_mode5_at_the_nightly_price() -> None:
    idx = pd.date_range("2026-09-14 00:00", periods=24 * 5, freq="h")
    price = np.full(len(idx), GER40_PRICE)
    df = pd.DataFrame({"open": price, "high": price + 1, "low": price - 1, "close": price},
                      index=idx)
    sig = Signal(time=idx[5], side=1, stop=GER40_PRICE - 100.0,
                 target=GER40_PRICE + 10_000.0, ttl_bars=60, tag="t")
    base = Costs.from_symbol(_with(GER40, swap_mode=0))
    m5 = Costs.from_symbol(_with(GER40, swap_mode=5))
    r0 = engine.run_backtest(df, [sig], base).trades[0]
    r5 = engine.run_backtest(df, [sig], m5).trades[0]
    nights = rollovers_between(r5.entry_time, r5.exit_time)
    assert nights > 0
    # Each night costs 3.209893 EUR on a 100-point stop, contract 1: 0.0320989 R a night.
    assert (r0.r_multiple - r5.r_multiple) == pytest.approx(nights * 3.209893 / 100.0, abs=1e-6)


def test_every_swap_carrying_registry_row_is_correctly_moded() -> None:
    """All 248 rows through from_symbol: none unmeasured, none read in the wrong unit."""
    reg = BASE / "data" / "universe" / "universe.json"
    if not reg.exists():
        pytest.skip("universe registry is not on this box")
    rows = json.loads(reg.read_text(encoding="utf-8"))
    swap_rows = {s: v for s, v in rows.items() if isinstance(v, dict) and "swap_long" in v}
    seen: dict[int, int] = {}
    for sym, meta in swap_rows.items():
        mode, _src = engine.swap_mode_of(meta)
        c = Costs.from_symbol(meta)
        assert mode is not None, f"{sym}: no swap_mode anywhere"
        assert c.swap_unmeasured is None, f"{sym}: {c.swap_unmeasured}"
        seen[mode] = seen.get(mode, 0) + 1
        worse = max(abs(float(meta.get("swap_long") or 0)), abs(float(meta.get("swap_short") or 0)))
        if mode == engine.SWAP_MODE_INTEREST_CURRENT:
            # a percent is never a points amount
            assert c.swap_per_lot_per_night == 0.0, sym
            assert c.swap_per_lot_per_price == pytest.approx(
                float(meta["contract_size"]) * worse / 100.0 / 360.0), sym
        elif mode == engine.SWAP_MODE_POINTS:
            assert c.swap_per_lot_per_price is None, sym
            assert c.swap_per_lot_per_night == pytest.approx(
                worse * float(meta["tick_size"]) * float(meta["contract_size"])), sym
    assert len(swap_rows) >= 248
    assert seen.get(5, 0) >= 138 and seen.get(1, 0) >= 110, seen


def test_the_registry_writer_now_records_the_unit() -> None:
    """The box's registry producers carry swap_mode (0 included) and the 2/3 currencies."""
    from mt5desk.universe_registry import cost_fields_from_symbol_info

    class _SI:
        trade_tick_value = 0.01
        currency_profit = "EUR"
        currency_base = "EUR"
        currency_margin = "EUR"

        def __init__(self, mode: object) -> None:
            self.swap_mode = mode

    assert cost_fields_from_symbol_info(_SI(5))["swap_mode"] == 5
    assert cost_fields_from_symbol_info(_SI(0))["swap_mode"] == 0
    assert "swap_mode" not in cost_fields_from_symbol_info(_SI(None))
    assert "swap_mode" not in cost_fields_from_symbol_info(_SI(True))
    out = cost_fields_from_symbol_info(_SI(1))
    assert out["currency_base"] == "EUR" and out["currency_margin"] == "EUR"
