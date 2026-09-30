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
TEST_MANIFEST = ROOT / "data" / "gate_test_manifest.txt"

# The recorder performs multiple independent Git reads. On the Windows trading checkout each is
# deliberately bounded at 60 seconds, so a 120-second wrapper could kill an otherwise completed
# gate run before ``gate_attestation.json`` was written. Three reads plus process startup fit in
# this budget and remain below the scheduled task's 30-minute hard limit. This changes only the
# time allowed to RECORD the verdict; it does not change a gate or turn a failure into a pass.
ATTEST_RECORD_TIMEOUT_S = 300


def _run(args: list[str], timeout: int = 1500) -> tuple[int, str, float]:
    t0 = time.time()
    r = subprocess.run(args, capture_output=True, text=True, cwd=str(ROOT), timeout=timeout,
                       encoding="utf-8", errors="replace")
    tail = "\n".join(((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-2:])
    return r.returncode, tail, round(time.time() - t0, 1)


def _tracked_python_paths() -> tuple[list[str], str]:
    """Return the exact committed Python/Ruff population without crawling runtime data."""
    try:
        r = subprocess.run(["git", "ls-files", "*.py", "*.pyi", "*.ipynb"], cwd=str(ROOT),
                           capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=120,
                           check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return [], f"{type(exc).__name__}: {exc}"
    if r.returncode != 0:
        return [], (r.stderr or f"git ls-files rc={r.returncode}").strip()[-300:]
    paths = [rel for rel in r.stdout.splitlines() if rel.strip()]
    return paths, "" if paths else "tracked Python manifest is empty"


def _ruff_discovered_paths(py: str) -> tuple[list[str], str]:
    """Return Ruff's normal ``check .`` population without linting untracked scratch files."""
    try:
        r = subprocess.run([py, "-m", "ruff", "check", "--show-files", "."], cwd=str(ROOT),
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=120, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return [], f"{type(exc).__name__}: {exc}"
    if r.returncode != 0:
        return [], (r.stderr or f"ruff --show-files rc={r.returncode}").strip()[-300:]
    paths: list[str] = []
    for raw in r.stdout.splitlines():
        if not raw.strip():
            continue
        path = Path(raw.strip())
        try:
            paths.append(path.resolve().relative_to(ROOT.resolve()).as_posix())
        except ValueError:
            return [], f"Ruff discovered a path outside the release root: {path}"
    return paths, "" if paths else "Ruff discovery manifest is empty"


def _tracked_test_manifest(paths: list[str]) -> tuple[Path | None, str]:
    """Materialize pytest's tracked ``testpaths`` population without crawling runtime data."""
    tests = []
    for rel in paths:
        normalized = Path(rel).as_posix()
        # pyproject.toml declares testpaths=["tests"]. Operational scripts elsewhere may be
        # named test_*.py but are executable probes, not pytest modules; importing one during a
        # gate once opened a real SSH miner. Preserve pytest's canonical discovery boundary.
        if not normalized.startswith("tests/"):
            continue
        name = Path(rel).name
        if name.startswith("test_") or name.endswith("_test.py"):
            tests.append(rel)
    if not tests:
        return None, "tracked test manifest is empty"
    TEST_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    TEST_MANIFEST.write_text("\n".join(tests) + "\n", encoding="utf-8")
    return TEST_MANIFEST, ""


def _run_tracked_ruff(py: str, paths: list[str], chunk_size: int = 180) -> tuple[int, str, float]:
    """Lint Ruff's canonical discovery population in Windows-safe command-line chunks."""
    started = time.time()
    failures: list[str] = []
    for offset in range(0, len(paths), chunk_size):
        rc, tail, _ = _run([py, "-m", "ruff", "check", *paths[offset:offset + chunk_size]])
        if rc != 0:
            failures.append(tail)
    return (1 if failures else 0,
            "\n".join(failures[-4:]) if failures else "All tracked checks passed!",
            round(time.time() - started, 1))


def main() -> int:
    py = sys.executable
    tracked_paths, tracked_error = _tracked_python_paths()
    ruff_paths, ruff_error = _ruff_discovered_paths(py)
    manifest, manifest_error = (_tracked_test_manifest(tracked_paths)
                                if tracked_paths else (None, tracked_error))
    gates = {
        "mypy": [py, "-m", "mypy"],
    }
    results: dict[str, tuple[int, str, float]] = {
        "ruff": (_run_tracked_ruff(py, ruff_paths) if ruff_paths else
                 (1, f"Ruff manifest unavailable: {ruff_error}", 0.0)),
    }
    rc, tail, seconds = results["ruff"]
    print(f"ruff: rc={rc} in {seconds}s -- {tail.replace(chr(10), ' | ')[:160]}")
    for name, cmd in gates.items():
        try:
            results[name] = _run(cmd)
        except Exception as exc:                          # a gate that cannot run is a failure
            results[name] = (1, f"{type(exc).__name__}: {exc}", 0.0)
        rc, tail, s = results[name]
        print(f"{name}: rc={rc} in {s}s -- {tail.replace(chr(10), ' | ')[:160]}")
    if manifest is None:
        results["collect"] = (1, f"manifest unavailable: {manifest_error}", 0.0)
    else:
        try:
            results["collect"] = _run(
                [py, "-m", "pytest", "--co", "-q", "-p", "no:cacheprovider",
                 f"@{manifest}"],
            )
        except Exception as exc:
            results["collect"] = (1, f"{type(exc).__name__}: {exc}", 0.0)
    rc, tail, seconds = results["collect"]
    print(f"collect: rc={rc} in {seconds}s -- {tail.replace(chr(10), ' | ')[:160]}")
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
