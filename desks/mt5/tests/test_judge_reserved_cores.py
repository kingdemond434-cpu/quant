"""THE JUDGE'S RESERVED CORES (principal, 2026-11-20: "We made it 6 cores"; 2026-10-29 base).

By default the judge's sweep tree is confined to six logical cores and runs one class above the
miners there (NORMAL, never higher, never above the registered live class). Nothing else moves:
no miner is lowered or confined. `{"enabled": false}` restores the 2026-10-20 rule. Every
malformed or unmeasurable input fails closed to the old rule."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts import judge_priority as jp  # noqa: E402

R = jp.CLASS_RANK
BN, N = R[jp.BELOW_NORMAL], R[jp.NORMAL]


def _sw(tmp_path: Path, doc: object | None) -> Path:
    p = tmp_path / "JUDGE_RESERVED_CORES.json"
    if doc is not None:
        p.write_text(doc if isinstance(doc, str) else json.dumps(doc), "utf-8")
    return p


def test_absent_switch_reserves_six_cores_clear_of_the_shaper_pins(tmp_path: Path) -> None:
    r = jp.reserved_cores(18, _sw(tmp_path, None))
    assert r["enabled"] and r["cpus"] == [8, 9, 10, 11, 12, 13]


@pytest.mark.parametrize("doc,why", [
    ({"enabled": False}, "enabled=false"),
    ("{not json", "unreadable"),
    ([1, 2], "not an object"),
    ({"cores": 0}, "cores malformed"),
    ({"cores": True}, "cores malformed"),
    ({"cpus": [3, 3]}, "cpus malformed"),
    ({"cpus": [40]}, "cpus malformed"),
    ({"cores": 12}, "would leave fewer"),
])
def test_every_off_or_malformed_switch_is_the_old_rule(tmp_path: Path, doc, why) -> None:
    r = jp.reserved_cores(18, _sw(tmp_path, doc))
    assert not r["enabled"] and why in r["why"]


def test_a_small_box_or_unmeasured_count_never_reserves(tmp_path: Path) -> None:
    assert not jp.reserved_cores(8, _sw(tmp_path, None))["enabled"]
    assert not jp.reserved_cores(0, _sw(tmp_path, None))["enabled"]


def test_explicit_cpus_are_honoured(tmp_path: Path) -> None:
    assert jp.reserved_cores(18, _sw(tmp_path, {"cpus": [13, 2, 7]}))["cpus"] == [2, 7, 13]


RES = {"enabled": True, "cpus": [8, 9, 10, 11, 12, 13], "why": "test"}


def test_the_judge_goes_one_class_above_the_miners_and_carries_its_cores() -> None:
    t = jp.judge_target([BN, BN], [BN, N], registered_live=N, reserved=RES)
    assert t["rank"] == N and t["above_any_miner"] and t["cpus"] == RES["cpus"]


@pytest.mark.parametrize("kw", [
    {"unreadable": 1},                       # an unreadable row blocks any raise
    {"registered_live": None},               # live class unreadable
    {"registered_live": BN},                 # live registered at the miners' class
])
def test_the_reservation_fails_closed_like_the_old_rule(kw) -> None:
    args = {"registered_live": N, **kw}
    t = jp.judge_target([BN], [N], reserved=RES, **args)
    assert t["rank"] == BN and "cpus" not in t


def test_a_miner_already_at_normal_gets_no_raise_above_it() -> None:
    t = jp.judge_target([BN, N], [N], registered_live=N, reserved=RES)
    assert "cpus" not in t and t["rank"] <= N


def test_the_launcher_never_starts_the_child_raised_unconfined() -> None:
    flags, _ = jp.sweep_creationflags([])   # nothing measurable: the old default
    assert jp.CLASS_RANK[flags] <= BN
    orig = jp.census
    try:
        jp.census = lambda rows, **k: {"target": {"status": "MEASURED", "rank": N,
                                                  "cpus": [8, 9]},
                                       "verdict": "X", "classes": {}}
        flags, _ = jp.sweep_creationflags([])
        assert jp.CLASS_RANK[flags] == BN
    finally:
        jp.census = orig


class Proc:
    def __init__(self, sticks: bool = True) -> None:
        self.aff = list(range(18))
        self.sticks = sticks

    def cpu_affinity(self, cpus=None):
        if cpus is None:
            return self.aff
        if self.sticks:
            self.aff = list(cpus)
        return None


def test_confine_reads_back_and_reports_a_failure() -> None:
    assert jp.confine(1, [8, 9], Proc())["applied"] is True
    assert jp.confine(1, [8, 9], Proc(sticks=False))["applied"] is False


def test_the_sweep_child_confines_before_it_raises_and_falls_back_if_it_cannot(
        monkeypatch) -> None:
    import os

    from scripts import run_sharded_gauntlet as rsg
    me = os.getpid()
    row = {"pid": me, "ppid": 1, "name": "python.exe", "cmdline": ["python"], "nice": 0x4000,
           "rank": BN, "cls": "judge", "create_time": 1.0, "unreadable": False}
    monkeypatch.setattr(jp, "snapshot", lambda *a, **k: [dict(row)])
    monkeypatch.setattr(jp, "census", lambda rows, **k: {
        "target": {"status": "MEASURED", "rank": N, "class": "NORMAL", "cpus": [8, 9]},
        "verdict": "JUDGE_BELOW_MINERS", "rows": [dict(row)], "classes": {}})
    seen: list = []
    monkeypatch.setattr(jp, "equalise", lambda rows, rank, apply: seen.append(rank) or [])
    monkeypatch.setattr(jp, "account", lambda *a, **k: {"changed": False})
    monkeypatch.setattr(jp, "revert_with", lambda rows: None)
    monkeypatch.setattr(jp, "confine", lambda pid, cpus: {"applied": True, "cpus": cpus})
    out = rsg._equalise_self()
    assert seen == [N] and out["affinity"]["applied"]
    monkeypatch.setattr(jp, "confine", lambda pid, cpus: {"applied": False, "error": "x"})
    out = rsg._equalise_self()
    assert seen[-1] == BN and out["target"]["cpus"] == []
