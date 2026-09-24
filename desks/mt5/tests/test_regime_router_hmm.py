"""THE LATENT AXIS AND THE POOLED ROUTER -- and the distinction that made the organ honest.

This organ published `router_active: 0` with the note "no router beats its unrouted model out of
sample after tax" while ZERO routers had ever been scored. A measured zero and a dark zero are
different verdicts and they were being printed with the same words. The tests below pin the three
states the pooled path can be in, and pin that they stay distinguishable:

    UNMEASURED      nothing to score. Not a judgement.
    TAXED_OUT       scored, and the state did not earn its tax. A REAL, valuable negative.
    EARNS_ITS_PLACE scored, and it did.

They also pin the rule that makes the negative trustworthy: routed and unrouted are scored on an
IDENTICAL trade set, with the same proper score and the same tax.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.regime import pooling  # noqa: E402
from research import regime_router as rr  # noqa: E402


def _obs(sleeve: str, family: str, state: str, r: float, ns: int) -> pooling.Obs:
    return pooling.Obs(sleeve=sleeve, family=family, state=state, r=r, ns=ns)


def test_the_latent_axis_is_declared_and_is_the_sixth() -> None:
    assert rr.HMM_AXIS == "hmm"
    assert rr.HMM_AXIS in rr.AXES
    assert set(rr.AXES) >= {"vol", "session", "usd", "dow", "risk", "hmm"}


def test_an_unfittable_symbol_reads_unmeasured_never_a_fabricated_state() -> None:
    """A regime nobody was ever in is worse than no regime at all."""
    notes: list[str] = []
    states = rr.States(notes)
    from datetime import UTC, datetime

    labels, _row = states.read("NO_SUCH_SYMBOL_XYZ", datetime(2026, 9, 24, tzinfo=UTC), None)
    assert labels[rr.HMM_AXIS] == rr.UNMEASURED


def test_nothing_to_score_is_unmeasured_and_says_why() -> None:
    book, rows = rr._pooled_router([_obs("a", "f", "quiet", 1.0, i) for i in range(3)])
    assert book["status"] == rr.UNMEASURED
    assert rows == {}
    assert "UNMEASURED" in book["why"] and "not a zero" in book["why"]
    assert "net" not in book, "an UNMEASURED router must not publish a net"


def test_a_state_that_carries_nothing_is_a_measured_zero_not_a_dark_one() -> None:
    """Pure noise must come back TAXED_OUT and inactive -- and MEASURED, which is the point."""
    rng = np.random.RandomState(4)
    obs = []
    for i in range(160):
        obs.append(_obs(f"s{i % 8}", f"fam{i % 3}", ["quiet", "normal", "stress"][i % 3],
                        float(rng.randn()), i))
    book, rows = rr._pooled_router(obs)
    assert book["status"] == "MEASURED"
    assert book["verdict"] == "TAXED_OUT"
    assert book["active"] is False
    assert book["net"] <= 0 or book["t_gain"] < rr.MIN_T_GAIN
    assert "MEASURED zero" in book["why"]
    assert rows, "a measured book must still publish its per-sleeve rows"


def test_a_state_that_really_moves_returns_is_found() -> None:
    """The negative above must not be the only answer the path can give."""
    rng = np.random.RandomState(9)
    obs = []
    for i in range(400):
        state = ["quiet", "stress"][i % 2]
        mean = 1.5 if state == "stress" else -1.5
        obs.append(_obs(f"s{i % 6}", "fam", state, float(mean + 0.3 * rng.randn()), i))
    book, _rows = rr._pooled_router(obs)
    assert book["status"] == "MEASURED"
    assert book["verdict"] == "EARNS_ITS_PLACE", book
    assert book["active"] is True
    assert book["net"] > 0 and book["t_gain"] >= rr.MIN_T_GAIN


def test_routed_and_unrouted_are_judged_on_the_same_trades_and_the_same_tax() -> None:
    rng = np.random.RandomState(1)
    obs = [_obs(f"s{i % 5}", "fam", ["quiet", "stress"][i % 2], float(rng.randn()), i)
           for i in range(120)]
    book, rows = rr._pooled_router(obs)
    from libs.models.zoo import TAX

    assert book["tax"] == float(TAX["soft_moe"]), "the pooled path must pay the walk-forward tax"
    assert book["net"] == pytest.approx(
        book["gain"] - book["tax"], abs=1e-6), "net must be gain less the declared tax"
    # every scored sleeve's n is a count of predictions, and they sum to the book's n
    assert sum(r["n"] for r in rows.values()) == book["n_scored"]


def test_small_n_is_scored_where_the_fold_minimum_refused() -> None:
    """The whole point: a six-trade sleeve gets an answer, and the bar did not move."""
    rng = np.random.RandomState(2)
    obs = []
    for i in range(120):
        obs.append(_obs("big", "fam", ["quiet", "stress"][i % 2], float(rng.randn()), i))
    for j in range(6):
        obs.append(_obs("tiny", "fam", ["quiet", "stress"][j % 2], float(rng.randn()), 200 + j))
    _book, rows = rr._pooled_router(obs)
    assert "tiny" in rows
    assert rows["tiny"]["scored"] is True
    assert rows["tiny"]["n"] < rr.MIN_ROUTER_TRADES, (
        "this sleeve is below the walk-forward fold minimum; that is why it is here")
    assert rows["tiny"]["basis"] == "prequential_partial_pooling"


def test_a_sleeve_with_nothing_to_predict_from_is_published_unmeasured() -> None:
    rng = np.random.RandomState(3)
    obs = [_obs("big", "fam", ["quiet", "stress"][i % 2], float(rng.randn()), i)
           for i in range(60)]
    obs.append(_obs("lonely", "fam", "quiet", 0.5, 900))
    _book, rows = rr._pooled_router(obs)
    assert rows["lonely"]["scored"] is False
    assert "why" in rows["lonely"] and str(rr.MIN_POOLED_TRADES) in rows["lonely"]["why"]
