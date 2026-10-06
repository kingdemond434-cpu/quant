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
    # No exclusive artifact by default -- that is the real state of every frontier seat (they
    # all write the shared prospector_coverage.md), so bytes are the only honest signal there.
    monkeypatch.setattr(runway, "_organ_artifact_age_h", lambda _o: float("inf"))
    monkeypatch.setattr(runway, "_scheduled", lambda _r: True)
    monkeypatch.setattr(runway, "_SEATS", {
        "frontier-ru": ("ops/frontier_ru_prompt.txt", "ops/run_frontier_miner.sh",
                        "frontier_ru_*.log", 36.0)})
    # These cases exercise the stub rung in isolation. Supersession is a separate property with
    # its own fixture below; leaving the real map in place here would route every verdict
    # through an absent superseder.
    monkeypatch.setattr(runway, "_SUPERSEDED_BY", {})
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


def test_a_tiny_log_with_a_FRESH_artifact_is_not_a_stub(seatbox, monkeypatch):
    """THE FALSE POSITIVE THIS FENCE NEARLY SHIPPED. A claude organ writes deliverables through
    file tools, so a completely successful run can leave only a start line in the shell log --
    litminer's 686-byte log on 2026-08-25 was a real dig that minted two cards and four ledger
    rows. Grading on bytes alone called it a stub, and a fence that is wrongly red gets switched
    off, which is precisely the failure this fence exists to prevent."""
    monkeypatch.setattr(runway, "_organ_artifact_age_h", lambda _o: 14.4)
    _log(seatbox, "frontier_ru_20260825T1900.log", 686, age_h=18.1)
    rep = runway.audit()
    assert rep["seats"]["frontier-ru"]["status"] == "ok", rep["seats"]["frontier-ru"]
    assert rep["seats"]["frontier-ru"]["artifact_age_h"] == 14.4


def test_both_signals_quiet_is_still_a_stub(seatbox, monkeypatch):
    """The escape is not a blanket amnesty: an artifact that has ALSO gone past the cadence
    proves nothing, and the seat is back to producing nothing."""
    monkeypatch.setattr(runway, "_organ_artifact_age_h", lambda _o: 500.0)  # cadence is 36h
    _log(seatbox, "frontier_ru_20260825T1603.log", 118, age_h=1.0)
    assert runway.audit()["seats"]["frontier-ru"]["status"] == "stub"


def test_artifact_age_is_imported_not_reimplemented():
    """Exclusivity is the subtle half (a prospector_coverage.md that eight organs write is not
    evidence any ONE of them ran) and a second copy of it is a second thing to drift."""
    from scripts import max_audit
    assert runway._organ_artifact_age_h is max_audit._artifact_age_h


# ---------------------------------------------------------------------------------------
# SUPERSESSION. Seven regional seats stopped having any invoker on 2026-08-25 (53c55b8e
# deleted the REGIONS loop). Deleting their rows would have shrunk the denominator until the
# fence went green -- the trick LAWS §2a forbids by name -- and leaving them as permanent reds
# would have trained every reader to ignore this fence, which is how six days of cron outage
# went unescalated. They keep their rows AND inherit their obligation.
# ---------------------------------------------------------------------------------------


@pytest.fixture
def twoseats(tmp_path, monkeypatch):
    logs = tmp_path / "cro_ai_logs"
    logs.mkdir()
    (tmp_path / "ops").mkdir()
    for f in ("frontier_ru_prompt.txt", "frontier_unified_prompt.txt"):
        (tmp_path / "ops" / f).write_text("mission", "utf-8")
    (tmp_path / "ops/run_frontier_miner.sh").write_text("#!/bin/bash\n", "utf-8")
    monkeypatch.setattr(runway, "_ROOT", tmp_path)
    monkeypatch.setattr(runway, "_LOGDIR", logs)
    monkeypatch.setattr(runway, "_creds_present", lambda: True)
    monkeypatch.setattr(runway, "_scheduled", lambda _r: True)
    monkeypatch.setattr(runway, "_organ_artifact_age_h", lambda _o: float("inf"))
    monkeypatch.setattr(runway, "_SEATS", {
        "frontier-ru": ("ops/frontier_ru_prompt.txt", "ops/run_frontier_miner.sh",
                        "frontier_ru_*.log", 36.0),
        "frontier-unified": ("ops/frontier_unified_prompt.txt", "ops/run_frontier_miner.sh",
                             "frontier_unified_*.log", 36.0)})
    monkeypatch.setattr(runway, "_SUPERSEDED_BY", {"frontier-ru": "frontier-unified"})
    return logs


def test_healthy_superseder_forgives_the_absorbed_seat(twoseats):
    _log(twoseats, "frontier_ru_20260825T1603.log", 118, age_h=200.0)
    _log(twoseats, "frontier_unified_20260826T1121.log", 11919, age_h=0.4)
    rep = runway.audit()
    assert rep["seats"]["frontier-ru"]["status"] == "superseded"
    assert rep["seats"]["frontier-ru"]["covered_by"] == "frontier-unified"
    assert rep["n_bad"] == 0


def test_broken_superseder_takes_every_ground_down_with_it(twoseats):
    """THE PROPERTY THAT MAKES THIS NOT A DENOMINATOR TRICK. One repair, N grounds -- and the
    fence says so instead of going quietly green on seven dead hunting grounds."""
    _log(twoseats, "frontier_ru_20260825T1603.log", 118, age_h=200.0)
    _log(twoseats, "frontier_unified_20260826T1121.log", 180, age_h=0.4)  # a stub
    rep = runway.audit()
    assert rep["seats"]["frontier-unified"]["status"] == "stub"
    assert rep["seats"]["frontier-ru"]["status"] == "superseder-broken"
    assert rep["n_bad"] == 2, "an absorbed ground was forgiven while its superseder was failing"


def test_supersession_pointing_at_nothing_is_worse_than_none(twoseats, monkeypatch):
    """A retirement that points at an absent seat is a ground with no watcher at all."""
    monkeypatch.setattr(runway, "_SUPERSEDED_BY", {"frontier-ru": "frontier-does-not-exist"})
    _log(twoseats, "frontier_ru_20260825T1603.log", 118, age_h=200.0)
    _log(twoseats, "frontier_unified_20260826T1121.log", 11919, age_h=0.4)
    rep = runway.audit()
    assert rep["seats"]["frontier-ru"]["status"] == "superseder-broken"
    assert "ABSENT" in rep["seats"]["frontier-ru"]["covered_by"]


def test_every_superseder_named_today_is_a_real_seat():
    """Live wiring check: a supersede map that drifts off its own table is the defect returning."""
    missing = set(runway._SUPERSEDED_BY.values()) - set(runway._SEATS)
    assert not missing, missing


def test_the_organ_that_actually_runs_is_watched():
    """The hole this whole change exists to close: the dig that replaced seven seats appeared
    in no liveness table at all, so its death would have been invisible."""
    from scripts.max_audit import ORGANS
    assert "frontier-unified" in ORGANS
    assert "frontier-unified" in runway._SEATS
    assert runway._SEATS["frontier-unified"][2] in runway._MIN_BYTES
