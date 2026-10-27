"""The engine's per-hour spread table (`Costs.spread_per_lot_by_hour`), pinned inside the MT5 suite.

The money-path coverage floor measures `mt5desk/engine.py` from `desks/mt5/tests` only, so the
table's branches -- the 24- and 168-slot lookups, the malformed-table fallback, the stress scale
and the ask-crossing leg in `run_backtest` -- are pinned here as well as in tests/costs.
"""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.engine import Costs, Signal, run_backtest, spread_at  # noqa: E402

META = {"contract_size": 100000.0, "tick_size": 0.00001, "tick_value": 1.0,
        "median_spread_pts": 10.0}


def _bars(n: int = 200, start: str = "2024-01-02 00:00") -> pd.DataFrame:
    idx = pd.date_range(start, periods=n, freq="h", tz="UTC")
    px = [1.0 + 0.0001 * (i % 7) for i in range(n)]
    return pd.DataFrame({"open": px, "high": [p + 0.002 for p in px],
                         "low": [p - 0.002 for p in px], "close": px,
                         "spread": 0, "tick_volume": 100}, index=idx)


def test_no_table_is_the_flat_spread():
    c = Costs.from_symbol(META)
    assert spread_at(c, "2024-01-02 05:00") == c.spread_per_lot


def test_24_and_168_slot_tables_read_their_own_slot():
    base = Costs.from_symbol(META)
    t24 = replace(base, spread_per_lot_by_hour=tuple(float(h) for h in range(24)))
    assert spread_at(t24, pd.Timestamp("2024-01-02 07:30", tz="UTC")) == 7.0
    t168 = replace(base, spread_per_lot_by_hour=tuple(float(i) for i in range(168)))
    # 2024-01-03 is a Wednesday (dayofweek 2): slot 2*24 + 5
    assert spread_at(t168, pd.Timestamp("2024-01-03 05:00", tz="UTC")) == 53.0


def test_a_malformed_table_never_charges_less_than_flat():
    base = Costs.from_symbol(META)
    cheap = replace(base, spread_per_lot_by_hour=(0.01,) * 5)
    assert spread_at(cheap, "2024-01-02 00:00") == base.spread_per_lot
    dear = replace(base, spread_per_lot_by_hour=(base.spread_per_lot * 9,) * 5)
    assert spread_at(dear, "2024-01-02 00:00") == base.spread_per_lot * 9


def test_stress_scales_the_table_and_leaves_none_alone():
    base = Costs.from_symbol(META)
    assert base.stressed(3.0).spread_per_lot_by_hour is None
    c = replace(base, spread_per_lot_by_hour=(2.0,) * 24)
    assert c.stressed(3.0).spread_per_lot_by_hour == (6.0,) * 24


def test_a_constant_table_equals_the_flat_charge_and_the_ask_leg_pays_its_slot():
    df = _bars()
    flat = Costs.from_symbol(META)
    const = replace(flat, spread_per_lot_by_hour=(flat.spread_per_lot,) * 24)
    zero = replace(flat, spread_per_lot_by_hour=(0.0,) * 24)
    tab = [1.0] * 24
    tab[1] = 101.0
    dear = replace(flat, spread_per_lot_by_hour=tuple(tab))
    for side, stop, target in ((1, 0.99, 5.0), (-1, 1.01, 0.5)):
        sig = [Signal(time=df.index[0], side=side, stop=stop, target=target, ttl_bars=3, tag="t")]
        r_flat = run_backtest(df, sig, flat).trades[0].r_multiple
        assert run_backtest(df, sig, const).trades[0].r_multiple == pytest.approx(r_flat,
                                                                                 abs=1e-12)
        tr = run_backtest(df, sig, dear).trades[0]
        paid = 101.0 if side > 0 else tab[tr.exit_time.hour]
        diff = run_backtest(df, sig, zero).trades[0].r_multiple - tr.r_multiple
        assert diff == pytest.approx(paid / flat.contract_oz / abs(tr.entry - stop), rel=1e-9)
