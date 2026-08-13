"""R0395 -- THE DAILY WORK QUEUE MAY NOT BE BUILT ON NUMBERS IT DID NOT REFRESH.

`run_max_push` re-runs six producers, then merges their artifacts into one ranked queue stamped
`generated: <now>`. Until 2026-08-12 the refresh was `check=False, capture_output=True,
except (OSError, TimeoutExpired): return` -- a producer that crashed, exited non-zero or blew
the 300s budget was discarded at the call site, `build()` read whatever stale file was on disk,
and the merged queue carried today's date over last week's numbers with nothing to say so.

Widest blast radius on the desk: every organ and every session reads this artifact to decide
what to work on, so a silently-frozen input steers the whole day.

THE ONE THING THESE TESTS MUST ALSO PIN is the fix that would have been WORSE than the bug:
`check=True`. Five of the six producers are FENCES, and a fence exits 2 when it CATCHES
something. Refusing to build the queue on rc!=0 would have blanked it precisely on the days the
desk had most to work on -- so the test below asserts that an rc=2 producer which REWROTE its
artifact is a healthy refresh.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import scripts.run_max_push as MP


def _artifacts(tmp_path: Path) -> Path:
    """A tmp root carrying every declared producer artifact, all young and readable."""
    for _script, rel in MP._REFRESHERS:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"ok": True}), "utf-8")
    return tmp_path


@pytest.fixture
def rooted(tmp_path, monkeypatch):
    root = _artifacts(tmp_path)
    monkeypatch.setattr(MP, "_ROOT", root)
    return root


def _fake_run(outcomes: dict[str, Any]):
    """Stand in for subprocess.run, keyed on the producer script name in argv."""
    def run(cmd, **_kw):
        script = Path(cmd[1]).name
        outcome = outcomes.get(script, ("write", 0))
        if outcome[0] == "timeout":
            raise subprocess.TimeoutExpired(cmd, 300)
        if outcome[0] == "oserror":
            raise OSError("no interpreter")
        if outcome[0] == "write":
            rel = dict(MP._REFRESHERS)[script]
            p = MP._ROOT / rel
            p.write_text(json.dumps({"ok": True, "refreshed": True}), "utf-8")
        return subprocess.CompletedProcess(cmd, outcome[1], b"", b"boom\n")
    return run


# --------------------------------------------------------------- the refresh reports its fate


def test_a_producer_that_writes_nothing_is_NOT_REWRITTEN(rooted, monkeypatch) -> None:
    monkeypatch.setattr(MP.subprocess, "run", _fake_run({"check_ratchets.py": ("skip", 1)}))
    out = MP._refresh("check_ratchets.py", "data/ratchet_report.json")
    assert out["status"] == "NOT-REWRITTEN"
    assert out["rc"] == 1
    assert "boom" in out["detail"]


def test_a_timeout_is_reported_not_swallowed(rooted, monkeypatch) -> None:
    monkeypatch.setattr(MP.subprocess, "run", _fake_run({"check_ratchets.py": ("timeout", 0)}))
    out = MP._refresh("check_ratchets.py", "data/ratchet_report.json")
    assert out["status"] == "TIMEOUT" and "300s" in out["detail"]


def test_an_unlaunchable_producer_is_reported_not_swallowed(rooted, monkeypatch) -> None:
    monkeypatch.setattr(MP.subprocess, "run", _fake_run({"check_ratchets.py": ("oserror", 0)}))
    out = MP._refresh("check_ratchets.py", "data/ratchet_report.json")
    assert out["status"] == "UNRUNNABLE" and "no interpreter" in out["detail"]


def test_a_fence_that_FIRED_is_a_healthy_refresh_not_a_failure(rooted, monkeypatch) -> None:
    """THE FIX THAT WOULD HAVE BEEN WORSE THAN THE BUG. rc=2 is a fence CATCHING something.
    The artifact was rewritten, so the queue's input is current and the refresh is REFRESHED."""
    monkeypatch.setattr(MP.subprocess, "run", _fake_run({"check_freshness.py": ("write", 2)}))
    out = MP._refresh("check_freshness.py", "data/freshness_status.json")
    assert out["status"] == "REFRESHED" and out["rc"] == 2


# ------------------------------------------------- the queue publishes what it was built from


def test_a_dead_producer_reaches_the_QUEUE_not_just_a_log(rooted, monkeypatch) -> None:
    """DETECT IMPLIES REPAIR. A provenance block nobody is scheduled to act on is the
    found-never-fixed defect one layer up, so the failure is ranked in the same list."""
    monkeypatch.setattr(MP.subprocess, "run", _fake_run({"check_calibration.py": ("skip", 1)}))
    (rooted / "data/calibration_status.json").unlink()

    inp, runs = MP._queue_inputs(refresh=True)

    assert inp.status() == "UNMEASURED"
    assert [f for f in inp.fabricated() if f.endswith("calibration_status.json")]
    dead = [r for r in runs if r["status"] != "REFRESHED"]
    assert [r["script"] for r in dead] == ["check_calibration.py"]
    # the producer's fate is joined onto the input row, not left for a human to correlate
    rec = next(r for r in inp.records if r.path.endswith("calibration_status.json"))
    assert "producer check_calibration.py NOT-REWRITTEN" in rec.detail


def test_all_producers_healthy_reads_OK(rooted, monkeypatch) -> None:
    """The fence must not cry wolf on the healthy case, or it gets switched off (L1.43)."""
    monkeypatch.setattr(MP.subprocess, "run", _fake_run({}))
    inp, runs = MP._queue_inputs(refresh=True)
    assert inp.status() == "OK", inp.why()
    assert {r["status"] for r in runs} == {"REFRESHED"}


def test_no_refresh_still_declares_the_inputs(rooted, monkeypatch) -> None:
    """`--no-refresh` reads the artifacts as-is; that is a stronger reason to declare them, not
    a weaker one. Zero declared inputs may never read OK (L1.28a)."""
    inp, runs = MP._queue_inputs(refresh=False)
    assert runs == []
    assert inp.status() == "OK" and len(inp.records) == len(MP._REFRESHERS)


def test_a_stale_artifact_is_DEGRADED_even_when_the_producer_ran(rooted, monkeypatch) -> None:
    """Age and producer health are two different questions and both get asked."""
    import os
    import time

    monkeypatch.setattr(MP.subprocess, "run", _fake_run({"check_ratchets.py": ("skip", 0)}))
    old = time.time() - (MP._ARTIFACT_MAX_AGE_H + 10) * 3600
    os.utime(rooted / "data/ratchet_report.json", (old, old))
    inp, _runs = MP._queue_inputs(refresh=True)
    assert inp.status() == "DEGRADED", inp.why()
