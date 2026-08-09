# DEEP COLD AUDIT — ALPHA-DISCOVERY — 2026-07-31

STATUS: COMPLETE

_Auditor: weekly deep cold audit (core doctrine v2). Scope: hypothesis diversity, unexplored
market behaviors, crowded themes, neglected regimes, cross-asset transfer, temporal-resolution
gaps, feature-interaction and higher-order opportunities, regime-conditioned hypotheses,
causal-vs-correlational assumptions, hypothesis redundancy, negative-result reuse,
abandoned-idea reassessment, falsification quality, ignored markets/public-info, untestable
signals. Read-only. Every claim carries its proving command. Findings appended incrementally
as verified — if this run is cut off, what is here is the deliverable._

_Context note: the 2026-07-30 alpha-discovery report is a 54-line empty skeleton (verified:
`wc -l` = 54, all four outputs "(placeholder)"), and the 20260730 SYNTHESIS records
alpha-discovery as "NO AUDIT — 2nd loss in 3 sweeps". This report is the first completed
deep audit of the desk's alpha-discovery subsystem. It therefore establishes the baseline._

## SCORES (subsystem: alpha-discovery)

- current_capability_pct: **35%** — falsification discipline is excellent for the desk's size
  (S1–S5, S8); but generation is at steady-state zero (F13), the horizon/intraday/cross-asset
  dimensions of the search space are closed or unexplored (F5, F15, F10), the reassessment loop
  is unwired (F2, F6), diversity has never been measured (F11), and the allocation thesis has no
  surviving positive exemplar (F1).
- practical_ceiling_estimate: **~85%** — every closing item is instrument/wiring work already
  scoped in O1–O9; none requires new external capability. The residual 15% is genuine data
  poverty (crypto history depth, missing intraday history pre-collection).
- ceiling_gap: **~50 pts**, almost all recoverable by small code (O1 ≈ 50 lines; O3/O4/O6/O9 ≈
  hours each) — the same striking shape execution-growth reported last sweep.
- opportunity_cost_1y: **HIGH.** A year in the current state means: discovery output = 3 axis
  clocks + manual screens inside a box that cannot power h≥5, cannot see sub-8h, and re-tests
  nothing it previously killed. If any closed dimension holds one real edge, its entire forward
  compounding stream is forfeited silently (L1.28's exact asymmetry). The un-run 420 re-score
  (O2) alone carries the risk that the desk's core allocation of research effort has been
  steered by an instrument artifact for a full year.
- confidence: **0.85 on findings** (every claim command-verified this run, read-only); **0.5 on
  the scores** (scores are judgment over verified parts).
- unknown_unknown_score: **0.55** — this one audit found four instances of the same
  silent-degradation shape (phantom DB ×4 callers, stale slot snapshot, dropped INTERESTINGs,
  dedup-blocked re-scoring). Base rates say the shape exists elsewhere; the wiring agent
  (cron 09:44 daily) did not catch any of these.
- info_gain_if_investigated: **HIGH for T1/T2/T4/T6** — each converts a standing narrative
  ("price dead", "cross-asset barren", "0 survivors means no edge") into a measurement.
- expected_alpha_contribution: direct MEDIUM (T2/T4/T5 can seed clocks this quarter); indirect
  HIGH (O1/O5 de-blind the instrument every future candidate passes through).
- expected_compounding_contribution: **HIGH** — O1, O5, O6, O9 are multipliers: they raise the
  value of every future screen, every novelty check, and every recorded experiment.
- CEILING EXPANSION note: the 85% ceiling assumes daily/H8 bars and current history depth. The
  binding assumption is the 4,268-obs power wall, which is an `ic_min=0.03` CHOICE, not physics
  (O1 moves it), and the absence of intraday history, which is a $0 acquisition (F15). If both
  move, the ceiling itself is ~95% and the residual is only true market-history shortness. The
  assumption class is methodological + organizational, NOT technological — nothing here waits
  on 2-3y compute.

## 1. WHAT WE KNOW (validated strengths, each with proving command)

**S1 — The Stage-A screening harness is real, audited, and has caught real artifacts.**
`libs/research/axis_screen.py` bakes in the angle-20 de-contamination gate, a power floor, an
implausibility ceiling (SUSPECT-LOOKAHEAD), and forward-clock persistence. It has demonstrably
killed plausible fakes: Coinbase premium and Turkey premium (timing artifacts), and the
exchange_netflow sign-flip (raw IC −0.0345 mechanism-correct → residual +0.0124 after
de-contamination; graveyard line 185 calls this "unusually trustworthy" and explains why).
Proof: `grep -n "decontam\|angle-20" libs/research/axis_screen.py`; `grep -n "exchange_netflow"
docs/graveyard.md`.

**S2 — The graveyard is genuinely high-quality falsification memory, not a stub.**
185 lines; entries carry mechanism-of-death, tags, and re-entry conditions. It includes
external-literature kills with per-category replication numbers (Hou–Xue–Zhang RFS 2020: trading
frictions 3.8%/1.9% survive; Fieberg IRFA 2024 crypto restatement; Chordia 2.1M-strategy p-hacking
paper) and an era natural experiment (Bitcointalk Automated Trading Contest: same community/
platform/asset — pre-registered forward rounds 0/8 beat buy-and-hold, in-sample round 6/8 with a
228× "winner") that independently validates pre-registration + forward clocks as the load-bearing
control. Proof: `wc -l docs/graveyard.md` = 185; lines 85, 113–116.

**S3 — Research memory is alive and logging negatives as first-class.**
160 rows in `data/sor_research.sqlite` `research_memory` (categories: construction 96,
hypothesis 37, method 15, dataset 9, mission 3; results: failure 128, success 22, pending 10).
Construction-level logging (96 rows) satisfies the log-every-construction duty. Span
2026-07-24 → 2026-07-30, i.e. the habit is ~1 week old and active daily.
Proof: `SELECT category, COUNT(*) ... GROUP BY category` (ro connection).

**S4 — The L1.16a resurrection discipline has now worked end-to-end once, against the desk's own
flagship.** Kimchi was re-opened on a named enabling change (boundary proof refuting the
retraction premise) and re-tested at full 8.2y depth — and the claim-scale effect was REFUTED
(IC +0.0012 at n=2987 vs the original +0.148 at 200d; "would have been detected with
overwhelming power"). The desk falsified its own best story and recorded it. Proof:
`research_memory` rows `rm-20260730T223434-d36b21`, `rm-20260730T224130-41045b`.

**S5 — Two-stage discipline is stamped into artifacts.** Every screen artifact carries
`"stage": "A (zero promotion authority)"`; forward-slot registry note states Holm-cohort
semantics and refuses to under-count m ("Unreadable sources are counted as UNKNOWN, never
zero"). Proof: `grep -rn "zero promotion authority" data/batch_*.json`; `data/forward_slots.json` note.

**S6 — The daily discovery loop actually runs and produced output today.**
`web/discovery.json` updated 2026-07-31T00:27Z: 8 sleeves tested, 4 shadow-eligible
(funding_carry, xsec_price_mom, ts_trend, taker_flow), 3 data-gated mechanisms PENDING at
33/40d of forward archive. Proof: `python -c "json.load(open('web/discovery.json'))['updated']"`.

**S7 — The campaign-constant gate defect (420/420 auto-reject) is fixed in code.**
`libs/autodiscovery/validation.py` now computes PER-CANDIDATE verdicts: `cscv_candidate_pbo`
+ step-down adjusted p (`campaign_gate_stats`, line 383ff); legacy campaign-level PBO/RC demoted
to deprecated helper (line 344 "Use campaign_gate_stats + validate(campaign=..., column=...)").
Commit trail: `d56675a` "GAP #71 ROOT-CAUSED AND FIXED... the FDR module to fix it was already in
the repo, orphaned". Proof: `grep -n "campaign_gate_stats\|cscv" libs/autodiscovery/validation.py`.

**S8 — Pre-registration quality at its best is genuinely good.** The COT positioning panel
(AXIS_PREREGISTRATIONS.md §77, 2026-07-29) fixes constructions, splits, kill criteria and trial
charges BEFORE computation, pre-commits a negative result's budget consequence (cancels a
data acquisition), and documents dropped assets (Stooq bot-gate → §13 ruling pending; metals/
grains dropped, "part of the result, not a footnote"). Proof: read
`docs/research/AXIS_PREREGISTRATIONS.md` lines 82–124.

**S9 — Event-shaped edges have an event-shaped gate.** `libs/research/listing_events.py` with
pre-registered VARIANTS_TRIED trial pricing exists per §42; capacity policy is single-sourced in
`libs/research/capacity_policy.py`. Proof: files exist and are imported by scorers
(`grep -rn "capacity_policy" libs/research/*.py`).

## 2. WHAT WE DON'T KNOW (ignorance ledger: uncertainties, untested assumptions, evidence gaps)

### F1 — CRITICAL: the desk's search-allocation thesis ("price dead / axis rich") now has ZERO
### surviving positive exemplar, and standing doctrine still cites the refuted one.
Kimchi — the proof-case quoted in the SCREEN-ON-DISCOVERY doctrine ("IC +0.148 and momentum
timing Sharpe 1.3 — beating every price-only sleeve the desk ever rejected") — was refuted at
full depth on 2026-07-30 (F4/S4 above: IC +0.0012, n=2987). The 175-asset KR-premium panel
family was also null the same night (median IC +0.0050, sign-z 0.98 NS, 30/175 TIMING-ARTIFACT).
What remains on the axis side: three accruing clocks with 0–7 forward days and nothing confirmed.
The doctrinal claim "the edges are in untouched axes, not the picked-clean price space" is now
supported by NO validated instance. This does NOT prove the thesis wrong — the 420/0 price record
and the era natural experiment still stand against price families — but the affirmative half of
the allocation argument is currently evidence-free, and every organ's prompt still carries it as
settled fact. Consequence: the desk is steering 100% of new-axis effort by a narrative whose one
exemplar died, without a stated fallback ranking for where discovery effort goes next.
Proof: `research_memory` rows rm-20260730T223434 / rm-20260730T224130; doctrine text (system
prompt / SCREEN-ON-DISCOVERY) still citing +0.148.

### F2 — CRITICAL: a Holm forward slot is idle while the ledger says "capacity-blocked", and the
### 42-item resurrection queue that could fill it is read by nothing.
Live computation `derive_slots()` → m_concurrent=11, idle_slots=1 (kimchi's slot freed when it
left `data/axis_shadow_state.json`, updated 07-30T12:14). But the committed snapshot
`data/forward_slots.json` (updated 07-30T07:08) still says 12/12, idle 0, and experiment
`E-b70298da0e` (07-30) ledgered "the cohort is capacity-blocked at 12/12, not idle" — now false.
Meanwhile `data/graveyard_resurrection_queue.json` (n=42, prioritized, updated 07-27, PRIME
RESURRECTION treatments naming exact remedies) is written by `scripts/graveyard_resurrect.py`
and read by NOTHING (`grep -rn graveyard_resurrection_queue libs scripts api app` → only the
writer). Under L1.28a an unfilled forward slot is "evidence that will never be accrued"; under
L2.9 a built-but-unconsumed artifact is the named defect. Abandoned-idea reassessment currently
exists as a FILE, not a PROCESS.
Proof commands: inline above.

### F3 — CRITICAL: four production references point at a database that has never existed;
### all four degrade silently to "empty".
`data/research_memory.db` does not exist anywhere on the box (`find / -name research_memory.db`
→ nothing). Referenced by: `scripts/run_promotion_queue.py:47` (the L1.18a deployment race —
its artifact `data/promotion_queue.json` has NEVER been produced), `scripts/run_generation_diversity.py:46`
(HYPOTHESIS_MAX #2/#3/#6 wiring — `data/gen_diversity.json` absent, `panel_scorecard.json` has
no `gen_diversity` field), and `scripts/max_audit.py:1467,1665` (the audit organ itself reads a
phantom candidate store). Each carries the clause "this box may not be the research box, and an
empty queue is a fact worth reporting" — but this box IS the research box (the real store is
`data/sor_research.sqlite`, used by run_worker/run_supervisor/research_memory.py). The
graceful-degradation clause converts a wiring bug into a permanent silent no-op — the exact
self-greening class the audit doctrine names as prime quarry. Net effect for alpha-discovery:
the desk has NEVER measured hypothesis diversity (novel_rate / mechanism_entropy /
cross_generator_dup — the numbers that distinguish "420 candidates" from "one question asked
420 ways"), and the capacity-runway promotion race has never ranked a real candidate.
Proof: `grep -rn "research_memory.db" --include="*.py" scripts libs` (4 hits); `ls
data/promotion_queue.json data/gen_diversity.json` → absent.

### F4 — HIGH: the documented multiplicity spine is a corpse — trials_ledger has 0 rows and
### GauntletRunner has no production caller.
`trials_ledger` is empty in BOTH `data/alpha_registry.sqlite` and `data/sor_research.sqlite`
(SELECT COUNT(*) → 0). `GauntletRunner` (libs/validation/gauntlet.py — "the trials ledger feeds
the true (inflated) trial count into the Deflated Sharpe Ratio") is imported only by
`__init__.py` re-export and two type-only imports; nothing instantiates it. Its fallback when
run without a ledger: `n_trials=2`. Production validation actually lives in
`libs/autodiscovery/validation.py` with its own campaign accounting. Consequences: (a) the
gate-optimality duty's "audit effective-vs-raw trial count every cycle" cannot run off the
durable ledger — it is empty; (b) cross-CAMPAIGN multiplicity (trials accumulated across days/
sessions/organs) has no single accounting spine — each screen logs trials in prose
(research_memory) but no queryable count aggregates them.
Proof: `grep -rn "GauntletRunner(" libs scripts api app` → definition only.

### F5 — HIGH: the Stage-A power gate structurally closes the HORIZON dimension of the search
### space, and R0030 (which names half of this) has sat open since 07-28.
`powered ⇔ 1.96/sqrt(n_eff) <= ic_min` with `ic_min=0.03` FIXED at every horizon, and
`n_eff = n/(horizon_days × panel_width)`. Therefore: h=1d needs 4,268 obs ≈ 11.7 years (BTC
5,575d qualifies; ETH 4,008d does NOT); h=5d needs 58 years; h=20d needs 233 years — no crypto
asset can EVER produce a powered multi-day-horizon daily cell; stacked panels collapse to date
count (R0030). Measured outcome across 27 screen artifacts: 69 UNDERPOWERED / 49 WEAK / 20
INTERESTING / 3 SUSPECT-LOOKAHEAD / 2 TIMING-ARTIFACT — 48% of all recorded cells land in the
zero-information bucket. The unpriced defect beyond R0030's text: ic_min is not horizon-scaled.
Economics says the minimum IC worth caring about GROWS as sqrt(h) (fewer independent bets/year:
Sharpe ≈ IC×sqrt(bets)), so a horizon-honest gate is `ic_min(h) = 0.03×sqrt(h)` — which makes
h=5 powerable at n_eff≥1,115 (BTC has it) and h=20 at n_eff≥267 (BTC has it) at exactly the
effect sizes that would matter economically. Today the TARGET/HORIZON SWEEP DUTY commands
testing cells (5d, 20d+) that the harness auto-demotes regardless of merit, and the resurrection
queue's PRIME candidates prescribe "horizon search is the exact remedy" — a remedy the
instrument cannot score. This is L1.25's diagnostic order item 1 (instrument defective) live.
Proof: `libs/research/axis_screen.py:96-160`; verdict tally command in this report's log;
`recommendation_ledger.json` R0030 status "open", roi_bps 60, raised 07-28.

### F6 — HIGH: three SCREEN-INTERESTING survivors from 07-23 were silently dropped — no clock,
### no kill, no memory row, no conversion entry.
`github_dev_velocity` (IC −0.1924, n=38!), `n-unique-addresses` (−0.0449, n=475),
`estimated-transaction-volume-usd` (−0.0478, n=475) all carry verdict SCREEN-INTERESTING in
`data/batch_github_screen.json` / `data/batch_onchain_screen.json` (both 07-23, pre-power-gate)
and appear NOWHERE else: not in the graveyard, not in research_memory (`LIKE '%github%'` etc. →
0 rows), not in conversion_record.json, not in any clock. All three are sub-detection-floor by
the 07-26 power gate (n=38 → min detectable IC 0.318 vs claimed −0.19) so the likely honest
verdict is UNDERPOWERED — but the honest ACTION is to re-verdict and ledger them, not silence.
"Silent drops are forbidden" is the duty's own language. Also stale-artifact debt:
`data/venue_premium_screen.json` still says Coinbase premium "SCREEN-INTERESTING" on disk
(hand-rolled pre-harness screen, no decontam fields) though the graveyard records it as a
timing-artifact kill — a contradiction between committed artifact and graveyard.
Proof: files named; grep outputs in audit log.

### F7 — MEDIUM: an entire superseded research orchestration layer sits undead in the primary
### research DB (L2.9: neither ACTIVATE nor RETIRE).
`data/sor_research.sqlite`: campaigns 348 total = 340 'queued' + 7 done + 1 leased; last
campaign created 2026-06-22; workers' last heartbeat 2026-06-22 on host DESKTOP-R5I548F (not
this box); the 14 candidates ever produced are FX pairs (AUDCAD…) from a scope the desk left.
The queued 340 are crypto-symbol × 12-price-family campaigns that will never run. This corpse
is exactly what the (phantom-pathed) promotion queue would read if its path were fixed naively —
fixing F3 by pointing at this store without draining/retiring it would rank 39-day-old FX
candidates into the deployment race.
Proof: `SELECT status, COUNT(*) FROM campaigns GROUP BY status`; workers table dump.

### F8 — MEDIUM: the Charter-§22 hypothesis organ (discovery_hypotheses.md) is stalled at 2
### entries, and its own covenant is unmet.
Doc promises "Every newly validated + adopted dataset immediately spawns hypothesis-generation
entries here (no new data axis sits idle)". Reality: DH-001 and DH-002, both seeded 2026-07-19,
both status open, outcome "—", nothing added since — while research_memory records 9 dataset
rows since 07-26. 12 days without a single new WHERE-value-exists hypothesis or an outcome on
the two open ones.
Proof: `wc -l docs/research/discovery_hypotheses.md` = 37; body read.

### F9 — MEDIUM: the novelty gate's known weakness is live in 4 callers and unfixed.
`hypothesis_novelty.py` is unchanged since its creation (git log: single commit f290d8a);
the 07-30 research-engine audit measured 0% recall on paraphrased duplicates (Jaccard tokens).
It IS wired (generation_roi.py, screen_fred_macro_axis.py, screen_idle_axes.py,
screen_exchange_netflow.py), so every screen's novelty check can wave through a reworded dead
idea — multiplicity budget burned twice, the exact failure the NOVELTY GATE duty exists for.
A better matcher (TF-IDF) already exists in-repo at knowledge_engine.py:80-99 (research-engine
audit finding, verified still true by git history).
Proof: `git log --oneline -- libs/alpha_factory/hypothesis_novelty.py` → 1 commit.

### F10 — MEDIUM: cross-asset transfer is empirically UNEXPLORED — every one of the 11
### pre-registered cross-asset hypotheses died at the EV pre-gate, none at data.
AXIS_PREREGISTRATIONS (07-22): cme, etf_flows, wikipedia, fx, equity, index, metal, energy,
mining, fed, crossasset — 11/11 REJECT (EV below thresh), EVs 0.0003–0.0326. So the desk's
entire cross-asset surface (CME anchor, ETF flow pressure, DXY rotation, equity lead-lag, gold
rotation, net-liquidity...) was killed by an estimator BEFORE any data was consulted. Whether
the EV gate is calibrated or dead is UNKNOWN — its lifetime accept/reject histogram (the
gate-optimality duty's required artifact) does not exist anywhere I could find. A gate that
rejected 11/11 in its one recorded batch, feeding a duty that says "a gate that rejects ~100%
carries ZERO information", is either honestly reporting a barren class or silently deleting a
dimension; nobody has measured which. (COT panel S8 is the one cross-asset MEASUREMENT since,
and it is a methods measurement, not an edge hunt.)
Proof: AXIS_PREREGISTRATIONS.md table; absence: `grep -rn "ev_gate\|accept.*histogram" libs
scripts` → no histogram artifact.

### F11 — MEDIUM: hypothesis diversity has never been measured (instrument built, output never
### produced) — so "420 candidates" vs "one question 420 ways" is still undecidable.
The metrics exist in code as of 07-30 22:50 (`run_generation_diversity.py`: novel_rate,
mechanism_entropy, market_breadth, cross_generator_dup) and the script's own docstring admits
"The desk has never been able to tell those apart, and 420/0 is exactly the record that needed
telling apart." It reads the phantom DB (F3) and has never produced `data/gen_diversity.json`.
Until this number exists, the 420/0 record cannot be attributed between "price space is dead"
and "the generator is redundant" — which is exactly the attribution the allocation thesis (F1)
needs.
Proof: `ls data/gen_diversity.json` → absent; `_DB` path at line 46.

### F13 — HIGH: the automated generation engine is in a steady state of ZERO new tests, by its
### own honest accounting — and nothing refills its mechanism pool.
`data/cro_ai_logs/crypto_factory_cron.log` (07-30 03:30 run): `[cycle] tested=0 survivors=0
rejected=0 promoted_paper=0 skipped_dup=420` — the daily D1 factory re-generates the same 420
price-family candidates, content-hash dedup skips every one, zero get tested. Its own pilot
verdict: "0 durable survivors in 1244 trials — throughput is re-drawing a known pool; the
constraint is DATA/MECHANISM, not volume. Do NOT rent hardware yet." The engine is honest about
being exhausted; the defect is that NOTHING feeds it new mechanisms: the axis pipeline runs
outside the factory (manual/LLM screen scripts), the resurrection queue is unread (F2), the
Charter-§22 organ is stalled (F8), and the fusion engine's 5 combos all landed UNDERPOWERED
(data/fusion_engine.json, 07-30 — it runs, refuses to mine noise, and is walled by F5's power
floor like everything else). Generation capacity is idle at 100% (L1.28a) while four separate
refill mechanisms exist in various states of disconnection.
Proof: factory log lines quoted; `data/fusion_engine.json`.

### F14 — HIGH (CONTRARIAN, and constitutionally pre-confirmed): "price space is dead" has never
### been measured by the FIXED instrument — the 420 have not been re-scored since the
### per-candidate gate landed, because dedup marks them already-known.
L1.25's own text records that "The 420/0 record was an INSTRUMENT ARTIFACT (two campaign-constant
gates) misread as a fact about crypto." The instrument is now fixed (S7: per-candidate CSCV PBO +
step-down). But the factory's dedup (`skipped_dup=420`) treats candidates tested under the BROKEN
gate as settled, so no candidate has ever been scored by the fixed gate. The honest current state
of the price space is UNKNOWN, not dead. A gate-version-aware re-score is a NAMED enabling change
under L1.16a (new measurement capability) — re-running the 420 through the fixed per-candidate
gate is constitutionally authorized resurrection, cheap (code + data already on disk), and
directly tests the desk's central allocation narrative from the other side than F1 tests it.
Proof: factory log `skipped_dup=420`; L1.25 text; commit `d56675a`.

### F15 — MEDIUM-HIGH: the temporal dimension of the search space is two cells wide — D1 and H8.
The lake holds D1 everywhere and H8 for crypto (`find data/lake/bronze/crypto -type d -name H8` →
present; factory runs `--timeframe H8` and `D1` daily). Below 8h: nothing — no 1m/5m/1h bars
anywhere in the lake. The named free source of truth (`data.binance.vision`, 1m klines since
2017) sits in the universe map with status `queued`. Meanwhile: the graveyard's own follow-ups
demand intraday ("Do not re-test exchange-flow at daily frequency without either intraday
granularity or a per-exchange decomposition"), and §42's named structural ground — day-1 listing
funding spikes, delisting unwinds, thin-pair cross-venue funding — is event/intraday-shaped, so
the constitutionally-named niche advantage is largely UNTESTABLE with current data. Combined
with F5 (h≥5 unpowerable at daily), the desk's entire powered hypothesis surface is: h=1d (BTC
depth only) and H8. Everything shorter lacks data; everything longer lacks power.
Proof: lake listing; universe map entry status; graveyard line 185.

### F16 — MEDIUM: causal attribution is absent from 79% of the experiment record.
338/429 rows in `data/experiment_registry.jsonl` carry `M_UNMAPPED` as their mechanism; the
mapped tail (M_ATTENTION_DELAY 30, M_FORCED_DELEVERAGE 23, M_STRUCTURAL_BARRIER 18...) shows the
taxonomy works when applied. L1.16 says an edge (and by extension a falsification) not understood
at mechanism level is not durable knowledge; four-fifths of the desk's recorded experiments
cannot be queried by mechanism, so "which mechanisms have we never probed?" — the exact question
generation needs (F13) — is unanswerable from the record. (Caveat: this registry is
commit-derived, so some UNMAPPED is classifier weakness rather than research weakness — but the
classifier being weak IS the finding: mechanism tagging happens at auto-classification time, not
at experiment time.)
Proof: mechanism tally command in audit log.

### F17 — MEDIUM: the catalog-vs-launch leak persists at the SOURCE level: 17 of 41 graded
### universe-map sources are still `queued`; 5 are LIVE/confirmed-class.
`data/data_universe_map.json`: 60 categories, 41 graded source entries — status: queued 17,
confirmed 3, LIVE 1, verified-downloaded 1, remainder leads/dead/licence-gated. The
screen-on-discovery duty exists because "catalog breadth ran ~8.5/10 while ingested-AND-TESTED
ran ~4.5/10"; the source-level ratio today (≈41% queued) says the same leak is alive one level
up, with the intraday source (F15) among the queued.
Proof: tally command in audit log.

### F18 — LOW-MEDIUM: regime-conditioning exists as a price FAMILY but not as a testing
### DIMENSION; crowding assessment does run.
Only one screen script conditions on regime (`grep -rln regime scripts/screen_*.py` →
screen_fred_macro_axis.py); the resurrection queue's `btc_correlation_regime_carry_conditioning`
("died in one regime — re-test conditioned on regime") is unread like the rest of the queue.
Regime infrastructure itself is live (`data/crypto_regime.json` updated today; note in passing
for validation-stats: rule-based says bear, HMM says bull, `hmm_gmm_agree: false`, yet
`regime_confidence: 1.0`). Crowding: `CrowdingIntelligence` runs via the alpha-factory export
path (`alpha_pipeline.json` updated 07-30 08:40) — assessed, not orphaned.
Proof: greps + file timestamps above.

### F12 — OPEN QUESTION: what the desk cannot test for missing data is documented only
### case-by-case, never as a registry.
The fred_macro precedent is excellent ("this axis cannot produce a powered daily verdict,
ever" — generation_due.md, with the arithmetic) — but there is no standing "untestable-signals
map" enumerating which mechanisms are blocked by which missing data (intraday granularity,
per-exchange decomposition, options surfaces, orderbook depth history...). The graveyard's own
follow-ups name intraday variants ("Do not re-test exchange-flow at daily frequency without
either intraday granularity or a per-exchange decomposition") that no artifact tracks as a
data-acquisition demand. Each such case lives in prose; none aggregate into the universe map's
residual_gap grading.

## 3. WHAT COULD MATTER MOST (ranked opportunities; compounding multipliers flagged)

Ranked by expected impact × confidence / (cost × maintenance). Every item names what it displaces
(L1.14): each displaces one day of the current default — running an exhausted generator and
manual screens inside a closed search box — which is the lowest-EV use of the slot available.

**O1 [COMPOUNDING MULTIPLIER] — Make the Stage-A power gate horizon-honest (fixes F5, executes
open R0030).** Scale `ic_min(h) = 0.03·√h` (economics: Sharpe ≈ IC·√bets, so the minimum IC
worth detecting grows exactly this way), and fix panel n_eff to model cross-sectional effective
breadth instead of collapsing to date count. ~50 lines in one audited file + re-run of all
archived screens (inputs on disk). Raises the value of EVERY future screen and re-opens the
horizon dimension for the whole backlog, the fusion engine, and the resurrection queue's PRIME
candidates. Risk: a looser gate admits noise → mitigate by keeping the de-contam gate unchanged
and re-verdicting archived screens first (measurable flip-rate before any new hunting).
Complexity: low. Dependencies: none. Monitoring: verdict histogram per gate (the gate-optimality
duty's own artifact). Retirement: never (this IS the instrument).

**O2 — Re-score the 420 through the fixed per-candidate gate (F14).** One flag
(gate-version-aware dedup or explicit resurrection batch), data on disk, zero new collection.
Either outcome is decisive: survivors → the price space was never dead and the allocation
narrative flips on evidence; zero survivors → "price dead" is FINALLY measured by a working
instrument and becomes citable fact instead of instrument artifact. Directly answers the desk's
central strategic question. Cost: hours of compute. Confidence of information gain: ~1.0.

**O3 — Wire the resurrection loop into the idle slot (F2+F6).** A consumer for
`graveyard_resurrection_queue.json`: refresh `forward_slots.json` (one `write_snapshot()` call),
re-verdict the 3 silently-dropped 07-23 INTERESTINGs and ledger them, then work the queue's top
entries and fill the idle Holm slot with the best survivor. The queue's standout is **options
VRP** (graveyard line 65: "best IC of campaign (+0.06)... real signal, starved — revisit only
with more vol markets"; queue treatment "starved, not wrong"): its named re-entry condition is
now satisfiable for FREE — the universe map records Deribit historical access verified by actual
download. Next: the PRIME horizon candidates (defi_health, multilingual_wikipedia — both "killed
at DAILY horizon only", exactly what O1 unlocks). Converts abandoned-idea reassessment from a
file into a process. Complexity: low-medium. The horizon candidates depend on O1; options VRP
depends only on data collection already proven possible.

**O4 — Repoint the four phantom-DB references; retire the campaign corpse first (F3+F7, in that
order).** `run_promotion_queue.py`, `run_generation_diversity.py`, `max_audit.py`×2 →
`data/sor_research.sqlite`; but FIRST mark the 340 dead 06-22 campaigns/candidates retired (or
filter by scope) so the promotion race doesn't rank 39-day-old FX candidates. Then the diversity
metrics (F11) and the capacity-runway race produce their first real output. Complexity: low.
Failure mode if order ignored: stale-candidate pollution of the deployment race.

**O5 — Add positive controls to the screen (EXTERNAL-perspective gap; no F-number because it is
a capability that has never existed).** The screen has never been shown to DETECT a true edge:
since the 07-26 power gate, its accept rate is ~0/45+ cells; every historical accept was later
refuted, demoted or graveyarded. Inject synthetic edges (known IC, known horizon, realistic
noise) through `stage_a_screen` as calibration probes — the memory note's "synthetic-probe
normalization trap" applies: inject at the SIGNAL level, never post-normalization. Deliverable:
measured detection power per (IC, n, horizon) cell — the gate's ROC, which the gate-optimality
duty implicitly requires and nothing produces. [COMPOUNDING MULTIPLIER: converts every future
"0 survivors" from ambiguous to informative.]

**O6 — Swap the novelty gate's matcher for the in-repo TF-IDF (F9).** knowledge_engine.py:80-99
already implements it; the gate has 4 live callers and 0% paraphrase recall. Hours of work,
protects the multiplicity budget every organ spends. Displaces nothing material.

**O7 — Audit the cross-asset EV pre-gate with accrued hindsight (F10).** The 11 rejected
preregistrations are 9 days old (07-22) and their falsifiers specified "40 fwd days NW-t" — the
lake has been accruing exactly that forward data since. Score all 11 falsifiers on the accrued
window: any that would have passed → the EV gate mis-calibrated and cross-asset re-opens; none →
the gate's 11/11 reject was honest and is ledgered as such. Free evidence, already collected.

**O8 — Open the intraday dimension scoped to §42's named ground (F15).** Launch
`data.binance.vision` 1m ingestion bounded to listing/delisting event windows (not a full
backfill), feeding `listing_events.py` at hourly resolution. The niche the constitution names as
the desk's structural advantage becomes testable. Complexity: medium (storage + alignment
discipline). Licence: free venue archive, §13-clean.

**O9 — Mechanism-tag at experiment time, not classification time (F16).** `research_memory.py
log` gains a required `--mechanism` from the MECHANISM_GRAPH taxonomy; backfill is optional, the
forward flow is the point. Makes "which mechanisms have we never probed?" queryable — the exact
query generation (F13) needs. Complexity: trivial.

**O10 — Untestable-signals registry (F12) + practitioner-literature run (FRONTIER).** One JSON
mapping blocked mechanism → named missing data → acquisition demand, fed by the fred_macro
precedent's arithmetic; and the literature rotation already BINDS toward the never-visited
practitioner family (AQR/Man/BIS/IMF/Fed) per literature_coverage.md's own rule.

## 4. WHAT WE TEST NEXT (concrete experiments, success criteria, retirement conditions)

**T1 — Gate-fix flip-rate measurement (executes O1; validates before it hunts).**
Re-run every archived screen input under the horizon-scaled gate. Success criterion: a measured
verdict-flip table (how many UNDERPOWERED → WEAK / INTERESTING, per horizon). Validation: the
de-contam gate stays untouched; any new INTERESTING goes to a clock, never to capital
(two-stage law unchanged). Retirement condition: if <5% of archived UNDERPOWERED cells flip,
the power wall was real data poverty, not gate miscalibration — ledger that as the proving push
and keep the current gate with an expiry.

**T2 — The 420 re-score under the fixed gate (executes O2).** Pre-register NOW, before running:
this is ONE resurrection batch under a named enabling change (per-candidate gate), not 420 new
trials — the multiplicity charge is the batch, and survivors earn CLOCKS not capital. Success:
a per-candidate verdict table published either way. Kill criterion: none — both outcomes are
the deliverable (F14). Retirement: n/a, single shot.

**T3 — First diversity measurement (executes O4's diversity half; needs the DB repoint).**
Run `run_generation_diversity.py` against the real store; publish novel_rate /
mechanism_entropy / cross_generator_dup for the 420 and for the current seats. Success: the
numbers exist and are floored per L1.0 (born with fence in the same commit). Info gain: decides
whether F13's exhaustion is space-exhaustion or generator-redundancy.

**T4 — Cross-asset hindsight audit (executes O7).** Score the 11 pre-registered falsifiers on
the forward window accrued since 07-22. Success: 11-row table (NW-t, verdict vs EV-gate
prediction) + a calibration decision on the EV gate. Retirement: if data gaps block >3 of 11,
document per-axis and re-run when 40d complete.

**T5 — Resurrection pilot: options VRP first, then the two PRIME horizon candidates (executes
O3).** (a) Options VRP: collect the free Deribit vol-market breadth its kill demanded, re-screen
under the audited harness with a pre-registered construction — this one does NOT depend on T1
(it died of breadth, not horizon). (b) defi_health and multilingual_wikipedia at weekly/20d
horizons under the fixed gate (depends on T1). Winner (if any) takes the idle Holm slot with a
pre-registered forward clock. Success: slot filled OR a ledgered empty-seam result and queue
rows closed either way. Retirement: queue empty or all treatments consumed.

---

**REGISTER ROWS OWED (§35 / no-orphaned-recommendation law).** This audit ran READ-ONLY, so it
could not row its own findings. The next live cycle owes one `scripts/recommendations.py add`
row per opportunity O1–O10 (or a reasoned rejection), and `scripts/track_findings.py` rows for
F1–F18. Per the coverage ratchet, reaching 100% by not rowing these is the denominator trick;
this paragraph exists so the omission cannot be silent.

**T6 — Screen positive-control battery (executes O5).** Synthetic edges at IC ∈ {0.03, 0.06,
0.12}, h ∈ {1, 5, 20}, n ∈ {200, 1000, 4268}, injected at signal level pre-normalization.
Success: a detection-power surface published next to the gate; every future screen batch cites
which power cell it ran in. Retirement: never; re-run on any gate change (it becomes the gate's
regression test).

## APPENDIX A — SIX-PERSPECTIVE COVERAGE LOG

- **INTERNAL** (measured, not configured): F2 (live `derive_slots()` vs stale snapshot), F3
  (phantom DB, artifacts absent), F6 (silent drops traced through graveyard + research_memory +
  conversion record), F13 (factory log's own `tested=0 skipped_dup=420`). Strengths S3/S6
  verified from row counts and today's artifact timestamps, not from schedules.
- **EXTERNAL** (how another world-class team would improve this): (a) horizon-scaled power
  analysis is standard practice — O1; (b) panel effective-breadth modeling instead of
  date-collapse — O1; (c) positive controls / detection-power ROC for any gate that can kill
  candidates — O5, currently absent: the screen has never been shown to accept a true edge;
  (d) explicit exploration quota in generation instead of a converged dedup pool — F13/O2.
- **FUTURE** (2-3y redesign): LLM-native mechanism-first generation grounded in the mechanism
  graph × data-axis matrix (the taxonomy exists, MECHANISM_GRAPH.md, 113 lines; the coverage
  query it needs is blocked by F16); embedding-based novelty replacing token Jaccard (an
  `alpha_embedding_engine.py` already sits in libs/alpha_factory); agentic per-axis screen
  authoring is already this desk's norm — the future design mostly requires wiring what exists.
- **CONTRARIAN** (core assumptions actively tested): F14 — "price is dead" has never been
  measured by the fixed instrument, and the constitution itself records the original 420/0 as an
  instrument artifact; F1 — "axis rich" lost its only exemplar to the desk's own depth re-test;
  F5 — "we screen honestly" is true per-cell but the gate's accept rate since the power gate is
  ~0/45+ cells, which under the gate-optimality duty is itself a zero-information state to
  investigate, not a virtue.
- **GREENFIELD** (rebuild from validated knowledge only): one store (`sor_research.sqlite`), one
  screen (axis_screen with horizon-honest power + positive controls), one cross-organ trials
  spine, generation driven by mechanism-coverage gaps, resurrection as a scheduler input.
  Historical baggage scored: two dead stores (empty `trials_ledger` ×2 DBs), one dead
  orchestration layer (340 queued campaigns, workers heartbeat 06-22, F7), four phantom-path
  callers (F3), three stale/contradictory artifacts (forward_slots snapshot, venue_premium
  SCREEN-INTERESTING vs graveyard kill, `experiment_registry` "capacity-blocked" claim).
  Replaceability: high — nothing in the current design is load-bearing except the graveyard,
  research_memory, and axis_screen, which are exactly the parts worth keeping.
- **FRONTIER** (recently possible, unexploited): the literature machine is real and recent
  (five LIT reports 07-26; failed-replication family already yielded 11 findings / 4 graveyard
  rows / 3 method rails) — the rotation rule now BINDS toward the never-visited practitioner
  family (AQR/Man/Two Sigma/BIS/IMF/Fed), literature_coverage.md's own words: "criminally
  under-mined"; SSRN is a routing problem (403, NK-005 ladder exists), not a dead corpus;
  `data.binance.vision` 1m archives (free, catalogued, queued) are the single highest-value
  unexploited public dataset for the §42 niche (F15/O8).

## APPENDIX B — NEGATIVE-SPACE SWEEP LOG

Questions never asked / data never collected / methods never attempted — each checked for
existing artifacts before being listed (a hit would have removed it):

1. **Detection-power of the desk's own screen** — never measured (no positive-control artifact
   anywhere; O5/T6). The desk knows its false-positive discipline intimately and its
   false-NEGATIVE rate not at all — after a year whose every "0 survivors" result was read as
   fact about markets.
2. **Options/vol-surface axis — the sharpest single resurrection on the desk, and it is
   sitting unread.** Graveyard line 65: "options VRP | best IC of campaign (+0.06) but breadth
   2 | no_breadth | real signal, starved — revisit only with more vol markets." The resurrection
   queue carries it ("RESURRECT-ABLE: same — starved, not wrong", priority 3) — in the file
   nothing reads (F2). Its named re-entry condition is now SATISFIED for free: the universe map
   records Deribit historical access VERIFIED by actual download ("prior 'destroyed-at-source'
   claim REFUTED... 159,259,129 B, 19,239,595 rows, free"), and watchlist card 13 already
   proposes the block-print/IV construction. Zero research_memory rows match
   option/implied/gamma/skew — no options hypothesis has been screened since the kill. A
   real-by-our-own-record signal with a satisfied unlock has been waiting behind a reader that
   doesn't exist.
3. **Orderbook-depth history** — recorders started recently (run_recorder_bybit/spot on 10-min
   watchdog); no depth-derived hypothesis has ever been screened; the archive is accruing
   unread. Clock-saturation duty will owe this axis a hypothesis when it matures — nothing
   pre-registers it today.
4. **Delisting unwinds** — §42 names them; `listing_events.py:56` explicitly EXCLUDES them
   ("keeping only listings (a delisting is a different event)") — the code documents the other
   half of its own event family as out of scope, and no delisting collector, event study, or
   graveyard attempt exists anywhere. Named ground, never walked, and the exclusion is written
   down.
5. **Weekly/monthly aggregation as a power remedy** — the COT panel uses weekly by nature;
   no crypto screen has ever been aggregated to weekly to buy power at long horizons (would
   need O1's scaled ic_min to be coherent). Never attempted.
6. **Stablecoin depeg/redemption events** — stablecoin supply axes are live clocks, but the
   EVENT family (depegs, redemption windows, attestation gaps) has no event study. Event gate
   exists (S9); this family was never routed through it.
7. **Arabic-language ecosystem** — L1.11a names it as a category; no dig ARTIFACT exists
   (KR/CN/JP/TR/BR all have artifacts; AR has none). The gap is KNOWN and rotting in the
   write-only inbox: improvement_inbox.md:157 "MIDDLE EAST / UAE CRYPTO FLOW... Arabic forums/
   Telegram nearly unmonitored. Add Arabic to language-blind" — an inbox the desk's own
   operational memory records as read-by-nothing. Known gap + dead letterbox = still a gap.
8. *(corrected during verification — the original claim here was WRONG and is replaced by its
   refutation, which is itself the finding)*: cross-venue funding dispersion HAS been screened
   — rm-20260729T062525 ("Four novel hypotheses on already-ingested axes: ...cross-venue
   funding d[ispersion]...", result: failure) and KR premium dispersion is pending
   (rm-20260730T223424). The seam is CLOSED, not open — and the fact that this auditor's
   first-pass grep missed it confirms research_memory works when queried properly. Negative
   knowledge did its job here.
9. **The desk's own fill/quote data as an alpha source** — the Execution Reality Model is a
   moat pillar (L1.11); execution intel runs (cron */20); no hypothesis has ever been screened
   FROM fills (adverse-selection timing, queue-position value). Free, proprietary, unread.
10. **Failure-mode simulation for discovery itself** — black_swan_library.json exists for
    markets; no equivalent stress test exists for the RESEARCH pipeline (what does the desk
    discover in a regime where all current clocks die simultaneously?). Never simulated.

Empty seams verified and reported as empty (documented-empty is a deliverable): crowding
assessment DOES run (F18 — checked before listing it here); H8 timeframe IS tested daily
(factory log) — the "everything is daily" hypothesis was FALSE and is corrected in F15;
research_memory IS being written with negatives as first-class (S3) — the write-only concern
from the 07-30 audit applies to READERS, not writers.

## APPENDIX C — PRIOR-SWEEP DELTA

The 2026-07-30 and 2026-07-29 alpha-discovery reports were empty skeletons (54 lines, all
placeholders; synthesis: "NO AUDIT — 2nd loss in 3 sweeps"). There is no prior completed
alpha-discovery audit to delta against. This report is the baseline. The 20260730_SYNTHESIS
items touching this subsystem (promotion stall, findings-to-queue break) are incorporated as
F3/F4/F13 with fresh evidence rather than re-cited.
