"""regime_probabilities (audit #8): walk-forward filtered HMM probabilities are PIT, named by
volatility, and the contract machinery returns GAIN on a planted regime effect. Synthetic only."""
from __future__ import annotations

import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK.parents[1]), str(_DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from macro import regime_probabilities as rp  # noqa: E402


def _closes(n: int, planted: bool, seed: int = 3) -> dict[str, float]:
    """Alternating calm (vol 0.5%) and stress (vol 2.5%) spells; in stress, the 20-day move
    persists (a drift of a third of a sigma in its direction)."""
    rng = np.random.default_rng(seed)
    state, rets = 0, []
    for _ in range(n):
        if planted and rng.random() < 1 / 40:
            state = 1 - state
        sig = 0.025 if state else 0.005
        r = rng.normal(0, sig)
        if planted and state and len(rets) >= 20:
            r += 0.35 * sig * float(np.sign(sum(rets[-20:])))
        rets.append(r)
    c = 100 * np.exp(np.cumsum(rets))
    d0 = date(2019, 1, 1)
    return {(d0 + timedelta(days=i)).isoformat(): float(v) for i, v in enumerate(c)}


def test_rows_are_pit_and_named_by_volatility() -> None:
    closes = _closes(700, planted=True)
    rows, complete = rp.walk_forward(closes)
    assert complete and rows
    for r in rows[:5] + rows[-5:]:
        assert abs(r["p_quiet"] + r["p_normal"] + r["p_stress"] - 1.0) < 1e-6
        assert datetime.fromisoformat(r["available_time"]) == rp.available_at(r["event_time"])
        assert 0.0 <= r["p_switch"] <= 1.0 and r["exp_duration"] >= 1.0
    # truncating the future does not change a past row: the filter never smooths
    cut = dict(sorted(closes.items())[:600])
    early, _ = rp.walk_forward(cut)
    by = {r["event_time"]: r for r in rows}
    for r in early[-30:]:
        assert abs(by[r["event_time"]]["p_stress"] - r["p_stress"]) < 1e-9


def _write(tmp: Path, closes: dict[str, float]) -> Path:
    idx = pd.DatetimeIndex([pd.Timestamp(d, tz="UTC") + pd.Timedelta(hours=20) for d in closes])
    pd.DataFrame({"close": list(closes.values())}, index=idx).to_parquet(tmp / "US500_H1.parquet")
    return tmp


def test_planted_stress_trend_is_gain_and_noise_is_not(tmp_path: Path) -> None:
    now = datetime(2030, 1, 1, tzinfo=UTC)
    (tmp_path / "a").mkdir()
    rep = rp.run(dry_run=True, universe_dir=_write(tmp_path / "a", _closes(1600, True)),
                 now=now, symbols=("US500",))
    by = {c["label"]: c for c in rep["contracts"]}
    # planted regimes: the filtered mixture forecasts variance and a likely switch is a move
    assert by["var_hat->next5_variance"]["verdict"] == "GAIN"
    assert by["p_switch->|move|"]["verdict"] == "GAIN"
    (tmp_path / "b").mkdir()
    noise = rp.run(dry_run=True, universe_dir=_write(tmp_path / "b", _closes(1600, False, 9)),
                   now=now, symbols=("US500",))
    nb = {c["label"]: c for c in noise["contracts"]}
    # one constant-vol regime: nothing to find
    assert all(c["verdict"] in ("NO_GAIN", "UNMEASURED") for c in nb.values()), nb
    assert rep["grounds"]["US500"]["data_source"] == "mt5:bars"
