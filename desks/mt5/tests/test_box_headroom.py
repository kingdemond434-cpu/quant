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
    live_priority = 32768

    def process_iter(self, attrs):
        ps = self

        class P:
            def __init__(self, name, pid):
                self.info = {"name": name, "pid": pid}

            def nice(self):
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
