"""CAUSAL GUARD -- make the future-invariance leakage PROOF callable from any screen.

WHY THIS ADAPTER EXISTS. libs/features/validation.py implements the strongest leakage test the
desk owns:

    "a causal feature's value at time t must not change when *future* bars (> t) are mutated.
     Every perturbable column is mutated [...] so the test rejects future leakage, lookahead
     bias, hindsight labels, and full-sample normalization on ANY such input."

`run_leakage_test` was called from NOWHERE. The reason is mechanical, not neglect: it takes a
`FeatureDefinition` (a registry object with .compute/.min_periods), while every screen works
with plain numpy return series and closures. There was no bridge, so the proof sat unreachable
and leakage was policed instead by HEURISTICS on outputs -- scripts/leakage_detector.py's
|IC|>0.35, Sharpe>6, gapped-window and horizon-adjacency rails.

THAT DISTINCTION IS THE WHOLE POINT. Heuristics catch leakage that produces implausible numbers.
A feature can leak and still post IC 0.20 and Sharpe 2.5 -- squarely inside every rail, and
promoted. Future invariance is CONSTRUCTIVE: it perturbs every future value (scale+shift for
numerics, flips for bools, displacement for datetimes) and proves the past value cannot move.
It does not ask whether the result looks suspicious; it proves the feature cannot see forward.

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
            f"{name}: {res.message} -- past values moved when future bars were perturbed "
            f"(checked {res.n_checked}, {res.n_leaked} leaked, "
            f"max_diff={res.max_diff:.6g}). "
            "This is a constructive proof of lookahead, not a heuristic warning.")
    return res


def self_test() -> None:
    """Prove the guard bites, on the WIDEST real schema, not the narrowest.

    Until R0289 this fixture held OHLC only -- structurally incapable of revealing that the
    mutation skipped every other column, while the guard waved through funding.shift(-1),
    a funding[-1] broadcast, and full-sample z(funding) (all demonstrated live). The bronze
    D1 schema is the fixture now, and those three exact leaks are the positive controls.
    """
    import numpy as np
    n = 300
    rng = np.random.default_rng(7)
    bars = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=n, freq="1D", tz="UTC"),
        "open": np.linspace(100, 120, n), "high": np.linspace(101, 121, n),
        "low": np.linspace(99, 119, n), "close": np.linspace(100, 120, n),
        "volume": rng.uniform(100, 1000, size=n),
        "taker_buy_frac": rng.uniform(0.3, 0.7, size=n),
        "funding": rng.normal(0.0, 1e-4, size=n),
        "basis": rng.normal(0.0, 5e-4, size=n),
    })
    # negative controls: causal features on price AND non-price inputs must pass
    assert_causal(lambda d: d["close"].rolling(20).mean(), bars, name="sma20", min_periods=20)
    assert_causal(lambda d: d["funding"].rolling(3, min_periods=1).mean(), bars,
                  name="funding_ma3", min_periods=3)
    # positive controls: each must raise, or the guard is blind on that axis
    leaks: list[tuple[str, Callable[[pd.DataFrame], pd.Series]]] = [
        ("peek_close", lambda d: d["close"].shift(-1)),
        ("peek_funding", lambda d: d["funding"].shift(-1)),
        ("funding_last_bar", lambda d: pd.Series(d["funding"].iloc[-1], index=d.index)),
        ("funding_full_z", lambda d: (d["funding"] - d["funding"].mean()) / d["funding"].std()),
    ]
    for leak_name, leak_fn in leaks:
        try:
            assert_causal(leak_fn, bars, name=leak_name, min_periods=1)
        except LeakageError:
            continue
        raise AssertionError(f"causal guard failed to catch known leak {leak_name!r}")
