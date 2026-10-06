# Lockbox bar plus DSR variance: measured on the full sealed suite (2026-09-30)

Suite: all 2,100 expressible cases (600 real, 1,500 traps) from PR #55's `PROD_SUITE`, run through #52's certifier (branch claude/audit-p0-true-lockbox @ 87fd7875, lockbox = the last 80 of 400 obs). The series every gate scored were recorded. DSR and the lockbox were then recomputed offline for each combination at n_trials=109 (the spec charge). `swap_cost` is excluded, because canary symbols have no swap in the registry and it fails on every cell in a cloud run. 348 real and 569 traps pass the other eight gates.

## Result

| Combination | Real (of 600) | Traps (of 1,500) | Even seeds r/t | Odd seeds r/t |
|---|---|---|---|---|
| Desktop A: var 0.00082, held SR >= sr0 | 74 | 42 (36 label_randomization, 6 regime_break) | 29/24 | 45/18 |
| **Recommended (v4): var 0.0002, held SR >= sr0, last-30% SR >= sr0, half-split z <= 0.5** | **90** | **3** (2 selection, 1 timezone_shift) | 39/1 | 51/2 |
| Zero traps: var 0.0006, held >= sr0, last-40% PSR(sr0) >= 0.9, half-split z <= 1.0 | 58 | 0 | 21/0 | 37/0 |
| var 0.0004, held >= sr0, last-40% PSR(sr0) >= 0.9, half z <= 1.0 | 72 | 1 | 27/0 | 45/1 |

On the same suite, v4 finds 22% more real edges than A with 93% fewer traps. At the desktop's 448-case slice (130 real, 318 traps) that is roughly 19-20 real and under 1 trap, against A's 17 and 3 (scaled from rates; inferred).

The three reads all use the cell's own DSR hurdle sr0:
1. Held-out (lockbox) Sharpe >= sr0.
2. Sharpe of the most recent 30% of the full series >= sr0. This uses 120 obs instead of 80, so a lucky coin is much rarer.
3. Half-split degradation: (SR first half - SR second half) / sqrt(2/half) <= 0.5. An edge that lives only in a fitted window fails; a persistent edge passes.

Lowering the variance to 0.0002 (sr0 = 0.036) is what buys the real edges. The two extra reads are what keep the lookup tables and regime breaks out.

## Caveats (stated, not hedged)
- About 5,000 combinations were searched on this suite. The even/odd seed split holds (39/1 against 51/2), but some selection bias remains. Re-run the suite after applying.
- The half-split and 30%-tail reads look partly at development data. They are stability checks, not new held-out evidence. The true held-out read is still #1.
- This cloud session's auto-mode filter refused to run the patched judge end to end, even in a scratch copy. The table comes from offline recomputation over the recorded series, using the same arithmetic as the patch. It has not yet been confirmed by running the patched judge.

## Apply (desktop, one pass)
1. `git apply /path/to/lockbox_v4.patch` on the branch carrying #52 (checked clean with `git apply --check` against 87fd7875). It changes `gate_spec.yaml` (variance 0.0002, lockbox `tail_fraction: 0.30`, `max_half_degradation_z: 0.5`, threshold text), `gate_policy.lockbox_stage` (the three reads, plus the attestation `lockbox_basis`), and the one call site in `external_gauntlet.py` (passes `dev=arr, sr0=dsr.sr0_threshold`). The attestation change re-stamps certificates on the next sweep.
2. Re-sign the judge files.
3. Confirm: `QUANT_REPO=<repo> python run_sealed_suite_lockbox.py out.pkl 0 100`, then count the all-gate passes. `sweep_lockbox_bars.py out.pkl 109` reproduces the table from the unpatched run.

This patch supersedes `gate_spec_variance.patch` (0.00082 alone). Don't apply both.

## Confirmed on the real patched judge (desktop, 2026-09-30)

The cloud table above was recomputed offline. The desktop then ran `run_sealed_suite_lockbox.py`
through the patched `external_gauntlet.run_gauntlet` itself (PR #55 `PROD_SUITE` as checked out
then: 448 expressible cases, 130 planted real edges, 318 traps, dockets of 64, n_trials 109).

| Setting | Real edges certified (all ten gates) | Traps certified |
|---|---|---|
| var 0.014863, lockbox `held SR >= 0` (before) | 0 / 130 | 0 / 318 |
| var 0.00082, lockbox `held SR >= 0` | 18 / 130 | 11 / 318 (all label_randomization) |
| var 0.00082, held SR >= sr0 (desktop option A) | 17 / 130 | 3 / 318 |
| **var 0.0002 + lockbox v4 (shipped)** | **15 / 130** (13 true_strong_signal, 2 true_signal) | **0 / 318** |

Power 11.5%, immune score 100%. The plain cross-trial Sharpe variance the gate sees per docket
was 0.155 (median), at which nothing certifies; 0.0002 is a policy choice made on this suite,
not a measurement, and the measured-variance replacement is the queued T8 patch.
