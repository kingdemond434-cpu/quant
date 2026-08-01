"""HOW MANY INDEPENDENT BETS IS THIS COHORT ACTUALLY MAKING? -- with an external benchmark.

THE NUMBER THAT MAKES THIS MEASURABLE. The 2026-08-01 transcript batch supplied one genuinely
useful statistic: a published study of 101 real production alphas found their AVERAGE PAIRWISE
CORRELATION was 15.9% (the "101 Formulaic Alphas" line of work; the platform described is
WorldQuant BRAIN, which is public and free to join). Until now this desk could measure its own
cohort correlation but had nothing to compare it against -- and a number with no benchmark is a
number nobody acts on.

WHY IT MATTERS MORE THAN IT LOOKS. Under an equicorrelation approximation, N signals with average
pairwise correlation rho are worth about

    N_eff = N / (1 + (N - 1) * rho)

independent bets. Run that on the benchmark itself and the result is uncomfortable in a useful
way: 101 alphas at rho = 0.159 are worth 101 / (1 + 100 * 0.159) = 6.0 independent bets. A
professional, deliberately-diversified library of a hundred signals is SIX bets. That reframes
what a large campaign is: past a few dozen correlated candidates, N stops buying information and
only buys multiplicity burden -- which is precisely what this desk measured independently when
power came out identical at N = 420, 100, 30 and 5.

So the honest reading of a big campaign is not "420 hypotheses tested". It is N_eff, and the gap
between the two is the size of the illusion.

RELATIONSHIP TO effective_n_tests IN scripts/audit_gate_power.py. That one uses the participation
ratio of the correlation matrix's eigenvalues -- more general, since it does not assume every pair
is equally correlated, but it has a floor at T < N (~178 of 420 on genuinely independent columns)
which makes its absolute value unreadable. This one assumes equicorrelation, which is cruder, but
it is comparable to a published external number and has no such floor. They answer the same
question from opposite directions, and where they disagree the disagreement is the finding: a
participation ratio far above the equicorrelation estimate means the cohort has a few strong
clusters rather than uniform redundancy, which is a different problem with a different fix.

NOTHING HERE PROMOTES ANYTHING. This measures the SHAPE of a candidate set. A cohort of six
independent bets can still be six worthless ones.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

#: Average pairwise correlation of 101 real production alphas, from the published study named in
#: the 2026-08-01 transcript batch. The desk's own cohorts are read AGAINST this, not against zero
#: -- zero is unreachable and comparing to it makes every real cohort look broken.
BENCHMARK_MEAN_CORR = 0.159
BENCHMARK_N = 101

#: Below this many observations a correlation matrix estimated from T samples on N series is
#: dominated by estimation noise (the Marchenko-Pastur regime), and the mean off-diagonal
#: correlation is biased UPWARD. Reported rather than silently tolerated.
_MIN_OBS_PER_SERIES = 3


@dataclass(frozen=True)
class Independence:
    n_series: int
    n_obs: int
    mean_corr: float
    median_corr: float
    n_eff: float
    n_eff_benchmark: float
    ratio_to_benchmark: float
    noise_dominated: bool
    verdict: str

    def summary(self) -> str:
        return (f"{self.n_series} candidates, mean pairwise corr {self.mean_corr:.3f} "
                f"-> {self.n_eff:.1f} independent bets "
                f"(benchmark: {BENCHMARK_N} alphas at {BENCHMARK_MEAN_CORR:.3f} "
                f"-> {self.n_eff_benchmark:.1f}) :: {self.verdict}")


def effective_bets(n: int, mean_corr: float) -> float:
    """N / (1 + (N-1) * rho) -- independent bets under an equicorrelation approximation.

    Clamped at 1.0 from below. Negative average correlation can push the formula above N, which is
    real (a hedged pair genuinely carries more information than two independent series) but the
    clamp on the low side matters more: rho -> 1 sends this to 1, which is the correct statement
    that a cohort of identical signals is ONE bet however many copies it contains.
    """
    if n <= 1:
        return float(n)
    denom = 1.0 + (n - 1) * mean_corr
    if denom <= 0:
        return float(n)
    return max(1.0, n / denom)


def measure(returns: np.ndarray) -> Independence:
    """Independence of a candidate cohort. `returns` is (observations x candidates).

    Columns with zero variance are DROPPED rather than treated as uncorrelated. A flat series has
    undefined correlation with everything, and NaN-filling it to 0 would silently inflate the
    independence estimate -- a dead candidate would then read as the most diversifying thing in
    the cohort, which is exactly backwards.
    """
    m = np.asarray(returns, dtype="float64")
    if m.ndim != 2 or m.shape[1] < 2:
        return Independence(int(m.shape[1] if m.ndim == 2 else 0), int(m.shape[0]),
                            float("nan"), float("nan"), float("nan"),
                            effective_bets(BENCHMARK_N, BENCHMARK_MEAN_CORR), float("nan"),
                            False, "UNMEASURABLE: need >= 2 candidates")
    live = np.std(m, axis=0) > 0
    m = m[:, live]
    n_obs, n = m.shape
    if n < 2:
        return Independence(int(n), int(n_obs), float("nan"), float("nan"), float("nan"),
                            effective_bets(BENCHMARK_N, BENCHMARK_MEAN_CORR), float("nan"),
                            False, "UNMEASURABLE: fewer than 2 non-degenerate candidates")

    c = np.corrcoef(m, rowvar=False)
    iu = np.triu_indices(n, k=1)
    pair = c[iu]
    pair = pair[np.isfinite(pair)]
    if pair.size == 0:
        return Independence(int(n), int(n_obs), float("nan"), float("nan"), float("nan"),
                            effective_bets(BENCHMARK_N, BENCHMARK_MEAN_CORR), float("nan"),
                            False, "UNMEASURABLE: no finite pairwise correlations")

    mean_corr = float(np.mean(pair))
    n_eff = effective_bets(n, mean_corr)
    bench = effective_bets(BENCHMARK_N, BENCHMARK_MEAN_CORR)
    noisy = n_obs < _MIN_OBS_PER_SERIES * n

    # The verdict compares CORRELATION to the benchmark, not N_eff. N_eff depends on cohort size,
    # so a small well-diversified cohort would otherwise be scored worse than a huge redundant one
    # purely for being small -- which would reward exactly the width this desk already measured as
    # worthless.
    if mean_corr <= BENCHMARK_MEAN_CORR:
        verdict = "AT OR BETTER THAN BENCHMARK: candidates are genuinely distinct"
    elif mean_corr <= 2 * BENCHMARK_MEAN_CORR:
        verdict = "ABOVE BENCHMARK: some redundancy, N overstates the hypotheses being tested"
    else:
        verdict = ("FAR ABOVE BENCHMARK: this cohort is largely one bet in many costumes -- "
                   "widen the MECHANISM space, not the parameter space")
    if noisy:
        verdict += (f" [NOISE-DOMINATED: {n_obs} obs for {n} candidates; mean correlation is "
                    "biased UPWARD here, so redundancy may be overstated]")

    return Independence(int(n), int(n_obs), mean_corr, float(np.median(pair)), n_eff,
                        bench, float(mean_corr / BENCHMARK_MEAN_CORR), bool(noisy), verdict)
