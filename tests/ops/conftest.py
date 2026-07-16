"""Fixtures for the ops/DR test suite."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from migrations import MIGRATIONS

from libs.store.connection import Database
from libs.store.migrations import run_migrations


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "sor.sqlite"


@pytest.fixture
def db(db_path: Path) -> Iterator[Database]:
    database = Database(db_path)
    run_migrations(database, MIGRATIONS)
    yield database
    database.close()
