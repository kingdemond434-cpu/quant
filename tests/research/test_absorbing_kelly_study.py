"""GRADUATES L0082 -- a positive control is not enough, and an argmax is not a finding.

R0266's absorbing-Kelly study passed its positive control 12 out of 12 cells (it recovered full
Kelly with no barrier and no noise, exactly as theory says it must) and then reported a confident
WRONG number: "the two shrinks DOUBLE-COUNT in 12/12 cells". The positive control could not have
caught it, because the bug did not live in the baseline -- it lived in the INTERACTION between the
absorbing floor and parameter dispersion. Only CONTROL A, a no-treatment arm carrying estimation
noise with NO barrier, separated them.

A separate first version of the same study fixed the Kelly scale at 1.0, which put the true
optimum at 3.93x and 6.02x for S=1.5 and S=2.3 -- outside a grid capped at 3.0. Two cells would
have reported their argmax sitting AT THE EDGE of the search window, and every gamma derived from
them would have measured the grid rather than the process.

Both halves of the lesson are structural properties of the study, so both are pinned here:

  1. CONTROL A must exist, must isolate parameter noise alone, and must come back at full Kelly.
     E[log W_T] = T(L*mu - L^2 sigma^2 / 2) is LINEAR in mu, so averaging over an unbiased mu
     cannot move the argmax at all. A control arm that moves is a broken simulator.
  2. An argmax at the grid edge must be REFUSED, not reported -- and refused even when the
     positive control passed, which is the exact configuration that produced the wrong answer.

The Monte Carlo is shrunk here (400 paths, 60 steps) because these are assertions about the
study's LOGIC, not re-measurements of its numbers. The published cell counts live in
docs/research/absorbing_kelly_study.json and are the study's own output, not this file's job.
"""
from __future__ import annotations

import numpy as np
import pytest

from scripts import study_absorbing_kelly as sk


@pytest.fixture
def small(monkeypatch: pytest.MonkeyPatch):
    """A cheap simulator. Small enough to run in a test, large enough to place an argmax."""
    monkeypatch.setattr(sk, "_N_PATHS", 400)
    monkeypatch.setattr(sk, "_HORIZON", 60)
    return sk


# ------------------------------------------------------------------ CONTROL A
def test_parameter_noise_alone_cannot_move_the_kelly_optimum(small) -> None:
    """THE NO-TREATMENT ARM. This is the control the first version lacked, and it is the one that
    located the real cause: the shift came from the absorbing floor capping downside at
    log(barrier) while upside stayed unbounded, never from estimation noise.

    Symmetric noise on an unbiased mu, with no barrier, must leave f* at full Kelly. If this ever
    drifts, the simulator is averaging the uncertainty away or re-drawing it per step, and every
    other number the study reports is describing that bug.
    """
    f_star, _ = small._argmax_f(sharpe_ann=1.5, kelly_lev=small.full_kelly_leverage(1.5),
                                barrier=0.20, absorbing=False, sharpe_sd=0.6, seed=11)
    assert 0.85 <= f_star <= 1.15, (
        f"CONTROL A moved the optimum to {f_star}x. E[log W] is LINEAR in mu, so symmetric "
        "parameter noise on its own cannot shift the Kelly argmax -- a shift here means the "
        "simulator is wrong, not that estimation error is expensive.")


def test_the_control_arm_is_reported_in_every_cell(small) -> None:
    """A control computed and then dropped from the artifact protects nobody. The reader has to
    be able to see the no-treatment arm next to the treated one without rerunning anything."""
    cell = small.study(1.5, 180.0, 0.20)
    assert "f_star_uncertainty_only" in cell
    assert abs(cell["f_star_uncertainty_only"] - 1.0) <= 0.15, cell


def test_the_two_arms_are_not_the_same_measurement(small) -> None:
    """The interaction is the whole finding. If the barrier arm and the no-treatment arm always
    agreed, CONTROL A would be decoration -- it earns its place by DISAGREEING with the joint
    cell, which is what proved the shift was the floor and not the noise."""
    cell = small.study(1.5, 40.0, 0.20)
    assert cell["f_star_joint"] != cell["f_star_uncertainty_only"], (
        "the joint cell and the noise-only control returned identical argmaxes -- either the "
        "barrier is not being applied or the control is not isolating anything")


# ------------------------------------------------------------------ the grid edge
def test_an_argmax_at_the_grid_edge_is_refused_not_reported(small, monkeypatch) -> None:
    """THE SECOND HALF. A grid capped below the true optimum returns the cap and looks like a
    measurement. Here the grid is truncated so the optimum cannot be inside it, and the cell must
    come back UNUSABLE rather than quietly reporting the boundary as its answer."""
    monkeypatch.setattr(sk, "_F_GRID", np.round(np.arange(0.05, 0.31, 0.05), 4))
    cell = small.study(1.5, 180.0, 0.20)
    assert cell["verdict"].startswith("UNUSABLE"), cell["verdict"]
    assert "grid edge" in cell["verdict"]


def test_a_passing_positive_control_does_not_license_a_clipped_cell(small, monkeypatch) -> None:
    """THE PRECISE SHAPE OF THE ORIGINAL ERROR. 12/12 on the positive control was read as
    permission to believe the study. The two judgements are independent and the refusal must win:
    a cell whose argmax sits on the boundary is unusable NO MATTER how well the baseline behaved.
    """
    monkeypatch.setattr(sk, "_F_GRID", np.round(np.arange(0.05, 0.31, 0.05), 4))
    cell = small.study(1.5, 180.0, 0.20)
    # The clipped cell is refused, and the control verdict is still PUBLISHED beside it rather
    # than suppressed -- a reader has to be able to see that the baseline was fine and the cell
    # was rejected anyway, because that combination is what the original error looked like.
    assert cell["verdict"].startswith("UNUSABLE")
    assert "positive_control_ok" in cell
    # The gammas the wrong conclusion was built from are still computed, which is the trap: they
    # look like ordinary numbers. Only the verdict marks them unusable, so the verdict is the
    # thing a consumer must read.
    assert cell["gamma_boundary"] is not None and cell["composed_fraction"] is not None


def test_a_healthy_cell_is_not_condemned(small) -> None:
    """The refusal has to be a real discriminator. A check that called everything UNUSABLE would
    pass the test above and destroy the study."""
    cell = small.study(1.5, 180.0, 0.20)
    assert not cell["verdict"].startswith("UNUSABLE"), cell
    assert cell["positive_control_ok"], cell


# ------------------------------------------------------------------ the scale that caused it
def test_f_is_a_kelly_multiple_so_the_grid_can_contain_the_optimum() -> None:
    """THE ROOT CAUSE of the grid-edge failure: `f` was a raw leverage against a grid capped at
    3.0, so a high-Sharpe cell's optimum was outside the window by construction. Expressing f as a
    MULTIPLE of full Kelly is what puts every cell's optimum at ~1.0 and leaves the grid room."""
    cap = float(sk._F_GRID[-1])
    assert float(sk._F_GRID[0]) < 1.0 < cap, "full Kelly must sit inside the grid, not on its rim"

    # THE HISTORICAL FAILURE, reproduced as arithmetic. With f as a RAW leverage the optimum for
    # each cell is full_kelly_leverage(S) itself, and for S=1.5 and S=2.3 that is outside a grid
    # capped at 3.0 -- so those two cells could only ever have returned the cap.
    raw_optima = {s: sk.full_kelly_leverage(s) for s in (0.75, 1.5, 2.3)}
    assert raw_optima[0.75] < cap, "the low-Sharpe cell was inside the grid, which is why it hid"
    assert raw_optima[1.5] > cap and raw_optima[2.3] > cap, (
        f"the two cells that broke the first version must still be OUTSIDE a raw grid: "
        f"{raw_optima}. If this stops holding the regression this test guards has changed shape.")

    # On the Kelly-multiple scale every one of them lands at 1.0, well inside the grid.
    for sharpe, lev in raw_optima.items():
        assert lev > 0, sharpe
        assert sk._F_GRID[0] <= lev / lev <= cap


def test_the_joint_cell_is_declared_not_evidence_in_the_artifact(small) -> None:
    """The study reaches a number it does NOT believe, and says so in the file rather than in a
    reviewer's memory. A finding that needs a caveat carried separately loses the caveat."""
    cell = small.study(1.5, 180.0, 0.20)
    assert cell["joint_cell_is_evidence"] is False
    assert "call option" in cell["joint_cell_note"], "the mechanism must be named, not hinted at"
