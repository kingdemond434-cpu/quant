"""Tests for the configuration system."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.core.helpers import write_config_dir

from libs.core.config import (
    Settings,
    clear_settings_cache,
    deep_merge,
    ensure_directories,
    get_settings,
    hash_config,
    load_settings,
)
from libs.core.enums import Environment, LogLevel
from libs.core.errors import ConfigError

BASE = """
logging:
  level: INFO
  json: true
  redact_keys: [password, secret]
reproducibility:
  default_seed: 12345
  require_clean_git: false
paths: {}
"""

DEV = """
environment: dev
logging:
  level: DEBUG
  json: false
"""


def _config_dir(tmp_path: Path) -> Path:
    return write_config_dir(tmp_path / "config", base=BASE, env_name="dev", env_yaml=DEV)


def test_deep_merge_is_recursive_and_pure() -> None:
    base = {"a": 1, "nested": {"x": 1, "y": 2}}
    overlay = {"nested": {"y": 20, "z": 30}, "b": 2}
    merged = deep_merge(base, overlay)
    assert merged == {"a": 1, "b": 2, "nested": {"x": 1, "y": 20, "z": 30}}
    assert base == {"a": 1, "nested": {"x": 1, "y": 2}}  # unmutated


def test_load_merges_base_and_environment(tmp_path: Path) -> None:
    settings = load_settings("dev", root=tmp_path, config_dir=_config_dir(tmp_path))
    assert settings.environment is Environment.DEV
    # dev overlay wins for level/json; base provides redact_keys.
    assert settings.logging.level is LogLevel.DEBUG
    assert settings.logging.emit_json is False
    assert settings.logging.redact_keys == ["password", "secret"]


def test_environment_variable_overrides_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QP_LOGGING__LEVEL", "ERROR")
    settings = load_settings("dev", root=tmp_path, config_dir=_config_dir(tmp_path))
    assert settings.logging.level is LogLevel.ERROR
    # untouched nested field survives the partial override
    assert settings.logging.emit_json is False


def test_explicit_overrides_beat_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QP_LOGGING__LEVEL", "ERROR")
    settings = load_settings(
        "dev",
        root=tmp_path,
        config_dir=_config_dir(tmp_path),
        overrides={"logging": {"level": "WARNING"}},
    )
    assert settings.logging.level is LogLevel.WARNING


def test_env_var_selects_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QP_ENV", "dev")
    settings = load_settings(root=tmp_path, config_dir=_config_dir(tmp_path))
    assert settings.environment is Environment.DEV


def test_unknown_key_is_rejected(tmp_path: Path) -> None:
    bad_dir = write_config_dir(
        tmp_path / "config",
        base=BASE + "\nunknown_key: 1\n",
        env_name="dev",
        env_yaml=DEV,
    )
    with pytest.raises(ConfigError):
        load_settings("dev", root=tmp_path, config_dir=bad_dir)


def test_missing_file_raises(tmp_path: Path) -> None:
    (tmp_path / "config").mkdir()
    with pytest.raises(ConfigError):
        load_settings("dev", root=tmp_path, config_dir=tmp_path / "config")


def test_non_utc_timezone_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_settings(
            "dev",
            root=tmp_path,
            config_dir=_config_dir(tmp_path),
            overrides={"timezone": "Europe/London"},
        )


def test_paths_derived_from_root(tmp_path: Path) -> None:
    settings = load_settings("dev", root=tmp_path, config_dir=_config_dir(tmp_path))
    assert settings.paths.root == tmp_path.resolve()
    assert settings.paths.lake_dir == tmp_path.resolve() / "lake"
    assert settings.paths.data_dir == tmp_path.resolve() / "data"
    assert settings.paths.artifacts_dir == tmp_path.resolve() / "artifacts"
    assert settings.paths.logs_dir == tmp_path.resolve() / "logs"


def test_ensure_directories_creates_paths(tmp_path: Path) -> None:
    settings = load_settings("dev", root=tmp_path, config_dir=_config_dir(tmp_path))
    ensure_directories(settings)
    assert settings.paths.lake_dir.is_dir()
    assert settings.paths.data_dir.is_dir()
    assert settings.paths.artifacts_dir.is_dir()
    assert settings.paths.logs_dir.is_dir()


def test_real_project_config_loads() -> None:
    # The shipped config/ must load for every environment.
    for env in ("dev", "live", "test"):
        settings = load_settings(env)
        assert settings.environment.value == env
        assert settings.timezone == "UTC"


def test_get_settings_is_cached() -> None:
    clear_settings_cache()
    first = get_settings("dev")
    second = get_settings("dev")
    assert first is second
    clear_settings_cache()
    assert get_settings("dev") is not first


def test_hash_config_is_deterministic_and_sensitive() -> None:
    a = {"x": 1, "y": [1, 2, 3]}
    b = {"y": [1, 2, 3], "x": 1}  # different insertion order, same content
    assert hash_config(a) == hash_config(b)
    assert hash_config({"x": 1}) != hash_config({"x": 2})


def test_hash_config_accepts_model_and_none(tmp_path: Path) -> None:
    settings = load_settings("dev", root=tmp_path, config_dir=_config_dir(tmp_path))
    assert isinstance(hash_config(settings), str)
    assert len(hash_config(None)) == 64  # sha256 hex


def test_settings_is_a_basesettings_instance(tmp_path: Path) -> None:
    settings = load_settings("dev", root=tmp_path, config_dir=_config_dir(tmp_path))
    assert isinstance(settings, Settings)
