"""Event-driven refits for the learned miners: regime breaks (GAP_MAP row 29, first built in
PR #406) and decay of the model's own out-of-sample edge (row 35).

The CN shops refit when the regime moves or the edge decays, not on a calendar. A regime break is
a change of the panel's volatility state against its own trailing year, read from rows <= t. A
decay alarm is a one-sided CUSUM on the model's own cross-sectional IC, each row's IC read only
once its target is known, tuned to detect the edge going to zero at a declared false-alarm run
length. These tests pin what makes both honest: causality, a planted change is found, the clock
schedule is unchanged when no event is asked for, a model with no edge never "decays", the
threshold delivers its declared ARL, and the future never changes a past prediction.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
_DESK = _ROOT / "desks" / "mt5"
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.models import learned_propagation as LP  # noqa: E402

WF = {"min_train": 300, "refit_every": 50, "window": 600}


def _panel(ret: np.ndarray) -> LP.Panel:
    dates = pd.bdate_range("2019-01-01", periods=ret.shape[0], tz="UTC")
    return LP.Panel(dates, [f"S{j:02d}" for j in range(ret.shape[1])], ret,
                    np.full(ret.shape, 5e-5))


def _vol_shift(t_n: int = 1200, at: int = 700, seed: int = 4) -> np.ndarray:
    """Quiet panel that turns four times as volatile at row `at`."""
    rng = np.random.default_rng(seed)
    r = rng.normal(0, 0.005, (t_n, 8))
    r[at:] *= 4.0
    return r


def test_a_planted_regime_change_is_found_where_it_happened() -> None:
    br = LP.regime_breaks(LP.design(_panel(_vol_shift())))
    assert br and any(700 <= b <= 760 for b in br), br


def test_a_break_is_read_from_the_past_only() -> None:
    ret = _vol_shift()
    full = LP.regime_breaks(LP.design(_panel(ret)))
    for cut in (650, 720, 900):
        part = LP.regime_breaks(LP.design(_panel(ret[:cut])))
        assert part == tuple(b for b in full if b < cut), cut


def test_the_clock_schedule_is_unchanged_without_breaks() -> None:
    assert LP.refit_points(1000, 300, 50) == list(range(300, 1000, 50))
    seen: list[tuple[int, int]] = []

    def fit(lo: int, k: int, _prev: Any) -> int:
        seen.append((lo, k))
        return 1

    LP.walk_forward(1000, 2, fit, lambda m, a, b: np.zeros((b - a, 2)), **WF)
    assert seen == [(max(0, k - 600), k) for k in range(300, 1000, 50)]


def test_a_break_adds_a_refit_and_trains_on_the_new_regime() -> None:
    seen: list[tuple[int, int]] = []

    def fit(lo: int, k: int, _prev: Any) -> int:
        seen.append((lo, k))
        return 1

    preds = LP.walk_forward(1000, 2, fit, lambda m, a, b: np.full((b - a, 2), float(a)),
                            breaks=(420,), **WF)
    ks = [k for _lo, k in seen]
    assert 421 in ks and set(range(300, 1000, 50)) <= set(ks)
    for lo, k in seen:
        if k > 420:
            assert lo == max(k - 600, min(420, k - LP.POST_BREAK_MIN))
    assert preds[421, 0] == 421.0 and preds[420, 0] == 400.0     # the break's refit takes over


def test_perturbing_the_future_never_changes_a_past_regime_prediction() -> None:
    ret = _vol_shift(t_n=900, at=500)
    t0 = 640
    fut = ret.copy()
    fut[t0 + 1:] = np.random.default_rng(99).normal(0, 0.05, fut[t0 + 1:].shape)
    cfg = next(c for c in LP.GNN_GRID if c.get("refit") == "regime")
    p1 = LP.predictions(LP.design(_panel(ret)), "gnn", cfg, **WF)
    p2 = LP.predictions(LP.design(_panel(fut)), "gnn", cfg, **WF)
    assert np.isfinite(p1[WF["min_train"]:t0 + 1]).any()
    np.testing.assert_allclose(p1[:t0 + 1], p2[:t0 + 1], equal_nan=True)


def test_every_model_charges_one_regime_and_one_decay_configuration_and_refuses_unknown_modes(
) -> None:
    import learned_miners as LM
    from mt5desk import families_orthogonal as FO
    for spec in LM.MINERS.values():
        grid = spec["grid"]
        assert grid[0].get("refit", "clock") == "clock"           # the primary is unchanged
        for mode in ("regime", "decay"):
            hit = [c for c in grid if c.get("refit") == mode]
            assert len(hit) == 1, (spec["family"], mode)
            assert {k: v for k, v in hit[0].items() if k != "refit"} == grid[0]
        fn = FO.ORTHOGONAL_FAMILIES[spec["family"]]
        frame = pd.DataFrame({"close": [1.0]})
        assert fn(frame, symbol="EURUSD", peer_symbols=["GBPUSD"], refit="weekly") == []


# ------------------------------------------------------------------------------- decay (row 35)
def test_cusum_threshold_delivers_its_declared_false_alarm_run_length() -> None:
    rng = np.random.default_rng(7)
    mu0, sd, arl0 = 0.03, 0.3, 200.0
    mon0 = LP.DecayMonitor.from_history(rng.normal(mu0, sd, 5000), arl0=arl0)
    assert mon0 is not None
    runs = []
    for _ in range(300):
        m = LP.DecayMonitor(mu0=mon0.mu0, sigma=mon0.sigma, kappa=mon0.kappa, h=mon0.h)
        for t in range(20 * int(arl0)):
            if m.update(t, float(rng.normal(mu0, sd))):
                runs.append(t + 1)
                break
    assert 0.6 * arl0 < float(np.mean(runs)) < 1.6 * arl0, np.mean(runs)


def test_a_model_that_never_had_an_edge_cannot_decay() -> None:
    rng = np.random.default_rng(3)
    assert LP.DecayMonitor.from_history(rng.normal(-0.01, 0.3, 500)) is None
    assert LP.DecayMonitor.from_history(rng.normal(0.05, 0.3, LP.DECAY_REF_MIN - 1)) is None


def _edge_then_noise(t_n: int, n: int, die: int, seed: int = 11) -> tuple[np.ndarray, Any]:
    """Targets y and a predictor whose rows < `die` carry a strong edge on y and whose later rows
    are pure noise -- an edge that decays at row `die`."""
    rng = np.random.default_rng(seed)
    y = rng.normal(0, 1, (t_n, n))
    noise = rng.normal(0, 1, (t_n, n))

    def predict(_m: Any, a: int, b: int) -> np.ndarray:
        out = noise[a:b].copy()
        live = np.arange(a, b) < die
        out[live] += 0.6 * y[a:b][live]
        return out
    return y, predict


def test_a_decayed_edge_triggers_a_refit_soon_after_the_decay() -> None:
    t_n, n, die = 1400, 12, 800
    y, predict = _edge_then_noise(t_n, n, die)
    log: list[dict[str, Any]] = []
    LP.walk_forward(t_n, n, lambda lo, k, prev: 1, predict, decay_y=y, log=log, **WF)
    decays = [e for e in log if e["trigger"] == "decay"]
    after = [e for e in decays if e["row"] > die]
    assert after and after[0]["row"] < die + 60, decays
    # before the decay, false alarms run at the declared rate (ARL0 rows), not every few rows
    assert len([e for e in decays if e["row"] <= die]) <= 2 * (die - 450) / LP.DECAY_ARL0 + 1
    # trains from the change-point estimate, never on fewer than POST_BREAK_MIN rows
    first = after[0]
    assert first["row"] - first["train_from"] >= LP.POST_BREAK_MIN
    assert first["train_from"] >= first["row"] - WF["window"]
    # the clock schedule is all still there
    assert set(range(300, t_n, 50)) <= {e["row"] for e in log}


def test_a_stable_edge_alarms_at_the_declared_rate_only() -> None:
    t_n, n = 3000, 12
    y, predict = _edge_then_noise(t_n, n, die=10 ** 9)
    log: list[dict[str, Any]] = []
    LP.walk_forward(t_n, n, lambda lo, k, prev: 1, predict, decay_y=y, log=log, **WF)
    alarms = len([e for e in log if e["trigger"] == "decay"])
    assert alarms <= 2 * (t_n - 450) / LP.DECAY_ARL0 + 1, alarms


def test_without_decay_targets_the_walk_is_the_clock_walk() -> None:
    t_n, n = 900, 4
    _y, predict = _edge_then_noise(t_n, n, die=600)
    a = LP.walk_forward(t_n, n, lambda lo, k, prev: 1, predict, **WF)
    log: list[dict[str, Any]] = []
    LP.walk_forward(t_n, n, lambda lo, k, prev: 1, predict, log=log, **WF)
    assert [e["row"] for e in log] == list(range(300, t_n, 50))
    assert np.isfinite(a[300:]).all()


def test_perturbing_the_future_never_changes_a_past_decay_prediction() -> None:
    ret = _vol_shift(t_n=900, at=500)
    t0 = 700
    fut = ret.copy()
    fut[t0 + 1:] = np.random.default_rng(5).normal(0, 0.05, fut[t0 + 1:].shape)
    cfg = next(c for c in LP.GNN_GRID if c.get("refit") == "decay")
    p1 = LP.predictions(LP.design(_panel(ret)), "gnn", cfg, **WF)
    p2 = LP.predictions(LP.design(_panel(fut)), "gnn", cfg, **WF)
    assert np.isfinite(p1[WF["min_train"]:t0 + 1]).any()
    np.testing.assert_allclose(p1[:t0 + 1], p2[:t0 + 1], equal_nan=True)


def test_unknown_refit_mode_is_refused_by_the_library() -> None:
    import pytest
    d = LP.design(_panel(_vol_shift(t_n=400)))
    with pytest.raises(ValueError):
        LP.predictions(d, "gnn", {"adjacency": "lead_lag", "layers": 1, "refit": "weekly"}, **WF)
