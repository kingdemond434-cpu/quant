"""Exercise the real persistence functions without importing the order adapter."""
import ast
import contextlib
import json
import os
import tempfile
from pathlib import Path

import pytest


def functions(tmp_path):
    source = Path(__file__).parents[1] / "mt5desk/gateway.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name in {"save_state", "load_state"}]
    namespace = {"STATE": tmp_path / "gateway_state.json", "json": json, "os": os,
                 "tempfile": tempfile, "contextlib": contextlib}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), namespace)
    return namespace


def test_success_preserves_restart_identity(tmp_path):
    scope = functions(tmp_path)
    state = {"armed": False, "brackets": {"ticket": 123}, "orig_stop_dist": {"123": 0.1}}
    scope["save_state"](state)
    recovered = scope["load_state"]()
    assert all(recovered[key] == value for key, value in state.items())
    assert list(tmp_path.iterdir()) == [scope["STATE"]]


@pytest.mark.parametrize("failure", ["fsync", "replace"])
def test_interruption_preserves_previous_state(tmp_path, monkeypatch, failure):
    scope = functions(tmp_path)
    previous = b'{"armed": false, "brackets": {"existing": 42}}'
    scope["STATE"].write_bytes(previous)

    def fail(*args):
        raise OSError("injected persistence failure")

    monkeypatch.setattr(os, failure, fail)
    with pytest.raises(OSError, match="injected persistence failure"):
        scope["save_state"]({"armed": False, "brackets": {"new": 43}})
    assert scope["STATE"].read_bytes() == previous
    assert list(tmp_path.iterdir()) == [scope["STATE"]]


def test_corrupted_existing_state_never_becomes_empty_book(tmp_path):
    scope = functions(tmp_path)
    scope["STATE"].write_bytes(b"\x00" * 17161)
    with pytest.raises(json.JSONDecodeError):
        scope["load_state"]()
    assert scope["STATE"].read_bytes() == b"\x00" * 17161
