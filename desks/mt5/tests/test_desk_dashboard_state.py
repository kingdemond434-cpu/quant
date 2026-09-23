"""THE DASHBOARD'S JOIN, ON A TEMPORARY DESK: an absent artifact is MISSING with its reason and
never a zero, a stale artifact is STALE, a ratio with one observation is UNMEASURED, and a
certificate is joined to its clock through the canonical identity rather than by name."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK / "research"), str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import desk_dashboard_state as DDS  # noqa: E402


@pytest.fixture()
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty repo shape. Nothing here is a tracked file, and the organ writes only inside it."""
    (tmp_path / "desks" / "mt5" / "reports").mkdir(parents=True)
    (tmp_path / "desks" / "mt5" / "data").mkdir(parents=True)
    (tmp_path / "web").mkdir()
    monkeypatch.setattr(DDS, "ROOT", tmp_path)
    monkeypatch.setattr(DDS, "DESK", tmp_path / "desks" / "mt5")
    monkeypatch.setattr(DDS, "OUT", tmp_path / "desks" / "mt5" / "reports" /
                        "DESK_DASHBOARD_STATE.json")
    monkeypatch.setattr(DDS, "WEB", tmp_path / "web" / "desk_state.json")
    return tmp_path


def _write(path: Path, doc: Any, age_s: float = 0.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")
    if age_s:
        stamp = time.time() - age_s
        os.utime(path, (stamp, stamp))


def test_absent_artifacts_are_missing_with_a_reason_never_zero(desk: Path) -> None:
    doc = DDS.build(budget_s=20.0)
    assert doc["status"] == "PARTIAL"
    head = doc["headline"]
    for key in ("equity", "certificates", "defects_open", "clocks_accruing"):
        cell = head[key]
        assert cell["value"] is None, f"{key} invented a value out of an absent artifact"
        assert cell["status"] in ("MISSING", "UNMEASURED", "UNREADABLE")
        assert cell["why"], f"{key} reported an absence without a reason"
    assert doc["n_unmeasured"] > 0
    assert all(row["why"] for row in doc["unmeasured"])


def test_stale_source_renders_stale_and_says_why(desk: Path) -> None:
    _write(desk / "desks/mt5/data/gateway_state.json", {"equity": 771.62, "armed": True},
           age_s=6 * 3600)
    live = DDS._live(time.time() + 20)
    assert live["equity"]["status"] == "STALE"
    assert "past its" in live["equity"]["why"]
    assert live["equity"]["value"] == 771.62          # stale is shown, flagged, never hidden


def test_certificate_joins_its_clock_on_the_canonical_identity(desk: Path) -> None:
    _write(desk / "desks/mt5/reports/UNIVERSAL_SURVIVORS.json",
           {"n": 2, "survivors": ["CADJPY.asia", "XAUUSD.session_range_breakout.london"],
            "swept_at": "2026-09-23T18:00:00+00:00"})
    _write(desk / "desks/mt5/data/sleeve_registry.json",
           {"sleeves": {"CADJPY.asia": {
               "identity": {"symbol": "CADJPY", "family": "session_range_breakout",
                            "selector": "asia", "direction": "LONG", "timeframe": "H1"},
               "status": "LIVE", "forward_start": "2026-09-01T00:00:00+00:00"}}})
    _write(desk / "desks/mt5/data/sleeves.json", {"sleeves": []})
    canon = DDS._canon(time.time() + 20)
    rows = {r["certificate"]: r for r in canon["rows"]}
    assert rows["CADJPY.asia"]["clocks"] == ["CADJPY.asia"]
    assert rows["CADJPY.asia"]["clock_age"] != "UNMEASURED"
    orphan = rows["XAUUSD.session_range_breakout.london"]
    assert orphan["clocks"] == []
    assert "sleeve_registry" in orphan["clock_why"]
    assert canon["certificate_age"]["status"] == "UNMEASURED"   # never faked from swept_at


def test_one_observation_has_no_sharpe(desk: Path) -> None:
    assert DDS._stats([0.7])["sharpe"] is None
    assert "n=1" in DDS._stats([0.7])["why"]
    assert DDS._stats([])["sharpe"] is None
    two = DDS._stats([1.0, -1.0])
    assert two["sharpe"] == 0.0 and two["n"] == 2       # a real zero, measured, is allowed


def test_publish_extends_the_existing_payload_rather_than_replacing_it(desk: Path) -> None:
    _write(desk / "web/desk_state.json", {"account": {"equity": 1.0}, "clocks": {"n": 3}})
    doc = DDS.run(budget_s=20.0, write=True)
    payload = json.loads((desk / "web/desk_state.json").read_text("utf-8"))
    assert payload["account"] == {"equity": 1.0}        # the publisher's own blocks survive
    assert payload["dashboard"]["source"] == "desk_dashboard_state"
    assert payload["dashboard"]["cadence_s"] == DDS.CADENCE_S
    assert json.loads((desk / "desks/mt5/reports/DESK_DASHBOARD_STATE.json")
                      .read_text("utf-8"))["host"] == doc["host"]


def test_calendar_rows_say_whether_the_book_is_in_the_window(desk: Path) -> None:
    ahead = "2099-01-01T00:00:00+00:00"
    _write(desk / "desks/mt5/data/forced_flow_calendar.json",
           {"n_events": 2, "events": [
               {"kind": "central_bank", "name": "ecb", "window_start_utc": ahead,
                "window_end_utc": ahead, "instruments": ["EURUSD", "XAUUSD"]},
               {"kind": "fixing", "name": "tokyo", "window_start_utc": ahead,
                "window_end_utc": ahead, "instruments": ["AUDJPY"]}]})
    _write(desk / "desks/mt5/data/sleeves.json",
           {"sleeves": [{"name": "gold_asia", "symbol": "XAUUSD", "status": "LIVE",
                         "family": "session_range_breakout", "session": "asia"}]})
    macro = DDS._macro(time.time() + 20)
    rows = {r["name"]: r for r in macro["calendar"]["next"]}
    assert rows["ecb"]["acted"] is True and "XAUUSD" in rows["ecb"]["desk"]
    assert rows["tokyo"]["acted"] is False
    assert "NO LIVE SLEEVE" in rows["tokyo"]["desk"]
    assert macro["surprise"]["status"]["status"] in ("MISSING", "UNMEASURED")
