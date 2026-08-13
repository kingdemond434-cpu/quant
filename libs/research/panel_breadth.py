"""HOW MANY INDEPENDENT OBSERVATIONS DOES ONE PANEL-DAY ACTUALLY CARRY? -- measured, not assumed.

THE DEFECT THIS CLOSES, AND BOTH ENDPOINTS OF IT WERE ASSUMPTIONS. `libs/research/axis_screen.py`
turns a stacked (symbol x date) panel into a power figure by dividing the row count by the panel
width::

    deflator = max(t_deflator, 1.0) * max(int(panel_width), 1)
    n_eff    = len(zv) / deflator

That asserts a K-symbol panel carries exactly ONE independent observation per bar, for every K.
Before 2026-08-11 the same line asserted the opposite -- panel_width was not passed at all, so K
symbols carried K independent observations and every t-stat was inflated by sqrt(K) ~ 11.8x at
K=139. The desk swung from one endpoint to the other in a single change, and the change record
(`scripts/screen_oi_ls_axes.py`) names the cost of the first endpoint exactly: "42 'graveyard-grade'
SCREEN-WEAK verdicts the screen lacked the power to make". NEITHER ENDPOINT WAS EVER MEASURED. The
truth is a property of the panel, it is cheap to compute, and nothing computed it.

WHY THE SURVIVING ERROR RAN CONSERVATIVE, WHICH IS WHY NOBODY AUDITED IT. Dividing by the full K
can only ever LOWER n_eff, and a low n_eff produces SCREEN-UNDERPOWERED -- explicitly "could not
tell", never a kill. That verdict writes no graveyard entry, no ledger row, no alert and no clock,
so it is the one exit from the screen that leaves no trace, and 380 of 711 recorded verdicts on
this desk (53%, the largest class by 2.4x) sit in it. An error whose only symptom is silence is
invisible by construction. This is L1.55's own lesson -- "nobody audits a number that is already
small" -- and it is the L1.25 diagnostic's first question, *instrument?*, one layer below the two
campaign-constant gates already found.

WHAT IS MEASURED, AND WHY IT IS THE PRODUCT TERMS AND NOT THE RETURNS. A pooled IC is (up to
standardisation) the mean of ``signal[i,d] * target[i,d]`` over every cell. The variance of that
mean is set by the covariance of the SUMMANDS, so the quantity that governs its standard error is
the average pairwise cross-sectional correlation of the PRODUCTS -- not of the raw returns and not
of the demeaned returns. The three differ enormously and the difference is the whole finding.
Measured 2026-08-13 on the desk's own 139-symbol futclose panel, 1,897 dates:

    RAW returns                     rho = +0.5288   ->  effective breadth   1.88
    RELATIVE (demeaned) returns     rho = -0.0069   ->  effective breadth 139.00  (capped)
    PRODUCT TERMS signal*target     rho = +0.0067   ->  effective breadth  72.27

Read those three rows in order, because each one refutes a different tempting shortcut. The RAW
row is why the 2026-08-11 change looked right: against a raw-return target, K symbols really are
worth about 1.9 bets and dividing by K is nearly correct. The RELATIVE row is why it is wrong
here: the screen's target IS the cross-sectionally demeaned return, whose residual correlation
sits at -0.0069 against a `demeaning_floor(139)` of -0.00725 -- 95% of the way to a number that
pure arithmetic produces from data with no structure at all. And the RELATIVE row is ALSO why the
pre-08-11 endpoint is wrong: reading breadth off it returns the full K, because the demeaning
constraint forces it there, which is precisely the misreading `cohort_independence.effective_bets`
was clamped to prevent after it reported "64.4 independent bets from 29 perps". Only the PRODUCT
row is both measured and relevant, and it lands between the two endpoints, near neither.

So the honest deflator for that panel is 139 / 72.27 = 1.92, not 139: n_eff was understated 72x
and the detection floor inflated sqrt(72) = 8.5x.

THIS MODULE MEASURES; IT NEVER ASSUMES. There is no default breadth, no fallback constant and no
"reasonable prior". A panel that cannot be measured returns UNMEASURABLE and the screen's caller
keeps the conservative full-K deflator it has today -- absence resolves to the tighter reading,
never to a clean one (L1.28a, WS-005).

NOTHING HERE PROMOTES ANYTHING, LOOSENS ANY BAR, OR SIZES ANYTHING. ic_min, sharpe_min, the
angle-20 de-contamination gate, the Holm correction, alpha and MAX_FORWARD_SLOTS are untouched.
This changes one denominator in one power calculation from a guess to a measurement, and the
measurement is capable of moving it in EITHER direction: on a raw-return panel it would confirm
the full-K deflator, and it says so.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from libs.research.cohort_independence import demeaning_floor, effective_bets

#: Minimum finite observations a symbol's product series needs before it can enter the pairwise
#: correlation. Below this its correlation with anything is estimation noise.
MIN_OBS_PER_SYMBOL = 60

#: Observations per symbol below which the mean off-diagonal correlation is dominated by
#: estimation noise and biased UPWARD (the Marchenko-Pastur regime). Same constant and same
#: reasoning as `cohort_independence._MIN_OBS_PER_SERIES`, restated because the consequence here
#: is different: an upward-biased rho UNDERSTATES breadth, which is the conservative direction, so
#: this is REPORTED rather than refused.
NOISE_OBS_PER_SYMBOL = 3


@dataclass(frozen=True)
class PanelBreadth:
    """The measured cross-sectional breadth of one panel, with its own refusal path."""

    status: str                      # MEASURED | UNMEASURABLE
    n_symbols: int                   # K actually measured (degenerate columns dropped)
    n_symbols_declared: int          # K handed in, before drops
    n_dates: int
    mean_corr: float
    floor: float                     # demeaning_floor(K): what arithmetic alone produces
    xs_neff: float                   # independent cross-sectional bets per date
    deflator: float                  # panel_width / xs_neff -- what the power model divides by
    noise_dominated: bool
    dropped: dict[str, int] = field(default_factory=dict)
    why: str = ""

    @property
    def measured(self) -> bool:
        return self.status == "MEASURED"

    def summary(self) -> str:
        if not self.measured:
            return f"UNMEASURABLE: {self.why}"
        return (f"K={self.n_symbols} over {self.n_dates} dates, product-term rho="
                f"{self.mean_corr:+.5f} (arithmetic floor {self.floor:+.5f}) -> "
                f"{self.xs_neff:.2f} independent bets/date, deflator {self.deflator:.2f}x "
                f"(vs {self.n_symbols_declared:.0f}x assumed)"
                + (" [NOISE-DOMINATED]" if self.noise_dominated else ""))

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "n_symbols": self.n_symbols,
                "n_symbols_declared": self.n_symbols_declared, "n_dates": self.n_dates,
                "mean_corr": None if not np.isfinite(self.mean_corr) else round(self.mean_corr, 6),
                "floor": round(self.floor, 6),
                "xs_neff": None if not np.isfinite(self.xs_neff) else round(self.xs_neff, 3),
                "deflator": None if not np.isfinite(self.deflator) else round(self.deflator, 3),
                "noise_dominated": self.noise_dominated, "dropped": dict(self.dropped),
                "why": self.why}


def _unmeasurable(why: str, *, k_decl: int = 0, n_dates: int = 0,
                  dropped: dict[str, int] | None = None) -> PanelBreadth:
    nan = float("nan")
    return PanelBreadth("UNMEASURABLE", 0, int(k_decl), int(n_dates), nan,
                        demeaning_floor(max(k_decl, 2)), nan, nan, False,
                        dropped or {}, why)


def measure_panel_breadth(signal: np.ndarray, target: np.ndarray, *,
                          min_obs: int = MIN_OBS_PER_SYMBOL) -> PanelBreadth:
    """Independent cross-sectional observations per date, from the panel's own product terms.

    ``signal`` and ``target`` are 2-D (dates x symbols) and ALIGNED THE WAY THE SCREEN SCORES
    THEM: ``target[d, i]`` is the return the caller is predicting from ``signal[d, i]``. Pass the
    same shift the screen applies, or this measures the breadth of a pairing nobody screened.

    EVERY DISCARD IS COUNTED (L2.4/L1.60). Columns leave for three distinct reasons -- too few
    finite products, zero variance, or a non-finite correlation row -- and each is reported
    separately in ``dropped`` rather than silently shrinking K. A column that vanishes without a
    reason makes "this symbol was out of scope" and "this symbol broke the estimator" identical to
    every reader, and only one of those is a defect.
    """
    s = np.asarray(signal, dtype="float64")
    t = np.asarray(target, dtype="float64")
    if s.ndim != 2 or t.ndim != 2 or s.shape != t.shape:
        return _unmeasurable("signal and target must be the same 2-D (dates x symbols) shape")
    n_dates, k_decl = s.shape
    if k_decl < 2:
        return _unmeasurable("a cross-section needs at least 2 symbols", k_decl=k_decl,
                             n_dates=n_dates)

    # The summands of the pooled IC. Non-finite in EITHER leg makes the cell unusable, which is
    # what the screen's own pairing does when it drops unpaired rows.
    prod = s * t
    prod[~np.isfinite(prod)] = np.nan

    dropped: dict[str, int] = {}
    finite = np.isfinite(prod).sum(axis=0)
    sparse = finite < int(min_obs)
    dropped["too_few_obs"] = int(sparse.sum())
    keep = ~sparse
    if keep.sum() >= 2:
        with np.errstate(invalid="ignore"):
            var = np.nanvar(prod[:, keep], axis=0)
        dead = ~(var > 0)
        dropped["zero_variance"] = int(dead.sum())
        idx = np.flatnonzero(keep)[~dead]
    else:
        dropped["zero_variance"] = 0
        idx = np.flatnonzero(keep)

    if idx.size < 2:
        return _unmeasurable(
            f"fewer than 2 symbols survive the {min_obs}-observation floor "
            f"({dropped.get('too_few_obs', 0)} too sparse, "
            f"{dropped.get('zero_variance', 0)} degenerate)",
            k_decl=k_decl, n_dates=n_dates, dropped=dropped)

    m = prod[:, idx]
    # PAIRWISE-COMPLETE, because symbols list on different dates and complete-case deletion would
    # throw away the entire early history to accommodate the youngest symbol. np.ma.corrcoef does
    # exactly this deletion per pair; mean-imputing instead would bias every correlation toward
    # zero, which INFLATES breadth -- the over-claim direction this module exists to prevent.
    with np.errstate(invalid="ignore", divide="ignore"):
        # numpy ships np.ma.corrcoef untyped; the ignore is on the CALL, not the result, so a
        # future typed numpy turns this into an unused-ignore error rather than hiding a real one.
        c = np.ma.corrcoef(  # type: ignore[no-untyped-call]
            np.ma.masked_invalid(m), rowvar=False, allow_masked=True)
    cm = np.ma.filled(c, np.nan)
    k = cm.shape[0]
    iu = np.triu_indices(k, k=1)
    pair = cm[iu]
    bad_pairs = int((~np.isfinite(pair)).sum())
    pair = pair[np.isfinite(pair)]
    dropped["non_finite_pairs"] = bad_pairs
    if pair.size == 0:
        return _unmeasurable("no finite pairwise correlations between product series",
                             k_decl=k_decl, n_dates=n_dates, dropped=dropped)

    rho = float(np.mean(pair))
    xs_neff = effective_bets(k, rho)
    # The deflator is stated against the DECLARED width, because that is what the power model
    # divides by and what the caller will replace. Dropped columns contribute no evidence, so
    # they must not silently reduce the correction.
    deflator = max(float(k_decl), 1.0) / max(xs_neff, 1.0)
    obs = float(np.isfinite(m).sum()) / max(k, 1)
    return PanelBreadth(
        status="MEASURED", n_symbols=int(k), n_symbols_declared=int(k_decl),
        n_dates=int(n_dates), mean_corr=rho, floor=demeaning_floor(k), xs_neff=float(xs_neff),
        deflator=float(max(deflator, 1.0)), noise_dominated=bool(obs < NOISE_OBS_PER_SYMBOL * k),
        dropped=dropped, why="")


def breadth_deflator(panel_width: int, xs_neff: float | None) -> float:
    """What the power model should divide the stacked row count by. Never below 1.

    THE DEFLATOR ONLY EVER DEFLATES, which is the invariant `axis_screen` already enforces and
    already paid for once (a sub-daily horizon inverted it into a 1,449x MULTIPLIER). Here it
    holds by construction rather than by clamp: `effective_bets` is bounded above by K, so
    K / xs_neff >= 1 always. The clamp stays anyway -- an invariant that depends on a callee's
    internals is one refactor away from being untrue.

    ``xs_neff`` of None is the REFUSAL, not a default: an unmeasured panel keeps the full-K
    deflator it has today. Absence must never resolve to the looser reading.
    """
    w = max(int(panel_width), 1)
    if xs_neff is None or not np.isfinite(xs_neff) or xs_neff < 1.0:
        return float(w)
    return float(max(w / min(float(xs_neff), float(w)), 1.0))
