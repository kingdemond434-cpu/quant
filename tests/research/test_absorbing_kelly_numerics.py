"""R0431 regression: the horizon sweep reached a regime where `cumprod` underflows to zero.

THE DEFECT THIS PINS. `_argmax_f` scored each leverage by `log(cumprod(steps))`. At the base
study's 365-day horizon that is safe, but R0431 asked for 1,095 and 3,650-day horizons, and at
3,650 the product underflows to EXACTLY 0.0 -- `log(0.0)` is then `-inf`, which is not "very bad"
but INFINITELY bad, so a single underflowing path out of 8,000 sets that leverage's whole score to
-inf and DELETES it from the argmax for an arithmetic reason rather than an economic one.

THE CELL IS SPECIFIC, AND MEASURING IT IS WHY THIS TEST IS NARROW. Underflow needs BOTH arms of
the study's own design at once: no barrier (the absorbing arm replaces every barrier-crosser's
terminal wealth with `barrier` BEFORE the log, so it is structurally immune) and parameter
uncertainty (`sharpe_se(2.3, 40d) = 3.03` is wide enough that `s_true` draws reach -3.5, and a
path with a strongly negative drift at 21.7x leverage decays fast enough to leave float64 range).
`f_star_uncertainty_only` is the ONLY one of the four arms carrying both. Measured at seed 11:
0/64 paths underflow at 365 and 1,095 days, **7/64 at 3,650**. The base study could not have seen
this, and the sweep this row asked for is exactly what reached it.

WHY IT WAS INVISIBLE, which is the part worth keeping. The corruption lands on high-f grid points
in an arm whose optimum sits at ~1.0x, so it deleted only leverages that were never going to win,
moved no published number, and announced itself solely as a RuntimeWarning on stderr. An error
whose only symptom is a warning nobody reads is invisible by construction -- and CONTROL A's claim
("symmetric parameter noise alone cannot move the Kelly optimum") is an assertion about that arm's
grid, so it deserves an intact one.

The fix accumulates `cumsum(log(steps))`: mathematically identical, cannot underflow, and gives a
decayed path the large-but-finite log-wealth it actually has.
"""
from __future__ import annotations

import warnings

import numpy as np
import pytest

from scripts import study_absorbing_kelly as study

#: The study's own worst cell: highest Sharpe (so the widest `se` and the largest Kelly leverage),
#: shortest evidence width, longest swept horizon.
_SHARPE, _EVIDENCE_DAYS, _HORIZON = 2.3, 40.0, 3650


@pytest.fixture
def _tiny_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """64 paths, not 8,000. Underflow needs a LONG horizon, never a wide one -- 7 of 64 paths
    reproduce it at seed 11, so the regression runs in about a second."""
    monkeypatch.setattr(study, "_N_PATHS", 64)


def test_uncertainty_arm_at_long_horizon_raises_no_divide_by_zero(_tiny_paths: None) -> None:
    """THE DISCRIMINATING ASSERTION: pre-fix this raises `RuntimeWarning: divide by zero
    encountered in log`; post-fix it is silent.

    Asserting only that the RETURNED score is finite would pass against the broken code -- the
    argmax still reports a finite winner at ~1.0x while high-f grid points sit at -inf. The
    warning is the only signal that the grid was silently truncated, so the warning is what is
    pinned.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        f_star, g = study._argmax_f(
            sharpe_ann=_SHARPE, kelly_lev=study.full_kelly_leverage(_SHARPE),
            barrier=0.20, absorbing=False,
            sharpe_sd=study.sharpe_se(_SHARPE, _EVIDENCE_DAYS), seed=11, horizon=_HORIZON)
    assert np.isfinite(g)
    assert 0.0 < f_star <= float(study._F_GRID[-1])


def test_every_leverage_on_the_grid_keeps_a_finite_score(_tiny_paths: None) -> None:
    """The defect's REAL cost: a leverage deleted from the search rather than out-competed.

    Re-scores the top of the grid both ways on ONE set of shocks. The legacy arithmetic must
    actually break here -- otherwise this regression has no teeth and would pass against the bug.
    """
    rng = np.random.default_rng(11)
    kelly = study.full_kelly_leverage(_SHARPE)
    se = study.sharpe_se(_SHARPE, _EVIDENCE_DAYS)
    s_true = rng.normal(_SHARPE, se, size=(64, 1))
    mu_d = s_true / np.sqrt(study._PPY) * study._SIGMA_D
    r = mu_d + study._SIGMA_D * rng.standard_normal((64, _HORIZON))
    steps_top = np.maximum(1.0 + (float(study._F_GRID[-1]) * kelly) * r, 1e-9)

    # TEETH: the legacy path genuinely underflows in this cell, so the fix is load-bearing.
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        legacy_terminal = np.cumprod(steps_top, axis=1)[:, -1]
    assert (legacy_terminal == 0.0).any(), "cell no longer underflows -- regression lost its teeth"

    # THE FIX: same quantity, accumulated in log space, finite for every path on the grid.
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        scores = [float(np.sum(np.cumsum(
            np.log(np.maximum(1.0 + (float(f) * kelly) * r, 1e-9)), axis=1)[:, -1]))
            for f in study._F_GRID]
    assert all(np.isfinite(s) for s in scores), "a leverage was deleted from the grid, not beaten"


def test_absorbing_arm_was_never_the_underflowing_one(_tiny_paths: None) -> None:
    """Pins the REASON the corruption never moved a published number, so a future reader does not
    rediscover the warning and assume the headline `gamma_boundary` was an artifact.

    The absorbing arm replaces a barrier-crosser's terminal wealth with `barrier` itself, and an
    underflowing path is certainly a crosser, so its log is log(0.2) -- finite at any horizon.
    `gamma_boundary` is built only from absorbing-arm optima and was never at risk.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        _f, g = study._argmax_f(
            sharpe_ann=_SHARPE, kelly_lev=study.full_kelly_leverage(_SHARPE),
            barrier=0.20, absorbing=True,
            sharpe_sd=study.sharpe_se(_SHARPE, _EVIDENCE_DAYS), seed=11, horizon=_HORIZON)
    assert np.isfinite(g)
    assert g >= np.log(0.20) - 1e-9, "absorbed paths cannot score below the barrier they froze at"
