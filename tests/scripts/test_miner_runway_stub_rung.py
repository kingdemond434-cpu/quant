"""A seat that fires on time and dies at birth is not `ok` (gap-fixer 2026-08-26).

`check_miner_runway` computed `last_bytes` for every seat and never read it. Its own comment
said the max ages "mirror scripts/max_audit.py ORGANS" -- and mirroring copied one of that
table's two columns: `ORGANS` carries `(glob, min_bytes_for_success, max_age_h)` and only the
age came across. So `frontier-ru` graded `ok` on a 118-byte log whose entire content is an
"attempt" line and a "start" line, `litminer` graded `ok` on a stub at 18h, and
`seats_productive` reported 7/11 while the true figure was 4/11. Arrivals fell to 24/week
against a 160/week baseline with every liveness gauge reading survivable.

`ops/run_frontier_rotation.sh` has enforced the same 1500-byte bar the whole time. The number
was never in doubt; it just was not imported.
"""
from __future__ import annotations

import os
import time

import pytest
from scripts.max_audit import ORGANS

from scripts import check_miner_runway as runway


@pytest.fixture
def seatbox(tmp_path, monkeypatch):
    """One seat with a complete runway, so only OUTPUT decides the verdict."""
    logs = tmp_path / "cro_ai_logs"
    logs.mkdir()
    (tmp_path / "ops").mkdir()
    prompt = tmp_path / "ops/frontier_ru_prompt.txt"
    prompt.write_text("mission", "utf-8")
    runner = tmp_path / "ops/run_frontier_miner.sh"
    runner.write_text("#!/bin/bash\n", "utf-8")
    monkeypatch.setattr(runway, "_ROOT", tmp_path)
    monkeypatch.setattr(runway, "_LOGDIR", logs)
    monkeypatch.setattr(runway, "_creds_present", lambda: True)
    monkeypatch.setattr(runway, "_scheduled", lambda _r: True)
    monkeypatch.setattr(runway, "_SEATS", {
        "frontier-ru": ("ops/frontier_ru_prompt.txt", "ops/run_frontier_miner.sh",
                        "frontier_ru_*.log", 36.0)})
    return logs


def _log(logs, name: str, size: int, age_h: float = 1.0):
    f = logs / name
    f.write_bytes(b"x" * size)
    old = time.time() - age_h * 3600.0
    os.utime(f, (old, old))
    return f


def test_fresh_stub_is_not_ok(seatbox):
    """THE DEFECT, verbatim: 118 bytes, one hour old, complete runway."""
    _log(seatbox, "frontier_ru_20260825T1603.log", 118, age_h=1.0)
    rep = runway.audit()
    row = rep["seats"]["frontier-ru"]
    assert row["status"] == "stub", row
    assert rep["n_bad"] == 1, "a seat dying at birth did not count as bad"


def test_real_log_is_ok(seatbox):
    """The positive control. A fence that never passes a known-good seat has not been
    validated -- only its rejections have been observed."""
    _log(seatbox, "frontier_ru_20260826T0800.log", 11919, age_h=1.0)
    rep = runway.audit()
    assert rep["seats"]["frontier-ru"]["status"] == "ok"
    assert rep["n_bad"] == 0


def test_stub_outranks_stale(seatbox):
    """A FRESH stub is the worse condition -- the seat is failing every single time it fires.
    Grading on age first reports the healthiest-looking verdict on the worst day."""
    _log(seatbox, "frontier_ru_20260824T1501.log", 131, age_h=46.7)
    assert runway.audit()["seats"]["frontier-ru"]["status"] == "stub"


def test_bar_comes_from_the_shared_table_not_a_restated_constant(seatbox):
    """The number is IMPORTED. If `max_audit.ORGANS` moves the floor, this fence moves with it
    -- which is the whole reason the original defect was possible."""
    _log(seatbox, "frontier_ru_20260826T0800.log", 900, age_h=1.0)
    assert runway.audit()["seats"]["frontier-ru"]["status"] == "stub"
    assert runway._MIN_BYTES["frontier_ru_*.log"] == ORGANS["frontier-ru"][1]


def test_unjoinable_glob_is_recorded_never_defaulted(seatbox, monkeypatch):
    """UNMEASURED is a real answer (L1.28a). A join that stops joining must not quietly fall
    back to a default floor -- that restores the blindness invisibly."""
    monkeypatch.setattr(runway, "_SEATS", {
        "frontier-ru": ("ops/frontier_ru_prompt.txt", "ops/run_frontier_miner.sh",
                        "no_such_organ_*.log", 36.0)})
    _log(seatbox, "no_such_organ_1.log", 10, age_h=1.0)
    rep = runway.audit()
    assert rep["table_drift"], "an unjoinable seat was graded silently"
    assert rep["seats"]["frontier-ru"]["min_bytes"] is None
    assert any("no longer covers every seat" in b["blocker"] for b in rep["blockers"])


def test_every_seat_joins_the_shared_table_today():
    """Live wiring check: the two tables must actually agree right now, not just be capable of
    agreeing. A drift here is the defect returning by rename."""
    globs = {g for _p, _r, g, _a in runway._SEATS.values()}
    assert globs <= set(runway._MIN_BYTES), globs - set(runway._MIN_BYTES)
