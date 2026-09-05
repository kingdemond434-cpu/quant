"""HOW MANY INDEPENDENT BETS THE BOOK IS, measured from EXPOSURES rather than waited for.

    "You need approximately twice as many genuinely independent sources of P&L. Five
     Gold/JPY/session-breakout variants are not five independent edges if they all make money
     from approximately the same market phenomenon."               -- the principal, 2026-09-05

THE MEASUREMENT THAT ALREADY EXISTS AND THE HOLE IN IT. `mt5desk/independence.py` computes k_eff
from REALISED daily sleeve returns and floors it with `libs/risk/fx_factors.effective_bets`, which
counts currency legs. Both are right and neither can answer today: the return estimator needs
MIN_PAIR_OVERLAP = 20 overlapping trading days per pair, and on this desk's shadow history the
best pair has TEN. The leg counter needs no history at all but answers a coarser question -- how
many distinct legs -- and treats EUR, CHF, NOK, SEK and DKK as five legs when they are close to
one bet. So the desk's headline breadth number is either UNMEASURED or optimistic, and the
`n_effective 1.019 across 17 sleeves` finding that motivated all of this came from the coarse one.

WHAT THIS ADDS. The book's DIRECTIONAL EXPOSURE has years of price history behind it even when
the sleeves have weeks. A sleeve that is long CADJPY carries CADJPY's covariance whether or not
it has traded twenty days, so:

    N_eff = (sum_s |w_s|)^2 / (x' C x)

where w_s is each sleeve's standalone risk, x is those risks aggregated onto the instruments they
are expressed in and signed by direction, and C is the correlation of vol-normalised instrument
returns. Independent and equal-sized sleeves give N_eff = N; N copies of one trade give 1. This is
the diversification ratio squared, and it is measured on the desk's own H1 bars.

THREE WAYS IT IS DELIBERATELY CONSERVATIVE, because every one of them could have gone the other
way and flattered the book:

1. TWO SLEEVES ON ONE INSTRUMENT COUNT AS ONE BET. A London breakout and an Asia reversion on
   GBPJPY differ in timing and mechanism, and that difference is real breadth -- which this does
   not claim, because only realised returns can measure it. So the number is a LOWER BOUND on the
   book's P&L breadth and an EXACT reading of its exposure breadth. Timing can only add.
2. AN UNDIRECTIONAL SLEEVE IS DROPPED, NOT DILUTED. A sleeve that went long half the time nets a
   small directional loading while still carrying a full unit of variance; crediting the small
   loading would understate book risk and overstate breadth. It is excluded and counted in
   `dropped` instead.
3. AN INSTRUMENT WITH NO BARS ADDS NO BREADTH. ZAR, MXN, NOK, SEK and DKK crosses are in the book
   and not in the local universe. They are excluded and their share of nominal risk is reported,
   rather than being assumed independent of what is measured.

THE COLLIDER THIS MODULE REFUSES TO WALK INTO, and the reason `conditional_breadth` takes a LAGGED
conditioner and nothing else. "Correlation on the book's worst days" is the natural thing to ask
and the answer is worthless: selecting days by the book's own return selects on a SUM of the
series being correlated, which mechanically decorrelates them. Measured here on this desk's own
panel, breadth conditioned on the book's worst 5% of days reads 8.9 against a full-sample 1.3 --
a book that looks SEVEN TIMES more diversified precisely when it is losing, which is the exact
opposite of what happens and would raise leverage into a crisis. Conditioning on same-day
magnitude has the same defect from the other side (-0.00 mean pairwise correlation on the top-vol
5%). Conditioning on a PRIOR-window statistic has neither: it is known before the returns being
correlated, so it selects a regime rather than a realisation. On the same panel the JPY block
reads 0.93 in a high prior-vol regime against 0.49 in a calm one -- correlations rise in stress,
which is what everyone assumes and nothing here had measured.

NOTHING HERE SIZES ANYTHING. Sizing stays in the gateway. This measures, names its refusals, and
returns None wherever it cannot measure -- None never widens a budget.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from libs.research.cohort_independence import effective_bets

__all__ = [
    "MEASURED",
    "MIN_PAIR_OVERLAP",
    "MIN_PANEL_OBS",
    "MIN_REGIME_OBS",
    "MIN_SCALE_OBS",
    "UNMEASURED",
    "Reading",
    "conditional_breadth",
    "exposure_breadth",
    "exposure_neff",
    "factor_breadth",
    "headline",
    "lagged_vol_regime",
    "realised_breadth",
]

MEASURED, UNMEASURED = "MEASURED", "UNMEASURED"

#: Overlapping days a PAIR of sleeves needs before its realised correlation is used. Identical to
#: `mt5desk.independence.MIN_PAIR_OVERLAP` and mirrored rather than imported so that libs does not
#: depend on the desk package; a noisy correlation near zero is indistinguishable from genuine
#: independence, which is the error that raises leverage.
MIN_PAIR_OVERLAP = 20

#: Observations a price panel needs before its correlation matrix is read as a measurement. Below
#: this the off-diagonals are dominated by estimation noise in BOTH directions and the resulting
#: N_eff is not a number anyone should size on.
MIN_PANEL_OBS = 250

#: Observations an expanding scale needs before it is used to normalise anything. Below this the
#: scale is noise and the regime label it produces is noise divided by noise.
MIN_SCALE_OBS = 20

#: Observations inside a conditioned regime before the conditional correlation is a measurement.
#: Lower than MIN_PANEL_OBS because a regime is a subsample by construction, and high enough that
#: a 12-symbol correlation matrix is not being read off a quarter of a year.
MIN_REGIME_OBS = 60


@dataclass(frozen=True)
class Reading:
    """One way of counting the book's independent bets, with its own refusal path."""

    name: str
    status: str                 # MEASURED | UNMEASURED
    n_eff: float | None
    n_nominal: int
    n_obs: int
    why: str
    detail: dict[str, Any] | None = None

    @property
    def measured(self) -> bool:
        return self.status == MEASURED and self.n_eff is not None

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "status": self.status,
                "n_eff": None if self.n_eff is None else round(float(self.n_eff), 3),
                "n_nominal": self.n_nominal, "n_obs": self.n_obs, "why": self.why,
                **({"detail": self.detail} if self.detail else {})}


def _unmeasured(name: str, why: str, *, n_nominal: int = 0, n_obs: int = 0) -> Reading:
    return Reading(name, UNMEASURED, None, int(n_nominal), int(n_obs), why)


def exposure_neff(nominal_risk: float, exposure: np.ndarray, corr: np.ndarray) -> float:
    """(sum of standalone risks)^2 / (portfolio variance in the same units) -- the bet count.

    ``nominal_risk`` is the sum of the sleeves' standalone risks, which on this desk is simply
    the sleeve count when every sleeve risks the same fraction at stop. ``exposure`` is those
    risks aggregated onto instruments and SIGNED by direction, and ``corr`` is the correlation of
    those instruments' vol-normalised returns.

    Equal to N for N independent equal-risk sleeves and to 1 for N copies of one trade. The
    variance term is refused rather than floored when it is non-positive: a non-PSD correlation
    matrix would produce an enormous bet count out of a measurement error, and an enormous number
    that looks like an answer is worse than an exception.
    """
    x = np.asarray(exposure, dtype="float64").reshape(-1)
    c = np.asarray(corr, dtype="float64")
    if c.shape != (x.size, x.size):
        raise ValueError(f"exposure of {x.size} does not match a {c.shape} correlation matrix")
    var = float(x @ c @ x)
    if not math.isfinite(var) or var <= 0.0:
        raise ValueError(
            "book variance from the supplied exposures and correlations is not positive -- the "
            "correlation matrix is not positive semi-definite; fix the measurement, never size "
            "on it")
    nom = float(nominal_risk)
    return (nom * nom) / var


def _panel_corr(panel: np.ndarray) -> np.ndarray:
    """Pearson correlation of vol-normalised columns. Degenerate columns are the caller's job."""
    m = np.asarray(panel, dtype="float64")
    sd = m.std(axis=0)
    z = m / np.where(sd > 0, sd, 1.0)
    return np.asarray(np.corrcoef(z, rowvar=False), dtype="float64")


def exposure_breadth(nominal_risk: float, exposure: Mapping[str, float],
                     panel: Mapping[str, Sequence[float]], *,
                     name: str = "exposure_full_sample",
                     min_obs: int = MIN_PANEL_OBS) -> Reading:
    """Independent bets implied by what the book is directionally long and short of.

    ``exposure`` maps instrument -> signed risk. ``panel`` maps the same instruments to aligned
    return series. Instruments present in ``exposure`` and absent from ``panel`` are NOT silently
    dropped: they raise, because a caller that quietly loses half its book from the denominator
    gets a flattering number and no warning. Filter before calling, and report what was filtered.
    """
    names = sorted(exposure)
    if len(names) < 2:
        return _unmeasured(name, "a correlation needs at least two instruments",
                           n_obs=0)
    missing = [s for s in names if s not in panel]
    if missing:
        raise KeyError(f"no return series for {missing} -- drop them from the exposure and report "
                       "the risk share they carry, never measure breadth on a silent subset")
    cols = [np.asarray(panel[s], dtype="float64") for s in names]
    n_obs = min(int(c.size) for c in cols)
    if n_obs < int(min_obs):
        return _unmeasured(name, f"{n_obs} aligned observations, below the {min_obs} floor: a "
                                 "correlation matrix this thin is estimation noise",
                           n_obs=n_obs)
    m = np.stack([c[-n_obs:] for c in cols], axis=1)
    if not np.all(np.isfinite(m)) or not np.all(m.std(axis=0) > 0):
        return _unmeasured(name, "a return column is constant or non-finite over the window",
                           n_obs=n_obs)
    x = np.array([float(exposure[s]) for s in names], dtype="float64")
    corr = _panel_corr(m)
    try:
        k = exposure_neff(nominal_risk, x, corr)
    except ValueError as exc:
        return _unmeasured(name, str(exc), n_obs=n_obs)
    iu = np.triu_indices(len(names), 1)
    return Reading(name, MEASURED, k, round(nominal_risk), n_obs,
                   f"(sum|w|)^2 / x'Cx on {len(names)} instruments over {n_obs} observations",
                   {"instruments": names, "mean_pairwise_corr": round(float(corr[iu].mean()), 4),
                    "max_pairwise_corr": round(float(corr[iu].max()), 4)})


def factor_breadth(nominal_risk: float, exposure: Mapping[str, float],
                   panel: Mapping[str, Sequence[float]], *, k_factors: int = 3,
                   min_obs: int = MIN_PANEL_OBS) -> Reading:
    """Independent bets against the SYSTEMATIC part of the correlation only.

    The full-sample reading counts idiosyncratic instrument moves as diversification. They are,
    on an average day; they are not what decides how much leverage the book can carry, because
    idiosyncratic moves do not arrive together and factor moves do. Truncating the correlation to
    its leading ``k_factors`` principal components answers the narrower question: how many bets is
    the book making ON THE THINGS THAT MOVE EVERYTHING AT ONCE.

    Reported BESIDE the full-sample number, never instead of it. Where the two disagree the
    disagreement is the finding: a factor breadth far below the full-sample one says the book's
    apparent diversification lives in idiosyncratic risk and will not be there in a shock.
    """
    base = exposure_breadth(nominal_risk, exposure, panel, name="exposure_systematic",
                            min_obs=min_obs)
    if not base.measured:
        return base
    names = sorted(exposure)
    cols = [np.asarray(panel[s], dtype="float64") for s in names]
    n_obs = min(int(c.size) for c in cols)
    m = np.stack([c[-n_obs:] for c in cols], axis=1)
    kf = int(max(1, min(int(k_factors), len(names) - 1)))
    corr = _panel_corr(m)
    vals, vecs = np.linalg.eigh(corr)
    order = np.argsort(vals)[::-1][:kf]
    load = vecs[:, order] * np.sqrt(np.clip(vals[order], 0.0, None))
    sys_cov = load @ load.T
    # The systematic correlation keeps a unit diagonal: the idiosyncratic remainder is what makes
    # each instrument's own variance up to 1, and dropping it would make the matrix non-PSD.
    idio = np.clip(1.0 - np.diag(sys_cov), 1e-9, None)
    rho_factor = sys_cov + np.diag(idio)
    explained = float(np.sum(vals[order]) / max(float(np.sum(vals)), 1e-12))
    x = np.array([float(exposure[s]) for s in names], dtype="float64")
    try:
        kk = exposure_neff(nominal_risk, x, rho_factor)
    except ValueError as exc:
        return _unmeasured("exposure_systematic", str(exc), n_obs=n_obs)
    return Reading("exposure_systematic", MEASURED, kk, round(nominal_risk), n_obs,
                   f"{kf}-factor systematic correlation explaining {explained:.1%} of panel "
                   "variance; idiosyncratic risk excluded from the diversification claim",
                   {"k_factors": kf, "variance_explained": round(explained, 4)})


def lagged_vol_regime(panel: Mapping[str, Sequence[float]], *, window: int = 20) -> np.ndarray:
    """A regime series that is KNOWN BEFORE the returns it will be used to condition.

    The mean absolute move across the panel, each column scaled by ITS OWN EXPANDING standard
    deviation through t-1, averaged over the previous ``window`` observations. Index t carries
    information from observations strictly before t and from nothing else, so selecting on it
    selects a REGIME and never a realisation. The leading `MIN_SCALE_OBS + window` entries are NaN
    and the caller must treat them as unavailable.

    THE EXPANDING SCALE IS NOT FASTIDIOUSNESS, AND THE FIRST VERSION OF THIS FUNCTION GOT IT
    WRONG. It normalised each column by its FULL-SAMPLE standard deviation before taking the
    rolling window, so a single observation at the end of the panel changed the scale and with it
    every label in the series, including the ones years earlier. The lag was in the window and not
    in the normaliser, which is exactly the kind of leak that survives review: the shift is
    visible in the code and the sd is not. A test that perturbs the last observation and demands
    every earlier label be unchanged catches it, and `test_alpha_breadth_factory.py` carries one.

    THE SHIFT ITSELF IS THE OTHER HALF. Without it every conditional correlation in this module is
    a collider: conditioning on same-period magnitude or on the book's own return decorrelates the
    series by construction and reports a book that diversifies itself precisely when it is losing.
    """
    names = sorted(panel)
    cols = [np.asarray(panel[s], dtype="float64") for s in names]
    n = min(int(c.size) for c in cols)
    m = np.stack([c[-n:] for c in cols], axis=1)
    w = int(window)
    out = np.full(n, np.nan, dtype="float64")
    if w < 1 or n <= MIN_SCALE_OBS + w:
        return out
    # Expanding population std over observations 0..t-1, per column. Strictly prior by index.
    idx = np.arange(1, n + 1, dtype="float64")[:, None]
    c1 = np.cumsum(m, axis=0)
    c2 = np.cumsum(m * m, axis=0)
    mean_prior = c1 / idx
    var_prior = np.clip(c2 / idx - mean_prior * mean_prior, 0.0, None)
    scale = np.full_like(m, np.nan)
    scale[1:] = np.sqrt(var_prior[:-1])              # scale[t] uses 0..t-1 only
    with np.errstate(invalid="ignore", divide="ignore"):
        z = np.abs(m) / np.where(scale > 0, scale, np.nan)
    # Counted mean rather than nanmean: the leading rows have no scale at all, and nanmean warns
    # on an empty slice instead of simply saying "no value here", which is what NaN already says.
    finite = np.isfinite(z)
    cnt = finite.sum(axis=1)
    tot = np.where(finite, z, 0.0).sum(axis=1)
    zbar = np.where(cnt > 0, tot / np.where(cnt > 0, cnt, 1), np.nan)
    zbar[:MIN_SCALE_OBS] = np.nan
    # out[t] = mean(zbar[t-w : t]) -- the window ENDS at t-1, so nothing at t enters its own label.
    for t in range(MIN_SCALE_OBS + w, n):
        seg = zbar[t - w:t]
        good = seg[np.isfinite(seg)]
        if good.size:
            out[t] = float(good.mean())
    return out


def conditional_breadth(nominal_risk: float, exposure: Mapping[str, float],
                        panel: Mapping[str, Sequence[float]], conditioner: Sequence[float], *,
                        quantile: float = 0.2, high: bool = True,
                        name: str = "exposure_stress",
                        min_obs: int = MIN_REGIME_OBS) -> Reading:
    """Independent bets inside a regime picked out by a LAGGED conditioner.

    ``conditioner`` must be known before the observation it labels -- `lagged_vol_regime` builds
    one. There is no way for this function to verify that from the array alone, so the contract is
    stated and the caller carries it; passing a contemporaneous statistic (the book's own return,
    same-day realised vol) turns this into the collider described in the module docstring and the
    answer will be confidently wrong in the direction that raises leverage.
    """
    names = sorted(exposure)
    if len(names) < 2:
        return _unmeasured(name, "a correlation needs at least two instruments")
    missing = [s for s in names if s not in panel]
    if missing:
        raise KeyError(f"no return series for {missing}")
    cols = [np.asarray(panel[s], dtype="float64") for s in names]
    n_obs = min(int(c.size) for c in cols)
    cond = np.asarray(conditioner, dtype="float64")
    if cond.size != n_obs:
        return _unmeasured(name, f"conditioner has {cond.size} entries against {n_obs} aligned "
                                 "observations; an unaligned regime label is not a regime",
                           n_obs=n_obs)
    ok = np.isfinite(cond)
    if int(ok.sum()) < int(min_obs):
        return _unmeasured(name, f"{int(ok.sum())} observations carry a finite regime label, "
                                 f"below the {min_obs} floor", n_obs=int(ok.sum()))
    q = float(np.quantile(cond[ok], 1.0 - quantile if high else quantile))
    sel = ok & ((cond >= q) if high else (cond <= q))
    n_sel = int(sel.sum())
    if n_sel < int(min_obs):
        return _unmeasured(name, f"{n_sel} observations inside the regime, below the {min_obs} "
                                 "floor: a conditional correlation this thin is noise",
                           n_obs=n_sel)
    m = np.stack([c[-n_obs:] for c in cols], axis=1)[sel]
    if not np.all(np.isfinite(m)) or not np.all(m.std(axis=0) > 0):
        return _unmeasured(name, "a return column is constant or non-finite inside the regime",
                           n_obs=n_sel)
    x = np.array([float(exposure[s]) for s in names], dtype="float64")
    corr = _panel_corr(m)
    try:
        k = exposure_neff(nominal_risk, x, corr)
    except ValueError as exc:
        return _unmeasured(name, str(exc), n_obs=n_sel)
    iu = np.triu_indices(len(names), 1)
    return Reading(name, MEASURED, k, round(nominal_risk), n_sel,
                   f"correlation inside the {'top' if high else 'bottom'} "
                   f"{quantile:.0%} of a LAGGED regime conditioner ({n_sel} observations); the "
                   "conditioner is known before the returns it labels, so this selects a regime "
                   "and not a realisation",
                   {"quantile": quantile, "high": high,
                    "mean_pairwise_corr": round(float(corr[iu].mean()), 4)})


def realised_breadth(series: Mapping[str, Mapping[str, float]], *,
                     min_overlap: int = MIN_PAIR_OVERLAP,
                     name: str = "realised_returns") -> Reading:
    """Independent bets from the sleeves' OWN realised P&L, on overlapping days only.

    The measurement the exposure readings cannot make, and the one that captures timing and
    mechanism differences the exposure view refuses to claim. It needs history: a pair with fewer
    than ``min_overlap`` common trading days contributes nothing, and a book where NO pair reaches
    the floor is UNMEASURED. The floor is not lowered to produce an answer -- a correlation
    estimated from eight days is indistinguishable from independence, and reading it as
    independence is exactly how a correlated book comes to size like a diversified one.

    Averaging is in Fisher-z space and the UPPER 95% bound is returned, not the point estimate:
    correlations are estimated on whatever regime happened to be sampled, and the desk takes the
    breadth its evidence supports at the pessimistic end.
    """
    names = sorted(series)
    n = len(names)
    if n < 2:
        return _unmeasured(name, f"{n} sleeve(s) with realised returns; correlation needs two",
                           n_nominal=n)
    zs: list[float] = []
    smallest = 0
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            common = sorted(set(series[a]) & set(series[b]))
            if len(common) < int(min_overlap):
                continue
            xa = np.array([float(series[a][d]) for d in common], dtype="float64")
            xb = np.array([float(series[b][d]) for d in common], dtype="float64")
            if xa.std() <= 0 or xb.std() <= 0:
                continue
            r = float(np.corrcoef(xa, xb)[0, 1])
            if not math.isfinite(r):
                continue
            r = max(min(r, 0.999999), -0.999999)
            zs.append(math.atanh(r))
            smallest = len(common) if smallest == 0 else min(smallest, len(common))
    if not zs:
        return _unmeasured(
            name, f"no sleeve pair has {min_overlap} overlapping trading days ({n} sleeves); the "
                  "floor is not lowered to produce a number", n_nominal=n)
    z_bar = sum(zs) / len(zs)
    se = 1.0 / math.sqrt(max(smallest - 3, 1))
    rho_upper = math.tanh(z_bar + 1.645 * se)
    return Reading(name, MEASURED, effective_bets(n, rho_upper), n, smallest,
                   f"{len(zs)} pair(s) cleared the {min_overlap}-day overlap floor, thinnest "
                   f"overlap {smallest}d; rho <= {rho_upper:.3f} at the 95% upper bound, not the "
                   "point estimate",
                   {"n_pairs": len(zs), "rho_upper": round(rho_upper, 4)})


def headline(readings: Sequence[Reading], n_nominal: int) -> dict[str, Any]:
    """The number to publish: nominal against the SMALLEST measured breadth, and why.

    THE MINIMUM, NEVER THE MEAN AND NEVER THE BEST. Each reading answers a different question --
    what the exposures imply, what the systematic part implies, what a stress regime implies, what
    the realised returns imply -- and a book is only as diversified as its worst true answer.
    Averaging them would let one optimistic reading buy leverage the others say is not there, and
    taking the best is the same error with less arithmetic.

    Every UNMEASURED reading is listed by name with its reason. Absence is never folded into the
    verdict: a book with one measured reading has one measured reading, and saying so is the point.
    """
    measured = [r for r in readings if r.measured]
    unmeasured = [r for r in readings if not r.measured]
    best: Reading | None = None
    for r in measured:
        if best is None or (r.n_eff is not None and best.n_eff is not None
                            and r.n_eff < best.n_eff):
            best = r
    k = None if best is None else float(best.n_eff or 0.0)
    ratio = None if (k is None or n_nominal <= 0) else k / float(n_nominal)
    return {
        "n_nominal": int(n_nominal),
        "effective_breadth": None if k is None else round(k, 3),
        "binding_reading": None if best is None else best.name,
        "breadth_ratio": None if ratio is None else round(ratio, 4),
        "sharpe_multiplier_vs_one_bet": None if k is None else round(math.sqrt(max(k, 0.0)), 3),
        "status": MEASURED if k is not None else UNMEASURED,
        "readings": [r.as_dict() for r in readings],
        "unmeasured": [{"name": r.name, "why": r.why} for r in unmeasured],
        "rule": (
            "effective breadth is the MINIMUM over the measured readings, because a book is only "
            "as diversified as its worst true answer; combined Sharpe scales as sqrt(k_eff), so "
            f"{n_nominal} nominal sleeves at k_eff "
            + ("UNMEASURED" if k is None else f"{k:.2f}")
            + " compound like "
            + ("an unmeasured number of" if k is None else f"{k:.2f}")
            + " bets, not like "
            + f"{n_nominal}"),
    }
