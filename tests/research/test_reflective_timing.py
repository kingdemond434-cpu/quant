"""Contract tests for libs/research/reflective_timing: gain where it should exist, none where it
should not, and no look-ahead."""
from __future__ import annotations

import numpy as np

from libs.research import reflective_timing as rt


def _regime(n: int, rng: np.random.Generator, d: int = 2) -> np.ndarray:
    s = np.zeros((n, d))
    for t in range(1, n):
        s[t] = 0.98 * s[t - 1] + rng.normal(0, 0.2, d)
    return s


def _planted(n: int = 3000, seed: int = 1, flip_at: int | None = None) -> tuple[np.ndarray, ...]:
    rng = np.random.default_rng(seed)
    s = _regime(n, rng)
    sign = np.where(s[:, 0] > 0, 1.0, -1.0)
    if flip_at is not None:
        sign[flip_at:] *= -1.0
    mu = 0.0015 * np.column_stack([sign, -sign, np.zeros(n)])
    f = mu + rng.normal(0, 0.006, (n, 3))
    return f, s


def _sharpe(res: rt.TimingResult) -> float:
    return float(rt.metrics(res.returns)["sharpe"])


def test_analog_timing_beats_equal_weight_on_planted_regimes() -> None:
    f, s = _planted()
    cfg = rt.TimingConfig(horizon=5)
    eq = _sharpe(rt.run_timing(f, s, cfg, method="equal"))
    an = _sharpe(rt.run_timing(f, s, cfg, method="analog"))
    re = _sharpe(rt.run_timing(f, s, cfg, method="reflect"))
    assert an > eq + 0.5
    assert re > eq + 0.5


def test_reflection_rescues_a_broken_analogue() -> None:
    # The regime/factor link reverses half way: history-based analogues are now wrong, and only
    # grading recent calls made in similar regimes can notice.
    f, s = _planted(n=4000, seed=3, flip_at=2000)
    cfg = rt.TimingConfig(horizon=5)
    an = rt.run_timing(f, s, cfg, method="analog")
    re = rt.run_timing(f, s, cfg, method="reflect")
    late = slice(2600, None)
    an_late = rt.metrics(an.returns[late])["sharpe"]
    re_late = rt.metrics(re.returns[late])["sharpe"]
    assert re_late > an_late
    assert min(re.multipliers[-50:]) < 1.0


def test_no_gain_on_pure_noise() -> None:
    # Falsification control: with no regime/factor link the mean Sharpe gain across independent
    # worlds is ~0 (measured 20 seeds: +0.002, sd 0.12). A leak would show as a positive mean.
    gains = []
    for seed in range(8):
        rng = np.random.default_rng(100 + seed)
        n = 2000
        s = _regime(n, rng)
        f = rng.normal(0, 0.006, (n, 4))
        cfg = rt.TimingConfig(horizon=5)
        eq = rt.metrics(rt.run_timing(f, s, cfg, method="equal").returns)["sharpe"]
        re = rt.metrics(rt.run_timing(f, s, cfg, method="reflect").returns)["sharpe"]
        gains.append(re - eq)
    assert abs(float(np.mean(gains))) < 0.12


def test_point_in_time_future_rows_cannot_move_past_weights() -> None:
    f, s = _planted(n=1500, seed=5)
    cfg = rt.TimingConfig(horizon=5)
    base = rt.run_timing(f, s, cfg, method="reflect").weights
    f2, s2 = f.copy(), s.copy()
    cut = 1000
    f2[cut:] = np.random.default_rng(99).normal(0, 0.05, f2[cut:].shape)
    s2[cut:] = -s2[cut:] * 3
    moved = rt.run_timing(f2, s2, cfg, method="reflect").weights
    # weights held on day d were decided at or before d-1, so rows <= cut are unchanged
    np.testing.assert_array_equal(base[: cut + 1], moved[: cut + 1])


def test_short_news_window_shrinks_tilt_on_shock() -> None:
    f, s = _planted(n=1500, seed=6)
    news = np.zeros(1500)
    news[::7] = 1.0
    news[1200:1203] = 40.0
    cfg = rt.TimingConfig(horizon=5)
    res = rt.run_timing(f, s, cfg, news=news, method="reflect")
    hit = [m for d, m in zip(res.decisions, res.multipliers, strict=True)
           if 1200 <= d.t <= 1202]
    calm = rt.run_timing(f, s, cfg, method="reflect")
    calm_m = [m for d, m in zip(calm.decisions, calm.multipliers, strict=True)
              if 1200 <= d.t <= 1202]
    assert hit and calm_m and hit[0] < calm_m[0]


def test_forward_sums_and_zscore_are_causal() -> None:
    x = np.arange(10, dtype=float).reshape(-1, 1)
    y = rt.forward_sums(x, 2)
    assert y[0, 0] == 1 + 2 and np.isnan(y[-1, 0])
    z = rt.zscore_pit(np.arange(30, dtype=float).reshape(-1, 1))
    z2 = rt.zscore_pit(np.r_[np.arange(25.0), [1e6] * 5].reshape(-1, 1))
    np.testing.assert_array_equal(z[:25], z2[:25])


def test_contract_builds_factors_and_states_point_in_time() -> None:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "desks" / "mt5" / "research"))
    import reflective_timing_contract as c

    rng = np.random.default_rng(2)
    syms = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF", "USDCAD",
            "AUDJPY", "NZDJPY", "CADJPY", "XAUUSD"]
    closes = np.exp(np.cumsum(rng.normal(0, 0.005, (400, len(syms))), axis=0))
    f, names, s = c.build(closes, syms)
    assert f.shape == (400, len(names)) and np.isfinite(f[70:]).all()
    closes2 = closes.copy()
    closes2[300:] *= 1.5
    f2, _, s2 = c.build(closes2, syms)
    np.testing.assert_array_equal(s[:300], s2[:300])
    np.testing.assert_array_equal(f[:300], f2[:300])
