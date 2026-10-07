"""ARCH-09: every essential function on the ladder, every rung derived, a false rung fails."""
from __future__ import annotations

import copy
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops import function_registry as fr  # noqa: E402
from scripts import check_function_registry as cfr  # noqa: E402


def _row(**over: object) -> dict:
    row = {
        "id": "research.toy", "domain": "research", "function": "toy",
        "owner": "desks/mt5/research/toy.py",
        "inputs": ["toy_in.json"], "outputs": ["toy_out.json"],
        "contracts": ["tests/test_toy.py"],
        "runtime_process": ["leg:toy"],
        "consumers": ["desks/mt5/research/reader.py"],
        "decision_authority": {"level": "proposes", "scope": "toys"},
        "failure_behaviour": {"mode": "unmeasured", "marker": "UNMEASURED", "says": "absent"},
        "verification": ["tests/test_toy.py"],
    }
    row.update(over)
    return row


def _repo(tmp: Path) -> Path:
    r = tmp / "desks" / "mt5" / "research"
    r.mkdir(parents=True)
    (tmp / "desks" / "mt5" / "ops").mkdir(parents=True)
    (tmp / "desks" / "mt5" / "reports").mkdir(parents=True)
    (tmp / "scripts").mkdir()
    (tmp / "tests").mkdir()
    (r / "toy.py").write_text('IN = "toy_in.json"\nOUT = "toy_out.json"\n'
                              'def main():\n    return "UNMEASURED"\n', "utf-8")
    (r / "reader.py").write_text('SRC = "toy_out.json"\n', "utf-8")
    (r / "bystander.py").write_text('X = 1\n', "utf-8")
    (r / "hourly_cycle.py").write_text(
        'x = _costed("toy", lambda: _producer("toy", "research/toy.py"))\n', "utf-8")
    (tmp / "desks" / "mt5" / "ops" / "box_tasks.manifest").write_text(
        'TASK name="MT5-Toy" trigger="daily 04:00" runs="desks/mt5/research/toy.py"\n', "utf-8")
    (tmp / "scripts" / "run_law_gate.py").write_text("FENCES = ()\n", "utf-8")
    (tmp / "tests" / "test_toy.py").write_text("from research import toy\n", "utf-8")
    return tmp


def _dirs(tmp: Path) -> tuple[Path, ...]:
    return (tmp / "desks" / "mt5" / "reports",)


def test_a_complete_row_climbs_to_connected_and_stops_at_unmeasured(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    f = fr.derive(_row(), repo, dirs=_dirs(repo))
    assert [f["rungs"][r]["state"] for r in fr.RUNGS] == [
        fr.TRUE, fr.TRUE, fr.TRUE, fr.UNMEASURED, fr.UNMEASURED]
    assert f["rung"] == "connected"
    assert f["false_static"] == []


def test_a_fresh_output_on_this_host_is_running_and_then_behaviour_verified(
        tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "desks" / "mt5" / "reports" / "toy_out.json").write_text("{}", "utf-8")
    f = fr.derive(_row(), repo, dirs=_dirs(repo))
    assert f["rungs"]["running"]["state"] == fr.TRUE
    assert f["rung"] == "behaviour_verified"


def test_a_stale_output_is_false_not_unmeasured(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    p = repo / "desks" / "mt5" / "reports" / "toy_out.json"
    p.write_text("{}", "utf-8")
    old = time.time() - 3 * 86_400
    os.utime(p, (old, old))
    f = fr.derive(_row(), repo, dirs=_dirs(repo))
    assert f["rungs"]["running"]["state"] == fr.FALSE
    assert f["rung"] == "connected"
    # a runtime FALSE is a fact about the host, never a false STATIC rung
    assert f["false_static"] == []


def test_a_task_clock_reads_its_trigger_for_the_silence_window(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    target, silence, _ = fr.clock_target("task:MT5-Toy", repo)
    assert target == "desks/mt5/research/toy.py"
    assert silence == fr.DAILY_SILENCE_S


def test_a_row_that_asserts_a_rung_is_false_at_declared(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    f = fr.derive(_row(rung="behaviour_verified"), repo, dirs=_dirs(repo))
    assert f["rungs"]["declared"]["state"] == fr.FALSE
    assert "asserts a rung" in f["rungs"]["declared"]["why"]
    assert "declared" in f["false_static"]


def test_an_output_the_owner_never_names_is_false_at_implemented(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    f = fr.derive(_row(outputs=["imaginary.json"]), repo, dirs=_dirs(repo))
    assert f["rungs"]["implemented"]["state"] == fr.FALSE
    assert "imaginary.json" in f["rungs"]["implemented"]["why"]


def test_a_consumer_that_reads_nothing_is_false_at_connected(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    f = fr.derive(_row(consumers=["desks/mt5/research/bystander.py"]), repo, dirs=_dirs(repo))
    assert f["rungs"]["connected"]["state"] == fr.FALSE
    assert "connected" in f["false_static"]


def test_a_clock_the_repository_does_not_know_is_false_at_connected(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    f = fr.derive(_row(runtime_process=["leg:never_registered"]), repo, dirs=_dirs(repo))
    assert f["rungs"]["connected"]["state"] == fr.FALSE
    assert "never_registered" in f["rungs"]["connected"]["why"]


def test_a_test_that_never_names_the_owner_is_a_false_verification(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "tests" / "test_other.py").write_text("x = 1\n", "utf-8")
    f = fr.derive(_row(verification=["tests/test_other.py"]), repo, dirs=_dirs(repo))
    assert f["rungs"]["behaviour_verified"]["state"] == fr.FALSE
    assert "behaviour_verified" in f["false_static"]


def test_build_names_every_domain_without_a_function(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    doc = fr.build(repo, {"functions": [_row()]}, dirs=_dirs(repo))
    missing = [p for p in doc["problems"] if "has no essential function" in p]
    assert len(missing) == len(fr.DOMAINS) - 1


def test_a_published_map_that_has_gone_false_is_caught(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    good = fr.build(repo, {"functions": [_row()]}, dirs=_dirs(repo))
    (repo / "desks" / "mt5" / "research" / "reader.py").write_text("X = 2\n", "utf-8")
    now = fr.build(repo, {"functions": [_row()]}, dirs=_dirs(repo))
    lies = fr.published_false_rungs(good, now)
    assert lies and "connected=TRUE" in lies[0]


def test_a_git_copy_is_not_runtime_evidence() -> None:
    sealed = ROOT / "ops" / "principal_doctrine.txt"
    assert sealed in fr._tracked_unchanged([sealed], ROOT)


def test_the_real_registry_covers_every_domain_with_no_false_rung() -> None:
    reg = fr.load_registry()
    rows = reg["functions"]
    assert {r["domain"] for r in rows} == set(fr.DOMAINS)
    for r in rows:
        assert not (fr.ASSERTED_KEYS & set(r)), f"{r['id']} asserts a rung"
    doc = fr.build()
    assert doc["problems"] == [], doc["problems"]
    for f in doc["functions"]:
        assert f["rung"] in fr.RUNGS
        assert fr.RUNGS.index(f["rung"]) >= fr.RUNGS.index("connected"), f


def test_the_fence_reads_the_published_map_and_fails_on_a_false_rung(tmp_path: Path) -> None:
    doc = fr.build()
    lie = copy.deepcopy(doc)
    lie["functions"].append({"id": "ghost.function",
                             "rungs": {"connected": {"state": fr.TRUE}}})
    path = tmp_path / "FUNCTION_MAP.json"
    path.write_text(json.dumps(lie), "utf-8")
    res = cfr.check(map_path=path)
    assert not res["ok"]
    assert any("ghost.function" in p for p in res["problems"])
    path.write_text(json.dumps(doc), "utf-8")
    assert cfr.check(map_path=path)["ok"]


def test_the_leg_and_the_fence_are_wired() -> None:
    hc = (ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_producer(\n        "function_registry", "libs/ops/function_registry.py")' in hc
    gate = (ROOT / "scripts" / "run_law_gate.py").read_text("utf-8")
    assert '("check_function_registry.py", ())' in gate
