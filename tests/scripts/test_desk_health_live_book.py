"""DESK_HEALTH turns RED when the desk cannot trade (CRO noon pass, 2026-11-14).

sleeves.json held 0 LIVE and 26 STANDBY rows and data/GATEWAY_PAUSED had stood since 10-30, while
markout.json had not been rewritten since 11-11 -- and no finding said any of it.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "desks" / "mt5" / "scripts" / "check_desk_health.py"


@pytest.fixture
def dh() -> Any:
    spec = importlib.util.spec_from_file_location("_quant_desk_health_live_book", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._FINDINGS.clear()
    return mod


def _book(tmp: Path, statuses: list[str]) -> Path:
    p = tmp / "sleeves.json"
    p.write_text(json.dumps({"sleeves": [{"name": f"s{i}", "status": s}
                                         for i, s in enumerate(statuses)]}), "utf-8")
    return p


def _levels(dh: Any) -> list[tuple[str, str]]:
    return [(f["level"], f["message"]) for f in dh._FINDINGS]


def test_zero_live_sleeves_is_a_problem(dh, tmp_path):
    dh.check_live_book(_book(tmp_path, ["STANDBY"] * 26 + ["RETIRED"]), tmp_path / "nope")
    found = _levels(dh)
    assert ("OK", "data/GATEWAY_PAUSED is absent -- the gateway is not paused") in found
    assert any(lvl == "PROBLEM" and "0 LIVE sleeves (26 STANDBY)" in m for lvl, m in found)


def test_a_live_sleeve_is_ok(dh, tmp_path):
    dh.check_live_book(_book(tmp_path, ["LIVE", "STANDBY"]), tmp_path / "nope")
    assert all(lvl == "OK" for lvl, _ in _levels(dh))


def test_the_pause_switch_is_a_problem(dh, tmp_path):
    pause = tmp_path / "GATEWAY_PAUSED"
    pause.write_text("paused", "utf-8")
    dh.check_live_book(_book(tmp_path, ["LIVE"]), pause)
    assert any(lvl == "PROBLEM" and "GATEWAY_PAUSED is present" in m for lvl, m in _levels(dh))


def test_an_unreadable_book_is_unknown_not_empty(dh, tmp_path):
    bad = tmp_path / "sleeves.json"
    bad.write_text("{not json", "utf-8")
    dh.check_live_book(bad, tmp_path / "nope")
    assert any(lvl == "UNKNOWN" and "UNMEASURED, not empty" in m for lvl, m in _levels(dh))
    assert not any(lvl == "PROBLEM" for lvl, _ in _levels(dh))


def test_a_stale_markout_is_a_problem(dh, tmp_path, monkeypatch):
    import os
    import time
    rel = "reports/markout.json"
    assert any(a[0] == rel and a[2] <= 26.0 for a in dh.ARTIFACTS)
    monkeypatch.setattr(dh, "DESK", tmp_path)
    monkeypatch.setattr(dh, "ROOT", tmp_path)
    monkeypatch.setattr(dh, "ARTIFACTS", tuple(a for a in dh.ARTIFACTS if a[0] == rel))
    f = tmp_path / rel
    f.parent.mkdir(parents=True)
    f.write_text("{}", "utf-8")
    old = time.time() - 3 * 86400
    os.utime(f, (old, old))
    dh.check_artifacts()
    assert any(lvl == "PROBLEM" and "markout.json" in m for lvl, m in _levels(dh))
