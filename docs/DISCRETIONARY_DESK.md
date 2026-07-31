# The Discretionary Desk — Binance perpetuals

**Venue: Binance USD-M perpetual futures. Nothing here trades MT5.** The principal's MT5 gold
screenshots were the *origin* of this desk and the source of one measured data point about trail
width. They are a separate personal account and are never this desk's venue, price source, or
benchmark. Prices come from Binance USD-M with OKX as fallback (Binance returns 451 from some
egress regions, and a sleeve that dies on that is a sleeve that never runs).

This is a first-class section of the platform, equal in priority to the systematic side — its own
organs, its own evidence ladder, its own learning loop, and its own place in the law gate.

## Why it exists

The systematic side has tested 420 statistical patterns and promoted **zero**. Discretionary
reasoning over heterogeneous evidence is a genuinely *different class* of attempt, not attempt
#421. That is the whole argument for this desk, and it is a good one.

It is also the weaker of the two hypotheses this desk runs, and saying so is part of running it
honestly. Chart structure is public — every screen shows the same 6-touch shelf, and there is no
structural reason an LLM reading it beats the people and bots already reading it. The stronger
version is the event sleeve (R0122): multi-step causal reasoning across heterogeneous documents,
where an LLM plausibly has an asymmetry a human desk does not. Chart structure is what makes a
trade *sane*; it is not by itself the edge. Both are built, both are scored, and the forward clock
settles it rather than either opinion.

## The organs

| organ | cadence | what it does |
|---|---|---|
| `build_chart_context.py` | 20 min | multi-timeframe structure for 18 instruments: fractal swing levels **with touch counts**, trend from the swing sequence, position in range, room to the next level, vol regime, and the measured correlation matrix |
| `run_conviction_trader.py` | hourly | reads the charts, the playbook and the noise floors; names an invalidation **level**; the desk derives the stop, sizes it, and books it |
| `resolve_paper_book.py` | hourly | walks the recorded ladder against real bars, deducts fees/slippage/funding, benchmarks vs buy-and-hold, feeds calibration, reports growth |
| `run_trade_review.py` | after closes | reviews each closed trade against its own thesis, classifies the cause, extracts a falsifiable lesson |
| `check_mechanism_attribution.py` | hourly | refuses "survived" for any sleeve whose P&L its mechanism cannot explain |

## The method, and why each piece is there

**The stop is calculated, not chosen.** The model names an invalidation *price* and the structure
it belongs to; the desk derives the distance. It refuses an invalidation on the wrong side of
entry, a stop not at a named structure, and an asserted `stop_pct` that contradicts the level
named. This is not bookkeeping — Kelly sizes `risk_budget / stop_distance`, so a real 1% swing
carries multiples of the size a lazy 4% stop does on the same edge.

**The noise floor is measured per instrument and per horizon.** The median distance price goes
*against* a random entry over that horizon. Measured: PAXG 24h long 0.64%, SOL 24h long 1.28%. A
single flat minimum was ~2.5× too loose on one and about right on the other. A stop inside the
noise turns a *correct thesis* into a loss, which is the most expensive way to be right.

**Winners are ridden, not taken.** No take-profit. Breakeven, then trail, then add on strength.
Open risk falls 1.00 → 0.50 → 0.25 → 0.00 of the entry budget while exposure rises to 1.75u —
computed from the tranche book, not asserted, and pinned by tests.

**The position clock is not the forecast clock.** `horizon_hours` scores the forecast; the
position runs to its structural exit with a hard stop at 4× that. Measured: the same trade reads
+0.07R at a 12h horizon and +0.63R at 30h. An arbitrary clock was setting the P&L.

**Aggression lives in breadth and frequency, not bet size.** Simulated: at 20% risk per trade this
book meets a −90% drawdown with near-certainty *even when profitable*, and past full Kelly more
size makes growth **negative**. Holding total heat fixed and changing only its shape, one bet at
24% gives P(−90%) = 100% while eight at 3% give 0%. So: 6% per trade, 18 instruments, hourly, up
to 5–8 concurrent, 30% effective heat — *more* total exposure than one-bet-at-20% ever ran.

**Heat sizes the trade rather than blocking it.** A busy book trims a good setup instead of
refusing it; an unbooked setup contributes exactly zero to compounding. Solved against *effective*
heat, so correlation decides the room — on a 5-alt book gold fits at 4.39% where LTC fits at 3.14%.

**Size follows measured accuracy, both directions.** If the sleeve claims 0.63 and truly hits 0.45,
sizing on 0.63 is ~2× Kelly and growth is negative. A sleeve measured *under*-confident gets its
size raised automatically. The raw claim is still what gets scored.

## Training the brain

Weights are fixed; nothing here fine-tunes anything. What improves is the desk's evidence-weighted
knowledge of **which setups actually pay** — the same way a journal improves a human trader: not by
making them smarter, but by stopping them repeating the mistake they cannot see from inside a
single trade.

**The review loop** reads each closed trade against what was claimed at entry and classifies the
cause into something actionable: `THESIS-WRONG`, `LEVEL-WRONG`, `TIMING-WRONG`, `NOISE-STOP`,
`RIGHT-AND-PAID`, `RIGHT-BUT-TRUNCATED`, `UNLUCKY`. That last one is load-bearing — a desk that
cannot tell right-and-unlucky from wrong will "fix" a process that was working.

**The playbook is an evidence ladder, not a pile of opinions.** A lesson enters PROVISIONAL and
carries no authority; it becomes SUPPORTED only after 3 independent agreeing trades; it is RETIRED
the moment a trade contradicts it, and the contradiction is recorded so it cannot quietly return;
it goes STALE if the desk stops testing it. **Only SUPPORTED lessons reach the trading brief** — one
lucky trade must not rewrite the method. Same standard the rest of the desk applies to alpha.

**Outcomes are conditioned on the setup.** A single global hit rate hides everything actionable: a
sleeve that is 55% with the 4h trend and 25% against it reads as a mediocre 40% overall, and the
fix — stop taking counter-trend setups — is invisible until the outcomes are split. Every trade is
tagged with trend alignment, vol regime, position in range, level touch count and horizon bucket;
buckets under 5 trades report INSUFFICIENT rather than a number, because a 100% hit rate on two
trades is not a finding and publishing it as one is how a desk learns superstition.

## What 300% net CAGR actually requires

Growth is `g × N`. Costs are measured, not assumed: at ~6.7× leverage a round trip is ~1.0% of
sleeve equity maker-in / taker-out — about 17% of one R.

| true hit rate | net per trade | outcome at ~460 trades/yr |
|---|---|---|
| ≤ 29% | negative | **graveyard — costs eat it** |
| 30–32% | ~0 | flat |
| 35% | +1.4% | 100–300% |
| **38%+** | +2.1% | **300%+** |

**Cost-adjusted breakeven is 31.1%, not 25%.** The target needs roughly a **38% hit rate**. That is
not heroic — but it is unmeasured, and the entire distance between "this compounds hard" and "this
is a slow bleed" is about seven points of a number nobody has yet observed.

Nothing in this document changes that. Only the forward clock does.

## Standing rails

Paper only until it earns real size the same way everything does (L1.6): a forward clock, beating
buy-and-hold **and** the carry sleeve after costs. Every call is a pre-registered forecast scored by
L1.29. Per-trade risk ≤ 6%, effective heat ≤ 30%, gross ≤ 50%, sleeve drawdown halt at 35%, and
the whole sleeve inside the book's −35% ruin rail (L1.23). Every money-path constant carries its
derivation (L1.41). It places no orders.
