"""The E8 venue and its guard, tested WITHOUT a funded account and without credentials.

An adapter whose first real test is a real order on a $100,000 evaluation is not tested. Every
case below runs against a fake SDK and a fake equity, which is the reason the adapter and the
guard are two files instead of one.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from prop import e8_guard as g  # noqa: E402
from prop.tradelocker_venue import (  # noqa: E402
    Credentials,
    TradeLockerVenue,
    VenueError,
    load_credentials,
)


# ------------------------------------------------------------------------------ the fake venue
class FakeAPI:
    def __init__(self, instruments=None, quotes=None, state=None, details=None, reject=False):
        self.instruments = instruments if instruments is not None else [
            {"name": "EURUSD", "tradableInstrumentId": 1},
            {"name": "XAU/USD", "tradableInstrumentId": 2},
            {"name": "AUDNZD", "tradableInstrumentId": 3},
        ]
        self._quotes = quotes or {1: {"bp": 1.1000, "ap": 1.1001},
                                  2: {"bp": 2400.0, "ap": 2400.3},
                                  3: {"bp": 1.0800, "ap": 1.0802}}
        self._state = state or {"balance": 100_000.0, "openNetPnL": -250.0}
        self._details = details or {1: {"minLot": 0.01}, 2: {"minLot": 0.01}, 3: {"minLot": 0.01}}
        self.sent: list[dict] = []
        self.reject = reject

    def get_all_instruments(self):
        return list(self.instruments)

    def get_quotes(self, instrument_id):
        return self._quotes[instrument_id]

    def get_account_state(self):
        return dict(self._state)

    def get_instrument_details(self, instrument_id, locale="en"):
        return dict(self._details[instrument_id])

    def get_all_positions(self):
        return []

    def create_order(self, **kw):
        if self.reject:
            return None
        self.sent.append(kw)
        return 1000 + len(self.sent)

    def close_position(self, position_id=0, close_quantity=0, order_id=0):
        return True

    def close_all_positions(self):
        return True


def _venue(**kw) -> TradeLockerVenue:
    return TradeLockerVenue(api=FakeAPI(**kw)).connect()


# ------------------------------------------------------------------------------ credentials
def test_credentials_never_render_themselves(capsys) -> None:
    """THE RULE IS THAT NO TOOL EVER PRINTS A KEY, and a dataclass prints its fields by default.

    `repr` is what a traceback, a log line and an f-string all reach for, so the redaction has to
    live there rather than in a convention about how to log.
    """
    c = Credentials(environment="demo", username="someone@example.com",
                    password="hunter2-not-real", server="E8")
    for rendered in (repr(c), str(c), f"{c}"):
        assert "hunter2-not-real" not in rendered
        assert "someone@example.com" not in rendered
        assert "<redacted>" in rendered


def test_a_missing_credential_names_the_field_and_never_the_value(tmp_path, monkeypatch) -> None:
    for var in ("E8_TL_ENV", "E8_TL_USERNAME", "E8_TL_PASSWORD", "E8_TL_SERVER"):
        monkeypatch.delenv(var, raising=False)
    secret = tmp_path / "e8_tradelocker.json"
    secret.write_text(json.dumps({"environment": "demo", "username": "u", "server": "E8"}), "utf-8")
    with pytest.raises(VenueError) as exc:
        load_credentials(secret)
    assert "password" in str(exc.value)
    assert "'u'" not in str(exc.value), "the refusal must name the FIELD, never a value"


# ------------------------------------------------------------------------------ the adapter
def test_the_symbol_map_is_built_from_the_venue_not_hard_coded() -> None:
    """A hard-coded table is how a venue rename becomes a silently unplaced trade.

    The desk spells it XAUUSD and this venue spells it XAU/USD; neither is wrong, and the map has
    to absorb that rather than the sleeve rows having to know about it.
    """
    v = _venue()
    assert v.instrument_id("XAUUSD") == 2
    assert v.instrument_id("xau/usd") == 2
    assert v.instrument_id("EURUSD.pro") == 1


def test_an_unknown_symbol_is_a_named_refusal_and_never_a_silent_skip() -> None:
    """L1.28a on the money path: a sleeve that quietly stops trading is the failure to prevent."""
    with pytest.raises(VenueError, match="GBPNOK"):
        _venue().instrument_id("GBPNOK")


def test_an_empty_catalogue_refuses_to_connect() -> None:
    """Trading a blind map is worse than not trading."""
    with pytest.raises(VenueError, match="no instruments"):
        TradeLockerVenue(api=FakeAPI(instruments=[])).connect()


def test_the_venue_is_not_usable_before_connect() -> None:
    with pytest.raises(VenueError, match="not connected"):
        TradeLockerVenue().account()


def test_the_stop_travels_with_the_order() -> None:
    """ON A 2.5% DAILY FLOOR, THE GAP BETWEEN AN OPEN POSITION AND ITS STOP IS THE WHOLE RISK.

    "Place then modify" leaves that window open across a network call, which is the one thing
    this account cannot afford.
    """
    v = _venue()
    v.place("EURUSD", "buy", 0.10, stop=1.0950, take_profit=1.1100)
    (sent,) = v._raw_api.sent                                    # type: ignore[attr-defined]
    assert sent["stop_loss"] == 1.0950 and sent["stop_loss_type"] == "absolute"
    assert sent["type_"] == "market" and sent["quantity"] == 0.10 and sent["side"] == "buy"


def test_the_lot_is_floored_at_the_venue_minimum_and_otherwise_untouched() -> None:
    """The principal's 2026-09-12 order applies at THIS venue with THIS venue's number.

    The adapter raises a sub-minimum lot -- an order below the minimum is REJECTED, not small --
    and does nothing else to it, because sizing is `decision_core`'s and a second site computing
    "the lot" is the defect class `bracket_lane_lot` exists to close.
    """
    v = _venue()
    v.place("EURUSD", "buy", 0.001, stop=1.0950)
    v.place("EURUSD", "buy", 0.37, stop=1.0950)
    qtys = [s["quantity"] for s in v._raw_api.sent]              # type: ignore[attr-defined]
    assert qtys == [0.01, 0.37]


def test_a_rejected_order_raises_rather_than_returning_nothing() -> None:
    with pytest.raises(VenueError, match="rejected"):
        _venue(reject=True).place("EURUSD", "buy", 0.10, stop=1.0950)


def test_a_degenerate_quote_is_refused() -> None:
    """A crossed or empty book is unpriceable, and sizing off one is how a position gets an
    arbitrary size rather than a large one."""
    with pytest.raises(VenueError, match="degenerate"):
        _venue(quotes={1: {"bp": 1.10, "ap": 0.0}, 2: {"bp": 1.0, "ap": 1.0},
                       3: {"bp": 1.0, "ap": 1.0}}).quote("EURUSD")


def test_equity_is_balance_plus_open_pnl_when_the_venue_gives_no_equity() -> None:
    """The guard reads equity and nothing else, so the adapter must always be able to answer."""
    assert _venue().account()["equity"] == pytest.approx(99_750.0)


# ------------------------------------------------------------------------------ the guard
def _assess(equity, day_start=None, **kw):
    st = None if day_start is None else {"day": g.server_day(), "day_start": day_start,
                                         "peak_equity": day_start, "stood_down": False}
    return g.assess(equity, state=st, persist=False, **kw)


def test_the_static_floor_is_permanent_and_is_checked_first() -> None:
    d = _assess(90_000.0, day_start=100_000.0)
    assert d.verdict is g.Verdict.BREACHED and d.flatten and not d.may_open
    assert d.detail["breach"] == "static"


def test_the_daily_floor_breaches_at_two_and_a_half_percent_of_the_DAY_START() -> None:
    """Of the day's opening balance, not of the original $100k and not of the peak.

    A guard that measured the daily floor from the starting balance would hand a book that was
    already down 5% a 7.5% day, which is not the rule being enforced.
    """
    assert _assess(95_050.0, day_start=97_500.0).verdict is g.Verdict.BREACHED
    assert _assess(95_100.0, day_start=97_500.0).verdict is not g.Verdict.BREACHED


def test_the_voluntary_stand_down_fires_inside_e8s_floor_and_flattens() -> None:
    d = _assess(100_000.0 * (1 - g.STAND_DOWN) - 1, day_start=100_000.0)
    assert d.verdict is g.Verdict.STOOD_DOWN and d.flatten and not d.may_open
    assert g.STAND_DOWN < g.DAILY_DRAWDOWN, "a stand-down outside E8's own floor is decoration"


def test_reaching_the_daily_cap_stops_trading_because_more_profit_is_confiscated() -> None:
    """THE REFUSAL NOBODY WRITES, and it is free.

    Above +2% the gain is stripped at rollover and a loss is not, so every further trade that day
    has downside and no upside. The simulation does not model this, which makes every pass number
    in PROP_BARRIER.json conservative.
    """
    d = _assess(102_000.0, day_start=100_000.0)
    assert d.verdict is g.Verdict.CAPPED and not d.may_open
    assert d.counted_profit_today == pytest.approx(2_000.0)
    assert not d.flatten, "a capped day keeps its open positions; it just opens nothing new"


def test_profit_above_the_cap_is_never_counted() -> None:
    assert _assess(105_000.0, day_start=100_000.0).counted_profit_today == pytest.approx(2_000.0)


def test_reaching_the_target_stops_trading() -> None:
    """EXACTLY AT THE TARGET, WHICH IS WHERE THIS FIRST FAILED.

    `100_000.0 * 1.10` is 110000.00000000001 in binary floating point, so the guard reported OK
    at exactly $110,000 -- it missed the pass by one part in 10^11 and would have gone on trading
    a finished evaluation. Every threshold is now compared in CENTS. The same arithmetic sits
    under both floors, where the error runs the other way: OK a hundredth of a cent inside a
    breach.
    """
    d = _assess(110_000.0, day_start=109_000.0)
    assert d.verdict is g.Verdict.PASSED and d.flatten and not d.may_open
    assert _assess(109_999.99, day_start=109_000.0).verdict is not g.Verdict.PASSED


def test_every_threshold_is_exact_at_the_boundary() -> None:
    """One cent either side of each wall, because a floor out by a rounding error is not a floor.
    The floors are `<=`, so ON the line is already a breach.

    EACH WALL IS PROBED WITH THE OTHERS OUT OF REACH, which the first version of this test got
    wrong: at day_start 100,000 the DAILY floor sits at 97,500, so a 90,000.01 equity is breached
    by the daily wall long before the static one and the probe proved nothing about the static
    floor. Testing a floor requires standing somewhere only that floor can reach you.
    """
    # static floor at 90,000, with day_start low enough that today's floor (88,725) is beneath it
    assert _assess(90_000.00, day_start=91_000.0).detail.get("breach") == "static"
    assert _assess(90_000.01, day_start=91_000.0).verdict is not g.Verdict.BREACHED
    # daily floor at 97,500, well clear of the static one
    assert _assess(97_500.00, day_start=100_000.0).detail.get("breach") == "daily"
    assert _assess(97_500.01, day_start=100_000.0).verdict is not g.Verdict.BREACHED
    # the cap, where the float error ran the other way
    assert _assess(102_000.00, day_start=100_000.0).verdict is g.Verdict.CAPPED
    assert _assess(101_999.99, day_start=100_000.0).verdict is g.Verdict.OK


def test_an_ordinary_day_is_allowed_and_reports_both_distances() -> None:
    d = _assess(100_500.0, day_start=100_000.0)
    assert d.may_open
    assert d.room_to_daily_floor == pytest.approx(3_000.0)
    assert d.room_to_static_floor == pytest.approx(10_500.0)


def test_the_days_anchor_survives_a_restart_and_never_follows_losses_down(tmp_path) -> None:
    """THE ONE DIRECTION A FLOOR MUST NEVER MOVE.

    The gateway restarts. If the day's opening balance were re-derived from current equity, a book
    already down 2% would silently receive a fresh 2.5% of room, and the daily floor would chase
    the losses downward until the static floor caught it.
    """
    sp = tmp_path / "e8_guard_state.json"
    first = g.assess(100_000.0, state_path=sp)
    assert first.day_start == pytest.approx(100_000.0)
    after = g.assess(98_000.0, state_path=sp)            # a fresh process, same server day
    assert after.day_start == pytest.approx(100_000.0), "the anchor moved with the equity"
    assert after.room_to_daily_floor == pytest.approx(500.0)


def test_a_new_server_day_re_anchors(tmp_path) -> None:
    sp = tmp_path / "e8_guard_state.json"
    g.assess(100_000.0, state_path=sp, now=datetime(2026, 9, 15, 12, 0, tzinfo=UTC))
    nxt = g.assess(98_000.0, state_path=sp, now=datetime(2026, 9, 16, 12, 0, tzinfo=UTC))
    assert nxt.day_start == pytest.approx(98_000.0)
    assert nxt.may_open, "a new day starts with its full allowance"


def test_the_server_day_is_not_the_utc_day() -> None:
    """E8 rolls over at SERVER midnight, and every certified sleeve fires in the asia session --
    which is exactly the window a UTC-anchored guard would misattribute."""
    assert g.SERVER_UTC_OFFSET_HOURS != 0
    late = datetime(2026, 9, 15, 22, 0, tzinfo=UTC)
    assert g.server_day(late) == "2026-09-16"


def test_a_stand_down_latches_for_the_rest_of_the_session() -> None:
    """Recovering above the line must not re-arm the book: the rule is "no new risk today"."""
    st = {"day": g.server_day(), "day_start": 100_000.0, "peak_equity": 100_000.0,
          "stood_down": True}
    assert g.assess(100_400.0, state=st, persist=False).verdict is g.Verdict.STOOD_DOWN
