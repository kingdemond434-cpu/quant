"""Feature-layer exceptions."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class FeatureError(QuantPlatformError):
    """Generic feature error (bad definition, missing inputs, duplicate version)."""


class LeakageError(FeatureError):
    """A feature looks into the future (lookahead / future / hindsight / full-sample leakage)."""


class ParityError(FeatureError):
    """A feature's offline (training) and online (serving) computations disagree."""
