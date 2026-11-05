"""Discovery organs never study an empty list while bars exist; an empty pass is written."""

from __future__ import annotations

import json
from pathlib import Path

from research import representation_discovery as rd
from research import research_panel as rp


def _uni(root: Path, *syms: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for s in syms:
        (root / f"{s}_H1.parquet").write_bytes(b"")
    return root


def _sleeves(path: Path, rows: list[tuple[str, str]]) -> Path:
    path.write_text(json.dumps({"sleeves": [{"symbol": s, "status": st} for s, st in rows]}))
    return path


def test_no_live_rows_falls_through_to_standby_then_the_core_panel(tmp_path):
    uni = _uni(tmp_path / "u", "XAUUSD", "AUDCHF", "EURUSD", "USDJPY")
    sl = _sleeves(tmp_path / "s.json", [("AUDCHF", "RETIRED"), ("XAUUSD", "STANDBY")])
    syms, origin = rp.panel_symbols(12, sleeves=sl, universe=uni)
    assert syms == ["XAUUSD", "EURUSD", "USDJPY"]
    assert origin == {"live": 0, "standby": 1, "core_panel": 2}


def test_live_rows_come_first_and_the_limit_holds(tmp_path):
    uni = _uni(tmp_path / "u", "GBPUSD", "EURUSD", "USDJPY", "XAUUSD")
    sl = _sleeves(tmp_path / "s.json", [("GBPUSD", "LIVE")])
    syms, origin = rp.panel_symbols(2, sleeves=sl, universe=uni)
    assert syms == ["GBPUSD", "EURUSD"] and origin["live"] == 1


def test_a_symbol_without_bars_is_never_in_the_panel(tmp_path):
    uni = _uni(tmp_path / "u", "EURUSD")
    sl = _sleeves(tmp_path / "s.json", [("NOBARS", "LIVE")])
    assert rp.panel_symbols(12, sleeves=sl, universe=uni)[0] == ["EURUSD"]


def test_an_unmeasured_pass_is_written_not_skipped(tmp_path, monkeypatch):
    out = tmp_path / "REPRESENTATION_DISCOVERY.json"
    monkeypatch.setattr(rd, "OUT", out)
    monkeypatch.setattr(
        rd,
        "build",
        lambda: {"at": "now", "status": "UNMEASURED", "why": "no panel symbol has H1 bars"},
    )
    assert rd.main(["--once"]) == 0
    doc = json.loads(out.read_text("utf-8"))
    assert doc["status"] == "UNMEASURED" and "why" in doc


def test_without_apply_nothing_is_written(tmp_path, monkeypatch):
    out = tmp_path / "REPRESENTATION_DISCOVERY.json"
    monkeypatch.setattr(rd, "OUT", out)
    monkeypatch.setattr(rd, "build", lambda: {"status": "UNMEASURED", "why": "x"})
    assert rd.main([]) == 0 and not out.exists()
