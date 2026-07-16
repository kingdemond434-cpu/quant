"""``libs.monitoring`` — live telemetry, threshold alerting, SLOs, and heartbeat.

Persists metrics and alerts to the SQLite system of record (migration 0004), evaluates
thresholds/SLOs deterministically, and routes alerts to pluggable sinks. No parallel store; the
metric series is append-only and alerts are resolvable but never deleted.
"""

from __future__ import annotations

from libs.monitoring.alerting import (
    AlertRouter,
    AlertSink,
    AlertStore,
    CollectingSink,
)
from libs.monitoring.metrics_store import MetricsStore
from libs.monitoring.models import (
    SLO,
    Alert,
    MetricPoint,
    Op,
    Severity,
    Threshold,
    compare,
)
from libs.monitoring.monitor import HeartbeatWatchdog, MonitorService, SLOEvaluator

__all__ = [  # noqa: RUF022  # grouped by concern
    # models
    "Severity",
    "Op",
    "compare",
    "MetricPoint",
    "Threshold",
    "Alert",
    "SLO",
    # stores
    "MetricsStore",
    "AlertStore",
    # alerting
    "AlertRouter",
    "AlertSink",
    "CollectingSink",
    # service
    "MonitorService",
    "HeartbeatWatchdog",
    "SLOEvaluator",
]
