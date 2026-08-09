from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from libs.research import alpha_frontier_gaps, completion_program_gaps


def _item(*args: Any) -> dict[str, Any]:
    return {
        "key": args[0],
        "source": args[1],
        "current": args[2],
        "target": args[3],
        "reason": args[4],
        "next_action": args[5],
        "artifact": args[6],
    }


def test_completion_program_projects_every_status_class() -> None:
    report = {
        "validation": {
            "unknown": {"status": "UNMEASURED", "missing": "real samples"},
            "failed": {"status": "CONTROL_FAILURE", "reason": "gate failed"},
            "nested_partial": {"children": [{"status": "PARTIAL"}]},
            "measured": {"status": "HEALTHY"},
            "empty": {},
            "ignored": "not a measurement",
        },
        "portfolio": {"ok": [{"status": "MEASURED"}]},
        "research": "not a section",
        "unknown_section": {"ignored": {"status": "UNMEASURED"}},
    }

    rows = completion_program_gaps.queue_rows(report, _item, artifact="report.json")
    by_key = {row["key"]: row for row in rows}

    assert by_key["completion::validation::unknown"]["current"] is None
    assert "real samples" in by_key["completion::validation::unknown"]["reason"]
    assert by_key["completion::validation::failed"]["current"] == 0.0
    assert by_key["completion::validation::nested_partial"]["current"] == 0.5
    assert by_key["completion::validation::measured"]["current"] == 1.0
    assert by_key["completion::validation::empty"]["reason"] == "MEASURED: MEASURED"
    assert by_key["completion::portfolio::ok"]["source"] == "capital_utilisation"
    assert all(row["artifact"] == "report.json" for row in rows)


def test_completion_program_load_is_fail_closed(tmp_path: Path) -> None:
    valid = tmp_path / "valid.json"
    valid.write_text(json.dumps({"validation": {}}), encoding="utf-8")
    assert completion_program_gaps.load(valid) == {"validation": {}}

    non_object = tmp_path / "list.json"
    non_object.write_text("[]", encoding="utf-8")
    assert completion_program_gaps.load(non_object) == {}

    invalid = tmp_path / "invalid.json"
    invalid.write_text("{", encoding="utf-8")
    assert completion_program_gaps.load(invalid) == {}
    assert completion_program_gaps.load(tmp_path / "missing.json") == {}


def test_alpha_frontier_projects_missing_and_measured_evidence(tmp_path: Path) -> None:
    report = {
        "factory": {
            "unmeasured": {"status": "UNMEASURED"},
            "blocked_without_controls": {
                "status": "BLOCKED",
                "promotion_blocked": True,
            },
            "blocked_with_controls": {
                "status": "BLOCKED",
                "promotion_blocked": True,
                "controls": ["embargo"],
            },
            "implicit_measured": {},
            "ignored": 3,
        },
        "practitioner_frontier": {"items": [{"mechanism": "state transition"}]},
    }
    path = tmp_path / "frontier.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    rows = alpha_frontier_gaps.queue_rows(path, _item)
    by_key = {row["key"]: row for row in rows}

    assert by_key["alpha_frontier::unmeasured"]["current"] is None
    assert by_key["alpha_frontier::blocked_without_controls"]["current"] is None
    assert by_key["alpha_frontier::blocked_with_controls"]["current"] == 1.0
    assert by_key["alpha_frontier::implicit_measured"]["current"] == 1.0
    assert by_key["alpha_frontier::practitioner_missions"]["current"] == 1.0


def test_alpha_frontier_missing_invalid_and_empty_practitioner(tmp_path: Path) -> None:
    missing_rows = alpha_frontier_gaps.queue_rows(tmp_path / "missing.json", _item)
    assert missing_rows[0]["key"] == "alpha_frontier::artifact"
    assert missing_rows[0]["current"] is None

    invalid = tmp_path / "invalid.json"
    invalid.write_text("{", encoding="utf-8")
    assert alpha_frontier_gaps.queue_rows(invalid, _item)[0]["key"] == ("alpha_frontier::artifact")

    scalar = tmp_path / "scalar.json"
    scalar.write_text("[]", encoding="utf-8")
    rows = alpha_frontier_gaps.queue_rows(scalar, _item)
    assert rows == [
        {
            "key": "alpha_frontier::practitioner_missions",
            "source": "evidence_throughput",
            "current": None,
            "target": 1.0,
            "reason": "0 processed items",
            "next_action": (
                "run the unified GPT video/transcript, extreme-return and public-strategy missions"
            ),
            "artifact": "data/intelligence/daily_alpha_frontier.json",
        }
    ]
