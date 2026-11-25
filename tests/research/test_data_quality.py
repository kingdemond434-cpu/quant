"""Clean data enforced: a score per series, hard defects quarantine, the floor only rises."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from libs.research import data_quality as dq

NOW = datetime(2026, 11, 25, 12, tzinfo=UTC)


def _frame(n: int = 1200, *, end: datetime = NOW) -> pd.DataFrame:
    idx = pd.date_range(end=pd.Timestamp(end).floor("h"), periods=n * 2, freq="h", tz="UTC")
    idx = idx[(idx.dayofweek < 5)][-n:]
    rng = np.random.default_rng(3)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.001, len(idx))))
    o = np.roll(c, 1)
    o[0] = c[0]
    h = np.maximum(o, c) * 1.0005
    lo = np.minimum(o, c) * 0.9995
    return pd.DataFrame({"open": o, "high": h, "low": lo, "close": c}, index=idx)


def test_a_clean_series_scores_clean_and_is_not_quarantined() -> None:
    s = dq.score_bars(_frame(), NOW)
    assert s["status"] == "MEASURED" and s["hard"] == [] and s["content_score"] > 0.9
    assert dq.assess({"X": s})["n_quarantined"] == 0


def test_too_few_bars_is_unmeasured_never_clean() -> None:
    s = dq.score_bars(_frame(30), NOW)
    assert s["status"] == dq.UNMEASURED and s["score"] is None


def test_duplicates_and_broken_ohlc_quarantine() -> None:
    df = _frame()
    df = pd.concat([df, df.iloc[[100]]]).sort_index()
    df.iloc[200, df.columns.get_loc("high")] = df.iloc[200]["low"] * 0.5
    s = dq.score_bars(df, NOW)
    assert "duplicate_timestamps" in s["hard"] and "ohlc_invariant_broken" in s["hard"]
    assert set(dq.assess({"BAD": s})["quarantined"]) == {"BAD"}


def test_a_non_utc_or_off_grid_clock_quarantines() -> None:
    df = _frame()
    naive = df.copy()
    naive.index = naive.index.tz_localize(None)
    assert "clock_not_utc" in dq.score_bars(naive, NOW)["hard"]
    off = df.copy()
    off.index = off.index + pd.Timedelta(minutes=7)
    assert "bars_off_the_hour_grid" in dq.score_bars(off, NOW)["hard"]


def test_future_stamped_bars_are_lookahead() -> None:
    s = dq.score_bars(_frame(end=NOW + timedelta(days=2)), NOW)
    assert "future_stamped_bars" in s["hard"]


def test_staleness_pages_but_does_not_quarantine() -> None:
    s = dq.score_bars(_frame(end=NOW - timedelta(days=30)), NOW)
    out = dq.assess({"OLD": s})
    assert s["stale"] and out["n_stale"] == 1 and out["n_quarantined"] == 0
    assert s["score"] < s["content_score"]


def test_holes_in_the_sessions_lower_coverage() -> None:
    df = _frame()
    holed = df.drop(df.index[300:420])
    assert dq.score_bars(holed, NOW)["components"]["coverage"] < \
        dq.score_bars(df, NOW)["components"]["coverage"]


def test_the_floor_only_rises() -> None:
    best = {"mean_score": 0.9, "mean_content_score": 0.95, "n_quarantined": 1, "n_stale": 2,
            "n_unreadable": 0}
    ok = dict(best)
    assert dq.check_ratchet(ok, best) == []
    worse = dict(best, mean_content_score=0.80, n_quarantined=3, n_stale=5, n_unreadable=2)
    assert len(dq.check_ratchet(worse, best)) == 4
    assert dq.check_ratchet({"mean_score": None}, best)  # UNMEASURED never passes


def test_quarantined_symbols_reads_a_report_and_tolerates_junk() -> None:
    assert dq.quarantined_symbols({"quarantined": {"xauusd": {}}}) == {"XAUUSD"}
    assert dq.quarantined_symbols(None) == set()


def test_the_real_universe_scores_without_error() -> None:
    out = dq.run(now=NOW)
    assert out["n_series"] > 50 and out["n_measured"] + out["n_unreadable"] == out["n_series"]


def test_best_only_improves() -> None:
    b = dq.merge_best(None, {"mean_score": 0.8, "mean_content_score": 0.9, "n_quarantined": 3,
                             "n_stale": 5, "n_unreadable": 1})
    b2 = dq.merge_best(b, {"mean_score": 0.7, "mean_content_score": 0.95, "n_quarantined": 4,
                           "n_stale": 2, "n_unreadable": 1})
    assert b2["mean_score"] == 0.8 and b2["mean_content_score"] == 0.95
    assert b2["n_quarantined"] == 3 and b2["n_stale"] == 2


def test_the_tensor_publishes_quality_and_skips_a_quarantined_series(tmp_path, monkeypatch) -> None:
    import sys
    sys.path.insert(0, str(dq.ROOT / "desks" / "mt5"))
    from research import global_coverage_tensor as G

    monkeypatch.setattr(G, "OUT", tmp_path / "GLOBAL_COVERAGE_TENSOR.json")
    (tmp_path / G.QUALITY_OUT_NAME).write_text('{"quarantined": {"XAUUSD": {}}}')
    assert G._quarantined() == {"XAUUSD"}
    doc = G._data_quality(None)
    assert doc.get("n_series", 0) > 0 and "best" in doc
