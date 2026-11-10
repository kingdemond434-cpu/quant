"""The cache warmer can never again be blocked for days by one of its own orphans (2026-11-10).

Box: an MT5-CacheWarm python from 11-02 logged HARD_STOP and never exited, held the task's
`>> MT5-CacheWarm.log` handle, and every later run died in cmd with Last Result 1. Pinned here:
the reaper ends only an orphaned warm_gauntlet_cache.py past its hour and logs every decision;
the memo stamp ignores the hourly rewrite of universe.json unless a field the partition reads
moved; and a held log costs only that file."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK / "scripts"), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import warm_reaper as wr  # noqa: E402

NOW = 1_800_000_000.0
OLD = NOW - 8 * 86400.0


class _Proc:
    def __init__(self, pid: int, cmd: list[str], created: float, parent_alive: bool) -> None:
        self.pid, self._cmd, self._created, self._parent_alive = pid, cmd, created, parent_alive
        self.killed = False

    def cmdline(self) -> list[str]:
        return self._cmd

    def create_time(self) -> float:
        return self._created

    def parent(self) -> Any:
        alive = self._parent_alive

        class _P:
            def is_running(self) -> bool:
                return alive
        return _P() if alive else None

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout: float | None = None) -> None:
        return None


WARM = ["python.exe", "-u", "scripts\\warm_gauntlet_cache.py"]


def test_only_an_orphaned_warmer_past_its_hour_is_reaped_and_every_decision_is_logged(
        tmp_path: Path) -> None:
    orphan = _Proc(36780, WARM, OLD, parent_alive=False)
    running = _Proc(2, WARM, NOW - 600, parent_alive=False)            # inside its hour
    waited_on = _Proc(3, WARM, OLD, parent_alive=True)                 # someone still owns it
    judge = _Proc(4, ["python.exe", "scripts/external_gauntlet.py"], OLD, parent_alive=False)
    miner = _Proc(5, ["python.exe", "warm_gauntlet_cache_helper.py"], OLD, parent_alive=False)
    log = tmp_path / "reaped.jsonl"
    res = wr.reap(NOW, procs=[orphan, running, waited_on, judge, miner], log=log, by="test")
    assert orphan.killed and res["reaped"] == 1 and res["failed"] == 0
    assert not (running.killed or waited_on.killed or judge.killed or miner.killed)
    by_pid = {r["pid"]: r["decision"] for r in res["rows"]}
    assert by_pid == {36780: "REAP", 2: "SPARED_YOUNG", 3: "SPARED_PARENT_ALIVE"}
    line = json.loads(log.read_text("utf-8").splitlines()[-1])
    assert line["by"] == "test" and {r["pid"] for r in line["rows"]} == {36780, 2, 3}
    assert all("cmdline" in r and "created" in r for r in line["rows"])


def test_a_reaper_that_cannot_list_processes_kills_nothing_and_says_so(tmp_path: Path) -> None:
    class _Boom:
        def __iter__(self) -> Any:
            raise RuntimeError("no process table")
    res = wr.reap(NOW, procs=_Boom(), log=tmp_path / "r.jsonl")
    assert res["reaped"] == 0 and str(res["status"]).startswith("UNMEASURED")


def test_the_hourly_universe_rewrite_no_longer_voids_the_docket_memo(tmp_path: Path) -> None:
    import warm_gauntlet_cache as W
    uni = tmp_path / "universe.json"
    uni.write_text(json.dumps({"EURUSD": {"median_spread_pts": 3}, "GBPSEK": {"tradeable": True}}),
                   "utf-8")
    a = W.universe_projection(uni)
    # spreads, swaps and stamps move every hour and change no partition outcome
    uni.write_text(json.dumps({"EURUSD": {"median_spread_pts": 9, "at": "x"},
                               "GBPSEK": {"tradeable": True, "swap": 1}}), "utf-8")
    assert W.universe_projection(uni) == a
    # a symbol joining the registry, or going CLOSE_ONLY, does
    uni.write_text(json.dumps({"EURUSD": {}, "GBPSEK": {}, "USDNOK": {}}), "utf-8")
    assert W.universe_projection(uni) != a
    uni.write_text(json.dumps({"EURUSD": {}, "GBPSEK": {"tradeable": False}}), "utf-8")
    assert W.universe_projection(uni) != a
    uni.write_text("{torn", "utf-8")
    assert W.universe_projection(uni).startswith("stat:")


def test_a_held_log_costs_only_that_file(tmp_path: Path, monkeypatch: Any) -> None:
    import warm_gauntlet_cache as W
    log = tmp_path / "MT5-CacheWarm.log"
    real_open = Path.open

    def held(self: Path, *a: Any, **k: Any) -> Any:
        if self == log:
            raise PermissionError("used by another process")
        return real_open(self, *a, **k)

    monkeypatch.setattr(Path, "open", held)
    monkeypatch.setattr(sys, "stdout", sys.stdout)
    monkeypatch.setattr(sys, "stderr", sys.stderr)
    got = W._open_own_log(["--log", str(log)])
    assert got is not None and got != str(log) and Path(got).parent == tmp_path
    sys.stdout.flush()
    assert "LOG FALLBACK" in Path(got).read_text("utf-8")
    assert W._open_own_log([]) is None
