"""R0094: daily-cycle steps that carry CLI args must reach the child as argv, not as a
single filename-with-a-space. The original bug ran `[python, "scripts/research_exchange.py
brief"]` -> rc=2 on EVERY cycle, and the best-effort chain swallowed it for weeks.

Two guards:
  1. _run() splits the step string shell-style before exec.
  2. Every _STEPS entry's script token is a real file, so a renamed organ cannot rot here
     silently (the rc=2 class again, one spelling over).
"""

from __future__ import annotations

import shlex
from pathlib import Path
from unittest import mock

import scripts.daily_research_cycle as dc

_ROOT = Path(dc.__file__).resolve().parent.parent


def test_run_splits_args_into_argv() -> None:
    captured: dict[str, list[str]] = {}

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN003 - signature mirrors subprocess.run
        captured["cmd"] = list(cmd)
        return mock.Mock(returncode=0, stdout="ok", stderr="")

    with mock.patch.object(dc.subprocess, "run", side_effect=fake_run):
        out = dc._run("scripts/research_exchange.py brief", timeout=5)

    assert out["ok"] is True
    assert captured["cmd"][1:] == ["scripts/research_exchange.py", "brief"], (
        "args must be separate argv elements, not one filename: %r" % (captured["cmd"],)
    )


def test_every_step_script_exists() -> None:
    missing = []
    for label, script, _timeout in dc._STEPS:
        path = shlex.split(script)[0]
        if not (_ROOT / path).is_file():
            missing.append((label, path))
    assert not missing, f"steps pointing at absent scripts (rc=2 class): {missing}"
