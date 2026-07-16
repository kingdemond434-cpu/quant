"""Fixtures for cross-stage integration tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from migrations import MIGRATIONS

from libs.store.connection import Database
from libs.store.migrations import run_migrations


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database(tmp_path / "sor.sqlite")
    run_migrations(database, MIGRATIONS)
    yield database
    database.close()
