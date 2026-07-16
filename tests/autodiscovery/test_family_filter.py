"""Focused-family restriction of the hypothesis universe (committee T0)."""

from __future__ import annotations

from libs.autodiscovery.generators import planned_hypotheses
from libs.autodiscovery.models import Family


def test_family_filter_restricts_universe() -> None:
    full = planned_hypotheses(["EURUSD"])
    focused = planned_hypotheses(["EURUSD"], families=[Family.CARRY, Family.CROSS_ASSET])
    assert 0 < len(focused) < len(full)                      # strictly fewer trials
    assert {h.family for h, _ in focused} <= {Family.CARRY, Family.CROSS_ASSET}


def test_none_keeps_all_families() -> None:
    full = planned_hypotheses(["EURUSD"])
    assert len({h.family for h, _ in full}) == 12             # all twelve families present
