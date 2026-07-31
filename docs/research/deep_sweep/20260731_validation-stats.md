# WEEKLY DEEP COLD AUDIT — validation-stats — 2026-07-31

STATUS: COMPLETE

_(Live addendum pointer: `reports/gauntlet_certification.json` was still computing at report
close — my launched run, log `/tmp/certify_audit_20260731.log`, ~6.2min/control × 21 controls;
the 08:21 cron fire is the backstop. First row already in and quoted in V1/U1: true Sharpe 2.0
FAILS both paths — sole blockers dsr + reality_check on the per-candidate path. T1/X1 instruct
the next cycle to read the finished artifact.)_

**Subsystem scope:** selection bias, multiple testing, parameter sensitivity, sample dependence,
walk-forward + CV methodology, regime robustness, distributional assumptions, uncertainty
propagation, capacity/cost modeling, simulation realism, MC design, bootstrap quality,
structural breaks. Prime quarry: zero-information gates, rigorous methods as dead code, DSR bar
optimality.

**Relationship to prior sweeps.** 07-29 report (complete, 13 findings F1–F13, strengths S1–S8,
unknowns U1–U6) mapped the campaign path's degenerate gates and measured the DSR design surface.
07-30 report died as a skeleton (never flipped COMPLETE) — its declared plan is inherited here:
(1) verify which 07-29 findings actually moved on disk (outcome-not-config applied to the audit
itself), (2) attack the statistical correctness of the primitives the 07-29 report certified as
strengths from architecture reads only, (3) attack seams never opened: the Stage-B forward path
(now the ONLY route to capital), the screen harness's own power/alignment math, and the cost
model. This report does NOT re-litigate F1–F13; each is re-cited only where its disk state
changed or failed to change.

---

## SCORES

- current_capability_pct: **58** — primitives ~85 (K1-K8: dsr/stepwise/screen_select/
  positive_control/kelly_shrink/event_study all survive adversarial read); measurement layer ~30
  (four built instruments have never produced their number: certification, honest histogram,
  reject scores, forward-verdict history); Stage-B stated error ≠ realized error (V7).
- practical_ceiling_estimate: **90** — everything found is wiring, cadence, or a 3-line formula
  fix; nothing requires new science. The residual 10% is T=310 sample physics (see CEILING
  EXPANSION).
- ceiling_gap: **32 points**, dominated by: unwired deciders (V3), unproduced measurements
  (V1/V2/U2), Stage-B peeking (V7), capacity incoherence (V5).
- opportunity_cost_1y: **the conversion funnel's entire throughput** — a real edge generated any
  time this year meets a screen that admits nobody (V4: 0/420 even ignoring welds; first
  certification row: true SR 2.0 fails) and forward clocks running at ~5× stated α (V7). Until
  X1-X3 land, discovery output cannot reach capital at designed error rates in either direction.
- confidence: **0.85** on findings (every claim command-cited, two agent traces cross-checked);
  **0.6** on the welded-gate prediction pending the certification artifact.
- unknown_unknown_score: **0.35** — the subsystem is well-mapped (4 audits in 6 days) but U3
  (verdict history possibly unrecoverable) and U7 (correlation structure) could each surprise.
- info_gain_if_investigated: **reports/gauntlet_certification.json is the single highest
  info-gain read available to the desk this week** (X1/T1).
- expected_alpha_contribution: indirect, first-order — X2+X3 are the unblockers between
  generation and capital; without them validated-alpha throughput is structurally ~0.
- expected_compounding_contribution: X1 (gate-CI), X6 (histogram ratchet), X8 (verdict history)
  are compounding multipliers: they make every FUTURE gate change cheap, safe, and measured.
- CEILING EXPANSION: the ceiling assumption is **T=310 days of history** — merely historical,
  not technological (07-29 F8: T=1500 drops the passable true-SR bar from ~5 to ~2.4; T dominates
  N logarithmically). The lever is reconstruction/backfill and higher-frequency evidence (8h
  panels ≈ √3× evidence rate) — owned by data-moat, named here as the cross-subsystem dependency
  that moves this subsystem's physics.

---

## 0. DELTA SINCE 07-29 (what actually moved on disk)

Outcome-not-config applied to the prior audit's own findings. Verified 2026-07-31 ~03:00Z.

| 07-29 finding | State today | Proving command |
|---|---|---|
| F1 gate histogram organ absent | **MOVED (partially)**: `scripts/measure_gate_histogram.py` exists (2ec4fde), artifact `reports/gate_histogram.json` (2026-07-30T02:15Z) with legacy AND per-candidate tallies. One-shot so far, callers `certify_gauntlet.py`, `max_audit.py` — recurrence unverified (see V-findings) | `cat reports/gate_histogram.json`; `grep -rln measure_gate_histogram scripts` |
| F2 trials_ledger 0 rows | **UNMOVED**: 0 rows in all 8 DBs with the table | sqlite scan over `data/*.sqlite` → `trials_ledger: 0` × 8, `no-table` × 2 |
| F3 rejection-shadow inert | **UNMOVED**: `web/reject_shadow.json` as_of 2026-07-31T02:36Z says `57 eligible, n_pending_rescore: 57, NONE re-scored yet`; `data/reject_forward_scores.json` still does not exist. The organ refreshes daily and produces zero verdicts — a green timer with zero output, the audit doctrine's prime quarry, now ~6 days old | `ls data/reject_forward_scores.json` → No such file; `cat web/reject_shadow.json` |
| F4 stepwise gates dormant, ruling displaced | **MOVED — ACTIVATED**: production passes `campaign=` at `libs/autodiscovery/orchestrator.py:220`, `scripts/run_mt5_funding_bridge.py:124`, `scripts/run_crypto_portfolio.py:133`, `scripts/certify_gauntlet.py:102`. But R0033 is STILL open in the ledger ("UNDISPOSED past grace, 1.8d") — the ledger lags the repo (see V10) | `grep -rn "campaign=" libs scripts`; `python3 scripts/recommendations.py report` |
| F5 dead rigorous methods | **PARTIALLY MOVED**: `cpcv.py` now wired (`validation.py:249` real CPCV with purge+embargo, contiguous fallback only <60 obs); `fdr.py` wired via new `screen_select.py` (d56675a) — but as REPORTING, not as the deciding gate (V2); `stepwise.py` (per-candidate CSCV + Romano–Wolf) live. Others unverified this pass: lockbox, baselines (imported at `validation.py:24`, gate skip-as-True), stationarity | `sed -n '228,260p' libs/autodiscovery/validation.py`; reads below |
| F7 adv_usd $100B default | **UNMOVED**: `validation.py:409` still `adv_usd: float = 1.0e11`; capacity ≈ EV-sign duplicate confirmed by the new histogram itself (capacity 238/420 pass vs expected_value 251/420) | `grep -n adv_usd libs/autodiscovery/validation.py`; `cat reports/gate_histogram.json` |
| F8 DSR bar (design defect) | **UNMOVED as a gate**: `validate():478` still binary `dsr.passed` at 0.95 per-candidate; T=310 campaign unchanged | `sed -n '473,488p' libs/autodiscovery/validation.py` |
| F9 EV gate ~100% reject | R0023 still open (2.5d); histogram shows expected_value 251/420 pass **inside validate()** — the ~100%-reject EV gate finding was about `alpha_economics.py` hypothesis-EV (different gate), unresolved | `recommendations.py report` → R0023 UNDISPOSED |
| F10 disposition throughput | **WORSE in absolute terms**: ledger 36→69 rows, 33 open past grace (was 31). Implementation throughput improved (3→12 implemented) but detection still outruns disposition; ledger also now UNDER-reports reality (R0033 implemented-but-undisposed) | `python3 scripts/recommendations.py report` |
| F11 annual_sharpe ×4.1 inflation | **UNMOVED**: `validation.py:40` `_PERIODS_PER_YEAR = 24*260`; `:463` applies √6240 to whatever frequency arrives | `grep -n _PERIODS_PER_YEAR libs/autodiscovery/validation.py` |
| R0017 synthetic-probe arm | **CLOSED with corrected diagnosis** (a5da892): cause was seed-reuse (all 13 rows one noise draw) + SE(ann SR)≈1.085 at T=310, not mis-wiring. `positive_control.py` landed 07-30 | `git show a5da892 --stat` |
| Kimchi Stage-B slot | Freed when kimchi was refuted at depth (07-31 alpha-discovery F2): slot idle, snapshot stale — owned by today's alpha-discovery report, not re-derived here | `docs/research/deep_sweep/20260731_alpha-discovery.md` §F2 |

Net delta: the desk moved fast on the *instrument* (per-candidate gates live, FDR screen computed,
positive control landed, histogram measured once) and did NOT move on the two *evidence organs*
(trials ledger, reject-shadow scoring) nor the two known metric bugs (annual_sharpe, adv_usd).

## 1. WHAT WE KNOW (validated strengths, each with proving command)

**K1. The per-candidate multiplicity migration is real, live, and statistically competent.**
`stepwise.py` read in full: correct Romano-Wolf stepdown (stationary block bootstrap, max-null
stepdown loop, monotone-p enforcement `stepwise.py:213-214`, zero-variance guard), exact
sufficient-stats CSCV (12,870 splits, O(1) combine — `stepwise.py:80-104`), raw_p exposed for
downstream FDR with the double-correction trap documented (`:68-73`). Production callers:
`orchestrator.py:220`, `run_mt5_funding_bridge.py:124`, `run_crypto_portfolio.py:133`.

**K2. The orchestrator path has grown four genuinely-wired safeguards since 07-29** (agent
trace, all with file:line): `campaign_fdr` acts (demotes to PAPER, `orchestrator.py:228,237-240`);
`LockedHoldout` seals and opens with a demotion decision (`:211-214, 245-249`);
regime-robustness gates REGISTRY status (`:257`, ≥2 vol regimes); DSR deflation uses cumulative
store count, not batch (`:79-81, 157`). F5/U4 are materially smaller than on 07-29.

**K3. The one-source equity fix works end-to-end.** `_desk_equity_usd()` returns $18,676 from
venue truth (NAV chain) — measured live this audit; the config file said $4,500 and is now rung 3
of the ladder (`validation.py:88-115`).

**K4. positive_control.py survives adversarial read.** Exact-sample-Sharpe construction
(standardize innovations then add drift — sample SR pinned at any T), raw null cohort preserving
cross-sectional dispersion (the R0017 trap, documented and test-asserted), multi-seed discipline.
The R0017 root-cause correction (seed reuse + SE(annSR)=1.085 at T=310) is itself a model of
honest retraction (`git show a5da892`).

**K5. kelly_shrink.py survives numeric attack (S7 re-certified at depth).** Lo (2002) SE,
Bayesian shrink S²/(S²+SE²), vif-aligned effective N (same autocorr_factor as the significance
test), NAV-scaled first-inversion probation, self-expiring. No defect found.

**K6. The real CPCV is now the cpcv gate.** Purge+embargo combinatorial splits with honest
fallback only below 60 obs (`validation.py:228-259`); gate informative at 238/420 pass.

**K7. Stage-B conservatisms that are real:** rank=1 Bonferroni-for-all (`run_axis_shadows.py:138`
— tighter than full Holm), carry counted in m while exempt from the bar (makes others stricter),
verdicts un-latch (ELIGIBLE can revert), m now live (`concurrent_m()`, fixed from `len(_AXES)`
07-30 — bar 2.24→2.61/2.64 in the phantom-edge-safe direction).

**K8. Screen-layer trial accounting remains exemplary** (07-29 S4 spot-rechecked):
`reports/axis_screens/_raw_trials.json` logs every cell; wikipedia screen logs falsification
lags and skips graveyarded cells by name.

## 2. WHAT WE DON'T KNOW (ignorance ledger)

**U1. The gauntlet's certified admission threshold** — resolving NOW: certification launched
this audit (V1); first row in: true SR 2.0 fails BOTH paths (blockers: dsr + reality_check on
per-candidate). Full pass_rate_by_true_sharpe + null FPR lands in
`reports/gauntlet_certification.json` (~2.2h at 374s/control from `/tmp/certify_audit_20260731.log`).

**U2. The false-negative COST of the reject pile** — unchanged: 57 rejects, 0 forward-scored,
and now root-caused: `run_rejection_rescore.py:30-38` `_forward_score()` is a stub returning
None ("until the lake-backed replay is wired"), so the daily organ audits an empty feed forever.
Was U1/F3 on 07-29; the missing piece is ONE function: a lake-backed forward return lookup.

**U3. Realized Stage-B error rate at the DESK level.** V7 measured per-clock peeking inflation
(×4.9) and V9 estimated recycling exposure (~0.2-0.45 designed, ~1-2 realized false
ELIGIBLEs/yr); the actual historical count of false ELIGIBLEs (clocks that went ELIGIBLE then
FAILING) has never been tallied from the artifacts. Cheap to measure from web/axis_shadows.json
history if archived; unknown if history is retained.

**U4. Whether ANY of the 420 pass the six informative gates under an UN-welded conjunction**
(V4): survivors=[] with sole_blocker={} means every candidate fails ≥2 gates — but nobody has
computed survivorship with dsr+RW removed and screen_select (BY-FDR) deciding, i.e. the
shortlist the fixed instrument would actually produce. One script-run away once V2/V3 close.

**U5. True desk-wide effective trial count** — three counting regimes now coexist (V17);
the honest cumulative N for any DSR remains unknowable until one regime wins.

**U6. Block-length adequacy** (third audit): mean_block=10 everywhere, never sensitivity-tested.
Politis-White auto-selection remains unimplemented.

**U7. Cross-sectional signal correlation ρ̄ on the desk's panels** — the number that decides how
much evidence V12's width-discount is discarding (139× at ρ̄=0 vs 1× at ρ̄=1). Never measured.

**U8. Cost-model fidelity vs own fills** — the −51.74 bps round-trip anomaly (R0026) is
unexplained; until it is decomposed, every net-of-cost backtest number carries an unquantified
bias of that order (V15).

## FINDINGS (new this sweep, V-numbered; every claim carries its proving command)

### V1 — CRITICAL: the gauntlet has NEVER been certified; the instrument, its input, and its
schedule all exist, and the verdict artifact has never existed. `libs/validation/positive_control.py`
(landed a5da892, 07-30 12:41) is complete and well-designed; `_audit_prepared.pkl` EXISTS at repo
root (6.1MB, Jul 26 — `ls -la _audit_prepared.pkl`); `scripts/certify_gauntlet.py` is installed in
the live crontab (`crontab -l | grep -c certify` → 1; `ops/crontab.manifest:485`, daily 08:21) —
and `reports/gauntlet_certification.json` DOES NOT EXIST (`ls` → No such file). Mechanics: the cron
entry was added 12:41 on 07-30, after that day's 08:21 slot, so zero scheduled fires have occurred
(`data/cro_ai_logs/certify_gauntlet.log` absent); the one manual attempt (07-30 12:11, per
`data/blind_spot_ledger.jsonl`) died with a 0-byte log — consistent with a killed process whose
block-buffered stdout never flushed, NOT with the docstring's "dying on FileNotFoundError" story
(the pkl was present the whole time). Consequence: "welded gate" vs "picked-clean space" — the
question the entire 434-tested/0-promoted record turns on — remains undecided by measurement.
**Action taken this audit: launched the certification myself** (`nohup .venv/bin/python -u
scripts/certify_gauntlet.py --seeds 3 > /tmp/certify_audit_20260731.log`), unbuffered so progress
is visible; per-control cost is dominated by the legacy `probability_backtest_overfitting` loop
(12,870 combos × 421 strategies per control), so completion is hours away; today's 08:21 cron fire
is a second chance. THE VERDICT LANDS IN `reports/gauntlet_certification.json` — the next cycle
must read it (success metric already defined in `data/decision_ledger.json`).

### V2 — HIGH: the desk's only gate-optimality artifact predates its own honesty fix and was
never regenerated. `reports/gate_histogram.json` was generated 2026-07-30T02:15Z; the fix that
makes "a total veto distinguishable from an absent gate" (2ec4fde — tally `seen`/`fail_tally` for
every gate) landed 21:37, ~19h LATER, and the script has no scheduled caller (`grep certify
scripts/run_cadence.py` → nothing for measure_gate_histogram; absent from crontab and
daily_research_cycle — agent trace). Net effect: the artifact's `pass_counts` silently OMIT
`dsr`, `reality_check`, and `beats_baselines` — the DSR gate, measured 07-29 at 100% reject, is
rendered as *absence* in the very artifact the GATE-OPTIMALITY DUTY mandates. The improved
instrument exists; the improved measurement does not. One command closes this:
`.venv/bin/python scripts/measure_gate_histogram.py` (not run this audit — CPU is committed to V1's
certification; 2 cores, load 1.7).

### V3 — HIGH: the GAP #71 fix (FDR screen) computes and is ignored — the fix for the
0-survivor screen does not decide anything. `screen_select` is called exactly once, inside
`CampaignGates.__init__` (`validation.py:379-380`); `.screen` is READ NOWHERE (agent trace:
only occurrences are the write); `screen_report` has zero production callers. `validate()`'s
significance gate still consumes `campaign.stepdown.rejected[column]` (`validation.py:444`) —
Romano-Wolf FWER across all N, the bar the fix's own docstring proves admits 0/420 at any window
(min adjusted p 0.522 min-length, 0.089 max-observation) and calls "a bar that RISES WITH
GENERATION — the exact thing the law forbids". So after the de-welding commits, the production
screen remains a 0-survivor instrument BY CONSTRUCTION, proven by its own artifact:
`reports/gate_histogram.json` per_candidate `rw_rejected: 0, both: 0, survivors: []`. The
comment at `validation.py:372-378` shows this is a deliberate two-step (report first, decide
later) — but no ledger row, due date, or ruling request for the second step exists (`grep -rn
screen_select data/recommendation_ledger.json` — nothing). A fix that never decides is F4's
displacement shape one layer deeper: built, computed, unconsumed.

### V4 — HIGH: even ignoring the multiplicity welds, ZERO of 420 candidates pass the six
candidate-attributed gates simultaneously. From `reports/gate_histogram.json` per_candidate
pass_counts: economic_mechanism 420, fragility 219, expected_value 251, cpcv 238, capacity 238,
walk_forward 176, pbo 209 — and `survivors: []`, `sole_blocker: {}` (every failing candidate
fails ≥2 gates). The conjunction of individually-informative gates (52-60% pass each) admits
nobody. Two readings, and the certification (V1) decides between them: (a) the 420 really are
noise — plausible, they are price-derived families; (b) the gate CONJUNCTION is welded even
where each gate is calibrated. Either way, the current stack has never admitted anyone through
the informative gates alone, so the marginal information of the dsr/RW welds on this campaign is
zero — they veto candidates already dead.

### V5 — HIGH: validate()'s capacity gate demands an edge absorb TWICE THE ENTIRE BOOK — the
constitutional inversion of L1.18a — currently masked by the $100B ADV default. Measured live
(`.venv/bin/python` calling the gate's own functions):
```
live equity read by gate: $18,676        (venue truth — the one-source fix works)
validate() capacity bar:  $37,351        (_CAPACITY_MULTIPLE_OF_EQUITY = 2.0, validation.py:68,119)
capacity_status ADMIT bar: $1,868        (_MIN_SLICE_FRACTION = 0.10, validation.py:67,143)
→ an edge with capacity = 100% of book: validate FAIL, capacity_status ADMIT (20× divergence)
```
L1.18a: "NO EDGE GETS THE WHOLE BOOK. Judge capacity against ONE SLEEVE. Comparing a candidate to
the full book assumes a single-strategy desk" — the gauntlet gate compares to 2× the full book.
Every §42-class edge (day-1 listing spikes, thin-pair funding: capacities $5-50k) fails validate()
at today's equity the moment ADV is plumbed honestly. TODAY the defect is masked: no production
caller passes `adv_usd` (agent trace: grep empty), so capacity_estimate runs on adv=$100B
(`validation.py:409`) and produces fake-huge capacities that clear even the 2× bar whenever
mean>0 (capacity 238/420 ≈ expected_value 251/420 — the F7 duplicate). INTERACTION: fixing F7
alone (plumb real ADV) would flip the mask off and turn the 2× bar into a systematic §42-edge
killer. The two defects must be fixed together, slice-band first.

### V6 — MEDIUM: validate() grew two documented parameters that are DEAD in its body.
`deployed_equity_usd` (`validation.py:416`, with a docstring explaining why None means "read the
live book") and `n_sleeves` (`:417`) are referenced NOWHERE in the function body (`:424-494` uses
neither; agent trace confirms no caller passes them either). The capacity gate reads equity through
`_min_capacity_usd()` internally. A caller passing `deployed_equity_usd=X` gets a silent no-op —
the exact "config-vs-outcome" trap: the signature promises a knob the body ignores. Either wire
them into the gate or delete them (L1.12: dead weight).

### V7 — CRITICAL (Stage-B): the ONLY path to capital gates on a fixed-sample statistic that is
peeked daily — realized false-ELIGIBLE rate is ~5× nominal, cohort-wise ~22% vs designed 5%.
`scripts/run_axis_shadows.py:138-143` flips ELIGIBLE when `nw_t >= holm_bar(m)` with
`_MIN_DAYS=40` the START of looking, not a pre-committed single look; the script runs on the
recurring cycle (`daily_research_cycle.py:116`) over a monotonically growing series. `holm_bar`
corrects cross-sectional multiplicity only. Monte Carlo this audit (20k null paths, unit-vol
daily, bar 2.61 = holm_bar(11, rank 1)):
```
correct one-sided nominal at 2.61:        0.00453
single look at day 40:                    0.0062   (×1.37 — the normal-quantile-on-n=40 effect)
ANY crossing, daily peeks day 40→90:      0.0223   (×4.9)
ANY crossing, daily peeks day 40→120:     0.0272   (×6.0)
cohort FWER m=11, single look (design):   0.049
cohort FWER m=11, daily peeks to 90d:     0.220
```
The sharpener: the desk ALREADY BUILT the peek-safe instrument — `libs/research/anytime_valid.py`
(e-process, Ville's inequality, honest self-assessment in its docstring) — and wired it only to
REPORTING sleeves (`run_shadow_8h.py:126`, `run_derivative_shadow.py:99` — both explicitly gate
nothing on it). The capital-path gate never imports it. Mitigants, honestly stated: ELIGIBLE has
zero promotion authority (human + gauntlet still follow), verdicts un-latch (an ELIGIBLE can
revert to FAILING next run), and rank=1 Bonferroni-for-all is conservative cross-sectionally. But
the forward clock is the desk's PRIMARY evidence standard under the two-stage law — its realized
type-I should be its designed type-I, and the fix is already on the shelf.

### V8 — HIGH (Stage-B): retirement LOWERS the surviving clocks' bar — the code's own invariant,
unenforced. Live proof: kimchi's retirement moved m 12→11 and holm_bar 2.64→2.61 for every
survivor (web/axis_shadows.json now carries `m_concurrent: 11, holm_bar: 2.61`; the stale
data/forward_slots.json still shows 12). `run_axis_shadows.py:59-61` states "a candidate that
legitimately accrued and lost must STAY in the denominator (attrition must never lower the bar)"
— but retirement is executed by deleting/commenting the axis out of `_AXES`, and NO script ever
writes the `RETIRED` verdict that `slot_registry.py:86` filters on (agent grep: only enum text
and prose produce the literal). Kimchi's case was argued as invalid-measurement (contaminated
timestamps), for which shrinking m is defensible — but the code cannot distinguish
invalid-measurement from failed-on-merits, so the invariant rests entirely on manual discipline.
One mechanism (a ledgered RETIRED-with-reason writer, m kept for merit-failures within a cohort)
closes it.

### V9 — MEDIUM (Stage-B): sequential slot recycling is unaccounted multiplicity — asserted as
law, never measured as risk. `MAX_FORWARD_SLOTS=12` caps CONCURRENT clocks; `run_alerts.py:280-288`
actively refills idle slots within 7 days; unbounded hypotheses therefore flow through ≤12 slots
over time, each cohort tested at holm_bar(≤12). The design docstrings assert this is the only
multiplicity that matters (`slot_registry.py:4-7`, `run_alerts.py:256-257`) — a defensible
POLICY (per-cohort FWER, like per-paper error control) but stated nowhere as the quantity it
actually controls: expected false ELIGIBLEs ≈ 0.05/cohort × cohorts/yr (at ~40-90d clocks and
full recycling, ~4-9 cohorts/yr → ~0.2-0.45 expected false ELIGIBLEs/yr at DESIGN alpha — and
~×4.9 that under V7's peeking, i.e. ~1-2/yr). Combined with V7 this is the honest number the desk
runs on. Write it down where the two-stage law lives; either accept it explicitly (with the
downstream gauntlet+human as the stated backstop) or add an across-cohort budget.

### V10 — MEDIUM: the recommendation ledger now UNDER-reports reality — implemented fixes sit
undisposed, so the backlog number is inflated and trust in the ledger erodes in both directions.
R0033 (per-candidate gates) shows "UNDISPOSED past grace, 1.8d" while the fix is LIVE in
production (`orchestrator.py:220` passes `campaign=`; four callers total). 69 rows | 12
implemented | 33 open — some unknown fraction of the 33 are R0033-shaped (done, unledgered).
The 07-29 finding was detection-outruns-disposition; the new twist is disposition-lags-
implementation: `recommendations.py implement --commit` is not being run when the work ships.
Cheap fix with compounding value: make the implementing cycle dispose in the same commit.

### V11 — MEDIUM: serial correlation is handled inconsistently across the desk's own primitives —
DSR/PSR assume IID exactly where the desk's stickiest streams are scored. `dsr.py:40` uses
√(n−1) with raw n (no autocorrelation adjustment — Bailey-LdP PSR is an IID formula);
`forward_stats.py` deflates n by the Bartlett VIF (clamped [1,5]); `kelly_shrink.py` takes a
`vif` parameter. Consequence: a funding-carry candidate with lag-1 autocorrelation ~0.2 (VIF
≈1.3) gets a DSR whose z is ~√1.3 ≈ 1.15× overconfident, while the SAME series' forward clock
correctly discounts it. Direction: anti-conservative on the backtest screen, conservative on the
forward clock — the screen is the loose side. Fix is three lines: n_eff = n/autocorr_factor(r)
inside probabilistic_sharpe_ratio, reusing the exact function the desk already trusts.

### V12 — MEDIUM: the Stage-A power gate's panel discount assumes cross-sectional correlation
= 1.0, discarding up to width× real evidence — and its "powered" label is a 50%-power criterion.
`axis_screen.py:103`: `n_eff = len(zv) / (horizon_days × panel_width)` — a 139-symbol × 310-day
panel counts as 310 obs, correct ONLY for a market-wide signal (kimchi: one series fanned out),
maximally wrong for genuinely cross-sectional per-symbol signals (independent draws discarded
139:1). The desk owns the standard fix (n_eff = n·w/(1+(w−1)ρ̄) with ρ̄ measured from the
signal panel itself). Second defect same line-block: `axis_screen.py:104` `min_detectable_ic =
1.96/√n_eff` is the significance threshold, i.e. detection at ~50% power; a real 80%-power
MDE is (1.96+0.84)/√n_eff ≈ 2.8/√n_eff — so "powered" overstates the screen's actual
sensitivity at the margin. (The horizon dimension of this gate — ic_min=0.03 fixed at every
horizon → 4,268-obs wall, h≥5 impossible — is owned by today's alpha-discovery report F5;
this finding adds the width-ρ and power-semantics dimensions.)

### V13 — LOW: production still runs White's RC (weaker) on the legacy path while Hansen's SPA
sits test-only; block length fixed at 10 everywhere. `validate():450` calls
`whites_reality_check`; `hansen_spa` (correctly implemented — studentized, consistent
recentering `-√((ω²/T)·2loglogT)`, `reality_check.py:57-83`) is reachable only through the
tests-only `Gauntlet`. `mean_block=10` remains hard-coded in reality_check.py, stepwise.py,
bootstrap.py defaults (U6, third audit in a row) — no Politis-White auto-selection, never
sensitivity-tested on the desk's own autocorrelation structure. Also minor: Romano-Wolf uses the
ORIGINAL-sample ω per candidate rather than re-studentizing per bootstrap draw
(`stepwise.py:189`) — asymptotically fine, slightly finite-sample-inaccurate; and my V7 MC
measured the normal-quantile-at-n=40 effect at ×1.37 (agent finding 6a quantified).

### V14 — LOW: event_study's two legs disagree on overlap conservatism. The parametric t uses
`n_eff = n·(1−overlap)` (`event_study.py:145,162`) but the bootstrap CI resamples all n events
IID (`:165`) — under heavy overlap the CI is too narrow while the t is (over-)conservative.
Both legs must pass, so the strict leg dominates today; if the t-side linear discount is ever
refined, the bootstrap side silently becomes the leak. Same-file strengths worth keeping: the
degenerate-variance guard (`:153`) and the pre-registered n_cohort/rank plumbing into holm_bar.

### V15 — MEDIUM: the cost/capacity model has never met the desk's own fills — simulation
realism runs on four uncalibrated constants. `capacity_estimate` (`libs/discovery/capacity.py`):
`impact_coefficient=0.1`, `participation_cap=0.01`, `turnover_per_year=50`, and `252.0` trading
days on 365-day crypto markets — none fit to measured execution. The desk HAS the calibration
data: live carry fills with a measured −51.74 bps round-trip price_pnl anomaly (R0026, open) and
a NAV attestation chain. `stress_costs.py` (the 1×/2×/3× cost-stress stage) remains DEAD — only
importer is the tests-only Gauntlet (agent trace). L2.10 (reality gap) names this chain
explicitly: backtest→live cost gaps are research input with risk-breach priority; today NO gate
consumes a measured cost surface. The Execution Reality Model the moat doctrine (L1.11) requires
is, at the validation layer, four constants from a textbook.

### V16 — MEDIUM: no gate anywhere consumes a ruin/survival statistic, while the survival rail
is stated in ruin terms. The L1.23 rail is "ruin ≤2%"; `monte_carlo_survival.py` is now WIRED
(stage14 via `app/readiness.py` and demo runners — an improvement since 07-29) but readiness is
not the gauntlet: `validate()`'s fragility gate is a skew/kurtosis/CVaR heuristic with arbitrary
weights (30/30/25/15, threshold 60 — `libs/discovery/tail_risk.py`) that has never been
validated against realized drawdowns or a simulated ruin probability. The desk's most
constitutional risk number (P(ruin)) is computed nowhere in the candidate path.

### V17 — LOW (hygiene): the trials-ledger story now has three inconsistent layers.
(a) hash-chained `trials_ledger`: 0 rows in every DB (unchanged, R0008 open 4.6d);
(b) orchestrator deflates DSR by `n_new + store.total()` — cumulative CANDIDATE-STORE count
(`orchestrator.py:79-81`), a reasonable stand-in that is neither the ledger nor documented as
its replacement; (c) four scripts still pass local batch size (`run_discovery.py:169`,
`run_xsec_funding_max.py:82`, `run_mt5_funding_bridge.py:123`, `run_crypto_portfolio.py:132`).
Three trial-counting regimes coexist; U5 (true desk-wide effective N) remains unknowable.

### V18 — LOW (Stage-B, reporting): `data/forward_slots.json` is a snapshot nobody refreshes —
`write_snapshot()`'s only caller is the module's `__main__` (agent trace) — so it froze 07-30
pre-kimchi-retirement showing 12/12 while every live consumer computes `derive_slots()` fresh
(11 slots, 1 idle). Decisions are unaffected; dashboards and humans read a wrong m. Today's
alpha-discovery report owns the idle-slot finding; the validation-stats addition is the root
cause (no cadence caller) and the guarantee that live bars are computed, not read from the
stale file.

## SIX PERSPECTIVES (explicit coverage)

**1. INTERNAL (measured, not configured).** The subsystem's measured state: certification
never produced (V1) — now producing; gate-histogram artifact stale vs its own fix (V2); FDR
screen computed-but-ignored (V3); 0/420 through even the informative-gate conjunction (V4);
Stage-B realized type-I ×4.9 nominal (V7, measured by MC this audit); first certification row:
true SR 2.0 fails both paths. The instrument-building velocity since 07-29 is genuinely high
(K1-K7); the MEASUREMENT velocity has not kept up — three instruments (certify, histogram,
reject-rescore) exist without ever having produced their number.

**2. EXTERNAL (how another world-class team would improve this).** (a) They would run the
positive-control certification CONTINUOUSLY (every gauntlet change gates on re-certification —
CI for the gate itself), not as a cron afterthought. (b) They would control FDR at the screen and
FWER only at promotion — exactly what screen_select implements and nothing consumes (V3).
(c) They would use group-sequential or anytime-valid boundaries on forward clocks (the tool is
in-repo, quarantined — V7). (d) They would calibrate impact/cost models to their own fills
quarterly (V15). (e) They would compute effective trials via clustering (correlated 420 ≠ 420
independent — the DSR's n_trials input) rather than raw counts.

**3. FUTURE (2-3y compute/AI).** The entire 420-campaign gate stack re-runs in minutes today
(374s/control is the LEGACY PBO's python loop; the sufficient-stats CSCV in stepwise.py proves
the 100× path exists in-repo). At that cost, the correct design is: every gate change triggers
automatic re-certification + histogram regeneration + reject-pile re-score — a standing
"gate-CI" organ. Statistical direction: replace fixed-sample forward clocks with e-process
boundaries everywhere (already built), making peeking free and clocks self-terminating; sample
length T (the true bar-setter, F8) attacked by reconstruction/backfill remains the binding
physical constraint no compute removes.

**4. CONTRARIAN (what if our assumptions are wrong).** (a) "The gauntlet is too strict" may be
the wrong frame entirely: if the 420 are genuinely noise (V4 survivors=[] through informative
gates alone), the welds cost NOTHING on this campaign — the cost lands only on future
better-generated cohorts; certification quantifies which world we're in. (b) The two-stage law's
premise "screen multiplicity cannot create phantom edges because nothing reaches capital"
under-weights the OPPORTUNITY cost channel: a welded screen starves forward slots (idle slot
today, alpha-discovery F2), so screen strictness DOES cost capital — through vacancy, not
phantom edges. (c) The desk treats forward evidence as gold-standard, but V7 shows the forward
clock's realized error rate is ~5× design — forward evidence is currently WEAKER per nominal
unit than backtest evidence at its stated alpha; the hierarchy "live>shadow>backtest" (L1.4) is
about bias, not about honesty of stated error rates, and right now the forward stage is the one
overstating its own guarantee.

**5. GREENFIELD (rebuild from validated knowledge only).** A rebuilt validation layer would
have: ONE trial ledger (not three regimes — V17), ONE capacity sufficiency definition (not two —
V5), FDR-screen → Holm-forward as the only two error-control points (dropping the DSR-0.95
binary and RW-FWER from the screen — they become ranking statistics), e-process forward clocks,
and a positive-control CI gate. Roughly: keep dsr/stepwise/screen_select/positive_control/
event_study/anytime_valid/kelly_shrink (the primitives are excellent), delete the welded
conjunction, wire the three unwired instruments. The historical baggage is the GATE TOPOLOGY,
not the primitives: 10 gates accreted where ~5 decision points belong.

**6. FRONTIER (recently possible, unexploited).** In-repo and dormant: e-process/anytime-valid
(built 07-2x, quarantined to reporting — V7); BY-FDR under dependence (built 07-30, unconsumed —
V3); Hansen SPA (tests-only — V13); min_track_record_length (exported, zero callers — the
T-planning tool for a desk whose binding constraint IS T). External, cheap, unadopted:
Politis-White automatic block length (U6); Romano-Wolf per-draw studentization; clustered
effective-trial counting (López de Prado's ONC exists in literature; the desk already clusters
nothing); conformal prediction for regime-conditional intervals — no current consumer, flagged
as watch-list only.

## NEGATIVE-SPACE SWEEP

Questions never asked, instruments never built, in this subsystem:

- **No gate has ever been A/B-tested against its own absence** on outcome (forward realized
  Sharpe of admitted vs rejected cohorts). The reject-shadow would be exactly this instrument —
  stub since built (U2).
- **P(ruin) is computed nowhere in the candidate path** (V16) while being THE constitutional
  rail. monte_carlo_survival wired only to readiness/demo.
- **No archived history of forward-clock verdicts** (U3): axis_shadows.json is overwritten in
  place; whether any clock ever flipped ELIGIBLE→FAILING (the false-positive tally) may be
  unrecoverable. The cheapest possible append-only line-per-run log would make Stage-B's
  realized error rate measurable forever.
- **Parameter sensitivity of the gate stack itself** has never been mapped: nobody knows how
  survivor count responds to _DSR_THRESHOLD, _CPCV_MIN_POSITIVE=0.6, fragility threshold=60,
  _MIN_SLICE_FRACTION=0.10 — the histogram measures gates at their set points only. A 1-page
  sensitivity sweep (vary each ±20%, count survivors) would show which thresholds are load-
  bearing and which are decorative.
- **No screen for cross-candidate correlation structure**: 420 candidates enter DSR as
  n_trials=420 independent; nobody has measured the effective number (eigenvalue/clustering) —
  it changes the E[max] benchmark by ~1 Sharpe unit (07-29 F8 sensitivity).
- **Distributional assumptions untested against own data**: PSR's skew/kurt adjustment assumes
  the Cornish-Fisher-style expansion holds; crypto daily returns with kurtosis>10 sit at the
  expansion's edge; never validated on desk data.
- **The languages/communities axis of this subsystem is empty but appropriately so** — no
  free-frontier data question lives in validation-stats; noted for completeness, no dig owed.

## 3. WHAT COULD MATTER MOST (ranked: impact × confidence / (cost × maintenance))

Per the read-only charter these are NOT self-rowed; the synthesis organ rows them (each maps to
a V/U finding above; several repeat OPEN ledger rows and are cited, not duplicated, per §41).

**X1 [zero cost — read the artifact].** `reports/gauntlet_certification.json` lands today (my
run or the 08:21 cron). Read it; it decides between "welded" and "empty" for the whole 434/0
record. If min_passing_true_sharpe(per-candidate) ≥ 5 → the gate is PROVABLY welded and X2 is
the desk's top validation priority with evidence attached. COMPOUNDING MULTIPLIER when made a
standing gate-CI: every future gauntlet change re-certifies automatically.

**X2 [the conversion unblocker].** Make `screen_select` DECIDE (V3): shortlist = BY-FDR q=5% on
raw_p; dsr + RW demoted from binary vetoes to ranking statistics; shortlist feeds the forward-
clock queue (expiry-ordered). This is the two-stage law implemented as designed — screen
controls a proportion, promotion keeps Holm. Needs a ruling (gate-topology change): page it
properly this time (F4's displacement lesson).

**X3 [Stage-B error honesty].** Fix V7 either way: (a) wire `anytime_valid.e_value` as the
ELIGIBLE condition (peek-safe, module exists, α preserved under daily looks), or (b) pre-commit
single-look days (40/90) and test only then. Also freeze m per cohort on merit-failures (V8) via
a ledgered RETIRED writer. Cheap; the instruments exist.

**X4 [one function].** Implement the lake-backed `_forward_score()` stub
(`run_rejection_rescore.py:30-38`) — activates the only false-negative instrument the desk has
(57 rejects waiting ~6 days; repeats OPEN intent of F3/U2, root cause now named).

**X5 [capacity coherence].** Replace validate()'s 2×-book bar with the `capacity_status` ADMIT
band (≥10% slice, ≥$200 exec floor) AND plumb real per-symbol ADV in the same change (V5+F7
interact: fixing either alone misfires). Delete or wire the dead `deployed_equity_usd`/
`n_sleeves` params (V6).

**X6 [measurement cadence].** Regenerate `reports/gate_histogram.json` with the post-2ec4fde
tally and schedule it (nightly or per-campaign) WITH a floor artifact per L1.0/L2.0 — gate
accept/reject rates are ratchet metrics that currently have no floor and no fence (V2; battery
move 10).

**X7 [three lines].** DSR autocorrelation honesty: n_eff = n/autocorr_factor(r) inside
probabilistic_sharpe_ratio (V11) — closes the screen-vs-forward inconsistency in the
anti-conservative direction.

**X8 [one tee].** Append-only forward-verdict history (one JSONL line per axis per run from
run_axis_shadows) — makes Stage-B's realized error rate measurable forever (U3). Trivial cost,
permanent evidence.

**X9 [cost realism].** Decompose the −51.74 bps carry round-trip anomaly (R0026, OPEN — cited
not re-rowed) and fit impact_coefficient/participation to own fills; revive stress_costs as a
per-candidate stage (V15/U8). This is the L2.10 reality-gap chain's validation-layer terminus.

**X10 [hygiene with compounding value].** Disposition-in-same-commit: the cycle that ships a
ledgered fix runs `recommendations.py implement --commit` in that commit (V10). Restores ledger
trust in both directions.

Deliberately NOT recommended: loosening any threshold by opinion (the certification decides);
building new statistical machinery (the shelf is full — V3/V7/V13 show built-and-unwired is the
failure mode, not missing tools); touching Holm/forward bars (L2.8a evidence restraint).

## 4. WHAT WE TEST NEXT (concrete, with success criteria)

**T1 — Read the certification** (owner: next cycle, cost: minutes). Success: pass_rate table +
null FPR + sole-blocker counts read and acted on. Branch: min_passing ≥5 → X2 escalates with
proof; ≤3 → gates are calibrated and the 420 are evidence about generation, redirecting effort
to new axes (which SCREEN-ON-DISCOVERY already prioritizes). Retirement condition: standing
gate-CI (X1) makes this a permanent regression test, not a one-off.

**T2 — Un-welded conjunction re-score of the 420** (cost: one script run; U4). Re-run the
histogram with dsr/RW as ranking-only and screen_select deciding. Success criteria: shortlist
∈ [1, 21] (q=5% of 420) → queue by capacity runway; shortlist = 0 → "empty space" gains real
evidence beyond the welds. Failure mode: shortlist >> slots — bounded by the 12-slot cap and
expiry ordering; no phantom risk (zero promotion authority).

**T3 — Peek-safe gate A/B** (cost: hours; V7). Replay existing clock series under (a) current
daily-peek rule, (b) e-value≥100 rule, (c) single-look-at-40/90. Success: chosen rule's realized
α within 20% of nominal on 20k-path MC calibrated to the desk's actual nw pipeline (vif
included). Validation method: the MC harness from this audit, extended with AR(1) nulls.

**T4 — Panel ρ̄ measurement** (cost: hours; V12/U7). Measure mean pairwise cross-sectional
correlation of screen signals on the 139-symbol funding panel; adopt n_eff = n·w/(1+(w−1)ρ̄)
if synthetic-panel validation (known ρ) reproduces nominal type-I within 20%. Retirement: if
measured ρ̄ > 0.8, current ρ=1 discount is approximately right — document and keep.

**T5 — Block-length sensitivity** (cost: one overnight run; U6). RW adjusted-p on the real 420
at mean_block ∈ {5, 10, 20, 40}. Success: min_adj_p moves < 0.05 across the grid → U6 closes as
"insensitive, mean_block=10 certified"; else implement Politis-White. Either exit closes a
three-audit-old unknown.

**T6 — Stage-B verdict history** (cost: trivial; X8). After 30 days: first realized
ELIGIBLE→FAILING tally. Success metric: the count exists; expectation under design ≈ 0-1.

## PROACTIVE BATTERY (generative moves run + what each produced)

1. **Contingency before failure:** certification's single input `_audit_prepared.pkl` has 0
   writers (named in its own docstring); replacement named — commit a builder or the
   null_cohort fallback already sketched in the BLOCKED path. → V1 resolution path.
2. **Adjacency:** the V2 shape ("artifact predates its own fix / organ exists, output empty")
   swept across the subsystem → found 4 instances: certification (V1), histogram (V2),
   reject-rescore stub (U2), forward_slots snapshot (V18). This class — instrument built,
   measurement never produced — is the sweep's central theme.
3. **Config vs outcome:** demanded the artifact for every claimed capability: certification
   (absent → LAUNCHED IT), cron (installed, zero fires, log absent), reject scores (absent →
   stub root-caused), histogram (stale). → V1, V2, U2.
4. **Regression sweep — what did the 07-30 fixes make worse:** the per-candidate migration made
   certification ~374s/control (legacy-PBO python loop) — slow enough that a killed run left no
   trace; and shipping R0033's fix without disposing R0033 made the ledger WRONG (V10).
5. **Cost inversion:** nothing paid in this subsystem; checked for free-primary repackaging —
   none found. Reported as empty, per doctrine.
6. **Generalise the rule:** "attrition must never lower the bar" (axis clocks) generalized to
   the other two slot sources — standing sleeves and derivative sleeves retire by file edits
   with the same unenforced invariant. → V8 scope extension.
7. **Autonomy check:** the BLOCKED-artifact recovery (2ec4fde) has been configured, never SEEN
   to work — zero cron fires since it landed; first live test is today 08:21. → flagged in V1.
8. **Negative space:** dedicated section above; 7 items, 2 promoted to X8/X9.
9. **Scope the negative result:** "0/420" scoped into route-vs-capability (V4's two readings);
   "SR-2 control fails" scoped to exactly the two multiplicity gates, not the informative six.
10. **Ratchet check:** the subsystem owns NO ratcheted metric — gate accept rates, certification
    min-passing-SR, Stage-B realized error all floor-less. → folded into X6.

## AUDIT SELF-NOTES (honesty)

- Read-only respected with two deliberate exceptions, both measurements writing their DESIGNED
  artifacts: this report, and launching `certify_gauntlet.py` (writes
  reports/gauntlet_certification.json, gitignored; its own docstring: "this script measures, it
  never promotes"). The MC in V7 wrote nothing. Synthesis should sanity-check that judgment.
- NOT done: histogram regeneration (2 cores, load ~1.7, certification owns the CPU — one command
  for the next cycle); certification completion within this audit window (it continues in
  background; partial first row reported); Politis-White implementation (proposed as T5, not
  built — read-only).
- Overlap management: today's alpha-discovery report owns the idle-slot and power-wall findings
  (its F2/F5); this report cites them and adds the validation-mechanics layers (V8/V12/V18)
  rather than re-deriving. The 07-29 validation-stats report's F1-F13 were not re-litigated;
  every re-cited item carries its delta state in §0.
- Confidence caveat: the V9 false-ELIGIBLE/yr estimate assumes full slot recycling at 40-90d
  cadence; actual cadence may be slower (slots have sat idle) — the estimate is an upper band
  until X8's history exists.
- The 07-30 validation-stats skeleton (1.9KB, never completed) should be marked superseded by
  this report to stop the runner re-queuing it — synthesis decision, not mine.
