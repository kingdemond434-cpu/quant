"""Declared per-sleeve allocations -- what makes an allocation-aware capacity gate honest.

§42 lets a candidate be judged against the equity IT will actually be funded with rather than an
equal-weight share of the book. That is strictly correct -- a $5k-capacity edge funded with $1,000
is 5x headroom and perfectly safe, while equal weight on a $14.8k book reads $1,477 into it and
fails -- and it is exactly the excluded-by-default bug §42 exists to kill, one layer further down.

BUT A DECLARED NUMBER WITH NOTHING CHECKING IT IS A BYPASS. If a candidate may simply assert
"I will only use $1", every capacity gate in the desk passes forever and the protection is gone. A
declaration is therefore a COMMITMENT with two mechanical consequences, both enforced by
``max_audit.check_capacity_allocation_honesty``:

  1. IT MUST BE SELF-CONSISTENT. A declaration above what its own edge can hold
     (``max_allocation(capacity)``) is refused outright -- it is asking for a pass it does not
     qualify for even under its own numbers.
  2. IT IS RECONCILED AGAINST WHAT THE SLEEVE IS ACTUALLY FUNDED WITH. Funding a sleeve above its
     declaration is the whole bypass, and it fires as a defect naming the sleeve, the declared
     figure and the real one. This is the half that has to exist BEFORE the declaration is trusted
     anywhere, which is why it ships in the same change rather than being left for Gate 0.

PRE-GATE-0 HONESTY. Nothing is live yet, so the reconciliation has nothing to compare against most
of the time. It reports that as UNVERIFIED rather than as a pass -- "no live funding data" and
"funding matches the declaration" are different states and must never print the same way.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from libs.research.capacity_policy import max_allocation

STORE = Path("data/sleeve_allocations.json")


class SleeveAllocation(BaseModel):
    """One sleeve's declared capacity and the equity it commits to using."""

    model_config = ConfigDict(frozen=True)

    sleeve: str
    capacity_usd: float
    declared_usd: float

    @property
    def ceiling_usd(self) -> float:
        """Most this sleeve may EVER be funded with, from its own capacity."""
        return max_allocation(self.capacity_usd)

    @property
    def self_consistent(self) -> bool:
        return 0.0 < self.declared_usd <= self.ceiling_usd


def load(store: Path = STORE) -> list[SleeveAllocation]:
    """Read the declarations. A missing or corrupt store is EMPTY, never an exception."""
    try:
        raw = json.loads(store.read_text("utf-8"))
    except Exception:
        return []
    out: list[SleeveAllocation] = []
    for name, row in (raw.items() if isinstance(raw, dict) else []):
        try:
            out.append(SleeveAllocation(
                sleeve=str(name), capacity_usd=float(row["capacity_usd"]),
                declared_usd=float(row["declared_usd"])))
        except Exception:
            continue                      # one malformed row must not hide the rest
    return out


def inconsistent(allocs: list[SleeveAllocation]) -> list[SleeveAllocation]:
    """Declarations that exceed what their own edge can hold -- refused before anything else."""
    return [a for a in allocs if not a.self_consistent]


def overfunded(
    allocs: list[SleeveAllocation], funded: dict[str, float], *, tolerance: float = 0.05
) -> list[tuple[SleeveAllocation, float]]:
    """Sleeves funded above what they declared -- the bypass, caught.

    A 5% tolerance absorbs mark-to-market drift and fill slippage: a sleeve declared at $1,000 that
    marks to $1,020 has not cheated, and firing on that would train the desk to ignore the check.
    Anything beyond it is a real breach of the commitment the capacity gate was passed on.
    """
    out: list[tuple[SleeveAllocation, float]] = []
    for a in allocs:
        got = funded.get(a.sleeve)
        if got is not None and got > a.declared_usd * (1.0 + tolerance):
            out.append((a, got))
    return out


def unverified(
    allocs: list[SleeveAllocation], funded: dict[str, float]
) -> list[SleeveAllocation]:
    """Declarations with no live funding figure to check -- reported, never counted as OK."""
    return [a for a in allocs if a.sleeve not in funded]
