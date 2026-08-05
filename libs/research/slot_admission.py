"""SLOT ADMISSION BY EV-RANK -- the law's own rule, finally implemented.

WHAT THE LAW SAYS, verbatim (docs/research/TWO_STAGE_DISCOVERY_LAW.md):

    STAGE A -- SCREEN (unlimited, zero promotion authority).
    The backtest gauntlet is a RANKING DEVICE only. Its job is to order candidates by quality and
    decide who gets a confirmation slot -- nothing screened here is ever validated.

    SLOT ADMISSION (the only place selection pressure survives, and it's harmless).
    Slots are filled by EV-rank (economics, orthogonality, capacity, measured cost) from Stage-A
    survivors. Picking the best-looking backtest into a slot does NOT leak luck into Stage B.

WHAT WAS ACTUALLY IMPLEMENTED, until this module. `paper_sleeves.QUALIFYING_PREFIX` admitted a
candidate only when its corrected Stage-A verdict began with "SCREEN-INTERESTING". That is a
SIGNIFICANCE GATE at Stage A, and it is the exact thing the law forbids: it hands the ranking
device promotion authority. Its cost was total and measurable -- of 120 scored cells on disk, ZERO
carried that verdict, so zero were ever admitted, so of twelve Stage-B slots ten sat idle with not
one forward clock ever started. The desk then read the silence as "no edges exist". It was reading
its own closed door.

The arithmetic makes the point sharper. With ~1,096 Stage-A trials the data-snooping critical value
is sqrt(2*ln(1096)) = 3.74 sigma, which on three years of daily bars demands an in-sample Sharpe
near 2.2. Requiring that BEFORE granting a costless forward clock means the desk only ever
forward-tests hypotheses so strong they needed no confirmation. Every real, weak, exploitable edge
-- the only kind that survives in a liquid market -- is filtered out before it can be tested. That
is not conservatism, it is a guarantee of zero discoveries (L1.49: weak is not dead).

WHAT REPLACES IT: TIME-TO-RESOLUTION.
A forward slot's scarce resource is CALENDAR TIME, not significance. So rank by how fast a clock
settles the question:

    n_needed     = (z_holm / |ic|)^2          rows for the FORWARD test to reject at its own bar
    resolve_days = n_needed * bar_length_days  calendar days that clock occupies its slot

That single number reorders everything. Measured on the desk's own store, 2026-08-05:

    45 days   liq_reversion_BTCUSDT_5m   |ic| 0.0172, 5-minute bars, decontaminated, no leak
    63 days   AVAX:t90 vol-risk-premium  |ic| 0.2477, daily bars
   >3 years   64 of 114 cells

Thirteen cells settle inside ninety days. The desk had been calling them "no survivors" while
holding candidates that a six-week forward clock would resolve. A weak IC on a fast bar is worth
far more slot-time than a strong IC on a slow one, and significance-ranking inverts that exactly.

NOTHING HERE LOOSENS ANY BAR. Stage B's Holm threshold, alpha=0.05 and MAX_FORWARD_SLOTS=12 are
untouched -- this module READS the Holm bar to compute resolution time and never sets it. Adding
clocks RAISES m, which TIGHTENS every standing candidate's bar; filling idle slots is therefore the
CONSERVATIVE direction on the promotion side, not the permissive one. What changes is only which
candidates get to attempt Stage B, which is the one place the law says selection pressure is
harmless.

ORTHOGONALITY IS ENFORCED, not hoped for. Twelve slots all spent on one mechanism buys one bet
measured twelve times. The per-mechanism cap is DERIVED from the cohort (ceil(slots / distinct
mechanisms), floor 1), never a magic constant, so it widens automatically as the mechanism census
grows and never needs hand-editing to stay correct.

Pure stdlib + libs.validation.forward_stats.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Any

from libs.validation.forward_stats import holm_bar

__all__ = [
    "AdmissionRow",
    "forward_resolution_days",
    "rank",
    "resolution_bucket",
]

#: Cells whose forward clock would outlive the desk are ranked, reported, and NOT admitted -- the
#: slot would be occupied for a decade returning nothing. This is a COST fence, not a strength bar:
#: the cell keeps its verdict and stays a candidate the moment more data shortens its resolution.
#: Ten years, so that anything a patient desk could actually finish stays in.
MAX_RESOLVE_DAYS = 3650.0

#: Buckets used for reporting only. Never a filter.
_BUCKETS: tuple[tuple[float, str], ...] = (
    (90.0, "<=90d"), (365.0, "<=1y"), (1095.0, "<=3y"), (MAX_RESOLVE_DAYS, "<=10y"),
)


@dataclass(frozen=True)
class AdmissionRow:
    """One candidate scored for slot admission. `why` always states the reason in full."""

    name: str
    axis: str
    mechanism: str
    ic: float
    horizon_days: float
    n_eff: float
    resolve_days: float
    n_needed: float
    bar_z: float
    clean: bool
    admissible: bool
    why: str
    #: Capacity runway in multiples of the book, inf when UNMEASURED. The L1.18a tie-break.
    runway: float = math.inf

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "axis": self.axis, "mechanism": self.mechanism,
            "ic": round(self.ic, 6), "horizon_days": self.horizon_days,
            "n_eff": self.n_eff, "resolve_days": round(self.resolve_days, 1),
            "n_needed": round(self.n_needed, 1), "bar_z": self.bar_z,
            "bucket": resolution_bucket(self.resolve_days),
            "clean": self.clean, "admissible": self.admissible, "why": self.why,
            "runway": None if not math.isfinite(self.runway) else round(self.runway, 4),
        }


def resolution_bucket(days: float) -> str:
    if not math.isfinite(days):
        return "unresolvable"
    for edge, label in _BUCKETS:
        if days <= edge:
            return label
    return ">10y"


def forward_resolution_days(
        ic: float, horizon_days: float, *, m: int = 12, rank_position: int = 1,
        alpha: float = 0.05) -> tuple[float, float, float]:
    """(calendar days to settle, rows needed, the z bar used).

    The bar is the FORWARD cohort's own Holm threshold -- the same number the clock will actually
    have to clear -- so this is the honest cost of the test rather than a friendlier proxy. A
    zero or non-finite IC is UNRESOLVABLE (inf), never a small number: an effect the screen
    measured at zero cannot be settled by waiting, and rounding that to a finite wait would let a
    measured nothing outrank a measured something.
    """
    z = float(holm_bar(max(1, int(m)), max(1, int(rank_position)), alpha=alpha))
    a = abs(float(ic))
    if not math.isfinite(a) or a <= 0.0 or not math.isfinite(horizon_days) or horizon_days <= 0.0:
        return math.inf, math.inf, z
    n_needed = (z / a) ** 2
    return n_needed * float(horizon_days), n_needed, z


def _mechanism_cap(n_slots: int, n_mechanisms: int) -> int:
    """Per-mechanism admission cap, DERIVED. Widens on its own as the census grows."""
    if n_slots <= 0 or n_mechanisms <= 0:
        return 0
    return max(1, math.ceil(n_slots / n_mechanisms))


def rank(candidates: list[dict[str, Any]], *, n_slots: int, m_cohort: int = 12,
         alpha: float = 0.05) -> dict[str, Any]:
    """EV-rank every candidate and pick who gets the free slots.

    `candidates` are canonical trial dicts (ic, horizon_days, n_eff, mechanism_class, name, axis,
    is_candidate). Returns admitted rows, the full ranked table, and the reason for every
    exclusion -- a candidate that is not admitted is never silently absent.
    """
    rows: list[AdmissionRow] = []
    for c in candidates:
        ic = c.get("residual_ic")
        ic = c.get("ic") if not isinstance(ic, (int, float)) else ic
        horizon = c.get("horizon_days")
        n_eff = c.get("n_eff") or c.get("n") or 0.0
        mech = str(c.get("mechanism_class") or c.get("axis") or "unclassified")
        name = str(c.get("name", "?"))
        axis = str(c.get("axis", ""))
        clean = bool(c.get("decontam_passed", True)) and not bool(c.get("implausible_leak"))
        rw = c.get("runway")
        runway = float(rw) if isinstance(rw, (int, float)) and math.isfinite(float(rw)) \
            else math.inf
        if not isinstance(ic, (int, float)) or not isinstance(horizon, (int, float)):
            # LAST IN LINE, NOT EXCLUDED. An unmeasured forward cost is not a measured-and-too-high
            # one: `resolve_days = inf` puts this behind every candidate whose wait is known, so it
            # can never jump a queue, but if slots remain free after all of those are placed then
            # leaving one IDLE to spite a missing field is giving up on a hypothesis nobody has
            # judged (L1.54, and the same direction as runway-inf in the deployment race).
            rows.append(AdmissionRow(name, axis, mech, 0.0, 0.0, float(n_eff or 0), math.inf,
                                     math.inf, 0.0, clean, True,
                                     "UNRANKED -- the cell carries no IC/horizon pair, so its "
                                     "forward cost cannot be computed. Not a judgement on the "
                                     "hypothesis: the measurement is missing, not the effect. "
                                     "Sorted behind every candidate with a known wait, and "
                                     "admitted only into a slot that would otherwise sit idle.",
                                     runway))
            continue
        days, needed, z = forward_resolution_days(float(ic), float(horizon), m=m_cohort,
                                                  alpha=alpha)
        if days > MAX_RESOLVE_DAYS:
            why = (f"UNAFFORDABLE -- a forward clock at |ic|={abs(float(ic)):.4f} on "
                   f"{float(horizon):g}-day bars needs {needed:,.0f} rows "
                   f"({days:,.0f} days) to clear its own Holm bar z={z}. The slot would return "
                   f"nothing for {days / 365.25:,.1f} years. A COST fence, not a strength bar: "
                   "the cell keeps its verdict and re-enters the moment faster bars or a wider "
                   "panel shorten the wait.")
            rows.append(AdmissionRow(name, axis, mech, float(ic), float(horizon),
                                     float(n_eff or 0), days, needed, z, clean, False, why,
                                     runway))
            continue
        rows.append(AdmissionRow(
            name, axis, mech, float(ic), float(horizon), float(n_eff or 0), days, needed, z, clean,
            True, f"settles in {days:,.0f} days ({needed:,.0f} rows at |ic|={abs(float(ic)):.4f} "
                  f"vs Holm z={z})", runway))

    # DETERMINISTIC ORDER: fastest to settle, then cleanest, then SHORTEST CAPACITY RUNWAY, then
    # strongest, then name.
    #
    # Cleanliness sorts ahead of strength on purpose -- a contaminated cell that settles quickly is
    # settling the wrong question, and spending a slot on it buys a confident answer about an
    # artifact.
    #
    # RUNWAY IS THE TIE-BREAK AND IT IS LOAD-BEARING (L1.18a, the deployment race). Two candidates
    # that settle equally fast are not equally urgent: a long-runway edge loses nothing by waiting
    # a month, a short-runway one loses everything, so arrival order systematically sacrifices
    # exactly the edges that cannot afford to wait. Unknown capacity sorts LAST (inf) -- never
    # ahead of an edge measurably about to expire. This mattered immediately: with three
    # unranked-cost candidates the order collapsed to ALPHABETICAL and handed the only free slot
    # to the long-runway edge.
    ordered = sorted(rows, key=lambda r: (r.resolve_days, not r.clean, r.runway, -abs(r.ic),
                                          r.name))
    eligible = [r for r in ordered if r.admissible]

    n_mech = len({r.mechanism for r in eligible}) or 1
    cap = _mechanism_cap(n_slots, n_mech)
    used: Counter[str] = Counter()
    admitted: list[AdmissionRow] = []
    deferred: list[dict[str, Any]] = []
    for r in eligible:
        if len(admitted) >= max(0, int(n_slots)):
            deferred.append({**r.as_dict(),
                             "deferred_because": "no free slot this pass -- queued in rank order"})
            continue
        if used[r.mechanism] >= cap:
            deferred.append({**r.as_dict(),
                             "deferred_because": (
                                 f"orthogonality cap: {cap} slot(s) per mechanism this pass "
                                 f"({n_slots} free / {n_mech} distinct mechanisms). Twelve clocks "
                                 "on one mechanism is one bet measured twelve times.")})
            continue
        used[r.mechanism] += 1
        admitted.append(r)

    return {
        "admitted": [r.as_dict() for r in admitted],
        "deferred": deferred,
        "excluded": [r.as_dict() for r in ordered if not r.admissible],
        "n_ranked": len(rows),
        "n_slots": int(n_slots),
        "mechanism_cap": cap,
        "m_cohort": int(m_cohort),
        "buckets": dict(Counter(resolution_bucket(r.resolve_days) for r in rows)),
        "law": ("TWO_STAGE_DISCOVERY_LAW: slots are filled by EV-rank, never by a Stage-A "
                "significance verdict. Ranking is by TIME-TO-RESOLUTION -- a forward slot's "
                "scarce resource is calendar time. No bar is moved: the Holm z used here is READ "
                "from the cohort, and admitting clocks RAISES m, which tightens every standing "
                "candidate's bar."),
    }
