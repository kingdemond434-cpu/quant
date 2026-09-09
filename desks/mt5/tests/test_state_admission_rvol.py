"""The `rvol` state dimension (Tier-1 audit G6): three dimensions become four, point-in-time.

STATE_ADMISSION.json read `dimensions_tried: 3` -- session, weekday, event -- and of the
blueprint's thirteen state axes only those with a point-in-time labeller could ever be asked
"P(alpha > 0 | state)". Realised vol is computed elsewhere on the desk and had no
`build_labeller` branch. What is pinned: the label is the quintile of the trade's OWN symbol's
trailing realised vol ranked among that symbol's EARLIER readings only; the bar read is the last
one stamped strictly before the trade; rewriting the bars after a trade cannot move its label;
too little history or no bars is no label rather than a guessed one; and the judge's bars did not
move.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import state_admission_run as runner  # noqa: E402

from libs.regime import state_admission as sa  # noqa: E402

N = 3000
SPLIT = 1500


def _bars(seed: int = 0, n: int = N, sigma_late: float = 1e-3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    sig = np.concatenate([np.full(SPLIT, 1e-4), np.full(n - SPLIT, sigma_late)])
    close = 1.10 * np.exp(np.cumsum(rng.normal(0, 1, n) * sig))
    idx = pd.date_range("2025-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame({"open": close, "high": close, "low": close, "close": close}, index=idx)


def _universe(tmp_path: Path, bars: pd.DataFrame) -> Path:
    uni = tmp_path / "universe"
    uni.mkdir(parents=True, exist_ok=True)
    bars.to_parquet(uni / "EURUSD_H1.parquet")
    return uni


def _trade(when: pd.Timestamp, sym: str = "EURUSD") -> sa.Trade:
    return sa.Trade(sleeve=f"{sym}_session_range_breakout_asia", when=str(when), r=0.1)


def test_rvol_is_in_the_default_dimensions_and_the_judge_is_untouched() -> None:
    assert "rvol" in runner.DEFAULT_DIMENSIONS
    assert runner.DEFAULT_DIMENSIONS[:3] == ("session", "weekday", "event")
    assert (sa.ADMIT_T, sa.GRAVEYARD_T, sa.MIN_TEST_TRADES, sa.K_BUCKET) == (2.0, -2.0, 150, 40.0)


def test_a_trade_in_the_high_vol_regime_lands_in_the_top_quintile(tmp_path, monkeypatch) -> None:
    bars = _bars()
    monkeypatch.setattr(sa, "UNIVERSE", _universe(tmp_path, bars))
    fn = sa.build_labeller("rvol")
    assert fn is not None
    # Just after the change every reading is above all 1,500 quiet ones: the top quintile.
    late = [fn(_trade(bars.index[i])) for i in range(SPLIT + 30, SPLIT + 300, 30)]
    assert late and set(late) == {"Q5_HIGH"}, late
    # Inside the quiet regime the ranks are spread across the quintiles, never all one bucket.
    early = {fn(_trade(bars.index[i])) for i in range(sa.RVOL_MIN_HISTORY + 100, SPLIT, 50)}
    assert len(early) >= 3 and "" not in early, early
    # And deep into the loud regime it has become the new normal: the expanding rank spreads
    # again, which is the point-in-time semantics -- "high" is high against what was known.
    deep = {fn(_trade(bars.index[i])) for i in range(N - 600, N, 40)}
    assert len(deep) >= 2 and "" not in deep, deep


def test_the_label_reads_the_last_bar_strictly_before_the_trade(tmp_path, monkeypatch) -> None:
    bars = _bars()
    monkeypatch.setattr(sa, "UNIVERSE", _universe(tmp_path, bars))
    fn = sa.build_labeller("rvol")
    pct = sa.rvol_percentiles(bars["close"])
    i = SPLIT + 300
    # A trade AT the stamp of bar i must read bar i-1: bar i's close is an hour in the future.
    assert fn(_trade(bars.index[i])) == sa.rvol_bucket(float(pct.iloc[i - 1]))
    # A trade one second later is still inside bar i and still reads bar i-1.
    assert fn(_trade(bars.index[i] + pd.Timedelta(seconds=1))) == sa.rvol_bucket(
        float(pct.iloc[i - 1]))


def test_rewriting_the_bars_after_a_trade_cannot_move_its_label(tmp_path, monkeypatch) -> None:
    bars = _bars()
    cut = SPLIT + 400
    probes = [bars.index[i] for i in range(sa.RVOL_MIN_HISTORY + 50, cut, 37)]
    monkeypatch.setattr(sa, "UNIVERSE", _universe(tmp_path, bars))
    before = [sa.build_labeller("rvol")(_trade(w)) for w in probes]
    # Everything after `cut` becomes a different, wildly more volatile walk.
    rng = np.random.default_rng(99)
    dirty = bars.copy()
    tail = float(bars["close"].iloc[cut - 1]) * np.exp(np.cumsum(rng.normal(0, 0.02, N - cut)))
    for col in ("open", "high", "low", "close"):
        dirty.iloc[cut:, dirty.columns.get_loc(col)] = tail
    monkeypatch.setattr(sa, "UNIVERSE", _universe(tmp_path / "b", dirty))
    after = [sa.build_labeller("rvol")(_trade(w)) for w in probes]
    assert before == after, "a label moved when only LATER bars changed: the rank looks ahead"
    assert "" not in before


def test_too_little_history_or_no_bars_is_no_label(tmp_path, monkeypatch) -> None:
    bars = _bars()
    monkeypatch.setattr(sa, "UNIVERSE", _universe(tmp_path, bars))
    fn = sa.build_labeller("rvol")
    assert fn(_trade(bars.index[10])) == ""                       # before any vol reading
    assert fn(_trade(bars.index[sa.RVOL_MIN_HISTORY // 2])) == ""  # under RVOL_MIN_HISTORY
    assert fn(_trade(bars.index[2000], sym="GBPUSD")) == ""       # no parquet for the symbol
    assert fn(sa.Trade(sleeve="EURUSD_x_y", when="not a time", r=0.0)) == ""
    # A universe that does not exist at all is a gap the runner names, not a crash.
    monkeypatch.setattr(sa, "UNIVERSE", tmp_path / "absent")
    assert sa.build_labeller("rvol") is None


def test_the_bucket_edges_and_the_expanding_rank() -> None:
    assert sa.rvol_bucket(float("nan")) == ""
    assert sa.rvol_bucket(0.0) == "Q1_LOW" and sa.rvol_bucket(0.19) == "Q1_LOW"
    assert sa.rvol_bucket(0.2) == "Q2" and sa.rvol_bucket(0.61) == "Q4"
    assert sa.rvol_bucket(1.0) == "Q5_HIGH"
    s = pd.Series(np.r_[np.full(300, 1.0), np.full(300, 1.0 + 0.0)])  # flat: no vol at all
    p = sa.rvol_percentiles(s)
    assert p.iloc[:sa.RVOL_MIN_HISTORY - 1].isna().all(), "no rank before the minimum history"


def test_the_runner_labels_trades_with_rvol_alongside_the_others(tmp_path, monkeypatch) -> None:
    bars = _bars()
    monkeypatch.setattr(sa, "UNIVERSE", _universe(tmp_path, bars))
    trades = [_trade(bars.index[i]) for i in range(SPLIT + 30, SPLIT + 300, 15)]
    labelled, gaps = runner.label(trades, ("weekday", "rvol"))
    assert "rvol" not in gaps
    assert all(t.buckets.get("rvol") == "Q5_HIGH" for t in labelled)
    assert all(t.buckets.get("weekday") for t in labelled)
    with pytest.raises(KeyError):
        _ = labelled[0].buckets["session"]
