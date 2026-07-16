"""Secrets interface.

Broker credentials are the crown jewels: they live only behind a provider, never in
config files, never in logs. Stage 1 ships an environment-variable provider (prefix
``QP_SECRET_``); a Vault/KMS provider can be slotted in later behind the same protocol.
"""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

from libs.core.errors import SecretsError

SECRET_ENV_PREFIX = "QP_SECRET_"


@runtime_checkable
class SecretsProvider(Protocol):
    """A source of named secrets. Implementations must never log secret values."""

    def get_secret(self, name: str) -> str:
        """Return the secret value for ``name``, or raise :class:`SecretsError` if absent."""
        ...

    def has_secret(self, name: str) -> bool:
        """Return whether a secret named ``name`` is available."""
        ...


def _env_key(name: str) -> str:
    return f"{SECRET_ENV_PREFIX}{name.upper()}"


class EnvSecretsProvider:
    """Reads secrets from environment variables named ``QP_SECRET_<NAME>``."""

    def get_secret(self, name: str) -> str:
        value = os.environ.get(_env_key(name))
        if value is None or value == "":
            raise SecretsError(f"secret {name!r} is not set (expected env var {_env_key(name)})")
        return value

    def has_secret(self, name: str) -> bool:
        value = os.environ.get(_env_key(name))
        return value is not None and value != ""


_default_provider: SecretsProvider = EnvSecretsProvider()


def set_default_provider(provider: SecretsProvider) -> None:
    """Override the process-wide default secrets provider."""
    global _default_provider
    _default_provider = provider


def get_default_provider() -> SecretsProvider:
    """Return the process-wide default secrets provider."""
    return _default_provider


def get_secret(name: str) -> str:
    """Fetch a secret from the default provider."""
    return _default_provider.get_secret(name)
