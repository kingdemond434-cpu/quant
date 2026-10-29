"""The box compute ledger (libs/ops/box_compute_ledger.py): organs, deltas, days and the ranking."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.ops import box_compute_ledger as cl
from libs.ops.box_shaper import Proc

NOON = datetime(2026, 10, 29, 12, tzinfo=UTC)


def _procs(cpu: float = 100.0, io: float = 10.0) -> list[Proc]:
    return [
        Proc(1, "python.exe", ppid=0, cmdline=r"python.exe -u C:\q\scripts\run_sharded_gauntlet.py",
             group="judge", create_time=10, cpu_s=cpu, io_mb=io, rss_mb=500),
        # a shard `-c` child books to the launcher
        Proc(2, "python.exe", ppid=1, cmdline="python.exe -u -c import sys; shard_worker(1)",
             group="judge", create_time=11, cpu_s=cpu * 2, io_mb=io, rss_mb=900),
        # a pool worker of a miner books to the miner
        Proc(3, "python.exe", ppid=4, cmdline="python.exe -c from multiprocessing.spawn import x",
             group="mining", create_time=12, cpu_s=cpu, io_mb=0, rss_mb=100),
        Proc(4, "python.exe", ppid=0, cmdline=r"python.exe C:\q\desks\mt5\moat\moat_miner.py",
             group="mining", create_time=9, cpu_s=cpu, io_mb=0, rss_mb=200),
        Proc(5, "python.exe", ppid=0, cmdline="python.exe -m libs.ops.state_publication --watch",
             group="other", create_time=9, cpu_s=cpu / 10, io_mb=0, rss_mb=50),
        Proc(6, "MsMpEng.exe", group="system", create_time=1, cpu_s=cpu, rss_mb=300),
    ]


def _box(procs: list[Proc], extra: float = 0.0) -> float:
    """The box's cumulative CPU seconds when every second is a measured process's (+ extra)."""
    return sum(p.cpu_s for p in procs) + extra


def test_every_process_lands_on_a_named_organ() -> None:
    got = cl.attribute(_procs())
    assert got[1] == got[2] == "judge:run_sharded_gauntlet"
    assert got[3] == got[4] == "mining:moat_miner"
    assert got[5] == "other:libs.ops.state_publication"
    assert got[6] == "system:msmpeng"


def test_the_first_pass_is_a_baseline_and_later_passes_book_deltas() -> None:
    first, state = cl.pass_delta(_procs(100, 10), None)
    assert state["baseline"] is True
    assert all(v["core_s"] == 0 for v in first.values())
    last = {"at_epoch": 50.0, "totals": state["totals"]}
    later = [*_procs(160, 15), Proc(7, "python.exe", cmdline="python.exe new_organ.py",
                                     group="other", create_time=60, cpu_s=30)]
    delta, _ = cl.pass_delta(later, last)
    assert delta["judge:run_sharded_gauntlet"]["core_s"] == 60 + 120
    assert delta["judge:run_sharded_gauntlet"]["io_mb"] == 10
    assert delta["other:new_organ"]["core_s"] == 30          # born since the last pass
    # a reused pid (new creation time) never inherits the old process's total
    reused = [Proc(4, "python.exe", cmdline="python.exe moat_miner.py", group="mining",
                   create_time=40, cpu_s=500)]
    delta, _ = cl.pass_delta(reused, last)
    assert delta["mining:moat_miner"]["core_s"] == 0         # alive before last pass, unseen: none


def test_days_accumulate_and_only_seven_are_kept() -> None:
    led: dict[str, object] = {}
    for d in range(1, 10):
        led = {"days": cl.accumulate(led, {"judge:x": {"core_s": 3600.0, "io_mb": 1.0,
                                                       "rss_mb": 5.0, "n": 1}},
                                     f"2026-10-{d:02d}")}
    days = led["days"]
    assert isinstance(days, dict) and sorted(days)[0] == "2026-10-03" and len(days) == 7
    twice = cl.accumulate({"days": days}, {"judge:x": {"core_s": 3600.0, "io_mb": 1.0,
                                                        "rss_mb": 9.0, "n": 1}}, "2026-10-09")
    assert twice["2026-10-09"]["organs"]["judge:x"] == {"core_s": 7200.0, "io_mb": 2.0,
                                                        "rss_mb_peak": 9.0, "passes_seen": 2}


def test_yield_ranks_first_and_unmeasured_says_so(tmp_path: Path) -> None:
    (tmp_path / "r").mkdir()
    (tmp_path / "r" / "J.json").write_text(json.dumps(
        {"rate": {"verdicts_per_day": 7200, "at": "2026-10-29T11:30:00+00:00"}}))
    (tmp_path / "r" / "BAD.json").write_text(json.dumps({"rate": {"verdicts_per_day":
                                                                    "UNMEASURED"}}))
    cfg = {"outputs": {"judge": {"unit": "verdicts", "sources": [
        {"file": "r/BAD.json", "path": ["rate", "verdicts_per_day"]},
        {"file": "r/J.json", "path": ["rate", "verdicts_per_day"], "at_path": ["rate", "at"]}]}}}
    outs = cl.outputs(cfg, tmp_path, NOON)
    assert outs["judge"]["per_day"] == 7200 and outs["judge"]["source"].startswith("r/J.json")
    day = {"organs": {"judge:run_sharded_gauntlet": {"core_s": 36000.0},
                      "mining:moat_miner": {"core_s": 72000.0},
                      "other:tiny": {"core_s": 360.0}}}
    ranked = cl.rank(day, outs)
    assert ranked[0]["organ"] == "judge:run_sharded_gauntlet"
    assert ranked[0]["output_per_core_hour"] == 720.0
    assert [r["organ"] for r in ranked[1:]] == ["mining:moat_miner", "other:tiny"]
    assert ranked[1]["output"].startswith("UNMEASURED")
    assert ranked[1]["output_per_core_hour"] is None


def test_update_writes_the_ledger_and_never_acts(tmp_path: Path) -> None:
    path = tmp_path / "BOX_COMPUTE_LEDGER.json"
    t0 = datetime(2026, 10, 29, 12, tzinfo=UTC)
    first = cl.update(_procs(100), {}, now=t0, path=path, repo=tmp_path)
    assert first["baseline_pass"] is True
    second = cl.update(_procs(400), {}, now=t0.replace(minute=10), path=path, repo=tmp_path)
    doc = json.loads(path.read_text())
    assert second["baseline_pass"] is False and doc["authority"] == "report_only"
    assert doc["days"]["2026-10-29"]["organs"]["judge:run_sharded_gauntlet"]["core_s"] == 900.0
    assert doc["free_cpu_first"][0]["organ"] == "judge:run_sharded_gauntlet"


def test_a_stale_or_undated_output_is_unmeasured(tmp_path: Path) -> None:
    """#493 S2: an output older than max_age_s (2x its hourly cadence) is no output."""
    f = tmp_path / "J.json"
    cfg = {"outputs": {"judge": {"unit": "verdicts", "max_age_s": 7200, "sources": [
        {"file": "J.json", "path": ["verdicts_per_day"], "at_path": ["at"]}]}}}
    f.write_text(json.dumps({"verdicts_per_day": 9000, "at": "2026-10-29T08:59:00Z"}))
    out = cl.outputs(cfg, tmp_path, NOON)["judge"]
    assert out["per_day"] is None and "stale" in out["why"]
    f.write_text(json.dumps({"verdicts_per_day": 9000}))
    out = cl.outputs(cfg, tmp_path, NOON)["judge"]
    assert out["per_day"] is None and "timestamp" in out["why"]
    f.write_text(json.dumps({"verdicts_per_day": 9000, "at": "2026-10-29T10:30:00Z"}))
    assert cl.outputs(cfg, tmp_path, NOON)["judge"]["per_day"] == 9000
    day = {"organs": {"judge:x": {"core_s": 3600.0}}}
    stale = {"judge": {"per_day": None, "unit": "verdicts", "why": "J.json: stale"}}
    assert cl.rank(day, stale)[0]["output"] == "UNMEASURED: J.json: stale"


def test_yield_waits_for_a_window_that_matches_the_output(tmp_path: Path) -> None:
    """#493 S1: a 24 h count is divided only by 24 h of core-seconds."""
    (tmp_path / "J.json").write_text("{}")
    path = tmp_path / "L.json"
    cfg = {"outputs": {"judge": {"unit": "verdicts", "sources": [
        {"file": "J.json", "path": ["verdicts_per_day"]}]}}}
    from datetime import timedelta
    t = NOON
    for i in range(25):                       # one pass an hour for a day, 360 core-s each time
        (tmp_path / "J.json").write_text(json.dumps(
            {"verdicts_per_day": 2400, "at": t.isoformat()}))
        procs = _procs(100 + 60 * i)
        cl.update(procs, cfg, now=t, path=path, repo=tmp_path, box_cpu_s=_box(procs))
        doc = json.loads(path.read_text())
        judge = next(r for r in doc["free_cpu_first"]
                     if r["organ"] == "judge:run_sharded_gauntlet")
        if i < 23:
            assert judge["output_per_core_hour"] is None, i
            assert "window observed" in judge["output"]
        t += timedelta(hours=1)
    assert doc["window"]["covered_h"] == 24.0 and len(doc["hours"]) == cl.KEEP_HOURS
    # 24 hourly buckets x 180 core-s for the judge launcher + shard = 4320 s = 1.2 core-h
    assert doc["window"]["organs"]["judge:run_sharded_gauntlet"]["core_s"] == 4320.0
    assert judge["output_per_core_hour"] == 2000.0


def test_an_exited_process_is_counted_not_guessed(tmp_path: Path) -> None:
    """#493 S3: what an exiting process spent after the last pass is unreadable; it is counted."""
    path = tmp_path / "L.json"
    cl.update(_procs(100), {}, now=NOON, path=path, repo=tmp_path)
    cl.update(_procs(200), {}, now=NOON.replace(minute=10), path=path, repo=tmp_path)
    cl.update(_procs(300)[:4], {}, now=NOON.replace(minute=20), path=path, repo=tmp_path)
    assert json.loads(path.read_text())["exited_since_last_pass"] == 2


def _judge_cfg(tmp_path: Path) -> dict[str, Any]:
    return {"outputs": {"judge": {"unit": "verdicts", "sources": [
        {"file": "J.json", "path": ["verdicts_per_day"]}]}}}


def _judge_row(doc: dict[str, Any]) -> dict[str, Any]:
    return next(r for r in doc["free_cpu_first"] if r["organ"] == "judge:run_sharded_gauntlet")


def test_an_outage_is_not_coverage_and_old_buckets_leave_the_window(tmp_path: Path) -> None:
    """#493 MF1 repro: hourly passes with a 10 h outage. Before: covered_h read 24.0, the
    window was the last 24 buckets however old, and the yield was published (overstated)."""
    from datetime import timedelta
    path = tmp_path / "L.json"
    cfg = _judge_cfg(tmp_path)
    t, cum = NOON, 100.0
    hours = [h for h in range(31) if not 10 < h < 20]      # passes at 0..10, then 20..30
    for h in hours:
        t = NOON + timedelta(hours=h)
        (tmp_path / "J.json").write_text(json.dumps({"verdicts_per_day": 2400,
                                                     "at": t.isoformat()}))
        cum += 60
        procs = _procs(cum)
        cl.update(procs, cfg, now=t, path=path, repo=tmp_path, box_cpu_s=_box(procs))
        doc = json.loads(path.read_text())
        if h == 20:
            assert doc["baseline_pass"] is True and doc["gap_s"] == 10 * 3600.0
    # window = hours 7..30 wall; observed: 7..10 (4 h) and 21..30 (10 h) = 14 h
    assert doc["window"]["covered_h"] == 14.0
    judge = _judge_row(doc)
    assert judge["output_per_core_hour"] is None and "observed 14.0 h" in judge["output"]
    end = NOON + timedelta(hours=30)
    assert all(cl.in_window(k, end) for k in doc["hours"])
    assert all(cl.in_window(k, end) for k in doc["observed"])
    # the restarted spend after the outage is not booked into any hour: re-baselined
    gap_hour = (NOON + timedelta(hours=20)).strftime("%Y-%m-%dT%H")
    assert all(v["core_s"] == 0.0 for v in doc["hours"][gap_hour].values())
    assert doc["observed"][gap_hour]["s"] == 0.0


def test_short_lived_spend_marks_yield_unmeasured(tmp_path: Path) -> None:
    """#493 SF1 repro: judge shards under 10 min are never booked; the box's own CPU time shows
    the unbooked spend and the yield is UNMEASURED, never overstated."""
    from datetime import timedelta
    cfg = _judge_cfg(tmp_path)
    for extra_per_pass, box_known, measured in ((0.0, True, True), (200.0, True, False),
                                                (0.0, False, False)):
        path = tmp_path / f"L{extra_per_pass}{box_known}.json"
        t = NOON
        for i in range(25):
            (tmp_path / "J.json").write_text(json.dumps({"verdicts_per_day": 2400,
                                                         "at": t.isoformat()}))
            procs = _procs(100 + 60 * i)
            box = _box(procs, extra_per_pass * i) if box_known else None
            cl.update(procs, cfg, now=t, path=path, repo=tmp_path, box_cpu_s=box)
            t += timedelta(hours=1)
        doc = json.loads(path.read_text())
        judge = _judge_row(doc)
        assert (judge["output_per_core_hour"] is not None) is measured, (extra_per_pass,
                                                                         box_known)
        if not measured:
            assert "short-lived processes unmeasured" in judge["output"]
        if extra_per_pass:
            # 200 of 566 core-s a pass were booked to no organ
            assert doc["window"]["unbooked_share"] == round(200 / 566, 4)
