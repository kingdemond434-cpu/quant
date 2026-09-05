"""The optimiser solved a book and then nothing used it, and nothing made it earn the right to.

    python -m pytest tests/portfolio/test_allocator_authority.py -q

TWO DEFECTS, ONE SHAPE. `allocator_heat` took the optimiser's TOTAL and `allocator_order` took
its RANKING, so h_i -- the only number the optimiser actually solves for -- reached nothing: a
book of {A: 4.3%, B: 3.7%} became "total 8%, in that order", which is a different allocation to
the one that maximised E[log W]. And nothing ever asked whether the dynamic allocator was better
than equal weight.

WHAT MUST NOT REGRESS, in order of what it would cost:

  1. no fresh passing certificate -> the book may NOT size (fails closed, silently keeps Q_OPT)
  2. the contest is FAIR: same worlds, same evidence, same total heat, only weights differ
  3. an optimiser that merely deploys more capital cannot win by doing so
  4. a hair's-breadth win does not grant authority
  5. an unscoreable dynamic book never passes
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pytest

from libs.portfolio import allocator_proof as ap
from libs.portfolio.robust_elog import SleeveEvidence, WorldConfig, sample_worlds


def _ev(name: str, mu: float, sd: float = 1.0, n: int = 400, seed: int = 0) -> SleeveEvidence:
    rng = np.random.default_rng(seed)
    return SleeveEvidence(name=name, daily_r=rng.normal(mu, sd, n), family=name, symbol=name,
                          forward_days=120, live_days=60)


@pytest.fixture
def book() -> list[SleeveEvidence]:
    return [_ev("a", 0.05, 1.0, seed=1), _ev("b", 0.03, 2.0, seed=2), _ev("c", 0.01, 0.5, seed=3)]


# ------------------------------------------------- 1. the contest is fair

def test_every_baseline_is_scored_at_the_dynamic_books_total_heat(book) -> None:
    """An optimiser that just deploys more capital must not win by doing so."""
    dyn = {"a": 0.04, "b": 0.02, "c": 0.01}
    res = ap.contest(book, dyn, cfg=WorldConfig(seed=7, n_worlds=64, n_rows=128))
    total = sum(dyn.values())
    for name, sc in res["scores"].items():
        if name == "static_incumbent":
            continue
        assert sc["total_heat"] == pytest.approx(total, abs=1e-9), (
            f"{name} was scored at a different heat -- the contest measures deployment, "
            f"not allocation skill")


def test_all_four_baselines_are_present(book) -> None:
    res = ap.contest(book, {"a": 0.03, "b": 0.02, "c": 0.01},
                     {"a": 0.05}, cfg=WorldConfig(seed=7, n_worlds=64, n_rows=128))
    assert set(res["scores"]) >= {"dynamic", "equal_weight", "inverse_vol", "risk_parity",
                                  "static_incumbent"}


def test_the_incumbent_is_scored_at_its_own_heat_not_rescaled(book) -> None:
    """Do-nothing must stay do-nothing; rescaling it invents a strategy nobody is running."""
    res = ap.contest(book, {"a": 0.03, "b": 0.02, "c": 0.01}, {"a": 0.005},
                     cfg=WorldConfig(seed=7, n_worlds=64, n_rows=128))
    assert res["scores"]["static_incumbent"]["total_heat"] == pytest.approx(0.005, abs=1e-9)


def test_the_same_world_population_scores_every_book(book) -> None:
    """Drawing fresh worlds per book is the classic rigged comparison."""
    cfg = WorldConfig(seed=11, n_worlds=64, n_rows=128)
    w = sample_worlds(book, cfg)
    a = ap.contest(book, {"a": 0.03, "b": 0.02, "c": 0.01}, cfg=cfg, worlds=w)
    b = ap.contest(book, {"a": 0.03, "b": 0.02, "c": 0.01}, cfg=cfg, worlds=w)
    assert a["scores"]["equal_weight"] == b["scores"]["equal_weight"]


# ------------------------------------------------- 2. winning must be earned

def test_a_hairs_breadth_win_does_not_grant_authority(book, monkeypatch) -> None:
    """Inside the noise of a sampled-world estimate, a win is luck."""
    monkeypatch.setattr(ap, "score_book", lambda ev, h, **k: {
        "robust_score": 1.0 + (1e-9 if h.get("a") == 0.99 else 0.0), "total_heat": 0.1})
    res = ap.contest(book, {"a": 0.99}, cfg=WorldConfig(seed=1, n_worlds=8, n_rows=32))
    assert res["passed"] is False


def test_a_clear_win_passes(book, monkeypatch) -> None:
    monkeypatch.setattr(ap, "score_book", lambda ev, h, **k: {
        "robust_score": 5.0 if h.get("a") == 0.99 else 1.0, "total_heat": 0.1})
    res = ap.contest(book, {"a": 0.99}, cfg=WorldConfig(seed=1, n_worlds=8, n_rows=32))
    assert res["passed"] is True


def test_an_unscoreable_dynamic_book_never_passes(book, monkeypatch) -> None:
    monkeypatch.setattr(ap, "score_book", lambda ev, h, **k: {
        "robust_score": float("-inf") if h.get("a") == 0.99 else 1.0, "total_heat": 0.1})
    res = ap.contest(book, {"a": 0.99}, cfg=WorldConfig(seed=1, n_worlds=8, n_rows=32))
    assert res["passed"] is False and "finite" in res["why"]


# ------------------------------------------------- 3. the certificate gates authority

def test_no_certificate_means_no_sizing(tmp_path: Path) -> None:
    cert, why = ap.read_certificate(tmp_path)
    assert cert is None and "has not beaten the baselines" in why


def test_a_failing_certificate_means_no_sizing(tmp_path: Path) -> None:
    (tmp_path / "reports").mkdir()
    (tmp_path / ap.PROOF).write_text(json.dumps({"passed": False, "why": "lost to inverse_vol"}))
    cert, why = ap.read_certificate(tmp_path)
    assert cert is None and "did not beat" in why


def test_a_stale_certificate_means_no_sizing(tmp_path: Path) -> None:
    (tmp_path / "reports").mkdir()
    p = tmp_path / ap.PROOF
    p.write_text(json.dumps({"passed": True, "best_baseline": "equal_weight"}))
    cert, why = ap.read_certificate(tmp_path, now=time.time() + ap.MAX_AGE_S + 60)
    assert cert is None and "old" in why


def test_a_fresh_passing_certificate_grants_it(tmp_path: Path) -> None:
    (tmp_path / "reports").mkdir()
    (tmp_path / ap.PROOF).write_text(json.dumps({"passed": True, "best_baseline": "inverse_vol"}))
    cert, why = ap.read_certificate(tmp_path)
    assert cert is not None and "inverse_vol" in why


def test_an_unreadable_certificate_fails_closed(tmp_path: Path) -> None:
    (tmp_path / "reports").mkdir()
    (tmp_path / ap.PROOF).write_text("{not json")
    cert, why = ap.read_certificate(tmp_path)
    assert cert is None and "unreadable" in why
