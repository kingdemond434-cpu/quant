"""RISK_SNAPSHOT: every account's floors and open risk, and UNMEASURED (never 0) when absent."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import risk_snapshot as rs  # noqa: E402

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


def _w(p: Path, doc: object) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), encoding="utf-8")


def _owners(desk: Path) -> None:
    """The rail owners' real sources, so constants are read exactly as on the box."""
    for rel in ("proposals/fusion_deadman.py", "mt5desk/fusion_equity_reference.py",
                "prop/e8_guard.py", "prop/ftmo_follower.py"):
        dst = desk / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text((DESK / rel).read_text(encoding="utf-8"), encoding="utf-8")


def _tree(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path
    desk = root / "desks" / "mt5"
    _owners(desk)
    return desk, root


def test_every_absent_input_is_unmeasured_never_zero(tmp_path: Path) -> None:
    desk, root = _tree(tmp_path)
    doc = rs.build(NOW, desk=desk, root=root)
    for name, acct in doc["accounts"].items():
        assert acct["equity"]["status"] == "UNMEASURED", name
        assert acct["open_risk"]["status"] == "UNMEASURED", name
        for fk, fv in acct["floors"].items():
            assert fv["status"] in ("UNMEASURED", "NO_RULE"), (name, fk)
            assert "distance" not in fv
    ev = doc["events_next_24h"]
    assert ev["calendar"]["status"] == "UNMEASURED"
    assert ev["event_ledger"]["status"] == "UNMEASURED"
    assert "fusion.equity" in doc["unmeasured"]


def test_fusion_floor_uses_withdrawn_offset_and_hysteresis(tmp_path: Path) -> None:
    desk, root = _tree(tmp_path)
    d = desk / "data"
    _w(d / "gateway_state.json", {"equity": 266.01, "last_reconcile": "2026-11-04T11:30:00+00:00",
                                  "day_start_equity": {"date": "2026-11-04", "equity": 270.0},
                                  "position": None})
    _w(d / "fusion_deadman_state.json", {"halt_codes": ["EQUITY_FLOOR"], "mode": "LIVE",
                                         "checked_at": "2026-11-04T11:55:00+00:00",
                                         "readings": {"open_positions": 0}})
    _w(d / "FUSION_EQUITY_REFERENCE.json", {"reference_equity": 460, "withdrawn": 200})
    _w(d / "CERT_BOOK_LIVE.json", {"fusion": {"gold_asia": 0.0075}})
    f = rs.build(NOW, desk=desk, root=root)["accounts"]["fusion"]
    mx = f["floors"]["max_loss_deadman"]
    assert mx["floor"] == 315.0 and mx["hysteresis_applied"] is True
    assert mx["withdrawn_offset"] == 200.0
    assert mx["distance"] == round(266.01 + 200 - 315.0, 2)
    assert f["floors"]["daily_loss"]["floor"] == 243.0
    assert f["floors"]["weekly"]["status"] == "UNMEASURED"
    assert f["open_risk"]["open_risk_frac"] == 0.0
    assert f["open_risk"]["allocator_risk_frac"] == 0.0075


def test_stale_stamps_are_unmeasured(tmp_path: Path) -> None:
    desk, root = _tree(tmp_path)
    d = desk / "data"
    _w(d / "gateway_state.json", {"equity": 266.01, "last_reconcile": "2026-10-30T19:50:13+00:00",
                                  "day_start_equity": {"date": "2026-10-30", "equity": 457.74}})
    _w(d / "fusion_deadman_state.json", {"halt_codes": [], "checked_at": "2026-09-12T12:05:02Z",
                                         "readings": {"open_positions": 0}})
    f = rs.build(NOW, desk=desk, root=root)["accounts"]["fusion"]
    assert f["equity"]["status"] == "UNMEASURED" and f["equity"]["last_value"] == 266.01
    assert f["floors"]["daily_loss"]["status"] == "UNMEASURED"
    assert f["open_risk"]["status"] == "UNMEASURED"


def test_e8_and_ftmo_floors_from_owner_constants(tmp_path: Path) -> None:
    desk, root = _tree(tmp_path)
    _w(desk / "reports" / "E8_GUARD.json", {"equity": 99_000.0, "day_start": 100_000.0,
                                            "generated_at": "2026-11-04T11:00:00+00:00",
                                            "verdict": "OK"})
    _w(desk / "reports" / "FTMO_ACCOUNT_STATE.json", {
        "status": "OK", "generated_at": "2026-11-04T11:00:00+00:00", "equity": 99_666.72,
        "initial_balance": 100_000.0, "day_start_balance": 99_700.0, "open_positions": []})
    acc = rs.build(NOW, desk=desk, root=root)["accounts"]
    assert acc["e8"]["floors"]["daily_loss"]["distance"] == 99_000.0 - 97_500.0
    assert acc["e8"]["floors"]["max_loss_static"]["floor"] == 90_000.0
    assert acc["e8"]["floors"]["weekly"]["status"] == "NO_RULE"
    assert acc["ftmo"]["floors"]["daily_loss"]["floor"] == 94_700.0
    assert acc["ftmo"]["floors"]["max_loss"]["floor"] == 90_000.0
    assert acc["ftmo"]["open_risk"]["open_risk_frac"] == 0.0


def test_events_next_24h_touch_live_symbols_and_list_unclassified(tmp_path: Path) -> None:
    desk, root = _tree(tmp_path)
    _w(desk / "data" / "MINLOT_OVERRIDE.json", {"enabled": True, "sleeves": ["gold_asia"]})
    _w(root / "data" / "event_calendar.json", {
        "valid_through": "2027-12-08", "source": "fed",
        "events": [{"utc": "2026-11-04T19:00:00Z", "name": "FOMC decision", "impact": "high"},
                   {"utc": "2026-11-09T19:00:00Z", "name": "later", "impact": "high"}]})
    rows = [{"event_id": "u1", "title": "rumour", "category": "UNCLASSIFIED",
             "happened_at": "2026-11-04T15:00:00+00:00", "importance": 0.0},
            {"event_id": "old", "title": "past", "category": "central_bank_policy",
             "happened_at": "2026-11-01T15:00:00+00:00", "importance": 0.9}]
    p = desk / "data" / "macro" / "event_ledger.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    ev = rs.build(NOW, desk=desk, root=root)["events_next_24h"]
    assert ev["live_symbols"] == ["XAUUSD"]
    names = [e["name"] for e in ev["events"]]
    assert names == ["FOMC decision", "rumour"]
    unc = ev["events"][1]
    assert unc["status"] == "UNCLASSIFIED" and unc["importance"] == "UNMEASURED"


def test_main_writes_the_report(tmp_path: Path) -> None:
    out = tmp_path / "RISK_SNAPSHOT.json"
    assert rs.main(["--once", "--out", str(out)]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["report_only"] is True and set(doc["accounts"]) == {"fusion", "e8", "ftmo"}
