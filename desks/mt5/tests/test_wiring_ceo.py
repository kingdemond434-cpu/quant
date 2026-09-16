"""The wiring hunter: organs, clocks, transitive scheduling, probation eligibility, the ratchet;
and the probation runner's rotation and money-path refusal."""
from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if p not in sys.path:
        sys.path.insert(0, p)

import probation_runner as pr  # noqa: E402
import wiring_ceo as wc  # noqa: E402


def _tree(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "desks/mt5/research").mkdir(parents=True)
    (root / "desks/mt5/scripts").mkdir(parents=True)
    (root / "desks/mt5/ops").mkdir(parents=True)
    (root / "desks/mt5/tests").mkdir(parents=True)
    (root / "ops").mkdir()
    (root / "scripts").mkdir()
    r = root / "desks/mt5/research"
    (r / "hourly_cycle.py").write_text(
        'import helper_organ\ndef main():\n    _producer("x", "research/scheduled_organ.py")\n',
        encoding="utf-8")
    (r / "scheduled_organ.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (r / "helper_organ.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (r / "orphan_organ.py").write_text(
        "import argparse\ndef main():\n    ap = argparse.ArgumentParser()\n"
        "    ap.add_argument('--dry-run')\n    return 0\n", encoding="utf-8")
    (r / "gateway_thing.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (r / "needs_args.py").write_text(
        "import argparse\ndef main():\n    ap = argparse.ArgumentParser()\n"
        "    ap.add_argument('--x', required=True)\n", encoding="utf-8")
    (root / "desks/mt5/ops/box_tasks.manifest").write_text(
        'TASK name="MT5-Hourly" trigger="hourly" runs="desks/mt5/research/hourly_cycle.py"\n',
        encoding="utf-8")
    (root / "desks/mt5/tests/test_orphan_organ.py").write_text(
        "import orphan_organ\n", encoding="utf-8")
    return root


def _point(monkeypatch, root: Path) -> None:
    monkeypatch.setattr(wc, "ROOT", root)
    monkeypatch.setattr(wc, "DESK", root / "desks/mt5")
    monkeypatch.setattr(wc, "OUT", root / "desks/mt5/reports/WIRING_CEO.json")
    monkeypatch.setattr(wc, "FLOOR", root / "desks/mt5/data/wiring_floor.json")
    monkeypatch.setattr(wc, "PROBATION_QUEUE", root / "desks/mt5/data/probation_queue.json")


def test_scheduled_directly_or_through_an_import_and_the_rest_are_unwired(monkeypatch, tmp_path):
    root = _tree(tmp_path)
    _point(monkeypatch, root)
    doc = wc.build(apply=True)
    unwired = {r["organ"]: r for r in doc["unwired"]}
    assert "desks/mt5/research/scheduled_organ.py" not in unwired      # named by the cycle
    assert "desks/mt5/research/helper_organ.py" not in unwired         # imported by the cycle
    assert "desks/mt5/research/hourly_cycle.py" not in unwired         # named by the manifest
    assert set(unwired) == {"desks/mt5/research/orphan_organ.py",
                            "desks/mt5/research/gateway_thing.py",
                            "desks/mt5/research/needs_args.py"}
    o = unwired["desks/mt5/research/orphan_organ.py"]
    assert o["has_tests"] and o["probation"] and "dry-run" in o["probation_why"]
    assert not unwired["desks/mt5/research/gateway_thing.py"]["probation"]   # money-path name
    assert not unwired["desks/mt5/research/needs_args.py"]["probation"]      # required args
    q = json.loads(wc.PROBATION_QUEUE.read_text(encoding="utf-8"))["queue"]
    assert [x["organ"] for x in q] == ["desks/mt5/research/orphan_organ.py"] and q[0]["dry_run"]
    assert doc["floor"]["status"] == "HELD" and doc["floor"]["previous"] is None


def test_the_floor_ratchets_down_and_reports_a_rise_as_breach(monkeypatch, tmp_path):
    root = _tree(tmp_path)
    _point(monkeypatch, root)
    wc.FLOOR.parent.mkdir(parents=True, exist_ok=True)
    wc.FLOOR.write_text(json.dumps({"unwired": 5}), encoding="utf-8")
    doc = wc.build(apply=True)
    assert doc["floor"]["status"] == "RATCHETED"
    assert json.loads(wc.FLOOR.read_text(encoding="utf-8"))["unwired"] == 3
    (root / "desks/mt5/research/another_orphan.py").write_text("def main():\n    return 0\n",
                                                                encoding="utf-8")
    doc = wc.build(apply=True)
    assert doc["floor"]["status"] == "BREACH" and doc["floor"]["now"] == 4
    assert json.loads(wc.FLOOR.read_text(encoding="utf-8"))["unwired"] == 3   # never rises


def test_probation_picks_least_recently_run_and_refuses_money_names():
    queue = [{"organ": "desks/mt5/research/a.py"}, {"organ": "desks/mt5/research/b.py"},
             {"organ": "desks/mt5/research/gateway_x.py"}, {"organ": "desks/mt5/research/c.py"}]
    state = {"last_run": {"desks/mt5/research/a.py": "2026-09-16T10:00:00+00:00",
                          "desks/mt5/research/b.py": "2026-09-16T09:00:00+00:00"}}
    picked = [r["organ"] for r in pr.pick(queue, state, 2)]
    assert picked == ["desks/mt5/research/c.py", "desks/mt5/research/b.py"]
    assert all("gateway" not in r["organ"] for r in pr.pick(queue, state, 10))


def test_probation_runs_an_organ_and_records_history(monkeypatch, tmp_path):
    root = tmp_path / "repo"
    (root / "desks/mt5/research").mkdir(parents=True)
    organ = root / "desks/mt5/research/tiny.py"
    organ.write_text("import sys\nprint('ok', sys.argv[1:])\n", encoding="utf-8")
    monkeypatch.setattr(pr, "ROOT", root)
    monkeypatch.setattr(pr, "DESK", root / "desks/mt5")
    monkeypatch.setattr(pr, "QUEUE", root / "desks/mt5/data/probation_queue.json")
    monkeypatch.setattr(pr, "STATE", root / "desks/mt5/data/probation_state.json")
    monkeypatch.setattr(pr, "OUT", root / "desks/mt5/reports/PROBATION.json")
    pr.QUEUE.parent.mkdir(parents=True, exist_ok=True)
    pr.QUEUE.write_text(json.dumps({"queue": [{"organ": "desks/mt5/research/tiny.py",
                                               "dry_run": True, "budget_s": 30}]}),
                        encoding="utf-8")
    assert pr.main(["--per-pass", "4"]) == 0
    out = json.loads(pr.OUT.read_text(encoding="utf-8"))
    assert out["ran"][0]["status"] == "OK" and out["ran"][0]["dry_run"] is True
    hist = json.loads(pr.STATE.read_text(encoding="utf-8"))["history"]
    assert hist["desks/mt5/research/tiny.py"]["clean"] == 1
    for _ in range(2):
        pr.main([])
    out = json.loads(pr.OUT.read_text(encoding="utf-8"))
    assert out["promotable"] == ["desks/mt5/research/tiny.py"]


def test_auto_legs_clock_only_organs_probation_ran_clean_and_pick_the_plan():
    probation = [{"organ": "desks/mt5/research/fast.py", "dry_run": True, "budget_s": 120},
                 {"organ": "desks/mt5/research/slow.py", "dry_run": False, "budget_s": 120},
                 {"organ": "desks/mt5/research/never.py", "dry_run": True, "budget_s": 120}]
    state = {"history": {"desks/mt5/research/fast.py": {"runs": 3, "clean": 3, "seconds": 12.0},
                         "desks/mt5/research/slow.py": {"runs": 1, "clean": 1, "seconds": 95.0}}}
    legs = {x["leg"]: x for x in wc.auto_legs(probation, state)}
    assert set(legs) == {"auto_fast", "auto_slow"}          # never ran clean -> not clocked
    assert legs["auto_fast"]["plan"] == "core" and legs["auto_fast"]["argv"] == ["--dry-run"]
    assert legs["auto_slow"]["plan"] == "heavy" and legs["auto_slow"]["argv"] == []


def test_run_auto_legs_runs_only_the_current_plan(monkeypatch, tmp_path):
    import hourly_cycle as hc
    ran: list[str] = []
    monkeypatch.setattr(hc, "_auto_leg", lambda e: ran.append(e["organ"]) or {"exit_code": 0})
    monkeypatch.setattr(hc, "_costed", lambda name, fn: fn())
    f = tmp_path / "auto_legs.json"
    f.write_text(json.dumps({"legs": [
        {"organ": "desks/mt5/research/a.py", "leg": "auto_a", "plan": "core"},
        {"organ": "desks/mt5/research/b.py", "leg": "auto_b", "plan": "heavy"}]}),
        encoding="utf-8")
    out = hc.run_auto_legs("core", f)
    assert ran == ["desks/mt5/research/a.py"] and out["n"] == 1 and out["of"] == 2
    ran.clear()
    hc.run_auto_legs("all", f)
    assert ran == ["desks/mt5/research/a.py", "desks/mt5/research/b.py"]
    assert hc.in_plan("auto_anything", "core") and hc.in_plan("auto_anything", "heavy")
    assert hc.run_auto_legs("core", tmp_path / "absent.json")["n"] == 0
