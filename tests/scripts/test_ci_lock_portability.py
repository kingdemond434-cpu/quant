"""The canonical gate must hold one real interprocess lock on Windows and POSIX."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _gate():
    spec = importlib.util.spec_from_file_location("ci_lock_probe", ROOT / "scripts/run_ci.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_second_process_cannot_enter_until_the_first_releases(tmp_path):
    gate = _gate()
    lock = tmp_path / "gate.lock"
    gate._LOCK = lock
    first = gate._acquire()
    assert first is not None
    child = (
        "import importlib.util,sys;from pathlib import Path;"
        f"sys.path.insert(0,{str(ROOT)!r});"
        f"s=importlib.util.spec_from_file_location('gate',{str(ROOT / 'scripts/run_ci.py')!r});"
        "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
        f"m._LOCK=Path({str(lock)!r});"
        "h=m._acquire();sys.exit(0 if h is None else 1)"
    )
    try:
        result = subprocess.run([sys.executable, "-c", child], capture_output=True,
                                text=True, timeout=30, cwd=ROOT)
        assert result.returncode == 0, result.stderr
    finally:
        first.close()
    second = gate._acquire()
    assert second is not None
    second.close()
