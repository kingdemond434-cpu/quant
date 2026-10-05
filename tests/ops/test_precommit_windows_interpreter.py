"""Execute the real commit hook in owned repos with both venv layouts."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / "ops/githooks/pre-commit"


@pytest.mark.parametrize("layout", ["bin/python", "Scripts/python.exe"])
@pytest.mark.parametrize("first_status", [0, 7])
def test_real_hook_preserves_guard_order_and_status(tmp_path, layout, first_status):
    bash = shutil.which("bash")
    if os.name == "nt":
        candidate = Path("C:/Program Files/Git/bin/bash.exe")
        bash = str(candidate) if candidate.is_file() else bash
    if not bash:
        pytest.skip("no Bash available to execute the repository hook")
    python = tmp_path / ".venv" / layout
    python.parent.mkdir(parents=True)
    # The launcher is an actual executable shim, not a textual hook inspection.
    executable = Path(sys.executable).as_posix().replace("'", "'\"'\"'")
    python.write_text("#!/bin/sh\nexec '" + executable + "' \"$@\"\n", encoding="utf-8")
    python.chmod(0o755)
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name, status in (("moneypath_precommit_guard.py", first_status),
                         ("check_protected_records.py", 0)):
        (scripts / name).write_text(
            "from pathlib import Path\nimport sys\n"
            "with Path('invocations.jsonl').open('a') as f: f.write("
            + repr(json.dumps(name) + "\n") + ")\n"
            + "sys.exit(" + str(status) + ")\n", encoding="utf-8")
    result = subprocess.run([bash, str(HOOK)], cwd=tmp_path, capture_output=True,
                            text=True, timeout=30)
    assert result.returncode == first_status, result.stderr
    calls = [json.loads(line) for line in (tmp_path / "invocations.jsonl").read_text().splitlines()]
    assert calls == (["moneypath_precommit_guard.py", "check_protected_records.py"]
                     if first_status == 0 else ["moneypath_precommit_guard.py"])
