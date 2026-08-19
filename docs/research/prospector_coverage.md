# Prospector coverage map

_Seeded 2026-07-18; every family unvisited -- the first run biases per the rotation rule (>=40% of query budget to least-recently-covered). Log per session: family, date, queries spent, notable sources._

| Family | Last visited | Sessions | Notes |
|---|---|---|---|
| Podcasts/interviews | 2026-07-19 | 1 | 1 ep (Pavel Kycek, algoadvantage.substack.com) — CLAIM-grade, generic momentum+meanrev, no mechanism; 0 cards |
| YouTube/talks | never | 0 | untouched this session — priority next run |
| Forums (deep+legacy) | 2026-08-12 | 4 | s1 (07-25): Bitcointalk ERA-ARCHAEOLOGY opened — boards 8 (18,640 topics, 2011-14 era = offsets 14480-18640) + 78 (2,376 topics) mapped via OP-021; 6 topics mined to reply-depth → 3 graveyard entries + EN era lexicon. **s2 (08-04): QUANTOPIAN ARCHIVE OPENED — dead site (HTTP 000), 12 CDX pages of /posts/* slugs mapped (OP-034); olmar + in-and-out threads mined to reply-depth → 2 graveyard entries + diaspora answered (QuantConnect/IBridgePy/Slack/OSS org).** **s3+s4 (08-12, two runs): NUCLEAR PHYNANCE OPENED + WORKED — 6,645 thread captures CDX-mapped; 4 threads EXHAUSTED (161897 vol-carry/no-static-hedge, 161299 VR discipline, 161162 convexity-neglect → COIN-M dapi axis card 31 + EV-rejected RV, 161713 2012 validation time capsule); forum indices 8/13 classified (f2 TRADING = next batch ground, 25 titles mapped 2011-02; f3/7/9/11/13 UNARCHIVED, 2 probes each). EliteTrader CLOSED for both bot families (robots by-name). Wilmott WALLED (CF 403 on robots, probed twice 08-12).** |
| Social (X/Discord/Substack) | 2026-07-19 | 1 | 3 Substacks fetched (Maverick Quant, quantjourney [paywalled], algoadvantage) — 0 cards, mostly explainer/content-marketing grade |
| Code (GitHub/Kaggle) | 2026-07-19 | 1 | operator-named dig: ai_quant_trade, Qbot, QuantDinger, Vibe-Trading (READMEs+issues) + Hummingbot/Freqtrade issues — all infra/framework shells or equity factor zoos, 0 crypto-perp strategy logic; 0 cards but confirmed funding-arb is now commoditized into hummingbot's v2_funding_rate_arb.py (crowding evidence) |
| Academic (SSRN/arXiv) | never | 0 | untouched this session (RSRS is sell-side research, not SSRN/arXiv) — priority next run |
| Records (contests/CTA) | 2026-08-19 | 5 | **s-I (08-19, EN): Numerai methodology batch 899/3170/151 + crypto 8212/7916 to full depth → 2 graveyard falsifications (MDA leakage 0.7/0.5/0.025; grid-uniqueness), 4 inbox items, OP-087; jefferythewind run-2 NOT YET PUBLISHED (checked).** sH (08-13): Kaggle G-Research design layer EXHAUSTED (OP-068, WS-012). s1 (07-25): Bitcointalk "Automated Trading Contest" (CryptoTrader.org rounds #1-#5) → in-sample-vs-forward natural experiment entry. **s2 (08-04): the Quantopian FUND record mined via HN trees → graveyard `crowdsourced_backtest_selection_fund` (backtest-Sharpe>2.5 selection → −3% live vs SPX +6.6% → capital returned Feb-2020) — the at-scale companion to s1's entry.** **s3 (08-12): HN 9152332 MINED (full tree, 28 comments, OP-022) — the 2015 CONTEST thread closes the family's era arc: in-thread 2015 predictions (max-risk selection wins contests; survivorship arithmetic) were confirmed by the 2020 outcome, and the operator's own defense named the gate that failed → graveyard entry enriched + OPERATOR-DEFENSE MINING field note on OP-022.** **s4 (08-13): KAGGLE G-RESEARCH CRYPTO OPENED — the ground named untouched since 07-25. ACCESS-MAPPED to exhaustion → OP-068, a THIRD false-null class beside R0466's pair: REACHABLE-BUT-CONTENTLESS (no robots.txt at all; `/discussion/<id>` 200 + 5.6KB JS shell; `publicleaderboarddata.zip` returns **HTTP 200 `content-type: text/html`**, so `curl -o lb.zip` succeeds and the ground reads as harvested). The platform's archive asymmetry is the mineable half: discussion/leaderboard captures hold competition-level state ONLY (topic bodies + LB rows were XHR-loaded and **never entered Wayback at any timestamp**) while **notebook pages hold FULL kernel state** — the code layer is archived and the forum layer is not. DESIGN LAYER EXHAUSTED from the 2021 capture: 1,946 teams / 2,398 competitors, $125k, models **frozen 2022-02-01 and forward-scored on live data to 2022-05-03**, weighted-Pearson metric, and the host's own **"THE PUBLIC LEADERBOARD FOR THIS COMPETITION IS NOT MEANINGFUL"**. THE FIND is a TARGET CONSTRUCTION, not a mechanism: G-Research's target is **"15 minute residualized returns"**, while `screen_moat.py:317` screens per-symbol **RAW** forward returns at 60s–900s with no demeaning and `panel_breadth.py` records the desk's own 1.88-vs-139 effective-bets gap between raw and demeaned — two screen layers disagreeing on target construction with nothing comparing them (L1.61 shape) → **WS-012 + R0577**, DERIVES-FROM: NONE both ways. **NOT verified and the load-bearing limit: that any team achieved positive forward correlation** — prizes were awarded, which is a different claim; the private-LB rows are structurally unrecoverable and the falsifier is named. Solution layer SURVEYED only (4 ranks via a secondary index, 0 primary). Numerai post-mortems still untouched.** |
| Non-English forums | 2026-08-19 | 11 | s1 (07-19): Chinese RSRS + funding-arb (CSDN/VeighNa/BigQuant/Zhihu/FMZ) + JP note.com — RSRS EV-killed, ML-funding-rate graveyard-matched. s2 (07-26, CN frontier miner): axis #76 usdt-cny-otc-premium UN-PARKED — "no clean free API" REFUTED, 3 keyless routes, 591d history reconstructed (OP-031), Stage-A 4/4 cells → no promotable edge but SIGN and MAGNITUDE priors falsified. New: OP-031, OP-032, CN lexicon. **s3 (08-04, CN frontier miner): era-archaeology STARTED at depth — 8btc board CDX-mapped (993 urls, 39 boards), 3 era windows (2013 ban / 2017 freeze / 94 exodus) mined to reply-depth ≥2 → graveyard 5th instance adds the premium-SIGN law (coin-leg frozen → domestic discount; fiat-leg frozen → premium) + primary-source 94 diaspora record; LTW-2022 momentum "non-replication" REVERSED by code forensics (pd.cut fat-tail trap → OP-047); Gitee access-mapped (discovery-walled/content-open → OP-048); +12 lexicon rows. Board 233 (BitMEX 合约党, ~1000pp) surveyed, unmined.** **s4 (08-04, RU frontier miner s1-on-branch): forum.btcsec.com era corpus OPENED — 48 CDX pages, 1,570 topics mapped, 283 trading-tagged (data/btcsec_trading_topics.json); 3 threads reply-depth → grid-bot SECOND instance (correlated-outage failure mode) + barrier-rent SIXTH instance (Sep-2013 fee-ladder: ~12% route dispersion, Bitstamp anchor, "мы не в РФ" jurisdiction-arb); live successor forum.bits.media censused (sections 74/166/110) → 2022 diaspora ANSWERED (offshore-venue RU-language trading vs obnal-Telegram rails, double barrier) + corridor-tech-export weak signal + volume-profile POC watchlist card (novelty-clean). RU seat s1 proper lives on diverged master ledger.** **s5 (08-04, KR frontier miner s1-on-branch): the 3 routed legitimacy items RESOLVED (none seat-decidable; #67/#69 live+dated in GAP register; one gap — #69 priced at 1 axis vs 3 grounds — routed via recommendations R0020, scheduled 08-05); velog.io OPENED as ground (robots clean, GraphQL keyless) → OP-050 (Apollo-SSR route + 4 silent-failure traps), 6-post deep-read lake data/velog_kr_quant_posts.jsonl, Bithumb 2026-02-06 mis-credit DATA FENCE onto watchlist card #4, 2 weak signals (per-coin premium dispersion retail-tooled = KR twin of RU corridor-export, same day; order-flow stack commoditized + folk liquidation-long self-refuted at 45% WR), KR lexicon section STARTED (김프/GIMP collision the load-bearing entry); Ppomppu 가상화폐 board BOOTSTRAPPED as the era ground (robots-clean legal twin of hard-stopped DCInside: ~190k posts, 2014-07→live, no purge, universe row 91) — era-seek of the 2017-12/2018-01 mania+ban window is next run's first item. KR seat s1 proper lives on diverged master ledger.** **s6 (08-04, JP frontier miner s1-on-branch): Qiita 仮想通貨botter Advent Calendar OPENED+MAPPED — 187 entries / 5 years to data/jp_botter_advent_calendar.jsonl (note.com 91/qiita 45/zenn 24, robots-clean; adventar.org HARD STOP ClaudeBot-named, 3rd region hit by the Cloudflare rollout); 5 deep-reads → graveyard ×3: `jp_sfd_boundary_game` (SFD dead-at-source 2024-03 with full dated 2017→2024 lifecycle; venue-CLOCK boundary-game class extracted → SFD-class cadence-probe watchlist card), `jp_intraday_anomaly_pair` (hourly-mark reversal died 2022-04 community-documented; 24h-lag contrarian desk-screened SCREEN-WEAK powered BOTH cells at H8, sign flipped to momentum post-2024-04, 2 trials logged), `jp_atr_limit_reversion_timeframe_migration` (12H variant positive-fee lived 2022-mid→2024-03 then died — family migrates across timeframes; 2024-03 = triple JP era boundary); funding-mechanics fences → R0021 (FR is quantized/clamped/capped/lagged PI; read PI not FR; Binance premiumIndexKlines keyless catalogued, FR-vs-PI screen deferred 08-11); JP LEXICON started (13 rows, 2/4 s1 seeds verified: 養分+イナゴ; ガチホ unobserved stays SEED) + OP-051 annual-series-as-finite-corpus + OP-050 react-on-rails addendum; diaspora QUANTIFIED: on-chain topic share 4%→26% (2021→2024) but community consolidated on one venue — diaspora of TOPIC, not PLACE. JP seat s1 proper lives on diverged master ledger.** **s7 (08-12, CN frontier miner): 8btc era continuation — 2013-12 ban window mined (4 threads to depth) → NEW graveyard class `era_selfref_mark_liquidation_796` (liquidation vs venue's own unanchored last-trade; 插针 birth class; OP+moderator dual corroboration) + 7th instance of era_crossvenue_fiat_premium_arb (venue-credit share, bots-first prior, DEMAND-DIRECTION sign variable from the SAFE analysis) + 94-rail no-RMB-leg detail (thread-73825 EXHAUSTED); board 233 size CORRECTED (~31 threads not 1000pp — Discuz out-of-range page aliasing → OP-034 addendum; board-page layer SECTION-EXHAUSTED) with 2 threads to depth → card-31 COIN-M second independent mechanism prior (synthetic-dollar demand → funding skew; converges with EN 08-12 convexity prior, neither derives from the other) + WS-008 (funding-settlement phase reaches into the liquidation boundary); diaspora question CLOSED by probe (Gate WALLED edge-403, Binance Square CN THIN influencer surface, OKX no community layer — open CN layer = repos + era archives + platform 文库, confirmed); +2 lexicon (塞舌尔人/对敲); new dead-venue era grounds btcicc.com + coinsbbs.com. Unreadable named: 136734 (BitMEX大战796), 129162.** **s8 (08-13, CN frontier miner): `vnpy.alpha` MINED — the half of data_axis_watchlist card 24 that the 08-11 "verified + MINED" conversion left unread (it read vn.py's LICENCE then mined only Qlib paths; the 12-file research system was never opened). §13 MIT read from canonical LICENSE. **Card 24's remaining-diff #2 REFUTED: no rolling walk-forward harness exists in vnpy.alpha** (zero hits module-wide; static 3-way split, lab.py is persistence) — nothing there to port. Remaining-diff #1 (feature-expression DSL) now has a 285-line reference implementation: operator-overloaded proxy + `eval()` → copy the proxy, REJECT eval (generated expressions into eval = arbitrary code execution). DERIVES-FROM recorded (alpha_158 docstring says factors are Qlib's ⇒ NOT an independent convergence node, GAP-#85 echo trap). 10 divergences → operator anchor `vnpy-alpha-dsl`: negative ts_delay = future (2nd framework ⇒ family-level leak rule), a DIFFERENT label horizon than qlib's despite the docstring, min_samples inconsistent WITHIN one library (WS-005 shape at the feature layer), cs_rank raw 1..N not Alpha101-normalised (165 call sites in their own port), processor fit-window defaulting to the full panel (latent, NOT shipped — neither dataset adds processors). A drafted claim that the desk's causal guard is blind to this was CAUGHT AND KILLED pre-publication (R0289 is implemented; `_perturbable` now covers every column ⇒ the desk is AHEAD). Era half: **08-12's own "board counts are suspect" generalisation REFUTED** — board 2 REAL (128/128 captures >2KB, max real page 1009, zero-tid overlap across eras), board 61 REAL (p999 vs p1000 zero overlap), board 82 left explicitly UNTESTED → OP-070 (aliasing means you EXCEEDED the real count; it is a binary-search probe, not a reason to distrust counts; overlap ≠ aliasing, only an IDENTICAL set is — my sticky hypothesis was refuted by a 3-page test). **OP-069, the expensive one:** a Wayback `id_` 503 is TRANSIENT and PER-RECORD (107 bytes for a record CDX sized 25,431; refetch = 236,208 bytes intact), so "refetch a different URL" is an INVALID control — it produced two opposite confident wrong conclusions in ten minutes; CDX `length` is the free referee OP-034 already prescribed. 4th member of the false-null family (OP-033 encoding / OP-034 compression / OP-068 SPA shell / OP-069 transport) — all four make live ground read as exhausted; propagated to all seats. MINING half attempted: thread-49 mined 9/9 to full depth = MECHANISM NULL, recorded as a result -> OP-071 (a Dec-2013 capture of a DEEP page returns SEPT-2012 threads: Discuz sorts by last reply, so capture date is only an upper bound and page depth walks BACKWARDS from it -- my own s7 "era-seek by capture timestamp" is inverted for deep pages; ban-window discussion needs a post-event capture at LOW page numbers). No new mechanism card or graveyard entry this run.** **s9 (08-19, CN frontier miner): ban-window mining LANDED — OP-071 selector validated on first use (Dec-25 capture, page 6 = threads last-replied 12-04→12-07); graveyard TENTH instance of era_crossvenue_fiat_premium_arb (btcicc article-237 complete CNY onramp 银联→rchange HK→OKPay CY→BTC-e independently corroborates the FIRST instance "low OKPAY reserves" from the mainland side — provenance checked both ways; rail-cut-vs-announcement timing law; days-scale crowding clock: tutorial 12-06 → "spread gone" complaint 12-07, 70 unlock-replies/9d; named-scope loophole → WS-014 + card-24 schema input). coinsbbs.com thread-120 mined 8pp/70 posts → OP-088 (回复可见 gate = payload structurally unarchived; 5th false-null family member; metadata inversion + cross-post recovery + discovery-inversion search keys) + OP-069/071 field notes (0-byte id_-fetch artifact; td|div selector drift). btcicc.com surveyed: domain reused post-2019, 2013-14 article layer UNGATED and RICH for original 教程/系列 (news reposts skippable). Backlog card 23 stale-listing closed (grade-vocabulary fail-open; class → ledger). +4 era lexicon (抄币/MT/搬砖群/gate-markers). Mid-run sibling tree-reset clobbered all writes; re-applied from context, committed same-block. NEW ground named: 2014-03-28 crawl of board-2 pp2-10 = the April-2014 second rail-cut window, zero search cost.** **s10 (08-19, RU frontier miner s3-on-branch, died + continued same day): btcsec bot-class slice closed at 5 threads → era_grid_ladder_vol_bot 3rd instance grown to (a)-(h) — link-layer depth identified topic 4320 as the 8150-challenged bot's OWN author thread (ezhrd = Evgeny Pozharsky, FREE bot; slug triage structurally cannot see this pairing), and the author's blog is LIVE in 2026 (robots-clean): 86 comments 2015→2018 mined → the class's 4th kill channel, dated and author-stated (Bittrex 2018-01 cancel-fee/fill-ratio enforcement ends grid mechanics — a venue-POLICY kill no backtest prices), BTC-E→WEX seizure-week fleet migration, Bitfinex-hack off/on, EXMO no-key-granularity; WS-010 obs3 = 2nd independent vendor (cloud-EXECUTED fleet, synchronized by construction) → [3 obs across 2 vendors]; WS-009 obs2 = Cryptsy fee-endpoint lie (venue fee-API vs true fee, 2nd era venue, metadata layer). OP-089 minted (4-way failed-video-fetch triage: PRIVATE≠WALLED protects the GAP-26 purchase gate; false-null family 6th member: route obituary served as hollow 200 — 'Piped has shutdown'); @crypto_maniacdt corpus PRIVATIZING its back-catalog (2 of 3 repo-linked walkthroughs withdrawn in 7d — funnel rotation; mine video channels promptly on discovery); backtest↔live divergence read from the locked video's companion code (RSI 24 vs 96, ATR exits vs fixed 0.4%, zero funding on a perp system). +3 lexicon (сетка/тягать сетку, фикс, депо). REPAIRS: dead first leg's claimed-but-uncommitted WS routing rebuilt from a re-fetch (a same-run claim of a write is not the write); 6th R0423-class clobber (desk snapshot committed a STALE tree over fresh HEAD, deleting the RU 3rd instance AND CN-s9 10th instance) restored from pinned f0301d75 — run-end check is 'does HEAD still contain it', never 'did I commit it'. Next vein: bits.media 27623 (ezhrd's free LIVE real-money chronicle 2017-05→, primary grid-class P&L through the mania+crash).** **s11 (08-19, KR frontier miner s4): KR s3 LANDED — c32ed2be had sat unmerged 6 days (branch `claude/kr-miner-s3-20260813`; batch_premium 15h look-ahead repair rows ledgered into a void the whole time) → merge 0c691dc3 with semantic renumbering (card #33→#35, OP-072→OP-090 + id-provenance block; the collision rule: a side-branch id is not claimed — renumber at landing with every reference, same commit) + s3 rows re-minted R0631–R0634; EN ROUTE the landing's conflict resolution caught the a5c30542 desk snapshot (7th R0423-class) having ZEROED recommendation_ledger.json (0 bytes ~4h, 629 rows) and deleted GAP_REGISTER's 08-18 decision pass — both healed from pinned ac7ad0fc, verified parse + superset; R0631 = exact producer patch demand. Item 1 (R0634): rail-transition enumeration KILLED s3's knife-edge axis decisively — s3's stated input was category=trade ONLY (0 bank hits/737 structurally; → OP-091 collection-scope false null, 7th family member) so the full notice archive was fetched first-party (776 rows 2017-10→2026-08, data/upbit_notice_announcements.jsonl) → data/kr_bank_rail_transitions.json (19 classed events, announce≠treatment separated): ~0.9 sharp episodes/yr, ONE since 2021-09, EV 0.0004–0.0006 REJECT (needed ≥8/yr) → graveyard kr_bank_rail_event_study (design underpowered; registry KEPT as WS-011 provenance gate; re-open = one-bank-rule repeal transition). WS-016 born (Upbit notice archive = dated counterparty-risk verdicts on OTHER venues, ~40 rows, maps to NO mechanism-vocabulary entry; decisive lead/lag count named, n≈10). feed.bithumb.com WALLED (IP-level 403 incl. robots, browser-UA control same). Collector category gap → improvement_inbox (one-line fix owed by owning organ). Cocoa chain 4TH deferral NAMED — s5's unconditional first item. Video: 0 fetched, 0 locked.** |
| Forums (deep+legacy) | 2026-07-28 | 2 | s1 (07-25): Bitcointalk ERA-ARCHAEOLOGY opened — boards 8+78 mapped via OP-021; 6 topics mined to reply-depth → 3 graveyard entries + EN era lexicon. **s2 (07-28, session D): QUANTOPIAN ARCHIVE opened + mapped — 52,187 threads confirmed in Wayback (the whole forum); In&Out thread (108 posts) + its live-trade continuation (13) mined to EXHAUSTION → graveyard `era_inout_regime_rotation` (the community's own decomposition kills the crypto port), inbox #71, WS-003 4th confirmation, OP-034 + Quantopian-stratum lexicon, and the full named diaspora record (QC canonical / Quantiacs futures / self-host branch).** **s3 (2026-08-01, session E): OLMAR/OLPS cluster (20 captures, not the 9 logged) — 3 threads exhausted incl. the paper AUTHOR's in-thread admission; family killed on our own data AND the era's own kill reason refuted (crypto has 3.3–3.8× the dispersion of the sector ETFs OLMAR failed on). WILMOTT FIRST TOUCH DONE after a 4-session carry: 403 direct, 14,890 threads via Wayback, full board map recovered, verdict THIN-BUT-REAL (~5,868 mineable of 14,890; 68% Off-Topic/Politics noise).** EliteTrader/Nuclear Phynance still never touched |
| Social (X/Discord/Substack) | 2026-07-19 | 1 | 3 Substacks fetched (Maverick Quant, quantjourney [paywalled], algoadvantage) — 0 cards, mostly explainer/content-marketing grade |
| Code (GitHub/Kaggle) | 2026-07-19 | 1 | operator-named dig: ai_quant_trade, Qbot, QuantDinger, Vibe-Trading (READMEs+issues) + Hummingbot/Freqtrade issues — all infra/framework shells or equity factor zoos, 0 crypto-perp strategy logic; 0 cards but confirmed funding-arb is now commoditized into hummingbot's v2_funding_rate_arb.py (crowding evidence) |
| Academic (SSRN/arXiv) | never | 0 | untouched this session (RSRS is sell-side research, not SSRN/arXiv) — priority next run. **2026-08-01: touched only OBLIQUELY — the OLMAR paper (Li & Hoi ICML-2012 #168) was read THROUGH its forum thread, where its author answers questions the paper never addresses. Standing note: for any algorithm with a live practitioner community, the FORUM is a higher-yield read than the paper.** |
| Records (contests/CTA) | 2026-07-25 | 1 | partial, via forum route: Bitcointalk "Automated Trading Contest" (topic 261086, CryptoTrader.org rounds #1-#5) mined as a contest RECORD — produced the in-sample-vs-forward natural experiment graveyard entry. Kaggle G-Research + Numerai post-mortems still untouched |
| Non-English forums | 2026-07-26 | 2 | s1 (07-19): Chinese RSRS + funding-arb (CSDN/VeighNa/BigQuant/Zhihu/FMZ) + JP note.com — RSRS EV-killed, ML-funding-rate graveyard-matched. **s2 (07-26, CN frontier miner): axis #76 usdt-cny-otc-premium UN-PARKED — "no clean free API" REFUTED, 3 keyless routes, 591d history reconstructed (OP-031 CDX-replay of a capped JSON API), Stage-A screened 4/4 cells → no promotable edge but the catalogued mechanism's SIGN and MAGNITUDE priors both falsified. New: OP-031, OP-032, CN lexicon.** Era-archaeology (banzhuan/8btc/ChainNode/Tieba) still UNSTARTED — first item next run. **s3 (2026-08-01): T1 instrument repair — the 7 supplied unverified slang terms negative-controlled, 0/7 survived, 6 with the real form named; +14 verified lexicon rows; OP-036 (evasion slang has a BIRTH DATE — 大饼 born of the 2017-09-04 "94" ban, so the search key is a function of the ERA, and our era ground straddles it), OP-037 (negative-control a supplied glossary), OP-038 (a JS wall on the HTML is not a wall on the API — unblocked the Gitee chain carried 3 sessions). CN OSS tranche: AlphaGPT paper + NOFX "3 mechanisms" both REFUTED, Vibe-Trading crypto layer weaker than ours (honest null). Screened `unlock_events.json` (24,201 events, 0 readers) 0/27 cells → UNMEASURABLE not dead, 2 measurement defects. VERIFIED on live API: a 123-event Binance delisting forced-close panel discarded by a `status=="TRADING"` filter (R0292). R0288–R0293. Era: 8btc thread-44638 mined to reply-depth, CN-side corroboration of the cross-venue-premium kill. DIASPORA ANSWERED: CN discussion migrated into paid/ID-gated enclosures — §13 puts it permanently out of reach, so the open CN layer worth mining is repos + era archives + platform 文库, NOT live community.** |
| Non-English forums — **JP** | 2026-08-19 | 5 | **s5 (2026-08-19, JP frontier miner): DEEP-FOREST QUEUE MINED (5 posts, 4 hosts, repo chain 1 hop) + VERIFICATION LANE CLOSED — both JP dues landing today were already closed by siblings (J-Quants killed 08-12; bitbank wired by EN s-I), and the residual was ours: bitbank re-listed as pending every cycle via the R0514/R0617 `_classify` fail-open → KR-s4-precedent grade-token close on our own card (commit d615cfba; parser stays engineering-owned; backlog now 7 pending, bitbank absent). BEST PAGE: `rarirure.rip` news-latency listing bot — SUPPLY-side corroboration of the desk's pre-registered SHORT-the-pop listing hypothesis (Binance perp-listing insiders crash the pop: BWEnews complaint + 「インサイダーには勝てない」), キムチパンプ named as the fill driver (KR retail), announcement-endpoint-vs-aggregator clock gap measured (>1min vs BWEnews once), Bybit title-format variants break naive symbol regexes → both to improvement_inbox; latency race DOA for this desk, drift horizons uncontested. `arkham_alert_edge` → graveyard (practitioner-dated alert-vendor edge death; his fix was moving UPSTREAM of the vendor). PERP-DEX TGE DIP TEMPLATE (shidokamo, HYPE→ASTER two instances, three EX-ANTE conditions: single-venue concentration + zero-cost-basis holders + official AF support bid): EV-gated to KNIFE-EDGE REJECT 0.0016 with re-open measurements named (≥6 qualifying TGE windows/yr, or alpha-vs-hold on HYPE's own tape after a §13 read of HL API terms) — memory not card; novelty 0.761. OP-072 gains two sharpenings: RLHF-consensus tilt (優等生 effect — contamination is BIASED toward textbook consensus, so consensus-shaped convergence is the weakest post-2023 evidence) + INTERFACE-contamination layer (LINE→GPT→config-DB, decisions human). WS-017 (perp-DEX points-season flow is contractually non-profit-seeking — a dated regime label) + WS-018 (airdrop instant-sell prior FLIPPED 2024). +7 lexicon (キムチパンプ/脳筋/鉄火場/野良SDK/無限買い/AF/…). PROCESS: 鉄火場 8-hour ship rule; folk order-randomization standard; lever-then-DE-lever as mania ages; grep-then-fork 野良SDK; infra diaspora cloud→LOCAL. JP half of the "Foreign AI-quant SYSTEMS" card answered for tooling: JP layer is bot-infra (ro-soku MIT + weekly cron-CI spec-drift detection = inbox item; tvbit-bot AGPL; starter-trader no-licence forks>stars), NOT a Qlib-class research system. NEW: yameteeeee.com (CBbot origin, unprobed); ERA TARGET: ヨーロピアン's DELETED 2017 Medium corpus (community begs for copies — lost ground, Wayback route). zenn.dev 200-robots-over-403-content PERSISTS; note.com 403/403. Video: 0 fetched, 0 locked.** — **s4 (2026-08-13, JP frontier miner): THE DEEP-FOREST SELF-HOSTED TAIL OPENED — after 08-12 closed 62% of the mapped corpus, a UA-matrix probe over 10 hosts found **8/9 self-hosted botter blogs serve 200 to ClaudeBot and 4 have no robots.txt at all** → **OP-073** (an AI-crawler denylist is a PLATFORM product decision; re-scope the HOST COLUMN, never the region — the JP ground went from "thinning" to a fresh 20-entry queue across 12 open domains with one group-by). **zenn.dev sharpened the §13 finding into its worst form: robots.txt now returns 200 AND explicitly allows `*`, while the content path returns 403 — every standard §13 check comes back green and permissive over a closed ground.** **OP-072, the run's best find and fleet-wide: the post-2023 practitioner corpus is LLM-CONTAMINATED** — the mined options post's entire mechanism analysis is self-disclosed ChatGPT output (チャッピー), so practitioners in unrelated regions now converge because they queried the same weights, not because the world taught them; worse than the arXiv echo GAP #85 models (a paper echo leaves a citation, an LLM echo leaves nothing), fixed by per-region markers + an observation/explanation split + `NONE (checked)` made illegal post-2023 (→ UNVERIFIABLE), and it hands era-archaeology a new argument: **pre-2023 archives are structurally uncontaminated.** MINING: `blog_UKI`'s BitMEX spoofing **intervention** (not an observation) decomposes OFI → **the market-order take components dominate; the displayed book is not where the information is**, so `book imbalance` and `aggressor flow` may be ONE axis and the desk's L1.18 independence count too high by one (EV 0.0002 REJECT as a trade → routed to improvement_inbox as a feature-redundancy fact; the strategy is prohibited conduct and is not proposed). `pip_pip_pip_p` **corroborates the 08-01 richmanbtc kill from the opposite fee sign** (the rule-based core is down-sloping on Binance in every period since 2021, incl. the 2024-11/12 bull) + names a live desk gap: **the desk checks FEATURE-distribution stationarity, apparently never the TARGET's**. `gitan.dev`'s 2023↔2024 venue-survey **pair** (a free longitudinal diff) → **WS-013**: a 13-month +2% JP margin dislocation, a venue REPLACING an SFD divergence penalty with a funding rate, and its resting long-pays-short constant **numerically identical to Binance's 0.01%/8h interest component** — an independent venue corroborating this seat's 08-12 clamp census that the 1bp print is a copied CONVENTION. Graveyard ×1 (`rev_calendar_spread_iv_convergence`, refuted at source: vega-neg + theta-neg has no favourable regime; its transferable half is **a hedged leg with a contractual expiry un-hedges itself on a schedule** — a risk-rail event for any future dated-future-vs-perp basis trade). Universe source **102** (venue fee schedule as the conditioning variable for every volume feature; EV 0.0058 QUEUE, the session's only gate survivor of 4 scored). +8 OBSERVED JP lexicon rows (鞘/アビトラ/見せ板/お蔵入り/反面教師/チャッピー/限月/爆損). **Self-caught defect: my own 08-12 next-run queue was 40% dead on arrival** — titled "qiita-hosted", it named 3 zenn.dev entries I had ruled HARD STOP in the same note. Video: 0 fetched, 0 locked.** —  **s3 (2026-08-12, JP frontier miner): §13 REGRESSION — note.com + zenn.dev now serve 403 to ClaudeBot/GPTBot/CCBot/Bytespider AT THE CDN EDGE while BOTH robots.txt files are clean of any such rule (Googlebot/curl/SomeRandomBot get 200 ⇒ a curated AI-crawler denylist, not a WAF heuristic). HARD STOP, archives included; NOT routed around (Claude-User returns 200 and was deliberately not used). Closes 116/187 (62%) of the mapped botter corpus incl. all 3 planned targets; rollout DATED between 08-04 and 08-12 by this seat's own successful prior reads → **OP-052** (probe the CONTENT PATH with a UA matrix; robots.txt is necessary, not sufficient) + lesson **L0096** + **R0466** (a blocked ground and an exhausted ground are byte-identical to any fetch path that treats non-200 as no-content — a FALSE NULL that silently retires a region). **Past-due PI-vs-FR deferral RESOLVED** (`data/jp_funding_clamp_census.json`): clamp verified by positive control (BTC 49/60, DOGE 46/60); **41.6% of the owned 8h panel and 68.8% of the live 812-symbol cross-section sit on a censoring constant**, 74.9 bps of real premium dispersion hides inside one 56-name tie group — the root cause of the already-paid-for "42 perps at the 1bp floor" churn incident; censoring DECAYS 68.8%(2019)→10.7%(2026) ⇒ **backtest-integrity upgrade first, live-signal second**; EV 0.0193 QUEUE, novelty 0.726, NOT promoted (screen still owed). **L1.47 corroborated with a count → R0465: 426/812 (52.4%) of live perps settle on 4h, only 385 on the 8h that `held/8.0` assumes** ("many" is the majority); ranking damage honestly modest (Spearman 0.959). JP funding-settlement sandwich (qiita/lud-botter, DERIVES-FROM: NONE checked ⇒ genuine independent convergence with L1.47) **EV 0.0006 REJECT** as published — dead at source, venue changed settlement rules mid-operation — with the observation routed as execution-timing **EV 0.0087 QUEUE**; JP **Travel Rule 2023-06-01** era marker (domestic↔overseas arb killed by regulation, not competition). **マケデコ (`market-api`) NEW GROUND opened + mapped: 74 entries 2023–2025 (2021/22 = 404, series began 2023), JP EQUITIES not crypto, 74% on the closed hosts**; J-Quants axis catalogued-unverified (row 29). Video: 0 fetched, 0 locked.** — **s1 (2026-08-01, JP frontier miner, seat's first run).** §13: **5ch.net + all sister hosts REFUSE `ClaudeBot` by name** (Cloudflare-*managed* block → treat as a platform rollout, not a site decision; re-check on entry, never cache); note/qiita/zenn/GMO/bitbank clean. **bitFlyer axis CLOSED after 4 deferrals** — the "403/WAF/needs-a-human" record was a **tarpit**, the block is **per-hostname** (api+lightning serve 200 from the *same edge IP*), the "never archived" claim was a wrong CDX host+slug, and the ToS was then read: it retains rights in *"data such as transaction prices"* → **`restricted-by-licence`**, which pre-emptively killed `getchats`, `getfundingratehistory` and an archived keyless 15-min BTC/JPY series (2014-10→, Wayback-only) before any were carded. **Replacements found same run: GMO Coin free keyless tick tape (2018-09-05→, 28 spot + 12 margin, JP-only MONA/XYM/FCR/NAC/WILD) and bitbank — both licence-unread, no ingest (R0309/R0310).** **richmanbtc lineage (the C62 "gem", unstarted 12 days) KILLED**: the edge is a bare ATR×0.5 limit, the ML adds ~nothing, and the maker fee was **zero-or-negative across the whole backtest** → a venue-subsidy harvest, dead on 3 venues. Salvaged 3 CC0 tools (p-mean order-sensitive decay bar — **published error-rate formula reproduced BROKEN**; time-adversarial feature screen; `publicGetExpiredFutures` for R0239). New: **OP-043/044/045** + OP-041 refinement. Era-archaeology (2017 bitFlyer-FX **SFD**, Mt.Gox 5ch) **UNSTARTED**; JP lexicon seeds still **unverified**. Next: **the 仮想通貨botter Qiita Advent Calendar 2021–2025, never touched.** |
| Non-English forums — **BR** | 2026-08-13 | 3 | **s3 (2026-08-13) — THE MINED SYSTEM WAS REFUTED BY MEASUREMENT, AND THE FAMILY SURVIVED THE OBJECTION THAT SHOULD HAVE KILLED IT.** `Vido/zecontinha` (Apache-2.0, live at `zecontinha.com.br`, broadcasting to Telegram) takes its cointegration p-value from `adfuller(sm.OLS(y,x).fit().resid)` — the textbook Engle–Granger error — so I ran their exact window as a null instead of asserting it: **4,000 trials, two independent random walks, n=120 → 17.97% [16.8,19.2] rejections against its own nominal 5%; `statsmodels.coint()` gives 7.60%. 3.59× nominal.** Full published gate (ADF `p<.05` ∧ `|z|≥2`) fires on 0.88% of pure noise ⇒ **≈44 spurious pairs/run** over 4,950 pairs × **10 unrcorrected lookback windows (49,500 tests/run)**, from which the bot publishes the **3 lowest-Hurst** — noise filtered, then ranked by noise (**OP-077**, graveyard). **THE COMMENT LAYER PAID BEST:** nothing on the surface says what the maintainer says in PR #30 — *"`select_pair(n)` was just a silly function to **draw a pair**… **Telegram folks see it as recommendations. Which they are NOT!**"* — the selection step was `order_by('?')`, **random ordering**; and because the switch to a screened rule is **dated** (PR #30, 2025-11-06), the channel's public history is **a random-selection control arm followed by a screened one, timestamped** (**OP-080**). **THE FAMILY IS NOT KILLED, and that is the run's most consequential line:** the desk's breadth lesson hard-kills *directional* cross-sectional mechanisms at **1.54 independent bets**, but a cointegration pair is long *y* / short *βx* — **beta-neutral by construction**, so it lands on the **29** side. STATISTICAL-ARBITRAGE (THIN, n=1 of 14) is thin for **instrument** reasons, not verdict reasons → improvement_inbox, **no kill claimed**. **FORK TREE EXHAUSTED — HONEST NULL:** `forks_count:6`, `/forks` returns **8**, **zero ahead** by one commit; the 2 extras are **tombstone 404s** that any walker treating non-200 as "skip" silently drops (L1.60 attrition on a *mining* instrument), and `?path=` is **rename-blind** — 3 commits reported vs **11 true** (**OP-078**). **A FREE POINT-IN-TIME UNIVERSE (source 103):** git history of a hardcoded ticker list = dated universe vintages, answering the desk's own *"`exchangeInfo` is a look-ahead in the UNIVERSE"*; honest number **8.7% true USDT survivorship erasure, not the headline 25.8%** (40 of 55 absentees are the **BUSD wind-down**, a quote-currency retirement), and **3 of the 15 are rebrands with a continuing series** (MATIC→POL, RNDR→RENDER, TOMO→VIC) — **a rename and a delisting are opposite events that look identical in a symbol diff**. **s2's "RICH SEAM" prediction CORRECTED:** `TCC` is a **precision key, not a recall key** — `TCC bitcoin` 29 / `TCC trading` 18 but `TCC cointegração` **1** vs **30** for `cointegração` alone, so genre ∩ topic ≈ ∅ (**OP-081**, union never AND); `dissertação trading` = a measured **0**, and student repos are disproportionately **vendored framework forks** so counts overstate. One TCC repo mined to its result layer: headline **87.1% win rate / +8.78%** vs a **separate** left-open file holding **13 losers to 1 winner** ⇒ **true +5.87%, a 49.6% overstatement** (**OP-082**; mechanism `sell_profit_only` labelled a hypothesis because config and strategy contradict each other — the 4th OP-055 instance in this corpus). **VIDEO: 4 probed, 1 fetched, 3 locked — and the fetch REFUTES AR s2's same-day boundary:** a **13,297-view** PT-BR practitioner video passes while AR at 538k/234k/47k and EN at 142k/50k/33k fail, so *"mega-viral only"* is wrong; **3/3 persistent retries** kill the "temporarily blocked" reading too — it is a **stable per-video** property, **UNMEASURED** as to cause, and GAP #26 should measure the blocked **fraction**, not assert a **class**. R0592 still live: all 6 wrapper calls printed a **dead-domain DNS error** for a YouTube bot-wall. +5 BR lexicon rows (**prazo** = lookback window, **beta rotation** used untranslated inside PT, **enquadrado**, dissertação-negative). Venue found by reading repo code: **`@pythonfinancas`** Telegram. Next: the **`berlinguyinca` 30-strategy collection with vendored OHLCV beside it** (EXECUTABLE tier), the crypto-native Johansen/VECM subset, B3 (**unprobed after 3 sessions**), era-archaeology (**still not started**). || **s2 (2026-08-12) — THE NATIVE KEY WAS HIDING THE DESK'S ONLY NEVER-HUNTED FAMILY.** Cleared s1's 8-day-overdue ITEM 3. Measured, same corpus same minute: `pairs trading brasil` → **0 repos**, `cointegração` (native PT key) → **30**, essentially all genuine statarb, several crypto-native — so a seat querying the English term grades BR statistical arbitrage DEAD on a clean zero, and `strategy_coverage.json` reports **STATISTICAL-ARBITRAGE as the only never-hunted family (0/14)**. `long short` is unusable bare in PT-BR via **two independent collisions** (LSTM written out in full; C's `unsigned long/short`) — the vocabulary sibling of the RU ticker collision. **OP-054.** Depth on `mateusmartinelli/tcc` (crypto pairs trading; Gatev + Caldeira–Moura + Rad–Low–Faff): more rigorous than average (loads T-bills, computes excess returns) yet **three code/comment contradictions all in the config block** — cost 0.001 commented "0.05%" (**2×**, conservative), entry **1.5σ** commented "2σ as per paper" (**not** conservative), formation **90d** commented "252" — plus **zero funding accounting** and top-10 pairs from ~4,950 candidates at p<0.10 with **no multiplicity correction** (~495 expected false pairs). **OP-055.** Killed `pedhsm/systematic-research-framework`'s MCPT: it permutes **realised returns** and scores sharpe/cagr/vol, **all order-invariant** — verified by independent reimplementation, 500 perms × 4 series, **max−min = 1.1e-15**; FP non-associativity then makes the p-value a rounding-order hash (**winner p=0.978, catastrophe p=0.618**). A **wall, not a bar** → graveyard + **OP-056**. **The desk was already ahead** (`bar_permutation.py` permutes bars, with a measured `_TIE_RTOL` + add-one) ⇒ genuine cross-ecosystem convergence, **NO BUILD**. RFB: s1's *"decaying deadline"* was an inferred rate — census gives **23 dates, 12 live / 12 dead, clean boundary at 2023-03-02|2023-05-03, 4 with no capture at all**; **rate UNMEASURED** (two rival hypotheses, opposite urgency, falsifier recorded) and the series is **~4 months unpublished against a 13-month hiatus precedent**. BR lexicon opened (none existed); supplied seeds scored **0/3 as dark-forest keys**. Video: **0 fetched, 0 locked — not attempted**, named in next ground. Next: `Vido/zecontinha` fork tree + crypto subset, `TCC` as a structural key, PT-BR video, B3 (still unprobed), era-archaeology (still not started). |
| _(BR s1 history)_ | 2026-08-01 | 1 | **s1 (2026-08-01, BR frontier miner, seat's first run).** **§13: the KR/JP by-name-block pattern does NOT generalise** — 18 hosts swept full-file over 17 AI-crawler tokens, **zero BR blocks**; the community layer (bastter, InfoMoney, MQL5-PT, Investing BR, bitcointalk, YouTube, Telegram) is **open**, so KR/JP was a property of *those* consumer portals, not a global rollout (OP-041 corrected). One **HARD STOP: `reddit.com` `Disallow: /`** to everyone — a *global* decision that bites BR hard (r/investimentos, r/farialimabets, r/BrasilBitcoin). **Pre-emptive graveyard check killed one third of my own brief before any searching:** the seat's era target "BR P2P premium" is already `mercado_br` **REJECTED** (graveyard:81) inside a family killed **5×** whose lone survivor (kimchi) was itself refuted 07-30 — no L1.16a enabling change exists, so the **seed list** is the defect. **THE FIND: RFB `criptoativos_dados_abertos`** — Brazil's **mandatory** national crypto-reporting panel (every domestic exchange reports **every** operation, no minimum; P2P + foreign venues >R$30k), free and keyless: **77 months Ago-2019→Dez-2025, 66 assets, 4,206 asset-months**; Dez-2025 = **3,544,986 taxpayers / R$43.1bn**; all-time **USDT R$1.004tn vs BTC R$269bn (3.7×)** ⇒ a **dollarization**, not speculation, mechanism. **Deliberately NOT screened** — n=77 monthly + 3.5mo lag vs a ~4,268-obs bar would manufacture a false null (L1.25); reported **UNDERPOWERED** with the cross-sectional enabling change named. **The depth layer was the prize: a FREE POINT-IN-TIME VINTAGE STACK** — RFB republishes monthly under a dated filename and **42/42 common months are revised** (worst Março-2023 **+40.9%**; a month **2.4y old** still moved), systematically upward, so backtesting today's file is a **+41% look-ahead in the CONDITIONING variable** (R0289 class — passes every return-series leak check, fails toward a FALSE POSITIVE). Proven recoverable: 23+ dates in CDX, and a **live-404 vintage restored intact** via `web.archive.org/<ts>id_/`. Read at all only by writing a **stdlib OLE2+BIFF8 reader** (no xlrd on this box) validated by the data's **own conservation law: 78/78 rows, residual 0.00e+00**. New **OP-046 / OP-047 / OP-035-BR**; R0316–R0318. Incidental: a **BR-only tokenized-RWA universe** in a government dataset (**MBPRK = tokenized *precatórios***, MBCONS, IMOB01, MCO2; **BRZ = 92.4M ops**, a payment rail). **ITEM 3 (PT-BR practitioner ground) explicitly DEFERRED to 08-04, not dropped.** Next: practitioner ground first, then **mirror the vintage stack before it decays**, B3, Pix fraud stats. |
| Non-English forums — **AR** | 2026-08-13 | 2 | **s2 (2026-08-13) — THE SEAT IS RE-AIMED, on measurement.** (1) **`mql5.com/ar` DOES NOT EXIST** — MQL5 publishes 11 hreflang locales and `ar` is not one; `/{loc}/code` = 200 for 11/11 real locales, 404 for `ar` alone. s1 graded it OPEN **from robots.txt**, which answers *may I*, never *is there anything here* → **OP-074**. (2) **THE AR LANGUAGE IS NOT A MOAT** — AR-script repo search: arbitrage **1/0/0**, quant-trading **0**, EA **0**, all hits 0–1★ Telegram signal-bots, against **CN 1,174 / RU 24 / KR 6** on the same instrument. Discriminator by developer LOCATION: **UAE 67 > Korea control 59** (~99 AR-region devs) ⇒ population EXISTS and **writes in English**, so its output is already in the EN seat's ground → **OP-075**. **Not "the ground is thin"** — a precise verdict on ONE layer (AR-script *code*); the seat's edge must be what is native-language **by institutional construction** (regulators, exchanges, courts, the Sharia layer). (3) **VIDEO: 8 attempted, 1 fetched, 7 LOCKED — `video_locked_log.md` has its FIRST ROWS EVER**, and the **EN control** (142k/50k/33k views, walled identically to AR 538k/47k/31k) proves the block is **not regional**: GAP #26 must buy a **general** authenticated route. The log was empty because `fetch_video_transcript.py` reports only the LAST instance's error and that instance is a **dead domain** — a platform bot-wall displayed as a local DNS fault (R0592). **AR corpus is VIDEO-FIRST**, which is the natural complement to OP-075. See s2 session note. || **s1 (2026-08-12, seat's first run) — CLOSED.** No AR row existed before this run (`grep -ic arabic` = 0). **Pre-emptive graveyard check killed the seat brief's ENTIRE era target before any searching:** MENA/Egypt/Lebanon P2P-premium-under-FX-restriction is `era_crossvenue_fiat_premium_arb` (buried **7×**) inside the regional-premium class the desk declared **exhausted** (`try_premium_timing` — the Turkey capital-control analog, the closest MENA case that exists — REJECTED; kimchi, the lone survivor, itself KILLED 08-01); `strategy_coverage.json` has CROSS-VENUE-PREMIUM = HUNTED/9. Second consecutive seat (after BR) handed a dead era target ⇒ **the seed list is the defect**. Items: (1) §13 UA-matrix access map (OP-052) — AR unmapped in BOTH directions, and R0466 makes an unmapped ground's null uninterpretable; (2) report+replace the dead brief; (3) **replacement axis: Hijri/Ramadan calendar + Sharia-compliance forced-flow** — novelty-clean at **0 hits** across graveyard/both watchlists/universe map/vault, maps to NONE of the 24 CRYPTO_MECHANISMS, and lunar-vs-Gregorian drift (~11d/yr) makes it orthogonal to every Gregorian calendar effect by construction. See session note below. |
| AI/HF documentation | 2026-07-19 | 1 | touched only incidentally via Vibe-Trading (AI trading-agent platform) + ai_quant_trade (LLM module) — both infra, not alpha-discovery-process documentation; weak coverage, revisit properly next run |

## COVERAGE REALITY vs DIRECTIVE (honesty record, 2026-07-20)
Charter s25 "no source class skipped" and the specs' "dig to exhaustion" are STANDING
DIRECTIVES (how every dig must be run) -- they are NOT claims that the universe has been
covered. Actual state on 2026-07-20:
* Prospector: 1 session ever (2026-07-19), 0 cards. 4 of 9 families still NEVER visited
  (YouTube/talks, deep+legacy forums, academic SSRN/arXiv, contest/CTA records).
* 7 regional frontier miners: ACTIVATED 2026-07-20, ZERO runs so far (first crons fire
  00:15Z 07-21). Non-English coverage to date = ONE session touching surface-layer CN
  (CSDN/VeighNa/BigQuant/Zhihu/FMZ) + one JP note.com blog. The richmanbtc/note.com botter
  lineage (addendum C62, the named gem) is NOT yet dug.
* VIDEO: **~~direct transcript fetch is IP-BLOCKED from this VPS~~ SUPERSEDED 2026-07-26,
  MARKED HERE 2026-08-07.** The 07-18 finding was about ONE ROUTE (youtube.com/api/timedtext),
  never about the capability, and `scripts/fetch_video_transcript.py` has fetched real
  transcripts via public Piped instances since 07-26. Video is FIRST-CLASS dig material.
  The original text is struck rather than deleted because this file records what the desk
  BELIEVED and when -- but the strike is the point: this bullet sat 91 lines above its own
  refutation for twelve days, and every digger prompt inherited the stale half. A reader
  going top-to-bottom acted on the wrong line, which is exactly how the video-locked log
  reached 2026-08-07 with zero rows. GAP #26 (paid unlock) remains principal-spend-gated and
  is now LESS likely to be needed, not more.
* "DARK FOREST": the genuinely closed layer (private WeChat/QQ groups, paid Knowledge-Planet
  circles, invite-only Discords/Telegrams) is PERMANENTLY OUT OF SCOPE under charter s13 --
  closed-group and paid-content material is never scraped or adopted. What is in scope is the
  PUBLIC Chinese/regional layer, and that layer is barely scratched (one session).
Any future statement that a region or source class is "exhausted" must cite session counts
from this table. Directive != achievement.

## SESSION NOTES — EN frontier miner

### 2026-07-25 session A (RECONSTRUCTED post-hoc — the run died before writing this note; deliverables verified present in the repo by session B)
GROUNDS: Bitcointalk era-archaeology (dark-forest mandate #1) + HN items API + backlog burn-down.
DELIVERABLES (all confirmed on disk): 4 backlog re-verifications with primary artifacts
(Upbit portal: 4 of 5 old claims REFUTED, real API extracted from webpack chunk, 1m candles reach
2017-10-24 not 2023-07 — a 5.7yr understatement from one mistranslated Korean character (초봉=1s
bars, not 분봉); bitFlyer: 31-day wall confirmed 3 ways incl. exact binary-searched boundary id
2646808096; Tardis: backfill-destroyed claim REFUTED, full-depth L2 free every 1st-of-month
2019-04→2026-07 ≈ 88 ground-truth days; Kaiko: index methodology public (BMR rulebook PDF, VWM+TWAP),
$1-2.5k/mo pricing claim struck as unsourced). 3 graveyard entries (era_ta_indicator_stack_crypto —
the round #2/#3-forward-vs-round-#5-in-sample natural experiment; era_grid_ladder_vol_bot — GMVT-BOT
short-gamma economics; era_crossvenue_fiat_premium_arb — 3 instances, premium=barrier-rent).
4 inbox items (#54 grade-provenance rail, #55 fill-rate decay discriminator from HN 9642325 depth-2
reply, #56 premium-as-barrier-rent prior, #57 side/depth phantom-arb rail from topic 14466 reply #19).
3 operators (OP-020 SMF printpage, OP-021 board-tail era-seek, OP-022 HN items tree-walk) + the
corpus-derived EN era lexicon (5,702-topic frequency differencing — finding: era vocabulary is
VENUES+RAILS, not strategies).
DEPTH LINE: topic 261086 read to post #285 of 301 (printpage, full thread); 171349 replies #37/#39
mined (fee-stack + OKPAY-reserve refutations); 339040 replies #7/#13 (capital-control mechanics);
14466 reply #19 (side/depth debunk); HN 9638748 walked to depth≥2 (53 of 65 comments), 9642325
depth-2. Era-seek calibrated by 8-offset binary probe. NOT breadth-theater: every carded find came
from a reply layer, none from an OP.
UNFINISHED AT DEATH (completed by session B): this coverage note; universe-map sync of the 4
re-grades; Glassnode/CryptoQuant handoff (inbox #54 names it next).
DIASPORA (standing question): where did Bitcointalk's 2011-14 strategy posters go? Partial answer
in-thread: CryptoTrader.org (the contest platform) → closed 2018; visible migration to
private/paid Telegram signal groups (OUT OF SCOPE s13) and QuantConnect/Quantopian — the public
successor ground IS the Quantopian archive (already on the region list, still undug).

### 2026-07-25 session B (this run — backlog burn-down per RESUME mandate; verification WAS the session)
COMPLETED SESSION A's UNFINISHED ITEMS: this coverage note pair; universe-map sync of the 4
session-A re-grades (Upbit/bitFlyer/Tardis/Kaiko); the inbox-#54 Glassnode/CryptoQuant handoff.
BACKLOG: 7 pending-verification + 2 legitimacy at open → **2 pending (both externally blocked) +
3 legitimacy at close; 8 of 13 resolved.** Verdicts, each from primary artifacts actually opened:
- §7 Glassnode/CryptoQuant: claimed Dune path key-gated (401/403 keyless — demoted secondary);
  BETTER primary found+verified: **Coin Metrics community** (btc.csv 2.48MB/6,352 rows 2009→
  2026-05; flows since 2011-04; LIVE keyless community API current T+1; GitHub mirror STALE
  since 2026-05-24). CC BY-NC → legitimacy queue. CM netflow = 15yr backfill + independent diff
  target for desk onchain_flows.
- §4 Bithumb: **"paid-mirror-only" gap REFUTED** — v1 Upbit-schema keyless API paginates daily
  to 2014-01-13 (epoch≈launch) and **1m to at least 2014-05-31** — 4.7yr deeper than the paid
  mirror, 3.5yr deeper than Upbit's portal; deepest free KRW minute archive known to the desk.
  Two-API same-venue diff exact on overlap. Futures docs lead DEAD (404). Licence/ToS still open.
- §9 stablecoin mint/burn: **mechanism verified integer-exact** (24h USDC: 2,404 mints 375.8M −
  1,656 burns 564.6M = totalSupply Δ −188.76M after boundary-block fix; convention (then,now]
  documented). Treasury-first failure mode confirmed live (Circle wallet took 300.7M of mints).
- §11 eth-labels: **downgraded to supplementary-only** — all 3 canonical Binance wallets absent,
  label/nameTag contradictions at scale (bilaxy label on "Binance Dep" tags); cross-diffed vs
  cex-list (276/373 overlap). §12 cex-list verified as era-correct 2023 snapshot (last commit
  2023-07-27), the cleaner-but-tiny counterpart.
- §21 NAVER: endpoint live-confirmed (error body 024 keyless); sole blocker = free key (human).
- §3 bitFlyer licence: Wayback route exhausted (0 snapshots) — 2 failed routes logged; needs
  non-blocked egress. TIME-SENSITIVE: 31-day window keeps destroying history daily.
SCREEN-ON-DISCOVERY (s26, same-run): new axis CapMVRVCur (CM) Stage-A screened → TIMING-ARTIFACT
(same-period corr 0.416 — price-numerator ratio at 20d-z is momentum in disguise); graveyarded
with pre-registered weekly/orthogonalized escalation. 1 construction, 1 verdict, logged.
ECOLOGY SHIFTS (s21, logged in inbox #58): registry eth_public_rpc chain 3/4 dead for getLogs
(ankr key-walled, publicnode token-gating); working keyless set = MEV-relay RPCs (flashbots/
mevblocker ≥700-blk); CryptoCompare min-api key-walled (killed the independent Bithumb diff);
CM GitHub mirror stale. Free-tier ENCLOSURE is a trend; same-day replacements found each time.
CONTRIBUTED: OP-023 (per-method RPC capability matrix), OP-024 (conservation-law reconciliation);
inbox #58. Registry defects flagged-not-edited (freeze): eth_public_rpc chain, Tardis $599 tier.
DEPTH LINE: verification session — depth = artifacts opened/downloaded per card (CSV downloads,
live API probes incl. 18-chunk getLogs reconciliation, boundary-block root-cause, cross-diffs);
zero new forum grounds opened (deliberate: RESUME mandate makes verification the priority, and
session A banked today's era-archaeology dig. NOT breadth-theater — nothing was surface-scanned.)
COUNTERFACTUALS (s17): Bithumb 2014-depth find LOW-MED (public API but the depth documented
nowhere; found only by boundary-probing — the paid mirror was universally believed deeper).
CM-covers-the-flow-class MED (CM community is known, but no desk card connected it to the
Glassnode/CryptoQuant replacement question or knew it was keyless-current).
DIASPORA (carried): Quantopian archive = the public successor ground of the Bitcointalk-era
posters — next dig target, with never-touched Wilmott/EliteTrader/Nuclear Phynance.
NEXT-SESSION QUEUE: (1) Kaiko VWM+TWAP diff vs desk normalizer (fully unblocked); (2) OP-008
binance trades 2026-07-01 Tardis-vs-recorder diff (unblocked); (3) desk-netflow vs CM-netflow
overlap diff; (4) Quantopian archive dig; (5) re-probe apidocs.bithumb.com for ToS.

### 2026-07-26 — VIDEO IS NOT BLOCKED (refutes the 07-18 finding, retires the GAP #26 purchase gate)
The standing record said "VIDEO: direct transcript fetch is IP-BLOCKED from this VPS
(RequestBlocked, tested 07-18)", and GAP #26 gated a PAID residential-proxy purchase on it. Half
right, wholly misleading: the DIRECT `youtube.com/api/timedtext` route does return empty from this
box, but PIPED instances (open-source YouTube proxies) serve the same caption tracks freely.
VERIFIED: `api.piped.private.coffee` returned 6 subtitle tracks and 2,089–2,165 chars of real
transcript text, keyless, first try. Bilibili is reachable through its own public API
(view → cid → subtitle json); videos without public CC honestly report none.
TOOL: `scripts/fetch_video_transcript.py <url|id>` (rotates 4 Piped instances) and
`--bilibili <BVid>`. VIDEO-LOCKED LOGGING IS NO LONGER A PURCHASE TRIGGER for YouTube — log only
genuinely unreachable platforms. LESSON: one failed route was generalised to "video is blocked" and
then gated a purchase; a negative result is about the ROUTE TESTED, never the whole capability.

### 2026-07-26 session C (EN frontier miner) — IN PROGRESS (write-first note; updated as items resolve)
ITEMS THIS RUN (bounded per completion contract):
1. BACKLOG BURN: (a) NAVER DataLab — re-confirm endpoint live + still key-blocked-on-human;
   (b) Kaiko — resolve the T1-a "RE-RUN REQUIRED" blocker facts: does Kaiko publish its Reference
   Rate FIXINGS freely (no fixings ⇒ no tracking diff is possible with ANY constituent set), and
   does crypto.com's public REST serve a deep trades tape (adapter feasibility)? Verdict → card.
2. QUANTOPIAN ARCHIVE DIG (era-archaeology, dark-forest mandate #1; the carried diaspora target):
   find the durable public archive route, map the ground, mine ≥2 strategy threads to reply-depth.
3. IF BUDGET REMAINS: apidocs.bithumb.com ToS re-probe (queue item 5).
STATUS: item 1 CLOSED (results below, write-up in watchlist/universe map in progress); item 2 next.
ITEM 1 RESULTS (all from live probes this run):
- NAVER: endpoint live (error 024 keyless, re-confirmed) — still blocked ONLY on the human free-key
  step. No change; stays pending-external.
- crypto.com public/get-trades: keyless, `end_ts` backward pagination, count cap 150/call, archive
  floor measured between 1370d and 1420d ago (serves 2022-10-25, empty by ~2022-09) ≈ **3.8 years
  of free tick history on a TRUE Kaiko constituent** — adapter feasible; deeper than bitstamp's 24h
  by ~1400×. Boundary probed at 12h/7d/30/90/365/730/1095/1250/1300/1370/1420d.
- KAIKO FIXINGS ROUTE FOUND (the T1-a "RE-RUN REQUIRED" unblocked on the ground-truth side):
  CFE **PBT (Continuous Bitcoin futures, settles to the Cboe Kaiko Bitcoin Index)** daily settlement
  is FREE per-date CSV: `cboe.com/us/futures/market_statistics/settlement/csv/?dt=YYYY-MM-DD`
  (2026-07-24: PBT/Z35 = 64156.00). Launch between 2025-12-01 (absent) and 2026-01-02 (present).
  LICENCE DISTINCTION (s13): these are Cboe's OWN futures settlement statistics, not Kaiko's
  key-gated index feed — no Kaiko value is redisseminated. T1a line 589 ("Published rate + index
  VALUES: NO") upgrades to PARTIAL-daily via this route.
- BONUS (same directory): `cdn.cboe.com/api/global/us_indices/definitions/all_indices.json` = 2,286
  indices; free 15-min-delayed quotes at `/api/global/delayed_quotes/quotes/_SYM.json` (verified
  _CMUSDTUSD = 0.9992 live). Includes **18 Coin Metrics reference prices (CMUSDTUSD/CMUSDCUSD peg
  series, CMXMRUSD…), CoinRoutes RealPrice family, Lukka LKRX/LKRE** — three more BMR-class
  administrator families disseminated free through the exchange. NOT new signal axes (redundant
  SOURCES for prices the desk can already compute) — no Stage-A owed on those; the one genuine
  axis-candidate is the PBT basis/regulated-funding series, handled next.
**[SESSION D 2026-07-28: session C DIED here — the PBT axis-candidate was NEVER handled (zero
mentions in watchlist/universe map as of session D start). Session C item 2 (Quantopian) and
item 3 (bithumb ToS) also not started. Taken over by session D below.]**

### 2026-07-28 session D (EN frontier miner) — IN PROGRESS (write-first note; updated as items resolve)
PRIOR STATE (resume rule): mine gate BACKLOG-CLEAR (all 5 carded finds disposed). Backlog
verify-queue surfaces Kaiko + NAVER, but BOTH were verified 2026-07-26 by session C (NAVER: §33
deferred(2026-08-09), sole blocker = human key step — re-probing today is duplication, not
verification; Kaiko: stays needs-monitoring on raw ticks only, fixings route found). NOT re-run.
Session C died mid-run with its PBT deliverable unwritten — resume mandate says finish the dead
run's item before opening new ground.
ITEMS THIS RUN (bounded per completion contract):
1. **FINISH SESSION C's UNFINISHED ITEM: Cboe PBT (Continuous Bitcoin futures) basis axis.**
   Graveyard/novelty-check the regulated-basis family first; card into data_axis_watchlist +
   universe map; pull the free daily settlement history (route session C verified:
   `cboe.com/us/futures/market_statistics/settlement/csv/?dt=`); declare timestamp alignment;
   run `libs.research.axis_screen` Stage-A in this run (expect UNDERPOWERED at n≈140 — an honest
   verdict, logged, with forward accrual). Also write the T1a line-589 upgrade session C promised
   if it is unwritten.
2. **QUANTOPIAN ARCHIVE DIG (era-archaeology, dark-forest #1; the carried diaspora target):**
   find the durable public archive route (s13-gated), map the ground, mine ≥2 strategy threads
   to reply-depth. Standing diaspora question: where did the named high-value authors go.
3. IF BUDGET REMAINS: Wilmott first touch (never visited per coverage row).
STATUS: **items 1 and 2 CLOSED to depth; item 3 not started (named, not buried). Full results below.**

#### ITEM 1 — CLOSED. Session C's dead PBT deliverable finished, and the axis is BIGGER than C knew. [§33: screened -> data/cfe_regulated_basis_screen.json]
- **The axis is a COMPLEX, not one contract.** Session C saw PBT only. The same free CSV
  (`cboe.com/us/futures/market_statistics/settlement/csv/?dt=`) carries the full CFE crypto suite:
  **FBT** monthly BTC futures (4-point term structure), **PBT** Continuous BTC (funding-style,
  2035 expiry — a US-REGULATED PERP ANALOG), **XBTF** mini, **FET/PET** the Ether pair. Launches
  measured by probe: FBT+FET 2025-09-29, XBTF 2025-11-26, PBT+PET 2025-12-15.
- **History pulled in full:** 2,005 rows / 207 trading days / all expiries →
  `data/cfe_crypto_settlements.jsonl`; derived spot-referenced basis series (DST-aware 16:00-ET
  alignment, declared) → `data/cfe_regulated_basis_daily.jsonl`.
- **Novelty gate run BEFORE compute:** graveyard kills (`funding_momentum`, cross-exchange funding
  dispersion) are offshore-perp constructions; live carry book = offshore funding. Regulated-venue
  participant set is access-segmented → distinct mechanism. PASS, nearest priors logged.
- **Stage-A (audited harness, 4 pre-declared cells, levels only, ALL logged):** PBT h1d
  UNDERPOWERED (n=204, IC 0.007 vs min-detectable 0.137); PBT h5d INSUFFICIENT (n=24); FBT h1d
  UNDERPOWERED (n=281, IC 0.016 vs 0.117); FBT h5d UNDERPOWERED (n=39). **Honest verdict:
  uninformative BOTH directions — no edge, no negative; the complex is 10 months old. Accrues
  free daily; re-screen dated on card 22 (2027).** Informative descriptives: FBT carry mean
  +6.73% ann (range −5.67%→+15.79%); PBT premium std 0.09% — the regulated funding mechanism
  binds tight to spot. Hazard logged: PBT prem same-period corr 0.434 (spot in denominator) —
  future screens use the PBT-minus-FBT or regulated-minus-offshore SPREAD.
- **TRAP CAUGHT (verify-don't-trust paying out):** `cdn.cboe.com/api/global/delayed_quotes/charts/
  historical/{SYM}.json` returns 200 with plausible daily OHLCV for "FBT"/"PBT"/"XBTF" — but it is
  the EQUITY namespace (First Trust Biotech ETF, Permian Basin Royalty Trust, delisted VanEck ETF).
  Caught only by cross-checking one known settlement value (64,212 vs 246.74). Logged in universe
  map as trap; generalization → operator library.
- Routed: watchlist **card 22** (grade verified-clean, §33 screened) + universe map source 60
  (`cboe_cfe_crypto_settlements`) + 3 research-memory rows (1 dataset validated, 2 hypothesis
  screening incl. the uninformative verdicts) + **T1a line-589 upgraded** (Kaiko index values:
  NO → PARTIAL-daily via PBT settle as a proxy with measured 0.09% error bound — session C's
  promised upgrade, now actually written).

#### ITEM 2 — CLOSED to depth. Quantopian archive OPENED + GROUND MAPPED; 2 threads exhausted. [§33: killed -> docs/graveyard.md era_inout_regime_rotation]
GROUND (the finite era mine, measured): **52,187 unique forum threads archived in Wayback**
(CDX statuscode:200, urlkey-collapsed) — essentially the whole forum. Durable route = Wayback
directly (GitHub mirrors checked: 2 repos, tiny/unlicensed — Wayback wins on s13 + completeness).
Extraction traps hit and solved → **OP-034** (stored-gzip `1f8b` captures; single-quote HTML
attributes; OP body login-walled but ALL replies survive; final code pasted verbatim in the dying
platform's last weeks). 52,187 threads is NOT exhausted and no such claim is made — two threads
are, and the recipe now makes the rest cheap.
- MINED TO EXHAUSTION (all replies, full text): `posts/new-strategy-in-and-out` (108 posts,
  Oct 4 – Nov 2020, the era's flagship collaborative strategy thread) + its explicit continuation
  `posts/live-slash-paper-trade-the-in-out-stragegy` (13 replies, reply-chain follow from R98 —
  the depth move, not a second surface pick).
- FINDINGS ROUTED:
  → **graveyard `era_inout_regime_rotation`** (pre-emptive kill of "port In&Out to crypto"): the
    thread's OWN decomposition shows bonds out-leg = +123% (~6.5%/yr) of the 942% total; the
    short-SPY swap collapses returns (out-signal precision too low to trade directionally); ±1
    parameter step costs 25-40%; same-idea variants diverge 2× YTD. Crypto translation: the
    out-leg is stables+funding — the desk's carry book ALREADY harvests it; the residual timing
    layer is the 3×-killed overlay class. The community falsified its own strategy in-thread and
    never named it that; era archaeology harvests the falsification for free.
  → **inbox #71** (signal sources need PRECISION, not liquidity — "we don't want exposure, just
    the price differences"; rejection of a signal input on liquidity grounds must name the traded
    leg affected or it is void; includes the era's own verification method, correlation-vs-ground
    -truth with the asof-date alignment fix — same hazard class as the desk's bithumb kill).
  → **WS-003 post-promotion confirmation** (4th platform/era): the OP was ABSENT from the capture
    and every load-bearing finding lived in replies — bond-beta decomposition R15/R40/R41,
    rebalance-artifact catch R82/R83, ratio-instability demo R88, complete final code R106.
  → **operator library**: OP-034 + the Quantopian-stratum lexicon (In&Out/OUT_DAY/magic numbers/
    handles-as-diaspora-tracers) + the SECOND-STRATUM COROLLARY: on platform archives the
    "search the rail" heuristic INVERTS — search the STRATEGY, follow the HANDLE.
- **DIASPORA (standing question ANSWERED for this community, explicitly, in-thread):**
  QuantConnect = canonical destination (R100/R104 name it; Kyle Oates explicitly organizes
  "capture the main thread on QC", which happened — the QC "Amazing returns" superthread);
  Quantiacs = the futures branch (Tentor Testivis, toolbox installable without signup);
  self-host branch = yfinance/pandas_datareader + IBridgePy/PythonAnywhere/EC2 (motivated
  in-thread by platform-risk: "dependent on external infrastructure which can be shut down any
  day" — a lesson learned in real time); one closed-group Slack (existence noted, content out of
  s13 scope permanently). Named leaders to trace on QC: Tentor Testivis, Dan Whitnable, Vladimir,
  Thomas Chang, Peter Guenther, Guy Fleury.
DEPTH LINE (per mandate, honest):
- In&Out thread: **exhausted** — OP reconstructed from quotes (capture login-walled it), all 107
  replies read in full, reply-chain link followed to its continuation thread, final code recovered
  verbatim from two independent replies.
- Live-trade thread: **exhausted** (13/13 replies).
- Quantopian archive as a whole: **mapped, NOT exhausted** — 52,187 threads; per-item exhaustion
  claims only, per the completion contract.
ITEM 3 (Wilmott): **NOT STARTED** — named, not buried; remains the next-run candidate.
NEXT RUN TAKES FIRST: (1) OLMAR thread cluster (`posts/olmar-*`, 9 archived captures located this
run — 2013 era, on-line portfolio selection + its era debunking); (2) "Quality Companies in an
Uptrend" (the companion superthread — its combination experiment posts); (3) Wilmott first touch.
STANDING DIASPORA QUESTION (next layer): the QC "Amazing returns" superthread itself — mine it for
what the In&Out community DISCOVERED after 2020 (did the strategy survive out-of-sample? The
2022 bond crash is the natural experiment the era never saw — free forward-validation evidence).
PROACTIVE BATTERY (moves run this session, per standing duty):
- #2 ADJACENCY: OP-033's encoding-trap SHAPE recurred one layer down — stored-GZIP captures render
  as identical mojibake; solved and written as a paired class into OP-034. Also applied to the
  session-death shape: sessions A and C both died before writing, so D committed item 1 to remote
  BEFORE opening item 2 (the note is now provably crash-proof, not just write-first).
- #3 CONFIG-VS-OUTCOME: every "screened/pulled" claim above names its on-disk artifact; the Cboe
  bulk route was REJECTED because one known settlement value failed to reproduce (64,212 vs
  246.74) — a 200-with-plausible-dates response is config, not outcome.
- #9 SCOPE-THE-NEGATIVE: the failed bulk route was scoped to "delayed_quotes serves the EQUITY
  namespace", not "no bulk route exists"; the 4 UNDERPOWERED screen cells are recorded as
  "could not tell", not "refuted" — both would have been capability-negatives from route-negatives.
- #8 NEGATIVE SPACE: the Quantopian archive (52,187 threads) had never been touched by any desk
  organ despite being a named region ground since 07-20; opened and mapped this run.
- #4 REGRESSION SWEEP: card 22's grade text contains no pending-substring, so it parses RESOLVED —
  the new card adds ZERO standing backlog burden (checked against source_backlog._classify rules).
  Moves #1/#5/#6/#7/#10 produced nothing beyond the above this run — reported as such, not skipped.

### 2026-08-01 session E (EN frontier miner) — IN PROGRESS (write-first note; updated as items resolve)
CONCURRENCY: a CN frontier-miner session is live in this same working tree (uncommitted note at
file end as of my start). All my edits are surgical anchored Edits inside the EN section, never a
whole-file write, and I commit each item as it closes (session A and C both died before writing).
Mine gate: **BACKLOG-CLEAR** (`scripts/mine_gate.py`: all 7 carded finds disposed; mining authorised).
VERIFY-QUEUE (resume rule, 60s config-vs-outcome — NOT re-derived): the 4 pending items are litminer
cards 23/24/25 carrying **future-dated deferrals** (2026-08-07 / 2026-08-10) with owning R-rows, plus
NAVER (credential-blocked, deferral 2026-08-09 stands). Card 23 states the build is owed by the alpha
org and that litminer freeze bars the runner code — re-probing today is duplication, not verification.
Nothing in the queue is EN-region-actionable today. Named, not silently skipped.
PRIOR EN STATE (resume rule): last EN session 2026-07-28 (session D). Its written chain, in order:
(1) **OLMAR thread cluster** (`posts/olmar-*`, 9 Wayback captures already located by D — 2013 era,
on-line portfolio selection + its era debunking); (2) "Quality Companies in an Uptrend" companion
superthread; (3) **Wilmott first touch** (never visited by any desk organ; carried and NOT started
across sessions B, C and D — a §37 silent-carry, named here rather than carried a fourth time).

ITEMS THIS RUN (bounded per completion contract; depth per item unbounded):
1. **OLMAR / on-line-portfolio-selection cluster — carried pointer #1, and it lands on the desk's
   ONLY never-tested strategy family.** `data/strategy_coverage.json` (2026-08-01T05:50Z) grades 14
   families: 7 HUNTED, 6 THIN, and **STATISTICAL-ARBITRAGE = MENTIONED-NEVER-TESTED, n_tested=0**.
   OLPS (OLMAR/PAMR/universal portfolios) is relative-price mean reversion — that family exactly.
   L1.35 prefers an unhunted family over deepening a worked one, so this is the highest-value
   version of the carried pointer, not merely the next thread. Plan: mine the cluster to reply-depth
   incl. the era's own debunking, novelty-gate BEFORE compute, and SCREEN-ON-DISCOVERY in the same
   run if a stated-mechanism construction emerges (every construction logged as a charged trial).
2. **WILMOTT FIRST TOUCH** — the never-visited EN legacy ground, plus the standing VENUE-DISCOVERY
   obligation (the seed list is a floor: harvest venues named *inside* threads, not just the row).
3. Data axes are hunted on every venue touched, even when the strategy yield is zero — a dig
   returning 0 strategies and 1 new axis is a GOOD dig.
STATUS: **items 1 and 2 CLOSED. Full results below.**

#### ITEM 1 — CLOSED. OLPS/OLMAR killed on our own data, and the era's OWN kill reason REFUTED. [§33: killed -> docs/graveyard.md era_olps_olmar_portfolio_selection]
GROUND: the OLMAR cluster is **20 archived threads, not the 9 session D logged** (CDX
`filter=original:.*olmar.*`) across two strata — the 2014 original wave and the 2019–20 revival.
- MINED TO EXHAUSTION (all posts, full text): `olmar-implementation-fixed-bug` (65 posts, 2014,
  the original wave), `comparing-olps-algorithms-olmar-up-et-al-dot-on-etfs` (40 posts, 2019, the
  family-level comparison), `odd-behavior-olmar-algorithm-and-commissions` (7 posts, 2014).
- **DEPTH PAID THE WHOLE BILL: the paper's OWN AUTHOR is in the 2014 thread.** Bin Li (Li & Hoi,
  ICML 2012) replies at posts 19/21 and concedes the algorithm's central defect in his own words:
  *"in some extreme cases, it does happen that the vector contains one 1 and the rest are 0s. We
  are still looking methods to control its behaviors."* That admission exists nowhere in the paper.
- NOVELTY GATE RUN BEFORE COMPUTE (audited harness): nearest prior `short_term_reversal (xsec)`,
  similarity 0.25, **NOT redundant**. Treated as UNINFORMATIVE rather than a green light — the
  desk's own 2026-07-30 research-engine audit measured this gate at **0% recall**. The kill below
  is justified on mechanism and measurement, never on the gate's PASS.
- **THE ERA'S STATED KILL REASON WAS TESTED AND FAILED.** Grant Kiehne (2019) blamed correlation:
  OLMAR dies on sector ETFs because they are "an arbitrarily coarsely chopped SPY". That is
  falsifiable, so it was measured — one estimator, both universes, our own lake, and we happen to
  hold **the exact 8 sector SPDRs he named**. Idiosyncratic share of daily return variance vs the
  panel's own leave-one-out equal-weight factor: **crypto top-8 0.513 / top-30 0.467 vs sector
  ETFs 0.492**, with crypto carrying **3.3–3.8× the cross-sectional dispersion** (0.0283/0.0324 vs
  0.0085 daily). Crypto is NOT more factor-dominated than the universe that already failed. The
  convenient conclusion was the wrong one and is recorded as refuted (`data/olps_era_mechanism_test.json`).
- **WHAT ACTUALLY KILLS IT, measured on our panel** (published rule, PAPER DEFAULTS w=5 eps=10,
  ONE pre-registered config, no sweep; `data/olps_olmar_crypto_run.json`): gross CAGR **+11.28%
  vs uniform-CRP +42.24% and BAH +39.38%** — a −31pp/yr deficit at ZERO cost; mean max-weight
  0.991 → **effective N = 1.02 of 8**, reproducing the author's own confession 14 years later;
  median turnover **1.851/day** → net −8.06% @5bps, −24.05% @10bps, **−75.49% @39.5bps** (the
  desk's fail-closed p90). Universe picked on CURRENT liquidity biases the test UP; it fails anyway.
- **THE LOAD-BEARING NEGATIVE:** the dispersion result is written INTO the graveyard row's lesson
  field precisely so this kill can never be miscited as "crypto has no cross-section". The family
  dies on its ALLOCATION RULE, not on the opportunity set.
- Era self-falsification harvested free (the reply layer, not the headline): Paul Perry's full
  OLPS-toolbox comparison — *"hard to say that any of these algorithms decidedly beat BAH or CRP…
  OLMAR is really not outperforming"*; ONS + Borodin et al. (2004) — uniform CRP beats all prior
  algorithms; **Thomas Wiecki (Quantopian head of research) publishing only after swapping
  VolumeSlippage→FixedSlippage *because the volume model stopped the rebalance completing*** — the
  friction WAS the finding; "Blue Seahawk" recomputing a headline 190% to **58% on capital actually
  utilized vs a 128% benchmark**; Jason Tichy — *"it only seems to work with the seed money of
  $100k"*, disqualifying for a §42 small book on its own.
- ROUTED: graveyard row (with an explicit L1.16a re-entry condition — a turnover-constrained OLPS
  variant holding effective-N>3 and median turnover<0.15 BEFORE any return is computed; a new
  parameter set is NOT an enabling change), 2 research-memory rows (1 rejected hypothesis, 1
  validated construction), **OP-035**, inbox pointer, **R0286 + R0287**, 2 data artifacts.
- ADJACENCY (battery #2) PAID OUT ON OUR OWN CODE: the 2014 thread's defect is an int-vs-float cast
  in the commission model that silently changed backtest results (CEO-confirmed, zipline#128), and
  the community's own read was *"members haven't been too concerned with trading costs, to-date,
  since one would expect that the bug would have been found by now"*. Hunting that SHAPE in our
  tree found **`libs/risk/growth_leverage.py:124`**: `analyze()` returns `cagr`/`ann_vol`
  annualized at the caller's ppy (`run_crypto_portfolio.py:186` correctly passes 365) beside
  `risk_of_ruin()` called with NO horizon, silently using its default **252** — two year
  conventions in one output row, understating annual ruin on the L1.23 rail. **Verify-don't-trust
  mattered: my first read flagged ppy=252 as the bug and that was WRONG** — the crypto caller
  passes 365; the real defect is one line down. Rowed R0286 (freeze barred the fix).

#### ITEM 2 — CLOSED as a genuine FIRST TOUCH (the 4-session silent carry is ended). Wilmott: MAPPED, verdict THIN-BUT-REAL.
- **ACCESS: 403 direct from this VPS on all three hostnames — a ROUTE negative, not a capability
  negative** (battery #9). Wayback carries **14,890 unique `viewtopic` threads** (CDX, collapsed,
  statuscode:200), so the ground is fully open by a §13-clean public-archive route.
- **BOARD MAP RECOVERED — this is the durable deliverable, because phpBB URLs carry no titles and
  without it every future run must surface-scan.** Thread counts by board:
  `f=15 Off Topic 8,200` | `f=10 Programming and Software 2,229` | `f=73 Politics 1,885` |
  `f=3 General 1,790` | `f=16 Careers 1,717` | `f=4 Technical 1,709` | `f=44 Quantitative Finance
  Code Library 1,244` | `f=8 Student 1,201` | `f=38 Trading 1,052` | `f=34 Numerical Methods 1,033`
  | `f=11 Book And Research Paper 830` | `f=26 Brainteaser 721` | `f=41 Economics 475`.
- **FIRST-PASS VERDICT: THIN-BUT-REAL, and the map is what makes it cheap.** ~68% of the archive
  (Off Topic 8,200 + Politics 1,885 + Careers/Student) is noise; the mineable core is
  Trading + Code Library + Technical + Numerical Methods + Book/Research ≈ **5,868 threads**.
  Wilmott is a derivatives/vol/rates community, so expect execution, microstructure and numerical
  methods rather than crypto mechanisms — 2 crypto-keyword hits in the 50 titles sampled.
- **CROSS-PLATFORM CONVERGENCE ON TODAY'S ITEM 1:** Trading board `t=100441` is titled
  *"Are the online portfolio selection alg. practical approach?"* — an INDEPENDENT community
  interrogating the exact family killed above. **Honest null: no Wayback capture of that thread
  body exists** (title recovered from the board listing; CDX returns zero rows for t=100441), so
  it is title-only evidence and is NOT counted as corroboration of the kill.
- Named for the next run from the 50 titles sampled: `t=100271` "Probability of limit order being
  filled given a state of the order book" (execution-reality-model relevant), `t=85860` RenTech
  strategy-morphing, `t=100638` "Volume as trend detector", `t=100661` factor investing.
- **OP-035 EARNED ITS KEEP TWICE IN ONE RUN.** Wilmott's 2017 skin uses `itemlist__item
  topic_read`, NOT phpBB's default `topictitle` — my first two extraction passes returned 0 titles
  from 115KB pages that were full of them. The class census diagnosed it in one command, on a
  second platform, hours after the operator was written for the first.


**§33 dispositions (2026-08-18, owed-work batch3 — items above, in order):**
- Wilmott first touch: [§33: screened] — items 1-2 closed in-block ('Full results below'); ground later measured WALLED x3 (:5490,:5523)
### 2026-08-04 session D (EN frontier miner) — IN PROGRESS (write-first note; updated as items resolve)
MINE GATE: BACKLOG-CLEAR (all 5 carded finds disposed; mining authorised). Generation priors read:
data_axis_watchlist is the only measured class (57.1% conversion, 0d median latency) → favoured.
PRIOR STATE: session C (07-26) closed its item 1 (NAVER + Kaiko blocker facts, crypto.com tape,
Cboe PBT fixings route) but DIED before (a) syncing those verdicts into the watchlist cards —
which is why source_backlog_next still lists Kaiko+NAVER as pending 9 days later — and (b) its
item 2 (Quantopian archive dig). JP miner 08-01 ruled bitFlyer `restricted-by-licence` (ToS read,
Wayback 20190601153535 of bitflyer.jp/en-eu/terms-of-use) but watchlist card #3 was never synced.
ITEMS THIS RUN (bounded per completion contract):
1. BACKLOG BURN / SESSION-C COMPLETION (Tier-1 defect-closer — the verify-queue is stale, every
   future cycle re-reads dead items): (a) card #21 NAVER — technical verification is DONE 3×
   (07-25/07-26 live-probe evidence); re-route to the account-gating (legitimacy/human) queue where
   it honestly belongs; (b) card #3 bitFlyer — sync the JP 08-01 licence ruling → terminal;
   (c) card #8 Kaiko — execute the card's own "RE-RUN REQUIRED": reconstruction against the TRUE
   constituent set (Bitstamp/Crypto.com/Gemini/Kraken; LMAX leg destroyed-at-source, no free
   history) diffed vs a PUBLISHED fixing (Cboe PBT settlement CSV route found by session C).
2. QUANTOPIAN ARCHIVE DIG (session C's unfinished item 2; era-archaeology, the carried diaspora
   target since session A): durable public archive route, ground map, ≥2 strategy threads to
   reply-depth, graveyard-check every dead-era mechanism.
3. IF BUDGET REMAINS: Wilmott/EliteTrader/Nuclear Phynance FIRST TOUCH — robots.txt + ground
   survey only (KR/JP lesson: read robots.txt before digging; platform beats geography as the
   block predictor).
STATUS: item 1 CLOSED (details below). Item 2 open.
ITEM 1 RESULTS — backlog verify-queue 2→0 pending technical, 8→10 resolved, all 3 remaining
legitimacy items genuinely human-blocked (GAP #67 rulings due 08-15; GAP #69 NAVER key):
- NAVER #21: 3rd live keyless probe (401/024 today) → re-queued as account-gating (the parser's
  own legitimacy-queue definition); treadmill ended.
- bitFlyer #3: synced to CLOSED restricted-by-licence per the JP 08-01 ToS read; GAP #68 moot
  (rowed R0019). Graveyard entry `jp_bitflyer_direct_recording` RESTORED verbatim from bd32eda.
- Kaiko #8: the 07-26 "RE-RUN REQUIRED" EXECUTED → `data/kaiko_true_constituent_rerun.json`,
  21 trials all logged. Constituent-set effect **0.30 bps** (small!); desk's invented params were
  the real error (**4.34 bps**); published prose ambiguous to **±4.7 bps** (1/rank vs 1/mid-age
  weight reading) so ~5 bps is the fidelity floor without the exact formula; VWM vs VWAP 16.4 bps
  this window (value-add re-confirmed); 3-of-5 historical fixing +8.5 bps vs PBT/Z35 settle
  63,832.00 (basis-contaminated band, declared). NEGATIVE ROUTE FACT: Cboe us_indices carries CM/
  Lukka/CoinRoutes free but ZERO Kaiko entries — no free intraday Kaiko dissemination exists.
  Gemini public tape floor ~40 min (probed; corroborates session C). Card → verified-clean.
- **P0 FOUND EN ROUTE (rowed R0018): the working tree FORKED from master at 3bf89cd (07-29)** —
  master holds 419 commits this line lacks (all 08-01/08-02 work incl. §33 enforcement fixes +
  graveyard entries); 08-03/08-04 snapshots land only here (23 commits); master frozen since
  08-02T08:38Z; this branch's own origin moved 63 commits ahead mid-session (sibling live).
  Repair rowed with the R0261 union convention; NOT attempted here (out of freeze lane).
  FORK COROLLARY found at push time: the L1.37 pre-push hook calls scripts/run_law_gate.py which
  exists ONLY on master → every push from this branch fails on ENOENT (why the cron sat 6+
  commits unpushed). This run pushed docs-only artifacts via the hook's own sanctioned
  --no-verify, recorded here; merging master back restores the gate and closes the bypass.
  MERGE DONE THIS RUN (sibling line only, not master): the 63-commit origin divergence was merged
  (7fc92ce), 5 conflicts resolved by the desk's own conventions — ratchets took the max
  (test_suite 243, LAW_COVERAGE 100/100/100, conversion_record HEAD side), holdings honored the
  sibling's schema migration, weak-signal registry UNIONED (both WS-005s kept; mine renumbered
  WS-006, id computed once per R0261).
ITEM 2 RESULTS — QUANTOPIAN ARCHIVE OPENED (session C's carried item, era-archaeology):
- GROUND: quantopian.com fully dead (HTTP 000). Archive route durable: Wayback /posts/* = **12 CDX
  pages of unique thread slugs** — a FINITE, mappable, exhaustible ground (OP-034 written: slug
  index + LENGTH-column triage separates ~9KB JS shells from 30-60KB server-rendered full threads;
  id_ bytes can be stored-gzip, sniff `1f 8b`). Ground is MAPPED, explicitly NOT exhausted.
- MINED TO DEPTH (2 threads + 3 HN trees): `olmar-implementation-fixed-bug` (2014 capture, 315KB,
  the era's most-cloned algo, 708 clones) → **graveyard `olmar_olps_era_zero_cost_canon`**: the
  canonical shared code hardcodes `commission=0` + `price_impact=0` on a hand-picked sid list —
  3rd independent instance of the fee-artifact class; audit the COST MODEL first in any inherited
  era code. `new-strategy-in-and-out` (2020, 100+ replies) → **graveyard
  `inout_early_warning_rotation_fragility`**: killed in-thread by the community's own perturbation
  test (constants 15/58→20/53 = "drastic drop"); residual general cross-asset lead-lag question →
  **WS-006** (crypto analog, de-contam caveat declared). HN 15652997 (94 comments, walked to
  depth 5) + 24931089 + 24940644 → **graveyard `crowdsourced_backtest_selection_fund`**: the
  at-scale natural experiment (backtest Sharpe>2.5 selection → live −3% vs SPX +6.6% → investor
  capital RETURNED Feb 2020) = the historical evidence base for the two-stage law. WS-003
  (reply>OP) observations 3→6.
- DIASPORA (the standing question, ANSWERED from primary captures): Quantopian's community went to
  **QuantConnect** (main successor, with friction — "platform quite different… gave up"; paid port
  offers in-thread at $250-300), **IBridgePy** (live trading), a dedicated **Slack workspace**
  (created in-thread by Chris Liu), cloudquant, factset.quantopian.com (enterprise arm), and the
  open-sourced **github.com/quantopian** org (zipline/alphalens/pyfolio = the surviving artifact
  layer; repo-chain dig queued). Bitcointalk-era → Quantopian → QuantConnect chain now complete.
- NO NEW DATA AXIS surfaced (equities-era, dead platform) → no Stage-A screen owed this run;
  nothing carded as tradeable (nothing passed the mechanism-prior bar for a crypto desk).
ITEM 3 (Wilmott/EliteTrader/Nuclear Phynance robots.txt first touch): **NOT STARTED** — named,
not buried. First item next run alongside quantopian-algos repo chain + section-by-section
/posts/* exhaustion (OP-034) + HN 9152332 contest-winner tree (unmined).
DEPTH LINE: olmar thread = full-thread read (315KB server render, reply layer to Wiecki refactor);
in-and-out = 2 captures compared, reply layer through the 100th-reply mark incl. the kill;
HN 15652997 = full tree walk, 94 comments, best find at depth 5; CDX ground survey = 3 calls.
NOT breadth-theater: every graveyard entry came from a reply layer or a settings line, none from
an OP's claim.
STANDING TEST ("which artifact on disk is different because of what was mined?"):
data/kaiko_true_constituent_rerun.json (21 trials); docs/graveyard.md +4 entries (3 new + 1
restored); data_axis_watchlist cards #3/#8/#21 re-graded (verify-queue 2→0);
search_operator_library +OP-034; weak_signal_registry +WS-006, WS-003 updated; recommendation
ledger +R0018/R0019. Verify-queue state change is the run's conversion payload.

## SESSION NOTES — CN frontier miner

### 2026-07-26 session 1 (CN frontier miner) — IN PROGRESS (write-first note; updated as items resolve)
PRIOR CN STATE (read before starting, per resume rule): exactly ONE prior CN session ever
(2026-07-19, surface-layer CSDN/VeighNa/BigQuant/Zhihu/FMZ) → RSRS found + EV-killed,
ML-funding-rate-prediction graveyard-matched. Ground is effectively unmined. Mine gate:
BACKLOG-CLEAR. Backlog verify-queue items (Kaiko, NAVER) were both closed by EN session C this
same day — not re-run here (that would be duplicated work, not resumption).

ITEMS THIS RUN (bounded per completion contract — depth maxed, breadth bounded):
1. **DEFECT-CLOSER, Tier-1 — universe-map axis #76 `usdt-cny-otc-premium` is CATALOGUED BUT NEVER
   INGESTED** (cataloged 2026-07-22, grade UNVERIFIED, parked on the claim *"no clean free API
   found; TradingView script is a lead, not a feed"*). This is the exact leak SCREEN-ON-DISCOVERY
   was written to close, sitting in MY region. Attack the routing claim: hunt a free live
   USDT/CNY (and USDT/RMB OTC) quote route. If one exists → catalog it, pull history, and run
   `libs.research.axis_screen` Stage-A **in this run**. Mechanism prior is the desk's strongest:
   kimchi premium scored IC +0.148 / timing Sharpe 1.3, and the desk's OWN graveyard entry
   `era_crossvenue_fiat_premium_arb` establishes *premium magnitude tracks BARRIER HEIGHT* —
   mainland China has the highest barrier in the world (capital controls + the 2021 total ban),
   so the CNY premium is the highest-barrier premium available and, per that same entry, must be
   used as an INFORMATION/TIMING signal and NEVER sized as arb.
2. **ERA-ARCHAEOLOGY (dark-forest #1) — the `banzhuan` (搬砖, cross-border arb) era on the CN
   boards** (8btc/Babbit, ChainNode old boards, Baidu Tieba bitcoin bar) via Wayback. Hunts the
   HISTORICAL provenance + mechanics of the same premium mechanism as item 1 (deliberately paired,
   not scattered): what drove the CNY premium, what killed each era of it, where the barrier sat.
   Plus dark-forest #2: extend the CN lexicon in the operator library with every new term learned.
3. IF BUDGET REMAINS: Gitee / CN-GitHub repo chain (vn.py lineage, factor libraries) per OP-001.
STATUS: **item 1 CLOSED to depth. Item 2 OPENED after item 1 committed — ground surveyed, one thread
mined to reply-depth, one graveyard entry + one inbox item + one operator produced. The CN era archive
is NOT exhausted; it is now MAPPED. Item 3 not started.**

#### ITEM 1 — CLOSED. Axis #76 un-parked, ingested, screened. [§33: screened -> data/cny_otc_premium_history.jsonl]
THE PARKED CLAIM WAS WRONG. #76 sat 4 days on *"no clean free API found; TradingView script is a
lead, not a feed."* Three keyless routes exist and all agree: OKX C2C (`/v3/c2c/tradingOrders/books`,
393 ads both sides with full depth), Binance P2P (`/bapi/c2c/v2/friendly/c2c/adv/search`), and
`history.btc126.com/usdt/api.php` for daily history. ECB (`api.frankfurter.app`) serves the FX leg
free back to 1999. HTX/Huobi OTC answers 200 but `totalCount=0` — CNY OTC has **left** Huobi
(diaspora datapoint). ChaiNext, the original index publisher, is **NXDOMAIN**: btc126 is a surviving
mirror of a dead index family, so it is a single point of failure and the desk's own recorder must
stay primary.
- **WHAT UNLOCKED IT: the native-language query, and nothing else** (now OP-032). Controlled A/B in
  the same minute: the English query returned CoinGecko/CMC boilerplate and the explicit conclusion
  *"may not be readily available through standard free APIs"* — a confident FALSE NEGATIVE. The
  Chinese query `USDT 场外价格 历史数据 API 人民币 溢价指数` returned the formal index definition plus
  the site serving the free history. This is the desk's LLM-translation edge paying out literally.
- **HISTORY RECONSTRUCTED (now OP-031).** The api.php route hard-caps at a rolling ~177 rows; ten
  parameter guesses all returned the identical 177. The cap is unliftable — but the *endpoint* is
  archived. CDX-replaying `api.php` itself (with the `id_` raw flag) recovered 414 more days.
  **591 daily rows, 2020-03-16 → 2026-07-25** → `data/cny_otc_premium_history.jsonl`. Gap
  2021-05-08→2026-01-26 is permanently unrecoverable (only 4 captures exist) and is declared, not
  hidden. `row_id=10` on 2020-03-16 proves the series begins ~2020-03-06, so the gap is *bounded*.
  Context for scale: the desk's live recorder `data/cny_premium.jsonl` held **4 rows** — the axis was
  unscreenable before this run.
- **MEASUREMENT CROSS-VALIDATED THREE WAYS** on the same date: desk-computed OKX mid ÷ ECB =
  **−0.623%**, btc126 published = **−0.62%**, desk recorder (Binance P2P) = **−0.618%**.
- **STAGE-A SCREEN RUN (audited harness, all 4 cells reported, no cherry-pick):** block1 h1d
  UNDERPOWERED (IC −0.027); block1 h5d UNDERPOWERED **+ de-contam FAILED** (same-period corr −0.281);
  block2 h1d **SCREEN-INTERESTING** (n=155, IC −0.0748, reversal Sharpe 1.39, de-contam passed) **but
  `powered=false`** — min-detectable IC 0.157 > |IC| 0.075, i.e. **not distinguishable from zero**;
  block2 h5d INSUFFICIENT-DATA (n=36). Alignment declared (23:55 CST = 15:55 UTC, predicts UTC-day
  D+1; **robust to the timezone ambiguity** — forward-only either way). Quantization checked:
  std/tick 9.5 and 4.0, above the 3.0 floor, so signal not rounding.
- **HONEST VERDICT: no promotable edge.** No clock, no Holm slot, no capital. But two findings
  survive the null, and BOTH contradict the catalogued prior:
  (1) **the sign is backwards** — all 4 cells negative (premium up → next-day return *down*), against
  #76's "premium up = inflow = bullish";
  (2) **the magnitude prior is falsified** — premium std collapsed **1.397% (2020-21) → 0.580%
  (2026)**, now **~4× smaller than kimchi** (2.0–2.3%). China holds the world's highest capital
  barrier and the world's *smallest* stablecoin premium. Reconciling variable: **merchant-network
  depth** (393 live ads on one venue). This refines the desk's own `era_crossvenue_fiat_premium_arb`
  rule — barrier height sets the premium's *ceiling*; merchant density sets where inside it it sits.
- **ADJACENCY MOVE (proactive battery #2), run in the same pass — NEGATIVE and informative.** Applied
  OP-031 to the desk's other capped endpoint of identical shape (`bitcoin-data.com/v1/mvrv` etc.,
  1,461-row window, params accepted-and-ignored): **0 CDX captures**, nothing recoverable. So
  OP-031's success rate is set by *archive density*, not by the cap — API paths are archived far more
  sparsely than HTML pages. Operator updated with a "check CDX count first" precondition.
- FLEET CONTRIBUTIONS (charter §16): **OP-031** (Wayback-replay a JSON API to defeat a rolling cap),
  **OP-032** (search the native language FIRST — with the A/B evidence), and the **CN lexicon** (12
  terms, those confirmed in live use this run marked ✓).

DEPTH LINE: axis #76 — **exhausted for this route**: live routes probed both sides (393 ads), history
route parameter-attacked 10 ways, CDX-replayed to its floor, series cross-validated against two
independent constructions, screened across 4 target-horizon cells, quantization and timezone
robustness both tested, and the adjacency instance tested and closed. Not surface, not breadth-theater.
#### ITEM 2 — OPENED, ground MAPPED, one thread mined to reply-depth. NOT exhausted. [§33: killed -> docs/graveyard.md era_crossvenue_fiat_premium_arb 4th instance]
GROUND SURVEY (the era-archaeology precondition — do this before hunting, it is one cheap call):
**8btc.com, chainnode.com and Baidu Tieba are ALL unreachable from this box.** This is genuine dead
forest: the ground exists only in Wayback. CDX confirms the old Discuz structure is archived
(`8btc.com/forum-1-1.html` back to 2013-10-26; `chainnode.com/forum-108-1.html`, `forum-110...`).
**Note for the next run: `chainnode.com/post/70078` — a 「比特币搬砖套利攻略」 surfaced by search — has
ZERO CDX captures. It is visible in search results but unreadable. Do not spend budget re-finding it.**
- MINED TO DEPTH: `8btc.com/thread-53689-1-1.html` 「P网搬砖简明指南（以及一种交易策略）」(2017-05-02,
  capture 20171019172042) — OP + reply chains at depth 1 and 2, 7 substantive posts.
- **ENCODING TRAP HIT AND SOLVED (now OP-033):** the page is **GBK**, not UTF-8. Decoded as UTF-8 it is
  solid mojibake — indistinguishable from a corrupt capture, and the natural move is to discard the
  source. That would have produced a false *"CN era boards are unreadable"* conclusion. Pre-2018
  regional forums are gb2312/gbk/big5/euc-kr/shift_jis; the dark-forest mandate and this operator are
  now permanently paired.
- FINDINGS ROUTED (nothing carded as tradeable — the class is already graveyarded and stays so):
  → **graveyard**: 4th independent instance of `era_crossvenue_fiat_premium_arb`, with the mechanism
    detail the other three lacked. Gap up to **10%**, ~3% net after fees, and the binding barrier named
    outright: **domestic venues could not withdraw BTC**. The replies expose the permissions layer
    (Poloniex refused mainland registration → users selected "Hong Kong"; KYC capped $2k until ID
    upload). **The new mechanism detail: BTC was frozen but ALTCOINS WERE NOT** — the arb routed around
    the barrier on the fastest-confirming rail (XRP worked example; XLM/ZEC/SC/NEO named at depth), and
    the OP explicitly warns BTC itself works badly under congestion. The barrier was asset-specific.
  → **improvement_inbox #70**: the one still-live idea. 「搬砖砸脚」 ("dropping a brick on your own
    foot") is the era's name for **transfer latency as unhedged directional exposure**, with two
    generalising mitigations: move on the fastest-confirming asset (a free choice), and start the move
    only when short-term momentum favours your exposure. Open question for whoever owns execution:
    does `cost_model` price inter-venue transfer as a fee, or as fee + in-flight variance? NOT checked
    this run (research freeze) — filed as hypothesis, not adopted.
  → NOT carded, recorded as era knowledge: a depth-1 reply argues the frozen-withdrawal regime made
    domestic BTC supply **segmented and deflationary**, making the *re-opening* a predictable catalyst.
    Sophisticated, but untestable now — dead venues, and 2026 mainland rails are more closed than 2017.
- **CONNECTS THE TWO ITEMS (why they were paired, not scattered):** 2017's 10% gap vs 2026's 0.580%
  premium std is exactly the barrier-vs-merchant-depth finding from item 1. In 2017 the rail was frozen
  and the premium was enormous; in 2026 the capital barrier is *higher* yet a deep 承兑商 (OTC merchant)
  network grinds the premium to a quarter of Korea's. **Barrier height sets the ceiling; merchant
  density sets where inside it the premium sits.** Era archaeology paid for the live axis, as designed.

DEPTH LINE (per the depth mandate — honest, per lead):
- axis #76 (item 1): **EXHAUSTED for this route** — both sides of two live books probed (393 ads),
  history endpoint parameter-attacked 10 ways, CDX-replayed to its floor, cross-validated against two
  independent constructions, screened across 4 target-horizon cells, quantization + timezone robustness
  both tested, and the adjacency instance (bitcoin-data.com) tested and closed NEGATIVE.
- 8btc thread-53689 (item 2): **reply-chain ≥2** (quoted-reply chains at depth 2 gave the permissions
  and KYC mechanics the OP omitted — the depth outranked the surface, exactly as the mandate predicts).
- 8btc / ChainNode boards: **SURVEYED ONLY, explicitly NOT exhausted.** One thread of an archived
  multi-board Discuz. This is the honest state — no "EXHAUSTED" claim is made or earned.
NOT DONE THIS RUN (named, not buried): item 3 (Gitee/CN-GitHub repo chain, OP-001); Zhihu/Xueqiu/
JoinQuant/BigQuant BBSs; Bilibili quant lectures (video is now readable — `fetch_video_transcript.py
--bilibili`, and NO CN video was tried this run, so nothing is video-locked and nothing was logged).
NEXT RUN TAKES FIRST: (1) section-by-section exhaustion of `8btc.com/forum-*` era boards via OP-021
board-tail pagination + OP-020 whole-thread extraction, now that OP-033 makes them readable;
(2) Gitee/CN-GitHub repo chain per OP-001.
OPEN QUESTION CARRIED (diaspora, standing): CNY OTC has left Huobi (`totalCount=0` on a live 200) — the
books are now on OKX C2C and Binance P2P. Where did the *discussion* go? (OKX/Bitget/Gate CN
communities, CN-language Telegram/X, overseas Zhihu mirrors.)

### 2026-08-04 session 2 (CN frontier miner) — IN PROGRESS (write-first note; updated as items resolve)
RESUME STATE: mine gate BACKLOG-CLEAR (all 3 prior cards disposed). source_backlog: 0 pending
technical verification; the 3 pending LEGITIMACY decisions (Upbit portal, Glassnode/CryptoQuant
vendor-replacement, NAVER DataLab) are KR-region/vendor-policy items already tracked by the backlog
itself — outside CN scope, not silently skipped, named here. Generation priors favour
data_axis_watchlist class (0.571 conversion). Prior session's named NEXT items are this run's items.

ITEMS THIS RUN (bounded per completion contract — depth maxed, breadth bounded):
1. **ERA-ARCHAEOLOGY: 8btc.com `forum-*` era boards, section-by-section** — OP-034 (CDX slug index +
   length triage + gzip sniff) to map the dead board into a FINITE crawl, OP-021 era-seek for the
   banzhuan / 94 (Sept-2017) / 2013 windows, OP-033 GBK decode, reply-chain ≥2 on every thread taken.
   Graveyard-check before carding; every new slang term → lexicon. Goal: section map + highest-value
   era threads mined; claim EXHAUSTED only per-section, honestly.
2. **Gitee / CN-GitHub repo chain per OP-001** (vn.py lineage, factor libraries) — deferred twice
   (s1 item 3 unstarted both runs); takes real budget this run. Forks/issues/contributor-chain depth.
3. IF BUDGET REMAINS: diaspora open question (where CN OTC discussion went) — one probe, else recarry.
STATUS: **RUN COMPLETE — items 1 and 2 CLOSED to depth; item 3 honestly recarried (no probe made).**

#### ITEM 1 — 8btc era boards: CDX-MAPPED + three era windows mined to reply-depth. [§33: killed -> docs/graveyard.md era_crossvenue_fiat_premium_arb 5th instance]
- **BOARD MAP (OP-034 step 1, durable):** 993 archived `forum-*` URLs; board 2 = 比特币论坛 (main BTC,
  max archived page 1009 — THE era ground), 43 = 竞争币/山寨币 (166), 82 = 币界主版 (1000), 233 =
  **BitMEX board (1000 pages — 合约党 era, unmined)**, 61 = 区块链 (1000), 39 = 挖矿, 147 = BCC, 186 =
  EOS, 65 = 综合区, 163 = 读书会, 118 = 链友活动, 143 = Bytom, 229 = Bibox. Titles decode gb2312
  (OP-033). Board-2 capture density lands EXACTLY on era pivots: 2013-09..12 (33 captures), freeze
  spring 2017-02..06 (~21), 94 exodus 2017-09..10 (32).
- **ERA-SEEK METHOD NOTE (feeds OP-021/034):** for a dead board, era-seek by CAPTURE TIMESTAMP of
  page 1-9, not by deep-page offset — a 2017-09 capture of page 1 IS the 94-era thread list. Deep
  pages at late timestamps show the *founding* era instead (2013-12 capture of page 26 = 2011-12
  Bitcoinica/Pirateat40 lore, low value).
- **4 threads mined to reply-depth ≥2 (GBK, both template eras parsed):** 50730 (freeze-era 30% LTC
  spread, depth-4 chain), 74908 (94 diaspora decision, 29 posts/2 pages), 75923 (HK Bitfinex exit
  rail), 72814 (banzhuan under exodus load). → **graveyard 5th instance** of
  era_crossvenue_fiat_premium_arb with the family's missing variable: **barrier SIDE sets premium
  SIGN** (coin leg frozen → domestic DISCOUNT, spring 2017, LTC −30%; fiat leg frozen → domestic
  premium) + venue-side latency detail (Bitfinex hot-wallet depletion 09-10) + primary-source
  diaspora record (retail→wallet hodl; traders→B网/Bitfinex-HK; size→USD quota, never returns;
  **承兑商 network observably BORN in-thread 09-16/17**; GFW exchange-block dated 2017-09-20).
- **UNREADABLE (zero CDX captures, do not re-find):** thread-73564 (承兑商 birth thread proper),
  thread-50836 (国行差价1200). Same class as chainnode post/70078.
- **NEXT-RUN CANDIDATES:** thread-73825 (Bitfinex BVI structure explainer, 2 full captures,
  cross-referenced twice); board 233 BitMEX 合约党 era; 2013-12 ban reaction (needs the 302-retry
  with -L on 20131225 forum-2-6).
- LEXICON: +12 rows (郭嘉/辣条/内盘外盘/B网P网果盘/央妈/被墙/提币提现/转外网/结售汇/搬砖砸脚), all
  era-text-confirmed. OP-033 addendum: per-POST charset failures + dual date-markup template eras.
- Wayback ops note: ~1/3 of id_ fetches 000/302 on first try; sequential + 8s backoff recovers all
  but two 302-looping captures (20170911 forum-2-1/2 — alternate timestamps exist, not chased).

#### ITEM 2 — OP-001 chain on CN quant repos: one false falsification REVERSED + Gitee access map. [§33: killed -> docs/graveyard.md ltw2022_crypto_momentum_nonreplication_claim] [§33: wired -> docs/research/search_operator_library.md OP-047+OP-048]
- **Chain A (GitHub, mined to OP-001 depth — README→blogs→code→issue thread→all 8 forks→both
  commenters' profiles):** `YungFuu/Cryptocurrency-trading-strategy-replication` (39★, HKU course) —
  the only public CN replication of **Liu-Tsyvinski-Wu (J. Finance 2022)** crypto size/momentum
  factors. Surface reading = "momentum fails to replicate" (author + an independent second
  replicator in issue #1). CODE FORENSICS REVERSED IT: momentum binned with `pd.cut` (equal-width
  on fat tails → outlier detector), size with `qcut`; selection helper fits bin edges on the pooled
  panel (look-ahead); author's stated method is post-hoc sign selection. → graveyard row kills the
  CLAIM (evidence about nothing, either direction), OP-047 generalises the check, and the second
  replicator's EW/VW significance-flip survives as weak signal `ltw_ewvw_significance_flip` (with a
  named promotion check: audit desk crypto_xsec weighting VW-vs-EW). Forks: all 8 = same-day
  classmate snapshots, ZERO diverged — chain honestly exhausted. License=None → no code reuse (§13).
- **Novelty-gate kill made explicitly (no card):** Alpha101/191-on-crypto factor batteries
  (popbo/alphas 572★ etc.) = the price-formulaic family the desk's 420/0 campaign already refuted;
  re-testing would burn multiplicity budget on graveyard ground. Named so no future CN run re-finds
  it as "opportunity".
- **Chain B (Gitee ground): four-route probe → OP-048 access map.** robots clean (no Claude block,
  crawl-delay 1, /api/v* disallowed); API v5 search = silent empty anon; so.gitee.com search = 401
  anon (Indexea widget, id public in bundle); /explore + /search = nox JS-challenge 405; **repo
  landing pages = 200 with browser UA**. Verdict: discovery-walled, content-open — discover via
  Baidu `site:gitee.com` (OP-002) or GitHub-side, read on site. Wayback holds explore taxonomy
  2021-2025: NO crypto-quant category exists (`quantum` = quantum computing). Not a §13 refusal;
  re-probe quarterly.
- vnpy lineage note: crypto gateways live in **veighna-global** (VeighNa Evo: vnpy_okx 173★ active
  2026-06) — engine code, not alpha; low conversion prior; not carded.
ITEM 3 (diaspora probe): **NOT DONE — recarried** (budget went to chain-A forensics; that trade was
right: a false negative entering crypto_xsec priors outprices one diaspora probe).
DEPTH LINE (per mandate, honest):
- 8btc era boards (item 1): board index CDX-EXHAUSTED (993/993 urls mapped, 39 boards titled from
  14 fetches + size ranks); era windows: 6 board-pages read, 4 threads mined to reply-chain ≥2
  (50730 to depth 4); board 233 (BitMEX/合约党, ~1000pp) surveyed only — NOT exhausted.
- YungFuu chain (item 2): EXHAUSTED — README+2 blogs+full .py+issue thread (3 comments)+8/8 forks
  (all dead snapshots)+both commenters' repo lists. Depth surfaced what surface could not: the
  binning bug (code layer) reversing the issue thread's claim (comment layer).
- Gitee (item 2): route-mapped to its floor for this box; content layer deliberately not crawled
  (discovery must come from outside; nothing yet worth fetching by path).
WHICH ARTIFACT ON DISK IS DIFFERENT BECAUSE OF WHAT WAS MINED (§33 closing question):
docs/graveyard.md (5th-instance section + ltw row), docs/research/search_operator_library.md
(OP-047, OP-048, OP-033 addendum, +12 lexicon rows), docs/research/weak_signal_registry.md
(ltw_ewvw_significance_flip), data/research_memory (3 rows: ef7ecc/fb1c64/56f118), this file.
NEXT RUN TAKES FIRST: (1) thread-73825 (Bitfinex BVI explainer, 2 full captures) + 2013-12 ban
window (-L retry on 20131225 forum-2-6); (2) board 233 BitMEX 合约党 era-seek (unmined 1000pp
ground); (3) item 3 diaspora probe (recarried twice — do it or kill it with a reason).
OPEN QUESTION CARRIED (diaspora, standing): unchanged from s1, now with the 94-era precedent that
conversion moved to PRIVATE QQ/WeChat groups within 48h of the ban — the public-ground thinness is
structural, so the probe should target overseas-hosted CN communities (OKX/Gate CN boards, CN X),
not mainland mirrors.

### 2026-08-12 session (CN frontier miner) — IN PROGRESS (write-first note; updated as items resolve)
RESUME STATE: mine gate BACKLOG-CLEAR (all 22 prior cards disposed). source_backlog 08-12: 6 verify
items (BIS WP 1087 carry↔liquidation, Auer–Claessens regulatory taxonomy, stablecoin-run
conditioning, KR venue-state layer, copula stat-arb 5-min, quarter-hour clock) — all desk-level
screens or KR-region, none CN-actionable by this seat; 6 legitimacy decisions all KR/JP/vendor.
Named here, not silently skipped. Generation priors favour data_axis_watchlist (0.444) — data
surfaces hunted alongside era lore. Predecessor note (08-04) closed RUN COMPLETE; its named
next-run items are this run's items, verbatim:
1. **ERA-ARCHAEOLOGY continuation (8btc):** thread-73825 (Bitfinex BVI structure explainer, 2 full
   captures, cross-referenced twice by 94-era threads) + the 2013-12 ban-reaction window (`-L`
   302-retry on 20131225 forum-2-6). OP-034 CDX triage, OP-033 GBK, reply-chain ≥2.
2. **Board 233 (BitMEX 合约党) era-seek** — ~1000pp, surveyed 08-04, unmined. Era-seek by CAPTURE
   TIMESTAMP of pages 1–9 (08-04 method note), then mine highest-value perp-mechanics threads to
   reply-depth ≥2. This is the CN perp/funding-lore ground — closest era ground to the desk's only
   repeat-survivor family (funding/carry).
3. **Diaspora probe — DO IT OR KILL IT (recarried twice, third carry forbidden by own note):** one
   bounded probe at overseas-hosted CN grounds (OKX/Gate CN boards, Binance Square CN), verdict
   RICH/THIN/WALLED routed to the venue table; if WALLED confirms the s3 enclosure finding, the
   standing question closes with that structural answer.
STATUS: RUN COMPLETE — items 1–3 all closed to depth; blocks below.

#### ITEM 1 — CLOSED. 8btc era continuation: BVI thread + 2013-12 ban window, 4 threads to depth. [§33: killed -> docs/graveyard.md era_selfref_mark_liquidation_796] [§33: killed -> docs/graveyard.md era_crossvenue_fiat_premium_arb 7th instance]
- **thread-73825 (Bitfinex BVI profile, 2017-09) EXHAUSTED** (9/9 posts, single page, both captures
  cross-checked): the 94 exit rail explained from the CN side — BVI holding + Taiwan ops after
  Wells Fargo cut USD wires (spring 2017), "萬一交易所被關了…還有Bitfinex" a week before the ban's
  full force, and the depth payout at post #5: **"不支持人民币充值提现"** — the rail had NO fiat
  leg, which is WHY the 承兑商 network (5th instance dates its birth 09-16/17) had to exist. Plus
  offshore maker-taker vs domestic 0.2%-flat fee contrast, and Bitfinex phishing clones in the
  migration window. → enrichment (d) of the 7th-instance graveyard entry.
- **2013-12 ban window (forum-2-6 @ 20131225003502, the `-L` retry the 08-04 note owed):** 40-thread
  era board page read; 4 threads triaged mechanism-first, 3 mined to full depth:
  **thread-2352 「796离奇爆仓」** → NEW graveyard class `era_selfref_mark_liquidation_796`
  (liquidation against the venue's own unanchored last-trade; OP + moderator corroboration;
  matched-book exit failure; hedged-but-per-contract-margined kills the hedge leg; 插针 lore's
  birth class; residue = thin index constituents on tails + the both-legs lesson).
  **thread-1983 「btc-e搬砖第一站」** (full 14-reply chain incl. 2014-15 tail) + **thread-2353**
  (SAFE FX-control analysis) + **thread-1940** (赵东 1M→13M origin document) → **7th instance** of
  era_crossvenue_fiat_premium_arb: venue-credit share of persistent discounts (btc-e), the
  practitioner-voiced bots-first prior ("机器人才不愿意去"), and the DEMAND-DIRECTION variable
  (SAFE analysis documents INBOUND USD→CNY bridge demand in the RMB-appreciation era — the mirror
  of 2016-17 outbound flight; sign law now: barrier side sets who pays, net demand direction sets
  sign).
- UNREADABLE (zero CDX captures, do not re-find): none new in this window — all 4 targeted threads
  had captures (1989 top-holder-cohort thread has none; noted, low value).
#### ITEM 2 — CLOSED. Board 233 (BitMEX 合约党): size estimate CORRECTED, board fully enumerated, 2 threads to depth. [§33: wired -> docs/research/data_axis_watchlist.md card 31 rider] [§33: wired -> docs/research/weak_signal_registry.md WS-008]
- **CORRECTION of the 08-04 survey: board 233 is ~31 threads, NOT 1000 pages.** forum-233-1000.html
  renders the same thread list as page 1 — out-of-range Discuz page URLs alias to the last real
  page (→ OP-034 addendum; the board map's page counts for OTHER boards are now suspect the same
  way and must be diff-verified before any deep-dig budget is allocated on them). Board 233
  archived inventory = pages 1 (2018-07) + 1000 (2018-09), union ~31 unique threads, fully listed
  this run → **SECTION-EXHAUSTED at the board-page layer 2026-08-12** (thread layer: 2 mined, 2
  unreadable, remainder triaged low-value: shills, access complaints, flow-number reposts).
- **thread-166158 (instant liquidation on releverage, 2018-05) mined to depth:** the mechanism
  reply — mark≠last AND **"爆仓线好像要算一期的资金费率"** (liquidation line embeds the upcoming
  funding payment) → WS-008: funding-settlement-phase → liquidation clustering on the paying side
  at tails; desk holds both instrument halves (own liquidation tape + funding_clock). Lexicon:
  塞舌尔人. Era color: the 50x-minimum mock-slogan.
- **thread-172717 (1x inverse short = USD?, 2018-05) mined to depth (11 replies):** the CN crowd
  deriving inverse-perp convexity in public — linear-logic reply ("coin doubles ⇒ ruin") corrected
  by OP's TESTNET EXPERIMENT (liq price ≈ +∞), closed by the carry statement: "比换成USDT更稳定
  更省手续费…做空的资金费率会更划算" → **second, independent mechanism prior for card 31's
  COIN-M/USDT-M funding-differential panel: synthetic-dollar demand** (capital-control clientele
  → structural short flow → persistent funding skew, widening on rail barriers + stablecoin
  distrust). Genuine cross-ecosystem convergence with the EN miner's 08-12 convexity prior
  (2012 US forum vs 2018 CN forum, neither derives from the other) — recorded on the card with
  SOURCE/DERIVES-FROM. Discovery counterfactual (charter §17): LOW — the EN crowd does not read
  8btc; the demand-side clientele story exists nowhere in the NP-thread lineage.
- **UNREADABLE (zero CDX captures, do not re-find): thread-136734 (BitMEX大战796 strategy
  commentary — the direct 796 sequel, honest loss), thread-129162 (funding-sign-as-positioning,
  2018).** Same class as thread-73564/50836.
#### ITEM 3 — CLOSED (probe MADE; standing question ANSWERED structurally). [§33: killed -> diaspora probe: all three named overseas grounds probed, verdicts recorded; open CN layer = repos + era archives + platform 文库, confirmed]
- **Gate 广场: WALLED** — edge-403 on robots.txt itself (both gate.io and gate.com); cannot even
  read the access policy; no routing around (§13).
- **Binance Square CN: OPEN but THIN** — robots allows content paths + publishes a Square sitemap
  (utility paths + `*/comments` disallowed); server-rendered and readable, but the feed is
  influencer/news (and served EN content to a zh-CN request) — positioning-intelligence surface
  only, not practitioner mechanism ground.
- **OKX: NO public community layer** — zh-hans surface is official one-way content; community
  pointer goes to official X accounts.
- VERDICT (closes the question carried since s1): post-ban CN practitioner discussion at depth
  lives in private/paid enclosures (§13-unreachable, per s3), CN-language X/Telegram (API-walled
  for reading at depth), and exchange squares that are influencer surfaces. **The open CN layer
  worth mining is repos, era archives, and platform 文库 — now confirmed by probe, not inference.**
  Re-entry condition (L1.16a): a named enabling change (a new open CN board emerging; X read
  access changing; an enclosure opening its archive).
DEPTH LINE (per mandate): thread-73825 EXHAUSTED (9/9 posts + both captures); forum-2-6 2013-12
window: board page read in full, 3/4 mechanism threads mined to reply-depth (2352 both replies =
full; 1983 full 14-reply chain to its 2015 tail; 2353 zero replies — OP analysis mined; 1940
identity extracted, capture truncates the interview); board 233: board-page layer SECTION-EXHAUSTED
(31/31 threads enumerated + triaged), 2 threads full-depth (166158 8/8, 172717 11/11), 2 unreadable
named. Depth surfaced what surface could not: the no-RMB-leg detail (post #5), the funding-in-
liquidation-line mechanism (reply #3), the testnet-experiment correction (replies #2–#10), the
moderator's hedge-leg liquidation (reply #2 of 2352).
VENUE DISCOVERY (standing obligation): **btcicc.com** (dead CN board, 796-thread cross-post source
— CDX-check as era ground next run) | **coinsbbs.com** (dead CN board, the banzhuan tutorial's
"full version" host — same) | Gate 广场 WALLED | Binance Square CN THIN-open | OKX no-community.
PROACTIVE BATTERY (#3 config-vs-outcome): the 08-04 board map's page counts were CONFIG (URL
existence), not OUTCOME (content) — corrected via OP-034 addendum; every other board's count in
that map is now flagged suspect in-place. (#10 ratchet): lexicon 26→**28** verified rows; operators
library +1 addendum; graveyard instances 6→**7** + 1 new class; board-233 enumeration 0→100%.
VIDEO: 0 fetched, 0 locked — no CN video ground was in this run's three items; explicit zero per
mandate (ambiguity between never-hit and never-tried resolved: never-tried this run).
WHICH ARTIFACT ON DISK IS DIFFERENT (§33 closing question): docs/graveyard.md (new class entry +
7th instance), docs/research/weak_signal_registry.md (WS-008), docs/research/data_axis_watchlist.md
(card 31 second mechanism prior), docs/research/search_operator_library.md (OP-034 addendum + 2
lexicon rows), data/research_memory (3 rows this run), this file.
NEXT RUN TAKES FIRST: (1) **diff-verify the 08-04 board map's page counts** (boards 2/82/61 claimed
~1000pp — same aliasing trap suspect; board 2's count is load-bearing for the era plan); (2) board 2
era windows still owed: 2013-12 window has 30+ unmined board-page captures (33 in 2013-09..12);
(3) btcicc.com + coinsbbs.com CDX survey (new dead-venue era grounds found this run); (4) the
JoinQuant/BigQuant/UQER 文库 ground (carried since s3, still the largest untouched open-CN layer).
OPEN QUESTION: none carried — the diaspora question is closed above; the era grounds are now the
enumerated work queue.

### 2026-08-13 session (CN frontier miner, s8) — IN PROGRESS (write-first note; updated as items resolve)
RESUME STATE: mine gate BACKLOG-CLEAR (18 carded finds disposed; mining authorised). source_backlog
08-13: 6 pending-verification items — BIS WP 1087 carry↔liquidation, stablecoin-run conditioning,
KR venue-state layer, foreign AI-quant RESEARCH SYSTEMS (VeighNa/vnpy.alpha, Qlib), crypto grouping
map, WorldQuant BRAIN data-field catalogue. **One of these IS CN-actionable and no prior CN run has
claimed it: `Foreign AI-quant RESEARCH SYSTEMS (VeighNa/vnpy.alpha, Qlib …)` — both are Chinese-
ecosystem projects and this is the CN seat's ground.** The 08-04 note dismissed the vnpy lineage as
"engine code, not alpha, low conversion prior; not carded" — but `vnpy.alpha` is named in the
backlog as a RESEARCH SYSTEM, which is a different artifact from the gateway code that dismissal
looked at. Verification-before-cataloguing is the resume mandate's step 1, so it goes first this
run. Remaining 5 backlog items are desk/KR/vendor-level, not seat-decidable — named, not skipped.
Generation priors: data_axis_watchlist favoured (0.45 conversion), nothing starved.
ITEMS THIS RUN (bounded scope, depth maxed per item):
1. **BACKLOG VERIFICATION (resume step 1): `vnpy.alpha` + Qlib as RESEARCH SYSTEMS.** The claim to
   test is whether these carry a research-PROCESS layer (factor pipelines, label construction,
   validation harness, data-feed catalogue) distinct from the execution-gateway layer the 08-04 run
   already dismissed. Deliverables: verdict on the backlog item, licence per §13, every named data
   feed → data_axis_watchlist/universe map, process/engine patterns → improvement_inbox, and a
   graveyard/novelty check on any factor construction before carding. MINE AS TEXT, never install
   (supply-chain rule).
2. **Era-archaeology continuation, item (1)+(2) of the owed queue: diff-verify the 08-04 board
   map's page counts** (boards 2/82/61 claimed ~1000pp — the board-233 aliasing trap makes every
   other count suspect and board 2's is load-bearing), **then mine board 2's owed 2013-12 window**
   (30+ unmined board-page captures). OP-034 triage + OP-033 GBK decode, reply-depth ≥2.
3. IF BUDGET REMAINS: btcicc.com + coinsbbs.com CDX survey (dead-venue era grounds named last run).
STATUS: RUN COMPLETE — items 1 and 2 closed to depth; item 3 not started (named below, not buried).

#### ITEM 1 — CLOSED. `vnpy.alpha` mined: card 24's unread half, and its walk-forward claim REFUTED. [§33: wired -> docs/research/search_operator_library.md `vnpy-alpha-dsl`] [§33: wired -> docs/research/data_axis_watchlist.md card 24 correction]
- **THE PREMISE OF MY OWN ITEM WAS WRONG, AND CHECKING COST ONE GREP.** I took this item believing
  the backlog listed an unverified source. Card 24 is graded **verified + MINED (2026-08-11)**. But
  the residual gap was real and finer than the backlog could express: the 08-11 conversion read
  vn.py's LICENCE and then mined **only Qlib paths** (`qlib/data/ops.py`, `contrib/data/loader.py`,
  `contrib/data/handler.py`). **`vnpy/alpha` — 12 files, a full research system — was never
  opened.** A card can be honestly graded MINED while half its named subject is unread.
- **§13: MIT (Xiaoyou Chen), read from the canonical LICENSE this run**, not inherited.
- **DERIVES-FROM recorded so this is never miscounted as convergence:** `alpha_158.py`'s own
  docstring says *"158 basic factors from Qlib"*. The FACTOR SET is derived; only the polars ENGINE
  is independent. Counting this as a second ecosystem agreeing would be the GAP-#85 echo trap.
- **CARD 24's "REMAINING DIFF" #2 IS REFUTED for vnpy.alpha:** it claims these systems have *"a
  rolling walk-forward harness wired to the enumerator"*. There is **none** — zero hits for
  rolling/walk-forward/refit/retrain/expanding/fold across the entire module; it has a STATIC
  three-way split and `lab.py` is a persistence layer. **The desk's gap is real; this system is not
  evidence for it, and there is nothing here to port.** (The Qlib half was not re-tested; it stands
  unexamined, and is named that way rather than assumed.)
- **"REMAINING DIFF" #1 (the DSL) now has a 285-line reference implementation** — operator-overloaded
  proxy + `eval()`, no parser, no AST, open operator set via `register_functions`. **Copy the proxy,
  reject `eval`:** enumerated or LLM-authored expressions flowing into `eval()` is arbitrary code
  execution, and the desk's `combination_engine` is exactly such a producer.
- **10 divergences with real teeth** (full semantics in the library): negative `ts_delay` = future
  (**second independent framework ⇒ the leak rule is family-level, not a qlib quirk**); the label is
  a **different horizon than qlib's** despite the "from Qlib" docstring; `min_samples` is
  **inconsistent within one library**, so a composite returns non-null numbers computed on two
  observations while a sibling term is still null (**WS-005's shape at the feature layer**); and
  **`cs_rank` is raw 1..N, not Alpha101's normalised rank** — provable from their own
  `process_cs_rank_norm`, and inherited by **165 call sites** in their own Alpha101 port, which is
  worse in a time-varying crypto universe where rank scale moves with symbol count.
- **Processor leak surface:** the fit window is optional and defaults to the **full panel**
  (`process_replace_inf` has no fit window at all). **HONEST SCOPE: neither shipped dataset adds
  processors, so this is a latent footgun, not a shipped leak** — stated rather than inflated.
- **A STALE CLAIM WAS CAUGHT BEFORE PUBLISHING.** I drafted "the desk's causal guard is blind to
  this (R0289)". R0289's row says `implemented`, and `libs/features/validation.py:_perturbable` now
  perturbs **every** numeric/bool/datetime column. Since the guard mutates FUTURE bars and asserts
  PAST invariance, it **would** catch what vnpy ships. Corrected in place: the desk is AHEAD here.
  A recalled defect is a claim about the past, and it was one grep from being checked.
- **Also routed:** `lab.load_component_filters` reconstructs per-symbol point-in-time membership
  intervals incl. non-contiguous spells — the correct fix SHAPE for the desk's already-rowed
  `exchangeInfo`-universe look-ahead (SYNTH0801 P2-8). Not re-rowed; corroboration only.

#### ITEM 2 — CLOSED (diff-verify half). Board page counts RE-VERIFIED; my own 08-12 generalisation refuted. [§33: wired -> docs/research/search_operator_library.md OP-069 + OP-070]
- **THE 08-12 SUSPICION IS REFUTED FOR THE BOARDS THAT MATTER.** My last note flagged boards
  2/82/61 as suspect under the board-233 aliasing trap. Direct content diff on thread ids:
  **board 2 REAL** (128/128 captures >2 KB, max real page **1009**; p1000 vs p1008/1009 share
  **zero** tids), **board 61 REAL** (58/58 real, p999 vs p1000 overlap **zero**), board 82 26/26
  real but **UNTESTED** by adjacent diff — named as untested, not assumed either way.
- **THE CORRECTED RULE (OP-070), better than the warning it replaces:** out-of-range aliasing means
  **you exceeded the board's real page count** — a symptom of asking for a page that does not exist,
  not a property of Discuz URLs. Small boards alias early; large boards paginate honestly past 1000.
  So aliasing is a *binary-search probe for the true count*, not a reason to distrust counts.
- **ONE HYPOTHESIS OF MINE WAS REFUTED MID-ITEM:** I read the 24 tids shared by pages 1008/1009 as
  pinned stickies; a three-page test found **zero** recurring across all three. The real cause is
  last-reply reordering between captures two days apart. **Overlap is not aliasing — only an
  IDENTICAL set is.**
- **OP-069, the expensive one, and it hit me twice in ten minutes.** A Wayback `id_` fetch returned
  a **107-byte 503** for a record CDX sized at **25,431 bytes**; refetching the same record returned
  **236,208 bytes** of intact GBK. The 503 is **transient and PER-RECORD**, so my control —
  refetching a *different* known-good URL — was **invalid by construction** and produced a confident
  wrong answer twice (first "archived error page", then "board 61 is dead ground"). **CDX `length`
  is the free referee and OP-034 already prescribed it; this run skipped it and paid.** Fourth
  member of the false-null family with OP-033 (encoding), OP-034 (compression), OP-068 (SPA shell) —
  all four make live ground read as exhausted. **Propagated to all seats (§16).**
- **CONSEQUENCE:** the era plan built on board 2's count is SOUND, and the binding constraint on
  that ground is **capture coverage (128 pages), not board size (~1009)**.
#### ITEM 2b — MINING HALF ATTEMPTED AFTER ALL: one thread to full depth, MECHANISM NULL, and the null is the method finding. [§33: wired -> docs/research/search_operator_library.md OP-071]
- Rather than leave the gap named-but-unworked, took one bounded mining pass at the 2013-12 window.
  Board 2 page 26 @ `20131213073329` (19 captures exist in 2013-09..12). Triaged 45 threads by
  **mechanism-keyword density, not prominence** (the habr lesson): picked **thread-49
  「比特币的前途-----地下钱庄-----洗钱工具」** because 地下钱庄 (underground banks) is the exact
  fiat rail behind banzhuan — the desk's most-instanced graveyard class (7 instances).
- **MINED 9/9 POSTS TO FULL DEPTH (2012-09-22 → 09-24). VERDICT: MECHANISM NULL, recorded as a
  result, not padded into a card.** It is an ideological argument about bitcoin as a laundering
  rail and the state's response — **no arb workflow, no premium mechanics, no venue microstructure,
  nothing tradeable**. The one item with any durable value is post 3's game-theoretic read (no state
  wants to ban FIRST, because anyone can mine, so a unilateral ban means *other* countries'
  citizens accumulate the reserve — allegedly argued by a PBoC official in a journal, Sept 2012,
  fifteen months before the ban). That is era political-economy context, **not** a mechanism, and
  it is logged as such rather than dressed up as one.
- **THE NULL IS WHY IT WAS NULL, AND THAT IS THE TRANSFERABLE PART → OP-071.** A December-2013
  capture of a DEEP page returned **September-2012** threads (ids 1–66). Discuz sorts by last
  reply, so deep pages hold the STALEST threads: **the capture date is only an upper bound, and
  page depth walks backwards from it.** My own s7 note prescribed "era-seek by capture timestamp",
  which is correct for pages 1–9 and **inverted** for deep ones. Ban-window discussion needs a
  post-event capture at LOW page numbers; I fetched the opposite and got the board's oldest stratum.
  Also captured the era-correct post selector (`<div class="t_f" id="postmessage_NN">`, not the
  later `<td>` skin) and the quoted-reply double-count trap — both save a probe every future run.
DEPTH LINE (per mandate, honest): item 1 — `vnpy/alpha` read at the CODE layer in full (9 files
incl. the complete DSL, both shipped factor libraries, the processor layer and the artifact store),
plus the desk-side cross-check into `libs/features/validation.py` and the ledger that killed my own
stale claim. Depth surfaced what surface could not: the walk-forward refutation and the `cs_rank`
scale mismatch are both invisible from a README, and both change what the desk would have ported.
Item 2 — three-page and adjacent-page content diffs across three boards, with the transport failure
diagnosed rather than recorded as a null; then one thread (49) mined 9/9 posts to full reply depth.
**HONEST RESULT: no new mechanism card and no graveyard entry this run.** The one thread mined was
a genuine mechanism null, and it is recorded as a null (L1.25a: a documented empty seam is a
result). The run's yield is concentrated in item 1 and in four operators — that is what the
evidence supported, and padding it into a card would have been the defect.
VIDEO: 0 fetched, 0 locked — no video ground was in this run's items; explicit zero per mandate
(never-tried this run, not never-hit).
WHICH ARTIFACT ON DISK IS DIFFERENT (§33 closing question): docs/research/search_operator_library.md
(anchor `vnpy-alpha-dsl` + OP-069 + OP-070), docs/research/data_axis_watchlist.md (card 24 corrected
— a refuted claim struck in place, not appended around), this file.
NEXT RUN TAKES FIRST: (1) **board 2's ban-window mining, now with the RIGHT selector (OP-071)** —
this run proved deep pages return the 2012 stratum, so take a capture from just AFTER 2013-12-05
(PBoC) and read **pages 1–9**, not deep ones; 19 captures exist in 2013-09..12 and the low-page
ones are the ban-window ground. Apply OP-069's CDX-length referee from the first fetch and the
OP-071 post selector (no probe needed). (2) btcicc.com + coinsbbs.com CDX survey (carried, never
started);
(3) board 82 adjacent-diff (the one board left UNTESTED this run); (4) JoinQuant/BigQuant/UQER 文库
(carried since s3, still the largest untouched open-CN layer).
OPEN QUESTION: none carried.

### 2026-08-19 session (CN frontier miner, s9) — CLOSED (write-first note was CLOBBERED mid-run by a sibling tree reset; fully re-applied from authoring context and committed same-block — see CONCURRENCY INCIDENT below)
ITEMS THIS RUN (bounded scope, depth-maxed; backlog-verification first per resume protocol, then
the s8 NEXT-RUN queue in order): (1) card-23 stale verification listing; (2) 8btc board-2
ban-window mining with the OP-071 selector; (3) coinsbbs.com + btcicc.com survey (carried s7).

#### ITEM 1 — CLOSED. Card 23 regraded verified-clean; backlog 8→7 pending, 18→19 resolved (re-run verified). [§33: wired -> docs/research/data_axis_watchlist.md card 23 regrade]
The 08-18 dig was complete (universe map 104/105/106 checked PRESENT this run before regrading);
the grade token "MINED" is outside `source_backlog._classify`'s vocabulary so the card fail-opened
back into every cycle's verify queue. Instance fixed by regrade; CLASS routed:
improvement_inbox 2026-08-19 entry + ledger row: **OWED, NOT LANDED** — four add attempts (R0626 assigned twice, both times
swept) lost races to a concurrent raw ledger writer (the mid-merge sibling session, see
CONCURRENCY INCIDENT); the row content is durably in the improvement_inbox entry and the first
quiet session raises it against that entry.

#### ITEM 2 — CLOSED to available depth. 8btc board-2 ban window mined; OP-071 selector VALIDATED on first use. [§33: wired -> docs/graveyard.md era_crossvenue_fiat_premium_arb TENTH instance]
Capture `20131225003502/forum-2-6.html`: 35 threads, last-replied 12-04→12-07 — exactly the
notice-reaction window (OP-071's low-page rule confirmed: no probe wasted). 4 threads read to
full archived depth (1983 banzhuan cross-post; 1944 notice thread — the named-scope loophole
reply; 1950/1951 policy readings — payment-processor scope read within HOURS). 2 threads
unreadable (1989 TOP100/TOP1000 holder analysis, 1973 — zero captures; recorded in the graveyard
entry). Deliverables: graveyard TENTH instance (OKPay-reserve cross-region corroboration with the
FIRST instance's Bitcointalk side — provenance checked both ways; rail-cut-vs-announcement
timing; days-scale crowding clock; named-scope loophole), **WS-014** [§33: wired ->
docs/research/weak_signal_registry.md], card-24 schema input (NAMED-SCOPE field + announcement/
rail-cut date split) [§33: wired -> docs/research/data_axis_watchlist.md card 24, deferral
untouched].

#### ITEM 3 — TAKEN AFTER ALL (the 1983 cross-post pointed straight into it). Both venues surveyed; coinsbbs thread-120 mined to full depth. [§33: wired -> docs/research/search_operator_library.md OP-088]
**coinsbbs.com** (比特币-山寨币信息大全): ~40 boards + /archiver/ index captured 2013-12; dead by
2016 (615-byte tombstone). thread-120 (btc-e banzhuan tutorial): all 8 pages / 70 posts read —
payload behind a 回复可见 gate = STRUCTURALLY UNARCHIVED (guest-view captures). The mine inverts
to metadata: 70 unlock-attempts in 9 days during ban week = demand meter; replies yield the Dec-7
spread-collapse datum ("MT大跌，说好的差价呢") + admin's retail-flight read (12-08 "吓退了不少
大妈") + closed-QQ-group distribution ("绝密" 搬砖群). thread-183 (advanced tutorial, "another
unknown banzhuan site") member-gated even to the crawler — venue name unrecoverable, honest null.
Registered as **OP-088** (5th false-null family member) + OP-069/OP-071 field notes (0-byte
id_-fetch artifact; td|div selector drift). VERDICT: ARCHIVED-RICH-GATED — metadata mine, payload
only via cross-posts.
**btcicc.com** (比特国际中文网): 2013-14 stratum REAL, domain REUSED post-2019 (2025 captures =
corporate squat — era-scope the CDX before grading). Article layer UNGATED: mostly reposted news
(238/240/248 title-scanned) but carries ORIGINAL 高级搬砖系列 tutorials — article-237 = the
complete CNY onramp workflow (银联→rchange.net HK→OKPay CY→BTC-e; KYC 1-2d + English
translations; float ceiling named by the author). VERDICT: RICH for the 教程/系列 slice; hunt
series continuations, skip the news reposts. Both venue verdicts + universe-map-grade detail in
research_memory rm-20260819T020436-a4abfa.

**LEXICON (+4 rows, landed in the library table):** 抄币 (pre-炒币 era orthography, 2013-12
admin usage), MT (in-era MtGox key; 门头沟 post-dates the collapse), 搬砖群/板砖群 (closed QQ arb
groups, "绝密" by 2013-12 — finds the public recruitment threads), 回复可见/隐藏内容/阅读权限
(gate MARKERS as search operators — OP-088's discovery inversion).

**VIDEO: 0 fetched, 0 locked** — no video ground in this run's items (text archives throughout);
explicit zero per mandate (never-tried this run, not never-hit).

**DEPTH LINE (honest).** coinsbbs thread-120: reply-chain EXHAUSTED (all 8 archived pages, 70/70
posts, quote-dedup applied). 8btc ban-window: 4 threads to full archived depth (their reply
chains are shallow — 1-3 replies — because the capture is 2-4 days post-thread; the depth IS the
window). btcicc: 1 article deep-read + 3 title-scanned (survey grade, not exhaustion). Board-2
page-6 SECTION: the 35-thread tape is now mapped with 6 threads read, 2 unreadable-named; NOT
claimed exhausted — 27 titles remain, mostly news reposts by title, ban-window originals
prioritized first. Breadth-theater check: 3 reply chains ≥2 mined, 1 cross-venue chain followed
(8btc→coinsbbs→btcicc), 0 fork/citation chains (no repos in scope this run).

**CONCURRENCY INCIDENT (4th recorded R0423-class instance, NEW twist).** Mid-run, a sibling
session in this shared tree reset the working copy (its unpopped `git stash` "pre-merge desk
state 0953" is the mechanism visible in `git stash list`) and swept EVERY uncommitted edit of
this session — Edit-tool writes and bash appends alike — plus the first ledger add (R0626,
dropped by the concurrent ledger union-merge c0d7cde5; FOUR add attempts lost the race even after flock
7f7ceb07 landed — the writer bypasses the CLI (raw whole-file writes). Worse: the ledger was
caught MID-TRUNCATE twice (0-byte file), one race committed an EMPTY ledger (b224a897, reverted
1d3bcff0 via git hash-object index staging — clobber-immune), and a torn-tail corruption was
truncate-repaired (0 of 624 rows lost, tail row verified duplicated in prefix). The ledger row
is OWED; content preserved in improvement_inbox). Only the last post-reset edit survived. Everything was re-applied from the
authoring context and committed in the SAME bash block as this note. Lesson unchanged from the
standing one (commit within minutes; explicit paths; verify from `git show HEAD:`), plus the
twist: a sibling's stash can eat BOTH write channels at once, and the author's context is the
only recovery path — so the write-first note must COMMIT first too, not merely exist on disk.

**WHICH ARTIFACT ON DISK IS DIFFERENT (§33 closing question):** docs/graveyard.md (TENTH
instance), docs/research/search_operator_library.md (OP-088 + 2 field notes + 4 lexicon rows),
docs/research/weak_signal_registry.md (WS-014), docs/research/data_axis_watchlist.md (card 23
regrade + card 24 design input), docs/research/improvement_inbox.md (+1 with ledger row),
docs/research/recommendation_ledger.json (truncate repair + empty-commit revert; row itself OWED), data/research_memory rows
rm-20260819T020435-{7b9f2b,ff957f} + rm-20260819T020436-a4abfa (gitignored store, host-local),
this file.

**NEXT RUN TAKES FIRST:** (1) **the 2014-03-28 crawl of 8btc board-2 pages 2–10** — a full
low-page sweep captured DAYS before the April-2014 bank-account cutoff wave: the second rail-cut
window, same selector, zero search cost (timestamps in this run's CDX pull: 20140328{060123,
073358,064252,065546,071409,070426},20140310045720,20140328054046). (2) **btcicc 搬砖系列
continuations** — enumerate article-N captures (125–187 range, Aug-2014 crawl) for 系列二+ and
other original tutorials; the ungated-payload exception makes this the highest-yield era slice.
(3) OP-088 discovery inversion on 8btc: hunt 回复可见+教程 threads via CDX title scan → cross-post
recovery. (4) board 82 adjacent-diff (carried from s8). (5) JoinQuant/BigQuant/UQER 文库 (carried
since s3, still the largest untouched open-CN layer).
**OPEN QUESTION carried:** none.


## SESSION NOTES — RU frontier miner

### 2026-08-04 session 1-on-this-branch (RU frontier miner) — IN PROGRESS (write-first note; updated as items resolve)
BRANCH CONTEXT (read this before judging continuity): this working tree forked from master at
3bf89cd (07-29). RU seat s1 (2026-08-01) was written to the DIVERGED master ledger and is NOT in
this tree; its laws are carried here by seat memory: (a) BARRIER MIGRATES — never hunt a
friendlier jurisdiction, its premium is already zero; (b) RU premium axis CLOSED — OFAC-sanctioned
venues are a charter s13 HARD STOP, never a data source, never carded; (c) crypto statarb capacity
$3–11k/pair sits in our band; (d) OP-039 (habr comments API) exists on master — referenced by
master id, never renumbered here; new OPs on this branch number from OP-049 (per the CN-s3/EN-s4
fork convention at library line ~536). Pre-fork RU state in THIS tree = cyberleninka.ru API row in
universe map + the арбитраж=arbitration lexical trap (OP library line ~300). At merge: union +
renumber-once, ratchet-max.
BACKLOG (resume mandate step 1): 0 pending technical verification. 3 pending LEGITIMACY/POLICY
decisions (Upbit Historical portal, Glassnode/CryptoQuant vendor-replacement, NAVER DataLab) — all
KR-ground/vendor-spend licence questions; ROUTED to the KR seat (licence reading in Korean) and
the desk brain (vendor spend is principal-gated), not decidable from the RU seat. Not silence:
routing recorded here.
ITEMS THIS RUN (bounded scope, depth-maxed):
  1. bits.media ERA-ARCHAEOLOGY (dark-forest #1; region era target). Wayback CDX map per OP-034
     (propagated from EN s4 — charter s14 parity in action) + OP-033 windows-1251 decode
     discipline. Hunt: pre-sanctions LocalBitcoins/EXMO era premium+arb mechanics, MM lore,
     exchange-microstructure notes. STATUS: DONE (this run's slice; ground NOT exhausted).
     RESULT: the era ground is forum.btcsec.com (btcsec.com renamed bits.media 2015; successor
     forum.bits.media LIVE, robots `User-agent: *` only — s13 PASS both). CDX: 48 pages, 1,570
     unique 200-status topics, IPB3 UTF-8 (NO 1251 trap). 283-topic trading shortlist →
     data/btcsec_trading_topics.json; universe map row 90-ru-btcsec-forum-wayback-corpus.
     3 threads mined to reply-depth → 2 graveyard instance-appends: era_grid_ladder_vol_bot
     SECOND INSTANCE (topic 5499 MensFreedom "временной арбитраж" corridor bot — retail restates
     short-gamma in one sentence; NEW failure mode: correlated infra outage, bot server died
     during the move); era_crossvenue_fiat_premium_arb SIXTH INSTANCE (topic 1987: Sep-2013
     fee-ladder primary numbers, ~12% route dispersion, immediacy rent 3-4%, multi-hop beats
     direct; ANCHOR FACT: RU exchangers priced off Bitstamp not BTC-E/Gox; topic 4083 post 3:
     Gox untradeable to RU retail 6wk pre-collapse; "физически мы не в РФ" = jurisdiction-arb
     business model, 2013 ancestor of post-2022 P2P rails). OP-030 finding: `arbitr` = ZERO slug
     hits in 1,570 topics — RU arb lore titles itself обмен/биржа/бот, never арбитраж.
  2. DIASPORA (dark-forest #3, standing question): 2022 sanctions-exodus — where did the RU crypto
     crowd GO (P2P/USDT rails, which platforms, which languages). s13-clean framing: public
     threads only; sanctioned venues are never carded as sources; the deliverable is mechanism
     knowledge + new PUBLIC grounds, not sanctioned-venue data. STATUS: ANSWERED (primary
     evidence, forum.bits.media live sections 74/166/110, 2026-08-04):
     (a) THE COMMUNITY SPLIT IN TWO. The TRADING crowd went OFFSHORE-VENUE, RUSSIAN-LANGUAGE:
     Binance/Bybit/OKX/MEXC (+DEX), tooling = Telegram bots + TradingView-webhook bridges +
     self-hosted open-source terminals (section 110 census). Language stayed Russian; venues
     left. The FIAT-RAIL crowd became an obnal-services industry (section 74 census): USDT-TRC20
     as settlement unit, Telegram-bot interfaces, corridors RUB/TRY/KZT/INR/AZN/PKR/SAR/AED +
     cash Moscow/Asia/Turkey, geography Minsk/Brest/Warsaw/TH; ads price "AML < 25%", "чистка",
     mixers, no-KYC QR-СБП payment processing. That layer is s13-UNTOUCHABLE (illicit-adjacent,
     invite-only "закрытые площадки" carry the size) — recorded as structure, never as source.
     (b) POST-2022 BARRIER IS DOUBLE: domestic (CB RF classifies crypto txs as card-block
     grounds → "самые живучие карты" threads, СБП limit engineering, дроп/mule infra) plus
     external (SWIFT cutoff, sanctions). Confirms the barrier-rent law from the 2013 sixth
     instance: rent collectors sit outside the barrier's jurisdiction (2013: "мы не в РФ";
     2022: Telegram bots + Warsaw/Dubai corridors). The RU premium axis stays CLOSED (OFAC s13
     hard stop, per master-ledger s1) — nothing here re-opens it; the measurable residue is
     structural knowledge, not a series. (c) WEAK SIGNAL routed: sanctions-rail tech resold as
     generic gray-payments processing across EM corridors (TRY/INR/PKR/EGP/KRW in one ad) —
     barrier-rent infrastructure is now a productized EXPORT, so premium magnitudes across EM
     should converge toward the productized rent floor; logged to weak_signal_registry.
     (d) Funding-arb commoditization visible in RU retail too (Axiona "funding mechanism"
     platform, section 110) — third regional confirmation of the crowding evidence.
  3. (stretch) habr.com quant long-reads at comment depth via the two-step comments endpoint
     (library line ~202). STATUS: SWAPPED for a higher-ROI in-session find (recorded, not
     silent): section 110's code-included practitioner thread topic 2130528 "Аукционная теория
     в коде" (Volume Profile / POC-retest 1h state machine, GitHub source, cross-posted from
     Habr — so this IS the habr genre, reached via the forum). Mined to reply depth (6 blocks).
     → prospector_watchlist.md card (novelty-clean vs graveyard; named defect: daily
     walk-forward coin selector = selection on 3-15-trade noise across 100 coins, coin-level
     twin of `crowdsourced_backtest_selection_fund`; engine must be tested SEVERED from
     selector). Free reply-layer prior harvested: 20-yr practitioner null on volume-profile
     extraction. GENRE-EVOLUTION finding for source-weighting: RU retail practitioner content
     now ships causal engines, same-code-backtest/live, pessimistic tie-breaks, stated
     limitations — the "pink backtest" tell is obsolete; audit must move to meta-level defects
     (selector multiplicity, param-search trial counts, affiliate venue economics — BingX
     execution choice smells sponsored). Full habr sweep remains OPEN ground for next run.
DEPTH LINE (mandate report): topic 5499 reply-depth 20/20 posts (debunking replies harvested);
topic 4083 reply-depth 20 posts (the load-bearing fact was reply #3, not the OP); topic 1987
reply-depth 20 posts (fee-ladder was reply #4); topic 2130528 OP 20.7k chars + all 5 replies;
sections 74/166/110 censused title-layer (25 threads each) — census WAS the instrument for
item 2 (see OP-049). Forks/citations: GitHub repo noted in watchlist card (not fetched — next
run: repo + Habr author page per OP-005/OP-013). Zero-hit checks: `arbitr` 0/1570 slugs
(OP-030 lexical-zero verified: RU arb lore titles itself обмен/биржа/бот).
PROACTIVE BATTERY (moves run): #2 ADJACENCY — the EN-seat's era grid-bot + barrier-rent classes
were hunted deliberately in RU ground and found (2 instance-appends; one fix-shape, all
regions). #9 SCOPE-THE-NEGATIVE — Wayback 0-byte fetches were the ROUTE (missing curl -L on
302-to-canonical-ts), not the capability; OP-034 footnote added. #3 CONFIG-VS-OUTCOME — s13
verdicts cite fetched robots.txt artifacts (both domains), not assumptions. #8 NEGATIVE SPACE —
live-successor-board census (nobody had read the CURRENT P2P board as data; it answered the
diaspora question in one fetch). Moves producing nothing: #5 COST-INVERSION (nothing paid
touched this run — vendor-decision items routed to KR seat/brain).
NEXT RUN (in order): (1) 280 unmined shortlist topics in data/btcsec_trading_topics.json —
work obmen/birzha class first (barrier-rent instances compound); (2) cryptomaniac_dt GitHub
repo + Habr author page (fork/citation chain per depth mandate); (3) smart-lab.ru algo section
(never touched, robots unread); (4) MMGP forum era-archaeology (untouched region era target);
(5) habr full sweep via comments endpoint (master OP-039).
PUSH RECORD (L1.37 --no-verify, sanctioned): pre-push fence execs scripts/run_law_gate.py which
does not exist on this forked branch (ENOENT verified by running the hook manually — same class
as EN s4's 08-04 record; the law gate lives on master, 419 ahead). Pushed ccfa013 + priors with
--no-verify per the standing fork corollary; nothing was bypassed that exists here to run.

### 2026-08-12 session 2-on-this-branch (RU frontier miner) — COMPLETE (write-first note, finalized end of run)
BACKLOG (resume step 1): 15 pending-verification items are ALL cross-desk mechanism/vendor items
(BIS WP 1087, Auer–Claessens taxonomy, stablecoin-run conditioning, KR venue-state, copula
stat-arb, quarter-hour clock) — none is RU-ground; owned by the research organs / KR seat per the
08-04 routing note above. Recorded, not silence. §33 header this run: backlog clear, mining
authorised.
ITEMS THIS RUN (bounded scope, depth-maxed; drawn from the 08-04 NEXT RUN queue in order):
  1. btcsec shortlist continuation — obmen/birzha class FIRST (159 unmined of 283 trading-tagged;
     data/btcsec_trading_topics.json). Bounded slice: 4-6 threads to reply depth, length-ranked
     per OP-034; hunting barrier-rent PRIMARY NUMBERS (fee ladders, deposit-premium structure)
     + venue-microstructure lore (btc-e anomaly threads). STATUS: DONE — 6 threads to full
     depth (3426, 6157, 5848, 2047, 4382, 8115; extractor hit OP-034 trap 3 mixed-quote markup,
     fixed in-run). YIELD: (a) barrier-rent EIGHTH INSTANCE [§33: killed -> docs/graveyard.md
     era_crossvenue_fiat_premium_arb 8th instance]: demand-direction sign variable PRICED ON ONE
     DEALER'S MENU (RUB-codes IN pays customer +1..3% premium, RUB OUT charges 7%, USD codes
     near-symmetric — the CN 7th instance's variable, on a price list), legal capacity cap
     (15,000 RUB e-money single-payment law + tiny dealer floats = rail capacity bounded BY
     CONSTRUCTION, §42's too-small-for-funds ground in 2013 form), fraud-premium term in the
     rent decomposition, rail-share census (60% QIWI / 20% Sber), EXMO launch-day fee schedule
     (2.5%/side vs 0.8% private baseline). (b) WS-009 [§33: wired ->
     docs/research/weak_signal_registry.md]: BTC-E public tape is DISPLAY-ROUNDED (trades print
     at prices absent from the book; venue API returned rounded fills), has a HIDDEN MT4-bridge
     order channel invisible in public depth, and NO history API existed — an era-tape
     provenance prior for every archived pre-2017 tape the moat ingests. (c) WS-010 [§33:
     wired]: vendor strategy-FILE monoculture (identical rule-tables mass-distributed, group-buy
     складчина distribution) syncs retail flow at encoded thresholds; modern echo = copy-trade/
     signal-channel monoculture. (d) catalog updated [§33: wired -> data/btcsec_trading_topics.json
     mined 9/283, 274 remain].
  2. cryptomaniac_dt chain (owed from the 08-04 watchlist card, depth mandate): GitHub repo +
     Habr author page per OP-005/OP-013 fork/citation discipline. STATUS: DONE — chain CLOSED
     and it widened: live topic → github.com/roman-boop → 50-repo profile sweep (Dec-2025..
     Aug-2026, all strategy code public). FINDS: (a) bybit-trading-on-delistings +
     bybyt-tokensplash-long = EXECUTABLE-tier practitioner code for §42's NAMED ground
     (delisting unwinds / day-1 listings): telethon on @Bybit_Announcements + Binance CMS parse
     → short mentioned perps at announcement latency. Mechanism EV-GATED THIS RUN [§33:
     screened -> docs/research/prospector_watchlist.md delisting_announcement_unwind_window]:
     EV 0.0013 < 0.002 HONEST REJECT at prior (crowded_known, thin-by-selection capacity);
     measurement trigger named = universe-map row 44 verify, which now carries the CONCRETE
     collector routes from this repo [§33: wired -> data/data_universe_map.json row 44]. The
     listing-side twin is already desk-owned (listing_events.py pre-registered — no new trial
     burned). (b) BingX-affiliate tell CONFIRMED (4 BingX tooling repos) — the 08-04 card's
     venue-economics suspicion is now documented fact, raising the sponsored-content discount
     on the whole genre. (c) aggregator-of-aggregators pattern: his event bots parse OTHER
     Telegram bots' output (a bot parsing a bot-parser) — the retail event-reaction chain
     stacks ≥2 latency hops, which LENGTHENS the exploitable window for direct feed readers.
     (d) NEW VENUE GROUND recorded: @crypto_maniacdt YouTube channel (video walkthroughs of
     each repo), Habr author page + Yandex Dzen (volume.py "для яндекс дзена" — Dzen hosts a
     RU quant-content layer the desk has never touched), quikpy-grid-bot- (MOEX/QUIK retail
     algo layer — RU stock-market tooling community, out of tradeable scope, in scope as
     process/data ground). thirdeye_strategy_algo ("350%/yr backtest" BARE_CLAIM + code =
     cheap-to-refute EXECUTABLE) noted for a future run, NOT carded (bounded scope).
  3. (stretch) smart-lab.ru algo section FIRST TOUCH: robots read, then census. STATUS: DONE
     (first pass; ground NOT exhausted). robots.txt fetched: `User-agent: *` disallows only
     /r.php + /blog/offtop/, NO by-name AI blocks — s13 PASS (named blocks are SEO crawlers
     only). /algotrading/ title census (30 links): verdict RICH-BUT-VENDOR-HEAVY — dominated by
     autofollow/track-record vendors (AITRUST/ABIGTRUST/CGT/Trading Bot PRO weekly-results
     genre), loose moderation (spam present). BUT: (a) cryptomaniac_dt cross-posts HERE too
     (1335751 = supply_demand, 1335689 = trendline_bot) — smart-lab is his FOURTH surface;
     cross-region convergence dedup: forum/Habr/YouTube/Dzen/smart-lab sightings of this corpus
     are ONE source (provenance discipline, GAP #85 class). (b) three depth targets named for
     next run: 1336741 ("downloaded 30y of history in an evening, spent half a year fixing the
     data" — data-quality war story, process-mandate material), 1335532 ("built a platform that
     REJECTED all 231 of my strategies — the project's best result" — a retail practitioner
     independently landing on the desk's own 420/0 discipline; mine his gauntlet design),
     1335574 (independent tick-level refutation of a sold MQL5 scalping robot — free graveyard
     genre). Also 1338486 "Арбитражные пары в криптоактивах на рынке РФ" — RF-onshore crypto
     instruments (MOEX layer) — new seam.
VENUE DISCOVERY (standing obligation, recorded for inheritance): NEW — Yandex Dzen quant-content
layer (roman-boop's volume.py is "для яндекс дзена"; Dzen hosts RU retail-quant long-reads the
desk has NEVER touched; discovery route: repo description) | first-pass verdict UNTOUCHED-RICH?
(unprobed). NEW — @crypto_maniacdt YouTube channel (video walkthroughs paired 1:1 with repos;
route: repo README) | video ground, transcript-fetchable next run. NEW — MOEX/QUIK retail algo
community (quikpy ecosystem; route: repo sweep) | out of tradeable scope, in scope as
process/data ground. smart-lab.ru | RICH-BUT-VENDOR-HEAVY (above). VIDEO LINE: 0 fetched, 0
locked this run — no video dug (YouTube channel found and NAMED as next-run ground; honesty
per the video mandate: the zero is a not-tried zero, not a blocked zero).
DEPTH LINE (mandate report): 6 era threads mined at full capture depth (16-20 posts each,
quote-chains preserved; the load-bearing facts were reply-layer AGAIN: +1% premium verification
in 3426 reply 6, taker-only design rationale in 4382 reply 6, rail-share census in 5848 reply
16, MT4-hidden-channel in 8115 replies 5+9); fork/citation chain WALKED to close the 08-04
debt: live topic → author profile → 50 repos → 2 READMEs deep + sibling repos + 4th-surface
cross-post discovery on smart-lab. Zero-hit checks: none needed this run (no zero results).
Breadth-theater check: 3 items, all closed to depth or honest first-pass verdict — no
surface-touch-and-move.
PROACTIVE BATTERY (moves run): #2 ADJACENCY — the CN seat's 7th-instance demand-direction
variable was hunted deliberately in RU ground and found PRICED ON A MENU (8th instance;
cross-region instance-compounding as designed). #6 GENERALISE-THE-RULE — the fee-ladder
sign-asymmetry became an OP-049 extension (two-sided ladders as flow-direction gauges,
all regions). #8 NEGATIVE SPACE — WS-009 exists because nobody had asked what the era's
public tape DIDN'T contain (hidden MT4 channel, unrounded precision); the absence was the
finding. #3 CONFIG-VS-OUTCOME — smart-lab s13 verdict cites the fetched robots.txt, not
assumption. Moves producing nothing: #5 COST-INVERSION (nothing paid touched this run).
NEXT RUN (in order): (1) smart-lab depth targets 1335532 (the 231-rejections platform — mine
the gauntlet design) + 1336741 (data-repair war story) + 1335574 (MQL5 refutation → graveyard);
(2) btcsec 274 remaining shortlist topics — bot/strategy class next (grid/ladder instances
compound; obmen class's richest veins now banked); (3) @crypto_maniacdt YouTube transcripts
(fetch_video_transcript.py) — pair each video with its repo, hunt the stated-but-uncoded
failures; (4) Yandex Dzen quant layer first probe (robots + census); (5) MMGP forum
era-archaeology (still untouched region era target); (6) habr full sweep via master OP-039.
PUSH RECORD: see end-of-run commit; law-gate presence checked at push time per the 08-04 fork
corollary (record below if --no-verify was needed).

### 2026-08-19 session 3-on-this-branch (RU frontier miner) — COMPLETE (first leg died after item 1 + one item-2 commit; continuation session verified artifacts from disk, repaired the lost writes and a snapshot clobber, finished items 2-3, closed clean)
BACKLOG (resume step 1): 7 pending-verification items re-read this run — all cross-desk
mechanism/vendor/other-seat items (stablecoin-run conditioning, KR venue-state, BIS WP 1087,
vnpy.alpha/Qlib systems [CN s8 mined the vnpy half], crypto grouping map [desk-brain build],
bitbank candles [JP/EN ground, EN s-I already wired bitbank]); 1 policy item
(Glassnode/CryptoQuant) is principal-gated vendor spend. NONE RU-decidable — routing unchanged
from 08-04/08-12 notes. Recorded, not silence. §33 header this run: backlog clear, mining
authorised.
ITEMS THIS RUN (bounded scope, depth-maxed; drawn from the s2 NEXT RUN queue in order):
  1. smart-lab depth targets (owed from s2): 1335532 ("platform that REJECTED all 231 of my
     strategies" — mine the gauntlet design, process mandate), 1336741 ("30y of history in an
     evening, half a year fixing the data" — data-repair war story), 1335574 (independent
     tick-level refutation of a sold MQL5 scalper → graveyard genre). Reply-depth ≥2 each.
     STATUS: DONE — all 3 mined to full comment depth. YIELD: (a) [§33: wired ->
     docs/research/improvement_inbox.md 2026-08-19 RU s3 entry] Nedomolkov gauntlet (KZ, 1C
     stack, 30y/5,264-ticker PIT lake w/ 1,083 Form-25 delistings): 231 strategies → 25 pass
     naive walk-forward → 0 pass DSR-deflated (bar ≈ Sharpe 1.7 at his n); DERIVES-FROM
     Bailey/LdP + Jobson–Korkie + Aronson (checked — method ancestry SHARED with desk, not an
     independent convergence node; the 231/0 EVENT is independent). 3 routed cross-checks:
     closed-loop lake identity test (aggTrades↔klines↔funding), benchmark-superiority
     SIGNIFICANCE wiring audit (Jobson–Korkie vs the desk's once-callerless beats_baselines),
     L1.63 wild evidence (his vol×period 15-cell gate DISCRIMINATES on directional factor
     strategies — welding is edge-specific, per-family axes). (b) [§33: wired ->
     docs/research/weak_signal_registry.md WS-015] Telegram-LLM-agent retail research harness
     (3rd regional AI-quant-diffusion confirmation; crowding clock on published mechanisms →
     weeks). (c) reply-layer corroborations, classes stay CLOSED: Amihud real-but-borrow-cost-
     killed (3rd kill channel on illiquidity_premium/lit_trading_frictions_family, no re-open);
     "high IS-Sharpe = search for error" = desk 9.84 lesson from the wild; bonzamen 30y-regime-
     conflation = era-provenance discipline independently restated; VladMih broker-quote-vs-
     clean-feed = L1.5/ERM restated. (d) 1335574 MQL5 refutation RECORDED HERE, no graveyard
     entry (contended file + forex-land product the desk never touches): "Scalping Robot Pro
     MT5" (80+ sales/mo, smooth marketing curve) on REAL RannForex ticks → PF 0.60, ~79% DD,
     2,627 trades, 59% WR, avg win $0.77 vs avg loss $1.65 — high-WR/negative-skew sold-EA
     shape; Kopcap reply: even this UNDERSTATES live damage (no requotes/slippage/spread-
     widening modeled). Author admits ~30% LLM paraphrase → OP-072 admitted-rate datapoint.
     (e) NEW VENUE: tezbase.kz (KZ tech-writeup platform, Nedomolkov's architecture post) —
     unprobed. NOTE: docs/graveyard.md worktree state observed mid-run DELETING the committed
     CN-s9 tenth-instance entry (sibling clobber shape, R0423 class) — I did NOT stage or edit
     that file; content safe in HEAD at eb6b90bc; recorded so a wholesale sibling commit can
     be caught.
  2. btcsec shortlist continuation — bot/strategy class (grid/ladder instances compound;
     274 unmined of 283 in data/btcsec_trading_topics.json). Bounded slice 3-5 threads to
     full capture depth. STATUS: DONE (split across a death/resume boundary — first leg died
     after committing the graveyard entry; continuation session verified §33 from disk, found
     the routing writes LOST, and repaired them). Threads mined: 8150 (bot-vs-hodl challenge,
     21 posts / 2 pages) + 1168 (izlevinv rules corpus, 20 posts) + 6549 (1b bot lite vendor
     changelog, 15 posts) → [§33: wired -> docs/graveyard.md] era_grid_ladder_vol_bot THIRD
     instance @ f0301d75 (re-anchor-down mechanics; era's own null: grid = execution wrapper,
     timing stays human; vendor declined a free live A/B). Continuation repaired the lost half:
     WS-009 append (SECOND ERA VENUE at the fee-METADATA layer: Cryptsy fee endpoint kept
     returning 0.2/0.3 after the venue moved to 0.25%, vendor hardcoded truth against the
     venue's own API — hardening trigger NOT met, different defect layer) + WS-010 append
     (same-vendor channel WIDTH: vendor-curated strategy-file distribution across 9 venues /
     145 pairs, and the May-2014 promo demanded customers EMAIL API KEYS ⇒ vendor-held key
     registry = fleet-enumeration channel harder than shared rule files) + mined ledger
     +{1168, 6549, 8150} in data/btcsec_trading_topics.json. LESSON (this boundary, for the
     next reader): the dead run's graveyard text CLAIMED the WS routing ("routed to
     WS-009/WS-010") while the commit touched only graveyard.md — a same-run claim of a write
     is not the write; §33's artifact-postdates-find check caught it on resume.
     CONTINUATION EXTENSION (same session, slice completed at 5 threads): +4320 ("Бот для
     торговли на btc-e" — ezhrd's OWN thread: the 8150-challenged bot, author = Evgeny
     Pozharsky, FREE + paid features; mechanism from the author: sharp-dip buy / bounce sell +
     WALL-CONDITIONED order control ⇒ displayed walls had automated retail consumers by
     2013-14; reply-layer forensic catch: duplicate cancels on the vendor's own screenshot)
     and +6475 ("Трейдинг ботом или майнинг" — engine/strategy severance THIRD era voice;
     venue-risk-over-strategy-risk lore). DEPTH CHAIN from 4320 (the run's best vein):
     ezhrd.wordpress.com is LIVE in 2026, robots-clean (§13 PASS, admin-paths only) — 86
     comments 2015→2018 mined on the 2014/01/05 post → graveyard third instance grew blocks
     (e)-(h): the Bittrex VENUE-POLICY KILL (2018-01, cancel-fee/fill-ratio enforcement ends
     grid mechanics, author-stated — the class's 4th kill channel), vendor-cloud fleet
     mechanics + BTC-E→WEX seizure-week migration + Bitfinex-hack off/on, EXMO
     no-key-granularity, BTC-E nonce one-key-one-machine; WS-010 obs 3 = SECOND INDEPENDENT
     VENDOR (vendor-EXECUTED cloud fleet, synchronized by construction) → header now
     [observations: 3 across 2 vendors]; +3 RU lexicon rows (сетка/тягать сетку, фикс, депо).
     MID-RUN CLOBBER REPAIR: desk-snapshot a5c30542 (03:23Z) committed a stale graveyard.md
     over f0301d75 (02:32Z), deleting BOTH the RU third instance AND the CN-s9 tenth instance
     (6th R0423-class instance; pure-deletion diff verified) — restored from pinned f0301d75
     @ 4dd08abf, both entries HEAD-verified. NEW GROUNDS from the chain (recorded, unmined):
     forum.bits.media topic 27623 (ezhrd's FREE LIVE real-money trading chronicle from
     2017-05 — primary grid-class P&L across the 2017 mania+crash, the highest-value next
     target of this vein), bits.media topic 7990 (bot-2 thread, btcsec topic ids SURVIVE the
     2015 rename), blog.cloudbot.uk (2018+ generation), mensfreedom.ru/forum (RU bot-release
     forum, unprobed), ezhrd blog earlier posts. [§33: wired -> docs/graveyard.md (e)-(h) +
     docs/research/weak_signal_registry.md WS-010 obs 3 + data/btcsec_trading_topics.json]
  3. (stretch) @crypto_maniacdt YouTube transcripts via fetch_video_transcript.py — pair video
     with repo, hunt stated-but-uncoded failures; explicit video line owed either way.
     STATUS: DONE (honest partial — transcripts unreachable; pairing completed at the CODE
     layer). VIDEO LINE: 3 attempted, 0 fetched, 1 LOCKED (logged: OWsum6xcNvM, with a PROVEN
     RU auto-caption track via nadeko's list endpoint), 2 PRIVATE (ilSpSqKWkRg, LO2OpaMPZSI —
     withdrawn, NOT locked-class, deliberately kept out of the purchase gate per OP-089).
     FINDINGS: (a) s2's "1:1 video↔repo" ground has DECAYED in 7 days — 2 of 3 README-linked
     walkthroughs privatized; the corpus rotates free content into its BingX-referral/products
     funnel (author is a BingX partner; the READMEs are referral funnels) ⇒ mine such channels
     PROMPTLY on discovery, back-catalogs are unstable. (b) The locked video's companion code
     (habr_files) read instead: backtest models taker fees ×2 ×leverage + ATR-fraction slippage
     (above retail average) but ZERO funding accounting on a perp hold system (WS-006 class:
     absence of funding is the finding), and backtest↔live DIVERGE — RSI period 24 vs 96,
     ATR-multiple exits vs fixed 0.4% stop, Binance-data/BingX-execution venue split — the
     published backtest does not describe the live system (OP-055 family at a new boundary:
     backtest-file vs live-file). (c) OP-089 minted: 4-way failed-fetch triage
     (PRIVATE/IP-wall/route-obituary/disabled-endpoint); the private≠walled distinction
     protects GAP #26's purchase-evidence gate; false-null family now 6 members. (d) The Piped
     route family is DYING ("Piped has shutdown" served as a hollow 200) — Invidious-fallback
     engine fix routed to improvement_inbox with consumers named (R0592-adjacent).
     [§33: wired -> docs/research/video_locked_log.md + docs/research/improvement_inbox.md
     2026-08-19 entry + OP-089 in search_operator_library.md]
DEPTH LINE (mandate report): item 1 = 3 smart-lab threads to full comment depth (first leg).
Item 2 = 5 btcsec threads to full capture depth ACROSS the death boundary, then the chain
followed OUT of the forum: 4320's link layer → ezhrd.wordpress.com (LIVE, robots-clean §13
PASS) → 86 comments 2015→2018 read in full → blog.cloudbot.uk + bits.media successor threads
named. That chain is the run's yield: the slug-triage layer says NOTHING connecting 4320 to
8150's challenged bot — only reading 4320's hrefs did (discovery counterfactual, charter s17:
a slug-only or title-only miner structurally cannot find an author↔challenge pairing; the link
layer is where identity lives). Item 3 = video ground closed at the code layer with a 10-route
wall probe and a 4-way triage minted (OP-089). Comment layers: btcsec threads thin-but-load-
bearing (the 4320 forensic reply), blog layer RICH (the venue-policy kill lives ONLY in a
2018 comment — no post states it). VIDEO LINE: 3 attempted, 0 fetched, 1 locked (logged),
2 private (not locked-class). Zero-hit checks: none needed (no zero results this run).
PROACTIVE BATTERY (moves run): #8 NEGATIVE SPACE — the §33 artifact-postdates-find check on
RESUME found the dead run's claimed-but-absent WS routing (a same-run claim of a write is not
the write); #4 REGRESSION SWEEP — post-commit HEAD grep found the snapshot clobber (committed
≠ surviving; the check at run end is "does HEAD still contain it", not "did I commit it").
NEXT RUN (in order): (1) forum.bits.media topic 27623 — ezhrd's FREE LIVE real-money grid
chronicle from 2017-05 (primary class P&L across the 2017 mania+crash; highest-value named
vein) + bits.media topic 7990 (bot-2, ids survive the 2015 rename); (2) Yandex Dzen first
probe (robots + census); (3) MMGP era-archaeology (still untouched region era target);
(4) habr full sweep via master OP-039; (5) smart-lab 1338486 (RF-onshore crypto instruments
seam); (6) mensfreedom.ru/forum probe (robots first); (7) tezbase.kz (item-1 leftover).
PUSH RECORD: continuation commits 4c3019c5 / 4dd08abf / 378f62a5 / 983270f8 + close commit;
push verified at run end (see below).

## SESSION NOTES — KR frontier miner

### 2026-08-04 session 1-on-this-branch (KR frontier miner) — IN PROGRESS (write-first note; updated as items resolve)
BRANCH CONTEXT (per the RU/EN fork convention): this tree forked from master at 3bf89cd (07-29).
KR seat s1 (2026-08-01, master commit bc93838) is NOT in this tree; its laws carried by seat
memory: (a) READ robots.txt BEFORE digging — cafe.naver.com `Disallow: /` + anti-RAG prose,
blog.naver.com names ClaudeBot/Claude-SearchBot, gall.dcinside.com names ClaudeBot/anthropic-ai/
Claude-Web — 3/5 briefed grounds refuse this agent family BY NAME; a seed list is not
authorisation, a permissive `*` is no loophole, and per the fleet convention (RU btcsec ruling:
origin-domain robots governs Wayback mining too) their ARCHIVES are equally closed; (b) coinpan
Cloudflare-walled at CDN edge (OP-038 split does not rescue it); (c) velog.io + bithumb.com
CLEAN and untouched — this run's ground; (d) venue-API layer findings (Upbit announcements
5,685 events to 2017-10-24, English `trade` filter key; `first_listed_at` never `listed_at`,
42.5% differ; Upbit purges candles on delisting 6/6 — treatment group ERASED; Bithumb
assetsstatus = independent barrier regressor; GLOBAL_PRICE_DIFFERENCES 22% is USDT/BTC
illiquidity not fiat premium — split by quote currency) live on master's ledger, cited here so
this branch never re-derives them wrong. New OPs number from OP-050 (RU took 049).
BACKLOG (resume step 1): 0 pending technical verification; the 3 "pending legitimacy" items are
the KR/vendor rows ROUTED TO THIS SEAT by RU/CN/EN — resolved this run as item 1 below.
ITEMS THIS RUN (bounded per completion contract):
1. **Legitimacy-decision sweep of the 3 routed items** (Upbit portal / Coin Metrics CC BY-NC /
   NAVER DataLab). STATUS: RESOLVED — none is KR-seat-decidable, and NONE IS STUCK: all three
   carry §33 dispositions AND live GAP_REGISTER rows with owners and deadlines (#67 principal,
   rule by 08-15, both licence questions bundled one-session; #69 operator, by 08-09, free NAVER
   key). The escalation organ is driving (rerank_gaps.py cycle-stamped; register row 83 closed
   the never-ranked hole). The seat's licence-reading duty is ALREADY DONE upstream: Upbit's
   guide is translated verbatim in card #1 including the 초봉/분봉 mistranslation fix; nothing
   left to read in Korean. ONE GAP FOUND: this branch's #69 row prices the key at 1 axis;
   master-side s1 established it unlocks 3 grounds (/v1/search/blog + /v1/search/cafearticle =
   the only §13-licensed route into the two robots-hard-stopped grounds; identical errorCode
   024, settled — do not re-verify the 401 a 6th time). Card #21 on this branch already carries
   the 3-grounds line (EN synced 08-04); register row correction routed via recommendations.py
   (GAP register is outside this seat's freeze scope). [§33: n/a — no new find carded]
2. **velog.io first dig** (zero robots rules, re-verified this run; the one briefed ground never
   touched). Target: code-included KR practitioner posts — Upbit/Bithumb API mechanics, 김프
   constructions, 자동매매/펀딩비 lore; comment layer where it exists; OP-002 native queries.
   STATUS: DONE (ground OPENED, not exhausted — universe row 92). Route: keyless GraphQL
   (v3.velog.io) + SSR __APOLLO_STATE__ fallback → **OP-050** with 4 silent-failure traps
   (invalid-field empty-200; strict-AND; count=10000 no-match sentinel; stale index serving
   deleted posts — the best lead, a 2026-01 kimchi-arb-bot build log, 404'd with no Wayback
   capture: honest dead end, recorded). Corpus map: 업비트 API 486 / 빗썸 API 207 / 호가창 157 /
   김치프리미엄 55 / 펀딩비 20. 6 posts deep-read into data/velog_kr_quant_posts.jsonl (83KB):
   (a) @rivkode Bithumb 2026-02-06 mis-credit timeline → **DATA FENCE on watchlist card #4**
   (620k phantom BTC 19:00 KST, 1,788 BTC sold pre-freeze 19:35-40, FSS 02-07 — fence prints +
   stale window + barrier spike on any Bithumb leg); (b) @hansanghun Cocoa (coincoin.kr, OSS) =
   per-coin premium ROUTE OPTIMIZER → weak signal (dispersion retail-tooled; KR twin of RU
   corridor-export, logged same day independently); (c) @vividbaek CoinWhale 12-part order-flow
   stack → weak signal (CVD/OI/liq family commoditized on our own free sources; folk
   liquidation-long 45% WR self-refuted; CVD threshold 50→300 flips 50.2→60.9% — screen-grade
   priors only); (d) @papapat honest 0-for-6 falsification of KR-equity folk beliefs by a
   NON-developer via Claude Code → genre-evolution 3rd-region confirmation (audit must move to
   meta-defects; crowding rate rising). Zero tradeable cards — honest result; the value was one
   fence, one ground map, two weak signals, one operator. [§33: wired -> data/velog_kr_quant_posts.jsonl]
3. **Ppomppu era-archaeology bootstrap** (region era target; robots UNREAD — read first, dig
   only if clean; if blocked, record and fall back to bithumb.com notice archive as era ground).
   Bounded: robots verdict + CDX map as durable artifact; era windows next runs.
   STATUS: DONE (bootstrap only, zero threads mined — declared). robots: `User-agent: *` +
   `Allow: /zboard/`, NO bot-name blocks; Disallows = marketplace boards + /search_bbs.php →
   **s13 PASS for board/thread reads; site search FORBIDDEN → era-seek by post-no binary search
   is the only legal path** (OP-021 KR adaptation added). Board 가상화폐: ~190,481 posts /
   ~6,300 pages, **2014-07 → live, NO purge** (no=1..18 still served) — spans pre-mania,
   2017-12 mania (>40% premium), 2018-01 Park Sang-ki shock + real-name-law, everything since.
   The robots-clean LEGAL TWIN of hard-stopped DCInside. cp949 errors=replace (strict euc-kr
   dies). Universe map row 91. [§33: wired -> data/data_universe_map.json]
DEPTH LINE (mandate report, honest): velog = 6 posts read FULL-BODY (42KB Korean prose + code),
comment layer checked on all 6 — thin everywhere (≤4, best was 1 spam + 1 cheer): on velog the
yield is post+linked-repo, NOT comment chains (regional counter-instance to WS-003; the depth
rule holds but the LAYER differs by platform). Forks/citations: Cocoa GitHub repo + papapat's
playbook site NOT fetched this run — next-run queue per OP-001/OP-005. Ppomppu: 3 probe fetches
(p1, p6300, no=150), zero threads — bootstrap by design, not breadth-theater: the bounded
contract spent the thread budget on velog full-reads. Zero-hit lexical checks logged: 재정거래
compound 0-hit (folk term ≠ formal term, OP-030 class), 김프 collision documented.
PROACTIVE BATTERY (moves run): #2 ADJACENCY — RU's 0-byte Wayback trap generalized: velog's
empty-200-on-invalid-field is the same "route fails, capability lives" shape, now OP-050(1);
also the RU corridor-productization signal deliberately hunted in KR ground and FOUND (Cocoa) —
two regions, same day, independent instances. #9 SCOPE-THE-NEGATIVE — GraphQL body=null was the
ROUTE not the post (SSR carried it); fool030 404 was the POST not the platform. #3
CONFIG-VS-OUTCOME — every s13 verdict cites a robots.txt fetched THIS session (velog re-verified
despite s1 verdict; Ppomppu first-read); no cached verdicts (JP Cloudflare lesson). #8
NEGATIVE-SPACE — Ppomppu was on the region's era list since 07-24 and no organ had ever read its
robots; one fetch turned "unknown ground" into the region's best legal era corpus. Moves
producing nothing: #5 COST-INVERSION (nothing paid touched; the 3 vendor items resolved to
register rows, not spend). #1 CONTINGENCY named: if velog ever walls the GraphQL, the SSR
Apollo route is the standing replacement (both documented in OP-050).
NEXT RUN (in order): (1) Ppomppu era-seek: binary-search post-no → date map, land on 2017-11 →
2018-02 window (mania peak + Park Sang-ki + real-name-law), mine threads to reply-depth ≥2 —
graveyard-check each mechanism (premium family is at 6 instances; expect KR instances of the
same laws, hunt the KR-SPECIFIC residue: real-name-law microstructure, Upbit-Bithumb basis
lore, 원화마켓 vs BTC마켓 routing); (2) Cocoa repo chain (OP-001: code + issues + author's
other repos) — the premium/fee calc internals are the mechanism document; (3) velog CoinWhale-9
(capital mgmt) + @garine 김프 자동매매 series if still live (404-check first per OP-050); (4)
NAVER key status check (#69 due 08-09 — if landed, the 3 unlocked grounds change this seat's
whole frontier).
PUSH RECORD: pre-push hook expected ENOENT on this fork (law gate lives on master) — verified by
running the hook manually before pushing; --no-verify per the standing fork corollary if so.

### 2026-08-12 session 2-on-this-branch (KR frontier miner) — IN PROGRESS (write-first note; updated as items resolve)
BACKLOG (resume step 1, closed at session start, zero re-spend): (a) the one KR item in the
source-backlog verify list — **KR venue-state layer** (watchlist card #26) — was RE-VERIFIED
EARLIER TODAY by litminer run 6 (§33(8) artifact check: data/upbit_trade_announcements.jsonl
199KB / 737 rows / 2017-10-27→2026-07-31, 0 claims refuted; screen still owed, unchanged owner).
Re-probing it this session would be re-measuring a constant — recorded, not re-spent. (b) GAP
#69 NAVER key: `data/secrets/naver.json` still ABSENT (checked this session); row re-dated to
08-19 at the R0300 re-price, human step, "do not re-verify the 401" honored — nothing
seat-actionable today. (c) mining authorised (no data/mining_suspended).
ROBOTS (fetched THIS session, no cached verdicts): ppomppu.co.kr `User-agent: *` + `Allow:
/zboard/`, no bot-name blocks; Disallows = marketplace boards + /search_bbs.php + utility paths.
가상화폐 board reads remain s13 PASS; site search remains FORBIDDEN → era-seek by post-no
binary search is still the only legal path (OP-021 KR adaptation, unchanged from s5 verdict).
ITEMS THIS RUN (bounded per completion contract):
1. **Ppomppu era-seek: the 2017-11 → 2018-02 mania+ban window** (s5's designated first item).
   Build post-no → date map by binary search, land on the window (mania peak >40% premium,
   2018-01-11 Park Sang-ki shock, 01-30 real-name law), mine threads to reply-depth ≥2.
   The premium family is at EIGHT graveyard instances as of this morning — a ninth echo of
   "persistent premium = barrier rent" is NOT the target; hunt the KR-SPECIFIC residue:
   real-name-law microstructure (who lost rail access, what broke), Upbit↔Bithumb basis lore,
   원화마켓 vs BTC마켓 routing, 가두리 (deposit-freeze fenced-market) mechanics, era margin/
   liquidation lore on KR venues. STATUS: **DELIVERED** (see RESUMED RUN below).
2. (if room) **Cocoa repo chain** (OP-001: coincoin.kr premium route-optimizer code + issues +
   author's other repos) — else stays named next ground. STATUS: **NOT TAKEN** — displaced by the
   §33 defect below, which outranked new ground (L1.28b: conversion before new findings). Stays
   the named next ground.


**§33 dispositions (2026-08-18, owed-work batch3 — items above, in order):**
- Ppomppu era-seek 2017-11→2018-02: [§33: wired -> data/ppomppu_bitcoin_era_map.json + data/ppomppu_kr_era_threads.jsonl + data/ppomppu_kr_rail_corpus.json] — DEPTH LINE at :1389, artifacts on disk
### 2026-08-12 session 2-on-this-branch — RESUMED RUN (the first attempt died mid-item-1; this is its continuation, not a new session)
§33 STANDING TEST ("which artifact on disk is different because of what was mined?"):
`data/ppomppu_bitcoin_era_map.json` + `data/ppomppu_kr_era_threads.jsonl` (**NEWLY TRACKED** —
they existed on the box but were untracked; commit 5b6ff73d), `docs/research/
weak_signal_registry.md` (**WS-011**), `docs/research/search_operator_library.md` (+6 KR lexicon
rows), this note. Not "none".

**0. THE DEFECT THIS RUN EXISTS TO FIX (found while resuming, fixed first, outranked all new ground).**
The died run's card `kr_rail_state_transition_global_leg` was written with
`[§33: wired -> data/ppomppu_kr_era_threads.jsonl]` — and **both cited paths were untracked**,
caught by `data/*` in `.gitignore:11`. §33 credits an artifact ON DISK and §32 depth-parity
requires the commit: *uncommitted output did not happen*, so the card was citing evidence that
existed on this box and nowhere else. The RU seat (`btcsec_trading_topics.json`) and JP seat
(`jp_funding_clamp_census.json`, `jp_makedeco_advent_calendar.jsonl`) had already set the `!`
exception precedent; **the KR seat had not followed it.** Fixed in 5b6ff73d with the reason
recorded inline. Cost of not fixing: the era map is the ONLY legal seek index for this board
(site search is robots-forbidden) and rebuilding it costs a fresh binary search.
**Second-order finding, worth more than the fix:** the card was committed inside **d917b3c4,
whose subject is the JP miner's session** — a sibling agent working the same checkout swept my
uncommitted card into its commit. So a card can be "committed" while its author never committed
anything, and the §33 disposition then points at paths the sweeping commit never staged. A seat
that trusts `git status` clean as evidence its own output landed is reading a sibling's work.

**1. Item 1 — DELIVERED, and deliberately NOT a ninth barrier-rent echo.** The died run had
already built the ground map (post-no→date calibration, head 190,509; three era slices; 2,130-row
title tape) and 13 threads to comment depth, but wrote **zero findings** — the extraction was the
owed half. Mining what was already on disk cost zero fetches.
- **A scan-bug caught before it became a false null:** my first title-tape scan returned **0 hits
  on all 8 residue patterns**. That was my own off-by-one (I matched `r[2]`, the *timestamp*
  column, after prepending the slice key — titles are `r[3]`), not an empty ground. Re-scanned
  correctly: 46 wallet/deposit-closed, 22 real-name/bank-rail, 11 margin/futures, 3 Upbit↔Bithumb.
  Recording it because a zero from the wrong column is indistinguishable from an exhausted seam,
  and this seat's standing failure mode is exactly that (BR-miner s2, 3rd false-exhaustion mode).
- **The residue found (Upbit↔Bithumb basis lore, the note's own named target) → WS-011.** Thread
  **52389** (2018-01-11, shock day), OP + an independent commenter both naming it: the intra-KR
  spread inverted to ~140,000 KRW because **Bithumb's matching engine froze during the crash** —
  the stale venue did not fall, it stalled. Plus **5835** (~1.6% intra-KR gap as routine) and
  **6465** (Bithumb-rich in Dec-2017 vs Upbit-rich by Jan-2018 → the intra-KR sign is
  regime-dependent, not structural). **Why this is the valuable residue and not lore:** the
  confounder is *correlated with the treatment* — tapes freeze during crashes and volume spikes,
  which is exactly when premium extremes and rail-state transitions happen, so it biases the
  event window specifically instead of averaging out.
- **Verified against live desk code rather than asserted:** `libs/research/upbit_data.py:64`
  returns `{date: trade_price}` and **discards `candle_acc_trade_volume`** — the one field that
  separates "price stable" from "venue not trading" is dropped at the boundary; and
  `data/kr_perasset_premium_history.jsonl` carries **`fx_ffill`** (FX-leg staleness flagged) with
  **no venue-price-leg equivalent**. The two legs of one ratio are instrumented asymmetrically and
  the uninstrumented leg is the one the era says froze. Honest limit stated in WS-011: era
  evidence is INTRADAY, the desk series is DAILY, so this is a prior to MEASURE, not to assume.
- **This sharpens my own card's falsifier rather than supporting it.** Thread **77829**'s best
  reply — "해외 차트 고스란히 반영 되요... 봇들도 사람처럼 해외 차트 맞추는거라" (the bots just
  track the overseas chart) — says the KR book FOLLOWS global. If so, the card's KR→global
  transmission may be the wrong direction, and a measured effect could be outage-staleness. Both
  routed as adversarial context on the card, not as support for it.
- **Legality boundary, cleanly stated by the era (55701 + 77951):** "원화로 사고 원화로 출금하면
  상관없습니다" — intra-KR arbitrage was legally unencumbered; only the CROSS-BORDER leg triggered
  외환법 (Korean nationals: ~$50k/yr cap, and "virtual currency purchase" a refused declared
  purpose; foreign nationals: unrestricted inbound, unlimited outbound on source declaration).
  **Consequence for method:** the intra-KR spread sits behind the SAME capital control on both
  legs, so the barrier-rent term *differences out* — which is precisely what makes it a cleaner
  control than the KR-vs-global premium that the desk already retracted as ~73% artifact.
  Deliberately NOT carded as a ninth barrier-rent instance; it is a control-construction note.
- **+6 KR lexicon rows** (charter §16): 가두리, 보따리상, 벌집계좌, 허매수/허매도, and 한프/코프
  recorded as **SEED with gloss UNVERIFIED** rather than guessed — if those are per-venue premium
  words, the era had folk vocabulary for intra-KR dispersion, i.e. the WS-011 axis itself.
  Second-corpus confirmation of an existing row: 재정거래 hit **1 of 2,130** era titles, matching
  the velog lexical-zero verdict in a different corpus and era (the formal term finds textbooks).

**VIDEO: 0 fetched, 0 locked** — no video ground was touched this run (the item was a text
archive). Recording the explicit zero because an empty log is otherwise ambiguous between "never
hit" and "never tried".

**DEPTH LINE (honest).** Ppomppu era corpus: **reply-chain ≥2 / comment-layer exhausted on 5
threads read this run** (52389, 6465, 5835, 55701, 55357) on top of the died run's 13, plus the
full 2,130-row title tape mined by pattern. Depth surfaced what the surface could not: 52389's
*title* reads as ordinary premium chatter and only the body+comment layer carries the outage
cause; 55357's title asks why banks blocked accounts and only its 4-comment argument carries the
zero-interest-float economics. **Not exhausted, and not claimed as such** — 46 wallet/deposit and
22 rail threads from the tape remain unread, and the board's 2018-02→2018-12 tail is unmapped.
The tape itself is the reusable asset: those 68 named post-numbers are a work queue, not a search.

**NEXT UN-EXHAUSTED GROUND (in order).** (1) The 46 wallet/deposit-closed + 22 real-name/bank-rail
threads already named in the tape — direct evidence for card #26's rail-state event list, zero
search cost. (2) The Cocoa repo chain (item 2, untaken). (3) The 2018-02→2018-12 post-no range,
uncalibrated between no 85000 (2018-02-16) and 100000 (2018-12-06) — the post-ban bear era, the
cheapest remaining binary-search extension.

### 2026-08-13 session 3 (KR frontier miner) — LANDED 2026-08-19 by KR s4 (note below is s3's verbatim record from its branch; its "card #33" is now watchlist card #35 and its "OP-072" is now OP-090, both renumbered at landing after live-branch id collisions)
Own worktree `/home/quant/qp-kr-s3`, branch `claude/kr-miner-s3-20260813` (R0423: the main checkout
has 13 sibling worktrees and s2 was already swept once by a sibling's commit — not sharing again).
`.venv` symlinked from the main checkout per RU-s3's finding (a fresh worktree fails the L1.37 law
gate on `ModuleNotFoundError: pydantic`, and `--no-verify` is the wrong reach).

BACKLOG (resume step 1, closed at session start): `source_backlog_next.py --limit 6` lists ONE
KR-ground item — **KR venue-state layer** (watchlist card #26). Checked on disk rather than
re-probed: the card is disposed `[§33: screened -> data/upbit_trade_announcements.jsonl]`, and a
LIVE collector now exists (`data/kr_venue_flags.jsonl`, 586 rows, first write 2026-08-12T06:12Z,
last 2026-08-13T07:07Z). Re-verifying it would be re-measuring a constant. The other five verify
items are not KR ground. `data/mining_suspended` absent ⇒ mining authorised.

ITEMS THIS RUN (bounded per completion contract; depth per item unbounded):
1. **The 68 named rail/wallet threads in the s2 title tape** — s2's own designated next ground #1.
   Post numbers are already known, so this is extraction, not search. Target: a DATED KR
   rail-state event list for 2017-11→2018-02, i.e. the independent barrier-height regressor that
   R0299 says breaks the KR-premium circularity, for an era the live flag collector cannot reach.
   NOT a ninth barrier-rent echo. STATUS: pending.
2. **The Cocoa repo chain** (coincoin.kr premium route-optimizer; OP-001 repo-chain discipline) —
   named next ground #2, untaken twice. STATUS: **NOT TAKEN** — item 1 opened a live regulatory
   mechanism and its measurement chain, and following that to depth outranked opening new ground
   (depth mandate; L1.28b conversion before new findings). Stays the named next ground.
3. (standing, not an item) venue discovery + lexicon + data axes harvested en route.

### 2026-08-13 session 3 (KR frontier miner) — **COMPLETE** (results appended to the write-first note above)
§33 STANDING TEST ("which artifact on disk is different because of what was mined?"):
`data/ppomppu_kr_rail_corpus.json` (**NEW**, 85 threads / 334 comments, tracked via a `.gitignore`
`!` exception — the s2 defect, not repeated), `data/kr_venue_bank_rail.json` (**NEW**),
`docs/research/data_axis_watchlist.md` (**card #33 NEW** + a clock fence on card #4),
`docs/research/prospector_watchlist.md` (1 EV-rejected mechanism, logged as memory),
`docs/research/weak_signal_registry.md` (**WS-011 → 2 observations**),
`docs/research/search_operator_library.md` (**OP-072** + 벌집계좌 lexicon row enriched). Not "none".

**1. ITEM 1 — DELIVERED, and it turned out not to be era archaeology at all.**
The 85 post-numbers were already known from s2's tape, so this was extraction over a fixed queue,
not a search: **85/85 fetched, 0 errors, 334 of 454 declared comments read.**
- **THE FIND: the KR fiat rail is a REGULATORY EXCLUSIVITY, and it is still in force.** Primary,
  2018-01-30, corroborated across five threads: *"거래소마다 입금계좌는 한개의 은행밖에 안되죠 /
  업비트는 기업이고"* — **one exchange, one bank, exclusive**. Verified live: the rule is current
  2026 regulation (Upbit→K-Bank, Bithumb→KB, Coinone→Kakao, Korbit→Shinhan, Gopax→Jeonbuk) and is
  under active political challenge. So a bank-level event is a **venue-asymmetric** shock to one
  venue's KRW rail — exactly the barrier regressor R0299 wants, and the one that survives the
  intra-KR differencing s2 established. Routed as data-axis **card #33**.
- **AND IT HAS A MEASURED FOOTPRINT.** Bithumb's 1m tape has a **10.50h hole** across its
  2025-03-24 NH→KB migration (+51bp over the halt) while Upbit ran continuous. The rail event is
  visible in price data **as an absence**. → WS-011 observation 2, which **retires that entry's own
  "2017-18 reliability is not 2026 reliability" caveat** with a 2025 measurement.
- **EV GATE RUN, NOT ASSERTED: REJECT at 0.0019 (thresh 0.002), breadth-killed at ~6 transitions/yr;
  novelty 0.899.** Rejected on ECONOMICS, not as re-tested ground. **And the rejection is
  knife-edge** — breadth 8 or sharpe 0.5 flips it to QUEUE — so the verdict measures my hand
  estimate, not the world. Recorded as such, with a precise re-open condition (**≥8 transitions/yr**
  from the notice archives) rather than a pass or a kill. **NOT SCREENED, deliberately: n=1
  treatment is an anecdote with a timestamp, and L1.62 forbids certifying on an unmeasured n.**
- **What the comment layer paid for, and nothing else could have.** 76535's headline ("7 beehive
  venues cut off, >1M users") was **disputed by two named venues within 44 minutes** (76551), and a
  commenter observes the cut venues *"어차피 현금 입금 안되던 곳"* — the rail had already died quietly.
  **The announcement date is NOT the treatment date.** That fence now binds card #33's enumeration;
  an event study keyed on press timestamps would mis-date its treatment and inherit press errors as
  events. It also recovered the full primary venue list + user counts into the 벌집계좌 lexicon row.

**2. THE DEFECT I ALMOST SHIPPED, recorded because the catch is the point.** Measuring the venues'
clocks, I found Upbit dailies are UTC-days and Bithumb dailies are KST-days, and drafted it as a
find. **It is already in the graveyard as `bithumb_kr_premium_lookahead`** (named in
`libs/research/upbit_data.py:25`). The novelty gate working is not a finding. **But the check that
killed my claim also produced the real one:** the *request* parameter `to=` is **KST on Bithumb and
UTC on Upbit** — 9h apart, response fields honest UTC, no error and no anomalous value, so it passes
every provenance gate the desk owns. That is a **different fact** from the bar boundary and is not
covered by the kill. → **OP-072** ("a request parameter carries its own timezone claim, separate
from the response field — and only the response field is ever audited"), plus a clock fence on
data-axis card #4, whose selling point is precisely *"the desk's Upbit pagination code shape works
nearly verbatim"* — the sentence that makes this bite. **And the remedy widens the ground rather
than closing it:** 1m bars are honest UTC on both venues and align to the minute once +9h is applied,
so the intra-KR spread WS-011 asked for is constructible after all (L1.25a: a blocked ROUTE is not a
dead CAPABILITY).

**3. A LIVE LEAK, FOUND BY VERIFYING A CLAIM I HAD ALREADY LEDGERED AS FACT (→ F0001, R0584).**
Writing OP-072 up I asserted in ledger row **R0583** that "no repo code calls api.bithumb.com
candles". It is checkable in one command, so I checked it, and **it was false**:
`scripts/batch_premium.py:43` does. Reading it found a live instance of the leak the desk already
killed. `bithumb()` keys Bithumb 24h candles by the **UTC date of the bar's START** epoch — but
Bithumb bars start **15:00 UTC (00:00 KST)** while the Binance leg starts 00:00 UTC, so on a shared
date key **the Bithumb close sits 15h AFTER the Binance close** and the premium mechanically
contains future Bithumb price. That is verbatim the cause recorded for graveyard entry
`bithumb_kr_premium_lookahead` (IC 0.72 / Sharpe 10.0). **The axis was killed in 2026-07; the code
that manufactured it was never touched**, so any re-run re-manufactures it. Verified against the
live endpoint, not inferred. **Coinone CHECKED and CLEAN** (00:00 UTC bars) — so the graveyard's
"correctly aligned" note on `coinone_kr_premium` stands, and the day boundary is **per-venue, not a
KR rule**; I had assumed the two KR venues would match and they do not. **NOT FIXED HERE** — this
seat runs under the research freeze (docs/ + data/ only), so the exact patch is named and chased in
F0001 rather than applied. R0583's parenthetical is withdrawn in R0584.
**The generalisable half → blind-spot log:** a graveyard kill retires the **axis** and nothing links
it to the **producer** of the killed number. Ask of every graveyard entry with a mechanical cause
(leak, clock, alignment, denominator): *which file produced this, and was IT changed?*

**4. A DENOMINATOR FINDING IN MY OWN INSTRUMENT (L1.60).** Ppomppu publishes `total_comment` as a
stored aggregate that **does not decrement on deletion**, so it is an UPPER BOUND: across 85 threads,
**454 declared vs 334 readable = 26.4% attrition**, and it is not uniform (11 threads declare 0;
77938 reads 19 of 42). Both numbers are recorded per thread in the corpus rather than the readable
count alone — reporting `n_read` as the corpus size would have understated deletion by a quarter.
Also caught: my first parser returned body-and-comment chrome for every thread (the comments load
from an embedded `initialCommentData` blob + `/zboard/comment.php?cmd=get_comment_json`, not the
DOM), and **`initialCommentData` is only the LAST page** — 76535 gives 10 of 20 until page 1 is
fetched too. A parse failure and an empty board are byte-identical (OP-033/068/069 family).

**DEPTH LINE (honest).** Ppomppu rail queue: **85 threads to full comment depth, paginated** — not a
skim; the venue↔bank structure, the 농협중앙회-only detail, the 300k비대면 limit, the 44-minute
correction and the "already dead" observation are **all comment-layer or body-layer**, and every one
of them is invisible from the titles. Depth beyond the corpus: the mechanism was **carried forward
8 years** (2018 era claim → 2026 live regulation → 2025 measured tape outage), which is the chain
that turned era lore into a live axis. **Not exhausted:** 2,045 of the tape's 2,130 titles are
outside this rail filter, the board's 2018-02→2018-12 tail is still unmapped, and the Cocoa repo
chain is untouched for the third run.
**VIDEO: 0 fetched, 0 locked** — no video ground touched this run (text archive + REST APIs).
Explicit zero per the mandate.
**SCOPE HONESTY on the lexicon:** 가두리/보따리상/허매수/한프 all return **0 hits in this corpus** —
but this is an **85-thread rail-FILTERED subset**, selected by a bank/deposit regex, so a zero here
says nothing about the board. Recording the filter as the denominator because "absent from my
sample" and "absent from the ground" is exactly the confusion this seat keeps paying for.
**MECHANISM-VOCABULARY FLAG (mandate):** the conditioning variable — *venue-exclusive banking rail*
— maps to **NONE** of `CRYPTO_MECHANISMS`. Per the mandate that is the interesting case, not the
discardable one: the effect it conditions (cross-exchange spread) is in the vocabulary, the
**regressor is not**, so it widens the desk's feature space rather than re-searching it.

**NEXT UN-EXHAUSTED GROUND (in order).** (1) **Enumerate KR venue↔bank rail transitions since 2018**
from `data/upbit_trade_announcements.jsonl` + the Bithumb notice feed — this is now the single
blocking measurement for card #33 and it flips a knife-edge EV verdict either way; the
announcement≠treatment fence above binds it. (2) The **Cocoa repo chain** (third deferral — take it
before it becomes a standing skip). (3) The 46 wallet/deposit threads' **non-rail** residue and the
board's 2018-02→2018-12 tail (post-no 85000→100000, uncalibrated).

### 2026-08-19 session 4 (KR frontier miner) — IN PROGRESS (write-first note; updated as items resolve)
RESUME STATE READ FIRST, and it found the run's top item before any searching: **KR s3
(2026-08-13, commit c32ed2be, branch `claude/kr-miner-s3-20260813`, own worktree) was never
merged into this branch** — the branch every organ reads. `git merge-base --is-ancestor` says NO.
Cost of that gap, verified in this tree today: (a) the **batch_premium.py Bithumb 15h look-ahead
producer s3 found is STILL LIVE** (`scripts/batch_premium.py` `bithumb()` still keys KST-day 24h
bars by UTC start-date; the two commits that touched the file since were lint/type passes) because
s3's repair rows (R0583/R0584 on its branch) never reached the live ledger — the repair queue has
been structurally blind to a found leak for 6 days; (b) WS-011 still reads [observations: 1] here
(s3 measured obs 2: Bithumb 10.50h tape hole across the 2025-03-24 NH→KB migration); (c) s3's
card #33 (KR venue↔bank fiat-rail registry) + `data/kr_venue_bank_rail.json` +
`data/ppomppu_kr_rail_corpus.json` tracking are absent from HEAD; (d) **the OP id s3 minted
COLLIDED**: live's library now carries TWO OP-072 headers (s3's request-param timezone operator
landed by some path at one line, JP s4's LLM-contamination operator at another) and every repo
reference to "OP-072" outside the library means the JP one. A partial, referenceless landing is
worse than none — it fakes presence.
BACKLOG (resume step 1): the one KR item in the verify list (KR venue-state layer, card #26) is
disposed on disk and its successor collector is LIVE — `data/kr_venue_flags.jsonl` 3,505 rows,
last write TODAY 06:22Z, rows carry `"clock": "recv_only"` (L1.46 discipline). Not re-probed;
re-measuring a constant. `data/mining_suspended` absent ⇒ mining authorised (§33 backlog clear).
ITEMS THIS RUN (bounded per completion contract; landing owed work outranks new ground, L1.28b):
0. **Land KR s3 into the live branch** — reconciling merge in a private worktree (13 sibling
   worktrees share the main checkout; R0423 ×6). Semantic resolutions required, not textual:
   s3's card #33 renumbers to **#35** (live's #33 = VARA Dubai, #34 = bitbank order-book);
   s3's operator renumbers to **OP-090** (dedup the double OP-072, keep JP as 072 — all
   references point there); WS-011 obs 2 lands into the CURRENT registry text; the
   batch_premium repair lands as FRESH ledger rows via scripts/recommendations.py so the live
   repair queue finally sees it. STATUS: pending.
1. **s3's named next ground #1: enumerate KR venue↔bank rail transitions since 2018** from
   `data/upbit_trade_announcements.jsonl` (737 rows, 2017-10→2026-07, on disk) + Bithumb notice
   surface — the single blocking measurement for the renumbered card #35; flips s3's knife-edge
   EV REJECT (0.0019 vs 0.002) either way at the pre-stated re-open condition (≥8
   transitions/yr). The announcement≠treatment fence (s3, thread 76535/76551: headline disputed
   in 44 min, rail already dead before the notice) binds this enumeration. STATUS: pending.
2. **Cocoa repo chain** (OP-001) — deferred by s1, s2, s3; a FOURTH silent deferral would be a
   standing skip, so if this run cannot take it the deferral is named loudly with its count.
   STATUS: pending.

**RESULTS (run complete; items in order):**

**0. LANDED — merge commit 0c691dc3 (parents 4e4b62ad + c32ed2be), pushed. And the landing
tripped over a bigger heal than the landing itself.** Semantic resolutions as planned: card
#33→**#35**, s3's operator→**OP-090** (id-provenance block written into the operator itself),
WS-011 obs 2 auto-merged clean into the current registry, s3's session note landed verbatim above
with a landing header, s3's ledger rows re-minted fresh as **R0631–R0634**. EN ROUTE, found
because the ledger conflict resolution refused to parse: **the a5c30542 desk snapshot (03:23Z
today) had committed a stale tree that zeroed `docs/research/recommendation_ledger.json` — 0
bytes on the live branch for ~4 hours** (629 rows; two earlier zeroings the same morning were
caught in-session, this third one was not) — **and deleted GAP_REGISTER's 08-18 full decision
pass** (66 lines, the 67-row implement/defer/retire record). Both restored from pinned
`ac7ad0fc` and verified (ledger parses at 629+4 rows; register restoration is a pure superset of
HEAD). 7th R0423-class hit; **R0631** carries the exact producer patch demand (HEAD-parentage
check + refuse 0-byte/-50% shrink on ledger-class files + explicit paths).
**CORRECTION to this note's own item (d), because the wrong claim was committed:** live carried
ONE OP-072 (JP's). My "live's library now carries TWO OP-072 headers" misread my own tool
output — the grep that showed the KR timezone header at one line was run against the **branch's**
file, not live's. The collision was LATENT (an unmerged branch claiming a taken id), not
manifest. The repair (renumber at landing) is unchanged; the claim is corrected because a
committed misreading left uncorrected becomes a future session's false premise.

**1. ENUMERATED — and s3's knife-edge resolved DOWN, decisively. The event-study axis is DEAD on
measured breadth; the registry survives as provenance.** The enumeration's first fact was about
the desk, not Korea: **s3's stated input (`data/upbit_trade_announcements.jsonl`) structurally
cannot contain the treatment** — it is `category=trade` only (0 bank hits in 737 rows, one
`Counter()` call), while the source API serves `notice` (776 rows — every bank/rail event),
`event` (312) and ~3,900 further rows under `all`. → **OP-091** (collection-scope false null,
7th member of the family; the archive you own is only as complete as its collector's filter) +
**improvement_inbox** routing (one-line category fix for the owning organ; full notice backfill
landed this run so only the incremental pull is owed). Fetched the complete notice archive
first-party (**776/776 rows, 2017-10-24→2026-08-14**, 39 pages, 429-backoff measured ~5-page
burst allowance → `data/upbit_notice_announcements.jsonl`, tracked). Built
**`data/kr_bank_rail_transitions.json`**: 19 events, classed sharp/weak/window with
announce-vs-effective dates separated per s3's announcement≠treatment fence, sources graded
MEASURED (Upbit archive, desk-measured Bithumb 2025-03-24) vs press_dated (Coinone/Gopax,
verification owed), and the excluded classes NAMED (the ~40-row VASP counterparty-suspension
mass is a different mechanism — see WS-016). **THE RATE: ~0.9 sharp episodes/yr (8 in 8.6y);
ONE sharp episode since 2021-09** (the market consolidated). EV re-run with measured breadth:
**0.0004–0.0006 vs 0.002 threshold — REJECT, no knife-edge left** (QUEUE needed ≥8/yr = 9× the
measured sharp rate). s3's ~6/yr hand estimate was 6× the measurement because it lacked class
boundaries. → graveyard **`kr_bank_rail_event_study`** (killed on treatment scarcity — the
design, not the mechanism; the AR seat's annual-event-study lesson arriving in KR), card #35
re-graded (registry KEPT as the WS-011 tape-provenance gate; alpha use dead), re-open condition
NAMED (one-bank-rule repeal transition — watch the rule, not the venues). **R0634 disposed
implemented this run.** Bithumb's own notice archive: **WALLED from this probe origin**
(feed.bithumb.com serves 403 on robots.txt AND content, browser-UA control also 403 ⇒ IP-level
wall, not bot-name; recorded, not routed around — cross-venue lead/lag for WS-016 stays
unfetched).
**EN-ROUTE FIND → WS-016:** the same archive is a **dated counterparty-risk event stream about
OTHER venues** (~40 rows: FTX/Gate/Binance/GDAC/Haru/Delio/BingX/HTX suspensions, thresholds,
closures) — a licensed venue's compliance desk as a paid sensor on venue death; maps to NONE of
the 24 CRYPTO_MECHANISMS (the interesting case). Decisive next measurement named in the row
(do suspension rows LEAD the named venue's death date; n≈10, countable in one sitting).

**2. Cocoa repo chain: NOT TAKEN — the FOURTH consecutive deferral, and it is now a standing
skip by this note's own definition.** No excuse survives four runs: it is the FIRST item of s5,
before any backlog check, or s5 must write down what about the seat keeps displacing it (that
sentence, if written, is itself a finding about the seat's triage).

**VIDEO: 0 fetched, 0 locked** — no video ground touched (first-party REST archive + git
forensics run). Explicit zero per the mandate.

**DEPTH LINE (honest).** This run's depth was **vertical through the desk's own stack** rather
than through a forum: a merge's conflict hunks read line-by-line against three trees (base, live,
branch — the landing found the snapshot zeroing precisely because a conflict resolution refuses
to skim), a 776-row primary archive fetched WHOLE and classified row-by-row (not sampled), and
the one number that decides an axis (transitions/yr) carried from hand estimate to enumeration to
EV re-run to graveyard in a single chain. Ground NOT deepened this run, stated: Ppomppu's 2,045
non-rail titles, the 2018-02→2018-12 tail, the Cocoa chain (4th deferral, above), Bithumb's
walled archive, WS-016's lead/lag count.

**NEXT UN-EXHAUSTED GROUND (in order, for s5).** (1) **Cocoa repo chain** — 4th deferral, goes
first, unconditionally. (2) **WS-016's decisive count** (suspension-row dates vs named venues'
death dates; zero search cost, rows on disk, one sitting, L1.62 count-before-screen). (3)
Bithumb notice archive via a route this box can reach (Wayback CDX of feed.bithumb.com — OP-086
canonicalization applies; NOT a §13 route-around: Wayback's own access rules govern its copies).
(4) Ppomppu 2018-02→2018-12 post-no extension (85000→100000 uncalibrated). (5) The
`category=all` residue (~3,900 unenumerated rows — OP-091's own next application).

## SESSION NOTES — JP frontier miner

### 2026-08-19 session (JP frontier miner, s5) — COMPLETE (write-first note, finalized end of run)
§33 STANDING TEST ("which artifact on disk is different because of what was mined?"):
`docs/research/data_axis_watchlist.md` (card 28 grade-token close, commit d615cfba),
`docs/research/prospector_watchlist.md` (+s5 block: 1 EV-gated mechanism, 1 evidence attachment),
`docs/graveyard.md` (+`arkham_alert_edge`), `docs/research/weak_signal_registry.md` (+WS-017,
+WS-018), `docs/research/search_operator_library.md` (OP-072 addendum ×2 sharpenings, +7 JP
lexicon rows), `docs/research/improvement_inbox.md` (+2 engine items), this note. Not "none".

ITEMS THIS RUN (bounded per completion contract; resume order from s4's queue):
0. **Standing cheap probe — UA-matrix on note.com/zenn.dev CONTENT paths + robots on every host
   touched.** [§33: screened] RESULT: note.com 403/403 (3rd consecutive run); **zenn.dev robots
   still 200-and-permissive over a content-path 403** — the OP-052 worst case persists unchanged.
   All four target hosts OPEN to honest `ClaudeBot` UA with clean robots (rarirure.rip 200,
   blog.shidokamo.com robots-404/content-200, yard.tips 200, mirumi.me 302→200 trailing-slash).
1. **Verification lane (resume step 1).** [§33: screened -> commit d615cfba] BOTH JP-dated dues
   landing today were already closed by sibling seats: card 29 J-Quants killed 08-12; card 28
   bitbank verified + §13 LEGITIMATE + wired TODAY by EN s-I (`data/bitbank_1day.jsonl` on disk,
   R0619 owns the refresher). The residual defect was OURS to close: bitbank re-listed as
   pending-verification every cycle — the R0514/R0617 `_classify` fail-open ("verified-
   technically-clean" misses the "verified-clean" token; §33 verb `wired` not terminal). Fixed by
   the KR-s4-precedent token edit on this seat's OWN card only; parser stays engineering-owned.
   Verified post-edit: backlog parser now lists 7 pending, bitbank absent.
2. **Deep-forest queue (s4 item 1) — 5 posts read to full depth, repo chain walked 1 hop,
   contributor profiles listed.** [§33: screened; details in the s5 watchlist block]
   (a) `rarirure.rip/archives/1301` — the run's best page: a news-latency listing/delisting bot
   that corroborates the desk's pre-registered SHORT-the-pop listing hypothesis from the SUPPLY
   side (insider selling crashes perp-listing pops — BWEnews's own complaint + 「インサイダーには
   勝てない」), names キムチパンプ (KR retail) as the fill driver, and hands two collection-layer
   guards to improvement_inbox (announcement-endpoint event clock; symbol-regex variants). The
   latency race itself: DOA for this desk, uncontested drift horizons are ours. Also yielded
   `arkham_alert_edge` (graveyard, practitioner-dated) and WS-018 (airdrop instant-sell flip).
   (b) `blog.shidokamo.com` ×2 — starter-trader = the PERP-DEX TGE DIP TEMPLATE (HYPE→ASTER, two
   instances, three ex-ante conditions): EV-gated honestly to REJECT 0.0016 KNIFE-EDGE with both
   re-open measurements named (≥6 qualifying TGE windows/yr, or alpha-vs-hold on HYPE's own tape
   after a §13 read of HL API terms — universe-map HL entry still `needs-monitoring`, so no
   ingest this run). GPT post = OP-072 addendum: RLHF-consensus tilt (優等生 effect — LLM
   contamination is BIASED toward textbook consensus, so consensus-shaped convergence is the
   weakest evidence) + the INTERFACE-contamination layer (decisions human, prose contaminated).
   (c) `yard.tips` 3tomcha — THIN: TradingView-strategy reading (Squeeze/WVF/SMC-FVG); value =
   JP-retail crowding read (LuxAlgo SMC vocabulary spreading; FVG levels now folk support).
   (d) `mirumi.me` — ro-soku (MIT, Rust, multi-venue candle CLI, dormant 2023-10) + Candlestick
   Renderer; the PROCESS find is the weekly cron-CI against live venue endpoints that caught real
   spec drift → improvement_inbox item 2. Repo chain: tvbit-bot AGPL (text-only), starter-trader
   NO-LICENSE (blog grants in prose; forks 7 > stars 5 = template being cloned), rluisr's news
   fork PRIVATE. This closes the JP half-hunt of the "Foreign AI-quant RESEARCH SYSTEMS (JP/KR
   equivalents)" backlog card for the TOOLING layer: the JP layer is bot-infra (pybotters-class,
   ro-soku, tvbit-bot), NOT a Qlib-class research system — no walk-forward harness exists here
   either; the nearest research-system artifact remains J-Quants-Tutorial (equities, card 29
   killed).

**DEPTH LINE (mandate report).** rarirure 1301: full body incl. traceroutes + module list;
comment layer 0 (form only). shidokamo GPT: full body; starter-trader: full body incl. the
implementation-notes tail (partial-fill→timeout-extension quirk recorded); site has no comment
layer. yard.tips: full body; platform "相談" layer not fetched (login-gated — respected). mirumi:
full body incl. both tool sections; repo chain followed to GitHub API (licence/stars/forks/
pushed) + per-author non-fork repo listings. Era depth: none this run (living-web run); the era
target found (ヨーロピアン's DELETED 2017 Medium corpus — the community itself begs for copies,
so it is LOST ground with a Wayback route) is named below as next-run item. Video: 0 fetched,
0 locked (no video-only mechanism encountered).

**PROCESS FINDS (mandate).** (1) The 鉄火場 8-hour rule (shidokamo): in a TGE window ship the
simplest bot within ~8h, test small, improve while running — the retail statement of the
capacity-runway race (a short-runway edge is lost by waiting). (2) Folk execution randomization
is STANDARD: both shidokamo bots split orders randomly within a band; rarirure precomputes
everything but price. The desk's L1.45 excitation design operates in a market where retail
already randomizes placement. (3) Leverage-sequencing lesson: HYPE +400% virtual then large DD —
his stated fix is START levered and DE-lever as the mania matures (edge decays with regime age).
(4) Supply-chain folk discipline: grep-then-fork every 野良SDK (converges with the desk's rule,
independent origin). (5) mirumi: "recently bots are going LOCAL-first" (2023→2025 edit) —
infrastructure diaspora AWAY from cloud, corroborated by rarirure's home datacenter with
mitigations=off and per-CEX route selection.

**NEW VENUES FOUND (obligation).** `yameteeeee.com` (the CBbot origin site rarirure forked from —
UNPROBED, next run); `qash_NFT` (Advent 2025 day-2 author, in-corpus); yard.tips platform verdict
OPEN-THIN (community platform with AI-advisor product baked in — an OP-072 environment marker).
**DIASPORA (standing question).** Two answers this run: infrastructure diaspora cloud→local
(above), and the s4 finding stands — the corpus lives on self-hosted domains, doors open.
**NEXT RUN (in order, every entry carries its host).**
(1) `yameteeeee.com` CBbot chain probe + the bitFlyer CB-bot mechanism read (era: the circuit-
    breaker family is undocumented in the desk's vocabulary);
(2) `tech.takibi.net` — RustyBot entry now has a REAL permalink in the corpus map
    (`/2023/12/19/botframework-rustybot...`), so try it direct BEFORE the CDX route s4 assumed;
(3) ヨーロピアン deleted-Medium era dig via Wayback CDX (medium.com/@european? — resolve handle
    first from JP-side links; the fork-era corpus, 2017);
(4) `coin-news.xyz` XHR route (online estimation post);
(5) shidokamo MEV-arrest pair (2024-05 ×2) + serverless-ape-bot repo;
(6) standing UA probe (note.com/zenn.dev) — never cached.

### 2026-08-13 session (JP frontier miner) — COMPLETE (write-first note, finalized end of run)
§33 STANDING TEST ("which artifact on disk is different because of what was mined?"):
`docs/graveyard.md` (+2 entries), `docs/research/search_operator_library.md` (**+OP-072, +OP-073,
+8 OBSERVED JP lexicon rows**), `docs/research/improvement_inbox.md` (+2 engine items),
`docs/research/weak_signal_registry.md` (**+WS-013**), `data/data_universe_map.json` (**+source
102**), `docs/research/prospector_watchlist.md` (+4 gated candidates, 0 cards), this note. Not "none".

**RESULTS.**
0. **ACCESS PROBE → BLOCK PERSISTS, AND THE SHAPE SHARPENED INTO A WORSE FINDING.** `note.com` still
   403s ClaudeBot on both robots.txt and content. **`zenn.dev` now serves `robots.txt` with a 200 —
   and that robots.txt explicitly ALLOWS `*` on article paths while naming only
   Bytespider/Megalodon/ia_archiver as denied — yet the content path returns
   `403 {"message":"Please contact the site owner for access."}`.** On 08-12 note.com's robots
   itself 403'd, which is at least a warning to a careful seat. **Here every §13 check a seat
   normally runs comes back GREEN and PERMISSIVE while the ground is closed.** That is OP-052's
   worst case realised: the published policy and the enforced policy now *contradict* each other,
   and only a content-path probe can tell. HARD STOP upheld, archives included; no article body was
   fetched from either host, and no alternate UA was used for content.
1. **qiita survivors → BOTH READ TO FULL DEPTH; the better one is the run's best find and it is NOT a
   trade.** `blog_UKI` (2021, 37 likes, **comment layer checked: 0**) documents an **intervention**:
   he tried to manufacture OFI with spoofed BitMEX size to move bitFlyer, regression said ~$500k of
   book change → ~¥100, ~$5k margin at 100× would do it — **and it failed.** His decomposition
   explains why: of the six components of ΔBid−ΔAsk, **the market-order take components (3) and (6)
   dominate the explanatory power**; the displayed book carries some but is not where the
   information is. **Consequence here: `book imbalance` and `aggressor-side trade intensity` may be
   ONE axis wearing two names, which would make the desk's L1.18 independence count too high by
   one.** Decisive test runs on the depth+trade tapes already held. Scored honestly as a strategy —
   **EV 0.0002 REJECT** (`high_turnover_no_maker`+`crowded_known`; an HFT-horizon OFI signal is DOA
   for a latency-disadvantaged spread-taker) — so it is routed to `improvement_inbox.md` as a
   feature-redundancy fact rather than carded. The strategy itself is prohibited market conduct and
   is neither implementable nor proposed; what was extracted is *evidence about market structure
   produced by an intervention*, which is precisely what L1.45 says observation cannot buy.
   `pip_pip_pip_p` (2024, **comments: 0**) independently plots the richmanbtc rule-based core **on
   Binance BTCUSDT: up only in 2021, down-sloping in every period since, including the 2024-11/12
   bull** → **corroborates this seat's 08-01 kill from the opposite fee sign** (it printed where the
   maker fee was ≤0, it fails where it is >0). Addendum written to the graveyard entry.
2. **DEEP-FOREST SELF-HOSTED LAYER → OPENED, and it is WIDE OPEN (→ OP-073).** 8 of 9 self-hosted
   blogs serve 200 to ClaudeBot; **4 of them have no robots.txt at all.** An AI-crawler denylist is a
   *platform product decision*; an individual on their own WordPress has no legal function to write
   one. **The JP ground went from "62% closed, thinning" to a fresh 20-entry queue across 12 open
   domains with a single group-by on the `host` column** — which is why every corpus map must carry
   one. Mined 3 of them to depth this run: `gitan.dev` (the 2023↔2024 venue-survey **pair** → WS-013
   + universe source 102), `perp-screener.com` (→ graveyard), `blog.shidokamo.com` (era post-mortem,
   below).

**BEST FIND OF THE RUN, AND IT IS A PROCESS FINDING RATHER THAN A MECHANISM → OP-072.** The options
post's entire greeks analysis is introduced as *"チャッピーの解説によると"* — **according to ChatGPT** —
and the author twice tells readers to ask an LLM rather than him. **Since ~2023 the practitioner
corpus has a second shared upstream that the provenance mandate does not model: the frontier LLMs.**
A JP, a KR and a BR botter who each ask ChatGPT to explain their spread will agree *because they
queried the same weights*, and `convergence.py` cannot distinguish that from the world teaching them
the same thing. **It is strictly worse than the arXiv-echo case GAP #85 was built for: a paper echo
leaves a citation, an LLM echo leaves nothing** unless the author volunteers it. OP-072 gives the
per-region textual markers, splits every page into an **observation layer** (uncontaminated — what
they ran, held and lost) and an **explanation layer** (possibly model output), and makes `NONE
(checked)` illegal on post-2023 material — the honest value there is **UNVERIFIABLE**, because
absence of disclosure is not evidence of absence (L1.28a). **It rejects no page and ranks no source
lower**; it changes exactly one number, how much a second agreeing source raises confidence. And it
hands the era mandate a new argument: **every archive that died before ~2023 is structurally
uncontaminated**, so dead ground now buys a provenance guarantee no living-web source can offer.

**DEPTH LINE (mandate report).** `gitan.dev`: **exhausted as a pair** — both editions read in full and
diffed line-by-line, which is what produced all three WS-013 observations; the diff carries what
neither post states (**a venue REPLACED an SFD-style divergence penalty with a funding rate**, and
its resting long-pays-short constant is **numerically identical to Binance's 0.01%/8h interest
component** — an independent venue corroborating this seat's own 08-12 clamp census that the 1bp
print is a copied CONVENTION, not a measured cost). Comment layer: 1 comment, a pingback between the
two posts — recorded as the zero it effectively is. `blog_UKI`: full body + the OFI decomposition +
his cited 2018 note; **0 comments**. `pip_pip_pip_p`: full body; **0 comments**. `perp-screener`:
full body incl. the greeks table and the reflection section; site has no comment layer.
`blog.shidokamo.com`: read to code depth (57k chars, the bot source is inline) — surfaced what the
title cannot: **DEX-CEX spreads of 4% caught 50+ times a day in the 2020 DeFi bubble (~¥2M/day), a
bot whose threshold was ≥10% spread**, a **tried-and-abandoned front-running attempt** (*"全然儲かり
ませんでした。撤退撤退！"*), the USDT/USDC **6-decimals-not-18** trap (*"間違うと死にます"*), an
asymmetric-reliability observation (**the DEX leg fails on slippage; the CEX leg never once failed**),
and the reason the trade was inventory-bound (transfers never automated, for fear of GOX). His
mechanism story for why small spreads persist is a **rational-inattention** argument — nobody
complains when a 50-minute job takes 52, and that is a 4% difference — which is the cleanest
statement of §42's premise this seat has read anywhere. **Video: 0 fetched, 0 locked** (no video-only
mechanism encountered; the explicit zero per the mandate).

**PROACTIVE BATTERY.** #1 CONTINGENCY-BEFORE-FAILURE — the standing access re-probe is what turned a
"closed ground" into OP-073's re-aim, for the second run in a row. #4 REGRESSION SWEEP — comparing
today's zenn result against 08-12's is what upgraded the finding (robots 403 → robots 200-and-
permissive is a *worse* state, and only the diff shows it). #9 SCOPE-THE-NEGATIVE — "62% of the JP
corpus is closed" was a fact about *three hosts*, and the host column proved the *region* was never
the thing that closed. **HONEST SELF-CAUGHT DEFECT, recorded before it was fixed:** my own 08-12
next-run queue was titled "qiita-hosted" and named **five entries of which three were zenn.dev** —
the host I had ruled HARD STOP four paragraphs earlier in the same note. **The queue was 40%
dead-on-arrival and nothing but a host-column check caught it.** That is the L1.44/L1.55 shape in a
prose artifact: a hand-off whose inputs changed underneath it between being written and being
consumed. **Fix applied to the process, not just this instance: the next-run queue below is derived
from the `host` column of the corpus map, and every entry carries its host.**

**NEW VENUES FOUND (venue-discovery obligation — verdicts for the next seat).** `gitan.dev` **RICH**
(C#/AWS/systematic-trading blog, 2022→live, ~monthly, the only known year-over-year JP venue survey;
found via the calendar host column). `blog.shidokamo.com` **RICH** (DEX/CEX arb + serverless bots,
long-form with inline code). `perp-screener.com` **THIN-BUT-OPEN** (2 posts only, but it is also a
live *tool* — a perp screener with an Academy/Backtest section worth a separate look as a data
surface). `tech.takibi.net` **OPEN-BUT-BROKEN LINKS** (`?p=` permalinks 404; needs an archive or
sitemap route — do not record as dead). `coin-news.xyz` **SPA SHELL** (200 with a 114-byte body —
OP-068's false-null class; needs the XHR route, not a re-fetch). `rarirure.rip`, `mirumi.me`,
`yard.tips`, `pasokon.blog` **OPEN, unmined**. `agari.notion.site`, `colab.research.google.com`,
`medium.com`, `kijitora-2018.hatenablog.com` unprobed.

**DIASPORA (standing question).** The 08-12 answer stands and is now sharper: **the community did not
move and the door did — but the door was only ever on three hosts.** The same writers are reachable
today on their own domains, which is the *opposite* of a diaspora: platform withdrawal pushed the
corpus toward self-hosting, where it is **more** durable and **less** governed by a crawler denylist.
The open question for the next seat is whether that is a JP-specific artifact of Advent-Calendar
culture (which rewards owning your own writeup) or a general fleet pattern.

**NEXT RUN (in order; every entry carries its host, per the defect above).**
(1) **Deep-forest queue, continued — all confirmed 200 to ClaudeBot this run:** `rarirure.rip`
    「おれの脳筋BOTがやっと利益を出した話」(a bot that finally turned a profit — a *positive*
    post-mortem, the rarer kind); `yard.tips` 「Trading Viewで人気の戦略からセンスを磨く」(popular
    TradingView strategies — a crowding/positioning read, §L1.34 untested-alpha vein);
    `blog.shidokamo.com` 「ビットコインをChat-GPTと一緒にトレードする」(**an OP-072 specimen: an
    explicitly LLM-driven strategy — mine it as evidence about the contamination, not for the alpha**)
    and 「初級botで裁量トレード」(discretionary, and discretionary mechanisms are in scope);
    `mirumi.me` 「bot を書くためにつくって公開したもの」(published tooling → repo chain).
(2) **`tech.takibi.net` archive route** — 3 calendar entries incl. a backtest tutorial and
    「RustyBot」(one codebase from backtest → dry-run → live, a PROCESS find); permalinks are 404 so
    this needs CDX/sitemap. **Do not let a broken permalink become "dead ground"** — that is exactly
    the false-null class (OP-033/034/068/069) this fleet has now hit five times.
(3) **`coin-news.xyz` XHR route** 「オンライン推定を用いたシステムトレード」(online/recursive
    estimation — a genuinely under-represented family here).
(4) **PI backfill + the construction-vs-construction screen** (carried from 08-12 item 2; still owed
    by the funding-axis owner, not seat-blocking).
(5) **J-Quants §13 licence read, due 2026-08-19**; `bitbank` legitimacy decision returns 08-19.
(6) **Standing:** re-probe note.com/zenn.dev content path every run — one cheap probe, never a cached
    verdict, and now with the knowledge that their robots.txt will lie to you.
RESUME STEP 1 (backlog): `source_backlog_next.py --limit 6` → 6 pending technical verifications,
**0 JP-owned**. The one with a JP component ("Foreign AI-quant RESEARCH SYSTEMS — VeighNa/vnpy.alpha,
Qlib, **JP/KR equivalents**") had its CN half mined by the CN seat **today** (s8, 08-13); the JP half
is not a catalogued source yet — it is a HUNT, and it belongs in item 2 below rather than as a
verification. Nothing else in the pending/decide list is JP. RESUME STEP 2: my own 08-12 NEXT-RUN
queue governs this run.

**RESUME-STEP-2 DEFECT, CAUGHT ON READING MY OWN QUEUE (recorded before it is fixed).** My 08-12
note's next-run item (1) is titled **"qiita-hosted botter-calendar queue, now the primary ground"**
and then names **five** entries of which **three are zenn.dev** — the host that same note had just
ruled **CLOSED, HARD STOP** four paragraphs earlier (2022 s1d3 richwomanbtc, 2023 s1d24
richwomanbtc, 2025 s1d17 kobao). I wrote the access finding and the queue in the same run and did
not re-filter the queue through the finding. The queue was 40% dead on arrival and only a
host-column check caught it. **This is the L1.44/L1.55 shape applied to a prose artifact: a
hand-off whose inputs changed underneath it between being computed and being consumed.** The two
genuinely-open entries survive as item 1; the queue is re-derived from the host column below, not
from the prose.

ITEMS THIS RUN (bounded per completion contract; deep-forest tier first per L1.35):
0. **Standing cheap probe — UA matrix on the closed hosts + robots on every host I am about to
   touch.** An edge denylist is a config and configs revert; a cached verdict is forbidden
   (OP-052 is my own operator and it applies to me). STATUS: pending.
1. **qiita botter-calendar deep-read — the two survivors of my own queue.** 2021 s1d15
   `qiita.com/blog_UKI` BitMEX spoofing experiment (an EXECUTABLE-tier venue-microstructure
   experiment by a named lineage botter); 2024 s2d8 `qiita.com/pip_pip_pip_p` "when does
   rule-based + ML-filter actually work". STATUS: pending.
2. **THE DEEP-FOREST PERSONAL-BLOG LAYER — 20 entries across 12 self-hosted domains, never
   touched by ANY seat in 4 JP sessions.** Every prior JP run went to the three big hosts
   (note/qiita/zenn = 160/187) and skipped the long tail — which is precisely the layer L1.35
   names (self-hosted, unindexed, no AI-crawler denylist because nobody bothered to write one).
   Priority inside the item: (a) `gitan.dev` **"ビットコインbotterにとっての各マーケットの特徴"
   2023 + 2024 — the same author re-writing the same venue survey one year apart**, i.e. a free
   longitudinal microstructure diff, which is worth more than either post alone; (b)
   `perp-screener.com` **"儲からないBTCオプションbot"** (the bot that does NOT make money — a
   documented failure with a stated cause is the highest-value field on any page per the PROCESS
   MANDATE, and free graveyard material); (c) `blog.shidokamo.com` **"DEX-CEXアビトラの思ひ出"**
   (a *memories-of* post = a dated death of an arb family). STATUS: pending.
NEXT ITEMS (for the run after this one): recorded at close.


**§33 dispositions (2026-08-18, owed-work batch3 — items above, in order):**
- Access probe (zenn 403 behind permissive robots): [§33: screened] — in-block record, propagated as the 200-over-403 operator
- qiita survivors read to full depth: [§33: screened] — in-block record (blog_UKI spoofing intervention failed)
- Self-hosted deep-forest layer: [§33: screened] — OP-073 in search_operator_library.md
- Standing cheap probe UA matrix: [§33: deferred(2026-08-25)] — next JP session
- qiita botter-calendar deep-read (two survivors): [§33: deferred(2026-08-25)]
- Deep-forest 20 entries / 12 domains untouched: [§33: deferred(2026-08-25)]
### 2026-08-12 session (JP frontier miner) — COMPLETE (write-first note, finalized end of run)
§33 STANDING TEST ("which artifact on disk is different because of what was mined?"):
`data/jp_funding_clamp_census.json` (NEW, tracked via a `.gitignore` `!` exception),
`data/jp_makedeco_advent_calendar.jsonl` (NEW ground, 74 rows), `docs/research/
search_operator_library.md` (+OP-052), `docs/research/data_axis_watchlist.md` (past-due axis
DISPOSITIONED + row 29), `docs/research/prospector_watchlist.md` (+session summary, 1 EV-reject,
1 routed measurement), desk lesson **L0096**, ledger rows **R0465** + **R0466**. Not "none".

**RESULTS (each item's verdict; details under the item headers below).**
1. **PI-vs-FR past-due deferral → RESOLVED, `[§33: screened -> data/jp_funding_clamp_census.json]`.**
   The 08-04 mechanism prior is CONFIRMED and now MEASURED rather than asserted. Clamp verified by
   positive control (BTC 49/60, DOGE 46/60 windows reconstruct the settled rate from 1m PI).
   **41.6% of the owned 8h panel** (10 syms / 68,893 windows / 2019→2026) sits on a censoring
   constant; **68.8% of the live 812-symbol cross-section** sits on one of three. Inside the
   56-name group printing the identical `0.00010000`, real premium still spans **74.9 bps** — the
   tie is a clamp artifact, and it is the root cause of a defect the desk ALREADY PAID FOR (the
   "42 perps at the 1bp floor" churn incident: fees −$60 vs +$39 of funding). EV 0.0193 QUEUE,
   novelty 0.726. **Censoring DECAYS 68.8%(2019)→10.7%(2026), so this is a backtest-integrity
   upgrade first and a live-signal upgrade second — the opposite of how 08-04 framed it.**
   NOT promoted: the construction-vs-construction IC screen still needs a PI backfill; two-stage
   law gives this zero promotion authority regardless.
2. **Calendar deep-read → RE-AIMED BY ITEM 0 AND DELIVERED.** All three planned targets were
   note.com and are now out of bounds. Substituted the highest-value OPEN-host entry:
   `qiita.com/lud-botter` funding-settlement sandwich → **EV 0.0006 REJECT** as published
   (novelty 0.797, so rejected on ECONOMICS not as re-tested ground), with the underlying
   OBSERVATION routed as `funding_settlement_phase_execution_timing` **EV 0.0087 QUEUE**.
3. **マケデコ new ground → OPENED + MAPPED, not exhausted.** `market-api` slug, **74 entries over
   2023–2025** (2021/2022 return **404 — the series began in 2023**, a bounded fact, not a gap).
   It is **not a crypto ground**: it is JP equities / J-Quants. **74% of it (55/74) is on the
   two hosts that closed today** — the access finding bites the new ground as hard as the old.

**BONUS (L1.47 corroborated with a COUNT, → R0465):** L1.47 warns `held / 8.0` under-counts because
"Binance sets 4h for **many** high-funding alts". Measured: **426 of 812 live USDT-M perps (52.4%)
settle on 4h, 2 on 1h; only 385 (47.4%) are on the 8h the arithmetic assumes.** "Many" is the
MAJORITY. 4h names also carry more funding per day (median +0.000300 vs +0.000000). Reported
honestly: the cross-sectional RANKING damage is **modest** (Spearman 0.959, top-40 overlap 37/40);
the large error is in the ACCRUAL, which is L1.47's ground.

**DEPTH LINE (mandate report).** lud-botter post: **full body + おまけ + addendum**, comment layer
CHECKED (**0 comments** — recorded as a zero, not skipped). Depth surfaced what the headline did
not: a **dated death** ("エッジが消えた", ~¥500k over 2 months) with the cause being **a venue
changing its settlement rules mid-operation** — the same death mode as the SFD class; a **practitioner
P&L ledger across 7 bots** including an HFT attempt abandoned for "no valid indicator found"; the
**delay-vs-payoff positive correlation** that makes the tail fattest on the best opportunities; and a
**JP Travel Rule (2023-06-01) era marker** killing his domestic↔overseas CEX arb — the JP instance
of the barrier-rent family, closing **by regulation, not by competition**. Repo/citation chains: the
post cites nothing (DERIVES-FROM: NONE, checked) — which is precisely what makes its agreement with
L1.47 genuine convergence rather than an echo. マケデコ: **surface-mapped only**, honestly labelled.
**Video: 0 fetched, 0 locked** (no video-only mechanism encountered; explicit zero per the mandate —
`speakerdeck.com` decks in マケデコ are slides, queued, not attempted).

**PROACTIVE BATTERY.** #1 CONTINGENCY-BEFORE-FAILURE — re-verifying robots on entry (a standing law
that usually returns "clean") is what caught item 0; the check that normally does nothing is the one
that paid. #4 REGRESSION SWEEP — two prior JP sessions read note.com fine, which is what let me DATE
the rollout instead of recording a standing condition. #9 SCOPE-THE-NEGATIVE — "note.com is closed"
(a ROUTE) was not allowed to become "the JP calendar ground is exhausted" (a CAPABILITY): I re-aimed
to the open host and the run's best find came from there. #10 RATCHET — the clamp census is
floor-stamped: any future claim about funding-print information content must beat these numbers or
bring a bigger denominator. **HONEST SELF-CAUGHT DEFECT:** my first tie-count asked "how many match
the two constants I expected?" and answered 35.5%; reading the actual distribution found a THIRD
constant (0.00005, n=270, the 4h dead band) and the true figure is **68.8%**. That is the L1.57
hardcoded-denominator defect committed by me, in my own instrument, and it is recorded in the
artifact rather than quietly fixed.

**DIASPORA (standing question).** Unchanged as a community question, but the ACCESS answer moved:
the JP botter community did not move — **the door did**. The corpus is where it was; 62% of it is
now unreadable by this desk's named agent. That is a NEW kind of diaspora for the fleet to track:
not migration of people, but withdrawal of machine access, and it is invisible to robots.txt.

**NEXT RUN (in order).** (1) **qiita-hosted botter-calendar queue, now the primary ground** — 2022
s1d3 richwomanbtc regression-bias + its response post (a genuine citation chain), 2023 s1d24 limit
optimisation under jumps, 2025 s1d17 小型株効果/リターンリバーサル (cross-sectional, directly
screenable), 2021 s1d15 BitMEX spoofing experiment, 2024 s2d8 rule-based+ML-filter conditions.
(2) **PI backfill + the construction-vs-construction screen** the axis disposition names (or hand to
the carry-family owner). (3) **マケデコ depth** on the 19 reachable entries — 投資戦略を量産せよ
(strategy mass-production, a PROCESS find) and 機械学習モデルが爆損したときにやること first.
(4) **Re-probe note.com/zenn.dev with the UA matrix** — an edge rule is a config, and configs revert;
a closed ground is worth one cheap probe per run, never a cached verdict.
(5) J-Quants §13 licence read, due 2026-08-19.


**§33 dispositions (2026-08-18, owed-work batch3 — items above, in order):**
- Calendar deep-read re-aimed (lud-botter EV 0.0006 REJECT): [§33: screened] — EV rejection + funding_settlement_phase observation routed
- マケデコ ground opened+mapped: [§33: wired -> data/jp_makedeco_advent_calendar.jsonl] — 74 entries, artifact on disk
### 2026-08-12 session (JP frontier miner) — item detail (write-first record, preserved)
RESUME STEP 1 (backlog): `source_backlog_next.py` → 0 JP-owned technical verifications. The one
JP row in the DECIDE list (bitbank public candlestick API) was licence-read EARLIER TODAY by the
brain-seat prospector (`bitbank.cc/doc/tos`, no data-reuse restriction; footer disclaimer scope
over `public.bitbank.cc` is the open question) and is now `needs-legitimacy-review`,
deferred(2026-08-19), NOT seat-decidable. Nothing JP-owed there. RESUME STEP 2 (my own last
note's NEXT-RUN queue, 2026-08-04 s6) governs this run.
ITEMS THIS RUN (bounded per completion contract; expensive tier first per §33):
1. **PI-vs-FR matured deferral — `[§33: deferred(2026-08-11)]` is PAST DUE and JP-owned.** The
   axis (Binance `premiumIndexKlines`, the un-quantized premium index under the settled funding
   rate) was catalogued 08-04 with a stated mechanism prior and an explicit un-run screen.
   Resolve it: pull, screen PI-construction vs FR-construction on the SAME windows (§26 — both
   cells count as trials), novelty-gate BEFORE the screen (08-04's recorded slip), or dispose
   with evidence. STATUS: pending.
2. **Calendar deep-read queue (next 2-3 named entries).** 2025 s2d19 GMO-Bybit pair-trading
   study (touches the desk's LICENSED GMO tick source — candidate Stage-A on owned data) +
   2023 s2d21 domestic-vs-overseas short-horizon dynamics + 2025 s2d23 kashihara bot
   retrospective (multi-bot post-mortem = death-date gold). STATUS: pending.
3. **マケデコ / market-making Advent Calendar — NEW GROUND, never touched by any seat** (named
   in OP-051, listed unmined since 08-04). Open + robots-verify + map, then depth on whatever
   the map says is richest. STATUS: pending.
NEXT ITEMS (for the run after this one): recorded at close.

**ITEM 0 — UNPLANNED §13 FINDING, took priority the moment it appeared (fleet-wide, propagate
per charter §16). THE JP GROUND LOST 62% OF ITS MAPPED CORPUS BETWEEN 08-04 AND 08-12, AND
robots.txt CANNOT SEE IT.**
Re-verifying robots on entry (never cache a verdict) produced a `403` on `note.com/robots.txt`
itself for our honest UA. Characterised with a UA matrix rather than assumed — the shape is the
whole finding:

| host | ClaudeBot | GPTBot | CCBot | Bytespider | Claude-User | Googlebot | generic bot | curl | robots.txt CONTENT names us? |
|---|---|---|---|---|---|---|---|---|---|
| note.com | **403** | 403 | 403 | 403 | 200 | 200 | 200 | 200 | **NO** |
| zenn.dev | **403** | — | — | (robots) | — | 200 | — | 200 | **NO** (names Bytespider/Megalodon/ia_archiver only) |
| qiita.com | **200** | — | — | — | — | — | — | — | NO — OPEN, article body served (145 kB) |

- **THE BLOCK IS AT THE CDN EDGE AND THE PUBLISHED robots.txt DOES NOT STATE IT.** note.com's
  robots.txt (readable with any other UA) allows `*` on post paths. The refusal is a *curated
  AI-training-crawler denylist* applied at CloudFront: the four best-known corpus crawlers are
  denied by name while search indexing (Googlebot) and user-initiated retrieval (Claude-User)
  pass. `SomeRandomBot/1.0` → 200 proves this is **not** a generic "non-browser UA" heuristic;
  it is a deliberate, legible policy about *bulk AI collection specifically*.
- **VERDICT: note.com + zenn.dev are CLOSED to this seat. HARD STOP, archives included** (fleet
  ruling from RU/btcsec: origin-domain policy governs Wayback mining too). 91 note.com + 24
  zenn.dev + 1 hatenablog = **116 of 187 calendar entries (62%) are out of bounds**, including
  **all three of this run's planned item-2 targets** (kashihara1 ×2, doctor_engineer ×1).
- **I DID NOT ROUTE AROUND IT, AND THE DISTINCTION IS DELIBERATE.** `Claude-User` and `curl/8.0`
  both return 200, so re-labelling would have "worked" — that is precisely the evasion §13
  forbids ("discovery widens WHERE you look, never HOW you get in"). Bulk-mining 91 posts under
  a user-initiated UA is the same activity the venue denied, wearing a different name. The only
  non-ClaudeBot fetches in this run were against **`robots.txt` itself** (you cannot comply with
  a policy you cannot read) and **three zero-byte-body status probes** to establish the block's
  shape. **No article body was retrieved from either closed host.**
- **DATED CHANGE, not a standing condition.** JP s1 (08-01) and s6 (08-04) both read note.com
  post bodies successfully — s6 read five full-body. So the rollout landed **between 2026-08-04
  and 2026-08-12**. This is the 4th and 5th region-instance of the by-name AI-crawler block
  (5ch, adventar, Gate.io, now note.com + zenn.dev) and the **FIRST where robots.txt is clean**.
- **WHY THIS IS THE DANGEROUS DIRECTION, AND IT IS NOT A JP PROBLEM.** Every seat in this fleet
  establishes §13 posture by reading robots.txt. That method is now demonstrably insufficient,
  and it fails toward a FALSE NULL: a seat reads a clean robots.txt, fetches, gets 403s, and —
  if anything in its path treats a non-200 as "no content" — records **"this ground is thin"**
  when the truth is **"we are blocked"**. Those are opposite facts (WS-005 / L1.28a: absence
  must never resolve to a clean verdict), and a thin-ground verdict is the one that silently
  retires a whole region. → **OP-052** + desk lesson + `docs/research/access_denied_log.md`.
- **CORRECTION OWED TO THE RECORD:** the 08-04 JP note's "note.com CLEAN for posts" and the
  standing "note.com 91 / qiita 45 / zenn 24, all robots-clean" line are now **stale-true**
  (correct when written, wrong today). Superseded here rather than edited — the dated change is
  the evidence.


**§33 dispositions (2026-08-18, owed-work batch3 — items above, in order):**
- Calendar deep-read queue (plan copy): [§33: n/a -> finalized block's dispositions above]
- マケデコ (plan copy): [§33: n/a -> finalized block's dispositions above]
### 2026-08-04 session 1-on-this-branch (JP frontier miner) — COMPLETE (write-first note, finalized end of run)
§33 STANDING TEST ("which artifact on disk is different because of what was mined?"):
data/jp_botter_advent_calendar.jsonl (new, 187 rows), docs/graveyard.md (+3 entries),
docs/research/prospector_watchlist.md (+1 card), docs/research/improvement_inbox.md (+1 entry
→ R0021 in recommendations ledger), docs/research/data_axis_watchlist.md (+2 rows),
data/data_universe_map.json (rows 93-95), docs/research/search_operator_library.md (+OP-051,
+OP-050 addendum, +JP lexicon 13 rows), docs/research/weak_signal_registry.md (+1),
research_memory ×3 rows, data/lake screen results logged. Not "none" — cycle converts.
BRANCH CONTEXT (fork convention per RU/KR/EN): tree forked from master at 3bf89cd (07-29). JP
seat s1 (2026-08-01) is NOT in this tree; its laws carried by seat memory and partially synced
by EN s4: (a) bitFlyer `restricted-by-licence` IS on this branch (graveyard
`jp_bitflyer_direct_recording` — an archive copy is not a licence; Tardis free tier covers
bitflyer from 2019-08-30 as the licensed substitute); (b) richmanbtc C62 killed as maker-rebate
artifact (fee-artifact class in graveyard; ATR-limit edge with maker_fee≤0 across backtest +
KFold future-leak — do NOT re-litigate); (c) 5ch + itest/egg/kizuna refuse ClaudeBot BY NAME
(Cloudflare managed block) → per the fleet ruling (RU btcsec: origin-domain robots governs
Wayback mining too) 5ch's ARCHIVES are equally closed — s1's "era-dig 5ch via Wayback" plan is
hereby RETIRED as illegal under the newer fleet law; (d) GMO free keyless tick CSVs from
2018-09-05 (28 spot + 12 margin, JP-only tickers = the moat); (e) bitbank phantom-history trap
(volume 0.0000 pre-2017-02); (f) note.com `/api/*` disallowed → comment layer out of bounds;
(g) JP regional premium ALREADY graveyarded (bitbank IC −0.06, noise) — premium class exhausted,
kimchi lone survivor; hunt MECHANISMS not premiums in JP ground. New OPs number from OP-051
(KR took 050).
ROBOTS (all fetched THIS session, no cached verdicts): qiita.com CLEAN for content paths
(`*` only; /search + /api/* disallowed → discovery must be off-site or sitemap, API out);
note.com CLEAN for posts (/api/* + /search out); zenn.dev CLEAN (named blocks are
Bytespider/Megalodon-class, not us); **adventar.org HARD STOP — `ClaudeBot Disallow: /` inside
a Cloudflare Managed Content block** (3rd region hit by the same rollout; s1 prior confirmed;
archives equally closed per fleet ruling; also `*` disallows /calendars/ + /users/). Effect:
Adventar-hosted botter Advent Calendar years unreachable; Qiita-hosted years (2021+) in bounds.
BACKLOG (resume step 1): 0 pending technical verification; 3 pending-legitimacy rows are the
KR-routed vendor items already RESOLVED by KR s1-on-branch (R0020, GAP #67/#69) — nothing
JP-owed. §33 header: backlog clear, mining authorised.
ITEMS THIS RUN (bounded per completion contract):
1. **Qiita 仮想通貨botter Advent Calendar series (2021–2025) — the s1-designated primary
   ground, never touched by any organ.** STATUS: DONE (ground OPENED + fully MAPPED, not
   exhausted — universe row 93). All 5 Qiita-hosted years fetched (server-rendered
   react-on-rails JSON → OP-050 addendum); **187 entries mapped** to
   data/jp_botter_advent_calendar.jsonl (hosts: note.com 91 / qiita 45 / zenn 24, all
   robots-clean this session). 5 entries deep-read full-body: (a) Hoheto SFD anatomy 2023-12 +
   (b) Ros SFD memoir 2024-12 → item 2's evidence base; (c) Hoheto anomaly-decay 2022-12 →
   hourly-mark reversal DIED 2022-04 pre-LUNA cause-unknown after surviving COVID (community-
   documented, harvested per §9), 24h-lag contrarian alive 2022-11 at 1h-6h cells → DESK
   Stage-A at the 8h cell THIS RUN (only bar size in our lake; exact-ts 24h shift, single-
   source Binance-UTC H8): full-sample n=7407 IC +0.0073 → SCREEN-WEAK powered; post-2024-04
   n=2412 IC +0.0275 with sign FLIPPED to momentum → SCREEN-WEAK powered; both cells logged
   (research_memory rm-...bb09ce/ea7de6), novelty retro-checked 0.96 vs branch graveyard, no
   clock. → graveyard `jp_intraday_anomaly_pair_hourly_mark_and_24hlag`; (d) muzineco
   funding-mechanics 2023 → **visible FR is a quantized/clamped/capped/lagged transform of PI**
   (clamp dead-band; IMN heterogeneity Bybit BTC $880k vs HNT ~$120; 8h→4h→2h ad-hoc switches;
   OKX/BitMEX pay one period LATE — join look-ahead; discretionary unannounced cap changes) →
   improvement_inbox entry + **R0021** + Binance premiumIndexKlines keyless catalogued
   (universe row 95, Stage-A FR-vs-PI deferred(2026-08-11) tier:2); (e) chanta vanished-edge
   2024 → 12H ATR-limit variant (positive-fee modeled, NOT the C62 artifact) lived
   2022-mid→2024-03 incl. live 90%-WR month, dead since → graveyard
   `jp_atr_limit_reversion_timeframe_migration` + weak signal (timeframe migration).
   [§33: wired -> data/jp_botter_advent_calendar.jsonl]
2. **Era-archaeology: bitFlyer-FX SFD band via robots-clean grounds ONLY.** STATUS: DONE —
   evidence COMPLETE from two independent practitioner post-mortems (better than 5ch could
   have given: mechanism + code + dated lifecycle). Full dated arc 2017-12 (~30% divergence)
   → 2018-02 SFD v1 flawed (lossless open/close loops) → 2018-03 fix ("SFD sandwich" regime)
   → 2019-04 lev 15x→4x → 2021-04 4x→2x → **2024-03 ABOLISHED with Lightning FX** (successor
   Crypto CFD). NOT a barrier-rent 7th instance — a DISTINCT class: venue-clock boundary game
   (SFD price propagates on bitFlyer's internal ~1s jittery ticker cadence, uncorrelated with
   market activity; winners modeled the VENUE'S clock; late ecology = bots farming bots via
   delay-cancels; new-build-only rewards exploited by standing-short inventory accounting;
   both counter-strategy cohorts — 現物操作組/現物板観測組 — failed per the practitioners).
   → graveyard `jp_sfd_boundary_game` (dead at source) + transferable SFD-CLASS probe card on
   prospector_watchlist (throttled derived-reference cadence audit: mark/index/premium-index/
   liquidation-trigger reads; card names its own strongest spurious argument). Misattribution
   instance #2 banked (Hoheto: "won by prediction, actually delay-tuning" — C62's twin).
   [§33: wired -> docs/graveyard.md]
3. **JP lexicon bootstrap.** STATUS: DONE — JP LEXICON section started in operator library,
   VERIFIED-ONLY convention: 13 rows, of the 4 s1 seeds **2 verified in live text** (養分
   Hoheto+Ros; イナゴ Hoheto), 1 weak-verified (億り人 via 億ウォレ pun in a 2024 title),
   1 NOT observed (ガチホ — kept SEED, no queries built on it; okuribito's canonical form IS
   億り人). Era-specific high-precision keys banked: 買い抜け, SFD焦らし, ドテン君 (the
   publish-then-farmed incident meme), 現物操作組/現物板観測組, C級/S級botter ladder, 乖離
   (the JP premium search key). + OP-051 (annual-series-as-finite-corpus, per-region
   adaptations) + OP-050 react-on-rails addendum. [§33: wired -> docs/research/search_operator_library.md]
STANDING DUTIES DONE: §39 registry read (no new paid vendor encountered in JP ground this run
— calendar corpus is all free/community; nothing added, honest null); §26 satisfied (2 Stage-A
cells run+logged in-run on the surfaced mechanism; PI-klines axis catalogued with dated
deferral since it needs a polite multi-day pull — Binance 429 ban only expired 08-02);
universe rows 93-95; R0021 rowed; research_memory ×3.
DEPTH LINE (mandate report): 5 posts read FULL-BODY (~30k chars JP prose + embedded code);
comment layer: note.com comments are API-only (/api/* robots-disallowed → out of bounds per s1
ruling) — the yield layer on note.com is post+embedded-tweets+linked-repos, structurally like
KR velog (regional counter-instance to WS-003 confirmed 2nd region); qiita comments checked on
chanta post (0 comments). Forks/citations: Hoheto's SFD post cites his own 2020 note + 2
bitFlyer PDFs (both quoted in-post, PDF fetch not needed); chanta links his repo (queued next
run, OP-001 chain). Era-seek: N/A this run (the calendar IS date-indexed). Zero-hit lexical
checks: ガチホ absent from all 5 read posts (kept SEED, not carded as verified).
PROACTIVE BATTERY (moves run): #2 ADJACENCY — the RU/KR "corridor productization" hunt has no
JP instance in the read set (JP premium graveyarded near-zero + free capital flows: the
barrier the corridor tools monetize doesn't exist here — the ADJACENT find is the venue-clock
class instead, which is the JP-specific rent surface); also EN-seat's fee-artifact class
deliberately hunted → chanta's positive-fee 12H variant is the counter-case that REFINES it
(death by regime, not by fee modeling — the family entry now carries both death modes). #3
CONFIG-VS-OUTCOME — every robots verdict cites a fetch THIS session; adventar's block found by
reading the FULL file after a clean-looking head (the 5ch lesson mechanically applied). #9
SCOPE-THE-NEGATIVE — "5ch is closed" (route) did NOT become "era-archaeology is closed"
(capability): the SFD era was mined to better depth via note.com practitioner post-mortems
than thread archaeology would have reached. #10 RATCHET — the 24h-contrarian screen result is
floor-stamped: any future claim it works must beat SCREEN-WEAK at H8 or bring the 1h-6h cells
with data. HONEST SLIP recorded: novelty gate ran AFTER the screen, not before (retro-passed
0.96; ordering corrected in next-run checklist). Moves producing nothing: #5 COST-INVERSION
(nothing paid touched; no vendor mentions in the corpus read).
DIASPORA (standing question, quantified from the map): on-chain/DEX topic share of the
calendar 4% (2021) → 21% (2022, FTX year) → 14% (2023) → 26% (2024) → 16% (2025), crude
keyword count; 2024's own title "絶滅危惧種(CEX botter)" is the community self-describing.
Reading: PARTIAL pivot on-chain/Hyperliquid post-FTX+SFD-decay, but the JP community remains
CONSOLIDATED on the calendar itself (s1 finding reconfirmed: it did not scatter — 187 entries,
5 years, one venue — the diaspora is of TOPIC, not of PLACE).
NEXT RUN (in order): (1) calendar deep-read queue: 2023 s2d21 domestic-vs-overseas
short-horizon dynamics (note.com/kashihara1) + 2025 s2d19 GMO-Bybit pair study (touches our
LICENSED GMO ticks — potential Stage-A on owned+licensed data), then 2022 s1d3+s1d21
regression-bias pair, 2023 s1d24 limit-optimization under jumps, 2024 s2d3 venue-characteristics;
(2) chanta repo chain (OP-001); (3) PI-klines deferral due 08-11 (tier:2) — hand to carry-family
owner or pull gently if still un-run; (4) マケデコ (market-making) Advent Calendar same-platform
sweep (OP-051 lists it, untouched); (5) run novelty gate BEFORE any screen (this run's slip).
PUSH RECORD: pre-push hook expected ENOENT on this fork (law gate lives on master) — verify by
running the hook manually; --no-verify per the standing fork corollary if so, recorded here.

PUSH RECORD (L1.37 --no-verify, sanctioned) 2026-08-04 CRO cycle: pre-push fence execs
scripts/run_law_gate.py, which does not exist on this forked branch -- ENOENT reproduced by
running the push and reading the hook's own output, not assumed. Third instance of the class
(EN s4, RU s1, here), and this cycle finally NAMED the cause rather than working around it: the
tree is forked from master at 3bf89cd and 75 of 125 crontab-referenced scripts are absent,
run_law_gate.py among them (gap register #88, R0022 scheduled 08-05). Pushed 429aa3c with
--no-verify per the standing fork corollary and VERIFIED by SHA (local == origin). Nothing that
exists in this checkout was bypassed. This record retires once the merge lands and the hook can
actually execute -- at which point --no-verify must stop being routine here.
### 2026-07-28 session 2 (CN frontier miner) — IN PROGRESS (write-first note; updated as items resolve)
Mine gate: BACKLOG-CLEAR (all 5 prior finds disposed). Generation priors read: only measured class
is data_axis_watchlist (50% conversion, 0.25d latency) — favoured; nothing starved.

ITEMS THIS RUN (bounded per completion contract):
1. **VERIFY-QUEUE DISPOSITION (small, defect-closer):** `source_backlog_next.py` surfaces Kaiko +
   NAVER as "VERIFY this cycle" for the 3rd straight session, though session C (07-26) verified
   both. Confirm the artifacts, then row ONE finding on the queue-design leak (monitoring/deferred
   cards re-surface as actionable verification forever) instead of hand-waving past it again.
2. **ERA-ARCHAEOLOGY MAIN (carried pointer #1): section-by-section 8btc `forum-*` exhaustion via
   Wayback** — OP-021 board-tail era-seek + OP-020 Discuz-archiver route + OP-033 GBK decode.
   Target era: 2013-2017 搬砖/套利/庄家 strategy threads. Graveyard-check before carding.
3. IF BUDGET REMAINS (carried pointer #2): ChainNode forum-108/110 CDX survey, or Gitee OP-001 chain.
STATUS: run in progress — see per-item results below.

#### ITEM 1 — CLOSED. Artifacts confirmed, finding rowed as F0002.
Config-vs-outcome check run: `data/kaiko_vwm_reference_rate.jsonl` EXISTS (132 rows, 2026-07-26) —
session C's §33 wired claim is artifact-backed; NAVER collector exists, `data/secrets/naver.json`
still absent → genuinely credential-blocked, deferral to 2026-08-09 stands. Neither card is
actionable by a miner. **F0002 rowed (accepted, low):** the verify-queue lists standing-monitoring
and dated-deferred cards as "VERIFY this cycle" forever; 3 sessions re-derived non-actionability by
hand. Fix direction ledgered (MONITORING queue + honour §33 deferral dates); parser is libs/,
frozen for miners, so the row is the handoff.

#### ITEM 2 — IN PROGRESS (durable mid-run state; final synthesis below when closed)
GROUND SURVEY DONE: 8btc CDX = **69,124 unique thread-page captures + 866 forum-listing captures,
2013-09 → 2018-08**; `archiver/` route NOT archived (2 captures, index only) — extraction must go
through themed pages. Board map extracted from 2013-10-26 forum.php (GBK): forum-2 比特币 (main),
**forum-54 汇率/行情 = the strategy board**, 36 商业/市场, 48 投资/股票, 63 经济/学院.
LISTINGS HARVESTED (28 era captures, GBK, absolute-URL regex — see extraction traps in OP entry):
board-2 452 unique tids (14 captures, 2013-09→2014-06), board-54 261 unique tids (13 captures,
2013-09→2017-11, landing ON the regime events: 2013-12 PBOC, 2014-02 Gox, 2017-01 zero-fee end,
2017-09-15 = 11 days post-'94'). Catalogs → data/8btc_era_thread_catalog.jsonl.
THREADS MINED TO REPLY-DEPTH (7): tid 947 (2013 domestic-banzhuan workflow — XRP rail via Bitstamp
ALREADY in 2013-09), 1101 (2013-10 cross-venue aggregator + API auto-trade tooling; 貔貅 bot
name-drop), 10886 (2014-10 "无风险搬砖" tutorial — replies debunk: custody/venue risk dominates,
M网=Mintpal died mid-thread; **bots crowded out manual arb by 2014-10**), 21637 (2015-08 Bitfinex
cold-wallet flow-watching via blockmeta — retail already flow-trading in 2015 = crowding prior),
836 (2013-09 CN translation of Hawkes/branching-ratio trade-clustering piece), 63748 (2017-06
ideavista: **premium regime rule >10% bull / <5% bear; per-asset rail equilibrium — LTC premium
compresses to ~3% = its rail-cost advantage; live cross-asset dispersion trade LTC+9% vs BTC+5%**),
39588 (2016-09 inverse-premium era: foreign>domestic, arb domestic-only, 币看 monitoring).
tid 6991 (buy/sell-wall observation thread) 404s on thread-6991-1-1.html — recorded, dropped.
PENDING IN-RUN (screen-on-discovery duty): novelty-gate + Stage-A screen of the surfaced axis
**per-asset premium dispersion in a barriered market (KR per-asset KRW books — CN books are
USDT-only post-2021, mechanism not reconstructable in-region)**; graveyard/lexicon/operator routing.


**§33 dispositions (2026-08-18, owed-work batch3 — items above, in order):**
- Verify-queue disposition (queue-design leak finding): [§33: wired -> F0002] — rowed, fixed f9b50e36 2026-08-12
### 2026-07-30 session (PROSPECTOR, standing daily) — IN PROGRESS (write-first note; updated as items resolve)
Mine gate: BACKLOG-CLEAR (all 5 prior finds disposed; mining authorised). Generation priors read:
only measured class = data_axis_watchlist (50% conv, 0.25d latency) — favoured; nothing starved.
Verify-queue fresh check (30s, config-vs-outcome): kaiko_vwm_reference_rate.jsonl EXISTS (132 rows);
data/secrets/naver.json ABSENT → NAVER deferral to 2026-08-09 stands; F0002 (queue-design leak)
already rowed 07-28. Not re-derived a 4th time.

ITEMS THIS RUN (bounded per completion contract):
1. **RESUME THE DEAD RUN (§26/§33 obligation, Tier-1):** 07-28 session 2 died with the Stage-A
   screen of **per-asset KR premium dispersion** pending. Found on disk: data/kr_perasset_premium_history.jsonl
   (3,008 rows, 2018-05-04→2026-07-28, prem_btc/eth/xrp + disp_std + alt_minus_btc, fx_ffill flags)
   — built by the dying run, NEVER verified, NEVER screened, NOT in git (data/ gitignored; no
   committed builder). Plan: (a) verify-don't-trust — spot-check rows against primary sources +
   pin down candle-label alignment (bithumb KST-label lookahead is the graveyarded hazard);
   (b) novelty gate + manual graveyard check (aggregate KR premium retracted ~73% artifact — the
   CROSS-SECTIONAL construct cancels common FX/timing terms by construction, but venue-close
   mismatch is asset-specific and does NOT cancel: de-contam gate is load-bearing); (c) mechanism-
   appropriate targets = RELATIVE alt-vs-BTC returns (1d + 5d non-overlap), every cell a logged
   trial; (d) stage_a_screen per cell → stage_a_verdicts + research_memory + routing + commit.
   Folds in the Upbit-portal legitimacy read (backlog DECIDE item) as the data-provenance leg.
2. **ERA-ARCHAEOLOGY CONTINUATION (carried pointer #1):** 8btc forum-54 (汇率/行情 strategy board)
   thread-mining from the 713-tid catalog — next tranche to reply-depth, graveyard-check, route.
3. IF BUDGET REMAINS (search-space expansion ≥25%): KR-community ground survey (Coinpan/DCInside/
   Naver cafe quant-crypto layer) — new source class + mechanism-prior support for item 1's axis.
STATUS: run in progress — per-item results below.

#### ITEM 1 progress (durable mid-run state, 2026-07-30)
**(a) VERIFICATION COMPLETE, with a major institutional finding on the way through.**
- Orphan series data/kr_perasset_premium_history.jsonl: internally consistent (0/3008 mismatches,
  full 7-day calendar), 2021 squeeze forensics correct (+21.5% peak 2021-05-19, XRP tilt +24.4%).
- **BOUNDARY PROOF (primary evidence, Upbit's own hourly candles):** daily candle labelled
  `candle_date_time_utc=D` closes EXACTLY at 24:00 UTC D (match to the won on 2026-07-28 AND
  2021-05-19; ≠ the 15:00 UTC price). Upbit dailies are UTC-midnight-boundary, NOT KST-day.
  ⇒ open-date keying is SAME-INSTANT with Binance UTC closes; close-keying (the 2026-07-29
  canonical "fix" in libs/research/upbit_data.py) introduces 24h STALENESS, not leak protection.
  ⇒ live collect_kimchi_premium.py currently pairs legs 24h apart (Upbit close-keyed ∩ Binance
  open-keyed); rows appended since 07-29 measure −r_binance(D)+noise, not the premium.
  ⇒ kimchi retraction E-02f2917dfb's stated mechanism ("Upbit KST candles ahead of Binance UTC
  closes") is contradicted by primary measurement; a +1d-shifted premium is contemporaneous BY
  CONSTRUCTION (denominator mechanics), so the 0.823 +1d cell was expected, not leak evidence.
  Finding to be rowed with evidence; kimchi re-adjudication belongs to the brain, not this organ.
- **REBUILD = REPRODUCTION:** same-instant rebuild from primaries (Upbit open-keyed + Binance UTC
  + ECB USDKRW via frankfurter, ffill flagged) matches the orphan EXACTLY: corr 1.0000 on
  prem_btc/alt_minus_btc/disp_std, median diff 0, max diff 0.8bp over 3,008 common days.
  Orphan provenance = SOLVED (open-keyed + ECB FX). Screening the rebuilt file (full manifest).
- Construction trials logged (§26.3): T#1 close-keyed build → GARBAGE on volatile days (24h-stale
  leg; "+65.8% XRP premium" on 2021-05-19) — recorded failed. T#2 same-instant build → verified.
**(b) PRE-REGISTERED SCREEN GRID (declared BEFORE results; all cells logged as trials):**
  Signal legs all ≤24:00 UTC D (Upbit close 24:00 D, Binance close 24:00 D, ECB fix ~13:15 D
  ffilled — staleness common-mode, cancels in cross-section); target starts 24:00 UTC D. No lookahead.
  1. alt_minus_btc → next-day mean(ETH,XRP)−BTC rel return, h=1. Prior: NEGATIVE IC (KR retail
     alt-crowding reverts; mechanism = per-asset rail equilibrium, 8btc tid 63748 era evidence).
  2. alt_minus_btc → h=5 non-overlapping. Prior: negative.
  3. disp_std → h=1 rel target. Prior: negative (dispersion blowout = frenzy top).
  4. disp_std → h=5. Prior: negative.
  5. REALIGNMENT RE-TEST (L1.16a petition; named enabling change = boundary proof): z20(prem_btc)
     → next-day BTC, h=1 — original kimchi construction on the same-instant-verified series.
  ±1d shift sensitivity reported on any INTERESTING cell. Zero promotion authority throughout.

#### ITEM 2 — CLOSED (bounded tranche: 4 threads from the 713-tid catalog, mined via Wayback+GBK)
Candidates selected by strategy-term scan (21 hits; 15 skipped as one poster's daily 庄家 commentary
noise + fee announcements). Mined:
- **tid 5875 (capture 2014-06-26): OKCoin ships retail algo-execution tools** — 计划委托 (trigger),
  跟踪委托 (trailing), 冰山委托 (iceberg), 时间加权委托 (TWAP); led by 赵长鹏 (CZ, ex-Bloomberg
  Tradebook, then OKCoin CTO). ERA KNOWLEDGE: from 2014-06 the largest CN venue's tape contains
  systematically-sliced retail/institutional flow (iceberg+TWAP) and a VENUE-HELD conditional-order
  book. No card (execution-microstructure class already adjudicated: vpin_ofi REJECTED 2026-07-03).
- **tid 25692 (2015-11): retail theory that the venue feeds stop-cluster data (止盈点 concentrations)
  to short-side 庄家** who enter size at the cluster → cascade. Advice given: self-custody + never
  pre-set stops (they reveal your hand). CLAIM-grade suspicion, zero evidence — but documents (a)
  era belief in venue data leakage, (b) the liquidation-hunting mechanism EXISTING pre-perps
  wherever cluster data exists, (c) measurable behavioral reaction (stop-avoidance). Corroborating
  era provenance for the already-tracked liquidation_reversal family; no new card.
- **tid 2232 (capture 2014-01): BTCChina restores 0.3% fee** "防止炒作" = zero-fee era END; reply
  documents rail-closure SEQUENCING (财付通/Tenpay cut before bank cards). Adds intra-era ordering
  detail to the graveyarded fiat-premium barrier mechanics. Era knowledge; no card.
- **tid 37055 (2016-08): auto-trading-bot thread — capture holds the question post only, zero
  replies archived.** Route-negative (capture too early), not a content judgment.
DEPTH LINE item 2: 4 threads to their ARCHIVE depth (captures hold 0-2 replies — that is the
archive's truth; reply-chain≥2 not reachable on these captures). tid 5875 template-shell defeated
by direct postmessage-slice (regex needed attr-order-agnostic form — OP-020 refinement noted).
Catalog now 11/713 tids mined to capture depth; board-54 systematic exhaustion continues next runs.
[§33: screened -> docs/research/prospector_coverage.md] (era-knowledge routing, no tradeable cards)

#### ITEM 3 — CLOSED (search-space expansion slice, bounded)
NEW SOURCE CLASS: the **KR per-coin premium tracker ecosystem** — ≥6 live public dashboards
(kimpga.com, kimp.co.kr, cryprice.com/scolkg.com, coinsect.io, 94bit.com, "더따리"), surfaced by
the native-language key 코인별 김프 (OP-032: native language FIRST). Value: (a) BEHAVIORAL
COUNTERPARTY EVIDENCE for the kr_perasset axis — KR retail watches per-asset 김프/역프 in real
time, so premium tilts are attention objects, not accounting residuals; (b) catalogued to
data_universe_map (regional_venues_kr_jp; trackers are corroboration pointers — the desk
reconstructs from primaries, vendor-replacement doctrine); (c) KR LEXICON seeded into the
operator library (김프/역프/따리/코인별/재정거래/잡코인 — 6 terms, 3 confirmed-in-use).
NOT done this run (named, next-run ground): Coinpan/DCInside/Naver-cafe community deep-mining —
the discussion layer behind the trackers; era + diaspora angles apply (KR had no ban-event, so
the living web is the primary layer, unlike CN).

#### ITEM 1 (cont.) — PANEL FAMILY SCREEN, PRE-DECLARED BEFORE RESULTS
Universe: all fetched assets with ≥120 aligned days both legs (177 Upbit-kept, ex-BTC reference,
ex-pegged). ONE construction (declared): per-asset signal = prem_i − prem_btc (BTC-relative tilt;
FX + venue-close terms cancel exactly); per-asset target = next-day ret_i − ret_btc (same Binance
legs); harness = stage_a_screen per asset, h=1, zwin=20, defaults. Aggregation (descriptive only,
no invented verdict): N, median/mean IC, share positive, verdict-class counts, decontam pass share;
sign-test on share-positive with the declared caveat that assets are cross-correlated (common alt
factor only partially removed by BTC-relative construct). Multiplicity: 177 within-mechanism
variations of ONE pre-registered mechanism ≈ 1 independent cluster (§31.3); family report is the
deliverable; best/worst assets named as descriptives WITH the forking caveat, never promoted alone.
Interpretation rule (pre-declared): significantly >50% positive → "consistent-positive, brain
adjudication warranted (R-row)"; else honest null. Zero promotion authority either way.

#### ITEM 1 — CLOSED. Panel family result + final routing.
PANEL FAMILY (per pre-declaration above): N=175 assets, median IC **+0.0050**, mean +0.0053,
share-positive 94/175 (54%, sign-z 0.98 NS), median residual IC +0.0016, decontam passed 99/175,
verdicts {SCREEN-UNDERPOWERED:145, TIMING-ARTIFACT:30}. Tails (PUNDIX +0.24 … TFUEL −0.14) are
noise-order at N=175×~380d — descriptive only. **Pre-declared rule fires the HONEST-NULL branch.**
Novelty gate run for duty: 0.965 not-redundant (nearest kimchi 0.035; tool recall known weak —
manual graveyard check was the operative gate). Routed: family verdict row + 5 cell rows →
data/stage_a_verdicts.jsonl; rich report → reports/axis_screens/kr_perasset_premium.json;
research_memory rm-…41045b (+5 cell rows, 2 construction rows, kimchi re-test row); watchlist
entry with single trigger = **R0069** (brain adjudicates full-depth panel backfill + §26.5 clock).
[§33: screened -> data/stage_a_verdicts.jsonl]
NOTE for R0067 owner: screen_exchange_netflow.py:102 hardcodes the wrong retraction lesson text
("KST vs UTC candle labels") in its PriorIdea — include in the derived-registry correction sweep.
BACKLOG ANNOTATION (verify queue): Upbit REST primary route now VERIFIED at 400–1000d depth,
195-market breadth, 0 fetch failures — the "Upbit Historical Market Data portal" DECIDE item's
urgency drops (in-house reconstruction exists); decision still owed but nothing blocks on it.

### SESSION CLOSE 2026-07-30 — DEPTH LINE, BATTERY, STANDING TEST
DEPTH (per lead): kr_perasset axis — **exhausted for this run's declared scope**: provenance
solved by exact reproduction (3,008d), boundary proven from primary hourly data on two eras,
5 pre-registered cells + L1.16a re-test + 175-asset pre-declared panel run, all trials logged,
negatives first-class. Full-depth panel backfill is the ONE named remaining move (R0069 owns it).
8btc tranche — 4 threads to their archive depth (captures hold 0–2 replies; that is the archive's
truth); catalog 11/713 mined; board-54 exhaustion continues. KR expansion — survey depth only
(trackers catalogued, lexicon seeded); community layer (Coinpan/DCInside/Naver cafes) = named
next-run ground. NOT breadth-theater: two carried obligations closed to terminal state, one
expansion slice, zero re-surface-scanning.
PROACTIVE BATTERY (moves run → produced): (1) contingency — ECB/frankfurter named + verified as
KRW FX primary with Yahoo as fallback (collector currently uses Yahoo 250d; noted). (2) adjacency —
the private-keying shape: found fusion_engine.py:66 + signal_halflife.py:55 (R0068) after
upbit_data.py; also netflow PriorIdea stale text (noted above). (3) config-vs-outcome — the
boundary test itself: the canonical policy's factual premise had NO artifact behind it; demanded
one, got a refutation (F0015). (4) regression sweep — what this run made worse: two per-asset
series files now coexist (orphan + rebuilt, identical values); manifest cross-references written,
brain may delete the orphan at R0067 disposition. (5) cost-inversion — n/a this run (all free
primaries). (6) generalise-the-rule — blind_spot row: every alignment/keying policy module needs a
primary-evidence test artifact. (7) autonomy check — n/a. (8) negative space — per-asset KR
premium had NEVER been screened at width; now it has a permanent family record. (9) scope-the-
negative — family null scoped to recent-era-width ROUTE, not the full-depth capability (named
decisive experiment); tid 37055 scoped to capture-too-early. (10) ratchet check — conversion
ledger + stage_a_verdicts + research_memory + universe map + lexicon all grew; no floor fell.
STANDING TEST — "Which artifact on disk is different because of what was mined?":
data/kr_perasset_premium_rebuilt.jsonl + kr_perasset_legs_raw.json + kr_perasset_panel_400d.json
(new datasets, manifested), 11 stage_a_verdicts rows, 9 research_memory rows, F0015,
R0067/R0068/R0069, 1 blind-spot row, reports/axis_screens/kr_perasset_premium.json, universe-map
entry, KR lexicon section, paid-target Nansen line advanced, this note, watchlist. Cycle CONVERTED.

### 2026-08-01 session 3 (CN frontier miner) — IN PROGRESS (write-first note; updated as items resolve)
Mine gate: **BACKLOG-CLEAR** (`scripts/mine_gate.py`: all 7 carded finds disposed; mining authorised).
Verify-queue (30s config-vs-outcome, NOT re-derived a 5th time — F0002 already rowed 07-28): the 4
"VERIFY this cycle" items are the same standing-monitoring/dated-deferral cards; NAVER still
credential-blocked (deferral 2026-08-09 stands). None is CN-region or miner-actionable.
PRIOR CN STATE (resume rule): last CN session 2026-07-30. Carried un-exhausted grounds, in order:
(1) 8btc forum-54 era board — catalog 713 tids, **11 mined**, exhaustion continues; (2) **Gitee /
CN-GitHub repo chain per OP-001 — carried since 07-26 and NEVER STARTED across 3 sessions** (a §37
silent-carry defect, named here); (3) CN OSS tranche deeper pass (principal 07-31).

ITEMS THIS RUN (bounded per completion contract; depth per item unbounded):
1. **T1 INSTRUMENT DEFECT-CLOSER — the unverified-slang block (principal 2026-08-01).** The prompt
   ships 8 UNVERIFIED terms with an explicit warning that querying invented slang "would make a
   rich ground look picked clean". That is a **recall defect in this seat's primary instrument**,
   and it outranks any single dig: it multiplies every future CN run (charter §16 propagates it to
   the whole fleet). Plan: OP-030 negative-control every unverified term against live CN sources,
   promote/kill each, ADD the 4 verified-block terms missing from our lexicon table (大饼/糖果/
   空气币/山寨币), and A/B measured recall vs the translated-English key.
2. **CN OSS TRANCHE DEEPER PASS (principal 07-31, the seat's named job):** AlphaGPT
   `paper/20251226.pdf` (the tranche's only real target there) + Vibe-Trading issues #476/#331 +
   discussion #468 — mining for **DATA SOURCES the bounded extraction missed** and mechanism-
   carrying constructions. Screen-on-discovery in the SAME run for anything with a stated mechanism.
3. **VENUE DISCOVERY (standing obligation) + carried pointer #2 (Gitee/CN-GitHub OP-001 chain).**
   Every run must attempt venues NOT on the seed list; the seed list is a floor.
STATUS: run in progress — per-item results below.

#### ITEM 1 — CLOSED. Unverified-slang block negative-controlled: **0 of 7 survived.** [§33: wired -> docs/research/search_operator_library.md]
METHOD (OP-030/OP-037): positive control FIRST — 韭菜/割韭菜/庄家 and 大饼 queried by the same
pipeline returned abundant live text, so any later zero is attributable to the TERM, not to my
search method. Then each candidate quoted, in native context. Every construction tried is logged
below, not just the ones that printed.

**KILLED — 6 of 7, with the nearest REAL form named (that is where the value was):**
| supplied term | verdict | the real form |
|---|---|---|
| 牛季节 "cow season" | KILL — zero exact-match | 牛市 (bull mkt) / **山寨季·山寨币季节** (altseason, live: "山寨季节的味道越来越浓了") |
| 蜡烛猴 "candlestick monkey" | KILL — zero | 蜡烛图 (candlestick chart) and/or **猴市** ("monkey market" = choppy/range regime) — probable conflation of the two |
| 新葱 "new onion" | KILL — zero | 小白 / 新韭菜 |
| 韭菜盒 | KILL — **not a crypto term at all**; 韭菜盒子 is a FOOD (leek pastry) | **韭菜币** (leek-coin) is the real adjacent term |
| 狗商 | KILL — zero | **狗庄** — prompt's guess CONFIRMED, live 2025-09 usage on Gate square/Toutiao/Foresight |
| 大鳄鱼 | KILL — zero | **大鳄** — prompt's guess CONFIRMED (People's Daily 2021 "币圈大鳄") |
| "Kuisancle" | **UNRESOLVABLE** — not pinyin | 亏损 kuīsǔn (loss) is the probable intent but is STANDARD financial vocabulary, so it carries no search-key value either way. Recorded as unresolvable rather than force-fitted |

**THE FINDING IS NOT THE KILL LIST — IT IS WHY A BAD GLOSSARY IS WORSE THAN NO GLOSSARY** (OP-037):
querying invented slang does not merely waste a query, it returns a CLEAN ZERO, and a clean zero on
what looks like a native term reads as *"this ground has no coverage"*. Bad vocabulary makes a RICH
ground look picked clean and the seat then rationally deprioritises it forever. That is a
manufactured false exhaustion, and it was sitting in this seat's own primary instrument.

**NEW OPERATOR OP-036 — censorship-evasion slang has a BIRTH DATE; pick the key by ERA.** The run's
best find, and it came out of verifying a term rather than hunting a mechanism. CONFIRMED verbatim
by two independent CN sources: `最开始叫大饼的是比特天空的群，自从去年94事件之后，为防止敏感词语导致群被封，
比特天空让大家把比特币称之为大饼` — BTC became 大饼 **specifically so WeChat groups would not be banned
for typing a filtered word**, dated to the **2017-09-04 "94" ban**. Consequences for our own era ground:
  - post-2017-09 CN group/forum text searched for 比特币 systematically UNDER-RECALLS the exact layer
    that matters, because that layer deliberately stopped typing it;
  - pre-2017-09 archives searched for 大饼 return near-zero — the term did not exist yet, and that
    zero is a FALSE NEGATIVE about the era, not evidence of an empty archive;
  - **our 8btc/ChainNode/Tieba ground (2011-2021) straddles the event**, so every single-key search of
    it was guaranteed to half-miss regardless of effort — and would have read as "the archive is thin".
  §16 propagation: the mechanism is language-general, only the trigger event changes (KR 2017-12
  crackdown, RU post-2022 sanctions, TR 2021 payment ban). Standing question added for every region
  seat: *what regulatory event hit this ground, and what did the vocabulary do on that date?*

**LEXICON: +14 rows to the operator-library table**, all confirmed in live text this run, incl. the
COIN-NICKNAME EUPHEMISM CLASS which is the layer that never types a ticker — 大饼 BTC, 二饼/姨太 ETH,
太子 BCH, 末日战车 ETC, 柚子 EOS, 辣条 LTC. **Trap recorded: 薄饼 is PancakeSwap, NOT bitcoin** — a
near-homograph of 大饼 meaning something unrelated. Also added the manipulation-mechanics set
(洗盘/控盘/诱多/诱空/砸盘 — 控盘 "float control" is the mechanism-bearing one), the regime term 猴市,
and the retail-positioning set (套牢/踏空/割肉/装死/纸手/钻石手).
SCREEN-ON-DISCOVERY: nothing to screen — item 1 produced an INSTRUMENT upgrade (recall), not a data
axis or a mechanism. Stated plainly rather than manufacturing a screen to look productive.

#### ITEM 1 DEPTH OVERFLOW — the layer past where I would have stopped. [§33: screened -> data/unlock_event_screen.json]
An operator written and never tested is the built-never-wired defect, so I spent OP-036 and the new
lexicon on live ground instead of banking them. Two things came back.
(a) **OP-036 era-key test:** `site:8btc.com 大饼` DID return era forum threads — incl. `thread-44638`
    *"真够疯的，国内外价格相差8-10%"* (domestic-vs-foreign price gap of 8-10%), which is banzhuan-era
    CN-premium material on our own carried ground, and `thread-87728` on whale mechanics. HONEST
    CAVEAT: this is weak evidence for the operator — the engine does semantic matching, not
    exact-key matching, so I cannot claim from it that the euphemism key beat the ticker key. The
    operator's ERA-DATING logic rests on the two verbatim origin sources, not on this test.
(b) **The real overflow: 控盘 carried NUMBERS, and they landed on a dataset we already owned.**
    CN practitioner lore states float-control thresholds (~10% to move a thin book short-term, 30%
    medium, 50%+ for a full cycle) and that low-circulation coins are the manipulable ones. Numbers
    with a mechanism are the class that converts here (spoken/forum sources: MECHANISMS 0/13,
    NUMBERS 4/4). That is a conditioning prior for `data/unlock_events.json` — **24,201 events,
    s13-passed, ZERO python readers, sitting unused since 2026-07-24.**
    NOVELTY GATE: PASSED — no unlock/vesting row anywhere in the graveyard.
    MECHANISM: insider/private-sale vesting delivers tokens to a ~zero-cost-basis holder on a
    contractually fixed PUBLIC date; they cannot sell before receipt and fund lifecycles force
    distribution. Forced seller on an immutable schedule — the funding/carry shape, not price-pattern.
    **SCREENED IN THE SAME RUN via the §42 event-study path** (an unlock is ~2 non-zero days in 30;
    judging it on a continuous daily statistic is the error that gate exists to prevent).
    **RESULT: 0 of 27 pre-registered cells pass** — all 27 logged, not just the best, `n_cohort=27`.
    Powered cells are a genuine null (best |t|=1.32 vs bar 2.24).
    **BUT THE VERDICT IS *UNMEASURED*, NOT *DEAD*, AND FOR TWO REASONS I DID NOT EXPECT:**
    (1) `pct_circ_now` is a % of **TODAY's** circulating supply applied to events back to 2016 —
        supply grows, so old unlocks that were huge shares of float at the time record as small
        ones, structurally emptying the ≥10% bucket (insiders ≥10%: 14 events; ≥30%: **0**). The
        conditioning variable is unknowable at event time. Clean prospectively, contaminated
        historically. (2) It is a SNAPSHOT, not a series: forward calendar runs only to
        **2026-08-23** with **zero** ≥10% events, so the forward test the mechanism needs cannot be
        run from it and the file expires in three weeks.
    NOT graveyarded — nothing was refuted, and a false kill would poison the novelty gate against a
    live mechanism and corrupt family survival stats (L1.18a reasoning applied to a null).
    Routed: axis card + narrow re-entry condition in `data_axis_watchlist.md`, collector rowed
    **R0288**, `rm-20260801T125319-a95125`.
    **TRANSFERABLE LESSON:** check the as-of date of a ratio's DENOMINATOR separately from its
    numerator. A `_now` field joined to historical events is a silent look-ahead in the
    *conditioning* variable even when the return series is spotless — and it fails toward a FALSE
    NULL, which is the direction no gate on this desk would ever catch.

#### VENUE DISCOVERY (standing obligation — harvested from inside results, NOT from the seed list)
Recorded with first-pass verdicts so no seat re-spends on them. The seed list is a floor.
| venue | what lives there | how found | verdict |
|---|---|---|---|
| **maimai.cn** (脉脉) | CN professional/workplace network, semi-anonymous. Surfaced `揭秘主观做市商：江湖雅称"狗庄""操盘手""大内资金总管"` — a **market-maker insider writeup**. CN analogue of Blind/Glassdoor: insider talk + **job postings**, which L1.34 names as leaking infrastructure and strategy families | 狗庄 query | **RICH — and a NEW VENUE CLASS for this seat.** OP-007 (ex-employee/insider layer) had no CN venue until now; every prior CN session mined forums and repos only |
| **otcbtc.zendesk.com** | Help-centre docs of **OTCBTC, a defunct CN OTC exchange**, incl. step-by-step 搬砖 (banzhuan) arb walkthroughs that survived the venue | banzhuan query | **RICH for era-archaeology** — a dead venue's own docs are primary era material and were never on our list |
| **xiarj.com / 闽发论坛** (Minfa) | Old CN stock forum; carries `威科夫控盘法详解` (Wyckoff float-control, multi-part) | 控盘 query | THIN-to-RICH, unmined — CN *equity* lore is the source of the 控盘 vocabulary crypto inherited |
| tokenairdrop.org · kttg.pro · candy666.top · bicoin8.com | 糖果/空投 aggregators — airdrop calendars, "首码" new-project feeds | 糖果 query | THIN as alpha, but they are **event-calendar feeds**; adjacent to `unlock_events` and same forced-supply family |
| huoxing24.com (火星财经) · tuoluo.cn (陀螺科技) · blockweeks.com (区块周刊) · 528btc.com (币界网) | CN crypto media + market analysis | 庄家/大饼 queries | THIN individually; useful as **positioning intelligence** (what CN retail is being told) |
| jb51.net/blockchain (脚本之家) | Unglamorous CN dev-tutorial site carrying the **single richest slang glossary** found this run | 黑话 query | RICH-for-lexicon — the boring-source lesson (L1.35) paying out literally |
| cngold.com.cn (中金网) | Carried the verbatim 大饼 origin text | 大饼 origin query | THIN but load-bearing — one of OP-036's two sources |
| **zhuanlan.zhihu.com** | — | — | **WALLED from this VPS: HTTP 403 on article fetch.** Zhihu SEARCH results are readable, article bodies are not. Scoped as a ROUTE failure, not a capability failure (L1.25a / battery #9) — glossary content was obtained free elsewhere, so **no paid unlock is justified and nothing is video-locked** |

#### ITEM 2 — CLOSED. CN OSS tranche deeper pass: **the tranche's two headline targets are REFUTED, and the real find was a feed stack nobody was looking for.** [§33: screened -> docs/research/data_axis_watchlist.md]
Licence gate first: AlphaGPT Apache-2.0, Vibe-Trading MIT, NOFX AGPL-3.0 — all read from the LICENSE
blob, no hard stops. Nothing cloned, installed or executed; all read as text (supply-chain rule).

**(a) THE 07-31 NOTE'S "ONE REAL TARGET" IS NOT WHAT IT SAYS IT IS.** `AlphaGPT/paper/20251226.pdf`
is *"Defense in Predatory Markets: A Differential Game Framework for AMM Liquidity via Uniswap V4
Hooks"* — **not a factor-mining paper at all**. Its entire "extensive empirical validation" is 1,000
Monte-Carlo paths of a synthetic jump-diffusion: **zero real observations**. And it is internally
broken in a way that settles how to read it — Proposition 1 states the attacker's optimal injection
*decreases* in the fee, while its own proof derives the opposite and says, verbatim and unedited,
*"This seems counterintuitive. Let's re-examine... So σ_sol(φ) is \*increasing\* in φ."* The abstract
calls it zero-sum; §IV.B says *"Ah, the initial modeling as zero-sum was an oversimplification."*
First-person LLM self-correction left inside a formal proof. **Unreviewed LLM output — do not cite
its numbers anywhere.** The repo's actual method is a REINFORCE Transformer emitting RPN formulas
over **6 price features**, scored in-sample with no train/test split — the 420/0-refuted class, with
full-sample normalisation leak. *Useful negative:* it independently reproduces five defect classes
we already name, which is corroboration that **our 420/0 rejections were correct**.
⚠ `times.py:13` carries a **hardcoded live Tushare token** — someone else's credential. Never use it.

**(b) THE NOFX "3 MECHANISM CONSTRUCTIONS" CLAIM IS REFUTED — and the failure mode is instructive.**
0 of 3 are constructed in that repo. The 07-31 note's signature phrase *"the crowd's fuel and walls"*
is **verbatim marketing copy from NOFX's own README line 70** — the note was quoting a README and
reporting it as a code reading. Two of the three are a single purchased endpoint
(`claw402.ai/.../cost-liquidation-heatmap`); cross-exchange net flow **does not exist** in the code.
**That section of the 07-31 note is retired as secondhand.** Governance: SlowMist-confirmed 2025-11
incident (admin_mode default true, `/api/exchanges` returned API keys unauthenticated, >1,000
publicly reachable deployments, coordinated key revocation) — never run it on a key host.

**(c) HONEST NULL on the tranche's stated purpose:** Vibe-Trading's crypto layer is **strictly weaker
than ours** — OHLCV + funding history only, with no order-book, no trade-tape and no liquidation
collector anywhere. Nothing to take. The tranche was mined for what it was catalogued for and it
was not there; recorded as a null rather than dressed up.

**(d) THE ACTUAL FIND — a keyless CN alt-data stack, 6 endpoints verified live, up to 26 years.**
`datacenter-web.eastmoney.com` / `push2his.eastmoney.com`: margin balance 融资融券 (2010-03-31→2026-07-31,
~6.69M rows), block trades 大宗交易 (2000-08-29→, ~678k), dragon-tiger 龙虎榜 (2004-06-25→, ~264k),
**lockup expiry 限售解禁 (forward calendar TO 2035, ~34k)**, shareholder count, size-bucketed fund flow.
**§13 IS NOT SATISFIED AND I HAVE NOT TREATED IT AS IF IT WERE:** these are undocumented internal
APIs with **no stated terms**, and "no terms stated" is not "licensed". Routed as a legitimacy
DECISION (**R0290**), not carded as clean.
**WHY IT MATTERS IF IT CLEARS, and this is the run's neatest convergence:** `RPT_LIFT_STOCK` is the
**same forced-supply mechanism** my own item-1 overflow screened in crypto — except with 26 years of
history *and* a forward calendar to 2035, which is exactly the two things the crypto unlock snapshot
lacked. The cheap ordering is therefore to validate the mechanism on the deep clean panel BEFORE
paying for a crypto collector (R0288). Two datasets, one mechanism, both currently unexploited.

**(e) GeckoTerminal — keyless, and the one axis that cannot be bought later.** `/trades` returns
**wallet-resolved signed DEX flow** (`tx_from_address`, buy/sell `kind`, `volume_in_usd`, `tx_hash`) —
true signed order flow with counterparty identity, free. **But retention is 300 trades / ~17h of 1m
bars, so it is FORWARD-ONLY-UNRECOVERABLE: every hour not recorded is gone at any price.** Measured
burst limit ~3 rapid calls then 429 (documented 30/min). Our `data_universe_map.json` has **zero**
entries for geckoterminal/birdeye/dexscreener and our collector inventory has **no DEX-native host
at all** — the entire pool- and trade-level on-chain axis is uncovered.

**(f) TWO CORRECTIONS TO STANDING DESK MATERIAL, both verified at primary source:**
  1. **Northbound Stock Connect flow is DEAD** — probed over 400 sessions (2024-11-20→2026-07-31):
     `hk2sh` all zeros, `hk2sz`/`s2n` one non-zero each; daily net-purchase disclosure **ceased
     2024-08-16**. This refutes the top-ranked component of the 07-31 note's axis #1.
  2. **`run_leakage_test` is blind on the axes we actually trade — VERIFIED MYSELF, rowed R0289.**
     `libs/features/validation.py:91-99` mutates only `["open","high","low","close"]`. Our bronze D1
     schema is `timestamp/open/high/low/close/volume/taker_buy_frac/funding/basis` — so **4 of 9
     columns are never perturbed and any feature built on them passes the future-invariance test
     trivially, leak or no leak**, while `causal_guard.py`'s docstring claims the test "rejects
     future leakage, lookahead bias, hindsight labels, and full-sample normalization".
     **Funding/carry is this desk's only repeat survivor**, so the one family that works is the one
     the guard cannot see. UNMEASURED-REPORTED-AS-OK (L1.40): it returns PASS where it owes UNKNOWN.
     Concrete trigger found: Eastmoney's dragon-tiger rows ship `D1..D30_CLOSE_ADJCHRATE` —
     **vendor-precomputed forward returns in the same row as the features** — and in-row leakage is
     invisible to an across-row invariance test by construction.

⚠ **SAFETY, recorded so no seat repeats it:** `discord.gg/2vDYc2w5` (the old Vibe-Trading README
invite) is a **hostile impostor server running a wallet drainer** — disowned by a repo collaborator
in discussion #265. Do not join. Official venue is `discord.gg/6TdQnT5xcF`. **Honest null on venue
discovery here: no QQ, Telegram, Slack, forum or mailing list exists for this project.**

#### R0289 UPGRADED FROM REASONED TO **DEMONSTRATED** (battery #3 — demand the artifact, never the claim)
The leakage-guard finding arrived reasoned-from-source, which is not the same as measured, so I ran
it against the real bronze schema. Reproducible in-repo via `libs.features.causal_guard.check_causal`:
```
CONTROL   close.shift(-1)            -> ok=False  n_leaked=23   correctly CAUGHT
DEFECT    funding.shift(-1)          -> ok=True   n_leaked=0    LEAKS, REPORTED CLEAN
          basis.shift(-1)            -> ok=True   n_leaked=0    LEAKS, REPORTED CLEAN
          volume.shift(-1)           -> ok=True   n_leaked=0    LEAKS, REPORTED CLEAN
          taker_buy_frac.shift(-1)   -> ok=True   n_leaked=0    LEAKS, REPORTED CLEAN
WORST     funding[-1] broadcast      -> ok=True   n_leaked=0    reads the FINAL BAR of the whole
                                                                 series and is REPORTED CLEAN
          full-sample z(funding)     -> ok=True   n_leaked=0    the EXACT leak class the docstring
                                                                 names as rejected
```
The control failing correctly proves the harness itself works — **only its column coverage is
broken**. And the reason this survived: `causal_guard.self_test()` builds its fixture from
`open/high/low/close` ONLY, so *the test that exists to prove the guard bites is structurally
incapable of revealing what it is blind to*. That is a sharper variant of this desk's own recorded
lesson — unit tests prove a mechanism works and say nothing about its coverage.
**ADJACENCY SWEEP (battery #2 — one instance is never one instance):** swept for the same shape
(`a checker enumerating a hardcoded subset of its input space while reporting PASS on all of it`).
`libs/features/validation.py:91` is the **only** literal OHLC-list instance in `libs/` + `scripts/`,
and `check_causal`/`assert_causal` inherit it rather than repeating it — so the blast radius is one
module with three entry points, not a family. Reported as a bounded null, not left unstated.

#### ERA-ARCHAEOLOGY — `8btc thread-44638` mined to reply-depth. GROUND EXTENDED. [§33: screened -> docs/graveyard.md corroboration]
Surfaced by the OP-036 era-key test and **not in our 713-thread catalog** (that catalog covers board
`forum-2` only) — so the era ground is larger than the catalogue implies. Wayback capture
`20170107145729`, declared `gb2312`, GBK-decoded per **OP-033** (confirmed again — UTF-8 renders it
as mojibake). 15 post bodies recovered; the reply chain is where everything below lives.

**WHAT IT IS:** January 2017, a live CN-premium episode at **8-10%**, argued out by practitioners.
**THE MECHANISM, stated by the participants themselves:**
- *"人民币废纸了，美元买不到了，有钱人纷纷借比特币出逃，怎么不要价差大啊"* (BigArnold, 2017-01-05) — RMB
  debasement fear plus **inability to buy USD** drives capital flight through BTC. That is the
  demand side of the premium, named explicitly.
- **THE BARRIER, which is why it did not close** — *"这想法可能性不大，成本太高了，单是币价相差8-10%，还有国外
  交易所的实名制防洗钱的问题比国内严得多"* (神级人物): beyond the 8-10% gap, **foreign venues' real-name/AML
  requirements are far stricter than domestic** — and *"美元充值很慢，有的要1天，有的要3天"* (空军2号): USD
  funding takes **1–3 days**. Latency and permissions, not price.
- **IT IS EPISODIC, not a level:** *"上次冲8000的时候，国内交易所差价都五六百，现在基本没差价呢"* — the spread
  appears during rallies and collapses to ~nothing otherwise. And it recurs across eras:
  *"新韭菜吧，13年也是这样的"* / *"去年也这样过"* / *"差价百分之十很正常"*.

**VALUE: this CORROBORATES an existing graveyard kill from the other side of the trade.**
`era_crossvenue_fiat_premium_arb` concluded a persistent cross-venue premium is *"rent on a
capital-control / withdrawal / counterparty barrier — compensation, not inefficiency, harvestable
only by whoever holds the specific rail access."* That was derived from **English** Bitcointalk
threads written by outsiders flying cash INTO China. This is the **CN-language, mainland-resident
view of the same barrier in the same era**, and it independently names the identical three
frictions — and the participants themselves conclude the arb is not worth doing (*"成本太高了"*).
Independent-source corroboration of a kill is worth recording: it converts a one-region conclusion
into a two-region one. **No new graveyard row** — nothing new died, and duplicating a kill would
corrupt the family survival statistics.
**Direct attribution value (L1.16)** for our live axis #76 `usdt-cny-otc-premium`: this is *why* it
is episodic and barrier-scaled, from primary era text.

**TWO INSTRUMENT CONFIRMATIONS, both free:**
1. **新韭菜 appears organically in 2017 practitioner text** — independent confirmation of item 1's
   kill of the invented 新葱, from a source that predates the glossary by nine years.
2. **OP-036's era-dating rule survives its first contact with real era text:** this is a *pre-94*
   thread (2017-01) and it uses 比特币 throughout, **not 大饼** — exactly as the rule predicts, since
   the euphemism was not born until 2017-09. n=1, so this is corroboration, not proof, and it is
   labelled as such.

#### ITEM 3 — CLOSED. Gitee / CN-GitHub chain: the §37 silent-carry defect is DISCHARGED, and the wall was never real. [§33: wired -> OP-038 + R0292/R0293]
Carried and never started across **3 sessions** — named as a defect in this run's header, so the
first duty was to find out *why*. **The answer is that it looked walled and was not.** Gitee HTML sits
behind a JS anti-bot shim: WebFetch → **HTTP 405**, curl → empty `<body>`, and the API *search*
endpoint returns `[]` without a token. Four independent signals all reading "walled". Three keyless
routes work fine (metadata+licence, recursive file tree, raw source) and carried the entire session
— written up as **OP-038**, because the general lesson is that *a JS wall on the HTML is not a wall
on the API*, and grading a ground WALLED on the HTML alone is OP-037's false-exhaustion by another
door. §13 boundary explicitly held: these are the platform's own public unauthenticated endpoints;
no access control was crossed and no closed group entered.

**BEST FIND — VERIFIED MYSELF AGAINST THE LIVE API, and it is on a venue we actually trade (R0292).**
`fapi/v1/exchangeInfo` carries **123 PERPETUAL symbols with a real `deliveryDate`** (≠ sentinel
`4133404800000`), **all `status=SETTLING`**, spanning **2022-06-17 → 2026-07-02** — by year 2022:3,
2024:21, 2025:45, **2026:54**, an accelerating ~1/week. `run_listing_watch.py:33` filters
`status == "TRADING"`, so **0 of 123 survive**; delistings are caught only as a set-difference *after*
the symbol vanishes, and `deliveryDate` is discarded. `grep deliveryDate` across `scripts/`+`libs/`
= **ZERO hits over 11 `exchangeInfo` consumers.**
So a complete **123-event delisting forced-close panel with exact settlement timestamps is
retroactively buildable TODAY from one keyless call we already make daily** — no new feed, no §13
question, no collector to build. The source claimed it needed *forward* collection; that is refuted —
Binance retains delisted contracts in the live payload. **Same defect class as the `min_len`
truncation and `limit=30`: the data was already inside a payload we fetch, and a filter threw it away.**
Mechanism: delisting forces every holder to close by a hard published deadline. Test *three* separate
hypotheses (initial impulse / drift to settlement / rebound) — they may carry opposite signs, since
some tokens fully recover within 24h. **Caution recorded:** delisting candidates are by construction
the illiquid cohort our execution layer handles worst — the two execution-denylisted symbols are
exactly this type — so any edge must be net of a real slippage model.

**SECOND DEFECT (R0293) — funding-clamp saturation is unrepresented anywhere on the desk.** OKX
publishes per-instrument `minFundingRate`/`maxFundingRate` via `priapi/v5/public/funding-rate-all`
(**521 instruments in one keyless call**; the documented per-`instId` route we use at
`run_cost_hunt.py:111` does **not** return these fields). The clamps are **three-tiered, not
constant**: ±0.375% (2), ±0.75% (17), **±1.0% (502)**. `collect_tail_funding_divergence.py` studies
funding gaps **on the thin tail** — precisely the cohort pinned at the ±1.0% cap — and there is
**zero** clamp handling anywhere in `scripts/` or `libs/`. A **censored** funding print read as an
extreme signal is a measurement error, not an edge, and a constant-threshold "extreme funding" rule
mis-classifies 502 of 521 instruments. Saturation is also a candidate *regime flag* in its own right:
pinned funding can no longer pull perp to index, so the basis must close via spot flow or forced
deleveraging instead.

**NEW DATA AXES (verified live, keyless) — HTX is absent from every desk collector:**
`api.hbdm.com/linear-swap-api/v1/swap_batch_funding_rate` returns **all USDT-M symbols in one call**;
`swap_historical_funding_rate` gives **6,330 rows / 5.78y** (USDT-M, epoch 2020-10-21) and **6,960
rows / 6.35y** (coin-M). Gate is likewise absent (`api.gateio.ws/api/v4/futures/usdt/tickers`, all
perps + indicative funding; history capped at ~30d, `limit=1000` silently ignored).
**CFFEX named-broker position rankings** (`cffex.com.cn/sj/ccpm/...csv`, GBK, epoch **2010-04-16**,
16.3y, all 7 products): daily **named-firm long AND short open interest** — no Western venue
publishes this (CFTC COT is weekly and category-level). Genuinely moat-class, though not our market.

**FACTOR CONSTRUCTION WORTH CARRYING (mechanism + transferable):** 筹码分布 / chip-distribution
cost-basis reconstruction, algorithm extracted from `akshare` (MIT): 120-day window, 150 price bins,
each day deposits a triangular kernel around `(O+H+L+C)/4` scaled by turnover, decaying the prior
distribution by `(1 − turnoverRate)`. **It is not a feed — it is computed from OHLCV alone**, so it
reconstructs a cost-basis distribution for **every CEX-only altcoin perp where on-chain URPD does not
exist**. Mechanism: disposition effect — holders trapped just above spot are the supply overhang.
*Caveat this desk must apply to itself:* the disposition effect is a BEHAVIOURAL pattern, not a
forced flow — nobody is compelled — so it owes the gauntlet like anything else and must not be
carded as forced-supply.

**HONEST NULLS, and they are most of the ground:** `tianx123/FMZ-strategies` — 573 files, **25%
literally named for the refuted class** (MACD/RSI/KDJ/Bollinger/Donchian/Dual Thrust/海龟/网格×6/
马丁格尔×3); its forks are **mirrors, not diverged** (same dead tree, no added code).
`hugo2046/QuantsPlaybook` (5.7k★) — **~90% refuted-class**, incl. RSRS which this desk already
EV-killed. `insoteam/samaritan` — MIT and clean, but its entire venue list (BTCC, CHBTC, OKCoin.cn,
Poloniex, Huobi-legacy) is 2017-era and **dead**. FMZ `GetData("SPOTPRICE"/"BASIS")` is
**platform-internal only**, not a fetchable endpoint. **ECOLOGY SHIFT:** `yutiansut.com` is fully
dead (HTTP 000), which silently breaks QUANTAXIS's `QATdx/QAThs/QAQAWEB` symbol-list fetchers —
do not build on them.

**LICENCE GATE — HARD STOPS RECORDED (§13 is absolute):** `dromara/northstar` and
`yunjinqi/backtrader` are **GPL-3.0** → read-only, no code lift. `tianx123/FMZ-strategies`,
`hugo2046/QuantsPlaybook`, `mrkanhai/oskhquant`, `CodeBang01/Ashare` carry **NO LICENCE** → all
rights reserved by default → **text-mine only, never vendor**. FMZ 文库 articles are © INVENTOR PTE
LTD. Clear: `akshare` **MIT** (the CN endpoint atlas), `adata` Apache-2.0, `QUANTAXIS` MIT,
`starquant`/`EliteQuant_R`/`rqalpha` Apache-2.0.

**VENUES — the CN community layer is overwhelmingly WALLED, and that is itself the finding.**
Seven QQ groups (QUANTAXIS 563280067 / 773602202 / 945822690, VeighNa 262656087), three 知识星球
(paid: AkShare, northstar, QuantsPlaybook), and multiple WeChat groups/公众号 (QAPRO,
quantitativeanalysis) — **all recorded as WALLED, none entered**. `discord.gg/mkk5RgN` (QUANTAXIS,
1,611 members / 14 online — metadata read via the public invite API, not joined): **THIN**.
`vnpy.com/forum/` is **public and THIN** — 4 boards sampled, ~95% install/API-debug traffic, and the
entire 价差交易 board is module debugging: a *tooling* community, not a research one.
`yutiansut.com:3000` (QUANTAXIS CLUB): **DEAD**. `fmz.com` 文库 digests: RICH-ish, and the digests
are the good part. **The structural read: CN quant's real discussion has migrated into paid and
identity-gated enclosures (知识星球, QQ, WeChat), which the §13 gate puts permanently out of reach.
That is a durable constraint on this region, not a gap to be closed — and it means the OPEN CN layer
worth mining is repos, era archives and platform 文库, not live community.**


**§33 dispositions (2026-08-18, owed-work batch3 — items above, in order):**
- Northbound Stock Connect flow DEAD (400 sessions probed, disclosure ceased 2024-08-16): [§33: screened] — refutation recorded on the card, data_axis_watchlist.md:1604
- 新韭菜 organic in 2017 text: [§33: n/a -> evidence line under its ITEM's tag]
- OP-036 era-dating survives first contact: [§33: n/a -> OP-036, search_operator_library.md]
### SESSION CLOSE 2026-08-01 session E (EN frontier miner) — DEPTH LINE, BATTERY, STANDING TEST

**STANDING TEST — "Which artifact on disk is different because of what was mined?"**
`docs/graveyard.md` (`era_olps_olmar_portfolio_selection`, with its L1.16a re-entry condition),
`data/olps_era_mechanism_test.json`, `data/olps_olmar_crypto_run.json`, OP-035 in the operator
library, 2 research-memory rows (rm-20260801T122725-080a44 rejected / -a80d0a validated),
R0286 + R0287 in the recommendation ledger, the improvement-inbox pointer, and this note.
**Cycle CONVERTED** — and the conversion is a KILL plus a REFUTATION, both first-class (L1.17).

**DEPTH LINE (honest, per mandate):**
- `olmar-implementation-fixed-bug` (2014, 65 posts): **EXHAUSTED** — reply-chain depth is what
  surfaced Bin Li, the paper's own author, conceding the weight-collapse defect. Surface would
  have given a code listing and nothing else.
- `comparing-olps-algorithms-olmar-up-et-al-dot-on-etfs` (2019, 40 posts): **EXHAUSTED** — the
  headline is a comparison notebook; the value is at reply 24, where a third party recomputes a
  190% headline to 58% on capital actually utilized, and at reply 30 where the community
  *"utterly amazed that we are all so blindly trusting"* records its own methodological collapse.
- `odd-behavior-olmar-algorithm-and-commissions` (2014, 7 posts): **EXHAUSTED**; citation chain
  followed out to zipline#128, quantopian/quantopian-algos, `cais.ntu.edu.sg/~chhoi/olps/`,
  JMLR li11b (the PAMR/CWMR predecessor), NIPS 5436.
- OLMAR cluster as a whole: **17 of 20 captures remain** — NOT exhausted, and no such claim made.
- Quantopian archive as a whole: **mapped, NOT exhausted** (52,187 threads).
- Wilmott: **MAPPED, NOT mined** — board map + 50 sampled titles only; 5,868 mineable threads.
- MECHANISM DEPTH beyond the text: the era's qualitative claim was converted into a quantitative
  measurement on our own lake. That is the layer past where the dig would normally stop.

**NEXT RUN TAKES FIRST (the chain — do not re-surface-scan the above):**
1. **Wilmott f=38 Trading + f=44 Code Library title harvest to completion** (~2,300 threads; the
   board map and the working `itemlist__item` selector make this cheap now), then mine the
   execution/microstructure seam — `t=100271` limit-order fill probability is the named entry.
   Wilmott's derivatives crowd is the desk's best EN ground for EXECUTION reality, not alpha.
2. **OLMAR cluster remainder** — `long-slash-short-olmar-hack` (2020, 33KB, the long/short variant
   the graveyard row's re-entry condition would have to beat) and `mean-reverting-excess-returns-
   olmar-idea`. Both are now cheap and both are potential re-entry-condition evidence.
3. "Quality Companies in an Uptrend" (still carried from session D — carried TWICE now, name it
   again next run rather than letting it go silent a third time).

**STANDING DIASPORA QUESTION:** unchanged and still open — the QC "Amazing returns" superthread
(did In&Out survive the 2022 bond crash, the natural experiment the era never saw). Wilmott adds a
second diaspora question: Wilmott is a LIVE forum that went 403-to-bots, so its practitioners are
still somewhere — the board map shows Careers (1,717) and Events (475) boards, which are where
migration announcements live.

**VENUE DISCOVERY (standing obligation — the seed list is a floor):** attempted and honestly THIN
this run. Harvested from inside the threads mined, not from the seed list: `cais.ntu.edu.sg/~chhoi/
olps/` (the OLPS authors' own project site + toolbox — an academic-lab venue, RICH for this family
and the canonical index of every OLPS variant), `github.com/quantopian/quantopian-algos` (the
era's official algo repo, RICH), `nbviewer`-hosted `github.com/paulperry/quant` (a practitioner's
own comparison notebooks, RICH), `github.com/Marigold/universal-portfolios` (Vinkler's
implementation + thesis, named in-thread). Verdicts recorded here so nobody re-spends on them.

**PROACTIVE BATTERY (moves run, honestly reported — a move that produced nothing is named):**
- **#2 ADJACENCY — PAID OUT, on our own code.** The era's int/float commission cast → hunted the
  same convention-constant shape in our tree → `growth_leverage.py:124` mixes ppy-annualized
  cagr/ann_vol with a hardcoded 252-day ruin horizon. Rowed R0286.
- **#3 CONFIG-VS-OUTCOME.** Every claim above names its artifact. Specifically: the Quantopian
  backtest stat tables are AJAX-loaded and every captured value is the placeholder `--`, so era
  performance numbers in that archive are CLAIMS, never platform-computed stats (written into
  OP-035). This is why the era's own in-thread RECOMPUTATIONS are the valuable objects.
- **#9 SCOPE THE NEGATIVE RESULT — twice.** Wilmott 403 was scoped to "this VPS is blocked on the
  live site", NOT "Wilmott is inaccessible" (14,890 threads say otherwise). The zero-title
  extraction was scoped to "wrong selector for this skin", NOT "the board pages are empty".
- **#4 REGRESSION SWEEP — what this run made worse:** the graveyard gains a long row whose
  dispersion caveat MUST travel with any citation of it; mitigated by writing the caveat into the
  row's own lesson field rather than relying on a reader's memory. R0286/R0287 add 2 rows to a
  conversion queue the desk already measures as over-subscribed — real cost, named, not hidden.
- **#10 RATCHET CHECK.** Two counts this run beat their recorded predecessors and should not fall:
  OLMAR captures located 9 → **20**; EN region grounds with a mapped board structure 1 (Quantopian)
  → **2** (+Wilmott). Both are floors.
- **#1/#5/#6/#7/#8 produced nothing beyond the above this run — reported as such, not skipped.**

**COMMIT STATE — READ THIS IF THE ARTIFACTS BELOW ARE MISSING (concurrency hazard, R0135 class).**
Item 1's kill landed in commit `6e4c9b2` (graveyard + both data artifacts) and the write-first note
in `e995cb3`. **The remaining output — OP-035, the inbox pointer, and this entire session note —
was still uncommitted at session close because a SIBLING session left an open `git merge`
(`MERGE_HEAD` → `3bf89cd`) across ~50 files including `libs/execution/binance_live.py`.** Its
conflicts were resolved (0 `UU`) but uncommitted, and git refuses a partial commit during a merge,
so the only way to save this note would have been to AUTHOR the sibling's unreviewed money-path
resolution as my own commit. Under L1.38 (sterile cockpit) and this seat's research-only freeze
that is not mine to do, so I declined and left the merge alone. All four touched docs are backed
up at `/tmp/olmar/backup/` (`prospector_coverage.md`, `search_operator_library.md`,
`improvement_inbox.md`, `graveyard.md`); restore from there if the merge was aborted rather than
committed. Four Claude sessions were live in this tree during this run.

**SEAT-EXHAUSTION CHECK (L1.35):** false, as always. Named un-exhausted ground at close: 17 OLMAR
captures, 52,187 Quantopian threads, 5,868 mineable Wilmott threads, EliteTrader and Nuclear
Phynance never touched, Kaggle G-Research and Numerai post-mortems never touched, the Academic
(SSRN/arXiv) family still never touched directly. The forest is not thin; this seat is bounded
per-run by design.


**§33 dispositions (2026-08-18, owed-work batch3 — items above, in order):**
- Wilmott f=38+f=44 title harvest: [§33: killed] — ground WALLED x3 (403 both hosts, both egress paths); re-probe condition = robots change or different egress
- OLMAR cluster remainder: [§33: killed -> docs/graveyard.md era_olps_olmar_portfolio_selection + olmar_olps_era_zero_cost_canon]
### SESSION CLOSE 2026-08-01 session 3 (CN frontier miner) — STANDING TEST, DEPTH, BATTERY, NEXT GROUND

**STANDING TEST — "Which artifact on disk is different because of what was mined?"**
`search_operator_library.md` (**OP-036/037/038** + **14 verified lexicon rows**), `data_axis_watchlist.md`
(unlock axis card + its same-run correction + the northbound strike), `data/unlock_event_screen.json`
(27 cells, now git-tracked via a narrow `!` exception), `cn_oss_extraction_20260731.md` (5 corrections
at source), `recommendation_ledger.json` (**R0288–R0293**), `rm-20260801T125319-a95125`, and this note.
**Cycle CONVERTED** — and note what the conversions actually were: **two refutations, one demonstrated
defect, one null, and one instrument repair.** Not one new alpha. That is the honest shape of it.

**DEPTH LINE (per lead, honest):**
- **Unverified-slang block: EXHAUSTED** — 7/7 resolved, 6 with the real form named. Depth was the
  *near-form hunt*: deleting the bad rows would have been half the job; the value was 猴市, 韭菜币,
  山寨季 and 狗庄 sitting one step away from the garbled terms.
- **大饼 origin: EXHAUSTED to two independent primary sources** with verbatim text and a date. Surface
  would have given "big pancake = BTC"; depth gave the **2017-09-04 causal origin**, which is the
  entire content of OP-036.
- **`unlock_events.json`: EXHAUSTED as an artifact** — read to its schema, screened 27 cells, and both
  its defects found. Depth past the screen is what turned "null" into "unmeasurable, and here is
  precisely why".
- **8btc thread-44638: EXHAUSTED** (15 posts, reply-chain). The headline is a price gap; the *replies*
  carry the AML/latency barrier and the episodic character — the surface would have given a number and
  no mechanism.
- **8btc era board as a whole: NOT exhausted** — 713 catalogued, ~11 mined, and this run proved the
  catalogue is **incomplete** (44638 is outside it). No exhaustion claimed.
- **Gitee/CN-GitHub chain: OPENED, NOT exhausted** — akshare/QuantsPlaybook/FMZ/QUANTAXIS/samaritan
  read; JoinQuant, BigQuant, RiceQuant, 掘金量化 **untouched behind community logins**.
- **CN OSS tranche: EXHAUSTED for its three named targets** (AlphaGPT, Vibe-Trading, NOFX) — two
  refuted, one honest null.

**PROACTIVE BATTERY (moves run; a move that produced nothing is named, never skipped):**
- **#3 CONFIG-VS-OUTCOME — the run's biggest payout.** Refused to bank R0289 as reasoned-from-source
  and executed it: the guard reports CLEAN on a feature reading the **final bar of the entire series**.
  Also refused to bank OP-036 unexercised, which is what produced the era find.
- **#2 ADJACENCY — ran, bounded null.** Swept for the leakage-guard's shape (checker covering a subset
  of its input space while reporting PASS on all of it): `validation.py:91` is the only literal
  instance across `libs/`+`scripts/`. One module, three entry points — not a family. Reported as such.
- **#9 SCOPE THE NEGATIVE RESULT — three times, and one of them unblocked a 3-session carry.** Gitee
  405/empty-body/`[]` scoped to "the HTML front is walled", NOT "Gitee is unreachable" → OP-038 and the
  whole of item 3. Zhihu 403 scoped to the ROUTE (search readable, articles not) → **no paid unlock
  justified**. Kill-list zeros scoped to the TERM, not the pipeline, via a positive control.
- **#5 COST INVERSION — paid out twice.** NOFX's two "mechanisms" reduce to one **purchased** endpoint
  (`claw402`) whose free primary is our own liquidation tape; and the CN margin-balance axis has a
  **first-party exchange route** (SSE `queryMargin`, 16.3y) behind the ToS-grey Eastmoney aggregator —
  prefer the exchange, which is both cleaner provenance and free.
- **#10 RATCHET CHECK — floors that must not fall:** operators 37→**40**; CN lexicon 12→**26** verified
  rows; era threads mined 11→**12** *and* the era ground proven larger than its 713-thread catalogue;
  CN OSS tranche targets verified-at-primary-source 3/3.
- **#4 REGRESSION SWEEP — what this run made worse, stated plainly.** I added **6 rows** (R0288–R0293)
  to a queue the fence already reports as **REPAIR-MODE: 195 backlog, 54 past due, 291 raised vs 81
  dispositioned in 7d (ρ≈3.6)**. That is a real cost and I am not hiding it. L1.28b(f) exempts miners
  and screens-on-discovery from repair-mode throttling *by name*, so the correct response is to say it
  out loud rather than suppress detection — but three of my six rows are **defects in our own code**
  (R0289/R0292/R0293), which is the cheapest tier to convert and needs no new feed. Second cost: the
  unlock axis card now carries a same-run self-correction, so a reader who stops at the screen table
  gets the wrong window — mitigated by putting the correction *inside* the card, not in a session note.
- **#1/#6/#7/#8 produced nothing beyond the above this run — reported as such, not skipped.**

**VIDEO-LOCKED:** nothing logged. **No CN video was attempted this run**, so there is no route failure
to report — and a platform is only logged after a real attempt fails. Honest gap, not a blocker.

**NEXT RUN TAKES FIRST (the chain — do not re-surface-scan the above):**
1. **The delisting panel (R0292) is the highest-value thing this seat has ever surfaced** — 123 events,
   exact timestamps, one keyless call, a venue we trade, no §13 question. Build the panel and run the
   **three separate hypotheses** (impulse / drift-to-settlement / rebound) through the §42 event-study
   path, net of a real slippage model for the illiquid cohort.
2. **Re-run the unlock screen on the CORRECTED window** `[T−30d, T]` — the external evidence says the
   effect lives pre-event and all 27 of my cells tested post-event.
3. **8btc era board, section by section, with BOTH era keys** (比特币 pre-94, 大饼 post-94, per OP-036)
   — and **re-catalogue first**, since 44638 proved the 713-thread catalogue incomplete.
4. **JoinQuant / BigQuant / RiceQuant / 掘金量化 实战 threads** — the only major CN ground this run
   opened and did not enter.

**SEAT-EXHAUSTION CHECK (L1.35): FALSE, as always.** Named un-exhausted ground at close: ~700 8btc
era threads plus an under-count of unknown size; four CN quant platforms untouched; CFFEX 16.3y
named-broker OI never pulled; HTX/Gate funding history catalogued but not ingested; 承兑商 merchant-
density thread never opened; Xiaohongshu and Gate 广场 (both on the seed list) never visited this run.
**The ground grew faster than I mined it this session, which is the normal and correct state.**

**STANDING DIASPORA QUESTION — materially advanced, and the answer is uncomfortable.** Previous runs
asked where CN crypto discussion went after the bans. This run found it: **into paid and
identity-gated enclosures** — 知识星球 (paid), QQ groups (ID-gated), WeChat groups (friend-add) — with
the open web layer left as tutorials, refuted-class strategy dumps and marketing. **§13 puts that
layer permanently out of reach, and that is a structural ceiling on this region, not a gap to close.**
The operative consequence: **the open CN layer worth mining is repos, era archives and platform 文库
— not live community.** Next question carried: did the *era* boards (8btc/ChainNode) preserve the
pre-enclosure discussion that is now walled? If so, era-archaeology is not merely one CN deliverable
— it is the **only** route to CN practitioner discussion at depth, which would sharply raise its
priority relative to living-web digging.

---

## SESSION NOTES — RU frontier miner

_Region grounds: habr.com quant/algo long-reads, smart-lab.ru, RU-language GitHub (lang:ru), RU
YouTube algo channels, RU public Telegram. Operators: OP-002 (Yandex/RU templates), OP-003
(habr comments / smart-lab forums), OP-004 (cyberleninka.ru open archive)._


**§33 dispositions (2026-08-18, owed-work batch3 — items above, in order):**
- Delisting panel R0292 (123 events + three hypotheses): [§33: wired -> libs/research/listing_events.py + scripts/run_listing_watch.py + data/delisted_instruments.json + data/delisted_rosters/*]
- Unlock screen re-run on corrected [T-30d,T] window: [§33: deferred(2026-08-25)] — no re-run evidence found anywhere; still owed
- 8btc era board section-by-section: [§33: screened] — s7/s8 08-12/08-13 records (2013-12 ban window mined; OP-069/070/071)
- JoinQuant/BigQuant/RiceQuant 实战 threads: [§33: deferred(2026-09-01)] — measured credential-walled
### 2026-08-01 session 1 (RU frontier miner) — IN PROGRESS (write-first note; updated as items resolve)

**SEAT STATUS: FIRST RUN.** There is no prior RU session note anywhere in this document — EN has
sessions A–E, CN has 1–3, PROSPECTOR has one. **The RU ground has never been dug.** So nothing here
is a resume; everything is ground-opening, and I claim EXHAUSTED on nothing I have not mined
section-by-section.

**WHY THESE ITEMS (the reasoning, so the next run can overrule it):** the desk's own
`data/strategy_coverage.json` says **STATISTICAL-ARBITRAGE is the only MENTIONED-NEVER-TESTED
family** (n_tested=0, 1 ledger mention, nothing ever reached the graveyard). RU retail algo culture
— smart-lab.ru, MOEX spread traders, habr quant long-reads — is the most stat-arb/pairs-saturated
practitioner community in any region the desk covers. **Unhunted family × this seat's actual
specialty** is a better use of a first run than deepening CROSS-VENUE-PREMIUM, which is HUNTED with
9 candidates and **9 deaths**.

**ITEMS TAKEN THIS RUN (bounded breadth, unbounded depth per item):**

1. **BACKLOG VERIFICATION (RESUME mandate — verification is the desk's bottleneck, not cataloguing).**
   From `source_backlog_next.py`: **Regulatory-event timeline (5-class taxonomy, Auer–Claessens)**.
   Taken because it is the most RU-adjacent of the 4 pending items — Russia is the highest-barrier
   regulatory regime in the desk's entire premium dataset. Verify: primary source reachable, §13
   licence, and whether it actually yields a *usable dated event list* rather than a prose taxonomy.
   - **RESOLVED — VERIFIED, and the answer is NO for the QR version.** BIS QR Sept-2018
     (`bis.org/publ/qtrpdf/r_qt1809f.htm`) is **prose + regressions with NO annex event table**. It
     names **151 regulatory news events, start-2015 → end-June-2018, sourced from Reuters**, and
     shows exactly **two** illustrative events with timestamps (2017-03-10 21:04 SEC rejects
     bitcoin ETF; 2018-06-22 07:17 Japan FSA orders 6 exchanges to improve AML). The dataset lives
     in the separate extended paper (Auer & Claessens, *Cryptocurrency Market Reactions to
     Regulatory News*), which is **SSRN 403 from this VPS** — route failure, NOT capability
     failure (L1.25a): CESifo WP 8228 / CEPR DP 14602 are the same paper and were not exhausted.
   - **THE USABLE PART, which is why this is not a null.** The *taxonomy and its effect sizes* are
     extractable now and are the reusable asset: **3 primary classes + 2 auxiliary** — legal
     status; AML/CFT; interoperability (restrictions on links to regulated entities); plus general
     warnings and CBDC statements. Measured: **interoperability restrictions ≈ −6.4pp**, **AML/CFT
     median ≈ −4pp over a 10-day window**, legal-status largest, and — the load-bearing one —
     **general warnings show NO statistically significant effect.**
   - **THE OPERATIVE READ for the desk:** the categories are *not* interchangeable, and the null on
     general warnings is the useful half. Any event-study panel that pools "regulatory news" into
     one bucket dilutes a −6.4pp effect with a class measured at zero. If the desk builds a
     regulatory-event axis, **it must carry the 3-class label or it is pre-diluted.** That is a
     design constraint obtainable *without* the event list.
   - **VERDICT: keep PENDING, re-scope.** Not "no event list exists" — "the QR does not carry it and
     the SSRN route is walled from here". Next attempt: CESifo WP 8228 PDF and CEPR DP 14602.

2. **RU LIVING-WEB GROUND, opening dig: habr.com + smart-lab.ru**, hunting STATISTICAL-ARBITRAGE
   first (unhunted family), then data axes and engine ideas. To comment/reply depth ≥2 (OP-003), not
   headline depth. Every venue mentioned inside a thread is harvested as a new venue (venue-discovery
   obligation).
   - RESOLVED → see below.

3. **ERA-ARCHAEOLOGY + BARRIER-HEIGHT OUT-OF-SAMPLE TEST.** The desk's `era_crossvenue_fiat_premium_arb`
   graveyard entry was **mechanism-reclassified**: a persistent cross-venue premium is *rent on a
   capital-control / withdrawal / counterparty barrier*, and **premium magnitude tracks BARRIER
   HEIGHT** (KR 1.42% std → JP 0.37% → TR 0.23%, all dead except kimchi, which was itself later
   refuted). That law was fit on KR/JP/BR/TR/CN. **Russia post-2022 is the highest-barrier point in
   existence** — SWIFT cutoff, card rails severed, sanctioned venues — and it is *out of sample*.
   This is a test of a mechanism the desk already believes, which outranks a 10th candidate in a dead
   family. Plus the standing diaspora question: **where did they go** after 2022?
   - **RESOLVED — the law SURVIVES its most extreme out-of-sample test, and the axis is CLOSED on
     two independent grounds (§13 hard stop + the rent is charged as spread, so the desk would be
     the payer).** Full card in `prospector_watchlist.md`. The cross-era synthesis it produced —
     *the barrier migrates, and a premium with no barrier is arbitraged away by definition* — is in
     `graveyard.md` and is the session's most transferable output.

**NEXT GROUND (named before I start, so the chain survives being killed mid-run):** MMGP.ru +
bits.media era boards section-by-section; RU-language GitHub `lang:ru` fork chains; RU YouTube algo
channels via `fetch_video_transcript.py`; cyberleninka.ru citation chains (OP-004).


**§33 dispositions (2026-08-18, owed-work batch3 — items above, in order):**
- Backlog verification (Auer–Claessens timeline): [§33: screened] — resolved in-block; walled remainder carried in session close
- RU living-web ground (habr + smart-lab): [§33: screened] — in-block results
- Era-archaeology + barrier-height OOS: [§33: screened] — the-barrier-MIGRATES result; graveyard barrier-rent rows
### SESSION CLOSE 2026-08-01 session 1 (RU frontier miner) — STANDING TEST, DEPTH, BATTERY, NEXT GROUND

**STANDING TEST — "Which artifact on disk is different because of what was mined?"**
`search_operator_library.md` (**OP-039** habr comments API — verified runnable, **OP-040** the
re-denomination-convention probe, + an **11-row RU lexicon**, 8 of them verified in situ),
`graveyard.md` (**`retail_crossvenue_scan_arb`** killed with the operator's own instrumentation,
**`statarb_kalman_hedge_ratio_refinement`** killed by its own reply chain, and the **cross-era
barrier-migration synthesis**), `prospector_watchlist.md` (STATISTICAL-ARBITRAGE family prior + the
RU premium axis CLOSED), `improvement_inbox.md` (1 demonstrated defect, 1 design inversion, 1 engine
pattern), `recommendation_ledger.json` (**R0294–R0297**), and this note. **Cycle CONVERTED.**
And the honest shape of it: **two refutations, one demonstrated code defect, one design inversion,
one family prior, and zero tradeable cards.** No alpha. That is the correct output for a first run
on ground whose two dominant families were already adjudicated here.

**DEPTH LINE (per lead, honest):**
- **habr 911056: EXHAUSTED** — article + **all 66 comments to depth 7** via OP-039. This is the
  session and it is the clearest depth-payoff I can show: the **surface** gave "15,256 signals → 4
  viable". The **depth** gave (a) the ticker-collision mechanism *(«ticker один а по факту разные
  сети... сразу арбитраж и 600%»,* depth 1, **score 0**), which I then demonstrated against our own
  join; (b) the venue-ban/toxic-flow constraint from the thread's *bull* case (depth 0) — the
  counter-claimant concedes the P&L is not withdrawable, which is worth more than the debunking;
  (c) the two-stage scan architecture (depth 4); (d) hard infra numbers — 50 msg/s/pair protobuf,
  247 pairs, 25–40 Mbit/s, 100% CPU (depth 1). **Ranking by keyword density rather than votes is
  what surfaced (a) — it had zero votes and the top-voted comment carried nothing.**
- **habr 599551: EXHAUSTED at article level** (comments not exposed in fetch; not re-attempted via
  OP-039 — a named gap, not a claim of exhaustion). Value: independent second source for the
  closed-rail mechanism, verbatim.
- **smart-lab statarb tranche: OPENED, NOT exhausted.** 707565 (67 comments, mined via fetch) and
  936066 (reply chain, mined) closed; **339456, 52568, 504951, 133052, and the full
  `/tag/статистический арбитраж` index remain unmined.** No exhaustion claimed.
- **BIS/Auer–Claessens: NOT exhausted** — QR read to its taxonomy and effect sizes; the extended
  paper is walled on the SSRN route only. Two live alternate routes named and untried.
- **RU premium / Garantex: EXHAUSTED as an axis** — closed permanently on §13, which is dispositive
  and needs no further digging. The only RU ground where "done" is genuinely claimable.
- **BREADTH-THEATER CHECK:** not this run. 1 comment tree fully walked, 2 reply chains mined, 1
  live cross-venue probe run against desk code, 1 import graph walked. But **zero repo forks and
  zero citation chains** — `github.com/Alex-ok2005/crypto-arbitrage-scanner` (named in habr 911056)
  was **not** followed, and cyberleninka (OP-004) was not touched. Naming both as owed.

**PROACTIVE BATTERY (moves run; a move that produced nothing is named, never skipped):**
- **#3 CONFIG-VS-OUTCOME — the run's biggest payout, twice.** Refused to bank the ticker-collision
  comment as a plausible-sounding warning and **executed a live two-venue probe**: it turned into a
  demonstrated, quantified coverage gap (260/653; 5 named liquid perps). Then refused to bank *that*
  as a live defect and **walked the import graph** — which showed the only caller hardcodes 14 large
  caps, so the defect is **LATENT, not live**. Both refusals changed the verdict.
- **#9 SCOPE THE NEGATIVE RESULT — twice.** SSRN 403 scoped to **the route**, not the paper (two
  alternate routes named) — this is the exact error that once turned one blocked endpoint into "video
  is blocked". And the `okx_inst` miss scoped correctly: of 16 unresolved re-denominated tickers,
  only **5** are defects; the other 11 are genuine OKX absences and calling them defects would have
  been a manufactured finding.
- **#4 REGRESSION SWEEP — what this run made worse, plainly.** I added **4 rows (R0294–R0297)** to a
  queue the fence already calls REPAIR-MODE. Real cost, not hidden. Mitigating: three are defects in
  **our own code**, the cheapest tier to convert, needing no new feed; and L1.28b(f) exempts miners
  from repair-mode throttling by name. Second cost: I seeded an RU lexicon of which **3 rows are
  UNVERIFIED** (carried from the seat brief, not seen in the wild) — marked as such inline per
  OP-037 rather than presented as knowledge.
- **#5 COST INVERSION — paid out.** The RU premium axis looked like a paid-data question (who sells
  RU P2P quotes?) and is in fact a **§13 hard stop**, so no purchase can ever be justified. Closing
  it at the legitimacy gate costs nothing and permanently retires a spend proposal.
- **#2 ADJACENCY — ran, bounded.** The re-denomination hazard is not one-venue: Bybit/Binance mostly
  agree on the `1000` prefix, **OKX does not**, and Bitget/Gate/HTX are **unverified** — named as the
  next probe in OP-040 rather than assumed either way.
- **#10 RATCHET CHECK — floors that must not fall:** operators 38 → **41**; RU lexicon 0 → **11 rows
  (8 verified)**; RU session notes 0 → **1**; graveyard cross-era instances of the premium law 4 → **5**.
- **#1/#6/#7/#8 produced nothing beyond the above this run — reported as such, not skipped.**

**VIDEO-LOCKED:** nothing logged. **No RU video was attempted this run** — RU YouTube algo channels
were in my ground list and I did not reach them. That is an honest gap in coverage, **not** a route
failure, and it must not be recorded as a blocker: a platform is only logged after a real attempt
fails.

**VENUE DISCOVERY (obligation: every run finds venues not on the seed list):**
| venue | what lives there | how found | verdict |
|---|---|---|---|
| `habr.com/kek/v2/` comments API | full nested comment trees, keyless | endpoint probe | **RICH** — now OP-039 |
| smart-lab.ru `/tag/статистический арбитраж` | the RU statarb index, many unmined posts | tag-index from a post | **RICH**, unmined |
| pikabu.ru | statarb/pairs explainers, large comment culture | search surface | **THIN** (derivative), unmined |
| vc.ru `/services` | RU P2P/venue comparison writeups | premium search | **THIN** for alpha, useful venue intel |
| `github.com/Alex-ok2005/crypto-arbitrage-scanner` | the debunked scanner's actual source | named in habr 911056 | **UNVISITED — owed** |
| Finam broker's habr company blog | broker-published statarb tutorials | search surface | **UNMINED** |

**NEXT RUN TAKES FIRST (the chain — do not re-surface-scan the above):**
1. **The smart-lab statarb tranche to exhaustion** (339456, 52568, 504951, 133052 + the tag index),
   mining comments — this is the desk's only never-tested family and the reply chains are where the
   RU corpus keeps its cost/capacity numbers. Highest value on this ground.
2. **`crypto-arbitrage-scanner` repo chain** (OP-001: issues, forks, contributor's other repos) —
   the one lead this run named and did not follow.
3. **RU YouTube algo channels** via `fetch_video_transcript.py` — untouched this run; video is
   first-class and must not silently become a skipped class.
4. **CESifo WP 8228 / CEPR DP 14602** for the Auer–Claessens event annex (the walled-route retry).
5. **Era-archaeology, still entirely unopened on this ground:** MMGP.ru + bits.media archives,
   pre-sanctions LocalBitcoins/EXMO mechanics. **Zero era work happened this run** — the dark-forest
   mandate's era limb is owed and I am naming it rather than letting it quietly lapse.

## SESSION NOTES — KR frontier miner

_Region grounds: Naver blogs + public cafes, DCInside trading galleries, velog/tistory dev posts,
KR GitHub, Upbit/Bithumb developer ecosystems. Operators: OP-002 (native-language templates),
OP-032 (native language FIRST). KR lexicon seeded 2026-07-30 by the PROSPECTOR seat._


**§33 dispositions (2026-08-18, owed-work batch3 — items above, in order):**
- smart-lab statarb tranche (339456/52568/504951/133052): [§33: deferred(2026-08-25)] — re-carried by later RU sessions
- crypto-arbitrage-scanner repo chain: [§33: deferred(2026-08-25)] — table row 'UNVISITED — owed'
- RU YouTube algo channels: [§33: screened] — RU s3 08-13: fetcher ALIVE, YouTube wall is a hollow full-size 200
- CESifo WP 8228 / CEPR DP 14602: [§33: deferred(2026-08-25)] — attempted, not exhausted
- Era-archaeology: [§33: screened] — RU branch-s1 08-04 (btcsec era corpus, data/btcsec_trading_topics.json)
### 2026-08-01 session 1 (KR frontier miner) — IN PROGRESS (write-first note; updated as items resolve)

**SEAT STATUS: FIRST RUN.** No `SESSION NOTES — KR frontier miner` section existed in this document
before this line. KR ground HAS been touched, but by other seats: the **PROSPECTOR seat on
2026-07-30** ran the per-asset KR premium axis to a family null (175 assets, median IC +0.0050,
honest-null branch fired) and catalogued the per-coin premium tracker ecosystem. That session
**named its own next KR ground and did not do it**: _"Coinpan/DCInside/Naver-cafe community
deep-mining — the discussion layer behind the trackers"_. **I am resuming that chain, not
restarting**, per the RESUME mandate.

**WHY THESE ITEMS — the reasoning, so the next run can overrule it:**
`data/strategy_coverage.json` says **CROSS-VENUE-PREMIUM is HUNTED with 9 candidates and 9 deaths**,
three of them Korean (`bithumb_kr_premium_lookahead`, `coinone_kr_premium`, and kimchi itself,
REFUTED at full 8.2y depth 2026-07-30). **The obvious KR dig is the one dig this seat must not do.**
The unhunted/thin ground is elsewhere: **ATTENTION-SENTIMENT is THIN (n_tested=2)** and it is the
family a Korean-retail seat is structurally best placed to open — KR retail is a distinct,
concentrated, KRW-rail flow cohort with its own information ecosystem.

**ITEMS TAKEN THIS RUN (bounded breadth, unbounded depth per item):**

1. **BACKLOG VERIFICATION, RE-SCOPED (RESUME mandate).** `source_backlog_next.py` lists **NAVER
   DataLab (Korean search-attention)** as pending verification. It has been "verified" **three
   times** (07-25, 07-30, 07-31) with the identical answer: HTTP 401, keyed API, blocker is a free
   NAVER Developers registration = a human step. **A fourth re-confirmation is worth zero.** The
   part that is NOT settled, and that a KR seat is the right organ to settle:
   **is the whole KR search-attention CLASS blocked, or only that one route?** (L1.25a: scope the
   negative result to the ROUTE, never the CAPABILITY.) Sub-item: the desk's axis watchlist carries
   **four KR/CN/JP community sources parked at `needs-legitimacy-review`** (Coinpan, DCInside,
   Weibo/Zhihu, 5ch) — a placeholder verdict nobody has ever actually adjudicated. **A §13 gate that
   is never run on a candidate rejects it by default**, which is the welded-gate pattern (L1.43)
   pointed at our own legitimacy gate. Decide it, either way, with the primary documents.
   - RESOLVED → see below.

2. **THE NAMED, UNDONE KR GROUND: community deep-mine.** DCInside 비트코인 갤러리 / Coinpan /
   Naver cafés — to **reply depth ≥2**, hunting mechanisms in THIN or NEVER-HUNTED families, not
   the adjudicated premium. Reading a public thread as a researcher is a different act from
   adopting it as an automated feed; §13 governs the second. Every venue named inside a thread is
   harvested (venue-discovery obligation).
   - RESOLVED → see below.

3. **UPBIT / BITHUMB DEVELOPER ECOSYSTEM + KR GITHUB — data axes, not strategies.** Standing
   obligation: every venue is asked what it PUBLISHES. A dig returning zero strategies and one new
   data axis is a good dig. Hunt endpoint lists inside collector code, not marketing pages.
   - RESOLVED → see below.

STATUS: run in progress — per-item results appended below as they close.

#### ITEM 1 — CLOSED. The KR §13 map, read off the PRIMARY documents for the first time.

**The desk had never fetched a single `robots.txt` on this ground.** Four KR/CN/JP community
sources sat at `needs-legitimacy-review` in `data_axis_watchlist.md` — a placeholder that has
survived three rounds — and my own seat brief names Naver cafés and DCInside as REGION GROUNDS.
One `curl` each settled all of it. **Measured 2026-08-01, verbatim:**

| venue | `User-agent: *` policy | AI/Claude family named explicitly? | §13 verdict |
|---|---|---|---|
| **cafe.naver.com** | **`Disallow: /`** — entire site, to everyone | `ClaudeBot`, `GPTBot`, `Google-Extended` + prose header *"BOT ACCESS FOR THE PURPOSES OF AI TRAINING AND RETRIEVAL-AUGMENTED GENERATION (RAG) IS STRICTLY PROHIBITED"* | **HARD STOP** |
| **blog.naver.com**, **m.blog.naver.com** | permissive except `/PostList.nhn` | **`ClaudeBot` + `Claude-SearchBot` → `Disallow: /`**, same RAG prose | **HARD STOP for this agent family** |
| **gall.dcinside.com**, `m.`, `www.` | `Allow: /` (minus ~15 named galleries + `/kcaptcha/`, `/api/`, `/search/`) | **`ClaudeBot`, `anthropic-ai`, `Claude-Web` → `Disallow: /`** under the header `# ----- AI 학습 크롤러 차단 -----` | **HARD STOP for this agent family.** See the split below — do **not** self-grant the `*` route |
| **coinpan.com** | **`Disallow: /inquiry/` and nothing else** | none | **OPEN — CLEAN** |
| **datalab.naver.com** | `Allow: /$`, `Allow: /index.naver`, **`Disallow: /`** | — | **the web-XHR scrape route is DISALLOWED** |
| **velog.io** | `User-agent: *` with **zero rules** | none | **OPEN — CLEAN** |
| **www.bithumb.com** | `User-agent: *`, no `Disallow` at all | none | **OPEN — CLEAN** |
| **kimpga.com** | `Allow: /` (minus privacy/terms) | none | **OPEN — CLEAN** |
| tistory.com apex | serves a Next.js app shell at `/robots.txt`, no policy | — | per-subdomain check owed |
| coinone.co.kr | 302 → Cloudflare on `/robots.txt` | — | **UNRESOLVED**, named not assumed |

**FINDING 1 — THREE OF MY FIVE ASSIGNED GROUNDS REFUSE THIS AGENT BY NAME.** Naver cafés, Naver
blogs and DCInside galleries each carry a machine-readable directive naming `ClaudeBot` /
`anthropic-ai` / `Claude-Web` with `Disallow: /`. §13 is absolute — *"a licence forbidding the use
is a HARD STOP, never a hurdle"* — and the doctrine adds *"never route around a venue's own access
control."* **Selecting a different user-agent to evade a block aimed at this agent by name is
exactly that routing-around, so the `*` section is not a loophole I am entitled to take.** I did
not fetch page content from any of the three. The seat brief is a seed list, not an authorisation;
where a seed collides with §13, §13 wins and the ground is closed.

**FINDING 2 — THE DESK'S TWO KR COMMUNITY GRADINGS WERE BACKWARDS.** `data_axis_watchlist.md`
excluded *"Korean forums (Coinpan, DCInside crypto boards) — needs-legitimacy-review … ToS-grey"*
as one undifferentiated class. The primary documents split them cleanly and in the opposite
direction to the guess: **DCInside blocks us by name; Coinpan allows everything except
`/inquiry/`.** The source the desk declined to build is the clean one. This is the welded-gate
pattern (L1.43) aimed at our own §13 gate: **a legitimacy verdict that is never actually
adjudicated rejects by default**, and a default rejection is indistinguishable from a reasoned one
in every downstream artifact.

**FINDING 3 — GAP #69 IS WORTH FAR MORE THAN ITS CARD SAYS, and this is the actionable one.**
`openapi.naver.com` was only ever probed at `/v1/datalab/search`. I probed the sibling content
endpoints. **All four return the identical keyed-API 401** (`errorCode 024`, *"Not Exist Client ID"*):
```
GET /v1/search/blog.json        -> HTTP 401  errorCode 024
GET /v1/search/cafearticle.json -> HTTP 401  errorCode 024
GET /v1/search/news.json        -> HTTP 401  errorCode 024
GET /v1/datalab/search          -> HTTP 401  errorCode 024
```
So the **one free NAVER Developers registration** does not merely unlock a search-attention axis
(the card's framing, filed tier-3). **It is simultaneously the LICENSED route into Naver blog and
Naver café content that `robots.txt` otherwise closes to us permanently.** One human step converts
**two hard-stopped grounds plus one blocked axis** into a single §13-clean feed. That is a large
change in the value of GAP #69 and it was invisible because nobody probed the neighbouring paths.

**FINDING 4 — a free confirmation of a judgement call.** The 07-26 session refused the
`datalab.naver.com` web-XHR scrape on instinct (*"ToS-grey… producing an artifact by doing the
thing the card refused to do is a fake conversion"*). `datalab.naver.com/robots.txt` is
`Disallow: /` for everything but the bare index. **That instinct is now evidenced, not merely
principled** — and the refusal should be cited as correct rather than re-litigated.

**DCINSIDE — THE ONE VERDICT I AM NOT ENTITLED TO MAKE ALONE.** Two distinct acts must not be
collapsed: *(a)* me, an Anthropic-family agent, fetching pages — **named, blocked, closed, and I
complied**; *(b)* a future desk collector under its own UA doing statistical post-counting, which
the `User-agent: *  Allow: /` section permits on its face while the file's own header states the
operator's intent is to block AI crawlers. That gap is a **principal legitimacy decision**, not
something a miner grants itself, and it is rowed as such rather than resolved here in either
direction. Recording the ambiguity beats inventing a verdict.

**VERDICT ON THE BACKLOG ITEM: NAVER DataLab stays PENDING — unchanged, and correctly so — but the
re-verification loop is now CLOSED.** Three prior sessions each re-confirmed the same 401. The
route is settled; a fifth probe is worth nothing. What this run adds instead is the *scope*: the
blocker is not "one attention axis is unavailable", it is **"the licensed gateway to the entire
KR consumer-web layer is unpurchased, and it is free."**

#### ITEM 2 — CLOSED, and the honest verdict is that this ground is SHUT on three independent mechanisms.

The named next-run ground was *"Coinpan/DCInside/Naver-cafe community deep-mining."* I could not
mine any of the three, and the reasons are different in each case — which matters, because
collapsing them into "KR community is blocked" would be the exact error that once turned one
blocked YouTube endpoint into *"video is blocked."*

- **DCInside** — blocked by **§13**: `ClaudeBot` / `anthropic-ai` / `Claude-Web` named with
  `Disallow: /`. I did not fetch. **Not a route failure; a legitimacy hard stop.**
- **Naver cafés / blogs** — blocked by **§13**, same shape, plus prose forbidding RAG use outright.
  **Licensed alternative exists and is free** (`/v1/search/cafearticle.json`, `/v1/search/blog.json`)
  — see Finding 3. **Not a capability failure; an unpurchased key.**
- **Coinpan** — **§13-CLEAN but technically WALLED.** `robots.txt` permits everything bar
  `/inquiry/`, and every content route sits behind a Cloudflare interstitial:
  ```
  /rss                        -> HTTP 403  "Just a moment..."
  /index.php?mid=free&act=rss -> HTTP 403  "Just a moment..."
  /free                       -> HTTP 403  "Just a moment..."
  /sitemap.xml                -> HTTP 200  (the one route that serves)
  ```
  I applied **OP-038** (*a JS wall on the HTML is not a wall on the API*) — it does **not** rescue
  this one: the wall is at the **CDN edge**, not the renderer, so the feed routes are walled too.
  That is a real refinement to OP-038 and is written back to the library. **Solving a Cloudflare
  challenge is routing around access control and is forbidden**, so this stays WALLED, not
  "pending a better scraper".

**THE RE-AIM THIS FORCES, and it is the session's most useful structural output.** All three KR
retail-community venues are unreachable, by three unrelated mechanisms, none of which a better
query or more persistence would fix. **A KR seat whose value proposition is "read what Korean
retail says" has no ground.** But the thing that makes Korean retail interesting is not their
*forum posts* — it is that they are a large, concentrated, KRW-rail-captive flow cohort. **Their
venues publish machine-readable state about that cohort, keylessly, and nobody collects it.**
Item 3 is where the value actually was, and this run found it only because item 2 closed.

#### ITEM 3 — CLOSED. The KR venue-API layer is wide open, deep, and uncollected.

**FINDING 5 — `api-manager.upbit.com/api/v1/announcements`: keyless, first-party, and it reaches
back to Upbit's open-beta day.** Verified by direct probe of the final page:
```
total_count 5,685   total_pages 1,137 (per_page=5; cap is 20, per_page>=30 -> 429, >=100 -> 400)
oldest rows: 2017-10-24T10:41:48+09:00  "오픈베타 안내 (Q&A)"
             2017-10-27T23:33:33+09:00  "스팀달러(SBD), 블록틱스(TIX) 상장 안내"
categories:  거래 / 입출금 / 안내 / 점검 / 이벤트 / NFT / 디지털 자산 / 서비스+
             (filter key is ENGLISH: `category=trade` -> 737 events; `category=거래` -> HTTP 400)
```
**8.8 years of dated, categorised, first-party KRW-venue events.** `category=trade` (737) is the
listing / delisting / trading-support subset — the tradeable core.

**FINDING 6 — A LOOK-AHEAD TRAP SITTING IN THE OBVIOUS FIELD, measured not asserted.** Each record
carries **both** `listed_at` and `first_listed_at`. They differ on **17 of 40 (42.5%)** of a
recent sample, with **median edit lag 2.08 days, p90 9.30 days, max 14.7 days**. `listed_at` is the
field the list sorts by and the one any reasonable person would key an event study on — **and for
42.5% of events it is a timestamp assigned AFTER the fact, on median two days late, sometimes two
weeks.** An announcement edited later acquires a later `listed_at`, which can push its apparent
date past the price move it caused. **Key on `first_listed_at`. Always.** This is the L1.46 class
— *"a timestamp whose clock is undeclared is an assumption wearing a measurement's clothes"* —
and here the venue hands us the fix for free, but only if you look at the second field.

**FINDING 7 — THE FIND OF THE SESSION: `api.upbit.com/v1/market/all?isDetails=true` publishes
venue-computed state about the Korean retail cohort, per asset, keylessly.** Every market carries
`market_event.warning` (the 유의종목 investment-warning designation) plus a five-field `caution`
object. Measured live, **2026-08-01T13:34Z**, 803 markets / 277 KRW:

| flag | ALL (n=803) | **KRW-only (n=277)** | what it is |
|---|---|---|---|
| `warning` (유의종목) | 15 (1.9%) | **6 (2.2%)** | the venue's own investment-warning designation |
| `TRADING_VOLUME_SOARING` | 16 (2%) | **14 (5.1%)** | venue-defined volume frenzy |
| `GLOBAL_PRICE_DIFFERENCES` | 175 (22%) | **1 (0.4%)** | venue's own per-asset premium alarm |
| `DEPOSIT_AMOUNT_SOARING` | 7 (1%) | **3 (1.1%)** | inbound retail capital per asset |
| `PRICE_FLUCTUATIONS` | 9 (1%) | **1 (0.4%)** | venue-defined volatility flag |
| `CONCENTRATION_OF_SMALL_ACCOUNTS` | 0 | **0** | **retail crowding, per asset — in schema, not firing today** |

**The flags are LIVE and DISCRIMINATING, not welded** — they fire at rates from 0% to 22%, which
is the first thing to check on any new flag surface (L1.43).

**AND THE TRAP INSIDE IT, which is why the KRW column is broken out separately.**
`GLOBAL_PRICE_DIFFERENCES` fires on **175 markets (22%)** — by far the biggest number on the page,
and the one that looks like a ready-made kimchi-premium signal. **On KRW markets it fires once
(0.4%).** The 175 are almost entirely USDT- and BTC-quoted books, where the "global price
difference" is *thin-book illiquidity*, not a fiat premium. **Reading the headline 22% as a
premium signal would have been a pure artifact** — the desk's own tail-screen rule (*the biggest
number in a noisy panel is the likeliest artifact*) fires exactly here, and the KRW split is what
catches it.

**FINDING 8 — BITHUMB IS A SECOND, INDEPENDENT KR VENUE PUBLISHING THE SAME STATE, plus the
barrier itself.** `api.bithumb.com/v1/market/all?isDetails=true` (487 markets) carries
`market_warning`: **470 NONE / 17 CAUTION**. Cross-venue overlap with Upbit's 6 KRW warnings:
**ZIL, STORJ, TT, BONK are flagged at BOTH** — so the designation tracks asset-level state rather
than venue idiosyncrasy, while **Bithumb flags 17 vs Upbit's 6**, i.e. a materially looser
threshold. **The 13-name disagreement set is itself a candidate signal** (one venue sees trouble
the other has not designated yet), and it costs nothing to record.

And `api.bithumb.com/public/assetsstatus/ALL` — **506 assets, per-asset deposit and withdrawal
status**, measured today: **withdrawal closed on 4 (0.8%), deposit closed on 51 (10.1%).**

**WHY FINDING 8 IS THE ONE WITH THE DEEPEST MECHANISM BEHIND IT.** The desk's own cross-era
synthesis (RU seat, 2026-08-01) concluded that a persistent cross-venue premium is **rent on a
barrier**, and that premium magnitude tracks **barrier height**. Every KR premium study this desk
has ever run — including the kimchi work that was ultimately refuted — inferred the barrier *from
the premium itself*, which is circular. **These two endpoints publish the barrier DIRECTLY,
per-asset, per-day, free:** a coin whose deposit rail is shut at Bithumb cannot be arbitraged into
that venue, and that is an *independent* regressor for the premium rather than a restatement of
it. **ZIL is the live worked example — warned at both venues AND deposit- and withdrawal-closed at
Bithumb simultaneously.** Whether this rescues anything is an open empirical question and I am
claiming nothing about it; what I am claiming is that the circularity that has dogged every KR
premium study here is **breakable with two keyless endpoints nobody has collected.**

**THE IRREPLACEABILITY POINT, and it decides the priority.** `market/all` and `assetsstatus`
return **CURRENT STATE ONLY — there is no history endpoint.** Every hour not recorded is gone at
any price (L1.46). The announcement archive back-fills the *event dates* to 2017, but the *flag
state* series can only ever start the day the desk begins recording. **This is the cheapest
irreplaceable-data decision available right now: a few hundred bytes a day, keyless, and the
series can never be bought later.** A competitor would have to reconstruct
`CONCENTRATION_OF_SMALL_ACCOUNTS` from Upbit's internal account-level book, which is
structurally unbuyable.

#### ITEM 3 (cont.) — EVENT-CLASS TAXONOMY + THE FEASIBILITY GATE, measured.

Classifying the `category=trade` archive (**360 of 737 rows pulled at time of writing**, spanning
**2023-02-15 → 2026-07-31**; the pull is resumable and the remainder is next-run work — I am **not**
claiming the full archive):

| event class | Korean title form | n (in 360) | what it is |
|---|---|---|---|
| new listing | `신규 거래지원 안내` | **151** | brand new to Upbit, all markets at once |
| **KRW market addition** | `KRW 마켓 디지털 자산 추가` | **41** | **already trading on Upbit's BTC/USDT books; KRW access added** |
| warning ON | `거래 유의 종목 지정 안내` | **47** | 유의종목 designation |
| warning OFF | `거래 유의 종목 지정 해제 안내` | **9** | designation lifted |
| delisting | `거래지원 종료 안내 (M/D HH:MM)` | **40** | trading-support termination |

**THE STRUCTURAL FIND: `KRW 마켓 추가` IS A DIFFERENT EVENT FROM `신규 거래지원`, AND IT IS THE
CLEAN ONE.** A new listing confounds two shocks — the market learning the asset exists on a major
venue, *and* Korean retail gaining won-denominated access. A **KRW market addition applies only the
second**: the asset is *already* trading on Upbit's own BTC and USDT books, so it is already
discovered, already priced on that very venue, already arbitraged — and then one rail opens.
**That is a natural experiment isolating rail access from discovery**, and it is the shape of
mechanism the desk's whole barrier synthesis predicts. 41 such events in 3.5 years, ~90+ expected
across the full archive.

**THE FEASIBILITY GATE — measured, and it PASSES with room.** A pre-announced event is only
tradeable if there is a window between the announcement and the effect. Every delisting title
carries its own effective timestamp in parentheses, so the window is measurable with **zero**
price data. **40/40 titles parsed:**
```
NOTICE WINDOW (announcement -> trading halt), days:
  min 14.0   p25 30.0   median 30.9   p75 31.9   max 36.0
  two regimes: a 14-day regime (2023-24) and a ~31-day regime (2025-26)
  shortest: PCI  2023-03-31 -> 2023-04-14 (14.0d)
  longest:  LOOM 2025-04-01 -> 2025-05-07 (36.0d)
```
**Upbit pre-announces delistings by a median of 31 days with a precise published halt time.** This
is exactly §42's named ground (*"delisting unwinds"*), it is a month-long forced-unwind window on a
retail-captive venue, and the desk collects none of it. Checking this first was the right order:
had the window been ~0, the mechanism would have been DOA and no price work would have been
justified.

**AND IT EXPLAINS FINDING 6'S MECHANISM, which was previously only measured.** The listing titles
carry suffixes `(거래지원 개시 시점 안내)`, `(...변경 안내)`, `(...추가 변경 안내)` — the venue
*amends the trading-start time* after first publishing. **That amendment is what rewrites
`listed_at`.** So the 42.5% divergence is not noise: `first_listed_at` = when the market first
learned, `listed_at` = when the schedule was last revised. Both are meaningful, they answer
different questions, and keying an event study on the second silently dates the event to the
revision instead of the news.

**PRE-REGISTRATION — written and committed to this document BEFORE any price data was fetched.**
- **Event:** Upbit `거래지원 종료` delisting announcement, keyed on **`first_listed_at`** (never
  `listed_at`, per Finding 6).
- **Direction: NEGATIVE**, declared in advance. *Mechanism:* KR retail is the marginal buyer for
  small-cap KRW-quoted names and is heavily non-self-custodial. A delisting notice removes their
  access on a published deadline; holders who cannot or will not move the asset to another venue
  **must sell before the halt and cannot stop** — that is the forced counterparty. The bid
  shrinks over a known month.
- **Window:** announcement → **+3 days**, ONE window, pre-declared. A second window is a second
  trial and would raise the bar (§42).
- **Benchmark:** BTC over each event's own window, subtracted (`abnormal_returns`) — otherwise the
  study measures beta, not edge.
- **Gate:** `libs/validation/event_study.py`, `n_cohort=1` (single pre-registered hypothesis),
  harness's own multiplicity-corrected bar + bootstrap. **`axis_screen` is the WRONG instrument
  here and would manufacture a false null** — ~2 non-zero days in 30 reads as noise on every
  continuous statistic, which is the exact failure that module was written to fix.
- **Timestamp alignment, declared:** announcements are **KST (+09:00)**; Upbit daily candles close
  at **24:00 UTC** (proven from primary hourly data, PROSPECTOR 2026-07-30, and reused here rather
  than re-assumed). An announcement at `2026-07-16T17:00+09:00` is `08:00 UTC` — **inside** that
  UTC day — so the return window must start at the **next** UTC daily close or it is look-ahead.
- **Falsifiers:** mean abnormal return ≥ 0; t below the harness bar; bootstrap interval spanning
  zero; or **n < 20**, at which point the harness itself returns "a story, not evidence".
- **KNOWN THREAT, declared before it is tested:** if Upbit purges candle history for delisted
  markets, only *surviving* markets are studyable and the sample is catastrophically
  survivorship-biased. **This is checked FIRST, and if it fails the study is impossible and that
  is the reported result** — not a smaller study quietly run on whatever remains.

#### ITEM 3 (cont.) — THE PRE-DECLARED THREAT FIRED, 6/6. And scoping it correctly is the finding.

**Upbit PURGES candle history when it delists a market.** Tested on six assets delisted across
three years, every one at the venue where the event happened:
```
KRW-OXT   (halted 2026-06-29) -> HTTP 404        KRW-QTCON (halted 2025-08-25) -> HTTP 404
KRW-NKN   (halted 2026-06-15) -> HTTP 404        KRW-PCI   (halted 2023-04-14) -> HTTP 404
KRW-LOOM  (halted 2025-05-07) -> HTTP 404        KRW-MARO  (halted 2023-09-26) -> HTTP 404
```
**This is not a biased sample — it is an ERASED treatment group.** Every delisted asset has had its
Upbit price history deleted, and no delisted asset survives to be studied, so the studyable sample
of Upbit-priced delisting events is exactly **zero**, not "40 minus some". Declaring this threat in
the pre-registration and testing it *before* fetching any prices is the only reason this run did
not produce a confident study of whatever happened to remain.

**SCOPE IT TO THE ROUTE, NOT THE CAPABILITY (L1.25a).** Three distinct things were at risk and only
one actually died:
- **DEAD:** the *Upbit-KRW-priced* delisting study, and with it any measurement of the KRW-specific
  premium collapse into a halt. That needs the purged leg and cannot be reconstructed.
- **ALIVE:** the *event dates* — the announcement archive is intact and is precisely the asset that
  survives the purge. This is what makes the archive worth more than it first appears.
- **ALIVE:** the study itself, **re-based on global prices**. OXT, NKN, LOOM, MARO and PCI all
  trade on venues whose history is intact. The runnable question becomes *"does an Upbit KRW
  delisting announcement move the asset's GLOBAL price?"* — which, if KR retail is genuinely a
  marginal buyer, is the sharper test anyway, and it is not survivorship-affected because the
  global venues keep their history. **That is next-run work and I am not claiming its result.**

**FINDING 9 — THE IRREPLACEABILITY IS LARGER THAN THE FLAGS, AND IT HAS A DATE ON IT.**
Finding 7 said the *flag* series is snapshot-only. The purge says something much bigger: **the
entire KRW price history of any Upbit asset is destroyed the day it delists**, at a measured rate
of **~11.4 markets/year**. Concretely, and this expires in two days:

| market | halt date | in the desk's 07-30 `kr_perasset` panel? | history the desk holds |
|---|---|---|---|
| **KRW-AQT** | **2026-08-03 (2 days)** | **no** | **none** |
| **KRW-AERGO** | **2026-08-03 (2 days)** | **no** | **none** |
| **KRW-SPURS** | **2026-08-18** | **no** | **none** |

**AND THE SECOND SURVIVORSHIP MECHANISM, which is ours, not the venue's.** The 07-30 panel holds
**176 of 277** KRW markets because it filtered to `>=120 aligned days`. That filter excludes the
newest and thinnest names — **which are exactly the names that get delisted**. So the desk's KR
dataset is survivorship-biased *by its own construction filter*, stacking in the same direction as
the venue's purge. Two independent selection effects pointing the same way, neither previously
named. (Honest note on a weaker probe: I also checked how many panel symbols vanished between
07-30 and today and got **0/176** — but at ~11 purges/year a 2-day window expects ~0.06, so that
zero is **underpowered by construction and is not reassurance**. The dated table above is the real
evidence, not the null.)

Rowed as **R0303** with the 08-03 expiry: capture full candle history for all 277 live KRW markets
before the halt, then daily. After 08-03 the AQT and AERGO series are unobtainable at any price.

#### ITEM 3 (cont.) — FINAL ARCHIVE + A SELF-CAUGHT SELECTOR DEFECT (OP-035, in my own work).

Pull reached **680 of 737** `category=trade` rows, spanning **2018-03-28 → 2026-07-31** (the
remainder is resumable next-run; `data/upbit_trade_announcements.jsonl` dedupes on `id`).
Per-year: `2018:78 2019:71 2020:90 2021:34 2022:41 2023:51 2024:67 2025:142 2026:106`.

**MY OWN CLASSIFIER WAS ERA-FITTED AND I CAUGHT IT — 332/680 (49%) unclassified.** The counts I
reported above are a **LOWER BOUND**, and the reason is exactly OP-035 (*a selector validated on
one era silently zero-hits another*), here in title convention rather than markup. **Upbit renamed
its own event classes at least five times in eight years:**

| era form | count | class |
|---|---|---|
| `BTC 마켓 코인 추가` | 75 | market addition (2018 register: "코인" = coin) |
| `BTC 마켓 디지털 자산 추가` | 52 | same event, 2020 register ("디지털 자산" = digital asset) |
| **`원화 마켓 신규 상장`** | **18** | **KRW listing — early register** |
| `BTC, ETH 마켓 코인 추가` | 16 | multi-market form my single-market key missed |
| `KRW, BTC 마켓 디지털 자산 추가` | 15 | multi-market, modern register |
| **`원화마켓 신규 상장`** | **12** | **same as above, WITHOUT the space** |
| `KRW 마켓 디지털 자산 추가` | 8 | the only form my selector caught |
| `원화 마켓 디지털 자산 추가` / `원화 마켓 코인 추가` | 7 / 3 | more KRW-rail events |

**`원화` (won) was the early word; `KRW` the later one — and both appear with and without a space.**
So the pure rail-access class is **not 43 events, it is ~83+**, and a modern-title selector finds
barely half. This is a lexicon finding with direct search value, not a formatting curiosity.

**AND THE WARNING REGIME HAS AT LEAST FIVE STATES, NOT TWO** — I had modelled it as on/off:
`유의 종목 지정` (designated) · `유의 종목 해제` (released) · **`유의 촉구 안내`** (caution *urged*
— a softer tier below designation) · **`유의 종목 일시 지정`** (temporary designation) ·
**`유의 종목 지정 기간 연장`** (designation period **extended** — the venue stating the problem is
unresolved). A designation-extension is a distinct and informative event, and modelling this ladder
as a binary would throw away most of its content.

Corrected headline figures (still lower bounds where noted): **50 delistings** (2018-10-05 →
2026-07-16), notice window **43/50 parsed: min 6.8d, median 30.9d, max 36.0d** — the fuller sample
reveals a short-notice tail the 40-event sample did not show. **72 `유의 종목 지정`** designations
(2019-02-22 →) plus the softer tiers above. **151 `신규 거래지원`** listings — but that form only
exists from **2024-04-23**, so pre-2024 listings live under the era forms in the table.

#### ITEM 3 — CLOSED. Full archive, era-aware counts, and what catching the selector defect bought.

**Pull complete: 737/737 `category=trade` rows, 2017-10-27 → 2026-07-31 (8.8 years).**
Re-classified with era-aware keys (`원화`+`KRW`, `코인 추가`+`디지털 자산 추가`+`신규 상장`+
`신규 거래지원`, both spacings):

| event class | era-aware n | modern-key n | span |
|---|---|---|---|
| **KRW rail-access (listing / market addition)** | **239** | 43 | 2018-03-22 → 2026-07-31 |
| **delisting** | **97** | 50 | 2018-01-06 → 2026-07-16 |
| **유의종목 designated** | **102** | 72 | 2019-02-22 → 2026-07-31 |
| 유의 촉구 (soft caution tier) | **41** | — | 2022-05-13 → 2026-07-11 |
| 유의종목 released | **18** | 12 | 2019-11-28 → 2026-07-24 |

**Catching my own era-fitted selector multiplied the primary event class 5.6× (43 → 239)** and
roughly doubled delistings and designations. Had I shipped the first pass, every downstream event
study would have run at ~18% of available power on a class the desk would then have called
underpowered — the L1.25 instrument-defect failure, arriving through a selector rather than a gate.
Notice window on the fuller set: **45/97 parsed (min 2.9d, median 30.9d, max 36.0d)** — the 52
unparsed are pre-2022 delistings using a different in-title date format (`(19.01.05 종료)`), which
is more era-convention work owed, named rather than glossed.


**§33 dispositions (2026-08-18, owed-work batch3 — items above, in order):**
- Backlog verification re-scoped (NAVER 4th re-confirm worth zero): [§33: screened] — in-block; queue-design leak = F0002 fixed; NAVER stays credential-blocked
- KR community deep-mine (DCInside/Coinpan/cafés): [§33: killed] — 3/5 grounds refuse Claude BY NAME; replacement ground velog/tistory
- Upbit/Bithumb dev ecosystem + KR GitHub: [§33: screened] — in-block results
### SESSION CLOSE 2026-08-01 session 1 (KR frontier miner) — STANDING TEST, DEPTH, BATTERY, NEXT GROUND

**STANDING TEST — "Which artifact on disk is different because of what was mined?"**
`data/upbit_trade_announcements.jsonl` (**737 rows, 8.8y, new dataset**),
`data/upbit_announcements.jsonl` (100 rows, resumable, all-category),
`data/data_universe_map.json` (**+4 entries**, incl. the KR community layer recorded CLOSED so no
seat re-spends on it), `docs/research/data_axis_watchlist.md` (**axis #26**),
`docs/research/search_operator_library.md` (**OP-041**, **OP-042**, an **OP-038 refinement**, an
**OP-035 extension**, and **+9 KR lexicon rows**, all confirmed in situ),
`recommendation_ledger.json` (**R0298–R0301, R0303**), and this note. **Cycle CONVERTED.**
Honest shape: **zero tradeable cards, one new data axis with four surfaces, one ground permanently
closed on legitimacy, one dated destruction deadline, and a self-caught selector defect.**

**DEPTH LINE (per lead, honest):**
- **Upbit announcement archive: EXHAUSTED for `category=trade`** — 737/737 pulled, classified twice
  (modern keys, then era-aware after I caught the defect), notice window measured, taxonomy mapped
  across five era conventions. **NOT exhausted for the other 7 categories** (`입출금` is the
  rail-state event log and is the obvious next tranche); all-category pull sits at 100/5,685.
- **Upbit / Bithumb market-state endpoints: EXHAUSTED at snapshot depth** — every flag enumerated,
  base rates measured, KRW split forced, cross-venue overlap computed. Cannot go deeper without a
  time series, and there is none to fetch — which is the finding, not a limit of my effort.
- **The delisting event study: went one layer PAST where I would have stopped, and that layer is
  the whole result.** Surface = "40 delisting events, let's screen them". Depth = declared the
  survivorship threat, tested it first, found the treatment group **erased 6/6**, and scoped the
  death to the route (Upbit prices) rather than the capability (global prices survive). **A run
  that skipped that check would have published a study of the assets that did not get delisted.**
- **KR community layer: EXHAUSTED as a question, on primary documents** — three venues, three
  independent closure mechanisms, verdicts recorded so it is never re-spent. Zero content fetched
  from the two that name this agent family.
- **BREADTH-THEATER CHECK — partly guilty, and I will name it.** I mined **zero comment trees, zero
  reply chains, zero repo forks and zero citation chains this run.** The DEPTH MANDATE's
  reply-chain limb went entirely unserved. The honest defence is that all three KR discussion
  venues were closed by §13 or Cloudflare, so there was no legitimate comment layer to mine — but
  the honest admission is that I did **not** substitute velog/tistory (both **CLEAN**, both on my
  ground, both untouched), and that is a gap I chose by pursuing the venue-API seam instead. Named,
  and it is the first item next run.

**PROACTIVE BATTERY (moves run; a move that produced nothing is named, never skipped):**
- **#3 CONFIG-VS-OUTCOME — the run's biggest payout, three times.** (a) Refused to accept
  `needs-legitimacy-review` as a verdict and fetched the actual `robots.txt` — which reversed the
  desk's grading on two venues at once. (b) Refused to accept "the blocker is a NAVER key" and
  probed the sibling endpoints — which tripled what that key is worth. (c) Refused to trust that a
  venue keeps its own history and tested six delisted markets — which killed the study I had just
  pre-registered. **Every one of the three changed a verdict, and none was more than a minute.**
- **#9 SCOPE THE NEGATIVE RESULT — four times, and it is the discipline that carried this run.**
  The KR community closure split into three *different* mechanisms (§13-named / §13-blanket /
  CDN-walled) instead of one "KR is blocked"; the purge scoped to *Upbit prices*, not to the study;
  Coinpan scoped to *the CDN edge*, not to OP-038 being wrong; the NAVER 401 scoped to *the route*,
  with the licensed alternative named.
- **#1 CONTINGENCY BEFORE FAILURE — paid out immediately.** Bithumb was catalogued as a *second*
  KR venue publishing the same warning field before anyone asked what happens if Upbit closes. It
  then turned out to carry the rail-state endpoint Upbit does not have.
- **#4 REGRESSION SWEEP — what this run made worse, plainly.** I added **5 rows (R0298–R0301,
  R0303)** to a queue the conversion fence already calls REPAIR-MODE, one of them with a **2-day
  fuse**. Real cost, stated not hidden. Mitigating: R0298 makes a **DEGRADED** organ healthy rather
  than adding surface, and L1.28b(f) exempts miners from repair-mode throttling by name. Second
  cost: `data/upbit_announcements.jsonl` is a **partial** 100-row file that could be mistaken for
  the full archive — labelled resumable in the universe map, but it is a loose end.
- **#10 RATCHET CHECK — floors that must not fall:** operators 41 → **43** (+2 refinements); KR
  lexicon 6 → **15 rows**; KR session notes 0 → **1**; universe-map `regional_venues_kr_jp` 6 → **10**;
  desk-known KR event archive 0 → **737 rows / 8.8y**.
- **#2 ADJACENCY — ran, and it found the highest-ROI row.** After finding the Upbit feed I asked
  where else this shape lives and found `scripts/collect_announcements.py` **DEGRADED** with both
  its exchange sources broken — so the find is a *repair*, not an addition (R0298).
- **#6 GENERALISE THE RULE — ran.** The robots-first check is not a KR rule; it is now **OP-041**
  with the AI-crawler UA list, and it predicts the pattern (consumer-web portals closing, venue and
  developer infrastructure staying open) rather than just recording this instance.
- **#5 COST INVERSION — ran, paid out.** Every surface here is keyless and first-party; the one
  paid-shaped question (KR search attention) resolves to a **free** registration whose value I
  raised rather than to a purchase (R0300).
- **#8 NEGATIVE SPACE — ran.** "What has never been looked at at all" on this ground was *the venue
  APIs' non-price surface*. It had never been asked, and it is where the entire session's value was.
- **#7 AUTONOMY CHECK — produced nothing this run**, reported as such.

**VIDEO-LOCKED: nothing logged, and deliberately so.** I attempted **no** KR video this run —
tistory/velog/YouTube KR were in my ground and I did not reach them. That is a **coverage gap, not
a route failure**, and logging it as a blocker would corrupt the purchase-trigger evidence the log
exists to hold. A platform is logged only after a real attempt fails.

**VENUE DISCOVERY (obligation: every run finds venues not on the seed list):**
| venue | what lives there | how found | verdict |
|---|---|---|---|
| `api-manager.upbit.com/api/v1/announcements` | 5,685 dated KR venue events, 8.8y, keyless | endpoint probe | **RICH** — now axis #26 |
| `api.upbit.com/v1/market/all?isDetails=true` | venue-computed retail-crowding + premium flags | `isDetails` param guess | **RICH** — now OP-042 |
| `api.bithumb.com/public/assetsstatus/ALL` | per-asset deposit/withdrawal rail state | second-venue contingency | **RICH** — independent barrier measure |
| `api.bithumb.com/v1/market/all?isDetails=true` | 2nd KR venue warning field, 17 CAUTION | ditto | **RICH** |
| `openapi.naver.com/v1/search/{blog,cafearticle,news}` | licensed route to KR consumer web | sibling-endpoint probe | **WALLED — free key (GAP #69)** |
| `coinpan.com` | KR crypto forum; robots CLEAN | robots.txt | **WALLED** (Cloudflare edge, all routes) |
| `gall.dcinside.com` | KR trading galleries | robots.txt | **§13 HARD STOP** — names this agent family |
| `cafe.naver.com`, `blog.naver.com` | KR cafés/blogs | robots.txt | **§13 HARD STOP** — named + RAG-prohibited |
| `velog.io` | KR dev writeups; **zero robots rules** | robots.txt | **OPEN — CLEAN, UNMINED** |
| `www.bithumb.com` | venue site; no `Disallow` at all | robots.txt | **OPEN — CLEAN, UNMINED** |
| `kimpga.com` | premium tracker; `Allow: /` | robots.txt | **OPEN — CLEAN**, corroboration only |

**NEXT RUN TAKES FIRST (the chain — do not re-surface-scan the above):**
1. **`velog.io` + tistory KR quant/algo writeups, to comment depth.** Both **CLEAN**, both on my
   ground, both untouched, and they are the *replacement* for the closed community layer — this
   closes the reply-chain gap I named above. **Highest priority precisely because it is the limb I
   failed this run.**
2. **The global-priced delisting event study** — 97 events, prices intact off-venue, hypothesis and
   falsifiers already pre-registered above. Use `libs/validation/event_study.py`, `n_cohort=1`,
   **never `axis_screen`**.
3. **The KRW rail-access study (239 events)** — the cleaner natural experiment: asset already on
   Upbit's BTC/USDT books, KRW rail opens, discovery held constant.
4. **`category=입출금`** — the deposit/withdrawal event log, i.e. the *historical* barrier-state
   series to pair with today's snapshot; plus finish the all-category pull (100/5,685).
5. **Parse the 52 pre-2022 delisting effective dates** (`(19.01.05 종료)` format) — more era work.
6. **Era-archaeology proper: still entirely unopened on this ground.** The 2017–18 kimchi-mania
   boards, pre-real-name-law communities, Ppomppu — **zero era work happened this run**, and with
   DCInside and Naver closed the route must be Wayback/mirror-based. Naming it rather than letting
   the dark-forest era limb quietly lapse.

---

## SESSION NOTES — JP frontier miner


**§33 dispositions (2026-08-18, owed-work batch3 — items above, in order):**
- velog+tistory to comment depth: [§33: screened] — velog OPENED s5 08-04 (OP-050); tistory half deferred(2026-08-25)
- Global-priced delisting event study (97 events): [§33: wired -> libs/research/listing_events.py + delisted rosters]
- KRW rail-access study (239 events): [§33: deferred(2026-08-25)] — carded route (watchlist card #26)
- category=입출금 deposit/withdrawal log: [§33: deferred(2026-08-25)] — partially advanced by the 08-12 rail corpus
- 52 pre-2022 delisting effective dates: [§33: deferred(2026-08-25)] — fold-in to rosters unverified; deferral keeps it owed
- Era-archaeology (Ppomppu, pre-real-name): [§33: screened] — s5 bootstrap + 08-12 era-seek artifacts
### 2026-08-01 session 1 (JP frontier miner, SEAT'S FIRST RUN) — IN PROGRESS (write-first note; updated as items resolve)

**RESUME check done first.** `source_backlog_next.py --limit 6` → 5 pending technical
verification + 3 pending a legitimacy decision. Exactly ONE of the eight is JP-region:
**bitFlyer getexecutions + self-recorded candles** (`data_axis_watchlist.md` item 3, graded
`needs-legitimacy-review`, `[§33: deferred(2026-08-09) tier:2]`). The seat's own prior note: none
— this is run 1. The carried-since-07-20 unstarted ground is the **richmanbtc/note.com botter
lineage** (addendum C62, named a gem 12 days ago and never dug).

**ITEMS TAKEN THIS RUN (bounded scope, maxed depth):**
1. **§13 robots.txt sweep of all five assigned JP grounds** — the KR seat's s1 lesson propagated
   under charter §16 (it found 3 of 5 KR grounds refuse this agent BY NAME). Must run before any
   digging, because a seed list is not an authorisation.
2. **bitFlyer legitimacy (T2 backlog item, blocking, human-dependency)** — re-open the "WAF-blocked,
   needs a human to read one page" verdict. Route-vs-capability (battery move #9).
3. **richmanbtc / note.com botter lineage to genuine depth** — the named-and-never-dug gem.

---

#### ITEM 1 — §13 ROBOTS SWEEP: **RESOLVED. 5ch IS REFUSED BY NAME; THE OTHER THREE ARE CLEAN.**

| Ground | robots.txt verdict for this agent | Evidence |
|---|---|---|
| **5ch.net** (+ `itest.`, `egg.`, `kizuna.` sister hosts) | **REFUSED — `User-agent: ClaudeBot` → `Disallow: /`** | verbatim, all four hosts |
| note.com | **CLEAN** — no Claude/Anthropic UA anywhere; `/api/*`, `/search`, `/*/archives` disallowed for `*` | article paths allowed |
| qiita.com | **CLEAN** — no Claude UA; `/api/*` disallowed for `*` (`Allow: /api/*/docs$`) | sitemap published |
| zenn.dev | **CLEAN** — no Claude UA; only `/search` disallowed for `*` | sitemap published |

**5ch is out of scope for this seat, permanently, until the file changes.** It was an assigned
ground; the assignment does not override the site's own refusal (§13). Recorded, not routed around.

**THE PROPAGATION FINDING, which is bigger than 5ch (charter §16 — fleet-wide):** the 5ch block is
delimited in the file by `# BEGIN Cloudflare Managed content` / `# END Cloudflare Managed Content`.
It is **not a hand-written site decision** — it is Cloudflare's *managed robots.txt* feature
emitting a standard AI-crawler block list (`ClaudeBot`, `GPTBot`, `CCBot`, `Google-Extended`,
`Applebot-Extended`, `Bytespider`, `meta-externalagent`, `CloudflareBrowserRenderingCrawler`).
Two consequences the fleet must carry:
- **This is now the second region in two days to lose grounds to the same block** (KR lost naver
  cafe/blog + dcinside on 08-01). The correct prior is no longer "some sites block us" but
  **"any Cloudflare-fronted community site is likely to refuse this agent by name"** — so the
  robots check is cheapest run FIRST and is now mandatory per ground, not per region.
- The same file carries `Content-Signal: search=yes, ai-train=no, use=reference` for `User-agent: *`.
  That signal would have *permitted* reference use. **The named-agent `Disallow: /` overrides it,
  and reading the permissive generic block alone would have produced a false "allowed" verdict** —
  the exact loophole the KR seat warned about, confirmed independently on a second region.

---

#### ITEM 2 — bitFlyer legitimacy: **RESOLVED. THE LICENCE IS READ. VERDICT: RESTRICTED. HUMAN DEPENDENCY REMOVED.**

The card (`data_axis_watchlist.md` item 3) said: WAF-blocked → licence unread → **"one page-read by a
human"** → `[§33: deferred(2026-08-09)]`. Three of its recorded facts were wrong, and the fourth
conclusion did not follow. All four corrected against artifacts fetched this run.

**(a) THE FAILURE MODE IS NOT A 403 AND NOT AN IP BLOCK.** The card records "403" and "WAF-blocked".
Actual behaviour: TLS completes, cert verifies (`O="bitFlyer, Inc."`), the HTTP/2 stream OPENS, then
`INTERNAL_ERROR (err 2)`; over HTTP/1.1 and over IPv4 it simply **hangs to timeout** (`code=000`).
An Akamai tarpit, not a status code. **And it is not our IP:** `api.bitflyer.com` and
`lightning.bitflyer.com` both return **200 from the identical edge IP** (`2a02:26f0:e80:588::2644`)
that tarpits `bitflyer.com`. Same node, same TLS, different `Host` → one serves, one hangs. So the
policy is **per-hostname on the marketing/legal site**, and the API + docs hosts were never blocked.
*Generalises: diagnose a block by varying ONE thing at a time against the same edge — an "our IP is
banned" verdict that never tried a sibling hostname is a guess.*

**(b) "NEVER USEFULLY ARCHIVED" IS REFUTED — the CDX probe used the wrong host AND the wrong slug.**
The card queried `bitflyer.com/{en-jp,ja-jp}/*`. The pre-migration host is **`bitflyer.jp`** and the
slug is **`terms-of-use`**, not `terms`. Correct query returns captures immediately, incl.
`https://bitflyer.jp/en-eu/terms-of-use` (2019-06-01, **200**) and
`bitflyer.jp/pub/terms-comparison-table-201711-ja.pdf`. *A negative CDX result is a statement about
the query, never about the archive.*

**(c) THE OPERATIVE CLAUSE, READ AND QUOTED VERBATIM** (`/en-eu/terms-of-use`, capture 20190601153535):
> "The bitFlyer API is the copyrighted technology of bitFlyer and may not be copied, imitated or
> used, in whole or in part, outside of the API's intended use. bitFlyer retains all its rights
> related to its databases, websites, ... **including chat text, the content of bitFlyer emails, and
> data such as transaction prices** — developed or provided by bitFlyer or its affiliates **which can
> be acquired by various external APIs**. bitFlyer may demand any third party stop using bitFlyer's
> API for any purposes not authorized by bitFlyer."

Reinforced by: *"you may use the bitFlyer Materials only for your internal purposes and solely as
necessary for your use of the Service"*; and a bar on *"any robot, spider, crawler, scraper, script
... not authorized by us to access the Services, extract data"*.

**VERDICT: `restricted-by-licence`.** The venue names transaction-price data acquired via its
external APIs as retained property and conditions use on *"your use of the Service"*. Our proposed
use — bulk automated recording of executions by a non-customer, to build a research dataset — is
squarely what that text refuses. §13 is a HARD STOP, not a hurdle: **do not build a bitFlyer
direct-recording collector.**

**HONEST RESIDUAL, stated so nobody over-reads this:** the document read is the **EU entity's**
2019 ToS, not the JP entity's current 利用規約 (JP-side `terms-of-use` paths return no CDX captures;
the live host is tarpitted). So this is bitFlyer *group's* stated position, strongly against, rather
than a JP-entity ruling. It does not need to be: §13 asks whether a licence forbids the use, and the
only bitFlyer terms document the desk has ever actually read says yes. **Grading a restriction on
the evidence we have beats deferring a fourth time on evidence we cannot get.**

**THE SAME CLAUSE PRE-EMPTIVELY KILLS TWO THINGS I FOUND THIS RUN** before they could be carded —
which is the clause earning its keep rather than a coincidence:
- `GET /v1/getchats` — **live, keyless, returns real JP retail chat** (verified: 2026-07-27
  messages, nicknames, timestamps). A venue's own retail chat is structurally unbuyable and I would
  otherwise have carded it immediately. Clause 678 names **"chat text"** explicitly. **BLOCKED.**
- `GET /v1/getfundingratehistory` — live, keyless, verified returning 8-hourly JP funding
  (`rate` 0.0001 / 0.00199, calculation+settlement dates). Funding/carry is the desk's *only*
  repeat-surviving family, so this is the one I most wanted. Same clause. **BLOCKED.**

**AND IT BLOCKS THE BIGGEST FIND OF THE RUN, WHICH I AM NOT GOING TO LAUNDER THROUGH THE ARCHIVE:**
CDX surfaced `https://bitflyer.jp/api/chart/btc_jpy?start=<ms>&end=<ms>` — an **undocumented keyless
price-series endpoint, dead on the live site (302) but captured 200 by Wayback from 2015-08**.
Verified payload: **414,675 bytes, `[[epoch_ms, price], …]` at 15-minute steps, 2014-10-16 →
2015-08-12 in a single capture** — i.e. ~10 months of BTC/JPY per capture, with many captures at
differing windows, from the era when JPY was the world's top BTC fiat pair. That is exactly the
"irreplaceable, competitor-must-pay-to-reconstruct" asset L1.11a tells me to hunt.
**It is still bitFlyer's data.** Reading it from a third-party archive does not extinguish the
venue's stated rights in it, and "the Internet Archive had a copy" is not a licence. **NOT CARDED.**
Recorded here in full so no future seat spends the discovery cost again and so the finding survives
if the licence position ever changes (L1.16a re-entry condition: **a bitFlyer JP-entity ToS, or an
explicit bitFlyer data-use permission, that does not retain rights in transaction prices**).

**THE LICENSED SUBSTITUTE ALREADY EXISTS AND THE DESK ALREADY OWNS IT.** `data_axis_watchlist.md`
records Tardis.dev covering **`bitflyer` since 2019-08-30**, free first-of-month, under a licence
whose *internal research use is PERMITTED*. So the correct disposition of this axis is not "wait for
a human" — it is **use the licensed path, drop the direct-collector plan**. Residual gap is
granularity (1 day/month), not availability.

---

#### ITEM 3 — richmanbtc / note.com botter lineage: **RESOLVED. THE NAMED GEM IS A MAKER-REBATE ARTIFACT; THREE OF ITS TOOLS ARE REAL.**

Carried unstarted since 2026-07-20 (addendum C62, "the anti-consensus gem"). Dug this run to repo +
fork + notebook + community-reply depth. **The headline is a kill, and it is a good one.**

**THE MECHANISM IS DEAD → `docs/graveyard.md` `jp_mlbot_atr_limit_reversion`.**
`github.com/richmanbtc/mlbot_tutorial` (519★, 187 forks, **CC0-1.0** and **dead since 2022-11-28** —
both verified by me via the GitHub API, not taken on report). LightGBM on ~43 TA-Lib features
predicting the P&L of a passive limit rule, GMO Coin BTC_JPY 15-min, 2018-10→2021-04.
**The community itself did the attribution** (バジル, `note.com/kkngo/n/n631e9fdc7855`): the edge is
**「毎回ATR×0.5の位置に指値を置くだけ」** — the bare ATR×0.5 limit returns ~1700% over the window with
**no ML at all**, and the ML layer leaves cumulative return **almost unchanged**. And the rule is a
**fee artifact**: the tutorial's own `maker_fee_history` is `0.0 → -0.00035 → -0.00025 → 0.0`, i.e.
**the maker fee is zero or NEGATIVE across the entire backtest.** It is a venue-subsidy harvest.
Three independent practitioners then watched it die on three different venues/timeframes
(kkngo 2023 JP; chanta Bybit 12h, died 2024-03; pip_pip_pip_p Binance, down monotonically from 2022
through the 2024 bull market). **Its own author publishes numbers that fail his own two bars**
(p-mean 0.2005 vs bar 1e-5, ~840× off; non-stationarity 0.4556 vs bar 0.3) and states
「そのままでは儲からない」 up front. Method defects recorded in the graveyard entry: `KFold()` at
sklearn defaults trains on the future for **4 of 5 folds** with purging explicitly omitted;
frictionless fills; no liquidation.

**THREE TOOLS SURVIVE → `docs/research/improvement_inbox.md` (all CC0, verified):**
1. **p平均法 (p-mean)** — an **order-sensitive** significance bar. Our whole promotion stack
   (t-test/PSR/DSR) is **order-invariant** and therefore blind to late-window decay; under L1.30
   that is exactly the blind spot we cannot afford. **But I reproduced a real bug in the published
   error-rate formula on this box:** it is the Irwin–Hall lower tail, valid only for `p_mean ≤ 1/N`,
   and it returns **8.53 at `p_mean=0.8, N=5`** and **26.04 at `p_mean=1.0`** — unbounded above 1,
   no guard. The tutorial's **own headline run** (`p_mean=0.2004701…`) already sits outside the
   valid region (`N·p_mean = 1.00235`); my reproduction returns its exact published
   `0.008431733454943706`, which confirms the transcription is right and the *formula* is wrong.
   Adoption also requires a **pre-registered window**: opecry (`note.com/opecry/n/nc064da3a68b8`)
   improved p-mean 0.2→0.04 and the error rate 0.008→6.4e-7 — **four orders of magnitude — purely
   by deleting the sub-period where the curve dipped.**
2. **richman非定常性スコア** — adversarial validation with **time as the label** (fit LGBM on
   `np.arange(n)`; R² is the score; `feature_importances_` names the offenders; ships as a drop-in
   sklearn transformer). Our critique: `shuffle=True` makes index-prediction near-trivial, so it
   measures interpolation, not extrapolation, and the 0.3 threshold is unjustified (the author's own
   baseline is 0.4556 and he ships it). Worth building in the **ordered-fold** variant.
3. **`publicGetExpiredFutures`** — survivorship-free universe construction solved **venue-side in
   three lines**, in 2021. Directly shortcuts **R0239**, and the KR seat's Upbit candle-purge finding
   is the same defect class. **Ask every venue for its own graveyard before reconstructing one.**

**THE CROSS-CORROBORATION THAT MATTERS.** `crypto_data_fetcher` (CC0) pulls
`api.coin.z.com/data/trades/{MKT}/{YYYY}/{MM}/{YYYYMMDD}_{MKT}.csv.gz`, **scanning from 2018** — the
*exact* endpoint I had independently found an hour earlier while hunting a licensed replacement for
the §13-restricted bitFlyer axis. **Two unrelated routes, same artifact, same session.** That is the
strongest confirmation available short of a second model family, and it upgrades axis 27 from "a
thing I probed" to "the JP scene's standard historical source". Nulls, stated: 187 forks produced
**one** substantive derivative (a Bybit port); GitHub has **zero** discussion; both "advanced"
notebooks are **empty stubs** (「執筆中」); the author's own P&L disclosure is **an image**.

**VENUE DISCOVERY (standing obligation) — where the JP botter community actually is:**
| Venue | What lives there | Verdict |
|---|---|---|
| **仮想通貨botter Qiita Advent Calendar** (2021–2025, `qiita.com/advent-calendar/{YYYY}/botter`; 2022 had 32 participants × 3 series) | **The community's real annual record — where the post-mortems get published.** 4 of the 5 best sources this run came from it | **RICH — the single highest-yield JP ground found. NEXT RUN'S PRIMARY.** |
| **マケデコ / Market API Developer Community** (Discord, run *with* **JPX総研**; `mkdeco.connpass.com`; own Advent Calendar) | J-Quants API (JPX official JP equities+options). Institutionally backed | RICH-adjacent (equities, not crypto) |
| **Bivolab** (Discord, operated by **bitbank** itself) | exchange-run botter lab | UNVISITED |
| X/Twitter `#botter` | primary hub; `@richmanbtc2 @blog_UKI @richwomanbtc @yoshiso @MtkN1 @magimagi1223 @i_love_profit @morio202008` | hub, long-form spills to note/Zenn/Qiita |
| Blog network | `blog.shidokamo.com`, `tech.takibi.net` (yasstake/RustyBot), `gitan.dev`, `mirumi.me`, `rarirure.rip`, `yodakaart.tech` | UNVISITED |
| `jodawithforce.hatenablog.com` | JP botter blog | **WALLED (403)** |
| note.com comment layer | loads via `/api/*` | **OUT OF BOUNDS — robots.txt disallows `/api/*` for `*`.** Not a wall we may route around |

**A COMMUNITY NORM WORTH RECORDING, because it explains the shape of everything above.** UKI names
オフ会 (offline meetups) as where live information is exchanged, on the norm that botters discuss
**exhausted** edges openly and never advertise active ones. **⇒ The published JP record is
structurally a post-mortem archive.** That is not a limitation to complain about — it is a
*specification*: mine this ground for **deaths, decay dates and method defects** (which is exactly
what it yielded), and never expect a live edge from it.

---


**§33 dispositions (2026-08-18, owed-work batch3 — items above, in order):**
- §13 robots sweep of all five JP grounds: [§33: screened] — in-block sweep results (5ch blocks ClaudeBot by name)
- bitFlyer legitimacy (T2 human-dependency): [§33: wired -> commit eaa8b84a] — licence READ, 403/no-archive claims refuted, dependency removed
- p平均法 order-sensitive bar + Irwin-Hall bug: [§33: screened] — critique + reproduced bug in session record
- richman非定常性スコア adversarial validation: [§33: screened] — shuffle critique in session record
- publicGetExpiredFutures survivorship-free universe: [§33: wired -> data/delisted_rosters/binance_futures.json + scripts/probe_delisted_instruments.py]
### SESSION CLOSE 2026-08-01 session 1 (JP frontier miner) — DEPTH, BATTERY, STANDING TEST, NEXT GROUND

**DEPTH LINE (per promising lead):**
| Lead | Depth reached | What depth surfaced that the surface did not |
|---|---|---|
| bitFlyer legitimacy | **EXHAUSTED** (live 4 ways × 2 IP families × 2 HTTP versions, 3 sibling hosts, CDX domain dump, ToS body read) | The whole finding. Surface = "403, ask a human". Depth = a **tarpit not a 403**, a **per-hostname** policy proven by 200s from the same edge IP, an archived ToS the prior probe's *query* had missed, and the **verbatim IP clause** that closes the item |
| bitFlyer CDX domain dump | **repo-equivalent of fork depth** | The undocumented **`/api/chart/btc_jpy`** endpoint — invisible to any path-guessing probe; only the full key dump reveals it |
| richmanbtc lineage | **repo + 100 forks + notebooks + Qiita/note back-catalogue + community reply layer** | The surface is a 519★ ML tutorial. Depth is: the ML **adds nothing** (kkngo), the fee was **negative**, three dated **deaths**, a **live exploit** of its own metric (opecry), and a **reproduced formula bug** |
| GMO Coin | **EXHAUSTED technically** (payload, schema, ms timestamps, day-precision start boundary, 40-symbol universe, robots) — **licence unread** | An entire free JP tick tape the desk did not know it could have |
| bitbank | **surface + structural-zero test** | `success:1` hiding **~1,090 phantom pre-launch bars**. One extra column check separated a good source from a poisoned one |

**Not breadth-theater:** 3 items taken, 3 closed, 2 marked EXHAUSTED, and every conclusion rests on
an artifact fetched this run.

**PROACTIVE BATTERY — moves run, and what each produced (a move that produced nothing says so):**
- **#9 SCOPE THE NEGATIVE RESULT** — *the run's highest-yield move.* "bitFlyer ToS unreachable" was a
  **route** failure read as a **capability** failure for four sessions. Separating them closed the item.
- **#2 ADJACENCY** — the same shape immediately: the KR seat's robots lesson applied to JP found 5ch;
  the bitFlyer licence kill was then applied forward to pre-emptively block `getchats`,
  `getfundingratehistory` and the archived chart series *before* they were carded.
- **#3 CONFIG VS OUTCOME** — demanded the artifact everywhere: fetched the CSV, decompressed it, read
  the rows; counted zero-volume bars rather than trusting `success:1`; verified CC0 and the formula
  bug myself rather than accepting the scout's report.
- **#1 CONTINGENCY BEFORE FAILURE** — the bitFlyer kill was not allowed to stand alone; GMO + bitbank
  were hunted **in the same run** as its replacements.
- **#6 GENERALISE THE RULE** — three findings promoted to fleet operators (OP-043/044/045) plus an
  OP-041 refinement; none left as JP-local trivia.
- **#10 RATCHET CHECK** — 5ch's robots verdict is explicitly marked **do not cache** (the Cloudflare
  list grows), so today's clean is not tomorrow's clean.
- **#5 COST INVERSION** — **produced nothing this run.** No paid path was proposed or needed; the
  video-locked log stays untouched because no mechanism was video-only. Recorded, not skipped.
- **#8 NEGATIVE SPACE** — produced the next-ground answer below (the Advent Calendar archive, five
  years deep, never touched by this desk).

**STANDING TEST (L1.11a):** does it carry information a competitor must pay to reconstruct?
**GMO tick tape — YES** (JP-only tickers at tick resolution, free, 7.9y, absent from English
catalogues). **bitbank phantom-history — YES, inverted**: knowing where a free source *lies* is worth
as much as the source. **bitFlyer — moot, licence forbids.** **The Advent Calendar archive — YES**:
five years of JP-language post-mortems with dates and numbers, which is precisely the material our
graveyard is made of.

**DIASPORA — "where did they go?"** JP is the one region so far that **did not scatter**. Unlike CN
(into paid/ID-gated enclosures, §13-unreachable) and RU (barrier migration), the JP botter community
**consolidated onto X + an annual Qiita Advent Calendar**, and its exchanges even run *official*
Discords (Bivolab/bitbank, マケデコ/JPX). The migration that did happen is **venue-side**: FTX's death
(ky's ¥15M loss report) pushed the scene onto **Bybit/Binance**, which is why post-2022 JP writeups
are Bybit-centric while the 2018–2021 canon is GMO/bitFlyer-centric.

**§13 LEDGER FOR THIS RUN:** 5ch **REFUSED by name** (recorded, not routed around) · bitFlyer
**RESTRICTED by licence** (killed, not worked around) · note.com `/api/*` **out of bounds** (comment
layer left unmined rather than fetched) · note/qiita/zenn/GMO/bitbank **CLEAN** · GMO robots
**explicitly `Allow: /`**. Nothing was accessed against a stated refusal.

**NEXT UN-EXHAUSTED GROUND, in order, for JP session 2:**
1. **仮想通貨botter Qiita Advent Calendar 2021–2025** — up to ~75 slots/year × 5 years, **never
   touched**, and it is where this community publishes its dated post-mortems. Mine year-by-year and
   claim **SECTION-EXHAUSTION per year** (L1.35). This is the JP ground's richest seam by a distance.
2. **Close the two licence reads (R0309/R0310)** — GMO and bitbank; both hosts serve us, both bodies
   are JS-rendered, both block real ingest of a verified-clean tape. Cheapest unlock on the board.
3. **Era-archaeology, NOT YET STARTED** — the 2017 bitFlyer-FX **SFD** (Special Fee for Deviation)
   mechanics: an *exchange-imposed* mechanical convergence band between FX_BTC_JPY and spot BTC_JPY,
   i.e. a rule that literally forces traders to pay for deviation. Strong mechanism prior
   (a named party is compelled), and the era's discussion is in 5ch archives — **which are
   ClaudeBot-refused live**, so this must be reached via Wayback/mirrors or it does not get reached.
   Mt.Gox-era threads likewise.
4. **Bivolab (bitbank's own Discord) + the six-blog network** — unvisited.
5. **JP lexicon** — seeds `okuribito / gachiho / inago / yobun` remain **UNVERIFIED**. The CN seat's
   OP-037 is explicit: negative-control a supplied glossary before spending budget on it (0/7 CN
   terms survived). Do that before using any of them as search keys.

**Which artifact on disk is different because of what was mined?** `docs/graveyard.md` (+1 kill),
`docs/research/data_axis_watchlist.md` (entry 3 closed after 4 deferrals; entries 27–28 new),
`docs/research/improvement_inbox.md` (+3 engine tools), `docs/research/search_operator_library.md`
(OP-043/044/045 + OP-041 refinement), `data/data_universe_map.json` (+4, **but see R0311 — that file
is gitignored**), this coverage doc, and ledger rows **R0309–R0313**.

---

## SESSION NOTES — BR frontier miner


**§33 dispositions (2026-08-18, owed-work batch3 — items above, in order):**
- botter Advent Calendar 2021-2025: [§33: wired -> data/jp_botter_advent_calendar.jsonl] — 187 entries, s6 08-04
- GMO/bitbank licence reads (R0309/R0310): [§33: deferred(2026-08-19)] — cards 27/28 DECIDE-queue owed
- 2017 bitFlyer-FX SFD mechanics: [§33: killed -> docs/graveyard.md jp_sfd_boundary_game] — s6
- Bivolab + six-blog network: [§33: deferred(2026-08-25)] — no visit evidence since
- JP lexicon seeds: [§33: screened] — s6: 13 rows, 養分+イナゴ verified, ガチホ stays SEED
### 2026-08-01 session 1 (BR frontier miner, SEAT'S FIRST RUN) — IN PROGRESS (write-first note; updated as items resolve)

**No BR row existed in this document before this run.** The seat has never been run. Per the RESUME
mandate I read the backlog (`source_backlog_next.py`: 8 pending verification, 2 pending a legitimacy
decision — **none BR**), the region table above (**no BR entry**), and the three prior first-run seat
notes (KR s1, JP s1, RU s1) for propagated operators. There is no prior BR session to resume from, so
this run opens the ground.

**PRE-EMPTIVE GRAVEYARD CHECK — DONE BEFORE ANY SEARCHING, AND IT KILLED ONE THIRD OF MY OWN BRIEF.**
My seat brief names as an era target: *"USD-restriction-era P2P premium mechanics (another
premium-analog provenance)"*. That ground is **already dead, and Brazil specifically is already
dead**:
- `docs/graveyard.md:81` — `bitbank_jp / mercado_br premiums`: *"mercado SCREEN-WEAK, same-day −0.27
  ... **Brazil rejected**. Regional-premium class is now exhausted: kimchi is the lone survivor across
  KR/JP/BR/TR/Coinbase tested."* **The desk has already screened the Brazilian premium and killed it.**
- `docs/graveyard.md:244–268` — the CROSS-ERA SYNTHESIS, five instances deep, states the law:
  *"**do not hunt for a region whose barrier is low enough to arb — that region's premium is already
  zero**"* and *"a persistent cross-venue premium is rent on whatever barrier is currently binding."*
- And the lone survivor that the whole family was ranked against — kimchi — was itself **REFUTED** at
  full 8.2y depth on 2026-07-30 (IC +0.0012, n=2987). So the family's best case is now zero too.

Under **L1.16a** re-opening a graveyard entry requires a **NAMED ENABLING CHANGE** addressing the
original mechanism of death. I have none: Brazil's mechanism of death was *low barrier height* (BRL is
freely convertible, no capital controls), and nothing about that has changed. **I am therefore NOT
spending this run on the BR premium, and I am recording the seed list itself as the defect** — a brief
pointing a fresh seat at a six-times-killed family is how a desk burns a whole first run re-deriving a
known null. Routed as a finding, not silently skipped.

**ITEMS TAKEN THIS RUN (bounded per the completion contract; depth per item unbounded):**

1. **§13 ROBOTS SWEEP of every named BR ground, before spending a single query on any of them.**
   Propagated OP-041. This has now fired on **2 of 2** prior first-run seats (KR: 3 of 5 grounds refuse
   ClaudeBot by name; JP: 5ch + all sister hosts refuse by name). A third region is the test of whether
   that is a pattern or a coincidence, and the answer changes where this seat is aimed permanently.

2. **BR STATE + VENUE DATA LAYER — the keyless-API hunt.** This is what actually paid for both prior
   first runs when their community ground turned out to be closed (KR: Upbit 5,685-event archive;
   JP: GMO free tick tape from 2018). `data/data_universe_map.json` currently contains **ZERO** Brazilian
   entries. Priority order by *reverse-engineering cost per unit of effort* (L1.11a), not by familiarity:
   **(a)** Receita Federal **IN 1888/2019** — every Brazilian exchange is *legally compelled* to report
   every crypto transaction to the tax authority monthly, and RFB publishes aggregates. A national
   mandatory-reporting crypto flow series is **structurally unbuyable**. **(b)** BCB open data (SGS
   series, PTAX, **Pix** instant-payment rails = the crypto on/off-ramp). **(c)** Mercado Bitcoin's
   public trade tape (the premium is dead; **the tape is not the premium**). **(d)** B3 free historical
   series. Every one gets the OP-042/OP-045 treatment: does it fire, does it have history, and is the
   history real rather than `success:1` phantom bars.

3. **BR PRACTITIONER GROUND, mined to reply-depth ≥2 / fork depth.** PT-BR GitHub quant repos and one
   live community chain, hunting **untested alphas** (L1.34 #6, the richest and most neglected vein) and
   **engine ideas** — not another premium.

**STANDING OPEN QUESTION (diaspora):** where did the BR crypto community go? Named checkpoints to
answer against: the 2017 mania boards, the Mercado Bitcoin early era, and the flow between local venues
and Binance BRL.

_Status: note written 2026-08-01 before any searching. Items resolve below._


#### ITEM 1 — CLOSED. §13 ROBOTS SWEEP: **the KR/JP pattern does NOT generalise. BR's community layer is open; the one hard stop is a global platform, not a BR site.** [§33: wired -> docs/research/search_operator_library.md OP-041 adaptation]

Ran OP-041 over **18 hosts** covering every ground in my brief, reading all three layers (the `*`
block, any block naming an AI crawler, and prose headers). **Full-file grep, not a truncated head** —
my first pass cut at 1,200 bytes, which would have hidden a by-name block further down a long file
(GitHub's and MQL5's both are long). Re-ran as a whole-file regex over 17 AI-crawler tokens.

| Host | AI-crawler block | Verdict |
|---|---|---|
| `www.youtube.com` | none | **CLEAN** (`/results` disallowed — search pages only) |
| `github.com` | none | **CLEAN** |
| `www.b3.com.br` | none | **CLEAN** — the file is literally `User-agent: *` (14 bytes) with **zero directives** |
| `www.bcb.gov.br`, `api.bcb.gov.br`, `olinda.bcb.gov.br` | none | **CLEAN** (`api.` and `olinda.` serve no robots.txt at all) |
| `www.gov.br` | none | **CLEAN** |
| `bitcointalk.org` | none | **CLEAN** (sitemap line only) |
| `bastter.com`, `br.investing.com`, `www.mql5.com`, `www.smarttbot.com`, `www.nelogica.com.br`, `clear.com.br`, `www.infomoney.com.br`, `t.me` | none | **CLEAN** |
| `dadosabertos.bcb.gov.br` | none | CLEAN **except `Disallow: /api/`** — the CKAN portal API. Irrelevant: the real data APIs are on `api.`/`olinda.`, different hosts, both unrestricted |
| **`www.reddit.com`** | — | **HARD STOP: `User-agent: *` → `Disallow: /`, to everyone**, under a Public Content Policy header |
| `www.mercadobitcoin.com.br`, `www.advfn.com` | — | **CLOUDFLARE-WALLED at the edge** (403 on robots.txt itself) |

**THE FINDING IS THE NEGATIVE ONE, AND IT IS LOAD-BEARING.** Two prior first-run seats found their
assigned community ground **named-blocked** (KR 3 of 5; JP 5ch + siblings), and OP-041's stated
expectation was that *"the community layer closes and the API layer stays open."* **In BR the
community layer is open** — bastter, InfoMoney, MQL5, Investing BR, bitcointalk, YouTube, Telegram all
carry no AI-crawler directive. So the KR/JP result is **a property of KR/JP consumer-web portals
(Naver, DCInside, 5ch-on-Cloudflare), not a global rollout**. OP-041's adaptation note is corrected
accordingly: **check per region, and do not carry a regional verdict forward as a prior.**

**The one hard stop is `reddit.com`, and it is a GLOBAL platform decision, not a Brazilian one** — but
it bites BR unusually hard, because r/investimentos, r/farialimabets and r/BrasilBitcoin are where a
large share of BR retail trading talk actually lives. Recorded, not routed around. Two further sites
(`mercadobitcoin.com.br`, `advfn.com`) are Cloudflare-walled **on the HTML**; per OP-038 that is not a
wall on the API, and **`api.mercadobitcoin.net` answers keylessly** — confirmed below.

#### ITEM 2 — CLOSED, AND IT IS THE RUN'S FIND. The BR state/venue data layer, and a **free point-in-time vintage stack** nobody has. [§33: screened -> docs/research/data_axis_watchlist.md entry 29]

`data/data_universe_map.json` held **zero** Brazilian entries before this run. Probed keyless, verified
live, and **read the artifact rather than the marketing page** in every case.

| Source | Status | What it holds |
|---|---|---|
| **RFB `criptoativos_dados_abertos`** | **200, keyless, PARSED** | national **mandatory**-reporting crypto panel, **77 months** Ago-2019→Dez-2025, 66 assets, 4,206 asset-months |
| **BCB SGS** `api.bcb.gov.br/dados/serie/bcdata.sgs.{n}/dados` | **200, keyless** | PTAX FX (series 1), Selic (11) — verified returning live values |
| **BCB Olinda `Pix_DadosAbertos`** | **200, keyless** | Pix instant-payment open data incl. **`EstatisticasFraudesPix`** — per-month Pix fraud/contestation statistics. **UNMINED** |
| **Mercado Bitcoin** `api.mercadobitcoin.net/api/v4` + legacy `/api/BTC/trades/` | **200, keyless** | live tick tape; **rolling window starts ~2024-08** (not 2013 — tested year by year), **1000-row cap per call** (the desk's own pagination lesson) |
| `b3.com.br` | robots-clean, **unprobed** | next ground |

**THE HEADLINE AXIS — and why I did NOT screen it.** Under **IN RFB 1888/2019** (now **DeCripto, IN
2291/2025**) every Brazil-domiciled exchange must report **every** crypto operation with **no minimum
value**; residents must report foreign-exchange and **P2P** activity above R$30k/month. Receita
Federal publishes the aggregate free. Dec-2025 alone: **3,544,986 unique individual taxpayers**,
**R$43.1bn (~US$8bn)** in one month, split **domestic exchange R$26.1bn / P2P R$10.1bn / foreign
exchange R$6.9bn**. All-time by declared value: **USDT R$1.004 TRILLION vs BTC R$269bn** — USDT is
**3.7×** BTC, which says Brazilians are buying a **dollar proxy**, not a speculative asset. That is
the mechanism (EM dollarization / capital flight on a compelled-reporting basis), and it is joinable
to BCB PTAX, which I verified keyless in the same run.

**I deliberately did not run `axis_screen`, and that is the disciplined call, not a skipped duty.**
n = **77 monthly** points with a **~3.5-month publication lag**; the screen needs ~4,268 independent
observations (R0030). A screen here returns a null at ~zero power — **a manufactured false null on a
genuinely novel axis (L1.25), burning multiplicity budget to learn nothing.** Reported **UNDERPOWERED,
not dead**, exactly as the CN seat scoped `unlock_events.json`. The enabling change is named in the
watchlist: use it **cross-sectionally** (66 assets × 77 months = 4,206 asset-months) where breadth,
not length, supplies the observations.

**THE DEPTH LAYER — one past where I would have stopped — is where the real find was.** RFB
republishes the whole file monthly under a **dated filename**, so every release is a **vintage**.
I pulled three and diffed them:
- 2023-05-03 → 2023-08-07: **39 of 42** common months revised **within three months**
- 2023-05-03 → 2026-04-15: **42 of 42** revised; worst **Março-2023 R$15,828mn → R$22,308mn (+40.9%)**
- 2022-01-04 → 2026-04-15: Ago-2019 total **3,940.3 → 4,036.9 (+2.5%)**, unique CPF **160,589 →
  182,935 (+13.9%)** — a month **2.4 years old** was still moving
- revisions are **systematically upward** (late and amended filings accrue for years)

⇒ **Anyone backtesting the current file embeds a look-ahead of up to +41% in the CONDITIONING
VARIABLE** — the R0289 class, which every return-series leak check passes cleanly because the returns
are spotless, and which fails toward a **FALSE POSITIVE** that would survive to a forward clock and
waste a Holm slot. **The fix is free and I proved it works**: 23+ publication dates recovered from
Wayback CDX, and a vintage that is **404 on the live server** was recovered intact (282,624 B, valid
`d0cf11e0` OLE2 magic) via the raw-replay modifier `web.archive.org/web/<ts>id_/<url>`. **Point-in-time
reconstruction back to 2021-09 is PROVEN FEASIBLE, not hoped for.** Generalised as **OP-047**.

**AND THE TRAP FOR WHOEVER BUILDS IT.** Across vintages the file changes **row offset** (10→8),
**column ORDER** (`CNPJ|CPF` → `CPF|CNPJ` — **swapped**, so a fixed reader takes CNPJ ≈2k as CPF
≈160k, an ~80× error that still looks like a plausible count), **number encoding** (2022 is *text*
with BR thousands separators — `float("160.589")` = 160.589, a silent **1000×** error), **labels**,
and even the **filename date convention** (`DDMMYYYY` → `YYYYMMDD`, with a real publication hiatus
2023-09 → 2024-10). Parse by **header semantics per vintage, never by cell address**. Generalised as
the **OP-035 BR extension** — and note the inversion that makes it dangerous: OP-035's earlier
instances *produced nothing*, so you noticed; **this one produces a full, plausible, wrong series.**

**HOW IT WAS READ AT ALL, and how I know the numbers are right.** The box has **no xlrd, no openpyxl,
no olefile**, installs are frozen, and `pandas.read_excel` cannot open a legacy `.xls` — so this
576 KB dataset was, on paper, unreadable. Wrote a ~200-line pure-stdlib **OLE2 + BIFF8** reader
(**OP-046**). It shipped with a real bug I caught and fixed mid-run: cells keyed on `(row, col)`
**silently merged all five sheets** into one plausible grid (a header spliced onto another report's
numbers) — cells carry no sheet id, and the only attribution is the record's **absolute stream offset**
against the BOUNDSHEET positions. Rather than validate against the PDF twin (whose text layer is
CID-encoded and would have needed its own unvalidated extractor), I used **the data's own arithmetic**
(OP-024): PF+PJ=Subtotal and Subtotal₁+Subtotal₂+Domestic=TotalGeral across **78 monthly rows → 0
violations, worst residual exactly 0.00e+00**. That is stronger than text agreement because it spans
three independent column groups **and both RK- and NUMBER-encoded cells**, so a decoder bug could not
cancel.

**INCIDENTAL — a BR-only tokenized-RWA universe, sitting in a government dataset.** Of the 66 assets:
**`MBPRK02/03/04` = tokenized *precatórios*** (court-ordered Brazilian government debt),
**`MBCONS02`** (*consórcio* credit), **`IMOB01`** (real estate), **`MCO2`** (tokenized carbon),
`CBRL`/`BRLT`/`BRZ`/`BRZX` (BRL stablecoins), `WBX`. **`BRZ` carries 92.4M operations — the highest
op-count of any asset in Brazil** on R$38bn, i.e. a retail *payment rail*, not an investment. None of
these exist in the desk's universe or in any global vendor's crypto taxonomy.

#### ITEM 3 — **NOT DONE. Named, not disguised.** [§33: deferred(2026-08-04)]
The PT-BR practitioner ground (GitHub quant repos, forum reply-chains, untested alphas) was **not
touched**. I chose to spend its budget going one layer deeper on ITEM 2 once the vintage diff started
producing, per the L1.35 "go one layer past where you would stop" obligation — and that layer is where
the run's actual find was. **Recording this as an explicit deferral with a date rather than quietly
dropping it**, because §37's silent-carry defect starts exactly here. It is the first item next run.

### SESSION CLOSE 2026-08-01 session 1 (BR frontier miner) — DEPTH, BATTERY, §13, STANDING TEST, NEXT GROUND

**DEPTH LINE (per promising lead):**
| Lead | Depth reached | What depth surfaced that the surface did not |
|---|---|---|
| §13 robots sweep | **EXHAUSTED** (18 hosts × full-file grep over 17 AI-crawler tokens, 3 layers each) | The surface answer after KR/JP was "expect a block". Depth found **zero BR blocks** and one **global** stop (reddit), correcting OP-041's stated expectation from a global rollout to a **regional** one |
| RFB open data | **EXHAUSTED for a first pass** (5 sheets, 77 months, 4,206 rows, 3 vintages diffed, Wayback CDX, live-404 recovery, conservation-law validation) | Surface = "a monthly gov statistic". Depth = **42/42 months revised**, a **free point-in-time stack**, an **80× column-order trap**, and a **BR-only tokenized-RWA universe** |
| The `.xls` blocker | **EXHAUSTED** (format specs → working reader → self-caught sheet-collision bug → arithmetic validation) | "This box cannot read `.xls`" is **false**, and the dataset behind it is 576 KB of national flow data |
| Mercado Bitcoin API | **surface + boundary test** | Cloudflare-walled HTML **is not** a walled API (OP-038); and the tape is a **rolling window from ~2024-08**, not the deep 2013 history the venue's age implies |
| BR premium (era target) | **graveyard-checked BEFORE spending** | Killed the item before it cost anything — see below |

**Not breadth-theater:** 2 items closed to genuine exhaustion, 1 explicitly deferred with a date, and
every number above was read off an artifact fetched this run.

**THE HIGHEST-VALUE THING I DID WAS BEFORE I SEARCHED.** My own brief named *"USD-restriction-era P2P
premium mechanics"* as an era target. `graveyard.md:81` already records **`mercado_br` premium:
SCREEN-WEAK, same-day −0.27, Brazil rejected**, and the cross-era synthesis (5 instances) states the
law: *"do not hunt for a region whose barrier is low enough to arb — that region's premium is already
zero."* The family's lone survivor, kimchi, was itself **refuted** on 2026-07-30. Under **L1.16a** a
re-open needs a **named enabling change** addressing the original mechanism of death; Brazil's was
*low barrier height* (BRL freely convertible), and nothing has changed. **A whole first run was
available to be burned re-deriving a six-times-known null, and the graveyard check cost one grep.**
The defect is in the **seed list**, and it is logged as such rather than silently skipped.

**PROACTIVE BATTERY — moves run, and what each produced (a move that produced nothing says so):**
- **#9 SCOPE THE NEGATIVE RESULT** — twice, both decisive. "This box cannot read `.xls`" was a
  **library** failure read as a **capability** failure → OP-046. And a Wayback CDX query returning
  **0 rows** was a **504 gateway timeout**, not an empty archive (OP-044, verbatim) — I re-ran it and
  got 23 publication dates. Concluding "not archived" there would have killed the run's best find.
- **#3 CONFIG VS OUTCOME** — demanded the artifact everywhere: downloaded and parsed the `.xls`
  rather than citing the news summary (which said *"R$1–5bn/month"*; the file says **R$43.1bn**, ~10×
  stale); year-by-year probed the MB tape rather than assuming a 2013-founded venue serves 2013 data.
- **#2 ADJACENCY** — the vintage/look-ahead shape was immediately matched to the desk's **R0289**
  (`pct_circ_now` denominator) and to **R0239**'s point-in-time universe work, and filed as the same
  defect in a different coordinate rather than as a BR curiosity.
- **#10 RATCHET CHECK** — the MB rolling window means **its early data is being lost daily**; starting
  collection is cheap and starting late is irreversible (L1.46). Flagged in the watchlist.
- **#6 GENERALISE THE RULE** — three fleet operators (OP-046, OP-047, OP-035-BR) + an OP-041
  correction; nothing left as BR-local trivia.
- **#1 CONTINGENCY BEFORE FAILURE** — the vintage stack is **Wayback-dependent** and Wayback already
  404s on the live server for 2 of 4 files tried; the contingency is to mirror the vintages now, while
  they exist. Named in the watchlist.
- **#5 COST INVERSION** — **produced nothing this run.** No paid path was proposed or needed; every
  source found was free and keyless. Recorded, not skipped.
- **#8 NEGATIVE SPACE** — produced the next-ground list below (B3 and Pix fraud statistics, neither
  touched by any seat).

**§13 LEDGER FOR THIS RUN:** `reddit.com` **`Disallow: /` — HARD STOP, recorded and not routed
around** (three BR subreddits left unmined). `mercadobitcoin.com.br` + `advfn.com` **Cloudflare-walled
on HTML** — not circumvented; the venue's own **public API** was used instead, which is a different
door the venue itself opens, not a way around the closed one. RFB/BCB/B3/gov.br published under
Brazil's open-data law (**LAI 12.527/2011**) — **CLEAN**. No AI-crawler directive was overridden, and
no `User-agent: *` was self-granted against a block naming this family. Nothing accessed against a
stated refusal.

**STANDING TEST (L1.11a): does it carry information a competitor must pay to reconstruct?**
**RFB panel — YES, and unusually so.** It is *compelled* reporting (no minimum value for domestic
exchanges), it covers **P2P and foreign-exchange activity that no venue API can see**, and no vendor
sells it. **The vintage stack — YES, and more strongly than the panel itself**: vendors sell the
*revised* series; the point-in-time stack is free, is disappearing from the live server, and most
builders will not know it is needed. **Pix fraud statistics — YES, and untouched by anyone.**
**MB tape — NO** (an ordinary venue tape, and shallow at ~2024-08).

**DIASPORA — "where did they go?"** Partially answered, and the answer is **into compelled disclosure
rather than into another venue**. The RFB panel shows the migration in numbers: **P2P/no-exchange
volume (R$10.1bn/mo) now exceeds foreign-exchange volume (R$6.9bn/mo)**, while domestic exchanges hold
R$26.1bn. So BR flow did not flee offshore — it split between **domestic regulated venues** and a
large **peer-to-peer** layer, both now inside the reporting perimeter (and from 2026 DeCripto widens
it further to crypto-to-crypto, transfers and payments). The community-platform half of the question
is **unanswered** and belongs to ITEM 3.

**VENUE DISCOVERY (standing obligation — harvested from inside results, not from the seed list):**
| Venue | What lives there | How found | Verdict |
|---|---|---|---|
| `gov.br/receitafederal/.../criptoativos` | the national mandatory-reporting panel + its vintage stack | RFB regulation search | **RICH — the run's find** |
| `olinda.bcb.gov.br/.../Pix_DadosAbertos` | Pix open data incl. **`EstatisticasFraudesPix`** (fraud/contestation per month) | BCB API probe | **RICH, UNMINED** |
| `api.bcb.gov.br/dados/serie/bcdata.sgs.{n}` | keyless BR macro series (PTAX, Selic, …) | BCB API probe | **RICH** — the join target for the dollarization mechanism |
| `api.mercadobitcoin.net` | keyless BR venue tape behind a Cloudflare-walled site | OP-038 applied to a walled host | THIN (rolling ~2024-08) but real |
| `web.archive.org/.../<ts>id_/` | raw-replay of deleted government binaries | vintage recovery | **RICH — the route that makes OP-047 work** |
| `reddit.com` (r/investimentos, r/farialimabets, r/BrasilBitcoin) | BR retail trading talk | robots sweep | **WALLED — `Disallow: /`, §13 hard stop** |
| `b3.com.br` | BR exchange free historical series | robots sweep | **CLEAN, UNPROBED — next ground** |

**NEXT UN-EXHAUSTED GROUND, in order, for BR session 2:**
1. **ITEM 3, carried with a date (2026-08-04)** — PT-BR practitioner ground: BR GitHub quant repos to
   fork/issue depth, MQL5's Portuguese section (B3 algo traders, robots-clean), bastter/InfoMoney
   forum reply-chains ≥2. Hunting **untested alphas** (L1.34 #6) and engine ideas. **First, not later.**
2. **Mirror the RFB vintage stack before it decays** — 23+ dates known, 2 of 4 already live-404. This
   is the one item with a **decaying deadline**; everything else waits patiently.
3. **B3** — robots-clean and unprobed. Hunt the free historical series and, specifically, whether B3
   publishes **open interest / positions by investor type** (a real positioning axis that is paid
   almost everywhere else).
4. **BCB `EstatisticasFraudesPix`** — a monthly national payment-fraud series, keyless, that no
   crypto desk anywhere is looking at. Mechanism prior owed before any screen.
5. **Era-archaeology: NOT STARTED.** Mercado Bitcoin's early era and the 2017-mania BR boards remain
   untouched. Note the correction above: hunt them for **microstructure and workflow lore**, *not* for
   the premium, which is graveyarded.
6. **BR lexicon** — seeds `alavancado`, `laranja`, PT-isms are **UNVERIFIED**. Per **OP-037**,
   negative-control the supplied glossary before spending budget on it (the CN seat's supplied terms
   scored **0/7**). Do that before using any of them as search keys.

**Which artifact on disk is different because of what was mined?**
`docs/research/data_axis_watchlist.md` (**entry 29**, new), `docs/research/search_operator_library.md`
(**OP-046, OP-047, OP-035-BR extension** + an OP-041 regional correction),
`docs/research/improvement_inbox.md` (**+3 engine ideas**), `docs/research/recommendation_ledger.json`
(**R0316, R0317, R0318**), and this coverage doc (**the BR seat's first region row + first session
note**). No graveyard entry: the BR premium was already there, which was the point.

---


**§33 dispositions (2026-08-18, owed-work batch3 — items above, in order):**
- PT-BR practitioner ground to fork/issue depth: [§33: screened] — taken by BR s2 08-12 (zecontinha corpus)
- RFB vintage stack mirror: [§33: wired -> R0472 / commit 8f73b1f8] — recoverable vintages harvested 2026-08-18
- BCB EstatisticasFraudesPix: [§33: deferred(2026-08-25)] — carried untouched through s2/s3
- Era-archaeology (Mercado Bitcoin early era): [§33: deferred(2026-08-25)] — still not started at s3 close
- BR lexicon seeds (alavancado/laranja): [§33: screened] — s2 built the BR native lexicon table
### 2026-08-12 session 2 (BR frontier miner) — IN PROGRESS (write-first note; updated as items resolve)

**RESUMING, NOT RESTARTING.** Read before searching: `source_backlog_next.py` (16 pending
verification, 6 pending a legitimacy decision — **none BR**, so the backlog does not redirect this
seat), the BR region row, and my own s1 close. s1 left an explicit, dated carry:

> `#### ITEM 3 — NOT DONE. Named, not disguised. [§33: deferred(2026-08-04)]`
> *"It is the first item next run."*

**That deferral is 8 days PAST DUE** (dated 2026-08-04, today is 2026-08-12; no BR session ran in
between). Under the RESUME mandate — *"if a previous run died mid-work, finish ITS unfinished item
before opening new ones"* — ITEM 3 is item 1 of this run and nothing new opens ahead of it. The §33
gate reads BACKLOG-CLEAR, so the obligation is **schedule debt, not a carded-find block**: the gate
tracks carded finds, and a deferred *item* is invisible to it. That asymmetry is itself worth
naming — a dig item can rot for 8 days without any fence noticing, which is the §37 silent-carry
defect one level up from the one s1 guarded against.

**ITEMS TAKEN THIS RUN (bounded per the completion contract; depth per item unbounded):**

1. **ITEM 3, CARRIED AND OVERDUE — PT-BR practitioner ground, to fork/issue/reply depth.**
   BR GitHub quant repos, MQL5's Portuguese section (B3 algo traders; robots-clean per s1),
   PT-BR practitioner writeups. Hunting **untested alphas** (L1.34 #6) and **process** (the
   PROCESS MANDATE half s1 never reached). **Aimed deliberately at STATISTICAL-ARBITRAGE**, which
   `data/strategy_coverage.json` reports as the desk's **only NEVER-HUNTED family (n=0 of 14)** —
   and BR is the right ground for it: B3 retail culture has a large, old, native *long&short*
   (pairs) practice, so this is the one place where an unhunted family and my region's actual
   density coincide. L1.35: prefer an unhunted family over deepening a worked one.

2. **RFB VINTAGE STACK — the DECAYING-DEADLINE item, now 11 days older.** s1 measured 23+ Wayback
   publication dates and found **2 of 4 probed already live-404**. s1 flagged this as *"the one
   item with a decaying deadline; everything else waits patiently"* and then nobody came back for
   11 days. **Measure the decay first** (how many of the known dates are still live *today* vs
   2026-08-01) — that number is unrecoverable once it decays further, and it converts "we should
   mirror this" from an opinion into a dated rate.

3. **BR LEXICON NEGATIVE CONTROL (OP-037) — a prerequisite, not a deliverable.** My brief supplies
   `alavancado`, `laranja`, "HODLar PT-isms" as search keys; s1 recorded them **UNVERIFIED**. The
   CN seat's supplied glossary scored **0/7**. Negative-control them *before* item 1 spends query
   budget on them, because an unobserved term is not a search key and a zero-hit from a dead term
   is indistinguishable from a thin ground (OP-030).

**STANDING OPEN QUESTION (diaspora), unchanged and still unanswered:** where did the BR crypto
community go — 2017-mania boards → ? → local venues vs Binance BRL.

**VIDEO:** PT-BR YouTube fintwit/algo channels are in my brief and were untouched by s1. If a
mechanism is video-only I fetch it (`scripts/fetch_video_transcript.py`) and record the explicit
zero or the locked row; an empty `video_locked_log.md` is ambiguous and the zero is what
disambiguates it.

_Status: note written 2026-08-12 before any searching. Items resolve below._

#### ITEM 3 (lexicon control) — CLOSED FIRST, because it gates the other two. **1 of 3 supplied seeds survives, and none as a dark-forest key.** [§33: wired -> search_operator_library.md BR lexicon table]

Ran OP-037 on the three seeds my brief supplies. **No BR lexicon existed in the library before this
run** (`grep -c alavancado` = 0), so this also opens the region's dark-forest deliverable #2.

| seed | verdict |
|---|---|
| `alavancado` | **REAL BUT WORTHLESS AS A KEY.** Standard Portuguese for "leveraged" — ordinary financial vocabulary, zero discrimination. The CN `亏损/kuisun` case exactly: a real word is not automatically a search key |
| `laranja` | **REAL, BUT OUT OF SCOPE.** A genuine BR term (nominee/straw-man account) that indexes fraud and laundering material, not trading mechanism. §13 awareness only |
| `HODLar` | **UNOBSERVED.** Targeted search surfaced BR Bitcoin communities but no instance of the coinage. Morphologically plausible; **not a key until seen in live text** |

The replacements are worth far more than the seeds, and they were found by reading the ground
rather than by translating into it — see ITEM 1, which is where they came from.

#### ITEM 1 — CLOSED, AND IT IS THE RUN'S FIND. **The desk's only never-hunted family was being hidden by vocabulary.** [§33: wired -> search_operator_library.md OP-054/055/056 + docs/graveyard.md mcpt_return_permutation]

**THE MEASUREMENT, same corpus, same minute:**
- `pairs+trading+brasil` → **0 repos**
- `cointegracao` (the native PT key) → **30 repos**, essentially all genuine pairs-trading /
  statistical-arbitrage work, several crypto-native

**A seat that queried the English term and stopped would have graded BR statistical arbitrage a
DEAD GROUND on a clean zero.** That matters more than usual here: `data/strategy_coverage.json`
reports **STATISTICAL-ARBITRAGE as the desk's ONLY never-hunted family (0 of 14)** — so the one
family most in need of ground was the one being made invisible. Filed as **OP-054**.

And `long short` is unusable as a bare key in PT-BR because of **two independent collisions**,
either of which alone would empty the result set: **LSTM** (`Long Short-Term Memory` is written out
in full in PT ML repos — 3 of the top 5 hits on `long+short+acoes`) and **C type keywords**
(`MODIFICADORES-DE-TIPOS-DE-DADOS-Unsigned-Long-e-Short` — 2 of the top 5 on `"long e short"`).
This is the vocabulary-collision sibling of the RU seat's ticker-collision finding: same failure
mode, different layer.

**DEPTH — `mateusmartinelli/tcc` (crypto pairs trading; Gatev distance + Caldeira–Moura +
Rad–Low–Faff, ~1,384–1,464 lines each; no licence, so mined as TEXT only).** Read the code, not the
title. It is **more rigorous than the retail average** — it loads a T-bill series (`Rf.csv`) and
computes excess returns, which is the `beats_baselines` discipline this desk found *unwired in its
own gauntlet* — and it is **broken in three places, all in the config block**:
- `TRANSACTION_COST = 0.001  # 0.05% por trade` → 0.001 is **0.1%**, **2× the commented intent**
  (identical in all three files — copy-pasted, so the whole comparison shares it). Direction is
  conservative, so it does not inflate results.
- `Z_ENTRY_THRESHOLD = 1.5  # 2 standard deviations for entry (as per paper)` → the value is
  **1.5σ**, not the paper's 2σ. **Not conservative:** looser entry ⇒ more trades ⇒ interacts
  directly with the mis-stated cost.
- `LOOKBACKS = [90]  # 12 months formation period (252 trading days)` → **90 days, not 252.**
Generalised as **OP-055**: the comment is the author's INTENT, the value is what RAN, and the
write-up is generated from the intent. One grep prices the gap. **The two gaps that are not
comment-vs-value are larger still:** zero funding accounting anywhere (a market-neutral crypto
long/short is most cheaply expressed in perps, where funding routinely exceeds the edge — WS-006),
and top-10 pairs selected from ~100 tickers (≈4,950 candidates) at `ADF_PVALUE_THRESHOLD = 0.10`
with **no multiplicity correction** — ~495 expected false positives at that threshold.
Author chain followed: 2 repos total, 10 commits, no forks, no issues — **chain EXHAUSTED**.

**DEPTH — `pedhsm/systematic-research-framework`, and this one I killed.** Self-described as a
*validation* library implementing MCPT. Its `mcp/tester.py` permutes the **realised return series**
and scores `sharpe`/`cagr`/`vol` — **all three order-invariant**, so the permuted statistic *is* the
real one. Verified by independent reimplementation of the arithmetic (not by executing the repo —
supply-chain rule), 500 permutations × 4 synthetic series: **max−min spread = 1.1e-15**, machine
epsilon. **The failure is worse than uninformative:** FP summation is not associative, so
`perm >= real` resolves on rounding order and the p-value is a hash of FP dust — measured **p=0.978
for a strong winner and p=0.618 for a catastrophe**, i.e. the disaster outranked the winner. A
**wall, not a bar** (L1.49). → graveyard `mcpt_return_permutation`, operator **OP-056**.

**AND THE HONEST HALF: the desk is already ahead here, so this is NOT a repair.**
`libs/validation/bar_permutation.py` independently documents the identical trap, permutes **bars**
rather than returns, and handles the FP-dust ties this repo falls into via a measured
`_TIE_RTOL = 1e-4` plus the add-one correction `(sum(s >= real − tol) + 1)/(n + 1)`. Two
ecosystems, **no citation link either way**, same trap — one solved, one not. Per the provenance
rule that is genuine convergence and it buys a **queue place, not a lower bar**; here it buys
**confirmation of an existing desk design**. Disposition: **NO BUILD.** I checked before claiming a
defect, which is the only reason this note says "confirmed" instead of "found".

#### ITEM 2 — CLOSED. **The "decaying deadline" was never measured. Now it is a level, and its rate is explicitly UNMEASURED.** [§33: wired -> docs/research/data_axis_watchlist.md entry 29 update]

Full census of every known RFB publication date against the live server: **23 dates known, 12 live
(2023-05-03 … 2026-04-15), 12 dead (≤ 2023-03-02), of the dead 8 Wayback-recoverable and 4 with no
direct capture at all** (2021-09-02, 2022-07-05, 2023-02-06, 2023-03-02). The boundary is perfectly
clean, and the public page links **only** the current file — the other 11 are served but unlinked,
so the date list itself is the asset.

**Two hypotheses fit equally and imply OPPOSITE urgency:** (A) rolling keep-last-12 ⇒ every new
publication kills the oldest ⇒ mirror now; (B) a one-time 2023-04/05 gov.br CMS migration ⇒ the
live set is stable ⇒ no ongoing decay. **I could not discriminate them and did not pretend to:**
Wayback captured these files ~once each at publication, so no death can be dated from CDX. s1
recorded no date list, so no delta was computable — **the census above is the baseline that makes
the second measurement possible**, with the falsifier written down. Correcting s1's inferred *rate*
to a measured *level* is the actual deliverable.

**A bigger constraint surfaced incidentally:** the newest vintage is still **2026-04-15**,
unchanged since s1 probed it on 08-01 and **~4 months stale**, against a documented prior hiatus of
**13 months** (2023-09 → 2024-10). The publication lag is not fixed but **variable with a 13-month
precedent** — a far more serious limit on using this axis live than the archival decay is.

### SESSION CLOSE 2026-08-12 session 2 (BR frontier miner)

**DEPTH LINE (per promising lead):**
| Lead | Depth reached | What depth surfaced that the surface did not |
|---|---|---|
| PT-BR statarb ground | **corpus EXHAUSTED at repo-search level** (30 repos enumerated, ranked, crypto subset identified) | Surface = `pairs trading brasil` → **0**, i.e. "dead ground". Depth = **30 repos under the native key**, and the whole OP-054 finding |
| `mateusmartinelli/tcc` | **EXHAUSTED** (3 files read at config+method level, 10 commits, author profile → 2 repos, no forks/issues) | Surface = a tidy thesis title. Depth = **three code/comment contradictions**, no funding model, and ~495 expected false pairs from uncorrected multiplicity |
| `pedhsm/...framework` | **EXHAUSTED for its validation layer** (read `mcp/tester.py` in full, then numerically refuted) | Surface = "MCPT validation library". Depth = **the null cannot move its own statistic** — a wall, not a bar |
| RFB vintage stack | **EXHAUSTED as a census** (23 dates × 2 extensions probed live; CDX timelines attempted and found insufficient) | Surface = s1's "decaying deadline". Depth = **12/12 split, a clean boundary, two rival hypotheses, and no rate** |
| BR lexicon seeds | **EXHAUSTED** (3 seeds controlled; replacements harvested from live text) | Supplied seeds scored **0 usable dark-forest keys of 3**; the real keys came from reading the ground |

**NOT breadth-theater:** 3 items closed to genuine depth, one of them by **refuting** an artifact
numerically rather than describing it, and one by **correcting my own predecessor's unevidenced
urgency claim**. One negative result (lexicon seeds) and one no-build (the desk was already right)
are recorded as first-class outcomes.

**VIDEO: 0 fetched, 0 locked — and the zero is explicit because an empty log is ambiguous.**
PT-BR YouTube/algo channels are in my brief and I did **not** enter that ground this run; budget
went to the overdue ITEM 3 and the census. This is a **not-attempted**, NOT a block — nothing is
owed to `video_locked_log.md`, which records only routes tried and failed. It is named in the next
ground below so the omission cannot read as coverage.

**NEW VENUES / GROUND recorded for the next run:**
| venue | what lives there | how found | verdict |
|---|---|---|---|
| GitHub `cointegração` corpus (30 repos) | BR statarb/pairs implementations, several crypto-native | OP-054 native-key search | **RICH — the seat's primary open ground** |
| `Vido/zecontinha` (14★, 6 forks, active 2026-07) | PairTrading proof-of-concept, the corpus's most-starred + only real fork tree | corpus ranking | **UNMINED — fork depth owed** |
| `GustavoDMentz/JohanseneEngle-GrangerCode`, `moliveirasilv/Testes-de-Raiz-Unitaria---Crypto` | Johansen/Engle-Granger + VECM **on crypto** | corpus | **UNMINED, crypto-native ⇒ desk priority** |
| `Moreti2002/mcp-analytics`, `Novalt/Cointegration-Portfolio` | active 2026 statarb systems | corpus | **UNMINED** |
| `TCC` as a structural key | BR undergraduate thesis code — full replications, never OOS-validated | this run | **RICH SEAM, L1.34 #6** |

**NEXT UN-EXHAUSTED GROUND, in order, for BR session 3:**
1. **`Vido/zecontinha` fork tree (6 forks) + the crypto-native subset** of the `cointegração`
   corpus. Diverged forks first. This is the live ground for the desk's only unhunted family.
2. **`TCC` as a structural search key across BR quant topics** — thesis code is rigorous-looking,
   uniformly un-out-of-sampled, and unread by the English crowd.
3. **PT-BR video ground — explicitly owed, not attempted this run.**
4. **B3** — still robots-clean and **still unprobed** after two sessions (open interest / positions
   by investor type is the target: a real positioning axis, paid almost everywhere else).
5. **BCB `EstatisticasFraudesPix`** — carried from s1, untouched.
6. **Era-archaeology: STILL NOT STARTED** (Mercado Bitcoin early era, 2017-mania boards) — hunt
   microstructure/workflow lore, *not* the premium, which is graveyarded.

**Which artifact on disk is different because of what was mined?**
`docs/research/search_operator_library.md` (**OP-054, OP-055, OP-056** + the **BR native lexicon
table**, which did not exist), `docs/graveyard.md` (**`mcpt_return_permutation`**, a pre-emptive
kill), `docs/research/data_axis_watchlist.md` (**entry 29 census update** correcting s1's rate
claim), `docs/research/improvement_inbox.md`, `docs/research/recommendation_ledger.json`, and this
coverage doc.


**§33 dispositions (2026-08-18, owed-work batch3 — items above, in order):**
- Vido/zecontinha fork tree + cointegração subset: [§33: killed -> docs/graveyard.md zecontinha_eg_pairs_screen] — s3 OP-077 screen refuted; fork-tree remainder deferred(2026-08-25)
- TCC as structural search key: [§33: screened] — s3 corpus table (29/18, OP-081); remainder deferred(2026-08-25)
- PT-BR video ground: [§33: screened] — s3 attempted (25% fetch rate measured; dead-domain lie exposed)
- BCB EstatisticasFraudesPix: [§33: deferred(2026-08-25)]
- Era-archaeology: [§33: deferred(2026-08-25)]
### 2026-08-13 session 3 (BR frontier miner) — IN PROGRESS (write-first note; updated as items resolve)

**RESUMING, NOT RESTARTING.** Read before searching: `source_backlog_next.py` (6 pending
verification, 1 pending a legitimacy decision — **none BR**; the deferred queue holds exactly one
BR row, RFB, dated **2026-09-05**, so it is not workable this cycle and the backlog does not
redirect this seat), the BR region row, and my own s2 close, which left a **numbered, un-started
next-ground queue of 6**. Nothing is past due: s2 deferred no dated item. So this run takes the
top of its own queue in order.

**ITEMS TAKEN THIS RUN (bounded per the completion contract; depth per item unbounded):**

1. **`Vido/zecontinha` fork tree (6 forks, DIVERGED forks first) + the crypto-native subset of the
   `cointegração` corpus** — s2's queue item 1. Aimed at **STATISTICAL-ARBITRAGE**, which
   `data/strategy_coverage.json` still reports as the desk's **thinnest family (THIN, n=1 of 14)**
   after s2's `mcpt_return_permutation` kill moved it off zero. L1.35: prefer a thin family over
   deepening a worked one. Hunting **untested alphas** (L1.34 #6) and **process** alongside claims.

2. **`TCC` as a structural search key** — s2's queue item 2. BR undergraduate/masters thesis code:
   full replications, rigorous-looking, uniformly never out-of-sampled, and unread by the English
   crowd. This is a **structural** key (a document-type, not a topic), so it is the kind of key
   that transfers to every region with a named thesis genre — the operator-library half matters
   more than any single repo it returns.

3. **PT-BR video ground — explicitly owed by s2** ("named in the next ground so the omission cannot
   read as coverage"), and it now doubles as a **third-region control**: AR s2 wrote the first-ever
   rows into `video_locked_log.md` this same day and concluded the YouTube bot-wall is **not
   regional** (EN controls at 142k/50k/33k views walled identically to AR at 538k/47k/31k), leaving
   the boundary hypothesis *"blocked = all practitioner-scale video; passing = mega-viral only"*
   resting on **one** passing observation (`dQw4w9WgXcQ`, ~1.6bn views). A PT-BR probe is the cheap
   discriminator: a third language plus a different view-count band either sharpens that boundary
   or refutes it, and GAP #26 buys on this log.

**STANDING OPEN QUESTION (diaspora), carried unanswered from s1 and s2:** where did the BR crypto
community go — local venues → Binance BRL → ? Named checkpoints remain unvisited.

_(items resolve below as they close)_

#### ITEM 1 — CLOSED, AND IT IS THE RUN'S FIND. The fork tree is a null; the CODE is a measured refutation; the COMMENT LAYER is the prize. [§33: killed -> docs/graveyard.md `zecontinha_eg_pairs_screen`]

**THE FORK TREE — EXHAUSTED, AND IT IS AN HONEST NULL.** `forks_count: 6`, `/forks` returns **8**,
and **not one fork is ahead by a single commit** (2 identical, 1 behind 10, 3 behind 144). The two
extra entries — `yoshimorimori`, `igor110055` — are **HTTP 404 on both API and HTML**: tombstones of
deleted accounts still served in the fork list. So the queue item that sent me here ("6 forks, diverged
first") had **no diverged forks to find**, and "6 forks" was a popularity signal misread as a
development signal. The null is worth as much as a find here because it retires the ground: **nobody
needs to walk this fork tree again.** → **OP-078**, whose sharper half is that a tombstone 404 is
byte-identical to a rate-limit or a network failure to any walker that treats non-200 as "skip" — the
L1.60 denominator-attrition defect firing on a *mining* instrument (R0466's false null).

**THE CODE — THE SCREEN IS REFUTED BY MEASUREMENT, NOT BY OBJECTION.** `coint_model()` fits
`OLS(y ~ const + x)` and takes its p-value from `adfuller(resid)`. That is the textbook Engle–Granger
error — ADF critical values do not apply to residuals of an *estimated* cointegrating vector, because
OLS chose β to minimise the very variance the test examines — so I ran their exact window as a null
instead of asserting it. **4,000 trials, two independent random walks, n=120 (their broadcast window):
theirs rejects 17.97% [16.8, 19.2] against its own nominal 5%; `statsmodels.coint()` rejects 7.60%.
3.59× nominal, 2.37× the correct test.** The full published gate (ADF `p<0.05` **and** `|z|≥2`) fires on
0.88% of pure noise → **≈44 spurious pairs per run** on the 4,950-pair universe, at the broadcast
window alone, before counting the **10 lookback windows** (`range(60,260,20)` = 49,500 tests/run) that
carry no multiplicity correction anywhere in the codebase. The bot then publishes the **3 lowest-Hurst**
survivors — ranking the output of a noise filter by an R/S statistic at n=120. → **OP-077**, graveyard.

**THE COMMENT LAYER PAID BEST, EXACTLY AS THE DEPTH MANDATE PREDICTS.** Nothing on the surface — live
site, Telegram channel, ADF/Hurst/half-life panel — says what the maintainer says in PR #30:

> *"`select_pair(n)` was just a silly function to **draw a pair** … What ends up happening was **Telegram
> folks see it as recommendations. Which they are NOT!**"* — Vido, 2025-10-21

The selection step was `order_by('?')` — Django's **random ordering**. → **OP-080**. And because the
switch to a screened selection is **dated and attributable** (PR #30, merged 2025-11-06; message
template `v3`→`v4`), the channel's own public history contains **a random-pair baseline followed by a
screened one on the same universe, timestamped** — a free control arm for the question "does a
cointegration screen beat drawing a pair out of a hat", which is the question this family actually owes.

**THE FAMILY IS *NOT* KILLED, AND I CHECKED THE OBJECTION THAT WOULD HAVE KILLED IT.** The desk's
standing breadth lesson is *"1.54 independent bets RAW and 29 market-neutral … any **directional**
cross-sectional mechanism is hard-killed by narrow_breadth"*. A cointegration pair is long *y* /
short *βx* — **beta-neutral by construction**, so it lands on the **29** side. The argument that ends
every directional cross-sectional mechanism here **does not apply to this family**, and is closer to an
argument *for* it. That is the opposite of the conclusion I expected to write, and it is why
STATISTICAL-ARBITRAGE being the desk's thinnest family (THIN, n=1 of 14) looks like neglect rather than
a verdict. Routed to `improvement_inbox.md`; **no kill claimed.** *(Honest caveat:
`reports/cross_section_breadth.json` is gitignored and unreadable from this checkout, so 1.54/29 are
cited from the desk-lesson text, not re-verified.)*

**THE DATA FIND — A FREE POINT-IN-TIME UNIVERSE, WHICH ANSWERS A RECORDED DESK GAP.** The repo's
`BINANCE_FUTURES` list is hardcoded with a `# TODO` to automate it (PR #37, still open). That staleness
is the asset: **git history turns one hardcoded ticker list into a time series of dated universes**, and
the desk already recorded that *"`exchangeInfo` is a look-ahead in the UNIVERSE"* (free-data-miner
2026-08-12) — the live endpoint only ever returns today's set. Vintages 2020-06-28 (n=25) / 2023-03-07
(213) / 2023-12-05 (202) / 2025-11-14 (199) measured against live `fapi` exchangeInfo (865 symbols, 731
TRADING). **And the honest number is not the headline one:** 55 of 213 absent = 25.8%, but **40 are
BUSD-quote pairs killed by the BUSD wind-down** — a quote-currency retirement, not delistings — leaving
**15 of 173 USDT names = 8.7% true survivorship erasure**, of which **3 are rebrands with a continuing
series** (MATIC→POL, RNDR→RENDER both TRADING; TOMO→VIC SETTLING). **A rename and a delisting are
opposite events that look identical in a symbol-set diff.** → universe map source **103**.
*Self-correction recorded:* my first read of the current 100-symbol list was "frozen circa early 2021";
the history says the opposite — it was **213 in 2023 and the author cut it to 100** in Nov 2025.

**VENUE DISCOVERED BY READING REPO CODE (the mandated method):** **`@pythonfinancas`** ("Python e
Finanças", `message_thread_id=9973`) — a public PT-BR Telegram, and it is in this seat's brief's ground
list without any prior session having found it. Not carded as a data axis: its natural mechanism is
retail signal-following, and it earns no card without a mechanism that is not already dead.

**LEXICON / LANGUAGE — OP-079, and it refines the AR seat's OP-075 from the opposite direction.** The
maintainer states an **English-only policy for a Brazilian project** (*"not just the lusophones"*) —
in reply to a contributor asking, **in Portuguese**, which language to use. So the language boundary
does not run around the repo, **it runs through it**: code and PR titles in English, the reasoning in
Portuguese. The greppable residue is the identifiers the policy came too late to rename —
`gera_pares`, `calcula_modelo`, `PERIODOS_CALCULO`, `ativo_x`/`ativo_y` — plus PT code comments
(`# limpa o canvas`, `# TODO: descobrir qual é correto`). **Grep identifiers, not prose.**

**PROCESS MANDATE — what the maintainer said he could not do, which is the shopping list:**
`# TODO: This data does not require Binance Credentials` beside a `data.binance.vision` URL (he is
paying an API-key cost for data that is free and bulk-downloadable); the daily-kline call is
`get_historical_klines(..., KLINE_INTERVAL_1DAY, "1 year ago UTC")` under a comment reading *"fetch
**weekly** klines **since it listed**"* — **a third OP-055 proving instance** (config comment
contradicts config value) on a second repo, which is what promotes OP-055 from an anecdote about one
thesis to a property of this corpus. And PR #35, 2025-11-15: *"Last week I deployed the changes in
production… and lots of things broke"* — dates a data-quality discontinuity in the public feed, next to
a commit literally titled *"Workaround on Low Quality Data"* (2025-11-14).

#### ITEM 2 — CLOSED. The `TCC` key is REAL but NARROW, and it must never be ANDed with the native topical key. One repo taken to depth returned a **quantified** hidden-loser artifact. [§33: screened -> docs/research/search_operator_library.md OP-081]

**GRADING THE STRUCTURAL KEY (measured, one instrument, same minute):**

| query | repos | verdict |
|---|---|---|
| `TCC bitcoin` | **29** | the key works |
| `TCC trading` | **18** | works |
| `TCC criptomoedas` | **15** | works |
| `TCC quantitativo` | 3 | mostly false hits (orçamentação, RAIS payroll) |
| `TCC cointegração` | **1** | — against **30** for `cointegração` alone (s2) |
| `dissertação trading` | **0** | the formal graduate word is **dead** as a repo label |
| `"undergraduate thesis" trading` (EN control) | 8 | the EN genre word is weaker than the BR one |

**THE VERDICT, AND IT CORRECTS THE QUEUE ITEM THAT SENT ME HERE.** s2 predicted `TCC` was a "RICH
SEAM". It is a **precision key, not a recall key**: everything it returns really is thesis code, but
intersecting it with the native topical key collapsed a 30-repo corpus to **1**. Structural keys and
topical keys select on **different axes** — genre vs subject — so they must be **unioned, never
ANDed**. And `dissertação` → 0 while `TCC` → 29 shows that within one country only *one* of several
thesis words is actually used as a label: **test each genre word, never assume the formal one.** →
**OP-081**, which is fleet-portable (JP 卒論, KR 졸업논문, CN 毕业设计, RU дипломная работа).

**AND A COUNT-INFLATION CAVEAT I FOUND BY OPENING ONE:** `cadilhe/freqtrade_2020_tcc` is a **vendored
fork of freqtrade itself** — 428 blobs, of which the student's own contribution is a handful of files
under `user_data/`. The structural key's raw counts therefore **overstate** the corpus: a "TCC repo"
is frequently an upstream framework with a thin layer on top. Grade by the non-upstream path count,
not the repo count.

**THE DEPTH FIND — A HIDDEN-LOSER ARTIFACT, AND THE ARITHMETIC IS UNAMBIGUOUS.** The repo ships a real
backtest table (`user_data/backtest_results/`, Binance spot /BTC, 23 pairs, 5m):

| report | trades | win | loss | win rate | tot profit | cum profit |
|---|---|---|---|---|---|---|
| **BACKTESTING REPORT** (the headline) | 411 | 358 | 53 | **87.1%** | **+8.78%** | +131.65% |
| **LEFT OPEN TRADES** (a separate file) | 14 | **1** | **13** | 7.1% | **−2.91%** | −43.67% |
| **combined (true)** | 425 | 359 | 66 | 84.5% | **+5.87%** | +87.98% |

**The headline overstates total return by 49.6%** — positions still open when the backtest ended are
reported in a *different file* and are **13:1 losers**, with an average duration of 4d23h against 1d0h
for closed trades. This is the survivorship shape in miniature: the winners closed and got counted,
the losers stayed open and got filed elsewhere. **This arithmetic needs no assumption and no rerun**,
which is why it is the part I am asserting.

**THE MECHANISM IS A HYPOTHESIS AND I AM LABELLING IT AS ONE.** `Strategy001.py` sets
`sell_profit_only = True` (the sell signal fires **only** when the trade is in profit), with
`stoploss = -0.10`; every left-open loser sits between −0.20% and −6.44%, i.e. **above the stop and
below profit — structurally untouchable by either exit**. That explains the pattern exactly. But
`config.binance.json` sets `sell_profit_only: false`, and **config overrides strategy in freqtrade** —
while that same config declares `ticker_interval: "1h"` against a report filename of `..._5m2911`, so
the config in the repo is probably *not* the one that produced the table. **Which setting was live is
undeterminable from the repo**, so the mechanism stays a hypothesis with its falsifier named (rerun
with `sell_profit_only` both ways on the vendored data, which is *also* in the repo —
`user_data/data/binance/*.json`, 1m/5m/1h, so this is genuinely EXECUTABLE-tier). **This is the fourth
config-vs-declaration contradiction this seat has found in the BR corpus (OP-055).**

**COST ACCOUNTING (the BACKTEST MINER's required field):** neither config declares a `fee` key, so
fees came from freqtrade's framework default rather than from anything stated in the repo. That is
**not "no cost model"** — it is an **undeclared, inherited** one, which is a distinct and more
insidious state than absence: a reader cannot tell what was charged without knowing the framework
version's default. **Slippage, spread and impact are unmodelled** (limit orders assumed filled). These
are **spot /BTC pairs, so funding does not apply** — worth saying explicitly, because the desk's
standing WS-006 lesson is about perps and does not transfer here.

**NOT THE STUDENT'S STRATEGY, WHICH RAISES THE STAKES:** `Strategy001.py` carries
`author@: Gerald Lonlas, github@: freqtrade/freqtrade-strategies` — this is the **widely-copied
upstream example**. The artifact is therefore a property of a strategy thousands of freqtrade users
start from, not of one Brazilian undergraduate.

#### ITEM 3 — CLOSED. Video ground entered, **1 fetched / 3 locked**, and the fetch REFUTES a same-day sibling's boundary claim. [§33: screened -> docs/research/video_locked_log.md]

**VIDEO: 4 PT-BR practitioner videos probed, 1 fetched (4,645 chars), 3 locked.** Rows written to
`video_locked_log.md`, and the explicit count is stated here because an empty log is ambiguous between
"never hit" and "never tried" — s2 owed this ground and did not enter it.

**THE REFUTATION.** AR s2 wrote, hours earlier, that *"the blocked class is all practitioner-scale
video in every language; the passing class is mega-viral content only"* — on **one** passing
observation at ~1.6bn views. **`vaDLuXYDSJ8`, a PT-BR practitioner video at 13,297 views, fetched
cleanly with a `pt` subtitle track**, while AR videos at 538k/234k/47k and EN videos at 142k/50k/33k
failed. **View count does not order the outcome.** I then tested the endpoint's own explanation
(*"probably **temporarily** blocked"*): **3/3 persistent failures per video**, against two successes
from the same IP in the same minutes — so it is a **stable per-video property**, not a per-request
rate limit, and the error text misdescribes its own cause. The determinant is **UNMEASURED** from
outside (instance-side caching is my unconfirmed candidate). **Consequence for GAP #26:** the *ask*
(an authenticated route) survives, the *evidence* does not — measure the blocked **fraction** on a real
target list before buying, rather than asserting a blocked **class**. BR pass rate: **1 of 4 (25%), not 0.**

**R0592 IS STILL LIVE AND IT COST ME SIX MISLEADING RESULTS.** All six
`scripts/fetch_video_transcript.py` calls printed `Name or service not known` — the *last* instance in
its rotation is `api.piped.yt`, **a dead domain**, so a YouTube bot-wall renders as a local DNS fault.
Querying `api.piped.private.coffee/streams/<id>` directly gave the true status. Next seat: do that.

**WHAT THE ONE TRANSCRIPT ACTUALLY YIELDED** (PT-BR ASR, heavily garbled — tickers mangled, `Cielo`
→ *"se ela"* — so I extract only what survives repetition): he is on **B3 equities** (CIEL3 × BRML3),
not crypto, and his stated selection procedure is **(1) scan cointegration across windows "de 10 em
10"** — the same multi-window scan as `zecontinha`'s `range(60,260,20)` — **and (2) prefer the pair
whose `beta rotation` is most stable.** Sizing is the beta ratio (600 × 1,200 shares). It is also a
**course advertisement** (R$500 promotional lot, student spreadsheets, Instagram group), which changes
nothing about the mechanism and everything about the numbers: per the MINE-EVERYTHING mandate I take
the mechanism and the vocabulary and drop every claim.

**PROVENANCE — AND THIS IS THE PART THAT MATTERS MOST.** **SOURCE:** `vaDLuXYDSJ8`.
**DERIVES-FROM:** the BR retail *"Long&Short quantitativo"* teaching tradition — the same tradition
`zecontinha` sits in. So the agreement between a video course seller and a GitHub hobbyist on
*beta-rotation stability as the selection criterion* is **ONE ecosystem node, not two independent
ones**, and it elevates nothing (GAP #85). Recorded as convergence-within-ecosystem, explicitly not as
cross-ecosystem corroboration.

**THE ONE IDEA WORTH CARRYING OUT OF IT:** rank pairs by **rolling-hedge-ratio stability** rather than
by in-sample ADF p-value. It is cheap, it is orthogonal to the statistic OP-077 just showed is
mis-calibrated, and an unstable β is a direct argument that the relationship is not structural.
Routed to `improvement_inbox.md` as a hypothesis; **not screened this run, and not claimed as an edge.**

---

### SESSION CLOSE 2026-08-13 session 3 (BR frontier miner)

**DEPTH LINE (per promising lead):**
| Lead | Depth reached | What depth surfaced that the surface did not |
|---|---|---|
| `Vido/zecontinha` | **EXHAUSTED** — 8 files read at mechanism level, 47 issues/PRs enumerated, **5 comment threads mined**, fork tree walked to divergence, file history walked across a rename seam | Surface = "PairTrading proof of concept". Depth = a **measured 3.59× size inflation**, the maintainer admitting the signal was a **random draw**, and a **free PIT universe** in the git history |
| zecontinha **fork tree** | **EXHAUSTED — honest null** (8 listed, 6 live, 0 ahead) | Surface = "6 forks, diverged first". Depth = **no divergence exists**, plus 2 **tombstone 404s** that any walker would silently drop |
| `TCC` structural key | **EXHAUSTED as a grading exercise** (7 queries + EN control + 1 repo opened) | Surface = s2's predicted "RICH SEAM". Depth = **precision-not-recall**, `genre ∩ topic ≈ ∅`, and `dissertação` = a measured **0** |
| `cadilhe/freqtrade_2020_tcc` | **EXHAUSTED for its result layer** (backtest + left-open + strategy + config read) | Surface = "87.1% win rate, +8.78%". Depth = **+5.87% true**, a 49.6% overstatement sitting in a second file |
| PT-BR video ground | **OPENED** (4 probed, 1 mined, 3 logged) — not exhausted | Surface = "video is blocked". Depth = **a 13k-view video fetches fine**, refuting the same-day class boundary |

**NOT breadth-theater:** 3 items closed, two of them by **measurement that could have gone the other
way** (the Monte Carlo, the retry test), one by **refuting my own predecessor's prediction** (TCC),
one by **refuting a same-day sibling seat with a counterexample** (video), and one by **declining to
kill a family** when I checked the objection that would have killed it and found it did not apply.
Two honest nulls (fork tree, `dissertação`) recorded as first-class results. **Self-corrections
recorded in place: two** — my "universe frozen circa 2021" read (the history says it was *cut* in
2025) and my first-pass reading of `exclude(success | adf | hurst)` as an inverted filter (it is
correct De Morgan; I checked before writing it down).

**MECHANISM-VOCABULARY CHECK (L1.34):** this run's finds map to **NONE of the 24 CRYPTO_MECHANISMS** —
they are validation-methodology, universe-construction and access findings. Flagged explicitly as the
mandate requires: that is the *interesting* case, not the discardable one, and here it reflects that
the desk's thinnest family (STATISTICAL-ARBITRAGE) is thin for **instrument** reasons rather than
mechanism reasons.

**NEW VENUES / GROUND recorded for the next run:**
| venue | what lives there | how found | verdict |
|---|---|---|---|
| **`@pythonfinancas`** (Telegram, `message_thread_id=9973`) | live PT-BR pair-trade broadcast, **random draw pre-2025-11 → screened after** | reading `src/bin/bot.py` | **RICH as a research artifact** (a dated control arm); **no data card** — its mechanism is already dead |
| `zecontinha.com.br` | the live dashboard behind the repo | repo homepage field | **UNPROBED** |
| PT-BR `cointegração` video vein | 20+ practitioner videos, B3-focused | Piped `/search` on the native key | **RICH, 25% fetchable** |
| `TCC bitcoin` / `TCC trading` corpus (29 / 18) | BR thesis code, crypto subset | OP-081 | **UNMINED except one** |
| `berlinguyinca/` strategy collection (30 files, vendored) | a whole public freqtrade strategy library | inside the TCC repo | **UNMINED — and it is EXECUTABLE tier with vendored OHLCV beside it** |

**NEXT UN-EXHAUSTED GROUND, in order, for BR session 4:**
1. **The `berlinguyinca` strategy collection + the vendored `user_data/data/binance/*.json`** — 30
   strategies and the data to run them, in one repo. Apply **OP-082** to each: this is the cheapest
   EXECUTABLE-tier ground the seat has found.
2. **The crypto-native subset of the `cointegração` corpus** — `GustavoDMentz/JohanseneEngle-GrangerCode`,
   `moliveirasilv/Testes-de-Raiz-Unitaria---Crypto` (Johansen/VECM **on crypto**), `Novalt/Cointegration-Portfolio`.
   **Now with OP-077 in hand**, which makes each one a minutes-long check rather than a read.
3. **PT-BR video vein, continued** — 20+ candidates enumerated, 25% fetch rate measured.
4. **B3** — robots-clean, **still unprobed after three sessions** (positioning by investor type).
5. **BCB `EstatisticasFraudesPix`** — carried from s1, still untouched.
6. **Era-archaeology: STILL NOT STARTED** (Mercado Bitcoin early era, 2017-mania boards) — microstructure
   and workflow lore, *not* the premium, which is graveyarded.

**STANDING OPEN QUESTION (diaspora) — still unanswered after three sessions, and now named as a
deliberate carry rather than an omission:** where did the BR crypto community go? The one datum this
run adds is that a slice of it is on **Telegram**, being fed automated pair signals.

**Which artifact on disk is different because of what was mined?**
`docs/research/search_operator_library.md` (**OP-077 … OP-082**, + 5 new BR lexicon rows and a
measured correction to the `TCC` row), `docs/graveyard.md` (**`zecontinha_eg_pairs_screen`**, refuted
by Monte Carlo), `data/data_universe_map.json` (**source 103**, a free point-in-time universe),
`docs/research/video_locked_log.md` (**3 locked rows + a refutation of its own purchase argument**),
`docs/research/improvement_inbox.md`, and this coverage doc.

---

### 2026-08-19 session 4 (BR frontier miner) — IN PROGRESS (write-first note; updated as items resolve)

**RESUME STATE (mandate order followed):** `source_backlog_next.py --limit 6` reports 3 pending
verification — but all three (watchlist cards 23/25/26) are **R0636 phantom-pendings**: each already
carries a grade AND a §33 disposition in the watchlist itself (23 = SCREENED 2026-08-18 →
`data/carry_liq_screen.json` by litminer run 8; 25/26 = needs-monitoring, wired/screened). The
fail-open parser half is ledgered and scheduled(2026-08-26) by AR s3 the same day. **No real
verification is owed; re-verifying graded cards would be duplicate spend, not conversion.** The one
DECIDE item (Glassnode/CryptoQuant vendor-replacement) is a policy call above a miner's seat.

**ITEMS THIS RUN (bounded per completion contract):**
1. **`berlinguyinca` 30-strategy collection** vendored in `cadilhe/freqtrade_2020_tcc`
   (`user_data/strategies/`) **+ the vendored `user_data/data/binance/*.json` OHLCV beside it** —
   s3's named #1 ground, EXECUTABLE tier, NOT in the 08-25 deferral batch. Apply OP-082 (result
   layer vs headline) and OP-055 (config-vs-code contradiction) per strategy; this collection is the
   widely-copied freqtrade community baseline, so anything measured is a property of thousands of
   retail bots, not one student.
2. **Crypto-native `cointegração` subset** — `GustavoDMentz/JohanseneEngle-GrangerCode`,
   `moliveirasilv/Testes-de-Raiz-Unitaria---Crypto`, `Novalt/Cointegration-Portfolio` — pulled
   FORWARD from the 08-25 deferral: the deferral's stated reason was "no s4 evidence exists", and
   this run IS s4. OP-077 in hand makes each a minutes-long instrument check (p-value from
   `adfuller(OLS.resid)` — the measured 3.59×-anti-conservative EG error — vs proper
   `coint()`/Johansen).
3. **STRETCH only if 1–2 close:** era-archaeology first section (Mercado Bitcoin early era via
   Wayback) — owed 3 sessions, formally deferred to 08-25.

Standing obligations tracked this run: venue discovery beyond the seed list; explicit video count
(zero stated if ground untouched); lexicon additions; DEPTH line; next ground named at close.

---

## SESSION NOTES — AR frontier miner


**§33 dispositions (2026-08-18, owed-work batch3 — items above, in order):**
- Crypto-native cointegração subset (GustavoDMentz/moliveirasilv/Novalt, OP-077): [§33: deferred(2026-08-25)] — next BR session; no s4 evidence exists
- PT-BR video vein + B3 unprobed x3: [§33: deferred(2026-08-25)]
- BCB EstatisticasFraudesPix: [§33: deferred(2026-08-25)]
- Era-archaeology: [§33: deferred(2026-08-25)]
### 2026-08-12 session 1 (AR frontier miner, SEAT'S FIRST RUN) — IN PROGRESS (write-first note; updated as items resolve)

**No AR row existed in this document before this run** — `grep -ic arabic` over this whole file
returned **0**. The seat has never been run. Per the RESUME mandate I read the backlog
(`source_backlog_next.py`: 16 pending verification, 6 pending a legitimacy decision — **none AR**),
the region table above (**no AR entry**), and the four prior first-run seat notes (KR/JP/RU/BR s1)
for propagated operators. There is no prior AR session to resume from, so this run opens the ground.

**PRE-EMPTIVE GRAVEYARD CHECK — DONE BEFORE ANY SEARCHING, AND IT KILLED THE SEAT BRIEF'S ENTIRE
ERA TARGET.** My brief names *"LocalBitcoins MENA-era P2P premium discussions, pre-2021 P2P mechanics
under FX restrictions (Egypt/Lebanon premium episodes — CNY-premium analog provenance)"*. That is
`era_crossvenue_fiat_premium_arb` / the regional-premium class, and the desk has already buried it:

- `try_premium_timing` (**Turkey capital-control — the closest MENA-adjacent analog that exists**)
  REJECTED, verdict verbatim: *"best kimchi-analog tested and it FAILS … Kimchi is RARE, not a
  generic regional-premium pattern."*
- `bitbank_jp / mercado_br premiums` REJECTED with the class-level verdict: *"Regional-premium class
  is now **exhausted**: kimchi is the lone survivor across KR/JP/BR/TR/Coinbase tested."*
- `kimchi_premium` — that lone survivor — itself **KILLED 2026-08-01** (~73% timestamp artifact).
- `era_crossvenue_fiat_premium_arb` buried with **seven** era instances (MtGox↔BTC-e, CN×4, RU, EN).
- `data/strategy_coverage.json`: **CROSS-VENUE-PREMIUM = HUNTED, 9 distinct candidates**.
- And the cross-era synthesis states the rule that forecloses the *replacement* search too:
  *"do not hunt for a region whose barrier is low enough to arb — that region's premium is already
  zero"*, with **the barrier MIGRATES** as the family law.

Egypt/Lebanon P2P-under-FX-restriction is the SAME mechanism (barrier → premium), so it would be
instance #8 of a family killed seven times, inside a class declared exhausted, whose sole survivor
was itself refuted. **No L1.16a enabling change exists, so the SEED LIST is the defect, not the
ground** — this is the second seat in a row (BR 08-01 was the first) whose principal-supplied era
target was already dead on arrival. Routed as a recommendation, not silently skipped.

**THIS RUN'S 3 ITEMS** (bounded per the completion contract; depth per item unbounded):

1. **§13 ACCESS MAP for the AR ground** — UA-matrix probe of the content path per **OP-052**, not
   robots.txt alone. Mandatory-first for a first-run seat: without it every subsequent null is
   ambiguous between *blocked* and *empty* (**R0466** — a blocked ground and an exhausted ground are
   byte-identical to any fetch path that treats non-200 as no-content, a FALSE NULL that silently
   retires a region). KR/JP found by-name blocks; BR found none; **AR is unmapped in both directions.**
2. **Report + replace the dead era brief** (above) — route the seed-list defect, and name what the
   AR ground carries that the premium axis does not.
3. **THE REPLACEMENT AXIS — Hijri/Ramadan calendar + the Sharia-compliance constraint.**
   Novelty-clean on every instrument the desk owns: `ramadan/islamic/sharia/halal/hijri/lunar/eid/
   fatwa` all return **0 hits** across `graveyard.md`, `data_axis_watchlist.md`,
   `prospector_watchlist.md`, `data_universe_map.json` **and** the 4,384-chunk vault index. It is
   AR-language-native by construction (the certification/fatwa layer), it is the *interesting* case
   under the crypto-mechanism vocabulary rule (**it maps to NONE of the 24 CRYPTO_MECHANISMS**, so it
   widens the search space rather than re-searching it), and the lunar calendar drifts ~11 days/year
   against the Gregorian — **so it is orthogonal to every Gregorian calendar effect by construction**,
   which is exactly what the desk's own negative-space sweep flagged as never-asked.

---

#### ITEM 1 — §13 ACCESS MAP — **CLOSED. AR is the FOURTH region on the Cloudflare AI-crawler denylist.**

UA matrix per **OP-052** over 16 hosts (robots.txt sweep, then content-path probe — because robots is
necessary and not sufficient):

| host | what lives there | robots | verdict |
|---|---|---|---|
| **hawamer.com** (حوامير البورصة) | **the largest Gulf/Saudi retail trading forum** | 200, **names 3 AI agents** | **HARD STOP — `User-agent: ClaudeBot` / `Disallow: /` by name** |
| bitoasis.net | UAE exchange (GCC #1) | 200, names AI | **OPEN to us** — `*: Allow: /`; CCBot denied, ClaudeBot unnamed |
| arabsgate.com | ArabsGate forum | 200 clean | **OPEN** — content path 200 uniform across all 4 UAs |
| mql5.com (/ar) | **code-included algo community** | 301→clean (`/search`,`/data` only) | **OPEN** — `/ar/code` 404s **uniformly** (wrong path, NOT a block) |
| aaoifi.com | Islamic-finance standards body | 200 clean | OPEN (wp-admin/uploads only) |
| islamweb.net | fatwa centre (primary rulings) | 429 | **CAPTCHA-WALLED** on content — human-verification screen; **not routed around** |
| argaam / mubasher / coinmena / vara.ae / sca.gov.ae / cma.org.sa | Saudi+GCC data, exchanges, regulators | 301, no AI rules | open, unprobed at depth |
| arabictrader.com · rain.bh · adgm.com | AR broker / Bahrain exchange / ADGM | **403 on robots.txt itself** | edge-filtered before the policy layer — re-probe |

**THE FINDING: `hawamer.com` refuses this desk's agent BY NAME, inside a `# BEGIN Cloudflare Managed
content` block**, alongside Amazonbot / Applebot-Extended / Bytespider / CCBot / GPTBot /
Google-Extended / meta-externalagent, and carries an explicit EU DSM Article 4 rights reservation
plus `Content-Signal: ai-train=no`. This is a **legible, robots-STATED policy** — cleaner than the JP
case (note.com/zenn were clean-in-robots but 403 at the edge). **HARD STOP, archives included.**

**This is the fourth region to hit the same Cloudflare-managed rollout** — KR (DCInside), JP (5ch,
then note.com+zenn at the edge 08-12), CN (Gate, edge-403), now **AR (hawamer)**. BR remains the lone
region with **zero** blocks. So OP-041's "regional, not global" correction still holds, but the
denylist is now the **modal** posture for large consumer forums in every region except BR — the
pattern is **platform-class (big Cloudflare-fronted consumer forum), not geography**.

**Why this had to run first, and it earned its place immediately:** the single richest AR forum is
closed, so a seat that dug without the matrix would have found thin returns on the AR forum layer and
recorded **"the AR ground is thin"** — the exact **R0466 / WS-005** false null that silently retires
a region. The AR forum layer is not thin; its biggest node is **fenced**, and the open ground is
elsewhere (`arabsgate`, `mql5/ar`, GCC regulators, the exchange layer).

**NEW VENUE CLASS, recorded for the fleet:** `bitoasis.net` publishes an **allowlist** —
`OAI-SearchBot`, `ChatGPT-User`, `PerplexityBot`, `Perplexity-User` explicitly `Allow: /` while
`CCBot` is denied. Venues are starting to discriminate **between** AI agents rather than blanket-deny.
`ClaudeBot` is unnamed there and so falls to `*: Allow: /` — permitted, but the fleet should expect
per-agent policy to become normal and re-probe rather than carry a binary open/closed prior.

---

#### ITEM 2 — THE DEAD ERA BRIEF — **CLOSED (killed above, before any searching).**

Recorded as the headline: **second consecutive seat handed an era target the desk had already
buried.** BR (08-01) = `mercado_br`; AR (08-12) = the whole regional-premium class. Routed to
`improvement_inbox.md` as a **seed-list defect**: seat briefs are written from region stereotypes
("this region has capital controls → hunt its premium") and are **not graveyard-checked before
dispatch**, so a seat burns its own first item discovering the desk already knows. The fix is cheap
and is named in the inbox.

---

#### ITEM 3 — HIJRI/RAMADAN + SHARIA — **CLOSED. Honest null, and I was WRONG on my own novelty claim.**

**SELF-CORRECTION FIRST (it changes the verdict, so it leads).** I opened this item calling the axis
"novelty-clean at 0 hits". That was true **of this desk** and **false of the literature**: the axis is
**published** — *"Ramadan effect in the cryptocurrency markets"*, Review of Behavioral Finance
14(4):508 (2022), DOI `10.1108/rbf-09-2021-0173` — finding a Ramadan return effect on ETH/XRP/XLM/BNB
(BTC only under AR(1)), no volatility effect, none for LTC. **0 desk hits meant the desk had never
looked, NOT that nobody had.** An empty internal index is evidence about the index (the BM25 caveat
in CLAUDE.md, applied to my own claim).

**PROVENANCE (mandatory field, and it matters here).**
**SOURCE:** Emerald RBF 14(4):508, 2022. **DERIVES-FROM:** Białkowski, Etebari & Wiśniewski (2012,
*JBF*) "Piety and Profits" — the equity Ramadan anomaly (11 of 14 Muslim countries), which the crypto
paper explicitly extends ("previously documented for traditional assets… not yet analysed in
cryptocurrency markets"). **This is an ECHO of one equity literature, not an independent discovery**,
so it elevates NOTHING under the convergence rule (GAP #85: counting readings of the world, not
events in it).

**THE COST FINDING (BACKTEST-MINER duty):** the paper accounts for **no** transaction costs, fees,
funding, slippage or spread, and **tests no strategy** — it reports the significance of a calendar
**dummy**. Per WS-006 that is not a weaker version of this desk's quantity, it is a **different
quantity**. Absence of cost accounting is itself the finding.

**THE MECHANISM I ACTUALLY WANTED TO TEST, which is not the paper's.** The doctrinal layer is a
**hard participant-exclusion**, not a sentiment story: Sharia rulings consistently prohibit
derivatives, deferred settlement and margin (*gharar*, *maysir*, *riba*) — the fatwa consensus
formula is **«مع التقابض الفوري وتحريم التداول الآجل والمشتقات»** ("with immediate possession, and the
prohibition of deferred trading and derivatives"), and practitioner guidance is explicitly *"avoid
perpetual futures and stick to the spot market using swap-free accounts"*. So a doctrinally
constrained pool is **spot-only by construction**. **I had to correct my own first version of this:**
that pool does not *switch* from perp to spot during Ramadan (it never used perps), so the channel
must be a change in that pool's **activity level** — and the sharpest version is **zakat**, a
**mandatory** 2.5% annual wealth levy that most contemporary rulings apply to crypto and that is
commonly discharged in Ramadan. That is a genuine forced-flow ("who is forced to trade against this
and cannot stop?" — an obligation-bearer at a calendar-predictable date), and it is **spot-side**,
which lands it in **funding/basis** — the desk's only repeat-survivor family — rather than in
direction, where the desk has 129/129 failures on record.

**THE DESK TEST — `data/ar_ramadan_power_check.json`** (BTCUSDT D1, 2019-09-09→2026-08-12, 2,530 days,
**208 Ramadan-days across 7 episodes**; windows are moon-sighted so ±1d by jurisdiction — itself a
tradability caveat, since the exact start is not deterministic ex ante):

| channel | naive daily t | episode-level t | ICC | design effect | observed vs MDE |
|---|---|---|---|---|---|
| return | −0.561 | **−0.948** | 0.000 | 1.00 | −0.142 %/day vs MDE 0.493 → **0.29×** |
| funding | +1.314 | **+0.691** | **0.525** | **16.07** | +0.627 bps/8h vs MDE 2.982 → **0.21×** |
| basis | +1.165 | **+0.574** | **0.695** | **20.96** | +0.696 bps vs MDE 3.989 → **0.17×** |

**VERDICT: `unmeasurable_by_construction`, NOT refuted** (the `unlock_events` precedent). Every
channel is null, and the sign on returns is **negative** — opposite to the published claim — but the
honest reading is that **n=7 events cannot detect anything real**: the 80%-power MDE is 3–6× the
observed effect, i.e. returns would need **+0.49%/day (≈500%/yr)** to clear. And this does not improve
with patience — **MDE scales 1/√n, so halving it needs 28 episodes = 21 more years.** An annual event
is **permanently underpowered as an annual event study**. L1.25 applies in full: this is not evidence
that no effect exists, and I have deliberately not dressed it as one (the BR precedent).

**THE TRANSFERABLE FINDING, and it is worth more than the axis — plus a refutation of my own
critique.** I expected to show the published result was a clustering artifact (gap-register row 85:
*"any n gating a statistical claim must count EVENTS IN THE WORLD, never READINGS OF THE WORLD"*).
**On returns that critique is REFUTED: ICC = 0.000**, so a daily dummy on returns is roughly honest
and the paper's method is not broken in the way I predicted. **But on the persistent series it is
severe** — funding ICC 0.525 and basis ICC 0.695 give design effects of **16 and 21**, inflating a
naive daily-dummy t by **≈4.0× and ≈4.6×**. So the rule is not about Ramadan at all:

> **Any calendar/event test on a PERSISTENT series (funding, basis, OI, spread) must cluster at the
> event level; a daily dummy inflates t by ~4× on this desk's own data. On returns (ICC≈0) it does
> not.** The error is invisible because it depends on the *series*, not the *test*.

Routed to `improvement_inbox.md` — it binds the desk's whole EVENT-AND-CALENDAR family, where funding
and basis are exactly the targets a direction-agnostic desk should prefer.

**Video: 0 fetched, 0 locked** — no video ground was reached this run (the AR YouTube layer is named
in my brief and is **explicitly carried to the next run**, unstarted). Recording the zero so the empty
`video_locked_log.md` stays unambiguous between "never hit" and "never tried": **never tried, this run.**

---

#### NEXT UN-EXHAUSTED GROUND (the chain that makes exhaustion achievable across runs)

1. **`mql5.com/ar`** — the code-included AR algo layer, confirmed OPEN, correct path not yet found
   (`/ar/code` is a uniform 404). **EXECUTABLE-tier ground, highest priority**: code + params = cheapest
   to refute.
2. **AR YouTube / video** — named in the brief, untouched; `fetch_video_transcript.py` unexercised on
   AR content, so the platform's AR posture is **unmeasured**, not open or closed.
3. **`arabsgate.com` forum** — confirmed OPEN, zero threads mined; reply-chain depth unstarted.
4. **GCC regulator + exchange layer** (VARA, ADGM, SCA, CMA, bitoasis, CoinMENA) — the BR seat's win
   came from a *government* dataset, not a community; this is the AR analogue and is unmined.
5. **`arabictrader.com` / `rain.bh` / `adgm.com`** — robots.txt itself 403s; re-probe with a neutral UA
   to read the policy (reading policy is not routing around access control; fetching bodies would be).
6. **Era-archaeology: UNSTARTED.** With the premium target dead, the AR era ground needs a different
   question — the dead-venue layer (defunct GCC/Levant exchanges) rather than the P2P-premium layer.

---


**§33 dispositions (2026-08-18, owed-work batch3 — items above, in order):**
- §13 access map (OP-052 UA-matrix): [§33: screened] — in-block access map (the result trio)
- Dead era brief replaced: [§33: screened] — in-session
- Hijri/Ramadan + Sharia axis: [§33: killed -> docs/graveyard.md hijri_ramadan_calendar_axis] — unmeasurable_by_construction 2026-08-12, NOT refuted
- mql5.com/ar path: [§33: killed] — s2 re-measured 404 at locale root; ground may not exist
- AR video posture: [§33: screened] — s2 exercised it; video_locked_log.md 2026-08-13 rows
- arabsgate.com threads: [§33: deferred(2026-08-25)] — still zero mined after s2
- GCC regulator + exchange layer: [§33: screened] — s2 artifacts (its item 3 carries the tag)
- arabictrader/rain.bh/adgm robots-403 re-probe: [§33: deferred(2026-08-25)] — re-carried as UNMEASURED (OP-076)
- Era-archaeology (dead-venue layer): [§33: deferred(2026-08-25)]
### 2026-08-13 session 2 (AR frontier miner) — **CLOSED.** All 3 items resolved to depth; deliverables committed.

**RESUMED, NOT RESTARTED.** Read first: (a) `source_backlog_next.py` — 6 pending verification,
**none AR**, and all 6 are actively owned elsewhere (BRAIN hunter s1/s2 took the grouping map,
COT-BTC and stablecoin legs on 08-11/08-12; KR venue-state is the KR seat's). Re-verifying another
seat's live item would be duplicated labour, not backlog burn-down, so this run resumes at my own
chain. (b) My **s1 note (08-12)** and its named next-ground list. (c) §33 gate: BACKLOG-CLEAR,
18/18 disposed, mining authorised.

**ITEMS THIS RUN** (bounded per the completion contract; depth per item unbounded):

1. **`mql5.com/ar` — RESOLVE THE GROUND, and re-measure my own s1 premise.** s1 graded it
   *"OPEN, correct path not yet found (`/ar/code` is a uniform 404)"*. First probe this run:
   `https://www.mql5.com/ar` **404s at the ROOT** with a browser UA. A 404 at the locale root is not
   a wrong sub-path — it is evidence the **AR locale may not exist at all**, which would make my #1
   priority ground a ground that was never there. **OP-054 discipline applied to myself**: verify the
   key against the ground before grading it. If there is no AR locale, the real question replaces it:
   *where does the AR-language algo-code layer actually live?*
2. **AR VIDEO — the route this seat has NEVER TRIED.** s1 recorded an honest `video: 0 fetched,
   0 locked — never tried`. The fleet-wide `video_locked_log.md` still has **zero rows** after weeks
   of digs across seven regions, which the mandate names as either implausible or a silent skip. AR
   video posture is **UNMEASURED**, not open and not closed. Exercise
   `scripts/fetch_video_transcript.py` on real AR trading content and record the result **either way**.
3. **GCC REGULATOR + EXCHANGE DATA LAYER — the BR-analogue.** The BR seat's actual win was a
   *government dataset*, not a community mechanism; s1 named this as the AR analogue and it is
   unmined. Hunt **DATA AXES** (what does each venue/regulator publish, what does its API expose),
   not strategies — a dig returning zero strategies and one new data axis is a good dig.

STATUS: opened 2026-08-13. Updated in place as each item resolves.

---

#### ITEM 1 — **CLOSED, and it OVERTURNS my own s1 grade AND re-aims the seat.**

**(a) `mql5.com/ar` DOES NOT EXIST.** s1 recorded *"OPEN, correct path not yet found (`/ar/code` is a
uniform 404)"* and put it at **#1 priority** for this run. That was wrong, and the control is clean:
MQL5 publishes **11 hreflang locales** (`en ru zh es pt de ja ko fr it tr`) and **`ar` is not among
them**; `/{loc}/code` returns **200 for 11/11 real locales and 404 for `ar` alone**. It was never a
wrong sub-path — **there is no Arabic MQL5**. A seat inheriting my s1 line would have spent this run
hunting for the "correct path" to a ground that was never there. *(Lesson: s1 graded a ground OPEN
from its **robots.txt** — but robots.txt answers "may I?", never "is there anything here?". OP-052
told me to probe the content path and I probed the **policy** path. → OP-074 below.)*

**(b) SO WHERE IS THE AR ALGO-CODE LAYER? — MEASURED, NOT ASSUMED.** Replaced the dead ground with
the brief's own "AR-language GitHub topics". Native-key search (OP-054 — verify the key against the
ground before grading THIN), honest UA, GitHub search API:

| AR term | gloss | repos | max ★ |
|---|---|---|---|
| `المراجحة` / `مراجحة` / `أربيتراج` | arbitrage (3 variants) | **1 / 0 / 0** | 0 |
| `التداول الكمي` | quantitative trading | **0** | — |
| `اكسبيرت` | expert advisor (MT4/5 EA) | **0** | — |
| `تداول آلي` | automated trading | 11 | 0 |
| `تحليل فني` | technical analysis | 12 | 0 |
| `عملات رقمية` | cryptocurrencies | 27 | 1 |
| `بينانس` | Binance (AR script) | **1** | 0 |

The single `المراجحة` hit is an **AI car-pricing engine in Egypt**, not markets. **Every** hit across
all seven terms has **0 or 1 stars**; the population is Telegram signal-bots, *"نسبة نجاح 95٪"*
(95% success rate), *"أرباح مضمونة"* (guaranteed profits). **Zero backtests, zero cost accounting,
zero out-of-sample anything.**

**(c) THE CALIBRATED DENOMINATOR — because "1 repo" means nothing without one** (L1.62: a denominator
that was assumed is not a measurement). Same term, same instrument, four scripts:

| script | arbitrage term | repos | max ★ |
|---|---|---|---|
| **CN** | `套利` | **1,174** | 671 |
| **RU** | `арбитраж` | 24 | 12 |
| **KR** | `차익거래` | 6 | 2 |
| **AR** | `المراجحة` | **1** | 0 |

**(d) TWO HYPOTHESES SURVIVED (c), AND THEY DEMAND OPPOSITE CONCLUSIONS — so I ran the
discriminator instead of picking one.** **H1**: the AR algo-trading developer population does not
exist. **H2**: it exists and writes in **English** (the OP-054 trap at full strength — a correct
native key returning a true zero because the *practitioners* left the language, not the field).
GitHub **users** search, self-reported location + "trading", with a KR control on the same instrument:

| location | users | | location | users |
|---|---|---|---|---|
| **UAE** | **67** | | **Korea (control)** | **59** |
| Egypt | 24 | | Egypt + "quant" | 7 |
| Saudi Arabia | 8 | | Saudi + "quant" | 1 |

**H1 IS REFUTED. H2 IS CONFIRMED.** AR-region developers who mention trading number **≈99 across
three countries — UAE alone (67) EXCEEDS the Korean control (59)** — while the AR-*language* corpus
sits at 0–1. *(Instrument caveat, stated because it cuts both ways: `location:` is self-reported and
sparse, and I queried `UAE` not `United Arab Emirates`, `Korea` not `South Korea` — so **both sides
are undercounted by the same mechanism**. The comparison is a lower bound on each, and AR already
≥ the control, so the direction is robust even though the levels are not.)*

**THE FINDING, AND IT RE-AIMS THIS SEAT** — routed to the operator library as **OP-075**:

> **For CN/KR/JP/RU/PT the language IS the moat: the corpus exists natively and the crowd cannot read
> it. FOR AR IT IS NOT.** The AR technical layer is written **in English by the same developers**, so
> (i) an AR-script search is not a window into a hidden technical corpus — it is a window into the
> **retail/promotional** layer, which is exactly and only what it returned; and (ii) whatever those
> ~99 developers do produce **is already inside the EN seat's ground**. There is **no language
> arbitrage in AR code**, and no amount of further AR-script GitHub digging will create one.

**WHAT THIS DOES NOT SAY (L1.25, and it is the load-bearing half):** this is **not** "the AR ground is
thin" — that is the exact R0466/WS-005 false null s1 built the §13 access map to prevent. It is a
**precise statement about ONE layer**: AR-script *code*. It says the seat's edge cannot be in code or
in language-as-such, and must instead be in what is **Arabic-only by INSTITUTIONAL construction** and
therefore cannot migrate to English — regulator publications, exchange notices, the Sharia/fatwa
layer, GCC government data. **That is item 3, and this measurement promotes it from third to first.**

---

#### ITEM 2 — VIDEO — **CLOSED. The log has its FIRST ROWS EVER, and they say DO NOT buy a regional proxy.**

**video: 8 attempted, 1 fetched, 7 LOCKED.** Full table, controls and the GAP #26 consequence written
to `docs/research/video_locked_log.md` (previously **zero rows** since creation).

**(a) THE AR VIDEO GROUND IS RICH — richer than the AR text ground, which inverts my item-1 finding
in a useful way.** Piped search served AR queries perfectly: `المراجحة`/`أربيتراج` return full pages of
AR-native arbitrage walkthroughs (`Alcrybto` 31k views, `Dr Crypto` 538k, `كريبتو بالعربي` 47k). **The AR
corpus is VIDEO-FIRST.** That is the natural complement to OP-075: the AR technical layer is not
absent from the world, it is absent from *text* — the practitioners talk instead of writing.

**(b) AND IT IS UNREADABLE.** `api.piped.private.coffee` is genuinely UP — its `/search` endpoint
answered these very queries — but `/streams/<id>` returns **HTTP 500** carrying
`SignInConfirmNotBotException … LOGIN_REQUIRED: "Sign in to confirm that you're not a bot"`.

**(c) THE CONTROL IS THE DELIVERABLE, AND IT CORRECTS A SAME-DAY SIBLING.** RU miner s3 (2026-08-13)
recorded video access *"works on popular English content and fails on cold non-English"*. I ran the
discriminating control — **EN crypto videos in the same view range**:

| video | lang | views | result | | video | lang | views | result |
|---|---|---|---|---|---|---|---|---|
| dQw4w9WgXcQ | EN | ~1.6bn | **OK (6 tracks)** | | IpN5Oof6Kbc | **EN** | 142,551 | BOT-WALL |
| AoGDmyI2eAY | AR | 538,494 | BOT-WALL | | OEuI_stZKUc | **EN** | 50,775 | BOT-WALL |
| _MSNqMjT9ng | AR | 234,541 | BOT-WALL | | fYncVOgQolg | **EN** | 33,421 | BOT-WALL |
| SAZeeuxuo1k | AR | 47,625 | BOT-WALL | | O0gZL-wrH2k | AR | 31,217 | BOT-WALL |

**The English half of the sibling claim is REFUTED: language is ORTHOGONAL.** EN at 142k/50k/33k walls
identically to AR at 538k/47k/31k; the only pass is a ~1.6bn-view control. **Had I logged only my AR
rows, this log would have argued for an AR/regional unlock — the wrong purchase, on the one artifact
whose entire job is to decide what to buy.** The boundary sits between 538k and 1.6bn views and the
**mechanism is UNIDENTIFIED** (popularity? cache residency? age?) — stated as unidentified rather than
guessed. GAP #26 should therefore price a **general authenticated/residential YouTube route**; the EN
seat is affected exactly as much as every regional seat.

**(d) WHY THE LOG SAT EMPTY FOR WEEKS — AN INSTRUMENT FAULT, NOT DIGGER LAZINESS.** The mandate reads
the empty log as seats silently skipping the duty. Measured cause: `fetch_video_transcript.py` loops 4
instances overwriting one `last = <error>` and raises only that. The four fail for **four different
reasons** — private.coffee **500** (bot-wall), kavin.rocks **502** (down), adminforge.de **301** (API
moved), api.piped.yt **000** (**dead domain, NXDOMAIN**) — and since the dead domain is **last in the
tuple**, every failure of any cause surfaces as `Name or service not known`. **A platform bot-wall is
displayed as a local DNS fault**, so every digger who hit it saw a problem with their own box and
correctly declined to log a platform block. Routed to `improvement_inbox.md` (seat is frozen out of
`scripts/`); the RU s3 "fetcher is ALIVE" verdict stands — the rotation *does* work, on content the
wall spares.

**video: 8 fetched-attempts, 1 succeeded, 7 LOCKED** (explicit zero-or-count per the mandate, so the
log stays unambiguous between "never hit" and "never tried": **hit, hard, and logged**).

---

#### DEPTH LINE (per the depth mandate — depth per lead, and what depth surfaced that the surface did not)

| lead | depth reached | what the SURFACE said | what DEPTH said |
|---|---|---|---|
| `mql5.com/ar` | **EXHAUSTED** (locale enumeration + 12-locale sibling control) | s1: "OPEN, correct path not yet found" | **the locale does not exist**; 11/11 siblings 200, `ar` alone 404 |
| AR GitHub code layer | **EXHAUSTED at term level** (7 native keys × 3 arbitrage variants, + 4-script control, + location discriminator) | "260 repos for `تداول` — looks like a ground" | 0–1★ signal-bots only; **arbitrage 1, quant-trading 0, EA 0**; the practitioners exist and write in English |
| AR video corpus | **comments/reply layer NOT reached — blocked at transcript** | rich, mechanism-bearing, AR-native | **7/8 bot-walled**; and the EN control proved the wall is not regional |
| Piped instance rotation | **EXHAUSTED** (all 4 probed individually, exact codes) | "all Piped instances failed — DNS error" | **4 instances, 4 distinct causes**; the reported one was the dead domain's |
| `aaoifi.com` | **document-path resolved** (robots → content path → real PDF URL) | robots 200, allows `*`, no by-name refusal ⇒ **OPEN** | **the entire document corpus sits under the one Disallowed path** |

**HONEST SELF-ASSESSMENT AGAINST THE BREADTH-THEATER TEST:** this run mined **zero reply chains and
zero forum threads** — the `arabsgate.com` thread layer (s1's ground #3) is still unstarted, and the AR
video comment layer was unreachable because the transcript was. What it did instead was **kill two
grounds with controls and re-aim the seat**, which is the higher-value trade on this particular run
*only because* the item-1 measurement invalidates the layer those threads sit in. **That excuse does
not extend to `arabsgate`**, which is a forum in the retail layer OP-075 predicts is thin — and
**a prediction is not a measurement**, so it stays on the list to be tested rather than assumed.

**PROVENANCE (mandatory).** **SOURCE:** all findings are first-hand measurements taken this run
(GitHub search API, MQL5 hreflang, Piped `/streams`, `aaoifi.com` robots + content path), not readings
of anyone's writeup. **DERIVES-FROM: NONE (checked)** for OP-074/OP-075 — no paper, post or thread was
consulted or reacted to; they come from probing the desk's own grounds. The one input from outside my
own run is **RU miner s3's same-day video claim**, which I **contradict by control** rather than extend
— recorded explicitly so `convergence.py` never books these two seats as independent agreement (GAP #85).

**CRYPTO-MECHANISM VOCABULARY CHECK (mandated flag):** this run produced **no tradeable mechanism card**,
so it maps to none of the 24 CRYPTO_MECHANISMS — correctly, not by omission. Its output is **access,
instrument and seat-aiming**, which is the honest result when the measurement says the ground you were
pointed at cannot hold an edge. **No card was invented to fill the slot**, and no source was added to
`data_axis_watchlist.md`: the AR video corpus is real but currently **unreachable**, and carding an
unverifiable source while the desk's measured bottleneck is verification is the breadth-theater the
brief names as a defect. It is logged to `research_memory` as `pending` and to `video_locked_log.md`
instead — routed, not catalogued.

---

#### ITEM 3 — GCC REGULATOR + EXCHANGE LAYER — **CLOSED. One card, against a documented unmet need.**

Item 1's measurement promoted this from third to first: OP-075 says the AR seat's edge must be in what
is Arabic-native **by institutional construction**. 10 hosts enumerated, honest UA, exact codes; every
claim below that I record was **re-verified by me first-hand** rather than taken on report.

**THE FIND — `VARA` (Dubai), carded as `data_axis_watchlist.md` #33 `[§33: deferred(2026-08-24) tier:3]`.**
It is carded **only because it serves a named, failed need**: card 24 (Auer–Claessens regulatory-event
timeline) is graded *"the timeline dataset is the owed build"* and records a **targeted search for a
published event list that FAILED**, with the reconstruction scheduled as **R0193, due 2026-08-24**.
Verified: `robots.txt` 200 with **zero non-comment directive lines** (§13 clean, no agent named);
public register **200 with 51 `VL/YY/MM/NNN` refs** whose ref *encodes year/month*; **unlicensed-VASP
blacklist 200 with 38 dated rows, 2023/04/12 → 2025/05/15**; enforcement + warning notices dated.
Every register row carries its own issue date, so **one pull already yields a point-in-time panel on the
entry side** — exits still need snapshots, because a vanished row leaves no trace.

**AND THE LIMITS, WHICH MATTER MORE THAN THE FIND:** one jurisdiction (not a panel); mostly
**entity-level** events where Auer–Claessens classifies **national policy**; and **no plausible channel
to BTC/ETH on Binance — no mechanism is claimed and none should be inferred.** It is timeline *material*
for an existing build, **not an axis**. The obvious GCC-venue idea is foreclosed anyway: the
regional-premium family is buried 7× and kimchi was killed 08-01.

**ENUMERATED, GRADED, DELIBERATELY NOT CARDED** — a source earns a card by serving a named need, and
cataloguing while the desk's bottleneck is verification is the breadth-theater the brief forbids:
**Saudi CMA open-data API** (no auth, 2,156 dated private funds) — real, free, and **zero crypto
content**, so no desk need; **`api.bitoasis.net`** live AED trade tape (200 JSON, real fills) — its
natural mechanism is graveyarded; **ADGM** sitemap with **1,109 dated announcements carrying `lastmod`**
— the second-best artifact and the natural next column *if* R0193 wants one.

**UNMEASURED, KEPT DISTINCT FROM EMPTY** (WS-005): SCA/UAE CMA (pages 200, data behind a **401**),
QFMA (200 Handlebars shells, 0 dates, **zero** "virtual asset"/"crypto"/"VASP"), rain.bh · cbb.gov.bh ·
saudiexchange.sa (403 everywhere; the last has **no apex DNS record**), coinmena.com (`robots.txt`
**200 carrying a Next.js error shell and zero directives**).

**THE ACCESS FINDING, ROUTED AS `OP-076`:** on `bitoasis.net`, **permission and reachability are
independent in BOTH directions** — the apex robots **explicitly names `ClaudeBot` with `Allow: /`**
(verified by me; the **first positive by-name mention in the fleet's entire access map**, where every
prior one was a refusal) yet **403s every content path**, while `api.bitoasis.net` **403s its own
robots.txt and serves a full JSON trade tape**. The two errors are **not symmetric**: inferring
permission from reachability breaches §13; inferring unreachability from refusal merely loses ground.
*(Note s1 read this same file on 08-12 as "ClaudeBot unnamed". Either a misread or a change inside 24h —
either way, a policy read is a dated observation, never a standing fact.)*

---

#### NEXT UN-EXHAUSTED GROUND (named before closing, per L1.35/L1.40)

**The list is re-ordered by OP-075: institutionally-native Arabic first, retail-language layers last.**

1. **ADGM announcement corpus** — `sitemap.xml`, **1,109 dated URLs with `lastmod`**, verified 200 and
   un-mined. The natural **second jurisdiction column** for R0193 and the highest-value unstarted item.
2. **VARA notice BODIES** — this run mined the register/blacklist to row level; the **notice texts**
   (enforcement + warning) are unread, and the reasons inside them are the classifiable content.
3. **`arabsgate.com` thread layer** — still zero threads mined across two sessions. OP-075 *predicts*
   it is thin retail, **and a prediction is not a measurement** — test it rather than inheriting it.
4. **AR video comment layer** — the corpus is rich and mechanism-bearing but transcript-blocked; the
   **comment trees are plain HTML and were never attempted**. Rank by mechanism-keyword density, never
   by votes (the habr lesson). This is the cheapest route into a video-first corpus while GAP #26 is open.
5. **Era-archaeology: STILL UNSTARTED** (carried from s1) — dead GCC/Levant venue layer, *not* the
   P2P-premium layer, which is graveyarded.
6. **`arabictrader.com` / `rain.bh` / `cbb.gov.bh` / `adgm.com` apex** — all 403 on robots.txt itself.
   Under OP-076 these are **UNMEASURED, not closed**; re-probe to read policy (reading policy is not
   routing around access control).
7. **Sharia/fatwa layer — the mechanism s1 left alive.** s1 retired the annual-event *design*
   (`unmeasurable_by_construction`, MDE 3–6× the observed effect, 28 episodes = 21 years) and named the
   only rescue: **cross-sectional expansion (7 events × N assets), never waiting.** That test is unrun.
   Note `aaoifi.com` is an **OP-074-addendum host**: robots-OPEN, but its entire document corpus sits
   under the one `Disallow`ed path, so the standards themselves are **not harvestable**.

---

## BRAIN HUNTER — session 1 (2026-08-11, dedicated daily organ, first run)

**§33 CONVERT-FIRST drained 10 → 0 before digging (weighted 26 → 0, zero unbacked claims):**
2 WIRED with artifacts postdating the finds (`data/cot_btc_panel.json` — CME BTC 435w + CBOE
2017-2019 + micro/nano/perp-style COT, nonreportables net/OI; `data/stablecoin_run_variables.json`
— USDT 3,178d + USDC 2,892d burn-signature, sanity PASS on Terra/SVB, price leg DECLARED ABSENT
per L1.55), 2 KILLED to graveyard with mechanisms + L1.16a re-entry conditions (aigu/ProBitForge
unresolvable; EODHD = L1.11), 1 WIRED via extraction (VeighNa/Qlib → operator library), 5 dated
deferrals with named blockers (NAVER ×2 principal-key GAP #69 re-verified absent; CN corpus
verified-reachable → CN seat 08-18; Kraken archive verified-live → collector 08-25; reg-timeline
→ R0193 08-24 with the no-public-annex failed search documented). R0193 re-scheduled with two of
three data legs landed. Ledger: R0437 raised+scheduled (grouping-map wiring). Lesson L0089.

**GROUND OPENED AND CLAIMS, per the two-exhaustions rule:**
- `microsoft/qlib` `qlib/data/ops.py` — **EXHAUSTED at operator-class level** (all 54 classes
  enumerated from the raw file; 5 elided semantics extracted: N-type-keyed Rolling
  {int/0=expanding/float=EWM-alpha}, min_periods=1 partial windows, future-Ref labels
  verbatim `Ref($close,-2)/Ref($close,-1)-1`, negative-Ref-in-feature = mechanical leak kill,
  Greater/Less = elementwise max/min). NOT claimed: per-operator NaN edge cases below class
  level, the C++/cython accelerated paths.
- `qlib/contrib/data/loader.py` — **EXHAUSTED at field-block level** (Alpha158 ~20 blocks ×
  windows {5,10,20,30,60} mapped, crypto analogues assigned, price-only blocks flagged against
  the graveyard prior). `handler.py` label + processor config read (CSZScoreNorm on the LABEL).
- LICENCES READ FROM CANONICAL FILES: qlib MIT, vn.py MIT.
- **THE BLOCKING INPUT IS CLOSED AT ARTIFACT LEVEL:** `data/crypto_grouping_map.json` — 4 maps,
  296 symbols, quality measured (peer map intra +0.138 / inter −0.011 / floor −0.0034; raw map
  measured-degenerate 268/296 = the N_eff≈1.5 lesson reproduced). Consumer wiring = R0437.
- CoinGecko api_terms — **read FAILED (403), documented on card 28**; not a verdict on the terms.

**Video: 0 fetched, 0 locked** — no video route tried this run (§33 backlog + the blocking input
outranked it; BRAIN lecture corpus untouched and named below).

**NEXT UN-EXHAUSTED GROUND, in order, for session 2 (L1.40 — named before closing):**
1. `vnpy/vnpy` `vnpy.alpha` module tree — the DSL + factor sets in vnpy dialect (licence already
   read; the module read is the owed half of card 24's method mining).
2. The `wqb` Python library (BRAIN API wrapper) — operator/simulation semantics from the
   platform's own API surface; plus open-source BRAIN simulators and alpha101 reimplementations
   for group-operator + decay/turnover semantics the official docs elide.
3. BRAIN lecture/tutorial VIDEO corpus via `scripts/fetch_video_transcript.py` (the video-first
   mandate this run did not reach).
4. CoinGecko ToS via docs subdomain + DeFiLlama licence page (two licence reads owed, card 28).
5. Auer–Claessens WP-version annex (one more route for the 151-event list before R0193's
   reconstruction burns labour).
6. BRAIN community discussion of FAILED approaches (publicly documented negative results —
   graveyard ore, the corpus's most neglected vein).

---


**§33 dispositions (2026-08-18, owed-work batch3 — items above, in order):**
- mql5.com/ar ground resolution: [§33: killed] — 404 at locale root, in-block result
- AR video route: [§33: screened] — 3 AR videos + EN controls logged 2026-08-13 (video_locked_log.md)
- ADGM announcement corpus (1,109 dated URLs): [§33: deferred(2026-08-25)]
- VARA notice bodies: [§33: deferred(2026-08-25)]
- arabsgate thread layer: [§33: deferred(2026-08-25)]
- AR video comment layer: [§33: deferred(2026-08-25)]
- Era-archaeology: [§33: deferred(2026-08-25)]
- apex robots-403 re-probes (OP-076): [§33: deferred(2026-08-25)]
- Sharia/fatwa cross-sectional test: [§33: deferred(2026-08-25)]
### 2026-08-11 session F (EN frontier miner) — IN PROGRESS (write-first note; updated as items resolve)
MINE GATE: BACKLOG-CLEAR (19/19 carded finds disposed; header authorised). PRIOR STATE read:
BRAIN hunter s1 ran TODAY and drained its §33 queue 10→0 — cards #23/#25 got their data legs
(cot_btc_panel, stablecoin_run_variables), R0193 re-scheduled 08-24, NAVER re-deferred (GAP #69),
Auer–Claessens public-annex search already run+failed (their next-ground #5 = WP annex; NOT
poached here). Verify-queue reads 16 pending but ≥2 are PHANTOM: merge-union duplicate cards
whose stale grade lines fail the parser open to pending (#3 bitFlyer line ~187 "RESTRICTED-BY-
LICENCE — CLOSED" lacks a resolved-substring; #21 NAVER line ~988 "needs-monitoring (built,
unrun)" shadows the real legitimacy-queue card at ~932).
ITEMS THIS RUN (bounded per completion contract):
1. BACKLOG HYGIENE (Tier-1 defect-closer — phantom pending items make every future cycle re-read
   dead cards): dedupe cards #3 and #21 to ONE card each with the honest current grade; re-run
   source_backlog_next to verify the queue drops; confirm R0193 live in the ledger.
2. ELITETRADER + NUCLEAR PHYNANCE FIRST TOUCH (carried since 08-04 session D item 3; the last
   never-touched EN deep/legacy forum grounds): robots/§13 gate first, ground survey, then ≥1
   thread to reply-depth ≥2 on whichever ground is open. Nuclear Phynance expected dead →
   era-archaeology route via Wayback CDX.
3. IF BUDGET REMAINS: HN 9152332 contest-winner tree (Records family, unmined, named since 08-04).
STATUS: session DIED MID-WORK (items never resolved here). CLOSED 2026-08-12 by the next
prospector session, which inherited and finished items 1-2 (see its note below: hygiene commit
4f902d2, EliteTrader/NP touched); item 3 (HN 9152332) remains un-mined and is re-named there.

---

### 2026-08-12 PROSPECTOR session (standing daily; brain seat, real egress) — IN PROGRESS (write-first note; updated as items resolve)
PRIOR STATE: session F (2026-08-11 EN frontier) died mid-work — its note still reads "items open"
(coverage doc untouched since 08-11 16:26 UTC, no concurrent miner in ps). Its items are inherited
here per RESUME-DO-NOT-RESTART (3). MINE GATE at start: CONVERT-FIRST, 2 owed (both T3, both
licence-read blockers, both deferred(2026-08-12) — the deferrals matured today).
ITEMS THIS RUN (bounded per completion contract):
1. §33 DRAIN (first, per CONVERT-FIRST): card 27 GMO Coin tick archive — read kihon-yakkan.pdf
   (URL harvested this run from coin.z.com/jp/corp/policy/terms/, ver=20260725) + hunt the API
   terms doc; re-grade + dispose R0309. Card 28 bitbank — the brain seat has real egress the
   research container lacked; try direct/Wayback/underlying-JSON routes for the 規約 body;
   re-grade + dispose R0310.
2. SESSION F ITEM 1 (backlog hygiene, Tier-1 defect-closer): dedupe phantom pending cards #3
   bitFlyer + #21 NAVER in data_axis_watchlist.md; verify source_backlog_next count drops.
3. SESSION F ITEM 2 (first touch of the last never-touched EN legacy forums): EliteTrader +
   Nuclear Phynance — robots/§13 gate first, then ≥1 thread to reply-depth ≥2; NP expected dead
   → Wayback CDX era-archaeology route.
RESOLVED 1 (§33 DRAIN 2→0, both T3 licence reads DONE, commit 5361358): **Card 27 GMO** —
kihon-yakkan.pdf (ver=20260725) extracted stdlib-only (zlib+ToUnicode CID decode; the PDF read
needed no poppler and no install — method now reusable for any JP 約款 PDF). Art. 14(15) =
consent-required off-service-use clause; Art. 7(1) deemed assent; NO API-specific terms exist
(policy index + product page + archive index all enumerated). → needs-legitimacy-review, DECIDE
queue, owed 08-19. **Card 28 bitbank** — the 08-04 "egress" diagnosis was WRONG-URL:
`/error/terms` is the SPA's error route; canonical ToS at **`bitbank.cc/doc/tos`** server-renders
to curl (686 KB, 86,728 chars extracted, double-entity-encoded). Art. 17 has NO data-reuse
clause; Art. 20 excludes 公知 info; the one restrictive text is the site-footer 免責事項
(私的利用のみ/非商用 over prices+data) — scope over public.bitbank.cc is the open question;
venue support docs positively invite programmatic public-data retrieval. → needs-legitimacy-
review, DECIDE queue, owed 08-19. R0309+R0310 → IMPLEMENTED. Gate: BACKLOG-CLEAR.
RESOLVED 2 (session F item 1, backlog hygiene, commit 4f902d2): phantom pending cards deduped —
card 3 bitFlyer (line-200 superseded ruling demoted h3→h4) + card 21 NAVER (needs-monitoring
twin demoted; the real needs-legitimacy-review card stands). Verified: catalogued 32→30, verify
queue 14→12, mine gate 19→18 finds still BACKLOG-CLEAR, no mine-item-vanished (stable_key
preserved — checked vanished() keying BEFORE demoting). R0193 confirmed live: due 2026-08-24.
RESOLVED 3 (session F item 2 — the last never-touched EN legacy forums, both gated then dug):
- **ELITETRADER: CLOSED for this seat.** robots.txt names `User-agent: ClaudeBot / Disallow: /`
  (GPTBot also refused — BOTH model families are barred by name, so the second-family seat is no
  door either). Cloudflare content-signals for `*` read search=yes/ai-train=no/use=reference, but
  the by-name refusal governs (KR-seat precedent). Archive side-door NOT taken — a standing
  by-name refusal is not extinguished by Wayback (bitFlyer ruling). §38 REPLACEMENT, same run:
  the same information class (EN practitioner-forum mechanisms) is served by the NP archive
  corpus OPENED below + the already-rotating live grounds (r/algotrading, QuantConnect).
  RESIDUAL, graded: EliteTrader's post-2012 content is unreachable for both bot families;
  re-entry = robots change or a human read. Wilmott (live-forum replacement candidate): WALLED
  today — Cloudflare 403 on robots.txt through BOTH egresses (curl + WebFetch); re-probe later,
  not a refusal-by-name.
- **NUCLEAR PHYNANCE: ERA-ARCHAEOLOGY GROUND OPENED (dead site, no standing operator).** Live
  host dead (000 https+http). Wayback CDX: **6,645 distinct archived thread-page captures**
  (`Show Post.aspx?PostIDKey=*`, 2006→2021) + forum indices (`Show Forum.aspx?ForumIDKey=1..13`,
  captures 2009-2013 rich) + a 2004 `/beta/` era. Post-2009 domain-root captures are mostly
  error pages — the thread-page pattern is where the corpus lives.
- **DEPTH LINE (per the depth mandate):** forum-1 index (Sep-2012 capture) read to title level
  (24 threads mapped w/ PostIDKeys); thread **161897 EXHAUSTED** (Page 1 of 1, 6 posts, full
  reply chain ≥2 with quoted-reply refinement — yielded the no-static-hedge vol-carry mechanism
  + the funding-is-flow-not-replication confirmation, which the SURFACE title never showed);
  thread **161299 EXHAUSTED** (Page 1 of 1, 8 posts, reply chain ≥2 — yielded the ≥15-min/
  midpoint VR discipline + the Lo reference + the "statistical quantities cannot label a
  specific run" caveat, none visible from the title). 159928 (HFT Apology): NO captures — dead
  seam, documented. Yield routed: 1 EV-gated mechanism (rejected 0.0003, watchlisted with
  breadth trigger), 1 methodology constraint (inbox + R0452 scheduled 09-09), 2 research-memory
  rows, 0 fabricated survivors.
- **SECTION STATE CLAIMED:** NP forum-1 Sep-2012 snapshot = SURVEYED (24 titles); threads
  161897 + 161299 = EXHAUSTED (2026-08-12). NOT claimed: the other ~6,600 captures, other
  forum indices (2-13), other index years.
NEXT UN-EXHAUSTED GROUND, in order (L1.35 — named before closing):
1. NP forum indices ForumIDKey=2..13 (one CDX-captured snapshot each; map which are
   Trading/Numerical vs Careers noise) + the 2013 forum-1 snapshots for post-2012 titles.
2. NP high-value thread batch from the mapped titles: 161162 Convexity arbitrage, 161713
   backtest-evaluation methodology (both capture-verified this run).
3. Session F item 3, still un-mined: HN 9152332 contest-winner tree (Records family).
4. bitFlyer/GMO decision follow-through: the two DECIDE-queue rows owe a ruling by 08-19
   (cards 27/28) — the next session verifies the decision landed or escalates.
5. Wilmott re-probe (WALLED today, not refused — a different day/egress may open robots).
STATUS: ALL THREE ITEMS RESOLVED. Run closed cleanly 2026-08-12 (completion contract met:
write-first note, bounded scope, §33 drained 2→0, dead session F's items finished, findings
routed, dead ends logged).

---

### 2026-08-12 session G (EN frontier miner, seat rotation 05:30) — IN PROGRESS (write-first note; updated as items resolve)
PRIOR STATE: the 08-12 PROSPECTOR (brain seat) run closed cleanly this morning — §33 drained 2→0,
session F's items 1-2 finished, NP archaeology ground OPENED (6,645 thread captures mapped, forum-1
Sep-2012 index surveyed, 2 threads EXHAUSTED). Mine gate: BACKLOG-CLEAR (no mining_suspended).
Verify queue reads 14 pending but the cycle's 6 listed are OWNED IN-FLIGHT elsewhere: card 23 BIS
1087 [§33: wired -> data/cot_btc_panel.json, screen=R0193 due 08-24], card 24 Auer–Claessens
[§33: deferred(2026-08-24)], copula-5min + quarter-hour = litminer run 6 (commit cab49a0, R0459),
KR venue-state + stablecoin-run = KR/brain seats. Not poached; my queue is the prior close's
NEXT-UN-EXHAUSTED-GROUND list.
ITEMS THIS RUN (bounded per completion contract; oldest debt first, so a dying run strands the
least-carried item, not the most):
1. HN 9152332 contest-winner tree (Records family) — carried since 08-04 session D, thrice-named,
   never mined. OP-022 full-tree walk, depth labels, mechanism-keyword ranking, venue harvest.
2. NP high-value thread batch: 161162 (Convexity arbitrage) + 161713 (backtest-evaluation
   methodology), both capture-verified 08-12am. OP-019/OP-034 discipline (length-rank captures,
   id_ fetch, gzip-sniff), reply-chain ≥2, then claim EXHAUSTED per-thread.
3. NP forum indices ForumIDKey=2..13 (one CDX-captured snapshot each; classify Trading/Numerical
   vs Careers noise) + forum-1 2013 snapshot for post-2012 titles — survey level, feeds the next
   thread batch.
SIDE-CHECKS (recorded, not items): Wilmott robots re-probe (WALLED this morning, one curl, honest
record either way); venue-discovery harvest from every tree read (standing obligation).
STATUS: items 1-3 OPEN.
RESOLVED 1 (HN 9152332, Records family — carried since 08-04, now CLOSED): full tree via OP-022
(28 comments, max depth 3, all read — mine-everything, no filter). Yield: the 2015 contest thread
is the ERA COMPANION to graveyard `crowdsourced_backtest_selection_fund` — in-thread 2015
predictions (learnstats2 max-risk selection; numlocked/im2w1l survivorship arithmetic) confirmed
by the 2020 capital-return; fawce's defense named the failed gate; im2w1l's data-fingerprint
attack on blackbox evaluation = the conditional-behavior overfit class forward-only promotion is
immune to. Graveyard entry ENRICHED (era rider). Leaderboard-CSV lead probed and DEAD:
/leaderboard/csv exists in CDX only as a 2020 301 — content never archived; per-contest HTML
snapshots exist (e.g. /leaderboard/15, 20.9KB, 2017-03) but an equities IS-vs-paper panel is
low-EV vs the desk's own measured 86% OOS decay — recorded, not carded (verification-bottleneck
doctrine). New venue harvest from tree: ZERO (only quantopian.com self-refs). OP-022 field note
added: OPERATOR-DEFENSE MINING (the platform's own defensive replies = free pre-registration of
its failure mode; pair with outcome = complete natural experiment).
RESOLVED 2 (NP threads 161162 + 161713, both EXHAUSTED 2026-08-12): **161162 "Convexity
arbitrage"** (3 posts, Page 1 of 1) — mid-90s convexity-adjustment-neglect era lore (FRA-vs-
futures ignored until a London desk arbitraged it; victim "no longer around"; Napoleon/reverse-
cliquet rider → WS-007). TRANSLATED: inverse-contract convexity ⇒ COIN-M vs USDT-M fair-basis
wedge ⇒ **NEW DATA AXIS: Binance COIN-M dapi, verified-live keyless this run (30 instruments:
20 perps + 5 quarterly underlyings BTC/ETH/BNB/SOL/XRP), ZERO prior desk coverage** →
data_axis_watchlist card 31 [§33: deferred(2026-08-19) tier:2] + universe map 98-binance-coinm-
dapi + R0462 (backfill + pre-registered convexity-differential screen). Mechanism
coinm_usdtm_basis_convexity_rv EV-gated honestly: REJECT 0.0009 (both tag readings reported,
0.0009/0.0002) → watchlist memory with a MEASUREMENT promotion trigger (4/5 slots). **161713
"Help needed with backtested results evaluation"** (14 posts, full reply chain) — a 2012
validation time capsule CONFIRMING desk doctrine part-for-part: Maggette's random-tape harness
placebo (= certify_gauntlet known-NULL, R0017 — already wired, NO inbox row spent), YukaRedux's
live-vs-backtest same-window reconciliation (= L2.10 reality gap), IVolrev's slippage-feedback-
into-cost-model (= L1.11(b) execution reality model), intradaybill's profit-factor≈1 noise-trading
tell + "even 1 parameter suffices for curve-fitting" + the GP anecdote (1000 generations, "OOS
was good", −70% — selection ON the OOS is still selection → graveyard rider). 3 research-memory
rows logged (rm-20260812T062443-5b1577/-a9efcc/-4a0939).
RESOLVED 3 (NP forum indices 2..13 survey): 8/13 CLASSIFIED from one snapshot each — **f2
TRADING (RICH: 25 titles mapped @2011-02 incl. 112425 Price patterns, 147526 new-issue premium,
4851 Renaissance watch — THE next thread-batch ground)**, f4 risk/VaR methods, f5 quant-theory
(2005 capture), f8 books (2005), f6 careers NOISE, f10 off-topic NOISE, f12 general-misc (147620
Kelly, 147696 Dynamic Correlation), f1 done prior. **f3/f7/f9/f11/f13: ZERO Wayback captures (2
CDX probes each) — unarchived seams, documented.** Venue-discovery thread 148582 ("top 3 forums")
= 0 replies at its only capture: dead seam, honest zero. CDX operational note: web.archive.org
CDX threw intermittent 503s + 2 whole-loop stalls this run — single-shot retries recovered ~half;
counts for f2/f4/f5 were limit-capped at 50 (spans 2005-12→2013/15/18).
DEPTH LINE: HN 9152332 = full tree exhausted (28/28 comments, depth 3); NP 161162 = exhausted
(3/3 posts + risk.net citation noted, not chased — era exotics, no desk options book); NP 161713
= exhausted (14/14 posts, reply-chain ≥2 with quoted-reply refinement); NP indices = surveyed
(title level, by design — survey item). Zero surface-only touches. video: 0 fetched, 0 locked —
no video grounds hit this run.
SIDE-CHECKS RESOLVED: Wilmott robots.txt 403 again (2nd probe, WALLED stands, not refusal-by-
name; re-probe next run). Sibling-modified files NOT staged (CRO_BRIEFING.md,
gauntlet_certification.json).
NEXT UN-EXHAUSTED GROUND, in order (L1.35 — named before closing):
1. NP forum-2 (TRADING) thread batch from the 25 mapped titles: 112425 "Price patterns", 147526
   "corporate bond new issue premium" (translate: listing/unlock premium mechanics), 4851
   "Renaissance Watch" (process lore) — via CDX per-thread captures.
2. NP forum-1 2013 snapshots for post-2012 titles (from the 08-12am session's list) + forum-12's
   147620 Kelly criterion + 147696 Dynamic Correlation Model threads.
3. Records family: Kaggle G-Research crypto post-mortems + Numerai forum post-mortems (the two
   never-touched Records grounds).
4. Cards 27/28 (GMO/bitbank) DECIDE-queue follow-through owed 08-19; card 31 §33 deferral owed
   2026-08-19 (R0462 disposition owed 24h — engineering seat).
5. Wilmott re-probe (WALLED ×2; a robots change or different egress reopens it).
STATUS: ALL THREE ITEMS RESOLVED + 2 side-checks. Run closed cleanly 2026-08-12 (write-first
note, bounded scope, depth per item maxed, 1 new axis + 1 EV-gated mechanism + 1 WS + graveyard
enrichment + OP-022 contribution routed; honest zeros: 0 new venues, 0 video, leaderboard-CSV
dead, 148582 dead, 5 NP indices unarchived).

---

## BRAIN HUNTER — session 2 (2026-08-12, dedicated daily organ)

**MINE GATE: BACKLOG-CLEAR** (17/17 carded finds disposed; header authorised). **PRIOR STATE READ:** s1's next-ground chain (6 items) inherited intact. R0437 verified live and correctly SCHEDULED (due 08-18) — the grouping map's consumer wiring is owed by the alpha org, not by this seat.

**S1's BLOCKING-INPUT WORRY IS CLOSED, AND IT CLOSED BETTER THAN S1 THOUGHT.** S1 left "CoinGecko ToS read FAILED (403)" open as a possible §13 exposure on `data/crypto_grouping_map.json`. Re-read from the artifact: its `provenance.source` records **desk-owned D1 bars, NO vendor taxonomy consumed** — so the map has **zero licence surface** and the CoinGecko/DeFiLlama licence reads (s1 next-ground item 4) are **not blockers on it**. They remain owed only if the desk ever wants a *category* taxonomy. **This is L1.11 working as designed: the moat is the transformation, not the purchased dataset.**

### GROUND OPENED, and the two-exhaustions rule applied

- `efJerryYang/worldquant-brain-simulator` (**GPL-3.0**, 32★) — **EXHAUSTED at PIPELINE level.** `settings.yaml`, `expression.py`, `util.py` and `simulate.py` (389 lines) read in full. **NOT claimed:** `alpha_pool/alpha101.py` (43KB) — deliberately unmined, it is 101 equity *formulas* and this organ extracts *mechanisms* (brief: "a copied formula is a crowded expression over a universe the desk does not trade"); `datasource/database.py`.
- `QuantML-Research/wq-alpha-research` `SKILL.md` (**NO LICENCE ⇒ all-rights-reserved**, 349★) — **EXHAUSTED §§1–6** (decision tree, field catalogue, operator table, templates, metrics, IS checks, diagnostics). **§§7+ NOT MINED AND WILL NOT BE: account-gated BRAIN API automation. §13 hard stop** — a credentialed account's contents are not public because an account exists. No credential was held, sought or used.
- **`platform.worldquantbrain.com/learn/...` — WALLED.** Route tried 2026-08-12, returns a JS shell (title only). Logged as WALLED, not as absent. Naming what is behind it is legitimate; going behind it is not.

### VIDEO: 0 fetched, 0 source-locked — and the distinction is the whole finding

**1 id (`kuIfHJEsPkY`, Learn2Quant lesson 1) attempted through 3 independent routes, all failed — and NOT ONE failure is WorldQuant's.** The desk fetcher's 4 hardcoded Piped proxies are **all down** (500 / 502 / 301 / DNS-NXDOMAIN, each measured); the legacy timedtext endpoint returns 200 with a **zero-byte** body; the ANDROID innertube client returns 400. **`www.youtube.com` returns 200 from this box.**

**So the corpus is REACHABLE and our tool is DEAD, and `video_locked` would have been the wrong log.** L1.34 makes video first-class for *every* seat, so this outage is silently degrading all of them and each one that tries will mis-attribute a desk-side failure to a source-side wall — the desk's own lesson inverted ("a verdict about the HOST is not a verdict about the DESK"). **Ledgered R0527, scheduled 08-15** with the full diagnosis and a 4-step fix. **The official BRAIN lecture corpus therefore remains UNMINED and is not claimed as thin.**

> **🔴 RETRACTED 2026-08-13 BY BRAIN HUNTER s3 — THIS PARAGRAPH IS WRONG IN BOTH HALVES, AND `video_locked` WAS THE RIGHT LOG AFTER ALL.**
> Measured on the same endpoint s3 morning: **`api.piped.private.coffee` is UP** and serves
> `dQw4w9WgXcQ` with 6 subtitle tracks (HTTP 200) *in the same minute* that 15 of 16 other videos
> return HTTP 500. **s2 read a proxy faithfully RELAYING an upstream wall as a proxy that was
> DOWN** — the 500 bodies carry YouTube's own `SignInConfirmNotBotException … LOGIN_REQUIRED`,
> which is a *source* verdict, not a transport failure. And the corpus is **not** reachable: a
> plain honest-UA GET of `www.youtube.com/watch?v=kuIfHJEsPkY` returns a **1,133,907-byte HOLLOW
> 200** — empty `<title>`, **zero** `captionTracks`. s2 checked that `www.youtube.com` returned
> 200 and never checked what was *in* the 200, which is the desk's own hollow-success lesson
> arriving one level up from where it was written.
> **R0527 REJECTED** (premise refuted; acting on it would have sent an engineer to replace four
> working proxies). The real defect — per-instance error reporting, dropping the dead
> `api.piped.yt` domain, classifying `LOGIN_REQUIRED` as PLATFORM-WALL — is correctly diagnosed
> and live as **R0592**. The 13 lecture ids are now logged in `video_locked_log.md` with a
> measured **93.75% blocked fraction** over a 16-video controlled panel. The corpus is
> **SOURCE-WALLED, still UNMINED, and still not claimed as thin.**

### NEW VENUES (standing discovery obligation — the seed list is a floor)

| venue | what lives there | how found | verdict |
|---|---|---|---|
| `rocky-d/wqb` (MIT, 272★) | the BRAIN **API wrapper** — platform semantics from its own API surface | search | **RICH, UNMINED** — s1 item 2's other half |
| Learn2Quant YT playlist `PLmpIWlqVqfbf0F0sqUaYeOKoT_LFvB2yd` | official BRAIN lecture corpus | search | **RICH, TOOL-BLOCKED** (R0527) |
| **IQC 2026 webinar series** (weekly, Thursdays) | official research webinars, **recurring** | search | **RICH, RECURRING** — the standing argument for a daily organ: the platform keeps publishing |
| `jglazar/notes` (247★, **no licence**) | `worldquant_seminar.md`, `submitted_alphas.md` — PROCESS mining | search | **UNVERIFIED** — both guessed paths 404; needs a tree walk |
| `laox1ao/Alpha101-WorldQuant`, `zhutoutoutousan/worldquant-miner`, `TonyMa1/wq_new`, `jdhruv1503/Brainiac`, `alexisdpc/WorldQuant-alpha-trading`, `dige04/WQ-Brainn`, `RussellDash332/WQ-Brain`, `xiegengcai/world-quant-brain`, `jingmouren/CrisperX-50_..._Alphathon` | reimplementations, miners, agent harnesses, a 50-alpha low-correlation example set | search | **UNTRIAGED** — the fork/reimplementation layer, exactly the recursive-expansion node the brief calls highest-yield |

### §33 DISPOSITIONS — every find routed in-run (screen-on-discovery)

- **Pipeline semantics** (neutralize→truncate→normalize; `rank` = uncentered [0,1]; `decay_linear` exact weights; 6 missing operators; the two-stage construct) **[§33: wired -> docs/research/search_operator_library.md `wq-brain-pipeline`, OP-058..067]**
- **4,367-field taxonomy + 142 GROUP-typed fields + yield-by-category** **[§33: screened -> docs/research/data_axis_watchlist.md card 32]**
- **4 process imports** **[§33: screened -> docs/research/improvement_inbox.md + ledgered R0528 scheduled 08-18]**
- **3 defects in the public alpha101 lineage** (bfill look-ahead, neutralization dead-branch, gross-only PnL) **[§33: killed -> docs/graveyard.md]**
- **Video-fetcher outage** **[§33: wired -> ledger R0527 scheduled 08-15]**

**CONFIRMED, NOT ASSUMED:** the desk's `fitness()` matches the CN community source **exactly**, 0.125 floor included — independent corroboration of a formula previously held on one screenshot. **NO card added to `prospector_watchlist.md` (5/5 slots used, and nothing here earns a displacement).** The one construct worth trading — `group_rank(ts_rank(funding_carry, N), corr_cluster_residual)`, the platform's canonical two-stage form applied to the desk's only repeat survivor — is **not a new mechanism** and must not pretend to be one: it is a **variant dimension for the pre-registration R0437 already schedules**, and it is priced there in `VARIANTS_TRIED`, not smuggled in as a watchlist card.

### NEXT UN-EXHAUSTED GROUND, in order, for session 3 (L1.35/L1.40 — named before closing)

1. **`rocky-d/wqb` (MIT)** — the API wrapper's request/response models are the platform's **own** vocabulary for settings, checks and failure codes; MIT makes it the cleanest source on this ground. Carried from s1 item 2, half-done.
2. **The reimplementation/fork layer** (table above, 9 repos) — triage for *elided semantics*, especially anyone who implements `group_neutralize`, `winsorize`, `ts_zscore` or `vec_*`, since those are the six operators the desk still lacks. **`CrisperX-50` is the specific prize:** 50 alphas selected to pass a *mutual correlation* test — that is a worked example of building a **low-correlation portfolio**, which is the desk's independence problem, not its signal problem.
3. **BRAIN lecture corpus** — blocked on R0527, **re-attempt the day it lands** (do not re-log as walled).
4. **`jglazar/notes` tree walk** — process/seminar mining; both guessed paths 404, so walk the tree rather than guessing again.
5. **IQC 2026 webinar series** — recurring weekly; establish whether materials are published outside the login wall.
6. **BRAIN community discussion of FAILED approaches** — s1 item 6, still the most neglected vein. This run took the *first* real bite (the failure-cause and yield-by-category tables) and it was the highest-value find of the session, which argues the vein is rich rather than worked.

**A NULL WAS NOT AVAILABLE THIS RUN and none is claimed.** Ground remains wide open: 9 untriaged repos, an unmined official lecture corpus, a recurring webinar series, and a platform that keeps publishing. **Seat-exhaustion is false here as everywhere.**

---


**§33 dispositions (2026-08-18, owed-work batch3 — items above, in order):**
- rocky-d/wqb API wrapper: [§33: screened] — s3 08-13 API-namespace mining
- Reimplementation/fork layer (9 repos): [§33: screened] — partial (CrisperX taken); remainder re-carried in the s4 list
- BRAIN lecture corpus: [§33: killed] — R0527 REJECTED (500-carrying-LOGIN_REQUIRED); SOURCE-walled; re-entry = text mirror (s4 list)
- jglazar/notes tree walk: [§33: deferred(2026-08-25)] — superseded by the s4 list
- IQC 2026 webinar series: [§33: deferred(2026-08-25)] — superseded by the s4 list
- BRAIN community FAILED approaches: [§33: deferred(2026-08-25)] — superseded by the s4 list
### 2026-08-13 session H (EN frontier miner) — IN PROGRESS (write-first note; updated as items resolve)

PRIOR STATE READ (resume rule, not restart): session G (08-12) closed cleanly — HN 9152332
exhausted, NP 161162 + 161713 exhausted, NP indices 2..13 surveyed (8/13 classified, 5 unarchived).
Mine gate re-read live this run: **BACKLOG-CLEAR, 18/18 carded finds disposed, mining authorised**
(`scripts/mine_gate.py`, not the header alone). `source_backlog_next.py` verify-queue re-read: the
6 listed are the same set session G recorded as owned in-flight elsewhere — **re-measured, not
inherited** (see SIDE-CHECKS).

ITEMS THIS RUN (bounded per completion contract; the never-touched crypto-native ground first,
because the BINANCE/CRYPTO PRIORITY order outranks my own carried list — NP is general TradFi):
1. **Kaggle G-Research Crypto Forecasting post-mortems — NEVER TOUCHED by any seat.** Named
   untouched in the Records row on 07-25, 08-04 and 08-12 (three sessions carried it). Crypto-
   native, EXECUTABLE tier (code + data + params + public leaderboard = refutable), and a
   competition post-mortem is the one artifact class where FAILURES are published by the people
   who ran them. §13 access map first (OP-052 UA matrix), then winners' writeups + discussion to
   reply-depth ≥2, mechanism + PROCESS extraction, screen-on-discovery.
2. **NP forum-2 (TRADING) thread batch** — session G's named next-ground #1, from the 25 titles
   mapped @2011-02: 147526 "corporate bond new issue premium" (TRANSLATES to listing/unlock
   premium mechanics — a desk-owned axis), 112425 "Price patterns", 4851 "Renaissance Watch"
   (process lore). CDX per-thread captures, OP-019/OP-034 discipline, claim EXHAUSTED per thread.
3. Only if 1-2 close: Numerai forum post-mortems (the other never-touched Records ground).

SIDE-CHECKS (recorded, not items): Wilmott robots re-probe (WALLED ×2 as of 08-12); venue harvest
from every tree read (standing obligation); video — fetch anything video-shaped I hit and record
the explicit zero either way (R0527 has the desk fetcher DEAD, so a failure there is DESK-side and
must NOT be logged as video_locked — that is the exact mis-attribution R0527 names).

STATUS: items 1-3 OPEN.

RESOLVED 1 (Kaggle G-Research Crypto Forecasting — the never-touched Records ground, OPENED and
worked; the ground is now ACCESS-MAPPED and PARTLY EXHAUSTED, and the two halves are different
verdicts that must not be collapsed):

**§13 / ACCESS MAP (every line a probe run this session, not an inference) → OP-068.** Kaggle serves
**no robots.txt at all** (404 to ClaudeBot, curl and Googlebot alike) — so there is no exclusion and
the ground is §13-clean on the robots axis, which is exactly how a seat stopping at robots concludes
"open ground" and mis-reads what follows. The content path is a **JS shell**: `/discussion/<id>` →
200 / 5.6 KB / zero topic content; `/writeups/<slug>` → 200 / 6.2 KB with `og:title` carrying the
title and `og:description` **empty**. The nastiest case is the data export —
**`/c/30894/publicleaderboarddata.zip` returns HTTP 200 with `content-type: text/html`, 5,593
bytes**, so a naive `curl -o lb.zip` *succeeds*, writes a plausibly-named file, and the ground reads
as harvested. **This is a THIRD false-null class** beside R0466's walled-vs-exhausted pair:
REACHABLE-BUT-CONTENTLESS, and it is invisible to any pipeline that treats 200 as success.
The live gRPC-web API answers **400** on `discussions.DiscussionsService/GetTopicListByForumId`
(route real, body/session wrong) and 404 on sibling names — 400-vs-404 is a usable method-name oracle.

**THE ASYMMETRY, which is what makes the ground partly mineable and is not guessable:** Kaggle
embeds `Kaggle.State.push({...})` in served HTML, but **what it holds depends on page type** —
discussion and leaderboard pages carry **competition-level state only** (topic bodies and
leaderboard rows were XHR-loaded and therefore **never entered Wayback at any timestamp**, so no
amount of re-probing recovers them), while **notebook pages carry FULL kernel state**. On this
platform **the code layer is archived and the forum layer is not**, which inverts the usual digging
order. Captures must be **length-ranked, not recency-ranked** (20 KB 2021-22 captures carry state;
4-5 KB 2023+ captures are the modern shell), fetched with `id_`, **gzip-sniffed** (cost a wasted
probe again), and brace-matched rather than regexed. `renderedOutputUrl` is a signed
kaggleusercontent URL and **403s years later** — recoverable metadata pointing at unrecoverable
content, a lead and never a source.

**WHAT WAS RECOVERED (primary source, archived, verified — not from context):** the competition
DESIGN. **1,946 teams / 2,398 competitors / 3,141 entries; $125,000 over 10 prizes;** models
**frozen at the 2022-02-01 final-submission deadline** and scored on **live forward market data to
2022-05-03** (~3 months), 2 scored submissions per team, code-competition rules (notebooks only,
**internet disabled**, ≤9h runtime). Metric = **weighted Pearson correlation**, per-asset weights
shipped in `asset_details.csv`. Target = **"15 minute residualized returns"** — market-neutral, not
raw. And the host's own words in the data description: **"THE PUBLIC LEADERBOARD FOR THIS
COMPETITION IS NOT MEANINGFUL"** because the public-LB targets were shipped inside the training
data. So the private leaderboard is a genuine frozen-model forward-only test — with the sharp
caveat that competitors selected their 2 final submissions **with no meaningful validation
feedback at all**.

**THE FIND → WS-012 + R0577 (screen-on-discovery, routed in-run).** The desk-relevant content is
not a mechanism, it is a TARGET CONSTRUCTION, and chasing it corrected me twice against the
artifacts: I first assumed the desk screens only daily (**false** — `screen_moat.py` screens 60s
bars) and then that it never neutralises (**false** — `panel_breadth.py` states the daily panel
screen's target IS the cross-sectionally demeaned return). The surviving, verified claim is
narrower and better: **`scripts/screen_moat.py:317` loops per symbol and builds a per-symbol RAW
forward return at 60s-900s horizons with no demeaning at any horizon, while
`libs/research/panel_breadth.py:35-42` records the desk's own measurement that raw-return panels
carry 1.88 effective bets against 139 for demeaned ones.** The two screen layers disagree about
target construction and **nothing compares them** — the L1.61 shape, where each artifact is
individually correct and the contradiction exists only in the relation. G-Research chose the
residual at almost exactly this horizon, **DERIVES-FROM: NONE (checked)** in both directions, so
this is genuine independent convergence on METHOD — which buys a queue place, never a lower bar.
**Honest limit, recorded because it is the load-bearing one: I could NOT verify that any team
achieved positive forward correlation.** Prizes were awarded; that is a different claim. The
private-LB rows are structurally unrecoverable (above), so "the space is non-empty at 15-min
residualised" stays **unevidenced** and WS-012 rests only on G-Research's DESIGN — a statement
about their prior, not about the outcome. The falsifier is named: the private LB score column.

**PROCESS MINING (the half a session returning only claims would miss).** From the host's own
wrap-up: all of the top three used **LightGBM**, some tried neural nets, and **every top competitor
attributed their result to FEATURE ENGINEERING over model development** — on a residualised
sub-hourly crypto target, model class was not the lever. From a third-party solutions index
(secondary, flagged as such): 2nd = walk-forward CV, squared loss, **trained on the COMPLETE
history rather than recent periods** (an empirical non-stationarity claim that contradicts the
competition's own "highly non-stationary" framing — worth remembering when the desk next assumes
recency-weighting); 3rd = **minimal feature engineering, close prices only**; 9th = hull MAs +
Fibonacci-sequence windows + per-regime expert models; 7th = ensemble over sequence lengths +
time-of-day + axial attention. **Untested here, recorded as ore, not as evidence.**

SIDE-CHECKS RESOLVED: **Wilmott re-probed a 3rd time — robots.txt AND forum root both 403.
WALLED stands** (not refusal-by-name; a CF edge block). **VIDEO: 0 fetched, 0 locked.** One
video-shaped artifact was hit (the competition overview embeds a YouTube introduction,
`GW84uCnYr30`) and **deliberately not fetched**: R0527 has the desk's 4 Piped proxies measured dead,
so a failure would be DESK-side and logging it as `video_locked` would be exactly the
mis-attribution R0527 names. **Explicit zero recorded so a later reader can tell "never hit" from
"never tried": hit 1, tried 0, blocked-by-desk-tooling 1.** New venues discovered: **1** —
`kaggle.curtischong.me`, a third-party index of Kaggle solution writeups by rank (**RICH for
navigation, SECONDARY for evidence**: it is the only route that maps rank → writeup URL now that
the forum layer is unreadable, and it is how the 2nd/3rd/7th/9th-place approaches above were
identified at all).

ITEM 2 (NP forum-2 TRADING batch) — **NOT STARTED, and named as such rather than padded.** Item 1
went deep instead of wide: the access map, the state-recovery route, the design recovery and the
target-construction find each opened the next, and the DEPTH MANDATE prefers one ground exhausted
to two touched. Item 2 carries forward unchanged as next-ground #1, with no work lost.

DEPTH LINE: Kaggle competition ground = **access-mapped to exhaustion** (robots ×3 UAs, 4 content
paths, 3 API method names, 2 archive routes, export magic-bytes) + **design layer EXHAUSTED**
(every `pages` entry, `rules`, `dataIntro`, `evaluationAlgorithm` read in full from the archived
state) + **solution layer SURVEYED** (4 ranks identified via a secondary index, 0 read at primary —
the forum layer is unrecoverable and the notebook layer was never captured for these authors:
`kaggle.com/code/sugghi*` returns **zero CDX rows**). Zero surface-only touches. **SECTION-EXHAUSTION
claimed for: the competition design layer (2026-08-13). NOT claimed for: the solution layer, the
notebook layer, or the Kaggle ground as a whole** — the notebook-state route (OP-068) is proven and
untried at scale, which is next-ground #2.

NEXT UN-EXHAUSTED GROUND, in order (L1.35 — named before closing):
1. **NP forum-2 (TRADING) thread batch** — carried intact from session G: 147526 "corporate bond
   new issue premium" (translates to listing/unlock premium mechanics), 112425 "Price patterns",
   4851 "Renaissance Watch". Twice-carried now; take it FIRST next run.
2. **Kaggle NOTEBOOK layer via OP-068** — the route is proven and the code layer is the archived
   half of this platform. Highest-value targets are crypto competition notebooks with CDX captures;
   `sugghi`'s have none, so CDX-map by competition rather than by author. Also unblocks the OTHER
   crypto competitions on Kaggle, never surveyed.
3. **Numerai forum post-mortems** — the last never-touched Records ground.
4. Cards 27/28 (GMO/bitbank) DECIDE-queue owed 08-19; card 31 §33 deferral owed 2026-08-19.
5. Wilmott re-probe (WALLED ×3 — a robots change or different egress reopens it).

STATUS: **item 1 RESOLVED to genuine depth (1 operator OP-068, 1 weak signal WS-012, 1 ledger row
R0577, 1 new venue, design layer section-exhausted); item 2 NOT STARTED and carried; item 3 not
reached.** Run closed cleanly 2026-08-13. Honest zeros recorded: 0 mechanisms carded (the find is
methodological, and the watchlist is at 5/5 with nothing here earning a displacement), 0 video
fetched, 0 primary-source solution writeups readable, private leaderboard UNRECOVERABLE with the
falsifier named.

---

## BRAIN HUNTER — session 3 (2026-08-13, dedicated daily organ)

**MINE GATE re-read live** (`scripts/mine_gate.py`, not the header alone): **BACKLOG-CLEAR**, 19/19
carded finds disposed, mining authorised. **PRIOR STATE:** s2's 6-item next-ground chain inherited
intact; R0437 (grouping-map consumer wiring) verified live and correctly SCHEDULED 08-18 — owed by
the alpha org, not this seat.


**§33 dispositions (2026-08-18, owed-work batch3 — items above, in order):**
- Kaggle G-Research post-mortems: [§33: screened] — resolved to depth (OP-068, WS-012, R0577)
- NP forum-2 batch (147526/112425/4851), first copy: [§33: screened] — closed by 7c26b766 2026-08-18 (112425+147526 EXHAUSTED, 4851 surveyed; R0616 handoff)
- NP forum-2 batch, close copy: [§33: n/a -> same disposition as above]
- Kaggle NOTEBOOK layer via OP-068: [§33: deferred(2026-08-25)]
- Numerai post-mortems + cards 27/28 + Wilmott: [§33: deferred(2026-08-19)] — cards owed 08-19; Wilmott killed(walled) per session E close
### THE FIRST THING THIS RUN DID WAS REFUTE ITS OWN PREVIOUS RUN

**s2's video verdict was wrong and is now retracted in place** (see the red block at the s2 note
above). s2 graded the desk fetcher **INERT DESK-WIDE** and ledgered R0527 on that premise. Measured
this morning: `api.piped.private.coffee` **serves a video with 6 subtitle tracks in the same minute**
that 15 of 16 others return HTTP 500 — and those 500 bodies carry **YouTube's own
`SignInConfirmNotBotException … LOGIN_REQUIRED`**. **A proxy relaying an upstream wall is not a proxy
that is down.** **R0527 REJECTED**; acting on it would have sent an engineer to replace four working
proxies. The genuine defect is already live and better-diagnosed as **R0592** (BR seat).

**The trigger was a sibling seat's memory, not a fence** — RU s3 recorded "the fetcher WORKS, the
08-12 verdict was refuted on the first call". A capability graded from a **single-instant probe of N
rotating endpoints** is a measurement with no repeat; ask *does the rotation succeed*, never *are all
N up*.

### VIDEO: 0 fetched, 13 SOURCE-LOCKED — and the blocked FRACTION is now measured

**BR s3 left an explicit ask in `video_locked_log.md`: "measure the blocked FRACTION on a real target
list, never assert a blocked CLASS." The BRAIN lecture corpus is that list** — one channel, one
language, one publisher, **13 videos over a 45x view range**.

**15/16 blocked = 93.75%.** Blocked at **5,269,269 views**; blocked at **5,374 views**; passing only
at ~1.6bn. **RU s3's "keyed to video popularity" is REFUTED and BR s3's "not view-count-shaped" is
CONFIRMED** — this panel reaches 10x higher up the view range than either seat's could, which is the
only reason it separates the two stories. Channel-specificity was the next guess and is dead too (two
non-WorldQuant control channels blocked). **Instance cache residency** is the sole surviving
hypothesis and remains **UNMEASURED as a cause** — real answer, not a hedge (L1.28a). Full table and
the §13 note on why `yt-dlp`-with-cookies is *not* proposed: `video_locked_log.md`.

### GROUND OPENED, and the two-exhaustions rule applied

- **`rocky-d/wqb` v0.2.5 (MIT, 272★)** — **EXHAUSTED at API-SURFACE level.** `wqb_urls.py`,
  `__init__.py`, `filter_range.py` and the `filter_alphas_limited` / `simulate` / `check` paths of
  `wqb_session.py` (43,330 B) read. **NOT claimed:** the async retry/concurrency machinery
  (`retry`, `concurrent_*`), which is HTTP plumbing carrying no platform semantics. **Honest
  limitation recorded so nobody re-opens it:** every enum (`Neutralization`, `NanHandling`,
  `Pasteurization`, `UnitHandling`, `Region`, `Universe`) is aliased to **`Any`** — the library gives
  the *namespace and exact API paths*, never the *value sets*.
- **`CrisperX/50_WorldQuant_Alpha_Examples_for_Alphathon` (85★, NO LICENCE ⇒ all-rights-reserved)** —
  **EXHAUSTED** (2 files, both read; `alpha50.csv` measured in full). Mechanism and aggregate
  statistics extracted; **no formula or code copied into this repo.**
- **§13 HELD, unchanged:** no credential was held, sought or used, and **no call was made to
  `api.worldquantbrain.com`** — `wqb` is an authenticated client and this seat does not touch
  authenticated surfaces. Reading the client's source is public; running it is not.

### THE TWO FINDS

**OP-083 — the desk imported BRAIN's THRESHOLDS (which do not port) and missed its RATIOS (which
do).** `brain_calibration.py` was built from a *webinar transcript*, and a transcript states
thresholds; an *API* states the measurement namespace. Four BRAIN metrics are **dimensionless ratios
of two like-measured quantities**, so every convention difference that module correctly warns about
(annualisation, cost base, return definition, periodicity) **cancels**: `os.osISSharpeRatio`
(**ABSENT**), `os.sharpe60/125/250/500` (**ABSENT**), `os.preCloseSharpe*` (**PARTIAL** —
`earnability.phase_sensitivity` covers funding-settlement binning, not decision-timestamp
sensitivity), `is.prodCorrelation` (**HALF** — the self-correlation cap was imported, the production
half was not). **The transferable rule, well past this platform: a threshold is asset-class-bound and
does not travel; a ratio of two like-measured quantities is unit-free and travels intact.**
**[§33: wired -> `search_operator_library.md` OP-083; ledgered R0601 + R0602]**

**OP-084 — measured: the independence came from the DATA, not the MATH.** Over all 50 rows of a
worked low-correlation portfolio: **49 distinct data fields, 8 operator tokens, 48/50
single-operator expressions**, median expression depth **1**. Diversity of *expression* contributed
essentially nothing; diversity of *underlying field* contributed everything. It corroborates the
desk's most expensive lesson from a different market, institution and asset class (129 mechanisms,
all price-derived, all failed). **This re-ranks this organ's own brief: operators are the low-yield
axis, fields are the high-yield one.** Separately measured and robust to the source being
untrustworthy: **Sharpe min = median = 1.2500, 100% below 1.30, 26/50 exactly at the platform's
stated 1.25 target** — total threshold-hugging, and if the numbers were fabricated they were
fabricated *to hug the bar*, which reveals the same selection norm either way.
**[§33: wired -> `search_operator_library.md` OP-084]**

### §33 DISPOSITIONS — every find routed in-run

- BRAIN metric namespace / portable-ratio rule **[§33: wired -> `docs/research/search_operator_library.md` OP-083]**
- 50-alpha population measurement **[§33: wired -> `docs/research/search_operator_library.md` OP-084]**
- 13 source-locked lecture ids + 93.75% blocked fraction **[§33: wired -> `docs/research/video_locked_log.md`]**
- s2's refuted video verdict **[§33: killed -> R0527 REJECTED, retraction written in place]**
- `ts_zscore`, `ts_av_diff`, `ts_corr`, `group_rank` confirmed as real platform operators **[§33: screened -> OP-083 footer]**

**NO card added to `prospector_watchlist.md`** (5/5 slots used; nothing here earns a displacement).
**No new tradeable mechanism is claimed this run** — both finds are methodological, and OP-084's
whole point is that the desk's binding constraint is field count, which is already carded and already
has its consumer wiring owed at R0437.

### NEXT UN-EXHAUSTED GROUND, in order, for session 4 (L1.35/L1.40 — named before closing)

1. **The reimplementation/fork layer, 8 repos still untriaged** — s2's item 2, only CrisperX taken.
   Hunt the **six operators the desk lacks**; `ts_zscore` is now confirmed real and in live use, so
   it is the one with a demonstrated caller. `zhutoutoutousan/worldquant-miner` (**Apache-2.0**,
   723★) is the licence-cleanest of them and its tree did not resolve on `main` — **check `master`**
   (this seat has been caught by a wrong default branch twice now).
2. **`yli188/WorldQuant_alpha101_code` (846★)** — the most-starred artifact on this entire ground and
   **never opened by any session**. No licence, so mechanism-only.
3. **BRAIN lecture corpus** — **re-grade the blocker: it is SOURCE-walled, not tool-blocked.** Do not
   re-attempt through Piped; the only routes that could open it are authenticated egress (§13 bar,
   see the video log) or a text mirror. **Hunt the text mirror first** — course transcripts,
   community lecture notes, and the IQC webinar series are all candidate mirrors of the same content.
4. **`jglazar/notes` tree walk** — carried unresolved from s2; both guessed paths 404'd, so walk the
   tree via the API rather than guessing a third time.
5. **IQC 2026 webinar series** — recurring weekly; establish whether materials are published outside
   the login wall. **The standing argument for a daily organ: the platform keeps publishing.**
6. **BRAIN community discussion of FAILED approaches** — s1 item 6, still the most neglected vein and
   still the highest-yield bite either previous session took.

**A NULL WAS NOT AVAILABLE THIS RUN and none is claimed.** Ground remains wide open: 8 untriaged
repos, the most-starred artifact on the ground unopened, a source-walled official lecture corpus with
its text-mirror route untried, and a recurring webinar series. **Seat-exhaustion is false here as
everywhere.**

---


**§33 dispositions (2026-08-18, owed-work batch3 — items above, in order):**
- Reimplementation/fork layer (8 repos untriaged): [§33: deferred(2026-08-25)] — next BRAIN session; no s4 evidence
- yli188/WorldQuant_alpha101_code: [§33: deferred(2026-08-25)]
- BRAIN lecture corpus text-mirror hunt: [§33: deferred(2026-08-25)]
- jglazar/notes tree walk via API: [§33: deferred(2026-08-25)]
- IQC 2026 webinar series: [§33: deferred(2026-08-25)]
- BRAIN community FAILED approaches: [§33: deferred(2026-08-25)]
### 2026-08-18 PROSPECTOR session (standing daily; brain seat, real egress) — IN PROGRESS (write-first note; updated as items resolve)
PRIOR STATE: both 08-12 sessions (brain seat + session G) closed cleanly — no dead run to
resurrect. MINE GATE at start: BACKLOG-CLEAR (19/19 disposed; re-read live, header confirmed).
RESUME RULE 1 (verify queue) SATISFIED BY OWNERSHIP CHECK, not poaching: all 6 listed verify
items are done or owned in-flight — 中文 corpus MINED 2026-08-18 (free-data seat, card 23 grade);
Foreign AI-quant systems MINED (Qlib 08-11, vnpy.alpha 08-13, JP/KR half 08-18 litminer run 8,
card 24 grade); BIS 1087 wired + carry-liq screen executed (litminer run 8, commit b35e0b3b);
KR venue-state + stablecoin-run = KR/brain seats; grouping map = R0437 (alpha org, sched 08-18).
Backlog listing is STALE for cards 23/24 — noted for the backlog tool owner below.
GENERATION PRIORS read: favour data_axis_watchlist.md (0.489 conv), starve: none.
STRATEGY COVERAGE read: 0 unhunted, 6 THIN (ATTENTION-SENTIMENT, MARKET-MAKING-EXECUTION,
EVENT-AND-CALENDAR, LEVEL-REACTION, STATISTICAL-ARBITRAGE, LEAD-LAG) — this run's threads bias
EVENT-AND-CALENDAR (147526 new-issue premium) + Records/process.
ITEMS THIS RUN (bounded per completion contract; oldest debt first):
1. NP forum-2 (TRADING) thread batch, carried since 08-12: 112425 "Price patterns", 147526
   "corporate bond new issue premium" (translate: listing/unlock premium mechanics —
   EVENT-AND-CALENDAR THIN), 4851 "Renaissance Watch" — via CDX per-thread captures,
   reply-chain ≥2, claim EXHAUSTED per-thread.
2. RECORDS FAMILY FIRST TOUCH (search-space expansion ≥25%): Numerai forum post-mortems
   (tournament/Signals/crypto burn threads) + Kaggle G-Research crypto post-mortems — the two
   never-touched Records grounds named 08-12.
3. (stretch) NP forum-1 2013 snapshots for post-2012 titles + f12 147620 Kelly / 147696
   Dynamic Correlation.
SIDE-CHECKS (recorded, not items): cards 27/28 DECIDE status (ruling owed 08-19 — verify
landed/pending, escalate only if overdue); Wilmott robots re-probe (WALLED ×2); watchlist
trigger probes: ETHDVOL futures listed? (dvol card), card 31/R0462 COIN-M backfill landed?
(coinm card), POC/SFD screens run? (research_memory).
STEP -1 DIVERGENT QUERIES (3 a different searcher would run; ≥2 spent): (a) Numerai forum
"burn"/"what went wrong" staking post-mortems — a PARTICIPANT's query, not a mechanism-hunter's;
(b) Kaggle G-Research winners' "what didn't work" sections — the negative-result layer of
solution write-ups; (c) era-journalist chain on 4851: Medallion basket-options/leverage
structure via public record rather than forum lore.
STATUS: items 1-3 OPEN.
RESOLVED 1 (NP forum-2 TRADING batch, carried since 08-12 — all three threads closed):
- **112425 "Price patterns" EXHAUSTED** (6/6 archived pages, 2008→2014; page-3 final state lost
  to the capture lattice — the sole 2011-01 capture predates its fill; named, not papered over).
  Yield: QIM capacity-decay case study end-to-end (VERIFIED-grade contemporaneous tape: founding
  capacity belief $500M → 2010 hard-close letter claiming $6-10B → FDAXHunter's measured
  impact-cost refutation → "flat since 2009" 2013 verdict → 2013 down year + HFT-impact
  suspicion); the operator's OWN May-2010 attribution that its systematic drawdown-reduction
  policy subtracted value (lowest exposure in the recovery, highest in the worst stretch) —
  the L1.51 clamp-cost law observed in the wild, priced by the payer; 2013 GP commoditization
  testimony ("everyone and his brother… cheap genetic programming engines") — free crowding
  context for the desk's own 420/0 + DSR discipline; Meyer-Packard floating-hypercubes
  "didn't pan out for Prediction Company" scuttlebutt. NO new mechanism (candlestick/pattern
  class = price-only daily, desk-dead). Routed: rm-…-e701c2.
- **147526 "corporate bond new issue premium" EXHAUSTED** (3/3 posts, sole capture 2011-02).
  Yield: THE CARD — new issues reprice the EXISTING comparable curve → listing_comparables_
  repricing (novelty 0.802, EV QUEUE 0.0038 untagged / REJECT 0.0013 crowded_known, BOTH
  reported; card in prospector_watchlist.md, screen handoff = R0616, owner alpha-screening,
  due 2026-09-01; dvol displaced to rm-…-7ef2c7 with trigger preserved, probed unfired live —
  Deribit ETH DVOL futures: NONE).
- **4851 "Renaissance Watch" SURVEYED** (pages 1/17/18 read of 27 archived, 45 total). Yield:
  Aug-2007 quake contemporaneous tape (RIEF −8.7%, Simons deleveraging-wave letter, AQR −13%,
  Tykhe −19%, kubrick's factor-vs-technical cross-section read); GLOBEX confirm-parsing
  counterparty-identity leak + protocol reverse-engineering as standard HFT practice (2
  practitioners) — era instance of protocol-metadata flow attribution; modern analog ALREADY
  CATALOGUED (universe map row 54 Hyperliquid position transparency) — enrichment, no new axis.
  NAMED RESIDUAL: pages ~38-40 (2014 Senate-PSI basket-options era) + 44-45 (2018+); low
  mechanism density measured (3-page sample: news-watch genre) — residual is optional ground,
  not owed ground.
RESOLVED 2 (RECORDS FAMILY FIRST TOUCH — Numerai forum ground OPENED; search-space expansion
quota spent here): robots clean (no by-name refusal — checked, the KR lesson), Discourse JSON
route works. 3 threads mined to FULL depth: **7914 "Reducing Numerai Crypto Payouts" (5/5
posts)** — the operator's own 2025-01 statement that crypto-tournament participants scored
corr/MMC so far above the equities tournaments that payouts were cut to 0xCORR+1xMMC
("far more profitable for users… unsustainable"), while the fund does NOT trade crypto —
scoreboard-grade, participant-pool-controlled evidence that the crypto cross-section carries
MORE harvestable signal than equities. CONVERGENCE with the desk's own dispersion measurement
(OLMAR graveyard row) — two independent instances now; cite both, never the row alone
[§33: wired -> rm-20260818T200154-449f69]. **8197 Spectra dataset (1/1)** — a 300-token universe
filtered FOR shortability reaches only ~35% Hyperliquid short coverage: named structural
truncation of crypto L/S short legs that the desk's Binance-perp universe does NOT share (perps
are short-symmetric); UCID join key noted; the 22 new features are ranked/binned 20D/60D TA =
price-derived class, desk-dead — no card [§33: wired -> same rm row]. **8235 LLM-RL code-gen
post-mortem (1/1)** — one worked example in the generation prompt = 96% example-echo across 775
experiments; measured corroboration of the L1.31 rotation premise + a free harness checklist
(43% compile-failure, 34pp from undeclared schema) [§33: wired -> improvement_inbox.md item 1].
ITEM 3 (stretch) NOT TAKEN — bounded scope; rolls to next-ground intact.
SIDE-CHECKS RESOLVED: cards 27/28 DECIDE — NOT landed (no ruling in principal_replies /
PRINCIPAL_ACTION / ledger), due 2026-08-19, NOT overdue today; the §33 deferral expiry
auto-returns both to backlog tomorrow, so the chase is mechanical — next session verifies
landed-or-escalates. Wilmott robots: 403 both hosts, BOTH egress-relevant paths — WALLED ×3,
still not refusal-by-name; re-probe on a different day/egress. ETHDVOL: NONE listed (Deribit,
live probe). R0462 due 08-27 (coinm trigger pending). BACKLOG-STALENESS DEFECT verified twice
and routed: source_backlog_next.py still lists MINED cards 23/24 as pending-verify →
improvement_inbox item 2 + ledger R0617 (fix owner = unfrozen engineering seat; this seat is
research-frozen).
FAMILIES THIS RUN: Forums-legacy (NP, deep), Records (Numerai — NEVER-TOUCHED ground opened;
≥40% least-recently-covered bias satisfied), AI/HF documentation (8235). Non-English: indirect
only this run (KR 가두리 era lore grounds the card's phase-1 mechanism; CN/JP/KR verify items
ownership-checked, not poached) — named honestly, next-ground carries the CN/KR grounds.
VIDEO: 0 fetched, 0 locked — no video grounds hit this run.
DEPTH LINE (per the depth mandate): 112425 = EXHAUSTED 6/6 archived pages; 147526 = EXHAUSTED
3/3 posts; 4851 = SURVEYED 3/27 archived pages (sampled at its highest-value era; measured low
mechanism density; residual OPTIONAL ground, named); Numerai 7914/8197/8235 = complete trees
(5/5, 1/1, 1/1). What depth surfaced that the surface never showed: the run's ONE card came from
a 1-post account's reply in the SMALLEST thread taken (147526 #2, Lucy — the comparables
repricing channel), and the QIM capacity refutation lived on page 2+ (FDAXHunter's measured
impact-cost post) — invisible from every title.
STEP -1 ACCOUNTING: divergent query (a) Numerai burn/post-mortem participant-query — SPENT
(surfaced the methodology-thread set + 8235); (c) 4851 PSI-era journalist chain — PARTIALLY
spent (pages triaged toward the era, residual named); (b) Kaggle negative-result layer — ROLLED
to next-ground with its route named (winners' GitHub/arXiv mirrors; the Kaggle forum SPA wall is
already on record, do not re-probe it).
NEXT UN-EXHAUSTED GROUND, in order (L1.35 — named before closing):
1. Numerai continuation: classic methodology threads (899 feature-exposure, 3170 López de Prado
   feature selection, 151 performance stationarity) + crypto-tournament threads (8212
   USD-staking, 7916 staking-alignment) + jefferythewind's run-2 verdict when published.
2. Kaggle G-Research crypto post-mortems via winners' GitHub/arXiv write-ups (mirror layer, not
   the SPA wall).
3. NP forum-1 2013 snapshots (post-2012 titles) + f12 147620 Kelly + 147696 Dynamic Correlation.
4. 4851 optional residual: pages ~38-40 (2014 Senate-PSI basket-options era) + 44-45 (2018+).
5. Cards 27/28 DECIDE follow-through (due 08-19): verify landed or ESCALATE (deferral expiry
   returns them to backlog mechanically).
6. Wilmott re-probe (WALLED ×3).
STATUS: ITEMS 1-2 RESOLVED TO DEPTH, item 3 rolled. Run closed cleanly 2026-08-18 (write-first
note, bounded scope, 1 QUEUE card with screen handoff R0616, 1 defect ledgered R0617, 2 inbox
items, 4 research-memory rows, watchlist reviewed 5/5 with one displacement, cadence stamped,
honest zeros: 0 video, Wilmott walled, no new axis).
PUSH RECORD (sanctioned path, recorded per EN-s4/free-data-0818 protocol): pre-push gate RED on
the STANDING recorder ruff-lint failure (R0611, owed by an unfrozen seat, due 08-19) — collect ok,
mypy ok, my 3 commits verified docs/json-only (zero .py) → pushed --no-verify; push verified
landed (HEAD == origin == 5addbfe9).

### 2026-08-19 session I (EN frontier miner) — IN PROGRESS (write-first note; updated as items resolve)

PRIOR STATE READ (resume rule, not restart): 08-18 EN session closed cleanly (Numerai OPENED:
7914/8197/8235 complete trees; R0616 screen handoff, R0617 ledgered; push landed 5addbfe9).
MINE GATE re-read live this run (`scripts/mine_gate.py`, not the header alone): **CONVERT-FIRST,
1 owed (T3): card 28 bitbank** — the `deferred(2026-08-19)` legitimacy DECISION matured today.
`source_backlog_next.py` verify-queue re-read: same 6 as 08-13/08-18, owned in-flight elsewhere
(KR/CN/brain seats) — re-measured, not inherited. DECIDE queue: bitbank (mine, owed today) +
Glassnode/CryptoQuant vendor-replacement (brain-owed policy item, not this seat's).

ITEMS THIS RUN (bounded per completion contract; §33 CONVERT-FIRST order):
1. **§33 DRAIN (T3, the one owed item): card 28 bitbank §13 scope DECISION.** The licence READ is
   done (R0310, 08-12); owed is the ruling on the site-footer 免責事項 vs the `public.bitbank.cc`
   API. Plan: fetch the decisive evidence the 08-12 read named but did not pull — official
   `bitbankinc` SDK licences (GitHub API `license` field), the support-KB article body
   (360019410033), any API-terms surface — then WRITE THE VERDICT on the card with named residual
   + kill/re-entry condition. If LEGITIMATE: minimal lawful backfill into data/ with the
   2017-02-14 true-start guard as the §33 backing artifact; ledger row for the standing collector
   (engine-seat build — this seat is research-frozen). If RESTRICTED: kill with mechanism +
   graveyard. STATUS: pending.
2. **Numerai continuation (next-ground #1 from 08-18):** methodology threads 899 (feature
   exposure), 3170 (López de Prado feature selection), 151 (performance stationarity) +
   crypto-tournament threads 8212 (USD-staking), 7916 (staking-alignment); jefferythewind run-2
   verdict if published. Reply-depth ≥2, PROCESS extraction, screen-on-discovery. STATUS: pending.
3. Only if 1–2 close: GMO card 27 gate-parse discrepancy (two cards carry `deferred(2026-08-19)`;
   the gate counts ONE owing — L1.61-shaped; verify which artifact is right) + Kaggle winners'
   mirror layer (GitHub/arXiv, not the SPA wall).

SIDE-CHECKS (recorded, not items): venue harvest standing; video — fetch anything video-shaped
and record the explicit zero (R0527 REJECTED 08-18: the rotation WORKS; a per-instance 500 is
upstream LOGIN_REQUIRED, not desk-death); push via sanctioned path only if gates are red on the
standing R0611 recorder lint (check whether 301843d2 already retired it before invoking that path).

STATUS: items 1–3 OPEN.

RESOLVED 1 (2026-08-19, §33 T3 drain — card 28 bitbank DECIDED + WIRED, plus one NEW AXIS out of
the hunt itself): **The §13 scope decision is MADE: LEGITIMATE** — not by re-weighing the 08-12
evidence but on NEW venue-conduct evidence one GitHub API call surfaced: the venue MIT-licenses
its own Public-API clients (python/node/java + MCP server), publishes TWO sample market-making
bots, runs an official Discord botter community (ビボラボ repo), and OFFICIALLY distributes
historical order-book data. A footer that banned commercial API use would make the venue's own
published MM bots a ToS breach. Kill/re-entry condition on card 28; residual named (no single
written grant; aggregate conduct). **WIRED SAME RUN: `data/bitbank_1day.jsonl`** — 100,885 rows,
all 62 pairs, 2017-02-14 → 2026-08-18, 620 keyless calls, phantom guard VALIDATED end-to-end
(btc_jpy dropped exactly the 43 phantom bars; true start 2017-02-14 as card 28 measured).
Measured new: daily bars **UTC-midnight aligned, NOT JST** (offset 0 on all 3,474 btc bars);
year-absent = **HTTP 404 + code 10000** (a non-200=failure fetcher misreads every pre-listing
year — L1.60 class, re-probed 5/5). **NEW AXIS (screen-on-discovery honoured): card 34 — bitbank
official historical L2 order-book snapshots** (200×2 levels ~2/min, BTC+XRP 2019-03-13→, S3,
venue-granted registration; NOT screenable until grant — R0620 owns the human step; mechanism
prior + sampling limit stated on card). Ledger: R0619 (forward refresher, engine seat, sched
08-26), R0620 (registration, sched 09-02), research_memory ×2. **MINE GATE RE-RUN: BACKLOG-CLEAR,
20/20 disposed, mining authorised.** LEDGER-RACE INCIDENT (recorded for the lesson file): my adds
were clobbered by a sibling whole-file write, my re-add then clobbered the SIBLING's probe-cap
re-anchor row, and a third writer reverted my dispose inside a 2-minute window — resolved by a
single-process 3-way reconcile (R0619/R0620/R0621) committed and verified from `git show HEAD:`
on attempt 1. The new half vs the 08-18 lesson: after ANY ledger add, verify the NEIGHBOR rows
survived, not only that yours landed.
[§33: wired -> data/bitbank_1day.jsonl]

STATUS: item 1 RESOLVED. Items 2–3 open.

RESOLVED 2 (Numerai continuation — next-ground #1 from 08-18, five threads to full depth):
methodology threads 899/3170/151 + crypto-tournament 8212/7916, every post of every thread read
(44+35+16+1+5, pagination completed via posts.json). YIELD: **2 pre-emptive falsifications
graveyarded** — `numerai_mda_feature_selection_gain` (the +0.5% claim is ~95% evaluation
leakage; jay1100's 3-arm measurement 0.7/0.5/0.025 proves fold-averaging DILUTES a leak, never
removes it) and `hyperparam_grid_uniqueness_as_signal_diversity` (39.6 quadrillion combos ≈ 1
effective bet; genuine independent convergence with OP-084 + the demeaning-floor lesson,
DERIVES-FROM: NONE checked both ways). **4 engine items → improvement_inbox** (leak-free
importance protocol w/ self-test; max-feature-exposure OOS-fragility diagnostic, 80-model
measurement; era-wise prediction-on-feature neutralization + mdo's clamped variant + taori's
helps-simple-hurts-advanced boundary; smart-sharpe |AR1| SE-inflation with the community's
negative-AR1 sign-bug fix). 8212 graded THIN honestly (tokenomics, no mechanism).
jefferythewind run-2 verdict **NOT YET PUBLISHED** (searched his latest posts; newest is
2026-04-24 governance) — carried, not padded.
[§33: killed -> docs/graveyard.md `numerai_mda_feature_selection_gain` + `hyperparam_grid_uniqueness_as_signal_diversity`]

RESOLVED 3 (item 3 side-check ESCALATED TO A FULL RESOLUTION — the GMO card's heading was
DESTROYED): the L1.61-shaped discrepancy (two cards dated 08-19, gate counts one) was not a
parse quirk — an 08-13 edit destroyed card 27's `### 27.` heading line, gluing its grade + §33
tag mid-paragraph into the KR venue-state card, where `_ITEM_RE` (heading-line-only) cannot see
it. **A matured T3 obligation sat invisible to mine_gate, source_backlog_next AND the
vanished-item detector for 6 days** (the tag TEXT survived, so nothing "vanished"). Heading
restored verbatim from 5361358; the obligation then DECIDED same run: **§13 RESTRICTED-PENDING-
CONSENT** — Art. 14(15) consent-required reuse + Art. 7(1) deemed assent, and the OP-087 conduct
check came back EMPTY for GMO (no org, no SDKs, no grant language) — clause + silence ≠ licence.
[§33: killed -> graveyard `jp_gmo_tick_archive_direct_ingest`], re-entry = written consent
(R0622, ops/principal, due 09-02). Substitution chain recorded: bitFlyer→GMO both licence-dead;
bitbank (wired today) + Tardis free tier are the surviving JP tape.

SESSION CLOSE 2026-08-19 (EN frontier miner s-I) — DEPTH LINE, VENUES, NEXT GROUND:
DEPTH: bitbank legitimacy = decided on NEW primary evidence (whole-org licence read via GitHub
API — 15 repos, 3 MIT API clients, 2 sample MM bots, botter-community + historical-data repos;
API host robots re-probed; support-KB re-fetch attempted, CF-walled, recorded not routed
around) + 620-call backfill with the phantom guard validated end-to-end; GMO = heading forensics
via 4-commit git bisect + org/conduct probe + archive-page read; Numerai = 5 complete trees,
reply-chains to full depth, refutation layers mined (the run's 2 graveyard entries BOTH came
from reply layers, not OPs — the depth mandate's point, again). Kaggle/NP grounds untouched this
run (bounded scope; carried).
VENUES DISCOVERED: 1 — bitbank's official historical-orderbook S3 distribution (card 34, via the
org listing; the practitioners' venue-harvest rule applied to a VENUE'S OWN org). VIDEO: hit 0,
fetched 0, locked 0 (no video-shaped artifact on any ground touched).
STRATEGY-FAMILY note: no new family hunted this run (conversion + methodology run); coverage
denominator unchanged.
NEXT UN-EXHAUSTED GROUND, in order (L1.35):
1. Numerai classic-tournament remainder: threads the 08-18 list named that today's batch did not
   reach (jefferythewind run-2 verdict when published; crypto-tournament operational threads).
2. Kaggle G-Research winners' mirror layer (GitHub/arXiv write-ups — NOT the SPA wall).
3. NP forum-1 2013 snapshots + f12 147620 Kelly + 147696 Dynamic Correlation (carried from 08-18).
4. 4851 optional residual (pages ~38-40, 44-45).
5. bitbank L2 S3 first-month screen — fires the day R0620's registration lands (screen-on-
   discovery obligation pre-registered on card 34).
6. Wilmott re-probe (WALLED ×3).
STATUS: **items 1-3 ALL RESOLVED to depth** (item 1: DECIDED+WIRED+new axis; item 2: 5 threads,
2 graveyard + 4 inbox + OP-087; item 3: heading restoration + GMO DECIDED+killed). Run closed
cleanly 2026-08-19. Honest zeros: 0 new mechanism cards (watchlist 5/5, nothing displaced), 0
video, 8212 THIN. Ledger races: 4 clobbers absorbed, 5-way reconcile verified from HEAD, lesson
L0166, root fix R0623.

---

## AR FRONTIER MINER — session 3 (2026-08-19) — IN PROGRESS (write-first note; updated as items resolve)

MINE GATE at start: BACKLOG-CLEAR (19/19 disposed; header authorised). PRIOR STATE read per
RESUME(2): s2 (08-13) closed with a 7-item next-ground list re-ordered by OP-075; owed-work
batch3 (08-18) batch-deferred all seven to 2026-08-25. Working the top of that list EARLY is
strictly better than the deferral date because items 1–2 feed R0193 (regulatory-event timeline
reconstruction) which is due 2026-08-24 — BEFORE the deferral matures. Verify-queue read per
RESUME(1): 7 pending, of which 3 are PHANTOM (F0002 class — resolved cards whose grade lines
lack the parser's terminal substrings; verified first-hand: card 24 `qlib-alpha158`+`vnpy-alpha-dsl`
present in operator library, card 27 `data/crypto_grouping_map.json` 27KB/4 maps, card 32 routed
rows present) and 4 are GENUINELY pending with work ledgered elsewhere (23→R0615 liq-archive
repair; 25→R0193 remaining legs; 26→KR screen owed; KR fiat-rail→R0299) — those four are
CORRECTLY served by the queue's conservative design and are not touched.

ITEMS THIS RUN (bounded per completion contract; worktree `qp-ar-s3`, branch
`claude/ar-miner-s3-20260819`, R0423 discipline):
1. BACKLOG HYGIENE (Tier-1 defect-closer; RESUME(1) duty): re-grade phantom cards 24/27/32 with
   parser-terminal vocabulary (`verified-clean`), content preserved; add the grade-vocabulary
   rule to the watchlist header so the trap stops recurring; route the silent fail-open on
   `[§33: wired]` cards to improvement_inbox.
2. VARA NOTICE BODIES (s2 next-ground #2; §13-clean per s2 robots read, re-verified this run):
   read enforcement + warning notice TEXTS; extract the reason taxonomy R0193's 5-class build
   needs. STATUS: **CLOSED — deferral converted 5 days early, [§33: wired ->
   data/vara_regulatory_events.json] (96KB).** Robots re-verified 200/zero-directives (now a
   Cloudflare content-signals preamble, comments only, NO Content-signal directive lines ⇒
   nothing restricted; dated observation). Via the Gatsby data layer (→ **OP-092**, new operator):
   21 dated POLICY circulars 2023-02→2026-06 (Travel Rule 02-24-2026, CARF, FATF lists, AML
   decree — the A–C-classifiable rows, hiding under News not Notices; s2 undersold this), 30 EN +
   1 AR-only notice BODIES 2022-11→2026-07, 37 structured enforcement rows, 38 unlicensed, 77-
   entity register (65/77 institutional-scoped; 58 BD / 14 exchange / 3 VA-derivatives). EN↔AR
   circulars mirror 21/21 — bilingual by construction, the AR edge was ENDPOINT knowledge.
   Major-exchange find: KuCoin & MEXC warning(2026-03-05)→fine(06-22/24) ~110d escalation pairs +
   TON foundation fine 2025-07-24 (the only Binance-tradeable subject) → **WS-019** (n=2, KCS/MX
   not desk-tradeable, AR-s1 power lesson binds: no card; promotion rides on R0193's cross-
   regulator union). Card 33 grade → verified-clean/wired.
3. ADGM ANNOUNCEMENT CORPUS (s2 next-ground #1): FIRST re-probe apex+www robots per OP-076 —
   policy read only; if §13 passes, mine the 1,109-URL dated sitemap for VASP/crypto/enforcement
   rows → R0193 second jurisdiction column. If robots stays unreadable, record UNMEASURED-POLICY
   and stop at the sitemap surface already held. STATUS: **CLOSED — [§33: wired ->
   data/adgm_regulatory_events.json] (277KB), new card 36.** §13 RESOLVED: apex 403 was the wrong
   host — `www.adgm.com/robots.txt` GET 200 text/plain, real policy, corpus paths NOT disallowed,
   sitemap advertised in robots (→ OP-076 ADDENDUM: per-host + per-method robots grading; VARA
   same day showed GET 200 vs HEAD 404). Sitemap = 5,302 URLs: 1,111 announcements + **3,848
   `/public-registers/fsra` pages s2 never saw — new ground, named unmined**. CLOCK MEASURED
   (L1.46): 728/1111 lastmods flattened onto 2024 bulk-migration stamps; `article:published_time`
   SURVIVES migration (control: 2021 event → 18/08/2021 preserved) and is day-first (validated:
   128 rows day>12, 0 rows month>12). Crawled all 230 crypto/enforcement-tagged pages politely
   (0.7s spacing, 230/230 ok, 0 failed) → dated titled event rows 2016-05-10→2026-08-11 incl.
   **Binance global licence under ADGM framework 2025-12-08**, staking framework
   proposal→final pair (2025-10-01→2026-04-29), FRT/stablecoin framework pair
   (2025-09-09→2025-11-03), TON DLT Foundation 2025-02-12, Coinbase tokenization hub 2026-08-13.
   881 untagged rows kept in-artifact as index (tagging is recall-unmeasured — stated on card).
STRETCH (arabsgate first touch): NOT REACHED — items 1–3 consumed the run; carried, stays #1
retail-layer item on the next-ground list below.

#### SESSION CLOSE 2026-08-19 (AR s3) — DEPTH LINE, VENUES, VIDEO, NEXT GROUND

DEPTH (per the depth mandate): item 1 = instrument-level (parser grammar read from
`libs/research/source_backlog.py` source, 3 artifacts behind phantom cards verified first-hand,
queue re-run measured 7→4); item 2 = **exhausted at corpus level** (VARA: every static-query
payload the site ships — register/notices/news/enforcement/unlicensed — parsed to rows; notice
BODIES read; §33-wired; NOT claimed: per-entity register sub-pages); item 3 = **corpus-indexed +
tagged-subset exhausted** (ADGM: all 5,302 sitemap URLs enumerated, all 230 tagged pages fetched
and dated; NOT claimed: 881 untagged bodies, 3,848 register pages). Zero reply-chains/forums this
run — the ground was institutional JSON/HTML, not threads; the retail-thread debt (arabsgate)
stays explicit and carried.
VENUES DISCOVERED: 1 — ADGM `/public-registers/fsra` page corpus (3,848 dated pages; found via
sitemap path-prefix enumeration, verdict RICH/unmined). VIDEO: 0 fetched, 0 locked — no
video-shaped artifact on any ground touched this run (explicit zero per the mandate).
STRATEGY-FAMILY note: no new family hunted (conversion + data-axis run); coverage denominator
unchanged.
OPERATORS CONTRIBUTED (charter s16): **OP-092** (JAMstack data layer defeats the SPA-shell false
null — Gatsby/Next/Nuxt table + per-region adaptation), **OP-076 ADDENDUM** (robots grading is
per-host AND per-method), watchlist header **grade-vocabulary rule** (terminal grades must carry
a parser-recognized substring).
NEXT UN-EXHAUSTED GROUND, in order (L1.35 — named before closing):
1. `arabsgate.com` thread layer — THIRD carry; the OP-075 thin-retail prediction is still a
   prediction, not a measurement. First item next run, before any institutional ground.
2. ADGM `/public-registers/fsra` 3,848 register pages — licence-grant panel (entry side) for the
   ADGM column; robots-allowed, enumerated, unread.
3. VARA per-entity register sub-pages (77 URLs in the register payload) — issue dates + licence
   conditions live there; closes the "createDate is not issue date" gap in card 33's artifact.
4. AR video comment layer (carried from s2) — comment trees are plain HTML, never attempted;
   rank by mechanism-keyword density (habr lesson).
5. Era-archaeology (carried from s1): dead GCC/Levant venue layer via Wayback — still UNSTARTED.
6. Sharia/fatwa cross-sectional test (carried from s2): 7 events × N assets design — unrun.
7. Remaining OP-076 UNMEASURED apexes: `arabictrader.com` / `rain.bh` / `cbb.gov.bh` — re-probe
   www + GET variants per the addendum before recording anything.

POST-CLOSE OPS NOTE (AR s3, 2026-08-19): the run's ONE defect was mine — commit 81627908 deleted
R0636 30 seconds after the ff-merge landed it: a concurrent whole-file ledger writer regressed the
WORKING copy between merge and `git add`, my HEAD-verify read only the committed blob, and the add
staged the stale image under my name (8th R0423-class ledger race). Repaired same-minute from
pinned 224a768c, R0636 restored + dispositioned scheduled(2026-08-26). Lesson **L0168**: before
committing a contended whole-file store, `git diff --staged` must show ONLY your intended delta —
HEAD-verify alone passes while you commit someone else's stale image.

---

## BRAIN HUNTER — session 4 (2026-08-19, dedicated daily organ)

**MINE GATE re-read live** (`scripts/mine_gate.py`, not the header alone — s3's rule): **BACKLOG-CLEAR**,
14/14 carded finds disposed, mining authorised. **BACKLOG (resume step 1):** `source_backlog_next.py`
= 3 pending technical verifications, **none BRAIN-owned** (stablecoin-run conditioning, KR venue-state,
BIS WP 1087 — the last already verified by litminer run 8, commit b35e0b3b); 1 policy item
(Glassnode/CryptoQuant) is principal-gated vendor spend. Routing recorded, not silence.
**PRIOR STATE:** s3's 6-item next-ground chain inherited intact and worked in order.
**Worktree:** own tree (`qp-brain-s4`) per R0423 — 8 recorded instances of a sibling sweeping another
session's staged work; the main checkout had 9 live siblings at session start.

### THE ITEM S3 NAMED FIRST PAID OFF, AND IT CLOSED S3'S OWN RECORDED LIMITATION

s3 predicted `zhutoutoutousan/worldquant-miner` would resolve on **`master`** ("this seat has been
caught by a wrong default branch twice now"). **Confirmed** — both target repos default to `master`.

**`generation_two/constants/operatorRAW.json` is the OPERATOR VALUE SET** (Apache-2.0, 724★, 192
forks, pushed 2026-02-22): **98 operators** with name, category, scope, level and semantics. s3 had
recorded honestly that `rocky-d/wqb` gives *"the namespace and exact API paths, never the value
sets"* — **this is the value set, and it arrived from the licence-cleanest repo on the ground.**

**MEASURED DESK COVERAGE — 5 of 98 defined in `libs/`, 67 absent, 26 ambiguous-not-counted**
(a *definition* search `^\s*def <name>\b`, never a mention search). **Reduce 14/14 absent,
Vector 4/4 absent, Group 8/10, Time Series 28/29.** Artifact: `data/brain_operator_catalogue.json`.

### THE FIND IS A DATA SHAPE, NOT 67 MISSING FUNCTIONS — OP-093

`vec_*` (4) + `reduce_*` (14) only make sense if a field holds a **vector per instrument-day**. The
platform ships a two-stage pipeline (`vector field → reduce → scalar → everything else`); **the desk's
pipeline has no first stage** — measured: `grep -rEn "skew|kurtosis"` over `libs/features/` and
`libs/alpha_factory/` returns **nothing**. And the desk's vectors are *denser than an equity
platform's*: `geckoterminal_trades.jsonl` carries per-trade **`tx_from` (wallet identity)**, which
equities have no analogue for at all.

**Sharpest single operator: `self_corr`** — `(D×N)` → `(D×N×N)` rolling pairwise correlation, which
`reduce_avg` collapses into *a per-symbol per-day "how correlated am I to the universe right now"*.
The desk's `cohort_independence.measure()` returns **one scalar for a whole cohort**, and
`crypto_grouping_map.json`'s `corr_cluster` is a **static** 2026-08-11 assignment. `self_corr` is the
operator that makes the desk's own blocking input *dynamic*. **[§33: wired -> search_operator_library.md OP-093 + data/brain_operator_catalogue.json]**

### THE SECOND FIND WAS THE CITATION, NOT THE CHAPTER — OP-094

`paper/chapters/crypto-trading-strategies.tex` presents a bars comparison (time 0.85 → CUSUM 1.28)
that is **`\cite{gradzki2025}` — attributed, not measured by that author**; its unattributed claims
("2–5% monthly" arbitrage) carry no evidence. **Take the citation, drop the chapter's numbers.**
Primary source verified via **Crossref, not the publisher wall**: Grądzki, Wójcik & Lessmann,
*Financial Innovation* **11:136 (2025-12-15)**, `10.1186/s40854-025-00866-w`, **CC BY 4.0** — tick-level
BTC/ETH Jan-2018→Jun-2023, CUSUM+Triple-Barrier beats time bars **after costs**; Transformer variants
(FEDformer, Autoformer) evaluated — a negative-results layer worth its own dig.
**[§33: wired -> search_operator_library.md OP-094]**

**INSTRUMENT FACT worth reusing:** `doi.org` → `link.springer.com` → `idp.springer.com/authorize`
(303), and the SpringerOpen host `jfin-swufe.springeropen.com` **301s back into the same loop**.
That is a **cookie/consent redirect on a CC-BY article**, not a paywall. **Do not grade a CC-BY
article WALLED from a redirect loop** — take the metadata/OA route (Crossref answered in one call).

### THE DESK-SIDE DEFECTS THIS SURFACED — both ledgered, both with named upward fixes

**R0638 — a self-blocking adoption trigger.** `adoption_queue.md` rules "build nothing until the
trigger fires"; its dollar/volume-bars row triggers on *"a bar-sampled (non-time-bar) alpha enters the
pipeline"*. **A bar-sampled alpha cannot exist before the bar sampler** — unreachable by construction,
the exclusion-cycle shape L1.45 names ("what is the path back?"). There is none. Measured: **zero**
CUSUM/dollar-bar/volume-bar/changepoint implementations repo-wide, while the same gap was
independently re-reported **three times** (`adoption_queue.md:13`, `20260805_s0:39`, `20260801_s3:48`
— the last being a *test fixture documenting a detector that was never built*). Triple Barrier, by
contrast, **already exists** (`libs/features/labels.py`): the desk built the labeling half and never
the sampling half. Weaker second instance named but not asserted equal: the frac-diff row.
**[§33: killed -> R0638 ledgered; the queue defect, not the research gap, is the finding]**

**R0637 — a write-only moat tape the utilisation meter cannot see.** `data/geckoterminal_trades.jsonl`:
**322,187 wallet-resolved signed DEX trades, 153MB, captured since 2026-08-12.** Repo-wide reference
audit: one WRITER, one build-standard registration, one enforcement-matrix citation, one file-*counting*
audit — **zero analytical readers**, and no glob reader reaches it (siblings all glob `*.jsonl.gz`;
this is plain `.jsonl`). **Second-order:** `moat_utilisation.inventory()` walks only
`data/moat/<venue>/<SYMBOL>/*.jsonl.gz`, so a flat file at `data/` root is in **neither the numerator
nor the denominator** — utilisation reads healthy because the unused asset was never counted (L1.57/
L1.60 shape). The enforcement matrix is **GREEN on L1.11, the moat law, citing an unmined file**, and
its own comment states the desk's reasoning: *"the one axis where waiting IS the loss — capture is
forward-only-unrecoverable."* **[§33: wired -> R0637 + data_axis_watchlist.md card 37]**

**AND I CLOSED THE VISIBILITY HALF IN-RUN (L1.39).** The tape was in **neither** `data_universe_map.json`
**nor** this watchlist — the two catalogues miners and the §33 generation priors actually read. A
collector registered in governance but absent from the map is invisible to exactly the organs whose
job is to mine it. **Axis card 37 written, measured first-hand** (not from the collector's claims):
8-day span live today, 68 pools, **93,241 distinct wallets**, buy/sell 169,555/152,632, volume median
$18.82 vs mean $1,336 (**71×**), **181 of 187 pool-day cells with n≥30**, richest cell skew **11.19**,
p90/p50 17.6×. **Explicitly NOT claimed:** under L1.62 the panel's cross-sectional denominator is
unmeasured, so **nothing there is powered and nothing is a candidate.**

### HONEST NULLS — recorded so nobody re-spends

- **Polymarket subtree: DUPLICATE, not re-carded.** `polymarket_core` uses
  `gamma-api.polymarket.com/markets` unauthenticated — but `libs/data/prediction_markets.py:18`
  **already holds that exact endpoint**, and axis card 30 already graveyards the OpenMarket corpus
  with a strong permanent mechanism. Novelty gate did its job; re-carding would burn multiplicity
  budget twice. Its `FactorEngine` is hand-weighted heuristics with hardcoded normalisers — **a
  parameter set is not a mechanism**, so nothing is carded from it. **[§33: killed -> duplicate of card 30 + prediction_markets.py]**
- **The BRAIN data-field catalogue remains §13-walled.** `data_field_fetcher.py` is an *authenticated*
  client and the repo commits **no cached field dump** (tree scanned for `constants/`/`cache`).
  Reading the client's source is public; running it is not. **No credential was held, sought or used;
  no call was made to `api.worldquantbrain.com`.** OP-084's high-yield axis stays behind the wall —
  named, not breached.
- **R0437 IS OVERDUE** (status `scheduled`, due **2026-08-18**, `commit: None`) — this seat's own
  blocking input, owed by the alpha org, not fixable from a research-frozen seat. Mechanical chase
  recorded. New evidence for its owner: the map unlocks **more than R0437 assumed** — 8 of 10 GROUP
  operators are absent, not 2.

### THE TWO EXHAUSTIONS, applied honestly

**SECTION-EXHAUSTED (claimed, dated — do not re-surface-scan):**
- `generation_two/constants/operatorRAW.json` — **EXHAUSTED**, all 98 entries parsed and catalogued.
- `polymarket/polymarket_core/alpha/factors.py` + `adapters/polymarket_http_adapter.py` — **EXHAUSTED**, both read in full.
- `paper/main.tex` bibliography — **EXHAUSTED**, all 7 entries read.

**EXPLICITLY NOT EXHAUSTED — read the section map, not the sections.** `crypto-trading-strategies.tex`:
I read the section map, Empirical Results, Key Findings and Summary. **UNREAD: Information-Driven Bars
implementation (L31–255), Triple Barrier (255–355), Bybit (355–485), Arbitrage — remix/cross-exchange/
ETF (485–770), and Low-Liquidity Crypto Lottery / scam-token detection (770–849)**, that last being
**§42 ground** (too small for funds) and the most likely mechanism vein in the chapter.

**UNTOUCHED IN THIS REPO:** `generation_one` (416 files), `generation_two` (**104 of 106**),
`stone_age` (36, incl. `alpha_generator.py`, `improved_alpha_expression_miner.py`, `machine_lib.py` 41KB),
`tradr-platform` (84), `mini-quant` (9), `paper-zh` (13 — the **Chinese** edition, L1.34 class 5),
**10 of 11 paper chapters**, and the **192-fork layer**. 22MB total, of which ~5,215 blobs are a
vendored Dify copy (noise, named so nobody re-triages it).

**VIDEO: 0 fetched, 0 locked** — no video route attempted this run; s3's finding stands unchanged
(the BRAIN lecture corpus is **SOURCE-walled at 93.75%**, not tool-blocked; the text-mirror route
remains untried and is carried below).

**VENUE DISCOVERY (standing obligation):** *Financial Innovation* (`jfin-swufe.springeropen.com`,
SpringerOpen, fully OA/CC BY) — an open-access journal actively publishing crypto ML with costs
included; a recurring publisher worth a standing sweep rather than a one-off read. Reached by walking
repo → paper → bibliography, exactly the recursive-expansion chain.

**FAMILIES THIS RUN:** AI-quant structures / factor-mining frameworks (L1.34 class 4 — the dominant
family), academic literature + negative-results layer (class 8), prediction markets (null, duplicate).
Non-English: `paper-zh` **identified and named, not yet read** — carried below.

### NEXT UN-EXHAUSTED GROUND, in order, for session 5 (L1.35/L1.40 — named before closing)

1. **`crypto-trading-strategies.tex` L770–849, the Low-Liquidity Lottery / scam-token section** —
   §42 ground, the chapter's most likely mechanism vein, and the one section a crowd skips.
2. **`stone_age/python/pre_consultant/`** — `alpha_generator.py` (33KB),
   `improved_alpha_expression_miner.py`, `promising_alpha_miner.py`, `machine_lib.py` (41KB). The
   **generation-1 engine is where FAILED approaches are visible** (s1 item 6, still the most
   neglected vein and named highest-yield by two prior sessions).
3. **`generation_two/core/fast_expr_ast.py` + `expression_compiler.py` + `template_validator.py` (94KB)** —
   expression semantics and the *validator*, which encodes what the platform rejects.
4. **`paper-zh/` — the Chinese edition** (L1.34 class 5). Diff EN vs ZH: translated technical corpora
   routinely carry author asides the English edition drops.
5. **The Grądzki CC-BY paper itself, in full** — especially its **negative results** (Transformer
   architectures) and its CUSUM threshold calibration. OA, legally minable, cost-inclusive.
6. **`yli188/WorldQuant_alpha101_code` (851★)** — still the most-starred artifact on this ground and
   **still unopened by any session**. No licence ⇒ mechanism-only. Carried from s3 unstarted.
7. **The 192-fork layer + `jglazar/notes` tree walk via API** — carried from s2/s3, both unresolved.

**A NULL WAS NOT AVAILABLE THIS RUN and none is claimed.** Ground is wider open than when the session
started: one 22MB repo triaged, ~1.3% of its non-vendored blobs read, a CC-BY primary source opened,
the Chinese edition identified, and the fork layer untouched. **Seat-exhaustion is false here as
everywhere.**

**POST-CLOSE OPS NOTE — 9th R0423-class ledger race, and it manufactured a FALSE §33 defect (L0168).**
After the merge, `mine_gate` reported *"1 claim conversion with NO backing artifact — anchor-absent:
`recommendation_ledger.json` does not contain 'R0637'"*. It did contain it: `git show HEAD:` had
**637 rows incl. R0637+R0638** while the **working copy had 635** — a sibling's whole-file writer had
reverted it. Row-level diff first (the rule): **strict subset, the sibling added nothing**, so healing
from the pinned sha destroyed no one's work. It then **reverted AGAIN within ~60s of the first heal**
(mtime 08:27:25) — an active cadence, not a one-shot. Healing and gating in **one atomic command**
returned the true verdict: **BACKLOG-CLEAR, all 15 carded finds disposed.**
**The generalisable half:** a gate that reads the WORKING COPY does not merely *bury* failures in a
shared tree (the 2026-08-05 dirty-tree lesson) — it **manufactures** them against correctly-committed
work. Diff HEAD vs working copy for the gate's input before believing any gate verdict here. And
**fleeing to a fresh worktree does not escape it**: the worktree lacks gitignored `data/` and faked a
*larger* red (4 unbacked vs the true 0). Fix already ledgered upstream (R0623, flock); not re-rowed.
**One real defect of my own, caught by the gate and fixed:** card 37's first `[§33: wired -> ...]`
named *itself* and was not path-shaped. Corrected to the checked ``path `anchor`​`` form. A
self-referential disposition is a conversion claim backed by the claim.
