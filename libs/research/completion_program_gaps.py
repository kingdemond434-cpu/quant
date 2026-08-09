"""Flatten integrated completion measurements into the existing max-push queue."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any


def _status_rows(value: Any) -> list[tuple[str, str]]:
    """Collect nested status evidence so list-valued controls cannot disappear from ranking."""
    rows: list[tuple[str, str]] = []
    if isinstance(value, dict):
        if "status" in value:
            reason = (
                value.get("reason") or value.get("failed_or_unmeasured") or value.get("missing")
            )
            rows.append((str(value["status"]), str(reason or value["status"])))
        for child in value.values():
            if isinstance(child, (dict, list)):
                rows.extend(_status_rows(child))
    elif isinstance(value, list):
        for child in value:
            rows.extend(_status_rows(child))
    return rows


def queue_rows(
    report: dict[str, Any],
    item: Callable[..., dict[str, Any]],
    *,
    artifact: str = "data/completion_program.json",
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    source_for = {
        "validation": "evidence_throughput",
        "portfolio": "capital_utilisation",
        "research": "evidence_throughput",
        "production": "money_path_correctness",
    }
    unknown = {"UNMEASURED", "REFUSED", "INELIGIBLE", "ERROR", "INVALID_INPUT"}
    failed = {"CONTROL_FAILURE", "BLOCKED", "DEGRADED"}
    partial = {"PARTIALLY_MEASURED", "PARTIAL"}
    for section, values in report.items():
        if section not in source_for or not isinstance(values, dict):
            continue
        for name, measurement in values.items():
            if not isinstance(measurement, (dict, list)):
                continue
            evidence = _status_rows(measurement)
            statuses = {status for status, _ in evidence}
            if statuses & unknown:
                current: float | None = None
                status = sorted(statuses & unknown)[0]
            elif statuses & failed:
                current = 0.0
                status = sorted(statuses & failed)[0]
            elif statuses & partial:
                current = 0.5
                status = sorted(statuses & partial)[0]
            else:
                current = 1.0
                status = "MEASURED" if not statuses else "+".join(sorted(statuses))
            reasons = "; ".join(reason for _, reason in evidence[:3]) or status
            rows.append(
                item(
                    f"completion::{section}::{name}",
                    source_for[section],
                    current,
                    1.0,
                    f"{status}: {reasons}",
                    (
                        "supply and verify the named real input contract; never "
                        "substitute a zero or synthetic success"
                        if current is None
                        else "repair the measured control failure without weakening its bar"
                        if current < 1.0
                        else (
                            "keep the producer fresh and challenge whether this measurement "
                            "has enough power"
                        )
                    ),
                    artifact,
                )
            )
    return rows


def load(path: Path) -> dict[str, Any]:
    import json

    try:
        doc = json.loads(path.read_text("utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}
