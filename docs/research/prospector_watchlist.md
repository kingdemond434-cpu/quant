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
