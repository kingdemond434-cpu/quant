"""Per-sleeve decay, per-sleeve crisis share and the solve deadline: relief-only by construction.

THE LAW THESE PIN (principal, 2026-09-08, three times): nothing added to the allocator may size
any sleeve below what it gets today. So every new field here is a CEILING relationship with the
constant it replaces -- `decay_prob_i` is applied at `min(own, blanket)`, a per-sleeve crisis
share at `min(own, scalar)` -- and a population in which every sleeve carries the old constant is
byte-identical to the one the desk drew yesterday. Each test below measures one direction of
that: identical when absent, more heat when relieved, never less.
"""
from __future__ import annotations

import time

import numpy as np
import pytest

from libs.portfolio.robust_elog import (
    SleeveEvidence,
    WorldConfig,
    crisis_share_vector,
    decay_prob_of,
    optimise,
    sample_worlds,
)


def _sleeve(name: str, mu: float, sd: float, n: int = 600, seed: int = 0,
            activity: float = 0.2, **kw: object) -> SleeveEvidence:
    rng = np.random.default_rng(seed)
    r = rng.normal(mu / activity, sd, n) * (rng.random(n) < activity)
    return SleeveEvidence(name=name, daily_r=r, **kw)  # type: ignore[arg-type]


CFG = WorldConfig(n_worlds=64, n_rows=128, seed=3)


# ----------------------------------------------------------------------- identical when absent
def test_a_population_without_per_sleeve_fields_is_byte_identical_to_the_scalar_draw() -> None:
    """The vectorised arithmetic must reproduce the scalar overlay exactly, or the change moved
    every book on the desk by a rounding error nobody asked for."""
    plain = [_sleeve("a", 0.05, 1.0, seed=1), _sleeve("b", 0.04, 1.0, seed=2)]
    explicit = [SleeveEvidence(name=e.name, daily_r=e.daily_r, decay_prob_i=CFG.decay_prob)
                for e in plain]
    cfg_vec = WorldConfig(n_worlds=64, n_rows=128, seed=3, crisis_prob=0.5,
                          crisis_common_share_by_sleeve=(("a", CFG.crisis_common_share),
                                                         ("b", CFG.crisis_common_share)))
    cfg_plain = WorldConfig(n_worlds=64, n_rows=128, seed=3, crisis_prob=0.5)
    w0 = sample_worlds(plain, cfg_plain)
    w1 = sample_worlds(explicit, cfg_vec)
    assert int(w0.crisis.sum()) > 0, "fixture: crisis worlds must be present for the overlay"
    np.testing.assert_array_equal(w0.r, w1.r)


# ------------------------------------------------------------------------- decay: relief only
def test_decay_prob_i_is_applied_at_the_blanket_or_below_never_above() -> None:
    cfg = WorldConfig(decay_prob=0.30)
    assert decay_prob_of(SleeveEvidence("x", np.zeros(3)), cfg) == pytest.approx(0.30)
    assert decay_prob_of(SleeveEvidence("x", np.zeros(3), decay_prob_i=0.05), cfg) == 0.05
    assert decay_prob_of(SleeveEvidence("x", np.zeros(3), decay_prob_i=0.90), cfg) == 0.30
    assert decay_prob_of(SleeveEvidence("x", np.zeros(3), decay_prob_i=-1.0), cfg) == 0.30
    assert decay_prob_of(SleeveEvidence("x", np.zeros(3), decay_prob_i=float("nan")), cfg) == 0.30
    # A decay-free reference population stays decay-free whatever the sleeves carry.
    assert decay_prob_of(SleeveEvidence("x", np.zeros(3), decay_prob_i=0.9),
                         WorldConfig(decay_prob=0.0)) == 0.0


def test_a_decay_posterior_above_the_blanket_changes_nothing_in_the_worlds() -> None:
    base = [_sleeve("a", 0.05, 1.0, seed=1), _sleeve("b", 0.04, 1.0, seed=2)]
    worse = [SleeveEvidence(name=e.name, daily_r=e.daily_r, decay_prob_i=0.95) for e in base]
    np.testing.assert_array_equal(sample_worlds(base, CFG).r, sample_worlds(worse, CFG).r)


def test_a_healthy_sleeve_pays_less_decay_and_earns_at_least_what_it_earned() -> None:
    """The drift monitor calls one sleeve healthy: it stops paying the blanket 30% and the free
    optimum gives it MORE heat, with the book's total never lower than before."""
    base = [_sleeve("healthy", 0.06, 1.0, seed=11), _sleeve("other", 0.05, 1.0, seed=12)]
    relieved = [SleeveEvidence(name="healthy", daily_r=base[0].daily_r, decay_prob_i=0.02),
                base[1]]
    before = optimise(base, hard_cap=0.45, target=None, cfg=CFG)
    after = optimise(relieved, hard_cap=0.45, target=None, cfg=CFG)
    assert after.heat["healthy"] >= before.heat["healthy"] - 1e-6, (
        f"relief lowered the healthy sleeve: {before.heat['healthy']:.4f} -> "
        f"{after.heat['healthy']:.4f}")
    assert after.total_heat >= before.total_heat - 1e-6
    assert after.mean_log_growth >= before.mean_log_growth - 1e-9


def test_relief_never_lowers_a_mandated_total_below_its_target() -> None:
    ev = [SleeveEvidence(name="a", daily_r=_sleeve("a", 0.05, 1.0, seed=1).daily_r,
                         decay_prob_i=0.01),
          _sleeve("b", 0.04, 1.0, seed=2)]
    r = optimise(ev, hard_cap=0.45, target=0.20, cfg=CFG, max_per_sleeve=0.15)
    assert r.total_heat == pytest.approx(0.20, abs=1e-6)


# ------------------------------------------------------------- crisis share: the scalar is the cap
def test_the_per_sleeve_crisis_share_is_capped_at_the_book_wide_scalar() -> None:
    cfg = WorldConfig(crisis_common_share=0.55,
                      crisis_common_share_by_sleeve=(("a", 0.20), ("b", 0.90), ("c", -1.0)))
    v = crisis_share_vector(("a", "b", "c", "d"), cfg)
    assert v.dtype == np.float32
    assert v[0] == pytest.approx(0.20)
    assert v[1] == pytest.approx(0.55), "a block may never be stressed harder than the book"
    assert v[2] == pytest.approx(0.0)
    assert v[3] == pytest.approx(0.55), "an unlisted sleeve carries the scalar"


def test_a_block_measured_less_fused_is_less_correlated_in_crisis_worlds() -> None:
    """Two sleeves, every world a crisis. With the scalar both load 0.55 on the common factor;
    with one at 0.10 their crisis correlation must fall -- that is the independence a sleeve
    outside the shocked block keeps."""
    ev = [_sleeve("usd", 0.02, 1.0, seed=5, activity=1.0),
          _sleeve("metal", 0.02, 1.0, seed=6, activity=1.0)]
    common = {"n_worlds": 48, "n_rows": 256, "seed": 9, "crisis_prob": 1.0}
    fused = sample_worlds(ev, WorldConfig(**common))
    relieved = sample_worlds(ev, WorldConfig(**common,
                                             crisis_common_share_by_sleeve=(("metal", 0.10),)))

    def _rho(w) -> float:
        cs = [np.corrcoef(w.r[i, :, 0], w.r[i, :, 1])[0, 1] for i in range(w.n_worlds)]
        return float(np.nanmean(cs))

    assert _rho(fused) > _rho(relieved) + 0.05
    assert _rho(relieved) > 0.0, "the block is less fused, not independent -- one factor remains"


def test_a_share_above_the_scalar_is_the_scalar_population_exactly() -> None:
    ev = [_sleeve("a", 0.02, 1.0, seed=5), _sleeve("b", 0.02, 1.0, seed=6)]
    common = {"n_worlds": 32, "n_rows": 128, "seed": 9, "crisis_prob": 0.5}
    scalar = sample_worlds(ev, WorldConfig(**common))
    above = sample_worlds(ev, WorldConfig(**common, crisis_common_share_by_sleeve=(("a", 0.99),)))
    np.testing.assert_array_equal(scalar.r, above.r)


# --------------------------------------------------------------------------- the solve deadline
def test_a_spent_deadline_returns_a_feasible_partial_book_and_says_so() -> None:
    ev = [_sleeve("a", 0.05, 1.0, seed=1), _sleeve("b", 0.04, 1.0, seed=2)]
    r = optimise(ev, hard_cap=0.45, target=0.20, cfg=CFG, max_per_sleeve=0.15,
                 deadline=time.time() - 1.0)
    assert r.budget_hit is True and r.converged is False and r.iterations == 0
    assert r.total_heat == pytest.approx(0.20, abs=1e-6), "a partial book is still feasible"
    assert all(v <= 0.15 + 1e-9 for v in r.heat.values())
    assert np.isfinite(r.robust_score)


def test_no_deadline_is_exactly_the_old_solve() -> None:
    ev = [_sleeve("a", 0.05, 1.0, seed=1), _sleeve("b", 0.04, 1.0, seed=2)]
    a = optimise(ev, hard_cap=0.45, target=0.20, cfg=CFG, max_per_sleeve=0.15)
    b = optimise(ev, hard_cap=0.45, target=0.20, cfg=CFG, max_per_sleeve=0.15, deadline=None)
    assert a.heat == b.heat and a.budget_hit is False and b.budget_hit is False
    far = optimise(ev, hard_cap=0.45, target=0.20, cfg=CFG, max_per_sleeve=0.15,
                   deadline=time.time() + 3600.0)
    assert far.heat == a.heat and far.budget_hit is False
