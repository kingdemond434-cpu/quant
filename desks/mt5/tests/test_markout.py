"""Execution markout: the desk's first measurement of what it actually pays to trade.

Every return figure here assumes fills at exactly the bracket price, and session breakout enters
on STOP orders into fast moves -- the worst case for slippage. The crypto desk in this same repo
modelled 0.35bps and paid ~16bps, and found out only by comparing intents to fills.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.markout import Markout, _direction, compute, load_jsonl, render  # noqa: E402

BUY, SELL = 0, 1


def _intent(ticket, intended, side="buy_stop"):
    return {"ticket": ticket, "intended": intended, "side": side, "sleeve": "gold_asia",
            "symbol": "XAUUSD"}


def _deal(ticket, fill, side=BUY, risk=19.1):
    return {"order": ticket, "fill_price": fill, "side": side, "risk_quote": risk,
            "sleeve": "gold_asia", "symbol": "XAUUSD", "deal": ticket * 10}


def test_a_buy_filled_above_its_trigger_is_positive_slip():
    m = compute([_intent(1, 2000.0)], [_deal(1, 2000.5, BUY)])
    assert m.usable
    assert m.mean_slip_quote == pytest.approx(0.5)


def test_a_sell_filled_below_its_trigger_is_ALSO_positive_slip():
    """SIGN CONVENTION IS THE WHOLE POINT. A buy filled high and a sell filled low are the same
    event -- worse than asked. Unsigned, they would cancel in the mean and a desk bleeding on
    both sides would report zero slippage."""
    m = compute([_intent(1, 2000.0, "sell_stop")], [_deal(1, 1999.5, SELL)])
    assert m.mean_slip_quote == pytest.approx(0.5)

    both = compute([_intent(1, 2000.0, "buy_stop"), _intent(2, 2000.0, "sell_stop")],
                   [_deal(1, 2000.5, BUY), _deal(2, 1999.5, SELL)])
    assert both.mean_slip_quote == pytest.approx(0.5), (
        "a buy and a sell, each half a point worse, cancelled to zero")


def test_a_favourable_fill_is_negative_slip():
    m = compute([_intent(1, 2000.0)], [_deal(1, 1999.8, BUY)])
    assert m.mean_slip_quote == pytest.approx(-0.2)


def test_slippage_is_reported_in_R_because_that_is_the_unit_of_every_gate():
    """0.5 quote on a 19.1 stop distance is 0.0262R -- against a +0.159R edge, 16% of it."""
    m = compute([_intent(1, 2000.0)], [_deal(1, 2000.5, BUY, risk=19.1)])
    assert m.mean_slip_r == pytest.approx(0.5 / 19.1, rel=1e-6)
    assert m.edge_share == pytest.approx((0.5 / 19.1) / 0.159, rel=1e-6)


def test_an_unfilled_bracket_is_not_a_zero_slippage_fill():
    """THE FABRICATION THIS PREVENTS. Most intents never fill -- the 20:30 cancel, or a range
    that never broke. Counting them as zero drags the mean toward 'no slippage' using orders that
    never traded, the same defect as writing 0.0 for a day a sleeve did not trade."""
    m = compute([_intent(1, 2000.0), _intent(2, 2000.0), _intent(3, 2000.0)],
                [_deal(1, 2000.5, BUY)])
    assert m.n_matched == 1
    assert m.n_unfilled_intents == 2
    assert m.mean_slip_quote == pytest.approx(0.5), "unfilled intents diluted the measurement"


def test_a_deal_with_no_intent_is_a_reconciliation_finding():
    """Something placed an order this desk cannot account for. A statistic would hide it."""
    m = compute([], [_deal(99, 2000.5, BUY)])
    assert m.n_unmatched_deals == 1
    assert not m.usable
    assert "UNMEASURED" in m.why


def test_no_fills_yet_is_not_a_clean_bill_of_health():
    """Before the first trade, execution is UNMEASURED -- which must not read as 'no slippage'."""
    m = compute([], [])
    assert not m.usable
    assert "UNMEASURED" in m.why
    assert "no slippage" not in render(m).lower()


def test_the_report_escalates_when_slippage_eats_the_edge():
    """0.10R average against a 0.159R edge is 63% of everything the book earns."""
    m = compute([_intent(1, 2000.0)], [_deal(1, 2000.0 + 1.91, BUY, risk=19.1)])
    assert m.mean_slip_r == pytest.approx(0.10, abs=0.001)
    out = render(m)
    assert "eating the edge" in out
    assert "assumes fills AT the bracket price" in out


def test_direction_parses_both_the_numeric_type_and_the_intent_string():
    assert _direction(0) == 1 and _direction(4) == 1
    assert _direction(1) == -1 and _direction(5) == -1
    assert _direction("buy_stop") == 1 and _direction("sell_stop") == -1
    assert _direction(None) == 0 and _direction("weird") == 0


def test_load_jsonl_survives_a_partial_line(tmp_path):
    """The gateway appends while this may be reading; a torn final line must not lose the file."""
    p = tmp_path / "x.jsonl"
    p.write_text('{"a": 1}\n{"b": 2}\n{"c": ', encoding="utf-8")
    assert load_jsonl(p) == [{"a": 1}, {"b": 2}]
    assert load_jsonl(tmp_path / "absent.jsonl") == []


def test_the_gateway_actually_records_both_halves():
    """A tracker with nothing feeding it measures nothing. Pins the wiring, not just the maths."""
    src = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
    assert "_record_intent(" in src, "placement intent is never written"
    assert '"fill_price"' in src, "the deal ledger does not record the fill price"
    assert "order_intents.jsonl" in src
