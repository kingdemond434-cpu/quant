# CAPABILITY HUNT PROPOSALS 20260813 slot 3

LENS: FASTER PROMOTION -- what shortens the path from screen-hit to sized-capital without lowering a bar: an evidence accelerant (8h panels, event-density), a paper-sleeve auto-spawn, a resurrection-queue consumer. Time-to-alpha is a growth term.

## A -- Claude family

## MISSING CAPABILITY

**A measured cross-sectional breadth term in the screen's power model.** `axis_screen` divides `n_eff` by the *full* panel width, asserting that K symbols carry exactly **one** independent observation per bar — for panels the desk deliberately demeaned to make them independent.

**WHY IT IS INVISIBLE TODAY.** Three layers, each individually correct:

1. The error runs **conservative**. `libs/research/axis_screen.py:175` — `deflator = max(t_deflator,1.0) * max(panel_width,1)` — was written to kill a real over-claim (raw symbol-days inflate t by √K). It over-corrected past the truth to the opposite endpoint, and nobody audits a number that is already small (L1.55's own lesson).
2. Its output verdict is **structurally silent**. `SCREEN-UNDERPOWERED` is explicitly *not* a kill (`axis_screen.py:220` — "could not tell"), so a candidate dying here writes no graveyard entry, no alert, no ledger row, no resurrection-queue entry. It is the only exit from the pipeline that leaves no trace. **312 of 590 verdicts on disk are SCREEN-UNDERPOWERED — the largest class by 2×** — and no fence reads that ratio.
3. Every promotion-speed instrument the desk owns (`promotion_latency`, `slot_admission`, `evidence_clock`, `event_density`, `forward_slots`) starts **at or after the forward clock**. Nothing measures the screen's own false-null rate, and `SCREEN-INTERESTING` is the *only* verdict that starts a clock (`axis_screen.py:257`).

**MECHANISM.** `stage_a_screen` takes a measured `xs_neff` instead of dividing by `panel_width`: `effective_bets(K, measured residual ρ̄)` from `libs/research/cohort_independence.py`, referenced against `demeaning_floor(K)` — the module already hardened for exactly this trap, and never imported by the screen. Same fix at the second copy, `libs/validation/type2_cost.py:286` (whose *own file*, at `:250`, already calls `effective_bets` correctly for a different purpose). Publish the currently-absent `reports/cross_section_breadth.json`. New fence status on a panel cell that reports `n_eff` with no measured breadth basis: `UNMEASURED-BREADTH`, never a clean verdict.

**WHAT IT WOULD HAVE CAUGHT.** `scripts/screen_oi_ls_axes.py:126-133` records it: on 2026-08-11 the desk swung K_eff from K to 1 in one change, converting **"42 'graveyard-grade' SCREEN-WEAK verdicts the screen lacked the power to make"** into 42 silent underpowered ones. Both endpoints were assumptions; neither was measured. Measured now, on disk:

| | |
|---|---|
| panel cells (K=139/80/78), **all** SCREEN-UNDERPOWERED | **48** |
| `n_eff` understated by (desk's own 20.47-of-29 residual breadth) | up to **98×** |
| ⇒ detection floor inflated | **9.9×** |
| flip to `powered` when corrected | **48 / 48** → 1 SCREEN-INTERESTING (a clock), 47 graveyard-grade refutations |
| `slot_admission` resolve_days, `M3_taker_level\|xsrank\|rel\|1d` | **106,228 d (290 yr, UNAFFORDABLE)** → ~1,084 d, inside `MAX_RESOLVE_DAYS` |

This is the L1.25 diagnostic's first question — *instrument?* — one layer below the two campaign-constant gates already found.

**ROI.** Direct: 48 dead cells re-adjudicated, one clock born, 47 refutations banked. Cascade is the real term: the desk's own record says all 129 directional mechanisms failed at max OOS Sharpe 0.100, raw N_eff is 1.54 vs ~20 residual, and standing guidance is *"neutralise BTC beta or do not build it."* The desk is instructed to build market-neutral cross-sectional signals and its screen mis-measures exactly those by ~10× in t. It multiplies L1.30 births at the source, ahead of every downstream accelerant.

**COST.** ~4-6h. Competes with R0342 (calendar-gate migration, due 08-19) and the 38 past-due repair-mode rows. Loosens the *screen* only; `ic_min`, `sharpe_min`, Holm z, α and `MAX_FORWARD_SLOTS` are untouched. Must be **measured per panel** — asserting N_xs = K re-creates the pre-08-11 over-claim — and must use equicorrelation, not the matrix inverse: the desk already measured that `1'C⁻¹1` returns 1642 (noise) at this sample size.

**FALSIFIER.** Measure residual pairwise ρ̄ on the actual 139-symbol panel. If it sits near raw (~0.64) rather than near `demeaning_floor(139) = -0.00725` — i.e. the `rel` demeaning did not decorrelate it — then N_xs ≈ 1.56, the current deflator is approximately right, and this is worth 1.25× in t, not 9.9×. One script run decides it.

NOVELTY-CHECK: `grep -rniE "panel_width|cross-sectional n_eff|K_eff" docs/GAP_REGISTER.md docs/research/recommendation_ledger.json docs/CONSTITUTION.md docs/MASTER_QUANT_CONSTITUTION.md data/max_push_queue.json docs/research/TIER1_BENCHMARK.md` → one unrelated hit (R0-row on venue-fetch panel shrinkage); `grep -rn "effective_bets\|demeaning_floor" libs/research/axis_screen.py` → empty. Confirmed against a full sweep of the promotion-speed ground: L1.18a, L1.56, GAP #25/#25-RESULT (anytime-valid, retired-as-refuted), R0118/R0102/R0262/R0265/R0342/R0516 — all sit at or after the clock; none touches the screen's breadth term.

---

## BRAINSTORM

- **Publish `reports/cross_section_breadth.json`** — it is absent; the number survives only in a docstring. Any consumer of it is reading a fossil. — **S** — fence/ratchet
- **`SCREEN-UNDERPOWERED` rate as a fenced ratchet metric** — 312/590 and nothing reads it; a screen whose modal verdict is "could not tell" is an instrument report, not a research result. — **S** — new fence
- **Signal half-life per candidate** (`scripts/signal_halflife.py` exists) wired into `forward_resolution_days` as the bets-per-year term — the desk's own breadth study concludes half-life, not breadth, is binding, and the slot ranker ignores both. — **S** — ledger
- **`ic_min` is breadth-blind**: a fixed 0.03 IC floor means IR 0.48 on one series and IR 1.8 on a 139-panel. Replace the strength floor with a target IR at measured breadth (Grinold inverted — already coded at `measure_cross_section_breadth.py:585`, never used as a gate). — **S** — ledger
- **Paper sleeves can never reach ELIGIBLE** — no evaluator branch exists in `run_paper_sleeve_forward.py`; a live sleeve sits at `progress_to_resolution: 4.89` (489% of rows needed) still reading ACCRUING. — **S** — gap register
- **`ELIGIBLE` → capital has no reader** — only consumers are a counter and a list in `research_alpha_optimizer.py`. The promotion stage does not exist as code. — **S** — gap register
- **Cohort is 15/12, over the law cap** — `MAX_FORWARD_SLOTS=12` is "fixed for life" and is currently exceeded, so the Holm bar is no longer the bar that was pre-registered. — **S** — fence
- **4 of 6 axis clocks are DEGENERATE/UNTRACKED** (registered without `target_symbol`, unscoreable forever) — paying multiplicity, structurally unable to produce a birth. — **A** — ledger
- **`data/forward_slots.json` is a stale orphan** (`write_snapshot()` has no caller; 13 days old; says 12/12 while live is 15/12) yet is read by `survivor_panel` and `max_audit`. — **A** — fence
- **A false-null meter for the whole screen**: plant known-strength synthetic panels through `stage_a_screen` and measure the verdict distribution. The gauntlet has a positive control; the *screen* does not. — **S** — new fence
- **Ask what fraction of the 434 rejects were rejected by an instrument rather than by evidence** — R0329/R0444 already found 8/25 shadowed rejects (32%) would have paid OOS; re-run that with the corrected breadth term. — **A** — ledger
- **Verdict-transition ledger**: no artifact records that 42 cells changed verdict class on 2026-08-11 from a code change rather than from data. A screen re-adjudication should be a dated, diffable event. — **A** — new artifact
- **`libs/validation/screen_admission.py` is a full orphan** (`admit()`, `MIN_ADMISSION_BARS=1460`, all constants, zero production callers) while the live path uses `slot_admission.rank()` — two admission policies, one dead, no fence noticing. — **A** — ledger
- **`data/ramp_state.json` has never existed**, so the size ramp is pinned at 0.10 with six never-evaluated conditions — already known as a phantom, but the *lifting condition* is unpriced under L1.51. — **A** — ledger
- **Charge multiplicity by expected births, not by headcount** — a clock that cannot resolve inside its own capacity runway contributes zero births while taxing all 11 others; the Holm denominator should be auditable by *productive* slots. — **A** — ledger
- **Screen at the horizon where the mechanism decorrelates, not at a default grid** — every panel cell above is run at 1/5/20d; the h=20d cells are the ones that stay underpowered even corrected. — **B** — axis watchlist
- **Residual-correlation drift monitor** — breadth measured once at 20.47 is a fossil; correlation regime-shifts (a crypto beta spike) silently invalidate every power calculation downstream. — **A** — fence
- **Cross-venue panel widening** — the 139-symbol panel is one venue; independent names on a second venue add breadth that costs nothing but a collector already running. — **B** — axis watchlist
- **Measure `stack()`'s symbol weighting** — the fundamental-law breadth term only applies if the pooled IC weights names equally; unequal weights silently shrink effective breadth. — **B** — ledger
- **Every screen that passes `panel_width=1` on a genuinely pooled book should say why** — `screen_vol_risk_premium.py:744` documents its reasoning; `screen_primary_market_flow.py:816` and `screen_orderbook_state.py:615` just pass 1. — **B** — fence
- **A "why did this candidate never get a clock" trace** — today a candidate can die at the screen, at admission, at the mechanism cap, or at the slot cap, and only the last two leave a `deferred_because`. — **A** — new artifact
- **Retire `MAX_RESOLVE_DAYS` as a hard exclusion, make it a rank** — it currently permanently excludes on a number computed with a K_eff=1 error; a mis-measured cost fence is a silent kill. — **A** — ledger
- **Count the desk's own screens by target type** — the target/horizon sweep duty demands cross-sectional targets for asset-selection signals; measure what fraction of screens actually use one. — **B** — fence
- **Price the closed door** under L1.51: 48 cells × their idle days × stated ROI is a clamp with no `{since, holds_usd, lifting_condition}`. — **B** — ledger
- **`type2_cost.correlation_n_eff` has no independent test for the panel term** — the same bug in two files means a fix in one leaves the other authoritative. — **B** — fence
- **Ask whether `overlap_periods` is ever wrong in the same direction** — the desk found and fixed the sub-daily multiplier and the product-clamp; the third factor (autocorrelated *signals*, not targets) has never been deflated at all. — **A** — ledger

Next, unwritten: whether `xs_rank_z` normalisation destroys the very cross-sectional dispersion the breadth term prices, and whether the demeaning that buys independence also removes the alpha — the same estimator question one level up.


## B -- GPT-9 family (independent)

(GPT-9 seat unavailable: HTTPError: HTTP Error 402: Payment Required. This run is SINGLE-FAMILY -- treat its proposal as unconfirmed by an independent family, and note that in the record.)
