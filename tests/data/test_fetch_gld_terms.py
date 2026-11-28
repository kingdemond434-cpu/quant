"""fetch_gld is terms-refused: it never opens a network path."""

from __future__ import annotations

import importlib.util
import socket
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "desks" / "mt5" / "research" / "fetch_gld.py"


def _load():
    spec = importlib.util.spec_from_file_location("fetch_gld_terms_probe", SRC)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_main_refuses_without_touching_the_network(monkeypatch: pytest.MonkeyPatch,
                                                    capsys: pytest.CaptureFixture[str]) -> None:
    def _no_net(*a: object, **k: object) -> None:
        raise AssertionError("fetch_gld opened a socket")

    monkeypatch.setattr(socket, "create_connection", _no_net)
    mod = _load()
    assert mod.main() == 2
    out = capsys.readouterr().out
    assert "BLOCKED_ON_TERMS" in out


def test_refusal_carries_missed_growth() -> None:
    st = _load().status()
    assert st["status"] == "BLOCKED_ON_TERMS"
    mg = st["missed_growth"]
    assert isinstance(mg, dict) and mg["mechanism"] == "gld_terms_refusal"


def test_no_http_client_imported() -> None:
    text = SRC.read_text(encoding="utf-8")
    for mod in ("requests", "urllib", "httpx", "pandas"):
        assert f"import {mod}" not in text
