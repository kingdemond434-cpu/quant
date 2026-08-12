"""TOKENIZED-COMMODITY MOVES: DID THE METAL MOVE, OR DID THE WRAPPER DISLOCATE?

GRADUATES L0077. On 2026-08-05 the conviction seat read PAXGUSDT +4.002%/24h as a breakout in
gold. A single tokenized-commodity chart cannot tell those two stories apart, and they imply
OPPOSITE trades:

    the underlying repriced   -> the move is real, momentum/trend logic applies
    the wrapper dislocated    -> you are looking at an issuer or venue premium, and the trade is
                                 CONVERGENCE (short the premium), not momentum

The cheap discriminator is a second token on the SAME underlying from a DIFFERENT issuer. That
day, Tether Gold (XAUTUSDT) showed +3.957% over the same window -- 4.5bp apart, PAXG/XAUT ratio
1.0027 -- so the metal moved and the momentum reading was correct. Had XAUT been flat, the correct
trade was the opposite one.

WHY THIS IS A LIBRARY AND NOT A NOTE. The desk trades PAXGUSDT as its on-Binance gold analogue
(`scripts/run_conviction_trader.INSTRUMENTS`). A lesson about it that lives in a lessons file
reaches an organ only while that file fits in the injection budget, and the budget is a ranking --
it will fall out. A function the sizing path can call does not.

THE THREE-STATE RULE APPLIES HERE AS EVERYWHERE. A missing cross-issuer quote is UNVERIFIABLE,
never "confirmed": the whole point is that one chart is not enough, so failing to fetch the second
one leaves you with exactly the evidence that caused the error. UNVERIFIABLE does not block the
trade -- it is not a risk gate and pretending otherwise would make a data outage into a position
decision -- it removes the CONFIRMATION, and the caller must size on that.
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = ["CROSS_ISSUER", "Verdict", "classify", "peer_for"]

#: underlying -> the tokens the desk can quote on it, from INDEPENDENT issuers. Independence is
#: the entire mechanism: two tokens from the same issuer share the redemption plumbing that
#: dislocates, so they would agree while both were wrong.
CROSS_ISSUER: dict[str, tuple[str, ...]] = {
    "gold": ("PAXGUSDT",      # Paxos
             "XAUTUSDT"),     # Tether -- different issuer, different custody, same metal
}

#: How far two independently-issued claims on the same metal may drift over the same window and
#: still be read as the metal moving. 50bp is deliberately WIDE relative to the 4.5bp seen on
#: 2026-08-05: the failure this guards against is a premium BLOWOUT (whole percents), and a tight
#: band would fire on ordinary venue microstructure and be switched off within a week.
AGREE_BPS = 50.0

#: Below this the "move" is not a move and asking which kind it is measures noise. The desk's own
#: measured 24h noise floor on PAXG is 0.64%, so anything under it cannot be classified at all.
MIN_MOVE_PCT = 0.64


@dataclass(frozen=True)
class Verdict:
    """A reading, its reason, and -- when the answer is no -- what to do instead."""

    state: str                 # CONFIRMED | DISLOCATION | NOISE | UNVERIFIABLE
    gap_bps: float | None
    why: str
    trade: str                 # the direction this state implies, in words

    @property
    def confirmed(self) -> bool:
        """True ONLY for a cross-checked underlying move. UNVERIFIABLE is not a pass."""
        return self.state == "CONFIRMED"


def peer_for(symbol: str) -> str | None:
    """The independently-issued token to cross-check `symbol` against, or None."""
    sym = str(symbol or "").upper()
    for peers in CROSS_ISSUER.values():
        if sym in peers:
            other = [p for p in peers if p != sym]
            return other[0] if other else None
    return None


def classify(symbol: str, move_pct: float, peer_move_pct: float | None) -> Verdict:
    """Read a tokenized-commodity move against its cross-issuer twin.

    `move_pct` and `peer_move_pct` must cover the SAME window -- comparing a 24h move against a
    4h one measures the window, not the issuer, and would report a dislocation on every quiet day.
    A None peer means the quote could not be fetched, which is UNVERIFIABLE and never CONFIRMED.
    """
    peer = peer_for(symbol)
    if peer is None:
        return Verdict("UNVERIFIABLE", None,
                       f"{symbol} has no independently-issued twin on the desk's venues, so a "
                       "premium blowout and a real repricing are indistinguishable from here",
                       "size as if the move may be a wrapper artifact")

    # NOISE IS A PROPERTY OF THE PAIR, NOT OF ONE LEG, and the first version of this function got
    # that wrong -- it floored on `move_pct` alone, so a flat PAXG against a XAUT that ran 4%
    # returned NOISE. That is the most actionable state there is: the metal moved and the desk's
    # own instrument did not follow, i.e. PAXG is CHEAP to the underlying. Reading it as "nothing
    # happened" discards a convergence trade and does it silently.
    moves = [abs(float(move_pct))]
    if peer_move_pct is not None:
        moves.append(abs(float(peer_move_pct)))
    if max(moves) < MIN_MOVE_PCT:
        return Verdict("NOISE", None,
                       f"neither leg cleared the measured {MIN_MOVE_PCT}% 24h noise floor "
                       f"({move_pct:+.3f}% here) -- there is no move to attribute",
                       "no trade; the question does not arise")

    if peer_move_pct is None:
        return Verdict("UNVERIFIABLE", None,
                       f"{peer} did not quote, so this is the single-chart evidence that caused "
                       "the 2026-08-05 misread -- the move is real, its CAUSE is unknown",
                       "treat the momentum reading as unconfirmed and size down, or wait for the "
                       f"{peer} quote rather than inferring one")

    gap_bps = round((float(move_pct) - float(peer_move_pct)) * 100.0, 2)
    if abs(gap_bps) <= AGREE_BPS:
        return Verdict("CONFIRMED", gap_bps,
                       f"{symbol} {move_pct:+.3f}% vs {peer} {peer_move_pct:+.3f}% over the same "
                       f"window -- {abs(gap_bps):.1f}bp apart, so two independent issuers agree "
                       "and the underlying repriced",
                       "the directional reading stands")

    # The tell: the wrapper moved and the metal did not follow.
    rich = gap_bps > 0
    return Verdict("DISLOCATION", gap_bps,
                   f"{symbol} {move_pct:+.3f}% vs {peer} {peer_move_pct:+.3f}% over the same "
                   f"window -- {abs(gap_bps):.1f}bp apart, past the {AGREE_BPS:.0f}bp agreement "
                   f"band. Two independent claims on one metal cannot both be right, so this is "
                   f"an issuer/venue premium on {symbol if rich else peer}, not a move in the "
                   "underlying",
                   f"CONVERGENCE, not momentum: the premium on {symbol if rich else peer} is the "
                   "thing that mean-reverts. Trading the move as a breakout takes the wrong side")
