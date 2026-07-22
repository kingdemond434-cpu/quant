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

## AlphaZeroBeta: Deep Reinforcement Learning for Market-Neutral Portfolios
- 2026-07-20 · http://arxiv.org/abs/2607.18001v1
- Market-neutral portfolios aim to generate consistent returns while offsetting systematic market risk. Traditional approaches based on factor models or convex optimization often underperform during market regime shifts or when structural assumptions break down. We propose AlphaZeroBeta, a deep reinforcement learning framework designed to deliver benchmark-relative alpha (excess returns) with near-zero beta (market neutrality). AlphaZeroBeta combines a composite reward function that balances risk-adjusted excess return, benchmark correlation, and transaction costs with a CNN-GRU policy trained e

## Optimal Market Making in Prediction Markets
- 2026-07-20 · http://arxiv.org/abs/2607.17991v1
- Prediction markets are attracting growing attention as trading volumes rise and their practical relevance increases. To ensure efficient price discovery, liquidity provision becomes ever more important. Due to the binary settlement structure in prediction markets, optimal market making leads to an optimization problem that is fundamentally different from the ones studied in classical settings. In this paper, we develop a stochastic control framework for prediction markets in which the market price is modeled as a conditional probability of the outcome that is generated by a transformed latent 

## Uniform-Loss Automated Market Making for Prediction Markets
- 2026-07-19 · http://arxiv.org/abs/2607.17428v1
- Automated market makers (AMMs) for prediction markets descend from market scoring rules, where a mechanism operator subsidizes a market to aggregate beliefs about uncertain events. The existing literature has focused on bounding the total worst-case loss to the subsidizer, but has not addressed how that loss is distributed across price states or over time. We use the framework of loss-versus-rebalancing (LVR) to study this distribution and introduce \textit{uniform AMMs}, defined by the property that instantaneous LVR is proportional to pool value and independent of the current token price. In

## Herding and Liquidity in Order-Book Markets. II. Fundamental Anchoring and the Resilience of Liquidity
- 2026-07-18 · http://arxiv.org/abs/2607.16970v1
- An order-book market whose liquidity provision is anchored to a fundamental value carries a restoring force: the price mean-reverts to value and the book refills after a shock. We show this restoring force is a robust intrinsic stabiliser and identify it causally-dialling the anchor down removes the mean-reversion, and a leverage-driven fire-sale then self-sustains. Separately, we ask whether a stressed market transmits its liquidity stress to a coupled calmer one, and find that it cannot: across six transmission channels of increasing strength-cross-market herding, arbitrage flow, and market-

## Proof-of-Stake Dynamics: The Elusive Price Anchor and Endogenous Volatility Harvesting
- 2026-07-18 · http://arxiv.org/abs/2607.16622v1
- In this paper, we develop an open-economy macroeconomic model of a Proof-of-Stake network to analyze nominal token-price dynamics and the systemic effects of speculative capital. We first consider a network populated solely by active utility users, who finance network activity through a steady exogenous inflow of fiat currency. We prove the existence of a unique, globally asymptotically stable steady-state equilibrium with a well-defined nominal token price and derive a closed-form expression for the network's relaxation time. Calibrating the model using parameters representative of the curren

## Portfolio Optimization under Heavy Tails and Asymmetric Volatility: Evidence from Taiwan-Exposed ETFs
- 2026-07-17 · http://arxiv.org/abs/2607.16450v1
- Taiwan's central role in global semiconductor manufacturing exposes Taiwan-related ETFs to technology concentration, geopolitical uncertainty, and supply-chain disruptions, resulting in return distributions characterized by heavy tails, volatility clustering, and asymmetric responses to negative shocks. This paper analyzes thirty U.S.-listed ETFs with Taiwan exposure from February 2015 to February 2025 using tail-risk diagnostics, asymmetric volatility modeling, and portfolio optimization under mean--variance and conditional value-at-risk (CVaR) criteria. Hill tail-index estimates document hea

## A Novel Hybrid Quantum Reservoir Computing (nHQRC) for Phase Transition Detection in Non-Equilibrium Dynamical Systems
- 2026-07-09 · http://arxiv.org/abs/2607.16281v1
- The analysis of highly non-linear stochastic data within non-equilibrium dynamical systems requires computational frameworks capable of detecting latent phase transitions before systemic structural breakdowns occur. Traditional Variational Quantum Algorithms (VQAs) are frequently bottlenecked by vanishing gradients, the barren plateau problem, and prohibitive training overheads. In this paper, we propose a novel Hybrid Quantum Reservoir Computing (nHQRC) framework, which bypasses these limitations by employing a frozen, disordered Transverse-Field Ising Model (TFIM) to project time-dependent s

## Observable Matrix Dynamics of Stocks
- 2026-07-21 · http://arxiv.org/abs/2607.19005v1
- The Observable Matrix Dynamics (OMD) approach monitors the time development of complex non-linear systems through the trajectory of a fixed-size distance matrix and its spectrum. We apply it to the S\&P 500 cross section over three crisis decades, the 2001 dot-com bust, the 2007--2008 financial crisis, and the 2020 Covid crash, with three fixed-size observables on a fixed universe. The arccos distance matrix of the rolling return correlations reads the correlation geometry: its effective dimension collapses at the 2008 and 2020 crises, while the 2001 bust is a dispersed unwind. Read against ma

## Mixing-Law Uncertainty in Multivariate Normal Mean-Variance Mixtures: Semi-parametric Estimation and Robust Cumulative-Prospect Decisions
- 2026-07-21 · http://arxiv.org/abs/2607.18813v1
- The distribution of a normal mean-variance mixture depends on the law of its positive mixing variable. We compare six parametric mixing laws with a grid nonparametric maximum likelihood estimator under the same determinant identification constraint. The mixing mean $m=\E(Z)$ is estimated and is not fixed at one. A paired block bootstrap is used to compare multivariate holdout log scores. The models that cannot be distinguished from the model with the largest score define a finite ambiguity set. We then consider a cumulative prospect problem on a common portfolio direction. For each model in th
