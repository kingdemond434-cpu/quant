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
