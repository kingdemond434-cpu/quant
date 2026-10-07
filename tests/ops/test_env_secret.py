"""A key set with `setx /M` must be found even by a process started before it was set."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.ops import env_secret as es


def test_process_env_first_then_registry_then_file(tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.delenv("FRED_KEY", raising=False)
    reg = {("machine", "FRED_API_KEY"): "m" * 32}
    monkeypatch.setattr(es, "_registry", lambda hive, name: reg.get((hive, name)))
    f = tmp_path / "fred.json"
    f.write_text('{"key": "from-file"}', encoding="utf-8")
    assert es.lookup(("FRED_API_KEY",), [f]) == ("m" * 32, "machine")
    monkeypatch.setenv("FRED_API_KEY", "p" * 32)               # stale inherited copy
    assert es.lookup(("FRED_API_KEY",), [f])[1] == "machine"  # the registry's newest wins
    reg.clear()
    assert es.lookup(("FRED_API_KEY",), [f])[1] == "process"
    monkeypatch.delenv("FRED_API_KEY")
    reg.clear()
    reg[("user", "FRED_KEY")] = "u"
    assert es.lookup(("FRED_API_KEY", "FRED_KEY"), [f]) == ("u", "user")
    reg.clear()
    assert es.lookup(("FRED_API_KEY",), [f]) == ("from-file", "file:fred.json")
    assert es.lookup(("FRED_API_KEY",), [tmp_path / "none"]) == (None, "absent")


def test_presence_never_carries_the_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRED_API_KEY", "secret-value-123")
    p = es.presence(("FRED_API_KEY",))
    assert p == {"present": True, "origin": "process", "length": 16,
                 "names": ["FRED_API_KEY"]}
    assert "secret-value-123" not in repr(p)


def test_registry_is_never_read_off_windows() -> None:
    import sys
    if sys.platform.startswith("win"):
        pytest.skip("on Windows the registry is real")
    assert es._registry("machine", "PATH") is None


def test_fresh_secrets_fills_only_absent_secret_names(monkeypatch: pytest.MonkeyPatch,
                                                     tmp_path: Path) -> None:
    monkeypatch.setattr(es, "CATALOG", tmp_path / "absent.json")     # the suffix rule alone
    hives = {"machine": {"FRED_API_KEY": "k1", "PATH": "C:\\x", "GITHUB_TOKEN": "t",
                         "OPENROUTER_API_KEY": "new"},
             "user": {"MY_SECRET": "s", "FRED_API_KEY": "user-copy"}}
    monkeypatch.setattr(es, "_registry_all", lambda hive: hives[hive])
    got = es.fresh_secrets({"OPENROUTER_API_KEY": "already", "PATH": "/bin"})
    assert got == {"FRED_API_KEY": "k1", "GITHUB_TOKEN": "t", "MY_SECRET": "s"}


def test_with_the_catalog_only_catalogued_names_are_carried(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Audit #204: login-shaped names ride into LLM seats and miners only when catalogued; an MT5
    or broker login that is not in the inventory never leaves the registry."""
    cat = tmp_path / "env_keys_catalog.json"
    cat.write_text(json.dumps({"keys": [
        {"name": "FRED_API_KEY", "group": "free_data"},
        {"name": "JQ_USER", "group": "account_free"}, {"name": "JQ_PASS", "group": "account_free"},
        {"name": "ECOS_API_KEY", "group": "unavailable"},
        {"name": "ESTAT_APP_ID", "group": "free_data"},
        {"name": "JQUANTS_MAILADDRESS", "group": "legacy", "aliases": ["JQUANTS_EMAIL"]},
        {"name": "MYFXBOOK_PASSWORD", "group": "account_free"},
        {"name": "ODD_FEED_SECRET", "group": "free_data", "status": "BLOCKED_ON_TERMS"},
        {"name": "PAID_VENDOR_KEY", "group": "paid_blocked"},
        {"name": "REDDIT_SECRET", "group": "banned", "aliases": ["REDDIT_PASSWORD"]}]}))
    monkeypatch.setattr(es, "CATALOG", cat)
    hives = {"machine": {"FRED_API_KEY": "k", "JQ_USER": "u", "JQ_PASS": "p",
                         "ESTAT_APP_ID": "a", "JQUANTS_EMAIL": "m",
                         "MYFXBOOK_PASSWORD": "x", "ODD_FEED_SECRET": "o", "ECOS_API_KEY": "e",
                         "PAID_VENDOR_KEY": "x", "REDDIT_PASSWORD": "r",
                         "MT5_PASSWORD": "broker", "MT5_LOGIN_USER": "123",
                         "BROKER_EMAIL": "e", "UNLISTED_API_KEY": "z",
                         "USERNAME": "dell", "COMPUTERNAME": "box"},
             "user": {}}
    monkeypatch.setattr(es, "_registry_all", lambda hive: hives[hive])
    assert set(es.fresh_secrets({})) == {"FRED_API_KEY", "JQ_USER", "JQ_PASS", "ESTAT_APP_ID",
                                         "JQUANTS_EMAIL"}


def test_without_the_catalog_only_api_key_shapes_are_carried(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(es, "CATALOG", tmp_path / "absent.json")
    assert es.is_secret_name("FRED_API_KEY") and es.is_secret_name("GITHUB_TOKEN")
    for name in ("PATH", "MT5_PASSWORD", "BROKER_USER", "JQ_PASS", "MYFXBOOK_SESSION"):
        assert not es.is_secret_name(name)


def test_hard_refusals_hold_even_without_a_catalog(monkeypatch: pytest.MonkeyPatch,
                                                   tmp_path: Path) -> None:
    """Audit #204 (2026-10-07): suffix mode carried X_BEARER_TOKEN, REDDIT_SECRET and paid
    vendors' tokens to every child."""
    monkeypatch.setattr(es, "CATALOG", tmp_path / "absent.json")
    for name in ("X_BEARER_TOKEN", "REDDIT_SECRET", "STOCKTWITS_TOKEN", "DISCORD_TOKEN",
                 "TIANYANCHA_TOKEN", "WIND_KEY", "MYFXBOOK_SESSION"):
        assert not es.is_secret_name(name), name
    assert es.is_secret_name("FRED_API_KEY")


@pytest.mark.parametrize("body", ["{not json", '{"keys": "abc"}', "[]"])
def test_an_unreadable_catalog_carries_nothing(monkeypatch: pytest.MonkeyPatch,
                                               tmp_path: Path, body: str) -> None:
    cat = tmp_path / "env_keys_catalog.json"
    cat.write_text(body)
    monkeypatch.setattr(es, "CATALOG", cat)
    monkeypatch.setattr(es, "_registry_all",
                        lambda hive: {"FRED_API_KEY": "k", "GITHUB_TOKEN": "t"}
                        if hive == "machine" else {})
    assert es.fresh_secrets({}) == {}
