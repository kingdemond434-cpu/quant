"""The engine charges overnight financing, and charges it at an INSTANT rather than pro rata.

Every certificate this desk minted before 2026-09-15 was judged by an engine whose `Costs` had no
swap field at all. These pin the three things that made that fix wrong in every earlier attempt:
the rollover is an instant, Wednesday counts three, and a field added to a frozen dataclass must
not silently re-price an existing call site.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

BASE = Path(__file__).resolve().parents[2] / "desks" / "mt5"
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from mt5desk.engine import (  # noqa: E402
    ROLLOVER_HOUR_SERVER,
    TRIPLE_SWAP_WEEKDAY,
    Costs,
    rollovers_between,
)


def test_financing_is_charged_at_an_instant_not_pro_rata():
    """Two hours across the rollover pays a night; twenty hours inside one pays nothing.

    This is the whole reason `(t1 - t0).days` is the wrong implementation: it gets both of these
    backwards, and it is the version that looks obviously correct.
    """
    # Server stamps: the rollover is 00:00 (17:00 New York), not 21:00 (2026-10-13).
    short_but_crosses = rollovers_between(pd.Timestamp("2026-09-14 23:00"),
                                          pd.Timestamp("2026-09-15 01:00"))
    long_but_inside = rollovers_between(pd.Timestamp("2026-09-15 00:00"),
                                        pd.Timestamp("2026-09-15 23:00"))
    assert short_but_crosses == 1.0
    assert long_but_inside == 0.0


def test_the_rollover_is_server_midnight_which_is_17_new_york_across_dst():
    """Audit of #269: the bars are broker stamps (New York + 7 h), and the engine charged the night
    at 21:00 server -- 18:00 UTC in summer, three hours before the venue. Server midnight is the
    17:00 New York rollover on both sides of both DST changes, so no date needs special-casing."""
    from libs.regime.session_clock import server_to_utc
    for day, utc_hour in (("2026-10-28", 21),    # EU already on winter time, NY still summer
                          ("2026-11-04", 22),    # both on winter time
                          ("2026-03-11", 21),    # NY on summer time, EU not yet
                          ("2026-01-14", 22), ("2026-07-15", 21)):
        stamp = pd.Timestamp(day) + pd.Timedelta(days=1)      # 00:00 server, ending `day`
        assert server_to_utc([stamp])[0].hour == utc_hour
        assert server_to_utc([stamp])[0].tz_convert("America/New_York").hour == 17
        # one night across server midnight, none across the old 21:00 server stamp
        assert rollovers_between(stamp - pd.Timedelta(hours=1), stamp + pd.Timedelta(hours=1)) >= 1
        assert rollovers_between(pd.Timestamp(day) + pd.Timedelta(hours=20),
                                 pd.Timestamp(day) + pd.Timedelta(hours=22)) == 0.0


def test_wednesday_rollover_carries_three_nights():
    """43% of a week's financing lands on one instant, and a family that holds pays it weekly."""
    wed = pd.Timestamp("2026-09-16")
    assert wed.weekday() == TRIPLE_SWAP_WEEKDAY
    crossing = rollovers_between(wed + pd.Timedelta(hours=ROLLOVER_HOUR_SERVER - 1),
                                 wed + pd.Timedelta(hours=ROLLOVER_HOUR_SERVER + 1))
    assert crossing == 3.0
    # A full week is five rollovers (Monday-Friday server days; the venue is shut at the
    # weekend) with Wednesday counting three: 4 + 3 = 7 -- the seven calendar nights, once each.
    assert rollovers_between(pd.Timestamp("2026-09-14 10:00"),
                             pd.Timestamp("2026-09-21 10:00")) == 7.0
    # Saturday's and Sunday's server days end in no rollover.
    assert rollovers_between(pd.Timestamp("2026-09-19 10:00"),
                             pd.Timestamp("2026-09-21 01:00")) == 0.0


def test_intraday_holds_owe_nothing():
    """The scalp lane must be unaffected, or the fix has re-priced sleeves it does not apply to."""
    assert rollovers_between(pd.Timestamp("2026-09-14 08:00"),
                             pd.Timestamp("2026-09-14 16:30")) == 0.0
    assert rollovers_between(pd.Timestamp("2026-09-14 10:00"),
                             pd.Timestamp("2026-09-14 10:00")) == 0.0


def test_existing_call_sites_are_not_silently_repriced():
    """`Costs(0.48, 3.50, 100.0)` appears at two dozen call sites and must mean what it meant.

    A default that moves an existing number is a silent re-pricing of the live book; the class
    documents that discipline for `quote_per_account` and `spread_pts` and this holds swap to it.
    """
    c = Costs(0.48, 3.50, 100.0)
    assert c.swap_per_lot_per_night == 0.0
    assert c.financing(5.0) == 0.0
    assert c.per_oz_roundtrip() == pytest.approx(0.48 + 3.50 * 2.0)


def test_swap_survives_a_cost_stress_derivation():
    """`stressed()` derives with `replace`, so a field added later is carried by construction.

    The defect this guards is in the desk's history: every stress scenario rebuilt `Costs(...)`
    positionally from three fields, so the fourth reverted to its default and the x3 gate tested
    a candidate at 0.36x. A fifth field must not re-open that.
    """
    c = Costs(0.48, 3.50, 100.0, quote_per_account=185.0, swap_per_lot_per_night=61.76)
    s = c.stressed(3.0)
    assert s.spread_per_lot == pytest.approx(1.44)
    assert s.quote_per_account == 185.0
    # Financing is a published contractual rate: it does not widen when the market does, for the
    # same reason commission is not scaled.
    assert s.swap_per_lot_per_night == 61.76


def test_from_symbol_reads_the_registry_the_desk_already_keeps():
    """248 of 251 symbols carry swap_long/swap_short; the engine simply never looked."""
    meta = {"contract_size": 100.0, "tick_size": 0.01, "tick_value": 1.0,
            "median_spread_pts": 29.0, "swap_long": -61.76, "swap_short": 29.45,
            "swap_mode": 1}
    c = Costs.from_symbol(meta)
    # The worse side, always: the book does not get to pick the cheaper financing afterwards.
    assert c.swap_per_lot_per_night == pytest.approx(61.76 * 0.01 * 100.0)
    # The SAME numbers with no swap_mode are in an unknown unit: UNMEASURED, never points.
    bare = Costs.from_symbol({k: v for k, v in meta.items() if k != "swap_mode"})
    assert bare.swap_per_lot_per_night == 0.0 and bare.swap_unmeasured
    # And a symbol with no swap fields charges zero rather than guessing one.
    assert Costs.from_symbol({"contract_size": 1e5, "tick_size": 1e-5,
                              "tick_value": 1.0}).swap_per_lot_per_night == 0.0


def test_the_live_registry_actually_carries_financing():
    """If this ever fails, the fix above is inert and every re-judge silently charges zero."""
    reg = BASE / "data" / "universe" / "universe.json"
    if not reg.exists():
        pytest.skip("universe registry is not on this box")
    rows = json.loads(reg.read_text(encoding="utf-8"))
    priced = [s for s, v in rows.items()
              if isinstance(v, dict)
              and (abs(float(v.get("swap_long") or 0.0))
                   + abs(float(v.get("swap_short") or 0.0))) > 0]
    assert len(priced) > 200, f"only {len(priced)} of {len(rows)} symbols carry a swap rate"
