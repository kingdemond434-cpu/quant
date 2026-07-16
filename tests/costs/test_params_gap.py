"""Tests for cost parameters and the gap-risk component."""

from __future__ import annotations

import pytest

from libs.costs.errors import CostError
from libs.costs.gap import estimate_gap_cost
from libs.costs.params import DEFAULT_COST_PARAMS, get_cost_params

_REQUIRED = {"XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY", "US500", "NAS100", "BTCUSD"}


def test_all_required_instruments_have_params() -> None:
    assert set(DEFAULT_COST_PARAMS) >= _REQUIRED


def test_get_cost_params_unknown_raises() -> None:
    with pytest.raises(CostError):
        get_cost_params("DOGEUSD")


def test_custom_registry_used() -> None:
    custom = dict(DEFAULT_COST_PARAMS)
    params = get_cost_params("XAUUSD", custom)
    assert params.instrument == "XAUUSD"


def test_estimate_gap_cost() -> None:
    params = get_cost_params("XAUUSD")
    assert estimate_gap_cost(params, 1.0, 2000.0) == pytest.approx(2000.0)  # 0.01*2000*100*1
    assert estimate_gap_cost(params, 2.0, 2000.0) == pytest.approx(4000.0)
