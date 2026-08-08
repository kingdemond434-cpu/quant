"""EFFECTIVE SAMPLE SIZE — how much of a row count is actually information.

THE FINDING THIS GENERALISES. A cross-lab review pointed out that adjacent rolling windows can
contain nearly identical information: a 30-day feature computed daily shares 29 of its 30 days
with yesterday's value, so a year of "365 observations" contains something closer to twelve
independent ones. Every significance test the desk runs takes `n` as an input, and `n` entering a
t-statistic under a square root means a tenfold inflation of the count is a threefold inflation of
the t. That is the difference between a discovery and noise, applied silently to every candidate.

    t = IC * sqrt(n)        n inflated 10x  ->  t inflated 3.2x

**SIX SOURCES OF DEPENDENCE, AND THEY COMPOUND RATHER THAN COMPETE.** Overlapping windows,
autocorrelation, shared events, regime concentration, a common asset factor and cross-venue
dependence each shrink the count, and a sample can suffer all six at once. The deflators multiply
because they describe different ways the same observations fail to be new.

**THIS IS NOT `evidence_clock` AND IT IS NOT `cpcv`, though all three are about dependence.**
`evidence_clock` deflates FORWARD evidence for a promotion decision -- how much a live record has
earned. `cpcv` CONSTRUCTS purged, embargoed splits so a fold cannot see its own future. This one
answers the question neither asks: given a sample already in hand, how many independent
observations does it contain, and therefore what `n` may a test legitimately use.

**IT DOES NOT THROW INFORMATION AWAY, AND THE DISTINCTION MATTERS.** The naive fix for overlap is
to subsample to non-overlapping windows, which discards most of the data and its own statistical
power along with it. Overlapping observations are not worthless -- they are worth less. The right
move is to keep the data and deflate the COUNT used in the test, which is what this computes.

Measures. Sets no threshold, kills nothing, and hands the number to whoever owns the bar.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = [
    "DEFLATORS",
    "SampleGeometry",
    "cross_dependence_deflator",
    "effective_n",
    "inflation_factor",
    "overlap_deflator",
    "serial_deflator",
    "summarise",
    "t_correction",
]

#: The six named sources, in the order the specification lists them. Present as data so a report
#: can show WHICH dependence cost the count, not merely that something did.
DEFLATORS: tuple[str, ...] = (
    "WINDOW_OVERLAP", "AUTOCORRELATION", "SHARED_EVENTS",
    "REGIME_CONCENTRATION", "COMMON_FACTOR", "CROSS_VENUE",
)


@dataclass(frozen=True)
class SampleGeometry:
    """The shape of a sample, from which its information content follows.

    Every field defaults to the value that means UNMEASURED, and every deflator returns 1.0 for
    that -- which is deliberately the OPTIMISTIC direction. A deflator that guessed downward on
    absent information would quietly kill candidates for the sin of being unmeasured, and the
    report says explicitly which deflators were inert rather than letting a clean number imply
    they all passed.
    """

    rows: int
    #: Length of the rolling window in observations. 1 = non-overlapping.
    window_length: int = 1
    #: Step between consecutive observations, in the same units. 0 = unmeasured.
    step: int = 0
    #: Lag-1 autocorrelation of the residual series. 0 = unmeasured OR genuinely independent, and
    #: the caller must distinguish them via `measured_deflators`.
    autocorrelation: float = 0.0
    #: Distinct market events the rows fall under. 0 = unmeasured.
    distinct_events: int = 0
    #: Distinct regimes covered. 0 = unmeasured.
    distinct_regimes: int = 0
    #: Number of assets, and their mean pairwise correlation.
    n_assets: int = 1
    mean_asset_rho: float = 0.0
    #: Number of venues carrying the same instrument, and their dependence.
    n_venues: int = 1
    mean_venue_rho: float = 0.0

    @property
    def measured_deflators(self) -> tuple[str, ...]:
        """Which of the six were actually measured. The rest are INERT, not passed."""
        out = []
        if self.window_length > 1 and self.step > 0:
            out.append("WINDOW_OVERLAP")
        if self.autocorrelation != 0.0:
            out.append("AUTOCORRELATION")
        if self.distinct_events > 0:
            out.append("SHARED_EVENTS")
        if self.distinct_regimes > 0:
            out.append("REGIME_CONCENTRATION")
        if self.n_assets > 1:
            out.append("COMMON_FACTOR")
        if self.n_venues > 1:
            out.append("CROSS_VENUE")
        return tuple(out)


def overlap_deflator(window_length: int, step: int) -> float:
    """Fraction of each observation that is NEW information. step/window, capped at 1.

    A 30-day window stepped daily retains 1/30 of its nominal count. This is the deflator the
    original finding named and it is usually the largest of the six by an order of magnitude.
    """
    if window_length <= 1 or step <= 0:
        return 1.0
    return min(1.0, step / window_length)


def serial_deflator(rho: float) -> float:
    """Kish deflator (1-rho)/(1+rho), clamped at rho >= 0.

    NEGATIVE autocorrelation genuinely carries more information per observation, and crediting it
    would let a mean-reverting series claim more evidence than it has rows -- an inflation in the
    one direction nobody would think to question.
    """
    r = max(0.0, min(0.99, rho))
    return (1.0 - r) / (1.0 + r)


def cross_dependence_deflator(n: int, rho: float) -> float:
    """Participation-ratio deflator for n correlated series: (1 + (n-1)*rho) / n, inverted.

    At rho = 0 this returns 1.0 -- n independent series are n samples' worth. At rho = 1 it
    returns 1/n, which is the correct and uncomfortable answer for the same instrument observed on
    several venues: it is one series wearing several tickers.
    """
    if n <= 1:
        return 1.0
    r = max(0.0, min(1.0, rho))
    return 1.0 / (1.0 + (n - 1) * r) if r > 0 else 1.0


def _regime_deflator(distinct_regimes: int) -> float:
    """Evidence drawn entirely from one regime is evidence about one regime."""
    if distinct_regimes <= 0:
        return 1.0        # unmeasured: inert, and reported as inert
    if distinct_regimes == 1:
        return 0.5
    if distinct_regimes == 2:
        return 0.8
    return 1.0


def effective_n(g: SampleGeometry) -> float:
    """Effective independent observations. NEVER larger than the row count.

    The event cap applies last and applies hard: 500 rows inside one liquidation cascade are one
    observation of one cascade, and no amount of serial independence within an event makes the
    event happen twice.
    """
    n = float(max(0, g.rows))
    if n <= 0:
        return 0.0
    n *= overlap_deflator(g.window_length, g.step)
    n *= serial_deflator(g.autocorrelation)
    n *= cross_dependence_deflator(g.n_assets, g.mean_asset_rho)
    n *= cross_dependence_deflator(g.n_venues, g.mean_venue_rho)
    n *= _regime_deflator(g.distinct_regimes)
    if g.distinct_events > 0:
        n = min(n, float(g.distinct_events))
    return max(0.0, n)


def inflation_factor(g: SampleGeometry) -> float | None:
    """rows / effective_n. How many times over the raw count overstates the evidence."""
    eff = effective_n(g)
    if eff <= 0:
        return None
    return g.rows / eff


def t_correction(t_raw: float, g: SampleGeometry) -> tuple[float | None, str]:
    """The t-statistic recomputed on the effective count. THE NUMBER THAT DECIDES THINGS.

    t scales as sqrt(n), so a corrected t is t_raw * sqrt(n_eff / n). Returned rather than
    compared: the hurdle belongs to the caller, and a module that both deflated the sample and
    ruled on significance would be marking its own homework.
    """
    eff = effective_n(g)
    if eff <= 0 or g.rows <= 0:
        return None, "effective sample is zero or the row count is unmeasured -- t is undefined"
    corrected = t_raw * math.sqrt(eff / g.rows)
    infl = g.rows / eff
    measured = list(g.measured_deflators)
    which = (str(measured) if measured else
             "NONE -- every deflator was inert, so this correction is a LOWER "
             "bound on the real one")
    return corrected, (
        f"t {t_raw:.3f} on {g.rows} rows becomes {corrected:.3f} on {eff:.1f} effective "
        f"observations ({infl:.1f}x inflation). Dependence sources measured: {which}")


def summarise(samples: dict[str, SampleGeometry]) -> dict[str, object]:
    """Report shape. Leads with the worst inflation, because that is where a false discovery is."""
    if not samples:
        return {"samples": 0, "headline": (
            "no sample geometry recorded -- every `n` this desk feeds into a significance test is "
            "a raw row count, and whether it overstates the evidence is UNMEASURED")}
    rows = []
    for name, g in samples.items():
        eff = effective_n(g)
        infl = inflation_factor(g)
        rows.append({
            "sample": name, "rows": g.rows,
            "effective_n": round(eff, 2),
            "inflation_factor": None if infl is None else round(infl, 2),
            "measured_deflators": list(g.measured_deflators),
            "inert_deflators": [d for d in DEFLATORS if d not in g.measured_deflators],
            "overlap_deflator": round(overlap_deflator(g.window_length, g.step), 4),
            "serial_deflator": round(serial_deflator(g.autocorrelation), 4),
        })
    rows.sort(key=lambda r: -(float(str(r["inflation_factor"]))
                              if r["inflation_factor"] is not None else 0.0))
    worst = rows[0]
    all_inert = [r for r in rows if not r["measured_deflators"]]
    return {
        "samples": len(samples),
        "rows": rows,
        "worst_inflation": worst["inflation_factor"],
        "unmeasured_geometry": len(all_inert),
        "headline": (
            f"worst sample {worst['sample']!r} overstates its evidence "
            f"{worst['inflation_factor']}x "
            f"({worst['rows']} rows -> {worst['effective_n']} effective); t scales as sqrt(n), so "
            f"that is a {math.sqrt(float(str(worst['inflation_factor'] or 1.0))):.1f}x inflation "
            "of every t-statistic computed on it"
            if worst["inflation_factor"] and float(str(worst["inflation_factor"])) > 1.5 else
            f"{len(all_inert)} of {len(rows)} samples have NO measured dependence geometry, so "
            "their corrections are lower bounds rather than measurements"),
        "note": ("Overlapping observations are worth LESS, not worthless. The correction deflates "
                 "the COUNT used in a test rather than subsampling the data, because discarding "
                 "rows to reach independence throws away the power it was meant to protect. "
                 "Unmeasured deflators return 1.0 -- the optimistic direction -- and are listed "
                 "as inert so a clean number cannot be read as six passed checks."),
    }
