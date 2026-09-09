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

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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

#: E8 ONE-PHASE 100K, ~$234 (checked 2026-08-29). 6% target, 4% STATIC total drawdown, no
#: minimum trading days, NO TIME LIMIT, drawdown measured END OF DAY only.
#:
#: THE BEST STRUCTURAL FIT AVAILABLE, for three reasons unrelated to the price:
#:
#:   NO TIME LIMIT is the whole edge. The barrier math says smaller bets RAISE the probability of
#:   reaching the target and merely take longer, so an account with no clock lets the desk take
#:   the safe side of that trade for free. Every timed product forces the opposite choice.
#:
#:   END-OF-DAY DRAWDOWN forgives intraday excursion entirely. These sleeves are bracketed and
#:   close within session, so they collect that concession fully.
#:
#:   ONE PHASE removes a second independent chance to fail.
#:
#: THE DANGER IS THE 4% STATIC DRAWDOWN -- HALF the Pro tier's -- and the ABSENCE of a daily
#: limit, which reads as generous and is the opposite: nothing caps a single day's loss below the
#: account-ending number. risk_frac is therefore derived from the TOTAL drawdown.
E8_ONE_PHASE_100K = AccountProfile(
    name="e8-one-phase-100k",
    risk_frac=0.0018,
    daily_loss_limit=None,
    max_drawdown_limit=0.04,
    daily_circuit_breaker=0.010,
    profit_target=0.06,
    consistency_cap=0.40,
    retire_max_dd_r=-5.0,
    why=("one phase, 6% target, 4% static DD, no time limit, end-of-day drawdown. Sized from the "
         "TOTAL drawdown because there is no daily limit -- the absence of one is a hazard, not "
         "a freedom"),
)

PROFILES = {p.name: p for p in (LIVE, E8_PRO, E8_ONE_8, E8_ONE_PHASE_100K)}


#: Measured expectancy -> risk fraction. Computed by `scripts/optimise_prop_settings.py` as the
#: FASTEST size still clearing a 90% pass probability, on the two-barrier model with 11 trades/day
#: and n_eff 5.5 independent bets/day:
#:
#:      expectancy   risk    P(pass)   days
#:          0.00R      --      0.400   never    no size passes; sizing cannot rescue no edge
#:          0.02R    0.10%     0.900     273
#:          0.05R    0.35%     0.901      31
#:          0.08R    0.50%     0.924      14
#:          0.12R    0.70%     0.90+       6
#:
#: A SCHEDULE RATHER THAN A NUMBER, because the input it depends on does not exist yet. P(pass)
#: at 0.35% swings from 0.90 to 0.67 between 0.05R and 0.02R, so picking a size today bets the
#: fee on an unmeasured quantity. Reading the size off the measurement sizes the account by
#: evidence instead.
_RISK_BY_EXPECTANCY: tuple[tuple[float, float], ...] = (
    (0.12, 0.0070),
    (0.08, 0.0050),
    (0.05, 0.0035),
    (0.02, 0.0010),
)

#: Below this measured expectancy NO size clears the probability floor, so the answer is not a
#: smaller size -- it is DO NOT FUND. A driftless path passes at drawdown/(target+drawdown)
#: whatever the risk, and shrinking only makes the eventual failure slower.
MIN_VIABLE_EXPECTANCY = 0.02


def risk_for_expectancy(exp_r: float | None,
                        profile: "AccountProfile | None" = None) -> tuple[float, str]:
    """Fastest safe risk fraction for a MEASURED expectancy. Returns (risk_frac, why).

    Unmeasured expectancy returns the conservative default and says so. It never guesses upward:
    on a prop account being too small costs time while being too large costs the account, and an
    unmeasured input is exactly when that asymmetry should govern (LAWS L1.28a).
    """
    prof = profile or E8_ONE_PHASE_100K
    if exp_r is None:
        return prof.risk_frac, (
            "expectancy is UNMEASURED -- no forward window has completed. Using the conservative "
            "default: the slow-but-safe corner of the frontier, which is the correct place to "
            "sit while the input is unknown")
    if exp_r < MIN_VIABLE_EXPECTANCY:
        floor = (prof.max_drawdown_limit or 0.0) / ((prof.profit_target or 0.0)
                                                    + (prof.max_drawdown_limit or 1.0))
        return 0.0, (
            f"measured expectancy {exp_r:+.4f}R is below {MIN_VIABLE_EXPECTANCY}R. No size "
            f"clears a 90% pass probability at this edge -- a driftless path passes at "
            f"{floor:.0%} whatever the risk. The answer is DO NOT FUND, not a smaller size.")
    for threshold, risk in _RISK_BY_EXPECTANCY:
        if exp_r >= threshold:
            return risk, (f"measured {exp_r:+.4f}R >= {threshold}R -> {risk:.2%} per trade, the "
                          f"fastest size still clearing a 90% pass probability")
    return prof.risk_frac, "below the schedule; conservative default"


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


# ------------------------------------------------- which envelope THE CONNECTED ACCOUNT gets
#: Where the box declares which venue each account it might connect to actually is. Relative to
#: the repository root, next to the desk's other state.
DECLARATIONS_REL = "desks/mt5/data/ACCOUNT_PROFILES.json"

#: Key shape in that file: "<login>@<server>" -> profile name. Login alone is not enough, for the
#: reason `provenance.same_account` already gives: a broker that reuses logins across servers
#: would collide, and the demo and live sides of one broker differ by exactly this pair.
def account_key(acc: dict[str, Any] | None) -> str | None:
    """The declaration key for a `provenance.current_account()` dict, or None if unidentifiable."""
    if not acc:
        return None
    login, server = acc.get("login"), acc.get("server")
    if login in (None, "") or server in (None, ""):
        return None
    return f"{login}@{server}"


def read_declarations(root: Path) -> tuple[dict[str, str] | None, str]:
    """The box's account declarations, or (None, why) when there are none to read.

    ABSENT IS NOT EMPTY, AND NEITHER IS BROKEN. The whole safety of this layer turns on holding
    those three apart:

      * NO FILE -> None. The desk has never been told it runs more than one account, and the
        answer must be the behaviour it already had.
      * FILE PRESENT BUT UNREADABLE OR MALFORMED -> {}. Something declared the set and this
        process cannot read it. That is NOT "there are no declarations": a truncated write while
        a prop account is connected would otherwise hand that account the live envelope, which
        is the one outcome this file exists to prevent. An empty mapping leaves every account
        undeclared, and the caller fails each of them closed.
      * FILE READ -> the mapping it carries.
    """
    p = root / Path(*DECLARATIONS_REL.split("/"))
    if not p.exists():
        return None, f"no {DECLARATIONS_REL} on this box"
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {}, f"{DECLARATIONS_REL} exists but is unreadable ({exc.__class__.__name__})"
    accounts = raw.get("accounts") if isinstance(raw, dict) else None
    if not isinstance(accounts, dict):
        return {}, f"{DECLARATIONS_REL} exists but carries no 'accounts' object"
    return {str(k): str(v) for k, v in accounts.items()}, f"declared in {DECLARATIONS_REL}"


def envelope_for_connected(acc: dict[str, Any] | None,
                           root: Path) -> tuple[AccountProfile | None, str]:
    """The envelope binding the account now under the terminal, or (None, why) for no bar.

    (principal, 2026-09-09: "we tune only our prop firm side for the prop firm n keep 20 percent
    heat rule fr the main only".)

    THE THREE ANSWERS, AND WHY THE FIRST ONE IS NOT `LIVE`:

      * NO DECLARATION FILE -> (None, why). No venue bar is applied and the desk sizes exactly as
        it does today. This is deliberately NOT `profile_for`'s fail-closed default. That
        function answers "how should an account I am being asked to FUND be sized", where an
        unknown one must resolve to the tightest envelope. This one answers "may I keep sizing
        the book I am already trading", and there the tightest envelope is not caution -- it is a
        silent 12x cut to a running live book that nobody asked for and nothing would report.
        Refusing to change what was not declared is the conservative answer to THIS question.

      * DECLARED -> that profile. Creating the file is the arming act, in the same shape as
        `GENERIC_EXEC_ENABLED`: the wiring never waits for a person, the ARMING always does.

      * FILE EXISTS AND THIS ACCOUNT IS NOT IN IT -> E8_PRO, the tightest. Once the box has been
        told it runs more than one account, an account nobody named is an account nobody has
        vouched for, and the funding asymmetry applies again in full.

    Pure over its inputs: the caller reads the terminal, this decides. It never writes.
    """
    declared, why = read_declarations(root)
    if declared is None:
        return None, f"{why}; the account envelope is unchanged from the desk's own"
    key = account_key(acc)
    if key is None:
        return E8_PRO, (
            f"the terminal did not name the connected account (login/server missing) while "
            f"{DECLARATIONS_REL} exists; failing closed to {E8_PRO.name}")
    name = declared.get(key)
    if name is None:
        # `why` and not a fixed sentence: "not named" and "named, in a file this process could
        # not parse" reach the same envelope by different routes, and only one of them is a
        # missing declaration. An operator reading "not named" after a torn write would go and
        # add a line that is already there.
        return E8_PRO, (
            f"account {key} is not declared ({why}); failing closed to "
            f"{E8_PRO.name} rather than sizing an undeclared account at the live envelope")
    prof = PROFILES.get(name)
    if prof is None:
        return E8_PRO, (
            f"account {key} is declared as {name!r}, which is not a known profile "
            f"({', '.join(sorted(PROFILES))}); failing closed to {E8_PRO.name}")
    return prof, f"account {key} is declared {prof.name} ({why})"


def venue_heat_cap(acc: dict[str, Any] | None, root: Path) -> tuple[float | None, str]:
    """Total book heat this venue's rules allow at once, or (None, why) when they impose none.

    `LIVE` has no daily loss limit, so `max_concurrent_risk()` is None and the desk's own budget
    stands alone -- the 20% heat floor and everything above it are untouched on the main book.
    A prop profile answers with `daily_loss_limit x LIMIT_UTILISATION`, which is a HARD bar on
    total concurrent risk and has nothing to do with the growth budget it caps.
    """
    prof, why = envelope_for_connected(acc, root)
    if prof is None:
        return None, why
    cap = prof.max_concurrent_risk()
    if cap is None:
        return None, f"{why}; {prof.name} imposes no daily loss limit"
    return cap, (f"{why}; {prof.name} allows {cap:.2%} concurrent risk "
                 f"({prof.daily_loss_limit:.2%} daily x {LIMIT_UTILISATION:.0%} utilisation)")
