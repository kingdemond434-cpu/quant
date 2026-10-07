"""DATA-33: breaks, half-life and own-lag residual -- and the future-corruption test for EVERY
single-input transform the forge offers.

The corruption test is the one that matters. A transform that reads one point past t produces a
plausible series and a spotless return curve; the only way to see it is to change what comes AFTER
t and watch whether anything stamped at or before t moves. Each transform is run twice, once on
the clean series and once with every value after the cut replaced by garbage, and the two outputs
must agree on every point stamped at or before the cut.
"""
from __future__ import annotations

import math
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "desks" / "mt5"), str(ROOT / "desks" / "mt5" / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import representations as R  # noqa: E402


def _series(values: list[float], dataset: str = "ds") -> R.Series:
    base = datetime(2025, 1, 1, tzinfo=UTC)
    pts = tuple(R.Point(available_time=(base + timedelta(days=i)).isoformat(),
                        period_time=(base + timedelta(days=i)).isoformat(), value=v)
                for i, v in enumerate(values))
    return R.Series(series_id=f"raw:{dataset}", points=pts, dataset=dataset, region="US",
                    information_type="macro_state")


def _ar1(n: int, phi: float, *, seed: int = 7, mu: float = 0.0) -> list[float]:
    rng = random.Random(seed)
    x = [mu]
    for _ in range(n - 1):
        x.append(mu + phi * (x[-1] - mu) + rng.gauss(0.0, 1.0))
    return x


def test_a_mean_shift_is_flagged_and_dated_and_a_stationary_window_mostly_is_not() -> None:
    rng = random.Random(3)
    values = [rng.gauss(0.0, 1.0) for _ in range(120)] + [rng.gauss(4.0, 1.0) for _ in range(60)]
    flag = R.structural_break(_series(values), window=60, output="flag")
    stat = R.structural_break(_series(values), window=60, output="stat")
    age = R.structural_break(_series(values), window=60, output="age")
    by_t = {p.available_time: p.value for p in flag.points}
    times = [p.available_time for p in _series(values).points]
    before = [by_t[t] for t in times[20:115] if t in by_t]
    after = [by_t[t] for t in times[140:175] if t in by_t]
    assert sum(before) / len(before) < 0.25, "a stationary window must rarely cross the 5% bar"
    assert sum(after) / len(after) > 0.9, "a 4-sd mean shift inside the window must be flagged"
    assert max(p.value for p in stat.points) > R.BREAK_CRITICAL
    assert age.points and age.points[-1].value >= 0.0
    assert flag.series_id != stat.series_id != age.series_id


def test_age_is_absent_until_a_first_break_rather_than_infinitely_old() -> None:
    flat = R.structural_break(_series([1.0] * 80), window=40, output="age")
    assert flat.points == ()
    with pytest.raises(ValueError):
        R.structural_break(_series([1.0] * 10), output="date")


def test_half_life_recovers_a_known_ar1_and_is_absent_for_a_random_walk() -> None:
    phi = 0.8
    hl = R.half_life(_series(_ar1(3000, phi)), window=1000)
    want = -math.log(2) / math.log(phi)
    assert hl.points
    assert hl.points[-1].value == pytest.approx(want, rel=0.25)
    trend = R.half_life(_series([float(i) for i in range(200)]), window=60)
    assert trend.points == (), "a trending window does not revert: absence, not a number"


def test_ar_residual_is_zero_on_an_exact_ar1_and_never_fits_on_its_own_point() -> None:
    x = [1.0]
    for _ in range(80):
        x.append(0.5 + 0.7 * x[-1])
    x = [v + 0.001 * math.sin(i) for i, v in enumerate(x)]
    res = R.ar_residual(_series(x))
    assert res.points
    assert max(abs(p.value) for p in res.points) < 0.01
    # A spike at the last point is fully a residual: the model was fitted without it.
    spiked = R.ar_residual(_series([*x, x[-1] + 50.0]))
    assert spiked.points[-1].value > 40.0


SINGLE = [(name, dict(params)) for name, params in (
    ("zscore", {"window": 0}), ("zscore", {"window": 30}), ("surprise", {"control": "weekday"}),
    ("seasonal_expectation", {"cycle": "month"}), ("pace", {"cycle": "month"}),
    ("diff", {"lag": 1}), ("acceleration", {"lag": 1}), ("lead_lag", {"lag": 2}),
    ("rank_percentile", {"window": 0}), ("rolling_volatility", {"window": 20}),
    ("spectral_state", {"window": 32}), ("vintage_revision", {}),
    ("structural_break", {"window": 40, "output": "stat"}),
    ("structural_break", {"window": 40, "output": "flag"}),
    ("structural_break", {"window": 40, "output": "age"}),
    ("half_life", {"window": 60}), ("ar_residual", {"window": 0}),
    ("ar_residual", {"window": 50}))]


@pytest.mark.parametrize(("name", "params"), SINGLE, ids=[f"{n}:{p}" for n, p in SINGLE])
def test_future_corruption_never_moves_a_feature_at_or_before_t(name: str,
                                                                params: dict[str, object]) -> None:
    clean_values = _ar1(240, 0.6, seed=11, mu=5.0)
    rng = random.Random(99)
    cut = 160
    dirty_values = clean_values[:cut] + [rng.uniform(-1e4, 1e4) for _ in clean_values[cut:]]
    clean, dirty = _series(clean_values), _series(dirty_values)
    t = clean.points[cut - 1].available_time
    a = R.apply(R.Transform(name, params), clean)
    b = R.apply(R.Transform(name, params), dirty)
    left = [(p.available_time, p.value) for p in a.points if p.available_time <= t]
    right = [(p.available_time, p.value) for p in b.points if p.available_time <= t]
    assert left, f"{name} produced nothing at or before t: the test would prove nothing"
    assert [s for s, _ in left] == [s for s, _ in right]
    assert [v for _, v in left] == pytest.approx([v for _, v in right], rel=1e-9, abs=1e-9)


def test_every_new_transform_is_registered_with_a_declared_family() -> None:
    for name in ("structural_break", "half_life", "ar_residual"):
        spec = R.TRANSFORMS[name]
        assert spec.family in R.FAMILIES and spec.arity == 1
    for family in ("structure", "disagreement", "latent"):
        assert family in R.FAMILIES
