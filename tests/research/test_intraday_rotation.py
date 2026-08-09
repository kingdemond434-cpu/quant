"""The intraday rotation engine's honesty tests — Part 3 of the spec, made mechanical.

The spec's own warning: "if the backtest comes back with a 90% win rate matching the source
book, that is evidence of a bug — most likely lookahead in the range-boundary calculation or
optimistic limit fills. Check those first." These tests check them FIRST, on synthetic data
where the truth is known, so the real run's numbers arrive already-audited.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.research.intraday_rotation import (
    ConfigResult,
    Trade,
    atr,
    bootstrap_sizing,
    deflated_sharpe,
    efficiency_ratio,
    expectancy,
    half_kelly,
    regimes,
    run_config,
    wilson_ci,
)


def _panel(t: int = 6000, seed: int = 0, drift: float = 0.0) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    ret = rng.normal(drift, 0.002, t)
    close = 100.0 * np.cumprod(1 + ret)
    spread = np.abs(rng.normal(0, 0.001, t)) + 5e-4
    high = close * (1 + spread)
    low = close * (1 - spread)
    opn = np.concatenate([[close[0]], close[:-1]])
    times = 1_700_000_000_000.0 + np.arange(t) * 300_000.0
    return {"open": opn, "high": high, "low": low, "close": close, "open_time": times,
            "volume": np.full(t, 1e6), "quote_volume": np.full(t, 1e8)}


class TestNoLookahead:
    def test_future_bars_cannot_change_present_entries(self) -> None:
        """THE PART-3 PROBE. Replace everything after bar T with a different world; every entry
        decision at or before T must be identical. If it is not, some boundary/regime quantity
        is reading the future."""
        d1 = _panel(seed=1)
        d2 = {k: v.copy() for k, v in d1.items()}
        cut = 3000
        alt = _panel(seed=99)
        for k in ("open", "high", "low", "close"):
            d2[k][cut:] = alt[k][cut:]
        r1 = run_config(d1, symbol="X", strategy="rotation", n=48, k=0, m=24, variant="r2",
                        stop=cut)
        r2 = run_config(d2, symbol="X", strategy="rotation", n=48, k=0, m=24, variant="r2",
                        stop=cut)
        e1 = [(t.entry_i, t.side, round(t.entry_px, 10)) for t in r1.trades if t.exit_i < cut]
        e2 = [(t.entry_i, t.side, round(t.entry_px, 10)) for t in r2.trades if t.exit_i < cut]
        assert e1 == e2, "entries before the cut changed when only the future changed"

    def test_boundary_excludes_the_current_bar(self) -> None:
        """A bar making a new N-high must not see itself as 'at the boundary' of a range that
        includes it — that is the classic rotation lookahead named in the spec."""
        from libs.research.intraday_rotation import _shifted_extrema
        high = np.arange(100, dtype="float64")
        low = high - 1
        hi, _lo = _shifted_extrema(high, low, 10)
        assert hi[50] == high[49], "boundary includes the current bar"


class TestConservatism:
    def test_stop_beats_target_inside_one_bar(self) -> None:
        """When one bar spans both stop and target, the STOP must fill — the pessimistic order
        is the only one that cannot flatter the backtest."""
        d = _panel(seed=3)
        i = 4000
        d["low"][i + 1] = d["close"][i] * 0.90     # both stop and target inside bar i+1
        d["high"][i + 1] = d["close"][i] * 1.10
        from libs.research.intraday_rotation import _resolve
        t = _resolve(1, i, float(d["close"][i]), float(d["close"][i] * 0.99),
                     d["high"], d["low"], d["close"], float(d["close"][i] * 1.05),
                     "r2", 24, d["open_time"], np.empty(0), np.empty(0), "RANGE", 5.0)
        assert t is not None and t.exit_reason == "stop"

    def test_pure_noise_does_not_return_the_source_books_win_rate(self) -> None:
        """On driftless noise, net of costs, the machinery must NOT manufacture a 90% hit rate.
        (It may trade little — the location filter is strict — but what it takes must lose or
        break even after costs on average across seeds.)"""
        rs = []
        for seed in range(6):
            d = _panel(t=8000, seed=seed)
            for strat in ("rotation", "continuation"):
                c = run_config(d, symbol="X", strategy=strat, n=48, k=12, m=48, variant="r2")
                rs.extend(c.r_series().tolist())
        r = np.asarray(rs)
        if len(r) >= 30:
            assert float(np.mean(r > 0)) < 0.75, "suspiciously high hit rate on pure noise"
            assert float(np.mean(r)) < 0.15, "positive expectancy manufactured from noise"


class TestPrimitives:
    def test_regimes_classify_trend_and_chop(self) -> None:
        t = 2000
        trend = 100 * np.cumprod(1 + np.full(t, 0.001))
        rng = np.random.default_rng(5)
        chop = 100 + np.cumsum(rng.normal(0, 1, t)) * 0.001  # tiny scale: mean-reverting-ish
        chop = 100 + 0.5 * np.sin(np.arange(t) / 5.0) + rng.normal(0, 0.05, t)
        assert np.mean(regimes(trend)[100:] == 1) > 0.9
        assert np.mean(regimes(chop)[100:] == 0) > 0.5

    def test_atr_and_er_shapes(self) -> None:
        d = _panel(t=500)
        assert np.isnan(atr(d["high"], d["low"], d["close"])[:19]).all()
        er = efficiency_ratio(d["close"])
        assert np.nanmax(er) <= 1.0 + 1e-9

    def test_wilson_interval_covers_the_point(self) -> None:
        lo, hi = wilson_ci(10, 11)
        assert lo < 10 / 11 < hi and lo > 0.55, (lo, hi)   # n=11 at 91%: CI floor near 0.6

    def test_sizing_bootstrap_streak_arithmetic_matches_the_spec(self) -> None:
        """The spec fixes: at 4% risk a 10-loss streak = 33.5% DD, a 20-loss = 55.6%."""
        assert abs(1 - 0.96 ** 10 - 0.335) < 0.005
        assert abs(1 - 0.96 ** 20 - 0.556) < 0.005
        r = np.concatenate([np.full(30, 1.0), np.full(10, -1.0)])
        rows = bootstrap_sizing(r, risk_fracs=(0.04,), n_paths=200)
        assert rows and rows[0]["longest_loss_streak_real"] == 10
        assert abs(rows[0]["streak_implied_dd"] - 0.335) < 0.01

    def test_half_kelly_zero_on_negative_edge(self) -> None:
        rng = np.random.default_rng(9)
        assert half_kelly(rng.normal(-0.2, 1.0, 300))["half_kelly"] == 0.0

    def test_deflated_sharpe_punishes_config_count(self) -> None:
        one = deflated_sharpe(0.1, 250, 1)
        many = deflated_sharpe(0.1, 250, 540)
        assert many < one

    def test_result_r_series_roundtrip(self) -> None:
        c = ConfigResult("X", "rotation", 48, 0, 24, "r2",
                         trades=[Trade(1, 2, 1, 100.0, 101.0, 99.0, 1.0, 0.01, "RANGE",
                                       "target", 12)])
        assert c.r_series().tolist() == [1.0]


def test_expectancy_empty_is_zero_not_crash() -> None:
    assert expectancy(np.empty(0))["n"] == 0
