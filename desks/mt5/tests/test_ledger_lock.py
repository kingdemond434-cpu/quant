"""Invariant I1: no writer of a forward ledger drops a clock another writer opened.

Every writer of shadow_state.json / scalp_shadow_state.json / qquant_shadow_state.json goes
through `ledger_lock` (or `shadow_forward.state_lock`, the same lock): a fresh read-modify-write
under the lock (`update`) or a three-way merge against the writer's own snapshot
(`merge_write`). These pin that two interleaved writers both keep their clocks.
"""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(DESK))

import clock_coverage  # noqa: E402
import ledger_lock  # noqa: E402
import shadow_forward  # noqa: E402


def _doc(p: Path) -> dict:
    return json.loads(p.read_text("utf-8"))


def _clock(n: int = 0) -> dict:
    return {"status": "ACTIVE", "n": n}


def test_a_stale_writer_merges_and_never_drops_a_clock_opened_after_its_read(tmp_path) -> None:
    p = tmp_path / "shadow_state.json"
    p.write_text(json.dumps({"AUDUSD.asia": _clock(5), "EURUSD.asia": _clock(1)}), "utf-8")
    # WRITER A (the reconciler, say) reads, then works for a while ...
    a = json.loads(p.read_text("utf-8"))
    base = ledger_lock.snapshot(a)
    # ... WRITER B (the certification transaction) opens a clock meanwhile ...
    ledger_lock.update(p, lambda d: d.setdefault("GBPUSD.asia", _clock()) is not None)
    # ... and A writes what it changed: one row retired, one row removed.
    a["AUDUSD.asia"]["status"] = "RETIRED_ORPHAN"
    del a["EURUSD.asia"]
    ledger_lock.merge_write(p, base, a)
    doc = _doc(p)
    assert "GBPUSD.asia" in doc, "the clock B opened was dropped by A's stale write"
    assert doc["AUDUSD.asia"]["status"] == "RETIRED_ORPHAN" and doc["AUDUSD.asia"]["n"] == 5
    assert "EURUSD.asia" not in doc, "A's own removal was not applied"


def test_nested_scalp_sleeves_merge_one_level_in(tmp_path) -> None:
    p = tmp_path / "scalp_shadow_state.json"
    p.write_text(json.dumps({"sleeves": {"s1": _clock(2)}}), "utf-8")
    a = json.loads(p.read_text("utf-8"))
    base = ledger_lock.snapshot(a)
    ledger_lock.update(p, lambda d: d["sleeves"].setdefault("s2", _clock()) is not None)
    a["sleeves"]["s1"]["n"] = 3
    ledger_lock.merge_write(p, base, a)
    assert set(_doc(p)["sleeves"]) == {"s1", "s2"} and _doc(p)["sleeves"]["s1"]["n"] == 3


def test_two_writers_interleaving_in_threads_both_keep_every_clock(tmp_path) -> None:
    p = tmp_path / "shadow_state.json"
    p.write_text("{}", "utf-8")
    start = threading.Barrier(2)

    def writer(prefix: str) -> None:
        start.wait()
        for i in range(40):
            if i % 2:
                ledger_lock.update(p, lambda d, k=f"{prefix}{i}": d.setdefault(k, _clock()))
            else:
                base = ledger_lock.read(p) or {}
                after = {**ledger_lock.snapshot(base), f"{prefix}{i}": _clock()}
                ledger_lock.merge_write(p, base, after)

    threads = [threading.Thread(target=writer, args=(x,)) for x in ("A", "B")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    keys = set(_doc(p))
    want = {f"{x}{i}" for x in "AB" for i in range(40)}
    assert want <= keys, f"lost updates: {sorted(want - keys)}"
    assert not list(tmp_path.glob(".*.lock")), "a lock outlived its writer"


def test_the_engine_pass_and_the_certification_transaction_interleave_safely(
        tmp_path, monkeypatch) -> None:
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    monkeypatch.setattr(shadow_forward, "SHADOW_DIR", shadow)
    monkeypatch.setattr(shadow_forward, "slog", lambda *a: None)
    p = shadow / "shadow_state.json"
    p.write_text(json.dumps({"AUDUSD.asia": _clock(1)}), "utf-8")
    # the engine pass reads its working copy ...
    state = shadow_forward._TouchedState(shadow_forward._read_state(p) or {})
    # ... the certification transaction opens a clock while the pass replays ...
    rows = [("EURUSD", "asia", dict(shadow_forward.WINDOWS["asia"]), "session_range_breakout",
             "LONG")]
    assert clock_coverage.backfill(10, rows=rows, state_path=p)["opened"] == 1
    # ... and the pass persists the row it evaluated.
    state["AUDUSD.asia"] = _clock(2)
    shadow_forward._persist_state(p, state, final=True)
    doc = _doc(p)
    assert doc["AUDUSD.asia"]["n"] == 2 and "EURUSD.asia" in doc, doc


def test_an_unreadable_ledger_is_never_overwritten_by_update(tmp_path) -> None:
    p = tmp_path / "shadow_state.json"
    p.write_text("{torn", "utf-8")
    assert ledger_lock.update(p, lambda d: True) is None
    assert p.read_text("utf-8") == "{torn"


def test_a_dead_writers_lock_is_broken(tmp_path) -> None:
    import os
    import time
    p = tmp_path / "shadow_state.json"
    p.write_text("{}", "utf-8")
    lock = tmp_path / ".shadow_state.json.lock"
    lock.write_text("999999 then", "utf-8")
    old = time.time() - 3600
    os.utime(lock, (old, old))
    with ledger_lock.state_lock(p, timeout_s=1.0) as got:
        assert got, "a stale lock from a dead writer was not broken"
