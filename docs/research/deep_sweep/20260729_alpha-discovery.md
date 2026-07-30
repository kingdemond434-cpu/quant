# DEEP COLD AUDIT — ALPHA-DISCOVERY SUBSYSTEM — 2026-07-29

_Auditor: weekly deep cold audit (doctrine v2 + exhaustion mandate 2026-07-28). Scope: hypothesis
diversity, unexplored behaviors, crowded themes, neglected regimes, cross-asset transfer,
temporal-resolution gaps, feature interactions, regime-conditioned hypotheses,
causal-vs-correlational, redundancy, negative-result reuse, abandoned-idea reassessment,
falsification quality, ignored markets, untestable-for-missing-data signals. READ-ONLY.
Prior sweeps: 20260726 and 20260728 (yesterday). Because only ~24h elapsed, this sweep
(a) re-measures the 07-28 sweep's 6 pre-registered success metrics, (b) verifies what actually
MOVED in 24h, and (c) spends its main effort on seams neither prior sweep dug: quantified
hypothesis-diversity/concentration, target-universe concentration, crowding on the live book,
event/calendar mechanisms, unlock/listing event axes, and live-edge decay re-falsification._

## SCORES (headline)

- current_capability_pct: TBD
- practical_ceiling_estimate: TBD
- ceiling_gap: TBD
- opportunity_cost_1y: TBD
- confidence: TBD
- unknown_unknown_score: TBD
- info_gain_if_investigated: TBD
- expected_alpha_contribution: TBD
- expected_compounding_contribution: TBD
- CEILING EXPANSION: TBD

## 0. RE-MEASUREMENT OF THE 07-28 SWEEP'S 6 PRE-REGISTERED METRICS

_Context for fairness: only ~9–33h elapsed since the prior sweep's data pulls (this sweep runs
2026-07-29 01:00–02:30 UTC; the prior pulled ~07-28 16:00). Zero commits landed since 3db47ef
(07-28 15:26; `git log -1 --format='%ci %h'`). One working session happened (07-28 20:26–20:32,
visible as 87 uncommitted files, `git status --short | wc -l` → 87; `git diff --stat` → 76 files,
+940/−278) — it was a direct response to the prior sweep and it moved three of six metrics. All of
it is UNCOMMITTED ~5h later; per §33 "uncommitted output DID NOT HAPPEN." A second material event:
the cash-and-carry DEADMAN ruin rail fired DURING this sweep (see F0)._

**M1 — Positive-control matrix exists (T1): FAIL.** No artifact newer than the 07-26 probe files
(`ls -la _audit_gate_probe*.py` → both Jul 26 20:09). R0017 (synthetic arm injects SR +0.5,
realises −2.32) still `open`. The funnel's false-negative rate remains unmeasurable.

**M2 — `ev_gate_audit.json` ≥20 entries + in-code appends: FAIL.** Still 3 entries, latest
2026-07-12 (`python3 - <<read json>>` → entries: 3, latest: 2026-07-12). The only code reference
to the file is a docstring in `research_cycle.py:205` — no append site exists. The gate has now
missed every verdict for 17 days while being the subsystem's most-cited defect.

**M3 — One slot-cohort number: FAIL.** `cat data/shadow_sleeves.json` → `[]`;
`run_alerts.py:241` → `_standing = 6` hardcode intact; `data/stageb_capacity.json` still
recommends 5 vs law's `MAX_FORWARD_SLOTS = 12` (`TWO_STAGE_DISCOVERY_LAW.md:27`) with no written
resolution. Four incompatible cohort numbers persist unchanged.

**M4 — coverage matches artifacts: PASS (closed within hours of being named).**
`.venv/bin/python scripts/research_memory.py coverage` → "AXIS COVERAGE: 20/20 converted (100%)".
The 3-idle-axes contradiction was closed in the 20:28 session: idle-axis cells + micro result now
carry memory rows (rows LIKE '%liquidity_withdrawal%' → 1; stage_a-linked rows → 5; research_memory
total 133→140). The fastest finding-to-fix turnaround this subsystem has recorded (~4.5h).

**M5 — ≥1 resurrection re-test AND ≥1 micro-feature screen rowed: FAIL (0 of 2).**
research_memory LIKE '%resurrect%' → 0 rows; `data/feature_library.json` still lists the same 5
features `computed_unused` (spread_bps, depth10, imbalance, concentration, slope), 447 proposals
untouched. The two nearest-term Stage-B feeder programs both idle.

**M6 — §41 zero open rows >7d for this subsystem: ON TRACK TO FAIL, not yet failed.**
R0016/R0017/R0023 all still `open` (raised 07-26, so 3 days — they cross the 7-day bar 08-02).
The ledger overall: 32 rows, **27 open** (14 raised 07-26, 13 raised 07-28), 3 implemented,
1 scheduled, 1 rejected. Dispositions in the last 24h: **zero**, while 8 new rows were raised
(R0025–R0032). The finding-closure deficit is now growing at ~8 rows/day.

**Net: 1 PASS, 4 FAIL, 1 pending — and the one PASS was the cheapest item.** The pattern from
07-28 sharpens: instrument-repair happens same-day when it is a small write (coverage rows);
governor-repair (EV gate, slot cohort, positive control) has now survived three consecutive
sweeps, two self-findings, and 27 open ledger rows without a line of code changing.

## F0 — INCIDENT DURING SWEEP (context every reader needs first)

At **2026-07-29T01:04:23Z**, while this sweep ran, the cash-and-carry DEADMAN ruin rail fired:
`cat data/CASHCARRY_KILL` → "DEADMAN ruin rail fired 2026-07-29T01:04:23Z"; `deadman_state.json`
→ `fired: true, breaches: 163, has_positions: false, last_eq: -23179.23, high_water: +7510.02`.
Lineage: this is deadman #7, same fee-fire as INCIDENT #6 (07-27, "TRUE FIRE, software-caused":
commission-billing loop = −35.01% of the sleeve's $5,000 vs thesis-only P&L −2.19%). No
intervention taken (this audit is read-only; the rail is doing its designed job). The
alpha-discovery consequence is large and appears throughout this report: **the EV gate's
"known-good calibration anchor" (carry, EV 0.1171) is production-falsified at its deployed
config** — research_memory 07-28T20:28 rows: method "Venue-truth fee attribution … " → `success`;
hypothesis "The delta-neutral cash-and-carry sleeve is net-positive after real venue fees at its
current 24h-min-hold conf…" → `failure`. Every EV verdict ever issued was computed against a cost
model that production has now shown can be wrong by 35% of allocation in one failure mode.

## 1. WHAT WE KNOW (validated strengths, each with proving command)

**K1 — Audit-finding response latency can be hours, when the fix is a write.** The prior sweep's
F2 (coverage contradicting finished work) was closed the same evening:
`.venv/bin/python scripts/research_memory.py coverage` → "AXIS COVERAGE: 20/20 converted (100%)"
(was 3 idle on 07-28); idle-axis, try_premium already-ruled note, and the micro result all carry
memory rows timestamped 20:28–20:29 (research_memory 133→140 rows). Turnaround ≈4.5h from sweep
to fix. The subsystem CAN close findings fast — which sharpens, rather than excuses, the
governor-repair failures in M1–M3.

**K2 — The Stage-A screening layer broadened to near-doctrine-compliance in one session.**
`data/stage_a_verdicts.jsonl` grew 6→32 verdicts (all 07-28; file mtime 20:28). Verdict rows now
carry the audited-harness power fields (`n_eff`, `powered`, `min_detectable_ic`, `residual_ic`,
`same_period_corr`), span horizons h1/h5/h20 (+block-scaled equivalents), three axes
(fred_macro 12, onchain_activity 8, crypto 6) and true panel cells (`panel_width` 80/78). Verdict
histogram: 22 SCREEN-UNDERPOWERED / 3 UNDERPOWERED / 2 SCREEN-NULL / 2 SCREEN-WEAK /
2 TIMING-ARTIFACT / 1 SCREEN-FLAGGED — zero false INTERESTINGs claimed. The de-contamination rail
caught VIX as coincident-not-leading (equity_vol_deleveraging h5b/h20b TIMING-ARTIFACT,
same_period_corr −0.18/−0.21) — the angle-20 artifact gate generalizing correctly to macro.

**K3 — The WALCL near-miss was handled exactly right, and is the best current lead.** R0031
(ledger): reserve_quantity_impulse h1b printed IC +0.1106, de-contamination PASSED (residual
+0.0964), momentum Sharpe 0.82 — cleared ic_min and sharpe_min, stopped ONLY by the power gate,
and the row itself corrects the n: a 4-week overlapping window sampled weekly ≈ 204 independent
obs (t≈1.6), not 815. Verdict text: "NOT an edge and NOT a clock … run a PRE-REGISTERED
NON-OVERLAPPING re-test." That is textbook honest screening under the two-stage law. (The re-test
has not run — see T2.)

**K4 — Live-edge decay monitoring exists and produces.** `data/signal_halflife_report.json`
(updated 07-28 08:35): stablecoin_supply ic_early 0.0828 → ic_recent 0.0410, trend −0.0418/window,
status **AGEING**, half-life ≈155 windows, with the full 41-point IC curve stored. Falsification
now covers LIVE signals, not only candidates — the "abandoned-idea reassessment" duty's inverse
(kept-idea reassessment) is an organ, not an aspiration.

**K5 — Production falsification of the desk's flagship sleeve, by its own instruments.** The
venue-truth fee attribution method (memory row 20:28, `success`) joined per-event COMMISSION rows
onto logged carry round-trips and proved the deployed carry config fee-negative; the churn-loop
fix shipped as commit 59b837d (R0018 `implemented`); the ruin rail then fired autonomously (F0).
Chain: measure → falsify → fix → rail. Painful, and exactly how the system is supposed to fail.

**K6 — Cross-era transfer is tested, not romanticized.** The Quantopian archaeology (52,187
threads mapped — mission row `success` 15:22) immediately produced a ported test: "Port Quantopian
In&Out risk-off rotation (pair-ratio bear signals gold/silver, XLU/XLI → rotate to safe leg)" →
`failure`, same day. Era-mining converts to counted trials at the full bar, per §33.

**K7 — The desk found its own zero-information gate, quantitatively.** R0030 (raised 20:31,
roi_bps 60): `stage_a_screen` requires n_eff ≥ (1.96/0.03)² = 4,268 independent obs for POWERED,
but n_eff date-caps for stacked panels — so the crypto lake (2,516 dates, mdi 0.039) and
fred_macro (~4,030 business days, BTC-capped) can NEVER produce a powered daily verdict, whatever
the signal. "A gate that rejects ~100% carries zero information" — the GATE-OPTIMALITY duty
executed on itself, with the correct instruction attached: fix the panel power calculation, do
NOT loosen the threshold.

**K8 — Novelty/graveyard discipline holds under temptation.** try_premium was queued for
re-screen and REFUSED with a rowed refusal (memory 20:29: "ALREADY RULED — NOT RE-TESTED THIS
RUN. docs/graveyard.md c…" → `failure` row, zero compute burned). Same organ, same evening,
honest UNDERPOWERED verdicts on 22 cells it did pay for.

## 2. WHAT WE DON'T KNOW (ignorance ledger)

**U1 — Whether the funnel can pass a good candidate (carried 3rd sweep, unmoved).** R0017 open;
probe files untouched since Jul 26 20:09 (`ls -la _audit_gate_probe*.py`). The synthetic arm still
realises SR −2.32 on an injected +0.5. All 115+ banked failures still carry the "or the
instrument ate it" discount. Highest info-gain item in the subsystem, 3 sweeps running.

**U2 — The EV gate's false-negative rate — now with its calibration anchor gone.** Carried from
both prior sweeps; materially WORSE today: the gate's known-good reference (carry EV 0.1171) was
computed gross of the venue-truth fees that just killed the sleeve. So the gate is (a) unaudited
— `ev_gate_audit.json` still 3 entries, latest 07-12, no append site in code (only a docstring,
`research_cycle.py:205`); (b) never shadow-tracked; and (c) now anchored to a falsified
reference. What the correct EV constants are, net of real costs, is unknown — but for the first
time the instrument to answer it exists (the fee-attribution join, K5).

**U3 — True Stage-B concurrency / Holm cohort (carried, unmoved).** `shadow_sleeves.json` → `[]`;
`run_alerts.py:241` `_standing = 6`; `stageb_capacity.json` recommends 5; law says 12. Four
numbers, no resolution, every live clock's eventual verdict still computed on an unverifiable m.

**U4 — Regime conditioning (carried, unmoved).** `ls data/crypto_regime_history.jsonl` → ABSENT
(R0006 open, day 3). Every day without the 3-line appender is another permanently lost regime
label — the only self-generated dataset the desk destroys daily by not writing it.

**U5 — Is the 62% BTC-timing generation mix a decision or a drift? (NEW, measured this sweep.)**
Of 121 hypothesis+construction memory rows, keyword classification gives **75 BTC-timing (62%),
25 cross-sectional (21%), 21 other** — against the principal's STANDING TARGETING ORDER
(generation_due.md, 2026-07-19 founders review #4): "All generate runs target CROSS-SECTIONAL
FACTOR FAMILIES — carry, momentum, basis (incl. cross-venue once Bybit data matures), and
vol/short-vol — ranked across the FULL perp universe. Single-name candidates enter only as
members of a cross-sectional rank." Classifier is approximate (keyword-based), but 3:1 against
the ordered direction is beyond labeling noise. No organ measures or reports generation mix, so
nobody decided this — it accreted. (R0030 gives one mechanical cause: the power gate punishes
panels hardest, quietly teaching organs that timing cells are "cheaper".)

**U6 — The entire scheduled-event information class is unmeasured while the desk owns the data
(NEW).** research_memory keyword sweep: unlock 0 rows, listing 0, expiry 0, month-end 0,
day-of-week 0, halving 0, settlement 2 (both venue-ops), weekend 1. Meanwhile
`data/unlock_events.json` (07-24, 5.2MB) holds **24,201 dated unlock events, 174 perp-matched
symbols, history to 2016, licence-cleared (DefiLlama, charter §13 pass), with pct_max/pct_circ
and category (team/publicSale/…) fields** — idle 5 days, zero screens, zero rows, in direct
violation of SCREEN-ON-DISCOVERY. `data/listings.jsonl` (5 events since 07-24, with
funding_at_detect) accrues correctly but is fed by no hypothesis. The missing event-study harness
(R0007, open day 3) and the idle event datasets are one compound gap: the desk cannot ask "do
scheduled supply events price in?" — crypto's most literature-documented cross-sectional anomaly
family — despite having bought (free) the data twice.

**U7 — The epistemic status of `funding_persistence.json`'s "ENTRY SIGNAL WORKS" verdict (NEW).**
`data/funding_persistence.json` (07-27): 36 symbols × 160 periods, persistence IC 0.4322
(t 29.66), top-decile funding annualized +29.1% vs median +3.8% — "ENTRY SIGNAL WORKS". Zero
research_memory rows (LIKE '%funding_persistence%' → 0), zero pre-registrations, no multiplicity
accounting, not in any clock registry. It fed the (now-dead) carry sleeve's leg selection. As a
research object it is an untracked positive claim — the exact write-site bypass yesterday's sweep
documented for negatives, now on a POSITIVE result, where the cost of amnesia is losing a found
edge rather than re-running a null.

**U8 — Whether audit cadence above closure capacity has positive marginal ROI (NEW, meta).**
Three alpha-discovery deep sweeps ran in 4 days (07-26, 07-28, 07-29) totalling ~1,470 report
lines, while governor-closure throughput over the same window is ZERO (M1–M3 all unmoved;
ledger: 27 open / 32, 0 dispositions in the last 24h vs 8 new rows raised). This sweep's marginal
novel content vs yesterday's is real but thin outside the incident and the new seams — the
finding-generation:finding-closure ratio is running ≈∞. Unknown: whether the next sweep at this
cadence buys anything a closure day would not buy more of.

## 3. WHAT COULD MATTER MOST (ranked opportunities)

Ranked by expected impact × confidence / (cost × maintenance). ★ = compounding multiplier.
The 07-28 sweep's diagnosis stands and hardens: the binding constraint is **disposition of
already-found defects**, not discovery of new ones. This sweep adds two genuinely new alpha
surfaces (R2, R3) that are also the cheapest route back into compliance with the standing
cross-sectional order.

**R1 ★ — CLOSE THE THREE GOVERNORS (carried 3rd time; now with a changed EV anchor).** Same
work-item as the prior sweep's R1 (positive-control repair R0017 + campaign-gate scoping R0016 +
EV recalibration R0023 + append-at-write-site for `ev_gate_audit.json`) with one amendment forced
by F0: **the EV recalibration must use the venue-truth fee attribution join (K5) as its cost
input, and the carry anchor must be re-scored net-of-realized-fees before it anchors anything.**
Evidence of urgency beyond yesterday's: the anchor itself failed in production; 17 days of
verdicts missing from the audit ledger; R0016/R0017/R0023 cross the §41 7-day bar on 08-02.
Everything else in this subsystem inherits meaning from these three instruments. Complexity:
low-medium, all code on disk. Confidence 0.85. If only ONE thing happens before the next sweep,
it is this. *Failure mode of NOT doing it: the desk's honest-bar reputation with itself decays —
three sweeps, three self-findings, zero repairs teaches organs that findings are decorative.*

**R2 ★ — SCREEN THE UNLOCK AXIS AND BUILD THE EVENT-STUDY HARNESS AS ONE DELIVERABLE (new).**
- *Exactly what:* one script: panel event study on `data/unlock_events.json` (24,201 events, 174
  perp-matched symbols) over the bronze crypto lake — abnormal return vs 80-perp panel in
  event-time windows (−10..+10d), split by `category` (team/VC vs publicSale) and unlock size
  (`pct_circ_now` buckets), Stage-A bar, block-bootstrap power fields, every cell rowed at write
  site. Generalize the window/abnormal-return core into the event-study harness R0007 already
  specifies — listings (`data/listings.jsonl`), funding-boundary (T6), and airdrop calendars
  (FREE_DATA_ADDENDA item 72, which already says "same event-study pipeline as unlocks") then
  reuse it.
- *Why:* (a) mechanism-first: scheduled forced supply is adjacent to the board's two ALIVE
  families (M_STRUCTURAL_BARRIER, M_FORCED_DELEVERAGE) and is NOT in any killed family
  (M_FLOW_PRESSURE's kills were order-flow constructs); (b) it is cross-sectional by nature —
  first new candidate family fully aligned with the standing targeting order; (c) the data is
  owned, licence-cleared, and 5 days idle in violation of SCREEN-ON-DISCOVERY; (d) event-time
  n_eff does NOT date-cap the way daily panels do (24,201 events are the observations, not 2,516
  dates) — it dodges the exact power hole R0030 documents.
- *Evidence:* `python3` read of unlock_events.json (fields shown in U6); memory sweep: unlock →
  0 rows ever. *Complexity:* ~1 day. *Dependencies:* none (lake + file). *Validation:* placebo
  events (random dates) must show no effect; category split must behave sanely. *Failure modes:*
  event-date error in source (DefiLlama forward-shifts) — guard: verify 5 known unlocks by hand;
  survivorship in perp matching (delisted tokens absent) — state it. *ROI:* highest new-alpha
  item on the board. *Confidence:* 0.7 on executing clean; 0.3 on finding a live edge (the
  anomaly is documented, which also means partially crowded — measuring the residual IS the
  finding). *Retirement:* harness never retires; unlock verdict stands either way.

**R3 — MAKE GENERATION MIX A MEASURED, REPORTED QUANTITY (new).** One function in the generation
path: classify each new hypothesis row {cross-sectional | timing | other} × {mechanism family} ×
{horizon}, report the running mix vs the standing order every cycle, and alert when timing share
exceeds an explicit ceiling. Zero new bars, zero vetoes — telemetry only. *Why:* U5 — a 3:1
drift against a standing principal order accreted invisibly because nothing measures it. This is
the cheapest steering instrument the subsystem lacks. *Complexity:* trivial. *Confidence:* 0.9.
*Interaction:* R0030's panel-power fix removes the mechanical incentive currently pushing organs
toward timing cells; do both.

**R4 — ROW THE POSITIVE STRAYS: funding_persistence + WALCL + funding-spread (new).** Three
positive-shaped results currently live outside every ledger: `funding_persistence.json` (U7 —
"WORKS", no rows), R0031's WALCL near-miss (in the rec ledger but not research_memory), and the
never-screened precomputed `spread` column in `hyperliquid_funding.parquet` (232 coins, 16,668
rows since 06-26 — yesterday's negative-space item turns out to be an idle COMPUTED column, not
missing data). One hour of rowing + one pre-registration each. *Why:* untracked positives are
lost edges; untracked "needs-more-n" verdicts without accrual clocks are U8-class rot (prior
sweep's R6). *Confidence:* 0.9.

**R5 — Slot-cohort truth (carried unchanged from prior R2b/T3).** Populate `shadow_sleeves.json`
from the real inventory, delete `_standing = 6`, reconcile 12-vs-5 in writing. Unmoved for 3
sweeps; every day of delay keeps every clock's Holm bar unverifiable.

**R6 — Regime-history 3-liner (carried; R0006 day 3).** Start the append. Each day unwritten is
a day of regime labels destroyed at source — mining-never-regresses applied to self-generated
state.

**R7 — Fix panel n_eff per R0030, or publish per-axis detection floors.** The desk's own text
has the right design ("n_eff should not be date-capped when breadth is real; do NOT loosen the
threshold"). Without it, every future panel screen — including R2's — mis-states its power.

*Explicitly NOT recommended:* any Stage-B bar change; re-testing graveyarded price-family
constructions (novelty gate is working — K8); new sweeps of this subsystem before ≥2 governor
closes land (U8 — the next marginal token belongs to closure, not discovery-of-defects);
paid data (nothing above costs a dollar).

## 4. WHAT WE TEST NEXT (concrete experiments)

**T1 — Unlock event study (from R2).** Hypothesis: perp-matched tokens show negative abnormal
returns into/at large unannounced-fraction unlocks (team/VC > publicSale), vs the 80-perp panel.
Method: event-time panel study, −10..+10d, category × size buckets, placebo-controlled, Stage-A
bar, every cell rowed. Success: any cell POWERED at |IC|≥0.03-equivalent with sane placebo →
pre-register a Stage-B construction. Null: the class dies with receipts and the harness remains.
Data: on disk. Cost: ~1 day.

**T2 — WALCL non-overlapping re-test (R0031's own prescription).** Pre-register: weekly
non-overlapping 4-week reserve-impulse windows, h5b, exact construction frozen from
`fred_macro_screen.json`, n≈204 independent obs, decision rule stated BEFORE running
(|t|≥2 → pre-register forward clock; else the axis's 7th and final rejection). Data:
`data/fred_macro_deep.json` (on disk, 07-28 20:27). Cost: hours.

**T3 — Funding-spread first construction (from R4).** Pre-register on the young data honestly:
cross-sectional rank of |hl−bn funding spread| → next-period relative return, expect
UNDERPOWERED at 33 days, so pair the screen with an accrual clock declaration (the R5/R6 pattern
from the prior sweep: "needs more data" verdicts must start accrual or say why not). Cost: hours.

**T4 — Positive-control matrix (carried 3rd time, R0017).** Unchanged spec from prior sweep's
T1. Still the highest info-gain experiment on the board. Still zero code moved.

**T5 — Resurrection batch 1 + micro-feature batch (carried; both still owed).** M5 failed 0-for-2
this sweep: `research_memory` LIKE '%resurrect%' → 0; feature_library still lists the same 5
`computed_unused`. Both were fully specced yesterday (its T4/T5). No new spec needed — only
execution.

**T6 — Funding-settlement boundary event study (carried 3rd time — now cheap).** After T1, this
is a parameter change on the same harness (events = 8h funding timestamps). Third consecutive
sweep recommending it; if it is not started by the next sweep, row a dated deferral or a reasoned
rejection per §41 — continued silence on a twice-free experiment is itself a defect.

**Success metrics for the next sweep to re-measure (pre-registered):**
1. R0016/R0017/R0023 dispositioned before their 08-02 §41 bar (M-metric: ledger status ≠ open).
2. EV anchor re-scored net-of-fees; `ev_gate_audit.json` ≥ 20 entries with an in-code append site.
3. Unlock event study artifact exists with placebo control; its cells rowed at write site.
4. Generation-mix telemetry reports a number in a cycle artifact; timing share stated vs order.
5. `shadow_sleeves.json` non-empty AND `_standing` hardcode deleted (same test as yesterday).
6. WALCL re-test verdict on disk, whichever way it lands.
7. Working tree ≤ a day stale: the 07-28 20:26 session (87 files) committed or explained.

## APPENDIX A — six-perspective findings log (raw, evidence-first)

### A1 INTERNAL (measured, not configured)
1. **Disposition throughput is measurably zero while the raise rate runs ~8/day.** Ledger 24→32
   rows in 24h (R0025–R0032, all raised 07-28 20:26–20:31), dispositions in the same 24h: 0. Open
   rows: 27/32 (14 from 07-26, 13 from 07-28). The three implemented rows ever (R0014/R0018/R0021)
   are all execution-side crisis fixes; discovery-side governors are 0-for-3-sweeps. The system's
   introspection organ works; its hands do not reach its own gates.
2. **Output of the 07-28 20:26 session exists only as an uncommitted working tree.** `git status
   --short | wc -l` → 87 files; `git diff --stat` → +940/−278 across 76 files, including the
   ledger's 8 new rows, `stage_a_executor.py`'s broadening, and `generation_due.md`'s honest
   fred_macro postmortem. Last commit remains 3db47ef (07-28 15:26). Under §33's own words this
   output "did not happen" — and a crash tonight would make that literal.
3. **Positive results bypass the ledgers the way negatives used to (funding_persistence, U7).**
   The write-site fix pattern (K1) was applied to the artifacts yesterday's sweep NAMED, not to
   the CLASS — `funding_persistence.json` (07-27, "WORKS") still has zero rows. Adjacency move
   (proactive battery #2) not run on the fix.

### A2 EXTERNAL (how another world-class team would improve this)
1. Event studies are a day-one harness at any equities/crypto quant shop (earnings, index
   rebalance, lockup expiry are THE canonical cross-sectional anomalies); this desk built
   collectors for two event classes (unlocks, listings) before building any event-time harness.
   The R0007 gap would be considered an architecture omission, not a backlog item.
2. A research manager function is missing: 27 open findings with named fixes and no owner-dates.
   A serious shop runs a daily triage that DISPOSITIONS (build/reject/schedule) faster than it
   raises, or stops raising. §41 specifies exactly this and is not being executed to its own 24h
   standard.
3. Credit: per-verdict power fields (`n_eff`, `min_detectable_ic`) emitted by a screening layer
   is ABOVE most professional practice, as is refusing an in-house re-test on graveyard grounds
   with a logged refusal (K8).

### A3 FUTURE (2–3y redesign pressure)
1. Event-indexed data is the direction of travel (bar-time → event-time): unlocks, listings,
   funding boundaries, governance votes, ETF creations all share one join shape. Building the
   event-study core now (R2) is the cheapest possible down-payment on that architecture.
2. Generation-mix telemetry (R3) anticipates LLM-era fleets: when hypothesis generation is nearly
   free, the scarce resource is ALLOCATION of trials across families/targets — a desk that cannot
   measure its own mix cannot steer a fleet of generators. The mechanism board already does this
   for families; targets/horizons still have nothing.

### A4 CONTRARIAN (test the core assumptions)
1. **"Carry was proven edge" — production says the deployed CONFIG wasn't.** The two-limits
   doctrine sizes on "proven edge", where proof came from gross-of-realized-fee arithmetic. F0
   shows proof must be net-of-venue-truth at the deployed parameterization (24h-min-hold churn is
   what died, not the funding-harvest thesis, whose isolated P&L was +2.26%). Consequence tested
   and real: EV verdicts (U2) and every future promotion inherit the corrected standard. This is
   the sharpest possible reminder that "PROVEN" is a property of a strategy×config×venue triple,
   not of a thesis.
2. **"More sweeps = more discovery" fails its own compounding test at current closure rate (U8).**
   Three sweeps/4 days re-found the same three governors unfixed. JUDGE-EVERYTHING-BY-COMPOUNDING
   applied to this audit: sweep #4 at this cadence has lower expected value than one closure
   session; the correct next investment is R1, not another 500-line report. (This report
   therefore front-loads closure-shaped deliverables: pre-registered specs T1–T3 executable in
   hours each.)
3. **"BTC-timing concentration is wrong" — steelman checked and rejected.** Steelman: BTC is
   where liquidity/capacity is, so timing-BTC candidates deserve overweight. Rejected on the
   desk's own record: the standing order (07-19) explicitly mandates cross-sectional families for
   capacity reasons; the price-family campaign (420/0) and four family-kills are precisely the
   exhausted BTC-timing space; and the only currently-live positive artifacts (funding
   persistence selection, kimchi/stablecoin clocks, WALCL near-miss) are 3-of-4 NOT
   next-day-BTC-timing shapes. The 62% is drift, not thesis.

### A5 GREENFIELD (rebuild-from-scratch score)
1. A greenfield discovery stack from today's validated knowledge = the two-stage law + audited
   screen harness + mechanism board + novelty gate + ONE write-site ledger + ONE clock registry +
   an event-study core — plus the halflife monitor on everything live. Roughly 70% of that
   exists; the missing 30% (ledger unification, registry, event core) is all bookkeeping-shaped
   and estimated ≤3 days of work total. Baggage score: moderate, unchanged in 24h; nothing new
   accreted (the 20:26 session reused existing shapes — good).
2. Keep-list confirmation from production: the deadman rail chain (K5/F0) survives greenfield
   scrutiny untouched — it is the one subsystem that has now repeatedly proven itself by OUTCOME.

### A6 FRONTIER (recently possible, unexploited)
1. **Owned-and-idle beats new-and-shiny this week:** unlock_events.json (24,201 events, 5 days
   idle — R2), hyperliquid_funding.parquet's precomputed cross-venue spread column (33 days
   accruing, never screened — T3), listings.jsonl (accruing, correct), 8btc_era_thread_catalog
   .jsonl + Quantopian corpus (converting, K6). The frontier duty this sweep is conversion, not
   acquisition — consistent with mined-to-wired.
2. **Bybit second venue: healthy and nearly "matured" with no maturity definition.** Heartbeat
   fresh (01:10), `du -sh data/moat/bybit` → 4.2GB, 20 symbols × hourly gzip since 07-21 (185
   files/symbol, current to 01:10) — my initial "green-heartbeat-zero-output" suspicion was
   checked and is FALSE (log is empty because output goes to per-symbol gzip). The standing
   order's cross-venue basis family is gated on "once Bybit data matures" with no threshold
   written anywhere — an undated deferral in spirit. Define it (e.g., 30 venue-days) so the
   family auto-arms.
3. Carried, still true, still free: CFTC crypto COT uncollected (3rd sweep); Deribit SOL/XRP
   absent (`deribit_surface.parquet` → 72 rows, {BTC:36, ETH:36}, 3rd sweep); prediction-market
   collector absent (U8 of prior sweep; no new commits since — `git log` empty past 3db47ef).

## APPENDIX B — negative-space sweep (never asked / collected / tested)

- **Questions never asked, found by keyword sweep over all 140 memory rows + graveyard:**
  halving-cycle conditioning (0 mentions ever, in a market defined by a 4-year supply cycle);
  day-of-week/weekend structure (1 mention); options-expiry effects (0); month/quarter-end
  rebalance flows (0); ETF options (IBIT options listed Nov 2024 — 0 mentions, no surface
  collector); listing-day funding dynamics (data accruing since 07-24, no hypothesis row).
- **Questions now askable that weren't yesterday:** "does the desk's generation mix match the
  standing order?" (U5 — measured here for the first time; answer: no, 3:1 against); "is any
  positive result untracked?" (U7 — yes, at least one).
- **Data collected but never researched (delta vs prior sweep):** unlock_events.json (NEW to the
  list — 5 days), hyperliquid_funding spread column (NEW — 33 days), fred_macro_deep.json (1 day,
  already has a pre-registered consumer waiting: T2 — acceptable), Bybit moat (8 days, blocked on
  an undefined "matured"). Cleared from yesterday's list: none (own-fills replay, cot_zcache,
  liquidations-tick studies all still unread — carried).
- **Signals untestable for missing data:** unchanged from prior sweep (HL userFills cap, pre-2026
  L2 depth, prediction-market entry prices). One reclassification: cross-venue funding dispersion
  moves OUT of this category — the data existed all along with the spread precomputed (T3).
- **Failure modes never simulated:** unchanged — no candidate-stage regime stress, no planted-
  noise negative control for the screen layer. Both carried findings; neither moved.
- **Empty seams checked and found genuinely empty this sweep:** memory rows for 'resurrect' (0 —
  M5 fail, not an oversight in my search), research-shaped consumers of `listings.jsonl` (grep
  scripts/ → collector only), any maturity threshold for Bybit anywhere in docs/ (grep 'matur'
  in BYBIT_SECOND_VENUE_SPEC.md → absent), any event-study artifact (R0007 consumers → none).

## APPENDIX C — commands run (audit trail, all read-only)

Every finding above cites its command inline. Key ones, in run order:
- `git log --oneline --since=2026-07-28T12:00` / `git log -1 --format='%ci %h'` → last commit
  3db47ef 07-28 15:26; zero commits since. `git status --short | wc -l` → 87; `git diff --stat`
  → 76 files +940/−278 (mostly 07-28 20:26–20:32 mtimes).
- recommendation_ledger.json → 32 rows {open 27, implemented 3, scheduled 1, rejected 1}; new
  R0025–R0032 all 07-28T20:26–20:31; R0016/R0017/R0023 open; full texts of R0030/R0031.
- `cat data/CASHCARRY_KILL` → deadman fire 2026-07-29T01:04:23Z (during sweep);
  `deadman_state.json` → fired true, breaches 163; `INCIDENT_20260727_DEADMAN6.md` → fee-fire
  table (commission −35.01% vs thesis −2.19%).
- `.venv/bin/python scripts/research_memory.py coverage` → 20/20 (100%). research_memory: 140
  rows; by-day {07-28: 14}; all 14 listed with categories/results; keyword counts (unlock 0,
  listing 0, expiry 0, halving 0, weekend 1, resurrect 0, funding_persistence 0).
- `data/stage_a_verdicts.jsonl` → 32 rows, verdict/horizon/axis/panel_width histograms; all 12
  fred_macro cells printed (WALCL h1b ic 0.1106 n 815 n_eff 116.4 powered False).
- `data/ev_gate_audit.json` → 3 entries latest 07-12; grep append-site → docstring only.
- `shadow_sleeves.json` → `[]`; `run_alerts.py:241` → `_standing = 6`; stageb_capacity.json vs
  TWO_STAGE_DISCOVERY_LAW.md:27. `ls data/crypto_regime_history.jsonl` → absent.
- `data/axis_shadow_state.json` → 4 axes, updated 07-28T12:21 (kimchi cum −4.0% nw_t −1.1;
  stablecoin +2.5%); daily cycle cron 02:00 confirmed via `crontab -l` (no missed tick — sweep
  ran at 01:00).
- unlock_events.json → keys, 24,201 events, 174 perp_matched, sample row 2016, licence note;
  docs grep 'unlock' → zero research references (only growth-ladder homonyms + ADDENDA item 72).
- `data/funding_persistence.json` → full verdict JSON; hyperliquid_funding.parquet → (16668, 5)
  cols [timestamp, coin, hl_funding, bn_funding, spread], 232 coins, 06-26→07-29, |spread| mean
  0.65bps/8h max 133bps.
- `data/signal_halflife_report.json` → stablecoin AGEING half-life 155w with 41-point IC curve.
- mechanism_board.json → deaths + verdicts (2 ALIVE, 4 FAMILY KILL, M_LIQUIDITY_WITHDRAWAL
  UNTESTED); feature_library.json → 9 features / 5 unused / 447 proposals (unchanged).
- Target-mix measurement: sqlite over 121 hypothesis+construction rows → {btc-timing 75,
  cross-sectional 25, other 21}; STANDING TARGETING ORDER quoted from generation_due.md.
- Bybit: `run_recorder_bybit.py:30` → data/moat/bybit; `du -sh` → 4.2G, 20 symbols, 185 hourly
  files/symbol, newest 01:10. deribit_surface.parquet → (72,6) {BTC:36, ETH:36}.
- fred_macro_deep.json / fred_macro_screen.json → on disk 07-28 20:27 (T2's inputs ready).
