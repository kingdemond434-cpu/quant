"""The two-lane mandate is enforced at the DOCKET's door, not only the backtest's.

THE PRINCIPAL, 2026-09-06: single-name equities are traded on news, financial reports and
earnings reaction -- never hunted for statistical hypotheses. Routing was wired at
`run_external_backtest.route_by_lane`, which is the BACKTEST's door; nothing stood at the
docket's.

MEASURED 2026-09-12 by `frontier_map`: 10,927 of 21,582 docket cells -- 51% -- sat on symbols
`may_hypothesise` returns False for, holding ZERO certificates between them at a 0.046% upper
bound, and 447 of them were first seen in September, AFTER the mandate. The leak was live.

WHY A TEST AND NOT JUST A FIX. Trial count is a shared cost: every equity cell raised the bar
every FX and metals cell had to clear, so this door is worth more to the desk's growth than most
things it could gate. A door with no test is a door that reopens the next time someone edits the
donation path, and nothing would say so -- the docket would simply start filling again.
"""
from __future__ import annotations

import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.proposer_common import _lane_filtered  # noqa: E402


def test_hypothesis_lane_symbols_are_admitted() -> None:
    """Gold and FX are the hypothesis lane and must pass untouched."""
    ok, refused = _lane_filtered([{"symbol": "XAUUSD", "family": "session_range_breakout"},
                                  {"symbol": "EURUSD", "family": "momentum_volgate"}])
    assert [c["symbol"] for c in ok] == ["XAUUSD", "EURUSD"]
    assert refused == []


def test_single_name_equities_are_refused_with_a_reason() -> None:
    """An equity hypothesis is turned away AND says why -- a silent drop is not a refusal."""
    ok, refused = _lane_filtered([{"symbol": "Apple", "family": "discovered"},
                                  {"symbol": "GoldmanSachs", "family": "discovered"}])
    assert ok == []
    assert {r["symbol"] for r in refused} == {"Apple", "GoldmanSachs"}
    for r in refused:
        assert "two-lane mandate" in r["why"]


def test_a_row_with_no_symbol_is_not_refused() -> None:
    """ABSENCE IS NOT A VERDICT (L1.28a). A row that names no instrument has not been shown to
    be in the wrong lane, and refusing it would turn a missing field into a policy breach."""
    ok, refused = _lane_filtered([{"family": "macro_conditional"}])
    assert len(ok) == 1
    assert refused == []


def test_the_filter_never_takes_the_intake_dark() -> None:
    """A mixed batch loses only the wrong-lane rows; the rest still reach the docket."""
    ok, refused = _lane_filtered([{"symbol": "XAUUSD", "family": "f"},
                                  {"symbol": "Apple", "family": "f"},
                                  {"symbol": "GBPUSD", "family": "f"}])
    assert [c["symbol"] for c in ok] == ["XAUUSD", "GBPUSD"]
    assert len(refused) == 1
