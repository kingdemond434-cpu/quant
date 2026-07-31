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

## Retail Trader's Ruin: An Anatomy of Popular Signal Failure
- 2026-07-22 · http://arxiv.org/abs/2607.20093v1
- We test whether five widely promoted retail signal families - trend, oscillator, candlestick, volume, and calendar rules - deliver a positive, economically meaningful, net-of-cost, and survivable edge. Practical viability is the conjunction of three predeclared gates: statistical edge after multiplicity correction, economic viability after trading costs, and finite-bankroll survival under leverage. Exposure-matched benchmarks, stationary-bootstrap confidence intervals, hierarchical Benjamini-Yekutieli control, one-sided claim-exclusion tests, and equivalence tests distinguish positive evidence

## The Science and Practice of Trend-Following Systems
- 2026-07-21 · http://arxiv.org/abs/2607.19497v1
- We present a unified approach to designing trend-following (TF) systems and classify them into European, American, and Time Series Momentum categories. For European TF systems, we derive an exact relationship between profit-and-loss, autocorrelation, and drift in volatility-normalized returns. We analyze the expected return under fractional ARFIMA processes and show that TF systems are profitable when the long-term autocorrelation is positive, even under short-term mean reversion. In the frequency domain, the expected return is represented as a Poisson-kernel reading of the analytical or empir

## Predictive Extrema, Unprofitable Policies: An AI-Assisted Audit of Candle-Based Binance Spot Timing Models
- 2026-07-21 · http://arxiv.org/abs/2607.19453v1
- We audit whether candle-based machine-learning models can turn predictions of cryptocurrency extrema or short-horizon outcomes into positive Binance Spot paper policies after assumed costs. Numerical results come from scripted fixed-seed model runs and deterministic simulators; human-supervised AI agents supported the July 20 evidence-integrity revision through literature retrieval, separately tasked critique, artifact reconciliation, documentation, and source packaging, not trading decisions. The strongest later-period evidence, conditional on extensive predecessor search, is negative: an unc

## Observable Matrix Dynamics of Stocks
- 2026-07-21 · http://arxiv.org/abs/2607.19005v2
- The Observable Matrix Dynamics (OMD) approach monitors the time development of complex non-linear systems through the trajectory of a fixed-size distance matrix and its spectrum. We apply it to the S\&P 500 cross section over three crisis decades, the 2001 dot-com bust, the 2007--2008 financial crisis, and the 2020 Covid crash, with three fixed-size observables on a fixed universe. The arccos distance matrix of the rolling return correlations reads the correlation geometry: its effective dimension collapses at the 2008 and 2020 crises, while the 2001 bust is a dispersed unwind. Read against ma

## Portfolio Optimization under Dynamic Rebalancing via Topological Data Analysis and News Sentiments
- 2026-07-23 · http://arxiv.org/abs/2607.21170v1
- Understanding similarity among financial assets is essential for effective portfolio diversification. This paper proposes a novel sentiment-adjusted portfolio optimization framework that integrates Topological Data Analysis (TDA) with technical indicators and FinBERT-based sentiment scores extracted from financial news. A TDA-based distance measure is employed within an agglomerative clustering framework to identify topologically dissimilar assets for portfolio construction. By incorporating sentiment information, the framework captures rapid changes in market perception and investor behavior 

## Quantifying Sub-Optimality in Routing for Automated Market Makers
- 2026-07-22 · http://arxiv.org/abs/2607.20762v1
- We provide a large-scale empirical audit of DEX routing using 2.98 million WETH-USDC swaps on Ethereum. Comparing realized routes with optimized benchmarks, we measure an average shortfall of 2.02 bps per trade or \$24 million. To attribute losses, we introduce three reproducible optimal benchmarks: a Support-Constrained Optimum (SCO) that evaluates split quality conditional on the pools actually used; a Full-Venue Optimum (FVO) that considers all available pools to quantify the value of broader pool access; and a Gas-Aware FVO (G-FVO) that augments FVO with gas costs to capture the trade-off 

## Uniform-Loss Automated Market Making for Prediction Markets
- 2026-07-19 · http://arxiv.org/abs/2607.17428v2
- Automated market makers (AMMs) for prediction markets descend from market scoring rules, where a mechanism operator subsidizes a market to aggregate beliefs about uncertain events. The existing literature has focused on bounding the total worst-case loss to the subsidizer, but has not addressed how that loss is distributed across price states or over time. We use the framework of loss-versus-rebalancing (LVR) to study this distribution and introduce \textit{uniform AMMs}, defined by the property that instantaneous LVR is proportional to pool value and independent of the current token price. In

## Are cryptocurrencies real financial bubbles? Evidence from quantitative analyses
- 2026-07-23 · http://arxiv.org/abs/2607.21826v1
- The growth of peer-to-peer exchanges and the blockchain technology has led to a proliferation of cryptocurrencies and to a massive increase in the number of investors who actually negotiate digital money. Cryptocurrencies trade at prices mainly driven by investor sentiment, becoming a potential source of financial bubbles and instabilities. In this work, we apply quantitative models to the study of Bitcoin and Ether, two of the most famous cryptocurrencies. Our bubble detection methodology combines the Log Periodic Power Law (LPPL) model, originally created by Johansen, Ledoit and Sornette (JL

## The Fundamental Structure of Risk: From Characteristics to Covariance
- 2026-07-27 · http://arxiv.org/abs/2607.24410v1
- Estimating the covariance structure of financial assets typically relies on his- torical returns, making risk models dependent on noisy and asset-specific time se- ries. We propose the Characteristic-Driven Dynamic Factor Model (CD-DFM), a non-linear latent factor model that instead constructs a representation of the asset cross-section directly from observable firm characteristics, primarily company funda- mentals. The learned latent space jointly determines interpretable factor exposures and a forward covariance estimator, and is trained end to end on an objective that combines a Stein covar

## Optimal Control with Expectation Constraint in a Smooth Boundary Case
- 2026-07-27 · http://arxiv.org/abs/2607.24114v1
- As in Bouchard et al. (2010) and Bouchard and Nutz (2014), we study a utility maximization problem with expectation constraint. We first consider a uniformly elliptic case in which the endogenous state boundary associated with the constraint in expectation is proved to be smooth. This allows one to derive a proper Dirichlet condition for the value function of the optimal control problem on this boundary. We then propose a new truncation argument in the martingale representation of the expectation constraint. This leads to an approximating sequence of auxiliary systems of PDEs for which compari

## Variational Quantum Conditional Boltzmann Machines for Time-Series Forecasting: Architectures, Symmetric Hyperparameter Evaluation, and a Nonlinear Benchmark
- 2026-07-27 · http://arxiv.org/abs/2607.24065v1
- In this study, we developed and evaluated four conditional energy-based forecasting architectures: a classical Gaussian-Bernoulli CRBM, a hybrid quantum-classical QCRBM, a full-register QQRBM, and a lag-feature QFeatureQRBM with complete derivations of their conditional distributions, Contrastive-Divergence gradients, and hybrid training, bridging the energy-based formulation and the implementation-level quantum computation. Unlike prior comparisons, our evaluation enforces symmetric hyperparameter optimisation: classical and quantum-specific hyperparameters receive an equally thorough grid se

## Neural Network-Driven Volatility Drag Mitigation under Aggressive Leverage
- 2026-07-25 · http://arxiv.org/abs/2607.23068v1
- This paper introduces a compact reformulation of a modular end-to-end neural network for global minimum-variance portfolio optimization that decouples model complexity from both look-back window length and universe size. A five-parameter hyperbolic weighted moving average combined with a saturating exponential replaces the original 2,400-parameter lag-transformation layer, and a bidirectional gated-recurrent-unit eigencleaning module together with a streamlined marginal-volatility network reduce total learnable parameters from 39,586 to just 2,175. In out-of-sample tests against state-of-the-a

## Emergent Latent-State Computation under Stochastic Volatility
- 2026-07-28 · http://arxiv.org/abs/2607.25459v1
- Mechanistic interpretability has largely focused on language models and deterministic toy tasks. Much less is known about how sequence models internally represent latent stochastic dynamics under noisy, partially observed observations. We study this question in a controlled multivariate stochastic volatility setting, where models observe only returns while the ground-truth latent volatility state is known to the researcher. This setting provides a useful benchmark for mechanistic interpretability under partial observability: the latent state is hidden from the model but directly available for 

## Long-memory GARCH via a two-dimensional Markov chain
- 2026-07-28 · http://arxiv.org/abs/2607.25189v1
- This paper proposes a GARCH-type volatility model in which level-and-slope updates of a latent power-law kernel generate state-dependent decay of past shocks within a two-dimensional Markov state. We derive a joint Foster--Lyapunov condition and establish positive Harris recurrence and uniqueness of the invariant distribution. Simulations show substantial low-frequency persistence in log-squared innovations, especially near the diagnostic stability boundary. Empirically, the model captures a substantial portion of observed volatility persistence and delivers competitive out-of-sample forecast 

## Inverse Learning of Latent Risk-Neutral Densities from Irregular Option Quotes
- 2026-07-29 · http://arxiv.org/abs/2607.27188v1
- Accurate option prices do not imply accurate recovery of the latent risk-neutral density. We study this distinction with two complementary benchmarks. A controlled benchmark exposes simulator-truth densities for latent evaluation, while a chronological NIFTY benchmark tests only held-out market prices. A two-component lognormal mixture has the lowest aggregate price, $L^1$, Wasserstein, and fixed-tail errors on the synthetic benchmark. Learned operators retain narrower strengths: DeepONet reduces 1% quantile and variance error by 39.0% and 34.6% relative to the mixture, and a quote transformer

## Rainfall is rough
- 2026-07-29 · http://arxiv.org/abs/2607.27099v1
- We propose a new approach to model rainfall by combining heterogeneous data sources at different time scales. Continuous arrivals of rain cells are incorporated into a Hawkes process formalism that encompasses the classical Bartlett-Lewis and Neyman-Scott models, thereby providing a more flexible representation of clustering. Analysis of high frequency rainfall data (at the minute scale over several years) indicates that critical Hawkes processes with heavy-tailed power-law kernels yield a superior fit relative to classical models and alternative kernel specifications. Scaling arguments inspir

## Where does the criticality live? Early-warning signals are event-heterogeneous across seven crypto-perpetual liquidation cascades
- 2026-07-29 · http://arxiv.org/abs/2607.27070v1
- Do crypto perpetual-futures crashes carry a reproducible early-warning fingerprint of a critical transition, and in which state variable? We study seven major BTC liquidation cascades (2022-2025, including the record 19B USD event of 10 October 2025) using minute-level price and 5-minute leverage/order-flow data. On detrended residuals we compute rolling variance and lag-1 autocorrelation and test their pre-cascade trend with the Kendall-tau statistic, sweeping 39 analysis configurations per variable per event. No variable is event-invariant. Price carries the critical-slowing-down signature i

## Herding, Momentum, and Reversal in China's A-Share Market: An Agent-Based Network Model with Information Diffusion
- 2026-07-29 · http://arxiv.org/abs/2607.27063v1
- This study develops an agent-based financial market model to explain stock-price momentum and reversal through the joint effects of local herding and delayed information diffusion. Investors form heterogeneous Gaussian beliefs about the next-period price, choose among buying, selling, and remaining inactive, and revise their action probabilities in response to neighboring investors. The local interaction structure is represented by von Neumann and Moore lattices and is later replaced by Erdős--Rényi and Watts--Strogatz networks for robustness. A separate information process updates investor be

## Multi-Currency AMMs for Decentralized FOREX Markets: Feasibility & Optimal Design
- 2026-07-29 · http://arxiv.org/abs/2607.26405v1
- Most currency pairs lack a direct liquid market, so international foreign exchange relies on routing transactions through a dominant vehicle currency. Multi-currency automated market makers (AMMs) offer an alternative by sharing liquidity across many currency pairs, facilitating direct cross-currency trade while exploiting liquidity consolidation. This paper studies a multi-currency pool design that minimizes trading cost. Under a constant-mean AMM architecture, equilibrium trading costs reflect the trade-off between reduced price impact from consolidated liquidity and increased impermanent lo

## OpenMarket: A Synchronized Polymarket-Binance Dataset for High-Frequency Prediction-Market Research
- 2026-07-28 · http://arxiv.org/abs/2607.26245v1
- OpenMarket began as an attempt to trade Polymarket's BTC 15-minute binary markets against Binance BTC/USDT order flow. The attempt did not produce a tradable edge: out-of-sample, a walk-forward logistic model over 43 microstructure features does not beat, and slightly underperforms, the probability already implied by Polymarket's own order book, and simulated trading nets -0.116 normalized payoff units per attempted trade under stated fee and slippage assumptions. We release the synchronized corpus and infrastructure that attempt produced and, to our knowledge, the first public millisecond-lev

## Bitcoin Runs on a Clock: Why Every Price Indicator Dies and the Halving Clock Doesn't
- 2026-07-28 · http://arxiv.org/abs/2607.26188v1
- Every widely followed Bitcoin cycle indicator (Pi Cycle, MVRV, Mayer, Puell) called turns precisely for a decade, then degraded in one sequence: precise, then early, then silent. This is one structural phenomenon. Across the four halving epochs (2011-2026), the per-cycle maxima of five top-calling oscillators decline monotonically while minima end higher, so any threshold calibrated on past cycles must stop firing; short-horizon indicators decay toward zero and several invert sign; yet Bitcoin's time structure stays fixed, with mature-cycle tops 525/546/534 days after their halvings and bottom

## Train Often, Deploy Selectively: Forward-Gated Model Replacement in Crypto Markets
- 2026-07-30 · http://arxiv.org/abs/2607.28577v1
- Production forecasting systems retrain models regularly, but a retrained candidate does not necessarily outperform a continuously maintained incumbent that has continued to learn. We introduce Shadow Before Swap (SBS), a deployment policy that warm-refits a challenger off the serving path, evaluates it against the maintained incumbent on the same next week of delayed labels, and promotes it only after a fixed paired negative-log-likelihood (NLL) advantage. In historical replay over two nonoverlapping Binance episodes spanning 48 UTC weeks, three seeds, eight underlyings, and two perpetual-futu

## Can Large Language Models Execute Parent Orders?
- 2026-07-30 · http://arxiv.org/abs/2607.28410v1
- Parent-order execution is a core problem in algorithmic trading, where the goal is to split a large order into smaller orders while reducing execution costs. Existing approaches either rely on pre-specified market assumptions that may not hold in practice, or require task-specific training that limits adaptability to new settings. To overcome these limitations, we present the first systematic study of large language models (LLMs) for parent-order execution. This extends the use of LLMs in finance from what to trade to how to execute. We propose PACE (Plan-Ahead Controlled Execution), a hierarc

## Optimal Execution with Passive Market Impact
- 2026-07-30 · http://arxiv.org/abs/2607.28323v1
- We derive a mesoscopic model for optimal execution with limit orders that incorporates microstructural features of passive price impact. Our framework is based on two empirical observables: the approximately exponential decay of limit-order fill probabilities with distance from the midprice, and the short-term linear response of price changes to order flow imbalance. Combining these ingredients, we obtain a reduced-form passive impact rate that decays exponentially with quote distance. The model describes passive execution at a tactical level, where fills arise from a sequence of quote adjustm

## Bootstrap inference in autoregressive duration models
- 2026-07-30 · http://arxiv.org/abs/2607.28294v1
- This paper develops bootstrap inference for autoregressive conditional duration (ACD) models observed over a fixed calendar span, so that the number of durations is random. We study recursive schemes that either fix the calendar span or the realized event count. For the fixed-count bootstrap, we establish consistency when the duration tail index satisfies $κ\geq1$. When $0<κ<1$, classical consistency fails because the estimator has a mixed-normal limit, but the bootstrap reproduces its conditional Gaussian component. Consequently, basic percentile intervals remain first-order valid and bootstr

## Boundary-Induced Apparent Risk Aversion in Nonergodic Multiplicative Growth
- 2026-07-30 · http://arxiv.org/abs/2607.28230v1
- Finite multiplicative systems often cease to evolve when a lower continuation threshold is reached,whereas standard growth-optimal benchmarks assume uninterrupted continuation. We study a finite-horizon binary multiplicative process in which a fixed exposure is chosen ex ante and paths crossing an absorbing boundary are assigned a residual value. Exact lattice propagation yields the optimal exposure as a function of initial log distance to the boundary, horizon, and residual ratio. Costly absorption compresses exposure below the no-boundary Kelly fraction near the boundary. When interpreted th

## FinSMART: Financial Sentiment Analysis for Algorithmic Trading through Market-Aligned Reinforcement Learning
- 2026-07-30 · http://arxiv.org/abs/2607.28127v1
- Recent advances in Generative AI have substantially improved financial sentiment analysis through post-trained financial large language models (LLMs). However, existing approaches remain confined to a market-agnostic, supervised learning paradigm that relies on limited, static and human-annotated datasets, and thus are incapable of adapting to evolving market conditions. To address this limitation, we introduce FinSMART, the first market-aligned reinforcement learning framework for financial sentiment analysis, which directly optimizes sentiment signals using realized market outcomes. To deal 

## Energy Market and Carbon Emission Spillovers in Critical Minerals Investment: A Dynamic Connectedness Approach
- 2026-07-29 · http://arxiv.org/abs/2607.27485v1
- Design/methodology/approach A time-varying parameter vector autoregression (TVP-VAR) model is employed to quantify dynamic connectedness and directional volatility spillovers using daily data from May 1, 2013, to May 2, 2023. The study isolates the impact of extreme events by splitting the data into pre- and post-COVID-19 samples based on the February 2020 stock market crash. Purpose This paper examines the daily financial risk spillovers associated with investing in critical minerals. It examines the dynamic interconnectedness between seven critical mineral Exchange-Traded Fund (ETF) portfoli

## Are Three Matrices All You Need To Beat the Market? Observable Matrix Dynamics for Portfolio Optimization
- 2026-07-29 · http://arxiv.org/abs/2607.27461v1
- We present a simple framework for dynamic portfolio management that uses nothing but daily prices, trading volumes, and market capitalizations. Its state is three fixed-size matrices built from the price history: the distance matrix of the return correlations and the transition matrices of two Markov chains that rank the S\&P 500 names monthly by trailing return and by trailing volatility. These three matrices rest on the price history alone, the same information Markowitz mean-variance optimization draws on, but they replace its expected-return vector and covariance matrix. Our method require
