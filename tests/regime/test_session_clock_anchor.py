"""Anchor-clocked families keep their anchor (2026-10-06): the window an open / close / gap /
rollover family is judged in runs from the prior close (server 00:00) to the market's 16:00."""
from __future__ import annotations

import pandas as pd

from libs.regime import session_clock as sc

#: The shared filter's server-hour windows before pass 2 (family_call.SESSIONS on LIVE 2d61e69a1).
LEGACY = {"asia": (0, 8), "london": (8, 16), "ny": (14, 22)}


def _weekday_hours(start: str, end: str) -> pd.DatetimeIndex:
    idx = pd.date_range(start, end, freq="h", tz="UTC")
    return idx[idx.dayofweek < 5]


def test_the_anchored_window_contains_the_old_window_and_the_market_session_every_hour() -> None:
    # Every weekday hour of 2018-2030: both DST regimes and every US/UK mismatch week.
    idx = _weekday_hours("2018-01-01", "2030-12-31 23:00")
    for s, (lo, hi) in LEGACY.items():
        anchored = sc.in_anchored_session(idx, s)
        legacy = (idx.hour >= lo) & (idx.hour < hi)
        market = sc.in_session(idx, s)
        assert anchored is not None and market is not None
        assert not (legacy & ~anchored).any(), s     # no signal the old filter kept is lost
        assert not (market & ~anchored).any(), s     # and the market session is inside it


def test_asia_is_the_prior_close_through_tokyo_16() -> None:
    # Summer: Tokyo 16:00 = 07:00 UTC = server 10:00. Winter: 07:00 UTC = server 09:00.
    s = pd.DatetimeIndex(["2026-07-15 00:00", "2026-07-15 09:59", "2026-07-15 10:00",
                          "2026-01-15 08:00", "2026-01-15 09:00", "2026-07-14 23:00"], tz="UTC")
    assert sc.in_anchored_session(s, "asia").tolist() == [True, True, False, True, False, False]


def test_which_families_are_anchor_clocked() -> None:
    for fam in ("overnight_gap_decay", "session_range_breakout", "opening_range", "carry",
                "family_overnight_gap_decay", "fx_rollover_drift"):
        assert sc.anchor_clocked(fam), fam
    assert sc.anchor_clocked("some_family", {"open_hour": 9})
    for fam in ("trend_ma_cross", "london_close_momentum", "asia_momentum", "", None):
        assert not sc.anchor_clocked(fam), fam


def test_filter_mask_picks_the_clock_and_unknown_sessions_answer_none() -> None:
    s = pd.DatetimeIndex(["2026-07-15 00:00"], tz="UTC")
    assert sc.filter_mask(s, "asia", anchored=True).tolist() == [True]
    assert sc.filter_mask(s, "asia", anchored=False).tolist() == [False]
    assert sc.in_anchored_session(s, "overlap") is None
    assert sc.in_anchored_session(pd.DatetimeIndex([], tz="UTC"), "asia").tolist() == []
