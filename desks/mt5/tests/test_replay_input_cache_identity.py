"""A replay cache cannot serve returns from superseded input reconstruction."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(DESK), str(DESK / "scripts")]
import external_gauntlet as gauntlet  # noqa: E402


@pytest.mark.parametrize("changed", ["mt5desk/legacy_family_inputs.py",
                                     "mt5desk/family_inputs.py",
                                     "mt5desk/family_clock_transition.py",
                                     "scripts/external_gauntlet.py",
                                     "research/orthogonal_sweep.py"])
def test_input_and_builder_repairs_invalidate_replay_cache(tmp_path, monkeypatch, changed):
    desk = tmp_path / "desks/mt5"
    for rel in ("mt5desk/engine.py", "mt5desk/cell_modifiers.py", "mt5desk/data.py",
                "mt5desk/legacy_family_inputs.py", "mt5desk/family_inputs.py",
                "mt5desk/family_clock_transition.py", "scripts/external_gauntlet.py",
                "research/orthogonal_sweep.py",
                # The signed image (hour-of-entry, stack step 05) adds the cost a cached series
                # was charged to the identity: both must exist for it to be computed at all.
                "research/entry_hour_cost.py", "data/cost_surface.json"):
        path = desk / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("version = 1\n", encoding="utf-8")
    monkeypatch.setattr(gauntlet, "BASE", tmp_path)
    gauntlet._replay_code_identity.cache_clear()
    try:
        original = gauntlet._cache_key("EURUSD", "carry", {}, "2026-10-09", "M5")
        (desk / changed).write_text("version = 2\n", encoding="utf-8")
        # A running worker retains its loaded identity; a new worker recomputes it.
        assert gauntlet._cache_key("EURUSD", "carry", {}, "2026-10-09", "M5") == original
        gauntlet._replay_code_identity.cache_clear()
        assert gauntlet._cache_key("EURUSD", "carry", {}, "2026-10-09", "M5") != original
    finally:
        gauntlet._replay_code_identity.cache_clear()
