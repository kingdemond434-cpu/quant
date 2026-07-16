"""Feature validation: leakage detection and train/serve parity.

The single mechanism behind leakage detection is **future invariance**: a causal feature's
value at time t must not change when *future* bars (> t) are mutated. This one test rejects
future leakage, lookahead bias, hindsight labels, and full-sample normalization. Parity is a
separate check that the offline (batch) and online (incremental) computations agree.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict

from libs.features.definition import FeatureDefinition
from libs.features.errors import FeatureError


class LeakageResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool
    n_checked: int
    n_leaked: int
    max_diff: float
    message: str

    def __bool__(self) -> bool:
        return self.ok


class ParityResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool
    n_checked: int
    n_mismatch: int
    max_abs_diff: float
    message: str

    def __bool__(self) -> bool:
        return self.ok


class FeatureValidation(BaseModel):
    model_config = ConfigDict(frozen=True)

    feature: str
    ok: bool
    structural_ok: bool
    leakage: LeakageResult
    parity: ParityResult
    reasons: list[str]

    def __bool__(self) -> bool:
        return self.ok


def _sample_points(n: int, start: int, count: int) -> list[int]:
    start = max(start, 1)
    if start >= n:
        return []
    if n - start <= count:
        return list(range(start, n))
    return list(np.linspace(start, n - 1, count, dtype=int))


def _equal(a: float, b: float, tol: float) -> bool:
    if np.isnan(a) and np.isnan(b):
        return True
    if np.isnan(a) != np.isnan(b):
        return False
    return bool(abs(a - b) <= tol)


def run_leakage_test(
    definition: FeatureDefinition,
    bars: pd.DataFrame,
    *,
    sample: int = 24,
    tol: float = 1e-9,
) -> LeakageResult:
    """Detect lookahead by mutating future bars and checking past values are invariant."""
    full = definition.compute(bars).to_numpy(dtype="float64")
    n = len(bars)
    points = _sample_points(n, definition.min_periods, sample)
    n_leaked = 0
    max_diff = 0.0
    ohlc = ["open", "high", "low", "close"]
    have = [c for c in ohlc if c in bars.columns]
    for t in points:
        if t >= n - 1:
            continue
        mutated = bars.copy()
        # Drastically scale every future bar; a causal feature at t cannot notice.
        mutated.loc[mutated.index[t + 1 :], have] = mutated.loc[
            mutated.index[t + 1 :], have
        ] * 1000.0
        recomputed = definition.compute(mutated).to_numpy(dtype="float64")
        if not _equal(float(full[t]), float(recomputed[t]), tol):
            n_leaked += 1
            max_diff = max(max_diff, abs(float(full[t]) - float(recomputed[t])))
    ok = n_leaked == 0
    message = "no future leakage" if ok else f"future leakage at {n_leaked} point(s)"
    return LeakageResult(
        ok=ok, n_checked=len(points), n_leaked=n_leaked, max_diff=max_diff, message=message
    )


def run_parity_test(
    definition: FeatureDefinition,
    bars: pd.DataFrame,
    *,
    sample: int = 24,
    tol: float = 1e-9,
) -> ParityResult:
    """Check the offline (batch) table equals the online (incremental) computation."""
    offline = definition.compute(bars).to_numpy(dtype="float64")
    n = len(bars)
    points = _sample_points(n, definition.min_periods, sample)
    n_mismatch = 0
    max_diff = 0.0
    for t in points:
        online_value = float(definition.compute(bars.iloc[: t + 1]).to_numpy(dtype="float64")[-1])
        if not _equal(float(offline[t]), online_value, tol):
            n_mismatch += 1
            max_diff = max(max_diff, abs(float(offline[t]) - online_value))
    ok = n_mismatch == 0
    message = "offline == online" if ok else f"parity violated at {n_mismatch} point(s)"
    return ParityResult(
        ok=ok, n_checked=len(points), n_mismatch=n_mismatch, max_abs_diff=max_diff, message=message
    )


def validate_feature(
    definition: FeatureDefinition,
    bars: pd.DataFrame,
    *,
    label_columns: Sequence[str] = (),
    strict: bool = False,
) -> FeatureValidation:
    """Validate a feature: structural inputs, target leakage, future leakage, parity.

    With ``strict=True`` a failure raises :class:`FeatureError`; otherwise a report is returned.
    """
    reasons: list[str] = []

    missing = [c for c in definition.inputs if c not in bars.columns]
    if missing:
        reasons.append(f"missing input columns: {missing}")
    leaked_labels = sorted(set(definition.inputs) & set(label_columns))
    if leaked_labels:
        reasons.append(f"target leakage: feature reads label column(s) {leaked_labels}")
    structural_ok = not reasons

    leakage = (
        run_leakage_test(definition, bars)
        if structural_ok
        else LeakageResult(ok=False, n_checked=0, n_leaked=0, max_diff=0.0, message="skipped")
    )
    parity = (
        run_parity_test(definition, bars)
        if structural_ok
        else ParityResult(
            ok=False, n_checked=0, n_mismatch=0, max_abs_diff=0.0, message="skipped"
        )
    )
    if not leakage.ok:
        reasons.append(f"future/lookahead leakage: {leakage.message}")
    if not parity.ok:
        reasons.append(f"train/serve parity violation: {parity.message}")

    ok = not reasons
    if strict and not ok:
        raise FeatureError(f"feature {definition.key} rejected: {'; '.join(reasons)}")
    return FeatureValidation(
        feature=definition.key,
        ok=ok,
        structural_ok=structural_ok,
        leakage=leakage,
        parity=parity,
        reasons=reasons,
    )
