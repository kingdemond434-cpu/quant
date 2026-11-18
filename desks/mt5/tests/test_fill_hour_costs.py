"""Forward clocks charge the spread of the hour they FILL, frozen with the clock (2026-11-13)."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import shadow_forward as sf  # noqa: E402
from mt5desk.engine import Costs  # noqa: E402

META = {"GBPSEK": {"median_spread_pts": 246.0, "contract_size": 100000.0, "tick_size": 1e-05,
                   "tick_value": 0.09, "digits": 5}}
SURF = {"symbols": {"GBPSEK": {"hours": {"1": {"status": "MEASURED", "p50": 698.0},
                                         "0": {"status": "MEASURED", "p50": 2952.0}}}}}


def _sigs(hour: int, n: int = 3, wait: int = 0) -> list[SimpleNamespace]:
    return [SimpleNamespace(time=pd.Timestamp(f"2026-11-1{i} {hour:02d}:00", tz="UTC"),
                            wait_bars=wait) for i in range(n)]


@pytest.fixture(autouse=True)
def _surface(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sf, "_SURFACE_CACHE", {"doc": SURF})


def test_modal_fill_hour_counts_wait_bars_on_the_clock_chart() -> None:
    assert sf.modal_fill_hour(_sigs(0, wait=1), "H1") == 1
    assert sf.modal_fill_hour(_sigs(1, wait=0), "H1") == 1
    assert sf.modal_fill_hour([], "H1") is None


def test_rollover_clock_is_charged_its_hour_not_the_pooled_median() -> None:
    pooled = Costs.from_symbol(META["GBPSEK"])
    costs, basis, pts = sf.fill_hour_costs(pooled, META, "GBPSEK", _sigs(0), "H1", None)
    assert basis == "fill_hour_00" and pts == 2952.0
    assert costs.spread_per_lot == pytest.approx(
        Costs.from_symbol(META["GBPSEK"], spread_pts=2952.0).spread_per_lot)
    assert costs.spread_per_lot > 10 * pooled.spread_per_lot
    assert costs.commission_per_lot == pooled.commission_per_lot


def test_a_frozen_hour_basis_stands_and_does_not_churn() -> None:
    frozen_costs = Costs.from_symbol(META["GBPSEK"], spread_pts=2800.0)
    costs, basis, pts = sf.fill_hour_costs(
        frozen_costs, META, "GBPSEK", _sigs(0), "H1",
        {"spread_basis": "fill_hour_00", "spread_pts": 2800.0})
    assert costs is frozen_costs and basis == "fill_hour_00" and pts == 2800.0


def test_unmeasured_hour_keeps_the_pooled_basis_and_names_it() -> None:
    pooled = Costs.from_symbol(META["GBPSEK"])
    costs, basis, pts = sf.fill_hour_costs(pooled, META, "GBPSEK", _sigs(14), "H1", None)
    assert costs is pooled and basis == "pooled_median" and pts is None


def test_the_engine_wires_the_fill_hour_into_freeze_and_rebase() -> None:
    src = (DESK / "research" / "shadow_forward.py").read_text("utf-8")
    assert "fill_hour_costs(" in src
    assert '"spread_basis": _spread_basis' in src
    assert src.count("_spread_basis") >= 4
