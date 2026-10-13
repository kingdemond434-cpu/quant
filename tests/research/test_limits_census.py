"""ARCH-25: every active limit is classed by what lifts it, and binding is measured or None."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "limits_census", ROOT / "desks" / "mt5" / "research" / "limits_census.py")
assert _spec and _spec.loader
lc = importlib.util.module_from_spec(_spec)
sys.modules["limits_census"] = lc
_spec.loader.exec_module(lc)


def test_every_row_has_a_known_class_and_a_three_valued_binding():
    doc = lc.build()
    assert doc["rows"]
    for r in doc["rows"]:
        assert r["class"] in lc.CLASSES
        assert r["binding"] in (True, False, None)
    assert set(doc["binding_by_class"]) == set(lc.CLASSES)
    assert all(r["binding"] is True for r in doc["binding"])


def test_every_rail_and_every_gate_is_listed():
    from libs.portfolio.rails import RAILS
    doc = lc.build()
    names = {r["name"] for r in doc["rows"]}
    assert {f"rail:{r.name}" for r in RAILS} <= names
    assert any(n.startswith("gate:") for n in names)
    assert all(r["class"] == "SCIENCE" for r in doc["rows"] if r["name"].startswith("gate:"))


def test_a_stale_box_reading_is_unmeasured_not_headroom(tmp_path, monkeypatch):
    p = tmp_path / "stall_watch.json"
    p.write_text(json.dumps({"checked_at": "2026-01-01T00:00:00.1234567Z", "free_gb": 1.0,
                             "memory": {"total_phys_mb": 8000, "free_phys_mb": 10}}), "utf-8")
    monkeypatch.setattr(lc, "STALL", (p,))
    rows = [r for r in lc.resource_rows() if "trading_box" in r["name"]]
    assert len(rows) == 1 and rows[0]["binding"] is None


def test_a_fresh_box_reading_below_its_floor_binds(tmp_path, monkeypatch):
    from datetime import UTC, datetime
    p = tmp_path / "stall_watch.json"
    p.write_text(json.dumps({"checked_at": datetime.now(tz=UTC).isoformat(), "free_gb": 1.0,
                             "memory": {"total_phys_mb": 8000, "free_phys_mb": 10}}), "utf-8")
    monkeypatch.setattr(lc, "STALL", (p,))
    rows = {r["name"]: r for r in lc.resource_rows()}
    assert rows["memory@trading_box"]["binding"] is True
    assert rows["disk@trading_box"]["binding"] is True


def test_a_retired_credential_binds_nothing():
    doc = lc.build()
    for r in doc["rows"]:
        if r["name"] == "credential:binance_testnet.json":
            assert r["binding"] is False
