# APPENDIX A -- PENDING PRINCIPAL RESEAL (parked 2026-08-18, owed-work batch3)

**GOVERNANCE (§36): governed by L2.8 (constitutional evolution) as a PENDING amendment; terminal
disposition arrives when the principal either reseals the master with this content or rejects it.**

**WHY THIS FILE EXISTS.** Sections 218-223 below were appended to the SEALED master
(docs/MASTER_QUANT_CONSTITUTION.md) by session commits 98d63ce3 + 6b8b61a9 (2026-08-17 21:39/22:05Z)
WITHOUT a reseal -- and `check_constitution_core.py --reseal` is PRINCIPAL-ONLY by design. From
2026-08-17 21:39Z the master violated its own seal (225 headings vs the locked 0..217, lock sha
b04d813e), and the measured blast radius was:

- the LIVE cash-carry executor (`guard(strict=True)`, L1.42 money path) crash-looped on
  LawBreach CORE-SEAL -- 2,242 restarts over ~22h; zero trading and zero book management;
- every organ spawn's fast law gate printed BREACH CORE-SEAL (frontier seats, brain runs);
- `run_law_gate.py` failed desk-wide.

The master was restored to its exact sealed bytes on 2026-08-18 (this commit); the appendix moved
here, UNCHANGED, for the principal's decision. Restoring the sealed text is seal ENFORCEMENT, not
an opinion on the content: the content may well be worth adopting -- that adoption is the
principal's act (`python scripts/check_constitution_core.py --reseal` after re-appending).

---

================================================================================

# APPENDIX A. REPRESENTATION, COMPILATION, COMPUTE AND MICROSTRUCTURE

# SECTIONS 218-223. ADDITIVE. NOTHING ABOVE IS REPEALED.

Six capabilities are added below. Everything else proposed alongside them was
already covered by sections 1-217 and is not restated.

## A.0 TWO CLAIMS THIS APPENDIX EXPLICITLY REFUSES

These additions are frequently sold with two assertions. Both are false and
adopting either would make this operation worse.

# FIRST: THAT AUTOMATED SEARCH AT SCALE ELIMINATES OVERFITTING RISK.

It does the opposite. Selection bias scales with the number of things selected
among. A factory that tests ten million hypotheses is not safer than one that
tests a thousand; it is three and a half orders of magnitude more dangerous, and
its danger is invisible in every individual result. The genealogy requirement,
null and placebo tests, DSR/PBO-style controls, untouched chronological OOS and
frozen-forward evidence are not friction to be optimized away as throughput
rises. They are the only reason throughput is permitted to rise at all.

# EVERY CAPABILITY IN THIS APPENDIX INCREASES TRIAL COUNT.

# EVERY ONE THEREFORE INCREASES ITS OWN MULTIPLICITY BURDEN.

# THE BURDEN IS PAID, RECORDED, AND REPORTED. IT IS NEVER ASSUMED AWAY.

# SECOND: THAT A CORRECTLY BUILT ARCHITECTURE MAKES 100-200% CAGR REALISTIC BY DEFAULT.

Architecture does not manufacture alpha. It raises the probability of finding
alpha, lowers the cost of testing it, and shortens the path from discovery to
capital. The return level is then whatever the forward evidence supports, and
sizing follows that evidence rather than the ambition. A triple-digit outcome is
accepted if independent forward alpha, diversification, execution quality and
capacity jointly support it without unacceptable ruin probability. It is never
a target that justifies leverage.

================================================================================

# 218. MARKET EVENT TOKENIZATION AND SELF-SUPERVISED MICROSTRUCTURE LANGUAGE

## 218.1 THE PIPELINE

    RAW TICKS
        -> EVENT ENCODER
            -> DISCRETE MARKET TOKENS
                -> SELF-SUPERVISED SEQUENCE MODEL

## 218.2 THIS IS NOT "BPE FOR TICKS"

Byte-pair encoding was designed around repeated symbol fragments in text.
Markets carry continuous numeric and state information, and a tokenizer that
assumes otherwise imports an assumption it cannot defend. BPE-style merging of
recurrent market motifs is ONE CANDIDATE ENCODER AMONG SEVERAL, entered as a
competitor and retained only if it wins.

## 218.3 CANDIDATE TOKEN VOCABULARY

Tokens encode market events, not prices:

    UP_SMALL              UP_LARGE              DISPLACEMENT_DOWN
    BID_IMBALANCE_HIGH    SPREAD_EXPANSION      FVG_FORMATION
    SWEEP_HIGH            LIQUIDITY_REFILL      VOL_BURST
    QUOTE_GAP

## 218.4 THE TOKENIZER IS ITSELF A COMPETITION

Test, on identical data and identical downstream objective:

    quantile discretization
    learned vector quantization / VQ-style codebooks
    BPE-like merging of recurrent market motifs
    learned event embeddings
    continuous transformer baseline (no discretization at all)

The continuous baseline is mandatory. Without it, a tokenizer's win may be a
win over the alternatives it was compared against rather than over not
tokenizing.

## 218.5 THE ACTUAL HYPOTHESIS

# CAN A SELF-SUPERVISED MODEL DISCOVER MICROSTRUCTURE GRAMMAR THAT OUR

# HUMAN-DEFINED SMC STATE MACHINE MISSES?

## 218.6 LEARNED REPRESENTATION VERSUS OBJECTIVE SMC ENGINE IS A COMPETITION

Not a replacement, not an ensemble by default. The two are run against the same
states and scored by the same economics.

If the learned representation INDEPENDENTLY REDISCOVERS a known structure such
as

    SWEEP -> DISPLACEMENT -> RETRACEMENT

that is extremely strong evidence, in both directions at once: it corroborates
the hand-built state machine, and it demonstrates the encoder finds real
structure rather than fitting noise. Record such rediscoveries explicitly. They
are among the most informative results this programme can produce.

If the learned representation finds structure the SMC engine has no language
for, that structure is a first-class alpha candidate and enters the ordinary
validation ladder with its full trial count attached.

================================================================================

# 219. PUBLIC CODE TO CANONICAL ALPHA COMPILER

## 219.1 MANDATE

The competitor and black-box miner already exists. This strengthens it by one
level: public trading CODE is compiled into testable hypotheses automatically.

Applicable sources, where lawfully accessible:

    MQL4 / MQL5     PineScript      Python
    C++             EasyLanguage    NinjaScript      QuantConnect

## 219.2 THE COMPILATION CHAIN

    DOWNLOAD / PARSE
        -> STRIP UI, PLOTTING, ALERTS
            -> EXTRACT ACTUAL TRADING RULES
                -> NORMALIZE INTO CANONICAL IR
                    -> IDENTIFY MECHANISM
                        -> TRANSLATE TO QUANT RESEARCH API
                            -> GENERATE ABLATIONS
                                -> TEST ACROSS MARKETS AND REGIMES
                                    -> STORE DESCENDANTS

## 219.3 ABLATION IS THE POINT, NOT REPLICATION

Given a discovered system of the form

    EMA + LIQUIDITY SWEEP + FVG

the compiler automatically generates and tests:

    original                without EMA             without FVG
    sweep only              sweep + FVG             opposite direction
    different sessions      different instruments   delayed entry
    failed-signal reversal

# THE PUBLIC INTERNET BECOMES AN AUTOMATIC HYPOTHESIS DONOR.

This is categorically different from copying internet strategies. The imported
object is a MECHANISM to be decomposed and falsified, never a system to be run.
A donated hypothesis that survives is ours because it survived our gauntlet,
not because someone published it.

## 219.4 LEGAL WALL, UNCHANGED

Lawfully available information only. No unauthorized access to proprietary
code, no credential theft, no MNPI, no licence violation. The goal is to infer
the ECONOMIC MECHANISM, never to reproduce a proprietary implementation.

## 219.5 MULTIPLICITY

Every compiled descendant carries its parent, its mutation, and its trial
count. An ablation family of twelve is twelve trials, not one result with
eleven robustness checks. Section A.0 applies in full and this section is its
largest single source of trial inflation.

================================================================================

# 220. MULTI-TIER ACCELERATED RESEARCH ENGINE

## 220.1 THE OBJECTIVE IS NOT SPEED

# VALIDATED SURVIVORS PER COMPUTE-HOUR.

Not backtests per second, not GPU utilization, not lines of CUDA. A faster
engine that produces the same survivors is worth nothing; a faster engine that
produces WRONG survivors is worth less than nothing.

## 220.2 TIERS

    TIER A   CHEAP SCREENING
             Highly vectorized CPU/GPU. Millions of candidates. Approximate
             costs, approximate chronology. Purpose: eliminate obvious failure
             cheaply.

    TIER B   ACCURATE RESEARCH
             Detailed transaction costs, correct chronology, portfolio effects.

    TIER C   TRUTH ENGINE
             Event-driven tick replay with actual broker mechanics. The
             reference implementation. Slow by design.

## 220.3 THE FUNNEL

    10,000,000 cheap hypotheses
         100,000 interesting
           5,000 rigorous
             100 serious
                 forward candidates

An expensive simulator is never run on a hypothesis a cheap one can kill.

## 220.4 MANDATORY EQUIVALENCE REGRESSION

# A LIGHTNING-FAST WRONG BACKTESTER WOULD MAKE THIS OPERATION WORSE.

Tier A and Tier B are bound to Tier C by regression tests that assert
bit-identical or explicitly economically-equivalent results on a fixed corpus.
Equivalence tolerances are stated numerically and justified. A tier that drifts
from the truth engine is DISABLED, not tuned, until it agrees again.

A cheap tier is permitted to be less precise. It is never permitted to be
differently ordered: a hypothesis Tier C ranks above another must not be
eliminated by Tier A.

## 220.5 WHEN TO ACCELERATE

Profile first. Acceleration is justified by MEASURED wall-time share, not by
the availability of a technology. If backtesting is not a large fraction of
research wall time, the bottleneck is elsewhere and CUDA is a distraction from
it.

Escalate through Numba, C++, Rust, GPU, CUDA on benchmark evidence, in that
order of increasing engineering cost, stopping at the first tier that removes
the measured bottleneck.

================================================================================

# 221. LOW-LATENCY STACK AS ECONOMIC CHALLENGER

## 221.1 MT5 IS NOT A RAW EXCHANGE PROTOCOL

An order does not travel from this desk's NIC to a matching engine. It traverses

    BROKER GATEWAY -> MT5 SERVER -> BROKER RISK CONTROLS
                   -> LP ROUTING -> INTERNET / DC PATH

Kernel-bypass networking cannot remove layers that are not in the kernel.
Claims that eBPF or DPDK let this desk "blast an MT5 packet from the NIC" are
false and must not enter a design document.

## 221.2 THE LADDER

    Python
      -> Rust / C++ service
        -> optimized socket and networking
          -> eBPF / kernel tuning
            -> DPDK
              -> specialized hardware

Progressive. Each rung is entered only when the rung below is measured and
exhausted.

## 221.3 THE ONLY ADMISSION CRITERION

    delta E[log W] from the latency improvement
        >
    engineering cost + infrastructure cost + operational risk

Estimated from the LATENCY VALUE CURVE (section 63), by deliberately replaying
the strategy at 0ms, 10ms, 50ms, 100ms, 250ms, 1s and 5s and measuring
NET_EDGE(latency).

For M5/M15 gold strategies, 300 microseconds is economically irrelevant and
buying it is a pure loss. For genuine news or leader-lag micro-alpha it can
dominate every other consideration. THE CURVE DECIDES, PER SLEEVE, NOT A
GENERAL PREFERENCE FOR SPEED.

## 221.4 STATUS

eBPF and DPDK are hereby added to the latency challenger inventory.

# THEY ARE NOT SCHEDULED FOR CONSTRUCTION.

================================================================================

# 222. LIQUIDITY SURVIVAL AND CANCEL-REFILL MICROSTRUCTURE MODEL

## 222.1 BEYOND "BIG WALL EQUALS SUPPORT"

Existing order-book work tracks imbalance, refill and cancellation. This adds a
survival model over resting liquidity clusters.

Per cluster, measure:

    AGE                   DISTANCE_FROM_MID     SIZE
    SIZE_CHANGE           CANCEL_HAZARD         EXECUTION_HAZARD
    REFILL_RATE           REAPPEARANCE_RATE     MIGRATION
    PRICE_FOLLOWING

## 222.2 THE ESTIMATES

    P(liquidity survives dt)

    P(level breaks | liquidity decay state)

## 222.3 THE STATE WORTH FINDING

    REAL ABSORPTION       size repeatedly replenishes after executions
    FRAGILE DISPLAY       size evaporates as price approaches

These are opposite information despite looking identical in a depth snapshot.
Distinguishing them is the point of the model.

## 222.4 INTENT IS NOT OBSERVABLE FROM THE BOOK

# DO NOT LABEL EVAPORATING LIQUIDITY "SPOOFING".

Cancellation is lawful, ubiquitous, and has many benign causes: hedge
adjustment, inventory change, quote refresh, risk limit, stale-quote pull. The
book shows WHAT HAPPENED, never WHY. Trade the statistical market-state
implication; never assert manipulative intent, and never build a signal whose
economic story requires attributing intent to an identifiable participant.

================================================================================

# 223. REPRESENTATION TOURNAMENT AND ALPHA CANONICALIZATION CACHE

## 223.1 NO REPRESENTATION IS PRIVILEGED

Neither handcrafted features nor deep learning is assumed to win. For every
important dataset, compete:

    RAW SEQUENCE          HANDCRAFTED FEATURES     SMC STATE MACHINE
    TOKENIZED SEQUENCE    WAVELETS                 LATENT AUTOENCODER
    TREE FEATURES

Scored on:

    OOS INFORMATION COEFFICIENT      NET STRATEGY CONTRIBUTION
    REGIME STABILITY                 COMPUTE COST
    EXPLAINABILITY                   FORWARD SURVIVAL

Different representations may win in different regimes, and that outcome is
more valuable than a single champion: it is a conditional model-selection edge
in its own right (section 47). Do not force a global winner.

## 223.2 CANONICALIZATION: THE SAME IDEA MUST NOT BE COUNTED TWICE

At industrial mining volume, equivalent formulas WILL be rediscovered
repeatedly.

    (close - SMA20) / ATR20

and any algebraically equivalent expression are ONE hypothesis, not two.

Fingerprint every feature and strategy on:

    AST                        NORMALIZED FORMULA
    INPUT DATA LINEAGE         TIME HORIZON
    TRANSFORMATION GRAPH

Classify:

    EXACT_DUPLICATE       NEAR_DUPLICATE       FUNCTIONAL_CLONE

## 223.3 WHY THIS IS A STATISTICAL CONTROL AND NOT A CACHE

Compute saving is the smaller benefit. The larger one:

# A CLONE-INFLATED TRIAL COUNT CORRUPTS THE MULTIPLICITY CORRECTION IN BOTH

# DIRECTIONS, AND THE DESK IS EXPOSED TO THIS RIGHT NOW.

The deflated Sharpe threshold scales with E[max of N trials], which is monotone
increasing in N. That formula assumes INDEPENDENT trials. A sweep whose raw
count is inflated by functional clones is being penalized against a threshold
computed for far more independent searches than it actually performed, and
genuine edges are killed by arithmetic.

This is live, not hypothetical. The current nine MT5 candidates fail the
gauntlet on deflated Sharpe alone, against n_trials = 2,464, while passing PBO
at 0.034 and walk-forward stability at 1.0. If a material fraction of those
2,464 cells are functional clones of one another, the effective independent
trial count is lower, the threshold is too harsh, and the verdict on those nine
changes.

# COMPUTING THE EFFECTIVE INDEPENDENT TRIAL COUNT IS THEREFORE A VALIDATION

# TASK, NOT AN OPTIMIZATION, AND IT RANKS ABOVE THE OTHER FIVE ADDITIONS.

Deduplication must never be used to make a threshold easier by construction.
The effective count is computed by a stated, pre-registered method, reported
alongside the raw count, and both appear in every result. Lowering N is a claim
that requires evidence exactly as much as raising a Sharpe does.

## 223.4 DIVERSITY IS PRESERVED DELIBERATELY, NOT HOPED FOR

A naive evolutionary search converges to ten thousand variations of one idea —
the same pathology as clone inflation, arriving by a different route, and it is
why survivor COUNT is a misleading measure of a factory's output.

Maintain explicit niches:

    trend        mean reversion    event          microstructure
    options      RV                cross-sectional session
    carry        forced flow       SMC            volatility

Apply quality-diversity selection (MAP-Elites style, novelty-preserving) rather
than fitness ranking alone. Score offspring on

    EDGE      ROBUSTNESS      NOVELTY
    INDEPENDENCE     CAPACITY     FORWARD PLAUSIBILITY

# NOT ON BACKTEST SHARPE.

The operation's objective is INDEPENDENT survivors. A niche that is empty is a
research instruction; a niche that is crowded is a warning that the factory is
producing clones and calling them discoveries.

================================================================================

# END APPENDIX A.

The open question is no longer which technology is missing.

# IT IS WHICH RESEARCH PATH PRODUCES THE MOST GENUINELY INDEPENDENT FORWARD

# SURVIVORS PER UNIT OF TIME AND COMPUTE.

That is where the next major gain comes from, and every section above is
justified only insofar as it moves that ratio.

================================================================================

# 224. CRYPTO TAPE RETIRED. THE OBLIGATION TRANSFERS TO MT5.

## 224.1 WHAT IS RETIRED, AND WHY THIS IS NOT A LAPSE

The three crypto L2 recorders -- quant-recorder-fut, quant-recorder-spot,
quant-recorder-bybit -- are RETIRED as of 2026-08-17.

Their unit files carried a header stating that leaving them off is a breach of
P26, on the grounds that an unrecorded second is permanently unbuyable at any
price. That reasoning was correct and it still is. It simply no longer applies
to Binance and Bybit, because:

    Irish retail rules make the crypto leg SPOT ONLY
    the desk trades MT5
    the tape fed nothing that trades
    it had reached 19GB on a 37GB disk, with root at 87%

# A TAPE NOBODY WILL TRADE ON IS NOT A MOAT. IT IS A BILL.

## 224.2 THE OBLIGATION IS NOT CANCELLED. IT MOVES.

P26 now binds `mt5desk.tape` instead. Every MT5 tick this desk can see is
recorded, for the identical reason: pre-recorder tick data does not exist free
at any broker, the archive only grows, and downtime is the one cost money
cannot recover later.

    RETIRED   data/moat/{fut,spot,perp,bybit}     Binance + Bybit L2
    KEPT      data/moat/execution_tape            this desk's own fills
    ACTIVE    data/tape/ticks                     MT5 tick tape (section 23)

## 224.3 DEPTH IS PROBED, NEVER ASSUMED

An MT5 CFD broker is not an exchange. `market_book_get` usually returns nothing
or a single synthetic level echoing the spread already carried by the tick.

`mt5desk.tape.probe_depth()` therefore establishes by evidence whether real
depth exists, per symbol, and records the verdict.

# WHERE THERE IS NO REAL DEPTH, SECTION 222 IS NOT BUILDABLE ON THIS VENUE.

The liquidity survival engine -- cancel and execution hazards, refill rate,
absorption versus fragile display -- requires more than one level per side.
Building it on a book synthesised from bid/ask would produce a precise model
OF THE SYNTHESIS, and every state it reported would be an artefact. Section 222
waits for a venue that has depth, or it does not get built.

The tick tape is unaffected and supports section 23 in full: quote-change
imbalance, tick direction, micro momentum, spread expansion and contraction,
update intensity, burstiness, gap frequency.

## 224.4 NO COMPUTE, NO RESEARCH EFFORT, NO LLM BUDGET ON CRYPTO VENUES

Binance, Bybit and every other crypto venue are out of scope for this desk:
no recording, no hunting, no gauntlet runs, no data spend, no agent hours.

Crypto INSTRUMENTS remain in scope only where MT5 quotes them and they clear
the ordinary promotion protocol like any other symbol. The venue is retired,
not the asset class.

Reversal requires a stated change in the legal or venue position, recorded
here. It is not reversed by a passing idea that the old tape might be useful.
