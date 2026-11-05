"""THE BOX MEASURE HAS ITS OWN CLOCK (2026-11-05). The 01:44Z and 02:45Z passes on the box entered
`measure_box` and never left it, and JUDGING_RATE.json went 2.1 h stale while the judge kept
judging. The measure now runs in a child that is killed at `MEASURE_BOX_TIMEOUT_S`; the pass goes
on with the process-free box, names the stage the child hung in, and still publishes the rate."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from test_judging_rate_attempt import box  # noqa: E402,F401  (the tmp_path desk fixture)

from research import judging_throughput as jt  # noqa: E402


def test_the_child_returns_the_real_box() -> None:
    got = jt.measure_box_bounded(timeout_s=60.0)
    assert got["box_source"] == "child", got.get("box_timeout")
    assert got["cores"] >= 1 and "terminal_running" in got and "is_judging_box" in got


def test_a_hung_child_is_killed_and_names_its_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    def hang(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw["timeout"], output=b"",
                                        stderr=b"MEASURE_BOX_STAGE memory\nMEASURE_BOX_STAGE cpu\n")
    monkeypatch.setattr(jt.subprocess, "run", hang)
    got = jt.measure_box_bounded(timeout_s=5.0)
    assert got["box_source"] == "fallback"
    assert got["box_timeout"]["stage"] == "cpu"
    assert got["terminal_running"] == jt.UNMEASURED and got["cpu_source"] == jt.UNMEASURED
    assert got["cores"] >= 1 and "free_phys_mb" in got


def test_a_failed_child_falls_back_with_its_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jt.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(
        cmd, 3, stdout="", stderr="MEASURE_BOX_STAGE terminal\nboom"))
    got = jt.measure_box_bounded()
    assert got["box_source"] == "fallback" and got["box_timeout"]["stage"] == "terminal"
    assert "exited 3" in got["box_timeout"]["why"]


def test_an_unmeasured_terminal_stands_down_to_the_baseline_never_below() -> None:
    fb = jt._box_without_processes(None, "UNMEASURED: test")
    fb["market_closed"] = False
    decision = jt.plan(fb, {"status": jt.UNMEASURED}, jt.declared_costs())
    base = jt.sealed_baseline(fb, jt.declared_costs())
    assert decision["workers"] >= int(base["workers"])


def test_the_rate_is_published_when_the_box_measure_hangs(
        box: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    monkeypatch.setattr(jt, "measure_box", jt._MEASURE_BOX)        # the real, bounded path
    monkeypatch.setattr(jt, "MEASURE_BOX_TIMEOUT_S", 5.0)

    def hang(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw["timeout"], stderr=b"MEASURE_BOX_STAGE terminal\n")
    monkeypatch.setattr(jt.subprocess, "run", hang)
    payload = jt.run(write=True, apply=False)
    assert payload["box"]["box_timeout"]["stage"] == "terminal"
    rate = json.loads(jt.RATE_OUT.read_text("utf-8"))
    assert rate.get("at")
