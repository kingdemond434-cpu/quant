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
#:
#: RAISED 0.35 -> 0.642 ON 2026-08-22, PRINCIPAL'S EXPLICIT AND REPEATED INSTRUCTION, to put
#: Q_OPT at 3.00%. Raised HERE rather than hardcoding Q_OPT, so the derivation stays intact and
#: the number re-solves itself when BOOK_WORST_DD_R is next measured.
#:
#: WHAT THE EVIDENCE SAID, INCLUDING THE PART AGAINST IT. Measured on 5,731 real gold session
#: trades (682/yr, exp +0.1176R in-sample), growth by TRUE edge as a fraction of backtest:
#:
#:     true edge   Kelly q*    g(2%)   g(3%)      <- 3% is at/near optimum only if the edge
#:       x1.00       8.00%      323%    671%         lands around a THIRD of backtest
#:       x0.50       5.10%       90%    132%
#:       x0.33       3.30%       45%     54%
#:       x0.25       2.50%       27%     27%      <- 2% and 3% TIE here
#:       x0.15       1.50%        8%      0%      <- 3% is the last non-negative size
#:
#: 3.00% is the LARGEST q whose worst case across those scenarios is still non-negative; 3.5%
#: returns -7% there and 5% returns -33%. That is the argument for it, and it is a real one.
#:
#: THE ARGUMENT AGAINST, RECORDED SO IT IS NOT LOST. At x0.25 3% buys NOTHING over 2% (+27% both)
#: while costing 15 more points of drawdown, and the 5-year bad-decile outcome on $5,000 is
#: $3,836 at 3% against $6,241 at 2% -- one path in eight ends five years of compounding BELOW
#: starting capital, and 2.3% of paths end under $1,000. Trailing stops and profit locks do not
#: mitigate this: the worst drawdown is -45.8R built from 168 small losses against 94 wins, whose
#: largest single loss was -1.12R. There is no fat loss for a tighter stop to cut and no open
#: winner for a trail to protect, so drawdown here is attrition, not tail events.
#:
#: THE UNCERTAINTY THAT DOMINATES BOTH. The spread between x1.00 and x0.15 at a FIXED 3% is 671%
#: to 0%. Which column is true matters far more than 2% vs 3%, and nothing in a backtest can say
#: which it is. Shadow forward evidence is the only thing that narrows it, and it currently holds
#: ZERO trades. Until it does, this constant rests on in-sample data by necessity.
#: EXACTLY half measured Kelly. 0.6417324740 is not a taste: it is the tolerance that solves
#: q* = 3.0000% at BOOK_WORST_DD_R = 33.7R, i.e. 0.06/2. Chosen to the tenth decimal so the
#: budget lands ON the half-Kelly fence rather than 0.0022% over it -- a bound that is "about
#: right" is a bound nobody can test against.
MAX_DRAWDOWN_TOLERANCE = 0.6417324740

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
