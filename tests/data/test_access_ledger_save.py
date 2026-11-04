"""The shared access ledger (world_crawler_access.json) is never overwritten blind (audit HOLD on
06cab1824, MUST-FIX 2).

An unreadable ledger used to read as {} and the next save wrote only this process's holds over
it, dropping every other process's person-held 401/403/429 hold. Now a corrupt ledger is moved
aside (kept) and the save is refused and recorded; saves are serialised by a lock file; the tmp
name carries the pid.
"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
from pathlib import Path

from libs.data import polite_fetch as pf


def _hold(path: Path, site: str) -> None:
    acc = pf.HostAccess.load(path)
    acc.block(f"https://{site}/x", 403)


def test_corrupt_ledger_is_preserved_and_not_overwritten(tmp_path: Path) -> None:
    led = tmp_path / "world_crawler_access.json"
    bad = '{"blocked": {"other.example": {"verdict": "HTTP_403"'      # truncated JSON
    led.write_text(bad, encoding="utf-8")
    acc = pf.HostAccess.load(led)
    acc.blocked["mine.example"] = {"verdict": "HTTP_403", "released_by": None}
    assert acc.save() is False
    aside = sorted(tmp_path.glob("world_crawler_access.json.corrupt.*"))
    assert len(aside) == 1 and aside[0].read_text("utf-8") == bad          # kept, byte for byte
    assert str(os.getpid()) in aside[0].name
    assert not led.exists()                                                # never overwritten
    assert acc.save_refusals and "corrupt" in acc.save_refusals[-1]["why"]
    rec = (tmp_path / "world_crawler_access.json.save_refusals.jsonl").read_text("utf-8")
    assert "mine.example" in rec


def test_invalid_utf8_ledger_is_corrupt_and_quarantined(tmp_path: Path) -> None:
    led = tmp_path / "a.json"
    bad = b'{"blocked": {"o.example": {"verdict": "\xff\xfe HTTP_403"}}}'
    led.write_bytes(bad)
    acc = pf.HostAccess.load(led)                      # a read never raises
    acc.blocked["mine.example"] = {"verdict": "HTTP_403"}
    assert acc.save() is False
    (aside,) = tmp_path.glob("a.json.corrupt.*")
    assert aside.read_bytes() == bad and not led.exists()
    assert "UnicodeDecodeError" in acc.save_refusals[-1]["why"]


def test_non_object_ledger_is_corrupt_too(tmp_path: Path) -> None:
    led = tmp_path / "a.json"
    led.write_text("[1, 2]", encoding="utf-8")
    acc = pf.HostAccess.load(led)
    assert acc.save() is False
    assert list(tmp_path.glob("a.json.corrupt.*"))


def test_unreadable_ledger_is_left_in_place_and_not_overwritten(tmp_path: Path,
                                                                 monkeypatch) -> None:
    led = tmp_path / "a.json"
    led.write_text(json.dumps({"blocked": {"o.example": {"verdict": "HTTP_429"}}}), "utf-8")
    acc = pf.HostAccess(led)
    real = Path.read_bytes

    def boom(self: Path) -> bytes:
        if self == led:
            raise PermissionError("share violation")
        return real(self)
    monkeypatch.setattr(Path, "read_bytes", boom)
    assert acc.save() is False
    monkeypatch.setattr(Path, "read_bytes", real)
    assert "o.example" in json.loads(led.read_text("utf-8"))["blocked"]
    assert not list(tmp_path.glob("a.json.corrupt.*"))


def test_lock_timeout_refuses_and_does_not_overwrite(tmp_path: Path, monkeypatch) -> None:
    led = tmp_path / "a.json"
    led.write_text(json.dumps({"blocked": {}}), "utf-8")
    before = led.read_text("utf-8")
    (tmp_path / "a.json.lock").write_text("999 0", "utf-8")              # a live writer's lock
    monkeypatch.setattr(pf, "SAVE_LOCK_WAIT_S", 0.1)
    acc = pf.HostAccess(led)
    acc.blocked["mine.example"] = {"verdict": "HTTP_403"}
    assert acc.save() is False
    assert led.read_text("utf-8") == before
    assert "lock" in acc.save_refusals[-1]["why"]


def test_stale_lock_is_broken(tmp_path: Path) -> None:
    led = tmp_path / "a.json"
    lock = tmp_path / "a.json.lock"
    lock.write_text("1 0", "utf-8")
    old = os.path.getmtime(lock) - pf.SAVE_LOCK_STALE_S - 5
    os.utime(lock, (old, old))
    acc = pf.HostAccess(led)
    acc.blocked["mine.example"] = {"verdict": "HTTP_403"}
    assert acc.save() is True
    assert not lock.exists()


def test_two_concurrent_savers_keep_both_holds(tmp_path: Path) -> None:
    led = tmp_path / "world_crawler_access.json"
    ctx = mp.get_context("spawn")
    sites = [f"s{i}.example" for i in range(8)]
    procs = [ctx.Process(target=_hold, args=(led, s)) for s in sites]
    for p in procs:
        p.start()
    for p in procs:
        p.join(60)
        assert p.exitcode == 0
    blocked = json.loads(led.read_text("utf-8"))["blocked"]
    assert set(sites) <= set(blocked)
    assert not (tmp_path / "world_crawler_access.json.lock").exists()


def test_tmp_name_includes_pid(tmp_path: Path, monkeypatch) -> None:
    led = tmp_path / "a.json"
    seen: list[str] = []
    real = Path.replace

    def spy(self: Path, target: object) -> Path:
        seen.append(self.name)
        return real(self, target)
    monkeypatch.setattr(Path, "replace", spy)
    acc = pf.HostAccess(led)
    acc.blocked["mine.example"] = {"verdict": "HTTP_403"}
    assert acc.save() is True
    assert seen and f".{os.getpid()}." in seen[0] and seen[0].endswith(".tmp")


def test_stale_break_never_deletes_a_live_peers_lock(tmp_path: Path, monkeypatch) -> None:
    """The race: waiter A saw a stale lock; before A breaks it, B broke it and took a LIVE lock.
    A's break must leave B's lock (and B's token) in place."""
    led = tmp_path / "a.json"
    b = pf._LedgerLock(led)
    assert b.acquire()                                  # B's live lock
    a = pf._LedgerLock(led, wait_s=0.1)
    real_stat = Path.stat
    calls = {"n": 0}

    def stale_once(self: Path, *args: object, **kw: object) -> os.stat_result:
        st = real_stat(self, *args, **kw)
        if self == b.path and calls["n"] == 0:          # A's age check reads the OLD lock
            calls["n"] += 1
            vals = list(st)
            vals[8] = st.st_mtime - pf.SAVE_LOCK_STALE_S - 10
            return os.stat_result(vals)
        return st
    monkeypatch.setattr(Path, "stat", stale_once)
    a._break_stale()
    monkeypatch.setattr(Path, "stat", real_stat)
    assert b.path.exists() and b.path.read_text("utf-8") == b.token
    assert not a.acquire()                              # still B's
    b.release()
    assert not b.path.exists()
    assert not list(tmp_path.glob("a.json.lock.stale.*"))


def test_two_waiters_breaking_one_stale_lock_never_both_hold(tmp_path: Path) -> None:
    import threading
    led = tmp_path / "a.json"
    lock = tmp_path / "a.json.lock"
    lock.write_text("1 deadbeef", "utf-8")
    old = os.path.getmtime(lock) - pf.SAVE_LOCK_STALE_S - 5
    os.utime(lock, (old, old))
    holders: list[int] = []
    peak = {"n": 0}
    mu = threading.Lock()

    def worker() -> None:
        lk = pf._LedgerLock(led, wait_s=20)
        assert lk.acquire()
        with mu:
            holders.append(1)
            peak["n"] = max(peak["n"], len(holders))
        import time
        time.sleep(0.01)
        with mu:
            holders.pop()
        lk.release()
    ts = [threading.Thread(target=worker) for _ in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(60)
    assert peak["n"] == 1 and not lock.exists()


def test_release_never_unlinks_a_peers_lock(tmp_path: Path) -> None:
    led = tmp_path / "a.json"
    mine = pf._LedgerLock(led)
    assert mine.acquire()
    mine.path.write_text("999 peer-token", "utf-8")     # a peer broke ours as stale and holds it
    mine.release()
    assert mine.path.read_text("utf-8") == "999 peer-token"


def test_a_release_that_cannot_be_saved_raises_and_changes_nothing(tmp_path: Path,
                                                                    monkeypatch) -> None:
    led = tmp_path / "a.json"
    _hold(led, "held.example")
    (tmp_path / "a.json.lock").write_text("999 live", "utf-8")
    monkeypatch.setattr(pf, "SAVE_LOCK_WAIT_S", 0.1)
    import pytest
    with pytest.raises(pf.ReleaseNotSaved):
        pf.release("site:held.example", "alice", path=led)
    row = json.loads(led.read_text("utf-8"))["blocked"]["held.example"]
    assert not row.get("released_by")
