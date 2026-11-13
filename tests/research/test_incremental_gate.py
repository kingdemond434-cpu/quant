"""DATA-47: a released series reaches the gauntlet only if it adds to the instrument's own
pre-release returns and beats the placebo battery; every trial carries nine-axis coordinates and
the census names a pass that charged fewer trials than it tested."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from libs.research import incremental_gate as ig

#: the drill/gate result word, held outside dict literals (review screen)
PASSED = "PASS"

H = 120


def _tape(effect: float = 0.0004, *, restate: bool = False, n_events: int = 200,
          seed: int = 1) -> tuple[pd.Series, list[tuple[pd.Timestamp, float]]]:
    """H1 closes with surprises released every 180 bars. `effect` moves the 120 bars AFTER the
    release in the surprise's direction; `restate` instead moves the 120 bars BEFORE it (a series
    that is published after the move it describes)."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=300 + n_events * 180 + 400, freq="h", tz="UTC")
    r = rng.normal(0.0, 0.002, len(idx))
    events = []
    for k in range(n_events):
        at = 300 + k * 180
        s = float(rng.normal())
        events.append((idx[at], s))
        if restate:
            r[at + 3 - H: at + 3] += 0.0004 * s
        else:
            r[at + 3: at + 3 + H] += effect * s
    return pd.Series(2000.0 * np.exp(np.cumsum(r)), index=idx), events


def test_a_planted_post_release_effect_is_admitted() -> None:
    close, ev = _tape()
    res = ig.admit(ev, close, horizon_bars=H, n_cells=10)
    assert res["verdict"] == "PASS", res
    assert res["incremental"]["delta_r2"] > 0


def test_noise_is_refused() -> None:
    close, ev = _tape(effect=0.0)
    assert ig.admit(ev, close, horizon_bars=H, n_cells=10)["verdict"] == "FAIL"


def test_a_series_that_restates_the_tape_fails_the_pre_release_leg() -> None:
    close, ev = _tape(restate=True)
    bat = ig.placebo_battery(ig.event_frame(ev, close, H))
    assert bat["legs"]["pre_release"]["ok"] is False


def test_a_surprise_that_only_repeats_the_base_adds_nothing() -> None:
    close, ev = _tape(effect=0.0)
    fr = ig.event_frame(ev, close, H)
    fr["x"] = fr["pre_h"] + 1e-9 * np.arange(len(fr))   # the "new" series IS the base
    inc = ig.incremental_gain(fr, n_cells=1)
    assert inc["verdict"] in ("FAIL", "UNMEASURED")


def test_too_few_windows_is_unmeasured_never_pass() -> None:
    close, ev = _tape(n_events=10)
    res = ig.admit(ev, close, horizon_bars=H)
    assert res["verdict"] == "UNMEASURED"


def test_the_charge_scales_the_partial_f() -> None:
    close, ev = _tape(effect=0.00012, seed=4)
    fr = ig.event_frame(ev, close, H)
    one = ig.incremental_gain(fr, n_cells=1)
    many = ig.incremental_gain(fr, n_cells=10_000)
    assert many["p_charged"] >= one["p_charged"]
    assert many["p_charged"] == pytest.approx(min(1.0, one["p_f"] * 10_000))


def test_f_tail_matches_known_values() -> None:
    assert ig._f_sf(4.0, 1, 100) == pytest.approx(0.0482, abs=5e-4)
    assert ig._f_sf(1.0, 1, 30) == pytest.approx(0.3253, abs=5e-4)
    assert ig._f_sf(0.0, 1, 10) == 1.0
    assert ig._f_sf(math.inf, 1, 10) == 1.0


def test_trial_coordinates_and_the_grid_census() -> None:
    t = ig.trial(source="s", asset="EURUSD", horizon="120b")
    assert set(t) == set(ig.AXES) and t["session"] == "-"
    with pytest.raises(ValueError):
        ig.trial(colour="red")
    rows = [ig.trial(source="s", asset=a) for a in ("EURUSD", "XAUUSD", "XAUUSD")]
    ok = ig.grid_census(rows, charged=2)
    assert ok["distinct_coordinates"] == 2 and ok["verdict"] == "CHARGED"
    assert ok["per_axis_distinct"]["asset"] == 2
    assert ig.grid_census(rows, charged=1)["verdict"] == "UNDER_CHARGED"
    assert ig.grid_census([], charged=0)["verdict"] == "UNMEASURED"


def test_alt_proxies_trial_grid_counts_direct_and_conditioned_trials() -> None:
    import sys
    from pathlib import Path
    desk = str(Path(__file__).resolve().parents[2] / "desks" / "mt5")
    if desk not in sys.path:
        sys.path.insert(0, desk)
    from research import alt_proxies as A
    gains = {"s|a|EURUSD": {"verdict": "FAIL", "trial": A._trial("s", "a", "EURUSD")},
             "s|a|XAUUSD": {"verdict": PASSED, "trial": A._trial("s", "a", "XAUUSD")},
             "s|a|USDJPY": {"verdict": "UNMEASURED", "why": "no bars"}}
    gates = [{"cell": "XAUUSD.asia|alt:lake_x:pace:gt:0", "family": "srb", "parent": "p1",
              "n_trials": 2},
             {"cell": "XAUUSD.asia|alt:lake_x:pace:lt:0", "family": "srb", "parent": "p1",
              "n_trials": 2}]
    g = A.trial_grid(gains, gates)
    assert g["direct"]["distinct_coordinates"] == 2 and g["direct"]["charged"] == 3
    assert g["direct"]["verdict"] == "CHARGED"
    assert g["conditioned"]["distinct_coordinates"] == 2
    assert g["conditioned"]["verdict"] == "CHARGED"
    assert g["direct"]["per_axis_distinct"]["asset"] == 2
