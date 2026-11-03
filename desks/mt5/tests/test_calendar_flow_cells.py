"""calendar_flow_cells: every dated forced-flow kind reaches the intake, on its own instruments."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import calendar_flow_cells as cfc  # noqa: E402
from research import forced_flow_calendar as C  # noqa: E402


def test_the_grid_is_kind_x_mode_x_polarity_on_the_utc_clock() -> None:
    g = cfc.grid("gotobi_fix")
    assert len(g) == 4
    assert {(p["mode"], p["side"]) for p in g} == {(m, s) for m in cfc.MODES for s in (1, -1)}
    assert all(p["clock"] == "utc" and p["event_kind"] == "gotobi_fix" for p in g)


def test_targets_are_the_instruments_the_calendar_names_for_each_kind() -> None:
    lo, hi = date(2026, 1, 1), date(2026, 12, 31)
    t = cfc.kind_instruments(lo, hi)
    assert set(t) >= set(C.KINDS)
    for kind, syms in t.items():
        named = {s for e in C.events(lo, hi) if e.kind == kind for s in e.instruments}
        assert set(syms) == named


def _bars(n: int = 24 * 900) -> pd.DataFrame:
    idx = pd.date_range("2023-01-02", periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.normal(0, 0.2, n))
    return pd.DataFrame({"open": close, "high": close + 0.3, "low": close - 0.3,
                         "close": close, "volume": 1.0}, index=idx)


def test_seed_donates_once_per_identity_and_names_the_scarce(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cfc, "STATE", tmp_path / "state.json")
    from mt5desk import family_forced_flow as fff
    monkeypatch.setattr(fff, "to_bar_time", lambda ts: (ts, "CONVERTED", "test clock"))
    monkeypatch.setattr(cfc, "_bars", lambda sym, chart: _bars() if chart == "H1" else None)
    monkeypatch.setattr(cfc, "kind_instruments",
                        lambda lo, hi: {"fixing": ("USDJPY",), "ust_refunding": ("USDJPY",)})
    donated: list[list[dict]] = []
    from research import proposer_common as pc
    monkeypatch.setattr(pc, "donate", lambda src, rows, n: donated.append(rows) or
                        tmp_path / "d.json")
    monkeypatch.setattr(pc, "donation_counts", lambda: {"donated": len(donated[-1])})
    out = cfc.seed(budget_s=600, today=date(2026, 10, 13))
    fixing = out["cells_by_kind"]["fixing"]
    refunding = out["cells_by_kind"]["ust_refunding"]
    assert refunding.get("clears_floor", 0) == 0          # ~4 a year: observation-scarce
    assert refunding["observation_scarce"] == 4
    assert fixing["grid"] == 8 and fixing["no_bars"] == 4  # M15 absent here, counted
    assert fixing["clears_floor"] == 4                     # daily fix, 900 days of bars
    rows = donated[0]
    assert all(r["family"] == "forced_flow" and r["params"]["symbol"] == "USDJPY" for r in rows)
    assert all(r["params"]["clock"] == "utc" for r in rows)
    again = cfc.seed(budget_s=600, today=date(2026, 10, 13))
    assert again["candidates_this_pass"] == 0              # never donated twice
    assert not hasattr(fff.calendar_windows, "cache_info")  # the pass leaves no global behind
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["cells"]


def test_hourly_leg_is_wired() -> None:
    text = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("calendar_flow_cells"' in text
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["calendar_flow_cells"] == "prediction"
