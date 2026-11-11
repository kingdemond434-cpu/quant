"""Every job lock carries a lease; a living holder past it checkpoints and yields (idea 614).

Measured the night of 2026-11-10/11: heavy pf_allocator held its lock 3 h 18 m, research_bandit
ran 6 h 20 m, TapeFeatures was killed by its task limit every hour and the gauntlet pre-warm ran
2.6 h against a 45 min budget. Every holder was alive and beating, so no waiter could (or may)
reclaim it. The lease is the holder's own signal to hand back; a waiter still never robs it.
"""
from __future__ import annotations

import ast
import json
import socket
import sys
import textwrap
import time
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import job_lock as JL  # noqa: E402


@pytest.fixture
def locks(tmp_path, monkeypatch):
    monkeypatch.setattr(JL, "LOCK_ROOT", tmp_path)
    monkeypatch.setattr(JL, "record_spec", lambda *a, **k: None)
    monkeypatch.setattr(JL, "peak_rss_mb", lambda: None)
    for k in ("JOB_LOCK_MAX_HOLD_S", "JOB_LOCK_MAX_HOLD_S_DEMO"):
        monkeypatch.delenv(k, raising=False)
    return tmp_path


def test_every_lock_records_its_lease(locks) -> None:
    with JL.exclusive_job("demo") as go:
        assert go
        row = json.loads((locks / "demo.json").read_text("utf-8"))
        assert row["max_hold_s"] == JL.DEFAULT_MAX_HOLD_S
        assert row["lease_until"] == pytest.approx(row["heartbeat_at"] + JL.DEFAULT_MAX_HOLD_S)
        assert JL.lease_left_s("demo") == pytest.approx(JL.DEFAULT_MAX_HOLD_S, abs=5)
    assert JL.lease_left_s("demo") is None


def test_lease_precedence(monkeypatch) -> None:
    monkeypatch.delenv("JOB_LOCK_MAX_HOLD_S", raising=False)
    monkeypatch.delenv("JOB_LOCK_MAX_HOLD_S_TAPE_FEATURES", raising=False)
    assert JL.max_hold_s("tape_features") == 50 * 60
    assert JL.max_hold_s("tape_features", 600) == 600            # the caller's declaration
    monkeypatch.setenv("JOB_LOCK_MAX_HOLD_S_TAPE_FEATURES", "120")
    assert JL.max_hold_s("tape_features", 600) == 120            # the per-job env wins
    monkeypatch.setenv("JOB_LOCK_MAX_HOLD_S", "900")
    assert JL.max_hold_s("other") == 900
    assert JL.max_hold_s("other", -5) == 900                     # never zero or negative
    monkeypatch.setenv("JOB_LOCK_MAX_HOLD_S", "nonsense")
    assert JL.max_hold_s("other") == JL.DEFAULT_MAX_HOLD_S


def test_checkpoint_says_yield_only_once_the_lease_is_spent(locks, capsys) -> None:
    assert JL.checkpoint("demo") is False                        # holds nothing: never yields
    with JL.exclusive_job("demo", max_hold=3600) as go:
        assert go and JL.checkpoint("demo") is False
        JL._LEASE_UNTIL["demo"] = time.time() - 1
        assert JL.checkpoint("demo") is True
        assert JL.checkpoint("demo") is True
    assert capsys.readouterr().out.count("LEASE SPENT") == 1     # said once, not every stage


def test_a_living_holder_past_its_lease_is_named_never_robbed(locks, monkeypatch) -> None:
    path = locks / "demo.json"
    path.write_text(json.dumps({
        "token": "held", "pid": 4242, "host": socket.gethostname(),
        "started_at": "2026-11-11T00:00:00+00:00", "heartbeat_at": time.time(),
        "max_hold_s": 3600, "lease_until": time.time() - 1800}), "utf-8")
    monkeypatch.setattr(JL, "_owner_state", lambda p: "ALIVE")
    with JL.exclusive_job("demo", heartbeat_stale_s=3600) as go:
        assert go is False
    assert JL.LAST_REFUSAL["demo"]["over_lease_s"] >= 1800
    assert json.loads(path.read_text("utf-8"))["pid"] == 4242   # still the holder's lock
    over = JL.lease_overruns(locks)
    assert [o["name"] for o in over] == ["demo"] and over[0]["pid"] == 4242


def test_a_holder_inside_its_lease_is_not_listed(locks) -> None:
    with JL.exclusive_job("demo"):
        assert JL.lease_overruns(locks) == []


def test_old_locks_without_a_lease_are_untouched_by_it(locks, monkeypatch) -> None:
    (locks / "demo.json").write_text(json.dumps({
        "token": "held", "pid": 4242, "host": socket.gethostname(),
        "started_at": "2026-11-11T00:00:00+00:00", "heartbeat_at": time.time()}), "utf-8")
    monkeypatch.setattr(JL, "_owner_state", lambda p: "ALIVE")
    with JL.exclusive_job("demo") as go:
        assert go is False
    assert "over_lease_s" not in JL.LAST_REFUSAL["demo"]
    assert JL.lease_overruns(locks) == []


# ------------------------------------------------------------------ tape_features yields
def test_tape_features_wires_its_lease() -> None:
    src = (_DESK / "recorders" / "tape_features.py").read_text("utf-8")
    assert 'should_yield=lambda: checkpoint("tape_features")' in src
    assert "DEFERRED, lease spent" in src and '"yielded_at_lease": yielded' in src


# ------------------------------------------------------------------ the pre-warm drain is bounded
_EG = (_DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")


def _fn(name: str) -> str:
    tree = ast.parse(_EG)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return textwrap.dedent(ast.get_source_segment(_EG, node))
    raise AssertionError(name)


def _slow_cell(spec: dict, meta: dict) -> dict:
    time.sleep(float(spec["sleep"]))
    return {"status": "WARMED"}


def _prewarm_ns(lease_spent=lambda: False) -> dict:
    import contextlib
    import os
    from typing import Any
    ns: dict = {"time": time, "os": os, "contextlib": contextlib, "Any": Any,
                "WORKERS": 2, "PREWARM_DRAIN_GRACE_S": 1.0, "_warm_one": _slow_cell,
                "_lease_spent": lease_spent}
    exec(_fn("_abandon_pool"), ns)
    exec(_fn("_prewarm_cache"), ns)
    return ns


def test_prewarm_abandons_stragglers_after_the_grace() -> None:
    ns = _prewarm_ns()
    specs = [{"sym": "A", "sleep": 0.0}, {"sym": "B", "sleep": 120.0}, {"sym": "C", "sleep": 120.0}]
    t0 = time.time()
    out = ns["_prewarm_cache"](specs, {}, time.time() + 1.0)
    assert time.time() - t0 < 30, "the pre-warm waited on its stragglers"
    assert out["stop"] == "deadline" and out["abandoned"] >= 1
    assert out["warmed"] == 1


def test_prewarm_stops_at_the_lease() -> None:
    ns = _prewarm_ns(lease_spent=lambda: True)
    specs = [{"sym": "A", "sleep": 120.0}] * 4
    t0 = time.time()
    out = ns["_prewarm_cache"](specs, {}, time.time() + 3600)
    assert time.time() - t0 < 30
    assert out["stop"] == "lease" and out["abandoned"] >= 1


def test_prewarm_inside_budget_is_unchanged() -> None:
    ns = _prewarm_ns()
    out = ns["_prewarm_cache"]([{"sym": s, "sleep": 0.0} for s in "ABC"], {}, time.time() + 60)
    assert out["warmed"] == 3 and out["abandoned"] == 0 and out["stop"] is None
