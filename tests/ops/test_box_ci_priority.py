from __future__ import annotations

import os
import subprocess
import types
from pathlib import Path

from ops.box_git import box_ci


def test_ci_jobs_run_below_normal_not_idle(monkeypatch):
    monkeypatch.setattr(box_ci, "os", types.SimpleNamespace(name="nt", nice=os.nice))
    kw = box_ci.idle_priority_kwargs()
    flag = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x4000)
    assert kw == {"creationflags": flag}
    assert flag != getattr(subprocess, "IDLE_PRIORITY_CLASS", 0x40)


def test_ci_task_is_not_registered_at_the_lowest_priority():
    ps1 = (Path(__file__).resolve().parents[2] / "ops" / "box_git" /
           "install_box_forge.ps1").read_text(encoding="utf-8")
    line = next(ln for ln in ps1.splitlines() if ln.startswith("$cSet ="))
    assert "-Priority 7" in line and "-Priority 9" not in line
