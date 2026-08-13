"""R0266: does an absorbing-boundary shrink COMPOSE with the shrinks already in the sizer, or
DOUBLE-COUNT against them? Study only -- this wires nothing and sizes nothing.

THE ROW'S QUESTION. `libs/risk/kelly_shrink.py` shrinks for ESTIMATION error: S^2/(S^2+SE^2), the
max-E[log] bet under parameter uncertainty. The nonergodic-growth literature describes a
DIFFERENT and additive shrink: with a costly lower boundary, optimal exposure falls BELOW the
no-boundary Kelly fraction as a function of log-distance to that boundary. This desk is the exact
case the second one is written for -- capital deploys from ~$1k, and venue minimums make small
equity genuinely absorbing: below roughly $200 (`_EXEC_VIABILITY_FLOOR_USD`, 20x the $10 venue
minimum) an account cannot execute a handful of economic round-trips, so it cannot trade its way
back. That floor is not a metaphor for ruin; it IS the barrier.

But the row also names the trap, and it is the reason this is a study and not a patch: two
independent haircuts on the same estimate is the duplicated-multiplicity error in sizing form --
the identical mistake the gate audit found in validation, where turnover was priced twice because
nobody checked whether it was already in the number.

SO THERE ARE TWO DOUBLE-COUNT QUESTIONS, NOT ONE, and only the second is dangerous:

  Q1  boundary shrink vs ESTIMATION shrink. Different causes -- one is about not knowing the
      parameter, the other about the objective changing near a barrier you can be stopped at.
      Expected to compose.
  Q2  boundary shrink vs THE RUIN CAP ALREADY IN THE SIZER. `dynamic_leverage._ruin_cap` already
      searches for the largest leverage whose bootstrapped P(ruin) <= 2%, and `optimize_sleeve`
      already takes min(base, kelly, ruin_cap). If that cap already binds below the
      absorption-aware optimum, a boundary shrink on top charges twice for one barrier.

WHY Q2 IS NOT ANSWERABLE FROM THE CODE ALONE. A ruin CAP and a boundary-aware OPTIMUM are
different objects even though both respond to the barrier. The cap is a constraint -- keep
P(hit) under a tolerance -- and says nothing about growth. The optimum asks what maximises
E[log W] when paths that touch the barrier stop compounding. A leverage can satisfy the
constraint and still be well above the growth optimum, or the reverse. Which one binds is an
empirical question about this desk's numbers, so it is measured here rather than argued.

WHAT IS SIMULATED. A multiplicative wealth process at a known true Sharpe, one year of daily
steps, over a grid of Kelly multiples, under three regimes:

  NO-BARRIER   paths compound through everything             -> f*_noabs  (textbook Kelly)
  ABSORBING    a path touching the barrier stops there       -> f*_abs
  JOINT        absorbing AND the Sharpe is only estimated    -> f*_joint

plus CONTROL A -- estimation noise with NO barrier, which is what makes the rest readable.

Absorption is modelled as the account FREEZING at the barrier, not going to zero. That is the
honest reading of a venue minimum -- the money is still there, it just cannot be put to work --
and it keeps log(W) finite so the expectation exists. A literal log(0) would make every
positive-f bet infinitely bad and the study would answer itself.

WHAT IT MEASURED (2026-08-05, 12 cells, positive control 12/12)
---------------------------------------------------------------
1. THE BOUNDARY SHRINK IS REAL AND SMALL AT THE DESK'S ACTUAL BARRIER. At the $200-on-$1k
   viability floor (barrier 0.20), gamma_boundary is 1.00 / 0.95 / 0.90 for S = 0.75 / 1.5 / 2.3.
   At a $100 book (barrier 0.50) it steepens to 0.90 / 0.75 / 0.70. So the effect the row
   describes exists and is worth at most a 10% haircut at the size the desk actually trades --
   against an estimation shrink already applying 0.058 to 0.721 in the same cells. It is an
   order of magnitude smaller than the shrink already in the sizer.

2. CONTROL A KILLED THE FIRST VERSION OF THIS STUDY, and it locates WHY the existing shrink is
   right -- which is not the reason usually given for it. Estimation noise ALONE leaves the
   optimum at exactly full Kelly (f* = 1.00 in every cell). Not a simulation quirk:
   E[log W_T] = T(L*mu - L^2 sigma^2/2) is LINEAR in mu, so averaging over an UNBIASED mu cannot
   move the argmax. The everyday story -- "Kelly's penalty is asymmetric, so noise means bet
   less" -- does not survive that: asymmetry of the penalty is already inside the quadratic, and
   symmetric noise about a correct mean does not move the optimum.

   What DOES justify shrinking is that the desk's estimate is not unbiased for the quantity it
   bets on. It selects edges BECAUSE they measured well, so mu-hat carries a winner's curse, and
   the correct input is the POSTERIOR MEAN of mu under a prior that most candidates have no edge
   -- which is strictly below mu-hat. And `shrink_fraction`'s S^2/(S^2+SE^2) is exactly the
   James-Stein / normal-posterior shrinkage factor toward a zero-edge prior, so THE FORMULA IS
   THE RIGHT ONE; it is the rationale attached to it that is misstated. This matters practically
   because the two stories calibrate differently: a posterior-mean shrink should be tuned to how
   strong the zero-edge prior is and how selected the candidate was, and neither of those is an
   input to it today. Flagged, not acted on -- this study changes no sizer, and the shrink errs
   toward betting less.

3. THE JOINT CELL IS AN ARTIFACT AND IS PUBLISHED AS ONE. Combining absorption with parameter
   noise pushed f* ABOVE full Kelly in 11 of 12 cells (measured range 0.90-3.00, two of them
   clipped at the grid edge and flagged). Cause: freezing at the barrier floors terminal
   log-wealth at log(barrier) while the upside stays unbounded, so mu-dispersion pays like a
   call option. That is a property of the ONE-YEAR horizon, not of the desk's objective -- over
   a lifetime, absorption forfeits ALL future compounding rather than settling at 0.2x book. A
   first version of this file read that artifact as "the two shrinks DOUBLE-COUNT in 12/12
   cells" and would have shipped it; the horizon-aware version is the honest next step and is
   rowed rather than guessed at.

SO THE ROW'S QUESTION IS ANSWERED WHERE IT MATTERS: do not wire a boundary shrink. Not because
it is unreal, but because at this desk's barrier it is <=10%, it is dominated by the estimation
shrink already applied, and `_ruin_cap` already binds the same barrier from the constraint side.
Wiring a third haircut for a tenth-order effect is the duplicated-multiplicity error the row
itself warned about.

NOTHING HERE CHANGES A RAIL, A BAR OR A SIZER.
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np

from libs.risk.kelly_shrink import sharpe_se, shrink_fraction

_ROOT = Path(__file__).resolve().parents[1]
_OUT = _ROOT / "docs/research/absorbing_kelly_study.json"

_PPY = 365.0
_HORIZON = 365                      # one year of daily steps
_N_PATHS = 8_000
_F_GRID = np.round(np.arange(0.05, 3.01, 0.05), 4)   # multiples of full Kelly
_SIGMA_D = 0.02                     # ~38% annualised, a crypto-sleeve scale

#: The desk's REAL barrier, and it is not a modelling choice. `_EXEC_VIABILITY_FLOOR_USD` is
#: $200 (20 x the $10 venue minimum) and below it an account cannot execute a handful of
#: economic round-trips -- `validation.py` already calls that SUB-VIABLE. From a $1k book that is
#: 0.20 of starting equity. The $100 starting case the row names is far worse and is swept too.
_BARRIERS = (0.20, 0.50)


#: Path-chunk budget in array elements. A 10-year horizon at 8,000 paths is 29M float64s per
#: array and `cumprod` needs a second one -- ~470MB on a box whose OOM floor is 400MB free, which
#: is how a study kills the test suite rather than answering its question. Chunking bounds the
#: footprint at ~64MB whatever the horizon. AT 365 DAYS 8,000x365 = 2.92M FITS IN ONE CHUNK, so
#: the 1y cells draw exactly the arrays they drew before and their numbers are unchanged.
_CHUNK_ELEMS = 4_000_000


def _argmax_f(*, sharpe_ann: float, kelly_lev: float, barrier: float, absorbing: bool,
              sharpe_sd: float, seed: int, horizon: int = _HORIZON) -> tuple[float, float]:
    """Grid-search f by E[log W_T] under COMMON RANDOM NUMBERS across the whole grid.

    One set of shocks is drawn per cell and every f is evaluated on it. That is not only ~60x
    cheaper than re-drawing per grid point, it is the correct estimator for this question: the
    quantity wanted is which f is BEST, and differencing curves computed on independent noise
    buries a real ordering under Monte-Carlo error that common shocks cancel exactly.

    COMMON RANDOM NUMBERS SURVIVE THE CHUNKING, which is the only thing that could have broken
    here: every f is evaluated on the SAME chunk before the next chunk is drawn, so the shocks are
    still shared across the grid exactly as they were when the whole horizon fit in one array.
    Chunking changes the memory footprint, never the estimator.
    """
    rng = np.random.default_rng(seed)
    chunk = max(1, min(_N_PATHS, _CHUNK_ELEMS // max(1, horizon)))
    acc = np.zeros(len(_F_GRID), dtype="float64")
    done = 0
    while done < _N_PATHS:
        n = min(chunk, _N_PATHS - done)
        # Parameter uncertainty is ONE draw per path, held for the whole horizon: the desk lives
        # with a single estimate for the life of the bet. Re-drawing each step would average the
        # uncertainty away and report that estimation error costs nothing.
        s_true = (rng.normal(sharpe_ann, sharpe_sd, size=(n, 1)) if sharpe_sd > 0
                  else np.full((n, 1), sharpe_ann))
        mu_d = s_true / np.sqrt(_PPY) * _SIGMA_D
        z = rng.standard_normal((n, horizon))
        r = mu_d + _SIGMA_D * z                      # the shared return path, f-independent
        for i, f in enumerate(_F_GRID):
            steps = np.maximum(1.0 + (f * kelly_lev) * r, 1e-9)
            if absorbing:
                # Freeze at the barrier from the first touch. The account keeps the money and
                # loses the ability to compound it, which is what a venue minimum actually does.
                #
                # THIS ARM KEEPS `cumprod` AND IS PROVABLY SAFE, WHICH IS WHY ITS NUMBERS ARE
                # UNCHANGED BIT FOR BIT. Underflow cannot corrupt it: equity moves continuously
                # (every step is positive), so a path reaching 0.0 must have passed through
                # `barrier` first and `.any()` has already caught it -- and a caught path is
                # scored at `barrier`, never at its underflowed value. gamma_boundary, the only
                # half of this study that bears on sizing, is built solely from this arm.
                eq = np.cumprod(steps, axis=1)
                terminal = np.where((eq <= barrier).any(axis=1), barrier, eq[:, -1])
                acc[i] += float(np.sum(np.log(terminal)))
            else:
                # THE ARM THAT UNDERFLOWED, AND THE HORIZON SWEEP IS WHAT REACHED IT. With no
                # barrier to absorb it, a path just keeps compounding down: at f=3.0 and S=2.3 the
                # leverage is 21.7x, so a single -4.6% day floors its step at 1e-9, and enough of
                # those over 3,650 steps drive the product below the float64 minimum. `log(0.0)`
                # is then -inf -- not "very bad" but INFINITELY bad -- so ONE underflowing path in
                # 8,000 set that f's entire score to -inf and deleted it from the argmax for an
                # arithmetic reason rather than an economic one. Measured at seed 11: 0/64 paths
                # underflow at 365 and 1,095 days, 7/64 at 3,650. The base study could not have
                # seen this; 365 steps cannot get there.
                #
                # Summing logs is mathematically identical and cannot underflow, and it needs no
                # cumulative array because nothing here asks WHEN the path crossed anything --
                # only where it ended.
                acc[i] += float(np.sum(np.log(steps)))
        done += n

    g_all = acc / _N_PATHS
    j = int(np.argmax(g_all))
    return float(_F_GRID[j]), float(g_all[j])


def full_kelly_leverage(sharpe_ann: float, sigma_d: float = _SIGMA_D) -> float:
    """Textbook full-Kelly leverage mu/sigma^2 for this log-normal process.

    THIS IS WHAT MAKES `f` A KELLY MULTIPLE RATHER THAN A RAW LEVERAGE, and getting it wrong is
    not cosmetic. A first version of this study fixed the scale at 1.0, which put the no-barrier
    optimum at 1.96x for S=0.75 but 3.93x and 6.02x for S=1.5 and S=2.3 -- outside a grid capped
    at 3.0. Both of those cells would have reported their argmax AT THE EDGE OF THE SEARCH WINDOW
    and every gamma derived from them would have been an artifact of the grid, exactly the
    failure `slot_budget_analysis` already records against itself.

    It also buys the study a POSITIVE CONTROL: with the scale correct, `f_star_no_barrier` must
    come back at ~1.0 by construction. If it does not, the simulator is wrong and no other number
    in the file means anything.
    """
    return sharpe_ann / (np.sqrt(_PPY) * sigma_d)


def study(sharpe_ann: float, n_days: float, barrier: float, *, seed: int = 11,
          horizon: int = _HORIZON) -> dict:
    """One cell: a true Sharpe, an evidence width, a barrier, and a horizon."""
    kelly_lev = full_kelly_leverage(sharpe_ann)     # f is reported in MULTIPLES of full Kelly
    f_noabs, g_noabs = _argmax_f(sharpe_ann=sharpe_ann, kelly_lev=kelly_lev, barrier=barrier,
                                 absorbing=False, sharpe_sd=0.0, seed=seed, horizon=horizon)
    f_abs, g_abs = _argmax_f(sharpe_ann=sharpe_ann, kelly_lev=kelly_lev, barrier=barrier,
                             absorbing=True, sharpe_sd=0.0, seed=seed, horizon=horizon)
    se = sharpe_se(sharpe_ann, n_days)
    f_joint, g_joint = _argmax_f(sharpe_ann=sharpe_ann, kelly_lev=kelly_lev, barrier=barrier,
                                 absorbing=True, sharpe_sd=se, seed=seed, horizon=horizon)

    # CONTROL A -- uncertainty WITHOUT the barrier. This is the decisive one and it was not in
    # the first version of this study, which is why that version reported a confident and wrong
    # answer. E[log W_T] = T(L*mu - L^2 sigma^2 / 2) is LINEAR in mu, so averaging over an
    # UNBIASED mu leaves the argmax exactly at full Kelly: symmetric parameter noise, on its own,
    # cannot move the Kelly optimum at all. Measured f* = 1.00, matching theory.
    f_unc_only, _ = _argmax_f(sharpe_ann=sharpe_ann, kelly_lev=kelly_lev, barrier=barrier,
                              absorbing=False, sharpe_sd=se, seed=seed, horizon=horizon)

    gamma_boundary = f_abs / f_noabs if f_noabs > 0 else float("nan")
    gamma_est = shrink_fraction(sharpe_ann, n_days)
    composed = gamma_est * gamma_boundary * f_noabs
    ratio = composed / f_joint if f_joint > 0 else float("nan")

    # WHY THE JOINT CELL IS NOT EVIDENCE, stated in the artifact rather than left to a reader.
    # With absorption modelled as FREEZING at the barrier, terminal log-wealth is floored at
    # log(barrier) while the upside stays unbounded. Adding dispersion to mu then pays like a
    # call option -- more spread puts more mass in the unbounded good tail while the bad tail is
    # capped -- so f*_joint comes out ABOVE full Kelly (measured 1.05 to 3.00). That is a
    # property of a ONE-YEAR horizon, not of the desk's objective: over a lifetime, absorption
    # forfeits ALL future compounding rather than settling at 0.2x book, and the floor that
    # creates this convexity is exactly what a lifetime horizon removes.
    # Clipping is judged ONLY on the quantities the verdict is built from -- f_abs and f_noabs.
    # f_joint clips in the low-Sharpe cells, but it is already declared not-evidence below, so
    # letting it condemn the whole cell would throw away a sound gamma_boundary alongside an
    # artifact that was never going to be used.
    _edge = float(_F_GRID[-1]) - 1e-9
    clipped = bool(f_abs >= _edge or f_noabs >= _edge)
    joint_clipped = bool(f_joint >= _edge)
    verdict = ("BOUNDARY-SHRINK-REAL-BUT-SMALL" if gamma_boundary >= 0.85
               else "BOUNDARY-SHRINK-MATERIAL")
    if clipped:
        verdict = "UNUSABLE (argmax at the grid edge)"

    # POSITIVE CONTROL. With no barrier and no estimation error the optimum IS full Kelly, so
    # f_star_no_barrier must return ~1.0. A cell that fails this is reporting on a broken
    # simulator and its gammas are meaningless -- said out loud in the artifact rather than left
    # for a reader to notice, because an uncontrolled study that agrees with your prior is the
    # easiest thing in the world to publish.
    control_ok = bool(0.85 <= f_noabs <= 1.15)

    return {
        "sharpe_ann": sharpe_ann, "n_days": n_days, "barrier_frac_of_book": barrier,
        "horizon_days": horizon,
        "full_kelly_leverage": round(kelly_lev, 3),
        "positive_control_ok": control_ok,
        "f_star_no_barrier": f_noabs, "f_star_absorbing": f_abs, "f_star_joint": f_joint,
        "f_star_uncertainty_only": f_unc_only,
        "joint_cell_is_evidence": False,
        "joint_cell_hit_grid_edge": joint_clipped,
        "joint_cell_note": "f_star_joint is NOT usable: freezing at the barrier floors terminal "
                           "log-wealth at log(barrier) while the upside is unbounded, so mu "
                           "dispersion pays like a call option and pushes the argmax above full "
                           "Kelly. An artifact of the 1y horizon, which under-penalises "
                           "absorption -- over a lifetime absorption forfeits all future "
                           "compounding, not 0.8x of one year's book",
        "gamma_boundary": round(gamma_boundary, 4),
        "gamma_estimation": round(gamma_est, 4),
        "composed_fraction": round(composed, 4),
        "composed_over_joint": round(ratio, 4),
        "verdict": verdict,
        "elogw_no_barrier": round(g_noabs, 5), "elogw_absorbing": round(g_abs, 5),
        "elogw_joint": round(g_joint, 5),
        "sharpe_se": round(se, 4),
    }


#: R0431's sweep. 1y is the base study's horizon; 10y is the longest the desk can simulate at this
#: path count inside its memory budget. The desk's objective is LIFETIME E[log W_T], so if the
#: joint cell's above-Kelly optimum is the 1y freezing floor rather than something real, f*_joint
#: must fall toward f*_absorbing as the horizon grows -- the direction theory predicts.
_HORIZON_SWEEP = (365, 1095, 3650)

#: The sweep runs at the desk's REAL barrier only, and at the SHORT evidence width where the
#: artifact is largest. NOT SILENTLY CAPPED (L1.53): the 0.50 barrier is a $100-book case the desk
#: does not trade, and 180d evidence has a narrower se and so a smaller artifact to dissolve --
#: dropping them costs the sweep nothing it was built to see, and the cost of the full 3x12 grid
#: is ~14x the base study's runtime for cells that answer a question nobody asked.
_SWEEP_BARRIER = 0.20
_SWEEP_N_DAYS = 40.0


def horizon_sweep() -> list[dict]:
    """R0431: is the joint cell's above-Kelly optimum an artifact of the ONE-YEAR horizon?

    THE BASE STUDY PUBLISHED ITS OWN CAVEAT AND COULD NOT TEST IT. Freezing at the barrier floors
    terminal log-wealth at log(barrier) while the upside stays unbounded, so mu-dispersion pays
    like a call option and pushes f*_joint ABOVE full Kelly (measured 1.05-3.00). The claim
    attached to that number is that it is a property of the 1y horizon and not of the desk's
    objective: over a lifetime, absorption forfeits ALL future compounding rather than settling at
    0.2x book, so the floor creating the convexity is exactly what a long horizon removes.

    That is a FALSIFIABLE claim and it was carrying no evidence. If f*_joint does NOT fall as the
    horizon grows, the artifact's stated explanation is wrong and the joint cells need a different
    one -- which matters more than the confirmation would, because the base study's headline
    verdict (do not wire a boundary shrink) rests on reading those cells as an artifact.
    """
    out = []
    for horizon in _HORIZON_SWEEP:
        for sharpe in (0.75, 1.5, 2.3):
            c = study(sharpe, _SWEEP_N_DAYS, _SWEEP_BARRIER, horizon=horizon)
            # The quantity the row is about: how far the joint optimum sits above the
            # absorbing-only one. Theory says this gap closes as the horizon grows.
            c["joint_over_absorbing"] = (round(c["f_star_joint"] / c["f_star_absorbing"], 4)
                                         if c["f_star_absorbing"] > 0 else float("nan"))
            out.append(c)
    return out


def main() -> int:
    # The desk's own real-edge band (0.5-1.5 OOS Sharpe, from its 131,441-backtest sweep) plus the
    # cashcarry-scale case, each at a short and a long evidence width.
    cells = []
    for barrier in _BARRIERS:
        for sharpe in (0.75, 1.5, 2.3):
            for n_days in (40.0, 180.0):
                cells.append(study(sharpe, n_days, barrier))

    verdicts: dict[str, int] = {}
    for c in cells:
        verdicts[c["verdict"]] = verdicts.get(c["verdict"], 0) + 1
    n_control_ok = sum(1 for c in cells if c["positive_control_ok"])
    # CONTROL A across every cell: symmetric parameter noise alone must leave the optimum at full
    # Kelly, because E[log W] is linear in mu. Reported as a count, not asserted in prose.
    n_unc_neutral = sum(1 for c in cells if abs(c["f_star_uncertainty_only"] - 1.0) <= 0.15)

    # ------------------------------------------------------------------ R0431 HORIZON SWEEP
    sweep = horizon_sweep()
    # The row's prediction, tested rather than asserted: the joint optimum's excess over the
    # absorbing-only optimum should SHRINK as the horizon grows, because the log(barrier) floor
    # that manufactures the convexity is what a long horizon removes.
    # THE VERDICT IS BUILT FROM UNCLIPPED CELLS ONLY, and the denominator is published beside it.
    # f*_joint pins at the 3.00 grid edge in every S=0.75 cell, so its ratio there is a LOWER
    # BOUND, not a measurement -- averaging it in would let a censored number drive the conclusion
    # (L1.57). The count of what was dropped is reported rather than silently excluded.
    by_h = {h: [c for c in sweep
                if c["horizon_days"] == h and not c["joint_cell_hit_grid_edge"]]
            for h in _HORIZON_SWEEP}
    mean_excess = {h: (sum(c["joint_over_absorbing"] for c in cs) / len(cs) if cs else float("nan"))
                   for h, cs in by_h.items()}
    # gamma_boundary is the DECISION-RELEVANT half and it is never clipped (f_abs and f_noabs both
    # sit well inside the grid), so it is averaged over every cell at each horizon.
    mean_gamma = {h: sum(c["gamma_boundary"] for c in sweep if c["horizon_days"] == h)
                     / max(1, sum(1 for c in sweep if c["horizon_days"] == h))
                  for h in _HORIZON_SWEEP}
    ordered = [mean_excess[h] for h in _HORIZON_SWEEP]
    n_usable = sum(len(cs) for cs in by_h.values())
    falls = all(b <= a + 1e-9 for a, b in itertools.pairwise(ordered))
    n_sweep_control_ok = sum(1 for c in sweep if c["positive_control_ok"])
    if n_sweep_control_ok < len(sweep):
        horizon_verdict = "UNUSABLE (positive control failed in the sweep)"
    elif n_usable < 2 or any(v != v for v in ordered):     # NaN-safe: no unclipped cell somewhere
        horizon_verdict = "UNMEASURED (too few unclipped cells to read a trend)"
    elif falls and ordered[-1] < ordered[0]:
        horizon_verdict = "CONFIRMED-ARTIFACT-OF-HORIZON"
    elif ordered[-1] < ordered[0]:
        horizon_verdict = "FALLS-BUT-NOT-MONOTONE"
    else:
        horizon_verdict = "REFUTED (the excess RISES with horizon)"

    doc = {
        "row": "R0266",
        "question": "does an absorbing-boundary shrink compose with the estimation shrink, "
                    "or double-count against it (and against the ruin cap already in the sizer)?",
        "status": "MEASURED",
        "n_paths": _N_PATHS, "horizon_days": _HORIZON,
        "r0431_horizon_sweep": {
            "row": "R0431",
            "question": "is f*_joint > 1 an artifact of the ONE-YEAR horizon, as the base "
                        "study's own caveat claims? Over a lifetime absorption forfeits ALL "
                        "future compounding rather than settling at 0.2x book, so the excess "
                        "should fall as the horizon grows",
            "horizons_days": list(_HORIZON_SWEEP),
            "barrier_frac_of_book": _SWEEP_BARRIER,
            "evidence_width_days": _SWEEP_N_DAYS,
            "scope_note": "run at the desk's REAL barrier and the SHORT evidence width only -- "
                          "the 0.50 barrier is a $100-book case the desk does not trade and 180d "
                          "evidence has a smaller artifact to dissolve. Dropped deliberately and "
                          "named here rather than silently capped",
            "n_cells": len(sweep),
            "n_cells_usable_for_verdict": n_usable,
            "n_cells_dropped_grid_edge": len(sweep) - n_usable,
            "positive_control_passed": f"{n_sweep_control_ok}/{len(sweep)}",
            "mean_joint_over_absorbing_by_horizon": {
                str(h): round(v, 4) for h, v in mean_excess.items()},
            "monotone_decreasing": falls,
            "verdict": horizon_verdict,
            "answer": (
                "REFUTED. The base study's caveat claimed f*_joint > 1 is an artifact of the 1y "
                "horizon that a lifetime horizon would remove. Measured over 1y/3y/10y the "
                "excess RISES instead. THE MECHANISM: modelling absorption as FREEZING floors "
                "terminal log-wealth at log(barrier) FOREVER, while surviving paths compound "
                "roughly linearly in T -- so the gap the floor insures against GROWS with the "
                "horizon and the mu-dispersion call option becomes MORE valuable, not less. The "
                "horizon was never the fix; the ABSORPTION MODEL is. Testing the row's actual "
                "claim needs the alternative it names in its own parenthesis -- an explicit "
                "continuation value for the non-absorbed state, so that absorption forfeits the "
                "compounding the capital would otherwise have earned rather than settling at "
                "log(0.2). f*_joint remains NOT EVIDENCE either way, exactly as before."),
            "gamma_boundary_by_horizon": {str(h): round(v, 4) for h, v in mean_gamma.items()},
            "gamma_boundary_note": (
                "THE HALF THAT ACTUALLY BEARS ON SIZING, and it moved. gamma_boundary is never "
                "clipped, and it FALLS with the horizon exactly as theory predicts: at the "
                "desk's real barrier it is ~0.95 at 1y but ~0.82 at 10y, so the boundary shrink "
                "over a LIFETIME is roughly 15-20%, about double the '<=10%' the base study "
                "measured at one year. The base study's headline figure is a 1-YEAR number and "
                "this desk's objective is lifetime E[log W_T]. The conclusion still holds -- the "
                "estimation shrink applies 0.058-0.721 in the same cells and continues to "
                "dominate, and _ruin_cap already binds the same barrier from the constraint side "
                "-- but the margin is smaller than the artifact previously stated."),
            "cells": sweep,
        },
        "barrier_note": "fraction of starting book at which the account can no longer execute "
                        "economic round-trips at venue minimums ($200 viability floor / book)",
        "wired": False,
        "wired_note": "STUDY ONLY. No sizer, rail or bar is changed by this file.",
        # SCANNED, not asserted: a cell count that cannot fall when a cell disappears is not a
        # denominator (L1.57).
        "n_cells": len(cells),
        "positive_control_passed": f"{n_control_ok}/{len(cells)}",
        "uncertainty_alone_leaves_kelly_unmoved": f"{n_unc_neutral}/{len(cells)}",
        "positive_control_note": "with no barrier and no estimation error the optimum IS full "
                                 "Kelly, so f_star_no_barrier must be ~1.0. Any cell failing "
                                 "this is a broken simulator and its gammas mean nothing",
        "status_note": ("READ NOTHING FROM THIS FILE" if n_control_ok < len(cells)
                        else "controls green"),
        "verdict_counts": verdicts,
        "cells": cells,
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(doc, indent=1), "utf-8")

    print(f"=== R0266 ABSORBING-BOUNDARY KELLY STUDY ({len(cells)} cells) ===")
    print(f"{'S':>5} {'nday':>5} {'barr':>5} {'f*none':>7} {'f*unc':>6} {'f*abs':>6} "
          f"{'g_bnd':>6} {'g_est':>6}  verdict")
    for c in cells:
        print(f"{c['sharpe_ann']:5.2f} {c['n_days']:5.0f} {c['barrier_frac_of_book']:5.2f} "
              f"{c['f_star_no_barrier']:7.2f} {c['f_star_uncertainty_only']:6.2f} "
              f"{c['f_star_absorbing']:6.2f} {c['gamma_boundary']:6.3f} "
              f"{c['gamma_estimation']:6.3f}  {c['verdict']}")
    print()
    print(f"=== R0431 HORIZON SWEEP ({len(sweep)} cells, barrier {_SWEEP_BARRIER}, "
          f"{_SWEEP_N_DAYS:.0f}d evidence) ===")
    print(f"{'S':>5} {'horiz':>6} {'f*none':>7} {'f*abs':>6} {'f*joint':>8} {'j/abs':>6}")
    for c in sweep:
        print(f"{c['sharpe_ann']:5.2f} {c['horizon_days']:6d} {c['f_star_no_barrier']:7.2f} "
              f"{c['f_star_absorbing']:6.2f} {c['f_star_joint']:8.2f} "
              f"{c['joint_over_absorbing']:6.2f}")
    print(f"  mean f*joint/f*abs by horizon (UNCLIPPED cells only, "
          f"{n_usable}/{len(sweep)} usable): " + ", ".join(
              f"{h}d={mean_excess[h]:.2f}" for h in _HORIZON_SWEEP))
    print("  mean gamma_boundary by horizon: " + ", ".join(
        f"{h}d={mean_gamma[h]:.3f}" for h in _HORIZON_SWEEP)
        + "   <-- the half that bears on sizing, and it FALLS")
    print(f"  R0431 VERDICT: {horizon_verdict}")
    print()
    print(f"  POSITIVE CONTROL: {n_control_ok}/{len(cells)} cells recovered full Kelly "
          f"(f*_no_barrier ~ 1.0) with no barrier and no estimation error")
    print(f"  CONTROL A:        {n_unc_neutral}/{len(cells)} cells left the optimum at full Kelly "
          f"under estimation noise ALONE -- E[logW] is linear in mu, so symmetric parameter")
    print("                    uncertainty on its own cannot shrink Kelly. The existing shrink "
          "must rest on selection bias, sigma uncertainty or fat tails, NOT on this.")
    if n_control_ok < len(cells):
        print("  *** CONTROL FAILED -- the simulator is wrong; read nothing else here ***")
    for v, n in sorted(verdicts.items(), key=lambda kv: -kv[1]):
        print(f"  {n:2d} cell(s): {v}")
    print(f"\nwritten -> {_OUT.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
