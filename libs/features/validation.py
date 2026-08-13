"""Feature validation: leakage detection and train/serve parity.

The single mechanism behind leakage detection is **future invariance**: a causal feature's
value at time t must not change when *future* bars (> t) are mutated. Every perturbable
column is mutated -- numeric columns are scaled AND shifted (a pure scaling leaves ratio and
range leaks invariant), booleans are flipped, datetimes are displaced -- so the test rejects
future leakage, lookahead bias, hindsight labels, and full-sample normalization on ANY such
input. A definition consuming a column the mutation cannot perturb (object/string dtypes)
gets a loud UNTESTABLE failure, never a silent pass: until R0289 only OHLC was mutated, and
features built from volume/taker_buy_frac/funding/basis passed unconditionally -- the
UNMEASURED-REPORTED-AS-OK class, on the desk's only repeat-survivor family. R0461 made that
refusal MECHANISED rather than enumerated -- consumption is probed, not read off the
caller's ``inputs`` declaration -- and published the perturbation denominator, because a
verdict of "nothing moved" over zero perturbed columns is an identity, not a proof (L1.57).
Parity is a separate check that the offline (batch) and online (incremental) computations
agree.
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
    #: Columns present in the bars that the mutation could not perturb (object/string
    #: dtypes). Informational unless the definition CONSUMES one, which fails the test.
    untested_columns: tuple[str, ...] = ()
    #: L1.57 DENOMINATOR. How many columns the mutation actually moved to earn this verdict.
    #: `ok=True` over zero perturbed columns is VACUOUS and is refused at the exit site: the
    #: mutant frame equals the baseline, so "past values did not move" is arithmetically
    #: guaranteed and carries no information about the feature.
    n_perturbed_columns: int = 0
    #: The columns behind that count -- measured from the frame handed in, never a literal.
    perturbed_columns: tuple[str, ...] = ()
    #: Unperturbable columns the definition was MEASURED to consume (probe, not declaration).
    consumed_untestable_columns: tuple[str, ...] = ()

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


#: Pure scaling leaves ratio/range leaks (high/low, spreads) and sign leaks invariant; the
#: additive shift breaks ratios and flips the sign of small-magnitude series (funding, basis).
_PERTURB_SCALE = 1000.0
_PERTURB_SHIFT = 7.0
_PERTURB_TIMEDELTA = pd.Timedelta(days=1000, hours=7)  # hours too, so .dt.hour leaks move


#: Whole-column substitutes used to MEASURE whether a definition reads an unperturbable
#: column. Several, because one sentinel can coincide with the column's own values (a probe
#: that does not change the column proves nothing) or with the feature's output.
_PROBE_SENTINELS: tuple[object, ...] = (None, "", 0)


def _differs(a: np.ndarray, b: np.ndarray) -> bool:
    if a.shape != b.shape:
        return True
    return not bool(np.array_equal(a, b, equal_nan=True))


def _consumes_column(
    definition: FeatureDefinition, base: pd.DataFrame, full: np.ndarray, col: str
) -> bool:
    """MEASURE whether ``definition`` reads ``col`` -- never ask what it DECLARED.

    Keying the UNTESTABLE refusal on ``definition.inputs`` re-created R0289 one level up:
    :func:`libs.features.causal_guard.as_feature` defaults ``inputs=("close",)``, so every
    ad-hoc closure declared it read close no matter what it actually read, and an
    unperturbable column it really consumed never intersected the declaration. The
    declaration is a claim; this is the observation. Corrupt the WHOLE column and watch the
    output: if it moves, the column is consumed. A raise is also consumption -- the feature
    read it hard enough to break on it. If no sentinel changes the column, the probe is
    UNDECIDABLE and we fail closed (L1.28a): absence of evidence is not a pass.
    """
    original = base[col]
    probed_at_all = False
    for sentinel in _PROBE_SENTINELS:
        probed = base.copy()
        try:
            probed[col] = sentinel
        except Exception:  # a sentinel this column rejects proves nothing; try the next
            continue
        if original.equals(probed[col]):
            continue  # the probe did not move the input, so it cannot test the output
        probed_at_all = True
        try:
            out = definition.compute(probed).to_numpy(dtype="float64")
        except Exception:  # breaking on a corrupted column IS consumption -- fail closed
            return True
        if _differs(full, out):
            return True
    return not probed_at_all


def _perturbable(bars: pd.DataFrame) -> tuple[list[str], list[str], list[str], list[str]]:
    """Split columns into (scalable numeric, flippable bool, shiftable datetime, unperturbable)."""
    scalable: list[str] = []
    flippable: list[str] = []
    shiftable: list[str] = []
    untestable: list[str] = []
    for c in bars.columns:
        s = bars[c]
        if pd.api.types.is_bool_dtype(s):
            flippable.append(c)
        elif pd.api.types.is_numeric_dtype(s):
            scalable.append(c)
        elif pd.api.types.is_datetime64_any_dtype(s):
            shiftable.append(c)
        else:
            untestable.append(c)
    return scalable, flippable, shiftable, untestable


def run_leakage_test(
    definition: FeatureDefinition,
    bars: pd.DataFrame,
    *,
    sample: int = 24,
    tol: float = 1e-9,
) -> LeakageResult:
    """Detect lookahead by mutating future bars and checking past values are invariant.

    EVERY perturbable column is mutated, not just OHLC: until R0289 only
    ``['open','high','low','close']`` were scaled, so a feature computed from any other
    input (volume, taker_buy_frac, funding, basis, ...) passed unconditionally regardless
    of whether it leaked.

    R0461 closed the two ways that verdict could still be earned over nothing:

    1. **The refusal is MEASURED, not declared.** R0289 keyed the UNTESTABLE refusal on
       ``definition.inputs``, and :func:`libs.features.causal_guard.as_feature` defaults
       that to ``("close",)`` -- so an ad-hoc closure reading an object-dtype ``funding``
       never intersected its own declaration and ``funding.shift(-1)`` passed again, one
       level up from the defect R0289 fixed. Consumption is now probed
       (:func:`_consumes_column`); the declaration is unioned in and can only ADD.
    2. **The denominator is published and fenced (L1.57).** ``n_perturbed_columns`` and
       ``n_checked`` count what THIS RUN moved and compared. A pass over zero perturbed
       columns, or zero evaluated points, is arithmetically guaranteed and is refused as
       VACUOUS rather than reported as ``ok``.
    """
    scalable, flippable, shiftable, untestable = _perturbable(bars)
    untestable_set = set(untestable)
    perturbed_columns = tuple(c for c in bars.columns if c not in untestable_set)
    n_perturbed = len(perturbed_columns)
    # L1.57 DENOMINATOR, read BEFORE any verdict. With nothing perturbable every mutant frame
    # is byte-identical to the baseline, so `n_leaked == 0` is an identity, not a measurement.
    if n_perturbed == 0:
        return LeakageResult(
            ok=False, n_checked=0, n_leaked=0, max_diff=0.0,
            untested_columns=tuple(untestable), n_perturbed_columns=0, perturbed_columns=(),
            message=(
                f"VACUOUS: perturbed 0 of {len(bars.columns)} column(s) "
                f"{tuple(untestable)} -- no future value was moved, so 'no future leakage' "
                "is an empty claim, not a proof (L1.57 denominator)"
            ),
        )
    # Cast numerics to float64 ONCE and compute the baseline on the same view the mutants
    # use, so dtype effects cancel instead of reading as leaks (e.g. ns-epoch int64 columns
    # lose precision under a float cast -- identically on both sides).
    base = bars.copy()
    if scalable:
        base[scalable] = base[scalable].astype("float64")
    full = definition.compute(base).to_numpy(dtype="float64")
    # Consumption is MEASURED (probe), then unioned with what was declared -- a declaration
    # can only ADD a refusal here, never withdraw one.
    consumed_untestable = sorted(
        {c for c in untestable if _consumes_column(definition, base, full, c)}
        | (set(definition.inputs) & untestable_set)
    )
    if consumed_untestable:
        return LeakageResult(
            ok=False, n_checked=0, n_leaked=0, max_diff=0.0,
            untested_columns=tuple(untestable), n_perturbed_columns=n_perturbed,
            perturbed_columns=perturbed_columns,
            consumed_untestable_columns=tuple(consumed_untestable),
            message=(
                f"UNTESTABLE: input column(s) {consumed_untestable} cannot be perturbed "
                "(unsupported dtype) and the feature was measured to read them, so "
                "future-invariance cannot be certified"
            ),
        )
    n = len(base)
    points = _sample_points(n, definition.min_periods, sample)
    n_leaked = 0
    n_evaluated = 0
    max_diff = 0.0
    for t in points:
        if t >= n - 1:
            continue
        n_evaluated += 1
        mutated = base.copy()
        future = mutated.index[t + 1 :]
        # Drastically perturb every future bar; a causal feature at t cannot notice.
        if scalable:
            mutated.loc[future, scalable] = (
                mutated.loc[future, scalable] * _PERTURB_SCALE + _PERTURB_SHIFT
            )
        if flippable:
            mutated.loc[future, flippable] = ~mutated.loc[future, flippable]
        for c in shiftable:
            mutated.loc[future, c] = mutated.loc[future, c] + _PERTURB_TIMEDELTA
        recomputed = definition.compute(mutated).to_numpy(dtype="float64")
        if not _equal(float(full[t]), float(recomputed[t]), tol):
            n_leaked += 1
            max_diff = max(max_diff, abs(float(full[t]) - float(recomputed[t])))
    # Second denominator, same law: `n_checked` used to be `len(points)`, which counts the
    # points the sampler PROPOSED, including any dropped by the `t >= n - 1` skip above. A
    # verdict earned over zero evaluated points is vacuous exactly as a verdict over zero
    # perturbed columns is.
    if n_evaluated == 0:
        return LeakageResult(
            ok=False, n_checked=0, n_leaked=0, max_diff=0.0,
            untested_columns=tuple(untestable), n_perturbed_columns=n_perturbed,
            perturbed_columns=perturbed_columns,
            message=(
                f"VACUOUS: evaluated 0 of {len(points)} proposed sample point(s) on {n} bar(s) "
                f"at min_periods={definition.min_periods} -- nothing was compared "
                "(L1.57 denominator)"
            ),
        )
    ok = n_leaked == 0
    message = (
        f"no future leakage (perturbed {n_perturbed} column(s) at {n_evaluated} point(s))"
        if ok
        else f"future leakage at {n_leaked} point(s)"
    )
    return LeakageResult(
        ok=ok, n_checked=n_evaluated, n_leaked=n_leaked, max_diff=max_diff,
        untested_columns=tuple(untestable), n_perturbed_columns=n_perturbed,
        perturbed_columns=perturbed_columns, message=message
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
