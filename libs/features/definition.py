"""Feature definitions.

A feature is a *versioned, tested* transform of bars to a single causal series — the same
``compute`` is used offline (training) and online (serving), which is what guarantees
train/serve parity. ``inputs`` declares the columns the feature reads (used for structural
target-leakage checks).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import pandas as pd

ComputeFn = Callable[[pd.DataFrame], pd.Series]


@dataclass(frozen=True)
class FeatureDefinition:
    """A versioned feature: name + version + a causal compute function."""

    name: str
    version: int
    compute: ComputeFn = field(compare=False, repr=False)
    inputs: tuple[str, ...]
    category: str = "price"
    description: str = ""
    min_periods: int = 1

    @property
    def key(self) -> str:
        return f"{self.name}@v{self.version}"
