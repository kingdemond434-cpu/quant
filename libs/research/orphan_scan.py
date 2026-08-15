"""ORPHANS BEYOND MODULES — every producer whose output nothing consumes.

`dormancy` answers this for CODE: which module does nothing import, which script does nothing
schedule. That is one producer class out of many, and it is not the expensive one. The expensive
orphans are further down the chain, where the desk has already paid for the discovery:

    a dataset collected and turned into no feature
    a feature computed and used in no hypothesis
    a hypothesis written and never tested
    a recommendation accepted and never implemented
    a survivor validated and never portfolio-tested
    a failure recorded and never mined
    a near-survivor banked and never revisited

Each of those is value that reached the desk and stopped. NONE of them is visible to an importer
count, a scheduler check, or a test suite -- the code all works, the artifacts all exist, and the
chain is broken at a join nobody is watching. This is L1.54(a)'s CONVERSION_FAILURE state applied
to research objects rather than to Python modules.

WHY THIS IS A SCAN AND NOT A LEDGER. A ledger would require every producer to register its output,
which is a change to every producer and would be half-adopted forever. The scan reads the artifacts
the desk ALREADY writes and asks whether each stage's population appears downstream. It is
therefore approximate, and it is honest about that: a stage whose artifact is absent reports
UNMEASURED, never zero, because "nobody looked" and "nothing was stranded" are opposite facts and
only one of them is good news.

IT PUBLISHES RATHER THAN PRINTS. Rows go to the `gap_contract` channel, so the max-push queue ranks
them beside every other gap without anyone editing the ranker. Detection that cannot reach a
priority is half a control -- the exact defect that produced this module's sibling this morning.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from libs.research.gap_contract import Gap

__all__ = ["STAGES", "Stage", "StageCount", "scan", "to_gaps"]

_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Stage:
    """One join in the conversion chain and the canonical schemas on both sides."""

    name: str
    produced_artifact: str
    consumed_artifact: str
    #: Why a stranded object here is expensive, in the desk's own terms.
    why: str
    #: What to do about it -- required, because a row nobody can act on is a complaint.
    action: str
    source: str = "conversion_debt"
    produced_schema: str = "auto"
    consumed_schema: str = "auto"


#: The joins, ordered along the chain. Each names the artifact that holds the PRODUCED population
#: and the artifact that would show it was CONSUMED. Where the desk writes no such artifact yet,
#: the stage still appears and reports UNMEASURED -- an unwatched join is the finding.
STAGES: tuple[Stage, ...] = (
    Stage("data_to_feature", "data/data_universe_map.json", "data/feature_library.json",
          "a dataset collected and turned into no feature is storage cost with no research "
          "output, and it is the stage where the desk's own measurement showed the largest "
          "leak (catalog breadth ~8.5/10 against ingested-and-tested ~4.5/10)",
          "run the Stage-A screen on the unconverted axes -- SCREEN-ON-DISCOVERY makes this the "
          "same run as the discovery, not a later one",
          produced_schema="data_sources", consumed_schema="feature_sources"),
    Stage("feature_to_hypothesis", "data/feature_library.json", "data/hypothesis_queue.jsonl",
          "a feature computed and used in no hypothesis is compute already spent that bought no "
          "test; the combination engine can enumerate over it for free",
          "enumerate the unused features into the candidate space -- generation is not a trial "
          "(L1.52), so this costs no multiplicity budget",
          produced_schema="features", consumed_schema="hypothesis_references"),
    Stage("hypothesis_to_test", "data/hypothesis_queue.jsonl", "data/full_sweep.json",
          "a hypothesis written and never executed is the queue-backlog state L1.52 names "
          "explicitly: with ideas queued and none tested, the next priority is THROUGHPUT",
          "execute the untested backlog; if experiment capacity binds, that is the engineering "
          "target -- never a reason to generate fewer (L1.54)",
          produced_schema="hypotheses", consumed_schema="full_sweep_survivors"),
    Stage("recommendation_to_change", "docs/research/recommendation_ledger.json",
          "docs/research/recommendation_ledger.json",
          "an accepted recommendation that never became a change is advice the desk paid for and "
          "declined to collect; §41 already requires every row to reach implemented or rejected",
          "close each open row to implemented (with commit) or rejected (with a substantive "
          "reason) -- 'still open' past 14 days is a defect to name, not a backlog",
          produced_schema="recommendations_all", consumed_schema="recommendations_terminal"),
    Stage("survivor_to_portfolio", "data/full_sweep.json", "data/portfolio_admission.json",
          "a validated survivor never tested for INCREMENTAL portfolio value may be the "
          "fiftieth expression of an alpha already deployed; standalone Sharpe cannot tell",
          "run marginal-contribution and independence clustering on each survivor before it is "
          "counted as a discovery",
          produced_schema="full_sweep_survivors", consumed_schema="portfolio_rows"),
    Stage("failure_to_mining", "docs/graveyard.md", "data/graveyard_resurrection_queue.json",
          "a failure recorded and never mined discards the most specific information the desk "
          "owns about where an effect is NOT -- which is also information about where it is",
          "extract failure mode, regime, horizon and cost for each killed hypothesis, then "
          "generate the mutations those fields license",
          produced_schema="graveyard", consumed_schema="resurrection_entries"),
    Stage("near_survivor_to_experiment", "data/research_review.json",
          "data/hypothesis_queue.jsonl",
          "a banked near-survivor never revisited is the cheapest experiment the desk has, "
          "already located and already costed",
          "run the next_experiments the bank licenses, at the ancestry-deflated hurdle -- a "
          "descendant inherits the whole search that produced it",
          produced_schema="near_survivors", consumed_schema="hypothesis_references"),
)


@dataclass(frozen=True)
class StageCount:
    """Both sides of one join, including exact producer identities when measurable.

    `consumed` is deliberately the number of PRODUCED identities found downstream, not the raw
    size of the downstream population. Population subtraction can say that every producer was
    consumed merely because an unrelated downstream artifact happens to contain enough rows.
    """

    stage: Stage
    produced: int | None
    consumed: int | None
    produced_ids: frozenset[str] | None = None
    consumed_ids: frozenset[str] | None = None

    @property
    def measured(self) -> bool:
        return self.produced is not None and self.consumed is not None

    @property
    def stranded_ids(self) -> tuple[str, ...] | None:
        if self.produced_ids is None or self.consumed_ids is None:
            return None
        return tuple(sorted(self.produced_ids - self.consumed_ids))

    @property
    def stranded(self) -> int | None:
        identities = self.stranded_ids
        if identities is not None:
            return len(identities)
        if self.produced is None or self.consumed is None:
            return None
        return max(0, self.produced - self.consumed)

    @property
    def conversion(self) -> float | None:
        """Matched producer identities / produced identities, capped at 1.0."""
        if self.produced is None or self.consumed is None:
            return None
        if self.produced <= 0:
            # Nothing produced is not a conversion failure. It is an upstream problem, and the
            # stage above this one is where it will show up as a real gap.
            return 1.0
        return min(1.0, self.consumed / self.produced)


IdentityRows = dict[str, frozenset[str]]
_NON_ID = re.compile(r"[^\w]+", re.UNICODE)
_TERMINAL_RECOMMENDATION_STATES = frozenset({
    "implemented", "rejected", "retired", "done", "screened",
})


def _normalise(value: object) -> str:
    """Conservative exact-match form; prose is never split into convenient keyword hits."""
    return _NON_ID.sub("_", str(value).strip().casefold()).strip("_")


def _identity_values(value: object) -> set[str]:
    """Flatten explicit identity/reference fields without mining substrings from prose."""
    if isinstance(value, Mapping):
        out: set[str] = set()
        for nested in value.values():
            out.update(_identity_values(nested))
        return out
    if isinstance(value, (list, tuple, set, frozenset)):
        out = set()
        for nested in value:
            out.update(_identity_values(nested))
        return out
    if value is None or isinstance(value, bool):
        return set()
    norm = _normalise(value)
    return {norm} if norm else set()


def _field_values(row: Mapping[str, Any], fields: Iterable[str]) -> set[str]:
    out: set[str] = set()
    for field in fields:
        if field in row:
            out.update(_identity_values(row[field]))
    return out


def _first(row: Mapping[str, Any], fields: Iterable[str], fallback: str = "") -> str:
    for field in fields:
        value = row.get(field)
        if value is not None and str(value).strip():
            return str(value).strip()
    return fallback


def _add(records: dict[str, set[str]], primary: object, aliases: Iterable[str] = ()) -> None:
    display = str(primary).strip()
    norm = _normalise(display)
    if not display or not norm:
        return
    records.setdefault(display, set()).update({norm, *(a for a in aliases if a)})


def _freeze(records: dict[str, set[str]]) -> IdentityRows:
    return {name: frozenset(aliases) for name, aliases in records.items()}


def _read_artifact(path: Path) -> object | None:
    """Load one complete artifact. Corrupt/partial input is UNMEASURED, never an empty set."""
    if not path.exists():
        return None
    try:
        text = path.read_text("utf-8")
    except (OSError, UnicodeError):
        return None
    if path.suffix == ".md":
        return text
    if path.suffix == ".jsonl":
        rows: list[object] = []
        try:
            for line in text.splitlines():
                if line.strip():
                    rows.append(json.loads(line))
        except (TypeError, ValueError):
            return None
        return rows
    try:
        loaded: object = json.loads(text)
        return loaded
    except (TypeError, ValueError):
        return None


def _mapping_rows(doc: object, key: str) -> list[Mapping[str, Any]] | None:
    if not isinstance(doc, Mapping):
        return None
    value = doc.get(key)
    if not isinstance(value, list) or not all(isinstance(row, Mapping) for row in value):
        return None
    return list(value)


def _data_sources(doc: object) -> IdentityRows | None:
    """The live catalog is intentionally mixed: category lists plus ID-keyed source rows."""
    if not isinstance(doc, Mapping) or not isinstance(doc.get("sources"), Mapping):
        return None
    records: dict[str, set[str]] = {}
    for category, value in doc["sources"].items():
        if isinstance(value, list):
            if not all(isinstance(row, Mapping) for row in value):
                return None
            rows = [(f"{category}:{index}", row) for index, row in enumerate(value)]
        elif isinstance(value, Mapping):
            rows = [(str(category), value)]
        else:
            return None
        for fallback, row in rows:
            primary = _first(row, ("id", "name", "source", "url"), fallback)
            aliases = _field_values(row, ("id", "name", "source", "url"))
            aliases.update(_identity_values(category))
            _add(records, primary, aliases)
    return _freeze(records)


def _features(doc: object, *, references_only: bool = False) -> IdentityRows | None:
    rows = _mapping_rows(doc, "features")
    if rows is None:
        return None
    records: dict[str, set[str]] = {}
    for index, row in enumerate(rows):
        primary = _first(row, ("id", "name"), f"feature:{index}")
        fields = ("id", "name", "source", "source_id", "dataset", "data_source") \
            if references_only else ("id", "name")
        _add(records, primary, _field_values(row, fields))
    return _freeze(records)


def _hypotheses(doc: object, *, references_only: bool = False) -> IdentityRows | None:
    if not isinstance(doc, list) or not all(isinstance(row, Mapping) for row in doc):
        return None
    records: dict[str, set[str]] = {}
    for index, row in enumerate(doc):
        primary = _first(row, ("id", "name", "title"), f"hypothesis:{index}")
        fields = (
            "id", "name", "title", "feature", "feature_id", "features", "feature_ids",
            "source_feature", "data", "parent", "parent_id", "ancestor",
            "near_survivor", "killed_by", "mechanism",
        ) if references_only else ("id", "name", "title")
        _add(records, primary, _field_values(row, fields))
    return _freeze(records)


def _full_sweep_survivors(doc: object) -> IdentityRows | None:
    if isinstance(doc, Mapping) and doc.get("survivors_truncated"):
        # The JSON omits identities beyond max_detail; claiming complete conversion would be false.
        return None
    rows = _mapping_rows(doc, "survivors")
    if rows is None:
        return None
    records: dict[str, set[str]] = {}
    for index, row in enumerate(rows):
        key = row.get("key")
        joined = "|".join(str(part) for part in key) if isinstance(key, list) else ""
        primary = joined or _first(row, ("id", "name", "trial"), f"survivor:{index}")
        aliases = _field_values(row, ("id", "name", "trial"))
        aliases.update(_identity_values(joined))
        _add(records, primary, aliases)
    return _freeze(records)


def _recommendations(doc: object, *, terminal_only: bool = False) -> IdentityRows | None:
    rows = _mapping_rows(doc, "recommendations")
    if rows is None:
        return None
    records: dict[str, set[str]] = {}
    for index, row in enumerate(rows):
        status = str(row.get("status", "")).strip().casefold()
        if terminal_only and status not in _TERMINAL_RECOMMENDATION_STATES:
            continue
        primary = _first(row, ("id", "recommendation_id", "summary"),
                         f"recommendation:{index}")
        _add(records, primary, _field_values(row, ("id", "recommendation_id", "summary")))
    return _freeze(records)


def _portfolio_rows(doc: object) -> IdentityRows | None:
    rows = _mapping_rows(doc, "rows")
    if rows is None:
        return None
    records: dict[str, set[str]] = {}
    for index, row in enumerate(rows):
        primary = _first(row, ("survivor", "id", "name"), f"portfolio:{index}")
        _add(records, primary, _field_values(row, ("survivor", "id", "name")))
    return _freeze(records)


def _graveyard(doc: object) -> IdentityRows | None:
    if not isinstance(doc, str):
        return None
    records: dict[str, set[str]] = {}
    for line in doc.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells:
            continue
        primary = cells[0].strip("` ")
        if (not primary or _normalise(primary) in {"name", "signal", "strategy"}
                or not _normalise(primary).strip("_")):
            continue
        # Markdown separator rows contain only punctuation in their first cell.
        if not any(ch.isalnum() for ch in primary):
            continue
        _add(records, primary)
    return _freeze(records)


def _named_rows(doc: object, key: str, *, prefix: str) -> IdentityRows | None:
    rows = _mapping_rows(doc, key)
    if rows is None:
        return None
    records: dict[str, set[str]] = {}
    for index, row in enumerate(rows):
        primary = _first(row, ("name", "id", "key", "trial"), f"{prefix}:{index}")
        _add(records, primary, _field_values(row, ("name", "id", "key", "trial", "axis")))
    return _freeze(records)


def _near_survivors(doc: object) -> IdentityRows | None:
    rows = _mapping_rows(doc, "near_survivor_bank")
    if rows is None:
        return None
    records: dict[str, set[str]] = {}
    for index, row in enumerate(rows):
        primary = _first(row, ("id", "killed_by", "mechanism", "name"),
                         f"near-survivor:{index}")
        _add(records, primary, _field_values(
            row, ("id", "killed_by", "mechanism", "name")))
    return _freeze(records)


def _extract(path: Path, schema: str) -> IdentityRows | None:
    doc = _read_artifact(path)
    if doc is None:
        return None
    if schema == "data_sources":
        return _data_sources(doc)
    if schema == "feature_sources":
        return _features(doc, references_only=True)
    if schema == "features":
        return _features(doc)
    if schema == "hypothesis_references":
        return _hypotheses(doc, references_only=True)
    if schema == "hypotheses":
        return _hypotheses(doc)
    if schema == "full_sweep_survivors":
        return _full_sweep_survivors(doc)
    if schema == "recommendations_all":
        return _recommendations(doc)
    if schema == "recommendations_terminal":
        return _recommendations(doc, terminal_only=True)
    if schema == "portfolio_rows":
        return _portfolio_rows(doc)
    if schema == "graveyard":
        return _graveyard(doc)
    if schema == "resurrection_entries":
        return _named_rows(doc, "entries", prefix="resurrection")
    if schema == "near_survivors":
        return _near_survivors(doc)

    return None


def _count(path: Path) -> int | None:
    """Legacy population counter retained for injected-counter callers and focused tests."""
    doc = _read_artifact(path)
    if doc is None:
        return None
    if isinstance(doc, list):
        return len(doc)
    if isinstance(doc, Mapping):
        for key in ("entries", "rows", "items", "records", "survivors", "candidates",
                    "hypotheses", "features", "gaps", "runs", "recommendations"):
            value = doc.get(key)
            if isinstance(value, list):
                return len(value)
        if doc and all(isinstance(value, Mapping) for value in doc.values()):
            return len(doc)
    if isinstance(doc, str):
        rows = _graveyard(doc)
        return None if rows is None else len(rows)
    return None


def scan(*, root: Path | None = None, counter: Callable[[Path], int | None] | None = None,
         ) -> list[StageCount]:
    """Measure exact producer identities at every join.

    `counter` remains as a compatibility/test seam. Production scans use schema-aware identity
    extraction; a downstream row only counts when it names an actual upstream identity.
    """
    r = root or _ROOT
    if counter is not None:
        return [StageCount(stage, counter(r / stage.produced_artifact),
                           counter(r / stage.consumed_artifact)) for stage in STAGES]

    out: list[StageCount] = []
    for stage in STAGES:
        produced_rows = _extract(r / stage.produced_artifact, stage.produced_schema)
        downstream_rows = _extract(r / stage.consumed_artifact, stage.consumed_schema)
        if produced_rows is None or downstream_rows is None:
            out.append(StageCount(
                stage,
                None if produced_rows is None else len(produced_rows),
                None if downstream_rows is None else 0,
                None if produced_rows is None else frozenset(produced_rows),
                None,
            ))
            continue
        downstream_aliases = set().union(*downstream_rows.values()) if downstream_rows else set()
        matched = frozenset(
            identity for identity, aliases in produced_rows.items()
            if aliases & downstream_aliases
        )
        out.append(StageCount(stage, len(produced_rows), len(matched),
                              frozenset(produced_rows), matched))
    return out


def to_gaps(counts: list[StageCount]) -> list[Gap]:
    """Published rows. AN UNWATCHED JOIN IS THE FINDING, not an omission from the report.

    A stage whose artifact is missing publishes `current=None`, which the queue ranks ABOVE a
    partially-converted stage. That ordering is deliberate and it is the whole reason this scan is
    worth running: the desk knows roughly how bad its measured conversion is, and does not know
    which joins nobody is watching at all.
    """
    out: list[Gap] = []
    for sc in counts:
        s = sc.stage
        if sc.measured:
            stranded_ids = sc.stranded_ids
            sample = ""
            if stranded_ids:
                sample = f"; stranded identity sample: {', '.join(stranded_ids[:5])}"
            evidence = "identity-matched" if stranded_ids is not None else "population-only"
            detail = (f"{sc.consumed} of {sc.produced} converted ({evidence}); "
                      f"{sc.stranded} stranded at {s.name}{sample}")
            action = s.action
        else:
            missing = [a for a, n in ((s.produced_artifact, sc.produced),
                                      (s.consumed_artifact, sc.consumed)) if n is None]
            detail = (f"UNMEASURED -- {', '.join(missing)} absent or unrecognised, so this join "
                      "is unwatched. Nobody-looked and nothing-stranded are opposite facts")
            action = (f"emit the missing artifact so the join can be counted, THEN {s.action}. "
                      "An unwatched join outranks a measured one because an unknown quantity is "
                      "being ignored rather than worked (L1.28a)")
        out.append(Gap(
            aspect=f"conversion::{s.name}", source=s.source,
            current=sc.conversion, ceiling=1.0, detail=detail, action=action,
            artifact=s.consumed_artifact, evidence=s.why,
            dependency=s.produced_artifact, tags=("conversion-chain",)))
    return out


def summarise(counts: list[StageCount]) -> dict[str, Any]:
    """Report shape: the WORST-CONVERTING measured join first, and the unwatched ones named.

    The bottleneck stage is the work (L1.53). A report ordered by stage name would bury it.
    """
    measured = [c for c in counts if c.measured]
    unwatched = [c.stage.name for c in counts if not c.measured]
    ranked = sorted(measured, key=lambda c: (c.conversion or 0.0))
    return {
        "joins": len(counts), "measured": len(measured), "unwatched": unwatched,
        "bottleneck": ranked[0].stage.name if ranked else None,
        "chain": [{
            "stage": c.stage.name,
            "produced": c.produced,
            "consumed": c.consumed,
            "stranded": c.stranded,
            "conversion": None if c.conversion is None else round(c.conversion, 4),
            "identity_matched": c.stranded_ids is not None,
            "consumed_id_sample": (
                sorted(c.consumed_ids)[:5] if c.consumed_ids is not None else None),
            "stranded_id_sample": (
                list(c.stranded_ids[:5]) if c.stranded_ids is not None else None),
        } for c in counts],
        "note": ("UNMEASURED joins outrank measured ones. The desk knows roughly how bad its "
                 "measured conversion is; it does not know which joins nobody watches at all."),
    }
