"""CAN THIS CAMPAIGN SEE AN EDGE AT ALL -- asked BEFORE the compute is spent, not after.

WHY THIS EXISTS (2026-08-05). `scripts/run_campaign.py:94` sets `n_trials = len(candidates)`, and
`run_moat_campaign.py:144` passes `m.shape[1]`. In both, N -- the multiplicity burden every
candidate must clear -- is an ACCIDENT OF GENERATION VOLUME rather than a design decision, and
nothing anywhere computed what that N did to the campaign's resolving power. The measured
consequence is on the record in `reports/gauntlet_certification.json`: at the desk's real shape of
T=310 observations and N=420 trials the DSR hurdle is an annualised Sharpe of **5.04**, and the
power against a TRUE annual Sharpe of 3 -- a superb systematic edge -- is **2.98%**.

So the campaign that produced the desk's 420-tested / 0-survivors record would have missed a true
Sharpe-3 alpha ninety-seven times out of a hundred. That record has been read repeatedly as a fact
about the market ("price space is dead"). It is substantially a fact about the INSTRUMENT, which
is precisely the first branch of the L1.25 diagnostic -- and the desk had to hand-run a separate
certification script to discover it, weeks late, after the compute was already spent.

THE ONE THING THIS MODULE MUST NEVER BECOME. It does not stop, gate, throttle or shrink anything.
An UNDERPOWERED verdict is a LABEL on the result, never a veto on the run: refusing to run
underpowered campaigns would throttle discovery, which L1.25a ("null streaks throttle nothing")
and L1.28b(f) ("acquisition is never cut to meet extraction") both forbid outright. What changes
is only what the desk is entitled to CONCLUDE afterwards -- an underpowered null is uninformative
about the market and must never be recorded as evidence of absence. The campaign still runs, at
full breadth, every time.

Nor is it a route to a lower bar. It reads thresholds and never writes them: there is no function
here that can move DSR's tolerance, Holm, PBO or the forward-evidence law, by construction and not
merely by convention -- the same discipline `libs/execution/excitation.py` uses when it refuses to
own any vocabulary for position size. The two legitimate responses to "nothing survived" are not
symmetric: lowering a threshold MANUFACTURES survivors and is forbidden; re-shaping the experiment
buys the same resolution with every threshold left exactly where it stands.

WHY THE SUGGESTED FIX IS ORDERED THE WAY IT IS, WHICH IS THE SUBTLE PART. Two knobs set the
hurdle: T shrinks the standard error, N widens the multiplicity deflator E[max of N nulls]. Both
lower it, but they are NOT equally honest.

  * RAISING T is unambiguously legitimate. More observations is more evidence; there is no way to
    launder anything by running a longer history.
  * CUTTING N is legitimate ONLY through PRE-REGISTERED, mechanism-motivated families. Splitting
    420 pooled candidates into fourteen families of 30 does not reduce how many hypotheses the
    desk generates -- generation volume is untouched, which is what L1.40 protects -- it stops
    pooling unrelated mechanisms into one multiplicity family. But choosing those families AFTER
    seeing which candidates did well is textbook garden-of-forking-paths, and it would inflate the
    desk's false-discovery rate exactly where it is least able to detect it.

So `cheapest_fix` asks the BREADTH-PRESERVING question first -- what history rescues the campaign
with every candidate kept -- and only reaches for an N-cut when no reachable history can, with the
pre-registration condition written into its own text rather than a comment someone can skip. That
ordering is not cosmetic: on the desk's real shape the measured frontier says T=2500 clears the
target at the FULL N=420, so the honest fix is deeper history and NOT a narrower hunt. An earlier
draft of this function scanned the other way and duly recommended cutting 420 candidates to 10 --
the module reproducing, in its own advice, the narrowing reflex it exists to prevent.

UNMEASURABLE IS NEVER POWERED. A degenerate shape returns INDETERMINATE, and `informative_null()`
is False there. An unmeasured quantity reading as a measured one is the `beats_baselines` failure
this desk has already paid for once -- a gate with no production caller that therefore passed
every candidate it ever saw.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.stats import norm as _norm

from libs.validation.admission_power import POWER_TARGET
from libs.validation.dsr import expected_max_sharpe

__all__ = [
    "DEFAULT_TARGET_SHARPE",
    "INDETERMINATE",
    "POWERED",
    "UNDERPOWERED",
    "Design",
    "design_power",
    "dsr_hurdle_annual",
    "preflight",
]

POWERED = "POWERED"
UNDERPOWERED = "UNDERPOWERED"
INDETERMINATE = "INDETERMINATE"

#: Periods per year for daily bars -- matches the gauntlet's own annualisation.
PPY = 365.0

#: The DSR tolerance the production gate applies. Imported semantics, restated as a module
#: constant only so the hurdle solve can invert it; `preflight` never writes it anywhere.
DSR_THRESHOLD = 0.95

#: The true annualised Sharpe the desk designs to RESOLVE. Deliberately 2.0, not 5.0: a
#: world-class systematic book runs 2-3, so a campaign that only resolves above 5 resolves
#: nothing that actually exists. The old "certified floor of 5.0" was never a target -- it was
#: the smallest level at which the all-gates rule passed anything at all.
DEFAULT_TARGET_SHARPE = 2.0

#: Shapes to price when proposing a fix. T rows are ordered ASCENDING so the scan prefers the
#: least extra history that works; N columns DESCENDING so it keeps as much breadth as possible.
_FIX_T = (310, 620, 1250, 2500, 5000)
_FIX_N = (420, 200, 100, 30, 10, 5)

_TRUE_SR_GRID = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0)


def dsr_hurdle_annual(n_trials: int, n_obs: int, *, var_sharpes: float | None = None,
                      ppy: float = PPY) -> float:
    """The observed ANNUALISED Sharpe a candidate must post to clear the DSR gate.

    Derived from the desk's own `expected_max_sharpe` primitive rather than restated, so the
    number moves if the gate moves. Inlining the deflator as a literal would let this drift
    silently away from the gate it claims to describe.

    `var_sharpes` defaults to the NULL dispersion 1/T -- the variance of sample Sharpes across
    zero-edge candidates -- which makes the result a FLOOR. A real cohort disperses more than
    noise and `expected_max_sharpe` scales linearly in that dispersion, so the live hurdle is
    >= this, never below it. Reporting the floor keeps every verdict conservative in the safe
    direction: this module can understate how underpowered a campaign is, never overstate it.
    """
    sr0 = expected_max_sharpe(n_trials, (1.0 / n_obs) if var_sharpes is None else var_sharpes)
    # dsr >= threshold  <=>  z >= Phi^-1(threshold), with z = (sr - sr0)*sqrt(T-1)/sqrt(denom)
    # and denom -> 1 for near-normal returns. Solve for sr, then annualise.
    z = float(_norm.ppf(DSR_THRESHOLD))
    return float((sr0 + z / np.sqrt(max(1, n_obs - 1))) * np.sqrt(ppy))


def design_power(n_trials: int, n_obs: int, *, ppy: float = PPY) -> dict[str, Any]:
    """The full power curve for a campaign shape -- what size of edge it can actually find."""
    se = float(np.sqrt(ppy / n_obs))
    hurdle = dsr_hurdle_annual(n_trials, n_obs, ppy=ppy)
    power = {f"{s:g}": float(1.0 - _norm.cdf((hurdle - s) / se)) for s in _TRUE_SR_GRID}
    blind_to = [s for s in _TRUE_SR_GRID if power[f"{s:g}"] < POWER_TARGET]
    return {
        "dsr_threshold": DSR_THRESHOLD,
        "n_trials": n_trials,
        "n_obs": n_obs,
        "periods_per_year": ppy,
        "se_annual_sharpe": se,
        "hurdle_annual_sharpe": hurdle,
        "power_by_true_annual_sharpe": power,
        "blind_below_annual_sharpe": (max(blind_to) if blind_to else None),
        "hurdle_is_a_floor": "null dispersion assumed; a real cohort disperses more, so the live "
                             "hurdle is >= this, never below it",
    }


def _power_at(n_trials: int, n_obs: int, target: float, ppy: float = PPY) -> float:
    se = float(np.sqrt(ppy / n_obs))
    return float(1.0 - _norm.cdf((dsr_hurdle_annual(n_trials, n_obs, ppy=ppy) - target) / se))


@dataclass(frozen=True)
class Design:
    """A campaign's resolving power, priced before its compute is spent."""

    n_trials: int
    n_obs: int
    target_true_sharpe: float
    periods_per_year: float
    hurdle_annual_sharpe: float
    se_annual_sharpe: float
    power_at_target: float
    verdict: str
    blind_below_annual_sharpe: float | None
    cheapest_fix: dict[str, Any] | None
    power_curve: dict[str, float] = field(default_factory=dict)
    note: str = ""

    def informative_null(self) -> bool:
        """May a zero-survivor result from this campaign be read as evidence about the market?

        Only when the design could actually have SEEN the edge it was hunting. INDETERMINATE
        answers False for the same reason UNDERPOWERED does -- an unmeasured design is not a
        powered one, and treating it as such is how "we tested 420 and found nothing" becomes a
        belief about the world instead of a fact about the experiment.
        """
        return self.verdict == POWERED

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_trials": self.n_trials,
            "n_obs": self.n_obs,
            "target_true_sharpe": self.target_true_sharpe,
            "periods_per_year": self.periods_per_year,
            "hurdle_annual_sharpe": self.hurdle_annual_sharpe,
            "se_annual_sharpe": self.se_annual_sharpe,
            "power_at_target": self.power_at_target,
            "verdict": self.verdict,
            "blind_below_annual_sharpe": self.blind_below_annual_sharpe,
            "cheapest_fix": self.cheapest_fix,
            "power_curve": self.power_curve,
            "informative_null": self.informative_null(),
            "note": self.note,
        }

    def summary(self) -> str:
        if self.verdict == INDETERMINATE:
            return f"[campaign-design] INDETERMINATE -- {self.note}"
        head = (f"[campaign-design] {self.verdict} N={self.n_trials} T={self.n_obs}: "
                f"hurdle {self.hurdle_annual_sharpe:.2f} annual Sharpe, power "
                f"{self.power_at_target:.1%} at true Sharpe {self.target_true_sharpe:g}")
        if self.verdict == POWERED:
            return head
        fix = self.cheapest_fix
        tail = (f" -- FIX: {fix['shape']} reaches {fix['power']:.0%} ({fix['legitimacy']})"
                if fix else " -- NO SHAPE ON THE GRID REACHES THE TARGET; the binding constraint "
                             "is history length, so this needs deeper data, not a lower bar")
        return (head + tail + ". A null from this campaign is UNINFORMATIVE about the market and "
                "must not be recorded as evidence of absence (L1.25).")


def _cheapest_fix(n_trials: int, n_obs: int, target: float,
                  ppy: float = PPY) -> dict[str, Any] | None:
    """The least-cost shape that reaches POWER_TARGET, preferring BREADTH-PRESERVING fixes.

    THE ORDERING IS THE WHOLE POINT, and the first draft of this function got it backwards in a
    way worth recording. It scanned T ascending and, at each T, took the first N that worked --
    which for the desk's real shape returned "T=1250, N=10": cut the campaign from 420 candidates
    to 10. That is the narrow-the-hunt reflex this module was written to prevent, produced by the
    module itself. The measured frontier says something much better: at T=2500 the FULL N=420
    reaches 72% power, so the desk never needed to test fewer things at all -- it needed deeper
    history, which costs nothing but a backfill and launders nothing.

    So the scan now asks the breadth-preserving question FIRST: what is the smallest T at which
    the campaign's OWN n_trials clears the target? Only when no available history can rescue the
    requested breadth does it consider narrowing, and it says plainly that narrowing is sound only
    through pre-registered mechanism families.
    """
    # 1. Breadth-preserving: keep every candidate, buy resolution with history alone.
    for t in _FIX_T:
        if t > n_obs and _power_at(n_trials, t, target, ppy) >= POWER_TARGET:
            return {
                "shape": f"T={t}, N={n_trials}",
                "n_obs": t,
                "n_trials": n_trials,
                "power": _power_at(n_trials, t, target, ppy),
                "hurdle_annual_sharpe": dsr_hurdle_annual(n_trials, t, ppy=ppy),
                "extra_observations_needed": t - n_obs,
                "narrows_the_hunt": False,
                "legitimacy": ("raising T only, FULL BREADTH KEPT -- unambiguously legitimate, "
                               "strictly more evidence, no candidate dropped"),
            }
    # 2. Only now consider narrowing, and only with the pre-registration condition attached.
    for t in _FIX_T:
        for n in _FIX_N:
            if n >= n_trials or _power_at(n, t, target, ppy) < POWER_TARGET:
                continue
            return {
                "shape": f"T={t}, N={n}",
                "n_obs": t,
                "n_trials": n,
                "power": _power_at(n, t, target, ppy),
                "hurdle_annual_sharpe": dsr_hurdle_annual(n, t, ppy=ppy),
                "extra_observations_needed": max(0, t - n_obs),
                "narrows_the_hunt": True,
                "legitimacy": ("no reachable history rescues the full breadth, so this splits the "
                               "campaign into PRE-REGISTERED mechanism families chosen BEFORE any "
                               "result is seen -- never post-hoc, and never by generating fewer "
                               "hypotheses (L1.40): the same candidates, honestly grouped"),
            }
    return None


def preflight(n_trials: int, n_obs: int, *,
              target_true_sharpe: float = DEFAULT_TARGET_SHARPE,
              ppy: float = PPY) -> Design:
    """Price a campaign's resolving power BEFORE it runs. Never blocks; only labels.

    Returns INDETERMINATE -- explicitly not POWERED -- for any shape too degenerate to price.

    `ppy` is the caller's OWN annualisation and every caller must pass its real one. The default
    is daily bars; an intraday campaign annualises by bars-per-year instead, and silently letting
    it inherit 365 would report a hurdle for an experiment nobody ran. That is the mixed-scope
    error the desk has already paid for twice -- the futures-vs-total NAV comparison and the
    L1.46 clock-provenance corpus -- so a wrong `ppy` is refused rather than assumed.
    """
    if not np.isfinite(ppy) or ppy <= 0:
        return Design(
            n_trials=n_trials, n_obs=n_obs, target_true_sharpe=target_true_sharpe,
            periods_per_year=ppy,
            hurdle_annual_sharpe=float("inf"), se_annual_sharpe=float("inf"),
            power_at_target=0.0, verdict=INDETERMINATE, blind_below_annual_sharpe=None,
            cheapest_fix=None,
            note=(f"periods_per_year={ppy} is not an annualisation -- design not priced. "
                  "Treated as NOT powered."),
        )
    bad = None
    if n_trials < 1:
        bad = f"n_trials={n_trials} is not a campaign"
    elif n_obs < 2:
        bad = f"n_obs={n_obs} cannot support a Sharpe standard error"
    elif not np.isfinite(target_true_sharpe) or target_true_sharpe <= 0:
        bad = f"target_true_sharpe={target_true_sharpe} is not a resolvable edge"
    if bad is not None:
        return Design(
            n_trials=n_trials, n_obs=n_obs, target_true_sharpe=target_true_sharpe,
            periods_per_year=ppy,
            hurdle_annual_sharpe=float("inf"), se_annual_sharpe=float("inf"),
            power_at_target=0.0, verdict=INDETERMINATE, blind_below_annual_sharpe=None,
            cheapest_fix=None,
            note=(f"{bad} -- design not priced. Treated as NOT powered: an unmeasured design "
                  "must never read as a measured one."),
        )

    curve = design_power(n_trials, n_obs, ppy=ppy)
    power = _power_at(n_trials, n_obs, target_true_sharpe, ppy)
    powered = power >= POWER_TARGET
    return Design(
        n_trials=n_trials,
        n_obs=n_obs,
        target_true_sharpe=target_true_sharpe,
        periods_per_year=ppy,
        hurdle_annual_sharpe=curve["hurdle_annual_sharpe"],
        se_annual_sharpe=curve["se_annual_sharpe"],
        power_at_target=power,
        verdict=POWERED if powered else UNDERPOWERED,
        blind_below_annual_sharpe=curve["blind_below_annual_sharpe"],
        cheapest_fix=(None if powered
                      else _cheapest_fix(n_trials, n_obs, target_true_sharpe, ppy)),
        power_curve=curve["power_by_true_annual_sharpe"],
        note=("design resolves the target edge more often than not"
              if powered else
              "the campaign may run at full breadth -- what it may not do is have its null "
              "recorded as evidence that the space is empty"),
    )
