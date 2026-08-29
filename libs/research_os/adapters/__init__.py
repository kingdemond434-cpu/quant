"""Mechanism adapters: the code that knows what a mechanism's real observable is.

Registered here so `REGISTRY.resolve` reaches them without any caller importing a concrete
adapter. A mechanism with no adapter resolves to UNAVAILABLE with the missing data named -- which
is a data-acquisition task, never a licence to substitute a price feature.
"""
from libs.research_os.adapters.base import (
    MIN_COMPATIBILITY,
    REGISTRY,
    AdapterRegistry,
    MeasurementResult,
    ResearchAdapter,
)
from libs.research_os.adapters.owned_data import (
    CarryAdapter,
    CotPositioningAdapter,
    CrossAssetAdapter,
)

for _a in (CotPositioningAdapter(), CarryAdapter(), CrossAssetAdapter()):
    REGISTRY.register(_a)

__all__ = ["MIN_COMPATIBILITY", "REGISTRY", "AdapterRegistry", "CarryAdapter",
           "CotPositioningAdapter", "CrossAssetAdapter", "MeasurementResult", "ResearchAdapter"]
