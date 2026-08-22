from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
for path in (DESK, DESK / "research", DESK.parent.parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from research import allocation  # noqa: E402


def test_mt5_allocator_reuses_joint_dependence_preserving_monte_carlo() -> None:
    rng = np.random.default_rng(23)
    common = rng.normal(0.0002, 0.01, 120)
    daily = pd.DataFrame({
        "gold": common + rng.normal(0.0, 0.002, 120),
        "fx": common + rng.normal(0.0, 0.002, 120),
    })

    report = allocation.portfolio_mc_report(daily, np.array([0.5, 0.5]))

    assert report["measured"] is True
    assert report["strategies"] == 2
    assert report["marks"] == 120
    assert report["draws"] == 2_000
    assert "PORTFOLIO_MC_DRAWDOWN" in report
    assert "PORTFOLIO_MC_RUIN" in report
    assert report["DEPENDENCE_BLINDNESS"] is not None
