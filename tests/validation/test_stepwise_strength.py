"""MUTATION-DRIVEN STRENGTH TESTS for the per-candidate gates (gap #53).

These exist because the desk MEASURED its test strength for the first time on 2026-07-29 and
`libs/validation/stepwise.py` killed only 55% of mutants against a >=90% bar. Reading the
survivors separated two very different things, and the distinction is the point:

  EQUIVALENT MUTANTS (not test gaps -- the output genuinely cannot see them): CSCV PBO is
  RANK-based, so any rank-preserving change to the Sharpe formula is unobservable in the verdict.
  Verified directly: `(n-1) -> (n+1)` in the variance denominator and `s**2 -> s**3` both leave
  every block's candidate ORDERING identical, so `candidate_pbo` is unchanged by construction.
  No assertion on the verdict can ever kill those. What CAN kill them is asserting the Sharpe
  VALUES themselves -- which is what `test_sufficient_stat_sharpe_matches_direct` does, and it is
  worth having independently: the sufficient-statistic path is an optimisation of a formula whose
  correctness nothing else pinned.

  REAL GAPS (the suite could see them and did not look): every boundary in the input validator
  survived (`< 2` -> `<= 2` on strategy count, on n_splits, and `n_obs < n_splits` -> `<=`), i.e.
  nothing asserted that the SMALLEST legal input is accepted -- only that illegal ones raise.
  A gate that rejects its own boundary case silently shrinks the campaign it can judge. Also
  unpinned: the results models' immutability, and chunk-invariance of the split loop.
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np
import pytest

from libs.validation.errors import ValidationError
from libs.validation.stepwise import (
    _block_sufficient_stats,
    _sharpe_from_stats,
    cscv_candidate_pbo,
    romano_wolf_stepdown,
)

_RNG = np.random.default_rng(29)


def _matrix(n_obs: int = 64, n_strat: int = 6) -> np.ndarray:
    return _RNG.normal(0.0005, 0.01, (n_obs, n_strat))


class TestSharpeFromStats:
    """The sufficient-statistic Sharpe is an optimisation; its VALUES were never asserted."""

    def test_sufficient_stat_sharpe_matches_direct(self) -> None:
        m = _matrix(80, 5)
        counts, sums, sqs = _block_sufficient_stats(m, 8)
        got = _sharpe_from_stats(counts, sums, sqs)
        # Direct per-block Sharpe (ddof=1), computed the slow obvious way.
        blocks = np.array_split(np.arange(m.shape[0]), 8)
        want = np.array([[m[idx, k].mean() / m[idx, k].std(ddof=1)
                          for k in range(m.shape[1])] for idx in blocks])
        assert np.allclose(got, want, atol=1e-12), np.abs(got - want).max()

    def test_zero_variance_block_yields_zero_not_nan(self) -> None:
        # The std>0 guard: a constant block must give 0.0, never inf/nan leaking into ranks.
        counts = np.array([10.0, 10.0])
        sums = np.array([[5.0], [0.0]])
        sqs = np.array([[2.5], [0.0]])       # block 0: constant 0.5 -> var 0
        out = _sharpe_from_stats(counts, sums, sqs)
        assert np.isfinite(out).all()
        assert out[0, 0] == 0.0


class TestValidatorBoundaries:
    """Every boundary survived mutation: the suite tested rejection, never ACCEPTANCE."""

    def test_exactly_two_strategies_is_legal(self) -> None:
        res = cscv_candidate_pbo(_matrix(32, 2), n_splits=4)
        assert len(res.candidate_pbo) == 2      # `< 2` must not become `<= 2`

    def test_one_strategy_still_rejected(self) -> None:
        with pytest.raises(ValidationError):
            cscv_candidate_pbo(_matrix(32, 1), n_splits=4)

    def test_n_splits_of_two_is_legal(self) -> None:
        res = cscv_candidate_pbo(_matrix(32, 3), n_splits=2)
        assert len(res.candidate_pbo) == 3      # `n_splits < 2` must not become `<= 2`

    def test_odd_and_zero_n_splits_rejected(self) -> None:
        for bad in (0, 1, 3, 5):
            with pytest.raises(ValidationError):
                cscv_candidate_pbo(_matrix(32, 3), n_splits=bad)

    def test_n_obs_exactly_equals_n_splits_is_legal(self) -> None:
        # One observation per block is degenerate but LEGAL; `n_obs < n_splits` must not be `<=`.
        res = cscv_candidate_pbo(_matrix(4, 3), n_splits=4)
        assert len(res.candidate_pbo) == 3

    def test_fewer_obs_than_splits_rejected(self) -> None:
        with pytest.raises(ValidationError):
            cscv_candidate_pbo(_matrix(3, 3), n_splits=4)


class TestResultContracts:
    """Immutability and chunk-invariance -- both unpinned before this file existed."""

    def test_results_are_frozen(self) -> None:
        res = cscv_candidate_pbo(_matrix(48, 4), n_splits=6)
        with pytest.raises((ValueError, TypeError, AttributeError)):
            res.candidate_pbo = [0.0, 0.0, 0.0, 0.0]  # type: ignore[misc]
        sd = romano_wolf_stepdown(_matrix(48, 4))
        with pytest.raises((ValueError, TypeError, AttributeError)):
            sd.rejected = [True, True, True, True]    # type: ignore[misc]

    def test_chunking_cannot_change_the_verdict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # The chunk size is a MEMORY knob; if it ever changes a verdict that is a real defect.
        m = _matrix(64, 5)
        base = cscv_candidate_pbo(m, n_splits=8)
        import libs.validation.stepwise as sw
        real = sw._sharpe_from_stats
        calls = {"n": 0}

        def counting(*a: object, **k: object) -> np.ndarray:
            calls["n"] += 1
            return real(*a, **k)  # type: ignore[arg-type]

        monkeypatch.setattr(sw, "_sharpe_from_stats", counting)
        again = cscv_candidate_pbo(m, n_splits=8)
        assert calls["n"] >= 2                      # the split loop really did chunk
        assert np.allclose(base.candidate_pbo, again.candidate_pbo, atol=1e-12)

    def test_candidate_pbo_is_a_probability_per_candidate(self) -> None:
        res = cscv_candidate_pbo(_matrix(64, 7), n_splits=8)
        assert len(res.candidate_pbo) == 7
        assert all(0.0 <= p <= 1.0 for p in res.candidate_pbo)

    def test_stepdown_p_values_are_monotone_in_the_test_statistic(self) -> None:
        # Romano-Wolf 2016 sec. 4: adjusted p-values must be non-decreasing as the SIGNED
        # studentised statistic falls. Asserted against the statistic the function itself
        # returns, so the contract is pinned rather than a re-derivation of it (the first
        # version of this test ranked by |Sharpe| and failed for that reason -- sign matters:
        # a large-negative-mean strategy is the WORST candidate, not a strong one).
        m = np.column_stack([_RNG.normal(mu, 0.01, 200)
                             for mu in (0.003, 0.002, 0.0, 0.0, -0.003)])
        sd = romano_wolf_stepdown(m)
        order = np.argsort(-np.asarray(sd.t_stat))
        seq = [sd.adjusted_p[k] for k in order]
        assert all(b >= a - 1e-12 for a, b in pairwise(seq)), seq
