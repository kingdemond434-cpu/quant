"""E8 fills ledger (box 11-24: E8 had none, so its realised R was unmeasured)."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK), str(DESK.parents[1])):
    if p not in sys.path:
        sys.path.insert(0, p)

from prop import e8_fills as ef  # noqa: E402

T0 = datetime(2026, 11, 24, 5, 30, tzinfo=UTC)


class _V:
    def __init__(self, positions, balance):
        self._p, self._b = positions, balance

    def positions(self):
        return self._p

    def account(self):
        return {"balance": self._b, "equity": self._b}


def _paths(tmp_path: Path):
    intents = tmp_path / "intents.jsonl"
    intents.write_text(json.dumps({"at": "2026-11-24T05:01:00+00:00", "status": "SENT",
                                   "side": "buy_stop", "sl": 4276.5, "price": 4310.0}) + "\n",
                       encoding="utf-8")
    return {"state": tmp_path / "s.json", "ledger": tmp_path / "l.jsonl", "intents": intents}


POS = {"id": 77, "side": "buy", "qty": 0.1, "avgPrice": 4310.0, "openDate": "x"}


def test_a_closed_position_writes_one_measured_row(tmp_path):
    kw = _paths(tmp_path)
    assert ef.observe(_V([POS], 100_000.0), now=T0, **kw)["open"] == 1
    out = ef.observe(_V([], 100_670.0), now=T0 + timedelta(minutes=5), **kw)
    assert out == {"open": 0, "closed": 1, "written": 1}
    (row,) = [json.loads(x) for x in kw["ledger"].read_text().splitlines()]
    assert row["book"] == "e8" and row["position_id"] == "77"
    assert row["risk_quote"] == 335.0                    # 33.5 x 0.1 x 100
    assert row["pl_net_quote"] == 670.0 and row["r_multiple"] == 2.0
    assert not any(b in row for b in ef.BANNED)
    # idempotent: the same close is never written twice
    ef.observe(_V([], 100_670.0), now=T0 + timedelta(minutes=10), **kw)
    assert len(kw["ledger"].read_text().splitlines()) == 1


def test_two_closes_in_one_gap_leave_pl_unmeasured(tmp_path):
    kw = _paths(tmp_path)
    ef.observe(_V([POS, {**POS, "id": 78}], 100_000.0), now=T0, **kw)
    ef.observe(_V([], 100_500.0), now=T0 + timedelta(minutes=5), **kw)
    rows = [json.loads(x) for x in kw["ledger"].read_text().splitlines()]
    assert len(rows) == 2 and all(r["pl_net_quote"] is None and r["r_multiple"] is None
                                  and r["pl_status"].startswith("UNMEASURED") for r in rows)


def test_a_broken_venue_never_raises(tmp_path):
    class _Bad:
        def positions(self):
            raise RuntimeError("TradeLocker down")

    assert "error" in ef.observe(_Bad(), now=T0, **_paths(tmp_path))


def test_the_first_pass_writes_nothing(tmp_path):
    kw = _paths(tmp_path)
    assert ef.observe(_V([], 100_000.0), now=T0, **kw)["written"] == 0
    assert not kw["ledger"].exists()
