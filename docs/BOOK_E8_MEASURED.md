# The fastest E8 book the desk can actually field — measured, 2026-09-08

Answering the principal's question: *"calculate every sleeve we have currently, the most promising
ones, all the most uncorrelated ones, as much quantity as you can find, and calculate the fastest
book possible — highest passing probability, under a month, safe."*

**Nothing here is a decision to trade.** No sleeve gets capital from this document; the ten gates,
a forward clock and measured rent decide, exactly as for anything else.

## What was actually measured

Every sleeve in `sleeve_registry.json` (53) was replayed from the local H1 lake through the same
call the forward clock uses — `family_call` shape, frozen cost basis, `run_backtest` — to a
**dated** trade series. 40 replayed (13 have no local bars), **104,916 trades**.

Two windows, deliberately not interchangeable:

| quantity | window | why |
|---|---|---|
| expectancy | out-of-sample **by symbol** | the means are what selection contaminates |
| co-movement, trade rate | full history, 2018-01-02 → 2026-08-28 | sleeves were never selected on their mutual correlation, and there are nowhere near enough forward days to estimate a 16×16 covariance |

Forward expectancy could **not** be recomputed here: the local lake ends **2026-08-28** and every
forward clock opened after it. Forward figures below are the box's own, read from
`dash.quanttt.xyz/desk_state.json` at 02:20 UTC.

## Finding 1 — the live book is one mechanism on five symbols

Of 56 rows the box reports, **14 are `ACTIVE`**; everything else is `RETIRED_ORPHAN`,
`BLOCKED_NO_BARS` or `RETIRED_UNRECONSTRUCTIBLE`. All 14 are `session_range_breakout` on the
`asia` window, over **5 symbols** — USDJPY, CADJPY, XAUUSD, EURJPY, GBPJPY.

The `rr=1.5 / 2.0 / 2.5` variants are one entry with three targets and **correlate at 0.91–0.96**.
Fifteen clocks on five symbols are worth **k_eff = 4.5** independent bets, and the five distinct
signals are worth **4.1**. Counting parameterisations as breadth overstates it ~3×.

## Finding 2 — `discovered` is 21 of 53 clocks and has no edge in its own selection window

| family | sleeves | trades | exp_R (full history) | k_eff |
|---|---:|---:|---:|---:|
| `discovered` | 21 | 72,326 | **−0.006** | 14.74 |
| `session_range_breakout` | 15 | 31,937 | +0.126 | 4.47 |
| `overnight_gap_decay` | 1 replayable | 653 | +0.238 | 1.00 |

`discovered` is negative **in the window it was searched in** — before any out-of-sample haircut.
It carries the most statistical breadth in the registry and none of it is worth anything, because
breadth multiplies an edge and there is no edge to multiply. It should be retired.

## Finding 3 — the mechanism generalises, but only where the instrument can pay for the trade

The certified cell (`range_start=7, rr=2.0, ttl_bars=12, wait_bars=12`) was applied **unchanged**
to every symbol with local bars and a measured spread — 31 symbols, 63,249 trades. Raw:

| set | symbols | trades | exp_R | t | positive |
|---|---:|---:|---:|---:|---|
| in-sample (the 5 chosen) | 5 | 10,687 | **+0.1413** | +13.9 | 5/5 |
| out-of-sample | 26 | 52,562 | **−0.4046** | −49.6 | 13/26 |

That reads as a dead mechanism and is not one. The OOS pool is dominated by instruments whose
round trip exceeds their stop distance:

```
cost_ratio = round-trip cost in price units / median stop distance (1.2 x ATR20)
```

ADAUSD **1190%**, BCHUSD 206%, BNBUSD 204%, AUDCHF 98%, NZDJPY 93%, AUS200 58%, ETHUSD 54%. The
rank correlation between `cost_ratio` and expectancy across all 31 symbols is **−0.855**.

Screened **ex ante** — spread and ATR only, never the outcome:

| threshold | symbols kept | OOS exp_R | t | positive |
|---|---:|---:|---:|---|
| ≤ 5% | 2 | +0.1136 | +5.5 | 1/1 |
| ≤ 8% | 5 | +0.0704 | +5.7 | 2/3 |
| ≤ 10% | 10 | +0.0540 | +6.3 | 4/6 |
| **≤ 15%** | **16** | **+0.0552** | **+8.0** | **9/11** |
| ≤ 25% | 24 | +0.0332 | +6.4 | 13/19 |

**The honest edge is +0.055R, not the +0.20 every earlier plan assumed and not the +0.141 the
five chosen symbols show.** Out-of-sample is ~39% of in-sample, which is an ordinary haircut.

The screen is legitimate precisely because it never looks at P&L. Dropping symbols because they
lost would be a second pass of selection; dropping them because the desk cannot pay their spread
is arithmetic.

## The book

**16 symbols** at cost/stop ≤ 15%: AUDCAD, AUDSGD, BTCUSD, CADJPY, CHFJPY, EURAUD, EURCHF, EURJPY,
EURUSD, GBPAUD, GBPJPY, GBPUSD, USDCAD, USDCHF, USDJPY, XAUUSD.

* mean pairwise ρ **+0.072**, max +0.400
* **k_eff = 13.26** independent bets (against 4.1 live today)
* ~13 trades/day, 2,636 trading days in the matrix

Note the mean ρ flatters it: flat-filling 0.072 gives k_eff 14.85. The 1.6 missing bets are the
JPY cluster. Anything sizing on a mean correlation is sizing on a book that does not exist.

## The simulation

E8 One, $100k. Target is fixed at **1.5 × drawdown**, so the barrier *ratio* cannot be bought —
only a bigger or smaller arena. Days are **bootstrapped as whole rows** out of the measured daily
matrix in 5-day blocks, so shared drawdowns and shared dead weeks survive. No ρ is assumed
anywhere. Every sleeve's mean is forced to **+0.0552R**, incumbents included.

Modelled: trailing **and** static max DD, the 4% daily loss limit against each day's opening
equity, and the **40% consistency rule** — no single day above 40% of total profit. Every earlier
estimate on this desk ignored the consistency rule; modelling it turns out to be worth 1.0 point,
so it was worth including and was NOT, as first written here, "what bounds fast". The barrier
ratio bounds fast.

### What breadth buys (6% static DD, same mechanism, only the symbol count changes)

| book | n | k_eff | risk | P(pass) | P(pass ≤30d) | median |
|---|---:|---:|---:|---:|---:|---:|
| live today | 5 | 4.08 | 0.25% | 65.8% | **3.2%** | 86d |
| live today | 5 | 4.08 | 0.50% | 64.8% | 25.7% | 37d |
| screened | 16 | 13.26 | 0.25% | 76.5% | **38.3%** | 30d |
| screened | 16 | 13.26 | 0.35% | 61.4% | 43.2% | 21d |

**Breadth buys TIME, not pass probability** — see the attribution table below, which isolates it
properly by holding risk fixed. At a common 0.30% the two books pass 70.9% (5 symbols) against
73.5% (16); what separates them is 69 days against 28. The apparent gap in the table above is
mostly the risk level moving with the book, not the book itself. What remains true either way is
that the 5-symbol book cannot pass inside a month at any size: pushed fast enough to try, it
fails more often than it passes.

### Static beats trailing, everywhere

At 6% DD / 0.25%: **76.4% static vs 57.1% trailing**. If both products are on offer, the
static-drawdown one is worth materially more than any risk-setting choice within it.

### The daily stop, modelled honestly

At 13 trades/day the **daily loss limit**, not the max drawdown, becomes the binding barrier —
0% of deaths at 0.20% risk, 22.8% at 0.30%, 72.9% at 0.45%.

A first pass modelled the stop by clipping the day's total loss and reported 0.25% risk going
76.8% → **97.8%**. That was an upper bound and wrong: it assumed the stop fired at exactly the
right moment and kept every recovery for free. Re-run with trades realised in **exit order**, a
running daily stop, and forgone winners included:

| risk | no stop | −8R | −6R | −5R | −4R | −3R |
|---|---:|---:|---:|---:|---:|---:|
| 0.25% | 76.5% | 77.0% | 77.1% | 78.3% | 78.3% | 77.0% |
| 0.35% | 63.1% | 68.4% | 68.0% | 69.4% | 69.0% | 67.9% |
| 0.45% | 44.6% | 59.9% | 61.2% | **62.2%** | 61.6% | 60.4% |
| 0.60% | 28.1% | 22.6% | 43.4% | 53.3% | **53.9%** | 51.9% |

The real gain is **2–5pp at low risk** — not 20. It only becomes large where the daily limit was
already the thing killing the account, which is exactly what the barrier diagnosis predicted.

## The recommendation

**E8 One $100k · 6% drawdown (9% target) · static if available · 16-symbol book · 0.30% risk per
trade · −5R daily stop.**

> **P(pass) 60–75% · median 25–35 days.** The point estimate at this exact specification is 73.6%
> with a 28-day median (p90 70d, P(fail) 26.1%, P(pass within 30d) 40.5%) — but see the band
> below. The specification uncertainty around it is 49 points wide, so the point estimate is
> reported for reproducibility and the BAND is the answer.

Alternatives on the same frontier:

| goal | setting | P(pass) | median | P(≤30d) |
|---|---|---:|---:|---:|
| highest pass probability | 0.25% + −5R | **78.3%** | 33d | 35.5% |
| fastest that still passes | 0.35% + −8R | 68.4% | 23d | **44.6%** |
| maximum pass, any speed | 0.15%, no stop | 85.9% | 60d | 12.6% |

### The honest limit on "under a month"

Median 28 days is the median **of the paths that pass**. The probability of passing *within* 30
days peaks at **~44.6%** across everything tested. **No configuration both passes reliably and
passes inside a month** — that is a property of the 1.5:1 barrier and the consistency rule, not of
the sizing. Buying speed past this point buys failure, not time.

## Why this number has moved, and the band it must not leave again

Recorded 2026-09-08 after the principal pointed out, correctly, that the pass probability changed
every time it was asked for: 92% (the original doc), 67%, 73.6%. The defence "each change was a
correction" is worth nothing unless the changes are ATTRIBUTABLE, so they were attributed. Same
account, same 0.30% risk, one specification choice changed at a time:

| what changed | P(pass) | median | vs base |
|---|---:|---:|---:|
| **base: OOS exp_R, 16 symbols, consistency on** | **73.5%** | 28d | — |
| exp_R = +0.20 (the original assumption) | 98.9% | 14d | +25.4 |
| exp_R = +0.1413 (the in-sample five) | 95.2% | 18d | +21.8 |
| exp_R = +0.109 (forward breakout) | 90.4% | 21d | +16.9 |
| **trailing drawdown instead of static** | 50.3% | 21d | **−23.1** |
| exp_R at its 95% bounds | 66.3% / 79.4% | 29d / 26d | ∓7 |
| 5 live symbols instead of 16 | 70.9% | 69d | −2.6 |
| no daily stop | 70.3% | 25d | −3.1 |
| consistency rule not modelled | 74.4% | 24d | +1.0 |

**Specification range 50.3%–98.9% (49 points). Sampling range with the spec fixed, 13 points.**

The dominant uncertainty is SPECIFICATION, not sampling, and every point estimate this desk has
published sat inside the band while being quoted to one decimal place. That was the error, each
time, independent of which estimate was closest — a number whose specification band is 49 points
wide is not decision-grade at any precision.

**The standing answer is a band: 60–75% pass, 25–35 day median**, at $100k / 6% static DD /
0.30% risk / 16 symbols / −5R daily stop. It does not move again without one of these:

1. **Static vs trailing confirmed** — worth 23 points, the single largest term, and it is a
   product fact rather than a measurement.
2. **`repair_universe_spreads.py --apply` on the full lake** — 199 symbols still carry no
   measured spread. Widens the book past 16, which buys TIME, not probability.
3. **Forward clocks on the 11 unenrolled symbols** — the only step that kills the exp_R
   uncertainty rather than bounding it.

### Two claims in this document were overstated and are corrected here

* **"Breadth is the entire story" — wrong for pass probability.** At 0.30% the 5-symbol book
  passes 70.9% against the 16-symbol book's 73.5%. Breadth is the entire story for TIME
  (69 days against 28) and close to nothing for whether the account passes at all.
* **The consistency rule is worth 1.0 point, not "what bounds fast".** The barrier ratio bounds
  fast. The rule was worth modelling and was not worth the emphasis it was given.

## Four things that would make this wrong

1. **Mechanism breadth is 1.** k_eff 13.26 is *instrument* diversity. All 16 sleeves are one
   mechanism; if `asia` range breakout stops working, all 16 stop together and the correlation
   matrix will not have warned anyone. This is the book's real fragility, and it is not priced in
   any number above.
2. **11 of the 16 symbols have no forward clock.** They would be fielded on out-of-sample-by-symbol
   evidence alone. That is real evidence and it is not the same as a forward clock.
3. **The edge could be overstated.** At half of +0.0552 the recommendation gives 57.4% pass; at a
   quarter, 49.6%; at zero, 40.6% — the account survives long enough to time out rather than
   blowing up, which is what the daily stop is buying.
4. **Local bars end 2026-08-28** and 199 symbols in the registry still carry no measured spread.
   `repair_universe_spreads.py --apply` on the full lake would widen the screened book beyond 16
   and is the highest-value next step for speed.

## Reproducing it

`libs/portfolio/symbol_breadth.py` holds the ex-ante screen and `effective_breadth`;
`tests/portfolio/test_symbol_breadth.py` pins the four ways a breadth claim can be a lie. The
replay and simulation harnesses used for the tables above are session scratch and are not
committed — they depend on the desk tree, which lives on
`claude/llm-auto-upgrade-verify-gcjac3`.
