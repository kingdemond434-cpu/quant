"""The first family whose ENTRY CONDITION is an execution state (Tier-1 audit G8).

Execution is the most measured thing on the desk and the least discovered: the surfaces, the
fill model, AlphaCapture and markout all exist, `microstructure_miner` ran 83 tests and proposed
0 cells, and no registered family's signal was an execution state. What is pinned: the family
refuses without the venue's surface; the eligible windows come from the surface; the percentiles
that fire an entry are computed from the bars' own book over the PREVIOUS bars only, so a bar is
never ranked against itself or anything later; the sweep and the gauntlet rebuild the same map; and it is registered, executable and off the charts that carry no
stamp hour.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import orthogonal_sweep as osw  # noqa: E402  (the module family_inputs resolves)

from mt5desk import executables, family_inputs  # noqa: E402
from mt5desk import families_orthogonal as fo  # noqa: E402

FAM = "execution_state"
CHEAP = (1, 9)          # (weekday, hour) the venue quotes cheap and deep
DEAR = (3, 21)          # ... and dear and thin


def _bars(n: int = 6000, seed: int = 5) -> pd.DataFrame:
    """Hourly bars whose SPREAD depends on the (weekday, hour) bucket, as a venue's does."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    close = 100 + np.cumsum(rng.normal(0, 0.25, n))
    o = np.concatenate([[100.0], close[:-1]])
    spread = np.full(n, 20.0)
    vol = np.full(n, 100.0)
    for i, t in enumerate(idx):
        if (t.dayofweek, t.hour) == CHEAP:
            spread[i], vol[i] = 5.0, 900.0
        elif (t.dayofweek, t.hour) == DEAR:
            spread[i], vol[i] = 60.0, 20.0
    return pd.DataFrame({"open": o, "high": np.maximum(o, close) + 0.4,
                         "low": np.minimum(o, close) - 0.4, "close": close,
                         "tick_volume": vol, "spread": spread}, index=idx)


def _surface() -> dict:
    return {"cheapest_deepest_windows": [f"dow{CHEAP[0]}:h{CHEAP[1]}"],
            "dearest_thinnest_windows": [f"dow{DEAR[0]}:h{DEAR[1]}"],
            "spread_median": 20.0, "spread_p95": 60.0}


# --------------------------------------------------------------------- registered and wired
def test_the_family_is_registered_executable_and_declares_its_input() -> None:
    assert FAM in fo.ORTHOGONAL_FAMILIES
    need, source = fo.FAMILY_INPUTS[FAM]
    assert "surface" in need and source.endswith("MICROSTRUCTURE_SURFACES.json")
    assert executables.resolve_family(FAM) is fo.ORTHOGONAL_FAMILIES[FAM]
    assert executables.population_of(FAM) == "orthogonal"
    assert executables.gateway_can_execute(FAM, "H1")


def test_it_is_declared_off_the_charts_that_carry_no_stamp_hour() -> None:
    assert fo.timeframe_refusal(FAM, "H4") and fo.timeframe_refusal(FAM, "D1")
    for tf in ("M1", "M5", "M15", "M30", "H1"):
        assert fo.timeframe_refusal(FAM, tf) is None, tf


def test_the_sweep_passes_the_surface_and_the_gauntlet_rebuilds_it(monkeypatch, tmp_path
                                                                   ) -> None:
    """A family declaring a non-price input that the sweep never passes returns [] on every
    symbol and reads as a data gap -- the defect `pca_residual` cost 297 rows."""
    import ast
    tree = ast.parse((_DESK / "research" / "orthogonal_sweep.py").read_text("utf-8"))
    kwargs_map = next(
        {k.value: {kk.value for kk in v.keys} for k, v in zip(node.value.keys,
                                                              node.value.values, strict=True)}
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign) and node.targets
        and getattr(node.targets[0], "id", "") == "kwargs_by_family")
    assert kwargs_map[FAM] == {"surface"}

    path = tmp_path / "MICROSTRUCTURE_SURFACES.json"
    path.write_text(json.dumps({"generated_at": "2026-09-08T00:00:00Z",
                                "symbols": {"EURUSD": _surface()}}), "utf-8")
    monkeypatch.setattr(osw, "MICROSTRUCTURE_SURFACES", path)
    osw._surfaces.cache_clear()
    assert osw._surface_for("EURUSD") == _surface()
    assert osw._surface_for("GBPUSD") is None

    got, why = family_inputs.resolve("EURUSD", FAM, {}, None)
    assert got is not None and got["surface"] == _surface(), why
    missing, why = family_inputs.resolve("GBPUSD", FAM, {}, None)
    assert missing is None and "no microstructure surface for GBPUSD" in why
    osw._surfaces.cache_clear()
    # The vintage identifies the map and is not an argument any family takes.
    assert "surface_generated_at" in family_inputs.IDENTITY_KEYS
    assert family_inputs.strip_identity_keys(FAM, {"surface_generated_at": "x", "mode": "a"}) \
        == {"mode": "a"}


# --------------------------------------------------------------------- the refusals
@pytest.mark.parametrize("kwargs", [
    {"surface": None},
    {"surface": {}},
    {"surface": {"cheapest_deepest_windows": []}},          # a surface naming no window
    {"surface": _surface(), "mode": "sideways"},            # an unknown mode
])
def test_it_refuses_rather_than_degrading_into_a_momentum_sleeve(kwargs) -> None:
    assert fo.family_execution_state(_bars(), **kwargs) == []


def test_bars_with_no_spread_column_are_refused() -> None:
    d = _bars().drop(columns=["spread"])
    assert fo.family_execution_state(d, surface=_surface()) == []


# --------------------------------------------------------------------- the mechanism
def test_every_entry_falls_in_a_window_the_surface_named() -> None:
    sigs = fo.family_execution_state(_bars(), surface=_surface(), mode="cheap_deep")
    assert sigs, "the cheap-deep window must produce entries on bars that moved"
    for s in sigs:
        t = pd.Timestamp(s.time)
        assert (t.dayofweek, t.hour) == CHEAP, t
        assert s.tag == "execution_state:cheap_deep"
        assert s.trigger is None and s.wait_bars == 1


def test_the_two_modes_take_opposite_sides_of_their_own_windows() -> None:
    d = _bars()
    cheap = fo.family_execution_state(d, surface=_surface(), mode="cheap_deep")
    dear = fo.family_execution_state(d, surface=_surface(), mode="dear_thin")
    assert cheap and dear
    assert {(pd.Timestamp(s.time).dayofweek, pd.Timestamp(s.time).hour) for s in dear} == {DEAR}
    ret = d["close"].diff()
    for s in cheap:
        assert s.side == (1 if float(ret.loc[pd.Timestamp(s.time)]) > 0 else -1)
    for s in dear:
        assert s.side == (-1 if float(ret.loc[pd.Timestamp(s.time)]) > 0 else 1)


def test_the_windows_can_be_recovered_from_the_maps_when_the_lists_are_absent() -> None:
    spreads = {f"{d}:{h}": (5.0 if (d, h) == CHEAP else 40.0)
               for d in range(5) for h in range(24)}
    acts = {f"{d}:{h}": (900.0 if (d, h) == CHEAP else 50.0)
            for d in range(5) for h in range(24)}
    got = fo._surface_windows({"spread_by_dow_hour": spreads, "activity_by_dow_hour": acts},
                              "cheap_deep", 0.30, 0.70)
    assert CHEAP in got
    assert fo._surface_windows({"spread_by_dow_hour": {}, "activity_by_dow_hour": {}},
                               "cheap_deep", 0.3, 0.7) == set()


# --------------------------------------------------------------------- point in time
def test_a_bar_is_ranked_against_bars_that_had_already_printed() -> None:
    idx = pd.date_range("2024-01-01", periods=200, freq="1h", tz="UTC")
    rising = pd.Series(np.arange(200, dtype=float), index=idx)
    pct = fo._trailing_percentile(rising, 24)
    # A strictly rising series: every ranked bar is above all 24 that preceded it.
    assert pct.iloc[:24].isna().all(), "no rank before the window has filled"
    assert set(np.round(pct.dropna().to_numpy(), 6)) == {1.0}
    falling = pd.Series(np.arange(200, 0, -1, dtype=float), index=idx)
    assert set(np.round(fo._trailing_percentile(falling, 24).dropna().to_numpy(), 6)) == {0.0}
    # And a series shorter than the window has no ranks at all, rather than a fabricated one.
    assert fo._trailing_percentile(rising.iloc[:10], 24).isna().all()


def test_rewriting_later_bars_cannot_move_an_earlier_signal() -> None:
    d = _bars()
    cut = 4500
    base = [s for s in fo.family_execution_state(d, surface=_surface())
            if pd.Timestamp(s.time) <= d.index[cut - 1]]
    assert base, "the invariant would be vacuous"
    dirty = d.copy()
    rng = np.random.default_rng(99)
    tail = float(d["close"].iloc[cut - 1]) + np.cumsum(rng.normal(0, 3.0, len(d) - cut))
    for col in ("open", "high", "low", "close"):
        dirty.iloc[cut:, dirty.columns.get_loc(col)] = tail
    dirty.iloc[cut:, dirty.columns.get_loc("spread")] = 1.0
    dirty.iloc[cut:, dirty.columns.get_loc("tick_volume")] = 5000.0
    after = [s for s in fo.family_execution_state(dirty, surface=_surface())
             if pd.Timestamp(s.time) <= d.index[cut - 1]]
    key = lambda sigs: sorted((pd.Timestamp(s.time).value, s.side, round(s.stop, 6),  # noqa: E731
                               round(s.target, 6)) for s in sigs)
    assert key(base) == key(after), "a signal moved when only LATER bars changed"
