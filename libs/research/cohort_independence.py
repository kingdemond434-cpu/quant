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

#: Smallest random-subset correlation that can serve as the denominator of an amplification ratio.
#: Below this the baseline is noise and the ratio is uninterpretable -- see
#: `selection_amplification`.
_MIN_RATIO_BASE = 0.02


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

    CLAMPED TO [1, N], AND THE UPPER CLAMP IS NOT COSMETIC. The first version clamped only from
    below, reasoning that negative average correlation genuinely carries more information than
    independence. That is true of a deliberately hedged PAIR and false of everything this function
    is actually used on, and the difference cost a real misreading on 2026-08-01:
    measure_cross_section_breadth reported **64.4 independent bets from 29 crypto perps**. There
    is no arrangement of 29 assets that constitutes 64 independent bets. The formula was
    extrapolating outside its domain and the output was read as a finding.

    WHERE THE NEGATIVE CORRELATION CAME FROM, because this recurs. Removing a common factor from a
    panel induces negative correlation among the residuals BY CONSTRUCTION -- subtract a
    cross-sectional mean and the residuals must sum to zero, forcing average pairwise correlation
    to about -1/(N-1). At N=29 that floor is -0.0357; the measured residual correlation was
    -0.0196, i.e. 55% of the way to a number that pure arithmetic produces from data with no
    structure at all. So the near-zero residual correlation was mostly the demeaning, not
    diversification, and the honest statement after factor removal is N_eff ~= N, capped.

    This is the desk's own lesson L0020 -- know an estimator's floor before reading its output as
    a finding -- recurring in a new place, on code written the same day the lesson was recorded.
    The low clamp still matters for the opposite reason: rho -> 1 sends this to 1, correctly
    saying that a cohort of identical signals is ONE bet however many copies it holds.
    """
    if n <= 1:
        return float(n)
    denom = 1.0 + (n - 1) * mean_corr
    if denom <= 0:
        return float(n)
    return min(float(n), max(1.0, n / denom))


def demeaning_floor(n: int) -> float:
    """The average pairwise correlation that cross-sectional demeaning produces from nothing.

    Residuals of a panel against its own cross-sectional mean must sum to zero at every date, and
    that constraint alone forces mean pairwise correlation to -1/(N-1). Any residual correlation
    at or below this is fully explained by the arithmetic; only the DISTANCE ABOVE it is evidence
    of genuine common structure surviving the factor removal. Report the ratio, never the level.
    """
    return -1.0 / max(n - 1, 1)


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


# ---------------------------------------------------------------- selection amplifies correlation

@dataclass(frozen=True)
class SelectionEffect:
    n_pool: int
    n_selected: int
    pool_corr: float
    selected_corr: float
    random_subset_corr: float
    amplification: float
    p_value: float
    n_eff_pool: float
    n_eff_selected: float
    verdict: str

    def summary(self) -> str:
        return (f"pool {self.n_pool} @ corr {self.pool_corr:.3f} ({self.n_eff_pool:.1f} bets) "
                f"-> selected {self.n_selected} @ corr {self.selected_corr:.3f} "
                f"({self.n_eff_selected:.1f} bets), {self.amplification:.1f}x a random subset, "
                f"p={self.p_value:.3f} :: {self.verdict}")


def selection_amplification(
    returns: np.ndarray, scores: np.ndarray, *, k: int, n_null: int = 400, seed: int = 0,
    selected: np.ndarray | None = None,
) -> SelectionEffect:
    """Does SELECTING the best candidates make the cohort more correlated? Measure it.

    THE DEFECT THIS CLOSES, and it is a measured one rather than a hypothetical. `measure()` runs
    on the candidate POOL, and that is the number the desk has been reading. On the 2026-08-01
    fifty-one-strategy cohort the pool's mean pairwise correlation was 0.08 -- comfortably better
    than the 0.159 professional benchmark, reading as "these candidates are genuinely distinct".
    Among the candidates that actually WON it was 0.85. The pool number was true and completely
    beside the point: nothing trades the pool. The desk allocates to the survivors, and the
    survivors were one bet wearing eleven costumes.

    WHY SELECTION DOES THIS. Ranking on realised performance over a shared window ranks partly on
    whatever common factor was paying during that window. Every candidate loading on it is pushed
    up together, so the top of the ranking fills with the same exposure -- the correlation is not
    created by the selection, it is CONCENTRATED by it. That is why a pool measurement cannot
    detect it and why this has to be computed on the admitted set.

    WHY THERE IS A NULL RATHER THAN A THRESHOLD. Correlation measured on k series is noisier than
    on N, so a selected subset would read as more correlated than the pool sometimes even under
    perfectly innocent selection, and a fixed threshold would fire on that noise. The null here is
    RANDOM subsets of the same size k drawn from the same pool: it holds the subset size fixed and
    varies only whether the choice was informed. The p-value is the fraction of random subsets at
    least as correlated as the selected one, with the standard +1 correction so a null that never
    once reaches the observed value reports 1/(n_null+1) rather than an impossible zero.

    `scores` is any per-candidate ranking statistic, higher meaning better -- Sharpe, rank score,
    whatever the admission actually used. Pass the SAME statistic admission ranked on, or this
    measures the amplification of a selection nobody made.

    `selected` OVERRIDES scores and k with the literal column indices that were admitted, and is
    the preferred call from a real gauntlet. Top-k-by-score is a PROXY for what admission did;
    admission also applies structural blocks, so the set it actually returns is not the top k of
    anything. Measuring the proxy would answer a question about a portfolio nobody holds.
    """
    m = np.asarray(returns, dtype="float64")
    s = np.asarray(scores, dtype="float64")
    if m.ndim != 2 or m.shape[1] < 2 or s.shape[0] != m.shape[1]:
        return _no_selection_effect(int(m.shape[1]) if m.ndim == 2 else 0, k,
                                    "UNMEASURABLE: need a 2-D matrix and one score per column")
    live = np.std(m, axis=0) > 0
    keep = np.flatnonzero(live)
    m, s = m[:, live], s[live]
    n = m.shape[1]

    if selected is not None:
        # Re-index onto the surviving columns, since dead ones were dropped above. An admitted
        # column that was dead is silently gone rather than shifting every later index by one.
        remap = {int(o): i for i, o in enumerate(keep)}
        chosen = np.array(sorted({remap[int(j)] for j in np.asarray(selected).ravel()
                                  if int(j) in remap}), dtype=int)
        k = int(chosen.size)
    else:
        k = int(min(max(k, 2), n))
        chosen = np.argsort(-s)[:k]

    if n < 4 or k < 2 or k >= n:
        return _no_selection_effect(n, k, "UNMEASURABLE: the selected set is the whole pool or "
                                          "smaller than a pair, so there is nothing for "
                                          "selection to concentrate")

    c = np.corrcoef(m, rowvar=False)
    pool_corr = _mean_offdiag(c, np.arange(n))
    sel_corr = _mean_offdiag(c, chosen)

    rng = np.random.default_rng(seed)
    null = np.array([_mean_offdiag(c, rng.choice(n, size=k, replace=False))
                     for _ in range(int(n_null))])
    null = null[np.isfinite(null)]
    if not np.isfinite(sel_corr) or null.size == 0:
        return _no_selection_effect(n, k, "UNMEASURABLE: no finite pairwise correlations")

    rand_corr = float(np.mean(null))
    p = float((int(np.sum(null >= sel_corr)) + 1) / (null.size + 1))
    # Ratio against the RANDOM-SUBSET mean, not against the pool: the like-for-like comparison is
    # a subset of the same size chosen without information, which is what isolates the selection.
    #
    # NOT REPORTED WHEN THE BASELINE IS NEAR ZERO, which is not a rounding concern but the same
    # domain error as the effective_bets upper clamp (see above). A genuinely uncorrelated pool
    # gives a random-subset correlation of about -0.008, and dividing by that produced
    # "-8.8x amplification" from data with no structure whatsoever -- a number that reads as a
    # dramatic finding and means only that the denominator was noise. Below the threshold the
    # amplification is NaN and the p-value and the two correlation LEVELS carry the answer, which
    # they can do without a denominator.
    amp = float(sel_corr / rand_corr) if rand_corr >= _MIN_RATIO_BASE else float("nan")

    if p > 0.10:
        verdict = ("SELECTION IS NOT CONCENTRATING: the winners are no more correlated than a "
                   "random subset of the same size. The pool's independence carries over.")
    elif sel_corr >= 2 * BENCHMARK_MEAN_CORR:
        verdict = ("SELECTION COLLAPSES THE COHORT: the winners are one bet in many costumes. "
                   "Size on the SELECTED n_eff, not the pool's -- allocating as though these "
                   "were independent is the single fastest way to a correlated drawdown.")
    else:
        verdict = ("SELECTION CONCENTRATES: the winners are measurably more correlated than "
                   "chance, so the pool's n_eff overstates the diversification being bought.")

    return SelectionEffect(
        n_pool=n, n_selected=k, pool_corr=pool_corr, selected_corr=sel_corr,
        random_subset_corr=rand_corr, amplification=amp, p_value=p,
        n_eff_pool=effective_bets(n, pool_corr), n_eff_selected=effective_bets(k, sel_corr),
        verdict=verdict)


def _mean_offdiag(c: np.ndarray, idx: np.ndarray) -> float:
    """Mean off-diagonal correlation of the submatrix on `idx`, reusing the pool's matrix.

    Re-estimating correlations from the subset's own columns would give the same answer at far
    greater cost -- a pairwise correlation does not depend on which other columns were included.
    """
    sub = c[np.ix_(idx, idx)]
    iu = np.triu_indices(len(idx), k=1)
    pair = sub[iu]
    pair = pair[np.isfinite(pair)]
    return float(np.mean(pair)) if pair.size else float("nan")


def _no_selection_effect(n: int, k: int, why: str) -> SelectionEffect:
    nan = float("nan")
    return SelectionEffect(n, k, nan, nan, nan, nan, nan, nan, nan, why)
