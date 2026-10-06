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


def test_a_donated_cell_the_judge_saw_is_charged_once_not_twice(desk: Path) -> None:
    by_src: dict[tuple[str, str], int] = {}
    _donate(desk, "anomalies", "1", {"tests_run": 40,
                                     "discoveries": [{"family": "carry"}] * 3})
    L._proposer_counts(by_src)
    assert by_src == {("anomalies", "carry"): 40}
    judged = {("anomalies", "carry"): 3,             # donated, then judged: already screened
              ("", "carry"): 2,                      # judged with no BORN row: nobody screened it
              ("broker_swaps", "carry"): 4,          # a source that charged no tests_run
              ("", "mass_screen_cond"): 7}
    over = L.judged_screened_overlap(by_src, {"mass_screen_cond": 5}, judged)
    assert over == {"carry": 3, "mass_screen_cond": 5}   # never more than either side charged


def test_lifetime_subtracts_the_overlap_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(L, "_graph_counts", lambda: (10, {"carry": 10}))

    def prop(by_source=None):
        if by_source is not None:
            by_source[("anomalies", "carry")] = 6
        return 6, {"carry": 6}
    monkeypatch.setattr(L, "_proposer_counts", prop)
    monkeypatch.setattr(L, "_mass_screen_counts", lambda: (0, {}))
    monkeypatch.setattr(L, "_claim_selection_counts", lambda: (0, {}))
    monkeypatch.setattr(L, "_graph_judged_by_source",
                        lambda: {("anomalies", "carry"): 4, ("", "carry"): 6})
    doc = L.lifetime(write=False)
    assert doc["judged_already_screened"] == 4
    assert doc["lifetime_trials"] == 10 + 6 - 4 == doc["by_family"]["carry"]
