# MANAGEMENT-POLICY SWEEP — PRE-REGISTRATION (2026-08-07)

**Status: PRE-REGISTERED, NOT RUN.** Kill criteria and the trial budget are fixed below before any
data is touched.

## The question, stated so it can be wrong

Is trade MANAGEMENT — stop placement, target placement, breakeven ratchets, partial exits, trailing,
time stops, volatility-scaled sizing — a source of expectancy **independent of entry timing**?

The claim under test, from a discretionary write-up forwarded by the principal: *"Our edge isn't our
win rate. Our edge is asymmetric risk... 1:4 R:R with a 40% win rate yields positive expectancy."*

`FAILED_BREAKOUT_PREREGISTRATION` arm 5 already tests ONE management rule against ONE entry rule.
This generalises it: **every management policy, on entries with no signal at all.**

## Design — the entry is deliberately worthless

Entries are RANDOM, matched to the realised-volatility distribution of the tested venue rather than
drawn uniformly. Uniform draws would compare quiet-hour baselines against volatile-hour policies
and score the difference as management skill. **If any policy shows expectancy on random entries
net of costs, the finding is about the harness, not the market** — and that inference is fixed here
so it cannot be reinterpreted after the fact.

| axis | values |
|---|---|
| stop | 0.5·ATR, 1.0·ATR, 1.5·ATR, 3.0·ATR |
| target | 1R, 2R, 3R, 4R, none (time exit) |
| breakeven ratchet | off, at 0.5R, at 1R |
| partial exit | off, 50% at 1R |
| trailing | off, 1·ATR chandelier |
| time stop | 4h, 24h, none |
| sizing | fixed, **vol-targeted (∝ 1/ATR)** |
| **nominal** | 4×5×3×2×2×3×2 = **2,880** |

**These 2,880 JOIN the shared deflation budget: 17,172 → 20,052.** Hurdle √(2 ln N) moves
**4.416 → 4.451**. An axis added anywhere makes the bar harder everywhere; a budget updated only
where the axis was added is not shared.

## What the theory predicts, recorded so the result can falsify it

Stops and targets are **stopping times**. On a driftless process, optional stopping gives an
expected value at any stopping time equal to the starting value. **No stop/target geometry creates
expectancy** — it reshapes variance, skew and hit rate and leaves the mean where it was, minus
costs. Specifically:

- **R:R and win rate are NOT independent.** Widening the target and tightening the stop lowers the
  hit rate roughly proportionally; at 1:4 it converges toward ~20%. "40% at 1:4" asserts directional
  edge and calls it risk management.
- **The breakeven ratchet is not free.** It converts some WINNERS into scratches — trades that
  retrace to entry then continue — in exchange for removing some losers. It feels free because the
  loss it prevents is visible and the winner it kills is not.

**THE ONE ARM PREDICTED TO WORK, AND FOR A DIFFERENT REASON THAN USUALLY GIVEN.** Vol-targeted
sizing should raise the **geometric** mean while leaving the **arithmetic** mean unchanged. It is
not "size up for bigger moves" — that is the opposite of what it does. It equalises RISK per trade,
reducing return-stream variance, and geometric growth is reduced by variance
(E[log W] ≈ μ − σ²/2). So it can raise compounding with **zero directional edge**, which is exactly
what this desk's objective asks for.

## Kill criteria — BINDING, fixed before the run

| # | Criterion | Kills / concludes |
|---|---|---|
| M1 | **Arithmetic-mean invariance** | If policies differ in arithmetic mean beyond Monte-Carlo error on random entries, the HARNESS IS BROKEN — not a discovery |
| M2 | Cost monotonicity | Higher-turnover policies must show strictly worse net; a violation is a cost-model defect |
| M3 | Vol-targeting | Must raise the GEOMETRIC mean net of costs. A null indicts the harness or cost model, not the mechanism (the effect is well supported) |
| M4 | Breakeven ratchet | Predicted ≈ neutral on the mean. A POSITIVE result requires the winner-truncation to be measured and reported, not inferred |
| M5 | Sample floor | <200 trades per arm → **UNMEASURED**, never "no effect" (L1.28a) |
| M6 | Deflation | No arm may be called an effect below √(2 ln 20052) = 4.451 |
| M7 | Selection ban | The best-of-2,880 arm is an ORDER STATISTIC. It may not be reported as a finding without clearing M6 on its own |

**M1 is the positive control and the most important row.** These policies are applied to entries
with no information in them. Their arithmetic means must agree. If the harness says otherwise, every
other number it has produced — including the failed-breakout study — is suspect, and that is the
most valuable outcome available here.

## Authority

**NONE.** Stage A. Pre-registers nothing beyond a measurement, promotes nothing, sizes nothing,
trades nothing. A surviving management policy earns a place in the queue, never capital.
