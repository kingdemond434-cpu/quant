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
