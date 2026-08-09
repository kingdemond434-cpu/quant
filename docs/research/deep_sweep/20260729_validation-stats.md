# WEEKLY DEEP COLD AUDIT — validation-stats — 2026-07-29

_Retry of failed run (prior attempt died BRAIN_AUTH_FAILED at 493 bytes). This run completed._

**Subsystem scope:** selection bias, multiple testing, parameter sensitivity, sample dependence,
walk-forward + CV methodology, regime robustness, distributional assumptions, uncertainty
propagation, capacity/cost modeling, simulation realism, MC design, bootstrap quality,
structural breaks. Prime quarry: zero-information gates, rigorous methods sitting as dead code,
DSR bar optimality.

**Headline (one paragraph).** The desk's statistical library is institutional-grade and its
Stage-A/Stage-B screening discipline is genuinely excellent — but the *campaign validation path*
(`libs/autodiscovery/validation.py`) is a nine-gate stack in which **five gates carry zero or
near-zero information** (two always-accept, two campaign-constant always-reject, one
effectively-unclearable DSR), the cumulative trials ledger has **0 rows everywhere**, the
gate-leak detector has been **inert since built** (57/57 rejects unscored), the best rigorous
methods (purged CPCV, Hansen SPA, FDR, lockbox, MC-survival, structural breaks) are **dead
code**, and — the audit's sharpest new result — **the DSR gate at the current campaign design
(T=310 days, N=420 trials) mathematically requires a TRUE annualized Sharpe ≈ 5 to pass**, so
the 420/0 record was overdetermined: three independent gates each guaranteed zero survivors.
The binding constraint is no longer discovery of these defects (the desk found most of them
itself in the last 72h) but **disposition throughput**: 31 of 36 ledgered recommendations sit
undisposed past grace, and the one decision that reopens the pipeline exit (R0033) has been
displaced off the principal's action page.

---

## SCORES

- **current_capability_pct: 40%** — primitives 90%, screen harness 85%, campaign gauntlet ~15%
  (five degenerate gates, empty funnel), calibration loop 0% (all instruments inert or starved).
- **practical_ceiling_estimate: 90%** — nothing here needs new science; every fix is wiring,
  calibration, or one ruling.
- **ceiling_gap: 50 points.**
- **opportunity_cost_1y:** every campaign run until R0033+DSR-redesign is a guaranteed-zero pass
  (~all Stage-A compute on the campaign path produces no survivors by construction); the
  forward-slot pipeline starves at 4/12 slots occupied while the screen that feeds it passes
  nothing. If even 1–2 real edges/year exist in the searched space at ann SR 1.5–2.5 (the
  kimchi screen suggests the space is not empty), the current design forfeits all of them at
  Stage A. Compounding cost of a year of empty funnel: the entire discovery objective.
- **confidence: high** on every finding below (each carries its command); **medium** on the
  ranking of fixes.
- **unknown_unknown_score: medium-low** for this subsystem specifically — three independent
  self-audits (07-26 sweep, 07-28/29 cycles, this sweep) now converge on the same defect set,
  which is evidence the map is near-complete; residual risk concentrates in *silent metric
  consumers* (F11 class) not yet enumerated.
- **info_gain_if_investigated: highest** for the rejection-shadow forward scoring (F3) — it is
  the only instrument that can measure the false-negative rate empirically.
- **expected_alpha_contribution: high, indirect** — this subsystem produces no alpha; it decides
  which alpha survives. Right now it decides "none", deterministically.
- **expected_compounding_contribution: very high** — gate calibration + trial accounting are
  multipliers on every future campaign, and the fix set is mostly one-day builds.
- **CEILING EXPANSION:** the ceiling assumption is *organizational* (one principal ruling
  gates activation; disposition throughput is single-threaded through brain cycles), not
  technological or methodological. What would move it: batch rulings (one page, N decisions),
  and letting evidence-preserving fixes (per-candidate attribution at unchanged thresholds)
  ship under a pre-registered revert trigger instead of a pre-approval.

---

## 1. WHAT WE KNOW (validated strengths, each with proving command)

**S1. The statistical primitive library is genuinely institutional-grade.** Read in full this
sweep: `libs/validation/dsr.py` (Bailey–López de Prado PSR/DSR with skew/kurtosis adjustment),
`pbo.py` (true CSCV PBO, C(16,8) splits, logit ranks), `reality_check.py` (White's RC **and**
Hansen's SPA with studentization + consistent recentering `-sqrt((ω²/T)·2loglogT)`),
`bootstrap.py` (moving-block + stationary bootstrap; correctly refuses IID resampling),
`cpcv.py` (combinatorial purged CV with purge + embargo), `forward_stats.py` (Newey–West
effective-N t-stat clamped [1,5]; Holm step-down with pre-registered-primary exemption). No
hand-rolled significance in any of these files.

**S2. The Stage-A axis-screen harness encodes five separately-dated statistical injuries as
baked-in rails.** `libs/research/axis_screen.py`: angle-20 de-contamination (killed
coinbase/turkey), SUSPECT-LOOKAHEAD ceiling with two-factor corroboration (killed bithumb
IC-0.72; un-killed the real kimchi lead), horizon-correct annualisation (2026-07-26 fix: noise
scored Sharpe 0.55 at 20d before), panel-width effective-N (139-symbol panel: t=3.5 was really
t=0.35), and power gating BOTH branches (SCREEN-UNDERPOWERED can neither kill nor start a
clock). Clock starts only on powered SCREEN-INTERESTING.

**S3. Stage-B forward multiplicity is real and honest.** `web/axis_shadows.json` (08:46Z
today): 4 clocks ACCRUING with `nw_t`, `holm_bar: 2.24` at `m_concurrent: 4`,
`min_forward_days: 40`, "ELIGIBLE ≠ deployment". Slot guard counts all three slot sources since
yesterday's fix and fires on the under side too (7bc1f7b). `run_axis_shadows.py:120` consumes
`holm_bar(len(_AXES), rank=1)` — Bonferroni-at-rank-1 for all axes, marginally stricter than
full Holm step-down: conservative, honest.

**S4. Screen-level trial accounting exists and is exemplary.**
`reports/axis_screens/_raw_trials.json`: n_trials=48, every target/horizon/transform cell
logged with name pattern `M1_ls_level|xsrank|rel|1d`, panel provenance, IC and both Sharpes per
cell. The wikipedia screen artifact declares its ~1h look-ahead, runs every construction
+1d-lagged as falsification, uses non-overlapping 5d/20d returns, and skips graveyarded cells
by name. This is the target/horizon sweep duty operating as designed — at the screen layer.

**S5. Negative results are banked.** `data/sor_research.sqlite::research_memory` = 143 rows (93
construction-failures, 26 hypothesis-failures with causes; last entry 11:11Z today — the kimchi
IC +0.2249 ~73%-timestamp-artifact retraction). Command:
`SELECT category,result,COUNT(*) FROM research_memory GROUP BY 1,2`.

**S6. Anytime-valid inference is wired where peeking actually happens.**
`libs/research/anytime_valid.py` imported by `run_shadow_8h.py`, `run_derivative_shadow.py`
(`grep -rln`). Daily-peeked shadow clocks use always-valid bounds.

**S7. Uncertainty propagates into sizing correctly.** `libs/risk/kelly_shrink.py`: Lo (2002)
SE, Bayesian shrinkage `S²/(S²+SE²)`, and a `vif` parameter so the SE lives on the same
effective sample as the NW t-stat — sizing cannot over-trust sticky returns the significance
test distrusts. Plus scale-dependent first-inversion probation. This is the strongest
uncertainty-propagation artifact on the desk.

**S8. Yesterday's campaign-constant discovery (7bc1f7b) was self-found, correctly diagnosed,
and correctly not self-activated.** PBO 0.6159 / RC p 0.4220 measured on the real 420-matrix
vetoed all 420 at any quality; one true SR=3 winner flips 60/60 nulls to PASS under old gates.
Fix (`stepwise.py`: per-candidate CSCV + Romano–Wolf, FWER 5%, thresholds unchanged, 13 tests,
legacy path byte-identical) awaits the principal per rail-revision protocol. `git show 7bc1f7b`;
GAP #87.

---

## 2. WHAT WE DON'T KNOW (ignorance ledger)

**U1. The false-negative rate of the whole gauntlet.** Zero rejects have ever been forward-
scored (`web/reject_shadow.json`: "57 eligible rejects, NONE re-scored yet";
`data/reject_forward_scores.json` does not exist). Until F3 is fixed, "the bar kills real
alphas at rate X" has no measured X in either direction.

**U2. Whether ANY searched family contains a real edge at realistically-passable size.** The
420/0 record is now known to be an instrument artifact (three independent always-reject gates),
so the standing read "price space is picked clean" is **unsupported in either direction** by
the campaign record. The 420 candidates have simply never been evaluated by an instrument
capable of passing anything.

**U3. Which downstream consumers read the inflated `annual_sharpe`** (F11). Found:
`run_rejection_rescore.py:54` (biases rescore priority), candidate store, crypto_adapter
reports. Not exhaustively enumerated beyond grep.

**U4. Regime robustness of anything validated.** No validation stage conditions on regime
(`grep -c "regime" scripts/run_xsec_funding_max.py` → 0; `validate()` has no regime gate;
`libs/autodiscovery/regime.py` exists for generation, not validation). Whether survivors would
survive *per-regime* is untested by construction.

**U5. True desk-wide effective trial count.** trials_ledger empty (F2); screen trials logged
per-artifact but never aggregated. The honest cumulative N for any DSR anywhere is unknown —
only per-batch lower bounds exist.

**U6. Bootstrap block-length adequacy.** `mean_block=10` fixed everywhere (`reality_check.py`,
`bootstrap.py` defaults); no Politis–White automatic selection; never sensitivity-tested on the
desk's actual return autocorrelation structure.

---

## FINDINGS (all verified this sweep; each feeds outputs 3–4)

**F1 — The per-gate accept/reject histogram the GATE-OPTIMALITY DUTY mandates exists nowhere
as an organ; computed fresh, it shows 4 of 9 gates at exactly 0% or 100%.** Over all 57 stored
candidates (`sor_autodiscovery.sqlite::research_candidates`, two campaigns):

```
economic_mechanism  0% fail   <- checkbox: bool(hypothesis.failure_modes)
pbo                 0% fail   <- campaign constant (loose side here; 0.027-0.172)
dsr               100% fail   <- stored dsr value 0.0000 on EVERY row
reality_check     100% fail   <- campaign constant (p=0.095 / 0.403 per campaign)
capacity           93% fail   <- median capacity_usd = 0 (≈duplicate of EV sign, F7)
cpcv 82% / walk_forward 82%   <- near-duplicates of each other (F13)
expected_value 77% / fragility 68%
```

The 07-26 cycle's probe (R0016) measured the 420-campaign once; its synthetic arm is mis-wired
(R0017, undisposed) and no recurring artifact exists (`grep -rln "gate_histogram|per_gate"
scripts` → nothing). This table took ~30 lines of read-only SQL. It should be a nightly organ
with a ratchet.

**F2 — The hash-chained trials ledger has 0 rows in all 10 databases; production DSR deflates
by local batch size only.** `trials_ledger rows: 0` in every `data/*.sqlite` (python sqlite
scan). Sole writer `Gauntlet._resolve_n_trials` (`gauntlet.py:89`); `Gauntlet(` constructed
only in `tests/validation/test_gauntlet.py`. Callers pass `n_trials=len(lib)`
(`run_discovery.py:156`, `run_xsec_funding_max.py:80`). The 7× safety multiplier exists only in
dead code. Mitigant: two-stage law (promotion pays only Holm forward slots). Cost: every
"trials-adjusted DSR" line in reports overstates its own deflation; already rowed as R0008 —
**undisposed 3.2d**.

**F3 — The rejection-shadow audit (the gate-leak detector) has been inert since built.**
`web/reject_shadow.json` (08:46Z): 57 eligible, 0 scored, `data/reject_forward_scores.json`
absent. The only empirical instrument for "does the bar kill real alphas" has produced zero
verdicts ever. Highest info-gain-per-day build in the subsystem (see output 4, X1).

**F4 — The candidate-attributed gates are built, tested, dormant — and the ruling that
activates them has been DISPLACED off the principal's page.** No production caller passes
`campaign=` (`grep -rn "campaign=" libs scripts app` → one unrelated kwarg). 7bc1f7b says
"Paged: data/PRINCIPAL_ACTION.md §1, YES/NO"; that file (rewritten 16:11Z today for the
carry-book absorbing-state decision) now contains **zero** mentions of
stepwise/R0033/romano/cscv (`grep -c` → 0). R0033 status: open, no disposition, no due
(`recommendation_ledger.json`). The single-slot page file has no queue — the same
event-vs-event displacement shape as the 07-28 pager lesson, one layer up.

**F5 — Rigorous methods sitting as dead code** (importer scans, excluding tests/own package):
`cpcv.py` (real purged CPCV) **0 importers** — production "cpcv" gate is
`_cpcv_positive_fraction` (`validation.py:35`): unpurged `array_split` sign-check;
`lockbox.py` **0**; `fdr.py` (Benjamini–Hochberg) **0**; `baselines.py` **0**;
`libs/research/stationarity.py` (structural breaks) **0**; `Gauntlet` 7-stage orchestrator
(Hansen SPA, stress-costs ×3, lockbox stage, trials ledger) **tests only** — production swapped
SPA for weaker White RC and dropped stress-cost + lockbox stages;
`libs/discovery/monte_carlo_survival.py` (ruin/survival MC incl. parameter perturbation) —
`libs/discovery` imported only by `autodiscovery/validation.py` for capacity+tail_risk, so the
MC engine and `cagr_optimizer` are unreachable from any script. Already rowed as R0001 —
**undisposed 3.2d**.

**F6 — The revalidation trigger system is a switchboard with no wires.**
`RevalidationController` (STRUCTURAL_BREAK/DRIFT/SIGNAL_DEAD hard triggers, fail-closed
production-capital gate): zero production constructors (`grep -rn "RevalidationController"`
→ only `__init__` exports). No organ computes a structural-break statistic (stationarity.py
dead). The fail-closed design has nothing to close on. Also `WalkForwardEngine` refits nothing
(returns-only), so "walk_forward" ≡ later-window sign consistency ≡ the fake-cpcv gate (F13).

**F7 — Capacity gate: `adv_usd` defaults to $100B and no caller overrides.**
`validation.py:113`; `grep -rn "adv_usd" scripts` → no run_* passes it. Gate binds only through
the candidate's own mean (capacity_usd=0 when mean≤0 → 93% fail ≈ EV-sign duplicate); for any
positive-edge candidate it is effectively unbounded — zero information precisely on survivors,
where capacity is supposed to bite. Real ADV exists in the lake and is unplumbed.

**F8 — THE DSR BAR, ANSWERED (the question GAP #87 explicitly deferred: "dsr … needs its own
investigation").** Measured on the real reconstructed 420-candidate matrix
(`_audit_prepared.pkl`, T=310, N=420, D1 crypto):
- Cross-sectional per-period Sharpe sd = 0.049 (ann 0.94) — **consistent with pure estimation
  noise** (1/√310 = 0.057 daily): the deflation variance is honest, not junk-inflated.
- Implied benchmark `sr0` = expected max of 420 no-skill trials = **ann Sharpe 2.81**.
- Injecting exact-sample-SR winners into the real batch through production's own call
  (`deflated_sharpe_ratio(w, n_trials=421, sharpe_estimates=…)`): **true ann SR 3.0 → DSR 0.556
  FAIL; 5.0 → 0.968 PASS.** With honest synthetic cohorts the minimum-passable TRUE Sharpe is:

```
T(days) |  N=12 | N=50 | N=420 | N=2000
    310 |  4.28 | 4.95 |  5.32 |  5.60
    730 |  3.09 | 2.89 |  3.31 |  3.61
   1500 |  1.91 | 2.02 |  2.40 |  2.49
   2500 |  1.55 | 1.71 |  1.76 |  1.92
```

Three conclusions. (a) The threshold is not mis-set; the **campaign design** is: at T=310 no
achievable crypto edge net of costs (ann SR ≲ 3) can pass at any N — the third welded gate,
welded by *sample length*. (b) **T dominates N logarithmically**: quadrupling history buys ~3
Sharpe units of bar; cutting trials 35× buys ~1. The reconstruction/backfill program is
therefore the single highest-ROI validation lever the desk owns — this quantifies it. (c) DSR
at 0.95 as a *binary screen* contradicts the two-stage law: proof lives in forward slots, so
Stage A should **rank** (top-K by DSR → forward clocks) rather than demand 95% proof from 310
days. Also: 7 of the 420 columns are all-zero (dead strategies), skew/kurtosis → NaN → DSR NaN
→ silent auto-reject; harmless today, but NaN-as-False is an unlabeled code path.

**F9 — The EV gate rejects ~100% of honestly-scored ideas and its self-scoring loop is
starved.** `alpha_economics.py`: `_EV_THRESHOLD=0.05` vs formula ceiling with honest inputs
(p≈0.24 after new-axis prior, S=0.5, orth≤1, breadth_f≤1.73, effort 8h) → EV ≈ 0.01–0.03.
Confirmed live: 4/4 novel hypotheses EV-rejected at 0.005–0.010 (R0034, open). The near-miss
band (`run_axis_generate.py:138`, ≥0.02 → low-rank queue) catches part of the range but
yesterday's 4 fell below even that. Meanwhile `data/ev_gate_audit.json` — the designed
recalibration loop — has **3 entries in 18 days** against its own n≥50 recalibration
condition: at this rate the priors become posteriors in ~10 months. Also `line 155`
`ev >= QUEUE_MIN or ev >= NEAR_MISS` is redundant (≡ `ev >= NEAR_MISS`) — harmless, but the
QUEUE_MIN branch is unreachable as a condition.

**F10 — THE BINDING CONSTRAINT IS DISPOSITION THROUGHPUT, NOT DETECTION.**
`python3 scripts/recommendations.py report`: **36 total | 3 implemented | 1 rejected | 1
scheduled | 31 open**, nearly all flagged `UNDISPOSED past grace` — including R0001 (wire
CPCV/SPA/FDR/lockbox — found by the 07-26 sweep, 3.2d), R0008 (trials ledger, 3.2d), R0016/17
(gate-optimality probe + its broken synthetic arm, 2.8d), R0023 (EV gate, 1.0d), R0033/34
(yesterday). Three independent audits have now *re-discovered* overlapping defect sets faster
than one brain disposes them. §41's own defect definition is firing continuously. Every
finding below that repeats an open row cites it rather than re-rowing (per §41 no-duplication).

**F11 — `annual_sharpe` is annualized with a hardcoded hourly constant on daily data, and a
live consumer uses it.** `validation.py:28` `_PERIODS_PER_YEAR = 24*260`; `:159`
`annual_sharpe = sr·√6240` — the 420-campaign feeds **D1** returns (`_audit_gate_probe.py`
rebuild uses `Timeframe.D1`), overstating annual Sharpe ×√(6240/365) ≈ **4.1×**. Consumers:
candidate store, `crypto_adapter.py:181`, `reports.py:42`, and
`run_rejection_rescore.py:54` — which takes `max(oos_sharpe, annual_sharpe)` as the rescore
metric, so rescore prioritization inherits the 4.1× inflation on daily campaigns while hourly
campaigns (MT5) are correct. One constant serving two frequencies must be a parameter.

**F12 — Bespoke reconstruction verification bypasses the audited gate (adjacency).**
`gate_calibration.reconstruction_verified` (the refuse-on-disagreement backfill interlock) has
**0 callers**; `backfill_oi_ls_oos.py:66` implements its own `diff_verify()` (correlation +
relative-diff). Discipline followed, shared audited gate bypassed — two implementations of one
safety check, one of them dead. Same shape the desk fixed for axis screens by centralizing
into `axis_screen.py`.

**F13 — Gate redundancy: nine names, ~six measurements.** cpcv ≈ walk_forward (both
later-window sign consistency, both 82%); capacity ≈ expected_value on non-survivors (93% vs
77%, capacity=0 iff mean≤0 given the $100B ADV default); economic_mechanism ≡ constant-true.
The stack's apparent depth overstates its information by a third.

---

## SIX PERSPECTIVES (explicit coverage)

**INTERNAL (measured, not configured):** F1–F13. Sharpest: the funnel's exit has been closed
by three independent mechanisms at once (campaign constants ×2 + DSR-by-design), so throughput
metrics upstream (hypotheses generated, screens run) were measuring motion into a dead end.

**EXTERNAL (how a world-class desk would differ):** (1) One canonical validation path — not a
rigorous `Gauntlet` used by tests and a flatter `validate()` used by production (F5). (2)
Gate telemetry as a first-class nightly artifact with alerting on degenerate rates (F1). (3)
Rejected-candidate forward tracking as standard practice (F3) — top labs treat the reject
stream as free experimental data. (4) Campaign design chosen from a power calculation (the F8
table IS that calculation) before spending compute — pre-registered N, T, and passable-SR,
instead of discovering post-hoc that the design admits nothing.

**FUTURE (2–3y compute/AI):** the F8 surface inverts the workflow — with cheap LLM-driven
generation, N is nearly free while T is physical; the desk should spend engineering on
*history manufacture* (reconstruction, cross-venue splicing, regime-labeled synthetic
extension via the dead MC engine) and stop economizing on trial count. A future redesign
validates *mechanisms across many expressions jointly* (hierarchical/panel evidence pooling,
partial pooling across symbols) rather than 420 independent single-series tests — the same
data supports a far lower bar when evidence is pooled (panel width already enters
`axis_screen` correctly; the campaign path ignores it).

**CONTRARIAN (test the core assumptions):** (a) "The gauntlet is strict, therefore safe" —
falsified by 7bc1f7b: the same constants that reject everything flip to accepting 60/60 nulls
when one winner enters the batch; strictness without attribution is a coin-flip on batch
composition. (b) "420/0 proves the space is empty" — unsupported; the instrument could not
pass anything (F8). (c) "More gates = more safety" — F13: three of nine gates re-measure the
same quantity; redundant correlated gates add rejection variance, not information. (d) "The
DSR threshold is the conservative choice" — at T=310 it converts to "reject all", which under
L1.23's symmetric law (timidity on proven edge = recklessness) is not conservative, it is a
silent full-stop on discovery.

**GREENFIELD (rebuild with only validated knowledge):** keep: primitives (S1), axis_screen
(S2), forward slots + NW/Holm (S3), kelly_shrink (S7), research_memory. Rebuild as ONE
pipeline: mechanism-priored generation (small N) → Stage-A screen with per-artifact trial log
auto-aggregated into a global counter → ranked top-K into forward clocks (Holm) → shrunk-Kelly
sizing. That is ~5 modules; the current path spans `libs/validation` (23 files, 8 dead),
`libs/discovery` (mostly unreachable), `libs/autodiscovery`, and `libs/stage14/15` — historical
strata, not architecture. Baggage score: high; replaceability: high (the good parts are
importable as-is).

**FRONTIER (recent public methods not exploited):** (1) **Romano–Wolf is already built
in-house** — the frontier item is activation, not discovery. (2) e-values/e-processes:
`anytime_valid.py` exists — extend it from shadow clocks to the campaign screen and the gates
compose by multiplication (no Holm bookkeeping). (3) Politis–White automatic block length for
the stationary bootstrap (fixed `mean_block=10` today, U6). (4) López de Prado's
"false strategy" theorem gives a closed-form for the F8 design question — expose it as a
pre-campaign power calculator so no campaign launches whose passable-SR exceeds the plausible
edge. All four are ≤1-day builds on existing code.

**NEGATIVE-SPACE SWEEP (never asked/never built):** no regime-conditional validation gate
(U4); no parameter-sensitivity stage in the production path (the perturbation code exists —
dead, F5); no per-gate telemetry organ (F1); no forward scoring of rejects (F3); no aggregation
of screen-level trial logs into cumulative multiplicity (F2/S4 gap); no pre-campaign power
check (F8); no automatic block-length selection (U6); no Execution-Reality-Model calibration
from own fills — `mt5_calibration.py` says slippage "is a prior … until calibrated on real
fills" and no fill-calibration artifact exists (`grep -rln "execution_reality|slippage_model|
fill.*calibrat"` → nothing; constitutional moat pillar, unbuilt; the new
`run_venue_reconcile.py` is the first organ that could feed it).

---

## 3. WHAT COULD MATTER MOST (ranked: impact × confidence / (cost × maintenance))

1. **Re-page R0033 and rule it** (F4). Impact: reopens the pipeline exit; cost: minutes (the
   case is written; the page was simply displaced). Include the page-queue fix so a single-slot
   file can never displace a pending ruling again (append sections, never overwrite; or a
   `pending_rulings.json` the pager renders in full). COMPOUNDING MULTIPLIER: every future
   ruling survives contention.
2. **Wire reject forward-scoring** (F3, X1 below). The only instrument that measures
   false-negatives; unblocks `reject_shadow`, `reject_rescore`, and the EV-gate audit ledger
   (three starved organs share this one input). COMPOUNDING MULTIPLIER.
3. **Pre-campaign power calculator + campaign redesign** (F8). Never again launch a campaign
   whose minimum-passable true SR exceeds ~2.5; prioritize T-extension (reconstruction) over
   N; pool panel evidence. Converts the audit's table into a standing gate on campaign specs.
4. **Per-gate telemetry organ with ratchet** (F1). Nightly histogram over the candidate store;
   alert on any gate <5% or >95% over a rolling window. Cheap; makes every future gate defect
   self-announcing. COMPOUNDING MULTIPLIER.
5. **Aggregate screen trial logs into a global multiplicity counter** (F2 + S4): a 20-line
   collector summing `_raw_trials.json` + research_memory hypothesis rows into
   `data/global_trial_count.json`, consumed as `n_trials` floor by every validate() caller.
   Populates-or-retires R0008 honestly.
6. **Fix `_PERIODS_PER_YEAR`** (F11): make PPY a `validate()` parameter; correct
   `run_rejection_rescore`'s metric. One hour, removes a 4× reporting bias.
7. **Dead-code disposition** (F5, R0001): either wire (SPA→production, CPCV→replace fake-cpcv,
   MC-survival→fragility stage, FDR→screen-level q-values) or delete per L1.12 — carrying
   "rigor we don't run" misleads every reader of the tree, including audits.
8. **EV gate recalibration** (F9/R0034): back-solve the threshold from known-good/known-
   marginal historical ideas (same method as the gate fix); until then route sub-threshold
   ideas to the near-miss queue instead of REJECT.

**Interaction note:** items 2, 4, 5 are the instrumentation that makes item 1's activation
*verifiable* — flipping stepwise without them means not knowing whether the new per-candidate
rates are sane. Ship instrumentation first or simultaneously.

---

## 4. WHAT WE TEST NEXT (concrete, with success criteria)

**X1 — Score the 57 rejects forward (1 day).** For each reject in the candidate store, re-run
its frozen rule on data after `created_at` (the run_* scripts already contain every returns
pipeline), write `data/reject_forward_scores.json`, let the existing audit judge. Success:
`web/reject_shadow.json` shows `n_rejects ≥ 30` decided and a leak verdict either way.
Validation: leak_frac with 95% Wilson interval. Retirement: the audit itself decides —
over-strict → recalibrate; calibrated → the bar is empirically defended for the first time.

**X2 — Re-run the 420 through the per-candidate path in SHADOW (0 capital, 2 hours).**
`campaign_gate_stats` + `validate(campaign=…, column=…)` over `_audit_prepared.pkl` offline;
report survivor count and per-gate rates vs legacy. Success: a written comparison the R0033
ruling can cite (does the flip admit 0, 3, or 30 of 420?). This does not activate anything —
it measures the counterfactual, which the ruling currently lacks.

**X3 — Pre-campaign power gate (half day).** Implement the F8 closed-form/simulated surface as
`libs/validation/campaign_power.py`; require every campaign spec to state (T, N,
min-passable-SR) and refuse launch when min-passable-SR > 3. Success: next campaign's spec
carries the number; the 310-day/420-trial shape becomes impossible to launch silently.

**X4 — Gate telemetry organ (half day).** Nightly job writing
`web/gate_histogram.json` (per-gate accept rates, rolling 90d, per campaign) + max_audit check
firing on any gate outside [5%, 95%]. Success: artifact exists, updates, and back-fills the
07-26/07-29 findings as its first two datapoints.

**X5 — DSR-as-ranking experiment (1 day, analysis only).** On the 420 matrix: rank by DSR,
take top-K (K=12−current slots), simulate forward-clock outcomes on the held-out tail vs the
binary-0.95 policy (which forwards nothing). Success criterion: top-K forward Sharpe
distribution beats the empty set (trivially) AND the noise-admission rate stays under the Holm
slot budget — evidence for/against converting Stage-A DSR from proof to prioritization.

---

## PERSPECTIVE COVERAGE CHECKLIST

- [x] INTERNAL — F1–F13
- [x] EXTERNAL — perspectives section
- [x] FUTURE — perspectives section
- [x] CONTRARIAN — perspectives section (four core assumptions tested, two falsified)
- [x] GREENFIELD — perspectives section
- [x] FRONTIER — perspectives section (4 items, all ≤1-day)
- [x] NEGATIVE-SPACE SWEEP — 8 never-built items named
- [x] Five-things search: weaknesses (F1,F6,F9,F11), bottlenecks (F10, F4), capability gaps
  (F3, ERM, power calc), compounding multipliers (ranked items 1,2,4,5), unknown-unknowns
  (U1–U6 ledger)

## AUDIT SELF-NOTES (honesty)

- This sweep nearly shipped a wrong synthetic table (noise columns normalized to exact zero
  mean → deflation variance collapsed) — the same R0017 failure shape already on the ledger.
  Caught before publication; the corrected table is above. The R0017 probe fix should reuse
  this exact-SR-winner + raw-noise-cohort construction.
- Prior-art check: F1/F2/F5/F9 overlap open rows R0016/R0008/R0001/R0023 — cited, not
  re-rowed, per §41 no-duplication. F3 (inert since built), F4 (page displacement), F8 (DSR
  surface + winner injection), F11 (PPY), F12 (bespoke verify), F13 (redundancy) are new.
- Everything here was produced read-only; no code, state, cron, or git was modified. The
  register rowing for new findings belongs to the consuming brain cycle (§35).
