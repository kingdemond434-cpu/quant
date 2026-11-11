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


# ------------------------------------------------------------ the join that never matched
def _closing_deal(pid, entry_fill, close_fill, side=BUY, risk=19.1, **over):
    """A ledger row as the gateway writes it for a CLOSING deal: `order` is the server's
    stop/target order (a ticket the desk never saw), `fill_price` is the exit, and the entry
    side is carried on position_id / entry_order / entry_deal / entry_price."""
    row = {"order": pid * 1000 + 1, "position_id": pid,
           "entry_order": pid, "entry_deal": pid * 10 + 1,
           "entry_price": entry_fill, "fill_price": close_fill, "side": side,
           "risk_quote": risk, "sleeve": "gold_asia", "symbol": "XAUUSD",
           "deal": pid * 10 + 2, "r_multiple": 1.7, "pl_quote": 32.5,
           "time": "2026-09-08T14:00:00Z"}
    row.update(over)
    return row


def test_a_closing_deal_joins_on_the_position_id_and_slips_against_the_entry_fill():
    """THE ZERO THE REVIEW FOUND. The ledger records closing deals; their `order` is the exit
    order, never the intent's ticket, so the old join matched nothing by construction -- and
    the price it would have compared was the exit, not the entry."""
    intent = _intent(7, 2000.0)
    intent.update({"time": "2026-09-08T04:00:00Z", "release_id": "abc123",
                   "state_vector_id": "sv-9"})
    m = compute([intent], [_closing_deal(7, entry_fill=2000.5, close_fill=2019.1)])
    assert m.usable and m.n_matched == 1
    assert m.mean_slip_quote == pytest.approx(0.5), "slip must be measured at the ENTRY"
    assert m.attributed_deals == 1 and m.attributed_share == 1.0
    (link,) = m.chain
    assert link["release_id"] == "abc123" and link["state_vector_id"] == "sv-9"
    assert link["ticket"] == 7 and link["close_deal"] == 72 and link["entry_deal"] == 71
    assert link["realized_r"] == 1.7 and link["slip_quote"] == pytest.approx(0.5)


def test_a_row_with_only_the_position_id_still_joins():
    m = compute([_intent(7, 2000.0)],
                [_closing_deal(7, 2000.2, 2010.0, entry_order=None)])
    assert m.n_matched == 1 and m.mean_slip_quote == pytest.approx(0.2)


def test_a_closing_order_ticket_alone_never_matches_an_intent():
    """Rows written before the position id was recorded carry only the exit order: they stay
    unmatched, reported as such, never silently attributed to the wrong intent."""
    m = compute([_intent(7, 2000.0)],
                [_closing_deal(7, 2000.2, 2010.0, entry_order=None, position_id=None)])
    assert m.n_matched == 0 and m.n_unmatched_deals == 1 and m.attributed_deals == 0


def test_attribution_share_counts_every_deal_the_desk_can_explain():
    m = compute([_intent(7, 2000.0)],
                [_closing_deal(7, 2000.5, 2010.0), _closing_deal(8, 2000.5, 2010.0)])
    assert m.attributed_deals == 1 and m.n_deals == 2
    assert m.attributed_share == pytest.approx(0.5)
    assert "attributed deals     1/2" in render(m)


def test_the_gateway_writes_the_key_chain_and_filters_magic_in_python():
    src = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
    for key in ('"position_id"', '"entry_order"', '"entry_deal"', '"close_order"'):
        assert key in src, f"the ledger row does not carry {key}"
    assert "magic=MAGIC)" not in src, (
        "history_deals_get takes no magic keyword; a refused keyword lands in the except and "
        "the ledger is silently never written")
    assert 'getattr(d, "magic", 0)' in src


def test_slip_in_R_is_over_the_intended_stop_distance_never_the_money_at_risk():
    """THE 2026-11-11 RED THAT WAS A DENOMINATOR. `risk_quote` is account money for the
    position's volume, measured from the fill: on a 0.01-lot FX cross it is ~1000x the price
    distance, and a fill near its stop shrinks it toward zero. A slip in R is over the distance
    the trade was sized on -- intended entry to the intent's stop."""
    fx = {"ticket": 1, "intended": 0.93000, "side": "buy", "sl": 0.92600,
          "sleeve": "eurchf_x", "symbol": "EURCHF"}
    deal = {"order": 1, "fill_price": 0.93004, "side": SELL, "risk_quote": 4.06,
            "sleeve": "eurchf_x", "symbol": "EURCHF", "deal": 10}
    m = compute([fx], [deal])
    assert m.rows[0]["risk_basis"] == "intent_sl"
    assert m.mean_slip_r == pytest.approx(0.00004 / 0.004, rel=1e-6)

    # A short filled $3.84 ABOVE its trigger and $0.10 under its stop: -0.97R, not -44R.
    short = {"ticket": 2, "intended": 4338.91, "side": "sell", "sl": 4342.85,
             "sleeve": "xau_m5", "symbol": "XAUUSD"}
    near = {"order": 2, "fill_price": 4342.75, "side": BUY, "risk_quote": 0.086688,
            "sleeve": "xau_m5", "symbol": "XAUUSD", "deal": 20}
    m2 = compute([short], [near])
    assert m2.mean_slip_r == pytest.approx(-3.84 / 3.94, rel=1e-3)


def test_the_position_stop_stands_in_when_the_intent_carries_none():
    m = compute([_intent(1, 2000.0)],
                [{**_deal(1, 2000.5, BUY, risk=999.0), "sl": 1990.0}])
    assert m.rows[0]["risk_basis"] == "position_sl"
    assert m.mean_slip_r == pytest.approx(0.05)


def test_slippage_splits_by_sleeve_and_symbol_beside_realised_R():
    intents = [{**_intent(1, 2000.0), "sl": 1990.0},
               {**_intent(2, 2000.0), "sl": 1990.0, "sleeve": "other", "symbol": "EURUSD"},
               {**_intent(3, 2000.0), "sl": 1990.0}]
    deals = [{**_deal(1, 2001.0, BUY), "r_multiple": 1.5},
             {**_deal(2, 1999.0, BUY), "sleeve": "other", "symbol": "EURUSD",
              "r_multiple": -1.0},
             {**_deal(3, 2000.0, BUY), "r_multiple": 0.5}]
    m = compute(intents, deals)
    gold = m.by_sleeve["gold_asia"]
    assert gold["n"] == 2 and gold["worse"] == 1 and gold["at_price"] == 1
    assert gold["mean_slip_r"] == pytest.approx(0.05)
    assert gold["mean_realized_r"] == pytest.approx(1.0)
    assert m.by_symbol["EURUSD"]["better"] == 1
    assert m.median_slip_r == pytest.approx(0.0)
    assert "by sleeve" in render(m)
