"""The gate's git calls died at rc 128 on every sweep from 2026-11-05 to 11-13 (box repro):
merger_env.ps1 set GIT_CONFIG_VALUE_n to "", which Windows PowerShell 5.1 turns into a DELETED
variable, so git read GIT_CONFIG_COUNT naming a value that did not exist. And the gate loaded
that file from its stale clone before fetching, so no fix could reach it."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MERGER = (ROOT / "ops/release/merger/merger_env.ps1").read_text(encoding="utf-8")
GATE = (ROOT / "ops/box/workflow_gate.ps1").read_text(encoding="utf-8")


def _code(text: str) -> str:
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))


def test_no_env_variable_is_ever_set_to_an_empty_string() -> None:
    for src in (MERGER, GATE, (ROOT / "ops/box/sign_train_leg.ps1").read_text(encoding="utf-8")):
        code = _code(src)
        assert not re.search(r"env:[^\s\"]+\"?\s+-Value\s+(\"\"|'')", code)
        assert not re.search(r"\$env:\w+\s*=\s*(\"\"|'')\s*$", code, flags=re.M)


def test_the_credential_helper_reset_rides_in_git_config_parameters() -> None:
    code = _code(MERGER)
    assert "credential.helper" in code and "GIT_CONFIG_PARAMETERS" in code
    assert not re.search(r'GIT_CONFIG_KEY_\$m"\s+-Value\s+"credential\.helper"', code)


def test_git_reads_the_quoted_empty_reset() -> None:
    env = dict(os.environ, GIT_CONFIG_PARAMETERS="'credential.helper'=''")
    out = subprocess.run(
        ["git", "config", "--show-origin", "--get-all", "credential.helper"],
        capture_output=True, text=True, env=env, cwd=ROOT, check=True,
    )  # fmt: skip
    assert out.stdout.splitlines()[-1].split("\t") == ["command line:", ""]


def test_the_merger_identity_loads_only_after_the_clone_is_on_live() -> None:
    code = _code(GATE)
    fetch = code.index("fetch -q --no-tags origin")
    checkout = code.index("checkout -q -f --detach")
    load = code.index(". $mergerEnv")
    assert fetch < checkout < load
    assert code.index("sparse-checkout set") < load
    # and the gh login check still runs before anything that uses gh
    assert load < code.index("auth status") < code.index("live_first_ci.py")
