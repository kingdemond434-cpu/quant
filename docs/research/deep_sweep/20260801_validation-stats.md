# WEEKLY DEEP COLD AUDIT — validation-stats — 2026-08-01

STATUS: COMPLETE

Auditor: cold sweep, read-only. Subsystem: selection bias, multiple testing, parameter
sensitivity, sample dependence, walk-forward/CV methodology, regime robustness, distributional
assumptions, uncertainty propagation, capacity/cost modelling, simulation realism, MC design,
bootstrap quality, structural breaks.

Prior: `20260729`, `20260730`, `20260731_validation-stats.md` (V1–V18). This sweep opens on the
delta, because the subsystem moved more in the 9 hours before it started (5 commits, 23:47–00:50Z)
than in the preceding week.

**HEADLINE.** The desk's central claim about itself — *"the multiplicity bar is honest; the SAMPLE
is what is unpayably short"* (`BITMEX_DECADE_INGEST_SPEC.md:8`) — rests on an artifact that no
longer says what the documents citing it say. The live certification tested **one** control at
true Sharpe **10.0**, **one** seed, and reports `min_passing_true_sharpe: 10.0` — which is the
minimum of a one-element grid, not a measured detection threshold. Two strategic documents cite
`min_passing_true_sharpe = 5.0` and *"legacy path admits NOTHING up to SR 15"*; the file on disk
says both paths admit at 10.0 and nothing below 10.0 was ever tested. The artifact is untracked
(`reports/` is gitignored), was overwritten, and has no history.

Separately, and independently verifiable: I tested the desk's own proposed fix for its welded
gate (the FDR screen) and **it does not unweld it** — BH and BY select 0 of 266 at the best
available window. The reason is structural and knowable in advance, and it is not the reason the
desk's code comments give.

---

## SCORES

| score | value | basis |
|---|---|---|
| current_capability_pct | **34%** | The primitives are correct and well-tested (DSR, CPCV, Romano-Wolf, BH/BY, PBO, SPA all textbook). The *assembly* is not: 3 of 11 production gates carry zero information, the cost-stress gate is dead, multiplicity is per-script, and the certification is self-greening. Capability is in the parts, not the instrument. |
| practical_ceiling_estimate | **85%** | Bounded by genuine crypto sample depth and by the irreducible fact that forward evidence takes calendar time. Not bounded by method — every method needed is already in the repo. |
| ceiling_gap | **51pp** | Almost all of it is wiring and honesty, not new statistics. |
| opportunity_cost_1y | **HIGH — the whole discovery funnel** | The gate has admitted 0 candidates in its life (`furthest_gate: 5` of 11; gates 6–11 never occupied). One year of a 100%-reject screen = one year of zero validated births against L1.30's replacement-rate clock. |
| confidence | **HIGH** on everything command-cited; **MEDIUM** on the sparse-signal argument in N3 (it is theory + one measured cohort, not a simulation study). |
| unknown_unknown_score | **HIGH (0.7)** | The desk has never once run its gate against a *realistic* control (SR 1.5–3). Every certification point is at SR 10. The entire operating range is unmeasured. |
| info_gain_if_investigated | **VERY HIGH** | Two experiments below (E1, E2) are each <1 hour of compute and each can flip a strategic programme. |
| expected_alpha_contribution | **HIGH, indirect** | This subsystem does not find alpha; it decides which alpha is allowed to exist. A 100%-reject gate has the same effect on terminal wealth as having no research at all. |
| expected_compounding_contribution | **VERY HIGH** | Gate optimality is a multiplier on every future candidate the desk will ever generate. |

**CEILING EXPANSION.** The stated ceiling assumption is *methodological* — "we need more T"
(the BitMEX decade programme). That assumption is currently **unproven**, because it is derived
from an artifact that tested one point at SR 10. The competing hypothesis — that the multiplicity
*framing* (one flat family of 266–420 at the screen stage) is the binding constraint, not T — is
cheaper to test and is directly contradicted by the desk's own two-stage law. Both should be
tested before the decade ingest is scored as the T-lever. See E1/E2.

---

## 0. DELTA SINCE 07-31 (what actually moved on disk)

| commit | what it did | verified state now |
|---|---|---|
| `aebc591` | fixed positive_control so it could run at all | runs |
| `b3d6c8e` | "Positive control CERTIFIED, both halves" | artifact exists, **1 target / 1 seed** — see N1 |
| `750129a` | "The gate is too harsh, and the harshness is not in any threshold" | correct diagnosis |
| `dfa47dd` | statistical audit harness (Type I/II per gate) | **artifact never written** — see N2 |
| `787620a` | score gate SUBSETS (leave-one-out is blind to redundancy) | correct method; same missing artifact |

The methodological direction of all five is right. The problem is that **none of the measurements
they produced is on disk in a form anything can read**, and the one that is on disk is weaker than
the documents that cite it.

---

## 1. WHAT WE KNOW (validated strengths, each with its proving command)

**K1. The statistical primitives are correct.** `libs/validation/dsr.py` implements Bailey &
López de Prado's PSR with skew and kurtosis *estimated from the sample* (`dsr.py:35-37`:
`g3 = skew(r, bias=False)`, `g4 = kurtosis(r, fisher=False, bias=False)`), not defaulted to
normal. `expected_max_sharpe` (`dsr.py:44-51`) is the correct Euler-Mascheroni form. This is not
a place where the desk is cutting corners.

**K2. Romano-Wolf is implemented correctly, including the part that is usually wrong.**
`libs/validation/stepwise.py:180-193`: the bootstrap is studentized (`t_stat = sqrt(T)*d_bar/omega`)
and **recentered** (`boot[b] = sqrt(T)*(f[idx].mean(axis=0) - d_bar)/omega`), using a stationary
block bootstrap. Recentering is the step that makes the null valid and it is present. The
`raw_p` field carries a docstring explaining why feeding `adjusted_p` to an FDR screen would be a
double correction — the desk found and fixed that on 2026-07-30.

**K3. I reproduced the desk's own headline numbers exactly.** Independent re-run:
```
$ .venv/bin/python -c "... romano_wolf_stepdown(M) at both windows ..."
=== min_len (PRODUCTION) : T=310 N=420 ===
  Romano-Wolf FWER  : rejected 0  (min adj p 0.5220)
=== max_obs : T=2109 N=266 ===
  Romano-Wolf FWER  : rejected 0  (min adj p 0.0890)
```
matching `reports/matrix_window_measurement.json` (`min_adjusted_p` 0.522 / 0.089) to 4 decimals.
The instrument is deterministic and its published numbers are real.

**K4. ~~CPCV is genuinely purged and embargoed on the live path.~~ — RETRACTED, see N22.**
I originally recorded this as a strength on the evidence of the constructor call
(`validation.py:249-250`: `CPCV(n_groups=6, n_test_groups=2, purge=2, embargo=0.01)`) and its
docstring. **That was reading the wiring, not the outcome.** The consuming statistic never
references the training fold, so purge and embargo cannot change the result — proved at purge
∈ {0, 2, 50, 500} with identical output. The correct CPCV implementation does exist in
`libs/validation/cpcv.py`; it is the *gate* that ignores it. Retained here, struck through, as
the report's own worked example of the failure mode it is auditing.

**K5. The desk found the sample-truncation defect itself, before I did.**
`scripts/measure_matrix_window.py` docstring: *"min_len=310 while the median candidate carries
2134 observations, so 130,200 of 759,444 available observations (83%) are discarded"*. I verified
the distribution independently:
```
n candidates: 420
min 310  p05 381  p25 845  median 2134  p75 2382  max 4594
total obs available: 759444 ; retained at min_len: 130200 (17.1%)
```
Credit where due: this is the desk's find, measured 2026-07-30. What is new below is that it is
still unfixed in production and that fixing it is not sufficient.

**K6. Stage B's selection logic is the defensible choice and is explicitly argued.**
`scripts/run_axis_shadows.py:9-12` states the forward window is treated as a fresh independent
sample because the hypothesis was registered before the window opened. That is the correct reading
and it is reasoned in writing rather than assumed.

---

## 2. WHAT WE DON'T KNOW (the ignorance ledger)

1. **What the gate does at realistic effect sizes.** Every certification point on disk is SR=10.
   The operating range the desk actually cares about — true SR 1.0–3.0 — has never been tested
   end-to-end. This is the single largest known-unknown in the subsystem.
2. **Whether T is really the binding constraint.** Asserted by two strategic documents, derived
   from a one-point artifact. Untested against the competing hypothesis (multiplicity framing).
3. **What the effective number of independent trials is.** 420 candidates drawn from 7 families
   over one universe and one era are heavily correlated; DSR is fed the raw count as if independent.
   No `N_eff` is computed anywhere.
4. **Whether any gate is calibrated at all.** No gate has a measured Type-I/Type-II curve on disk
   (N2). `dfa47dd` built the harness to produce exactly this and its output file does not exist.
5. **Whether the desk's returns series are even net of realistic cost** — the cost-stress gate is
   dead code and the measured cost model does not reach the deployed sleeve (external agent §3).
6. **Suspected unknown-unknown:** the interaction between the *screen's* multiplicity and the
   *forward stage's* multiplicity has never been analysed jointly. The desk pays FWER twice
   (once across 266 at screen, once across 12 at forward) and nobody has computed the combined
   operating characteristic.

---

## FINDINGS

Numbering: **N#** = new this sweep. Prior V1–V18 re-verification is in the carry table at the end.

### N1 — CRITICAL: the certification is self-greening. It certifies on a one-element grid and reports the grid's minimum as if it were a measured threshold.

`reports/gauntlet_certification.json` is the desk's proof that its gate works. Its content:
```
$ .venv/bin/python -c "import json; d=json.load(open('reports/gauntlet_certification.json')); ..."
generated       : 2026-07-31T23:47:04Z
targets tested  : [10.0] seeds 1
legacy   min_passing_true_sharpe: 10.0  admits_good: True
per-cand min_passing_true_sharpe: 10.0  admits_good: True
```
The script's own default grid is 21 rows:
```
$ grep -n "default=" scripts/certify_gauntlet.py
242:    ap.add_argument("--seeds", type=int, default=3)
243:    ap.add_argument("--targets", default="2,3,5,7,10,15")
```
So the artifact was produced by a **hand invocation with `--targets 10 --seeds 1`**, not by the
scheduled run (`crontab: 10 5 * * * ... certify_gauntlet.py`, no args — and at the time of audit,
01:40Z, today's 05:10 run has not yet fired; the script's blocking bug was only fixed tonight in
`aebc591`). The full grid **has never run**.

Three separate defects compound here:

**(a) `min_passing_true_sharpe: 10.0` is not a measurement.** It is `min(targets_that_passed)`
over a set containing exactly one element. It reads as "the gate detects edges from Sharpe 10
upward" and it actually means "10 is the only number we tried". This is the classic self-greening
metric: a field whose name asserts a property its computation cannot establish.

**(b) `certified_admits_good: true` on n=1.** One control, one seed, at an effect size roughly
3–4× the highest Sharpe any public systematic fund has sustained. A gate that admits a Sharpe-10
strategy and rejects an exact-zero null has demonstrated it is not *literally* inert. It has
demonstrated nothing about its behaviour anywhere in the range the desk operates.

**(c) The artifact contradicts the documents that cite it, and it is unversioned.**
```
$ git check-ignore -v reports/gauntlet_certification.json
reports/carry_basis_path.json          <- (git ls-files reports/ output; the file IS tracked)
reports/gate_histogram.json
reports/gauntlet_certification.json
```
It is tracked, but its content was overwritten by the 1-point run. `docs/GAP_REGISTER.md:94`:
> **Certification read (R0077): the gate question is ANSWERED.** ... legacy path admits NOTHING at
> any true Sharpe up to 15 (sole weld: reality_check); per-candidate path admits from **SR≥5**

`docs/research/BITMEX_DECADE_INGEST_SPEC.md:8`:
> at **T=310 days / N=420 trials** ... even the per-candidate path cannot admit a true SR-3 edge —
> `min_passing_true_sharpe = 5.0`. The multiplicity bar is honest; the SAMPLE is what is unpayably
> short.

Neither statement is checkable against the file today. The file says both paths admit at 10.0 and
that SR 3, 5, 7 and 15 were not tested in the run that produced it.

**Why this matters beyond bookkeeping:** the BitMEX decade-ingest programme — a multi-month data
acquisition effort — is justified in its own spec by `min_passing_true_sharpe = 5.0` and the claim
that raising T "drops the admittable true Sharpe from ~5 toward ~1.5". That inference chain now has
no artifact under it. The programme may still be right (T genuinely matters; see N3), but it is
currently resting on a number the cited source does not contain.

**Failure mode this creates:** a future reader — human or organ — checks the citation, sees
`certified_admits_good: true`, and concludes the gate is fine. That is the guard greening itself.

---

### N2 — CRITICAL: the brand-new gate-power audit has never written its artifact. Its numbers exist only in a git commit message, and its reader has never had a file to read.

`dfa47dd` and `787620a` (00:21 and 00:28 today) built exactly the instrument this audit's
central question needs — per-gate Type I / Type II, leave-one-out and subset scoring. The commit
message carries detailed measured results (DSR blocks 100.0% of genuine alphas at true SR 2.0;
reality_check 94.2%; DSR's LOO cost is 290pp of power per point of FPR reduction).

The artifact does not exist:
```
$ ls -la reports/gate_power_audit.json
ls: cannot access 'reports/gate_power_audit.json': No such file or directory

$ grep -rn "gate_power_audit" --include=*.py .
scripts/report_gate_audit.py:2:"""Read reports/gate_power_audit.json and print the tables ...
scripts/report_gate_audit.py:23:_DEFAULT = Path("reports/gate_power_audit.json")
scripts/audit_gate_power.py:54:_OUT = Path("reports/gate_power_audit.json")
```
`scripts/report_gate_audit.py` is a 164-line reader for a file that has never existed — built,
committed, and dead on arrival. And neither script is scheduled:
```
$ crontab -l | grep -iE 'gate_power|report_gate'
(no output)
```

**Consequence, and it is the reason this is CRITICAL rather than hygiene:** under L1.0(a) a metric
that exists must be *measured, published and floored*. These are the most decision-relevant numbers
in the subsystem — they are the direct answer to "is the DSR bar optimal" — and they are stored in
a git commit message, which is the one place no fence, no ratchet, no consumer and no future audit
will ever look. There is no floor, so there is nothing that fires if gate power regresses.

This is the same class as the L1.41 build-standard violation the desk wrote a fence for eleven
hours earlier: an organ shipped without the artifact that proves it ran.

---

### N3 — CRITICAL, and it corrects the desk's own stated reasoning: the FDR screen does NOT unweld the gate. BH and BY select 0 of 266 at the best available window, and the reason is not the one in the code.

This is the finding I consider most important, because the desk has already built the fix, already
believes the fix works, and is one step from concluding that "even FDR admits nobody" means the
price space is genuinely picked clean — which is the exact pessimism-decay trap L1.25a forbids.

`libs/validation/screen_select.py` (the gap-#71 fix) argues:
> FDR controls a PROPORTION, so the bar does not escalate as generation grows: 5% of a 20-name
> shortlist and 5% of a 200-name shortlist are the same guarantee per selected name.

**That claim is false at the rank that matters.** Benjamini-Hochberg's step-up threshold at rank
*k* is `k·q/m`. At **k=1 it is exactly q/m — Bonferroni.** BH only buys power over FWER when many
hypotheses are true simultaneously, because only then does the procedure walk up to a higher *k*.
With a sparse signal — which is the desk's situation, a handful of real edges among hundreds — BH
never leaves rank 1 and is therefore identical to the family-wise bar it was introduced to replace.

Measured, at both windows, `n_boot` raised to 10,000 to rule out Monte-Carlo resolution:
```
$ .venv/bin/python -c "... romano_wolf_stepdown + screen_select at both windows ..."
=== min_len (PRODUCTION) : T=310 N=420 ===
  Romano-Wolf FWER  : rejected 0  (min adj p 0.5220)
  raw bootstrap p   : min 0.0140   #raw<0.05 = 15
  FDR BH q=0.05     : selected 0
  FDR BY q=0.05     : selected 0
=== max_obs : T=2109 N=266 ===
  Romano-Wolf FWER  : rejected 0  (min adj p 0.0890)
  raw bootstrap p   : min 0.0020   #raw<0.05 = 21
  FDR BH q=0.05     : selected 0
  FDR BY q=0.05     : selected 0
```
and at B=10,000:
```
max_obs window T=2109 N=266 ; BH k=1 threshold = q/m = 0.000188
B=  1000 [  3.5s]  min raw p=0.002000  #raw==0: 0  #raw<q/m: 0 | FWER rej 0 (min adj 0.0890) | BH 0 | BY 0
B= 10000 [ 35.2s]  min raw p=0.001400  #raw==0: 0  #raw<q/m: 0 | FWER rej 0 (min adj 0.0810) | BH 0 | BY 0
```

**A hypothesis I formed and then refuted with my own test, recorded because negative results are
first-class:** I suspected a bootstrap *resolution* artifact — with `n_boot=1000` (`stepwise.py:161`)
the p-grid is quantised at 0.001, and BH rank-1 needs 0.000188, so only an exact `p=0` could ever
enter. That would have been a pure instrument artifact of the L1.25 class. **It is not the cause.**
At B=10,000 the best raw p is 0.00140 — a genuine value far above the 1/10,000 floor, and stable
(0.0020 → 0.0014 as B rose 10×). The p-value is real. The resolution hypothesis is **REFUTED**.

**The actual arithmetic**, which is the useful part:
```
POOLED: m=266 best raw p=0.00140 ; BH rank-1 threshold q/m=0.000188 -> need q>=0.372 to admit the best
what pooled m would admit the best candidate at q=0.05?  m <= 35.7
```
To admit the single best of 266 candidates, BH would need `q = 37.2%` — an absurd false-discovery
rate. Or the multiplicity family would need to be **≤ 35 candidates**.

**I then tested the obvious remedy and it also fails**, which is worth knowing before anyone builds it:
```
family sizes and within-family BH at q=0.05 (m = family size):
   liquidity                    n= 57  best raw p=0.01180  q/m=0.00088  BH selects 0
   trend                        n= 57  best raw p=0.01550  q/m=0.00088  BH selects 0
   momentum                     n= 57  best raw p=0.00140  q/m=0.00088  BH selects 0
   mean_reversion               n= 38  best raw p=0.01180  q/m=0.00132  BH selects 0
   cross_asset                  n= 19  best raw p=0.12120  q/m=0.00263  BH selects 0
   volatility_expansion         n= 19  best raw p=0.04720  q/m=0.00263  BH selects 0
   volatility_compression       n= 19  best raw p=0.01590  q/m=0.00263  BH selects 0
TOTAL family-scoped BH selections: 0
```
Family-scoping to the desk's 7 declared families (n=19–57) still selects **0**, because even the
smallest family's `q/m = 0.00263` is below its best raw p of 0.0472. The needed `m ≤ 35.7` is not
reachable by the existing family partition.

**What this means, stated plainly.** The screen stage is applying a *promotion-grade* error control
to a *screening* stage. The desk's own TWO_STAGE_DISCOVERY_LAW says the backtest gauntlet is "a
SCREEN with ZERO promotion authority" whose "generation volume is unbounded and can never create a
phantom edge, since nothing it produces reaches capital" — and then the screen imposes a bar that
scales as `1/m` in generation volume. `screen_select.py`'s docstring identifies this exact
contradiction in the FWER version and then reintroduces it, because BH-at-rank-1 *is* FWER.

The honest resolutions are (in order of my preference):
1. **The screen should rank, not gate.** Take the top-k by raw p into the forward queue; pay
   multiplicity once, at the forward stage, on ≤12 slots, where the desk already does Holm
   correctly. This is what the two-stage law actually prescribes and it needs no new statistics.
2. If a gate is wanted at the screen, use a **pre-registered** small family (mechanism-scoped,
   m ≤ 35 declared *before* seeing p-values) — noting that my family test above was run *after*
   seeing the pooled result and is therefore a forking path, not a result. It is a hypothesis to
   pre-register, and I flag it as such rather than presenting it as an answer.
3. Report the FDR *q-value* per candidate as a continuous rank statistic and stop thresholding it.

**Retirement condition for this finding:** if a future cohort contains ≥10 genuinely strong
candidates, BH will walk up past rank 1 and this ceases to bind. It binds precisely in the sparse
regime, which is the regime the desk is in.

---

### N4 — HIGH: three of eleven production gates carry zero information. Two accept 100%, one rejects 100%.

The prompt's question — *which gates accept/reject ~100%?* — answered on the real 420 cohort
(`reports/gate_histogram.json`, generated 2026-07-30):
```
"histogram_per_candidate": {"pass_counts": {
      "economic_mechanism": 420,   <- 100.0% ACCEPT
      "fragility": 219, "expected_value": 251, "cpcv": 238, "capacity": 238,
      "walk_forward": 176, "pbo": 209 }},
"per_candidate": {"cscv_pbo_ok": 209, "rw_rejected": 0, "both": 0, "min_adj_p": 0.522}
                                       ^^^^^^^^^^^^^^ reality_check: 0.0% ACCEPT
"survivors": [], "sole_blocker": {}
```

**(a) `economic_mechanism` — 420/420 pass.** The gate is
`libs/autodiscovery/validation.py:474`: `bool(hypothesis.failure_modes)` — a truthiness test on a
list. Any generator that populates one string passes. `measure_gate_histogram.py:46` fills it with
the literal `["reconstructed-for-gate-measurement"]`, which passes.

Meanwhile the desk owns a real economic-prior gate — `libs/validation/economic_prior.py:
economic_prior_gate` — and it is **not on the production path**:
```
$ grep -rn "economic_prior import" --include=*.py . | grep -v MechanismType
tests/validation/test_gates.py:10:from libs.validation.economic_prior import EconomicPrior, economic_prior_gate
libs/validation/gauntlet.py:21:from libs.validation.economic_prior import economic_prior_gate
libs/stage15/economic_mechanism.py:14:from libs.validation.economic_prior import EconomicPrior, economic_prior_gate
```
Every one of the ~25 production scripts imports only `MechanismType` (the enum). The rigorous
gate is reachable only from `libs/validation/gauntlet.py`, which is itself dead (N5).

**(b) `beats_baselines` — structurally 100% accept.** `validation.py:487` calls
`_beats_baselines(arr, benchmark_returns)`, which returns `True` when the benchmark is `None`
(`:272-273`), on length mismatch (`:276`), and on exception (`:279-280`). And:
```
$ grep -rn "benchmark_returns" --include=*.py scripts/ libs/ | grep -v 'libs/autodiscovery/validation.py'
(no output)
```
**No production caller passes a benchmark.** The gate is `True` for 100% of real candidates and
does not even appear in the histogram. The docstring's defence ("skipping rather than failing on a
missing benchmark is a deliberate fail-OPEN … for market-neutral carry") is reasonable for *carry*
and is being applied to *trend, momentum, liquidity, mean-reversion and volatility* families, for
every one of which buy-and-hold is a perfectly well-defined comparator. This is the highest-value
cheap gate on the desk and it is switched off by omission.

**(c) `reality_check` — 0/420 pass, and the desk knows.** `validation.py:372-377` says it in the
code:
> Romano-Wolf FWER admits 0/420 at every window tested (best adjusted p 0.522 at min-length, 0.089
> at max-observation), so as a SCREEN gate it carries zero information about candidate quality --
> and a bar that rises with generation volume is what TWO_STAGE_DISCOVERY_LAW forbids.

and then, three lines later:
> it does NOT change the survival gate here.

The replacement (`self.screen`) is computed on every campaign and **discarded**; the diagnosed
zero-information gate remains wired as a survival gate at `validation.py:480`. This is
computed-but-ignored in its most consequential form: the desk built the fix, measured the defect,
wrote both down, and left the defect in control.

**Gate-optimality verdict (the prompt's direct question):** the stack is not "too strict" in a way
any threshold change would fix. It is **mis-assembled**: 3 gates carry no information, and of the
8 that do, one (DSR) blocks 100% of genuine alphas at true SR 2.0 by the desk's own measurement.
An accept/reject histogram with `survivors: []` and `sole_blocker: {}` — no gate is ever the sole
blocker because several fail at once — is the signature of a stack that is redundantly conservative
rather than sharply discriminating.

---

### N5 — HIGH: there are two gauntlets. The one named "the validation gauntlet — the Skeptic" has zero production constructors, and it is the only home of three rigorous gates.

```
$ grep -rn "Gauntlet(" --include=*.py . | grep -v '^tests/'
(no output)
```
`libs/validation/gauntlet.py` — 214 lines, docstring *"The validation gauntlet — the Skeptic.
Runs the ordered, trials-adjusted gauntlet"* — is **never instantiated outside tests**. The
production path is `libs/autodiscovery/validation.py:validate()`, imported by ~8 scheduled scripts.

The two have **different gate sets**. Gates present only in the dead one:

| gate | module | production status |
|---|---|---|
| `stress_costs` (BASE/2×/3×/5× cost scenarios) | `libs/validation/stress_costs.py` | **DEAD** — `grep -rn "stress_cost_validation" libs/ scripts/` → `libs/validation/gauntlet.py:189` only |
| `economic_prior` (real mechanism gate) | `libs/validation/economic_prior.py` | **DEAD on this path** (N4a) |
| `lockbox` (held-out confirmation) | `libs/validation/lockbox.py` | imported by `libs/autodiscovery/orchestrator.py` only; not consulted by any Stage-B evaluator |

**The L1.5 consequence is direct.** EXECUTION PHYSICS says *"no alpha is valid until it survives
realistic slippage, fees and impact"*. The desk's only cost-stress gate — the one that asks
"does this survive 3× costs?" — **has never been executed on a real candidate.** `validate()` has
no cost gate of any kind; it assumes the returns handed to it are already net, and an independent
check of that assumption found the measured cost model does not reach the deployed sleeve at all.

Two additional structural notes on the dead gauntlet, both of which would have been defects had it
been live, and which matter because it is the version a future engineer would reach for:
- `gauntlet.py:164,176` call `probability_backtest_overfitting(matrix)` and `hansen_spa(matrix)`
  with **no candidate index** — verified against the signatures (`pbo.py:34`, `reality_check.py:57`,
  both take only the matrix). Used per-candidate these are campaign constants: all pass or all fail.
  This is the exact weld `validate()` already migrated away from via `campaign_gate_stats`.
- `gauntlet.py:74`: `trials_multiplier: float = 7.0` — a 7× inflation of the ledger trial count with
  no derivation anywhere in the repo (`grep -rn "trials_multiplier"` returns only its own
  definition and use). A magic constant that directly sets the harshness of the bar.

---

### N6 — HIGH: multiplicity is counted per-script, not per-desk. The same stack is simultaneously far too strict on one path and nearly uncorrected on another.

`validate()` takes `n_trials` as a caller-supplied parameter. What callers actually pass:
```
$ grep -rn "n_trials=" --include=*.py scripts/
run_onchain_history_backtest.py:109:   n_trials=2
run_derivative_backtest.py:104:        n_trials=2
run_cashcarry_backtest.py:89:          n_trials=2
run_kama_squeeze_backtest.py:132:      n_trials=2
run_crossasset_shadow.py:111:          n_trials=3
backfill_onchain_oos.py:108:           n_trials=6
run_crypto_portfolio.py:132:           n_trials=matrix.shape[1]
run_discovery.py:210:                  n_trials=len(lib)
run_carry_harvest.py:92,104:           n_trials=len(prepared)
```
Each script counts **only its own trials**. The `TrialsLedger` that exists precisely to carry the
desk's true cumulative trial count (`libs/store/trials.py`, used by `_resolve_n_trials` in the
*dead* gauntlet) is consulted by **nothing** on the production path.

Quantified, using the campaign's own recorded dispersion (`se_annual_sharpe = 1.0851`, T=310):
```
sr0 = E[max Sharpe] under N trials, in ANNUAL units (sigma=1.0851):
   N=    2  sr0_annual=0.564
   N=    3  sr0_annual=0.925
   N=   42  sr0_annual=2.397
   N=  420  sr0_annual=3.255
   N= 2940  sr0_annual=3.852

required OBSERVED annual Sharpe to reach DSR>=0.95:
   N=    2  need observed annual SR >= 2.047
   N=   42  need observed annual SR >= 3.880
   N=  420  need observed annual SR >= 4.738
   N= 2940  need observed annual SR >= 5.335
```
**The campaign path demands an observed annualised Sharpe of 4.74 over 310 days.** That is above
any sustained public track record, including the ceiling exemplar the benchmark doctrine names.
**The sleeve paths demand 2.05** — and the sleeve paths are where the money is.

Both numbers are wrong in opposite directions, from the same root cause: nobody owns the trial count.

**N6b — five scripts fabricate the trial distribution outright.**
```
$ grep -rn "sharpe_estimates=\[\|sharpe_estimates=np.array(\[" --include=*.py scripts/
run_onchain_history_backtest.py:109:  sharpe_estimates=[sh, -sh]
run_kama_squeeze_backtest.py:132:     sharpe_estimates=[sh, -sh]
backfill_onchain_oos.py:108:          sharpe_estimates=np.array([shp, -shp])
backfill_oi_ls_oos.py:137,139:        sharpe_estimates=np.array([shp_n, sharpe_ratio(g)])
```
`variance_of_sharpes` is the variance of `[sh, -sh]` = `2·sh²`, i.e. **manufactured from the
candidate's own point estimate**. The DSR benchmark becomes `sr0 = 0.734·sh` — a bar that scales
with the number being tested. That is not a deflated Sharpe ratio; it is a self-referential
statistic with the name of one.

**N6c — the variance term is estimated from a cohort that contains the signal.** `validate()`
receives `sharpe_estimates` across all trials and DSR takes their empirical variance
(`dsr.py:83`). Bailey & LdP's formula wants the dispersion **under the null**. The measured
inflation:
```
theoretical NULL sd of an annualised Sharpe estimate over T=310 daily obs: 0.9016
   => observed 1.0851 is 1.20x the pure-null value
```
A 20% inflation of σ propagates directly into `sr0` and therefore into the bar. It is also a
perverse feedback: **the more genuine alpha a campaign contains, the higher the bar every member
of it must clear.** Good research raises its own hurdle.

---

### N7 — HIGH: the sample truncation is measured, unfixed, and by itself insufficient — all three facts matter.

Production still truncates the campaign matrix to the shortest member:
```
$ grep -n "min_len\|column_stack" libs/autodiscovery/orchestrator.py
171:        min_len = min(len(r) for _, r, _ in prepared)
172:        matrix = np.column_stack([r[-min_len:] for _, r, _ in prepared])  # T x N
```
One 310-observation candidate drags 419 others — median length **2134** — down to 310. Measured
2026-07-30 in `reports/matrix_window_measurement.json`; **unchanged in production on 2026-08-01**,
two days and ~40 commits later. Under L1.28b that is a found-unfixed defect aging at its stated ROI,
and its stated ROI is large: the blocking statistic improves 5.9× (adj p 0.522 → 0.089) from this
change alone.

But — and this is why it must not be sold as *the* fix — the desk's own artifact records that it is
**not sufficient**:
```
"max_obs":     {"T": 2109, "N": 266, "min_adjusted_p": 0.089, "n_rejected_at_5pct": 0}
"max_T_at_90N": {"T": 486, "N": 378, "min_adjusted_p": 0.679, "n_rejected_at_5pct": 0}
```
0 survivors at every window, and N3 shows FDR does not rescue it either. **T is a real lever and it
is not the binding one.** The BitMEX decade programme is therefore probably worth doing on its own
merits and should not be scored as the thing that unwelds the gate, because the desk has already
measured that a 6.8× increase in T does not.

A quantified upper bound on what T alone can buy, holding the multiplicity framing fixed: the
required observed annual Sharpe scales with `1/√T` through both `sr0`'s σ and the estimator SE. At
T=310 the bar is 4.74; at T≈2109 the same arithmetic gives ≈1.96. That is the honest version of the
spec's "~5 toward ~1.5" claim — directionally right, and it still leaves 0 survivors today.

---

### N8 — HIGH: the capacity gate contradicts the capacity policy in the same file, by a factor of exactly 20.

```
$ .venv/bin/python -c "from libs.autodiscovery.validation import ..."
live equity read by validate(): 18675.73
capacity GATE floor  _min_capacity_usd(): 37351.46
capacity POLICY floor (10pct slice)   : 1867.573
ratio gate/policy: 20.0
  capacity $  5000: capacity_status=     ADMIT   validate() gate passes=False
  capacity $ 13000: capacity_status=     ADMIT   validate() gate passes=False
  capacity $ 26000: capacity_status=     ADMIT   validate() gate passes=False
```
`capacity_status()` (`:143`) implements the principal's 10%-slice band and returns **ADMIT** for a
$26,000-capacity edge. The binding gate (`:483`) uses `_min_capacity_usd()` = `max(equity × 2.0,
$200)` and **rejects** it. Two functions, one file, opposite verdicts on the same input.

The file spends lines 43–70 arguing the multiple rule is wrong — *"THE BAND IS A MINIMUM SLICE,
NOT A MULTIPLE OF THE BOOK … a multiple was wrong and measurably so"* — and then line 68 retains
`_CAPACITY_MULTIPLE_OF_EQUITY = 2.0` "for the gauntlet's own headroom bar", which is the binding
one. This is V5 from 07-31, **still open**, in a file that was edited since.

It is also *structurally* worse than the $100,000 floor it replaced. The old floor was absolute, so
the desk could compound past it. This one is a **ratio to the book**, so it demands 2× the book at
every scale forever — an edge sized for the desk can never satisfy it, at any equity, by
construction. Under L1.18a ("any absolute capacity floor is a DEFECT" — the intent being that the
band scale *with* the desk), a 2× multiple inverts the intended direction: it makes every edge the
desk can actually fill permanently inadmissible.

---

### N9 — MEDIUM: `_audit_prepared.pkl` — the certification declared itself blocked on a file that exists, and the file is a frozen, unwritable, uncontracted input.

The certification's own honesty note:
> "That half stays blocked on a builder for `_audit_prepared.pkl` (3 readers, 0 writers)."

```
$ ls -la _audit_prepared.pkl
-rw-rw-r-- 1 quant quant 6100907 Jul 26 15:08 _audit_prepared.pkl
$ grep -rln "_audit_prepared" --include=*.py .
_audit_gate_probe.py  _audit_gate_probe2.py  scripts/measure_gate_histogram.py
scripts/measure_matrix_window.py  scripts/certify_gauntlet.py
```
"0 writers" is true. "Blocked" is **not** — the file is present, readable, and I ran the entire
420-candidate analysis in N3 against it. The real-peer half of the certification could have run.

The genuine defect is different and it is an L1.44 case: a **6-day-frozen artifact with no
producer**, consumed on the decision path by 5 organs including the certification, with no
freshness contract. It is also gitignored (`.gitignore:33`), so the cohort every gate diagnostic on
this desk is measured against is unversioned and unreproducible. Note also that
`_audit_gate_probe.py`, `_audit_gate_probe2.py` and `_audit_rows.pkl` are **git-tracked scratch
probes at the repo root** (`git ls-files | grep '^_audit'`) — ungoverned artifacts under §36.

**And the fix for N1 is already in the file the script imports from.**
`libs/validation/positive_control.py:135` contains `certify_gauntlet()` — an 8-target × 12-seed
harness whose own docstring says *"one seed is one draw... perfectly smooth, perfectly wrong"*.
It has zero production callers; `scripts/certify_gauntlet.py:57` imports only `PPY`,
`exact_sharpe_series` and `null_cohort` and hand-rolls its own loop. The desk wrote the correct
certification harness, then wrote a weaker one next to it and shipped that one's output.

---

### N10 — CRITICAL: in production the capacity gate is not a capacity gate. It is a second, slightly harsher copy of `expected_value`.

`scripts/run_discovery.py:207-212` calls `validate()` without `adv_usd`, so every candidate is
scored against the parameter default `adv_usd = 1.0e11` (`validation.py:409`) — roughly the entire
Binance USD-M venue. `capacity_usd` is linear in ADV, so with ADV held constant the gate's only
candidate-varying input is `eff_edge_bps = max(0, mean(returns)·1e4)` (`validation.py:458`):
```
$ .venv/bin/python -c "... capacity_estimate(adv_usd=1e11, ...) vs _min_capacity_usd() ..."
production ADV default = 1e+11 ; capacity gate floor = $37351.46
capacity_usd at edge=1bps: $504000  -> edge_bps needed to clear gate = 0.07411 bps
eff_edge_bps = mean*1e4, so capacity gate == (mean per-period return > 7.411e-06)

expected_value gate     == (mean per-period return > 0)
=> at constant ADV the capacity gate is a STRICTLY-NESTED, slightly harsher copy of expected_value.
   histogram: expected_value 251/420 pass, capacity 238/420 pass  (13 candidates separate them)
```
The histogram confirms it empirically: 251 vs 238 pass, and the 238 are a subset. **Thirteen
candidates out of 420 is the entire independent information content of the capacity gate.**

This reconciles N8 and makes both worse. The gate is simultaneously:
- **20× too strict on paper** (demands 2× the book where the policy says 10% of it), and
- **incapable of ever binding on capacity**, because the quantity it is supposed to measure
  (venue depth) is a constant.

So the whole §42 / L1.18a capacity-parity apparatus — `capacity_status`, `capacity_runway_days`,
`capacity_race`, the ADMIT/OUTGROWN/SUB-VIABLE lifecycle, the deployment-race ordering — is
**never exercised by the gate that decides survival**. It is advisory code around a gate that
tests the sign of the mean return. The real ADV is computed correctly one function away
(`run_discovery._panels():65` — `(df["close"]*df["volume"]).tail(180).mean()`) and simply never
passed.

This is also the redundancy the `787620a` subset-scoring commit went looking for, in a place it
did not look: leave-one-out will price `capacity` as nearly free precisely because
`expected_value` already blocks almost everyone it blocks.

---

### N11 — HIGH: the FDR screen stage is computed on every campaign by 13 scheduled scripts and read by nobody.

`libs/autodiscovery/validation.py:379-380` runs `screen_select(stepdown, q=0.05, method="by")` on
every `campaign_gate_stats` call. `StepdownResult` is a plain pydantic model with no `__bool__`,
so `if stepdown` is always true — it always executes. Consumers:
```
$ grep -rn "\.screen\b\|screen_report\|ScreenSelection" --include=*.py scripts/ libs/ | grep -v test
libs/autodiscovery/validation.py:378:        self.screen: ScreenSelection | None = None
libs/autodiscovery/validation.py:380:        self.screen = with_screen
```
Assignment, and nothing else. `screen_report()` has zero production callers. Thirteen scheduled
scripts pay for the computation (8 direct cron + 5 via `run_daily_research`).

Combined with N3 this is the sharpest structural statement available about the discovery pipeline:
**stage one of the desk's two-stage design does not exist in production.** The stage that is
supposed to shortlist is computed and dropped; the stage that actually gates is the FWER bar the
two-stage law explicitly forbids at the screen.

---

### N12 — HIGH: `libs/validation/event_study.py` is a total orphan, on a desk whose doctrine mandates it by name.

§42 is unambiguous: *"EVENT-SHAPED EDGES GO THROUGH THE EVENT-SHAPED GATE. Do not judge a listing
dislocation on a daily return series... Use `libs/validation/event_study.py`."*
```
$ python /tmp/why.py libs.validation.event_study
importers: libs.research.listing_events  /  NO PATH TO ANY ENTRYPOINT
$ python /tmp/why.py libs.research.listing_events
importers: (NONE)
```
Both the event-study module (CAAR, `holm_bar`, `overlap_fraction`, 23 tests) and its only importer
are disconnected from every entry point. The daily cycle *does* run an `event_study` step — but
`scripts/run_event_study.py`'s entire import list is `json, sys, urllib.request, datetime,
pathlib`. It does not touch the module. Meanwhile a `listing_watch` collector runs daily and
accumulates the exact data the orphaned study is built for.

This is the doctrine's own named remedy for "collected data stays unconvertible forever",
disconnected at both ends, while the data it needs is being collected on schedule.

---

### N13 — HIGH: no cointegration test and no distribution-shift detector reaches any production path — on a desk whose only live sleeve is basis/carry.

```
$ python /tmp/why.py libs.research.stationarity
importers: (NONE)
$ grep -rn "adf_pvalue\|engle_granger\|garch_conditional" --include=*.py . | grep -v tests/
(no output outside ops/VPS_DEPLOY_PROMPT.md prose)

$ python /tmp/why.py libs.research.dist_shift
importers: (NONE)
$ grep -rn "distribution_shift\|split_and_check" --include=*.py . | grep -v tests/
(no output)
```
Zero importers, anywhere, for both. The desk's live capital is in cash-and-carry — a **spread**
trade whose entire economic premise is that basis mean-reverts, i.e. that two series are
cointegrated. The Engle-Granger test that would check that premise is written, tested, and
imported by nothing. Likewise `dist_shift`, which is the only distribution-shift detector in the
repo, on a desk that trades a regime-sensitive asset class.

Under the audit's distributional-assumptions remit this is the largest negative-space item found:
the assumption most load-bearing for the deployed sleeve is the one with no instrument attached.

**N13 UPDATE — the `dist_shift` half was closed at 01:47 today, mid-audit, by a sibling session.**
The tree moved under me and I am reporting it rather than shipping a stale claim.
`scripts/revalidate_clocks.py` (modified `Aug 1 01:47`, uncommitted at time of writing) now imports
`libs.research.dist_shift.split_and_check` and `libs.validation.revalidation`, and produced
`data/clock_revalidation.json` at 01:47. Credit where it is due: **it caught its own welded-gate
defect on the first run and fixed it**, in its own words —
> "a two-window distribution test fed RAW LEVELS fires on any trending series: a deterministic
> constant-increment ramp — a process with no distributional change whatsoever — returns SHIFT...
> The first run of this wiring duly reported SHIFT on both axes with an identical 0.35 haircut,
> which is the welded-gate signature: a detector that fires on everything carries zero information."

It now tests the z-score the strategy actually consumes, and carries a correct refusal path
(`"UNMEASURED means no axis series was fetched... never that the distribution is stable"`). That is
the L1.41 build standard met properly. Live output:
```
"status": "SHIFT", "capital_blocked": ["stablecoin_supply_momentum"]
  kimchi_premium              dist_verdict STABLE  haircut 0.00
  stablecoin_supply_momentum  dist_verdict SHIFT   haircut 0.35  triggers ['structural_break']
```
**Two caveats that keep this a finding rather than a closure.** (i) It is **not scheduled** —
`crontab -l | grep -i revalidate` is empty and it appears in neither `daily_research_cycle._STEPS`
nor `run_daily_research`. Under L1.41 condition 3 an unscheduled organ needs a recorded exemption,
and under L1.28c a cadence nobody decided is idle capacity. A distribution-shift detector that runs
when someone remembers is a detector that will be stale exactly when a regime turns. (ii) It covers
**distribution shift only**. The cointegration half of N13 — Engle-Granger on the carry basis, the
LTCM rail — remains completely open: `stationarity.py` still has zero importers.

**No regime-robustness gate exists at all.** `validate()`'s complete gate set is:
```
$ sed -n '473,488p' libs/autodiscovery/validation.py | grep -oE '"[a-z_]+":'
"economic_mechanism": "expected_value": "cpcv": "walk_forward": "dsr": "pbo":
"reality_check": "capacity": "fragility": "beats_baselines":
```
Ten gates, and not one requires an edge to survive across multiple regimes. No regime module
reaches `validate()` or `run_discovery.py` (`grep -rn "crypto_regime\|regime_validation"` over both
→ no output). Regime robustness — a first-class item in this audit's remit and a standard gate at
every firm in the benchmark cohort — is **not tested anywhere on the path to capital**. Combined
with the absence of any structural-break test on a candidate's return series (`grep -rniE
"chow_test|cusum|bai_perron|breakpoint"` finds only the `structural_break` *flag* consumed by
`revalidate_clocks.py`, never a test that produces one from a return series), the desk currently
detects a break only after deployment, by drawdown.

---

### N14 — HIGH (false-green): `collapse_detector` writes fabricated perfect-diversity scores onto a live scoreboard.

`scripts/run_generation_diversity.py:70-71` runs on cron `23 */6`. Its `_DB` is
`data/research_memory.db`, which **does not exist**, so `_batch()` returns `([], [])` and the
module emits its defaults:
```
$ cat data/gen_diversity.json
"n_in_batch": 0, "mechanism_entropy": 1.0, "feature_breadth": 1.0, "semantic_distinctness": 1.0
```
Those `1.0`s are **defaults, not measurements**, and `_append_scorecard` writes them into
`data/panel_scorecard.json`. The console log says "NO BATCH" honestly; the JSON artifact — the
thing other organs read — reports perfect generation diversity. `record()` has zero production
call sites so `data/gen_diversity_history.jsonl` never exists and `assess()` runs at
`n_trailing: 0` forever.

This is exactly the failure class L1.41 condition 1 exists to prevent (a refusal path: an organ
with no vocabulary for "I could not measure" reports OK on absent input), shipped and running.

---

### N15 — HIGH: the hypothesis-dedup engine is dead while the desk's own artifact says throughput is re-drawing a known pool.

`libs/research/variation_blocker.py`: `screen()` (:77) and `record()` (:102) have **zero
production call sites**; only `telemetry()` is called. Its `LEDGER = data/variation_ledger.jsonl`
does not exist, so telemetry reads a file nothing writes:
```
"variation_telemetry": {"n": 0, "note": "no generation screened yet"}
```
Meanwhile `web/pilot.json` records 1,244 trials, 0 survivors, and concludes in its own text that
*"throughput is re-drawing a known pool"*.

The novelty-gate duty in the doctrine is explicit that a redundant hypothesis "burns DSR
multiplicity budget twice, making every OTHER candidate harder to promote". N6 shows the
multiplicity budget is the binding constraint. So this orphan is not merely unused capability —
**it is actively inflating the denominator of the bar that is rejecting everything.** If a
material share of the 420 are re-draws, the effective trial count is far below 420 and the DSR bar
is over-deflated by a measurable amount (N6c). Wiring `screen()` into the generator is the cheapest
available reduction of the bar that loosens no threshold.

---

### N16 — CRITICAL (Stage B): the stopping rule was rewritten mid-clock, in the direction of the result, citing the candidate's own observed Sharpe.

This is the most serious validation-honesty finding in the sweep, and it sits on the only path that
has ever carried real capital.

`data/decision_ledger.json`, id `2026-07-09-adaptive-validation-windows`:
> "decision": "Replace fixed 90d validation with evidence-based windows: fast-track at >=40d when
> forward t-stat >=1.65 AND fwd>=0.5x backtest; standard 90d otherwise"
> "hypothesis": "...a Sharpe-13 carry is provable in 40d, a Sharpe-1.4 trend is not..."
> "expected_benefit": "carry live-eligible ~Aug 5 instead of ~Sep 24 (7 weeks earlier compounding)"

The cash-and-carry forward clock **started 2026-06-26**. This decision is dated **2026-07-09 — day
13 of that live window.** It justifies itself by citing the observed Sharpe of the candidate under
test, and it names the exact date the shortened rule makes that candidate eligible.

That is textbook optional stopping: the stopping rule was selected after seeing the data, for the
specific hypothesis being tested. The resulting bar is 1.65 rather than the cohort's Holm bar of
2.64, and cash-carry is at day 35 with NW-t 2.28 — it flips to live-promotable on **2026-08-05**,
four days from now.

Three aggravating details:
- **No maximum window exists anywhere.** `run_axis_shadows.py` has `_MIN_DAYS = 40` (a floor on
  when looking starts) and no ceiling. A clock reading FAILING at day 40 runs to 41, 42, … until it
  crosses. Unbounded optional stopping, on top of the rule change.
- **Double-counted exemption.** cash-carry claims Holm-exemption as a "pre-registered PRIMARY
  hypothesis" yet appears in `derive_slots()` as slot 5 of 12 — raising every other axis's bar from
  2.61 to 2.64 while facing 1.65 itself.
- **It went live before its own clock.** `web/portfolio.json` shows `cash_and_carry (real)` with
  `days_live: 29.85`, against a clock that started 2026-06-26 — i.e. capital was deployed at
  roughly **forward day 6 of a 40-day minimum**, while the artifact still says *"must hold forward
  before any capital."*

---

### N17 — HIGH (Stage B): the daily-peeking inflation is ×5.0, and the realised cohort error rate is 23.1% against a designed 5%.

V7 re-measured at today's bar (`holm_bar(12,1) = 2.64`, 20k null paths):
```
single look day 40      : 0.00550
daily peeks day 40->90  : 0.02080  (x3.78 vs single look)
daily peeks day 40->120 : 0.02515  (x4.57)
nominal one-sided at 2.64: 0.00415
inflation vs NOMINAL, peeks to 90d: x5.02
cohort FWER m=12, daily peeks to 90d: 0.2306   (design 0.05)
```
`run_axis_shadows.py:150-155` evaluates a fixed-sample t-statistic every day
(`daily_research_cycle.py:120`, cron `0 2 * * *`). The desk owns the correct instrument —
`libs/research/anytime_valid.py`, e-values, valid under continuous monitoring — and it gates
nothing: its only two importers write it into a JSON field for display. Last commit touching it
`020b02a`, 2026-07-22. **Nine days, zero wiring.**

The two errors compound in opposite directions and do not cancel: the *screen* is far too strict
(N3, N6) while the *promotion* stage's true error rate is 4.6× its design. The desk is rejecting
real candidates upstream and would admit false ones downstream.

---

### N18 — MEDIUM/HIGH (Stage B): the cohort size is circular, three slots are structurally inert, and no forward clock has ever completed.

- **Circular `m`.** `concurrent_m()` reads `data/axis_shadow_state.json`, the file
  `run_axis_shadows.py` writes at the end of the same run. Every axis is judged against the
  *previous* run's cohort; on 07-31 all four axes were scored at 2.61 when the live bar was 2.64.
- **Three of twelve slots cannot produce evidence.** `defi_utilisation`: `z20=[0,0,0,0]`, every
  return exactly zero, `nw_tstat` returns 0.0 on sd=0 — it can never cross. `cny_premium`: 0/40
  days after nine days, `z20=[None]×9`, and `data/claim_verification.json` grades this **OK**.
  `crossasset`: artifact frozen **41 days** (`web/crossasset_shadow.json`, 2026-06-21) and
  `run_crossasset_shadow.py` appears in no cron line and no cycle step — a dead clock holding a
  live slot. Because the registry counts *files* rather than *evidence*, `idle_slots: 0` and no
  L1.28a idleness alert fires, while `run_promotion_queue` reports a 90-day estimated queue wait
  on an empty queue.
- **Nothing has ever been promoted.** `data/alpha_lifecycle.json`: `"furthest_gate": 5` of 11;
  `scripts/alpha_lifecycle.py:236` states *"gates 6-11 (FORWARD_PASSED .. RETIRED) have NEVER been
  occupied."* No axis clock has ever reached day 40 (max observed: kimchi at 8/40 before eviction).
  The axis Stage-B path has never completed a single test.
- **V8 is worse than reported: the invariant violation is pinned by a passing test.**
  `tests/research/test_slot_registry.py:43` asserts as correct the retirement-drops-from-cohort
  behaviour that `run_axis_shadows.py:59-61` calls forbidden ("attrition must never lower the
  bar"). And no production path ever writes the RETIRED verdict, so `slot_registry.py:86` is dead
  code while real retirement happens by editing `_AXES`, which the registry cannot see.
- **V18 changed:** `data/forward_slots.json` is now current, but it is **write-only** — all four
  consumers call `derive_slots()` live and `grep` finds no reader of the file at all.

---

### N19 — HIGH: the cost side of "execution physics" is unmeasured in the validation stack, and the one instrument built to measure it has never emitted a number.

Beyond the dead `stress_costs` gate (N5):
- **The reality-gap comparator is inert.** `scripts/run_reality_gap.py` (cron `23 */2`, built
  2026-07-30) prints `NO-DATA` on all five links, every run: `grep -c "NO-DATA"` → **24**, i.e.
  every line of every retained run. All five are **key-name mismatches against files that exist and
  are fresh** (e.g. it looks for `sharpe` where the file has `forward_ann_sharpe`; for `rt_bps`
  where the tape has `spot_slip_bps`/`fut_slip_bps`). The gap it should have printed is inside a
  file it already opens: `backtest 3.320 -> forward 14.300, ratio 4.31 = GAP`. It also carries a 4×
  unit error (`_cost_link()` compares a one-way single-leg median to a round-trip).
- **The measured cost model does not reach the deployed sleeve.** `data/cost_model.json` is a real
  L2 book-walk measurement (30 symbols × 5 sizes) and it contradicts the hardcoded tier table in
  both directions (BTC 3.0 measured vs 5.0 assumed; CELR 10.4 measured vs 5.0 assumed). But
  `crypto_sleeves.py:43` and `crypto_xsec.py:43` hard-code `adv_tier_cost` internally, so the
  five funding/basis/flow sleeves — including the only deployed one — silently discard it.
- **Like-for-like, the desk's own model vs its own fills is a BREAK on its own band:** modelled
  pair round-trip 5.74 bps vs realised 19.03 bps, **ratio 3.32×** (band: GAP >1.5×, BREAK >3.0×).
  523 fill events and 265 closed round-trips exist to check this against.
- **No cost constant has moved since the 2026-07-16 baseline commit** — including after the
  2026-07-31 finding (R0219) that attributed ~66 bps of the carry sleeve's loss to execution.
- **Cost and capacity are not coupled.** Returns use a flat per-unit-turnover bps constant, so the
  return series is invariant to book size; the sqrt-impact `slippage_curve` computed by
  `capacity_estimate` is discarded (`validation.py` reads only `cap.capacity_usd`). Capacity
  therefore *cannot* bind even if N10 were fixed.
- **Survivorship.** `run_discovery.py:57` builds the universe from a live call to Binance
  `fapi/v1/ticker/24hr` sorted by *today's* 24h volume, top-120, then drops anything with <250
  bars. A perp liquid in 2022 and delisted by 2026 is never requested. The desk uses the correct
  point-in-time pattern elsewhere (`backfill_oi_ls_oos.py:22` explicitly reconstructs "including
  delisted symbols... no survivorship pick") and did not apply it here.
- Queue position, partial fills, liquidations and exchange halts are unmodelled; `libs/backtest/
  queue_fill.py` implements maker-fill modelling and is orphaned, while the live tape shows spot
  legs fill passively only **31%** of the time against a 60% target.

---

### N20 — MEDIUM: further orphaned rigour, and one timed-not-dead loop worth watching.

Dead functions inside otherwise-live modules (each tested, each with zero production callers):
`reality_check.hansen_spa`; `revalidation.RevalidationController` / `RevalidationTrigger` (the
production-capital fail-closed controller — `app/readiness.py:74` is a bare-constructor smoke test
and `app.readiness` is itself unreachable); `gate_calibration.reconstruction_verified` (7 grep
hits, all in its own test); `dsr.min_track_record_length` and `dsr.probabilistic_sharpe_ratio`;
`capacity_policy.{capacity_required, niche_share, outgrown_at, sleeve_equity}`;
`ic.{cross_sectional_ic, ic_stats}`; `pre_filter.{audit_due, ledger_counts}`;
`profit_retention.{trailing_stop_exit, time_decay_exit, vol_target_overlay}` — the last three
being the exact remedy `web/capture.json` calls for in its own `next_step` ("carry book has no exit
logic", capture 0.1), ten lines away in the same file.

Never-produced artifacts: `libs/validation/report.py:generate_validation_report` (no
`validation_report*` file has ever existed); `scripts/run_onchain_history_backtest.py` (cron
`25 4 * * *`, `web/onchain_history_backtest.json` does not exist);
`scripts/run_autodiscovery.py` (cron `20 3 * * *`, all six outputs frozen at 2026-06-20 — **42
days**).

**Timed, not dead (do not kill):** the reject-recovery loop (`reject_rescore` +
`rejection_shadow` + `gate_calibration`) is correctly wired and runs daily, but is arithmetically
vacuous until **2026-08-10** (`min_age_days=30`; oldest reject 2026-07-11). Its first real verdict
should be read rather than missed. Note `data/reject_forward_scores.json` has never existed, so
the re-eval hook itself is unproven — worth a ledger row with an 08-10 due date.

---

### N21 — MEDIUM/HIGH: the two out-of-sample gates in the same `validate()` call disagree about serial correlation. One purges and embargoes; the other has no embargo at all — and it is the harshest informative gate in the stack.

`validate()` runs two OOS consistency checks on the same return series:
```
validation.py:432:  wf = WalkForwardEngine().evaluate(arr, n_splits=4, test_size=max(20, len(arr) // 6))
validation.py:249:  CPCV(n_groups=6, n_test_groups=2, purge=2, embargo=0.01)
```
CPCV purges 2 observations at each boundary and embargoes a further 1%. The walk-forward engine's
signature is `evaluate(..., embargo: int = 0)` (`revalidation.py:91`) and `validate()` **does not
pass one** — so `walk_forward_splits` runs with `train_end = test_start - 0`, i.e. the training
window ends on the bar immediately before the test window begins.

This is the V11 inconsistency, located precisely. It matters more than it looks because
`walk_forward` is the **harshest gate that carries any information**: 176/420 pass, versus cpcv's
238 and pbo's 209 (`reports/gate_histogram.json`). A gate with no embargo on a serially-correlated
stream leaks train→test information, which biases it *optimistic* — so the desk's strictest
informative gate is also its leakiest, and nobody can currently say how much of its 176/420 pass
rate is real. The fix is one keyword argument; the correct value is the label horizon, which is
also the number nobody has written down (see below).

**Two related items in the same seam:**
- **The block-bootstrap length is hardcoded at 10 in all three consumers** and no caller overrides
  it (`bootstrap.py:56`, `stepwise.py:162`, `reality_check.py:38` — all `mean_block: float = 10`).
  Every multiplicity p-value on this desk — Romano-Wolf, White's RC, Hansen's SPA — depends on this
  constant, and it is an assumption that the autocorrelation of the return series dies inside ~10
  bars. It has never been checked against the actual series, and the standard automatic selector
  (Politis–White) is not implemented. Given that N3's whole verdict turns on a bootstrap p-value of
  0.0014, the sensitivity of that p-value to `mean_block` is an unmeasured input to the desk's most
  consequential statistic.
- **The label horizon is not declared anywhere in the validation stack.** Purge (2 bars) and
  embargo (1%) are constants, not functions of a stated forward-return horizon; nothing in
  `validate()` knows or asks how many bars forward the label looks. If any candidate uses a
  multi-day forward return, its overlapping windows inflate the effective sample and neither purge
  distance nor `T` is corrected for it. No overlap deflation is applied anywhere.

---

### N22 — CRITICAL: CPCV's purge and embargo are INERT. The gate cannot see them, and the fix that was celebrated for removing a leak removed nothing.

`validation.py:228-245` carries a 14-line docstring explaining that the old `np.array_split` leaked
across fold boundaries and that purge+embargo now fix it. The gate that consumes the splitter,
`validation.py:251`:
```python
positive = [bool(arr[s.test].mean() > 0)
            for s in splitter.split(len(arr)) if len(s.test) > 1]
```
**`s.train` is never referenced.** Purge and embargo remove *training* rows; the statistic reads
only *test* rows. They are arithmetically incapable of changing the output. Proved on the desk's
real `funding_carry` candidate (n=2520):
```
occurrences of ".train" in _cpcv_positive_fraction: 0

purge=   0 embargo=0.00 -> cpcv_positive_fraction = 0.733333
purge=   2 embargo=0.01 -> cpcv_positive_fraction = 0.733333
purge=  50 embargo=0.10 -> cpcv_positive_fraction = 0.733333
purge= 500 embargo=0.40 -> cpcv_positive_fraction = 0.733333
production value = 0.733333   threshold _CPCV_MIN_POSITIVE = 0.6
```
Identical to six decimals across a 250× range of purge. The gate reduces to *"is the mean positive
in ≥60% of the 15 pairings of 6 contiguous sixths"* — a deterministic function of six numbers, with
no leak protection of any kind.

This is the desk's inert-fix class in its most expensive form: the leak was correctly diagnosed, the
correct machinery was built (`libs/validation/cpcv.py` is a proper López de Prado implementation),
it was wired in, tests passed, the docstring was written — and **the statistic was never changed to
look at the thing that was fixed.** The desk currently believes it has leak-proof cross-validation
on its primary OOS gate and does not. Combined with N21 (walk-forward embargo=0) and the fact that
neither PBO implementation has purge, embargo or block structure at all, **no gate in the live path
has any leak protection whatsoever.**

The embargo is also the wrong quantity even if it were read: `cpcv.py:69` computes it as
`round(embargo * n_samples)` — a fraction of the *sample*, not of the label horizon. It scales with
how much data you have. Against feature windows of `rolling(7)`, `rolling(30)` and `rolling(252)`
(`crypto_xsec.py:39-40`, `run_crypto_portfolio.py:100`), the configured purge is **2 bars**.

---

### N23 — CRITICAL: the reported `annual_sharpe` is overstated 4.1× on every daily candidate, and it is persisted, surfaced and used to rank.

`validation.py:40`: `_PERIODS_PER_YEAR = 24 * 260` (= 6240, i.e. hourly bars), applied at `:463` to
daily crypto sleeves:
```
metrics.annual_sharpe reported = 3.84
correct daily annualisation    = 0.929
overstatement factor           = 4.135 x
```
This is not a display-only defect. The value is persisted (`libs/autodiscovery/memory.py:26,85`),
surfaced in reports (`crypto_adapter.py:181`, `reports.py:42`), and **used to rank rejects for
re-scoring** (`scripts/run_rejection_rescore.py:107`). Every human or organ reading a Sharpe off a
desk report is reading a number 4× too large — including anyone assessing whether the desk's
candidates are "good enough to be worth the gate", which is the exact question this whole audit
turns on. No gate consumes it, which is the only reason this has survived.

**N23b — the same path strips zeros before validating, inflating Sharpe by 1/√p.**
`run_crypto_portfolio.py:126`: `active = r[r != 0.0]` (also `:93`, `crypto_regime.py:37`,
`run_reversal_costtest.py:61`):
```
full series n = 2520   after r[r!=0] n = 2364   fraction kept p = 0.9381
Sharpe(full)*sqrt(365)   = 0.8994
Sharpe(active)*sqrt(365) = 0.9287   <- what the report prints
inflation = 1.0325   predicted 1/sqrt(p) = 1.0325
```
Exactly the predicted bias. It also destroys the calendar index, so CPCV's contiguous blocks and
walk-forward's windows no longer map to contiguous time — flat days (no position) are silently
deleted rather than counted as zero return, which is what they are.

---

### N24 — HIGH: the regime gate labels regimes in-sample, contemporaneously, and passes 47.2% of pure noise. It is a calendar proxy, and it is not wired into the path that validates the real sleeves.

`libs/autodiscovery/regime.py::regime_robust`, wired only at `orchestrator.py:257` as a
REGISTRY→PAPER **demotion**, not a rejection — and absent from the three scripts that validate the
desk's actual crypto sleeves (`grep -c "regime_robust\|LockedHoldout"` → 0 in
`run_crypto_portfolio.py`, `run_xsec_funding_max.py`, `run_discovery.py`).

Two leaks in six lines:
```
regime.py:25:  vol[i] = returns[i - window + 1 : i + 1].std()      <- includes bar i itself
regime.py:29:  lo, hi = np.nanquantile(vol, [1 / 3, 2 / 3])        <- terciles over the WHOLE series
occurrences of "shift" in the module: 0
```
The label at *t* is contemporaneous with the return at *t*, and the tercile boundaries know the test
period. (Contrast `libs/research/crypto_regime.py:25-32`, which correctly `.shift(1)`s every axis —
and is explicitly diagnostic-only with no gate authority.)

Because terciles guarantee three non-empty buckets, `present >= 2` (`regime.py:49`) is always true
and the gate collapses to "≥2 of 3 tercile sums positive":
```
=== PASS RATE ON PURE NOISE, n=1000, 400 draws ===
   true ann Sharpe 0.0: regime_robust PASSES  47.2%
   true ann Sharpe 0.5: regime_robust PASSES  75.2%
```
And the "regimes" are a proxy for calendar time, not market state — the sleeve's own vol falls
monotonically as the cross-section widens from 12 names (2020) to 271 (2026):
```
year   -1    0    1    2        (0=low vol, 1=mid, 2=high)
2021    0    3   92  270    <- 74% high-vol
2025    0  298   47   20    <- 82% low-vol
```
So the gate asks "was the edge positive in ≥2 of 3 calendar chunks", not "did it survive a bull, a
crash and a chop". The desk owns a real regime engine (`libs/regime/hmm.py`, `gmm.py`, `bayesian.py`)
and it produces a *leverage multiplier* for the live book, never a validation verdict.

---

### N25 — HIGH: `signal_governance_gate` can never return True in production. Its structural-break input has exactly one writer, and it is a test fixture.

```
$ grep -rn "structural_break_pass" --include=*.py .
libs/signal_engine/governance.py:27:    structural_break_pass: bool = False
libs/signal_engine/governance.py:40:        and verdict.structural_break_pass
tests/signal_engine/conftest.py:68:    ... structural_break_pass=True, ...
```
Declared, required, and written only by a test. In production the field is permanently `False`, so
the eight-gate signal-governance path is **unreachable rather than passing**. It fails closed, which
is the safe direction — but by accident, not by design, and it means an entire governance stack the
repo appears to run does not run.

More broadly, there is **no structural-break test anywhere in the repo**:
```
$ grep -rniE "chow_test|cusum|bai.?perron|supf|sup-wald|qlr|andrews.?quandt|pettitt|pelt|ruptures" --include=*.py .
tests/validation/conftest.py:40:  "how_detect_decay": "CUSUM on live IC vs backtest confidence band"
```
One hit, in a fixture, describing a plan — with `statsmodels` and `arch` both installed. The
`revalidate_clocks` wiring (N13 update) is a two-sample distribution *monitor* on a fixed 75/25
split of the signal series: no break date, no test against a break-point null, no multiple-break
search, and it never touches a candidate's return series. Outside it, a break is detected only after
deployment, by drawdown (`libs/risk/drawdown.py:64`, `risk_controls.py:63`).

---

### N26 — HIGH: quantified, the DSR gate's two distributional corrections both run LOOSE. Type I is 1.75× nominal at AR(1)=0.2.

V11's serial-correlation gap, measured end-to-end on the real candidate:
```
n = 2520   ann_sharpe = 0.899   lag-1 rho = 0.0214
desk's own Bartlett VIF autocorr_factor(r) = 1.2385
   => effective N = 2034.7 vs raw n = 2520  (evidence loss 19.3%)
   PSR z with raw n       = 2.4456 -> PSR = 0.992769
   PSR z with n_eff       = 2.1974 -> PSR = 0.986005
   z inflation factor     = 1.1129 (= sqrt(VIF))
   forward_stats on the SAME series: nw_tstat = 2.12   naive t = 2.36
```
The desk owns the correction (`forward_stats.autocorr_factor`) and applies it at the *forward*
stage while the *gate* uses raw `n`. Type I consequence on pure nulls (4000 reps, n=2520):
```
  ar1   PSR>=0.95 FPR
 0.00          5.20%
 0.10          6.35%
 0.20          8.75%     <- 1.75x nominal
 0.40         13.98%     <- 2.80x nominal
```

**N26b — and the non-normality correction is loose too, which is the opposite of what everyone
assumes.** The moments *are* estimated (`dsr.py:35-36`, unbiased, non-excess kurtosis) — so the
"defaults to normal" hypothesis is **refuted**. But on the real candidate (skew +1.63, kurtosis
19.3):
```
PSR denominator WITH estimated moments = 0.93344588
PSR denominator IF moments were normal = 1.00110813
ratio 0.932413 -> z scales by 1/sqrt(ratio) = 1.035609
```
Positive skew enters as `−g3·SR` and *reduces* the estimator variance, making the fat-tail-aware PSR
**3.6% more permissive** than a naive normal one. And the kurtosis term is nearly inert at daily
resolution: at SR=0.047 it contributes **+1.0%** to the denominator, because it scales as `SR²`. The
formula only becomes conservative above annualised Sharpe ≈ 6.

**Net:** the DSR z on the desk's best candidate is ≈**1.15× too large** (1.1129 × 1.0356), giving
PSR 0.9928 where the honest number is 0.9860. A candidate reported at DSR 0.951 is genuinely at
0.936 and should have failed. This is the one place in the whole report where the gate is too
**loose**, and it sits inside the gate that is otherwise too strict — which is precisely why
"tighten it" and "loosen it" are both wrong answers and E1 is the right one.

**N26c — block length 10 is a magic number in five signatures**, never overridden, with no
Politis–White selector anywhere (`grep -rniE "politis|opt_block|b_star|auto.?block"` → no hits).
Measured on a true-null AR(1)=0.3 matrix where the correct answer is 5.0%:
```
 mean_block      FPR
          1     26.7%
         10      6.7%
         50      5.8%
```
Ten is roughly adequate here — credit where due, this is the one place serial correlation *is*
handled — but it was never verified against the desk's own autocorrelation, and N3's entire verdict
rests on a bootstrap p-value whose sensitivity to this constant is unmeasured.

---

### N27 — HIGH: the sample is far thinner than every power argument on this desk assumes. Eight independent macro episodes, a 7.3-month common panel span, and no crypto winter.

```
=== BTC SAMPLE SPAN AVAILABLE TO VALIDATION ===
first: 2019-09-08  last: 2026-08-01  days: 2520
MISSING: the 2017 bull top and the ENTIRE 2018-19 bear (Binance perp data starts 2019-09)

=== MAJOR BTC DRAWDOWN EPISODES (>25%) ===
   8 independent macro episodes  (covid, China ban, LUNA+FTX, yen carry, ...)
   daily N the tests use: 2520
   ratio: 315 days per independent macro episode
```
And the cross-section is much shallower than the headline:
```
universe symbols: 279   history rows: median 810 (2.2y), p25 452, max 4947
  >= 2 years:  144 symbols      >= 5 years:  59      >= 6.9 years:  5
COMMON span (max-of-firsts -> min-of-lasts): 2025-11-11 -> 2026-06-21   (7.3 MONTHS)
```
Against which the desk's own report claims `"perps": 98, "days": 2520`, while:
```
days with >=12 usable names: 2371     days with >=50 names: 1963
days with >=98 names: 1078   first 2023-08-10
```
**The 98-perp strategy the report describes has 1,078 days of data, not 2,520.**

This reframes N7 and the BitMEX programme. The T-lever is real and it is bigger than the min_len
truncation: even after fixing truncation, the *universe-wide* common span is 7.3 months, the median
symbol carries 2.2 years, and **every candidate this desk has ever validated was fit on a sample
that begins after the last full crypto winter ended.** No amount of multiplicity correction
compensates for 8 independent macro observations. This is the strongest available argument *for*
the decade-ingest programme — and it is a different argument from the one the spec makes (which
rests on the retracted `min_passing_true_sharpe = 5.0`).

Storage footnote, because it bears on the "irreplaceable moat" claim: `du -sh data/*` gives
7.3G `data/moat` (L2 snapshots, first file `20260722` — ~10 days) against 160M for the crypto
price/funding panel every validation actually runs on. **93% of desk storage is 10 days of order
books.**

---

### N28 — HIGH: the desk's best candidate fails the two tests that were not run on it.

`funding_carry` is recorded in `reports/crypto_portfolio/report.json` at `"gates": "9/10",
"fails": ["reality_check"]`. Run the gates it never met:
```
  validation slice : 2019-09-08 -> 2025-03-15 (2016 d)
  LOCKBOX (last 20%): 2025-03-16 -> 2026-08-01 (504 d)
  lockbox test: mean(held) > 0  ->  False   mean = -1.071e-05
```
**It fails the lockbox** — negative mean over the most recent 504 days. The lockbox is
orchestrator-only; `run_crypto_portfolio.py` never opens one.

And the walk-forward gate it *does* pass, passes at exactly the threshold:
```
   split0: OOS 2021-12-26..2023-02-18   mean=+1.647e-04  positive=True
   split1: OOS 2023-02-19..2024-04-13   mean=-2.707e-04  positive=False
   split2: OOS 2024-04-14..2025-06-07   mean=+4.793e-04  positive=True
   split3: OOS 2025-06-08..2026-08-01   mean=-1.074e-04  positive=False
```
2 of 4, against `min_stability = 0.5` — and **the most recent 420-day window is negative**. Four
draws with a coin-flip bar is the entirety of the sequential regime evidence in the live path.

Taken with N23 (its reported Sharpe is 4.1× too large) and N28's lockbox failure, the honest
statement is: the desk's single best candidate is *not* a strong candidate blocked by an
over-strict gate. It is a marginal candidate whose reported strength is an artifact, blocked by a
gate that is over-strict for unrelated reasons. **Both of the desk's competing narratives — "the
gate is welded" and "the space is picked clean" — are partly right, and neither is the whole story.**

---

## SIX PERSPECTIVES

**1. INTERNAL (measured, not configured).** The instrument has never admitted anything: 0 survivors
in 1,244 trials (`web/pilot.json`), `furthest_gate: 5` of 11, gates 6–11 never occupied. Three of
eleven gates carry zero information (N4); one more is a nested duplicate of another (N10). The two
measurements that would characterise the gate — the power audit and the certification — are
respectively unwritten (N2) and self-greening (N1). **A gate that has rejected 100% of everything
for its entire life, and whose calibration artifacts do not exist, is not a strict gate; it is an
unmeasured one.**

**2. EXTERNAL — the motive-similar tier-1 cohort.** Three transferable practices the cohort has
and this desk does not:
- *XTX / HRT / Jump:* the trial count is a **desk-level ledgered quantity**, not a per-script
  argument. N6 shows nine scripts each inventing their own, spanning 2 to 420. No firm at this tier
  would let the deflation term be a caller's opinion.
- *Optiver / IMC / SIG (and RenTech, the standing exemplar):* cost and impact are calibrated from
  **own fills**, continuously, and the calibration is a first-class monitored artifact. This desk
  has 523 fill events and 265 closed round-trips on disk, a comparator built to use them, and it
  has emitted `NO-DATA` on every run since it was built (N19). Medallion's defining practice is
  precisely that its transaction-cost model is fitted to its own executions and treated as an
  alpha in its own right; here the modelled/realised ratio is 3.32× — a BREAK on the desk's own
  band — and nothing reads it.
- *Jane Street / DRW:* a screen **ranks**; error control is paid once, at the point of capital
  commitment. Applying FWER across 266 backtests at the screen (N3, N11) is a category error that
  a trading desk with a research pipeline would not make, because it makes generation
  self-defeating.

*Negative exemplars (control group).* Which of our rails would have stopped their deaths, and does
it fire? **LTCM** — cointegration breakdown in a spread book. Our candidate rail is
`libs/research/stationarity.py` (Engle-Granger); it has **zero importers** (N13), so the rail does
not exist, on the desk's only live sleeve, which is a spread trade. **Archegos** — concentration
and unmodelled liquidation. `capacity`/`fragility` nominally cover this; N10 shows capacity is the
sign of the mean return, and liquidation/margin state is absent from every return path (N19). Rail
does not fire. **Alameda** — mark-to-model equity. Directly present: `live_book_usd()` returns
$18,675.73 from a *molded simulated curve* (`nav_attestation`: `"molded_curve_usd is a
MOLDED/SIMULATED curve, not venue truth"`, `deployed_notional: 0`, `mode: PAPER`) against venue
truth of $6,257.59 — **2.98× hot** — and every capacity ratio on the desk is a ratio to it. The rail
that should catch this is the NAV attestation chain, and it is the thing being bypassed.
**Tier-grade impact: I would not grade validation-stats above Tier 3 on this evidence**, and the
binding reason is not statistical sophistication (which is genuinely good) but that no instrument's
output is consumed.

**3. FUTURE (2–3 years).** Two changes make most of this stack obsolete rather than better.
(a) **Ragged-panel multiplicity by simulation.** Cheap compute makes the rectangular-matrix
constraint (N7) unnecessary: simulate the null of the *actual* unbalanced panel — per-candidate T,
observed correlation structure — and read the critical value off it. No truncation, no
independence assumption, no `N_eff` approximation. This is affordable today at this cohort size
(my B=10,000 Romano-Wolf run on 2109×266 took 35s). (b) **Continuous forward monitoring as the
default**: e-values/e-processes (already in the repo, unwired — N17) make the daily-peek problem
vanish and make "stop when decisive" statistically legitimate, which is exactly what the desk
wants and is currently obtaining illegitimately (N16).

**4. CONTRARIAN — test the core assumption.** The desk's stated core belief is *"the multiplicity
bar is honest; the SAMPLE is what is unpayably short"*. I tested it and it does not survive intact.
Honest: the bar is *arithmetically* correct given its inputs. Not honest: its inputs are a raw
trial count treated as independent (N6), a σ inflated 1.20× over the null by including signal
dispersion (N6c), a cohort inflated by an unknown share of re-draws because the dedup engine is
dead (N15), and a matrix truncated 6.8× (N7). And the decisive test: **increasing T by 6.8× does
not change the verdict** (0 survivors at max_obs) and **the FDR fix does not either** (N3). So the
"sample is the constraint" hypothesis is, on the desk's own artifacts, *insufficient* — it may be
necessary, it is demonstrably not sufficient, and a multi-month data programme is currently
justified on it.

Second contrarian probe, and it cuts the other way — against my own findings: is the gate perhaps
*correctly* rejecting because these 420 candidates are genuinely worthless? Evidence for: 0/1,244
across the whole factory; `web/pilot.json`'s own conclusion that throughput is re-drawing a known
pool. **I cannot rule this out and I will not pretend to.** But it is untestable while the
instrument is uncalibrated — which is precisely why N1/N2 rank above everything else here. You
cannot distinguish "picked clean" from "welded" without a control at a realistic effect size, and
the desk has never run one.

**5. GREENFIELD.** Rebuilding today with only validated knowledge, the stack would be: one
`validate()`; the trial count owned by a ledger, not a parameter; a **ranking** screen (raw p or
q-value, no threshold); multiplicity paid once at the forward stage; forward evidence monitored
with e-values so peeking is legal; cost and capacity fitted from own fills and coupled to the
return series; and every gate born with a Type-I/Type-II curve and a floor. Historical baggage to
delete: two gauntlets (N5), five capacity policies, the campaign-constant legacy path retained
"for unmigrated call sites", and `libs/stage15/` (unreachable). Roughly 40% of `libs/validation/`
by module count is currently unreachable or vacuous.

**6. FRONTIER (recently possible, unexploited).** (a) **e-values / e-processes and anytime-valid
inference** (Grünwald–de Heide–Koolen; Ramdas et al.) — the module is in the repo and gates
nothing (N17); this is the single most mature frontier method the desk already owns and does not
use. (b) **Effective-number-of-trials via trial clustering** (López de Prado's own later work) —
directly addresses N6's independence assumption, needs only the correlation matrix the desk already
computes. (c) **Ragged-panel bootstrap** — no library needed, just removing the truncation.
(d) **Deflated-Sharpe alternatives that condition on the search path** rather than a scalar count.
None of these requires a purchase, a licence, or new data.

---

## NEGATIVE-SPACE SWEEP (what has never been looked at at all)

- **No gate has ever had its Type-I/Type-II curve measured on disk.** The harness exists (N2). The
  question "at what true Sharpe does this stack detect an edge 80% of the time" has no answer.
- **No control has ever been run at a realistic effect size.** Every certification point is SR=10.
  SR 1.0–3.0 — the entire operating range — is unmeasured.
- **No structural-break test exists anywhere in the stack.** No Chow, CUSUM, or Bai–Perron on any
  candidate return series or feature distribution. Breaks are detected post-deployment, by drawdown.
- **No cointegration test reaches production** (N13) — on a spread book.
- **The joint operating characteristic of screen-multiplicity × forward-multiplicity has never been
  computed.** The desk pays FWER twice and nobody has asked what the combined power is.
- **`N_eff` (effective independent trials) is computed nowhere**, though the correlation matrix
  needed for it is already built every campaign.
- **No gate consumes a ruin or drawdown statistic**, while L1.23 makes ruin ≤2% a survival rail.
  `fragility` is a tail-shape score, not a ruin probability.
- **Overlapping-label deflation is applied nowhere.** If labels are multi-day forward returns, the
  effective T is below the nominal T and no statistic corrects for it. (Handed to the regime
  sub-audit; not yet returned at time of writing.)
- **No simulation of the desk's own failure modes** — no synthetic cohort containing a *known*
  number of planted edges of *realistic* size has ever been pushed end-to-end through the live
  path. That single experiment would answer most of this report's open questions.

---

## 3. WHAT COULD MATTER MOST

Ranked by impact × confidence / (cost × maintenance). Compounding multipliers flagged ⚡.

| # | action | why it ranks here | cost | confidence |
|---|---|---|---|---|
| 0 | **Make the CPCV gate read the purged training fold** (N22) — or delete the parameters and the docstring that claims they work. | The desk's primary OOS gate has *no leak protection at all*, and believes it has the best available. Every candidate ever scored by it — including the 420 — was scored by a gate that is a deterministic function of six contiguous sixth-means. Nothing else in this report changes what the desk knows about its own past results as much as this does. | small | HIGH |
| 1 | **Run the real certification: the existing 8×12 harness, at SR 1,1.5,2,2.5,3,5, with AR(1) ∈ {0, 0.2}** (N1, N9, N26). Then publish and floor the curve. | Everything else in this report is a hypothesis until the instrument is calibrated. It also settles the "picked clean vs welded" question the whole desk is currently arguing from a 1-point artifact — and decides whether a multi-month data programme is correctly aimed. The harness already exists, and `audit_gate_power.py:435` already contains the `ar1: 0.2` row that has never been run. | ~1h compute | HIGH |
| 2 | **Write the gate-power artifact and floor it** (N2). ⚡ | The measurement is already implemented and already ran; only the file is missing. Highest ratio of value to work in the report. Creates the ratchet that makes gate regressions visible forever. | ~0 | HIGH |
| 3 | **Make the screen rank instead of gate; pay multiplicity once, at the forward stage** (N3, N11). ⚡ | This is the desk's own two-stage law, implemented. It unwelds the 0%-accept gate without loosening any bar that guards capital, and it stops the screen bar rising with generation volume — which is what makes maximal generation (L1.8) self-defeating today. | small | HIGH |
| 4 | **Fix the optional-stopping breach on the live path** (N16): a maximum window, a pre-registered evaluation date, and either an e-value monitor or a fixed look. | It is on the only path that has ever carried capital, and a promotion lands **2026-08-05**. Of everything here this is the one with a deadline. | small | HIGH |
| 5 | **Own the trial count in one ledger** (N6, N6b, N6c). ⚡ | Simultaneously fixes the over-strict campaign path and the under-corrected sleeve paths, and removes the fabricated `[sh,-sh]` distributions. One number, nine call sites. | small | HIGH |
| 6 | **Pass the real ADV into `validate()`** (N10) and reconcile the two capacity policies (N8). | One line restores an entire gate from "sign of the mean return" to an actual capacity test, and makes the whole §42 apparatus live rather than advisory. | ~1 line + policy decision | HIGH |
| 7 | **Wire `variation_blocker.screen()` into the generator** (N15). ⚡ | Reduces the multiplicity denominator — i.e. lowers the bar — by removing re-draws rather than by loosening a threshold. The only bar reduction in this list that is unambiguously *more* rigorous, not less. | small | MEDIUM-HIGH |
| 8 | **Fix the five key-name mismatches in `run_reality_gap.py`** (N19) and the 4× unit error. | L2.10 is a constitutional duty with zero current output; the numbers are already in the files it opens. Turns the desk's largest measured discrepancy (3.32× BREAK) from invisible to monitored. | small | HIGH |
| 9 | **Remove the min_len truncation** (N7). | Real 5.9× improvement in the blocking statistic; necessary but not sufficient, and should be scored honestly as such. | medium | HIGH |
| 10 | **Wire `anytime_valid` into the forward evaluator** (N17). | Makes daily monitoring legitimate and makes early stopping legal — which is what the desk wants and is currently taking without paying for. | medium | HIGH |
| 11 | **Give `collapse_detector` a refusal path** (N14) and audit the other 5 organs for the same shape. | False-green on a live scoreboard. The adjacency sweep matters more than the instance. | small | HIGH |
| 12 | **Wire `stationarity` (Engle-Granger) onto the carry sleeve** (N13). | The load-bearing assumption of the deployed book has no instrument. LTCM's failure mode, unmonitored. | small | MEDIUM-HIGH |
| 13 | **Connect `event_study` to `listing_events`** (N12). | Doctrine-mandated by name; data already being collected daily. | medium | MEDIUM |
| 14 | Supply `benchmark_returns` for the non-carry families (N4b). | Converts a 100%-accept gate into a real one at near-zero cost. | small | HIGH |

**Interactions worth stating explicitly.** #5 and #7 both reduce the DSR bar *by fixing inputs*,
and they compound: a smaller, de-duplicated, correctly-counted trial set lowers `sr0` twice.
#3 and #9 also compound (a longer window raises power; a ranking screen removes the FWER wall) —
but #9 alone provably does not clear the gate, so shipping #9 without #3 will reproduce today's
0-survivor result with more compute. #1 must precede any decision about #9's big-brother, the
BitMEX decade programme.

---

## 4. WHAT WE TEST NEXT (concrete experiments)

**E1 — Calibrate the gate at realistic effect sizes. (highest priority)**
Run `libs/validation/positive_control.certify_gauntlet()` — the existing 8-target × 12-seed harness,
not the hand-rolled 1×1 — at true annual Sharpe {1.0, 1.5, 2.0, 2.5, 3.0, 5.0, 10.0} × ≥12 seeds,
through the real `validate()`, on the real cohort statistics, at both the min_len and max_obs
windows.
*Success criterion:* a published detection curve — P(pass) vs true Sharpe — with its 50% and 80%
detection points named, plus the null false-pass rate, floored in a committed artifact.
*What each outcome means:* if 80%-detection lands below SR≈2.5 at max_obs, the gate is defensible
and the sample really is the constraint (the BitMEX programme is correctly aimed). If it lands
above SR≈4, the gate is welded in the operating range and N3/N6 are the binding defects, not T.
*Retirement:* re-run whenever any gate threshold, the trial count, or the window rule changes.

**E2 — Does the screen-as-ranking design admit anything real?**
On the same synthetic cohorts as E1, replace the FWER/FDR screen gate with a top-k ranking by raw
bootstrap p (k = free forward slots) and measure end-to-end: how many planted edges reach a forward
clock, and what the *joint* false-positive rate is after the forward stage's Holm bar.
*Success criterion:* planted-edge recall at the forward stage rises materially while the joint
false-positive rate stays ≤5%. That is the number that decides whether #3 is safe, and it is the
only honest way to make the change — the two-stage law's whole claim is that screen volume is free
*because* the forward stage pays; E2 tests that claim rather than assuming it.
*Retirement:* if joint FPR exceeds 5%, the ranking screen is rejected and FWER stays.

**E3 — Effective trial count.**
Compute `N_eff` from the campaign correlation matrix (trial clustering, or the eigenvalue-based
participation ratio) and recompute `sr0` at `N_eff` instead of raw N. Report the required observed
annual Sharpe at both.
*Success criterion:* a number. If `N_eff` ≪ 420, N6's over-deflation is quantified and the bar drops
without any threshold being touched. My prior, stated so it can be scored: `N_eff` between 30 and
120, giving a required observed annual Sharpe of ~3.7–4.3 versus today's 4.74.
*Retirement:* superseded by E1's empirical detection curve, which measures the same thing end-to-end.

**E4 — Planted-edge end-to-end, with a known answer.**
Inject *k* known edges of realistic size (SR 1.5–2.5) into a real 420-candidate cohort and push the
whole pipeline — screen, FDR, forward clock, Holm — recording where each planted edge dies.
*Success criterion:* a per-stage survival table for known-good candidates. This is the single
experiment that would answer the most open questions in §2, and nothing like it has ever been run.

**E5 — Modelled vs realised cost, on the 265 closed round-trips.**
*Success criterion:* a committed number with a floor, and the reality-gap comparator emitting it
every 2h instead of `NO-DATA`. Prior: the 3.32× like-for-like ratio holds within ±30%.

**Forecasts logged for calibration (L1.29), resolve-by 2026-09-01:** E1 80%-detection point lands
above SR 4 at min_len — **0.75**. E3 `N_eff` < 150 — **0.8**. E2 joint FPR stays ≤5% under top-k
ranking — **0.6**. Removing min_len truncation alone still yields 0 survivors — **0.85**.

---

## CARRY TABLE — V1–V18 from 2026-07-31, re-verified

| id | 07-31 claim | status today | evidence |
|---|---|---|---|
| V1 | gauntlet never certified | **PARTIALLY CLOSED, badly** | certification exists, 1 target × 1 seed → N1 |
| V2 | gate-optimality artifact predates its honesty fix | **OPEN** | `gate_histogram.json` still 2026-07-30 |
| V3 | FDR screen computed and ignored | **CONFIRMED, and it would not help anyway** | N3, N11 |
| V4 | 0 of 420 pass the six gates | **CONFIRMED** | `survivors: []` |
| V5 | capacity gate demands 2× the whole book | **CONFIRMED, unfixed, and worse than thought** | N8, N10 (20× vs policy; and it isn't a capacity gate at all) |
| V6 | two documented params dead in `validate()`'s body | **CONFIRMED** | `capacity_required` is a `# noqa: F401` re-export |
| V7 | Stage-B daily peeking ×4.9 | **CONFIRMED at ×5.0**, cohort FWER 23.1% | N17 |
| V8 | retirement lowers the surviving clocks' bar | **CONFIRMED, and pinned by a passing test** | N18 |
| V9 | sequential slot recycling unaccounted | **CONFIRMED**, 6 hypotheses through ≤4 slots in 9 days | N18 |
| V10 | ledger under-reports reality | not re-checked this sweep | — |
| V11 | serial correlation handled inconsistently | **CONFIRMED and localised** → N21. Three distinct treatments in one `validate()` call: CPCV purges+embargoes, walk-forward has **zero** embargo, DSR's PSR uses plain `sqrt(n-1)` (`dsr.py:40`) with no Lo/serial-correlation adjustment. Block length hardcoded at 10 everywhere. |
| V12 | power gate's panel discount assumes cross-sectional correlation | not re-checked | — |
| V13 | White's RC on the legacy path, Hansen's SPA stronger | **CONFIRMED**: `hansen_spa` is reachable only from the dead gauntlet | N20 |
| V14 | event_study's two legs disagree on overlap | **moot** — the module is a total orphan | N12 |
| V15 | cost/capacity model has never met the desk's own fills | **CONFIRMED**, 3.32× BREAK, comparator inert | N19 |
| V16 | no gate consumes a ruin statistic | **CONFIRMED** | negative-space sweep |
| V17 | three inconsistent trials-ledger layers | **CONFIRMED and worse**: the ledger is consulted by nothing on the production path | N6 |
| V18 | `forward_slots.json` is a stale snapshot | **CHANGED**: current, but write-only — no reader exists | N18 |

---

## OPPORTUNITY COST OF NOT FIXING, ONE YEAR

The subsystem's output is *permission to deploy capital*. Its measured output over its lifetime is
**zero** — 0 survivors in 1,244 trials, `furthest_gate: 5` of 11, no forward clock ever completed.

- **Direct.** Under L1.30, terminal wealth is set by whether validated *births* keep pace with
  deaths. A screen that admits nobody produces a birth rate of exactly 0. A year of this is a year
  of guaranteed replacement-rate failure regardless of how good the research upstream is — and the
  desk cannot currently distinguish that from "the space is picked clean", because the instrument
  has never been calibrated (N1). That indistinguishability is itself the cost: it makes every
  strategic decision downstream — including a multi-month data-acquisition programme — a guess.
- **Indirect, and larger.** L1.8 orders mining and acquisition to run at maximum. With the screen
  bar scaling as `1/m` in generation volume (N3), **every additional candidate raises the bar
  against every other one.** Maximal generation and a FWER screen are directly contradictory
  policies; running both means the harder the desk hunts, the less can survive. One year of that
  is one year of the desk's central operating law working against itself.
- **Cheapest counterfactual.** Items #1 and #2 in the ranking are roughly one hour of compute and
  one file write. They do not loosen a single bar. They convert "we think the sample is the
  constraint" into a measured curve — and that curve is the input to every other decision here.

---

## PROACTIVE BATTERY (generative moves run, and what each produced)

- **(1) CONTINGENCY BEFORE FAILURE** — the campaign gate stack has one hard dependency,
  `_audit_prepared.pkl`, with 5 readers and **0 writers**, gitignored, frozen 6 days. If it is
  deleted, every gate diagnostic on this desk becomes unrunnable and unreproducible. No replacement
  path exists. *Produced: N9.*
- **(2) ADJACENCY** — took the `collapse_detector` false-green shape ("missing input → emit
  defaults → write to a live scoreboard") and looked for the same shape elsewhere. Found it in
  `variation_blocker.telemetry` (reads a ledger nothing writes), `rejection_shadow` (n=0 reported
  as a clean audit), `gate_calibration.rejection_shadow_audit` (runs on an empty list), and
  `min_passing_true_sharpe` (min of a 1-element set presented as a threshold). *Produced: N1, N14.*
- **(3) CONFIG VS OUTCOME** — demanded the artifact for every claimed capability rather than the
  schedule. Killed four "it's implemented" claims: the gate-power audit (no file), the validation
  report (no file ever), `run_onchain_history_backtest` (cron-scheduled, artifact never written),
  `run_autodiscovery` (cron-scheduled, outputs frozen 42 days). *Produced: N2, N20.*
- **(4) REGRESSION SWEEP** — what did the last 24h of commits make worse? Nothing statistically;
  but `787620a`/`dfa47dd` added two organs whose output file does not exist, so the desk's count of
  measured-and-floored metrics did not rise while its count of built organs did. Reported as N2.
- **(5) COST INVERSION** — every method this report recommends is already in the repo. No purchase,
  licence, or new data is required for any of items #1–#14. The frontier section names four methods
  and all four are free.
- **(6) GENERALISE THE RULE** — the screen/promotion multiplicity distinction (N3) is written as a
  law for the *backtest gauntlet* only. It applies identically to the axis screens, the litminer
  outputs, and every future screen-shaped organ. Written as a general principle in #3 rather than a
  patch to one file.
- **(7) AUTONOMY CHECK** — has any of this recovery been *seen* to work? No. No forward clock has
  ever completed (N18), the reject-recovery loop is vacuous until 2026-08-10 (N20), and the
  certification has never run its real grid. Every recovery path in this subsystem is configured,
  none is proven. *This is the honest summary of the subsystem's maturity.*
- **(8) NEGATIVE SPACE** — see the sweep above; largest item is that no gate has ever had a
  Type-I/Type-II curve measured, and no control has ever been run at a realistic effect size.
- **(9) SCOPE THE NEGATIVE RESULT** — applied to the desk's own "0 survivors": is that a failure of
  the *route* or of the *capability*? I tested three routes (longer window, BH, BY, plus
  family-scoping) and all four return 0, which looks like capability — **but the instrument is
  uncalibrated, so the inference is not available yet.** Recorded as the report's central open
  question rather than resolved in either direction. This is the L1.25 discipline: the 420/0 record
  was an instrument artifact once already.
- **(10) RATCHET CHECK** — is today's value a floor? No. Neither the gate-power numbers, the
  detection curve, nor the modelled/realised cost ratio has a floor artifact or a fence. Three
  metrics currently exist as prose or commit messages only. *Produced: N2, N19.*

**A move that produced nothing, reported as such:** I checked whether the recent commits had
introduced any statistical error (wrong formula, wrong direction, misapplied test). They had not —
`campaign_stats_fast`'s claim of verdict-equivalence is asserted against the full path across a
whole cohort rather than assumed, and the subset-scoring rationale (leave-one-out is blind to
redundancy) is correct method. The recent work's problem is entirely that its outputs are not
persisted, not that its reasoning is wrong.

---

## AUDIT SELF-NOTES (honesty)

- **One hypothesis of mine was refuted by my own test** and is recorded rather than dropped: the
  bootstrap-resolution artifact in N3. At B=10,000 the p-values are genuine. I was wrong, and the
  refutation is what produced the correct explanation.
- **The family-scoped BH result in N3 is a forking path**, run after seeing the pooled result. It
  is flagged in-line as a hypothesis to pre-register, not a finding. It should not be cited as
  evidence that family-scoping works — it is evidence that the *specific* existing 7-family
  partition does not.
- **I did not independently re-derive** the Stage-B measurements (N16–N18) or the cost/simulation
  measurements (N19); those came from parallel read-only sub-audits whose commands are quoted. I
  verified the load-bearing pieces myself (the certification artifact, the gate histogram, both
  gauntlets' reachability, the capacity arithmetic, the FDR result).
- **`min_track_record_length` being dead is worth one more line than it got:** it is the function
  that answers "how long must this run before we can tell", which is precisely the question the
  whole T-lever argument turns on. It has zero production callers.
- **The tree moved during the audit.** A sibling session modified `scripts/revalidate_clocks.py` at
  01:47 and added `scripts/check_enforcement_execution.py`, mid-sweep. The N13 update records this.
  Any reachability claim in this report is true as of **2026-08-01 ~01:50Z** and no later; the
  orphan census in particular was computed before 01:47 and `dist_shift` moved after it ran.
- **The regime/distributional seam returned after I first closed, and it overturned two of my own
  claims.** I had recorded (a) "no regime gate exists" — wrong: `regime_robust` exists, it is
  simply not wired into the scripts that validate the real sleeves (N24), which is a different and
  more interesting defect; and (b) I had rated the CPCV purge/embargo as correctly implemented
  under K4 — **wrong, and it is now N22, the single worst finding in the report.** K4 is retracted
  in place. I am leaving both corrections visible rather than silently rewriting, because the
  pattern that fooled me is the one the desk keeps getting caught by: I read the constructor call
  (`CPCV(purge=2, embargo=0.01)`) and the docstring, and did not check whether the consuming
  statistic reads the training fold. It does not. **Reading the wiring is not reading the outcome.**
- **Two of my hypotheses were refuted by test and are kept in place:** the bootstrap-resolution
  artifact (N3) and "DSR defaults the moments to normal" (N26b). Both were wrong; both produced the
  correct explanation only because they were tested rather than asserted.
- **What I could not check:** whether the 420 candidates are genuinely worthless. That requires E1
  and E4 and is the honest limit of this audit.

