"""A STEP KILLED BY A SIGNAL IS A VERDICT ON THE BOX, NOT ON THE CODE.

`_run_steps` reduced every non-zero exit to `ok = r.returncode == 0` and filed the bare step label,
so a child the kernel SIGKILLed before it ran a single test was recorded identically to a child
that ran to completion and reported real failures. The file already draws exactly this distinction
one branch higher -- "[HUNG] ... 'wedged' and 'broken' have different first moves" -- but only for
the clock. It was never drawn for the resource this box actually runs out of.

MEASURED 2026-08-05, which is why this is a bug and not a hypothetical: several agent sessions
share this 3.8GB VPS with the live executor and the recorders, and it has NO SWAP. max_audit's
pytest probe recorded rc=-9 and raised `test-suite-uncollectable` with an EMPTY reason (its `why`
extraction finds no ERROR lines, because the process was killed before printing any) and advice to
"install the missing dependency". There was no missing dependency: the full suite collected cleanly
seconds later -- rc=0, peak RSS 326MB, 19s. The desk was being pointed at a phantom.

THE COST IS NOT THE WASTED HUNT, IT IS THE HABIT. `ci-gate-red` has recurred 8x in 10.8d over 18
sightings, and the previous repair generalised only the FILE half of the shared-box problem
(a sibling's untracked scratch files, `tracked_ok`). The memory half was left open, so reds kept
arriving that nobody could act on -- and a red everyone has learned to dismiss is how two real mypy
errors sat buried inside one on 2026-08-05.

WHAT THIS SUITE PINS, and the direction matters more than the wording:

  1. a signal death is named distinctly and carries its evidence (the signal, the memory reading);
  2. it is STILL COUNTED FAILED -- the gate exits non-zero, the marker writes ok=false, and
     `tracked_ok` stays False so max_audit's ci-gate-red still fires. "Unknown" reads as
     NOT-PROVEN-GREEN on a safety gate, never as fine. Nothing here loosens the gate, and a
     future edit that makes a killed step read green must fail this file;
  3. it is never re-run by `_attribute` -- re-running a memory-killed step under the same pressure
     doubles the shortage it is reporting, which is the stated reason HUNG refuses a re-run too.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import scripts.run_ci as run_ci

_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _isolate_marker(monkeypatch, tmp_path):
    """Never let this suite write the REAL data/.ci_last_run.json.

    `_run_steps` writes the desk's safety-gate marker as a side effect, and max_audit escalates
    off that file. A test that fabricates a verdict into it would be manufacturing the exact
    stale/false gate state this repository keeps paying to detect.
    """
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(run_ci, "_ROOT", tmp_path)


def _marker(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "data/.ci_last_run.json").read_text("utf-8"))


def _fake_run(returncode: int):
    """A subprocess.run stand-in that reports `returncode` for the pytest step only."""
    def _run(cmd, **kw):
        rc = returncode if any("pytest" in str(c) for c in cmd) else 0
        return subprocess.CompletedProcess(cmd, rc, stdout="", stderr="")
    return _run


class TestSignalDeathIsNotACodeVerdict:
    def test_killed_step_is_named_distinctly_and_carries_its_evidence(
            self, monkeypatch, capsys, tmp_path):
        """The label IS the diagnosis -- max_audit prints failed_tracked verbatim."""
        monkeypatch.setattr(run_ci.subprocess, "run", _fake_run(-9))
        monkeypatch.setattr(run_ci, "_inflight_py", lambda: [])
        run_ci._run_steps()
        marker = _marker(tmp_path)
        killed = [s for s in marker["failed"] if "pytest" in s]
        assert killed, "the killed step vanished from `failed` -- that is the stale-green failure"
        label = killed[0]
        assert "KILLED sig9" in label, f"signal death not named: {label!r}"
        assert "MemAvailable" in label, (
            f"no evidence in the label -- the claim must be checkable, not asserted: {label!r}")
        assert "NOT a code failure" in label, (
            f"the label must stop the reader hunting a broken test: {label!r}")
        assert "[KILLED]" in capsys.readouterr().out

    def test_killed_step_still_fails_the_gate(self, monkeypatch, tmp_path):
        """THE NON-LOOSENING DIRECTION. Unknown is not green; this must never become a pass."""
        monkeypatch.setattr(run_ci.subprocess, "run", _fake_run(-9))
        monkeypatch.setattr(run_ci, "_inflight_py", lambda: [])
        assert run_ci._run_steps() == 1, (
            "a killed step read as GREEN -- the gate switched itself off")
        marker = _marker(tmp_path)
        assert marker["ok"] is False
        assert marker["tracked_ok"] is False, (
            "tracked_ok went True on a step that never reported a verdict -- max_audit's "
            "ci-gate-red would go silent about a gate that did not run")
        assert marker["killed"], "the `killed` field must record the state structurally"

    def test_killed_step_is_never_re_run(self, monkeypatch):
        """Re-running a memory-killed step under the same pressure doubles the shortage."""
        calls: list[list[str]] = []

        def _counting(cmd, **kw):
            calls.append([str(c) for c in cmd])
            rc = -9 if any("pytest" in str(c) for c in cmd) else 0
            return subprocess.CompletedProcess(cmd, rc, stdout="", stderr="")

        monkeypatch.setattr(run_ci.subprocess, "run", _counting)
        # Scratch files present is what makes _attribute re-run steps at all.
        monkeypatch.setattr(run_ci, "_inflight_py", lambda: ["tests/scratch_wip.py"])
        run_ci._run_steps()
        # COUNTED PER DISTINCT COMMAND, NOT PER TOOL. This asserted `len(pytest_runs) == 1`, which
        # silently encoded "there is exactly ONE pytest step in _STEPS" -- so adding the 8-second
        # collection gate ahead of the full suite failed it, on the gate being ADDED rather than on
        # anything being re-run. The invariant was never about how many pytest steps exist; it is
        # that a step killed by the OOM killer is not immediately re-run under the same shortage.
        pytest_runs = [tuple(c) for c in calls if any("pytest" in x for x in c)]
        repeated = {c for c in pytest_runs if pytest_runs.count(c) > 1}
        assert not repeated, (
            f"a memory-killed pytest step was re-run under the same pressure that killed it: "
            f"{sorted(repeated)}")
        assert pytest_runs, "guard the guard: no pytest step ran at all, so nothing was proved"

    @pytest.mark.parametrize("rc", [1, 2])
    def test_an_ordinary_red_is_untouched(self, monkeypatch, rc, tmp_path):
        """A real failure must keep reading as a real failure -- this fix must not launder one."""
        monkeypatch.setattr(run_ci.subprocess, "run", _fake_run(rc))
        monkeypatch.setattr(run_ci, "_inflight_py", lambda: [])
        assert run_ci._run_steps() == 1
        marker = _marker(tmp_path)
        assert "tests (pytest)" in marker["failed_tracked"], (
            "a genuine test failure stopped being attributed to committed code")
        assert not marker["killed"]


class TestMemoryReadingDegradesHonestly:
    def test_unreadable_meminfo_reports_unknown_not_zero(self, monkeypatch):
        """None and 0 are different answers. 'We could not measure' must never render as 'none'."""
        monkeypatch.setattr(run_ci.Path, "read_text",
                            lambda self, *a, **k: (_ for _ in ()).throw(OSError("no /proc")))
        assert run_ci._mem_available_mb() is None

    def test_reads_the_real_value_where_proc_exists(self):
        got = run_ci._mem_available_mb()
        if Path("/proc/meminfo").exists():
            assert isinstance(got, int) and got >= 0
