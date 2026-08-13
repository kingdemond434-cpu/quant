# LIT deep-miner — THESES LAYER, run 7 (2026-08-12)

**Seat:** LITERATURE DEEP-MINER / theses-and-dissertations layer.
**Resumes:** `docs/research/deep_sweep/20260805_LIT_theses_layer.md` — a seat that died at its
repository checklist with every row PENDING and an EMPTY findings section. Its aim, priors,
negative-result grading vocabulary and repository checklist are **inherited whole** and are not
re-derived here. The bar being beaten is `LIT_d_nonenglish_theses.md` (2026-07-26), which retrieved
**exactly one thesis** and called that "the honest shortfall".

**Write freeze:** this file is the ONLY write of this seat. Read-only on scripts/, libs/, executor,
rails, live/state, and EVERY shared ledger (recommendation_ledger.json, graveyard.md,
improvement_inbox.md, data_axis_watchlist.md, research_memory). Parent routes serially at close.

## Inherited thesis-of-the-ground (tested at close, section 6 — NOT assumed here)
A thesis is the only literature genre **contractually obliged to report what failed**: a
failed-specification chapter (free graveyard entries the desk adopts without spending a
multiplicity slot), a "further work" section (free untested hypotheses = unpriced options), and a
data chapter naming exact feeds/endpoints/vintages. Nobody reads them. **Is that edge real?**

## Inherited aim (re-read from `data/strategy_coverage.json` at run start, 2026-08-12)
- **STATISTICAL-ARBITRAGE = MENTIONED-NEVER-TESTED (n=0)** — the desk's ONE never-tested family.
  HIGHEST PRIORITY.
- THIN (n≤2): LEVEL-REACTION (1), EVENT-AND-CALENDAR (1), ATTENTION-SENTIMENT (2),
  MARKET-MAKING-EXECUTION (2), VOL-AND-OPTIONS (2), LEAD-LAG (2).
- HUNTED, not brought back: carry-funding (4), cross-venue-premium (9), cross-sectional-factor (5),
  trend-and-structure (8), order-flow-positioning (5), copy-trader-skill (3), onchain-flow (6).

## The extraction rule that pre-selects what is read (from the desk's own graveyard)
`docs/graveyard.md` → `statarb_kalman_hedge_ratio_refinement`: the ESTIMATOR layer is dead —
*"if the desk ever tests statarb, spend the budget on COSTS AND CAPACITY, never on the estimator."*
**So in every stat-arb thesis: read the COST chapter and the CAPACITY/liquidity chapter, skip the
model chapter.** A thesis whose only content is a fancier estimator is a null and is written up as
one.

## Structural kills applied by me, not deferred
- crypto cross-section = **1.54 independent bets raw / 29 market-neutral** ⇒ directional
  cross-sectional mechanisms hard-killed on breadth unless BTC-beta-neutralised.
- direction is not predictable while volatility is (129/129 directional mechanisms, max OOS
  Sharpe 0.100).
- daily-bar textbook mechanisms are picked clean (420 tested / 0 survivors).
- **a positive backtest with a fake or absent cost model IS a negative result**, written up as one.
- graveyard + `research_agenda.json:do_not_repeat` cross-check before anything is carded.

## Provenance grades (binding, on every item)
- `[PRIMARY]` — full text opened and read from this box (HTTP status + exact URL recorded).
- `[ABSTRACT]` — landing/abstract page read only.
- `[SUMMARY-ONLY]` — search snippet only. **A LEAD, NEVER EVIDENCE. Barred from priors.**

## Negative-result grading (inherited, load-bearing)
- **STRUCTURAL** — no mechanism, no loser, or no capacity. Blocks forever. Desk adopts free.
- **STATISTICAL** — underpowered / short window / one pair. Does NOT block; re-specify.

## Legitimacy gate (charter §13, HARD STOP)
Open-access only. No paywall circumvention in any language. ProQuest / CNKI / Wanfang / DBpia =
EXCLUDED paywalled giants; route to the university's own institutional repository instead. A
ToS-block or bot-gate is recorded as a ROUTING finding about the route from this box — never as a
verdict about the corpus — and §38 requires a REPLACEMENT route named in the same run.

## Box constraint recorded up front (it shaped every depth decision below)
`curl`/`wget` have **no network from this box** (sandbox; verified 2026-08-12 — `curl
https://dspace.cuni.cz/` times out at 20s). The only route to the open web is `WebFetch`/
`WebSearch`. Consequence: the 2026-07-26 stdlib PDF extractor (OP-025, `/tmp/pdftxt.py`, still on
disk) is **unusable this run** — it needs a locally-downloaded PDF and nothing can download one.
Every PDF this run was read through WebFetch's own extractor.

---

## 1. REPOSITORY CHECKLIST (inherited whole; each row stamped with status + date + exact query)

All 15 inherited rows are stamped. **NOT-REACHED is used honestly and is a required status** — the
08-05 seat left every row `PENDING`, which is what made its file unusable. Statuses:
`MINED` (full text opened + read) / `THIN` (target identified, not opened) /
`EXHAUSTED-BY-ABSENCE` (correct native query, quantified zero) / `BLOCKED` (route closed from this
box — a statement about the ROUTE, never about the corpus) / `DEFUNCT` / `NOT-REACHED`.

| # | Repository | Region | Status (2026-08-12) | Exact query / URL used |
|---|---|---|---|---|
| 1 | DiVA (diva-portal.org) | Nordic | **THIN** — 1 full text opened (null), 1 target identified but NOT opened | `"thesis" cryptocurrency "statistical arbitrage" site:diva-portal.org`; `diva-portal.org master thesis cryptocurrency pairs trading cointegration transaction costs FULLTEXT`. Opened: `diva-portal.org/smash/get/diva2:1322682/FULLTEXT02` (KTH, triangular fiat/crypto arb, **null** — see T-5). NOT opened: `diva2:1324527` (Uppsala, "Pairs Trading, Cryptocurrencies and Cointegration") — direct `FULLTEXT01.pdf` fetch died with `socket hang up`. Its snippet content is `[SUMMARY-ONLY]` and is **barred from priors**. |
| 2 | theses.fr | FR | **EXHAUSTED-BY-ABSENCE** for crypto stat-arb | JSON API `theses.fr/api/v1/theses/recherche/?q=cryptomonnaie&nombre=50` → **98 theses**, composition is law / tax / management / market-efficiency, **zero** microstructure or arbitrage mechanics. `?q="arbitrage statistique"` → **exactly 1 result**, Yohan Fereres 2013 *Stratégies d'arbitrage systématique multi-classes d'actifs*, Paris-Est, **not crypto**. A correct native term returning a clean 1-and-not-crypto is the finding. |
| 3 | DART-Europe | EU aggregator | **DEFUNCT — the inherited row is stale** | `dart-europe.org/basic-search.php` → **301** → `ucl.ac.uk/library/dart-europe-e-theses-portal-has-closed-down`, which states verbatim: *"the DART-Europe e-theses portal was closed down permanently on Monday 03 February 2025."* Replacements it names: BASE, CORE, NDLTD Global ETD Search. |
| 4 | EThOS successor(s) | UK | **NOT-REACHED** | No query run. Untouched. |
| 5 | CORE (core.ac.uk) | global aggregator | **BLOCKED** (route, not corpus) | `core.ac.uk/search?q="Pairs Trading in Cryptocurrency Markets"` → **HTTP 403**. |
| 6 | BASE (base-search.net) | global aggregator | **NOT-REACHED** | No query run. Untouched. |
| 7 | OATD (oatd.org) | global | **BLOCKED** (route, not corpus) | `oatd.org/oatd/search?q=cryptocurrency+AND+arbitrage` → **HTTP 403**. |
| 8 | OpenThesis | global | **NOT-REACHED** | No query run. Untouched. |
| 9 | NARCIS / Dutch repos (TU Delft, Erasmus, Tilburg) | NL | **THIN** — Erasmus MINED, others NOT-REACHED | `thesis.eur.nl/pub/67552/Thesis-Pairs-trading-.pdf` → HTTP 200, full text extracted and read (**T-3**, a documented negative). NARCIS itself, TU Delft and Tilburg: no query run — **NOT-REACHED**, and NARCIS's rumoured discontinuation was **not verified this run** and must not be asserted. |
| 10 | ETH Research Collection | CH | **NOT-REACHED** | A `site:research-collection.ethz.ch` query was issued but the engine did not honour the site filter and returned zero ETH items — that is a failed query, **not** evidence about the corpus. |
| 11 | SciELO / BR institutional | BR/LatAm | **THIN** + **the inherited row is mis-specified** | **SciELO is a JOURNAL index, not a thesis index** — the correct BR thesis ground is **BDTD** (`bdtd.ibict.br`) plus university repositories. Query: `dissertação mestrado criptomoeda arbitragem estatística pairs trading custos de transação BDTD repositório`. Identified and **named for run 8, not opened**: `lume.ufrgs.br/handle/10183/175317` — *"Arbitragem estatística em criptomoedas"* (UFRGS) — WebFetch returned `Command failed with no output`, one attempt. Also surfaced: FGV + USP statarb dissertations (equities), and `repositorio.ucp.pt` (PT) *"Pairs trading: cointegration-based methods applied to the cryptocurrency market"*. |
| 12 | J-STAGE + CiNii Dissertations | JP | **EXHAUSTED-BY-ABSENCE** in the national index; **NEW SEAM opened** | CiNii Research OpenSearch API `cir.nii.ac.jp/opensearch/all?q=暗号資産 裁定取引&format=json` → **`opensearch:totalResults: 0`**, empty items array — confirms the 2026-07-26 finding with a fresh, dated, quantified zero. **But** `修士論文 暗号資産 統計的裁定取引 ペアトレード 大学 リポジトリ` surfaced Hitotsubashi's finance-programme master's-thesis list (`fs.hub.hit-u.ac.jp/performance/masters-thesis/`, ~800 theses, 平成21–令和7 / 2009–2025) carrying **20+ quantitative microstructure and pairs-trading theses** (Hawkes-process order intensity, tick-size effects, market impact, robust dynamic pairs trading, JGB relative value). **Crypto × stat-arb is still absent, but the JP quant thesis layer EXISTS and the national index cannot see it** — see T-6. |
| 13 | KCI / RISS open subsets | KR | **MINED — highest yield of the run** | `학위논문 암호화폐 차익거래 페어트레이딩 통계적차익거래 석사학위논문 거래비용`, then `조정환 "비트코인 무기한 선물" 차익 거래 전략 국민대학교 석사학위논문 원문 dcollection`. Full Korean text of the doctoral work's journal instance extracted and read: `kais99.org/jkais/journal/Vol23No12/vol23no12p073.pdf` (HTTP 200). **DBpia hits were refused per §13** and routed to the issuing society's open PDF. → **T-4**. |
| 14 | CN self-archives (Tsinghua/PKU open) | CN | **NOT-REACHED** | No query run. The single largest un-attempted parity gap of this run — stated plainly rather than buried. |
| 15 | MIT DSpace / Berkeley eScholarship / Stanford | US | **NOT-REACHED** | A combined `site:` query was issued but the engine did not honour the site filters and returned only arXiv/SSRN/MDPI items — a failed query, **not** evidence about the corpora. |

**Grounds NOT on the inherited checklist, discovered and worked this run:**

| Repository | Status | Basis |
|---|---|---|
| **CUNI DSpace** (`dspace.cuni.cz`, Charles Univ. IES) | **MINED — the productive seam of this run** | **2 full texts** opened and read end-to-end (T-1 Fil 2019; T-5 Smutný 2025). Serves `bitstream/handle/...pdf` at **HTTP 200** with no bot gate. Krištoufek and Baruník supervise a continuing line of crypto microstructure/stat-arb theses here. |
| **NDLTD Global ETD Search** (DART-Europe's named successor) | **BLOCKED** | `search.ndltd.org/search.php?q=cryptocurrency%20arbitrage` → **HTTP 503, `Retry-After: 86400`**. |
| **Semantic Scholar Graph API** | **WORKING — adopt as first probe** | `api.semanticscholar.org/graph/v1/paper/...` → HTTP 200 JSON with publisher abstract, DOI, licence and OA-PDF pointer. The only route that produced the T-2 abstract. |
| **scholar.archive.org** (fatcat) | **BLOCKED** | rate-limited on first request. |
| **IEEE Xplore** | **BLOCKED** (CC-BY content, bot gate) | `/document/`, `/stamp/stamp.jsp` and the S2-declared OA PDF `/ielx7/...` all → **HTTP 418**. |

---

## FINDINGS

_(appended as each item resolves — write-as-you-go)_

---

### T-1 — THE COST-BREAKEVEN LADDER: a bachelor thesis prints the gross-vs-net pair of tables that lets the desk compute the exact one-way cost at which each stat-arb construction dies — and three of the four die below Binance's own taker fee
**(the single highest-value item of this run; it is what the desk's extraction rule was pointing at)**

**Source.** Miroslav Fil, *Pairs Trading in Cryptocurrency Markets*, **Bachelor thesis**, Charles
University, Faculty of Social Sciences, Institute of Economic Studies, Prague, **2019**, 57pp.
Supervisor: **doc. PhDr. Ladislav Krištoufek Ph.D.**
PDF: `https://dspace.cuni.cz/bitstream/handle/20.500.11956/109634/130268190.pdf?sequence=1`
Landing: `https://dspace.cuni.cz/handle/20.500.11956/109634`
**`[PRIMARY]`** — HTTP 200, 1.0 MB PDF, full text extracted on this box and read end-to-end
(133,823 chars). Every number below is read off the thesis's own printed tables.
**Why this one:** it is the thesis BEHIND `Fil & Kristoufek (2020), IEEE Access 8:172644–172651`,
which litminer **run 6 cited as a "reference-level base rate" for its live stat-arb card 1 without
ever opening it**. This run opened the primary.

**THE DATA CHAPTER (exact, because nobody indexes for it).** Binance, **calendar year 2018 only**
— 365 daily obs/coin, 8,760 hourly obs/coin. The author states the reason plainly: Binance was
founded in late 2017, *"there is simply not much more data to get"*. 20 nominated pairs; 82–92% of
nominated pairs actually traded. Daily scenario: 4-month formation / 2-month trading / 1-month
step. Hourly scenario: 20-day formation / 10-day trading / 10-day step. **Execution lag = 1
period. Opening threshold = 2σ. Leverage = 2x.**

**THE COST CHAPTER (§3.5 — the chapter the desk's graveyard row orders us to read).**
- Commissions: Binance spot **10/10 bps maker/taker baseline, falling to 2/4 bps at the top volume
  tier**.
- Market impact: **20 bps, borrowed wholesale from Do & Faff (2012) — a study of US EQUITIES
  centred on the year 2000.** The author concedes it in the text: *"we recognize that it is likely
  inaccurate for our purposes."*
- **Total one-way assumption: 30 bps, applied twice per completed round trip.**
- **SHORT-SELLING COSTS ARE EXCLUDED FROM EVERY REPORTED RESULT**, and the thesis explains why the
  exclusion is not innocent: *"The data we work with comes from Binance which does not support
  margin trading whatsoever as of June 2019."* For venues that did, it prices it: **Kraken charged
  1 bp rollover every 4 hours = 6 bps/day ≈ 21.9%/yr**, which the author calls *"enormous compared
  to costs in traditional securities, making serious use of short-selling difficult."*

**THE TWO TABLES THAT MATTER — gross and net, same signals, printed 30 pages apart.**
Trade counts are IDENTICAL across the two tables (0.469 / 0.526 / 3.29 / 4.38 per month), which
confirms costs change only P&L and not the signal path — that is what makes the elasticity below
a valid derivation rather than a guess.

| | Daily Distance | Daily Cointegration | Hourly Distance | Hourly Cointegration |
|---|---|---|---|---|
| Monthly profit @ **30 bps** one-way (Table 3) | **−0.01%** | **−0.07%** | **+2.87%** | **−1.09%** |
| Annualised Sharpe @ 30 bps | 0.17 | **−0.78** | 2.6 | **−2.8** |
| Monthly profit @ **ZERO** cost (Table 13) | +0.31% | +0.26% | **+5.29%** | +1.77% |
| Annualised Sharpe @ zero cost | 0.5 | −0.42 | **6.5** | 1.5 |
| Trades/month (both tables) | 0.469 | 0.526 | 3.29 | 4.38 |
| Round-trip (converged) trades | 22.3% | 21.9% | 27.9% | 36.4% |
| **% of WINNING trades** | 46.3% | 45.4% | 45.5% | 48.4% |
| Max drawdown | 24.6% | 22.7% | 13.3% | 16.2% |

**THE DERIVATION THE THESIS DOES NOT DO, AND THE PAPER DOES NOT EITHER — a breakeven ladder.**
Because signals are cost-invariant, net(c) = gross − (c/30 bps)·drag₃₀ is exact, so each
construction has a closed-form **one-way cost at which it reaches exactly zero**:

| construction | gross %/mo | drag @30bps | **breakeven ONE-WAY cost** |
|---|---|---|---|
| Hourly **Distance** | 5.29 | 2.42 | **65.6 bps** |
| Daily Distance | 0.31 | 0.32 | **29.4 bps** |
| Daily Cointegration | 0.26 | 0.33 | **23.6 bps** |
| Hourly **Cointegration** | 1.77 | 2.86 | **18.6 bps** |

**Read the bottom row first: hourly cointegration dies at 18.6 bps one-way — below Binance's own
published spot taker fee of the era (10 bps) plus any realistic half-spread on an alt pair.** It is
not "unprofitable after costs" in the vague sense; it is unprofitable before anything except the
fee schedule. Daily cointegration (23.6 bps) and daily distance (29.4 bps) are barely better.

**AND THE ASYMMETRY THAT MATTERS TO *THIS* DESK, which inverts the usual reading.** The desk's
book is ~$5k. The 20 bps of that 30 bps is **equity market impact from the year 2000** and is
approximately **zero at $5k on liquid Binance perps**; the desk's real one-way cost is ~4 bps
futures taker + ~1–2 bps half-spread ≈ **5–6 bps**. So the literature's headline verdict — "costs
kill crypto pairs trading" — is **calibrated to institutional size and is NOT binding on a micro
book**. The consequence is the opposite of encouraging, and it is the actual finding:
**at desk scale the family does not die of costs, so it must be judged on GROSS, and gross at
daily is +0.31% and +0.26% per month.** That is economically trivial (≈3.2–3.8%/yr, before the
short leg is financed) on a strategy holding 2x leverage through 24.6% drawdowns with a **46%
win rate**. The daily rungs are killed by **having no gross edge**, which is a structural death and
a strictly stronger one than "costs ate it".

**WHAT THE SHORT LEG DOES TO THE ONE SURVIVOR — using the thesis's own Kraken number.** Hourly
Distance holds a position 5.5 of every 10 trading days, i.e. ≈55% time-in-market ≈ 16.5 days/month.
At the author's own 6 bps/day borrow, the short leg alone costs ≈ **99 bps/month**, taking the
+2.87% to ≈ **+1.88%/month** and dropping its breakeven one-way cost from 65.6 to ≈ **53 bps**.
**This cost is real for a SPOT construction and structurally ABSENT for a PERP construction** — a
perp short pays funding, not borrow. That is the single largest systematic distortion between the
academic crypto-pairs literature and the desk's actual instrument, and it runs in the desk's
FAVOUR for once. It does not vanish, though: it is replaced by the **funding differential between
the two perp legs**, and 6 bps/day is a useful magnitude bracket for what run 6's card-1 falsifier
#1 ("add funding accrual, does net Sharpe flip ≤0?") should expect to find.

**THE DESK'S OWN RAIL FIRES ON THE SURVIVOR.** Hourly Distance at zero cost prints **Sharpe 6.5**.
The desk's hardened-harness rail flags **best Sharpe > 6 as SUSPECT-LOOKAHEAD**. On one calendar
year, one regime (2018 was a monotonic bear), 20 pairs, and as the winner of a 4-cell base grid
plus a stop-loss × threshold grid. Treat 2.87% as a selection tail, not a base rate.

**Free negatives the thesis reports that the desk gets without spending a slot.**
1. **Stop-losses make it worse.** *"introducing a stop-loss actually lowers our performance
   significantly across both methods"*, and the author gives the correct reason: if a pair is truly
   cointegrated, stopping out is a mistake; if it is not, the spread is a coin flip and the stop is
   neutral — *"overall, stop-lossing is at best"* neutral. Directly relevant: risk overlays on a
   mean-reversion spread are structurally value-destroying, not merely unhelpful.
2. **Win rate is below 50% in ALL FOUR constructions** (45.4–48.4%) even in the profitable one.
   Any desk screen that gates on hit-rate would reject the only rung that works.
3. **Better auxiliary metrics do not translate into profit.** Hourly Cointegration has the *highest*
   round-trip rate (36.4%) and the *highest* win rate (48.4%) and the *worst* P&L (−1.09%). The
   author's own diagnosis is the useful part: cointegration selects **tighter, less volatile
   spreads**, so it trades more often for a smaller upside against a fixed cost. **Corollary the
   desk should keep: a pairs-formation rule must be a function of the cost, not just of
   mean-reversion quality** — *"Proper pairs formation procedure thus also has to be a function of
   transaction costs."*
4. **Only ~22–28% of trades converge**; the rest are closed by the calendar at period end. The
   "mean reversion" is mostly not observed.

**Further-work section (the free-options layer, verbatim content).** (a) robustness and risk
management are *"mostly ignored"* in the pairs literature, including the choice among
cointegration test statistics; (b) **no crypto-specific transaction-cost research exists**, so
every crypto pairs paper is importing equity cost estimates — *"it is without doubt inappropriately
restrictive to base our approximations of transaction costs on research studying US equities"*;
(c) **crypto has no established sectors**, so the classic sector-restricted pair pre-selection is
unavailable — the author proposes inventing one via *"qualitative analysis or unsupervised cluster
analysis"*. (c) is a live, cheap, untested idea for the desk and is carded below as the only
mechanism card of this run.

**Intraday-seasonality by-product (Table 14, returns by hour of day UTC).** Pairs-trading returns
are not flat across the clock: Distance hour 00 t=+3.0, hour 09 t=+2.6, hour 15 t=+2.3, hour 22
t=−2.1; Cointegration hour 01 t=−3.8, hour 22 t=−3.9, hour 13 t=+2.3, hour 20 t=+2.5. The author
correctly refuses to claim it (*"far beyond the scope of this thesis"*). With 24 hourly tests a
Bonferroni bar is |t|≈2.9, so only the two Cointegration negatives clear it. **Independent, 2018,
spot-Binance corroboration of the intraday-clock structure that run 6's MECHANISM-CARD 2
(quarter-hour effect, arXiv 2607.09426) rests on** — different data, different decade, different
construction, same conclusion that the crypto intraday clock is not uniform. Logged as
corroboration, not as a new card.

**Graveyard check.** `statarb_kalman_hedge_ratio_refinement` — NOT violated: this thesis spends its
budget exactly where that row says to (costs), and its estimator layer is plain distance/EG, no
Kalman. `lit_hourly_copula_pairs_netneg` (killed 2026-08-12) — **INDEPENDENTLY CORROBORATED and
extended**: that row killed hourly copula/cointegration pairs on Tadi–Witzany-family evidence from
2021–2023; Fil's **Hourly Cointegration is −1.09%/month, Sharpe −2.8, on 2018 Binance data with a
different estimator** — a second witness, different era, different method, same verdict. The row's
re-entry bar is now stronger, not weaker. 420/0 daily price-only kill — confirmed again from
outside. `research_agenda.json:do_not_repeat` — no match (no statarb entry exists; the family is
n=0).

**Verdict:** `graveyard-candidate` ×2 (hourly cointegration, STRUCTURAL — dies at 18.6 bps one-way,
below the venue's own fee; daily distance + daily cointegration, STRUCTURAL — no gross edge at
micro size, +0.31%/+0.26% monthly at ZERO cost) + `prior-upgrade` on run 6's live card 1
+ `card` (sector-free clustering, T-4 below).

---

### T-2 — THE PUBLICATION DELTA, MEASURED: the journal version KEPT the negatives and made them the headline — which REFUTES the naive form of this ground's own thesis
**(the test the seat was told to run: did the published version drop the negative results?)**

**Sources.** Published version: Fil, M. & Krištoufek, L. (2020), *Pairs Trading in Cryptocurrency
Markets*, **IEEE Access 8, pp. 172644–172651**, DOI `10.1109/ACCESS.2020.3024619`, **CC-BY (GOLD
OA)**. Abstract retrieved verbatim from the Semantic Scholar Graph API
`https://api.semanticscholar.org/graph/v1/paper/5d311f01c4b1bb7981c05eb5af28ff12d306d7bc`
(HTTP 200) — **`[ABSTRACT]`**, publisher-supplied abstract, 34 citations.
Thesis version: T-1 above, `[PRIMARY]`.

**The delta, stated as measured.**

| | Thesis (2019) | Published (2020) |
|---|---|---|
| Universe | 20 nominated pairs | **26 liquid cryptocurrencies** |
| Frequencies | daily, hourly | **daily, hourly, 5-MINUTE** |
| Sample | Binance, 2018 only | Binance (period not in abstract) |
| Headline verdict | mixed; only hourly distance positive | *"the strategies **underperform classical benchmarks**"* |
| Daily distance | −0.01%/mo | **−0.07%/mo** |
| Best rung | hourly distance +2.87%/mo | **5-minute, +11.61%/mo** |

**The negatives were NOT dropped — they were promoted to the abstract.** The published abstract
leads with *"In our backtests, the strategies underperform classical benchmarks"* and prints a
NEGATIVE monthly number (−0.07%) as its comparison anchor. **So on this one, well-cited (n=34),
gold-OA instance, the "journals launder failures, theses report them" premise is simply FALSE.**
The honest generalisation is narrower and is stated in section 6.

**WHAT THE PUBLICATION ADDED IS THE PART THE DESK CARES ABOUT, AND IT IS UNVERIFIABLE FROM THIS
BOX.** The journal version extends the same code base **down to 5-minute bars and reports +11.61%
monthly**. That is a second, fully independent research group landing on the **5-minute rung** —
the exact rung litminer run 6's live MECHANISM-CARD 1 is built on (Tadi–Witzany copula, 5-min,
Sharpe 3.77). Two unrelated groups, two different estimators (distance vs copula), both find the
family lives only at 5-min-or-faster. **That materially raises the prior behind run 6's card.**

**But the cost model behind the 11.61% could not be read**, and it is the only thing that decides
the number. From the thesis's own framework, a 5-min run inherits **30 bps one-way** and a
**1-period (= 5-minute) execution lag**, and the hourly rung already showed costs eating **46% of
gross** at 3.29 trades/month. A 5-minute rung trades far more often, so the cost drag must be
multiples larger, and +11.61% net would require an implausibly large gross — OR a changed cost
assumption. **One of those two is true and this run could not determine which.**

**ROUTING FINDING (charter §13 / §38) — not a verdict about the corpus.** The paper is **CC-BY, so
mirroring is licit**, but every open route to its full text is bot-gated from this box:
`ieeexplore.ieee.org/document/9195252` → **HTTP 418**; `ieeexplore.ieee.org/stamp/stamp.jsp` →
**418**; the Semantic-Scholar-declared OA PDF `ieeexplore.ieee.org/ielx7/6287639/8948470/09200323.pdf`
→ **418**; `doaj.org/article/...` → **403**; `core.ac.uk/search` → **403**;
`scholar.archive.org/search` → **rate-limited**. **Replacement route named for the next run:** the
IES CUNI working-paper server (`ies.fsv.cuni.cz`) and the CUNI DSpace record for any successor
thesis by the same author — the same institute that served T-1 openly at HTTP 200. Second
replacement: `api.semanticscholar.org/graph/v1/...` returns publisher abstracts and OA-PDF
pointers reliably (200) and should be the FIRST probe for any paywalled-looking DOI.

**Verdict:** `engine-finding` (the publication-filter premise is refuted on this instance) +
`prior-upgrade` (independent second group at the 5-min rung, raising run 6 card 1's prior) +
`residual-gap` (the 5-min cost model — **named, dated, and routed**, not left as a shrug).

---

### T-3 — A THESIS WITH A FAKE COST MODEL, WRITTEN UP AS THE NEGATIVE RESULT IT IS: 12% MONTHLY from daily Yahoo-Finance bars and a correlation screen
**(the desk's standing rule: a positive backtest with an absent cost model IS a negative result)**

**Source.** Maxime de Vries, *Pairs Trading in the Cryptocurrency Market: An Empirical Analysis of
Trading Signals and Performance Metrics*, **Bachelor thesis**, Erasmus University Rotterdam,
Erasmus School of Economics. PDF: `https://thesis.eur.nl/pub/67552/Thesis-Pairs-trading-.pdf`
**`[PRIMARY]`** — HTTP 200, 425 KB, full text extracted on this box (68,535 chars).
**This is almost certainly the same "one thesis" the 2026-07-26 session retrieved and declined to
write up** (it logged "Erasmus bachelor, pairs trading in crypto, reports Sharpe ~3 … not written
up"). It is written up now, because a documented negative is a deliverable.

**The claim.** Top-30 cryptocurrency pairs formed by the **correlation method** (Ehrman 2006).
*"a monthly excess return of 12% and an average excess return of 13.9%"*, and the robustness
section concludes *"the results were robust to transaction fees"* and *"there was no sign of a
decreasing trend in the profitability of the trading strategy."*

**Why it is a negative result, four independent ways, each read off the thesis's own text.**
1. **The cost model is wrong about the venue it names.** *"The leading cryptocurrency exchange
   Binance charges between a 0% and 0.60% spot trading fee. If a conservative estimate of 0.60% is
   taken, the strategy still yields a monthly return of 10.58%."* Binance's published spot schedule
   is 0.10% base — **0.60% is not a Binance fee tier**, and the "conservative" 0.60% therefore
   prices nothing that exists. Only **1.42 percentage points** of a 12% monthly return is charged
   away, implying ~2.4 charged legs/month; no round-trip accounting is shown.
2. **The data are DAILY bars from YAHOO FINANCE**, not from the venue whose fees are quoted:
   *"The data was retracted from Yahoo Finance, using a daily frequency."* Sample ends
   2022-12-31; 50 cryptocurrencies filtered to 33. Yahoo crypto daily bars are vendor-aggregated
   with an undeclared bar boundary — this is precisely the cross-source daily-candle alignment
   class that produced the desk's own `bithumb_kr_premium_lookahead` kill and the Cho–Park–Ahn
   stale-leg artifact (LIT_d D-2). **Alignment is never declared in the thesis.**
3. **No slippage, no bid-ask spread, no market impact, and no short-financing cost anywhere in the
   document** — a market-neutral strategy is costed as if the short leg were free. T-1, from the
   same year and asset class, prices that leg at **6 bps/day**.
4. **The magnitude refutes itself against its own benchmark.** The thesis cites Gatev et al. (2006)
   for an *annualised* excess return of **11%** and then reports **12% per month** (≈289%/yr) from
   the *weakest* of the three standard formation rules. A 26x uplift over the canonical result,
   from correlation-screened daily bars, is the desk's "fat Sharpe is a tell" pattern.
   The document is also visibly unfinished — the title page still carries the template
   placeholders *"[title and name of thesis supervisor]"* and *"[day month year]"*.

**Structural kills the desk owns that also land on it.** Daily-bar textbook mechanism (420 tested /
0 survivors); and the correlation method is the pair-formation rule that T-1 measured as strictly
dominated. Note the two theses **disagree by a factor of ~1,000** on the same family, the same
asset class and overlapping years (T-1: −0.01% monthly daily-distance; T-3: +12% monthly daily-
correlation). Only one of them models an execution lag.

**Verdict:** `graveyard-candidate`, graded **STRUCTURAL on the construction, STATISTICAL on the
family** — the specific result is an artifact of an absent cost model plus unaligned vendor daily
bars and blocks nothing about pairs trading per se, but **"crypto pairs trading on daily Yahoo
Finance bars with a correlation screen" is dead on arrival and should never consume a desk slot**.
Also a reusable genre marker: *a thesis quoting a fee schedule that does not match the venue it
names has not modelled costs at all.*

---

### T-4 — KOREA, and the desk's exact instrument: a doctoral dissertation on BITCOIN PERPETUAL-SWAP arbitrage whose gross edge is 2.6 bps against a 6.5 bps retail cost, whose only profitable configuration ran on FTX, and which defines funding fees and then never charges them
**(the non-English parity yield, and the closest thing this run found to the desk's own book)**

**Source.** 조정환 · 김선웅 · 최흥식 (Junghwan **Cho**, Sun Woong **Kim**, Heung Sik **Choi**),
「비트코인 무기한 선물을 활용한 차익 거래 전략」 / *A Study on the Arbitrage Trading with Bitcoin
Perpetual Swap*, **한국산학기술학회논문지 (JKAIS) Vol.23 No.12, pp.666–675, 2022**,
DOI `10.5762/KAIS.2022.23.12.666`. Accepted **2022-12-07**, published **2022-12-31**.
Open PDF, no login: `https://www.kais99.org/jkais/journal/Vol23No12/vol23no12p073.pdf` (HTTP 200).
**`[PRIMARY]`** — full 10-page **Korean** text extracted on this box and read directly; every number
below is read off the printed Tables 4, 9–17.
**This is the journal instance of a DOCTORAL dissertation** (박사학위논문, 국민대학교 비즈니스IT
전문대학원 트레이딩시스템전공, 2023-02, supervisor 김선웅), catalogued at the National Assembly
Library as `dl.nanet.go.kr/detail/KDMT12023000031161`. **DBpia indexes it behind a paywall and was
NOT used** (§13 excluded); the issuing society's own open PDF was — the same replacement route
LIT_d established in 2026-07-26.

**Why this is the highest-relevance non-English item available on this ground.** It is not another
fiat-premium study. It trades **BTC spot against BTC PERPETUAL SWAPS across venues** — the desk's
instrument, on the desk's venues (Binance / FTX / OKX).

**Construction.** Spread = spot − perpetual across two venues. **Enter when the sign of the spread
flips, exit at the next flip.** Minute data: Binance + FTX, 2020-12-31 15:00 → 2022-06-18 15:39,
**767,889 closes**; ~**57 closed trades/day** (~3,400/month), average hold **33 minutes**. Daily
data: Binance + OKX, 2019-12-24 → 2021-04-01, **465 closes**; ~10.6 closed trades/month, average
hold **1.83 days** (max 7).

**Fee table (Table 4, verbatim).** Normal / VIP: BNC Spot **0% / 0%**; BNC Perp **0.0288% /
0.01224%**; FTX Spot **0.033% / 0.009%**; FTX Perp **0.033% / 0.009%**; (daily) OKX Spot **0.08% /
0.05%**.

**THE MINUTE RESULT, WHICH IS A FEE-TIER ARTIFACT AND DIES AT RETAIL (Tables 9–12, USDT/trade).**

| combo | no fee | **Normal tier** | **VIP tier** |
|---|---|---|---|
| Binance Spot – FTX Perp | +10.47 | **−15.73** | +3.33 |
| FTX Spot – Binance Perp | +14.13 | **−38.49** | **−3.96** |

Monthly: no fee **+30% / +45%**; **VIP fees applied +9% / −12%**.
**At the RETAIL (Normal) fee tier BOTH configurations are NET NEGATIVE.** Only the VIP tier rescues
ONE of the two, and the authors say why in their own words: FTX's perp fee was *"relatively
cheap"*. **Converted to bps on the ~1 BTC notional traded: the gross edge is ≈2.6 bps per round
trip, retail cost ≈6.5 bps, VIP cost ≈1.8 bps.** A desk paying Binance VIP-0 (spot taker 10 bps +
futures taker 4 bps, charged on open and close ⇒ ≈28 bps round trip across the four legs) is **an
order of magnitude above the gross edge**. This is a clean, measured, STRUCTURAL kill of
minute-frequency cross-venue spot-vs-perp arbitrage **at any fee tier this desk can reach**.

**AND THE VENUE THAT MAKES IT WORK NO LONGER EXISTS.** The single profitable minute configuration
is *Binance spot – **FTX** perp at VIP fees*. **FTX halted withdrawals 2022-11-08 and filed
Chapter 11 on 2022-11-11.** This paper was **accepted 2022-12-07 and published 2022-12-31** — one
to seven weeks *after* the collapse — and does not mention it. The result is **non-reproducible by
construction**: its edge was rent on one venue's unusually cheap perp fee schedule, and that venue
is gone. Grade **STRUCTURAL** and dated.

**THE DAILY RESULT IS NOT ARBITRAGE, IT IS CASH-AND-CARRY IN THE BIGGEST BASIS REGIME ON RECORD.**
Tables 13–17: 162 and 164 closed trades, mean **+879.59** and **+881.45** USDT, **min +17.33 and
+31.38** — i.e. the text states outright *"모든 거래에서 0 이상의 수익이 발생하였다"* (**every
single trade produced a profit ≥ 0**). Monthly **+37% and +38%**; fees barely register (879.59 →
840.97 at Normal tier) because there are only ~10 trades/month. Three things kill it:
1. **A 100% win rate over 162 trades is not a strategy result, it is an accounting result.** No
   real spread trade wins 162 times out of 162.
2. **The two "different" venue combinations produce the same P&L month by month** — 33/33, 24/24,
   31/31, 18/18, 39/39, 32/32 — which means the driver is not the venue pairing at all but the
   **common spot-vs-perp basis**. Long spot / short perp held ~1.8 days through 2020–2021 **is the
   cash-and-carry trade**, relabelled. That is the desk's HUNTED `CARRY-FUNDING` family (n=4),
   where `carry_entry_shorts_widening_basis` is already `mechanism_refuted` and the live sleeve
   realised **−58.27 bps**.
3. **The daily sample is 2019-12-24 → 2021-04-01 — it stops at the top of the bull market**, inside
   the single largest sustained positive-basis regime crypto has had.

**THE OMISSION THAT DECIDES IT, AND THEY DOCUMENT IT THEMSELVES.** §3.2 names the two principal
cost types of crypto trading as trading fees **and funding fees**, and correctly describes funding
as settled *"보통 8시간"* (typically every 8 hours) — **and then funding never appears again.** The
P&L identity Eq. (2) is four price legs; Table 4 lists trading fees only; no result anywhere
charges funding. For the daily strategy at 1.83 days average hold that is **≈5.5 unmodelled funding
settlements per trade**, on a perp leg, during 2020–2021 when BTC funding routinely ran
0.05–0.10% per 8h — i.e. **27–55 bps per trade of unpriced carry, in the adverse direction for
whichever half of the configurations is long the perp.** Per the desk's standing rule, a positive
backtest with an absent cost model is a negative result.

**The limitations section is limitation-free in the wrong direction.** The ONLY limitation the
authors name is that exchanges may privately offer **even lower** fees, and they recommend
negotiating them. There is no mention of funding, slippage, order-book depth, inter-venue transfer,
the capital locked simultaneously on two venues, the 100% win rate, or FTX.

**Who loses money and why they persist — asked, and the answer is nobody identifiable.** The claimed
counterparty is whoever quotes the stale side of a spot/perp spread for 33 minutes. At 2.6 bps
gross that "loser" is paying less than the fee the arbitrageur must pay to collect it, which is the
definition of a pattern rather than an edge. **Dropped on the desk's own mechanism test, not merely
on costs.**

**Graveyard check.** Matches `era_crossvenue_fiat_premium_arb` (cross-venue premium is barrier rent
— here the "barrier" is the fee schedule itself, and the ninth-plus instance of the same shape),
`carry_entry_shorts_widening_basis` (basis capture, refuted on the desk's own panel), and
`retail_crossvenue_scan_arb` (RU 2025: 15,256 signals → 4 survivors; 90.8% expire in
milliseconds). CROSS-VENUE-PREMIUM is HUNTED (n=9) and CARRY-FUNDING is HUNTED (n=4). **Nothing is
proposed; this is adopted as a kill.**

**Citation chain (backward, 2 levels).** Its reference [7] is **Krištoufek & Bouri, "Exploring
sources of statistical arbitrage opportunities among Bitcoin exchanges", *Finance Research Letters*
2022, DOI 10.1016/j.frl.2022.103332** — the same Krištoufek who supervised T-1. The Korean and
Czech stat-arb lines converge on one supervisor; that is a small, mapped literature, not a large
one, which bears on the exhaustion claim in section 7.

**Verdict:** `graveyard-candidate` **STRUCTURAL** ×2 (minute cross-venue spot-perp: gross 2.6 bps <
retail cost 6.5 bps, and its only profitable venue is defunct; daily: cash-and-carry mislabelled,
funding unpriced, sample ends at the basis peak) + `confirms-existing-kill` ×3 + `parity-yield`
(the KR thesis layer is NOT empty — the prior seats' zeros were a routing artifact, see T-6).

---

### T-5 — TWO MORE FULL TEXTS, BOTH NULLS, BOTH REPORTED
**(a null opened to full text is a deliverable; a null asserted from a snippet is not)**

**(a) Order-book asymmetries — `confirms-existing-kill` on the OFI family.**
Josef **Smutný**, *Impact of order book asymmetries on cryptocurrency prices*, **Master's thesis**,
Charles University FSV IES, defended **2025**, supervisor **doc. PhDr. Jozef Baruník, Ph.D.**
`https://dspace.cuni.cz/bitstream/handle/20.500.11956/200516/120505902.pdf?sequence=1`
**`[PRIMARY]`** — HTTP 200, 2.7 MB, full text extracted on this box and read.
Data chapter: **Binance high-frequency FUTURES** data for BTC, ETH, LTC, **June–November 2021 (six
months)**. Method: OLS + VAR + event study on order-imbalance ratio (OIR), depth imbalance, spread,
volume, trade count vs immediate returns. Finding: imbalance measures are statistically significant
predictors of immediate returns, robust across specifications.
**Why it is a null for the desk, from the thesis's own text.** It is a set of **in-sample
predictive regressions, not a backtest** — there is no cost model, no execution simulation and no
P&L anywhere. The author says so: *"Although the results demonstrate profit potential, several
real-world limitations are acknowledged, including transaction costs, latency, and the risk of
exploitation by adversarial trading algorithms"*, and the conclusion adds that the edge needs
*"low-latency infrastructure and favorable fee agreements"* and that competitors *"may
intentionally create misleading order book conditions to provoke a specific reaction from the
strategy"*. **Graveyard/agenda check: `research_agenda.json:do_not_repeat` already carries
`vpin_ofi_microstructure` — REJECTED 2026-07-03, "gross +59.4bps decaying 2024→+82bps to
2026→+12bps; requires L2 tick infra; IC decay kills expected ROI".** This thesis re-establishes the
signal exists and adds nothing about the decay or the cost, which are the only two things that
decided it. **`confirms-existing-kill`, do not re-queue.**

**(b) Triangular fiat/crypto arbitrage — null on construction.**
Fred **Robinson** & Sanghyun **Bai**, KTH Royal Institute of Technology, Information &
Communication Technology; examiner Markus Hidell, supervisor Peter Sjödin.
`https://www.diva-portal.org/smash/get/diva2:1322682/FULLTEXT02` **`[PRIMARY]`** — HTTP 200, full
text extracted and read. It is a **software-engineering** thesis: the "result" is that a simulation
passes its unit tests and *"turns a profit on average over many runs"*. Two fiat currencies + one
cryptocurrency, trades executed against a **simulation**, no venue fee schedule, no slippage, no
transfer latency, no order book. Per the desk's standing rule a positive backtest with an absent
cost model is a negative result; here there is not even a backtest. Family is CROSS-VENUE-PREMIUM
(**HUNTED, n=9**) and it matches `era_crossvenue_fiat_premium_arb`. **Null, no card, not re-queued.**

---

### T-6 — WHY THE PRIOR SEATS KEPT FINDING ZERO: the ETD AGGREGATOR LAYER IS CLOSED TO THIS BOX, AND JAPAN'S NATIONAL INDEX CANNOT SEE ITS OWN MASTER'S THESES
**(a routing finding and a lexical/structural finding — the two reasons a thesis hunt reads as an empty corpus when it is not)**

**(1) Every general ETD aggregator refused this box; every university's own DSpace served full text
at HTTP 200.** Measured this run, not assumed:

| aggregator | result | | institutional repository | result |
|---|---|---|---|---|
| OATD | **403** | | `dspace.cuni.cz` | **200**, 2 full texts |
| CORE | **403** | | `thesis.eur.nl` | **200**, 1 full text |
| DART-Europe | **DEFUNCT 2025-02-03** | | `diva-portal.org` | **200**, 1 full text |
| NDLTD (its successor) | **503, Retry-After 86400** | | `kais99.org` (society) | **200**, 1 full text |
| scholar.archive.org | rate-limited | | `theses.fr` API | **200**, JSON |
| IEEE Xplore (CC-BY!) | **418** | | `api.semanticscholar.org` | **200**, JSON |

**Standing rule this yields: on the thesis ground, NEVER route through an aggregator. Go to the
awarding institution's own repository, or to the issuing society's own PDF.** The aggregator layer
is where a hunt dies and reports "the corpus is empty"; it is the ROUTE that is empty. This is the
single most transferable operator of the run and it fully explains the 2026-07-26 shortfall
(1 thesis retrieved) and the 2026-08-05 seat's total non-start.

**(2) JAPAN — the national index is structurally blind to 修士論文, and that is not a lexical
failure.** CiNii Research (the successor to CiNii Dissertations) returns
**`opensearch:totalResults: 0`** for `暗号資産 裁定取引`. That is a real, dated, quantified zero and
it CONFIRMS the prior seat. **But it is not evidence that Japan has no quantitative thesis layer.**
Hitotsubashi's 金融戦略・経営財務プログラム publishes its own master's-thesis register (~800 titles,
2009–2025) containing a deep microstructure line — multidimensional **Hawkes-process order-arrival
intensity** (2020), **Queue-Reactive Hawkes** order-book work (2013), **market impact for
algorithmic trading** (2014), **tick-size-reduction effects on HFT intensity** (2016, 2021), **HFT
in IPO names** (2025), **robust dynamic pairs trading** (2016), **developed-market rates pairs
trading** (2017), **Kalman-filter JGB relative value** (2018) — plus two crypto items (**stablecoin
flight-to-liquidity/safety**, 2023; LLM sentiment annotation, 2023). **Japanese master's theses are
largely not deposited nationally; they live on programme pages.** Consequence for the desk's corpus
map: the JP academic ground should be re-graded from "EXHAUSTED" to "**EXHAUSTED IN THE NATIONAL
INDEX, UNMINED ON PROGRAMME PAGES**". Note honestly: **none of the JP items is crypto × stat-arb**,
so this run's aim is still not served by Japan — the correction is to the corpus map, not a lead.

**(3) The mandated DIVERGENT DATA-CHAPTER query returned ZERO new feeds, and that is the finding.**
The librarian's angle — search for *"tick data provided by"*, *"we were granted access"*,
*"proprietary dataset"*, *"order book snapshots"* instead of a strategy name — was run and is
reported as a null. Every data chapter actually read this run named a **commodity, already-held
source**: Binance public REST/klines (T-1, T-4, T-5a), Yahoo Finance daily (T-3), Coinmarketcap
(DiVA cohort), OKX/FTX public closes (T-4). **Not one thesis named a feed the desk lacks and could
acquire.** The only data-layer content with any value was NEGATIVE: T-3's use of Yahoo Finance
daily crypto bars is an *anti*-source (undeclared bar boundary, the desk's own
`bithumb_kr_premium_lookahead` hazard class). **Charter §11/§27 deliverable for this run: zero new
data sources, stated as measured rather than omitted.** Plausible reason, offered as a hypothesis
for run 8 and not as a result: students get the free public API precisely *because* they are
students, so the thesis genre is structurally the WRONG place to hunt privileged feeds — the
"granted access" language belongs to funded PhD/lab work, which is the un-run refinement.

---

## 2. MECHANISM CARDS — **ZERO, by decision, not by omission**

The brief permits max 3 and states that zero is valid and creditable. This run produces **zero**,
and the one candidate that existed is written up here so the decision is auditable rather than
silent.

**The candidate considered and DROPPED: "cluster-formed pairs" (from T-1's further-work section).**
Fil's own further work names the gap: crypto has **no established sectors**, so the equity
literature's sector-restricted pair pre-selection cannot be carried over, and he proposes inventing
one *"based on either qualitative analysis or unsupervised cluster analysis"*. The idea is real —
in equities, within-sector pairing is what makes the residual spread idiosyncratic instead of a
disguised factor bet, and the desk's own **1.54-independent-bets** measurement says crypto pairs
formed on raw prices are overwhelmingly BTC-beta.

**Dropped on the desk's own mechanism test: WHO LOSES MONEY AND WHY DO THEY PERSIST — no answer.**
The best story available ("narrative flow chases the cluster leader and abandons the laggard") is
asserted, not evidenced, and nothing in any thesis opened this run identifies that cohort or prices
its persistence. Per the desk's rule, **no identified loser ⇒ a pattern, not an edge ⇒ dropped.**
Two further reasons it should not be carded: it is a pair-**selection** refinement, i.e. exactly the
"estimator/construction layer" that `statarb_kalman_hedge_ratio_refinement` says never to spend
budget on; and it sits inside the family run 6's **live** MECHANISM-CARD 1 already occupies, so
carding it would spend a multiplicity slot re-asking a question already on the clock.

**What this run contributes to the stat-arb family instead of a card:** a raised prior and a named
dependency on run 6's existing card (T-2), and three constructions killed with numbers (below).

---

## 3. GRAVEYARD CANDIDATES

Graded **STRUCTURAL** (no mechanism / no loser / no capacity — blocks forever, desk adopts free)
vs **STATISTICAL** (underpowered / short window / one pair — does NOT block, re-specify).
All are literature priors, not desk tests. Every one carries a mechanism of death.

| # | candidate | grade | mechanism of death (measured) | source |
|---|---|---|---|---|
| G-1 | **Hourly COINTEGRATION crypto pairs** | **STRUCTURAL** | Breakeven one-way cost **18.6 bps** — *below the venue's own published taker fee*. Gross +1.77%/mo, net **−1.09%/mo, Sharpe −2.8** at 30 bps. Selects tight, low-volatility spreads ⇒ trades more for a smaller upside against a fixed cost. **Second independent witness for the existing `lit_hourly_copula_pairs_netneg` row** — different era (2018 vs 2021–23), different estimator (EG vs copula), same verdict. | T-1 `[PRIMARY]` |
| G-2 | **DAILY crypto pairs (distance AND cointegration)** | **STRUCTURAL** | Dies on **GROSS, not on costs** — the stronger death. At **ZERO** cost: +0.31%/mo and +0.26%/mo, with 24.6% drawdowns, 2x leverage and a **46% win rate**. At micro size the desk's real one-way cost (~5–6 bps) is far below the 29.4/23.6 bps breakevens, so costs are not what kills it: there is no economically meaningful gross edge to collect. Confirms 420/0 from outside. | T-1 `[PRIMARY]` |
| G-3 | **Minute-frequency cross-venue SPOT-vs-PERP arbitrage** | **STRUCTURAL** | Gross edge **≈2.6 bps/round-trip**; **retail cost ≈6.5 bps** ⇒ both configurations net-negative at the Normal fee tier (−15.73 and −38.49 USDT/trade). Survives *only* at VIP fees, *only* on one pairing, **and that pairing's venue is FTX** — which collapsed 2022-11-11, *before* the paper was accepted (2022-12-07). Desk fee tier (~28 bps round trip across four legs) is an order of magnitude above the edge. No identifiable loser at 2.6 bps. | T-4 `[PRIMARY]` |
| G-4 | **Daily cross-venue spot-vs-perp "arbitrage" (sign-reversal rule)** | **STRUCTURAL** | Not arbitrage — **cash-and-carry mislabelled**. 162/162 and 164/164 trades profitable (a 100% win rate is an accounting result, not a strategy result); two *different* venue pairings return the **same P&L month by month**, identifying the common spot-perp **basis** as the sole driver; sample **ends 2021-04-01**, at the peak of the largest positive-basis regime on record; **funding fees are defined in §3.2 and never charged** (~5.5 unmodelled 8-hour settlements per 1.83-day trade). Lands on HUNTED `CARRY-FUNDING` (n=4) where `carry_entry_shorts_widening_basis` is already `mechanism_refuted`. | T-4 `[PRIMARY]` |
| G-5 | **Crypto pairs trading on daily Yahoo-Finance bars with a CORRELATION screen** | **STRUCTURAL on the construction, STATISTICAL on the family** | Claims 12%/mo excess return "robust to transaction fees" using a **0.60% "Binance" fee that Binance does not charge**; no slippage, no spread, no short financing; **vendor-aggregated daily bars with an undeclared boundary** (the desk's `bithumb_kr_premium_lookahead` hazard class); **26× its own cited Gatev benchmark**. Blocks nothing about pairs trading per se; the construction is dead on arrival. | T-3 `[PRIMARY]` |
| G-6 | **Order-book-imbalance / OFI signals re-proposed without a decay or cost model** | **confirms-existing-kill** | In-sample OLS/VAR/event-study only — **no cost model, no P&L**, author concedes it needs *"low-latency infrastructure and favorable fee agreements"* and is exploitable by adversarial quoting. Says nothing about the two things that actually decided the family: `research_agenda.json:do_not_repeat` → `vpin_ofi_microstructure` REJECTED 2026-07-03 on **IC decay** (+59.4→+12 bps) and L2 infra cost. | T-5a `[PRIMARY]` |
| G-7 | **Triangular fiat/crypto arbitrage evaluated in simulation** | **STRUCTURAL** | "Profit" is a simulation passing unit tests: no venue fee schedule, no slippage, no transfer latency, no order book. Family CROSS-VENUE-PREMIUM is HUNTED (n=9); matches `era_crossvenue_fiat_premium_arb`. | T-5b `[PRIMARY]` |

**Cross-cutting prior the desk gets free from G-1+G-2 together:** the crypto pairs family's death
is **frequency-ordered**, and the ordering is measurable rather than rhetorical — daily dies on
gross, hourly cointegration dies below the fee schedule, hourly distance survives only at
institution-sized cost assumptions that do not apply to a $5k book, and every positive claim
remaining in the literature sits at **5-minute-or-faster**. That is consistent with run 6's
standing implication and now has a numeric ladder under it.

---

## 4. ENGINE / METHOD FINDINGS

**E-1 — A working PDF-text route exists under the network sandbox, and R0358 can be closed by it.**
`curl`/`wget` have **no network** from this box (verified: `curl https://dspace.cuni.cz/` times out
at 20s), so the 2026-07-26 OP-025 workflow ("curl the PDF, extract locally") is dead as written, and
`scripts/pdf_text.py` does not exist (R0358 open). **But `WebFetch` writes the raw response body to
disk** — `.../tool-results/webfetch-<id>.pdf` — even when its own summariser reports the PDF as
"corrupted binary". **So the working route is: WebFetch the PDF URL (ignore its text answer
entirely), then run a stdlib extractor over the saved binary.** Every number in this file for T-1,
T-3, T-4, T-5a and T-5b came through that route.
**PROVENANCE GUARANTEE, given the parent's warning about `arxiv.org/pdf/` silent fabrication: NO
number in this file was taken from WebFetch's own PDF summarisation.** Numbers came from (i) local
stdlib extraction of a saved binary, read by me with `grep`/`sed`, or (ii) an HTML/JSON landing
route (`api.semanticscholar.org`, `theses.fr/api`, `cir.nii.ac.jp/opensearch`). Nothing here needs
an `[UNVERIFIED-PDF-ROUTE]` tag. The one item that would have needed it — the Uppsala DiVA thesis —
is explicitly held at `[SUMMARY-ONLY]` and **barred from priors**.

**E-2 — THE DEFECT ANY FUTURE `pdf_text.py` WILL HAVE IF IT MERGES CMAPS, found the hard way.**
The inherited extractor (`/tmp/pdftxt.py`) returned **empty output** on modern theses because it
only handles literal `(...)` strings, while pdfTeX emits CID hex strings `<0024...>`. Worse, the
obvious fix — parse `/ToUnicode` CMaps and merge them into one map — **silently corrupts text**:
academic PDFs carry several subset fonts whose glyph ids collide, so a merged map decoded the
Korean paper's header as *"Jousnam og uhe Kosea Bdaeemia-Jneutusiam doopesauion Sodieuy"* instead of
*"Journal of the Korea Academia-Industrial cooperation Society"* — Latin text off by +1 on some
glyphs while the CJK looked perfect. **That is the dangerous failure mode: it does not error, it
produces confident wrong numbers**, which on a results table is exactly the class of defect the
desk kills strategies for. Fix implemented and verified: resolve `/Font` resource dicts → font
objects → each font's OWN `/ToUnicode`, track the active font through `Tf`, decode per font, and
fall back to per-font auto-offset detection for subset fonts with no CMap. Working extractors left
at **`/tmp/pdfx.py`** (offset-detection) and **`/tmp/pdfx2.py`** (per-font CMap; the correct one).
**Both are OUTSIDE the repo — this seat is under a write freeze and wired nothing.** Recommendation
for whoever closes R0358: implement the per-font version, and add a regression fixture that asserts
a known Latin header decodes exactly, because the CJK output looks fine while the Latin is wrong.

**E-3 — `api.semanticscholar.org/graph/v1/paper/...` is the correct FIRST probe for any
paywalled-looking DOI.** It returned HTTP 200 with the publisher abstract, DOI, citation count,
licence (`CCBY`) and an OA-PDF pointer for a paper whose every other route 403/418'd. It is what
made T-2's publication-delta test possible at all.

**E-4 — supervisor identity was the only reliable quality predictor in this genre.** Four theses
opened, quality variance enormous: the two supervised by named econometricians (Krištoufek → T-1;
Baruník → T-5a) were rigorous, declared their assumptions and printed their sensitivity tables; the
one whose title page still carried the template placeholders *"[title and name of thesis
supervisor]"* and *"[day month year]"* (T-3) reported 12% monthly from a fee tier its own named
venue does not offer. **Operator: read the title page before the abstract. An unfilled supervisor
field is a stronger negative signal than any result in the document.**

**E-5 — a shared scratch directory is contended.** `.../tool-results/` is written by sibling agents
in the same project; two PDFs belonging to another seat's AI-methods run appeared in it mid-task.
Key on the exact filename returned by your OWN WebFetch call, never on "the newest file".

---

## 5. DEPTH LINE — how deep each lead went, and what depth surfaced that the surface did not

| lead | depth reached | **what depth surfaced that the surface did not** |
|---|---|---|
| **Fil 2019 (CUNI, T-1)** | **full-text + chapter-level + citations-2-level (forward to its own published version) + exhausted** | The surface (abstract, and run 6's citation of it) says only *"family is fee-fragile"*. Depth produced **the gross table (13) and the net table (3) as a pair**, which is the whole asset: it yields a **closed-form breakeven one-way cost per construction** (18.6 / 23.6 / 29.4 / 65.6 bps) that appears nowhere in either the thesis or the paper. It also produced the **6 bps/day short-borrow number**, the **stop-losses-hurt** result, and the **sub-50% win rate in all four cells** — none of which is visible above the abstract. |
| **Fil & Krištoufek 2020 (IEEE Access, T-2)** | **abstract (verbatim, publisher-supplied) + delta-vs-thesis test; full text BLOCKED** | The surface assumption (this ground's own premise) was that publication would drop the negatives. Depth showed the **opposite**: the negatives were promoted into the abstract. It also revealed the paper **added a 5-minute rung (+11.61%/mo)** that the thesis never had — the exact rung run 6's live card 1 stands on — and that **its cost model is unreadable from this box**, which is a precise residual gap rather than a vague one. |
| **de Vries (Erasmus, T-3)** | **full-text + exhausted** | The surface is "Sharpe ~3, pairs trading works" — which is why the 2026-07-26 seat dropped it unwritten. Depth found the **0.60% "Binance" fee that Binance does not charge**, the **Yahoo Finance daily bars**, the **absent short-financing**, and the **26× discrepancy against the Gatev benchmark it cites**. A dropped lead became a documented graveyard candidate. |
| **Cho/Kim/Choi (Kookmin, T-4)** | **full-text (Korean) + chapter-level + citations-backward-1 + author/venue-diaspora (the venue, not the author) + exhausted** | The surface (and the search snippet) is *"9%/month minute, 38%/month daily"* — a positive. Depth found: **both minute configurations are net-NEGATIVE at the retail fee tier**; the one positive configuration **runs on FTX**, which had already collapsed **before the paper was accepted**; the daily result has a **100% win rate over 162 trades** and the two "different" venue pairs return **the same P&L month by month**, which identifies it as cash-and-carry rather than arbitrage; and **funding fees are defined in §3.2 and never charged anywhere**. Every one of those is invisible above full text. |
| **Smutný (CUNI, T-5a)** | **full-text + conclusion-level** | Surface says "order book imbalance predicts returns". Depth confirms there is **no cost model and no P&L at all** — it is regressions, so it cannot speak to the only question (`vpin_ofi_microstructure`'s IC decay) that decided the family. |
| **Robinson & Bai (KTH, T-5b)** | **full-text** | Surface reads like crypto arbitrage; depth shows a **software-engineering thesis whose "profit" is a simulation passing unit tests**. |
| **Uppsala DiVA `diva2:1324527`** | **surface only — `[SUMMARY-ONLY]`, barred from priors** | Nothing. Named for run 8. |
| **UFRGS `10183/175317` (BR)** | **surface only — identified, one failed fetch** | Nothing. Named for run 8. |
| **theses.fr / CiNii** | **corpus-count level (API), exhausted for the queried concepts** | Counts convert "I looked and found nothing" into a defensible, dated zero. |

**Anti-breadth-theatre self-assessment.** Six theses/papers opened to **full text and read**, four of
them mined to chapter level, in **three languages** (EN, KR, CZ-institution). This is not a
repository catalogue. But the honest defects are: **CN and US were NOT REACHED at all**, BASE /
EThOS / OpenThesis / ETH were not queried, and **two identified high-value targets (Uppsala, UFRGS)
were not opened**. Coverage is partial and is stamped as partial.

---

## 6. VERDICT ON THE GROUND'S CENTRAL CLAIM

**The claim:** a thesis is the only genre *contractually obliged* to report what failed, so it
yields (a) free graveyard entries, (b) free untested hypotheses, and (c) a data chapter naming
exact feeds — and nobody reads them.

**Verdict: the edge is REAL but it is NARROW, it is NOT the edge as stated, and one of its four
limbs is simply false. Limb by limb, on what I actually opened:**

**(a) Free graveyard entries — TRUE, and this is the entire yield.** Five of the six items opened
produced a usable negative, and two of them (T-1, T-4) produced negatives of a quality the desk
could not have bought elsewhere: a **breakeven-cost ladder** and a **fee-tier-artifact kill with a
dead venue**. This limb alone justifies the ground.

**(b) Free untested hypotheses ("unpriced options") — FALSE in practice, on this sample.** The
further-work sections yielded exactly one idea worth writing down (T-1's *"no established sectors in
cryptocurrencies … sensible sector design might be invented, based on … unsupervised cluster
analysis"*). Applied to the desk's mechanism test it **fails**: it is a pair-*selection* refinement
with **no identified loser**, and per the desk's own rule that makes it a pattern, not an edge. It
is also substantially the same family as run 6's already-queued card 1, so carding it would spend a
multiplicity slot to re-ask a live question. **Therefore this run produces ZERO mechanism cards, by
decision and not by omission.** Every other "further work" line was a request for more robustness
checks — useful to academics, worthless as a hypothesis source.

**(c) Data chapters naming exact feeds — TRUE but WORTHLESS HERE.** Every data chapter did name its
feed precisely. **Every one named something the desk already has** (Binance public API ×3, Yahoo
Finance daily, Coinmarketcap, public OKX/FTX closes). Net new data sources this run: **ZERO.**
Hypothesis for why, offered untested: students are given the free public API *because* they are
students; "we were granted access" is funded-lab language, not thesis language.

**(d) "Journals launder failures, theses have a chapter for them" — REFUTED on the one instance
where it was directly testable.** T-1's own journal version (T-2) **kept every negative and made
them the abstract's headline**, printing *"the strategies underperform classical benchmarks"* and a
negative monthly return as its anchor. A 34-citation gold-OA paper did exactly what the thesis is
supposed to be uniquely good at.

**The reformulation that survives, and which run 8 should use instead:** the exploitable property of
a thesis is **not** its failure narrative — it is that a thesis prints the **INTERMEDIATE TABLES a
journal compresses away for space**. The asset is the *sensitivity table*: gross **next to** net,
the full parameter grid, the per-hour breakdown, the with-and-without-execution-lag pair. That is
what let T-1 yield a breakeven ladder and T-4 yield a fee-tier artifact, and it is what neither
published version carries. **Hunt theses for SENSITIVITY TABLES, not for confessions.** Corollary
quality filter, cheap and effective: **read the title page first** (E-4).

**Net for the desk:** the desk's ONE never-tested family is still never-tested, and nothing found
here changes that it should be tested at **5-minute-or-faster**. What changed is that the daily and
hourly rungs are now dead with *numbers attached* rather than by analogy, and run 6's live card 1
has both a **raised prior** (a second, independent group lands on the 5-min rung) and a **named
unverified dependency** (that group's cost model).

---

## 7. NEXT UN-EXHAUSTED GROUND — named precisely so run 8 resumes rather than re-scans

**Resume here, in this order. Do NOT re-scan rows 2, 3, 12 or 13 of the checklist — they are
answered with dated, quantified results.**

1. **`lume.ufrgs.br/handle/10183/175317` — "Arbitragem estatística em criptomoedas" (UFRGS, BR).**
   Identified, **one failed fetch, never opened**. The only BR-language item found that is squarely
   on the desk's n=0 family. Route: the Lume handle page for the bitstream link, then the
   WebFetch-lands-binary + `/tmp/pdfx2.py` route (E-1).
2. **`diva-portal.org/smash/get/diva2:1324527/FULLTEXT01.pdf` — "Pairs Trading, Cryptocurrencies and
   Cointegration" (Uppsala).** Currently `[SUMMARY-ONLY]` and **barred from priors**; its snippet
   claims a 2% transaction-cost threshold and that crypto pairs are not cointegrated over long
   windows. Both claims are directly load-bearing on T-1's ladder and **must be verified or
   discarded**. One fetch died with `socket hang up`; retry.
3. **The Fil–Krištoufek 2020 5-MINUTE cost model — the highest-value residual gap in this file.**
   It is the dependency under run 6's live MECHANISM-CARD 1. `ieeexplore` is **418** on all three
   routes despite the paper being **CC-BY**. Try, in order: `ies.fsv.cuni.cz` working-paper server;
   a CUNI DSpace record for any successor thesis by Fil; `unpaywall` DOI resolution; a licit CC-BY
   mirror. **Do not accept the +11.61% figure into any prior until the cost model is read.**
4. **CUNI DSpace (`dspace.cuni.cz`) systematically — the proven seam.** Two full texts at HTTP 200
   this run with zero friction. Krištoufek and Baruník supervise a continuing crypto
   microstructure / stat-arb line at IES. Enumerate their supervised theses by year; this is the
   single highest yield-per-fetch ground found.
5. **`repositorio.ucp.pt` (PT) — "Pairs trading: cointegration-based methods applied to the
   cryptocurrency market."** Identified, not opened; reportedly runs a 1% transaction-cost case,
   which would extend T-1's ladder to a third independent estimate.
6. **JP programme-page master's-thesis registers — a NEW seam, national index is blind to them.**
   Start `fs.hub.hit-u.ac.jp/performance/masters-thesis/` (~800 titles, 2009–2025, deep Hawkes /
   market-impact / tick-size line), then the equivalent registers at Tokyo, Waseda 商学研究科 and
   Keio. Expect microstructure, **not** crypto stat-arb.
7. **NOT-REACHED, in priority order — the honest remainder of this run's mandate:**
   **CN self-archives (the largest parity gap — zero queries run)**, then **MIT DSpace / Berkeley
   eScholarship / Stanford**, **ETH Research Collection**, **BASE**, **EThOS successor**,
   **OpenThesis**, **TU Delft / Tilburg**, and **BDTD (`bdtd.ibict.br`) proper**.
8. **Binding route rule for whoever runs it (T-6):** go to the **awarding institution's own
   repository or the issuing society's own PDF**. Every general ETD aggregator refused this box
   (OATD 403, CORE 403, NDLTD 503, DART-Europe defunct, scholar.archive.org rate-limited) while
   every institutional repository served full text at 200. Routing through an aggregator is what
   makes a full corpus read as empty.
