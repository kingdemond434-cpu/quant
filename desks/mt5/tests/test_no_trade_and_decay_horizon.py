"""ALLOC-06/16 and DECAY-03 (2026-10-07): a cost- and edge-derived no-trade gate, and a 90-day
hazard converted to the world path without being read as "already broken"."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import pf_allocator as pa  # noqa: E402


def test_cost_is_each_sleeves_own() -> None:
    cheap = pa.no_trade({"a": 0.05}, {"b": 0.05}, 0.0, one_way_cost={"a": 0.001, "b": 0.001})
    dear = pa.no_trade({"a": 0.05}, {"b": 0.05}, 0.0, one_way_cost={"a": 0.05, "b": 0.05})
    assert dear["cost"] > cheap["cost"] * 10


def test_a_perishable_edge_is_credited_less_than_five_days() -> None:
    durable = pa.no_trade({}, {"a": 0.05}, 1e-4)
    perish = pa.no_trade({}, {"a": 0.05}, 1e-4, half_life_days={"a": 0.5})
    assert durable["effective_horizon_days"] == pytest.approx(pa.NO_TRADE_HORIZON_DAYS)
    assert perish["effective_horizon_days"] < 1.0
    assert perish["benefit_over_horizon"] < durable["benefit_over_horizon"]


def test_required_risk_reduction_never_waits() -> None:
    nt = pa.no_trade({"a": 0.30}, {"a": 0.20}, 0.0, max_heat_now=0.20)
    assert nt["verdict"] == "REBALANCE" and nt["risk_reduction"] is True
    noise = pa.no_trade({"a": 0.20}, {"a": 0.199}, 0.0, max_heat_now=0.25)
    assert noise["verdict"] == "NO CHANGE" and noise["risk_reduction"] is False


def test_hazard_horizon_is_preserved_and_anchored_to_the_blanket() -> None:
    path = 256 * 365.0 / 252.0
    assert pa.hazard_to_path_decay(0.0, path_days=path) == 0.0
    shares = [pa.hazard_to_path_decay(p, path_days=path) for p in (0.05, 0.3, 0.6, 0.95)]
    assert shares == sorted(shares) and all(0 < x < 1 for x in shares)
    # A 90-day hazard is never read as "already broken for the whole path".
    assert pa.hazard_to_path_decay(0.95, path_days=path) < 0.95 + 1e-12
    # Constant-rate identity: lam = -ln(1-p)/90.
    lam = -math.log1p(-0.3) / 90.0
    x = lam * path
    assert pa.hazard_to_path_decay(0.3, path_days=path) == pytest.approx(1 - (1 - math.exp(-x)) / x)


def test_a_base_rate_sleeve_pays_the_blanket() -> None:
    import numpy as np

    from libs.portfolio.robust_elog import SleeveEvidence
    ev = [SleeveEvidence("a", np.zeros(10)), SleeveEvidence("b", np.zeros(10))]
    meta = pa.apply_decay_posterior(ev, {"a": 0.30, "b": 0.90}, 0.30, path_days=371.0)
    assert meta["by_sleeve"]["a"]["decay_prob_i"] == pytest.approx(0.30)
    assert meta["by_sleeve"]["b"]["decay_prob_i"] > 0.30
    assert meta["hazard_horizon_days"] == 90.0
