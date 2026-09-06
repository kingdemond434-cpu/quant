"""A DASHBOARD SHOWING TEN-DAY-OLD NUMBERS AND ONE SHOWING LIVE NUMBERS ARE PIXEL-IDENTICAL.

Only the age distinguishes them, and the age was the one thing not on screen.

MEASURED 2026-09-06. The box's last real state push was 2026-08-26 14:50 -- 249 hours.
`monitor_mt5_shadow_sync` had detected it correctly the entire time, returning `status: FAILED,
shadow health sync stale: 896946s > configured 2700s` every thirty minutes into a systemd timer
whose non-zero exit nobody reads. `build_zentech_state` never imported that verdict, so every tile
went on rendering ten-day-old figures in the present tense while the desk was being asked whether
to put live capital behind them.

WHY `STALE` WAS NOT ENOUGH. `health.status` already had a STALE state, but it was scoped to the
account feed, which lags its writer by design and is therefore STALE most of every hour. A word
that is true most of the time carries no information when it becomes urgent (L1.37, and L1.63:
a partition that cannot fail is not a partition). Ten days had to be able to say something two
minutes could not.

These tests drive the real builder against a temp tree. A test that asserted only on the helper
would have passed throughout the outage, because the helper was never the broken part -- nothing
called it.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "_bzs_box", _ROOT / "scripts" / "build_zentech_state.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def bzs():
    return _load()


def _tree(bzs, tmp_path, monkeypatch, age: timedelta | None):
    """A desk tree whose box last reported `age` ago. `None` writes no clock at all."""
    desk = tmp_path / "desks" / "mt5"
    (desk / "reports" / "shadow").mkdir(parents=True)
    (desk / "data").mkdir(parents=True)
    if age is not None:
        stamp = (datetime.now(UTC) - age).isoformat(timespec="seconds")
        (desk / "reports" / "shadow" / "shadow_health.json").write_text(
            json.dumps({"status": "OPERATING", "updated_at": stamp}), "utf-8")
    else:
        (desk / "reports" / "shadow" / "shadow_health.json").write_text(
            json.dumps({"status": "OPERATING"}), "utf-8")
    monkeypatch.setattr(bzs, "ROOT", tmp_path)
    monkeypatch.setattr(bzs, "DESK", desk)
    return desk


@pytest.mark.parametrize(("age", "expect"), [
    (timedelta(seconds=60), "REPORTING"),
    (timedelta(minutes=44), "REPORTING"),
    (timedelta(minutes=46), "LATE"),
    (timedelta(hours=5), "LATE"),
    (timedelta(hours=7), "SILENT"),
    (timedelta(days=10), "SILENT"),
])
def test_the_box_is_graded_by_how_long_it_has_been_quiet(bzs, tmp_path, monkeypatch, age, expect):
    """Each band must be reachable. A grade that only ever returns one value is not a grade."""
    _tree(bzs, tmp_path, monkeypatch, age)
    got = bzs._box_liveness(datetime.now(UTC))
    assert got["status"] == expect, (
        f"a box quiet for {age} grades {got['status']}, expected {expect} -- "
        f"{got.get('why')}")


def test_ten_days_of_silence_reaches_the_published_payload(bzs, tmp_path, monkeypatch) -> None:
    """THE HALF THAT WAS ACTUALLY BROKEN.

    The watchdog was right for ten days. Nothing read it. So this asserts on `build()`'s output,
    not on the helper: a correct detector nobody calls is indistinguishable from no detector.
    """
    _tree(bzs, tmp_path, monkeypatch, timedelta(days=10))
    box = bzs.build()["health"]["box"]
    assert box["status"] == "SILENT"
    assert box["silent_seconds"] > 9 * 86400
    assert box["last_reported_at"].startswith("2026-08") or box["last_reported_at"], (
        "the payload must NAME when the box last spoke; a status with no timestamp cannot be "
        "checked against anything")
    assert "Do not size capital off it" in box["why"], (
        "the payload states a condition but not its consequence -- the reader has to already "
        "know what SILENT means to act on it, and the whole failure was that nobody knew")


def test_a_silent_box_is_not_reported_with_the_same_word_as_a_lagging_feed(
        bzs, tmp_path, monkeypatch) -> None:
    """STALE at two minutes is routine. STALE at ten days is not. They may not share a word."""
    desk = _tree(bzs, tmp_path, monkeypatch, timedelta(days=10))
    (desk / "data" / "account_state.json").write_text(json.dumps(
        {"equity": 743.14, "balance": 743.14, "currency": "USD",
         "updated_at": (datetime.now(UTC) - timedelta(days=10)).isoformat()}), "utf-8")
    monkeypatch.setattr(bzs, "_mt5_snapshot", lambda: {})
    health = bzs.build()["health"]
    assert health["status"] == "SILENT", (
        f"the account tile reads {health['status']} on a box that has not spoken in ten days -- "
        "the same word it shows when the feed is forty seconds behind")


def test_a_box_with_no_clock_at_all_is_unmeasured_never_healthy(bzs, tmp_path, monkeypatch):
    """ABSENCE IS NEVER A PASS (L1.28a).

    A health file with no `updated_at` is one this dashboard cannot judge. Defaulting it to fresh
    would make a dead organ that stopped writing its own timestamp read as the healthiest thing
    on the board.
    """
    _tree(bzs, tmp_path, monkeypatch, None)
    got = bzs._box_liveness(datetime.now(UTC))
    assert got["status"] == "UNMEASURED", f"a clockless box grades {got['status']}"
    assert got["silent_seconds"] is None, "an unmeasured age must not be reported as a number"


def test_one_dead_organ_is_distinguishable_from_a_dead_machine(bzs, tmp_path, monkeypatch):
    """Opposite responses, so they may not collapse into one status.

    One lane stopping is a defect in that lane. All of them stopping is the machine. The overall
    grade takes the FRESHEST clock -- so a live box is not condemned by one stale file -- and
    `per_report` keeps the individual ages so the single stale file is still visible.
    """
    desk = _tree(bzs, tmp_path, monkeypatch, timedelta(seconds=60))
    (desk / "data" / "regime_state.json").write_text(json.dumps(
        {"swept_at": (datetime.now(UTC) - timedelta(days=16)).isoformat()}), "utf-8")
    got = bzs._box_liveness(datetime.now(UTC))
    assert got["status"] == "REPORTING", (
        "one stale artifact condemned a box that is plainly alive -- the grade must take the "
        "freshest clock, or every retired lane permanently reads as an outage")
    assert got["per_report"]["regime_state.json"]["status"] == "STALE", (
        "the stale lane vanished from per_report; taking the freshest clock must not hide WHICH "
        "artifact stopped, or a real single-organ death becomes invisible")


def test_the_dashboard_tolerance_matches_the_watchdogs(bzs) -> None:
    """Two opinions on one fact, and the looser one is the one on screen.

    `monitor_mt5_shadow_sync` calls the shadow feed stale past 2700s. If this dashboard allowed
    more, the board would say REPORTING while the watchdog said FAILED, and the board is what
    gets read.
    """
    src = (_ROOT / "scripts" / "monitor_mt5_shadow_sync.py").read_text("utf-8")
    assert 'SHADOW_SYNC_MAX_AGE_SECONDS", "2700"' in src, (
        "the watchdog's threshold moved; BOX_LATE_SECONDS must move with it or the two disagree")
    assert bzs.BOX_LATE_SECONDS == 2700, (
        f"dashboard tolerates {bzs.BOX_LATE_SECONDS}s, watchdog tolerates 2700s -- the dashboard "
        "must never be the more forgiving of the two")
