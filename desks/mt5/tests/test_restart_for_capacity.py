"""The capacity restart's safety properties, pinned.

This script stops the terminal on the box that trades. Every guard that stops it doing so at the
wrong moment is tested here, because the failure mode is a live trading box restarted into a
window it should have been allowed to take.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import restart_for_capacity as rfc  # noqa: E402


def _desk(tmp_path, *, e8_positions=False, open_positions=0, allows=True):
    (tmp_path / "reports").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    wins = {"asia": {"position_id": 123 if e8_positions else None}}
    (tmp_path / "reports" / "E8_GOLD.json").write_text(json.dumps(
        {"guard": "stood down: no new placements this pass",
         "state": {"date": "2026-09-25", "windows": wins}}), "utf-8")
    (tmp_path / "data" / "account_state.json").write_text(json.dumps(
        {"open_positions": open_positions, "equity": 771.47}), "utf-8")
    (tmp_path / "data" / "release_identity.json").write_text(json.dumps(
        {"allows_new_risk": allows, "verdict": "OK" if allows else "REFUSED",
         "age_h": 0.1, "reason": "x"}), "utf-8")
    return tmp_path


# --------------------------------------------------------------- the window guard
@pytest.mark.parametrize("hour", [0, 1, 3, 4, 5])
def test_it_refuses_before_the_windows_have_had_their_chance(tmp_path, monkeypatch, hour):
    """The desk had not placed since 05:56Z the previous day. Taking gold_asia's window away to
    save a reboot is the wrong trade in every direction."""
    monkeypatch.setattr(rfc, "DESK", _desk(tmp_path))
    out = rfc.preconditions(datetime(2026, 9, 25, hour, 30, tzinfo=UTC))
    assert out["ok"] is False
    assert not next(c for c in out["checks"] if c["check"] == "windows_had_their_chance")["ok"]


def test_it_allows_after_the_freeze_and_both_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(rfc, "DESK", _desk(tmp_path))
    out = rfc.preconditions(datetime(2026, 9, 25, 6, 30, tzinfo=UTC))
    assert out["ok"] is True, [c for c in out["checks"] if not c["ok"]]


# --------------------------------------------------------------- flatness and the seal
def test_e8_flatness_reads_positions_not_the_guard(tmp_path, monkeypatch):
    """'Stood down' is not 'flat'. The guard says no NEW placements; the positions say what is
    actually at risk across a restart."""
    monkeypatch.setattr(rfc, "DESK", _desk(tmp_path, e8_positions=True))
    out = rfc.preconditions(datetime(2026, 9, 25, 6, 30, tzinfo=UTC))
    e8 = next(c for c in out["checks"] if c["check"] == "e8_flat")
    assert e8["ok"] is False and "asia" in e8["detail"]
    assert out["ok"] is False


def test_it_refuses_to_restart_into_an_already_broken_state(tmp_path, monkeypatch):
    """allows_new_risk False going in means the box is restarted into a halt nobody has cleared."""
    monkeypatch.setattr(rfc, "DESK", _desk(tmp_path, allows=False))
    out = rfc.preconditions(datetime(2026, 9, 25, 6, 30, tzinfo=UTC))
    assert not next(c for c in out["checks"] if c["check"] == "allows_new_risk")["ok"]
    assert out["ok"] is False


def test_an_open_mt5_position_refuses(tmp_path, monkeypatch):
    monkeypatch.setattr(rfc, "DESK", _desk(tmp_path, open_positions=2))
    out = rfc.preconditions(datetime(2026, 9, 25, 6, 30, tzinfo=UTC))
    assert out["ok"] is False


def test_an_unreadable_artifact_refuses_rather_than_passing(tmp_path, monkeypatch):
    d = _desk(tmp_path)
    (d / "data" / "account_state.json").write_text("{not json", "utf-8")
    monkeypatch.setattr(rfc, "DESK", d)
    out = rfc.preconditions(datetime(2026, 9, 25, 6, 30, tzinfo=UTC))
    flat = next(c for c in out["checks"] if c["check"] == "mt5_flat")
    assert flat["ok"] is False and "UNMEASURED" in flat["detail"]


# --------------------------------------------------------------- the ini edit
def test_maxbars_is_rewritten_in_place_preserving_utf16(tmp_path, monkeypatch):
    """common.ini is UTF-16LE with a BOM. Writing UTF-8 makes the terminal ignore the file."""
    ini = tmp_path / "common.ini"
    ini.write_bytes("[Charts]\nMaxBars=100000\nPrintColor=0\n".encode("utf-16"))
    monkeypatch.setattr(rfc, "COMMON_INI", ini)
    out = rfc.set_maxbars(2_000_000)
    assert out["ok"] and out["from"] == 100_000 and out["to"] == 2_000_000
    raw = ini.read_bytes()
    assert raw[:2] == b"\xff\xfe", "the BOM must survive"
    assert "MaxBars=2000000" in raw.decode("utf-16")
    assert "PrintColor=0" in raw.decode("utf-16"), "the rest of the file is untouched"
    assert Path(out["backup"]).exists()


def test_a_missing_maxbars_key_refuses_rather_than_guessing_the_layout(tmp_path, monkeypatch):
    ini = tmp_path / "common.ini"
    ini.write_bytes("[Charts]\nPrintColor=0\n".encode("utf-16"))
    monkeypatch.setattr(rfc, "COMMON_INI", ini)
    out = rfc.set_maxbars(2_000_000)
    assert out["ok"] is False and "refusing" in out["why"].lower()


def test_the_chosen_maxbars_is_deliberate_and_never_unlimited():
    """Unlimited would let one symbol's M1 take unbounded commit and put the judge back at the
    ceiling this restart exists to clear. 2,000,000 x 60 bytes x 248 M1 charts = 29.8 GB."""
    assert rfc.MAXBARS == 2_000_000
    ceiling_gb = 248 * rfc.MAXBARS * 60 / 1024 ** 3
    assert ceiling_gb < 40, "the M1 ceiling must stay well inside 96 GB of RAM"
    src = Path(rfc.__file__).read_text(encoding="utf-8")
    assert "Unlimited" in src, "the refusal of Unlimited is stated in the file"


def test_the_pagefile_target_is_the_authorised_one():
    assert rfc.PAGEFILE_VALUE == r"C:\pagefile.sys 262144 393216"


def test_staging_stops_the_terminal_before_it_edits_the_ini():
    """MetaTrader rewrites common.ini at shutdown, so an edit made while it is up is discarded.

    ASSERT THE ORDER, NOT THE PROSE. Three earlier tests in this session failed on a docstring
    phrase that wrapped across a line; the sentence is not the property, the sequence is.
    """
    src = Path(rfc.__file__).read_text(encoding="utf-8")
    body = src.split("if a.stage and", 1)[1]
    assert body.index("stop_terminal") < body.index("set_maxbars"), (
        "common.ini must not be edited until the terminal is down")
    # and the edit is gated on the stop actually having worked
    assert 'if doc["stop_terminal"]["ok"]:' in body
    # the restart is gated on staging having succeeded
    assert 'if a.restart and doc["staged"]' in src
