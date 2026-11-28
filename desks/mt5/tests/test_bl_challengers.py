"""The BL / MVO challenger leg (mandate D15): walk-forward on realised returns, no authority."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio.robust_elog import SleeveEvidence  # noqa: E402

blc = pytest.importorskip("research.bl_challengers", reason="ships with the desk")
ia = pytest.importorskip("research.input_ablation", reason="ships with the desk")


def _daily(n: int = 290, k: int = 4, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-01-01", periods=n, freq="D")
    data = {f"s{i}": 0.02 * (2 - i) + rng.normal(0, 0.5, n) for i in range(k)}
    return pd.DataFrame(data, index=[str(d.date()) for d in idx])


@pytest.fixture()
def fast(monkeypatch):
    def build(_trials):
        return lambda hist: [SleeveEvidence(name=str(c), daily_r=hist[c].to_numpy(dtype=float))
                             for c in hist.columns]
    monkeypatch.setattr(ia, "_evidence_asof", build)
    monkeypatch.setattr(blc, "_regime", lambda daily, asof=None: (
        tuple("calm" if (i // 30) % 2 == 0 else "stress" for i in range(len(daily))),
        (("calm", 0.7), ("stress", 0.3))))
    monkeypatch.setattr(blc, "_bounds", lambda daily, total: {})
    monkeypatch.setattr(blc, "N_WORLDS", 32)
    monkeypatch.setattr(blc, "N_ROWS", 64)


def test_walk_forward_scores_every_arm_and_caches_windows(fast) -> None:
    daily = _daily()
    cache: dict = {}
    wf = blc.walk_forward(daily, {}, 0.2, max_windows=3, deadline=None, cache=cache,
                          persist=lambda: None)
    assert len(wf["rows"]) == 3 and len(cache) == 3 and wf["pending_windows"] == 0
    for r in wf["rows"]:
        assert set(r["metrics"]) == set(blc.bl.ARMS)
    again = blc.walk_forward(daily, {}, 0.2, max_windows=3, deadline=None, cache=cache,
                             persist=lambda: None)
    assert again["cache_hits"] == 3
    s = blc.summarise(wf["rows"])
    assert "vs_allocator" in s["D_bl_world_state_views"]
    assert "vs_shuffled_control" in s["D_bl_world_state_views"]
    assert "vs_allocator" not in s["A_allocator"]


def test_a_spent_budget_leaves_windows_pending_not_faked(fast) -> None:
    wf = blc.walk_forward(_daily(), {}, 0.2, max_windows=3, deadline=0.0, cache={},
                          persist=lambda: None)
    assert wf["rows"] == [] and wf["pending_windows"] == 3


def test_now_books_scores_on_one_population_and_holds_no_authority(fast) -> None:
    daily = _daily()
    ev = ia._evidence_asof({})(daily)
    now = blc.now_books(ev, daily, {}, 0.2)
    assert set(now["arms"]) == set(blc.bl.ARMS)
    assert now["beliefs"]["prior_source"] == "equal heat"
    for a in now["arms"].values():
        assert a["total_heat"] == pytest.approx(0.2, abs=1e-6)


def test_incumbent_falls_back_to_the_floor(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(blc, "ALLOC", tmp_path / "none.json")
    book, tot = blc.incumbent()
    assert book == {} and tot == pytest.approx(0.20)
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"book": {"x": 0.15, "y": 0.1}, "heat": {"total": 0.25}}))
    monkeypatch.setattr(blc, "ALLOC", p)
    assert blc.incumbent() == ({"x": 0.15, "y": 0.1}, 0.25)


def test_the_leg_is_wired_into_the_hourly_cycle_and_billed() -> None:
    src = (_DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '"research/bl_challengers.py"' in src and '"bl_challengers": blc' in src
    from libs.research import layers
    assert layers.LEG_LAYER["bl_challengers"] == "portfolio"
