# Research feed inbox (auto-fetched; CRO processes then DELETES entries)

For each item: economic intuition -> orthogonality vs the alpha map -> EV-score (alpha_economics) -> graveyard-reject OR distill into docs/research/<topic>.md with [[wikilinks]] + research queue.

<!-- 2026-07-10: batch of 25 q-fin papers (2026-07-02..08) triaged and cleared. None cleared the EV
gate for a solo crypto carry/derivative desk at the current binding constraint (calendar-time data
accumulation): the set was dominated by equity factor-model diagnostics (BBP transition, spectral
variance-ratio, characteristic-axis, absorption-ratio), option-pricing theory (entropic jump-diffusion,
local-vol projection), microstructure THEORY (square-root law necessity, Gabor-Epps, limit-order
equilibria), and off-topic (wealth-tax Fokker-Planck, QQQ/DIA rotation, US news sentiment). Two noted
for possible later value but NOT queued now: "Look-Ahead-Freedom as Temporal Non-Interference"
(2607.04958 -- formal backtest look-ahead property; revisit if we build a new backtester) and
"tsbootstrap conformal PI" (2607.06690 -- dependence-aware uncertainty bands; potential upgrade to
forward-clock significance testing). Solana pump.fun / DEX-filter papers (2607.02823, 2607.02830) are
venue-specific memecoin microstructure -- no orthogonal carry/derivative signal, no free-data edge. -->

<!-- 2026-07-17: batch of 20 q-fin papers (2607.05091..2607.15195, dated 07-06..07-16) triaged and
cleared. 17 REJECTED as off-topic-domain or pure theory with no free-data translation for this desk:
generic portfolio-optimization/index-tracking methodology (evolutionary algorithms, MILP, RL), equity
factor-model/10-K-sentiment/LoRA-equity-forecasting papers (wrong asset class), AMM protocol-fee
economics and prediction-market volatility (off our strategy surface), Kyle-model/liquidity-herding/
quantum-TDA THEORY papers (no free-data mechanism), credit-risk divergence-measure monitoring and
correlation-network-recovery methodology (generic statistical tooling, not a testable edge), EU-
election thermodynamics (off-topic), LLM-RAG fundamental-analysis system (equity, off-topic), and a
crypto-exchange complexity-measure anomaly-detection paper (surveillance-flavored, no return-
predictive mechanism identified). 1 EV-SCORED AND REJECTED: quarter_hour_periodicity_crypto_futures
(2607.09426, ev 0.0006, crowded_known -- published pattern + the desk is D1-only today, no intraday
collector; see research_agenda.json do_not_repeat). 1 DISTILLED AS A REFERENCE (not a new hypothesis):
2607.09230 "When Does Order Flow Matter? State-Dependent L2 Liquidity-State Transitions in Crypto
Futures" -- folded into engineering_backlog.json's execution_tca_fill_log (GAP#4) as a design
reference for when that item is built (liquidity STATE, not just level, predicts adverse selection). -->

<!-- 2026-08-06 (R0269): THE BACKLOG DRAIN. All 27 remaining entries (2607.15057 .. 2607.27188,
dated 07-09..07-29, oldest 28.0 days) triaged and cleared. This is the batch the row was raised
about: the inbox is specified as a queue processed and CLEARED every cycle, and it had not been
drained since 2026-08-01 while reporting nothing at all.

2 GRAVEYARDED -- both are PRE-PAID NEGATIVES, the vein this desk most wants and most often skips:
  * 2607.20093 "Retail Trader's Ruin" -> lit_retail_signal_families. Five retail signal families
    (trend, oscillator, candlestick, volume, calendar) against three PRE-DECLARED gates ANDed:
    multiplicity-corrected edge, cost viability, finite-bankroll survival. The desk's own DSR /
    execution-physics / L1.23 triple, arrived at independently by an outside team. The reusable
    half is the CONJUNCTION -- each family clears one or two gates and none clears all three,
    which is exactly how a signal survives a blog post and fails a desk.
  * 2607.19453 "Predictive Extrema, Unprofitable Policies" -> lit_candle_ml_timing_crypto. Candle
    ML on Binance SPOT: the models predict and the policies still lose after costs. The desk's
    oldest recurring trap (positive IC != tradeable P&L) replicated by outsiders on the desk's own
    venue and bar type. Held as a CORROBORATING prior, not decisive: fixed-seed scripted runs with
    AI-assisted evidence integrity is weaker provenance than a peer-reviewed replication.

1 DELETED AS AN ALREADY-JUDGED RE-DELIVERY:
  * 2607.09426 "The Quarter-Hour Effect" -- EV-rejected 2026-07-17 (ev 0.0006, crowded_known) and
    already in do_not_repeat. It came back because the collector keyed its seen-archive on the
    VERSIONED arXiv URL, so a v2 read as a new paper. FIXED THIS RUN in collect_research_feed.py:
    ids are version-stripped, and the collector now screens against do_not_repeat AND the
    graveyard before writing an entry. Verified: 2607.09426 is now blocked.

2 DUPLICATE PAIRS, same cause, same fix (2607.19005 v1+v2 "Observable Matrix Dynamics of Stocks";
2607.17428 v1+v2 "Uniform-Loss AMM for Prediction Markets").

22 REJECTED WITH REASONS, grouped by why:
  * WRONG ASSET CLASS (7): 2607.18001 equity DRL market-neutral; 2607.16450 Taiwan-exposed ETF
    tail risk; 2607.19005 S&P correlation geometry; 2607.24410 equity-fundamental covariance;
    2607.27461 three-matrices S&P; 2607.27188 NIFTY option RND recovery; 2607.23068 NN global-min-
    variance (equity portfolio -- and desk sizing was answered by R0266's study, which measured
    the boundary shrink at <=10% and concluded DO NOT WIRE).
  * THEORY WITHOUT A FREE-DATA MECHANISM (6): 2607.15057 multi-insider Kyle existence proofs;
    2607.16970 herding/liquidity ABM; 2607.16622 PoS price anchor macro model; 2607.18813 mixing-
    law mean-variance mixtures; 2607.24114 expectation-constrained optimal control; 2607.25189
    long-memory GARCH. Each is a model of a market, not a measurement of one.
  * OFF THE STRATEGY SURFACE (5): 2607.17991 + 2607.17428 prediction-market MM/AMM design (and
    see lit_prediction_market_microstructure_vs_book, graveyarded this same run -- the desk's
    position on prediction markets is now recorded); 2607.26405-class multi-currency AMM;
    2607.20762 DEX routing shortfall (2.98M swaps, 2.02bps -- real and empirical, but the desk
    trades CEX perps and has no DEX order path); 2607.21170 TDA + FinBERT sentiment (needs
    annotation infra, sentiment is off surface).
  * METHOD-CURIOSITY, NO PATH TO A POSITION (4): 2607.16281 quantum reservoir phase detection;
    2607.24065 variational quantum CRBM; 2607.25459 latent-state interpretability under
    stochastic vol; 2607.27099 "Rainfall is rough" (Hawkes rainfall -- off-domain entirely).
  * ALREADY PRICED (2): 2607.19497 "Science and Practice of Trend-Following" -- the desk runs
    trend_30d/trend_regime and already carries the measured crypto TSMOM haircut (-58% to -65% vs
    published, in the graveyard's standing McLean-Pontiff prior), so a taxonomy adds no decision;
    2607.21826 LPPL/JLS crypto bubble detection -- directional timing on a crowded published
    signal, and the desk's own measured lesson is that volatility is predictable while direction
    is not.

<!-- 2026-08-11 (owed-work batch3): backlog drain, 52 live entries (2026-07-09..08-10, oldest
33.6d) triaged and cleared. 2 were RE-FETCHED DUPLICATES of papers graveyarded in the 2026-08-06
drain (Retail Trader's Ruin -> lit_retail_signal_families; Predictive Extrema -> 
lit_candle_ml_timing_crypto) plus one internal duplicate (Observable Matrix Dynamics x2) -- the
collector does not dedupe against triage records, only against live entries.

43 REJECTED at the EV gate for a solo crypto carry/derivative D1 desk, by class: wrong asset
(Taiwan ETFs, equity factor/covariance/LSTM/10-K structure, FX predictability, life insurance,
lending fairness, given-name thermodynamics); pure theory with no free-data translation (LOB
herding II, PoS price anchor, diffusive-price paradox, expectation-constraint control, proper-score
filters, rough Hawkes-Heston, ergodicity boundary risk-aversion -- the desk's log objective already
internalizes the last); methodology exotica (quantum reservoir, variational quantum Boltzmann, TDA
+news, multifractal allocation, Wasserstein-robust, Markov GoF, frozen-foundation-model
correction); off-surface venues (AMM routing/prediction markets/Axient x2/OTC MM/options intraday
manipulation -- no options or DEX book data on desk); crowded-known (crypto bubble diagnostics,
trend-following survey -- every desk directional trend family is already graveyarded); mechanism
requires price limits crypto venues lack (retained hidden excess); duplicate-of-owned (lower-
spectrum correlation sync -- cohort_independence already measures N_eff with the demeaning floor).

6 DISTILLED as mechanism-prior references into research_memory (method rows, 2026-08-11):
  * Conformal Kelly (2608.xx) -- conformal intervals as the fractional-Kelly scale: a
    distribution-free gamma for the desk's Robust-Kelly shrink; ALSO ledgered as an actionable
    sizing candidate (see recommendation ledger, raised 2026-08-11).
  * Robustness or Crowding: capacity experimental design -- designed experiments for capacity
    measurement; prior for the L1.45 excitation program and capacity_policy.
  * Liquidation-cascade subcritical branching -- criticality measure on the INGESTED liquidation
    stream; prior for the BIS carry<->liquidation family (R0193 screen construction).
  * Stablecoin transaction scaling laws (USDT/USDC) -- transaction-leg empirics for the
    stablecoin_flows family beside the new supply-leg variables (2026-08-11).
  * Cross-venue agreement is not price discovery -- outside corroboration of the desk's own
    L1.46 aliasing lesson (R0117 refutation); caution prior for venue-divergence shadows.
  * Optimal trading of microstructure mean reversion -- exploitation-rule reference for moat
    L2 screen survivors when one promotes.

1 DATASET LEAD routed to the dataaxis organ rather than carded unscreened (screen-on-discovery
discipline -- a card without its same-run screen would re-suspend mining): Public Trader Identity
/ adverse selection -- public-identity perp venues (Hyperliquid-style wallet-visible flow) are a
free orthogonal flow axis; the dataaxis dig should card AND screen it in one run. Recorded as a
research_memory dataset row (pending).
-->
