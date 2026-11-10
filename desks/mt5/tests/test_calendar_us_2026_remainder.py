"""The 2026 remainder of calendar_us.FIXED matches the official rows read on 2026-11-10, and
2027 is still a refusal (a FOMC-only year must never read as a complete one)."""
from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import calendar_us as cal  # noqa: E402
from mt5desk import news_fence as nf  # noqa: E402

#: (family, UTC time). November and December 2026 are both standard time: ET is UTC-5.
OFFICIAL = [
    ("NFP", datetime(2026, 11, 6, 13, 30, tzinfo=UTC)),
    ("CPI", datetime(2026, 11, 10, 13, 30, tzinfo=UTC)),
    ("PPI", datetime(2026, 11, 13, 13, 30, tzinfo=UTC)),
    ("GDP", datetime(2026, 11, 25, 13, 30, tzinfo=UTC)),
    ("PCE", datetime(2026, 11, 25, 13, 30, tzinfo=UTC)),
    ("NFP", datetime(2026, 12, 4, 13, 30, tzinfo=UTC)),
    ("FOMC", datetime(2026, 12, 9, 19, 0, tzinfo=UTC)),
    ("CPI", datetime(2026, 12, 10, 13, 30, tzinfo=UTC)),
    ("PPI", datetime(2026, 12, 15, 13, 30, tzinfo=UTC)),
    ("GDP", datetime(2026, 12, 23, 13, 30, tzinfo=UTC)),
    ("PCE", datetime(2026, 12, 23, 13, 30, tzinfo=UTC)),
]


def test_november_and_december_2026_are_exactly_the_official_rows() -> None:
    rel = cal.releases(date(2026, 11, 1), date(2026, 12, 31))
    got = sorted((r.family, r.when) for r in rel if r.tier == 1)
    assert got == sorted(OFFICIAL)


def test_the_monthly_families_are_all_dated_and_the_undated_minutes_are_a_named_gap() -> None:
    # Every monthly family is dated for the rest of 2026. The October-meeting minutes have no
    # official date yet: that is published as a gap for November, never a quiet month.
    assert nf.uncovered_families(date(2026, 11, 1), date(2026, 12, 31)) == \
        ("FOMC_MINUTES:2026-11",)
    assert nf.uncovered_families(date(2026, 12, 1), date(2026, 12, 31)) == ()
    v = nf.verdict(datetime(2026, 11, 18, 19, 0, tzinfo=UTC), flag_path=Path("/nonexistent"))
    assert not v.calendar_ok and "FOMC_MINUTES:2026-11" in v.uncovered


def test_a_dated_row_clears_the_undated_gap_by_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = (*cal.FIXED[2026], ("FOMC_MINUTES", 11, 18, 14, 0))
    monkeypatch.setitem(cal.FIXED, 2026, rows)
    assert nf.uncovered_families(date(2026, 11, 1), date(2026, 11, 30)) == ()


def test_the_rule_derived_nfp_agrees_with_the_official_dates() -> None:
    # FRED release 50: 2026-11-06 and 2026-12-04, both first Fridays, so no NFP_MOVED row.
    assert (2026, 11) not in cal.NFP_MOVED and (2026, 12) not in cal.NFP_MOVED


def test_past_months_nothing_official_was_read_for_stay_published_gaps() -> None:
    gaps = nf.uncovered_families(date(2026, 9, 1), date(2026, 10, 31))
    assert "CPI:2026-09" in gaps and "CPI:2026-10" in gaps


def test_2027_is_still_a_refusal_not_a_fomc_only_year() -> None:
    assert 2027 not in cal.FIXED
    with pytest.raises(ValueError):
        cal.releases(date(2027, 1, 1), date(2027, 1, 31))
    assert nf.uncovered_families(date(2027, 1, 1), date(2027, 1, 31)) == ("ALL:2027",)


def test_a_december_window_into_the_new_year_names_the_whole_missing_year() -> None:
    # In December the liveness check looks at this and next whole month: 2027 must be named.
    assert "ALL:2027" in nf.uncovered_families(date(2026, 12, 1), date(2027, 1, 31))


def test_every_fixed_batch_names_its_source_pages() -> None:
    src = cal.FIXED_SOURCES["2026-11..12"]
    assert len(src["fed"].split()[-1]) == 64 and len(src["bea"].split()[-1]) == 64
