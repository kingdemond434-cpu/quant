"""A research comparison must read genuine outcomes and preserve leading-rung caveats."""
import json
import math

import pytest

from libs.research_os import brain_ab as ab
from libs.research_os import store


@pytest.fixture
def memory(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB", tmp_path / "memory.sqlite")
    return store


def test_actual_store_outcomes_preserve_assignment_and_stage(memory):
    memory.record_hypothesis(hypothesis_id="terminal", brain_version="mutation")
    memory.record_hypothesis(hypothesis_id="cost", brain_version="control")
    memory.record_hypothesis(hypothesis_id="unassigned")
    memory.record_hypothesis(hypothesis_id="foreign", brain_version="unknown")
    memory.record_measurement(hypothesis_id="terminal", status="DIRECT", adapter="fixture")
    memory.record_experiment(hypothesis_id="terminal", stage="FORWARD_SURVIVED", passed=True)
    memory.record_experiment(hypothesis_id="cost", exp_r_net=0.1)
    result = ab._outcomes_from_store()
    assert sum(map(len, result["forward_survived"].values())) == 3
    assert sum(map(sum, result["forward_survived"].values())) == 1
    assert sum(map(sum, result["cost_survived"].values())) == 2
    assert sum(map(sum, result["attributable_measured"].values())) == 1
    # The read context has released its owned connection, so a subsequent write succeeds.
    memory.record_hypothesis(hypothesis_id="after-report", brain_version="control")
    assert sum(map(len, ab._outcomes_from_store()["forward_survived"].values())) == 4


@pytest.mark.parametrize("success", [0.0, 1.0])
def test_zero_variance_bernoulli_arm_keeps_finite_uncertainty(success):
    lower, mean, upper = ab._interval([success] * 100)
    assert math.isfinite(lower) and math.isfinite(upper)
    assert lower < mean < upper and mean == success
    assert ab._interval([]) == (0.0, 0.0, 0.0)


def test_assignment_stable_native_ids_and_explicit_arm_set():
    assert ab.assign_arm("") == "control"
    assert ab.assign_arm("検証") == ab.assign_arm("検証")
    assert ab.assign_arm("anything", ("single",)) == "single"
    assert {ab.assign_arm(str(i)) for i in range(100)} == set(ab.ARMS)


def test_underpowered_is_never_a_null_result():
    result = ab.compare({"control": [0.0] * 3, "mutation": [1.0] * 40}, "cost_survived", "cost")
    assert result["verdict"] == "UNDERPOWERED"
    assert "Not a null result" in result["detail"]
    assert not result["terminal"] and "LEADING" in result["caveat"]


def test_actual_sequences_win_only_with_nonoverlap():
    result = ab.compare({"control": [0.0] * 1000, "mutation": [1.0] * 1000},
                        "forward_survived", "terminal")
    assert result["verdict"] == "WINNER: mutation"
    assert result["terminal"] and result["caveat"] == ""
    overlap = ab.compare({"control": [0.0, 1.0] * 20, "mutation": [0.0, 1.0] * 20},
                         "forward_enrolled", "clock")
    assert overlap["verdict"] == "INCONCLUSIVE"


def test_ladder_selects_supported_rung_and_main_delivers_same_evidence(memory, tmp_path,
                                                                       monkeypatch, capsys):
    for arm in ab.ARMS:
        for i in range(20):
            memory.record_hypothesis(hypothesis_id=f"{arm}-{i}", brain_version=arm)
    report = ab.report()
    assert report["headline"]["metric"] == "forward_survived"
    assert len(report["ladder"]) == 4
    assert report["headline"]["verdict"] == "INCONCLUSIVE"
    monkeypatch.chdir(tmp_path)
    assert ab.main() == 0
    delivered = json.loads((tmp_path / "data/brain_ab.json").read_text(encoding="utf-8"))
    assert delivered == report
    assert "RESEARCH BRAIN A/B" in capsys.readouterr().out


def test_empty_memory_names_underpowered_leading_rung(memory, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    report = ab.report()
    assert report["headline"]["verdict"] == "UNDERPOWERED"
    assert report["headline"]["metric"] == "attributable_measured"
    assert ab.main() == 0
    assert "CAVEAT" in capsys.readouterr().out
