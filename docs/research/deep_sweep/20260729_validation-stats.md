# WEEKLY DEEP COLD AUDIT — validation-stats — 2026-07-29

_Retry of failed run (prior attempt died BRAIN_AUTH_FAILED at 493 bytes). This run is live._

**Subsystem scope:** selection bias, multiple testing, parameter sensitivity, sample dependence,
walk-forward + CV methodology, regime robustness, distributional assumptions, uncertainty
propagation, capacity/cost modeling, simulation realism, MC design, bootstrap quality,
structural breaks. Prime quarry: zero-information gates (accept/reject ~100%), rigorous
methods sitting as dead code, DSR bar optimality.

## SCORES (filled at end of audit)

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

## 1. WHAT WE KNOW (validated strengths, each with proving command)

**S1. The statistical primitive library is genuinely institutional-grade — implementations are
correct, not cargo-culted.** Read in full this sweep: `libs/validation/dsr.py` (Bailey–López de
Prado PSR/DSR with skew/kurtosis adjustment and expected-max-Sharpe deflation), `pbo.py` (true
CSCV PBO over C(16,8) splits with logit ranks), `reality_check.py` (White's RC **and** Hansen's
SPA with studentization + consistent recentering, both on stationary bootstrap), `bootstrap.py`
(moving-block + stationary bootstrap — correctly refuses IID resampling of returns), `cpcv.py`
(combinatorial purged CV with purge + embargo), `forward_stats.py` (Newey–West/Bartlett
effective-N t-stat clamped to [1,5], Holm step-down bar with pre-registered-primary exemption).
No hand-rolled significance anywhere in these files. Proof: `Read` of each file (this sweep);
e.g. `hansen_spa` implements the Hansen-2005 recentring threshold `-sqrt((ω²/T)·2loglog T)`.

**S2. The Stage-A axis-screen harness is the best single artifact in the subsystem — it encodes
five separately-dated statistical injuries as baked-in rails.** `libs/research/axis_screen.py`:
angle-20 de-contamination gate (killed coinbase/turkey premium artifacts), SUSPECT-LOOKAHEAD
ceiling (killed the bithumb IC-0.72 fake), horizon-correct annualisation (fixed 2026-07-26:
sqrt(365/horizon) — noise scored Sharpe 0.55 at 20d before), panel-width effective-N division
(139-symbol panel: apparent t=3.5 was really t=0.35), and power gating BOTH branches
(SCREEN-UNDERPOWERED can neither kill nor start a clock — fixed after a cell 18x below its own
detection floor was labelled INTERESTING). A forward clock starts ONLY on a powered
SCREEN-INTERESTING. This is what the constitution's screen-on-discovery duty points at, and it
deserves the trust.

**S3. Stage-B forward multiplicity is real and currently honest.** `web/axis_shadows.json`
(updated 2026-07-29T08:46Z): 4 axis clocks ACCRUING, each carrying `nw_t` (autocorrelation-
corrected), `holm_bar: 2.24` at `m_concurrent: 4`, `min_forward_days: 40`, and the legend
"ELIGIBLE means the evidence bar is met … NOT an automatic deployment". The slot guard was
blind to axis clocks until yesterday (commit 7bc1f7b fixed it to count all three slot sources
and fire on the under side too). `nw_tstat`/`holm_bar` are consumed by `run_axis_shadows.py:120`
and `run_shadow_8h.py` — the promotion path uses the corrected statistic, not naive Sharpe.

**S4. Yesterday's campaign-constant discovery (commit 7bc1f7b) is the single most important
validation fact of the quarter, and the desk found it itself.** PBO and White's RC take only the
returns *matrix* — never the candidate's own column — so used per-candidate they are campaign
constants: measured PBO 0.6159 / RC p 0.4220 on the real 420-matrix vetoed all 420 at any
quality, and the synthetic experiment showed one true SR=3 winner in a batch flips 60/60 pure-
noise candidates to PASS under the old gates. Both too strict AND unboundedly loose, decided by
the batch. The fix (`libs/validation/stepwise.py`: per-candidate CSCV rank consistency +
Romano–Wolf stepdown, FWER 5% across all N, thresholds unchanged) is built and tested (13 tests
incl. phantom-edge and winner-vs-noise discrimination). Proof: `git show 7bc1f7b`;
`libs/autodiscovery/validation.py:41-103`.

**S5. Negative results are being banked.** `data/sor_research.sqlite::research_memory` = 143
rows (93 construction-failures, 26 hypothesis-failures logged with causes; last entry
2026-07-29T11:11Z — the kimchi IC +0.2249 ~73%-timestamp-artifact retraction). The graveyard
discipline is operating, not aspirational. Proof:
`sqlite SELECT category,result,COUNT(*) FROM research_memory GROUP BY 1,2`.

**S6. Anytime-valid inference exists AND is wired where it matters most.** `libs/research/
anytime_valid.py` is imported by `run_shadow_8h.py` and `run_derivative_shadow.py` — the shadow
clocks that are peeked at daily use always-valid bounds rather than fixed-n tests. Proof:
`grep -rln "research.anytime_valid" scripts` → 2 live shadow runners.

## FINDINGS (each with proving command; feeds outputs 2–4)

**F1 — THE PER-GATE ACCEPT/REJECT HISTOGRAM THE GATE-OPTIMALITY DUTY MANDATES DOES NOT EXIST;
computed fresh this sweep, it shows 4 of 9 production gates carry ZERO information.** Over all
57 stored candidates (`data/sor_autodiscovery.sqlite::research_candidates`, campaigns
camp_f3676… n=51 and camp_aebbdf… n=6):

```
economic_mechanism   fail   0/57   (0%)   <- checkbox: bool(hypothesis.failure_modes)
expected_value       fail  44/57  (77%)
cpcv                 fail  47/57  (82%)
walk_forward         fail  47/57  (82%)
dsr                  fail  57/57 (100%)   <- stored dsr value is 0.0000 for every row
pbo                  fail   0/57   (0%)   <- campaign constant, loose side here
reality_check        fail  57/57 (100%)   <- campaign constant, strict side (p=0.095/0.403)
capacity             fail  53/57  (93%)   <- median capacity_usd = 0 (duplicates EV sign)
fragility            fail  39/57  (68%)
```

Command: read-only sqlite scan of `research_candidates` parsing `rejection_reason` tokens +
`dsr/pbo/reality_p/capacity_usd` distributions (dsr: min=med=max=0.0000; reality_p: 0.095/0.403
constants per campaign; pbo: ≤0.1724 all rows). The constitution's gate-optimality duty says
"audit … the per-gate accept/reject histogram every cycle" — no script produces this artifact
(`grep -rln "gate_histogram|per_gate" scripts libs` → only validation.py itself). This took ~30
lines of read-only SQL; it has simply never been run as an organ.

**F2 — THE HASH-CHAINED TRIALS LEDGER HAS ZERO ROWS IN ALL 10 DATABASES; the DSR "n_trials" in
production is each script's local batch size, so desk-cumulative multiplicity is never paid.**
`libs/store/trials.py` docstring: "Nothing is validated without a ledger entry first." Reality:
`trials_ledger rows: 0` in alpha_registry, sor_autodiscovery, sor_crypto, sor_live_demo,
sor_research, sor_research_lake(+v2), sor_smoke (command: python sqlite scan over
`data/*.sqlite`). The only writer is `Gauntlet._resolve_n_trials` (`libs/validation/
gauntlet.py:89-102`) and `Gauntlet(` is constructed **only in tests** (`grep -rn "Gauntlet(" `
→ tests/validation/test_gauntlet.py only). Production `validate()` callers pass
`n_trials=len(lib)` / `len(series)` (e.g. `scripts/run_discovery.py:156`,
`run_xsec_funding_max.py:80`) — the local matrix width. ~25 run_* scripts each deflate by their
own batch only; the 420-trials campaign, the 57 stored candidates, and every axis screen are
mutually invisible multiplicity. Mitigation that keeps this from being fatal: the two-stage law
(backtest = screen with zero promotion authority; promotion pays only Holm-corrected forward
slots). But every report that prints "trials-adjusted DSR" is claiming a deflation the desk does
not perform, and the 7x safety multiplier (`trials_multiplier=7.0`) exists only in dead code.

**F3 — THE REJECTION-SHADOW AUDIT (the empirical gate-leak detector) HAS BEEN INERT SINCE
BUILT: 57/57 rejects pending, forward evaluator never wired.** `web/reject_shadow.json`
(2026-07-29T08:46Z): "57 eligible rejects, NONE re-scored yet -- the forward evaluator has not
produced scores; the audit cannot judge the gate until it does." Its input
`data/reject_forward_scores.json` does not exist (`ls` → No such file). So the desk's only
empirical instrument for "is the bar killing real alphas" (constitution: "a good alpha lost to
an accidentally-too-high bar is as costly as a false one admitted") has produced zero verdicts.
The runner honestly reports the blockage — but honesty about a dead organ does not substitute
for the organ. This is the highest-leverage 1-day build in the subsystem: score each reject's
frozen rule on post-rejection data (the returns pipelines already exist in the run_* scripts)
and the leak fraction becomes a measured number instead of a faith position.

**F4 — THE CANDIDATE-ATTRIBUTED GATES (stepwise.py) ARE BUILT, TESTED, AND DORMANT — no
production caller passes `campaign=`.** `grep -rn "campaign=" libs scripts app` → only
`libs/ops/research_daemon.py` (an unrelated kwarg). All ~22 run_* scripts still import and use
the legacy `campaign_pbo_rc` + `validate(...)` path (grep listing in this sweep). This is
deliberate — rail-revision protocol reserves gate-strictness changes to the principal, and the
YES/NO was handed over yesterday — but note what it means TODAY: every campaign the desk runs
until the ruling still applies two zero-information gates, and any batch that contains one real
edge admits its noise cohort (the measured 60/60 flip). The blocking item is a decision, not
engineering. If the ruling is YES, the flip is ~22 one-line call-site edits behind a
byte-identical-legacy test.

**F5 — RIGOROUS METHODS SITTING AS DEAD CODE (the audit's explicit quarry), verified by
importer scan:** `grep -rln` for each module, excluding tests/its own package:
- `libs/validation/cpcv.py` (real purged/embargoed CPCV) — **0 importers**. Production's "cpcv"
  gate is `_cpcv_positive_fraction` (`autodiscovery/validation.py:35-38`): plain
  `np.array_split` k-fold sign check, **no purge, no embargo, no combinatorial splits**, on the
  candidate's own returns. The gate name oversells the method; the real method is unused.
- `libs/validation/lockbox.py` (holdout registry) — **0 importers**. No terminal never-touched
  holdout exists anywhere in the promotion path.
- `libs/validation/fdr.py` (Benjamini–Hochberg) — **0 importers**.
- `libs/validation/baselines.py` — **0 importers**.
- `libs/research/stationarity.py` (ADF/structural-break tooling) — **0 importers**. Regime/
  break detection in validation is therefore: `RevalidationController.assess(structural_break=
  False, drift=False, …)` — flags that no caller computes (see F6).
- `libs/validation/gauntlet.py` `Gauntlet` (7-stage orchestrator with trials ledger, Hansen
  SPA, stress costs ×3, lockbox stage) — **constructed only in tests**. Production uses the
  flatter `autodiscovery/validate()` which swapped Hansen SPA for the weaker White RC and
  dropped the stress-cost and lockbox stages entirely.
- `libs/validation/reject_rescore.py` `plan_rescore` — wired to `run_rejection_rescore.py` but
  starved by the same missing forward scores as F3 (57 pending_rescore).

**F6 — THE REVALIDATION TRIGGER SYSTEM IS A SWITCHBOARD WITH NO WIRES.** `libs/validation/
revalidation.py` defines STRUCTURAL_BREAK / DRIFT / REGIME_TRANSITION / SIGNAL_DEAD hard
triggers that gate production capital — but the booleans are caller-supplied and `grep -rn
"structural_break=" libs scripts app` finds no caller passing anything but defaults (the only
non-test caller path is `autodiscovery/validation.py:128` which calls `.evaluate()` directly and
never constructs `RevalidationController`). No organ computes a structural-break statistic
(stationarity.py: 0 importers), so the fail-closed design has nothing to close on. The walk-
forward inside it is also mislabeled: `WalkForwardEngine.evaluate` computes OOS Sharpe on
test windows of a fixed returns series — nothing is refit (no parameters exist at that call
site), so "walk_forward" ≡ "sign consistency on later sub-windows" ≡ the same information as
the fake-cpcv gate. Two of nine gates are near-duplicates; the histogram confirms (both 82%).

**F7 — CAPACITY GATE: `adv_usd` DEFAULTS TO $100B AND NO CALLER OVERRIDES IT.**
`autodiscovery/validation.py:113` `adv_usd: float = 1.0e11`; `grep -rn "adv_usd" scripts libs`
→ no run_* script passes it. The gate only ever binds through the candidate's own mean return
(capacity_usd=0 when mean≤0 — hence 93% fail ≈ duplicate of expected_value). For any
positive-edge candidate the $100B ADV makes capacity effectively unbounded — the gate would
accept ~100% of survivors, i.e. zero information in exactly the state (real edges) where
capacity is supposed to bite. Real per-venue ADV numbers exist in the data lake
(`data/crypto_trades.sqlite`, collector outputs) and are simply not plumbed.

## 2. WHAT WE DON'T KNOW (ignorance ledger)

_(filling incrementally)_

## 3. WHAT COULD MATTER MOST (ranked opportunities)

_(filling incrementally)_

## 4. WHAT WE TEST NEXT (concrete experiments)

_(filling incrementally)_

## PERSPECTIVE COVERAGE CHECKLIST

- [ ] INTERNAL
- [ ] EXTERNAL
- [ ] FUTURE
- [ ] CONTRARIAN
- [ ] GREENFIELD
- [ ] FRONTIER
- [ ] NEGATIVE-SPACE SWEEP
