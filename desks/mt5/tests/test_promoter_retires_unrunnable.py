"""Rows whose certificate hygiene evicted as UNRUNNABLE leave the roster (2026-09-16).

Five `session_range_breakout` rows carried bare-cell certificates whose parameterisation was
never recorded; the gateway refused them on every pass ("names no parameterisation and the
docket holds 403 distinct ones"), one of them LIVE with heat assigned, four STANDBY waiting for a
restore that could only restore a refusal. Their re-earned parameterised twins already sat on the
roster. The promoter now reads the eviction back into the roster.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import promoter  # noqa: E402

_BARE = "external.CADJPY.session_range_breakout"
_PARAM = "external.CADJPY.session_range_breakout.rr=1.5_wb=12"


def _rows() -> list[dict]:
    return [
        {"name": "cadjpy_srb_bare", "status": "LIVE", "risk_frac": 0.0086,
         "certificate": {"cell": _BARE, "source": "UNIVERSAL_SURVIVORS"}, "params": None},
        {"name": "cadjpy_srb_param", "status": "LIVE", "risk_frac": 0.0086,
         "certificate": {"cell": _PARAM}, "params": None},
        {"name": "eurjpy_srb_bare_standby", "status": "STANDBY", "risk_frac": 0.0,
         "certificate": "external.EURJPY.session_range_breakout", "params": None},
        {"name": "explicit_params", "status": "LIVE", "risk_frac": 0.01,
         "certificate": {"cell": _BARE}, "params": {"rr": 2.0, "wait_bars": 12}},
        {"name": "already_retired", "status": "RETIRED", "certificate": {"cell": _BARE}},
    ]


def test_evicted_bare_certificates_are_retired_and_their_twins_are_not() -> None:
    promoter._DOOR_EVENTS.clear()
    rows = _rows()
    evicted = {_BARE, "external.EURJPY.session_range_breakout"}
    assert promoter.retire_unrunnable(rows, evicted) is True
    by = {r["name"]: r for r in rows}
    assert by["cadjpy_srb_bare"]["status"] == "RETIRED"
    assert by["cadjpy_srb_bare"]["risk_frac"] == 0.0
    assert "UNRUNNABLE" in by["cadjpy_srb_bare"]["retire_reason"]
    assert by["eurjpy_srb_bare_standby"]["status"] == "RETIRED"
    # The parameterised twin, the row with explicit params and the retired row are untouched.
    assert by["cadjpy_srb_param"]["status"] == "LIVE"
    assert by["explicit_params"]["status"] == "LIVE"
    assert by["already_retired"]["status"] == "RETIRED"
    assert "retire_reason" not in by["already_retired"]
    doors = [e for e in promoter._DOOR_EVENTS if e["door"] == "RETIRED"]
    assert {e["name"] for e in doors} == {"cadjpy_srb_bare", "eurjpy_srb_bare_standby"}
    assert {e["from_status"] for e in doors} == {"LIVE", "STANDBY"}
    promoter._DOOR_EVENTS.clear()


def test_no_eviction_file_retires_nothing(tmp_path: Path) -> None:
    rows = _rows()
    assert promoter.retire_unrunnable(rows, set()) is False
    assert promoter.evicted_certificate_keys(tmp_path / "missing.json") == set()
    f = tmp_path / "ev.json"
    f.write_text(json.dumps({"survivors": {_BARE: {"cell": "x"}}}), "utf-8")
    assert promoter.evicted_certificate_keys(f) == {_BARE}
    assert all(r["status"] != "RETIRED" or r["name"] == "already_retired" for r in rows)
