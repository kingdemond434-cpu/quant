from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "build_midnight_operations_report", ROOT / "scripts"
    / "build_midnight_operations_report.py"
)
assert SPEC and SPEC.loader
reporter = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = reporter
SPEC.loader.exec_module(reporter)


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), "utf-8")


def test_report_balances_every_screen_and_measures_forward_truth(tmp_path: Path) -> None:
    desk = tmp_path / "desks" / "mt5"
    docket = [
        {"symbol": "XAUUSD", "family": family, "params": {}}
        for family in ("pass", "fail", "later", "nodata")
    ]
    _write(desk / "data" / "hypotheses" / "external_survivors.json", docket)
    ids = {row["family"]: reporter._cell_id(row) for row in docket}
    _write(desk / "reports" / "universal_gates_external.json", {
        "n_cells_discovered": 4,
        "n_cells_deferred_build_budget": 1,
        "verdicts": [
            {"cell": ids["pass"], "passed": True, "stages": {}},
            {"cell": ids["fail"], "passed": False,
             "stages": {"deflated_sharpe": {"passed": False}}},
            {"cell": ids["later"], "passed": None,
             "downstream_status": "NOT_RUN_BUILD_BUDGET_DEFERRED", "stages": {}},
            {"cell": ids["nodata"], "passed": None,
             "downstream_status": "NOT_RUN_DATA_MISSING", "stages": {}},
        ],
    })
    _write(desk / "data" / "research_queue.json", [{
        "id": "q", "status": "PENDING", "created_at": "2026-08-01T00:00:00Z"
    }])
    _write(desk / "reports" / "UNIVERSAL_SURVIVORS.json", {"survivors": {
        "cert": {"cell": "cert-cell", "gated_at": "2026-08-28T00:00:00Z"}
    }})
    _write(desk / "reports" / "shadow" / "shadow_state.json", {
        "forward": {"status": "ACTIVE", "certificate": "cert", "n": 3,
                    "bar_source": "Fusion MT5 native",
                    "last_source_bar": "2026-08-29T10:00:00Z"}
    })
    _write(desk / "reports" / "portfolio_evidence.json", {
        "effective_bets": {"n_sleeves": 2, "n_effective": 1.2}
    })
    completion = {
        "before": {"universal_certificates": 0},
        "after": {"universal_certificates": 1},
        "hard_failures": [],
        "stages": [{"name": "gauntlet", "cpu_seconds": 1800,
                    "certificate_delta": 1, "duration_seconds": 2000}],
    }
    report = reporter.build(tmp_path, completion, datetime(2026, 8, 29, 12, tzinfo=UTC))
    assert report["candidate_conservation"] == {
        "formula": "discovered = tested + queued + rejected + blocked; lost must equal zero",
        "discovered": 4, "tested": 1, "queued": 1, "rejected": 1, "blocked": 1,
        "accounted": 4, "lost": 0, "balanced": True, "lost_cells": [],
        "resumable_deferred": 1,
        "cell_checkpoint": "content-addressed external_gauntlet series cache by cell+data-day",
    }
    assert report["sla"]["queue_overdue"] == 1
    assert report["sla"]["certificates_not_enrolled"] == 0
    assert report["forward_truth"]["fusion_native"] == 1
    assert report["forward_truth"]["stale"] == 0
    assert report["compute_efficiency"]["certificates_per_cpu_hour"] == 2.0
    assert report["failure_root_causes"][0]["cause"] in {
        "deflated_sharpe", "NOT_RUN_BUILD_BUDGET_DEFERRED", "NOT_RUN_DATA_MISSING"
    }


def test_report_calls_an_unverdict_ed_screen_lost(tmp_path: Path) -> None:
    desk = tmp_path / "desks" / "mt5"
    _write(desk / "data" / "hypotheses" / "external_survivors.json", [
        {"symbol": "EURUSD", "family": "x", "params": {}}
    ])
    _write(desk / "reports" / "universal_gates_external.json", {
        "n_cells_discovered": 1, "verdicts": []
    })
    report = reporter.build(tmp_path, {}, datetime(2026, 8, 29, tzinfo=UTC))
    assert report["candidate_conservation"]["lost"] == 1
    assert report["candidate_conservation"]["balanced"] is False


def test_gauntlet_records_missing_data_and_build_failures_instead_of_dropping_them() -> None:
    source = (ROOT / "desks" / "mt5" / "scripts" / "external_gauntlet.py").read_text("utf-8")
    assert '"downstream_status": "NOT_RUN_DATA_MISSING"' in source
    assert '"downstream_status": "NOT_RUN_BUILD_FAILED"' in source
    assert 'result["n_cells_blocked_build_or_data"]' in source
    assert "blocked_verdicts" in source
