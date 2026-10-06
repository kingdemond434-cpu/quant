"""A judged cell its proposer or the mass screen already charged is charged once."""
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


def test_counts_with_no_overlap_are_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(L, "_graph_counts", lambda: (10, {"carry": 7, "trend": 3}))

    def prop(screened=None):
        if screened is not None:
            screened.update(ids={"x"}, by_family={"carry": 6})
        return 6, {"carry": 6}
    monkeypatch.setattr(L, "_proposer_counts", prop)
    monkeypatch.setattr(L, "_mass_screen_counts", lambda: (0, {}))
    monkeypatch.setattr(L, "_claim_selection_counts", lambda: (0, {}))
    monkeypatch.setattr(L, "_graph_judged", lambda: {"a": "carry", "t": "trend"})
    doc = L.lifetime(write=False)
    assert doc["judged_already_screened"] == 0 and doc["lifetime_trials"] == 16
    assert doc["by_family"] == {"carry": 13, "trend": 3}
