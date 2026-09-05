"""Controls for the shift-test leak detector -- both directions, on planted ground truth.

WHY THIS FILE EXISTS. shift_ic is a LEAK DETECTOR: its output gets read as evidence that a signal
contains future information, and the desk acts on that reading. It had never been shown to give
the right answer on data whose truth was known.

It did not. For a ratio signal whose denominator is the target's own price -- which is every
cross-venue premium the desk screens -- the old implementation shifted only the NUMERATOR leg
(signal[i+shift] over fx[i]/gb[i]), which does not shift the signal at all: it rebuilds it as
approximately gb[i+1]/gb[i], the forward return itself. It reported a +1d cell of +0.931 on a
premium that was i.i.d. noise by construction.

THE COST OF THAT FALSE POSITIVE IS ON THE RECORD. On 2026-07-29 it fired on kimchi, the reading
was taken as proof of a ~73% timestamp artifact, and a `+1 day` Upbit keying "fix" was shipped in
response. The premise was false (Upbit dailies are UTC-midnight-boundary), the "fix" 24h-mispaired
three days of live collection, and a refuted mechanism went into the graveyard as fact (R0067).
A detector that fires on clean data is worse than no detector: it gets "fixed" in the direction of
the damage, by someone doing exactly what the evidence appeared to say.

The rule these tests encode: NEVER ship a detector without showing it (a) stays quiet on data
known to be clean and (b) still fires on the defect it exists to catch.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.validation.shift_leak import shift_ic

_N = 400


def _world(seed: int = 7) -> tuple[list[str], np.ndarray, np.ndarray, dict, dict]:
    """A synthetic venue pair: BTC random walk, flat FX -- the premium is the only free variable."""
    rng = np.random.default_rng(seed)
    dates = [f"2025-{1 + i // 28:02d}-{1 + i % 28:02d}" for i in range(_N)]
    px = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, _N)))
    fxv = np.full(_N, 1300.0)
    gb = {d: float(p) for d, p in zip(dates, px, strict=False)}
    fx = {d: float(f) for d, f in zip(dates, fxv, strict=False)}
    return dates, px, fxv, gb, fx


def _upbit_from_premium(dates: list[str], px: np.ndarray, fxv: np.ndarray,
                        prem: np.ndarray) -> dict[str, float]:
    """upbit_krw = binance_usd * fx * (1 + premium) -- the exact identity the screen inverts."""
    return {d: float(p * f * (1 + q))
            for d, p, f, q in zip(dates, px, fxv, prem, strict=False)}


@pytest.mark.parametrize("shift", [-1, 0, 1])
def test_clean_premium_is_not_flagged(shift: int) -> None:
    """NEGATIVE CONTROL: an i.i.d. premium has zero predictive content. No cell may be large.

    The old implementation returned +0.931 at shift=+1 here. That single number is what the
    2026-07-29 keying regression was built on.
    """
    dates, px, fxv, gb, fx = _world()
    rng = np.random.default_rng(11)
    upbit = _upbit_from_premium(dates, px, fxv, rng.normal(0, 0.005, _N))

    ic = shift_ic(upbit, gb, shift, fx)

    assert abs(ic) < 0.25, (
        f"shift={shift:+d} reported IC {ic:+.3f} on a premium that is independent of returns by "
        "construction. The detector is manufacturing its own evidence -- see R0067."
    )


def test_planted_lookahead_is_still_caught() -> None:
    """POSITIVE CONTROL: a premium built from tomorrow's return MUST show up.

    Without this, 'the detector stays quiet' is satisfied by a detector that is simply broken.
    """
    dates, px, fxv, gb, fx = _world()
    ret = np.zeros(_N)
    ret[1:] = px[1:] / px[:-1] - 1.0
    fwd = np.roll(ret, -1)
    rng = np.random.default_rng(13)
    leaky = 0.005 * np.sign(fwd) + rng.normal(0, 0.001, _N)

    ic0 = shift_ic(_upbit_from_premium(dates, px, fxv, leaky), gb, 0, fx)

    assert ic0 > 0.4, (
        f"a premium containing tomorrow's return sign scored only {ic0:+.3f} at shift 0 -- "
        "the detector no longer detects the thing it exists to detect."
    )


def test_stale_label_shows_as_plus_one_dominance() -> None:
    """The bithumb SHAPE: a series whose labels lag its content peaks at +1d, not 0d.

    This is the pattern the production verdict rule keys on (abs(+1d) > 1.5x abs(0d)), so it needs
    a case where that rule is known to be right -- otherwise the rule is untested prose.
    """
    dates, px, fxv, gb, fx = _world()
    ret = np.zeros(_N)
    ret[1:] = px[1:] / px[:-1] - 1.0
    fwd = np.roll(ret, -1)
    rng = np.random.default_rng(17)
    honest = 0.005 * np.sign(fwd) + rng.normal(0, 0.001, _N)
    stale = np.roll(honest, 1)          # label i carries what really belonged to i-1
    upbit = _upbit_from_premium(dates, px, fxv, stale)

    s0, s1 = shift_ic(upbit, gb, 0, fx), shift_ic(upbit, gb, 1, fx)

    assert abs(s1) > abs(s0) * 1.5 and abs(s1) > 0.3, (
        f"stale-labelled series scored 0d {s0:+.3f} / +1d {s1:+.3f}; the production rule "
        "(+1d dominates 0d) would NOT have flagged it."
    )
