"""A fill rate may only count legs where a fill was attempted.

R0029 read "spot maker share is 23.8% vs a 60% target while futures is 61.9%". Both numbers were
computed over every leg carrying a mode string, and a third of those legs never sent an order:

  * `already-flat` -- the leg was already square, so nothing was placed (4 spot, 8 fut of 21);
  * `close` events -- closes BYPASS the maker path deliberately. Post-only closes carry neither
    reduceOnly nor a venue size cap, and twice accumulated resting fills that bought a short
    through zero into a long (+916,772 and +1,138,985 units). "Patient on opens, fast on closes"
    is the rule; counting it as a failed maker fill scores a safety policy as an execution defect.

The distortion was not even -- futures carries twice as many already-flat legs as spot -- so the
metric understated the two legs unequally and hid the real shape: on genuine attempts futures
converts 100% and the whole gap is the spot quote.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "rtf", Path(__file__).resolve().parents[2] / "scripts" / "run_trade_forensics.py")
assert _SPEC and _SPEC.loader
_M = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_M)


def _row(event: str, spot: str | None = None, fut: str | None = None) -> dict:
    r: dict = {"event": event}
    if spot:
        r["spot_mode"] = spot
    if fut:
        r["fut_mode"] = fut
    return r


def test_already_flat_legs_are_not_failed_maker_fills() -> None:
    trades = [_row("open", "maker", "maker"), _row("open", "already-flat", "already-flat")]
    assert _M._leg_share(trades, "spot_mode") == 1.0
    assert _M._leg_share(trades, "fut_mode") == 1.0


def test_market_only_closes_are_excluded() -> None:
    # A close is market-only BY DESIGN; scoring it as a maker miss penalises the safety rule.
    trades = [_row("open", "maker", "maker"), _row("close", "taker", "taker")]
    assert _M._leg_share(trades, "spot_mode") == 1.0


def test_topups_and_opens_both_count() -> None:
    trades = [_row("open", "maker"), _row("topup", "taker_fallback")]
    assert _M._leg_share(trades, "spot_mode") == 0.5


def test_a_real_taker_fallback_on_an_open_still_counts_against_us() -> None:
    """The correction must not become a way to make the number look good."""
    trades = [_row("open", "taker_fallback", "maker") for _ in range(4)]
    assert _M._leg_share(trades, "spot_mode") == 0.0
    assert _M._leg_share(trades, "fut_mode") == 1.0


def test_no_instrumented_records_reports_none_not_zero() -> None:
    assert _M._leg_share([_row("open")], "spot_mode") is None
    assert _M._leg_share([], "spot_mode") is None


def test_all_excluded_reports_none_rather_than_a_perfect_score() -> None:
    trades = [_row("open", "already-flat"), _row("close", "taker")]
    assert _M._leg_share(trades, "spot_mode") is None
