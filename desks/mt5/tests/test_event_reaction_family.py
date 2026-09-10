"""The lane 103 instruments were routed to, and the one bar that must never be traded.

`universe_policy` routes single-name equities to a news/earnings lane rather than excluding them
-- 103 of 251 registry symbols, 41% of the universe, assigned to a department that had no staff.
`event_calendar` and `event_density` are readers, `news_desk` idles, `earnability` had no consumer
at all. This family is the executor, and it deliberately produces ordinary `Signal` objects so the
existing gauntlet judges an event hypothesis exactly as harshly as a price one. The event lane
must not become a second, gentler standard.

THE LOAD-BEARING TEST is `test_an_event_cannot_be_traded_on_the_bar_that_contains_it`. The bar
containing a filing OPENED before the filing was public, so entering there buys at a price set
while the information was still private. It is the same silent, flattering leak as dating a
cluster on its transaction date instead of its acceptance time, one layer down -- and if it ever
passes vacuously the family is worthless, because that leak is most of what an event study can
accidentally measure.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.family_event_reaction import MODES, family_event_reaction  # noqa: E402

N = 400
IDX = pd.date_range("2026-06-01", periods=N, freq="h", tz="UTC")


def _bars(seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, N)))
    o = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"open": o, "high": np.maximum(o, close) * 1.001,
                         "low": np.minimum(o, close) * 0.999, "close": close}, index=IDX)


def _event(pos: int, *, symbol: str = "ACME", minute: int = 0) -> dict:
    at = IDX[pos] + pd.Timedelta(minutes=minute)
    return {"kind": "INSIDER_CLUSTER", "at": at.isoformat(), "symbol": symbol, "score": 1.0}


# --------------------------------------------------------------- THE BAR THAT MUST NOT BE TRADED
def test_an_event_cannot_be_traded_on_the_bar_that_contains_it() -> None:
    """THE LEAK, ONE LAYER DOWN. A filing accepted at 10:30 is inside the 10:00 bar -- whose open
    is 10:00, half an hour before the news was public. Entering there buys at a price set while
    the information was private."""
    d = _bars()
    mid = _event(100, minute=30)          # lands inside the bar labelled IDX[100]
    (s,) = family_event_reaction(d, events=[mid], symbol="ACME")
    assert s.time == IDX[101], (
        "the signal was placed on the bar containing the event, which opened before it")
    assert s.time > pd.Timestamp(mid["at"])


def test_an_event_exactly_on_a_bar_open_is_tradeable_on_that_bar() -> None:
    """The boundary case in the other direction: a filing at exactly 10:00 IS knowable when the
    10:00 bar opens, so refusing it would throw away a whole bar of every event."""
    (s,) = family_event_reaction(_bars(), events=[_event(100, minute=0)], symbol="ACME")
    assert s.time == IDX[100]


def test_entry_is_at_the_next_open_like_every_other_family() -> None:
    (s,) = family_event_reaction(_bars(), events=[_event(100)], symbol="ACME")
    assert s.trigger is None and s.wait_bars == 1


# ---------------------------------------------------------------------- it is actually an engine
def test_it_produces_ordinary_signals_the_gauntlet_can_judge() -> None:
    """The event lane must not be a second, gentler standard: same Signal, same engine, same
    gates as a price family."""
    sig = family_event_reaction(_bars(), events=[_event(80), _event(200), _event(300)],
                                symbol="ACME")
    assert len(sig) == 3
    for s in sig:
        assert s.side in (1, -1) and s.stop != s.target and s.ttl_bars > 0
        assert s.tag.startswith("event_")


def test_the_two_modes_are_opposite_claims_about_the_same_event() -> None:
    """Continuation and overshoot are separate hypotheses; a family that chose after seeing the
    data would have tested nothing."""
    d, ev = _bars(), [_event(120)]
    (drift,) = family_event_reaction(d, events=ev, symbol="ACME", mode="drift", side=1)
    (fade,) = family_event_reaction(d, events=ev, symbol="ACME", mode="fade", side=1)
    assert drift.time == fade.time and drift.side == -fade.side
    assert set(MODES) == {"drift", "fade"}


def test_the_side_the_event_implies_is_declared_not_searched() -> None:
    d, ev = _bars(), [_event(120)]
    (buy,) = family_event_reaction(d, events=ev, symbol="ACME", side=1)
    (sell,) = family_event_reaction(d, events=ev, symbol="ACME", side=-1)
    assert buy.side == 1 and sell.side == -1


# ------------------------------------------------------------------------------- refusals
def test_another_issuers_event_is_not_this_instrument_s_news() -> None:
    assert family_event_reaction(_bars(), events=[_event(100, symbol="OTHER")],
                                 symbol="ACME") == []


def test_a_malformed_event_is_skipped_rather_than_guessed() -> None:
    """A row with no timestamp cannot be dated, and dating it by position would invent the one
    field the whole study depends on."""
    bad = [{"symbol": "ACME"}, {"symbol": "ACME", "at": "not a date"},
           {"symbol": "ACME", "at": ""}]
    assert family_event_reaction(_bars(), events=bad, symbol="ACME") == []
    assert family_event_reaction(_bars(), events=[*bad, _event(100)], symbol="ACME")


def test_a_naive_timestamp_is_read_as_utc_rather_than_dropped() -> None:
    """The desk's bars are tz-aware and some producers are not; dropping those would silently
    lose whole sources."""
    naive = {"symbol": "ACME", "at": IDX[100].tz_localize(None).isoformat()}
    assert family_event_reaction(_bars(), events=[naive], symbol="ACME")


@pytest.mark.parametrize(("kw", "why"), [
    ({"events": None}, "no events"),
    ({"events": []}, "an empty feed"),
    ({"mode": "whatever"}, "an unknown mode"),
    ({"side": 0}, "no declared direction"),
    ({"symbol": ""}, "no instrument"),
])
def test_it_refuses_rather_than_inventing_an_event(kw, why) -> None:
    args = {"events": [_event(100)], "symbol": "ACME"}
    args.update(kw)
    assert family_event_reaction(_bars(), **args) == [], why


def test_an_event_after_the_last_bar_produces_nothing() -> None:
    """A filing that lands after the data ends has no bar to trade, and inventing one would be
    the same leak in reverse."""
    late = {"symbol": "ACME", "at": (IDX[-1] + pd.Timedelta(days=5)).isoformat()}
    assert family_event_reaction(_bars(), events=[late], symbol="ACME") == []


def test_a_burst_of_events_is_one_position_not_twelve() -> None:
    """Insiders file separately for one decision, so a cluster arrives as several rows. Trading
    each is reporting one event as twelve and sizing accordingly."""
    burst = [_event(100 + i) for i in range(6)]
    assert len(family_event_reaction(_bars(), events=burst, symbol="ACME",
                                     cooldown_bars=12)) == 1
    assert len(family_event_reaction(_bars(), events=burst, symbol="ACME",
                                     cooldown_bars=0)) > 1
