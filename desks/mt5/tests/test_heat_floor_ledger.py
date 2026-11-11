"""heat_floor_ledger: causes per below-floor hour, UNMEASURED on missing input, breach on an
unexplained hour, atomic write."""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from research import heat_floor_ledger as hfl

NOW = datetime(2026, 11, 11, 7, 30, tzinfo=UTC)


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(hfl, "BASE", tmp_path)
    monkeypatch.setattr(hfl, "OUT", tmp_path / "reports" / "HEAT_FLOOR_LEDGER.json")
    monkeypatch.setattr(hfl, "SOURCES", {
        "fusion": tmp_path / "data" / "xacct" / "fusion_book.json",
        "e8": tmp_path / "data" / "xacct" / "e8_book.json",
        "ftmo": tmp_path / "reports" / "FTMO_ACCOUNT_STATE.json"})
    for name in ("FTMO_ALLOCATOR_ARMED", "FTMO_EXECUTOR_ARMED"):
        monkeypatch.setattr(hfl, name, tmp_path / "data" / name)
    monkeypatch.setattr(hfl, "FTMO_FOLLOWER_INTENTS",
                        tmp_path / "data" / "ftmo_follower_intents.jsonl")
    monkeypatch.setattr(hfl, "CERT_BOOK", tmp_path / "data" / "CERT_BOOK_LIVE.json")
    monkeypatch.setattr(hfl, "heat_floor", lambda: (0.20, "test"))
    (tmp_path / "data" / "xacct").mkdir(parents=True)
    (tmp_path / "reports").mkdir()
    return tmp_path


def _put(path: Path, doc: dict) -> None:
    path.write_text(json.dumps(doc), "utf-8")


def _arm(desk: Path) -> None:
    for name in ("FTMO_ALLOCATOR_ARMED", "FTMO_EXECUTOR_ARMED"):
        (desk / "data" / name).write_text("", "utf-8")


def test_missing_input_is_unmeasured_never_zero(desk: Path) -> None:
    doc = hfl.run(NOW)
    for acct in ("fusion", "e8", "ftmo"):
        day = doc["today"][acct]
        assert day["hours_below_floor"] == hfl.UNMEASURED
        assert day["time_weighted_heat"] == hfl.UNMEASURED
        assert day["idle_capital_usd_hours"] == hfl.UNMEASURED
    _put(hfl.SOURCES["ftmo"], {"equity": 1000.0, "open_positions": 2})
    assert hfl.sample("ftmo", hfl.SOURCES["ftmo"])["verdict"] == hfl.UNMEASURED


def test_ftmo_unarmed_cause(desk: Path) -> None:
    _put(hfl.SOURCES["ftmo"], {"equity": 100000.0, "open_positions": 0})
    day = hfl.run(NOW)["today"]["ftmo"]
    assert day["by_cause"] == {"ftmo_unarmed": 1}
    assert day["idle_capital_usd_hours"] == pytest.approx(20000.0)
    assert not day["breach"]


def test_gold_only_pin_cause(desk: Path) -> None:
    _put(hfl.SOURCES["fusion"], {"equity": 1000.0, "open_risk_usd": 50.0})
    day = hfl.run(NOW)["today"]["fusion"]
    assert day["by_cause"] == {"gold_only_pin (#954)": 1}
    assert day["time_weighted_heat"] == pytest.approx(0.05)


def test_follow_late_limit_cause(desk: Path) -> None:
    _arm(desk)
    _put(hfl.SOURCES["ftmo"], {"equity": 1000.0, "open_positions": 0})
    hfl.FTMO_FOLLOWER_INTENTS.write_text(json.dumps(
        {"at": "2026-11-11T07:10:00+00:00", "status": "RAIL_BLOCKED",
         "rail": "ftmo_follower", "reason": "follow_late_limit"}) + "\n", "utf-8")
    assert hfl.run(NOW)["today"]["ftmo"]["by_cause"] == {"follow_late_limit (#959)": 1}


def test_cert_book_zero_cause(desk: Path) -> None:
    _arm(desk)
    _put(hfl.SOURCES["ftmo"], {"equity": 1000.0, "open_positions": 0})
    _put(hfl.CERT_BOOK, {"ftmo": {"some_sleeve": 0.0}})
    assert hfl.run(NOW)["today"]["ftmo"]["by_cause"] == {"cert_book_zero": 1}


def test_unexplained_hour_is_a_breach(desk: Path) -> None:
    _arm(desk)
    _put(hfl.SOURCES["ftmo"], {"equity": 1000.0, "open_positions": 0})
    doc = hfl.run(NOW)
    assert doc["today"]["ftmo"]["by_cause"] == {hfl.UNEXPLAINED: 1}
    assert doc["today"]["ftmo"]["breach"] is True
    assert doc["breaches"] == ["ftmo:2026-11-11T07:00Z"]
    assert doc["missed_growth"] and doc["missed_growth"][0]["rail"] == "heat_floor:ftmo"


def test_above_floor_has_no_cause(desk: Path) -> None:
    _put(hfl.SOURCES["ftmo"], {"equity": 1000.0, "open_risk_usd": 250.0})
    day = hfl.run(NOW)["today"]["ftmo"]
    assert day["hours_below_floor"] == 0 and day["by_cause"] == {}


def test_atomic_write_and_report_only(desk: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []
    real = os.replace
    monkeypatch.setattr(hfl.os, "replace",
                        lambda a, b: (calls.append((str(a), str(b))), real(a, b))[1])
    hfl.run(NOW)
    assert calls == [(str(hfl.OUT) + ".tmp", str(hfl.OUT))]
    doc = json.loads(hfl.OUT.read_text("utf-8"))
    assert doc["report_only"] is True and doc["consumer"] is None
    assert "missed-growth" in doc["intended_consumer"]
    assert not Path(str(hfl.OUT) + ".tmp").exists()
    # A second pass in the same hour replaces that hour's sample instead of adding one.
    hfl.run(NOW)
    assert json.loads(hfl.OUT.read_text("utf-8"))["today"]["ftmo"]["hours_sampled"] == 1
