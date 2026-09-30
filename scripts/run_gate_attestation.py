"""Run the three fast gates on THIS box and bind the result to its HEAD.

The closed-loop attestation's `release_authority.tested_sha_matches` and `ci_green` read
data/gate_attestation.json, and the seal is written unattended without the suite. So the box
measures itself: ruff over the tree, mypy over the configured files, pytest collection -- the
same three the shared gate runs -- and `scripts/gate_attestation.py` records pass or fail on
the exact running sha. Every adopt moves HEAD, so this runs on a clock (task MT5-GateAttest,
every two hours) and after an adopt the next run re-binds. A gate that fails is recorded as
fail; nothing here can turn a red gate green.

    python scripts/run_gate_attestation.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_REPORT = ROOT / "data" / "gate_attestation_run.json"

# The recorder performs multiple independent Git reads. On the Windows trading checkout each is
# deliberately bounded at 60 seconds, so a 120-second wrapper could kill an otherwise completed
# gate run before ``gate_attestation.json`` was written. Three reads plus process startup fit in
# this budget and remain below the scheduled task's 30-minute hard limit. This changes only the
# time allowed to RECORD the verdict; it does not change a gate or turn a failure into a pass.
ATTEST_RECORD_TIMEOUT_S = 300


def _run(args: list[str], timeout: int = 1500) -> tuple[int, str, float]:
    t0 = time.time()
    r = subprocess.run(args, capture_output=True, text=True, cwd=str(ROOT), timeout=timeout)
    tail = "\n".join(((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-2:])
    return r.returncode, tail, round(time.time() - t0, 1)


def main() -> int:
    py = sys.executable
    gates = {
        "ruff": [py, "-m", "ruff", "check", "."],
        "mypy": [py, "-m", "mypy"],
        "collect": [py, "-m", "pytest", "--co", "-q", "-p", "no:cacheprovider"],
    }
    results: dict[str, tuple[int, str, float]] = {}
    for name, cmd in gates.items():
        try:
            results[name] = _run(cmd)
        except Exception as exc:                          # a gate that cannot run is a failure
            results[name] = (1, f"{type(exc).__name__}: {exc}", 0.0)
        rc, tail, s = results[name]
        print(f"{name}: rc={rc} in {s}s -- {tail.replace(chr(10), ' | ')[:160]}")
    verdict = "pass" if all(rc == 0 for rc, _, _ in results.values()) else "fail"
    # Persist the component verdicts before the subject recorder. If recording the Git-bound
    # attestation fails, operators still see which gate was red versus a plumbing failure.
    RUN_REPORT.parent.mkdir(parents=True, exist_ok=True)
    RUN_REPORT.write_text(json.dumps({
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "verdict": verdict,
        "gates": {name: {"rc": rc, "tail": tail, "seconds": seconds}
                  for name, (rc, tail, seconds) in results.items()},
    }, indent=1), encoding="utf-8")
    rc, tail, _ = _run([py, "scripts/gate_attestation.py", "--gates", "fast", "--result", verdict],
                       timeout=ATTEST_RECORD_TIMEOUT_S)
    print(f"attestation: {verdict} rc={rc} ({tail[:120]})")
    # A verdict that was never persisted is not an attestation.  Previously the wrapper ignored
    # recorder failure and returned the gate verdict, so the task looked like an ordinary red
    # gate while consumers kept reading yesterday's file.  Distinguish infrastructure failure.
    if rc != 0:
        return 2
    return 0 if verdict == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
