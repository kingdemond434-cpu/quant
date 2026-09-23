"""Failed certificate transfers preserve the exact previous evidence bytes."""
import importlib.util
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("failure", ["exit", "timeout", "invalid", "scalar", "success"])
def test_certificate_publication_is_atomic(tmp_path, monkeypatch, failure):
    path = Path(__file__).resolve().parents[1] / "scripts" / "pull_certs.py"
    spec = importlib.util.spec_from_file_location("certificate_pull_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "WIN_BASE", tmp_path)
    target = tmp_path / "reports" / "cert.json"
    target.parent.mkdir()
    previous = b'{"survivors":{"existing":{}}}'
    target.write_bytes(previous)

    def transfer(cmd, **kwargs):
        incoming = Path(cmd[-1])
        assert incoming != target
        incoming.write_text('{"survivors":{"new":{}}}' if failure == "success" else
                            ('null' if failure == "scalar" else '{"partial":'), "utf-8")
        if failure == "timeout":
            raise subprocess.TimeoutExpired(cmd, 90)
        return SimpleNamespace(returncode=1 if failure == "exit" else 0)

    monkeypatch.setattr(module.subprocess, "run", transfer)
    assert module.pull("reports/cert.json", "reports/cert.json") == (failure == "success")
    if failure != "success":
        assert target.read_bytes() == previous
    else:
        assert b'"new"' in target.read_bytes()
    assert not list(target.parent.glob("*.incoming"))
