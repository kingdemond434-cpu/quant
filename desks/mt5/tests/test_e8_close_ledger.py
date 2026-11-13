"""The E8 closed-trade ledger records what came back from the venue, for our own sends only."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from prop import e8_close_ledger as cl  # noqa: E402
from prop import e8_guard  # noqa: E402

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
SEND = {"status": "SENT", "order_id": 11, "sleeve": "audchf_overnight_gap_decay_asia_p_x",
        "symbol": "AUDCHF", "side": "buy", "lot": 2.0, "stop": 0.5790, "risk_usd": 1000.0,
        "at": "2026-10-12T22:41:26+00:00", "latency_send_to_ack_ms": 90.0}
HIST = [{"id": 11, "positionId": 5, "status": "Filled", "side": "buy", "avgPrice": 0.5800,
         "filledQty": 2.0, "createdDate": "1"},
        {"id": 12, "positionId": 5, "status": "Filled", "side": "sell", "avgPrice": 0.5790,
         "filledQty": 2.0, "createdDate": "2"},
        {"id": 21, "positionId": 6, "status": "Filled", "side": "buy", "avgPrice": 1.0,
         "filledQty": 1.0, "createdDate": "1"}]


def test_a_closed_position_of_ours_is_recorded_with_its_r_and_charged_risk() -> None:
    rows = cl.closed_positions(HIST, set(), cl.our_sends([[SEND]]), done=set(), now=NOW)
    assert len(rows) == 1, "position 6 was opened by an order that is not ours"
    r = rows[0]
    assert r["position_id"] == 5 and abs(r["r_multiple"] + 1.0) < 1e-9
    assert r["risk_frac"] == 0.01 and r["pl_usd_est"] == -1000.0


def test_open_or_already_recorded_positions_are_skipped() -> None:
    sends = cl.our_sends([[SEND]])
    assert cl.closed_positions(HIST, {5}, sends, done=set(), now=NOW) == []
    assert cl.closed_positions(HIST, set(), sends, done={"5"}, now=NOW) == []


def test_record_is_idempotent_and_marks_the_ledger_measured(tmp_path: Path) -> None:
    journal = tmp_path / "j.jsonl"
    journal.write_text(json.dumps(SEND) + "\n")
    ledger = tmp_path / "e8_ledger.jsonl"

    class _Api:
        def get_all_orders(self, **_k):
            return HIST

    class _Venue:
        _api = _Api()

        def positions(self):
            return []

    first = cl.record(_Venue(), ledger=ledger, now=NOW, journals=(journal,))
    again = cl.record(_Venue(), ledger=ledger, now=NOW, journals=(journal,))
    assert first["new_closes"] == 1 and again["new_closes"] == 0
    assert len(ledger.read_text().splitlines()) == 1


def test_the_start_balance_is_the_guards() -> None:
    assert cl.START_BALANCE == e8_guard.START_BALANCE
