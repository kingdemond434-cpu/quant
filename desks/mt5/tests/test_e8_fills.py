"""E8 fills ledger (box 11-24: E8 had none, so its realised R was unmeasured)."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import ClassVar

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK), str(DESK.parents[1])):
    if p not in sys.path:
        sys.path.insert(0, p)

from prop import e8_fills as ef  # noqa: E402

T0 = datetime(2026, 11, 24, 5, 30, tzinfo=UTC)
XAU, EURUSD = 6102, 101


class _V:
    _by_key: ClassVar[dict[str, int]] = {"XAUUSD": XAU, "EURUSD": EURUSD}

    def __init__(self, positions, balance):
        self._p, self._b = positions, balance

    def positions(self):
        return self._p

    def account(self):
        return {"balance": self._b, "equity": self._b}


def _intent(side="buy_stop", price=4310.0, sl=4276.5, lot=0.1, at="2026-11-24T05:01:00+00:00"):
    return json.dumps({"at": at, "status": "SENT", "side": side, "sl": sl, "price": price,
                       "lot": lot})


def _paths(tmp_path: Path, *intents: str):
    p = tmp_path / "intents.jsonl"
    p.write_text("\n".join(intents or (_intent(),)) + "\n", encoding="utf-8")
    return {"state": tmp_path / "s.json", "ledger": tmp_path / "l.jsonl", "intents": p}


POS = {"id": 77, "side": "buy", "qty": 0.1, "avgPrice": 4310.0, "openDate": "x",
       "tradableInstrumentId": XAU}


def _pass(kw, positions, balance, k):
    return ef.observe(_V(positions, balance), now=T0 + timedelta(minutes=5 * k), **kw)


def _rows(kw):
    return [json.loads(x) for x in kw["ledger"].read_text().splitlines()] \
        if kw["ledger"].exists() else []


def test_a_close_confirmed_on_two_reads_writes_one_measured_row(tmp_path):
    kw = _paths(tmp_path)
    _pass(kw, [POS], 100_000.0, 0)
    assert _pass(kw, [], 100_670.0, 1)["written"] == 0          # one absence is not a close
    assert _pass(kw, [], 100_670.0, 2)["written"] == 1
    (row,) = _rows(kw)
    assert row["book"] == "e8" and row["position_id"] == "77" and row["symbol"] == "XAUUSD"
    assert row["risk_quote"] == 335.0                             # 33.5 x 0.1 x 100
    assert row["pl_net_quote"] == 670.0 and row["r_multiple"] == 2.0
    assert not any(b in row for b in ef.BANNED)
    _pass(kw, [], 100_670.0, 3)
    assert len(_rows(kw)) == 1                                    # idempotent


def test_an_empty_read_with_an_unchanged_balance_is_unmeasured_never_a_close(tmp_path):
    """Audit MF-1: one empty venue read must not write a P/L-0 row that dedupes the real one."""
    kw = _paths(tmp_path)
    _pass(kw, [POS], 100_000.0, 0)
    for k in (1, 2, 3):
        out = _pass(kw, [], 100_000.0, k)
        assert out["status"].startswith("UNMEASURED") and out["written"] == 0
    _pass(kw, [POS], 100_000.0, 4)                                # it was open all along
    _pass(kw, [], 99_665.0, 5)
    _pass(kw, [], 99_665.0, 6)
    (row,) = _rows(kw)
    assert row["pl_net_quote"] == -335.0 and row["r_multiple"] == -1.0


def test_a_position_that_reappears_is_not_closed(tmp_path):
    kw = _paths(tmp_path)
    _pass(kw, [POS, {**POS, "id": 78}], 100_000.0, 0)
    _pass(kw, [{**POS, "id": 78}], 100_000.0, 1)                  # partial read
    _pass(kw, [POS, {**POS, "id": 78}], 100_000.0, 2)
    _pass(kw, [POS, {**POS, "id": 78}], 100_000.0, 3)
    assert _rows(kw) == []


def test_two_closes_in_one_span_leave_pl_unmeasured(tmp_path):
    kw = _paths(tmp_path)
    _pass(kw, [POS, {**POS, "id": 78}], 100_000.0, 0)
    _pass(kw, [], 100_500.0, 1)
    _pass(kw, [], 100_500.0, 2)
    rows = _rows(kw)
    assert len(rows) == 2 and all(r["pl_net_quote"] is None and r["r_multiple"] is None
                                  and r["pl_status"].startswith("UNMEASURED") for r in rows)


def test_a_non_gold_close_has_its_own_symbol_and_no_gold_risk(tmp_path):
    """Audit MF-2: a non-gold E8 close never borrows the gold contract or a gold stop."""
    kw = _paths(tmp_path)
    fx = {**POS, "id": 90, "avgPrice": 1.08, "tradableInstrumentId": EURUSD}
    _pass(kw, [fx], 100_000.0, 0)
    _pass(kw, [], 100_100.0, 1)
    _pass(kw, [], 100_100.0, 2)
    (row,) = _rows(kw)
    assert row["symbol"] == "EURUSD" and row["risk_quote"] is None and row["r_multiple"] is None
    assert row["risk_status"].startswith("UNMEASURED") and row["pl_net_quote"] == 100.0


def test_an_unknown_instrument_is_unmeasured(tmp_path):
    kw = _paths(tmp_path)
    _pass(kw, [{**POS, "tradableInstrumentId": 999}], 100_000.0, 0)
    _pass(kw, [], 100_100.0, 1)
    _pass(kw, [], 100_100.0, 2)
    (row,) = _rows(kw)
    assert row["symbol"] is None and row["risk_quote"] is None


def test_two_windows_on_one_side_pick_the_matching_leg_or_none(tmp_path):
    """Should-fix: the stop is matched on lot and nearest entry, never 'the last SENT'."""
    a = _intent(price=4310.0, sl=4276.5, lot=0.1)
    b = _intent(price=4350.0, sl=4330.0, lot=0.1, at="2026-11-24T11:01:00+00:00")
    p = _paths(tmp_path, a, b)["intents"]
    assert ef.sent_stop(p, "buy", "2026-11-24", qty=0.1, entry=4310.4) == 4276.5
    assert ef.sent_stop(p, "buy", "2026-11-24", qty=0.1, entry=4351.0) == 4330.0
    assert ef.sent_stop(p, "buy", "2026-11-24", qty=0.1, entry=4330.0) is None    # a tie
    assert ef.sent_stop(p, "buy", "2026-11-24", qty=0.2, entry=4310.0) is None    # no lot match


def test_a_broken_venue_never_raises(tmp_path):
    class _Bad:
        def positions(self):
            raise RuntimeError("TradeLocker down")

    assert "error" in ef.observe(_Bad(), now=T0, **_paths(tmp_path))


def test_the_first_pass_writes_nothing(tmp_path):
    kw = _paths(tmp_path)
    assert _pass(kw, [], 100_000.0, 0)["written"] == 0
    assert not kw["ledger"].exists()
