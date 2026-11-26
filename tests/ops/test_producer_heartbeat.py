"""The producer heartbeat and the soft leg deadline (2026-11-25 producer triage).

Pins: every run row carries start/end/status/rows_out/artifacts_moved; every producer gets ONE
named status from the closed vocabulary (never UNMEASURED); a manifest task with no contract is
NO_CONTRACT by name; the hourly and daily runners call it at their leg boundary; the summary is
published off-box; the harness exports the absolute deadline and producers can read it.
"""
from __future__ import annotations

import json
import math
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.ops import leg_deadline as ld
from libs.ops import producer_heartbeat as hb

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


# ------------------------------------------------------------------------------ the writer
def test_rows_out_reads_the_result_dict_and_the_stdout_marker() -> None:
    assert hb.rows_out({"donated_rows": 12}) == 12
    assert hb.rows_out({"cells_proposed": 3, "exit_code": 0}) == 3
    assert hb.rows_out({"tail": "noise\nPRODUCER_ROWS_OUT: 41\n"}) == 41
    assert hb.rows_out({"tail": "PRODUCER_ROWS_OUT: 2\nPRODUCER_ROWS_OUT: 9"}) == 9
    assert hb.rows_out({"exit_code": 0, "tail": "done"}) is None
    assert hb.rows_out({"donated": True}) is None              # a bool is not a count
    assert hb.rows_out("not a dict") is None


def test_run_status_maps_every_contract_verdict_and_falls_back_to_the_result() -> None:
    assert hb.run_status("OK") == hb.RUN_OK
    assert hb.run_status("LEG_TIMEOUT") == hb.RUN_TIMEOUT
    assert hb.run_status("LEG_FAILED") == hb.RUN_ERROR
    assert hb.run_status("SILENT_NO_OP") == hb.RUN_SILENT
    assert hb.run_status("DECLARED_NO_OP") == hb.RUN_NO_INPUT
    assert hb.run_status("SKIPPED") == hb.RUN_SKIPPED
    assert hb.run_status(None, {"timeout_s": 720, "exit_code": None}) == hb.RUN_TIMEOUT
    assert hb.run_status(None, {"exit_code": 3}) == hb.RUN_ERROR
    assert hb.run_status(None, {"error": "boom"}) == hb.RUN_ERROR
    assert hb.run_status(None, {"status": "ROTATED_OUT"}) == hb.RUN_SKIPPED
    assert hb.run_status(None, {"ok": True}) == hb.RUN_OK


def test_beat_writes_start_end_status_rows_and_artifacts(tmp_path: Path) -> None:
    ledger = tmp_path / "hb.jsonl"
    started = datetime.now(UTC) - timedelta(seconds=5)
    row = hb.beat("qd_frontier", started=started, result={"exit_code": 0, "tail":
                                                           "PRODUCER_ROWS_OUT: 7"},
                  woe={"verdict": "OK", "wrote": ["a.json", "b.json"]}, ledger=ledger,
                  publish=False)
    assert row["recorded"] is True
    got = [json.loads(x) for x in ledger.read_text("utf-8").splitlines()]
    assert len(got) == 1
    rec = got[0]
    for key in ("producer", "started_at", "ended_at", "wall_s", "status", "rows_out",
                "artifacts_moved"):
        assert key in rec, key
    assert rec["status"] == "ok" and rec["rows_out"] == 7 and rec["artifacts_moved"] == 2
    assert rec["wall_s"] >= 5


def test_the_writer_never_raises_and_never_writes_desk_state_under_a_test(
        tmp_path: Path, monkeypatch) -> None:
    blocked = tmp_path / "a_file"
    blocked.write_text("x", encoding="utf-8")
    assert hb.record({"producer": "x"}, ledger=blocked / "nested" / "hb.jsonl") is False
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "t")
    monkeypatch.delenv("PRODUCER_HEARTBEAT_LEDGER", raising=False)
    assert hb.record({"producer": "x"}) is False
    assert hb.maybe_publish() is False


# ------------------------------------------------------------------------------ the judge
def _runs(*specs: tuple[float, str]) -> list[dict]:
    return [{"producer": "leg", "ended_at": _iso(NOW - timedelta(hours=h)), "status": s}
            for h, s in specs]


def test_a_leg_gets_exactly_one_named_status() -> None:
    assert hb.judge_leg(_runs((30, "ok"), (2, "ok")), NOW)["status"] == hb.OK
    assert hb.judge_leg(_runs((2, "timeout"), (1, "timeout")), NOW)["status"] == hb.TIMEOUT
    assert hb.judge_leg(_runs((1, "error")), NOW)["status"] == hb.ERROR
    assert hb.judge_leg(_runs((1, "silent_no_op")), NOW)["status"] == hb.SILENT
    assert hb.judge_leg(_runs((1, "skipped_no_input")), NOW)["status"] == hb.NO_INPUT
    assert hb.judge_leg(_runs((30, "ok")), NOW)["status"] == hb.STALE
    assert hb.judge_leg(_runs((100, "ok")), NOW)["status"] == hb.DEAD
    assert hb.judge_leg([], NOW)["status"] == hb.DEAD
    # a skipped run (plan / rotation) decides nothing: the earlier truth stands
    assert hb.judge_leg(_runs((30, "ok"), (1, "skipped")), NOW)["status"] == hb.STALE


def test_build_names_every_producer_and_never_says_unmeasured(tmp_path: Path) -> None:
    ledger = _write_jsonl(tmp_path / "hb.jsonl", [
        {"producer": "axis_registry", "ended_at": _iso(NOW - timedelta(hours=1)),
         "status": "timeout"},
        {"producer": "qd_frontier", "ended_at": _iso(NOW - timedelta(hours=1)),
         "status": "ok", "rows_out": 4, "artifacts_moved": 3},
    ])
    woe = _write_jsonl(tmp_path / "woe.jsonl", [
        {"leg": "graveyard_resurrection", "at": _iso(NOW - timedelta(hours=2)),
         "verdict": "LEG_TIMEOUT", "wrote": []}])
    seat_root = tmp_path / "intelligence"
    fresh = seat_root / "fresh_seat"
    fresh.mkdir(parents=True)
    (fresh / "discoveries_1.jsonl").write_text('{"a":1}\n{"a":2}\n', encoding="utf-8")
    old = seat_root / "quiet_seat"
    old.mkdir()
    f = old / "discoveries_0.json"
    f.write_text("[]", encoding="utf-8")
    stamp = (NOW - timedelta(hours=200)).timestamp()
    os.utime(f, (stamp, stamp))
    for p in (fresh / "discoveries_1.jsonl",):
        t = (NOW - timedelta(hours=1)).timestamp()
        os.utime(p, (t, t))
    manifest = tmp_path / "box_tasks.manifest"
    manifest.write_text('TASK name="MT5-NoContractThing" trigger="hourly" runs="x.py"\n'
                        'TASK name="MT5-Hourly" trigger="hourly" runs="y.py"\n', encoding="utf-8")
    doc = hb.build(NOW, ledger=ledger, woe_ledger=woe, seat_roots=(seat_root,),
                   manifest=manifest)
    by = {(r["kind"], r["producer"]): r for r in doc["producers"]}
    assert by[("leg", "axis_registry")]["status"] == hb.TIMEOUT
    assert by[("leg", "qd_frontier")]["status"] == hb.OK
    assert by[("leg", "qd_frontier")]["rows_out_window"] == 4
    assert by[("leg", "graveyard_resurrection")]["status"] == hb.TIMEOUT      # history backfill
    assert by[("seat", "fresh_seat")]["status"] == hb.OK
    assert by[("seat", "fresh_seat")]["rows_window"] == 2
    assert by[("seat", "quiet_seat")]["status"] == hb.DEAD
    assert by[("box_task", "MT5-NoContractThing")]["status"] == hb.NO_CONTRACT
    assert ("box_task", "MT5-Hourly") in by                   # contracted: judged, not omitted
    assert by[("box_task", "MT5-Hourly")]["status"] != hb.NO_CONTRACT
    for r in doc["producers"]:
        assert r["status"] in hb.STATUSES, r
        assert "UNMEASURED" not in str(r["status"])
        assert r.get("why"), r
    assert sum(doc["counts"].values()) == doc["n_producers"]
    json.dumps(doc)                                           # publishable as is


def test_the_residents_and_research_tasks_are_contracted() -> None:
    import sys
    sys.path.insert(0, str(ROOT / "ops"))
    import organ_contract as oc
    for task in ("MT5-Forest-Africa", "MT5-Forest-Asean", "MT5-Forest-China",
                 "MT5-Forest-Europe", "MT5-Forest-Korea", "MT5-Forest-Latam", "MT5-Forest-Mena",
                 "MT5-Forest-NorthAmerica", "MT5-Forest-Oceania", "MT5-Forest-RussiaCis",
                 "MT5-Forest-SouthAsia", "MT5-Dept-Mathlab", "MT5-DeepSeek",
                 "Quant-SideChannelMiners", "MT5-ResearchSupervisor"):
        assert task in oc.CONTRACTS, task
    import importlib.util

    from libs.ops.control_plane import watermarks as wm
    name = "_quant_heartbeat_components"
    spec = importlib.util.spec_from_file_location(name, ROOT / "desks" / "mt5" / "ops"
                                                  / "components.py")
    assert spec and spec.loader
    comp = importlib.util.module_from_spec(spec)
    sys.modules[name] = comp            # dataclasses resolve their module by name
    spec.loader.exec_module(comp)
    for task, rel in ((t, oc.CONTRACTS[t][0]) for t in oc.CONTRACTS
                      if t.startswith(("MT5-Forest-", "MT5-Dept-Mathlab"))
                      and " (" not in t):     # "Task (organ)" rows contract an artifact, not a task
        # the contract names exactly the file the resident's watermark writes
        cid = comp.TASK_CANONICAL[task]
        assert (ROOT / rel) == wm.path_for(cid), task
        assert oc.INTERNAL_STAMPS[rel] == "at", task


# ------------------------------------------------------------------------------ the wiring
def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8", errors="replace")


def test_both_cycles_beat_at_their_leg_boundary() -> None:
    hourly = _src("desks/mt5/research/hourly_cycle.py")
    costed = hourly.split("def _costed(", 1)[1].split("\ndef ", 1)[0]
    assert costed.count("_heartbeat(name, _hb_t0") == 2            # the ok path and the raise
    assert "from libs.ops.producer_heartbeat import beat" in hourly
    daily = _src("desks/mt5/research/daily_cycle.py")
    step = daily.split("def run_step(", 1)[1].split("\ndef ", 1)[0]
    assert "_beat(name, started, out" in step
    proposers = daily.split("def _proposers(", 1)[1].split("\ndef ", 1)[0]
    assert proposers.count("_beat(name, _t0") == 2


def test_the_summary_rides_the_box_state_sync() -> None:
    assert '"desks/mt5/reports/PRODUCER_HEARTBEAT.json"' in _src(
        "desks/mt5/scripts/sync_shadow_to_git.ps1")
    assert "!desks/mt5/reports/PRODUCER_HEARTBEAT.json" in _src(".gitignore")


def test_the_harness_exports_the_absolute_deadline() -> None:
    hourly = _src("desks/mt5/research/hourly_cycle.py")
    impl = hourly.split("def _producer_impl(", 1)[1].split("\ndef ", 1)[0]
    assert '"QUANT_LEG_DEADLINE_TS": f"{time.time() + budget:.3f}"' in impl
    auto = hourly.split("def _auto_leg(", 1)[1].split("\ndef ", 1)[0]
    assert '"QUANT_LEG_DEADLINE_TS"' in auto


# ------------------------------------------------------------------------------ the deadline
def test_deadline_left_prefers_the_absolute_instant() -> None:
    now = 1_000_000.0
    env = {ld.ENV_DEADLINE: str(now + 120), ld.ENV_BUDGET: "9999"}
    assert ld.deadline_left(0, environ=env, now=now) == 120
    assert ld.deadline_left(30, environ=env, now=now) == 90
    assert not ld.expired(60, environ=env, now=now)
    assert ld.expired(60, environ=env, now=now + 61)
    assert math.isinf(ld.deadline_left(environ={}, now=now))
    assert not ld.expired(environ={}, now=now)
    assert math.isinf(ld.deadline_left(environ={ld.ENV_DEADLINE: "garbage"}, now=now))


def test_a_bare_budget_still_gives_a_deadline() -> None:
    left = ld.deadline_left(0, environ={ld.ENV_BUDGET: "300"})
    assert 0 < left <= 300


def test_env_for_and_own_budget() -> None:
    env = ld.env_for(600, now=50.0)
    assert env == {ld.ENV_BUDGET: "600", ld.ENV_DEADLINE: "650.000"}
    assert ld.own_budget(240, 0, environ={ld.ENV_DEADLINE: str(time.time() + 100)}) <= 100
    assert ld.own_budget(240, 0, environ={}) == 240
    assert ld.own_budget(None, 0, environ={}) is None


def test_publish_partial_and_cursor(tmp_path: Path) -> None:
    out = tmp_path / "r" / "REPORT.json"
    assert ld.publish_partial(out, {"n": 3})
    doc = json.loads(out.read_text("utf-8"))
    assert doc["partial"] is True and doc["stopped_by"] == "deadline" and doc["generated_utc"]
    assert ld.publish_partial(out, {"n": 4}, complete=True)
    assert json.loads(out.read_text("utf-8"))["partial"] is False
    cur = ld.Cursor(tmp_path / "c.json")
    assert cur.load() == {}
    assert cur.save({"offset": 17})
    assert cur.load()["offset"] == 17
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    assert ld.Cursor(tmp_path / "bad.json").load() == {}
