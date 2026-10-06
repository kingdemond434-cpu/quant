import sqlite3

import pytest

from libs.moat import registry


def test_failed_schema_initialization_closes_its_owned_connection(tmp_path, monkeypatch):
    connection = sqlite3.connect(tmp_path / "registry.sqlite")
    monkeypatch.setattr(registry, "_restore_if_absent", lambda: False)
    monkeypatch.setattr(registry.sqlite3, "connect", lambda *args, **kwargs: connection)

    def fail(_connection):
        raise RuntimeError("schema initialization failed")

    monkeypatch.setattr(registry, "_evolve", fail)
    try:
        with pytest.raises(RuntimeError, match="schema initialization failed"):
            registry.connect()
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")
    finally:
        connection.close()
