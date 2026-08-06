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

THE DUTY THAT WAS SILENTLY NOT RUNNING NOW HAS AN INSTRUMENT: max_audit.check_feed_inbox_backlog
counts live entries and the age of the oldest, and fires past 20 open / 3 days. Zero entries is
the healthy state and reads clean, so draining is what the fence rewards. Separately, this doc was
nominally inside the section-33 scanned set the whole time and contributed exactly ZERO parsed
items -- listing a denominator is not counting one (L1.57). It is now in _DIG_DOCS_EXCLUDED with
its real lifecycle stated, and check_mine_scope_vacuous fails if any doc in scope ever again
carries content the parser cannot see. -->
