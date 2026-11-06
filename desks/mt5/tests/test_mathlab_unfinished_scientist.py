"""A scientist the pass stopped waiting for has an UNMEASURED yield, never a measured zero.

Audit of 1ce440654 (MF2 and SF5-SF7): the TIMED_OUT row used to read evaluated 0, compute_s 0.0
and nothing unmeasured, so the report showed a clean empty pass and `record_registry` wrote
generated=0 at no cost into generator_yield. These pin the reason in `unmeasured`, a measured
wall clock, no yield write, the deadline reaching the scientist, and the hard exit firing even
when the pass raised.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
import time
import types
from pathlib import Path
from typing import Any

import pytest

_DESK = str(Path(__file__).resolve().parents[1])
if _DESK not in sys.path:
    sys.path.insert(0, _DESK)

from research import math_lab as ML  # noqa: E402


def test_unfinished_row_names_why_and_measures_the_wall_clock() -> None:
    started = time.monotonic() - 2.0
    row = ML.unfinished_row(started, "TIMED_OUT", "still running", tradition="topology")
    assert row["tradition"] == "topology" and row["status"] == "TIMED_OUT"
    assert row["unmeasured"] == ["TIMED_OUT: still running"]
    assert row["compute_s"] >= 2.0 and "upper bound" in row["compute_basis"]
    assert row["yield_measured"] is False


def test_an_unmeasured_yield_is_never_written_to_generator_yield(
        monkeypatch: pytest.MonkeyPatch) -> None:
    writes: list[str] = []
    fake = types.SimpleNamespace(
        connect=lambda: types.SimpleNamespace(commit=lambda: None, close=lambda: None),
        generator_yield_update=lambda gen, **kw: writes.append(gen))
    import libs.moat
    monkeypatch.setattr(libs.moat, "registry", fake, raising=False)
    monkeypatch.setitem(sys.modules, "libs.moat.registry", fake)
    monkeypatch.setattr(ML.B, "record_trials", lambda *a, **k: {}, raising=False)
    out = ML.record_registry([], {
        "topology": {"proposed": 0, "yield_measured": False, "status": "TIMED_OUT"},
        "algebra": {"proposed": 3, "compute_s": 1.5},
    }, {})
    assert writes == ["math:algebra"]
    assert out["generator_yield_skipped"] == [{"generator": "math:topology",
                                               "status": "TIMED_OUT"}]


def test_a_panel_past_the_deadline_is_not_started(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[float] = []

    class Sci:
        def __init__(self) -> None:
            self.evaluated = 0
            self.distinct: set[str] = set()
            self.unmeasured: list[str] = []
            self.minted: list[str] = []

        def propose(self, view: Any, budget: float, rng: Any) -> list[Any]:
            calls.append(budget)
            return []

    monkeypatch.setattr(ML.S, "build", lambda t, **k: Sci())
    monkeypatch.setattr(ML, "_copy_panel", lambda p: p)
    panel = types.SimpleNamespace(target="EURUSD")
    late = ML._run_tradition("algebra", [panel], 100.0, {}, {}, time.monotonic() - 1)
    assert calls == [] and late["unmeasured"] == [
        "panel EURUSD: not started before the science deadline"]
    ML._run_tradition("algebra", [panel], 100.0, {}, {}, time.monotonic() + 5)
    assert calls and calls[0] <= 5.0                  # never more than the time left


def test_the_hard_exit_fires_even_when_the_pass_raised() -> None:
    script = textwrap.dedent(f"""
        import sys, threading, time
        sys.path.insert(0, {_DESK!r})
        from research import math_lab as ML
        threading.Thread(target=time.sleep, args=(60,)).start()   # non-daemon, abandoned
        ML.ABANDONED_THREADS = 1
        def body():
            raise RuntimeError("judge blew up")
        ML.run_then_exit(body)
    """)
    t0 = time.monotonic()
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                          timeout=50, cwd=str(Path(_DESK).parents[1]))
    assert time.monotonic() - t0 < 45                 # did not wait for the 60 s thread
    assert proc.returncode == 1
    assert "judge blew up" in proc.stderr             # the failure is still read as one
