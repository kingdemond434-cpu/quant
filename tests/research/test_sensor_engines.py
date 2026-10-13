"""The gain contract every world-sensor engine reports: real gains pass, shuffled ones do not,
small samples are UNMEASURED, and the lake series and cell door keep the PIT stamp."""
from __future__ import annotations

import numpy as np
import pandas as pd

from libs.research import sensor_engines as se


def _regime_world(n: int = 1500, seed: int = 3) -> tuple[np.ndarray, np.ndarray]:
    """A persistent state; the base cell earns only while it holds."""
    rng = np.random.default_rng(seed)
    state = np.zeros(n, dtype=bool)
    for i in range(1, n):
        state[i] = state[i - 1] if rng.random() < 0.97 else not state[i - 1]
    pay = rng.normal(0.0, 0.01, n) + np.where(state, 0.0025, -0.0008)
    return pay, state


def test_a_real_gate_shows_gain_and_a_random_one_does_not() -> None:
    pay, state = _regime_world()
    got = se.gated_gain(pay, state, engine="t", cards=["X"], falsifier="f")
    assert got["verdict"] == se.GAIN and got["gain"] > 0 and got["null_p"] < 0.05
    rng = np.random.default_rng(9)
    noise = rng.random(pay.size) < 0.5
    bad = se.gated_gain(pay, noise, engine="t", cards=["X"], falsifier="f")
    assert bad["verdict"] == se.NO_GAIN


def test_a_gate_that_is_only_the_control_fails_inside_its_strata() -> None:
    pay, state = _regime_world()
    got = se.gated_gain(pay, state, engine="t", cards=["X"], falsifier="f",
                        strata=state.astype(int))
    assert got["verdict"] == se.NO_GAIN and "strata" in got["why"]


def test_small_samples_are_unmeasured_never_zero() -> None:
    pay, state = _regime_world(100)
    got = se.gated_gain(pay, state, engine="t", cards=["X"], falsifier="f")
    assert got["verdict"] == se.UNMEASURED


def test_forecast_gain_and_monotone_gain() -> None:
    rng = np.random.default_rng(5)
    truth = rng.gamma(2.0, 1.0, 600)
    good = truth + rng.normal(0, 0.3, 600)
    naive = np.full(600, truth.mean())
    got = se.forecast_gain(truth, good, naive, engine="t", cards=["Y"], falsifier="f",
                           baseline="mean")
    assert got["verdict"] == se.GAIN and got["relative_reduction"] > 0.5
    worse = se.forecast_gain(truth, naive, good, engine="t", cards=["Y"], falsifier="f",
                             baseline="good")
    assert worse["verdict"] == se.NO_GAIN
    x = rng.normal(size=300)
    mono = se.monotone_gain(x, 0.5 * x + rng.normal(size=300), engine="t", cards=["Z"],
                            falsifier="f")
    assert mono["verdict"] == se.GAIN and mono["value"] > 0.3


def test_lake_series_keeps_the_pit_stamp_and_the_conditioner_reads_it(tmp_path) -> None:
    rows = [{"available_time": f"2026-01-{d:02d}T01:00:00+00:00", "vrp_rank": d / 31}
            for d in range(1, 31)] + [{"vrp_rank": 9.9}]
    out = se.write_lake_series("ws_test", rows, root=tmp_path)
    assert out["rows"] == 30 and out["dropped_without_available_time"] == 1
    df = pd.read_csv(tmp_path / "ws_test.csv")
    assert {"available_time", "vrp_rank", "source_id"} <= set(df.columns)
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "desks" / "mt5"))
    from mt5desk.family_exogenous_conditioner import conditioner
    s = conditioner("ws_test", "vrp_rank", "delta", root=tmp_path)
    assert s is not None and len(s) == 29


def test_cell_door_dry_run_and_rollup(tmp_path) -> None:
    got = se.emit_conditioner_cells("ws_test", ["a", "b"], ["US500"], mechanism="m",
                                    falsifier="f", generator="g", sides=(1, -1), dry_run=True,
                                    data_source="mt5:bars")
    assert got["emitted"] == 2 * 1 * 3 * 2
    # the terms gate fails closed: an unnamed source and a held source emit nothing, and FRED
    # is held from fitted models (ruling on prohibition (j), 2026-10-07)
    for src in (None, "yahoo:cboe_indices:^VIX", "fred:DGS10"):
        held = se.emit_conditioner_cells("ws_test", ["a"], ["US500"], mechanism="m",
                                         falsifier="f", generator="g", dry_run=True,
                                         data_source=src)
        assert held["emitted"] == 0 and held["status"] == "HELD_TERMS"
    se.publish("eng", [se.contract(engine="eng", cards=["QG1"], metric="m", baseline="b",
                                   falsifier="f", value=None, baseline_value=None, n=0)],
               root=tmp_path)
    doc = se.rollup(root=tmp_path, out=tmp_path / "R.json",
                    cards={"QG1": {"title": "t"}, "QG2": {"title": "u"}})
    assert doc["cards"]["QG1"]["best_verdict"] == se.UNMEASURED
    assert doc["cards"]["QG2"]["contracts"] == 0
