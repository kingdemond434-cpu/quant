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
adequately-explored-confidence: med — the retraction event is documented and primary-read, but the
  PubPeer thread on citation stacking was NOT opened (carry-over) and no systematic audit of the
  affected corpus was attempted.
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
