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

## CONVERTED FROM MINING — 2026-08-05 Bilibili deep sweep

### DH-006 A liquidity-capped micro-cap size premium survives regime-split live testing [status: open]
rationale: surfaced by the dedicated Bilibili sweep (score 7.0, query `统计套利 策略`) —
  "分行情实测微盘市值策略：牛市年化 45% 震荡市 16%，流动性决定最终收益上限"
  (regime-split live test of a micro-cap size strategy: 45%/yr bull, 16% chop, LIQUIDITY
  determines the final return ceiling). Converted rather than queued because it is the one row in
  this sweep carrying all three things a hypothesis needs: a NAMED mechanism (cross-sectional size
  premium), STATED economics split by regime, and an explicitly named CAPACITY CONSTRAINT.
mechanism-prior: `cross_sectional_risk_premium` (census), with a second leg in
  `liquidity_provision_immediacy`. The forced participant is the marginal holder of an illiquid
  small name who must exit into a thin book — which is also precisely why the edge is capped, so
  the mechanism and its capacity limit are the SAME fact rather than two findings.
expected-info-value: med-high — the capacity claim is directly testable against this desk's own
  capacity-parity machinery (L1.18/L1.18a), and a size premium whose ceiling is set by liquidity
  is the shape most likely to survive a backtest and die at the desk's actual size. That makes it
  worth testing for the REFUTATION as much as the edge.
supporting-evidence: NONE BEYOND A TITLE, and this is stated rather than glossed. The desk cannot
  read Bilibili video content (measured: 0 of 14 quant videos expose a subtitle track to an
  unauthenticated request), so the entire evidential basis is the 39 characters above. The 45%/16%
  figures are the uploader's UNVERIFIED claim, carry no sample window, no cost model, no
  multiplicity charge and no out-of-sample statement, and must never be quoted as measurements.
search-plan: (1) restate the mechanism from public data alone, ignoring the video's numbers;
  (2) build the cross-section on the desk's own D1 crypto lake, ranked by circulating market cap;
  (3) pre-register the regime split BEFORE looking — a split chosen after seeing returns is a free
  parameter, and "bull vs chop" is exactly the split a fitted story picks;
  (4) charge the capacity test FIRST via capacity_status, because if the edge dies at the desk's
  size the rest is unfalsifiable entertainment.
confidence: 0.25 — the mechanism is real and well documented in equities; that it survives NET OF
  COST at crypto micro-cap liquidity is the open question, and the source's own headline concedes
  the ceiling.
outcome: —


### DH-007 The put-call parity residual is computed every collection and thrown away [status: open]
rationale: surfaced by the dedicated Bilibili sweep 2026-08-06, three MECHANISM-naming rows at the
  3.0 threshold — `11.2 期权平价公式套利策略` (put-call parity arbitrage), `量化实战策略：BTC期权统计套利｜
  同一个BTC，为什么有两套概率？` (BTC options statistical arbitrage: "the same BTC, why two sets of
  probabilities?"), and `盘点中国市场所有套利交易策略`. Converted rather than queued because chasing
  the prompt into the desk's own code found something the video did not say and could not have.
mechanism-prior: `relative_value_convergence` (census), with a second leg in
  `liquidity_provision_immediacy`. WHO PAYS: a participant who must transact one leg — an option
  buyer with a view, or a market maker forced to warehouse inventory — when the synthetic built
  from the other legs is cheaper. Parity is an arbitrage IDENTITY, so a persistent residual is not
  a forecast, it is a rent someone is paying to trade in the wrong instrument.
THE FINDING, which is a DATA-PATH defect rather than an untested idea:
  `scripts/collect_deribit_vol_markets.py:261` — "the forward comes from put-call parity at" the
  ladder — recovers the forward from the call/put legs and then writes ONLY the aggregate
  (`atm_iv`, `forward`, `n_strikes`, `dte_days`). Verified against the artifact: 400 sampled rows
  of data/deribit_vol_markets.jsonl carry NO per-strike quotes. So the desk computes the parity
  relationship on every collection, uses it to derive one number, and DISCARDS the residual — and
  the residual is exactly the signal. The mechanism is untestable today not because the data is
  unavailable but because the collector consumes it.
expected-info-value: high, and cheap. The fix is a COLLECTOR change (retain the per-strike legs, or
  at minimum the parity residual per strike and expiry), not a new data source, no vendor and no
  paywall. Deribit's chain is already fetched on the existing cadence; the desk is paying the
  fetch cost and throwing away the byproduct (L1.50: an unexploited asset is a defect — here the
  asset is generated in-house and deleted).
supporting-evidence: the VIDEO IS THE PROMPT, NOT THE EVIDENCE, and unlike DH-006 that distinction
  matters here. The desk cannot read Bilibili video content, so the titles above are worth exactly
  the mechanism NAME they carry. The evidential basis is the desk's OWN collector source line and
  its OWN artifact schema, both quoted above, plus a textbook identity that needs no source at all.
  No number from any video is used, and none should be.
search-plan: (1) amend the collector to persist the parity residual per (underlying, expiry,
  strike) with the same one-clock stamping the VRP screen already documents — this is the only
  build step and it is small; (2) accrue forward: the residual is point-in-time and cannot be
  backfilled from the aggregate now on disk, so the series starts the day the collector changes;
  (3) pre-register the test BEFORE any data exists — deviation must be net of the fee/spread it
  would take to close, or the whole residual is a measurement of the bid-ask; (4) charge it as one
  cell in the existing multiplicity family, never as a fresh campaign.
BLOCKER, stated plainly: nothing can be screened today. The historical residual is unrecoverable —
  it was never written — so this hypothesis owes forward accrual before it owes a screen, exactly
  like the circulating-supply denominator. That is a fact about the collector's history, not a
  verdict about the mechanism.
confidence: 0.35 — parity residuals on a liquid venue are usually small and usually eaten by
  costs, which is why the fee-net construction is step (3) and not an afterthought. What raises it
  above DH-006 is that the economics are an identity rather than a premium story, and the desk
  already pays for the data.
outcome: —
