"""Return-on-capital-utilized -- the reporting invariant of R0287.

THE ERA'S LESSON, ADOPTED AS LAW. Quantopian 2019: a headline 190% return recomputed to 58%
against a 128% benchmark once margin was counted -- the return had been quoted on
portfolio_value while the strategy drew far more cash than the portfolio showed. The community's
own reaction ("blindly trusting of something so critically flawed") is the epitaph of every desk
that reports returns on a denominator leverage can hide in.

THIS DESK HAS HIT THE SAME SHAPE THREE TIMES: R0234 (LIVE equity undercount ~25x), R0235 (testnet
profit sizing live capital), and the 13,155/4,500 equity split. The class is recurring, so the
remedy is structural: ONE named helper for the computation, ONE vocabulary for the denominator,
and a fence (scripts/check_capital_basis.py) that fails any performance artifact reporting a
return without declaring which denominator it used.

A return quoted without its capital basis is not a measurement -- it is a numerator wearing a
measurement's clothes (the L1.46 shape, one ledger up).
"""
from __future__ import annotations

from typing import Any

#: The denominators a performance artifact may declare. `capital_utilized` is the invariant's
#: preferred basis -- max cash actually drawn, margin included. The others are legal ONLY because
#: they are visible: a reader can reject them, which is impossible while the basis is unstated.
BASES: tuple[str, ...] = (
    "capital_utilized",     # max cash drawn incl. margin -- the honest leveraged-book basis
    "initial_equity",       # fixed inception denominator (rails, drawdown ratios)
    "venue_equity",         # what the venue attests, marked to venue truth
    "portfolio_value",      # the Quantopian trap: legal to declare, impossible to hide
)


def return_on_capital_utilized(pnl_usd: float, capital_utilized_usd: float) -> float:
    """The invariant computation: PnL over capital ACTUALLY UTILIZED, as a fraction.

    Refuses (ValueError) a zero or negative denominator rather than returning inf/None -- a
    return computed on no capital is not a large return, it is a division error upstream, and
    every caller that would swallow it publishes fiction.
    """
    if not capital_utilized_usd or capital_utilized_usd <= 0:
        raise ValueError(
            f"capital_utilized_usd={capital_utilized_usd!r}: a return needs a positive "
            "denominator of capital actually drawn -- refuse, never fabricate")
    return float(pnl_usd) / float(capital_utilized_usd)


def declare(basis: str, capital_usd: float | None = None) -> dict[str, Any]:
    """The fragment a performance artifact embeds beside any return it reports.

    Unknown basis strings are refused: an unrecognised denominator name defeats the entire
    invariant (the fence can only verify vocabulary it knows).
    """
    if basis not in BASES:
        raise ValueError(f"capital basis {basis!r} not in {BASES}")
    out: dict[str, Any] = {"capital_basis": basis}
    if capital_usd is not None:
        out["capital_basis_usd"] = float(capital_usd)
    return out
