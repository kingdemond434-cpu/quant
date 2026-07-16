"""Monitor service — record metrics, evaluate thresholds/SLOs, raise and route alerts.

Deterministic: a metric value is compared against its thresholds with fixed operators; any breach
records a durable alert and dispatches it. A heartbeat watchdog and SLO evaluator are provided for
liveness and objective tracking. Fail-closed: a missing metric fails its SLO.
"""

from __future__ import annotations

from collections.abc import Sequence

from libs.monitoring.alerting import AlertRouter, AlertStore
from libs.monitoring.metrics_store import MetricsStore
from libs.monitoring.models import SLO, Alert, MetricPoint, Severity, Threshold, compare
from libs.store.connection import Database


class MonitorService:
    """Records metrics and raises alerts when thresholds are breached."""

    def __init__(
        self,
        db: Database,
        thresholds: Sequence[Threshold] | None = None,
        *,
        router: AlertRouter | None = None,
    ) -> None:
        self.metrics = MetricsStore(db)
        self.alerts = AlertStore(db)
        self.router = router or AlertRouter()
        self._thresholds: list[Threshold] = list(thresholds or [])

    def add_threshold(self, threshold: Threshold) -> None:
        self._thresholds.append(threshold)

    def record(self, name: str, value: float, *, tags: dict[str, str] | None = None) -> MetricPoint:
        """Persist a metric point and evaluate its thresholds (raising alerts on breach)."""
        point = self.metrics.record(name, value, tags=tags)
        self.evaluate(name, value)
        return point

    def evaluate(self, name: str, value: float) -> list[Alert]:
        """Evaluate a value against all thresholds for ``name``; record+route any breaches."""
        raised: list[Alert] = []
        for threshold in self._thresholds:
            if threshold.metric != name:
                continue
            if compare(value, threshold.op, threshold.value):
                alert = self.alerts.record(
                    severity=threshold.severity, source="monitor", metric=name, value=value,
                    threshold=threshold.value,
                    message=threshold.message
                    or f"{name}={value} {threshold.op.value} {threshold.value}",
                )
                self.router.dispatch(alert)
                raised.append(alert)
        return raised


class HeartbeatWatchdog:
    """Liveness check from monotonic timestamps (seconds); fail-closed if silent too long."""

    def __init__(self, *, max_silence_seconds: float) -> None:
        self.max_silence_seconds = max_silence_seconds

    def alive(self, *, last_beat_epoch: float, now_epoch: float) -> bool:
        return (now_epoch - last_beat_epoch) <= self.max_silence_seconds


class SLOEvaluator:
    """Evaluates a set of SLOs against current metric values (missing metric -> failed)."""

    def __init__(self, slos: Sequence[SLO]) -> None:
        self.slos = list(slos)

    def evaluate(self, metrics: dict[str, float]) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for slo in self.slos:
            if slo.metric not in metrics:
                results[slo.name] = False  # fail-closed
                continue
            results[slo.name] = compare(metrics[slo.metric], slo.op, slo.target)
        return results


__all__ = [
    "HeartbeatWatchdog",
    "MonitorService",
    "SLOEvaluator",
    "Severity",
]
