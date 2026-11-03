"""THE JUDGE STALL PAGER (2026-10-21, v3 after the audits of e759c01f6 and e60b42212): each
incident pages once, reminds at 6h, resolves once -- and UNMEASURED (persistent or flapping),
unknown phases, pid reuse, a stuck idle resident, a zero-cell or result-less sweep, an unreadable
host identity and a killed send all page instead of going quiet.

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
        # the judge's own layout: indent=2, counts at the head, swept_at after the verdicts
        sweep.write_text(json.dumps({"n_cells": cells, "n_judged": cells, "verdicts": [],
                                     "swept_at": _iso(end - timedelta(minutes=30))},
                                    indent=2), "utf-8")
    elif sweep.exists():
        sweep.unlink()
    return {"ledger": ledger, "resident": res, "throughput": tmp / "absent.json",
            "sweep_result": sweep, "env_file": tmp / "absent.env.json"}


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


# ---- v3 (audit of e60b42212): every incident that stays UNMEASURED past a bound pages ----

def _series(jsp, tmp: Path, ch: Channel, minutes, write) -> list[dict]:
    """Run the pager at NOW + each minute, letting `write(t, paths)` shape that reading."""
    docs = []
    for m in minutes:
        t = NOW + timedelta(minutes=m)
        paths = _world(tmp, t)
        write(t, paths)
        docs.append(jsp.run(now=t, root=tmp, sender=ch, on_box=True,
                            out=tmp / "JUDGE_STALL.json", pid_alive=_alive, **paths))
    return docs


def _resident(doc: dict) -> Any:
    return lambda t, p: p["resident"].write_text(json.dumps(doc), "utf-8")


def test_a_resident_with_no_heartbeat_pages_after_the_bound(jsp, tmp_path):
    ch = Channel()
    doc = {"pid": 111, "status": "BACKOFF", "started_utc": _iso(NOW - timedelta(days=2)),
           "last_sweep_ended_utc": _iso(NOW), "last_sweep_s": 100.0, "last_rc": 1}
    docs = _series(jsp, tmp_path, ch, range(0, 30, 5), _resident(doc))
    assert docs[0]["incidents"]["resident_dead"]["open"] is None
    assert ch.sent == []
    d = _series(jsp, tmp_path, ch, [jsp.UNMEASURED_PAGE_MIN], _resident(doc))[0]
    assert d["page"]["opened"] == ["inputs_unmeasured"]
    assert d["incidents"]["inputs_unmeasured"]["incidents"] == ["resident_dead"]
    assert "no heartbeat stamp" in ch.sent[0][1]


def test_a_bare_running_status_pages(jsp, tmp_path):
    ch = Channel()
    docs = _series(jsp, tmp_path, ch, range(0, 35, 5), _resident({"status": "RUNNING"}))
    inc = docs[-1]["incidents"]
    assert inc["resident_dead"]["open"] is None and inc["sweep_overdue"]["open"] is None
    assert docs[-1]["page"]["opened"] == ["inputs_unmeasured"] and len(ch.sent) == 1
    assert set(inc["inputs_unmeasured"]["incidents"]) == {"resident_dead", "sweep_overdue"}


def test_a_sweep_child_with_no_start_stamp_pages(jsp, tmp_path):
    ch = Channel()

    def strip(t: datetime, p: dict) -> None:
        doc = json.loads(p["resident"].read_text("utf-8"))
        del doc["sweep_phase"]["sweep_started_utc"]
        p["resident"].write_text(json.dumps(doc), "utf-8")

    def alive(pid: object, started: datetime | None) -> bool | None:
        return None if started is None else True           # as _pid_alive reads it

    for m in range(0, 35, 5):
        t = NOW + timedelta(minutes=m)
        paths = _world(tmp_path, t)
        strip(t, paths)
        d = jsp.run(now=t, root=tmp_path, sender=ch, on_box=True,
                    out=tmp_path / "JUDGE_STALL.json", pid_alive=alive, **paths)
    assert d["incidents"]["sweep_dead"]["open"] is None
    assert d["page"]["opened"] == ["inputs_unmeasured"]
    assert d["incidents"]["inputs_unmeasured"]["incidents"] == ["sweep_dead"]


def test_an_rc0_sweep_that_wrote_no_result_pages_at_its_longer_bound(jsp, tmp_path):
    """run_sharded's early returns exit 0 and write no result: UNMEASURED, then a page."""
    assert jsp.UNMEASURED_BOUND_MIN["zero_judged_sweep"] == 120.0
    ch = Channel()

    def missing(t: datetime, p: dict) -> None:
        p["sweep_result"].unlink()

    docs = _series(jsp, tmp_path, ch, range(0, 120, 5), missing)
    assert docs[6]["incidents"]["zero_judged_sweep"]["open"] is None       # 30 min: no page
    assert ch.sent == []
    d = _series(jsp, tmp_path, ch, [120], missing)[0]
    assert d["page"]["opened"] == ["inputs_unmeasured"]
    assert d["incidents"]["inputs_unmeasured"]["incidents"] == ["zero_judged_sweep"]


def test_a_result_from_another_sweep_reads_unmeasured_and_pages(jsp, tmp_path):
    ch = Channel()

    def stale(t: datetime, p: dict) -> None:            # stamped a day before the last sweep
        p["sweep_result"].write_text(json.dumps({"n_cells": 5, "verdicts": [],
                                                 "swept_at": _iso(t - timedelta(days=1))},
                                                indent=2), "utf-8")

    docs = _series(jsp, tmp_path, ch, range(0, 125, 5), stale)
    assert docs[0]["incidents"]["zero_judged_sweep"]["open"] is None
    assert "inside the last sweep" in docs[0]["incidents"]["zero_judged_sweep"]["why"]
    assert docs[-1]["page"]["opened"] == ["inputs_unmeasured"] and len(ch.sent) == 1


def test_a_flapping_input_pages_and_a_single_torn_read_does_not(jsp, tmp_path):
    ch = Channel()
    # torn on five reads of six inside the window (the clean read is the 4th)
    def flap(t: datetime, p: dict) -> None:
        if t != NOW + timedelta(minutes=15):
            p["resident"].write_text("{torn", "utf-8")

    docs = _series(jsp, tmp_path, ch, range(0, 35, 5), flap)
    assert docs[3]["incidents"]["resident_dead"]["open"] is False          # one clean read
    assert docs[-1]["page"]["opened"] == ["inputs_unmeasured"] and len(ch.sent) == 1
    quiet = tmp_path / "q"
    quiet.mkdir()
    ch2 = Channel()

    def once(t: datetime, p: dict) -> None:
        if t == NOW + timedelta(minutes=15):
            p["resident"].write_text("{torn", "utf-8")

    docs = _series(jsp, quiet, ch2, range(0, 65, 5), once)
    assert all(d["incidents"]["inputs_unmeasured"]["open"] is False for d in docs)
    assert ch2.sent == []


def test_the_done_phase_has_a_short_limit(jsp, tmp_path):
    assert jsp.PHASE_LIMIT_H["done"] == 1.0
    ok = _step(jsp, tmp_path, NOW, Channel(), phase="done", phase_h=0.5)
    assert ok["incidents"]["phase_overrun"]["open"] is False
    hung = _step(jsp, tmp_path, NOW, Channel(), phase="done", phase_h=1.1)
    assert hung["incidents"]["phase_overrun"]["open"] is True
    assert hung["incidents"]["phase_overrun"]["known_phase"] is True


def test_the_sweep_result_is_read_from_its_ends_only(jsp, tmp_path, monkeypatch):
    end = NOW - timedelta(hours=2)
    doc = {"last_sweep_ended_utc": _iso(end), "last_sweep_s": 20_000.0, "last_rc": 0}
    big = tmp_path / "universal_gates_external.json"
    body = {"n_cells": 40_000, "n_judged": 0,
            "verdicts": [{"cell": f"c{i}", "verdict": "FAIL" * 20} for i in range(40_000)],
            "swept_at": _iso(end - timedelta(minutes=30))}
    big.write_text(json.dumps(body, indent=2), "utf-8")
    assert big.stat().st_size > jsp.RESULT_HEAD_BYTES + jsp.RESULT_TAIL_BYTES
    monkeypatch.setattr(json, "loads", lambda *a, **k: pytest.fail("parsed the result"))
    z = jsp._zero_judged(doc, big)
    assert z["open"] is True and z["cells"] == 0 and z["basis"] == "n_judged"
    # a key nested inside a verdict (deeper indent) is never read as the top-level count
    nested = tmp_path / "n.json"
    nested.write_text(json.dumps({"verdicts": [{"n_cells": 0}],
                                  "swept_at": _iso(end - timedelta(minutes=30))}, indent=2),
                      "utf-8")
    assert jsp._zero_judged(doc, nested)["open"] is None


def test_the_prewarm_limit_is_derived_from_the_fresh_budget(jsp, tmp_path, monkeypatch):
    monkeypatch.delenv("GAUNTLET_FRESH_BUDGET_SEC", raising=False)
    tp = tmp_path / "JUDGING_THROUGHPUT.json"
    tp.write_text(json.dumps({"decision": {"fresh_budget_s": 4_000.0}}), "utf-8")
    env = tmp_path / "judging_throughput.env.json"
    assert jsp.fresh_budget_s(tp, env) == (4_000.0, "JUDGING_THROUGHPUT.json "
                                                    "decision.fresh_budget_s")
    assert jsp.phase_limits(4_000.0)["prewarm"] == round(1.5 * 5_100 / 3600, 2)
    paths = _world(tmp_path, NOW, phase="prewarm", phase_h=2.2)
    paths["throughput"] = tp
    d = jsp.measure(NOW, pid_alive=_alive, **paths)
    assert d["incidents"]["phase_overrun"]["open"] is True              # 2.2h > 2.12h
    assert d["thresholds"]["prewarm_budget_s"] == 4_000.0
    paths["throughput"] = tmp_path / "absent.json"
    d2 = jsp.measure(NOW, pid_alive=_alive, **paths)
    assert d2["incidents"]["phase_overrun"]["open"] is False            # 8,640 s -> 4.06h
    assert d2["thresholds"]["prewarm_budget_source"].startswith("UNMEASURED")
    env.write_text(json.dumps({"env": {"GAUNTLET_FRESH_BUDGET_SEC": "6000"}}), "utf-8")
    assert jsp.fresh_budget_s(tmp_path / "absent.json", env)[0] == 6_000.0
    monkeypatch.setenv("GAUNTLET_FRESH_BUDGET_SEC", "7000")
    assert jsp.fresh_budget_s(tmp_path / "absent.json", tmp_path / "no.json")[0] == 7_000.0
    monkeypatch.setenv("GAUNTLET_FRESH_BUDGET_SEC", "nonsense")
    assert jsp.fresh_budget_s(tmp_path / "absent.json", tmp_path / "no.json")[0] == 8_640.0


def test_a_key_pushed_past_the_ends_is_still_read_by_streaming(jsp, tmp_path):
    """external_gauntlet appends keys after swept_at; a big one must not read as UNMEASURED."""
    end = NOW - timedelta(hours=2)
    doc = {"last_sweep_ended_utc": _iso(end), "last_sweep_s": 20_000.0, "last_rc": 0}
    big = tmp_path / "universal_gates_external.json"
    body = {"trial_census": ["x" * 100] * 20_000, "n_judged": 12, "verdicts": [],
            "swept_at": _iso(end - timedelta(minutes=30)),
            "gate_ledger": ["y" * 100] * 5_000}
    big.write_text(json.dumps(body, indent=2), "utf-8")
    z = jsp._zero_judged(doc, big)
    assert z["open"] is False and z["cells"] == 12 and z["read"].startswith("streamed")
    small = tmp_path / "s.json"
    small.write_text(json.dumps({"n_cells": 3, "swept_at": _iso(end)}, indent=2), "utf-8")
    assert jsp._zero_judged(doc, small)["read"] == "streamed top-level lines (the ends cover " \
        "the file)"


# ---- v4 (audit of f4ba99308) ----

def _done(end: datetime) -> dict:
    return {"last_sweep_ended_utc": _iso(end), "last_sweep_s": 20_000.0, "last_rc": 0}


def test_n_cells_in_the_head_never_stands_in_for_a_later_n_judged(jsp, tmp_path):
    """The auditor's probe: 1.3 MB, n_cells 500 second, n_judged 0 after a census block."""
    end = NOW - timedelta(hours=2)
    body = {"hunt": "h", "n_cells": 500, "trial_census": ["c" * 100] * 12_000, "n_judged": 0,
            "verdicts": [], "swept_at": _iso(end - timedelta(minutes=30))}
    f = tmp_path / "r.json"
    f.write_text(json.dumps(body, indent=2), "utf-8")
    assert 1.2e6 < f.stat().st_size < 1.4e6
    z = jsp._zero_judged(_done(end), f)
    assert z["open"] is True and z["cells"] == 0 and z["basis"] == "n_judged"
    assert z["read"].startswith("streamed")
    big = tmp_path / "big.json"                    # past head + tail: the ends miss n_judged
    body["trial_census"] = ["c" * 100] * 20_000
    big.write_text(json.dumps(body, indent=2), "utf-8")
    zb = jsp._zero_judged(_done(end), big)
    assert zb["open"] is True and zb["read"].endswith("(the ends missed a key)")


def test_n_cells_is_used_only_when_the_whole_file_has_no_n_judged(jsp, tmp_path):
    """external_gauntlet's no-gate-1 branch writes n_cells 0 and no n_judged."""
    end = NOW - timedelta(hours=2)
    body = {"n_cells": 0, "big": ["z" * 100] * 15_000, "verdicts": [],
            "swept_at": _iso(end - timedelta(minutes=30))}
    f = tmp_path / "r.json"
    f.write_text(json.dumps(body, indent=2), "utf-8")
    z = jsp._zero_judged(_done(end), f)
    assert z["open"] is True and z["basis"].startswith("n_cells") and z["read"].startswith("str")


@pytest.mark.parametrize("indent", [1, 4, "\t"])
def test_the_top_level_indent_is_read_not_assumed(jsp, tmp_path, indent):
    end = NOW - timedelta(hours=2)
    body = {"meta": {"n_judged": 7, "swept_at": _iso(end)}, "n_judged": 3,
            "verdicts": [{"n_judged": 9}], "swept_at": _iso(end - timedelta(minutes=30))}
    f = tmp_path / "r.json"
    f.write_text(json.dumps(body, indent=indent), "utf-8")
    z = jsp._zero_judged(_done(end), f)
    assert z["cells"] == 3 and z["basis"] == "n_judged"
    compact = tmp_path / "c.json"
    compact.write_text(json.dumps(body), "utf-8")
    c = jsp._zero_judged(_done(end), compact)
    assert c["open"] is None and "unrecognised" in c["why"] and c["read"]


def test_the_tail_drops_its_partial_first_line(jsp, tmp_path):
    """A tail that starts inside a nested line's indent must not read it as top-level."""
    end = NOW - timedelta(hours=2)
    body = {"n_judged": 4, "census": ["c" * 100] * 12_000, "verdicts": [],
            "swept_at": _iso(end - timedelta(minutes=30)),
            "gate_ledger": {"inner": {"swept_at": _iso(end - timedelta(days=3))}}}
    text = json.dumps(body, indent=2).encode()
    cut = text.index(b'      "swept_at"') + 4       # the tail opens with '  "swept_at"'
    assert cut > jsp.RESULT_HEAD_BYTES
    f = tmp_path / "r.json"
    f.write_bytes(text + b"\n" * (cut + jsp.RESULT_TAIL_BYTES - len(text)))
    assert f.stat().st_size - jsp.RESULT_TAIL_BYTES == cut
    ht = jsp._result_head_tail(f)
    assert not ht[1].startswith('  "swept_at"')       # the partial first line is gone
    z = jsp._zero_judged(_done(end), f)
    assert z["open"] is False and z["cells"] == 4


def test_the_unmeasured_branches_all_carry_a_read_field(jsp, tmp_path):
    end = NOW - timedelta(hours=2)
    assert jsp._zero_judged(_done(end), tmp_path / "absent.json")["read"] == "unreadable"
    stale = tmp_path / "s.json"
    stale.write_text(json.dumps({"n_judged": 1, "swept_at": _iso(end - timedelta(days=2))},
                                indent=2), "utf-8")
    z = jsp._zero_judged(_done(end), stale)
    assert z["open"] is None and z["read"]


@pytest.mark.parametrize("raw", [float("inf"), float("nan"), True, "Infinity", "nan", 0, -5])
def test_a_bool_or_non_finite_budget_falls_back_to_the_measured_figure(jsp, tmp_path,
                                                                       monkeypatch, raw):
    monkeypatch.delenv("GAUNTLET_FRESH_BUDGET_SEC", raising=False)
    env = tmp_path / "e.json"
    env.write_text(json.dumps({"env": {"GAUNTLET_FRESH_BUDGET_SEC": raw}}), "utf-8")
    val, src = jsp.fresh_budget_s(tmp_path / "absent.json", env)
    assert val == 8_640.0 and src.startswith("UNMEASURED") and "rejected" in src
    tp = tmp_path / "t.json"
    tp.write_text(json.dumps({"decision": {"fresh_budget_s": raw}}), "utf-8")
    assert jsp.fresh_budget_s(tp, tmp_path / "no.json")[0] == 8_640.0
    limits = jsp.phase_limits(jsp.fresh_budget_s(tp, tmp_path / "no.json")[0])
    assert all(v == v and v < 100 for v in limits.values())      # finite, never NaN


def test_a_rejected_source_falls_through_to_the_next_good_one(jsp, tmp_path, monkeypatch):
    monkeypatch.delenv("GAUNTLET_FRESH_BUDGET_SEC", raising=False)
    tp = tmp_path / "t.json"
    tp.write_text(json.dumps({"decision": {"fresh_budget_s": True}}), "utf-8")
    env = tmp_path / "e.json"
    env.write_text(json.dumps({"env": {"GAUNTLET_FRESH_BUDGET_SEC": "5000"}}), "utf-8")
    assert jsp.fresh_budget_s(tp, env) == (5_000.0, "e.json GAUNTLET_FRESH_BUDGET_SEC")


def test_a_huge_budget_is_capped_at_the_residents_hang_cap(jsp, tmp_path, monkeypatch):
    import re
    src = (REPO / "desks/mt5/scripts/run_sharded_gauntlet.py").read_text("utf-8")
    m = re.search(r"(?m)^RESIDENT_HANG_CAP_S = (\d+) \* 3600\.0", src)
    assert m and float(m.group(1)) * 3600.0 == jsp.RESIDENT_HANG_CAP_S == 48 * 3600.0
    monkeypatch.delenv("GAUNTLET_FRESH_BUDGET_SEC", raising=False)
    tp = tmp_path / "t.json"
    tp.write_text(json.dumps({"decision": {"fresh_budget_s": 1e12}}), "utf-8")
    val, label = jsp.fresh_budget_s(tp, tmp_path / "no.json")
    assert val == jsp.RESIDENT_HANG_CAP_S and "capped at RESIDENT_HANG_CAP_S" in label
    paths = _world(tmp_path, NOW, phase="brand_new_phase", phase_h=jsp.UNKNOWN_PHASE_LIMIT_H + 1)
    paths["throughput"] = tp
    d = jsp.measure(NOW, pid_alive=_alive, **paths)
    assert d["thresholds"]["unknown_phase_limit_h"] == jsp.UNKNOWN_PHASE_LIMIT_H == 18.0
    assert d["thresholds"]["phase_limit_h"]["prewarm"] == 48.0     # never past the hang cap
    assert d["incidents"]["phase_overrun"]["open"] is True      # unknown limit not widened


def test_a_lone_unmeasured_read_after_a_gap_does_not_page(jsp, tmp_path):
    ch = Channel()

    def torn_after_gap(t: datetime, p: dict) -> None:
        if t >= NOW + timedelta(minutes=40):
            p["resident"].write_text("{torn", "utf-8")

    docs = _series(jsp, tmp_path, ch, [0, 40], torn_after_gap)
    assert docs[-1]["incidents"]["inputs_unmeasured"]["open"] is False and ch.sent == []
    d = _series(jsp, tmp_path, ch, [45], torn_after_gap)[0]
    assert d["page"]["opened"] == ["inputs_unmeasured"]
    assert jsp.UNMEASURED_MIN_READS == 2


# ---- v5 (audit of c483ae765) ----

@pytest.mark.parametrize("value", [None, "0", False, True, [0], 0.0, "abc"])
@pytest.mark.parametrize("big", [False, True])
def test_a_present_non_int_n_judged_reads_unmeasured_never_n_cells(jsp, tmp_path, value, big):
    end = NOW - timedelta(hours=2)
    body: dict[str, Any] = {"n_cells": 500}
    if big:
        body["trial_census"] = ["c" * 100] * 20_000      # n_judged past the head: streamed
    body.update({"n_judged": value, "verdicts": [],
                 "swept_at": _iso(end - timedelta(minutes=30))})
    f = tmp_path / "r.json"
    f.write_text(json.dumps(body, indent=2), "utf-8")
    z = jsp._zero_judged(_done(end), f)
    assert z["open"] is None and "not a non-negative int" in z["why"] and z["read"]
    assert "cells" not in z


def test_a_plain_int_n_judged_still_reads(jsp, tmp_path):
    end = NOW - timedelta(hours=2)
    for v, opened in ((0, True), (17, False)):
        f = tmp_path / f"r{v}.json"
        f.write_text(json.dumps({"n_cells": 500, "n_judged": v, "verdicts": [],
                                 "swept_at": _iso(end)}, indent=2), "utf-8")
        z = jsp._zero_judged(_done(end), f)
        assert z["open"] is opened and z["cells"] == v and z["basis"] == "n_judged"


@pytest.mark.parametrize("cadence", [30, 31, 45, 60, 120])
@pytest.mark.parametrize("which", ["resident", "zero_judged_sweep"])
def test_persistent_unmeasured_pages_whatever_the_run_spacing(jsp, tmp_path, cadence, which):
    """48 straight UNMEASURED runs at or past the window: two in a row must page."""
    ch = Channel()

    def gone(t: datetime, p: dict) -> None:
        if which == "resident":
            p["resident"].write_text("{torn", "utf-8")
        else:
            p["sweep_result"].unlink()

    docs = _series(jsp, tmp_path, ch, [i * cadence for i in range(48)], gone)
    opened = [i for i, d in enumerate(docs) if "inputs_unmeasured" in d["page"]["opened"]]
    assert opened, f"never paged at a {cadence}-min cadence"
    bound = jsp._bound_min("zero_judged_sweep" if which != "resident" else "resident_dead")
    assert opened[0] * cadence <= max(bound, cadence) + cadence  # by the 2nd read past bound
    assert len(ch.sent) >= 1


def test_spaced_runs_with_one_clean_reading_between_do_not_page(jsp, tmp_path):
    """Spaced runs need two UNMEASURED in a row; a window with enough reads keeps the flap rule."""
    ch = Channel()

    def alternate(t: datetime, p: dict) -> None:
        if int((t - NOW).total_seconds() // 3600) % 2:
            p["resident"].write_text("{torn", "utf-8")

    docs = _series(jsp, tmp_path, ch, [i * 60 for i in range(12)], alternate)
    # resident_dead's 30-min window holds one reading, and its predecessor is clean every time
    assert all("resident_dead" not in (d["incidents"]["inputs_unmeasured"].get("incidents")
                                       or ()) for d in docs)
    # zero_judged_sweep's 120-min window holds two, so the FLAP rule judges it: torn on half
    # its reads is the share that pages (unchanged since v3)
    assert docs[-1]["incidents"]["inputs_unmeasured"]["incidents"] == ["zero_judged_sweep"]


def test_the_prewarm_limit_never_exceeds_the_hang_cap(jsp):
    assert jsp.phase_limits(jsp.RESIDENT_HANG_CAP_S)["prewarm"] == 48.0
    assert jsp.phase_limits(8_640.0)["prewarm"] == round(1.5 * 9_740 / 3600, 2)
    assert jsp.phase_limits(1e9)["prewarm"] == 48.0


# ---- v6 (audit of 98bb7726c) ----

@pytest.mark.parametrize("big", [False, True])
@pytest.mark.parametrize("key", ["n_judged", "n_cells"])
def test_a_negative_count_reads_unmeasured(jsp, tmp_path, big, key):
    end = NOW - timedelta(hours=2)
    body: dict[str, Any] = {"hunt": "h"}
    if big:
        body["trial_census"] = ["c" * 100] * 20_000
    body.update({key: -1, "verdicts": [], "swept_at": _iso(end - timedelta(minutes=30))})
    f = tmp_path / "r.json"
    f.write_text(json.dumps(body, indent=2), "utf-8")
    z = jsp._zero_judged(_done(end), f)
    assert z["open"] is None and "cells" not in z
    assert jsp._count("-0") == 0 and jsp._count("-1") is None


def test_conflicting_duplicate_n_judged_reads_unmeasured(jsp, tmp_path):
    end = NOW - timedelta(hours=2)
    stamp = _iso(end - timedelta(minutes=30))
    f = tmp_path / "r.json"
    f.write_text('{\n  "n_judged": 5,\n  "verdicts": [],\n  "n_judged": 0,\n'
                 f'  "swept_at": "{stamp}"\n}}\n', "utf-8")
    z = jsp._zero_judged(_done(end), f)
    assert z["open"] is None and "conflicting duplicates" in z["why"]
    same = tmp_path / "s.json"
    same.write_text('{\n  "n_judged": 0,\n  "n_judged": 0,\n'
                    f'  "swept_at": "{stamp}"\n}}\n', "utf-8")
    assert jsp._zero_judged(_done(end), same)["open"] is True       # agreeing duplicates read


def test_the_head_drops_its_cut_last_line(jsp, tmp_path):
    """A value straddling RESULT_HEAD_BYTES must not read as its truncation."""
    end = NOW - timedelta(hours=2)
    prefix = '{\n  "hunt": "'
    line = '  "n_judged": 10.5,\n'
    # place the cut just after '  "n_judged": 1'
    fill = jsp.RESULT_HEAD_BYTES - len(prefix) - len('",\n') - len('  "n_judged": 1')
    text = (prefix + "h" * fill + '",\n' + line + '  "big": "' + "b" * 400_000 + '",\n'
            f'  "swept_at": "{_iso(end - timedelta(minutes=30))}"\n}}\n')
    f = tmp_path / "r.json"
    f.write_text(text, "utf-8")
    cut_at = text.encode().index(b'"n_judged": 1') + len('"n_judged": 1')
    assert cut_at == jsp.RESULT_HEAD_BYTES              # the head ends on '...: 1' of '10.5'
    head = jsp._result_head_tail(f)[0]
    assert '"n_judged"' not in head and head.endswith("\n")
    z = jsp._zero_judged(_done(end), f)
    assert z["open"] is None and z["read"].startswith("streamed")      # 10.5, not 1


def test_a_gap_past_keep_keeps_the_predecessor_but_the_flap_rule_waits_a_full_bound(
        jsp, tmp_path):
    """clean, a 250-min gap, then UNMEASURED every 10 min (v6.1, audit of 1927577c1).

    The pre-gap reading is kept as a predecessor only. It is clean, so the consecutive rule
    does not fire, and it never makes the window full for the flap rule: that takes a recent
    reading a full bound back, so the page comes once the streak spans the 30-min bound."""
    ch = Channel()

    def torn_after(t: datetime, p: dict) -> None:
        if t > NOW:
            p["resident"].write_text("{torn", "utf-8")

    docs = _series(jsp, tmp_path, ch, [0, 250, 260, 270, 280], torn_after)
    assert [d["page"]["opened"] for d in docs[:4]] == [[], [], [], []]
    assert docs[4]["page"]["opened"] == ["inputs_unmeasured"]          # 250 -> 280: one bound
    hist = _state(jsp, tmp_path)["unmeasured_hist"]["resident_dead"]
    assert hist[0][0] == _iso(NOW)                       # the reading before the gap is kept


def test_an_old_unmeasured_predecessor_never_enters_the_flap_window(jsp, tmp_path):
    """The auditor's probe: UNMEASURED at t0, clean at +3d, UNMEASURED at +3d5m: no page."""
    ch = Channel()
    t3d = 3 * 24 * 60

    def probe(t: datetime, p: dict) -> None:
        if t in (NOW, NOW + timedelta(minutes=t3d + 5)):
            p["resident"].write_text("{torn", "utf-8")

    docs = _series(jsp, tmp_path, ch, [0, t3d, t3d + 5], probe)
    assert all(d["incidents"]["inputs_unmeasured"]["open"] is False for d in docs)
    assert ch.sent == []
    # and an old UNMEASURED predecessor still pairs with a lone spaced UNMEASURED reading
    ch2 = Channel()
    other = tmp_path / "o"
    other.mkdir()

    def both(t: datetime, p: dict) -> None:
        p["resident"].write_text("{torn", "utf-8")

    d = _series(jsp, other, ch2, [0, t3d], both)[-1]
    assert d["page"]["opened"] == ["inputs_unmeasured"]
