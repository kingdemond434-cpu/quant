"""THE REAPER THAT UNWEDGES THE SHIP PATH -- it must kill what is stopped and nothing else.

MEASURED 2026-09-24 01:10Z ON THE TRADING BOX. Four git processes alive since 22:03:53Z --
`git merge -s ours`, the `git stash create` it spawned, and the `git update-index --stdin` that
was blocked on a pipe nobody would write to -- held `.git/index.lock` and the `MT5-GitWriter`
mutex. Every ship step serialises on that mutex, so the adoption logged "another git writer held
Local\\MT5-GitWriter for the full 9 min" at 22:41, 22:53 and 23:00 and shipped nothing, while the
box sat 7 commits behind origin running code that was not the shipped code.

These tests pin the two halves that make the reaper safe to run unattended on a live trading box:

  * it kills only what it can PROVE is stopped -- a slow writer that is burning CPU or moving
    bytes is spared, because `git gc` on this repository is legitimately slow and killing it
    mid-repack is how a repository is destroyed;
  * without psutil the answer is UNMEASURED and nothing is signalled, never a guess.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops import git_writer_lock as gwl  # noqa: E402


class _FakeProc:
    """Minimal psutil.Process stand-in: a name, an age, and a CPU/IO tape it plays back."""

    def __init__(self, pid: int, name: str, age_s: float, tape: list[tuple[float, int]],
                 cmd: str = "git merge", parent_alive: bool | None = None) -> None:
        self.pid = pid
        self._name = name
        self.info = {"pid": pid, "name": name,
                     "create_time": time.time() - age_s, "cmdline": cmd.split()}
        self._tape = tape
        self._n = 0
        self.killed = False
        self._parent_alive = parent_alive

    def _tick(self) -> tuple[float, int]:
        row = self._tape[min(self._n, len(self._tape) - 1)]
        self._n += 1
        return row

    def cpu_times(self) -> Any:
        cpu, _io = self._tick()

        class _T:
            user = cpu
            system = 0.0
        return _T()

    def io_counters(self) -> Any:
        _cpu, io = self._tape[min(max(self._n - 1, 0), len(self._tape) - 1)]

        class _C:
            read_bytes = io
            write_bytes = 0
        return _C()

    def parents(self) -> list[Any]:
        return []

    def parent(self) -> Any:
        if self._parent_alive is None:
            raise NotImplementedError
        if not self._parent_alive:
            return None

        class _Parent:
            @staticmethod
            def is_running() -> bool:
                return True
        return _Parent()

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout: float | None = None) -> int:
        return 0


class _FakePsutil:
    def __init__(self, procs: list[_FakeProc]) -> None:
        self._procs = procs

    def process_iter(self, _attrs: Any = None) -> list[_FakeProc]:
        return list(self._procs)

    def Process(self, pid: int) -> _FakeProc:  # psutil's own spelling, kept verbatim
        for p in self._procs:
            if p.pid == pid:
                return p
        raise LookupError(pid)


@pytest.fixture
def _no_sleep() -> Any:
    return lambda _s: None


def _install(monkeypatch: pytest.MonkeyPatch, procs: list[_FakeProc]) -> _FakePsutil:
    fake = _FakePsutil(procs)
    monkeypatch.setattr(gwl, "_psutil", lambda: fake)
    return fake


def test_a_stopped_writer_is_named(monkeypatch: pytest.MonkeyPatch, _no_sleep: Any) -> None:
    """Zero CPU and zero I/O across the window, well past every writer's own timeout."""
    stopped = _FakeProc(101, "git.exe", 3.2 * 3600, [(5.0, 1000), (5.0, 1000)])
    _install(monkeypatch, [stopped])
    rep = gwl.hung_writers(sleep=_no_sleep)
    assert rep["status"] == "MEASURED"
    assert [r["pid"] for r in rep["hung"]] == [101]
    assert "stopped, not slow" in rep["hung"][0]["why"]


def test_a_slow_writer_is_spared(monkeypatch: pytest.MonkeyPatch, _no_sleep: Any) -> None:
    """`git gc` is legitimately slow and old. Killing it mid-repack destroys a repository."""
    busy = _FakeProc(202, "git.exe", 9 * 3600, [(5.0, 1000), (7.5, 4000)], cmd="git gc")
    _install(monkeypatch, [busy])
    rep = gwl.hung_writers(sleep=_no_sleep)
    assert rep["hung"] == []
    assert any(r["pid"] == 202 and "slow, not stopped" in r["why"] for r in rep["spared"])


def test_an_orphaned_stdin_index_pack_is_reaped_even_if_it_burns_cpu(
        monkeypatch: pytest.MonkeyPatch, _no_sleep: Any) -> None:
    """A fetch child with no parent cannot publish a ref; CPU movement cannot make it useful."""
    orphan = _FakeProc(207, "git.exe", 2 * 3600, [(5.0, 1000), (8.0, 4000)],
                       cmd="git index-pack --stdin --fix-thin", parent_alive=False)
    _install(monkeypatch, [orphan])
    rep = gwl.hung_writers(sleep=_no_sleep)
    assert [r["pid"] for r in rep["hung"]] == [207]
    assert "has no parent in either sample" in rep["hung"][0]["why"]


def test_a_live_parent_keeps_an_active_stdin_index_pack_safe(
        monkeypatch: pytest.MonkeyPatch, _no_sleep: Any) -> None:
    child = _FakeProc(208, "git.exe", 2 * 3600, [(5.0, 1000), (8.0, 4000)],
                      cmd="git index-pack --stdin --fix-thin", parent_alive=True)
    _install(monkeypatch, [child])
    rep = gwl.hung_writers(sleep=_no_sleep)
    assert rep["hung"] == []
    assert any(r["pid"] == 208 and "slow, not stopped" in r["why"] for r in rep["spared"])


def test_a_writer_still_waiting_for_the_mutex_is_never_a_candidate(
        monkeypatch: pytest.MonkeyPatch, _no_sleep: Any) -> None:
    """THE ONE REAL JOB OF THE AGE FLOOR, and it is not "slow writers are legitimate" -- the delta
    proof already handles those. A writer BLOCKED WAITING for the mutex burns no CPU and moves no
    bytes either, so it is indistinguishable from a wedge by movement alone. Adopt-And-Seal waits
    540 s before giving up, so a motionless writer at 500 s may simply be queued and about to do
    real work. Killing it is the trigger-happy failure that gets a reaper switched off."""
    waiting = _FakeProc(303, "git.exe", 500.0, [(0.0, 0), (0.0, 0)])
    _install(monkeypatch, [waiting])
    rep = gwl.hung_writers(sleep=_no_sleep)
    assert rep["hung"] == []
    assert any(r["pid"] == 303 for r in rep["spared"])


def test_the_floor_clears_the_longest_legitimate_wait_and_no_more(
        monkeypatch: pytest.MonkeyPatch, _no_sleep: Any) -> None:
    """MEASURED 2026-09-24: at 1800 s, with the reaper on a 15-minute clock, a wedge was invisible
    for up to 45 minutes -- and one was, through five consecutive CLEAR reports, while the seal
    could not take the lock and `allows_new_risk` stayed False into the approach of a placement
    window. The floor now sits just past the 540 s mutex wait, so a motionless writer past every
    legitimate queue is reaped on the evidence rather than waited out."""
    assert 540.0 < gwl.HUNG_MIN_AGE_S <= 900.0, (
        "the floor must clear Adopt-And-Seal's 540 s mutex wait and nothing beyond it")
    wedged = _FakeProc(404, "git.exe", 620.0, [(1.5, 900), (1.5, 900)])
    _install(monkeypatch, [wedged])
    rep = gwl.hung_writers(sleep=_no_sleep)
    assert [r["pid"] for r in rep["hung"]] == [404]


def test_a_writer_moving_only_bytes_is_spared(monkeypatch: pytest.MonkeyPatch,
                                              _no_sleep: Any) -> None:
    """A chunked push blocked on the network burns almost no CPU while still transferring. If the
    proof were CPU alone this would be killed mid-push, which is one lane's legitimate work
    destroyed by the fence meant to protect it. I/O movement alone must spare."""
    pushing = _FakeProc(505, "git.exe", 5_000.0, [(2.0, 1_000), (2.0, 4_500_000)])
    _install(monkeypatch, [pushing])
    rep = gwl.hung_writers(sleep=_no_sleep)
    assert rep["hung"] == []
    assert any("slow, not stopped" in r["why"] for r in rep["spared"])


def test_a_writer_moving_only_cpu_is_spared(monkeypatch: pytest.MonkeyPatch,
                                            _no_sleep: Any) -> None:
    """The mirror case: `git gc` on a 22 GB repository burns CPU for a long time and may report
    no per-process I/O at all on some platforms. Killing it mid-repack is how a repository gets
    corrupted."""
    packing = _FakeProc(606, "git.exe", 9_000.0, [(11.0, 0), (48.0, 0)])
    _install(monkeypatch, [packing])
    rep = gwl.hung_writers(sleep=_no_sleep)
    assert rep["hung"] == []
    assert any("slow, not stopped" in r["why"] for r in rep["spared"])


def test_the_sample_window_is_long_enough_to_see_a_working_writer() -> None:
    """The other half of lowering the floor: the proof that replaces it is made stronger, not
    weaker. One `sleep` covers every candidate, so this costs sixty seconds per RUN and not per
    process, and a longer window makes this strictly LESS likely to kill live work."""
    assert gwl.HUNG_SAMPLE_S >= 60.0
    assert gwl.HUNG_SAMPLE_S < 540.0, "the sample must sit well inside the mutex wait"


def test_sshd_is_not_a_writer() -> None:
    """The SSH SERVER is long-lived by design; matching it once reported a healthy 3.9-day-old
    service as a stuck writer, and a guard whose first output is a false positive gets removed."""
    assert "sshd" not in gwl._WRITER_NAMES
    assert "sshd.exe" not in gwl._WRITER_NAMES
    assert {"git", "git.exe", "ssh", "ssh.exe"} == set(gwl._WRITER_NAMES)


def test_without_psutil_the_answer_is_unmeasured_and_nothing_is_signalled(
        monkeypatch: pytest.MonkeyPatch, _no_sleep: Any) -> None:
    monkeypatch.setattr(gwl, "_psutil", lambda: None)
    rep = gwl.reap_hung_writers(apply=True, sleep=_no_sleep)
    assert rep["status"] == "UNMEASURED"
    assert rep["killed"] == [] and rep["hung"] == []


def test_dry_run_kills_nothing(monkeypatch: pytest.MonkeyPatch, _no_sleep: Any) -> None:
    """The decision must always be readable before it is taken."""
    stopped = _FakeProc(404, "git.exe", 4 * 3600, [(1.0, 10), (1.0, 10)])
    _install(monkeypatch, [stopped])
    rep = gwl.reap_hung_writers(apply=False, sleep=_no_sleep)
    assert rep["hung"] and rep["killed"] == []
    assert stopped.killed is False
    assert "--apply was not given" in rep["why"]


def test_apply_kills_only_the_stopped_one(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                                          _no_sleep: Any) -> None:
    stopped = _FakeProc(505, "git.exe", 4 * 3600, [(1.0, 10), (1.0, 10)])
    busy = _FakeProc(506, "git.exe", 4 * 3600, [(1.0, 10), (9.0, 99)])
    _install(monkeypatch, [stopped, busy])
    rep = gwl.reap_hung_writers(apply=True, sleep=_no_sleep, repo=tmp_path)
    assert [r["pid"] for r in rep["killed"]] == [505]
    assert stopped.killed is True
    assert busy.killed is False


def test_the_ratchet_in_the_reversion_fence_only_falls() -> None:
    """The count of builder work about to be silently reverted is a burn-down: a run that
    measures MORE than the best ever leaves the bar where it is and reports the regression.
    Raising the bar to match a regression is the denominator trick one level up."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_br", ROOT / "scripts" / "check_box_reversion.py")
    assert spec and spec.loader
    br = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(br)

    out = Path(__file__).resolve().parent / "__reversion_ratchet_tmp.json"
    try:
        base = {"generated": "2026-09-24T00:00:00+00:00", "status": "AT_RISK",
                "uncommitted": [{"path": f"libs/a{i}.py"} for i in range(5)], "unpushed": []}
        first = br.publish(dict(base), out=out)
        assert first["best_at_risk"] == 5 and first["ratchet_ok"] is True

        better = dict(base, uncommitted=[{"path": "libs/a0.py"}])
        second = br.publish(better, out=out)
        assert second["best_at_risk"] == 1 and second["ratchet_ok"] is True

        worse = dict(base, uncommitted=[{"path": f"libs/a{i}.py"} for i in range(9)])
        third = br.publish(worse, out=out)
        assert third["best_at_risk"] == 1, "the bar must NOT rise to match a regression"
        assert third["ratchet_ok"] is False
        assert "REGRESSION" in third["ratchet_why"]

        unmeasured = dict(base, status="UNMEASURED", uncommitted=[], unpushed=[])
        fourth = br.publish(unmeasured, out=out)
        assert fourth["best_at_risk"] == 1, "an unmeasurable tree may not move the bar"
        assert fourth["ratchet_ok"] is None
    finally:
        out.unlink(missing_ok=True)
