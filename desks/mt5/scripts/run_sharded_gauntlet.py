"""Launch the canonical judge through its existing fail-closed shard protocol.

The sealed judge owns every statistical decision.  This launcher only supplies the
parallel dispatcher that ``external_gauntlet.run_sharded`` deliberately exposes.
Each planned cell is assigned by the judge's own stable partition, returned once,
and merged by the judge before any authority artifact is written.
"""
from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _path in (str(ROOT), str(DESK)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from libs.ops.proctree import run  # noqa: E402


def _shards() -> int:
    """Read the measured shard count, falling closed to the serial judge."""
    try:
        return max(1, int(os.environ.get("GAUNTLET_SHARDS", "1")))
    except (TypeError, ValueError):
        return 1


def dispatch(shard_dir: Path, n: int, phase: str) -> None:
    """Run every judge-owned shard once; any missing/failed child aborts publication."""
    code = (
        "import sys;"
        f"sys.path[:0]=[{str(ROOT)!r},{str(DESK)!r}];"
        "from scripts.external_gauntlet import shard_worker;"
        "shard_worker(sys.argv[1],int(sys.argv[2]),sys.argv[3])"
    )

    def one(k: int) -> None:
        run(
            [sys.executable, "-u", "-c", code, str(shard_dir), str(k), phase],
            cwd=DESK,
            env=os.environ.copy(),
            timeout=None,
            capture_output=False,
            check=True,
        )

    with ThreadPoolExecutor(max_workers=n, thread_name_prefix=f"judge-{phase}") as pool:
        # Iterating forces every result; one failed process raises and the judge publishes nothing.
        for _ in pool.map(one, range(n)):
            pass


def main() -> int:
    from research.judging_throughput import apply_env

    apply_env()
    log_path = DESK / "logs" / "MT5-Gauntlet.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", buffering=1) as log:
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = log
        try:
            print(
                f"{datetime.now(UTC).isoformat()} canonical sharded judge "
                f"runtime={sys.executable} shards={_shards()}",
                flush=True,
            )
            from scripts import external_gauntlet as judge

            if getattr(judge, "SHARD_PROTOCOL", None) != 2:
                raise RuntimeError(
                    "canonical judge does not expose the required fail-closed shard protocol v2"
                )
            return int(judge.run_sharded(_shards(), dispatch))
        finally:
            sys.stdout, sys.stderr = old_out, old_err


if __name__ == "__main__":
    raise SystemExit(main())
