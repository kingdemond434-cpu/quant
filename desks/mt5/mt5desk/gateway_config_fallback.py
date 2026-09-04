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


# ---------------------------------------------------------------------------------------
# PORTFOLIO HEAT -- the three numbers that bound total open risk, defined here for the same
# reason Q_OPT is: two files holding a risk budget is a defect waiting for the edit that
# forgets one. `heat_budget()` in the gateway and `research/heat_policy.py` both read these.
# ---------------------------------------------------------------------------------------

#: NORMAL FULL-UTILISATION TARGET (principal, 2026-09-02). Total heat the desk aims to have
#: WORKING at all times during certified operation -- a target, not a ceiling. Raised from the
#: 15% that stood here after the E[log W] allocator was measured against it.
#:
#: WHY A TARGET AND NOT MERELY A CAP. A cap answers "how much may we risk"; the desk needs the
#: answer to "how much SHOULD we risk", and those differ whenever the cap binds. Under a cap the
#: allocator quietly runs at 3-6% because the free robust optimum sits there, and the account
#: compounds at a fraction of what the opportunity set supports. Under a target the question
#: becomes WHAT the budget is spent on, and an unfillable budget becomes a research request
#: (`pf_allocator.opportunity`) instead of an invisible shortfall.
#:
#: CERTIFIED, NOT ASSERTED. `heat_policy.certify()` re-measures the growth curve on the live
#: world population every heavy pass and `reports/pf_allocation.json` carries the verdict: if the
#: opportunity set ever degrades enough that 20% sits past the peak of the curve, that artifact
#: says so and `gateway.allocator_heat()` refuses the number. This comment is not the evidence.
HEAT_TARGET = 0.20

#: THE HARD BAR. Total heat may never cross this, whatever the optimiser computes -- the outer
#: envelope inside which the allocator is free, and the only constant here that is a limit rather
#: than a goal.
#:
#: 30% IS WHERE THE ARITHMETIC TURNS, which is why it is the bar rather than a round number.
#: Measured 2026-09-02 across 256 sampled worlds on the 109-sleeve matrix: the ROBUST score (half
#: its weight on the worst 20% of worlds) runs +0.00133/day at the free optimum, +0.00072 at 20%,
#: +0.00011 at 25% and NEGATIVE at 30%. Past 30% the book loses wealth in the worlds it has to
#: survive, and no amount of average-case growth buys that back.
HEAT_HARD_CEILING = 0.30

#: No single sleeve may hold more than this share of total heat. NOT tidiness -- measured
#: 2026-09-02: told to spend 20% with no per-sleeve bound, the optimiser put 14.4 of those 20
#: points into one sleeve it gives exactly ZERO when free, because a near-cash sleeve is the
#: cheapest place to park a budget you do not believe in. A mandate without this bound funds the
#: flattest row in the matrix, not the book.
MAX_SLEEVE_HEAT_SHARE = 0.25

#: No single MECHANISM may hold more than this share of total heat.
#:
#: MEASURED 2026-09-02: the solved book put 97% of its heat into `overnight_gap_decay` across
#: seven exotic crosses. DISCOVERY DID NOT CAUSE THAT -- the family is 232 of 23,465 docket cells
#: (0.99%), against 20,341 from the family-free searcher, and it holds 12 of 65 certificates.
#: Nothing directs the search at it. The ALLOCATOR concentrated, because that family's replayed
#: edge was the largest among the sleeves it could price.
#:
#: THE REDUNDANCY TERM CANNOT SEE THIS. It charges pairwise correlation of daily returns, and
#: seven gap sleeves on different currency pairs genuinely are weakly correlated day to day. They
#: also share one mechanism and one fill hour (01:00, the thinnest book of the session), so they
#: fail TOGETHER on a liquidity event that no daily correlation contains. That is the factor
#: duplication and tail co-failure the mandate asks to penalise, and it needs a CONSTRAINT rather
#: than a price: a penalty is something growth can outbid.
#:
#: 60%, MEASURED (2026-09-04). The cap was 40% on the reasoning above, which is sound about WHY a
#: constraint is needed and was a guess about WHERE it belongs. Swept on the live 126-sleeve
#: universe at the 30% heat ceiling, every axis peaks or bottoms together at 60%:
#:
#:     famcap   ann %    robust      cvar     P(loss)  histDD  legs   d growth
#:       40%    322.1   0.00123   -0.00049    0.062    27.8%    13
#:       50%    427.8   0.00217   -0.00021    0.062    26.8%    12     +53.0
#:       55%    482.7   0.00261   -0.00012    0.062    25.6%    11     +54.9
#:       60%    543.3   0.00304   -0.00010    0.047    25.3%    11     +60.6   <-- optimum
#:       65%    610.5   0.00344   -0.00017    0.047    27.2%    10     +67.2
#:       70%    657.3   0.00369   -0.00026    0.047    28.5%     8     +46.8
#:       80%    657.3   0.00369   -0.00026    0.047    28.5%     8      +0.0
#:
#: 40% WAS DOMINATED, not merely conservative: 60% carries +221pp of annual growth with LOWER
#: drawdown (25.3% vs 27.8%), a less negative tail and a lower probability of annual loss. A
#: constraint that costs growth AND worsens the tail is not buying safety with return; it is
#: simply mis-sited.
#:
#: WHY NOT FURTHER, WHICH IS THE HALF THAT MATTERS. Past 60% the trade inverts: at 65% CVaR
#: worsens and drawdown climbs back, and at 70% the book collapses from 11 sleeves to 8 for the
#: SMALLEST marginal gain in the table. 80% and 101% are byte-identical to 70%, which means the
#: cap has stopped binding there -- that concentration is the solver's own choice, and the
#: original argument applies to it exactly: seven sleeves sharing one mechanism and one 01:00
#: fill hour fail together on a liquidity event no daily correlation contains.
#:
#: So the constraint stays, and still forces several independent mechanisms to be right. It is
#: now placed where the evidence puts it rather than where it felt prudent.
MAX_FAMILY_HEAT_SHARE = 0.60
