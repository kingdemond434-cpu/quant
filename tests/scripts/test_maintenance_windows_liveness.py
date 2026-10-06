import os

import psutil
import pytest

from scripts import run_miner_maintenance as maintenance


@pytest.mark.parametrize("exists", [True, False])
def test_windows_maintenance_uses_a_non_signalling_probe(monkeypatch, exists):
    monkeypatch.setattr(maintenance.sys, "platform", "win32")
    monkeypatch.setattr(psutil, "pid_exists", lambda pid: exists)

    def forbidden(*args):
        raise AssertionError("a liveness check must not send signals")

    monkeypatch.setattr(maintenance.os, "kill", forbidden)
    assert maintenance._owner_alive(6904) is exists


def test_windows_probe_failure_is_unknown(monkeypatch):
    monkeypatch.setattr(maintenance.sys, "platform", "win32")

    def failed(_pid):
        raise OSError("query failed")

    monkeypatch.setattr(psutil, "pid_exists", failed)
    assert maintenance._owner_alive(6904) is None


@pytest.mark.skipif(os.name != "nt", reason="native Windows process regression")
def test_windows_maintenance_preserves_its_current_process():
    assert maintenance._owner_alive(os.getpid()) is True
