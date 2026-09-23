"""Every scheduled leg belongs to a declared layer; the census is the ledger's numbers grouped."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.research import layers  # noqa: E402


def test_every_scheduled_leg_has_a_layer() -> None:
    assert layers.unassigned() == [], \
        "a leg was added to hourly/daily_cycle without a layer in libs/research/layers.LEG_LAYER"
    assert set(layers.LEG_LAYER.values()) <= set(layers.LAYERS)


def test_the_seven_layers_are_all_declared_with_at_least_one_leg() -> None:
    for L in layers.LAYERS:
        assert any(v == L for v in layers.LEG_LAYER.values()), L


def test_census_groups_the_ledger_and_names_starved_layers() -> None:
    cost = {"external_gauntlet": {"runs": 10, "hours": 2.5, "failures": 1},
            "pf_allocator": {"runs": 10, "hours": 0.5, "failures": 0},
            "not_a_leg": {"runs": 3, "hours": 9.0, "failures": 0}}
    doc = layers.census(cost)
    pred = doc["layers"]["prediction"]
    assert pred["runs"] == 10 and pred["hours"] == 2.5 and pred["failure_rate"] == 0.1
    assert "external_gauntlet" in pred["costed_legs"] and "backtest" in pred["dark_legs"]
    assert doc["total_hours"] == 3.0, "an unregistered run is not silently added to a layer"
    assert "exit" in doc["starved_layers"] and "prediction" not in doc["starved_layers"]
    assert doc["layers"]["portfolio"]["share_of_hours"] == round(0.5 / 3.0, 4)
