"""The box's Claude Code settings check (read-only) and the person-only repair (2026-11-13)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops"))

import claude_settings_health as csh  # noqa: E402

REPAIR = ROOT / "ops" / "bridge" / "Repair-ClaudeSettings.ps1"
GOOD = (
    '{"permissions": {"defaultMode": "bypassPermissions", "allow": ["Bash(*)"]},'
    ' "env": {"K": "s3cr3t"}}'
)


@pytest.mark.parametrize(
    ("text", "want"),
    [
        (GOOD[1:], "MISSING_LEADING_BRACE"),  # the 2026-11-13 box file
        (GOOD[:-1], "MISSING_TRAILING_BRACE"),
        ("\ufeff" + GOOD, "UTF8_BOM"),
        ('{"a": 1, "b": [1, 2,]}', "TRAILING_COMMA"),
        ("not json at all", "UNKNOWN"),
    ],
)
def test_diagnosis_names_the_one_exact_repair(text: str, want: str) -> None:
    assert csh.diagnose(text) == want


def test_a_broken_file_is_invalid_with_position_and_diagnosis(tmp_path: Path) -> None:
    f = tmp_path / "settings.json"
    f.write_text(GOOD[1:], encoding="utf-8")
    row = csh.inspect_file(f, "user:Administrator")
    assert row["verdict"] == "INVALID_JSON"
    assert row["diagnosis"] == "MISSING_LEADING_BRACE"
    assert row["line"] == 1 and isinstance(row["column"], int)


def test_an_ok_file_reports_mode_and_counts_never_values(tmp_path: Path) -> None:
    f = tmp_path / "settings.json"
    f.write_text(GOOD, encoding="utf-8")
    row = csh.inspect_file(f, "user:Administrator")
    assert row["verdict"] == "OK"
    assert row["default_mode"] == "bypassPermissions" and row["n_allow"] == 1
    assert row["keys"] == ["env", "permissions"]
    assert "s3cr3t" not in json.dumps(row) and "Bash(*)" not in json.dumps(row)


def test_not_an_object_is_a_fault(tmp_path: Path) -> None:
    f = tmp_path / "settings.json"
    f.write_text("[1, 2]", encoding="utf-8")
    assert csh.inspect_file(f, "managed")["verdict"] == "NOT_OBJECT"


def _layout(tmp_path: Path, user_text: str) -> tuple[Path, Path, Path]:
    users = tmp_path / "Users"
    (users / "Administrator" / ".claude").mkdir(parents=True)
    (users / "Administrator" / ".claude" / "settings.json").write_text(user_text, encoding="utf-8")
    checkout = tmp_path / "bridge"
    (checkout / ".claude").mkdir(parents=True)
    (checkout / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
    return users, checkout, tmp_path / "hb.json"


def test_check_is_broken_when_the_user_file_does_not_parse(tmp_path: Path) -> None:
    users, checkout, hb = _layout(tmp_path, GOOD[1:])
    rep = csh.check(
        users_root=users, managed=(tmp_path / "none.json",), checkout=checkout, heartbeat=hb
    )
    assert rep["status"] == "BROKEN"
    assert rep["faults"] == [str(users / "Administrator" / ".claude" / "settings.json")]
    assert "Repair-ClaudeSettings.ps1" in rep["repair"]
    assert str(tmp_path / "none.json") in rep["absent"]


def test_a_file_changed_after_the_rc_server_started_needs_a_restart(tmp_path: Path) -> None:
    users, checkout, hb = _layout(tmp_path, GOOD)
    started = datetime.now(UTC) - timedelta(hours=1)
    hb.write_text(json.dumps({"server_started_at": started.isoformat()}), encoding="utf-8")
    rep = csh.check(users_root=users, managed=(), checkout=checkout, heartbeat=hb)
    assert rep["status"] == "NEEDS_RC_RESTART"
    hb.write_text(
        json.dumps({"server_started_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat()})
    )
    assert (
        csh.check(users_root=users, managed=(), checkout=checkout, heartbeat=hb)["status"] == "OK"
    )


def test_the_checker_never_writes_a_settings_file() -> None:
    code = (ROOT / "ops" / "claude_settings_health.py").read_text(encoding="utf-8")
    # its only write is its own report
    writes = re.findall(r"(\w+)\.write_(?:text|bytes)\(", code)
    assert writes == ["OUT"]
    assert "os.replace" not in code and "shutil" not in code


def test_process_health_carries_the_check_and_is_not_applicable_off_windows() -> None:
    sys.path.insert(0, str(ROOT / "ops"))
    import process_health

    code = (ROOT / "ops" / "process_health.py").read_text(encoding="utf-8")
    assert '"claude_settings": settings' in code and 'settings.get("status") == "BROKEN"' in code
    if os.name != "nt":
        assert process_health.claude_settings()["status"] == "NOT_APPLICABLE"


def test_the_repair_is_a_persons_tool_only() -> None:
    code = REPAIR.read_text(encoding="utf-8")
    assert "$env:CLAUDECODE" in code and "$env:CLAUDE_CODE_ENTRYPOINT" in code
    assert "UserInteractive" in code and "SessionId -eq 0" in code
    assert 'Read-Host "Type REPAIR to apply"' in code
    assert code.index("Read-Host") < code.index("WriteAllText")
    assert code.index("Copy-Item -LiteralPath $full -Destination $backup") < code.index(
        "WriteAllText"
    )
    # nothing schedules or installs it
    for rel in (
        "desks/mt5/ops/box_tasks.manifest",
        "ops/box",
        "ops/bridge",
        "desks/mt5/scripts",
        ".github",
    ):
        p = ROOT / rel
        files = (
            [p] if p.is_file() else [f for f in p.rglob("*") if f.is_file()] if p.exists() else []
        )
        for f in files:
            if f == REPAIR:
                continue
            try:
                txt = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            assert "Repair-ClaudeSettings" not in txt, f


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="pwsh not installed")
def test_the_repair_puts_back_the_brace_keeps_a_backup_and_refuses_in_a_claude_session(
    tmp_path: Path,
) -> None:
    d = tmp_path / "u" / ".claude"
    d.mkdir(parents=True)
    f = d / "settings.json"
    f.write_text(GOOD[1:], encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")}
    refused = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(REPAIR), "-Path", str(f)],
        input="REPAIR\n",
        text=True,
        capture_output=True,
        env={**env, "CLAUDECODE": "1"},
        timeout=120,
    )
    assert refused.returncode == 3 and f.read_text(encoding="utf-8") == GOOD[1:]
    declined = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(REPAIR), "-Path", str(f)],
        input="no\n",
        text=True,
        capture_output=True,
        env=env,
        timeout=120,
    )
    assert declined.returncode == 1 and f.read_text(encoding="utf-8") == GOOD[1:]
    done = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(REPAIR), "-Path", str(f)],
        input="REPAIR\n",
        text=True,
        capture_output=True,
        env=env,
        timeout=120,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert json.loads(f.read_text(encoding="utf-8")) == json.loads(GOOD)
    assert [p.read_text(encoding="utf-8") for p in d.glob("settings.json.bak-*")] == [GOOD[1:]]
    other = tmp_path / "notclaude" / "x.json"
    other.parent.mkdir()
    other.write_text("{", encoding="utf-8")
    wrong = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(REPAIR), "-Path", str(other)],
        input="REPAIR\n",
        text=True,
        capture_output=True,
        env=env,
        timeout=120,
    )
    assert wrong.returncode == 2


def test_the_published_projection_carries_no_path_user_or_position(tmp_path: Path) -> None:
    """Audit 2026-11-13 MF1/MF2: process_health.json is published and the repo is public."""
    users, checkout, hb = _layout(tmp_path, GOOD[1:])
    (users / "jane.doe" / ".claude").mkdir(parents=True)
    (users / "jane.doe" / ".claude" / "settings.local.json").write_text("[1]", encoding="utf-8")
    rep = csh.check(users_root=users, managed=(), checkout=checkout, heartbeat=hb)
    pub = csh.publishable(rep)
    assert tuple(pub) == csh.PUBLISHED_KEYS
    assert pub["status"] == "BROKEN" and len(pub["faults"]) == 2
    for f in pub["faults"]:
        assert tuple(f) == csh.PUBLISHED_FAULT_KEYS
        assert f["scope"] in ("user", "managed", "project")
        for v in f.values():
            v = str(v)
            assert "/" not in v and "\\" not in v and not re.match(r"^[A-Za-z]:", v), v
            assert "Administrator" not in v and "jane" not in v
    text = json.dumps(pub)
    assert str(tmp_path) not in text and "line" not in text and "column" not in text
    assert "Expecting" not in text  # the parser's message stays local
    assert {f["file"] for f in pub["faults"]} == {"settings.json", "settings.local.json"}


def test_the_full_report_is_written_only_where_git_ignores_it() -> None:
    assert csh.OUT == ROOT / "data" / "claude_settings_health.json"
    got = subprocess.run(["git", "check-ignore", "-q", str(csh.OUT)], cwd=ROOT, check=False)
    assert got.returncode == 0
    code = (ROOT / "ops" / "process_health.py").read_text(encoding="utf-8")
    assert "claude_settings_health.publishable(rep)" in code
