# Weekly Deep Cold Audit — VALIDATION-STATS (2026-07-26)

Auditor: cold sweep, read-only. Working dir `/home/quant/quant-platform`.
Scope: selection bias, multiple testing, parameter sensitivity, sample dependence,
walk-forward + CV methodology, regime robustness, distributional assumptions, uncertainty
propagation, capacity/cost modeling, simulation realism, MC design, bootstrap quality,
structural breaks. Zero-information gates. Dead rigorous code. DSR bar optimality.

> **STATUS: IN PROGRESS** — findings appended incrementally as verified (completion contract §1).
> Previous run of this subsystem produced only `# AUDITOR FAILED (validation-stats)` (49 bytes)
> — see finding META-1.

## SCORES (provisional — updated as evidence lands)

| metric | value | note |
|---|---|---|
| current_capability_pct | TBD | |
| practical_ceiling_estimate | TBD | |
| ceiling_gap | TBD | |
| opportunity_cost_1y | TBD | |
| confidence | TBD | |
| unknown_unknown_score | TBD | |
| info_gain_if_investigated | TBD | |
| expected_alpha_contribution | TBD | |
| expected_compounding_contribution | TBD | |

## HEADLINE (read this if you read nothing else)

**The desk's production validation gate cannot accept anything, and the rigorous gauntlet it
believes it runs has never run.** Three independent, individually-fatal defects, each verified by
running the real production code on the real 420-candidate campaign matrix:

1. **`reality_check` is a campaign-level constant used as a per-candidate veto.** Measured
   p = 0.422 for the 420-campaign; the gate needs p < 0.05. It is computed **once** and handed
   to every candidate, so it is `False` for all 420. Acceptance rate of the whole gauntlet is
   therefore **identically 0 for any input, however good** — the gauntlet is a null function.
2. **`dsr` rejects 100% (0/420) and its bar is set by sample-size noise, not skill.** The
   deflated benchmark demands an annualized Sharpe of ~3.0–3.5; the best candidate in the entire
   campaign reached 1.61. The `variance_of_sharpes` that sets that bar is **~100% estimation
   noise** in 5 of 7 families, because Sharpes estimated on 310-day and 4594-day series are
   pooled into one variance.
3. **The rigorous gauntlet (`libs/validation/gauntlet.py`) is TEST-ONLY.** Hansen SPA, stress-cost
   validation, the economic-prior gate and the lockbox holdout never execute in production. So do
   CPCV (the real purged one), the entire FDR module, and the bootstrap CI machinery.

Power analysis (below): with the two campaign-constant gates *forced to pass*, a strategy with a
**true annualized Sharpe of 3.0 on 2134 days still fails**. Real alphas of Sharpe 1–2 die with
certainty. This is not a strict gate; it is a broken one.

---

## 1. WHAT WE KNOW (validated strengths, each with proving command)

### K-1. The statistical primitives are, individually, correctly implemented
Reading `libs/validation/dsr.py`, `pbo.py`, `reality_check.py`, `bootstrap.py`, `fdr.py`,
`cpcv.py`, `forward_stats.py` against the source papers, the maths is right:

- `probabilistic_sharpe_ratio` (dsr.py:28) implements the Bailey–López de Prado PSR with the
  correct skew/kurtosis denominator `1 - g3*sr + ((g4-1)/4)*sr^2` and non-excess kurtosis.
- `expected_max_sharpe` (dsr.py:44) is the correct Euler–Mascheroni expected-maximum expression.
- `hansen_spa` (reality_check.py:57) implements the *consistent* variant properly — studentised
  by `omega`, recentred with the `A_n = -sqrt((omega^2/T) * 2 log log T)` threshold
  (reality_check.py:69-71), and the recentring `d_bar * keep` correctly pushes hopeless
  strategies out of the max. Zero-variance strategies are sent to `inf` so they cannot be
  significant (reality_check.py:65) — a real, deliberate guard.
- `bootstrap.py` refuses the i.i.d. bootstrap and offers moving-block and stationary block
  resampling with geometric block lengths (bootstrap.py:27-37) — correct Politis–Romano.
- `fdr.py` `_control` implements BH and BY with the correct `c_m = sum(1/i)` dependence penalty.
- `cpcv.py` implements genuine purge **and** embargo, purging symmetrically around each
  contiguous test block (cpcv.py:75-79).
- `forward_stats.autocorr_factor` uses Bartlett weights and is deliberately clamped to `[1, 5]`
  so a noisy `rho` can neither inflate significance nor nuke a real edge (forward_stats.py:49).

**This is the audit's most important asymmetry: the library is good and the wiring is not.**
Almost every finding below is an integration defect, not a mathematics defect. That is good news
for cost-to-fix and bad news for what the desk currently believes about its own rigour.

### K-2. The DSR ratchet was already correctly diagnosed and fixed
`libs/autodiscovery/orchestrator.py:_family_trials` (lines 63-88) replaced an ever-growing global
trial counter with a **pre-registered per-family fixed wall** (`family_trial_budget=120`), with a
`max()` so a family that genuinely exceeds its declared budget still pays. Verified live —
every family reports exactly 120 trials:

```
$ .venv/bin/python -c "...fam_trials..."
n_trials per family: {'cross_asset': 120, 'liquidity': 120, 'volatility_expansion': 120,
 'volatility_compression': 120, 'trend': 120, 'momentum': 120, 'mean_reversion': 120}
```

The reasoning in that docstring is statistically sound and is the correct treatment. **Note the
irony this audit must record: the desk fixed the *ratchet* and never checked the *level*. The
wall is fixed at a height nothing can climb (finding W-2).**

### K-3. `TrialsLedger` is genuinely append-only and hash-chained
`libs/store/trials.py` chains every row (`prev_hash` → `row_hash` via `compute_chain_hash`) and
`verify_trials_chain` walks the chain. This is real tamper-evidence, not a comment claiming it.

### K-4. The `capacity` constant-veto defect was found and fixed once already
`libs/autodiscovery/validation.py:83-86` carries the fix comment: the old fixed `edge_bps` "made
this gate a constant veto for every candidate". So the desk **has** encountered the
constant-gate failure shape before, diagnosed it correctly, and fixed that one instance.
It did not then sweep for the same shape elsewhere — which is exactly where findings W-1 and W-2
were waiting. (Proactive battery move 2, ADJACENCY: one instance is never one instance.)

## 1b. VERIFIED DEFECTS (the substance of this audit)

Severity key: **FATAL** = the subsystem cannot do its job at all. **SEVERE** = produces materially
wrong numbers. **MODERATE** = real cost, bounded.

### W-1 [FATAL] `reality_check` and `pbo` are campaign-level constants used as per-candidate vetoes
**What.** `libs/autodiscovery/orchestrator.py:171` computes `pbo_once, rc_once = campaign_pbo_rc(matrix)`
**once per campaign** and passes both into every candidate's `validate()` call
(orchestrator.py:186-191). `libs/autodiscovery/validation.py:101-102` then uses them as gates:
```python
"pbo": pbo is not None and not pbo.overfit,
"reality_check": rc is not None and rc.significant_at_5pct,
```
Both values are identical for every candidate in the campaign. A gate that takes one value per
campaign can only ever reject **0% or 100%** of it. It cannot rank, cannot discriminate, and
carries exactly **zero bits** of per-candidate information.

**Evidence — measured on the real 420-campaign matrix with the real function:**
```
$ .venv/bin/python -c "...whites_reality_check(M)..."
zero-variance columns in matrix: 7
--- WHITES REALITY CHECK (campaign-wide, the value ALL 420 candidates receive) ---
  statistic       = 0.2344
  p_value         = 0.422
  n_strategies    = 420
  significant_at_5pct = False
  --> gate "reality_check" for EVERY candidate = False
```
**Evidence — the stored artifacts agree exactly.** `data/sor_crypto.sqlite`
(`research_candidates`, 420 rows) holds only **3 distinct `pbo` values and 3 distinct
`reality_p` values** — one per campaign, with counts 195/195/30 exactly matching the three
campaign sizes:
```
pbo:       distinct=3 -> [(0.6799, 195), (0.6389, 195), (0.7000, 30)]
reality_p: distinct=3 -> [(0.468, 195), (0.080, 195), (0.833, 30)]
dsr:       distinct=383          <-- dsr IS per-candidate; these two are not
rejected by reality_check: 420/420 (100%)
rejected by pbo:           420/420 (100%)
```
**Evidence it flips to 100% ACCEPT on a different draw** — the same gate, different campaign:
```
data/sor_autodiscovery.sqlite  n=57  distinct_pbo=2  pbo=[0.0270, 0.1724]  -> PBO accepted 57/57
data/sor_research_lake.sqlite  n=49  distinct_pbo=2  pbo=[0.6646, 0.7152]  -> PBO rejected 49/49
data/sor_research_lake_v2.sqlite n=49 distinct_pbo=1 pbo=[0.6882]          -> one value, 49 rows
```
This is the textbook definition of a zero-information gate, and it is the *exact* failure the
GATE-OPTIMALITY DUTY names: "a campaign-level statistic vetoing every candidate".

**Consequence.** `validate()` returns `survived = not failed` over **all** gates
(validation.py:110), so with `reality_check=False` campaign-wide, **the acceptance rate of the
production gauntlet is identically zero for every possible input.** The famous "420 hypotheses →
0 survivors" result is not evidence about price-family alpha. It is the arithmetic of a
constant-False gate. The desk has been citing a null function's output as a research finding in
14 places (`docs/DIGGING_CHARTER.md:215`, `docs/graveyard.md:72-73`, `docs/GAP_REGISTER.md:89`, …).

**Why it is also statistically wrong, not just badly wired.** White's Reality Check tests the
*family* null "the best of N strategies does not beat the benchmark". Its answer is a property of
the search, not of any one candidate — so using it as a per-candidate gate is a category error in
both directions. Worse, `whites_reality_check(matrix)` is passed **raw returns**, but its
contract (reality_check.py:40) is `performance[t,k] = strategy k's edge over benchmark at t`. The
benchmark is therefore implicitly **zero**, so the test asks "did the best of 420 beat cash",
never "did it beat buy-and-hold" — the comparison that would actually matter for a long-biased
crypto book.

**Fix.** (a) PBO and RC/SPA are **campaign diagnostics** — report them once per campaign, log them,
and let them gate *the campaign* (e.g. "this search was too overfit to promote anything from"),
never a candidate. (b) For per-candidate multiplicity, the DSR is already the right instrument.
(c) If a per-candidate selection-bias test is wanted, use `hansen_spa` on a matrix whose columns
are that candidate's own parameter neighbourhood, with an actual benchmark column subtracted.

---

### W-2 [FATAL] The DSR bar is unclearable, and its height is set by sample-size noise
**What.** `dsr` rejected **420/420 (100%)** — the third zero-information gate. Unlike W-1 it *is*
per-candidate (383 distinct values), so this is a calibration failure, not a wiring failure.

**Evidence — pass rate and the bar's height, real code, real campaign:**
```
=== PER-CANDIDATE GATE PASS RATES (n=420, real production code) ===
gate                passed   seen  pass_rate
expected_value         251    420     59.8%
cpcv                   238    420     56.7%
walk_forward           176    420     41.9%
dsr                      0    420      0.0%     <-- zero information
capacity               238    420     56.7%
fragility              219    420     52.1%

best DSR in the entire 420-candidate campaign = 0.5588   (bar = 0.95)
```
Stored artifacts agree: `dsr n=413 min=1.4e-35 p25=4.6e-06 med=5.4e-04 p75=7.3e-03 max=0.4577`
against `dsr_threshold: 0.95`.

**The bar translated into money terms:**
```
=== WHAT ANNUALIZED SHARPE DOES THE DSR BAR ACTUALLY DEMAND? ===
  cross_asset       sr0(daily)=0.0620 -> ann 1.18 | DSR-pass needs ANN SHARPE > 2.97
  liquidity         sr0(daily)=0.0778 -> ann 1.49 | DSR-pass needs ANN SHARPE > 3.27
  mean_reversion    sr0(daily)=0.0829 -> ann 1.58 | DSR-pass needs ANN SHARPE > 3.37
  momentum          sr0(daily)=0.0883 -> ann 1.69 | DSR-pass needs ANN SHARPE > 3.48
  trend             sr0(daily)=0.0691 -> ann 1.32 | DSR-pass needs ANN SHARPE > 3.11
  vol_compression   sr0(daily)=0.0765 -> ann 1.46 | DSR-pass needs ANN SHARPE > 3.25
  vol_expansion     sr0(daily)=0.0832 -> ann 1.59 | DSR-pass needs ANN SHARPE > 3.38

  best ANNUALIZED sharpe actually achieved in campaign = 1.61
```
**The root cause is subtler and more important than "the bar is too high".** `sr0` is
`expected_max_sharpe(n_trials, variance_of_sharpes)`. The `variance_of_sharpes` term is computed
from Sharpe estimates of series whose **lengths differ by 14.8x**, so it measures estimation
noise rather than dispersion of skill:
```
=== IS variance_of_sharpes MEASURING SKILL OR SAMPLE-SIZE NOISE? ===
  series lengths: min 310  median 2134  max 4594  (ratio 14.8x)
  cross_asset            var_obs=0.00057  pure-noise floor(mean 1/n)=0.00091  noise_share=100%
  liquidity              var_obs=0.00090  pure-noise floor=0.00091            noise_share=100%
  mean_reversion         var_obs=0.00102  pure-noise floor=0.00091            noise_share= 89%
  momentum               var_obs=0.00116  pure-noise floor=0.00091            noise_share= 78%
  trend                  var_obs=0.00071  pure-noise floor=0.00091            noise_share=100%
  volatility_compression var_obs=0.00087  pure-noise floor=0.00091            noise_share=100%
  volatility_expansion   var_obs=0.00103  pure-noise floor=0.00091            noise_share=100%
```
`Var(SR_hat) ≈ 1/n` under the null, so `mean(1/n)` is the variance you would see from
**pure noise alone**. In 5 of 7 families the observed variance is *at or below* that floor: the
deflation term contains **no skill-dispersion signal whatsoever**. Bailey & López de Prado derive
the DSR assuming all trial Sharpes are estimated on a **common sample length**; pooling 310-day
and 4594-day estimates violates the derivation and inflates `sr0` with pure sampling noise. The
desk is deflating by an artifact of its own ragged data coverage.

**Fix.** Estimate `variance_of_sharpes` on the **common window** (the truncated `matrix` already
computed at orchestrator.py:174 — it is right there and unused for this purpose), or
variance-weight the estimates by their sample lengths. Then re-measure the bar with W-2's power
analysis before trusting it.

---

### W-3 [FATAL] Power analysis: a true Sharpe-3.0 alpha fails the live gate
The audit's assigned question is "Is the DSR bar OPTIMAL — neither so strict that real alphas die
nor so loose that noise passes?" Answered directly, by injecting synthetic candidates of **known
true Sharpe** into the real `validate()` with the two campaign-constant gates **forced to pass**
(so this measures the *best case* the gauntlet could ever achieve):
```
=== POWER ANALYSIS: candidate with KNOWN true annualized Sharpe, real validate() ===
   iid normal, daily vol 2%, family=momentum, n_trials=120 (fixed wall)
   pbo & reality_check FORCED TO PASS to isolate the per-candidate gates

 true_SR      n realized_SR     DSR  dsr  cpcv  wf  EV  cap  frag  SURVIVED
     1.0    310       -1.46   0.002    .     .   .   .    .     Y     False
     1.5    310       -0.91   0.008    .     .   .   .    .     Y     False
     2.0    310       -0.37   0.029    .     .   Y   .    .     Y     False
     3.0    310        0.71   0.186    .     Y   Y   Y    Y     Y     False
     4.0    310        1.79   0.524    .     Y   Y   Y    Y     Y     False
     6.0    310        3.96   0.964    Y     Y   Y   Y    Y     Y      True
    10.0    310        8.29   1.000    Y     Y   Y   Y    Y     Y      True

     1.0   2134        0.32   0.001    .     Y   Y   Y    Y     Y     False
     1.5   2134        0.83   0.019    .     Y   Y   Y    Y     Y     False
     2.0   2134        1.33   0.185    .     Y   Y   Y    Y     Y     False
     3.0   2134        2.34   0.918    .     Y   Y   Y    Y     Y     False
     4.0   2134        3.36   1.000    Y     Y   Y   Y    Y     Y      True
     6.0   2134        5.38   1.000    Y     Y   Y   Y    Y     Y      True
    10.0   2134        9.43   1.000    Y     Y   Y   Y    Y     Y      True
```
**A true annualized Sharpe of 3.0 on 2134 days of data does not clear the gate.** The detection
threshold is true SR ≈ 4.0 at n=2134 and ≈ 5–6 at n=310. Any real crypto alpha — Sharpe 1–2 net
of costs would be excellent — is rejected with near-certainty. And this is the *optimistic*
measurement: in production `reality_check` is constant-False, so true power is **0 at every
Sharpe**.

**The controlled natural experiment that proves the bar tracks campaign size, not quality.**
`web/trend_gauntlet.json` (Jul 4, `n_trials_penalty: 4`) ran the same machinery:
```
pbo: 0.079,  reality_check_p: 0.005
trend_30d   ann_sharpe 1.40  gates 9/9  survived: true
trend_60d   ann_sharpe 0.96  gates 9/9  survived: true
trend_90d   ann_sharpe 0.76  gates 8/9  survived: false  failed: ["dsr"]
trend_120d  ann_sharpe 1.04  gates 9/9  survived: true
```
**3 of 4 survived at n_trials=4, with strictly LOWER Sharpes than the 420-campaign's maximum.**
Same code, same thresholds; the only difference is the size of the campaign the candidate happens
to be embedded in. The gate is measuring the search, not the strategy.

---

### W-4 [SEVERE] `annual_sharpe` is inflated 4.13x — daily returns annualized with an hourly constant
`libs/autodiscovery/validation.py:26` sets `_PERIODS_PER_YEAR = 24 * 260 = 6240` (hourly bars),
but the campaign runs on **daily** bars (`load_universe(Timeframe.D1, ...)`). Verified end-to-end
against the stored database:
```
  _PERIODS_PER_YEAR constant in validation.py = 6240 (= 24*260, i.e. HOURLY bars)
  data actually used: Timeframe.D1 (daily)
  max per-period sharpe in campaign        = 0.08451
  x sqrt(6240) [what the code does]        = 6.675
  MAX(annual_sharpe) stored in the DB      = 6.844   <-- matches the WRONG annualiser
  x sqrt(365)  [correct for daily bars]    = 1.614   <-- the truth
  INFLATION FACTOR = sqrt(6240/365) = 4.13x
```
Every `annual_sharpe` the desk has ever recorded for this campaign is **4.13x too large**. A row
reading "Sharpe 6.84" is really Sharpe 1.61. The gates themselves are unaffected (the DSR works in
consistent per-period units), so this is purely a **human-facing lie**: it is the number in
dashboards, reports and `ValidationMetrics`, and it is the number a person would use to decide
that a rejected candidate "looked great". The same object also mixes units — `annual_sharpe` is
annualized while `oos_sharpe` (validation.py:93) is left per-period, so the two Sharpes in one
record differ by a factor of 79.

**Fix.** Derive periods-per-year from the `Timeframe` actually loaded; never hardcode it. Assert
that every Sharpe in a single model carries the same annualization.

---

### W-5 [SEVERE] The `cpcv` gate contains no CPCV, and the `walk_forward` gate is not out-of-sample
Two gates are named after out-of-sample methods and neither performs one.

**`cpcv`** — `libs/autodiscovery/validation.py:28-31`:
```python
def _cpcv_positive_fraction(returns: np.ndarray, *, k: int = 5) -> float:
    folds = np.array_split(returns, k)
    positive = [f.mean() > 0 for f in folds if len(f) > 1]
    return float(np.mean(positive)) if positive else 0.0
```
This is a contiguous 5-fold **mean-sign vote on the already-realized return series**. There is no
train set, no test set, no purge, no embargo, no combinatorial recombination — and therefore no
cross-validation of any kind. The module docstring (validation.py:4) nevertheless claims
"CPCV (purged K-fold OOS consistency)". The genuine implementation — `libs/validation/cpcv.py`,
which correctly purges symmetrically around each contiguous test block and applies an embargo
(cpcv.py:75-79) — is **never imported by any production path**. Repo-wide, `purge=`/`embargo=`
appear on 6 lines: 5 in `tests/validation/test_splits.py`, and 1 pass-through in
`revalidation.py:97` that defaults to 0.

**`walk_forward`** — `libs/validation/revalidation.py:101-104`:
```python
for split in splits:
    test = arr[split.test]
    oos_sharpes.append(sharpe_ratio(test) if len(test) > 1 else 0.0)
    oos_means.append(float(test.mean()) if len(test) else 0.0)
```
`split.train` is **never read**. Nothing is refit; the engine slices an already-computed return
series — produced by parameters that were themselves chosen using the whole history, including
these windows — and calls the last two-thirds "out-of-sample". `walk_forward_splits` dutifully
computes `min_train` and `train_start` (walk_forward.py:41-44) and the result is discarded.

**Consequence.** The production path's *only* two claimed OOS gates are both in-sample statistics
of a fitted series. Combined with W-1/W-2/W-3 this means the 420-candidate campaign contained
**zero out-of-sample evidence of any kind**, while reporting an `oos_sharpe` column. And the
observed `oos_sharpe med=-0.0016` with only 193/420 positive is what a no-information split of a
selected series looks like.

**Fix.** For a signal-generating strategy the fold must re-run parameter selection on train and
evaluate on purged/embargoed test. `libs/validation/cpcv.py` already does the hard part; wire it,
and require `purge >= label_horizon` and a non-zero embargo.

---

### W-6 [SEVERE] The hash-chained trials ledger is empty, and its only monitor reads the wrong databases
`trials_ledger` is fully built — schema, hash chain, append-only triggers
(`migrations/m0001_core.py:69-95`) — and holds **0 rows in all 8 databases that define it**. Its
sole consumer, `scripts/max_audit.py:129-141`, iterates
`("sor_research.sqlite", "sor.sqlite", "sor_demo.sqlite", "sor_live.sqlite")` — a list that
**omits `sor_crypto.sqlite`, the only database with candidates** — and returns `[]` on failure
with no alarm. Two of the four names it does probe are worse than useless: `data/sor.sqlite` is a
4096-byte file with **zero tables**.

So the effective-trial-count monitor always sees an empty list and silently "degrades to prior
behaviour": `n_trials = 7 x 0 = 0`. This is a **self-greening guard** — the exact quarry the
doctrine names. It is also why W-2 went undetected: the organ whose job is to audit
effective-vs-raw trial count reports nothing, forever, without erroring.

Note the production DSR path does *not* depend on the ledger (it uses the per-family fixed wall of
120), so this is not a live sizing risk — it is a **blind instrument**, and the reason a fatal
calibration defect survived in plain sight.

---

### W-7 [SEVERE] The rigorous gauntlet is a museum piece; production runs a weaker look-alike
The desk has **two** validation stacks and runs the worse one.

`libs/validation/gauntlet.py` — documented as "the Skeptic", ordered, fail-at-first-stage, with
the economic-prior gate, DSR, PBO, **Hansen SPA**, **stress-cost validation** and a **lockbox
holdout** — is constructed **nowhere outside tests**. Verified: `Gauntlet` has 5 test call sites
and 0 non-test call sites; `CandidateEvaluation` 1/0; `StageResult` is entirely unreferenced.
`hansen_spa` and `stress_cost_validation` are dead at second order — their only callers are the
test-only `Gauntlet` and the test-only `AlphaDiscoveryFactory`.

Production instead runs `libs/autodiscovery/validation.py::validate()`, which has **no** SPA (it
uses the weaker White's RC), **no** stress-cost scenario, **no** economic-prior gate beyond
`bool(hypothesis.failure_modes)` — a truthiness check on a list, not a mechanism test — and **no**
lockbox. `LockedHoldout` (lockbox.py) is test-only: **the desk has no production holdout.**

**Additional dead rigorous code, all test-only or unreferenced:**
| module | status | what is lost |
|---|---|---|
| `libs/validation/fdr.py` (BH + BY) | **entire module test-only** | no FDR control anywhere in production; the "program-wide layer of the family-wise error budget" its docstring promises does not exist |
| `libs/validation/cpcv.py` | **entire module test-only** | no purging, no embargo (W-5) |
| `libs/validation/lockbox.py` | test-only | no held-out lockbox |
| `libs/validation/baselines.py` | test-only | no buy-and-hold/random baseline comparison |
| `bootstrap.py`: `block_bootstrap`, `stationary_bootstrap`, `confidence_interval` | test-only | **no confidence interval is ever placed on any Sharpe or IC the desk reports** |
| `dsr.py`: `min_track_record_length` | test-only | the desk never asks "how long until this could be significant?" — directly relevant to sizing forward clocks |
| `revalidation.py`: `RevalidationController`, `RevalidationTrigger` | test-only | the structural-break / drift / decay triggers that are supposed to force revalidation never fire |
| `stationarity.py` (ADF, Engle-Granger, GARCH) | **entire module test-only** | no stationarity or cointegration test in any production path; structural breaks untested |
| `anytime_valid.py`: `graduates`, `days_to_graduation` | unreferenced | only `e_value` is wired |
| `gate_calibration.py`: `reconstruction_verified` | test-only | the backfill leakage interlock its docstring calls "the safety interlock that makes backfill a survivor multiplier instead of a leakage source" is **not installed** |
| `libs/validation/__init__.py` | **zero importers** | all 46 re-exports dead |

`RevalidationController` being dead deserves its own line: `docs` and the module docstring state
"no strategy may hold production capital unless `walk_forward_status == PASSED`", and the object
that enforces that never runs.

---

### W-8 [SEVERE] The one gate with promotion authority is under-corrected for multiplicity
This is the inverse of W-1/W-2/W-3 and it is the finding with actual capital consequences.

Under the TWO-STAGE DISCOVERY LAW, backtest gates have **zero promotion authority**; promotion
comes only from pre-registered forward evidence with Holm correction over concurrent slots
(`MAX_FORWARD_SLOTS=12`). So Stage B is the only place strictness protects capital. It is the one
place strictness is missing.

`data/axis_shadow_state.json` (live, 2026-07-26T08:32) records:
```
"nw_t": 0.0,  "holm_bar": 2.13,  "m_concurrent": 3
```
But **10 forward clocks are actually accruing** (`web/cashcarry_shadow.json`,
`cashcarry_shadow_8h.json`, `crypto_shadow.json`, `trend_shadow.json`,
`trend_regime_shadow.json`, `derivative_shadow.json` x2, `axis_shadows.json` x3). The cohort is
recorded as 3 — the axis clocks only — so the correction ignores 7 concurrent tests:
```
  holm_bar(m= 3, rank=1) = 2.130   <-- the bar in use
  holm_bar(m=10, rank=1) = 2.580   <-- the bar the live cohort requires
  holm_bar(m=12, rank=1) = 2.640   <-- at MAX_FORWARD_SLOTS
```
The Stage-B bar is **0.45–0.51 t-units too low**, i.e. the family-wise error rate is roughly
`1-(1-0.05·3/10)^10` rather than 5%. Compounding it, `data/shadow_sleeves.json` — which
`docs/research/TWO_STAGE_DISCOVERY_LAW.md` names as the slot registry of record — is **`[]`, 2
bytes, untouched for 4 days**, while `scripts/run_alerts.py:240` adds a **hardcoded `_standing = 6`**.
So the slot counter reports 6/12, the Holm correction uses 3, and 10 clocks are running. Three
different numbers, none of which is the truth.

**Consequence.** The desk's only promotion-authorized gate under-corrects, and the saturation
alarm that is supposed to detect an idle clock (a reported DEFECT under the doctrine) is counting
a number unrelated to disk. One clock is at `e-value 120.0 > 100` — already past its threshold —
under a cohort count of 3.

**Fix.** Derive `m_concurrent` by enumerating live clock artifacts, never by hand. Make
`shadow_sleeves.json` the single source and have every clock register into it or fail loudly.

---

### W-9 [MODERATE] `capacity` does not measure capacity
`validate()` calls `capacity_estimate(adv_usd=1.0e11, ...)` — the default at validation.py:88,
never overridden by the orchestrator. **$100 billion of average daily volume** is not a figure
any crypto pair possesses; the largest is ~2 orders of magnitude smaller. With `edge_bps` derived
from the candidate's own mean return, the gate reduces algebraically to
`mean per-bar return > ~0.445 bps` — a weaker duplicate of the `expected_value` gate wearing a
capacity costume. Measured pass rates confirm the near-duplication: `capacity` 56.7% vs
`expected_value` 59.8%, and stored `capacity_usd` is bimodal (`min=5.04e-13`, `med=1.80e6`)
because it collapses to ~0 whenever the mean return is ≤ 0.

**Consequence.** Real capacity — the AUM at which each edge dies — is **never estimated for any
candidate**. Every Sharpe the desk has is a zero-size Sharpe. For a book whose supreme objective
is maximum safe-aggressive deployment, not knowing the capacity of an edge is a direct constraint
on how much capital can be justified.

---

### W-10 [MODERATE] NaN silently becomes "reject" instead of "error"
7 of 420 candidates have a **NaN** DSR, and `passed = dsr >= threshold` evaluates `NaN >= 0.95`
to `False`:
```
  NaN DSR values: 7/420   (NaN >= 0.95 is False -> silent rejection, not a verdict)
```
Root cause: 7 columns are zero-variance (never traded), so `skew`/`kurtosis` return NaN,
`denom` becomes NaN, the `if denom <= 0` guard at dsr.py:38 does **not** catch NaN, and
`norm.cdf(NaN)` = NaN. The database confirms 7 rows with `dsr IS NULL`. Small in count, but the
pattern is the dangerous part: **a numerical failure is indistinguishable from a scientific
verdict.** `reality_check.py:65` shows the desk knows how to do this properly — it explicitly
maps zero-variance strategies to `inf`. `dsr.py` should do the same and raise or flag rather
than silently reject.

---

### W-11 [MODERATE] `stage_a_screen` demands high power to say "no" but no significance at all to say "yes"
`libs/research/axis_screen.py` is the desk's most-used validation path (30 non-test call sites)
and is genuinely the best-engineered validation code in the repo — the power gate distinguishing
`SCREEN-WEAK` from `SCREEN-UNDERPOWERED` (axis_screen.py:91-103), the `panel_width` correction
that stops a 139-symbol panel inflating t-stats 11.8x, and the horizon-aware annualiser
(axis_screen.py:83) are all sophisticated and correct.

But the two verdicts are held to opposite standards:
- To declare a **negative** (`SCREEN-WEAK`, graveyard-grade) it requires
  `min_detectable_ic = 1.96/sqrt(n_eff) <= ic_min`, i.e. `n_eff >= (1.96/0.03)^2 = 4268`
  observations — **11.7 years of daily data** for a single series.
- To declare a **positive** (`SCREEN-INTERESTING`, which earns a scarce forward clock) it
  requires only `|IC| >= 0.03` and `best timing Sharpe >= 0.5`, with **no significance test, no
  standard error, no confidence interval, and no multiplicity accounting.** At n=300,
  `SE(IC) ≈ 0.058`, so an IC of 0.031 is 0.5 sigma from zero and still passes.

There is also **no cost model**: `_sh` (axis_screen.py:85-87) computes
`np.sign(sig) * fv` — a gross, cost-free daily sign-flipping strategy — and compares it to a
`sharpe_min=0.5` gross bar. Turnover is neither computed nor reported, so a signal whose net
Sharpe is negative can be `SCREEN-INTERESTING`.

Finally, `stage_a_screen` writes **no trials-ledger row and no multiplicity record**. With 30 call
sites screening many axes x targets x horizons, the desk's busiest validation path has **no
multiplicity accounting whatsoever** — while the UNIVERSAL DUTY SET requires every target-horizon
cell to be a DSR-counted, ledgered trial.

**Consequence.** False positives flow into the 12 scarce Stage-B slots (W-8) unchecked, while true
negatives are almost never bankable as knowledge — so the graveyard and the novelty gate are
starved of the "free multiplicity budget" the doctrine counts on.

---

### W-12 [MODERATE] PBO is computationally infeasible at production scale, and `validate()` recomputes it per candidate
`probability_backtest_overfitting` defaults to `n_splits=16` → `C(16,8) = 12,870` combinations,
each computing a Sharpe for all N strategies. On the 420-column campaign matrix that is
~10.8M Sharpe evaluations for **one** call. Measured directly: a `validate()` sweep of 14
candidates with `pbo=None` **exceeded a 120-second budget and had to be backgrounded**, because
`validation.py:76-79` recomputes the full campaign PBO for *every* candidate when the precomputed
value is not supplied.

The orchestrator avoids this via `campaign_pbo_rc` — but that optimisation is *why* PBO became a
campaign constant (W-1). The performance fix and the statistical defect are the same line of code.
Any other caller of `validate()` silently pays O(N x 12,870 x N).

Note also `blocks = np.array_split(np.arange(n_obs), n_splits)` (pbo.py:47) with `n_obs=310`
gives ~19-row blocks and no purging between adjacent in-sample/out-of-sample blocks, so PBO
inherits the same overlapping-label leakage that W-5 describes.

---

### W-13 [MODERATE] Selection into the campaign matrix is length-truncated and survivorship-shaped
`orchestrator.py:174`: `matrix = np.column_stack([r[-min_len:] for _, r, _ in prepared])`.
Measured: `min_len = 310` while the longest series is **4594**. So every campaign-level statistic
(PBO, RC, and the DSR variance term via the `sharpe_estimates` array) is computed on the last
310 observations — one particular ~10-month regime — while each candidate's own DSR is computed on
its full history. **The benchmark and the statistic are measured on different samples**, which is
what W-2's noise-share result is a symptom of.

Compounding it, `sharpe_estimates` (orchestrator.py:175) is built from the **full-length** series,
so the variance term mixes 310-day and 4594-day estimates while the matrix does not. The two
inputs to a single DSR call disagree about what the sample is.

---

### W-14 [THE CENTRAL DIAGNOSIS] The obvious fix fails — the real defect is a category error
I proposed in W-2 that fixing the ragged-length `variance_of_sharpes` would restore discriminating
power. **I tested it and it made the gate strictly worse.** Reported because a fix that fails is
more valuable than a fix that sounds right:
```
=== DOES FIXING THE VARIANCE ESTIMATOR RESTORE DISCRIMINATION? ===
  CURRENT (ragged)         median DSR 0.0034  max 0.5588  n>=0.95: 0/420
  FIXED (common window)    median DSR 0.0000  max 0.2379  n>=0.95: 0/420

=== sr0 (deflated benchmark) BEFORE vs AFTER the fix, annualised ===
  cross_asset       ragged sr0 ann 1.18  ->  common-window sr0 ann 1.74
  liquidity         ragged sr0 ann 1.49  ->  common-window sr0 ann 2.35
  volatility_compression  ragged 1.46    ->  common-window          2.76
  (all 7 families move UP)
```
On a common 310-day window each Sharpe estimate is *noisier*, so the variance rises and `sr0`
rises with it. The inconsistency in W-2 is real and should still be fixed for correctness, **but it
is not what is blocking discovery.**

**What is actually blocking discovery.** Demanding 95% posterior confidence against the *expected
maximum of 120 trials* mathematically requires an annualized Sharpe of ~2–3.5 on these sample
lengths. No parameter tweak escapes that; it is what the DSR *means*. The defect is therefore not
the threshold's value — it is that a **confirmatory** significance bar has been applied to a
**screening** stage.

By the desk's own TWO-STAGE DISCOVERY LAW, the backtest gauntlet has **zero promotion authority**:
"generation volume there is unbounded and can never create a phantom edge, since nothing it
produces reaches capital." A stage that cannot promote does not need 95% confidence. Its job is
**sensitivity** — rank candidates and feed the best into the scarce forward clocks. Specificity is
Stage B's job, and Stage B is exactly where it is missing (W-8).

So the desk currently pays the multiplicity price **twice** — a confirmatory bar at Stage A
*and* a confirmatory bar at Stage B — and the arithmetic of paying it twice is zero throughput.
Meanwhile the Stage-B bar it relies on is under-corrected by 0.45–0.51 t-units.

**The measured cost of this, exactly.** The calibration curve the desk has never plotted:
```
=== ACCEPT-RATE vs DSR THRESHOLD ===
 threshold  current accepts
      0.95            0/413      <-- the bar in use
      0.50            3/413
      0.25           16/413
      0.10           47/413
```
The 420-candidate campaign contained a **ranked list**: 3 candidates at DSR ≥ 0.50 and 16 at
≥ 0.25. Under a screening interpretation those 3–16 would have entered forward clocks and be
accruing honest out-of-sample evidence today. Instead all 420 were discarded and the desk recorded
"price space is picked clean" as a research conclusion. **That conclusion is unsupported by its own
data.**

**Power curve, for the record** (200 Monte Carlo draws per cell, campaign gates forced to pass;
`power == dsr-gate` at every level, confirming DSR is the sole binding per-candidate gate):
```
 true_SR |  n=310 power  |  n=2134 power
     0.0 |        0.0%   |         0.0%     <-- size: no false positives...
     1.0 |        0.5%   |         0.0%
     1.5 |        1.0%   |         0.0%     <-- ...and no power where real alphas live
     2.0 |        6.0%   |        12.0%
     2.5 |       16.0%   |        54.0%
     3.0 |       29.5%   |        87.0%
     4.0 |       64.5%   |       100.0%
```
An outstanding crypto alpha at true Sharpe 1.5 net of costs has a **1% chance** of detection in the
best case and **0%** in production. A gate with 0% size and ~1% power in its operating region is
not conservative; it is uninformative. This is the quantified answer to the assigned question:
**the DSR bar is not optimal, and it is not fixable by re-tuning — it is in the wrong place.**

---

### W-15 [FATAL] `stage_a_screen` returns SCREEN-INTERESTING on ~50% of pure noise
W-11 predicted this from the algebra. Measured, on independent random series (`clock=None`, no
writes), 400 Monte Carlo draws per row:
```
=== FALSE-POSITIVE RATE OF stage_a_screen ON PURE NOISE ===
    signal and target are INDEPENDENT random walks -> every INTERESTING verdict is a
    false positive that would consume one of the 12 scarce forward-clock slots.

 n_days  INTERESTING    WEAK  UNDERPWR  ARTIFACT  SUSPECT
    150       54.2%   0.0%    42.5%     1.8%    1.5%
    300       49.0%   0.0%    50.5%     0.5%    0.0%
    600       33.5%   0.0%    66.5%     0.0%    0.0%
   1200       23.0%   0.0%    77.0%     0.0%    0.0%
   2500        6.2%   0.0%    93.8%     0.0%    0.0%
   5000        1.0%  99.0%     0.0%     0.0%    0.0%
```
**At the sample sizes new axes actually arrive with (150–600 days), between a third and a half of
pure noise is graded SCREEN-INTERESTING and earns a forward clock.** The mechanism: a z-scored
persistent signal is strongly autocorrelated, so the cost-free sign-flipping timing Sharpe clears
`sharpe_min=0.5` by luck, and `|IC| >= 0.03` is trivial when `SE(IC) ≈ 0.06–0.08`. There is no
significance test on either quantity (W-11).

**The de-contamination "angle-20" gate does not catch this.** It fires on 0–1.8% of noise. That gate
detects *timing artifacts* (a misaligned series that coincides rather than leads) — a real and
different failure mode. It provides **no protection against ordinary spurious correlation**, which
is the dominant risk at these sample sizes. The doctrine's confidence that "the artifact gate is
BAKED IN ... impossible to skip" is well-founded and guards the wrong door.

**And the negative side is unbankable**, exactly as the algebra predicted:
```
    powered  <=>  1.96/sqrt(n_eff) <= ic_min(0.03)  <=>  n_eff >= 4268 obs
    horizon=1d  panel=  1 -> needs      4268 rows =    11.7 years of daily rows
    horizon=5d  panel=  1 -> needs     21342 rows =    58.5 years of daily rows
    horizon=20d panel=  1 -> needs     85369 rows =   233.9 years of daily rows
    horizon=1d  panel=139 -> needs    593314 rows =  1625.5 years of daily rows
```
`SCREEN-WEAK` — the only graveyard-grade verdict — occurs **0.0% of the time until n=5000**. So the
graveyard and the novelty gate are starved of the "free multiplicity budget" the doctrine counts
on, while ~50% of noise flows forward. The 20-day-horizon and panel cases need more daily history
than exists.

**Independent confirmation from the live clocks.** If ~50% of screen survivors are noise, forward
evidence should be ~0 or negative across the board. It is:
```
kimchi_premium              nw_t  0.00  (vs holm_bar 2.13)
stablecoin_supply_momentum  nw_t  0.00
crypto book                 forward Sharpe -2.83  (23 of 90 days)
trend_30d                   forward Sharpe -1.38  (23 of 90 days)   [backtest Sharpe was 1.42]
trend_regime                forward Sharpe  0.00
oi_divergence / ls_contrarian  e-value 0.436 / 0.498  (need 100)
```
Every clock that has accrued meaningful data is at or below zero. **The prediction and the
observation agree.** Stage A is feeding noise into Stage B, and Stage B (under-corrected, W-8) is
the only thing standing between that noise and capital.

**Fix.** Require a significance test on the positive verdict symmetric with the power test already
demanded of the negative: report `IC` with its standard error / block-bootstrap CI (the bootstrap
module exists and is dead, W-7), require `|IC| >= max(ic_min, 1.96/sqrt(n_eff))`, compute turnover
and a net-of-cost timing Sharpe, and write a ledger row per screen so multiplicity is counted.

---

### W-16 [SEVERE] Three of four lifecycle states are unreachable, and two committee gates are dead by consequence
`libs/autodiscovery/lifecycle.py:promote()` short-circuits: `if not validation_survived: return
CandidateStatus.REJECTED`. Because W-1 makes `verdict.survived` identically False, **SHADOW, PAPER
and REGISTRY have never been reached, ever.** Verified across the whole recorded population:
```
=== LIFECYCLE STATES EVER REACHED (data/sor_crypto.sqlite, 420 rows) ===
   ('rejected', 420)
  survived flag: [(0, 420)]
```
(and 599/599 rejected across all 9 databases, `alpha_registry` = 0 rows in every one).

The cascade is worse than one blocked gate. `orchestrator.py:196-203` guards the execution-gap and
regime-robustness gates on `status is CandidateStatus.REGISTRY`, which can never occur — so
"committee Lever 2" (`survives_execution_gap`, live-cost stress) and "committee Lever 3"
(`regime_robust`, edge in ≥2 vol regimes) are **unreachable in production**. Confirmed — they have
never appeared in a rejection reason:
```
  execution_gap        appears in 0/420 rejection reasons
  regime_robustness    appears in 0/420 rejection reasons
```
So one campaign-level constant silently disabled the accelerated shadow/paper lifecycle *and* two
independently-built gates. Nothing errored, and the dashboards kept refreshing.

Separately, `regime.vol_regime_labels` computes its tercile cuts with
`np.nanquantile(vol, [1/3, 2/3])` over the **whole** series — regime labels are assigned using
future volatility. Acceptable for a diagnostic, not for anything load-bearing; worth fixing when
the gate is made reachable.

---

### W-17 [SEVERE] Nothing in production ever compares a candidate to buy-and-hold
`libs/validation/baselines.py` exists, is well-written, and states the gap in its own docstring:
> The gauntlet (DSR, SPA, CPCV) asks "is this edge statistically distinguishable from noise, given
> the search?". It does NOT ask the blunter question ... **does it even beat a trivial baseline?**
> A strategy can clear DSR and still lose to buy-and-hold or to equal-weight — in which case it is
> complexity with no reason to exist.

`baseline_scorecard` has **1 reference in the entire repo outside its own file** — its unit test.
It is not wired into any production path.

Combined with W-1's observation that `whites_reality_check` receives **raw returns** rather than
excess-over-benchmark (so its benchmark is implicitly zero/cash), the conclusion is:
**no benchmark comparison of any kind exists in the production validation path.** For a long-biased
crypto book measured over a sample containing large directional moves, this is a first-order
omission — a strategy can be "validated" while losing to holding BTC. The desk wrote the fix and
never installed it.

---

### W-18 [MODERATE] Structural breaks: an enum, a parameter, and zero detectors
`RevalidationTrigger.STRUCTURAL_BREAK` exists (revalidation.py:31) and
`RevalidationController.assess(structural_break: bool = False, ...)` accepts it (revalidation.py:133),
but **nothing in the repository ever computes it.** Every reference is a declaration or a default:
```
libs/signal_engine/governance.py:27:    structural_break_pass: bool = False
libs/signal_engine/governance.py:40:        and verdict.structural_break_pass
libs/validation/revalidation.py:31:    STRUCTURAL_BREAK = "structural_break"
libs/validation/revalidation.py:133:        structural_break: bool = False,
libs/validation/revalidation.py:145:        if structural_break:
```
`RevalidationController` is itself test-only (W-7), so even the plumbing is inert. Note
`governance.py:40` requires `structural_break_pass` to be True for a signal to pass — and since
nothing ever sets it, that is another permanently-False conjunct in a different subsystem
(the same shape as W-1; flagged for the infrastructure sweep).

Negative-space sweep — statistical machinery with **zero implementation anywhere** in the repo
(`grep -rli` over all non-venv Python):
```
ABSENT: ljung / jarque          -> residual autocorrelation & normality never tested
ABSENT: chow_test / bai_perron / cusum / changepoint / ruptures
                                -> no structural-break or regime-shift detector of any kind
ABSENT: conformal               -> no distribution-free prediction intervals
ABSENT: haircut_sharpe          -> Harvey & Liu's *ranking* alternative to DSR's binary veto
ABSENT: romano_wolf / stepM     -> no stepwise multiple-testing improvement on White's RC
ABSENT: e_bh                    -> no e-value multiplicity procedure for the forward cohort (W-8)
ABSENT: impact_adjusted / sharpe_ratio_at_scale / participation_rate
                                -> no capacity-aware performance measure (W-9)
ABSENT: borrow_cost / funding_cost_model
                                -> carry/borrow costs unmodelled in validation
```
The `haircut_sharpe` and `e_bh` absences are the two that matter most, because they are precisely
the instruments that would fix W-14 and W-8 respectively.

---

### W-19 [FATAL] Every Sharpe the desk owns is a zero-size Sharpe
No return series in the repository is a function of position size. `strategy_returns`,
`net_returns`, `xsec_funding_returns`, `_book` and `run_signal_backtest` all charge a constant per
unit of turnover; doubling AUM changes nothing. The entire fill model is
`libs/backtest/fills.py:20-26` — a fixed `slippage_frac` and a per-unit commission, with **no size,
no book, no volume**. `MarketEvent.volume` is written at `libs/backtest/engine.py:74` and **never
read anywhere in `libs/backtest/`**.

`libs/backtest/queue_fill.py` — a competent FIFO queue-priority + latency + partial-fill model
whose docstring says it exists "to stop the backtest assuming a 100% passive fill rate, which is a
silent P&L lie for the maker-carry / cash-and-carry book" — has **tests as its only callers.** The
maker fill-rate instrumentation from commit `d3bf8ab` is live-only
(`scripts/run_trade_forensics.py:116-135`) and the backtest has no wiring to consume it. So the
desk simultaneously owns (a) a partial-fill model with no caller, (b) a fill-rate measurement with
no consumer, and (c) a backtest that assumes 100% instant fills.

**Impact is unfitted and, with current data, unfittable.** `impact_coefficient = 0.1` is hardcoded
in four modules and never calibrated. From the desk's own `data/cost_model.json` (30 symbols,
`sizes_usdt: [100, 250, 500, 1000, 2500]`):
- median cost ratio $2,500/$100 = **1.03x** (the square-root law predicts 5.00x)
- implied impact exponent = **0.009** against an assumed **0.5**
- `exhausted_frac` nonzero in **0 of 60** symbol-size cells

**The largest trade the desk has ever costed is $2,500.** The whole measurement sits inside
top-of-book, so it is not evidence for the square-root law — it is evidence that the probe is far
too small to see impact at all. Combined with W-9 (fabricated $100B ADV), the desk does not know
the capacity of any edge and the numbers it publishes as capacity are functions of Sharpe and a
made-up constant.

### W-20 [SEVERE] The cost stress test is calibrated below realized cost, and is a sign test not a Sharpe test
Two independent defects in the one gate that is supposed to prove an edge survives pessimism.

**(a) The bar is below reality.** Modeled round-turn cost is ~4.5–10 bps (`COST_PER_SIDE = 5e-4` at
`libs/autodiscovery/crypto_adapter.py:39`; ~4.9 bps/side on measured sleeves). The required stress
scenario is `X3` → ~30 bps. Realized all-in on the live book (`web/trade_forensics.json`) is
**−48.1 bps over 96 closes** (−$261.74 on $54,399), with every hold bucket negative. **The required
stress multiplier does not reach the realized outcome.** And the residual is 5–10x the *entire*
modeled cost stack, so it is not a scaling error — it is a cost category the model does not contain
(adverse selection, timing, impact). `libs/costs/gap.py` exists but `include_gap` defaults to
`False` (`libs/costs/model.py:32,67`), so gap risk is never charged in research at all.

**(b) It cannot change a Sharpe.** `libs/validation/stress_costs.py:62-67`:
```python
gross_total = float(gross.sum())
cost_total  = float(costs.sum())
    net = gross_total - scenario.multiplier * cost_total
```
The test is a **sign test on aggregate PnL**. Costs enter as a deterministic constant subtracted
from a total, so they have **zero effect on return variance and zero covariance with returns by
construction.** A strategy falling from Sharpe 2.0 to Sharpe 0.1 still "survives 3x cost stress".
For a validation-statistics layer whose entire purpose is risk-adjusted inference, a stress test
that cannot move the risk adjustment is not a stress test. The same shape recurs in
`orchestrator.py:191-192`, which compares `np.sum(rets)` to `np.sum(stressed)` — total-PnL erosion,
never a Sharpe comparison.

**(c) The measured cost fix reaches 3 of 8 sleeves.** `scripts/run_discovery.py:85-100` passes the
measured cost dict to `xsec_price_mom`, `ts_trend`, `xsec_reversal`. The other five re-derive the
**guessed** ADV tier internally (`libs/research/crypto_xsec.py:43`,
`libs/research/crypto_sleeves.py:43`), and `xsec_funding_returns` has no `cost` parameter at all.
So `funding_carry` — described in its own module as "the program's single best candidate", published
at Sharpe 0.72 — is still screened on the cost model the desk's own gap register records as wrong
in **both** directions (BTC slippage 0.009 bps vs 5 bps charged; NOMUSDT realized −149 bps vs 15
assumed).

**(d) The reconciliation gate has no producer.** `libs/execution/staging.py:67` requires
`"realized_cost_le_1_25x": float(evidence.get("cost_ratio", 999.0)) <= 1.25` — and **nothing in the
repo computes `cost_ratio`.** It fails closed (safe) but the assumed-vs-realized reconciliation
exists as a gate definition with no measurement pipeline.

**(e) Measured tails are computed and discarded.** `scripts/run_cost_model.py:110-111` computes both
`median_bps` and `p90_bps`; `run_discovery.py:121` reads **only the median**. `p90_bps` has no
consumer anywhere (p90/median = **1.48x** at the $500 rung). Worse,
`run_cost_model.py:101-103` `continue`s on exhausted book **before** appending to `bps_list`, so the
cost median is computed only over snapshots that filled — **censoring the cost statistic downward
exactly for the illiquid names where capacity binds.** That is the opposite of conservative.

### W-21 [SEVERE] Universe selection is survivorship-biased two independent ways
**(a) Today's liquidity ranked, full history served.** `libs/autodiscovery/crypto_adapter.py:139-152`
ranks symbols by dollar volume over `.tail(180)` — the **most recent** 180 bars — then serves each
selected symbol's **entire** history. Production default is `limit=30`. This is the textbook bias:
selection on end-of-sample liquidity, backtested over the whole sample. A perp in today's top-30
partly got there by appreciating across the sample, which mechanically flatters momentum and trend —
the two largest families in the campaign (90 candidates each). The docstring defends the cap on
DSR-trial-count and memory grounds, both sound; **it does not mention the selection bias.**

**(b) A live 24-hour snapshot applied to years of history.** `scripts/run_discovery.py:57` calls
`list_liquid_perps(top_n=120)`, which is a **live API call** ranking by a single 24h quote-volume
reading (`libs/data/crypto_source.py:77-84`) — stronger selection noise than a 180-bar median. And
`list_perp_symbols()` filters `status == "TRADING"`, so **only currently-listed perps are ever
visible**; since `scripts/ingest_crypto.py:40` populates the lake from that same call, any perp
delisted before its first ingest **never entered the lake and cannot be tested.**

**Why this matters for the audit's central question.** This bias pushes measured Sharpes **up**,
while the broken gate (W-1/W-2) pushes acceptance **down** to zero. The two errors point in opposite
directions and neither was quantified — so "420 price-family hypotheses produced 0 survivors" tells
us **nothing** about whether price-family alpha exists. The desk cannot currently construct a
point-in-time universe to measure the bias, because the delisted names were never ingested. That
inability is itself the finding.

**(c) Data-quality validation is thin.** `libs/data/schema.py:40-56` checks columns, UTC tz, OHLC
NaNs and optional sort order — **no zero-volume check, no duplicate-timestamp check, no
OHLC-consistency check (high >= low), no gap detection.** Lake scan: zero-volume bars 0 (a latent
gap, not an active bias), **317 `high == low` frozen bars** unflagged, and **208 of 268 symbols have
stopped updating** (117 stop at 2026-06-21; 60 current) while `crypto_symbols()` still enumerates
them and ranks them against live names. Minimum admissible history is 251 bars against
`_MIN_BARS = 250`, where annualized Sharpe SE ≈ 1.21 — **a reported Sharpe of 1.2 on the shortest
admissible series is one standard error from zero.**

### W-22 [MODERATE] Eligibility look-ahead in the cross-sectional sleeve
`libs/research/crypto_xsec.py:48`:
```python
valid = close.iloc[t].reindex(sig.index).notna() & ret.iloc[t].reindex(sig.index).notna()
```
Time-`t` data decides which names are eligible for the position *held over* `t`. A name that stops
printing at `t` is dropped **before** the loss; live, you hold into the halt. Small on a liquid
top-120 panel, but it is precisely the mechanism by which delisting losses disappear from a
backtest.

Separately, the bar-fill convention differs between the event engine (signal at close of bar `i`
fills at **open** of bar `i+1`, `libs/backtest/engine.py:78-83` — honest) and the path that actually
runs daily (`app/signal_builder.py:137-142`, position decided from `close[t-1]` transacts **at**
`close[t-1]`). Measured impact on this data is ~zero (median `|open[t]/close[t-1] − 1|` is
0.007–0.66 bps for 24/7 perps; Sharpe delta ≤ 0.001 across three generators), so **severity is low
for crypto** — but the corollary is that the engine's next-open protection buys nothing in a 24/7
market, and the quantity that actually matters, implementation shortfall, is measured live at
`libs/execution/tca.py:67` and never fed back.

---

## 2. WHAT WE DON'T KNOW (ignorance ledger)

## 3. WHAT COULD MATTER MOST (ranked opportunities)

_pending_

## 4. WHAT WE TEST NEXT (concrete experiments)

_pending_

## APPENDIX: six-perspective coverage log

- INTERNAL: _pending_
- EXTERNAL: _pending_
- FUTURE: _pending_
- CONTRARIAN: _pending_
- GREENFIELD: _pending_
- FRONTIER: _pending_
