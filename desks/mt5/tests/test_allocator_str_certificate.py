"""One sleeve row must never kill the allocator pass (box 2026-11-24).

From 11-21 to 11-24 every allocator pass died with "AttributeError: 'str' object has no attribute
'get'" -- 440 times -- because one clock-promoted STANDBY row carried its certificate as the bare
clock key instead of the {"cell": ...} dict, and the book stood frozen on a 3-day-old reading.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK))
sys.path.insert(0, str(DESK.parents[1]))

from research import pf_allocator as pa  # noqa: E402

KEY = ("XAUUSD.cross_asset_residual.asia@M30#beta_win=240_entry_z=2.0_factor_symbols="
       "['NZDUSD', 'USDHUF']_lookback=240_side_mode=revert_ttl_bars=8")
CELL = "external.XAUUSD@M30.cross_asset_residual.abc"


def _desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rows: list, law: dict) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "reports").mkdir()
    (tmp_path / "data" / "sleeves.json").write_text(json.dumps({"sleeves": rows}), "utf-8")
    (tmp_path / "reports" / "CLOCK.json").write_text(json.dumps(law), "utf-8")
    monkeypatch.setattr(pa, "BASE", tmp_path)
    monkeypatch.setattr(pa, "CLOCK_LAW", tmp_path / "reports" / "CLOCK.json")


def test_a_bare_clock_key_certificate_no_clock_maps_is_unmeasured_not_a_crash(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [{"name": "m30_row", "status": "STANDBY", "certificate": KEY},
            {"name": "none_row", "status": "STANDBY", "certificate": None},
            {"name": "int_row", "status": "STANDBY", "certificate": 7}]
    _desk(tmp_path, monkeypatch, rows, {})
    specs, zero, unmeasured = pa._rostered_certificates({})
    assert specs == {} and zero == {}
    assert "bare clock key" in unmeasured["m30_row"]
    assert "none_row" not in unmeasured and "int_row" not in unmeasured


def test_a_bare_clock_key_maps_back_to_its_cell_through_the_clock_table(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [{"name": "m30_row", "status": "STANDBY", "certificate": KEY}]
    law = {"clocks": [{"certificate": CELL, "key": KEY, "status": "KILL"}]}
    _desk(tmp_path, monkeypatch, rows, law)
    specs, zero, unmeasured = pa._rostered_certificates({})
    # Resolved to its cell: the clock's own verdict (KILL) now applies to it by name.
    assert "m30_row" in zero and "KILL" in zero["m30_row"]
    assert unmeasured == {} and specs == {}


def test_a_dict_certificate_reads_as_before(tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [{"name": "dict_row", "status": "STANDBY",
             "certificate": {"source": "UNIVERSAL_SURVIVORS", "cell": CELL}}]
    law = {"clocks": [{"certificate": CELL, "key": KEY, "status": "BLOCKED_NO_BARS"}]}
    _desk(tmp_path, monkeypatch, rows, law)
    _, _, unmeasured = pa._rostered_certificates({})
    assert "BLOCKED" in unmeasured["dict_row"]
