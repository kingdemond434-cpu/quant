"""DATASET-CONDITIONED: an existing family's own entries, kept only in a dataset's regime.

THE INDIRECT USE OF A DATASET (principal, 2026-09-30: every alt, macro or intelligence dataset
feeds direct cells, indirect conditioning/interaction cells on existing families, and allocation
state). `exogenous_conditioner` is the DIRECT use: a stance taken because a pack's statistic is at
an extreme. This is the other one: the question "does `session_range_breakout` on USDJPY behave
differently while Japanese positioning is stretched" -- a buildable base family, unchanged, and a
filter that keeps its entries only while the dataset's point-in-time reading sits in the named
state. The bet is still the base family's mechanism; the dataset decides WHEN it is taken, which
is exactly the interaction a price-only family can never express.

It loads its own input (`mt5desk.dataset_series`, lagged a full publication day), so the sealed
`build_cell`'s ordinary `fn(h1, side=1, **params)` call suffices and no sealed branch is needed.

REFUSES -- returns no signals -- when:
  * the base family is unwrappable (`family_exit_operated._UNWRAPPABLE`: it needs a runtime input
    `(bars, params)` cannot supply), is an operator, or is this family;
  * the dataset, the field or its availability stamp is absent, or it carries fewer than
    MIN_OBSERVATIONS readings: UNMEASURED, never a fall-back to the unconditioned base (which
    would be a duplicate cell carrying a second multiplicity charge for no new question);
  * the state is not one of STATES.

States read the transformed series (a z-score by default): `high` is above +threshold, `low`
below -threshold, `mid` within it. A bar before the dataset's first available reading is in NO
state, so the conditioned cell is simply silent there.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.build_memo import Memo, args_key, copy_signals, frame_fingerprint
from mt5desk.dataset_series import DEFAULT_LAG_HOURS, DEFAULT_Z_WINDOW, conditioned, on_bars
from mt5desk.families import Signal, _h1, get_family_func

STATES: tuple[str, ...] = ("high", "low", "mid")
MIN_OBSERVATIONS = 30
#: Families that are operators over another family, or that ARE this one: never a base.
NOT_A_BASE: frozenset[str] = frozenset({"dataset_conditioned", "exit_operated",
                                        "exogenous_conditioner"})

_BASE_MEMO = Memo(copier=copy_signals)


def base_ok(name: str) -> bool:
    """Can `name` be a base? Rebuildable from bars and params alone, and not an operator."""
    from mt5desk.family_exit_operated import wrappable
    return bool(name) and name not in NOT_A_BASE and not name.startswith("uu_") and \
        wrappable(name)


def in_state(values: np.ndarray, state: str, threshold: float) -> np.ndarray:
    thr = abs(float(threshold))
    with np.errstate(invalid="ignore"):
        if state == "high":
            m = values > thr
        elif state == "low":
            m = values < -thr
        elif state == "mid":
            m = np.abs(values) <= thr
        else:
            m = np.zeros(len(values), bool)
    return m & np.isfinite(values)


def family_dataset_conditioned(
    df: pd.DataFrame,
    side: int = 1,
    *,
    base_family: str,
    dataset: str,
    field: str,
    base_params: dict[str, Any] | None = None,
    match: str = "",
    transform: str = "level_z",
    state: str = "high",
    threshold: float = 1.0,
    lag_hours: int = DEFAULT_LAG_HOURS,
    z_window: int = DEFAULT_Z_WINDOW,
    series_root: Path | None = None,
) -> list[Signal]:
    """`base_family`'s signals on these bars, kept where `dataset.field` is in `state`."""
    if state not in STATES or not base_ok(str(base_family)):
        return []
    series = conditioned(str(dataset), str(field), transform=str(transform), match=str(match),
                         lag_hours=int(lag_hours), z_window=int(z_window), root=series_root)
    if series is None or len(series) < MIN_OBSERVATIONS:
        return []
    fn = get_family_func(str(base_family))
    if fn is None:
        return []
    params = dict(base_params or {})
    # The identity keys `build_cell` strips before calling a family (see family_exit_operated).
    for k in ("timeframe", "session"):
        params.pop(k, None)
    d = _h1(df)
    if d.empty:
        return []

    def _base() -> list[Signal] | None:
        try:
            raw = fn(d, side=side, **params)
        except TypeError:
            try:
                raw = fn(d, **params)
            except Exception:
                return None
        except Exception:
            return None
        return [s for s in (raw or []) if isinstance(s, Signal)]

    sigs = _BASE_MEMO.get_or_compute(
        (frame_fingerprint(d), args_key(str(base_family), {**params, "__side": side})), _base)
    if not sigs:
        return []
    times = pd.DatetimeIndex([s.time for s in sigs])
    keep = in_state(on_bars(series, times), str(state), float(threshold))
    return [s for s, k in zip(sigs, keep, strict=True) if k]
