"""The robust E[log W] allocator's load-bearing properties.

Each test here fences a defect that was MEASURED on the real 109-sleeve matrix while this module
was being wired, not a property that merely sounds desirable.
"""
from __future__ import annotations

import numpy as np
import pytest

from libs.portfolio.robust_elog import (
    SleeveEvidence,
    WorldConfig,
    marginal_delta_elog,
    optimise,
    project_capped_simplex,
    sample_worlds,
)


def _sleeve(name: str, mu: float, sd: float, n: int = 600, seed: int = 0,
            activity: float = 0.2, **kw: object) -> SleeveEvidence:
    """A sleeve that is FLAT most days, like every real one.

    A session sleeve trades when its bracket triggers -- measured on the live matrix, between 1
    and 2,105 active days out of 2,370, median 204. Synthetic sleeves that trade every day make a
    20% book genuinely ruinous, so a test built on them measures the fixture, not the allocator.
    """
    rng = np.random.default_rng(seed)
    r = rng.normal(mu / activity, sd, n) * (rng.random(n) < activity)
    return SleeveEvidence(name=name, daily_r=r, **kw)  # type: ignore[arg-type]


CFG = WorldConfig(n_worlds=48, n_rows=128, seed=3)


# --------------------------------------------------------------------------- the heat constraint

def test_projection_respects_cap_and_nonnegativity() -> None:
    v = np.array([0.4, -0.2, 0.1, 0.9])
    h = project_capped_simplex(v, 0.3)
    assert (h >= 0).all()
    assert h.sum() <= 0.3 + 1e-9


def test_projection_leaves_a_feasible_point_alone() -> None:
    """`exact=False` is pure growth: a book that wants less than the cap KEEPS less than the cap."""
    v = np.array([0.05, 0.02, 0.0])
    assert np.allclose(project_capped_simplex(v, 0.3), v)


def test_exact_projection_spends_the_whole_budget() -> None:
    """The full-utilisation mandate: sum == cap even when the input wants far less."""
    v = np.array([0.01, 0.002, 0.0, 0.0])
    h = project_capped_simplex(v, 0.20, exact=True)
    assert h.sum() == pytest.approx(0.20, abs=1e-9)
    assert (h >= 0).all()


def test_per_sleeve_bound_is_honoured_under_the_mandate() -> None:
    """MEASURED 2026-09-02: with no bound, a forced 20% put 14.4 points into ONE near-cash sleeve.

    The bound is what makes the mandate spend on the book rather than on the flattest row.
    """
    v = np.array([9.0, 0.01, 0.01, 0.01, 0.01])
    ub = np.full(5, 0.05)
    h = project_capped_simplex(v, 0.20, exact=True, upper=ub)
    assert h.sum() == pytest.approx(0.20, abs=1e-9)
    assert h.max() <= 0.05 + 1e-9
    assert (h > 1e-6).sum() >= 4, "a bounded mandate must fund more than one sleeve"


def test_exact_projection_refuses_a_budget_the_bounds_cannot_fund() -> None:
    """Silently under-spending a mandate would read exactly like a mandate that was honoured."""
    with pytest.raises(ValueError, match="below the mandated"):
        project_capped_simplex(np.ones(3), 0.30, exact=True, upper=np.full(3, 0.05))


# ------------------------------------------------------------------ posterior and world sampling

def test_posterior_shrinks_the_lucky_backtest_toward_no_edge() -> None:
    """A sleeve reaches the matrix BECAUSE it measured well; the prior is that it has no edge.

    Two sleeves with the same sample mean and the same noise, one with 40 observations and one
    with 4,000: the short one must be pulled much harder toward zero, or the allocator's largest
    position ends up in its luckiest backtest.
    """
    short = _sleeve("short", 0.10, 1.0, n=40, seed=1)
    long_ = _sleeve("long", 0.10, 1.0, n=4000, seed=2)
    w = sample_worlds([short, long_], WorldConfig(n_worlds=400, n_rows=64, seed=5))
    assert abs(float(w.mu_draws[:, 0].mean())) < abs(float(w.mu_draws[:, 1].mean()))


def test_crisis_worlds_exist_and_are_worse() -> None:
    ev = [_sleeve("a", 0.05, 1.0, seed=1), _sleeve("b", 0.05, 1.0, seed=2)]
    w = sample_worlds(ev, WorldConfig(n_worlds=200, n_rows=128, crisis_prob=0.25, seed=11))
    assert 0 < int(w.crisis.sum()) < w.n_worlds
    calm = w.r[~w.crisis].std()
    storm = w.r[w.crisis].std()
    assert storm > calm, "a crisis world must be more volatile than a calm one"


def test_regime_worlds_carry_no_mean_advantage() -> None:
    """THE 3,862%-A-YEAR BUG. Regime labels come from the same series as the returns, so a
    regime selected for having gone up hands the optimiser a book that wins by construction.

    Here regime "up" is literally the up days. A regime-conditioned population must NOT have a
    higher mean than an unconditioned one -- it may only differ in shape.
    """
    rng = np.random.default_rng(0)
    r = rng.normal(0.02, 1.0, 800)
    labels = tuple("up" if x > 0 else "down" for x in r)
    ev = [SleeveEvidence(name="s", daily_r=r)]
    plain = sample_worlds(ev, WorldConfig(n_worlds=120, n_rows=200, seed=4))
    tilted = sample_worlds(ev, WorldConfig(n_worlds=120, n_rows=200, seed=4,
                                           regime_labels=labels,
                                           regime_probs=(("up", 1.0),), regime_min_days=50))
    assert tilted.regimes and set(tilted.regimes) == {"up"}, "regime conditioning did not engage"
    assert float(tilted.r.mean()) < float(plain.r.mean()) + 0.05 * float(plain.r.std()), (
        "conditioning on the up days bought a free mean -- the pool recentring is broken")


# ------------------------------------------------------------------------------- the optimisation

def test_uncorrelated_edges_beat_one_duplicated_edge() -> None:
    """The whole reason for E[log W] over Sharpe: correlation shows up in the variance drag."""
    rng = np.random.default_rng(7)
    base = rng.normal(0.05, 1.0, 800)
    dupes = [SleeveEvidence(name=f"d{i}", daily_r=base + rng.normal(0, 0.05, 800))
             for i in range(4)]
    indep = [SleeveEvidence(name=f"i{i}", daily_r=rng.normal(0.05, 1.0, 800)) for i in range(4)]
    g_dupe = optimise(dupes, hard_cap=0.30, target=0.15, cfg=CFG).mean_log_growth
    g_indep = optimise(indep, hard_cap=0.30, target=0.15, cfg=CFG).mean_log_growth
    assert g_indep > g_dupe


def test_free_solve_may_hold_back_but_the_mandate_may_not() -> None:
    ev = [_sleeve("bad", -0.05, 1.0, seed=1), _sleeve("worse", -0.08, 1.0, seed=2)]
    free = optimise(ev, hard_cap=0.30, target=None, cfg=CFG)
    assert free.total_heat < 0.05, "nothing worth betting on and it bet anyway"
    forced = optimise(ev, hard_cap=0.30, target=0.20, cfg=CFG, max_per_sleeve=0.15)
    assert forced.total_heat == pytest.approx(0.20, abs=1e-6)
    assert forced.mean_log_growth < free.mean_log_growth, (
        "forcing exposure onto a negative opportunity set must COST growth, and the artifact "
        "must be able to say so")


def test_target_above_hard_cap_is_refused() -> None:
    ev = [_sleeve("a", 0.05, 1.0)]
    with pytest.raises(ValueError, match="exceeds hard cap"):
        optimise(ev, hard_cap=0.20, target=0.25, cfg=CFG)


def test_marginal_delta_reallocates_instead_of_rejecting() -> None:
    """"The book is full, reject it" must not be an answer the desk can give.

    The book is pinned at full utilisation and a genuinely better, uncorrelated candidate
    arrives. It must be funded by taking heat from the incumbents, not deferred.
    """
    current = [_sleeve(f"c{i}", 0.02, 1.0, seed=i) for i in range(3)]
    cand = _sleeve("new", 0.12, 1.0, seed=99)
    out = marginal_delta_elog(current, cand, hard_cap=0.30, target=0.20,
                              max_per_sleeve=0.10, cfg=CFG)
    assert out["admit"] is True
    assert float(out["candidate_heat"]) > 1e-4, "a better edge got no capital"
    assert float(out["total_heat_after"]) == pytest.approx(0.20, abs=1e-6)
    realloc = out["reallocation"]
    assert isinstance(realloc, dict)
    assert min(realloc.values()) < 0, "nobody paid for the new sleeve; heat came from nowhere"


def test_marginal_delta_declines_a_worthless_candidate_on_the_arithmetic() -> None:
    current = [_sleeve(f"c{i}", 0.08, 1.0, seed=i) for i in range(3)]
    junk = _sleeve("junk", -0.10, 1.0, seed=42)
    out = marginal_delta_elog(current, junk, hard_cap=0.30, target=None, cfg=CFG)
    assert out["admit"] is False


def test_a_candidate_already_in_the_book_is_an_error_not_a_duplicate() -> None:
    ev = [_sleeve("a", 0.05, 1.0)]
    with pytest.raises(ValueError, match="already in the book"):
        marginal_delta_elog(ev, _sleeve("a", 0.05, 1.0), hard_cap=0.30, cfg=CFG)


def test_ruinous_book_is_refused_rather_than_scored() -> None:
    """A book that can go to zero has no log growth. Scoring it as "very negative" would let a
    large enough average buy a real ruin path."""
    ev = [SleeveEvidence(name="bomb", daily_r=np.array([0.1] * 99 + [-50.0]))]
    r = optimise(ev, hard_cap=0.30, target=None, cfg=WorldConfig(n_worlds=16, n_rows=64, seed=1))
    assert r.total_heat < 0.02


def test_empty_book_is_an_error_not_a_zero() -> None:
    with pytest.raises(ValueError, match="no sleeves"):
        optimise([], hard_cap=0.30)


def test_world_population_respects_the_memory_budget() -> None:
    """This box has 3.8 GB, no swap and a history of OOM kills. The population is trimmed to fit
    and SAYS SO, rather than being sized by hope."""
    ev = [_sleeve(f"s{i}", 0.02, 1.0, n=500, seed=i) for i in range(30)]
    w = sample_worlds(ev, WorldConfig(n_worlds=256, n_rows=384, max_elements=200_000, seed=1))
    assert w.r.size <= 200_000
    assert "trimmed" in w.note
