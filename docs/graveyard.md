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
