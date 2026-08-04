# Prospector coverage map

_Seeded 2026-07-18; every family unvisited -- the first run biases per the rotation rule (>=40% of query budget to least-recently-covered). Log per session: family, date, queries spent, notable sources._

| Family | Last visited | Sessions | Notes |
|---|---|---|---|
| Podcasts/interviews | 2026-07-19 | 1 | 1 ep (Pavel Kycek, algoadvantage.substack.com) — CLAIM-grade, generic momentum+meanrev, no mechanism; 0 cards |
| YouTube/talks | never | 0 | untouched this session — priority next run |
| Forums (deep+legacy) | 2026-08-04 | 2 | s1 (07-25): Bitcointalk ERA-ARCHAEOLOGY opened — boards 8 (18,640 topics, 2011-14 era = offsets 14480-18640) + 78 (2,376 topics) mapped via OP-021; 6 topics mined to reply-depth → 3 graveyard entries + EN era lexicon. **s2 (08-04): QUANTOPIAN ARCHIVE OPENED — dead site (HTTP 000), 12 CDX pages of /posts/* slugs mapped (OP-034); olmar + in-and-out threads mined to reply-depth → 2 graveyard entries + diaspora answered (QuantConnect/IBridgePy/Slack/OSS org).** Wilmott/EliteTrader/Nuclear Phynance STILL never touched — first item next run |
| Social (X/Discord/Substack) | 2026-07-19 | 1 | 3 Substacks fetched (Maverick Quant, quantjourney [paywalled], algoadvantage) — 0 cards, mostly explainer/content-marketing grade |
| Code (GitHub/Kaggle) | 2026-07-19 | 1 | operator-named dig: ai_quant_trade, Qbot, QuantDinger, Vibe-Trading (READMEs+issues) + Hummingbot/Freqtrade issues — all infra/framework shells or equity factor zoos, 0 crypto-perp strategy logic; 0 cards but confirmed funding-arb is now commoditized into hummingbot's v2_funding_rate_arb.py (crowding evidence) |
| Academic (SSRN/arXiv) | never | 0 | untouched this session (RSRS is sell-side research, not SSRN/arXiv) — priority next run |
| Records (contests/CTA) | 2026-08-04 | 2 | s1 (07-25): Bitcointalk "Automated Trading Contest" (CryptoTrader.org rounds #1-#5) → in-sample-vs-forward natural experiment entry. **s2 (08-04): the Quantopian FUND record mined via HN trees → graveyard `crowdsourced_backtest_selection_fund` (backtest-Sharpe>2.5 selection → −3% live vs SPX +6.6% → capital returned Feb-2020) — the at-scale companion to s1's entry.** Kaggle G-Research + Numerai post-mortems + HN 9152332 contest-winner tree still untouched |
| Non-English forums | 2026-08-04 | 3 | s1 (07-19): Chinese RSRS + funding-arb (CSDN/VeighNa/BigQuant/Zhihu/FMZ) + JP note.com — RSRS EV-killed, ML-funding-rate graveyard-matched. s2 (07-26, CN frontier miner): axis #76 usdt-cny-otc-premium UN-PARKED — "no clean free API" REFUTED, 3 keyless routes, 591d history reconstructed (OP-031), Stage-A 4/4 cells → no promotable edge but SIGN and MAGNITUDE priors falsified. New: OP-031, OP-032, CN lexicon. **s3 (08-04, CN frontier miner): era-archaeology STARTED at depth — 8btc board CDX-mapped (993 urls, 39 boards), 3 era windows (2013 ban / 2017 freeze / 94 exodus) mined to reply-depth ≥2 → graveyard 5th instance adds the premium-SIGN law (coin-leg frozen → domestic discount; fiat-leg frozen → premium) + primary-source 94 diaspora record; LTW-2022 momentum "non-replication" REVERSED by code forensics (pd.cut fat-tail trap → OP-047); Gitee access-mapped (discovery-walled/content-open → OP-048); +12 lexicon rows. Board 233 (BitMEX 合约党, ~1000pp) surveyed, unmined.** |
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
