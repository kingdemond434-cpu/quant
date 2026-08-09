"""INFORMATION ASYMMETRY -- not "have we looked at this source", but "does anyone else have it".

THE GAP THIS FILLS, STATED AGAINST THE ORGAN THAT ALREADY EXISTS. `scripts/info_class_map.py`
maps MODALITY x ACCESS across 33 classes and answers "has the desk visited this carrier". It is a
breadth map and a good one. It has no axis for asymmetry, so it files two sources identically that
could not be more different in edge terms:

    exchange_api_ohlcv   "covered"   -- and every participant on earth has the identical bytes
    orderbook_l2         "covered"   -- self-recorded, and NOBODY else has this exact tape

Both read as green. One is infrastructure and one is the only genuinely proprietary asset the desk
owns. A coverage map that cannot tell them apart will keep directing effort at sources whose
information is already in the price, which is the most expensive way to look busy.

THE TAXONOMY IS ABOUT WHY A COMPETITOR CANNOT HAVE IT, because that is the only thing that
survives contact with a market:

  EXCLUSIVE       nobody else holds it and it CANNOT be reconstructed after the fact. Self-recorded
                  L2 tape, own fills, own research corpus. The strongest and the rarest, and the
                  only kind that does not decay by being used.
  RECONSTRUCTIBLE public raw material that requires real work to assemble. Wallet clustering,
                  entity graphs, mempool history. Everyone COULD have it; almost nobody does. The
                  asymmetry is in the PROCESSING, not the access -- which means it is bought with
                  engineering rather than with money, and is the class a small desk should hunt.
  PERISHABLE      public to all, valuable only inside a window. Mempool state, funding at
                  settlement. The asymmetry is LATENCY, and it is a race the desk will usually
                  lose to colocated firms -- worth holding only where the window is minutes.
  INTERPRETIVE    everyone has the raw data; the claim is a better model of it. The weakest form,
                  and the most self-flattering to assert. Almost every losing retail strategy
                  believes it is here.
  COMMODITY       everyone has it and processes it identically. OHLCV, headline funding. Necessary
                  infrastructure, never edge. Naming it as such is what stops it being counted.

ASYMMETRY DECAYS AND THE LEDGER MUST SAY SO. A source that is RECONSTRUCTIBLE today is COMMODITY
once a vendor productises it; the desk's own graveyard has vendor-replacement entries that are
exactly this transition. Every claim therefore carries a `verified` date and expires, and an
expired claim is reported as UNVERIFIED rather than silently believed -- the desk's own recurring
failure is reading "not measured" as "measured and fine", and a stale asymmetry claim is that
failure applied to the one thing that supposedly justifies the whole enterprise.

AND A CLAIM MUST BE EVIDENCED. `why_not_replicable` is REQUIRED for EXCLUSIVE and RECONSTRUCTIBLE.
A desk telling itself its data is special, with no stated reason a competitor cannot obtain it, is
the failure mode this module exists to prevent -- so the constructor refuses it rather than
recording a wish.

BREADTH AND DEPTH ARE DIFFERENT AXES AND BOTH ARE TRACKED. Breadth is how many asymmetric sources
exist; depth is how far each has actually been mined. A desk with twenty sources at depth 1 knows
less than one with three at depth 5, and only tracking breadth makes the first look better.

Pure stdlib + dataclasses. No I/O.
"""

from __future__ import annotations

import contextlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from libs.core.coerce import finite_float

__all__ = [
    "ASYMMETRY_AXES",
    "ASYMMETRY_CLASSES",
    "DEPTH_LEVELS",
    "REPLICATION_FACTORS",
    "SELF_FOOTPRINT_FIELDS",
    "AsymmetrySource",
    "Portfolio",
    "asymmetry_weight",
    "information_advantage_frontier",
    "replication_cost_profile",
    "requires_evidence",
    "self_footprint_coverage",
]

#: class -> (edge weight, how long a claim stays fresh in days). Weights are ORDINAL, not a
#: forecast: they rank where effort should go, and multiplying them by an expected return would be
#: inventing a number. Half-lives differ because a self-recorded tape does not stop being
#: exclusive, while a processing advantage erodes as soon as somebody productises it.
ASYMMETRY_CLASSES: dict[str, tuple[float, int]] = {
    "EXCLUSIVE": (1.00, 365),
    "RECONSTRUCTIBLE": (0.70, 180),
    "PERISHABLE": (0.40, 90),
    "INTERPRETIVE": (0.15, 90),
    "COMMODITY": (0.00, 3650),
}

#: Classes whose asymmetry claim must state WHY a competitor cannot replicate it.
requires_evidence = ("EXCLUSIVE", "RECONSTRUCTIBLE")

#: How far a source has actually been mined. The rungs are deliberately about ARTEFACTS, not
#: effort: "we looked at it a lot" is not a depth.
DEPTH_LEVELS: dict[int, str] = {
    0: "UNTOUCHED -- named only",
    1: "SAMPLED -- pulled by hand at least once, nothing persisted",
    2: "COLLECTED -- a collector runs and history accumulates",
    3: "STRUCTURED -- parsed into features with a schema and a causal guard",
    4: "SCREENED -- features have been through stage A and the verdicts are recorded",
    5: "EXHAUSTED -- screened, and the negative results are in the graveyard with mechanisms",
}


@dataclass(frozen=True)
class AsymmetrySource:
    """One source, on both axes, with the evidence for its claim and an expiry on that claim."""

    name: str
    asymmetry: str
    depth: int
    verified: str  # ISO date the asymmetry claim was last checked
    why_not_replicable: str = ""
    note: str = ""
    owner: str = ""

    def __post_init__(self) -> None:
        if self.asymmetry not in ASYMMETRY_CLASSES:
            raise ValueError(
                f"{self.name}: unknown asymmetry class {self.asymmetry!r}. "
                f"Use one of {sorted(ASYMMETRY_CLASSES)}"
            )
        if self.depth not in DEPTH_LEVELS:
            raise ValueError(f"{self.name}: depth must be one of {sorted(DEPTH_LEVELS)}")
        if self.asymmetry in requires_evidence and not self.why_not_replicable.strip():
            raise ValueError(
                f"{self.name}: {self.asymmetry} requires `why_not_replicable`. A desk telling "
                "itself its data is special, with no stated reason a competitor cannot obtain "
                "it, is recording a wish rather than an asset -- and it is the single most "
                "comfortable error available in this file."
            )
        try:
            datetime.fromisoformat(self.verified)
        except ValueError as e:
            raise ValueError(f"{self.name}: `verified` must be an ISO date -- {e}") from None

    @property
    def stale(self) -> bool:
        """Has the asymmetry claim outlived its half-life without re-verification?"""
        _, days = ASYMMETRY_CLASSES[self.asymmetry]
        return datetime.fromisoformat(self.verified).replace(tzinfo=UTC) < (
            datetime.now(tz=UTC) - timedelta(days=days)
        )

    @property
    def effective_class(self) -> str:
        """UNVERIFIED once the claim is stale. NEVER silently the class it used to be."""
        return "UNVERIFIED" if self.stale else self.asymmetry

    @property
    def weight(self) -> float:
        """Edge weight, zero while unverified -- an expired claim earns nothing until rechecked."""
        return 0.0 if self.stale else ASYMMETRY_CLASSES[self.asymmetry][0]

    @property
    def realised(self) -> float:
        """Asymmetry ACTUALLY REALISED = weight x depth fraction.

        Holding exclusive data at depth 0 realises nothing. This is the number that matters and
        the one a breadth-only map cannot express: it is the product, and a zero in either factor
        zeroes it. The desk's 8.2GB of self-recorded tape scored maximum asymmetry and depth 2 for
        months, which is a rounding error away from not having it.
        """
        return self.weight * (self.depth / max(DEPTH_LEVELS))


def asymmetry_weight(cls: str) -> float:
    return ASYMMETRY_CLASSES.get(cls, (0.0, 0))[0]


@dataclass(frozen=True)
class Portfolio:
    """The desk's asymmetric holdings, on both axes at once."""

    sources: tuple[AsymmetrySource, ...] = field(default=())

    def by_class(self) -> dict[str, list[AsymmetrySource]]:
        out: dict[str, list[AsymmetrySource]] = {}
        for s in self.sources:
            out.setdefault(s.effective_class, []).append(s)
        return out

    @property
    def breadth(self) -> int:
        """How many sources carry a LIVE, non-commodity asymmetry claim."""
        return sum(1 for s in self.sources if s.effective_class not in ("COMMODITY", "UNVERIFIED"))

    @property
    def mean_depth(self) -> float:
        live = [s for s in self.sources if s.effective_class != "COMMODITY"]
        return sum(s.depth for s in live) / len(live) if live else 0.0

    @property
    def realised_total(self) -> float:
        return sum(s.realised for s in self.sources)

    def stale_claims(self) -> list[AsymmetrySource]:
        return [s for s in self.sources if s.stale and s.asymmetry != "COMMODITY"]

    def shallow_gold(self) -> list[AsymmetrySource]:
        """High asymmetry, low depth -- the desk's most expensive waste.

        These are the sources where the hard part is already done (the data is genuinely hard for
        a competitor to get) and the easy part is not (nobody has mined it). Ranked FIRST for
        effort, ahead of acquiring anything new: buying a second asymmetric source while the first
        sits at depth 1 grows breadth and shrinks realised asymmetry.
        """
        return sorted(
            (
                s
                for s in self.sources
                if s.weight >= ASYMMETRY_CLASSES["RECONSTRUCTIBLE"][0] and s.depth <= 2
            ),
            key=lambda s: (-s.weight, s.depth),
        )


ASYMMETRY_AXES = (
    "temporal",
    "latency",
    "geographic",
    "language",
    "semantic",
    "structural",
    "participant_constraint",
    "market_knowledge",
    "data_cleaning",
    "entity_resolution",
    "archival",
    "computational",
    "cross_domain_synthesis",
    "cross_venue",
    "execution",
    "capital_size",
    "liquidity",
    "regulatory_timing",
    "information_diffusion",
)

REPLICATION_FACTORS = (
    "source_breadth",
    "historical_depth",
    "data_cleaning",
    "entity_resolution",
    "compute",
    "specialist_knowledge",
    "latency",
    "engineering",
    "endogenous_history",
    "calibration_history",
)

SELF_FOOTPRINT_FIELDS: dict[str, tuple[str, ...]] = {
    "orders_submitted": ("order_submitted",),
    "orders_cancelled": ("order_cancelled", "cancelled"),
    "fills": ("order_filled", "fill_price", "filled"),
    "partial_fills": ("partial_fill", "partial"),
    "rejected_orders": ("order_rejected", "order_failed", "rejected"),
    "queue_estimates": ("queue_ahead", "queue_position"),
    "slippage": ("slippage", "cost_bps"),
    "latency": ("latency", "timestamps"),
    "market_impact": ("market_impact", "impact_bps"),
    "venue_response": ("venue_response", "broker_order_id", "mt5_ticket"),
    "signal_state": ("signal_state", "signal"),
    "portfolio_state": ("portfolio_state", "positions"),
    "capital_state": ("capital_state", "equity", "deployable"),
    "model_disagreement": ("model_disagreement", "model_votes"),
    "realized_vs_expected": ("expected", "realised", "realized"),
    "research_decisions": ("research_decision", "hypothesis", "decision"),
}


def replication_cost_profile(factors: Mapping[str, object]) -> dict[str, object]:
    """Aggregate explicit 0..1 reverse-engineering barriers without inventing hidden weights."""
    measured: dict[str, float] = {}
    invalid = []
    for name in REPLICATION_FACTORS:
        value = factors.get(name)
        if value is None:
            continue
        if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
            invalid.append(name)
            continue
        measured[name] = float(value)
    if not measured:
        return {
            "status": "UNMEASURED",
            "reason": "no explicit normalized replication factors",
            "missing": list(REPLICATION_FACTORS),
        }
    return {
        "status": "MEASURED" if len(measured) == len(REPLICATION_FACTORS) else "PARTIALLY_MEASURED",
        "replication_difficulty": sum(measured.values()) / len(measured),
        "hardest_factor": max(measured, key=lambda name: measured[name]),
        "weakest_factor": min(measured, key=lambda name: measured[name]),
        "factors": measured,
        "missing": [name for name in REPLICATION_FACTORS if name not in measured],
        "invalid": invalid,
        "weighting": "equal weight over supplied factors; no missing factor is imputed",
    }


def information_advantage_frontier(
    candidates: Sequence[Mapping[str, object]], *, as_of: str | datetime | None = None
) -> dict[str, object]:
    """Rank legally obtainable information moats on the mandate's multiplicative objective."""
    now = (
        as_of
        if isinstance(as_of, datetime)
        else datetime.fromisoformat(as_of)
        if as_of
        else datetime.now(tz=UTC)
    )
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    rows = []
    required = (
        "economic_usefulness",
        "persistence",
        "independence",
        "actionability",
    )
    for candidate in candidates:
        row = {"id": candidate.get("id", candidate.get("name"))}
        if candidate.get("lawfully_obtainable") is not True:
            rows.append(
                {
                    **row,
                    "status": "INELIGIBLE_OR_LEGAL_REVIEW_REQUIRED",
                    "priority_score": None,
                }
            )
            continue
        replication = candidate.get("replication_difficulty")
        raw_factors = candidate.get("replication_factors")
        profile = replication_cost_profile(raw_factors if isinstance(raw_factors, Mapping) else {})
        if not isinstance(replication, (int, float)):
            replication = profile.get("replication_difficulty")
        values = {name: candidate.get(name) for name in required}
        values["replication_difficulty"] = replication
        if not all(
            isinstance(value, (int, float)) and 0 <= float(value) <= 1 for value in values.values()
        ):
            rows.append(
                {
                    **row,
                    "status": "UNMEASURED",
                    "missing_or_invalid": [
                        name
                        for name, value in values.items()
                        if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1
                    ],
                    "replication_profile": profile,
                    "priority_score": None,
                }
            )
            continue
        decay = 1.0
        verified = candidate.get("verified_at")
        half_life = candidate.get("half_life_days")
        if verified and isinstance(half_life, (int, float)) and float(half_life) > 0:
            with contextlib.suppress(ValueError):
                stamp = datetime.fromisoformat(str(verified).replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=UTC)
                age_days = max(0.0, (now - stamp).total_seconds() / 86400)
                decay = 0.5 ** (age_days / float(half_life))
        adjusted = {name: finite_float(value) for name, value in values.items()}
        adjusted["persistence"] *= decay
        moat_value = math.prod(adjusted.values())
        cost = candidate.get("acquisition_research_cost")
        priority = (
            moat_value / float(cost) if isinstance(cost, (int, float)) and float(cost) > 0 else None
        )
        capacity = candidate.get("capacity")
        desk_capital = candidate.get("desk_capital")
        institution_floor = candidate.get("institutional_minimum_capacity")
        small_scale = (
            finite_float(capacity) >= finite_float(desk_capital)
            and finite_float(capacity) < finite_float(institution_floor)
            if all(
                isinstance(value, (int, float)) and not isinstance(value, bool)
                for value in (capacity, desk_capital, institution_floor)
            )
            else None
        )
        rows.append(
            {
                **row,
                "status": "MEASURED",
                "asymmetry_class": candidate.get("asymmetry_class"),
                "components": adjusted,
                "moat_value": moat_value,
                "acquisition_research_cost": cost,
                "priority_score": priority,
                "small_scale_structural_fit": small_scale,
                "replication_profile": profile,
                "decay_multiplier": decay,
                "state_recipe": candidate.get("state_recipe", []),
            }
        )
    rows.sort(
        key=lambda row: (
            row.get("priority_score") is None,
            -finite_float(row.get("priority_score")),
            str(row.get("id")),
        )
    )
    represented = sorted(
        {str(row.get("asymmetry_class")) for row in rows if row.get("asymmetry_class") is not None}
    )
    return {
        "status": "MEASURED" if candidates else "UNMEASURED",
        "candidates": rows,
        "asymmetry_axes": list(ASYMMETRY_AXES),
        "represented_axes": represented,
        "missing_axes": [name for name in ASYMMETRY_AXES if name not in represented],
        "objective": (
            "economic usefulness x persistence x independence x actionability x "
            "replication difficulty"
        ),
        "authority": "RESEARCH PRIORITY ONLY -- law, evidence, cost and survival rails remain",
    }


def self_footprint_coverage(
    records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Measure preservation of endogenous observations that no external source can recreate."""
    counts = dict.fromkeys(SELF_FOOTPRINT_FIELDS, 0)
    stamps: list[datetime] = []
    for record in records:
        blob = repr(record).casefold()
        for name, aliases in SELF_FOOTPRINT_FIELDS.items():
            if any(alias.casefold() in blob for alias in aliases):
                counts[name] += 1
        for time_field in ("timestamp", "at", "_taped", "opened", "closed", "generated"):
            if record.get(time_field):
                with contextlib.suppress(ValueError):
                    stamp = datetime.fromisoformat(str(record[time_field]).replace("Z", "+00:00"))
                    if stamp.tzinfo is None:
                        stamp = stamp.replace(tzinfo=UTC)
                    stamps.append(stamp)
                    break
    covered = sum(value > 0 for value in counts.values())
    return {
        "status": "MEASURED" if records else "UNMEASURED",
        "records": len(records),
        "coverage": covered / len(counts) if counts else None,
        "covered_fields": [name for name, value in counts.items() if value > 0],
        "missing_fields": [name for name, value in counts.items() if value == 0],
        "observations_by_field": counts,
        "history_days": (
            (max(stamps) - min(stamps)).total_seconds() / 86400 if len(stamps) >= 2 else None
        ),
        "compounding": (
            "append-only endogenous history; missing past observations cannot be backfilled"
        ),
        "authority": "MOAT COVERAGE ONLY -- no execution or promotion authority",
    }
