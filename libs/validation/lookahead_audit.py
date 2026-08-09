"""MECHANICAL look-ahead detection. Causality that is asserted in a docstring is not causality.

PROVENANCE. Two transcripts in the 2026-08-01 batch describe the same idea independently, which
is part of why it is worth building: Algovibes' regime study ("take 20 random days, replace
everything after with random noise, ask the detector for its label again -- if the label changes,
the detector was cheating; 20 of 20 held") and its 3.2-million-backtest study (a deliberately
rigged signal that knows the current candle scores Sharpe > 100 when allowed to trade it, and
collapses below zero once the engine's one-bar delay is applied).

WHY THIS DESK NEEDS IT, stated as a measurement rather than a worry. `grep -rln "look.ahead"`
across libs/ and scripts/ returns EIGHT modules -- crypto_adapter, backtest/engine,
backtest/strategy, axis_screen, microstructure, transcript_candidates, crossasset, label_factory
-- every one of them asserting in prose that it is causal. `grep -rc "def test_"` across tests/
returns not one file testing it. Eight claims, zero readers. That is rubric class 1 on this
desk's own list: a thing is only true if something READS it.

And look-ahead is the failure that most deserves a mechanical check, because it is silent and
enormous. It does not raise, it does not look wrong, it produces a beautiful equity curve, and
every downstream statistic -- the permutation p-value, the monkey beat rate, the deflated Sharpe --
faithfully certifies a number computed from information the strategy could not have had. Every
control this desk built in the 2026-08-01 batch is downstream of the assumption that positions
were knowable when they were taken. Nothing was checking it.

THE TWO PROBES ARE COMPLEMENTARY.

    future_invariance    tests an INDICATOR: does its value at bar i depend on data after bar i?
    perfect_foresight_probe  tests a HARNESS: if handed a signal that knows the answer, does the
                         scoring path refuse to reward it?

The first catches a leaky feature. The second catches a leaky backtester, which no amount of
careful feature engineering will save you from. A desk needs both because they fail in different
places and each is invisible to the other.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np

#: Probe points per audit. The source used 20; more is cheap here because the desk's indicators
#: are numpy-vectorised, and each probe is an independent chance to catch a leak.
DEFAULT_PROBES = 24

#: Draws per probe point. One perturbed future can coincidentally leave a leaky value unchanged
#: (a max() over a window whose maximum happens to survive the shuffle); several rarely do.
DEFAULT_DRAWS = 3

_EPS = 1e-9


def perturb_future(
    series: np.ndarray, index: int, *, rng: np.random.Generator, scale: float = 1.5
) -> np.ndarray:
    """A copy of `series` identical up to `index` and deliberately different after it.

    BOTH SHUFFLED AND RESCALED, because either alone misses real leaks. Shuffling preserves the
    multiset, so a future-reading `max()` over a window can survive it unchanged; rescaling moves
    every level, so an indicator normalised by a future statistic still moves. Doing both makes
    the perturbed future differ in ORDER and in LEVEL, and a genuinely causal function is blind
    to both.
    """
    out = np.array(series, dtype="float64", copy=True)
    tail = out[index + 1:]
    if tail.size == 0:
        return out
    out[index + 1:] = rng.permutation(tail) * scale
    return out


def future_invariance(
    fn: Callable[[np.ndarray], np.ndarray],
    series: np.ndarray,
    *,
    rng: np.random.Generator,
    n_probes: int = DEFAULT_PROBES,
    n_draws: int = DEFAULT_DRAWS,
    warmup: float = 0.3,
    atol: float = 1e-8,
) -> dict[str, object]:
    """Does `fn(series)[i]` change when everything after bar i is replaced?

    If it does, `fn` reads the future at bar i and every backtest built on it is fiction.

    PROBES SKIP THE WARM-UP because an indicator that is NaN for its first N bars would report a
    spurious pass there -- NaN equals NaN under the comparison used, so a leaky indicator could
    hide behind its own warm-up. Probes are drawn from the last `1 - warmup` of the series, where
    the indicator is actually producing values.

    NaN IS TREATED AS A VALUE, not skipped: an indicator that returns a number on real data and
    NaN on perturbed data has just told you it depends on the future.
    """
    x = np.asarray(series, dtype="float64")
    n = x.size
    if n < 50:
        raise ValueError(f"need at least 50 bars to probe, got {n}")
    base = np.asarray(fn(x), dtype="float64")
    if base.size != n:
        raise ValueError(f"fn returned {base.size} values for {n} bars -- must be aligned")

    lo = int(n * warmup)
    hi = n - 2                      # need at least one bar of future to perturb
    if hi <= lo:
        raise ValueError("series too short for the requested warmup")
    probes = rng.choice(np.arange(lo, hi), size=min(n_probes, hi - lo), replace=False)

    leaks: list[dict[str, object]] = []
    for i in sorted(int(p) for p in probes):
        for d in range(n_draws):
            got = np.asarray(fn(perturb_future(x, i, rng=rng)), dtype="float64")
            a, b = base[i], got[i]
            same = (np.isnan(a) and np.isnan(b)) or (
                np.isfinite(a) and np.isfinite(b) and abs(a - b) <= atol)
            if not same:
                leaks.append({"index": i, "draw": d, "real": _j(a), "perturbed": _j(b)})
                break               # one confirmed leak at this bar is enough
    n_probed = len(probes)
    return {
        "n_probes": n_probed,
        "n_draws_per_probe": n_draws,
        "n_leaking_probes": len(leaks),
        "causal": not leaks,
        "leaks": leaks[:8],
        "verdict": (
            f"CAUSAL: {n_probed} probes x {n_draws} draws, no probe changed when the future was "
            "replaced." if not leaks else
            f"LOOK-AHEAD: {len(leaks)} of {n_probed} probes CHANGED when data after the bar was "
            "replaced. The value at those bars depends on information not yet available, so every "
            "backtest statistic computed from this is fiction."),
    }


def perfect_foresight_probe(
    score: Callable[[np.ndarray, np.ndarray], float],
    market_returns: np.ndarray,
    *,
    threshold: float = 0.5,
) -> dict[str, object]:
    """Hand the scorer a signal that KNOWS each bar's return. Does the scorer refuse to reward it?

    The canary for a leaky HARNESS rather than a leaky feature. `score(positions, returns)` must
    apply the lag itself -- that is the thing under test. A correctly-lagged scorer gives the
    cheating signal roughly nothing, because knowing bar i's return tells you nothing about bar
    i+1. A scorer that lets the signal trade the bar it already knows returns an absurd number.

    ``threshold`` is in per-bar Sharpe and is deliberately loose. The failure this catches is not
    subtle: an unlagged perfect-foresight signal scores near the theoretical maximum, not slightly
    high. Anything above the threshold means the scoring path is letting the signal act on the bar
    it already saw.
    """
    r = np.asarray(market_returns, dtype="float64")
    cheat = np.sign(r)
    got = float(score(cheat, r))
    leaked = np.isfinite(got) and got > threshold
    return {
        "perfect_foresight_score": got if np.isfinite(got) else None,
        "threshold": threshold,
        "harness_leaks": bool(leaked),
        "verdict": (
            f"HARNESS LEAKS: a signal that knows each bar's own return scored {got:.3f}, above "
            f"the {threshold} threshold. The scoring path is letting positions act on the bar "
            "they were derived from -- every result it has ever produced is inflated."
            if leaked else
            f"HARNESS CLEAN: perfect foresight scored {got:.3f}, at or below {threshold}. "
            "Knowing bar i tells you nothing about bar i+1, which is the correct answer."),
    }


def audit_many(
    named: Sequence[tuple[str, Callable[[np.ndarray], np.ndarray]]],
    series: np.ndarray,
    *,
    rng: np.random.Generator,
    **kw: object,
) -> dict[str, object]:
    """Run `future_invariance` over a set of named indicators and summarise.

    A FAILING INDICATOR IS REPORTED, NEVER RAISED. One leaky feature must not stop the audit of
    the other forty -- the whole point is to get the full list in one pass, because a partial
    audit that stopped at the first problem would be read as "only one problem".
    """
    results: dict[str, object] = {}
    leaking: list[str] = []
    errored: dict[str, str] = {}
    for name, fn in named:
        try:
            rep = future_invariance(fn, series, rng=rng, **kw)  # type: ignore[arg-type]
        except Exception as exc:
            errored[name] = str(exc)[:200]
            continue
        results[name] = rep
        if not rep["causal"]:
            leaking.append(name)
    return {
        "n_audited": len(results),
        "n_leaking": len(leaking),
        "leaking": leaking,
        "errored": errored,
        "results": results,
        "verdict": (f"{len(leaking)} of {len(results)} indicators read the future: {leaking}"
                    if leaking else
                    f"all {len(results)} audited indicators are causal at the probed bars"),
    }


def _j(v: float) -> float | None:
    return None if not np.isfinite(v) else float(v)
