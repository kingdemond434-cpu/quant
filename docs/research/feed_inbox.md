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

## Effort-Centric Fairness in Lending Decisions
- 2026-07-30 · http://arxiv.org/abs/2607.28847v1
- Algorithmic credit scoring must satisfy fairness and explanation requirements, yet prevailing predictive-parity criteria assess only outcomes at the decision point. They can therefore overlook whether rejected applicants face unequal burdens in reaching future approval, a phenomenon we call masked inequality. We develop an effort-centric framework that measures an applicant's effort as the minimum weighted cost of feasible changes required to cross the approval boundary. The framework distinguishes feature-independent actions from additive structural shifts that propagate through a causal mode

## Path Portfolio Optimization: Defect, Lift, and the Price of Path Complexity
- 2026-08-03 · http://arxiv.org/abs/2608.02355v1
- This paper builds Path Portfolio Optimization: portfolio theory on a path-first framework in which the signature is the universal coordinate of the price path, and asks whether it survives estimation. A portfolio is a linear functional of the signature, so the control lives in a truncated tensor algebra, the covariance of signature coordinates is the non-group-like part of the expected signature --- a defect form --- and the whole mean--variance problem becomes a linear system in one tensor. Two structural results follow. The lift is the execution convention: the gap between the Marcus and for

## AI Governance for Institutional Readiness in Finance
- 2026-08-03 · http://arxiv.org/abs/2608.02311v1
- Agentic AI is gaining acceptance in asset management, but governance has not kept pace: 88% of surveyed finance professionals report no operational governance framework for agentic AI despite universal awareness of its deployment, and only 24 of 75 large U.S. money managers disclosing AI use in Form ADV filings report a formal governance policy. We argue this gap is architectural, not cultural: governance built for deterministic systems assumes static validation. However, continuously retrained agentic policies violate static governance by design. We propose a four-layer framework (Policy, Eng

## AI Financial Advice: Supply, Demand, and Life Cycle Implications
- 2026-08-03 · http://arxiv.org/abs/2608.01607v1
- We ask a representative sample to write prompts seeking spending and investing advice from LLMs, then simulate the lifetime effects of following the advice under realistic asset and labor market conditions. Applying this method to GPT-5.2, we find following the advice would move respondents toward life cycle theory: broader participation in diversified equity funds, age-declining equity shares, and larger savings buffers. Recommendations vary systematically by gender, prior AI experience, and financial literacy. For gender, two-thirds of recommended equity-share differences arise from men and 

## Conformal Kelly: Conformal Prediction Intervals as the Scale in Fractional Kelly Position Sizing
- 2026-08-02 · http://arxiv.org/abs/2608.01494v1
- Conformal prediction has traditionally been used to quantify prediction uncertainty. We put that uncertainty to a second use, combining a 75% conformal interval with fractional Kelly to size portfolio positions: as the range widens we shrink the position, and as it narrows we grow it. On a six-year development window (2016-2021), with trading costs and strict leverage caps, this compounds at 28.5% annualised net log growth with a Sharpe ratio of 1.34 and a 27.7% maximum drawdown, versus 15.9% for holding the S&P 500 and 21-22% for passive portfolios at the same leverage. Our main development-w

## Exactly solvable model for the diffusive price-dynamics paradox under long-range correlated market-order flow
- 2026-08-02 · http://arxiv.org/abs/2608.00988v1
- We develop an exactly solvable nonlinear time-series model by incorporating the square-root price-impact law into the Lillo--Mike--Farmer (LMF) model to resolve the diffusive price-dynamics paradox under predictable market-order flow. In financial market microstructure, it is well established that the price dynamics are approximately described by Brownian motion at long times. However, it is also well-known that market-order flow is clearly predictable due to long-range correlations, as mathematically formulated by the LMF model. Since market orders have a positive price impact in general, pre

## Optimal Trading of Microstructure Mean Reversion
- 2026-08-01 · http://arxiv.org/abs/2608.00885v1
- At the scale of seconds the observed mid carries a stationary, mean-reverting error around a latent efficient price. We build an order book whose own flow produces that error and solve for the trading rule that maximises the long-run average profit rate net of the bid-ask spread. In a liquid large-tick asset the spread is one tick or two, and it is exactly the parity of the mid on the half-tick grid: tight at a half-integer, open at an integer. One coordinate therefore carries the problem: the gap $G$ between the mid and the efficient price; the price is an exogenous Brownian martingale, and $

## Data-Driven Measures of High-Frequency Trading
- 2026-08-01 · http://arxiv.org/abs/2608.00858v1
- We introduce data-driven measures of high-frequency trading (HFT) that distinguish between liquidity-supplying and liquidity-demanding strategies. We train machine learning models on a proprietary dataset with observed HFT activity, then apply these models to public intraday data to generate HFT measures across all U.S. stocks during 2010-2023. Our measures outperform conventional proxies, which struggle to capture the temporal dynamics of HFT. Consistent with theory, our measures respond to a quasi-exogenous speed bump introduction and a data feed upgrade. The measures help uncover the differ

## AI and Exchange Rate Predictability
- 2026-08-01 · http://arxiv.org/abs/2608.00761v1
- I revisit the exchange rate disconnect puzzle, first documented by Meese and Rogoff (1983), using generative artificial intelligence (AI) to forecast currency returns based on economic fundamentals. Using ChatGPT and DeepSeek, I analyze a comprehensive dataset of economic data releases for major currency pairs and measure the fundamental strength of each currency. These AI-powered fundamentals exhibit significant cross-sectional predictive power. A simple trading strategy that goes long currencies with strong fundamentals and short currencies with weak fundamentals generates a Sharpe ratio exc

## Axient: On-Chain Credit and Loss Allocation for Leveraged Event Markets: A Venue-Agnostic Protocol for Traders, Credit Providers, Market Makers, and Liquidation Backstops
- 2026-08-01 · http://arxiv.org/abs/2608.00647v1
- A physically backed leveraged event position requires real credit: if collateral C receives leverage L, the protocol supplies (L-1)C and uses the combined amount to acquire recognized event exposure. This paper develops a venue-agnostic on-chain credit architecture for that capital layer and an endogenous model of its capital market. It separates traders, Senior Credit LPs, market makers, liquidators, and Liquidation Backstop Providers; formalizes pool and debt shares, utilization- and risk-sensitive interest, collateral-locked position accounts, venue capabilities, market-maker commitments, w

## Axient: Debt-Free Finality for Leveraged Binary Event Markets
- 2026-08-01 · http://arxiv.org/abs/2608.00631v1
- Leveraged event positions combine a repayable loan with an outcome claim that may become non-tradable before oracle payout is final. This paper specifies Axient, a physically backed margin layer for binary event markets that separates leverage maturity from claim maturity and makes the hard-flat decision under explicit execution uncertainty. The model distinguishes quoted book proceeds, matched proceeds, settled proceeds, and redemption. At decision time, the protocol selects the smallest sale whose lower settled-proceeds envelope covers an upper bound on debt at the settlement horizon plus a 

## Drawdown Risk Beyond Brownian Motion: A Monte-Carlo Framework, Non-Gaussian Extensions, and Long Memory
- 2026-07-31 · http://arxiv.org/abs/2608.00127v1
- How deep and how long should the drawdowns of a systematic trading strategy run, given its Sharpe ratio and the statistical structure of its returns? Building on the drawdown framework of Rej, Seager and Bouchaud (2017), we develop the answer in three steps. We first reframe their closed-form results as a transparent Monte-Carlo experiment, validate it against their analytic benchmarks, and extend the mapping from drawdowns to four decision-relevant measures: maximum drawdown, maximum loss, final negative time and longest recovery time. We then relax the Gaussian assumption, holding the true S

## Boundary-Induced Apparent Risk Aversion in Nonergodic Multiplicative Growth
- 2026-07-30 · http://arxiv.org/abs/2607.28230v2
- Observed risk-taking behavior is often rationalized through expected-utility curvature, yet the curvature required to fit choices in one context can differ sharply from the curvature required in another, a tension highlighted by calibration critiques of expected-utility theory. Finite multiplicative systems often cease to evolve when a lower continuation threshold is reached, whereas standard growth-optimal benchmarks assume uninterrupted continuation. We study a finite-horizon binary multiplicative process in which a fixed exposure is chosen ex ante and paths crossing an absorbing boundary ar
