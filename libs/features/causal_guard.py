"""CAUSAL GUARD -- make the future-invariance leakage PROOF callable from any screen.

WHY THIS ADAPTER EXISTS. libs/features/validation.py implements the strongest leakage test the
desk owns:

    "a causal feature's value at time t must not change when *future* bars (> t) are mutated.
     This one test rejects future leakage, lookahead bias, hindsight labels, and full-sample
     normalization."

`run_leakage_test` was called from NOWHERE. The reason is mechanical, not neglect: it takes a
`FeatureDefinition` (a registry object with .compute/.min_periods), while every screen works
with plain numpy return series and closures. There was no bridge, so the proof sat unreachable
and leakage was policed instead by HEURISTICS on outputs -- scripts/leakage_detector.py's
|IC|>0.35, Sharpe>6, gapped-window and horizon-adjacency rails.

THAT DISTINCTION IS THE WHOLE POINT. Heuristics catch leakage that produces implausible numbers.
A feature can leak and still post IC 0.20 and Sharpe 2.5 -- squarely inside every rail, and
promoted. Future invariance is CONSTRUCTIVE: it mutates the future by 1000x and proves the past
value cannot move. It does not ask whether the result looks suspicious; it proves the feature
cannot see forward.

This matters more here than almost anywhere, because the desk's own failure autopsy is
38% WRONG_TIMING + 26% DATA_QUALITY = 64% MEASUREMENT failures, not alpha failures. The tool
that attacks the dominant failure class by construction was one adapter away from usable.

USAGE -- any screen, any closure, one line:

    from libs.features.causal_guard import assert_causal
    assert_causal(lambda df: df["close"].rolling(20).mean(), bars, name="sma20")

Raises LeakageError on any leak. Fail closed: a signal that cannot be proven causal must never
reach a gate, and "we did not check" is how 64% of this desk's refutations happened.
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from libs.features.definition import FeatureDefinition
from libs.features.validation import LeakageResult, run_leakage_test

__all__ = ["LeakageError", "as_feature", "assert_causal", "check_causal"]


class LeakageError(AssertionError):
    """A signal's past values moved when the future was mutated. Never catch to proceed."""


def as_feature(fn: Callable[[pd.DataFrame], pd.Series], *, name: str = "adhoc",
               min_periods: int = 1, inputs: tuple[str, ...] = ("close",),
               version: int = 1) -> FeatureDefinition:
    """Wrap a plain `bars -> series` callable as a FeatureDefinition the validator accepts.

    `min_periods` matters: the validator skips warm-up points, so a rolling-20 signal declared
    with min_periods=1 gets tested on indices where it is still NaN-padded and can report a
    spurious result. Declare the real warm-up.
    """
    return FeatureDefinition(name=name, version=version, compute=fn, inputs=inputs,
                             category="adhoc", description="ad-hoc screen signal",
                             min_periods=max(1, int(min_periods)))


def check_causal(fn: Callable[[pd.DataFrame], pd.Series], bars: pd.DataFrame, *,
                 name: str = "adhoc", min_periods: int = 1, sample: int = 24,
                 tol: float = 1e-9) -> LeakageResult:
    """Run the future-invariance proof and RETURN the result (no raise). Pure-ish, testable."""
    return run_leakage_test(as_feature(fn, name=name, min_periods=min_periods),
                            bars, sample=sample, tol=tol)


def assert_causal(fn: Callable[[pd.DataFrame], pd.Series], bars: pd.DataFrame, *,
                  name: str = "adhoc", min_periods: int = 1, sample: int = 24,
                  tol: float = 1e-9) -> LeakageResult:
    """Prove the signal cannot see the future, or RAISE.

    Fail closed by design. The alternative -- warn and continue -- is the fail-open-guard class
    this codebase's own auditor prompt lists first among its measured defect history.
    """
    res = check_causal(fn, bars, name=name, min_periods=min_periods, sample=sample, tol=tol)
    if not res.ok:
        raise LeakageError(
            f"{name}: {res.message} -- past values moved when future bars were scaled 1000x "
            f"(checked {res.n_checked}, {res.n_leaked} leaked, "
            f"max_diff={res.max_diff:.6g}). "
            "This is a constructive proof of lookahead, not a heuristic warning.")
    return res


def self_test() -> None:
    """Prove the guard bites: a causal signal passes, a deliberately leaky one raises."""
    import numpy as np
    n = 300
    bars = pd.DataFrame({"open": np.linspace(100, 120, n), "high": np.linspace(101, 121, n),
                         "low": np.linspace(99, 119, n), "close": np.linspace(100, 120, n)})
    assert_causal(lambda d: d["close"].rolling(20).mean(), bars, name="sma20", min_periods=20)
    try:                                    # shift(-1) reads tomorrow -- must be caught
        assert_causal(lambda d: d["close"].shift(-1), bars, name="peek", min_periods=1)
    except LeakageError:
        return
    raise AssertionError("causal guard failed to catch a shift(-1) lookahead")
