"""The cash-carry LEG-MODE vocabulary, and what each mode means for a maker-share measurement.

ONE vocabulary, two readers (R0324 + R0064). `run_cashcarry_executor` stamps every trade row with
`spot_mode`/`fut_mode` -- one string PER LEG, because a pair can rest maker on spot and cross taker
on futures. Two organs then measure maker share off those strings (`scripts/fill_quality_monitor`
and `scripts/run_trade_forensics`), and before this module they each carried their own idea of what
the strings mean. Two readers of one tape that disagree do not produce two opinions; they produce
two numbers for one fact, and the desk cannot tell which one is the defect.

THE MODE THAT IS NOT A FILL. `already-flat` is written by `_close_goal_state` when the venue says
the leg is ALREADY flat -- no order was placed, nothing was filled, no fee was paid. Counting it in
a maker-share denominator is not a rounding error, it is a category error: it deflates the share
with legs that never had the chance to be maker, and the deflation is a FALSE INTEGRITY FLAG
against the 0.60 target (R0064). It is excluded from the denominator here, once, for both readers.

Every OTHER known mode did put an order on the venue and so stays in the denominator, scored
non-maker unless it is a confirmed maker fill. That direction is deliberate: fail closed, so an
unconfirmed leg can only ever push the measured share DOWN, never up past the target.

This module is deliberately dependency-free (no venue clients, no I/O) so a read-only monitor can
import it without acquiring keys or a network.
"""

from __future__ import annotations

#: Confirmed maker fill: the post-only quote rested and left the book without a cancel.
MAKER_MODES = frozenset({"maker"})

#: An order WAS placed and it was not a confirmed maker fill -- in the denominator, scored taker.
#:   taker               -- crossed the spread outright (fast-close path / no passive quote)
#:   taker_fallback      -- the resting quote did not fill in the wait; cancelled + market
#:   maker_pending       -- post-only accepted, outcome not yet resolved (fails CLOSED: a leg is
#:                          maker only once confirmed)
#:   limit_only_unfilled -- live_guard degraded mode: quote cancelled, no taker chase, no fill
#:   mkt / limit         -- `_mkt_or_limit` reconcile covers (market, else post-only at the touch)
NON_MAKER_MODES = frozenset({
    "taker", "taker_fallback", "maker_pending", "limit_only_unfilled", "mkt", "limit",
})

#: NO ORDER WAS PLACED. Excluded from every maker-share denominator -- see the module docstring.
#: `_mkt_or_limit` also returns "" for "nothing placed"; `_norm` maps that (and None) here too.
NO_ORDER_MODES = frozenset({"already-flat", ""})

#: The full vocabulary. A mode outside this set is UNKNOWN: the tape has grown a string this
#: reader has never been taught, which is a schema question, not a fill outcome.
KNOWN_MODES = MAKER_MODES | NON_MAKER_MODES | NO_ORDER_MODES


def _norm(mode: object) -> str:
    """Mode string as written on the tape; anything not a string reads as 'nothing recorded'."""
    return mode.strip() if isinstance(mode, str) else ""


def is_known(mode: object) -> bool:
    """Is this a mode string this desk actually understands?

    Readers use it to tell "we measured a taker leg" from "we cannot read this tape at all" -- the
    difference between a finding and a measurement failure.
    """
    return _norm(mode) in KNOWN_MODES


def placed_order(mode: object) -> bool:
    """Did this leg put an order on the venue, i.e. does it belong in the maker denominator?

    False ONLY for the no-order markers (`already-flat`, nothing recorded). An unknown mode counts
    as an order placed and scores non-maker: that is the tightening direction, never the loosening
    one -- an unreadable leg can lower a measured maker share but can never lift it over target.
    """
    return _norm(mode) not in NO_ORDER_MODES


def is_maker(mode: object) -> bool:
    """True only for a CONFIRMED maker fill. Every other mode -- unknown ones included -- is not."""
    return _norm(mode) in MAKER_MODES
