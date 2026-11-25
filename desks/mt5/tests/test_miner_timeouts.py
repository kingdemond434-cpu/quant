"""Per-miner walls: a measured overrun gets its own hard wall; the rest keep the default."""
from __future__ import annotations

import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "side_channels"), str(DESK), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import run_all_miners as ram  # noqa: E402


def test_seasonality_gets_its_measured_wall_and_others_the_default():
    assert ram.miner_timeout_s("seasonality") == 600
    assert ram.miner_timeout_s("github") == ram.MINER_TIMEOUT_S


def test_every_override_is_a_finite_wall_above_the_default():
    for name, wall in ram.MINER_TIMEOUT_OVERRIDES_S.items():
        assert ram.MINER_TIMEOUT_S < wall <= 1800, name
