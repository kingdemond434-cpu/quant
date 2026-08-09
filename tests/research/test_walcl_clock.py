"""R0031 WALCL forward clock -- the pre-registered construction, pinned.

The clock's value is that its construction is FROZEN: 4-week log impulse, +2d release lag,
z over 20 weekly obs, no back-writing. These tests pin exactly those properties so a later
edit is a visible contract break (a second window is a second trial), plus the L1.41 refusal
paths -- absent or degenerate input must refuse, never fabricate a 0.0 that reads as a position.
"""
from __future__ import annotations

import math

from scripts.derive_walcl_clock import (
    _IMPULSE_WEEKS,
    _MIN_OBS,
    _RELEASE_LAG_DAYS,
    _ZWIN,
    signal_for,
)


def _weekly(n, start_year=2024, base=6_000_000.0, growth=0.001, varied=True):
    """n weekly Wednesday observations; varied=True adds a deterministic wobble so the
    impulse window is not degenerate (constant growth => zero impulse variance => refusal)."""
    from datetime import date, timedelta
    d0 = date(start_year, 1, 3)
    out = []
    for i in range(n):
        v = base * (1 + growth) ** i
        if varied:
            v *= 1 + 0.0005 * (i % 7)
        out.append(((d0 + timedelta(weeks=i)).isoformat(), v))
    return out


def test_preregistered_constants_are_the_screened_ones():
    assert (_IMPULSE_WEEKS, _ZWIN, _RELEASE_LAG_DAYS) == (4, 20, 2)
    assert _MIN_OBS == 24


def test_short_history_refuses_rather_than_fabricates():
    rows = _weekly(_MIN_OBS - 1)
    assert signal_for("2030-01-01", rows) is None


def test_release_lag_hides_the_latest_observation_for_two_days():
    rows = _weekly(40)
    last_asof = rows[-1][0]
    # the day AFTER the as-of date the newest obs is still embargoed (+2d lag)
    from datetime import date, timedelta
    d = date.fromisoformat(last_asof)
    early = (d + timedelta(days=1)).isoformat()
    late = (d + timedelta(days=2)).isoformat()
    sig_early = signal_for(early, rows)
    sig_late = signal_for(late, rows)
    assert sig_early is not None and sig_late is not None
    assert sig_early["asof"] == rows[-2][0]      # embargoed: previous week's obs rules
    assert sig_late["asof"] == last_asof         # released: newest obs usable


def test_impulse_is_the_four_week_log_change():
    rows = _weekly(40)
    sig = signal_for("2030-01-01", rows)
    assert sig is not None
    expect = math.log(rows[-1][1]) - math.log(rows[-1 - _IMPULSE_WEEKS][1])
    assert abs(sig["impulse"] - expect) < 1e-6            # impulse published rounded to 6dp


def test_constant_growth_makes_a_degenerate_window_and_refuses():
    # perfectly constant growth -> zero impulse variance -> refuse (never z=inf or 0/0)
    rows = _weekly(40, growth=0.001, varied=False)
    assert signal_for("2030-01-01", rows) is None


def test_a_liquidity_surge_prints_a_positive_z():
    rows = _weekly(40, growth=0.0)
    # flat balance sheet, then a 3% expansion in the last 4 weeks
    surged = rows[:-4] + [(d, v * 1.03) for d, v in rows[-4:]]
    sig = signal_for("2030-01-01", surged)
    assert sig is not None and sig["z20"] > 1.0
