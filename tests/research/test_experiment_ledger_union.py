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


def test_three_ideas_citing_one_url_are_three_ideas(desk: Path) -> None:
    base, _ = L._proposer_counts()
    ideas = [{"url": "https://x/1", "title": t, "family": "carry"} for t in ("a", "b", "c")]
    _donate(desk, "deepseek", "1", {"discoveries": ideas})
    # A re-donation that only rewrites its stamps is the same idea.
    _donate(desk, "deepseek", "2", {"discoveries": [ideas[0] | {"ingested_time": "later"}]})
    assert L._proposer_counts()[0] == base + 3


def test_committee_files_count_until_the_union_exists(desk: Path) -> None:
    base, _ = L._proposer_counts()
    _donate(desk, "committee_ensembles", "1", {"tests_run": 4, "discoveries": []})
    assert L._proposer_counts()[0] == base + 4            # no union yet: the files' own charge
    union = desk / L.COMMITTEE_UNION
    union.parent.mkdir(parents=True)
    union.write_text("n1|a\nn2|a\nn3|a\n")
    assert L._proposer_counts()[0] == base + 3            # union on: charged from it, once


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


def test_a_donated_cell_the_judge_saw_is_charged_once_by_spec_identity(desk: Path) -> None:
    from libs.research.hypothesis_graph import node_id
    spec = {"symbol": "eurusd", "family": "carry", "params": {"lb": 20}}
    other = {"symbol": "GBPUSD", "family": "carry", "params": {"lb": 20}}
    _donate(desk, "anomalies", "1", {"tests_run": 40, "discoveries": [spec, other]})
    _donate(desk, "plumbing", "1", {"tests_run": 5, "discoveries": [spec]})   # same spec, 2 seats
    screened: dict = {}
    L._proposer_counts(screened)
    same = node_id("EURUSD", "carry", {"lb": 20})             # judged under its own spelling
    judged = {same: "carry",
              node_id("EURUSD", "carry", {"lb": 20, "chart": "M15"}): "carry",   # an expansion
              "unscreened": "carry", "m1": "mass_screen_cond", "m2": "mass_screen_cond"}
    over = L.judged_screened_overlap(screened, {"mass_screen_cond": 1}, judged)
    # One identity, once, though two seats donated it; the expansion is a new trial; the mass
    # screen gives back no more than it charged.
    assert over == {"carry": 1, "mass_screen_cond": 1}


def test_the_overlap_never_exceeds_what_the_proposers_charged() -> None:
    screened = {"ids": {"a", "b", "c"}, "by_family": {"carry": 2}}
    assert L.judged_screened_overlap(screened, {}, {"a": "carry", "b": "carry",
                                                    "c": "carry"}) == {"carry": 2}


def test_lifetime_subtracts_the_overlap_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(L, "_graph_counts", lambda: (10, {"carry": 10}))

    def prop(screened=None):
        if screened is not None:
            screened.update(ids={"a", "b", "c", "d"}, by_family={"carry": 6})
        return 6, {"carry": 6}
    monkeypatch.setattr(L, "_proposer_counts", prop)
    monkeypatch.setattr(L, "_mass_screen_counts", lambda: (0, {}))
    monkeypatch.setattr(L, "_claim_selection_counts", lambda: (0, {}))
    monkeypatch.setattr(L, "_graph_judged",
                        lambda: {"a": "carry", "b": "carry", "c": "carry", "d": "carry",
                                 "z": "carry"})
    doc = L.lifetime(write=False)
    assert doc["judged_already_screened"] == 4
    assert doc["lifetime_trials"] == 10 + 6 - 4 == doc["by_family"]["carry"]
