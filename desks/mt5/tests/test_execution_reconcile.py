"""ARCH-06: the reconciliation of the account book vs the order door's ledger vs the intents
(partial fills, missing acks, restarts, duplicate messages)."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import execution_reconcile as xr  # noqa: E402
from research import recovery_drills as rd  # noqa: E402

NOW = datetime(2026, 10, 7, 12, tzinfo=UTC)


def _sent(**kw: Any) -> dict[str, Any]:
    req = {"action": 1, "symbol": "EURUSD", "volume": 0.1, "type": 0, "price": 1.1,
           "sl": 1.09, "tp": 1.12, "magic": 341953, "comment": "DWx"}
    row = {"at": NOW.isoformat(), "kind": "open", "door": "sent", "caller": "gateway",
           "symbol": "EURUSD", "request": req, "validation": "ok", "order": 11, "retcode": 10009}
    return {**row, **kw}


def test_the_join_names_each_break() -> None:
    intent = {"symbol": "EURUSD", "sl": 1.09, "tp": 1.12, "lot": 0.1, "ticket": 11}
    clean = xr.reconcile([_sent()], [intent], [], now=NOW)
    assert clean["verdict"] == xr.RECONCILED and not clean["breaks"]
    no_intent = xr.reconcile([_sent()], [], [], now=NOW)
    assert "send_without_intent" in xr._checks(no_intent, xr.BREAK)
    stray = xr.reconcile([_sent()], [intent, {**intent, "ticket": 99}], [], now=NOW)
    assert "intent_without_door" in xr._checks(stray, xr.BREAK)
    twice = xr.reconcile([_sent(), _sent()], [intent, intent], [], now=NOW)
    assert "order_acked_twice" in xr._checks(twice, xr.BREAK)
    old = (NOW - timedelta(hours=2)).isoformat()
    lost = xr.reconcile([_sent(at=old, validation="no_result", order=None, in_doubt=True)],
                        None, None, now=NOW)
    assert "missing_ack_unsettled" in xr._checks(lost, xr.BREAK)
    dup = xr.reconcile([_sent(at=old, validation="no_result", order=None, in_doubt=True),
                        _sent(at=(NOW - timedelta(hours=1, minutes=40)).isoformat())],
                       None, None, now=NOW)
    assert "duplicate_execution" in xr._checks(dup, xr.BREAK)
    assert xr.reconcile([], None, None, None, None)["verdict"] == xr.UNMEASURED


def test_the_shadow_drill_catches_every_planted_break_and_clears_every_clean_book() -> None:
    d = xr.drill()
    by = {r["scenario"]: r for r in d["scenarios"]}
    for sid in ("partial_fill", "partial_fill_planted", "missing_ack", "missing_ack_planted",
                "restart", "restart_planted", "duplicate_resend", "duplicate_deals"):
        assert by[sid]["verdict"] == "PASS", by[sid]
    assert len(by) == 8
    assert d["verdict"] == "PASS" and (d["passed"], d["n"]) == (8, 8)


def test_an_unmeasured_gateway_row_is_published_and_never_counted_as_a_pass() -> None:
    d = xr.drill()
    assert d["gateway"] and not any(r["scenario"].startswith("gateway") for r in d["scenarios"])
    unmeasured = [r for r in d["gateway"] if r["verdict"] == xr.UNMEASURED]
    assert d["gateway_measured"] == len(d["gateway"]) - len(unmeasured)
    assert d["passed"] == sum(1 for r in d["scenarios"] if r["verdict"] == "PASS")
    assert all(r["why"] for r in unmeasured)


def _live_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, book: Any) -> None:
    for name, attr in (("order_door_ledger.jsonl", "DOOR"), ("order_intents.jsonl", "INTENTS"),
                       ("live_ledger.jsonl", "DEALS"), ("account_state.json", "ACCOUNT"),
                       ("account_positions.json", "POSITIONS")):
        monkeypatch.setattr(xr, attr, tmp_path / name)
    monkeypatch.setattr(xr, "DESK", tmp_path)
    (tmp_path / "order_door_ledger.jsonl").write_text(json.dumps(_sent()) + "\n")
    (tmp_path / "order_intents.jsonl").write_text(
        json.dumps({"ts": NOW.isoformat(), "ticket": 11, "sleeve": "s", "symbol": "EURUSD",
                    "sl": 1.09, "tp": 1.12, "lot": 0.1}) + "\n")
    (tmp_path / "account_state.json").write_text(json.dumps(
        {"balance": 1000.0, "equity": 1000.0, "margin": 5.0, "open_positions": 1}))
    if book is not None:
        (tmp_path / "account_positions.json").write_text(json.dumps(book))


def test_the_live_join_reads_the_untracked_position_book(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    row = {"ticket": 11, "symbol": "EURUSD", "side": "buy", "volume": 0.1, "magic": 341953}
    _live_files(tmp_path, monkeypatch, book={"positions": [row]})
    lv = xr.live(NOW)
    assert lv["absent"] == [] and lv["rows"]["positions"] == 1
    assert lv["verdict"] == xr.RECONCILED, lv["findings"]
    assert "account_count_mismatch" not in xr._checks(lv)
    _live_files(tmp_path, monkeypatch, book={"positions": [row, {**row, "ticket": 12}]})
    assert "account_count_mismatch" in xr._checks(xr.live(NOW), xr.BREAK)   # 1 counted, 2 held


def test_an_absent_position_book_is_unmeasured_never_reconciled(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _live_files(tmp_path, monkeypatch, book=None)
    lv = xr.live(NOW)
    assert lv["verdict"] == xr.UNMEASURED and lv["absent"] == ["account_positions.json"]


def test_recovery_drills_grades_the_reconciliation(tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "EXECUTION_RECONCILE.json"
    monkeypatch.setattr(rd, "RECONCILE", p)
    assert rd._reconciliation(NOW)["verdict"] == rd.UNMEASURED
    base = {"generated_utc": NOW.isoformat(), "drill": {"verdict": "PASS", "passed": 12, "n": 12},
            "live": {"verdict": "UNMEASURED", "absent": ["data/order_door_ledger.jsonl"]}}
    p.write_text(json.dumps(base))
    assert rd._reconciliation(NOW)["verdict"] == rd.UNMEASURED     # live unread: never PASS
    p.write_text(json.dumps({**base, "live": {"verdict": "RECONCILED", "rows": {}}}))
    assert rd._reconciliation(NOW)["verdict"] == rd.PASS
    p.write_text(json.dumps({**base, "live": {"verdict": "BREAKS", "breaks": 1, "findings": [
        {"check": "send_without_intent", "severity": "BREAK"}]}}))
    assert rd._reconciliation(NOW)["verdict"] == rd.FAIL
    assert "reconciliation" in {d[0] for d in rd.DRILLS}
