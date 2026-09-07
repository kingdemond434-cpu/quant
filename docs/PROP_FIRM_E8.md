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
