"""THE PUBLISHED-GAP CONTRACT — one shape every detector emits, so the queue stops growing cases.

THE DEFECT THIS CLOSES, and it was called the same day it was created. `run_max_push.py` merges
every "not yet at 100%" source into one ranked queue, and each source arrives as a bespoke
`_from_*` reader that knows the shape of one artifact. Adding the stranding detector added a tenth
one. The principal's warning was immediate and correct: *"don't let run_max_push become an
ever-growing pile of special cases — make its input contract generic."*

WHY A BESPOKE READER PER SOURCE IS WORSE THAN IT LOOKS. It is not merely repetitive. Every new
detector has to be accepted by the QUEUE before its findings can be ranked, so the queue owner
becomes a gatekeeper on discovery: a detector written today cannot influence tomorrow's priorities
until somebody edits the ranker. That is the same shape as the defect the desk keeps finding —
capability that exists and cannot reach a decision — with the ranker itself as the bottleneck.

THE CONTRACT. A detector publishes `Gap` rows to `data/published_gaps/<detector>.json` and is done.
The queue globs that directory, so a detector added tomorrow ranks tomorrow with no edit anywhere.

    Gap(aspect, source, current, ceiling, detail, action, artifact, ...)

`current=None` IS THE LOAD-BEARING FIELD. It means UNMEASURED, and unmeasured outranks
partially-complete by design (L1.28a): an aspect at 60% is a known quantity being worked, an aspect
with no number is an unknown being ignored, and the desk's expensive defects have all lived in the
second class. A detector that cannot measure something must publish `None` rather than skip the row
— skipping is what makes an unknown look like a zero.

LEVERAGE IS DECLARED, NOT COMPUTED, and this module keeps that property rather than quietly
introducing an EV model. A detector names an existing source class; it cannot invent a weight. An
unknown class raises instead of defaulting, because a silent default would let any new detector
outrank the money path by accident.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "PUBLISHED_DIR",
    "Gap",
    "load_published",
    "publish",
    "to_queue_rows",
]

_ROOT = Path(__file__).resolve().parents[2]

#: Where detectors drop their rows. One file per detector, overwritten each run: the queue wants
#: TODAY's gaps, and an append-only log would rank a closed gap forever.
PUBLISHED_DIR = _ROOT / "data" / "published_gaps"

#: The source classes a detector may claim. Deliberately the SAME vocabulary `run_max_push`
#: already weights -- a detector that could mint a class could mint a weight, and the whole
#: honesty of the ranking is that weights are argued in one visible place.
KNOWN_SOURCES: frozenset[str] = frozenset({
    "money_path_correctness", "capital_utilisation", "evidence_throughput", "unenforced_law",
    "dormant_capability", "measurement_quality", "open_defect", "conversion_debt",
    "calibration_debt", "tier1_process_gap",
})


@dataclass(frozen=True)
class Gap:
    """One measurable distance between where an aspect is and where it could be.

    `current is None` means UNMEASURED and is never a synonym for zero. `ceiling` is the value at
    which the aspect would be complete, in whatever unit `current` uses; a fraction-of-1.0 aspect
    passes `ceiling=1.0`.
    """

    aspect: str
    source: str
    current: float | None
    ceiling: float
    detail: str
    action: str
    artifact: str
    #: Free-form provenance the ranker does not read but a human triaging the row will want.
    evidence: str = ""
    dependency: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.source not in KNOWN_SOURCES:
            raise ValueError(
                f"unknown gap source {self.source!r}. A detector may not mint a source class: "
                "the leverage weights are argued in ONE visible place (run_max_push._LEVERAGE) "
                f"and a new class would be a new weight nobody reviewed. Known: "
                f"{sorted(KNOWN_SOURCES)}")
        if self.ceiling <= 0:
            raise ValueError(f"ceiling must be positive, got {self.ceiling!r}")
        if not self.action.strip():
            raise ValueError(
                f"gap {self.aspect!r} has no action. A row nobody can act on is a complaint, and "
                "the queue exists to be worked rather than read")

    @property
    def measured(self) -> bool:
        return self.current is not None

    @property
    def gap_fraction(self) -> float:
        """1.0 when unmeasured -- the maximum, because an unknown quantity is being ignored."""
        if self.current is None:
            return 1.0
        return max(0.0, min(1.0, (self.ceiling - float(self.current)) / self.ceiling))


def publish(detector: str, gaps: Iterable[Gap], *, directory: Path | None = None) -> Path:
    """Write one detector's rows. OVERWRITES: the queue ranks today's gaps, not history.

    An empty iterable writes an empty list rather than deleting the file, because "this detector
    ran and found nothing" and "this detector has never run" are different facts and only the
    file's presence distinguishes them.
    """
    d = directory or PUBLISHED_DIR
    d.mkdir(parents=True, exist_ok=True)
    rows = [{"aspect": g.aspect, "source": g.source, "current": g.current, "ceiling": g.ceiling,
             "detail": g.detail, "action": g.action, "artifact": g.artifact,
             "evidence": g.evidence, "dependency": g.dependency, "tags": list(g.tags)}
            for g in gaps]
    path = d / f"{detector}.json"
    path.write_text(json.dumps(
        {"detector": detector, "generated": datetime.now(tz=UTC).isoformat(), "gaps": rows},
        indent=1), "utf-8")
    return path


def load_published(*, directory: Path | None = None) -> list[Gap]:
    """Every detector's current rows. A malformed row is SKIPPED, never guessed at.

    Skipping is right here and wrong in `publish`: a row the queue cannot parse has no aspect it
    could name, so there is nothing to report as unmeasured -- whereas a detector that measured
    nothing has a subject and must say so.
    """
    d = directory or PUBLISHED_DIR
    if not d.is_dir():
        return []
    out: list[Gap] = []
    for f in sorted(d.glob("*.json")):
        try:
            doc = json.loads(f.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        for row in (doc.get("gaps") or []) if isinstance(doc, dict) else []:
            if not isinstance(row, dict):
                continue
            try:
                cur = row.get("current")
                out.append(Gap(
                    aspect=str(row["aspect"]), source=str(row["source"]),
                    current=None if cur is None else float(cur),
                    ceiling=float(row.get("ceiling", 1.0)),
                    detail=str(row.get("detail", "")), action=str(row.get("action", "")),
                    artifact=str(row.get("artifact", str(f))),
                    evidence=str(row.get("evidence", "")),
                    dependency=str(row.get("dependency", "")),
                    tags=tuple(str(t) for t in (row.get("tags") or []))))
            except (KeyError, TypeError, ValueError):
                continue
    return out


def to_queue_rows(gaps: Iterable[Gap], item: Any) -> list[dict[str, Any]]:
    """Render published gaps through the queue's own `_item` builder.

    THE SCORING STAYS IN THE QUEUE ON PURPOSE. This module could compute a score and would then
    be a second place where priority is decided -- two rankers that can disagree is worse than a
    bespoke reader per source, which is at least wrong in one place.
    """
    return [item(g.aspect, g.source, g.current, g.ceiling, g.detail, g.action, g.artifact)
            for g in gaps]
