"""trusted-eval counts the base tests it must see run (#646: it counted 0 on every PR).

The count greps node ids (`::`) out of `pytest --co`. pyproject's addopts already pass one -q,
which prints node ids; a second -q prints `file: N` lines instead, so the count was 0 and the job
failed every PR. This runs the workflow's own count command on a real test file.
"""

from __future__ import annotations

import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "trusted-eval.yml"


def _count_command() -> list[str]:
    line = next(ln for ln in WORKFLOW.read_text(encoding="utf-8").splitlines()
                if ln.strip().startswith("want=$(pytest"))  # fmt: skip
    m = re.search(r'want=\$\((pytest [^|]*?)"\$\{present\[@\]\}"', line)
    assert m, line
    return shlex.split(m.group(1))


def test_the_count_command_sees_node_ids() -> None:
    cmd = _count_command()
    assert "-q" not in cmd and "-qq" not in cmd  # addopts supplies the one -q
    target = "tests/ops/test_trusted_eval_collect_count.py"
    out = subprocess.run([sys.executable, "-m", *cmd, target], cwd=ROOT, capture_output=True,
                         text=True, check=False, timeout=120).stdout  # fmt: skip
    assert sum("::" in ln for ln in out.splitlines()) >= 2, out
