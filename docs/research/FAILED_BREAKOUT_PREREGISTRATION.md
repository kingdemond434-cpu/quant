# Pre-registration — failed-breakout reversion on crypto perps

**Written 2026-08-04, BEFORE any analysis code was authored and before any market data existed on
this machine.** That ordering is the only thing that makes the thresholds below meaningful: chosen
after seeing a backtest, they are a description of the backtest.

Status at time of writing: `data/bars` empty, `data/moat` empty, both venues answer 403 to CONNECT
from this container. Nothing has been measured. Nothing can be.

---

## The hypothesis, as a mechanism

When price sweeps a level carrying dense resting liquidation exposure and fails to hold beyond it
within N bars, the reversion is driven by **forced-liquidation flow exhausting**, not by
discretionary supply arriving.

The two are separable and the distinction is the whole hypothesis:

| | forced-liquidation exhaustion | discretionary supply |
|---|---|---|
| OI across the sweep | **collapses** — positions are closed involuntarily | flat or rising — new sellers arrive |
| trade-size distribution | right tail spikes then **stops abruptly** | tail persists |
| funding into the sweep | **extreme**, one-sided | unremarkable |
| liquidation prints | clustered at the level, then **cease** | absent or diffuse |
| reversion timing | begins when the print stream stops | no fixed relationship |

If the OI collapse and the print cessation are not measurable, then any edge found is an
**unexplained empirical regularity**, and must be reported as such rather than as this mechanism.

---

## Kill criteria — binding, stated in advance

The strategy is **dead** if any one of these fires. Dead means: not revived with modified
parameters, not re-run on a different symbol set, not "improved" and re-tested. It goes to the
graveyard with the failing number attached.

| # | criterion | threshold | why this number |
|---|---|---|---|
| K1 | **Deflated Sharpe** on the honest trial count | **DSR < 0.95** | the desk's standing bar. Below it, the result is not distinguishable from the best of the variants tried |
| K2 | **PBO** (probability of backtest overfitting) | **PBO > 0.30** | above this, the in-sample ranking of variants carries no information about out-of-sample ranking |
| K3 | **White's Reality Check** p-value vs the full variant family | **p > 0.05** | the family, not the winner. A best-of-N that cannot clear this is an order statistic |
| K4 | **Net Sharpe after all costs** | **< 0.5** | below this the strategy cannot survive a bad quarter or pay for its own maintenance |
| K5 | **Post-2021 decay** | edge in 2022+ **< 40%** of 2018–2020 edge | the pattern is the most-published retail setup in crypto. If it decayed that hard it is being arbitraged and will keep decaying |
| K6 | **Capacity** at which impact eats half the edge | **< $50k per signal** | below this it cannot carry meaningful size, whatever the Sharpe |
| K7 | **Mechanism absent** | OI-collapse effect size **\|d\| < 0.2** on swept vs non-swept levels | the hypothesis is specifically about forced flow. Without it, any edge is a different (unexplained) thing and this study did not find it |
| K8 | **Directional calibration** | Brier score **≥** that of the unconditional base rate | a directional call no better calibrated than "always guess the base rate" is not a directional call |

**K7 deserves emphasis.** It is possible to pass K1–K6 and fail K7 — a tradeable edge with no
mechanism evidence. That outcome is reported as *unexplained edge, mechanism not established*, and
it does **not** get promoted on this hypothesis's ticket, because the thing that was pre-registered
was the mechanism.

---

## Trial budget — counted honestly, declared before the sweep

Deflation is only honest if the count includes everything looked at, not everything reported.
Declared budget:

| axis | values | count |
|---|---|---|
| level definition: lookback for swing extremes | 20, 50, 100 bars | 3 |
| minimum touches to qualify as a level, `N_touch` | 1, 2, 3 | 3 |
| sweep threshold: penetration beyond level | 0.1%, 0.25%, 0.5% ATR-normalised | 3 |
| failure window `N_fail` | 1, 3, 5 bars | 3 |
| timeframe | 1m, 5m | 2 |
| symbols | BTC, ETH, SOL, + 7 liquid alts | 10 |
| holding rule | fixed-N-bar, ATR-stop, level-retest | 3 |

**Nominal trials = 3 × 3 × 3 × 3 × 2 × 10 × 3 = 4,860.**

Symbols are **not** independent trials — crypto perps are ~0.8 correlated — so the effective
count is deflated to **≈ 1,458** (4,860 with the symbol axis counted as ~3 effective rather than
10, via the effective-breadth calculation already in `libs/ict/cross_sectional.effective_breadth`).
Both numbers are reported. DSR uses the effective count; if the verdict differs between the two,
the **nominal** count governs.

Any axis added later is added to this table **and the DSR is recomputed**, or the study is void.

---

## Feature definitions — causal by construction

Stated exactly, because "no look-ahead" is a property of the definition rather than an intention.

**Level.** At bar close `t`, a *level* is a swing extreme confirmed by `k` bars on **both** sides,
where the right-hand `k` bars are all at or before `t`. A swing high at `t-k` is therefore not
known until `t`, and is usable from `t+1`. It never uses a high or low after `t`.
*Rejected alternative:* `rolling(window).max()` centred on the bar — that is the standard
formulation and it is a time machine.

**Touch.** Price trades within `tol × ATR(t)` of the level without closing beyond it. `N_touch`
counts touches strictly before `t`.

**Sweep.** A bar whose high exceeds the level by more than `θ × ATR(t)` (or low, for support),
where ATR is computed on bars `≤ t`.

**Failure.** Close back inside the level within `N_fail` bars of the sweep, evaluated only at the
close of each of those bars. The signal fires at the **close of the failure bar**, and entry is at
the **open of the next bar** — never the failure bar's close, which is not obtainable.

**Every one of these is testable for leakage by truncation:** recomputing on data up to `t` must
reproduce the value at `t`. That test is mandatory and is part of the harness, not a review step.

---

## The ablation that answers the caveat

The discretionary version of this worked partly on context a rule cannot see — which zone mattered,
whether the tape was chopping. So the harness measures the decomposition rather than assuming it:

1. **entry rule alone** — signal fires, fixed exit, no filter
2. **entry + mechanism filter** — only when OI-collapse and funding-extreme conditions hold
3. **mechanism filter alone** — enter on the mechanism regardless of the price pattern
4. **regime filter alone** — trade only in the regime where (1) performed, chosen out-of-sample

If (3) ≈ (2) > (1), **the entry was never the alpha** — the mechanism was, and the chart pattern
was a noisy proxy for it. That is a publishable result and it is the outcome I consider most
likely a priori.

If (4) ≈ (2), the edge is regime selection, not the setup.

---

## Costs — modelled before scoring, not after

Reported **net only**. Gross Sharpe is not to appear in the output at all.

- taker fee both legs at the venue's actual tier
- funding paid or received across the hold, from real funding history
- slippage from **actual recorded book depth** via `libs/execution/book_walk.walk_book` — not a
  bps assumption
- adverse selection on any limit fill via `libs/backtest/queue_fill.maker_fill` — FIFO queue
  position, not an assumed fill rate

A sweep bar is by definition a moment of **thin, fast-moving book**. Slippage modelled at median
depth is the single most likely way this study reports an edge that does not exist, so slippage is
taken at the **p10** of depth observed in the sweep bars themselves.

---

## Regimes required

No verdict without all four, identified out-of-sample by a regime model that does not see returns:

1. trend up, 2. trend down, 3. chop, 4. **at least one full deleveraging event**

The deleveraging event is not optional. It is the regime the mechanism claims to be about, and a
result that excludes it has not tested the hypothesis.

---

## What would make me abandon this

Stated plainly, in advance: **I expect this to fail K5 or K7.** The pattern is the most-published
retail setup in crypto, and the most likely truth is that the entry was a proxy for a mechanism
that is either arbitraged away post-2021 or was never measurable from the entry rule alone.

If it dies, this document is the record of what it was tested against, and the graveyard entry
carries the failing number. No variants in the same report.

---

# AMENDMENT 1 — the management arm (written 2026-08-06, before anything below it was run)

Amended, not rewritten. The document above stands unchanged; this section adds axes and a fifth
ablation arm, and **pays the deflation for them up front**, per the standing rule that any axis
added later is added to the budget table or the study is void.

## The claim this amendment tests, stated as its author put it

> "Your edge today wasn't the 4265 level. Your edge was the 4263 structural stop loss, the
> wait-for-the-close rule, and the breakeven management."

That is a **specific, falsifiable, and currently untested** claim, and it identifies a real gap in
the four-arm ablation above: **every one of those four arms uses the same fixed exit.** The
decomposition can separate entry from mechanism from regime, and it cannot separate any of them
from *management*, because management is held constant across all four. If the claim is right, the
existing ablation is structurally incapable of noticing.

## The arithmetic that bounds the claim — and makes it falsifiable

An exit rule **cannot manufacture expectancy from a zero-expectancy entry.** Under a driftless
price process, every stop/target policy is a stopping time on a martingale, and optional stopping
gives every one of them the same expected value: zero. Wider stops raise win rate and enlarge the
loss when it comes; breakeven ratchets raise win rate and truncate the right tail. They **reshape
the payoff distribution; they do not move its mean.**

So the claim can only be true through one specific channel, and naming it is what makes it
testable rather than folklore: the conditional path distribution after a sweep must be
**asymmetric in a way the stop distance interacts with** — e.g. penetration beyond the level
mean-reverts within a bounded excursion, so a stop *outside* that excursion converts a loser into
a winner while a stop inside it does not. That is a measurable property of the tape (the
distribution of maximum adverse excursion conditional on a sweep), and it is measured directly
rather than inferred from a P&L difference.

**Corollary, pre-registered so it cannot be re-litigated later:** if the MAE distribution
conditional on a sweep is not distinguishable from the unconditional one, the management arm is
dead regardless of what its backtest says, and a positive backtest is then evidence of fitting.

## New axes, and the exact price paid

| axis | was | becomes | count |
|---|---|---|---|
| holding rule | fixed-N, ATR-stop, level-retest | + **structural stop** (beyond the sweep wick + buffer), + **breakeven ratchet** at 1R | 3 → **5** |
| timeframe | 1m, 5m | + **1h, 4h** (the "institutions don't fake out on H1" crowding claim) | 2 → **4** |

**Nominal trials: 3 × 3 × 3 × 3 × 4 × 10 × 5 = 16,200** (was 4,860).
**Effective trials: 4,860** (symbol axis at ~3 effective, as before; was 1,458).
**Three-study shared budget: 5,220 → 16,560.**

The deflation cost is small and is stated rather than hidden: the expected maximum of `N` null
trials scales as `√(2 ln N)`, so the hurdle moves **4.138 → 4.408, about +6.5%**. That is what
makes this amendment worth making — it buys the single most informative arm available for a
7% harder bar. It is not free, and the number is here so it is not treated as free.

## Arm 5 — management alone, on RANDOM entries

The decisive test, and it is nearly free to run:

5. **management alone** — random entry times matched to the sweep-time distribution, identical
   wait-for-close, structural stop, and breakeven ratchet.

Read exactly as the existing arms are read:

- **If (5) ≈ (2), the entry was never the alpha and neither was the mechanism** — the result is a
  payoff-shape transform, and it will not survive costs, because a wider stop pays more slippage
  on the trades that do hit it.
- If (5) ≈ 0 and (2) > 0, management is a **modifier** of a real entry edge, which is the only
  version of the claim worth sizing.
- If (5) > 0 **net of costs**, the harness is broken. Random entries do not have edge. That
  inference is pre-registered here, identically to the crowded-control rule in
  `THREE_MECHANISM_PREREGISTRATION.md`, so it cannot be reinterpreted as a discovery.

Entry times are matched to the sweep-time **distribution**, not drawn uniformly: sweeps cluster in
high-volatility hours, and a uniform random control would compare a quiet-hour baseline against a
volatile-hour strategy and call the difference edge.

## K9 — the new kill criterion

**K9.** If arm 5 reaches ≥ 70% of arm 2's net Sharpe, the entry rule is retired and the study is
reported as a **management/payoff-shape finding**, never as a failed-breakout edge. 70% rather
than 100%: a management rule capturing most of the claimed edge already falsifies the mechanism
story, and demanding exact equality would let a 30% shortfall preserve a hypothesis it does not
support.

## Priors, recorded before the run so a confirmation cannot be retrofitted

- **Breakeven ratchet: I expect it to LOWER net Sharpe.** It raises win rate — which is why it
  feels good and is near-universal in retail systems — by truncating precisely the right tail that
  pays for the losers.
- **Structural stop: I expect it to raise gross return and lower net**, because its edge case is
  the fast, thin sweep bar, which is the worst possible moment to be taking a market exit. This is
  the arm most likely to look good until `walk_book` slippage at p10 depth is charged.
- **Higher timeframes: I expect no crowding-decay improvement, and worse power.** The "H1 is less
  saturated" claim confuses *fewer participants* with *more edge*, and 4h bars over the available
  history give a sample too small for the DSR to clear at any effect size this hypothesis could
  plausibly have. That is a **power** objection, and it is the reason to be sceptical of the arm
  before any of it is run — not a reason to skip it, since it is now declared and paid for.
