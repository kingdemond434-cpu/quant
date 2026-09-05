"""The heat law: one fixed outer envelope, and growth chooses the exposure inside it.

THE HIERARCHY, in the principal's words (2026-09-02):

    high fixed hard ceiling  >  robust E[log W] chooses actual heat  >  all validated edges
    compete jointly for it

    H_actual = clip(H*_robust, HEAT_TARGET, HEAT_HARD_CEILING)

and NOT `H_actual = HEAT_HARD_CEILING` (that is overbetting whenever the optimum is lower), and
NOT a ceiling that shrinks every time uncertainty wiggles (that is a ceiling that becomes the
growth bottleneck, which is the failure this module exists to end).

WHAT WAS HERE BEFORE. `gateway.heat_budget()` computed a ceiling that MOVED: base heat scaled by
sqrt(k_eff / 2.26), capped at 15%. Two things were wrong with it. It was a CEILING, so the desk's
actual exposure was whatever happened to fit under it rather than what growth wanted -- and it
moved DOWNWARD on exactly the evidence that should raise exposure, because k_eff is measured on a
live ledger that was empty until 2026-09-01, so it returned its 3.81% floor on every call the
desk has ever made. The desk ran at a fifth of its stated budget and nothing said so.

THREE LAYERS, and only the third may reduce exposure below target:

  1. HEAT_HARD_CEILING -- the outer envelope. Catastrophe containment. Never crossed.
  2. Robust E[log W] -- picks H* inside it, and the full-utilisation mandate floors that at
     HEAT_TARGET so a certified book keeps its budget working.
  3. The integrity layer (`catastrophe_override`) -- broker malfunction, stale prices, unknown
     exposure, reconciliation failure. This is NOT the allocator turning conservative; it is the
     refusal to keep 20% of the account exposed when the desk cannot say what the 20% consists of.

CERTIFICATION IS PART OF THE LAW, not a footnote. Forcing full utilisation only maximises growth
while the target sits at or below the peak of the growth curve. `certify()` measures that on the
live world population every pass, and `resolve()` carries the verdict, so a target that stops
being safe is visible in the artifact rather than argued about from memory.

THE FLOOR COUNTS NOMINAL HEAT AND THE CEILING COUNTS EFFECTIVE HEAT, and that asymmetry is the
whole of `effective_ceiling()`. It is deliberate, it is not a compromise, and it follows from what
each bar is FOR:

    the FLOOR is a standing instruction to have capital at work -- "minimum cover 20% heat cap
    24/7 deployed minimum". Twenty per cent must be OUT THERE, in real positions, whatever the
    correlation between them; measuring the floor in effective terms would let the desk claim it
    had deployed 20% while holding 45% nominal, which is the opposite of what was asked for.

    the CEILING is catastrophe containment, and catastrophes do not care how many tickets are
    open. "XAU long, EURUSD short, GBPUSD short, AUDUSD short may be one giant hidden USD
    exposure" -- four sleeves that are one bet lose like one bet at four times the size. So the
    room ABOVE the floor is earned with EFFECTIVE independent risk: H_eff = max(covariance,
    factor, tail) heat from `libs.portfolio.latent_factors.effective`, and the breadth it implies
    (N_eff = (nominal / H_eff)^2) buys nominal heat at the desk's own sqrt-breadth law.

The cap is registered as the `effective_heat_ceiling` rail so `research/missed_growth.py` bills
what it costs, and it can never pull the book below the floor: a concentrated book is held at 20%
and told to go find independent risk, never de-risked to 13% on a correlation estimate.

H*_t IS CONDITIONED ON THE STATE. "Dynamic 20-30% heat should use marginal opportunity: H*_t =
argmax_{H in [20,30]} E[logW | X_t]; learn the surface, don't map it manually." `state_target()`
reads the growth curve measured on the CURRENT state's own worlds and returns its argmax inside
the band. It may only RAISE the resolved heat: a state whose curve wants LESS than the
unconditional optimum does not get to cut, because a reduction is a rail and this one has not
proved its dE[log W] (growth governance, rule 1).
"""
from __future__ import annotations

import math
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
for _p in (str(BASE), str(BASE.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk.gateway_config_fallback import (  # noqa: E402
    HEAT_HARD_CEILING,
    HEAT_TARGET,
    MAX_DRAWDOWN_TOLERANCE,
    MAX_FAMILY_HEAT_SHARE,
    MAX_SLEEVE_HEAT_SHARE,
    risk_per_trade,
)

__all__ = [
    "CERTIFY_TOLERANCE",
    "EFFECTIVE_BREADTH_REF",
    "HEAT_HARD_CEILING",
    "HEAT_TARGET",
    "MAX_FAMILY_HEAT_SHARE",
    "MIN_STATE_WORLDS",
    "READY_SCALE",
    "HeatVerdict",
    "StateCurve",
    "catastrophe_override",
    "certify",
    "effective_ceiling",
    "enforce_family_cap",
    "evidence_readiness",
    "per_sleeve_bounds",
    "resolve",
    "state_target",
]

#: A sleeve with no measured drawdown cannot have a drawdown-derived bound, and the honest
#: answer is not "unlimited". This is the R-drawdown assumed for such a sleeve -- the armed
#: book's own worst, so an unmeasured sleeve is bounded as tightly as the most-measured one.
_DEFAULT_DD_R = 33.7


#: Out-of-sample day-equivalents at which the desk is considered to have "a good amount of live
#: edges" and the utilisation target applies in full. Forward days count 4x and live days 12x
#: (`robust_elog._posterior_mu`), so this is reached by roughly 60 forward days across the book,
#: or 20 live ones. The same 250-day scale the selection-penalty relief uses -- one number, not
#: two that can drift.
READY_SCALE = 250.0


def evidence_readiness(oos_by_sleeve: dict[str, float],
                       heat_by_sleeve: dict[str, float]) -> tuple[float, str]:
    """How far the book has earned its utilisation target, in [0, 1].

    "once we have a good amount of live edges it should increase to 20 percent itself daily"
                                                            -- the principal, 2026-09-02

    THE TARGET IS EARNED, NOT ASSERTED. Forcing 20% while the book's expected growth rests on
    backtests is overbetting a prior; refusing to ever reach 20% wastes the opportunity set once
    the evidence exists. This measures the difference and lets the floor ramp between them, so
    the desk arrives at full utilisation by accumulating the evidence that justifies it rather
    than by a person deciding it is time.

    HEAT-WEIGHTED, because the question is about the CAPITAL, not the roster: a book whose funded
    sleeves are all backtest-only is not made ready by twenty unfunded ones that have clocks.
    """
    if not heat_by_sleeve:
        return 0.0, "no funded sleeves: readiness is 0, not unmeasured"
    total = sum(max(v, 0.0) for v in heat_by_sleeve.values())
    if total <= 0:
        return 0.0, "book holds no heat"
    share = sum(max(h, 0.0) * (oos_by_sleeve.get(k, 0.0)
                               / (oos_by_sleeve.get(k, 0.0) + READY_SCALE))
                for k, h in heat_by_sleeve.items()) / total
    n_ev = sum(1 for k, h in heat_by_sleeve.items()
               if h > 1e-6 and oos_by_sleeve.get(k, 0.0) > 0)
    return float(min(max(share, 0.0), 1.0)), (
        f"{n_ev}/{sum(1 for h in heat_by_sleeve.values() if h > 1e-6)} funded sleeve(s) carry "
        f"out-of-sample evidence; heat-weighted readiness {share:.1%} of the {READY_SCALE:.0f}"
        f"-day scale")


#: Effective breadth the hard ceiling was written for. The desk's own reference: `heat_budget`
#: (decision_core `_HEAT_BASE_KEFF`) grants the base budget at k_eff = 2.26 and scales with
#: sqrt(k_eff) from there, so 30% is earned at N_eff = 2.26 * (30/20)^2 = 5.09 independent bets.
#: The same number, so the two laws cannot disagree about what "diversified" means -- what CHANGES
#: here is where the breadth comes from: max(covariance, factor, tail) rather than realised return
#: correlation alone, which is exactly the measurement that reads four hidden USD shorts as four
#: bets right up until the dollar moves.
EFFECTIVE_BREADTH_REF = 2.26

#: Worlds a state bucket needs before its own growth curve may set the target. At cvar_alpha 0.20
#: a 24-world bucket puts ~5 worlds in the CVaR tail; below that the "curve" for that state is one
#: or two draws wearing a distribution, and the global curve is the honest answer.
MIN_STATE_WORLDS = 24


@dataclass(frozen=True)
class StateCurve:
    """One admitted state's own growth curve: heat -> mean log growth on THAT state's worlds."""

    state: str
    curve: dict[float, float]
    n_worlds: int


@dataclass(frozen=True)
class HeatVerdict:
    """Resolved total heat and every reason it is what it is."""

    total_heat: float
    free_optimum: float
    target: float
    hard_ceiling: float
    #: Which layer decided the number: "growth" (the optimum sat inside the band),
    #: "mandate" (floored at target), "state_growth" (the current state's curve wanted more),
    #: "ceiling" (clipped at the hard bar), "effective_ceiling" (clipped where the book's
    #: independent risk ran out), "catastrophe".
    binding: str
    certified: bool
    #: How much of the target the book has EARNED, and the floor that follows from it.
    readiness: float = 0.0
    floor: float = 0.0
    reasons: tuple[str, ...] = ()
    curve: tuple[tuple[float, float], ...] = ()
    detail: dict[str, float] = field(default_factory=dict)
    #: The ceiling the book's EFFECTIVE independent risk earned, in [floor, hard_ceiling], and the
    #: four heats it was derived from (nominal / covariance / factor / tail / n_eff).
    effective_ceiling: float = 0.0
    effective: dict[str, float] = field(default_factory=dict)
    #: The state the target was conditioned on, its bucket's world count, and its argmax.
    state: str = ""
    state_worlds: int = 0
    state_optimum: float = 0.0


def effective_ceiling(effective_heat: Mapping[str, Any] | None, *,
                      target: float = HEAT_TARGET,
                      hard_ceiling: float = HEAT_HARD_CEILING,
                      ref_breadth: float = EFFECTIVE_BREADTH_REF,
                      ) -> tuple[float, str, dict[str, float]]:
    """The most NOMINAL heat this book's INDEPENDENT risk earns. Returns (cap, why, detail).

    THE NUMBER THE CEILING SHOULD HAVE BEEN COUNTING. `latent_factors.effective` has computed
    four heats -- nominal, covariance, factor, tail -- and an N_eff under each since it was
    written, and the allocator REPORTED them and capped on nominal anyway. So a book of four
    sleeves that is one hidden USD factor read as 28% of heat under a 30% bar and was waved
    through, when the risk it actually carried was one bet at 28%.

        H_eff  = max(covariance, factor, tail)          the single-bet-equivalent exposure
        N_eff  = (nominal / H_eff)^2                    independent bets the book really holds
        cap    = clip(target * sqrt(N_eff / ref), target, hard_ceiling)

    The middle line is the identity `latent_factors.n_eff` already computes; the last is the
    desk's own sqrt-breadth law (`heat_budget`), fed by the four heats instead of by realised
    return correlation alone. THE MAXIMUM is taken across the three, not an average: covariance
    says what the sleeves did on average, factor says what they are exposed to underneath, tail
    says what they do on the book's worst days, and the ceiling has to answer to the worst of the
    three because that is the day it exists for.

    IT CANNOT GO BELOW THE FLOOR. `clip(..., target, ...)` is what makes this a ceiling rather
    than a de-risking mechanism: a concentrated book is held AT the floor -- 20% deployed, 24/7 --
    and the answer to its concentration is research that finds independent risk, not a smaller
    book. Growth governance rule 1 is satisfied because nothing below the floor is ever taken.

    AN UNMEASURED BOOK KEEPS THE NOMINAL BAR, and says so rather than falling back silently. The
    alternative -- clamping to the floor whenever the measurement fails -- would let a broken
    input cost real growth on a book that may be perfectly diversified (L1.28a cuts both ways).
    """
    detail: dict[str, float] = {}
    if not isinstance(effective_heat, Mapping) or not effective_heat:
        return hard_ceiling, ("effective heat UNMEASURED (no measurement on this pass): the "
                              f"ceiling stands at the nominal {hard_ceiling:.0%} bar"), detail
    if effective_heat.get("error"):
        return hard_ceiling, (f"effective heat UNMEASURED ({effective_heat['error']}): the "
                              f"ceiling stands at the nominal {hard_ceiling:.0%} bar"), detail
    legs = {}
    for key in ("covariance", "factor", "tail"):
        try:
            v = float(effective_heat[key])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(v) and v > 0:
            legs[key] = v
    try:
        nominal = float(effective_heat.get("nominal", 0.0))
    except (TypeError, ValueError):
        nominal = 0.0
    if not legs or not math.isfinite(nominal) or nominal <= 0:
        return hard_ceiling, ("effective heat UNMEASURED (no positive nominal/covariance/factor/"
                              f"tail heat in the report): the ceiling stands at the nominal "
                              f"{hard_ceiling:.0%} bar"), detail
    worst = max(legs, key=lambda k: legs[k])
    h_eff = min(legs[worst], nominal)          # the four-heat identity: H_eff <= nominal, always
    n_eff = (nominal / h_eff) ** 2
    earned = target * math.sqrt(max(n_eff, 0.0) / max(ref_breadth, 1e-9))
    cap = float(min(hard_ceiling, max(target, earned)))
    detail = {"nominal": round(nominal, 6), "effective": round(h_eff, 6),
              "n_eff": round(n_eff, 3), "earned": round(earned, 6), "cap": round(cap, 6),
              **{k: round(v, 6) for k, v in legs.items()}}
    if cap >= hard_ceiling - 1e-12:
        why = (f"effective heat {h_eff:.2%} of {nominal:.2%} nominal ({worst} binds) is "
               f"N_eff={n_eff:.2f} independent bets; that earns {earned:.2%}, so the full "
               f"{hard_ceiling:.0%} ceiling stands")
    elif cap <= target + 1e-12:
        why = (f"EFFECTIVE-HEAT CEILING at the floor: {h_eff:.2%} effective on {nominal:.2%} "
               f"nominal ({worst} binds) is N_eff={n_eff:.2f} against a reference "
               f"{ref_breadth:.2f}; this book earns {earned:.2%}, so the ceiling is the "
               f"{target:.0%} floor and the room above it must be found in independent risk")
    else:
        why = (f"EFFECTIVE-HEAT CEILING {cap:.2%}: {h_eff:.2%} effective on {nominal:.2%} nominal "
               f"({worst} binds) is N_eff={n_eff:.2f} against a reference {ref_breadth:.2f}; the "
               f"nominal {hard_ceiling:.0%} bar is not what this book's independence earns")
    return cap, why, detail


def state_target(curves: Mapping[str, StateCurve] | None, state: str | None, *,
                 floor: float, ceiling: float,
                 fallback: Mapping[float, float] | None = None,
                 min_worlds: int = MIN_STATE_WORLDS) -> tuple[float, str, dict[str, float]]:
    """H*_t = argmax_{H in [floor, ceiling]} E[log W | X_t]. Returns (H*, why, detail).

    THE SURFACE IS LEARNED, NOT MAPPED. Nothing here says "widen in trends, tighten in chop": the
    growth curve is re-measured every heavy pass on the worlds the desk believes it is in, and the
    target is wherever that curve peaks inside the band. A state whose curve peaks at 27% gets
    27% because the measurement says so, and stops getting it the moment the measurement changes.

    THE BUCKET HAS TO BE BIG ENOUGH TO BE A CURVE. Below `min_worlds` the state's own population
    is too thin for a CVaR to mean anything, so the GLOBAL curve is used and the reason says which
    -- a thin bucket is a smaller sample, never a licence to bet on its noise.

    RETURNS THE FLOOR WHEN THERE IS NO CURVE AT ALL, which is the mandate's answer and not a
    reduction: the caller's own floor logic is unchanged by an unmeasured state.
    """
    band = (float(floor), float(ceiling))
    picked: StateCurve | None = None
    why_src = ""
    if curves and state and state in curves:
        c = curves[state]
        if c.n_worlds >= min_worlds and len(c.curve) >= 3:
            picked, why_src = c, f"state {state!r} ({c.n_worlds} worlds)"
        else:
            why_src = (f"state {state!r} has {c.n_worlds} world(s) and {len(c.curve)} curve "
                       f"point(s) (need {min_worlds} and 3): the global curve stands")
    elif state:
        why_src = f"no curve measured for state {state!r}: the global curve stands"
    else:
        why_src = "no current state id: the global curve stands"
    curve = dict(picked.curve) if picked is not None else dict(fallback or {})
    inside = {h: g for h, g in curve.items()
              if band[0] - 1e-9 <= h <= band[1] + 1e-9 and math.isfinite(g)}
    if not inside:
        return band[0], (f"no growth curve point inside [{band[0]:.0%}, {band[1]:.0%}] -- "
                         f"{why_src}; the floor stands"), {}
    h_star = max(inside, key=lambda h: inside[h])
    detail = {"h_star": round(h_star, 6), "growth": round(inside[h_star], 8),
              "n_worlds": float(picked.n_worlds if picked is not None else 0),
              "points": float(len(inside))}
    return float(h_star), (f"H*_t = {h_star:.2%} ({inside[h_star]:+.5f} log/day) is the argmax of "
                           f"E[log W | state] over [{band[0]:.0%}, {band[1]:.0%}] on "
                           f"{len(inside)} point(s) -- {why_src}"), detail


def per_sleeve_bounds(worst_dd_r: dict[str, float], total_heat: float,
                      tolerance: float = MAX_DRAWDOWN_TOLERANCE, *,
                      effective_heat: Mapping[str, Any] | None = None) -> dict[str, float]:
    """Per-sleeve heat bound: the tighter of the drawdown derivation and the concentration share.

    THE DRAWDOWN LEG is the desk's existing derivation applied per sleeve instead of to the whole
    book -- `risk_per_trade(tolerance, dd_r)` solves the risk that spends exactly `tolerance` over
    a `dd_r` drawdown, so a sleeve that has historically drawn 10R may carry more than one that
    has drawn 40R, for the same account pain. One risk input, used twice, rather than a second
    number to argue about.

    THE CONCENTRATION LEG exists because the drawdown leg alone points the wrong way under a
    utilisation mandate: a quiet sleeve with a shallow drawdown earns the LARGEST bound, and a
    quiet sleeve is exactly where a forced budget goes to hide. `MAX_SLEEVE_HEAT_SHARE` of the
    book stops any one name carrying the mandate regardless of how flat its history looks.

    `effective_heat` (the `latent_factors.effective` report) makes the concentration leg count the
    heat the book's INDEPENDENCE earns rather than the nominal total it was asked to bound: the
    share cap is taken against `min(total_heat, effective_ceiling(...))`. In the allocator's own
    path this is belt-and-braces -- `resolve` has already capped the resolved heat -- but a caller
    that passes a nominal target of its own no longer gets sleeve bounds sized for a breadth the
    book does not have. It can only ever TIGHTEN: `min`, never `max`.
    """
    total = max(float(total_heat), 0.0)
    if effective_heat is not None:
        cap, _why, _detail = effective_ceiling(effective_heat)
        total = min(total, cap)
    share_cap = MAX_SLEEVE_HEAT_SHARE * total
    out: dict[str, float] = {}
    for name, dd in worst_dd_r.items():
        dd_r = float(dd) if dd and float(dd) > 0 else _DEFAULT_DD_R
        out[name] = float(min(risk_per_trade(tolerance, dd_r), share_cap))
    return out


#: How much of the peak growth rate the utilisation mandate may spend before it stops being
#: certifiable. The Kelly curve is FLAT near its top -- that is the property the whole mandate
#: rests on -- so "the target is one grid point past the peak" is not by itself a finding.
#: Measured 2026-09-02 on the operating curve, 20% gives up 0.1% of the peak rate against a peak
#: at 15%; a target genuinely past the hill gives up percent, not tenths of one.
CERTIFY_TOLERANCE = 0.02


def enforce_family_cap(heat: dict[str, float], family_of: dict[str, str], total: float,
                       share: float = MAX_FAMILY_HEAT_SHARE) -> dict[str, float]:
    """Per-sleeve upper bounds that hold any one MECHANISM under `share` of the book.

    A CONSTRAINT, NOT A PRICE. The redundancy term in `robust_elog` charges pairwise correlation
    of daily returns, and seven `overnight_gap_decay` sleeves on different crosses genuinely are
    weakly correlated day to day -- so it did not see them, and the solved book put 97% of its
    heat into that one mechanism. They share a fill hour (01:00, the thinnest book of the
    session) and a mechanism, so they fail together on a liquidity event no daily correlation
    contains. A penalty is something growth can outbid; this cannot be.

    Bounds are proportional to each sleeve's own solved weight within its family, so the
    optimiser's ranking inside a mechanism is preserved and only the mechanism's TOTAL is capped.
    A family already inside the cap is returned unbounded, so this only ever binds where it must.
    """
    if total <= 0:
        return {}
    cap = share * total
    by_fam: dict[str, float] = {}
    for name, h in heat.items():
        fam = family_of.get(name, "?")
        by_fam[fam] = by_fam.get(fam, 0.0) + max(h, 0.0)
    out: dict[str, float] = {}
    for name, h in heat.items():
        held = by_fam.get(family_of.get(name, "?"), 0.0)
        out[name] = float("inf") if held <= cap or held <= 0 else max(h, 0.0) * (cap / held)
    return out


def certify(curve: dict[float, float], target: float = HEAT_TARGET,
            tolerance: float = CERTIFY_TOLERANCE) -> tuple[bool, str]:
    """Is `target` at, below, or negligibly past the peak of the growth curve?

    `curve` maps total heat -> mean log growth per day, as measured on the live world population.
    The mandate is safe while the curve is still rising at the target, and STAYS safe just past
    the peak while the flat top costs nothing measurable; it stops being safe when running the
    target costs a real fraction of the achievable growth rate.
    """
    if len(curve) < 3:
        return False, f"UNCERTIFIED: {len(curve)} points on the growth curve, need 3"
    pts = sorted(curve.items())
    peak_h, peak_g = max(pts, key=lambda kv: kv[1])
    at_h, at_g = min(pts, key=lambda kv: abs(kv[0] - target))
    if target <= peak_h + 1e-9:
        return True, (f"certified: growth peaks at H={peak_h:.1%} ({peak_g:+.5f}/day); "
                      f"target {target:.1%} is at or below the peak")
    if peak_g <= 0:
        return False, (f"NOT CERTIFIED: peak growth is {peak_g:+.5f}/day -- non-positive at every "
                       "heat measured. No exposure is the growth-maximising exposure.")
    lost_frac = (peak_g - at_g) / peak_g
    if lost_frac <= tolerance:
        return True, (f"certified: peak at H={peak_h:.1%}, target {target:.1%} sits on the flat "
                      f"top and gives up {lost_frac:.2%} of the peak rate "
                      f"(tolerance {tolerance:.0%})")
    return False, (f"NOT CERTIFIED: growth peaks at H={peak_h:.1%} ({peak_g:+.5f}/day) and the "
                   f"{target:.1%} target runs at {at_g:+.5f}/day -- giving up {lost_frac:.1%} of "
                   f"the achievable rate ({(peak_g - at_g) * 252.0:+.3f} log/yr). Measured at "
                   f"H={at_h:.1%}. Forcing the target is a decision, not the growth optimum.")


def catastrophe_override(*, broker_ok: bool = True, prices_fresh: bool = True,
                         exposure_reconciled: bool = True, margin_ok: bool = True,
                         allocator_ok: bool = True) -> tuple[float | None, tuple[str, ...]]:
    """The only layer permitted to push heat below target. Returns (heat_or_None, reasons).

    FAILS CLOSED AND FAILS HARD: any one of these false takes the book to zero new heat, because
    every one of them means the desk does not know what its exposure IS. That is a different
    condition from "the opportunity set looks thin", and conflating the two is how a risk system
    ends up quietly de-risking on a bad classifier reading.
    """
    bad: list[str] = []
    if not broker_ok:
        bad.append("broker/terminal unavailable")
    if not prices_fresh:
        bad.append("stale or missing quotes")
    if not exposure_reconciled:
        bad.append("open exposure does not reconcile with the ledger")
    if not margin_ok:
        bad.append("margin state anomalous")
    if not allocator_ok:
        bad.append("allocator produced no usable book")
    return (0.0, tuple(bad)) if bad else (None, ())


def resolve(free_optimum: float, *, curve: dict[float, float] | None = None,
            target: float = HEAT_TARGET, hard_ceiling: float = HEAT_HARD_CEILING,
            mandate: bool = True, readiness: float = 1.0,
            readiness_why: str = "",
            effective_heat: Mapping[str, Any] | None = None,
            state: str | None = None,
            curves: Mapping[str, StateCurve] | None = None,
            **integrity: bool) -> HeatVerdict:
    """Total heat the desk should run right now, and why.

    `mandate=True` is the standing policy: the floor IS the target, flat, deployed 24/7. An
    earlier version ramped it with `readiness` so the budget had to be earned out of sample; the
    principal's instruction of 2026-09-02 supersedes that, and the comment on `floor` below
    records why. `readiness` is still measured and still reported every pass -- it is the honest
    statement of how much of this book has traded rather than been fitted -- and it gates nothing.
    `mandate=False` is pure E[log W]: the book may hold back. Both obey the ceiling and both obey
    integrity.

    Growth is ALWAYS free to exceed the target up to the hard ceiling. A book whose robust optimum
    genuinely wants 24% gets 24% on day one.

    `effective_heat` is the four-heat report for the CANDIDATE book (`latent_factors.effective`),
    measured before the solve. The FLOOR still counts nominal heat -- 20% deployed is a standing
    instruction about capital at work -- while the CEILING counts max(covariance, factor, tail),
    because hidden concentration bites at the top of the band and nowhere else. Omit it and the
    ceiling is the nominal bar exactly as before.

    `state` and `curves` condition the target on the market: H*_t is the argmax of that state's
    own growth curve inside the band, and it may only RAISE the number (`state_target`).
    """
    reasons: list[str] = []
    override, bad = catastrophe_override(**integrity) if integrity else (None, ())
    if override is not None:
        return HeatVerdict(total_heat=override, free_optimum=free_optimum, target=target,
                           hard_ceiling=hard_ceiling, binding="catastrophe", certified=False,
                           effective_ceiling=hard_ceiling,
                           reasons=tuple(f"CATASTROPHE GUARD: {b}" for b in bad))

    ok, why = certify(curve or {}, target)
    reasons.append(why)

    r = float(min(max(readiness, 0.0), 1.0))

    # THE FLOOR IS THE TARGET, FLAT. "it should minimum cover 20% heat cap 24/7 deployed minimum
    # ... if it allows up to 30 we let it do 30" -- the principal, 2026-09-02, after being shown
    # that 20% on the current three-leg gold book implies ~90% drawdown on that book's own worst
    # 33.7R run against a stated 35% tolerance. That is their decision, recorded here rather than
    # re-litigated on every pass.
    #
    # An earlier version ramped this floor with `readiness` so the target had to be EARNED with
    # out-of-sample evidence. The instruction supersedes it. Readiness is still measured and
    # still reported every pass -- it is the honest statement of how much of this book has traded
    # rather than been fitted -- it simply no longer gates the budget.
    floor = target if mandate else 0.0
    if mandate:
        reasons.append(f"utilisation floor {floor:.2%} (flat target, principal 2026-09-02); "
                       f"readiness {r:.1%} is REPORTED, not gating"
                       + (f" -- {readiness_why}" if readiness_why else ""))

    # THE CEILING COUNTS EFFECTIVE HEAT, THE FLOOR COUNTS NOMINAL. See `effective_ceiling`: the
    # room ABOVE the floor is bought with independent risk, and the floor itself is never touched
    # by a correlation estimate.
    eff_cap, eff_why, eff_detail = effective_ceiling(
        effective_heat, target=target, hard_ceiling=hard_ceiling)
    reasons.append(eff_why)

    # H*_t: the current state's own growth curve, inside the band the two bars leave open.
    h_state, state_why, state_detail = state_target(
        curves, state, floor=floor, ceiling=min(hard_ceiling, eff_cap), fallback=curve)
    if curves or state:
        reasons.append(state_why)

    h = float(free_optimum)
    binding = "growth"
    if mandate and h < floor:
        h, binding = floor, "mandate"
        reasons.append(f"utilisation mandate: floored {free_optimum:.2%} -> {floor:.2%}"
                       + (f"; the full {target:.0%} applies at readiness 100%"
                          if r < 0.999 else ""))
    # THE STATE MAY ONLY RAISE. A state whose curve wants LESS than the unconditional optimum is
    # not permitted to cut here: a reduction is a rail, and this one has not proved its
    # dE[log W] (growth governance rule 1). Wanting MORE is rule 2 in one line.
    if (curves or state) and h_state > h + 1e-12:
        reasons.append(f"state opportunity: {h:.2%} -> {h_state:.2%} on E[log W | X_t]")
        h, binding = float(h_state), "state_growth"
    if h > hard_ceiling:
        reasons.append(f"HARD CEILING: growth wanted {h:.2%}, clipped to {hard_ceiling:.2%}")
        h, binding = hard_ceiling, "ceiling"
    if h > eff_cap + 1e-12:
        reasons.append(f"EFFECTIVE-HEAT CEILING BINDS: nominal {h:.2%} wanted, "
                       f"{eff_cap:.2%} earned by independent risk")
        h, binding = float(eff_cap), "effective_ceiling"
    elif h > target:
        reasons.append(f"growth exceeds target: running {h:.2%} (ceiling {hard_ceiling:.2%})")

    return HeatVerdict(total_heat=h, free_optimum=float(free_optimum), target=target,
                       hard_ceiling=hard_ceiling, binding=binding, certified=ok,
                       readiness=r, floor=floor,
                       reasons=tuple(reasons),
                       curve=tuple(sorted((curve or {}).items())),
                       detail={"mandate": float(mandate), **state_detail},
                       effective_ceiling=float(eff_cap), effective=eff_detail,
                       state=str(state or ""),
                       state_worlds=int(state_detail.get("n_worlds", 0.0)),
                       state_optimum=float(h_state))
