# DISCOVERY HYPOTHESIS ENGINE — permanent learning record (Charter §22)
_Explicit hypotheses about WHERE valuable information exists but has not yet been observed.
Failed hypotheses are as permanent as successful ones — the search process itself is a
falsifiable, self-improving research programme. Every newly validated + adopted dataset
immediately spawns hypothesis-generation entries here (no new data axis sits idle)._

## Record schema
```
### DH-<nnn> <hypothesis>                    [status: open|validated|falsified]
rationale: <why this location/class should hold value>
expected-info-value: <low|med|high + what it would unlock (include option value, Charter §20)>
supporting-evidence: <emergence indicators, analogies, weak signals (link WS-nnn)>
search-plan: <operators from the library (OP-nnn), regions, budget>
confidence: <0-1>
outcome: <what was found / not found + date; feeds negative_knowledge.md on repeated misses>
```

## OPEN — seeded 2026-07-19

### DH-001 Regional-exchange native archives hold unindexed L2/funding history   [status: open]
rationale: Free-First found Binance/Bybit archives; regional venues (Upbit, Bithumb, bitFlyer,
  Gate, OKX regional trees) likely publish equivalents documented only in local languages
expected-info-value: high — cross-venue funding/basis breadth is the desk's highest-prior
  breadth lever; option value: opens each region's whole venue ecosystem
supporting-evidence: pattern-match from Binance/Bybit (vendors repackage free originals)
search-plan: OP-006 + OP-002 per region; KR/JP first (largest regulated retail crypto markets)
confidence: 0.6
outcome: —

### DH-002 CN quant framework Issues hold pre-debunked crypto edges              [status: open]
rationale: Chinese quant frameworks (vn.py class, Gitee ecosystems) have years of Issues/
  Discussions where strategies were proposed and shot down — free graveyard entries (§9)
expected-info-value: med — saves gauntlet slots via pre-emptive falsification
supporting-evidence: EN equivalent (Freqtrade/Hummingbot Issues) already yields debunkings
search-plan: OP-001 Gitee chain + OP-003 comment mining, CN expansion budget
confidence: 0.55
outcome: —

## OPEN — seeded 2026-08-01 (external methodology intake, principal-supplied video transcript)

_Provenance: a public YouTube methodology walkthrough supplied by the principal. Treated as a
SUGGESTION source under the same asymmetry as every outside finding — it may propose a mechanism,
it may never authorise one. None of these has desk evidence; each owes the ordinary gauntlet._

### DH-003 Trend-gated cross-asset rotation pays where single-asset trend does not  [status: open]
rationale: the transcript's only survivor after its own stress tests was a regime switch, not a
  timing rule — hold risk asset above its 200D average, hold the defensive asset below it. The
  mechanism is not "trend predicts": it is that the two legs have opposite regime exposure, so the
  pair harvests the regime rather than the direction. Crypto analogue: BTC/ETH above 200D vs
  stables-or-carry below, which the desk can express and has never tested as a PAIR
expected-info-value: med — the desk's TREND-AND-STRUCTURE family is worked, but as single-leg
  timing; the rotation form is unhunted and is a different mechanism
supporting-evidence: transcript reports ~5 trades/year surviving a 2000-2009 stress window; the
  desk's own coverage map shows no cross-asset rotation candidate in the graveyard
search-plan: 2-leg construction on the existing D1 tape; must clear the SAME gauntlet, no
  exemption for provenance
confidence: 0.35
outcome: —

### DH-004 Portfolio-level combination is where the desk's edge actually is        [status: open]
rationale: the transcript's strongest structural claim, and it is arithmetic rather than opinion —
  5 uncorrelated legs at true Sharpe 1.0 each combine to 2.24. The desk's gauntlet scores every
  candidate ALONE against a bar only the assembled portfolio could clear, so it would reject all
  five and never form the book worth 2.24. libs/discovery/objective.py::discovery_score already
  encodes the fix (diversification_contribution, average_correlation, failure_dependency_score)
  and has ZERO production callers; run_discovery ranks by raw Sharpe descending
expected-info-value: high — this is a scoring defect, not a data gap, so it is cheap to test and
  changes what the desk promotes rather than what it looks at
supporting-evidence: measured 2026-08-01 — P(a true-SR-1.0 leg clears) = 0.01% at the campaign
  shape, so P(all five clear) ~ 9e-21; grep confirms discovery_score is orphaned
search-plan: wire discovery_score into the ranking behind a measurement, exactly as the DSR change
  was; must NOT relax any gate — this changes ORDERING, not admission
confidence: 0.7
outcome: —

### DH-005 Parameter-plateau robustness is owned, unproduced, and nearly free      [status: open]
rationale: trust an optimised setting only when its NEIGHBOURS also work. Unlike a multiplicity
  deflator this costs almost no power — it rejects knife-edge fits specifically, rather than
  penalising every candidate for the existence of the others. discovery_score takes
  parameter_plateau_score as a required argument and NOTHING in the repo computes it
expected-info-value: med — closes an orphaned input on an orphaned objective; the two defects
  compound, since the score cannot be wired until its inputs exist
supporting-evidence: transcript uses the plateau test as one of three post-hoc filters and reports
  it removing survivors that the primary test passed
search-plan: sweep each surviving candidate's parameters +/- one step, score the neighbourhood's
  dispersion; produce the 0-100 figure discovery_score already expects
confidence: 0.6
outcome: —
