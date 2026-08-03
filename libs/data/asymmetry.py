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

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

__all__ = [
    "ASYMMETRY_CLASSES",
    "DEPTH_LEVELS",
    "AsymmetrySource",
    "Portfolio",
    "asymmetry_weight",
    "requires_evidence",
]

#: class -> (edge weight, how long a claim stays fresh in days). Weights are ORDINAL, not a
#: forecast: they rank where effort should go, and multiplying them by an expected return would be
#: inventing a number. Half-lives differ because a self-recorded tape does not stop being
#: exclusive, while a processing advantage erodes as soon as somebody productises it.
ASYMMETRY_CLASSES: dict[str, tuple[float, int]] = {
    "EXCLUSIVE":       (1.00, 365),
    "RECONSTRUCTIBLE": (0.70, 180),
    "PERISHABLE":      (0.40,  90),
    "INTERPRETIVE":    (0.15,  90),
    "COMMODITY":       (0.00, 3650),
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
    verified: str                       # ISO date the asymmetry claim was last checked
    why_not_replicable: str = ""
    note: str = ""
    owner: str = ""

    def __post_init__(self) -> None:
        if self.asymmetry not in ASYMMETRY_CLASSES:
            raise ValueError(
                f"{self.name}: unknown asymmetry class {self.asymmetry!r}. "
                f"Use one of {sorted(ASYMMETRY_CLASSES)}")
        if self.depth not in DEPTH_LEVELS:
            raise ValueError(f"{self.name}: depth must be one of {sorted(DEPTH_LEVELS)}")
        if self.asymmetry in requires_evidence and not self.why_not_replicable.strip():
            raise ValueError(
                f"{self.name}: {self.asymmetry} requires `why_not_replicable`. A desk telling "
                "itself its data is special, with no stated reason a competitor cannot obtain "
                "it, is recording a wish rather than an asset -- and it is the single most "
                "comfortable error available in this file.")
        try:
            datetime.fromisoformat(self.verified)
        except ValueError as e:
            raise ValueError(f"{self.name}: `verified` must be an ISO date -- {e}") from None

    @property
    def stale(self) -> bool:
        """Has the asymmetry claim outlived its half-life without re-verification?"""
        _, days = ASYMMETRY_CLASSES[self.asymmetry]
        return datetime.fromisoformat(self.verified).replace(tzinfo=UTC) < (
            datetime.now(tz=UTC) - timedelta(days=days))

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
        return sum(1 for s in self.sources
                   if s.effective_class not in ("COMMODITY", "UNVERIFIED"))

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
        return sorted((s for s in self.sources
                       if s.weight >= ASYMMETRY_CLASSES["RECONSTRUCTIBLE"][0] and s.depth <= 2),
                      key=lambda s: (-s.weight, s.depth))
