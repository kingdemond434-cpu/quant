"""The best single sleeve, reported beside the funded book (CRO row 111 Q4, ARCH-30).

Report only: the whole funded heat on the one sleeve that scores best alone, on the same worlds,
against the funded book. It is never a proof rival and never the fallback.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio.robust_elog import SleeveEvidence, WorldConfig, sample_worlds  # noqa: E402
from research import pf_allocator as pa  # noqa: E402


def _ev() -> list[SleeveEvidence]:
    rng = np.random.default_rng(3)
    core = rng.normal(0.0, 1.0, 500)
    out = []
    for i, (mu, rho) in enumerate([(0.06, 0.9), (0.05, 0.9), (0.04, -0.3), (0.01, 0.0)]):
        z = rho * core + np.sqrt(1 - rho * rho) * rng.normal(0.0, 1.0, 500)
        out.append(SleeveEvidence(name=f"s{i}", daily_r=0.3 * z + mu, family="f",
                                  symbol=f"S{i}", forward_days=40, n_trials=5))
    return out


def test_it_scores_the_best_lone_sleeve_against_the_funded_book() -> None:
    ev = _ev()
    cfg = WorldConfig(seed=7, n_worlds=64, n_rows=150)
    worlds = sample_worlds(ev, cfg)
    funded = {"s0": 0.08, "s1": 0.06, "s2": 0.06}
    doc = pa.best_single_sleeve(ev, funded, cfg=cfg, worlds=worlds)
    assert doc["status"] == "MEASURED" and doc["name"] in {"s0", "s1", "s2", "s3"}
    assert doc["heat"] == 0.2 and doc["n_scored"] == 4
    assert doc["beats_funded"] == (doc["delta_vs_funded"] is not None
                                   and doc["delta_vs_funded"] > 0)
    assert "never the fallback" in doc["role"]
    assert pa.best_single_sleeve(ev, {}, cfg=cfg, worlds=worlds)["status"] == "UNMEASURED"
    assert pa.best_single_sleeve(ev, funded, cfg=cfg, worlds=None)["status"] == "UNMEASURED"


def test_it_is_published_and_never_reaches_the_proof_or_the_fallback() -> None:
    src = (_DESK / "research" / "pf_allocator.py").read_text(encoding="utf-8")
    assert '"best_single_sleeve": best_single_sleeve(ev, funded, cfg=cfg, worlds=worlds),' in src
    from libs.portfolio import challengers
    assert "best_single_sleeve" not in challengers.CHALLENGERS
