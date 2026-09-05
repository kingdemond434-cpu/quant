"""The three-hourly miner maintainer: it must repair, and it must never lie about repairing.

A fixer is more dangerous than a checker. A checker that is wrong reports a false alarm; a fixer
that is wrong DELETES something. So the properties worth testing here are mostly the refusals --
what it declines to touch, and whether it can tell "nothing was wrong" from "I could fix nothing".
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "_miner_maint", _ROOT / "scripts" / "run_miner_maintenance.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mm():
    return _load()


@pytest.fixture
def locks(mm, tmp_path, monkeypatch):
    root = tmp_path / ".job_locks"
    root.mkdir()
    monkeypatch.setattr(mm, "LOCK_ROOT", root)

    def write(name: str, pid: int, age_s: float = 0.0) -> Path:
        p = root / f"{name}.json"
        p.write_text(json.dumps({"pid": pid, "token": "t", "host": "h"}), "utf-8")
        if age_s:
            st = p.stat()
            os.utime(p, (st.st_atime, st.st_mtime - age_s))
        return p
    return write


def test_a_lock_whose_owner_is_dead_is_removed(mm, locks) -> None:
    """The cheapest miner outage there is: a lock left by an OOM-killed job blocks every later
    run until the 45-minute stale timer expires, which on an hourly trigger is a guaranteed
    missed hour."""
    p = locks("edge_search", pid=999_999)          # a pid that cannot exist
    rows = mm.sweep_locks()
    assert not p.exists(), "a dead owner's lock was left in place"
    assert [r for r in rows if r["action"] == "REPAIRED"]


def test_a_live_owner_keeps_its_lock_however_old(mm, locks) -> None:
    """LIVENESS VETOES AGE, and this is the assertion that must never be relaxed.

    Reclaiming a running holder's lock produced two concurrent external_gauntlet sweeps on an 8GB
    box that also runs the live terminal, and saturated it so completely that ssh could not
    complete. A long job is not an abandoned one -- these sweeps legitimately run 60-90 minutes
    against a 45-minute timer, so age alone is evidence of nothing.
    """
    p = locks("external_gauntlet", pid=os.getpid(), age_s=mm.STALE_SECONDS * 4)
    rows = mm.sweep_locks()
    assert p.exists(), "a LIVE owner's lock was reclaimed -- this is how the box got saturated"
    assert any(r["action"] == "LEFT_ALONE" for r in rows)


def test_an_unreadable_lock_is_named_not_deleted(mm, locks, tmp_path) -> None:
    """A torn write is a producer bug, not an abandoned job. Deleting it destroys the evidence
    of which producer tore it, and the fixer becomes the reason nobody can debug the writer."""
    (tmp_path / ".job_locks" / "torn.json").write_text("{not json", "utf-8")
    rows = mm.sweep_locks()
    torn = [r for r in rows if r.get("lock") == "torn.json"]
    assert torn and torn[0]["action"] == "UNREPAIRABLE"
    assert (tmp_path / ".job_locks" / "torn.json").exists()


def test_dry_run_touches_nothing(mm, locks) -> None:
    """--dry-run must be honest in both directions: it reports the repair it WOULD make and does
    not make it. A dry run that quietly acts is worse than no dry run."""
    p = locks("orthogonal_sweep", pid=999_999)
    rows = mm.sweep_locks(dry_run=True)
    assert p.exists(), "dry-run deleted a lock"
    assert any(r["action"] == "REPAIRED" for r in rows), "dry-run hid what it would have done"


def test_an_unknowable_pid_is_treated_as_alive(mm, locks) -> None:
    """The third state exists so a host that cannot answer does not become the outage.

    If liveness is unreadable, every lock looks abandoned; a fixer that deletes on ignorance
    would clear the whole desk's locks on such a host and invite exactly the concurrency the
    locks prevent.
    """
    assert mm._owner_alive(0) is None
    p = locks("mystery", pid=0, age_s=mm.STALE_SECONDS * 3)
    mm.sweep_locks()
    assert p.exists(), "a lock with an unreadable owner was deleted"


def test_repairing_nothing_because_nothing_is_repairable_is_not_OK(mm, monkeypatch) -> None:
    """L1.28a, in the one place a fixer is most tempted to break it.

    "I repaired nothing because nothing was wrong" and "I repaired nothing because I could not"
    are different answers, and only the first is health. A maintainer that reports OK on the
    second is the reason nobody notices the thing it exists to notice.
    """
    monkeypatch.setattr(mm, "sweep_locks", lambda dry_run=False: [
        {"lock": "x.json", "action": "UNREPAIRABLE", "why": "torn"}])
    monkeypatch.setattr(mm, "_run", lambda rel: {"status": "OK", "exit_code": 0, "tail": []})
    doc = mm.run()
    assert doc["status"] == "UNREPAIRABLE"
    assert doc["repaired"] == 0


def test_a_successful_repair_does_not_exit_non_zero(mm, monkeypatch) -> None:
    """A maintainer whose SUCCESS pages is a maintainer its scheduler learns to ignore, and then
    its failures are invisible too. Only UNREPAIRABLE is worth waking somebody for."""
    monkeypatch.setattr(mm, "sweep_locks", lambda dry_run=False: [
        {"lock": "x.json", "action": "REPAIRED", "why": "owner gone"}])
    monkeypatch.setattr(mm, "_run", lambda rel: {"status": "OK", "exit_code": 0, "tail": []})
    monkeypatch.setattr(mm, "REPORT", Path(os.devnull))
    assert mm.main(["--json"]) == 0


def test_every_fence_on_the_desk_is_in_the_roster(mm) -> None:
    """The roster IS the cadence. A miner or seat fence missing from it runs at whatever schedule
    it separately has -- which for two of the six was none at all, measured 2026-09-05."""
    named = {rel for _n, rel in mm.CHECKS}
    on_disk = {f"scripts/{p.name}" for p in (_ROOT / "scripts").glob("check_miner_*.py")}
    on_disk |= {f"scripts/{p.name}" for p in (_ROOT / "scripts").glob("check_organ_*.py")}
    on_disk |= {f"scripts/{p.name}" for p in (_ROOT / "scripts").glob("check_seat_*.py")}
    missing = sorted(on_disk - named)
    assert not missing, (
        f"miner/seat fence(s) not on the maintainer's clock: {missing}. Add them to CHECKS, or "
        "they run only on whatever separate schedule they happen to have.")


def test_it_is_actually_scheduled(mm) -> None:
    """L1.28a again, one level up: a maintainer nobody runs maintains nothing. This is the whole
    point of the file and the easiest thing in it to leave undone."""
    manifest = (_ROOT / "ops" / "crontab.manifest").read_text("utf-8")
    rows = [ln for ln in manifest.splitlines()
            if "run_miner_maintenance.py" in ln and not ln.lstrip().startswith("#")]
    assert rows, "the maintainer is named only in a COMMENT -- a comment is not a schedule"
    assert any("*/3" in ln.split("cd ")[0] for ln in rows), (
        f"the principal asked for three-hourly; the cadence field carries no */3: {rows}")
