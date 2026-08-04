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
