"""The identity healer names its quiet passes; a twin-rooted path is named.

Measured on the box 2026-11-05 00:03Z: heal_clocks had nothing to do and exited 0 without saying
so, which the contract can only read as SILENT_NO_OP. This pins that its marker survives the
tail the cycle keeps and reads as DECLARED_NO_OP. (The promoter's twin line waits on the signed
evaluator route: promoter.py is a frozen file under check_immutable_evaluator.)
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from libs.ops import write_or_explain as woe

ROOT = Path(__file__).resolve().parents[2]
ABSENT = {"a.json": {"exists": False, "mtime_ns": 0, "size": -1}}


def _healer():
    path = ROOT / "desks" / "mt5" / "scripts" / "heal_identity_broken_clocks.py"
    spec = importlib.util.spec_from_file_location("heal_identity_noop_probe", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT / "desks" / "mt5"))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(ROOT / "desks" / "mt5"))
    return mod


def test_the_healers_marker_reads_as_a_declared_no_op_from_its_last_three_lines() -> None:
    line = _healer()._NOOP_LINE.format(why="0 resumable of 3 broken (3 left terminal)")
    out = "\n".join(["identity healer: 3 broken -> 0 resumed", "  TERMINAL x", line])
    tail = out.strip().splitlines()[-3:]           # what hourly_cycle.heal_clocks keeps
    rec = woe.judge("heal_clocks", ABSENT, ABSENT, {"exit_code": 0, "tail": "\n".join(tail)})
    assert rec["verdict"] == woe.DECLARED_NO_OP
    assert "0 resumable" in rec["reason"]


def test_a_path_present_under_both_roots_is_named(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    base = repo / "desks" / "mt5"
    for root in (repo, base):
        (root / "data").mkdir(parents=True)
        (root / "data" / "x.jsonl").write_text("{}\n", "utf-8")
    (repo / "data" / "only_root.jsonl").write_text("{}\n", "utf-8")
    monkeypatch.setattr(woe, "REPO", repo)
    monkeypatch.setattr(woe, "BASE", base)
    assert woe.both_roots([repo / "data" / "x.jsonl", repo / "data" / "only_root.jsonl",
                           "/nowhere/else.json"]) == ["data/x.jsonl"]
    assert woe.both_roots([base / "data" / "x.jsonl"]) == ["desks/mt5/data/x.jsonl"]


def test_a_silent_no_op_on_a_twin_rooted_path_says_so(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    base = repo / "desks" / "mt5"
    for root in (repo, base):
        (root / "data").mkdir(parents=True)
        (root / "data" / "x.jsonl").write_text("{}\n", "utf-8")
    monkeypatch.setattr(woe, "REPO", repo)
    monkeypatch.setattr(woe, "BASE", base)
    snap = woe.snapshot([repo / "data" / "x.jsonl"])
    rec = woe.judge("leg", snap, snap, {"exit_code": 0})
    assert rec["verdict"] == woe.SILENT_NO_OP
    assert rec["both_roots"] == ["data/x.jsonl"] and "BOTH" in rec["detail"]


def _shared_world(tmp_path, monkeypatch, *, age_h: float):
    import os
    import time
    art = tmp_path / "FOREST_KOREA.json"
    art.write_text("{}", "utf-8")
    stamp = time.time() - age_h * 3600
    os.utime(art, (stamp, stamp))
    table = {"forest_korea": ["k"], "forest_china": ["k"], "solo": ["s"]}
    monkeypatch.setattr(woe, "leg_table", lambda refresh=False: table)
    monkeypatch.setattr(woe, "declared_artifacts",
                        lambda leg: [art] if leg.startswith("forest") else [tmp_path / "s.json"])
    monkeypatch.setattr(woe, "_OWNERS", None)
    return woe.snapshot([art])


def test_a_leg_judged_on_a_fresh_file_another_leg_shares_is_unattributed(tmp_path,
                                                                         monkeypatch) -> None:
    """The box, 2026-11-05: ten forest legs were judged on FOREST_KOREA.json."""
    snap = _shared_world(tmp_path, monkeypatch, age_h=1.0)
    rec = woe.judge("forest_china", snap, snap, {"exit_code": 0})
    assert rec["verdict"] == woe.SHARED_UNATTRIBUTED
    assert rec["verdict"] not in woe.DEFECTS and rec["verdict"] not in woe.PASSING
    assert list(rec["shared_with"].values()) == [["forest_korea"]]


def test_a_shared_file_nobody_wrote_inside_the_window_is_silent_again(tmp_path,
                                                                     monkeypatch) -> None:
    snap = _shared_world(tmp_path, monkeypatch, age_h=woe.WINDOW_H + 1)
    assert woe.judge("forest_china", snap, snap, {"exit_code": 0})["verdict"] == woe.SILENT_NO_OP


def test_a_named_reason_still_wins_and_a_private_file_is_still_judged_alone(tmp_path,
                                                                            monkeypatch) -> None:
    snap = _shared_world(tmp_path, monkeypatch, age_h=1.0)
    rec = woe.judge("forest_china", snap, snap,
                    {"exit_code": 0, "tail": "WRITE_OR_EXPLAIN: NO_OP nothing new"})
    assert rec["verdict"] == woe.DECLARED_NO_OP
    private = woe.snapshot([tmp_path / "s.json"])
    assert woe.judge("solo", private, private, {"exit_code": 0})["verdict"] == woe.SILENT_NO_OP


def test_the_report_files_unattributed_legs_apart_and_not_as_a_breach(tmp_path,
                                                                      monkeypatch) -> None:
    row = {"leg": "forest_china", "verdict": woe.SHARED_UNATTRIBUTED,
           "at": woe._now(), "declared": ["k"]}
    monkeypatch.setattr(woe, "read_ledger", lambda: [row])
    monkeypatch.setattr(woe, "leg_table", lambda refresh=False: {"forest_china": ["k"]})
    rep = woe.build_report()
    assert [e["leg"] for e in rep["shared_unattributed"]] == ["forest_china"]
    assert rep["status"] == "CONTRACT_KEPT" and not rep["silent_no_ops"]


def test_a_per_leg_declaration_replaces_the_items_shared_artifact(tmp_path, monkeypatch) -> None:
    """Fifteen forests were judged on FOREST_KOREA.json; each now owns FOREST_<ID>.json."""
    import json
    prog = tmp_path / "tier1_program.json"
    prog.write_text(json.dumps({"items": [{
        "id": "U10", "artifact": "desks/mt5/reports/FOREST_KOREA.json",
        "scheduled_by": "hourly_cycle:forest_korea, hourly_cycle:forest_china, hourly_cycle:x",
        "artifact_by_leg": {"forest_china": "desks/mt5/reports/FOREST_CHINA.json"}}]}), "utf-8")
    monkeypatch.setattr(woe, "PROGRAM", prog)
    table = woe.leg_table(refresh=True)
    try:
        assert table["forest_china"] == ["desks/mt5/reports/FOREST_CHINA.json"]
        assert table["forest_korea"] == ["desks/mt5/reports/FOREST_KOREA.json"]
        assert table["x"] == ["desks/mt5/reports/FOREST_KOREA.json"]
    finally:
        monkeypatch.undo()
        woe.leg_table(refresh=True)


def test_the_real_registry_gives_every_forest_its_own_report() -> None:
    table = woe.leg_table(refresh=True)
    forests = {leg: paths for leg, paths in table.items() if leg.startswith("forest_")}
    assert len(forests) == 15
    for leg, paths in forests.items():
        assert paths == [f"desks/mt5/reports/FOREST_{leg[len('forest_'):].upper()}.json"], leg
    assert table["fred_macro"] == ["desks/mt5/reports/MACRO_VIEW.json"]
