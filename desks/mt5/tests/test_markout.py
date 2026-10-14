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

from mt5desk.markout import (  # noqa: E402
    IMPLAUSIBLE_STOP_FRAC,
    Markout,
    _direction,
    broker_hour,
    compute,
    load_jsonl,
    render,
    slip_breakdown,
    surface_points,
)

BUY, SELL = 0, 1


def _intent(ticket, intended, side="buy_stop", stop=19.1):
    sl = intended - stop if "buy" in side else intended + stop
    return {"ticket": ticket, "intended": intended, "side": side, "sleeve": "gold_asia",
            "symbol": "XAUUSD", "sl": sl}


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


# --- 2026-10-14: the R denominator, the breakdown and the quarantine -------------------------


def test_slip_r_is_price_over_the_intents_stop_never_account_money():
    """slip_r is the slip in units of the intent's own stop (price over price); the old
    price/risk_quote quotient survives only as slip_r_money, for audit."""
    m = compute([_intent(1, 2000.0, "sell", stop=4.0)], [_deal(1, 2001.0, SELL, risk=0.087)],
                points={})
    assert m.rows[0]["slip_r"] == pytest.approx(-0.25)
    assert m.rows[0]["slip_stop_frac"] == pytest.approx(-0.25)
    assert m.rows[0]["slip_r_money"] == pytest.approx(-1.0 / 0.087)
    assert m.rows[0]["stop_basis"] == "intent_stop"
    r = m.slip["pooled"]["all"]["r"]
    assert r["mean"] == pytest.approx(-0.25) and r["status"] == "MEASURED"


def test_the_44R_row_is_quarantined_on_its_stop_fraction():
    """Ticket 222937609: a MARKET sell intended at 4338.91 filled at the live bid 4342.75, 0.10
    under the stop the intent set from its stale price; risk_quote 0.087 EUR made it -44.3R."""
    it = {"ticket": 222937609, "intended": 4338.91, "side": "sell", "symbol": "XAUUSD",
          "sl": 4342.852255108066, "sleeve": "xau_m5_anti_breakout_overlap"}
    d = {"entry_order": 222937609, "entry_price": 4342.75, "fill_price": 4342.89, "side": 0,
         "sl": 4342.85, "risk_quote": 0.086688, "symbol": "XAUUSD", "deal": 200308589,
         "sleeve": "xau_m5_anti_breakout_overla"}
    m = compute([it], [d], points={"XAUUSD": 0.01})
    row = m.rows[0]
    assert row["slip_r_money"] == pytest.approx(-44.297, abs=0.01)
    assert row["slip_r"] == pytest.approx(row["slip_stop_frac"])
    assert row["quarantine"] and "stop distance" in row["quarantine"][0]
    assert m.mean_slip_r is None               # the only row is quarantined: no clean mean
    assert m.edge_share is None and "R UNMEASURED" in render(m)
    assert m.slip["pooled"]["n_quarantined"] == 1
    assert m.slip["quarantined"][0]["order"] == 222937609


def test_the_position_stop_is_the_fallback_and_no_stop_is_unmeasured():
    it = {"ticket": 1, "intended": 2000.0, "side": "buy", "symbol": "XAUUSD"}
    m = compute([it], [{**_deal(1, 2000.5, BUY, risk=1.0), "sl": 1990.5}], points={})
    assert m.rows[0]["slip_stop_frac"] == pytest.approx(0.05)
    assert m.rows[0]["stop_basis"] == "position_stop"
    m2 = compute([dict(it)], [_deal(1, 2000.5, BUY, risk=1.0)], points={})
    assert m2.rows[0]["slip_stop_frac"] is None
    assert m2.rows[0]["stop_basis"].startswith("UNMEASURED")


def test_the_sign_is_stated_in_the_payload_positive_is_a_cost():
    m = compute([_intent(1, 2000.0)], [_deal(1, 2000.5, BUY)], points={})
    assert "positive = cost" in m.slip["sign"]
    assert m.slip["pooled"]["all"]["quote"]["mean"] == pytest.approx(0.5)
    assert "positive = cost" in render(m)


def _row(sleeve, sym, slip, frac=None, pts=None, hour=10, spread=None, pending=False):
    row = {"sleeve": sleeve, "symbol": sym, "slip_quote": slip, "slip_stop_frac": frac,
           "slip_pts": pts,
           "broker_hour": hour, "spread_pts_at_decision": spread, "pending": pending}
    from mt5desk.markout import _quarantine
    row["quarantine"] = _quarantine(row)
    return row


def test_breakdown_reports_n_mean_median_p75_per_sleeve_and_symbol_hour():
    rows = [_row("a", "XAUUSD", q, q / 4, q * 100, hour=h)
            for q, h in ((0.1, 10), (0.2, 10), (0.3, 11), (0.4, 11))]
    b = slip_breakdown(rows)
    s = b["by_sleeve"]["a"]["clean"]["pts"]
    assert s["n"] == 4
    assert s["mean"] == pytest.approx(25.0)
    assert s["median"] == pytest.approx(25.0)
    assert s["p75"] == pytest.approx(32.5)
    assert b["by_sleeve"]["a"]["n_small"] is True
    cell = b["by_symbol_hour"]["XAUUSD"]["10"]["clean"]["pts"]
    assert cell["n"] == 2 and cell["mean"] == pytest.approx(15.0)
    assert b["by_symbol_hour"]["XAUUSD"]["11"]["all"]["quote"]["median"] == pytest.approx(0.35)


def test_an_implausible_row_is_quarantined_by_name_kept_in_all_excluded_from_clean():
    rows = [_row("a", "XAUUSD", 0.1, 0.02), _row("a", "XAUUSD", -3.84, -0.974)]
    b = slip_breakdown(rows)
    assert b["by_sleeve"]["a"]["n_quarantined"] == 1
    assert b["by_sleeve"]["a"]["all"]["quote"]["n"] == 2
    assert b["by_sleeve"]["a"]["clean"]["quote"]["mean"] == pytest.approx(0.1)
    assert len(b["quarantined"]) == 1
    assert str(IMPLAUSIBLE_STOP_FRAC) in b["quarantined"][0]["quarantine"][0]


def test_the_spread_rule_quarantines_a_market_order_but_not_a_pending_stop():
    assert _row("a", "XAUUSD", 3.25, 0.34, 325.0, spread=7.0)["quarantine"]
    assert not _row("a", "XAUUSD", 2.02, 0.05, 202.0, spread=6.0, pending=True)["quarantine"]


def test_an_empty_unit_is_unmeasured_not_zero():
    b = slip_breakdown([_row("a", "EURUSD", 0.0001, None, None)])
    assert b["pooled"]["all"]["pts"]["status"] == "UNMEASURED"
    assert b["pooled"]["all"]["pts"]["mean"] is None


def test_points_come_from_the_intent_then_the_surface(tmp_path):
    p = tmp_path / "cs.json"
    p.write_text('{"symbols": {"XAUUSD": {"tick_size": 0.01}, "BAD": {"tick_size": 0}}}')
    assert surface_points(p) == {"XAUUSD": 0.01}
    assert surface_points(tmp_path / "missing.json") == {}
    m = compute([_intent(1, 2000.0)], [_deal(1, 2000.5, BUY)], points=surface_points(p))
    assert m.rows[0]["slip_pts"] == pytest.approx(50.0)
    it = {**_intent(1, 2000.0), "point": 0.1}
    assert compute([it], [_deal(1, 2000.5, BUY)], points={}).rows[0]["slip_pts"] == \
        pytest.approx(5.0)


def test_broker_hour_is_new_york_plus_seven():
    assert broker_hour("2026-07-01T10:00:00+00:00") == 13      # EDT: UTC+3
    assert broker_hour("2026-01-15T10:00:00Z") == 12           # EST: UTC+2
    assert broker_hour("2026-01-15T10:00:00") == 12            # naive read as UTC
    assert broker_hour("not a time") is None


def test_a_row_with_no_symbol_or_hour_is_grouped_honestly_and_render_says_unmeasured():
    rows = [{"sleeve": None, "symbol": None, "slip_quote": 0.1, "slip_pts": None,
             "broker_hour": None, "quarantine": []},
            {"sleeve": "a", "symbol": "XAUUSD", "slip_quote": 0.2, "slip_pts": None,
             "broker_hour": None, "quarantine": []}]
    b = slip_breakdown(rows)
    assert list(b["by_sleeve"]) == ["a"]
    assert list(b["by_symbol_hour"]["XAUUSD"]) == ["unknown"]
    m = compute([{"ticket": 1, "intended": 2000.0, "side": "buy", "symbol": "ZZZ"}],
                [_deal(1, 2000.5, BUY)], points={})
    assert "clean mean slip      UNMEASURED" in render(m)


def test_main_renders_from_the_desk_ledgers(monkeypatch, tmp_path, capsys):
    import mt5desk.config as cfg
    monkeypatch.setattr(cfg, "DATA", tmp_path)
    from mt5desk import markout as mk
    assert mk.main() == 0
    assert "EXECUTION MARKOUT" in capsys.readouterr().out
