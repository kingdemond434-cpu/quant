# Prospector coverage map

_Seeded 2026-07-18; every family unvisited -- the first run biases per the rotation rule (>=40% of query budget to least-recently-covered). Log per session: family, date, queries spent, notable sources._

| Family | Last visited | Sessions | Notes |
|---|---|---|---|
| Podcasts/interviews | 2026-07-19 | 1 | 1 ep (Pavel Kycek, algoadvantage.substack.com) — CLAIM-grade, generic momentum+meanrev, no mechanism; 0 cards |
| YouTube/talks | never | 0 | untouched this session — priority next run |
| Forums (deep+legacy) | 2026-07-28 | 2 | s1 (07-25): Bitcointalk ERA-ARCHAEOLOGY opened — boards 8+78 mapped via OP-021; 6 topics mined to reply-depth → 3 graveyard entries + EN era lexicon. **s2 (07-28, session D): QUANTOPIAN ARCHIVE opened + mapped — 52,187 threads confirmed in Wayback (the whole forum); In&Out thread (108 posts) + its live-trade continuation (13) mined to EXHAUSTION → graveyard `era_inout_regime_rotation` (the community's own decomposition kills the crypto port), inbox #71, WS-003 4th confirmation, OP-034 + Quantopian-stratum lexicon, and the full named diaspora record (QC canonical / Quantiacs futures / self-host branch).** Wilmott/EliteTrader/Nuclear Phynance still never touched |
| Social (X/Discord/Substack) | 2026-07-19 | 1 | 3 Substacks fetched (Maverick Quant, quantjourney [paywalled], algoadvantage) — 0 cards, mostly explainer/content-marketing grade |
| Code (GitHub/Kaggle) | 2026-07-19 | 1 | operator-named dig: ai_quant_trade, Qbot, QuantDinger, Vibe-Trading (READMEs+issues) + Hummingbot/Freqtrade issues — all infra/framework shells or equity factor zoos, 0 crypto-perp strategy logic; 0 cards but confirmed funding-arb is now commoditized into hummingbot's v2_funding_rate_arb.py (crowding evidence) |
| Academic (SSRN/arXiv) | never | 0 | untouched this session (RSRS is sell-side research, not SSRN/arXiv) — priority next run |
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
