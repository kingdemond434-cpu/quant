"""The server clock, the truncated-name ledger match and the gold-window fold (2026-09-25).

Every MT5 time is the venue's wall clock stamped as if it were UTC. These tests pin the one
helper the gateway now compares such times against, the ledger match that stopped counting zero
trades for long-named sleeves, and the fold of versioned gold rows into their parent window.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk import decision_core as dc  # noqa: E402
from mt5desk import live_policy as lp  # noqa: E402


def test_offset_follows_the_new_york_close_rule() -> None:
    assert dc.broker_offset_hours(datetime(2026, 9, 25, 12, tzinfo=UTC)) == 3
    assert dc.broker_offset_hours(datetime(2026, 11, 1, 12, tzinfo=UTC)) == 2  # US DST ends
    assert dc.broker_offset_hours(datetime(2026, 10, 31, 12, tzinfo=UTC)) == 3
    assert dc.broker_offset_hours(datetime(2026, 3, 7, 12, tzinfo=UTC)) == 2
    assert dc.broker_offset_hours(datetime(2026, 3, 8, 12, tzinfo=UTC)) == 3  # US DST starts
    assert dc.broker_offset_hours(datetime(2027, 1, 15, tzinfo=UTC)) == 2


def test_server_now_is_utc_plus_the_offset_labelled_utc() -> None:
    t = datetime(2026, 9, 25, 1, 29, 3, tzinfo=UTC)
    # The measured case: a Fusion tick stamped 04:29:03 when true UTC was 01:29:03.
    assert dc.server_now(t) == datetime(2026, 9, 25, 4, 29, 3, tzinfo=UTC)
    assert dc.server_now(datetime(2026, 12, 1, tzinfo=UTC)).hour == 2


def test_bracket_deadline_on_the_server_clock_uses_window_hours() -> None:
    # A summer asia bracket placed at 07:05 server ends at the next window (10:00 server), not
    # three hours later as the true-UTC comparison made it.
    now_srv = dc.server_now(datetime(2026, 9, 25, 4, 5, tzinfo=UTC))
    until = dc.bracket_deadline("gold_asia", now=now_srv)
    nxt = min(float(w[1]) for w in dc.GOLD_WINDOWS if float(w[1]) > float(
        next(w[1] for w in dc.GOLD_WINDOWS if w[0] == "asia")))
    assert until.hour == int(nxt) and until.date() == now_srv.date()


def test_ledger_rows_with_a_truncated_name_count_for_their_sleeve(tmp_path: Path) -> None:
    name = "xau_m5_anti_breakout_overlap"
    stored = f"DW{name}"[:dc.COMMENT_MAX][2:]
    assert stored != name, "the fixture must exercise the truncation"
    ledger = tmp_path / "live_ledger.jsonl"
    ledger.write_text("\n".join(json.dumps({"sleeve": s}) for s in
                                (stored, stored, name, "xau_m5_anti", "other")) + "\n",
                      encoding="utf-8")
    assert dc.sleeve_live_n(name, ledger) == 3


def test_a_prefix_of_another_name_is_not_this_sleeve() -> None:
    assert not dc.ledger_sleeve_matches("gold_asia", "gold_asia_v2")
    assert not dc.ledger_sleeve_matches("", "gold_asia")
    assert not dc.ledger_sleeve_matches(None, "gold_asia")
    assert dc.ledger_sleeve_matches("gold_asia", "gold_asia")


def test_versioned_gold_rows_fold_into_their_window() -> None:
    pol = lp.Policy()
    for n in ("gold_asia_v2", "gold_london_am_v3", "gold_afternoon_v4", "gold_london_am_v12"):
        why = lp.refuse({"name": n, "symbol": "XAUUSD"}, pol)
        assert why and why.startswith("folded into gold_"), (n, why)
    for n in ("gold_asia", "gold_london_am", "gold_afternoon", "xau_m5_anti_breakout_overlap",
              "gold_asia_vx", "gold_asia_v2_extra"):
        assert lp.refuse({"name": n, "symbol": "XAUUSD"}, pol) is None, n


def test_the_parent_window_is_named_by_the_alias() -> None:
    assert lp.gold_window_alias({"name": "gold_afternoon_v3"}) == "gold_afternoon"
    assert lp.gold_window_alias({"name": "gold_afternoon"}) is None


def test_a_timeframe_carried_only_in_params_is_still_banned() -> None:
    why = lp.refuse({"name": "x", "symbol": "XAUUSD", "params": {"timeframe": "M15"}},
                    lp.Policy())
    assert why and "M15" in why

