"""The git environment a box process needs, for Python callers (the twin of GitBoxEnv.ps1).

MEASURED 2026-10-06 on vmi3571445: C:\\opt\\quant is owned by BUILTIN\\Administrators and the tasks
run as VMI3571445\\Administrator, so every plain git call refuses with "detected dubious
ownership". `sync_shadow_to_git.ps1` sets `safe.directory` for its own process through
GitBoxEnv.ps1, but a Python reader started elsewhere (MT5-StallWatch's `state_publication
--watch`, the hourly `publish_state` leg) gets no such setting, so BOX_STATE_FLOW could read
UNMEASURED on the very refusal it exists to name.

`git_env(root)` returns a copy of the environment with `safe.directory=<root>` appended to the
command-scope configuration (GIT_CONFIG_COUNT / GIT_CONFIG_KEY_n / GIT_CONFIG_VALUE_n), which git
honours for safe.directory and which writes nothing to any config file. Entries the caller already
set (the PowerShell parent's, including its auth header) are kept, never renumbered.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path


def git_env(root: Path, base: Mapping[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base is None else base)
    safe = str(root).replace("\\", "/").rstrip("/")
    try:
        n = int(env.get("GIT_CONFIG_COUNT", "0") or 0)
    except ValueError:
        n = 0
    for i in range(n):
        if (env.get(f"GIT_CONFIG_KEY_{i}") == "safe.directory"
                and env.get(f"GIT_CONFIG_VALUE_{i}") == safe):
            return env
    env[f"GIT_CONFIG_KEY_{n}"] = "safe.directory"
    env[f"GIT_CONFIG_VALUE_{n}"] = safe
    env["GIT_CONFIG_COUNT"] = str(n + 1)
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    return env
