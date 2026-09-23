"""THE STANDING BATTERIES: a rotation is a clock, and a rostered organ is never silence.

WHAT THESE PIN (principal 2026-09-22: "hunt all unwired unused unscheduled etc n make all wired
used scheduled everything. 100 percent of everything built always must be used never forgotten").

  * the rotation ADVANCES -- a second pass runs organs the first pass did not, so every rostered
    organ runs within one full rotation instead of the first N being exercised forever;
  * the artifact names what has NEVER run and what is FAILING, with the AGE of each verdict, so a
    rostered organ that died is a named row rather than an absence;
  * the memory floor is DERIVED from the total this machine actually reports, and an unreadable
    counter starts the organ (UNMEASURED is not a stop signal);
  * every rostered path EXISTS -- a roster that names a file the tree does not hold is a clock
    pointing at nothing, which is the defect the batteries were built to remove;
  * the registry gives every rostered organ a clock AND a freshness expectation (cadence and
    max_silence), so an anti-staleness prover can hold it to one without asking this file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import batteries as B  # noqa: E402
from desks.mt5.ops import components as C  # noqa: E402


def _organ(tmp_path: Path, name: str, body: str) -> str:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return name


@pytest.fixture
def desk(tmp_path: Path) -> Path:
    (tmp_path / "desks" / "mt5" / "reports").mkdir(parents=True)
    (tmp_path / "desks" / "mt5" / "data").mkdir(parents=True)
    return tmp_path


def _roster(tmp_path: Path, n: int) -> tuple[B.Entry, ...]:
    return tuple(B._e(_organ(tmp_path, f"organ{i}.py", "print('ok')\n"), f"organ {i}")
                 for i in range(n))


def test_rotation_advances_so_every_rostered_organ_runs_within_one_rotation(desk: Path) -> None:
    roster = _roster(desk, 6)
    state = desk / "state.json"
    out = desk / "desks" / "mt5" / "reports" / "BATTERY_T.json"
    seen: set[str] = set()
    for _ in range(6):
        doc = B.run_battery("t", 60.0, root=desk, state_path=state, roster=roster, out=out)
        seen |= set(doc["ran"])
        assert doc["n_ran"] >= 1, "a pass that runs nothing is not a clock"
    assert seen == {e.path for e in roster}, "the tail of the roster never ran: no rotation"
    assert json.loads(out.read_text("utf-8"))["n_never_run"] == 0


def test_the_artifact_names_never_run_and_failing_with_the_age_of_each_verdict(desk: Path) -> None:
    bad = B._e(_organ(desk, "bad.py", "raise SystemExit(3)\n"), "fails on purpose")
    good = B._e(_organ(desk, "good.py", "print('fine')\n"), "passes")
    gone = B._e("desks/mt5/research/not_a_file_here.py", "the roster points at nothing")
    out = desk / "desks" / "mt5" / "reports" / "BATTERY_T.json"
    doc = B.run_battery("t", 60.0, root=desk, state_path=desk / "s.json",
                        roster=(bad, good, gone), out=out)
    rows = {r["path"]: r for r in doc["rows"]}
    assert rows[bad.path]["verdict"] == "FAILED" and rows[bad.path]["rc"] == 3
    assert rows[good.path]["verdict"] == "OK"
    assert rows[gone.path]["verdict"] == "MISSING"
    assert set(doc["failing"]) == {bad.path, gone.path}
    assert all(isinstance(rows[p]["age_s"], float) for p in (bad.path, good.path))
    assert doc["oldest_age_s"] is not None


def test_a_never_run_organ_is_named_rather_than_counted_as_clean(desk: Path) -> None:
    slow = "import time\ntime.sleep(6)\n"
    roster = tuple(B._e(_organ(desk, f"slow{i}.py", slow), f"slow organ {i}") for i in range(4))
    out = desk / "desks" / "mt5" / "reports" / "BATTERY_T.json"
    # A budget that affords exactly one organ: the other three are NEVER_RUN, and named.
    doc = B.run_battery("t", B.MIN_SLICE_S + 5.0, root=desk, state_path=desk / "s.json",
                        roster=roster, out=out)
    assert doc["n_ran"] == 1
    assert doc["n_never_run"] == 3
    assert set(doc["never_run"]) == {e.path for e in roster[1:]}


def test_the_memory_floor_is_derived_from_this_machine_and_unmeasured_never_stops_a_pass(
        desk: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    roster = _roster(desk, 2)
    out = desk / "desks" / "mt5" / "reports" / "BATTERY_T.json"
    # A machine whose free memory has collapsed: the floor is a SHARE of its own total, so the
    # pass stops and says which number it compared against -- never a megabyte count from
    # another box (CLAUDE.md: the 96 GB note that was about a machine the code was not on).
    monkeypatch.setattr(B, "free_memory", lambda: (10.0, 64_000.0))
    doc = B.run_battery("t", 60.0, root=desk, state_path=desk / "s.json", roster=roster, out=out)
    assert doc["n_ran"] == 0 and doc["skipped"]
    assert "3840MB" in doc["skipped"][0]["why"]        # 6% of the measured 64 GB, not a constant
    # An unreadable counter is UNMEASURED and must not become a stop signal.
    monkeypatch.setattr(B, "free_memory", lambda: (None, None))
    doc2 = B.run_battery("t", 60.0, root=desk, state_path=desk / "s2.json", roster=roster,
                         out=out)
    assert doc2["n_ran"] >= 1 and doc2["memory"]["state"] == "UNMEASURED"


def test_the_slice_is_a_share_of_the_pass_budget_and_never_degenerates() -> None:
    assert B.slice_s(600.0) == B.MAX_SLICE_S          # capped: one organ cannot eat a rotation
    assert B.slice_s(10.0) == B.MIN_SLICE_S           # floored: not three seconds each
    assert B.MIN_SLICE_S < B.slice_s(200.0) < B.MAX_SLICE_S


def test_every_rostered_path_exists_in_this_tree() -> None:
    missing = [e.path for entries in B.ROSTERS.values() for e in entries
               if not (ROOT / e.path).is_file()]
    assert missing == [], f"the roster names files the tree does not hold: {missing}"


def test_no_organ_is_rostered_twice_across_the_batteries() -> None:
    seen: dict[str, str] = {}
    dupes: list[str] = []
    for name, entries in B.ROSTERS.items():
        for e in entries:
            if e.path in seen:
                dupes.append(f"{e.path} in {seen[e.path]} and {name}")
            seen[e.path] = name
    assert dupes == [], f"one organ on two clocks is two counts of one run: {dupes}"


def test_the_registry_gives_every_rostered_organ_a_clock_and_a_freshness_expectation() -> None:
    specs = {s.code_paths[0]: s for s in C.battery_specs()}
    rostered = {e.path for entries in B.ROSTERS.values() for e in entries}
    assert rostered <= set(specs), "a rostered organ the component registry cannot see"
    for rel in sorted(rostered):
        s = specs[rel]
        assert s.scheduled, f"{rel}: rostered but the registry reads it as unclocked"
        assert s.schedule.startswith("hourly_cycle:"), s.schedule
        assert s.cadence_s and s.cadence_s > 0, f"{rel}: no cadence, so no staleness to measure"
        assert s.max_silence_s and s.max_silence_s >= s.cadence_s, f"{rel}: freshness undeclared"
        assert s.outputs and s.consumers, f"{rel}: an artifact nobody reads is not wired"


def test_the_two_battery_legs_are_in_the_hourly_cycle_with_a_layer() -> None:
    from libs.research.layers import LEG_LAYER
    cycle = (DESK / "research" / "hourly_cycle.py").read_text("utf-8", errors="replace")
    for leg in ("fence_battery", "organ_battery"):
        assert f'_costed("{leg}"' in cycle, f"{leg} is not a leg of the hourly cycle"
        assert LEG_LAYER.get(leg) == "meta", f"{leg} belongs to no layer"


def test_the_country_packs_the_forest_runner_imports_by_pattern_are_reached() -> None:
    """An f-string import is invisible to a static walk; the roster and the pattern are not."""
    roots = C.dynamic_reach_roots()
    assert roots, "no dynamic root: the eleven forests import their packs at runtime"
    planes = [r for r in roots if r.endswith("/data_plane.py")]
    assert len(planes) >= 8, planes
    for rel in planes:
        assert "forest_runner.py" in roots[rel], "the edge must name the file that carries it"
    unclocked = set(C.census()["unclocked"])
    assert not (set(planes) & unclocked), "a data plane the Africa/Korea forests run every hour"


def test_the_systemd_units_the_vps_manifest_declares_own_their_scripts() -> None:
    specs = C.systemd_manifest_specs()
    assert len(specs) >= 40, "ops/crontab.manifest declares its units beside its cron lines"
    owned = {p for s in specs for p in s.code_paths}
    assert "scripts/deep_mine_x.py" in owned, "quant-x-deepmine.timer runs it three times a day"
    for s in specs:
        assert s.schedule.startswith("quant-") or s.schedule.endswith((".timer", ".service"))


def test_the_unclocked_ratchet_holds_and_names_what_is_left() -> None:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "cr_check", ROOT / "scripts" / "check_component_registry.py")
    assert spec and spec.loader
    mod: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    unclocked = C.census()["unclocked"]
    assert len(unclocked) <= mod.MAX_UNCLOCKED, f"the ratchet may only fall: {unclocked}"
