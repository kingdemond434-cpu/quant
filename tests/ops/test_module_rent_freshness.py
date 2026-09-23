"""Data freshness is a billed component (Tier-1 E10).

MODULE_RENT priced the tape (tick_tape, fill_corpus, broker_clock) and never its FRESHNESS, so
"the feed lagged six hours" carried a red flag and no log-wealth number. Pinned: the row exists
in the registry, the breach definition is check_job_manifest's own (STALE / MISSING / EMPTY, and
never FROZEN or IDLE), the with/without is clean days against breached days over realised R, and
it reads UNMEASURED with the shortfall until the breach history holds both kinds of day.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.ops import module_rent as mr

NAME = "data_source:freshness"


def _write(root: Path, rel: str, doc) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), "utf-8")


def _lines(root: Path, rel: str, rows: list[dict]) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", "utf-8")


def _module() -> mr.Module:
    for m in mr.MODULES:
        if m.name == NAME:
            return m
    raise AssertionError(f"{NAME} is not in the registry")


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    (tmp_path / "desks" / "mt5" / "reports").mkdir(parents=True)
    (tmp_path / "desks" / "mt5" / "data").mkdir(parents=True)
    return tmp_path


def _manifest(root: Path, statuses: dict[str, str]) -> None:
    _write(root, mr.JOB_MANIFEST,
           {"checked_at": "2026-09-08T12:00:00+00:00",
            "jobs": {rel: {"status": s} for rel, s in statuses.items()}})


def _ledger(root: Path, days: dict[str, float]) -> None:
    _lines(root, "desks/mt5/data/live_ledger.jsonl",
           [{"sleeve": "S", "close_time": f"{d}T10:00:00+00:00", "r_multiple": v}
            for d, v in days.items()])


# --------------------------------------------------------------------------- the registry row
def test_the_row_is_registered_as_a_data_source_billed_on_the_fences_own_breaches() -> None:
    m = _module()
    assert m.kind == "data_source" and m.kind in mr.KINDS
    assert m.ledger == mr.FRESHNESS_HISTORY and m.measure == "measure_freshness"
    assert "check_job_manifest" in m.where
    assert "E[log W with fresh data]" in m.rule
    assert mr.MEASURES["measure_freshness"] is mr.measure_freshness
    assert set(mr.BREACH_STATUSES) == {"STALE", "MISSING", "EMPTY"}
    assert not {"FROZEN", "IDLE"} & mr.BREACH_STATUSES


# --------------------------------------------------------------------------- UNMEASURED paths
def test_no_manifest_on_this_host_is_unmeasured_with_the_path(tree: Path) -> None:
    row = mr.measure(tree, modules=(_module(),))[NAME]
    assert row["verdict"] == mr.UNMEASURED and mr.JOB_MANIFEST in row["why"]
    assert row["watched"] == list(mr.FRESHNESS_ARTIFACTS) and row["breaching_now"] == []


def test_a_snapshot_without_a_history_is_unmeasured_and_still_reports_what_is_red(tree: Path):
    _manifest(tree, {"desks/mt5/reports/shadow/shadow_state.json": "STALE",
                     "web/desk_state.json": "OK",
                     "desks/mt5/data/decay_live.json": "STALE"})   # watched? no -- not counted
    row = mr.measure(tree, modules=(_module(),))[NAME]
    assert row["verdict"] == mr.UNMEASURED and row["rent"] is None
    assert row["breaching_now"] == ["desks/mt5/reports/shadow/shadow_state.json"]
    assert row["manifest_checked_at"] == "2026-09-08T12:00:00+00:00"
    assert "holds no readable day" in row["why"] and "1 of 4 artifact(s) breaching" in row["why"]


def test_frozen_and_idle_are_not_breaches(tree: Path) -> None:
    _manifest(tree, {"desks/mt5/reports/shadow/shadow_state.json": "FROZEN",
                     "desks/mt5/reports/shadow/scalp_shadow_state.json": "IDLE",
                     "web/desk_state.json": "MISSING"})
    row = mr.measure(tree, modules=(_module(),))[NAME]
    assert row["breaching_now"] == ["web/desk_state.json"]


def test_a_thin_side_is_unmeasured_with_both_counts(tree: Path) -> None:
    _manifest(tree, {"web/desk_state.json": "OK"})
    days = {f"2026-09-{d:02d}": 0.1 for d in range(1, 13)}
    _ledger(tree, days)
    _lines(tree, mr.FRESHNESS_HISTORY,
           [{"day": d, "breaches": []} for d in list(days)[:11]]
           + [{"day": list(days)[11], "breaches": ["web/desk_state.json"]}])
    row = mr.measure(tree, modules=(_module(),))[NAME]
    assert row["verdict"] == mr.UNMEASURED
    assert row["clean_days"] == 11 and row["breached_days"] == 1
    assert f"need {mr.MIN_N} of each" in row["why"]


# --------------------------------------------------------------------------- a real verdict
def test_growth_lost_on_breached_days_is_a_measured_earns(tree: Path) -> None:
    _manifest(tree, {"web/desk_state.json": "OK"})
    clean = {f"2026-09-{d:02d}": 0.30 + 0.001 * d for d in range(1, 13)}
    dirty = {f"2026-10-{d:02d}": -0.30 - 0.001 * d for d in range(1, 13)}
    _ledger(tree, {**clean, **dirty})
    _lines(tree, mr.FRESHNESS_HISTORY,
           [{"day": d, "breaches": []} for d in clean]
           + [{"day": d, "breaches": ["desks/mt5/reports/shadow/shadow_state.json"]}
              for d in dirty])
    row = mr.measure(tree, modules=(_module(),))[NAME]
    assert row["verdict"] == mr.EARNS
    assert row["unit"] == "log-wealth/day" and row["rent_logw_per_day"] == row["rent"]
    assert row["rent"] == pytest.approx(0.613, abs=1e-2)
    assert row["clean_days"] == 12 and row["breached_days"] == 12 and row["n"] == 24
    assert row["ci"][0] > 0 and row["t"] > mr.T_LINE
    assert row["window"] == "12 clean day(s) vs 12 breached day(s)"


def test_a_breach_on_an_unwatched_artifact_does_not_dirty_the_day(tree: Path) -> None:
    _manifest(tree, {"web/desk_state.json": "OK"})
    days = {f"2026-09-{d:02d}": 0.2 for d in range(1, 13)}
    _ledger(tree, days)
    _lines(tree, mr.FRESHNESS_HISTORY,
           [{"day": d, "breaches": ["data/authority_ratchet.json"]} for d in days])
    row = mr.measure(tree, modules=(_module(),))[NAME]
    assert row["clean_days"] == 12 and row["breached_days"] == 0


def test_the_last_word_about_a_day_stands_and_the_row_shape_is_accepted(tree: Path) -> None:
    flags, used = mr._breach_days([
        {"day": "2026-09-01", "breaches": []},
        {"day": "2026-09-01", "artifact": "web/desk_state.json", "status": "STALE"},
        {"day": "2026-09-02", "artifact": "web/desk_state.json", "status": "FROZEN"},
        {"day": "2026-09-03", "artifact": "data/unwatched.json", "status": "STALE"},
        {"at": "2026-09-04T09:00:00+00:00", "breaches": ["web/desk_state.json"]},
        {"nothing": "usable"},
    ])
    assert flags == {"2026-09-01": True, "2026-09-02": False, "2026-09-03": False,
                     "2026-09-04": True}
    assert used == 5
