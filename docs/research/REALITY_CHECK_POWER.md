# Why nothing survives `reality_check` — measured, 2026-08-01

`scripts/audit_reality_check.py` → `reports/reality_check_audit.json`

## The question

After the double-multiplicity fix, the real campaign's per-gate death counts were:

```
reality_check   196/196      cpcv            81
dsr             147          fragility       72
walk_forward     99          capacity        69
pbo              91          expected_value  64
```

Every gate discriminates except one. A gate rejecting 100% has no discriminating power, and that
has two possible causes demanding opposite responses: either the mechanisms genuinely fail
family-wise error control (a real result to accept), or the bar sits where nothing realistic can
reach it (the gate is measuring the campaign's design, not its edge).

## The answer: the gate is CORRECT and the campaign design is the defect

**False-positive rate is ~0 everywhere** — 0/3,900 true nulls at N=196, 1/980 at N=50, 4/380 at
N=20, 1/80 at N=5, against α=0.05. Romano-Wolf is doing exactly its job. Nothing here justifies
touching alpha, and nothing here is a licence to.

**But its power inside the desk's real-edge band is close to zero.** The band is 0.5–1.5
annualised Sharpe (external 131,441-backtest sweep). Measured power, 20 trials per cell,
T = 2,018 bars:

| true ann. Sharpe | N=196 | N=50 | N=20 | N=5 |
|---|---|---|---|---|
| 0.5 | **0%** | 10% | 10% | 15% |
| 1.0 | **5%** | 40% | 50% | 60% |
| 1.5 | **30%** | 80% | 90% | 95% |
| 2.0 | 95% | 100% | 100% | 95% |
| 3.0 | 100% | 100% | 100% | 100% |

At the campaign's actual N=196, a strategy with a **true** annualised Sharpe of 1.0 is detected
5% of the time. The gate is not rejecting the desk's candidates because they are bad. It is
rejecting them because it cannot see edge of that size at that N on that much data.

## The correction that mattered most: bar count is not evidence

The obvious response is higher-frequency bars — 4h instead of daily, six times the observations.
**It does nothing**, and this is worth stating plainly because it is the intuitive answer and it
is wrong:

```
t = sqrt(T) · SR_per_bar ,  SR_per_bar = SR_ann / sqrt(PPY)
  ⇒ t = SR_ann · sqrt(T / PPY) = SR_ann · sqrt(YEARS)
```

Moving to 4h bars multiplies both `T` and `PPY` by six and leaves the statistic unchanged.
Elapsed time is the evidence; bar count is not. OKX holds 6.7 years at most, so this lever is
nearly exhausted.

Closed-form minimum detectable annualised Sharpe at T=2,018 (5.53 years):

| N | 196 | 50 | 20 | 5 | 1 |
|---|---|---|---|---|---|
| min detectable SR | 1.48 | 1.31 | 1.19 | 0.99 | **0.70** |

Even at **N=1** — one candidate, no multiplicity whatsoever — the floor is 0.70. So multiplicity
is not the dominant term either. Cutting the candidate count alone cannot rescue this.

## What does work: pool by mechanism, not by symbol

The campaign tests `time_series_mom[40]` on BTC, on ETH, on SOL … as **ten separate hypotheses**.
That both inflates the multiplicity burden and discards the fact that all ten are evidence about
the *same claim*. Testing the mechanism once, against the equal-weight average of its per-symbol
returns, does two things at once.

The gain depends entirely on the cross-symbol correlation of the **strategy** returns, so it was
measured rather than assumed:

- raw cross-symbol daily return correlation: **0.622**
- same-mechanism cross-symbol *strategy* return correlation: **0.348** ← the one that governs pooling

At ρ=0.348 over 10 symbols the effective observation count rises by `10/(1+9·0.348)` = **2.42×**,
a **1.56×** gain on the t-statistic, while N falls from 196 to ~20.

| true ann. Sharpe | per-symbol, N=196 | pooled by mechanism, N=20 |
|---|---|---|
| 0.50 | 0% | 15% |
| 0.75 | — | 20% |
| 1.00 | **5%** | **70%** |
| 1.50 | 30% | **100%** |
| min detectable SR | **1.48** | **0.77** |

**Power at a true Sharpe of 1.0 goes from 5% to 70%,** and the detection floor moves from above
the entire real-edge band to inside it — with α untouched, the gate untouched, and no threshold
moved anywhere. It is not a loosening; it is asking the right question. "Does this mechanism work
on crypto" is one hypothesis with ten symbols of evidence, not ten hypotheses with one each.

## What this does NOT say

- **Not that the desk has edge.** It says the current design could not detect edge of the
  plausible size even if it were there. Whether it is there is still open.
- **Not that any gate should move.** The false-positive rate is clean; α stays at 0.05.
- **Not that pooling is free.** A mechanism that works on two symbols and fails on eight will be
  diluted by the average and correctly rejected — that is the intended behaviour, but it means
  pooling tests a strictly stronger claim than any per-symbol test does.
- **Not measured on real returns.** The power curves are synthetic panels matched to the real
  cohort's T, N and correlation; the 0.348 cross-symbol figure is real. A pooled run on live data
  is the next step, not a completed one.

## Next

Add a pooled-by-mechanism path to `run_real_campaign` alongside the per-symbol one, and report
both. The per-symbol view keeps its diagnostic value; the pooled view is the one that can actually
certify a survivor.
