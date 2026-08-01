"""Stratify the campaign by available history instead of truncating it to the shortest candidate.

THE DEFECT THIS REPLACES. Every campaign builder on the desk aligns its matrix with

    min_len = min(len(r) for r in return_series)
    matrix  = np.column_stack([r[-min_len:] for r in return_series])

so ONE short candidate truncates every other. On the 420-candidate campaign that meant 310
observations retained of ~1,808 available per candidate -- **82.9% of the data already on disk,
discarded before a single test ran**.

WHY THAT IS THE EXPENSIVE CHOICE, measured rather than assumed (docs/research/gate_power_audit.md):

    history   T=310 -> 620 -> 1250 -> 2500     power 0.0% -> 1.7% -> 4.6% -> 19.6%
    cohort    N=420 -> 100 -> 30               power 0.0% -> 0.0% ->  0.0%

Observations buy power; cohort size does not. The truncation makes exactly the wrong trade --
it spends observations to keep candidates aligned. On the desk's own campaign the consequence is
not marginal: the best candidate's Romano-Wolf adjusted p is 0.522 at the min-length window and
0.089 at the max-observation window. Same candidates, same gate, same threshold.

WHY STRATIFY RATHER THAN JUST PICK A LONGER WINDOW. The first version of this module maximised
per-candidate detection power and chose 4,000 observations x 16 candidates -- 99.9% power, and
404 of 420 hypotheses never tested at all. That is the wrong objective: a dropped candidate has
ZERO probability of discovery, not a small one. The quantity worth maximising is the EXPECTED
NUMBER OF TRUE DISCOVERIES, cohort size times per-candidate power, summed over strata. Stratifying
dominates any single window because every candidate is then tested at the longest window IT can
support, and none is truncated to a stranger's history.

MULTIPLICITY STAYS HONEST. Each stratum is its own family, corrected within itself, and the split
is priced at CAMPAIGN_ALPHA/k so total family-wise error stays at 5% however the campaign is cut.
The strata are defined by DATA AVAILABILITY ALONE -- ``plan_strata`` takes lengths and never sees
a return, a Sharpe, or a p-value -- so no channel exists through which results could shape the
partition. A window chosen after peeking at performance would be a selection effect dressed as a
fix.

*** WIRED 2026-08-01 into the autodiscovery campaign. Both preconditions are now met. ***

  1. DONE -- the planner is results-blind and the split is priced. Verified by tests.
  2. DONE (2026-08-01) -- the per-stratum level now reaches the gate.
     ``libs.autodiscovery.validation.stratified_campaign_gates`` is the ONLY supported way to
     split a campaign, and it computes ``CAMPAIGN_ALPHA/k`` itself and threads it through
     ``campaign_gate_stats(..., alpha=)`` into ``romano_wolf_stepdown(..., alpha=)``, so total
     family-wise error stays at 5% however the campaign is cut. Pinned by
     ``tests/autodiscovery/test_stratified_campaign.py::
     test_every_stratum_is_tested_at_campaign_alpha_over_k``.

     Until that landed, the campaign builders passed nothing and every family ran at 5%, so a
     k-stratum campaign would have carried ~1-(1-0.05)^k. The Bonferroni accounting this planner
     assumes is a PROPERTY OF THE CALLER, not of this module -- which is why splitting by hand,
     rather than through ``stratified_campaign_gates``, is still a loosening of error control.

MEASURED ON THE REAL CAMPAIGN when it was wired (420 candidates, `_audit_prepared.pkl`):

    min-length   130,200 obs (17.1% of available), 420 tested,  E[discoveries]   1.06
    stratified   698,655 obs (92.0% of available), 308 tested,  E[discoveries] 191.65   (180.8x)

24 strata, windows 4594 down to 1098. The 112 untested candidates are those no stratum's floors
(MIN_COHORT=12, MIN_OBS=250) can support; they are recorded as UNTESTED, never as rejected, and
the count is written to the audit log every campaign. Under min-length they were nominally tested
at ~0.25% power, so nothing that had a real chance of discovery lost one.

COST: Romano-Wolf's bootstrap is linear in retained observations, so a stratified campaign does
roughly 5x the work of a truncated one (measured ~97s for a 60-candidate two-stratum fixture).
That is the price of using the data, and it is paid once per campaign.
"""
from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache
from typing import NamedTuple

import numpy as np
from scipy.stats import norm

from libs.validation.dsr import expected_max_sharpe
from libs.validation.positive_control import PPY

#: The edge size the partition is tuned to resolve. 2.0 annualised is a world-class systematic
#: book; tuning larger would justify short windows only a fantasy strategy could clear, tuning
#: smaller would demand history the desk does not have.
REFERENCE_ANN_SHARPE = 2.0
#: Below this a cohort is too small for CSCV and Romano-Wolf to say anything.
MIN_COHORT = 12
#: Below this validate() cannot form its walk-forward and CPCV splits (it returns
#: "insufficient data" under 250).
MIN_OBS = 250


class Stratum(NamedTuple):
    """One campaign: a window, the candidates that support it, and the audit trail."""

    n_obs: int
    keep: tuple[int, ...]
    """Indices into the ORIGINAL input order, so a caller can map results back."""
    power: float
    obs_retained: int


class StrataPlan(NamedTuple):
    strata: tuple[Stratum, ...]
    obs_retained: int
    obs_available: int
    n_candidates: int
    n_tested: int
    expected_discoveries: float
    """Sum over strata of cohort x per-candidate power -- the objective actually maximised."""
    why: str

    @property
    def retained_fraction(self) -> float:
        return self.obs_retained / self.obs_available if self.obs_available else 0.0


#: Total family-wise error the WHOLE campaign is allowed, however many strata it is cut into.
CAMPAIGN_ALPHA = 0.05


#: Cap on strata, set FROM A MEASUREMENT rather than a guess. An earlier value of 8 was chosen on
#: the reasoning that "Bonferroni is brutal so the optimum k is small"; swept on a realistic length
#: distribution (420 candidates, lengths ~lognormal(1700, 0.55) floored at 310) the optimum was
#: k=26, sitting hard against that cap:
#:
#:      cap    2      4      6      8     12     16     24     35
#:      k      2      4      6      8     12     16     24     26
#:      E[d] 111.6  125.9  133.1  138.6  145.9  151.0  158.4  159.0
#:
#: The gain is mostly NOT from shrinking cohorts: it is from more candidates (200 -> 326) getting a
#: window their own history supports instead of being dropped or truncated. 32 sits above the
#: measured optimum with headroom; the DP is O(n^2 k^2) and still runs in well under a second.
MAX_STRATA = 32


@lru_cache(maxsize=200_000)
def detection_power(n_trials: int, n_obs: int,
                    true_ann_sharpe: float = REFERENCE_ANN_SHARPE,
                    alpha: float = CAMPAIGN_ALPHA) -> float:
    """P(a candidate with this TRUE annualised Sharpe clears the hurdle) at this shape and level.

    Built on ``expected_max_sharpe`` -- the desk's own deflator -- so the figure tracks the gate
    rather than restating it. Assumes null dispersion 1/T, which biases power upward equally for
    every window under comparison, so the RANKING this drives is unaffected.

    ``alpha`` is the level THIS stratum is tested at, and it is what stops the partition from
    being a loophole. See ``plan_strata``.
    """
    if n_obs <= 1 or n_trials < 1 or not 0.0 < alpha < 1.0:
        return 0.0
    sr0 = expected_max_sharpe(n_trials, 1.0 / n_obs)
    hurdle = (sr0 + float(norm.ppf(1.0 - alpha)) / np.sqrt(n_obs - 1)) * np.sqrt(PPY)
    se = float(np.sqrt(PPY / n_obs))
    return float(1.0 - norm.cdf((hurdle - true_ann_sharpe) / se))


_EULER = 0.5772156649015329


def _power_grid(m: np.ndarray, t_obs: np.ndarray, true_ann_sharpe: float,
                alpha: float) -> np.ndarray:
    """``detection_power`` evaluated over whole arrays at once.

    Identical arithmetic to the scalar form -- including reproducing expected_max_sharpe's
    Bailey/Lopez de Prado expression inline, because it takes scalars. That duplication is a real
    risk (two copies of one formula drift), so ``test_power_grid_matches_the_scalar_form`` asserts
    they agree elementwise; if the scalar version is ever changed the test fails rather than the
    planner silently optimising against a stale model.

    Needed because the planner evaluates this ~1.4M times and the scalar path did not finish.
    """
    m = np.asarray(m, dtype="float64")
    t = np.asarray(t_obs, dtype="float64")
    out = np.zeros(m.shape, dtype="float64")
    ok = (m >= 2) & (t > 1)
    if not np.any(ok):
        return out
    mm, tt = m[ok], t[ok]
    a = norm.ppf(1.0 - 1.0 / mm)
    b = norm.ppf(1.0 - 1.0 / (mm * np.e))
    sr0 = np.sqrt(1.0 / tt) * ((1.0 - _EULER) * a + _EULER * b)
    hurdle = (sr0 + norm.ppf(1.0 - alpha) / np.sqrt(tt - 1.0)) * np.sqrt(PPY)
    se = np.sqrt(PPY / tt)
    out[ok] = 1.0 - norm.cdf((hurdle - true_ann_sharpe) / se)
    return out


def plan_strata(lengths: Sequence[int], *, min_cohort: int = MIN_COHORT, min_obs: int = MIN_OBS,
                true_ann_sharpe: float = REFERENCE_ANN_SHARPE) -> StrataPlan:
    """Partition candidates into campaigns by available history, maximising expected discoveries.

    Sorted by length descending, a stratum is a CONTIGUOUS run and its usable window is the
    SHORTEST length in that run -- so the partition problem is one-dimensional and an exact
    dynamic program is affordable at any campaign size the desk will ever run.

    THE SPLIT IS PRICED, and without that this whole module would be a loophole. Each stratum is
    a separate family, so cutting a campaign into k pieces and testing each at 5% gives an overall
    false-positive rate near 1-(1-0.05)^k -- 82% at k=34. An unpriced objective exploits exactly
    that: the first version of this DP fragmented into 34 strata of the MINIMUM cohort size,
    because smaller cohorts carry a smaller multiplicity deflation. It was not finding structure
    in the data, it was evading the correction by partitioning, and it would have reported a 279x
    improvement that was mostly fictional.

    So each stratum is tested at CAMPAIGN_ALPHA/k (Bonferroni across strata) and the DP is solved
    once per k with that level, taking the best k. Splitting now costs what it actually costs, the
    optimiser cannot buy power by fragmenting, and total family-wise error stays at
    CAMPAIGN_ALPHA no matter how the campaign is cut.
    """
    lens = [int(x) for x in lengths]
    n = len(lens)
    available = sum(lens)
    if n == 0:
        return StrataPlan((), 0, 0, 0, 0, 0.0, "no candidates")

    order = sorted(range(n), key=lambda i: -lens[i])       # descending by length
    sorted_len = [lens[i] for i in order]

    max_k = max(1, min(MAX_STRATA, n // max(1, min_cohort)))
    NEG = -1.0e18
    lens_arr = np.asarray(sorted_len, dtype="float64")
    best_score, best_cuts, best_k = 0.0, [], 1
    for k in range(1, max_k + 1):
        alpha_k = CAMPAIGN_ALPHA / k
        # value[i, e] = expected discoveries from the stratum order[i:e]. Built VECTORISED --
        # the scalar form of this DP is O(n^2 k^2) Python iterations with a scipy call inside and
        # did not finish at n=420. Same arithmetic, same answer, seconds instead of minutes.
        idx = np.arange(n + 1)
        m = idx[None, :] - idx[:, None]                      # cohort size e - i
        win = np.zeros((n + 1, n + 1))
        win[:, 1:] = lens_arr[None, :]                       # window = shortest in the run
        ok = (m >= min_cohort) & (win >= min_obs)
        value = np.full((n + 1, n + 1), NEG)
        grid = m * _power_grid(m, win, true_ann_sharpe, alpha_k)
        value[ok] = grid[ok]
        dp = np.full((n + 1, k + 1), NEG)
        nxt = np.full((n + 1, k + 1), -1, dtype=int)
        dp[:, 0] = 0.0                                       # leaving the rest untested scores 0
        for j in range(1, k + 1):
            for i in range(n - 1, -1, -1):
                cand = value[i, :] + dp[:, j - 1]
                e = int(np.argmax(cand))
                if cand[e] > dp[i, j]:
                    dp[i, j], nxt[i, j] = cand[e], e
        for j in range(1, k + 1):
            if dp[0, j] > best_score:
                cuts, i, jj = [], 0, j
                while jj > 0 and nxt[i, jj] != -1:
                    cuts.append(int(nxt[i, jj]))
                    i, jj = int(nxt[i, jj]), jj - 1
                best_score, best_cuts, best_k = float(dp[0, j]), cuts, j

    alpha_final = CAMPAIGN_ALPHA / max(1, best_k)
    strata: list[Stratum] = []
    i = 0
    for j in best_cuts:
        window = sorted_len[j - 1]
        keep = tuple(sorted(order[i:j]))                    # back to input order
        strata.append(Stratum(n_obs=window, keep=keep,
                              power=detection_power(len(keep), window, true_ann_sharpe,
                                                    alpha_final),
                              obs_retained=window * len(keep)))
        i = j

    retained = sum(s.obs_retained for s in strata)
    tested = sum(len(s.keep) for s in strata)
    if not strata:
        # Nothing clears the floors. Fall back to min-length and SAY SO -- a builder that silently
        # produces no campaign is worse than one that produces a weak campaign, because only the
        # second is visible in the artifact.
        cut = min(lens)
        return StrataPlan(
            (Stratum(cut, tuple(range(n)), detection_power(n, cut, true_ann_sharpe), cut * n),),
            cut * n, available, n, n, n * detection_power(n, cut, true_ann_sharpe),
            f"NO stratification met the floors (min_obs={min_obs}, min_cohort={min_cohort}) -- "
            f"fell back to min-length {cut}. This campaign is underpowered and a null result from "
            "it must not be read as evidence about the price space.")
    return StrataPlan(
        strata=tuple(strata), obs_retained=retained, obs_available=available,
        n_candidates=n, n_tested=tested, expected_discoveries=best_score,
        why=(f"{len(strata)} strata, windows "
             f"{', '.join(str(s.n_obs) for s in strata)}; {tested}/{n} candidates tested; "
             f"{retained:,}/{available:,} observations used "
             f"({100 * retained / available:.1f}%); expected discoveries {best_score:.2f} at true "
             f"annualised Sharpe {true_ann_sharpe}"))


def stratum_matrix(series: Sequence[np.ndarray], s: Stratum) -> np.ndarray:
    """Aligned T x N matrix for one stratum: the last ``s.n_obs`` rows of each kept candidate."""
    if not s.keep:
        return np.empty((0, 0), dtype="float64")
    return np.column_stack([np.asarray(series[i], dtype="float64")[-s.n_obs:] for i in s.keep])
