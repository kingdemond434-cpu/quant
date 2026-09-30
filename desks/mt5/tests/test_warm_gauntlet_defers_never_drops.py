"""THE WARMER SCHEDULES; IT NEVER DROPS.

`warm_gauntlet_cache` decides which cells are CHEAP for the next sweep, and a cell it never warms
is a cell a bounded sweep will not reach. That makes its skip logic as consequential as an
ordering, so the same rule binds it: every cell is accounted for on every pass. A cell whose
build has failed is DEFERRED -- named in `data/hypotheses/warm_deferrals.json` with the age of its
first failure -- and retried the moment its bars change, because a missing parquet arriving is
exactly the event that makes the build succeed. Nothing is queued invisibly and nothing is
dropped.

These tests also pin the two identity corrections, because both were silent: the row-level
`timeframe` fold (a docket row that names its chart outside `params` must not collapse into the
H1 cell of the same name) and the retry-on-changed-bars rule.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK / "scripts"), str(_DESK / "research"), str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import warm_gauntlet_cache as W  # noqa: E402


def _cells(n: int) -> list[dict]:
    return [{"sym": f"S{i}", "family": "carry", "tf": "H1", "params": {},
             "ckey": f"key{i}"} for i in range(n)]


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(W, "DEFERRALS", tmp_path / "warm_deferrals.json")
    monkeypatch.setattr(W, "LASTDAY", tmp_path / "warm_last_day.json")
    monkeypatch.setattr(W, "REPORT", tmp_path / "WARM_GAUNTLET.json")


def test_every_cell_is_accounted_for(tmp_path: Path) -> None:
    """send + held == the input, exactly. No cell may vanish between them."""
    cells = _cells(20)
    now = time.time()
    W.DEFERRALS.write_text(json.dumps({"rows": {
        f"key{i}": {"first_failed_at": now - 60, "last_failed_at": now - 60,
                    "n_failures": 1, "bars": "stamp", "why": "failed"}
        for i in range(5)}}), encoding="utf-8")
    stamps = {f"S{i}|H1": "stamp" for i in range(20)}
    send, held, _rows = W.split_deferred(cells, stamps, now)
    assert len(send) + len(held) == len(cells)
    assert sorted(c["ckey"] for c in send + held) == sorted(c["ckey"] for c in cells)


def test_a_deferred_cell_is_retried_the_moment_its_bars_change(tmp_path: Path) -> None:
    now = time.time()
    W.DEFERRALS.write_text(json.dumps({"rows": {
        "key0": {"first_failed_at": now - 60, "last_failed_at": now - 60,
                 "n_failures": 3, "bars": "OLD", "why": "missing"}}}), encoding="utf-8")
    cells = _cells(1)
    held_stamps = {"S0|H1": "OLD"}
    send, held, _ = W.split_deferred(cells, held_stamps, now)
    assert held and not send, "unchanged bars: the cell waits out its retry window"
    moved_stamps = {"S0|H1": "NEW"}
    send, held, _ = W.split_deferred(cells, moved_stamps, now)
    assert send and not held, "bars changed: the build might now succeed, so retry NOW"


def test_a_deferred_cell_is_retried_after_the_retry_window(tmp_path: Path) -> None:
    now = time.time()
    W.DEFERRALS.write_text(json.dumps({"rows": {
        "key0": {"first_failed_at": now - W.RETRY_SEC - 10,
                 "last_failed_at": now - W.RETRY_SEC - 10,
                 "n_failures": 9, "bars": "SAME", "why": "failed"}}}), encoding="utf-8")
    send, held, _ = W.split_deferred(_cells(1), {"S0|H1": "SAME"}, now)
    assert send and not held


def test_retries_go_first(tmp_path: Path) -> None:
    """Leftovers lead the next pass: the oldest unresolved work is at the front."""
    now = time.time()
    W.DEFERRALS.write_text(json.dumps({"rows": {
        "key9": {"first_failed_at": now - 60, "last_failed_at": now - 60,
                 "n_failures": 1, "bars": "OLD", "why": "failed"}}}), encoding="utf-8")
    send, _held, _ = W.split_deferred(_cells(10), {f"S{i}|H1": "NEW" for i in range(10)}, now)
    assert send[0]["ckey"] == "key9"


def test_the_deferral_ledger_publishes_ages(tmp_path: Path) -> None:
    now = time.time()
    rows = {"key0": {"first_failed_at": now - 7200, "last_failed_at": now,
                     "n_failures": 2, "bars": "s", "why": "failed"}}
    census = W.publish_deferrals(rows, [], now, {})
    assert census["n_deferred"] == 1
    assert census["oldest_hours"] == pytest.approx(2.0, abs=0.05)
    assert "NOTHING IS DROPPED" in census["rule"]
    doc = json.loads(W.DEFERRALS.read_text("utf-8"))
    assert doc["rows"]["key0"]["n_failures"] == 2


def test_an_empty_ledger_defers_nothing(tmp_path: Path) -> None:
    send, held, rows = W.split_deferred(_cells(6), {}, time.time())
    assert len(send) == 6 and held == [] and rows == {}


def test_the_row_level_timeframe_is_folded_into_the_cell_identity() -> None:
    """A docket row naming M15 outside `params` must not collapse into the H1 cell of the same
    name. `external_gauntlet.main` folds it; this job must fold it identically or it warms a
    key the sweep never looks up."""
    class _G:
        HYP = Path(__file__).resolve().parents[1] / "data" / "hypotheses"

        @staticmethod
        def partition_at_economic_prior(specs, meta=None):  # type: ignore[no-untyped-def]
            return specs, []

        @staticmethod
        def timeframe_of(params, family):  # type: ignore[no-untyped-def]
            return str((params or {}).get("timeframe") or "H1").upper()

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        hyp = Path(td)
        (hyp / "external_survivors.json").write_text(json.dumps([
            {"symbol": "EURUSD", "family": "carry", "params": {}},
            {"symbol": "EURUSD", "family": "carry", "params": {}, "timeframe": "M15"},
        ]), encoding="utf-8")
        _G.HYP = hyp
        out = W.docket_specs(_G, {})
    assert len(out) == 2, "the M15 row must be its own cell, not a duplicate of the H1 one"
    assert sorted(s["tf"] for s in out) == ["H1", "M15"]


def test_workers_come_from_the_judges_own_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """ONE BUILDER for the worker arithmetic. The override still wins; an unreadable judge
    falls back to the historic figure rather than to unlimited."""
    monkeypatch.setenv("WARM_WORKERS", "7")
    assert W._workers() == 7
    monkeypatch.delenv("WARM_WORKERS")
    assert W._workers() >= 1
