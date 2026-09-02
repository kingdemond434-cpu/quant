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
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
for _p in (str(BASE), str(BASE.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk.gateway_config_fallback import (  # noqa: E402
    HEAT_HARD_CEILING,
    HEAT_TARGET,
    MAX_DRAWDOWN_TOLERANCE,
    MAX_SLEEVE_HEAT_SHARE,
    risk_per_trade,
)

__all__ = [
    "CERTIFY_TOLERANCE",
    "HEAT_HARD_CEILING",
    "HEAT_TARGET",
    "READY_SCALE",
    "HeatVerdict",
    "catastrophe_override",
    "certify",
    "evidence_readiness",
    "per_sleeve_bounds",
    "resolve",
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


@dataclass(frozen=True)
class HeatVerdict:
    """Resolved total heat and every reason it is what it is."""

    total_heat: float
    free_optimum: float
    target: float
    hard_ceiling: float
    #: Which layer decided the number: "growth" (the optimum sat inside the band),
    #: "mandate" (floored at target), "ceiling" (clipped at the hard bar), "catastrophe".
    binding: str
    certified: bool
    #: How much of the target the book has EARNED, and the floor that follows from it.
    readiness: float = 0.0
    floor: float = 0.0
    reasons: tuple[str, ...] = ()
    curve: tuple[tuple[float, float], ...] = ()
    detail: dict[str, float] = field(default_factory=dict)


def per_sleeve_bounds(worst_dd_r: dict[str, float], total_heat: float,
                      tolerance: float = MAX_DRAWDOWN_TOLERANCE) -> dict[str, float]:
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
    """
    share_cap = MAX_SLEEVE_HEAT_SHARE * max(total_heat, 0.0)
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
            readiness_why: str = "", **integrity: bool) -> HeatVerdict:
    """Total heat the desk should run right now, and why.

    `mandate=True` is the standing policy: utilisation of the target, RAMPED BY `readiness` --
    the floor is `target * readiness`, so the desk arrives at 20% by accumulating out-of-sample
    evidence rather than by asserting it. `readiness=1.0` is the un-ramped mandate and remains
    the default so no existing caller changes behaviour silently. `mandate=False` is pure
    E[log W]: the book may hold back. All three obey the ceiling and all three obey integrity.

    Growth is ALWAYS free to exceed the target up to the hard ceiling, whatever readiness says --
    readiness gates the FLOOR, never the upside. A book whose robust optimum genuinely wants 24%
    gets 24% on day one; readiness only decides how much the desk is willing to bet on a prior
    when the optimiser wants less.
    """
    reasons: list[str] = []
    override, bad = catastrophe_override(**integrity) if integrity else (None, ())
    if override is not None:
        return HeatVerdict(total_heat=override, free_optimum=free_optimum, target=target,
                           hard_ceiling=hard_ceiling, binding="catastrophe", certified=False,
                           reasons=tuple(f"CATASTROPHE GUARD: {b}" for b in bad))

    ok, why = certify(curve or {}, target)
    reasons.append(why)

    r = float(min(max(readiness, 0.0), 1.0))
    floor = target * r if mandate else 0.0
    if mandate:
        reasons.append(f"utilisation floor {floor:.2%} = {target:.0%} target x {r:.1%} readiness"
                       + (f" ({readiness_why})" if readiness_why else ""))

    h = float(free_optimum)
    binding = "growth"
    if mandate and h < floor:
        h, binding = floor, "mandate"
        reasons.append(f"utilisation mandate: floored {free_optimum:.2%} -> {floor:.2%}"
                       + (f"; the full {target:.0%} applies at readiness 100%"
                          if r < 0.999 else ""))
    if h > hard_ceiling:
        reasons.append(f"HARD CEILING: growth wanted {h:.2%}, clipped to {hard_ceiling:.2%}")
        h, binding = hard_ceiling, "ceiling"
    elif h > target:
        reasons.append(f"growth exceeds target: running {h:.2%} (ceiling {hard_ceiling:.2%})")

    return HeatVerdict(total_heat=h, free_optimum=float(free_optimum), target=target,
                       hard_ceiling=hard_ceiling, binding=binding, certified=ok,
                       readiness=r, floor=floor,
                       reasons=tuple(reasons),
                       curve=tuple(sorted((curve or {}).items())),
                       detail={"mandate": float(mandate)})
