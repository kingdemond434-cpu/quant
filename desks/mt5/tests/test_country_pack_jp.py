"""Country pack `jp` and the rebuilt Japan department it reads.

`research/japan/{mandate,calendars,miners_policy}.py` were never committed (the box may still hold
them untracked). The rebuild lives in `countries/jp/` so an adoption can never overwrite the box's
originals, and the pack asks for the box's department first.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.countries.jp import calendars as C  # noqa: E402
from research.countries.jp import mandate as M  # noqa: E402
from research.countries.jp import miners_policy as P  # noqa: E402
from research.countries.jp import pack  # noqa: E402


def test_the_pack_imports_and_names_the_departments_instruments() -> None:
    assert pack.CODE == "JP" and pack.EXECUTABLE_INSTRUMENTS
    assert pack.EXECUTABLE_INSTRUMENTS[0] == "USDJPY"
    quoted = set(pack._quoted())
    if "JPN225" in quoted:
        assert "JPN225" in pack.EXECUTABLE_INSTRUMENTS, "the department's index was not read"
    assert set(pack.EXECUTABLE_INSTRUMENTS) <= quoted | {"USDJPY"}


def test_the_mandate_intersects_with_the_broker_and_derives_single_names() -> None:
    ex = M.executable({"USDJPY", "EURJPY", "JPN225", "UST10Y"})
    assert ex[:2] == ["USDJPY", "EURJPY"] and "JPN225" in ex and "UST10Y" not in ex
    for row in M.single_names():
        assert row["lane"] == "event" and row["tse_code"].isdigit()
        assert set(row["families"]) == {"event_reaction", "news_reaction"}


def test_tse_holidays_2026_follow_the_holiday_act() -> None:
    h = set(C.exchange_holidays(2026))
    for d in (date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 12), date(2026, 2, 11),
              date(2026, 2, 23), date(2026, 3, 20), date(2026, 4, 29), date(2026, 5, 4),
              date(2026, 5, 5), date(2026, 5, 6), date(2026, 7, 20), date(2026, 8, 11),
              date(2026, 9, 21), date(2026, 9, 22), date(2026, 9, 23), date(2026, 10, 12),
              date(2026, 11, 3), date(2026, 11, 23), date(2026, 12, 31)):
        assert d in h, d
    assert date(2026, 1, 3) not in h                     # a Saturday is not an exchange holiday
    assert all(d.weekday() < 5 for d in h)


def test_gotobi_rolls_back_to_a_trading_day() -> None:
    days = C.gotobi_days(2026, 5)
    assert date(2026, 5, 1) in days                        # the 5th is a holiday -> 1 May
    assert all(C.is_trading_day(d) for d in days)


def test_boj_days_are_never_invented() -> None:
    got = C.boj_meetings(1999)
    assert got["status"] == "UNMEASURED" and got["dates"] == []
    assert got["months"] == list(C.BOJ_MEETING_MONTHS)


def test_miners_policy_routes_through_the_lane_door_and_carries_culture() -> None:
    ok, why = P.may_mint("gotobi", "USDJPY", "fx_fixing_reversal")
    assert ok, why
    assert not P.may_mint("gotobi", "USDJPY", "news_reaction")[0]      # not its declaration
    assert not P.may_mint("nobody", "USDJPY", "carry")[0]
    c = P.culture("boj_policy")
    assert c["source_culture"] == "JP" and c["participant_structure"] == "policy_driven"
    assert c["failure_mode_hypothesis"]
