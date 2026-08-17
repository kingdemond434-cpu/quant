"""The desk's risk budget, defined ONCE, importable without MetaTrader5.

`gateway.py` imports MetaTrader5, which only exists on the Windows execution box. Research code on
Linux still has to know the desk's risk budget, and the failure mode when it cannot is silent and
expensive: the importer falls back to a literal it defines itself, and that literal is whatever was
true when the file was written. `allocation.py` was optimising at 0.055 for exactly that reason,
long after the gateway moved to 0.0075.

THIS MODULE IS NOW THE DEFINITION, NOT A COPY OF ONE. It previously restated `Q_OPT` and a test
asserted the two agreed -- which caught a real drift the first time the gateway's value changed,
but only because someone had written the test. Two constants that must agree is a defect waiting
for the one edit that forgets; gateway.py imports these instead, so there is nothing left to
disagree with.
"""

from __future__ import annotations

#: THE DRAWDOWN THE PRINCIPAL IS WILLING TO SIT THROUGH. The single risk input on this desk: both
#: per-trade size and the portfolio heat budget are solved from it, so there is one number to
#: argue about rather than two that can silently diverge.
#:
#: WHY THIS IS THE AGGRESSIVE SETTING AND NOT THE TIMID ONE. Measured full Kelly on the 3-leg gold
#: book is 6.00% per trade. Sizing there is not "maximum growth" -- it is a bet that an in-sample
#: backtest is exact. If the true edge is HALF the measured one, sizing at measured full Kelly
#: makes LESS money than sizing well below it, because past the true optimum the geometric rate
#: falls; at 2x Kelly it goes negative while every backtest number still looks excellent. More
#: size is not more aggression past that point, it is less money.
MAX_DRAWDOWN_TOLERANCE = 0.35

#: Worst peak-to-trough drawdown the armed book has produced, in R, at the sweep that validated
#: it. Risk is solved against THIS, so the numbers answer a question about the actual book rather
#: than a generic risk-of-ruin formula.
#:
#: IT IS IN-SAMPLE, AND THAT IS THE LOAD-BEARING UNCERTAINTY HERE -- not the edge. A book that
#: really draws down 41R breaks the 35% tolerance at this q. Applying a safety haircut to this
#: figure is the textbook response, and it does not survive contact with the account: at EUR 1,684
#: the 0.01 lot floor forces 1.04% per trade, so any haircut beyond 1.22x drops the base heat
#: budget below the 3.12% the armed book already runs and amputates a validated leg. The desk
#: therefore has ~22% of drawdown headroom, and that is a statement about how thin the ACCOUNT is,
#: not about how good the edge is. The fix is equity, not a smaller q.
BOOK_WORST_DD_R = 33.7


def risk_per_trade(tolerance: float = MAX_DRAWDOWN_TOLERANCE,
                   dd_r: float = BOOK_WORST_DD_R) -> float:
    """The per-trade risk fraction that spends exactly `tolerance` over a `dd_r` R drawdown.

    A book that suffers `dd_r` R of drawdown at per-trade risk q loses roughly 1-(1-q)^dd_r of
    equity. Inverting gives q* = 1 - (1 - tol)^(1/dd_r) -- every basis point the stated tolerance
    allows, stopping precisely where the principal said to stop.
    """
    return 1.0 - (1.0 - tolerance) ** (1.0 / dd_r)


#: RISK PER TRADE, DERIVED -- not chosen. 1.27% at the current tolerance and drawdown.
#:
#: THIS WAS HARDCODED 0.75%, WHICH IS A SECOND, UNDECLARED TOLERANCE. 0.75% corresponds to a 22.4%
#: drawdown, so per-trade sizing was 41% tighter than the portfolio budget it sits inside -- the
#: desk stated 35%, sized for 22%, and nothing reconciled them. Whichever number was right,
#: holding both was wrong.
#:
#: SAFE BY THE TEST THAT MATTERS, the same half-edge test that rejected 5.5%: if the true edge is
#: half the measured one, q* still compounds at ~82%/yr against ~45%/yr at 0.75%, and the
#: half-edge optimum is 5.10% -- q* sits at a QUARTER of it, nowhere near the cliff where more
#: size becomes less money. In-sample, at the full measured edge: ~261%/yr at -35.0% DD.
#:
#: COSTS NOTHING TODAY. At EUR 1,684 both 0.75% and 1.27% round to the same 0.01 lot; the two
#: first diverge at EUR 2,076. This changes no order at current equity -- it removes a brake that
#: would otherwise bind for the whole of the account's growth.
Q_OPT = risk_per_trade()
