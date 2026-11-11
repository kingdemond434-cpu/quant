"""The shared session filter and the scalp masks judge sessions in real time (2026-09-30)."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import family_call as fc  # noqa: E402


def _sig(stamp: str) -> SimpleNamespace:
    return SimpleNamespace(time=pd.Timestamp(stamp, tz="UTC"))


def test_london_is_the_london_session_not_the_frankfurt_pre_open() -> None:
    # Summer: stamp 08:00 is 05:00 UTC, "london" under the old 8-16 server window and 06:00 in
    # London; 11:00 stamp = 09:00 London; 17:30 stamp = 15:30 London.
    early, open_ = _sig("2026-07-15 08:00"), _sig("2026-07-15 11:00")
    late = _sig("2026-07-15 17:30")
    assert fc.session_filter([early, open_, late], "london") == [open_, late]


def test_winter_follows_its_own_offset() -> None:
    # Winter stamp 10:00 = 08:00 UTC = 08:00 London: in. Stamp 09:00 = 07:00 London: out.
    a, b = _sig("2026-01-15 09:00"), _sig("2026-01-15 10:00")
    assert fc.session_filter([a, b], "london") == [b]


def test_ny_and_asia_windows() -> None:
    ny = _sig("2026-07-15 16:00")        # 13:00 UTC = 09:00 New York
    asia = _sig("2026-07-15 04:00")      # 01:00 UTC = 10:00 Tokyo
    assert fc.session_filter([ny, asia], "ny") == [ny]
    assert fc.session_filter([ny, asia], "asia") == [asia]


def test_all_unknown_and_untimed_signals_are_kept() -> None:
    s, bare = _sig("2026-07-15 04:00"), SimpleNamespace(time=None)
    assert fc.session_filter([s], "all") == [s]
    assert fc.session_filter([s], "overlap") == [s]
    assert fc.session_filter([bare], "london") == [bare]


def test_the_scalp_london_mask_reads_the_broker_clock() -> None:
    from desks.mt5.research import scalp_family_expansion as fam
    idx = pd.DatetimeIndex(["2026-07-15 10:30", "2026-07-15 13:30"], tz="UTC")
    # 10:30 stamp = 07:30 UTC = 08:30 London (in 08-12); 13:30 stamp = 11:30 London (in).
    assert fam._session_mask(idx, "london").tolist() == [True, True]
    idx2 = pd.DatetimeIndex(["2026-07-15 08:30", "2026-07-15 14:30"], tz="UTC")
    # 08:30 stamp = 06:30 London (out); 14:30 stamp = 12:30 London (out). The old reading had
    # both inside London's 08-12.
    assert fam._session_mask(idx2, "london").tolist() == [False, False]
