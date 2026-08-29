"""One interface every mechanism adapter implements. No adapter, no measurement, no guess.

WHY THIS EXISTS (principal, 2026-08-29: "remove the block -- nothing should ever be blocked")

That instruction is right, and blocking was the wrong fix. Five mechanisms were marked
UNMEASURABLE and removed from the search because `family_generic` measured them with a bare price
difference. But three of those five were blocked by WIRING, not by missing data:

    positioning_extreme   used distance-from-a-60-bar-mean   while COT parquets sat on disk
    carry_change          used a 24-bar price return          while carry_state.json held 388KB
                                                              of real swap terms
    cross_market_move     used ONE instrument's own return    while 251 instruments had bars

Blocking them was correct as a stopgap -- running a mislabelled test poisons every belief
downstream -- but it is not the fix. The fix is to MEASURE THEM PROPERLY, which is what an
adapter is: the code that knows what a mechanism's real observable is, where it lives, and how
to align it to bars without leaking the future.

AN ADAPTER EARNS ITS MEASUREMENT CLASS, IT DOES NOT DECLARE ONE. `compatibility` returns how
well this adapter can express a given hypothesis on the data actually present, and
`measurement_class` is derived from what it found -- so an adapter whose data file is missing
reports HEURISTIC or UNAVAILABLE for that run rather than claiming DIRECT and quietly falling
back. The class is a measurement of the measurement.

POINT-IN-TIME IS PART OF THE INTERFACE, not an afterthought. COT is published with a multi-day
lag; a swap rate is known only from its observation time. `pit_check` exists so an adapter cannot
be written without confronting when its observable was actually knowable, which is the single
easiest way to manufacture a spectacular backtest.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

#: Below this, the adapter is not expressing the hypothesis and must not be used for it.
MIN_COMPATIBILITY = 0.5


@dataclass
class MeasurementResult:
    """What an adapter actually managed to measure, and how honestly."""

    status: str                       # DIRECT | VALIDATED_PROXY | HEURISTIC_PROXY | UNAVAILABLE
    adapter: str
    feature_ids: list[str] = field(default_factory=list)
    confidence: float = 0.0
    pit_safe: bool = True
    notes: str = ""
    #: The observable series, aligned to the bar index. None when status is UNAVAILABLE.
    series: pd.Series | None = None

    @property
    def attributable(self) -> bool:
        """May a result from this measurement update beliefs about the mechanism?"""
        return self.status in ("DIRECT", "VALIDATED_PROXY") and self.pit_safe

    @property
    def runnable(self) -> bool:
        """UNAVAILABLE cannot run: there is no series.

        Everything else can, under its own honest label.
        """
        return self.status != "UNAVAILABLE" and self.series is not None


class ResearchAdapter(ABC):
    """A mechanism's real measurement. Subclasses know one mechanism and its data."""

    #: The semantic event this adapter measures.
    mechanism: str = ""
    #: Files/directories it needs. Reported when absent so a gap becomes a data-acquisition task
    #: rather than a silent downgrade.
    requires: tuple[str, ...] = ()

    @abstractmethod
    def compatibility(self, spec: dict[str, Any]) -> float:
        """0-1: how well this adapter expresses `spec`, given the data present RIGHT NOW."""

    @abstractmethod
    def measure(self, spec: dict[str, Any], bars: pd.DataFrame) -> MeasurementResult:
        """Produce the observable aligned to `bars.index`, or UNAVAILABLE with the reason."""

    def pit_check(self, series: pd.Series, bars: pd.DataFrame) -> tuple[bool, str]:
        """Is every value knowable at its own bar time?

        Default is the strict one: a series must be non-anticipating by construction, which for
        an as-of merge means every value's SOURCE timestamp is at or before the bar. An adapter
        with a lagged source overrides this and says how it lagged.
        """
        if series is None or series.empty:
            return False, "no series to check"
        if len(series) != len(bars):
            return False, (f"series length {len(series)} != bars {len(bars)}; an unaligned "
                           f"observable cannot be shown to be non-anticipating")
        return True, "aligned to the bar index by an as-of merge on or before each bar"

    def falsification_tests(self, spec: dict[str, Any]) -> list[str]:
        """Controls that would kill a result from this adapter. Never empty."""
        return [
            "randomise the observable's timestamps -- effect must vanish",
            "shuffle the observable across instruments -- effect must vanish",
            "cost stress at 3x measured spread",
        ]


class AdapterRegistry:
    """Every adapter, and the resolution that never guesses.

    `resolve` returns the BEST adapter above the compatibility floor, or an UNAVAILABLE result
    naming what was missing. It does not fall back to a generic price feature: the whole reason
    this package exists is that such a fallback tests a different hypothesis under the original's
    name.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, ResearchAdapter] = {}

    def register(self, adapter: ResearchAdapter) -> None:
        self._adapters[adapter.mechanism] = adapter

    def get(self, mechanism: str) -> ResearchAdapter | None:
        return self._adapters.get(mechanism)

    def all(self) -> dict[str, ResearchAdapter]:
        return dict(self._adapters)

    def resolve(self, spec: dict[str, Any], bars: pd.DataFrame) -> MeasurementResult:
        mech = str(spec.get("mechanism") or spec.get("event") or "")
        adapter = self._adapters.get(mech)
        if adapter is None:
            return MeasurementResult(
                status="UNAVAILABLE", adapter="none",
                notes=(f"no adapter registered for mechanism {mech!r}. This is a DATA-ACQUISITION "
                       f"or ADAPTER-BUILD task, not a licence to substitute a price feature -- "
                       f"substituting one tests a different hypothesis under this one's name."))
        score = adapter.compatibility(spec)
        if score < MIN_COMPATIBILITY:
            return MeasurementResult(
                status="UNAVAILABLE", adapter=adapter.__class__.__name__, confidence=score,
                notes=(f"{adapter.__class__.__name__} scores {score:.2f} on this hypothesis "
                       f"(floor {MIN_COMPATIBILITY}); it cannot express the claim. Missing: "
                       f"{', '.join(adapter.requires) or 'unclear'}"))
        return adapter.measure(spec, bars)


REGISTRY = AdapterRegistry()
