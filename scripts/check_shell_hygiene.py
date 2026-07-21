"""Shell-hygiene gate for the ops/ launcher scripts (CI step, 2026-07-20).

Why this exists: on 2026-07-19 an unescaped ``$300`` inside run_cro_ai.sh's double-quoted
PROMPT expanded as positional ``$3`` + "00" under ``set -u`` and crashed the brain launcher
BEFORE it reached Claude -- the desk lost a full reasoning day during an open dead-man
incident, silently (no log file was even created). Two independent micro-auditors converged
on gating this class in CI (2026-07-20 inbox: kimi shellcheck/dry-run, mistral pre-commit
lint). Three layers, cheapest-first:

1. ``bash -n`` syntax check on every ops/*.sh (catches plain syntax rot);
2. an unescaped ``$NN`` scan: ``$`` followed by 2+ digits in a shell script is almost
   certainly a money literal, never a positional (those are single-digit or ``${10}``) --
   this is the static check that WOULD have caught $300, which ``bash -n`` cannot;
3. a full dry-run of run_cro_ai.sh (BRAIN_DRY_RUN=1): builds the entire prompt under
   ``set -u`` with zero auth/network/token/log side effects, so ANY future bad expansion
   in the prompt assembly fails CI instead of killing a live cycle.

    .venv/bin/python scripts/check_shell_hygiene.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_OPS = _ROOT / "ops"

# unescaped $ then 2+ digits (a preceding backslash escapes it; $1..$9 positionals are fine)
_MONEY_LITERAL = re.compile(r"(?<!\\)\$[0-9]{2,}")


def main() -> int:
    failures: list[str] = []
    scripts = sorted(_OPS.glob("*.sh"))
    if not scripts:
        print("FAIL: no ops/*.sh found -- gate misconfigured")
        return 1

    for sh in scripts:
        r = subprocess.run(["bash", "-n", str(sh)], capture_output=True, text=True, check=False)
        if r.returncode != 0:
            failures.append(f"bash -n {sh.name}: {r.stderr.strip()[:200]}")
        for i, line in enumerate(sh.read_text("utf-8").splitlines(), 1):
            if _MONEY_LITERAL.search(line):
                failures.append(
                    f"{sh.name}:{i}: unescaped $<digits> literal (the 2026-07-19 crash "
                    f"class) -- escape as \\$ : {line.strip()[:120]}")

    r = subprocess.run(["bash", str(_OPS / "run_cro_ai.sh")], capture_output=True, text=True,
                       env={"BRAIN_DRY_RUN": "1", "PATH": "/usr/bin:/bin", "HOME": "/home/quant"},
                       cwd=str(_ROOT), check=False)
    if r.returncode != 0 or "DRY-RUN OK" not in r.stdout:
        failures.append(f"run_cro_ai.sh dry-run failed (rc={r.returncode}): "
                        f"{(r.stderr or r.stdout).strip()[:200]}")

    for f in failures:
        print(f"FAIL: {f}")
    print("shell hygiene:", "ALL OK" if not failures else f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
