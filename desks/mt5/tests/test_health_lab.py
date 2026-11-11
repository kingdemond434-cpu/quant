"""Strategy-health lab (DECAY-06/13) and the hazard horizon (DECAY-03)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

hl = pytest.importorskip("research.health_lab", reason="ships with the desk")
pa = pytest.importorskip("research.pf_allocator", reason="ships with the desk")


def test_every_case_carries_its_truth() -> None:
    rng = np.random.default_rng(0)
    for c in hl.CASES:
        r, alive = hl._case(c, rng)
        assert r.size == hl.LENGTH == alive.size
        if c in hl.HEALTHY:
            assert alive.all()
        else:
            assert (~alive).any()
        if c in hl.RECOVER:
            assert alive[-1]


def test_detectors_say_dead_on_a_dead_series_and_alive_on_a_good_one() -> None:
    rng = np.random.default_rng(1)
    dead = list(rng.normal(-0.8, 1.0, 60))
    good = list(rng.normal(0.5, 1.0, 60))
    for name in ("t_rule", "ewma"):
        det = hl.DETECTORS[name]
        assert det(dead) and not det(good), name
    assert not hl.t_rule(dead[:5])                    # under MIN_N: silent, not dead


def test_lab_scores_and_verdicts_against_the_baseline(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(hl, "PATHS", 3)
    monkeypatch.setattr(hl, "STEP", 20)
    monkeypatch.setattr(hl, "DETECTORS", {"t_rule": hl.t_rule, "ewma": hl.ewma})
    out = tmp_path / "HL.json"
    doc = hl.run(budget_s=None, force=True, out=out)
    assert doc["status"] == "MEASURED" and out.exists()
    assert set(doc["table"]) == {"t_rule", "ewma"}
    assert set(doc["table"]["ewma"]) == set(hl.CASES) | {"shared_failure"}
    assert doc["verdicts"]["ewma"]["verdict"] in ("BEATS_BASELINE", "LOSES", "MIXED",
                                                   "UNMEASURED")
    assert doc["n_detectors_measured"] >= 0
    again = hl.run(budget_s=None, force=False, out=out)
    assert "skipped" in again
    assert json.loads(out.read_text())["authority"].startswith("none")


def test_a_spent_budget_leaves_cases_pending(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(hl, "DETECTORS", {"t_rule": hl.t_rule})
    doc = hl.run(budget_s=1e-9, force=True, out=tmp_path / "x.json")
    assert doc["status"] == "PARTIAL"


def test_hazard_horizon_conversion() -> None:
    assert pa.hazard_at_horizon(0.1, 90.0) == pytest.approx(0.1)
    assert pa.hazard_at_horizon(0.1, 180.0) == pytest.approx(1 - 0.9 ** 2)
    assert pa.hazard_at_horizon(0.1, 45.0) < 0.1
    assert pa.hazard_at_horizon(1.0, 10.0) == 1.0


def test_decay_posterior_carries_both_horizons_and_applies_the_live_one() -> None:
    from libs.portfolio.robust_elog import SleeveEvidence
    ev = [SleeveEvidence(name="a", daily_r=np.zeros(5))]
    meta = pa.apply_decay_posterior(ev, {"a": 0.05}, 0.30, world_rows=256)
    row = meta["by_sleeve"]["a"]
    assert ev[0].decay_prob_i == pytest.approx(0.05)          # live path unchanged
    assert row["hazard_at_world_horizon"] > 0.05               # shadow on the world horizon
    assert meta["hazard_horizon_days"] == 90.0 and meta["world_horizon_days"] > 300


def test_the_legs_are_on_the_hourly_clock_and_billed() -> None:
    src = (_DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '"research/health_lab.py"' in src and '"research/drift_monitor.py"' in src
    assert '"drift_monitor": drm, "health_lab": hlb' in src
    from libs.research import layers
    assert layers.LEG_LAYER["health_lab"] == "portfolio"
    assert layers.LEG_LAYER["drift_monitor"] == "portfolio"


def test_world_rows_are_one_constant_for_sampler_and_hazard() -> None:
    import inspect

    from research import pf_allocator as pa
    src = inspect.getsource(pa)
    assert "384 if heavy else 256" not in src
    assert src.count("WORLD_ROWS_HEAVY if heavy else WORLD_ROWS_LIGHT") == 2
    assert pa.WORLD_ROWS_LIGHT < pa.WORLD_ROWS_HEAVY
