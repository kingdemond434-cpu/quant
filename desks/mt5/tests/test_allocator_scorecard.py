"""ALLOCATOR_SCORECARD (zuck 2026-11-24): four measures per account, weakest named, idle proven
sleeves emitted, absent artifacts UNMEASURED."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK.parent.parent), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

import allocator_scorecard as sc  # noqa: E402

NOW = datetime(2026, 11, 24, 18, 30, tzinfo=UTC)


def _w(d: Path, name: str, doc: object) -> None:
    (d / name).write_text(json.dumps(doc), encoding="utf-8")


def _world(tmp: Path) -> tuple[Path, Path]:
    rep, data = tmp / "reports", tmp / "data"
    rep.mkdir()
    data.mkdir()
    _w(rep, "FILL_PROVEN.json", {"schema": "fill-proven/1",
                                 "generated_at": (NOW - timedelta(hours=1)).isoformat(),
                                 "sleeves": [{"sleeve": "AUDCAD_carry_asia", "n_out": 20,
                                              "adjR_out": 0.4},
                                             {"sleeve": "EURUSD_srb_london", "n_out": 30,
                                              "adjR_out": 0.2}]})
    _w(rep, "pf_allocation.json", {"book": {"AUDCAD_carry_asia": 0.05},
                                   "heat": {"total": 0.24, "resolved": 0.25}})
    _w(rep, "allocator_attribution.json", {
        "terms": {"edge": {"value": -0.001}, "correlation": {"value": 0.0004},
                  "execution": {"value": -0.0002}, "regime": {"value": "UNMEASURED"}},
        "dlogw_per_day": {"mean": 0.0007}})
    _w(rep, "E8_BOOK.json", {"risk_frac": 0.0015, "sleeves": [
        {"key": "gold_asia", "symbol": "XAUUSD", "family": "gold", "selector": "asia"}]})
    _w(rep, "E8_GUARD.json", {"equity": 100000.0, "room_to_daily_floor": 2000.0})
    _w(rep, "FTMO_ALLOCATOR.json", {"executable": {"EURUSD_srb_london": 0.004}})
    _w(rep, "FTMO_ACCOUNT_STATE.json", {"equity": 100000.0, "initial_balance": 100000.0,
                                        "day_start_balance": 100000.0})
    t = (NOW - timedelta(days=2)).isoformat()
    (data / "live_ledger_prop.jsonl").write_text(
        "\n".join(json.dumps({"book": "ftmo", "r_multiple": r, "exit_time": t})
                  for r in (1.0, -1.0, 2.0)) + "\n", encoding="utf-8")
    return rep, data


def test_every_account_scored_on_all_four_measures(tmp_path):
    rep, data = _world(tmp_path)
    doc = sc.build(NOW, rep, data)
    assert set(doc["accounts"]) == {"fusion", "e8", "ftmo"}
    for a in doc["accounts"].values():
        assert all(a[m]["status"] in ("OK", "WEAK", "UNMET", "UNMEASURED") for m in sc.MEASURES)
        assert a["weakest"] in sc.MEASURES


def test_idle_proven_sleeves_are_emitted_per_account(tmp_path):
    rep, data = _world(tmp_path)
    doc = sc.build(NOW, rep, data)
    idle = {(e["account"], e["sleeve"]) for e in doc["events"]}
    assert idle == {("fusion", "EURUSD_srb_london"), ("e8", "AUDCAD_carry_asia"),
                    ("e8", "EURUSD_srb_london"), ("ftmo", "AUDCAD_carry_asia")}
    assert all(e["kind"] == "IDLE_PROVEN_SLEEVE" for e in doc["events"])
    assert doc["accounts"]["e8"]["weakest"] == "idle_proven"


def test_fusion_growth_and_heat(tmp_path):
    rep, data = _world(tmp_path)
    f = sc.build(NOW, rep, data)["accounts"]["fusion"]
    assert f["growth_vs_kelly"]["status"] == "WEAK"
    assert f["risk_utilisation"]["status"] == "OK"
    _w(rep, "pf_allocation.json", {"book": {}, "heat": {"total": 0.1, "resolved": 0.25}})
    f = sc.build(NOW, rep, data)["accounts"]["fusion"]
    assert f["risk_utilisation"]["status"] == "UNMET"


def test_prop_utilisation_against_the_daily_room(tmp_path):
    rep, data = _world(tmp_path)
    doc = sc.build(NOW, rep, data)
    e8 = doc["accounts"]["e8"]["risk_utilisation"]
    assert e8["room_daily_frac"] == 0.02 and e8["status"] == "WEAK"
    ft = doc["accounts"]["ftmo"]
    assert ft["risk_utilisation"]["room_daily_frac"] == 0.05
    assert ft["growth_vs_kelly"]["n"] == 3 and ft["growth_vs_kelly"]["status"] == "UNMEASURED"


def test_absent_artifacts_are_unmeasured_never_fine(tmp_path):
    rep, data = tmp_path / "r", tmp_path / "d"
    rep.mkdir()
    data.mkdir()
    doc = sc.build(NOW, rep, data)
    for a in doc["accounts"].values():
        assert all(a[m]["status"] == "UNMEASURED" for m in sc.MEASURES)
        assert a["weakest"] == "growth_vs_kelly"
    assert doc["events"] == []


def test_a_stale_fill_proven_measures_nothing(tmp_path):
    rep, data = _world(tmp_path)
    _w(rep, "FILL_PROVEN.json", {"schema": "fill-proven/1",
                                 "generated_at": (NOW - timedelta(hours=5)).isoformat(),
                                 "sleeves": [{"sleeve": "X", "n_out": 20, "adjR_out": 1.0}]})
    doc = sc.build(NOW, rep, data)
    assert doc["events"] == []
    assert doc["accounts"]["ftmo"]["idle_proven"]["status"] == "UNMEASURED"


def test_write_appends_events_and_replaces_the_report(tmp_path):
    rep, data = _world(tmp_path)
    doc = sc.build(NOW, rep, data)
    out, ev = tmp_path / "ALLOCATOR_SCORECARD.json", tmp_path / "events.jsonl"
    sc.write(doc, out, ev)
    sc.write(doc, out, ev)
    assert json.loads(out.read_text())["schema"] == sc.SCHEMA
    # events only on a change: the second identical pass appends nothing
    assert len(ev.read_text().splitlines()) == len(doc["events"])
    _w(rep, "FTMO_ALLOCATOR.json", {"executable": {"EURUSD_srb_london": 0.004,
                                                   "AUDCAD_carry_asia": 0.003}})
    sc.write(sc.build(NOW, rep, data), out, ev)
    last = json.loads(ev.read_text().splitlines()[-1])
    assert last["kind"] == "IDLE_PROVEN_CLEARED" and last["account"] == "ftmo"


def test_only_sleeves_the_venue_lists_can_be_idle(tmp_path):
    rep, data = _world(tmp_path)
    _w(data, "ftmo_registry.json", {"symbols": {"EURUSD": {}}})
    _w(rep, "E8_BOOK.json", {"risk_frac": 0.0015, "blocked_by_venue": ["AUDCAD"], "sleeves": [
        {"key": "gold_asia", "symbol": "XAUUSD", "family": "gold", "selector": "asia"}]})
    doc = sc.build(NOW, rep, data)
    idle = {(e["account"], e["sleeve"]) for e in doc["events"]}
    assert ("ftmo", "AUDCAD_carry_asia") not in idle
    assert ("e8", "AUDCAD_carry_asia") not in idle and ("e8", "EURUSD_srb_london") in idle
    assert doc["accounts"]["ftmo"]["idle_proven"]["status"] == "OK"
    assert doc["accounts"]["ftmo"]["idle_proven"]["not_allowed_by_venue"] == ["AUDCAD_carry_asia"]


def test_a_halted_fusion_book_is_not_scored_idle(tmp_path):
    rep, data = _world(tmp_path)
    _w(rep, "pf_allocation.json", {"book": {}, "heat": {"total": 0.0, "resolved": 0.0}})
    doc = sc.build(NOW, rep, data)
    assert doc["accounts"]["fusion"]["idle_proven"]["status"] == "UNMEASURED"
    assert not any(e["account"] == "fusion" for e in doc["events"])
