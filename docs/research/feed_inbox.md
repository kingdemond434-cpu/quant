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

## Existence and convergence of discrete-time Kyle models with multiple insiders
- 2026-07-16 · http://arxiv.org/abs/2607.15057v2
- Foster and Viswanathan (1996) extend the discrete-time setting of Kyle (1985) to multiple informed traders who have partial information about the stock's terminal dividend. We resolve two long-standing open problems in this literature. First, we prove that an equilibrium exists in the setting of Foster and Viswanathan (1996). Second, as the number of trading times goes to infinity, we prove that the discrete-time equilibrium converges to the continuous-time equilibrium already proven to exist in Back, Cao, and Willard (2000).

## The Quarter-Hour Effect: Periodic Algorithmic Trading and Return Predictability in Cryptocurrency Futures
- 2026-07-10 · http://arxiv.org/abs/2607.09426v2
- Cryptocurrency markets exhibit periodic bursts in volatility and volume at one-minute, five-minute, and quarter-hour marks. Using trade data for six Binance perpetual contracts, we link these bursts to algorithmic participation: trade-size roundness declines sharply during them. The Autocorrelation Map, a clock-phase-resolved display, reveals serial dependence in order flow and returns at quarter-hour openings that conventional measures obscure. Opening returns are predictable out of sample, while opening order imbalance predicts returns over four to twelve hours, with much weaker effects at f
