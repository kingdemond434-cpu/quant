# [LIT-a run 7] RETRACTION / FAILED-REPLICATION — **MECHANISED**

_Opened 2026-08-12 by the literature deep-miner, retraction/failed-replication seat (run 7)._
_**Write-as-you-go**: every item is appended the moment it resolves, so a mid-run kill leaves
durable output rather than a header._

**MANDATE DELTA vs prior runs.** Runs 2–6 hand-searched this ground (11 findings, 4 graveyard rows,
3 method rails; run 6 found "wave-2" by hand). This run's job is to turn it into a **reproducible
query family** against the public Retraction Watch / Crossref corpus, and to **grade every hit
editorial-vs-fraud**, because the two imply OPPOSITE priors:

> **fraud / fabrication / unreliable-results ⇒ the underlying MECHANISM is unevidenced and dies.**
> **citation-cartel / peer-review-manipulation / authorship-sale / rogue-editor ⇒ the mechanism may
> be perfectly fine and only the CITATIONS are fake. This is NOT a mechanism kill and must never be
> banked as one.**

**Headline, stated first and bluntly:** the finance/crypto retraction wave the desk has been tracking
is **overwhelmingly EDITORIAL, not empirical**. In the journals the desk actually mines, it kills
**almost no mechanisms**. It is a *provenance* event. The three genuinely mechanism-killing finance
retractions found in the entire corpus are named in §3 and only one of them is remotely desk-adjacent.
**Counting retractions was never the deliverable; here is the honest count and the honest zero.**

---

# 1. THE MECHANISED ROUTE — exact, licensed, scriptable

**Status: FULLY ESTABLISHED AND EXECUTED FROM THIS BOX.** Not a lead — the 65 MB corpus was
downloaded, parsed and sliced during this run. Everything below is reproducible verbatim.

## 1.1 The corpus and who owns it

Crossref **acquired the Retraction Watch database from the Center for Scientific Integrity in
September 2023** and publishes it openly. Verbatim from the repository README (`[PRIMARY]`, fetched
this run, HTTP 200):

> *"In September 2023, Crossref acquired the Retraction Watch database from the Center of Scientific
> Integrity and have made it publicly available. The database contains retractions gathered from
> publisher websites and is updated every working day by Retraction Watch."*

The README also states the snapshot date inline: *"This repository contains the latest dataset from
Retraction Watch, generated on **2026-08-11**"* — i.e. **one day stale at time of use**, which is the
freshness guarantee a scheduled desk job would inherit.

## 1.2 The two working download routes (BOTH verified HTTP 200 from this box)

| Route | URL | Result observed this run |
|---|---|---|
| **A — GitLab raw (canonical, versioned)** | `https://gitlab.com/crossref/retraction-watch-data/-/raw/main/retraction_watch.csv` | HTTP 200, **65,664,677 bytes**, `text/plain; charset=utf-8` |
| **B — Crossref Labs API (freshest)** | `https://api.labs.crossref.org/data/retractionwatch?<your@email>` | HTTP 200, **65,765,851 bytes** |
| File listing (to confirm repo shape) | `https://gitlab.com/api/v4/projects/crossref%2Fretraction-watch-data/repository/tree` | HTTP 200 — exactly two blobs: `README.md`, `retraction_watch.csv` |

**Route B was ~101 KB LARGER than route A on the same day.** Do not assume they are identical
snapshots. Prefer **A** for reproducibility (git-versioned, diffable across days → you can compute
*arrivals*, see §5); prefer **B** for maximum freshness.

⚠️ **The Crossref Labs page self-deprecates.** `https://www.crossref.org/labs/retraction-watch/`
(`[PRIMARY]`, HTTP 200) points at the GitLab repo and states the Labs API is outdated, directing
users to production services. It still served the CSV correctly today. **Treat route B as
best-effort and route A as the durable one.**

## 1.3 Licence — the §13 answer

- Crossref's standing metadata position: *"Almost all of the metadata held by Crossref is reusable
  without restriction... The majority of metadata is considered to be 'facts' which are not
  copyrightable and are thus in the public domain (CC0)."*
- **HONEST LIMIT, recorded rather than rounded up:** neither the GitLab README nor the Labs landing
  page carries an explicit `CC0` / `CC-BY` string *for this specific CSV*. The CC0 characterisation
  is Crossref's **general metadata policy**, applied here by inference.
- **Operational ruling for this desk: SAFE TO USE as an internal research/provenance screen**
  (bibliographic facts: DOI, journal, date, reason code — the least copyrightable material there is;
  published deliberately for reuse; no paywall circumvented; no key involved). **NOT cleared for
  redistribution of the CSV itself**, which is a different act and needs an explicit licence string
  the desk does not have. If a future use is redistributive, get the string first.
- The `Title` field is the only column with any plausible copyright colour, and titles are de minimis.

## 1.4 Field structure (verbatim from the README) and what each is worth

`Record ID · Title · Subject · Institution · Journal · Publisher · Country · Author · URLS ·
ArticleType · RetractionDate · RetractionDOI · RetractionPubMedID · OriginalPaperDate ·
OriginalPaperDOI · OriginalPaperPubMedID · RetractionNature · Reason · Paywalled · Notes`

Parsing rules that matter and will silently corrupt a naive script:
- **Multi-values inside one cell are `;`-separated** (authors, subjects, reasons). README: *"lists in
  a single entry separated by a semicolon"*.
- **There is a trailing empty column** (every row ends `,`) — `DictReader` yields a `''` key. Ignore it.
- `Reason` tokens are frequently prefixed `+` in the raw file — **strip a leading `+` before matching**
  or your reason histogram fragments.
- `RetractionDOI` / `OriginalPaperDOI` absence is encoded **three different ways**: blank,
  `unavailable`, `Unavailable`. PubMed absence is blank **or `0`**.
- `RetractionDate` is US `M/D/YYYY 0:00`. Do not `strptime` with a fixed width.
- `Reason` uses a **controlled vocabulary** maintained by Retraction Watch
  (`retractionwatch.com/retraction-watch-database-user-guide/...appendix-b-reasons/`). This is the
  single most valuable column for this desk and it is the whole basis of §1.6.
- `RetractionNature` ∈ {Retraction, Expression of concern, Correction, Reinstatement} — **note
  `Reinstatement` exists (160 rows corpus-wide): a retraction can be REVERSED.** A screen that
  treats the DB as monotone will keep punishing a cleared paper.

**Corpus totals measured this run (n = 71,743 rows):**

| RetractionNature | count |
|---|---|
| Retraction | 66,204 |
| Expression of concern | 3,586 |
| Correction | 1,499 |
| *(blank)* | 294 |
| Reinstatement | 160 |

## 1.5 ⚠️ THE SLICING TRAP — `Business - Finance` DOES NOT EXIST

**This is the routing finding of the run and it is a false-exhaustion generator.**

The obvious slice — filter `Subject` for finance — returns **exactly ZERO**:

```
(B/T) Business - Finance      -> 0 rows        <-- THE TERM IS NOT IN THE VOCABULARY
```

The complete `Business` sub-vocabulary is only these seven:

| Subject token | rows |
|---|---|
| `(B/T) Business - Economics` | **4,179** |
| `(B/T) Business - Management` | 3,088 |
| `(B/T) Business - General` | 2,098 |
| `(B/T) Business - Marketing` | 773 |
| `(B/T) Business - Manufacturing` | 620 |
| `(B/T) Business - Accounting` | 618 |
| `(B/T) Business - Public Relations` | 127 |

**Finance is filed under `Business - Economics` (and often `Business - Accounting` alongside).** A
scripted pass that greps for "Finance" gets a clean, confident, totally wrong zero — the exact
third-false-exhaustion mode the desk has already been bitten by (`pairs trading brasil` → 0). **The
Subject field is also NOT reliable on its own**: the Lucey crypto papers carry
`Business - Accounting; Business - Economics` and one carries `Business - General` with **no
Economics tag at all**.

**Therefore the correct slice is a UNION of three independent keys, never Subject alone:**
1. `Subject` ∈ {`Business - Economics`, `Business - Accounting`, `Business - General`}
2. `Journal` ∈ an explicit finance-journal name list (exact match — see §1.6)
3. `Title` regex for the crypto/finance mechanism vocabulary

## 1.6 What a future scripted pass should run

```python
# ROUTE: GET https://gitlab.com/crossref/retraction-watch-data/-/raw/main/retraction_watch.csv
# (verified 200 from this box 2026-08-12; egress to gitlab.com + api.labs.crossref.org WORKS)
csv.field_size_limit(10**9)                      # Notes/Author fields blow the 128k default
rows = list(csv.DictReader(open(path, encoding='utf-8', errors='replace')))
reasons = lambda r: {s.strip().lstrip('+').strip()
                     for s in (r['Reason'] or '').split(';') if s.strip()}

FRAUD = {   # data/result integrity destroyed  => MECHANISM DIES
  'Falsification/Fabrication of Data','Falsification/Fabrication of Image',
  'Falsification/Fabrication of Results','Manipulation of Images','Manipulation of Results',
  'Concerns/Issues about Data','Error in Data','Unreliable Results and/or Conclusions',
  'Concerns/Issues about Results and/or Conclusions','Error in Results and/or Conclusions',
  'Results Not Reproducible','Duplication of Data','Paper Mill','Error in Analyses',
  'Error in Methods','Concerns/Issues about Methods','Randomly Generated Content',
  'Computer-Aided Content or Computer-Generated Content',
  'Original Data and/or Images not Provided and/or not Available',
  'Misconduct by Author','Misconduct - Official Investigation(s) and/or Finding(s)'}

INTEGRITY = {  # process/citation/authorship => MECHANISM UNTOUCHED, do NOT bank as a kill
  'Rogue Editor','Conflict of Interest','Concerns/Issues about Peer Review',
  'Compromised Peer Review','Fake Peer Review','Sale of Authorship',
  'Concerns/Issues about Referencing/Attributions','Concerns/Issues about Authorship/Affiliation',
  'Objections by Author(s)','Investigation by Journal/Publisher','Investigation by Third Party',
  'Plagiarism of/in Article','Plagiarism of Text','Euphemisms for Plagiarism',
  'Duplication of/in Article','Euphemisms for Duplication','Breach of Policy by Author',
  'Ethical Violations by Author','Removed','Notice - Limited or No Information',
  'Date of Article and/or Notice Unknown','Error by Journal/Publisher','Error in Text', ...}
# grade = FRAUD if (R & FRAUD) else INTEGRITY-ONLY ; report MIXED when both fire.
```

**Two standing cautions for the scripted version, both learned the hard way this run:**
- **`Investigation by Journal/Publisher` is NOT a fraud signal.** It fires on 587 of 703 rows in the
  finance-journal slice — it means "the publisher looked", nothing about what they found. Classing it
  as fraud would grade essentially the whole corpus as fabrication.
- **`Unreliable Results and/or Conclusions` is the true fraud-side workhorse token**, and it is the
  one that separates a mechanism kill from a process kill. When it is ABSENT and only
  `Rogue Editor` / `Conflict of Interest` / referencing tokens are present, **the empirics were never
  impeached** and the desk must say so out loud.

**Also available and NOT used this run (named so it is not mistaken for exhausted):** the Crossref
REST API carries the same signal live at `https://api.crossref.org/works?filter=is-update:true`
(**HTTP 200 from this box, 469,019 total-results**), where each item carries an `update-to` array
with `{DOI, type: retraction|corrigendum|..., label, source, updated}`. The Crossref Labs page's own
instruction: *"See the `updated-by` field to know if a particular record has been retracted and
when."* That is the route for checking **one DOI at a time** (e.g. screening the desk's own citation
list, §5); the CSV is the route for **corpus sweeps**. Both are open and keyless.

---

# 2. THE WAVE, CHARACTERISED

## 2.1 The economics slice is a MIRAGE — 43% of it is one IEEE conference purge

`Business - Economics` = 4,179 rows, and the year histogram has an enormous 2009–2011 hump
(237 / 574 / 1,002). **That hump is not a research-integrity wave at all.** Measured:

- **1,813 rows** fall in 2009–2011; **1,787 of them are published by IEEE**, in conference
  proceedings — `2011 International Conference on E-Business and E-Government (ICEE)` alone is
  **695 rows**, plus `2009 Intl Conf on Management and Service Science` (164), `2010 ICEE` (116) etc.
- Their reason codes are administrative, not scientific: `Notice - Limited or No Information` (1,761),
  `Breach of Policy by Author` (1,165), `Date of Article and/or Notice Unknown` (1,062), `Removed` (187).

**This is a bulk conference-proceedings withdrawal, and it carries zero information about any
mechanism.** Any desk metric computed over "economics retractions" without excluding IEEE
proceedings will be dominated by it. Recorded because a naive year-over-year "retractions are
exploding in economics" chart is 43% this one artifact.

## 2.2 The crypto TITLE slice is a different mirage — it is the Hindawi paper mill

Crypto/blockchain title regex over the whole corpus → **226 rows** (224 Retraction, 2 Expression of
concern). Year peak 2023 (107), 2024 (54), 2022 (21).

**But look at the journals:**

| rows | journal |
|---|---|
| 39 | Security and Communication Networks |
| 18 | Journal of Intelligent & Fuzzy Systems |
| 16 | Computational Intelligence and Neuroscience |
| 15 | Soft Computing |
| 13 | Journal of Healthcare Engineering |
| 11 | Wireless Communications and Mobile Computing |
| 10 | Journal of Sensors |
| 6 | Mobile Information Systems |

These are the **Hindawi/Wiley special-issue paper-mill mass retractions of 2022–2024**. The papers are
*blockchain-as-a-technology* papers (IoT security, supply chain, healthcare records) — **not crypto
asset-pricing empirics.** Reason codes on the econ∩crypto intersection confirm it: `Paper Mill` (12),
`Computer-Aided Content or Computer-Generated Content` (12), `Rogue Editor` (8), `Compromised Peer
Review` (6).

**Consequence for the desk: the big scary crypto retraction number is ~95% irrelevant.** It is a
computer-science publishing scandal that happens to use the word "blockchain". It touches no
tradeable mechanism. **Do not let a future run cite "226 crypto retractions" as evidence about the
crypto finance literature.**

## 2.3 The REAL slice — core finance/economics journals: **55 rows in the entire database history**

Exact-name match against 22 core finance/econ journals (FRL, IRFA, IREF, JF, JFE, RFS, JFM, Physica A,
JRFM, RIBAF, Economics Letters, Economic Modelling, Energy Economics, Resources Policy, Journal of
Asset Management, Financial Review, Borsa Istanbul Review, NAJEF, International Review of Economics,
…): **55 rows, all natures, all years.**

| rows | journal | | rows | journal |
|---|---|---|---|---|
| 15 | Economic Modelling | | 2 | Physica A |
| 8 | International Review of Financial Analysis | | 2 | Resources Policy |
| 5 | Energy Economics | | 1 each | JFE · RFS · JFM · JRFM · RIBAF · Financial Review · Borsa Istanbul · IRE · NAJEF · J. Asset Mgmt |
| 4 | International Review of Economics & Finance | | | |
| 3 | Finance Research Letters · The Journal of Finance · Economics Letters | | | |

**That is the honest size of the "wave" in the corpus this desk mines: fifty-five papers, ever.**

### THE EDITORIAL-vs-FRAUD SPLIT — the number the mandate asked for

Grading all 55 core-finance rows individually by reason code:

| Grade | count | share |
|---|---|---|
| **INTEGRITY-ONLY** (process/citation/authorship — **mechanism untouched**) | **45** | **82%** |
| **FRAUD/DATA-side** (results impeached — **mechanism dies**) | **10** | **18%** |

And on the wider `Business - Economics` retraction slice (n = 4,131 retractions):

| Grade | count | share |
|---|---|---|
| INTEGRITY-ONLY | 2,718 | 65.8% |
| MIXED (both fire) | 1,334 | 32.3% |
| **FRAUD/DATA only** | **51** | **1.2%** |
| unclassified residual | 28 | 0.7% |

**The wave is editorial. Overwhelmingly. In the desk's own journals it is 82% editorial, and
pure-fraud economics retractions are ~1% of the slice.**

## 2.4 The Lucey cluster, now COMPLETE and reason-coded (run 6 had 2 of 12)

Run 6 found "Datestamping" + the Naeem FRL paper by hand. The mechanised pass returns the **whole
cluster: 12 finance retractions authored by Brian Lucey** (a 13th `Lucey` hit is an unrelated 2017
PNAS microbiology paper by *Jean F* Lucey — a name collision a naive author-key would have banked).

**Every single one of the 12 carries the IDENTICAL reason string:**

> `Conflict of Interest; Investigation by Journal/Publisher; Objections by Author(s); Rogue Editor;`
> *(+ `Date of Article and/or Notice Unknown` on the three whose notice date RW had to infer)*

**Zero data-side tokens. Not one.** No `Falsification`, no `Concerns/Issues about Data`, no
`Unreliable Results and/or Conclusions`. Retraction Watch's own controlled vocabulary says, in the
desk's language: *the editorial process was compromised; the empirics were never impeached.*

| # | Journal | Year | Title | Desk-relevant? |
|---|---|---|---|---|
| 1 | **FRL** | 2018 | **Datestamping the Bitcoin and Ethereum bubbles** (Corbet–Lucey–Yarovaya) | **YES** — GSADF/PSY bubble dating |
| 2 | **FRL** | 2019 | **Trading volume and the predictability of return and volatility in the cryptocurrency market** (Bouri–Lau–Lucey–Roubaud) | **YES — NEW to the desk** |
| 3 | **IRFA** | 2019 | **Cryptocurrencies as a financial asset: A systematic analysis** (Corbet–Lucey–Urquhart–Yarovaya) | YES — the 707-citation survey |
| 4 | **IRFA** | 2019 | **Is Bitcoin a better safe-haven investment than gold and commodities?** (Shahzad–Bouri–Roubaud–Kristoufek–Lucey) | **YES — NEW to the desk** |
| 5 | IRFA | 2019 | Identifying the multiscale financial contagion in precious metal markets | no |
| 6 | IRFA | 2020 | Extreme spillovers across Asian-Pacific currencies: A quantile-based analysis | no |
| 7 | IRFA | 2022 | Financing Irish high-tech SMEs: capital structure | no |
| 8 | IRFA | 2023 | Impacts of climate policy uncertainty on stock markets | no |
| 9 | IRFA | 2023 | Feature importance in predicting corporate financial distress (China) | no |
| 10 | IREF | 2022 | Oil price shocks and yield curve dynamics in emerging markets | no |
| 11 | IREF | 2024 | ESG disclosure and internal pay gap (China) | no |
| 12 | IREF | 2024 | Volatility forecasting on China's oil futures (ensemble boosting trees) | marginal |

**DOIs captured for all 12** (original + retraction notice) — e.g. #1 orig `10.1016/j.frl.2017.12.006`
(notice DOI *identical*, i.e. an in-place HTML overwrite; RW's `Notes` says so: *"date of retraction
unknown, html page overwrite, date taken from the modification date on the pdf"*), #3 orig
`10.1016/j.irfa.2018.09.003` → notice `10.1016/j.irfa.2026.105078`.

**Retraction dates cluster hard: 2025-12-18, 2025-12-22, 2026-01-22, 2026-02-01** — a coordinated
publisher sweep, not twelve independent findings.

## 2.5 The Naeem/Yarovaya wave-2 item — desk's `[SUMMARY-ONLY]` flag CLOSED

Run 6 recorded the Rahman–Naeem–Yarovaya–Mohapatra FRL 2024 retraction with *"reason text
[SUMMARY-ONLY] — ScienceDirect 403s this box"*. **Now resolved from the RW controlled vocabulary,
`[PRIMARY]` (record 71628):**

> `Concerns/Issues about Authorship/Affiliation; Concerns/Issues about Peer Review;`
> `Concerns/Issues about Referencing/Attributions; Investigation by Journal/Publisher;`
> `Objections by Author(s);`

Original 2024-05-28 (`10.1016/j.frl.2024.105633`) → retraction 2026-05-28
(`10.1016/j.frl.2026.110147`). **Grade: INTEGRITY-ONLY.** Note the composition — authorship +
peer review + *referencing/attributions*. That is the **citation-cartel signature**, and it is a
DIFFERENT signature from the Lucey cluster's `Rogue Editor` + `Conflict of Interest`. Two distinct
editorial failure modes in the same journal, two years apart. **Neither impeaches an empirical
result.**

## 2.6 Expressions of Concern — weak, and the desk should treat them as weak

`Business - Economics` EoCs: **33 rows, corpus-wide, ever.** Twelve of them are one journal
(`The International Journal of Electrical Engineering & Education`, all stamped 2021-12-15 — another
bulk event). **There is no EoC wave in finance.** Per the mandate: an EoC is *weaker* than a
retraction — it is "we are looking", not "we concluded". **Nothing in §3 rests on an EoC.**

## 2.7 Heliyon — big number, small relevance

Heliyon is the largest single journal in the finance-name slice (615 rows) but it is a
**multidisciplinary megajournal**: only **77** of the 615 carry the `Business - Economics` subject.
Its reason profile is the mass-integrity-sweep shape (`Investigation by Journal/Publisher` 560,
`Unreliable Results and/or Conclusions` 470, `Objections by Author(s)` 351,
`Concerns/Issues about Referencing/Attributions` 288). **No desk-relevant asset-pricing mechanism
surfaced in it.** Named so it is not re-chased as a lead.

---

# 3. GRAVEYARD CANDIDATES — mechanisms killed, and the much longer list of mechanisms NOT killed

**Grading vocabulary used, per the mandate:**
- **STRUCTURAL** — blocks the mechanism forever.
- **STATISTICAL** — underpowered/fragile; does NOT block; re-specify and it may live.
- **INTEGRITY-ONLY** — the citations/process are fake, **the mechanism is untouched. DO NOT BANK AS A
  MECHANISM KILL.** This is the honest majority verdict on this ground.

## 3.1 The four crypto/finance mechanisms in the Lucey cluster — ALL INTEGRITY-ONLY

Every one of these was retracted with `Rogue Editor; Conflict of Interest; Investigation by
Journal/Publisher; Objections by Author(s)` and **no data-side reason token whatsoever.**

**(a) GSADF/PSY bubble datestamping on BTC/ETH** — *Datestamping the Bitcoin and Ethereum bubbles*
(FRL 26, 2018). CLAIMED: recursive right-tailed unit-root tests (Phillips–Shi–Yu) identify and date
explosive sub-periods in BTC/ETH prices, i.e. bubbles are detectable in real time from price alone.
DIED OF: an editor handling his own paper. **INTEGRITY-ONLY — the econometrics were never
impeached.** *But note the desk does not need this row anyway*: GSADF is a price-only construction
and falls inside the standing `420 hypotheses / 0 survivors` price-only kill and the
`lit_intraday_ohlcv_mnq_14of14` extension. The retraction changes its CITABILITY, not its
tradeability. Already banked as `lit_retraction_wave_2026_datestamping_naeem`; this run confirms the
reason code `[PRIMARY]` and adds the DOIs.

**(b) ★ Trading volume predicts crypto return AND volatility** — *Trading volume and the
predictability of return and volatility in the cryptocurrency market* (FRL 29, 2019; Bouri, Lau,
Lucey, Roubaud). **NEW — the desk did not have this one.** CLAIMED: crypto trading volume carries
incremental predictive content for both returns and volatility. DIED OF: editorial self-dealing.
**INTEGRITY-ONLY — do not bank as a mechanism kill.** The desk's *independent* reason to leave this
alone is much stronger than the retraction: `lit_crypto_xsec_size_and_volume` (Fieberg–Liedtke–
Zaremba + Li–Zhu) already kills crypto volume cross-sectionally on mechanism grounds, and Fieberg's
NSE interior puts volume among the LEAST design-sensitive but still non-surviving variables.
**Correct desk posture: the mechanism was already dead on evidence; the retraction merely means the
paper cannot be cited either way.**

**(c) BTC as a safe haven vs gold/commodities** — *Is Bitcoin a better safe-haven investment than
gold and commodities?* (IRFA 63, 2019; Shahzad, Bouri, Roubaud, Kristoufek, Lucey). **NEW — the desk
did not have this one.** CLAIMED: BTC provides (weak) safe-haven properties against equity
drawdowns, conditionally and by horizon. **INTEGRITY-ONLY.** Desk-adjacent because the
"digital gold / debasement hedge" family sits in `do_not_repeat` as `digital_gold_rotation`
(REJECTED 2026-07-22, ev 0.0005, `price_only+crowded_known`) — **already dead on the desk's own EV
gate, independently.** The retraction adds nothing to the kill and must not be double-counted.

**(d) The 707-citation crypto survey** — *Cryptocurrencies as a financial asset: A systematic
analysis* (IRFA 62, 2019). A literature survey, not a mechanism. **INTEGRITY-ONLY.** Its importance
is purely as a provenance node: it is the single most-cited item in the retracted set, and anything
downstream that cites it for a *stylised fact* is resting on a retracted survey rather than on
primary evidence.

## 3.2 The Naeem/Yarovaya wave-2 item — INTEGRITY-ONLY, different signature

*Unravelling systemic risk commonality across cryptocurrency groups* (FRL 65, 2024). CLAIMED:
network/connectedness decomposition identifies common systemic-risk factors across crypto groups.
Reason set is authorship + peer review + **referencing/attributions** — the citation-cartel
signature, not the rogue-editor one. **INTEGRITY-ONLY.** The desk's zero-mapping stands: the
connectedness genre produces no tradeable construction the desk has ever been able to map.

## 3.3 ★★ THE ONE GENUINE MECHANISM KILL — and it is a FAILED REPLICATION, in the Journal of Finance

**`Risk Management in Financial Institutions` — Rampini, Viswanathan & Vuillemey, Journal of Finance
75(2):591–637 (2020). RETRACTED 2021-07-05.**

RW reason codes (`[PRIMARY]`, record from the corpus):
`Error in Analyses; Original Data and/or Images not Provided and/or not Available; Unreliable
Results and/or Conclusions` — **the fraud/data side of the grader, unambiguously.**

- **CLAIMED MECHANISM** (verbatim abstract via RePEc/IDEAS): *"Institutions with higher net worth
  hedge more, controlling for risk exposures, across institutions and within institutions over
  time."* Identification: net-worth shocks from loan losses due to house-price declines; institutions
  sustaining such shocks *"reduce hedging significantly relative to otherwise-similar institutions"*,
  most strongly where real-estate exposure is high. Interpretation: *"financial constraints impede
  both financing and hedging."*
- **HOW IT DIED — this is the part that matters.** Retraction notice, verbatim: *"The authors hereby
  retract the above article... A replication study finds that the replication code provided in the
  supplementary information section of the article does not reproduce some of the central findings
  reported in the article."* And: *"Upon reexamination of the work, the authors confirmed that the
  replication code does not fully reproduce the published results and were unable to provide revised
  code that does."* The paper had won the **Brattle Group Distinguished Paper Prize** before it was
  retracted.
- **GRADE: STATISTICAL → effectively STRUCTURAL for the desk.** The finding is not fabricated; it is
  *unreproducible from its own code by its own authors*. The theory (constrained institutions hedge
  less) may still be true — nobody has shown otherwise — but there is now **no evidence for it in the
  record**, so the desk must treat it as UNMEASURED (L1.28a), not as false and not as true.
- **DESK RELEVANCE: LOW-BUT-REAL, and it is a NEGATIVE result the desk gets free.** The desk has no
  bank-hedging axis, so nothing is contaminated. What transfers is the **prior on the class**: "net
  worth / balance-sheet capacity drives hedging demand" is exactly the shape of the desk's
  `carry → dealer-balance-sheet` intuition (BIS WP1087, card 23). **The single most-cited empirical
  support for constrained-intermediary hedging behaviour in a top-3 finance journal did not survive
  its own replication code.** Attach that as a confidence haircut on the intermediary-constraint
  family, not as a kill on card 23 (whose evidence is BIS's own, independent).

## 3.4 The other nine FRAUD/DATA-graded core-finance rows — screened, and only one more is desk-adjacent

Of the 10 FRAUD/DATA-graded rows in the 55-row core slice, **6 are one author cluster**
(Khalid Zaman et al., Economic Modelling, all retracted 2015-01-23, `Misconduct by Author` +
`Compromised Peer Review`) on Pakistani development-economics topics — **zero desk relevance**, and
the reason profile is a coordinated peer-review-ring bust with a misconduct finding on top. The
remainder:

| Paper | Journal | Reason | Desk relevance |
|---|---|---|---|
| *Common risk factors in the cross-section of corporate bond returns* (Bai, Bali, Wen) | **JFE** | `Error in Data; Error in Results and/or Conclusions` | **Corporate-bond factor models.** Desk has NO bond axis. See caveat below. |
| *The convergence of fictitious play in games with strategic complementarities* | Economics Letters | `Error in Methods; Error in Results and/or Conclusions` | none (game theory) |
| *Geopolitical oil price uncertainty transmission into core inflation* | Energy Economics | `Error in Data; Error in Results` (escalated from a Correction) | none |
| *Environmental legislative shaping or green competitive advantages?* | Energy Economics | `Error in Methods; Error in Results` | none |
| *Natural resources environmental quality and economic development* | Resources Policy | `Concerns/Issues about Data` | none |

### ⚠️→✅ THE JFE ROW: I flagged it as a probable false positive, CHASED IT, AND I WAS WRONG — it is a real retraction, and the DATABASE is what is wrong

**This is the run's self-correction and it is worth more than the row itself.**

RW gives `OriginalPaperDate` **and** `RetractionDate` as the *same day*, **2018-08-16**. I flagged
that as the "retract and replace of an online-first version" false-positive signature (§5.3) and
declined to bank it. **Chasing it inverted the conclusion:**

- The original is **Bai, Bali & Wen, *Common risk factors in the cross-section of corporate bond
  returns*, Journal of Financial Economics 131(3), 2019, 619–642.** Not 2018.
- The retraction notice is a **separate published article**: *"Retraction notice to 'Common risk
  factors in the cross-section of corporate bond returns' [Journal of Financial Economics 131 (3)
  (2019) 619–642]"*, **JFE 150(3), 2023**, DOI `10.1016/j.jfineco.2023.103721` — located `[PRIMARY]`
  on RePEc/EconPapers and on the OUCI index.
- **So the retraction is genuine and it is a full retraction, not a correction.** RW's reason codes
  `Error in Data; Error in Results and/or Conclusions` stand.

**BOTH of RW's date fields on this row are wrong by ~1 and ~5 years respectively.** That is a
different and more dangerous defect than the false-positive class I hypothesised: **the same-day
signature here is a DATA-QUALITY ERROR in the retraction database, not a publishing artifact.**

**Consequence for §5.3 and for any scripted screen: never compute anything on RW dates without
cross-checking the DOI.** A "retractions by year" chart built on this column is unreliable at the row
level. The DOIs and the reason codes are the trustworthy columns; the dates are not.

**Now bankable — GRADE: STATISTICAL (evidence withdrawn ⇒ reverts to UNMEASURED).**
CLAIMED MECHANISM: a four-factor model for the corporate-bond cross-section (downside risk, credit
risk, liquidity risk alongside the bond market factor) prices corporate bond returns — the "BBW
factors", a standard benchmark in that literature. DIED OF: `Error in Data; Error in Results and/or
Conclusions`. **DESK RELEVANCE: LOW — the desk has no corporate-bond axis and should not open one.**
It is banked because it is a *free documented negative* and because it is the second instance in this
corpus of the same pattern as §3.3: **a prize-adjacent, heavily-cited top-journal empirical factor
result that did not survive scrutiny of its own data.** Two of the three top-3/top-4 finance
retractions in the entire database are of exactly that shape.

**HONEST RESIDUAL:** the *verbatim* notice text was not read — ScienceDirect 403s from this box
(NK-005, re-confirmed today). The reason codes come from the RW controlled vocabulary, which is a
structured primary record, not a search summary. The bibliographic facts are `[PRIMARY]` via RePEc.

## 3.5 The honest bottom line on §3

**Mechanisms actually killed by this entire retraction corpus, for this desk: ONE**
(constrained-intermediary hedging, §3.3), **and the desk has no position in it.**
**Mechanisms NOT killed but merely de-citable: at least five** (§3.1–3.2).
**The wave is editorial. It kills nothing the desk trades and nothing the desk was about to test.**
That is a first-class result and it is stated without decoration.

---

# 4. CONTAMINATION MAP — the highest-value section, and it contains one near-miss the desk must know about

## 4.1 ★★★ `VPIN and the flash crash` IS IN THE RETRACTION DATABASE — and the desk MUST NOT act on that

**This is the finding of the run.**

The desk currently rests two live artifacts on Andersen & Bondarenko's critique of VPIN:
- `docs/research/deep_sweep/LIT_b_forgotten_literature.md` Finding 6, and its family verdict:
  *"Order flow / microstructure (Evans-Lyons, VPIN, PIN) — **EXHAUSTED.** ... the toxicity metric is
  a volatility artifact (Andersen-Bondarenko)"*
- `docs/research/improvement_inbox.md` **#66, the POSITIONING-CONTAMINATION LAW**, which names
  *"Andersen–Bondarenko 2011 vs VPIN"* as one of its four independent pillars.

**The Retraction Watch corpus contains a `Retraction` record for it:**

> Record — *VPIN and the flash crash*, Torben G Andersen; Oleg Bondarenko, **Journal of Financial
> Markets**, original 2012-10-30, **retraction 2013-04-01**.
> Reason: `Notice - Limited or No Information; Objections by Author(s); Objections by Third Party;`

A naive "retracted ⇒ discard" screen — exactly the screen §5 proposes building — **would have
destroyed a valid and load-bearing desk prior, and would have re-opened an EXHAUSTED family.**

**IT IS A FALSE POSITIVE, and the authors say so in their own words.** `[PRIMARY]` — Andersen &
Bondarenko, *Reflecting on the VPIN Dispute*, CREATES Research Paper 2013-42, full PDF downloaded
and text-extracted this run (`repec.econ.au.dk/repec/creates/rp/13/rp13_42.pdf`, HTTP 200):

> *"They know very well that our publication was delayed so that we could address also a more recent
> implementation strategy for VPIN. In fact, **we agreed to have the initially accepted version
> undergo a technical retraction to allow for addition of such material.** Moreover, with assistance
> from the journal editors, we obtained clarification on implementation details to ensure that we
> replicate the procedures of ELO (2011a, 2012a) as closely as possible. Thus, the published article,
> Andersen and Bondarenko (henceforth, AB) (2014), includes a substantial section dealing with the
> 'bulk volume' BV-VPIN metric introduced in ELO (2012a)."*

**Sequence, established:** accepted → online-first 2012 → **author-agreed TECHNICAL retraction 2013 so
the paper could be EXPANDED** → published as **Andersen & Bondarenko (2014), *VPIN and the flash
crash*, Journal of Financial Markets 17, 1–46** → ELO rejoinder (JFM 2014) → this reflection note.
**The critique stands, in the same journal, in expanded form. The desk's citation is CLEAN.**

**The three reason tokens should have been readable as the warning they are:** `Notice - Limited or No
Information` (RW could not find out why) + `Objections by Author(s)` + `Objections by Third Party`
(a *dispute*, not a finding). **No `Unreliable Results`, no data token.** The grader in §1.6 already
classes this INTEGRITY-ONLY — which is why the grader, not the flag, must be the decision rule.

**BONUS — the dispute note pays the desk a NEW method rail it did not have.** Andersen & Bondarenko
benchmark VPIN's alarm quality against the trivially-available quantity it is correlated with, and
report (verbatim table):

> Volatility percentile: **70 / 80 / 90 / 95 / 99** → False-positive rate: **10.8 / 3.0 / 1.2 / 0.0 / 0.0**
> *"When volatility rises above the 95% threshold of its empirical CDF, subsequent volatility is
> higher than the sample average 100% of the time. Thus, there is not a single false positive at the
> 95% level versus the 7% error rate for VPIN at the 99% level!"*

i.e. **plain, un-optimised realised volatility beats a 16,000-design-combination-optimised VPIN on
its own alarm metric.** Their diagnosis is verbatim the desk's own positioning-contamination law:
BV-VPIN *"impute[s] order imbalances through a monotone function of absolute price changes and then
use[s] the associated BV-VPIN measure to forecast volatility, effectively **letting absolute price
changes forecast absolute price changes**."* And: *"any variable correlated with volatility will,
inevitably, possess non-trivial forecast power for future volatility... This merely confirms that
volatility begets volatility."*

**Direct live application:** the desk's `lit_liquidation_csd_alarms` graveyard row (per-event
liquidation-cascade early warning from critical slowing down) is **the same object class** — an alarm
metric evaluated on hit-rate without a persistence benchmark. This is independent published support
for that kill, and a standing admission test: **an alarm statistic must beat the current realised
value of the thing it is alarming about, un-optimised, or it has measured persistence and called it
information.**

## 4.2 Systematic screen of the desk's own cited literature — result: CLEAN apart from §4.1

A title-level and author-level cross of the desk's research corpus (220 markdown documents under
`docs/research/**` plus `docs/graveyard.md`) against the 71,743-row retraction corpus returned **no
finance/economics contamination hit other than the Andersen–Bondarenko false positive**. Specifically
checked and **CLEAN** (present in neither the retraction nor EoC slice):

- Hou–Xue–Zhang *Replicating Anomalies* (RFS 2020) — clean
- Jensen–Kelly–Pedersen *Is There a Replication Crisis in Finance?* (JF 2023) — clean
- McLean–Pontiff (JF 2016) — clean
- Chen & Zimmermann *Open Source Cross-Sectional Asset Pricing* — clean
- Chordia–Goyal–Saretto *p-Hacking / Anomalies and False Rejections* — clean
- Fieberg–Günther–Poddig–Zaremba *Non-standard errors in the cryptocurrency world* (IRFA 2024) — clean
- Fieberg–Liedtke–Zaremba *Cryptocurrency anomalies and economic constraints* (IRFA 2024) — clean
- Li & Zhu *Taming crypto anomalies* (RIBAF 2026) — clean
- Brigida *TVL* (arXiv 2506.03287) — clean (preprint, not in scope of the DB anyway)
- BIS WP1087, NY Fed sr1073/sr1052 — working-paper series, **out of DB scope by construction** (see
  the honest limit in §6)

**Two of the desk's graveyard rows are sourced to IRFA — the same journal as five Lucey retractions.**
`lit_crypto_xsec_size_and_volume` (Fieberg–Liedtke–Zaremba, IRFA 2024) and the NSE rail
(Fieberg et al., IRFA 2024). **Neither paper is retracted, neither author appears anywhere in the
retraction corpus, and neither shares a co-author with the Lucey/Naeem clusters.** The venue-level
provenance discount in NK-004 therefore applies to them as a *venue* prior only, and **must not be
escalated to a paper-level doubt** — that would be exactly the over-harvesting the mandate warns
against. Recorded explicitly because "it was in IRFA" is precisely the kind of guilt-by-venue the
desk could talk itself into.

## 4.3 A live desk agenda item that touches a retracted title — and does NOT need to change

`do_not_repeat` contains `digital_gold_rotation` (REJECTED 2026-07-22 on EV grounds). The retracted
IRFA paper §3.1(c) is the canonical academic support for that family. **The kill is unaffected**: it
was made on the desk's own EV gate, not on that paper. Recorded so a future run does not "discover"
the retraction and think it has found a new reason for an old kill — that would double-count.

## 4.4 CLOSED CARRY-OVER — the "−0.31" digit in F4 is LOCATED, and run 2's record was CORRECT

Open since 2026-07-26 across four runs. Run 3 flagged it honestly: *"the '−0.31' in 'change in TVL
−0.31 to 0.41' does not appear in Table 9's alpha row (all four are positive). It is plausibly from
one of the Level-1 sub-tables (11–13), which were not checked."*

**Run 3's hypothesis was exactly right. It is Table 13.** `[PRIMARY]` — `arxiv.org/html/2506.03287v1`
re-opened this run (HTTP 200), full text parsed:

> **Table 13:** *"Results from cryptocurrency factor model regressions for the **Level 1 subset** of
> cryptocurrencies ... where i denotes the crypto portfolio formed on **Δ(TVL / Market Cap)**"*
> Row α: Quartile 1 **−0.09** (0.91) · Quartile 2 **0.21** (0.78) · Quartile 4 **−0.31** (0.45)
> three-factor spec: **−0.14** (0.87) · **0.24** (0.75) · **−0.30** (0.48)
> GRS Stat. **0.24** p (0.87) · GRS Stat. **0.26** p (0.86)

**Verdict: run 2's record `"change in TVL −0.31 to 0.41"` is VINDICATED** — the range spans the
Level-1 sub-tables as well as the main Table 9, and the −0.31 is the Level-1 ΔTVL Quartile-4 alpha
with p = 0.45. **The kill in `lit_defi_tvl_crosssection` is unchanged and if anything strengthened**:
every alpha in every panel including the Level-1 subset is insignificant, and every GRS F-test fails
to reject (0.86–0.87 here). **F4's last open digit is closed. Nothing in the desk record was wrong.**

---

# 5. ENGINE — research-integrity methods the desk should adopt

## 5.1 ★ Build the retraction screen as a GRADER, never as a flag

The §4.1 near-miss is the whole argument. A boolean `is_retracted` screen would have discarded a
valid critique and re-opened an exhausted family. The correct construction:

1. Join the desk's cited DOIs/titles against the RW CSV (§1.6).
2. **Grade every hit by reason code.** `INTEGRITY-ONLY` ⇒ *the citation's provenance is degraded, the
   mechanism is untouched* — flag for re-sourcing, never for kill. `FRAUD/DATA` ⇒ *the evidence is
   gone* — the claim reverts to **UNMEASURED (L1.28a)**, which is neither true nor false.
3. **Never let a retraction flag CREATE a kill.** A retraction removes evidence; it does not supply
   counter-evidence. A mechanism whose only support was retracted goes back to unproven, not to dead.
   (The desk's existing habit of writing "mechanism of death" rows makes this failure mode easy to
   commit.)
4. **Read `Reinstatement` (160 rows corpus-wide) and `Notes`.** RW records reversals, and its `Notes`
   column carries the human caveat (e.g. the Lucey rows' *"html page overwrite"* note).

## 5.2 ★ The BENCHMARK-FREE ALARM defect — a standing admission test the desk can run today

From §4.1's bonus. Any metric proposed as an *alarm* (toxicity, cascade risk, stress, "early
warning") must be scored against the **un-optimised current realised value of the quantity it
alarms about**. VPIN, optimised over 16,000 design combinations, posted a 7% false-positive rate at
its 99th percentile; raw realised volatility at its 95th percentile posted **0.0%**. The desk already
owns two instances of this class (`lit_liquidation_csd_alarms`, and the positioning-contamination law
#66). **Proposed rule: no alarm-shaped candidate is admitted to a screen without a persistence
benchmark leg pre-registered alongside it.** This is cheap, it is a pure admission test, and it would
have pre-killed at least one carded family.

## 5.3 Named false-positive classes in the RW database (so a scripted screen does not fire on them)

Measured this run, all four with concrete instances:
- **Technical retraction during dispute** — §4.1. Signature: `Objections by Author(s)` +
  `Objections by Third Party` + `Notice - Limited or No Information`, no data token, and **a later
  publication of the same title in the same journal.**
- **Same-day original/retraction date** — §3.4's JFE row. Signature of a "retract and replace" of an
  online-first version. **Always resolve before banking.**
- **Bulk administrative purges** — the 1,787 IEEE conference rows (§2.1). Signature:
  `Notice - Limited or No Information` + `Breach of Policy by Author` + `Removed`, one publisher, one
  narrow date band, hundreds of rows.
- **Name collisions on the author key** — the 13th "Lucey" is an unrelated PNAS microbiologist
  (§2.4). **Never key on surname alone**; require journal-class or subject agreement.

## 5.4 The venue de-rating in NK-004 now has a defensible SHAPE

NK-004 currently applies a ~2× citation de-rating to FRL/IRFA/IREF crypto papers. This run supplies
the missing structure: **the de-rating is on CITATION COUNT and VENUE SIGNAL, not on the empirics.**
The corpus shows *zero* data-integrity findings in the whole 12-paper Lucey cluster. So the correct
operational form is: *in this corpus, treat citation count as uninformative about replicability and
read the identification strategy directly* — which is already NK-004's sentence, now **evidenced by
reason code rather than by inference from a blog post.** Note this also converges with the desk's own
McLean–Pontiff interior finding: *"Once we control for publication date, [cumulative academic
citations] has little incremental value in explaining decay"* — **two independent routes to "citation
count is not a usable quality signal."**

## 5.5 Cheap standing job (spec'd, NOT built — litminer freeze bars `scripts/`)

Route A is a git repo. `git clone --depth 50` it, or diff yesterday's CSV against today's, and the
**arrivals** are free. A weekly job costing one 65 MB fetch would tell the desk, unprompted, when a
paper it cites gets retracted — with the grade attached. Estimated implementation: ~60 lines given
§1.6. Owner would be the brain; this seat records the spec and does not write the file.

## 5.6 ★ The CITATION-CHAIN contamination check is real, enforced, and rising — and it has NOT reached crypto

The mandate asked whether papers that cite a retracted result are themselves contaminated. **The
database answers this directly: `Cites Retracted Work` is a live reason code in the RW controlled
vocabulary — 221 rows corpus-wide, and the trend is sharply up:**

`2015: 8 · 2016: 8 · 2017: 10 · 2018: 21 · 2019: 9 · 2020: 36 · 2021: 20 · 2022: 10 · 2023: 6 ·
2024: 8 · 2025: 37 · 2026 YTD: 17`

So publishers now DO retract downstream papers purely for resting on retracted work. **But the
desk-relevant null is the important half:** of those 221, only **14** are finance/economics, and
**not one touches asset pricing, market microstructure, or crypto.** They are development economics
(digital financial inclusion in China, PLoS One), fuzzy multi-attribute decision-making, and
medicine.

**Therefore: the ~5,104 combined citations to the Lucey-cluster retractions have produced ZERO
documented downstream retractions.** The contamination chain is a documented publishing practice
that has **not** propagated into the crypto finance literature. **The desk should not expect a
second wave, and should not go looking for one.** Stated as a measured null rather than an
impression: the query was run, the count is 14, the crypto count is 0.

## 5.7 Screen-design defect found in my own screen (recorded because it nearly cost the run its best finding)

My title-level contamination screen (§4.2) required ≥4 tokens of length >3 after stopword removal.
**"VPIN and the flash crash" yields exactly three** (`vpin`, `flash`, `crash`) and was silently
dropped below the threshold. **The single most important contamination hit of the run was invisible
to the title screen and was caught only by the author-key screen.** A production version must run
**both keys** and must not impose a minimum-token filter that quietly excludes short titles —
short titles are disproportionately common in *letters* journals, which is exactly the corpus at
issue here.

---

# 6. DEPTH LINE — per lead, and what depth surfaced that surface did not

| Lead | Depth reached | What DEPTH surfaced that SURFACE did not |
|---|---|---|
| **Crossref/RW corpus route** | *search → Crossref Labs page → GitLab repo → **CSV downloaded (65 MB) and fully parsed** → README field spec → grader built and run* — **EXHAUSTED** | Surface said "the data is public". Depth produced: two working URLs with byte counts, the **`Business - Finance` subject does not exist** trap, the `+`-prefix and trailing-column parsing defects, and the `Reinstatement` nature nobody mentions. |
| **★ Andersen–Bondarenko VPIN** | *RW flag → search → **CREATES PDF fetched + stdlib-extracted (full text)** → author's own account of the withdrawal → publication sequence confirmed* — **EXHAUSTED, and it INVERTED the flag** | Surface: "retracted, therefore discard." Depth: the authors **agreed to a technical retraction so they could EXPAND the paper**, which then published in the same journal in 2014. A one-level dig would have destroyed a valid desk prior. **Plus** an unlooked-for method rail (the un-optimised-volatility benchmark table) that surface never hints at. |
| **Lucey cluster** | *run-6 hand-found 2 → **mechanised to all 12 with verbatim reason codes + DOIs** → author-key collision check* — **EXHAUSTED** | Surface: "12 retractions, editorial." Depth: the reason string is **byte-identical across all 12 with zero data tokens**, which is what converts "probably editorial" into "provably editorial"; plus **2 crypto empirics the desk did not have**; plus a 13th "Lucey" that is an unrelated PNAS microbiologist. |
| **Naeem/Yarovaya FRL 2024** | *desk had it `[SUMMARY-ONLY]` → **reason codes recovered `[PRIMARY]` from RW*** — **CLOSED** | The reason set is authorship+peer-review+**referencing** — a *different* editorial failure mode (cartel) from the Lucey rogue-editor mode. Two signatures, same journal. |
| **JF `Risk Management in Financial Institutions`** | *RW row → search → **retraction notice text verbatim** → original abstract via RePEc → prize history* — **EXHAUSTED for the desk's purpose** | Surface: "a JF paper was retracted." Depth: it was retracted because **a replication study found the authors' own supplied code did not reproduce their central findings, and the authors could not fix it.** That is the gold-standard failed-replication event and it is qualitatively different from every other row. |
| **JFE `Common risk factors… corporate bond returns`** | *RW row → **I flagged it a false positive** → chased → **inverted my own call**; notice located as a separate 2023 JFE article* — **notice text NOT read (ScienceDirect 403)** | Depth showed the retraction is real **and that the DATABASE's date fields are wrong by years** — a data-quality defect more dangerous than the false-positive class I had hypothesised. My own §5.3 heuristic was refuted by the second case I applied it to. |
| **Brigida "−0.31" (4-run carry-over)** | *arXiv HTML re-opened, **full text parsed, table caption matched*** — **CLOSED** | Located in **Table 13** (Level-1 subset, Δ(TVL/MarketCap), Q4 α = −0.31, p = 0.45). Run 2's record was **correct**; run 3's guess about which table was **correct**. Depth vindicated the desk record rather than correcting it — which is also a result. |
| **Citation-chain (`Cites Retracted Work`)** | *reason-code discovered in the vocabulary → **whole-corpus extraction + finance slice + year trend*** — **EXHAUSTED** | Surface would have said "downstream contamination is a worry". Depth measured it: 221 rows, rising, **0 in crypto/asset-pricing.** A measured null instead of a vibe. |
| **PubPeer** | *inherited blocker **RE-TESTED** per GAP #70's rule* — **STILL BLOCKED, not circumvented** | Refinement, not just a repeat: `pubpeer.com/` root returns **HTTP 200**, but `/search?q=…` returns **403**. The gate is on the SEARCH endpoint. §38 replacement named below. |
| Heliyon / Hindawi crypto slice | *counted, journal-profiled, reason-profiled* — **EXHAUSTED as a lead, DECLINED** | The scary "226 crypto retractions" number is ~95% a computer-science paper-mill event about the word "blockchain". Naming and declining it. |

**§38 — sources excluded, with the replacement hunt run in the same run:**
- **PubPeer search (403, bot-gate).** NOT circumvented — §13 is a boundary, not a hurdle, and
  GAP_REGISTER #80's ruling is still pending. **Replacement route FOUND AND EXECUTED: the RW/Crossref
  corpus is the licensed substitute for the *outcome* layer** (formal notices, reason codes, DOIs) —
  which is what this run needed and got. **Residual gap, graded honestly:** PubPeer's *allegation*
  layer (comments on papers that were never formally acted on) remains unreachable from this box.
  That is `blocked-from-here`, **NOT** `does not exist`.
- **ScienceDirect (403, NK-005 re-confirmed today).** Blocks the verbatim JFE/FRL notice texts.
  **Replacement executed:** RePEc/EconPapers + OUCI carried the bibliographic facts, and the RW
  controlled vocabulary carried the structured reason. **Residual:** the two verbatim notice
  paragraphs. Cheap to close from a box with different egress.
- **Wiley (JF notice).** Reached in substance via the Replication Network's verbatim quotation of the
  notice; publisher page not opened.

**Is this breadth-theater?** No, and the specific check: **five leads were driven to primary text or
full-corpus extraction, and three of them overturned something** — the VPIN flag (inverted), my own
JFE false-positive call (inverted), and the four-run "−0.31" carry-over (closed and vindicated). One
of those was my own error, caught in-run.

---

# 7. NEXT UN-EXHAUSTED GROUND — named precisely

1. **Land the retraction screen as a scheduled job.** Spec is complete in §1.6 + §5.1 + §5.5; ~60
   lines; the only open design choice is where the desk's cited-DOI list lives. **Must be built as a
   GRADER, not a flag** (§4.1 is the reason) and must run **both** title and author keys (§5.7).
   Owner: brain. This seat is freeze-barred from `scripts/`.
2. **Two verbatim notice texts**, one fetch each from a box with non-403 egress to ScienceDirect:
   JFE `10.1016/j.jfineco.2023.103721` and FRL `10.1016/j.frl.2026.110147`. Low value, cheap, and
   they close the run's only two `[SUMMARY-ONLY]`-adjacent residuals.
3. **The replication-comment layer in top finance journals — GENUINELY UNMINED and the richest thing
   left on this ground.** §3.3 shows the mechanism: a *published replication study* forced a JF
   retraction. That replication paper itself was never opened this run. The systematic version is:
   **Critical Finance Review's replication issues**, and JF/JFE/RFS `Comment on…` / `…: A Replication`
   articles. These are papers whose ENTIRE CONTENT is a documented negative — the single highest
   free-graveyard-yield genre the desk has identified and it has never been walked. **Name it as
   next-run item 1 for this ground.**
4. **RFS/JF code-sharing-policy era (post 2020-07-01) as a natural experiment.** The RFS code-sharing
   policy began 2020-07-01. Papers published under it are checkable in a way earlier ones are not.
   Zero-cost to watch; a dated revisit rather than a dig.
5. **Guo et al. (2024) replication-rate paper** — surfaced this run, not opened. The desk owns HXZ /
   JKP / Chen–Zimmermann / McLean–Pontiff / Harvey–Liu–Zhu and **must not re-bring them**; Guo et al.
   is the one name in the meta-literature that is NOT already owned. One fetch.
6. **DO NOT RE-RUN:** the RW corpus slice itself for at least a quarter. It is 65 MB, it moved by
   ~0.1% in a day, and this run has characterised it. The correct cadence is a **diff**, not a
   re-mine.

---

# RUN CLOSE — what this ground actually bought

**NET NEW TRADEABLE AXES: ZERO.** Stated first and deliberately, as this ground's convention.

1. **A mechanised, licensed, reproducible route** to a corpus the desk previously hand-searched —
   with the `Business - Finance` false-exhaustion trap, the parsing defects, and the four
   false-positive classes all documented before anyone writes the script.
2. **The editorial-vs-fraud split, measured:** 82% INTEGRITY-ONLY in the desk's own journals; ~1%
   pure-fraud in the wider economics slice. **The wave kills almost nothing.** Two crypto empirics
   the desk did not have were added to the provenance shelf, both INTEGRITY-ONLY, both already dead
   on the desk's own independent evidence.
3. **ONE genuine mechanism kill** (§3.3, constrained-intermediary hedging) and **one bankable
   low-relevance kill** (§3.4, corporate-bond factors) — both **failed-replication / data-error**
   events in top-4 journals, and the desk has no position in either.
4. **A near-miss that would have cost the desk a valid prior** (§4.1) — the strongest argument
   available for building the screen as a grader, and it came with a free method rail (the
   benchmark-free-alarm admission test) that maps onto a live graveyard row.
5. **A four-run carry-over closed** (§4.4, the "−0.31" digit) with the desk record **vindicated**.
6. **Two self-corrections in-run** — my JFE false-positive call (inverted on evidence) and my own
   screen's minimum-token filter (which hid the run's best finding).

**The honest headline stands: counting retractions was never the deliverable, and the count is
mostly noise. The deliverable is that the crypto-finance retraction wave is an EDITORIAL event, it
does not falsify the mechanisms it touches, and the desk must not harvest it as if it did.**
