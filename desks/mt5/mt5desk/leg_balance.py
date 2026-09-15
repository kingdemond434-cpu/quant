"""Size a new order by the currency leg it ADDS TO, not by the symbol it is written in.

WHAT THIS COST, MEASURED 2026-09-15. Eight forex positions closed that day and all eight closed
on their stop, for -34.05 EUR. It read like eight bad signals. It was not: EURCHF short x4 and
USDCHF short x2 are both LONG CHF, so six of the eight were ONE BET charged six times, and a
single CHF move collected all six at once. EURGBP was a third short into the same move. The two
CHFNOK shorts -- the only position on a different leg -- were the only ones still in profit.

Nothing in the desk objected, and that is the defect. `independence.factor_k_eff` already
decomposes the book into currency legs and already reports things like `n_effective 1.019 across
17 sleeves`; it scales the TOTAL heat budget and, in its own words, "sizes nothing". So the desk
could see that seventeen positions were one bet and still hand the eighteenth a full-size order
on that same leg.

WHY THIS IS NOT A RISK REDUCTION, and the distinction is the principal's standing order rather
than a technicality. A cap that shrinks the book is refused here. This does not shrink it: it is
TWO-SIDED and roughly heat-neutral by construction. An order that piles onto a leg the book is
already long gets less; an order on a leg the book does not hold gets MORE, up to the same bound.
The total heat is decided upstream by `heat_budget` and is untouched. What changes is WHICH bets
that heat buys -- which is the principal's own definition of Tier-1: "MORE independent positive-
Elog bets inside the same heat, never a smaller book."

AND IT RAISES E[log W] RATHER THAN INSURING AGAINST A TAIL (Rule 1). For correlated bets the
growth-optimal allocation is not proportional to each bet's edge but to the edge net of what the
book already holds; concentrating n positions on one factor multiplies variance by ~n while
multiplying expected log-return by ~1. Spreading the same heat across legs raises n_eff, and
E[log W] rises with n_eff at fixed heat. The missed-growth ledger records what the damping cost
on the other side, so the claim stays falsifiable rather than assumed.

NONE IS A REAL ANSWER. When the decomposition cannot be trusted -- an unrecognised symbol, an
unreadable book -- the multiplier is 1.0 with a stated reason, never a guess and never a silent
shrink.
"""
from __future__ import annotations

import os
from typing import Any, Mapping

#: The multiplier's bounds. SYMMETRIC ON PURPOSE: the same distance below 1.0 that a fully
#: duplicated leg is damped, a fully fresh leg is boosted. An asymmetric band would be a
#: reduction wearing a balancing word.
LEG_MULT_MIN = float(os.environ.get("LEG_MULT_MIN", "0.55"))
LEG_MULT_MAX = float(os.environ.get("LEG_MULT_MAX", "1.45"))

#: The share of the book's gross leg exposure ONE leg may hold before damping starts. Above it
#: the multiplier falls toward LEG_MULT_MIN; well below it the multiplier rises toward
#: LEG_MULT_MAX. 1/k for a k-leg book is the neutral point, so this is stated as a floor on that:
#: with fewer than ~4 legs open the book is small enough that damping would be noise.
NEUTRAL_SHARE = float(os.environ.get("LEG_NEUTRAL_SHARE", "0.25"))


def book_exposures(positions: Any) -> dict[str, float]:
    """Per-symbol signed exposure (lots, + long base) from live positions.

    Keyed by symbol because that is what `fx_factors.decompose` consumes; it does the currency
    arithmetic, so this deliberately does none.
    """
    out: dict[str, float] = {}
    for p in positions or []:
        sym = str(getattr(p, "symbol", "") or "")
        if not sym:
            continue
        vol = float(getattr(p, "volume", 0.0) or 0.0)
        sign = 1.0 if int(getattr(p, "type", 0)) == 0 else -1.0
        out[sym] = out.get(sym, 0.0) + sign * vol
    return out


def leg_shares(exposures: Mapping[str, float]) -> tuple[dict[str, float], float]:
    """(net exposure per currency leg, gross across legs). Empty when undecomposable."""
    try:
        from libs.risk.fx_factors import decompose
    except ImportError:
        return {}, 0.0
    try:
        d = decompose(exposures)
    except Exception:                                               # noqa: BLE001
        return {}, 0.0
    # `by_currency` and `by_metal` are the module's own field names -- read them from the object
    # rather than assuming, because an attribute this code invents silently yields an empty book
    # and an empty book reads as "nothing is crowded", which is the wrong way for this to fail.
    legs: dict[str, float] = {}
    for attr in ("by_currency", "by_metal"):
        part = getattr(d, attr, None)
        if isinstance(part, dict):
            for k, v in part.items():
                legs[k] = legs.get(k, 0.0) + float(v)
    gross = float(getattr(d, "gross", 0.0) or 0.0) or sum(abs(v) for v in legs.values())
    return legs, gross


def multiplier(symbol: str, side: int, positions: Any) -> tuple[float, str]:
    """How much of a full-size order this symbol should get, given what the book already holds.

    `side` is +1 long / -1 short, the desk's convention. Returns (multiplier, reason) and the
    reason is always worth logging: a sleeve that is damped needs to say which leg damped it, or
    the next session re-discovers this the expensive way.
    """
    exposures = book_exposures(positions)
    legs, gross = leg_shares(exposures)
    if not legs or gross <= 0:
        return 1.0, "leg balance 1.00: book has no decomposable exposure yet"

    try:
        from libs.risk.fx_factors import split_pair
        pair = split_pair(symbol)
    except Exception:                                               # noqa: BLE001
        pair = None
    if pair is None:
        return 1.0, f"leg balance 1.00: {symbol} has no currency decomposition"
    base, quote = pair

    # The legs THIS order would add to, with its own sign. A long EURCHF adds +EUR and -CHF.
    adds = {base: float(side), quote: -float(side)}

    # How much of the book's gross exposure already sits on those legs IN THE SAME DIRECTION.
    # Opposite-direction exposure is not crowding, it is offset, and must not be damped.
    same_dir = 0.0
    for ccy, sign in adds.items():
        held = legs.get(ccy, 0.0)
        if held * sign > 0:
            same_dir += abs(held)
    share = same_dir / gross if gross > 0 else 0.0

    n_legs = sum(1 for v in legs.values() if abs(v) > 1e-9)
    n_pos = sum(1 for _ in (positions or []))
    # THE QUIET GUARD IS ON POSITION COUNT, NOT LEG COUNT, AND THE DIFFERENCE IS THE WHOLE POINT.
    #
    # This first read `if n_legs < 4: return 1.0`, reasoning that a book with few legs is too
    # small for crowding to mean anything. That is exactly backwards: A CONCENTRATED BOOK HAS FEW
    # LEGS BY DEFINITION. Replaying the day's actual cluster through it -- EURCHF short x4 then
    # USDCHF short x2, which touch only EUR, CHF and USD -- the guard returned 1.00 for every one
    # of the six, switching the damping off precisely in the case it was written for.
    #
    # One open position cannot be crowded by anything, so that is the only case worth excusing.
    if n_pos < 2:
        return 1.0, f"leg balance 1.00: {n_pos} position(s) open, nothing to crowd against"

    # Linear in the crowding share, clamped. At NEUTRAL_SHARE the multiplier is exactly 1.0, so a
    # book already spread evenly is sized exactly as it is today and this changes nothing.
    if share >= NEUTRAL_SHARE:
        span = max(1e-9, 1.0 - NEUTRAL_SHARE)
        t = min(1.0, (share - NEUTRAL_SHARE) / span)
        mult = 1.0 - t * (1.0 - LEG_MULT_MIN)
        verdict = "crowded"
    else:
        span = max(1e-9, NEUTRAL_SHARE)
        t = min(1.0, (NEUTRAL_SHARE - share) / span)
        mult = 1.0 + t * (LEG_MULT_MAX - 1.0)
        verdict = "fresh"
    mult = max(LEG_MULT_MIN, min(LEG_MULT_MAX, mult))
    return mult, (f"leg balance {mult:.2f} ({verdict}): {symbol} "
                  f"{'long' if side > 0 else 'short'} adds to {base}/{quote}; book already holds "
                  f"{share:.0%} of its gross exposure on those legs in the same direction "
                  f"({n_legs} legs, neutral at {NEUTRAL_SHARE:.0%})")
