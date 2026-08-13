"""THE LIVE-GUARD PAGER WAS WELDED ON FOR AS LONG AS IT EXISTED (R0399).

`run_alerts._checks` read `live_guard.json`'s age from `lg.get("generated", "1970-01-01...")`, and
that file has never carried a `generated` key -- `run_live_guard.py` stamps `ts`. So the 1970
default was taken on every run, the age came out at ~56 years, and `live_guard_dead` fired on 100%
of runs. Measured on the box 2026-08-13: "live guard stale 29776345min (cadence 5min)" three
minutes after the guard wrote the file, with the key sitting in `_paged`.

A pager that fires always carries zero information (L1.43) and gets acked into silence, so the one
signal it exists to carry -- the size governor dead while the executor fail-opens to FULL SIZE --
was already lost. These tests pin BOTH ends: it must go quiet when the guard is alive, and it must
still fire when the guard is genuinely stale. A fix that only silenced it would be worse than the
bug, because it would look like a repair while deleting the rail.
"""
from __future__ import annotations

import importlib.util
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_SRC = Path(__file__).resolve().parents[2] / "scripts/run_alerts.py"


def _module() -> Any:
    spec = importlib.util.spec_from_file_location("run_alerts_under_test", _SRC)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, guard: dict | None) -> set[str]:
    """`_checks` reads cwd-relative paths, so an empty tmp cwd isolates it from box state."""
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    if guard is not None:
        (tmp_path / "data/live_guard.json").write_text(json.dumps(guard), "utf-8")
    monkeypatch.chdir(tmp_path)
    return {k for k, _msg in _module()._checks()}


def test_a_LIVE_guard_does_not_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The regression. A guard that wrote its file seconds ago is ALIVE, and the pager that
    exists to notice it dying must say nothing."""
    keys = _keys(tmp_path, monkeypatch, {"ts": datetime.now(tz=UTC).isoformat(), "stage": "S0"})
    assert "live_guard_dead" not in keys
    assert "live_guard_missing" not in keys


def test_a_GENUINELY_STALE_guard_still_pages(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    """The rail itself -- silencing the noise must not silence the signal. Cadence is 5min and the
    threshold 15min, so a guard stamped 2h ago is dead by any reading."""
    stale = (datetime.now(tz=UTC) - timedelta(hours=2)).isoformat()
    assert "live_guard_dead" in _keys(tmp_path, monkeypatch, {"ts": stale, "stage": "S0"})


def test_an_EPOCH_stamped_guard_is_measured_not_defaulted(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert "live_guard_dead" not in _keys(tmp_path, monkeypatch, {"ts": time.time()})
    assert "live_guard_dead" in _keys(tmp_path, monkeypatch, {"ts": time.time() - 7200})


def test_an_ABSENT_guard_pages_as_MISSING(tmp_path: Path,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    keys = _keys(tmp_path, monkeypatch, None)
    assert "live_guard_missing" in keys and "live_guard_dead" not in keys


def test_a_guard_with_NO_PARSEABLE_STAMP_is_UNMEASURABLE_not_fine(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UNMEASURED is a real answer (L1.28a) and must never resolve to a clean verdict. The
    tempting fix here is an mtime fallback, which would re-open the exact deploy-lies-fresh hole
    the check was built to close -- so an unstamped guard pages rather than passing."""
    keys = _keys(tmp_path, monkeypatch, {"stage": "S0", "measured": False})
    assert "live_guard_missing" in keys
