"""THE PLACEBO AUDIT (item 16, 2026-09-29): positive controls must pass, planted defects must fail,
through the real judge -- and the audit must itself be able to fail.

The adversary suite's canaries are all negatives, so a welded-shut gauntlet scores them perfectly.
These tests drive a gate that admits everything (blind) and one that refuses everything (welded)
through the audit and require each to be named, then run the audit against the desk's real
gauntlet and lookahead sentinel and require recall 1.0 with every positive admitted.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK / "scripts"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import adversary  # noqa: E402
import placebo_audit as pa  # noqa: E402


class _Fixed:
    """A stand-in gauntlet with one answer for every cell."""

    def __init__(self, passed: bool) -> None:
        self.passed = passed

    def run_gauntlet(self, cells: list[dict[str, Any]], _hunt: str, _meta: Any) -> dict[str, Any]:
        return {"n_cells": len(cells), "verdicts": [
            {"family": c["family"], "passed": self.passed, "stages": {}} for c in cells]}


def _gauntlet_plants() -> list[str]:
    return [p.name for p in pa.PLANTS if p.judge == pa.GAUNTLET]


def test_a_gate_that_admits_everything_is_blind_and_named() -> None:
    rows = pa.judge_gauntlet(_Fixed(True), adversary)
    rows.pop("_docket")
    rows.update(pa.judge_sentinel())
    s = pa.score(rows)
    assert s["status"] == "GATE_BLIND"
    assert set(s["blind_to"]) == {n for n in _gauntlet_plants() if n != "planted_edge"}
    assert s["audit_recall"] < 1.0


def test_a_gate_that_refuses_everything_is_welded_even_with_perfect_recall() -> None:
    """THE CASE THE CANARY CONSTANT CANNOT SEE: every negative caught, the positive refused."""
    rows = pa.judge_gauntlet(_Fixed(False), adversary)
    rows.pop("_docket")
    rows.update(pa.judge_sentinel())
    s = pa.score(rows)
    assert s["audit_recall"] == 1.0
    assert s["status"] == "GATE_WELDED" and s["welded_on"] == ["planted_edge"]


def test_an_unjudged_plant_counts_against_recall_and_is_not_blindness() -> None:
    rows = {p.name: {"judged": False, "passed": None, "why": "import"} for p in pa.PLANTS}
    s = pa.score(rows)
    assert s["status"] == "UNMEASURED" and s["audit_recall"] == 0.0 and not s["blind_to"]


def test_each_negative_differs_from_the_positive_in_its_one_respect() -> None:
    sig, fwd, off, mult = pa.gauntlet_series("planted_edge")
    assert off == 0 and mult == 1.0
    assert pa.gauntlet_series("sign_flip")[0] == [-s for s in sig]
    assert pa.gauntlet_series("spread_perturbation")[:2] == (sig, fwd)
    assert pa.gauntlet_series("spread_perturbation")[3] == pa.SPREAD_SHOCK
    assert pa.gauntlet_series("info_delay")[0][1:] == sig[:-1]
    assert sorted(pa.gauntlet_series("scrambled_timestamps")[0]) == sorted(sig)
    assert [abs(x) for x in pa.gauntlet_series("label_shuffle")[0]] == [abs(x) for x in sig]
    assert pa.gauntlet_series("harness_lookahead")[2] == 1
    assert pa.gauntlet_series("planted_edge") == pa.gauntlet_series("planted_edge")


@pytest.fixture(scope="module")
def real() -> dict[str, Any]:
    return pa.run()


def test_the_real_judges_admit_the_positives_and_catch_every_planted_defect(real) -> None:
    assert real["gate_source"] == pa.GAUNTLET, real["gate_source"]
    assert not real["unjudged"], [t for t in real["table"] if not t["judged"]]
    assert real["positive_pass_rate"] == 1.0, real["welded_on"]
    assert real["audit_recall"] == 1.0, real["blind_to"]
    assert real["status"] == "OK"
    assert real["by_judge"][pa.SENTINEL]["recall"] == 1.0


def test_main_writes_the_report_and_a_history_row(tmp_path: Path) -> None:
    rep, hist = tmp_path / "r.json", tmp_path / "h.jsonl"
    rc = pa.main(["--report", str(rep), "--history", str(hist)])
    assert rc == 0 and rep.exists() and len(hist.read_text("utf-8").splitlines()) == 1
