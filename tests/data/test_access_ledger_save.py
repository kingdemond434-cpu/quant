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
    real = Path.read_text

    def boom(self: Path, *a: object, **k: object) -> str:
        if self == led:
            raise PermissionError("share violation")
        return real(self, *a, **k)
    monkeypatch.setattr(Path, "read_text", boom)
    assert acc.save() is False
    monkeypatch.setattr(Path, "read_text", real)
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
