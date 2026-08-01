# CAPABILITY HUNT PROPOSALS 20260801 slot 3

LENS: REGIME-CONDITIONED EDGE -- an edge that exists only in a nameable, DETECTABLE regime (high-funding, high-vol, post-liquidation, low-liquidity) we could switch on and off. What regime do we not yet detect, and what edge would it gate?

## A -- Claude family

The regime map came back. It **confirms the deep proposal's novelty** — no per-clock accrual measurement exists anywhere, and it found no CUSUM, no changepoint library, no structural-break test, and no `data/crypto_regime_history.jsonl` in the repo.

One dependency it revealed that I should state honestly: the regime label is **overwritten in place nightly**, so the label series does not exist (R0006, flagged in five consecutive sweeps). My MONOCLIMATE branch therefore cannot be built on the HMM path — but `crypto_regime.regime_labels()` recomputes labels from price history on the fly, so the census is buildable today on that path without waiting for R0006.

It also surfaced a finding that competes with mine on quality, and I'd rather name it than bury it:

**`libs/validation/revalidation.py:133-135` defines `RevalidationTrigger.{STRUCTURAL_BREAK, DRIFT, REGIME_TRANSITION}` as HARD triggers that downgrade PASSED→STALE and block `production_capital_allowed` — and they are function parameters defaulting to `False` that nothing ever computes. `libs/research/dist_shift.py` computes exactly that (KS + variance-ratio → `STABLE|DRIFT|SHIFT`) and has no production caller.** The producer and the consumer both exist, fit each other exactly, and were never connected. Worse: `scripts/build_enforcement_matrix.py:78,100` *cites* `dist_shift.py` as the evidence that laws L1.19 (information decay) and L2.10 (reality gap) are enforced — while nothing executes it. That is the L1.43 decorative-fence defect one level up: the enforcement matrix is green on two laws whose only named enforcement never runs.

## BRAINSTORM (continued)

43. **`revalidation` triggers ↔ `dist_shift` — the matched orphan pair above.** Wiring is one call site; it re-arms two laws at once — S — ledger, high rank.
44. The enforcement matrix counts a **never-called module as evidence of enforcement** — audit every matrix citation for "is this file actually executed?", not "does it exist" — S — fence (generalises: L1.28's CONFIG-VS-OUTCOME move applied to the matrix itself).
45. `libs/regime/engine.py:84` — `conf = posteriors[-1].max()` ignores both cross-checks computed on the next lines; live artifact reads `regime_confidence: 1.0` while `hmm_gmm_agree: false` **and** the rule engine says bear against the HMM's bull. **Confidence is structurally incapable of falling on disagreement** — S — L1.40 UNMEASURED-REPORTED-AS-OK.
46. `scripts/run_intelligence_cycle.py:86` reads `web/regime.json`, **which does not exist** (real path `web/regime_engine.json`) — the meta-learner has silently labelled every observation `"unlabelled"` on a 4-hourly cron since 2026-07-30; `web/intelligence_cycle.json` shows `meta_learning: NO-INPUT` — S — L1.44 phantom-path read, and the artifact reports the symptom without naming the cause.
47. **The desk's only live sleeve is a basis trade and there is no basis-regime classifier** — `contango`/`backwardation` appear only in docstrings (`libs/data/crypto_source.py:211-212`). We trade a state we cannot name — S — axis watchlist.
48. `tests/validation/conftest.py:40` declares the decay-detection method as `"CUSUM on live IC vs backtest confidence band"` — **a test fixture documenting a detector that was never built** (zero CUSUM implementations repo-wide) — S — the fixture is a spec; build it or retract it.
49. The regime→leverage quarantine (gap #14, incidents 07-16/07-18) has **no visible lifting condition** — a clamp without one is removable under the burden-of-proof rule — S — ledger.
50. `libs/risk/crisis.py` fail-closed crisis detector (vol ≥2.5× baseline, or correlation, or stale data) is reachable only through `libs/risk/gate.py:144`, which has **no production caller** — a crisis detector that cannot fire — A.
51. `libs/alpha/{decay,health,card}.py` consume `regime_stability` / `regime_mismatch` **as inputs defaulting to 1.0 with no producer anywhere** — read-without-writer, the desk's most prolific defect class — A.
52. `meta_learning.learn_regime_affinity` is called with `cpcv_pass=False` hardcoded → structurally always `deployable=False` — a welded gate inside the learner — A.
53. `_VOL_FACTOR={high:0.5,mid:0.8,low:1.0}` × `_TREND_FACTOR={bull:1.0,bear:0.75}` are **hand-set leverage constants never validated against realized per-regime Sharpe** — and the desk already has that table in `web/crypto_portfolio.json:regimes` (1165 bear / 1355 bull / 1148 high-vol days). Checking them is free — A.
54. **The rule-vs-HMM disagreement stream is itself a signal** (regime uncertainty) and it is being destroyed nightly by the in-place overwrite — persist it in the same commit as R0006 — A.
55. `data/label_registry.json` is declared at `scripts/build_labels.py:27` and **absent from disk**; `regime_transition` labelling is `DEGENERATE_RARE` at shipped parameters (`tests/research/test_label_factory.py:156`) — A.
56. `run_cashcarry_executor.py:44` `_LEV_TGT` — declared, never referenced again in 91KB — the regime→leverage chain terminates in an unused variable — B.
57. `run_trend_regime_shadow.py` holds a Holm slot at `forward_ann_sharpe: 0.0`, day 23/90, `in_market_pct: 52.8` — the desk's only true regime-gated strategy, EV-gate-rejected at p≈7%, taxing the cohort — B — feeds directly into the deep proposal's eviction question.
58. **No liquidation-cascade detector exists at all** (`_ORPHAN_MAX_PER_HOUR` is venue-health, not market state) despite 50,311 live liquidation ticks — the detector is missing, not just the conditioning — A.
59. `libs/risk/tail.py:80` names stress scenarios `broad_risk_off` / `liquidity_crisis` / `vol_spike` as **prescribed shock vectors with nothing measuring whether we are in one** — the stress lab cannot recognise its own scenarios in the wild — A.
60. `libs/regime/bayesian.py` `BayesianRegimeFilter.update()` and `RegimeEngine.make_filter()` have zero callers outside tests — an online filter built and never run, while the desk relies on a nightly batch fit — B — L2.9 ACTIVATE-or-RETIRE.
61. The HMM transition matrix has diagonal 0.962/0.959/0.969 — **implied regime durations ~24-32 days**, which is comparable to the 40-day clock length: most forward clocks span roughly one regime by construction — A — this is the quantitative backbone of the MONOCLIMATE branch and it is computable today from `web/regime_engine.json`.

Item 61 is the one I'd hand the builder alongside the deep proposal: it converts "clocks may be monoclimate" from a worry into a measured prior, using an artifact already on disk, in about ten minutes.

Next I would continue at **regime-conditioned adverse selection** (does fill quality degrade specifically when our signal is strongest — the crowding tell), the **listing-window regime × §42 capacity interaction**, and **regime-conditioned data quality** (does the recorder drop ticks precisely during cascades, biasing every study of the state we most want to trade).


## B -- GPT-9 family (independent)

(GPT-9 seat unavailable: HTTPError: HTTP Error 400: Bad Request. This run is SINGLE-FAMILY -- treat its proposal as unconfirmed by an independent family, and note that in the record.)
