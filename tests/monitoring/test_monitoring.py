"""Metrics store, alerting, monitor thresholds, heartbeat, and SLOs."""

from __future__ import annotations

import pytest

from libs.monitoring.alerting import AlertRouter, AlertStore, CollectingSink
from libs.monitoring.metrics_store import MetricsStore
from libs.monitoring.models import SLO, Op, Severity, Threshold
from libs.monitoring.monitor import HeartbeatWatchdog, MonitorService, SLOEvaluator
from libs.store.connection import Database


def test_metrics_store_record_latest_history(db: Database) -> None:
    store = MetricsStore(db)
    store.record("equity", 100.0)
    store.record("equity", 101.0, tags={"account": "live"})
    assert store.latest("equity").value == 101.0
    hist = store.history("equity")
    assert [p.value for p in hist] == [100.0, 101.0]
    assert store.latest("missing") is None


def test_metric_points_append_only(db: Database) -> None:
    point = MetricsStore(db).record("x", 1.0)
    with pytest.raises(Exception, match="append-only"), db.transaction() as conn:
        conn.execute("DELETE FROM metric_points WHERE id = ?", (point.id,))
    with pytest.raises(Exception, match="append-only"), db.transaction() as conn:
        conn.execute("UPDATE metric_points SET value = 2 WHERE id = ?", (point.id,))


def test_monitor_raises_alert_on_threshold_breach(db: Database) -> None:
    sink = CollectingSink()
    monitor = MonitorService(
        db,
        [Threshold(metric="drawdown", op=Op.GT, value=0.2, severity=Severity.CRITICAL,
                   message="drawdown breach")],
        router=AlertRouter([sink]),
    )
    assert monitor.record("drawdown", 0.1) is not None
    assert sink.alerts == []  # below threshold

    raised = monitor.evaluate("drawdown", 0.3)
    assert len(raised) == 1
    assert raised[0].severity is Severity.CRITICAL
    assert sink.alerts[0].message == "drawdown breach"


def test_alert_store_resolve_and_open(db: Database) -> None:
    alerts = AlertStore(db)
    a = alerts.record(severity=Severity.WARNING, source="monitor", message="warn")
    assert [x.id for x in alerts.open_alerts()] == [a.id]
    alerts.resolve(a.id)
    assert alerts.open_alerts() == []
    assert len(alerts.all()) == 1


def test_alerts_append_only(db: Database) -> None:
    a = AlertStore(db).record(severity=Severity.INFO, source="s", message="m")
    with pytest.raises(Exception, match="append-only"), db.transaction() as conn:
        conn.execute("DELETE FROM alerts WHERE id = ?", (a.id,))


def test_heartbeat_watchdog() -> None:
    wd = HeartbeatWatchdog(max_silence_seconds=30.0)
    assert wd.alive(last_beat_epoch=100.0, now_epoch=120.0)
    assert not wd.alive(last_beat_epoch=100.0, now_epoch=140.0)


def test_slo_evaluator_fail_closed() -> None:
    evaluator = SLOEvaluator([
        SLO(name="uptime", metric="uptime", op=Op.GE, target=0.99),
        SLO(name="latency", metric="latency_ms", op=Op.LE, target=50.0),
    ])
    results = evaluator.evaluate({"uptime": 0.995})  # latency missing
    assert results == {"uptime": True, "latency": False}  # missing metric fails closed
