"""VITALS: one live file of the desk's state, ratios only on the wire (2026-11-13)."""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
REPO = DESK.parents[1]


def _vitals(monkeypatch, root: Path):
    monkeypatch.setenv("VITALS_DESK", str(root))
    spec = importlib.util.spec_from_file_location("vitals_t", DESK / "research" / "vitals.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _w(root: Path, rel: str, doc: object) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), "utf-8")


def _seed(root: Path) -> None:
    today = datetime.now(UTC).date().isoformat()
    _w(root, "reports/E8_EXEC.json", {"at": "t", "risk_usd_per_trade": 150.0, "guard": {
        "equity": 101500.0, "day_start": 100000.0, "day_pnl": 1500.0,
        "room_to_daily_floor": 2000.0, "may_open": True}})
    _w(root, "reports/FTMO_ACCOUNT_STATE.json", {
        "status": "OK", "generated_at": "t", "account_key": "sha256:deadbeefdeadbeef",
        "phase": "phase1", "initial_balance": 10000.0, "balance": 9900.0, "equity": 9900.0,
        "day_start_balance": 10000.0, "days_traded": 3, "open_positions": []})
    _w(root, "data/gateway_state.json", {"equity": 505.0,
                                          "day_start_equity": {"date": today, "equity": 500.0}})
    _w(root, "data/sleeves.json", {"sleeves": [{"name": "a", "status": "LIVE"},
                                               {"name": "b", "status": "STANDBY"},
                                               {"name": "c", "status": "RETIRED"}]})
    _w(root, "reports/UNIVERSAL_SURVIVORS.json", {"survivors": {
        "x": {"cell": "AUDCHF.overnight_gap_decay.p=1", "sym": "AUDCHF"},
        "y": {"cell": "XAUUSD.session_range_breakout.p=2", "sym": "XAUUSD"}}})
    _w(root, "data/CERT_BOOK_LIVE.json", {"ftmo": {"gold_asia": 0.0025, "z": 0.0}})
    _w(root, "reports/process_health.json", {"at": "t", "processes": [
        {"name": "MT5-Gateway", "last_run": "r", "last_result_code": 0, "verdict": "OK"}]})
    door = root / "data" / "order_door_ledger.jsonl"
    door.write_text(json.dumps({"at": datetime.now(UTC).isoformat(), "caller": "e8_gold",
                                "door": "sent"}) + "\n", "utf-8")


def test_vitals_carries_every_section_with_ratios_only(tmp_path, monkeypatch) -> None:
    root = tmp_path / "desks" / "mt5"
    _seed(root)
    v = _vitals(monkeypatch, root)
    doc = v.build()
    for key in ("heartbeat_at", "adopted", "certs_clocks", "breadth", "sleeves", "accounts",
                "allocator", "organs", "ci_queue"):
        assert key in doc
    assert doc["sleeves"]["live"] == 1 and doc["sleeves"]["standby"] == 1
    assert doc["breadth"]["certs"] == 2 and doc["breadth"]["families"] == 2
    assert doc["certs_clocks"]["per_lane"]["ftmo"]["funded"] == 1
    e8 = doc["accounts"]["e8"]
    assert e8["pnl_today_pct"] == 0.015 and e8["pnl_today_R"] == 10.0 and e8["trades_today"] == 1
    assert doc["accounts"]["fusion"]["pnl_today_pct"] == 0.01
    assert doc["accounts"]["ftmo"]["pnl_today_pct"] == -0.01
    # #1075 / MF2: no absolute money and no account key reach the wire
    wire = json.dumps(doc)
    for money in ("101500", "100000", "9900", "505.0", "deadbeef"):
        assert money not in wire, money


def test_absent_sources_read_unmeasured_not_zero(tmp_path, monkeypatch) -> None:
    v = _vitals(monkeypatch, tmp_path / "desks" / "mt5")
    doc = v.build()
    assert doc["sleeves"]["live"] == "UNMEASURED"
    assert doc["breadth"]["certs"] == "UNMEASURED"


def test_a_stale_heartbeat_is_red(tmp_path) -> None:
    sys.path.insert(0, str(REPO / "scripts"))
    import check_vitals_fresh as cv

    p = tmp_path / "VITALS.json"
    now = datetime.now(UTC)
    p.write_text(json.dumps({"heartbeat_at": (now - timedelta(seconds=30)).isoformat()}), "utf-8")
    assert cv.verdict(p, 120, now)[0] is True
    p.write_text(json.dumps({"heartbeat_at": (now - timedelta(minutes=10)).isoformat()}), "utf-8")
    ok, msg = cv.verdict(p, 120, now)
    assert ok is False and msg.startswith("RED")
    assert cv.verdict(tmp_path / "absent.json", 120, now)[0] is False
