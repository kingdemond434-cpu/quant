"""The hourly cadence must be OBSERVABLE, because a cadence nobody can see cannot be enforced.

THE STANDING BAR (principal, 2026-09-08): the miners, the backtests, the gauntlet and
certification run EVERY HOUR or the desk is a failure.

THE FIELD THAT LOOKED LIKE IT REPORTED THAT WAS WATCHING A DIFFERENT ORGAN.
`scripts/data_health.py` computes `organs.last_cycle_success_h` from
`data/cro_ai_logs/2026*_*.log` -- the CRO-AI lane. `hourly_cycle` writes
`desks/mt5/data/sync_marker.json`. They have never been the same thing, and reading the first as
the MT5 cadence reports "the hourly cycle has never succeeded" about a cycle it does not watch.
That is this desk's oldest recurring failure shape: a monitor pointed at the wrong organ,
answering confidently about something it never measured.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_spec = importlib.util.spec_from_file_location("bz", _ROOT / "scripts" / "build_zentech_state.py")
bz = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bz)

CHAIN = ("mine", "merge_docket", "backtest", "external_gauntlet", "recertify_canon",
         "enrol_clocks", "pf_allocator")


def _marker(tmp_path, monkeypatch, **legs):
    doc = {"last_cycle": datetime.now(UTC).isoformat(), **legs}
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "sync_marker.json").write_text(json.dumps(doc), "utf-8")
    monkeypatch.setattr(bz, "DESK", tmp_path)
    return bz._cycle_cadence(datetime.now(UTC))


def test_a_healthy_pass_reports_OK_with_every_conversion_leg(tmp_path, monkeypatch) -> None:
    out = _marker(tmp_path, monkeypatch, **{k: {"exit_code": 0} for k in CHAIN})
    assert out["status"] == "OK"
    assert out["failed_legs"] == [] and out["absent_legs"] == []
    assert set(out["conversion_chain"]) == set(CHAIN)


def test_a_failed_gauntlet_is_BROKEN_even_when_everything_else_passed() -> None:
    """"The cycle ran" is not the claim that matters. A pass where the gauntlet threw and every
    other leg succeeded still mints no certificates, and an aggregate would show it green."""
    legs = {k: {"exit_code": 0} for k in CHAIN}
    legs["external_gauntlet"] = {"exit_code": 1, "error": "MemoryError"}
    import tempfile

    import pytest as _pt
    with tempfile.TemporaryDirectory() as d:
        mp = _pt.MonkeyPatch()
        out = _marker(Path(d), mp, **legs)
        mp.undo()
    assert out["status"] == "BROKEN"
    assert out["failed_legs"] == ["external_gauntlet"]
    assert "MemoryError" in out["conversion_chain"]["external_gauntlet"]["error"]


def test_a_leg_missing_from_the_roster_is_ABSENT_not_OK(tmp_path, monkeypatch) -> None:
    """A box running an old checkout has no `external_gauntlet` leg at all. That must not read as
    a pass -- it is the difference between 'it ran and failed' and 'it was never scheduled'."""
    out = _marker(tmp_path, monkeypatch, mine={"exit_code": 0})
    assert out["status"] == "INCOMPLETE"
    assert "external_gauntlet" in out["absent_legs"]
    assert out["conversion_chain"]["external_gauntlet"]["status"] == "ABSENT"


def test_a_stale_cycle_is_STALE_whatever_its_legs_said(tmp_path, monkeypatch) -> None:
    doc = {"last_cycle": (datetime.now(UTC) - timedelta(hours=9)).isoformat(),
           **{k: {"exit_code": 0} for k in CHAIN}}
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "sync_marker.json").write_text(json.dumps(doc), "utf-8")
    monkeypatch.setattr(bz, "DESK", tmp_path)
    out = bz._cycle_cadence(datetime.now(UTC))
    assert out["status"] == "STALE"
    assert out["age_h"] > 2.0


def test_a_pass_twenty_minutes_late_is_not_an_alarm(tmp_path, monkeypatch) -> None:
    """A pass that starts at :55 and takes twenty minutes is not a missed hour, and alarming on
    it would train the reader to ignore this field."""
    doc = {"last_cycle": (datetime.now(UTC) - timedelta(minutes=80)).isoformat(),
           **{k: {"exit_code": 0} for k in CHAIN}}
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "sync_marker.json").write_text(json.dumps(doc), "utf-8")
    monkeypatch.setattr(bz, "DESK", tmp_path)
    assert bz._cycle_cadence(datetime.now(UTC))["status"] == "OK"


def test_no_marker_is_UNMEASURED_and_names_the_organ_it_is_not(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(bz, "DESK", tmp_path)
    out = bz._cycle_cadence(datetime.now(UTC))
    assert out["status"] == "UNMEASURED"
    assert "cro_ai_logs" in out["why"]


def test_the_block_disclaims_the_field_that_is_easy_to_confuse_it_with(tmp_path, monkeypatch):
    out = _marker(tmp_path, monkeypatch, **{k: {"exit_code": 0} for k in CHAIN})
    assert "cro_ai_logs" in out["note"]
    assert "DIFFERENT organ" in out["note"]


def test_the_chain_is_the_one_that_mints_certificates() -> None:
    """These six legs are what turn a docket row into a certificate on a forward clock. If the
    hourly cycle stops recording one of them, this test is what says so."""
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    for leg in ("merge_docket", "backtest", "external_gauntlet", "recertify_canon",
                "enrol_clocks", "pf_allocator"):
        assert f'"{leg}":' in src, f"{leg} is no longer written to sync_marker.json"
