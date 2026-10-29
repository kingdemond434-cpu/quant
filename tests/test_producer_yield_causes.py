"""WHY A PRODUCER IS DEAD -- the cause column of PRODUCER_YIELD (principal, 2026-10-29).

PRODUCER_YIELD read 91 of 137 producers DEAD and 75 of them "replacement: NONE DECLARED": the
symptom, with the remedy left to whoever read it. Every DEAD/UNMEASURED row now carries one cause
from a fixed vocabulary, the detail that named it and the evidence it was read from. These tests
pin the properties that make the column worth reading:

  * every cause is from `CAUSES`, and a producer whose evidence is unreadable is
    UNMEASURED_CAUSE -- never the likeliest-looking cause (L1.28a);
  * the classifier never lifts a wall: a robots/403/anti-bot refusal is FETCH_FAILURE;
  * output written somewhere the seat count does not look is PRODUCING, not DEAD;
  * the box legs the revival added exist, and the rosters the cause column trusts match the
    code that actually writes the seats.

Every test builds its own evidence; none reads the box's live artifacts.
"""
from __future__ import annotations

import ast
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from scripts import check_producer_yield as fence

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"


def _ev(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"window_h": 72.0, "legs": {}, "seat_legs": {}, "clocks": {},
                            "ledger": {"available": False, "last": {}, "path": "ledger"},
                            "ship": {"ref": fence.SHIP_REF, "last_commit": None},
                            "walls": {}, "platforms": {}, "blocked": {}, "bars": {}}
    base.update(over)
    return base


def _now(hours_ago: float = 0.0) -> str:
    return (datetime.now(UTC) - timedelta(hours=hours_ago)).isoformat(timespec="seconds")


def test_every_cause_is_from_the_vocabulary_and_the_default_names_no_guess() -> None:
    got = fence.cause_of("orphan_organ", None, _ev())
    assert got["cause"] in fence.CAUSES
    assert (got["cause"], got["cause_detail"]) == ("SCHEDULE", "NO_CLOCK")
    # Clocked here, but the run record is unreadable: that is a measurement gap, not a verdict.
    got = fence.cause_of("organ", None, _ev(legs={"organ": {"organ"}}))
    assert got["cause"] == fence.UNMEASURED_CAUSE and got["cause_detail"] == "LEDGER_UNREADABLE"


@pytest.mark.parametrize(("outcome", "cause", "detail"), [
    ("TIMEOUT", "SCHEDULE", "BUDGET_KILLED_BEFORE_WRITE"),
    ("ok", fence.UNMEASURED_CAUSE, "RAN_OK_WROTE_NOTHING"),
    ("exit_code=1", fence.UNMEASURED_CAUSE, "LEG_FAILED"),
    ("STOOD_DOWN: free 210 MB < 1200 MB", "BACKPRESSURE_GATE", "LEG_STOOD_DOWN"),
])
def test_the_last_ledger_row_names_the_clock_cause(outcome: str, cause: str,
                                                    detail: str) -> None:
    led = {"available": True, "path": "ledger",
           "last": {"organ_leg": {"at": _now(2), "outcome": outcome}}}
    got = fence.cause_of("organ", None, _ev(legs={"organ": {"organ_leg"}}, ledger=led))
    assert (got["cause"], got["cause_detail"]) == (cause, detail)
    assert "organ_leg" in got["cause_evidence"]


def test_a_box_leg_with_no_row_in_a_live_ledger_did_not_run() -> None:
    led = {"available": True, "path": "ledger",
           "last": {"someone_else": {"at": _now(1), "outcome": "ok"}}}
    got = fence.cause_of("organ", None, _ev(legs={"organ": {"organ"}}, ledger=led))
    assert (got["cause"], got["cause_detail"]) == ("SCHEDULE", "LEG_NOT_RUN_IN_WINDOW")


def test_an_off_box_clock_behind_a_silent_transport_is_schedule() -> None:
    ev = _ev(clocks={"aaii": {"full-pipeline.timer"}},
             ship={"ref": fence.SHIP_REF, "last_commit": _now(15 * 24)})
    got = fence.cause_of("aaii", None, ev)
    assert (got["cause"], got["cause_detail"]) == ("SCHEDULE", "OFF_BOX_CLOCK_TRANSPORT_SILENT")
    # A transport that is still live is not "silent", but the clock is still not this host's.
    ev["ship"] = {"ref": fence.SHIP_REF, "last_commit": _now(1)}
    assert fence.cause_of("aaii", None, ev)["cause_detail"] == "OFF_BOX_CLOCK"


def test_a_wall_is_fetch_failure_and_is_never_lifted_by_the_clock() -> None:
    # Even a producer with a box clock stays FETCH_FAILURE behind a recorded refusal: a clock
    # does not release a robots.txt disallow, and nothing here re-fetches it.
    ev = _ev(legs={"forexpeacearmy": {"seed_miners"}},
             walls={"forexpeacearmy": "ROBOTS_DISALLOW"})
    got = fence.cause_of("forexpeacearmy", None, ev)
    assert (got["cause"], got["cause_detail"]) == ("FETCH_FAILURE", "SOURCE_WALL:ROBOTS_DISALLOW")
    assert "never bypassed" in got["cause_evidence"]


def test_a_platform_that_never_yielded_is_fetch_failure_and_one_that_did_is_not() -> None:
    plats = {"hfm_pamm": {"last_state": "error:HTTPError", "best_rows": 0,
                          "last_attempt": "2026-09-12T04:01:55+00:00"},
             "amarkets": {"last_state": "ok", "best_rows": 115}}
    ev = _ev(platforms=plats)
    assert fence.cause_of("hfm_pamm", None, ev)["cause"] == "FETCH_FAILURE"
    assert fence.cause_of("amarkets", None, ev)["cause"] != "FETCH_FAILURE"
    # A blocked_sources entry older than a clean fetch of the same ground is history.
    ev["blocked"] = {"amarkets": {"diagnosis": "FETCH_ERROR"},
                     "share4you": {"diagnosis": "HTTP_BLOCKED"}}
    assert fence.cause_of("amarkets", None, ev)["cause"] != "FETCH_FAILURE"
    assert fence.cause_of("share4you", None, ev)["cause_detail"] == "BLOCKED:HTTP_BLOCKED"


def test_retirement_needs_a_declared_successor_and_no_clock_here() -> None:
    name = "lab_crossasset"
    assert name in fence.REPLACEMENTS
    got = fence.cause_of(name, None, _ev())
    assert got["cause"] == "RETIRED_SUPERSEDED"
    assert got["replacement"] == fence.REPLACEMENTS[name]
    # A producer with a declared FALLBACK that still runs here is not retired by it.
    ev = _ev(legs={"plumbing_miner": {"proposer_rotation"}})
    got = fence.cause_of("plumbing_miner", None, ev)
    assert got["cause"] != "RETIRED_SUPERSEDED"


def test_a_leg_that_merely_shares_the_seat_name_is_not_its_clock() -> None:
    got = fence.cause_of("frontier", None, _ev(legs={"frontier": {"frontier"}}))
    assert got["cause"] == "RETIRED_SUPERSEDED"


def test_key_missing_checks_existence_only(tmp_path: Path,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fence, "ROOT", tmp_path)
    monkeypatch.setattr(fence, "KEYED", {"seat_x": ("data/secrets/k.json", "SEAT_X_KEY")})
    monkeypatch.delenv("SEAT_X_KEY", raising=False)
    got = fence.cause_of("seat_x", None, _ev())
    assert got["cause"] == "KEY_MISSING" and "nothing read" in got["cause_evidence"]
    (tmp_path / "data" / "secrets").mkdir(parents=True)
    (tmp_path / "data" / "secrets" / "k.json").write_text("{}", encoding="utf-8")
    assert fence.cause_of("seat_x", None, _ev())["cause"] != "KEY_MISSING"


def test_upstream_dead_only_when_the_named_input_is_stale() -> None:
    legs = {"plumbing_miner": {"proposer_rotation"}}
    fresh = _ev(legs=legs, bars={"newest_bar_age_h": 0.1})
    stale = _ev(legs=legs, bars={"newest_bar_age_h": 300.0})
    assert fence.cause_of("plumbing_miner", None, fresh)["cause"] != "UPSTREAM_DEAD"
    got = fence.cause_of("plumbing_miner", None, stale)
    assert (got["cause"], got["cause_detail"]) == ("UPSTREAM_DEAD", "BARS_STALE")


def test_ledger_tail_reads_only_the_window(tmp_path: Path) -> None:
    p = tmp_path / "ledger.jsonl"
    rows = [{"at": _now(500), "run": "old_leg", "outcome": "ok"},
            {"at": _now(3), "run": "leg_a", "outcome": "TIMEOUT"},
            {"at": _now(1), "run": "leg_a", "outcome": "ok"}]
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n", encoding="utf-8")
    got = fence._ledger_last(72.0, p)
    assert got["available"] is True
    assert set(got["last"]) == {"leg_a"} and got["last"]["leg_a"]["outcome"] == "ok"
    assert fence._ledger_last(72.0, tmp_path / "absent.jsonl")["available"] is False


def _isolated_audit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, seats: dict[str, int],
                    alias: dict[str, int] | None = None,
                    cells: dict[str, Any] | None = None) -> dict[str, Any]:
    monkeypatch.setattr(fence, "DESK", tmp_path)               # no daily_cycle -> no proposers
    monkeypatch.setattr(fence, "_seat_output", lambda w: dict(seats))
    monkeypatch.setattr(fence, "_alias_output", lambda w: dict(alias or {}))
    return fence.audit(3.0, cells=cells, evidence=_ev())


def test_registry_cells_make_an_empty_seat_producing(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    cells = {"producers": [{"key": "miner:quiet_seat", "cells_emitted_per_hour": 2.5}]}
    doc = _isolated_audit(tmp_path, monkeypatch, {"quiet_seat": 0, "loud": 10}, cells=cells)
    row = next(r for r in doc["producers"] if r["producer"] == "quiet_seat")
    assert row["verdict"] == "PRODUCING" and row["basis"] == "registry_cells"
    assert row["resolved_cause"] == "WRITES_ELSEWHERE" and "quiet_seat" in doc[
        "resolved_writes_elsewhere"]


def test_a_shared_seat_file_alias_is_counted(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    doc = _isolated_audit(tmp_path, monkeypatch, {"world": 9000}, alias={"deep_forest_miner": 40})
    row = next(r for r in doc["producers"] if r["producer"] == "deep_forest_miner")
    assert row["verdict"] != "UNMEASURED" and row["rows_in_window"] == 40
    assert row["basis"].startswith("seat_file_alias:world/")


def test_every_dead_row_carries_a_cause(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    doc = _isolated_audit(tmp_path, monkeypatch, {"dead_a": 0, "dead_b": 0, "alive": 5})
    bad = [r["producer"] for r in doc["producers"]
           if r["verdict"] in ("DEAD", "UNMEASURED") and r.get("cause") not in fence.CAUSES]
    assert not bad, f"rows without a cause from the vocabulary: {bad}"
    assert sum(doc["causes"].values()) == sum(1 for r in doc["producers"]
                                              if r["verdict"] in ("DEAD", "UNMEASURED"))
    assert doc["seat_rule"] == fence.SEAT_RULE


def test_seat_of_follows_the_module_source(tmp_path: Path) -> None:
    (tmp_path / "proposer_x.py").write_text('SOURCE = "seat_y"\n', encoding="utf-8")
    assert fence.seat_of("proposer_x", (tmp_path,)) == "seat_y"
    assert fence.seat_of("absent", (tmp_path,)) is None
    # the real one the 2026-10-29 census missed
    assert fence.seat_of("weak_signal_compiler") == "weak_signal_ensemble"


def test_box_legs_reads_all_three_spellings() -> None:
    src = '''
def fn() -> dict:
    """doc"""
    return _producer("organ_b", "research/module_b.py")


def main():
    a = _costed("leg_a", lambda: _producer(
        "organ_a", "side_channels/module_a.py", "--x"))
    b = _costed("leg_b", fn)
'''
    got = fence.box_legs(src)
    assert got["organ_a"] == {"leg_a"} and got["module_a"] == {"leg_a"}
    assert got["organ_b"] == {"leg_b"} and got["module_b"] == {"leg_b"}
    real = fence.box_legs()
    for leg in ("seed_miners", "external_miners", "proposer_rotation"):
        assert leg in real, f"the revival leg {leg} is not in hourly_cycle"
    assert "seed_miners" in real["seed_miners"] and "external_miners" in real["run_all_miners"]


def test_leg_seats_match_the_code_that_writes_them() -> None:
    # seed_miners: every MINERS key is a seat it writes (seed_miners._write_rows -> INTEL / name).
    tree = ast.parse((DESK / "side_channels" / "seed_miners.py").read_text(encoding="utf-8"))
    miners: set[str] = set()
    for node in tree.body:
        if (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "MINERS" and isinstance(node.value, ast.Dict)):
            miners = {k.value for k in node.value.keys if isinstance(k, ast.Constant)}
    assert miners and miners <= set(fence.LEG_SEATS["seed_miners"])
    # run_all_miners: every miner module it imports writes the seat its own OUTPUT constant names.
    ram = (DESK / "side_channels" / "run_all_miners.py").read_text(encoding="utf-8")
    mods = re.findall(r"^from ([a-z0-9_]+) import run_and_save", ram, re.M)
    written: set[str] = set()
    for m in mods:
        src = (DESK / "side_channels" / f"{m}.py").read_text(encoding="utf-8")
        written |= set(re.findall(r'intelligence["\']\s*/\s*["\']([a-z0-9_]+)["\']', src))
    assert written and written <= set(fence.LEG_SEATS["external_miners"]), (
        written - set(fence.LEG_SEATS["external_miners"]))


def test_box_rotation_names_only_real_discovery_organs() -> None:
    rot = fence.box_rotation()
    tree = ast.parse((DESK / "research" / "hourly_discovery.py").read_text(encoding="utf-8"))
    organs: set[str] = set()
    for node in tree.body:
        tgt = node.target if isinstance(node, ast.AnnAssign) else None
        if isinstance(tgt, ast.Name) and tgt.id == "ORGANS" and isinstance(node.value, ast.Dict):
            organs = {k.value for k in node.value.keys if isinstance(k, ast.Constant)}
    assert rot and rot <= organs


def test_the_periodic_table_entry_point_writes() -> None:
    """`hourly_cycle.periodic_table` runs this file as a script; its `__main__` printed a demo
    and exited 0 without calling `run()`, so the seat read DEAD while the leg read ok."""
    tree = ast.parse((DESK / "side_channels" / "alpha_periodic_table.py")
                     .read_text(encoding="utf-8"))
    mains = [n for n in tree.body if isinstance(n, ast.If)
             and "__main__" in ast.unparse(n.test)]
    assert mains, "no __main__ block"
    assert "main()" in ast.unparse(mains[-1]), "the script entry point must call main()"


def test_run_all_miners_rotation_keeps_every_miner_once() -> None:
    src = (DESK / "side_channels" / "run_all_miners.py").read_text(encoding="utf-8")
    # Exercise the helper alone: importing the module would import every miner.
    ns: dict[str, Any] = {}
    fn_src = src[src.index("def _rotated"):src.index("def run_all_miners")]
    exec("from datetime import datetime, timezone\n" + fn_src, ns)
    roster = [("a", 1), ("b", 2), ("c", 3)]
    assert ns["_rotated"](roster, hour=0) == roster
    assert ns["_rotated"](roster, hour=1) == [("b", 2), ("c", 3), ("a", 1)]
    assert sorted(ns["_rotated"](roster, hour=7)) == sorted(roster)
    assert ns["_rotated"]([], hour=3) == []


def test_no_cause_reader_opens_a_secret() -> None:
    src = (ROOT / "scripts" / "check_producer_yield.py").read_text(encoding="utf-8")
    body = src[src.index("def cause_of"):src.index("def _rel(")]
    assert "read_text" not in body and "open(" not in body, (
        "the classifier checks credentials for EXISTENCE only")
