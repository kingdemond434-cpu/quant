"""A BOOK THAT REPORTS FULL ALLOCATION AND CANNOT EXECUTE IT IS THE FAILURE HERE.

The portfolio toolkit was already good -- max-Sharpe, HRP, risk parity, concentration caps. It ran
entirely in Sharpe space, where a strategy with a 30bp edge and 5bp of tradeable capacity looks
identical to one that can carry the whole book. And nothing measured whether two families were
actually the same trade in different vocabulary.

Both gaps produce confident numbers, which is why they survived. These tests pin the constraint
(capacity binds, hard) and the check (breadth is measured, not inferred from having different
names).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from libs.portfolio.capacity_allocation import allocate_with_capacity, family_correlation


def _streams(n: int = 2000, k: int = 4, rho: float = 0.0, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    common = rng.normal(0, 1, n)
    return pd.DataFrame({
        f"f{i}": np.sqrt(rho) * common + np.sqrt(1 - rho) * rng.normal(0, 1, n)
        for i in range(k)})


def _flat(names, v):
    return dict.fromkeys(names, v)


# ------------------------------------------------------------------- breadth

def test_independent_families_measure_full_breadth() -> None:
    d = _streams(rho=0.0, k=4)
    _, n_eff, corr = family_correlation(d)
    assert n_eff == pytest.approx(4, rel=0.15)
    assert abs(corr) < 0.05


def test_two_families_that_are_the_same_trade_measure_as_one_bet() -> None:
    """THE CHECK NOTHING WAS DOING. An ICT liquidity sweep and a mean-reversion-after-stop-run are
    not obviously the same thing on paper and may be identical in P&L. A sleeve allocator handed
    their separate Sharpes doubles the position and calls it diversification."""
    base = np.random.default_rng(1).normal(0, 1, 2000)
    d = pd.DataFrame({"ict": base, "reversion": base, "third": base})
    _, n_eff, corr = family_correlation(d)
    assert n_eff == pytest.approx(1.0, rel=0.05)
    assert corr == pytest.approx(1.0, rel=0.05)


def test_the_ir_multiple_is_the_sqrt_of_measured_breadth() -> None:
    d = _streams(rho=0.0, k=4)
    r = allocate_with_capacity(d, _flat(d.columns, 1.0), _flat(d.columns, 1.0))
    assert r.ir_multiple == pytest.approx(np.sqrt(r.n_eff))


# ------------------------------------------------------------------ capacity

def test_capacity_binds_regardless_of_sharpe() -> None:
    """The whole point. A brilliant strategy that cannot be executed at size cannot be held."""
    d = _streams(k=3)
    sharpes = {"f0": 5.0, "f1": 0.5, "f2": 0.5}
    cap = {"f0": 0.05, "f1": 1.0, "f2": 1.0}
    r = allocate_with_capacity(d, sharpes, cap)
    w = r.as_dict()
    assert w["f0"] <= 0.05 + 1e-9
    assert "f0" in r.capped


def test_zero_capacity_means_zero_weight() -> None:
    d = _streams(k=3)
    r = allocate_with_capacity(d, {"f0": 9.0, "f1": 1.0, "f2": 1.0},
                               {"f0": 0.0, "f1": 1.0, "f2": 1.0})
    assert r.as_dict()["f0"] == 0.0


def test_no_weight_ever_exceeds_its_capacity() -> None:
    """The invariant that must hold after every redistribution round."""
    rng = np.random.default_rng(5)
    d = _streams(k=6)
    for _ in range(20):
        cap = {n: float(rng.uniform(0.0, 0.4)) for n in d.columns}
        sh = {n: float(rng.uniform(0.1, 3.0)) for n in d.columns}
        r = allocate_with_capacity(d, sh, cap)
        for n, w in r.as_dict().items():
            assert w <= cap[n] + 1e-9, f"{n}: {w} > cap {cap[n]}"


def test_freed_capital_is_redistributed_not_dropped() -> None:
    """Capping without redistributing silently leaves the book under-invested -- a one-line
    mistake whose signature is a portfolio that never reaches its target for no stated reason."""
    d = _streams(k=3)
    tight = allocate_with_capacity(d, {"f0": 3.0, "f1": 1.0, "f2": 1.0},
                                   {"f0": 0.05, "f1": 1.0, "f2": 1.0})
    assert tight.gross > 0.5, f"gross fell to {tight.gross} -- spill was not redistributed"


def test_redistribution_does_not_overflow_a_second_cap() -> None:
    """Redistributing once without re-capping pushes freed capital into names already at their
    limit. The fixed-point loop is what makes both constraints hold at once."""
    d = _streams(k=3)
    r = allocate_with_capacity(d, {"f0": 3.0, "f1": 2.0, "f2": 1.0},
                               {"f0": 0.05, "f1": 0.05, "f2": 1.0})
    w = r.as_dict()
    assert w["f0"] <= 0.05 + 1e-9 and w["f1"] <= 0.05 + 1e-9


def test_an_uninvestable_book_reports_unallocated_rather_than_pretending() -> None:
    """If every strategy is at its cap the honest answer is that the desk cannot deploy that much
    capital, not that it should report as though it had."""
    d = _streams(k=3)
    r = allocate_with_capacity(d, _flat(d.columns, 1.0), _flat(d.columns, 0.1),
                               gross_target=1.0)
    assert r.gross == pytest.approx(0.3, abs=1e-6)
    assert r.unallocated == pytest.approx(0.7, abs=1e-6)


def test_unlimited_capacity_reproduces_the_uncapped_allocation() -> None:
    """The constraint must be inert when it does not bind, or it is silently reshaping the book."""
    d = _streams(k=4)
    sh = {n: 1.0 + i for i, n in enumerate(d.columns)}
    loose = allocate_with_capacity(d, sh, _flat(d.columns, 10.0))
    assert loose.capped == ()
    assert loose.gross == pytest.approx(1.0, abs=1e-6)


# ------------------------------------------------------------------- hygiene

def test_a_strategy_with_unknown_capacity_is_refused() -> None:
    """Defaulting an unknown capacity to unlimited is how an unexecutable book gets built."""
    d = _streams(k=2)
    with pytest.raises(ValueError, match="missing Sharpe or capacity"):
        allocate_with_capacity(d, {"f0": 1.0}, {"f0": 1.0})


def test_an_empty_universe_is_refused() -> None:
    with pytest.raises(ValueError, match="no strategies"):
        allocate_with_capacity(pd.DataFrame(), {}, {})


def test_the_note_states_that_capacity_is_hard() -> None:
    """A soft version reads as prudent and is worse: it lets a strategy hold slightly more than it
    can trade forever, with the excess surfacing only as unattributed slippage."""
    d = _streams(k=2)
    r = allocate_with_capacity(d, _flat(d.columns, 1.0), _flat(d.columns, 1.0))
    assert "HARD constraint" in r.note
