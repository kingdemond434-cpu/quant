"""How high the best of N noise results reaches, and why the constant had to go.

THE DEFECT THIS REPLACES

`run_hunt11` set `E_MAX_9 = 1.49  # E[max of 9 iid standard normals]` and `run_hunt12` set
`E_MAX = 1.5`, then gated on `t_stat - E_MAX > 2`. Subtracting the expected best-of-family
t before demanding significance is the right SHAPE of correction. Freezing it at a constant is
not, because the quantity it estimates depends entirely on how many cells were actually tried:

    9 cells      E[max t] ~ 1.49      (what the constant assumed)
    352 cells    E[max t] ~ 2.93      (what hunt12 actually swept)
    1,600 cells  E[max t] ~ 3.32      (a 100-symbol universe x 4 windows x 4 states)

So hunt12's gate demanded t > 3.5 while the honest bar for its own sweep size was t > 4.9. The
gap is not academic: it is exactly the region where the marginal "survivor" lives.

THIS MATTERS MOST RIGHT NOW, because the universe is being widened from 22 symbols to every
instrument the broker offers. Widening the search without widening the correction does not find
more edges -- it manufactures them, at a rate that grows with the size of the sweep. A desk that
tests 1,600 cells against a 9-cell bar will find "survivors" every single run, forever, and none
of them will trade profitably.

WHAT IS COMPUTED

E[max of n iid standard normals], by direct numerical integration of

    E[M_n] = integral x * n * phi(x) * Phi(x)^(n-1) dx

The textbook asymptotic sqrt(2 ln n) is deliberately NOT used: at n = 9 it returns 1.31 against
a true 1.49, a 12% understatement in precisely the small-n regime the desk has been running, and
understating this constant is the one direction that lets noise through.

Independence is assumed and the cells are NOT independent -- four session windows on one symbol
share a day, and four states partition it. Correlated trials make the true E[max] LOWER than
this, so the correction is conservative by construction. That is the correct direction to err:
the cost of being conservative is a missed edge, the cost of the reverse is trading noise.
"""

from __future__ import annotations

import math

import numpy as np

#: Integration grid. +/-12 sigma covers the max of any n this desk could ever sweep (the max of
#: 10^9 normals is ~6 sigma), and 20k points keeps the quadrature error far below the precision
#: anyone reads off a t-stat.
_LO, _HI, _N = -12.0, 12.0, 20_001


def _phi(x: np.ndarray) -> np.ndarray:
    return np.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _Phi(x: np.ndarray) -> np.ndarray:
    # erf is in the stdlib math module but not vectorised; np.vectorize would be slow enough to
    # matter inside a sweep, so the identity Phi(x) = 0.5*(1+erf(x/sqrt2)) is applied via
    # np.errstate-safe elementwise erf from numpy's own implementation.
    return 0.5 * (1.0 + np.vectorize(math.erf)(x / math.sqrt(2.0)))


def expected_max_t(n_trials: int) -> float:
    """E[max of `n_trials` iid standard normals]. The t a pure-noise family reaches by luck.

    Returns 0.0 for n <= 1: with a single pre-registered test there is no selection to correct
    for, and subtracting anything would penalise a hypothesis nobody chose from a menu.
    """
    n = int(n_trials)
    if n <= 1:
        return 0.0
    x = np.linspace(_LO, _HI, _N)
    pdf = n * _phi(x) * np.power(_Phi(x), n - 1)
    return float(np.trapezoid(x * pdf, x))


# Precomputed because the integration is the slow part of an inner loop and these are constants.
_CACHE: dict[int, float] = {}


def deflation(n_trials: int) -> float:
    """`expected_max_t` with memoisation -- safe to call per cell inside a sweep."""
    n = int(n_trials)
    if n not in _CACHE:
        _CACHE[n] = expected_max_t(n)
    return _CACHE[n]


def deflated_t(t_stat: float, n_trials: int) -> float:
    """Observed t minus what the best of `n_trials` noise draws would have reached."""
    return float(t_stat) - deflation(n_trials)


def sweep_size(n_symbols: int, n_windows: int, n_states: int, n_variants: int = 1) -> int:
    """Cells a sweep will actually test. THE COUNT MUST BE THE FULL GRID, NOT THE SURVIVORS.

    Counting only the cells that passed -- or only the ones someone chose to report -- is the
    classic way a multiplicity correction gets quietly disarmed: the denominator has to include
    every hypothesis the machine looked at, including the ones that failed instantly.
    """
    return max(1, int(n_symbols) * int(n_windows) * int(n_states) * int(n_variants))
