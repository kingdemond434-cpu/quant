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
| commit_velocity_dev_momentum (cross-sectional, 35-asset survivorship-aware L1s, 1/3/6mo) | 1mo CS-IC -0.018 (t -0.68); 3mo +0.033 (t 1.21); 6mo +0.014 (t 0.55), 6mo L/S NW-t 1.53 -- NONE clear |t|>=2 | `insignificant` | The CORRECT test of the Electric-Capital thesis (ecosystem selection, not BTC timing; forward RELATIVE return; winners+slow-survivors+dead L1s to kill survivorship bias; monthly N not obs-N). Direction is thesis-consistent at 3/6mo (positive) but insignificant; raw commits = weakest proxy. RETENTION/MIGRATION escalation PRE-REGISTERED below -- do NOT fish more commit-count variants (multiplicity). |
