"""R0389 / R0390 -- the collector write boundary.

Every fixture here is the REAL measured shape of the defect, not an invented one: the numbers are
the live values that produced each instance (desk lesson L0134 -- build loader fixtures from the
real on-disk row). The two that matter most are the ones the desk actually paid for:
`test_refuses_the_real_bad_read` (the stored -60% stablecoin day) and
`test_refuses_the_live_pool_census_collapse` (n_pools 566 of ~6800, booked as a position).
"""
from __future__ import annotations

import json
from typing import ClassVar

from libs.research.axis_integrity import (
    Bar,
    check_coverage,
    check_move,
    coverage_bar,
    move_bar,
)

#: The live stablecoin series either side of the 2026-07-27 bad read.
_GOOD_PREV = 306757352596.0
_BAD_READ = 122373928343.0


def _ramp(n: int, start: float = 300e9, step: float = 0.001) -> list[float]:
    """A slow upward ramp with the ~0.1%/day drift the real supply series has."""
    out = [start]
    for i in range(1, n):
        out.append(out[-1] * (1.0 + step * (1 if i % 2 else -0.5)))
    return out


class TestMoveBar:
    def test_unmeasured_below_min_obs_and_does_not_block(self) -> None:
        """A young series states that it cannot state a bar -- and is not blocked by it.

        Fail-closed here would stop every new axis from ever starting, which is timidity wearing
        a safety costume. UNMEASURED is a real answer (L1.28a) and it must be VISIBLE.
        """
        bar = move_bar(_ramp(10))
        assert not bar.measured
        assert bar.value is None
        assert "UNMEASURED" in bar.basis
        v = check_move(1.0, 2.0, bar)
        assert v.ok, "an unmeasured bar must not block a write"
        assert "UNCHECKED" in v.reason, "but it must say so rather than read as a clean pass"

    def test_publishes_its_denominator_and_attrition(self) -> None:
        """L1.57 / L1.60: the bar carries what it was derived from, and what it lost."""
        hist = _ramp(60)
        hist[10] = 0.0                       # a non-positive base cannot yield a move
        bar = move_bar(hist)
        assert bar.measured
        # 59 consecutive pairs. Only (hist[10], hist[11]) is unusable -- it is the one with a
        # non-positive BASE. The pair INTO the zero is perfectly usable and reads -100%, which is
        # the point: a corrupt zero is caught by check_move at the boundary rather than quietly
        # excused here.
        assert bar.n == 58
        assert bar.skipped == 1, "the skipped pair is COUNTED, never invisible"

    def test_refuses_the_real_bad_read(self) -> None:
        """The instance this exists for: 306.76bn -> 122.37bn, stored with z20=-239.803."""
        bar = move_bar(_ramp(900))
        assert not check_move(_BAD_READ, _GOOD_PREV, bar).ok

    def test_refuses_the_sign_flipping_direction_too(self) -> None:
        """The stablecoin instance escaped only because sign(z) happened to be preserved.

        A bad read HIGH flips the position and books that day's forward return inverted, which is
        the direction that actually costs a forward slot.
        """
        bar = move_bar(_ramp(900))
        assert not check_move(_GOOD_PREV * 1.6, _GOOD_PREV, bar).ok

    def test_admits_the_series_own_ordinary_days(self) -> None:
        """A bar that refuses real days gets switched off (L1.43), so it must refuse none."""
        hist = _ramp(900)
        bar = move_bar(hist)
        refused = [i for i in range(1, len(hist))
                   if not check_move(hist[i], hist[i - 1], bar).ok]
        assert refused == []

    def test_one_stored_corruption_cannot_blow_the_bar_open(self) -> None:
        """The contamination ratchet, on a series that HAS stored a corrupt read.

        A bar set to "the largest move ever seen" widens to admit the next corruption. The cap at
        OUTLIER_CAP x the robust scale is what stops that.
        """
        clean = _ramp(900)
        poisoned = [*clean]
        poisoned[500] = poisoned[499] * 0.4          # the -60% day, now IN the history
        bar = move_bar(poisoned)
        assert bar.value is not None
        assert bar.value < 0.2, f"bar widened to {bar.value:.1%} by one corrupt read"
        # Without the cap the bar would be the observed 150% x margin; with it, ~4.95%.
        assert not check_move(_BAD_READ, _GOOD_PREV, bar).ok, "still refuses the same read"

    def test_bar_is_measured_per_series_not_copied(self) -> None:
        """R0390's actual requirement: two series with different volatility get different bars."""
        quiet = move_bar(_ramp(900, step=0.0002))
        rowdy = move_bar(_ramp(900, step=0.02))
        assert quiet.value is not None and rowdy.value is not None
        assert rowdy.value > quiet.value * 5

    def test_flat_series_does_not_get_a_zero_bar(self) -> None:
        """A dead-flat stretch must not drive the bar to 0 and start refusing ordinary days."""
        bar = move_bar([100.0] * 900)
        assert bar.measured
        assert check_move(100.0, 100.0, bar).ok

    def test_non_positive_predecessor_is_unchecked_not_refused(self) -> None:
        bar = move_bar(_ramp(900))
        v = check_move(5.0, 0.0, bar)
        assert v.ok and "UNCHECKED" in v.reason


class TestCoverage:
    #: The live n_pools history off data/defi_util_axis.jsonl, collapses included.
    LIVE: ClassVar[list[int]] = [4014, 6892, 7031, 7795, 6691, 2511, 566,
                                 6538, 6835, 6794, 6792, 6774, 6496, 6183]

    def test_refuses_the_live_pool_census_collapse(self) -> None:
        """566 of ~6800 pools -- 92% of the aggregate missing -- was booked as a position."""
        bar = coverage_bar(self.LIVE)
        assert not check_coverage(566, bar).ok
        assert not check_coverage(2511, bar).ok

    def test_admits_ordinary_census_churn(self) -> None:
        bar = coverage_bar(self.LIVE)
        for n in (4014, 6183, 6496, 7795):
            assert check_coverage(n, bar).ok, f"refused an ordinary count {n}"

    def test_median_not_mean_so_collapses_cannot_lower_the_floor(self) -> None:
        """The collapses are already in the history the floor is derived from."""
        bar = coverage_bar(self.LIVE)
        assert bar.value is not None
        assert bar.value > 3000, "a mean-based floor would sag toward admitting the next collapse"

    def test_unmeasured_on_a_short_history(self) -> None:
        bar = coverage_bar([10, 20])
        assert not bar.measured
        assert check_coverage(1, bar).ok


class TestBarContract:
    def test_as_dict_is_json_safe(self) -> None:
        for bar in (move_bar(_ramp(900)), move_bar(_ramp(3))):
            json.dumps(bar.as_dict())
            json.dumps(check_move(1.0, 1.0, bar).as_dict())

    def test_verdict_truthiness_tracks_the_verdict(self) -> None:
        """A dataclass is unconditionally truthy, so `if not verdict:` would be a guard that can
        never fire. This footgun was found by it silently passing this module's own test."""
        bar = move_bar(_ramp(900))
        assert not check_move(_BAD_READ, _GOOD_PREV, bar)
        assert check_move(_GOOD_PREV, _GOOD_PREV, bar)

    def test_unmeasured_bar_is_not_a_zero_bar(self) -> None:
        """The whole WS-005 class: absence must never resolve to a clean numeric verdict."""
        bar = Bar(None, 0, 0, "UNMEASURED: nothing")
        assert bar.value is not None or not bar.measured
        assert bar.as_dict()["bar"] is None
