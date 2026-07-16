"""Feature registry with versioning.

Definitions are keyed ``name@vN``; a name may carry multiple versions but each version is
immutable once registered. ``register_feature`` can validate against a sample frame and
auto-reject leaky features before they ever enter the registry.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from libs.features.definition import FeatureDefinition
from libs.features.errors import FeatureError
from libs.features.validation import validate_feature


class FeatureRegistry:
    """An in-memory registry of versioned feature definitions."""

    def __init__(self) -> None:
        self._features: dict[str, FeatureDefinition] = {}

    def register(self, definition: FeatureDefinition, *, overwrite: bool = False) -> None:
        if definition.key in self._features and not overwrite:
            raise FeatureError(f"feature {definition.key} already registered")
        self._features[definition.key] = definition

    def get(self, name: str, version: int | None = None) -> FeatureDefinition:
        if version is not None:
            try:
                return self._features[f"{name}@v{version}"]
            except KeyError as exc:
                raise FeatureError(f"feature {name}@v{version} not found") from exc
        versions = self.versions(name)
        if not versions:
            raise FeatureError(f"feature {name} not found")
        return self._features[f"{name}@v{max(versions)}"]

    def versions(self, name: str) -> list[int]:
        return sorted(d.version for d in self._features.values() if d.name == name)

    def list(self) -> list[FeatureDefinition]:
        return list(self._features.values())

    def __len__(self) -> int:
        return len(self._features)

    def __contains__(self, key: str) -> bool:
        return key in self._features


DEFAULT_REGISTRY = FeatureRegistry()


def register_feature(
    definition: FeatureDefinition,
    *,
    registry: FeatureRegistry | None = None,
    bars: pd.DataFrame | None = None,
    label_columns: Sequence[str] = (),
    overwrite: bool = False,
) -> FeatureDefinition:
    """Register a feature, optionally validating (and auto-rejecting) it against ``bars``."""
    reg = registry if registry is not None else DEFAULT_REGISTRY
    if bars is not None:
        validate_feature(definition, bars, label_columns=label_columns, strict=True)
    reg.register(definition, overwrite=overwrite)
    return definition


def get_feature(
    name: str, version: int | None = None, *, registry: FeatureRegistry | None = None
) -> FeatureDefinition:
    reg = registry if registry is not None else DEFAULT_REGISTRY
    return reg.get(name, version)
