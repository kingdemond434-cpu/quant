"""The discretionary sleeve's risk process, pinned on the rules that survive a losing streak.

THE ONE THAT MATTERS MOST is `test_SIZE_DOES_NOT_RISE_AFTER_A_LOSS`. Progression after a loss --
martingale, averaging down, "recovering" the last trade -- is what produces the long smooth equity
curves that dominate short leaderboards and end in a single terminal loss (III.15). It is also the
easiest thing in the world to add later, in one line, for what feels at the time like a good
reason. This test is what makes that edit fail loudly instead of silently.
"""

from __future__ import annotations

import json
from pathlib import Path

from libs.execution.discretionary_sleeve import (
    Decision,
    RuleSignal,
    SleeveState,
    journal,
    size_and_check,
)


def _sig(**kw: object) -> RuleSignal:
    base: dict = {"rule_id": "liq_sweep_reclaim", "symbol": "BTCUSDT", "side": "BUY",
                  "entry_price": 100.0, "stop_price": 98.0,
                  "forced_participant": "late longs stopped out into the sweep"}
    base.update(kw)
    return RuleSignal(**base)


def test_FIXED_FRACTIONAL_SIZE_COMES_FROM_THE_STOP_DISTANCE() -> None:
    """1% of $10,000 is $100 at risk; a $2 stop distance is 50 units. The stop is what makes the
    size computable -- without it, 'how much do we buy' is a judgement call again."""
    d = size_and_check(_sig(), SleeveState(equity_usd=10_000.0))
    assert d.take
    assert d.risk_usd == 100.0
    assert abs(d.qty - 50.0) < 1e-9


def test_SIZE_DOES_NOT_RISE_AFTER_A_LOSS() -> None:
    """THE LINE THIS FILE EXISTS TO DEFEND. A sleeve that sizes up to recover the last trade has a
    smooth curve and one terminal loss."""
    flat = size_and_check(_sig(), SleeveState(equity_usd=10_000.0, loss_streak=0))
    streak = size_and_check(_sig(), SleeveState(equity_usd=10_000.0, loss_streak=5))
    assert flat.qty == streak.qty
    assert flat.risk_usd == streak.risk_usd
    assert "CONSTANT" in streak.why


def test_A_ZERO_RISK_DISTANCE_IS_REFUSED_NOT_DIVIDED_BY() -> None:
    """Entry == stop would divide by zero and return an infinite quantity -- the single most
    expensive arithmetic error available in this file."""
    d = size_and_check(_sig(stop_price=100.0), SleeveState(equity_usd=10_000.0))
    assert d.refused and "risk distance is zero" in d.why


def test_THE_DAILY_LOSS_CAP_ENDS_THE_DAY() -> None:
    """Checked BEFORE sizing, so a losing day cannot be argued past by a good-looking setup."""
    d = size_and_check(_sig(), SleeveState(equity_usd=10_000.0, realised_pnl_today_usd=-300.0))
    assert d.refused and "daily loss cap reached" in d.why


def test_THE_CAP_IS_ON_LOSSES_NOT_ON_ACTIVITY() -> None:
    """A profitable day is not a used-up day. Folding gains into the cap would stop the sleeve
    exactly when it is working."""
    d = size_and_check(_sig(), SleeveState(equity_usd=10_000.0, realised_pnl_today_usd=+900.0))
    assert d.take


def test_CONCURRENT_POSITIONS_ARE_CAPPED() -> None:
    d = size_and_check(_sig(), SleeveState(equity_usd=10_000.0, open_positions=2))
    assert d.refused and "already open" in d.why
    assert "CORRELATION" in d.why


def test_A_SUB_MINIMUM_NOTIONAL_IS_REFUSED_NOT_WIDENED() -> None:
    """Widening the risk fraction to reach the venue minimum is the same error as rounding a clip
    up to it: the limit is breached silently, in the direction that loses more.

    A WIDE STOP IS WHAT MAKES A POSITION TOO SMALL TO PLACE, which is the reverse of the intuition
    and worth stating: risking a fixed $2 across a $50 stop distance buys 0.04 units, so the
    notional is $4. The stop distance, not the conviction, is what the book cannot afford."""
    d = size_and_check(_sig(stop_price=50.0), SleeveState(equity_usd=200.0), min_notional_usd=10.0)
    assert d.refused
    assert "below the venue minimum" in d.why and "BOOK is" in d.why


def test_A_BAD_SIDE_IS_REFUSED() -> None:
    assert size_and_check(_sig(side="LONG"), SleeveState(equity_usd=10_000.0)).refused


def test_ZERO_EQUITY_IS_REFUSED() -> None:
    assert size_and_check(_sig(), SleeveState(equity_usd=0.0)).refused


def test_THE_JOURNAL_RECORDS_REFUSALS_TOO(tmp_path: Path) -> None:
    """A sleeve journalling only its trades cannot tell 'the rule fired twice' from 'the rule fired
    forty times and the risk process blocked thirty-eight' -- different strategies, one hit rate."""
    p = tmp_path / "j.jsonl"
    journal(size_and_check(_sig(), SleeveState(equity_usd=10_000.0)), p)
    journal(size_and_check(_sig(), SleeveState(equity_usd=10_000.0, open_positions=9)), p)

    rows = [json.loads(x) for x in p.read_text("utf-8").splitlines()]
    assert len(rows) == 2
    assert [r["taken"] for r in rows] == [True, False]
    assert rows[1]["rule_id"] == "liq_sweep_reclaim"
    assert "why" in rows[1]


def test_THE_JOURNAL_IS_APPEND_ONLY(tmp_path: Path) -> None:
    """A journal that can be rewritten is not evidence, for the same reason a forward clock whose
    history can be edited is not evidence."""
    p = tmp_path / "j.jsonl"
    for _ in range(3):
        journal(size_and_check(_sig(), SleeveState(equity_usd=10_000.0)), p)
    assert len(p.read_text("utf-8").splitlines()) == 3


def test_THE_SIGNAL_CARRIES_ITS_FORCED_PARTICIPANT() -> None:
    """From the hunt's own admission criterion: a candidate that cannot name who is forced to trade
    against you is a pattern, not a mechanism."""
    d = size_and_check(_sig(), SleeveState(equity_usd=10_000.0))
    assert "forced participant" in d.why
    assert d.signal["forced_participant"]


def test_A_DECISION_IS_JSON_SHAPED() -> None:
    d: Decision = size_and_check(_sig(), SleeveState(equity_usd=10_000.0))
    assert json.loads(json.dumps({"take": d.take, "qty": d.qty, **d.signal}))["qty"] == d.qty
