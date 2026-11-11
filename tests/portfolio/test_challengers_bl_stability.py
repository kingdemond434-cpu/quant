"""Audit repair #7 (2026-10-06): Black-Litterman challenger and the weight-perturbation report."""

from __future__ import annotations

import numpy as np
import pytest

from libs.portfolio import challengers
from libs.portfolio.allocator_proof import contest, perturbation_stability
from libs.portfolio.robust_elog import SleeveEvidence, WorldConfig, sample_worlds


def _ev(short: bool = False) -> list[SleeveEvidence]:
    rng = np.random.default_rng(0)
    return [SleeveEvidence(f"s{i}", rng.normal(0.02 * (i + 1), 0.3, 30 if short and i == 3
                                              else 400)) for i in range(4)]


def test_black_litterman_is_long_only_at_the_requested_heat() -> None:
    b = challengers.black_litterman(_ev(), 0.20)
    assert sum(b.values()) == pytest.approx(0.20)
    assert all(v >= 0 for v in b.values())
    assert "black_litterman" in challengers.all_books(_ev(), 0.20)


def test_black_litterman_is_a_different_book_from_mean_variance() -> None:
    ev = _ev(short=True)
    bl, mv = challengers.black_litterman(ev, 0.2), challengers.mean_variance(ev, 0.2)
    assert any(abs(bl[k] - mv[k]) > 1e-6 for k in bl)


def test_perturbation_stability_is_reported_in_the_contest() -> None:
    ev = _ev()
    cfg = WorldConfig(n_worlds=16, n_rows=64, seed=1)
    w = sample_worlds(ev, cfg)
    book = {e.name: 0.05 for e in ev}
    st = perturbation_stability(ev, book, cfg=cfg, worlds=w)
    assert st["status"] == "MEASURED" and st["n"] > 0 and 0.0 <= st["share_better"] <= 1.0
    out = contest(ev, book, cfg=cfg, worlds=w)
    assert out["perturbation_stability"]["status"] == "MEASURED"
    assert "black_litterman" in out["books"]
