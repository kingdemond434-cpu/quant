"""The wiring hunter: organs, clocks, transitive scheduling, probation eligibility, the ratchet;
and the probation runner's rotation and money-path refusal."""
from __future__ import annotations

import json
import sys
import time
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
    (r / "scheduled_organ.py").write_text("import helper_lib\ndef main():\n    return 0\n",
                                          encoding="utf-8")
    (r / "helper_organ.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (r / "orphan_organ.py").write_text(
        "import argparse\nimport unwired_only_lib\ndef main():\n"
        "    ap = argparse.ArgumentParser()\n"
        "    ap.add_argument('--dry-run')\n    return 0\n", encoding="utf-8")
    # three modules with NO main(): reached by a clock, imported only by an unwired organ, and
    # imported by nothing at all -- plus a hand-run script, which is a different remedy.
    (r / "helper_lib.py").write_text("VALUE = 1\n", encoding="utf-8")
    (r / "unwired_only_lib.py").write_text("VALUE = 2\n", encoding="utf-8")
    (r / "orphan_lib.py").write_text("VALUE = 3\n", encoding="utf-8")
    (r / "handrun_script.py").write_text(
        'if __name__ == "__main__":\n    print(1)\n', encoding="utf-8")
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
    """Repoint EVERY path the hunter writes at the throwaway tree.

    AUTO_LEGS and PROBATION_STATE were missing here until 2026-09-17, so `build(apply=True)` in
    these tests wrote data/auto_legs.json in the REAL repo and read the real probation state --
    a test that edits the tracked tree it is testing (R0748's shape: the suite's own writes
    become the thing the next reader trusts)."""
    monkeypatch.setattr(wc, "ROOT", root)
    monkeypatch.setattr(wc, "DESK", root / "desks/mt5")
    monkeypatch.setattr(wc, "OUT", root / "desks/mt5/reports/WIRING_CEO.json")
    monkeypatch.setattr(wc, "FLOOR", root / "desks/mt5/data/wiring_floor.json")
    monkeypatch.setattr(wc, "PROBATION_QUEUE", root / "desks/mt5/data/probation_queue.json")
    monkeypatch.setattr(wc, "PROBATION_STATE", root / "desks/mt5/data/probation_state.json")
    monkeypatch.setattr(wc, "AUTO_LEGS", root / "desks/mt5/data/auto_legs.json")


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


def _pr_tree(monkeypatch, tmp_path) -> Path:
    root = tmp_path / "repo"
    (root / "desks/mt5/research").mkdir(parents=True)
    monkeypatch.setattr(pr, "ROOT", root)
    monkeypatch.setattr(pr, "DESK", root / "desks/mt5")
    monkeypatch.setattr(pr, "QUEUE", root / "desks/mt5/data/probation_queue.json")
    monkeypatch.setattr(pr, "STATE", root / "desks/mt5/data/probation_state.json")
    monkeypatch.setattr(pr, "OUT", root / "desks/mt5/reports/PROBATION.json")
    pr.QUEUE.parent.mkdir(parents=True, exist_ok=True)
    return root


def test_probation_runs_an_organ_and_records_history(monkeypatch, tmp_path):
    root = _pr_tree(monkeypatch, tmp_path)
    organ = root / "desks/mt5/research/tiny.py"
    organ.write_text("import sys\nprint('ok', sys.argv[1:])\n", encoding="utf-8")
    pr.QUEUE.write_text(json.dumps({"queue": [{"organ": "desks/mt5/research/tiny.py",
                                               "dry_run": True, "budget_s": 30}]}),
                        encoding="utf-8")
    assert pr.main(["--per-pass", "4"]) == 0
    out = json.loads(pr.OUT.read_text(encoding="utf-8"))
    assert out["ran"][0]["status"] == "OK" and out["ran"][0]["dry_run"] is True
    assert out["ran"][0]["argv"] == ["--dry-run"]
    hist = json.loads(pr.STATE.read_text(encoding="utf-8"))["history"]
    assert hist["desks/mt5/research/tiny.py"]["clean"] == 1
    for _ in range(2):
        pr.main([])
    out = json.loads(pr.OUT.read_text(encoding="utf-8"))
    assert out["promotable"] == ["desks/mt5/research/tiny.py"]


def test_the_pass_is_bounded_by_max_organs_and_continues_where_it_stopped(monkeypatch, tmp_path):
    root = _pr_tree(monkeypatch, tmp_path)
    for i in range(5):
        (root / f"desks/mt5/research/o{i}.py").write_text("print('ok')\n", encoding="utf-8")
    pr.QUEUE.write_text(json.dumps({"queue": [{"organ": f"desks/mt5/research/o{i}.py"}
                                              for i in range(5)]}), encoding="utf-8")
    assert pr.main(["--max-organs", "2"]) == 0
    out = json.loads(pr.OUT.read_text(encoding="utf-8"))
    assert [r["organ"] for r in out["ran"]] == ["desks/mt5/research/o0.py",
                                                "desks/mt5/research/o1.py"]
    assert out["cursor"]["next_probation"] == "desks/mt5/research/o2.py"
    assert out["cursor"]["never_run"] == 3
    pr.main(["--max-organs", "2"])                      # the next pass resumes, never restarts
    out = json.loads(pr.OUT.read_text(encoding="utf-8"))
    assert [r["organ"] for r in out["ran"]] == ["desks/mt5/research/o2.py",
                                                "desks/mt5/research/o3.py"]
    assert out["cursor"]["next_probation"] == "desks/mt5/research/o4.py"
    hist = json.loads(pr.STATE.read_text(encoding="utf-8"))["history"]
    assert len(hist) == 4 and all(h["clean"] == 1 for h in hist.values())


def test_a_pass_cut_short_keeps_every_organ_it_already_measured(monkeypatch, tmp_path):
    """The cycle kills this leg at ITS budget; a pass that only saved at the end would record
    nothing, every hour, forever."""
    root = _pr_tree(monkeypatch, tmp_path)
    for i in range(4):
        (root / f"desks/mt5/research/o{i}.py").write_text("print('ok')\n", encoding="utf-8")
    pr.QUEUE.write_text(json.dumps({"queue": [{"organ": f"desks/mt5/research/o{i}.py"}
                                              for i in range(4)]}), encoding="utf-8")
    seen: list[str] = []
    real = pr.run_one

    def slow(row, budget_s, cwd=None):
        seen.append(row["organ"])
        if len(seen) == 2:
            time.sleep(1.2)                 # spends the pass budget inside the second organ
        return real(row, budget_s, cwd)

    monkeypatch.setattr(pr, "run_one", slow)
    assert pr.main(["--budget-s", "1"]) == 0
    out = json.loads(pr.OUT.read_text(encoding="utf-8"))
    assert len(out["ran"]) == 2 and "budget" in out["pass"]["stopped_why"]
    assert out["pass"]["ran"] == 2
    hist = json.loads(pr.STATE.read_text(encoding="utf-8"))["history"]
    assert set(hist) == {"desks/mt5/research/o0.py", "desks/mt5/research/o1.py"}


def test_revive_reruns_clocked_but_silent_organs_and_names_what_stops_them(monkeypatch, tmp_path):
    root = _pr_tree(monkeypatch, tmp_path)
    (root / "desks/mt5/research/works.py").write_text("print('filed')\n", encoding="utf-8")
    (root / "desks/mt5/research/brokenminer.py").write_text(
        "raise RuntimeError('no API key')\n", encoding="utf-8")
    pr.QUEUE.write_text(json.dumps({"queue": [], "revive": [
        {"organ": "desks/mt5/research/works.py", "clock": "ops/quant-x.timer",
         "last_output": "2026-09-10T00:00:00+00:00", "argv": [], "source": "scout_roster"},
        {"organ": "desks/mt5/research/brokenminer.py", "clock": "ops/quant-y.timer",
         "last_output": None, "argv": [], "source": "scout_roster"}]}), encoding="utf-8")
    assert pr.main([]) == 0
    out = json.loads(pr.OUT.read_text(encoding="utf-8"))
    rows = {r["organ"]: r for r in out["revive"]}
    assert rows["desks/mt5/research/works.py"]["revived"] is True
    bad = rows["desks/mt5/research/brokenminer.py"]
    assert bad["revived"] is False and "RuntimeError: no API key" in bad["reason"]
    assert bad["clock"] == "ops/quant-y.timer" and bad["last_output"] is None
    assert out["n_revived"] == 1
    assert [u["organ"] for u in out["unrevivable"]] == ["desks/mt5/research/brokenminer.py"]
    # a revive row is run FOR REAL -- never with the flag that makes an organ produce nothing
    assert all("--dry-run" not in r["argv"] for r in out["revive"])


def test_probation_refuses_a_money_path_row_even_if_the_queue_carries_one(monkeypatch, tmp_path):
    root = _pr_tree(monkeypatch, tmp_path)
    (root / "desks/mt5/research/gateway_thing.py").write_text("print('x')\n", encoding="utf-8")
    pr.QUEUE.write_text(json.dumps({"queue": [], "revive": [
        {"organ": "desks/mt5/research/gateway_thing.py", "clock": "t"}]}), encoding="utf-8")
    assert pr.main([]) == 0
    out = json.loads(pr.OUT.read_text(encoding="utf-8"))
    assert out["revive"] == [] and out["ran"] == []
    assert pr.run_one({"organ": "desks/mt5/research/gateway_thing.py"}, 5)["status"] == "REFUSED"


def test_auto_legs_clock_only_organs_probation_ran_clean_and_pick_the_plan():
    probation = [{"organ": "desks/mt5/research/fast.py", "dry_run": True, "budget_s": 120},
                 {"organ": "desks/mt5/research/slow.py", "dry_run": False, "budget_s": 120},
                 {"organ": "desks/mt5/research/never.py", "dry_run": True, "budget_s": 120}]
    state = {"history": {"desks/mt5/research/fast.py": {"runs": 3, "clean": 3, "seconds": 12.0},
                         "desks/mt5/research/slow.py": {"runs": 1, "clean": 1, "seconds": 95.0}}}
    legs = {x["leg"]: x for x in wc.auto_legs(probation, state)}
    assert set(legs) == {"auto_fast", "auto_slow"}          # never ran clean -> not clocked
    assert legs["auto_fast"]["plan"] == "core"
    assert legs["auto_slow"]["plan"] == "heavy"
    # THE DRY-RUN TRAP: probation may pass --dry-run, a CLOCK never may.
    assert all(x["argv"] == [] for x in legs.values())


def test_no_auto_leg_ever_carries_dry_run_and_production_args_are_the_organs_own(monkeypatch,
                                                                                tmp_path):
    root = _tree(tmp_path)
    _point(monkeypatch, root)
    r = root / "desks/mt5/research"
    (r / "orphan_organ.py").write_text(
        "import argparse\nPRODUCTION_ARGS = ['--apply', '--max-donations', '15']\n"
        "def main():\n    ap = argparse.ArgumentParser()\n"
        "    ap.add_argument('--dry-run', action='store_true')\n    return 0\n", encoding="utf-8")
    # an organ that only MENTIONS --dry-run in its prose does not take it
    (r / "mentions_only.py").write_text(
        '"""usage: mentions_only.py --dry-run"""\ndef main():\n    return 0\n', encoding="utf-8")
    state = root / "desks/mt5/data/probation_state.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({"history": {
        "desks/mt5/research/orphan_organ.py": {"runs": 2, "clean": 2, "seconds": 3.0},
        "desks/mt5/research/mentions_only.py": {"runs": 1, "clean": 1, "seconds": 2.0}}}),
        encoding="utf-8")
    doc = wc.build(apply=True)
    legs = {x["leg"]: x for x in json.loads(wc.AUTO_LEGS.read_text(encoding="utf-8"))["legs"]}
    assert legs["auto_orphan_organ"]["argv"] == ["--apply", "--max-donations", "15"]
    assert legs["auto_mentions_only"]["argv"] == []
    assert "--dry-run" not in wc.AUTO_LEGS.read_text(encoding="utf-8")
    assert doc["auto_legs"]["n"] == 2 and doc["auto_legs"]["with_production_argv"] == 1
    # probation still proves the organ STARTS with its own flag; the mention-only one does not
    q = {x["organ"]: x for x in json.loads(wc.PROBATION_QUEUE.read_text(encoding="utf-8"))["queue"]}
    assert q["desks/mt5/research/orphan_organ.py"]["dry_run"] is True
    assert q["desks/mt5/research/mentions_only.py"]["dry_run"] is False


def test_an_auto_clocked_organ_counts_as_scheduled_so_the_ratchet_can_fall(monkeypatch, tmp_path):
    root = _tree(tmp_path)
    _point(monkeypatch, root)
    organ = "desks/mt5/research/orphan_organ.py"
    before = wc.build(apply=True)["n_unwired"]
    assert json.loads(wc.AUTO_LEGS.read_text(encoding="utf-8"))["legs"] == []   # no clean run yet
    state = root / "desks/mt5/data/probation_state.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({"history": {organ: {"runs": 1, "clean": 1, "seconds": 4.0}}}),
                     encoding="utf-8")
    doc = wc.build(apply=True)                        # probation proved it: it earns a clock
    assert doc["auto_legs"]["n"] == 1
    assert [x["organ"] for x in
            json.loads(wc.AUTO_LEGS.read_text(encoding="utf-8"))["legs"]] == [organ]
    assert doc["n_unwired"] == before                 # the clock is not visible until it is read
    doc = wc.build(apply=True)                        # next pass: auto_legs.json IS a clock
    assert doc["n_unwired"] == before - 1 and doc["floor"]["status"] == "RATCHETED"
    assert organ not in {r["organ"] for r in doc["unwired"]}
    assert organ not in {r["organ"] for r in doc["probation"]}
    # and it STAYS clocked -- rebuilding auto_legs from the probation list alone dropped it
    assert [x["organ"] for x in
            json.loads(wc.AUTO_LEGS.read_text(encoding="utf-8"))["legs"]] == [organ]


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


def test_library_modules_are_judged_by_reach_and_the_dead_list_is_imported_by_nothing(
        monkeypatch, tmp_path):
    root = _tree(tmp_path)
    _point(monkeypatch, root)
    doc = wc.build(apply=True)
    assert doc["library"]["n"] == 4                       # four .py files with no main()
    rows = {r["module"]: r for r in doc["library_unreached"]}
    assert "desks/mt5/research/helper_lib.py" not in rows      # a clocked organ imports it
    assert doc["library"]["reached"] == 1
    lib = rows["desks/mt5/research/unwired_only_lib.py"]
    assert lib["importers"] == 1 and lib["importers_sample"] == [
        "desks/mt5/research/orphan_organ.py"] and not lib["reached_by_clock"]
    assert "desks/mt5/research/unwired_only_lib.py" not in doc["library_dead"]
    assert sorted(doc["library_dead"]) == ["desks/mt5/research/handrun_script.py",
                                           "desks/mt5/research/orphan_lib.py"]
    assert doc["library"]["dead_scripts"] == 1             # the hand-run one needs a main(), not a
    assert rows["desks/mt5/research/handrun_script.py"]["kind"] == "script_no_main"
    # a library is never an organ and never an unwired row -- it cannot be clocked at all
    assert not {r["organ"] for r in doc["unwired"]} & set(rows)


def test_a_from_package_import_module_still_counts_as_an_importer(monkeypatch, tmp_path):
    """`from side_channels import china_miner` binds a MODULE, and the narrow extraction the
    scheduling closure uses cannot see it. Reach uses the wider one, because a false DEAD verdict
    proposes deleting live code."""
    root = _tree(tmp_path)
    _point(monkeypatch, root)
    (root / "desks/mt5/research/helper_organ.py").write_text(
        "from research import orphan_lib\ndef main():\n    return 0\n", encoding="utf-8")
    doc = wc.build(apply=True)
    assert "desks/mt5/research/orphan_lib.py" not in doc["library_dead"]


def test_clock_signature_reads_every_shape_the_forward_engine_writes():
    assert wc._clock_signature("XAUUSD.asia") == ("XAUUSD", "session_range_breakout", "asia")
    assert wc._clock_signature("CADJPY.asia.FAILED_BREAK") == (
        "CADJPY", "session_range_breakout", "asia")
    assert wc._clock_signature("EURZAR.overnight_gap_decay.asia") == (
        "EURZAR", "overnight_gap_decay", "asia")
    assert wc._clock_signature("CADJPY.asia#rr=2.5") == (
        "CADJPY", "session_range_breakout", "asia")
    assert wc._clock_signature("XAUUSD.asia@M5.SHORT") == (
        "XAUUSD", "session_range_breakout", "asia")
    assert wc._clock_signature("XAUUSD") is None


def test_certificates_without_clocks_is_counted_and_unreadable_is_never_zero(monkeypatch,
                                                                            tmp_path):
    root = _tree(tmp_path)
    _point(monkeypatch, root)
    assert wc.certificate_clocks()["n"] is None           # UNMEASURED, never 0 (L1.28a)
    reports = root / "desks/mt5/reports"
    (reports / "shadow").mkdir(parents=True, exist_ok=True)
    (reports / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps({"survivors": {
        "a": {"shadow_spec": {"symbol": "XAUUSD", "family": "session_range_breakout",
                              "selector": "asia"}},
        "b": {"shadow_spec": {"symbol": "AUDNZD", "family": "dav_range_filter_adx",
                              "selector": "afternoon"}},
        "c": {"shadow_spec": {"symbol": "EURZAR", "family": "overnight_gap_decay",
                              "selector": "asia"}},
        "d": {"shadow_spec": {"symbol": "USDZAR", "family": "overnight_gap_decay",
                              "selector": "asia"}}}}), encoding="utf-8")
    (reports / "shadow" / "shadow_state.json").write_text(json.dumps({
        "XAUUSD.asia": {"status": "ACTIVE"},
        "EURZAR.overnight_gap_decay.asia": {"status": "IDENTITY_BROKEN"},
        "USDZAR.overnight_gap_decay.asia": {"status": "REFUSED_BY_UNIVERSE_POLICY"}}),
        encoding="utf-8")
    c = wc.certificate_clocks()
    assert c["n"] == 3 and c["n_certificates"] == 4 and c["n_clocked"] == 1
    assert c["by_status"] == {"NO_CLOCK_ROW": 1, "IDENTITY_BROKEN": 1,
                              "REFUSED_BY_UNIVERSE_POLICY": 1}
    # a policy refusal is a verdict about the instrument, never a clock for the healer to revive
    assert c["healable"] == 1
    assert wc.build(apply=False)["certificates_without_clocks"] == 3


def test_the_identity_healer_is_named_as_a_gap_when_it_cannot_run_here(monkeypatch, tmp_path):
    root = _tree(tmp_path)
    _point(monkeypatch, root)
    heal = wc.build(apply=True)["identity_heal"]
    assert "sleeve registry" in heal["gap"] and heal["applied"] is True
    assert heal["callables"] == ["heal_identity_broken_clocks.backfill_behaviour",
                                 "heal_identity_broken_clocks.freeze_unfrozen"]


def test_revive_queue_takes_clocked_but_silent_scouts_and_failing_auto_legs(monkeypatch,
                                                                           tmp_path):
    root = _tree(tmp_path)
    _point(monkeypatch, root)
    (root / "desks/mt5/reports").mkdir(parents=True, exist_ok=True)
    (root / "desks/mt5/reports/SCOUT_ROSTER.json").write_text(json.dumps({"scouts": [
        {"name": "silent", "organ_file": "desks/mt5/research/orphan_organ.py",
         "status": "broken", "clock": "ops/quant-x.timer", "cadence_s": 3600.0,
         "last_output_at": "2026-09-10T00:00:00+00:00"},
        {"name": "filing", "organ_file": "desks/mt5/research/scheduled_organ.py",
         "status": "active", "clock": "ops/quant-y.timer", "cadence_s": 3600.0,
         "last_output_at": "2026-09-17T00:00:00+00:00"},
        {"name": "no_clock", "organ_file": "desks/mt5/research/helper_organ.py",
         "status": "UNMEASURED", "clock": None, "cadence_s": None, "last_output_at": None},
        {"name": "money", "organ_file": "desks/mt5/research/gateway_thing.py",
         "status": "broken", "clock": "ops/quant-z.timer", "cadence_s": 3600.0,
         "last_output_at": None}]}), encoding="utf-8")
    state = {"history": {"desks/mt5/research/needs_args.py": {"runs": 2, "clean": 0,
                                                              "last_status": "EXIT"}}}
    rows = {r["organ"]: r for r in wc.revive_queue(
        {"desks/mt5/research/orphan_organ.py": ["ops/quant-x.timer"]},
        [{"organ": "desks/mt5/research/needs_args.py", "budget_s": 120}], state)}
    assert set(rows) == {"desks/mt5/research/orphan_organ.py",
                         "desks/mt5/research/needs_args.py"}
    silent = rows["desks/mt5/research/orphan_organ.py"]
    assert silent["clock"] == "ops/quant-x.timer" and silent["source"] == "scout_roster"
    assert silent["last_output"] == "2026-09-10T00:00:00+00:00"
    assert silent["argv"] == []                 # production args, and NEVER --dry-run
    assert rows["desks/mt5/research/needs_args.py"]["source"] == "auto_legs"
    doc = wc.build(apply=True)
    assert doc["n_revive"] == 1                 # the auto leg has no failing history in this pass
    queued = json.loads(wc.PROBATION_QUEUE.read_text(encoding="utf-8"))["revive"]
    assert [r["organ"] for r in queued] == ["desks/mt5/research/orphan_organ.py"]


def test_a_named_leg_takes_an_auto_clocked_organ_over_and_it_stops_running_twice(monkeypatch,
                                                                                tmp_path):
    root = _tree(tmp_path)
    _point(monkeypatch, root)
    organ = "desks/mt5/research/orphan_organ.py"
    state = root / "desks/mt5/data/probation_state.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({"history": {organ: {"runs": 3, "clean": 3, "seconds": 2.0}}}),
                     encoding="utf-8")
    assert wc.build(apply=True)["auto_legs"]["n"] == 1
    # a session promotes it to a named leg in the cycle
    (root / "desks/mt5/research/hourly_cycle.py").write_text(
        'import helper_organ\ndef main():\n    _producer("x", "research/scheduled_organ.py")\n'
        '    _producer("y", "research/orphan_organ.py")\n', encoding="utf-8")
    doc = wc.build(apply=True)
    assert doc["auto_legs"]["n"] == 0
    assert json.loads(wc.AUTO_LEGS.read_text(encoding="utf-8"))["legs"] == []
    # reached only through an importer is NOT a named leg: helper_organ keeps nothing but its
    # import edge, and directly_clocked must not claim it
    named = {"a.py": ["ops/x.timer"], "b.py": ["imported by a.py"], "c.py": [wc.AUTO_CLOCK]}
    assert wc.directly_clocked(named) == {"a.py"}
