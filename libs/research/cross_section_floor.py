"""A CROSS-SECTIONAL AGGREGATE OVER A THIN CROSS-SECTION IS NOISE WEARING A SIGNAL'S CLOTHES.

WHAT THIS MEASURES. Collapsing a (dates x symbols) panel down the SYMBOL axis -- `mean(axis=1)`,
a cross-sectional demean, a rank, a z-score -- produces one number per date. On a date where only
one or two symbols are finite that number is not an estimate of anything: it is one symbol's noise.
And the failure does not stay local, which is the part that makes it dangerous. Consecutive thin
dates produce consecutive wild values, so the SERIES acquires structure that the underlying data
never had.

THE MEASUREMENT THAT PRODUCED THIS MODULE (2026-08-13, capability-hunt seat 4). Hunting a
different defect entirely -- an unmeasured time denominator in `axis_screen` -- the falsifier
measured lag-1 autocorrelation of pooled-IC summands on the desk's own 139-symbol futclose panel
and reported rho = +0.856 on `M2_oi_growth|h=5`, which would have deflated that cell's effective
sample by 12.9x. It was an artifact. TWELVE dates out of 311 carried 98.1% of the lag-1 numerator,
and the floored answer is rho = -0.06. A statistic 98% determined by 4% of its input read as a
strong, clean, publishable measurement.

WHY THE OBVIOUS GUARD DOES NOT CATCH IT, AND THIS IS THE WHOLE POINT. The idiom this desk reaches
for is `if panel.shape[1] < N`. That counts DECLARED COLUMNS -- the panel's WIDTH -- and a ragged
panel's width is a property of its widest date. A 373-symbol panel passes `shape[1] >= 8` on a date
where six symbols are finite. The guard reads like a breadth guard, is documented like a breadth
guard, and checks a number that cannot fall when the cross-section empties. It is the L1.57
defect -- a denominator that counts what the author wrote down rather than what the run found --
one axis over.

THE REFUSAL IS THE LOAD-BEARING PART (L1.28a). `status` is UNMEASURABLE when the panel cannot
carry the question at all, and an UNMEASURABLE panel yields a mask that admits NOTHING. Absence
resolves to the tighter answer, never to a clean one: a caller that ignores the status and uses
the mask anyway gets no dates rather than every date.

EVERY DROPPED DATE IS COUNTED (L1.60). `n_thin` and `thin_dates` are published beside the mask, so
"this date was out of scope" and "this date could not carry a cross-section" are never
byte-identical to a reader. A date that vanishes without a reason is the attrition defect.

ANTI-TIMIDITY READING (L1.28, required of every restraint clause). This is a MEASUREMENT duty and
a SCOPE EXPANSION. It lifts nothing, sizes nothing, promotes nothing, opens no gate and loosens no
statistical bar. It DISCARDS dates that carry no cross-sectional information, which strictly
increases what the desk can believe about the dates it keeps -- and every error it prevents points
the same way: toward a series that looked more structured than its data ever was.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

__all__ = ["DEFAULT_MIN_SYMBOLS", "CrossSection", "apply_floor", "measure_cross_section"]

# A cross-sectional mean of two names is a two-name average, not a cross-section. This default is
# a FLOOR ON THE FLOOR, not a recommendation: callers that already declare a domain minimum
# (screen_oi_ls_axes uses 20, backfill_oi_ls_oos uses 8) pass their own and keep it.
DEFAULT_MIN_SYMBOLS = 8


@dataclass(frozen=True)
class CrossSection:
    """What a per-date collapse of this panel actually rests on."""

    status: str                      # MEASURED | UNMEASURABLE
    n_dates: int                     # rows handed in
    n_usable: int                    # rows clearing the floor
    n_thin: int                      # rows dropped for a thin cross-section
    min_symbols: int                 # the floor applied
    finite_min: int                  # thinnest cross-section seen
    finite_median: float             # typical cross-section width
    n_columns: int                   # DECLARED width -- the number `shape[1]` would have reported
    mask: np.ndarray = field(repr=False, default_factory=lambda: np.zeros(0, dtype=bool))
    thin_dates: tuple[int, ...] = ()  # row indices dropped, for a caller that must explain itself
    why: str = ""

    @property
    def measured(self) -> bool:
        return self.status == "MEASURED"

    @property
    def thin_fraction(self) -> float:
        return self.n_thin / self.n_dates if self.n_dates else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status, "n_dates": self.n_dates, "n_usable": self.n_usable,
            "n_thin": self.n_thin, "thin_fraction": round(self.thin_fraction, 4),
            "min_symbols": self.min_symbols, "finite_min": self.finite_min,
            "finite_median": self.finite_median, "n_columns_declared": self.n_columns,
            # The two numbers a reader needs to see the near-miss: a panel can declare 373 columns
            # and carry 6 finite names on its thinnest date.
            "thin_dates": list(self.thin_dates[:32]), "why": self.why,
        }


def _unmeasurable(why: str, *, n_dates: int = 0, n_columns: int = 0,
                  min_symbols: int = DEFAULT_MIN_SYMBOLS) -> CrossSection:
    return CrossSection(
        status="UNMEASURABLE", n_dates=int(n_dates), n_usable=0, n_thin=int(n_dates),
        min_symbols=int(min_symbols), finite_min=0, finite_median=0.0, n_columns=int(n_columns),
        mask=np.zeros(int(n_dates), dtype=bool), thin_dates=tuple(range(int(n_dates))), why=why)


def measure_cross_section(panel: Any, *, min_symbols: int = DEFAULT_MIN_SYMBOLS) -> CrossSection:
    """How many finite symbols each date actually carries, and which dates may be collapsed.

    ``panel`` is 2-D (dates x symbols) -- a DataFrame or an array. Pass the panel the collapse will
    actually run on: measuring one frame and collapsing another measures nothing.

    THE FLOOR IS ON FINITE VALUES PER ROW, never on ``shape[1]``. Those two numbers are equal only
    on a rectangular panel, and no panel assembled from live venue data is rectangular -- symbols
    list, delist, and gap.
    """
    arr = getattr(panel, "to_numpy", lambda: panel)()
    a = np.asarray(arr, dtype="float64")
    if a.ndim != 2:
        return _unmeasurable(f"a cross-section needs a 2-D (dates x symbols) panel, got {a.ndim}-D",
                             min_symbols=min_symbols)
    n_dates, n_cols = a.shape
    floor = max(int(min_symbols), 2)
    if n_dates == 0 or n_cols == 0:
        return _unmeasurable("panel is empty", n_dates=n_dates, n_columns=n_cols,
                             min_symbols=floor)
    if n_cols < floor:
        # The panel is too narrow for the floor to ever be cleared. This is a REFUSAL and not a
        # quiet pass-through: silently lowering the floor to the panel's width is exactly the
        # `shape[1]` mistake, arrived at from the other direction.
        return _unmeasurable(
            f"panel declares {n_cols} columns, below the {floor}-symbol floor: no date in it can "
            f"carry a cross-section this wide", n_dates=n_dates, n_columns=n_cols,
            min_symbols=floor)

    finite = np.isfinite(a).sum(axis=1)
    mask = finite >= floor
    thin = np.flatnonzero(~mask)
    if not mask.any():
        return _unmeasurable(
            f"no date carries {floor} finite symbols (thickest is {int(finite.max())})",
            n_dates=n_dates, n_columns=n_cols, min_symbols=floor)

    return CrossSection(
        status="MEASURED", n_dates=int(n_dates), n_usable=int(mask.sum()), n_thin=int(thin.size),
        min_symbols=floor, finite_min=int(finite.min()), finite_median=float(np.median(finite)),
        n_columns=int(n_cols), mask=mask, thin_dates=tuple(int(i) for i in thin),
        why="")


def apply_floor(panel: Any, *, min_symbols: int = DEFAULT_MIN_SYMBOLS,
                ) -> tuple[Any, CrossSection]:
    """Blank out every date whose cross-section is too thin, and say what was blanked.

    Returns ``(panel_with_thin_dates_masked, CrossSection)``. The panel keeps its shape and index
    so downstream alignment is untouched -- thin rows become NaN rather than disappearing, which
    is what every caller in this repo already does with its own floor (`rel.where(enough)`).

    AN UNMEASURABLE PANEL COMES BACK FULLY MASKED. A caller that skips the status still cannot
    collapse a cross-section that was never there.
    """
    cs = measure_cross_section(panel, min_symbols=min_symbols)
    keep = cs.mask
    if hasattr(panel, "where") and hasattr(panel, "index"):        # pandas
        import pandas as pd
        if keep.size != len(panel.index):
            keep = np.zeros(len(panel.index), dtype=bool)
        return panel.where(pd.Series(keep, index=panel.index), other=np.nan), cs
    out = np.array(np.asarray(panel, dtype="float64"), copy=True)
    if out.ndim == 2:
        if keep.size != out.shape[0]:
            keep = np.zeros(out.shape[0], dtype=bool)
        out[~keep, :] = np.nan
    return out, cs
