from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import scripts.verify_deployment as V


def _systemctl_fixture(
    *,
    system_enabled: str = "disabled",
    system_active: str | None = None,
    user_enabled: str = "disabled",
    user_active: str | None = None,
):
    resolved_system_active = system_active or (
        "active" if system_enabled.startswith("enabled") else "inactive"
    )
    resolved_user_active = user_active or (
        "active" if user_enabled.startswith("enabled") else "inactive"
    )

    def fake(*args: str) -> str:
        if args == ("--version",):
            return "systemd 257"
        if args == ("is-enabled", "quant-midnight-frontier.timer"):
            return system_enabled
        if args == ("is-active", "quant-midnight-frontier.timer"):
            return resolved_system_active
        if args == ("--user", "is-enabled", "quant-midnight-frontier.timer"):
            return user_enabled
        if args == ("--user", "is-active", "quant-midnight-frontier.timer"):
            return resolved_user_active
        if args[0] in {"is-enabled", "is-active"}:
            return "enabled" if args[0] == "is-enabled" else "active"
        raise AssertionError(f"unexpected systemctl arguments: {args!r}")

    return fake


def _midnight_unit(rows: list[dict]) -> dict:
    return next(row for row in rows if row["unit"] == "quant-midnight-frontier.timer")


def _write_status(root: Path, *, updated_at: datetime, **overrides: object) -> Path:
    payload: dict[str, object] = {
        "updated_at": updated_at.isoformat(),
        "status": V.MIDNIGHT_SUCCESS,
        "reason": "completed, checkpointed and transferred",
        "controller_rc": 0,
        "pipeline_rc": 0,
        "persistent_workers_controller_independent": True,
    }
    payload.update(overrides)
    path = root / V.MIDNIGHT_STATUS
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload), "utf-8")
    return path


def _midnight_production(rows: list[dict]) -> dict:
    return next(row for row in rows if row["artifact"] == V.MIDNIGHT_STATUS)


def test_midnight_timer_is_required_and_system_scope_satisfies_it(monkeypatch) -> None:
    assert "quant-midnight-frontier.timer" in V.REQUIRED_UNITS
    monkeypatch.setattr(V, "_systemctl", _systemctl_fixture(system_enabled="enabled"))
    monkeypatch.setattr(
        V, "_loginctl", lambda *args: pytest.fail(f"loginctl should not be needed: {args!r}")
    )

    row = _midnight_unit(V.check_units())

    assert row["state"] == "OK"
    assert row["scope"] == "system"


def test_persistent_user_scope_satisfies_midnight_timer(monkeypatch) -> None:
    monkeypatch.setattr(V, "_systemctl", _systemctl_fixture(user_enabled="enabled"))
    monkeypatch.setattr(V, "_loginctl", lambda *args: "yes")

    row = _midnight_unit(V.check_units())

    assert row["state"] == "OK"
    assert row["scope"] == "user"
    assert row["user_linger"] == "yes"


def test_user_timer_without_linger_is_not_claimed_persistent(monkeypatch) -> None:
    monkeypatch.setattr(V, "_systemctl", _systemctl_fixture(user_enabled="enabled"))
    monkeypatch.setattr(V, "_loginctl", lambda *args: "no")

    row = _midnight_unit(V.check_units())

    assert row["state"] == "NOT-ENABLED"
    assert row["scope"] == "none"
    assert "linger=yes" in row["why"]


@pytest.mark.parametrize(
    ("system_enabled", "system_active", "user_enabled", "user_active"),
    [
        ("enabled", "inactive", "disabled", "inactive"),
        ("disabled", "inactive", "enabled", "inactive"),
    ],
)
def test_enabled_but_inactive_midnight_timer_fails_verification(
    monkeypatch,
    system_enabled: str,
    system_active: str,
    user_enabled: str,
    user_active: str,
) -> None:
    monkeypatch.setattr(
        V,
        "_systemctl",
        _systemctl_fixture(
            system_enabled=system_enabled,
            system_active=system_active,
            user_enabled=user_enabled,
            user_active=user_active,
        ),
    )
    monkeypatch.setattr(V, "_loginctl", lambda *args: "yes")

    row = _midnight_unit(V.check_units())

    assert row["state"] == "NOT-ENABLED"
    assert row["scope"] == "none"
    assert "active='inactive'" in row["why"]


def test_midnight_freshness_uses_embedded_updated_at_not_mtime(
    tmp_path: Path, monkeypatch
) -> None:
    now = datetime(2026, 8, 15, 12, tzinfo=UTC)
    path = _write_status(tmp_path, updated_at=now - timedelta(hours=1))
    ancient = (now - timedelta(days=10)).timestamp()
    os.utime(path, (ancient, ancient))
    monkeypatch.setattr(V, "ROOT", tmp_path)
    monkeypatch.setattr(V, "_now_epoch", lambda: now.timestamp())

    row = _midnight_production(V.check_production())

    assert row["state"] == "RUNNING"
    assert row["age_h"] == pytest.approx(1.0)


def test_fresh_mtime_cannot_hide_stale_embedded_midnight_event(
    tmp_path: Path, monkeypatch
) -> None:
    now = datetime(2026, 8, 15, 12, tzinfo=UTC)
    _write_status(tmp_path, updated_at=now - timedelta(hours=31))
    monkeypatch.setattr(V, "ROOT", tmp_path)
    monkeypatch.setattr(V, "_now_epoch", lambda: now.timestamp())

    row = _midnight_production(V.check_production())

    assert row["state"] == "STALE"
    assert row["age_h"] == pytest.approx(31.0)


@pytest.mark.parametrize(
    ("overrides", "needle"),
    [
        ({"status": "AUTH_REQUIRED"}, "AUTH_REQUIRED"),
        ({"controller_rc": 7}, "controller_rc=7"),
        ({"pipeline_rc": 9}, "pipeline_rc=9"),
        ({"persistent_workers_controller_independent": False}, "is not true"),
    ],
)
def test_fresh_status_is_not_success_without_successful_full_cycle(
    tmp_path: Path, monkeypatch, overrides: dict[str, object], needle: str
) -> None:
    now = datetime(2026, 8, 15, 12, tzinfo=UTC)
    _write_status(tmp_path, updated_at=now - timedelta(minutes=5), **overrides)
    monkeypatch.setattr(V, "ROOT", tmp_path)
    monkeypatch.setattr(V, "_now_epoch", lambda: now.timestamp())

    row = _midnight_production(V.check_production())

    assert row["state"] == "FAILED"
    assert needle in row["why"]


def test_invalid_embedded_timestamp_fails_even_when_file_is_fresh(
    tmp_path: Path, monkeypatch
) -> None:
    now = datetime(2026, 8, 15, 12, tzinfo=UTC)
    path = _write_status(tmp_path, updated_at=now)
    payload = json.loads(path.read_text("utf-8"))
    payload["updated_at"] = "not-a-time"
    path.write_text(json.dumps(payload), "utf-8")
    monkeypatch.setattr(V, "ROOT", tmp_path)
    monkeypatch.setattr(V, "_now_epoch", lambda: now.timestamp())

    row = _midnight_production(V.check_production())

    assert row["state"] == "INVALID"
    assert row["age_h"] is None
    assert "invalid updated_at" in row["why"]


def test_missing_midnight_status_fails_until_one_full_cycle_completes(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(V, "ROOT", tmp_path)

    row = _midnight_production(V.check_production())

    assert row["state"] == "MISSING"
    assert "never written" in row["why"]


def test_failed_semantic_status_makes_deployment_incomplete(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(V, "REPORT", tmp_path / "deployment.json")
    monkeypatch.setattr(V, "check_units", lambda: [])
    monkeypatch.setattr(V, "check_production", lambda: [{"state": "FAILED"}])
    monkeypatch.setattr(V, "check_tape", lambda: [])
    monkeypatch.setattr(V.sys, "argv", ["verify_deployment.py", "--json"])

    rc = V.main()

    assert rc == 1
    report = json.loads(V.REPORT.read_text("utf-8"))
    assert report["verdict"] == "INCOMPLETE"
