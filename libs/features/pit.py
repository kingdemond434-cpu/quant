"""Point-in-time joins and feature-table construction.

``pit_join`` is an as-of (backward) merge: each base row sees only the most recent auxiliary
row at or before its timestamp — never a future one. The offline feature table and the online
feature vector are built from the same definitions, guaranteeing parity by construction.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from libs.features.definition import FeatureDefinition
from libs.features.errors import FeatureError

TIMESTAMP = "timestamp"


def pit_join(
    base: pd.DataFrame,
    other: pd.DataFrame,
    *,
    value_columns: Sequence[str],
    on: str = TIMESTAMP,
    suffix: str = "",
) -> pd.DataFrame:
    """As-of backward join: attach the latest ``other`` values known at each ``base`` time."""
    left = base.sort_values(on)
    right = other.sort_values(on)[[on, *value_columns]]
    if suffix:
        right = right.rename(columns={c: f"{c}{suffix}" for c in value_columns})
    merged = pd.merge_asof(left, right, on=on, direction="backward")
    return merged.reset_index(drop=True)


def build_feature_table(
    bars: pd.DataFrame, definitions: Sequence[FeatureDefinition]
) -> pd.DataFrame:
    """Build the offline (training) feature table: ``timestamp`` + one column per feature."""
    table = pd.DataFrame({TIMESTAMP: bars[TIMESTAMP].to_numpy()})
    for definition in definitions:
        table[definition.key] = definition.compute(bars).to_numpy()
    return table


def compute_online_vector(
    history: pd.DataFrame, definitions: Sequence[FeatureDefinition]
) -> dict[str, float]:
    """Compute the latest (serving) feature vector from history up to the current bar."""
    if history.empty:
        raise FeatureError("cannot compute an online vector from empty history")
    return {
        definition.key: float(definition.compute(history).to_numpy(dtype="float64")[-1])
        for definition in definitions
    }
