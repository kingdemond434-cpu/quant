"""``app`` — the runtime/application layer: feeds, demo runner, dashboard, readiness, MT5 adapter.

This layer wires the validated ``libs`` engines into a runnable end-to-end demo (paper venue,
replay feed) and the production MT5 path. It adds no trading logic of its own; it orchestrates and
renders. Live data (MT5) and the web dashboard (Streamlit) require external services; both guarded.
"""

from __future__ import annotations

from app.dashboard import DashboardState, build_dashboard
from app.demo_runner import DemoRunner, DemoRunResult
from app.feed import Feed, MT5Feed, ReplayFeed
from app.readiness import CheckResult, ReadinessReport, readiness_check

__all__ = [
    "CheckResult",
    "DashboardState",
    "DemoRunResult",
    "DemoRunner",
    "Feed",
    "MT5Feed",
    "ReadinessReport",
    "ReplayFeed",
    "build_dashboard",
    "readiness_check",
]
