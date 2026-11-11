# Preregistration: does a mechanism weaken after a world-state change? (DECAY-11)

Registered 2026-11-11, before any data is examined. Mandate 2026-10-06, Growth allocator overhaul, DECAY-11:

> "Preregister tests of whether mechanisms weaken after world-state changes; world change updates forecasts, not automatic breakage; same-event indicators not counted as independent."

## Question

Does a sleeve's mechanism lose expectancy after a change in the desk's own world state? The desk has two measures of world state:

- the HMM regime (`pf_allocator.regime_state`)
- the macro kernel dimensions (`macro_state`: dollar, risk/VIX, rates)

## Unit and sample

- **One mechanism** is one `SleeveEvidence.mechanism` family. Sleeves of one mechanism are pooled, never counted as independent.
- **One world-state change** is a day on which the MAP HMM regime changes, or on which a macro kernel dimension moves tercile (`macro_state.bucket`).
- Changes within 5 trading days of each other are **one event**. This is the same-event rule.
- A VIX tercile move and an HMM switch inside the same 5-day window are also one event, not two.
- The sample is every event since the start of the desk's daily matrix (`pf_allocator.build_evidence`).
- Only rows dated before the analysis run are used.

## Test (fixed now)

For each mechanism *m* and each event *e*, compute:

- **pre** = the mechanism's mean daily R over the 40 trading days before *e*
- **post** = the mean over the 40 trading days after *e*
- **d(m, e)** = post − pre

The test runs per mechanism:

- **Statistic:** a one-sided sign-flip permutation test of mean d(m, ·) < 0, with 10,000 permutations.
- **Requirement:** at least 8 events.
- **Error control:** Benjamini-Hochberg across mechanisms at q = 0.10.
- **Placebo:** the same statistic on 200 sets of random non-event days, matched in count. The real statistic must sit below the placebo's 5th percentile.

## What a result does

**A mechanism that passes (rejects).** Its forecast is updated, not broken. In practice, this means a regime-conditioned expectancy is fed to the allocator through the existing regime pools in `robust_elog.sample_worlds`. No automatic retirement may follow from this test alone.

**A mechanism that fails to reject.** Nothing changes. Absence of evidence is not evidence of robustness: the result is published as UNPROVEN, never as STABLE.

## What may not change after registration

None of the following may be changed after registration without a new, dated preregistration:

- the 40-day windows
- the 5-day same-event rule
- the 8-event minimum
- q = 0.10
- the placebo design

## Where it will run

This will run as a report-only leg reading `reports/HEALTH_LAB.json`'s sibling `reports/DECAY_WORLD_STATE.json`. It is to be built after the forecast ledger (ALLOC-28 / DECAY-05) lands, so that each event's pre-change forecast is the one actually published at the time.
