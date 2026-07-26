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

### D-2 — THE OPPOSING KOREAN PAPER REFUTES ITSELF: a peer-reviewed 4,709x "kimchi arbitrage" is a STALE-KOREAN-LEG artifact, and its own regression table reports the FX channel at R²=0.032
**(resolves the forward-reference left dangling in D-1; independently reproduces the desk's own `bithumb_kr_premium_lookahead` kill inside published literature)**

**Mechanism — three separate failures, each of which the desk has already named.**

*(1) The headline result is a stale-price artifact, and the paper prints the evidence itself.*
The strategy is: buy BTC on Upbit with KRW → transfer → sell on Binance for USDT → wait → buy back
on Binance → transfer → sell on Upbit. Reported result over 2020-01-01 → 2023-04-06: **RoR
4,709.85x** (official FX), **4,932.49x** (unofficial FX), **4,535.67x** (LSTM FX), on 380 trades
(=190 round trips), mean per-cycle RoR ≈ **1.0466**. A 4,709x on a 3.3-year window is the desk's
"fat Sharpe is a tell" pattern, so the worked example in Table 4/Table 5 was reconstructed
arithmetically. It does not survive:
- Row 3 of Table 4 reports a kimchi premium of **−5.4917%** on 2020-01-04. A 5.5% *Korea discount*
  never happened; the true Jan-2020 premium sat around +1–3%.
- Back out the implied USD price of their Korean leg: 8,038,000 KRW ÷ 1157.94 = **$6,941**. BTC was
  ~$6,941 on **Jan 2**, not Jan 4. Their Binance column on the same row is **7,345**, which is the
  **Jan 3** close. Repeat for every row: binbtcprice = 7195.24 / 6965.49 / 7345 / 7354.19 = the
  Jan 1 / Jan 2 / Jan 3 / Jan 4 closes, on rows labelled Jan 1 / Jan 3 / Jan 4 / Jan 5.
  **The Korean leg is stale by roughly one day relative to the Binance leg.**
- Therefore their "premium" ≈ **minus the previous Binance daily return**, and the trading rule
  ("enter when the premium is far below its predicted level") is mechanically *"buy right after
  BTC has just rallied on Binance"*, exiting one day later when the stale Korean leg catches up.
  The paper's own second cycle is exactly this: enter at premium −5.49% on 2020-01-04, exit at
  −0.47% on 2020-01-05, +5.03% gross. That +5% *is* the 2020-01-03 Soleimani BTC rally (+5.1%),
  re-labelled as arbitrage profit. **The 4,709x is a one-day lookahead on the Korean leg,
  compounded 190 times.**
- Arithmetic cross-check that it is not premium capture at all: Korea's premium standard deviation
  is ~1.4% (desk's own measurement, per the `try_premium_timing` entry). Harvesting **+4.6% net per
  round trip, 190 times**, out of a series whose own sd is 1.4%, is impossible from mean reversion.
  The P&L has to be coming from somewhere other than the premium, and it is: price staleness.

*(2) Their FX regression AGREES with Yang (D-1) and the authors mis-read their own table.*
Table 2: **R-square 0.032**, F 66.96, prob 4.86e-16. Table 3: intercept 0.2118 (t 39.060), exchange
rate coefficient **−0.0002** (std err 1.98e-05, **t −8.183**, p 0.000). The narrative around it
says, in the same paper, both *"상관계수가 0.032로서 … 낮은 상관관계가 보인다"* ("a correlation of
0.032, i.e. a LOW correlation") and later *"환율과 김치프리미엄은 꽤 유의한 상관관계가 있음을
확인하였다"* ("we confirmed exchange rate and kimchi premium have a QUITE SIGNIFICANT correlation").
Both cannot be true. With n≈2,000 daily obs a t of −8.18 is trivially attainable on 3.2% of
variance; the authors converted **statistical** significance into **economic** significance by
assertion. **So D-1 and D-2 do not actually disagree.** Yang's Adj. R² = 0.000 on a four-variable
FX/segmentation block and Cho–Park–Ahn's R² = 0.032 on a one-variable FX block are the *same
finding measured twice*: the FX channel into the kimchi premium is, for practical purposes, empty.
The disagreement is between Cho–Park–Ahn's conclusion and Cho–Park–Ahn's own Table 2.
Note also the coefficient's **sign is negative** — a WEAKER won predicts a SMALLER premium — which
is the reverse of the popular "capital-flight / weak-won → premium" story that circulates in
Korean retail commentary. At 3.2% R² this is best read as the 2017-21 strong-won-plus-big-premium
era sitting next to the 2022 weak-won-plus-dead-premium era, i.e. two regimes, not a mechanism.

*(3) All three "models" collapse to the SAME static threshold, so the model comparison is empty.*
Eq. (6) defines the "unofficial exchange rate" as `upbtcprice_krw / binbtcprice_usdt`. Verified
against their Table 6: 8,343,000 / 7,195.24 = **1,159.51**, printed 1,159.517; and official FX
1155.07 × (1 + 0.00385) = **1,159.52**. So the unofficial rate is *identically* the official rate
times one-plus-the-premium — **Strategy 2 regresses the premium on a linear function of itself.**
Substituting, its entry rule reduces to a fixed level test, `premium < ~0.0208`. Strategy 1's input
(official KRW/USD) moves slowly, so it is the same threshold with a slow drift. And Strategy 3's
LSTM prints 1149.394 / 1148.538 / 1148.625 / 1148.915 on four consecutive days — a **0.86-KRW
range against an actual FX of 1155–1158** — i.e. the network output is a near-constant, which via
the same regression is a *constant* threshold ≈ 0.0257. The 4,536 / 4,710 / 4,932 spread across
"three strategies" is therefore threshold tuning across three near-identical constants, not
evidence about FX or about deep learning.

*(4) Free negative result on FX forecasting, from the paper's own metric.* Validation-set
**MSE 253.688** on a level of ~1,150 ⇒ RMSE ≈ **15.9 KRW ≈ 1.4%**. Daily KRW/USD realised moves are
~0.4%, so a random walk beats this LSTM by roughly 3.5x, using 10 macro predictors (USD index
%IncMSE 19.68, KRX100 12.22, KOSPI 11.14, KRX Steel 8.29, CAC40 7.30, DAX 7.22, EUR 6.79, NIKKEI
6.57, CNY 4.94, SSEC 4.83). **Deep-learned daily FX forecasting adds nothing to a Korea-premium
model** — which is the same conclusion D-1 reached from the other direction.

**Who loses money and why they persist.** The loser is the Korean retail arbitrageur who reads
this (or one of the many Korean blog posts that recycle "논문으로 검증된 김치 프리미엄 차익거래")
and runs the Upbit↔Binance BTC loop. They lose to the three things the paper explicitly deletes,
and its own limitations section names two of them: *"이 분석에서는 거래의 슬리피지 및 … 최소 전송
단위를 고려하지 않았다"* (slippage and minimum transfer size not considered) and *"BTC 현물의 전송
시간에 대해서도 반영하지 못했는데"* (**BTC transfer time was not reflected**). Deleting transfer
time is not a rounding error — D-1 showed that on-chain settlement friction *is* ~29% of the
premium's variance, and congestion is worst exactly when the premium is widest, so real transfer
latency is **adversely correlated with the trade**. The third deleted item is never mentioned at
all: Korean capital controls, bank real-name-account rules and travel-rule limits on repatriation,
which is the desk's standing `era_crossvenue_fiat_premium_arb` mechanism — a persistent cross-venue
premium is rent on a barrier, not an inefficiency. The behaviour persists because the paper cleared
peer review with a 470,900% backtest, no walk-forward, no cost sensitivity and no settlement model.

**Source.** 조기정 · 박종현 · 안현철 (GiJeong Cho, Jonghyun Park, Hyunchul Ahn — Graduate School of
Business IT, Kookmin University), 「김치프리미엄과 환율 변동 예측을 활용한 가상화폐의 통계적
차익거래 연구」 (*A Study on Statistical Arbitrage Transactions of Cryptocurrency Using Kimchi
Premium and Exchange Rate Fluctuations Prediction*), 한국산학기술학회논문지 (Journal of the Korea
Academia-Industrial Cooperation Society) **Vol.24 No.10, pp.354–363, Oct 2023**.
DOI 10.5762/KAIS.2023.24.10.354.
Open PDF (publisher's own site, no login): https://www.kais99.org/jkais/journal/Vol24No10/vol24no10p041.pdf
KCI landing: https://www.kci.go.kr/kciportal/landing/article.kci?arti_id=ART003011145
**Language: Korean.** Open access from the issuing society. `[FETCHED-PRIMARY]` — full 10-page
Korean text extracted from the PDF and read directly; every number above is read off the printed
Tables 1–7, and the staleness diagnosis was derived arithmetically from Table 4/Table 5, not from a
summary. (DBpia also indexes it — **DBpia is paywalled and was NOT used**; the society's own open
PDF was.)

**Crypto-perp mapping (exact desk data) — this one produces an AUDIT and a RAIL, not a signal.**
1. **Audit executed this session, result CLEAN.** The desk's live kimchi collector
   (`scripts/collect_kimchi_premium.py`) keys Upbit off `candle_date_time_utc` from
   `/v1/candles/days`. Probed the endpoint live: `utc=2026-07-26T00:00:00 | kst=2026-07-26T09:00:00`
   — Upbit's daily candle boundary **is UTC midnight**, so the Upbit leg is genuinely UTC-aligned
   with the Binance `interval=1d` leg (which the collector converts via
   `datetime.fromtimestamp(ms/1000, tz=UTC)`). **The desk's live kimchi clock does NOT have the
   Cho–Park–Ahn defect.** Recording this as a positive verification rather than leaving it assumed
   — it is the single check that keeps the desk's best live axis credible.
2. **Residual exposure worth one look (not a new axis):** the FX leg is Yahoo `KRW=X interval=1d`,
   whose daily bar boundary is *not* documented as UTC. The kimchi premium's denominator is
   `binance_usd × KRW/USD`, and a stale FX bar injects the same class of error at ~1/4 the
   magnitude. Cheap cross-check: diff Yahoo `KRW=X` daily closes against the **Bank of Korea ECOS**
   official daily rate (free API, logged as data loot below) for 250 days.
3. **Generalised rail (the transferable part):** *any* venue-premium series built from two venues'
   DAILY candles must be validated by regressing the premium on the **foreign leg's own same-day
   and prior-day return**. If |corr| to the prior-day foreign return is large and negative, one leg
   is stale. This is a strictly stronger test than the desk's existing same-day de-contamination
   check, which measures corr(z, same-day BTC ret) and would **not** have caught this paper: a
   one-day-stale Korean leg makes the premium track the *prior* day's return, so it can pass a
   same-day screen and still be pure lookahead. **Add the t−1 lag to the de-contamination battery.**
4. Data needed: none new. All three items run on series the desk already collects.

**Replication scan.** No independent replication of the 4,709x exists, and it cannot be replicated
because the defect is in the input alignment, not the method. The paper's *regression* result,
however, is now replicated three ways: Yang 2019 (D-1) Adj. R² 0.000 on the FX/segmentation block;
Cho–Park–Ahn 2023 R² 0.032 on FX alone; and 오정훈 (J.H. Oh) 2019, "The determining factors of
kimchi premium in the cryptocurrency market", *Global E-Business Association* 20(2) 215–228
(DOI 10.20462/TeBS.2019.4.20.2.215) — cited by this paper as ref [11] as the source of the "FX is
the most important driver" claim, i.e. the claim's origin is a *citation chain*, not a replicated
measurement. Treat "FX drives the kimchi premium" as **folk belief with a citation trail and no
supporting R²**.

**Graveyard check.** `confirms-existing-kill` ×3, and no new hypothesis is proposed:
(a) `bithumb_kr_premium_lookahead` — same defect class (Korea-vs-Binance daily-candle timestamp
misalignment producing an impossible Sharpe), here with the **stale** sign instead of the **ahead**
sign, found in *peer-reviewed literature* rather than in the desk's own harness. The desk's
hardened-harness rail (|IC|>0.35 or best Sharpe>6 → SUSPECT-LOOKAHEAD) would have flagged this on
sight; a Korean journal's referees did not. Strong external validation of that rail.
(b) `era_crossvenue_fiat_premium_arb` — the paper is a modern, academic instance of exactly the
2013 Bitcointalk error: the premium is treated as free money while the barrier (transfer time,
transfer minimums, capital controls) is assumed away. Era evidence and 2023 academic evidence now
agree.
(c) `cm_mvrv_btc_daily_level` / the contamination family — a third instance of "impressive backtest,
contaminated construction", reinforcing that de-contamination must run **before** any performance
number is believed.

**Verdict:** `confirms-existing-kill` + `rail-upgrade`. Not a card and deliberately not a
hypothesis: its value is (i) a live-clock audit that came back CLEAN and is now on the record,
(ii) one concrete strengthening of the de-contamination battery (add the **t−1 foreign-leg lag**),
and (iii) it closes D-1's dangling forward reference by showing the two papers agree that the FX
channel is empty. Also logged: **do not re-mine the Korean FX→kimchi regression line of work** —
three papers, one folk belief, zero R².

---

### D-3 — JAPAN: a REGULATOR-AUDITED long/short positioning panel nobody uses, and a tax code that makes its cohort a structurally identified loser (with a dated 2028 regime break)
**(the Japanese ground's real yield — not a premium, so the JP-premium kill does not touch it)**

**Mechanism — WHO LOSES MONEY AND WHY THEY PERSIST, from the Japanese tax code itself.**
Japanese retail crypto traders face a payoff the rest of the world does not:
- Gains are 雑所得 (**miscellaneous income**), taxed on the **progressive** scale — up to 45% national
  + 10% inhabitant tax = **55% marginal**.
- Losses **cannot** be offset against any other income category, and — the load-bearing part —
  **cannot be carried forward at all**. *"雑所得の損失は損益通算の対象外である"*. An unused loss is
  simply **forfeited** at year end. Only within-year crypto-vs-crypto netting is permitted.

Write the after-tax expectation for a zero-alpha trader taking a symmetric ±X gamble:
`E = 0.5·(1−0.55)·X − 0.5·X = −0.275·X`.
**The tax code alone imposes a ~27.5% expected loss on a fair bet, before a single basis point of
spread, fee or funding.** The state takes 55% of the upside and shares 0% of the downside, with no
carryforward to smooth it. A return-maximising participant facing this should not trade at all.
A large Japanese retail cohort nonetheless trades **on margin**, which makes it a *structurally
identified* noise-trader population — identified not by inference from its returns (circular) but
by a published statute that guarantees its expectation is negative.

**Why it persists, specifically.** The penalty is invisible at trade time and arrives at the
March 15 filing, one to fifteen months after the decision that caused it; the no-carryforward rule
punishes *taking the loss* rather than *holding it*, so the rational response inside the code is to
hold losers indefinitely — the tax system manufactures disposition-effect behaviour by statute; and
the leverage cap on Japanese regulated venues is marketed as prudential protection, which frames a
capped-leverage product as safe rather than as negative-expectation-after-tax. None of these are
learnable from price data, and none appear in English-language crypto literature.

**THE DATA THAT MEASURES THIS COHORT — and it is genuinely rare.**
一般社団法人日本暗号資産等取引業協会 (JVCEA, Japan Virtual and Crypto assets Exchange Association) —
the JFSA-designated self-regulatory organisation — publishes **月次統計 (monthly statistics)** covering
**every licensed Japanese exchange in aggregate**. Verified by downloading and parsing the March-2025
release directly. Fields confirmed present in the file's own column headers:
- 現物取引 数量 / 金額 (spot volume, quantity and value)
- 証拠金取引 数量 / 金額 (margin trading volume)
- **証拠金取引建玉残高: 売建数 / 買建数 / 合計** — **SHORT and LONG open-interest counts, reported
  separately**, plus 売建額 / 買建額 / 合計 (short/long OI value)
- 利用者預託金残高: 暗号資産 / 金銭等 / 合計 (customer deposits, split crypto vs **fiat**)
- 利用者口座数: 設定口座 / 稼働口座 (accounts opened vs **active**), split spot vs margin
- Per-coin breakdown (BTC / ETH / XRP and others), 金額 in millions of JPY
- Footnote states the convention explicitly: *"利用者預託金残高、証拠金取引建玉残高、利用者口座数は、
  各月の末日時点の数値です"* — **deposits, margin OI and account counts are MONTH-END stocks**, while
  volumes are month-total flows. (Alignment convention captured now, before any use — this is the
  same discipline that D-2 shows a peer-reviewed paper skipped.)

**Why this is not just another positioning feed.** Every long/short ratio the desk currently has is
**exchange-self-reported** and unaudited — the venue publishing it also profits from the flow it
describes, and has no obligation to define "long/short account" consistently. JVCEA's series is
compiled by a **self-regulatory body from member filings under a JFSA designation**. To the best of
this session's search, it is the **only regulator-supervised, venue-aggregated long/short open-interest
series published for any crypto market anywhere.** That property, not the frequency, is its value.

**Crypto-perp mapping (exact desk data) — highest use is VERIFICATION, not signal.**
1. **Primary use — audit the desk's long/short feed (OP-008 class, cheap and decisive).** The desk
   already ingests exchange long/short ratio. Restrict to BTC, resample the desk's L/S series to
   month-end, and diff against JVCEA's 売建数 vs 買建数 over 2018-09 → present (~94 months). This is
   the first opportunity the desk has had to check an exchange-reported positioning feed against an
   **audited** one. Two outcomes, both worth having: they track (the L/S feed is credible, upgrade
   its grade) or they don't (the L/S feed is marketing, and every signal resting on it is suspect).
   No new axis, no new sleeve, one existing feed graded.
2. **Secondary — Japanese-retail net-long share as a fadeable sentiment stock.** Construct
   `jp_net_long = (買建数 − 売建数) / (買建数 + 売建数)`, month-end, per coin. Honest EV assessment,
   stated plainly rather than talked up: **monthly frequency, n≈94, breadth ≈3 coins.** That is the
   same starvation that put `options VRP` in the graveyard under `no_breadth` despite it having the
   best IC of its campaign. This does **not** clear the desk's EV gate as a standalone sleeve and is
   **not** proposed as one. It is logged as a **pre-registerable monthly-horizon test** to be run
   only if a monthly clock slot is ever free — never as a daily signal, and never as a conditioning
   overlay on the carry book (that class is dead: `btc_correlation_regime_carry_conditioning`,
   `vol-target overlay`).
3. **Missing data:** none. The panel is free; parsing is PDF-only (8 pages/month, ~94 files) — the
   dependency-free extractor written this session handles it.

**A DATED STRUCTURAL BREAK THE DESK SHOULD KNOW ABOUT NOW — and only Japanese sources carry it.**
The 2026 Japanese tax reform (改正所得税法) was **enacted 2026-03-31**. It moves 特定暗号資産 —
crypto assets *registered in the 金融商品取引業者登録簿 (FIEA registry)*, i.e. a restricted list, not
all crypto — from progressive 雑所得 to **20% 申告分離課税 (flat separate taxation)** and grants
**3-year loss carryforward** (*"翌年以後3年間にわたって繰越控除が可能となった"*), conditional on
filing in the loss year and every year thereafter; carryforward nets only against crypto gains, not
against equities or FX. **Effective date: 1 January of the year following FIEA implementation —
currently anticipated 2028-01-01.** Consequences the desk must price in *before* building anything
on JVCEA:
- The −27.5% statutory drag on a symmetric gamble collapses to `0.5·0.8·X − 0.5·X = −0.10·X`, and
  with carryforward the true drag on a multi-year strategy goes to roughly zero. **The mechanism
  above expires on a known date.** Any relationship fitted on 2018–2027 JVCEA data is fitted on a
  regime that is legislated out of existence.
- Direction: the reform makes Japanese retail crypto participation **cheaper and more
  professional**, so the cohort should get *less* noisy, not more. A fade-Japanese-retail signal is
  therefore a **decaying** asset with a published expiry — which is exactly the kind of thing the
  desk normally discovers only after it stops working.
- The restriction to FIEA-registry 特定暗号資産 means the treatment will differ *across coins*,
  creating a cross-sectional discontinuity at the same date.

**Sources.**
- JVCEA monthly statistics index: https://jvcea.or.jp/statistics/information/ — coverage
  **2018-09 → 2026-05**, monthly PDF, published ~the 3rd of the following month.
  Verified file parsed this session: https://jvcea.or.jp/cms/wp-content/themes/jvcea/images/pdf/statistics/202503-KOUKAI-01-FINAL.pdf
  (also confirmed the same URL pattern for 2022-09: `202209-KOUKAI-01-FINAL.pdf` — the archive is
  **address-predictable**, so the whole history is retrievable by iterating `YYYYMM`).
  **Language: Japanese.** `[FETCHED-PRIMARY]` — 8-page PDF downloaded and text-extracted locally;
  column headers, per-coin rows and the month-end footnote read from the file, not from a snippet.
  **Licence caution, stated explicitly:** JVCEA asserts copyright on its published content
  (*"掲載内容のデータやテキスト等は著作権の対象となり、著作権法及び国際条約により保護されています"*)
  and disclaims accuracy warranties for member-submitted figures. Publicly served, no paywall, no
  login → **passes the §13 legitimacy gate for internal research use**, but it is **NOT open-licensed**:
  no redistribution, no republication of the tables, internal analysis only. Graded accordingly.
- Japanese crypto loss tax treatment, pre- and post-reform (Japanese, tax-practitioner primary
  write-up with the statutory language quoted):
  https://kaoria-tax.com/knowledge/loss-carryforward/ and
  https://kaoria-tax.com/knowledge/crypto-loss/ — `[FETCHED-PRIMARY]`, **Language: Japanese**.
  Corroborated independently by MUFG's own tax explainer https://www.bk.mufg.jp/column/others/b0100.html
  (`[SEARCH-SUMMARY]` for MUFG, used only as a second witness to the 55% figure, not as the source).
  **Residual gap:** the National Tax Agency (国税庁) primary notice and the enacted 改正所得税法 text
  were **not** opened this session — the 2028 effective date and the 特定暗号資産 registry definition
  are therefore `[FETCHED-PRIMARY]` on a practitioner source, **not** on the statute. Confirm against
  国税庁 / 金融庁 before anything depends on the exact date.

**Replication scan.** The tax facts are statute, not an estimate — nothing to replicate. The
*behavioural consequence* (that a no-carryforward, high-rate, asymmetric regime manufactures
disposition-effect selling and negative after-tax retail expectation) is a standing result in the
Japanese-equity literature and is asserted here as a mechanism, **not** as a measured crypto effect.
No study was found this session that tests it on Japanese crypto data — which is precisely why the
JVCEA panel is interesting and why item 2 above is logged as unrun rather than as a result.

**Graveyard check.** Distinct from every dead item and checked one by one. **NOT** a Japan premium —
`bitbank_jp` (IC −0.06, JST-candle risk) killed the Japan *price-premium* axis and this proposes no
premium at all; it is a *positioning and deposits* panel. NOT multilingual attention (`no_edge_daily`)
— audited position stocks, not search interest. NOT a conditioning overlay. NOT price-only. The one
genuine adjacency is the desk's existing long/short-ratio family, and item 1 is deliberately framed
as **grading that existing feed** rather than adding a parallel one.

**Verdict:** `data-loot-confirmed` (high value, licence-restricted) + `verification-asset`
(the L/S-feed audit, which is the actionable part and costs almost nothing) + `parked-hypothesis`
(JP net-long fade — mechanism strong, breadth/horizon too thin to clear the EV gate, and it carries
a legislated 2028 expiry that must be written into any future pre-registration).

---
