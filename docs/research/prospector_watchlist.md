# Prospector Watchlist

_Seat memory: max 5 entries, each with the single trigger that would promote it to the gauntlet.
Overwritten each session per PROSPECTOR_SPEC. Session summaries are logged here chronologically;
this file also serves as the operator-visible "what did the digger find" record._

---

## SESSION SUMMARY — 2026-07-19T00:00:00+00:00 (first manual run, operator-triggered)

- **Queries used:** 12 / 12 web searches + 9 WebFetch deep-dives (WebFetch does not count against
  the search budget). Divergent-search-planning (STEP -1) queries run: direct-Chinese-language
  query (RSRS mechanism + funding-rate arb forums), direct-Japanese-language query (solo quant /
  perp arbitrage), and a cross-domain-transfer query (sports-betting closing-line-value → crypto
  perps) — a different searcher would have run these before touching English GitHub search;
  ~4/12 queries (33%) went to non-English or cross-domain angles.
- **Cards kept (survived graveyard + EV gate):** 0
- **Cards graveyard/EV-killed:** 2 candidate mechanisms decomposed and killed (RSRS timing
  factor; ML-predicted funding-rate timing). See DEAD ENDS below.
- **Highest-EV survivor:** none. Highest-EV candidate scored was `rsrs_crypto_perp_timing` at
  ev=0.0002 (REJECT, threshold 0.05) — see card below.
- **Honest verdict:** this is a ZERO-card session. The operator-named GitHub-maximal dig
  (Qbot, QuantDinger, Vibe-Trading, ai_quant_trade) turned up infrastructure/agent-framework
  shells and equity-market factor zoos, not crypto-perp strategy logic. No mechanism found this
  session cleared the graveyard + EV bar. Logged as a valid, creditable "nothing new" result per
  charter — not papered over.

### STEP 0 — Watchlist review
No prior watchlist exists (this is the Prospector's first run). Nothing to promote/hold/drop.

---

## DEAD ENDS (graveyard/EV-killed this session — logged so they are not re-mined)

1. **RSRS (阻力支撑相对强度 / Resistance-Support Relative Strength) timing factor**, ported to
   crypto perps. Source: Everbright Securities (光大证券) sell-side research, 技术择时系列报告
   ("Technical Timing Series"), original 2017 report + numerous reproductions (CSDN blogs,
   VeighNa quant-community forum, BigQuant wiki, 10jqka) — SEMI provenance (long public record,
   many independent reproductions, but all against CSI 300 2005–2017, no-cost backtest, no
   crypto-market reproduction found in this search). Mechanism: OLS-regress daily high vs. low
   over an ~18-day rolling window; the regression slope (β) is right-skew-standardized into a
   z-score used as a market-timing signal — structurally a support/resistance-slope trend
   indicator on OHLC price alone. **Graveyard cross-check:** not a literal match to any single
   graveyard entry, but structurally the same class as `breakout_donchian_majors` (REJECTED
   2026-07-18, ev 0.0002, `price_only`+`crowded_known`, "correlated ~0.6–0.7 with the
   already-deployed trend_30d TS-momentum sleeve") — a range/slope statistic on price alone,
   same failure mode expected. **EV gate:** `rsrs_crypto_perp_timing`, tags
   `price_only`+`crowded_known`, ev=0.0002, p_survive=0.0158 → REJECT (EV below threshold). One
   genuinely interesting fact: despite heavy reproduction within Chinese A-share quant circles
   (dozens of independent write-ups, forum optimization threads), **no crypto/Bitcoin-futures
   port was found** in this search — real obscurity in the crypto context, but the mechanism
   itself (price-only regression-slope trend) is exactly the class the graveyard has already
   killed twice (Donchian breakout, vol-regime trend overlay). Obscurity-in-one-market does not
   overcome being a crowded, orthogonality-poor price-only signal in the desk's own book.
   **Verdict: DISCARD** — not promoted, not watchlisted; would need a genuinely new
   non-price data axis to reopen.
2. **ML-predicted funding-rate direction/timing** (知乎 "基于机器学习的加密货币资金费率预测与
   套利策略"). CLAIM provenance (single Zhihu article, no code/backtest inspected, unbacked
   performance framing). Mechanism as described is functionally identical to the desk's own
   already-graveyarded `funding_momentum` (REJECTED: Sharpe −1.72, "dragged portfolio," costs
   killed the edge). **Graveyard cross-check: direct match — DISCARD**, no new evidence of
   regeneration presented.
3. (Non-mechanism, noted for completeness) Standard cash-and-carry spot/funding arbitrage
   surfaced repeatedly across CN forums (FMZ, CSDN), a Japanese solo-arbitrage blog (note.com),
   and is now literally shipped as `v2_funding_rate_arb.py` in Hummingbot's open-source
   strategy library (github.com/hummingbot/hummingbot) — confirms this mechanism is maximally
   commoditized (retail bot software ships it out of the box). This is the desk's own deployed
   sleeve; logged only as crowding evidence, not a new candidate.

## RSRS CARD (killed, logged for audit trail — not a watchlist entry)

1. **Source + provenance:** 光大证券 "阻力支撑相对强度（RSRS）择时" report series (2017) +
   community reproductions (CSDN, VeighNa forum, BigQuant wiki) — URLs opened:
   https://blog.csdn.net/vipsh2011/article/details/143028718 ,
   https://github.com/hugo2046/QuantsPlaybook ,
   https://www.vnpy.com/forum/topic/32993-rsrsze-shi-zhi-biao-de-150bei-ji-suan-jia-su .
   Grade: SEMI.
2. **Mechanism:** rolling-window OLS regression of daily high on low (~18d), slope β
   standardized (z-score over ~600d window, right-skew adjusted) into a timing signal; long
   when the standardized score is high (support strengthening relative to resistance), flat/
   short when low. Claimed low-lag leading indicator for bull/bear transitions.
3. **Counterparty + why they persist:** slow-moving technical/discretionary traders who read
   support/resistance visually rather than via regression; behavioral-persistence story, not a
   structural risk premium.
4. **Why the edge exists NOW:** unclear — heavily reproduced and optimized within Chinese
   A-share quant circles for years (a forum thread exists purely about a 150x speed-up of the
   calculation, i.e., people are actively running it at scale), which argues AGAINST edge
   persistence in its home market. No evidence found that it has crossed into crypto yet.
5. **Crypto-perp adaptation:** replace CSI 300 index OHLC with BTC/major-perp daily OHLC;
   free-computable off existing OHLC data, no new data axis required.
6. **Cheapest falsification:** free, historical — recompute RSRS z-score on existing BTC/ETH
   daily OHLC history already held, backtest as a standalone timing overlay.
7. **≤4-week observable:** N/A — did not clear the EV gate to warrant spending a test slot.
8. **Strongest argument it's spurious/decayed (written first):** it is a price-only,
   high/low-range regression-slope statistic — the same statistical family as Donchian breakout
   and vol-regime trend overlays already killed in this desk's own graveyard for being
   correlated 0.6–0.7 with the deployed trend_30d sleeve; nine years of Chinese-market
   reproduction and public optimization threads is evidence of crowding in its home market, and
   there is no structural reason a regression-slope-on-price statistic behaves differently in
   BTC than Donchian channels already tested and killed.

---

_No watchlist entries this session — nothing survived graveyard cross-check + EV gate at
QUEUE-verdict. Next session should prioritize the coverage families NOT touched this round:
Podcasts/interviews (beyond one Substack), YouTube/talks, Forums (deep+legacy — r/algotrading,
EliteTrader, Wilmott were not directly queried), Academic (SSRN/arXiv), Records
(contests/CTA), and AI/HF documentation — see prospector_coverage.md._

## 2026-08-04 — RU miner s1-on-branch: intraday volume-profile POC-retest structure (bits.media topic 2130528 + author's Habr series)
SOURCE: forum.bits.media section 110, topic 2130528 "Аукционная теория в коде" (author
cryptomaniac_dt, Jul-2026, full source on GitHub, cross-posted to Habr; second article in
series = supply/demand zone scoring, multi-TF, pinbar entry). Mined to reply depth (6 blocks).
1. **Mechanism (stated, code-backed):** 1h-bar state machine — consolidation windows (24/48/96
   bars) qualified by range ≤6·ATR ∧ ≤10% price ∧ net-move/range ≤0.35 ∧ POC concentration
   ≥2.5× uniform ∧ POC mid-range; then impulse validation (extreme ≥1× range within 12 bars);
   then POC retest with reaction-confirm/invalidation/expiry FSM; target = nearest strong
   (conc ≥ threshold) UNTESTED POC, min RR 1.5. Portfolio sim: fees+slip in R, stop-first
   tie-break (pessimistic), reported 148 trades PF 1.63 avgR 0.34 maxDD 18.3%; local-retest
   subclass carries the edge (n=92 WR 45.7% avgR 0.48 vs late-retest avgR 0.11).
2. **Novelty vs graveyard:** PASSES — zero volume-profile/POC/value-area entries in graveyard;
   family is volume-DISTRIBUTION-conditioned intraday structure, not a price derivative; the
   desk's "price-only alpha is dead" finding is explicitly a DAILY/slow-resolution result
   (blind-rediscovery memory), so 1h liquidity-anchored structure is an untested cell.
3. **Named defect (free falsification context):** the daily walk-forward coin selector (top-100
   mcap → 120d own-PnL backtest → trade coins with n≥3, PF≥1.0, sum_R>0, top-15 by sum_R) is
   SELECTION ON NOISE — 3-15-trade PF estimates across 100 coins guarantee ~half pass by luck;
   coin-level twin of graveyard `crowdsourced_backtest_selection_fund`. Any desk test must
   SEVER the selector from the engine and test the engine unconditionally.
4. **Evidence grade:** CLAIM (n=148 backtest, ~20 free config params, trial count unreported —
   effective multiplicity unknown; author honest about funding/depth/partial-fill gaps).
   Reply-layer prior: 20-yr practitioner null on extracting tradeable signal from volume
   profile ("делал 20 лет назад, нифига не понял что можно извлечь").
5. **Why edge might exist NOW:** volume-profile levels are watched by a large discretionary
   crowd (self-fulfilling liquidity pooling at POC) while the killed desk families are all
   price-derivative; 1h structure decays too fast for the daily-resolution tests already run.
   Why it might NOT: TradingView ships VP indicators to millions; BingX-affiliate content
   economics (execution venue choice smells sponsored) mean the genre optimizes for plausible
   narrative, not persistence.
6. **Cheapest falsification (Stage-A, owned data, no new axis):** compute rolling 96-bar POC +
   concentration on existing 1h BTC/ETH perp candles; screen distance-to-POC × concentration
   as conditioning feature via libs.research.axis_screen (artifact gate baked in). If the POC
   "magnet" prior is real, sign shows in residual IC after de-contamination; if not, graveyard
   with mechanism. ZERO promotion authority here — EV gate + pre-registration decide.
7. **≤4-week observable:** Stage-A screen verdict on owned candles (hours of work, free).
8. **Strongest spurious argument (written first):** every retest-entry system is structurally a
   pullback-in-trend filter; after de-contamination against momentum/vol regime the POC
   conditioning may add nothing — the 148-trade PF 1.63 is ~1.5-2σ from noise BEFORE counting
   the ~20-parameter search space, i.e. consistent with a tuned sample.

## 2026-08-04 — JP miner s1-on-branch: SFD-class venue-boundary cadence probe (throttled derived-reference games)
SOURCE: era-archaeology of the bitFlyer SFD game, 2018-2024 (graveyard `jp_sfd_boundary_game`
holds the dated lifecycle; primary sources Hoheto 2023-12 + Ros 2024-12, both practitioner
post-mortems with mechanism detail the English crowd never read).
1. **Mechanism (transferable, extracted from a dead game):** wherever a venue computes a
   threshold-triggered fee/transfer from a THROTTLED derived reference price (SFD price then;
   mark price, index price, premium index, liquidation trigger price now), two exploitable
   surfaces exist BY CONSTRUCTION: (a) the reference updates on the venue's internal cadence
   (SFD: ~1s jittery ticker, load-varying, uncorrelated with market activity) → a predictable
   propagation LAG between the input (spot/index components) and the boundary; the game is won
   by modeling the VENUE'S CLOCK; (b) reward/penalty asymmetries keyed to order TYPE (SFD paid
   new-builds only → standing-inventory accounting converted closes into rewarded opens).
2. **Novelty vs graveyard:** the SFD instance itself is dead at source (2024-03); the CLASS is
   novel — no graveyard entry tests a venue-cadence lag game. Distinct from barrier-rent
   (persistent premium = rent) and fee-artifact (backtest fee modeling) families.
3. **Where it would live today (concrete probe list, cheapest first):** (a) Binance/Bybit
   premium-index + mark-price update cadence vs their own component feeds — measurable from
   public websockets, keyless; (b) liquidation-trigger reads (mark-price cadence at cascade
   moments — pairs with the desk's liquidation listener); (c) funding interval switches
   8h→4h→2h on hot alts (muzineco documents these as discretionary + laggy); (d) dated-futures
   settlement-price windows (TWAP windows are published rules — boundary order-flow games).
4. **Evidence grade:** VERIFIED mechanism for the dead instance (two independent practitioner
   post-mortems + venue announcements); CLAIM for every live instance (nobody in the read
   sources demonstrates a live-venue lag game — which is exactly why it is worth a cheap probe
   before the crowd's tooling improves).
5. **Why edge might exist NOW:** mark/index cadences are infrastructure trivia no vendor sells
   and few measure; the SFD record proves venue clocks stay exploitable for YEARS when the
   crowd models the market instead of the venue. Why NOT: top-venue engineering is far better
   than 2018 bitFlyer (per-execution index recomputation would close the lag to ~0); HFT firms
   likely already own any residual at the venues where it pays.
6. **Cheapest falsification (bounded, no capital):** record mark-price + premium-index + trade
   streams for BTC on one venue for 48h; measure update-interval distribution + input→reference
   propagation delay. If the reference is per-execution (lag ≈ transport), the class dies at
   that venue → graveyard with the measured number. If throttled (SFD-like), THEN design the
   Stage-A question. Zero promotion authority; EV gate + pre-registration decide anything more.
7. **≤4-week observable:** measured cadence table for 1-2 venues (one 48h recording session).
8. **Strongest spurious argument (written first):** SFD's lag was harvestable because a RETAIL
   game formed around a 5% boundary with queue-position mechanics; a bare mark-price lag with
   no fee cliff at a known level may have NO monetizable surface even if measured — a lag is
   only an edge where a discontinuity turns timing into money. The probe must name the
   discontinuity before the recording, or it is cadence trivia.
[§33: wired -> docs/graveyard.md]
---

## SESSION SUMMARY — 2026-07-30 (standing daily run, uncapped budget)

- **STEP 0 watchlist review:** prior watchlist held ZERO entries (07-19 session) — nothing to
  promote/hold/drop.
- **Primary work (resume-first):** finished the 07-28 dying run's screen-on-discovery obligation
  end-to-end. On the way through, PROVED the Upbit daily-candle boundary is UTC-midnight
  (invalidating the 07-29 canonical keying + the kimchi retraction's stated mechanism — F0015,
  R0067/R0068), verified the orphan per-asset KR premium series by exact reproduction (corr
  1.0000), and ran the FULL pre-registered screen program: 5 cells on 8.2y 3-asset constructs +
  L1.16a kimchi realignment re-test + 175-asset × 400d panel family (pre-declared).
- **Cards kept (tradeable, survived graveyard + EV):** 0 — the panel family verdict is an honest
  null at recent-era width; nothing cleared the bar. Kimchi's kill STANDS on corrected grounds
  (full-depth same-instant IC +0.0012; original +0.148 was a thin-window read).
- **Era archaeology (8btc tranche):** 4 threads mined to capture depth — OKCoin's 2014-06 retail
  iceberg/TWAP launch (CZ-era), 2015 stop-cluster leakage suspicion, zero-fee era end + rail
  sequencing. Era knowledge routed; no cards (all map to adjudicated mechanism families).
- **Expansion:** KR per-coin premium tracker ecosystem (6 dashboards) catalogued + KR lexicon
  (6 terms) seeded into the operator library. §39 advance: dawsbot/eth-labels VERIFIED (MIT,
  169k labels, free API) — enabling ingredient for the netflow graveyard re-entry condition.

## WATCHLIST (max 5 — seat memory)

1. **kr_perasset_premium (dispersion / relative-tilt constructs)** — SINGLE TRIGGER: R0069
   adjudication. If the brain ranks the full-depth panel backfill (Upbit to 2017-09, n_eff ~50k)
   worth the fetch, that screen decides the axis permanently; family-positive → pre-register
   forward clock per §26.5. Do NOT re-screen partial windows or new constructions meanwhile
   (forking-paths guard). Mechanism: per-asset rail equilibrium (8btc tid 63748, 2017) + KR
   retail per-coin premium attention (6 live dashboards). Current state: recent-era family null;
   8.2y 3-asset cells could-not-tell with clean decontamination.

---

## RU FRONTIER MINER — session 1 (2026-08-01) — cards + the family this seat opened

**CARDS KEPT (tradeable, survived graveyard + EV): 0.** Honest null on tradeable mechanisms, and
the null is not for want of material — it is because the RU corpus's two dominant families are
both already adjudicated here (`retail_crossvenue_scan_arb` → graveyarded this session;
`statarb_kalman_hedge_ratio_refinement` → graveyarded this session). What the session actually
produced is a **family prior** for the desk's only never-tested family, and a demonstrated defect.

### FAMILY PRIOR — STATISTICAL-ARBITRAGE (`data/strategy_coverage.json` state:
### MENTIONED-NEVER-TESTED, n_tested=0). First real evidence base, from RU practitioners.
This family has **1 ledger mention and nothing ever in the graveyard** — the desk has never tested
it. RU retail algo culture is the most statarb-saturated community in any region the desk covers
(MOEX calendar spreads, SBRF/SBPR pairs, cointegration scanners), so it is the natural place to
source a prior cheaply before spending a forward slot. **Not a card — a prior. Nothing here is
promotable and no clock is requested.**

| datum | value | source |
|---|---|---|
| gross return, 80 cointegrated pairs | **4.78%/yr per contract** | smart-lab (cointegration basics tranche) |
| practitioner capacity ceiling per pair | **0.3–1.0M RUB ≈ $3–11k** before market makers take it | smart-lab 707565 comment (SaOLin) |
| named binding constraint | **slippage + colocation**, not signal quality | smart-lab 707565 (author's own conclusion) |
| bull-case claim (contested, unverified) | 50–100%/yr on SBRF-SBPR | smart-lab 707565 comment (Robinzon4) |
| estimator sophistication premium | **≈ zero** — Kalman ≈ polynomial ≈ OLS+σ | smart-lab 936066 reply chain |

**THE READ, and it cuts both ways — this is the honest part.**
- **AGAINST:** a 4.78%/yr gross per contract against a family whose practitioners unanimously name
  slippage as the killer is a thin starting point, and MOEX equity-pair statarb does not transfer
  to crypto instruments the desk can trade.
- **FOR, and it is a genuine §42 signal:** the practitioner capacity ceiling of **$3–11k per pair**
  is not a reason to decline — under L1.18a it is *exactly* the band this desk exists to occupy,
  and it is the reason funds cannot be here. "Market makers eat it above 1M RUB" is a statement
  that the edge survives *below* 1M RUB. A fund reads that as uninvestable; a $4.5k book reads it
  as a quota.
- **THE DECIDING GAP:** every RU number above is **gross, MOEX-instrument, and equity-pair**. The
  desk has no measurement of crypto-instrument statarb costs, and the desk's own record says
  costs are where families die (`illiquidity_premium`, 96.2% frictions-family replication failure).
- **THEREFORE:** the prior does NOT justify a forward slot and I am not requesting one. It justifies
  exactly one cheap thing — that when the desk next tests STATISTICAL-ARBITRAGE, it spends the
  budget on **cost/capacity measurement, not on the estimator**, because the RU corpus has already
  spent a decade proving the estimator is not the binding constraint. Ledgered as **R0296**.

### RU PREMIUM AXIS — CLOSED, do not re-open without a named enabling change (L1.16a)
Item 3 of this session tested the desk's own **barrier-height law** at its most extreme
out-of-sample point. Result: **the law survives, and the axis is closed on two independent
grounds.**
- **Measured:** RU P2P USDT/RUB bid-ask spread runs **~1.5–2.5%** (2025) — the widest of any region
  in the desk's dataset (KR premium std 1.42% / JP 0.37% / TR 0.23% / Coinbase 0.06%). Barrier
  height predicted the ordering correctly, out of sample. **But note the units differ** — 1.5–2.5%
  is a *bid-ask spread*, i.e. a **transaction cost paid to the merchant who holds the rail**, not a
  premium std the desk could harvest. That distinction is the whole finding: at the extreme of the
  barrier-height law, the rent is so large it is charged *as spread*, and the desk would be the
  payer, not the collector.
- **§13 HARD STOP, and it is dispositive on its own:** the principal RU venue in this axis
  (Garantex) is **OFAC-sanctioned**. Under §13 legitimacy this is a hard stop, never a hurdle — no
  data collection, no execution, no exception, in any language. The axis is unhuntable regardless
  of its economics.
- **RE-ENTRY CONDITION:** none that this desk can satisfy. Recorded so no future seat re-spends on
  "the Russia premium is huge, why aren't we there" — it is huge *because* it is unreachable, which
  is the barrier-height law restating itself.
- **DIASPORA (standing question, answered for this region):** post-2022 RU flow moved to **P2P/USDT
  rails and sanctioned/offshore venues** — i.e. into exactly the leg the §13 gate forbids. There is
  no followable diaspora here for this desk. This is a genuine dead end, and naming it as one is
  the deliverable.

---

## SESSION SUMMARY — 2026-08-12 (standing daily run; brain seat)

**STEP 0 — WATCHLIST REVIEW (one line each):**
1. `kr_perasset_premium` — **DROP.** Its single trigger (R0069 adjudication) fired 2026-08-01:
   decisive full-depth screen returned HONEST NULL (effective sign-z +1.15, 0/38 survivors,
   37 underpowered + 1 timing-artifact), forward clock explicitly declined. Axis adjudicated —
   nothing left to watch.
2. POC volume-profile retest (RU 08-04 card) — **HOLD.** Stage-A falsification (rolling 96-bar
   POC on owned 1h candles) still un-run; trigger unchanged.
3. SFD-class venue-cadence probe (JP 08-04 card) — **HOLD.** The 48h mark/premium-index cadence
   recording still un-run; the name-the-discontinuity precondition stands.

**THIS SESSION'S DIG (Nuclear Phynance era-archaeology, first touch):** ground OPENED — 6,645
distinct archived thread-page captures (2006→2021) via Wayback CDX; the live site is DEAD (000
both schemes). Two threads mined to full depth (both Page-1-of-1, complete reply chains):
161897 "VIX futures explanation" and 161299 "Quantifying how mean-reverting a market is?".
EliteTrader: **CLOSED for this seat — ClaudeBot refused by name in robots.txt** (§13; archive
side-door barred per the bitFlyer ruling). Wilmott: WALLED today (Cloudflare 403 both egresses).

**Cards kept (survived graveyard + EV): 0.** One mechanism decomposed and EV-gated honestly:

### dvol_futures_basis_carry — EV-REJECTED, logged as watchlist memory (not a card)
- **Source + provenance:** NP thread 161897 (2012-07-24, practitioners filthy/ebal/athletico;
  Wayback capture 20121015081431) — VERIFIED-mechanism (textbook-consistent, independently
  derivable); instrument verified live 2026-08-12: Deribit BTC DVOL futures (USDC cash-settled,
  60-min TWAP expiry; ETH not yet listed) — support.deribit.com 31424954825373.
- **Mechanism:** VIX² (variance) is statically replicable by an option strip; VIX is its square
  root — "you can't trade square roots": no static hedge exists, cash-and-carry cannot pin the
  future, so the basis is an UNPINNED risk-neutral expectation E[vol] bearing a vol-of-vol
  (convexity) premium. Same construction ⇒ same property for Deribit DVOL futures.
- **Desk transfer, both directions:** (a) DVOL futures basis = candidate vol-carry sleeve,
  structurally distinct from perp funding (counterparty = vol hedgers paying convexity, not
  levered longs); (b) the inverse test CONFIRMS the desk's funding prior: perp basis IS
  statically hedgeable (spot vs perp), so funding carry's edge must come from flow (leverage
  demand), never from replication failure — consistent with `_PRIORS` funding_family.
- **EV gate (honest, run this session):** est_sharpe 0.4, breadth 1 (BTC only), capacity ~$30k,
  orthogonality 0.4 (short-vol tail-correlated with funding book), 10h effort, tags
  funding_family+narrow_breadth → **EV 0.0003 < 0.002 REJECT** (p_survive 0.075, breadth_f
  0.224). The single-instrument construction starves exactly like VRP — the prior working as
  designed. No construction-shopping was done; this is the one construction scored.
- **SINGLE PROMOTION TRIGGER:** breadth. ETHDVOL futures listing PLUS any second venue's vol
  future (≥3 instruments), OR a validated ≥5-asset cross-sectional vol-carry construction —
  then re-score; at breadth 5 the same honest inputs clear the gate (~0.0027).
- **Strongest spurious argument (written first):** the premium is the most-published carry in
  finance; in thin crypto vol futures the roll-down may be entirely consumed by spread + the
  tail (short-vol blowups correlated with the funding book's own worst days), making the sleeve
  additive risk, not additive alpha.

**WATCHLIST (max 5 — active entries after this session): POC retest (hold), SFD cadence probe
(hold), dvol_futures_basis_carry (new). 3/5 slots used.**

---

## SESSION SUMMARY — 2026-08-12 session G (EN frontier miner, seat rotation)

**THIS SESSION'S DIG (NP era-archaeology continuation + HN Records family close):** three items,
all closed. (1) **HN 9152332** (2015 Quantopian contest-winner thread, 28 comments, full tree via
OP-022, max depth 3) — the ERA COMPANION to graveyard `crowdsourced_backtest_selection_fund`: the
mechanism of death was predicted IN the operator's own 2015 thread (learnstats2: "the algorithm
you need to win a contest is the highest-risk algorithm you can get away with"; fawce's defense
named the exact machinery — backtest + 1-month paper — that the 2020 fund outcome refuted).
Graveyard entry enriched, no new mechanism. (2) **NP threads 161162 + 161713 EXHAUSTED** (3 and
14 posts, full reply chains): 161162 → convexity-adjustment-neglect mechanism, translated and
EV-gated below; 161713 → 2012 validation time capsule (random-tape harness placebo, live-vs-
backtest same-window reconciliation, selection-on-OOS death anecdote) — CONFIRMATORY of desk
doctrine (certify_gauntlet already runs known-GOOD/known-NULL controls, R0017), no inbox row
spent. (3) **NP forum indices surveyed:** 8 of 13 classified (f2 TRADING rich — 25 titles mapped
2011-02; f4 risk/VaR; f5 quant-theory; f8 books; f6 careers noise; f10 off-topic noise; f12
general mixed; f1 done prior); f3/f7/f9/f11/f13 = ZERO Wayback captures (2 probes each,
unarchived seams). Venue-discovery thread 148582 ("top 3 forums you spend time on"): 0 replies at
capture — dead seam, documented. **DATA AXIS FOUND: Binance COIN-M (dapi), zero desk coverage,
verified-live keyless** → data_axis_watchlist card 31 + universe map 98-binance-coinm-dapi.

**Cards kept (survived graveyard + EV): 0.** One mechanism decomposed and EV-gated honestly:

### coinm_usdtm_basis_convexity_rv — EV-REJECTED, logged as watchlist memory (not a card)
- **Source + provenance:** NP thread 161162 "Convexity arbitrage" (2012-06-20, Wayback
  20121015082245, MrKlugh/gill/sas) — era lore: mid-90s convexity adjustments (FRA-vs-futures,
  in-arrears) ignored by the street until a London desk arbitraged them; one victim "no longer
  around". MECHANISM_ONLY tier at source; instrument layer verified live this run (dapi probe).
  DERIVES-FROM: NONE (checked) — 3-post thread, no citations beyond a risk.net cliquet feature.
- **Mechanism:** inverse (coin-margined) futures settle PnL in coin ⇒ convex USD payoff ⇒ fair
  COIN-M basis ≠ USDT-M basis by a computable convexity adjustment (∝ σ²T). Clienteles are
  segmented by collateral custody (coin-only hedgers cannot use USDT-M), so the differential can
  sit away from fair value persistently. Trade = same-expiry basis spread, market-neutral to
  first order, 5 quarterly underlyings (BTC/ETH/BNB/SOL/XRP).
- **EV gate (honest, run this session, libs.research.alpha_economics):** est_sharpe 0.5, breadth
  5, capacity $200k (COIN-M BTC/ETH deep), orth 0.5, 12h effort, 1.2× maint, tags
  funding_family + crowded_known (the spread is a known pro-desk trade even though the
  convexity-MISPRICING test framing is not published) → **EV 0.0009 < 0.002 REJECT** (p_survive
  0.105). Conservative variant WITH narrow_breadth tag also scored and reported: 0.0002. Two
  constructions considered, both logged (VARIANTS_TRIED discipline): quarterly-convexity (scored,
  mechanism-true) and 20-pair perp funding-differential (named, weaker mechanism — clientele
  demand, not convexity; NOT scored as a rescue).
- **SINGLE PROMOTION TRIGGER (measurement, not construction-shopping):** once the COIN-M axis is
  backfilled (card 31), compute the measured quarterly basis differential minus theoretical
  convexity value, net of 2× taker fees both legs. If |residual| persists on ≥3 of 5 underlyings
  across ≥2 quarterly rolls, re-score with MEASURED est_sharpe in place of the 0.5 prior —
  measured inputs, not tag relitigation, are the only path back.
- **Strongest spurious argument (written first):** every delta-neutral basis desk already watches
  this spread; post-2022 COIN-M OI share shrank (the coin-collateral clientele thinned), so the
  residual may be exactly fee-sized — the axis measurement decides, not this card.

**WATCHLIST (max 5 — active entries after this session): POC retest (hold), SFD cadence probe
(hold), dvol_futures_basis_carry (hold), coinm_usdtm_basis_convexity_rv (new). 4/5 slots used.**

## SESSION SUMMARY — 2026-08-12 session 2-on-branch (RU frontier miner)

### delisting_announcement_unwind_window — EV-REJECTED at prior, logged as watchlist memory (not a card; measurement trigger named)
- **Source + provenance:** github.com/roman-boop/bybit-trading-on-delistings (RU practitioner
  cryptomaniac_dt, the POC-retest card's author — chain walked live topic 2130528 → GitHub
  profile → 50-repo sweep, 2026-08-12). The bot is EXECUTABLE-tier evidence of the RETAIL SNIPE
  layer: telethon on @Bybit_Announcements + Binance CMS news parse → market SHORT on mentioned
  USDT-perps at announcement latency. Sibling repo bybyt-tokensplash-long = the listing-side
  twin (already desk-owned ground: listing_events.py is pre-registered; not a new trial).
  DERIVES-FROM: NONE (checked) — no citations in either repo; practitioner-native genre.
- **Mechanism:** delisting announcement opens a PRE-ANNOUNCED, DATED forced-unwind window
  (holders must exit; market-makers pull; perp contracts get settled/removed) ⇒ predictable
  sell pressure with published equities index-deletion analogues and a crypto study already
  quoted on the Upbit axis row (−12%/wk post-announcement, no reversal). §42 names "delisting
  unwinds" as desk ground. The desk angle is the multi-day WINDOW, never the t=0 snipe (that
  layer is measurably occupied — this repo IS the evidence).
- **EV gate (honest, run this session, libs.research.alpha_economics):** est_sharpe 0.5, breadth
  30 (batch-clustered events counted conservatively), capacity $50k (delisted names are thin BY
  SELECTION), orth 0.8, 16h effort (event-list collector + event study), 1.2× maint, tags
  crowded_known (index-deletion effect is published; snipe layer crowded) → **EV 0.0013 < 0.002
  REJECT** (p_survive 0.0525). Sensitivity at est_sharpe 0.7 also rejects (0.0019) — reported,
  not adopted. VARIANTS_TRIED: window-drift (scored); announcement-latency snipe (named, NOT
  scored — a latency race vs colocated retail bots at zero prior, naming it is not a rescue).
- **SINGLE PROMOTION TRIGGER (measurement, not construction-shopping):** universe-map row 44
  (exchange-announcement-calendars, adopted-pending-verify) now carries the CONCRETE collector
  routes this dig surfaced (Binance CMS news endpoint; @Bybit_Announcements as machine-readable
  feed). When that owed verify lands and the event list exists, the event study against bronze
  candles is ~free: if measured window drift nets positive after funding-spike carry cost +
  spread blowout (the two named killers — shorts crowd delisting perps, funding goes deeply
  negative), re-score with MEASURED est_sharpe via libs/validation/event_study.py (event-shaped
  gate, both exit rules = two trials). Nothing promotes from this entry directly.
- **Strongest spurious argument (written first):** the visible drift may be entirely the
  UNSHORTABLE segment — by the time a perp short is practical, funding cost ≈ the drift
  (barrier-rent shape again: the return accrues to whoever bears the constraint, and a
  crowded-short funding print IS that constraint priced).

**WATCHLIST (max 5): unchanged — 4/5 slots used; this entry holds no slot.**

## SESSION SUMMARY — 2026-08-12 session 2-on-branch (KR frontier miner)

### kr_rail_state_transition_global_leg — NEW CARD (slot 5) — EV 0.0061 QUEUE, novelty 0.772 [§33: wired -> data/ppomppu_kr_era_threads.jsonl]
- **Source + provenance:** Ppomppu 가상화폐 era corpus, mania+ban window threads mined to full
  comment layer this session (era-seek per OP-021 KR; archive data/ppomppu_kr_era_threads.jsonl,
  era map + 2,130-row title tape data/ppomppu_bitcoin_era_map.json). Load-bearing primary posts:
  22072 (2017-12-24: "지갑 없이 신규상장시 타거래소보다 매우 높은 시세" — deposit-closed listing
  = captive-market premium, stated as a RULE with live example BTG-Coinone 66; 보따리상 supply
  pipe throttled by chain congestion), 55179 (2018-01-12: ERC-20 tokens arb tight — per-coin
  premium ∝ transfer friction), 76535/76756/76863 (2018-01-29/30: venue↔bank binding + beehive
  kill → venue-level rail dispersion, frozen-leg discounts). DERIVES-FROM: NONE for the mechanism
  comments (checked — folk-original; news threads quote Yonhap). CONVERGENCE (genuinely
  independent, three instances): era folk rule (2017-12) + modern Cocoa per-coin premium
  route-optimizer (velog, s5 2026-08-04) + CN 7th-instance venue-credit share (8btc 2013) —
  different eras, languages, authors; none derives from another.
- **Mechanism:** per-coin deposit/withdrawal suspensions and resumptions on Upbit/Bithumb create
  and release fenced-market (가두리) venue premium dispersion. KR retail is KRW-rail-captive; when
  a coin's deposit rail closes, KR demand cannot import supply (보따리상 pipe cut) → venue-local
  premium builds; on rail REOPEN the premium converges through the first deposits. The desk
  cannot touch the KR leg (no KRW rail — the membrane cuts against us too) — the tradeable
  transmission is the GLOBAL leg: KR-dominated alts' Binance price/flow around KR rail-state
  transitions (KR venues are the marginal bid in many alt books; a rail state change gates that
  bid's transmission). The regressor is the venue's OWN label, structurally unbuyable (card #26).
- **EV gate (honest, run this session, libs.research.alpha_economics):** est_sharpe 0.5, breadth
  30 (rail-transition events/yr, batch-clustered counted conservatively), capacity $100k (Binance
  leg, mid-cap alts), orth 0.8 (no desk signal reads per-coin/per-venue KR rail state; kimchi =
  aggregate BTC premium only), 16h effort (announcement-category collector extension + event
  study), 1.2× maint, tags new_orthogonal_data → **EV 0.0061 ≥ 0.002 QUEUE** (p_survive 0.24,
  breadth_f 1.225). Novelty vs 231 graveyard priors: **0.772, not redundant** (nearest:
  illiquidity_premium 0.228). Capacity runway: event-shaped overlay on liquid Binance perps —
  no runway conflict; REACHES-LIVE class if it survives.
- **Pre-registration owed BEFORE any screen (two-stage law, zero promotion authority here):**
  event = per-asset rail-state TRANSITION on a KR big-2 venue (deposit close / deposit reopen —
  from the announcement archive's suspension notices + the live market/all + assetsstatus flags
  now accruing since 08-01); direction = close→global-leg underperformance of KR-dominated alts
  (KR bid transmission cut), reopen→recovery; window = announcement t0 to t+3d; target =
  cross-sectional relative return vs Binance alt universe (asset-selection signal per the
  target/horizon duty). BOTH event_study exit rules = two trials, logged. FALSIFIER: if
  close-events show no cross-sectional deficit vs matched controls (or the sign is random across
  the 8.8y announcement archive), the transmission is dead and the card dies — the KR-internal
  premium may be real while the global transmission is nil, and only the transmission is
  tradeable here. THE SCREEN IS CARD #26's OWED SCREEN — same owner, now with a design; this
  card adds no second screen obligation (§33: this find is WIRED as era evidence + design;
  the screen disposition lives on card #26, unchanged owner).
- **Strongest spurious argument (written first):** KR-dominated alts are SELECTED FOR
  manipulation-heavy books (the era's own bots were part venue-manufactured volume, and Upbit
  wash-volume was prosecuted) — a measured "KR bid transmission" may be the echo of paint, not
  flow; the control set must match on volume-quality, and any survivor owes a mechanism check
  against per-venue REAL-flow proxies before it is believed.
- **ADDENDUM 2026-08-12 (same seat, resumed run) — two era findings that cut AGAINST this card,
  recorded here because the screen must not be run without them.** (1) **WS-011 outage-staleness
  confound.** The same era corpus documents (thread 52389, OP + independent commenter) a KR venue
  whose matching engine FROZE during a crash, manufacturing a ~140,000 KRW intra-KR spread out of
  nothing. Tapes freeze during crashes and volume spikes — exactly when rail-state transitions
  cluster — so this confounder is *correlated with the treatment* and biases the event window
  rather than averaging out. The pre-registered screen above must therefore carry a liveness
  filter (venue volume / tape advance) on both legs, or a "rail state → premium" result is
  unidentifiable from "venue stopped trading". Note `libs/research/upbit_data.py:64` currently
  discards `candle_acc_trade_volume`, so that filter is not available from the stored series
  as-built. (2) **Direction risk.** Thread 77829's best reply — "해외 차트 고스란히 반영 되요"
  (the KR bots simply track the overseas chart) — is era testimony that the KR book FOLLOWS
  global. This card's tradeable claim is KR→global transmission; if the era reply generalises,
  the causal arrow points the other way and the card's mechanism is absent even if the correlation
  is present. Neither finding kills the card; both mean a naive positive result should be
  disbelieved first. The FALSIFIER above is unchanged and still binding.

**WATCHLIST (max 5): POC retest (hold), SFD cadence probe (hold), dvol_futures_basis_carry
(hold), coinm_usdtm_basis_convexity_rv (hold), kr_rail_state_transition_global_leg (NEW). 5/5
slots used.**

## SESSION SUMMARY — 2026-08-12 (JP frontier miner)

### jp_funding_settlement_sandwich — EV-REJECTED as published, logged as watchlist memory (not a card); the OBSERVATION is routed instead
- **Source + provenance (mandatory fields).** SOURCE: `qiita.com/lud-botter/items/6b4412fe2c7b3a9578a5`
  — 「金利をサンドイッチするBotのアイデア」, 仮想通貨botter Advent Calendar 2023 day 12, posted
  2023-12-11, updated 2024-03-10, 34 likes, **0 comments** (checked, not assumed — no reply layer
  to mine). Host qiita.com is the OPEN half of the JP corpus (note.com/zenn.dev closed this run,
  OP-052). **DERIVES-FROM: NONE (checked)** — the post cites no paper, repo or thread; it is a
  first-person account triggered by watching the 2023-08/09 alt-pump wave. This matters: it makes
  the agreement with the desk's own L1.47 finding **genuine independent convergence, not an echo**
  (the desk's usual false-convergence trap, GAP #85).
- **Mechanism as published.** On perps carrying large NEGATIVE funding (< −1% per settlement,
  common on 2023 alt pumps), price drops sharply AT the settlement stamp — the author reports the
  same down-candle at 1m, 1s AND ms resolution. Trade: hold a LONG for ~10 ms spanning the stamp,
  collect the payment, eat only the tiny price drop. Win iff |funding| > drop over the hold. WHO IS
  FORCED: the funding-harvesting long cohort, synchronised by the VENUE'S CLOCK — they are paid at
  a common instant and exit together, so the payment itself triggers the move.
- **EV gate (honest, run this session):** est_sharpe 0.6, breadth 30, capacity $25k, orth 0.85,
  60h effort, 2.5× maintenance, tags funding_family + high_turnover_no_maker → **EV 0.0006 <
  0.002 → REJECT.** Novelty 0.797 (not redundant, nearest `grave:cross-exchange funding
  dispersion` 0.203) — so it is rejected on ECONOMICS, not as re-tested ground.
- **WHY IT IS DOA HERE SPECIFICALLY, beyond the EV arithmetic.** (1) It needs millisecond execution
  against a stamp the author measured jittering **50–100 ms** on his own main venue; this desk has
  no HFT execution path and its one abandoned HFT attempt is in the same corpus. (2) The author's
  own sizing was **20× leverage**, which the survival rails forbid on an unproven edge — and his
  stated failure mode is a **−50% trade** when the funding is missed. (3) **The delay is worst
  exactly when funding is most extreme** ("金利-3%など、加熱している時ほど遅延しやすく"): payoff
  and execution risk are POSITIVELY correlated, so the fat left tail is concentrated on the
  best-looking opportunities. (4) **Dead at source with a dated cause:** ~¥500k over 2 months, then
  "エッジが消えた"; one venue **changed its funding-settlement rules mid-operation** — the same
  venue-rule-change death mode as the SFD class (graveyard `jp_sfd_boundary_game`, 08-04). (5) The
  author was also front-run on his BUY leg once his timing became regular.
- **WHAT IS ACTUALLY WORTH KEEPING — routed, not carded.** The tradeable bot is dead; the
  OBSERVATION behind it is a measurable claim about market structure that bears on the desk's
  DEPLOYED sleeve: *is there a systematic price move in the minutes around a funding settlement,
  conditional on funding sign/magnitude?* L1.47 already measured that the desk's own closes cluster
  near settlement stamps (22.3% within an hour of a payment) but never measured whether PRICE moves
  there. → **EV 0.0087 QUEUE** as `funding_settlement_phase_execution_timing` (est_sharpe 0.35,
  breadth 40, capacity $200k, orth 0.7, 12h, tags funding_family). This is an EXECUTION-TIMING
  measurement for an existing sleeve, not a new alpha — which is exactly the class L1.5/the
  bottleneck law says is usually cheaper and more certain than another signal.
- **UNTESTED ALPHA the author names and never tried (L1.34 #6, the unpriced option):** "if you can
  characterise the CONDITIONS under which the settlement delay occurs, you can build the mirror bot
  — short WITHOUT paying funding." Logged as his stated open question, not as a desk claim.
- **PROCESS EXTRACTION (process mandate).** DISCOVERY PATH: noticed an EXTREME in an already-visible
  observable (funding < −1% during alt pumps) and reasoned "a large discrete payment must create a
  distortion" — a mechanism-first trigger, not a data-mining sweep. THE NOTICING: confirmed the same
  artifact at THREE resolutions (1m/1s/ms) before trading it — a cheap, transferable robustness
  check the desk does not routinely run on microstructure claims. WHAT HE COULD NOT TEST: the
  venue's internal order-processing/settlement mechanics (his addendum section is a stub). HIS OTHER
  BOTS, with outcomes — a rare practitioner P&L ledger: CEX-CEX domestic↔overseas arb (**quit at the
  JP Travel Rule revision**, barely profitable), DEX shitcoin bot (atomic arb + sandwich, tens of
  thousands USD over months, chain dying), MEV sandwich via Flashbots (abandoned: gas + competition),
  spread-detection bot (manual execution, ~¥10k/mo), HFT (1+ month, **no valid indicator found**,
  abandoned), ML swing bot (backtest-good, untested live).
- **ERA MARKER for the JP map (dark-forest deliverable 3):** the JP **Travel Rule revision (in force
  2023-06-01)** killed this practitioner's domestic↔overseas CEX arb. That is a dated regulatory
  boundary closing the JP corridor-rent surface — the JP instance of the barrier-rent family the RU
  (8th instance) and KR seats keep hitting, and it closes the same way: **by regulation, not by
  competition**. Consistent with the JP premium axis already being graveyarded near zero.

**WATCHLIST (max 5): POC retest (hold), SFD cadence probe (hold), dvol_futures_basis_carry (hold),
coinm_usdtm_basis_convexity_rv (hold), kr_rail_state_transition_global_leg (hold). 5/5 slots used
— this session added NO card (one EV-reject, one measurement routed to the funding axis owner).**

## 2026-08-13 — JP frontier miner s4 (deep-forest self-hosted layer): 4 candidates scored, 1 clears, 0 new cards

All four were novelty-gated against the graveyard BEFORE scoring (universal duty; none redundant,
nearest-prior similarity 0.149–0.189) and then run through the pre-registered EV gate with honest
inputs. Verdicts, so the trials are counted rather than the survivor reported alone:

| candidate | novelty | EV | p_survive | verdict | disposition |
|---|---|---|---|---|---|
| `venue_fee_volume_credibility` | 0.816 | **0.0058** | 0.24 | **QUEUE** | → universe-map source **102** (data-integrity axis, not a sleeve) |
| `ofi_taker_component_dominance` | 0.851 | 0.0002 | 0.026 | REJECT (below thresh) | → `improvement_inbox.md` item 1 (feature-redundancy fact, not a trade) |
| `option_flow_informedness` | 0.828 | 0.0002 | 0.060 | REJECT (below thresh) | → held below as an untested-alpha lead + vocabulary flag |
| `rev_calendar_spread_iv_convergence` | 0.811 | 0.0000 | 0.013 | REJECT | → `docs/graveyard.md` (also refuted at source) |

**NO NEW CARD. The watchlist stays at 5/5: POC retest (hold), SFD cadence probe (hold),
`dvol_futures_basis_carry` (hold), `coinm_usdtm_basis_convexity_rv` (hold),
`kr_rail_state_transition_global_leg` (hold).** The one gate survivor is a *conditioning variable*,
not a sleeve, so it takes an axis row rather than a card slot — carding it would consume a scarce
slot with something that can never be promoted on its own.

**THE ONE LEAD HELD RATHER THAN DISCARDED — `option_flow_informedness`, flagged per the extraction
mandate as mapping to NO entry in `CRYPTO_MECHANISMS`.** From `perp-screener.com/posts/btc-bot`
(2025-12-04), stated as the author's reason for choosing options at all: *"「意志のある取引」が多いの
では？"* — **option order flow carries more intent per unit notional than perp flow, because
selecting a strike AND an expiry encodes direction, timing and magnitude simultaneously, whereas
`BTCUSDT` gets bought on a vibe.** The desk's vocabulary has `options skew` and `derivatives
positioning`, which are *state* variables; this is a claim about the **informedness of flow
conditional on instrument complexity**, and it is a different quantity. Testable in principle (does
option trade imbalance lead perp price by more than perp trade imbalance does?), and it **fails the
EV gate today on `narrow_breadth`** — BTC/ETH options are ~2–3 independent bets — which is an honest
rejection, not a hidden one. **Enabling change that would re-open it (L1.16a):** a materially wider
liquid crypto option cross-section, or a construction that pools the option-flow signal across many
perps rather than trading the options themselves. Held here, not carded, not screened.

**PROVENANCE NOTE ON THE WHOLE SESSION (OP-072, new this run):** the options post's *mechanism
analysis* is self-disclosed LLM output (*"チャッピーの解説によると"*), so it is **not** an independent
practitioner node and must never be counted as convergence. Its *observations* — realised P&L, greeks
snapshot, the expiry failure mode — stand. The other three sources are pre-2023 or carry no LLM
disclosure, checked.

## SESSION SUMMARY — 2026-08-18 (standing daily run; brain seat)

**STEP 0 — WATCHLIST REVIEW (one line each, triggers probed live this run):**
1. POC volume-profile retest (RU 08-04) — **HOLD.** Stage-A screen on owned 1h candles still
   un-run; trigger unchanged.
2. SFD-class venue-cadence probe (JP 08-04) — **HOLD.** 48h mark/premium-index cadence recording
   still un-run; name-the-discontinuity precondition stands.
3. `dvol_futures_basis_carry` — **DISPLACED to research_memory** (rm-20260818T195526-7ef2c7,
   trigger preserved verbatim). Probed live: Deribit ETH futures = 12, DVOL futures = **NONE** —
   trigger unfired after 6 days; it was the weakest holder (EV 0.0003) and a QUEUE card arrived.
4. `coinm_usdtm_basis_convexity_rv` — **HOLD.** R0462 (COIN-M backfill) scheduled, due 2026-08-27;
   measurement trigger pending.
5. `kr_rail_state_transition_global_leg` — **HOLD.** Screen owed on card #26 (design pre-registered
   08-12); no run visible in research memory.

**THIS SESSION'S DIG (NP forum-2 TRADING batch, carried since 08-12, all closed):**
112425 "Price patterns" **EXHAUSTED** (6/6 archived pages; page-3 final state lost to the capture
lattice — named residual). 147526 "corporate bond new issue premium" **EXHAUSTED** (3/3 posts,
sole capture). 4851 "Renaissance Watch" **SURVEYED** (pages 1/17/18 of 27 archived, 45 total;
named residual: pages ~38-40 = 2014 Senate-PSI basket-options era, 44-45 = 2018+ era). Yields
routed to research memory (rm-…-e701c2): QIM capacity-decay case study (VERIFIED-grade public
tape: founding capacity belief $500M → $6-10B hard-close claim → practitioner impact-cost
refutation → flat-since-2009; the operator's OWN May-2010 admission that its drawdown-reduction
policy subtracted value pro-cyclically), 2013 GP-engine commoditization testimony, Aug-2007 quake
contemporaneous tape, GLOBEX confirm-parsing counterparty-identity leak (era protocol-metadata
flow attribution; modern analog already catalogued = universe-map row 54 Hyperliquid position
transparency — enrichment only, no new axis).

**Cards kept (survived graveyard + EV): 1.**

### listing_comparables_repricing — NEW CARD (slot 5, after dvol displacement) — EV 0.0038 QUEUE (untagged) / 0.0013 REJECT (crowded_known) — BOTH REPORTED; novelty 0.802 [§33: screened -> ledger R0616 names the screening owner + due 2026-09-01]
1. **Source + provenance:** NP thread 147526 "corporate bond new issue premium/discount"
   (2010-11-29→2011-02-05, golftango/Lucy/tokyo; Wayback 20110206204021, sole capture, EXHAUSTED
   3/3 posts this run). Load-bearing reply (Lucy, 1-post account): a new issue priced wide/narrow
   **reprices existing bonds & CDS** — the new-issue event moves the COMPARABLE CURVE, not just
   the issue. Grade: **SEMI for the mechanism class** (independently grounded in the equity
   IPO-industry-spillover literature + the KR 가두리 era corpus documenting captive listing
   demand), **CLAIM for the crypto instance** (no crypto implementation found in this dig — and
   that absence is exactly the tag ambiguity scored below). DERIVES-FROM: NONE (3-post thread, no
   citations).
2. **Mechanism:** a major-venue listing ANNOUNCEMENT of asset X opens a dated two-phase repricing
   of X's already-listed comparables. Phase 1 (announcement→listing): demand for X routes to
   substitutes — X is not yet tradeable on that venue (Upbit KR retail cannot buy X at all;
   Binance announcement→listing gaps run days) — comparables outperform the cross-section.
   Phase 2 (post-listing): demand concentrates onto X; comparables reverse. The desk trades ONLY
   the comparables (liquid, already-listed perps) — harvesting listing information through
   instruments that exist, sidestepping the measurably-crowded listed-asset snipe layer entirely.
3. **Counterparty + why they persist:** attention-driven retail routing "the next X" demand into
   sector peers (behavioral, re-supplied by every listing cycle); market makers inventory-hedging
   new-listing risk with correlated names (structural, small). The snipe bots that crowd the
   listed asset CANNOT occupy this channel — it is a multi-day relative-value window with no
   latency race.
4. **Why the edge exists NOW:** the desk holds the dated announcement archives (Binance CMS +
   Upbit, 8.8y) AND a desk-built correlation-cluster grouping map (zero licence surface) — the
   comparable set is computable point-in-time from owned data; Upbit still lists with
   announcement gaps; §42 names listings as desk ground.
5. **Crypto-perp adaptation:** cleanest construction is CROSS-VENUE — Upbit announcement →
   Binance-perp comparables of the announced asset (announcement on one venue, harvest on
   another, no KRW rail needed). Second construction: Binance announcement → Binance-perp
   comparables. BOTH declared now (VARIANTS_TRIED; no construction-shopping later).
6. **Cheapest falsification (free, historical):** event list from the announcement archives;
   comparable sets from ROLLING PRE-EVENT correlation clusters — **NEVER the current grouping map
   applied backwards** (the pct_circ_now look-ahead class, named before the screen so it cannot
   be shipped); `libs/validation/event_study.py`, both exit rules = 2 trials, phase-1 cell
   primary, phase-2 reversal confirmatory. Timestamp alignment DECLARED: announcement stamps are
   venue-local (Upbit KST — the KR to= lesson), bars UTC D1; entry = next-UTC-day open after the
   announcement stamp, never same-bar.
7. **≤4-week observable:** event-study verdict on the archived events (both phases), plus ~8-12
   new events/month accruing forward across the two venues.
8. **Strongest spurious argument (written first):** REVERSE CAUSALITY — venues list what already
   pumped, so the listing is SELECTED ON the cluster's momentum and "comparables outperform
   before listing" may be the venue's selection rule, not a tradeable reaction. The screen must
   measure from the ANNOUNCEMENT stamp only, control for pre-announcement cluster momentum, and
   survive a placebo on matched non-event windows of the same clusters. Second: the meme-corner
   "sympathy play" is folk-crowded — both EV variants are reported above (QUEUE untagged, REJECT
   crowded_known) and the screen's FIRST question is the crowding check, not the return.

**WATCHLIST (max 5 — active entries after this session): POC retest (hold), SFD cadence probe
(hold), coinm_usdtm_basis_convexity_rv (hold), kr_rail_state_transition_global_leg (hold),
listing_comparables_repricing (NEW). 5/5 slots used; dvol trigger lives in research memory.**

## SESSION SUMMARY — 2026-08-13 session 3 (KR frontier miner) _(landed 2026-08-19 by KR s4 — this section sat on the unmerged branch `claude/kr-miner-s3-20260813` for 6 days; out of date order because the log accumulated later sessions first. Its "card #33" is now card #35; its "OP-072" is now OP-090. NOT a watchlist card — claims no slot.)_

### kr_venue_exclusive_bank_rail_asymmetry — **EV-REJECTED 0.0019 (thresh 0.002), logged as watchlist memory, NOT a card** — novelty 0.899 [§33: screened -> data/kr_venue_bank_rail.json]

- **Source + provenance.** Ppomppu 가상화폐 era corpus, the 85 rail/bank threads named by KR-s2's title
  tape and mined to full comment depth this run (`data/ppomppu_kr_rail_corpus.json`, 334 of 454
  declared comments — see the attrition note). Load-bearing primary: **76756** (2018-01-30)
  *"거래소마다 입금계좌는 한개의 은행밖에 안되죠 / 업비트는 기업이고"* — each exchange gets a KRW deposit
  rail at **exactly one bank** — corroborated in-thread by an independent commenter and across
  **76746 / 76863 / 76875 / 55174**. **76875** sharpens it: 농협**중앙회** only, 지역농협 (regional
  co-ops, 2금융권) were REJECTED — the rail is narrower than the bank name. **DERIVES-FROM: NONE
  (checked)** for the mechanism comments — folk-original practitioner reports; the two news threads
  (76535/76551) quote 한국블록체인협회 and are used only for the venue list, not for the mechanism.
- **Mechanism.** Korean regulation binds each licensed VASP to ONE partner bank for KRW
  deposit/withdrawal (2018 real-name system, **still in force 2026**). So a bank-level event —
  cutover, maintenance, KYC throttle, contract non-renewal — is a **venue-asymmetric shock to one
  venue's fiat rail and not the other's**: an exogenous shifter of the intra-KR (Upbit−Bithumb)
  basis that does not move crypto price. This is the piece R0299 wants: KR-s2 established that the
  intra-KR spread **differences out** the cross-border capital control that made kimchi ~73%
  artifact (both legs sit behind the same control), so what survives that differencing is
  venue-specific — and the fiat rail is the largest venue-specific state variable there is.
- **Current mapping (verified live, not assumed from the era):** Upbit→K-Bank (**contract expires
  Oct-2026** — a forward-dated, pre-announced, venue-asymmetric event ~2 months out),
  Bithumb→KB Kookmin (**migrated from NH on 2025-03-24**), Coinone→Kakao, Korbit→Shinhan,
  Gopax→Jeonbuk. **NAMED KILL CONDITION:** Woori Bank's CEO is publicly lobbying to repeal the
  one-bank rule; repeal ends the asymmetry the whole axis rests on. The axis therefore carries an
  expiry, not an assumed persistence.
- **The one measured instance.** Bithumb's 1m tape has a **10.50h hole on its migration date**
  (2025-03-23T15:30Z → 2025-03-24T02:00Z, +51bp across the halt) while Upbit ran continuous. The
  rail event is **observable in price data as an absence**. Routed to WS-011 as its second
  observation, which retires that entry's own "2017-18 is not 2026" caveat.
- **EV gate — RUN, NOT ASSERTED, AND IT REJECTS.** `libs.research.alpha_economics.ev_score`:
  est_sharpe 0.4, breadth **6** (KR venue↔bank rail transitions per year across 5 licensed venues),
  capacity $100k, orth 0.85, 20h effort, 1.2× maint, tags new_orthogonal_data →
  **EV 0.0019 < 0.002 → REJECT**, binding term `breadth_f 0.548`. The treatment is too rare.
  Novelty 0.899 (nearest `coinone_kr_premium` 0.101) — **so this is rejected on ECONOMICS, not as
  re-tested ground.**
- **AND THE REJECTION IS KNIFE-EDGE, WHICH IS ITSELF THE FINDING.** breadth 6→REJECT but 8→QUEUE
  (0.0022); est_sharpe 0.4→REJECT but 0.5→QUEUE (0.0023). A one-unit change in an input **I
  estimated by hand** flips the verdict, so this gate result is a statement about my guess, not
  about the world (GATE-OPTIMALITY DUTY). Recording it as a pass or a kill would both be
  over-claiming. **The count is the deciding measurement.**
- **RE-OPEN CONDITION (L1.16a — a named enabling change, not a vague "revisit").** Enumerate KR
  venue↔bank rail transitions since 2018 from venue notice archives — the desk already holds
  `data/upbit_trade_announcements.jsonl` (737 rows, 2017-10-27→) and Bithumb's notice feed is
  catalogued on data-axis card #4. **If that enumeration yields ≥8 transitions/yr the EV gate flips
  to QUEUE on inputs otherwise unchanged.** Until then this stays memory, not a card.
- **METHOD WARNING THE COMMENT LAYER PAID FOR, and it binds that enumeration.** 76535's headline
  ("7 beehive venues cut off, >1M users") was **disputed by the named venues within 44 minutes**
  (76551: HTS코인 and 코인네스트 both posted 오보 notices), and a commenter observes the cut venues
  *"어차피 현금 입금 안되던 곳"* — **the rail was already dead before the announcement**. So for this
  axis the **announcement date is NOT the treatment date**: the news is a lagging, sometimes wrong,
  marker of a state that changed earlier and quietly. An event study keyed on announcement
  timestamps would mis-date its own treatment. Only the reply layer carries this.
- **Screen status: NOT SCREENED, deliberately.** One clean dated treatment instance is n=1; that is
  an anecdote with a timestamp, not an event study, and L1.62 forbids certifying a verdict on a
  sample size nobody measured. A screen here manufactures either a phantom edge or a false
  SCREEN-WEAK kill on a real mechanism. Counting the treatment comes first and is not a substitute
  for the screen — it is its precondition.
