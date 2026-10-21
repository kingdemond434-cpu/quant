"""THE JUDGE STALL PAGER (2026-10-21, v2 after the audit of e759c01f6): each incident pages once,
reminds at 6h, resolves once -- and UNMEASURED, unknown phases, pid reuse, a stuck idle resident,
a zero-cell sweep, an unreadable host identity and a killed send all page instead of going quiet.

The channel is always mocked and pid liveness injected: no test reaches a network, reads a
credential or probes a real process.
"""
from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 10, 21, 3, 0, tzinfo=UTC)


def _load(name: str, rel: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def jsp() -> ModuleType:
    return _load("judge_stall_pager_t", "desks/mt5/scripts/judge_stall_pager.py")


class Channel:
    def __init__(self, raises: bool = False) -> None:
        self.sent: list[tuple[str, str]] = []
        self.raises = raises

    def __call__(self, title: str, body: str) -> dict[str, Any]:
        self.sent.append((title, body))
        if self.raises:
            raise OSError("channel down")
        return {"armed": 1, "delivered": 1}


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


def _alive(pid: object, started: datetime | None) -> bool | None:
    return True


def _world(tmp: Path, now: datetime, *, verdict_h: float = 1.0, hb_min: float = 0.5,
           status: str = "SWEEPING", phase: str | None = "plan", phase_h: float = 1.0,
           ended_h: float = 2.0, cells: int | None = 7, resident: dict | None = None) -> dict:
    ledger = tmp / "gate_verdict_ledger.jsonl"
    ledger.write_text("".join(json.dumps({"cell": f"c{i}", "at": _iso(now - timedelta(
        hours=verdict_h + i))}) + "\n" for i in range(3, -1, -1)), "utf-8")
    end = now - timedelta(hours=ended_h)
    doc = {"pid": 111, "status": status, "started_utc": _iso(now - timedelta(days=2)),
           "heartbeat_utc": _iso(now - timedelta(minutes=hb_min)),
           "last_sweep_ended_utc": _iso(end), "last_sweep_s": 20_000.0, "last_rc": 0}
    if phase is not None:
        doc["sweep_phase"] = {"pid": 222, "phase": phase,
                              "sweep_started_utc": _iso(now - timedelta(hours=phase_h + 1)),
                              "phase_started_utc": _iso(now - timedelta(hours=phase_h))}
    res = tmp / "JUDGE_RESIDENT.json"
    res.write_text(json.dumps(resident if resident is not None else doc), "utf-8")
    sweep = tmp / "universal_gates_external.json"
    if cells is not None:
        sweep.write_text(json.dumps({"swept_at": _iso(end - timedelta(minutes=30)),
                                     "n_cells": cells}), "utf-8")
    return {"ledger": ledger, "resident": res, "throughput": tmp / "absent.json",
            "sweep_result": sweep}


def _step(jsp, tmp: Path, now: datetime, ch: Channel, alive=_alive, on_box=True, **kw) -> dict:
    paths = _world(tmp, now, **kw)
    return jsp.run(now=now, root=tmp, sender=ch, on_box=on_box, out=tmp / "JUDGE_STALL.json",
                   pid_alive=alive, **paths)


def _state(jsp, tmp: Path) -> dict:
    return json.loads((tmp / jsp.PAGE_STATE_REL).read_text("utf-8"))


def test_a_healthy_judge_pages_nothing(jsp, tmp_path):
    ch = Channel()
    doc = _step(jsp, tmp_path, NOW, ch)
    assert {k for k, v in doc["incidents"].items() if v["open"] is not False} == set()
    assert ch.sent == [] and (tmp_path / "JUDGE_STALL.json").exists()


def test_no_verdict_pages_once_dedupes_resolves_and_recurs(jsp, tmp_path):
    ch = Channel()
    stale = jsp.NO_VERDICT_H + 1
    d1 = _step(jsp, tmp_path, NOW, ch, verdict_h=stale)
    assert d1["page"]["opened"] == ["no_verdict"] and len(ch.sent) == 1
    assert ch.sent[0][0] == "JUDGE STALLED: no_verdict"
    t2 = NOW + timedelta(minutes=5)
    _step(jsp, tmp_path, t2, ch, verdict_h=stale)
    assert len(ch.sent) == 1                                   # second reading: no page
    t3 = t2 + timedelta(minutes=5)
    d3 = _step(jsp, tmp_path, t3, ch)
    assert d3["page"]["resolved"] == ["no_verdict"] and len(ch.sent) == 2
    assert ch.sent[1][0] == "JUDGE STALL RESOLVED: no_verdict"
    t4 = t3 + timedelta(minutes=5)
    d4 = _step(jsp, tmp_path, t4, ch, verdict_h=stale)
    assert d4["page"]["opened"] == ["no_verdict"] and len(ch.sent) == 3
    assert _state(jsp, tmp_path)["open"]["no_verdict"]["incident"] == \
        f"judge_stall:no_verdict@{_iso(t4)}"


def test_reminder_after_six_hours(jsp, tmp_path):
    ch = Channel()
    _step(jsp, tmp_path, NOW, ch, hb_min=60)
    _step(jsp, tmp_path, NOW + timedelta(hours=5.9), ch, hb_min=60)
    assert len(ch.sent) == 1
    d = _step(jsp, tmp_path, NOW + timedelta(hours=6), ch, hb_min=60)
    assert d["page"]["reminded"] == ["resident_dead"] and len(ch.sent) == 2
    assert jsp.REPAGE_H == 6.0


def test_resident_heartbeat_stale_future_or_pid_dead_pages(jsp, tmp_path):
    d = _step(jsp, tmp_path, NOW, Channel(), hb_min=jsp.HEARTBEAT_STALE_MIN + 1)
    assert d["incidents"]["resident_dead"]["open"] is True
    (tmp_path / "f").mkdir()
    fut = _step(jsp, tmp_path / "f", NOW, Channel(), hb_min=-(jsp.FUTURE_SKEW_S / 60 + 1))
    assert fut["incidents"]["resident_dead"]["open"] is True
    assert "in the future" in fut["incidents"]["resident_dead"]["why"]
    near = _step(jsp, tmp_path / "f", NOW, Channel(), hb_min=-2)
    assert near["incidents"]["resident_dead"]["open"] is False      # inside the skew
    (tmp_path / "b").mkdir()
    d2 = _step(jsp, tmp_path / "b", NOW, Channel(), alive=lambda pid, s: pid != 111)
    assert d2["incidents"]["resident_dead"]["open"] is True
    assert d2["incidents"]["sweep_dead"]["open"] is False


def test_sweep_child_dead_pages(jsp, tmp_path):
    ch = Channel()
    d = _step(jsp, tmp_path, NOW, ch, alive=lambda pid, s: pid != 222)
    assert d["page"]["opened"] == ["sweep_dead"] and len(ch.sent) == 1


def test_pid_reuse_reads_as_dead(jsp, monkeypatch):
    """A live pid whose process was created after the stamp that names it is another process."""
    started = NOW - timedelta(hours=5)

    class Proc:
        def __init__(self, pid: int) -> None:
            self.pid = pid

        def create_time(self) -> float:
            return (started + timedelta(hours=1)).timestamp() if self.pid == 7 else \
                (started - timedelta(seconds=2)).timestamp()

    class FakePsutil:
        NoSuchProcess = LookupError
        Process = Proc

        @staticmethod
        def pid_exists(pid: int) -> bool:
            return pid != 9

    monkeypatch.setitem(__import__("sys").modules, "psutil", FakePsutil)
    assert jsp._pid_alive(7, started) is False                 # reused: created an hour later
    assert jsp._pid_alive(8, started) is True                  # the process the stamp names
    assert jsp._pid_alive(9, started) is False                 # gone
    assert jsp._pid_alive(8, None) is None                     # no stamp: UNMEASURED
    assert jsp._pid_alive("x", started) is None


def test_phase_overrun_known_new_and_unknown_phases(jsp, tmp_path):
    ch = Channel()
    ok = _step(jsp, tmp_path, NOW, ch, phase="plan", phase_h=jsp.PHASE_LIMIT_H["plan"] - 0.1)
    assert ok["incidents"]["phase_overrun"]["open"] is False
    assert jsp.PHASE_LIMIT_H["prewarm"] == round(1.5 * (8_640 + 1_100) / 3600, 2)
    assert jsp.PHASE_LIMIT_H["plan_handoff"] == 1.0
    pw = _step(jsp, tmp_path, NOW, Channel(), phase="prewarm", phase_h=4.2)
    assert pw["incidents"]["phase_overrun"]["open"] is True
    ho = _step(jsp, tmp_path, NOW, Channel(), phase="plan_handoff", phase_h=1.1)
    assert ho["incidents"]["phase_overrun"]["open"] is True
    assert max(jsp.PHASE_LIMIT_H.values()) == jsp.UNKNOWN_PHASE_LIMIT_H
    young = _step(jsp, tmp_path, NOW, Channel(), phase="brand_new_phase", phase_h=1.0)
    assert young["incidents"]["phase_overrun"]["open"] is False
    assert young["incidents"]["phase_overrun"]["known_phase"] is False
    old = _step(jsp, tmp_path, NOW, Channel(), phase="brand_new_phase", phase_h=100,
                ended_h=2.0)
    assert old["incidents"]["phase_overrun"]["open"] is True
    assert "UNKNOWN to this pager" in old["incidents"]["phase_overrun"]["why"]


def test_sweeping_with_no_phase_is_unmeasured_not_clean(jsp, tmp_path):
    d = _step(jsp, tmp_path, NOW, Channel(), phase=None)
    assert d["incidents"]["sweep_dead"]["open"] is None
    assert d["incidents"]["phase_overrun"]["open"] is None


def test_unmeasured_inputs_page_after_thirty_minutes(jsp, tmp_path):
    ch = Channel()
    torn = tmp_path / "JUDGE_RESIDENT.json"
    for minutes in (0, 10, 25):
        t = NOW + timedelta(minutes=minutes)
        _world(tmp_path, t)
        torn.write_text("{torn", "utf-8")
        d = jsp.run(now=t, root=tmp_path, sender=ch, on_box=True,
                    out=tmp_path / "JUDGE_STALL.json", ledger=tmp_path / "empty.jsonl",
                    resident=torn, throughput=tmp_path / "x.json")
        assert d["page"]["sent"] is False
    assert ch.sent == []
    t = NOW + timedelta(minutes=jsp.UNMEASURED_PAGE_MIN)
    d = jsp.run(now=t, root=tmp_path, sender=ch, on_box=True, out=tmp_path / "JUDGE_STALL.json",
                ledger=tmp_path / "empty.jsonl", resident=torn, throughput=tmp_path / "x.json")
    assert d["page"]["opened"] == ["inputs_unmeasured"] and len(ch.sent) == 1
    # an empty ledger is unmeasured too
    (tmp_path / "e").mkdir()
    (tmp_path / "e" / "l.jsonl").write_text("", "utf-8")
    assert jsp.last_verdict(NOW, ledger=tmp_path / "e" / "l.jsonl")["at"] is None


def test_unmeasured_neither_opens_nor_clears_its_own_incident(jsp, tmp_path):
    ch = Channel()
    _step(jsp, tmp_path, NOW, ch, hb_min=60)
    assert len(ch.sent) == 1
    (tmp_path / "JUDGE_RESIDENT.json").write_text("{broken", "utf-8")
    d = jsp.run(now=NOW + timedelta(minutes=5), root=tmp_path, sender=ch, on_box=True,
                out=tmp_path / "JUDGE_STALL.json", ledger=tmp_path / "gate_verdict_ledger.jsonl",
                resident=tmp_path / "JUDGE_RESIDENT.json", throughput=tmp_path / "x.json")
    assert d["incidents"]["resident_dead"]["open"] is None
    assert d["page"]["resolved"] == [] and len(ch.sent) == 1
    assert "resident_dead" in _state(jsp, tmp_path)["open"]


def test_sweep_overdue_catches_a_stuck_lane_held(jsp, tmp_path):
    assert round(1.5 * (61_111 + 300) / 3600, 2) == jsp.SWEEP_OVERDUE_H
    held = _step(jsp, tmp_path, NOW, Channel(), status="LANE_HELD", phase=None, ended_h=1.5)
    assert held["incidents"]["sweep_overdue"]["open"] is True
    brief = _step(jsp, tmp_path, NOW, Channel(), status="BACKOFF", phase=None, ended_h=0.1)
    assert brief["incidents"]["sweep_overdue"]["open"] is False
    long_sweep = _step(jsp, tmp_path, NOW, Channel(), ended_h=jsp.SWEEP_OVERDUE_H + 0.5,
                       phase_h=1.0)
    assert long_sweep["incidents"]["sweep_overdue"]["open"] is True
    stopped = _step(jsp, tmp_path, NOW, Channel(), status="STOPPED", phase=None, ended_h=50)
    assert stopped["incidents"]["sweep_overdue"]["open"] is False


def test_zero_judged_sweep_pages(jsp, tmp_path):
    d = _step(jsp, tmp_path, NOW, Channel(), cells=0)
    assert d["incidents"]["zero_judged_sweep"]["open"] is True
    other = tmp_path / "o"
    other.mkdir()
    d2 = _step(jsp, other, NOW, Channel(), cells=None)
    assert d2["incidents"]["zero_judged_sweep"]["open"] is None    # no result for that sweep


def test_operator_stop_does_not_page_a_dead_heartbeat(jsp, tmp_path):
    ch = Channel()
    d = _step(jsp, tmp_path, NOW, ch, status="STOPPED", hb_min=600, phase=None)
    assert d["incidents"]["resident_dead"]["open"] is False and ch.sent == []


def test_failed_send_is_recorded_and_retried(jsp, tmp_path):
    ch = Channel(raises=True)
    d = _step(jsp, tmp_path, NOW, ch, hb_min=60)
    assert d["page"]["sent"] is False and d["page"]["error"].startswith("OSError")
    assert "paged_at" not in _state(jsp, tmp_path)["open"]["resident_dead"]
    ch.raises = False
    d2 = _step(jsp, tmp_path, NOW + timedelta(minutes=5), ch, hb_min=65)
    assert d2["page"]["sent"] and d2["page"]["reminded"] == ["resident_dead"]


def test_failed_resolve_is_retried(jsp, tmp_path):
    ch = Channel()
    _step(jsp, tmp_path, NOW, ch, hb_min=60)
    ch.raises = True
    t = NOW + timedelta(minutes=5)
    d = _step(jsp, tmp_path, t, ch)
    assert d["page"]["resolved"] == ["resident_dead"] and d["page"]["sent"] is False
    assert "resident_dead" in _state(jsp, tmp_path)["resolving"]
    ch.raises = False
    t2 = t + timedelta(minutes=5)
    d2 = _step(jsp, tmp_path, t2, ch)
    assert d2["page"]["sent"] and d2["page"]["title"] == "JUDGE STALL RESOLVED: resident_dead"
    assert _state(jsp, tmp_path)["resolving"] == {}
    _step(jsp, tmp_path, t2 + timedelta(minutes=5), ch)
    assert len(ch.sent) == 3                                    # open, failed resolve, resolve


def test_a_send_killed_mid_flight_does_not_repage_every_run(jsp, tmp_path):
    class Killed(BaseException):
        pass

    def kill(title: str, body: str) -> dict:
        raise Killed

    _world(tmp_path, NOW, hb_min=60)
    with pytest.raises(Killed):
        jsp._page(jsp.measure(NOW, pid_alive=_alive, **_world(tmp_path, NOW, hb_min=60)),
                  root=tmp_path, now=NOW, sender=kill, repage_h=jsp.REPAGE_H)
    row = _state(jsp, tmp_path)["open"]["resident_dead"]
    assert row["inflight_at"] == _iso(NOW) and "paged_at" not in row
    ch = Channel()
    for minutes in (5, 10, 25):
        _step(jsp, tmp_path, NOW + timedelta(minutes=minutes), ch, hb_min=60)
    assert ch.sent == []                                       # the send may have landed
    d = _step(jsp, tmp_path, NOW + timedelta(minutes=jsp.INFLIGHT_RETRY_MIN), ch, hb_min=60)
    assert d["page"]["reminded"] == ["resident_dead"] and len(ch.sent) == 1


def test_host_identity_unreadable_fails_toward_paging(jsp, tmp_path):
    ch = Channel()
    d = _step(jsp, tmp_path, NOW, ch, on_box=None)
    assert d["incidents"]["host_unreadable"]["open"] is True
    assert "host_unreadable" in d["page"]["opened"] and len(ch.sent) == 1
    assert "host identity unreadable" in ch.sent[0][1]
    assert (tmp_path / "JUDGE_STALL.json").exists()


def test_host_identity_raising_reads_as_unknown(jsp, monkeypatch):
    import libs.ops.host_identity as hi

    def boom() -> None:
        raise RuntimeError("no machine id")

    monkeypatch.setattr(hi, "identify", boom)
    assert jsp._on_box() is None


def test_off_box_never_pages_or_writes(jsp, tmp_path):
    ch = Channel()
    d = _step(jsp, tmp_path, NOW, ch, on_box=False, hb_min=600, verdict_h=100,
              alive=lambda pid, s: None)
    assert d["incidents"]["resident_dead"]["open"] is True
    assert ch.sent == [] and d["page"]["reason"] == "off box"
    assert not (tmp_path / "JUDGE_STALL.json").exists()
    assert not (tmp_path / jsp.PAGE_STATE_REL).exists()


def test_last_verdict_falls_back_to_the_published_figure(jsp, tmp_path):
    tp = tmp_path / "JUDGING_THROUGHPUT.json"
    tp.write_text(json.dumps({"rate": {"verdicts": {"last_verdict_at": _iso(NOW - timedelta(
        hours=2))}}}), "utf-8")
    lv = jsp.last_verdict(NOW, ledger=tmp_path / "absent.jsonl", throughput=tp)
    assert lv["at"] == _iso(NOW - timedelta(hours=2)) and "JUDGING_THROUGHPUT" in lv["source"]
    assert jsp.last_verdict(NOW, ledger=tmp_path / "a", throughput=tmp_path / "b")["at"] is None


def test_box_heartbeat_invokes_the_pager_only_from_its_scheduled_entry():
    src = (REPO / "desks/mt5/scripts/box_heartbeat.py").read_text("utf-8")
    assert "judge_stall_pager.py" in src
    run_body = src.split("def run(", 1)[1].split("\ndef ", 1)[0]
    assert "_judge_stall(" not in run_body          # run(), which tests call, never invokes it
    assert "_judge_stall()" in src.split("def main(", 1)[1]


def test_box_heartbeat_records_the_pager_rc_and_a_failed_run_fails_the_next_beat(
        tmp_path, monkeypatch):
    hb = _load("box_heartbeat_t", "desks/mt5/scripts/box_heartbeat.py")
    out = tmp_path / "BOX_HEARTBEAT.json"
    reading = {"at": "x", "checks": {}, "failing": [], "verdict": "OK"}
    hb.run(out=out, secrets=(tmp_path / "absent.json",), reading=dict(reading))

    class R:
        returncode = 1

    import subprocess
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: R())
    rec = hb._judge_stall(out)
    assert rec["rc"] == 1 and rec["ok"] is False
    assert json.loads(out.read_text("utf-8"))["judge_stall_pager"]["rc"] == 1
    doc = hb.run(out=out, secrets=(tmp_path / "absent.json",),
                 reading={"at": "y", "checks": {}, "failing": [], "verdict": "OK"})
    assert doc["verdict"] == "FAIL" and doc["failing"] == ["judge_stall_pager"]

    def timeout(*a, **k):
        raise subprocess.TimeoutExpired("x", 60)

    monkeypatch.setattr(subprocess, "run", timeout)
    assert hb._judge_stall(out)["rc"] == "TIMEOUT"


def test_the_artifact_is_published_from_the_box():
    sync = (REPO / "desks/mt5/scripts/sync_shadow_to_git.ps1").read_text("utf-8")
    assert '"desks/mt5/reports/JUDGE_STALL.json"' in sync
    assert "!desks/mt5/reports/JUDGE_STALL.json" in (REPO / ".gitignore").read_text("utf-8")
