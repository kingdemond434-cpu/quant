"""``libs.core`` — the platform spine: contracts, config, logging, time, reproducibility.

This package depends on nothing internal and is imported by everything else. Types and
helpers defined here are the single source of truth and must never be redefined elsewhere.
"""

from __future__ import annotations

from libs.core.config import (
    LoggingConfig,
    Paths,
    ReproducibilityConfig,
    Settings,
    clear_settings_cache,
    deep_merge,
    ensure_directories,
    find_project_root,
    get_settings,
    hash_config,
    load_settings,
)
from libs.core.enums import Environment, LogLevel, RunMode
from libs.core.errors import (
    ConfigError,
    GitError,
    QuantPlatformError,
    ReproducibilityError,
    SecretsError,
    TimezoneError,
)
from libs.core.ids import generate_id, new_correlation_id, new_run_id, new_stamp_id
from libs.core.logging import (
    bind,
    clear_correlation_id,
    configure_logging,
    correlation_context,
    get_correlation_id,
    get_logger,
    set_correlation_id,
)
from libs.core.reproducibility import (
    GitInfo,
    ReproducibilityStamp,
    VerificationResult,
    create_reproducibility_stamp,
    get_git_info,
    seed_everything,
    verify_reproducibility,
)
from libs.core.secrets import (
    EnvSecretsProvider,
    SecretsProvider,
    get_secret,
    set_default_provider,
)
from libs.core.time import (
    UTC,
    ensure_utc,
    from_epoch_ms,
    from_iso8601,
    is_utc,
    to_epoch_ms,
    to_iso8601,
    to_utc,
    utcnow,
)

__all__ = [  # noqa: RUF022  # grouped by module for readability, not alphabetised
    # config
    "Settings",
    "Paths",
    "LoggingConfig",
    "ReproducibilityConfig",
    "load_settings",
    "get_settings",
    "clear_settings_cache",
    "ensure_directories",
    "find_project_root",
    "deep_merge",
    "hash_config",
    # enums
    "Environment",
    "RunMode",
    "LogLevel",
    # errors
    "QuantPlatformError",
    "ConfigError",
    "TimezoneError",
    "GitError",
    "ReproducibilityError",
    "SecretsError",
    # ids
    "generate_id",
    "new_run_id",
    "new_correlation_id",
    "new_stamp_id",
    # logging
    "configure_logging",
    "get_logger",
    "bind",
    "correlation_context",
    "set_correlation_id",
    "get_correlation_id",
    "clear_correlation_id",
    # time
    "UTC",
    "utcnow",
    "is_utc",
    "ensure_utc",
    "to_utc",
    "to_iso8601",
    "from_iso8601",
    "to_epoch_ms",
    "from_epoch_ms",
    # secrets
    "SecretsProvider",
    "EnvSecretsProvider",
    "get_secret",
    "set_default_provider",
    # reproducibility
    "GitInfo",
    "ReproducibilityStamp",
    "VerificationResult",
    "create_reproducibility_stamp",
    "verify_reproducibility",
    "get_git_info",
    "seed_everything",
]
