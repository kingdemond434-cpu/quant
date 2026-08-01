# Statistical audit of the validation gauntlet — Type I, Type II, and what actually binds

**Date:** 2026-08-01 · **Artifacts:** `reports/gate_power_audit.json`, `reports/gate_subset_audit.json`,
`reports/gate_fattail_check.json`, `reports/gate_topk_study.json`, `reports/gate_power_after_fix.json`
· **Harness:** `scripts/audit_gate_power.py` · **Reader:** `scripts/report_gate_audit.py`

## Verdict

**The gauntlet was over-conservative by a wide and measurable margin, and the cause was a
duplicated multiplicity correction rather than a badly-chosen threshold.**

Every candidate was scored through the real `validate()` with real campaign statistics — not a
reimplementation, which would have certified a model of the gauntlet rather than the gauntlet.
Cohorts were simulated with a known number of genuine alphas, so both error types are observed
rather than inferred.

## 1. The power curve (N=420, T=310, 240 genuine alphas and ~4,800 nulls per point)

| true annualised Sharpe | power BEFORE | power AFTER | Type I before | Type I after |
|---|---|---|---|---|
| 0.0 (null) | — | — | 0.000% | 0.020% |
| 1.5 | 0.0% | 1.67% | 0.000% | 0.021% |
| 2.0 | 0.0% | 5.83% | 0.000% | 0.021% |
| 3.0 | 1.2% | 23.75% | 0.000% | 0.021% |
| 5.0 | 12.1% | **85.42%** | 0.000% | 0.021% |
| 7.0 | 40.4% | **100.00%** | 0.000% | 0.021% |
| 10.0 | 80.4% | — | 0.000% | — |

95% Wilson intervals on the after column: 1.5 → [0.6, 4.2], 2.0 → [3.5, 9.6], 3.0 → [18.8, 29.5],
5.0 → [80.4, 89.3], 7.0 → [98.4, 100.0]. On the false-positive side, before is 0 of 5,040 (upper
bound 0.10%) and after is 1 of 5,040 (upper bound 0.11%) — intervals that overlap almost entirely.

The gauntlet previously rejected 60% of candidates whose true Sharpe was **7**. That is not a
conservative gate; it is a gate that had stopped measuring the candidate and was measuring its own
correction stack.

A world-class systematic book runs a true Sharpe of 2–3. The gauntlet admitted **0%** of those.
The false-positive rate moved from 0 of 5,040 to 1 of 5,040 — 95% intervals that almost entirely
overlap.

## 2. Why: the multiplicity penalty was paid twice

DSR is a Probabilistic Sharpe Ratio against a **deflated** benchmark
`sr0 = expected_max_sharpe(n_trials, ...)`. That deflation *is* a multiplicity correction over the
campaign. On the per-candidate path Romano-Wolf **already** controls family-wise error over the
same N candidates. Two family-wise bars were being compounded into one nothing could pass.

Gate subsets at true Sharpe 5.0 (`reports/gate_subset_audit.json`):

| gates kept | power | false positives |
|---|---|---|
| all gates | 5.8% | 0.000% |
| **without DSR** | **83.8%** | **0.000%** |
| without reality_check | 5.8% | 0.000% |
| without DSR *and* reality_check | 100.0% | **32.3%** |
| without all three multiplicity gates | 100.0% | 32.5% |

Romano-Wolf alone holds the false-positive rate at zero while power rises 14×. Removing **both**
sends false positives to 32%, which is why exactly one correction is kept and not zero.

Leave-one-out alone could not have found this: `without_reality_check` reads 0.0pp because DSR
masks it. Redundancy is only visible when the pair is removed together.

## 3. Calibration — correctly sized, wrongly targeted

The corrections are **not** miscalibrated. Measured at N=100, T=310, 60 reps:

| test | rejection rate under the global null | nominal |
|---|---|---|
| White's Reality Check | 3.3% | 5% |
| Hansen SPA | 5.0% | 5% |
| Romano-Wolf (any rejection) | 5.0% | 5% |

All correctly sized as **family-wise** tests. The over-conservatism is not a calibration defect —
it is that family-wise error was controlled twice over the same family.

Discrimination is excellent throughout, which is why the loss was recoverable:

| true SR | AUC(DSR) | AUC(reality p) | AUC(PBO) | AUC(OOS Sharpe) |
|---|---|---|---|---|
| 1.0 | 0.775 | 0.611 | 0.772 | 0.742 |
| 2.0 | 0.919 | 0.788 | 0.915 | 0.882 |
| 3.0 | 0.980 | 0.925 | 0.977 | 0.956 |
| 5.0 | 1.000 | 1.000 | 0.998 | 0.997 |

AUC 0.98 at 1.2% power is the signature of a good statistic behind a threshold placed out of
reach — not of an uninformative test.

## 4. The adversarial check that could have overturned this

PSR adjusts for skew and kurtosis; Romano-Wolf's mean-based bootstrap does not. So the honest
argument for keeping DSR's deflation is that it catches negatively-skewed nulls. Tested on three
**true nulls** (zero population mean), 2,000 candidates each:

| null shape | skew | kurtosis | realised SR | FPR all gates | FPR without DSR |
|---|---|---|---|---|---|
| gaussian | -0.00 | 2.98 | -0.02 | 0.000% | 0.050% |
| student-t(4) | -0.01 | 9.21 | -0.01 | 0.000% | 0.000% |
| short-vol | **-6.15** | **45.59** | +0.22 | **0.150%** | **0.150%** |

On the short-vol payoff — precisely the shape the moment adjustment exists to catch — DSR gives
**identical** protection to no DSR. The argument does not survive contact with measurement.

*Secondary finding:* 0.15% of short-vol nulls clear the whole stack including `fragility`. The
desk has no effective tail-shape veto on the money path. Small, but real, and unaddressed here.

## 4b. Effective number of independent tests — and why Romano-Wolf was the right survivor

Every multiplicity correction here is handed the RAW candidate count. 420 variants over one
universe in one era are not 420 independent tests. Measured at true SR 3.0, N=420, T=310:

| ρ | power | FPR | N_eff (participation) | independent baseline | ratio |
|---|---|---|---|---|---|
| 0.0 | 1.25% | 0.000% | 178.2 | 178.0 | **1.00** |
| 0.3 | 2.08% | 0.000% | 11.0 | 178.0 | 0.06 |
| 0.6 | 8.75% | 0.000% | 2.8 | 178.0 | 0.02 |
| 0.9 | 17.92% | 0.000% | 1.2 | 178.0 | 0.01 |

The ρ=0 row reads **exactly 1.00** against its own baseline, which is the guard working: the
raw figure of ~178 at T<N is an estimation artifact, and only the ratio is a finding. At a
merely moderate ρ=0.3 the 420-candidate cohort is worth about **11 independent tests**.

This is the sharpest justification for which correction to keep, and it is stronger than the
argument originally made for the fix:

* **Romano-Wolf ADAPTS.** Its stationary-block bootstrap resamples the cohort jointly, so the
  dependence structure is preserved and the correction shrinks toward the effective count. Power
  *rises* with ρ (1.25% → 17.92%) precisely because of this.
* **DSR's deflation does NOT.** `expected_max_sharpe(n_trials)` takes the raw integer 420 and has
  no channel through which correlation could reach it.

So on a realistically correlated campaign DSR was deflating for ~420 tests where roughly ~11
existed — over-correcting by more than an order of magnitude — while Romano-Wolf was already
sized correctly. Keeping the adaptive correction and dropping the fixed one is not a preference;
it is the only choice consistent with this table.

## 5. What actually binds — the bottleneck

| knob | power at true SR 2.0 |
|---|---|
| **history length** T=310 → 620 → 1250 → 2500 | 0.00% → 1.67% → 4.58% → **19.58%** |
| **campaign size** N=420 → 100 → 30 | 0.00% → 0.00% → **0.00%** |

**History length is the bottleneck. Campaign size is not.** Cutting the campaign from 420
candidates to 30 buys *nothing* at realistic effect sizes — the hurdle falls from 5.04 to 4.04,
still far above any real strategy. This corrects an earlier analytic framing that presented both
as levers.

And the desk is discarding the resource that matters:

```
obs retained   130,200  =   310 per candidate (the MINIMUM length)
obs available  759,444  =  1808 per candidate on average
-> 82.9% of the observations already in hand are thrown away by min-length truncation
```

## 6. The screen is an absolute threshold where it should be a ranker

The backtest gauntlet is a SCREEN feeding `MAX_FORWARD_SLOTS=12`. Ranking candidates by DSR and
taking the top 12 (`reports/gate_topk_study.json`):

| true SR | genuine alphas in top-12 (of 20) | precision | current gauntlet promotes |
|---|---|---|---|
| 1.5 | 4.4 | 37% | 0.00 |
| 2.0 | 6.1 | 51% | 0.00 |
| 3.0 | 10.2 | 85% | 0.00 |

An absolute threshold that admits nobody leaves the forward stage — the desk's actual instrument
of promotion — permanently starved. **Not implemented here**; recorded as the next-largest lever.

## 7. Portfolio construction versus per-candidate gating

The gate scores each leg alone against a bar only an assembled portfolio could clear.

| legs | each leg true SR | portfolio SR | P(one leg clears) | P(all clear) |
|---|---|---|---|---|
| 5 | 1.0 | 2.24 | 0.01% | 9e-21 |
| 8 | 1.0 | 2.83 | 0.01% | 8e-33 |
| 5 | 2.0 | 4.47 | 0.25% | 1e-13 |

## 8. Change made

One line, in `libs/autodiscovery/validation.py`: on the per-candidate path DSR is computed with
`n_trials=1`, so the duplicated deflation is removed and the **moment-aware PSR is retained**. The
legacy path keeps the full deflation because nothing else corrects for multiplicity there.

Nothing else was touched. No threshold was lowered. `_DSR_THRESHOLD` is still 0.95, Romano-Wolf
still controls FWER at 5%, and every economic gate is unchanged. Pinned by
`tests/validation/test_dsr_single_correction.py`.

## 9. Not done / open

- Effective-number-of-tests ratio under real correlation (study running; the estimator's floor at
  T<N is an artifact and only the ratio to an independent baseline is interpretable).
- Regime-shift and fat-tail power conditions (`realism` study).
- Top-K ranked screen (§6) and the min-length truncation (§5) — both larger than a one-line change
  and both worth more than the change made here.
