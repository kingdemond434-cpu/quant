# Prospector coverage map

_Seeded 2026-07-18; every family unvisited -- the first run biases per the rotation rule (>=40% of query budget to least-recently-covered). Log per session: family, date, queries spent, notable sources._

| Family | Last visited | Sessions | Notes |
|---|---|---|---|
| Podcasts/interviews | 2026-07-19 | 1 | 1 ep (Pavel Kycek, algoadvantage.substack.com) — CLAIM-grade, generic momentum+meanrev, no mechanism; 0 cards |
| YouTube/talks | never | 0 | untouched this session — priority next run |
| Forums (deep+legacy) | 2026-07-28 | 2 | s1 (07-25): Bitcointalk ERA-ARCHAEOLOGY opened — boards 8+78 mapped via OP-021; 6 topics mined to reply-depth → 3 graveyard entries + EN era lexicon. **s2 (07-28, session D): QUANTOPIAN ARCHIVE opened + mapped — 52,187 threads confirmed in Wayback (the whole forum); In&Out thread (108 posts) + its live-trade continuation (13) mined to EXHAUSTION → graveyard `era_inout_regime_rotation` (the community's own decomposition kills the crypto port), inbox #71, WS-003 4th confirmation, OP-034 + Quantopian-stratum lexicon, and the full named diaspora record (QC canonical / Quantiacs futures / self-host branch).** **s3 (2026-08-01, session E): OLMAR/OLPS cluster (20 captures, not the 9 logged) — 3 threads exhausted incl. the paper AUTHOR's in-thread admission; family killed on our own data AND the era's own kill reason refuted (crypto has 3.3–3.8× the dispersion of the sector ETFs OLMAR failed on). WILMOTT FIRST TOUCH DONE after a 4-session carry: 403 direct, 14,890 threads via Wayback, full board map recovered, verdict THIN-BUT-REAL (~5,868 mineable of 14,890; 68% Off-Topic/Politics noise).** EliteTrader/Nuclear Phynance still never touched |
| Social (X/Discord/Substack) | 2026-07-19 | 1 | 3 Substacks fetched (Maverick Quant, quantjourney [paywalled], algoadvantage) — 0 cards, mostly explainer/content-marketing grade |
| Code (GitHub/Kaggle) | 2026-07-19 | 1 | operator-named dig: ai_quant_trade, Qbot, QuantDinger, Vibe-Trading (READMEs+issues) + Hummingbot/Freqtrade issues — all infra/framework shells or equity factor zoos, 0 crypto-perp strategy logic; 0 cards but confirmed funding-arb is now commoditized into hummingbot's v2_funding_rate_arb.py (crowding evidence) |
| Academic (SSRN/arXiv) | never | 0 | untouched this session (RSRS is sell-side research, not SSRN/arXiv) — priority next run. **2026-08-01: touched only OBLIQUELY — the OLMAR paper (Li & Hoi ICML-2012 #168) was read THROUGH its forum thread, where its author answers questions the paper never addresses. Standing note: for any algorithm with a live practitioner community, the FORUM is a higher-yield read than the paper.** |
| Records (contests/CTA) | 2026-07-25 | 1 | partial, via forum route: Bitcointalk "Automated Trading Contest" (topic 261086, CryptoTrader.org rounds #1-#5) mined as a contest RECORD — produced the in-sample-vs-forward natural experiment graveyard entry. Kaggle G-Research + Numerai post-mortems still untouched |
| Non-English forums | 2026-07-26 | 2 | s1 (07-19): Chinese RSRS + funding-arb (CSDN/VeighNa/BigQuant/Zhihu/FMZ) + JP note.com — RSRS EV-killed, ML-funding-rate graveyard-matched. **s2 (07-26, CN frontier miner): axis #76 usdt-cny-otc-premium UN-PARKED — "no clean free API" REFUTED, 3 keyless routes, 591d history reconstructed (OP-031 CDX-replay of a capped JSON API), Stage-A screened 4/4 cells → no promotable edge but the catalogued mechanism's SIGN and MAGNITUDE priors both falsified. New: OP-031, OP-032, CN lexicon.** Era-archaeology (banzhuan/8btc/ChainNode/Tieba) still UNSTARTED — first item next run |
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
* VIDEO: direct transcript fetch is IP-BLOCKED from this VPS (RequestBlocked, tested
  07-18). Video-origin material is currently reached ONLY via text mirrors (show notes,
  transcript blogs, Substack writeups, community summaries). GAP #26 is the unlock and is
  principal-spend-gated; it pages ONLY once the coverage log proves video-locked mechanisms
  are a recurring binding blocker -- not yet demonstrated, because YouTube/talks has never
  been worked at all.
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
