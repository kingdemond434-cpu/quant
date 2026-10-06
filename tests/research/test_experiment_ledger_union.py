"""Every look is a trial: LLM ideas, committee falsifier looks and method-trial evaluations."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.research import experiment_ledger as L


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "desk"
    (d / "data" / "intelligence").mkdir(parents=True)
    monkeypatch.setattr(L, "DESK", d)
    return d


def _donate(desk: Path, seat: str, name: str, doc: object) -> None:
    p = desk / "data" / "intelligence" / seat
    p.mkdir(parents=True, exist_ok=True)
    (p / f"discoveries_{name}.json").write_text(json.dumps(doc))


def test_each_llm_idea_is_charged_once_even_when_re_donated(desk: Path) -> None:
    base, _ = L._proposer_counts()
    ideas = [{"url": "kimi://a", "family": "carry"}, {"url": "kimi://b"}]
    _donate(desk, "kimi", "1", {"discoveries": ideas})
    _donate(desk, "kimi", "2", {"discoveries": [ideas[0]]})          # the same idea again
    total, fam = L._proposer_counts()
    assert total == base + 2
    assert fam["carry"] == 1 and fam["llm_idea"] == 1


def test_a_non_llm_seat_without_tests_run_is_not_charged_per_row(desk: Path) -> None:
    base, _ = L._proposer_counts()
    _donate(desk, "broker_swaps", "1", {"discoveries": [{"url": "x"}] * 5})
    assert L._proposer_counts()[0] == base


def test_committee_looks_are_charged_once_from_the_union_and_never_from_their_files(
        desk: Path) -> None:
    base, _ = L._proposer_counts()
    union = desk / L.COMMITTEE_UNION
    union.parent.mkdir(parents=True)
    union.write_text("n1|cost_surface\nn1|truncation\nn1|cost_surface\n")
    _donate(desk, "committee_ensembles", "1", {"tests_run": 2, "discoveries": []})
    total, fam = L._proposer_counts()
    assert total == base + 2 and fam["committee_falsifier"] == 2


def test_the_method_trials_evaluations_are_charged(desk: Path) -> None:
    base, _ = L._proposer_counts()
    (desk / "data" / "coevolution_h2h.jsonl").write_text(
        json.dumps({"trials": 25}) + "\n" + json.dumps({"trials": 11}) + "\n")
    total, fam = L._proposer_counts()
    assert total == base + 36 and fam["model_pairing"] >= 36
