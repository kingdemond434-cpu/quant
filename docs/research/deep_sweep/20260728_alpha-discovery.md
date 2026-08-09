# DEEP COLD AUDIT — ALPHA-DISCOVERY SUBSYSTEM — 2026-07-28

_Auditor: weekly deep cold audit (doctrine v2 + exhaustion mandate 2026-07-28). Scope: hypothesis
diversity, unexplored behaviors, crowded themes, neglected regimes, cross-asset transfer,
temporal-resolution gaps, feature interactions, regime-conditioned hypotheses,
causal-vs-correlational, redundancy, negative-result reuse, abandoned-idea reassessment,
falsification quality, ignored markets, untestable-for-missing-data signals. READ-ONLY.
Prior sweep: 20260726_alpha-discovery.md (2 days ago) — this sweep re-measures its 5 declared
success metrics, audits follow-through on its R1–R6/T1–T5, then digs seams it did not reach._

## SCORES (headline)

- current_capability_pct: **58%** (up from 45% on 07-26). The generation/diversity half of the
  subsystem improved sharply in 48h — cross-asset sweep executed (93 construction rows), trader-split
  program executed and killed with reference-quality falsification, the moat got its first research
  read, and four new instruments landed (mechanism board, resurrection engine, feature-construction
  grammar, HL behavioural factory). The *governing* half did not move: the EV gate constants,
  multiplicity ledger, and slot/cohort accounting are all unchanged despite being named on 07-26 and
  independently re-found by the desk's own organs 2–3 times since.
- practical_ceiling_estimate: **85%** unchanged (existing data + existing harness, no new spend).
- ceiling_gap: **~27 points**, now concentrated in three governors (EV gate, multiplicity/ledger
  unification, slot-cohort truth) plus the slow-horizon power hole — all closable with code on disk.
- opportunity_cost_1y: (i) EV-gate false negatives continue accruing — 3 more mechanism-carrying
  hypotheses auto-rejected on 07-28 by arithmetic two sweeps have called broken; (ii) the desk cannot
  state its own Stage-B occupancy (4 numbers in circulation: 12/6/5/3), so clock-throughput — its #1
  bottleneck — is unmanaged in BOTH directions; (iii) 447 enumerated-but-untested constructions and 5
  computed-but-unused microstructure features sit idle on owned data; (iv) with the synthetic
  positive control broken (R0017), the funnel's false-negative rate is unmeasurable, which silently
  discounts every negative result the factory produces.
- confidence: **0.8** on INTERNAL findings (command-verified); 0.5 on opportunity sizing.
- unknown_unknown_score: **0.5** (down from 0.6 — the moat was probed and the 420/0 mechanics are now
  understood via R0016). Residual concentration: (a) funnel end-to-end FN rate (no working positive
  control), (b) regime-conditioning of every live clock (still one-regime history, no regime-history
  artifact), (c) whether the coverage/memory instruments under-report other finished work the way
  they under-report the idle-axis screens.
- info_gain_if_investigated: highest = repair the synthetic positive control (R0017) — it calibrates
  the ENTIRE funnel and re-prices every past and future negative; second = EV recalibration (R0023);
  third = desk-wide Holm cohort enumeration.
- expected_alpha_contribution: direct — resurrection queue's 2 priority-5 + 8 priority-3 candidates
  (horizon/regime re-tests of weaker-court kills) and the 5 ready-to-screen micro features are the
  nearest-term Stage-B feeders; indirect — a working positive control converts the 115 banked
  failures from "probably null" to "measured null", raising the value of every past experiment.
- expected_compounding_contribution: feature_library's construction grammar (447 counted untested
  cells) makes negative space enumerable — the first artifact that turns "keep exploring" into a
  countable frontier. Write-site ledger unification (R2 below) makes every future audit and every
  future DSR honest at zero marginal cost.
- CEILING EXPANSION: the 85% ceiling still assumes the funnel's own verdicts are trustworthy. The
  binding assumption is now **methodological, not organizational**: until a known-good synthetic
  passes end-to-end, "85% of ceiling" is measured with an uncalibrated instrument. Fixing R0017
  could move the ceiling in either direction — if the funnel is shown to pass good candidates, the
  ceiling holds; if it cannot, every historical null inflates the graveyard and the true ceiling is
  higher than estimated (edges killed in-funnel, recoverable by resurrection).

## 0. RE-MEASUREMENT OF THE 07-26 SWEEP'S DECLARED SUCCESS METRICS

The 07-26 sweep pre-registered 5 metrics for this sweep. Verdicts, each with its command:

**M1 — EV-gate accept rate enters (0%,100%) exclusive: FAIL.**
`grep -n "_BASE_P\|_EV_THRESHOLD\|effort_h" libs/research/alpha_economics.py` → `_BASE_P = 0.15`,
`_EV_THRESHOLD = 0.05`, `effort_h: float = 8.0` — constants unchanged; no commits touch the file
(`git log --since=2026-07-25 -- libs/research/alpha_economics.py` → empty). Since 07-26 the gate
scored 3 more mechanism-carrying DeFi hypotheses: 3/3 REJECT (EV 0.0085/0.0063/0.0082 vs 0.05,
commit 3db47ef). Lifetime: 1 QUEUE (never built) / ≥20 verdicts. `data/ev_gate_audit.json` still
holds **3 entries dated 07-04/07-11/07-12** — neither the 07-22 batch of 11 nor the 07-28 batch of 3
was appended, so the gate's feedback ledger has now missed **14 consecutive verdicts** after the
miss was named in the prior sweep. The desk itself re-found the miscalibration twice (R0016 gate
probe 07-26, R0023 generation cycle 07-28, roi_bps=30) — both rows still `open`.

**M2 — Stage-B occupancy ≥10/12: UNMEASURABLE, which is worse than a miss.**
Four incompatible numbers now govern the desk's #1 bottleneck: the law says 12
(`TWO_STAGE_DISCOVERY_LAW.md:27` `MAX_FORWARD_SLOTS = 12`); `run_alerts.py:241` hardcodes
`_standing = 6` + an empty registry (`cat data/shadow_sleeves.json` → `[]`); the new
`scripts/stageb_capacity.py` (commit fbedf2b, 07-27) derives **5** from a Holm-bar rule of thumb;
`data/axis_shadow_state.json` runs 4 axis clocks with `m_concurrent: 4` (its own file only).
`data/stageb_capacity.json` reads `running: 3` — stale AND counted on a cohort that excludes the 6
standing sleeves its own alert counts. The prior sweep's U7 (fragmented Holm cohort) got *worse*: a
new artifact published a capacity recommendation using yet another cohort definition.

**M3 — ≥1 non-daily-bar family carries a counted trial: PASS.**
(a) HL 4h behavioural/flow screens are graveyarded with full evidence (`tail docs/graveyard.md`:
smart_dumb_divergence 4h n=180 bars; hl_elite_directional_order_flow 4h buckets). (b) The moat's
first research read ran at 1s→hourly: `data/micro_features.json` (07-27 18:21) — lead-vs-coincident
liquidity-withdrawal study, 5 symbols × 35h. Caveat: the micro result has no verdict row anywhere
(`research_memory` LIKE '%liquidity_withdrawal%' → 0 rows) and the mechanism board still lists
M_LIQUIDITY_WITHDRAWAL as UNTESTED while the first evidence sits in its JSON.

**M4 — trials_ledger row count > 0: FAIL.**
`SELECT COUNT(*) FROM trials_ledger` → **0, 0, 0, 0** across sor_crypto / sor_autodiscovery /
sor_research / sor_research_lake_v2 (also 0 in alpha_registry.sqlite). Mitigation that is real but
partial: `research_memory` in sor_research.sqlite went from 0-ever (pre-07-24) to **133 rows**
(93 construction, 23 hypothesis, 8 method, 7 dataset, 2 mission; 115 failure / 14 success /
4 pending) — the spirit of trial-logging lives in a different, non-hash-chained table, and at least
two artifact classes bypass even that (21 idle-axis cells, 6 stage-A executor verdicts).

**M5 — ingested-axes-without-screen-verdict = 0: PASS (with one instrument defect).**
The 07-26 01:00 batch wrote 93 construction rows covering equity(12)/index(11)/energy(10)/metal(9)/
mining(3)/wikipedia(2)/fx(2)/binance-metrics M1–M5; memory rows exist for etf(7), fed(11),
crossasset(11), futclose(3), cme(14). The 3 remaining axes (crypto, try_premium, onchain_activity)
were screened 07-26 20:50 through the audited harness — 21 pre-registered cells in
`data/idle_axis_screen.json` (20 UNDERPOWERED / 1 INTERESTING) with novelty-gate checks and declared
alignment. **Defect:** those 21 cells were never rowed, so `research_memory.py coverage` still
reports the three axes as idle — the instrument contradicts the artifact 2 days later (see F2).

**Net:** 2 PASS, 2 FAIL, 1 UNMEASURABLE. Everything that passed was *new experimental work*;
everything that failed was *governor repair*. The subsystem generates and falsifies at a high and
rising standard; it is not yet closing the loops it discovers around its own gates and ledgers.

## 1. WHAT WE KNOW (validated strengths, each with proving command)

**K1 — Falsification quality reached reference grade this week; the trader-skill program should be
the desk's template.** Five graveyard entries since 07-26 (`git log --since=2026-07-26 --
docs/graveyard.md` → 5 commits) executed the full adversarial toolkit: gapped-window control
(hyperliquid skill persistence: adjacent-window ρ +0.120 t +10.9 FLIPS to −0.064 t −5.8 with a
3-week gap — the apparent persistence was position overlap, not skill), cohort-perturbation
stability (elite directional flow: +60 traders on the same rule inverted BTC IC sign → killed as
`unstable_artifact`), circularity-trap avoidance (cohorts selected on turnover, never performance),
safe-direction bias notes (leaderboard survivorship biases persistence UP, so true ≤ −0.064), and a
kept partial exception (drawdown-control persistence ρ +0.135 t +2.05, correctly NOT promoted —
below the 4-test multiplicity bar). The prior sweep's R4 (trader split) was executed and honestly
killed: smart_dumb_divergence pooled IC +0.0032, t +0.15 → `no_edge`.

**K2 — Mechanism-level knowledge is now an artifact, not a narrative.** `data/mechanism_board.json`
(updated 07-28 08:35): 9 mechanism families with death counts, 4 FAMILY KILLS (M_PRICE_PATTERN 22
deaths, M_ATTENTION_DELAY 13, M_SKILL_PERSISTENCE 7, M_FLOW_PRESSURE 6), 2 ALIVE
(M_FORCED_DELEVERAGE, M_STRUCTURAL_BARRIER), M_LIQUIDITY_WITHDRAWAL rated the only untested family
with a live information advantage — and `scripts/micro_factory.py` was built to test exactly it,
mechanism-first, around the lead-vs-coincident question that killed 38% of prior hypotheses
(C_WRONG_TIMING). Hypothesis targeting is now steered by measured family mortality.

**K3 — Abandoned-idea reassessment exists and is principled about the graveyard.**
`scripts/graveyard_resurrect.py` (07-27) classifies all kills by cause-of-death and ranks only
those judged by *weaker courts* (killed before the 07-23..27 rails: gapped-window,
cohort-perturbation, power reporting, SUSPECT-LOOKAHEAD). `data/graveyard_resurrection_queue.json`:
42 entries — 2 priority-5 (defi_health, multilingual_wikipedia: "killed at DAILY horizon only.
Horizon search is the exact remedy"), 8 priority-3 (regime_artifact / costs_killed_edge classes),
11 priority-0 correctly marked DEAD (no_economics). It resurrects nothing itself — it queues
evidence-driven re-tests at the full bar. This threads the sacred-graveyard needle correctly:
re-testing at the gauntlet bar with NEW rails is pushing, not re-litigating.

**K4 — The negative space is now countable.** `data/feature_library.json` (07-28): 9 features
registered, 5 computed-but-unused, and a construction grammar (OBSERVABLE × TRANSFORM × WINDOW ×
NORMALISATION) enumerating **447 untested proposals**. Born from a named waste event: micro_factory
computed 6 state variables over 4.4GB, tested 1 construction, discarded all 6. "What have we never
tested" is now a query, not a meditation.

**K5 — The novelty gate works in production.** Commit 3db47ef (07-28): the gate blocked an
exchange-netflow re-screen BEFORE compute — the class is dead on the record (cm_netflow IC −0.0075
SCREEN-WEAK n=5,549; MVRV TIMING-ARTIFACT). `data/idle_axis_screen.json` `novelty_gate` block:
3 candidates scored (taker_flow_absorption novelty 0.869 vs nearest prior sleeve:taker_flow 0.131)
before screening. Redundant hypotheses are being caught at the door in at least two organs.

**K6 — Research memory went from null pipe to live organ.** `SELECT COUNT(*) FROM research_memory`
(sor_research.sqlite) → **133 rows** spanning 07-24→07-28, 115 of them failures — negative results
dominate, which is the honest shape. Datasets, missions, methods, constructions all logged with
failure causes. (Gaps remain at two write sites — see F2.)

**K7 — Screen-on-discovery held for the newest axis.** The CFE regulated-futures complex was
carded by the EN miner and screened THE SAME DAY (`data/cfe_regulated_basis_screen.json`, 07-28):
pbt_funding_prem h1d n=204 → SCREEN-UNDERPOWERED with min_detectable_ic reported; honest
INSUFFICIENT-DATA at h5d. Verdicts carry power fields (`n_eff`, `min_detectable_ic`, `powered`) —
the power-reporting rail is live in the audited harness (also visible in the re-run
`batch_coinmetrics_screen.json` with external price verification and declared UTC alignment).

**K8 — Stage-A now has an executor; ranking is no longer mistaken for utilisation.**
`scripts/stage_a_executor.py` wired into `daily_research_cycle.py:61` and RAN (6 verdicts in
`data/stage_a_verdicts.jsonl`, 07-28 12:18), applying the validated 7-check leakage contract
(`scripts/leakage_detector.py` — tested against synthetic ground truth: planted leak, pure noise,
genuine weak signal). Its first catch was correct: `onchain_metrics:fees_usd` flagged
CONTEMPORANEOUS ("this is not a predictor of the quantity, it IS the quantity"). Design defects in
what it screens and how it targets are real (F3) — but the execution loop exists and drains.

**K9 — Cross-asset transfer was tested, not assumed.** The 07-26 01:00 batch put 93 constructions
through screens across equity/index/energy/metal/mining/fx/wikipedia plus binance-metrics M1–M5
(`SELECT category='construction' GROUP BY day` → {2026-07-26: 93}); all failures, all rowed. The
cross-asset daily-timing transfer question is now CLOSED with evidence, freeing attention — exactly
what the prior sweep asked (its T2), one day after it asked.

## 2. WHAT WE DON'T KNOW (ignorance ledger)

**U1 — Whether the discovery funnel can pass a genuinely good candidate end-to-end. The positive
control is broken.** R0017 (open, 43h): the gate-optimality probe's synthetic arm injects
SR_true=+0.5 and realises SR=−2.32 (+1.0 → −1.76) — sign-inconsistent with its own injection, so
the synthetic sweep cannot answer the funnel's single most important calibration question. Until a
known-good synthetic passes the gauntlet, every one of the 115 banked failures carries an
unquantified "or the instrument ate it" discount. This is the sharpest unknown in the subsystem.

**U2 — The EV gate's false-negative rate (carried from 07-26, now with more evidence and still no
measurement).** 14 verdicts since the last audit-ledger entry, all REJECT, none appended
(`data/ev_gate_audit.json` → 3 entries, latest 07-12). R0016 measured that the genuinely
per-candidate gates DO discriminate (walk_forward 58.1%, fragility 47.9%, cpcv 43.3%) while the
campaign-level PBO/RC (`libs/autodiscovery/validation.py:39` — "identical for every candidate in a
campaign") vetoed 420/420. No reject has ever been shadow-tracked. The gate's binding term (breadth,
per 3db47ef) structurally kills the modest-but-broad decorrelated-sleeve class — whether that class
holds real edge is unknowable until one reject is allowed to accrue information at $0.

**U3 — True Stage-B concurrency, therefore the true Holm bar, therefore whether any current clock's
eventual verdict will be computed at the right significance level.** Axis clocks correct with
m_concurrent=4 (their own file); the alert layer counts 6 hardcoded standing sleeves + an empty
registry; derivative-metrics/challenger clocks live elsewhere; stageb_capacity counted 3. If the
true desk-wide cohort is ~10, the axis clocks' Holm bar (2.24 at m=4) is too lenient; if capacity
"5" is adopted while ~10 run, the desk is over budget by its own new arithmetic. Nobody can
currently name the number. (Carried from 07-26 U7, now with a fourth conflicting source.)

**U4 — Regime-conditioning of everything (carried, unimproved, now with a visible instrument
contradiction).** `data/crypto_regime.json` (07-28): `trend: bear` (momentum −13.2%) while
`hmm_regime: bull/low_vol`, `hmm_gmm_agree: false` — yet `regime_confidence: 1.0`. A confidence of
1.0 under model disagreement is a self-contradicting readout. No `crypto_regime_history.jsonl`
exists (R0006 open, 52h), so no candidate can be regime-conditioned retroactively and the
resurrection queue's `regime_artifact` class (priority 3) has no data to re-test against. Every
live clock's regime sensitivity remains unknown in a one-regime sample.

**U5 — Whether slow-mechanism signals can EVER clear Stage A at current power.** The idle-axis
screen's own honest accounting shows the structural hole: 20/21 cells SCREEN-UNDERPOWERED,
concentrated at h5/h20 (onchain_activity B h20d: IC +0.0836, residual +0.0809 — the best raw signal
in the batch — verdict UNDERPOWERED at block-n). The mechanisms the desk itself rates ALIVE
(structural barriers, forced deleveraging) and the resurrection queue's prime candidates are mostly
weekly+ stories. At single-asset daily history lengths, h20 block designs may be underpowered *by
construction* — a silent structural bias toward fast signals that no current artifact names.

**U6 — Whether the coverage/memory instruments under-report other completed work.** Two confirmed
cases in 48h: the 21 idle-axis cells (done 07-26, still reported "idle" by
`research_memory.py coverage` on 07-28) and the micro_factory result (mechanism board still says
UNTESTED). Unknown: how much other finished work is invisible to the instruments that direct the
next cycle's effort. An organ that trusts `coverage` would redo done work — the amnesia the
RESEARCH-MEMORY DUTY exists to prevent, now arising from the duty's own instrumentation lag.

**U7 — Kimchi forward health and the pipeline behind it (carried).** kimchi_premium: 6/40 forward
days, cum −4.0%, nw_t −1.1 (noise at n=6, but the sign has been negative since day 1). Behind it:
defi_utilisation (1d), stablecoin (5d, +2.5%), cny (0d). The regional-premium class remains
otherwise exhausted; a kimchi failure at day 40 would leave Stage B fed mainly by the resurrection
and micro programs — both not yet producing candidates.

**U8 — Prediction-market class: probed, informative, and now un-owned.** `reports/prediction_markets/
report.json`: 153 resolved markets, calibration table (mid-low buckets realize ABOVE implied — a
tradable-shaped miscalibration), 3 strategies honestly failed at `n=153 < 250` gauntlet floor. But
no collector exists (`grep -rln "polymarket\|kalshi" scripts/` → none): the "needs more n" verdict
has no accrual path, so the question will be exactly as unanswerable next quarter. No owner, no
clock, no watchlist disposition found.

## 3. WHAT COULD MATTER MOST (ranked opportunities)

Ranked by expected impact × confidence / (cost × maintenance). ★ = compounding multiplier.
The theme is inverted from 07-26: that sweep's gaps were mostly *experiments not run*; this
sweep's gaps are mostly *self-found defects not closed*. The desk found every one of R1–R3's
components itself, rowed them, and left them open — the binding constraint has moved from
discovery of defects to disposition of defects.

**R1 ★ — Repair the funnel's calibration instruments as ONE work item: R0017 synthetic arm +
R0016 campaign-gate scoping + R0023 EV threshold.**
- *Exactly what:* (a) fix the synthetic injection so SR_true=+1.0 realises ≈+1.0, then run the
  positive-control sweep: does a known-good candidate pass walk_forward→cpcv→pbo→EV end-to-end?
  (b) score campaign-level PBO/RC at campaign scope only (rank/deflate, never per-candidate veto —
  `libs/autodiscovery/validation.py:39` already documents they are campaign-constant);
  (c) recalibrate `_EV_THRESHOLD`/`effort_h` against the known-good (carry, EV 0.1171) and
  known-marginal references per R0023, and wire verdict-append to `ev_gate_audit.json` in the same
  code path that produces the verdict (14 consecutive verdicts are missing because appending is a
  separate manual act).
- *Why:* U1+U2. Everything downstream — the value of 115 banked negatives, the legitimacy of
  "price space is dead", the resurrection queue's priors — inherits its meaning from a funnel whose
  positive control currently realises −2.32 on an injected +0.5.
- *Evidence:* R0016/R0017/R0023 rows (all open); `data/ev_gate_audit.json` 3 entries vs ≥20
  verdicts; commit 3db47ef's 3/3 REJECT.
- *Benefit:* a calibration certificate for the whole discovery factory; recovered edges if FN>0.
  *Complexity:* low-medium (the probe exists; the fix is injection alignment + gate scoping).
  *Dependencies:* none. *Validation:* synthetic pass/fail matrix (good must pass, null must fail —
  BOTH arms). *Failure modes:* over-loosening — guard: null-synthetics must keep failing; the
  Stage-B bar is untouched (it is the product). *Alternatives:* keep hand-auditing gates each sweep
  — rejected: this is the third consecutive independent finding of the same defect. *ROI:* highest
  available. *Confidence:* 0.85. *Maintenance:* probe joins the daily cycle. *Monitoring:* GATE-
  OPTIMALITY histogram per cycle. *Retirement:* when n≥50 scored verdicts recalibrate priors per
  the ledger's own policy. *Horizons:* 1w fixed + first certificate / 1m recalibrated gate + first
  shadow-tracked rejects / 3m first recovered edge / 1y+ every negative result worth more.

**R2 ★ — One multiplicity truth: write trials/verdicts to the ledger AT THE WRITE SITE, and one
slot-cohort number.**
- *Exactly what:* (a) every organ that writes a verdict JSON (axis_screen batches,
  idle_axis_screen, stage_a_executor, micro_factory, hl_*) appends its research_memory row (and a
  trials_ledger row) in the same function that writes the JSON — never as a separate duty;
  backfill the 21 idle-axis cells + 6 stage-A verdicts + micro result now; (b) populate
  `data/shadow_sleeves.json` from the real clock inventory (4 axis + 6 standing + derivative-
  metrics + challenger), delete the `_standing = 6` hardcode, and make axis clocks' m_concurrent
  read the registry; (c) reconcile 12 (law) vs 5 (stageb_capacity) explicitly — either amend the
  law with the derivation or correct the derivation's cohort and thresholds (its 0.30-z "cheap"
  cutoff is a rule of thumb, not a power analysis).
- *Why:* U3+U6+M4. Two instruments already contradict finished work; the Holm bar is currently
  computed on whichever cohort each file can see. Statistical honesty is load-bearing here and it
  rests on fragmented JSON.
- *Evidence:* `shadow_sleeves.json` = `[]`; `run_alerts.py:241`; stageb_capacity.json running=3 vs
  axis_shadow_state 4 axes + 6 standing; coverage says "idle" over 21 finished cells.
- *Benefit:* every future audit, DSR, and capacity decision computed on truth. *Complexity:* low.
  *Validation:* `coverage` output matches artifacts; one grep finds every clock. *Failure modes:*
  registry drifts stale — guard: alert reads ONLY the registry, so drift pages. *ROI:* pure
  compounding. *Confidence:* 0.85. *Retirement:* never (this IS the bookkeeping). *Horizons:* 1w
  wired / permanent honesty dividend.

**R3 — Bring the Stage-A executor inside the doctrine it was built to serve.**
- *Exactly what:* (a) pass each queue candidate through `hypothesis_novelty` before screening
  (aggregate on-chain activity fields were screened 07-28 hours after the novelty gate blocked the
  same class in another organ); (b) require/attach a one-line mechanism prior per candidate —
  unread telemetry fields (`venue_age_s`, `mark_age_s`) are data-quality series, not alpha
  candidates; triage them to the data-quality organ instead of burning screens; (c) sweep
  mechanism-appropriate targets/horizons (the current screen is next-day-BTC-only — the exact
  reflexive default the TARGET/HORIZON duty forbids) or explicitly re-scope the tool as "field
  triage" whose outputs are not screens; (d) either route through `axis_screen.stage_a_screen` or
  document why the parallel harness's different verdict bars (t≥2.5/IC≥0.05 vs ic_min 0.03 +
  timing-Sharpe) are intended — two harnesses now produce incomparable "SCREEN-*" verdicts.
- *Why:* the executor is the highest-throughput screening surface the desk has (6/cycle × 214
  queue); it is also the least doctrine-compliant, written the same day as the fully-compliant
  `screen_idle_axes.py` — the inconsistency is organ-local, so the fix is mechanical.
- *Evidence:* `scripts/stage_a_executor.py:37` (PRICE_SRC=BTC only), no novelty import (grep),
  queue composition in `data/conversion_queue.json` (unread_field entries).
- *Benefit:* converts a breadth-mining loop into a mechanism-led one before it manufactures its
  first plausible artifact. *Complexity:* low. *Confidence:* 0.8. *Failure modes:* over-filtering
  the queue — fine: Stage-A compute is cheap but attention to false PASSes is not. *Horizons:* 1w.

**R4 — Start the regime-history artifact and fix the confidence readout; feed the resurrection
queue's regime class.**
- *Exactly what:* append-only `crypto_regime_history.jsonl` (R0006's own 3-line spec); make
  `regime_confidence` reflect model disagreement (it reads 1.0 while hmm and momentum disagree);
  then run the first regime-conditioned re-screens from the resurrection queue's `regime_artifact`
  entries (priority 3) and record regime tags on every new screen row.
- *Why:* U4 — every regime question is currently unanswerable retroactively, and the desk's whole
  live history is one regime. This is also the cheapest standing data asset the subsystem lacks:
  its cost is 3 lines and its absence is permanent data loss (mining-never-regresses applied to
  self-generated state).
- *Evidence:* `ls data/crypto_regime_history.jsonl` → ABSENT; crypto_regime.json contradiction.
- *ROI:* high option value, trivial cost. *Confidence:* 0.9 on the artifact, 0.4 on near-term alpha.
  *Horizons:* 1w collecting / 3m first regime-conditioned trials / 1y regime-aware promotion.

**R5 — Name and attack the slow-horizon power hole.**
- *Exactly what:* a short spec: for h≥5 screens, (a) prefer cross-sectional panel constructions
  (panel_width>1 multiplies n_eff — the harness already computes it), (b) extend backfills where
  free history exists (the coinmetrics 16y precedent), (c) where neither is possible, pre-register
  a LONGER forward clock instead of discarding — an UNDERPOWERED verdict with IC +0.08 (onchain_
  activity h20) is a *deferral*, not a null, and currently nothing distinguishes the two states.
- *Why:* U5 — the mechanism families still alive are mostly slow; the screening layer is
  structurally biased toward fast signals; nobody has written this down.
- *Evidence:* 20/21 idle-axis cells UNDERPOWERED; CFE h1d underpowered at n=204 with
  min_detectable_ic 0.137 vs realistic ICs of 0.02–0.05.
- *Benefit:* stops silently discarding the exact class the mechanism board points at.
  *Complexity:* low (spec + verdict-taxonomy tweak: add SCREEN-DEFERRED-POWER). *Confidence:* 0.75.

**R6 — Every "needs more data" verdict starts an accrual clock or records why not.**
- *Exactly what:* prediction markets (U8): decide owner + collector (resolved-market snapshots are
  free REST pulls) or row a reasoned rejection; defi_lending (snapshot-only, honestly noted at
  generation time) — verify the forward accrual actually ticks (`build_defi_axis.py` is in the
  daily cycle; confirm rows grow); apply the same rule to future INSUFFICIENT-DATA/UNDERPOWERED
  verdicts via the R5 taxonomy.
- *Why:* the desk already treats uncollected forward history as destroyed value for external axes;
  the same law applies to its own probe verdicts. *Confidence:* 0.8. *Complexity:* low.

*Explicitly NOT recommended:* loosening any Stage-B bar (untouched, correctly); re-testing the 11
priority-0 graveyard entries (no_economics — the resurrection engine itself says DEAD); new
language miners (STOP line stands); paid data (nothing above requires a dollar).

## 4. WHAT WE TEST NEXT (concrete experiments)

**T1 — Funnel positive-control certificate (from R1).** Hypothesis: the gauntlet can pass a
genuinely good candidate. Method: after fixing the injection, run a matrix of synthetics —
SR_true ∈ {0, +0.5, +1.0, +2.0} × {tight, loose} construction — through the full per-candidate
gate chain. Success: monotone pass-rate in SR_true; nulls fail ≥95%; at least SR=+2.0 passes
end-to-end. Failure state is itself the headline finding (the funnel cannot promote, explaining
420/0 differently than "no edge exists"). Validation: probe re-runs in the daily cycle on a fixed
seed set. Retirement: never — this is the instrument's calibration weight.

**T2 — EV-reject shadow cohort (from R1/U2).** The 14 recent rejects (11 axis pre-registrations +
3 DeFi) are already pre-registered with constructions and falsifiers. Track them forward at $0
outside the slot budget (information-only, no promotion rights). Success criterion: after 40
forward days, measured FN rate — 0 vindicates the gate; ≥1 recalibrates it with evidence. This was
T1 in the 07-26 sweep; it did not start; it costs nothing; start it.

**T3 — Desk-wide Holm cohort enumeration (from R2).** Method: mechanical inventory of every live
forward clock across axis_shadow_state, per-sleeve shadow files, derivative-metrics state,
challenger state → one registry row each → recompute each clock's Holm bar at true m. Success:
one number, alert reads it, capacity derivation re-run against it with a power curve (P(detect |
SR, n=40d, m) rather than the 0.30-z heuristic). Deliverable doubles as the shadow_sleeves.json
population.

**T4 — Micro feature batch through the audited harness (from K4/K8).** The 5 computed-but-unused
microstructure features in feature_library are READY (already computed from the 4.4GB moat).
Screen each with declared mechanism cards at h∈{1h,4h,1d} equivalents, block-sampled, every cell
rowed at write site (R2 discipline). Success: standard bar; even 5 clean nulls close the first
tranche of the 447-cell frontier with receipts. This is also the M_LIQUIDITY_WITHDRAWAL follow-up
the mechanism board is waiting on — and the result must flip the board's UNTESTED cell either way.

**T5 — Resurrection batch 1 (from K3).** The 2 priority-5 entries (defi_health, multilingual
wikipedia) re-tested at h5/h20 with panel widening per R5, novelty-gated, pre-registered before
first screen. Success: standard screen bar → clock; both-null: the "killed at daily horizon"
hypothesis about those kills is itself falsified and the queue's priority model updates. Every
cell counted; the original kills stay in the graveyard regardless of outcome (new constructions,
new rows — never edits).

**T6 — Funding-settlement boundary event study (carried from 07-26 T3, still not started, still
free).** No artifact exists (`grep -rln "funding_boundary" scripts/ data/` → none research-shaped).
The moat + liquidations.parquet + H8 lake make this a pure-analysis test of crypto's clearest
calendar mechanism (time-of-day seasonality = the legacy taxonomy's port). Cost-floor first, per
HYPOTHESIS_MAX_SPEC #1. If not started within a week, row a reasoned deferral with a date —
silence on a twice-recommended free experiment is the one indefensible state.

**Success metrics for the next sweep to re-measure (pre-registered here):**
1. Positive-control matrix exists with a monotone pass-rate row (T1 artifact on disk).
2. `ev_gate_audit.json` entry count ≥ 20 (backfill) AND appends occur in-code with verdicts.
3. One slot-cohort number: `shadow_sleeves.json` non-empty, `_standing` hardcode gone, axis
   m_concurrent == registry count; the 12-vs-5 conflict carries a written resolution.
4. `research_memory.py coverage` reports 0 idle axes (matching artifacts) and stage-A/idle-axis/
   micro results all have memory rows.
5. ≥1 resurrection re-test and ≥1 micro-feature screen completed and rowed, whatever the verdicts.
6. §41: zero open recommendation rows older than 7 days attributable to this subsystem
   (R0016/R0017/R0023 dispositioned).

## APPENDIX A — six-perspective findings log (raw, evidence-first)

### A1 INTERNAL (measured, not configured)
1. **F1 — The defect-disposition loop is the new binding constraint.** 14 of 24 recommendation
   rows are `open` past the §41 24h bar (measured against 07-28 16:00: R0001 53h, R0003–R0009 52h,
   R0011–R0017 43–49h). Three of those open rows (R0016/R0017/R0023) are the desk's OWN discoveries
   of its most consequential subsystem defects. The same EV-gate miscalibration has now been found
   independently three times (07-26 sweep, 07-26 probe, 07-28 generation) and fixed zero times.
   Finding-generation is saturated; finding-closure is the leak.
2. **F2 — Verdict artifacts and the memory/coverage instruments have diverged at two write sites
   in 48h.** 21 idle-axis cells (done 07-26 20:50) invisible to `coverage` (still "3 axes idle" on
   07-28); micro_factory's lead-vs-coincident result (07-27 18:21) invisible to the mechanism board
   (M_LIQUIDITY_WITHDRAWAL "UNTESTED") and to research_memory (0 rows LIKE '%liquidity_withdrawal%').
   Root cause is structural: logging is a separate act from verdict-writing, so it skips under
   exactly the conditions (end of a long run) where skipping is invisible.
3. **F3 — The Stage-A executor screens without the three disciplines that make screening safe.**
   No novelty gate (grep: no import), no mechanism prior (queue = mechanically-enumerated unread
   FIELDS, including telemetry like `venue_age_s`), single target/horizon (next-day BTC,
   `stage_a_executor.py:37,63`), and a second parallel verdict scale (t≥2.5/|IC|≥0.05) incomparable
   with the audited harness's. Its honesty rails (leakage contract, UNDERPOWERED floor, persisted
   verdicts) are genuinely good — the gap is in WHAT it screens and AGAINST what, not how.
4. **F4 — Generation of counted candidates has been frozen for 6 days while the gate that would
   score them is known-broken.** `gen_done_*` cadence keys: 13 @ 07-22, 2 @ 07-17; last
   research_candidates row 07-22 in every DB. R0016's mechanism (campaign PBO rises with campaign
   size → whole campaign vetoed) makes large-batch generation *mechanically self-defeating* until
   R1 lands — the gate bug and the generation freeze are one defect, not two.

### A2 EXTERNAL (how another world-class team would improve this)
1. They would run positive controls on the whole funnel as routine calibration, not as an open
   ticket — a validation pipeline that has never passed a planted good candidate is an unvalidated
   instrument (R0017 is 43h old; at a serious shop it would be a same-day sev).
2. They would have ONE experiment registry keyed at write time. The desk now has research_memory
   (live, 133 rows), trials_ledger (designed, empty ×5), per-organ verdict JSONs (idle_axis,
   stage_a, cfe, batch_*, micro_features, hl_*) — six shapes of the same fact. The write-site
   append (R2) is the standard industry fix.
3. Credit where due: the trader-skill falsification sequence (gapped windows, cohort perturbation,
   survivorship direction notes, kept-but-not-promoted exceptions) is at or above professional
   replication-desk standard — most shops would have shipped the copytrading product first and
   discovered the position-overlap artifact in production.

### A3 FUTURE (2–3y redesign pressure)
1. The construction grammar (feature_library's OBSERVABLE × TRANSFORM × WINDOW × NORMALISATION,
   447 cells) is the right 2–3y architecture: enumerable search spaces + cheap LLM screening make
   "which cells are untested" the core research query. The missing half is closing the loop —
   tested cells auto-marking themselves (R2's write-site rule again).
2. Mechanism-board steering (K2) anticipates where LLM-era research goes: family-level mortality
   priors allocating attention, instead of idea-level enthusiasm. Making the board's UNTESTED/ALIVE
   cells consume screen results mechanically (F2 fix) turns it from a snapshot into a controller.

### A4 CONTRARIAN (test the core assumptions)
1. **"420/0 proves price-space is dead" now has a measured competing explanation.** R0016: the
   campaign-level PBO (0.6159 > 0.50 gate) and White RC (p 0.42) vetoed all 420 identically; the
   per-candidate gates individually passed 42–60% each. "Sole-cause failures is EMPTY" means no
   candidate died ONLY of the campaign gates — the kill was overdetermined — but the *strength* of
   the 420/0 evidence is weaker than its citation count implies, and the external corroboration
   (era experiments, HXZ) is now carrying more of that conclusion's weight than the desk's own
   experiment. Cheap resolution: T1's synthetic matrix quantifies exactly how much.
2. **"Stage-A is statistically free" is true for promotion risk and FALSE for attention risk.**
   Zero promotion authority bounds false-positive *capital* cost at 0, but every SCREEN-PASS
   consumes triage attention and Stage-B candidacy discussion. A 214-item mechanism-free queue at
   6/cycle will emit passes by chance (~1 in 40 at t≥2.5 two-sided even with clean data); without
   mechanism priors those passes are indistinguishable from discoveries at the moment they most
   matter. The two-stage law protects capital; only the mechanism prior protects attention.
3. **"The desk under-uses Stage-B" (stageb_capacity's own conclusion) may be exactly backwards.**
   If the true concurrent cohort is ~10 (4 axis + 6 standing) and honest capacity is 5, the desk is
   at 2× its derived budget and every current clock's Holm bar is too lenient — the opposite
   failure. The data to decide exists in files; nobody has joined them (T3).

### A5 GREENFIELD (rebuild-from-scratch score)
1. A greenfield build would fuse verdict-writing and ledger-writing into one function and derive
   ALL slot arithmetic from one registry. Baggage score: moderate and *rising* — 48h added two new
   verdict formats (stage_a_verdicts.jsonl, cfe_regulated_basis_screen.json) and one new capacity
   number (5). Nothing is wrong individually; the assembly tax compounds per artifact. R2 is the
   80% fix at ~1% of a rebuild's cost.
2. What a greenfield build would KEEP unchanged: the two-stage law, the leakage contract (validated
   on synthetic ground truth), the mechanism board, the graveyard's kill-basis discipline, and the
   resurrection engine's weaker-court doctrine. The subsystem's epistemics are not the baggage; its
   bookkeeping is.

### A6 FRONTIER (recently possible, unexploited)
1. **CFTC crypto COT remains uncollected** (carried from 07-26 A6.1 — `grep -rin "\bCOT\b" docs/
   research/data_axis_watchlist.md` shows watchlist presence only, no collector). Free, weekly,
   mechanism-rich (hedging pressure — the M_STRUCTURAL_BARRIER-adjacent family the board rates
   ALIVE), and the desk's own 26y COT muscle memory is idle since the MT5 stack retired (commit
   9ecadce removed the EA layer). Cheapest genuinely-new ALIVE-family axis available.
2. **Deribit SOL/XRP options** still satisfy the VRP revisit condition and the collector is still
   BTC/ETH-only (`deribit_surface.parquet` → 70 rows, {BTC:35, ETH:35}). Carried 48h without a
   disposition; the graveyard's own revisit clause is the pre-registration.
3. **The desk's own new probes create frontier data nobody else has**: stage_a_verdicts + 133
   research_memory failure rows + mechanism death counts are becoming a meta-dataset (which screen
   classes fail how, at what power) that could calibrate `p_survive` priors empirically — R0023's
   "tag-driven empirical prior" suggestion is buildable from data already on disk.

## APPENDIX B — negative-space sweep (never asked / collected / tested)

- **Questions never asked:** What is the desk's screen-level false-PASS base rate under the new
  t≥2.5 executor bar with 214 candidates queued? (Computable analytically; nobody has written it
  next to the tool.) Is `regime_confidence` ever <1.0 in practice? (No history file exists to
  check — R4.) Which of the 115 memory-logged failures were UNDERPOWERED rather than null? (The
  taxonomy conflates them; R5.)
- **Markets still never studied:** options surface dynamics beyond ATM snapshots (70 rows total);
  crypto COT positioning (A6.1); DEX/on-chain microstructure (the class was EV-vetoed pre-research
  and never revisited — a U2 casualty); cross-venue funding dispersion as its own signal (the desk
  trades single-venue funding sleeves but has never screened the SPREAD between venues' funding as
  a predictor — data exists in the funding_8h lake; no memory row matches 'funding dispersion' or
  'cross-venue funding').
- **Data collected but never researched (delta since 07-26):** moat now READ once (micro_factory —
  the 07-26 entry clears); still unread as research inputs: 253 live fills (own-fill replay corpus
  — specced in STRUCTURAL_EDGE_IDEAS #2, still no artifact), cot_zcache.parquet (26y × 11, now
  fully orphaned by the MT5 removal), the 5 computed-unused micro features (T4), and
  `data/liquidations.parquet` ticks for the boundary/cascade studies (T6).
- **Resolutions:** 1s→hourly now probed once (micro), 4h in production screens (HL) — the D1
  monoculture is broken. New gap made visible by the fix: nothing between hourly aggregates and
  daily bars has a harness (the moat's native event-time remains unexploited beyond hourly means).
- **Failure modes never simulated:** a candidate-stage regime-stress screen still doesn't exist
  (black_swan_library gates promoted alphas only — carried finding); newly visible: no synthetic
  NEGATIVE control for the *screen* layer either (the leakage detector has one; the verdict layer
  above it doesn't — planted-noise batches through stage_a_executor would measure its false-PASS
  rate directly).
- **Signals untestable for missing data (registry check):** defi_lending history (snapshot-born
  07-28, honestly marked forward-accruing); prediction-market entry-price series (no collector —
  U8); HL userFills beyond 2000/address (structural API wall, correctly documented in the
  graveyard); pre-2026 L2 depth (destroyed at source, graded residual_gap — unchanged). The
  registry handles these honestly; U8 is the one lacking a disposition.
- **Empty seams checked and found genuinely empty:** no new crowding measurement anywhere
  (crowding_intelligence.py + 13 sibling engines: 0 external importers, 0 artifacts — dead code
  carried from the factory build-out; the mechanism board is the de-facto replacement and covers
  theme-level crowding only); no Granger/causal-inference machinery beyond the leakage contract's
  reverse-causality + shift tests (event-study harness R0007 remains open); language/community
  coverage unchanged and adequate (STOP line evidence-backed; Quantopian archive opened 07-28 adds
  the largest dead-strategy-community corpus in English).

## APPENDIX C — commands run (audit trail, all read-only)

Key proving commands (each finding above cites its own):
- `git log --oneline --since=2026-07-26 --stat` — 10 commits; stage_a_executor/stageb_capacity/
  conversion_engine/micro+hl factories/EN-miner sessions D landed post-prior-sweep
- `data/ev_gate_audit.json` → 3 entries (07-04/07-11/07-12); `alpha_economics.py` constants
  unchanged; commit 3db47ef → 3/3 DeFi REJECT + novelty-gate block of netflow re-screen
- `data/axis_shadow_state.json` → 4 clocks (kimchi 6/40 cum −4.0% nw_t −1.1; defi 1d; stablecoin
  5d +2.5%; cny 0d), m_concurrent=4, holm_bar 2.24
- sqlite: trials_ledger 0×5 DBs; research_memory 133 rows (115 failure) with per-day construction
  histogram {07-26: 93}; per-axis LIKE counts (etf 7, fed 11, crossasset 11, cme 14, micro 1,
  liquidity_withdrawal 0)
- `data/idle_axis_screen.json` → 21 cells, 20 UNDERPOWERED / 1 INTERESTING, novelty_gate block,
  declared block-sampling convention; `research_memory.py coverage` → "3/20 axes idle" (the same 3)
- `data/stage_a_verdicts.jsonl` → 6 verdicts 07-28 (1 FLAGGED contemporaneous, 3 UNDERPOWERED n=5,
  2 NULL); `conversion_queue.json` → 214 unread-field candidates; executor source: BTC-only target,
  no novelty import, `_BATCH=6`
- `stageb_capacity.json` → {running: 3, backlog: 80, recommended: 5}; `TWO_STAGE_DISCOVERY_LAW.md:27`
  → MAX_FORWARD_SLOTS=12; `run_alerts.py:241` → `_standing = 6`; `shadow_sleeves.json` → `[]`
- `recommendation_ledger.json` → 24 rows: 19 open / 3 implemented / 1 scheduled / 1 rejected;
  14 open >24h; R0016/R0017/R0023 full texts
- `data/mechanism_board.json` → 9 families, 4 FAMILY KILLs, M_LIQUIDITY_WITHDRAWAL UNTESTED;
  `data/micro_features.json` → 5 symbols × 35h lead/coincident/residual stats;
  `data/feature_library.json` → 9 features, 5 unused, 447 proposals;
  `data/graveyard_resurrection_queue.json` → 42 entries {p5:2, p3:8, p2:13, p1:8, p0:11}
- `docs/graveyard.md` tail + 5 commits since 07-26 — trader-skill program kills with gapped/
  perturbation/survivorship evidence; `data/cfe_regulated_basis_screen.json` → same-day screen of
  the newest axis; `batch_coinmetrics_screen.json` (07-28) → power fields + external verification
- `reports/prediction_markets/report.json` → 153 markets, calibration, 0 survivors (n<250);
  `grep -rln "polymarket\|kalshi" scripts/` → no collector
- `data/crypto_regime.json` → bear/low_vol, hmm says bull, agree=False, confidence=1.0;
  `crypto_regime_history.jsonl` ABSENT
- `deribit_surface.parquet` → (70,6) BTC/ETH only; cadence `gen_done_*` → 13 @ 07-22;
  last research_candidates row 07-22 (all DBs)
- alpha_factory engine import sweep: 14 engines, controller has 0 external importers, 0 artifacts
