"""R0371: fee attribution from venue truth, and the three answers it must refuse to fake."""

from __future__ import annotations

from datetime import UTC, datetime

from libs.research.fee_attribution import (
    attribute,
    concentration_verdict,
    fill_instant,
)


def _ev(sym: str, amt: float, t: int = 1_785_000_000_000) -> dict:
    return {"symbol": sym, "commission": amt, "time": t}


def test_empty_events_is_unmeasured_never_zero_fees() -> None:
    """WS-005, the desk's most-repeated defect class: absence must not resolve to a clean zero."""
    out = attribute([])
    assert out["measured"] is False
    assert "venue_commission_usd" not in out          # no number at all, not 0.0
    assert "UNMEASURED" in out["note"]


def test_per_symbol_totals_and_concentration() -> None:
    out = attribute([_ev("AAAUSDT", 60.0), _ev("AAAUSDT", 20.0), _ev("BBBUSDT", 20.0)])
    assert out["measured"] is True
    assert out["venue_commission_usd"] == 100.0
    assert out["by_symbol"] == {"AAAUSDT": 80.0, "BBBUSDT": 20.0}
    assert out["events_priced"] == 3
    assert list(out["by_symbol"]) == ["AAAUSDT", "BBBUSDT"]     # ranked, biggest payer first


def test_attrition_counts_every_dropped_event() -> None:
    """L1.60: a denominator that loses members in silence is a coverage claim we cannot cash."""
    events = [_ev("AAAUSDT", 10.0), _ev("", 5.0), _ev("BBBUSDT", 0.0), "not-a-mapping"]
    out = attribute(events)  # type: ignore[arg-type]
    assert out["events_attempted"] == 4
    assert out["events_unusable"] == 3          # symbol-less, zero-amount and non-mapping
    assert out["events_priced"] == 1
    assert out["events_attempted"] == out["events_priced"] + out["events_unusable"]


def test_spot_leg_and_row_level_are_refused_not_faked() -> None:
    out = attribute([_ev("AAAUSDT", 10.0)])
    assert out["spot_leg"] == "UNMEASURED"
    assert out["row_level"] == "REFUSED"
    assert "fill-time stamp" in out["row_level_note"]


def test_fill_instant_open_and_close_resolve() -> None:
    assert fill_instant({"event": "open", "opened": "2026-08-01T14:18:54+00:00"}) == datetime(
        2026, 8, 1, 14, 18, 54, tzinfo=UTC)
    assert fill_instant({"event": "close", "closed": "2026-08-01T21:55:23+00:00"}) == datetime(
        2026, 8, 1, 21, 55, 23, tzinfo=UTC)


def test_fill_instant_refuses_a_topup() -> None:
    """A topup row carries the POSITION's open stamp, not the topup's fill time (51/51 verified).

    Returning that stamp would locate the fill hours away from where it happened, which is worse
    than returning nothing: a wrong timestamp is indistinguishable from a right one downstream.
    """
    assert fill_instant({"event": "topup", "opened": "2026-08-01T14:18:54+00:00"}) is None


def test_fill_instant_survives_junk() -> None:
    assert fill_instant({"event": "open", "opened": "not-a-date"}) is None
    assert fill_instant({"event": "open"}) is None
    assert fill_instant({}) is None


def test_naive_timestamp_is_treated_as_utc() -> None:
    got = fill_instant({"event": "open", "opened": "2026-08-01T14:18:54"})
    assert got is not None and got.tzinfo is not None


def test_coverage_and_residual_against_the_tape() -> None:
    """The bill implies a notional; the tape accounts for a fraction. Both get published."""
    events = [_ev("AAAUSDT", 50.0)]                  # $50 at 5bp implies $100,000 traded
    tape = [{"event": "open", "symbol": "AAAUSDT", "notional": 1000.0}]
    out = attribute(events, tape)
    assert out["implied_notional_usd"] == 100_000.0
    assert out["tape_coverage"] == 0.01
    assert "OPEN-FAIL/CLOSE-FAIL" in out["residual_note"]     # the candidate, flagged as unproven


def test_no_residual_note_when_the_tape_accounts_for_the_bill() -> None:
    events = [_ev("AAAUSDT", 50.0)]
    tape = [{"event": "open", "symbol": "AAAUSDT", "notional": 100_000.0}]
    out = attribute(events, tape)
    assert out["tape_coverage"] == 1.0
    assert "residual_note" not in out


def test_off_tape_symbols_are_named() -> None:
    events = [_ev("AAAUSDT", 10.0), _ev("ZZZUSDT", 4.0)]
    tape = [{"event": "open", "symbol": "AAAUSDT", "notional": 10.0}]
    out = attribute(events, tape)
    assert out["off_tape_symbols"] == ["ZZZUSDT"]
    assert out["off_tape_commission_usd"] == 4.0


def test_concentration_verdict_routes_the_repair() -> None:
    conc = attribute([_ev("A", 90.0), _ev("B", 4.0), _ev("C", 3.0), _ev("D", 2.0), _ev("E", 1.0)])
    v, why = concentration_verdict(conc)
    assert v == "CONCENTRATED"
    assert "symbol-level" in why

    diffuse = attribute([_ev(chr(65 + i), 10.0) for i in range(20)])
    v2, why2 = concentration_verdict(diffuse)
    assert v2 == "DIFFUSE"
    assert "execution path" in why2

    v3, _ = concentration_verdict(attribute([]))
    assert v3 == "UNMEASURED"


def test_reproduces_the_measured_sleeve_shape() -> None:
    """The real 2026-07-02..08-01 shape: 4 names carry ~86% of a $1,750.88 bill."""
    events = ([_ev("COOKIEUSDT", 623.30), _ev("1000CATUSDT", 413.03),
               _ev("MOVEUSDT", 245.95), _ev("TSTUSDT", 221.54)]
              + [_ev(f"S{i}USDT", 247.06 / 60) for i in range(60)])
    out = attribute(events)
    assert abs(out["venue_commission_usd"] - 1750.88) < 0.05
    assert out["top4_share"] > 0.85
    assert concentration_verdict(out)[0] == "CONCENTRATED"
