"""LENDING HAIRCUT, DERIVED (R0375) -- the one number that decides whether idle dollars may earn.

WHAT THIS REPLACES. `screen_collateral_allocation.DEFAULT_HAIRCUT_BPS = 300.0`, a constant with no
derivation anywhere in the repo, subtracted from the lending rung of `idle_yield.reachable_floor`.
Measured 2026-08-05: best stablecoin supply APY 3.78% against risk-free 3.73%/yr, so the BREAKEVEN
haircut is 5.5bps -- the assumed constant closed the band 55x over, and gross the lending rung
WINS by 5bps. Every verdict downstream ("carry-dominant", "the floor is simply the risk-free
rate") was therefore an assumption wearing a measurement's clothes (L1.47), and L1.51 requires a
clamp to carry a price and a lifting condition, not a number somebody typed.

THE DERIVATION, and every term is measured rather than asserted:

    haircut = exploit_loss_rate(upper bound)  +  depeg_shortfall(measured)

  EXPLOIT LOSS RATE. Net-of-returned-funds losses attributable to the reference set of lending
  protocols, divided by their trapezoid-integrated TVL-YEARS. Both halves come from DefiLlama's
  free keyless API via `scripts/collect_lending_risk_base_rates.py`. Measured 2026-08-12:
  $147.00M net loss over $120.19B TVL-years = 12.2 bps/yr.

  WHY THE PUBLISHED NUMBER IS AN UPPER BOUND AND NOT THAT POINT. Two events carry the entire
  estimate. A point estimate from two events, used to OPEN a yield band, is the L1.45 defect the
  desk already paid for: publishing a cost_ratio from too few fills would step the book up on
  fiction, which is strictly worse than leaving it pinned. So the frequency is taken at its
  one-sided 95% Poisson upper bound (solved by bisection on the Poisson CDF -- no scipy, and the
  test pins it against the closed-form rule-of-three at k=0). At k=2 that is 6.30 expected events
  against 2 observed, a 3.15x widening: 12.2 -> 38.5 bps/yr.

  WHAT THAT BOUND STILL DOES NOT COVER, stated because an unstated omission reads as zero: it
  prices FREQUENCY uncertainty only. Mean severity is held at its observed value, so a tail worse
  than anything in the sample is not in the number. The published haircut is a LOWER BOUND ON
  TOTAL RISK, and the two components below say so again.

  DEPEG. Mean shortfall below $1 at a randomly-timed exit, over the full daily price history
  (USDC 2020-12-30 -> 2026-08-12, n=2046, including the 0.9611 trough on 2023-03-12). Measured
  3.2bps for USDC. This belongs in the haircut for THIS comparison specifically -- the rung being
  compared against is a T-bill, which has no peg to break. An asset with no measured history takes
  the WORST measured peer, never zero.

WHAT IS MEASURED AND DELIBERATELY NOT PRICED. On the desk's own `defi_lending.jsonl` tape the
aave-v3 USDC pool that carries the quoted rate sat at utilisation >= 0.99 in 23.8% of 311
observations, touching 1.0001 -- at full utilisation a supplier CANNOT WITHDRAW AT ALL. That is
the "correlated with exactly the moments you need the collateral back" clause of the original
docstring, and it is now a measured frequency. It is NOT converted into bps: what a day of
unavailable collateral costs this desk is measured nowhere, and inventing a severity to complete
a formula would rebuild the exact defect this module exists to remove (L1.28a -- UNMEASURED is a
real answer). It is published in `unpriced` so a reader sees the gap instead of inferring zero.

THE FAILURE DIRECTION IS CHOSEN, NOT INCIDENTAL. When the base-rate artifact is absent, stale or
incomplete this module returns LAST_RESORT_HAIRCUT_BPS with `measured=False`. That is the LARGE
number, so a broken input keeps the band SHUT rather than opening it on a fabricated small
haircut. An absent input must never resolve to a permissive verdict (L1.55).

WHAT THIS MODULE DOES NOT DO. It moves no funds, lifts no clamp and promotes nothing (L1.6). It
replaces one undefended constant with a defended estimate, its uncertainty, and the named list of
what is still unmeasured. On the 2026-08-12 artifact the derived haircut is 41.7bps against a 5.5bps
breakeven, so the verdict is UNCHANGED -- lending still loses to T-bills. The margin was 295bps of
assumption; it is 36bps of measurement.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from libs.ops.fresh import read_fresh

#: Used ONLY when the derivation cannot be made. Deliberately the old undefended constant: it is
#: large, so a broken input fails toward a shut band. It is not a fallback estimate and must never
#: be reported as measured.
LAST_RESORT_HAIRCUT_BPS: float = 300.0

#: The base-rate artifact ages in multi-year aggregates (TVL-years, a 6-year hack record, 2046
#: days of prices), so a two-week-old copy is still evidence about the same quantities. This is a
#: STALENESS bound on the collector, not on the risk.
BASE_RATES_MAX_AGE_H: float = 336.0
BASE_RATES_PATH = "data/lending_risk_base_rates.json"

#: One-sided confidence level for the exploit-frequency bound.
CONFIDENCE: float = 0.95


def poisson_upper(k: int, confidence: float = CONFIDENCE) -> float:
    """One-sided upper bound on a Poisson mean given `k` observed events.

    Solves `P(X <= k; mu) = 1 - confidence` by bisection. At k=0 this is the closed-form rule of
    three, `-ln(1 - confidence)` = 3.00 at 95%, which the test pins. No scipy: the desk's pinned
    dependency set does not carry it and a distribution quantile is not worth a dependency.
    """
    if k < 0:
        raise ValueError("k must be >= 0: a negative event count is not an observation")
    alpha = 1.0 - confidence
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"confidence must be strictly inside (0, 1): got {confidence}")

    def cdf(mu: float) -> float:
        term, total = math.exp(-mu), math.exp(-mu)
        for i in range(1, k + 1):
            term *= mu / i
            total += term
        return total

    lo, hi = 0.0, max(1.0, float(k) + 1.0)
    while cdf(hi) > alpha:
        hi *= 2.0
        if hi > 1e9:                                       # unreachable for any real k
            return hi
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if cdf(mid) > alpha:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


@dataclass
class Haircut:
    """The derived haircut, with its components and its named gaps both visible."""
    bps: float
    measured: bool
    point_bps: float | None
    components: dict[str, Any] = field(default_factory=dict)
    unpriced: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _refusal(why: str, provenance: dict[str, Any] | None = None) -> Haircut:
    return Haircut(
        LAST_RESORT_HAIRCUT_BPS, False, None, {}, [],
        [f"UNMEASURED: {why}",
         f"falling back to the undefended LAST_RESORT_HAIRCUT_BPS={LAST_RESORT_HAIRCUT_BPS:.0f} -- "
         "the LARGE number, so a broken input keeps the lending band shut rather than opening it "
         "on a fabricated small haircut (L1.55)"],
        provenance or {})


def _exploit_component(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    losses, exposure = payload.get("losses") or {}, payload.get("exposure") or {}
    if losses.get("status") != "READ":
        return None, f"loss record unusable: {losses.get('status')} {losses.get('error', '')}"
    if not exposure.get("complete"):
        return None, (f"exposure incomplete: {exposure.get('n_protocols_read')} of "
                      f"{exposure.get('n_protocols_declared')} reference protocols read -- a "
                      "partial denominator OVERSTATES the loss rate and is still not a measurement")
    tvl_years = float(exposure.get("total_tvl_years_usd") or 0.0)
    if tvl_years <= 0.0:
        return None, "exposure integrates to zero TVL-years -- no denominator, no rate (L1.57)"
    events = losses.get("blue_chip_events") or []
    net = float(losses.get("blue_chip_net_usd") or 0.0)
    k = len(events)
    if k == 0:
        # Zero events is NOT zero risk, and with no observed severity there is nothing to scale.
        return None, ("zero attributable loss events in the reference set -- the frequency bound "
                      "exists (rule of three) but no severity was observed, so the component is "
                      "unmeasurable rather than zero")
    point = net / tvl_years * 10_000.0
    widen = poisson_upper(k) / float(k)
    return {
        "point_bps": round(point, 3),
        "upper_bps": round(point * widen, 3),
        "n_events": k,
        "net_loss_usd": net,
        "exposure_tvl_years_usd": tvl_years,
        "frequency_widening": round(widen, 4),
        "confidence": CONFIDENCE,
        "basis": (f"{k} net-of-returned-funds loss events totalling ${net / 1e6:,.2f}M over "
                  f"${tvl_years / 1e9:,.2f}B TVL-years across "
                  f"{exposure.get('n_protocols_read')} reference protocols"),
    }, ""


def _depeg_component(payload: dict[str, Any], asset: str) -> tuple[dict[str, Any] | None, str]:
    peg = payload.get("peg") or {}
    if peg.get("status") != "READ":
        return None, f"peg record unusable: {peg.get('status')}"
    per = {k: v for k, v in (peg.get("per_asset") or {}).items() if v.get("status") == "READ"}
    if not per:
        return None, "no stablecoin priced -- the depeg component has no measurement"
    want = asset.upper()
    if want in per:
        row, why = per[want], f"{want} own price history"
    else:
        # An asset with no measured history takes the WORST measured peer. Never zero: an
        # unpriced peg is unknown, and unknown is not safe (L1.28a).
        want = max(per, key=lambda k: float(per[k]["mean_shortfall_bps"]))
        row = per[want]
        why = (f"{asset.upper()} has no measured price history -- taking the WORST measured peer "
               f"({want}) rather than zero")
    return {
        "bps": float(row["mean_shortfall_bps"]), "asset_used": want, "basis": why,
        "n_days": row.get("n_days"), "window": f"{row.get('first')} -> {row.get('last')}",
        "worst": f"{row.get('worst_price')} on {row.get('worst_date')}",
        "pct_days_below_0995": row.get("pct_days_below_0995"),
    }, ""


def _unpriced(payload: dict[str, Any]) -> list[str]:
    """Measured risks deliberately absent from the bps sum, named so nobody infers zero."""
    out = ["severity tail: the frequency bound holds mean severity at its observed value, so a "
           "loss larger than anything in the sample is not priced"]
    queue = payload.get("withdrawal_queue") or {}
    if queue.get("status") != "READ":
        out.append(f"withdrawal queue: {queue.get('status', 'absent')} -- utilisation unmeasured")
        return out
    worst, worst_key = None, ""
    for key, slot in (queue.get("per_pool") or {}).items():
        pct = float(slot.get("pct_ge_99") or 0.0)
        if worst is None or pct > worst:
            worst, worst_key = pct, key
    if worst is not None and worst > 0.0:
        out.append(f"withdrawal queue: {worst_key} sat at utilisation >= 0.99 in {worst:.1f}% of "
                   f"observations -- at full utilisation a supplier CANNOT withdraw. Measured on "
                   f"the desk's own tape, NOT converted to bps because the severity (what a day "
                   f"of unavailable collateral costs this desk) is measured nowhere")
    else:
        out.append("withdrawal queue: no pool observed at utilisation >= 0.99 in the collected "
                   "window -- a short window, so this is weak evidence, not absence of risk")
    return out


def derive_haircut(root: Path | None = None, *, asset: str = "USDC") -> Haircut:
    """The haircut for supplying `asset` into a blue-chip lending pool, in bps/yr.

    Returns the LAST-RESORT constant with `measured=False` -- never a plausible small number --
    whenever the base rates cannot be read (L1.55: an absent input may not resolve to a
    permissive verdict).
    """
    fr = read_fresh(BASE_RATES_PATH, max_age_h=BASE_RATES_MAX_AGE_H,
                    caller="lending_haircut.derive_haircut", min_rows=1, root=root)
    payload = fr.data if isinstance(fr.data, dict) else None
    prov = {"artifact": BASE_RATES_PATH, "fresh": fr.fresh, "why": fr.why,
            "max_age_h": BASE_RATES_MAX_AGE_H}
    if payload is None:
        return _refusal(f"{BASE_RATES_PATH} unreadable -- {fr.why}", prov)
    if not fr.fresh:
        return _refusal(f"{BASE_RATES_PATH} is not fresh -- {fr.why}", prov)
    prov["generated"] = payload.get("generated")

    exploit, why_e = _exploit_component(payload)
    if exploit is None:
        return _refusal(why_e, prov)
    depeg, why_d = _depeg_component(payload, asset)
    if depeg is None:
        return _refusal(why_d, prov)

    published = exploit["upper_bps"] + depeg["bps"]
    point = exploit["point_bps"] + depeg["bps"]
    notes = [
        f"exploit {exploit['point_bps']:.2f}bps point -> {exploit['upper_bps']:.2f}bps at the "
        f"{CONFIDENCE:.0%} Poisson frequency bound on {exploit['n_events']} events "
        f"({exploit['frequency_widening']:.2f}x)",
        f"depeg {depeg['bps']:.2f}bps ({depeg['basis']})",
        f"published {published:.2f}bps is an UPPER BOUND on the priced components and a LOWER "
        f"BOUND on total risk -- see `unpriced`",
        f"the undefended constant it replaces was {LAST_RESORT_HAIRCUT_BPS:.0f}bps "
        f"({LAST_RESORT_HAIRCUT_BPS / published:.1f}x this estimate)",
    ]
    return Haircut(round(published, 2), True, round(point, 2),
                   {"exploit": exploit, "depeg": depeg}, _unpriced(payload), notes, prov)


def haircut_bps(root: Path | None = None, *, asset: str = "USDC") -> float:
    """Just the number, for callers that cannot carry the whole reading."""
    return derive_haircut(root, asset=asset).bps
