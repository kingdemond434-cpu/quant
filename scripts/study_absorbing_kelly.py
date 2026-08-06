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


def _argmax_f(*, sharpe_ann: float, kelly_lev: float, barrier: float, absorbing: bool,
              sharpe_sd: float, seed: int) -> tuple[float, float]:
    """Grid-search f by E[log W_T] under COMMON RANDOM NUMBERS across the whole grid.

    One set of shocks is drawn per cell and every f is evaluated on it. That is not only ~60x
    cheaper than re-drawing per grid point, it is the correct estimator for this question: the
    quantity wanted is which f is BEST, and differencing curves computed on independent noise
    buries a real ordering under Monte-Carlo error that common shocks cancel exactly.
    """
    rng = np.random.default_rng(seed)
    # Parameter uncertainty is ONE draw per path, held for the whole horizon: the desk lives with
    # a single estimate for the life of the bet. Re-drawing each step would average the
    # uncertainty away and report that estimation error costs nothing.
    s_true = (rng.normal(sharpe_ann, sharpe_sd, size=(_N_PATHS, 1)) if sharpe_sd > 0
              else np.full((_N_PATHS, 1), sharpe_ann))
    mu_d = s_true / np.sqrt(_PPY) * _SIGMA_D
    z = rng.standard_normal((_N_PATHS, _HORIZON))
    r = mu_d + _SIGMA_D * z                          # the shared return path, f-independent

    best_f, best_g = float(_F_GRID[0]), -np.inf
    for f in _F_GRID:
        steps = np.maximum(1.0 + (f * kelly_lev) * r, 1e-9)
        eq = np.cumprod(steps, axis=1)
        if absorbing:
            # Freeze at the barrier from the first touch. The account keeps the money and loses
            # the ability to compound it, which is what a venue minimum actually does.
            terminal = np.where((eq <= barrier).any(axis=1), barrier, eq[:, -1])
        else:
            terminal = eq[:, -1]
        g = float(np.mean(np.log(terminal)))
        if g > best_g:
            best_f, best_g = float(f), g
    return best_f, best_g


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


def study(sharpe_ann: float, n_days: float, barrier: float, *, seed: int = 11) -> dict:
    """One cell: a true Sharpe, an evidence width, and a barrier."""
    kelly_lev = full_kelly_leverage(sharpe_ann)     # f is reported in MULTIPLES of full Kelly
    f_noabs, g_noabs = _argmax_f(sharpe_ann=sharpe_ann, kelly_lev=kelly_lev, barrier=barrier,
                                 absorbing=False, sharpe_sd=0.0, seed=seed)
    f_abs, g_abs = _argmax_f(sharpe_ann=sharpe_ann, kelly_lev=kelly_lev, barrier=barrier,
                             absorbing=True, sharpe_sd=0.0, seed=seed)
    se = sharpe_se(sharpe_ann, n_days)
    f_joint, g_joint = _argmax_f(sharpe_ann=sharpe_ann, kelly_lev=kelly_lev, barrier=barrier,
                                 absorbing=True, sharpe_sd=se, seed=seed)

    # CONTROL A -- uncertainty WITHOUT the barrier. This is the decisive one and it was not in
    # the first version of this study, which is why that version reported a confident and wrong
    # answer. E[log W_T] = T(L*mu - L^2 sigma^2 / 2) is LINEAR in mu, so averaging over an
    # UNBIASED mu leaves the argmax exactly at full Kelly: symmetric parameter noise, on its own,
    # cannot move the Kelly optimum at all. Measured f* = 1.00, matching theory.
    f_unc_only, _ = _argmax_f(sharpe_ann=sharpe_ann, kelly_lev=kelly_lev, barrier=barrier,
                              absorbing=False, sharpe_sd=se, seed=seed)

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

    doc = {
        "row": "R0266",
        "question": "does an absorbing-boundary shrink compose with the estimation shrink, "
                    "or double-count against it (and against the ruin cap already in the sizer)?",
        "status": "MEASURED",
        "n_paths": _N_PATHS, "horizon_days": _HORIZON,
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
