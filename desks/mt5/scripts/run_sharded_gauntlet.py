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
from uuid import uuid4

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


def _retry_attempts() -> int:
    """Retries after the parallel attempt; invalid values fall closed to two."""
    try:
        return max(0, int(os.environ.get("GAUNTLET_SHARD_RETRIES", "2")))
    except (TypeError, ValueError):
        return 2


def _parallelism(n: int) -> int:
    """Bound the first wave so judge children do not exhaust committed memory.

    Two concurrent shards is the production-safe default measured after a 15-wide wave caused
    fourteen child failures.  Operators may raise the cap after measuring peak committed memory;
    malformed configuration falls closed to one child.
    """
    raw = os.environ.get("GAUNTLET_SHARD_CONCURRENCY")
    if raw is None:
        configured = 2
    else:
        try:
            configured = int(raw)
        except (TypeError, ValueError):
            configured = 1
    return max(1, min(n, configured))


def dispatch(shard_dir: Path, n: int, phase: str) -> None:
    """Run every judge-owned shard, retrying only failed children at low concurrency.

    Publication remains fail closed: a shard that still fails after the bounded retries raises,
    so the sealed judge cannot merge a partial result.  The retries are deliberately serial.
    A measured production failure mode had ten of fifteen memory-heavy shards finish, five die,
    and the next scheduled invocation discard all ten successful artifacts before repeating the
    two-hour pre-warm.  Retaining the successful outputs and rerunning only the failed children
    after the parallel wave has released its memory converts that restart loop into progress
    without changing a gate, verdict, docket, or merge rule.
    """
    code = (
        "import sys;"
        f"sys.path[:0]=[{str(ROOT)!r},{str(DESK)!r}];"
        "from scripts.external_gauntlet import shard_worker;"
        "shard_worker(sys.argv[1],int(sys.argv[2]),sys.argv[3])"
    )

    # Python's reassignment of sys.stderr does not redirect a child's OS stderr handle.
    # Keep errors outside the judge's disposable shard directory, without buffering them
    # in the parent's memory. Every retry gets its own receipt.
    logs = shard_dir.parent / f"{shard_dir.name}-logs"
    logs.mkdir(parents=True, exist_ok=True)
    invocation = uuid4().hex

    def one(k: int, attempt: int = 0) -> None:
        receipt = logs / f"{invocation}-{phase}-{k}-attempt-{attempt}.log"
        with receipt.open("wb") as output:
            output.write(f"{datetime.now(UTC).isoformat()} {phase} shard={k} "
                         f"attempt={attempt}\n".encode())
            output.flush()
            try:
                run([sys.executable, "-u", "-c", code, str(shard_dir), str(k), phase],
                    cwd=DESK, env=os.environ.copy(), timeout=None, capture_output=False,
                    stdout=output, stderr=output, check=True)
            except Exception as exc:
                raise RuntimeError(f"{phase} shard {k} failed; child log={receipt}") from exc

    def attempted(k: int) -> tuple[int, Exception | None]:
        try:
            one(k)
        except Exception as exc:  # child exit/OOM is evidence, then retried below
            return k, exc
        return k, None

    with ThreadPoolExecutor(max_workers=_parallelism(n),
                            thread_name_prefix=f"judge-{phase}") as pool:
        # Consume every result even when one child fails, so successful shard artifacts survive.
        first = list(pool.map(attempted, range(n)))

    failed = [(k, exc) for k, exc in first if exc is not None]
    if failed:
        print(f"SHARD RECOVERY: {len(failed)}/{n} {phase} shard(s) failed in parallel; "
              "retrying only those shards serially after peer memory was released", flush=True)
    for k, first_exc in failed:
        assert first_exc is not None
        last_exc = first_exc
        for attempt in range(1, _retry_attempts() + 1):
            try:
                one(k, attempt)
                print(f"SHARD RECOVERY: {phase} shard {k} recovered on retry {attempt}",
                      flush=True)
                break
            except Exception as exc:
                last_exc = exc
                print(f"SHARD RECOVERY: {phase} shard {k} retry {attempt} failed: "
                      f"{type(exc).__name__}: {exc}", flush=True)
        else:
            attempts = _retry_attempts() + 1
            raise RuntimeError(
                f"{phase} shard {k} failed after {attempts} attempt(s); refusing partial merge"
            ) from last_exc


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
                f"runtime={sys.executable} shards={_shards()} "
                f"shard_concurrency={_parallelism(_shards())}",
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
