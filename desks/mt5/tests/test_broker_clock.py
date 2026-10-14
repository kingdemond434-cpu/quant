"""The venue's clock, measured from bars -- and the three ways it must refuse to guess.

WHAT WAS DARK. `state_admission` reported one gap: `session`, "no labeller ... its input (e.g.
the broker clock) is unavailable here". `session_phase.broker_utc_offset_h()` tries a live
MetaTrader5 terminal, then `data/broker_clock.json`, then gives up -- and that file names the
gateway as its only writer and HAS NEVER BEEN WRITTEN. So on a desk whose entire mechanism
vocabulary is asia / london_am / afternoon, the state that obviously conditions the edge was the
one state nobody could label, and conditional allocation ran on `weekday` ("no measurable
improvement; kept only by the shrinkage") and `event` ("only 1 bucket").

WHY A WRONG CLOCK IS WORSE THAN NO CLOCK, which is why every test below is a refusal test: it
mislabels every bucket without ever raising, and produces a confident wrong conditional mean.
`session_phase` already says this about a hardcoded zero. The same standard applies to an
inference from bars.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.regime.broker_clock import (  # noqa: E402
    MEASURED,
    MIN_BARS,
    MIN_TROUGH_DEPTH,
    OVERLAP_PEAK_UTC,
    ROLLOVER_TROUGH_UTC,
    TOLERANCE_H,
    UNMEASURED,
    estimate_offset,
    hour_profile,
)


def _profile(offset: int, *, depth: float = 0.1) -> list[float]:
    """A synthetic FX day shifted by `offset`: trough at the rollover, peak at the overlap."""
    p = np.ones(24)
    for h in range(24):
        utc = (h - offset) % 24
        if utc == ROLLOVER_TROUGH_UTC:
            p[h] = depth
        elif utc == OVERLAP_PEAK_UTC:
            p[h] = 3.0
        elif utc in (ROLLOVER_TROUGH_UTC - 1, (ROLLOVER_TROUGH_UTC + 1) % 24):
            # The shoulders must stay ABOVE the trough at every depth, or a shallow-trough
            # fixture makes a shoulder the minimum and tests the wrong hour.
            p[h] = min(0.9, depth * 1.5)
    return [float(x) for x in p]


# ---------------------------------------------------------------------------------- it measures
def test_a_clean_fx_day_recovers_the_offset_it_was_shifted_by() -> None:
    for off in (0, 2, 3, -5, 7):
        r = estimate_offset({"EURUSD": _profile(off)})
        assert r["status"] == MEASURED, off
        assert r["utc_offset_hours"] == off, (off, r["utc_offset_hours"])


def test_several_symbols_that_agree_report_one_offset_and_zero_disagreement() -> None:
    r = estimate_offset({s: _profile(2) for s in ("EURUSD", "GBPUSD", "USDJPY")})
    assert r["utc_offset_hours"] == 2
    assert r["n_symbols"] == 3
    assert r["agreement"] == 0


def test_the_offset_is_signed_not_wrapped_into_zero_to_twentythree() -> None:
    """-5 and 19 are the same clock and only one of them reads as an offset."""
    r = estimate_offset({"EURUSD": _profile(-5)})
    assert r["utc_offset_hours"] == -5


def test_the_average_is_circular_because_twentythree_and_one_are_two_hours_apart() -> None:
    """Their arithmetic mean is 12, which is the wrong side of the world."""
    r = estimate_offset({"a": _profile(-1), "b": _profile(1)})
    assert abs(r["utc_offset_hours"]) <= 1, r["utc_offset_hours"]


# ------------------------------------------------------------------------------ it refuses
def test_a_flat_profile_has_no_rollover_to_find() -> None:
    """Taking the argmin of a flat profile returns noise wearing an offset."""
    r = estimate_offset({"EURUSD": [1.0] * 24})
    assert r["status"] == UNMEASURED
    assert r["utc_offset_hours"] is None
    assert "no rollover trough" in r["per_symbol"]["EURUSD"]["why"]


def test_a_shallow_trough_is_refused_at_the_declared_bar() -> None:
    shallow = estimate_offset({"EURUSD": _profile(2, depth=MIN_TROUGH_DEPTH + 0.05)})
    assert shallow["status"] == UNMEASURED
    deep = estimate_offset({"EURUSD": _profile(2, depth=MIN_TROUGH_DEPTH - 0.2)})
    assert deep["status"] == MEASURED


def test_two_anchors_that_disagree_are_not_one_measurement() -> None:
    """The trough is one sharp hour and the overlap is a four-hour plateau, so they may differ by
    an hour or two. Beyond that the estimator is reading something that is not a session."""
    p = np.ones(24)
    p[(0 + ROLLOVER_TROUGH_UTC) % 24] = 0.1          # trough says offset 0
    p[(9 + OVERLAP_PEAK_UTC) % 24] = 3.0             # peak says offset 9
    r = estimate_offset({"EURUSD": [float(x) for x in p]})
    assert r["status"] == UNMEASURED
    row = r["per_symbol"]["EURUSD"]
    assert row["disagreement_h"] > TOLERANCE_H
    assert row["offset_by_trough"] == 0 and row["offset_by_peak"] == 9


def test_a_malformed_profile_is_refused_rather_than_reshaped() -> None:
    for bad in ([1.0] * 23, [float("nan")] * 24, []):
        r = estimate_offset({"EURUSD": bad})
        assert r["status"] == UNMEASURED, bad


def test_no_usable_symbol_leaves_the_offset_unknown_and_says_why() -> None:
    r = estimate_offset({})
    assert r["status"] == UNMEASURED and r["utc_offset_hours"] is None
    assert "confident wrong conditional mean" in r["why"]


# --------------------------------------------------------------------------- the hour profile
def test_a_thin_window_cannot_produce_a_profile() -> None:
    n = MIN_BARS - 1
    assert hour_profile(list(range(n)), [1.0] * n) is None


def test_a_missing_hour_means_the_clock_cannot_be_read() -> None:
    """23 hours of history is not a day, and interpolating the missing one would invent the
    feature the estimator is looking for."""
    hours = [h % 23 for h in range(MIN_BARS * 2)]          # hour 23 never appears
    assert hour_profile(hours, [1.0] * len(hours)) is None


def test_the_profile_is_a_median_so_one_news_day_cannot_move_it() -> None:
    """A mean profile's argmax lands in whichever hour the news happened to land in."""
    hours = [h % 24 for h in range(MIN_BARS * 2)]
    vol = [1.0] * len(hours)
    vol[5] = 10_000.0                                      # one enormous bar at hour 5
    p = hour_profile(hours, vol)
    assert p is not None
    assert int(np.argmax(p)) != 5 or float(p[5]) == pytest.approx(1.0)


# ------------------------------------------------------------- the wire into the session labeller
def test_the_resolver_prefers_a_terminal_over_an_inference() -> None:
    """A measurement from bars is what a host with NO terminal deserves; it is not what a host
    with one should use. The tier order is the whole safety property here."""
    src = (_DESK / "research" / "session_phase.py").read_text("utf-8")
    i_live = src.index('"live_terminal"')
    i_rec = src.index('"recorded_broker_clock"')
    i_bars = src.index('"measured_from_bars"')
    assert i_live < i_rec < i_bars, "the fallback order must be terminal, record, then inference"


def test_the_inference_is_only_believed_when_it_says_MEASURED() -> None:
    src = (_DESK / "research" / "session_phase.py").read_text("utf-8")
    assert 'str(rec.get("status")) == "MEASURED"' in src


def test_the_inference_writes_its_own_file_and_never_the_terminals() -> None:
    """An inference must not race or overwrite a live measurement."""
    src = (_DESK / "research" / "measure_broker_clock.py").read_text("utf-8")
    assert "broker_clock_measured.json" in src
    assert 'OUT = BASE / "data" / "broker_clock.json"' not in src


def test_a_failed_measurement_exits_non_zero() -> None:
    """The desk's standing rule: a task that cannot do its job must say so in its exit code, or
    the task list stays green while the session dimension stays dark."""
    src = (_DESK / "research" / "measure_broker_clock.py").read_text("utf-8")
    assert 'return 0 if doc.get("status") == "MEASURED" else 1' in src
