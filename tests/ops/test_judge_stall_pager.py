"""THE JUDGE STALL PAGER (2026-10-21): each incident pages once, reminds at 6h, resolves once.

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


@pytest.fixture
def jsp() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "judge_stall_pager_t", REPO / "desks/mt5/scripts/judge_stall_pager.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def _world(tmp: Path, now: datetime, *, verdict_h: float = 1.0, hb_min: float = 0.5,
           status: str = "SWEEPING", phase: str = "plan", phase_h: float = 1.0) -> dict:
    ledger = tmp / "gate_verdict_ledger.jsonl"
    ledger.write_text("".join(json.dumps({"cell": f"c{i}", "at": _iso(now - timedelta(
        hours=verdict_h + i))}) + "\n" for i in range(3, -1, -1)), "utf-8")
    resident = tmp / "JUDGE_RESIDENT.json"
    resident.write_text(json.dumps({
        "pid": 111, "status": status, "heartbeat_utc": _iso(now - timedelta(minutes=hb_min)),
        "sweep_phase": {"pid": 222, "phase": phase,
                        "phase_started_utc": _iso(now - timedelta(hours=phase_h))}}), "utf-8")
    return {"ledger": ledger, "resident": resident, "throughput": tmp / "absent.json"}


def _step(jsp, tmp: Path, now: datetime, ch: Channel, alive=lambda pid: True, **kw) -> dict:
    paths = _world(tmp, now, **kw)
    return jsp.run(now=now, root=tmp, sender=ch, on_box=True, out=tmp / "JUDGE_STALL.json",
                   pid_alive=alive, **paths)


def test_a_healthy_judge_pages_nothing(jsp, tmp_path):
    ch = Channel()
    doc = _step(jsp, tmp_path, NOW, ch)
    assert not any(v["open"] for v in doc["incidents"].values())
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
    state = json.loads((tmp_path / jsp.PAGE_STATE_REL).read_text("utf-8"))
    assert state["open"]["no_verdict"]["incident"] == f"judge_stall:no_verdict@{_iso(t4)}"


def test_reminder_after_six_hours(jsp, tmp_path):
    ch = Channel()
    _step(jsp, tmp_path, NOW, ch, hb_min=60)
    _step(jsp, tmp_path, NOW + timedelta(hours=5.9), ch, hb_min=60)
    assert len(ch.sent) == 1
    d = _step(jsp, tmp_path, NOW + timedelta(hours=6), ch, hb_min=60)
    assert d["page"]["reminded"] == ["resident_dead"] and len(ch.sent) == 2
    assert jsp.REPAGE_H == 6.0


def test_resident_heartbeat_stale_or_pid_dead_pages(jsp, tmp_path):
    ch = Channel()
    d = _step(jsp, tmp_path, NOW, ch, hb_min=jsp.HEARTBEAT_STALE_MIN + 1)
    assert d["incidents"]["resident_dead"]["open"] is True and "resident_dead" in ch.sent[0][0]
    ch2 = Channel()
    other = tmp_path / "b"
    other.mkdir()
    d2 = _step(jsp, other, NOW, ch2, alive=lambda pid: pid != 111)
    assert d2["incidents"]["resident_dead"]["open"] is True
    assert d2["incidents"]["sweep_dead"]["open"] is False


def test_sweep_child_dead_pages(jsp, tmp_path):
    ch = Channel()
    d = _step(jsp, tmp_path, NOW, ch, alive=lambda pid: pid != 222)
    assert d["page"]["opened"] == ["sweep_dead"] and len(ch.sent) == 1


def test_phase_overrun_uses_the_measured_limit(jsp, tmp_path):
    ch = Channel()
    ok = _step(jsp, tmp_path, NOW, ch, phase="plan", phase_h=jsp.PHASE_LIMIT_H["plan"] - 0.1)
    assert ok["incidents"]["phase_overrun"]["open"] is False
    over = _step(jsp, tmp_path, NOW, ch, phase="merge_and_publish", phase_h=3.5)
    assert over["incidents"]["phase_overrun"]["open"] is True and len(ch.sent) == 1
    assert jsp.PHASE_LIMIT_H == {"plan": 4.5, "build_shards": 18.0, "collect_and_cut": 1.0,
                                 "rule_shards": 1.0, "merge_and_publish": 3.0}
    assert jsp.NO_VERDICT_H == 36.0 and jsp.HEARTBEAT_STALE_MIN == 10.0


def test_operator_stop_does_not_page_a_dead_heartbeat(jsp, tmp_path):
    ch = Channel()
    d = _step(jsp, tmp_path, NOW, ch, status="STOPPED", hb_min=600)
    assert d["incidents"]["resident_dead"]["open"] is False and ch.sent == []


def test_unmeasured_neither_opens_nor_clears(jsp, tmp_path):
    ch = Channel()
    _step(jsp, tmp_path, NOW, ch, hb_min=60)
    assert len(ch.sent) == 1
    (tmp_path / "JUDGE_RESIDENT.json").write_text("{broken", "utf-8")
    d = jsp.run(now=NOW + timedelta(minutes=5), root=tmp_path, sender=ch, on_box=True,
                out=tmp_path / "JUDGE_STALL.json", ledger=tmp_path / "gate_verdict_ledger.jsonl",
                resident=tmp_path / "JUDGE_RESIDENT.json", throughput=tmp_path / "x.json")
    assert d["incidents"]["resident_dead"]["open"] is None
    assert d["page"]["resolved"] == [] and len(ch.sent) == 1
    state = json.loads((tmp_path / jsp.PAGE_STATE_REL).read_text("utf-8"))
    assert "resident_dead" in state["open"]


def test_failed_send_is_recorded_and_retried(jsp, tmp_path):
    ch = Channel(raises=True)
    d = _step(jsp, tmp_path, NOW, ch, hb_min=60)
    assert d["page"]["sent"] is False and d["page"]["error"].startswith("OSError")
    state = json.loads((tmp_path / jsp.PAGE_STATE_REL).read_text("utf-8"))
    assert "paged_at" not in state["open"]["resident_dead"]
    ch.raises = False
    d2 = _step(jsp, tmp_path, NOW + timedelta(minutes=5), ch, hb_min=65)
    assert d2["page"]["sent"] and d2["page"]["reminded"] == ["resident_dead"]


def test_off_box_never_pages_or_writes(jsp, tmp_path):
    ch = Channel()
    paths = _world(tmp_path, NOW, hb_min=600, verdict_h=100)
    d = jsp.run(now=NOW, root=tmp_path, sender=ch, on_box=False,
                out=tmp_path / "JUDGE_STALL.json", pid_alive=lambda pid: None, **paths)
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
    assert "_judge_stall" not in run_body          # run(), which tests call, never invokes it
    assert "_judge_stall()" in src.split("def main(", 1)[1]
