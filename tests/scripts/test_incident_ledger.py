from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from scripts import incident_ledger as il

T0 = datetime(2026, 11, 10, 23, 0, tzinfo=UTC)


def _at(m: float) -> datetime:
    return T0 + timedelta(minutes=m)


def _apply(rows: list[dict[str, Any]], m: float, red: dict, ok: set, last_ok: dict,
           heals: dict | None = None) -> list[dict[str, Any]]:  # fmt: skip
    new = il.step(rows, _at(m), red, ok, last_ok, heals)
    rows.extend(new)
    return new


def test_open_once_then_close_with_mttd_and_mttr_bounds() -> None:
    rows: list[dict[str, Any]] = []
    last_ok = {"merge_train": _at(-30).isoformat()}
    _apply(rows, 0, {"merge_train": ["GATE_SILENT"]}, set(), last_ok)
    assert _apply(rows, 60, {"merge_train": ["GATE_SILENT"]}, set(), last_ok) == []
    close = _apply(rows, 180, {}, {"merge_train"}, last_ok)[0]
    assert close["event"] == "close" and close["minutes"] == 180.0
    assert close["mttd_min"] == 30.0 and close["mttr_min"] == 210.0
    assert close["cleared_by"] == "unattributed" and close["human_needed"] is False


def test_no_healthy_sighting_means_null_never_guessed() -> None:
    rows: list[dict[str, Any]] = []
    _apply(rows, 0, {"slo:feeds": ["BREACHING"]}, set(), {})
    close = _apply(rows, 60, {}, {"slo:feeds"}, {})[0]
    assert close["mttd_min"] is None and close["mttr_min"] is None and close["minutes"] == 60.0


def test_an_unmeasured_source_is_left_exactly_as_it_was() -> None:
    rows: list[dict[str, Any]] = []
    _apply(rows, 0, {"merge_train": ["MERGE_SLO"]}, set(), {})
    assert _apply(rows, 60, {}, set(), {}) == []  # neither red nor healthy: not measured
    assert "merge_train" in il.open_incidents(rows)


def test_cause_change_human_cause_and_heal_credit() -> None:
    rows: list[dict[str, Any]] = []
    _apply(rows, 0, {"merge_train": ["MERGE_SLO"]}, set(), {})
    _apply(rows, 60, {"merge_train": ["BOX_LOGIN", "MERGE_SLO"]}, set(), {})
    close = _apply(rows, 120, {}, {"merge_train"}, {})[0]
    assert close["causes_seen"] == ["BOX_LOGIN", "MERGE_SLO"]
    assert close["human_needed"] is True and close["cleared_by"] == "human"
    rows2: list[dict[str, Any]] = []
    _apply(rows2, 0, {"merge_train": ["GATE_SILENT"]}, set(), {}, {"merge_train": "start_gate"})
    assert _apply(rows2, 30, {}, {"merge_train"}, {})[0]["cleared_by"] == "self_heal"


def test_sources_are_independent() -> None:
    rows: list[dict[str, Any]] = []
    _apply(rows, 0, {"slo:feeds": ["BREACHING"], "merge_train": ["MERGE_SLO"]}, set(), {})
    new = _apply(rows, 30, {"merge_train": ["MERGE_SLO"]}, {"slo:feeds"}, {})
    assert [(r["event"], r["source"]) for r in new] == [("close", "slo:feeds")]
    assert set(il.open_incidents(rows)) == {"merge_train"}


def test_summary_freeze_minutes_split_at_midnight_and_quantiles() -> None:
    rows: list[dict[str, Any]] = []
    lo = {"merge_train": _at(-10).isoformat()}
    _apply(rows, 0, {"merge_train": ["GATE_SILENT"]}, set(), lo)  # 23:00
    _apply(rows, 180, {}, {"merge_train"}, lo)  # 02:00
    _apply(rows, 540, {"merge_train": ["BOX_LOGIN"]}, set(), lo)  # 08:00, still open
    doc = il.summary(rows, _at(600))
    assert doc["merge_train_frozen_min_per_day"]["2026-11-10"] == 60.0
    assert doc["merge_train_frozen_min_per_day"]["2026-11-11"] == 180.0
    assert doc["closed_7d"] == 1 and doc["mttd_min"]["median"] == 10.0
    assert doc["open"][0]["human_needed"] is True


def _health(path: Path, now: datetime, findings: list[dict[str, str]]) -> None:
    path.write_text(json.dumps({"checked_at": now.isoformat(), "findings": findings}))


SHADOW = {"section": "SCHEDULED TASKS  (x)", "level": "PROBLEM",
          "message": "MT5-Shadow last run 11/11/2026 5:55:01 AM and returned 3"}  # fmt: skip


def test_run_reads_reports_and_lists_the_absent_ones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("LEDGER", "STATE", "REPORT", "MERGE_FLOW", "SLO_STATUS", "DESK_HEALTH"):
        monkeypatch.setattr(il, name, tmp_path / f"{name}.json")
    now = datetime.now(UTC)
    (tmp_path / "MERGE_FLOW.json").write_text(json.dumps(
        {"at": now.isoformat(), "verdict": "RED", "reasons": ["GATE_SILENT"],
         "heal": "schtasks /Run: rc 0"}))  # fmt: skip
    _health(tmp_path / "DESK_HEALTH.json", now,
            [SHADOW, {"section": "PYTHON", "level": "OK", "message": "py resolves"}])  # fmt: skip
    doc = il.run(now)
    assert doc["unmeasured"] == ["SLO_STATUS.json"]
    srcs = {o["source"] for o in doc["open"]}
    assert "merge_train" in srcs and any(
        s.startswith("desk:scheduled tasks:MT5-Shadow") for s in srcs
    )
    rows = il.read_rows((tmp_path / "LEDGER.json").read_text().splitlines())
    assert any(r["event"] == "heal" for r in rows)
    # the same finding with a new timestamp is the same incident, never a second one
    later = {**SHADOW, "message": "MT5-Shadow last run 11/11/2026 6:55:01 AM and returned 3"}
    _health(tmp_path / "DESK_HEALTH.json", now, [later])
    assert il.run(now + timedelta(minutes=60))["appended"] == 0


def test_a_stale_report_is_unmeasured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("LEDGER", "STATE", "REPORT", "MERGE_FLOW", "SLO_STATUS", "DESK_HEALTH"):
        monkeypatch.setattr(il, name, tmp_path / f"{name}.json")
    now = datetime.now(UTC)
    (tmp_path / "MERGE_FLOW.json").write_text(json.dumps(
        {"at": (now - timedelta(hours=5)).isoformat(), "verdict": "GREEN"}))  # fmt: skip
    assert "MERGE_FLOW.json" in il.run(now)["unmeasured"]


def test_human_only_set_is_exact() -> None:
    assert frozenset({"BOX_LOGIN", "ROOT_PIN"}) == il.HUMAN_ONLY


def test_it_is_an_hourly_core_leg_and_published() -> None:
    root = Path(__file__).resolve().parents[2]
    hc = (root / "desks/mt5/research/hourly_cycle.py").read_text(encoding="utf-8")
    assert '"box_state_freshness", "desk_health", "incident_ledger",' in hc
    assert hc.index('"desk_health", "scripts/check_desk_health.py"') < hc.index(
        '"incident_ledger", "scripts/incident_ledger.py"')  # fmt: skip
    for f in ("libs/ops/release.py", "desks/mt5/mt5desk/release_identity.py",
              "desks/mt5/scripts/sync_shadow_to_git.ps1"):  # fmt: skip
        assert "desks/mt5/reports/INCIDENTS.json" in (root / f).read_text(encoding="utf-8")
    gi = (root / ".gitignore").read_text(encoding="utf-8")
    assert "!desks/mt5/reports/INCIDENTS.json" in gi
    assert "desks/mt5/data/incident_ledger.jsonl" in gi
    assert '"MT5-HourlyCore (incident ledger)"' in (root / "ops/organ_contract.py").read_text()
