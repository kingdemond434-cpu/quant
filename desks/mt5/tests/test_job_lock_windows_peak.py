"""Admission must remember actual Windows peaks after graph memory is released."""
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from desks.mt5.research import job_lock


def test_windows_admission_uses_native_peak_not_the_current_trough(monkeypatch):
    info = SimpleNamespace(peak_wset=5 * 1024**3, rss=12 * 1024**2)
    api = SimpleNamespace(Process=lambda: SimpleNamespace(memory_info=lambda: info))
    monkeypatch.setitem(sys.modules, "psutil", api)
    monkeypatch.setattr(job_lock.sys, "platform", "win32")
    assert job_lock.peak_rss_mb() == 5120


@pytest.mark.parametrize("peak", [0, -1, None, "unmeasured"])
def test_invalid_windows_peak_is_unmeasured_not_current_rss(monkeypatch, peak):
    info = SimpleNamespace(peak_wset=peak, rss=512 * 1024**2)
    api = SimpleNamespace(Process=lambda: SimpleNamespace(memory_info=lambda: info))
    monkeypatch.setitem(sys.modules, "psutil", api)
    monkeypatch.setattr(job_lock.sys, "platform", "win32")
    assert job_lock.peak_rss_mb() is None


@pytest.mark.skipif(sys.platform != "win32", reason="Native Windows working-set counter")
def test_native_windows_peak_survives_releasing_a_real_allocation():
    desk = Path(job_lock.__file__).resolve().parents[1]
    code = """
import gc, json
from research.job_lock import peak_rss_mb
before = peak_rss_mb()
block = bytearray(32 * 1024 * 1024)
block[::4096] = bytes([1]) * (len(block) // 4096)
allocated = peak_rss_mb()
del block
gc.collect()
released = peak_rss_mb()
print(json.dumps([before, allocated, released]))
"""
    result = subprocess.run(
        [sys._base_executable, "-c", code], check=True, capture_output=True,
        text=True, timeout=30, env={**os.environ, "PYTHONPATH": str(desk)},
    )
    before, allocated, released = json.loads(result.stdout)
    assert allocated >= before + 16
    assert released >= allocated
