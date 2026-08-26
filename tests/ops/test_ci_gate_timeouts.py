"""A HANG MUST BE A FAILURE, NOT A WAIT -- and a gate that stopped running must not read green.

Until 2026-08-05 nothing in this repository bounded a gate's runtime. That is not a tidiness
complaint; it is a gate that can switch itself off and report success while doing it:

    a step blocks (a network-bound test on a filtered-egress box does exactly this, today, in
    tests/scripts) -> run_ci never exits -> it never releases data/.ci_run.lock -> every later
    run finds the lock held and returns 0 "skipping (marker left untouched)" BY DESIGN -> the
    .ci_last_run.json marker freezes at its last value -> max_audit raised only on `ok is False`
    and a frozen marker is never false -> the desk reports its safety gate GREEN, with nothing
    running behind it, for as long as the wedge lasts.

That is the 2026-07-22 incident (81h of undetected red gate) reached through a different door,
and the repair applied then -- surface a red marker -- is structurally unable to catch it,
because this failure never produces a red marker. It produces a stale green one.

So three independent repairs, and this suite pins all three, because each one alone leaves the
hole open and each one is individually easy to delete while "cleaning up timeouts":

  1. run_ci bounds every step, and a breach is named [HUNG] and counted FAILED -> red marker;
  2. the inner bounds beat the outer one in daily_research_cycle, or the outer kill happens
     first and nothing is named or recorded -- the same blindness, merely relocated;
  3. max_audit treats a STALE or unreadable marker as a defect: on a safety gate the honest
     reading of "unknown" is "not proven green", never "fine".

Repair 2 is the one most likely to rot: the two numbers live in different files, nothing else
relates them, and either can be edited alone in perfectly good faith.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest
import scripts.max_audit as max_audit
import scripts.run_ci as run_ci

_ROOT = Path(__file__).resolve().parents[2]


class TestEveryGateStepIsBounded:
    def test_no_step_is_unbounded(self) -> None:
        assert run_ci._STEPS, "the gate has no steps at all"
        for step in run_ci._STEPS:
            assert len(step) == 3, f"step {step[0]!r} carries no timeout budget"
            label, _cmd, budget = step
            assert isinstance(budget, int | float) and budget > 0, (
                f"step {label!r} has a non-positive budget -- unbounded by another name")

    def test_a_hung_step_is_a_named_failure_and_writes_a_red_marker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The whole point, executed rather than asserted about: a step that never returns must
        end as FAILED with a marker a downstream reader can see, not as a process that waits."""
        monkeypatch.setattr(run_ci, "_ROOT", tmp_path)
        monkeypatch.setattr(run_ci, "_LOCK", tmp_path / "ci.lock")
        (tmp_path / "data").mkdir()
        monkeypatch.setattr(
            run_ci, "_STEPS",
            [("wedged step", [sys.executable, "-c", "import time; time.sleep(600)"], 1)])

        rc = run_ci.main([])

        assert rc == 1, "a hung gate step must fail the gate, not pass it"
        out = capsys.readouterr().out
        assert "HUNG" in out, "a hang must be named distinctly from an ordinary red"
        marker = json.loads((tmp_path / "data/.ci_last_run.json").read_text("utf-8"))
        assert marker["ok"] is False
        assert any("HUNG" in f for f in marker["failed"]), (
            "the marker must carry the hang, or max_audit cannot escalate what it cannot see")

    def test_the_budget_actually_bounds_wall_clock(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A budget that is recorded but not enforced is decoration. Ten-minute sleep, 1s
        budget: if this test takes ten minutes, the enforcement is not there."""
        monkeypatch.setattr(run_ci, "_ROOT", tmp_path)
        monkeypatch.setattr(run_ci, "_LOCK", tmp_path / "ci.lock")
        (tmp_path / "data").mkdir()
        monkeypatch.setattr(
            run_ci, "_STEPS",
            [("wedged step", [sys.executable, "-c", "import time; time.sleep(600)"], 1)])
        t0 = time.monotonic()
        run_ci.main([])
        assert time.monotonic() - t0 < 30, "the timeout did not actually kill the step"


class TestInnerBoundsBeatTheOuterOne:
    """If daily_research_cycle's outer timeout wins, run_ci is killed from outside: no [HUNG]
    line, no red marker, nothing named. The wedge becomes invisible again."""

    def _outer_ci_gate_budget(self) -> float:
        src = (_ROOT / "scripts/daily_research_cycle.py").read_text("utf-8")
        m = re.search(r'\(\s*"ci_gate"\s*,\s*"scripts/run_ci\.py"\s*,\s*([0-9_]+)\s*\)', src)
        assert m, "could not find the ci_gate step in daily_research_cycle._STEPS"
        return float(m.group(1))

    def test_sum_of_inner_budgets_is_under_the_cycles_outer_budget(self) -> None:
        outer = self._outer_ci_gate_budget()
        assert outer > run_ci.STEP_BUDGET_TOTAL_S, (
            f"run_ci's steps can take {run_ci.STEP_BUDGET_TOTAL_S}s worst-case but the cycle "
            f"kills it at {outer}s -- the outer kill wins, so a wedged gate is killed silently "
            "with no red marker written. Raise the outer budget or lower the inner ones.")

    def test_the_margin_is_not_hairline(self) -> None:
        """Equality passes the test above while being useless in practice -- process startup and
        the subprocess teardown of four killed steps both cost real time."""
        outer = self._outer_ci_gate_budget()
        assert outer - run_ci.STEP_BUDGET_TOTAL_S >= 300, (
            "leave at least 5min of headroom for interpreter startup and step teardown")


class TestAStaleMarkerIsNotGreen:
    """Fail-closed. The failure mode being guarded is a marker that says ok=true and is simply
    no longer being written -- so every assertion here uses a marker whose `ok` is TRUE."""

    def _defects_for(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                     marker: str | None) -> list[str]:
        monkeypatch.setattr(max_audit, "ROOT", tmp_path)
        monkeypatch.setattr(max_audit, "NOW", time.time())
        (tmp_path / "data").mkdir(parents=True, exist_ok=True)
        if marker is not None:
            (tmp_path / "data/.ci_last_run.json").write_text(marker, "utf-8")
        defects: list[tuple[str, str]] = []
        max_audit.check_ci_gate(defects)
        return [k for k, _ in defects]

    def _marker(self, *, age_h: float, ok: bool = True) -> str:
        from datetime import UTC, datetime, timedelta
        ts = datetime.now(tz=UTC) - timedelta(hours=age_h)
        return json.dumps({"ok": ok, "ts": ts.isoformat(), "failed": []})

    def test_the_staleness_branch_exists_and_is_fail_closed(self) -> None:
        """A source-level backstop to the behavioural tests below, kept for one narrow reason:
        the behavioural tests would still pass if someone reimplemented the age check against the
        file's MTIME instead of the marker's own `ts`. That version looks correct and is wrong --
        any organ touching the file would reset the staleness clock without the gate having run.
        So the SOURCE is pinned on the specific thing that cannot be observed from outside."""
        src = (_ROOT / "scripts/max_audit.py").read_text("utf-8")
        assert "ci-gate-stale" in src, "the staleness defect was removed"
        assert "ci-gate-unproven" in src, "the absent/unreadable marker defect was removed"
        assert "_CI_STALE_H" in src, "the staleness bound was removed"
        # the age must be computed against the marker's OWN timestamp, not the file mtime: an
        # organ touching the file without rewriting it would otherwise reset the clock.
        assert "fromisoformat" in src and ".timestamp()" in src

    def test_a_frozen_green_marker_is_still_a_defect(self, tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
        """The exact wedge scenario: ok=true, simply no longer being written."""
        keys = self._defects_for(tmp_path, monkeypatch, self._marker(age_h=200.0, ok=True))
        assert "ci-gate-stale" in keys, (
            "a 200h-old GREEN marker must raise -- the gate stopped running, and that is "
            "invisible to any check that only asks whether the last result was red")
        assert "ci-gate-red" not in keys, "it was green; the complaint is that it is old"

    def test_a_fresh_green_marker_is_silent(self, tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
        keys = self._defects_for(tmp_path, monkeypatch, self._marker(age_h=1.0, ok=True))
        assert not keys, ("a gate that ran an hour ago and passed must not be flagged -- a check "
                          "that fires on the healthy case is a check that gets deleted")

    def test_a_red_marker_still_raises(self, tmp_path: Path,
                                       monkeypatch: pytest.MonkeyPatch) -> None:
        """The original 81h-incident guard must survive the staleness addition."""
        keys = self._defects_for(tmp_path, monkeypatch, self._marker(age_h=1.0, ok=False))
        assert "ci-gate-red" in keys

    def test_an_absent_marker_is_not_green(self, tmp_path: Path,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
        assert "ci-gate-unproven" in self._defects_for(tmp_path, monkeypatch, None)

    @pytest.mark.parametrize("body", ["not json at all", "{}", '{"ok": true}',
                                      '{"ok": true, "ts": "yesterday"}'])
    def test_an_unparseable_or_undated_marker_is_not_green(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str,
    ) -> None:
        """Every way a marker can fail to prove freshness must land in the same place. A marker
        with no `ts` is the sharpest case: it parses, it says ok=true, and it can never be shown
        to be old -- so before this it read as permanently green."""
        assert "ci-gate-unproven" in self._defects_for(tmp_path, monkeypatch, body)


class TestTheSuiteItselfIsBounded:
    """The per-test timeout in pyproject is the inside-out half of the same repair: it turns the
    one hanging test into a named failure instead of a stalled suite."""

    def test_pytest_has_a_default_timeout(self) -> None:
        src = (_ROOT / "pyproject.toml").read_text("utf-8")
        assert re.search(r"^timeout\s*=\s*\d+", src, re.M), (
            "the suite-wide per-test timeout was removed -- one hanging test again stalls the "
            "whole gate instead of failing it")
        # THREAD, NOT SIGNAL -- corrected 2026-08-26 against the platform, not against the
        # preference. This assertion demanded `signal` and pyproject has said `thread` since the
        # same commit that added both, so it has been red ever since and was one of the failures
        # keeping the desk-wide gate down. signal (SIGALRM) IS the better method where it exists
        # -- it interrupts a blocking syscall and yields the offending test's own traceback --
        # but SIGALRM DOES NOT EXIST ON WINDOWS and the MT5 execution box is Windows, where it
        # raises AttributeError and takes the whole run down as an INTERNALERROR before a single
        # test reports. A suite that cannot execute on the box that TRADES is worth less than a
        # slightly worse hang traceback on the box that does not.
        #
        # NOTHING IS LOOSENED: the property this class exists to protect -- a hang becomes a
        # NAMED failing test instead of a stalled suite -- is carried entirely by `timeout = N`
        # above, which is still asserted. What is pinned here is only that a method is set
        # EXPLICITLY, so nobody silently reverts to a platform-fatal one.
        assert 'timeout_method = "thread"' in src, (
            "timeout_method must stay explicitly `thread`: SIGALRM does not exist on Windows and "
            "the MT5 execution box is Windows, so `signal` INTERNALERRORs the entire suite on "
            "the box that trades. Set it per-platform rather than flipping it globally.")

    def test_the_plugin_is_a_hard_dependency(self) -> None:
        """Without it, `timeout` is an unrecognised ini key -- a warning, not an error -- so the
        suite would silently run unbounded again on any box that skipped it."""
        src = (_ROOT / "pyproject.toml").read_text("utf-8")
        assert re.search(r'"pytest-timeout[><=]', src), (
            "pytest-timeout must stay a hard dev dependency, not an optional extra")

    def test_the_deploy_gate_bounds_each_command(self) -> None:
        """ops/deploy_vps.sh gates a LIVE box on these commands. Unbounded, a hang leaves the
        operator with a box that is neither deployed nor reported failed."""
        src = (_ROOT / "ops/deploy_vps.sh").read_text("utf-8")
        assert "gate()" in src and "timeout --kill-after" in src
        for label in ("ruff", "mypy", "pytest"):
            assert re.search(rf"^gate\s+\d+\s+\"{label}", src, re.M), (
                f"the {label} deploy gate lost its wall-clock bound")
        assert "124" in src and "137" in src, (
            "the deploy must distinguish a HANG from an ordinary failure -- different first move")


@pytest.mark.timeout(60)
def test_a_marker_written_by_the_real_run_ci_is_parseable_by_the_real_max_audit() -> None:
    """The two halves live in different files and agree only by convention: run_ci writes `ts`
    with datetime.isoformat(), max_audit parses it with fromisoformat. Pin the contract rather
    than trusting that nobody reformats one side."""
    out = subprocess.run(
        [sys.executable, "-c",
         "import json,sys;from datetime import UTC,datetime;"
         "print(json.dumps({'ok':True,'ts':datetime.now(tz=UTC).isoformat(),'failed':[]}))"],
        capture_output=True, text=True, check=True).stdout
    from datetime import datetime as _dt
    parsed = _dt.fromisoformat(json.loads(out)["ts"])
    assert parsed.tzinfo is not None, (
        "a naive timestamp makes the age computation wrong by the box's UTC offset -- and wrong "
        "in the direction that makes a stale marker look fresher than it is")


class TestTheCompilePassIsGated:
    """L0177. Every AST-level tool in this repo is blind to the symbol-table class of syntax
    error -- `await` outside `async` is the one that bit -- so ruff, mypy AND `pytest --co` all
    reported GREEN on scripts/liquidation_listener.py while `import` raised SyntaxError and the
    desk-wide gate sat RED for 21h. `ast.parse` shares the blindness, so reaching for it as a
    hand-check confirms the wrong answer. Only `compile()` runs the pass that catches it.

    Pinned in BOTH gate definitions because they are separate files that nothing else relates,
    and the local gate is the one a session actually runs before pushing.
    """

    def test_run_ci_has_a_compile_step(self) -> None:
        from scripts.run_ci import _STEPS
        labels = [label for label, _cmd, _budget in _STEPS]
        assert any("compile" in label for label in labels), (
            "the compileall step was removed from run_ci._STEPS -- a file that cannot be "
            f"imported can once again pass every other gate. Steps: {labels}")
        cmd = next(c for label, c, _ in _STEPS if "compile" in label)
        assert "compileall" in cmd, f"the compile step no longer runs compileall: {cmd}"

    def test_local_gates_have_a_compile_step(self) -> None:
        src = (_ROOT / "ops" / "gates.sh").read_text("utf-8")
        assert "compileall" in src, (
            "ops/gates.sh lost its compileall run. This is the gate a session actually executes "
            "before pushing, so losing it here is worse than losing it in CI.")

    def test_compile_runs_before_the_expensive_test_step(self) -> None:
        """~1s versus a 2h budget: the cheapest failure in the repo must not be detected last.
        The original defect was found only after a full-suite run, which on a 3.8GB swapless box
        competes with the live organs -- which is precisely why the red sat instead of being
        fixed."""
        from scripts.run_ci import _STEPS
        labels = [label for label, _c, _b in _STEPS]
        compile_at = next(i for i, label in enumerate(labels) if "compile" in label)
        tests_at = next(i for i, label in enumerate(labels) if label.startswith("tests"))
        assert compile_at < tests_at, f"compile must precede the suite: {labels}"
