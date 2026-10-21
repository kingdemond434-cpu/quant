"""JUDGING_RATE ATTEMPT MARKER: a killed pass names its phase, and the rate then reads STALE.

Measured 2026-10-21: JUDGING_RATE.json held `at` 01:52Z for hours while the box kept publishing,
and nothing said which pass died or where. These pin the marker, the early rate write, the bounded
ledger stream and the reader's three verdicts.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import judging_rate_attempt as jra  # noqa: E402
from research import judging_throughput as jt  # noqa: E402

UNMEASURED = jt.UNMEASURED
NOW = datetime(2026, 10, 21, 2, 0, tzinfo=UTC)
LATER = NOW + timedelta(seconds=jra.ATTEMPT_GRACE_S + 60)
BOX = {"cores": 18, "market_closed": False, "source": "GlobalMemoryStatusEx",
       "total_phys_mb": 98_298, "free_phys_mb": 59_364, "commit_limit_mb": 257_024,
       "commit_free_mb": 104_000, "terminal_running": True, "is_judging_box": True}


class Killed(BaseException):
    """A kill at the leg budget: not an Exception, so no best-effort handler swallows it."""


def _ledger(path: Path, n: int = 1) -> Path:
    path.write_text("".join(json.dumps({"at": NOW.isoformat(), "cell": f"c{i}",
                                        "terminal_gate": "in_sample_screen"}) + "\n"
                            for i in range(n)), encoding="utf-8")
    return path


@pytest.fixture
def box(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    r = tmp_path / "reports"
    r.mkdir()
    monkeypatch.setattr(jt, "OUT", r / "JUDGING_THROUGHPUT.json")
    monkeypatch.setattr(jt, "RATE_OUT", r / "JUDGING_RATE.json")
    monkeypatch.setattr(jt, "ATTEMPT_OUT", r / "JUDGING_RATE.attempt.json")
    monkeypatch.setattr(jt, "ENV_FILE", tmp_path / "env.json")
    monkeypatch.setattr(jt, "BACKPRESSURE", tmp_path / "bp.json")
    monkeypatch.setattr(jt, "BURNDOWN", tmp_path / "bd.json")
    monkeypatch.setattr(jt, "JUDGE_COVERAGE", tmp_path / "absent_coverage.json")
    monkeypatch.setattr(jt, "GATE_LEDGER", _ledger(tmp_path / "l.jsonl"))
    monkeypatch.setattr(jt, "REGISTRY", tmp_path / "none.sqlite")
    monkeypatch.setattr(jt, "measure_box", lambda *a, **k: dict(BOX))
    monkeypatch.setattr(jt, "task_time_limit_s", lambda *a, **k: 3600.0)
    monkeypatch.setattr(jt, "apply_env", lambda *a, **k: {})
    monkeypatch.setattr(jt, "apply_machine_env", lambda d, b: {"status": "APPLIED"})
    monkeypatch.setattr(jt, "apply_cadence", lambda m, b: {"status": "APPLIED", "minutes": m})
    # the last pass that DID publish, an hour before this one
    (r / "JUDGING_RATE.json").write_text(json.dumps(
        {"at": (NOW - timedelta(hours=1)).isoformat(), "status": "MEASURED",
         "verdicts_per_day": 5266.0, "created_per_day": 8303.0}), encoding="utf-8")
    return r


def _read(r: Path, now: datetime = LATER) -> dict:
    return jra.read_rate(now, rate_path=r / "JUDGING_RATE.json",
                         attempt_path=r / "JUDGING_RATE.attempt.json")


#: phase -> the call that runs inside it
KILL_POINTS = {
    "measure_box": "measure_box",
    "queue": "measure_queue",
    "plan": "plan",
    "rate": "measure_rate",
    "task_limit": "task_time_limit_s",
    "written": "apply_machine_env",
}


@pytest.mark.parametrize("phase", list(KILL_POINTS))
def test_a_kill_in_each_phase_leaves_a_marker_naming_it(box: Path, monkeypatch, phase) -> None:
    def _die(*a, **k):
        raise Killed(phase)

    monkeypatch.setattr(jt, KILL_POINTS[phase], _die)
    with pytest.raises(Killed):
        jt.run(write=True, now=NOW, apply=True)
    marker = json.loads((box / "JUDGING_RATE.attempt.json").read_text("utf-8"))
    assert marker["phase"] == phase
    assert marker["done"] is False
    assert marker["started_at"] == NOW.isoformat()
    assert marker["phases"][0]["phase"] == "started"
    got = _read(box)
    if phase in ("measure_box", "queue", "plan", "rate"):
        # the rate on disk is the previous pass's: it must read STALE, with the phase
        assert got["status"] == jra.STALE
        assert got["died_in_phase"] == phase
        assert got["why"].startswith(f"attempt started {NOW.isoformat()} died in phase {phase}")
    else:
        # the rate was published BEFORE the schtasks query and the apply: it is this pass's own
        rate = json.loads((box / "JUDGING_RATE.json").read_text("utf-8"))
        assert rate["at"] == NOW.isoformat()
        assert rate["attempt"]["started_at"] == NOW.isoformat()
        assert got["status"] == jra.FRESH, got["why"]


def test_a_normal_run_ends_applied_and_reads_fresh(box: Path) -> None:
    jt.run(write=True, now=NOW, apply=True)
    marker = json.loads((box / "JUDGING_RATE.attempt.json").read_text("utf-8"))
    assert marker["phase"] == "applied" and marker["done"] is True
    assert [p["phase"] for p in marker["phases"]] == list(jra.PHASES)
    rate = json.loads((box / "JUDGING_RATE.json").read_text("utf-8"))
    assert rate["status"] == "MEASURED"
    assert rate["attempt"] == {"marker": jra.ATTEMPT_REL, "started_at": NOW.isoformat(),
                               "pid": marker["pid"]}
    thr = json.loads((box / "JUDGING_THROUGHPUT.json").read_text("utf-8"))
    assert thr["attempt"]["started_at"] == NOW.isoformat()
    assert _read(box)["status"] == jra.FRESH


def test_a_run_without_apply_ends_written(box: Path) -> None:
    jt.run(write=True, now=NOW, apply=False)
    marker = json.loads((box / "JUDGING_RATE.attempt.json").read_text("utf-8"))
    assert marker["phase"] == "written" and marker["done"] is True
    assert _read(box)["status"] == jra.FRESH


def test_a_dry_run_writes_no_marker(box: Path) -> None:
    jt.run(write=False, now=NOW, apply=False)
    assert not (box / "JUDGING_RATE.attempt.json").exists()


def test_a_torn_marker_reads_unmeasured(box: Path) -> None:
    jt.run(write=True, now=NOW, apply=False)
    (box / "JUDGING_RATE.attempt.json").write_text('{"started_at": "2026-10-21T02:0', "utf-8")
    got = _read(box)
    assert got["status"] == UNMEASURED
    assert "torn" in got["why"]


def test_a_marker_without_a_stamp_reads_unmeasured(box: Path) -> None:
    (box / "JUDGING_RATE.attempt.json").write_text(json.dumps({"phase": "rate"}), "utf-8")
    assert _read(box)["status"] == UNMEASURED


def test_a_pass_still_inside_its_budget_is_not_called_dead(box: Path, monkeypatch) -> None:
    monkeypatch.setattr(jt, "measure_rate", lambda *a, **k: (_ for _ in ()).throw(Killed()))
    with pytest.raises(Killed):
        jt.run(write=True, now=NOW, apply=False)
    got = _read(box, now=NOW + timedelta(seconds=30))
    assert got["status"] == jra.FRESH     # the previous rate is one hour old: inside its age
    assert got["attempt_in_progress"]["phase"] == "rate"


def test_no_marker_falls_back_to_the_rates_own_age(box: Path) -> None:
    assert _read(box, now=NOW)["status"] == jra.FRESH
    got = _read(box, now=NOW + timedelta(hours=3))
    assert got["status"] == jra.STALE and "no JUDGING_RATE.attempt.json says why" in got["why"]


def test_an_unstamped_or_absent_rate_is_unmeasured(tmp_path: Path) -> None:
    got = jra.read_rate(NOW, rate_path=tmp_path / "none.json", attempt_path=tmp_path / "a.json")
    assert got["status"] == UNMEASURED
    (tmp_path / "r.json").write_text(json.dumps({"verdicts_per_day": 1.0}), "utf-8")
    got = jra.read_rate(NOW, rate_path=tmp_path / "r.json", attempt_path=tmp_path / "a.json")
    assert got["status"] == UNMEASURED and "`at`" in got["why"]


def test_a_ledger_stream_past_its_deadline_is_unmeasured_never_partial(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "big.jsonl", n=10)
    got = jt.measure_rate({"depth": UNMEASURED}, {}, NOW, ledger=ledger,
                          registry=tmp_path / "none.sqlite", deadline_s=-1.0)
    assert got["status"] == UNMEASURED
    assert got["verdicts"]["status"] == UNMEASURED
    assert "deadline" in got["verdicts"]["why"] and "deadline" in got["why"]
    assert got["verdicts_per_hour"] == UNMEASURED
    ok = jt.measure_rate({"depth": UNMEASURED}, {}, NOW, ledger=ledger,
                         registry=tmp_path / "none.sqlite", deadline_s=60.0)
    assert ok["status"] == "MEASURED" and ok["verdicts"]["counts"]["1h"] == 10


def test_an_overrun_pass_publishes_unmeasured_and_reads_unmeasured(box: Path) -> None:
    jt.run(write=True, now=NOW, apply=False, rate_budget_s=-1.0)
    rate = json.loads((box / "JUDGING_RATE.json").read_text("utf-8"))
    assert rate["status"] == UNMEASURED and "deadline" in rate["why"]
    assert "verdicts_per_day" in rate and rate["verdicts_per_day"] == UNMEASURED
    got = _read(box)
    assert got["status"] == UNMEASURED and "deadline" in got["why"]


def test_a_marker_write_failure_never_costs_the_pass(box: Path, monkeypatch) -> None:
    def _boom(path, doc):
        if path.name.endswith(".attempt.json"):
            raise PermissionError("held open")
        return real(path, doc)

    real = jra.write_atomic
    monkeypatch.setattr(jra, "write_atomic", _boom)
    jt.run(write=True, now=NOW, apply=False)
    rate = json.loads((box / "JUDGING_RATE.json").read_text("utf-8"))
    assert rate["at"] == NOW.isoformat()


def test_the_replace_retries_a_windows_permission_error(tmp_path: Path, monkeypatch) -> None:
    calls = {"n": 0}
    import os as _os
    real = _os.replace

    def _flaky(a, b):
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError("WinError 5")
        return real(a, b)

    monkeypatch.setattr(jra.os, "replace", _flaky)
    monkeypatch.setattr(jra, "REPLACE_BACKOFF_S", 0.0)
    jra.write_atomic(tmp_path / "x.json", {"a": 1})
    assert json.loads((tmp_path / "x.json").read_text("utf-8")) == {"a": 1}
    assert calls["n"] == 3
    assert not list(tmp_path.glob("*.tmp"))


def test_the_box_publishes_the_marker() -> None:
    from libs.ops import state_publication as sp
    assert jra.ATTEMPT_REL in sp.published_paths(_ROOT)
    gi = (_ROOT / ".gitignore").read_text("utf-8")
    assert f"!{jra.ATTEMPT_REL}" in gi


def test_tier1_gap_reads_a_dead_pass_as_stale(tmp_path: Path, monkeypatch) -> None:
    from research import tier1_gap as tg
    r = tmp_path / "reports"
    r.mkdir()
    monkeypatch.setattr(tg, "REPORTS", r)
    monkeypatch.setattr(tg, "HYP", tmp_path / "hyp")
    (r / "JUDGING_RATE.json").write_text(json.dumps(
        {"at": NOW.isoformat(), "verdicts_per_day": 5266.0, "created_per_day": 8303.0}), "utf-8")
    jra.Attempt(NOW + timedelta(minutes=50), r / "JUDGING_RATE.attempt.json").phase("rate")
    mj = tg.mining_and_judging(NOW + timedelta(hours=1))
    assert mj["judging_rate_status"] == jra.STALE
    assert "died in phase rate" in mj["judging_rate_why"]
    assert mj["verdicts_per_day"] == jra.STALE
    assert mj["judging_rate_last_measured"]["verdicts_per_day"] == 5266.0
    (r / "JUDGING_RATE.attempt.json").unlink()
    mj = tg.mining_and_judging(NOW + timedelta(minutes=10))
    assert mj["judging_rate_status"] == jra.FRESH and mj["verdicts_per_day"] == 5266.0
