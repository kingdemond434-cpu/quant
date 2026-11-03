"""The onion lane is permanently refused (auditor ruling 2026-11-03): no env var or ruling file
can open it, and the Tor Metrics producer never imports or calls it."""
from __future__ import annotations

import ast
import json
import socket
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from research import onion_mirrors as O  # noqa: E402


def test_refuses_even_with_socks_env_and_an_allow_ruling(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("QUANT_TOR_SOCKS", "127.0.0.1:9050")
    ruling = tmp_path / "ONION_EGRESS_RULING.json"
    ruling.write_text(json.dumps({"allowed": True, "ruled_by": "auditor",
                                  "ruled_at": "2026-11-03"}), "utf-8")

    def no_socket(*a: Any, **k: Any) -> Any:
        raise AssertionError("onion_mirrors opened a socket")
    monkeypatch.setattr(socket, "create_connection", no_socket)
    monkeypatch.setattr(socket.socket, "connect", no_socket)
    rep = O.run(environ={"QUANT_TOR_SOCKS": "127.0.0.1:9050"}, ruling=ruling, dry_run=False)
    assert O.REFUSED is True
    assert rep["gate"] == O.GATE and rep["refused"] is True
    assert rep["n_measured"] == 0 and rep["rows"] == []


def test_module_has_no_override_path() -> None:
    src = (DESK / "research" / "onion_mirrors.py").read_text("utf-8")
    tree = ast.parse(src)
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    imported = {a.name.split(".")[0] for n in ast.walk(tree)
                if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
    imported |= {(n.module or "").split(".")[0] for n in ast.walk(tree)
                 if isinstance(n, ast.ImportFrom)}
    assert "environ" not in attrs and "getenv" not in attrs and "environ" not in names
    assert not imported & {"os", "socket", "ssl", "http", "urllib", "libs"}
    assert "QUANT_TOR_SOCKS" not in src and "ONION_EGRESS_RULING" not in src
    assert not (DESK / "data" / "onion_allowlist.json").exists()


def test_tor_metrics_never_imports_or_calls_onion_mirrors() -> None:
    src = (DESK / "research" / "tor_metrics.py").read_text("utf-8")
    tree = ast.parse(src)
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            assert "onion_mirrors" not in (n.module or "")
            assert all("onion_mirrors" not in a.name for a in n.names)
        elif isinstance(n, ast.Import):
            assert all("onion_mirrors" not in a.name for a in n.names)
        elif isinstance(n, ast.Attribute):
            assert not (isinstance(n.value, ast.Name) and n.value.id == "onion_mirrors")
    import importlib
    T = importlib.import_module("research.tor_metrics")
    assert "onion" not in T.run.__code__.co_varnames[:T.run.__code__.co_argcount
                                                     + T.run.__code__.co_kwonlyargcount]


def test_terms_row_states_the_ruling_with_missed_growth() -> None:
    from libs.data import terms_fence as tf
    row = tf.SOURCE_POLICY["onion_mirrors"]
    assert "permanently refused" in row["why"] and "2026-11-03" in row["why"]
    assert row["missed_growth"]["delta_elogw"]
    assert tf.input_source("http://" + "a" * 56 + ".onion/") == "onion_mirrors"


@pytest.mark.parametrize("argv", [[], ["--once"], ["--once", "--dry-run"]])
def test_cli_refuses(argv: list[str], capsys) -> None:
    assert O.main(argv) == 0
    assert O.GATE in capsys.readouterr().out
