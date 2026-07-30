"""Miner runway doctor -- 6 of 7 frontier seats had ZERO runs ever while being 'monitored'.

The doctor's value is the DIAGNOSIS, so these tests pin each status against a fixture tree, and
above all pin the two properties that make it useful: creds-missing is reported instead of
never-ran when credentials are absent (cause, not symptom), and no secret VALUE is ever read or
printed.
"""
from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path
from types import ModuleType

import pytest

_SRC = Path(__file__).resolve().parents[2] / "scripts/check_miner_runway.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_miner_runway_probe", _SRC)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """A minimal fake repo with one seat, wired end to end."""
    mod = _load()
    (tmp_path / "ops").mkdir()
    (tmp_path / "data/cro_ai_logs").mkdir(parents=True)
    (tmp_path / "data/secrets").mkdir(parents=True)
    (tmp_path / "ops/seat_prompt.txt").write_text("mission text", "utf-8")
    (tmp_path / "ops/run_seat.sh").write_text("#!/bin/sh\necho dig\n", "utf-8")
    (tmp_path / "ops/quant-seat.service").write_text(
        "[Service]\nExecStart=/bin/bash /repo/ops/run_seat.sh\n", "utf-8")
    monkeypatch.setattr(mod, "_ROOT", tmp_path)
    monkeypatch.setattr(mod, "_LOGDIR", tmp_path / "data/cro_ai_logs")
    monkeypatch.setattr(mod, "_OUT", tmp_path / "data/miner_runway.json")
    monkeypatch.setattr(mod, "_CRED_HOME", tmp_path / "no-home-creds.json")
    monkeypatch.setattr(mod, "_SEATS", {
        "seat": ("ops/seat_prompt.txt", "ops/run_seat.sh", "seat_*.log", 36.0)})
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    return mod


def _arm(tmp_path: Path) -> None:
    (tmp_path / "data/secrets/claude_oauth_token").write_text("sk-ant-oat01-SECRETVALUE", "utf-8")


def test_creds_missing_beats_never_ran(tree: ModuleType, tmp_path: Path) -> None:
    # THE DIAGNOSIS THAT MATTERS: with no credential the seat CANNOT run, so reporting
    # 'never-ran' would name the symptom and hide the one human step that fixes 11 seats.
    rep = tree.audit()
    assert rep["seats"]["seat"]["status"] == "creds-missing"
    assert rep["blockers"] and rep["blockers"][0]["blast_radius"] == 1
    assert "setup_brain_token" in rep["blockers"][0]["human_step"]


def test_never_ran_once_creds_present(tree: ModuleType, tmp_path: Path) -> None:
    _arm(tmp_path)
    rep = tree.audit()
    assert rep["seats"]["seat"]["status"] == "never-ran"     # runway complete, zero output
    assert rep["seats"]["seat"]["creds"] is True
    assert rep["blockers"] == []


def test_ok_when_a_fresh_log_exists(tree: ModuleType, tmp_path: Path) -> None:
    _arm(tmp_path)
    (tmp_path / "data/cro_ai_logs/seat_20260729T1200.log").write_text("x" * 2000, "utf-8")
    rep = tree.audit()
    assert rep["seats"]["seat"]["status"] == "ok"
    assert rep["n_bad"] == 0


def test_stale_when_the_log_is_old(tree: ModuleType, tmp_path: Path) -> None:
    _arm(tmp_path)
    log = tmp_path / "data/cro_ai_logs/seat_old.log"
    log.write_text("x" * 2000, "utf-8")
    old = time.time() - 80 * 3600
    import os
    os.utime(log, (old, old))
    rep = tree.audit()
    assert rep["seats"]["seat"]["status"] == "stale"          # ran before -> runtime failure
    assert rep["seats"]["seat"]["age_h"] > 36.0


def test_not_scheduled_when_no_unit_names_the_runner(tree: ModuleType, tmp_path: Path) -> None:
    _arm(tmp_path)
    (tmp_path / "ops/quant-seat.service").unlink()
    rep = tree.audit()
    assert rep["seats"]["seat"]["status"] == "not-scheduled"   # nothing would ever invoke it


def test_manifest_alone_counts_as_scheduled(tree: ModuleType, tmp_path: Path) -> None:
    _arm(tmp_path)
    (tmp_path / "ops/quant-seat.service").unlink()
    (tmp_path / "ops/crontab.manifest").write_text("0 5 * * * bash ops/run_seat.sh\n", "utf-8")
    rep = tree.audit()
    assert rep["seats"]["seat"]["status"] == "never-ran"       # scheduled, just hasn't fired


def test_missing_prompt_detected(tree: ModuleType, tmp_path: Path) -> None:
    _arm(tmp_path)
    (tmp_path / "ops/seat_prompt.txt").write_text("", "utf-8")   # empty == missing
    assert tree.audit()["seats"]["seat"]["status"] == "missing-prompt"


def test_no_secret_value_is_ever_emitted(tree: ModuleType, tmp_path: Path) -> None:
    _arm(tmp_path)
    rep = tree.audit()
    blob = json.dumps(rep)
    assert "SECRETVALUE" not in blob and "sk-ant" not in blob
    assert rep["creds_present"] is True                        # existence only


def test_report_only_never_fails_the_cron(tree: ModuleType, tmp_path: Path,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["check_miner_runway.py", "--report-only"])
    assert tree.main() == 0                                    # bad seats, but exit 0 by request
    monkeypatch.setattr("sys.argv", ["check_miner_runway.py"])
    assert tree.main() == 1                                    # strict mode pages


def test_real_repo_seats_all_have_prompt_and_runner() -> None:
    """Against the ACTUAL repo: every configured seat's prompt and runner must exist. This is the
    regression test that fails the day a seat is renamed and its wiring silently rots."""
    mod = _load()
    rep = mod.audit()
    for seat, row in rep["seats"].items():
        assert row["prompt"], f"{seat}: prompt file missing or empty"
        assert row["runner"], f"{seat}: runner script missing"
        assert row["unit"], f"{seat}: nothing in-repo schedules it"
