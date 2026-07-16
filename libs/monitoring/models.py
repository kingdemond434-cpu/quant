"""Monitoring models — metric points, thresholds, alerts, SLOs."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Op(StrEnum):
    GT = "gt"
    LT = "lt"
    GE = "ge"
    LE = "le"


def compare(value: float, op: Op, threshold: float) -> bool:
    """Deterministic comparison used by thresholds and SLOs."""
    if op is Op.GT:
        return value > threshold
    if op is Op.LT:
        return value < threshold
    if op is Op.GE:
        return value >= threshold
    return value <= threshold


class MetricPoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    created_at: str
    name: str
    value: float
    tags: dict[str, Any] = Field(default_factory=dict)


class Threshold(BaseModel):
    """A rule that raises an alert of ``severity`` when ``metric op value`` is true."""

    model_config = ConfigDict(frozen=True)

    metric: str
    op: Op
    value: float
    severity: Severity = Severity.WARNING
    message: str = ""


class Alert(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    created_at: str
    severity: Severity
    source: str
    metric: str | None
    value: float | None
    threshold: float | None
    message: str
    resolved: bool = False


class SLO(BaseModel):
    """A service-level objective: ``metric op target`` must hold."""

    model_config = ConfigDict(frozen=True)

    name: str
    metric: str
    op: Op
    target: float
