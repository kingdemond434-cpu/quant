"""read_key reaches a key set with setx /M after the process started, and the catalog is complete."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from libs.ops import env_keys

ROOT = Path(__file__).resolve().parents[2]


def test_process_env_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QK_TEST_KEY", " abc ")
    monkeypatch.setattr(env_keys, "registry_sources", lambda name: [("machine", "zzz")])
    assert env_keys.read_key("QK_TEST_KEY") == "abc"


def test_registry_value_reaches_a_process_started_before_setx(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QK_TEST_KEY", raising=False)
    monkeypatch.setattr(env_keys, "registry_sources", lambda name: [("machine", "fromreg")])
    assert env_keys.read_key("QK_TEST_KEY") == "fromreg"
    # copied into the process so children inherit it
    import os
    assert os.environ["QK_TEST_KEY"] == "fromreg"


def test_missing_is_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QK_TEST_KEY", raising=False)
    monkeypatch.setattr(env_keys, "registry_sources", lambda name: [])
    assert env_keys.read_key("QK_TEST_KEY") == ""
    assert env_keys.read_key("") == ""


def test_catalog_rows_are_well_formed() -> None:
    rows = env_keys.catalog()
    names = [r["name"] for r in rows]
    assert len(names) == len(set(names))
    for r in rows:
        for field in ("group", "cost", "machine", "signup", "unlocks", "readers", "owner"):
            assert r.get(field), (r["name"], field)
        for reader in r["readers"]:
            path = reader.split(" ")[0]
            assert (ROOT / path).exists(), (r["name"], path)


def test_every_declared_key_env_is_in_the_catalog() -> None:
    """A new keyed source must land in the catalog, or the operator's checker never shows it."""
    names = set(env_keys.key_names())
    declared: set[str] = set()
    asia = json.loads((ROOT / "desks/mt5/data/asia_sources.json").read_text("utf-8"))
    declared |= set(re.findall(r'"key_env":\s*"([A-Z0-9_]+)"', json.dumps(asia)))
    alt = (ROOT / "desks/mt5/research/alt_proxies.py").read_text("utf-8")
    declared |= set(re.findall(r'key_env="([A-Z0-9_]+)"', alt))
    assert declared, "no key_env found: the scan pattern rotted"
    assert declared <= names, sorted(declared - names)
