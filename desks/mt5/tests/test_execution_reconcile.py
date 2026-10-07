"""ARCH-06: an authoritative account ledger, and the reconciliation of positions vs the order
door's ledger vs the intents (partial fills, missing acks, restarts, duplicate messages)."""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
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


def _publisher() -> Any:
    spec = importlib.util.spec_from_file_location(
        "publish_account_state_arch06", _ROOT / "ops" / "publish_account_state.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _info(**kw: Any) -> SimpleNamespace:
    base = {"login": 5551234, "company": "Venue", "server": "Srv", "currency": "EUR",
            "balance": 1000.0, "equity": 1012.5, "margin": 50.0, "margin_free": 962.5,
            "margin_level": 2025.0}
    return SimpleNamespace(**{**base, **kw})


def _pos(ticket: int, profit: float, swap: float) -> SimpleNamespace:
    return SimpleNamespace(ticket=ticket, identifier=ticket, symbol="EURUSD", type=0,
                           volume=0.1, price_open=1.1, sl=1.09, tp=1.12, profit=profit,
                           swap=swap, magic=341953, comment="DWx", time=1)


def test_the_account_record_carries_margin_level_swap_and_positions() -> None:
    mod = _publisher()
    rec = mod.build_record(_info(), [], [_pos(1, 10.0, 0.5), _pos(2, 3.0, -1.0)], NOW)
    for k in (*rd.ACCOUNT_FIELDS, "margin_level"):
        assert rec.get(k) is not None, k
    assert rec["margin"] == 50.0 and rec["margin_level"] == 2025.0 and rec["swap"] == -0.5
    assert [p["ticket"] for p in rec["positions"]] == [1, 2] and rec["open_positions"] == 2
    assert rec["ledger_check"]["consistent"] is True          # 1000 + 13 - 0.5 == 1012.5
    assert "login" not in rec and "5551234" not in json.dumps(rec)
    bad = mod.build_record(_info(equity=900.0), [], [_pos(1, 10.0, 0.0)], NOW)
    assert bad["ledger_check"]["consistent"] is False
    # a terminal without margin_level gets MT5's own definition
    lvl = mod.build_record(_info(margin_level=None), [], [], NOW)["margin_level"]
    assert lvl == round(1012.5 / 50.0 * 100, 2)


def test_recovery_drills_account_row_wants_measured_fields(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "account_state.json"
    monkeypatch.setattr(rd, "ACCOUNT", p)
    rec = _publisher().build_record(_info(), [], [_pos(1, 12.5, 0.0)], NOW)
    p.write_text(json.dumps({**rec, "generated_utc": NOW.isoformat()}))
    assert rd._account(NOW)["verdict"] == rd.PASS
    p.write_text(json.dumps({**rec, "margin": None, "generated_utc": NOW.isoformat()}))
    assert rd._account(NOW)["verdict"] == rd.FAIL               # a null margin is not a margin


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
    gw = [r for r in d["scenarios"] if r["scenario"].startswith("gateway_")]
    if any(r["verdict"] == xr.UNMEASURED for r in gw):
        pytest.skip(f"gateway does not import here: {gw}")
    assert all(r["verdict"] == "PASS" for r in gw), gw
    assert d["verdict"] == "PASS"


def test_the_gateway_drill_hands_over_its_ledgers() -> None:
    from libs.tiers import gateway_drill as gd
    r = gd.run_fault("healthy", with_ledgers=True)
    if r["status"] != "MEASURED":
        pytest.skip(f"gateway does not import here: {r}")
    led = r["observed"]["ledgers"]
    assert len(led["door"]) == r["observed"]["sends"] == len(led["intents"])
    assert "ledgers" not in gd.run_fault("healthy")["observed"]


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
