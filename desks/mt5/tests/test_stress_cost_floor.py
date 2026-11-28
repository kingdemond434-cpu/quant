"""The zero-spread stress basis shared by the sealed gauntlet patch and the stage-1 screen.

Fusion Zero quotes 0 points on 14 FX majors, so 3x a zero spread stressed nothing.
`research/stress_cost_floor.stress_costs_for` makes the 3x arm charge 3x a measured basis (the
cost-truth quote plus the round-turn commission, or the measured fill-hour spread): strictly
costlier than 1x, the commission never stressed, a symbol with a spread unchanged, and with
nothing measured it returns None so the stress arm fails closed.

Ported from #143 (`test_stage1_judge.test_zero_spread_stress_is_monotone_...`) without the
stage-1 parts, so it runs before the two-stage judge lands.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parent.parent
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(DESK / "scripts"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def test_zero_spread_stress_is_monotone_and_fails_closed_without_a_basis() -> None:
    import external_gauntlet as G

    from research import stress_cost_floor as F
    meta = json.loads((G.UNI / "universe.json").read_text())
    zero = sorted(k for k, v in meta.items() if isinstance(v, dict) and "median_spread_pts" in v
                  and float(v.get("median_spread_pts") or 0) == 0.0)
    assert "EURUSD" in zero
    assert F.is_zero_spread(meta["EURUSD"])
    c1 = G.costs_for("EURUSD", meta)
    c3, how = F.stress_costs_for("EURUSD", meta, 3.0)
    c6, _ = F.stress_costs_for("EURUSD", meta, 6.0)
    assert how["status"] == "MEASURED" and how["basis_pts"] > 0
    assert c1.spread_per_lot < c3.spread_per_lot < c6.spread_per_lot
    assert c3.commission_per_lot == c1.commission_per_lot          # commission never stressed
    # the sealed arithmetic: before gauntlet_zero_spread_stress.patch lands, 3x of zero == 1x
    # (no stress at all); once it lands the sealed 3x arm IS this basis.
    sealed3 = G.costs_for("EURUSD", meta, mult=3.0).spread_per_lot
    if hasattr(G, "StressBasisUnmeasured"):
        assert sealed3 == pytest.approx(c3.spread_per_lot)
    else:
        assert sealed3 == c1.spread_per_lot
    # a symbol with a spread is unchanged
    nz = next(k for k, v in meta.items() if isinstance(v, dict)
              and float(v.get("median_spread_pts") or 0) > 0 and v.get("tick_size"))
    a, _ = F.stress_costs_for(nz, meta, 3.0)
    assert a.spread_per_lot == G.costs_for(nz, meta, mult=3.0).spread_per_lot
    # THE FILL HOUR: with the cell's fill hour, the stress arm is 3x the MEASURED fill-hour
    # spread the 1x arm pays -- not 3x the commission-only basis
    surf = {"symbols": {"EURUSD": {"hours": {"9": {"status": "MEASURED", "p50": 12.0}}},
                        nz: {"hours": {"1": {"status": "MEASURED", "p50": 50_000.0}}}}}
    c1h = G.Costs.from_symbol(meta["EURUSD"], spread_pts=12.0)          # the sealed 1x arm
    c3h, how_h = F.stress_costs_for("EURUSD", meta, 3.0, hour=9, surface=surf)
    assert how_h["basis"] == "fill_hour_09_spread" and how_h["basis_pts"] == 12.0
    assert c3h.spread_per_lot == pytest.approx(3.0 * c1h.spread_per_lot)
    assert c3h.spread_per_lot > c3.spread_per_lot
    # a spread symbol whose fill hour is thin: 3x the fill hour, never below the registry stress
    b3, how_b = F.stress_costs_for(nz, meta, 3.0, hour=1, surface=surf)
    assert how_b["basis_pts"] == 50_000.0
    assert b3.spread_per_lot > G.costs_for(nz, meta, mult=3.0).spread_per_lot
    # an unmeasured fill hour changes nothing: the rules above apply
    assert F.stress_costs_for("EURUSD", meta, 3.0, hour=4, surface=surf)[1]["basis"] == \
        how["basis"]
    # nothing measured: fail closed
    bare = {"X": {"median_spread_pts": 0.0, "tick_size": 1e-5, "contract_size": 1e5}}
    none, why = F.stress_costs_for("X", bare, 3.0, quotes={})
    assert none is None and why["status"] == "UNMEASURED"
    assert F.stress_costs_for("X", bare, 3.0, quotes={}, hour=9, surface={})[0] is None
