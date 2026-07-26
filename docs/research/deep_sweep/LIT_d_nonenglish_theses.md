# [LIT-d] NON-ENGLISH ACADEMIC + THESIS MINING — deep sweep

_Opened 2026-07-26 by the literature deep-miner. **Write-as-you-go**: every item is appended the
moment it resolves, so a mid-run stop leaves durable output rather than a header. This ground
doubles as the run's ≥25% SEARCH-SPACE-EXPANSION reserve (charter §12)._

**Thesis of this ground (two under-mined layers).**
(A) OPEN NON-ENGLISH ACADEMIC INFRASTRUCTURE — CyberLeninka (RU), J-STAGE (JP), SciELO (BR/LatAm),
Chinese open-access + CN-author arXiv clusters, Korean open repositories (KCI/RISS open subsets),
plus native-language central-bank research (BOK/BOJ/PBoC). These corpora are invisible to
English-only search, so their mechanisms have not been arbitraged by the English-reading crowd.
(B) THESIS + DISSERTATION MINING — masters/PhD theses are the only literature genre CONTRACTUALLY
OBLIGED TO REPORT WHAT FAILED. That makes them free graveyard material and free hypotheses in the
same document.

**Highest-prior target on this ground:** Korean-language work on the KIMCHI PREMIUM. It is the
desk's one surviving regional-premium signal (IC +0.148, momentum-timing Sharpe 1.3, live forward
clock). Korean researchers have studied it far more than English literature has. The hunt is for
its DRIVERS, REGIME DEPENDENCE, DOCUMENTED DECAY, and any orthogonal Korea-specific variable —
NOT "trade the premium" (already established: information/timing signal only, never sized as an
arb — era evidence says a persistent cross-venue premium is rent on a capital-control barrier) and
NOT another Korean venue (Coinone tested → `redundant`).

**LICENCE GATE — ABSOLUTE (charter §13).** Open-access = adopt. PAYWALL-CIRCUMVENTED = NEVER, under
any circumstance: no Sci-Hub, no LibGen, no shadow library, no community mirror of a paid
institutional database. CNKI and Wind are EXCLUDED as paywalled giants — but authors'
self-archived preprints, open institutional-repository copies, and open-access equivalents are
fair and rich, and are hunted first. A paywalled item with no open copy is recorded as a
`residual-gap` and abandoned in place.

**Provenance honesty convention (binding, charter §8/§9).** The desk has been burned by a claim
sourced from a search snippet alone. Every item states the EXACT URL opened and the LANGUAGE of
the source:
- `[FETCHED-PRIMARY]` = full text opened and read.
- `[ABSTRACT-ONLY]` = only abstract / landing page read.
- `[MT]` = read via machine translation (stated explicitly wherever it applies).
- `[SEARCH-SUMMARY]` = search snippet only — a LEAD, never evidence; cannot carry a verdict
  stronger than `unresolved`.

**Mechanism test (binding).** WHO LOSES MONEY AND WHY DO THEY PERSIST. A finding with no
identified loser is a statistical pattern, not an edge, and is dropped. No mapping to concrete
desk data → no card.

**Graveyard priors loaded and binding** (matching items are `confirms-existing-kill`, noted once and
never re-queued): price-only alpha broadly (420 hypotheses / 0 survivors), retail TA indicator
stacks, short-term reversal, xsec low-vol (INVERTS in crypto), funding MOMENTUM, illiquidity
premium, cross-exchange funding DISPERSION, Fear&Greed timing, vol-target/conditioning overlays,
grid/ladder bots, cross-venue fiat-premium "arb", regional premiums OTHER than kimchi
(JP/BR/TR/Coinbase all dead), multilingual Wikipedia/search-attention at daily horizon (en/ja/ko/
ru/zh all screened weak — search-trends attention may NOT be re-proposed as a daily signal), DeFi
TVL/volume/fee aggregates at daily horizon, price-numerator ratios (MVRV/NVT/Mayer) z-scored
daily, commit-velocity dev momentum.

**Anti-breadth-theater clause.** A list of repository names with no mechanisms extracted is
BREADTH-THEATER and is a scored defect. Region parity (§14) means mining non-English with the SAME
DEPTH as English. If this session produces a catalogue instead of mechanisms, that is stated
plainly in the closing section.

---

## FINDINGS

_(appended as each item resolves)_

---

### D-1 — KIMCHI-PREMIUM DRIVER DECOMPOSITION: on-chain settlement friction is ~29% of the premium's variance, and the FX channel is ZERO
**(the single most actionable item on this ground)**

**Mechanism.** The Korea premium is not one thing. Yang (2019) regresses the Korbit-vs-Bitstamp
BTC price difference on three competing families and finds the *limits-of-arbitrage* family — BTC
**mempool pending-transaction count** and **on-chain cost per transaction** — is a large, highly
significant driver on its own. The economics are physical, not informational: to compress a Korea
premium an arbitrageur must move actual BTC onto a Korean venue, and when the mempool is deep and
the fee-per-tx is high, that leg is slow and expensive, so the correcting flow does not arrive and
the premium is mechanically allowed to widen. The loser is the would-be arbitrageur who is
*prevented*, not a mispricing victim — which is exactly why the friction persists rather than being
competed away: it is a settlement-technology constraint, not a behavioural one. **The consequence
for this desk is the opposite of a new alpha: it is a CONTAMINANT to strip.** Roughly a third of
the premium's variance is congestion noise carrying no Korean information at all, so the desk's
live kimchi signal is currently a blend of (a) Korean demand/positioning information — the part
that earned IC +0.148 — and (b) Bitcoin settlement congestion, which has already been independently
killed as a daily return predictor in the on-chain-activity family. Orthogonalising the premium
against mempool depth + fee-per-tx should raise the signal's information ratio *without adding a
new axis*, and is the cheapest possible improvement to a live clock.

**The FX channel is empirically empty in this sample, which kills a competing story.** Model 1 —
all four "rational market-segmentation" variables (US Dollar Index change, KRW/USD change,
KOSPI−S&P500 return difference, KR−US BTC volume-growth difference) — has **Adj. R² = 0.000** and
*not one* significant coefficient. This directly contradicts the popular "kimchi = FX/capital-
control demand" narrative and contradicts Cho/Park/Ahn (2023, D-2 below), which builds an entire
trading strategy on an FX→premium linear regression.

**Source.** 양철원 (Yang Chul-Won), 「비트코인의 국내외 가격차이를 이용한 차익거래에 관한 연구」
(A Study on the Arbitrage Trading Using the Price Difference of Bitcoin), 자산운용연구 (Asset
Management Review) Vol.7 No.2, Dec 2019, pp.1–20. DOI 10.23007/amr.2019.7.2.1.
Open PDF (KCI, no login): https://journal.kci.go.kr/capm/archive/articlePdf?artiId=ART002549675
**Language: Korean.** Open-access via the KCI national repository (Korea Citation Index is
publicly funded and serves this PDF without credentials). `[FETCHED-PRIMARY]` — full Korean text
extracted from the PDF and read directly (no machine translation of the results tables; the
regression table was read as printed).

**Evidence (read from the paper's own Table 3 / Table 4).**
- Sample: daily, 2015-07-01 → 2018-12-31, n = 1,280 days. KRW price = **Korbit**; USD price =
  **Bitstamp**; both taken at 00:00:00 UTC (the paper states the UTC timestamp explicitly — note
  this is the same timezone-alignment hazard that produced the desk's `bithumb_kr_premium_lookahead`
  kill, and Yang handled it correctly). FX from Bank of Korea. On-chain from Blockchain.com.
- Premium level: mean **+$223**, sd **$803**, min **−$307**, median **+$20**, max **+$8,358**.
  The median being near zero while the mean is $223 is the whole story — the premium is a rare
  fat-tailed episode, not a standing level.
- Model 1 (rational/FX): Adj. R² **0.000**. USD index Δ β=−0.439 (t −0.858); KRW/USD Δ β=−0.545
  (t −1.202); market-return diff β=−0.095 (t −0.433); BTC volume-growth diff β=−0.008 (t −1.345).
  **All insignificant.**
- Model 2 (attention): Google-Trends difference (KR minus US) β=**0.503, t=21.05***; Naver Trends
  β=**0.278, t=10.59***. Adj. R² **0.367**.
- Model 3 (limits-of-arbitrage): cost-per-transaction β=**0.062, t=11.40***; **mempool pending-tx
  count β=2.177, t=16.66***. Adj. R² **0.293**.
- Combined: Adj. R² **0.447** (n=636) and **0.491** (n=981); in the full model the limits-of-
  arbitrage variables SURVIVE (cost/tx t=5.18; mempool t=11.51) alongside attention.
- **Critical caveat, stated plainly: every regression is CONTEMPORANEOUS** (same-day explanatory
  variables on the same-day premium). This is a variance-decomposition of the premium, NOT a
  forecast of it, and it must not be read as a predictive result.

**Crypto-perp mapping (exact desk data).** Everything needed is already free and mostly already
collected. (1) Existing Upbit/Binance kimchi series (live). (2) BTC **mempool pending-tx count**
and **fee-per-transaction**, daily — free from blockchain.com charts API, mempool.space, or
Blockchair; the desk has previously touched on-chain activity metrics so the collector pattern
exists. (3) Construction: regress the kimchi z-score on contemporaneous mempool depth + fee/tx,
take the RESIDUAL as the "Korean-information premium", and screen the residual against the raw
premium on the existing forward clock. Nothing new must be built beyond one daily on-chain series.
**Missing: nothing.**

**Graveyard check.** Genuinely distinct, and deliberately NOT a re-proposal of a dead thing.
Mempool/on-chain-fee metrics as a *direct daily return predictor* are dead (on-chain activity
family, per the `defi_health` entry's note) — this item does not resurrect them; it uses them as a
**nuisance regressor to be projected OUT of a live signal**, which is the opposite operation. Not
"another Korean venue" (Coinone → `redundant`); not "trade the premium as arb" (era kill). The
attention result *confirms an existing kill*: Google/Naver attention explains the premium
**contemporaneously** (R²=0.367) — precisely consistent with the desk's own finding that
multilingual attention *co-moves with* rather than *leads* daily returns. That agreement is
corroboration, not a reopening: search-trends attention stays dead as a daily signal.

**Verdict:** `candidate-card` — *"kimchi premium orthogonalised to on-chain settlement friction"*.
A refinement of the desk's single best live axis, with a documented mechanism, free data, and no
new venue. Plus an embedded `confirms-existing-kill` on attention-as-daily-alpha.

---
