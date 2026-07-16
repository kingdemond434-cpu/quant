"""Tests for the secrets interface."""

from __future__ import annotations

import pytest

from libs.core.errors import SecretsError
from libs.core.secrets import (
    EnvSecretsProvider,
    SecretsProvider,
    get_default_provider,
    get_secret,
    set_default_provider,
)


def test_env_provider_reads_prefixed_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QP_SECRET_MT5_PASSWORD", "s3cret")
    provider = EnvSecretsProvider()
    assert provider.has_secret("mt5_password") is True
    assert provider.get_secret("mt5_password") == "s3cret"


def test_env_provider_missing_raises() -> None:
    provider = EnvSecretsProvider()
    assert provider.has_secret("nope") is False
    with pytest.raises(SecretsError):
        provider.get_secret("nope")


def test_env_provider_empty_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QP_SECRET_EMPTY", "")
    provider = EnvSecretsProvider()
    assert provider.has_secret("empty") is False
    with pytest.raises(SecretsError):
        provider.get_secret("empty")


def test_default_provider_get_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QP_SECRET_BROKER_LOGIN", "12345")
    assert get_secret("broker_login") == "12345"


def test_set_default_provider_swaps_implementation() -> None:
    original = get_default_provider()

    class StaticProvider:
        def get_secret(self, name: str) -> str:
            return f"static-{name}"

        def has_secret(self, name: str) -> bool:
            return True

    try:
        set_default_provider(StaticProvider())
        assert get_secret("anything") == "static-anything"
    finally:
        set_default_provider(original)


def test_env_provider_satisfies_protocol() -> None:
    assert isinstance(EnvSecretsProvider(), SecretsProvider)
