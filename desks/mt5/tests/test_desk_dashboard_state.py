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
    # THE STORE'S `swept_at` IS NEVER A BIRTH. These survivors are written in the LIST shape and
    # carry no `gated_at` of their own, so each gets a FLOOR -- "no younger than when this host
    # first saw it" -- and the block says so by name rather than claiming an age it cannot date.
    age = canon["certificate_age"]
    assert age["status"] == "MEASURED"
    assert age["value"]["n_dated"] == 2 and age["value"]["n_undated"] == 0
    assert sorted(age["floored"]) == sorted(rows), "a floored certificate must be named"
    assert all(r["age_basis"] == "FLOOR" for r in canon["rows"])
    assert all(r["born_at"] for r in canon["rows"])
    assert "no earlier evidence" in age["why"]


def test_a_certificate_is_dated_from_its_own_gated_at(desk: Path) -> None:
    """THE BIRTH WAS ALWAYS IN THE STORE. Every survivor row carries `gated_at` -- the instant it
    passed the tenth gate -- and the dashboard used to read `days`, the BACKTEST span, instead."""
    _write(desk / "desks/mt5/reports/UNIVERSAL_SURVIVORS.json",
           {"n": 1, "swept_at": "2026-09-23T18:00:00+00:00", "survivors": {
               "external.CADJPY.session_range_breakout": {
                   "cell": "CADJPY.session_range_breakout", "sym": "CADJPY", "days": 658,
                   "gated_at": "2026-08-26T01:44:33.109395+00:00",
                   "restored_at": "2026-09-23T09:04:07+00:00"}}})
    _write(desk / "desks/mt5/data/sleeve_registry.json", {"sleeves": {}})
    _write(desk / "desks/mt5/data/sleeves.json", {"sleeves": []})
    canon = DDS._canon(time.time() + 20)
    row = canon["rows"][0]
    assert row["age_basis"] == "GATED_AT"
    assert row["born_at"] == "2026-08-26T01:44:33.109395+00:00", (
        "a restored certificate must keep its ORIGINAL birth; `restored_at` three weeks later "
        "would make it younger, and an age that can fall is not an age")
    assert row["age_s"] > 20 * 86400
    assert canon["certificate_age"]["value"]["n_dated"] == 1
    assert canon["certificate_age"]["floored"] == []


def test_a_birth_only_ever_moves_earlier(desk: Path) -> None:
    """The ledger is a ratchet on truth: older evidence wins, a re-stamp never does."""
    _write(desk / "desks/mt5/reports/CERTIFICATE_BIRTHS.json",
           {"certificates": {"k": {"born_at": "2026-07-01T00:00:00+00:00",
                                   "basis": "prior ledger row",
                                   "first_seen_here": "2026-07-01T00:00:00+00:00"}}})
    got = DDS._births([("k", {"gated_at": "2026-09-01T00:00:00+00:00", "cell": "c"})], DDS._now())
    assert got["certificates"]["k"]["born_at"] == "2026-07-01T00:00:00+00:00", (
        "a later gated_at must never overwrite an earlier recorded birth")
    older = DDS._births([("k", {"gated_at": "2026-05-01T00:00:00+00:00", "cell": "c"})],
                        DDS._now())
    assert older["certificates"]["k"]["born_at"] == "2026-05-01T00:00:00+00:00", (
        "older evidence must move the birth earlier")


def test_a_measured_emptiness_is_not_an_unmeasured_row(desk: Path) -> None:
    """THE WORD UNMEASURED HAS TO MEAN ONE THING. A gateway that reconciled and holds nothing is
    a FLAT BOOK -- a real answer -- and must never sit in the same list as a hole."""
    _write(desk / "desks/mt5/data/gateway_state.json",
           {"equity": 771.62, "armed": True, "position": None})
    live = DDS._live(time.time() + 20)
    assert live["open_position"]["status"] == "MEASURED_EMPTY"
    assert "FLAT" in live["open_position"]["why"]
    holes: list[dict[str, Any]] = []
    empties: list[dict[str, Any]] = []
    DDS._collect_unmeasured({"live": live}, "", holes, empties)
    assert any(r["where"] == "live.open_position" for r in empties)
    assert not any(r["where"] == "live.open_position" for r in holes), (
        "a measured emptiness on the worklist is how the word UNMEASURED stops working")
    # ...and a gateway that never reported a book is still a hole, which is the whole point.
    _write(desk / "desks/mt5/data/gateway_state.json", {"equity": 771.62, "armed": True})
    assert DDS._live(time.time() + 20)["open_position"]["status"] == "UNMEASURED"


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
