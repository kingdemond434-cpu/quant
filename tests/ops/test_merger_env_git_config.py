"""The gate's git calls died at rc 128 on every sweep from 2026-11-05 to 11-13 (box repro):
merger_env.ps1 set GIT_CONFIG_VALUE_n to "", which Windows PowerShell 5.1 turns into a DELETED
variable, so git read GIT_CONFIG_COUNT naming a value that did not exist. And the gate loaded
that file from its stale clone before fetching, so no fix could reach it. #1089 fixed the empty
value (kernel32 SetEnvironmentVariableW keeps ""); this pins that, and the load order."""

from __future__ import annotations

import re
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


def test_the_empty_credential_helper_reset_is_set_so_it_survives() -> None:
    code = _code(MERGER)
    assert "credential.helper" in code
    # never through Set-Item env: or $env: (PowerShell deletes a variable set to "")
    assert 'SetEnvironmentVariable("GIT_CONFIG_VALUE_$m", "")' in code
    assert "throw" in code.split('SetEnvironmentVariable("GIT_CONFIG_VALUE_$m"', 1)[1][:120]


def test_the_merger_identity_loads_only_after_the_clone_is_on_live() -> None:
    code = _code(GATE)
    fetch = code.index("fetch -q --no-tags origin")
    checkout = code.index("checkout -q -f --detach")
    load = code.index(". $mergerEnv")
    assert fetch < checkout < load
    assert code.index("sparse-checkout set") < load
    # and the gh login check still runs before anything that uses gh
    assert load < code.index("auth status") < code.index("live_first_ci.py")
