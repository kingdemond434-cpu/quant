"""ResearchBrain: a frozen run cannot be rewritten, correlated survivors count once, and a brain
is only IMPROVED against a rival that produced fewer independent survivors per trial-hour."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.research import research_brain as rb


@pytest.fixture(autouse=True)
def _arena(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    arena = tmp_path / "brains"
    monkeypatch.setattr(rb, "ARENA", arena)
    return arena


def test_freeze_hashes_content_and_writes_once(_arena: Path) -> None:
    cands = [{"cell": "a", "sym": "XAUUSD"}, {"cell": "b", "sym": "EURUSD"}]
    run = rb.freeze("baseline", "2026-09-01T00:00", cands, 30, 7200.0, {"k": 1})
    assert run.content_hash == run.compute_hash() and len(run.content_hash) == 20
    path = _arena / "baseline_20260901T0000.json"
    on_disk = json.loads(path.read_text("utf-8"))
    assert on_disk["content_hash"] == run.content_hash and on_disk["effective_trials"] == 30
    # same content again is idempotent; the hash ignores dict key order and compute time
    again = rb.freeze("baseline", "2026-09-01T00:00", [{"sym": "XAUUSD", "cell": "a"},
                                                       {"cell": "b", "sym": "EURUSD"}], 30, 1.0)
    assert again.content_hash == run.content_hash


def test_a_frozen_run_may_not_be_rewritten() -> None:
    rb.freeze("b", "2026-09-01", [{"cell": "a"}], 10, 60.0)
    with pytest.raises(FileExistsError, match="pre-registration"):
        rb.freeze("b", "2026-09-01", [{"cell": "a"}, {"cell": "late"}], 10, 60.0)
    with pytest.raises(FileExistsError):
        rb.freeze("b", "2026-09-01", [{"cell": "a"}], 11, 60.0)     # trials are in the hash


def test_independent_count_falls_back_to_mechanism_symbol_pairs() -> None:
    assert rb.independent_count([]) == 0
    surv = [{"mechanism": "breakout", "symbol": "XAUUSD"},
            {"mechanism": "breakout", "symbol": "XAUUSD"},
            {"mechanism": "carry", "symbol": "XAUUSD"}, {}]
    assert rb.independent_count(surv) == 3            # two duplicates collapse; {} is ("?","?")


def test_independent_count_collapses_correlated_survivors_either_key_order() -> None:
    surv = [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"cell": "d"}]
    corr = {("a", "b"): 0.9, ("c", "a"): -0.6, ("d", "b"): 0.1}
    # b and c correlate with the kept a (|r| >= 0.5); d is independent of a
    assert rb.independent_count(surv, corr) == 2
    assert rb.independent_count(surv, {("a", "b"): 0.49}) == 4


def test_score_divides_by_trials_and_compute_hours() -> None:
    run = {"brain": "x", "cutoff": "c", "content_hash": "h", "candidates": [{}, {}],
           "effective_trials": 4, "compute_seconds": 7200}
    s = rb.score(run, [{"mechanism": "m1"}, {"mechanism": "m2"}], 0.01)
    assert s["survivors_independent"] == 2 and s["survivors_raw"] == 2
    assert s["candidates_frozen"] == 2 and s["compute_hours"] == 2.0
    assert s["score"] == pytest.approx(2 * 0.01 / (4 * 2.0))
    # missing trials/compute are floored, never divided by zero
    z = rb.score({"effective_trials": 0, "compute_seconds": 0}, [], 0.5)
    assert z["effective_trials"] == 1 and z["score"] == 0.0


def _scored(name: str, score: float, ind: int) -> dict:
    return {"brain": name, "score": score, "survivors_independent": ind}


def test_compare_verdicts() -> None:
    assert rb.compare([])["verdict"] == "UNMEASURED"
    solo = rb.compare([_scored("a", 1.0, 3)])
    assert solo["verdict"] == "UNMEASURED" and "one brain" in solo["why"]
    won = rb.compare([_scored("old", 0.2, 1), _scored("new", 0.5, 2)])
    assert won["verdict"] == "IMPROVED" and won["winner"] == "new"
    assert [r["brain"] for r in won["ranked"]] == ["new", "old"]
    tied = rb.compare([_scored("a", 0.3, 1), _scored("b", 0.3, 1)])
    assert tied["verdict"] == "TIED"
    nothing = rb.compare([_scored("a", 0.0, 0), _scored("b", -1.0, 0)])
    assert nothing["verdict"] == "UNMEASURED" and "absence is not a win" in nothing["why"]


def test_arena_lists_runs_and_skips_unreadable_files(_arena: Path) -> None:
    assert rb.arena()["n_runs"] == 0
    rb.freeze("a", "2026-09-01", [{"cell": 1}], 5, 10.0)
    rb.freeze("b", "2026-09-02", [{"cell": 1}, {"cell": 2}], 6, 10.0)
    (_arena / "zz_broken.json").write_text("{nope", "utf-8")
    doc = rb.arena()
    assert doc["n_runs"] == 2
    assert [(r["brain"], r["candidates"], r["effective_trials"]) for r in doc["runs"]] == [
        ("a", 1, 5), ("b", 2, 6)]
