"""A full `tier_s` pass killed at its leg cap resumes where it stopped (2026-11-05).

Every full run on the box was killed at 1,500 s in the same place, so TIER_S.json was never
written and the organs at the back of the fixed order had not run since 11-02.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

import tier_s as ts  # noqa: E402


def _noop() -> dict:
    return {}


PLAN = [(n, _noop) for n in ("truth_kernel", "firewall", "immune", "red_queen",
                             "test_invention", "online_fdr", "topology", "qd", "genomes",
                             "grammar", "theory")]


@pytest.fixture()
def tmp_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(ts, "STATE", tmp_path / "state")
    monkeypatch.setattr(ts, "SUMMARY", tmp_path / "TIER_S.json")
    return tmp_path


def test_the_door_inputs_stay_first_in_fixed_order(tmp_state: Path) -> None:
    ts._save_state(ts.ORGAN_STARTS, {"truth_kernel": "2026-11-05T12:00:00+00:00"})
    names = [n for n, _ in ts._order_full_pass(PLAN)]
    assert names[:6] == list(ts.FULL_PASS_HEAD)


def test_never_started_organs_go_first_and_ties_keep_authored_order(tmp_state: Path) -> None:
    names = [n for n, _ in ts._order_full_pass(PLAN)]
    assert names[6:] == ["topology", "qd", "genomes", "grammar", "theory"]
    ts._save_state(ts.ORGAN_STARTS, {"topology": "2026-11-05T10:00:00+00:00",
                                     "qd": "2026-11-05T10:05:00+00:00"})
    names = [n for n, _ in ts._order_full_pass(PLAN)]
    assert names[6:] == ["genomes", "grammar", "theory", "topology", "qd"]


def test_an_organ_killed_mid_run_goes_to_the_back(tmp_state: Path) -> None:
    ts._save_state(ts.ORGAN_STARTS, {n: "2026-11-02T00:00:00+00:00"
                                     for n in ("topology", "qd", "grammar", "theory")})
    ts._mark_started("genomes")         # started, then killed: it never finished
    names = [n for n, _ in ts._order_full_pass(PLAN)]
    assert names[-1] == "genomes"


def test_the_partial_summary_is_marked_incomplete(tmp_state: Path) -> None:
    ts._write_partial_summary({"firewall": {}}, {"firewall": 1.5}, {}, "firewall")
    doc = ts._read(ts.SUMMARY)
    assert doc["complete"] is False and doc["partial_through"] == "firewall"
    assert doc["total_seconds"] == 1.5
