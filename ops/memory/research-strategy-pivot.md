---
name: research-strategy-pivot
description: "Quant platform's binding constraint is data, not code; committee verdict + net-of-cost/data-breadth pivot implemented; real 0-survivor FX result."
metadata: 
  node_type: memory
  type: project
  originSessionId: 4af772ee-24a6-45c2-aa20-7c72e83a9443
---

Investment-committee review (2026-06-20) of the solo quant platform concluded: the binding
constraint is **data and edge, not software**. Engineering/validation are near-institutional; the
honest probability of a durable, net-of-cost edge **on the current price-only path is <5%**.

Decision: **option B (targeted pivot)** -- keep the validation/audit/governance/discovery core;
change the broken parts (inputs = data, accounting = net-of-cost) and focus on one niche (FX carry /
cross-asset). Exploit the solo edge: **low-capacity niches institutions ignore** (do NOT apply
institutional capacity filters). Real capital is never allocated automatically.

Implemented (all ruff+mypy+pytest green): **net-of-cost engine** from real MT5 symbol_info
(`libs/costs/mt5_calibration.py`) wired per-symbol into the lab; **execution-gap stress gate**
(`libs/costs/execution_gap.py`) + **regime-robustness gate** (`libs/autodiscovery/regime.py`, >=2
vol regimes) as REGISTRY gates; **cross-campaign DSR deflation** (cumulative trials); focused-family
filter; **Kelly = 1/3 base, 1/2 only when roi_qualified** (wired in `stage14/engine._roi_qualified`:
WF-pass + edge/conf/pf/capacity thresholds); `docs/KILL_THESIS.md` deployable bar. **Perf fix**: PBO
+ White's Reality Check computed ONCE per campaign (`validation.campaign_pbo_rc`), not per-candidate
-> gauntlet went from hanging to ~1 min.

REAL RESULT (2026-06-20): net-of-cost research on **26 yrs FX daily** (7 USD majors;
carry/cross-asset/momentum/mean-reversion) via `scripts/run_research_lake.py` -> **0 survivors / 49
tested** (all failed DSR+PBO+Reality-Check). Honest zero, consistent with the prior.

Data ceiling: only ~57 FX + energy D1 landed via MT5 (cold-terminal/weekend); FRED/Yahoo blocked.
Pivoted to FREE crypto data (Binance APIs reachable). Tested niches, all net-of-cost honest:
FX directional **0**, crypto funding reversal **0** (daily+8h), crypto funding carry **0** (caught a
Sharpe-17 FALSE POSITIVE that vanished once crash-history was included), prediction markets
**negative/data-capped**, token unlocks **data-blocked (DefiLlama paywalled)**.

BEST RESULT (2026-06-21): **cross-sectional crypto funding** (long lowest-funding / short
highest-funding perps, dollar-neutral, inverse-vol sizing, turnover band, ADV-tiered costs) on
**~85-100 liquid Binance perps x 6yr** -> **~0.96 net-of-cost annual Sharpe, passes 8/9 gates,
fails ONLY White's Reality Check** (data-snooping). Shared core: `libs/research/crypto_xsec.py`
(used by both `scripts/run_xsec_funding_max.py` and the shadow). NOT deployable; resolved FORWARD.

ARCHITECTURE DECISION (2026-06-21, user-set, binding): **research globally, execute natively on
MT5 (sole execution venue).** Brain = Python (alpha, data, portfolio construction, regime, risk,
sizing, signals) free to use ANY global data; Hands = MT5 EA does ONLY execution, position mgmt,
risk controls, sync, failover. Optimize for max real net return + robustness, not MT5-only data.

MT5 CROSS-ASSET SEARCH (2026-06-21, honest, all net-of-cost via the full gauntlet): ingested a real
30-symbol 5-class MT5 panel (FX/metals from 2008, indices 2012, BTC 2011) via
`scripts/ingest_multiasset.py`. Diversified-PORTFOLIO constructions in `libs/research/crossasset.py`
(`xsec_signal_returns`/`xsec_momentum_returns`/`trend_basket_returns`), run by
`scripts/run_mt5_crossasset.py` -> **0 survivors**: cross-asset momentum ~0.67 Sharpe & trend basket
~0.59 pass 7/9 gates, fail **DSR (trials-deflated) + fragility (fat tails)**; reversal negative.
Real-but-modest managed-futures premium, below the 0.7 deployable bar AND ETF-replicated (DBMF/KMLM).

DECISIVE finding -- funding edge CANNOT port to MT5 (`scripts/run_mt5_funding_bridge.py`): using the
Binance funding signal to trade the 8 MT5 crypto CFDs, PRICE-ONLY (a CFD earns no perp funding),
gross Sharpe ~**0.04** (noise); with realistic CFD financing it goes **negative**. So the ~0.96
funding Sharpe is the funding **cashflow itself**, not price prediction -> it is structurally
inseparable from Binance perps and cannot be replicated on MT5 CFDs. Not a data gap, a venue fact.

BRAIN->EA CHASSIS already exists (do NOT rebuild): Python brain (`app.signal_builder` -> Stage13.5
-> Stage14 sizing -> risk gate -> `DemoRunner`) + `libs/portfolio/rebalance.py` (target weights ->
trades) + `libs/execution/ea_bridge.py` (atomic-file `BrokerGateway`) + `ea/QuantPlatformExecutor.mq5`
(executes/reports/heartbeats/safety floors ONLY) + `scripts/run_live_demo.py` (DEMO-hard-gated).
Best MT5-EXECUTABLE candidate = cross-asset **trend(100)+momentum(120) equal-risk combo** (frozen),
~0.62 net Sharpe, 7/9 gates (fails PBO+fragility) -> in forward shadow via
`scripts/run_crossasset_shadow.py`, which emits today's `data/target_portfolio.json` (30-instrument
diversified book = the EA's would-be order set). Combo core + weight emitters in
`libs/research/crossasset.py`. Dashboard: 2nd shadow card on research.html; scoreboard 7 strategies.
Honest standing: NO deployable edge yet; funding (0.96, RC-fail) stays on Binance, cross-asset combo
(0.62, PBO/fragility-fail) is the MT5 path -- both shadow-only, ETF-benchmarked, human-approval-gated.

ATTEMPTED + FAILED (2026-06-21): vol-targeting overlay (`vol_target` in crossasset.py, 10%/30d/3x,
`scripts/run_crossasset_robust.py`) to rescue the combo's fragility/PBO -> made it WORSE (0.62->0.26,
added DSR fail). PBO+fragility are STRUCTURAL to the cross-asset premium here, not fixable by honest
risk engineering. Conclusion for "make MT5 as deployable as Binance": cannot by tuning/overlays
(that's p-hacking). The ONLY honest lever is stacking genuinely UNCORRELATED real edges (Sharpe ~
sqrt(N) x single) -- which is DATA-constrained (need carry=rates, value=fundamentals, positioning=
CFTC COT, vol-risk-premium=options). Data remains the binding constraint. Funding edge is richer
because it's a structural cashflow, not a crowded ETF-replicated premium.

FULL MT5 ALPHA-PORTFOLIO CAMPAIGN (2026-06-21, `scripts/run_mt5_portfolio.py`,
`libs/research/sleeves.py`, `libs/data/cot_source.py`): tested 9 MT5-executable sleeves net-of-cost
through the full gauntlet + CFTC COT positioning (free, reachable: publicreporting.cftc.gov legacy
6dca-aqww; 11 instruments mapped in COT_MAP w/ JPY/CHF/CAD sign-flip). RESULTS (ann Sharpe, gates):
xsec_mom 0.67 (7/9), trend 0.59 (7/9), **metals_mom 0.36 (8/9 -- best gate result, fails only DSR)**,
wti_brent_rv 0.24 (7/9), cot_positioning 0.11 (6/9, genuinely UNCORRELATED ~0.16 to trend), and
NEGATIVE/non-edges: index_trend -0.19, gold_plat_rv -0.33, fx_mom -0.58, gold_silver_rv -0.71.
Best honest portfolio = trailing-Sharpe-gated risk parity **0.71, still fails DSR+fragility**;
vol-target overlay hurts again (0.05). **0 survivors.** Positive sleeves are all momentum-family
(corr 0.5-0.83) so diversification can't lift them; the uncorrelated sleeves (COT/RV) are weak.
CONCLUSION: every MT5 price-based edge tops ~0.71 and fails DSR (multiple-testing significance) +
fragility (tails). No in-sample survivor. Honest paths left: (1) FORWARD SHADOW to earn OOS evidence
that overrides the deflation penalty (metals_mom + gated portfolio are the candidates); (2) a
genuinely stronger uncorrelated edge = needs data we lack free (rates/carry, options/vol-premium).
COT z-cache at data/cot_zcache.parquet. Will NOT weaken gates or claim n_trials=1 post-hoc.

FINAL (2026-06-21, 11 sleeves): added cot_timeseries (-0.33, worse than x-sec COT) and
gold_crisis_hedge (long gold in equity-risk-off; -0.5 standalone but genuinely NEG-correlated -0.24
to -0.54 to everything = real tail diversification, yet negative carry so trailing-Sharpe weighting
gives it ~0). Best portfolio = trailing-Sharpe-WEIGHTED risk parity (`_riskparity mode=weight`) =
0.67, still fails DSR+fragility. CEILING CONFIRMED: free MT5-executable price/positioning alpha tops
~0.67 Sharpe, 0 survivors. Adding sleeves doesn't help (positives are momentum-family & correlated;
orthogonal ones are weak or negative-carry) AND raises the DSR trials bar -- brute search is
self-defeating. This is MAXIMUM for the data class. Real unlock now = (1) forward shadow to earn OOS
significance, (2) NEW data class (rates/carry, options/vol-premium) -- not more in-sample sleeves.

CARRY + MACRO ADDED (2026-06-21): (1) MT5-native CARRY sleeve = broker swap rates
(`scripts/log_swaps.py` -> data/swap_log.parquet daily; `swap_carry_returns` in sleeves.py). No swap
history exists (MT5 gives only current) so carry is FORWARD-ONLY (auto-activates in the portfolio at
>=250 logged days; until then honestly excluded). Seeded 24 symbols; sensible signal (oil/AUDJPY/
USDJPY positive carry; note broker swap-spread asymmetry). (2) MACRO/CALENDAR turn-of-month sleeve
(`calendar_event_returns`): INITIALLY showed 1.48 Sharpe -- but that was a FALSE POSITIVE artifact
(crypto weekend rows in the combined frame poisoned the rolling vol -> <250 biased active days).
Caught + fixed (compute on each instrument's own trading days, map back). True value = **0.10 Sharpe,
split-half -0.49/+0.59 = NO edge**. Portfolio with all 12 sleeves still 0.66, fails DSR+fragility,
0 survivors. Honesty win: killed a 1.48 backtest illusion per the no-illusion mandate.

PUSH-TO-MAX ATTEMPT (2026-06-21, 13 sleeves): added (a) dedicated CRYPTO_TREND sleeve and (b)
hierarchical/cluster risk parity (`_cluster_riskparity`, momentum family = ONE bet). Also added
honest CFD overnight FINANCING (`_HOLD`: crypto 5bps/day etc.) to all held books -- this CAUGHT
another illusion: crypto_trend 0.74 -> **0.59** once financing is charged. crypto_trend is the best
single sleeve (0.59, 8/9, fails only DSR) BUT 0.95-correlated with trend_all (a concentrated trend
bet, not a diversifier; incr -0.03). Cluster RP IS the best construction (**portfolio 0.63** vs flat
0.55). Net: honest ceiling now ~0.63 (lower after true financing), still fails DSR+fragility, 0
survivors. Carry sleeve forward-only (seeded). AUTOMATION: Windows task **QuantDaily** 03:15 runs
`scripts/run_daily_research.py` (log_swaps -> funding shadow -> crossasset shadow -> portfolio ->
scoreboard). Conclusion stands: no in-sample survivor; real lift needs carry-accumulation + forward
significance + a new data class. Refused to manufacture a survivor.

GROWTH-OPTIMAL LEVERAGE (2026-06-21, `libs/risk/growth_leverage.py` + tests; wired into
run_mt5_portfolio -> web/leverage.json + research.html panel). Objective reframed by user to
geometric CAGR (not Sharpe). Ladder on portfolio_cluster: growth-optimal (Kelly) L~**1.15x**
(CAGR ~13% @1x), recommended half-Kelly ~0.58x; **aggressive >=2x -> CAGR collapses to -100%
(RUIN), ruin prob 15% @2x, 38% @3x**. Headline: growth-optimal leverage is LOW (~1x), NOT 5-10x;
volatility drag + fat tails destroy compounding above ~1.5x. KEY RISK FINDING: portfolio has skew
~8.6 and ann vol ~50% @1x with -85% maxDD -> the trailing-Sharpe cluster weighting CONCENTRATES into
crypto when its trailing Sharpe dominates, then eats the crash (real fat tail, partly genuine crypto
crash risk). Robustness fixes pending: per-cluster weight CAP + pct_change gap-guard. CAGR assumes
the (unvalidated) edge persists -> deploy fractional/shadow only. Kelly assumes edge is TRUE; on a
DSR-failing edge full Kelly maximizes ruin, so half-Kelly-capped is the honest size.

ROBUSTNESS FIXES + DEMO DEPLOYMENT (2026-06-21). (1) Return GAP-GUARD `libs/data/cleaning.py`
guard_close (caps per-bar log-return by asset class, rebuilds path) -> killed bad-print spikes;
portfolio skew 8.6->3.8, wired into run_mt5_portfolio + run_crossasset_shadow _load. (2) Per-cluster
WEIGHT CAP 30% (`_riskparity max_weight` + `_cluster_riskparity`) -> stops crypto concentration;
3x ruin -100%->-25%. Portfolio still 0.58 Sharpe, fails DSR+fragility (genuinely drawdown-prone,
-61% DD @0.5x). (3) LIVE DEMO EXECUTOR `scripts/run_portfolio_live.py`: reads target_portfolio.json
-> margin-aware lot sizing (gross = equity x --gross-leverage, floored at min-lot so ALL instruments
trade, scaled to --margin-frac of free margin), demo-HARD-GATED, magic 770001, dry-run default.
PLACED REAL DEMO TRADES on ICMarketsEU-Demo login 52918448: 12 diversified positions (short crypto
basket, long USD/US500, short metals) matching the brain target, ~1x gross, $2k margin. NOTE: $10k
demo too small for 30 names at min-lot (~$40k needed) -> weekend only crypto open; use bigger demo
or higher --gross-leverage. Dashboard research.html now has LIVE panel (web/live.json) + leverage
panel + shadows. Scheduled: QuantDaily 03:15 (research/target refresh), QuantLive HOURLY (rebalance
to target, --live), QuantShadow 02:30, QuantResearchTick 02:00. All 3 running: live + shadow + dash.

CRYPTO PIVOT (2026-06-22, user directive): binding constraint to 1.5 is the MT5-only venue, NOT
data/budget -- the strongest free edges are crypto-native (Binance perps). Switched factory to
crypto. `libs/research/crypto_sleeves.py` (funding_momentum, funding_reversal, generic `_book`) +
`scripts/run_crypto_portfolio.py` (cluster-RP portfolio engine, reuses crypto_xsec/crossasset/sleeves
/growth_leverage/gauntlet). RESULT on 86 perps x 2479d: **PORTFOLIO Sharpe 1.13** (vs MT5 0.6) with
GENUINELY LOW correlations (funding vs price ~0). Sleeves: funding_carry 0.91 (7/9, incr +0.53),
funding_momentum 0.54 (+0.36), xsec_price_mom 0.84 (+0.17); DRAGS to drop: ts_trend (incr -0.17),
btc_eth_rv (-0.7), funding_reversal (-2.21, dead). Portfolio 1.13 is BACKTEST, fails gauntlet
(dsr/pbo/wf) -> unvalidated, needs forward shadow. PATH TO 1.5 (all free): add orthogonal Binance
sleeves = OI divergence, perp-spot BASIS carry, long/short ratio, taker-vol imbalance, liquidations.
web/crypto_portfolio.json written. NEXT: more crypto data collection + sleeves; Binance TESTNET
executor (separate venue adapter, Python brain unchanged). Conclusion: crypto-native is the real
path to >1.5; MT5 stays a secondary low-Sharpe book.

CRYPTO PORTFOLIO UPGRADES (2026-06-22): 4 modules built+tested+wired into run_crypto_portfolio.
(1) Dynamic covariance forecasting `libs/portfolio/covariance.py` (ewma_cov + EV-gated ERC +
no-trade band + rebal cost) = `cov_forecast_portfolio`; the cov-forecast book scores ~0.97 at 6/9
gates (passes CPCV where static cluster-RP fails) -> the MORE ROBUST combiner. (2) Regime switching
`libs/research/crypto_regime.py` (bull/bear, hi/lo-vol, funding-rich/poor labels + per-regime Sharpe).
(3) TC-aware = no-trade band + rebal cost in the cov allocator. (4) Stress testing
`libs/risk/stress.py` (crisis_replay FTX/covid/LUNA/aug24, worst_window, beta_shock, funding-off).
KEY RESULTS: crypto portfolio Sharpe UNSTABLE ~0.75-1.16 across daily refreshes (-> unvalidated,
fails DSR/PBO/WF, consistent w/ overfitting). SURVIVABILITY EXCELLENT: BTC -30% shock -> -0.4% (beta
0.012, genuinely market-neutral); survives all named crises (<6% maxDD) + funding disappearing
(Sharpe holds ~1.3). Dead sleeves to drop: funding_reversal (-2.3), btc_eth_rv (-0.7). Path to 1.5
unchanged: more orthogonal Binance sleeves (OI/basis/long-short/taker/liquidations) + forward
shadow. Scoreboard + run_daily_research now include crypto portfolio. NEXT: more crypto data
collection + sleeves; Binance TESTNET executor (separate venue adapter).

FREE-DATA EXPANSION (2026-06-22): extended crypto_source (_klines now captures taker_buy_frac;
daily_enriched adds perp-spot BASIS; fetch_long_short_ratio/fetch_taker_ratio for 30d-capped
archive). New sleeves `crypto_sleeves.py`: basis_carry (0.86, perp-spot premium fade) + taker_flow
(**1.01, 7/9** order-flow momentum) -- both genuinely orthogonal (corr ~0-0.18). Enriched 55-92
liquid perps (`ingest_crypto_enriched.py`). Forward archiver `collect_binance_metrics.py` ->
data/crypto_metrics.parquet (OI/LS/taker daily; 30d-capped so accumulating for FUTURE sleeves).
DROPPED as economically refuted: funding_reversal (-2.3), btc_eth_rv (-0.7). Best combiner = flat
trailing-Sharpe-tilt (~0.99) > cluster (0.89) > cov-forecast (0.55); equal-risk methods DILUTE
high-Sharpe sleeves. HONEST CEILING: crypto portfolio ~0.9-1.1, UNSTABLE across refreshes (0.55-1.16),
fails DSR/PBO -> unvalidated. SURVIVABILITY EXCELLENT: BTC beta 0.003 (-30% shock -> -0.1%),
funding-off Sharpe 1.57, survives all crises (<6% DD). Why not 1.5: realized sleeve corrs 0.1-0.37
(not 0) + robust (non-overfit) combiner caps ~1.0. Path to 1.5 = archived OI/LS metrics maturing into
more orthogonal sleeves (weeks) + forward shadow. 4 upgrade modules live: dynamic cov forecasting
(`libs/portfolio/covariance.py` ewma_cov/erc_weights/cov_forecast_portfolio), regime switching
(`crypto_regime.py`), TC-aware (no-trade band+rebal cost), stress (`libs/risk/stress.py`).
Daily sched (QuantDaily) now: swaps->shadows->metrics archive->enrich->crypto portfolio->mt5->board.

TESTNET STACK + DASHBOARD FIX (2026-06-22). (1) DASHBOARD ACCESS BUG FIXED: was a manual http.server
dying on terminal close. Built `scripts/serve_dashboard.py` (threaded, no-cache, web/ only); now runs
as a DETACHED pythonw process (survives terminal close) + Startup .bat at
%APPDATA%\...\Startup\QuantDashboard.bat (survives reboot, no admin). localhost:8080 always up:
index/research/factory.html. (2) BINANCE FUTURES TESTNET executor: `libs/execution/binance_testnet.py`
(PINNED testnet URL, HMAC, keys from env BINANCE_TESTNET_KEY/SECRET -- never in code; has_keys gate;
public mark_prices/filters work keyless). `scripts/run_crypto_target.py` emits data/crypto_target.json
(43-perp net book from funding_carry+basis_carry+taker_flow). `scripts/run_crypto_testnet.py` =
executor: sizes off balance x gross-lev, diffs vs positions, market orders, trade DB
(data/crypto_trades.sqlite), kill switch (data/CRYPTO_KILL), daily-loss stop, gross-lev cap 5x,
DRY-RUN default (--live needs keys), writes web/crypto_testnet.json. Dry-run verified (19 pos, 1.46x).
TO GO LIVE: create keys at testnet.binancefuture.com, set env, run --live. (3) Information Advantage
Score `libs/factory/registry.py information_advantage_score` + `scripts/run_factory_status.py` ->
web/factory.json (IAS=26: 6 active/3 orthogonal/0 validated/1 archive-day; milestone 0.99->1.0).
QuantDaily extended: ...->crypto target->scoreboard->factory status. All ruff/mypy/pytest green.

8h FUNDING TEST (2026-06-22, `scripts/run_funding_8h.py`): tested the best edge (funding carry) at
NATIVE 8h resolution (3x obs) hoping more data clears DSR -> REFUTED: 0.28 Sharpe (vs ~0.9 daily),
0 survivors. Finer resolution = 3x turnover cost + noisier signal = WORSE net. Daily remains best.
IN-SAMPLE SEARCH NOW GENUINELY EXHAUSTED across all asset classes, families, frequencies, and
portfolio combiners -> 0 survivors everywhere; the deflated-Sharpe gate correctly blocks ~0.6-1.0
edges given the trial count. Remaining free edges (OI/liquidations/long-short) are forward-only
(30d-capped -> archiving). CONCLUSION (firm): a survivor can ONLY emerge from FORWARD shadow evidence
(converts unstable backtest into the significance the in-sample gauntlet correctly withholds); more
in-sample search RAISES the DSR bar and is counterproductive. Stop searching in-sample; accumulate
forward. Best candidates in shadow: funding_carry (~0.9), taker_flow (~1.0), basis_carry (~0.86).

90-DAY FORWARD RUN STARTED (2026-06-22). `scripts/run_crypto_shadow.py`: FROZEN crypto book
(funding_carry+basis_carry+taker_flow+xsec_price_mom+ts_trend, flat trailing-Sharpe combiner, NO
re-selection) tracked forward OOS from shadow_start=2026-06-22; bt_sharpe 1.27, fwd 1/90 days,
verdict ACCUMULATING. data/crypto_shadow_state.json holds the frozen start; web/crypto_shadow.json +
factory.html shadow card. Decision rule = docs/KILL_THESIS (promote if >=90d & fwd>=0.5 & >=half bt;
kill if fwd<0; never re-tune). Refused to hardcode the DSR bar (would fabricate a survivor) -- the
forward shadow is the ONLY honest path to certification. Why sleeves don't sum: Sharpes combine in
quadrature (sqrt sum sq ~1.6 ideal for the 3 best), cut by corr (funding-basis 0.37) + robust
(non-overfit) combiner -> realized ~1.0-1.27. SCHEDULED: QuantTestnet HOURLY (run_crypto_target +
run_crypto_testnet --live; DRY until user adds testnet keys to data/secrets/binance_testnet.json),
QuantDashboard always-on server (:8080, detached + Startup .bat), crypto shadow in QuantDaily.
Testnet goes live automatically once keys are dropped in.

TESTNET LIVE + FRONT PAGE (2026-06-22): user added testnet keys (data/secrets/binance_testnet.json),
LIVE trading confirmed (19 perp positions). Added equity/PnL tracking (bt.account_summary/
income_summary/realized_trades), web/binance.html FRONT PAGE (equity, balance, win rate, realized/
unrealized PnL, funding, positions, equity curve) + web/binance.json feed + equity_curve DB table.
FIXED daily-loss stop to use EQUITY not wallet balance (was false-flattening). LEVERAGE set to
aggressive sweet spot: crypto growth-opt L=6.1x (CAGR peak 53%), set executor default 3x (half-Kelly)
+ running testnet at 5x (51% CAGR, -93% DD); QuantTestnet hourly at 5x. LEVERAGE ANSWER (the math):
CAGR rises to ~6x then FALLS (8x->47%, 10x->27%+ruin) -- volatility drag; NOT unlimited benefit.
CAVEATS: (1) peak DDs are -93/-96% (brutal); (2) CAGR ladder ASSUMES the 0.99 Sharpe is real -- it's
UNVALIDATED, so if half-real the true peak HALVES to ~3x and 5-6x is PAST it -> real-money sweet spot
is ~3x until shadow validates. WIN RATE 7.5% is a CHURN ARTIFACT (dollar-neutral book pays spread on
every rebalance close -> tiny realized losses); watch equity/PnL not win rate. Churn cost real
(-$1066 realized from rebalance/flatten churn) -> no-trade band still the top refinement.

DD-CONTROL + ANTI-CHURN (2026-06-22): run_crypto_testnet now has (1) NO-TRADE BAND (default 0.25 =
skip rebalancing a position unless drifted >25%; always allow full exits) -> verified orders=0 when
within band, kills spread bleed; (2) DRAWDOWN THROTTLE (_dd_throttle): leverage x1.0 above -5% DD,
x0.7 to -10%, x0.4 to -20%, x0.2 below -20% -> auto-deleverages into slumps so realized DD << static.
Unified state (_sync_state: day/start_equity/peak_equity). Running testnet at 6x base (growth-opt CAGR
peak) WITH throttle -> aggressive when winning, defensive when losing. QuantTestnet hourly at 6x
--band 0.25. AUDIT verdict (CIO): binding constraint to Sharpe>1.5 is ORTHOGONAL ALPHA (data-gated)
+ forward-validation TIME, NOT code (portfolio/leverage/risk engines are done). Highest-ROI now:
(a) forward shadow time [running], (b) anti-churn [done], (c) archived OI/LS maturing into sleeves.
6x leverage CAGR is on an UNVALIDATED edge -> real-money sweet spot ~3x until shadow proves it.

UNIFIED + AUTONOMOUS + REAL-TIME (2026-06-22). (1) MT5 ABANDONED: deleted QuantLive task, removed all
MT5 steps from run_daily_research (now crypto-only: metrics->enrich->funding shadow->portfolio->
DISCOVERY->target->crypto shadow->scoreboard->factory status). (2) AUTONOMOUS DISCOVERY
`scripts/run_discovery.py` -> web/discovery.json: tests economically-distinct sleeve LIBRARY (not
param sweeps) through gauntlet, classifies REJECTED/CANDIDATE/SHADOW(orthogonal corr<0.4 +Sharpe>0.5)
/DEPLOYABLE, lists PENDING data-gated edges (oi_divergence/ls_contrarian/liquidation_reversal,
auto-activate at 40 archived days). First run: 6 shadow-eligible, xsec_reversal rejected. (3) UNIFIED
single-page dashboard = web/index.html (live exec + shadow + discovery + sleeves + info advantage; no
MT5; nav anchors). Old binance/factory/research.html still exist but index.html is the one host.
(4) REAL-TIME executor: --minutes 0 = persistent loop (default 60s), crash-resilient (_cycle in
try/except), SINGLE-INSTANCE LOCK (data/executor_heartbeat, refuses 2nd live instance). Running
detached (pythonw) + Startup\QuantExecutor.bat (auto-start on login). Confirmed heartbeat advancing
(real-time alive). Dashboard server also detached+Startup. To stop: data/CRYPTO_KILL. All green.

LIVE NOW: forward **shadow** (zero capital) via `scripts/run_shadow_forward.py` (frozen lb7/q20/b02),
daily Windows task **QuantShadow** 02:30 (refresh liquid lake -> shadow -> scoreboard); logs OI
forward. Dashboard: **http://localhost:8080/research.html** (scoreboard + shadow track). Decision
rule in `docs/KILL_THESIS.md`: accumulate 90d -> promote tiny-live only if fwd Sharpe>=0.5 & clears
RC with live data, else kill; never re-tune to pass. Default capital = factor/trend ETF benchmark.
Crypto data: `scripts/ingest_crypto.py --universe liquid`. See [[quant-platform-v1]].

FACTORY GOVERNANCE + FREE ETF EXPANSION (2026-06-22): built `libs/factory/registry.py` (dataset
registry+ROI, 10 edge-families x target 3, Sharpe milestones, paid DEFERRED-no budget) +
`scripts/run_factory.py` -> web/factory.json (leaderboard by PORTFOLIO CONTRIBUTION, family breadth,
milestone path+bottleneck, rejection->seeds, free dataset queue) + `web/factory.html` + wired into
QuantDaily; 29 tests green. FREE ETF CFDs ingested (`scripts/ingest_etfs.py`: TLT/IEF/SHY/LQD/EMB +
8 sector SPDRs + QQQ/EEM/GDX/UNG/SMH/CIBR/SKYY) -> rates_trend/curve_rv/credit_rv/sector_rotation
sleeves. RESULT they DON'T clear: rates_trend -1.2 (ETF CFDs are PRICE-ONLY -> dividend drag corrupts
bond ETFs), curve/credit/sector ~0; portfolio 0.66->0.58 (drag). HONEST STATE: portfolio Sharpe
~0.58, 0/10 families mature, gap to 1.5 target = +0.92. Free data largely mined. Remaining free
levers (marginal, queued): disaggregated/TFF COT, FX carry from ECB/Treasury rate diffs, day-of-week
seasonality, realized-vol timing. Assessment: **1.5 not reachable on free MT5 data** (free caps
~0.6-0.8); NOT recommending paid yet (free not 100% exhausted) per directive.
