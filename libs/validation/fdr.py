"""False Discovery Rate control (Benjamini-Hochberg / Benjamini-Yekutieli / e-BH).

Bounds the expected proportion of false discoveries among the rejected hypotheses across the
whole research program — the program-wide layer of the family-wise error budget.

THE P-VALUE PROCEDURES AND THE E-VALUE ONE ANSWER THE SAME QUESTION FOR DIFFERENT EVIDENCE. BH and
BY take p-values from FIXED-SAMPLE tests; e-BH takes e-values from the desk's anytime-valid
forward clocks (`libs/research/anytime_valid.e_value`), where the sample size is a stopping time
the desk chose by looking at the data. Feeding a peeked e-process into a p-value procedure would
throw away exactly the property that makes peeking legal, which is why e-BH is not a stylistic
alternative here — it is the only correct multiplicity procedure for the forward cohort.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict


class FDRResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    rejected: list[bool]
    threshold: float
    n_rejected: int
    method: str


def _control(pvalues: np.ndarray, alpha: float, *, dependent: bool) -> tuple[np.ndarray, float]:
    p = np.asarray(pvalues, dtype="float64")
    m = len(p)
    if m == 0:
        return np.zeros(0, dtype=bool), 0.0
    order = np.argsort(p)
    ranks = np.arange(1, m + 1)
    c_m = float(np.sum(1.0 / ranks)) if dependent else 1.0
    crit = (ranks / (m * c_m)) * alpha
    sorted_p = p[order]
    below = sorted_p <= crit
    if not below.any():
        rejected = np.zeros(m, dtype=bool)
        return rejected, 0.0
    k_max = int(np.max(np.where(below)[0]))
    threshold = float(sorted_p[k_max])
    rejected = p <= threshold
    return rejected, threshold


def benjamini_hochberg(pvalues: np.ndarray, *, alpha: float = 0.1) -> FDRResult:
    """Benjamini-Hochberg FDR control (assumes independence / positive dependence)."""
    rejected, threshold = _control(np.asarray(pvalues), alpha, dependent=False)
    return FDRResult(
        rejected=rejected.tolist(), threshold=threshold, n_rejected=int(rejected.sum()),
        method="benjamini_hochberg",
    )


def benjamini_yekutieli(pvalues: np.ndarray, *, alpha: float = 0.1) -> FDRResult:
    """Benjamini-Yekutieli FDR control (valid under arbitrary dependence)."""
    rejected, threshold = _control(np.asarray(pvalues), alpha, dependent=True)
    return FDRResult(
        rejected=rejected.tolist(), threshold=threshold, n_rejected=int(rejected.sum()),
        method="benjamini_yekutieli",
    )


def e_benjamini_hochberg(evalues: np.ndarray | list[float], *,
                         alpha: float = 0.1) -> FDRResult:
    """e-BH: FDR control on E-VALUES, valid under ARBITRARY dependence (Wang & Ramdas 2022).

    THE ABSENCE THIS CLOSES. `docs/research/deep_sweep/20260726_validation-stats.md:752` recorded
    "ABSENT: e_bh -> no e-value multiplicity procedure for the forward cohort (W-8)" and named it
    one of "the two absences that matter most". The desk has run an e-process on every forward
    clock since (`libs/research/anytime_valid.e_value`, four live consumers) and had no way to
    correct the COHORT of them for multiplicity, so the forward stage controlled family-wise error
    with Holm on t-statistics and left the e-values uncorrected beside it.

    Sort e descending and reject the largest k*, where

        k* = max { k : e_(k) >= K / (alpha * k) }

    WHY THIS BEATS RUNNING BY ON CONVERTED p-VALUES, which is the shortcut it replaces. Benjamini-
    Yekutieli buys arbitrary dependence by paying a log factor: at K=12 its critical values are
    divided by sum(1/i) = 3.10, so it forfeits about two thirds of its power. e-BH needs NO
    dependence correction at all -- the guarantee holds for any dependence structure whatsoever,
    with no penalty -- because an e-value's expectation under the null is bounded without any
    assumption about how it co-varies with its siblings. The desk's forward slots are heavily
    dependent by construction (twelve crypto sleeves sharing one market factor; the measured raw
    cross-section is 1.54 independent bets), so this is the exact case the procedure is for.

    IT IS ALSO SAFE UNDER OPTIONAL STOPPING, which p-value FDR is not. Each e-value may come from
    a clock the desk stopped when it liked the number; Ville's inequality already covers that per
    hypothesis, and e-BH lifts it to the cohort without re-introducing a fixed-sample assumption.

    NO ALPHA IS LOOSENED ANYWHERE BY THIS FUNCTION. It is a strictly additional instrument: it
    computes a cohort verdict and returns it. Nothing here promotes, sizes or relaxes a bar, and
    the two-stage law is untouched -- a hypothesis rejected here has cleared a multiplicity
    correction, not a promotion gate.
    """
    e = np.asarray(evalues, dtype="float64")
    m = len(e)
    if m == 0:
        return FDRResult(rejected=[], threshold=0.0, n_rejected=0, method="e_benjamini_hochberg")
    # A non-finite or negative entry is NOT evidence and must not be allowed to rank above a real
    # one. inf is a legitimate e-value (the null is crushed) and is kept; NaN is not, and is
    # floored to 0 so it can never be rejected -- absence resolving to a clean verdict is the
    # failure mode this desk pays for most (L1.28a).
    e = np.where(np.isnan(e), 0.0, e)
    e = np.maximum(e, 0.0)
    order = np.argsort(-e)                      # descending, stable -> deterministic on ties
    sorted_e = e[order]
    ranks = np.arange(1, m + 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        crit = m / (alpha * ranks)
    meets = sorted_e >= crit
    if not meets.any():
        return FDRResult(rejected=[False] * m, threshold=0.0, n_rejected=0,
                         method="e_benjamini_hochberg")
    k_star = int(np.max(np.where(meets)[0])) + 1
    # The cut is by RANK, which is what the procedure specifies. It is worth recording that this
    # is NOT a tie-safety measure, because that was the first guess and it is wrong: crit_k =
    # m/(alpha*k) DECREASES in k, so a hypothesis tied with the k*-th already meets its own
    # (looser) critical value and the step-up includes it either way. Rank and value agree here;
    # rank is used because it states the procedure directly rather than re-deriving it.
    rejected = np.zeros(m, dtype=bool)
    rejected[order[:k_star]] = True
    return FDRResult(
        rejected=rejected.tolist(), threshold=float(sorted_e[k_star - 1]),
        n_rejected=k_star, method="e_benjamini_hochberg",
    )


def merge_evalues(evalues: np.ndarray | list[float]) -> float:
    """Combine e-values for ONE hypothesis into one e-value, under arbitrary dependence.

    THE ARITHMETIC MEAN IS THE ANSWER, and it is the whole point (Vovk & Wang 2021). The mean of
    e-values is always a valid e-value no matter how they depend on each other, which has no
    analogue on the p-value side -- averaging p-values is not a p-value, and Fisher's or Stouffer's
    combination needs independence the desk does not have.

    USE IT TO MERGE EVIDENCE ABOUT THE SAME CLAIM, never to pool distinct hypotheses: three clocks
    on one sleeve merge here, twelve different sleeves go to `e_benjamini_hochberg`. Merging
    distinct hypotheses would average a strong edge together with a dead one and report the pair
    as middling evidence for a claim nobody made.
    """
    e = np.asarray(evalues, dtype="float64")
    e = e[~np.isnan(e)]
    if len(e) == 0:
        return 0.0                              # no evidence is 0, never the 1.0 of a null result
    return float(np.mean(np.maximum(e, 0.0)))
