"""R0134 chart context -- the structure the discretionary sleeve reads before it decides.

The sleeve was being asked to name swing levels it had never been shown. These tests pin that the
pivots are real pivots, that a defended level is distinguishable from an accidental one, and that
a missing instrument is RECORDED rather than silently dropped from the universe.
"""
from __future__ import annotations

from datetime import UTC, datetime

from scripts.build_chart_context import (atr_pct, build, build_symbol, cluster_levels,
                                         correlations, pivots, timeframe_view,
                                         trend_state)

_NOW = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)


def _bars(path):
    out, ts = [], int(_NOW.timestamp() * 1000) - len(path) * 900_000
    for hi, lo in path:
        out.append((ts, (hi + lo) / 2, hi, lo, (hi + lo) / 2))
        ts += 900_000
    return out


def _zigzag(peaks, troughs, n_between=5, base=100.0):
    """Alternating legs producing known swing highs at `peaks` and lows at `troughs`."""
    path, cur = [], base
    for i in range(max(len(peaks), len(troughs))):
        for tgt in (troughs[i] if i < len(troughs) else None,
                    peaks[i] if i < len(peaks) else None):
            if tgt is None:
                continue
            for j in range(n_between):
                px = cur + (tgt - cur) * (j + 1) / n_between
                path.append((px + 0.05, px - 0.05))
            cur = tgt
    # a retrace off the final extreme, so the last swing is far enough from the edge to be a
    # detectable pivot (a fractal needs PIVOT_K bars on BOTH sides)
    for j in range(n_between + 3):
        path.append((cur - (j + 1) * 0.3 + 0.05, cur - (j + 1) * 0.3 - 0.05))
    return path


def test_pivots_find_the_swings_that_are_actually_there():
    highs, lows = pivots(_bars(_zigzag([110, 112], [95, 97])))
    assert highs and lows
    assert any(abs(h[1] - 110) < 0.2 for h in highs)
    assert any(abs(lo[1] - 95) < 0.2 for lo in lows)


def test_a_defended_level_is_distinguishable_from_an_accidental_one():
    # A level touched three times and held is a different object from one touched once, and
    # telling them apart is most of what structure reading IS.
    pts = [(10, 100.0), (30, 100.1), (55, 99.95), (70, 120.0)]
    levels = cluster_levels(pts, n_bars=80)
    assert levels[0]["touches"] == 3 and abs(levels[0]["price"] - 100.0) < 0.2
    assert any(lv["touches"] == 1 for lv in levels)             # the one-off is kept, just ranked


def test_a_far_apart_pivot_is_not_folded_into_a_level():
    levels = cluster_levels([(10, 100.0), (20, 108.0)], n_bars=40)
    assert len(levels) == 2 and all(lv["touches"] == 1 for lv in levels)


def test_trend_is_read_from_the_swing_sequence():
    up = _bars(_zigzag([110, 118], [95, 103]))
    assert "UPTREND" in timeframe_view(up)["trend"]
    down = _bars(_zigzag([105, 97], [92, 85]))
    assert "DOWNTREND" in timeframe_view(down)["trend"]


def test_too_few_swings_is_unreadable_not_a_guess():
    assert "UNREADABLE" in trend_state([], [])
    assert timeframe_view(_bars([(100.1, 99.9)] * 4))["state"] == "UNMEASURED"


def test_room_to_the_next_level_is_reported_both_ways():
    # The number that decides whether a trade has room at all: long into resistance 0.3% away with
    # an invalidation 2% below is a bad trade at any conviction.
    v = timeframe_view(_bars(_zigzag([110, 112], [95, 97])))
    assert v["nearest_resistance_pct"] is None or v["nearest_resistance_pct"] > 0
    assert v["nearest_support_pct"] is None or v["nearest_support_pct"] < 0
    assert 0.0 <= v["position_in_range"] <= 1.0


def test_volatility_regime_is_measured_against_the_instruments_own_history():
    quiet = _bars([(100.05, 99.95)] * 120)
    assert atr_pct(quiet) is not None and atr_pct(quiet) < 0.5
    assert timeframe_view(quiet)["vol_regime"] in ("NORMAL", "CONTRACTING", "EXPANDING",
                                                   "UNMEASURED")


def test_an_unavailable_instrument_is_recorded_never_silently_dropped():
    # A universe that shrinks to whatever happened to answer is a universe nobody chose.
    rep = build(("BTCUSDT", "FAKEUSDT"), now=_NOW,
                fetch=lambda sym, a, b, tf=None: (([], "venue 404") if sym == "FAKEUSDT"
                                                  else (_bars(_zigzag([110], [95])), "test")))
    assert "FAKEUSDT" in rep["unavailable"]
    assert rep["status"] in ("PARTIAL-UNIVERSE", "DEGRADED")
    assert "FAKEUSDT" in rep["detail"]
    assert rep["n_symbols"] == 2 and rep["n_ok"] < 2


def test_a_fully_charted_universe_reports_ok():
    rep = build(("BTCUSDT",), now=_NOW,
                fetch=lambda *a, **k: (_bars(_zigzag([110, 118], [95, 103])), "test"))
    assert rep["status"] == "OK" and rep["n_ok"] == 1
    assert rep["charts"]["BTCUSDT"]["state"] == "OK"


def test_every_timeframe_is_charted_not_just_one():
    sym = build_symbol("BTCUSDT", now=_NOW,
                       fetch=lambda *a, **k: (_bars(_zigzag([110, 118], [95, 103])), "test"))
    assert set(sym["timeframes"]) == {"15m", "1h", "4h"}          # a scalp must see the 4h trend
    assert sym["momentum_pct"] and "day_range" in sym


def test_correlations_are_measured_across_the_universe():
    # Breadth is only real if the bets are separate; that has to be measured, not assumed.
    ident = [0.01, -0.02, 0.015, -0.005] * 12
    opp = [-x for x in ident]
    c = correlations({"A": ident, "B": ident, "C": opp})
    assert abs(c["A"]["B"] - 1.0) < 1e-6                 # same series -> perfectly correlated
    assert c["A"]["C"] < -0.9                            # opposite series -> negatively


def test_too_little_history_assumes_the_worst_case_not_the_best():
    # Assuming independence on thin data would let a blind book believe it was diversified.
    c = correlations({"A": [0.01, -0.01], "B": [0.02, -0.02]})
    assert c["A"]["B"] >= 0.9 and c["A"]["A"] == 1.0


def test_the_correlation_matrix_is_published_with_the_charts():
    rep = build(("BTCUSDT", "ETHUSDT"), now=_NOW,
                fetch=lambda *a, **k: (_bars(_zigzag([110, 118], [95, 103])), "test"))
    assert "correlations" in rep and "BTCUSDT" in rep["correlations"]
    assert "_returns" not in rep["charts"]["BTCUSDT"]    # working field stripped from the artifact
