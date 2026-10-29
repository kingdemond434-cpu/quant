"""The fast clock reuses a scenario population ONLY when the state that drew it is unchanged.

`pf_allocator` reused `data/pf_allocator_cache/worlds.npz` whenever it was under an hour old and
the sleeve names matched, so a new forecast, a refitted regime, a re-measured cost surface, a
moved drift hazard or a changed sampler all left the fast clock solving on stale worlds -- and the
fast clock skipped the regime fit entirely. The key is now a decision-state fingerprint
(`world_fingerprint`) stored inside the npz. These pin: a hit on identical inputs; a miss naming
the component when ANY one of forecast / regime / cost / health / sleeve spec / model version
changes; a regime refit on the fast clock exactly when the regime's inputs change; and a decision
that still runs when the cache is missing or corrupt.
"""
from __future__ import annotations

import inspect
import os
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio.robust_elog import SleeveEvidence, WorldConfig  # noqa: E402

pa = pytest.importorskip("research.pf_allocator", reason="the allocator ships with the desk")

DAYS = pd.date_range("2025-01-01", periods=120, freq="D")
LABELS = tuple("bull" if i % 2 else "bear" for i in range(len(DAYS)))
PROBS = (("bull", 0.6), ("bear", 0.4))
REGIME_IN = "regime-inputs-v1"


def _ev() -> list[SleeveEvidence]:
    rng = np.random.default_rng(7)
    return [SleeveEvidence(name=f"S{i}_asia_TREND", daily_r=rng.normal(0.02, 1.0, len(DAYS)),
                           family="session_bracket", symbol=f"S{i}", n_trials=10,
                           forward_days=3, live_days=1, cost_r=0.05, cost_bias_r=0.01,
                           decay_prob_i=0.2)
            for i in range(3)]


def _cfg(**kw) -> WorldConfig:
    base = {"seed": 0, "n_worlds": 32, "n_rows": 64, "regime_labels": LABELS, "regime_probs": PROBS,
                "regime_min_days": 10}
    base.update(kw)
    return WorldConfig(**base)


def _prime(tmp_path: Path, ev=None, cfg=None, regime_in: str = REGIME_IN) -> Path:
    """A normal pass: draws and writes the cache."""
    cachef = tmp_path / "worlds.npz"
    _, rep = pa.world_population("normal", ev or _ev(), cfg or _cfg(), regime_inputs=regime_in,
                                 regime_diag={"used": dict(PROBS)}, cachef=cachef, cached=None)
    assert rep["hit"] is False and rep["write_error"] is None and cachef.exists()
    return cachef


def _fast(cachef: Path, ev=None, cfg=None, regime_in: str = REGIME_IN):
    return pa.world_population("fast", ev or _ev(), cfg or _cfg(), regime_inputs=regime_in,
                               regime_diag={}, cachef=cachef,
                               cached=pa.read_world_cache(cachef))


def test_identical_inputs_hit_and_return_the_stored_population(tmp_path: Path) -> None:
    cachef = _prime(tmp_path)
    worlds, rep = _fast(cachef)
    assert rep["hit"] is True and rep["changed"] == []
    assert "cached" in worlds.note                 # the decay-billing branch keys on this word
    fresh = pa.sample_worlds(_ev(), _cfg())
    np.testing.assert_array_equal(worlds.r, fresh.r)
    assert worlds.regimes == fresh.regimes         # regimes now survive the round trip


@pytest.mark.parametrize("component, mutate", [
    ("forecast", lambda ev, cfg: ([replace(ev[0], daily_r=ev[0].daily_r + 1e-09), *ev[1:]], cfg)),
    ("forecast", lambda ev, cfg: ([replace(ev[1], forward_days=4), *ev[:1], *ev[2:]], cfg)),
    ("cost", lambda ev, cfg: ([replace(ev[0], cost_bias_r=0.02), *ev[1:]], cfg)),
    ("cost", lambda ev, cfg: (ev, replace(cfg, cost_uncertainty=0.6))),
    ("health", lambda ev, cfg: ([replace(ev[2], decay_prob_i=0.1), *ev[:2]], cfg)),
    ("health", lambda ev, cfg: (ev, replace(cfg, crisis_prob=0.09))),
    ("regime", lambda ev, cfg: (ev, replace(cfg, regime_probs=(("bull", 0.5), ("bear", 0.5))))),
    ("sleeve_spec", lambda ev, cfg: ([replace(ev[0], family="carry"), *ev[1:]], cfg)),
    ("sleeve_spec", lambda ev, cfg: (ev[:2], cfg)),
    ("world_config", lambda ev, cfg: (ev, replace(cfg, crisis_common_share=0.7))),
    ("world_config", lambda ev, cfg: (ev, replace(cfg, seed=1))),
])
def test_any_one_component_change_misses_and_is_named(tmp_path: Path, component, mutate) -> None:
    cachef = _prime(tmp_path)
    ev, cfg = mutate(_ev(), _cfg())
    worlds, rep = _fast(cachef, ev, cfg)
    assert rep["hit"] is False
    assert component in rep["changed"]
    np.testing.assert_array_equal(worlds.r, pa.sample_worlds(ev, cfg).r)   # rebuilt, not stale
    # ...and the rebuilt population is the new cache, so the next identical pass hits.
    assert _fast(cachef, ev, cfg)[1]["hit"] is True


def test_regime_INPUT_change_misses_under_regime(tmp_path: Path) -> None:
    cachef = _prime(tmp_path)
    _, rep = _fast(cachef, regime_in="regime-inputs-v2")
    assert rep["hit"] is False and rep["changed"] == ["regime"]


def test_model_version_bump_misses(tmp_path: Path, monkeypatch) -> None:
    cachef = _prime(tmp_path)
    monkeypatch.setattr(pa, "SCENARIO_MODEL_VERSION", pa.SCENARIO_MODEL_VERSION + 1)
    _, rep = _fast(cachef)
    assert rep["hit"] is False and rep["changed"] == ["model"]


def test_objective_only_fields_do_not_invalidate(tmp_path: Path) -> None:
    cachef = _prime(tmp_path)
    _, rep = _fast(cachef, cfg=_cfg(robust_lambda=0.9, cvar_alpha=0.1))
    assert rep["hit"] is True


def test_age_is_an_upper_bound_not_the_key(tmp_path: Path) -> None:
    cachef = _prime(tmp_path)
    old = cachef.stat().st_mtime - pa.WORLD_CACHE_MAX_AGE_S - 5
    os.utime(cachef, (old, old))
    _, rep = _fast(cachef)
    assert rep["hit"] is False and rep["changed"] == ["max_age"]


@pytest.mark.parametrize("damage", ["missing", "garbage", "truncated", "old_format"])
def test_decision_runs_when_cache_is_missing_or_corrupt(tmp_path: Path, damage: str) -> None:
    cachef = tmp_path / "worlds.npz"
    if damage != "missing":
        _prime(tmp_path)
        if damage == "garbage":
            cachef.write_bytes(b"not an npz at all")
        elif damage == "truncated":
            cachef.write_bytes(cachef.read_bytes()[:200])
        else:                                       # the pre-fingerprint layout: no key inside
            w = pa.sample_worlds(_ev(), _cfg())
            np.savez_compressed(cachef, r=w.r, names=np.array(w.names), crisis=w.crisis,
                                mu=w.mu_draws)
    cached = pa.read_world_cache(cachef)
    assert "error" in cached
    worlds, rep = pa.world_population("fast", _ev(), _cfg(), regime_inputs=REGIME_IN,
                                      regime_diag={}, cachef=cachef, cached=cached)
    assert rep["hit"] is False and rep["changed"] == ["cache_unreadable"]
    assert worlds.r.shape[2] == 3
    assert _fast(cachef)[1]["hit"] is True          # the rebuild repaired the cache


def test_write_is_atomic_and_leaves_no_temp(tmp_path: Path) -> None:
    _prime(tmp_path)
    assert [p.name for p in tmp_path.iterdir()] == ["worlds.npz"]
    assert "os.replace" in inspect.getsource(pa.write_world_cache)


def test_fast_clock_refits_regime_only_when_its_inputs_change(tmp_path: Path,
                                                               monkeypatch) -> None:
    calls: list[int] = []

    def fake_regime_state(daily):
        calls.append(1)
        return LABELS, PROBS, {"fit": True}

    monkeypatch.setattr(pa, "regime_state", fake_regime_state)
    daily = pd.DataFrame(index=DAYS)
    cachef = _prime(tmp_path)

    labels, probs, diag = pa.fast_regime(daily, pa.read_world_cache(cachef), REGIME_IN)
    assert calls == [] and diag["fast_clock"]["rebuilt"] is False
    assert labels == LABELS and probs == PROBS      # the config the cached worlds were drawn on

    labels, probs, diag = pa.fast_regime(daily, pa.read_world_cache(cachef), "changed-inputs")
    assert calls == [1] and diag["fast_clock"]["rebuilt"] is True

    _, _, diag = pa.fast_regime(daily, {"error": "absent"}, REGIME_IN)
    assert calls == [1, 1] and diag["fast_clock"]["rebuilt"] is True


def test_regime_inputs_track_the_file_regime_state_fits_on(tmp_path: Path, monkeypatch) -> None:
    assert pa.REGIME_SOURCE.name in inspect.getsource(pa.regime_state)
    src = tmp_path / "XAUUSD_H1.parquet"
    src.write_bytes(b"v1")
    monkeypatch.setattr(pa, "REGIME_SOURCE", src)
    daily = pd.DataFrame(index=DAYS)
    a = pa._regime_inputs(daily)
    assert pa._regime_inputs(daily) == a
    src.write_bytes(b"v2")
    assert pa._regime_inputs(daily) != a
    assert pa._regime_inputs(pd.DataFrame(index=DAYS[:-1])) != pa._regime_inputs(daily)


def test_run_wires_the_fingerprinted_path() -> None:
    src = inspect.getsource(pa.run)
    assert "world_population(" in src and "fast_regime(" in src
    assert "st_mtime < 3600" not in src
    assert '"world_cache"' in src
