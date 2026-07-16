"""``libs.features`` — versioned, PIT-correct features with leakage + parity validation.

The same definition serves training and serving (parity by construction); the leakage test
(future invariance) rejects future/target/lookahead/hindsight/full-sample leakage. Built-in
features are registered into :data:`DEFAULT_REGISTRY` on import.
"""

from __future__ import annotations

from libs.features.builtin import BUILTIN_FEATURES, register_builtin_features
from libs.features.definition import ComputeFn, FeatureDefinition
from libs.features.errors import FeatureError, LeakageError, ParityError
from libs.features.labels import LABEL_PREFIX, forward_direction, forward_log_return
from libs.features.pit import build_feature_table, compute_online_vector, pit_join
from libs.features.registry import (
    DEFAULT_REGISTRY,
    FeatureRegistry,
    get_feature,
    register_feature,
)
from libs.features.validation import (
    FeatureValidation,
    LeakageResult,
    ParityResult,
    run_leakage_test,
    run_parity_test,
    validate_feature,
)

register_builtin_features(DEFAULT_REGISTRY)

__all__ = [  # noqa: RUF022  # grouped by concern
    # definition / registry
    "FeatureDefinition",
    "ComputeFn",
    "FeatureRegistry",
    "DEFAULT_REGISTRY",
    "register_feature",
    "get_feature",
    "BUILTIN_FEATURES",
    "register_builtin_features",
    # validation
    "validate_feature",
    "run_leakage_test",
    "run_parity_test",
    "FeatureValidation",
    "LeakageResult",
    "ParityResult",
    # pit
    "pit_join",
    "build_feature_table",
    "compute_online_vector",
    # labels
    "forward_log_return",
    "forward_direction",
    "LABEL_PREFIX",
    # errors
    "FeatureError",
    "LeakageError",
    "ParityError",
]
