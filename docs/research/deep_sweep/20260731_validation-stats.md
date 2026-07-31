# WEEKLY DEEP COLD AUDIT — validation-stats — 2026-07-31

STATUS: IN PROGRESS

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

_(placeholders — filled at the end from the evidence below)_

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

_TBD_

## 2. WHAT WE DON'T KNOW (ignorance ledger)

_TBD_

## FINDINGS (new this sweep, V-numbered; every claim carries its proving command)

_TBD_

## SIX PERSPECTIVES (explicit coverage)

_TBD_

## NEGATIVE-SPACE SWEEP

_TBD_

## 3. WHAT COULD MATTER MOST (ranked: impact × confidence / (cost × maintenance))

_TBD_

## 4. WHAT WE TEST NEXT (concrete, with success criteria)

_TBD_

## PROACTIVE BATTERY (generative moves run + what each produced)

_TBD_

## AUDIT SELF-NOTES (honesty)

_TBD_
