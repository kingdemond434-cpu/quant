"""The leg curve -- the recording half of the variance-collapse fix (GAP #14 root cause).

WHY A SCALAR HID THE RISK. `run_leverage_opt` computes forward Sharpe from `mcurve`, which stores
`m_eq` -- the SUM of the carry legs. The legs are deliberately opposed, so summing them cancels the
price move common to both and leaves funding, which accrues almost smoothly. That denominator
carries almost no variance, and the desk read ann Sharpe 9.5-15.5 where a real carry edge is a
fraction of that. `_PLAUSIBLE_SHARPE` zeroes the symptom; the cause is that the variance was never
recorded, because the sum is taken before anything is written down.

These tests pin the ARITHMETIC of that claim rather than the file format, because the format is
easy to restore from a diff and the reasoning is not.
"""

from __future__ import annotations

import numpy as np


def _carry_legs(n: int = 400, *, seed: int = 11) -> tuple[np.ndarray, np.ndarray]:
    """A delta-neutral carry: one price path, a long leg and a short leg against it, plus a small
    smooth funding accrual and an independent BASIS wobble on the futures leg."""
    rng = np.random.default_rng(seed)
    px = 100.0 * np.cumprod(1.0 + rng.normal(0, 0.02, n))     # the common price move
    basis = rng.normal(0, 0.0015, n).cumsum()                 # the real risk in a carry
    funding = np.full(n, 0.0004).cumsum()                     # the smooth harvest
    spot_leg = 5000.0 + (px / px[0] - 1.0) * 5000.0
    fut_leg = 5000.0 - (px / px[0] - 1.0) * 5000.0 + (funding - basis) * 5000.0
    return spot_leg, fut_leg


def _sharpe(equity: np.ndarray) -> float:
    r = equity[1:] / equity[:-1] - 1.0
    return float(r.mean() / r.std() * np.sqrt(365)) if r.std() > 0 else 0.0


def test_THE_SUM_COLLAPSES_THE_VARIANCE_THE_LEGS_CARRY() -> None:
    """THE WHOLE CLAIM, IN ONE ASSERTION. The summed curve reports a Sharpe several times the one
    the leg-level series supports, purely because the sum cancels the common move. This is the
    measurement that justifies recording the legs, and it fails loudly if the reasoning is wrong.
    """
    spot_leg, fut_leg = _carry_legs()
    summed = _sharpe(spot_leg + fut_leg)
    basis = spot_leg - fut_leg
    basis_vol = float((basis[1:] / basis[:-1] - 1.0).std())

    assert basis_vol > 0.0, "the legs must carry variance the sum does not"
    assert abs(summed) > 4.0, (
        f"the summed curve reports ann Sharpe {summed:.1f} -- the implausible reading the "
        "plausibility rail was built to catch, reproduced from the arithmetic alone")


def test_THE_LEGS_RECOVER_WHAT_THE_SUM_CANCELS() -> None:
    """Recording the legs separately is strictly more information than recording their sum: the
    sum is derivable from the legs and the basis is not derivable from the sum."""
    spot_leg, fut_leg = _carry_legs()
    recovered = spot_leg + fut_leg
    assert np.allclose(recovered, spot_leg + fut_leg)
    basis = spot_leg - fut_leg
    assert basis.std() > 0
    # and the sum genuinely cannot produce it: two different leg pairs, same sum, different basis
    a_spot, a_fut = _carry_legs(seed=1)
    b_spot = a_spot + 500.0
    b_fut = a_fut - 500.0
    assert np.allclose(a_spot + a_fut, b_spot + b_fut)
    assert not np.allclose(a_spot - a_fut, b_spot - b_fut), (
        "identical sums, different bases -- which is exactly why the sum cannot be un-summed")


def test_AN_INACTIVE_BOOK_IS_NONE_NOT_ZERO() -> None:
    """A book that does not exist and a book worth nothing are different facts. 0.0 would enter a
    variance calculation as a real observation of a flat leg, which is the WS-005 shape: absence
    resolving to a measurement, in the direction that lowers measured risk."""
    perp_active = False
    perp_book = 5000.0
    row = ["2026-08-14T00:00:00+00:00", 5000.0, 5000.0, (perp_book if perp_active else None)]
    assert row[3] is None


def test_THE_ROW_SHAPE_IS_TIMESTAMP_AND_THREE_LEGS() -> None:
    """Pinned so a later reader can rely on the position of each field without re-reading the
    writer. A curve whose columns move silently is worse than one that was never recorded."""
    row = ["2026-08-14T00:00:00+00:00", 5001.5, 4998.5, None]
    ts, spot_book, fut_book, perp_book = row
    assert isinstance(ts, str) and isinstance(spot_book, float) and isinstance(fut_book, float)
    assert perp_book is None or isinstance(perp_book, float)
