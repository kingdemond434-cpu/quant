"""Stage 15 research-factory errors."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class Stage15Error(QuantPlatformError):
    """Base error for the Stage 15 alpha discovery / research factory."""


class ResearchGovernanceError(Stage15Error):
    """Raised when research governance (the research kill-switch) blocks an action."""
