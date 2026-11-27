"""The repo's `ops` stays bound even after a test puts desks/mt5 (a regular `ops`) on sys.path."""
from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_ops_is_the_repo_namespace_after_desks_mt5_lands_on_sys_path(monkeypatch) -> None:
    monkeypatch.syspath_prepend(str(ROOT / "desks" / "mt5"))
    mod = importlib.import_module("ops.box_git.drop_pull")
    assert Path(mod.__file__).resolve().parent == ROOT / "ops" / "box_git"


def test_the_shadow_is_real_without_the_binding() -> None:
    """Pins the cause: with desks/mt5 on sys.path and no prior binding, `ops` is desks/mt5/ops."""
    paths = [str(ROOT), str(ROOT / "desks" / "mt5")]
    code = f"import sys; sys.path[:0] = {paths!r}; import ops; print(list(ops.__path__))"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         check=True, cwd=ROOT).stdout
    assert "desks" in out
