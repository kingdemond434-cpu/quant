"""The box never fills up (principal 2026-11-25 02:49Z): measure, reclaim safely, never delete
evidence, never touch the tape, and publish I6/I7 for the guardian."""
from __future__ import annotations

import gzip
import json
import os
import sys
from collections import namedtuple
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))

import box_headroom as bh
import desk_self_heal as heal

NOW = datetime(2026, 11, 25, 3, 0, tzinfo=UTC)
U = namedtuple("U", "total used free")
GB = 1024 ** 3


def _usage(used_frac: float):
    return lambda _p: U(1200 * GB, int(1200 * GB * used_frac), int(1200 * GB * (1 - used_frac)))


class _PS:
    class _VM:
        total, available, percent = 64 * GB, 32 * GB, 50.0

    def virtual_memory(self):
        return self._VM()

    def cpu_percent(self, interval=0.0):
        return 40.0

    def cpu_count(self):
        return 18

    NORMAL_PRIORITY_CLASS, ABOVE_NORMAL_PRIORITY_CLASS = 32, 32768
    BELOW_NORMAL_PRIORITY_CLASS = 16384
    live_priority = 32768

    def process_iter(self, attrs):
        ps = self

        class P:
            def __init__(self, name, pid):
                self.info = {"name": name, "pid": pid}

            def nice(self):
                if self.info["name"] == "python.exe":  # a research process, below live
                    return ps.BELOW_NORMAL_PRIORITY_CLASS
                return ps.live_priority

            def memory_info(self):
                return namedtuple("M", "rss")(GB)

        return [P("terminal64.exe", i) for i in range(3)] + [P("python.exe", 9)]


def test_disk_over_the_75_line_is_a_fault_and_publishes_disk_headroom(tmp_path):
    doc = bh.run(tmp_path, NOW, usage=_usage(0.97), ps=_PS())
    assert doc["disk"]["ok"] is False and doc["disk"]["days_to_pause"] == 0.0
    pub = json.loads((tmp_path / bh.DISK_FILE).read_text())
    assert {"free_gb", "days_to_pause", "at"} <= set(pub) and pub["free_gb"] == 36.0
    ok = bh.run(tmp_path, NOW, usage=_usage(0.50), ps=_PS())
    assert ok["disk"]["ok"] and ok["holds"]
    assert ok["terminals"]["count"] == 3 and ok["ram"]["ok"] and ok["cpu"]["ok"]


def test_days_to_pause_comes_from_measured_growth(tmp_path):
    hist = tmp_path / bh.HISTORY
    hist.parent.mkdir(parents=True)
    then = (NOW - timedelta(days=2)).isoformat()
    hist.write_text(json.dumps({"at": then, "used": int(1200 * GB * 0.70) - 20 * GB}) + "\n")
    d = bh.disk(tmp_path, NOW, usage=_usage(0.70))
    assert d["growth_gb_per_day"] == 10.0
    assert d["days_to_pause"] == 12.0 and d["ok"] is False       # under 14 days: a fault


def test_logs_are_rolled_and_compressed_never_deleted_and_tape_is_never_touched(tmp_path):
    logs = tmp_path / "desks/mt5/logs"
    logs.mkdir(parents=True)
    big = logs / "big.log"
    big.write_bytes(b"x" * (bh.LOG_CAP_MB * 1024 * 1024 + 10))
    cold = logs / "cold.log"
    cold.write_bytes(b"evidence line\n" * 10000)
    old = (NOW - timedelta(days=bh.COLD_DAYS + 1)).timestamp()
    os.utime(cold, (old, old))
    tape = tmp_path / "desks/mt5/data/tape"
    tape.mkdir(parents=True)
    (tape / "ticks.log").write_bytes(b"t" * 100)
    pyc = tmp_path / "libs/__pycache__"
    pyc.mkdir(parents=True)
    (pyc / "a.pyc").write_bytes(b"c" * 100)
    ledger = tmp_path / "desks/mt5/data/ledger.jsonl"
    ledger.write_text("row\n")
    doc = bh.run(tmp_path, NOW, apply=True, usage=_usage(0.90), ps=_PS())
    assert set(doc["reclaim"]["done"]) == {"roll", "compress_cold", "derived_cache"}
    local = (tmp_path / bh.ACTIONS).read_text()
    assert "big.log" in local and "big.log" not in (tmp_path / bh.BOX_FILE).read_text()
    assert big.stat().st_size == 0
    rolled = next(logs.glob("big.log.*.gz"))
    assert len(gzip.decompress(rolled.read_bytes())) == bh.LOG_CAP_MB * 1024 * 1024 + 10
    assert not cold.exists()
    assert gzip.decompress((logs / "cold.log.gz").read_bytes()).count(b"evidence") == 10000
    assert (tape / "ticks.log").read_bytes() == b"t" * 100       # the tape, untouched
    assert ledger.read_text() == "row\n" and not pyc.exists()


def test_no_derived_cache_is_removed_below_the_line(tmp_path):
    pyc = tmp_path / "libs/__pycache__"
    pyc.mkdir(parents=True)
    (pyc / "a.pyc").write_bytes(b"c")
    bh.run(tmp_path, NOW, apply=True, usage=_usage(0.40), ps=_PS())
    assert pyc.exists()


def test_guardian_reads_i6_and_i7_from_the_published_file(tmp_path, monkeypatch):
    monkeypatch.setattr(heal, "_is_producing_host", lambda *a: True)
    bh.run(tmp_path, NOW, usage=_usage(0.97), ps=_PS())
    inv = {f.check: f for f in heal.check_invariants(tmp_path, NOW)}
    assert inv["invariant I6"].ok is False and "75%" in inv["invariant I6"].detail
    assert inv["invariant I7"].ok is True
    later = {f.check: f for f in heal.check_invariants(tmp_path, NOW + timedelta(hours=3))}
    assert later["invariant I6"].ok is False and "old" in later["invariant I6"].detail
    bh.run(tmp_path, NOW, usage=_usage(0.50), ps=_PS())
    assert {f.check: f for f in heal.check_invariants(tmp_path, NOW)}["invariant I6"].ok


def test_live_terminals_below_raised_priority_break_i7(tmp_path):
    ps = _PS()
    ps.live_priority = ps.NORMAL_PRIORITY_CLASS
    t = bh.terminals(ps)
    assert not t["ok"] and len(t["below_priority"]) == 3 and "NORMAL_PRIORITY_CLASS" in t["why"]
    ok = bh.terminals(_PS())
    assert ok["ok"] and ok["count"] == 3 and ok["live_rss_gb"] == 3.0


def test_a_log_that_grows_after_the_copy_is_never_truncated(tmp_path, monkeypatch):
    """Audit MF1: lines appended between the archive and the truncate must survive."""
    logs = tmp_path / "desks/mt5/logs"
    logs.mkdir(parents=True)
    big = logs / "big.log"
    n = bh.LOG_CAP_MB * 1024 * 1024 + 10
    big.write_bytes(b"x" * n)
    real = bh._gzip_verified

    def copy_then_append(src, dst, size):
        ok = real(src, dst, size)
        with src.open("ab") as fh:
            fh.write(b"late line\n")
        return ok

    monkeypatch.setattr(bh, "_gzip_verified", copy_then_append)
    out = bh.reclaim(tmp_path, NOW, past_line=False, apply=True)
    row = next(a for a in out["actions"] if a["kind"] == "roll")
    assert row["done"] is False and row["why"] == "grew_after_copy"
    assert big.stat().st_size == n + 10 and big.read_bytes().endswith(b"late line\n")
    assert not list(logs.glob("big.log.*.gz*"))


def test_gzip_copies_exactly_n_bytes(tmp_path):
    src = tmp_path / "a.log"
    src.write_bytes(b"0123456789")
    assert bh._gzip_verified(src, tmp_path / "a.gz", 6)
    assert gzip.decompress((tmp_path / "a.gz").read_bytes()) == b"012345"


def test_the_walk_never_enters_the_tape(tmp_path, monkeypatch):
    """Audit SF: protected dirs are pruned before descending, not filtered after an rglob."""
    tape = tmp_path / "desks/mt5/data/tape/ticks/EURUSD/__pycache__"
    tape.mkdir(parents=True)
    (tape / "x.pyc").write_bytes(b"c")
    pyc = tmp_path / "libs/__pycache__"
    pyc.mkdir(parents=True)
    seen: list[str] = []
    real = os.walk

    def spy(top, *a, **k):
        for row in real(top, *a, **k):
            seen.append(row[0])
            yield row

    monkeypatch.setattr(bh.os, "walk", spy)
    bh.reclaim(tmp_path, NOW, past_line=True, apply=True)
    assert seen and not any("tape" in Path(p).parts for p in seen)
    assert tape.exists() and not pyc.exists()


class _RecPS(_PS):
    BELOW_NORMAL_PRIORITY_CLASS = 16384
    rec_priority = 16384

    def process_iter(self, attrs):
        ps = self

        class R:
            def __init__(self, name, pid, cmd):
                self.info = {"name": name, "pid": pid}
                self._cmd = cmd

            def nice(self):
                return ps.rec_priority

            def cmdline(self):
                return self._cmd

            def memory_info(self):
                return namedtuple("M", "rss")(GB)

        return [*_PS.process_iter(self, attrs),
                R("python.exe", 40, ["python.exe", "-u", "-m", "recorders.tick_recorder"]),
                R("python.exe", 41, ["python.exe", "C:\\q\\prop\\e8_spread_sampler.py"]),
                R("python.exe", 42, ["python.exe", "C:\\q\\research\\some_miner.py"])]


def test_a_live_recorder_in_a_research_priority_class_breaks_i7():
    """Audit 2026-11-25 13:09Z: a live recorder sharing a class with research is a fault the
    guardian pages to Claude (box 11-25: tick_recorder gap 474 s at BELOW_NORMAL)."""
    ps = _RecPS()
    t = bh.terminals(ps)
    assert not t["ok"]
    assert [r.split(" ")[0] for r in t["recorders_below_priority"]] == [
        "tick_recorder", "e8_spread_sampler"]
    assert "live recorder(s) in a research priority class" in t["why"]
    ps.rec_priority = ps.ABOVE_NORMAL_PRIORITY_CLASS
    ok = bh.terminals(ps)
    assert ok["ok"] and ok["recorders_below_priority"] == [] and ok["count"] == 3


# --- I8: live outranks research (coordinator for zuck 2026-11-25 17:36Z, PERMANENT) -------------

class _PrioPS(_PS):
    """Terminals, live organs and research, each with its own class and CPU."""

    def __init__(self, classes):
        self.classes = classes  # pid -> priority constant

    def process_iter(self, attrs):
        ps = self

        class R:
            def __init__(self, name, pid, cmd, cpu):
                self.info = {"name": name, "pid": pid}
                self._cmd, self._cpu = cmd, cpu

            def nice(self):
                return ps.classes[self.info["pid"]]

            def cmdline(self):
                return self._cmd

            def cpu_percent(self, _interval=None):
                return self._cpu

        return [R("terminal64.exe", 1, ["terminal64.exe"], 5.0),
                R("python.exe", 2, ["python.exe", "-u", "-m", "recorders.tick_recorder"], 3.0),
                R("python.exe", 3, ["python.exe", "C:\\q\\gateway_resident.py"], 2.0),
                R("python.exe", 4, ["python.exe", "C:\\q\\research\\run_desk_self_heal.py"], 1.0),
                R("python.exe", 5, ["python.exe", "C:\\q\\research\\pf_allocator.py"], 1400.0),
                R("python.exe", 6, ["python.exe", "C:\\q\\research\\miner.py"], 100.0)]


AN, N, BN = 32768, 32, 16384


def test_live_above_research_holds_and_research_share_is_measured():
    p = bh.priority(_PrioPS({1: AN, 2: AN, 3: AN, 4: AN, 5: BN, 6: BN}), sleep=lambda s: None)
    assert p["ok"] and p["live"] == 4 and p["research"] == 2
    assert p["research_share"] == round(1500.0 / 1800.0, 4)


def test_a_live_organ_left_at_the_task_default_is_a_priority_inversion():
    """Box 11-25: the tick recorder and gateway_resident ran BELOW_NORMAL beside research."""
    p = bh.priority(_PrioPS({1: AN, 2: BN, 3: BN, 4: AN, 5: BN, 6: BN}), sleep=lambda s: None)
    assert not p["ok"] and "PRIORITY_INVERSION: live below ABOVE_NORMAL" in p["why"]
    assert [x.split(" ")[0] for x in p["live_below"]] == ["recorders.tick_recorder",
                                                          "gateway_resident.py"]
    assert len(p["research_at_or_above_live"]) == 2      # research ties the starved live floor
    assert "research holds 83% of the box" in p["why"]


def test_research_raised_to_the_live_class_is_an_inversion_even_when_live_is_raised():
    p = bh.priority(_PrioPS({1: AN, 2: AN, 3: AN, 4: AN, 5: AN, 6: N}), sleep=lambda s: None)
    assert not p["ok"]
    assert p["research_at_or_above_live"] == ["pf_allocator.py pid 5 ABOVE_NORMAL_PRIORITY_CLASS"]


def test_the_guardian_counts_as_live():
    jp = bh._jp()
    assert jp.own_class("python.exe", ["python.exe", "x/run_desk_self_heal.py"]) == "live"
    assert jp.own_class("python.exe", ["python.exe", "x/alert_feed.py"]) == "live"


def test_i8_pages_an_inversion_and_reads_unmeasured_off_windows(tmp_path):
    bh.run(tmp_path, NOW, usage=_usage(0.5),
           ps=_PrioPS({1: AN, 2: BN, 3: AN, 4: AN, 5: BN, 6: BN}))
    inv = {f.check: f for f in heal.check_invariants(tmp_path, NOW)}
    assert inv["invariant I8"].ok is False and "PRIORITY_INVERSION" in inv["invariant I8"].detail
    bh.run(tmp_path, NOW, usage=_usage(0.5), ps=_PrioPS({1: AN, 2: AN, 3: AN, 4: AN, 5: BN, 6: BN}))
    assert {f.check: f for f in heal.check_invariants(tmp_path, NOW)}["invariant I8"].ok
    assert bh.priority(object())["why"].startswith("UNMEASURED")
