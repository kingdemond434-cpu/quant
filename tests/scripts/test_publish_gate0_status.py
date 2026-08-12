"""publish_gate0_status.py -- the VPS-visibility channel a Claude Code container needed.

MEASURED 2026-08-12: a fresh container has no SSH to the VPS (HTTPS-only egress) and data/ is
gitignored, box-local -- every "is Gate 0 ready" question this session asked was answerable only
by guessing or asking the principal to paste command output. dash.quanttt.xyz already serves
web/*.json over HTTPS (confirmed live: web/discovery.json and web/trade_forensics.json both
fetchable from a container with zero VPS access) -- nothing published Gate 0's own readiness
board through that channel. This organ closes that gap: republish, never recompute, with an
honest age stamp so a stale read is visibly stale rather than presented as current.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def mod(tmp_path: Path, monkeypatch):
    import importlib.util
    monkeypatch.chdir(tmp_path)
    spec = importlib.util.spec_from_file_location(
        "publish_gate0_status", _REPO / "scripts/publish_gate0_status.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _write_board(tmp_path: Path, board: dict, *, mtime: float | None = None) -> None:
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    p = tmp_path / "data/gate0_readiness.json"
    p.write_text(json.dumps(board), "utf-8")
    if mtime is not None:
        import os
        os.utime(p, (mtime, mtime))


def test_absent_source_is_unmeasured_not_zero(mod, tmp_path: Path) -> None:
    doc = mod.publish(root=tmp_path)
    assert doc["status"] == "UNMEASURED"
    assert doc["rows"] == []


def test_republishes_the_same_rows_it_was_given(mod, tmp_path: Path) -> None:
    board = {"gate": "S1 entry", "ready": False, "n_ready": 2, "n_criteria": 9,
             "desk_owes": ["ruin_rail_clear"], "principal_owes": ["keys_present"],
             "rows": [{"criterion": "keys_present", "status": "NOT-READY"}]}
    _write_board(tmp_path, board)
    doc = mod.publish(root=tmp_path)
    assert doc["status"] == "OK"
    assert doc["ready"] is False
    assert doc["rows"] == board["rows"], "must republish verbatim, never recompute a verdict"


def test_fresh_artifact_carries_no_stale_warning(mod, tmp_path: Path) -> None:
    now = datetime.now(tz=UTC)
    _write_board(tmp_path, {"rows": []}, mtime=now.timestamp())
    doc = mod.publish(root=tmp_path, now=now)
    assert doc["stale_warning"] is False
    assert doc["source_age_h"] is not None and doc["source_age_h"] < 1.0


def test_an_old_artifact_is_flagged_stale_not_presented_as_current(mod, tmp_path: Path) -> None:
    """THE EXACT FAILURE MODE THIS EXISTS TO PREVENT. Found live 2026-08-12: this container's own
    fossil data/gate0_readiness.json was 302.6h (12.6 days) old and would have read as a current,
    trustworthy READY verdict without this flag."""
    now = datetime.now(tz=UTC)
    old = now - timedelta(hours=300)
    _write_board(tmp_path, {"ready": True, "rows": []}, mtime=old.timestamp())
    doc = mod.publish(root=tmp_path, now=now)
    assert doc["stale_warning"] is True
    assert doc["source_age_h"] > 250


def test_writes_the_exact_path_the_dashboard_would_serve(mod) -> None:
    assert Path("web/gate0_status.json") == Path(mod._OUT)


def test_it_never_computes_a_new_readiness_criterion(mod) -> None:
    """Pure republish. Two independent implementations of 'is this criterion ready' is how they
    quietly disagree -- the exact bug class check_build_standard.py already had once this
    session (its own scheduling detector re-derived instead of reusing a shared source).

    Checked against the FUNCTION BODY only, not the module docstring -- the docstring legitimately
    explains why net_of_fees_positive motivated building this, which would trip a naive whole-file
    grep on its own explanation (the same string-marker trap this desk has hit before)."""
    import inspect
    body = inspect.getsource(mod.publish)
    for forbidden in ("s1_entry_met", "ruin_rail_clear =", "net_of_fees_positive ="):
        assert forbidden not in body


# ------------------------------------------------------------------ the running organ
def test_runs_as_a_cron_line_would_invoke_it() -> None:
    r = subprocess.run([sys.executable, str(_REPO / "scripts/publish_gate0_status.py")],
                       cwd=_REPO, capture_output=True, text=True, timeout=60)
    assert "ModuleNotFoundError" not in r.stderr


def test_the_organ_is_actually_scheduled() -> None:
    man = (_REPO / "ops/crontab.manifest").read_text("utf-8")
    scheduled = any("publish_gate0_status.py" in ln and ln[:1] in "0123456789*"
                    for ln in man.splitlines())
    assert scheduled, "a publisher nobody schedules is exactly the ORPHAN class this session found"
