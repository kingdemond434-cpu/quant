"""read_key reaches a key set with setx /M after the process started; the catalog is complete."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from libs.ops import env_keys

ROOT = Path(__file__).resolve().parents[2]


def test_process_env_is_used_off_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QK_TEST_KEY", " abc ")
    assert env_keys.read_key("QK_TEST_KEY") == "abc"


def test_registry_value_reaches_a_process_started_before_setx(
        monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    from libs.ops import env_secret
    monkeypatch.setenv("QK_TEST_KEY", "stale")
    monkeypatch.setattr(env_secret, "_registry",
                        lambda hive, name: "fromreg" if hive == "machine" else None)
    assert env_keys.read_key("QK_TEST_KEY") == "fromreg"
    assert os.environ["QK_TEST_KEY"] == "stale", "no export unless asked"
    assert env_keys.read_key("QK_TEST_KEY", export=True) == "fromreg"
    assert os.environ["QK_TEST_KEY"] == "fromreg"


def test_another_users_hive_is_reported_but_never_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QK_TEST_KEY", raising=False)
    monkeypatch.setattr(env_keys, "registry_sources",
                        lambda name: [("user:S-1-5-21-1", "otheruser")])
    assert env_keys.read_key("QK_TEST_KEY") == ""


@pytest.mark.parametrize("name", ["TIANYANCHA_TOKEN", "BAIDU_INDEX_COOKIE", "XUEQIU_COOKIE",
                                  "X_BEARER_TOKEN", "REDDIT_CLIENT_ID", "WIND_KEY"])
def test_paid_and_banned_names_are_refused_even_when_set(
        monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.setenv(name, "set-on-the-box")
    assert env_keys.refused(name)
    assert env_keys.read_key(name) == ""


def test_missing_is_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QK_TEST_KEY", raising=False)
    assert env_keys.read_key("QK_TEST_KEY") == ""
    assert env_keys.read_key("") == ""


def test_catalog_rows_are_well_formed() -> None:
    rows = env_keys.catalog()
    names = [r["name"] for r in rows]
    assert len(names) == len(set(names))
    for r in rows:
        for field in ("group", "cost", "machine", "signup", "unlocks", "readers", "owner"):
            assert r.get(field), (r["name"], field)
        if r.get("pending_pr"):
            continue  # its reader lands with that PR
        for reader in r["readers"]:
            path = reader.split(" ")[0]
            assert (ROOT / path).exists(), (r["name"], path)


def test_every_declared_key_env_is_in_the_catalog() -> None:
    """A new keyed source must land in the catalog, or the operator's checker never shows it."""
    names = set(env_keys.key_names())
    for r in env_keys.catalog():
        names |= set(r.get("aliases") or [])
    declared: set[str] = set()
    asia = json.loads((ROOT / "desks/mt5/data/asia_sources.json").read_text("utf-8"))
    declared |= set(re.findall(r'"key_env":\s*"([A-Z0-9_]+)"', json.dumps(asia)))
    alt = (ROOT / "desks/mt5/research/alt_proxies.py").read_text("utf-8")
    declared |= set(re.findall(r'key_env="([A-Z0-9_]+)"', alt))
    assert declared, "no key_env found: the scan pattern rotted"
    assert declared <= names, sorted(declared - names)


def test_every_built_credential_registry_var_is_in_the_catalog() -> None:
    reg = json.loads((ROOT / "desks/mt5/data/credential_registry.json").read_text("utf-8"))
    known = set(env_keys.key_names())
    for r in env_keys.catalog():
        known |= set(r.get("aliases") or [])
    built = {v["env"] for v in reg["vars"] if str(v.get("built")) == "BUILT"}
    assert built, "credential registry has no BUILT var: the scan rotted"
    assert built <= known, sorted(built - known)
