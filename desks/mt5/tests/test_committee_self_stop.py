"""MR7 (2026-11-11): the committee legs timed out every hour and wrote nothing, and the runner
threw the child's output away, so their runtime could never be measured. These pin the fix:
an overrunning call is abandoned inside the pass, a committee the pass cannot reach is
DEFERRED_BUDGET (UNMEASURED, never a clean zero), and a timeout keeps the child's log tail."""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import committee_ensembles as ens  # noqa: E402
import committees as cm  # noqa: E402
import hourly_cycle as hc  # noqa: E402

from libs.research import committee_engine as ce  # noqa: E402


def test_a_bounded_call_that_overruns_is_abandoned_and_one_that_returns_is_kept():
    gate = threading.Event()
    t0 = time.monotonic()
    for mod in (ens, cm):
        assert mod._bounded(lambda: 7, 5.0) == (True, 7)
        done, value = mod._bounded(lambda: gate.wait(30), 0.2)
        assert (done, value) == (False, None)
    assert time.monotonic() - t0 < 5.0
    gate.set()


def test_a_bounded_call_re_raises_its_own_error():
    def boom() -> None:
        raise ValueError("seat")
    for mod in (ens, cm):
        try:
            mod._bounded(boom, 5.0)
        except ValueError as exc:
            assert str(exc) == "seat"
        else:
            raise AssertionError("the call's error was swallowed")


def test_a_committee_whose_pool_overruns_is_deferred_unmeasured_not_zero(monkeypatch):
    gate = threading.Event()
    monkeypatch.setattr(ens, "_committee_pool", lambda *a, **k: gate.wait(30) or [])
    monkeypatch.setattr(ens, "_PASS_STOP_AT", [time.monotonic() + 0.2])
    try:
        ens._run_committee(ens.SCIENTIFIC, None, None, [], {}, 5.0, time.time(), None)
    except ens._PoolOverran:
        pass
    else:
        raise AssertionError("an overrunning pool load was not reported")
    finally:
        gate.set()
    row = {"status": "DEFERRED_BUDGET", "why": "its subject pool did not load"}
    doc = ens.health_doc(ce.blank_state(), {}, {}, {}, {ens.SCIENTIFIC: row})
    verdict = doc["committees"][ens.SCIENTIFIC]
    assert verdict["verdict"] == ens.UNMEASURED and verdict["why"] == row["why"]
    assert doc["all_healthy"] is not True


def test_the_timeout_tail_survives_bytes_text_and_none():
    assert hc._text_tail(None, 10) == ""
    assert hc._text_tail(b"PHASE start +0.0s\n", 6) == "+0.0s\n"
    assert hc._text_tail("x" * 50, 5) == "xxxxx"
    leaked = hc._text_tail("PHASE start\nkey=sk-or-v1-" + "a" * 48 + "\n", 400)
    assert "a" * 48 not in leaked and "PHASE start" in leaked
