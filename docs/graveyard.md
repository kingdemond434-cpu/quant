# Graveyard — rejected hypotheses (do_not_repeat)

Every entry is permanent. Never re-test an identical hypothesis; a *materially new* mechanism or
dataset is required to reopen a class. Tags feed the EV-gate priors in `alpha_economics.py`.
Machine copy: `web/discovery.json`. Companion: [[institutional_knowledge]].

## CODE / CAPABILITY RETIREMENTS (L2.9 RETIRE exits, distinct from hypothesis kills below)

Dormancy-hunter RETIRE dispositions land here with a written mechanism-of-death, per
`docs/EXECUTION_QUEUE.md` RANK 1. Unlike a hypothesis kill this is reversible in principle (the
code is recoverable from git history) but is not re-activated without a fresh external importer
appearing — reintroducing a dead import is exactly the drift this section exists to catch.

### `libs/discovery/` Alpha Discovery Factory — RETIRED 2026-07-30

**Mechanism of death:** zero external importers. `libs/self_improvement/dormancy.py`'s
`_external_importers()` (full dotted-path regex, scoped to `scripts/libs/app/api/tests`, excluding
the module's own package/tests) found 14 of the 23 modules in `libs/discovery/` — `factory.py`,
`models.py`, `signals.py`, `hypotheses.py`, `acceptance.py`, `fragility.py`, `half_life.py`,
`parameter_stability.py`, `correlation_engine.py`, `failure_dependency.py`,
`family_concentration.py`, `pools.py`, `portfolio_geometry.py`, `cagr_optimizer.py` — reachable
from nothing outside their own package. They form a complete, self-contained MT5-era alpha
discovery pipeline that predates and was fully superseded by `libs.autodiscovery` (51 external
importers) without ever being wired to it or torn out.

**Disposition: RETIRE**, not MERGE — `libs.autodiscovery` already re-implements the equivalent
capability with its own validation stack (CSCV/Romano-Wolf, lockbox holdout, campaign FDR); there
is nothing here worth folding in.

**What survived (7 modules, genuinely alive via non-factory callers):** `capacity.py`,
`tail_risk.py`, `monte_carlo_survival.py`, `objective.py`, `regime_diversification.py`,
`stress_scenario.py`, `research_roi.py` (plus `errors.py`, a dependency of `capacity.py`). These
were individual utility functions other subsystems adopted directly, independent of the factory
that originally housed them — `libs/discovery/__init__.py` now exports only these 7.

**Verification before deletion:** whole-repo grep for every dead module's full dotted path found
one hit outside the package's own tests — `tests/research/test_capacity_policy.py`'s
`test_acceptance_no_longer_carries_its_own_flat_floor`, which did source-text inspection of
`libs.discovery.factory` (not a functional dependency). That test was removed rather than
retargeted: the property it guarded ("the flat $100k floor is not back") is trivially true forever
once the module carrying the floor no longer exists.

**Test suite change:** `tests/discovery/test_factory.py`, `test_hypotheses_signals.py`,
`test_optimizer_acceptance_pools.py` deleted wholesale (exclusively covered retired modules);
`tests/discovery/test_robustness_engines.py` trimmed from 14 tests to the 7 covering survivors.

**RESURRECTION NOTE (2026-08-11):** 12 of the 14 retired files plus the 3 deleted test files
came back on disk without any re-adding commit — a lineage-merge resolution (present again by
`40c0777`'s first parent, 2026-08-09) restored them, the same merge-union class as the `8e8ea23`
CI incident. Re-census confirmed zero new consumers; re-deleted 2026-08-11 by the owed-work
worker. TWO EXCEPTIONS now live legitimately: `portfolio_geometry.py` and `cagr_optimizer.py`
gained a real production consumer after the retirement (`scripts/run_geometric_review.py:41,46`)
— exactly the "fresh external importer" this section names as the lone re-activation condition,
so those two are un-retired on the record. `__init__.py` was already in its post-retirement form
and is unchanged.

### `libs/alpha_factory/feature_drift_engine.py` — RETIRED 2026-08-11

**Mechanism of death:** a 30-line wrapper around
`libs/self_improvement/drift_detector.population_stability_index` with zero importers anywhere
(production, tests, or its own package `__init__`) and no commit since the 2026-07-16 baseline.
The capability it wrapped is alive twice over: `drift_detector` itself, and the wired
distribution-shift screen `libs/research/dist_shift.py` (the only mode of that family sanctioned
for wiring — capability hunt s3 2026-08-01: DRIFT is overpowered at large n). **Disposition:
RETIRE** — re-activation condition per this section: a fresh external importer with a reason the
two live supersessors cannot serve.

**Kill-basis rule (2026-07-12, round-2 external review):** every kill must record its BASIS —
`economic` (mechanism/statistics falsified: permanent) vs `data/infra` (killed by a broken feed,
outage, or collection bug). An infra-killed hypothesis is NOT permanently dead: it becomes
re-testable once the specific infra defect is verified fixed. Existing entries below are all
economic kills unless noted.

| Hypothesis | Verdict | Tag | Lesson |
|---|---|---|---|
| short_term_reversal (xsec) | Sharpe −1.41; gross −0.48 (unprofitable at ZERO cost) | `wrong_sign` | positive IC ≠ tradeable P&L — IC lived mid-distribution |
| btc_leadlag | Sharpe −2.28; gross negative | `wrong_sign` | same IC trap |
| funding_momentum | −1.72; dragged portfolio (incr −0.08) | `costs_killed_edge` | dropped from perp book |
| illiquidity_premium | 0.0, IC −0.043 | `no_economics` | |
| xsec_lowvol | −0.83 — low-vol anomaly INVERTS in crypto | `wrong_sign` | lottery demand: high-vol wins; do NOT flip sign (p-hack) |
| cross-exchange funding dispersion | −5.28, corr 0.54 to carry | `no_economics` | reusable asset: multiexchange.py |
| Fear&Greed timing | −0.56 vs hold 0.73 | `no_economics` | display-only regime indicator |
| oi_divergence (hourly bt) | −1.21, 5/9 gates | `overfit` | forward clock continues (data still accruing) |
| ls_contrarian | bt 9.84 (!) — DSR killed it | `overfit` | fat Sharpe is a red flag, not a green one |
| vol-target overlay | Sharpe 1.40→1.07 — HURTS | `regime_artifact` | carry edge is vol-correlated; de-levering high vol cuts the good periods |
| options VRP | best IC of campaign (+0.06) but breadth 2 | `no_breadth` | real signal, starved — revisit only with more vol markets |
| breadth re-add (lowvol+reversal 2026-07-04) | reverted same day | `overfit` | combiner zero-weighting losers ≠ improvement; graveyard functions are not spare parts |
| trend_regime_gated (challenger) | EV gate REJECT p~7% — running anyway on principal override, day 0/90 | `regime_artifact`? | pre-registered; evidence will settle it |
| kama_squeeze (TTM squeeze + KAMA(10,2,30), canonical, principal-override 2026-07-11) | Sharpe 0.16, 4/9 gates, PBO 0.77, RC p 0.34 | `crowded` + `no_economics` | squeeze timing UNDERPERFORMED the raw KAMA baseline (0.16 vs 0.20 — both dead): vol compression is real but its direction is a coin flip; retail-canon signals arrive pre-arbitraged. EV gate's 1.6% prior vindicated |

**Standing conclusion (breadth campaign):** free-data price-only alpha is mostly dead; funding/carry
is the lone repeat survivor. The lever is genuinely-new data + validation time, not more sleeves.
| tftrailbreakout (TF Donchian20 + 10% trail) | annSh 0.82, 6/9 gates, max_corr 0.91 vs trend book; EV 0.0003 | `wrong_orthogonality`/crowded | tested 2026-07-19: trailing-stop exit does NOT rescue breakout -- redundant trend exposure (price_only+crowded), not a new stream |
| tfatrexitbreakout (TF Donchian20 + ATR14x3 Chandelier) | annSh 0.94, 7/9 gates, max_corr 0.91; EV 0.0004 | `wrong_orthogonality`/crowded | tested 2026-07-19: ATR/Chandelier exit marginally higher raw Sharpe but same 0.91 corr vs trend + crowded price-only -> reject |
| dex_cex_volume_ratio_flow | EV 0.0039 (p_survive base rate, no prior applies) | `no_economics`-adjacent | EV-gated 2026-07-19 pre-research (alpha map "DEX volume ?" branch): DEX/CEX volume-ratio flow signal has no strong pre-registered economic mechanism, base survival rate alone leaves it well below threshold -- reject before spending research hours |
| stablecoin_mint_burn_supply_signal | EV 0.0005 | `narrow_breadth` | EV-gated 2026-07-19 (alpha map "Mint/burn ?" branch): few stablecoins issue at meaningful scale (breadth~6) AND adjacent to the already-running stablecoin_flows family (orthogonality low) -- double-penalized, reject before research |
| btc_correlation_regime_carry_conditioning | EV 0.0003 | `regime_artifact`-adjacent | EV-gated 2026-07-19 (alpha map "BTC-correlation regime ?" branch): a conditioning overlay on the EXISTING carry book, not a new stream -- same structural class as the rejected vol-target overlay (Sharpe 1.40->1.07, HURTS) and the rejected FRED macro overlays; est_sharpe=refinement-not-new-stream scores low by design |
| coinbase_premium_timing | in-sample Sharpe 2.7 BUT contamination corr(z, same-day BTC ret)=+0.256; premium std 0.06% (USD~=USDT arbitraged flat) | `timing_artifact` | high Sharpe on a near-zero-variance venue premium is close-timestamp microstructure, not institutional flow -- the collapsed-variance red flag again. De-contamination check now mandatory on every premium screen. |
| try_premium_timing (Turkey capital-control) | IC -0.063, weak; de-contam same-day corr -0.495 | `timing_artifact` | best kimchi-analog tested and it FAILS: TRY premium std 0.23% (Korea 1.42%) is dominated by FX-close-timing noise; Turkey arbs global more tightly than Korea. Kimchi is RARE, not a generic regional-premium pattern. |
| bithumb_kr_premium_lookahead | IC 0.72 / momentum Sharpe 10.0 (!) -- shift-test: IC stays ~0.7 at +1d shift too | `lookahead_artifact` | Bithumb 24h candle is timestamped at KST-day open (15:00 UTC prior day), so its close sits ~1.6d AHEAD of Binance's UTC close -> the premium mechanically contains future price. Caught by the NEW hardened-harness rail (|IC|>0.35 or best Sharpe>6 -> SUSPECT-LOOKAHEAD). The 'too good' Sharpe was the tell, exactly like ls_contrarian 9.84. Timezone alignment now a standing hazard on any non-UTC venue candle. |
| coinone_kr_premium | IC 0.051, revSh 1.74, de-contam clean -- but SAME Korea axis as kimchi (z20 corr high) | `redundant` | Correctly aligned + passes the gate, but it is the kimchi/Upbit Korea-premium signal from a 3rd venue, not orthogonal-new. Value = corroborates kimchi's realness; NOT a separate clock. |
| bitbank_jp / mercado_br premiums | bitbank IC -0.06 (noise, + JST-candle timezone risk); mercado SCREEN-WEAK, same-day -0.27 | `no_economics`/`weak` | Japan premium near-zero (freer capital flows, std 0.37%); Brazil rejected. Regional-premium class is now exhausted: kimchi is the lone survivor across KR/JP/BR/TR/Coinbase tested. |
| multilingual_wikipedia_attention (en/ja/ko/ru/zh BTC pageviews) | all 5 SCREEN-WEAK: IC 0.01-0.065, best timing Sharpe <0.35; same-period 0.01-0.08 | `no_edge_daily` | Retail attention per language population (different geographic user bases) is GENUINELY orthogonal (same-period corr ~0.01-0.08) but NOT predictive at daily horizon -- attention co-moves with, does not lead, daily returns. Kills the whole multilingual-search-trends category as a daily timing signal (Baidu/Naver/Google Trends would be the same). May be a weekly conditioning feature at best; do not re-test as daily alpha. |
| era_inout_regime_rotation ("port Quantopian In&Out risk-off rotation to crypto") | the era community's OWN decomposition: bonds out-leg contributed +123% (~6.5%/yr) of the 942% total; swapping out-leg to short-SPY collapses returns (out-signal precision too low to bet directionally, max ~60% then decays); ±1 parameter step costs 25-40% of total return; two "same-idea" variants diverge 2x YTD | `economic` + era-evidence | PRE-EMPTIVE kill, mined 2026-07-28 from Wayback `quantopian.com/posts/new-strategy-in-and-out` (108 posts, Oct-Nov 2020, EN frontier miner session D). The thread ITSELF proved the timing alpha thin and the out-leg CARRY the sauce ("the signals are really just finding when to get into bonds" -- Whitnable). Crypto translation: the out-leg = stables + funding yield, which the desk's carry book ALREADY harvests; the residual timing layer is exactly the overlay class killed 3x here (FRED macro overlays, vol-target overlay, btc_correlation_regime conditioning). Do not re-test as a rotation strategy. Only residual worth a future look: risk-appetite PAIR-RATIOS (gold/silver, XLU/XLI, FXF/FXA -- common-factor-cancelling construction, Vladimir's intersection form) as candidate FEATURES for an existing regime model -- weak prior at daily horizon (24/7 arbitrage; cf. multilingual_wikipedia kill above), must clear novelty vs the FRED-overlay kills before any screen. Era lesson transferred to inbox #71 (signal-source precision beats liquidity). |
| defi_health (DefiLlama total TVL / DEX volume / protocol fees) | all SCREEN-WEAK: IC -0.01..+0.02, timing Sharpe <0.55 | `no_edge_daily` | DeFi activity/health aggregates are orthogonal (same-period ~-0.03) but carry no daily-horizon timing edge -- same 'activity' family as the on-chain n-transactions/fees/mempool metrics that also died. DEX volume ~ generic activity, already proxied. Don't re-test. |
| era_ta_indicator_stack_crypto (EMA/RSI/MACD/ADX/Ichimoku stacks on BTC, the 2013-14 retail canon) | PRE-EMPTIVE KILL from a public 2013-14 natural experiment, not a desk backtest. Bitcointalk "Automated Trading Contest" (topic 261086, 301 posts, CryptoTrader.org platform, rounds #1-#5): **when entries were submitted BEFORE the evaluation window (rounds #2-#3, pre-registered forward), 0 of 8 submissions beat buy-and-hold** (best entrant 1029.81 vs B&H 1058.33 on a $1000 base; organizer: "Again, buy and hold strategy generated highest profit"). **When the SAME community, platform and strategy families were scored on an IN-SAMPLE backtest over an already-completed year (round #5, 2013-01-01..2014-01-01, submissions open until 12/01), 6 of 8 beat B&H and the winner returned 228x** ($5,000 -> $1,140,904 on Ichimoku vs B&H $296,501 = 3.85x B&H) | `overfit` + `crowded` | THE CLEANEST PUBLIC IN-SAMPLE-vs-FORWARD NATURAL EXPERIMENT THE DESK HAS FOUND. Same platform, same people, same asset, same indicator families -- the ONLY variable changed was whether scoring was pre-registered-forward or in-sample, and it flipped the entire result set. Independently corroborates the desk's own 420-price-hypotheses/0-survivors record via a completely separate 2013-era path, and validates pre-registration + forward clocks as the load-bearing control (not DSR/PBO alone). Contemporary poster Coldstuff (#285) also flags the uncosted second-order defect: winning backtests traded size that "could have pushed the market $20 or $50 each way" on 2013 MtGox -- zero market-impact model. Do NOT re-test the retail TA-indicator family; and treat ANY leaderboard/backtest-scored external result as in-sample until pre-registration is proven |
| era_grid_ladder_vol_bot (laddered grid bot harvesting range oscillation, MtGox EUR/BTC 2012) | Real-money, publicly-reported era instance: GMVT-BOT (Bitcointalk topic 95760, ran ~Jul-Dec 2012, IPO'd as a security, **CLOSED**). Operator's own published numbers: 0.6-0.8%/wk gross ONLY in high volatility, "usually less than 0.5%" -- against MtGox fees of 0.6%/trade (0.55% above 100 BTC volume). Operator's claim "never makes a loss" is the tell | `no_economics` + `costs_killed_edge` | The grid/ladder family's P&L is a SHORT-GAMMA volatility-risk premium with a bounded gain and an unbounded inventory tail, dressed as "riskless": every round-trip books a small realized profit while the loss accumulates silently as inventory when price trends out of the ladder. The operator states the failure mode himself ("if price goes below 3 EUR/BTC there will be a decision... or close down"). Fee stack ate most of the gross even in the good regime. Era-provenance kill: the desk should not spend a cycle re-deriving grid-bot economics |
| era_crossvenue_fiat_premium_arb (harvesting a persistent cross-venue price premium as "riskless" arb) | Two documented era instances, both ending badly. (a) MtGox<->BTC-e, Bitcointalk topic 171349 (2013): OP claims 7% gap / ~3% cost = 3% edge; reply-chain refutes it -- full fee stack is 3.3% best / 5.2% worst (post #37), and the true binding constraint is fiat-rail transfer time + payment-processor reserves (#39, "Gox had low OKPAY reserves"). (b) "Bitcoin Arbitrage Fund", topic 330209 (2013): 8-20% China/abroad gap, but the OP states the edge IS access -- "as Shenzhen citizens we have several bank accounts in Hong Kong" -- and later reports the spread decaying ("getting small, it will make our fund more difficult to operate"). (c) THIRD, MOST EXPLICIT INSTANCE — topic 339040 "Flying to China to Arbitrage 100-500k" (2013-14): the operation's actual steps were selling on BTCChina then **physically flying cash to Hong Kong**, because participants state the binding limits outright — *"u are not allowed to bring more than someting like 20k rmb out of the country"* (#13) and *"As a foreigner, you can get an Alipay account, but you can't withdraw more than CNY 2k without being verified (which requires a Chinese ID)"* (#7). The premium was a LOGISTICS-AND-PERMISSIONS problem, not a trading one | `no_economics` (as arb) / **mechanism-reclassified** | A cross-venue premium that PERSISTS is rent on a capital-control / withdrawal / counterparty barrier -- it is compensation, not inefficiency, and it is only harvestable by whoever holds the specific rail access. The 2013 Gox premium was the market correctly pricing withdrawal-insolvency risk; anyone "arbing" it was collecting a risk premium while accumulating balances at an insolvent venue, and it went to zero in Feb 2014. DIRECTLY RELEVANT TO THE LIVE KIMCHI CLOCK: this era evidence EXPLAINS the desk's own KR/JP/BR/TR result set (kimchi survives, Japan/Brazil/Turkey die) -- premium magnitude tracks BARRIER HEIGHT, and it is why kimchi must be used as an information/timing signal (which the desk does) rather than sized as an arb (which the desk must never do) |
| commit_velocity_dev_momentum (cross-sectional, 35-asset survivorship-aware L1s, 1/3/6mo) | 1mo CS-IC -0.018 (t -0.68); 3mo +0.033 (t 1.21); 6mo +0.014 (t 0.55), 6mo L/S NW-t 1.53 -- NONE clear |t|>=2 | `insignificant` | The CORRECT test of the Electric-Capital thesis (ecosystem selection, not BTC timing; forward RELATIVE return; winners+slow-survivors+dead L1s to kill survivorship bias; monthly N not obs-N). Direction is thesis-consistent at 3/6mo (positive) but insignificant; raw commits = weakest proxy. RETENTION/MIGRATION escalation PRE-REGISTERED below -- do NOT fish more commit-count variants (multiplicity). |
| cm_mvrv_btc_daily_level (Coin Metrics CapMVRVCur, 20d-z level → next-day BTC, 2010-07→2026-05, n=5,767) | Stage-A TIMING-ARTIFACT: raw IC +0.046 and momentum Sharpe 1.18 clear the floors, but same-period corr 0.416 >> 0.20 contam bar — the 20d z-score of a PRICE-NUMERATOR ratio is largely recent momentum in disguise (market cap = price×supply sits in the numerator, so the z co-moves with the very returns it "predicts"). Alignment declared: CM daily rows = EOD UTC day t, signal(t)→ret(t+1), live availability lag ~2h past midnight (flash status observed 01:44Z t+1) | `timing_artifact` | ONE construction tried, one verdict, logged (charter §26.3). NOT a kill of the cost-basis mechanism itself: residual IC 0.039 SURVIVES orthogonalization to same-day returns (does not collapse below half of raw), and the mechanism is inherently slow — the honest escalation is a PRE-REGISTERED weekly-horizon / realized-cap-orthogonalized construction on a proper clock slot, never a same-run screen re-roll. Any future price-numerator ratio (NVT, Mayer multiple, price/realized-price) screened at daily 20d-z will hit this same contamination by construction — orthogonalize FIRST or screen at the mechanism's native horizon. Data: free CM community CSV (CC BY-NC — licence ruling pending for production use). |

---

## EXTERNAL-LITERATURE PRIORS (added 2026-07-26, literature deep-miner run 3)

**A THIRD KILL-BASIS, declared explicitly so it is never confused with the desk's own evidence:**
`external-literature`. Every row above this line was killed by the desk's OWN backtest/screen on the
desk's OWN data. Every row below was killed by somebody else's published evidence and has NOT been
independently re-run here. That is a weaker basis and it is labelled as such — but it is not a weak
REASON to skip: these are hypothesis families where a credible team already spent the multiplicity
budget and found nothing, so re-testing them buys the desk a near-certain null at full DSR cost.
Per LITERATURE_SPEC: *"A mechanism that failed replication enters the graveyard as prior, not the
queue."* Reopening any row below requires a materially new mechanism or dataset, exactly as above.

**Standing haircut prior attached to this whole section (McLean–Pontiff, JF 2016, 97 predictors):**
published predictor returns are **26% lower out-of-sample** and **58% lower post-publication**, and
decay is *larger* for predictors whose in-sample returns were *higher*. Any signal sourced from
published literature is haircut ~58% off its published effect before it is worth a slot, and more
than that if its published Sharpe was fat. The desk's own `ls_contrarian` (backtest 9.84 → DSR-killed)
is the same phenomenon observed internally.
**CRYPTO-NATIVE MEASURED INSTANCE (2026-07-31, litminer run 4 — the prior LANDS numerically):**
Man/Harvey published crypto TSMOM gross vol-scaled Sharpe **1.46–1.65** (2016–22, JPM 2022, primary
read via Duke archive); an independent 150-perp OOS 2022–24 NET re-test (arXiv 2602.11708) measures
classical TSMOM at **0.54–0.65 = −58% to −65% vs published** — McLean–Pontiff almost exactly, in
this desk's own asset class and instrument. The haircut is no longer only an equity-literature
import.

| Hypothesis (external prior) | Verdict | Tag | Lesson |
|---|---|---|---|
| lit_trading_frictions_family (the published "trading frictions" anomaly category: illiquidity, spread, volume, turnover, price-level variants) | **102 of 106 (96.2%) fail to replicate** under NYSE breakpoints + value weighting; whole-corpus failure 65% at t>1.96 and **82% at the 2.78 multiple-test hurdle** across 452 anomalies | `no_economics` / external-literature | Hou–Xue–Zhang, *Replicating Anomalies*, RFS 2020 — **primary text extracted and verified 2026-07-26** (not a summary; three numbers previously recorded from a search summary were WRONG and are corrected here). The desk's own `illiquidity_premium` kill (IC −0.043) was not bad luck — it is the MODAL outcome for the single worst-replicating category in the entire published anomaly literature. Do not reopen frictions-family variants. Mechanism: the original spreads are microcap-borne and equal-weighting-borne — real in the data, untradeable at size. **PER-CATEGORY BREAKDOWN (extracted 2026-07-26, NYSE-VW single test / multiple test at 2.78): Investment 73.7% / 50.0%; Momentum 63.2% / 49.1%; Profitability 44.3% / 17.7%; Value-vs-growth 42% / 10.1%; Intangibles 25.2% / 10.7%; Trading frictions 3.8% / 1.9%.** Recorded so the kill is not over-read: **investment and momentum are the ONLY categories that survive** — everything else fails at 82%+ under multiple testing. For THIS desk that residual is mostly unreachable: price-only momentum is already dead on desk data (420/0 + the era natural experiment), and 'investment' is an accounting characteristic with no crypto analogue for most assets. So the honest reading is *the equity literature's surviving signal does not transfer here*, not *the desk should go test investment factors*. |
| lit_crypto_xsec_size_and_volume (published crypto cross-sectional size/volume anomalies) | Spreads "originate from micro-cap coins of negligible economic importance"; crypto momentum's alpha "extracts... largely from short positions"; "most abnormal returns occur primarily in bull markets and fade over time" | `no_economics` + `regime_artifact` / external-literature | Fieberg–Liedtke–Zaremba, *Cryptocurrency anomalies and economic constraints*, IRFA 2024 (RePEc abstract, verbatim). Three independent mechanisms of death on the same family, and this is the CRYPTO restatement of the HXZ microcap finding by a different team. A long-biased, liquid-universe, cost-honest book captures approximately NONE of the published crypto cross-sectional spread — which is the external explanation for the desk's own 420-hypotheses/0-survivors record. **CORROBORATION ADDED 2026-07-31 (litminer run 4):** Li & Zhu, *Taming crypto anomalies: A Lasso-type factor model*, RIBF 83 (2026), DOI 10.1016/j.ribaf.2026.103298 — published-version abstract read VERBATIM via IDEAS/RePEc (`ideas.repec.org/a/eee/riibaf/v83y2026ics0275531926000255.html`, same provenance class as this row's own admission): *"there are noticeable changes in the behavior of out-of-sample anomalies. This includes the disappearance of size effect"*; their replacement DS3 model (MKT + MOM2 + RMOM) contains NO size factor. Two independent crypto teams now reach size-death by different routes. Held provisional and NOT recorded here: the "13 of 49 anomalies significant" figure and exact IS/OOS split dates — those are interior-level and the interior remains unread (SSRN delivery + ScienceDirect both 403 from this box, NK-005). DATED CAVEAT: this row's 420/0 cross-reference predates the 2026-07-30/31 finding that the 420/0 record was partially an instrument artifact (welded gate, L1.25); the kill itself stands on the papers' own content, not on the desk's campaign record. |
| lit_defi_tvl_crosssection (TVL level AND **change in TVL** as a cross-sectional crypto return predictor, weekly) | 335 coins, 2023-01→2024-12: TVL-sorted alphas all p>0.13; overstatement-adjusted TVL p>0.46; **ΔTVL p>0.40**; GRS F-tests fail to reject zero alphas throughout (p 0.35–0.99) | `no_economics` / external-literature | Brigida (2025), arXiv 2506.03287 (full HTML read). CLOSES THE SECOND AXIS on the desk's own `defi_health` kill: the desk killed TVL at the daily BTC-timing horizon, this kills it cross-sectionally at weekly INCLUDING the change-in-TVL construction the desk never ran. Load-bearing bonus: headline TVL is mechanically OVERSTATED by staking/pool2/governance-token/borrowing/liquid-staking/vesting double-counts, so a vendor TVL *level* must never be trusted as a quantity. |
| lit_bruteforce_ratio_mining (mechanically generating large families of accounting/price ratio strategies and keeping the significant ones) | 2.1M strategies generated; "most rejections of the null of no outperformance under single hypothesis testing are likely false"; "a remarkably small number of strategies survive... **Even these surviving strategies have no theoretical underpinnings**" | `overfit` / external-literature | Chordia–Goyal–Saretto, *p-Hacking: Evidence from Two Million Trading Strategies* (SFI RP17-37, verbatim abstract). The closest published analogue to what a mechanical screening loop IS. Strongest external argument for the desk's mechanism-first gate: **statistical survival without a mechanism is not evidence** — the survivors of a brute-force search have no mechanism and therefore will not survive forward. Widely-quoted specific thresholds (|t|>3.79 etc.) are SUMMARY-ONLY and deliberately NOT recorded here. |
| lit_retail_signal_families (the five widely-promoted retail signal families as a class: trend, oscillator, candlestick, volume, and calendar rules) | Tested against **three PRE-DECLARED gates -- statistical edge after multiplicity correction, economic viability after costs, and finite-bankroll survival under leverage** -- with exposure-matched benchmarks, stationary-bootstrap CIs, hierarchical Benjamini-Yekutieli control, one-sided claim-exclusion tests and equivalence tests. The paper's own framing is that practical viability is the CONJUNCTION of all three, and its title states the finding | `crowded` + `costs_killed_edge` / external-literature | *Retail Trader's Ruin: An Anatomy of Popular Signal Failure*, arXiv:2607.20093 (2026-07-22) — abstract read verbatim from the feed inbox 2026-08-06; INTERIOR NOT READ, and the row claims only what the abstract states. **WHY IT IS WORTH A ROW RATHER THAN A SHRUG: the methodology is this desk's own, arrived at independently.** Multiplicity correction, cost-honesty and a ruin gate are exactly the desk's DSR / execution-physics / L1.23 triple, and an outside team applying them to the retail canon reaches the same place the desk's own 420/0 campaign did. **THE REUSABLE HALF is the CONJUNCTION, not the verdict:** three gates ANDed is why the retail canon dies — each family clears one or two and none clears all three, which is precisely how a signal survives a blog post and fails a desk. Do not re-test any of the five families; the desk already killed `kama_squeeze` (retail-canon squeeze timing, Sharpe 0.16) and the whole price-only breadth campaign on its own data. |
| lit_candle_ml_timing_crypto (candle/OHLCV machine-learning models predicting crypto extrema or short-horizon outcomes, traded as a spot timing policy) | "The strongest later-period evidence, conditional on extensive predecessor search, is negative" — candle-based ML predictions of extrema do NOT convert into positive Binance **Spot** paper policies after assumed costs | `costs_killed_edge` + `overfit` / external-literature | *Predictive Extrema, Unprofitable Policies: An AI-Assisted Audit of Candle-Based Binance Spot Timing Models*, arXiv:2607.19453 (2026-07-21) — abstract read verbatim 2026-08-06; interior not read. **THE DISTINCTION THAT MAKES THIS A KILL AND NOT A SHRUG, and it is the desk's oldest recurring trap:** the models PREDICT (extrema are genuinely forecastable to a degree) and the POLICIES still lose. That is `short_term_reversal`'s "positive IC ≠ tradeable P&L" and `oi_divergence`'s IC trap, restated by an independent team on the desk's own venue and instrument class. Same venue (Binance), same bar type (candles), same conclusion the desk reached on its own data. **DO NOT SPEND A FORWARD SLOT ON AN OHLCV-ONLY CRYPTO TIMING MODEL**; the standing breadth-campaign conclusion at the head of this file already says free-data price-only alpha is mostly dead, and this is an outside replication of it. Held provisional: fixed-seed scripted runs with AI-assisted evidence integrity is a weaker provenance than a peer-reviewed replication, so the row's WEIGHT is "corroborating prior", not "decisive". |
| lit_prediction_market_microstructure_vs_book (forecasting a binary prediction-market outcome from the paired venue's microstructure, i.e. Polymarket BTC 15-minute up/down markets predicted from Binance BTC/USDT order flow) | Out-of-sample, a walk-forward logistic over **43 microstructure features does not beat — and slightly underperforms — the probability already implied by Polymarket's own order book**; simulated trading nets **−0.116 normalized payoff units per attempted trade** under the authors' stated fee and slippage assumptions | `no_economics` / external-literature | Young, *OpenMarket: A Synchronized Polymarket-Binance Dataset for High-Frequency Prediction-Market Research*, arXiv:2607.26245 (2026) — abstract read VERBATIM first-hand from `arxiv.org/abs/2607.26245` on 2026-08-06, HTTP 200, not a search summary. **MECHANISM OF DEATH, and it is the reusable half: the order book you are trying to beat is the aggregator of the very flow your features are derived from.** Binance order flow reaches Polymarket market-makers too, and they quote on it; a microstructure feature set is therefore a *lossy re-derivation of a price that already contains it*, and it can only lose by the width of its own approximation error plus fees. That is the null the −0.116 measures. Beating a prediction-market book requires information the book has NOT already seen — not a better-engineered restatement of information it has. **THIS IS AN AUTHORS'-OWN-NULL, published as the paper's central result**, so the McLean–Pontiff publication haircut at the head of this section does NOT apply in the usual direction: there is no inflated in-sample effect to discount, and the usual survivorship worry (nulls go unpublished) is exactly what makes this row cheap knowledge — the desk would otherwise have paid full DSR cost to rediscover it. **DO NOT REOPEN** by swapping the feature set, the model class, or the horizon: all three vary the approximation, none of them changes the mechanism. **WHAT SURVIVES THE KILL (and is why the corpus is still registered):** the paper's clock work, banked at `docs/research/openmarket_corpus.json` — three declared clocks per row, a stated **±99 ms single-vantage constant-offset ambiguity**, and a synchronization-free 347 ms event study on the collector clock alone. |

**RESOLVED 2026-07-31 (was: held back deliberately since 2026-07-26):** Li & Zhu, *Taming crypto
anomalies* was held out of the graveyard for two runs because its numbers reached the desk only
through a search index. The OP-026 ladder closed it: the PUBLISHED-version abstract (RIBF 83, 2026)
was read verbatim via IDEAS/RePEc — the same provenance class on which row 2 (Fieberg) was admitted
— and its size-death claim + no-size DS3 model are now recorded as CORROBORATION inside row 2 above
(one family, one row; a fifth row would have double-counted the same kill). What stays provisional,
still honestly un-pasted: the "13 of 49 significant" figure and the IS/OOS split dates (interior
never read; SSRN Delivery.cfm AND ScienceDirect abstract page both 403 from this box — NK-005's
scope now confirmed to include SSRN's direct PDF delivery route, not just abstract pages). The
abstention discipline worked as designed: nothing entered the graveyard until an author-written
text was read through a legitimate route.

---

### era_crossvenue_fiat_premium_arb — FOURTH INSTANCE (CN 2017, primary text) — CORROBORATED + MECHANISM REFINED
_CN frontier miner, 2026-07-26. Basis: `economic`. Not a new kill — a fourth independent era instance
of an already-dead class, added because it supplies the mechanism detail the other three lacked._

**SOURCE (dead-forest, Wayback-only).** `8btc.com/thread-53689-1-1.html` — 「P网搬砖简明指南（以及一种
交易策略）」("Concise guide to Poloniex banzhuan (and a trading strategy)"), 巴比特/8btc BTC forum,
posted 2017-05-02, capture `20171019172042`. 8btc.com, chainnode.com and Baidu Tieba are ALL
unreachable from this box — this ground exists only in the archive. Mined to reply-depth: OP + replies
at depth 1 and 2 (quoted-reply chains), 7 substantive posts.

**WHAT THE ERA TRADERS ACTUALLY DOCUMENTED.** The 2017 bull began on foreign venues (Poloniex 「P网」,
Bittrex 「B网」), so domestic venues (比特时代 BTC Trade, 云币网 Yunbi — collectively 「果盘」) lagged by
**up to 10%**. The OP states the binding barrier outright: **domestic platforms could not withdraw BTC**
(「国内不能提比特币」) — which is *why* the domestic price sat below the foreign price. Claimed economics:
gap >10%, net **~3% after fees**, called 「无风险获利」(riskless profit).

**WHY THIS IS THE SAME KILL, NOT A NEW EDGE.** Identical to the three instances already recorded: the
premium is rent on a withdrawal/permissions barrier, harvestable only by whoever holds the rail. The
replies make the permissions barrier explicit — Poloniex **did not accept mainland registrations**, so
the workaround was to **select "Hong Kong" as your country** (post #3), and KYC tiers capped you at
$2,000 until you uploaded ID to reach $25,000 (posts #5/#8). Same shape as the 2013 Bitcointalk
「fly the cash to Hong Kong」 instance: a logistics-and-permissions problem wearing a trade's clothes.

**THE NEW DETAIL — HOW THE ARB ROUTED *AROUND* THE BARRIER.** The other three instances never explained
how anyone transacted at all under a withdrawal freeze. This one does: **BTC was frozen, altcoins were
not.** The trade moved value on the fastest-confirming altcoin rail — XRP 瑞波币 is the worked example,
with XLM 恒星币, ZEC, SC and NEO 小蚁股 named at depth (post #9). The OP explicitly warns **using BTC
itself works badly, especially during network congestion**. So the barrier was asset-specific, and the
arb survived exactly as long as *some* asset had an open rail.

**THE PART THAT IS STILL LIVE (routed to improvement_inbox #58, not to capital).** The OP's risk
framing is the era's name for transfer-latency risk — 「搬砖砸脚」*"moving bricks and dropping one on
your own foot"*: your value is in flight, unhedged, while the price moves. His two mitigations are
real execution doctrine and generalise to any cross-venue movement the desk makes:
  1. 天时 (right timing) — move only when the gap is large AND the transferred asset is **rising on
     30-min-or-faster candles**, so latency drift is favourable rather than symmetric;
  2. 地利 (right ground) — pick the **fastest-confirming asset and fastest-withdrawing venue**.
This is the correct instinct: in-flight time is directional exposure, and asset choice is the lever.

**AND ONE GENUINELY SHARP OBSERVATION (depth-1 reply, post #1) worth preserving.** A replier argues the
spread is the *lesser* half of the trade: with domestic BTC withdrawal frozen, domestic BTC supply is
segmented and effectively **deflationary**, while Poloniex alts are BTC-denominated — so **the
re-opening of withdrawals is itself a predictable catalyst** that would inflate foreign alt prices.
That is a capital-control *regime-change* trade, not an arb, and it is the most sophisticated idea in
the thread. Recorded here as era knowledge; NOT carded — the venues are dead, mainland rails are far
more closed in 2026 than 2017, and the desk holds no way to test a 2017-specific segmentation.

**CONNECTS TO THE LIVE 2026 RESULT.** This era's 10% gap versus today's measured CNY OTC premium std of
**0.580%** is the barrier-vs-merchant-depth finding in axis #76 (data_axis_watchlist card 9): in 2017
the rail was frozen and the premium was enormous; in 2026 the capital barrier is *higher* but a deep
professional 承兑商 (OTC merchant) network arbitrages it to a quarter of Korea's. Barrier height sets
the premium's ceiling; **merchant density sets where inside that ceiling it actually sits.**

---

### era_crossvenue_fiat_premium_arb — FIFTH INSTANCE (CN 2017, two eras in one year) — SIGN MECHANISM ADDED
_CN frontier miner, 2026-08-04. Basis: `economic`. Same dead class, fifth independent instance; added
because it supplies the one variable the rule still lacked: what sets the premium's **SIGN**._

**SOURCES (dead-forest, Wayback-only, all reply-mined ≥2 deep, GBK per OP-033).**
(a) `8btc.com/thread-50730-1-1.html` 「辣条内外盘差价高达30%，醉了」(2017-04-06, capture
`20170409041105`) — freeze-era, 14 posts, quoted chains to depth 4;
(b) `thread-74908` 「政策出台后，各位是准备提现RMB还是转外网继续持有？」(2017-09-15→23, pages 1+2, 29
posts) — 94-exodus diaspora thread;
(c) `thread-75923` 「igaowei：香港bitfinex平台，香港开银行帐户，BTC换港币，再转人民币」(2017-09-20→23,
pages 1+2) — exit-rail mechanics;
(d) `thread-72814` 「[搬砖求带]bitfinex连20个BTC都提不出来?」(2017-09-10/11) — banzhuan under exodus load.

**THE NEW VARIABLE: BARRIER *SIDE* SETS THE PREMIUM'S SIGN.** During the Feb–May 2017 PBOC withdrawal
freeze, the **coin leg** was frozen (提币 halted; fiat deposits/withdrawals still open) and the LTC
domestic/overseas gap ran to **30% with the DOMESTIC side CHEAP** — thread (a)'s depth-4 chain states
the equilibrium outright: exchanges dare not arb their own book against the PBOC (post #3), big clients
「场外卖了币买在场内」 (sell OTC, rebuy in-venue at the discount, post #5), and the closing rebuttal —
「差价那么大。请问买家在哪？」 *"at that spread, where are the buyers?"* — is trapped-capital equilibrium
in one sentence: no exit rail, no marginal buyer, discount persists. In 2013→2021 capital-control eras
the **fiat leg** is the frozen one and the domestic side trades at a PREMIUM. So the family's rule is
now three-factor: **sign = which leg the barrier freezes (coin frozen → domestic discount; fiat frozen
→ domestic premium); magnitude ceiling = barrier height; position inside the ceiling = merchant
density.** A depth-1 counter-narrative in (a) (post #10, sourced to 「相关人员」): the freeze was partly
the platforms' own choice under a KYC-traceability order, 「假币太多」 — i.e. reserve quality, not only
regulation, froze the leg. Uncorroborated, preserved as era testimony (post #13 rebuts it with Yunbi's
later fate).

**WHY THIS STAYS DEAD AS A TRADE.** Same kill as instances 1–4: both sides of the 2017 gap were rent on
a barrier only rail-holders could cross — and thread (d) adds the venue-side detail that even the OPEN
rail degraded exactly when the herd moved (Bitfinex hot-wallet depletion queued 20-BTC withdrawals for
hours on 2017-09-10; the era veteran's reply distinguishes it from insolvency). Transfer latency spikes
when everyone needs the rail at once: in-flight risk is CORRELATED with the regime event that makes the
gap attractive. The premium family is information, never arb.

**DIASPORA RECORD (dark-forest #3, primary-source answer for the 94 event).** Threads (b)+(c), posted
inside the two weeks after the 2017-09-04 announcement, document where the CN market went, by size class:
retail → 黑市/direct-to-wallet hodl (dominant vote in (b)); traders → 「B网」Bittrex and Bitfinex via the
HK rail (BTC→HKD→HK bank→RMB, with replies flagging 结售汇 settlement and physical cash-over-border as
the residual chokepoints, and one asking for JP/KR venues because HK is 「触手可及」 within Beijing's
reach); size → official USD quota at 「央妈」 then overseas, with the era's own judgment 「这部分钱估计
是不会再回来了」 (that capital never returns); and the conversion layer → OTC dealer ads forming
**in-thread within 48 hours** (QQ group 91694750, WeChat dealers soliciting fee-free conversion,
2017-09-16/17) — the observable BIRTH of the 承兑商 merchant network that by 2026 grinds the CNY premium
to 0.580% std. GFW blocking of overseas exchange sites is dated by a primary source: 2017-09-20 (「今天
所有的国外交易所的网站都被墙了」) — a barrier-height step function with a date. 「转外网」's boards are
dead but the pattern (private QQ/WeChat groups, not public boards) is the honest prior for why the 2026
OTC-discussion diaspora question keeps returning thin public ground.
| smart_dumb_divergence (elite top-trader position ratio MINUS retail account ratio) | pooled mean IC +0.0032 (t +0.15, n=5 majors, 4h, 180 bars); 0/20 per-symbol screens passed | `no_edge` | THE DIRECT TEST of the Elite-Trader-Intelligence premise ('do skilled traders lead the crowd?'). Binance topLongShortPositionRatio (elite, size-weighted) minus globalLongShortAccountRatio (retail crowd) -- the two genuinely diverge in LEVEL (66.8% vs 55.1% long) but the divergence carries ZERO forward information. The 'smart money vs dumb money' signal is a narrative, not an edge, at aggregate 4h granularity. |
| elite_account_ratio (top-trader headcount long ratio) | pooled mean IC -0.0101 (t -0.32, n=5) | `no_edge` | Elite headcount positioning carries no forward information; only the size-weighted POSITION variant showed any sign consistency (logged as a candidate, not wired). |
| hyperliquid_trader_skill_persistence (41k-address leaderboard, 8,026 filtered, formation/holding rank test) | ADJACENT windows rho +0.120 (t +10.9) BUT with a ~3-week GAP rho FLIPS to -0.064 (t -5.8); long-horizon variant -0.060 (t -5.4); gapped decile spreads insignificant (t 1.33 / 1.15) | `position_overlap_artifact` | THE foundational test behind copytrading: does past trader performance predict future performance? The apparent persistence exists ONLY when formation and holding windows TOUCH -- a trader holding one position across the boundary yields mechanically correlated PnL (an open position, not skill); BTC's mildly-trending weekly path (-5.9/+6.8/+0.2/+1.5/+1.0/-0.0%) makes persistently-long accounts look consistently skilled. Insert a 3-week gap and it INVERTS to mild reversion. Robust in the safe direction: the leaderboard is a current snapshot so blown-up accounts are ABSENT, which biases persistence UP -- true persistence is <= -0.064. Top-decile forward returns were NEGATIVE in every variant (-1.7%, -3.4%, -28.6%). Kills the 26-layer Elite-Trader-Intelligence spec at its premise: selecting past winners selects luck. Do not re-test aggregate or per-trader copytrading without a GAPPED design. |
| hl_elite_directional_order_flow (Hyperliquid, performance-blind cohorts, 4h signed taker flow vs next-bucket return) | HFT-cohort BTC IC -0.139 (underpowered, 80 bkts); DIRECTIONAL cohort (260) BTC IC +0.157 / ETH +0.056, pooled t +3.00 on n=2 -- BUT breadth re-run (320, same rule, +60 traders) FLIPPED BTC to IC -0.033 + TIMING-ARTIFACT (same-period +0.202 > 0.20 gate); ETH IC +0.110 vs tercile spread -0.524% (opposite signs); 14/16 coins too thin | `unstable_artifact`/`no_edge` | Mechanism #3 of 3 pre-registered (after aggregate-positioning t+0.15 and gapped skill-persistence -0.064 both failed). Tested the actual copytrading mechanism: does elite flow LEAD price? Designed around both circularity traps (cohort selected on VOLUME/TURNOVER, never performance; flow(t) vs ret(t+1) only). Self-caught design flaw mid-experiment: top-VOLUME selection picks HFT/market-makers (2000 fills in 30 MINUTES) whose flow is inventory not conviction -- spec layer 11's own rule -- so re-selected on TURNOVER RATIO (1-25x/mo = discretionary). KILLED BY INSTABILITY: adding 60 traders to the SAME rule inverted BTC's IC sign. A real edge does not flip under cohort perturbation. Root mechanism: taker flow is CONCURRENT with price (buying moves price) -- it fails de-contamination, it does not lead. STRUCTURAL WALL: userFills caps at 2000 fills/address (30 min for the biggest accounts), so historical breadth is impossible from the snapshot API -- only forward accumulation could build it. Do not re-test elite/copytrade flow without >=8 coins AND cohort-perturbation stability AND a gapped/de-contaminated design. |
| hl_longterm_riskadjusted_skill (229 traders, median 621d / max 1195d verified on-chain records, own-curve 60/40 formation-holding split) | formation SHARPE -> holding return rho -0.019 (t -0.28) = ZERO; consistency t +0.45; total return t +0.73; cohort holding mean -3.3%, median -11.9%, only 40% positive | `no_predictive_power` | THE strongest version of the trader-skill hypothesis, built after the principal correctly objected that earlier tests used a ONE-WEEK holding window, no track-record filter, and raw-PnL ranking. Fixed all three: multi-YEAR records, risk-adjusted selection (Sharpe/consistency/drawdown), long-horizon holding, natural gap via own-curve split, pnlHistory normalised by contemporaneous accountValue so deposits are not counted as returns. Selecting proven multi-year traders by past Sharpe has ZERO forward predictive power. ONE PARTIAL EXCEPTION worth keeping: DRAWDOWN CONTROL persisted (rho +0.135, t +2.05; top-quartile holding +2.3% vs bottom -18.0%) -- does NOT clear the 4-test multiplicity bar (~2.5) so not an edge, but consistent with the classic finding that RISK characteristics persist while RETURNS do not. Also settles the 'dig deeper / Chinese / niche verified traders' objection: HL on-chain records are the STRONGEST available evidence class (cryptographically verifiable, losers included); self-reported or platform-curated track records are strictly weaker, and enlarging the search pool AMPLIFIES the winner's curse (max-order statistic gets more luck-dominated as N grows). |
| ltw2022_crypto_momentum_nonreplication_claim (CN course-replication of Liu-Tsyvinski-Wu, J.Finance 2022) | GitHub YungFuu/Cryptocurrency-trading-strategy-replication (39★, HKU MFIN7037, 2022) + its issue #1: author reports "some momentum factors insignificant"; independent replicator LeoLi2002 reports momentum non-replication AND an EW-vs-VW significance/sign flip. FORENSICS (CN miner s2, 2026-08-04, code read in full): the momentum functions bin with **`pd.cut(week_ret_lagN, bins=5)` — equal-WIDTH bins over fat-tailed weekly crypto returns** (the size functions correctly use `pd.qcut`), so "Q5−Q1" is a moonshot-outlier detector, not a momentum quintile spread; AND the selection helper reassigns from the full panel (`data = df[df.mcap>1e6]` overwrites the week filter), fitting bin edges on pooled history = look-ahead edges + cross-week name pollution; AND the author's stated method is post-hoc sign selection (「只要显著…根据系数正负采取做多做空」). All 8 forks are same-day classmate snapshots, zero divergence. | `replication_invalid` — kills the CLAIM, not the paper | The kill is of the NON-replication: this source is evidence about nothing, in either direction — do NOT cite it against LTW momentum (which crypto cross-sectional priors lean on), and do NOT cite its positive size-factor tables either (same pooled-bin defect). What survives the code's death is the SECOND replicator's independent EW/VW fragility report (own code, unseen) → weak_signal_registry `ltw_ewvw_significance_flip`. Genre lesson: course/blog replications state methods honestly enough to audit — audit the BINNING PRIMITIVE first (OP-047); a "failed replication" found in any region's practitioner web is a claim about the replication's method until proven otherwise. License note: repo has NO license → findings summarised, no code reused (§13). |

<!-- RESTORED 2026-08-04 (EN frontier miner): this entry was written 2026-08-01 in commit bd32eda on master, but the working tree forked to branch claude/llm-auto-upgrade-verify-gcjac3 at 3bf89cd (07-29) and the entry never reached this line — a §33 vanished-artifact instance created by BRANCH TOPOLOGY, not by an editor. Restored VERBATIM from bd32eda so the knowledge exists on the live line; the branch fork itself is rowed in the recommendation ledger this same run. -->
| exchange_netflow (Coin Metrics `netflow_ntv` / `sply_ex_ntv`, BTC 5,575d 2011-04-24->2026-07-28 + ETH 4,008d, 2 builds x 3 horizons = 12 cells) | 0/12 SCREEN-INTERESTING. Best cell btc/scaled/h=5: IC **-0.0345** with the mechanism-CORRECT negative sign, but residual IC after the angle-20 de-contamination **+0.0124 -- the sign FLIPS**. Horizon signs incoherent (btc/raw h=1 -0.0074 vs h=20 +0.0114). h=5/h=20 cells correctly SCREEN-UNDERPOWERED (overlapping windows collapse n_eff below the ~4268 independent obs the screen requires, R0030). | `no_edge` (contamination, not lead) | Mechanism tested: coins moving ONTO exchanges are supply arriving at the only venue where it can be sold, so netflow should be revealed selling intent leading weaker returns. **THIS NEGATIVE IS UNUSUALLY TRUSTWORTHY and that is the point of logging it loudly:** the axis is genuinely novel (novelty 0.973, nearest prior kimchi at sim 0.027), carries **16 years** of depth, and has the CLEANEST alignment available anywhere on the desk -- signal and target are the SAME Coin Metrics daily rows keyed by the same `date` field, so the cross-source timezone join that turned kimchi (~73% artifact) and Turkey premium into pure timing fakes is **structurally impossible** here. So this is not "unproven for want of data"; daily exchange netflow genuinely does not lead BTC or ETH. **TRANSFERABLE:** the de-contamination gate is the single highest-value component of `axis_screen` -- it caught a sign-flip that a raw-IC report would have sold as mechanism-CONFIRMING (correct sign, plausible story, 16y sample: every heuristic said edge). Do not re-test exchange-flow at daily frequency without either intraday granularity or a per-exchange (not aggregate) decomposition, and never trust a raw IC whose sign survives only before orthogonalisation. Research memory `rm-20260730T024116-185ecc`; `reports/screen_exchange_netflow.json`. |
| carry_entry_shorts_widening_basis (BR-08/R0206: funding-rank entry -> forward basis path; bronze D1 164 symbols, 2019-09-08..2026-07-31, 2 constructions x 2 horizons = 4 pre-registered cells) | **H1 REFUTED, and REVERSED.** Top-4-by-funding basis leg is **+0.65 bps/day (t +3.11)** -- CONVERGING, i.e. mildly FAVOURABLE to the short-perp leg, not widening. H2 (effect strengthens with rank) is refuted in the opposite direction, and on the NON-TAUTOLOGICAL component: the BASIS LEG ALONE improves monotonically across funding deciles (h=1 d1 -1.89 -> d10 +0.61 bps/day; h=5 d1 -4.71 -> d10 +0.91), in all four constructions. SELF-CORRECTION, recorded rather than quietly fixed: the first write-up cited NET by decile (d1 -17.8 -> d10 +7.0) as the H2 evidence, which is partly TAUTOLOGICAL -- funding is the ranking variable, so the funding leg must rise with rank. The basis leg carries no such mechanism and moves the same favourable way, which is what actually refutes H2. lag1 construction agrees throughout (+0.10 bps, t +0.59). | `mechanism_refuted` | Tested BECAUSE the ONLY deployed sleeve realised -58.27 bps net over 73 churn-free round-trips with price_pnl -51.74 bps, which for a delta-neutral pair IS the basis change and should be ~0. Proposed mechanism: Binance funding is computed FROM the premium index, so ranking by funding mechanically ranks by widest premium, and the entry might be shorting an ongoing squeeze. **It is not.** History says the extreme funding rank is the BEST bucket, not the worst, and the basis converges slightly after entry. **Therefore the live -51.74 bps is NOT a property of the entry rule** and goes back to the contamination/execution explanation exactly as the card pre-committed. THE REAL FINDING IS THE GAP: paper-gross +7.77 bps/day vs live -58.27 bps/round-trip is an L2.10 reality gap of ~66 bps that is now ATTRIBUTED TO EXECUTION, not selection -- which is where the next repair hour goes. **DO NOT CITE +7.77 bps/day AS AN EDGE:** it is gross of fees, slippage and impact, on a panel that is substantially a current-universe snapshot (the 18 symbols ending early cluster on ONE date = a collector boundary, not delistings), and the top-4 funding names are the thinnest on the venue. The SIGN and the decile MONOTONICITY are the robust parts; the LEVEL is not. Bias direction is stated in the artifact: basis measurement noise biases forward Delta-basis toward apparent convergence, so H1 was refuted despite the bias running against it being the only clean read -- the lag1 construction exists for exactly that and agrees. `scripts/screen_carry_basis_path.py`; `reports/carry_basis_path.json`. |
| era_olps_olmar_portfolio_selection (OLMAR/OLPS "follow-the-loser" on-line portfolio selection ported to crypto; Li & Hoi ICML-2012 paper 168, PAPER DEFAULTS w=5 eps=10, ONE pre-registered config, no sweep; Binance USDT-perp bronze D1, top-8 by median $vol 2023-05-05→2026-06-21 1,138d/3.12y + top-30 446d) | **DIES THREE INDEPENDENT WAYS, and NOT the way the era thought.** (1) LOSES TO THE TRIVIAL BENCHMARK AT ZERO COST: gross CAGR +11.28% vs uniform-CRP +42.24% and buy-and-hold +39.38% — a −31pp/yr deficit before a single basis point of cost (top-30: gross −29.04% vs BAH −10.67%). (2) IT IS NOT PORTFOLIO SELECTION: mean max-weight 0.991, **effective N = 1.02 of 8** — a daily single-asset rotation, exactly the collapse the paper's OWN AUTHOR (Bin Li, in-thread 2013) conceded: *"in some extreme cases, it does happen that the vector contains one 1 and the rest are 0s. We are still looking methods to control its behaviors."* (3) TURNOVER ANNIHILATES IT: median 1.851/day → net CAGR −8.06% @5bps, −24.05% @10bps, **−75.49% @39.5bps** (the desk's own fail-closed p90 for an unmeasured name), capital ×0.0125. | `costs_killed_edge` + `no_economics` | **THE ERA'S OWN STATED KILL REASON IS WRONG AND WAS REFUTED HERE — do not reuse it.** Grant Kiehne (2019) blamed correlation: OLMAR fails on sector ETFs because "each ETF is too correlated with the market… you are just dealing with an arbitrarily coarsely chopped SPY". MEASURED on our own data with one estimator over both universes (idiosyncratic share of daily return variance vs the panel's own leave-one-out equal-weight factor): **crypto top-8 idio 0.513 vs the sector ETFs that failed 0.492** — crypto is *no more* factor-dominated, and carries **3.3–3.8× the cross-sectional dispersion** (0.0283/0.0324 vs 0.0085 daily). So the family dies on its ALLOCATION RULE, never on the opportunity set: **this row must NEVER be cited as evidence that crypto cross-sectional strategies lack raw material — the dispersion measurement says the opposite.** Corroborating era self-falsification, all harvested in-thread (free): Paul Perry's full OLPS-toolbox comparison — *"hard to say that any of these algorithms decidedly beat BAH or CRP… OLMAR is really not outperforming"*; the ONS paper + Borodin et al. (2004) — uniform CRP outperforms all previous algorithms; Thomas Wiecki (Quantopian head of research) publishing results only after swapping VolumeSlippage→FixedSlippage *because the volume model prevented the rebalance completing* (the friction WAS the finding); "Blue Seahawk" recomputing a headline 190% to **58% on capital actually utilized vs a 128% benchmark** once margin was counted; Jason Tichy — *"it only seems to work with the seed money of $100k. If I input any smaller amount the algorithm loses it in a couple months"*, which is disqualifying for a §42 small book independent of everything above. BIAS DIRECTION IS SAFE: the universe was selected on *current* liquidity (survivorship + liquidity selection), biasing the test UP; it fails anyway. RE-ENTRY CONDITION (L1.16a): only on a named enabling change to the ALLOCATION rule — a turnover-constrained or transaction-cost-aware OLPS variant (e.g. an explicit L1-penalised update) demonstrated to hold effective-N > 3 and median daily turnover < 0.15 BEFORE any return is computed; a new parameter set for the same unconstrained update is NOT an enabling change and is re-litigating. Nearest desk prior: `short_term_reversal (xsec)` (unprofitable at zero cost, IC mid-distribution) — the novelty gate scored this 0.25 similarity / NOT redundant, but that gate was measured at **0% recall** by the desk's own 2026-07-30 research-engine audit, so the PASS was treated as uninformative and the kill was justified on mechanism, not on the gate. |
| lit_quarter_hour_clock_phase_alpha (arXiv 2607.09426 Kim & Hansen, "The Quarter-Hour Effect: Periodic Algorithmic Trading and Return Predictability" — the ALPHA leg: trade the quarter-hour clock-phase imbalance) | **STRUCTURAL KILL on the authors' own arithmetic: the effect is ~0.5 bp per boundary against a ~10 bp round trip — a 20x cost-to-signal ratio — and the paper carries an EXPLICIT DISCLAIMER against standalone trading.** Independently corroborates the desk's own EV-gate rejection of 2026-07-17 (`quarter_hour_periodicity_crypto_futures`, ev 0.0006, `crowded_known`). | `costs_killed_edge` | **THIS ROW EXISTS BECAUSE THE NOVELTY GATE WAS RUN AT HALF WIDTH.** litminer run 6 (2026-08-12) carded this as mechanism card 28 -> R0459 after cross-checking `docs/graveyard.md` ONLY; the collision sits in `research_agenda.json::do_not_repeat[23]`, **by exact arXiv id**, 26 days old. The standing duty names BOTH stores and only one was read. **THE SPLIT THAT MATTERS AND MUST SURVIVE THIS KILL:** only the ALPHA leg dies. Card 28's second leg — an execution-hygiene rule (do not execute ON the mark boundary), explicitly carrying NO alpha claim and feeding the 66bps execution program — is a DIFFERENT OBJECT that the EV gate never judged, and it is not killed here. **L1.16a re-entry is CLOSED for the alpha leg:** the 07-17 death was ev + crowding; the only change since is the desk's own-clock recorder, which answers a secondary infra remark and leaves the mechanism of death untouched. A new intraday collector is NOT an enabling change. |
| lit_prediction_market_options_wedge (Portnaya arXiv 2606.19517 — implied-probability gap between prediction-market binaries and the Black-Scholes digital `P_fair = e^(-r*tau)*Phi(d_2)` inverted from listed options; headline 5.6pp "segmentation" wedge) | **NULL, AND NOT IDENTIFIABLE AS SPECIFIED.** The paper's own arbitrage proxy is n=16 trades, one market carrying a single losing trade, pooled HAC CI **[-0.008, 0.143] CONTAINS ZERO**, and the friction formula's three parameters are **never assigned a number anywhere in the paper**. Worse, three biases each of the ORDER of the 5.6pp effect and each scaling with sqrt(tau) *along the paper's own headline axis*: omitted skew term ~2-10pp (sized off the desk's stored BTC skew 10.19 IV pts), spot-for-forward ~2-4pp at a 10% basis, and a longshot quoted half-spread co-varying with the wedge (arXiv 2604.24366). Nothing is left for "segmentation", and the paper states the OPPOSITE SIGN for the skew correction to what `-dC/dK` gives. | `no_edge` | **AND THE DESK ALREADY ANSWERED THIS ONCE:** `reports/prediction_markets/report.json` holds a completed favourite-longshot test — **166 markets, 0 survivors**, every variant below the n>=250 floor — uncited by the card that rested on it. **THE DATA CLAIM WAS ALSO FALSE:** card 29 cited "the Deribit surface the desk already holds"; `data/deribit_surface.parquet` is **100 rows x 6 SCALAR columns (`ts,currency,atm_iv,skew,term,spot`) with NO STRIKE DIMENSION**, 7 weeks daily — it cannot support a strike-wise digital comparison at all, and OpenMarket cannot backfill it (`up_token_id`/`down_token_id` are strikeless up/down binaries; licence **Apache-2.0, not CC-BY** — correcting universe-map entry 97). **WHAT SURVIVES, AND IT IS CHEAP:** one keyless chain snapshot comparing `Phi(d_2)` against the call-spread digital decides the identifiability question for the cost of a single HTTP GET. No history, no capital, no multiplicity slot. |
| lit_crypto_pairs_daily_gross_death (daily-frequency crypto pairs trading: distance AND cointegration selection — the textbook stat-arb rung) | **DIES ON GROSS, NOT ON COSTS — at ZERO cost: +0.31%/mo, 46% WIN RATE, 24.6% max drawdown.** A 46% win rate before a single basis point is not an edge being eaten; it is an edge that was never there. Independent corroboration from the same corpus: derived breakeven one-way costs (gross and net tables 30 pages apart, combined here, stated in NEITHER the thesis nor its journal version) — **daily cointegration 23.6 bps, daily distance 29.4 bps, hourly distance 65.6 bps, and hourly cointegration 18.6 bps which is BELOW the venue's own taker fee.** | `no_edge_daily` | **STRUCTURAL, and strictly stronger than a cost kill: a cost-reduction programme CANNOT rescue this rung.** Source: Fil, Charles University 2019 (supervisor Krištoufek), open-access thesis, full text `[PRIMARY]`. **THIS SHARPENS THE DESK'S OWN CARD 27 RATHER THAN KILLING IT:** the daily and hourly rungs are now dead from an independent direction, which is exactly why card 27 pre-registered the **5-min** rung — and an independent second group lands there too (+11.61%/mo), **though that group's cost model is UNREADABLE (IEEE 418s despite CC-BY) and the raise therefore carries a NAMED UNVERIFIED DEPENDENCY, not a validation.** **AND THE GROUND'S OWN PREMISE WAS REFUTED HERE:** the claim that journals launder a thesis's negatives is FALSE in this case — the journal version PROMOTED the negatives into the abstract headline. The exploitable asset in a thesis is the intermediate SENSITIVITY TABLE a journal compresses away (gross printed next to net), never the failure narrative. |
| lit_kr_spot_perp_arb_thesis (Kookmin Univ. doctoral work: BTC spot-vs-perpetual arbitrage, KR venue set) | **DIES TWICE, INDEPENDENTLY.** (1) Minute rung: **gross 2.6 bps against a retail all-in cost of 6.5 bps** — negative before it starts; and its ONE profitable configuration ran on **FTX, which collapsed BEFORE the paper was accepted**, so the surviving venue does not exist. (2) Daily rung: **cash-and-carry MISLABELLED as arbitrage — 100% win rate over 162 trades, with funding DEFINED in §3.2 and NEVER CHARGED.** | `costs_killed_edge` | **A POSITIVE BACKTEST WITH AN ABSENT COST MODEL IS A NEGATIVE RESULT, and this is the cleanest specimen the desk has banked: the paper defines the exact cost term it then omits.** 100% over 162 trades is the tell — no real spread trade wins every time; it is the funding leg's sign being assumed rather than paid. **ROUTE FINDING ATTACHED (T-6), and it reinterprets prior desk verdicts:** every ETD AGGREGATOR refused this box (OATD 403, CORE 403, NDLTD 503, IEEE 418; **DART-Europe PERMANENTLY CLOSED 2025-02-03**) while every INSTITUTIONAL repository served full text at 200. **Aggregator routing is why prior seats read full corpora as empty — the Korean thesis layer is NOT empty and the prior zeros were a routing artifact.** Never grade a corpus from an aggregator's silence. |

---

### retail_crossvenue_scan_arb — KILLED at source with the operator's own instrumentation (RU, 2025 primary text)
_RU frontier miner, session 1, 2026-08-01. Source: habr.com/ru/articles/911056/ (2025-05-20),
"Арбитраж криптовалют — или переливаем из пустого в порожнее" ("...or pouring from empty into
empty"), + its 66-comment tree mined to depth 7 via OP-039. Public article, §13 clean._

**THE MECHANISM AS CLAIMED:** scan every pair on every venue for BID(A) > ASK(B) net of fees; when
the spread exceeds costs, buy on B and sell on A. The retail cross-venue "переливы" family.

**THE OPERATOR'S OWN NUMBERS, from a purpose-built scanner (16 venues, 2,870 pairs, CCXT +
ClickHouse, two-stage bulk-ticker-then-orderbook architecture):**
- **15,256** arbitrage signals detected → **4** survived manual review. That is the entire result.
- **90.8%** of signals expire in **milliseconds**; only **0.9%** (137) last >15 minutes.
- 77% of all signals came from a single venue (Gate.io) — i.e. concentrated in the venue most
  likely to be quoting stale, not the venue most likely to be payable.
- $100k/day minimum volume filter and a $100 test deposit — this is the desk's own size band, so
  the kill is NOT a capacity artifact and §42 does not rescue it.

**WHY IT DIES — four named failure modes, none of which is "the spread was too small":**
1. **The withdrawal rail is closed exactly where the spread is wide.** Independent second source,
   habr 599551 (2018/2022): *"там, где большие проценты, монеты не доступны к выводу"* — where the
   percentages are big, the coins are not withdrawable. The spread IS the closed rail, priced.
2. **The venue's withdrawal-status API lies.** An asset reports as withdrawable while the network
   is in fact halted, and the API does not expose it. A cost model built on the API is wrong in
   the unsafe direction.
3. **Ticker collision — the same ticker is a different asset/network across venues.** Verbatim
   (comment, depth 1, score 0): *"есть скамные пары которые надо фильтровать — ticker один а по
   факту разные сети, на них сразу арбитраж и 600% будет"*. **The apparent edge is largest exactly
   where the join is wrong.** This independently confirms the desk's §42 rule that a cross-venue
   spread above the credibility ceiling is marked and never ranked first.
4. **The binding constraint is VENUE COUNTERPARTY RISK, not the spread.** From the thread's one
   substantive counter-claim (depth 0), which asserts 25–75%/month is achievable on futures and
   DEX-CEX rather than spot: *"Главная задача — это не спалиться... давно мониторят токсичные
   сделки и выдают неопытным бан. Очень повезёт, что вернёте стартовый капитал через пару
   месяцев."* — the venue detects "toxic" flow and bans/withholds withdrawal. **Even the bull case
   concedes the P&L is not withdrawable.** An edge you cannot withdraw is not an edge (L1.5).

**TAG:** `costs_killed_edge` + `no_economics` (as arb) — and **mechanism-reclassified**, see below.
**RE-ENTRY CONDITION (L1.16a):** only with (a) pre-funded inventory on both venues removing the
on-chain leg entirely — the thread's own top-voted suggestion, which the author concedes at least
doubles capital and requires synchronised execution — AND (b) a measured, venue-specific
withdrawal-success record proving the P&L is realisable. Absent (b) this stays dead: the desk would
be financing a venue's float and calling it alpha.

### CROSS-ERA SYNTHESIS — the barrier MIGRATES, the premium never becomes harvestable
This is the **fifth instance** of `era_crossvenue_fiat_premium_arb`, and the first from the RU
corpus. Placed here because it changes the law's shape rather than adding a data point.

The desk already held: *a cross-venue premium that persists is rent on a capital-control /
withdrawal / counterparty barrier — compensation, not inefficiency, harvestable only by whoever
holds the specific rail access*, with **premium magnitude tracking BARRIER HEIGHT**.

Five instances now, and the barrier is a **different object every era while the conclusion is
identical**:
| era | venue pair | the barrier | outcome |
|---|---|---|---|
| 2013 | MtGox ↔ BTC-e | withdrawal insolvency | premium → 0 at Gox collapse |
| 2013–14 | BTCChina ↔ abroad | capital controls; cash physically flown to HK | rent on permissions |
| 2017 | CN venues ↔ abroad | AML/latency barrier | episodic, merchant-density-bounded |
| **2022+** | **RU P2P ↔ global** | **sanctions; card rails severed** | **see RU note below** |
| **2025** | **any CEX ↔ any CEX** | **the venue's own anti-toxic-flow enforcement** | **P&L not withdrawable** |

**THE OPERATIVE UPGRADE:** the 2025 instance shows the barrier persists *even when every state-level
barrier is absent*. Two venues in the same jurisdiction with open crypto rails still produce an
unharvestable premium, because **the venue itself becomes the barrier** once it detects the flow.
So the law is not "premiums are rent on capital controls" — it is **"a persistent cross-venue
premium is rent on whatever barrier is currently binding, and a barrier is always binding, because
a premium with no barrier is arbitraged away by definition."** The corollary is the useful part:
**do not hunt for a region whose barrier is low enough to arb — that region's premium is already
zero.** This closes the "find a friendlier jurisdiction" idea before anyone spends a cycle on it.

### statarb_kalman_hedge_ratio_refinement — pre-emptively killed by its own comment thread (RU, 2023)
_Source: smart-lab.ru/blog/936066.php (2023-08-30), Kalman-filter statistical arbitrage BTC/ETH._
**CLAIM:** a Kalman filter estimating a time-varying hedge ratio between BTC and ETH beats a static
/ rolling-OLS ratio for pairs trading. 1,035 days of 4h bars, 27.05% time in market, z≤−2 long /
z≥+2 short / exit at 0.
**KILLED BY THE REPLIES, not by us** — free falsification, the cheapest kind:
- *"For arbitrage, normal regression plus std dev suffices"* — Kalman deemed unnecessary; roughly
  equivalent returns from a 3rd-order polynomial (commenter 3Qu).
- *"Realistically buying/selling at your model price will be extremely problematic"* — execution,
  which the post never models.
- *"ChatGPT wrote this. Ernie Chan, probably. And yes, Kalman filter not needed."* (robomakerr).
**AND IT FAILS EVERY DESK GATE ON ITS FACE:** no costs, no slippage, no out-of-sample, no
significance test, **one pair**, no comparison to the rolling-OLS baseline it claims to beat.
**TAG:** `no_economics` (the refinement, not pairs trading itself, which is UNTESTED here — see the
STATISTICAL-ARBITRAGE card in the watchlist). **The transferable lesson:** the sophistication layer
(Kalman, polynomial, ML hedge ratio) is where RU practitioners consistently report zero marginal
gain over OLS+σ. If the desk ever tests statarb, spend the budget on **costs and capacity**, which
is where every RU thread says it actually dies — never on the estimator.

## kimchi_premium -- daily close-to-close construction (KILLED 2026-08-01)

**Mechanism-of-death: NO EDGE AT FULL DEPTH, on a thin-window original screen.** The celebrated
IC +0.2249 was measured on ~200 days. At 2,303 same-instant-aligned days (2017-09-25 .. 2026-08-01)
the h=1d cell reads IC **+0.0148**, residual **+0.0118**, against a detection floor of 0.041 -- the
point estimate is a third of the smallest effect this sample could resolve. Per-era signs flip
across all four regimes (+0.0141 / -0.0092 / +0.0010 / +0.0532). The h=5d cell is de-contam-killed
(raw -0.2064, same-period -0.191, residual -0.0522 -> TIMING-ARTIFACT): the premium puts the
Binance price in its DENOMINATOR, so that is construction, not information.

**CORRECTION 2026-08-01 (R0067) -- the original stated mechanism was REFUTED, the kill was not.**
This entry first recorded the death as a *~73% timestamp artifact*: "Upbit's `candle_date_time_utc`
is the KST-day OPEN, so keying by it labelled closes ~15h early". **That premise is false.** Upbit
day candles are UTC-MIDNIGHT-boundary -- the candle labelled D closes at 24:00 UTC D, proven to the
won against Upbit's own hourly candles on four dates across two eras
(`tests/research/test_upbit_boundary.py`). The belief was inherited from
`bithumb_kr_premium_lookahead`, a REAL kill on a DIFFERENT venue whose 24h candle genuinely is
KST-day-open; Upbit is not Bithumb, and the premise was never measured before it became canon.
Consequences, both now closed: the "fix" it justified added a `+1 day` shift that 24h-mispaired
every leg (corr(premium, -r_binance) +0.813, std 2.98% vs 1.40% same-instant), and the depth
numbers first published in this entry (n=2,302, IC +0.0251, per-era -0.054/+0.072/-0.042/+0.052)
were computed on that mispaired series -- they are SUPERSEDED by the same-instant figures above.
The shift test that started it (`+1d 0.823` vs `0d 0.225`) was never leak evidence: the premium
carries the Binance price in its denominator, so a +1d-shifted premium is contemporaneous with the
target BY CONSTRUCTION. **The kill stands on depth, independent of any of this.**

**Reproduce:** `scripts/backfill_kimchi.py` (one-shot; archives to
`data/kimchi_premium_history.jsonl`). All 3 horizons and all 4 eras are reported, not just the
best cell -- reporting the winner alone would be p-hacking our own collector.

**Still open, and genuinely different rather than a re-litigation:** INTRADAY -- but note the
original argument for it ("the leak was a day-boundary problem, so the signal must live inside the
day") DIED WITH THE LEAK, and must not be cited. What survives is weaker and honest: a daily
close-to-close pair samples a continuously-quoted spread twice, so a mechanism acting on an
arbitrage-window timescale would be invisible here whether or not one exists. That is an argument
about RESOLUTION, not evidence of a signal, and it earns a screen on intraday data -- never a slot.

**ADDENDUM 2026-08-18 (litminer run 8, R0611) -- h>1 cell numerics were computed through a
defective target window; THE KILL IS UNCHANGED.** `backfill_kimchi.py` builds `ret` as the h-day
return ENDING at t on daily rows, so the harness's rolled target for h=5/20 spans (t+1-h, t+1] --
h-1 of h days already known at signal time (instrument defect proven by oracle synthetic,
`data/carry_liq_screen.json` `instrument_finding`). Consequence: the h=5d cell's raw/-0.2064,
same-period/-0.191, residual/-0.0522 must not be cited as forward-horizon measurements. The
TIMING-ARTIFACT verdict itself survives on structure (the premium carries the Binance price in its
denominator -- construction, not information), and the kill rests on the h=1d cell (correct window:
IC +0.0148 vs floor 0.041, per-era sign flips), which is untouched.

---

### jp_mlbot_atr_limit_reversion (richmanbtc `mlbot_tutorial` lineage) — PRE-EMPTIVELY KILLED by the community's own attribution study, before the desk spent a single screen on it
_JP frontier miner session 1, 2026-08-01. Free graveyard material: refuted at source, not by us._

**The claimed mechanism.** The most-cited artifact in the entire JP botter ecosystem —
`github.com/richmanbtc/mlbot_tutorial` (519★, 187 forks, **CC0-1.0** verified via GitHub API,
**dead since 2022-11-28**). LightGBM on ~43 TA-Lib features predicting the realised P&L of a
specific passive execution rule on GMO Coin BTC_JPY 15-minute bars, 2018-10 → 2021-04.

**WHY IT IS DEAD — the attribution, done by the community itself** (バジル @kkngo_crypto,
`note.com/kkngo/n/n631e9fdc7855`, 2023-02-05): the profit source is
**「毎回ATR×0.5の位置に指値を置くだけ」** — *just placing a limit at ATR×0.5, every time*. That rule
alone returns **~1700% over the 2.5-year window with no machine learning whatsoever**, and adding
the tutorial's full ML stack on top leaves cumulative return **almost unchanged** (it cuts trade
count and improves capital efficiency; it does not add return). **The ML is a filter on a rule that
was already the entire edge.**

**AND THE RULE ITSELF IS A FEE ARTIFACT.** The tutorial hand-transcribes GMO's
`maker_fee_history`: `0.0` initially, **`-0.00035` from 2020-08-05**, **`-0.00025` from 2020-09-09**,
`0.0` from 2020-11-04. **The maker fee is zero or NEGATIVE across the entire backtest window.** So
the mechanism is passive liquidity provision harvesting mean reversion on a retail JPY venue during
a period when the venue *paid you to post*. That is a **venue-subsidy harvest**, not an alpha — and
the subsidy ended.

**INDEPENDENT DEATH CONFIRMATIONS, three of them, different venues and timeframes:**
- kkngo 2023: 「毎回ATR×0.5の位置に指値を置くだけで勝てるわけがない」 — the identical approach now loses.
- chanta (`qiita.com/chanta/items/158f0d2b63afa2e6935b`, 2024-12-20, "消えたエッジの話"): same family
  on **Bybit, 12-hour bars, ATR(6), 0.21–0.25×ATR**, live-profitable from ~Dec 2023 (some months at
  90% win rate), **died March 2024** when the 12h BTC reversal cycle that had held since 2022 broke.
- pip_pip_pip_p (`qiita.com/pip_pip_pip_p/items/3b86e36ca536e99d26e0`, 2024-12-07): the rule-based
  layer on Binance BTCUSDT is up in 2021 and **monotonically down from 2022 onward, including
  through the Nov–Dec 2024 bull market**.

**THE TUTORIAL FAILS ITS OWN TWO BARS AND SAYS SO.** Published run: naive t-test `t=7.169`,
`p=7.62e-13` — overwhelming. Its author's own p-mean: **0.2005**, error rate **8.43e-3** against his
stated bar of **≤1e-5** (off by ~840×); his own non-stationarity score **0.4556** against his stated
threshold **≤0.3**. He states up front 「そのままでは儲からない」 (*it will not make money as-is*).
**The desk should read the p=7.6e-13 vs error-rate-840×-too-high contrast as the artifact it is** —
it is the same shape as our own 420/0 instrument lesson pointed the other way.

**METHOD DEFECTS, recorded so the shape is recognisable when it arrives in our own work:**
1. **No cost model in substance** — fee ≤ 0 for the whole window (above).
2. **Anti-causal CV.** `KFold()` with sklearn defaults = `shuffle=False, n_splits=5`, so for fold 0
   the validation block is the *earliest* 20% and training is the *subsequent* 80%. **Four of five
   folds train on data that postdates their validation block.** `TimeSeriesSplit` sits commented out
   one line below. Purging is explicitly omitted, with unbounded overlapping labels from the
   Force-Entry-Price forward scan (O(n²), **no horizon cap**).
3. **Frictionless fills** — a touch through the limit is a fill; no queue position, no volume check,
   no partial fills, no liquidation/zero-cut.

**VERDICT: do not screen this family on JP venues.** Not because passive reversion is uninteresting,
but because the published instance's return is attributable to a **maker rebate that no longer
exists**, and three independent practitioners have since watched it die on three different venues.

**L1.16a RE-ENTRY CONDITION:** a venue paying a **negative maker fee** on a book we can actually
reach, at a size our band can fill — at which point this is a *rebate-harvest* mechanism to be
sized on the rebate, and must never again be described as an ML edge.

**WHAT SURVIVES THE KILL** (routed to `improvement_inbox.md`, not here): the p-mean evaluation
shape, the adversarial-validation-against-time feature screen, and `publicGetExpiredFutures` as a
survivorship-free universe primitive. The mechanism is dead; three of its tools are not.

---

## `jp_bitflyer_direct_recording` — bitFlyer direct recording (getexecutions + self-recorded candles)

**KILLED 2026-08-01. Mechanism of death: §13 LEGITIMACY — the licence forbids the use.** Not a
technical failure, not a null result. The endpoints work and are keyless; we may not use them.

**THE OPERATIVE CLAUSE** (verbatim, Wayback capture `20190601153535` of
`https://bitflyer.jp/en-eu/terms-of-use`, 2019-06-01, HTTP 200): *"The bitFlyer API is the
copyrighted technology of bitFlyer and may not be copied, imitated or used, in whole or in part,
outside of the API's intended use. bitFlyer retains all its rights related to its databases,
websites, … including chat text, the content of bitFlyer emails, and data such as **transaction
prices** — developed or provided by bitFlyer or its affiliates which can be acquired by various
external APIs."* Reinforced by *"only for your internal purposes and solely as necessary for your
use of the Service"* and an explicit bar on *"any robot, spider, crawler, scraper, script … not
authorized by us to access the Services, extract data"*.

**BLAST RADIUS — the clause pre-emptively killed two live keyless endpoints before either could be
carded**, which is why this entry matters more than one collector: `/v1/getchats` (real JP retail
chat — the clause names *"chat text"*) and `/v1/getfundingratehistory` (8-hourly JP funding — the
desk's ONLY repeat-surviving family, and the single most wanted series in the region). It also
blocks the run's largest find, deliberately never carded: `bitflyer.jp/api/chart/btc_jpy`, an
undocumented keyless 15-minute BTC/JPY series, dead live (302) but Wayback-captured 200 from
2015-08 back to 2014-10-16 (~414,675 B ≈ 10 months per capture).

**AN ARCHIVE COPY IS NOT A LICENCE.** Reading bitFlyer's data out of a third-party archive does not
extinguish bitFlyer's stated rights in it. This is the reusable half of the ruling: whenever a
blocked source turns out to be Wayback-captured, the capture answers AVAILABILITY and says nothing
about PERMISSION, and the two must never be collapsed.

**WHAT WAS REFUTED ON THE WAY (route ≠ capability).** Four prior deferrals all varied the same
thing and all mis-read the evidence. "403/WAF-blocked" was wrong: TLS completes, the cert verifies
(`O="bitFlyer, Inc."`), the HTTP/2 stream opens, then `INTERNAL_ERROR (err 2)`; over HTTP/1.1+IPv4
it hangs to timeout (`code=000`) — an Akamai tarpit, not a status code. The block is PER-HOSTNAME,
not egress: `api.` and `lightning.` both return 200 from the *identical* edge IP
`2a02:26f0:e80:588::2644` that tarpits the apex; only the marketing/legal host is bot-managed.
"Never usefully archived" was refuted by fixing the CDX query — the pre-migration host is
`bitflyer.jp` (not `.com`) and the slug is `terms-of-use` (not `terms`); corrected, it returned the
document on the first attempt. A wrong host and a wrong slug had read as "the evidence does not
exist" for four sessions.

**HONEST RESIDUAL — this is a group position, not a JP-entity ruling.** The document read is the EU
entity's 2019 ToS. JP-side `terms-of-use` paths have no CDX captures and the live host is
tarpitted, so the JP entity's current 利用規約 has never been read. §13 asks whether a licence
forbids the use, and the only bitFlyer terms document this desk has ever read says yes. Grading a
restriction on the evidence we have beats a fifth deferral on evidence we cannot get.

**L1.16a RE-ENTRY CONDITION:** a bitFlyer **JP-entity** ToS, or an explicit bitFlyer data-use
permission, that does **not** retain rights in transaction prices. Absent that named change, do not
re-open — the endpoints working is not new information.

**LICENSED SUBSTITUTES, ALREADY OWNED:** Tardis.dev covers `bitflyer` from 2019-08-30, free
first-of-month, internal research use PERMITTED — residual gap is granularity (1 day/month), not
availability. Unrestricted JP alternatives found the same run: GMO Coin's free keyless tick CSVs
from 2018-09-05 (40 symbols, JP-only MONA/XYM/FCR/NAC/WILD) and bitbank's public candlestick API.

## `olmar_olps_era_zero_cost_canon` — OLMAR / OLPS portfolio-selection algorithms, 2013-14 Quantopian canon

**KILLED 2026-08-04 (EN frontier miner, Quantopian era-archaeology). Mechanism of death: COSTS
DISABLED IN THE CANONICAL CODE, propagated by cloning.** Primary artifact: Wayback capture
`20140214052422` of `quantopian.com/posts/olmar-implementation-fixed-bug` (Grant Kiehne's
implementation of Li & Hoi's ICML-2012 OLMAR, the era's most-cloned algorithm — **708 clones**).
The shared source contains, verbatim: `set_commission(commission.PerShare(cost=0))` and
`set_slippage(slippage.VolumeShareSlippage(volume_limit=0.25, price_impact=0))` — **zero
commission AND zero price impact hardcoded**, on a HAND-PICKED fixed `sid()` list. The era's
flagship "edge" was a fee-free, impact-free, selection-biased artifact BY CONSTRUCTION, and the
sharing/cloning culture propagated the disabled cost model through 708 descendant lineages.
Even the platform's own scientist's refactor thread says "I'm confident that it's doing the
correct thing **now**" — correctness arrived after the clones. THIRD INDEPENDENT INSTANCE of the
fee-artifact class (richmanbtc C62: maker fee ≤0 across the whole backtest; CryptoTrader.org
contest round #2/#3 forward vs round #5 in-sample) — **when era code is inherited, audit the
cost model FIRST; the death is usually in one settings line, not in the alpha logic.**
High-turnover daily mean-reversion of the OLMAR class is cost-dominated; do not re-test without
a real fee+impact model, and treat any strategy lineage descended from era Quantopian code as
cost-contaminated until its settings lines are read.

## `inout_early_warning_rotation_fragility` — "In & Out" cross-asset early-warning rotation (2020 Quantopian)

**KILLED AS AN INSTANCE 2026-08-04 — the community's OWN perturbation test falsified it
in-thread.** Primary artifact: Wayback captures `20201030003233`/`20201106094220` of
`quantopian.com/posts/new-strategy-in-and-out` (Peter Guenther, 100+ replies, the platform's
last flagship thread). Mechanism: exit SPY into IEF/TLT when early-value-chain signals (DBB base
metals, XLI industrials, SHY short-rate yield) drop "substantially" (~7% / 60bps over ~3mo);
re-enter after 3 trading weeks; evolved mid-thread into 1%-tail percentile triggers on shifted
history. THE KILL, from the reply layer (charter §9 — the debunking lives in the thread): Dmitry
Sarnachev re-ran with the magic constants rounded to less-engineered values (wait days 15→20/22,
lookback 58→53, "whole number of weeks") and reported **"a drastic drop in returns"** —
parameter-perturbation instability, the same instability class the desk's own
`hl_elite_directional_order_flow` kill established ("a real edge does not flip under
perturbation"). Thomas Chang's depth-1 reply asks the generating question: *"I wonder how much
time you have spent to figure out the value of 15 and 58?"* HONEST SCOPE: this kills the TUNED
INSTANCE, not the general cross-asset lead-lag hypothesis (which is a separate, live,
weak-signal-registered question); any re-test must be constants-free (percentile/rank triggers)
and survive ±perturbation of every window.

## `crowdsourced_backtest_selection_fund` — allocating real capital on community backtest rank (Quantopian fund, 2017-2020)

**KILLED BY HISTORY 2026-08-04 — the at-scale natural experiment of backtest-selection-vs-forward,
recorded so the desk never re-runs it in miniature.** The platform selected community strategies
showing **backtest Sharpe > 2.5** (contest + allocation machinery) into a real-money fund (launched
2017-06-01 with Point72/a16z backing). FORWARD RESULT: **−3% in the first 4 months vs SPX +6.6%**
(HN 15652997, quoting contemporaneous reporting); **investor capital RETURNED Feb 2020**
(bizjournals, cited HN 24931089); community platform shut 2020-11-14. The depth-1 diagnosis that
survives scrutiny: *"top strategies were showing off Sharpe ratios higher than 2.5 … such poor
performance is proof that something is wrong with the way they test"* — selection on in-sample
excellence at scale IS the flaw; crowding in US-equity factor space compounded it. CONFOUNDERS
DECLARED: 4 months is short, 2017 was hard for quant factors broadly, AUM was small — the
capital-return endpoint is what makes the verdict terminal rather than the 4-month print.
CORROBORATES: the desk's two-stage discovery law (backtest gauntlet = screen with ZERO promotion
authority; only pre-registered forward evidence promotes) and the 420/0 power-artifact finding.
This entry is the historical evidence base for WHY the confirmation bar never loosens: the
largest crowd-sourced attempt ever made bought negative live alpha with exactly the machinery the
two-stage law forbids. Microstructure rider (depth-5 reply, justrobert): OHLC backtests are
structurally blind to crash-day bid/ask breakdown and broker margin-call liquidation — an
execution-reality prior for any stress-period backtest claim.
Era rider (2026-08-12, EN frontier sG — HN 9152332, the 2015 CONTEST thread, full tree): the
mechanism of death was predicted in the operator's own thread FIVE YEARS before the outcome —
learnstats2: *"The algorithm you need to win a contest is the highest risk algorithm you can get
away with"* (selection-on-max ⇒ selects variance, not skill); numlocked/im2w1l stated the
survivorship arithmetic outright. The operator's own defense (fawce, 9153904) named the exact
gate that later failed: *"2 years of backtesting + live trading for a month — I don't think it is
likely you can both overfit and be lucky"* — one month of paper is statistically nothing, and the
2020 capital-return proved it at scale. Adversarial bonus (im2w1l, 9153953): a blackbox-tested
candidate can FINGERPRINT the evaluation data ("include signatures of past data; if detected you
know the future, else go for blind luck") — conditional-behavior overfit, the attack class the
desk's forward-only promotion is immune to by construction and any backtest-weighted gate is not.
Same-family NP corroboration (161713, intradaybill, 2012): 1000-generation GP curve-picking died
70% down WITH out-of-sample testing — "the guy who wrote the software is the king of selection
bias"; selection ON the OOS is still selection.

### era_grid_ladder_vol_bot — SECOND INSTANCE (RU 2014, sold-to-retail variant) — CORROBORATED + FAILURE MODE ADDED
Source: forum.btcsec.com topic 5499 ("Бесплатный btc-e бот от MensFreedom", 2014, Wayback
20140814073909, mined to reply-depth; RU miner s1-on-branch 2026-08-04). A corridor/"коридор
курса" grid script for BTC-E, marketed as "временной арбитраж" (temporal arbitrage) with
"беспроигрышная торговля" (can't-lose trading) — sold as freemium (free tier → Start/Basic/Pro
FTC subscriptions + 10%/5yr referral pyramid + volunteer moderator recruitment). The thread
contains its own kill, from users not the vendor: (post 15) "это не бот, это просто скрипт...
использовать можно только при флете, либо при пампе. В случае дампа всё будет просрано" — the
short-gamma economics of instance #1 (GMVT-BOT) restated by RU retail in one sentence; (post 16)
"если бот приносит прибыль, зачем его продавать?" — the seller-signal; (post 14) community
debunks "временной арбитраж" as requiring knowledge of future prices. NEW FAILURE MODE the GMVT
instance did not show: CORRELATED INFRA OUTAGE — (post 9) "когда сегодня ночью были такие движи,
сервак с ботом лёг и умер" / vendor confirms 1.5h outage during the move (posts 9-10): the
hosted-bot server died exactly during the large move, i.e. the grid's max-damage moment and the
operator's outage are the SAME event (both are volatility). Era-provenance kill extended: hosted
retail grid bots add a correlated-operational tail to the short-gamma tail — the desk never
re-derives grid-bot economics AND never treats hosted-execution uptime as independent of the
regime that kills the strategy. Lexicon: "временной арбитраж" = grail-marketing term, not a
mechanism; search key for the sold-bot genre in RU sources.

### era_crossvenue_fiat_premium_arb — SIXTH INSTANCE (RU/UA 2013, exchanger fee-ladder, primary numbers) — BARRIER-RENT QUANTIFIED + ANCHOR FACT
Source: forum.btcsec.com topic 1987 (24change.com exchanger thread, Sep 2013, Wayback
20130909id_) + topic 4083 (Romanov Capital daily TA thread, Dec 2013-Jan 2014), both mined to
reply-depth (RU miner s1-on-branch 2026-08-04). (a) ROUTE DISPERSION IS THE RETAIL-VISIBLE RENT,
with primary numbers (post 4, user "gladiator", Sep-2013): the SAME 1 BTC nets 86.74 у.е. via
the 5% exchanger vs 98.22 via metabank / Privat24-direct; BTC-E direct exit 94.40−6%; multi-hop
BTC-E→LiqPay(4%)→Privat24(0.5%+0.5) = 88.73 — an ~12% spread ACROSS ROUTES at one instant, with
multi-hop beating several direct rails. The barrier rent decomposes into: immediacy+inventory
rent ~3-4% (the exchanger's own pitch: "скорость и неограниченные резервы именно тогда, когда
это необходимо" — vs 2-day BTC-E withdrawal queues), plus per-rail friction stacks. (b) ANCHOR
FACT: the RU/UA exchanger layer priced off BITSTAMP ("биткоин покупается по курсу bitstamp"),
NOT the local venue BTC-E and NOT Gox — while a user (post 19) begs them to "switch to the Gox
rate already" because Gox printed HIGHER: retail wanted the broken venue's premium paid out over
working rails, which is exactly the rent transfer the barrier prohibits. (c) REAL-TIME GOX
KNOWLEDGE (topic 4083 post 3, 29-Dec-2013): "Какой толк от Гокса, вы там пробовали торговать?" —
RU practitioners treated the Gox price as untradeable SIX WEEKS before the Feb-2014 collapse;
the premium was priced withdrawal-failure in real time, corroborating instance (a)/(b)'s
retrospective reading with a contemporaneous primary source. (d) JURISDICTION ARB AS BUSINESS
MODEL (posts 15-16): asked about FSB requests, the exchanger answers "Физически мы не в РФ
находимся" — the 2013 ancestor of the post-2022 P2P/USDT rail structure; the rent collector
sits OUTSIDE the barrier's jurisdiction, always. Standing implication unchanged and
strengthened: persistent premium = barrier rent, harvestable only by rail-access holders;
usable as information/timing, never sized as arb.

## `jp_sfd_boundary_game` — bitFlyer Lightning FX Swap-For-Difference boundary game (2018–2024)

**DEAD AT SOURCE 2024-03 (JP frontier miner s1-on-branch, 2026-08-04, era-archaeology).**
Lightning FX and SFD were ABOLISHED end-March 2024 (successor product: bitFlyer Crypto CFD);
the game cannot be re-implemented. Primary sources, both practitioner-authored on robots-clean
ground: Hoheto's full game anatomy (note.com/hht/n/ne27d41e3e5a2, 2023-12) and Ros's era
memoir with dated timeline (note.com/ros_1224/n/n2d586b9fed53, 2024-12). **The dated lifecycle
of a venue-rule edge, end to end:** 2017-12 bubble divergence ~30% (FX had "almost no price
linkage" to spot) → 2018-02 SFD v1 FLAWED (closing orders also earned SFD → lossless open/close
loops; divergence re-expanded) → 2018-03 rule fix (widening closes penalized; "SFD sandwich"
5%-stuck regime emerges) → 2019-04 leverage 15x→4x (elasticity lost; 7-10% punch-throughs burn
boundary bots) → 2021-04 4x→2x (>15% divergences; SFD "no longer functioning" in hot markets) →
2023-04 rate change → 2023-12-01 Lightning Futures termination notice → 2024-03 abolition.
**Mechanics banked (transferable, the reason this entry exists):** (1) SFD price propagated
from spot with a LAG set by bitFlyer's internal ticker cadence (~1s, jittery, load-varying,
UNCORRELATED with spot/FX execution volume — i.e., venue infrastructure latency, not market
activity); winning bots modeled the VENUE'S CLOCK (next-ticker-timestamp prediction, delay-
tuned order/cancel around the reflection instant), not the market. (2) Late-stage ecology:
after retail flow dried up, surviving bots switched TARGET to other SFD bots (delay-cancel
feeding: leave the stale-priced order up until just before the new SFD price lands, so
mistimed competitors eat it) — a boundary game converges to bot-vs-bot predation, and
published-logic copies died first (Hoheto: note-copied bots "stopped with losses early";
リメンバードテンくん). (3) Rule-asymmetry exploit: rewards paid on NEW-position orders only →
hold a standing SHORT and trade pseudo-long via 両建て so closes become rewarded opens —
when a venue rewards only new-builds, inventory accounting converts flow type. (4) Both
documented counter-strategies FAILED per the practitioners themselves: spot-manipulation bots
(現物操作組) and spot-book-watcher bots (現物板観測組) "never profited much and withdrew"
(fills too rare, inventory PnL dominated); anti-observer spoof bots (0.001-lot flicker on the
spot book) existed just to poison them. (5) Attribution humility, SECOND JP instance of the
misattributed-edge class (after C62's ML-vs-ATR-limit): Hoheto's own verdict — "the profit
source was probably not the prediction model but the delay-tuning asymmetry" (cut it fine when
receiving, leave margin when escaping). **Standing implication:** the transferable residue is
the SFD-CLASS PROBE — wherever a venue computes a threshold fee/trigger from a THROTTLED
derived reference (mark price, index, premium index, liquidation trigger), the boundary carries
a venue-clock lag game and a reward-asymmetry surface; audit the CADENCE, not the formula
(→ prospector_watchlist card 2026-08-04). Era lexicon banked to operator library. Any future
"SFD revival" claim is pre-falsified: the product is gone.

## `jp_intraday_anomaly_pair_hourly_mark_and_24hlag` — Hoheto's two BTC intraday anomalies

**ONE COMMUNITY-DOCUMENTED DEATH + ONE DESK-SCREENED WEAK (JP frontier miner s1-on-branch,
2026-08-04).** Source: Hoheto's own decay analysis (note.com/hht/n/nb0aa4844014b, 2022-12,
Binance BTCUSDT minute bars). (a) **HOURLY-MARK REVERSAL** ("enter at :01 against the prior
5-min move, close +25min" — mechanism prior: on-the-hour position cycling by large players +
inago followers): worked ≥2019 through 2022-03 — SURVIVED the 2019-20 doldrums AND the COVID
crash — then DIED ~2022-04, before LUNA (not the crash's fault); :01 entry now negative,
:02-:05 marginal. Author's honest cause: unknown ("fuzzy in, fuzzy out"). Free falsification
harvested per charter §9 — do not spend a desk test slot re-deriving this without minute data
and a NEW mechanism reason. (b) **24H-LAG BAR CONTRARIAN** (bar return negatively correlated
with same bar 24h prior; Hoheto validated at 1h/2h/4h/6h bars, still alive 2022-11): DESK
Stage-A SCREENED this run at the 8h-bar cell (the only bar size in our lake; exact-timestamp
24h shift, single-source Binance-UTC H8, no cross-source alignment risk). BOTH pre-declared
cells logged, both POWERED: full-sample 2019-09→2026-06 n=7407 IC +0.0073 reversal-Sharpe 0.1
→ SCREEN-WEAK; post-2024-04 n=2412 IC +0.0275 momentum-Sharpe 0.3 (SIGN FLIPPED vs the 2022
contrarian reading, still under every floor) → SCREEN-WEAK. No clock. HONEST BOUNDARY: the
1h-6h cells Hoheto validated remain UNTESTED here (no hourly lake); this entry kills the 8h
construction and records the finer cells as open-but-unpromising (the post-2024 sign flip is
evidence the family decayed, consistent with (a) and with 12H ATR-reversion dying 2024-03).

## `jp_atr_limit_reversion_timeframe_migration` — the richmanbtc ATR-limit family's dated decay chain

**FAMILY DECAY CHAIN COMPLETED 2026-08-04 (JP frontier miner s1-on-branch; extends the
fee-artifact-class C62 kill with the community's own post-mortem).** Source: chanta
(qiita.com/chanta/items/158f0d2b63afa2e6935b, Advent Calendar 2024 day 22) — a LIVE-TRADED
decay record with dates. The original 15m-bar richmanbtc ATR×0.5 limit-reversion: community
consensus "no longer works" by 2023 (and the desk's C62 kill showed its tutorial-era profit
was maker-rebate + KFold leakage anyway). chanta's 12H-BAR VARIANT (ATR(6)×0.21-0.25 both-side
limits, Bybit, POSITIVE fees 0.02-0.04% modeled — so NOT the C62 fee artifact): backtest
profitable 2022-mid→2024-03, run LIVE 2023-12→2024-03 including a 90%-win-rate month
(2024-01), then "the market completely changed from 2024-03" — dead since. **The family
MIGRATES ACROSS TIMEFRAMES rather than dying globally (15m→12H→?), and each incarnation's
death is a dated regime marker. 2024-03 is now a TRIPLE JP era boundary: SFD abolished + 12H
ATR-reversion died + pre-halving regime shift.** Standing implication: (1) any "revived
richmanbtc-style" claim must name its bar size and post-2024-03 evidence or it is pre-falsified;
(2) the migration pattern itself is weak-signal-registered (NOT a card — no mechanism for
WHICH timeframe hosts the band next); (3) corroborates the desk's low-pass lesson from the
other side — the hours-band reversion pocket existed for years AFTER daily-resolution price
alpha died, and closed ~2024-03.

## `cn_aigu_probitforge_unresolvable` — two principal-named CN sources that do not resolve to any address

**KILLED 2026-08-11 (brain-hunter seat, §33 conversion of data_axis_watchlist card 22).**
MECHANISM OF DEATH: unresolvable pointer, not disproven content. Four independent searches
(English descriptive, English exact-handle, Chinese descriptive `爱谷 AI 量化 加密货币 实验室
多智能体`, Chinese practitioner-corpus) return no entity named **aigu** (claimed: CN AI crypto
quant lab, transparent paper trading, multi-agent experiments) or **ProBitForge** (claimed:
engineering posts on AI-driven crypto research systems). The only near-name is ProBit Global —
a TERMINATED exchange whose own help centre warns that accounts claiming its name are scams, so
the name-space is an active impersonation surface. A miner pointed at an unresolvable handle
either fabricates a source or silently mines nothing while coverage records EXPLORED — both
worse than an honest kill (WS-005: absence must never resolve to a clean verdict; this entry IS
the not-measured verdict, recorded durably). **THIS IS NOT A CLAIM THE SOURCES DO NOT EXIST** —
a WeChat 公众号, private Telegram channel or very new handle would produce exactly this result.
**RE-ENTRY CONDITION (L1.16a, named):** one line from the principal — a URL or exact platform
handle — re-opens immediately as `pending-verification`; nothing else is needed.

## `eodhd_paid_vendor` — EODHD.com $100/mo data subscription

**KILLED 2026-08-11 (brain-hunter seat, §33 conversion of data_axis_watchlist card 25).**
MECHANISM OF DEATH, three independent strikes: (1) **L1.11** — the moat is the transformation
pipeline, never a purchased dataset; commercial data purchase is constitutionally barred; (2)
the **free-first prerequisite is unmet** — paid is permitted only by the evidence-gated
exception AFTER a documented free hunt fails, and no free hunt has ever been run on the equity
axis this vendor would serve; (3) **for crypto it adds zero** — every series the desk uses is
already free and keyless from Binance; the provenance poster's own sentence ("I purchased the
data for $100 monthly and it just expired") is the reproducibility argument against renting.
WHAT SURVIVES THE KILL: reading EODHD's public coverage documentation as a FREE INDEX of what
data exists (validated technique, Search Operator Library) — no subscription required.
**RE-ENTRY CONDITION (named):** the desk expands to an equity/cross-asset book AND the
documented free hunt on that axis fails at the charter bar; then the evidence-gated paid
exception may be argued on its merits.

## `lit_hourly_copula_pairs_netneg` — copula/cointegration crypto pairs at HOURLY resolution (literature prior, interior-verified)

**KILLED 2026-08-12 (litminer run 6, arXiv sweep — literature prior, not a desk test).**
MECHANISM OF DEATH: gross-per-trade below cost drag at hourly signal cadence — structural, not
statistical. Independent near-replication of the Tadi–Witzany family ("Adaptive copula-based
pairs trading with market overlay", QFE 10(2) 2026, aimspress.com/article/doi/10.3934/QFE.2026016;
10 Binance USDT perps, HOURLY, 2021-01→2023-12, **funding modeled**): all three market-neutral
variants NET-NEGATIVE — Conservative −14.3% total / Sharpe −3.67, Balanced −16.3% / −3.29,
Moderate −15.4% (interior table extracted 2026-08-12 via the stdlib PDF extractor; /tmp copy of
PDF from run's fetch). Cost-sensitivity table is the kill's teeth: **net-negative at EVERY
round-trip cost tested, including an optimistic 0.04% (−9.4%, Sharpe −1.88)** — raising entry
thresholds to extreme deviations does not flip sign; authors' own diagnosis: "core mean-reversion
signal has a low signal-to-noise ratio after costs". Corroborated by JSAI 2020 (Ohwada–Suzuki,
J-STAGE 10.11517/pjsai.JSAI2020.0_2L4GS1305): crypto cointegration relations are unsustainable.
STANDING IMPLICATION: the stat-arb family's live region (if any) is **5-min-or-faster** — the
Tadi–Witzany 5-min claim (Sharpe 3.77, funding UNMODELED) is the only positive rung left and is
run-6 card 1's screen target, carrying this kill as its prior. Hourly copula/cointegration pairs
proposals are pre-falsified; a re-entry needs a NAMED cost or venue change (L1.16a).

## `lit_polymarket_15min_binary_ml` — fast Polymarket-vs-spot microstructure ML (author's own honest negative)

**KILLED 2026-08-12 (litminer run 6 — literature prior, author-published negative).**
MECHANISM OF DEATH: the prediction-market book already impounds spot microstructure at short
horizon. OpenMarket (arXiv 2607.26245): walk-forward logistic over 43 Binance-microstructure
features on Polymarket 15-min BTC binaries does not beat the venue's own order-book-implied
probability; simulated trading nets **−0.116 normalized payoff units per attempted trade** under
stated fees/slippage. Resolution-adjacent bot flow patrols the fast end (practitioner
corroboration: cryptodaily.co.uk 2026-07 desk note). STANDING IMPLICATION: do not propose fast
(≤15-min) Polymarket-vs-spot constructions; the seam's only live region is long-maturity /
low-probability threshold contracts (run-6 card 3, Portnaya wedge — different mechanism:
regulatory segmentation, not speed). Also one more datum on the ML-wrapper shelf: 43 features
add nothing over a liquid venue's own mid.

## `lit_liquidation_csd_alarms` — per-event liquidation-cascade early-warning from critical-slowing-down

**KILLED 2026-08-12 (litminer run 6 — literature prior).** MECHANISM OF DEATH: event
heterogeneity — no variable is event-invariant. arXiv 2607.27070 (seven BTC cascades 2022–2025
incl. 2025-10-10 $19B; 39 configs/variable/event, placebo-controlled): variance/lag-1-autocorr
(CSD) ramps fire in 5/7 events and are SILENT in exactly the exogenous-news crashes; the
celebrated Oct-2025 reading is "the outlier, not the rule"; cascades behave as shock-driven
discontinuous transitions. Any desk "cascade early warning" keyed on price/leverage
variance-autocorrelation inherits this kill unless it can classify endogenous-vs-exogenous
ex ante (unobservable). SURVIVOR CLAUSE (rails-only, never alpha): the one population-level
signal that survives placebo is pre-cascade taker order-flow variance COMPRESSION (Fisher
p≈5e-6) — desk holds taker-flow + tick liquidation feeds to check it; legitimate consumer is
the ruin-rail sizing prior ONLY.

## `lit_intraday_ohlcv_mnq_14of14` — intraday OHLCV signal families at 5-min (cross-instrument prior extending 420/0 downward)

**KILLED 2026-08-12 (litminer run 6 — literature prior, instrument ≠ crypto: recorded as strong
cross-instrument prior, not a crypto measurement).** MECHANISM OF DEATH: gross-per-trade an
order of magnitude below friction. arXiv 2605.04004 (Mesfin): 14 OHLCV signal families × 947
days of 5-min MNQ 2021–2025, walk-forward OOS, positive controls INCLUDED and detected (RTH
Confluence t=5.83; London-B t=5.15) — **0/14 families clear 2-pt round-trip friction** (max
gross 0.07–1.50 pts/trade). Closes the "maybe intraday price-only survives" flank the desk's
blind-rediscovery memory left open ("price-only alpha is dead really = no SLOW price alpha at
daily resolution"): now also dead at 5-min OHLCV on an index future, by a harness that proved
it could detect real edges. Crypto-side intraday price-only proposals carry this + the desk's
own 420/0 as compound prior; the surviving intraday exceptions on the desk's record are
FLOW-conditioned (quarter-hour imbalance, card 2), never price-only.

## `lit_retraction_wave_2026_datestamping_naeem` — crypto-empirics retraction wave, wave-2 extension (provenance shelf)

**RECORDED 2026-08-12 (litminer run 6, Retraction-Watch divergent ground — provenance kill, not
a mechanism kill).** Delta beyond LIT_a F8's Dec-2025/Jan-2026 Lucey/Elsevier cluster:
(1) **Corbet–Lucey–Yarovaya "Datestamping the Bitcoin and Ethereum Bubbles" (FRL 26, 2018) is
RETRACTED** (notice sciencedirect.com/science/article/pii/S1544612326000140) — the GSADF/PSY
crypto bubble-datestamping citation classic; mechanism: compromised editorial process
(receiving-editor-on-own-paper pattern), not adjudicated data fraud — the empirics are
unciteable either way. Any bubble-dating prior sourced to it is orphaned; GSADF-on-crypto
literature is UNVERIFIED until independently re-run. (2) **Rahman–Naeem–Yarovaya–Mohapatra
"Unravelling systemic risk commonality across cryptocurrency groups" (FRL 65, 2024) RETRACTED**
(notice .../S1544612326006756; reason text [SUMMARY-ONLY] — ScienceDirect 403s this box;
preprint SSRN 4366570) — extends the wave into the hyperprolific Naeem/Yarovaya connectedness
cluster. STANDING IMPLICATION: FRL/connectedness-genre crypto empirics carry a provenance
discount on top of their zero desk mapping; NEXT-GROUND holds the mechanised version (pull the
public Retraction Watch/Crossref dataset, grade editorial-process vs data-fraud — the discount
should differ by class).

## `era_selfref_mark_liquidation_796` — liquidation against the venue's own unanchored last-trade (796, 2013-12) — the 插针 lore's birth-class, dead at tier-1, residue on thin-index tails

**RECORDED 2026-08-12 (CN frontier miner, era-archaeology, 8btc 2013-12 ban-window board page).**
Source: 8btc thread-2352 「关于796离奇爆仓事件」 (2013-12-24, Wayback 20140328095543id_, GBK), OP
小排量板车 + **moderator 大头 corroborating with his own case in-reply within 4 hours** — two
independent accounts, one thread; OP cross-posted from btcicc.com/article-302 (dead site, logged
as era ground). **The incident:** on 796 (the era's main CN BTC futures venue), "MT当前行情价最高
没有高过730，当时796交易价格一路从710涨到782. 账户在762价格离奇爆仓" — MtGox spot never exceeded
730 while 796's own book ran 710→782; the OP's short liquidated at 762; OP alleges 机器人+对敲
(bots + self-matched prints). **The moderator's case is the richer document:** weekly LONG in
profit → "找不到对收盘" (matched-book venue, NO exit liquidity) → hedged with an intraday SHORT to
lock the profit → **the hedge leg liquidated** when 796 decoupled "tens of dollars" from MtGox —
"我当时一直盯着mt的k线在看盘" (he was watching the reference venue while his liquidation trigger
read the internal price). **Mechanism class, three failure modes in one incident:** (1)
liquidation trigger = the venue's OWN last-trade with no external anchor ⇒ whoever can push a thin
internal book harvests the liquidation bands at will and the price snaps back — the manipulation
cost is bounded by book thinness, the harvest by open interest; (2) offsetting positions across
contracts at one venue are NOT a hedge when each leg margins independently against that
manipulable internal price — cross-contract basis blowout kills one leg of a "locked" book (the
desk's NOMUSDT/dead-man mark-vs-fill lesson, 13 years earlier); (3) the trader's reference series
and the venue's liquidation series were different numbers, and only one of them settles.
**Why this is pre-emptive falsification:** index-composite mark-price marking at every modern
tier-1 venue exists precisely to kill (1) — any "liquidation hunt via last-price manipulation"
claim on a tier-1 book is dead at source; do not spend a test slot on it. **The residue that is
NOT dead, named:** (a) thin INDEX CONSTITUENTS on tail perps — moving a thin constituent moves
the index itself (§42's low-OI-tail ground; the credibility-ceiling flag in the tail screen
already guards the data side); (b) failure mode (2) is alive wherever margin is per-contract
(isolated margin, cross-venue two-leg books) — corroborates the both-legs-same-way accounting law
from the era side; (c) lexicon: this incident class is the birth context of 插针 (wick/stop-hunt)
and 狗庄-in-derivatives vocabulary. SOURCE: as above. DERIVES-FROM: NONE (checked — forum-native
first-person accounts; the btcicc cross-post is the OP's own text).

### era_crossvenue_fiat_premium_arb — SEVENTH INSTANCE (CN 2013, mainland side) — VENUE-CREDIT SHARE + DEMAND-DIRECTION VARIABLE + BOTS-FIRST PRIOR

**RECORDED 2026-08-12 (CN frontier miner, era-archaeology: 8btc 2013-12 ban window + 94-era
follow-up).** Sources, all Wayback id_ GBK reads: thread-1983 「btc-e.com——搬砖的第一站」
(2013-12-06 OP, replies through 2015-09; 20170207105349), thread-2353 「浅议比特币对目前中国
外汇管制体系的影响」 (2013-12-24 repost of a 比特时代 analysis; 20131226235233), thread-73825
(Bitfinex CEO/BVI profile, 2017-09; 20171021031939), thread-1940 (赵东 interview, 2013-12-08;
20131208153930). **(a) CN mirror of instance (a)'s Gox↔BTC-e route:** btc-e pitched as the cheap
external leg ("让外盘和国盘价格拉近"); its persistent DISCOUNT read by practitioners as
hard-fiat-leg friction ("几百元人民币先转美元再转充值平台，还有每天的限额", 2015) plus venue
credit risk — moderator capeta 2014-11: "btc-e最近有点问题，搬砖的话要注意异常情况"; the venue
was seized 2017-07, so the discount's collectors were accumulating balances at the venue that
vanished. Identical lesson to the Gox instance, CN-voiced, opposite side of the same route.
**(b) BOTS-FIRST PRIOR, practitioner-stated (2014-11):** "肯定是因为不好搬。所以机器人才不愿意
去吧？" — a VISIBLE persistent spread implies an INVISIBLE barrier because bots already took every
easy route. The family's efficient-barrier corollary from the era's own mouth. **(c)
DEMAND-DIRECTION VARIABLE (the SAFE analysis):** SAFE's control surface is the BANKING channel
("SAFE是大脑而各家银行是触手"); BTC bridges it in BOTH directions, and the 2013 document's binding
use case is INBOUND (foreign USD→BTC→CN exchange→CNY, evading per-transaction 结汇 limits in the
RMB-appreciation era) — the mirror of 2016-17 OUTBOUND flight. So the family's sign law gains its
second variable: **barrier SIDE sets who pays the rent (5th instance); NET BRIDGE-DEMAND
direction, itself a function of currency expectations, sets the premium's sign and magnitude.**
**(d) 94-rail enrichment of the 5th instance:** Bitfinex was named the successor venue a week
before the ban's full force ("萬一交易所被關了，不用擔心還有Bitfinex") BUT "不支持人民币充值提现"
— the exit rail had NO fiat leg, which is WHY the 承兑商 network (birth dated 09-16/17 in the 5th
instance) had to exist: coin moves through the venue, fiat moves through people. Plus: offshore
maker-taker vs domestic 0.2%-flat fee regime (post-freeze), Bitfinex phishing clones in the
migration window, 求翻墙 as standing access friction, and 赵东's Dec-2013 leveraged-holder origin
document (the future largest 承兑商 enters the record as a 2000-BTC hodler — the canonical arc:
leveraged holder → 2014-15 blowup → rebuilt as the market's fiat rail). **Standing implication
unchanged:** persistent premium = barrier rent, information/timing only, never sized as arb. This
does NOT reopen axis #76 (USDT-CNY OTC premium, screened 4/4 cells 2026-07-26, no promotable
edge); re-entry needs a named enabling change per L1.16a.

### era_crossvenue_fiat_premium_arb — EIGHTH INSTANCE (RU 2013-14, dealer fee-ladder) — DEMAND-DIRECTION SIGN PRICED ON A MENU + LEGAL CAPACITY CAP

**RECORDED 2026-08-12 (RU frontier miner s2-on-branch, era-archaeology: forum.btcsec.com
obmen/birzha class, Wayback id_ UTF-8 reads).** Sources, all mined to reply-depth: topic 3426
(MRaven BTC-E-code exchanger ladder, Samara, Dec-2013; 20140924id_), topic 6157 (EXMO launch
thread as exmoney.com, Feb-2014; 20140701id_), topic 5848 (exchanger thread + impersonation-scam
dispute, Feb-2014; 20140709id_), topic 2047 (btc-trade.ru auto-exchanger, Sep-2013;
20140813id_). **(a) THE 7th INSTANCE'S DEMAND-DIRECTION VARIABLE, PRICED ON ONE DEALER'S MENU
(sharpest form yet):** MRaven's simultaneous two-sided ladder — BTC-E **RUB codes IN: customer
RECEIVES a premium** ("от 3% премия"; verified in reply 6: paid 9,000 RUB → received 9,090 in
codes = +1%), **RUB codes OUT: 7% commission**; USD codes near-symmetric (IN 2.5%, OUT 0-0.5%).
One instrument, both directions, priced at one instant: the rent's SIGN and MAGNITUDE follow net
retail flow PER CURRENCY-LEG (RUB leg one-directional cash-out post-Nov-2013 top; USD leg
balanced). The CN 7th instance derived this variable from a policy analysis; here it sits on a
dealer's price list. **(b) THE LEGAL CAPACITY CAP — why the rent could not be arbed away:** RF
e-money law capped anonymous e-wallet payments at **15,000 RUB single-payment** with >100k RUB
transactions subject to up-to-72h review (EXMO launch thread, primary); exchanger floats were
tiny (a 15k RUB trade EXHAUSTED one dealer's reserve, 5848; "price QIWI at 2% and you will be
refilling the deposit nonstop", 2047) — per-transaction legal caps × per-dealer float = rail
capacity bounded BY CONSTRUCTION, so the premium persists at exactly the size that cannot be
institutionalised. §42's "too small for funds" ground, in its 2013 form. **(c) RENT
DECOMPOSITION GAINS A FRAUD TERM:** the rail carried organised counterparty fraud —
impersonation infrastructure (fake Skype handles one glyph off the dealer's: mraven/nigmar/
lmksar-vs-imksar; the coinbox scam), the two-account manipulator pattern (clean handle for
reputation, dirty twin for theft), and "grateful testimonials serve as scammers' target lists"
(5848 reply 14). Part of the 2.5-7% spread is an expected-fraud-loss premium, not pure barrier
rent. Rail-share census number: ~60% of withdrawals requested to QIWI, ~20% Sberbank (5848
reply 16). Venue-side fee baseline: EXMO fiat rails 2.5%/side vs 0.8% WebMoney private-transfer
baseline, trade fee 0.2%, crypto withdrawals at network cost (BTC 0.001). Rail latency: BTC-E →
card ≈ 20 min + 10 min after a manual name-confirm step (2047). **Standing implication
unchanged:** persistent premium = barrier rent, information/timing only, never sized as arb;
nothing here reopens axis #76 (L1.16a).

### era_crossvenue_fiat_premium_arb — NINTH INSTANCE (KR 2017-12→2018-02, mania+ban window, primary text) — NATIONALITY-SELECTIVE MEMBRANE + PREMIUM DISPERSION AS A FRICTION SURFACE

**RECORDED 2026-08-12 (KR frontier miner s2-on-branch, era-archaeology: Ppomppu 가상화폐 board,
era-seek per OP-021 KR — site search robots-forbidden, post-no binary search).** Sources, primary
era text, threads mined to full comment layer (archived data/ppomppu_kr_era_threads.jsonl; title
tape 2,130 rows in data/ppomppu_bitcoin_era_map.json): no 22072 (12-24, premium supply chain),
22069 (12-24, congestion), 55179 (01-12, token premium), 77951 (02-01, 환치기 legality), 76535
(01-29, beehive kill), 54482 (01-12, rail workarounds), 77829 (01-31, bots), 51139/54653/78040
(tooling + flow + folk tape). DERIVES-FROM: news threads quote Yonhap verbatim (76535, 76972);
every mechanism comment is folk-original, cites nothing (checked). **(a) THE BARRIER IS A
NATIONALITY-SELECTIVE MEMBRANE, NOT A WALL:** resident outbound remittance capped ~$50-60k/yr
(attested twice, 77951: "년에 6만불 제재", "송금은 연 오만불 한도") while FOREIGN NATIONALS
legally carry coins in, sell the premium, file a source-of-funds declaration and exit KRW
**unlimited** ("외국 큰손들은... 코인만 집어넣는거죠... 출금은... 무제한"; the Japanese
gold-carry precedent cited in-thread). Extends the 8th instance's legal-capacity-cap: the cap is
priced PER NATIONALITY, which names the marginal arbitrageur (foreign-KYC banking capacity, not
domestic capital) and explains 40%+ persisting for weeks — the legal channel was capacity-bounded
by non-resident won-account issuance, precisely the §42 too-small-for-funds shape. **(b) PREMIUM
DISPERSION IS A FRICTION SURFACE WITH TWO AXES, folk-stated as rules:** per-COIN — dispersion ∝
transfer friction: ERC-20 tokens arb tight ("토큰이라서그래요" — why EOS/BTG premium was LOW,
55179) while congested-chain coins ride wide (mempool congestion throttles the 보따리상
coin-carry supply pipe: "코인들 전송이 안됩니다... 수요는 높은데 공급이 낮아", 22072; same-day
title tape shows EOS 9-25% vs XRP 34%); per-VENUE — dispersion ∝ rail state: "지갑 없이
신규상장시 타거래소보다 매우 높은 시세" (deposit-closed listing = 가두리 captive market, stated
as a RULE with live example BTG-Coinone 66, 22072); the real-name law bound each big-4 venue to
EXACTLY ONE bank (Upbit-IBK, Bithumb-NH — 76756/76863) so bank-level throttles create
venue-level basis; the beehive-account kill (01-29) forced captive users at rail-terminated
venues into mass selling — the frozen-leg discount, CN 5th-instance sign law's KR instance
("중소거래소 거래하던 사람들이 집단 매도하면서 일시적 하락세", 76535). A market can be fenced
ON PURPOSE (venue lists without wallets) or BY ACCIDENT (bank terminates the rail): same
mechanism, opposite premium signs — fenced-DEMAND pumps, fenced-EXIT dumps. **(c) BOTS-FIRST
PRIOR CORROBORATED IN A THIRD ECOSYSTEM, WITH SPOOF TEXTURE:** per-second fake-wall bots
(허매수매도벽) pegging KR books premium-adjusted to global charts by 2018-01 (77829: "봇들도...
해외 차트 맞추는거라"), a dawn bot-lull, and folk suspicion the venue itself ran them — later
prosecuted (Upbit wash-volume case), so era KR volume figures are UPPER BOUNDS on real flow.
**Modern spin routed to prospector_watchlist (EV 0.0061 QUEUE, novelty 0.772):** per-coin
rail-state transitions are COLLECTED LIVE by the desk's venue-state layer (data_axis_watchlist
card #26) — the era evidence supplies the screen design that row still owes. **Standing
implication unchanged:** persistent premium = barrier rent, information/timing only, never sized
as arb; the KR premium remains usable exactly as the desk uses kimchi — a signal, not a trade.

---

### era_crossvenue_fiat_premium_arb — TENTH INSTANCE (CN 2013-12 ban window, mainland onramp workflow, primary text) — MARGINAL-ROUTE COST STACK + OKPAY-RESERVE CROSS-REGION CORROBORATION + ANNOUNCEMENT-VS-ENFORCEMENT TIMING

**RECORDED 2026-08-19 (CN frontier miner s9, era-archaeology: 8btc board-2 ban-window page read
with the OP-071 low-page selector — validated on first use; coinsbbs.com thread-120 mined all 8
pages / 70 posts; btcicc.com article layer opened).** Sources, all primary era text via Wayback,
GBK: 8btc thread-1983 "btc-e.com——搬砖的第一站" (2013-12-06, the day after 银发〔2013〕289号;
btc-e framed as the cheap foreign leg, the arb as "让外盘和国盘价格拉近"); coinsbbs thread-120
(the tutorial's full version, replies 12-06→12-15); btcicc article-237 "比特币 高级搬砖系列一"
(captured 2013-12-13); 8btc threads 1944/1950/1951 (12-05, hours after the notice, replies to
12-06). **DERIVES-FROM: NONE (checked)** — the btcicc tutorial is an original how-to with the
author's own registration screenshots and referral code; coinsbbs's likewise (images hosted on
coinsbbs itself); neither cites the EN Bitcointalk literature; the 8btc policy threads quote the
notice text and named CN commentators (龚明/长铗), and the folk replies cite nothing.

**(a) THE OKPAY-RESERVE BOTTLENECK IS NOW CORROBORATED FROM BOTH SIDES OF THE BARRIER,
INDEPENDENTLY.** The FIRST instance (Bitcointalk 171349 #39, EN, 2013) named "Gox had low OKPAY
reserves" as the real constraint. This CN mainland tutorial — original by construction — documents
the complete CNY onramp (银联/UnionPay → rchange.net, a HK e-currency dealer → OKPay, a Cyprus
PSP with real-name KYC: passport/ID + address proof, ENGLISH TRANSLATIONS required, 1–2 working
days → BTC-e) and names the binding risk in the author's own words: "rchange人民币充值存在...
okpay资金储备的问题" (the dealer's OKPay float can run short). Genuine cross-region convergence,
provenance checked on both sides, on the mechanism's core: the premium is rent on PSP FLOAT +
KYC LATENCY + jurisdiction hops, and the marginal arbitrageur queues behind one dealer's reserve.

**(b) THE FREEZE BINDS AT THE RAIL CUT, NOT THE NOTICE.** The crowd read the payment-processor
scope correctly within HOURS (thread-1950, 17:50 on 12-05: restrictions bind 银行/支付宝/财付通,
not individuals; thread-1951 quotes 龚明: commodity-not-currency was the survival path — a
currency ruling would have imposed financial-institution licensing = "全军覆没"). Domestic
third-party payment rails were actually cut ~2 weeks later; the offshore stack in (a) was already
operational and became the marginal route. The board admin's 12-08 read: "对抄币影响并不大，就是
吓退了不少大妈" — little effect on trading, scared off retail. **Consequence for method: any
regulatory event study keyed to ANNOUNCEMENT dates mis-times the treatment by weeks; the
treatment is the RAIL-STATE change** (feeds card #26's venue-state design and the deferred
regulatory-event timeline card — same lesson the KR ninth instance carries from the enforcement
side).

**(c) CROWDING TIMESCALE IN MANIA IS DAYS, AND THE TUTORIAL IS ITSELF THE CROWDING EVENT.**
coinsbbs tutorial posted 12-06; by 12-07 a replier is already asking "貌似这几天MT大跌，说好的
差价呢" (spread gone); 70 unlock-replies in 9 days; the 8btc cross-post appears the same day the
tutorial does. A PUBLISHED banzhuan tutorial marks crowd arrival — the premium's decay clock
starts at publication. Retail-speed corroboration of the bots-first prior (7th instance).

**(d) NAMED-SCOPE LOOPHOLE, SPOTTED IN REAL TIME.** 289号 names ONLY Bitcoin; a 12-06 reply
(8btc thread-1944 post 6195) calls it immediately — "通篇只针对比特币，没有涉及莱特币等一大堆
密码学货币" — contrasting the Fed/ECB's "以比特币为代表的虚拟货币" drafting; by 12-09 altcoin
banzhuan is discussed as standard practice (coinsbbs post #375 "众多山寨币搬砖"). **A regulatory
action binds its NAMED instrument; the unnamed sibling inherits the flow** (routed to
weak_signal_registry WS-014; modern analog: token-specific enforcement actions).

**(e) THE ERA'S EDGE-DISTRIBUTION STRUCTURE, MEASURED — what era-archaeology can and cannot
recover.** The tutorial payload sat behind a 回复可见 reply-gate (never served to the crawler:
OP-088), the advanced version (thread-183, "another banzhuan site not known to people") behind a
member-tier gate (even its intro unarchived), and 搬砖群 QQ groups were "绝密" and full (12-06
reply). The PUBLIC layer of the era archive holds the ADVERTISEMENT of edges; the edges lived in
closed groups. Metadata (who/when/how many/how fast) survives; payloads survive only where
cross-posted or ungated — btcicc's article layer is the ungated exception, which is what makes it
the next dig target. **Unreadable-named (zero Wayback captures): 8btc 1989 (TOP100/TOP1000
holder-concentration analysis, 12-07 — era whale-watching methodology) and 1973.**

---

### hijri_ramadan_calendar_axis (AR frontier miner, 2026-08-12) — `unmeasurable_by_construction`, **NOT refuted**

_Filed under the `unlock_events` precedent: UNMEASURABLE and DEAD are different verdicts and only one
of them retires search space. This entry retires a **method**, not the mechanism._

**THE CLAIM (published, not folk):** *"Ramadan effect in the cryptocurrency markets"*, Review of
Behavioral Finance 14(4):508 (2022), DOI `10.1108/rbf-09-2021-0173` — significant Ramadan return
effect for ETH/XRP/XLM/BNB, BTC under AR(1) only, none for LTC, no volatility effect.
**DERIVES-FROM:** Białkowski, Etebari & Wiśniewski (2012, *JBF*) "Piety and Profits" — the equity
Ramadan anomaly, which the crypto paper explicitly extends. **It is an ECHO of one equity literature,
not an independent discovery, and therefore elevates nothing** (GAP #85).

**COSTS: NOT ACCOUNTED.** No fees, funding, slippage, spread or impact anywhere; no strategy is
tested — only the significance of a calendar **dummy**. Per WS-006 this is a *different quantity*
from the desk's, not a weaker one.

**MECHANISM (the strongest available form, so the kill is not aimed at a straw man).** Sharia rulings
consistently prohibit derivatives, deferred settlement and margin (*gharar*/*maysir*/*riba*) — the
fatwa formula «مع التقابض الفوري وتحريم التداول الآجل والمشتقات» — making an observant pool
**spot-only by construction**. The pool does not switch instruments during Ramadan (it never held
perps), so the only coherent channel is a change in its **activity level**; the sharpest version is
**zakat**, a mandatory 2.5% annual wealth levy applied to crypto by most contemporary rulings and
commonly discharged in Ramadan — a genuine obligation-bearing forced flow at a calendar-predictable
date, landing **spot-side** and therefore in **funding/basis** rather than direction. MENA is a
material 7.5% of global on-chain value received ($338.7bn, Chainalysis 2024), 93% of it in $10k+
transactions.

**DESK TEST — `data/ar_ramadan_power_check.json`** (BTCUSDT D1, 2019-09-09→2026-08-12, 2,530 days,
208 Ramadan-days, **7 episodes**; moon-sighted windows ±1d by jurisdiction):

| channel | naive daily t | episode-level t | ICC | design effect | observed vs 80%-power MDE |
|---|---|---|---|---|---|
| return | −0.561 | −0.948 | 0.000 | 1.00 | −0.142 %/day vs 0.493 → **0.29×** |
| funding | +1.314 | +0.691 | 0.525 | 16.07 | +0.627 bps/8h vs 2.982 → **0.21×** |
| basis | +1.165 | +0.574 | 0.695 | 20.96 | +0.696 bps vs 3.989 → **0.17×** |

**WHY THIS IS A METHOD KILL AND NOT A MECHANISM KILL.** All three channels are null and the return
sign is *negative* (opposite the published claim) — but **n=7 cannot detect anything real**: the MDE
is 3–6× the observed effect, requiring **≈+0.49%/day (≈500%/yr)** on returns to clear. **It does not
improve with patience:** MDE scales 1/√n, so halving it needs **28 episodes = 21 more years**. An
annual event is **permanently underpowered as an annual event study**, and no forward clock fixes
that. L1.25 in full: this is not evidence the effect is absent.

**RETIRED:** the *annual-event-study design* on any Hijri-calendar axis. **NOT retired:** the
mechanism. The only enabling changes (L1.16a) that reopen it are (a) **cross-sectional** — many
assets/venues where MENA exposure varies, turning 7 events into 7×N cells, or (b) a **within-Ramadan
daily-structure** test, which must clear the clustering problem below.

**THE TRANSFERABLE FINDING — and a refutation of the seat's own critique, recorded because the
self-correction is the evidence.** I predicted the published result was an artifact of counting
Ramadan-DAYS as independent (gap row 85: *count events in the world, never readings of the world*).
**On returns that is REFUTED — ICC = 0.000**, so a daily dummy on returns is roughly honest and the
paper's method is not broken the way I claimed. **On persistent series it is severe:** funding ICC
0.525 and basis ICC 0.695 give design effects of **16 and 21**, inflating a naive daily-dummy t by
**≈4.0× and ≈4.6×**. The standing rule:

> **Any calendar/event test on a PERSISTENT series (funding, basis, OI, spread) must cluster at the
> event level — a daily dummy inflates t by ~4× on this desk's own data. On returns (ICC≈0) it does
> not.** The error depends on the SERIES, not the TEST, which is why it is invisible on inspection.

This binds the desk's whole EVENT-AND-CALENDAR family, where funding and basis are precisely the
direction-agnostic targets the desk should prefer (129/129 directional mechanisms failed, 2026-08-01).

---

## `mcpt_return_permutation` — a published "Monte Carlo permutation test" whose null cannot move its own statistic (BR frontier miner, 2026-08-12)

**PRE-EMPTIVE FALSIFICATION — a third-party validation method, killed before any desk time was
spent importing it.** Mined from `pedhsm/systematic-research-framework` (PT-BR, no licence),
self-described as a *"Biblioteca de validação de estratégias quantitativas implementando ETL, PCA,
Cointegração e testes de Monte Carlo (MCPT)"*. Its `mcp/tester.py` is the validation layer the whole
library reports through.

**THE DESIGN AS READ:** permute the **realised return series** (`rng.permutation(vals)`), recompute
the score, and report `p = mean(perm_scores >= real_score)`. The three available scores are
`sharpe = mean/std*sqrt(252)`, `cagr = exp(sum(r))**(1/years)-1`, and `vol = std*sqrt(252)`.

**WHY IT IS DEAD:** mean, std and sum are each **invariant under permutation**, so all three scores
are order-invariant and the permuted statistic *is* the real statistic. Verified numerically by
independent reimplementation of the arithmetic (not by executing the repo — supply-chain rule),
500 permutations × 4 synthetic return series: **max−min spread across permutations = 1.1e-15**,
i.e. machine epsilon.

**AND THE FAILURE IS WORSE THAN UNINFORMATIVE.** Floating-point summation is not associative, so
`perm >= real` resolves on rounding order and the p-value becomes a hash of FP dust rather than a
statistic. Measured: a strong winner (μ=+0.15%/d) scored **p = 0.978**; a catastrophe (μ=−0.20%/d)
scored **p = 0.618** — **the disaster outranked the winner.** At any conventional α nothing ever
passes. It is a **wall, not a bar** (L1.49), and the ordering it induces among candidates is pure
artifact.

**THE RULE THIS PRESERVES (L1.17 — the graveyard is sacred, and a failure with a named cause is
evidence rather than opinion):**

> **A permutation null must destroy the thing the statistic is supposed to measure.** Permuting
> realised strategy returns to test a Sharpe destroys nothing — the P&L has already been computed.
> The correct null permutes the **price path** and re-runs the strategy (killing timing skill while
> preserving the marginal distribution), or permutes the **signal** against fixed returns.

**THE DESK IS ALREADY ON THE RIGHT SIDE OF THIS, AND THAT IS THE POINT OF RECORDING IT.**
`libs/validation/bar_permutation.py` independently documents the identical trap (*"total log return
over the permuted window EQUALS the real total log return ... buy-and-hold scores identically on the
permutation and gets p ~ 1"*), permutes **bars** rather than returns, and handles the FP-dust ties
this repo falls into with a measured `_TIE_RTOL = 1e-4` and the add-one correction
`(sum(s >= real − tol) + 1)/(n + 1)`. Two ecosystems, **no citation link in either direction**,
same trap — one solved, one not. Per the provenance rule that is genuine convergence and it buys a
**queue place, not a lower bar**; here what it buys is **confirmation of an existing desk design**,
so the disposition is NO BUILD. Routed as OP-056 (the reusable invariance screen) rather than as a
repair, because there is nothing on this desk to repair.

**STATUS: DEAD ON ARRIVAL — never imported, never scheduled, no desk time owed.** Recorded so the
next seat that meets an "MCPT" validation layer in any language tests its invariance in one grep
instead of adopting it.

## 2026-08-12 — the public WorldQuant alpha101 lineage: three defects, DEAD ON ARRIVAL, never imported

**BRAIN hunter s2.** Provenance and licences as recorded in `search_operator_library.md` `wq-brain-pipeline`. Read as text, **nothing installed or run** (supply-chain rule). Recorded here so the next seat that meets an alpha101 reimplementation in any language spends one grep instead of an adoption.

**1. `decay_linear` BACKFILLS, and that is a look-ahead in the most-copied public alpha lineage.** The implementation cleans its input with a forward-fill *followed by a backward-fill* before computing the LWMA. **`bfill` writes a later observation into an earlier bar.** In a feature computed over a panel that is a mechanical leak, invisible in every result it contaminates, and it sits in a file whose own header credits the widely-forked `yli188/WorldQuant_alpha101_code` as its origin — so the defect is *inherited*, not local, and is likely present across that fork tree. The author's comment explicitly delegates the problem elsewhere ("the backtest engine should assure to be snooping bias free"); no engine can, because the leak is baked into the feature before the engine sees it.

**THE DESK IS ALREADY ON THE RIGHT SIDE OF THIS, WHICH IS WHY IT IS WORTH RECORDING.** `libs/alpha_factory/wq_operators.ts_backfill` is **forward-only by construction** and documents the refusal in its own docstring ("filling backwards writes a future observation into a past bar, which is leakage by construction"), plus a bounded `limit` so a dead series cannot masquerade as a live flat signal. Two lineages, no citation link either way, **same operator name, opposite handling of the same trap** — one leaks, one refuses. Per the provenance rule that is genuine convergence, and what it buys here is **confirmation of an existing desk design, so the disposition is NO BUILD.** Same shape as the qlib finding on 08-11 (negative-`Ref`-in-feature = mechanical leak kill).

*Residual honesty:* whether the **platform's** `ts_backfill` looks forward is **not established** — the official operator page is WALLED (route tried and failed, §13) and the community table says only "commonly used for backfilling missing data". A live trading platform cannot serve future data, so forward-only is the near-certain reading and it is the safe one regardless. **UNMEASURED is the honest verdict on the platform's exact semantics** (L1.28a); the desk's implementation is correct either way.

**2. The simulator silently ignores its own `neutralization` setting — a dead branch presented as a knob.** `post_processing` reads the setting into a local variable and then unconditionally subtracts the **universe** mean. `Sector`, `Industry`, `Subindustry` and `None` all produce **Market** neutralization, with no warning. A user who configures `neutralization: Subindustry` gets a different portfolio than the one their config describes, and the config file advertises all five values as valid. This is the desk's own most-hunted defect class in someone else's tree — read-without-consumer / dead-branch (L1.40), and `UNMEASURED-REPORTED-AS-OK`. **Consequence for us: any calibration against this simulator's group-neutralized output is void.** We ran none; the point is that a future seat might.

**3. Its PnL is GROSS — no fees, no slippage, no turnover charge anywhere in the loop.** Profit is the plain dot product of weights and next-day returns, scaled by a fixed $20M book. **No number produced by this simulator is a net number**, and none may ever be cited as one (L1.5: no alpha is valid until it survives realistic slippage, fees and impact). Note the irony that makes it worth writing down: the platform's *own* fitness metric divides by turnover precisely because churn is the dominant killer — and the community failure table puts LOW_FITNESS at 66.2% of rejections — yet the open-source reimplementation of it models cost nowhere.

**STATUS: DEAD ON ARRIVAL — nothing imported, nothing scheduled, no desk time owed.** The *semantics* extracted from this repo (pipeline order, `rank` scaling, `decay_linear` weights) are recorded in the operator library and stand on their own; the three defects above are why **no result, curve or Sharpe from this lineage is quotable**, and why the extraction was mechanism-only.

**USEFUL BY-PRODUCT — one structural fact worth keeping:** the platform's book is **$20M ($10M per side, dollar-neutral long/short)**, cross-checked two ways (the simulator's fixed `booksize`, and the community metric sheet quoting returns against $10M). That is their capacity calibration point, ~$6.7k average position across 3,000 names — **comparable to this desk's entire book.** Recorded as a fact about their process (L1.18a capacity parity: it makes their turnover and cost assumptions inapplicable here in both directions, not just one).

## 2026-08-13 — `rev_calendar_spread_iv_convergence` (BTC/ETH options): REFUTED AT SOURCE by its own author, with the code public

**JP frontier miner s4.** Free graveyard material — killed by the practitioner who built it and ran it live,
not by us. **SOURCE:** `perp-screener.com/posts/btc-bot`, 儲からないBTCオプションbot (「the BTC options bot
that does not make money」), 仮想通貨botter Advent Calendar 2025 day 16, posted 2025-12-04. Code public:
`bybit_rev_calendar_live`. **DERIVES-FROM:** Saxo Bank JP official channel (the calendar-spread explainer)
+ **ChatGPT** — see the provenance warning at the bottom, which is the more important half of this entry.

**THE CLAIMED MECHANISM.** A *reverse* calendar spread — buy the NEAR expiry, sell the FAR expiry, strikes
and right matched — held to harvest convergence of the near/far implied-vol difference. The author's stated
reason for choosing options at all is worth preserving independently of the kill (see the watchlist card):
option order flow carries more *intent* per trade than perp flow, because nobody buys
`BTCUSDT-5DEC25-96000-C` on a vibe.

**WHY IT DIES, AND IT IS STRUCTURAL RATHER THAN STATISTICAL.** The author's own greeks at a live snapshot:
delta ≈ 0, gamma ≈ 0, **vega negative, theta negative** (θ = −5.43). That combination has **no regime in
which both legs help**: quiet tape bleeds it via theta, and any vol event hurts it via negative vega — which
is precisely the state ("急落局面・イベント直前") where a crypto book most wants to be long convexity. He
describes the realised failure exactly that way: *"『IV差の収束を狙う』と言いながら、実態は「ベガマイナス
＋セータマイナス」を抱えたまま、相場が動かない時間に削られる"* — it was named as an IV-convergence trade
and was in fact two decaying legs. **A position whose two dominant greeks are both adverse is not an edge
awaiting better parameters; the label was wrong about what was being held.** Desk gates agree without
needing the anecdote: **EV 0.0000 REJECT** (`narrow_breadth` — BTC/ETH options are ~2–3 independent bets —
plus `crowded_known`), novelty 0.811 so this is an economics rejection, not re-tested ground.

**THE OPERATIONAL FAILURE MODE IS THE PART THAT TRANSFERS, AND IT IS NOT ABOUT OPTIONS.** The author names
the worst outcome explicitly: *"期近満期を跨いで放置 → 期近が消えて期先ショートだけ残る（これが一番危険）"*
— **hold through the near leg's expiry and the hedge VANISHES on a schedule, leaving a naked short.** The
general form is: *any hedged pair in which one leg has a contractual disappearance date is unhedged by
default, and the un-hedging is driven by the calendar rather than by the market.* This desk's live sleeve is
spot+perp and perps do not expire, so it is not exposed today — **but `publicGetExpiredFutures` was salvaged
for R0239 on 2026-08-01, and a dated-future-vs-perp basis trade has this exact failure mode.** If that is
ever built, the expiry of the dated leg is a **risk-rail event**, not a P&L event, and must be handled by
the rail rather than by the strategy.

**ALSO RECORDED — the author's blocker, which is a shopping-list item and a JP era marker.** He wanted to
backtest on historical IV and did not, because *"日本からBYBITグローバルが使えなくなるかも"* — Bybit Global
possibly becoming unusable from Japan (~2025-12). Two facts for the desk: **historical crypto option IV is
the named missing input** for anyone testing this family, and **a JP-access regime event lands ~2025-12**,
which joins the 2023-06-01 Travel Rule and the 2024-03 bitFlyer product replacement on the JP era timeline.

**PROVENANCE WARNING — THIS ENTRY IS ALSO THE FIRST RECORDED INSTANCE OF LLM-MEDIATED PSEUDO-CONVERGENCE.**
The greeks reasoning in the post is not the author's: it is introduced as *"チャッピーの解説によると"*
("according to ChatGPT's explanation"), and he twice tells the reader to ask an LLM instead of him
(*"詳細な解説はChatGPTなどに聞いた方がいい"*). **The mechanism analysis in this post is therefore NOT an
independent practitioner node** and must never be counted as one by `libs/research/convergence.py`. The kill
above still stands at full strength — it rests on his *realised P&L and his own greeks snapshot*, which are
observations, not on the LLM's commentary. → **OP-072**.

## 2026-08-13 — `jp_mlbot_atr_limit_reversion`: CORROBORATION ADDENDUM (independent, different venue, opposite fee sign)

**JP frontier miner s4.** The 2026-08-01 kill said the richmanbtc `mlbot_tutorial` edge was a **maker-rebate /
venue-subsidy harvest** (the fee was zero-or-negative across the whole backtest). A second JP practitioner
independently produced the complementary half of that evidence, on a venue where the maker fee is **positive**.

**SOURCE:** `qiita.com/pip_pip_pip_p/items/3b86e36ca536e99d26e0`, 「ルールベース戦略+MLフィルターが機能する
条件は？」, 2024-12-07, 仮想通貨botter Advent Calendar 2024 s2d8. **DERIVES-FROM:** the `mlbot` tutorial
itself (`note.com/btcml`) + López de Prado, *Advances in Financial Machine Learning* (triple-barrier). Not
independent of the tutorial — it is a direct critique of it — but **fully independent of this desk**, which
is what matters here.

**THE MEASUREMENT:** he plots the tutorial's rule-based core, **alone, on Binance BTCUSDT**, and reports it is
**up only in 2021 and down-sloping in every period since — including the bull tape of 2024-11/12**. The desk's
kill and this practitioner's curve are the *same fact seen from two venues*: on bitFlyer (maker ≤ 0) the rule
printed; on Binance (maker > 0 for retail) it does not, in any regime, bull included. **A strategy that
survives only where the venue pays you to quote is a subsidy harvest, and the cleanest possible confirmation
is that it fails where the subsidy is absent.** No change to the kill; its confidence rises and its stated
mechanism is now corroborated rather than inferred.

**AND THE HALF THAT IS NOT ABOUT THIS STRATEGY AT ALL** — his four desiderata for a rule-based base layer
under an ML meta-label filter, ranked by him as **② ≫ ③ > ④** with ① mandatory: ① abundant samples,
② **the TARGET's distribution is time-invariant**, ③ simple, ④ strong. His pointed observation:
*"mlbotチュートリアルでは特徴量の分布が時間で変化しないことをチェックしていますが、似たようなことを目的
変数に対して行うといいかもしれません"* — **the tutorial checks FEATURE-distribution stationarity; nobody
checks TARGET-distribution stationarity.** That is a live gap on this desk too and is routed to
`improvement_inbox.md`, not left in the graveyard. (His own claim that his filter rescues a down-sloping base
rule "thanks to property ②" is **unverified** — a practitioner assertion with no shared code or data, recorded
as claimed, never as evidence.)

---

## `zecontinha_eg_pairs_screen` — REFUTED AT SOURCE, by measurement, before any desk compute was spent
**Killed:** 2026-08-13, BR frontier miner s3. **Class:** STATISTICAL-ARBITRAGE (the desk's thinnest
family — `data/strategy_coverage.json`: THIN, n=1 of 14). **Tier:** EXECUTABLE (code + params + a live
deployment), which is why it could be settled in an afternoon rather than argued about.

**SOURCE:** `github.com/Vido/zecontinha` (Apache-2.0, 14★, 8 forks listed / 6 live, active 2019→2026-02),
live at `zecontinha.com.br`, broadcasting to the public PT-BR Telegram `@pythonfinancas`.
**DERIVES-FROM:** Engle–Granger (1987) two-step, via the standard BR retail *"Long&Short"* pairs
literature; no paper cited in-repo. The implementation is conventional, not novel — **which is the point:
this kill is about the convention, not about one Brazilian hobbyist.**

**THE PUBLISHED RULE, fully specified** (`src/bin/bot.py:select_pairs`): keep pairs with
ADF `p < 0.05` **and** Hurst `< 0.3` **and** `|z| ≥ 2.0` at `periods=120`; rank by **lowest Hurst**;
broadcast the top 3. Universe: a hardcoded 100-symbol Binance USDT-perp list → 4,950 pairs, each tested
at **10 lookback windows** (`PERIODOS_CALCULO = range(60,260,20)`) = **49,500 tests per run**, with no
multiplicity correction anywhere in the codebase.

**THE KILL — MEASURED, not asserted** (4,000 trials, two *independent* random walks, n=120, seed 20260813):

| gate as implemented | realised rejection rate under the null | nominal |
|---|---|---|
| `adfuller(sm.OLS(y, add_constant(x)).fit().resid)` | **17.97%** [16.8, 19.2] | 5% |
| `statsmodels.tsa.stattools.coint(y, x)` (MacKinnon) | 7.60% [6.8, 8.4] | 5% |

**The screen's 5% cointegration gate actually operates at 18% — 3.59× its own nominal size** (OP-077).
The cause is textbook and unambiguous: ADF critical values do not apply to residuals of an *estimated*
cointegrating vector, because OLS picked β to minimise exactly the variance the test then examines.
Full published screen (ADF **and** |z|≥2) fires on **0.88%** of pure-noise pairs against 0.43% for the
correctly-sized test → **≈44 spurious pairs per run at the broadcast window alone**, from which the bot
publishes the 3 with the lowest Hurst — i.e. it ranks the survivors of a noise filter by a statistic
(R/S Hurst at n=120) whose sampling error at that length is large. **Selection on noise, ranked by noise.**
The null used is *independent* walks; co-moving perps make spurious residual stationarity more likely,
so 17.97% is a **conservative floor**.

**WHAT IS *NOT* KILLED, AND THIS MATTERS MORE THAN THE KILL** — I checked whether the desk's standing
breadth objection applies here and **it does not**. The recorded desk lesson is *"the crypto cross-section
is 1.54 independent bets RAW and 29 market-neutral … any **directional** cross-sectional mechanism is
hard-killed by narrow_breadth before it starts — neutralise BTC beta or do not build it."* A cointegration
pair is long *y* / short *βx*: **beta-neutral by construction**, so it lands on the **29** side, not the
1.54 side. The breadth argument that ends every directional cross-sectional mechanism on this desk
**is not an argument against this family** — it is closer to an argument *for* it. Routed to
`improvement_inbox.md`; **no kill claimed**, and the family stays open.
(Caveat recorded honestly: `reports/cross_section_breadth.json` is gitignored and **not readable from
this checkout**, so the 1.54/29 figures are cited from the desk-lesson text, not re-verified here.)

**WHAT SURVIVES THE KILL AND IS WORTH KEEPING:**
1. **The correct instrument is one import away** — `coint()` vs `adfuller(resid)`. Any future desk
   statarb work must use the former; this entry is the reason.
2. **Half-life and Hurst as *descriptors*, not gates** — the repo computes an OU half-life
   (`-ln2 / β` from Δs on lagged s) and publishes it beside every pair. Sound construction, wrong role:
   it is a ranking input here, and ranking thousands of candidates by a noisy in-sample statistic is
   the selection problem again.
3. **A free control arm** (OP-080): the same channel broadcast a **uniform random draw** before
   PR #30 (2025-11-06) and a screened selection after — a dated, public, timestamped random-selection
   baseline for pair trading. Whoever tests a pairs screen here has the "does it beat a hat?" arm already.

**COST OF THIS KILL: one afternoon of Monte Carlo, zero desk data, zero forward slots.** Pre-emptive
falsification of a mined artifact is free graveyard material and this is what it looks like.

## `jp_gmo_tick_archive_direct_ingest` — GMO Coin free keyless tick archive (api.coin.z.com/data/trades/, 2018-09-05 →)

**KILLED 2026-08-19 (EN frontier miner s-I). Mechanism of death: §13 LEGITIMACY — consent-required
reuse clause with no consent held.** Not a technical failure: the archive is live, keyless,
26 spot + 12 margin symbols including JP-only MONA/FCR/NAC/WILD.

**THE OPERATIVE CLAUSE** (kihon-yakkan.pdf ver=20260725, read 2026-08-12 stdlib-extracted, R0309):
customer 基本約款 **Art. 14(15) requires company consent for off-service use of service-obtained
information**, and **Art. 7(1) deems use of the service to be assent** to the 約款. Whether the
anonymous keyless archive sits inside 本サービス scope is the ambiguity — and §13 demands CLEAR
permitted usage over a restrictive clause, so ambiguity resolves against ingest.

**THE ASYMMETRY WITH BITBANK, measured 2026-08-19 (the decision's spine):** bitbank was cleared
the same day on venue CONDUCT — MIT-licensed official Public-API clients, two published sample
market-making bots, an official Discord botter community, an official historical-data
distribution service — over a ToS with NO reuse clause. GMO has the OPPOSITE profile on both
axes: an explicit consent-required reuse clause AND zero affirmative conduct (no GitHub org —
gmo-coin/gmocoin/GMOcoin Not-Found/empty; archive page is a bare symbol listing in the API docs
with no grant language; robots 404; no API-specific terms per the 08-12 search of policy index +
API product page + archive index). A clause plus silence is not a licence.

**RE-ENTRY CONDITION (L1.16a, named):** written consent from GMO Coin (support-ticket request,
ledgered R0622, due 2026-09-02) OR a future API/archive terms document granting third-party
reuse. Either re-opens the card at `verified-technically-clean`.

**SUBSTITUTION CHAIN, so nobody re-derives it:** bitFlyer (killed 08-01, licence) → GMO was its
named replacement (killed today, licence) → **the surviving licensed JP tape is bitbank**
(candles WIRED 2026-08-19: data/bitbank_1day.jsonl; L2 orderbook S3 pending registration
R0620, watchlist card 34) plus Tardis `bitflyer` free 1st-of-month. The JP-only-ticker moat
argument transfers to bitbank's mona_jpy/xym_jpy, already in the wired tape.

## `numerai_mda_feature_selection_gain` — "MDA/permutation feature selection improves models" (as published)

**PRE-EMPTIVE FALSIFICATION (free graveyard material), recorded 2026-08-19 from primary-source
community measurement.** The claim (Numerai forum thread 3170, 2021-05, from LdP's AFML MDA):
selecting features by permutation importance gains "+0.5% CORR on validation". The measured
decomposition (jay1100, same thread, post #21, 3-arm experiment): importance computed ON
VALIDATION → **+0.7%**; importance averaged across 5 CV folds → **+0.5%**; importance computed
ON TRAINING folds only (leak-free) → **+0.025%**. ~95% of the published gain is evaluation
leakage, and the load-bearing lesson is sharper than "don't leak": **averaging a leaky statistic
across folds DILUTES the leak, it does not remove it** — the intermediate arm still books 20×
the true gain. The tool is not dead (leak-free permutation importance is sound; sklearn
`permutation_importance`); the PUBLISHED GAIN is. Any desk feature-selection step that selects
on the window it evaluates re-manufactures this artifact. DERIVES-FROM: AFML ch.8 (MDA); the
refutation is independent community measurement. SOURCE: forum.numer.ai/t/3170 #1/#21.

## `hyperparam_grid_uniqueness_as_signal_diversity` — "trillions of grid combinations = unique signals"

**PRE-EMPTIVE FALSIFICATION, recorded 2026-08-19.** The claim (Numerai forum 7916, 2025-01):
39.6 quadrillion hyperparameter combinations ⇒ "every staker could generate a completely unique
model". The refutation, from the thread's own reply layer and the desk's own arithmetic: models
drawn from one learner family on one dataset with one era structure are **correlated by
construction** — "most of the resulting models will still be highly correlated also because they
are subject to the same eras" (foolish_observer), "any automatic grid-searching thing still
basically converges in aggregate to some form of example predictions — it will still just be
xgboost" (wigglemuse). This is the desk's own measured law arriving from a foreign ecosystem:
**independence comes from the DATA, not the MATH** (OP-084, 48/50 single-operator survivors),
and N same-family variants are ~1 effective bet (demeaning-floor lesson). Genuine convergence,
DERIVES-FROM: NONE (checked — neither side cites the other). Kill any future proposal that
counts configuration-space cardinality as diversity; count effective bets on the desk's own
panel instead (libs/research/panel_breadth).

---

### era_grid_ladder_vol_bot — THIRD INSTANCE (RU 2014, live A/B challenge + the author's rules corpus) — RE-ANCHOR MECHANICS + THE ERA'S OWN EXECUTION-ALGO REFRAMING

**RECORDED 2026-08-19 (RU frontier miner s3, btcsec bot-class continuation; primary era text via
Wayback, IPB3 UTF-8).** Sources: forum.btcsec.com topic 8150 "Купить и подождать против бота
(btc-e bot by ezhrd)" (2014-06-02→04, 21 posts across 2 archived pages — page-2 capture EXISTS,
first CDX probe at limit-20 missed it, re-queried per OP-069 discipline before claiming the
negative); topic 1168 "Правила безопасного трейдинга на BTC-e" (izlevinv's rules corpus,
2013-04, 20 posts); topic 6549 (1b bot lite vendor thread, 2014-03→06, 15 posts).
**DERIVES-FROM: NONE (checked)** — folk challenge thread, cites nothing; the bot is ezhrd's
hosted commercial grid bot for btc-e; izlevinv is a paying USER stating its mechanics, not the
vendor.

**(a) THE GRID'S OPERATING RULES, from users quoting the author:** buy-ladder below price,
take-profit above; after a filled sell it CANCELS remaining buys and RE-PLACES the whole grid
DOWNWARD from current price; deliberately NO auto-trail-up option — izlevinv: "чтобы при резком
рывке вверх наверху не купить" (so a sharp up-move cannot make it buy the top); his settings:
перекрытие (grid coverage) ≥15%, 1% отступ (offset). The re-anchor-down rule is the
short-gamma economics one level deeper than instances #1/#2: the design ADDS inventory only on
the way down BY CONSTRUCTION, and the sole anti-top-buying defence is refusing to follow price
up — i.e. the failure mode is priced into the config vocabulary itself. #18 (sasa9): "Покупка
наверху — это общая проблема многих бот-алгоритмов" — the era names top-buying as the CLASS
failure, not this vendor's.

**(b) THE ERA'S OWN NULL, converged from BOTH sides of the argument:** sceptic sasa9 #16 — "тут
знать надо когда запускать и какой профит выставлять, а если знаешь — тогда зачем бот? купил и
поставил ордер на продажу" (you must know WHEN to start it and WHAT profit to set; if you know
that, why the bot); bot-user izlevinv #19 agrees from the pro side: its real use is EXECUTION
AFTER A DISCRETIONARY TIMING CALL ("включать в момент, когда вы спрогнозировали, откуда
покупать — купит со страховкой и дешевле"), and #21 closes: configure it so "прогноз и 'Отступ
от' совпадали — и можно спать идти" (make the forecast and the offset coincide, then sleep).
Both sides land on the same decomposition the desk already holds: THE GRID IS A LIMIT-LADDER
EXECUTION WRAPPER; THE TIMING DECISION IS THE ALPHA AND IT STAYS HUMAN. A grid bot's backtest
is therefore a JOINT test of an unstated discretionary entry signal + a ladder, and crediting
the ladder is attribution error (the coin-selector/engine severance rule, era edition).

**(c) THE CHALLENGE ITSELF DIED UNANSWERED:** sasa9 proposed a public live A/B (bot vs
buy-and-wait, both $50/pair, 5-10% target, ~10 days) and repeatedly asked the vendor to run 2
cloud instances; #14 "Что-то молчит автор" (the author stays silent); no test ever started
before the thread died 2014-06-04. A sold-bot vendor declining a free public live test is the
seller-signal of instance #2 ("если бот приносит прибыль, зачем его продавать?") in
behavioural form.

**(d) supporting era lore banked from the same slice (not separate entries):** topic 1168 rule
№3: "Не смотрите на стенки — их очень редко грызут, чаще ими пугают" (walls are rarely eaten,
mostly used to scare) — RU 2013 folk knowledge that DISPLAYED depth is intimidation, not
liquidity (era-side sibling of the desk's L1.45 displayed-depth caveat); rule №7: plan orders
in a table FIRST, then place ("Таблица-ордера, ни в коем случае не наоборот") — pre-registered
mechanical execution as 2013 retail discipline; kinken (#16, 1168): crypto venues read as
manipulated vs regulated FORTS futures — the era's own venue-quality ranking. Vendor-thread
6549 facts routed to WS-009/WS-010 observation appends (venue FEE-endpoint lie; strategy-file
+ vendor-held-API-keys synchronization channels).

**(e) THE CHALLENGED BOT'S OWN AUTHOR THREAD FOUND AND MINED (continuation, same run family:
topic 4320 + the author's LIVE blog).** Topic 4320 "Бот для торговли на btc-e" (2013→2014-05,
12 posts) is ezhrd's own thread — Evgeny Pozharsky = ezhrd (ezhrd.wordpress.com linked in-thread;
blog post "btc-e bot by ezhrd", 2014-01-05); the bot was FREE with optional paid features
("бот бесплатен? — в целом да; некоторые доп фичи по подписке"), which re-answers instance #2's
seller-signal: this vendor's economics were distribution-first, then subscription. Author's own
mechanism statement (May-2014 update): "покупаем при достаточно резком скачке вниз и продаем на
отскоке" + "функция контроля ордеров по стенкам стакана" + a borrow-coins-and-trade-down
pseudo-short. The wall-control line closes a loop with (d): by 2013-14 displayed-wall signals had
AUTOMATED retail consumers — the walls of rule №3 were scaring BOTS, not only humans, so wall
manipulation had algorithmic flow to harvest. Reply layer (WS-003 shape): a user ran forensics on
the AUTHOR'S OWN SCREENSHOT — "113908816 отменяется дважды с промежутком в 10 секунд" — duplicate
cancels in the vendor's published evidence, caught by a reader; and the era's partial-fill
mechanics explained in-thread. Successor chain: btcsec topic 7990 → forum.bits.media topic 7990
(the thread SURVIVED the forum's 2015 rename — btcsec topic ids carry over to bits.media).

**(f) THE VENUE-POLICY KILL CHANNEL — dated, author-stated, and the class's fourth kill
mechanism.** Blog comment 2018-01-06, ezhrd on why Bittrex was dropped: "битрикс стал предъявлять
претензии... за малый процент заполнения ордеров (слишком много отмененных ордеров по отношению к
выполненным) и начал требовать платить за отмененные ордера (!). Поскольку алгоритм работы бота
основан на тягании сетки ордеров туда-сюда, такие заявления биржи делают работу данного алгоритма
торговли невозможной." The grid's order footprint — many cancels, few fills — is structurally
indistinguishable from the quote-stuffing footprint venues police, so fill-ratio enforcement and
cancel fees are a class-level kill switch that NO grid backtest prices. Kill channels for this
class now: (1) short-gamma economics + fee stack (instance #1), (2) vendor no-show under live
test (instance #3a-c), (3) timing-is-the-alpha attribution (the era's own null), (4) VENUE POLICY
on cancel-to-fill ratio (this — and its modern echo is every order-to-trade limit and cancel-rate
tier on today's venues, including the ones this desk trades).

**(g) FLEET FACTS from the same chain (era record, banked here, not separate entries):** bot-2
(2015→2018+, cloudbot.uk) is a VENDOR-CLOUD subscription — the entire customer fleet executes
from the vendor's servers ("Бот работает в облаке... из-за океана": during BTC-E's DDoS
mitigations whole network segments lost access while the far hemisphere kept trading — a
cross-geography LIVENESS asymmetry the era's overseas-hosted bots collected structurally). The
fleet MIGRATED venues during the BTC-E seizure week (customer 2017-08-01: "btc-e не работает уже
неделю... переключиться бы на полонекс"; vendor: send new keys — and WEX appears as a supported
venue by 2017-10). Bitfinex was disabled 2016-08-04 "по понятным причинам" — two days after the
hack — and re-enabled 08-11. EXMO named (by the vendor, against his own interest) as the venue
with NO key-permission granularity: "У EXMO права ключа вообще никак не настраиваются – любой
ключ может делать все." BTC-E's nonce watermark made a key single-machine-forever ("хоть один
запрос под этим же ключем с другой машины – ключ перестанет работать навсегда"), which is the
mechanical reason vendors demanded FRESH keys (WS-010's registry channel has an era-API cause,
not just a business one). Author's folk sizing rail: "торговля на 100% депо – это самоубийство"
(recommends 60-70%). NAMED GROUND, unmined: forum.bits.media topic 27623 — the bot's FREE LIVE
real-money trading chronicle ("хроника реальных торгов", running from 2017-05): a primary P&L
record of the grid class across the 2017 mania and crash, better evidence than any marketing
claim on either side.

**(h) topic 6475 corroborations (mined same slice):** the engine/strategy severance gets a THIRD
independent era voice — "Прибыль зависит не от самого бота, а от стратегии - алгоритма торговли,
который в него заложен" (profit lives in the loaded strategy, not the bot) — and the era's
lived risk ranking puts VENUE risk above strategy risk: "Сколько не жалко потерять. (биржи
ломают, кидают, и довольно часто)"; plus the spot-market consolation fallacy in period form
("если не будешь специально фиксить убыток, то слить нереально" — unrealized losses read as no
losses).

### kr_bank_rail_event_study — KILLED ON MEASURED TREATMENT SCARCITY (design-level, not mechanism falsity)

**RECORDED 2026-08-19 (KR frontier miner s4, R0634 — the blocking measurement s3 named).** The
KR venue↔bank fiat-rail axis (watchlist card #35, minted as #33 on the s3 branch) proposed
trading venue-asymmetric KRW rail transitions. s3's EV verdict was knife-edge on a HAND estimate
(~6 transitions/yr → EV 0.0019 vs 0.002 thresh; QUEUE at ≥8/yr). **This session enumerated the
treatment from the primary record instead of estimating it**: Upbit's complete first-party
notice archive (776 rows, category=notice, 2017-10→2026-08, fetched whole this run —
`data/upbit_notice_announcements.jsonl`), the desk-measured Bithumb 2025-03-24 migration, and
press-dated rows for Coinone/Gopax/Korbit (`data/kr_bank_rail_transitions.json`, 19 rows classed
sharp/weak/window with announce-vs-effective dates separated per the announcement≠treatment
fence).

**THE MEASURED RATE: ~0.9 sharp episodes/yr (8 episodes in 8.6y); ~2.2/yr counting every weak
policy row.** Era structure makes it worse, not better: the mass sits in 2017-12→2021-09
(pre-real-name freeze, launch, both big migrations, 특금법 mass cutoff); **2022+ produced ONE
sharp episode in 4.6 years** (Bithumb NH→KB 2025-03-24). Contracts consolidated; the treatment
is drying up, not accruing. EV re-run with measured breadth: **0.0004 (sharp) / 0.0006 (all
rows) — 3–5× below the 0.002 threshold, REJECT with no knife-edge left** (QUEUE needed ≥8/yr =
9× the measured sharp rate). An event study here accrues n≈9 per decade: **permanently
underpowered by design** — the AR seat's annual-event-study lesson (retire the DESIGN, not the
instance), arriving in KR.

**WHAT SURVIVES, EXPLICITLY: the registry, as a PROVENANCE layer, not an alpha axis.** The
mechanism is real and desk-measured (WS-011 obs 2: the 10.50h Bithumb tape hole IS a rail
event printing as an absence). Knowing WHEN a KR venue sat in a migration/freeze window gates
every KR premium/spread measurement the desk makes — card #35 keeps that role; what dies is
the standing tradeable-event-study use.

**RE-OPEN CONDITION (L1.16a, narrow door):** a NAMED structural change that raises rail-event
frequency — concretely, repeal or amendment of the one-exchange-one-bank rule (Woori's CEO is
publicly lobbying for exactly this). A repeal TRANSITION would produce a one-shot cluster of
re-contracting migrations (tradeable as an event CLUSTER, not a standing edge) — and then end
the exclusivity mechanism entirely. Watch the rule, not the venues.

**METHOD RESIDUE (why the estimate was 6× the measurement):** s3's ~6/yr hand estimate implicitly
counted renewal cycles and policy noise as treatments. The enumeration separates classes:
renewals that change nothing are non-events; VASP counterparty suspensions (the ~40-row 2022+
mass in the same archive) are CRYPTO-leg events on a different card. **A breadth estimate made
without class definitions inflates by whatever class boundary the estimator hasn't drawn yet.**

### arkham_alert_edge — practitioner-dated death of alert-vendor-driven trading (JP, stopped ~2024)   [pre-emptive falsification context, NOT a desk test]
SOURCE: rarirure.rip/archives/1301 (2024-12-23, botter Advent Calendar 2024 d23), the bot's module
list. The author RAN an "Arkham でエッジを見つけ Webhook アラートから売買する" module — trading
Arkham Intelligence webhook alerts (entity-labelled on-chain flow) — and retired it:
「市況が変わり、エッジじゃなくなったので現在は停止中」 (the market changed; it is no longer an
edge; currently stopped). A documented ran→paid→died lifecycle with a stated cause, not a debunk
of the data axis itself.
MECHANISM OF DEATH (stated + inferable): a commercial alert product democratizes its own signal —
every subscriber sees the same webhook at the same time, so the edge decays toward the vendor's
subscriber count; "market changed" from the operator who was there. NOTE the boundary: this kills
ALERT-FOLLOWING as an edge class for one practitioner in one era; it says nothing about raw
entity-labelled flow as a conditioning axis (the desk's whale-activity/CEX-flow vocabulary), and
his own replacement was to poll explorers DIRECTLY for hot-wallet inflows on chains Arkham does
not cover — the practitioner's fix was to move UPSTREAM of the vendor, which is this desk's
free-first doctrine arriving from the retail side. DERIVES-FROM: NONE checked (own operation;
post-2023 so LLM-assist UNVERIFIABLE per OP-072, but the module lifecycle is his own record).
[§33: killed -> this entry]

### coingecko_category_taxonomy — vendor sector map for a cross-section the desk no longer hunts (mandate kill 2026-08-25)   [consumer removed by principal order, NOT refuted by data]
SOURCE: docs/research/data_axis_watchlist.md card 28 (carded 2026-08-11, brain-hunter seat) —
CoinGecko `/coins/categories/list` + per-coin categories (keyless free tier) as the mechanism-based
ORTHOGONAL fourth grouping map for card 27's `group_rank`/`group_zscore` inputs over the 296-symbol
crypto D1 lake.
MECHANISM OF DEATH: the consumer was removed, not the claim disproven. The MT5 UNIVERSE MANDATE
(2026-08-18, CLAUDE.md standing order) bans hunting the crypto-exchange cross-section outright;
card 27's group-transform program over 296 perps was this taxonomy's SOLE consumer. The surviving
MT5 universe carries ~10 Fusion-executable crypto CFD majors (desks/mt5/mt5desk/universe.py
`_CRYPTO`), which the desk's own asset-class grouping already covers — a vendor taxonomy of
thousands of alts groups nothing the desk may trade. LICENCE STATE AT DEATH: UNREAD, attempted
twice, not skipped (WS-005 discipline): coingecko.com/en/api_terms → HTTP 403 on 2026-08-11
(brain-seat fetcher) AND 2026-08-25 (this box, WebFetch); web.archive.org route unreachable from
this box's fetcher the same day.
RE-OPEN CONDITION (L1.16a, narrow door): a principal order re-opening a crypto cross-sectional
universe AND a completed api_terms read that permits desk use (row #79: read it, never assume in
our favour). Free fallback if ever re-opened: card 27's proprietary maps + DeFiLlama protocol
categories (licence equally unread — same read owed). DERIVES-FROM: NONE (checked — card 28 is the
desk's own carding of a vendor API surface, no upstream writeup).
[§33: killed -> this entry]

### retail_fx_stophunt_feed_manipulation — folk mechanism "the broker manipulates YOUR quote feed to hunt YOUR stop", insider-refuted (EN, 2020-21)   [pre-emptive falsification context, NOT a desk test — and the REAL mechanisms it obscures are execution intel for the MT5 desk]
SOURCE: HN 25219314 comment tree (mined to full depth 2026-08-25): AdrianAvtomat 25253286 +
25253035 (retail-FX industry, self-identified, corroborates a platform-vendor's account);
iamacyborg 26045541 (ex-spread-betting-firm employee, London); lordnacho 25219798 (ex-FX HF).
THE FOLK CLAIM KILLED: per-client quote-feed manipulation to trigger an individual trader's stop.
Insider verdict verbatim: "a broker wouldn't even need a front-running bot. If they're the
intermediary (A book) then they can just apply markups to the quotes from their maker. If they're
the maker (B book), they're the ones quoting the prices. Front-running is moot in either case …
manipulating the quote feed for thousands of traders just to hit one guy's stop … impractical if
not impossible using industry standard platforms."
WHAT IS REAL INSTEAD (the boundary, and it is desk-relevant execution reality): (1) A-book =
routed to LPs WITH broker markup on the spread — the desk's spread is a POLICY variable, not a
market constant; (2) B-book = internalized against the house, the broker profits from client
losses directly (corroborated first-person: "education" funnel downstairs, B-book upstairs);
(3) TOXIC-FLOW RE-ROUTING — consistently-winning accounts get moved B→A book ("if someone is too
good they just send him to the market"), so a profitable desk's execution regime CHANGES as its
edge is detected: treatment is ENDOGENOUS to desk PnL. Naming correction from the reply layer
(depth mandate, again): B-book = against the maker, A-book = to market — the OP had it backwards.
NOTE the class: stop CLUSTERING at round numbers is visible to any market participant and
stop-cascade mechanics at the MARKET level remain real; what dies is only the per-client
feed-manipulation story. FXCM's CFTC ban (undisclosed dealing-desk interest while advertising
"No Dealing Desk") is the canonical documented case of the REAL defect class.
DERIVES-FROM: NONE (checked — first-person industry accounts, no cited upstream).
[§33: killed -> this entry]

### cn_bucketshop_retail_loss_as_directional_signal — folk premise "retail loses ⇒ fade retail direction" refuted by the CN bucket-shop industry's own fee arithmetic (CN, 2011-2017 era; pre-emptive falsification for every retail-sentiment-contrarian hypothesis, incl. the 反向跟单 reverse-copy-trade industry built on it)
SOURCE: 南都/凤凰财经 2014-06-18 exposé (dead link; recovered via Wayback CDX this run, 3 captures,
2015-05-21 capture read to full depth — 6,559-char article) + 武久文 legal-mode analysis (sohu
193763502) + CSRC Shenzhen cleanup Q&A + 2026 反向跟单 vendor/search layer (qhfgd.com 68-part
series located, unmined).
THE FOLK PREMISE KILLED: CN member-firm B-books (贵金属交易所 era) proved retail "always loses",
and an entire 反向跟单 (reverse-copy-trade) software industry monetised fading aggregate retail
direction. THE REFUTATION IS IN THE HOUSE'S OWN ARITHMETIC (insider 杨诚, quoted with worked
numbers): one silver round-trip at ¥4000/kg, 100kg lot, 1% margin, 8bp commission, 2bp/day
overnight, ¥8/kg spread = **¥1,528 = 38.2% of the margin posted** — "就算不亏损，仅交易中涉及到的
手续费和点差反复倒腾几次就足以让整个保证金变为零". Client ruin was COST EXTRACTION plus churn
(measured case: ¥500k principal → ¥40M+ turnover in 10 trading days, advisor-driven 刷单), not
directional wrongness — so the anti-signal in retail direction is far weaker than retail LOSS
RATES imply. Any Myfxbook/retail-positioning contrarian screen must debias for cost-driven loss
or it manufactures a phantom edge from fee drag. Reply-layer reasons the 反向跟单 mirror-leg also
fails (search-layer, unmined to depth — leads only): B-book internal tape ≠ market prices (the
mirror executes on a DIFFERENT price series than the one the clients lost on), double-charged
costs, and the churned component of retail flow carries no direction at all.
WHAT IS REAL INSTEAD (execution intel, second independent instance of the EN entry above): the
2014 back-office screenshots show TOXIC-FLOW SEGMENTATION AS A GUI — menu "扫描赚钱的人" (scan
for profitable clients) with per-client 延迟 5s / 滑点 ¥10 auto-handling, 大笔入金/高频交易/
同一局域网 scans, 净头寸超限 — plus asymmetric order-gating (book 1000 short vs 2000 long →
"只能卖空不能买多"), engineered two-sided wicks on INTERNAL quotes (">1% dip to blow 1%-margin
longs, then resume"), NFP-window server "outages", and the platform economics: client losses
(头寸) rebated 100% to member firms + agents by negotiated split while the venue keeps fees —
a LISTED company (大智慧/民泰, 天贵所 member #166) booked ¥86.57M fees + ¥219M "investment
income" from this in ONE quarter, then sold the unit for ¥392M to the chairman's brother-in-law
when 418 victims (~¥90M) besieged HQ. Leverage sold: silver 4-100×, FX 80-160× vs a stated 20×
legal max. CONVERGENCE NOTE (charter §14): same segmentation structure as the EN/HN insider
account mined TODAY by EN s-J (A/B-book, winner re-routing) — 2014 CN court-adjacent journalism
and 2020-21 HN first-person accounts share no derivation path; this is genuine cross-ecosystem
corroboration that broker treatment is ENDOGENOUS to account profitability. Legal-mode taxonomy
(武久文): member-firm 对赌 mode, 邮币卡 closed-pump mode, 微盘 mode with quotes "参考国内外市场
价格甚至虚设价格行情"; criminalised as 非法经营罪/诈骗罪/聚众赌博. Era boundary: 38号文 (2011)
naming rule quoted in the exposé; 清理整顿办公室 est. 2014-04-11.
DERIVES-FROM: NONE between the CN and EN source families (checked both ways: the 2014 南都 exposé
cites CN insiders and CCTV's 天交所 coverage; the HN threads cite no CN material).
[§33: killed -> this entry]

### kr_venue_state_layer — Upbit/Bithumb venue flags + announcement archive for a KR cohort the desk no longer hunts (mandate kill 2026-08-25)   [consumer removed by principal order, NOT refuted by data]
SOURCE: docs/research/data_axis_watchlist.md card 26 (carded 2026-08-01, KR frontier miner s1) —
four keyless first-party surfaces: Upbit announcements (737 trade events 2017-10-27→, ingested to
data/upbit_trade_announcements.jsonl), Upbit/Bithumb warning+caution flags, Bithumb
deposit/withdrawal rail state (collector live 08-12→08-20, data/kr_venue_flags.jsonl, stopped in
the crypto retirement wave).
MECHANISM OF DEATH: consumer removed, not the claim disproven. The MT5 UNIVERSE MANDATE
(2026-08-18) bans crypto-exchange-native opportunity ground; every consumer this layer had —
intra-KR venue basis (R0299 family), KR premium conditioning, the listing_comparables_repricing
screen design (R0616, disposed same day) — is banned or re-graded. The card's measured traps are
BANKED so any re-entry inherits them: GLOBAL_PRICE_DIFFERENCES fires 22% on all markets vs 0.4%
on KRW (quote-currency artifact — split before reading any rate); key events on first_listed_at
never listed_at (differ on 42.5% of rows, amendments rewrite listed_at); announcements are KST
while Upbit daily closes 24:00 UTC (window starts NEXT UTC close or it is look-ahead).
L1.16a RE-OPEN DOOR (named enabling change): the desk gains a KRW-linked MT5 instrument (e.g. a
USD/KRW exotic added to the Fusion universe) AND a stated mechanism linking venue/rail state to
it — or the universe mandate itself changes. The owed screen died UNRUN: no trial charged, no
forward clock ever minted.

### dex_wallet_tape_mining — vec-operator mining program over the owned GeckoTerminal DEX tape (mandate kill 2026-08-25)   [consumer removed by principal order, NOT refuted by data]
SOURCE: docs/research/data_axis_watchlist.md card 37 (carded 2026-08-19, BRAIN hunter s4; ledger
R0637) — data/geckoterminal_trades.jsonl, 322,187 signed wallet-resolved DEX trades (solana/eth,
68 pools, 93,241 wallets), collector stopped 2026-08-20 (retirement wave), file frozen at 197MB
spanning 2026-08-11→08-20.
MECHANISM OF DEATH: the mining program (whale/retail mix, buy/sell asymmetry, wallet-cohort
reductions over DEX pools) targets a crypto-exchange-native cross-section the 2026-08-18 mandate
bans. Never screened, never a candidate (the card itself declared the panel unpowered under
L1.62); no trial charged. The 9.5-day tape stays owned on disk as provenance.
WHAT SURVIVES (not killed — lives in R0637, owner = brain seat, split prescribed brain-s5
2026-08-20): (a) utilisation-meter blindness to registered-but-uncatalogued collectors — a meter
defect, universe-independent; (b) the vec_*/reduce_* vector-operator gap (desk implements 0 of
18) — the identical per-event data shape exists on the MT5 desk's own recorded tick tape, which
is where that capability belongs now.
L1.16a RE-OPEN DOOR: universe mandate change only.

### wctc_leader_follower_replication — "contest/leaderboard returns are follower-replicable" (structural claim-class prior, prospector 2026-08-25)   [debias prior from operator + regulator text; NOT a statistical kill]
SOURCE (all opened this run): worldcupchampionships.com (operator site, live read); CFTC Docket
22-R009, Morris v. Robbins Futures Inc. d/b/a Robbins Trading, Initial Decision 2025-05-06
(primary PDF, full text extracted); trading-tournaments.com champions archive 1984–2026.
THE CLAIM CLASS KILLED: reading WCTC/leaderboard champion returns as follower-harvestable edge.
STRUCTURAL MECHANISM, from the operator's and regulator's own text: (1) the operator EXPLICITLY
permits multiple contest accounts per entrant and DISCLAIMS representativeness ("WCC competitors
may control accounts that produce results substantially different than the results achieved in
their WCC accounts. WCC entrants may trade more than one account in the competition") — champion
returns are order statistics over max-leverage tickets (200:1 available non-US forex; $10k/$5k
minimums; $3,999/yr entry), not skill estimates; (2) the contest feeds a monetized funnel — top
performers "may join the WorldCupAdvisor.com advisory team" selling autotrade subscriptions, so
the LEADER's contest account is an option (entry fee = premium; upside = advisory annuity) while
the FOLLOWER holds the position with full downside; (3) the CFTC decision found the broker and
the (unregistered) WCA advisors "entangled... evidenced by the fee structure and active
communications" — an agency relationship — while dismissing the complaint (losses ≠ wrongdoing);
the documented follower instance: $80,000 (funded from a Roth IRA) → −$29,129.44 in ~4 months
across four Leader-Follower AutoTrade sub-accounts. (4) MEASURED THIS RUN: champion return
values DISAGREE across mirrors (Davey 2006: 148% vs 107%; Unger 2012: 230% vs 82%) — even the
headline numbers are marketing artifacts.
WHAT THIS DOES NOT KILL: WCTC is the RARE forward-scored real-money contest (unlike
backtest-scored leaderboards, cf. era_ta_indicator_stack_crypto: "treat any leaderboard/backtest
result as in-sample until pre-registration is proven" — here forward IS proven). The bias
channel is SELECTION, not overfit: repeat-density (Unger 4 titles incl. 3 consecutive; 10
multi-title winners in the 1984–2026 panel; one cross-division champion) remains weak evidence
that learnable mechanisms exist — but it is confounded by the multiple-account rule, and the
REPEAT WINNERS' published mechanisms (Williams vol-breakout/COT/TDOM; Unger multi-system
short-term futures; Davey trend across 8–12 markets; Hughes premium-selling) all fall in
families this desk already killed on its own data (price-only breakout/trend, retail calendar,
TA stacks) or rejected (COT direction, pooled NW t=−0.64, 41y). The durable transfer is
PROCESS: winners solve max-growth-under-a-barrier (50% intraday-DD liquidation + $1.5k floor) —
the desk's own robust-Kelly-with-rails objective, independently converged on.
RELATED: cn_bucketshop_retail_loss_as_directional_signal (same debias-prior shape, CN s12
2026-08-25); master-23 selection-bias defense now carries operator-text + regulator-text
evidence.

## cot_hedging_pressure_level (upgraded to literature-convergent, litminer run 10 2026-08-25)
The desk's own kill (COT_SCREEN_RESULT.md: pooled lagged NW t=−0.64, 41y, 6 contracts, 24 trials,
GHR gate replicated) is now CONVERGENT with the published replication layer: Maréchal JFM 2023
(1994–2017) finds the insurance/hedging-pressure-level premium decays 0.43→0.34, significance
1%→10%, and "eventually vanishes" post-financialization, while GHR reject lagged predictability
outright. Two independent methods, same verdict. Level/lagged COT direction stays DEAD; re-entry
per L1.16a only on a construction-level enabling change (e.g. intraday positioning frequency).
The CHANGE/liquidity channel is explicitly NOT covered by this kill — it is carded live as
watchlist #40 (EV-queued).

## gotobi_nakane_drift (new entry, litminer run 10 2026-08-25 — replicated THEN measured dead)
USDJPY drift into the 09:55 JST Tokyo fix on gotobi days (importer USD settlement custom;
Ito–Yamada NBER w22820; Bessho–Sugimoto–Suzuki arXiv 2301.13204). Desk's own preregistered screen
(`data/gotobi_screen.json`, 3 trials, USDJPY H1 2018–2026, clock-corrected): **2018–2020 REPLICATES
the literature (+5.33bp/d gotobi excess, t=2.55, p=0.006); 2021–2026 DEAD (+0.43bp, t=0.26, gross
below the 1.02bp RT cost)** — killed by crowding (MQL5/TradingView EA productization of the exact
pattern; drift onset already front-run to ~03:00 JST in the 2018–2020 EBS data) and/or the
2022–2024 JPY intervention regime. NOT sent to the gauntlet: current-regime net expectancy is
negative — a forward slot would be spent confirming a measured null. RE-OPEN TRIGGERS (named):
(a) JPY rate-regime normalization (BoJ policy-rate path flattens, carry stabilises) AND
(b) retail abandonment measurable via MQL5 gotobi-EA product activity/reviews going quiet.
The MECHANISM (invoice-custom settlement demand) is not refuted — only its current-price is zero;
the flow persists per Akiyama et al. (JAFEE 19, 2021, JP): anomaly strength tracks USD invoice
share of JP imports.

---

## `tradingview_pine_agentic_mining` — KILLED 2026-08-27 on §13 legitimacy, not on yield (unified frontier dig)

**What it was.** Seeds S3 and S12 (watchlist cards 43 and 52) proposed systematically mining
TradingView's public Pine script library and idea stream as a strategy-mechanism corpus — a large,
obvious, MT5-relevant body of published retail logic.

**Why it is dead.** `https://www.tradingview.com/robots.txt` carries TWO user-agent groups. The
`*` group bars almost nothing relevant (only `/scripts/search/`, `/ideas/search/`). A SECOND group
enumerates 16 AI crawlers — `Google-Extended, GoogleOther, Applebot-Extended, Amazonbot,
meta-externalagent, **ClaudeBot**, PerplexityBot, cohere-training-data-crawler, OmgiliBot, AI2Bot,
Bytespider, TikTokspider, DeepSeekBot, ...` — and gives that group
`Disallow: /ideas/*, /scripts/*, /script/*, /v/*, /symbols/*/minds/*, /u/*, /chat/*, /chart/*,
/watchlists/*`. The publisher has explicitly and specifically withheld this exact ground from this
exact class of agent. §13 is absolute; the desk does not build UA-substitution routes.

**The methodological point, which is the reusable part.** A single-group robots read INVERTS this
verdict — read only the `*` group and TradingView looks wide open. This is the false-POSITIVE twin
of the KR-s5 lesson (a truncated read showed `Allow:` while the whole file scoped it to `yeti`).
**Group-scope every robots read against the desk's OWN agent identity, never against `*`.**

**RE-OPEN TRIGGERS (named, per L1.16a — a re-open needs an enabling change addressing the
mechanism of death, not a fresh appetite).**
(a) TradingView removes `ClaudeBot`/the AI-crawler group from robots, or publishes a research API
    or licensed bulk export covering `/scripts/`; or
(b) the desk obtains explicit written permission from TradingView for research use.
A human reading the site in a browser is NOT a re-open trigger and does not become one at scale.

**What is NOT killed.** The *mechanism families* retail Pine encodes are reachable on §13-clean
ground the desk already holds — the Forex-TSD CDX attachment corpus (OP-096b), MQL5's own surface
(card 41), and the FX Blue track-record layer opened the same day (card 53). Nothing about this
kill withdraws the search space; it withdraws one route into it.

---

## `crypto_exchange_universe_banned_2026_08_18` — eight verified free-data sources retired by the universe mandate, not by any defect of their own

**Date:** 2026-08-28 (free-data-alternatives miner). **Verdict: KILLED as huntable ground. Tier 3.**

**Cards retired:** 2 (OKX official historical-data portal), 4 (Bithumb spot+futures), 5 (Coincheck),
6 (Tardis vendor-replacement), 9 (stablecoin mint/burn self-computation), 10 (AWS Public Blockchain
Data), 11 (eth-labels), 12 (cex-list) in `docs/research/data_axis_watchlist.md`.

**Mechanism of death — and it is important that it is not a data-quality verdict.** Every one of
these was graded **verified-clean** on its own merits, several after full first-party
reconstruction. None of them broke. They are retired because the **principal's standing order of
2026-08-18 (LAWS §1)** makes the crypto-exchange-native universe permanently un-huntable: *"No
crypto-exchange-native universe (Binance/Bybit/OKX/Hyperliquid/Deribit or any successor) may ever
be hunted again."* A source that may not be hunted cannot carry an axis, however clean it is. They
sat untagged in the §33 backlog for weeks precisely because nothing was *wrong* with them — the
backlog had no verb for "correct, and now out of scope."

**§16a re-open condition (a NAMED enabling change, per L1.16a):** only a principal order restoring
crypto-exchange ground. No data improvement, no new route and no regime shift re-opens these — the
death is jurisdictional, so only the jurisdiction can reverse it. **Crypto reference data remains
admissible where it measurably informs an MT5 instrument** (LAWS §1), which is a different use and
is not killed here.

**§38 — what replaces them.** The capability these eight carried was *forced-participant flow and
venue microstructure observable for free*. Its MT5-universe successor is the **official-sector-flow
class**, opened 2026-08-28 and now at three verified members: **Japan MoF intervention operations**
(card 67), **SNB weekly sight deposits** (card 68), **CNB open API — forward points + open market
operations** (card 69). The mechanism transfers exactly: a participant who is forced to transact,
publishes the fact, and cannot stop. The replacement hunt is open, not closed — Banxico, RBI, CBRT,
MNB and NBP are named and unopened.

### exotic_fx_halt_reopen_gap_vol (PROSPECTOR s9, 2026-08-28) — `mechanism_refuted`, and refuted on the desk's own data

**THE HYPOTHESIS.** MT5 exotic FX crosses (USDIDR, USDINR, USDBRL, USDKRW) are halted at the broker
on their home-country holidays — 10.4–11.4% of all weekday sessions — while USD-side and global risk
keeps trading. A position held across the halt cannot be exited and stops cannot fill; at reopen the
price should gap to absorb accumulated global information, giving excess reopen volatility that a
direction-agnostic vol strategy could harvest. Direction-agnostic by construction, which is the
class the desk's own lessons say to prefer.

**THE HALTS ARE REAL — that part verified, and it survives the kill.** The broker's published dated
calendar predicts the desk's tape exactly: 5 of 5 spot-checked halt dates have **zero bars** in
`desks/mt5/data/universe/USDIDR_H1.parquet` (2025-06-06 Eid al-Adha, 2025-06-19 Juneteenth,
2025-06-27 Islamic New Year, 2026-01-01, 2026-01-16 Ascension of the Prophet). The refutation is of
the *edge*, not of the *calendar*.

**FIRST PASS LOOKED STRONG, AND IT WAS AN ARTIFACT.** Uncontrolled, post-halt daily return dispersion
runs **1.34x–3.08x** normal with Levene p < 0.01 on all four symbols — the kind of result that ships
if nobody asks what else changed. What else changed is that a post-halt return **spans more calendar
time**, so variance scales with it mechanically. Controlling by dividing each return by
√(weekday-sessions spanned):

| symbol | n halts | raw ratio | mechanical √(sessions) | ratio AFTER control | Levene p |
|---|---|---|---|---|---|
| USDIDR | 56 | 1.967 | 1.923 | **0.933** | 0.913 |
| USDINR | 73 | 1.380 | 1.712 | **0.916** | 0.529 |
| USDBRL | 71 | 1.345 | 1.728 | **0.911** | 0.232 |
| USDKRW | 56 | 3.080 | 1.861 | **1.052** | 0.946 |

**The excess vanishes completely.** Every controlled ratio sits at or below 1.0 and every p is
0.23–0.95 — not "weaker than hoped", but *indistinguishable from ordinary time-scaled volatility*,
in all four symbols independently. Two of the four (USDINR, USDBRL) had raw ratios *below* their own
mechanical expectation, i.e. reopen returns were **quieter** than √t predicts. There is no
halt-reopen premium here.

**THE EV GATE AGREED INDEPENDENTLY**, which is worth recording as a gate-calibration data point:
scored pre-registration, `exotic_fx_halt_reopen_gap_vol` returns **ev 0.0001, p_survive 0.0112,
"REJECT (hard economic kill)"** on `price_only + narrow_breadth` — breadth is 4 symbols, and the
mechanism as specified was price-only. The gate and the data killed it for the same reason from
opposite directions.

**DO NOT REOPEN** by swapping the vol estimator, the horizon, or the symbol set: all three vary the
measurement, none changes the mechanism, and the breadth ceiling (four halt-heavy exotics, ~56–73
episodes each) is structural. The nearest live-again condition would be a genuinely different
quantity — e.g. *spread* or *fill quality* at reopen rather than return dispersion — which is a
different mechanism and would need its own card.

**WHAT SURVIVES AND IS THE ACTUAL DELIVERABLE.** The √t model fitting almost exactly is precisely
what makes the desk's *accounting* defect measurable: since variance really does scale with sessions
spanned, treating a multi-session gap as one period overstates realised vol by 1.01x–1.18x and
therefore under-sizes. That, the unwired/hardcoded/empirically-wrong `operational_calendar_miner`,
and the working PNG-plus-Wayback-CDX route to the broker's dated halt calendar are all filed in
`docs/research/improvement_inbox.md` (PROSPECTOR s9).

**RELATION TO `hijri_ramadan_calendar_axis` (2026-08-12, `unmeasurable_by_construction`).** Different
quantity and different universe — a broker halt/reopen event on MT5 exotics, not a seasonal return
dummy on crypto — so this is not a re-litigation of that row. But that row's kill reason (episode-level
n too small) applies here too and is now joined by a measured null: this one is **refuted**, not
merely unmeasurable, and it retires the mechanism rather than a method.

### `lazarus_easter_conditional_reversion_sp500` — PROSPECTOR s12, 2026-08-28 — `post_hoc_conditioning` + `n_too_small` + calendar-class match

_Source: jonathankinlay.com/lazarus-trade-easter-mean-reversion-sp500-index (VERIFIED, robots
`Allow: /`, read under an honest UA). S&P 500 weekly data from 1950._

**CLAIM:** the week AFTER Easter, *conditional on the index having sold off in the week before
Easter*, delivers a mean return more than 2x the unconditional post-Easter week and ~4x the
average week, with less than half the standard deviation — an information ratio ~10x larger,
an 85% win rate (22/26) against 57% unconditional, and a 58bp difference "statistically
significant at the 0.2% level".

**DISCARDED — not screened, not carded, and the author's own narrative is the reason.** He tests
the unconditional post-Easter week FIRST, reports the t-test (unequal variances) as **not
significant**, and only then conditions on a prior-week selloff to obtain the significant result.
That is a second hypothesis tested after the first failed, reported as one finding: the
garden-of-forking-paths this desk's multiplicity law names explicitly ("EVERY TRIAL IS REPORTED";
selective reporting is indistinguishable from a real result at the point of reading, and it is the
failure that retracted this desk's flagship signal). The published p is uncorrected for the
conditioning choice, and the cut — "sold off in the prior week" — is itself a free parameter with
an unreported set of alternatives (magnitude threshold, window length, index vs ETF).

**And the n forecloses it regardless of the multiplicity argument: 26 events in 65 years.** No
correction, and no amount of patience, brings a once-a-year event to the canonical ten gates'
sufficiency bar — 65 more years buys 26 more observations. MT5-tradability is not the binding
constraint (US500 is in the Fusion universe); the sample is.

**Calendar-class graveyard match** — consistent with `TDOM` (discarded, calendar-class) and with
`hijri_ramadan_calendar_axis` (`unmeasurable_by_construction`). Per WS-006 the significance of a
calendar **dummy** is a different quantity from the mechanism, and no forced flow is named here:
the post offers no answer to *who* is obliged to trade against this and why they cannot stop.

**TAG:** `post_hoc_conditioning` / `n_too_small` / `no_economics`.
**RE-OPEN CONDITION (L1.16a):** only on a named forced-flow mechanism for the Easter week
(a settlement, hedging or mandated-rebalance obligation), tested pre-registered across MANY
indices to buy breadth the calendar cannot buy in time — never on a re-run of this conditioning.

### mt5_broker_swap_markup_asymmetry — the administered MT5 swap IS the policy differential (PROSPECTOR s14, 2026-08-28)   [universe: **MT5**, mandate-valid]

**CARDED s13 2026-08-28, KILLED s14 2026-08-28 by its own pre-committed first test.** One day of
life, which is the pipeline working: the card wrote the crowdedness decomposition as step 1 and
declared it allowed to kill the card, and it did.

**MECHANISM OF DEATH — pass-through, not residual.** The claim was that an MT5 broker's swap is an
*administered* rate that drifts from the true rate differential, leaving a broker-specific,
staleness-and-markup residual only this desk can see. Measured on the 29 Forex majors/crosses
against BIS `WS_CBPOL` daily central-bank policy rates:
**`carry_ann = 0.038 + 1.002 × (r_base − r_quote)`, R² = 0.9781, residual sd = 0.258 pp/yr.**
A unit slope is a pass-through. The administered swap *is* the policy differential to within 26
bp/yr, so the object the card was built on does not exist on the majors. `crowded_known` applies
→ EV **0.0013** → REJECT, the exact branch the card pre-registered as killing.

**AND THE EXOTICS' APPARENT RESIDUAL IS A COST, NOT A MISPRICING.** All-FX R² is only 0.36, which
looks like structure until conditioned: `corr(|resid|, markup)` = **0.943** across 79 symbols and
**−0.005** within the markup<5pp subsample. The entire exotic residual is the broker's both-sides
wedge (USDINR **100 pp/yr**, USDBRL 36, USDIDR 33) leaking into the mid. **A markup is paid on
either side; there is no leg that earns it.** The family dies on both halves of the universe for
two different reasons.

**TWO CARD CLAIMS ALSO FALSIFIED, recorded so they are not re-inherited:** (1) the lake does NOT
hold `fred_ECBDFR` — and FRED's OECD-MEI international rate series are withdrawn entirely (HTTP
400, 27/27 currencies), so the stated data route was dead as well as absent; (2) `swap_long` /
`swap_short` are **POINTS, not currency-per-lot** — held-out test fitting 22 non-JPY majors (where
`tick_size × contract_size` = 1 and the conventions coincide) and predicting the 7 JPY majors
(factor 100): RMSE **0.232** vs **207.499** pp/yr, an 894× separation.

**TAGS:** `crowded` + `no_economics` (on the majors) / `costs_killed_edge` (on the exotics).

**L1.16a RE-ENTRY DOOR (named, narrow).** The pass-through is a property of how this broker *sets*
the rate, not of the sample, so more data is NOT an enabling change and neither is another symbol
set. Re-open ONLY on: a demonstrated **time-series** lag — the swap table updating on a slower
clock than a *policy change*, measured across an actual rate decision with ≥3 months of the
hourly `broker_swaps` panel (73 snapshots over 3 days is not a sample). That is a different
quantity from the cross-sectional residual killed here, and it is the only version left alive.

**WHAT SURVIVED AS A COST FACT, not an alpha:** the majors' markup runs **0.55 pp/yr (GBPUSD) to
2.43 (GBPCHF)**, a 4.4× spread ordered by quote currency (CHF > JPY > commodity dollars),
correlated 0.316 with |rate differential|. Useful for choosing where to express a carry-holding
view; `execution_resolver` already reads the per-symbol field, so it is a measurement of an
existing input rather than a missing one.

**EVIDENCE:** `data/research/s14_swap_decomposition.json` (79 symbols, four fits, the convention
test, 26 BIS rates with as-of dates). Derivation: `docs/research/prospector_coverage.md` s14 item 1.
Related: **R0708** (the `execution_resolver` unit defect this test exposed), **R0709** (the BIS
replacement source).

### `fx_time_of_day_short_0900gmt_wed_thu_fri` — PROSPECTOR s18, 2026-08-29 — `confound_uncontrolled` (short-bias proxy) + `costs_killed_edge`   [universe: **MT5**, mandate-valid]

**CLAIM (published, `quantsjourney.blogspot.com/2017/09/two-strategies-you-can-start-trading.html`,
2017-09-07, VERIFIED — post body fetched, robots `Allow: /`):** "Short at GMT 09:15, on Wednesday,
Thursday and Friday, close after 5 hours" on EURUSD. Author's own backtest 2007-01-01→2017-05-05 on
M15. Companion claim (strategy 2): short USDJPY at 00:15 GMT, close after 5h, all weekdays.

**WHY IT NEVER HAD A MECHANISM.** No forced participant is named anywhere in the post. The author's
only causal gesture is a link to a Ranaldo PDF on intraday FX segmentation — a *descriptive* result
about session structure, which does not imply a directional short. The rule is a clock and a
direction with nothing between them.

**THE MULTIPLICITY WAS PRINTED IN THE POST.** `bt.test_all(hypo,'ALL')` runs **15 pairs** and the
pasted output accumulates the winners: strategy 1 → `['EURGBP','EURUSD','AUDUSD']` (**3/15**),
strategy 2 → `['USDJPY']` (**1/15**). A later `EDIT Nov 5th, 2017` narrows strategy 1 to EURUSD
alone — **1/15, selected after seeing the curves.** Uncorrected selection over 15 trials.

**KILLED ON 8.6 YEARS FULLY OUT-OF-SAMPLE TO THE AUTHOR** (`EURUSD_H1.parquet`, 2018-01-01→
2026-08-28, n=53,894; broker-EET stamps converted to GMT at +3 summer/+2 winter; cost taken from the
**tape** at 12.0 pts / `digits=5` = **1.07bp round trip**, never from the registry, whose EURUSD
`median_spread_pts` is the 0.0 defect of R0729):

```
S1 AS PUBLISHED  short 09GMT Wed/Thu/Fri   n= 1348  gross +0.72bp  net -0.35bp  t=-0.43
CONTROL A  short 09GMT all weekdays        n= 2246  gross +0.50bp  net -0.56bp  t=-0.96
CONTROL B  short every hour (short bias)   n=52689  gross +0.05bp  net -1.02bp  t=-11.25
CONTROL C  LONG 09GMT Wed/Thu/Fri          n= 1348  gross -0.72bp  net -1.78bp  t=-2.20
```

**It does not clear its own spread**: gross +0.72bp against 1.07bp round trip. It dies at the L1.5
money bar before significance is relevant. **Hour 09 is not special** — shorting every hour, all
weekdays, hour 09 ranks **6th of 24** on net t, in a smooth session profile with no spike, and all
24 hours are net-negative.

**THE CONFOUND, NAMED BY A COMMENTER IN 2017 AND CONFIRMED HERE.** Top reply on the post: *"The
EURUSD strategy is simply benefiting from the strong down trend since 2008 ... Try the same strategy
from 2000 to 2007!"* Split by trend direction:

| sub-period | EURUSD total move | S1 net | t |
|---|---|---|---|
| 2018–2021 | **−5.33%** | **+0.40bp** | +0.39 |
| 2022–2026 | **+1.88%** | **−1.00bp** | −0.81 |

**The sign of the strategy tracks the sign of the trend.** It is a short-bias proxy with a clock
attached — precisely the confound the commenter specified, settled on data he did not have.

**TAGS:** `confound_uncontrolled`, `costs_killed_edge`, `selection_over_15_trials`, `no_mechanism`.

**L1.16a RE-ENTRY DOOR (named, and it is narrow).** The killed quantity is a *directional* time-of-
day edge. What is NOT killed and was never tested here is the **non-directional** session structure
the Ranaldo citation actually describes (range/volume/spread by hour), which the desk's
`cost_surface.py` already builds from its own tape and uses as a *cost* input, not an alpha. Re-open
only on a time-of-day claim that (a) names a forced participant, (b) is direction-neutral or
justifies its direction mechanically, and (c) clears the tape-measured spread gross. More data is
**not** an enabling change: 8.6 years of OOS is already the test.

**RELATED / DO NOT RE-MINE:** the parent descriptive post `time-of-day-effects-in-fx` was already
EV-rejected by PROSPECTOR s16 as `fx_time_of_day_session_handover_drift` (EV 0.00020). The host
`quantsjourney.blogspot.com` is **EXHAUSTED** (6/6 posts, sitemap-enumerated, comment layer mined) —
see `docs/research/prospector_coverage.md` s18 item 3.

**EVIDENCE:** post body + 9 comments fetched 2026-08-29; sitemap `6 <loc>`; derivation and the full
control table in `prospector_coverage.md` s18 item 3.

## 2026-08-29 — REFUSED: adaptive (bandit) allocation over the search grid — brain_hunter s15

MECHANISM: epsilon-greedy multi-armed bandit over simulation CONFIGS (neutralization, truncation,
delay, weight cap), reward = the candidate's own in-sample Sharpe/fitness. SOURCE:
`zhutoutoutousan/worldquant-miner` (Apache-2.0, 728★). DERIVES-FROM: NONE (checked).

MECHANISM OF DEATH: incompatible with pre-registered multiplicity. `FusionPlan.effective_n_trials`
is the enumerated grid hashed before compute, and that is honest ONLY while allocation is
non-adaptive. An allocator that concentrates trials on arms that already scored well is
data-dependent selection that no fixed `n_trials` can price. L1.60 in architectural form.

MEASURED ON THE SOURCE: three stacked selection engines (LLM writer + genetic mutator + config
bandit) and **0 of 1,631 `.py` files** match any multiplicity-correction term. The published bandit
also does not compile (`adaptive_alpha_miner.py:491`) and its arm key drops two of its four axes
(56 arms → 28 keys; `delay` and `maxTrade` unreachable).

L1.16a RE-OPEN CONDITION: a named enabling change that prices adaptive allocation honestly — e.g. an
allocator restricted to re-ORDERING cells within a fixed pre-registered membership (ordering free,
membership pre-registered), or a published correction valid under data-dependent trial allocation.
Not before.

## 2026-08-29 — REFUTED: block-order permutation as an "adversarial" validity test — brain_hunter s16

MECHANISM: shuffle the panel's dates in contiguous BLOCKS, recompute forward returns, and pass a
factor when `real|IC| / mean(shuffled|IC|) > 1.5`. SOURCE: `Miasyster/QuantGPT` (MIT, 457★),
`quantgpt/adversarial_validator.py::test_temporal_shuffle`, defaults `block_size=20` against its
own `holding_period=5`. DERIVES-FROM: NONE (checked — no citation in the repo; the sibling
`test_label_permutation` is a correct 95th-percentile permutation null and is NOT graveyarded).

MECHANISM OF DEATH: **the test has zero power at its shipped defaults, and it errs toward
rejecting real signal.** Block-ORDER shuffling preserves within-block temporal alignment, so only
forward-return windows straddling a block boundary are disturbed. Measured on a synthetic panel
(60 names × 500 days, factor loading on the next-5-day cumulative return at a controlled strength,
20 shuffles per cell, `data/brain_hunter_s16_multiplicity_prior.json`):

| injected strength | real \|IC\| | ratio @ bs=20 | verdict | ratio @ bs=5 | verdict |
|---|---|---|---|---|---|
| 0.0 | 0.0001 | 0.07 | FAIL | 0.02 | FAIL |
| 0.1 | 0.0439 | **1.11** | FAIL | 2.18 | PASS |
| 0.4 | 0.1588 | **1.19** | FAIL | 2.38 | PASS |
| 3.0 | 0.4732 | **1.16** | FAIL | 2.19 | PASS |

The ratio is **pinned at 1.16–1.19 across a 10× range of real IC** and never reaches the 1.5 bar.
The verdict is a function of `block_size / holding_period` ALONE and is independent of whether the
factor is real: at `bs = HP` it is pinned at 2.19–2.44 and always passes. A test whose output does
not move with its input is not a test.

SECOND DEFECT, same direction: the baseline averages `abs(mean IC)` ACROSS shuffles — `E|X|`, not
`|E X|` — so the denominator carries a positive noise floor (0.0053 here) even under a pure null.
At strength 0 the real |IC| (0.0001) sits BELOW the shuffled floor.

WHAT SURVIVES AND IS ROUTED, NOT BURIED (`improvement_inbox.md`): the two design rules this
refutation establishes — a block-permutation null has power only when `block_size ≤ forecast
horizon`, and the null must be a PERCENTILE of the permuted distribution rather than a ratio of
means against an uncalibrated constant.

L1.16a RE-OPEN CONDITION: a block-permutation test whose block size is bounded by the horizon it
tests AND whose bar is a percentile of its own permuted distribution. That is a different test.

---

## 2026-08-29 — `QuantGPT.adversarial_validator.test_noise_injection` — REFUTED (BRAIN HUNTER s17)

SOURCE: `Miasyster/QuantGPT` (MIT, 457★), `quantgpt/adversarial_validator.py:253-299`, the fourth
of the four adversarial tests on this ground. DERIVES-FROM: s16's refutation of
`test_temporal_shuffle`, same file, same power-control design. Artifact:
`data/brain_hunter_s17_adversarial_power_and_costs.json`.

CLAIM: adding Gaussian noise at 0.5× the factor's own std should destroy a fake factor and only
degrade a real one, so "retains ≥ 50% of original |IC|" separates robust from fragile factors.

MECHANISM OF DEATH: **the retention ratio is an attenuation constant that does not depend on the
factor's true IC at all, and the shipped bar sits below it.** For `f' = f + kσε`,
`corr(f', r) = corr(f, r) / sqrt(1 + k²)` — the true IC cancels. At the shipped `k = 0.5` that
constant is **0.8944**, well above the shipped 0.50 bar, so the test cannot fail a real factor.

Measured on a synthetic panel (40 names × 200 bdays, exact injected IC, 2 seeds per cell, test
called at its shipped defaults):

| injected true IC | realized IC | retention @ 0.5× | verdict |
|---|---|---|---|
| 0.00 | −0.0073 | 0.7312 | **PASS** |
| 0.00 | 0.0103 | 0.5317 | **PASS** |
| 0.05 | 0.0404 | 0.9294 | PASS |
| 0.10 | 0.0868 | 0.9087 | PASS |
| 0.20 | 0.1814 | 0.8990 | PASS |
| 0.40 | 0.3706 | 0.8976 | PASS |

**14 of 14 cells pass, including all six pure-null cells.** The verdict never varied with the
injected signal. Analytic confirmation across the noise ladder (200 draws per cell):

| k | predicted `1/√(1+k²)` | measured, true IC = 0.30 | measured, true IC = 0.02 |
|---|---|---|---|
| 0.1 | 0.9950 | 0.9936 | 1.6009 |
| 0.5 | 0.8944 | 0.9030 | 2.1067 |
| 1.0 | 0.7071 | 0.6959 | 20.7032 |
| 2.0 | 0.4472 | 0.4523 | 2.1415 |

SECOND DEFECT, and it is the worse half: under a near-null factor the statistic is a ratio of two
near-zero quantities, so it does not merely pass — it **explodes above 1.0** (means 1.30–20.70) and
passes *harder* than a genuine factor. A reader ranking factors by this diagnostic would rank the
noise first.

WHAT SURVIVES AND IS ROUTED, NOT BURIED (`improvement_inbox.md`): the sensitivity idea is sound but
the statistic must be the SLOPE of `|IC|` against `1/√(1+k²)` — a real factor tracks the line with
slope ≈ 1, a null factor does not track it at all — never a single retention level against a fixed
bar, because the level is a property of `k` and not of the factor.

L1.16a RE-OPEN CONDITION: a noise-injection test scored on agreement with the analytic attenuation
curve across ≥3 noise levels, with the null's ratio instability handled explicitly. That is a
different test.

---

## 2026-08-29 — BRAIN s18: the "self-correcting AST" and the "retry until successful" repair loop are both REFUTED as capabilities

**Artifact:** `zhutoutoutousan/worldquant-miner` @ `6a0c9433`, Apache-2.0.
**Probe:** `data/brain_hunter_s18_validator_probe.py` → `data/brain_hunter_s18_validator_probe.json`.
**Why this is a graveyard entry and not an inbox note:** three consecutive sessions (s15, s16, s17)
named `fast_expr_ast.py` + `template_validator.py` as this ground's top un-mined item, on the
stated reasoning that "the expression AST's VALIDATOR names the well-formedness failure modes
someone else paid to discover". The failure modes are real and are routed to the inbox. The
*validator* is not.

### 1. `fast_expr_ast.py` (921 lines) is unreachable in the shipped configuration

`TemplateValidator.__init__` takes `use_ast: bool = False`. The repo's **only** instantiation site
— `generation_two/core/template_generator.py:187-192` — passes `use_ast=False` explicitly, with
the comment *"Disable AST by default, use prompt engineering and database knowledge only"*.
Every AST path is gated on that flag: `_fix_with_ast`, `_generate_fix_from_ast`,
`learn_from_success`, `SelfCorrectingAST.learn_from_error`, and the `store_ast_pattern` call in
`learn_from_simulation_error`. The AST, its self-correction and its pattern learning are dead code
in the only configuration the repo ever runs. **The desk spent three sessions ranking a component
its own author switched off.**

### 2. Consequently the "learned compiler knowledge" is empty, and ships that way

`generation_two/core/compiler_knowledge.json` describes itself as *"Compiler logic as code —
learned from runtime errors and reverse engineered from AST"* and ships with
`incompatible_operators: []`, `learned_rules: []`, `successful_patterns: []`,
`failed_patterns: []`. Every non-empty rule in the file is hand-written prose. The behaviour is
carried entirely by a hardcoded 15-name fallback set inside `_get_incompatible_operators`. This is
the desk's own recurring class — a learning loop whose output is an empty artifact that reads
identically to "nothing to learn".

### 3. The error classifier cannot name 4 of the 8 classes the repo builds fixers for — MEASURED

`_classify_error_from_message` matches four regex families (`unknown_variable`, `invalid_field`,
`syntax_error`, `type_error`). Fed one canonical message per shipped error class, it returns
`unknown_error` for **event-input incompatibility, arity, unexpected-character and
missing-lookback** — precisely the four classes with dedicated repair functions and dedicated
retry arms. Its output is stored as the `error_type` metadata key on every learned pattern, so the
learning loop is label-collapsed at the source even when the AST is enabled.

### 4. `max_attempts = 999` is a fixed-point spin, not a retry — MEASURED

`refeed_with_correction` sets `max_attempts = 999` ("retry until successful") for three error
classes and, for exactly those three, **explicitly skips prompt engineering** — the only
stochastic element in the loop. What remains is deterministic string rewriting. Measured over 9
cases, both repair functions reach their fixed point by pass 2 (`fixed_point_at_pass` ≤ 2 in every
case, and = 1 whenever the first pass changed nothing). So attempts 2…999 recompute a byte-
identical template. `_fix_input_count_error` failed to repair 1 of 3 arity cases
(`ts_corr(close, open, 20)` against "should be exactly 2" — unchanged), which is a concrete
instance that spins the full 999. Input-count and unexpected-character have no in-loop state
change at all; the event-input arm calls `_learn_event_input_compatibility`, so only that arm has
any mechanism by which a later pass could differ.

### 5. The "aggressive" fix no-ops on operators the repo's own knowledge file names — MEASURED

`_aggressive_event_input_fix` claims to "replace ALL incompatible operators". It is a table of 15
hardcoded names. `compiler_knowledge.json` states the rule *"Cross-sectional operators (rank,
winsorize, zscore) do not support event inputs"*; the table contains `rank` and neither of the
other two, and contains no group operator. Measured: `group_rank(...)`, `winsorize(...)` and
`zscore(...)` are returned **unchanged**, 4 of 6 probe cases no-op — after which the loop appends
"Applied aggressive event input fix" to its fix list regardless and re-enters the 999-spin.

### The common mechanism of death, and it is one the desk keeps meeting

Every one of these is a **verdict or capability that is a constant function of configuration
rather than of the input**: a flag off at the only call site, a classifier whose vocabulary does
not intersect its own error set, a retry bound over an idempotent function, a claim of exhaustive
replacement over a hardcoded list. Same shape as s16's `test_temporal_shuffle` and s17's
`test_noise_injection`, and the same shape as the desk's own `GAP-FIXER 2026-08-29` finding
(a verdict computed then discarded by the layer above).

### L1.16a RE-OPEN CONDITION

A NAMED enabling change: an upstream commit that flips `use_ast=True` at the call site, or that
adds patterns to `error_patterns` covering the four unreachable classes. Absent that, no seat
re-reads `fast_expr_ast.py` or `template_validator.py`. The **taxonomy** extracted from this file
is live and sits in `improvement_inbox.md` under the same date; only the implementation is buried.

## 2026-08-29 — BRAIN s19 — a performance chart that fabricates the history it draws

**Artifact:** `zeron-G/worldquant-alpha-research-agent` (MIT), `streamlit_app.py:1184-1200`,
`_synthetic_rows`-shaped fallback feeding `render_performance_chart`.
**What it does:** when a candidate has no real performance rows, it returns 126 rows of
`PnL` / `Sharpe` / `Turnover` generated by a deterministic seeded `math.sin` walk off three scalars
(`score`, `metrics.sharpe`, `metrics.turnover`), dated from 2014-01-03, and the UI draws them as
that alpha's track record.
**Why it is buried and not merely noted:** the rows carry **no marker**. A fabricated history and a
real one are byte-identical in shape at the point of reading, and the fallback is silent, so the
failure mode is a chart that looks like evidence. Same class as the desk's own recurring defect —
a display asserting data it does not have (WS-005 family: absence rendered as a clean reading).
**Not transferable as a technique, and that is the point:** logged so no seat mistakes this repo's
screenshots for evidence, and so the class is named the next time a dashboard on this desk fills a
gap instead of showing one.
**L1.16a re-open condition:** an upstream commit that labels the synthetic rows in the returned
payload, or removes the fallback. Then the repo's UI becomes readable again; the technique never does.
**Desk-side transfer check: NULL** — see `prospector_coverage.md` s19; the only `np.sin`+`np.random`
candidate in `desks/mt5/side_channels/` is a `__main__` demo that writes nothing.

## 2026-08-29 — aznikline/alpha-mining-system genetic-programming factor generator (BRAIN hunter s20)

**Class:** generator whose objective is noise by construction.
`alpha_mining/factor_engine.py:179` sets `y = np.random.randn(X.shape[0])` under the comment
"random y, will be overridden when fitness uses IC"; it is never overridden, and `gp.fit(X, y)`
(line 209, `metric='pearson'`) evolves `population_size=200 × generations=20` = 4,000 programs to
maximise correlation with that random vector. The hall-of-fame is returned as named factors
`gp_alpha_01..NN` and evaluated downstream like any other candidate.
Bounded: E[max |pearson|] over 4,000 noise programs = 0.0846 at n=2,000 and 0.0381 at n=10,000 —
**3.8x the single-program sd in both cases**, i.e. ~3.8 sd of pure selection on a target carrying
zero information. Worse than uncontrolled multiplicity over a real target: no downstream control
can rescue an objective that is noise.
**Nothing from this generator is importable.** Desk transfer check RUN and NULL — no desk
generator fits a placeholder or random target (only `desks/mt5/research/admission.py:343,373`, a
labelled synthetic sensitivity study that writes no artifact).
Evidence: `data/brain_hunter_s20_group_axis_and_gen_scale.json`; sha `7b149c2`.

## 2026-08-29 — "the BRAIN generator class supplies a peer-grouping axis" (BRAIN hunter s20)

**REFUTED at n = 0**, and the near-miss is instructive. `aznikline::_calculate_group_returns` is a
quantile-portfolio function (`pd.qcut` on the factor's own values), not a peer grouping — a
vocabulary collision that s19 read as a grouping-axis touch. The class's only real grouping
consumer, `_neutralize_factor`, is inert twice: its producer writes the constant
`df['group'] = 'unknown'` (`data_hub.py:279`, so `get_dummies` yields shape `(n,0)`), and its
consumer seeds `X_list` with a 1-D `np.ones_like(y)` that makes `np.hstack` raise on every call
with any regressor present, caught by a bare `except:` that returns a plain demean. The advertised
"industry/size neutralization" never runs, silently, 100% of the time.
**Consequence for this desk:** the founding blocking input — no grouping map — gets no help from
this ground. A grouping map must be BUILT. Re-entry only on a new repo entering the population.

## 2026-08-29 — IMF Primary Commodity Prices (PCPS), on EVERY route (free-data run x; disposed by BRAIN hunter s22)

**Class:** licence hard-stop (§13), not a route failure. Run (w) adopted PCPS via the DBnomics
mirror having left the IMF's own terms **unread** (`imf.org` 403s datacentre IPs); run (x) read them
on two independent routes and the adoption does not survive.
**Mechanism of death:** the IMF terms (`imf.org/external/terms.htm`, Wayback `20241007090557`) grant
download "**for personal, noncommercial usage only, without any right to resell or redistribute or
to compile or create derivative works**". A desk building features is commercial derivative-work
creation. **The mirror does not launder it:** the FRED route (release `rid=365`, 189 keyless series,
fresher than DBnomics at 2026-07 vs 2025-06) carries "Copyright © 2016, International Monetary Fund.
Reprinted with permission." and FRED's own ToU FAQ Q3 states that permission is **non-transferable**
— "the Federal Reserve Bank of St. Louis cannot give you such permission."
**A working route is not a licence.** Both live doors (FRED CSV, DBnomics) are technically open and
both are forbidden; a source can pass every technical check and still be unusable.
**L1.16a re-open condition:** written permission from the IMF, or a PCPS re-release under an open
licence. Nothing about a new mirror, a new endpoint or a fresher vintage re-opens this.
**Replacement already adopted:** World Bank Pink Sheet (card 91) — CC-BY, 32 years deeper.

## 2026-08-29 — naive text-layer extraction of KERNED PDF tables (free-data run x; disposed by BRAIN hunter s22)

**Class:** extraction METHOD refuted; the population it was aimed at (LBMA forecast back-years)
survives and is still worth mining by another method.
**Mechanism of death:** in the LBMA forecast PDFs the text layer is kerned character-by-character
(`1 , 1 00 7 5 0 9 50` for 1,100 / 750 / 950). The separator BETWEEN columns is a single space
**identical** to the space INSIDE a number, so the extractor cannot tell them apart and both
readings are silently plausible: a rank-walking parser recovered the row counts **exactly right**
(24 gold / 20 silver / 20 platinum / 20 palladium) while producing a gold mean of **150.04** against
the document's own printed **880.74**; de-kerning fails the opposite way, fusing the published
averages line into `1073.54721.46880.74`.
**The transferable lesson, and it is the expensive one: a correct row COUNT is not evidence the
parse worked.** Had the count been trusted, a fabricated analyst panel would have been carded.
Same family as "clean output from a broken extractor" (s13) — and `alch41_forecast` in the same
population decoded **1 of 8** streams and still yielded 19KB of clean-looking text.
**Population census retained (this part is NOT dead):** 9 distinct PDFs retrieved, but only 4 carry
the four-metal per-analyst tables in the text layer (`lbma_2008forecast`, `lbma_2009forecast`,
`forecast2009`, `forecast2011`); the other five are commentary editions whose tables are images.
**L1.16a re-open condition:** a positional extractor that reads the PDF content stream's `Tm`/`TJ`
X-coordinates rather than the flattened string, validated against the document's OWN printed
aggregate (gold 1073.54 high / 721.46 low / 880.74 average) as a built-in control. Any re-extraction
that cannot reproduce that printed average is wrong regardless of how right its row count looks.

### 2026-08-29 — REFUTED: "correlation-cluster content keeps rising with k" (BRAIN HUNTER s25/s26, killed by s27)

**Claim:** the desk's grouping map should move to higher cluster counts — s25 measured content
rising from 0.145 at k=24 to 0.318 at k=128 and called k=24 "0.145 left on the table"; s26 adopted
Ward k48/k96 on the same reasoning.

**Mechanism of death:** the ruler's evaluated population SHRANK with k (240 symbols at ward k=24,
28 at k=224), so rising "content" was the measurement contracting onto the symbols that cluster
most easily, not the grouping improving. Re-scored on one held population of 101 symbols
(`data/brain_hunter_s27c_common_population.json`), ward's k-curve is monotone DECREASING and
k=24 is the best cell in the grid (+0.3184, z=−38.6, control and real on the identical 101).

**Compounding cause:** the size-matched control's population guard compared the UNION of symbols
retained across eval years. Real singletons are the same symbols every year; a shuffle re-rolls
them, so the union always inflates — drift positive in 144/144 draws — and 26 of s26's 55 cells
were voided UNMEASURED by a property of the guard.

**Reopen condition (L1.16a):** a named enabling change that makes high-k groupings evaluable on
the FULL universe rather than on their own retained subset — e.g. a peer assignment that gives
singletons a nearest-cluster fallback instead of dropping them. Until then, k>24 must not be
preferred on the s25/s26 evidence.

---

## ALPHA101 AS A BODY OF IMPORTABLE ALPHAS — KILLED BY AN INDEPENDENT AUDIT (BRAIN HUNTER s28, 2026-08-29)

**Claim:** the 101 Formulaic Alphas are a ready stock of alpha the desk should translate to MT5.
Four sessions (s10, s12, s13, s14) went into recovering the formulas correctly — a transpiled
public implementation was found to invert corr/cov at 47/47 sites (s12), a PDF extractor returned
clean text from 1 of 22 pages (s13), and the field/glyph layer was repaired (s14). The implicit
premise throughout was that a CORRECT alpha101 is worth having.

**Mechanism of death:** an independent, audited, out-of-time replication —
`OctopusTakopi/toraniko-alpha101` (MIT), S&P Composite 1500, 2023-01-03 → 2026-07-16, signals at
*t* applied to *t+1*, quintile long/short, formula-mandated GICS neutralisations checked against
an explicit manifest — reports, against the paper's own numbers:

| statistic | audit (2023–2026) | paper |
|---|---:|---:|
| max Sharpe | 2.120 | 4.162 |
| median Sharpe | 0.518 | 2.224 |
| mean Sharpe | 0.411 | 2.265 |
| positive-Sharpe alphas | **74/101** | 101/101 |

**Median Sharpe falls by 4.3x and 27 of 101 alphas are outright negative** on a modern
cross-section, BEFORE costs and WITH survivorship bias helping the replication (current
constituents only). This is not a coding dispute — it is the same formulas, audited, on later
data.

**AND THE SURVIVORS DIE TO COSTS AT MT5 SPREADS.** Break-even round-trip cost per unit of gross
turnover, computed from the audit's own annual-return and turnover columns (mean daily return in
bp ÷ daily turnover):

| alpha | Sharpe | bp/day | daily turnover | break-even cost |
|---|---:|---:|---:|---:|
| alpha021 | 2.120 | 2.54 | 39.9% | **6.4 bp** |
| alpha043 | 1.512 | 2.53 | 54.5% | 4.7 bp |
| alpha011 | 1.339 | 1.89 | 56.7% | 3.3 bp |
| alpha096 | 1.153 | 0.74 | 34.3% | 2.2 bp |
| alpha054 | 1.082 | 1.98 | 79.3% | **2.5 bp** |

The whole distribution lives inside **2–13 bp of round-trip cost**. That is survivable on US
equities and is NOT survivable across an MT5 book whose non-major legs cost multiples of it — and
the desk's own spread census (R0728, s24b) shows `universe.json` UNDERSTATES spreads, so the true
margin is thinner than any number here. A cross-sectional daily alpha earning ~2.5 bp/day at 40%
turnover has no room for a CFD book's costs.

**Supporting refutation from the same audit:** mean/median pairwise alpha-RETURN correlation is
0.1942 / 0.1711 across 5,050 pairs. So the 101 are ~correlated as the paper claimed — the body is
not 101 independent bets, and importing many of them buys far less independence than the count
suggests. (This is a RETURN correlation on an equity cross-section and is NOT the same quantity as
s14's 87.33% max pairwise SIGNAL correlation measured on desk tape; the two are not in conflict
and must not be quoted as one number.)

**Also refuted, incidentally:** adding `log(Turnover)` to `log(Return) ~ log(Volatility)` gives a
coefficient of −0.016 at t = −0.072 — turnover explains nothing once volatility is in. Any
argument that a turnover penalty is picking up a return-relevant quantity, rather than a COST
quantity, is unsupported on this evidence. The fitness formula's churn penalty stays a cost
argument, which is the only footing it ever had (`wq_operators.fitness()`, diagnostic only).

**WHAT SURVIVES AND IS NOT KILLED HERE:** the alpha101 *vocabulary* — the operators, the
transformation grammar, the neutralisation idea, the construction methodology. That is exactly
what BRAIN HUNTER exists to extract, and s28's type-algebra find
(`docs/research/search_operator_library.md`) is worth more than any formula in the paper. The
FORMULAS as deployable alphas are dead; the METHOD is not.

**Reopen condition (L1.16a):** a named enabling change to the cost side — an execution venue or
instrument set where a 2–13 bp break-even is comfortable — or an audited replication on a
cross-section resembling the MT5 book rather than US equities. Neither exists today.

**Provenance:** SOURCE `OctopusTakopi/toraniko-alpha101` README + `reports/full_market/
alpha101_analysis.md` (public, MIT, raw.githubusercontent, mined as TEXT). DERIVES-FROM: the desk's
own s10/s12/s13/s14 alpha101 line. Claimed-not-verified: the audit's Sharpes are ORE — they are
another desk's numbers on another universe. They are used here only to KILL an import, never to
justify one, which is the direction in which unverified ore is admissible.

### 2026-08-29 — BRAIN s29: two pre-registered claims, both refuted

**KILLED: "cluster neutralisation helps dispersion features and hurts trend features" (s28's rule).**
Tested on six features s28 never saw, sign pre-registered before the run, falsifier declared at 6/6.
Result **5/6 — refuted as stated**. `mom_250` was predicted negative and came in **+0.194 at z=+5.51**
against its own size-matched permuted control. The rule as a *feature-family* statement is dead.
Evidence: `data/brain_hunter_s29_neutraliser_rule.json`. Mechanism of death: the axis is HORIZON, not
family — neutralisation hurts at 5d–120d and helps at 250d and at every dispersion feature.
**L1.16a reopen condition:** a pre-registered horizon-crossover test (150/180/200/250/300d) confirming
the crossover would revive the *idea* under a corrected statement; nothing revives the family version.

**KILLED: coarse cross-sectional rank as a turnover lever.** The platform's default `rank(x, rate=2)`
is deliberately imprecise, which suggested a free turnover cut for cells that die on cost. Measured
across 6 bucket counts × 3 cells (18 trials, all reported): precise → 3 buckets moves daily turnover
**1.467 → 1.452 (−1.0%)**, break-even bp non-monotone, effect within noise on every cell. Evidence:
`data/brain_hunter_s29b_coarse_rank.json`. Mechanism of death: `reversal_1` is yesterday's return and
re-sorts the whole cross-section daily, so the ordering *inverts* rather than jitters and coarsening
has nothing to bite on. Confirming contrast in the same table: persistent `lowvol_20` turns over 0.586
vs reversal's 1.467 on identical machinery. **This kill is directional** — it identifies feature
autocorrelation (hence `decay_linear`) as the only remaining lever on this family's binding constraint.

**NOT A KILL, a correction to one: `yli188`'s corr/cov inversion (s12) is repo-specific.**
`efJerryYang/worldquant-brain-simulator` cites yli188 as its source yet implements `correlation` and
`covariance` correctly. s12's finding stands against that repo; it must not be generalised to the
alpha101 transpile lineage as a whole.

## 2026-08-29 — `decay_linear` as a cost lever on the cross-sectional reversal family: REFUTED

**Pre-registered, falsifier stated in advance, both arms.**
`data/brain_hunter_s30c_decay_lever.json` · `data/brain_hunter_s30c_decay_lever.py`
(BRAIN HUNTER s30c; the mechanism is BRAIN's `ts_decay_linear`, ported as a mechanism — linear
weights d, d−1, …, 1 over each symbol's own valid observations — never copied as a formula.)

s29b established that this family's turnover is a property of the **feature's autocorrelation**,
not of the ranking operator, and named feature smoothing as **the one identified lever** on the
constraint that kills every cell in the family. The platform ships it as a first-class setting
(`decay: 30`). This run swept d ∈ {1,2,3,5,10,20,30} on `reversal_1`, both neutralisation arms,
2019–2026 daily MT5 closes.

- **Mechanical check (a) PASSED on both arms** — turnover strictly decreasing in d
  (ward: 1.467 → 1.247 → 1.128 → 0.997 → 0.856 → 0.754 → 0.703). The port does what the operator
  says, so the refutation below is of the claim, not of the code.
- **Substantive claim (b) REFUTED on both arms** — break-even cost is **maximised at d = 1**,
  i.e. no smoothing. Ward arm: **1.596 bp at d=1**, and every d > 1 is worse (0.903, 0.787,
  0.376, 0.806, 0.785, 0.706). Universe arm the same shape: 1.484 at d=1, everything else below.
- **The mechanism of the refutation is visible in the numbers, and it is the useful part.**
  Decay destroys the signal faster than it destroys the turnover: one step of smoothing (d=2)
  costs **51% of gross Sharpe** (ward 0.759 → 0.368) to buy a **15% turnover reduction**
  (1.467 → 1.247). `reversal_1`'s information is essentially all in the most recent bar — which is
  what a one-day reversal *is* — so any average over prior bars is mostly deletion.

**Consequence, stated plainly: this family is dead on cost and the desk should stop trying to
rescue it.** Both identified levers are now refuted with pre-registered falsifiers — coarse ranking
(s29b) and feature decay (s30c) — and the best cell in the family survives only to **1.6 bp per
unit of turnover at ~147% daily turnover**, unsurvivable on any MT5 spread. Three sessions have
now been spent lowering the cost of a signal whose gross edge cannot pay a realistic spread.

**What is NOT refuted, and the distinction matters for L1.16a reopening:** decay as an operator
(it works, it is now ported and measured), decay on *slower* features whose information is not
concentrated in the last bar, and the platform's `ts_target_tvr_*` **solver** approach to the same
constraint (routed to `improvement_inbox.md` — untested, and it targets turnover directly rather
than sweeping a proxy for it). The kill is specific: **decay does not rescue a one-day reversal.**

## 2026-08-30 — BRAIN s34: BB-16 Alpha101 A-share validation uses tomorrow's execution state

**KILLED AS EVIDENCE, not as an operator library.** Public MIT
`BB-16/worldquant_101_alphas_code` at `320b3738c9807a47c85c457e56cf1ea95e80c106`
claims 101/101 formulas ran, 87/101 had positive IC, 61/101 had positive gross return and **8/101
remained positive after a flat 10 bp one-way cost** on 120 A-shares over 2025-02-05–2026-02-06.
The executable source makes the result inadmissible: `evaluate()` constructs the target as
`close.pct_change().shift(-1)` but filters positions at day *t* using
`buyable_mask.shift(-1)` / `shortable_mask.shift(-1)`. Those masks contain day-*t+1* open,
pause, limit, volume, close and traded-amount state. The selected book therefore knows tomorrow's
execution state, while its P&L also receives the close-*t*→close-*t+1* overnight move that occurs
before the claimed next-open execution. **All 101 reported cells share the defect; none is a
survivor or candidate.** [§33: killed -> `data/brain_hunter_s34_failure_cohorts_and_pit_audit.json`]

**MT5 analogue (confirmed through `translate_to_mt5`):** industry neutralisation maps to
asset-class/currency-risk-bucket neutralisation across the contemporaneous terminal-enumerated
Fusion universe. A literal transfer is D1: fix the signal at close *t*, execute at the next
actually available Fusion bid/ask, and begin P&L there. Costs are symbol-specific spread,
commission, slippage/partial-fill markout and swap—not the source's flat 10 bp. No next-bar
availability, spread, session or volume state may enter selection before it is observed.

**Reopen condition (L1.16a):** a corrected run using point-in-time membership/groups and either
next-open→close (or later) returns, with all 101 cells reported under executable costs. This kill
does not retire Alpha101's operators or construction vocabulary. SOURCE: repository files named
in the evidence artifact. DERIVES-FROM: *101 Formulaic Alphas*, declared by the repository; no
further implementation lineage was declared in the inspected files.

## 2026-08-30 — BRAIN s37: conditional robustness denominator, censored trials and last-write sensitivity memory

**Source:** public MIT `ljb189/wq-alpha-skill` at
`62c91e5920bfd53284a7be4407fda9d01ca05df0`, read as text only. No BRAIN credential/API or
third-party runtime was touched. DERIVES-FROM: WorldQuant BRAIN workflow; no code lineage was
declared in the inspected README/source.

**KILLED — conditional robustness rate.** R117 declares 12 candidates, 8 IS passes and 3
submission passes. `evaluate_robustness()` receives only submission-check rows from those IS
passes, reports **3/8 = 37.5%**, and labels the cohort `marginal`; the preregistered-population rate
is **3/12 = 25%**. With its own mean-margin result 0.00207 against 0.05, the source's own rules
would label the full cohort `overfit`. Upstream failures/timeouts are structurally unable to hurt
the displayed denominator. Reopen only if the denominator begins at every preregistered candidate
and stage attrition stays explicit.

**KILLED — serial early stopping as research policy.** Five consecutive IS failures plus any
failure name recurring three times stops later candidates. That is a private pre-gate whose
verdict depends on ordering and whose skipped cells are never trials. Reopen only as compute
scheduling that resumes every cell and reports every outcome; never as a rejection or truncation.

**KILLED — `parameter_name × value` as memory identity.** `update_param_sensitivity()` overwrites
one metrics/result object at that key, erasing expression, fields, settings, round and prior
observations. Reopen only as append-only full-experiment identities with aggregation derived after
the fact. Evidence: `data/brain_hunter_s37_conditional_denominator_audit.json`.

**MT5 disposition:** these are process refutations, not tradeable formulas. The exact analogue is
full-population accounting over every terminal-enumerated Fusion candidate. The source's equity
inputs are merely data-gap ore for Fusion US-share CFDs at D1, PIT-vintaged and executed at the
next real bid/ask with spread, commission, slippage/partial-fill markout and swap. Zero desk cells
were tried and zero alpha cards were raised.
