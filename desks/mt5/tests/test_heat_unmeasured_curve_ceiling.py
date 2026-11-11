"""An unmeasured growth curve opens no licence above the 20% fallback (#896 audit SF).

`resolve`'s default ceiling was the measured-free 1.00 whenever ANY curve point existed, while
the target rule calls a curve with fewer than three points UNMEASURED. Both now use the same
three points. RULE 1, stated: on one or two points this LOWERS the ceiling a free optimum above
20% could reach (it held 1.00 before); the principal's 2026-10-29 order is that the fallback is
20% when the curve is unmeasured, and the held-back heat is named on the missed-growth `ceiling`
line as UNMEASURED with `forgone_heat`, priced once the curve is measured. Three or more points
leave everything exactly as before.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import heat_policy as hp  # noqa: E402
from research import missed_growth as mg  # noqa: E402

TWO = {0.1: 0.0010, 0.2: 0.0016}
FOUR = {0.1: 0.0010, 0.2: 0.0016, 0.4: 0.0021, 0.6: 0.0019}


def test_two_points_hold_the_fallback_and_say_why() -> None:
    v = hp.resolve(0.45, curve=TWO)
    assert v.hard_ceiling == pytest.approx(hp.HEAT_UNMEASURED_FALLBACK)
    assert v.total_heat == pytest.approx(hp.HEAT_UNMEASURED_FALLBACK) and v.binding == "ceiling"
    assert any("UNMEASURED-CURVE FALLBACK" in r for r in v.reasons)


def test_three_points_keep_the_measured_licence() -> None:
    v = hp.resolve(0.45, curve=FOUR)
    assert v.hard_ceiling == pytest.approx(hp.HEAT_HARD_CEILING)
    assert not any("UNMEASURED-CURVE FALLBACK" in r for r in v.reasons)
    assert hp.resolve(0.45, curve=TWO, hard_ceiling=0.5).hard_ceiling == 0.5   # explicit wins


def test_the_held_back_heat_is_named_on_the_missed_growth_line() -> None:
    alloc = {"heat": {"binding": "ceiling", "free_optimum": 0.45, "hard_ceiling": 0.20,
                      "curve": [[0.1, 0.0010], [0.2, 0.0016]]}}
    line = mg.measure_ceiling(None, alloc, {})
    assert line["verdict"] == mg.UNMEASURED and line["forgone_heat"] == pytest.approx(0.25)
    assert line["curve_points"] == 2
