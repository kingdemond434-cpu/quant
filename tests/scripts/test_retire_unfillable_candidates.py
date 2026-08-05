"""The L2.4 no-silent-swallow contract on the §42 retirement organ's live-writer probe.

`_live_writers(db)` returns TWO lists because they mean opposite things: writer EVIDENCE ("someone
is holding the store") and probe FAILURES ("I could not look"). Collapsing the second into the
first is exactly the reading that lets this script UPDATE research_candidates underneath a live
factory writer -- "I could not look" silently becoming "nothing is there". These tests pin that
UNMEASURED never reads as idle, in the helper and again at the caller's refusal.

NO NETWORK, NO REAL PROCESS SCAN: `subprocess.run` is replaced in every test, and the retry loop's
`time.sleep` is neutralised so a busy-store refusal is instant.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from scripts import retire_unfillable_candidates as ruc

_IDLE_PS = "\n".join([
    "/sbin/init splash",
    "sshd: quant@pts/0",
    ".venv/bin/python scripts/check_freshness.py",     # a python organ, but not a writer
])


def _cp(argv, rc: int, out: str = "", err: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(argv, rc, out, err)


def _router(monkeypatch, *, fuser=None, ps=None):
    """Drive both probes independently. Each hook takes argv and returns a CompletedProcess, or
    raises to simulate an unavailable probe."""
    def fake_run(argv, **_kw):
        if argv[0] == "fuser":
            if fuser is None:
                return _cp(argv, 1)                   # rc 1 = measured: nobody holds it
            return fuser(argv)
        if argv[0] == "ps":
            if ps is None:
                return _cp(argv, 0, _IDLE_PS)
            return ps(argv)
        raise AssertionError(f"unexpected probe {argv!r}")

    monkeypatch.setattr(ruc.subprocess, "run", fake_run)
    return fake_run


def _db(tmp_path: Path, *, wal: bool = True) -> Path:
    db = tmp_path / "sor_research.sqlite"
    db.write_bytes(b"SQLite format 3\x00")
    if wal:
        Path(str(db) + "-wal").write_bytes(b"")
    return db


# ---------------------------------------------------- the contract: UNMEASURED is never "idle"

def test_a_probe_that_cannot_run_is_reported_not_swallowed(monkeypatch, tmp_path):
    """Every probe raising OSError must produce an EMPTY hit list AND a non-empty failure list.
    An empty hit list on its own is indistinguishable from a measured-idle store -- the failure
    list is the only thing that stops the caller mutating rows under a live writer."""
    def boom(argv):
        raise OSError("[Errno 2] No such file or directory: 'fuser'")

    _router(monkeypatch, fuser=boom, ps=boom)
    hits, probe_failures = ruc._live_writers(_db(tmp_path))

    assert hits == []
    assert probe_failures, "a failed probe must never vanish into an empty hit list"
    assert any("fuser(" in f and "unavailable" in f for f in probe_failures)
    assert any("ps scan unavailable" in f for f in probe_failures)
    assert any("UNMEASURED" in f for f in probe_failures), (
        "the sentinel that says NO probe delivered a measurement must be present")


def test_a_probe_timeout_is_reported(monkeypatch, tmp_path):
    def slow(argv):
        raise subprocess.TimeoutExpired(argv, 10)

    _router(monkeypatch, fuser=slow, ps=slow)
    hits, probe_failures = ruc._live_writers(_db(tmp_path))
    assert hits == []
    assert any("TimeoutExpired" in f for f in probe_failures)
    assert any("UNMEASURED" in f for f in probe_failures)


def test_a_measured_idle_store_reports_no_failures(monkeypatch, tmp_path):
    """The counterpart: when both probes DO run and find nothing, the failure list must be empty,
    or the organ could never retire anything at all."""
    _router(monkeypatch)
    hits, probe_failures = ruc._live_writers(_db(tmp_path))
    assert hits == [] and probe_failures == []


def test_fuser_rc_one_is_a_real_measurement_not_a_malfunction(monkeypatch, tmp_path):
    """`fuser` exits 1 to say 'no process holds this file'. Reading that as a probe malfunction
    would make the organ refuse forever on a perfectly idle box."""
    _router(monkeypatch, fuser=lambda argv: _cp(argv, 1, "", ""))
    hits, probe_failures = ruc._live_writers(_db(tmp_path))
    assert hits == [] and probe_failures == []


def test_fuser_rc_above_one_is_a_probe_malfunction(monkeypatch, tmp_path):
    _router(monkeypatch, fuser=lambda argv: _cp(argv, 2, "", "fuser: cannot open /proc"))
    hits, probe_failures = ruc._live_writers(_db(tmp_path))
    assert hits == []
    assert len(probe_failures) == 2, "one failure per probed file (db + wal)"
    assert all("rc=2" in f for f in probe_failures)
    assert not any("UNMEASURED" in f for f in probe_failures), (
        "the ps probe DID deliver a measurement, so the no-probe sentinel must not fire")


def test_only_files_that_exist_are_probed(monkeypatch, tmp_path):
    probed: list[str] = []
    _router(monkeypatch, fuser=lambda argv: (probed.append(argv[1]), _cp(argv, 1))[1])
    ruc._live_writers(_db(tmp_path, wal=False))
    assert len(probed) == 1 and not probed[0].endswith("-wal")


def test_an_absent_db_still_gets_a_ps_measurement(monkeypatch, tmp_path):
    """Nothing to fuse is not nothing to measure: the ps scan alone is a real measurement, so the
    UNMEASURED sentinel must not fire."""
    _router(monkeypatch, fuser=lambda argv: pytest.fail("fuser must not run on an absent file"))
    hits, probe_failures = ruc._live_writers(tmp_path / "absent.sqlite")
    assert hits == [] and probe_failures == []


# ------------------------------------------------------------------- positive writer evidence

def test_fuser_reports_a_holding_pid_as_a_live_writer(monkeypatch, tmp_path):
    _router(monkeypatch, fuser=lambda argv: _cp(argv, 0, " 31337 31338"))
    hits, probe_failures = ruc._live_writers(_db(tmp_path, wal=False))
    assert len(hits) == 1
    assert "31337" in hits[0] and "sor_research.sqlite" in hits[0]
    assert probe_failures == []


def test_fuser_rc_zero_with_no_pids_is_not_evidence(monkeypatch, tmp_path):
    """rc 0 with empty stdout carries no pid, so it cannot be quoted as evidence of a holder."""
    _router(monkeypatch, fuser=lambda argv: _cp(argv, 0, "   \n"))
    hits, probe_failures = ruc._live_writers(_db(tmp_path, wal=False))
    assert hits == [] and probe_failures == []


@pytest.mark.parametrize("script", ruc._WRITER_SCRIPTS)
def test_every_declared_writer_entry_point_is_detected(monkeypatch, tmp_path, script):
    line = f"/home/quant/quant-platform/.venv/bin/python scripts/{script} --loop"
    _router(monkeypatch, ps=lambda argv: _cp(argv, 0, _IDLE_PS + "\n" + line))
    hits, probe_failures = ruc._live_writers(_db(tmp_path))
    assert len(hits) == 1 and script in hits[0]
    assert probe_failures == []


def test_a_non_python_cmdline_naming_a_writer_is_not_a_writer(monkeypatch, tmp_path):
    """The pgrep self-match trap (desk memory 2026-08-04): a sibling agent's cmdline carries a
    prompt that MENTIONS the factory scripts. Matching it would refuse retirement forever."""
    sibling = ('node /usr/local/lib/claude/cli.js --print "did scripts/run_autodiscovery.py and '
               'scripts/daily_research_cycle.py finish their tick?"')
    _router(monkeypatch, ps=lambda argv: _cp(argv, 0, _IDLE_PS + "\n" + sibling))
    hits, probe_failures = ruc._live_writers(_db(tmp_path))
    assert hits == [], "a prompt that merely names a writer is not a writer"
    assert probe_failures == []


def test_ps_rc_nonzero_is_a_probe_failure_not_an_idle_store(monkeypatch, tmp_path):
    _router(monkeypatch, ps=lambda argv: _cp(argv, 1, "", "ps: error"))
    hits, probe_failures = ruc._live_writers(_db(tmp_path))
    assert hits == []
    assert any("ps scan rc=1" in f for f in probe_failures)


# --------------------------------------------------------------- the caller's refusal ladder

def _lawful(monkeypatch, ok: bool = True):
    import libs.ops.lawful as lawful
    monkeypatch.setattr(lawful, "guard",
                        lambda *a, **k: lawful.GuardResult(ok=ok, failures=() if ok else ("x",)))


def _argv(monkeypatch, *args: str):
    monkeypatch.setattr(sys, "argv", ["retire_unfillable_candidates.py", *args])


def test_main_refuses_when_the_store_is_absent_and_never_creates_one(monkeypatch, tmp_path):
    """A writable Database() would happily make an empty DB and the run would then 'succeed' at
    retiring nothing on the wrong box."""
    _lawful(monkeypatch)
    missing = tmp_path / "nope.sqlite"
    _argv(monkeypatch, "--db", str(missing))
    assert ruc.main() == 2
    assert not missing.exists()


def test_main_refuses_when_the_law_guard_fails(monkeypatch, tmp_path):
    _lawful(monkeypatch, ok=False)
    _argv(monkeypatch, "--db", str(_db(tmp_path)))
    assert ruc.main() == 3


def test_main_refuses_to_write_when_idleness_is_unmeasured(monkeypatch, tmp_path, capsys):
    """The whole point of the 2-tuple: an unavailable probe must REFUSE the mutation, not fall
    through to the retirement walk on the strength of a measurement that never happened."""
    def boom(argv):
        raise OSError("fuser: not installed")

    _lawful(monkeypatch)
    _router(monkeypatch, fuser=boom, ps=boom)
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    _argv(monkeypatch, "--db", str(_db(tmp_path)))

    assert ruc.main() == 4
    err = capsys.readouterr().err
    assert "REFUSED: could not establish the store is idle" in err
    assert "--dry-run" in err, "the refusal must name the read-only path that IS still available"


def test_main_refuses_and_retries_while_a_writer_holds_the_store(monkeypatch, tmp_path, capsys):
    _lawful(monkeypatch)
    line = "/home/quant/quant-platform/.venv/bin/python scripts/run_autodiscovery.py"
    _router(monkeypatch, ps=lambda argv: _cp(argv, 0, line))
    slept: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))
    _argv(monkeypatch, "--db", str(_db(tmp_path)))

    assert ruc.main() == 4
    assert len(slept) == ruc._BUSY_RETRIES, "the store is re-probed, not refused on one look"
    err = capsys.readouterr().err
    assert "REFUSED: live writer still holds the store" in err
    assert "run_autodiscovery.py" in err, "the refusal must quote its evidence"
