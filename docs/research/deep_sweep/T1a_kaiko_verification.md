# [T1-a] Kaiko Verification — INDEPENDENT PRIMARY-SOURCE CLOSE-OUT

**Run date:** 2026-07-26
**Item:** [T1-a], PENDING VERIFICATION, owed across two prior runs.
**Mandate:** close the two named gaps on the Kaiko vendor-replacement card (card 8 of
`docs/research/data_axis_watchlist.md`) with INDEPENDENT primary sources, not a re-read of the
vendor marketing page. This card has already produced one REFUTED claim (the "$1,000-2,500/mo"
pricing figure) from single-source reading — that is the failure mode this run exists to avoid.

**The two verbatim gaps owed:**
1. "the rulebook's interior text was not independently re-extracted (no PDF tooling on this box)"
2. "ESMA register not independently checked"

**Discipline for this run:** exact URLs only, opened not remembered. Open-access only, no
paywall circumvention. Anything unverified is written "UNVERIFIED" with what was tried.

---

## STEP 0 — PDF TOOLING: TESTED, NOT ASSUMED

The prior card's excuse was "no PDF tooling on this box." That was TESTED this run rather than
inherited. Result: **the excuse is factually correct but was never load-bearing.**

Probed (all MISSING):
- venv `.venv/bin/python`: `pypdf`, `fitz` (PyMuPDF), `pdfminer`, `PyPDF2` — all ModuleNotFoundError
- system `/usr/bin/python3`: same four — all ModuleNotFoundError
- CLI: `pdftotext`, `pdftohtml`, `mutool`, `qpdf`, `gs`, `pdfimages`, `tika`, `java`,
  `zlib-flate` — all MISSING (`which` returns nothing)
- `.venv/bin/pip list` returns 0 lines

Present: `/usr/bin/strings`, `/usr/bin/perl`, and Python's **stdlib `zlib`**.

**Ruling: "no PDF tooling" does NOT imply "cannot extract."** A PDF content stream is
FlateDecode'd, and `zlib` is in the standard library. Extraction route taken is recorded below.
No installs performed (freeze respected).

---

## GAP 1 — RULEBOOK INTERIOR: **EXTRACTED. GAP CLOSED.**

**Route that worked: local pure-stdlib extraction, NOT WebFetch.** The file was downloaded to
`/tmp` and parsed with a throwaway `zlib`-only extractor (nothing written to the repo; no installs).
Sequence: linear indirect-object scan that skips stream bodies -> `zlib.decompress` each stream ->
parse each font's `/ToUnicode` CMap -> walk page content streams and recurse into Form XObjects ->
map 2-byte Identity-H glyph IDs back to Unicode.

**Artifact:** `https://25446524.fs1.hubspotusercontent-eu1.net/hubfs/25446524/Factsheets/Kaiko%20Indices%20Rulebook.pdf`
- HTTP 200, `content-type: application/pdf`, `content-length: 2527759`, `last-modified: Thu, 25 Sep 2025 12:51:15 GMT`
- `md5 4ae1e1ec42b8caeec7c4646ac4abd073`
- 1,751 indirect objects, 31 pages, 177 fonts carrying ToUnicode CMaps
- **51,470 characters of real text recovered** (every page rendered as a Form XObject over an
  image-backed layout, which is why a naive page-content read returns nothing)

**Why this matters procedurally:** the two prior runs recorded "no PDF tooling on this box" as if it
were a blocker. It is TRUE that no PDF library or CLI exists here — but it was never load-bearing.
`zlib` is stdlib and PDF text is FlateDecode'd. **The gap was a tooling assumption, not a tooling
limit.** Log this as a reusable capability: this desk CAN read PDFs.

### VERSION — the vendor page and the search index disagree, and the PDF settles it
Page 1 reads `April 2025 / Version 2.0 / www.kaiko.com/indices`. The document's own Version History
table (page 3):

| Version | Publication Date | Comments |
|---|---|---|
| 1.0.0 | 25/07/2023 | Created |
| 1.1.0 | 01/10/2024 | New section: Kaiko Sector Indices; Update: Kaiko Blue-Chip Indices (ISIN code) |
| 1.1.1 | 17/01/2025 | Update: Kaiko Sector Indices (Description, list of index) |
| 2.0.0 | 15/04/2025 | Document structure changes with new index families. Update: Kaiko Market Indices |

Google's index still describes this URL as "July 2023 Version 1.0" — **stale by two major
revisions.** Anyone grading this card off search snippets is reading a 2023 document. This is the
same failure mode that produced the refuted pricing claim.

### THE SUBSTANTIVE RULES (quoted from the extracted interior)

**1. Aggregation method — VWM + TWAP, confirmed IN the rulebook (not just on the HTML page):**
> "A Volume-Weighted Median combined with a Time-Weighted Average Price (TWAP) methodology is
> applied to derive fair and representative prices based on executed transactions from the selected
> exchanges."

**2. Constituent-exchange inclusion criteria — a TWO-TIER vetting table, fully enumerated.** This is
the single most valuable thing in the document and it was NOT on the marketing page. Page 9 carries
the actual criteria matrix, Basic Vetting vs Hard Vetting:

| Criterion | Basic Vetting | Hard Vetting |
|---|---|---|
| Absent from any sanction list | Yes | Yes |
| Located in stable and open country | – | Yes |
| Has been operating for the past | – | 5 Years |
| Regulated by an independent government body | – | Yes |
| KYC/AML controls | – | Strong |
| Trading Policies | – | Significant |
| Offers REST API & WebSocket data feeds | – | Yes |
| Offers live & historical trade data | – | Yes |
| Provide cold storage for customers funds | – | Yes |

> "The composition of Benchmark Reference Rates is derived from the hard-vetted exchanges... In
> contrast, Reference Rates incorporate data from exchanges that meet fundamental eligibility
> criteria, providing a broader yet systematically screened dataset."

So there are **two distinct rate products**: Benchmark Reference Rates (hard-vetted venues) and
Reference Rates (basic-vetted venues). The desk's prior reconstruction did not distinguish these.

> "Liquidity Optimization — From the curated exchange list, an optimization process selects the most
> relevant exchanges to maximize liquidity and offer accurate price discovery."

**3. Outlier / stale-quote / missing-data rejection — three separate named rules:**
> "Delayed & missing data — At the time of the calculation (t), some underlying components may be
> delayed or unavailable. To ensure index continuity, a Fixed Indices Publication Buffer is applied
> before the computation of the index value. **If any required underlying price is missing after this
> buffer period, the index value is not computed.**"

> "Spurious data — If for any reason any underlying price is identified as potentially suspect within
> an index composition, **the index value is not computed.**"

> "Rounding — All rates are calculated with all available decimals"

**This is the fallback procedure, and it is a REFUSAL, not a substitution.** Kaiko does not
interpolate, does not carry forward the last good print, and does not drop the venue and re-weight.
It publishes nothing. That is a materially different design from what the desk's reconstruction
assumed, and it is cheap to copy.

**4. Publication frequency + lag — exact numbers, and the lag is a deliberate BUFFER:**
- Real-time: `Publication interval: 5s`, `Indices Publication Buffer: 5s`
- Fixings: `Publication interval: 1 day`, `Indices Publication Buffer: 15 min`
- Daily fixings: **Europe/London 16:15 UTC, Asia/Singapore 08:15 UTC, North America/New York 20:15 UTC**

Note the `:15`. The underlying Reference Rates fix at 16:00 / 08:00 / 20:00 UTC (stated on rulebook
page 7); the INDEX publishes 15 minutes later. **That 15-minute gap is the publication buffer, not a
timezone artefact** — it exists so late/missing constituent prices can arrive before the index either
computes or refuses. Any reconstruction that stamps the index at 16:00 is wrong by 15 minutes.

**5. Venue-dropout / constituent turnover is handled by BUFFERING, not by ad-hoc substitution:**
> "For Benchmark Reference Rates, buffering mechanisms are implemented to minimize unnecessary
> parameters turnover during rebalancing, thereby maximizing liquidity coverage and maintaining
> methodological consistency."

> "Quarterly Reviews — The exchange constituents **and calculation window** of the Reference Rates are
> reviewed quarterly to ensure alignment with prevailing market conditions."

**LOAD-BEARING ADMISSION FOUND: the calculation window is a QUARTERLY-REVIEWED PARAMETER, not a
constant.** The desk's reconstruction hard-coded a 60-minute window as a "desk parameter". The
rulebook confirms the real window is re-tuned every quarter and is not published per-rate. See
GAP 3 — this is the single largest irreducible gap.

**Extraordinary review (asset removal path):** exclusion triggers are "Fraud", "Market manipulation",
"Significant loss of volume or liquidity"; the Administration Committee publishes findings within 24
hours and the asset is excluded 3 days after the event / "two days after the initial public
communication" (**the document contradicts itself on this interval — 3 days in the process diagram,
"two days" in the prose on the same page 19**). Noted as a genuine internal inconsistency in a
regulated rulebook, not a transcription error on my side.

**Index maths (not rate maths):** Laspeyres formula with a divisor; base value 100; divisor adjusted
for token burns, hard forks, airdrops, token unlocks, inflation/deflation. Capping at 30% per asset
for Blue-Chip and Market indices, applied iteratively until no constituent exceeds the threshold.
Blue-Chip selection = `Average Rank = 75% x Size Rank + 25% x Liquidity Rank`; weighting =
`50% x Size + 50% x Liquidity`; quarterly rebalance; 80/120 buffer rule.

---

## GAP 2 — ESMA REGISTER: **INDEPENDENTLY CONFIRMED. GAP CLOSED.**

The prior card said the register was "not independently checked (JS-driven UI)". The UI is indeed
JS-driven, but **the register is backed by a public, unauthenticated Solr endpoint** — no login, no
scraping of a rendered page, no paywall.

**Endpoint opened:**
`https://registers.esma.europa.eu/solr/esma_registers_bench_entities/select?q=en_fullName:*KAIKO*&rows=20&wt=json`

**Negative control run first (this matters):** `q=kaiko` against the default search field returns
`numFound: 0`. That is a QUERY artefact, not an absence — `q=*:*` on the same core returns
**28,134 documents**, and a field-qualified wildcard returns the entity. Had I stopped at the first
query I would have written "Kaiko is NOT on the ESMA register", which would have been a false
refutation. Recording this because it is exactly the failure this item exists to prevent.

**Result — `numFound: 1`, verbatim fields:**

| Field | Value |
|---|---|
| `en_fullName` | **Kaiko Indices SAS** |
| `en_esmaId` | **FRBMR2019000003** |
| `en_lei` | **969500BKJ2X29T7NJH85** |
| `en_country` | FRANCE |
| `en_supervisingAuthority` | Autorité des Marchés Financiers (AMF) - FRAM |
| `en_euEeaRelevantAuthority` | Autorité des Marchés Financiers (AMF) - FRAM |
| `en_euEeaStatus` | **Registration under Art. 34** |
| `en_contactInfo` | https://www.kaiko.com/products/rates-and-indices |
| internal id | 1327 |
| register snapshot `timestamp` | **2026-07-26T00:18:12.959Z** (same-day index build) |

**Human-openable equivalent:**
`https://registers.esma.europa.eu/publication/details?core=esma_registers_bench_entities&docId=1327`
and the register search UI at
`https://registers.esma.europa.eu/publication/searchRegister?core=esma_registers_bench_entities`

**TWO PRECISION CORRECTIONS TO THE CARD — both matter:**

1. **The registered entity is `Kaiko Indices SAS`, NOT "Kaiko".** The watchlist card says "Kaiko is
   an EU-BMR-registered benchmark administrator". The BMR registration attaches to a *separate legal
   entity* from the market-data business the desk is actually considering replacing. The regulatory
   halo does not automatically extend to Kaiko's raw tick/aggregate data products.

2. **The status is "Registration under Art. 34", i.e. REGISTERED, not AUTHORISED.** Under BMR Art.
   34 an administrator is *registered* (the lighter route, available where the administrator does not
   provide critical/significant benchmarks) rather than *authorised*. The card's phrasing
   "EU-BMR-registered ... under AMF supervision" is correct as far as it goes; "regulated benchmark
   administrator" as marketing shorthand overstates the tier. The ESMA field is the precise claim.

The rulebook's own self-description (page 2) is consistent with the register:
> "As a regulated Benchmark Administrator under the EU BMR framework and compliant with IOSCO
> principles..."

**So the card's BMR claim survives independent checking — but it no longer rests on Kaiko's own
documents.** It now rests on ESMA's register, which is the independent primary source that was owed.

---

## GAP 1b — LEVEL 2 OF THE CHAIN: THE **RATES** RULEBOOK. THIS IS THE DOCUMENT THAT MATTERED.

The Indices Rulebook is an INDEX document. It repeatedly defers the actual price-formation rules to
a second document ("as outlined in the Reference Rates methodology", "please refer to this link").
**That link is not visible in the rendered text — it is a PDF `/URI` link annotation.** I pulled the
annotations straight out of the PDF byte stream (5 URIs total, octal-escaped):

- `https://marketing.kaiko.com/hubfs/Factsheets/Kaiko%20Benchmark%20Rates%20Rulebook%20-%20202212%20(1).pdf`  <- **the real methodology**
- `https://www.kaiko.com/indices/benchmarks`
- `https://www.kaiko.com/pages/reference-rates`
- `https://www.kaiko.com/`
- (a Google Maps link to the Paris office)

**Downloaded:** HTTP 200, 666,559 bytes, PDF-1.4, 21 pages, **28,579 chars extracted**.

**TRAP — THE FILENAME LIES.** The URL says `202212` (December 2022). The document's own version
table says it is **Version 7, dated 13/04/2026**:

| Version | Date | Comments |
|---|---|---|
| 1 | 20/09/2022 | Created |
| 2 | 05/01/2023 | Addition of Benchmark Reference Rates |
| 3 | 28/03/2023 | **Partitioning scheme added** |
| 4 | 14/05/2024 | Rates name change; review calendar format |
| 5 | 01/09/2025 | Buffering logic change; Exchange Combination Optimization; Add Disclaimer |
| 6 | 16/03/2026 | Publication event timings extended; Missing Data section updated |
| 7 | 13/04/2026 | Data Source section updated for combined fiat/stablecoin order books |

Anyone who skipped this file because the filename looked three years stale would have missed the
entire current methodology. It is **three months old**, not four years.

### THE CARD'S CENTRAL "HONEST LIMIT" IS **REFUTED**. ALL THREE PARAMETERS ARE PUBLISHED.

The watchlist card states, as a documented limit:
> "window length, partition count and the recency decay are NOT published (60min / 12x5min / linear
> ramp are DESK parameters)"

**All three ARE published, in this document, in plain text.**

**(a) Window length — published as an explicit enumerated SET plus a deterministic selection rule:**
> "● Real-time set: [15s, 20s, 30s, 60s, 120s, 300s] ● Fixing set: [300s, 600s, 900s, 1200s, 1800s, 3600s]"

and the static values are pinned per rate type:

| Rate Type | Publication Interval | Calculation Window |
|---|---|---|
| All Reference Rates (real-time) | 5 seconds | **Static at 300 seconds** |
| All Benchmark Reference Rates (real-time) | 5 seconds | Dynamic - possible quarterly update |
| All Reference Rates (daily fixings NYC/SGP/LDN) | Daily | **Static at 3600 seconds** |
| All Benchmark Reference Rates (fixings) | Daily | Dynamic - possible quarterly updates |

**(b) Partition count — published as an exact mapping (§"Partitioning Scheme"):**
> "● Real-time set: [15s/5p, 20s/10p, 30s/10p, 60s/10p, 120s/10p, 300s/10p]
> ● Fixing set: [300s/10p, 600s/10p, 900s/10p, 1200s/10p, 1800s/10p, 3600s/10p]"

**It is 10 partitions, for every window except 15s (which uses 5).** The desk guessed 12. The
rulebook's own worked example agrees: *"eg. 1h calc. window with 10 partitions of 6 min"*.
=> **Reference Rate daily fixing = 3600s window / 10 partitions of 6 minutes.** The desk's
reconstruction used 60min/12x5min: **window right, partition count wrong.**

**(c) Recency decay — published, and it is NOT a linear ramp:**
> "We implement a sensitivity calibration method on partitions to increase the weight of the most
> recent prices included in the calculation window. First, we apply a specific weighting function to
> obtain weights that are **inversely proportional to time**. It gives: [formula] The weights are
> then normalised."

**Inverse-in-time, then normalised — not a linear ramp.** The desk's linear ramp is a different
functional form and will not reproduce Kaiko's number.
_HONEST LIMIT: the literal equation is typeset in a symbol font that my extractor renders as
placeholder glyphs, so I have the WORDING of the weighting function but not the exact LaTeX. The
verbal specification ("inversely proportional to time", then normalised) is unambiguous enough to
implement as `w_k ∝ 1/(age_k)`, but the exact offset/exponent is UNVERIFIED._

### THE FULL SUBSTANTIVE RULE SET (quoted)

**1. Aggregation — the actual algorithm, step by step:**
> "At calculation time... collect all executed trades in the calculation window (before the
> calculation time) on all selected exchanges. ● Merge all the executed trades from the different
> exchanges in the same dataset sorted by prices in ascending order. ● Create partitions of size
> from the calculation window (eg. 1h calc. window with 10 partitions of 6 min). ● Each partition is
> then subject to a Volume Weighted Median (outlier resistant by nature). ● A time weight is
> associated with each partition's volume-weighted median (more weights to the last partitions which
> are the most recent). ● Aggregation of those weighted prices... to obtain the reference price."

> "The volume-weighted median is calculated as the price of the trade where the trade is the trade
> that lies at **50% of the cumulative volume** for the partition."

Trades only, no order book:
> "They are **exclusively derived from executed transactions on centralized spot exchanges**, ensuring
> that all published rates reflect genuine market activity rather than indicative or theoretical
> pricing."

**2. Constituent-exchange inclusion criteria — now with the QUANTITATIVE gates the index rulebook omitted:**
- Asset-agnostic vetting: the same 9-criterion Basic/Hard table (Reference Rate vs Benchmark Reference Rate).
  Passing exchanges form the **Kaiko Vetted Exchanges List (KVEL)**.
- Asset-specific liquidity gate:
  > "The 3-month volume history of the relevant pair (e.g. BTCUSD) is extracted for each exchange
  > and, for each month, an average daily trading volume as a percent of the total average trading
  > volume from the initial KVEL is computed. The monthly average values are in turn averaged, and
  > **all exchanges whose average liquidity is strictly below 1% are not considered relevant** in
  > terms of liquidity and thus are excluded from the KVEL."
- Additional Liquidity Layer:
  > "When the list of exchanges... is above 10 exchanges, we apply a limitation layer that selects
  > only the **10 most liquid exchanges**..."
- **Minimum Exchanges Number: Reference Rate = 1, Benchmark Reference Rate = 3.**
- Final combination:
  > "extracting the final combination of **up to 5 exchanges** generating the best liquidity: minimum
  > number of zero-volume buckets and average volume per interval."
  (The desk's 5-venue reconstruction was RIGHT on this count.)
- Optimization metric — **"zero-volume buckets"**:
  > "A zero-volume bucket is defined as a timestamp for which no trades in the relevant pair are
  > observed during the rolling window considered."

**3. Dual buffering — exact numeric thresholds, fully published:**

| Name | Abbrev | Value |
|---|---|---|
| Target Threshold of Zero Volume | Target_ZV | 10% |
| Buffer current set up | Buffer_C | 5% |
| Upgrade threshold current (Target_ZV - Buffer_C) | Up_C | 5% |
| Downgrade threshold current (Target_ZV + Buffer_C) | Down_C | 15% |
| Buffer next set up | Buffer_N | 2.5% |
| Upgrade threshold next (Target_ZV + Buffer_N) | Up_N | 7.5% |

Selection rule: start from the SMALLEST eligible window; compute % zero-volume buckets over the past
3 months across all KVEL combinations; take the first window where some combination is below
Target_ZV; among qualifying combinations pick fewest zero-volume buckets, tie-break on highest
volume. Quarterly: window only moves if the condition **persists for two consecutive quarters**;
combination only changes if the best alternative is **5% lower** in zero-volume buckets; and
"If the exchange combination is changed, the calculation window remains the same."

**4. THE FALLBACK PROCEDURE WHEN A VENUE / DATA DROPS OUT — this is the answer to the task's
question, and it is a THREE-CASE rule, different per product:**
> "**Missing Data** — At the time of the calculation (t), some relevant transactions may be missing...
> **If no relevant transactions are recorded on the relevant partition, the corresponding partition is
> excluded from the calculation and weights are adjusted accordingly.** For **real-time** rates, if no
> relevant transactions are recorded in the entire calculation window, **no price is published**. For
> **fixing** rates, if no relevant transactions are recorded in the entire calculation window, **the
> last available real-time rate price will be used as a fallback price**, and the published fixing
> rate will include **an indication that the fallback mechanism has been applied, along with the
> timestamp of the fallback price**."

> "**Delayed Data** — If for any reason Kaiko was unable to retrieve any relevant transactions at the
> calculation time, the corresponding partition is excluded from the calculation."

> "**Spurious Data** — If for any reason any transactions were identified as potentially suspect
> within a partition, such transactions may be adjusted to disregard the spurious data."

Three things the desk's reconstruction does not do: (i) **drop empty partitions and RE-NORMALISE the
time weights** — not treat them as zero; (ii) **publish nothing** rather than degrade, for real-time;
(iii) **carry the last real-time rate forward WITH A FLAG** for fixings only.
Note the asymmetry: real-time refuses, fixings carry forward. The Indices rulebook layers a further
refusal on top (index not computed if any constituent price is missing or suspect).

**5. Publication frequency + lag — exact:**
- Real-time: publication interval **5s**.
- Fixings: **London 16:00 UTC & 16:00 BST/GMT; New York 20:00 UTC & 16:00 ET; Singapore 08:00 UTC.**
- Rounding: **"All rates are calculated with all available decimals but published with two decimals."**
  (The Indices rulebook says index values keep all decimals — the RATES are truncated to 2dp on
  publication. A reconstruction matching to sub-cent precision is chasing digits Kaiko does not publish.)
- Rebalancing calendar: quarterly (**March, June, September, December**); Cut-off = last day of the
  preceding month; ER Effective = first business day of review month; **Effective Date = the Monday
  after the third Friday of the rebalancing month, usually between 20:00 and 23:00 UTC.**

**6. A 2026 structural change the desk should note (v7, 13/04/2026):**
> "Certain trading venues operate combined order books that do not differentiate between fiat
> currency and stablecoin-denominated trades for a given asset. Where such structural practices are
> identified, **Kaiko will use the available trade data as-is rather than excluding the venue**, in
> order to preserve liquidity and market representativity."

i.e. Kaiko knowingly mixes USD and USDT prints on venues with combined books. Anyone diffing a
reconstruction that cleanly separates USD from USDT will see a systematic basis and misread it as
their own bug.

**7. Kaiko states replication as a DESIGN GOAL — in its own rulebook:**
> "Kaiko Benchmark Reference Rates are designed to **facilitate the methodology replication** and
> therefore the turnover of exchanges in the combination, from one period to the next one, is
> controlled."

That sentence is the whole vendor-replacement thesis, written by the vendor.

---

## GAP 1c — INDEPENDENT NON-KAIKO CORROBORATION: A **CBOE RULE FILING TO THE CFTC**

Everything above still came from Kaiko's own documents. The desk's stated failure mode on this card
is single-source reading. So the methodology was checked against a document Kaiko did not write:
**Cboe Futures Exchange's rule filing to the CFTC** for Perpetual-style Bitcoin futures (PBT),
which settle to the Cboe Kaiko Bitcoin Index.

- `https://cdn.cboe.com/resources/regulation/rule_filings/pending/2025/25-023-Bitcoin-Continuous-Futures.pdf`
- `https://www.cftc.gov/filings/orgrules/rules10202531765.pdf`
- **Both URLs return the byte-identical document** (654,696 bytes each, PDF-1.6). 47 pages,
  124,734 chars extracted. This one needed `/ObjStm` object-stream expansion (187 direct objects ->
  3,460 after expanding 47 object streams) — PDF 1.6 stores objects compressed inside streams.

**It confirms the methodology independently, in a regulator's own words:**
> "Kaiko implements an aggregation methodology that consists of a look-back that: • for the CKBRT,
> splits the 10-second reference rate calculation periods into 10 one-second segments (referred to as
> partitions); and • for the CKBR, splits the one-hour reference rate calculation periods into **10
> six-minute partitions**."

> "executed trades in each partition are subject to a volume-weighted median price calculation...
> Specifically, the volume-weighted median is calculated as **the price of the trade that lies at 50%
> of the cumulative volume for the partition**... Then, a time-weighted average price of all
> volume-weighted median prices across the partitions in a calculation window is calculated. **A
> time-weighted calibration method is applied which provides more weight to the most recent prices**...
> then normalized and aggregated..."

> "each constituent exchange must have at least **0.5%** of the total observed liquidity across all
> the constituent exchanges... over the past three months."

**Note the 0.5% vs the Kaiko rulebook's 1%.** The Cboe-specific product uses a 0.5% asset-specific
liquidity floor; Kaiko's own rulebook states 1%. These are different products with different
calibrations — do not treat the Cboe filing's numbers as Kaiko's house parameters.

**CAUTION — the regulator filing contains an internal error.** It says "the ten weighted prices for
the CKBRT partitions, and **the six weighted prices for the CKBR** partitions" — but it also says
CKBR uses **10** six-minute partitions, and Kaiko's own rulebook maps 3600s -> 10p. "Six" is a
drafting slip confusing *six-minute* with *six*. **10 is correct.** Recording this because it shows
even a CFTC filing is not automatically ground truth — the two sources had to be diffed against each
other, which is the entire point of independent verification.

### AND IT PUBLISHES THE CONSTITUENT LIST — which the card said was not public

The watchlist card's stated limit: *"Constituent set is five clean public USD venues, not Kaiko's own
vetted list (not public per-rate)."* **The constituent list for the flagship BTC rate IS public**, in
this filing (review period Oct 2024 - Sep 2025):

> "The **Kaiko Bitcoin Real-Time Rate** is comprised of pricing sourced from **Bitstamp, Crypto.com,
> Gemini, Kraken, and LMAX Digital**."

(For contrast the same page lists CME CF BRR = Bitstamp, Bullish, Coinbase, Crypto.com, Gemini,
itBit, Kraken, LMAX Digital; CoinDesk BPI = Bitstamp, Coinbase, Crypto.com, Gemini, itBit, Kraken,
LMAX Digital.)

**THIS BREAKS THE DESK'S EXISTING RECONSTRUCTION, AND THE BREAK IS LARGE.**
`data/kaiko_vwm_reference_rate.jsonl` was built from **coinbase (139,661 trades) / kraken (13,595) /
bitfinex (10,733) / bitstamp (10,210)**, with **Gemini deliberately excluded**.

| | Kaiko's actual BTC constituents | Desk's reconstruction |
|---|---|---|
| Bitstamp | YES | YES |
| Kraken | YES | YES |
| Gemini | YES | **excluded on purpose** |
| Crypto.com | YES | absent |
| LMAX Digital | YES | absent |
| Coinbase | **NOT a constituent** | **80.2% of the desk's tape** |
| Bitfinex | **NOT a constituent** | present |

Overlap is **2 of 5**, and the single largest contributor to the desk's tape (Coinbase, 80% of
trades by count) **is not in Kaiko's rate at all**. The desk's reported "median 1.42 bps vs our own
cross-venue VWAP" was therefore measured over a *different universe* than Kaiko prices. The
outlier-resistance conclusion (median beats mean under a shock) still holds — that is a property of
the estimator, not the venue set — **but the bps agreement figure is not evidence of tracking Kaiko.**
Any future diff must use Bitstamp + Crypto.com + Gemini + Kraken + LMAX.

Also referenced but not yet opened (level 3 of the chain, left as a named next step):
**"Cboe Kaiko Digital Asset Rates Rulebook, published September 2, 2025"** — a Cboe-specific rulebook
distinct from both documents extracted here.

---

## FREE KAIKO SURFACES — SEARCHED PROPERLY. ONE REAL FIND THE CARD MISSED.

Per the free-frontier axiom, a documented search was run rather than assumed.

### FOUND FREE (verified live, HTTP 200, keyless, this run)
**`reference-data-api.kaiko.io` — completely unauthenticated. The card never checked this host.**

| Endpoint | Status | Size | Content |
|---|---|---|---|
| `https://reference-data-api.kaiko.io/v1/exchanges` | 200 | 8,955 B | **149 exchanges**, `code` / `name` / `kaiko_legacy_slug` |
| `https://reference-data-api.kaiko.io/v1/instruments` | 200 | **676,185,303 B** | **2,213,397 instruments** |
| `https://reference-data-api.kaiko.io/v1/assets` | 200 | 2,887,846 B | asset reference data |
| `https://reference-data-api.kaiko.io/v1/pools` | 200 | 22,747,785 B | DEX pool reference data |

Each instrument record carries, free: `exchange_code`, `base_asset`, `quote_asset`, `class`
(spot/future/...), **`trade_start_time`**, **`trade_end_time`**, and **`trade_count`**. Example:
```
{"exchange_code":"btrx","code":"1st-btc","class":"spot",
 "trade_start_time":"2017-08-10T16:54:21.307Z","trade_end_time":"2020-06-22T14:38:32.7Z",
 "trade_count":1198938}
```
**What this actually is: a free, vendor-grade CENSUS of where crypto trade data exists** — 2.2M
instruments across 149 venues with exact first-trade/last-trade timestamps and trade counts,
including dead venues (MtGox, BTC-e, FTX, Ethfinex, C-CEX...). It contains **no prices**, so it does
not replace a data feed. But for answering "does venue X have pair Y, from when to when, and how
thick is it" — which is a question the desk pays other vendors to answer — it is free and
authoritative. **Recommend cataloguing it as a coverage/metadata source, not a price source.**
(It is also a database in the EU sui-generis sense — see the licence ruling below. Query it; do not
rehost it.)

Also 200 and login-free: `https://explorer.kaiko.com/` (473,980 B) and
`https://instruments.kaiko.com/` (70,765 B).

### CONFIRMED NOT FREE
- `https://us.market-api.kaiko.io/v2/data/index.v1/digital_asset_rates_price/{index_code}` -> **403**.
  Docs (`https://docs.kaiko.com/kaiko-indices/reference-rates/historical-prices`) require
  `X-API-KEY: $KAIKO_API_KEY`. **No free tier, no trial, no sample/public endpoint documented.**
  The actual rate VALUES are gated. Only the reference/metadata layer is open.
- `https://www.kaiko.com/pricing` -> 404 (consistent with the card's earlier refutation; pricing is
  quote-only). **The refuted "$1,000-2,500/mo" figure remains refuted — no dollar figure was found
  this run either. Do not resurrect it.**

### GITHUB ORG — CHECKED 2 LEVELS DEEP
`https://github.com/orgs/kaikodata/repositories` — **12 public repos, ZERO market data.** Confirms
the card. Inventory: `kaiko-sdk-examples`, `kaiko-rust-sdk`, `kaiko-cpp-sdk`, `kaiko-go-sdk`,
`kaiko-proto-public`, `vinter-sdk`, `canton-data-standard` ("Open Daml interfaces for the Kaiko Data
Standard on Canton"), `canton-tooling`, `vinter-cryptoicons`, `github-action-aws-cli`,
`github-action-pypi-publish`, `grpc-poc`.
**New signal the card did not note:** two `vinter-*` repos — Kaiko absorbed Vinter (the Swedish
crypto index administrator). Relevant if the desk ever tracks index-provider consolidation.
Every SDK is a *client* for the paid API; none ships data. **No free-data path exists via GitHub.**

---

## GAP 3 — IS KAIKO REPLACEABLE FROM FREE SOURCES? **VERDICT: (a) FULLY for the RATES. (b) PARTIALLY for the INDICES.**

The card graded this as one thing. Having read the actual rules, **it is two products with two
different answers**, and conflating them is why the card was vague.

### THE FIVE CONSTITUENT VENUES — PROBED LIVE THIS RUN, NOT ASSUMED

| Venue | Free keyless executed-trade data? | Evidence (probed 2026-07-26) |
|---|---|---|
| **Bitstamp** | **YES** | `https://www.bitstamp.net/api/v2/transactions/btcusd/?time=hour` -> 200, 61,914 B, tick-level `price`/`amount`/`date`/`tid` |
| **Kraken** | **YES** | `https://api.kraken.com/0/public/Trades?pair=XBTUSD&count=5` -> 200, tick-level; `since` cursor paginates history |
| **Gemini** | **YES** | `https://api.gemini.com/v1/trades/btcusd?limit_trades=3` -> 200, tick-level |
| **Crypto.com** | **YES** | `https://api.crypto.com/exchange/v1/public/get-trades?instrument_name=BTC_USD&count=3` -> 200, tick-level |
| **LMAX Digital** | **PARTIAL — forward only** | see below |

**LMAX Digital, run to ground rather than guessed.** Two invented URLs failed, so the real spec was
located: the docs page `https://docs.lmax.com/public-data-api/` is a Redoc shell that loads an
OpenAPI file. Pulled it directly:
`https://docs.lmax.com/public-data-api/public-api-with-tutorial.yaml` -> 200, 29,483 B.
- Base URL: **`https://public-data-api.london-digital.lmax.com`** — free, no account, no key.
- **Complete endpoint list: `/v1/orderbook/{id}`, `/v1/ticker/{id}`, `/v1/time`,
  `/v1/instruments/{id}`, `/v1/instruments`. THERE IS NO TRADES ENDPOINT.**
- Verified live: `/v1/time` -> 200; `/v1/instruments` -> 200, 35 instruments incl. **`btc-usd`**;
  `/v1/ticker/btc-usd` -> 200 returning `trade_id`, `last_price`, `last_quantity`, `best_bid/ask`,
  session OHL.
- The spec states: *"Ticker updates are **per trade** for each instrument"* on the WebSocket Ticker
  Channel. Rate limit on REST: **1 request/IP/second**, 429 for up to 1 hour if exceeded.

=> **LMAX executed-trade data is free and complete going FORWARD via the WS ticker channel, and
destroyed-at-source going BACKWARD** (no historical trades endpoint at any price on the public API).
This is structurally identical to the desk's bitFlyer card: start a recorder and you own it from that
day; you can never buy back yesterday for free.

### COMPONENT-BY-COMPONENT RULING

| Kaiko component | Reconstructable free? | Why |
|---|---|---|
| Executed-trade inputs (4 of 5 venues) | **YES, incl. history** | keyless public REST, verified live above |
| Executed-trade inputs (LMAX) | **FORWARD ONLY** | no historical trades endpoint; WS ticker is per-trade |
| VWM at 50% cumulative volume | **YES** | published verbatim in 2 independent documents |
| Partition count (10; 5 for 15s) | **YES** | published in rulebook §Partitioning Scheme + CFTC filing |
| Calculation window (300s RT / 3600s fixing, static for Reference Rates) | **YES** | published table |
| Inverse-time recency weighting + normalisation | **YES in form, exact equation UNVERIFIED** | wording published; equation is a symbol-font image |
| Fixing times (16:00 / 20:00 / 08:00 UTC) | **YES** | published |
| Missing/delayed/spurious data handling | **YES** | published verbatim, all three cases |
| Dynamic windowing (Benchmark Rates) | **YES — computable** | thresholds (10/5/15/2.5/7.5%) and the zero-volume-bucket rule are published, and zero-volume buckets are computable from free trade data |
| Exchange liquidity gate (1% of KVEL volume, 3-month) | **YES — computable** | published; needs only free volumes |
| Top-10 liquidity cap, up-to-5 final combination | **YES** | published |
| Constituent list for the BTC rate | **YES** | named in the CFTC/Cboe filing |
| Constituent lists for OTHER rates | **NO** | not systematically published per rate |
| Qualitative exchange vetting (KYC/AML "Strong", trading policies "Significant", "stable and open country") | **NO** | Kaiko Exchange Ranking judgements, not formulas |
| Index selection/weighting/capping/buffering maths | **YES** | 75/25 rank, 50/50 weight, 30% cap, 80/120 buffer, 2/3 & 3/2 segment buffers, Laspeyres + divisor — all published with exact numbers |
| **Circulating supply per asset** | **NO — THIS IS THE REAL BLOCKER** | Kaiko Indices Research proprietary model; 9 published *exclusion categories* but per-asset determinations are research judgements |
| Kaiko Asset Taxonomy / Theme classification | **NO** | proprietary classification (3 classes / 9 categories / 19 subcategories) |
| Published rate + index VALUES | **NO** | 403, API-key gated, no free tier |

### THE VERDICT, STATED PLAINLY

**RATES = (a) FULLY RECONSTRUCTABLE.** Every parameter needed to compute a Kaiko-methodology
reference rate is published, and 4 of the 5 BTC constituent venues serve tick history free and
keyless today. This is a stronger answer than the card's — the card believed window, partition count
and decay were unpublished; **all three are published**, they were just in a *second* PDF reachable
only through a link annotation in the first.

**INDICES = (b) PARTIALLY RECONSTRUCTABLE.** All the index *mathematics* is published to the last
constant. The irreducible input is **circulating supply**, which drives asset selection, weighting,
capping and the divisor. Kaiko's supply model is explicitly proprietary and explicitly restrictive
(excludes foundation-held, staked-for-governance, lost-key, unactivated-fork, founder/employee,
seed/private/public investor, PoS-locked, governance-locked, and legally-restricted tokens). Free
proxies exist (CoinGecko / CoinMarketCap / Coin Metrics `SplyCur`) but **none implements that
exclusion list**, so index levels will diverge structurally, not just numerically.

### WHAT IS MISSING — NAMED EXACTLY (5 items)
1. **Circulating supply under Kaiko's restrictive definition.** The one hard blocker. Blocks the
   index family; does **not** block the rates.
2. **LMAX Digital trade history** (pre-recorder-start). Free forward, gone backward.
3. **Per-rate constituent exchange lists** for anything other than the BTC rate.
4. **The literal recency-weighting equation** (verbal spec recovered; typeset formula not).
5. **Kaiko Exchange Ranking qualitative scores** — irreducibly judgemental, not computable.

### CORRECTIONS THE WATCHLIST CARD NOW OWES (do not let these rot)
1. "window length, partition count and the recency decay are NOT published" -> **REFUTED, all three published.**
2. "12x5min" -> **WRONG, it is 10 partitions** (3600s/10p = 6 min each).
3. "linear ramp" -> **WRONG, weights are inversely proportional to time, then normalised.**
4. "Constituent set ... not public per-rate" -> **REFUTED for the BTC rate** (Bitstamp, Crypto.com, Gemini, Kraken, LMAX Digital).
5. The reconstruction's venue set is **2-of-5 correct** and 80% dominated by a **non-constituent**
   (Coinbase); Gemini was excluded but is an actual constituent. The 1.42 bps agreement figure does
   not mean what the card implies.
6. "no PDF tooling on this box" -> true but **not a blocker**; stdlib `zlib` is sufficient.

---

## GAP 4 — FACTS vs LICENSED PRODUCT: WHICH SIDE EACH COMPONENT FALLS ON

The task's framing is right and worth stating precisely: **facts are not copyrightable, methods are
not copyrightable, but curated compilations and expressive text are protected — and databases get an
extra layer in the EU.**

### FREE SIDE — the desk may take these, they are not Kaiko's to license
- **The executed trades themselves.** Prices, volumes and timestamps of real transactions are
  *facts*. They belong to no one; the venues publish them; Kaiko merely also collects them. Pulling
  them from Bitstamp/Kraken/Gemini/Crypto.com/LMAX touches nothing of Kaiko's. (Each venue's own ToS
  still applies — that is a separate, per-venue question the desk already handles.)
- **The methodology as an idea/procedure.** VWM at the 50% cumulative-volume point; 10 equal
  partitions; inverse-time weights normalised; drop empty partitions and re-normalise; 1% liquidity
  floor; 10%/5%/15%/2.5%/7.5% buffer thresholds; 80/120 rules; Laspeyres with a divisor. These are
  **methods of operation**, expressly outside copyright (US 17 U.S.C. §102(b) excludes "any idea,
  procedure, process, system, method of operation"; in the EU, ideas and principles are likewise
  unprotected). **Kaiko publishes them because BMR/IOSCO transparency effectively compels it** — a
  regulated administrator cannot both claim benchmark transparency and keep the method secret.
- **Individual facts quoted for research** (e.g. "Kaiko uses 10 partitions") — reporting a fact about
  a published document.

### LICENSED / RESTRICTED SIDE — do not take these
- **The rulebook PDFs as documents.** The prose, tables and layout are copyrightable *expression*.
  Read them, quote briefly with attribution, **do not rehost or redistribute the files.** (Nothing
  was rehosted this run; downloads were to `/tmp` and are not in the repo.)
- **Kaiko's published rate values and index levels.** A curated output series. In the EU this is
  additionally covered by the **sui generis database right** (Directive 96/9/EC), which protects
  substantial investment in obtaining/verifying/presenting a database *independently of* copyright,
  and bites on extraction of a substantial part. Kaiko is a French entity — EU law is the operative
  regime.
- **`reference-data-api.kaiko.io` bulk contents.** Free to *query*; it is still a database.
  Systematic bulk extraction and re-publication is the classic sui-generis infringement. Query it,
  cache what you need, do not mirror all 676 MB as a product.
- **The names.** "Kaiko", "Kaiko Benchmark Reference Rate", the KT/KM/KS tickers and the ISINs are
  identifiers of *their* product. A desk reconstruction must not be labelled as, or held out to be, a
  Kaiko rate.

### THE DISCLAIMER — READ IT, AND NOTE THAT IT CONTRADICTS ITSELF
Both rulebooks carry (Indices p.30, Rates p.21):
> "This document and all of the information contained in it... is the property of **Challenger Deep
> SAS** or its subsidiaries (collectively, "Kaiko")... The Information may not be modified,
> **reverse-engineered**, reproduced or redisseminated... **The Information may not be used to create
> derivative works or to verify or correct other data or information.** For example (but without
> limitation), the Information **may not be used to create indexes, databases, risk models,
> analytics, software**..."

Three things the desk must register:
1. **New corporate fact:** the copyright owner is **Challenger Deep SAS**, the parent. ESMA registers
   **Kaiko Indices SAS**. Neither name is plain "Kaiko". Three entities wear one brand.
2. **On its face this clause purports to forbid exactly what a vendor-replacement project does** —
   use the published methodology to build analytics/indices, or to "verify or correct other data".
   Taken literally it forbids even *diffing* a desk series against Kaiko's.
3. **It contradicts the notice on the very next page of the same document** (Indices Rulebook p.31):
   > "Any use, reproduction or distribution **is permitted only if ownership and source are expressly
   > attributed to Kaiko**."
   That is a permission-with-attribution grant sitting one page after a blanket prohibition. **A
   single document says both "no use" and "use with attribution".**

### RULING (and the limit of my authority)
- **The clean path needs none of this resolved.** Collecting trades directly from the five venues and
  running an independently-implemented, publicly-documented algorithm over them uses **zero Kaiko
  property**: not their data, not their text, not their database. The method is an unprotectable
  procedure; the trades are facts from third parties. **That path is legitimate and is the one the
  desk should take.**
- **What is NOT an agent call:** whether a unilateral notice inside a freely-downloadable PDF, with
  no clickwrap and no assent, contractually binds a party who never accepted it — and whether a
  regulated administrator can enforce secrecy over a methodology it is obliged to publish. That is a
  legal question. Per §13 it is **NOT self-approved.** Route to the legitimacy queue alongside the
  Upbit and CC-BY-NC rulings (GAP_REGISTER #67).
- **Interim discipline, adopted now:** (i) rehost no Kaiko PDF; (ii) mirror no Kaiko database; (iii)
  never label a desk output as a Kaiko rate; (iv) attribute the *method* to Kaiko's published
  rulebooks in internal docs; (v) treat any diff-against-Kaiko-values as blocked until the ruling,
  since values are the API-gated, database-right-protected part.

**Practical consequence: the licence question does not block the work.** The desk can build and use
a VWM+TWAP reference rate over self-collected trades today. What it cannot do without a ruling is
benchmark that rate *against Kaiko's published values*.



