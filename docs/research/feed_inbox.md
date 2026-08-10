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

## Thermodynamic statistics of given names in USA and France
- 2026-08-06 · http://arxiv.org/abs/2608.06048v1
- Using official government data sets of USA and France we analyze the occurrence/frequency/popularity distributions of given names on a time scale of more than 100 years. These distributions are characterized through the Lorenz and Pareto curves broadly used in the analysis of wealth inequality in the world. These curves remain stable during the considered time period with the Gini coefficient remaining in the narrow range 0.85-0.95. As for the case of wealth inequality, we show that the distributions of names are well described by the Rayleigh-Jeans (RJ) thermalization and condensation phenome

## Knowledge-Optimising Investment Decisions with Informative Datasets
- 2026-08-06 · http://arxiv.org/abs/2608.05991v1
- The enormous growth in datasets, both in number and size, has prompted investors to adapt to new ways for assimilating information. Normatively, the approach has been to integrate such datasets into pricing formulations and assess the performance of portfolios created thereafter. However, such approaches underestimate their influence in portfolio investments by limiting their impact to pricing only. While being theoretically valid, this results in a potential sub-optimal performance in the presence of real-life decision constraints, and a blind spot for performance attribution. We start by ana

## Cross-Sectional Heterogeneity in LSTM Networks for Financial Time Series
- 2026-08-06 · http://arxiv.org/abs/2608.05755v1
- Predicting financial asset returns remains one of the most difficult challenges in empirical finance, driven by the low signal-to-noise ratio and the semi-strong form of market efficiency. While deep learning models, especially LSTM networks, have shown promise in capturing temporal dependencies, standard architectures often struggle to account for the cross-sectional heterogeneity of asset returns. This paper proposes a novel architectural extension to the basic LSTM model designed to improve both predictive accuracy and model interpretability. The framework integrates macro-financial covaria

## Velocity- and Regime-Aware Detection of Intraday Options Market Manipulation, with Explainable Attribution
- 2026-08-05 · http://arxiv.org/abs/2608.05373v1
- Intraday market manipulation is hard to detect because its footprint is brief, buried in millions of quotes, and statistically similar to ordinary volatility. Detectors reach high recall only by flagging so many other days that measured precision collapses, producing alerts no regulator can act on. We show that this manipulation leaves a distinctive dynamic signature: a pump-and-crash pattern visible in the velocity of market state, rather than its level. We build a minute-level detection pipeline, strictly partitioned in time, based on smoothed state velocity: option-Delta velocity for index 

## Portfolio Allocation under Heterogeneous Scales and Multifractality
- 2026-08-05 · http://arxiv.org/abs/2608.04987v1
- Cross-correlations between financial signals are neither scale-free nor amplitude-independent: they vary with the time scale over which they are measured and with the magnitude of the fluctuations that dominate the average. We exploit this structure to construct a portfolio allocation model in which the risk functional is the signed fluctuation function of multifractal cross-correlation analysis (MFCCA), indexed by a scale $s$ and a fluctuation order $q$. Unlike MFDCCA-type criteria, which rectify local detrended covariances before aggregation, MFCCA retains their sign, so that co-moving and c

## Optimal Life Insurance Decision in Mean-Variance DC Management with Mortality Improvements
- 2026-08-05 · http://arxiv.org/abs/2608.04532v1
- This paper studies the investment and insurance strategies of defined-contribution (DC) pension plans under the mean-variance framework. We consider a stochastic environment with time-varying interest rates, contributions, and mortality risk. The DC plan members are allowed to decide their bond and stock allocations, as well as their life insurance coverage. Adopting the martingale approach, we derive the closed-form optimal strategies and the mean-variance efficient frontier. Further numerical analysis investigates how mortality improvements affect investment and insurance decisions, as well 

## Public Trader Identity: Adverse Selection and Return Predictability
- 2026-08-05 · http://arxiv.org/abs/2608.04373v2
- Informed traders are supposed to need anonymity: they profit by hiding among the uninformed. A decentralized exchange now publishes the counterparty. Every committed order, cancellation, rejection, and fill carries a persistent pseudonymous wallet address. We reconstruct the full-depth limit order book from a record of 17.1 billion messages and 14.3 million aggressive orders by 147,113 wallets, covering $84.3 billion in taker notional. We report three findings. First, informativeness is a persistent wallet attribute. Wallets ranked by the price movement following their aggressive orders retain

## Measuring the engine of a liquidation cascade: subcritical branching inside a first-order transition
- 2026-08-04 · http://arxiv.org/abs/2608.03616v1
- We study seven major crypto-perpetual liquidation cascades (2022-2025), and in the largest of them we can watch the mechanism directly. From the on-chain fill log of a fully transparent venue we measure the branching ratio of that event -- the October 2025 crash, the largest on record -- in flight, with both of its factors observed and no free constants. It ran deeply subcritical: the structural ratio and the amplification bookkeeping both place it at $\hatλ\approx 0.1-0.2$ throughout, while a third, flow-based estimator falls through the climax rather than rising. All three agree on subcritic

## A New Approach to Goodness of Fit for Ergodic Markov Processes
- 2026-08-04 · http://arxiv.org/abs/2608.03088v1
- We introduce a new density-based goodness of fit test for ergodic Markov processes. Our test compares the data against the class of models specified in the null hypothesis, and rejects if no model in the class yields a stationary density that matches with the data. No alternative needs to be specified in order to implement the test. Although our test compares densities, estimation of smoothing parameters is not required, and the test has nontrivial power against $1/\sqrt{n}$ local alternatives. The test provides new perspectives on some existing problems in econometric and financial modeling.

## Mandate without Managers: Automated Market Makers as Verifiable Portfolio Products
- 2026-08-03 · http://arxiv.org/abs/2608.02917v1
- Automated market makers (AMMs) are typically interpreted and evaluated as decentralized exchanges. Herein, we take the perspective envisioned by Balancer that an AMM can also be viewed as a portfolio technology that programmatically enforces an economic mandate. In particular, we follow the geometric mean market maker (G3M) invariant employed by that protocol in order to enforce a target-weighted portfolio. We introduce a multi-asset fee structure to the G3M under which competitive arbitrage implements a band-rebalancing strategy with mis-weighting bounded ex ante, allowing compliance with the

## Proper-score observation-driven filters: local geometry, estimation, and continuous-time limits
- 2026-08-03 · http://arxiv.org/abs/2608.02828v1
- Observation-driven filters update a time-varying parameter with the likelihood score, linking the recursion to the logarithmic scoring rule. We replace this update with the negative parameter derivative of a differentiable proper scoring rule, within a declared working family and predictable scaling. For a general rule, the conditional mean update is a pre-conditioned stochastic-gradient of conditional scoring risk; when an autoregressive pull is included, the centre is the zero of a composite mean field. We derive local realised-loss descent and conditional-mean contraction results, and decom
THE DUTY THAT WAS SILENTLY NOT RUNNING NOW HAS AN INSTRUMENT: max_audit.check_feed_inbox_backlog
counts live entries and the age of the oldest, and fires past 20 open / 3 days. Zero entries is
the healthy state and reads clean, so draining is what the fence rewards. Separately, this doc was
nominally inside the section-33 scanned set the whole time and contributed exactly ZERO parsed
items -- listing a denominator is not counting one (L1.57). It is now in _DIG_DOCS_EXCLUDED with
its real lifecycle stated, and check_mine_scope_vacuous fails if any doc in scope ever again
carries content the parser cannot see. -->

## Certified High-Dimensional Wasserstein Robust Portfolio Optimization
- 2026-08-07 · http://arxiv.org/abs/2608.07032v1
- We develop a certified, scalable approximation for high-dimensional Wasserstein distributionally robust portfolio optimization. For expected-utility maximization under order-one Wasserstein ambiguity, standard duality yields a semi-infinite convex program. For long-only portfolios with box support under the one-norm ground metric, an exact sample-specific vertex reformulation provides an exponential-size computational benchmark. We then majorize the utility by supporting hyperplanes and dualize the support subproblems, obtaining a finite hyperplane--dual formulation over compact polyhedral sup

## Beyond Co-Movement: Locality by Exposures Enables a Joint Factor-Graph Framework for Portfolio Diversification
- 2026-08-06 · http://arxiv.org/abs/2608.06618v1
- Current portfolio construction methods are either agnostic to the effects of idiosyncratic shocks (standard factor models) or to the latent data structure driving systematic returns (recent graph-based approaches). This presents an opportunity to combine the complementary market aspects captured by the factor and graph domains, allowing asset allocations to operate directly on the underlying market structure, rather than on its observed co-movement or its finite-sample artefacts. In this work, we introduce the Mutually-INformed Graph-Locality and Exposures framework (MINGLE), which mutually re
