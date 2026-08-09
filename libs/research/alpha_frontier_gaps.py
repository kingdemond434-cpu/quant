"""Convert the daily alpha frontier's missing measurements into max-push rows."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any


def queue_rows(path: Path, item: Callable[..., dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        report = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return [
            item(
                "alpha_frontier::artifact",
                "evidence_throughput",
                None,
                1.0,
                "daily_alpha_frontier.json absent",
                "run scripts/run_alpha_frontier.py",
                "data/intelligence/daily_alpha_frontier.json",
            )
        ]
    factory = report.get("factory", {}) if isinstance(report, dict) else {}
    rows = []
    for name, value in factory.items() if isinstance(factory, dict) else []:
        if not isinstance(value, dict):
            continue
        status = str(value.get("status", "MEASURED"))
        missing = status == "UNMEASURED" or (
            value.get("promotion_blocked") is True and not value.get("controls")
        )
        rows.append(
            item(
                f"alpha_frontier::{name}",
                "evidence_throughput",
                None if missing else 1.0,
                1.0,
                status,
                "supply the named real evidence and re-run; never synthesize a success",
                "data/intelligence/daily_alpha_frontier.json",
            )
        )
    practitioner = report.get("practitioner_frontier", {}) if isinstance(report, dict) else {}
    n_items = len(practitioner.get("items", [])) if isinstance(practitioner, dict) else 0
    rows.append(
        item(
            "alpha_frontier::practitioner_missions",
            "evidence_throughput",
            1.0 if n_items else None,
            1.0,
            f"{n_items} processed items",
            "run the unified GPT video/transcript, extreme-return and public-strategy missions",
            "data/intelligence/daily_alpha_frontier.json",
        )
    )
    return rows
