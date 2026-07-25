# Prospector coverage map

_Seeded 2026-07-18; every family unvisited -- the first run biases per the rotation rule (>=40% of query budget to least-recently-covered). Log per session: family, date, queries spent, notable sources._

| Family | Last visited | Sessions | Notes |
|---|---|---|---|
| Podcasts/interviews | 2026-07-19 | 1 | 1 ep (Pavel Kycek, algoadvantage.substack.com) — CLAIM-grade, generic momentum+meanrev, no mechanism; 0 cards |
| YouTube/talks | never | 0 | untouched this session — priority next run |
| Forums (deep+legacy) | 2026-07-25 | 1 | EN frontier miner: Bitcointalk ERA-ARCHAEOLOGY opened — boards 8 (Trading Discussion, 18,640 topics, 2011-14 era = offsets 14480-18640) + 78 (Securities, 2,376 topics) mapped via OP-021; topics 261086/95760/171349/330209/339040/14466 mined to reply-depth → 3 graveyard entries + EN era lexicon. Wilmott/EliteTrader/Nuclear Phynance still never touched |
| Social (X/Discord/Substack) | 2026-07-19 | 1 | 3 Substacks fetched (Maverick Quant, quantjourney [paywalled], algoadvantage) — 0 cards, mostly explainer/content-marketing grade |
| Code (GitHub/Kaggle) | 2026-07-19 | 1 | operator-named dig: ai_quant_trade, Qbot, QuantDinger, Vibe-Trading (READMEs+issues) + Hummingbot/Freqtrade issues — all infra/framework shells or equity factor zoos, 0 crypto-perp strategy logic; 0 cards but confirmed funding-arb is now commoditized into hummingbot's v2_funding_rate_arb.py (crowding evidence) |
| Academic (SSRN/arXiv) | never | 0 | untouched this session (RSRS is sell-side research, not SSRN/arXiv) — priority next run |
| Records (contests/CTA) | 2026-07-25 | 1 | partial, via forum route: Bitcointalk "Automated Trading Contest" (topic 261086, CryptoTrader.org rounds #1-#5) mined as a contest RECORD — produced the in-sample-vs-forward natural experiment graveyard entry. Kaggle G-Research + Numerai post-mortems still untouched |
| Non-English forums | 2026-07-19 | 1 | Chinese (RSRS mechanism + funding-rate-arb forums: CSDN/VeighNa/BigQuant/Zhihu/FMZ) + Japanese (note.com solo arb blog) — 1 candidate mechanism found (RSRS), EV-killed; ML-funding-rate-prediction found and graveyard-matched |
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
