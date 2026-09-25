"""THE COVERAGE GRID ONLY EVER GOES UP, and the fence must be the thing that proves it.

A ratchet is only worth its line count if a regression FAILS and a re-seal cannot quietly lower
the mark. These bars are on the fence's pure core, so they need no parquet directory and no
terminal: `measure()` reads a directory, `evaluate()` compares two dicts, and every assertion
below is about the second.

The failure modes under test are the ones this repo has already paid for once, recorded in
`scripts/check_mt5_coverage_floor.py`: a missing mark file read as an empty dict (so every run
compares against zero and passes forever), and a regression writing itself in as the new mark on
the very run that reported it.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
_SPEC = importlib.util.spec_from_file_location(
    "check_bar_coverage_ratchet", ROOT / "scripts" / "check_bar_coverage_ratchet.py")
assert _SPEC and _SPEC.loader
F = importlib.util.module_from_spec(_SPEC)
sys.modules["check_bar_coverage_ratchet"] = F
_SPEC.loader.exec_module(F)

HOST = "TESTBOX"
LADDER = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]


def _now(by_tf: dict[str, int], n_instruments: int = 10, full: int = 10) -> dict[str, Any]:
    return {"at": "2026-09-24T00:00:00+00:00", "host": HOST, "ladder": LADDER,
            "n_instruments": n_instruments, "by_timeframe": dict(by_tf),
            "n_full_ladder": full, "n_cells_held": sum(by_tf.values()),
            "n_cells_possible": n_instruments * len(LADDER),
            "n_cells_excused": 0, "cells_excused": [],
            "n_cells_unexplained": 0, "cells_unexplained": []}


def _marks(by_tf: dict[str, int], n_instruments: int = 10, full: int = 10) -> dict[str, Any]:
    return {"tolerance": 0.02, "hosts": {HOST: {
        "sealed_at": "2026-09-01T00:00:00+00:00", "measured_at": "2026-09-01T00:00:00+00:00",
        "n_instruments": n_instruments, "by_timeframe": dict(by_tf), "n_full_ladder": full}}}


FULL = dict.fromkeys(LADDER, 248)


def test_a_first_measurement_seals_and_is_neither_a_pass_nor_a_fail() -> None:
    got = F.evaluate(_now(FULL, 248, 248), {"hosts": {}})
    assert got["verdict"] == "SEALED"
    assert not got["failures"]
    assert got["marks"]["hosts"][HOST]["by_timeframe"]["M1"] == 248
    assert "first" in got["why"]


def test_a_fall_past_tolerance_fails_by_name_and_the_mark_holds() -> None:
    """The regression this fence exists for: M1 collapses from 248 charts to four."""
    fell = {**FULL, "M1": 4}
    got = F.evaluate(_now(fell, 248, 4), _marks(FULL, 248, 248))
    assert got["verdict"] == "FAIL"
    assert any("tf:M1" in f for f in got["failures"]), got["failures"]
    assert got["marks"]["hosts"][HOST]["by_timeframe"]["M1"] == 248, (
        "a regression must never write itself in as the new mark")


def test_a_rise_raises_the_mark_and_keeps_the_seal_date() -> None:
    got = F.evaluate(_now({**FULL, "M1": 248}, 248, 248), _marks({**FULL, "M1": 236}, 248, 233))
    assert got["verdict"] == "OK", got["failures"]
    assert got["marks"]["hosts"][HOST]["by_timeframe"]["M1"] == 248
    assert got["marks"]["hosts"][HOST]["n_full_ladder"] == 248
    assert got["marks"]["hosts"][HOST]["sealed_at"] == "2026-09-01T00:00:00+00:00", (
        "the seal date is when the ratchet was armed; a raise does not move it")
    assert any("tf:M1" in r for r in got["raised"])


def test_a_fall_inside_tolerance_is_not_a_regression() -> None:
    """A floor that fires on one lost file out of 248 gets deleted, which is worse than none."""
    got = F.evaluate(_now({**FULL, "H4": 245}, 248, 245), _marks(FULL, 248, 248))
    assert got["verdict"] == "OK", got["failures"]
    assert got["marks"]["hosts"][HOST]["by_timeframe"]["H4"] == 248


def test_retiring_instruments_cannot_pass_as_coverage() -> None:
    """The denominator ratchets too: dropping rows raises a percentage and fetches nothing."""
    thin = dict.fromkeys(LADDER, 200)
    got = F.evaluate(_now(thin, 200, 200), _marks(FULL, 248, 248))
    assert got["verdict"] == "FAIL"
    assert any("instruments" in f for f in got["failures"]), got["failures"]


def test_each_host_keeps_its_own_mark() -> None:
    """The build box has no terminal and holds four M15 charts; it must not seal the desk's."""
    marks = _marks(FULL, 248, 248)
    build = {**_now(dict.fromkeys(LADDER, 4), 4, 4), "host": "BUILDBOX"}
    got = F.evaluate(build, marks)
    assert got["verdict"] == "SEALED"
    assert got["marks"]["hosts"][HOST]["by_timeframe"]["M1"] == 248, (
        "one host's first measurement must never touch another host's mark")
    assert got["marks"]["hosts"]["BUILDBOX"]["by_timeframe"]["M1"] == 4


def test_a_timeframe_the_run_does_not_measure_keeps_its_mark() -> None:
    got = F.evaluate(_now({tf: 248 for tf in LADDER if tf != "D1"}, 248, 248),
                     _marks(FULL, 248, 248))
    assert got["marks"]["hosts"][HOST]["by_timeframe"]["D1"] == 248


def test_a_missing_mark_file_is_a_failure_and_never_an_empty_dict(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Reading `{}` is how a ratchet compares every run against zero and reports green."""
    monkeypatch.setattr(F, "HIGH_WATER", tmp_path / "absent.json")
    with pytest.raises(SystemExit) as excinfo:
        F.read_marks()
    assert "ratchet with no memory" in str(excinfo.value)


def test_measure_counts_the_grid_and_splits_excused_from_unexplained(tmp_path: Path) -> None:
    uni = tmp_path / "universe"
    uni.mkdir()
    for tf in LADDER:
        (uni / f"EURUSD_{tf}.parquet").write_bytes(b"x")
    for tf in LADDER:
        if tf not in ("M1", "M5"):
            (uni / f"SUGAR_{tf}.parquet").write_bytes(b"x")
    verdicts = tmp_path / "verdicts.json"
    verdicts.write_text(json.dumps({"cells": {
        "SUGAR_M1": {"verdict": "BROKER_SERVES_NOTHING", "why": "the venue served nothing"}}}),
        "utf-8")
    got = F.measure(universe=uni, verdicts=verdicts)
    assert got["n_instruments"] == 2
    assert got["by_timeframe"]["H1"] == 2
    assert got["by_timeframe"]["M1"] == 1
    assert got["n_full_ladder"] == 1
    assert got["n_cells_excused"] == 1 and "SUGAR_M1" in got["cells_excused"][0]
    assert got["n_cells_unexplained"] == 1, (
        "a cell the venue was never asked about is a hole, not an excused one")
    assert "SUGAR_M5:NO_VERDICT" in got["cells_unexplained"]


def test_the_fence_is_rostered_in_the_battery() -> None:
    """UNWIRED IS A DEFECT (III.16): a ratchet nothing runs is a claim the desk cannot cash."""
    from research import batteries
    paths = {e.path for e in batteries.FENCES}
    assert "scripts/check_bar_coverage_ratchet.py" in paths
    organs = {e.path for e in batteries.ORGANS}
    assert "desks/mt5/scripts/fill_bar_gaps.py" in organs, (
        "the fence reports a gap and something must be able to close it on a clock")
