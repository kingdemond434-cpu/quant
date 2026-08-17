"""Which representation of the market actually predicts? Decided by contest, not by taste.

CONSTITUTION 223.1. Neither handcrafted features nor deep learning is assumed to win. The same
target, the same folds, the same costs, and whichever representation earns the most out-of-sample
information takes the slot.

WHY A TOURNAMENT AND NOT A CHAMPION

Different representations plausibly win in different regimes, and that outcome is MORE valuable
than a single winner: it is a conditional model-selection edge in its own right (section 47). So
this reports a table, not a verdict, and refuses to collapse it into one name.

THE THREE WAYS A CONTEST LIKE THIS LIES, AND WHAT IS DONE ABOUT EACH

1. THE SPLIT LEAKS. Random k-fold on a time series trains on the future and tests on the past.
   Every fold here is a chronological block, and the boundary is PURGED: rows within `horizon` of
   the split are dropped from training, because a label computed over the next h bars overlaps the
   test window and would carry it into the fit.

2. THE WINNER IS THE ONE THAT LOOKED HARDEST. A representation with 40 features searches a wider
   space than one with 6, and wins by search rather than by signal. Every entrant reports its own
   trial count and the census is emitted with the result, so the comparison can be deflated. A
   tournament that reports only scores is a multiplicity engine.

3. THERE IS NO FLOOR. Comparing five representations to each other answers which is least bad. A
   SHUFFLED-LABEL entrant runs in every tournament as the null: any representation that fails to
   beat it decisively has found nothing, however well it placed.

WHAT IS SCORED

Information coefficient -- the rank correlation between prediction and realised forward return --
rather than accuracy or Sharpe. IC is scale-free, robust to the fat tails these series actually
have, and does not silently reward a model for taking more risk.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Iterable

import numpy as np

#: Blocks the sample is cut into. Each is tested once, trained on everything chronologically
#: before it -- expanding window, never trained on the future.
N_FOLDS = 5

#: A fold with fewer usable test rows than this reports nothing rather than a noisy IC.
MIN_TEST_ROWS = 50


@dataclass
class Entrant:
    """One representation, its fitter, and the honest count of what it searched."""
    name: str
    features: np.ndarray                 # (T, k)
    n_trials: int = 1
    meta: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Result:
    name: str
    ic_mean: float
    ic_std: float
    ic_by_fold: list[float]
    n_features: int
    n_trials: int
    folds_scored: int
    why: str = ""

    @property
    def t_stat(self) -> float:
        """IC mean over its standard error across folds. Folds are the sample here, not rows."""
        if self.folds_scored < 2 or self.ic_std <= 0:
            return 0.0
        return self.ic_mean / (self.ic_std / math.sqrt(self.folds_scored))


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Rank correlation. Scale-free and unbothered by the tails these series actually have."""
    if len(a) < 3:
        return 0.0
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    if ra.std() == 0 or rb.std() == 0:
        return 0.0
    return float(np.corrcoef(ra, rb)[0, 1])


def _ridge_fit_predict(xtr: np.ndarray, ytr: np.ndarray, xte: np.ndarray,
                       lam: float = 1.0) -> np.ndarray:
    """Ridge, deliberately. Every entrant gets the SAME learner so the contest compares
    REPRESENTATIONS rather than model families -- otherwise the tournament silently becomes a
    contest between a linear model and a forest, which is a different question.

    Standardised on the TRAINING fold only. Using test-fold moments to scale is leakage that
    looks like nothing and inflates every score.
    """
    mu, sd = xtr.mean(axis=0), xtr.std(axis=0)
    sd[sd == 0] = 1.0
    xa = (xtr - mu) / sd
    xb = (xte - mu) / sd
    ymu = ytr.mean()
    k = xa.shape[1]
    w = np.linalg.solve(xa.T @ xa + lam * np.eye(k), xa.T @ (ytr - ymu))
    return xb @ w + ymu


def purged_folds(n: int, n_folds: int = N_FOLDS, horizon: int = 1):
    """Expanding-window chronological folds with a purged boundary.

    The purge is the part that matters. A label computed over the next `horizon` bars overlaps the
    test window for the last `horizon` training rows, so those rows carry test information into
    the fit. Dropping them is the difference between an honest OOS number and a flattering one.
    """
    edge = n // (n_folds + 1)
    for f in range(1, n_folds + 1):
        tr_end = edge * f
        te_beg, te_end = tr_end, min(edge * (f + 1), n)
        tr_end = max(0, tr_end - horizon)          # PURGE
        if tr_end < 50 or (te_end - te_beg) < MIN_TEST_ROWS:
            continue
        yield np.arange(0, tr_end), np.arange(te_beg, te_end)


def score(entrant: Entrant, y: np.ndarray, horizon: int = 1,
          n_folds: int = N_FOLDS) -> Result:
    """Out-of-sample IC for one representation, fold by fold."""
    x = np.asarray(entrant.features, dtype=float)
    y = np.asarray(y, dtype=float)
    n = min(len(x), len(y))
    x, y = x[:n], y[:n]
    ok = np.isfinite(x).all(axis=1) & np.isfinite(y)

    ics: list[float] = []
    for tr, te in purged_folds(n, n_folds, horizon):
        tr, te = tr[ok[tr]], te[ok[te]]
        if len(tr) < 50 or len(te) < MIN_TEST_ROWS:
            continue
        try:
            pred = _ridge_fit_predict(x[tr], y[tr], x[te])
        except np.linalg.LinAlgError:
            continue
        ics.append(_spearman(pred, y[te]))

    if not ics:
        return Result(entrant.name, 0.0, 0.0, [], x.shape[1], entrant.n_trials, 0,
                      why="no fold had enough usable rows; scored nothing rather than guessing")
    arr = np.array(ics)
    return Result(entrant.name, float(arr.mean()), float(arr.std()), [float(v) for v in arr],
                  x.shape[1], entrant.n_trials, len(ics),
                  why=f"purged expanding-window IC over {len(ics)} folds, horizon {horizon}")


def shuffled_null(entrant: Entrant, y: np.ndarray, horizon: int = 1,
                  seed: int = 0) -> Result:
    """THE FLOOR. The same representation against a shuffled target.

    Without this the tournament only answers which entrant is least bad. A representation that
    cannot decisively beat its own shuffled null has found nothing, whatever its rank.
    """
    rng = np.random.default_rng(seed)
    yshuf = np.asarray(y, dtype=float).copy()
    rng.shuffle(yshuf)
    r = score(Entrant(f"NULL({entrant.name})", entrant.features, entrant.n_trials),
              yshuf, horizon)
    return Result(r.name, r.ic_mean, r.ic_std, r.ic_by_fold, r.n_features, r.n_trials,
                  r.folds_scored,
                  why="shuffled target: any real entrant must beat this decisively")


def run(entrants: Iterable[Entrant], y: np.ndarray, horizon: int = 1,
        n_folds: int = N_FOLDS) -> dict:
    """The tournament. Returns a table plus the multiplicity burden it accumulated."""
    ents = list(entrants)
    results = [score(e, y, horizon, n_folds) for e in ents]
    nulls = [shuffled_null(e, y, horizon, seed=i) for i, e in enumerate(ents)]

    ranked = sorted(results, key=lambda r: r.ic_mean, reverse=True)
    total_trials = sum(e.n_trials for e in ents)
    null_ceiling = max((n.ic_mean for n in nulls), default=0.0)
    beat_null = [r.name for r in ranked if r.ic_mean > null_ceiling + 0.02]

    return {
        "ranked": [{"name": r.name, "ic": round(r.ic_mean, 4), "ic_std": round(r.ic_std, 4),
                    "t": round(r.t_stat, 2), "features": r.n_features,
                    "trials": r.n_trials, "folds": r.folds_scored} for r in ranked],
        "nulls": [{"name": n.name, "ic": round(n.ic_mean, 4)} for n in nulls],
        "null_ceiling": round(null_ceiling, 4),
        "beat_the_null": beat_null,
        "n_trials_total": total_trials,
        "verdict": (f"{len(beat_null)}/{len(ents)} representations beat the shuffled null by "
                    f">0.02 IC" if beat_null else
                    "NO representation beat its own shuffled null. This dataset, at this horizon, "
                    "supports none of them -- which is a result, not a failure to find one."),
        "multiplicity": (f"{total_trials} trials across {len(ents)} entrants. Deflate before "
                         "treating any IC here as evidence -- see mt5desk.canonical."),
        "why_no_single_winner": (
            "Different representations plausibly win in different regimes, and that is a "
            "conditional model-selection edge (section 47) rather than a tie to be broken. The "
            "table is the result."),
    }
