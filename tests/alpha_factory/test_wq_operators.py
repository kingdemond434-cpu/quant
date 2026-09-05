"""GROUP-RELATIVE OPERATORS, AND THE BAR THAT MUST NOT BE IMPORTED WITH THEM.

Since 2026-09-05 the last block also pins the SINGLE-SERIES reading of the same idea against
`libs.research.alpha_grammar`, which reimplements these operators rather than importing them
(the grammar is on the live signal path and this package is not). Two implementations of one
idea drift unless something measures them against each other; that is what those tests are.

A community summary of WorldQuant BRAIN practice arrived carrying two things at once: operators the
desk's expression language genuinely lacked, and an IN-SAMPLE submission threshold from a platform
whose economics are the opposite of this desk's. The operators are worth adopting; the threshold
would be an order-of-magnitude bar reduction wearing a respected name. So roughly half these tests
are about the second half never leaking into the first.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from libs.alpha_factory.combination_engine import TRANSFORMS, space_size
from libs.alpha_factory.wq_operators import (
    GROUP_TRANSFORMS,
    TS_GROUP_TRANSFORMS,
    UNIVERSE_IF_ADOPTED,
    fitness,
    group_rank,
    group_zscore,
    trade_when,
    ts_backfill,
    ts_group_rank,
    ts_group_zscore,
)
from libs.research import alpha_grammar as ag

#: three "L1" names and two "DeFi" names, so group and universe answers must differ
_GROUPS = {"BTC": "L1", "ETH": "L1", "SOL": "L1", "UNI": "DEFI", "AAVE": "DEFI"}


def _panel() -> pd.DataFrame:
    return pd.DataFrame({
        "BTC": [1.0, 2.0], "ETH": [2.0, 1.0], "SOL": [3.0, 3.0],
        "UNI": [10.0, 20.0], "AAVE": [20.0, 10.0],
    })


# ------------------------------------------------------- the operator the desk lacked


def test_GROUP_RANK_ASKS_A_DIFFERENT_QUESTION_FROM_UNIVERSE_RANK() -> None:
    """The desk had no group operator at all, so every cross-sectional cell in the 898,560-cell
    sweep asked 'extreme against ALL coins?' and none asked 'extreme against its PEERS?'. On a book
    where BTC and a small-cap L1 share almost no volatility regime, a universe-wide rank is
    dominated by which group a name belongs to rather than by anything specific to the name."""
    p = _panel()
    grouped = group_rank(p["BTC"], p, _GROUPS)
    universe = p.rank(axis=1, pct=True)["BTC"]
    assert grouped is not None
    assert not grouped.equals(universe), "group rank collapsed to the universe-wide rank"
    # BTC is lowest of the three L1s on bar 0 -> bottom third of its group
    assert grouped.iloc[0] == pytest_approx(1 / 3)


def pytest_approx(v: float, tol: float = 1e-9) -> float:
    """Tiny local helper so the assertions read as arithmetic rather than as fixtures."""
    class _A(float):
        def __eq__(self, other: object) -> bool:
            return isinstance(other, int | float) and abs(float(other) - v) < tol
        __hash__ = None  # type: ignore[assignment]
    return _A(v)


def test_GROUP_ZSCORE_STANDARDISES_WITHIN_THE_PEER_GROUP() -> None:
    p = _panel()
    z = group_zscore(p["UNI"], p, _GROUPS)
    assert z is not None
    # UNI vs AAVE on bar 0: 10 vs 20 -> UNI is the low one, so negative
    assert z.iloc[0] < 0 and z.iloc[1] > 0


def test_NO_GROUP_MAP_REFUSES_RATHER_THAN_FALLING_BACK_TO_UNIVERSE_RANK() -> None:
    """The load-bearing refusal. A silent fallback would consume a whole new arm of the search
    space while computing something the desk already has -- and every result would look like a new
    finding rather than a duplicate of `rank`."""
    p = _panel()
    assert group_rank(p["BTC"], p, None) is None
    assert group_rank(p["BTC"], p, {}) is None
    assert group_zscore(p["BTC"], p, None) is None


def test_A_SINGLE_GROUP_IS_THE_UNIVERSE_AND_IS_ALSO_REFUSED() -> None:
    """If every name maps to one group, `group_rank` IS `rank`. Computing it anyway would pay a
    trial to re-derive an existing transform."""
    p = _panel()
    one = dict.fromkeys(_GROUPS, "EVERYTHING")
    assert group_rank(p["BTC"], p, one) is None


def test_A_GROUP_OF_ONE_HAS_NO_RANK_TO_COMPUTE() -> None:
    """A lone member ranks 1.0 against itself at every bar -- a constant, which is the degenerate
    case this desk keeps finding disguised as a signal."""
    p = _panel()
    lonely = {**_GROUPS, "AAVE": "SOLO"}
    assert group_rank(p["AAVE"], p, lonely) is None


def test_UNLABELLED_MEMBERS_ARE_EXCLUDED_NOT_POOLED_INTO_AN_OTHER_BUCKET() -> None:
    """A residual group assembled from whatever was unlabelled is not a peer group, and ranking
    within it manufactures a comparison nobody intended."""
    p = _panel()
    partial = {"BTC": "L1", "ETH": "L1", "UNI": "DEFI", "AAVE": "DEFI"}   # SOL unlabelled
    r = group_rank(p["BTC"], p, partial)
    assert r is not None and group_rank(p["SOL"], p, partial) is None
    assert r.iloc[0] == pytest_approx(0.5), "SOL leaked into BTC's peer group"


# --------------------------------------------------------------------- ts_backfill


def test_BACKFILL_IS_BOUNDED_BECAUSE_UNBOUNDED_FILL_INVENTS_DATA() -> None:
    """On a delisted or halted name an unbounded forward-fill becomes a flat line the harness reads
    as a live signal, persisting against real forward returns for the rest of the sample."""
    x = pd.Series([1.0, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan])
    filled = ts_backfill(x, limit=2)
    assert filled.iloc[1] == 1.0 and filled.iloc[2] == 1.0
    assert bool(np.isnan(filled.iloc[3])), "the fill ran past its limit and invented data"


def test_BACKFILL_IS_FORWARD_ONLY_DESPITE_THE_NAME() -> None:
    """Filling backwards writes a future observation into a past bar -- leakage by construction,
    and invisible in every result it contaminates."""
    x = pd.Series([np.nan, np.nan, 5.0])
    assert bool(ts_backfill(x).isna().iloc[0]), "a future value was written into a past bar"


# ---------------------------------------------------------------------- trade_when


def test_TRADE_WHEN_HOLDS_WHERE_CONDITION_GOES_FLAT() -> None:
    """The whole difference from the desk's `condition` operator, and it is a TURNOVER difference:
    `condition` multiplies by a gate so a failed gate exits the book and re-enters when it
    flickers, paying the round trip twice for a view that never changed."""
    sig = pd.Series([1.0, 2.0, 3.0, 4.0])
    cond = pd.Series([True, False, False, True])
    held = trade_when(cond, sig)
    assert list(held) == [1.0, 1.0, 1.0, 4.0]

    flat = sig * cond.astype(float)          # what `condition` does today
    assert list(flat) == [1.0, 0.0, 0.0, 4.0]
    assert float(held.diff().abs().sum()) < float(flat.diff().abs().sum()), (
        "trade_when did not reduce turnover relative to gating flat -- which is its only reason "
        "to exist")


def test_TRADE_WHEN_IS_A_DIFFERENT_HYPOTHESIS_NOT_A_REPAIR() -> None:
    """It changes what the signal IS, so it owes its own trial rather than inheriting the parent's
    evidence. Fenced by the docstring saying so, since there is no code path that could enforce it
    here -- the trial ledger is where that lives."""
    import inspect

    from libs.alpha_factory import wq_operators

    doc = inspect.getdoc(wq_operators.trade_when) or ""
    assert "DIFFERENT hypothesis" in doc and "own trial" in doc


# ------------------------------------------------------- the bar that must not be imported


def test_THERE_IS_NO_SUBMISSION_BAR_FUNCTION_AT_ALL() -> None:
    """The central refusal. WorldQuant's 'in-sample Sharpe >= 1.25' is a submission filter for a
    platform that runs its own out-of-sample validation afterwards and pays per accepted alpha --
    they can afford false positives because THEY bear the expensive stage. This desk bears it with
    its own capital against a deflated t of 5.236 plus OOS, walk-forward and independence.

    A function returning True/False against 1.25 would be an order-of-magnitude bar reduction
    wearing a respected institution's name, so the function does not exist -- and the function that
    does not exist cannot be called by an organ that read the same summary."""
    from libs.alpha_factory import wq_operators

    banned = [n for n in dir(wq_operators)
              if any(k in n.lower() for k in ("passes", "submission", "accept", "qualif"))]
    assert banned == [], f"a submission-bar path appeared: {banned}"
    assert "1.25" not in " ".join(str(getattr(wq_operators, n, "")) for n in wq_operators.__all__)


def test_FITNESS_IS_A_DIAGNOSTIC_THAT_PENALISES_CHURN() -> None:
    """Its SHAPE is what is worth having: identical Sharpe ranks lower when turnover is higher,
    which is the lesson WS-006 paid for in measurement."""
    slow = fitness(2.0, 0.30, turnover=0.20)
    fast = fitness(2.0, 0.30, turnover=5.00)
    assert slow > fast
    assert fitness(2.0, 0.30, 0.001) == fitness(2.0, 0.30, 0.125), "the turnover floor is missing"


def test_FITNESS_RETURNS_NAN_RATHER_THAN_A_NUMBER_IT_CANNOT_JUSTIFY() -> None:
    assert math.isnan(fitness(float("nan"), 0.3, 0.5))
    assert math.isnan(fitness(2.0, 0.3, -1.0))


# ------------------------------------------------------------ the cost of adopting them


def test_THE_NEW_TRANSFORMS_ARE_NOT_SILENTLY_IN_THE_DECLARED_UNIVERSE() -> None:
    """Adding three transforms takes the universe from 898,560 to 1,698,840 and would invalidate
    FULL_SWEEP_PREREGISTRATION.md's declared count -- and the count IS the hurdle. They stay out of
    `TRANSFORMS` until a new family is declared."""
    assert not set(GROUP_TRANSFORMS) & set(TRANSFORMS)
    assert space_size(13, n_transforms=len(TRANSFORMS)) == 898_560


def test_THE_COST_OF_ADOPTION_IS_WRITTEN_DOWN_BEFORE_IT_IS_PAID() -> None:
    """So the enlarged hurdle is a decision rather than a discovery made after the fact."""
    n_tf = len(TRANSFORMS) + len(GROUP_TRANSFORMS)
    assert space_size(13, n_transforms=n_tf) == UNIVERSE_IF_ADOPTED
    before = math.sqrt(2 * math.log(898_560))
    after = math.sqrt(2 * math.log(UNIVERSE_IF_ADOPTED))
    assert after > before
    assert round(after, 3) == 5.356


# ------------------------------------------------- the single-series reading of the same idea
def _series(n: int = 300, seed: int = 0) -> tuple[pd.Series, pd.Series]:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    return (pd.Series(rng.normal(size=n), index=idx),
            pd.Series(np.concatenate([np.full(n // 2, -1.0), np.full(n - n // 2, 1.0)])
                      + rng.normal(0, 0.1, n), index=idx))


def test_THE_PEER_GROUP_CAN_BE_A_STATE_WHEN_THERE_IS_NO_PANEL() -> None:
    """The desk trades one instrument per cell, so the panel form is unusable there. What
    transfers is the QUESTION -- extreme against its peers, not against everything -- and the
    peers of a bar are the bars in the same state."""
    x, by = _series()
    w = 24
    rank = ts_group_rank(x, by, w)
    assert rank.iloc[:w - 1].isna().all()                # causal: no verdict before the window
    valid = rank.dropna()
    assert len(valid) > 200 and valid.between(0.0, 1.0).all() and (valid > 0).all()
    z = ts_group_zscore(x, by, w)
    assert z.iloc[:w - 1].isna().all() and z.dropna().abs().max() < 10.0
    # a bar is ranked only against bars on ITS side of the conditioning series' window mean,
    # so a series that is extreme overall but ordinary for its state does not rank extreme
    flat = pd.Series(np.tile([0.0, 1.0], 150), index=x.index)
    state = pd.Series(np.tile([0.0, 1.0], 150), index=x.index)
    perfect = ts_group_rank(flat, state, w).dropna()
    assert (perfect == 1.0).all()                        # every bar is the max OF ITS OWN state
    # too short a window, or a mismatched partner, is NaN rather than an exception
    assert ts_group_rank(x, by, 1).isna().all()
    assert ts_group_rank(x, by.iloc[:10], 24).isna().all()
    assert ts_group_zscore(x.iloc[:5], by.iloc[:5], 24).isna().all()


def test_THE_GRAMMAR_REIMPLEMENTS_THESE_OPERATORS_AND_MUST_NOT_DRIFT_FROM_THEM() -> None:
    """`alpha_grammar` cannot import this package -- it is on the live signal path and this
    pulls the whole Alpha Factory -- so it reimplements. This is what keeps the two equal."""
    x, by = _series(400, seed=3)
    frames = {"x": x, "by": by}
    for w in (5, 12, 24, 48):
        assert np.allclose(ag.evaluate(["group_rank", "x", "by", w], frames).to_numpy(),
                           ts_group_rank(x, by, w).to_numpy(), equal_nan=True), w
        assert np.allclose(ag.evaluate(["group_zscore", "x", "by", w], frames).to_numpy(),
                           ts_group_zscore(x, by, w).to_numpy(), equal_nan=True), w
    # and the two operators the grammar took verbatim in behaviour
    gappy = x.mask(x > 0.5)
    assert ag.evaluate(["ts_backfill", "x", 3], {"x": gappy}).equals(ts_backfill(gappy, limit=3))
    gate = pd.Series([1.0, -1.0, -1.0, 1.0], index=x.index[:4])
    sig = pd.Series([5.0, 6.0, 7.0, 8.0], index=x.index[:4])
    assert ag.evaluate(["trade_when", "g", "s"], {"g": gate, "s": sig}).equals(
        trade_when(gate > 0, sig))
    # the grammar TYPES them, which this module does not and does not need to
    assert ag.type_of(["group_rank", "close", "vol", 24]) == "RANK"
    assert ag.well_formed(["group_zscore", "close", "vol", 24])


def test_THE_TIME_SERIES_FORMS_ARE_ALSO_OUTSIDE_THE_DECLARED_UNIVERSE() -> None:
    """They are operators of the expression grammar, charged inside that search's own
    multiplicity -- never a silent extra arm of a pre-registered cross-sectional family."""
    assert not set(TS_GROUP_TRANSFORMS) & set(TRANSFORMS)
    assert not set(TS_GROUP_TRANSFORMS) & set(GROUP_TRANSFORMS)
    assert space_size(13, n_transforms=len(TRANSFORMS)) == 898_560
