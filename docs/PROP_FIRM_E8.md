# E8 evaluation: the plan, the arithmetic, and the readiness gate

Principal's standing intent (2026-09-07): take an **E8 One £100k** evaluation once the desk holds
the portfolio below. Recorded here so a fresh session can pick it up without re-deriving it.

**Nothing here is a decision to trade.** No sleeve gets capital from this document; the ten gates,
a forward clock and measured rent decide, exactly as for anything else.

## The account

**E8 One**, one step, customisable at checkout. The structural fact that drives everything:

> **The profit target is always 1.5 × the drawdown you choose.** Drawdown 4–14%, target 6–21%.

So the barrier *ratio* is fixed at 1.5 whichever you pick — you cannot buy a better risk/reward by
choosing differently, only a larger or smaller arena.

| Setting | Chosen | Why |
|---|---|---|
| Max drawdown | **8%** | see "why not 14%" below |
| Profit target | **12%** (= 1.5 × 8) | £12,000 on £100k |
| Daily loss limit | 4% | E8 One allows 3–9.2%; resets daily on the high-water mark |
| Consistency | 40% best-day rule | no single day may be >40% of total profit |
| Minimum days | none on Forex | |

## The portfolio

**Three to four INDEPENDENT mechanisms at 0.50% risk per trade.**

| Mechanism | State 2026-09-07 |
|---|---|
| `session_range_breakout` | 15 clocks, 14 positive, 5 symbols — the only one with evidence |
| `overnight_gap_decay` | 12 certificates, enrolled, **n=0 — no forward evidence yet** |
| `carry` | 1 certificate, enrolled, n=0 — the desk's only non-directional mechanism |

Expected: **~92% pass, ~36 days median** (p25 ≈ 23d, p90 ≈ 81d) at a true `exp_R` of +0.20.

### The arithmetic, so it can be checked rather than believed

```
12% target ÷ 0.5% risk           = 24R to clear
24R ÷ 0.20R per trade            = ~120 trades
120 trades ÷ ~2.5 trades/day     = ~48 days naive; ~36d median in simulation
```

Firing rate is measured, not assumed: **0.64 trades/day per window** (XAUUSD.asia and CADJPY.asia
each n=7 over 11 days). The `rr=1.5 / 2.0 / 2.5` variants are the SAME entry with different
targets — one signal, not three. Counting them separately overstates speed 4×.

## Why not 14% drawdown

14%/21% was the first suggestion and the simulation revised it. At a weak edge the p90 drawdown
reaches **19%** and the median time is 119 days — five months and a near-death experience for the
same pass. 8%/12% passes in 25–50 days with roughly half the drawdown. **Shorter path, less time
exposed, safer.**

## Why NOT to add more gold sleeves

This is the trap, and the numbers are unambiguous (exp_R +0.20, ρ ≈ 0.7 for same-mechanism
sleeves):

| sleeves | ρ | risk each | P(pass) | median days |
|---|---|---|---|---|
| 2 | 0.70 | 0.50% | 87% | 65d |
| 4 | 0.70 | 0.50% | **77%** | 27d |
| 8 | 0.70 | 0.50% | **60%** | 9d |
| 4 | 0.00 | 0.50% | 92% | 36d |
| 8 | 0.00 | 0.25% | **99%** | 42d |

More of the **same** mechanism buys speed by taking leverage and pays for it in pass probability.
Eight Asia session-range breakouts on eight correlated pairs is one bet at eight times the size:
they lose together, on the same day, into the 4% daily limit. Independence is the only thing that
improves both axes at once.

**The readiness metric is the count of independent MECHANISMS, never the count of certificates.**

## Not ready yet, and precisely why

- **1 mechanism with forward evidence.** 14 of 15 positive clocks are the same breakout, on four
  JPY crosses plus gold — correlated by construction.
- **`matched_fills: 0`.** Every expectancy above is replay. Real spread and slippage are unmeasured,
  and they are the difference between the +0.34R row (25 days) and the +0.10R row (48 days).
- **n = 7 per sleeve.** `USDJPY.asia#rr=2.5` shows +1.19R, which at 2.5:1 implies a **62.6% win
  rate on a breakout** — that is 5 wins in 8 trades, not an edge. Do not size to it.

Getting from 1 independent mechanism to 3 requires **no new research**: `overnight_gap_decay` and
`carry` are already certified and already enrolled. They need forward observations to accrue.

## The gate to open before buying

1. `overnight_gap_decay` and `carry` carrying non-zero forward evidence.
2. The first 20–30 **real fills** from the live Fusion account, so cost is measured rather than
   assumed. Re-run the simulation with those costs before paying the fee.
3. Re-check E8's current rules at purchase — they change, and this file is a snapshot.

---

# 2026-09-08: THE ACTUAL OFFERS, PRICED AND SIMULATED

The principal sent E8's live checkout. This section supersedes the 8%/12% recommendation above --
not because that arithmetic was wrong, but because 8% is not what is on the counter. The
drawdown selector's endpoints are **6%** and **14%**, and the ratio is 1.5x at both, as recorded.

| offer | price (code E8) | target | dynamic DD | daily DD |
|---|---|---|---|---|
| $100K @ 6% | $244 (was $488) | $9,000 | $6,000 | $4,000 |
| $200K @ 6% | $399 (was $798) | $18,000 | $12,000 | $8,000 |
| $100K @ 14% | $440 (was $879) | $21,000 | $14,000 | $9,200 |

**DYNAMIC, NOT STATIC.** The screenshots say "Dynamic Drawdown", so the floor TRAILS the high
water mark. That is materially harder than the static bound the section above assumed, and it is
why this simulation checks the barrier after every trade rather than at end of day.

## The three findings, from 40,000 simulated paths per cell

**1. $200K @ 6% STRICTLY DOMINATES $100K @ 6%.** Identical percentage rules, so identical pass
probability -- $399 for twice the funded capital against $244 for one. $2.11 per $1k funded
against $2.59. There is no configuration in which the $100K/6% is the better buy.

**2. RISK PER TRADE IS THE DOMINANT LEVER AND IT RUNS BACKWARDS TO INTUITION.** On $100K @ 6%,
at exp_R +0.20 with four independent sleeves:

| risk/trade | P(pass) | median | E[cost to pass] |
|---|---|---|---|
| 0.25% | **94.3%** | 62d | $259 |
| 0.50% | 73.3% | 26d | $333 |
| 0.75% | 60.3% | 12d | $405 |
| 1.50% | 47.0% | 5d | $519 |

HALVING the risk from the planned 0.50% to 0.25% moves pass probability from 73% to 94%. This is
the barrier problem stated at the top of this file, in numbers: permanent-out at the drawdown
against merely-sooner at the target means the growth-optimal size is far above the
pass-optimal one. E8's "Pass in as little as 1 Day" is achievable and costs roughly half the
pass probability.

**3. 14%/21% BUYS PROBABILITY WITH TIME AND MONEY.** 96.9% at 0.50% risk -- the highest of any
config at a sane speed -- but 75 days median and $4.54 per $1k funded, the worst value on offer.

## The recommendation

**$200K at 6% drawdown, 0.25% risk per trade.** 94.4% pass, 51 days median, 99 days at p90,
$2.11 per $1k funded -- best on value AND on probability. It loses only to configurations whose
pass rate is near a coin flip.

The $200K @ 14% price is not in the screenshots. If the selector offers it, it is worth pricing:
it would pair the dominant account size with the highest-probability drawdown setting.

## What the whole table rests on, and it is not yet true

Every number above assumes **exp_R = +0.20 is real**. Sensitivity on $100K @ 6%, 0.50% risk:

| true exp_R | P(pass) | E[cost to pass] |
|---|---|---|
| +0.30 | 87.5% | $279 |
| +0.20 | 73.1% | $334 |
| +0.10 | 51.2% | $476 |
| +0.05 | 37.5% | $650 |
| 0.00 | 24.5% | $996 |

At +0.10 -- half the assumed edge -- this is a coin flip. The desk's evidence for +0.20 is n=7
per sleeve.

**AND THE BOOK IS NOT LIVE.** Measured off the board 2026-09-08 01:39 UTC: `live: 0`,
`matched_fills: 0`, `certified: 5`, 15 forward clocks at n=7-8, and the two gold scalp candidates
sitting at promotion-ready rather than LIVE. There is no four-sleeve independent book -- there is
one mechanism on four JPY crosses plus gold, which is the rho=0.7 row, and it has never placed a
real order. The simulation assumes the desk executes; today it does not.

The gate in the section above is unchanged and unmet.

---

# 2026-09-12: THE ACCOUNT IS BOUGHT, AND IT IS NOT THE ONE THIS FILE WAS WRITTEN FOR

**E8 Pro, $100,000, TradeLocker.** Order 20260977504, $485 (from $646 with the E8 discount).
Everything above was written for **E8 One** -- customisable drawdown, target always 1.5x it,
*dynamic* drawdown that trails the high-water mark. None of that describes this account. The
numbers below supersede every table above for the purposes of this account; the One sections stay
because the reasoning in them is sound and a future One purchase would use it.

## The arena, from the invoice and the dashboard

| | | |
|---|---|---|
| Balance | **$100,000** | |
| Profit target | **10%** = $10,000 | confirmed by the principal off the dashboard |
| Max drawdown | **10% STATIC** = a floor at $90,000 | it never trails -- materially easier than One's dynamic |
| Daily drawdown | **2.5%** = $2,500 | from the day's starting balance, hard breach |
| Daily profit cap | **2%** = $2,000 | confirmed; excess is **stripped at rollover** |
| Platform | **TradeLocker** | not MetaTrader |
| Execution | no commissions | so the cost is in a **wider spread**, not absent |
| Swaps | apply | on anything held through rollover |
| Payout | 100% | |
| Consistency rule | none on Pro | the 40% rule above is an E8 One rule |

The barrier ratio is **1.0** -- a 10% target against a 10% drawdown. That is better than E8 One's
fixed 1.5 (12% against 8%), and it is the one way this account is kinder than the one planned for.

Published E8 Pro is 8% target / 8% static; this is a different configuration and the third-party
rule pages do not describe it. Trust the dashboard, not the reviews.

## Three facts decide this account, and two of them are not about strategy

**1. SPEED IS NOT A VARIABLE. The floor is five trading days.** 10% of target at 2% of counted
profit per day is 5 days, and no portfolio, edge or size can beat it. E8 strips profit above 2% at
rollover -- it does not merely stop counting it, it removes it from the balance between midnight
and 1am server time -- and splitting a winner across days by hedging or partial closes is
explicitly disallowed. So "pass it fastest" is answered by the rules. What is left to optimise is
P(pass) and the tail.

**2. THE RIGHT TAIL IS CONFISCATED AND THE LEFT TAIL IS NOT.** A day is capped at +2% and free to
run to -2.5%. Every unit of daily variance is taxed: a book whose good day is +5% banks +2% and
keeps all of the risk that produced it. This is why the pass-optimal size is far below the
growth-optimal one, and it is not a "reduce aggressiveness" argument -- it is the same E[log W]
logic answering a different question, on a different account, exactly as `account_profile.py`
already sets out.

**3. THE DAILY FLOOR IS WHAT KILLS, NOT THE STATIC ONE.** Measured, today's book at net +0.10R:

| risk/trade | P(pass) | died on the DAILY floor | died on the STATIC floor |
|---|---|---|---|
| 0.25% | 84.3% | 0.0% | 0.5% |
| 0.35% | 90.0% | 2.4% | 1.9% |
| 0.50% | 70.8% | **24.6%** | 4.0% |
| 0.75% | 28.2% | **68.8%** | 3.0% |

The 10% static floor is almost never reached. The 2.5% daily one gets there first, every time.
That inverts the usual prop posture: the constraint to manage is DAILY variance, not total
drawdown.

## THE LOCKED SPEC

**0.35% risk per trade ($350), with a hard voluntary stand-down at -0.75% ($750) for the rest of
the session.** Maximum two positions open at full risk at any moment, so a simultaneous stop-out
cannot overshoot the stand-down.

| book | P(pass) at net +0.20 | at net +0.10 | at net +0.05 | median days at +0.10 |
|---|---|---|---|---|
| **today: 1 mechanism, 4 correlated sleeves** | 99.9% | **91.0%** | 67.0% | 91d |
| 3 mechanisms, 8 sleeves | 99.9% | **96.2%** | 79.4% | 55d |

The stand-down takes daily breaches to **zero** and costs nothing in time. The speed variant, if
91 days is too slow, is **0.50% risk with a -1.00% stand-down**: 88.3% and 69 days -- 22 days
faster for 2.7 points of pass probability.

**The readiness metric is unchanged and it is the count of independent MECHANISMS.** Going from
one mechanism to three moves this from 91% to 96% and nearly halves the time, which is a bigger
move than any sizing choice on the table.

## What a stand-down is worth, and the modelling error that nearly overstated it

A first version of `research/prop_barrier.py` drew one common factor per DAY, so every trade a
book placed between midnight and midnight shared a regime. It reported a **98% pass rate on a book
with ZERO edge**, which is impossible: a stop applied to a driftless walk whose right tail is
confiscated cannot manufacture drift. The tell was arithmetic -- a driftless book cannot reach
+10% in a median 56 days at $720 of daily sigma, because that is 1.9 sigma of cumulative luck and
98% of paths do not get it. A separate naive reimplementation measured E[day P&L] at -0.000015
with the stop against -0.000004 without it: the stop moves variance, not drift, which is what a
stop on a driftless process must do.

The fault was conflating two different correlations. Sleeves firing in the SAME session are
correlated (same mechanism, correlated instruments, rho 0.70 measured); the same sleeve at 03:00
and at 14:00 is very nearly independent. Under a daily factor the regime is fixed at midnight and
the first trade of the day reveals it, so "stop after one loss" became a regime detector. The day
is now three independent sessions -- asia / london_am / afternoon, the desk's own windows -- and
the stand-down is worth a few points rather than a miracle. **Recorded because the wrong version
was the more attractive one**, and a simulation that says a no-edge book passes 98% of the time is
telling you about the simulation.

## The two things standing between this account and a trade

**1. TRADELOCKER IS NOT METATRADER, AND THE GATEWAY ONLY SPEAKS METATRADER.** Every order this
desk has ever sent went through the `MetaTrader5` Python package into a local terminal. This
account has no terminal. TradeLocker publishes a REST API and E8 permits automation, so the path
exists -- it is a new venue adapter behind the same `decision_core` sizing, not a new desk -- but
until it is written and its fills are reconciled, nothing here can be traded automatically. This
is the binding blocker and it is engineering, not research.

**2. COST IS UNMEASURED ON THIS ACCOUNT AND THE ACCOUNT IS COMMISSION-FREE, WHICH MEANS A WIDER
QUOTE RATHER THAN NO COST.** Third-party reports put E8's raw configuration near 0.8 pips plus
$5/lot round turn on EURUSD and about $0.26 plus $6/lot on gold; a commission-free option recovers
that in the spread. Call it ~1.3 pips all-in on a major, which on a 20-pip stop is a haircut of
roughly **0.065R per trade** -- so a +0.20R gross claim is about +0.135R net. Swaps apply through
rollover: irrelevant to the session sleeves that close intraday, a real cost to
`overnight_gap_decay`, and not a cost at all to `carry`, whose edge IS the swap.

**Every table here is read at the NET figure, and the desk's +0.20R is a GROSS replay number from
a book whose `matched_fills` is 0.** That is why the grid runs down to zero, and why the honest
column to read today is +0.10 rather than +0.20. Measure the spread on the account itself before
believing any of it -- that is one of the first things the TradeLocker adapter should publish.

**The clock starts on the first trade, not on purchase.** There is no time limit on Pro and no
reason to open a position before the book that is meant to trade it can actually reach the venue.

Artifact: `desks/mt5/reports/PROP_BARRIER.json` (`research/prop_barrier.py`).
