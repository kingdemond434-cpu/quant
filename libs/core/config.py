"""Configuration system: Pydantic settings with layered YAML + environment variables.

Precedence (highest first):

1. Explicit ``overrides=`` passed to :func:`load_settings`.
2. Environment variables (prefix ``QP_``, nested delimiter ``__``).
3. ``config/<environment>.yaml``.
4. ``config/base.yaml``.

The environment is selected by the ``QP_ENV`` variable (or the ``environment`` argument),
defaulting to ``dev``. Secrets never live here — see :mod:`libs.core.secrets`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from contextvars import ContextVar
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from libs.core.enums import Environment, LogLevel
from libs.core.errors import ConfigError

ENV_VAR = "QP_ENV"
ROOT_ENV_VAR = "QP_ROOT"
CONFIG_DIR_ENV_VAR = "QP_CONFIG_DIR"

# Carries the merged YAML layer into ``Settings`` construction as a low-priority source.
_yaml_layer: ContextVar[dict[str, Any] | None] = ContextVar("_yaml_layer", default=None)


# --------------------------------------------------------------------------- helpers


def find_project_root(start: Path | None = None) -> Path:
    """Walk upward from ``start`` (or this file) to the directory holding ``pyproject.toml``.

    Falls back to the current working directory if no marker is found.
    """
    here = (start or Path(__file__)).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return Path.cwd().resolve()


def deep_merge(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge ``overlay`` onto ``base`` without mutating either argument."""
    result: dict[str, Any] = dict(base)
    for key, value in overlay.items():
        existing = result.get(key)
        if isinstance(existing, Mapping) and isinstance(value, Mapping):
            result[key] = deep_merge(existing, value)
        else:
            result[key] = value
    return result


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file into a dict, returning ``{}`` for an empty file."""
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"config file {path} must contain a mapping at the top level")
    return data


def hash_config(config: Mapping[str, Any] | BaseModel | None) -> str:
    """Return a stable SHA-256 hex digest of a configuration object.

    Serializes to canonical JSON (sorted keys, ``str`` fallback for paths/enums/datetimes)
    so the same logical config always hashes identically. ``None`` hashes the empty object.
    """
    if config is None:
        payload: Any = {}
    elif isinstance(config, BaseModel):
        payload = config.model_dump(mode="json")
    elif isinstance(config, Mapping):
        payload = dict(config)
    else:  # pragma: no cover - defensive
        raise TypeError(f"cannot hash config of type {type(config)!r}")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- models


class Paths(BaseModel):
    """Filesystem layout. Everything is derived from ``root`` unless set explicitly."""

    model_config = ConfigDict(extra="forbid")

    root: Path
    config_dir: Path | None = None
    lake_dir: Path | None = None
    data_dir: Path | None = None
    artifacts_dir: Path | None = None
    logs_dir: Path | None = None

    @model_validator(mode="after")
    def _derive(self) -> Paths:
        root = self.root
        self.config_dir = self.config_dir or root / "config"
        self.lake_dir = self.lake_dir or root / "lake"
        self.data_dir = self.data_dir or root / "data"
        self.artifacts_dir = self.artifacts_dir or root / "artifacts"
        self.logs_dir = self.logs_dir or root / "logs"
        return self


class LoggingConfig(BaseModel):
    """Structured-logging configuration."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    level: LogLevel = LogLevel.INFO
    # YAML/env key is ``json``; the attribute avoids shadowing ``BaseModel.json``.
    emit_json: bool = Field(default=True, alias="json")
    include_caller: bool = False
    redact_keys: list[str] = Field(default_factory=list)

    @field_validator("redact_keys")
    @classmethod
    def _lowercase_keys(cls, value: list[str]) -> list[str]:
        return [k.lower() for k in value]


class ReproducibilityConfig(BaseModel):
    """Defaults for the reproducibility framework."""

    model_config = ConfigDict(extra="forbid")

    default_seed: int = 12345
    require_clean_git: bool = False

    @field_validator("default_seed")
    @classmethod
    def _non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("default_seed must be non-negative")
        return value


class _MappingSettingsSource(PydanticBaseSettingsSource):
    """A settings source that yields a pre-merged mapping (the YAML layer)."""

    def __init__(self, settings_cls: type[BaseSettings], data: Mapping[str, Any]) -> None:
        super().__init__(settings_cls)
        self._data = dict(data)

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        return self._data.get(field_name), field_name, False

    def __call__(self) -> dict[str, Any]:
        return self._data


class Settings(BaseSettings):
    """Resolved, validated platform configuration."""

    model_config = SettingsConfigDict(
        env_prefix="QP_",
        env_nested_delimiter="__",
        extra="forbid",
        case_sensitive=False,
    )

    environment: Environment = Environment.DEV
    paths: Paths
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    reproducibility: ReproducibilityConfig = Field(default_factory=ReproducibilityConfig)
    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def _utc_only(cls, value: str) -> str:
        if value != "UTC":
            raise ValueError("the platform operates in UTC only; timezone must be 'UTC'")
        return value

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        yaml_source = _MappingSettingsSource(settings_cls, _yaml_layer.get() or {})
        # init (explicit overrides) > env vars > dotenv > yaml layer > file secrets
        return (init_settings, env_settings, dotenv_settings, yaml_source, file_secret_settings)


# --------------------------------------------------------------------------- loading


def _resolve_environment(environment: str | Environment | None) -> Environment:
    if environment is not None:
        return Environment(environment)
    import os

    return Environment(os.environ.get(ENV_VAR, Environment.DEV.value))


def _resolve_config_dir(config_dir: Path | None, root: Path) -> Path:
    if config_dir is not None:
        return Path(config_dir)
    import os

    env_value = os.environ.get(CONFIG_DIR_ENV_VAR)
    return Path(env_value) if env_value else root / "config"


def _resolve_root(root: Path | None) -> Path:
    if root is not None:
        return Path(root).resolve()
    import os

    env_value = os.environ.get(ROOT_ENV_VAR)
    return Path(env_value).resolve() if env_value else find_project_root()


def load_settings(
    environment: str | Environment | None = None,
    *,
    root: Path | None = None,
    config_dir: Path | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> Settings:
    """Load, merge, and validate settings for an environment.

    Args:
        environment: ``dev`` / ``live`` / ``test``; defaults to ``QP_ENV`` or ``dev``.
        root: project root; defaults to ``QP_ROOT`` or the detected ``pyproject.toml`` dir.
        config_dir: directory of YAML files; defaults to ``QP_CONFIG_DIR`` or ``<root>/config``.
        overrides: highest-priority explicit values (above env vars).

    Raises:
        ConfigError: if a config file is missing/malformed or validation fails.
    """
    env = _resolve_environment(environment)
    resolved_root = _resolve_root(root)
    cfg_dir = _resolve_config_dir(config_dir, resolved_root)

    base = _load_yaml(cfg_dir / "base.yaml")
    env_overlay = _load_yaml(cfg_dir / f"{env.value}.yaml")
    merged = deep_merge(base, env_overlay)

    # Force consistency: the resolved environment always wins over file contents.
    merged["environment"] = env.value
    # Inject the project root into the (low-priority) YAML layer so env/overrides can win.
    paths_layer = dict(merged.get("paths") or {})
    paths_layer.setdefault("root", str(resolved_root))
    merged["paths"] = paths_layer

    token = _yaml_layer.set(merged)
    try:
        return Settings(**dict(overrides or {}))
    except ConfigError:
        raise
    except Exception as exc:  # pydantic ValidationError, yaml errors, etc.
        raise ConfigError(f"failed to build settings for environment {env.value!r}: {exc}") from exc
    finally:
        _yaml_layer.reset(token)


@cache
def get_settings(environment: str | None = None) -> Settings:
    """Return cached settings for an environment (process-wide singleton per env)."""
    return load_settings(environment)


def clear_settings_cache() -> None:
    """Clear the :func:`get_settings` cache (used by tests and config reloads)."""
    get_settings.cache_clear()


def ensure_directories(settings: Settings) -> None:
    """Create the lake / data / artifacts / logs directories if they do not exist."""
    for path in (
        settings.paths.lake_dir,
        settings.paths.data_dir,
        settings.paths.artifacts_dir,
        settings.paths.logs_dir,
    ):
        if path is not None:
            path.mkdir(parents=True, exist_ok=True)
