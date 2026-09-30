"""The live account's fills, recorded: asked, got, when, at what spread, and what it cost.

The properties that make the number trustworthy, not the plumbing. Every one of these is a
defect that was actually live on this box on 2026-09-23 and would have published a number.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import fill_recorder as fr  # noqa: E402

_INTENT: dict[str, Any] = {
    "time": "2026-09-16T09:00:00+00:00", "intent_id": "i1", "sleeve": "s", "symbol": "EURGBP",
    "side": "buy_stop", "lot": 0.1, "intended": 0.85613, "sl": 0.85513, "tp": 0.85813,
    # `latency_send_to_ack_ms` is the wall the gateway now stamps beside `latency_ms`: the same
    # round trip under the name the corpus reads it by, so send-to-fill stops being a field the
    # shortfall model finds empty on every row.
    "ticket": 111, "retcode": 10009, "latency_ms": 12.5, "latency_send_to_ack_ms": 12.5,
    "decision_bid": 0.85610, "decision_ask": 0.85614, "spread_at_decision": 0.00004,
    "point": 0.00001,
}
_DEAL: dict[str, Any] = {
    "time": "2026-09-16T09:30:00+00:00", "symbol": "EURGBP", "side": 0, "deal": 900,
    "entry_order": 111, "position_id": 111, "entry_price": 0.85627, "sl": 0.85513,
    "fill_price": 0.85700, "volume": 0.1, "contract_size": 100000.0, "risk_quote": 10.0,
    "r_multiple": 0.5, "commission": -0.5, "account_kind": "live",
}


def test_the_join_is_the_bridge_mt5_offers() -> None:
    pairs, unfilled, unmatched, census = fr.match([_INTENT], [_DEAL])
    assert len(pairs) == 1
    assert census["entry_order"] == 1
    assert unfilled == [] and unmatched == []


def test_slippage_is_measured_against_the_entry_never_the_close() -> None:
    """The defect that published +203 R of slippage on this box's thirty real fills: the ledger
    row's `fill_price` is the CLOSING price, and falling back to it measures the trade, not the
    execution."""
    row = fr.build_row(_INTENT, _DEAL, "entry_order", {})
    assert row["fill_price"] == _DEAL["entry_price"]
    assert row["fill_price"] != _DEAL["fill_price"]
    # asked 0.85613, got 0.85627 on a buy: 14 points worse than asked, signed positive.
    assert row["slip_points"] is not None
    assert abs(row["slip_points"] - 14.0) < 1e-6
    assert row["slip_r"] is not None and row["slip_r"] > 0


def test_an_unreadable_entry_price_leaves_the_fill_unmeasured() -> None:
    """`_position_entry` returns 0.0 when a position's opening deal cannot be read. Zero is not
    a fill price."""
    row = fr.build_row(_INTENT, {**_DEAL, "entry_price": 0.0}, "entry_order", {})
    assert row["fill_price"] is None
    assert row["slip_points"] is None and row["slip_r"] is None
    assert row["status"] == "UNRESOLVED"
    # what IS known is still recorded
    assert row["quote_bid"] == _INTENT["decision_bid"]
    assert row["latency_decision_to_send_ms"] == 12.5


def test_the_r_denominator_is_the_stop_geometry_not_the_ledgers_figure() -> None:
    """`risk_quote` arrives negative and in inconsistent units on this box; |entry - stop| x
    contract x lots is the definition `r_multiple` is written against."""
    row = fr.build_row(_INTENT, {**_DEAL, "risk_quote": -40.07}, "entry_order", {})
    expected = (0.85627 - 0.85613) / abs(0.85627 - 0.85513)
    assert row["slip_r"] is not None
    assert abs(row["slip_r"] - expected) < 1e-6
    assert row["join_keys"]["r_denominator"].startswith("|entry - stop|")


def test_a_stop_on_the_entry_has_no_r_denominator() -> None:
    row = fr.build_row(_INTENT, {**_DEAL, "sl": 0.85627, "risk_quote": 0.0},
                       "entry_order", {})
    assert row["slip_r"] is None


def test_the_point_size_is_read_off_the_quote_when_the_intent_has_none() -> None:
    """28 of this box's 30 matched fills predate `point` on the intent row."""
    row = fr.build_row({**_INTENT, "point": None}, _DEAL, "entry_order", {})
    assert row["point"] is not None
    assert abs(row["point"] - 1e-5) < 1e-12
    assert row["join_keys"]["point_basis"].startswith("derived")
    assert fr._point_from(4340.57) == 0.01
    assert fr._point_from(None) is None


def test_an_order_that_never_traded_is_never_a_zero_slip() -> None:
    row = fr.unfilled_row({**_INTENT, "fill_price": None})
    assert row["status"] == "UNRESOLVED"
    assert row["fill_price"] is None
    assert row.get("slip_r") is None
    assert row["quote_bid"] == _INTENT["decision_bid"]


def test_a_market_order_that_filled_needs_no_closing_deal() -> None:
    """The venue answers `order_send` with its fill; the gateway records it from 2026-09-23."""
    row = fr.unfilled_row({**_INTENT, "side": "buy", "fill_price": 0.85620,
                           "fill_volume": 0.1})
    assert row["status"] == "FILLED"
    assert row["slip_points"] is not None and abs(row["slip_points"] - 7.0) < 1e-6
    assert row["join_keys"]["basis"] == "intent_fill"


def test_absent_ledgers_are_unmeasured_never_zero_matched_fills(monkeypatch: Any,
                                                                tmp_path: Path) -> None:
    monkeypatch.setattr(fr, "INTENTS", tmp_path / "no_intents.jsonl")
    # THE PROP BOOK IS A SOURCE TOO. Both accounts place real orders and the recorder reads both;
    # a test that isolates only the live ledger leaves the real e8 file underneath and measures
    # the box instead of the fixture.
    monkeypatch.setattr(fr, "E8_INTENTS", tmp_path / "no_e8.jsonl")
    monkeypatch.setattr(fr, "LEDGER", tmp_path / "no_ledger.jsonl")
    doc = fr.build(dry_run=True)
    assert doc["status"] == "UNMEASURED"
    assert "not the same as no slippage" in doc["why"]


def test_the_corpus_row_carries_every_field_the_principal_named(tmp_path: Path,
                                                                monkeypatch: Any) -> None:
    from libs.execution import fill_corpus as fc
    monkeypatch.setattr(fr, "INTENTS", tmp_path / "i.jsonl")
    monkeypatch.setattr(fr, "E8_INTENTS", tmp_path / "e8.jsonl")
    monkeypatch.setattr(fr, "LEDGER", tmp_path / "l.jsonl")
    monkeypatch.setattr(fr, "DECISIONS", tmp_path / "d.jsonl")
    monkeypatch.setattr(fr, "CORPUS", tmp_path / "corpus.jsonl")
    fr.INTENTS.write_text(json.dumps(_INTENT) + "\n", encoding="utf-8")
    fr.LEDGER.write_text(json.dumps(_DEAL) + "\n", encoding="utf-8")
    doc = fr.build()
    assert doc["matched_fills"] == 1
    assert doc["rows_written"] == 1
    for field in fr.REQUIRED_FIELDS:
        assert doc["completeness"][field]["n"] == 1, field
    # and it reads back through the corpus's own reader with the new fields intact
    rec = fc.record_from_row(fc.read_rows(fr.CORPUS)[0])
    assert rec.slip_points is not None
    assert rec.spread_points_at_decision is not None
    assert rec.quote_mid_at_decision is not None
    assert rec.schema_version >= 2
    # a second pass appends nothing: the corpus key is stable
    assert fr.build()["rows_written"] == 0


# ---------------------------------------------------------------- the join, on box-shaped rows
# Copied verbatim from the committed box ledgers (desks/mt5/data/order_intents.jsonl and
# live_ledger.jsonl as of 2026-09-30). The ledger's `side` is the CLOSING deal's type: every one
# of these shorts closes with a BUY (0) and every long with a SELL (1).
_BOX_INTENTS: list[dict[str, Any]] = [
    {"sleeve": "gold_london_am", "symbol": "XAUUSD", "side": "sell_stop", "lot": 0.01,
     "intended": 4364.1, "sl": 4435.150000000001, "tp": 4222.400000000001,
     "ticket": 215819102, "retcode": 10009, "time": "2026-09-01T10:00:17+00:00"},
    # a rejected placement with the same geometry: ticket 0 never traded and never joins
    {"sleeve": "gold_afternoon", "symbol": "XAUUSD", "side": "buy_stop", "lot": 0.01,
     "intended": 4407.85, "sl": 4380.96, "tp": 4461.2300000000005, "ticket": 0,
     "retcode": 10015, "time": "2026-09-07T14:08:32+00:00"},
    {"sleeve": "gold_afternoon", "symbol": "XAUUSD", "side": "buy_stop", "lot": 0.01,
     "intended": 4407.85, "sl": 4380.96, "tp": 4461.2300000000005, "ticket": 218536618,
     "retcode": 10009, "decision_bid": 4406.93, "decision_ask": 4406.98, "point": 0.01,
     "order_type": "pending_stop", "time": "2026-09-07T14:10:28+00:00"},
    {"sleeve": "gold_afternoon", "symbol": "XAUUSD", "side": "buy_stop", "lot": 0.01,
     "intended": 4407.85, "sl": 4380.96, "tp": 4461.2300000000005, "ticket": 218537186,
     "retcode": 10009, "decision_bid": 4407.49, "decision_ask": 4407.55, "point": 0.01,
     "order_type": "pending_stop", "time": "2026-09-07T14:11:40+00:00"},
    {"sleeve": "xau_m15_anti_breakout", "symbol": "XAUUSD", "side": "buy", "lot": 0.01,
     "intended": 4351.47, "sl": 4339.891681552983, "tp": 4368.837477670526,
     "ticket": 221208826, "retcode": 10009, "time": "2026-09-11T18:19:15+00:00"},
]
_BOX_DEALS: list[dict[str, Any]] = [
    # legacy: no entry_order / position_id; `order` is the server's own stop/target order
    {"time": "2026-09-07T17:04:15+00:00", "sleeve": "gold_london_am", "symbol": "XAUUSD",
     "side": 0, "pl_quote": 8.47, "r_multiple": 0.0, "volume": 0.01, "commission": -0.02,
     "swap": 0.0, "deal": 194349021, "fill_price": 4351.09, "entry_price": 4360.93,
     "sl": 4435.15, "tp": 4222.4, "order": 216085421, "contract_size": 100.0,
     "risk_quote": -74.22, "account": 495044, "account_kind": "live"},
    {"time": "2026-09-08T15:08:25+00:00", "sleeve": "gold_afternoon", "symbol": "XAUUSD",
     "side": 1, "pl_quote": 4.93, "r_multiple": 0.0, "volume": 0.01, "commission": -0.02,
     "swap": 0.0, "deal": 196497927, "fill_price": 4413.65, "entry_price": 4407.89,
     "sl": 4380.96, "tp": 4461.23, "order": 218601290, "contract_size": 100.0,
     "risk_quote": -26.93, "account": 495044, "account_kind": "live"},
    {"time": "2026-09-08T15:08:25+00:00", "sleeve": "gold_afternoon", "symbol": "XAUUSD",
     "side": 1, "pl_quote": 4.86, "r_multiple": 0.0, "volume": 0.01, "commission": -0.02,
     "swap": 0.0, "deal": 196497929, "fill_price": 4413.66, "entry_price": 4407.98,
     "sl": 4380.96, "tp": 4461.23, "order": 218601292, "contract_size": 100.0,
     "risk_quote": -27.02, "account": 495044, "account_kind": "live"},
    # keyed: the bridge MT5 offers
    {"time": "2026-09-15T02:42:12+00:00", "sleeve": "xau_m15_anti_breakout", "symbol": "XAUUSD",
     "side": 1, "pl_quote": -0.11, "r_multiple": 0.0, "volume": 0.01, "commission": -0.02,
     "swap": 0.0, "deal": 198773659, "fill_price": 4351.47, "entry_price": 4351.57,
     "sl": 4339.89, "tp": 4368.84, "order": 221208829, "position_id": 221208826,
     "entry_order": 221208826, "entry_deal": 198773656, "close_order": 221208829,
     "magic": 341953, "contract_size": 100.0, "risk_quote": -11.68, "account": 495044,
     "account_kind": "live"},
]


def _corpus_rows(p: Path) -> list[dict[str, Any]]:
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_the_ledgers_side_is_the_closing_deal_and_never_the_positions() -> None:
    from mt5desk.markout import position_direction
    # a closing BUY with the stop above the entry is a SHORT
    assert position_direction(_BOX_DEALS[0]) == -1
    # a closing SELL with the stop below the entry is a LONG
    assert position_direction(_BOX_DEALS[3]) == 1
    # `entry_side` (the opening deal's own type) outranks the geometry when present
    assert position_direction({**_BOX_DEALS[0], "entry_side": 0}) == 1
    # with no geometry at all, the closing side is inverted rather than read as-is
    assert position_direction({"side": 0}) == -1


def test_every_box_deal_joins_its_own_intent_one_to_one() -> None:
    pairs, unfilled, unmatched, census = fr.match(list(_BOX_INTENTS), list(_BOX_DEALS))
    assert unmatched == []
    assert census["entry_order"] == 1 and census["sl_tp_echo"] == 3
    got = {d["deal"]: it["ticket"] for it, d, _h in pairs}
    assert got[194349021] == 215819102
    assert got[198773659] == 221208826
    # two positions, one stop/target pair, two tickets: one each, never the same one twice
    assert {got[196497927], got[196497929]} == {218536618, 218537186}
    # the rejected placement (ticket 0) is the one intent left over
    assert [it["ticket"] for it in unfilled] == [0]


def test_the_echo_never_joins_a_moved_stop_the_wrong_direction_or_a_later_intent() -> None:
    moved = {**_BOX_DEALS[0], "sl": 4400.0}
    _p, _u, unmatched, census = fr.match([_BOX_INTENTS[0]], [moved])
    assert census["sl_tp_echo"] == 0 and len(unmatched) == 1
    flipped = {**_BOX_INTENTS[0], "side": "buy_stop"}
    _p, _u, unmatched, census = fr.match([flipped], [_BOX_DEALS[0]])
    assert census["sl_tp_echo"] == 0 and len(unmatched) == 1
    late = {**_BOX_INTENTS[0], "time": "2026-09-09T00:00:00+00:00"}
    _p, _u, unmatched, _c = fr.match([late], [_BOX_DEALS[0]])
    assert len(unmatched) == 1


def test_a_short_that_filled_worse_than_asked_is_positive_slippage() -> None:
    """Sell stop at 4364.10 filled at 4360.93: 317 points WORSE than asked, signed positive. The
    old markout read the closing BUY as the trade's direction and would have published -3.17."""
    from mt5desk.markout import compute
    m = compute([_BOX_INTENTS[0]], [_BOX_DEALS[0]])
    assert m.n_matched == 1
    assert abs(m.rows[0]["slip_quote"] - 3.17) < 1e-6
    row = fr.build_row(_BOX_INTENTS[0], _BOX_DEALS[0], "sl_tp_echo", {})
    assert row["slip_points"] is not None and abs(row["slip_points"] - 317.0) < 1e-6


def test_the_minute_tier_reads_the_positions_opening_clock_only() -> None:
    """The ledger's `time` is when the gateway RECORDED the close; only `entry_time` says when
    the position opened. A row without it is never offered to the minute tier."""
    it = {**_BOX_INTENTS[4], "ticket": 999, "sl": 1.0, "tp": 2.0}
    keyless = {k: v for k, v in _BOX_DEALS[3].items()
               if k not in ("entry_order", "position_id")}
    _p, _u, unmatched, census = fr.match([it], [{**keyless, "sl": 3.0}])
    assert census["symbol_minute"] == 0 and len(unmatched) == 1
    opened = {**keyless, "sl": 3.0, "entry_time": "2026-09-11T18:19:15.120000+00:00"}
    _p, _u, unmatched, census = fr.match([it], [opened])
    assert census["symbol_minute"] == 1 and unmatched == []


def test_matched_fills_counts_joins_and_supersedes_the_bare_row(tmp_path: Path,
                                                                 monkeypatch: Any) -> None:
    from libs.execution import fill_corpus as fc
    monkeypatch.setattr(fr, "INTENTS", tmp_path / "i.jsonl")
    monkeypatch.setattr(fr, "E8_INTENTS", tmp_path / "e8.jsonl")
    monkeypatch.setattr(fr, "LEDGER", tmp_path / "l.jsonl")
    monkeypatch.setattr(fr, "DECISIONS", tmp_path / "d.jsonl")
    monkeypatch.setattr(fr, "CORPUS", tmp_path / "corpus.jsonl")
    # pass 1: the ledger alone -- every deal is a realised fill, none is MATCHED
    fr.LEDGER.write_text("".join(json.dumps(d) + "\n" for d in _BOX_DEALS), encoding="utf-8")
    doc = fr.build()
    assert doc["matched_fills"] == 0 and doc["realised_fills"] == 4
    bare = [r for r in _corpus_rows(fr.CORPUS) if r["join_keys"]["basis"] == "deal_only"]
    assert len(bare) == 4
    assert {r["deal"]: r["side"] for r in bare}[194349021] == "sell"
    assert {r["deal"]: r["side"] for r in bare}[198773659] == "buy"
    # pass 2: the intents arrive -- four joins, and the four bare rows are superseded, not left
    fr.INTENTS.write_text("".join(json.dumps(i) + "\n" for i in _BOX_INTENTS), encoding="utf-8")
    doc = fr.build()
    assert doc["matched_fills"] == 4 and doc["join_census"]["sl_tp_echo"] == 3
    latest = {fc.record_from_row(r).key: r for r in fc.read_rows(fr.CORPUS)}
    filled = [r for r in latest.values() if r.get("status") == "FILLED"]
    assert len(filled) == 4, "a deal must never be counted twice, bare and joined"
    assert sum(1 for r in latest.values() if r.get("status") == "SUPERSEDED") == 4
