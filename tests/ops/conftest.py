"""Fixtures for the ops/DR test suite."""

from __future__ import annotations

import importlib.util
from collections.abc import Iterator
from pathlib import Path

import pytest
from migrations import MIGRATIONS

from libs.store.connection import Database
from libs.store.migrations import run_migrations

#: CI-GATE TESTS ARE POSIX-ONLY AND MUST NOT BE COLLECTED ON WINDOWS (2026-09-12).
#:
#: `scripts/run_ci.py` takes its lock with fcntl, and `test_ci_gate_lock` imports fcntl directly.
#: Neither exists on Windows, so these four modules raise ModuleNotFoundError at IMPORT time --
#: before any in-module skip can run, which is why `pytest.importorskip` cannot save them and
#: `collect_ignore` is the only mechanism that works here.
#:
#: WHY IT MATTERED ENOUGH TO FIX. `pytest --co` is a PUSH GATE. Four Linux-only modules were
#: therefore holding the Windows trading box's code hostage: 24 commits sat unpushed behind a
#: collection error about a platform those tests were never meant to run on.
#:
#: SKIPPED, NOT WEAKENED. The CI gate runs on the Linux VPS, where fcntl exists and all four
#: modules collect and assert in full. Nothing here loosens an assertion; it records that the
#: platform cannot host them. If fcntl is ever present, they collect exactly as before.
collect_ignore: list[str] = []
if importlib.util.find_spec("fcntl") is None:
    collect_ignore += [
        "test_ci_gate_lock.py",
        "test_ci_gate_signal_death.py",
        "test_ci_gate_timeouts.py",
        "test_run_ci_attribution.py",
    ]


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "sor.sqlite"


@pytest.fixture
def db(db_path: Path) -> Iterator[Database]:
    database = Database(db_path)
    run_migrations(database, MIGRATIONS)
    yield database
    database.close()
