"""Tests for the lockbox, economic-prior gate, and stress-cost validation."""

from __future__ import annotations

import numpy as np
import pytest
from tests.validation.conftest import complete_prior

from libs.costs.scenarios import CostScenario
from libs.validation.economic_prior import EconomicPrior, economic_prior_gate
from libs.validation.errors import ValidationError
from libs.validation.lockbox import LockedHoldout
from libs.validation.stress_costs import stress_cost_validation

# --- lockbox ---------------------------------------------------------------


def test_lockbox_research_free_holdout_once() -> None:
    box = LockedHoldout(list(range(100)), holdout_fraction=0.3)
    assert box.research() == list(range(70))
    assert box.research() == list(range(70))  # research is always accessible
    held = box.open_lockbox()
    assert held == list(range(70, 100))
    assert box.is_opened
    assert len(box.access_log) == 1


def test_lockbox_second_open_raises() -> None:
    box = LockedHoldout(np.arange(50), holdout_fraction=0.4)
    box.open_lockbox()
    with pytest.raises(ValidationError):
        box.open_lockbox()


def test_lockbox_invalid_fraction() -> None:
    with pytest.raises(ValidationError):
        LockedHoldout(list(range(10)), holdout_fraction=0.0)


# --- economic prior gate ---------------------------------------------------


def test_complete_prior_passes() -> None:
    assert economic_prior_gate(complete_prior()).passed
    assert economic_prior_gate(EconomicPrior(**complete_prior())).passed


def test_missing_field_fails() -> None:
    prior = complete_prior()
    del prior["why_decay"]
    result = economic_prior_gate(prior)
    assert not result.passed
    assert "why_decay" in result.missing


def test_blind_no_mechanism_fails() -> None:
    prior = complete_prior()
    prior["mechanism"] = ""
    result = economic_prior_gate(prior)
    assert not result.passed
    assert "mechanism" in result.missing


def test_blank_answer_fails() -> None:
    prior = complete_prior()
    prior["why_it_works"] = "   "
    assert not economic_prior_gate(prior).passed


# --- stress cost validation ------------------------------------------------


def test_edge_survives_base_fails_5x() -> None:
    gross = [10.0] * 10  # gross 100
    costs = [3.0] * 10   # base 30
    result = stress_cost_validation(gross, costs, required_scenario=CostScenario.X3)
    assert result.passed  # 100 - 90 = 10 > 0 at 3x
    by = {s.scenario: s.survived for s in result.by_scenario}
    assert by["5x"] is False  # 100 - 150 < 0


def test_strong_edge_survives_all() -> None:
    result = stress_cost_validation([100.0], [1.0], required_scenario=CostScenario.X5)
    assert result.passed
    assert all(s.survived for s in result.by_scenario)


def test_stress_validates_inputs() -> None:
    with pytest.raises(ValidationError):
        stress_cost_validation([1.0, 2.0], [1.0])
    with pytest.raises(ValidationError):
        stress_cost_validation([1.0], [-1.0])
