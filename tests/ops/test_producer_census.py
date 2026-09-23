"""THE CENSUS MUST NOT BE ABLE TO GO BLIND AGAIN.

Every test here pins one of the five ways a producer went dark on the trading box on
2026-09-23, because each had a different remedy and a fence that collapsed them would have
fixed at most one: a clock on the wrong machine, a seat retired without an inheritor, an
environment provisioned on the wrong box, a mapping table never filled in, and an executable
that landed without a leg.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from libs.ops import producer_census as pc
from libs.ops.control_plane import actuators as act


def _tree(root: Path) -> None:
    (root / "data" / "intelligence").mkdir(parents=True)
    (root / "desks" / "mt5" / "data" / "intelligence").mkdir(parents=True)
    (root / "desks" / "mt5" / "reports").mkdir(parents=True)
    (root / "docs" / "research").mkdir(parents=True)
    (root / "libs").mkdir()
    (root / "scripts").mkdir()
    (root / "ops").mkdir()


def _seat(root: Path, name: str, *, age_s: float = 0.0) -> Path:
    d = root / "data" / "intelligence" / name
    d.mkdir(parents=True, exist_ok=True)
    f = d / "discoveries_1.json"
    f.write_text("{}", encoding="utf-8")
    if age_s:
        stamp = time.time() - age_s
        import os
        os.utime(f, (stamp, stamp))
    return d


@pytest.fixture(autouse=True)
def _no_cache() -> Any:
    pc._SCAN_CACHE.clear()
    pc._RUNTIME_CACHE.clear()
    yield
    pc._SCAN_CACHE.clear()
    pc._RUNTIME_CACHE.clear()


# ------------------------------------------------------- cause 4: the mapping never filled in
def test_tier1_literal_writer_is_derived_and_mapped_to_its_clock(tmp_path: Path) -> None:
    """A miner that names `data/intelligence/<seat>` is found WITHOUT anybody typing a table."""
    _tree(tmp_path)
    _seat(tmp_path, "aaii")
    (tmp_path / "desks" / "mt5" / "side_channels").mkdir(parents=True)
    (tmp_path / "desks" / "mt5" / "side_channels" / "aaii_miner.py").write_text(
        'OUT = BASE / "data" / "intelligence" / "aaii"\np.mkdir(parents=True)\n', encoding="utf-8")
    clocks = {"desks/mt5/side_channels/aaii_miner.py":
              {"clock": "hourly_cycle:aaii", "host": "either", "cadence_h": 1.0}}

    der = pc.derive_seat_organs(tmp_path, clocked=clocks)

    assert der["aaii"]["organ"] == "desks/mt5/side_channels/aaii_miner.py"
    assert der["aaii"]["tier"] == 1
    assert der["aaii"]["hops"] == 0


def test_tier1_walks_hops_to_the_file_that_actually_holds_the_clock(tmp_path: Path) -> None:
    """The seed-miner shape: the clock runs a sweep that imports the miner that writes the seat."""
    _tree(tmp_path)
    _seat(tmp_path, "academic")
    sc = tmp_path / "desks" / "mt5" / "side_channels"
    sc.mkdir(parents=True)
    (sc / "academic_miner.py").write_text(
        'OUT = BASE / "data" / "intelligence" / "academic"\nmkdir\n', encoding="utf-8")
    (sc / "seed_miners.py").write_text("from academic_miner import run\n", encoding="utf-8")
    clocks = {"desks/mt5/side_channels/seed_miners.py":
              {"clock": "quant-seed-miners.timer", "host": "vps", "cadence_h": 1.0}}

    der = pc.derive_seat_organs(tmp_path, clocked=clocks)

    assert der["academic"]["organ"] == "desks/mt5/side_channels/seed_miners.py"
    assert der["academic"]["writer"] == "desks/mt5/side_channels/academic_miner.py"
    assert der["academic"]["hops"] == 1


def test_tier2_roster_seat_with_no_literal_path_anywhere(tmp_path: Path) -> None:
    """Fifty seats are filled from one table; no literal path for any of them exists."""
    _tree(tmp_path)
    _seat(tmp_path, "darwinex")
    sc = tmp_path / "desks" / "mt5" / "side_channels"
    sc.mkdir(parents=True)
    (sc / "roster_miner.py").write_text(
        'SOURCES = ["darwinex", "collective2"]\n'
        'INTEL = BASE / "data" / "intelligence"\n'
        'for s in SOURCES:\n    (INTEL / s).mkdir(parents=True, exist_ok=True)\n',
        encoding="utf-8")
    clocks = {"desks/mt5/side_channels/roster_miner.py":
              {"clock": "hourly_cycle:roster", "host": "either", "cadence_h": 1.0}}

    der = pc.derive_seat_organs(tmp_path, clocked=clocks)

    assert der["darwinex"]["tier"] == 2
    assert der["darwinex"]["organ"] == "desks/mt5/side_channels/roster_miner.py"


def test_a_fence_never_wins_the_organ_slot_over_the_miner(tmp_path: Path) -> None:
    """A fence READS the seat. Naming it as the organ would point every repair at the wrong
    process -- which is how the hand table pointed four live seats at files that never existed."""
    _tree(tmp_path)
    _seat(tmp_path, "mql5")
    sc = tmp_path / "desks" / "mt5" / "side_channels"
    sc.mkdir(parents=True)
    (sc / "mql5_miner.py").write_text(
        'OUT = BASE / "data" / "intelligence" / "mql5"\nmkdir\n', encoding="utf-8")
    (tmp_path / "scripts" / "check_mql5.py").write_text(
        'from libs.ops.fence_exit import fence_exit\n'
        'SEATS = BASE / "data" / "intelligence" / "mql5"\nmkdir\n', encoding="utf-8")
    clocks = {"desks/mt5/side_channels/mql5_miner.py":
              {"clock": "hourly_cycle:mql5", "host": "either", "cadence_h": 1.0},
              "scripts/check_mql5.py":
              {"clock": "hourly_cycle:fence_battery", "host": "either", "cadence_h": 1.0}}

    der = pc.derive_seat_organs(tmp_path, clocked=clocks)

    assert der["mql5"]["organ"] == "desks/mt5/side_channels/mql5_miner.py"


def test_a_seat_no_organ_reaches_is_a_mapping_defect_not_unmeasured(tmp_path: Path) -> None:
    """THE INVERSION THIS WHOLE MODULE EXISTS TO KILL: 92 seats read UNMEASURED because a table
    had never been filled in, and UNMEASURED reads as 'nothing to do'."""
    _tree(tmp_path)
    _seat(tmp_path, "orphan_seat", age_s=400 * 3600)

    rows = pc.seat_rows(root=tmp_path, clocks={}, derived={}, retired={}, runs_here=True)
    row = next(r for r in rows if r.producer == "orphan_seat")

    assert row.verdict == pc.DARK
    assert row.details["mapping_gap"] is True
    assert "defect in the mapping" in row.why
    doc = {"dark_silent": [], "mapping_gaps": ["orphan_seat"]}
    assert pc.breach(doc), "a mapping gap must fail the fence, never excuse it"


# ------------------------------------------- cause 2: a seat retired without a named inheritor
def test_retired_seat_carries_its_inheritor(tmp_path: Path) -> None:
    _tree(tmp_path)
    (tmp_path / "docs" / "research" / "retirements.jsonl").write_text(
        json.dumps({"seat": "mql5_catalog", "reason": "one-shot crawl",
                    "replacement": "mql5_signals"}) + "\n", encoding="utf-8")
    _seat(tmp_path, "mql5_catalog", age_s=900 * 3600)

    ret = pc.retirements(tmp_path)
    rows = pc.seat_rows(root=tmp_path, clocks={}, derived={}, retired=ret, runs_here=True)
    row = next(r for r in rows if r.producer == "mql5_catalog")

    assert row.verdict == pc.RETIRED
    assert row.details["inheritor"] == "mql5_signals"


def test_a_retirement_with_no_replacement_is_named_an_abandonment(tmp_path: Path) -> None:
    _tree(tmp_path)
    (tmp_path / "docs" / "research" / "retirements.jsonl").write_text(
        json.dumps({"seat": "ghost", "reason": "stopped"}) + "\n", encoding="utf-8")
    _seat(tmp_path, "ghost", age_s=900 * 3600)

    rows = pc.seat_rows(root=tmp_path, clocks={}, derived={},
                        retired=pc.retirements(tmp_path), runs_here=True)
    row = next(r for r in rows if r.producer == "ghost")

    assert row.verdict == pc.RETIRED
    assert row.details["inheritor"] is None
    assert "NO INHERITOR" in row.why


# --------------------------------------------------- cause 1: a clock on the other machine
def test_a_mirror_checkout_never_judges_a_producer_it_does_not_run(tmp_path: Path) -> None:
    """A build box is Windows too. Judging its git-mirrored seats reported a hundred healthy
    producers DARK for work happening correctly on the machine that holds the clocks."""
    _tree(tmp_path)
    _seat(tmp_path, "china", age_s=300 * 3600)
    clocks = {"m.py": {"clock": "hourly_cycle:china", "host": "either", "cadence_h": 1.0}}

    rows = pc.seat_rows(root=tmp_path, clocks=clocks, declared={"china": "m.py"},
                        derived={}, retired={}, runs_here=False)
    row = next(r for r in rows if r.producer == "china")

    assert row.verdict == pc.UNMEASURED_HERE
    assert "holds NONE of the desk's clocks" in row.why
    #: and with the clocks here, the SAME seat is a defect
    rows = pc.seat_rows(root=tmp_path, clocks=clocks, declared={"china": "m.py"},
                        derived={}, retired={}, runs_here=True)
    assert next(r for r in rows if r.producer == "china").verdict == pc.DARK


def test_an_unreadable_scheduler_is_unmeasured_and_never_a_pass() -> None:
    assert pc.mirror_reason("either", "box", None, "c") is not None
    assert pc.mirror_reason("box", "box", True, "c") is None
    assert pc.mirror_reason("vps", "box", True, "c") is not None


# ---------------------------------------------------------------- the verdicts themselves
@pytest.mark.parametrize(("age_h", "want"), [(0.5, pc.LIVE), (2.0, pc.SLOW), (9.0, pc.DARK)])
def test_live_slow_dark_are_measured_against_the_declared_budget(age_h: float,
                                                                 want: str) -> None:
    verdict, why = pc._judge(age_h * 3600, 3600, 6 * 3600, label="x")
    assert verdict == want
    assert why


def test_never_produced_is_dark_not_unmeasured() -> None:
    assert pc._judge(None, 3600, 6 * 3600, label="x")[0] == pc.DARK


def test_no_silence_budget_is_unmeasured_never_a_pass() -> None:
    assert pc._judge(10.0, None, None, label="x")[0] == pc.UNMEASURED


# ----------------------------------------- cause 5: an executable that landed without a leg
def test_the_unclocked_ratchet_is_the_birth_fences_and_is_not_double_counted() -> None:
    """Two ratchets on one number is how a fence starts being argued with instead of read."""
    doc = {"dark": ["a", "b"], "dark_silent": ["a"], "dark_unclocked": ["b"],
           "mapping_gaps": []}
    assert pc.breach(doc, ratchet=1) == []
    assert pc.breach(doc, ratchet=0)


def test_the_dark_ratchet_may_only_fall() -> None:
    assert pc.DARK_RATCHET == 0, "the ratchet is a residue that falls, never a tolerance"


# ----------------------------------------------------------------- relighting, and its proof
def test_relight_is_proved_by_production_not_by_exit_code(tmp_path: Path) -> None:
    _tree(tmp_path)
    seat = _seat(tmp_path, "kimi", age_s=300 * 3600)
    doc = {"rows": [{"producer": "kimi", "verdict": pc.DARK, "repair": "run_organ",
                     "organ": "scripts/kimi_hunter.py", "criticality": "optional",
                     "age_h": 300.0,
                     "production_paths": ["data/intelligence/kimi"]}]}
    (tmp_path / "scripts" / "kimi_hunter.py").write_text("--once --budget-s\n", encoding="utf-8")
    plans = pc.plan_relight(doc, root=tmp_path, budget_s=5)
    assert plans and plans[0].action == "run_organ"
    assert "--once" in plans[0].argv and "--budget-s" in plans[0].argv

    def produced(argv: Any, timeout_s: int, cwd: str | None) -> dict[str, Any]:
        (seat / "discoveries_2.json").write_text("{}", encoding="utf-8")
        return {"rc": 0, "tail": ""}

    recs = pc.apply_relight(plans, root=tmp_path, runner=produced)
    assert recs[0]["result"] == "RELIT" and recs[0]["relit"] is True


def test_a_repair_that_exits_zero_and_produces_nothing_is_unproven(tmp_path: Path) -> None:
    """The exact failure the law names: publishing rc=0 for an organ that never resumed."""
    _tree(tmp_path)
    _seat(tmp_path, "kimi", age_s=300 * 3600)
    (tmp_path / "scripts" / "kimi_hunter.py").write_text("x\n", encoding="utf-8")
    doc = {"rows": [{"producer": "kimi", "verdict": pc.DARK, "repair": "run_organ",
                     "organ": "scripts/kimi_hunter.py", "criticality": "optional",
                     "age_h": 300.0,
                     "production_paths": ["data/intelligence/kimi"]}]}
    plans = pc.plan_relight(doc, root=tmp_path, budget_s=5)

    recs = pc.apply_relight(plans, root=tmp_path,
                            runner=lambda a, t, c: {"rc": 0, "tail": "done"})

    assert recs[0]["result"] == "UNPROVEN" and recs[0]["relit"] is False


def test_a_clock_or_retire_row_is_never_pretended_to_be_runnable(tmp_path: Path) -> None:
    """Giving an organ a leg is a CODE change; an hourly leg that edited the cycle to heal
    itself would be a loop nobody could review."""
    _tree(tmp_path)
    doc = {"rows": [{"producer": "x", "verdict": pc.DARK, "repair": "retire_or_clock",
                     "organ": None, "criticality": "optional", "age_h": 9.0,
                     "production_paths": []}]}
    assert pc.plan_relight(doc, root=tmp_path) == []


def test_production_resumed_postcondition_reads_a_directory(tmp_path: Path) -> None:
    d = tmp_path / "seat"
    d.mkdir()
    ctx = {"production_paths": [str(d)], "production_before": None}
    assert act.PRODUCTION_RESUMED.check(ctx)[0] is False
    (d / "a.json").write_text("{}", encoding="utf-8")
    assert act.PRODUCTION_RESUMED.check(ctx)[0] is True
    before = act.newest_production([d])
    assert act.PRODUCTION_RESUMED.check(
        {"production_paths": [str(d)], "production_before": before})[0] is False


def test_production_resumed_with_no_paths_is_unmeasured() -> None:
    assert act.PRODUCTION_RESUMED.check({})[0] is None


# ------------------------------------------------------------------------- the wiring itself
def test_the_census_has_a_clock_a_layer_and_an_artifact() -> None:
    """UNWIRED OR IDLE IS A DEFECT (LAWS III.16)."""
    from libs.research import layers

    cycle = (Path(__file__).resolve().parents[2] / "desks" / "mt5" / "research"
             / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '_producer(\n        "producer_census", "scripts/check_seat_health.py"' in cycle
    assert '"producer_census": pcn' in cycle
    assert layers.LEG_LAYER["producer_census"] == "meta"


def test_the_census_covers_seats_components_and_the_sandbox(tmp_path: Path) -> None:
    """Derived from the registry, not a hand list, so a new organ is covered the day it lands."""
    _tree(tmp_path)
    _seat(tmp_path, "s1")
    (tmp_path / "desks" / "mt5" / "reports" / "SANDBOX_LIVENESS.json").write_text(
        json.dumps({"n_runnable": 3, "n_unmeasured": 5,
                    "reasons": {"aeon": {"why": "not importable"}}}), encoding="utf-8")

    doc = pc.census(root=tmp_path, clocks={}, registry=None)

    kinds = {r["kind"] for r in doc["rows"]}
    assert {"seat", "sandbox"} <= kinds
    assert any(r["producer"] == "sandbox:aeon" for r in doc["rows"])
    assert doc["law"].startswith("EVERY SEAT, MINER AND RESEARCH ORGAN")


def test_an_older_control_plane_still_relights_and_says_so(tmp_path: Path,
                                                           monkeypatch: Any) -> None:
    """A box that has not adopted `producer_actuator` still has dark producers; the repair runs
    with the SAME proof and the record names the fallback rather than claiming the plane."""
    _tree(tmp_path)
    seat = _seat(tmp_path, "kimi", age_s=300 * 3600)
    (tmp_path / "scripts" / "kimi_hunter.py").write_text("--once\n", encoding="utf-8")
    monkeypatch.delattr(act, "producer_actuator", raising=True)
    doc = {"rows": [{"producer": "kimi", "verdict": pc.DARK, "repair": "run_organ",
                     "organ": "scripts/kimi_hunter.py", "criticality": "optional",
                     "age_h": 300.0, "production_paths": ["data/intelligence/kimi"]}]}
    plans = pc.plan_relight(doc, root=tmp_path, budget_s=5)

    def produced(argv: Any, timeout_s: int, cwd: str | None) -> dict[str, Any]:
        (seat / "discoveries_3.json").write_text("{}", encoding="utf-8")
        return {"rc": 0, "tail": ""}

    recs = pc.apply_relight(plans, root=tmp_path, runner=produced)

    assert recs[0]["result"] == "RELIT"
    assert recs[0]["plane"] == "fallback"
