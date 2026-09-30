from __future__ import annotations

from datetime import date

from desks.mt5.mech_split import carry_to_next_trading_day


def test_new_york_state_is_not_visible_until_next_trading_day() -> None:
    friday = date(2026, 9, 25)
    monday = date(2026, 9, 28)
    states = carry_to_next_trading_day(
        {friday: "FAILED_BREAK", monday: "NORMAL_DAY"},
        [friday, friday, monday, monday],
    )
    assert friday not in states
    assert states[monday] == "FAILED_BREAK"
