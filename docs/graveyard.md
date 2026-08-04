# Graveyard — rejected hypotheses (do_not_repeat)

Every entry is permanent. Never re-test an identical hypothesis; a *materially new* mechanism or
dataset is required to reopen a class. Tags feed the EV-gate priors in `alpha_economics.py`.
Machine copy: `web/discovery.json`. Companion: [[institutional_knowledge]].

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

| Hypothesis (external prior) | Verdict | Tag | Lesson |
|---|---|---|---|
| lit_trading_frictions_family (the published "trading frictions" anomaly category: illiquidity, spread, volume, turnover, price-level variants) | **102 of 106 (96.2%) fail to replicate** under NYSE breakpoints + value weighting; whole-corpus failure 65% at t>1.96 and **82% at the 2.78 multiple-test hurdle** across 452 anomalies | `no_economics` / external-literature | Hou–Xue–Zhang, *Replicating Anomalies*, RFS 2020 — **primary text extracted and verified 2026-07-26** (not a summary; three numbers previously recorded from a search summary were WRONG and are corrected here). The desk's own `illiquidity_premium` kill (IC −0.043) was not bad luck — it is the MODAL outcome for the single worst-replicating category in the entire published anomaly literature. Do not reopen frictions-family variants. Mechanism: the original spreads are microcap-borne and equal-weighting-borne — real in the data, untradeable at size. **PER-CATEGORY BREAKDOWN (extracted 2026-07-26, NYSE-VW single test / multiple test at 2.78): Investment 73.7% / 50.0%; Momentum 63.2% / 49.1%; Profitability 44.3% / 17.7%; Value-vs-growth 42% / 10.1%; Intangibles 25.2% / 10.7%; Trading frictions 3.8% / 1.9%.** Recorded so the kill is not over-read: **investment and momentum are the ONLY categories that survive** — everything else fails at 82%+ under multiple testing. For THIS desk that residual is mostly unreachable: price-only momentum is already dead on desk data (420/0 + the era natural experiment), and 'investment' is an accounting characteristic with no crypto analogue for most assets. So the honest reading is *the equity literature's surviving signal does not transfer here*, not *the desk should go test investment factors*. |
| lit_crypto_xsec_size_and_volume (published crypto cross-sectional size/volume anomalies) | Spreads "originate from micro-cap coins of negligible economic importance"; crypto momentum's alpha "extracts... largely from short positions"; "most abnormal returns occur primarily in bull markets and fade over time" | `no_economics` + `regime_artifact` / external-literature | Fieberg–Liedtke–Zaremba, *Cryptocurrency anomalies and economic constraints*, IRFA 2024 (RePEc abstract, verbatim). Three independent mechanisms of death on the same family, and this is the CRYPTO restatement of the HXZ microcap finding by a different team. A long-biased, liquid-universe, cost-honest book captures approximately NONE of the published crypto cross-sectional spread — which is the external explanation for the desk's own 420-hypotheses/0-survivors record. |
| lit_defi_tvl_crosssection (TVL level AND **change in TVL** as a cross-sectional crypto return predictor, weekly) | 335 coins, 2023-01→2024-12: TVL-sorted alphas all p>0.13; overstatement-adjusted TVL p>0.46; **ΔTVL p>0.40**; GRS F-tests fail to reject zero alphas throughout (p 0.35–0.99) | `no_economics` / external-literature | Brigida (2025), arXiv 2506.03287 (full HTML read). CLOSES THE SECOND AXIS on the desk's own `defi_health` kill: the desk killed TVL at the daily BTC-timing horizon, this kills it cross-sectionally at weekly INCLUDING the change-in-TVL construction the desk never ran. Load-bearing bonus: headline TVL is mechanically OVERSTATED by staking/pool2/governance-token/borrowing/liquid-staking/vesting double-counts, so a vendor TVL *level* must never be trusted as a quantity. |
| lit_bruteforce_ratio_mining (mechanically generating large families of accounting/price ratio strategies and keeping the significant ones) | 2.1M strategies generated; "most rejections of the null of no outperformance under single hypothesis testing are likely false"; "a remarkably small number of strategies survive... **Even these surviving strategies have no theoretical underpinnings**" | `overfit` / external-literature | Chordia–Goyal–Saretto, *p-Hacking: Evidence from Two Million Trading Strategies* (SFI RP17-37, verbatim abstract). The closest published analogue to what a mechanical screening loop IS. Strongest external argument for the desk's mechanism-first gate: **statistical survival without a mechanism is not evidence** — the survivors of a brute-force search have no mechanism and therefore will not survive forward. Widely-quoted specific thresholds (|t|>3.79 etc.) are SUMMARY-ONLY and deliberately NOT recorded here. |

**Held back deliberately (provenance discipline, not an oversight):** Li & Zhu, *Taming crypto
anomalies* (crypto SIZE disappears out-of-sample; 13 of 49 anomalies significant) would be a fifth
row and it points the same way as row 2 — but its numbers reached the desk only through a search
index (SSRN 403s from this box). Per the desk's own rule a SUMMARY-ONLY claim may not be pasted into
the graveyard. It stays provisional in `docs/research/deep_sweep/LIT_a_failed_replication.md` F11
until primary text is read. Recording the abstention because the temptation to round it up is
exactly how a phantom prior gets installed permanently.

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
