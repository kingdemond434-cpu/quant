"""Tests for config-version history."""

from __future__ import annotations

from libs.core.config import hash_config
from libs.store.config_versions import (
    get_config_version,
    list_config_versions,
    record_config_version,
)
from libs.store.connection import Database


def test_record_and_get(db: Database) -> None:
    config = {"strategy": "gold_trend", "lookback": 50}
    version = record_config_version(db, config, environment="dev", note="first")
    assert version.config_hash == hash_config(config)
    assert version.content == config
    assert get_config_version(db, version.config_hash) == version


def test_record_is_idempotent_on_hash(db: Database) -> None:
    config = {"a": 1}
    first = record_config_version(db, config)
    second = record_config_version(db, config)
    assert first.id == second.id
    assert len(list_config_versions(db)) == 1


def test_distinct_configs_distinct_rows(db: Database) -> None:
    record_config_version(db, {"a": 1})
    record_config_version(db, {"a": 2})
    assert len(list_config_versions(db)) == 2
