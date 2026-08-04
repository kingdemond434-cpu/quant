"""DECAY MUST NOT BE CONFUSED WITH NEVER HAVING WORKED, OR WITH NOBODY HAVING LOOKED.

Three states all present as "a low or missing recent reading" and only one of them is decay. The
desk's own recurring defect is the detector that reads "not measured" as "measured and fine"; the
inverse error -- retiring a live source off six readings taken in one minute -- is equally
available and equally wrong. Both are pinned here.

The bucket tests are the load-bearing ones. `instrumentation_coverage.jsonl` on this machine holds
164 rows written within a few seconds, every one carrying the identical value. Counted naively
that is a sample of 164 with a beautiful standard error and no content whatsoever.
"""

from __future__ import annotations

import numpy as np
import pytest

from libs.data.decay import MIN_BUCKETS, bucket, classify_decay

HOUR = 3600.0
DAY = 86400.0


def _daily(vals, start: float = 0.0):
    return [(start + i * DAY, v) for i, v in enumerate(vals)]


# --------------------------------------------------------------- sample size

def test_a_burst_of_identical_rows_is_one_observation() -> None:
    """THE LIVE CASE. 164 rows five seconds apart describe one moment, not 164 of them."""
    pts = [(1000.0 + i * 0.03, 60.0) for i in range(164)]
    assert len(bucket(pts)) == 1


def test_bucketing_averages_within_a_bucket_rather_than_taking_the_last() -> None:
    """Last-wins would let one late outlier speak for the whole hour."""
    out = bucket([(0.0, 0.0), (60.0, 1.0)])
    assert out == [(0.0, 0.5)]


def test_a_burst_is_underpowered_no_matter_how_many_rows() -> None:
    """An observation count is not a sample size, and this is the exact shape that makes the two
    look alike -- a huge n_rows with a tiny n_buckets."""
    d = classify_decay("burst", [(1000.0 + i * 0.03, 1.0 - i / 1000.0) for i in range(500)],
                       kind="availability")
    assert d.verdict == "UNDERPOWERED"
    assert d.n_rows == 500
    assert d.n_buckets == 1
    assert "raw row" in d.why


def test_enough_rows_but_too_short_a_span_is_underpowered() -> None:
    """Six readings inside six hours are six readings about one day."""
    d = classify_decay("short", [(i * HOUR, 1.0 - 0.1 * i) for i in range(8)],
                       kind="availability")
    assert d.verdict == "UNDERPOWERED"
    assert d.n_buckets >= MIN_BUCKETS, "the bucket bar is met; the SPAN bar is what fails"


# ---------------------------------------------------------------- the states

def test_never_worked_is_not_decay() -> None:
    """Filing this as decay credits the desk with having HAD something it never had, and sends
    somebody to repair a connection that was never made."""
    d = classify_decay("dead-on-arrival", _daily([0.0] * 10), kind="availability")
    assert d.verdict == "NEVER-WORKED"
    assert "never succeeded" in d.why
    assert not d.decaying


def test_a_source_that_worked_and_stopped_is_dead_not_never_worked() -> None:
    """The distinction is actionable: there is something to restore."""
    d = classify_decay("went-dark", _daily([1, 1, 1, 1, 1, 1, 0, 0, 0, 0]), kind="availability")
    assert d.verdict == "DEAD"
    assert "has stopped" in d.why


def test_a_real_decline_is_caught() -> None:
    d = classify_decay("fading", _daily(list(np.linspace(1.0, 0.2, 20))), kind="usefulness")
    assert d.verdict == "DECAYING"
    assert d.slope_per_day < 0
    assert d.t_stat <= -2.0


def test_a_flat_source_over_a_wide_sample_is_stable_not_underpowered() -> None:
    """STABLE is a real finding and must be reachable; if every flat series came back
    UNDERPOWERED the monitor could never clear anything."""
    rng = np.random.default_rng(0)
    d = classify_decay("steady", _daily(list(0.9 + rng.normal(0, 0.01, 40))), kind="availability")
    assert d.verdict == "STABLE"


def test_improvement_is_reported_too() -> None:
    """A source getting BETTER is a reason to lean on it harder. Tracking only decline throws that
    away, and the asymmetry would make the monitor a one-way ratchet toward retirement."""
    d = classify_decay("rising", _daily(list(np.linspace(0.2, 1.0, 20))), kind="usefulness")
    assert d.verdict == "IMPROVING"
    assert d.slope_per_day > 0


def test_noise_alone_does_not_produce_a_decay_verdict() -> None:
    """THE CONTROL. A monitor that flags noise retires healthy sources, and the first time it is
    right nobody will be listening."""
    flagged = 0
    for seed in range(30):
        rng = np.random.default_rng(seed)
        d = classify_decay(f"s{seed}", _daily(list(rng.normal(0.9, 0.05, 30))),
                           kind="availability")
        flagged += d.verdict in {"DECAYING", "IMPROVING"}
    assert flagged <= 4, f"{flagged}/30 pure-noise series got a trend verdict"


# ------------------------------------------------------------------ hygiene

def test_no_readings_is_its_own_state() -> None:
    """Not decay, not health -- a gap in instrumentation, which is somebody else's job to fix."""
    d = classify_decay("unseen", [], kind="availability")
    assert d.verdict == "NO-DATA"
    assert d.n_buckets == 0


def test_non_finite_readings_are_dropped_not_zero_filled() -> None:
    """A failed probe that wrote NaN is not a probe that returned zero, and treating it as one
    invents a failure the source never had."""
    d = classify_decay("nan", [(0.0, float("nan")), (DAY, 1.0), (float("inf"), 1.0)],
                       kind="availability")
    assert d.n_rows == 1


def test_the_verdict_is_frozen() -> None:
    d = classify_decay("x", _daily([1.0] * 10), kind="availability")
    with pytest.raises((AttributeError, TypeError)):
        d.verdict = "STABLE"        # type: ignore[misc]
