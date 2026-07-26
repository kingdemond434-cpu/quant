# [LIT-b] FORGOTTEN-LITERATURE ARCHAEOLOGY — pre-2015 mechanisms never tested on crypto perps

_Opened 2026-07-26 by the literature deep-miner. **Write-as-you-go**: every mechanism is appended
the moment it resolves. A mid-run kill leaves durable output, not a header._

**Thesis of this ground (the one-time-exhaustible layer).** Two dead strata nobody re-reads:
(a) pre-2015 microstructure / FX / commodity-futures mechanisms whose CRYPTO-PERP application was
never tested — a validated 1998 FX mechanism + 2026 perp data is a *new hypothesis carrying decades
of prior evidence*, which is the highest-value class available here; (b) 2013-2017 early crypto
papers nobody replicated on modern regimes. This stratum is finite: once read, it is read. Sections
are claimed EXHAUSTED or PARTIALLY-MINED at the end, named for the next run (charter §30).

**Provenance discipline (binding).** The desk has already been burned once by a claim resting on a
search-result summary. Every item below states the EXACT URL opened and whether PRIMARY TEXT was
read or only an abstract/landing page. Anything resting on an abstract is flagged **ABSTRACT-ONLY**
and may not carry a verdict stronger than `needs-data-desk-lacks` / `unresolved`.

**Mandatory adaptation step.** No mapping, no card. Every surviving mechanism states EXACTLY which
desk data it needs (funding rate / open interest / long-short ratio / liquidation feed / cross-venue
books+trades / FRED macro / recorder microstructure). A mechanism with no data mapping is not a
card and is dropped explicitly.

**Mechanism test (binding).** WHO LOSES MONEY AND WHY DO THEY PERSIST. A mechanism with no
identified loser is a statistical pattern, not an edge, and is dropped.

**Graveyard priors loaded and binding** — any item matching these is dropped as
`dead-on-arrival (graveyard match)`: price-only alpha broadly (420 hypotheses / 0 survivors), retail
TA indicator stacks, short-term reversal, xsec low-vol (INVERTS in crypto — sign-flipping it is
p-hacking and is itself logged), **funding MOMENTUM** (distinct from funding CARRY LEVEL, which
survives), illiquidity premium, cross-exchange funding DISPERSION (corr 0.54 to carry), Fear&Greed
timing, vol-target and conditioning overlays generally, grid/ladder bots (short gamma), cross-venue
fiat-premium "arb" (rent on a capital-control barrier, not inefficiency), regional premiums other
than kimchi, options VRP (real but breadth-starved), OI divergence (hourly), long/short contrarian
(DSR-killed).

---

## DESK DATA INVENTORY (verified on disk this run, not remembered — the adaptation step needs it)

| Asset | Path | Shape / coverage |
|---|---|---|
| Perp funding, 2 venues | `data/hyperliquid_funding.parquet` | 14,812 rows; cols `timestamp, coin, hl_funding, bn_funding, spread` |
| OI + long/short + taker | `data/crypto_metrics.parquet` (3,791 rows) and `data/oi_ls_history.jsonl` (daily from 2021-06-01) | cols `open_interest, ls_ratio, taker_ratio` |
| OI/LS per-symbol universe | `data/lake/bronze/oi_ls_daily/*.jsonl` | ~1 file per USDT perp |
| **Liquidation stream** | `data/liquidations.parquet` | 33,642 rows; `ts, symbol, side, qty, price, notional` |
| Options surface | `data/deribit_surface.parquet` | only 66 rows — `atm_iv, skew, term, spot` (breadth-starved, matches the VRP kill) |
| **COT positioning (NON-crypto)** | `data/cot_zcache.parquet` | 8,405 rows x 11: XAU/XAG/XPT/XPD, EUR/GBP/AUD/JPY/CHF/CAD, XTI(WTI) |
| Cross-venue premia | `kimchi_premium.jsonl`, `cny_premium.jsonl`, `try_premium.jsonl`, `venue_premium_coinbase.jsonl` | |

**Endpoint audit (load-bearing for Card 1).** `scripts/dl_oi_ls_universe.py` / `collect_binance_metrics.py`
pull exactly three Binance futures-data endpoints: `openInterestHist`,
**`globalLongShortAccountRatio`**, `takerlongshortRatio`. They do **NOT** pull
`topLongShortAccountRatio` or `topLongShortPositionRatio`. The desk therefore holds the
*retail/impatient* side of the book and **not** the *large-trader* side — which is precisely the
trader-type split the entire hedging-pressure literature is built on. Both missing endpoints are
free, keyless, and in the identical URL family already wired.

---

## FINDINGS

_(appended as each mechanism resolves)_

---

### 1. HEDGING-PRESSURE DECOMPOSITION — the two-premium result (Keynes 1923 → KRT 2020)
**Verdict: `needs-data-desk-lacks` (one free endpoint away from `candidate-card`)**

**Mechanism — who loses money and why they persist.** Normal backwardation (Keynes 1923, Hicks 1939)
says hedgers who are structurally net short pay speculators to carry price risk; the speculator's
profit is an insurance premium, and hedgers persist in paying it because their loss function is
*operational* (they hedge a physical exposure) not *speculative* — they are price-insensitive by
mandate, which is why the premium never arbitrages away. Kang-Rouwenhorst-Tang's contribution is
that this is **two different premiums with opposite signs, operating at different horizons**, and
that mixing them is why the classical hedging-pressure tests came out "mixed". At the **short
(weekly)** horizon the *impatient* trader pays for immediacy: speculators demand liquidity, hedgers
supply it, so commodities heavily **bought by speculators earn LOWER** subsequent returns and those
**bought by hedgers earn HIGHER** ones. At the **long** horizon the classical insurance premium runs
the *other* way. Net: the level of hedging pressure has essentially no short-horizon predictive
content, but the *decomposition* does. The loser at the short horizon is the impatient
momentum-chasing speculator paying the immediacy premium; the loser at the long horizon is the
commercial hedger buying insurance. Both are structural, mandated, and non-learning.

**Original evidence.** Kang, Rouwenhorst & Tang, *A Tale of Two Premiums: The Role of Hedgers and
Speculators in Commodity Futures Markets*, JF 75(1) 377-417 (2020); working-paper text read in full.
Sample **26 commodities, NYMEX/NYBOT/CBOT/CME, 1994-01-02 → 2014-11-01**, weekly CFTC COT (positions
measured Tuesday, released Friday after the close). Effect sizes, quoted from the primary text:
- Hedging-pressure **level** at weekly horizon: Fama-MacBeth cross-sectional slope **t = −0.43** — no
  short-term predictability. *(This is the paper killing the naive version of its own signal.)*
- Position **changes**: an average hedger position change (3.5% of open interest) times the
  cross-sectional slope of 4.77% ⇒ **+0.168% next-week return, ≈ 9.1% annualised**. Parallel
  speculator calculation: 5.58% × 3.0% = **0.167%**, opposite sign.
- Event study around the COT release: top-vs-bottom quintile spread **+0.21% over days 1-4
  (t = 3.04)**, **+0.30% days 5-10 (t = 3.62)**, **+0.15% days 11-20 (t = 1.23)** — "**67 basis
  points during the four weeks**".
- Trader-type regressions (Newey-West, 4 lags): hedgers −0.66 (t = −34.45), speculators +0.52
  (t = 32.44), non-reportables +0.14 (t = 20.16) on contemporaneous returns — i.e. **speculators
  chase, hedgers fade**, overwhelmingly significant.
- **Conditioning that matters most for the crypto transfer**: predictability is *stronger* when
  hedgers face a **capital loss** and binding funding constraints (explicit "cost of liquidity
  provision is expected to be high" dummy in a panel regression with commodity fixed effects).
- Small traders (non-reportables) do **not** move subsequent returns — the effect is a
  *large*-trader phenomenon.

URLs opened: `https://www7.uc.cl/economia/finance_uc/docs/conferences/11th/Rouwenhorst-Tale%20of%20two%20premiums.pdf`
(**PRIMARY TEXT READ IN FULL** — the PDF uses a subset-font substitution cipher and had to be
zlib-decompressed and decoded inline; all figures above are quoted from the decoded body text, not
from an abstract). Journal record: `https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12845`.
SSRN landing `https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2449315` returned **HTTP 403** and
was NOT read.

**Backward ≥2 levels** (citations verified inside the decoded text, not from search summaries):
Keynes (1923) and Hicks (1939) supply normal backwardation; **De Roon, Nijman & Veld (2000)**, JF
55(3) 1437-1456 (`https://onlinelibrary.wiley.com/doi/10.1111/0022-1082.00253`, **ABSTRACT-ONLY**)
adds own-market *and cross-market* hedging pressure; **Rouwenhorst & Tang (2012)** is cited by KRT
itself as the source of the verdict that "the empirical support for the relation between hedging
pressure and the expected futures risk premium as predicted by the theory of normal backwardation
is **mixed**"; **Cheng & Xiong (2014)** observe hedgers trade far more than their fundamental
hedging demand implies; **Kaniel, Saar & Titman (2008)** is the methodological parent — the identical
"infer who provides liquidity from the sign of short-horizon return predictability after a position
change" design, run on NYSE individual investors; **Grossman & Miller (1988)** is the liquidity-provision
theory underneath. The overlooked reference here is **Kaniel-Saar-Titman**, not the famous Keynes
cite: it is the actual template, and it was built for equities, not futures.

**Forward.** KRT *is* the forward critique of De Roon et al. — it explains the earlier mixed results
as an aggregation error rather than a failed mechanism. Published 2020 in the JF; the desk should
treat the short-horizon leg as the more crowded one.

**Crypto-perp mapping — exact data required.** Perp funding is *structurally* a hedging-pressure
instrument: it is a continuously-observable, cash-settled price of net positioning imbalance, which
is what COT approximates weekly with a 3-day publication lag. Crypto is strictly **better** on
frequency and lag and strictly **worse** on trader classification. Required:
- HAVE: `open_interest`, `taker_ratio` (the *impatient/immediacy-demanding* flow — the direct
  analog of KRT's "propensity to trade", where speculators traded 9.38%/wk vs hedgers 5.40%/wk),
  funding level (`hl_funding`/`bn_funding`), `liquidations.parquet` (for the capital-loss condition).
- **LACK, and this is the binding constraint**: a *trader-type split*. The desk pulls
  `globalLongShortAccountRatio` only. KRT's entire result is that the aggregate is uninformative
  (t = −0.43) and only the *split* predicts. Needed: Binance
  `/futures/data/topLongShortPositionRatio` and `/futures/data/topLongShortAccountRatio` (free,
  keyless, same family as the three endpoints already collected). `top − global` is the crypto
  large-trader-vs-retail analog of commercial-vs-non-commercial.
- Horizon: **weekly**, on position *changes*, not daily on levels.

**Why it is NOT in the graveyard.** Nearest kills are `ls_contrarian` (backtest Sharpe 9.84,
DSR-killed as `overfit`) and `oi_divergence` (hourly, −1.21). Distinctions, stated plainly: (i) both
kills used the **aggregate** ratio the desk already has — which is exactly the series KRT shows is
*uninformative* (t = −0.43); (ii) both ran at daily/hourly horizon, KRT's effect is **weekly on
position changes**; (iii) neither used a **trader-type split**, which is the new dataset the
graveyard's own reopening rule ("a materially new mechanism *or dataset* is required") names. **Honest
adjacency warning:** the retail-fading direction overlaps `ls_contrarian`'s economic story, and the
desk must not let "new decomposition" launder a re-test of a DSR-killed signal. The defensible test
is the *spread* (top-minus-global), which is a series the desk has never held, at a horizon it has
never tested — not another construction on `ls_ratio`.

**Crowding risk.** HIGH on the short-horizon leg. Published in the JF, and "follow smart money /
fade retail" is a crypto-native retail meme with dashboards on every analytics site — the desk's own
prior (`kama_squeeze`: retail-canon signals arrive pre-arbitraged) applies. Per charter §8 the
published claim raises research PRIORITY and lowers nothing about credibility. The *less* crowded
leg is the capital-loss conditioning, which needs the liquidation feed and is not a dashboard metric.

**Falsifier.** Construct `top_ls − global_ls` weekly change; if its Fama-MacBeth/IC against
next-week cross-sectional perp returns is insignificant, OR if it fails `axis_screen`'s angle-20
de-contamination (same-period corr > 0.20 — likely, since positioning co-moves with returns and this
is the exact trap that killed `cm_mvrv` and `coinbase_premium`), OR if its z20 correlation to the
existing funding-carry book exceeds ~0.5 (the bar `cross-exchange funding dispersion` failed at
0.54), it is dead. Also dead if the effect concentrates entirely in the 4 days after a scheduled
data release — crypto has no COT-release event, so an effect that only exists around a
publication timestamp does not transfer.

---

### 2. EVANS-LYONS ORDER FLOW → EXCHANGE RATES
**Verdict: `dead-on-arrival` (the headline result is CONTEMPORANEOUS by construction; the
predictive version needs proprietary dealer data and failed its replication)**

**What it is.** Evans & Lyons, *Order Flow and Exchange Rate Dynamics*, JPE 110(1) 170-180 (2002),
NBER WP 7317 (1999). Daily DM/$ log changes regressed on **interdealer order flow** produce
**R² > 60%**, against the Meese-Rogoff benchmark of ~0; $1bn of net dollar purchases moves DM/$ by
**0.5%**. This is the deepest 1990s-2000s FX micro vein and the obvious temptation: crypto taker
flow is order flow, and the desk records it.

**Why it dies before the data mapping.** The 60% R² is a **same-period** regression — order flow on
day *t* explaining the return on day *t*. That is a price-*discovery* result, not a forecast. Ported
to crypto it produces exactly the artifact class the desk has already graveyarded twice: the
`coinbase_premium_timing` kill (in-sample Sharpe 2.7, same-day corr +0.256 → `timing_artifact`) and
the `cm_mvrv` kill (same-period corr 0.416). `axis_screen`'s angle-20 gate exists to catch precisely
this and would reject it mechanically. Sources opened: `https://www.nber.org/papers/w7317`
(**ABSTRACT-ONLY** — the NBER landing page), `https://ideas.repec.org/a/ucp/jpolec/v110y2002i1p170-180.html`
(**ABSTRACT-ONLY**).

**Forward critique — the free graveyard entry.** Sager & Taylor, *Commercially Available Order Flow
Data and Exchange Rate Movements: "Caveat Emptor"*, JMCB 40(4) 583-625 (2008)
(`https://econpapers.repec.org/RePEc:mcb:jmoncb:v:40:y:2008:i:4:p:583-625`, **ABSTRACT-ONLY**;
JSTOR record `https://www.jstor.org/stable/25096271`, paywalled, not read — §13 forbids
circumvention). They find **little evidence that interdealer order flow can forecast exchange
rates**, and cast "considerable doubt on the practical value to market practitioners of
**commercially available** customer order flow data". The distinction is the whole finding: the
forecasting content Evans-Lyons later claimed (2005 "Meese-Rogoff Redux") lives in **proprietary
end-user/customer** flow segmented by client type — data a dealer sees and nobody else does.
**Crypto taker flow is the commercially-available kind**: public, undifferentiated, available to
everyone on the same free endpoint. It is the exact category Sager-Taylor tested and rejected.

**Data mapping (stated, then dropped).** Would need: signed cross-venue taker flow from the recorder
plus `taker_ratio`. The desk HAS these. The mechanism still fails — this is a case where the desk
has the data and the *mechanism* is the thing that is missing, which is worth recording explicitly
so a future run does not re-open it on "but we have order flow now".

**Why it is NOT already in the graveyard.** It is not — the graveyard has no order-flow entry. This
adds one, sourced entirely from other people's published failure, at zero cost to the desk's
multiplicity budget.

---

### 3. HOW CARRY DIES — Brunnermeier-Nagel-Pedersen 2008 → Jurek 2009 → Daniel-Hodrick-Lu 2017
**Verdict: SPLIT. (a) return-timing leg = `discard (graveyard match: conditioning overlay on the
carry book)`; (b) the SKEWNESS/DIVERSIFICATION-FAILURE leg = `risk-model card`, testable on data
the desk already holds, and it contradicts an assumption the live book is built on.**

This is the highest-priority vein named for this run because the desk's ONE repeat survivor is a
carry strategy and this literature is specifically about *how carry dies*.

**Mechanism — who loses money and why they persist.** Carry is a *liquidity-provision* premium, not
a free lunch: speculators earn the interest differential in exchange for bearing the risk that
their own crowded position gets unwound. Brunnermeier-Pedersen liquidity spirals: a shock that hurts
speculators is *amplified* (funding constraint binds → unwind → price falls → margins rise →
unwind), while a shock that helps them is *not* amplified. That asymmetry mechanically manufactures
negative skewness. The loser is the leveraged carry trader who is forced out at the bottom; the
winner is whoever has unencumbered capital at that moment. They persist because each individual
trader faces *synchronization risk* (Abreu-Brunnermeier) — he does not know when the others unwind,
so holding on is individually rational right up to the crash.

**Original evidence — BNP (2008), NBER WP 14473. PRIMARY TEXT READ IN FULL** (URL opened:
`https://www.nber.org/system/files/working_papers/w14473/w14473.pdf`; the PDF is subset-font
encoded and was zlib-decompressed and decoded inline — every number below is quoted from the decoded
body text, not an abstract). Sample: 8 currencies vs USD (AUD, CAD, JPY, NZD, NOK, CHF, GBP, EUR),
daily Datastream, **1986–2006**; CFTC futures positions 1992–2006 for 5–6 currencies only.
- Cross-section: average skewness vs average interest differential, **R² = 81%** — an almost
  mechanical relation. JPY (funding currency) most positive skew; AUD/NZD (investment currencies)
  most negative.
- Table 3 (panel, country FE): interest differential predicts next-quarter **skewness −23.92
  (se 3.87) ⇒ t ≈ −6.2**, and the coefficient stays significant out to t+9. By contrast it predicts
  the *return* at only 2.17 (se 0.78). **The crash-risk result is far stronger than the return
  result.**
- Table 2, and this is the load-bearing number for the desk: skewness **does not diversify away**.
  Quarterly carry portfolio skew is **−0.700 with 1 long/1 short, −0.748 with 2/2, −0.977 with 3/3**
  — it gets *worse* with breadth. Sharpe 0.654 / 0.638 / 0.784.
- Table 9: currencies with *similar* interest rates co-move, controlling for correlated monetary
  policy and country-pair fixed effects — coefficient on |i₁−i₂| is **−10.89 (se 3.81)**, and
  **−13.41 (se 6.41)** with country-pair FE. Selecting on carry *induces* the correlation.
- Table 5: ΔVIX × sign(differential) predicts carry unwinding — ΔFutures_t **−1.47 (0.77)**,
  ΔFutures_{t+1} **−1.29 (0.57)**, contemporaneous carry return **−0.43 (0.11)**.
- Table 7 (portfolio): ΔTED_t → **next-week** return **−1.57 (se 0.56), t ≈ −2.8**; ΔVIX_t is
  contemporaneous only (−0.94, se 0.25) with **no** next-week power (−0.07, se 0.23).
- **BNP's own self-limitation, quoted, and it is the pivot of the crypto transfer:** the futures
  position variable is **driven out** by the past return. Table 4 col 1 has Futures_t at −0.26
  (se 0.12) on next-quarter skewness; add z_t and it flips to +0.13 (se 0.15), insignificant, while
  z_t is −3.34 (se 0.60). BNP: *"Perhaps the past return is a better measure of speculator positions
  given the problems with the position data from the CFTC."* They also concede CFTC futures are a
  small slice — *"much of the liquidity in the currency market is in the over-the-counter forward
  market"* — and that theirs is merely *"the best publicly available data"*.

**Forward ≥2 levels — REPLICATION SCAN, and it partially guts the headline story.**
1. **Jurek, "Crash-Neutral Currency Carry Trades"** (SSRN 1262934; JFE 113(3) 2014). Open-access
   author copy read: `https://static1.squarespace.com/static/5e6033a4ea02d801f37e15bb/t/5f6152c31a671e2e487587c8/1600213700526/jurek_currency.pdf`
   (**PRIMARY TEXT READ**, decoded inline). G10, Jan 1990–Dec 2007/08. Equal-weighted carry: 4.42%
   ann. excess return, 5.05% vol, **Sharpe 0.88**; 1999–2007 EQL 1.06 / SPR 1.35. Monthly skewness
   1990–2008 = **−1.62**, ~2× the magnitude of US equity or momentum. Then the kill: buying OTM FX
   options to hedge the crash leaves most of the return intact — **"at most 15–35% of the excess
   returns to currency carry trades can be interpreted as compensation for exposure to currency
   crashes"**, and to drive crash-hedged returns to zero *"would have required implied volatilities
   for out-of-the-money options to be nearly four times their actual observed values."* Crash risk
   is therefore NOT the explanation for the carry premium.
2. **Jurek's second, larger result, which almost nobody cites:** *"once portfolios are constrained
   to simultaneously maintain a zero net dollar exposure, excess returns to crash-neutral portfolios
   become negligible, and statistically indistinguishable from zero. Net dollar exposure is a key
   determinant of returns to currency carry trades."* The carry premium is substantially a
   **common-factor (short-dollar) beta**, not a cross-sectional selection alpha.
3. **Daniel, Hodrick & Lu, "The Carry Trade: Risks and Drawdowns"**, NBER WP 20433 (2014), published
   *Critical Finance Review* 6:211–262 (2017). Landing pages opened: `https://www.nber.org/papers/w20433`,
   `https://business.columbia.edu/sites/default/files-efs/pubfiles/6378/Daniel.Hodrick.Lu.Carry%20Trade.Critical%20Finance%20Review.2017.pdf`
   (**ABSTRACT/summary level only — flagged**). Independently reaches Jurek's conclusion by a
   different route: **dollar-neutral carry trades exhibit *insignificant* abnormal returns and carry
   all the negative skewness; the dollar-exposure component earns the significant abnormal return
   and has *minimal* skewness.** Two independent teams, same verdict: strip the common factor and
   the cross-sectional carry alpha largely disappears, while the skew stays behind.
4. **Jurek's 2008 event study is the risk-management finding.** Even monthly crash-hedged investors
   suffered in 2008 because the decline was *protracted and autocorrelated*, not a single jump:
   *"these dynamics appear at odds with those postulated by models of extreme, but rare, disasters,
   when viewed at the monthly frequency."* Quarterly hedging beat monthly by 1–2% ann. **A carry
   crash is a multi-week grind, not a gap.**
5. Jurek also independently reproduces BNP's Table 9 as a *by-product*: dollar-neutral carry
   portfolios have *higher* volatility than plain ones, *"which may be due to excess co-movement of
   the relatively high- (low-) interest rate currencies, limiting the amount of attainable
   diversification."*

**Crypto-perp mapping — exact data required.**
- (a) **DISCARDED LEG — return timing.** BNP Table 7/8's tradeable claim is "signed ΔTED predicts
  next-week carry return; signed VIX predicts it 2–8 quarters out." In crypto that is a FRED-macro
  regime gate bolted onto the live carry book. The desk has already killed this exact structural
  class twice: `vol-target overlay` (Sharpe 1.40 → **1.07**, HURTS) and
  `btc_correlation_regime_carry_conditioning` (EV 0.0003, "a conditioning overlay on the EXISTING
  carry book, not a new stream"). **Discarded without testing.** Recording it explicitly so a future
  run does not reopen it on "but this one is from the JEP/NBER".
- (b) **DISCARDED LEG — the underreaction VAR.** BNP's VAR says the FX rate under-reacts to an
  interest-rate shock and the carry return keeps accruing for ~15 quarters. The crypto version is
  "funding shock → keep holding" = **`funding_momentum`, graveyard, Sharpe −1.72.** Discarded.
- (c) **CARD LEG — carry-selection destroys its own diversification.** BNP Table 2 + BNP Table 9 +
  Jurek's volatility observation make one falsifiable claim the desk has never tested and which its
  live book *assumes away*: **a basket selected on high carry is more tail-concentrated than its
  correlation matrix implies, and adding legs does not fix it — it may worsen it.** The desk's
  `cashcarry_config.json` runs `top: 10, hold_top: 3000` — i.e. it explicitly buys breadth in the
  carry direction on the assumption that 10 legs diversify. Data required, **ALL HELD AND
  COVERAGE-AUDITED THIS RUN**: `data/lake/bronze/crypto/<SYM>/D1/*.parquet` — **267 symbols, daily,
  from 2019-09-08, with `funding`, `basis` and `taker_buy_frac` all non-null** (this, NOT
  `hyperliquid_funding.parquet`, is the research-grade funding panel; see the inventory correction
  below). `run_carry_crowding.py` already reads exactly this path. Test: (i) regress pairwise
  realized correlation of perp returns within non-overlapping 13-week windows on
  |funding₁ − funding₂| with symbol-pair fixed effects — BNP's Table 9 exactly, and the desk has
  strictly *better* data than BNP because funding is observed continuously rather than as a weekly
  survey; (ii) compute realized skewness of an equal-weighted top-k funding basket for k = 1,3,5,10
  and check whether skew improves or deteriorates in k. **Falsifier: if skew improves monotonically
  in k and the |Δfunding| correlation coefficient is insignificant, the mechanism does not transfer
  and this dies.**
- (d) **DIAGNOSTIC LEG (needs one decomposition, no new data) — the Jurek/DHL common-factor test.**
  Decompose realized carry P&L into (i) a "crypto dollar carry" component = equal-weight funding
  harvest across the whole liquid perp universe, and (ii) a selection component = top-10 minus
  universe. DHL+Jurek predict (ii) ≈ 0 alpha and all of the skew. If that holds in crypto, the
  desk's *top-10 selection step* is adding tail risk for no return and the honest simplification is
  a broader, flatter basket. This is an attribution of an existing book, **not** a conditioning
  overlay — it adds no gate and no regime switch — which is why it does not fall under the
  overlay kill.

**Why (c)/(d) are NOT in the graveyard.** Nothing in the graveyard tests *skewness* or *realized
diversification* as the dependent variable; every carry-adjacent kill (`funding_momentum`,
`oi_divergence`, `ls_contrarian`, vol-target) predicts *returns*. These are risk-model claims about
the book the desk already runs.

**Crowding risk.** MEDIUM-LOW for (c)/(d) — "carry has negative skew" is famous, but *"breadth does
not reduce it"* is the part practitioners routinely get wrong, and the desk is currently on the
wrong side of it by construction. HIGH for the discarded legs.

**McLean-Pontiff note.** BNP is 2008 and Jurek/DHL are its published refutations. The honest reading
is that the *return* half of BNP has already been decomposed away by two independent teams; only the
*risk-structure* half survives. That is exactly why the verdict here is a risk card, not an alpha card.

---

### 4. THE DESK'S OWN EDGE, ALREADY PUBLISHED AND ALREADY CAUSALLY COMPRESSED — BIS WP 1087
**Verdict: `candidate-card` (a REPLICATION-ON-DESK-DATA card for the desk's #1 self-identified
bottleneck) + a hard, dated, causally-identified CROWDING PRIOR the desk should be holding and is
not.**

This surfaced as the mandatory replication scan on vein (a) and is more important than anything else
found this run, because it is about the desk's live book rather than a candidate.

**What it is.** Schmeling, Schrimpf & Todorov, **"Crypto Carry"**, BIS Working Papers No 1087
(April 2023; **this version October 1, 2025**). URL opened:
`https://www.bis.org/publ/work1087.pdf` — **PRIMARY TEXT READ** (zlib-decoded inline). Open access,
BIS-published, no paywall. Note the authorship: Schmeling and Schrimpf are two of the four authors of
the canonical FX-carry-volatility literature (Menkhoff-Sarno-Schmeling-Schrimpf). **This is the FX
carry literature deliberately ported to crypto by the people who wrote it** — i.e. the exact
arbitrage this ground exists to find has already been performed on the desk's own strategy.

**Data.** Daily, **March 2019 – July 2024**, BTC and ETH. Spot, futures and options characteristics
from Skew and Coinmetrics. Annualized constant-maturity 1M and 3M basis on **Binance, OKEx, FTX,
Huobi, BitMEX, Deribit and the CME** (CME basis begins Aug 2020). Futures data include basis, volume,
open interest, and **buy and sell liquidations**.

**Mechanism — who loses money and why they persist (this is the cleanest statement of the desk's own
edge that exists anywhere).** Crypto carry is a large **negative convenience yield** — an
*inconvenience* yield on holding spot, the mirror image of commodities (Gorton-Rouwenhorst 2006,
Koijen et al. 2018), and analogous to the documented preference for swaps/futures over cash Treasuries.
Two forces:
1. **Demand**: smaller, trend-chasing, leverage-constrained investors buy futures because that is the
   only way they can get leveraged exposure (explicitly framed via Frazzini-Pedersen). Max leverage on
   crypto-native venues "sometimes exceeding 100" — far beyond commodities or S&P.
2. **Limits to arbitrage**: professionals cannot easily hold spot (regulatory), and even those who can
   face **no cross-margining** between the spot and futures legs, so the two legs must be funded
   separately and a basis move can force liquidation before convergence (explicitly Brunnermeier-Pedersen
   2009 funding risk). Their FTX illustration: a stated max loss of USD 30,000 on a futures position
   means **a $1m short futures position is liquidated after a 3% rise in BTC**.
The loser is the leverage-constrained retail long. They persist because the constraint is structural
(they cannot borrow to buy spot), not a mistake they can learn out of.

**Empirical facts, quoted with numbers.**
- Average annualized carry across exchanges **Apr 2019 – Jul 2024 ≈ 7% p.a.**, occasionally
  **exceeding 40% p.a.**
- Interest-rate variation explains essentially none of it; storage costs ≈ 0 ⇒ the residual is a
  large negative convenience yield.
- **COT evidence (the trader-type split, on crypto):** higher crypto carry is associated with a rise in
  **net long positions of smaller, presumably less sophisticated traders** in CFTC Commitments of
  Traders for CME bitcoin futures, who increase positions *"in times of strong price trends and
  heightened attention"*; **dealer intermediaries and leveraged funds take the opposite (short) side.**
- **Causal DiD #1 (demand side):** the introduction of CME **micro** bitcoin futures — a smaller
  contract, i.e. easier small-investor access — **significantly increased** CME carry relative to other
  exchanges.
- **Causal DiD #2 (supply/arbitrage side), and this is the number the desk needs:** the January 2024
  **spot bitcoin ETF** introduction **decreased crypto carry by ~3 percentage points across exchanges
  and by an additional ~5pp on the CME — "very large declines of 36% and 97% of the mean crypto
  carry, respectively."**
- **Risk of the futures leg:** severe drawdowns; crypto futures returns are *"about 17% per month"*
  volatile.
- **Table 7 — the replicable result:** regressing monthly buy/sell liquidations (as % of open
  interest) on lagged standardized basis, *"a rise in standardized carry by 10% predicts a **22%
  increase in total sell liquidations** (relative to total open interest) over the next month"*, and
  carry **significantly predicts only SELL liquidations, not buy** — exactly the asymmetry the
  mechanism requires, since the cash-and-carry trader is the short.
- Authors' own caveat, recorded: their liquidation series *"covers both forced and voluntary
  liquidations since the data provider does not distinguish"*.

**Crypto-perp mapping — exact desk data. VERDICT DOWNGRADED AFTER A COVERAGE AUDIT (see
§DATA-INVENTORY CORRECTION below): `needs-data-desk-lacks (forward clock)`, not immediately testable.**
- The regressor side is **fully covered**: `data/lake/bronze/crypto/<SYM>/D1/*.parquet` holds
  `funding` and `basis` daily for **267 symbols from 2019-09-08**, all non-null. That is a longer and
  wider panel than BIS's own (BTC+ETH, 7 venues, Mar 2019–Jul 2024).
- The **dependent** side is the blocker. `data/liquidations.parquet` is **not a history** — audited
  this run it is **33,867 rows over 17 days (2026-07-09 → 2026-07-26) across 15 symbols**. BIS
  regress *monthly* liquidations over ~5 years. The desk has under three weeks. A Table-7
  replication is **not runnable today** and any attempt would be a 17-day overfit.
- **Correct disposition: put it on a forward clock.** `scripts/liquidation_listener.py` is live and
  the feed accrues daily; the desk already uses exactly this pattern (`oi_divergence`: "forward clock
  continues (data still accruing)"). Pre-register the BIS specification NOW — standardized funding →
  next-month coin-denominated sell-liquidations / OI, sign-predicted **negative for buy-side and
  positive for sell-side only** — and let it mature. Pre-registering against a *published external
  effect size* (+10% standardized carry ⇒ +22% sell liquidations) is a far stronger test than the
  desk's usual self-generated null, because the alternative hypothesis is specified by someone else.
- When it is runnable, the desk's version will be **better-specified** than BIS's on two axes:
  (i) perps make funding a continuous observable rather than a 1M/3M constant-maturity interpolation,
  and (ii) BIS could not separate forced from voluntary liquidations — an exchange liquidation feed
  contains **only forced** ones, removing their stated confound.
- **CONSTRUCTION HAZARD, binding.** `notional = qty × price` puts price in the numerator. The desk's
  own `cm_mvrv` kill is precisely this failure ("the 20d z-score of a PRICE-NUMERATOR ratio is largely
  recent momentum in disguise"). **Normalize liquidations in COIN UNITS (`qty`) over coin-denominated
  OI, never notional over notional**, or the contamination gate will (correctly) reject it. BIS
  normalizes by open interest, which mostly handles this; the desk must do the same deliberately.
- **NAMED MISSING DATA, free and keyless:** `data/cot_zcache.parquet` holds XAU/XAG/XPT/XPD, EUR/GBP/
  AUD/JPY/CHF/CAD and XTI — **but no crypto**. The CFTC publishes CME **Bitcoin and Ether** futures COT
  weekly, free. **This is a second and better answer to the gap Finding 1 left open.** Finding 1 named
  Binance `topLongShortPositionRatio` as the trader-type split it lacks; CFTC crypto COT is the
  *literal same dataset* the entire commodity hedging-pressure literature is built on, with the same
  commercial/non-commercial/non-reportable classification, and BIS has already shown it carries signal
  on crypto carry. It is narrower (CME only, BTC/ETH only, weekly, 3-day lag) but it is the real thing
  rather than a proxy.

**Why this is NOT a graveyard match.** It is not a new alpha sleeve and not an overlay — it is a
*forced-exit risk model for the position the desk already holds*, with a published effect size to
compare against. The closest graveyard neighbour is `oi_divergence` (hourly, −1.21), which predicted
*returns* from OI at hourly frequency; this predicts *short-side liquidations* from *carry* at monthly
frequency, a different regressor, dependent variable, and horizon.

**The crowding prior the desk should be holding.** The desk's `run_carry_crowding.py` correctly
identifies secular funding compression as the #1 failure mode and measures it against *the strategy's
own pre-registered history*. BIS supplies something that internal history cannot: a **causally
identified, dated, one-time structural break** — Jan 2024 spot ETF ⇒ **−36% of mean carry across
exchanges, −97% on CME**. Consequences: (i) any backtest window spanning pre-2024 overstates forward
edge by a knowable amount and should carry an explicit haircut rather than a vibe; (ii) the desk's
compression detector, which benchmarks against its own history, will read a *permanent regulatory
level shift* as gradual crowding and may mis-attribute it; (iii) the mechanism says the remaining
carry is rent on the *cross-margining friction*, so the correct thing to monitor for the next leg down
is not competitor entry but **the arrival of spot-futures cross-margining / regulated prime
brokerage** — a discrete, watchable, calendar event, not a slow grind.

**Crowding risk.** HIGH and explicit. A BIS working paper, a Bloomberg headline in its epigraph
(*"The 'Risk-Free' Crypto Trade Is Back In a Big Way"*, 8 Oct 2021), and the desk's own prospector
already logged `hummingbot v2_funding_rate_arb.py` as commoditization evidence. Per charter §8 this
raises research priority and says nothing against credibility — but it does mean the *level* of carry
is a public, contested quantity and the desk should expect compression, not mean reversion.

---

### DATA-INVENTORY CORRECTION (audited on disk 2026-07-26, run 2) — READ BEFORE ANY ADAPTATION STEP

The DESK DATA INVENTORY at the top of this file lists **row counts, not coverage spans**, and that is
actively misleading for the adaptation step this ground exists to perform. Row counts on a live
recorder are tick counts over a few weeks. Audited spans:

| Asset | Rows | **True coverage** | Research-usable? |
|---|---|---|---|
| `data/lake/bronze/crypto/<SYM>/D1/*.parquet` | 2,514 (BTC) | **2019-09-08 → 2026-07-26, 267 symbols**, cols `open,high,low,close,volume,taker_buy_frac,funding,basis` — all non-null | **YES — this is the desk's real funding/basis/immediacy panel and the inventory omits it entirely** |
| `data/lake/bronze/oi_ls_daily/*.jsonl` | 139 files | **2021-12-01 → 2026-07-23**, daily `oi, ls, taker, oi_first, ls_first` | **YES** (~4.6y, 139 symbols) |
| `data/hyperliquid_funding.parquet` | 15,044 | **2026-06-26 → 2026-07-26 = 28 days** | NO at weekly+ horizons — it is a 2-venue spread recorder, not a funding history |
| `data/crypto_metrics.parquet` | 3,791 | **2026-06-22 → 2026-07-26 = 28 days** | NO |
| `data/liquidations.parquet` | 33,867 | **2026-07-09 → 2026-07-26 = 17 days, 15 symbols** | NO — forward-accruing only |
| `data/deribit_surface.parquet` | 66 | 2026-06-26 → 2026-07-26 = 25 days | NO (already known breadth-starved) |
| `data/cot_zcache.parquet` | 8,405 | wide frame, metals + G10 FX + WTI — **no crypto column** | YES for cross-asset, but holds no BTC/ETH COT |

**Consequences that bind on this ground.**
1. Every mechanism in the pre-2015 literature worth transferring is **weekly, monthly or quarterly**
   (KRT weekly on position changes; BIS monthly liquidations; BNP quarterly skewness; Coval-Stafford
   quarterly). Three of the four "positioning" assets the inventory advertises cannot support any of
   those horizons. **The binding constraint on this ground is history length, not mechanism supply.**
2. The two assets that *can* — bronze crypto `D1` and `oi_ls_daily` — are the ones the inventory
   describes least well. `taker_buy_frac` in the D1 lake is a **6.9-year, 267-symbol** daily
   immediacy-demand series; Finding 1 mapped KRT's immediacy leg onto `crypto_metrics.taker_ratio`,
   which is **28 days long**. Finding 1's data mapping should be re-pointed at `taker_buy_frac`
   before anyone tries to run it.
3. Any future run that writes "the desk HAS X" must state X's **span and symbol count**, not its row
   count. This is the same class of error as the `notional = qty × price` contamination trap: a
   number that looks like evidence and is not.

---

### 5. INVENTORY BEATS POSITIONS — Gorton-Hayashi-Rouwenhorst rejects hedging pressure outright
**Verdict: `graveyard-prior` (free, and it is a LEVEL-2 FORWARD CRITIQUE OF THIS FILE'S OWN FINDING 1)
+ one `cheap-gating-test card` runnable on data already on disk.**

**What it is.** Gorton, Hayashi & Rouwenhorst, *The Fundamentals of Commodity Futures Returns*,
NBER WP 13249 (2007), published *Review of Finance* 17(1) 35-105 (2013). URL opened:
`https://www.nber.org/system/files/working_papers/w13249/w13249.pdf` — **PRIMARY TEXT READ**
(zlib-decoded inline). Sample: **31 commodities with hand-collected monthly PHYSICAL INVENTORY data,
Dec 1969 – Dec 2006**; the CFTC Report-of-Traders panel (Table 10) runs **Dec 1986 – Dec 2006**.

**Mechanism.** Theory of Storage, not Theory of Normal Backwardation. The convenience yield is a
*decreasing, non-linear* function of inventories (non-linear because inventories cannot go negative).
When inventories are low, the marginal value of having the physical good *now* spikes, the curve
backwardates, volatility rises, and the risk premium rises. Positions are a *symptom* of this state,
not a cause of the premium.

**The kill, quoted verbatim from the abstract:** *"Positions of futures markets participants are
correlated with prices and inventory signals, but we **reject the Keynesian 'hedging pressure'
hypothesis** that these positions are an important determinant of risk premiums."* And from the body:
*"The main conclusion of this section is that contrary to the existing literature, **we find no
evidence that supports a hedging pressure explanation for risk premiums in commodity futures
markets.** Instead, we have shown that risk premiums systematically vary with the state of
inventories, as predicted by the Theory of Storage."*

**HOW it fails is the transferable part — Table 10.** Regressing monthly futures excess returns on
commercial net-long position / open interest: *"the slope coefficients are generally significantly
negative when hedging pressure is measured at the end of the return interval (i.e.,
**contemporaneously**), but **insignificantly different from zero** when hedging pressure is
measured"* at t−1. The entire prior hedging-pressure literature was a **same-period correlation**.
GHR then state the endogeneity problem explicitly: *"The contemporaneous correlation may simply
reflect the response of traders to changes in futures prices and does not speak to a causal
relationship,"* and *"these papers treat hedging pressure as exogenous, but it seems reasonable to
assume that traders positions reflect an equilibrium response to demand and supply shocks."* They
also observe *"non-commercials take larger long positions in high momentum commodities than in
commodities with poor prior performance"* — **positioning is largely a lagged transform of past
returns.** This is the identical observation BNP made independently in Finding 3 ("perhaps the past
return is a better measure of speculator positions").

**Relation to Finding 1 (does NOT kill it, but re-prices it).** KRT (2020) postdates GHR and is
partly an answer to it: KRT's claim is about weekly position *changes* with a *trader-type split*,
and KRT itself reports the *level* is uninformative (t = −0.43), which is exactly consistent with
GHR. So GHR kills the naive level version and sets the bar KRT must clear. What GHR adds to Finding 1
is a **strong prior that the crypto version will fail its de-contamination test** — which Finding 1
already conceded was "likely" — plus a named reason.

**Crypto-perp mapping — exact desk data.**
- **The positive claim maps directly and favourably, and this is unusual external validation of the
  desk's live book.** GHR's state variable is the **basis**, and they show price-based signals (basis,
  prior futures returns, prior spot returns) are informative *because* they reveal inventory. The desk
  holds `basis` and `funding` daily for **267 symbols since 2019-09-08** in
  `data/lake/bronze/crypto/<SYM>/D1/`, and its one surviving edge already trades exactly that
  variable. Crypto has no observable "inventory" — and GHR's whole point is that you do not need one,
  because the basis reveals it.
- **CHEAP GATING TEST, runnable today, ~1 day of work, and it gates a multi-week data project.**
  Before the desk wires `topLongShortPositionRatio` (Finding 1) or CFTC crypto COT (Finding 4), run
  the incremental test on data in hand: does `ls` / `oi` from `data/lake/bronze/oi_ls_daily/*.jsonl`
  (**139 symbols, 2021-12-01 → 2026-07-23**) add cross-sectional predictive power for next-period
  perp returns **over and above `funding` and `basis`**? GHR predicts no. A null here should
  **cancel** the positioning-data acquisition, not motivate a bigger version of it.
- **GHR's Table-10 diagnostic, run on the desk's own two positioning kills.** Regress perp returns on
  `ls_ratio` contemporaneously and lagged. If ls is significant contemporaneously and insignificant
  lagged — GHR's exact pattern — that is a *single named mechanical cause* for both `ls_contrarian`
  (backtest 9.84, DSR-killed as `overfit`) and `oi_divergence` (−1.21), converting two unexplained
  kills into one understood one and retiring the positioning family with a reason. This is
  cheap forensic work on existing graveyard entries, not a new hypothesis, so it costs nothing
  against the multiplicity budget.

**Backward ≥2 levels** (all cited inside the decoded GHR text): Kaldor (1939) / Working (1949) theory
of storage; Keynes (1923) / Hicks (1939) normal backwardation; **Fama & French (1987, 1988)** — the
interest-adjusted basis as an inventory proxy, metals 1972-83; Ng & Pirrong (1994); Deaton & Laroque
(1992); **De Roon, Nijman & Veld (2000)** — which Finding 1 cites as *support* for hedging pressure
and which GHR is explicitly overturning. Finding 1's reference list and this finding's reference list
are the two sides of an unresolved dispute; the desk should hold both.

---

### 6. THE PHANTOM FLOW VARIABLE — VPIN's failed replication, and why crypto is the exception
**Verdict: `graveyard-prior` for the imported VPIN / order-flow-toxicity family. But the specific
defect that killed VPIN does NOT exist in crypto data, which is worth recording precisely so the
prior is not over-applied.**

**What it is.** Easley, López de Prado & O'Hara's VPIN (volume-synchronized probability of informed
trading) was sold as a real-time order-flow-toxicity gauge that spiked before the May 2010 Flash
Crash. It is the single most-cited pre-2015 microstructure metric with an obvious crypto application,
and the desk's recorder makes it trivially constructible — so it *will* be proposed.

**The failed replication.** Andersen & Bondarenko, *VPIN and the Flash Crash*, CREATES Research Paper
2011-50; published *Journal of Financial Markets* 17: 1-46 (2014). URL opened:
`https://repec.econ.au.dk/repec/creates/rp/11/rp11_50.pdf` — **PRIMARY TEXT READ** (zlib-decoded).
Verbatim: VPIN *"is a poor predictor of short run volatility, ... it did not reach an all-time high
prior, but rather **after**, the flash crash, and ... its predictive content is due primarily to a
**mechanical relation with the underlying trading intensity**."*
- The order-imbalance component degenerates: *"as the speed of trading grows, the number of time bars
  in the bucket declines and there is less diversification of buy and sell indicators. In the limit,
  it becomes unity, irrespective of the actual price path"* — **"OI degenerates into a pure trading
  intensity measure."**
- **The root cause is the trade-signing scheme.** Bulk Volume Classification *"lets the size of the
  concurrent price change — a realized volatility measure — directly impact the buy–sell indicator.
  Effectively, it is a distorted volatility measure which combines trading intensity and price
  volatility in a nonlinear fashion"*, so *"BV-VPIN constitutes an imperfect realized volatility
  metric which, **by construction, will have forecast power, due to the persistence in the volatility
  process**."*
- **Honesty note:** Easley, López de Prado & O'Hara published a rejoinder (*JFM* 2014) and the dispute
  is genuinely two-sided; A&B were answered, not conceded to. The desk should treat VPIN as
  *contested*, which for a signal that must clear a de-contamination gate is functionally the same as
  dead.

**THE CRYPTO EXEMPTION — the genuinely new observation.** BVC exists because in equity and futures
tapes the *direction* of a trade is not published and has to be inferred from the price change. That
inference is the defect. **Crypto exchanges publish the taker side as ground truth.** Verified on
disk this run: `libs/data/crypto_source.py:61` builds
`taker_buy_frac = takerBuyQuoteAssetVolume / quoteAssetVolume` straight from the Binance kline — a
true exchange-reported trade signing, not an inference from returns. It is also *not* a
price-numerator ratio in the `cm_mvrv` sense: price appears in both numerator and denominator of the
same bar's quote volume and largely cancels. **The single defect Andersen-Bondarenko identify as the
source of VPIN's illusory forecast power does not exist in the desk's data**, and the series runs
daily for 267 symbols since 2019-09.
**But what survives is narrow, and the desk should not get excited.** Finding 2 already killed
public order flow → *return* prediction (Sager-Taylor: commercially-available flow does not forecast).
What is left is order flow → *risk* (volatility / liquidation-cascade prediction), which is (i) not
an alpha stream and (ii) blocked by the same 17-day liquidation history as Finding 4. Disposition:
**`graveyard-prior` for VPIN-as-imported; `unresolved / forward-clock` for a clean-taker risk model.**

---

### 7. COVAL-STAFFORD FORCED SELLING → WARDLAW'S CRITIQUE → crypto liquidation cascades
**Verdict: `discard-for-now` — data-blocked (17-day liquidation history) AND graveyard-adjacent
(`short_term_reversal`). Recorded with a precise pre-registration because the desk would otherwise
build the WRONG version of it.**

**What it is.** Coval & Stafford, *Asset Fire Sales (and Purchases) in Equity Markets*, NBER WP 11357
(2005), *JFE* 86(2) 479-512 (2007). URL opened:
`https://www.nber.org/system/files/working_papers/w11357/w11357.pdf` — **PRIMARY TEXT READ**
(zlib-decoded). US equity mutual funds, 1980-2003.

**Mechanism — who loses money and why they persist.** Funds hit by large capital outflows must
liquidate existing positions *immediately*. The sale is motivated by necessity, not information, so
it pushes price below fundamental value and reverts. The loser is the distressed fund; it persists
because meeting redemptions is a non-discretionary mandate. Coval-Stafford's own summary: *"even in
the most liquid markets there can be a significant premium for immediacy"* and *"short-run excess
demand curves for stocks appear to be less than perfectly elastic."*

**Numbers.**
- |flows| > 5% and ≥ **25%** of holders net selling: CAAR from month t−2 to t+3 = **−18.13%
  (t = −7.58)**, with a reversal of **+15.01% (t = 3.84)** over the next 3 quarters.
- |flows| > 10% and ≥ 15% net sellers: **−13.02% (t = −6.36)**, **full reversal +14.57% (t = 4.93)**.
- Calendar-time portfolio alphas to the piling-on strategy: **−0.47%/month (t = −2.15)** to
  **−0.84%/month**.
- **THE BREADTH CONDITION IS THE ENTIRE RESULT.** *Isolated* distressed selling gives only **−2.52%
  (t = −6.66)** and the authors themselves call the magnitudes *"fairly small"*: *"The key to the
  reversal appears to be that the selling is widespread among mutual funds that must immediately sell
  due to capital outflows. Moreover, the effect seems to be increasing in the number of net sellers
  and in the level of distress."*
- Timing: *"The price effects are relatively long-lived, lasting around two quarters and taking
  several more quarters to reverse."* **This is a slow effect, not a wick.**

**Replication scan.** Wardlaw, *Measuring Mutual Fund Flow Pressure as Shock to Stock Returns*,
*Journal of Finance* 75(6) 3221-3243 (2020). **SEARCH-SUMMARY-ONLY — flagged at the weakest provenance
tier.** Wiley (`https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12962`) returned **HTTP 403** and
the author page returned **403**; no open-access copy was found and §13 forbids circumvention, so this
is **not** primary text and carries only hazard weight, not a verdict. Reported finding: the standard
flow-pressure measure *is inadvertently a direct function of the stock's realized return during the
outflow quarter*; once the embedded return is removed, outflows produce a negligible decline **with no
subsequent reversal**, and many results in the literature no longer hold.

**Crypto-perp mapping, and the two reasons it is blocked.**
- **Crypto's genuine advantage:** the forced trade is *directly observed*, not imputed. The exchange
  publishes side and quantity of every liquidation (`data/liquidations.parquet`:
  `ts, symbol, side, qty, price, notional`). Wardlaw's specific defect — an *imputed* pressure proxy
  that secretly contains the realized return — is absent, because nothing is imputed.
- **Blocker 1 — history.** The feed is **17 days, 15 symbols** (audited above). Coval-Stafford is a
  quarterly event study. Not runnable, and a 17-day version would be a pure overfit.
- **Blocker 2 — a different route to the same contamination.** A liquidation is *triggered by* the
  price move, so liquidation intensity at t is mechanically a function of the return at t. Different
  cause from Wardlaw's, identical symptom, and it lands directly on the desk's angle-20 gate.
- **Blocker 3 — graveyard adjacency.** The naive construction ("fade the coin that just got
  liquidated") is `short_term_reversal`: **Sharpe −1.41, gross −0.48 unprofitable at ZERO cost.**

**The pre-registration worth keeping, because it is the part the desk would get wrong.**
Coval-Stafford's effect *does not exist* without the breadth condition. So the crypto construction is
**not** "fade the liquidated coin" — it is: *on days when forced selling is WIDESPREAD ACROSS THE
CROSS-SECTION (a count of symbols with liquidation intensity above threshold, not a single name's
magnitude), go long the names with the highest forced-sale intensity relative to their own open
interest, measured in COIN UNITS (`qty`, never `notional` — `notional = qty × price` reintroduces the
price numerator that killed `cm_mvrv`), and hold for weeks, not hours.* Revisit only when
`liquidations.parquet` has ≥ 12 months and ≥ 50 symbols.

---

### SYNTHESIS — the one law this run kept rediscovering

Four independent literatures, and three of the desk's own kills, are the same failure:

| Source | The "flow/positioning" variable | What it actually contained |
|---|---|---|
| GHR 2007 (Finding 5) | commercial net long / OI | significant **contemporaneously**, zero when lagged |
| Andersen-Bondarenko 2011 (Finding 6) | VPIN via bulk-volume classification | *"an imperfect realized volatility metric which, by construction, will have forecast power"* |
| Wardlaw 2020 (Finding 7) | mutual-fund flow pressure | *"a direct function of the stock's actual realized return"* |
| BNP 2008 (Finding 3) | CFTC speculator futures position | driven out entirely by past return z_t |
| Desk: `cm_mvrv` | 20d-z of market-cap ratio | same-period corr **0.416** |
| Desk: `coinbase_premium_timing` | venue premium | same-period corr **+0.256** |
| Desk: `bithumb_kr_premium` | KR premium | candle timestamped 1.6d ahead |

**The law: a variable that is supposed to measure WHO IS POSITIONED almost always measures WHAT THE
PRICE JUST DID.** The desk arrived at this independently and built the angle-20 gate for it; the
academic literature arrived at it three separate times between 2007 and 2020 and each time it
demolished a headline result. Two consequences worth carrying: (i) the desk's contamination gate is
not conservatism, it is the single highest-yield filter in this entire stratum and it should be
applied to *every* positioning proposal before any backtest; (ii) the contamination is why
"price-only alpha is dead (420/0)" is a **broader** claim than it looks — most "non-price" positioning
data is price data wearing a hat.

---
