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
| smart_dumb_divergence (elite top-trader position ratio MINUS retail account ratio) | pooled mean IC +0.0032 (t +0.15, n=5 majors, 4h, 180 bars); 0/20 per-symbol screens passed | `no_edge` | THE DIRECT TEST of the Elite-Trader-Intelligence premise ('do skilled traders lead the crowd?'). Binance topLongShortPositionRatio (elite, size-weighted) minus globalLongShortAccountRatio (retail crowd) -- the two genuinely diverge in LEVEL (66.8% vs 55.1% long) but the divergence carries ZERO forward information. The 'smart money vs dumb money' signal is a narrative, not an edge, at aggregate 4h granularity. |
| elite_account_ratio (top-trader headcount long ratio) | pooled mean IC -0.0101 (t -0.32, n=5) | `no_edge` | Elite headcount positioning carries no forward information; only the size-weighted POSITION variant showed any sign consistency (logged as a candidate, not wired). |
| hyperliquid_trader_skill_persistence (41k-address leaderboard, 8,026 filtered, formation/holding rank test) | ADJACENT windows rho +0.120 (t +10.9) BUT with a ~3-week GAP rho FLIPS to -0.064 (t -5.8); long-horizon variant -0.060 (t -5.4); gapped decile spreads insignificant (t 1.33 / 1.15) | `position_overlap_artifact` | THE foundational test behind copytrading: does past trader performance predict future performance? The apparent persistence exists ONLY when formation and holding windows TOUCH -- a trader holding one position across the boundary yields mechanically correlated PnL (an open position, not skill); BTC's mildly-trending weekly path (-5.9/+6.8/+0.2/+1.5/+1.0/-0.0%) makes persistently-long accounts look consistently skilled. Insert a 3-week gap and it INVERTS to mild reversion. Robust in the safe direction: the leaderboard is a current snapshot so blown-up accounts are ABSENT, which biases persistence UP -- true persistence is <= -0.064. Top-decile forward returns were NEGATIVE in every variant (-1.7%, -3.4%, -28.6%). Kills the 26-layer Elite-Trader-Intelligence spec at its premise: selecting past winners selects luck. Do not re-test aggregate or per-trader copytrading without a GAPPED design. |
| hl_elite_directional_order_flow (Hyperliquid, performance-blind cohorts, 4h signed taker flow vs next-bucket return) | HFT-cohort BTC IC -0.139 (underpowered, 80 bkts); DIRECTIONAL cohort (260) BTC IC +0.157 / ETH +0.056, pooled t +3.00 on n=2 -- BUT breadth re-run (320, same rule, +60 traders) FLIPPED BTC to IC -0.033 + TIMING-ARTIFACT (same-period +0.202 > 0.20 gate); ETH IC +0.110 vs tercile spread -0.524% (opposite signs); 14/16 coins too thin | `unstable_artifact`/`no_edge` | Mechanism #3 of 3 pre-registered (after aggregate-positioning t+0.15 and gapped skill-persistence -0.064 both failed). Tested the actual copytrading mechanism: does elite flow LEAD price? Designed around both circularity traps (cohort selected on VOLUME/TURNOVER, never performance; flow(t) vs ret(t+1) only). Self-caught design flaw mid-experiment: top-VOLUME selection picks HFT/market-makers (2000 fills in 30 MINUTES) whose flow is inventory not conviction -- spec layer 11's own rule -- so re-selected on TURNOVER RATIO (1-25x/mo = discretionary). KILLED BY INSTABILITY: adding 60 traders to the SAME rule inverted BTC's IC sign. A real edge does not flip under cohort perturbation. Root mechanism: taker flow is CONCURRENT with price (buying moves price) -- it fails de-contamination, it does not lead. STRUCTURAL WALL: userFills caps at 2000 fills/address (30 min for the biggest accounts), so historical breadth is impossible from the snapshot API -- only forward accumulation could build it. Do not re-test elite/copytrade flow without >=8 coins AND cohort-perturbation stability AND a gapped/de-contaminated design. |
| hl_longterm_riskadjusted_skill (229 traders, median 621d / max 1195d verified on-chain records, own-curve 60/40 formation-holding split) | formation SHARPE -> holding return rho -0.019 (t -0.28) = ZERO; consistency t +0.45; total return t +0.73; cohort holding mean -3.3%, median -11.9%, only 40% positive | `no_predictive_power` | THE strongest version of the trader-skill hypothesis, built after the principal correctly objected that earlier tests used a ONE-WEEK holding window, no track-record filter, and raw-PnL ranking. Fixed all three: multi-YEAR records, risk-adjusted selection (Sharpe/consistency/drawdown), long-horizon holding, natural gap via own-curve split, pnlHistory normalised by contemporaneous accountValue so deposits are not counted as returns. Selecting proven multi-year traders by past Sharpe has ZERO forward predictive power. ONE PARTIAL EXCEPTION worth keeping: DRAWDOWN CONTROL persisted (rho +0.135, t +2.05; top-quartile holding +2.3% vs bottom -18.0%) -- does NOT clear the 4-test multiplicity bar (~2.5) so not an edge, but consistent with the classic finding that RISK characteristics persist while RETURNS do not. Also settles the 'dig deeper / Chinese / niche verified traders' objection: HL on-chain records are the STRONGEST available evidence class (cryptographically verifiable, losers included); self-reported or platform-curated track records are strictly weaker, and enlarging the search pool AMPLIFIES the winner's curse (max-order statistic gets more luck-dominated as N grows). |
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
