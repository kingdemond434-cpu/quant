"""A key set with `setx /M` must be found even by a process started before it was set."""
from __future__ import annotations

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
    monkeypatch.setenv("FRED_API_KEY", "p" * 32)
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


def test_fresh_secrets_fills_only_absent_secret_names(monkeypatch: pytest.MonkeyPatch) -> None:
    hives = {"machine": {"FRED_API_KEY": "k1", "PATH": "C:\\x", "GITHUB_TOKEN": "t",
                         "OPENROUTER_API_KEY": "new"},
             "user": {"MY_SECRET": "s", "FRED_API_KEY": "user-copy"}}
    monkeypatch.setattr(es, "_registry_all", lambda hive: hives[hive])
    got = es.fresh_secrets({"OPENROUTER_API_KEY": "already", "PATH": "/bin"})
    assert got == {"FRED_API_KEY": "k1", "GITHUB_TOKEN": "t", "MY_SECRET": "s"}
