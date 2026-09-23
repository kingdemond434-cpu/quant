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
    "ticket": 111, "retcode": 10009, "latency_ms": 12.5,
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
    monkeypatch.setattr(fr, "LEDGER", tmp_path / "no_ledger.jsonl")
    doc = fr.build(dry_run=True)
    assert doc["status"] == "UNMEASURED"
    assert "not the same as no slippage" in doc["why"]


def test_the_corpus_row_carries_every_field_the_principal_named(tmp_path: Path,
                                                                monkeypatch: Any) -> None:
    from libs.execution import fill_corpus as fc
    monkeypatch.setattr(fr, "INTENTS", tmp_path / "i.jsonl")
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
