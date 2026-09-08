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
