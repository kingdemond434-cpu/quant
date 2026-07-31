# NEGATIVE KNOWLEDGE REGISTRY — standing, REVERSIBLE (Charter §18)
_Low-yield search areas documented so budget flows elsewhere — NEVER permanently excluded.
Quarterly Temporal Rediscovery re-evaluates every record; trigger evidence (new repos, APIs,
maintainers, conferences, acquisitions, growth, citations, forks, mirrors, community activity)
re-opens a record immediately. Past absence of discoveries is evidence about the past only._

## Record schema
```
### NK-<nnn> <area>                     [priority: reduced|restored]   review-due: <date>
explored: <sessions/dates + coverage achieved>
reason-low-value: <no sources | poor quality | duplication | licensing | abandoned | ...>
adequately-explored-confidence: <low|med|high + why>
reopen-conditions: <specific evidence that justifies immediate re-exploration>
history: <date: action/finding>
```

## RECORDS — seeded 2026-07-19 from the graveyard + coverage maps (search-AREA level only;
## individual rejected strategies stay in docs/graveyard.md — this registry is about WHERE
## to dig, not WHAT was tested)

### NK-001 Kraken/OKX L1 exchange-reserve wallets            [priority: reduced]   review-due: 2026-10-19
explored: 2026-07-04 stablecoin-flow build; wallets checked directly
reason-low-value: labeled L1 wallets held <$3k — no reserve signal to reconstruct there
adequately-explored-confidence: med (direct balance check, but label sets evolve)
reopen-conditions: new/updated public wallet-label datasets for either venue; venue publishes
  proof-of-reserves with address lists
history: 2026-07-04 checked empty, dropped from collector

### NK-002 Binance dated-quarterly calendar-basis breadth    [priority: reduced]   review-due: 2026-10-19
explored: 2026-06-26 free-data layer build
reason-low-value: only BTC+ETH dated futures exist on Binance — breadth of 2 cannot carry a
  cross-sectional sleeve
adequately-explored-confidence: high (venue listing is exhaustive by definition)
reopen-conditions: venue lists dated futures beyond BTC/ETH; another free venue's dated futures
  become collectible with history
history: 2026-06-26 mapped, parked as forward-archive only

### NK-003 Hyperliquid historical funding via API            [priority: reduced]   review-due: 2026-10-19
explored: 2026-06-26 HL collector build
reason-low-value: API exposes NO funding history — forward-accrual only (clock started 06-26)
adequately-explored-confidence: high (API surface enumerated)
reopen-conditions: HL adds history endpoints; a community archive of HL funding with verifiable
  provenance appears (verify-don't-trust before adoption)
history: 2026-06-26 forward collector live instead

### NK-004 Short-format crypto-finance journals (FRL / IRFA / IREF) as a TRUST filter  [priority: reduced]   review-due: 2026-10-26
explored: 2026-07-26 literature deep-miner run 3 (retraction mining). Primary source read in full
  including its comment thread: https://retractionwatch.com/2026/01/08/finance-professor-brian-lucey-ireland-elsevier-journals-retractions/
reason-low-value: NOT low-value as CONTENT — these venues carry a large share of the crypto empirical
  literature and two of this desk's own findings (F5 non-standard-errors, F10 crypto anomalies) are
  IRFA papers worth having. What is de-rated is the venue/citation-count SIGNAL: twelve papers were
  retracted across International Review of Financial Analysis, International Review of Economics &
  Finance and Finance Research Letters for an editor overseeing review of his own co-authored
  manuscripts, including a crypto paper with 707 WoS citations. The editor's own defence is that this
  is "pretty common" in finance. A preprint separately alleged the associated Elsevier "Finance
  Journals Ecosystem" might facilitate citation stacking.
adequately-explored-confidence: HIGH (upgraded 2026-07-31, run 4 — the carry-over layer was mined).
  CITATION-STACKING IS NOW QUANTIFIED, NOT ALLEGED: a peer-reviewed 2025 econometric/graph-theory
  study measured **Ecosystem citations-per-article +103% (2021-2025 vs 2016-2020)** and concluded
  the ecosystem journals benefited from its creation; Elsevier DISMANTLED the Finance Journals
  Ecosystem (operating since 2020-11-04) in late 2025, retracting 12 papers carrying **5,104
  combined citations**. AUTHOR-LEVEL nodes now named (sharper than the venue filter): Lucey (55
  PubPeer flags; 56 papers in 2025 — one per 6.5 days), Vigne (21 flags; ≥33 Lucey co-pubs; removed
  as EiC of two journals), Goodell (68 papers in FRL alone, 61 in 2024). Documented co-authorship
  trading: an SSRN three-author draft scrubbed and republished with a fourth author added under an
  "equal contribution" statement, same text/figures. Lucey's own defence produced a list of **240
  instances of finance editors publishing in their own journals** — the defence generalises the
  defect to the field. Source: chrisbrunet.com/p/elsevier-shuts-down-its-finance-journal (secondary,
  read in full 2026-07-31, embedding the PubPeer evidence + the peer-reviewed study). PubPeer DIRECT
  = HTTP 403 from this box (bot-gate; NOT circumvented per the pending #80 ruling — logged).
  OPERATIONAL RULE SHARPENED: in FRL/IRFA/IREF crypto papers, (a) citation count is a CORRUPTED
  quality signal (may measure cartel membership; inflation scale ~2×), (b) any paper with
  Lucey/Vigne/Goodell in the author list is SINGLE-SOURCE regardless of venue or citations, and
  (c) the +103% number gives the litminer a concrete de-rating factor when weighing "highly cited"
  claims from this corpus.
reopen-conditions: this record is about a SIGNAL, not a source ban — keep reading these venues.
  Reopen/upgrade if: Elsevier publishes an outcome of the wider investigation (commenters asked for
  all ~240 articles to be reviewed); the PubPeer citation-stacking thread is read; or an independent
  bibliometric audit of the ecosystem appears.
history: 2026-07-26 recorded. Operational prior adopted (improvement_inbox #64): never let venue or
  citation count substitute for reading the identification strategy; treat FRL/IRFA/IREF crypto
  results as single-source until independently reproduced. NOTE the sharp edge — the retractions are
  for PROCESS, not fabrication; the claim is that the filter the desk was relying on did not run,
  not that the findings are false.

### NK-005 SSRN + ScienceDirect + Wiley direct fetch from this box  [priority: reduced]   review-due: 2026-10-26
explored: 2026-07-26 literature deep-miner run 3, plus run 2. Repeated attempts across several papers.
  SCOPE EXTENDED 2026-07-31 (run 4): SSRN `Delivery.cfm` direct-PDF URLs 403 as well — the block
  covers SSRN's own free-download mechanism, not just abstract pages. The OP-026 ladder's RePEc step
  RESOLVED the stranded F11 (published-version verbatim abstract via ideas.repec.org) — the ladder
  works; the 403 remains a routing problem, not a wall.
  TWO NEW SUBSTITUTE ROUTES VALIDATED 2026-07-31 (official-sector sweep — add to the OP-026 ladder):
  (a) NY Fed `newyorkfed.org/medialibrary/media/research/staff_reports/srNNNN.pdf` serves the PDF
  when the staff_reports HTML page 403s (validated on sr1052, read in full); (b) Boston Fed hosts
  mirrors of NY Fed staff-report content (`bostonfed.org/-/media/Documents/Workingpapers/...` —
  validated on the sr1073 stablecoin-runs paper after its primary route 403'd). Fed research 403s
  are ROUTING problems; the medialibrary/regional-mirror ladder resolves them legitimately.
reason-low-value: ACCESS, not content. Consistent **HTTP 403** from this VPS on
  papers.ssrn.com/sol3/papers.cfm, www.sciencedirect.com/science/article/*, and
  onlinelibrary.wiley.com/doi/full/*. This is the single largest cause of `[SUMMARY-ONLY]` grades in
  the desk's literature record, and SUMMARY-ONLY claims are barred from the graveyard — so this
  access gap directly costs the desk verified negative knowledge. One finding (F11, Li & Zhu crypto
  SIZE) is stranded provisional purely because of it.
adequately-explored-confidence: high that the direct fetch fails; LOW that the content is
  unreachable — the working routes are documented below and were NOT systematically exhausted.
reopen-conditions: n/a — this is a routing problem with known workarounds, not a dead area.
  WORKING SUBSTITUTE ROUTES, validated this run and to be tried IN THIS ORDER before grading a paper
  SUMMARY-ONLY: (1) arXiv HTML — arxiv.org/html/<id> and ar5iv.labs.arxiv.org/html/<id> render full
  text where the PDF does not; (2) NBER working-paper pages (author-written abstracts, fetchable);
  (3) RePEc/IDEAS records (carry VERBATIM abstracts — ideas.repec.org); (4) institutional open-access
  repositories (research-api.cbs.dk, open.icm.edu.pl, university self-archives, hec.ca) which host
  publisher-version PDFs legitimately; (5) **as of 2026-07-26, PDFs are directly readable** — see
  improvement_inbox #59, the "no PDF tooling" blocker was false and a stdlib extractor works.
history: 2026-07-26 recorded with substitute routes. LEGITIMACY NOTE (charter §13): the response to a
  paywall is an OPEN mirror, an author self-archive, or doing without — never circumvention. Every
  route listed above is publisher-sanctioned open access or an author's own posting.
