"""Register #71 -- the gate that could not promote, and the fix that does not relax it.

THE DEFECT. `campaign_pbo_rc` computes White's Reality Check and PBO once per campaign and hands
the result to every candidate. Both are properties of the SET: RC asks "is the BEST strategy here
real?", PBO asks "does the SELECTION PROCEDURE overfit?". Measured on this desk, campaign PBO
0.6159 and RC p 0.4220 made both gates False for all 420 candidates regardless of individual
merit, while every per-candidate gate discriminated normally. A promotion path that cannot promote
makes every research hour downstream of it worthless.

IT FAILS THE OTHER WAY TOO, and that direction is worse: plant ONE real edge among nineteen noise
strategies and campaign RC returns p=0.003, passing the reality_check gate for all twenty. The
campaign statistic is not merely harsh, it is uninformative about any individual.

THE FIX IS NOT RANK-NOT-VETO. The register filed #71 "not self-fixable" because downgrading a veto
to a ranking lowers the bar, which constitution point 5 forbids. Romano-Wolf stepdown and
per-strategy CSCV keep the veto and make it DISCRIMINATE -- these are the textbook per-hypothesis
methods, and they still correct for the full family.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.autodiscovery.validation import validate
from libs.validation.errors import ValidationError
from libs.validation.per_candidate import per_candidate_pbo, romano_wolf
from libs.validation.reality_check import whites_reality_check


def _planted(t: int = 800, n: int = 20, edge_at: int = 7, edge: float = 0.0015, seed: int = 0):
    """Nineteen pure-noise strategies and one with a real, modest edge."""
    rng = np.random.default_rng(seed)
    m = rng.normal(0, 0.01, (t, n))
    m[:, edge_at] += edge
    return m


# ------------------------------------------------------------------ the defect, demonstrated


def test_the_campaign_statistic_passes_NOISE_when_one_peer_is_good() -> None:
    """The failure direction nobody noticed, because it never showed up as a rejection. One
    genuine edge drags the campaign p-value under 0.05 and every noise strategy in the set
    inherits the pass. A gate that clears nineteen coin flips is not a gate."""
    m = _planted()
    rc = whites_reality_check(m)
    assert rc.p_value < 0.05, "fixture must contain a detectable edge for the point to hold"
    # ...and that single verdict was handed to all 20 candidates, 19 of which are noise.


def test_romano_wolf_rejects_the_real_one_and_only_the_real_one() -> None:
    """THE LOAD-BEARING TEST. Per-candidate adjusted p-values, family-wise error still controlled:
    the planted edge is significant, the nineteen noise strategies are not."""
    m = _planted()
    r = romano_wolf(m)
    assert r.significant(7), f"planted edge missed, p_adj={r.p_for(7):.4f}"
    noise = [k for k in range(m.shape[1]) if k != 7]
    assert sum(r.significant(k) for k in noise) == 0, "noise cleared the multiple-testing bar"
    assert r.n_rejected == 1


def test_adjusted_p_values_are_monotone_down_the_ordering() -> None:
    """The monotonicity is what keeps the family-wise guarantee valid -- a weaker candidate may
    never carry a smaller adjusted p-value than a stronger one."""
    m = _planted()
    r = romano_wolf(m)
    stat_order = np.argsort(-m.mean(axis=0))
    p_in_order = [r.p_for(k) for k in stat_order]
    assert p_in_order == sorted(p_in_order), p_in_order


def test_per_candidate_pbo_separates_the_robust_from_the_flattered() -> None:
    """A strategy whose backtest flatters it ranks high in-sample and low out-of-sample. The real
    edge should do neither; noise should do it at chance."""
    m = _planted()
    pc = per_candidate_pbo(m)
    noise_mean = float(np.mean([pc.pbo_for(k) for k in range(m.shape[1]) if k != 7]))
    assert pc.pbo_for(7) < noise_mean
    assert not pc.overfit(7)


def test_the_statistics_are_computed_ONCE_for_the_whole_matrix() -> None:
    """Both are vectorised across strategies, so the campaign pays one bootstrap pass and indexes
    per candidate. The first draft called them inside the candidate loop -- O(N^2), and at the 420
    candidates that motivated this fix it would have been unusable. The campaign version's SPEED
    argument was always right; only its statistic was wrong."""
    m = _planted(n=40)
    r, pc = romano_wolf(m), per_candidate_pbo(m)
    assert len(r.p_adjusted) == 40 and len(pc.pbo) == 40


def test_pbo_no_longer_moves_with_CAMPAIGN_SIZE() -> None:
    """Campaign PBO rises with the number of candidates tested, so the bar tightened every time
    the desk generated more -- which TWO_STAGE_DISCOVERY_LAW explicitly forbids. A per-candidate
    score must be stable when peers are merely ADDED around it."""
    small = _planted(n=6, edge_at=2)
    big = np.column_stack([small, np.random.default_rng(1).normal(0, 0.01, (small.shape[0], 30))])
    a = per_candidate_pbo(small).pbo_for(2)
    b = per_candidate_pbo(big).pbo_for(2)
    assert abs(a - b) < 0.35, f"candidate PBO moved {a:.3f} -> {b:.3f} on peers alone"


# ------------------------------------------------------------------ the gate end to end


def test_the_promotion_path_can_now_PROMOTE() -> None:
    """The whole point of #71. With per-candidate statistics a genuine edge survives the full
    gate; before this it could not, whatever its merit."""
    m = _planted()
    hyp = SimpleNamespace(failure_modes=["regime shift", "crowding"], family="ict")
    sh = np.array([r.mean() / max(r.std(), 1e-9) for r in m.T])
    v = validate(m[:, 7], hypothesis=hyp, periods_per_year=365.0, n_trials=m.shape[1],
                 sharpe_estimates=sh, returns_matrix=m,
                 pc_pbo=per_candidate_pbo(m).pbo_for(7), pc_p=romano_wolf(m).p_for(7))
    assert v.gates["pbo"] and v.gates["reality_check"]
    assert v.survived, v.rejection_reason


def test_noise_still_dies_at_the_same_gate() -> None:
    """STRICTNESS PRESERVED, and this is the test that proves the fix is not a relaxation. If the
    change had merely loosened the bar, this would pass too."""
    m = _planted()
    hyp = SimpleNamespace(failure_modes=["regime shift"], family="ict")
    sh = np.array([r.mean() / max(r.std(), 1e-9) for r in m.T])
    v = validate(m[:, 3], hypothesis=hyp, periods_per_year=365.0, n_trials=m.shape[1],
                 sharpe_estimates=sh, returns_matrix=m,
                 pc_pbo=per_candidate_pbo(m).pbo_for(3), pc_p=romano_wolf(m).p_for(3))
    assert not v.gates["reality_check"]
    assert not v.survived


def test_omitting_the_per_candidate_values_keeps_the_old_campaign_behaviour() -> None:
    """Backward compatible on purpose: a caller that has not been updated gets exactly what it got
    before, rather than silently switching statistics underneath it."""
    m = _planted()
    hyp = SimpleNamespace(failure_modes=["x"], family="ict")
    sh = np.array([r.mean() / max(r.std(), 1e-9) for r in m.T])
    v = validate(m[:, 7], hypothesis=hyp, periods_per_year=365.0, n_trials=m.shape[1],
                 sharpe_estimates=sh, returns_matrix=m)
    assert v.metrics.reality_p == pytest.approx(whites_reality_check(m).p_value, abs=0.05)


def test_degenerate_inputs_are_refused_not_guessed() -> None:
    with pytest.raises(ValidationError):
        per_candidate_pbo(np.zeros((100, 1)))
    with pytest.raises(ValidationError):
        romano_wolf(np.zeros(10))
