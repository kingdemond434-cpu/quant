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
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FLOOR_PER_PASS = 200
CIV_SHARE = 0.10                 # of the judge's measured hourly capacity
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


def release_budget(load: JudgeLoad, *, passes_per_day: int = 24) -> int:
    """Candidates the civilizations may donate this pass."""
    if not load.measured or not load.capacity_per_day:
        return FLOOR_PER_PASS
    share = load.capacity_per_day * CIV_SHARE / max(1, passes_per_day)
    if load.draining:
        share *= 2
    return max(FLOOR_PER_PASS, int(share))


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

    def park(self, rows: Iterable[Mapping[str, Any]]) -> int:
        n = 0
        with self.path.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(dict(r), default=str, ensure_ascii=False) + "\n")
                n += 1
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
        with self.released_path.open("a", encoding="utf-8") as fh:
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
