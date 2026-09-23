"""A release is an event for the currencies it concerns, and expensive has a cause.

Two engines, two errors they exist to stop.

EVENT. The version replaced here classified the WHOLE DESK from the nearest row on the calendar,
whatever it was about, so every instrument entered SHOCK whenever anything anywhere printed. A
Bank of England release is an event for GBP pairs and an ordinary Tuesday for AUDJPY.

LIQUIDITY. The version replaced here sorted the current spread into four percentile bands. It
could not say WHY an instrument was expensive, and the answer decides what to do: a rollover ends
on a clock, a news window ends with the release, a degraded feed means stop rather than size down.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.regime import event_state as ev  # noqa: E402
from libs.regime import liquidity_state as liq  # noqa: E402

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
META = {"EURUSD": {"asset_class": "Forex", "currency_profit": "USD"},
        "GBPJPY": {"asset_class": "Forex", "currency_profit": "JPY"},
        "AUDJPY": {"asset_class": "Forex", "currency_profit": "JPY"},
        "XAUUSD": {"asset_class": "Commodities", "currency_profit": "USD"},
        "GER40": {"asset_class": "Indices", "currency_profit": "EUR"}}


def _row(minutes: int, ccy: str, impact: str = "High", **kw) -> dict:
    return {"_stamp": NOW + timedelta(minutes=minutes), "symbols": [ccy], "impact": impact,
            "title": f"{ccy} thing", **kw}


# ------------------------------------------------------------------------------------------
# Event scope
# ------------------------------------------------------------------------------------------

def test_a_release_is_scoped_to_the_currencies_it_concerns():
    rows = [_row(-5, "GBP")]
    assert ev.relevant(rows, "GBPJPY", META), "a GBP print must reach a GBP pair"
    assert not ev.relevant(rows, "AUDJPY", META), "a GBP print is not AUDJPY's event"


def test_a_dollar_quoted_instrument_answers_to_usd_releases():
    assert ev.currencies_of("XAUUSD", META) == ("USD",)
    assert set(ev.currencies_of("GER40", META)) == {"EUR", "USD"}
    assert set(ev.currencies_of("EURUSD", META)) == {"EUR", "USD"}


def test_an_all_scoped_row_is_everyones_event():
    rows = [{"_stamp": NOW, "symbols": ["All"], "impact": "High"}]
    assert ev.relevant(rows, "AUDJPY", META)


def test_low_impact_releases_do_not_open_a_shock_window():
    rows = [_row(-2, "USD", impact="Low")]
    assert not ev.relevant(rows, "EURUSD", META)
    assert ev.relevant([_row(-2, "USD", impact="Medium")], "EURUSD", META)


# ------------------------------------------------------------------------------------------
# Event phases
# ------------------------------------------------------------------------------------------

def test_the_phase_machine_walks_the_release_in_order():
    stamp = NOW
    cases = [(-150, ev.NORMAL), (-100, ev.PRE_EVENT), (5, ev.SHOCK), (40, ev.PRICE_DISCOVERY),
             (500, ev.NORMALIZATION), (900, ev.NORMAL)]
    for offset, want in cases:
        got = ev.classify(stamp + timedelta(minutes=offset), [stamp]).phase
        assert got == want, f"{offset} minutes from the print gave {got}, expected {want}"


def test_drift_and_reversal_are_decided_by_the_tape_not_the_clock():
    stamp = NOW
    later = stamp + timedelta(minutes=120)          # inside the post-event window either way
    drift = ev.classify(later, [stamp], shock_move=0.004, move_since=0.003)
    revert = ev.classify(later, [stamp], shock_move=0.004, move_since=-0.003)
    assert drift.phase == ev.POST_EVENT_DRIFT
    assert revert.phase == ev.POST_EVENT_REVERSAL


def test_the_post_event_window_refuses_to_guess_without_the_moves():
    later = NOW + timedelta(minutes=120)
    st = ev.classify(later, [NOW])
    assert st.phase == ev.PRICE_DISCOVERY, "naming DRIFT from a stopwatch assumes the answer"


def test_no_scheduled_release_is_normal_not_a_missing_value():
    st = ev.classify(NOW, [])
    assert st.phase == ev.NORMAL
    assert st.minutes_to_next == float("inf")


def test_the_absent_actual_field_is_recorded_as_a_named_gap():
    rows = [_row(-5, "USD", forecast="0.4%", previous="0.2%")]
    st = ev.classify(NOW, [r["_stamp"] for r in rows], rows=rows)
    assert "surprise" in st.gaps
    assert "actual" in st.gaps["surprise"]
    # The expected CHANGE is available and is reported under its own name, never as surprise.
    assert st.expected_change == pytest.approx(0.2, abs=1e-9)


def test_calendar_figures_parse_through_their_units():
    assert ev._num("1.5%") == pytest.approx(1.5)
    assert ev._num("250K") == pytest.approx(250_000)
    assert ev._num("-1.2B") == pytest.approx(-1.2e9)
    assert ev._num("") is None and ev._num("n/a") is None


def test_a_row_with_no_parseable_stamp_is_dropped_not_guessed():
    assert ev.parse_rows([{"title": "x"}, {"event_date": "not a date"}]) == []
    assert len(ev.parse_rows([{"event_date": "2026-09-04T12:00:00+00:00"}])) == 1


# ------------------------------------------------------------------------------------------
# Liquidity
# ------------------------------------------------------------------------------------------

def _hist(n: int = 500, base: float = 1.0, seed: int = 0) -> list[float]:
    rng = np.random.default_rng(seed)
    return list(base + np.abs(rng.normal(scale=0.1, size=n)))


def test_a_normal_spread_is_normal():
    st = liq.classify("EURUSD", _hist())
    assert st.state == liq.NORMAL
    assert st.cost_multiple is not None


def test_a_wide_and_widening_spread_is_toxic():
    h = _hist()
    h[-1] = max(h) * 3.0
    st = liq.classify("EURUSD", h)
    assert st.state == liq.TOXIC
    assert st.widening
    assert st.cost_multiple > 2.0


def test_a_wide_but_quiet_spread_is_thin_not_toxic():
    """Wide with nothing happening is a cost with an option to wait; wide and moving is not."""
    h = _hist()
    h[-1] = float(np.quantile(h, 0.99))
    act = list(np.linspace(100, 1, 500))          # activity at its own minimum
    st = liq.classify("EURUSD", h, activity_history=act)
    assert st.state == liq.THIN
    assert st.quiet


def test_degradation_outranks_everything_because_its_instruction_is_stop():
    h = _hist()
    h[-1] = max(h) * 5.0
    st = liq.classify("EURUSD", h, in_news_window=True, broker_hour=23, recent_rejections=5)
    assert st.state == liq.BROKER_DEGRADED
    st2 = liq.classify("EURUSD", h, minutes_since_tick=90.0)
    assert st2.state == liq.BROKER_DEGRADED


def test_a_news_window_is_named_as_such_rather_than_merely_wide():
    st = liq.classify("EURUSD", _hist(), in_news_window=True)
    assert st.state == liq.NEWS


def test_the_rollover_window_is_read_in_broker_hours():
    assert liq.classify("EURUSD", _hist(), broker_hour=23).state == liq.ROLLOVER
    assert liq.classify("EURUSD", _hist(), broker_hour=0).state == liq.ROLLOVER
    assert liq.classify("EURUSD", _hist(), broker_hour=12).state == liq.NORMAL


def test_news_outranks_rollover_because_it_is_the_cause():
    st = liq.classify("EURUSD", _hist(), broker_hour=23, in_news_window=True)
    assert st.state == liq.NEWS


def test_no_tape_is_unmeasured_and_never_normal():
    """"No tape recorded" and "conditions are fine" are opposite facts."""
    st = liq.classify("EURUSD", None)
    assert st.state == liq.UNMEASURED
    assert "spread_history" in st.gaps
    st2 = liq.classify("EURUSD", [1.0] * 10)
    assert st2.state == liq.UNMEASURED
    assert "needs 200" in st2.gaps["spread_history"]


def test_states_needing_no_history_still_report_without_it():
    assert liq.classify("EURUSD", None, in_news_window=True).state == liq.NEWS
    assert liq.classify("EURUSD", None, broker_hour=0).state == liq.ROLLOVER


def test_bands_are_the_instruments_own_so_a_wide_exotic_is_not_permanently_toxic():
    tight = liq.classify("EURUSD", _hist(base=0.1, seed=1))
    wide = liq.classify("EXOTIC", _hist(base=50.0, seed=1))
    assert tight.state == wide.state == liq.NORMAL, "a fixed points threshold would split these"


def test_precedence_is_declared_and_complete():
    assert liq.STATES[0] == liq.BROKER_DEGRADED
    assert set(liq.STATES) == {liq.BROKER_DEGRADED, liq.TOXIC, liq.NEWS, liq.ROLLOVER,
                               liq.THIN, liq.NORMAL}


# ------------------------------------------------------------------------------------------
# The builder wiring
# ------------------------------------------------------------------------------------------

def test_the_builder_scopes_events_per_symbol_and_feeds_them_to_liquidity():
    import inspect

    from research import state_vector_build as svb

    src = inspect.getsource(svb.build)
    assert "event_state(now, book)" in src
    assert "liquidity_state(book, now, event)" in src, \
        "liquidity must see the event state, or a NEWS window reads as merely wide"


def test_the_builder_produces_per_symbol_event_states():
    from research import state_vector_build as svb

    state, why = svb.event_state(datetime.now(tz=UTC), ["XAUUSD", "EURUSD"])
    if why:
        pytest.skip(why)
    assert state["phase"] in ev.PHASES
    if state.get("per_symbol"):
        for sym, st in state["per_symbol"].items():
            assert st["phase"] in ev.PHASES, sym
