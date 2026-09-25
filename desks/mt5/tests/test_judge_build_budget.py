"""The judge's FIRST-TIME build budget comes from its own task's limit, and only ever grows.

MEASURED ON THE TRADING BOX 2026-09-24. The sealed gauntlet gives `_prewarm_cache` the SAME
deadline as the build loop (`_build_t0 + FRESH_BUILD_BUDGET_SEC`), so once the docket outgrew the
budget the warm consumed all of it:

    PRE-WARM: 15 worker(s) warmed 13993 cell(s) in 2874s (13927 already cached, 745 failed,
              67910 not reached before the build budget)

2,874 seconds spent against a 2,700-second budget, on a docket of 250,992 cells, with a quarter of
it never built. `MT5-Gauntlet` itself carries `ExecutionTimeLimit=PT4H`, so the sweep was stopping
itself at 19% of the wall clock its own scheduler was willing to give it.

Nothing about the judge's evaluation changes -- `external_gauntlet.py` is sealed and is not
touched. Only how long it is given, which is the same principle on which its cycle cap went from
720 s to 3,000 s. These tests pin that the figure is READ off the box, floored at the sealed
default so it can never shrink, and silently absent when the box cannot be read.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK / "research"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import judging_throughput as jt  # noqa: E402


def test_the_budget_is_a_share_of_the_tasks_own_limit() -> None:
    want, why = jt.fresh_budget_s(4 * 3600.0)
    assert want == pytest.approx(4 * 3600.0 * jt.FRESH_BUDGET_SHARE_OF_LIMIT)
    assert want > jt.SEALED_FRESH_BUDGET_SEC
    assert "ExecutionTimeLimit" in why and "gate phase" in why


def test_an_unreadable_limit_leaves_the_sealed_default_alone() -> None:
    """L1.28a: a limit nobody could read is an absence, never a number invented here."""
    want, why = jt.fresh_budget_s(None)
    assert want is None
    assert "unreadable" in why


def test_the_budget_never_falls_below_the_sealed_default() -> None:
    """ONE WAY. A short task limit must not make the judge build for less time than it does now."""
    for limit in (60.0, 600.0, jt.SEALED_FRESH_BUDGET_SEC, 4000.0):
        want, _ = jt.fresh_budget_s(limit)
        assert want is None or want >= jt.SEALED_FRESH_BUDGET_SEC


def test_the_env_carries_the_budget_only_when_it_is_a_raise() -> None:
    base = {"workers": 15, "memory_budget_mb": 11520, "headroom_cap_mb": 11520,
            "per_worker_mb": 768, "warm_workers": 1}
    assert "GAUNTLET_FRESH_BUDGET_SEC" not in jt.env_for(base)
    assert "GAUNTLET_FRESH_BUDGET_SEC" not in jt.env_for({**base, "fresh_budget_s": None})
    assert "GAUNTLET_FRESH_BUDGET_SEC" not in jt.env_for(
        {**base, "fresh_budget_s": jt.SEALED_FRESH_BUDGET_SEC})
    env = jt.env_for({**base, "fresh_budget_s": 8640.0})
    assert env["GAUNTLET_FRESH_BUDGET_SEC"] == "8640"
    assert "GAUNTLET_FRESH_BUDGET_SEC" in jt.ENV_KEYS


def test_the_sealed_default_matches_the_sealed_file() -> None:
    """If the sealed file's own default moves, this floor must be re-read, not assumed."""
    src = (_DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")
    assert 'os.environ.get("GAUNTLET_FRESH_BUDGET_SEC", "2700")' in src
    assert jt.SEALED_FRESH_BUDGET_SEC == 2700.0


def test_the_task_limit_parser_reads_the_schedulers_own_xml(
        monkeypatch: pytest.MonkeyPatch) -> None:
    class _Proc:
        returncode = 0
        stdout = "<Settings>\n<ExecutionTimeLimit>PT4H</ExecutionTimeLimit>\n</Settings>"
        stderr = ""

    monkeypatch.setattr(jt.sys, "platform", "win32")
    monkeypatch.setattr(jt.subprocess, "run", lambda *a, **k: _Proc())
    assert jt.task_time_limit_s() == pytest.approx(14_400.0)

    class _Empty(_Proc):
        stdout = "<Settings></Settings>"

    monkeypatch.setattr(jt.subprocess, "run", lambda *a, **k: _Empty())
    assert jt.task_time_limit_s() is None


def test_the_cadence_call_pushes_the_window_out_as_well_as_the_interval() -> None:
    """The defect of 2026-09-24: /RI set the interval onto a trigger whose window had closed."""
    src = (_DESK / "research" / "judging_throughput.py").read_text("utf-8")
    assert '"/DU", CADENCE_DURATION' in src
    assert jt.CADENCE_DURATION == "9999:59"
    assert "next_run_after" in src
