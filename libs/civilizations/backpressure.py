"""BACKPRESSURE: discovery runs 24/7, the expensive judge is fed at the rate it can drain.

    zuck, 2026-09-30: "cheap extraction -> semantic dedup -> cheap falsifiers -> novelty test ->
    buildability check -> only then expensive judging. And dynamically reduce candidate emission
    from saturated areas while continuing source discovery."

    standing rule (2026-09-29): never reduce information gathering, raw cell mining or research
    generation; close the backlog by adding capacity, never by throttling generation.

The two are compatible because what is paced here is DONATION, not mining: every candidate is
still extracted, deduplicated, falsified, novelty-scored and written to the durable PARKED
queue (nothing is dropped), and the knowledge graph, catalogues and coverage tensor take every
item at once. Only the hand-off to the sealed gauntlet waits, highest priority first, at a rate
that does not grow the judge's measured backlog. When `JUDGE_COVERAGE.json` says the judge is
draining, the release rate rises with it; when the backlog is UNMEASURED the floor rate applies
(never zero -- a missing report must not silence a civilization).

Priority (lexicographic): new mechanism skeleton > low crowding prior > published over
transferred > unsaturated area > older. An AREA (civilization x skeleton-or-family) is saturated
after SATURATION_JUDGED judged cells with no survivor; its candidates keep parking at 1/10th
weight so a slow area is sampled, never abandoned.
"""
from __future__ import annotations

import json
import os
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FLOOR_PER_HOUR = 200
FLOOR_PER_PASS = FLOOR_PER_HOUR   # kept for callers; the budget is HOURLY across all processes
CIV_SHARE = 0.10                 # of the judge's measured daily capacity, spread over 24 hours
GROWTH_WINDOW_H = 1.0            # the backlog is GROWING when it rose over this window
LOCK_STALE_S = 1800
SATURATION_JUDGED = 50
SATURATED_WEIGHT = 0.1
CROWDING_RANK = {"low": 0, "medium": 1, "UNMEASURED": 1, "high": 2}


@dataclass
class JudgeLoad:
    unjudged: int | None
    capacity_per_day: int | None
    draining: bool | None

    @property
    def measured(self) -> bool:
        return self.unjudged is not None


def judge_load(report: Path) -> JudgeLoad:
    try:
        t = (json.loads(Path(report).read_text("utf-8")).get("totals") or {})
    except (OSError, ValueError, AttributeError):
        return JudgeLoad(None, None, None)
    un = t.get("unjudged_total")
    cap = t.get("capacity_measured")
    drain = str(t.get("drain_status") or "").upper()
    return JudgeLoad(int(un) if isinstance(un, (int, float)) else None,
                     int(cap) if isinstance(cap, (int, float)) else None,
                     True if "DRAIN" in drain and "NOT" not in drain else
                     False if drain else None)


def release_budget(load: JudgeLoad, *, passes_per_day: int = 24,
                   growing: bool | None = None) -> int:
    """Candidates the civilizations may donate PER HOUR (all processes together).

    Ordered on the judge's own backlog signal: while the measured backlog is GROWING (and the
    judge is not draining) the civilizations donate nothing -- their candidates stay PARKED,
    mining and parking continue, and the pause is published. A backlog that is not measured
    gets the floor, never zero (a missing report must not silence a civilization)."""
    if not load.measured:
        return FLOOR_PER_HOUR
    if growing and not load.draining:
        return 0
    if not load.capacity_per_day:
        return FLOOR_PER_HOUR
    share = load.capacity_per_day * CIV_SHARE / max(1, passes_per_day)
    if load.draining:
        share *= 2
    return max(FLOOR_PER_HOUR, int(share))


def backlog_growing(history: Path, load: JudgeLoad, *, now: float | None = None) -> bool | None:
    """Record this reading and say whether the backlog ROSE over GROWTH_WINDOW_H. None while
    there is no reading at least that old (UNMEASURED, never 'not growing')."""
    t = time.time() if now is None else now
    rows: list[tuple[float, int]] = []
    try:
        for ln in Path(history).read_text("utf-8").splitlines():
            try:
                a, b = ln.split()
                rows.append((float(a), int(b)))
            except ValueError:
                continue
    except OSError:
        pass
    if load.unjudged is not None:
        rows.append((t, int(load.unjudged)))
        rows = [r for r in rows if r[0] >= t - 48 * 3600][-2000:]
        Path(history).parent.mkdir(parents=True, exist_ok=True)
        Path(history).write_text("".join(f"{a} {b}\n" for a, b in rows), "utf-8")
    old = [b for a, b in rows if a <= t - GROWTH_WINDOW_H * 3600]
    if not old or load.unjudged is None:
        return None
    return int(load.unjudged) > old[-1]


def released_within(log: Path, seconds: float, *, now: float | None = None) -> int:
    t = time.time() if now is None else now
    n = 0
    try:
        for ln in Path(log).read_text("utf-8").splitlines():
            try:
                a, b = ln.split()
            except ValueError:
                continue
            if float(a) >= t - seconds:
                n += int(b)
    except OSError:
        return 0
    return n


def log_release(log: Path, n: int, *, now: float | None = None) -> None:
    with Path(log).open("a", encoding="utf-8") as fh:
        fh.write(f"{time.time() if now is None else now} {int(n)}\n")


class FileLock:
    """A cross-process lock that works on Windows and POSIX: an O_EXCL lock file, broken when
    older than LOCK_STALE_S (a process that died holding it). `acquire(wait_s=0)` never blocks."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.held = False

    def acquire(self, wait_s: float = 0.0) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        end = time.monotonic() + max(0.0, wait_s)
        while True:
            try:
                fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, f"{os.getpid()} {time.time()}".encode())
                os.close(fd)
                self.held = True
                return True
            except FileExistsError:
                try:
                    if time.time() - self.path.stat().st_mtime > LOCK_STALE_S:
                        self.path.unlink(missing_ok=True)
                        continue
                except OSError:
                    continue
            if time.monotonic() >= end:
                return False
            time.sleep(0.05)

    def release(self) -> None:
        if self.held:
            self.path.unlink(missing_ok=True)
            self.held = False

    def __enter__(self) -> FileLock:
        if not self.acquire(wait_s=30.0):
            raise TimeoutError(f"lock {self.path} held")
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()


def priority(c: Mapping[str, Any], *, saturated: bool) -> tuple[Any, ...]:
    return (0 if c.get("novel_skeleton") else 1,
            CROWDING_RANK.get(str(c.get("crowding_prior") or "UNMEASURED"), 1),
            0 if c.get("published") else 1,
            1 if saturated else 0,
            str(c.get("parked_at") or ""))


class ParkedQueue:
    """Append-only JSONL of parked candidates + a released-id set. Durable across passes."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.released_path = self.path.with_suffix(".released.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # the resident and the hourly leg share this queue: every append holds the lock
        self.lock = FileLock(self.path.with_suffix(".lock"))

    def park(self, rows: Iterable[Mapping[str, Any]]) -> int:
        n = 0
        body = "".join(json.dumps(dict(r), default=str, ensure_ascii=False) + "\n"
                       for r in rows)
        if not body:
            return 0
        with self.lock, self.path.open("a", encoding="utf-8") as fh:
            fh.write(body)
            n = body.count("\n")
        return n

    def _released(self) -> set[str]:
        try:
            return {ln.strip() for ln in self.released_path.read_text("utf-8").splitlines()
                    if ln.strip()}
        except OSError:
            return set()

    def pending(self) -> list[dict[str, Any]]:
        done = self._released()
        out = []
        try:
            with self.path.open(encoding="utf-8") as fh:
                for ln in fh:
                    try:
                        r = json.loads(ln)
                    except ValueError:
                        continue
                    if isinstance(r, dict) and r.get("candidate_id") not in done:
                        out.append(r)
        except OSError:
            return []
        return out

    def mark_released(self, ids: Iterable[str]) -> None:
        with self.lock, self.released_path.open("a", encoding="utf-8") as fh:
            for i in ids:
                fh.write(f"{i}\n")
            fh.flush()
            os.fsync(fh.fileno())


def select(pending: list[dict[str, Any]], budget: int,
           saturated_areas: set[str]) -> list[dict[str, Any]]:
    """The candidates to release now: priority order, saturated areas sampled at 1/10."""
    ranked = sorted(pending, key=lambda c: priority(c, saturated=c.get("area")
                                                    in saturated_areas))
    out: list[dict[str, Any]] = []
    sat_seen = 0
    for c in ranked:
        if len(out) >= budget:
            break
        if c.get("area") in saturated_areas:
            sat_seen += 1
            if sat_seen % int(1 / SATURATED_WEIGHT):
                continue
        out.append(c)
    return out


# ------------------------------------------------------------------------ cheap falsifiers
def cheap_falsify(expr: Any, *, max_depth: int = 5) -> str | None:
    """Static reasons a translated expression cannot be a real signal. None = passes."""
    def walk(e: Any) -> Iterable[Any]:
        yield e
        if isinstance(e, list):
            for c in e[1:]:
                yield from walk(c)
    nodes = list(walk(expr))
    if not isinstance(expr, list):
        return "bare terminal"
    for n in nodes:
        if isinstance(n, list) and n and n[0] == "delay" and isinstance(n[-1], (int, float)) \
                and n[-1] < 0:
            return "negative delay reads the future"
    terms = {n for n in nodes if isinstance(n, str)}
    if not terms:
        return "no terminal: constant signal"

    def d(e: Any) -> int:
        return 1 + max((d(c) for c in e[1:] if isinstance(c, list)), default=0) \
            if isinstance(e, list) else 0
    if d(expr) > max_depth + 2:
        return f"depth {d(expr)} beyond grammar limit"
    if expr[0] in ("neg", "abs", "sign") and isinstance(expr[1], str):
        return "a transformed raw price level is not a stationary signal"
    return None
