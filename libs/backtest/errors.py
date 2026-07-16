"""Backtest exceptions."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class BacktestError(QuantPlatformError):
    """Invalid backtest configuration or inputs."""


class VerificationError(BacktestError):
    """Cross-engine verification found a divergence beyond tolerance."""
