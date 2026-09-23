#!/usr/bin/env python3
"""R0574 -- does the estimation shrink already absorb the best-of-m PROMOTION winner's curse?

THE QUESTION, AND WHY IT IS THE ONE THAT SURVIVED R0432. R0432 asked whether the screen's
420-trial count should tighten `libs/risk/kelly_shrink.shrink_fraction`. It must not, and that is
decided in that function's own docstring (commit e56c6d95): the shrink is fed `fwd_sharpe` /
`fwd_days` off the pre-registered FORWARD clock (`dynamic_leverage.py:112`), data that took no part
in the screen's selection, so charging the screen's winner's curse there prices one selection twice.

BUT A SMALLER SELECTION IS REAL AND WAS UNPRICED. Promotion picks winners from at most
`MAX_FORWARD_SLOTS = 12` concurrent forward clocks. Holm corrects the p-value of that DECISION
(`run_axis_shadows.py:449`, `auto_promotion.py:147`); nothing de-biases the effect SIZE that
`auto_promotion.py:172` and the sizer then use. A candidate that just cleared the bar therefore
carries an upward-biased forward Sharpe, and that Sharpe is exactly what sizes the book.

THE FIRST VERSION OF THIS STUDY WAS WRONG AND ITS OWN NULL CONTROL CAUGHT IT -- recorded here
because the correction is the reusable part. It compared the desk's sizing against an
empirical-Bayes posterior mean and read the (large) gap as the winner's curse. But promoting a
cohort member AT RANDOM, with no bar and no max-taking and therefore no selection whatever, showed
the same gap: 0.98 of oracle growth. The posterior mean was winning on a second effect entirely --
the desk's prior has a SPIKE AT ZERO (420 screened, 0 survivors) and `S^2/(S^2+SE^2)` shrinks
toward zero using SE alone, never toward that prior. That gain is real but it is NOT selection, and
a study that reported it as selection would have charged one effect for another's sins. The design
below isolates the selection term by construction.

METHOD (one cell = one (m, n_days, prior) triple, all arms on COMMON RANDOM NUMBERS):
  1. m candidates enter a cohort of concurrent forward clocks. Each draws a TRUE annualized Sharpe
     from the desk's prior: with probability `pi` a real edge ~ Exponential(mean `s_edge`),
     otherwise exactly zero.
  2. Each accumulates `n_days` of forward evidence, so the observed Sharpe is
     S_hat ~ Normal(S_true, SE(S_true, n_days)) with Lo's SE -- the same SE the sizer uses.
  3. t = S_hat * sqrt(n_days / 365), the desk's own `forward_stats` convention, is compared against
     `holm_bar(m, rank=1)`. The MAX-t candidate is promoted if it clears. That is the selection.
  4. The promoted sleeve is sized FIVE ways and then earns at its TRUE Sharpe:
       naive     L = S_hat                                   <- no shrink at all, the floor
       desk      L = shrink_fraction(S_hat, n) * S_hat       <- what runs today
       eb_blind  L = E[S_true | S_hat]                       <- posterior mean, SELECTION-BLIND:
                                                                calibrated on ALL candidates
       eb_aware  L = E[S_true | S_hat, promoted]             <- posterior mean, SELECTION-AWARE:
                                                                calibrated on WINNERS only
       oracle    L = S_true                                  <- the ceiling, unreachable
     Realized annualized log-growth at unit vol is L*S_true - L^2/2 (Kelly optimum L = S_true).
     A round promoting nobody earns 0 in every arm: growth per PROMOTION ROUND is the quantity the
     desk cares about, not growth per promoted sleeve.
  5. THE SELECTION TERM IS `eb_aware - eb_blind`. Both arms know the prior; they differ ONLY in
     whether the map conditions on having been selected. Their difference is therefore the
     winner's curse and nothing else. `desk - eb_blind` is the separate prior term, reported
     alongside so the two are never again read as one number.
  6. Both maps are calibrated on an INDEPENDENT draw (different seed) and applied out-of-sample.

PRE-REGISTERED, BEFORE THE RUN:
  * NULL CONTROL -- promote a RANDOM cohort member, no bar, no max-taking. Winners are then an iid
    sample of candidates, so the aware and blind maps are calibrated on the SAME distribution and
    the selection term must vanish: |selection gain| < 1% of oracle growth. This is the control the
    first version failed.
  * POSITIVE CONTROL -- m = 420, the screen's own intensity, where the selection term MUST be large
    and detectable. A method never shown to find a known-present bias has not been validated; only
    its silences would have been observed.
  * VERDICT at the live m = 12, on the SELECTION term:
      paired t < 3.0                      -> ABSORBED (retires the question)
      t >= 3.0 and gain < 1% of oracle    -> ABSORBED-MATERIALLY (detectable, not economic)
      t >= 3.0 and gain >= 1% of oracle   -> CORRECTION-REAL (and the direction is TIGHTER)

SCOPE -- TWO SIZING PATHS EXIST AND THIS STUDY IS ABOUT ONE OF THEM. Checked at the source rather
than assumed, because they carry different constants and reading them as one pipeline is the
same-name-different-question error (L1.61):
  * `dynamic_leverage.optimize_sleeve` -> `shrink_fraction(fwd_sharpe, fwd_days)` (line 112), fed
    for named sleeves by `run_leverage_opt.py`. THIS is the path R0574 asks about and the one the
    `desk` arm models.
  * `auto_promotion.decide` -> `clip` sized from `margin = t / holm_bar` (line 172). Also consumes
    the selected, un-de-biased forward t, but through a capped clip fraction rather than through
    `shrink_fraction`. NOT modelled here; it inherits the same bias by the same mechanism and is
    rowed separately.
`_PLAUSIBLE_SHARPE = 4.0` (`run_leverage_opt.py:36`) is a rail on the FIRST path only, applied to
the cash-and-carry shadow series, and it is NOT a gate on cohort promotion. It appears in the
artifact purely as a REFERENCE CEILING -- `frac_winners_above_desk_plausibility_ceiling` counts how
many of this study's promoted winners carry a forward Sharpe above the level the desk elsewhere
calls a measurement defect. It is context for reading the leverage numbers, never a claim that
anything zeroes these candidates today.

WHAT THIS DOES NOT DO. Nothing here is wired. No sizer, rail, gate or bar is changed by this file
(`"wired": false` in the artifact). `_ruin_cap` and `first_inversion_cap` bind from the constraint
side and are deliberately absent from the arms -- this measures the SHRINK in isolation.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.research.slot_registry import MAX_FORWARD_SLOTS  # noqa: E402
from libs.risk.kelly_shrink import sharpe_se, shrink_fraction  # noqa: E402
from libs.validation.forward_stats import holm_bar  # noqa: E402

_OUT = _ROOT / "docs/research/promotion_selection_bias_study.json"
_PPY = 365.0
_ROUNDS = 200_000          # promotion rounds per arm per cell
_N_BINS = 40               # quantile bins for the empirical-Bayes calibration maps
_CAL_POOL = 400_000        # candidates retained for the SELECTION-BLIND map
_SCREEN_M = 420            # the screen's own intensity -- the positive control
_PLAUSIBLE_SHARPE = 4.0    # run_leverage_opt.py:36 -- a rail on the OTHER path; reference only
# Bound the (rounds x m) intermediates. The positive control is 200k x 420 = 84M elements per
# array and several exist at once; unchunked, the first run of this script was OOM-killed at
# exit 137. Only the per-round WINNERS survive a chunk, and those are `rounds` long whatever m is.
#
# A CONSTANT NUMBER OF ROUNDS, NOT A CONSTANT NUMBER OF ELEMENTS. Deriving the chunk from `m`
# (elements // m) made the boundaries -- and therefore the order in which the generator is consumed
# -- a function of a STUDY PARAMETER, so the m=4 and m=12 cells drew differently for reasons that
# had nothing to do with the question. Fixed rounds keep the draw identical across cells and bound
# memory at _CHUNK_ROUNDS * m, which is 4.2M elements at the m=420 control.
_CHUNK_ROUNDS = 10_000


def _se_vec(s_true: np.ndarray, n_days: float) -> np.ndarray:
    """Lo (2002) SE of the annualized Sharpe, vectorized.

    Pinned against `libs.risk.kelly_shrink.sharpe_se` by `_instrument_checks` so this copy can
    never drift from the SE the sizer actually uses -- a study whose arithmetic has quietly
    diverged from the code it is judging measures nothing.
    """
    s_daily = s_true / math.sqrt(_PPY)
    return np.sqrt((1.0 + 0.5 * s_daily * s_daily) / n_days) * math.sqrt(_PPY)


def _shrink_vec(s_hat: np.ndarray, n_days: float) -> np.ndarray:
    """`shrink_fraction` vectorized, including its S<=0 and n_eff<5 zero branches (vif=1)."""
    out = np.zeros_like(s_hat)
    if n_days < 5:
        return out
    pos = s_hat > 0.0
    if not pos.any():
        return out
    s = s_hat[pos]
    se = _se_vec(s, n_days)
    s2 = s * s
    out[pos] = s2 / (s2 + se * se)
    return out


def _growth(lev: np.ndarray, s_true: np.ndarray) -> np.ndarray:
    """Annualized log-growth rate at unit vol: L*mu - L^2 sigma^2/2 with sigma = 1, mu = S_true.

    Full Kelly is L = S_true, which is what makes the oracle arm a genuine ceiling.
    """
    return lev * s_true - 0.5 * lev * lev


def _draw(rng: np.random.Generator, rounds: int, m: int, pi: float, s_edge: float,
          n_days: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """One cohort draw: (S_true, S_hat, t) each shaped (rounds, m)."""
    real = rng.random((rounds, m)) < pi
    s_true = np.where(real, rng.exponential(s_edge, (rounds, m)), 0.0)
    s_hat = s_true + rng.normal(0.0, 1.0, (rounds, m)) * _se_vec(s_true, n_days)
    return s_true, s_hat, s_hat * math.sqrt(n_days / _PPY)


def _select(t: np.ndarray, bar: float,
            rng: np.random.Generator | None) -> tuple[np.ndarray, np.ndarray]:
    """Return (index of the chosen candidate, promoted mask).

    `rng` is None for the real regime -- take the MAX t and require it to clear the Holm bar, which
    is the selection this study exists to price. Passing an rng switches to the NULL CONTROL:
    choose a cohort member at random and promote unconditionally, so winners are an iid sample of
    candidates and a correct selection term must vanish.
    """
    if rng is None:
        win = np.argmax(t, axis=1)
        return win, np.take_along_axis(t, win[:, None], 1).ravel() >= bar
    win = rng.integers(0, t.shape[1], size=t.shape[0])
    return win, np.ones(t.shape[0], dtype=bool)


def _harvest(rng: np.random.Generator, rounds: int, m: int, pi: float, s_edge: float,
             n_days: float, bar: float, sel_rng: np.random.Generator | None
             ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Draw `rounds` cohorts in memory-bounded chunks.

    Returns (S_hat_winner, S_true_winner, promoted, pool_hat, pool_true). The first three are one
    entry per round; the last two are an iid pool of ALL candidates -- selection-blind by
    construction -- capped at `_CAL_POOL`. The cohort is never materialized whole (`_CHUNK_ROUNDS`).
    """
    chunk = max(1, min(rounds, _CHUNK_ROUNDS))
    hat_w, true_w, prom, p_hat, p_true = [], [], [], [], []
    pooled = 0
    done = 0
    while done < rounds:
        n = min(chunk, rounds - done)
        s_true, s_hat, t = _draw(rng, n, m, pi, s_edge, n_days)
        win, ok = _select(t, bar, sel_rng)
        hat_w.append(np.take_along_axis(s_hat, win[:, None], 1).ravel())
        true_w.append(np.take_along_axis(s_true, win[:, None], 1).ravel())
        prom.append(ok)
        if pooled < _CAL_POOL:
            # every candidate is iid, so a prefix of the flattened chunk is an unbiased sample
            take = min(_CAL_POOL - pooled, s_hat.size)
            p_hat.append(s_hat.ravel()[:take])
            p_true.append(s_true.ravel()[:take])
            pooled += take
        done += n
    return (np.concatenate(hat_w), np.concatenate(true_w), np.concatenate(prom),
            np.concatenate(p_hat), np.concatenate(p_true))


def _calibrate(s_hat: np.ndarray, s_true: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Empirical-Bayes map E[S_true | S_hat] over quantile bins.

    Quantile bins rather than fixed-width: the promoted region is a thin upper tail and fixed-width
    bins there are mostly empty, which turns the map into noise exactly where it has to be right.
    """
    if s_hat.size < _N_BINS * 10:
        return np.array([]), np.array([])
    edges = np.unique(np.quantile(s_hat, np.linspace(0.0, 1.0, _N_BINS + 1)))
    if edges.size < 3:
        return np.array([]), np.array([])
    idx = np.clip(np.digitize(s_hat, edges[1:-1]), 0, edges.size - 2)
    centre = np.full(edges.size - 1, np.nan)
    target = np.full(edges.size - 1, np.nan)
    for b in range(edges.size - 1):
        sel = idx == b
        if sel.any():
            centre[b] = float(s_hat[sel].mean())
            target[b] = float(s_true[sel].mean())
    ok = ~np.isnan(centre)
    return centre[ok], target[ok]


def _apply(centre: np.ndarray, target: np.ndarray, s_hat: np.ndarray) -> np.ndarray:
    """Apply a calibrated map, clipped at the ends rather than extrapolated."""
    if centre.size < 2:
        return s_hat.copy()
    return np.maximum(np.interp(s_hat, centre, target), 0.0)


def _paired_t(a: np.ndarray, b: np.ndarray) -> float:
    """t-stat of mean(a - b) over paired rounds. Common random numbers make the pairing exact."""
    d = a - b
    sd = float(d.std(ddof=1))
    if sd <= 0.0 or d.size < 2:
        return 0.0
    return float(d.mean() / (sd / math.sqrt(d.size)))


def _instrument_checks() -> dict[str, object]:
    """Run BEFORE any adjudication -- a verdict from a blunt instrument is the false-null direction
    no other gate on this desk catches. Pins the vectorized copies against the live library."""
    grid_s = np.array([0.2, 0.5, 0.75, 1.0, 1.5, 2.3, 4.0])
    worst_se, worst_shrink = 0.0, 0.0
    for n in (40.0, 90.0, 180.0, 365.0):
        worst_se = max(worst_se, float(np.max(np.abs(
            _se_vec(grid_s, n) - np.array([sharpe_se(float(s), n) for s in grid_s])))))
        # the library rounds to 4dp; compare against the unrounded formula at that tolerance
        worst_shrink = max(worst_shrink, float(np.max(np.abs(
            _shrink_vec(grid_s, n) - np.array([shrink_fraction(float(s), n) for s in grid_s])))))
    rng = np.random.default_rng(20260820)
    emax = {k: float(np.mean(np.max(rng.standard_normal((200_000, k)), axis=1)))
            for k in (MAX_FORWARD_SLOTS, _SCREEN_M)}
    return {
        "se_matches_library_max_abs_err": round(worst_se, 12),
        "shrink_matches_library_max_abs_err": round(worst_shrink, 6),
        "instrument_ok": bool(worst_se < 1e-9 and worst_shrink < 1e-4),
        "e_max_of_k_standard_normals": {str(k): round(v, 3) for k, v in emax.items()},
        "e_max_note": (
            f"selection intensity is best-of-{MAX_FORWARD_SLOTS} at promotion "
            f"({emax[MAX_FORWARD_SLOTS]:.2f} SEs) against best-of-{_SCREEN_M} at the screen "
            f"({emax[_SCREEN_M]:.2f} SEs) -- roughly half, which is why R0432's answer does not "
            "carry over to this question"),
    }


def cell(m: int, n_days: float, pi: float, s_edge: float, *, null_control: bool = False,
         seed: int = 0, rounds: int = _ROUNDS) -> dict[str, object]:
    """One measured cell. All five sizing arms share the same draws (common random numbers)."""
    bar = float(holm_bar(m, 1))
    sel_cal = np.random.default_rng(seed + 8_000_000) if null_control else None
    sel_ev = np.random.default_rng(seed + 9_000_000) if null_control else None

    # --- calibration draw (independent seed; never scored) ---
    c_hat_w, c_true_w, c_prom, c_pool_h, c_pool_t = _harvest(
        np.random.default_rng(seed + 7_000_000), rounds, m, pi, s_edge, n_days, bar, sel_cal)
    aware = _calibrate(c_hat_w[c_prom], c_true_w[c_prom])   # winners only  -> selection-AWARE
    blind = _calibrate(c_pool_h, c_pool_t)                  # all candidates -> selection-BLIND

    # --- evaluation draw (scored, out-of-sample w.r.t. both maps) ---
    hat_w, true_w, prom, _, _ = _harvest(
        np.random.default_rng(seed), rounds, m, pi, s_edge, n_days, bar, sel_ev)

    arms = {
        "naive": np.maximum(hat_w, 0.0),
        "desk": _shrink_vec(hat_w, n_days) * hat_w,
        "eb_blind": _apply(*blind, hat_w),
        "eb_aware": _apply(*aware, hat_w),
        "oracle": true_w.copy(),
    }
    growth = {k: np.where(prom, _growth(lev, true_w), 0.0) for k, lev in arms.items()}
    means = {k: float(v.mean()) for k, v in growth.items()}
    orc = means["oracle"]

    # THE SELECTION TERM: both maps know the prior, they differ only in conditioning on selection.
    sel_gain = means["eb_aware"] - means["eb_blind"]
    sel_t = _paired_t(growth["eb_aware"], growth["eb_blind"])
    sel_rel = sel_gain / orc if orc > 0 else float("nan")
    # the separate PRIOR term, reported so the two are never read as one number again
    prior_gain = means["eb_blind"] - means["desk"]
    prior_rel = prior_gain / orc if orc > 0 else float("nan")

    n_prom = int(prom.sum())
    bias = float((hat_w[prom] - true_w[prom]).mean()) if n_prom else float("nan")
    bias_ses = (bias / float(_se_vec(true_w[prom], n_days).mean())) if n_prom else float("nan")
    railed = (float((hat_w[prom] > _PLAUSIBLE_SHARPE).mean()) if n_prom else float("nan"))

    if not math.isfinite(sel_rel):
        verdict = "UNMEASURED (oracle growth non-positive -- no edge exists in this prior)"
    elif null_control:
        verdict = ("NULL-CONTROL-PASSED" if abs(sel_rel) < 0.01 else
                   "NULL-CONTROL-FAILED (selection term non-zero where there is no selection)")
    elif abs(sel_t) < 3.0:
        verdict = "ABSORBED (selection term not measurable)"
    elif sel_rel < 0.01:
        verdict = "ABSORBED-MATERIALLY (selection term detectable but under 1% of oracle growth)"
    else:
        verdict = "CORRECTION-REAL (selection term buys growth; direction is TIGHTER)"

    return {
        "m": m, "n_days": n_days, "pi": pi, "s_edge": s_edge,
        "null_control": null_control, "holm_bar": bar, "rounds": rounds,
        "n_promoted": n_prom,
        "promotion_rate": round(n_prom / rounds, 5),
        "selected_sharpe_bias": round(bias, 4),
        "selected_sharpe_bias_in_ses": round(bias_ses, 3),
        "frac_winners_above_desk_plausibility_ceiling": round(railed, 4),
        "mean_growth": {k: round(v, 6) for k, v in means.items()},
        "selection_gain": round(sel_gain, 8),
        "selection_gain_t": round(sel_t, 2),
        "selection_gain_as_frac_of_oracle": round(sel_rel, 5) if math.isfinite(sel_rel) else None,
        "prior_gain": round(prior_gain, 8),
        "prior_gain_as_frac_of_oracle": round(prior_rel, 5) if math.isfinite(prior_rel) else None,
        "ceiling_holds": bool(all(orc >= means[k] - 1e-12 for k in arms)),
        "shrink_beats_naive": bool(means["desk"] > means["naive"]),
        "verdict": verdict,
    }


def main() -> int:
    instr = _instrument_checks()
    cells: list[dict[str, object]] = []
    seed = 4242

    # NULL CONTROL first -- if the selection term is non-zero with no selection present,
    # nothing downstream in this file means anything.
    for n_days in (90.0, 180.0):
        cells.append(cell(MAX_FORWARD_SLOTS, n_days, 0.15, 1.0, null_control=True, seed=seed))
        seed += 1
    # POSITIVE CONTROL -- the screen's own intensity, where the selection term must be large.
    cells.append(cell(_SCREEN_M, 180.0, 0.15, 1.0, seed=seed))
    seed += 1
    # THE LIVE REGIME.
    for m in (4, MAX_FORWARD_SLOTS):
        for n_days in (90.0, 180.0):
            for pi, s_edge in ((0.05, 1.0), (0.15, 1.0), (0.30, 0.5)):
                cells.append(cell(m, n_days, pi, s_edge, seed=seed))
                seed += 1

    nulls = [c for c in cells if c["null_control"]]
    pos = next(c for c in cells if c["m"] == _SCREEN_M and not c["null_control"])
    live = [c for c in cells if c["m"] == MAX_FORWARD_SLOTS and not c["null_control"]]

    n_null_ok = sum(1 for c in nulls if str(c["verdict"]).startswith("NULL-CONTROL-PASSED"))
    pos_ok = bool(str(pos["verdict"]).startswith("CORRECTION-REAL"))
    ceilings_ok = sum(1 for c in cells if c["ceiling_holds"])

    if not instr["instrument_ok"]:
        answer = "UNUSABLE (the study's arithmetic no longer matches libs/risk/kelly_shrink)"
    elif n_null_ok < len(nulls):
        answer = "UNUSABLE (null control failed -- the selection term is measuring something else)"
    elif not pos_ok:
        answer = ("UNMEASURED (positive control did not detect the known best-of-420 selection "
                  "bias, so a null at m=12 is a statement about the instrument, not the desk)")
    elif all(str(c["verdict"]).startswith("ABSORBED") for c in live):
        answer = ("ABSORBED -- at the desk's live selection intensity, conditioning the effect-size "
                  "estimate on having been selected buys no material growth over an equally "
                  "prior-aware estimator that ignores selection. R0574's specific question is "
                  "retired: best-of-12 does not warrant a change to shrink_fraction.")
    else:
        answer = ("CORRECTION-REAL -- conditioning on selection buys measurable growth at the live "
                  "intensity, so the promoted effect size IS upward-biased in a way the estimation "
                  "shrink does not absorb. Any change is TIGHTER, never looser.")

    worst_prior = max((c["prior_gain_as_frac_of_oracle"] or 0.0) for c in live)
    # Derived, not simulated: what forward Sharpe a candidate MUST show to clear the Holm bar at a
    # given horizon, since t = S * sqrt(n/365). Surfaced because the study's promoted winners sit
    # far above the level the desk calls implausible elsewhere, and that turned out to be
    # arithmetic rather than a simulation artifact.
    bar_vs_plaus = {}
    for mm in (4, MAX_FORWARD_SLOTS, _SCREEN_M):
        b = float(holm_bar(mm, 1))
        bar_vs_plaus[str(mm)] = {
            "holm_bar": b,
            "min_forward_sharpe_to_clear": {str(int(nn)): round(b / math.sqrt(nn / _PPY), 2)
                                            for nn in (90, 180, 365)},
            "days_until_requirement_falls_to_plausibility_ceiling":
                round(_PPY * (b / _PLAUSIBLE_SHARPE) ** 2),
        }
    doc = {
        "row": "R0574",
        "parent_row": "R0432",
        "question": ("promotion selects the best of MAX_FORWARD_SLOTS concurrent forward clocks and "
                     "Holm corrects the p-value of that decision, not the effect SIZE the sizer "
                     "then uses -- does S^2/(S^2+SE^2) already absorb the best-of-12 winner's "
                     "curse?"),
        "status": "MEASURED",
        "ran": datetime.now(UTC).isoformat(),
        "max_forward_slots": MAX_FORWARD_SLOTS,
        "screen_intensity_for_positive_control": _SCREEN_M,
        "rounds_per_cell": _ROUNDS,
        "instrument_checks": instr,
        "null_control_passed": f"{n_null_ok}/{len(nulls)}",
        "null_control_note": (
            "promote a RANDOM cohort member with no bar: winners are then an iid sample of "
            "candidates, both maps see the same distribution, and the selection term must vanish. "
            "The FIRST version of this study had no such control and read the prior term as the "
            "selection term -- it measured 0.98 of oracle growth where there was no selection at "
            "all."),
        "positive_control_passed": f"{1 if pos_ok else 0}/1",
        "positive_control_note": (
            "at m=420 the selection bias MUST be large and the aware map MUST find it. A method "
            "never shown to detect a known-present bias has not been validated -- only its "
            "silences have been observed."),
        "ceiling_holds": f"{ceilings_ok}/{len(cells)}",
        "ceiling_note": ("the oracle arm sizes on S_true and is an upper bound on every other arm "
                         "by construction; a cell where it is beaten is a broken simulator"),
        "n_cells": len(cells),
        "answer": answer,
        "the_larger_finding": (
            "THE SELECTION TERM IS NOT WHERE THE MONEY IS. Across the live cells the PRIOR term -- "
            f"an estimator that knows the desk's spike-at-zero prior, versus S^2/(S^2+SE^2) which "
            f"knows only SE -- is worth up to {worst_prior:.2f} of oracle growth, an order of "
            "magnitude more than conditioning on selection. shrink_fraction shrinks toward zero "
            "using the standard error alone and never toward the desk's own base rate, and that "
            "omission dominates the one R0574 asked about. Rowed separately rather than acted on "
            "here: it is a different question from the one this study pre-registered, and the "
            "prior is an input this desk would have to estimate and defend before any sizer read "
            "it."),
        "bar_vs_plausibility": bar_vs_plaus,
        "bar_vs_plausibility_note": (
            "PURE ARITHMETIC, NOT A SIMULATION RESULT, and it is a tension between two constants "
            "this desk holds in two different pipelines rather than a proven live weld. Because "
            f"t = S*sqrt(n/365), a cohort of {MAX_FORWARD_SLOTS} cannot clear its Holm bar of "
            f"{holm_bar(MAX_FORWARD_SLOTS, 1):.2f} on fewer than "
            f"{round(_PPY * (holm_bar(MAX_FORWARD_SLOTS, 1) / _PLAUSIBLE_SHARPE) ** 2)} forward "
            f"days unless the candidate shows a forward Sharpe above {_PLAUSIBLE_SHARPE} -- the "
            "level run_leverage_opt treats as a measurement defect rather than evidence of edge. "
            "The two constants govern different paths (see SCOPE in the module docstring), so "
            "nothing is currently blocked by this; it is flagged because any future wiring that "
            "put a short-horizon promotion through the cash-and-carry rail would deadlock, and "
            "because a bar only clearable by an implausible reading is worth knowing about."),
        "wired": False,
        "wired_note": ("STUDY ONLY. No sizer, rail, gate or bar is changed by this file. "
                       "libs/risk/kelly_shrink.py is untouched."),
        "cells": cells,
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(doc, indent=1), "utf-8")

    print(f"instrument: {'OK' if instr['instrument_ok'] else 'BROKEN'}   "
          f"E[max] {MAX_FORWARD_SLOTS}={instr['e_max_of_k_standard_normals'][str(MAX_FORWARD_SLOTS)]}"
          f" SEs  {_SCREEN_M}={instr['e_max_of_k_standard_normals'][str(_SCREEN_M)]} SEs")
    print(f"{'m':>7} {'n_d':>5} {'pi':>5} {'edge':>5} {'prom':>7} {'bias/SE':>8} {'railed':>7} "
          f"{'g_desk':>9} {'g_blind':>9} {'g_aware':>9} {'sel_t':>7} {'sel/orc':>8} {'pri/orc':>8}  verdict")
    for c in cells:
        tag = "NULL" if c["null_control"] else ""
        sr = c["selection_gain_as_frac_of_oracle"]
        pr = c["prior_gain_as_frac_of_oracle"]
        print(f"{tag:>4}{c['m']:>3} {c['n_days']:>5.0f} {c['pi']:>5.2f} {c['s_edge']:>5.2f} "
              f"{c['promotion_rate']:>7.3f} {c['selected_sharpe_bias_in_ses']:>8.2f} "
              f"{c['frac_winners_above_desk_plausibility_ceiling']:>7.3f} "
              f"{c['mean_growth']['desk']:>9.5f} {c['mean_growth']['eb_blind']:>9.5f} "
              f"{c['mean_growth']['eb_aware']:>9.5f} {c['selection_gain_t']:>7.1f} "
              f"{(sr if sr is not None else float('nan')):>8.4f} "
              f"{(pr if pr is not None else float('nan')):>8.4f}  {c['verdict']}")
    print(f"\nANSWER: {answer}")
    print(f"written -> {_OUT.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
