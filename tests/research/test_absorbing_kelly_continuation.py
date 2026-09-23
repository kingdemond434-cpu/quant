"""R0576: absorption scored as a FORFEITED GROWTH RATE, and why the row's own fix is refuted.

WHAT THESE PIN, AND WHY THE REFUTATION NEEDS PINNING AS HARD AS A FIX WOULD. R0576 asked for the
joint cell's above-Kelly optimum to be dissolved by re-scoring absorption -- score an absorbed path
at a growth rate of ZERO FOREVER instead of banking `log(barrier)`, so that P(absorb) enters the
objective directly and pushes f* DOWN. It was implemented and it moves f* the WRONG WAY, for a
reason that is one line of arithmetic: `log(0.2) = -1.609`, so "zero forever" is STRICTLY MORE
GENEROUS to absorption than the constant it replaces.

A refuted result is worth more test surface than a confirmed one here, because the next reader's
instinct will be that the fix "obviously" tightens and that the code must be wrong. These tests
make the direction a measured, reproducible fact rather than a claim in a docstring.

The decisive diagnostic (`se_convergence`) gets its own test: the joint cell collapses onto the
absorbing-only optimum as the Sharpe SE falls, which is what identifies it as a pure
parameter-uncertainty effect -- neither the horizon (R0431, refuted) nor the absorbed-state scoring
(R0576, refuted).
"""
from __future__ import annotations

import math

import pytest

from scripts import study_absorbing_kelly as study


@pytest.fixture
def _tiny_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the grid and the estimator honest but cut the path count -- these tests are about
    DIRECTION and invariants, not about reproducing the artifact's published numbers."""
    monkeypatch.setattr(study, "_N_PATHS", 400)


def test_absorbed_path_scores_higher_under_the_growth_rate_objective() -> None:
    """THE WHOLE REFUTATION IN ONE ASSERTION, and it needs no simulation.

    The terminal objective books an absorbed path at log(barrier); the growth-rate objective books
    it at zero. The barrier is a FRACTION of the starting book, so its log is NEGATIVE -- which
    makes R0576's replacement a smaller penalty, not a larger one. Any future reader who expects
    the continuation value to tighten sizing should start here.
    """
    growth_rate_score = 0.0        # R0576: an absorbed path earns zero forever
    for barrier in study._BARRIERS:
        assert 0.0 < barrier < 1.0
        terminal_score = math.log(barrier)
        assert terminal_score < 0.0, "a barrier below the starting book must have a negative log"
        assert growth_rate_score > terminal_score, (
            f"barrier {barrier}: R0576 replaces {terminal_score:.4f} with {growth_rate_score} -- "
            "the replacement is the MORE generous score, which is why f* rises rather than falls")


def test_growth_rate_objective_does_not_lower_the_optimum(_tiny_paths: None) -> None:
    """The measured direction: f*_continuation >= f*_terminal, cell by cell.

    Pinned as `>=` rather than `>` because the low-Sharpe cells pin at the 3.00 grid edge under
    both objectives and cannot separate there -- a strict inequality would fail on a censored
    number rather than on the effect (L1.57).
    """
    for sharpe in (1.5, 2.3):
        kelly_lev = study.full_kelly_leverage(sharpe)
        se = study.sharpe_se(sharpe, 40.0)
        common = {"sharpe_ann": sharpe, "kelly_lev": kelly_lev,
                  "barrier": study._SWEEP_BARRIER, "seed": 11, "horizon": 365}
        f_term, _ = study._argmax_f(absorbing=True, sharpe_sd=se, objective="terminal", **common)
        f_cont, _ = study._argmax_f(absorbing=True, sharpe_sd=se, objective="growth_rate",
                                    **common)
        assert f_cont >= f_term - 1e-9, (
            f"S={sharpe}: the continuation value LOWERED the optimum "
            f"({f_term} -> {f_cont}); R0576's refutation would need re-measuring")


def test_no_barrier_positive_control_survives_both_objectives(_tiny_paths: None) -> None:
    """With no barrier NOTHING is absorbed, so the growth-rate score is a positive monotone
    transform of the terminal one and the argmax must be IDENTICAL -- not merely close.

    This is the study's positive control (f* ~ full Kelly) carried into the new objective for free,
    which is the point: it keeps the control a single thing to trust rather than two.
    """
    for sharpe in (0.75, 2.3):
        kelly_lev = study.full_kelly_leverage(sharpe)
        common = {"sharpe_ann": sharpe, "kelly_lev": kelly_lev, "barrier": study._SWEEP_BARRIER,
                  "absorbing": False, "sharpe_sd": 0.0, "seed": 11, "horizon": 365}
        f_term, _ = study._argmax_f(objective="terminal", **common)
        f_cont, _ = study._argmax_f(objective="growth_rate", **common)
        assert f_term == f_cont, "a monotone transform moved the argmax -- the estimator is wrong"
        assert 0.85 <= f_cont <= 1.15, "positive control: no barrier, no noise => full Kelly"


def test_terminal_objective_is_the_default_and_is_unchanged(_tiny_paths: None) -> None:
    """The published numbers all come from the terminal arm, so the default must stay terminal.

    An `objective=` parameter whose default silently changed would rewrite every figure in
    docs/research/absorbing_kelly_study.json without touching a single call site.
    """
    common = {"sharpe_ann": 1.5, "kelly_lev": study.full_kelly_leverage(1.5),
              "barrier": 0.20, "absorbing": True, "sharpe_sd": 0.0, "seed": 11, "horizon": 365}
    assert study._argmax_f(**common) == study._argmax_f(objective="terminal", **common)


def test_unknown_objective_is_refused_rather_than_silently_defaulted() -> None:
    """A typo'd objective must raise, never fall through to `terminal` and publish a number under
    the wrong label -- the refusal path L1.41 requires of anything built here."""
    with pytest.raises(ValueError, match="unknown objective"):
        study._argmax_f(sharpe_ann=1.5, kelly_lev=1.0, barrier=0.2, absorbing=True,
                        sharpe_sd=0.0, seed=11, objective="time_average")


def test_absorption_probability_rises_with_leverage(_tiny_paths: None) -> None:
    """The mechanism R0576 wanted to exploit is real even though the fix built on it fails:
    P(absorb) IS increasing in f. The row's error was in the scoring, not in this."""
    absorb: dict[float, float] = {}
    study._argmax_f(sharpe_ann=1.5, kelly_lev=study.full_kelly_leverage(1.5), barrier=0.20,
                    absorbing=True, sharpe_sd=study.sharpe_se(1.5, 40.0), seed=11,
                    horizon=365, objective="growth_rate", absorb_out=absorb)
    lo = absorb[min(absorb)]
    hi = absorb[max(absorb)]
    assert hi > lo, "absorption must be more likely at higher leverage"
    assert 0.0 <= lo <= 1.0 and 0.0 <= hi <= 1.0, "a probability left [0, 1]"


def test_se_convergence_collapses_the_joint_cell_onto_the_absorbing_one(_tiny_paths: None) -> None:
    """THE DIAGNOSTIC THAT RETIRED BOTH ROWS. Hold horizon and barrier fixed, widen the evidence
    window so the Sharpe SE falls, and the joint optimum must fall toward the absorbing-only one.

    Asserted as a trend between the narrowest and widest window rather than as a fixed value, so
    the test pins the MECHANISM (it is a function of the SE) and not a Monte-Carlo draw.
    """
    sharpe, kelly_lev = 1.5, study.full_kelly_leverage(1.5)
    common = {"sharpe_ann": sharpe, "kelly_lev": kelly_lev, "barrier": study._SWEEP_BARRIER,
              "absorbing": True, "seed": 11, "horizon": 365}
    f_abs, _ = study._argmax_f(sharpe_sd=0.0, **common)
    f_narrow, _ = study._argmax_f(sharpe_sd=study.sharpe_se(sharpe, 40.0), **common)
    f_wide, _ = study._argmax_f(sharpe_sd=study.sharpe_se(sharpe, 36500.0), **common)
    assert f_narrow > f_abs, "a wide SE must lift the joint optimum above the absorbing-only one"
    assert f_wide <= f_narrow, "shrinking the SE must not RAISE the joint optimum"
    assert abs(f_wide - f_abs) <= abs(f_narrow - f_abs), (
        "as the SE shrinks the joint optimum must move TOWARD the absorbing-only optimum -- "
        "that convergence is what identifies the cell as a parameter-uncertainty effect")
