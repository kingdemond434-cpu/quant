"""GARCH dispersion scaling is a SHADOW reading until it wins out of sample (#896 audit MF1, SF3).

Standing order: GARCH/HMM and LLM sizing stay shadow-only; an input reaches money the moment it
beats the plain solve OOS, never before. Run-level: with a non-trivial GARCH scale in hand, the
book the optimiser solves while `GARCH_SIZING_LIVE` is False is exactly the book it solves with
no GARCH at all, and only the switch makes them differ.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio import garch_vol  # noqa: E402
from libs.portfolio.robust_elog import (  # noqa: E402
    SleeveEvidence,
    WorldConfig,
    optimise,
    sample_worlds,
)
from research import model_roles  # noqa: E402
from research import pf_allocator as pa  # noqa: E402


def _ev() -> list[SleeveEvidence]:
    rng = np.random.default_rng(11)
    return [SleeveEvidence(name=f"s{i}", daily_r=rng.normal(0.02 * (i + 1), 0.6, 400),
                           family="f", symbol=f"SYM{i}", forward_days=60, n_trials=5)
            for i in range(3)]


def _solve(ev: list[SleeveEvidence]) -> dict[str, float]:
    cfg = WorldConfig(seed=5, n_worlds=64, n_rows=120)
    return optimise(ev, hard_cap=0.20, target=0.20, cfg=cfg, worlds=sample_worlds(ev, cfg)).heat


def test_shadow_garch_leaves_the_solved_book_exactly_as_no_garch(monkeypatch, tmp_path) -> None:
    assert pa.GARCH_SIZING_LIVE is False
    scale = {"s0": 2.5, "s1": 0.4, "s2": 1.0}
    monkeypatch.setattr(garch_vol, "vol_scale_by_sleeve",
                        lambda ev, horizon_days: (dict(scale), {"fitted": len(scale)}))
    monkeypatch.setattr(pa, "CACHE", tmp_path)
    base = _ev()
    shadow_ev, meta = pa.apply_garch_vol(list(base), "normal")
    assert meta["applied"] is False and meta["shadow"] is True
    assert meta["scale"] == {k: round(v, 4) for k, v in scale.items()}     # published
    assert all(a.daily_r is b.daily_r for a, b in zip(shadow_ev, base, strict=True))
    assert _solve(shadow_ev) == pytest.approx(_solve(base), abs=0.0)        # same fractions
    live_ev, live_meta = pa.apply_garch_vol(list(base), "normal", live=True)
    assert live_meta["applied"] is True
    assert _solve(live_ev) != pytest.approx(_solve(base), abs=1e-6), "the switch is what moves it"


def test_the_family_registry_says_shadow() -> None:
    assert "SHADOW" in str(model_roles.FAMILIES["garch_vol"])
