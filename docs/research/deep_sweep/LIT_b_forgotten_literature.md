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
