"""One edge, two venues, two completely different risk problems.

WHY THIS EXISTS (principal, 2026-08-29: run the same system live AND on a funded prop account,
each with its own tuned risk levers)

THE TWO VENUES ARE NOT SOLVING THE SAME PROBLEM, and that is the whole reason this file exists
rather than a config flag.

    LIVE (Fusion, EUR500, the principal's own capital)
        Objective: maximise long-run geometric growth, E[log W].
        A drawdown is a cost. Survive it and the edge compounds back.
        The desk's own retirement rule tolerates -25R before acting.

    PROP (E8 evaluation, someone else's capital, a fee at risk)
        Objective: touch +target BEFORE touching -limit. A BARRIER problem.
        A drawdown is not a cost, it is DEATH. Breach the daily or the max and the
        account is gone permanently -- no recovery, no compounding back.

Optimising for the first and deploying into the second is how funded accounts die in week one.
-25R at 3% per R is -75% of the account; E8's maximum is 8%. The desk is not slightly outside
that envelope, it is an order of magnitude outside it.

MEASURED E8 RULES (checked 2026-08-29, verify before funding -- prop terms change often):

    E8 One / Classic:  max DD choice 4 / 6 / 8 / 10 / 14%, profit target = 1.5x the choice
                       (6 / 9 / 12 / 15 / 21%); daily loss choice 3 / 4 / 5.3 / 6.6 / 9.2%.
    E8 Pro v2:         fixed 8% target, 8% STATIC max DD, 2.5% hard daily loss, 2% daily
                       profit cap. Two-phase evaluation.
    Both:              40% CONSISTENCY RULE -- the best single day may not exceed 40% of
                       total profit.

THE CONSISTENCY RULE IS THE ONE THAT ACTUALLY SUITS THIS DESK, and it is the one most people
ignore until it fails them at payout. It makes a single lucky day worthless: profit must arrive
spread across many days. A discretionary trader hunting one big move cannot satisfy it. Seventeen
small sleeves firing continuously across sessions and instruments satisfy it structurally, by
construction, without trying. That is a genuine structural fit and the strongest argument for
this desk on a prop account.

THE BARRIER MATH SAYS SIZE DOWN, WHICH IS THE OPPOSITE OF THE INTUITION. For a walk with drift mu
and volatility sigma, scaling position size by k scales both, so the drift-to-variance ratio
scales as 1/k. SMALLER bets raise P(reach target before limit) -- they just take longer. The
correct prop posture with a real edge is the smallest size the time budget tolerates, which is
why `risk_frac` here is roughly a tenth of the live figure rather than a shaded version of it.

Note also that E8's target is ALWAYS 1.5x the chosen max drawdown. The barrier RATIO is therefore
constant across the whole menu, so picking a bigger drawdown tier does not improve the odds of
passing -- it only changes how much capital is at stake while they play out. Choose the tier for
the account size wanted, not to buy a better chance.

WHAT THIS FILE WILL NOT DO. It does not invent prop-specific edges. Re-mining for "strategies
that pass evaluations" would be fitting to a fee structure rather than to a market, and any edge
found that way exists only until the rules change. The mechanisms are the same; the SELECTION
among them and the SIZE of them differ, and only those two are tuned here.
"""
from __future__ import annotations

from dataclasses import dataclass

#: Effective independent bets in the current book. Measured, not assumed: 23 certificates carry
#: n_eff ~5.5, so sleeves lose TOGETHER and a daily limit is hit by a correlated cluster rather
#: than by any single sleeve. Every daily-loss calculation below divides by this, and treating
#: the sleeves as independent is precisely how a "safe" 1% per trade becomes a 5.5% day.
BOOK_N_EFF = 5.5

#: Fraction of a hard limit the desk will actually spend. A limit reached is an account lost, so
#: the working ceiling sits well inside it -- slippage, a gap, and one more correlated fill all
#: have to fit in the gap between this and the real number.
LIMIT_UTILISATION = 0.6


@dataclass(frozen=True)
class AccountProfile:
    """The risk envelope for one account. Immutable: a venue's rules are not a runtime opinion."""

    name: str
    #: Fraction of equity risked per trade, BEFORE the canary ramp and other multipliers.
    risk_frac: float
    #: Hard daily loss as a fraction of starting-day equity. None where the venue has none.
    daily_loss_limit: float | None
    #: Hard total drawdown. None for the principal's own capital, where drawdown is a cost
    #: rather than a termination.
    max_drawdown_limit: float | None
    #: Stop trading for the day at this fraction of equity lost -- deliberately inside the hard
    #: limit, because a breach is not recoverable.
    daily_circuit_breaker: float | None
    #: Profit target that ends the phase, if any.
    profit_target: float | None
    #: Best single day may not exceed this fraction of total profit.
    consistency_cap: float | None
    #: Forward-R drawdown at which a sleeve is retired on this account.
    retire_max_dd_r: float
    why: str

    def max_concurrent_risk(self) -> float | None:
        """Total risk the book may carry at once without threatening the daily limit."""
        if self.daily_loss_limit is None:
            return None
        return self.daily_loss_limit * LIMIT_UTILISATION

    def implied_safe_risk_frac(self) -> float | None:
        """Largest per-trade risk a correlated cluster can survive on this venue.

        The number that matters is not what one sleeve risks, it is what `BOOK_N_EFF` of them
        risk on the day they all lose together -- which, at n_eff 5.5, is the ordinary case
        rather than the tail.
        """
        cap = self.max_concurrent_risk()
        return None if cap is None else cap / BOOK_N_EFF

    def trades_to_target(self, exp_r: float) -> float | None:
        """Trades needed to reach the profit target at a given per-trade expectancy in R."""
        if self.profit_target is None or exp_r <= 0 or self.risk_frac <= 0:
            return None
        return (self.profit_target / self.risk_frac) / exp_r


#: The principal's own capital. Drawdown is a cost to be survived, not a termination, so the
#: envelope is the desk's canonical one and the objective stays geometric growth.
LIVE = AccountProfile(
    name="fusion-live",
    risk_frac=0.03,
    daily_loss_limit=None,
    max_drawdown_limit=None,
    daily_circuit_breaker=None,
    profit_target=None,
    consistency_cap=None,
    retire_max_dd_r=-25.0,
    why="own capital, geometric growth, drawdown is a cost the book recovers from",
)

#: E8 Pro v2 as measured 2026-08-29: 8% target, 8% static max drawdown, 2.5% hard daily loss.
#:
#: risk_frac derives rather than being chosen: 2.5% daily x 0.6 utilisation / 5.5 effective bets
#: = 0.27%, rounded down. That is a TWELFTH of the live figure, and the size of that gap is the
#: entire finding -- the live envelope is not slightly too big for a prop account, it is
#: catastrophically too big, and no amount of shading gets there from 3%.
E8_PRO = AccountProfile(
    name="e8-pro-v2",
    risk_frac=0.0025,
    daily_loss_limit=0.025,
    max_drawdown_limit=0.08,
    daily_circuit_breaker=0.015,
    profit_target=0.08,
    consistency_cap=0.40,
    retire_max_dd_r=-6.0,
    why=("barrier problem: reach +8% before -8% total or -2.5% in a day. Sized from the DAILY "
         "limit and n_eff, not from the drawdown tolerance, because the daily limit binds first "
         "and binds on a correlated cluster rather than on any one sleeve"),
)

#: E8 One at the 8% drawdown tier: 12% target, 5.3% daily. Same barrier RATIO as every other tier
#: (target is always 1.5x drawdown), so it offers no better chance of passing -- only a different
#: amount of capital in play while the same odds resolve.
E8_ONE_8 = AccountProfile(
    name="e8-one-8pct",
    risk_frac=0.0055,
    daily_loss_limit=0.053,
    max_drawdown_limit=0.08,
    daily_circuit_breaker=0.032,
    profit_target=0.12,
    consistency_cap=0.40,
    retire_max_dd_r=-6.0,
    why="E8 One 8% tier; roomier daily limit permits ~2x the per-trade size of Pro v2",
)

PROFILES = {p.name: p for p in (LIVE, E8_PRO, E8_ONE_8)}


def profile_for(account: str | None) -> AccountProfile:
    """Resolve an account name to its envelope, FAILING CLOSED to the tightest one.

    An unknown account resolves to E8_PRO, not to LIVE. Getting this backwards would size an
    unrecognised account at 3% and lose it on the first correlated day; the reverse merely
    under-trades until someone notices. The asymmetry is total, so the default follows it.
    """
    if not account:
        return LIVE
    p = PROFILES.get(account)
    if p is not None:
        return p
    return E8_PRO
