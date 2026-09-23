"""Research priors: posteriors that move with outcomes, unseen keys that are ignorance rather
than failure, the Dirichlet over failure classes, and the allocation draws that consume them."""
from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from libs.research import research_priors as P


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "research_priors"
    monkeypatch.setattr(P, "STATE_DIR", d)
    monkeypatch.setattr(P, "BETA_PATH", d / "beta.json")
    monkeypatch.setattr(P, "DIRICHLET_PATH", d / "dirichlet.json")
    return d


def test_an_unseen_key_is_ignorance_and_never_a_measured_failure(store: Path) -> None:
    p = P.prior_for("family", "never_tried_family")
    assert p.status == "PRIOR" and p.n == 0
    assert p.mean == pytest.approx(0.5)
    lo, hi = p.interval()
    assert lo < 0.5 < hi
    with pytest.raises(ValueError, match="unknown dimension"):
        P.prior_for("not_a_dimension", "x")


def test_priors_move_with_outcomes_in_the_right_direction(store: Path) -> None:
    before = P.posterior_mean("family", "carry_unwind")
    for _ in range(8):
        P.record_outcome("SURVIVED", family="carry_unwind", operator="deep_forest",
                         source="src_1", model="ols", representation="positioning")
    up = P.prior_for("family", "carry_unwind")
    assert up.mean > before and up.status == "POSTERIOR" and up.n == 8
    for _ in range(8):
        P.record_outcome("REJECTED", family="gap_decay", rejection_reason="cost_killed spread")
    down = P.prior_for("family", "gap_decay")
    assert down.mean < 0.5 < up.mean
    # every dimension the outcome was evidence for moved, including the model x representation PAIR
    assert P.posterior_mean("model_repr", "ols|positioning") > 0.5
    assert P.posterior_mean("operator", "deep_forest") > 0.5
    assert P.posterior_mean("source", "src_1") > 0.5


def test_an_unmeasured_experiment_is_not_charged_as_a_failure(store: Path) -> None:
    P.record_outcome("UNMEASURED", family="unknown_family")
    p = P.prior_for("family", "unknown_family")
    assert p.mean == pytest.approx(0.5)                     # no Beta failure charged
    assert P.outcome_posterior("family", "unknown_family")["unmeasured"] > 1.0 / len(
        P.OUTCOME_CLASSES)                                   # but the Dirichlet saw it


def test_the_failure_class_is_kept_because_it_sends_the_next_allocation_elsewhere() -> None:
    assert P.classify("REJECTED", rejection_reason="spread cost kill") == "rejected_cost"
    assert P.classify("REJECTED", failure_class="unstable") == "rejected_unstable"
    assert P.classify("REJECTED", rejection_reason="no edge") == "rejected_no_edge"
    assert P.classify("SURVIVED") == "survived"
    assert P.classify("BLOCKED") == "blocked"
    assert P.classify("") == "unmeasured"


def test_the_posterior_is_persisted_and_reloads_identically(store: Path) -> None:
    P.record_outcome("SURVIVED", family="carry_unwind", experiment_id="exp_1")
    assert (store / "beta.json").exists() and (store / "dirichlet.json").exists()
    doc = json.loads((store / "beta.json").read_text(encoding="utf-8"))
    assert doc["dimensions"]["family"]["carry_unwind"]["last_experiment"] == "exp_1"
    assert P.prior_for("family", "carry_unwind").a == pytest.approx(2.0)


def test_rank_keeps_every_key_and_pays_for_uncertainty(store: Path) -> None:
    """A family with 1/2 outranks one measured at 4/200: nothing is dropped, only ordered."""
    for verdict in ("SURVIVED", "REJECTED"):
        P.record_outcome(verdict, family="young")
    for i in range(200):
        P.record_outcome("SURVIVED" if i < 4 else "REJECTED", family="exhausted")
    rows = P.rank("family", ["young", "exhausted", "unseen"])
    assert {r["key"] for r in rows} == {"young", "exhausted", "unseen"}
    order = [r["key"] for r in rows]
    assert order.index("young") < order.index("exhausted")
    assert order.index("unseen") < order.index("exhausted")


def test_thompson_draws_from_the_posterior_so_an_unseen_key_still_competes(store: Path) -> None:
    for _ in range(50):
        P.record_outcome("REJECTED", family="dead")
    rng = random.Random(7)
    draws = [P.thompson("family", ["dead", "unseen"], rng=rng) for _ in range(200)]
    wins = sum(1 for d in draws if d["unseen"] > d["dead"])
    assert wins > 150                      # exploration is not vetoed by a measured failure


def test_old_evidence_decays_toward_the_prior_without_rewriting_the_record(store: Path) -> None:
    for _ in range(20):
        P.record_outcome("SURVIVED", family="ancient")
    fresh = P.prior_for("family", "ancient")
    later = P.prior_for("family", "ancient",
                        as_of=datetime.now(tz=UTC) + timedelta(days=720))
    assert later.mean < fresh.mean
    assert later.n == fresh.n              # the raw record is untouched and auditable


def test_snapshot_is_the_report_the_spine_publishes(store: Path) -> None:
    P.record_outcome("SURVIVED", family="carry_unwind", operator="deep_forest")
    snap = P.snapshot()
    assert set(snap["dimensions"]) == set(P.DIMENSIONS)
    fam = snap["dimensions"]["family"]
    assert fam["n_keys"] == 1 and fam["n_observations"] == 1
    assert fam["top"][0]["key"] == "carry_unwind"
    assert set(fam["top"][0]["outcomes"]) == set(P.OUTCOME_CLASSES)


def test_a_batched_state_writes_once(store: Path) -> None:
    state = P.load()
    for _ in range(5):
        P.record_outcome("SURVIVED", family="batched", state=state, persist=False)
    assert not (store / "beta.json").exists()
    P.save(state)
    assert P.prior_for("family", "batched").n == 5
