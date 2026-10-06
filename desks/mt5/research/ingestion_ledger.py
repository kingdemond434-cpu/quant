"""THE INGESTION-EXPLOITATION CONTRACT -- nothing the desk ingested may sit unexploited.

THE PRINCIPAL'S ORDER, 2026-09-17, permanent: all data mined and ingested must ALWAYS be
exploited for candidate-cell generation, 24/7, by a process; the conversion of research rows and
information into testable gauntlet cells must always be 100% and maximised.

WHAT WAS MISSING, and it is not bookkeeping. `discovery_compiler` already guarantees that no
DISCOVERY dies of neglect, and `conversion_debt()` counts the cells each discovery owes. But a
discovery only exists once something has already decided a row was worth recording. The desk
ingests far more than it records: 11,270 seat files under two `data/intelligence` roots, 2,767
tape instrument-days, 802 universe bar files, 197 shadow ledgers, the axis series, the claims
table, the collectors' normalised documents. NOTHING counted those, so the conversion rate from
INGESTION to cell was not merely low -- it was unmeasured, and an unmeasured conversion rate
counts as zero (sealed core, L1.28a).

THE CONTRACT. Every ingestion the desk performs registers WHAT it ingested, as a UNIT, and every
unit must reach a DISPOSITION:

    EXPLOITED        a discovery or candidate NAMES it -- payload/required_data/source_id match
                     by declared key, or (for the instrument-keyed kinds) its symbol and chart
    EXPLOITED_MACRO  `macro_intelligence` consumed it as a fusion feature
    BLOCKED          a BLOCKED discovery names it: an explicit refusal, with a reason, is a
                     lawful disposition and counts as exploited ground
    PENDING          ingested inside the grace window (--grace-hours 24) and nothing yet
    STRANDED         past the grace window with no disposition at all

A STRANDED UNIT IS NOT A REPORT LINE. It is handed to the process: a DISCOVERY is recorded
(source_type "ingestion", origin "MOAT", state UNPROCESSED) carrying the unit's kind, id and
path, so `discovery_compiler` picks it up on its next pass and closes it through the same seven
steps as every other finding. That is the process the principal asked for -- a stranded unit
becomes a discovery, never a report.

THE ONE TRAP THIS ORGAN HAD TO AVOID, and it is the denominator trick the laws forbid. Once a
stranded unit has been handed over, a discovery DOES name it -- so a naive index would read it
as EXPLOITED on the very next pass, and `exploitation_share` would reach 1.0 by the act of
measuring. So THIS ORGAN'S OWN HANDOFF DISCOVERIES ARE EXCLUDED from the exploited index until
they have actually converted: a handoff counts only once its state reaches COMPILED / QUEUED /
TESTED, or BLOCKED with a reason, or once a candidate carries its `discovery_id`. Until then the
unit stays STRANDED and keeps showing up as debt, which is the whole point of the number.

THE DOWNSTREAM-STATE RULE (principal, 2026-09-17, permanent):

    "No qualified public/licensed datum is allowed to sit in storage without a defined
     downstream state."

QUALIFIED WIDENED ON 2026-09-23 (LAWS 5e): it is now every access label off the five refused
acts, ACCESS_UNCLEAR included, because the unclear-access quarantine was deleted.

So every qualified datum carries EXACTLY ONE state from this enum, spelled exactly:
WORLD_MODEL_INPUT, CANDIDATE_INPUT, INTERACTION_INPUT, EXECUTION_INPUT, PORTFOLIO_INPUT,
NEGATIVE_KNOWLEDGE, AWAITING_EXPERIMENT, RETIRED_WITH_EVIDENCE. They are not a quality ladder:
NEGATIVE_KNOWLEDGE and RETIRED_WITH_EVIDENCE are as lawful as PORTFOLIO_INPUT, and
AWAITING_EXPERIMENT is the honest residual -- what is forbidden is carrying none of them.
`DOWNSTREAM_ORDER` is the declared tie-break, because "exactly one" needs a rule a reader can
argue with rather than discover. A DATUM INGESTED TWICE OR MORE THAT STILL REACHES NO CONSUMER IS
A DATA STRANDING DEFECT: `stranding_counts` carries the per-datum ingestion count across passes,
`stranded_data` names every one of them, and `scripts/check_ingestion_exploitation.py` fails on
a count above its ratchet (that ratchet may FALL, never rise).

THREE INDEPENDENT LABELS ON EVERY ROW, NEVER COLLAPSED INTO ONE ANOTHER:

    access_label      PUBLIC | PUBLIC_WITH_TERMS | LICENSED | OPEN_DATA | PUBLIC_ARCHIVE |
                      PUBLIC_SOCIAL | USER_SUBMITTED | ACCESS_UNCLEAR | PRIVATE |
                      CONFIDENTIAL_MNPI | STOLEN_UNAUTHORIZED
    credibility       AUTHORITATIVE | RELIABLE | UNRELIABLE | FRINGE | CONTRADICTED | UNKNOWN
    predictive_state  UNTESTED | PREDICTIVE | NOT_PREDICTIVE | NARRATIVE_FEATURE

Legality of access, credibility and predictive value are three different questions about one row,
and answering them with one number is how a desk ends up deleting its own evidence. A FRINGE or
CONTRADICTED public claim is KEPT as an evidence object -- it may be a crowding or narrative
feature -- and is never deleted for being unreliable. ACCESS_UNCLEAR IS QUALIFIED AND EXPLOITED
(LAWS 5e, 2026-09-23): it owes a downstream state like any other row and is handed to the
compiler when it is stranded. The quarantine that used to hold it -- metadata kept, content not
consumed -- was a discovery brake the desk imposed on itself and it is deleted; the unresolved
access question is a PROVENANCE NOTE on the row. PRIVATE, CONFIDENTIAL_MNPI and
STOLEN_UNAUTHORIZED carry the five refused ACTS, never become an alpha input on any pass, and are
recorded in `refusals` with the reason. The vocabulary belongs to
`libs/research/access_classifier`; that module is imported when it lands and its verdict wins,
and until then the same spellings are carried here so the join is a rename, never a re-derivation.

THE BUDGET IS A BUDGET AND IT SAYS SO (L1.61). A pass reads a bounded window of each kind's
listing and ROTATES that window forward, resuming from the cursor the previous artifact
published -- so every unit is reached across passes, and what this pass did not reach is COUNTED
in `not_reached` rather than silently excluded from the denominator.

    python desks/mt5/research/ingestion_ledger.py
    python desks/mt5/research/ingestion_ledger.py --dry-run
    python desks/mt5/research/ingestion_ledger.py --grace-hours 24 --budget-s 240
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(BASE), str(BASE / "research"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402

#: Module globals, not frozen constants: a test points the whole contract at `tmp_path`.
MOAT = REPO / "data" / "moat"
NORMALIZED = MOAT / "normalized_intel"
INTEL_DIRS: tuple[Path, ...] = (BASE / "data" / "intelligence", REPO / "data" / "intelligence")
AXES = BASE / "data" / "axes"
TAPE_TICKS = BASE / "data" / "tape" / "ticks"
UNIVERSE = BASE / "data" / "universe"
MOAT_SERIES = BASE / "data" / "moat"
SHADOW_DIR = BASE / "reports" / "shadow"
LIVE_LEDGER = BASE / "data" / "live_ledger.jsonl"
MACRO_REPORT = BASE / "reports" / "MACRO_INTELLIGENCE.json"
LEDGER = BASE / "data" / "ingestion_ledger.jsonl"
OUT = BASE / "reports" / "INGESTION_EXPLOITATION.json"

UNMEASURED = "UNMEASURED"
SOURCE_TYPE = "ingestion"
#: Claims the desk reads as news-like. They are units of their own kind so the news lane's
#: exploitation can be measured separately from the rest of the claims table.
NEWS_KINDS: frozenset[str] = frozenset({"news", "filing", "data_release", "central_bank"})
DISPOSITIONS: tuple[str, ...] = ("EXPLOITED", "EXPLOITED_MACRO", "BLOCKED", "PENDING", "STRANDED")
#: Column headings for the printed table, because EXPLOITED and EXPLOITED_MACRO share a prefix
#: and a naive truncation printed the same word twice over two different numbers.
SHORT: dict[str, str] = {"EXPLOITED": "expl", "EXPLOITED_MACRO": "macro", "BLOCKED": "blkd",
                         "PENDING": "pend", "STRANDED": "strd"}
#: The kinds whose DECLARED KEY is an instrument: a candidate that names EURUSD on H1 is using
#: the EURUSD H1 bars and the EURUSD tape, and pretending otherwise would manufacture debt.
SYMBOL_KEYED: frozenset[str] = frozenset({"tape_day", "universe_bars", "moat_series",
                                          "sleeve_ledger"})
#: A handoff discovery counts as exploitation only once it has actually converted.
CONVERTED_STATES: frozenset[str] = frozenset({"COMPILED", "QUEUED", "TESTED"})
#: WHAT MAKES EACH KIND POINT-IN-TIME, per dataset. A file mtime says when the desk wrote the
#: bytes and never when the world could read them, so it is NOT a PIT stamp and is not counted
#: as one -- question 2 of the utilization audit is answered off this table and the per-unit
#: flag, never off "the file exists".
PIT_BASIS: dict[str, str] = {
    "normalized_doc": "the source's own knowable_at, never the crawl time",
    "claim": "the claim's knowable_at",
    "news_claim": "the claim's knowable_at",
    "intel_row": "the seat's declared at/generated_at",
    "axis_series": "vintage note, knowable lag, or a per-row knowable_at",
    "country_plane": "vintage note or a per-row knowable_at",
    "tape_day": "the instrument-day is itself the knowable date",
    "universe_bars": "each bar carries its own close time",
    "sleeve_ledger": "each fill carries its own exit time",
    "moat_series": "UNMEASURED: a derived series carries no vintage of its own",
}

GRACE_HOURS = 24.0
BUDGET_S = 240.0
#: A HARD CEILING, deliberately above the sum of the per-kind caps below (2,950). The per-kind
#: caps are the operative control because they rotate independently; a global cap UNDER their sum
#: would slice in collection order and starve whichever kind sorts last -- the same silent
#: exclusion the `not_reached` counter exists to make visible.
MAX_UNITS = 3000
#: Every stranded unit is routed each pass (`route_stranded`); this bound is only the legacy
#: `hand_to_compiler` door's, kept at the unit ceiling so it can never be the thing that strands.
MAX_STRANDED_HANDOFFS = 3000
MAX_TOP_STRANDED = 25
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_ROWS_PER_FILE = 200
MAX_INTEL_FILES = 120
MAX_REGISTRY_ROWS = 20000
#: Per-kind slice of one pass. Rotating, so the cap costs coverage of THIS pass, never of the
#: contract: the remainder is counted in `not_reached` and reached by the next pass.
KIND_CAP: dict[str, int] = {
    "normalized_doc": 300, "claim": 400, "news_claim": 200, "intel_row": 600,
    "axis_series": 200, "country_plane": 100, "tape_day": 400, "universe_bars": 300,
    "sleeve_ledger": 250, "moat_series": 200,
}
UNIT_KINDS: tuple[str, ...] = tuple(KIND_CAP)

#: WHICH MODALITY THE FEATURE COMPILER TYPES EACH UNIT KIND AS (LAWS 5m). The ledger owns the
#: unit kinds, so the map lives here and the compiler imports it; `axis:cot` is positioning by
#: dataset name, which the compiler decides.
UNIT_MODALITY: dict[str, str] = {
    "tape_day": "prices", "universe_bars": "prices", "axis_series": "macro_releases",
    "country_plane": "physical_observations", "normalized_doc": "text_claims",
    "claim": "text_claims", "news_claim": "text_claims", "intel_row": "text_claims",
    "sleeve_ledger": "execution_records", "moat_series": "representations",
}
#: THE CONTRACT DEFECT (LAWS 5m; RESEARCH 11). Every dataset owes a DatasetContract; a unit
#: whose dataset has none is recorded CONTRACT_MISSING as a DEFECT ROW and is still ingested,
#: judged, exploited and handed on exactly as before. The defect names the contract nobody wrote;
#: it is never a brake on mining.
CONTRACTS_JSON = BASE / "data" / "feature_genome" / "contracts.json"
CONTRACT_STATES: tuple[str, ...] = ("CONTRACTED", "CONTRACT_INCOMPLETE", "CONTRACT_MISSING")
CONTRACT_RULE = ("a dataset without a contract is recorded CONTRACT_MISSING as a defect row; it "
                 "never brakes mining -- the datum is still ingested, judged and exploited")

#: THE DOWNSTREAM-STATE ENUM (principal, 2026-09-17). Exactly one per qualified datum, spelled
#: exactly. The states are not a quality ladder: NEGATIVE_KNOWLEDGE and RETIRED_WITH_EVIDENCE are
#: as lawful as PORTFOLIO_INPUT -- what is forbidden is carrying NONE of them.
DOWNSTREAM_STATES: tuple[str, ...] = (
    "WORLD_MODEL_INPUT", "CANDIDATE_INPUT", "INTERACTION_INPUT", "EXECUTION_INPUT",
    "PORTFOLIO_INPUT", "NEGATIVE_KNOWLEDGE", "AWAITING_EXPERIMENT", "RETIRED_WITH_EVIDENCE")
DOWNSTREAM_RULE = ("No qualified datum is allowed to sit in storage without a defined downstream "
                   "state -- and since LAWS 5e (2026-09-23) QUALIFIED means every access label "
                   "off the five refused acts, ACCESS_UNCLEAR included.")
#: The order a datum's single state is decided in. Declared, because "exactly one" needs a
#: tie-break that a reader can argue with rather than discover.
DOWNSTREAM_ORDER: tuple[str, ...] = (
    "PORTFOLIO_INPUT", "EXECUTION_INPUT", "WORLD_MODEL_INPUT", "INTERACTION_INPUT",
    "CANDIDATE_INPUT", "RETIRED_WITH_EVIDENCE", "NEGATIVE_KNOWLEDGE", "AWAITING_EXPERIMENT")

#: THREE INDEPENDENT DIMENSIONS, NEVER COLLAPSED (principal, 2026-09-17). Legality of access,
#: credibility and predictive value are different questions about the same row: a fringe or false
#: PUBLIC claim is kept as an evidence object -- it may be a crowding or narrative feature -- and
#: is never deleted for being unreliable.
ACCESS_LABELS: tuple[str, ...] = (
    "PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA", "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL",
    "USER_SUBMITTED", "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
CREDIBILITY_LABELS: tuple[str, ...] = ("AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE",
                                       "CONTRADICTED", "UNKNOWN")
PREDICTIVE_STATES: tuple[str, ...] = ("UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE",
                                      "NARRATIVE_FEATURE")
#: QUALIFIED is the population the downstream-state rule binds: EVERY label off the five refused
#: acts (LAWS 5e, 2026-09-23). ACCESS_UNCLEAR joined it when the quarantine was deleted -- a row
#: whose access path is unresolved is still ingested, still owes a downstream state, and is still
#: handed to the compiler when it is stranded.
QUALIFIED_ACCESS: frozenset[str] = frozenset({"PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED",
                                              "OPEN_DATA", "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL",
                                              "USER_SUBMITTED", "ACCESS_UNCLEAR"})
#: EMPTY BY CONSTRUCTION. The access quarantine was deleted on 2026-09-23; the name stays so an
#: old reader finds an explicit empty set rather than an AttributeError, and so a fence can assert
#: it never refills.
QUARANTINED_ACCESS: frozenset[str] = frozenset()
#: Never an alpha input, on any pass, for any reason -- the three labels that carry the five
#: refused ACTS. Recorded as refused WITH the reason.
REFUSED_ACCESS: frozenset[str] = frozenset({"PRIVATE", "CONFIDENTIAL_MNPI",
                                            "STOLEN_UNAUTHORIZED"})
REFUSAL_REASON: dict[str, str] = {
    "PRIVATE": "private information: never an alpha input",
    "CONFIDENTIAL_MNPI": "material non-public information: never an alpha input",
    "STOLEN_UNAUTHORIZED": "obtained without authorisation: never an alpha input",
}
#: The desk's own defaults per kind, used where the registry's `sources` row says nothing. FRED,
#: ECB, BIS and CFTC are open government/IO data; the broker's bars, ticks and the desk's own
#: fill record are held under the account's data licence; a seat's donation is USER_SUBMITTED
#: because an LLM seat wrote it, whatever it was reading.
DEFAULT_ACCESS: dict[str, str] = {
    "axis_series": "OPEN_DATA", "country_plane": "OPEN_DATA", "tape_day": "LICENSED",
    "universe_bars": "LICENSED", "moat_series": "LICENSED", "sleeve_ledger": "LICENSED",
    "normalized_doc": "PUBLIC", "claim": "PUBLIC", "news_claim": "PUBLIC",
    "intel_row": "USER_SUBMITTED",
}
DEFAULT_CREDIBILITY: dict[str, str] = {
    "axis_series": "AUTHORITATIVE", "country_plane": "AUTHORITATIVE",
    "tape_day": "AUTHORITATIVE", "universe_bars": "AUTHORITATIVE",
    "moat_series": "RELIABLE", "sleeve_ledger": "AUTHORITATIVE",
    "normalized_doc": "UNKNOWN", "claim": "UNKNOWN", "news_claim": "UNKNOWN",
    "intel_row": "UNKNOWN",
}
#: Artifacts that, by naming a datum, prove a consumer reached it. WORLD_MODEL_INPUT is answered
#: by `macro_intelligence`'s own `consumed_units` instead, which is an exact join rather than a
#: token probe.
CONSUMER_ARTIFACTS: dict[str, Path] = {
    "PORTFOLIO_INPUT": BASE / "reports" / "pf_allocation.json",
    "EXECUTION_INPUT": BASE / "data" / "cost_surface.json",
    "INTERACTION_INPUT": BASE / "reports" / "CROSS_ASSET_GRAPH.json",
}
MAX_ARTIFACT_NODES = 400_000
#: Passes a datum may be re-ingested with no consumer before it is a DATA STRANDING defect.
STRANDING_INGESTIONS = 2
MAX_STRANDING_COUNTS = 8000
MAX_STRANDED_DATA = 200
#: Bytes of the ledger's tail read to recover the population's latest disposition per unit.
MAX_POPULATION_BYTES = 8 * 1024 * 1024

#: The access classifier is another builder's module and carries this exact vocabulary. Imported
#: when it lands; until then the labels are carried as strings in the same spelling, so the join
#: is a rename and never a re-derivation.
try:
    from libs.research import access_classifier as AC
except Exception:                                    # pragma: no cover - absent on this box today
    AC = None                                        # type: ignore[assignment]

RULE = ("everything ingested is exploited or explicitly blocked; a stranded unit becomes a "
        "discovery, never a report; " + DOWNSTREAM_RULE)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(when: datetime) -> str:
    return when.isoformat(timespec="seconds")


def _stamp(value: Any) -> datetime | None:
    try:
        out = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return out if out.tzinfo else out.replace(tzinfo=UTC)


def _mtime(path: Path) -> str:
    try:
        return _iso(datetime.fromtimestamp(path.stat().st_mtime, tz=UTC))
    except OSError:
        return ""


def _read_json(path: Path) -> Any:
    try:
        if not path.exists() or path.stat().st_size > MAX_FILE_BYTES:
            return None
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _write_atomic(path: Path, payload: Any) -> None:
    """Atomic where the filesystem allows it. `os.replace` onto a read-only destination is legal
    on POSIX and raises WinError 5 here -- the way a VPS-tested fix once broke the trading box."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, indent=1, default=str)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    try:
        os.replace(tmp, path)
    except OSError:
        path.write_text(body, encoding="utf-8")


def population(path: Path, rows: list[dict[str, Any]], limit: int = MAX_POPULATION_BYTES
               ) -> tuple[dict[str, int], int]:
    """Each unit's MOST RECENT disposition over the ledger's recent tail plus this pass.

    WHY THE FENCED NUMBER IS NOT THIS PASS'S SHARE. The window rotates, so one pass is heavy on
    seat rows (55% exploited) and the next is heavy on tape (84%) -- the same tree, the same day,
    thirty points apart. A ratchet on that number is a ratchet on which slice the cursor happened
    to land, and it would be red most hours for no reason anybody could act on; a fence that is
    permanently red is a fence that gets switched off. So the share is measured over the UNION of
    what the ledger has seen recently, one row per unit, which is a property of the desk rather
    than of the cursor. The per-pass number is still published, as `pass_share`.
    """
    latest: dict[str, str] = {}
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > limit:
                fh.seek(size - limit)
                fh.readline()                        # drop the partial line the seek landed in
            for raw in fh:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get("unit_id") and row.get("disposition"):
                    latest[f"{row.get('kind')}:{row['unit_id']}"] = str(row["disposition"])
    except OSError:
        pass
    for row in rows:
        latest[f"{row.get('kind')}:{row.get('unit_id')}"] = str(row.get("disposition"))
    tally: dict[str, int] = dict.fromkeys(DISPOSITIONS, 0)
    for verdict in latest.values():
        if verdict in tally:
            tally[verdict] += 1
    return tally, len(latest)


def _append_jsonl(path: Path, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, default=str) + "\n")
    return len(rows)


def _json_field(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def _tokens(value: Any, out: set[str]) -> None:
    """Every string a declared field can carry, flattened -- lists, dicts and bare strings."""
    if isinstance(value, str):
        text = value.strip().lower()
        if text and len(text) <= 400:
            out.add(text)
    elif isinstance(value, list):
        for item in value[:64]:
            _tokens(item, out)
    elif isinstance(value, dict):
        # `field` is how a dataset-conditioned / dataset_stance cell names the SERIES it reads
        # (dataset_exploitation's cells carry {"dataset": id, "field": series}), so an exact
        # series join reaches the axis unit that series came from.
        for key in ("unit_id", "path", "source_id", "doc_id", "claim_id", "series", "symbol",
                    "file", "dataset", "field"):
            if key in value:
                _tokens(value[key], out)


# --------------------------------------------------------------------------- the unit
@dataclass(frozen=True)
class Unit:
    """One thing the desk ingested, with the keys any consumer would name it by."""

    kind: str
    unit_id: str
    path: str = ""
    keys: tuple[str, ...] = ()
    symbols: tuple[str, ...] = ()
    chart: str = ""
    at: str = ""
    #: True only where the stamp is the SOURCE's own knowable/vintage stamp. A file mtime says
    #: when the desk wrote the bytes, never when the world could read them, so it is not PIT.
    pit: bool = False
    #: The named dataset a unit belongs to -- `axis:fred`, `axis:cot`. Empty means "the kind".
    dataset_name: str = ""
    #: THREE INDEPENDENT LABELS, never collapsed into one another.
    access_label: str = ""
    credibility: str = ""
    predictive_state: str = ""
    #: What the unit SAYS, when it says anything (a claim's text, a seat row's mechanism/why, a
    #: document's title): carried onto its routed discovery so the compiler interprets the
    #: unit's own mechanism instead of the placeholder "ingested and unexploited".
    text: str = ""
    #: A mechanism id the source itself declared (the claims table's `mechanism_id`, a seat
    #: row's `mechanism`). Empty when nothing declared one.
    mechanism: str = ""

    @property
    def qualified(self) -> bool:
        return self.access_label in QUALIFIED_ACCESS

    @property
    def quarantined(self) -> bool:
        """ALWAYS FALSE (LAWS 5e, 2026-09-23). Kept so readers of the published artifact and of
        this class find an explicit False rather than a missing attribute."""
        return self.access_label in QUARANTINED_ACCESS

    @property
    def refused(self) -> bool:
        return self.access_label in REFUSED_ACCESS

    @property
    def dataset(self) -> str:
        return self.dataset_name or self.kind

    def all_keys(self) -> set[str]:
        out = {self.unit_id.lower(), f"{self.kind}:{self.unit_id}".lower()}
        out.update(k.strip().lower() for k in self.keys if k)
        if self.path:
            out.add(self.path.lower())
            out.add(Path(self.path).name.lower())
        return {k for k in out if k}

    def consumer_keys(self) -> set[str]:
        """The keys a DOWNSTREAM ARTIFACT may be searched for -- deliberately narrower than
        `all_keys`.

        `all_keys` carries the file stem and the parent directory, because that is how the desk's
        own miners name a source (`intel:<seat>:<file>`) and the registry join needs it. A
        downstream artifact is different: it is a big JSON full of ordinary words, and probing it
        with a directory name called `intelligence` matched 63 unrelated seat rows to the cost
        surface on the first pass that tried it. Only the unit's own id and, for the
        instrument-keyed kinds, its instrument are specific enough to prove consumption.
        """
        out = {self.unit_id.lower(), f"{self.kind}:{self.unit_id}".lower()}
        if self.kind in SYMBOL_KEYED:
            out |= {s.lower() for s in self.symbols if s}
            if self.path:
                out.add(Path(self.path).name.lower())
        return {k for k in out if k}

    def age_h(self, now: datetime) -> float | None:
        when = _stamp(self.at)
        return None if when is None else (now - when).total_seconds() / 3600.0


def _window(items: list[Any], kind: str, cursor: dict[str, Any], cap: int
            ) -> tuple[list[Any], int, int]:
    """A ROTATING window over a listing: (this pass's slice, next cursor, units not reached).

    The cursor is published in the artifact and read back on the next pass, so a bounded pass
    still sweeps the whole population over time instead of re-reading the same head forever.
    """
    n = len(items)
    if n == 0:
        return [], 0, 0
    start = int(cursor.get(kind) or 0) % n
    take = min(max(cap, 0), n)
    slice_ = [items[(start + i) % n] for i in range(take)]
    return slice_, (start + take) % n, n - take


# --------------------------------------------------------------------------- the collectors
#: Above this an axis file is read by HEAD only -- the scalars and the `symbols` array, which the
#: desk's own writer emits before the panel. The panel itself belongs to `macro_intelligence`,
#: which streams it.
AXIS_FULL_BYTES = 16 * 1024 * 1024
AXIS_HEAD_BYTES = 1024 * 1024


def _axis_header(path: Path) -> dict[str, Any] | None:
    """An axis file's header: every scalar, `series` where it is cheap, `symbols` always."""
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if size <= AXIS_FULL_BYTES:
        doc = _read_json(path)
        return doc if isinstance(doc, dict) else None
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as fh:
            head = fh.read(AXIS_HEAD_BYTES)
    except OSError:
        return None
    out: dict[str, Any] = {"_head_only": True}
    for key in ("axis", "id", "source", "at", "vintage_note", "knowable_lag_days", "shape"):
        marker = f'"{key}":'
        i = head.find(marker)
        if i < 0:
            continue
        line = head[i + len(marker):].split("\n", 1)[0].strip().rstrip(",")
        try:
            out[key] = json.loads(line)
        except ValueError:
            continue
    i = head.find('"symbols":')
    if i >= 0:
        start = head.find("[", i)
        end = head.find("]", start)
        if start >= 0 and end > start:
            with contextlib.suppress(ValueError):
                out["symbols"] = json.loads(head[start:end + 1])
    return out


def _sym_chart(stem: str) -> tuple[str, str]:
    sym, _, chart = stem.rpartition("_")
    return (sym.upper(), chart.upper()) if sym else (stem.upper(), "")


def units_normalized_docs(cursor: dict[str, Any], gaps: list[dict[str, str]]
                          ) -> tuple[list[Unit], int, int]:
    """The collectors' normalised documents: `data/moat/normalized_intel/<source>/<sha>.json`."""
    if not NORMALIZED.exists():
        gaps.append({"what": str(NORMALIZED), "why": "the moat's normalised-document store is "
                                                     "absent on this host; document ingestion is "
                                                     "UNMEASURED, not zero"})
        return [], 0, 0
    files = sorted(NORMALIZED.glob("*/*.json"))
    picked, nxt, missed = _window(files, "normalized_doc", cursor, KIND_CAP["normalized_doc"])
    out: list[Unit] = []
    for path in picked:
        doc = _read_json(path)
        doc = doc if isinstance(doc, dict) else {}
        keys = {str(doc.get("doc_id") or ""), str(doc.get("capture_sha") or ""),
                str(doc.get("source_id") or ""), path.stem, path.parent.name}
        knowable = _stamp(doc.get("knowable_at"))
        out.append(Unit("normalized_doc", str(doc.get("doc_id") or path.stem), str(path),
                        tuple(k for k in keys if k),
                        at=str(doc.get("knowable_at") or "") if knowable else _mtime(path),
                        pit=knowable is not None,
                        text=_snippet(doc.get("title"), doc.get("summary"), doc.get("text"))))
    return out, nxt, missed


def units_claims(conn: Any, cursor: dict[str, Any], gaps: list[dict[str, str]]
                 ) -> tuple[list[Unit], dict[str, int], dict[str, int]]:
    """The registry's claims table, split into news-like claims and the rest."""
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT claim_id, doc_id, source_id, kind, knowable_at, created_at, instruments_json, "
            "text, mechanism_id FROM claims ORDER BY created_at DESC LIMIT ?",
            (MAX_REGISTRY_ROWS,))]
    except Exception:                                    # an older file lacks text/mechanism_id
        try:
            rows = [dict(r) for r in conn.execute(
                "SELECT claim_id, doc_id, source_id, kind, knowable_at, created_at, "
                "instruments_json FROM claims ORDER BY created_at DESC LIMIT ?",
                (MAX_REGISTRY_ROWS,))]
        except Exception:                                # the table is absent on a fresh file
            rows = []
    if not rows:
        gaps.append({"what": "registry claims table", "why": "no claim has been recorded on this "
                                                             "host; claim and news ingestion are "
                                                             "UNMEASURED, not zero"})
    buckets: dict[str, list[Unit]] = {"claim": [], "news_claim": []}
    for row in rows:
        kind = "news_claim" if str(row.get("kind") or "").lower() in NEWS_KINDS else "claim"
        instruments = _json_field(row.get("instruments_json"))
        syms = tuple(str(s).upper() for s in instruments[:12]) if isinstance(instruments, list) \
            else ()
        at = str(row.get("knowable_at") or "")
        buckets[kind].append(Unit(
            kind, str(row.get("claim_id") or ""), "",
            tuple(k for k in (str(row.get("claim_id") or ""), str(row.get("doc_id") or ""),
                              str(row.get("source_id") or "")) if k),
            syms, at=at if _stamp(at) else str(row.get("created_at") or ""),
            pit=_stamp(at) is not None, text=_snippet(row.get("text")),
            mechanism=str(row.get("mechanism_id") or "")))
    out: list[Unit] = []
    nxt: dict[str, int] = {}
    missed: dict[str, int] = {}
    for kind, items in buckets.items():
        picked, nxt[kind], missed[kind] = _window(items, kind, cursor, KIND_CAP[kind])
        out.extend(picked)
    return out, nxt, missed


def units_intel_rows(cursor: dict[str, Any], gaps: list[dict[str, str]], deadline: float
                     ) -> tuple[list[Unit], int, int]:
    """Every row under BOTH `data/intelligence` roots -- the seats' donations, whatever shape."""
    from research.discovery_compiler import rows_of  # the desk's own tolerant row reader
    files: list[Path] = []
    for root in INTEL_DIRS:
        if not root.exists():
            gaps.append({"what": str(root), "why": "seat donation tree absent on this host; its "
                                                   "row ingestion is UNMEASURED, not zero"})
            continue
        files.extend(sorted(p for p in root.rglob("*.json") if p.is_file()))
        files.extend(sorted(p for p in root.rglob("*.jsonl") if p.is_file()))
    files.sort()
    picked, nxt, missed_files = _window(files, "intel_row", cursor, MAX_INTEL_FILES)
    out: list[Unit] = []
    for path in picked:
        if len(out) >= KIND_CAP["intel_row"] or time.monotonic() > deadline:
            break
        if path.suffix == ".jsonl":
            rows = []
            for line in (_read_text(path) or "").splitlines()[:MAX_ROWS_PER_FILE]:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
        else:
            rows = rows_of(_read_json(path))[:MAX_ROWS_PER_FILE]
        stamp = _mtime(path)
        rel = _rel(path)
        for i, row in enumerate(rows):
            if len(out) >= KIND_CAP["intel_row"]:
                break
            ident = str(row.get("id") or row.get("cell") or row.get("claim_id") or i)
            sym = str(row.get("symbol") or row.get("sym") or "").upper()
            declared = _stamp(row.get("at") or row.get("generated_at"))
            syms = tuple(str(x).upper() for x in (row.get("symbols") or [])[:12]
                         if isinstance(row.get("symbols"), list) and x)
            out.append(Unit("intel_row", f"{rel}#{ident}", str(path),
                            tuple(k for k in (ident, rel, path.stem, path.parent.name) if k),
                            (sym,) if sym else syms,
                            at=str(row.get("at") or row.get("generated_at") or "") if declared
                            else stamp, pit=declared is not None,
                            text=_snippet(*(row.get(k) for k in ("mechanism", "why", "claim",
                                                                 "title", "thesis", "text"))),
                            mechanism=str(row.get("mechanism") or "")))
    return out, nxt, missed_files


def _snippet(*parts: Any, limit: int = 600) -> str:
    """The first `limit` characters of the non-empty string parts, joined."""
    text = " ".join(str(p).strip() for p in parts if isinstance(p, str) and p.strip())
    return text[:limit]


def _read_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _rel(path: Path) -> str:
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def axis_units(path: Path) -> list[Unit]:
    """One unit per SERIES in an axis file: `series[sid]` where the file carries series, one per
    symbol where it carries rows (bis/cot are per-symbol panels and that is their series).

    THE HEADER IS READ, NEVER THE PANEL. `bis.json` is 81 MB on this box and 271 MB once parsed;
    this organ needs its series NAMES, not its 464,803 rows, and on a machine with 8 GB and the
    live terminal on it an hourly full parse is how a ledger becomes the outage.
    """
    doc = _axis_header(path)
    if not isinstance(doc, dict):
        return []
    kind = "country_plane" if path.stem[:3] in ("kr_", "jp_") else "axis_series"
    axis = str(doc.get("axis") or path.stem)
    at = str(doc.get("at") or "") if _stamp(doc.get("at")) else _mtime(path)
    rows = doc.get("rows") if isinstance(doc.get("rows"), list) else []
    # THE FILE'S OWN DECLARATION COUNTS. `bis.json` is read by head, so its rows are not in hand;
    # its `shape` line names `knowable_at` as the row key, and that declaration is the evidence --
    # refusing to read it would report the desk's best-stamped panel as un-certified.
    pit = bool(doc.get("vintage_note") or doc.get("knowable_lag_days")
               or "knowable_at" in str(doc.get("shape") or "")
               or (rows and isinstance(rows[0], dict) and "knowable_at" in rows[0]))
    name = f"axis:{path.stem}"
    out: list[Unit] = []
    series = doc.get("series")
    if isinstance(series, dict):
        for sid in sorted(series):
            out.append(Unit(kind, f"{path.stem}:{sid}", str(path),
                            (sid.lower(), f"{axis}:{sid}".lower(), path.stem), at=at, pit=pit,
                            dataset_name=name))
    symbols = doc.get("symbols")
    if not isinstance(symbols, list) and rows:
        symbols = sorted({str(r.get("symbol") or "") for r in rows[:5000]
                          if isinstance(r, dict) and r.get("symbol")})
    for sym in (symbols or [])[:400]:
        out.append(Unit(kind, f"{path.stem}:{sym}", str(path),
                        (str(sym).lower(), f"{axis}:{sym}".lower(), path.stem),
                        (str(sym).upper(),), at=at, pit=pit, dataset_name=name))
    return out


def units_axes(cursor: dict[str, Any], gaps: list[dict[str, str]]
               ) -> tuple[list[Unit], dict[str, int], dict[str, int]]:
    if not AXES.exists():
        gaps.append({"what": str(AXES), "why": "no axis store on this host; macro-series "
                                               "ingestion is UNMEASURED, not zero"})
        return [], {}, {}
    buckets: dict[str, list[Unit]] = {"axis_series": [], "country_plane": []}
    for path in sorted(AXES.glob("*.json")):
        for unit in axis_units(path):
            buckets[unit.kind].append(unit)
    if not buckets["country_plane"]:
        gaps.append({"what": "data/axes/kr_*, jp_*", "why": "no country data plane has landed on "
                                                            "this host; the country lane is "
                                                            "UNMEASURED, not zero"})
    out: list[Unit] = []
    nxt: dict[str, int] = {}
    missed: dict[str, int] = {}
    for kind, items in buckets.items():
        picked, nxt[kind], missed[kind] = _window(items, kind, cursor, KIND_CAP[kind])
        out.extend(picked)
    return out, nxt, missed


def units_tape_days(cursor: dict[str, Any], gaps: list[dict[str, str]]
                    ) -> tuple[list[Unit], int, int]:
    if not TAPE_TICKS.exists():
        gaps.append({"what": str(TAPE_TICKS), "why": "no tick tape on this host; instrument-day "
                                                     "ingestion is UNMEASURED, not zero"})
        return [], 0, 0
    files = sorted(TAPE_TICKS.glob("*/*.parquet"))
    picked, nxt, missed = _window(files, "tape_day", cursor, KIND_CAP["tape_day"])
    out = [Unit("tape_day", f"{f.parent.name}/{f.stem}", str(f),
                (f.parent.name.lower(), f.stem), (f.parent.name.upper(),),
                at=(str(_stamp(f.stem) or "") or _mtime(f)), pit=_stamp(f.stem) is not None)
           for f in picked]
    return out, nxt, missed


def units_universe_bars(cursor: dict[str, Any], gaps: list[dict[str, str]]
                        ) -> tuple[list[Unit], int, int]:
    if not UNIVERSE.exists():
        gaps.append({"what": str(UNIVERSE), "why": "no universe bar store on this host; bar "
                                                   "ingestion is UNMEASURED, not zero"})
        return [], 0, 0
    files = sorted(UNIVERSE.glob("*.parquet"))
    picked, nxt, missed = _window(files, "universe_bars", cursor, KIND_CAP["universe_bars"])
    out: list[Unit] = []
    for path in picked:
        sym, chart = _sym_chart(path.stem)
        out.append(Unit("universe_bars", f"{sym}.{chart}", str(path),
                        (path.stem.lower(), sym.lower()), (sym,), chart, _mtime(path), pit=True))
    return out, nxt, missed


def units_sleeve_ledgers(cursor: dict[str, Any], gaps: list[dict[str, str]]
                         ) -> tuple[list[Unit], int, int]:
    """One unit per SLEEVE: the shadow replay ledgers, plus the live ledger's own sleeve tags."""
    items: list[Unit] = []
    if SHADOW_DIR.exists():
        for path in sorted(SHADOW_DIR.glob("ledger_*.json")):
            stem = path.stem[len("ledger_"):]
            sym, _, window = stem.partition("_")
            items.append(Unit("sleeve_ledger", stem, str(path),
                              (stem.lower(), f"{sym}|{window}".lower(), sym.lower()),
                              (sym.upper(),), at=_mtime(path), pit=True))
    else:
        gaps.append({"what": str(SHADOW_DIR), "why": "no shadow ledger directory on this host; "
                                                     "forward-clock ingestion is UNMEASURED"})
    if LIVE_LEDGER.exists():
        stamp = _mtime(LIVE_LEDGER)
        seen: set[str] = set()
        for line in (_read_text(LIVE_LEDGER) or "").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            name = str(row.get("sleeve") or "").strip() if isinstance(row, dict) else ""
            if not name or name.startswith("[") or name in seen:
                continue
            seen.add(name)
            items.append(Unit("sleeve_ledger", f"live:{name}", str(LIVE_LEDGER),
                              (name.lower(),), (str(row.get("symbol") or "").upper(),), at=stamp,
                              pit=True))
    else:
        gaps.append({"what": str(LIVE_LEDGER), "why": "no live ledger on this host; live-fill "
                                                      "ingestion is UNMEASURED, not zero"})
    picked, nxt, missed = _window(items, "sleeve_ledger", cursor, KIND_CAP["sleeve_ledger"])
    return picked, nxt, missed


def units_moat_series(cursor: dict[str, Any], gaps: list[dict[str, str]]
                      ) -> tuple[list[Unit], int, int]:
    files = sorted(MOAT_SERIES.glob("*/*.parquet")) if MOAT_SERIES.exists() else []
    if not files:
        gaps.append({"what": str(MOAT_SERIES), "why": "the moat series store is empty or absent "
                                                      "on this host; derived-series ingestion is "
                                                      "UNMEASURED, not zero"})
        return [], 0, 0
    picked, nxt, missed = _window(files, "moat_series", cursor, KIND_CAP["moat_series"])
    out = [Unit("moat_series", f"{f.parent.name}/{f.stem}", str(f),
                (f.parent.name.lower(), f.stem.lower()), (f.stem.upper(),), at=_mtime(f))
           for f in picked]
    return out, nxt, missed


# --------------------------------------------------------------------------- the index
@dataclass
class Index:
    """What the registry already NAMES, split into exploited ground and explicit refusals."""

    exploited: set[str] = field(default_factory=set)
    blocked: set[str] = field(default_factory=set)
    symbols: set[str] = field(default_factory=set)
    symbol_chart: set[str] = field(default_factory=set)
    handed: set[str] = field(default_factory=set)
    #: Candidates a judge has NOT yet spoken about. A datum they name is a CANDIDATE_INPUT.
    live_candidates: set[str] = field(default_factory=set)
    #: Candidates terminally judged that did not survive. A datum only these name is
    #: RETIRED_WITH_EVIDENCE -- a real downstream state, not an absence of one.
    retired: set[str] = field(default_factory=set)
    #: Candidates that survived. The one thing that makes a datum PREDICTIVE rather than UNTESTED.
    survived: set[str] = field(default_factory=set)
    #: The instrument indexes, split the same way. Without the split a killed candidate's symbol
    #: still answered CANDIDATE_INPUT and RETIRED_WITH_EVIDENCE was unreachable -- a state that
    #: can never be published is a state the enum does not really have.
    live_symbols: set[str] = field(default_factory=set)
    live_symbol_chart: set[str] = field(default_factory=set)
    retired_symbols: set[str] = field(default_factory=set)
    #: The registry's own `sources` rows, for the access labels: source_id -> row.
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: Claims a CONTRADICTS edge points at. Kept as evidence objects, never deleted.
    contradicted: set[str] = field(default_factory=set)
    n_discoveries: int = 0
    n_candidates: int = 0
    n_handoffs: int = 0
    #: Did the pass read the whole registry? False names where the deadline stopped it.
    complete: bool = True
    stopped_at: str = ""
    symbols_complete: bool = False
    #: This organ's own handoffs by state: how many converted, blocked, or still wait.
    handoff_states: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def _discovery_keys(row: dict[str, Any], *, own: bool = False) -> set[str]:
    """The keys a discovery NAMES. An own handoff contributes its unit's identity and nothing
    else: its `assets` are the unit's instruments, and letting those into the key set would make
    one stranded EURUSD tape day credit every EURUSD bar file the desk holds."""
    out: set[str] = set()
    _tokens(row.get("source_id"), out)
    _tokens(_json_field(row.get("payload_json")), out)
    if not own:
        _tokens(_json_field(row.get("required_data_json")), out)
        _tokens(_json_field(row.get("assets_json")), out)
    return out


def _candidate_keys(row: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    _tokens(row.get("source_id"), out)
    _tokens(_json_field(row.get("required_data_json")), out)
    _tokens(_json_field(row.get("params_json")), out)
    _tokens(row.get("symbol"), out)
    return out


#: Registry rows fetched per round trip while the index streams the whole table.
INDEX_FETCH = 5000


def _stream(conn: Any, sql: str, args: tuple[Any, ...] = ()) -> Any:
    """Rows of one query, fetched in blocks -- never the whole table in memory at once."""
    cur = conn.execute(sql, args)
    while True:
        block = cur.fetchmany(INDEX_FETCH)
        if not block:
            return
        for row in block:
            yield dict(row)


def _judged(row: dict[str, Any]) -> bool:
    return bool(row.get("terminal_gate") or row.get("judged_at"))


def build_index(conn: Any, wanted: set[str] | None = None,
                deadline: float | None = None) -> Index:
    """The exploited / blocked index, with this organ's own handoffs held out until they convert.

    Held out ON PURPOSE. A handoff discovery names its unit, so counting it would make
    `exploitation_share` rise by the act of measuring -- the denominator trick the laws forbid.
    A handoff earns the unit's EXPLOITED verdict only by reaching COMPILED/QUEUED/TESTED, being
    BLOCKED with a reason, or having a candidate carry its `discovery_id`.

    THE WHOLE REGISTRY, NOT ITS FIRST 20,000 ROWS (2026-09-30). This index used to read
    `R.discoveries(limit=20000)` -- the OLDEST twenty thousand, by `created_at` -- and
    `R.candidates(limit=20000)` -- the twenty thousand best by score out of a table the breadth
    review counts at 1,587,074 cells. So every handoff this organ minted after the 20,000th
    discovery was invisible to it: the unit stayed STRANDED forever however its handoff ended,
    and every instrument named only by a low-scoring candidate read as unexploited. Both are now
    STREAMED in full. Memory stays bounded because a key is kept only when some unit of THIS pass
    carries it (`wanted`), and the instrument sets come from one GROUP BY over the whole table.
    The pass says whether it finished (`complete`); a deadline hit is published, never hidden.
    """
    idx = Index()
    keep = (lambda ks: ks & wanted) if wanted is not None else (lambda ks: ks)

    def late() -> bool:
        return deadline is not None and time.monotonic() > deadline

    # THE INSTRUMENT SETS, over every candidate the registry holds, in one aggregate.
    with contextlib.suppress(Exception):
        for row in _stream(conn, (
                "SELECT UPPER(TRIM(symbol)) AS s, UPPER(COALESCE(chart,'')) AS c, COUNT(*) AS n, "
                "SUM(CASE WHEN COALESCE(terminal_gate,'')<>'' OR COALESCE(judged_at,'')<>'' "
                "THEN 1 ELSE 0 END) AS judged, "
                "SUM(CASE WHEN (COALESCE(terminal_gate,'')<>'' OR COALESCE(judged_at,'')<>'') "
                "AND COALESCE(survived,0)=0 THEN 1 ELSE 0 END) AS dead "
                "FROM research_candidates WHERE COALESCE(TRIM(symbol),'')<>'' GROUP BY 1, 2")):
            sym, chart = str(row["s"]), str(row["c"])
            idx.symbols.add(sym)
            idx.symbol_chart.add(f"{sym}.{chart}")
            if int(row["dead"] or 0):
                idx.retired_symbols.add(sym)
            if int(row["n"] or 0) > int(row["dead"] or 0):
                idx.live_symbols.add(sym)
                idx.live_symbol_chart.add(f"{sym}.{chart}")
        idx.symbols_complete = True
    by_id: dict[str, set[str]] = {}
    try:
        rows = _stream(conn, "SELECT * FROM discoveries")
        for row in rows:
            if late():
                idx.complete = False
                idx.stopped_at = "discoveries"
                break
            did = str(row.get("discovery_id") or "")
            state = str(row.get("state") or "").upper()
            own = str(row.get("source_type") or "") == SOURCE_TYPE
            keys = keep(_discovery_keys(row, own=own))
            idx.n_discoveries += 1
            if own:
                idx.n_handoffs += 1
                idx.handed.update(keys)
                idx.handoff_states[state] = idx.handoff_states.get(state, 0) + 1
            if keys:
                by_id[did] = keys
            if state == "BLOCKED":
                idx.blocked.update(keys)
            elif not own or state in CONVERTED_STATES:
                idx.exploited.update(keys)
                assets = _json_field(row.get("assets_json"))
                if not own and isinstance(assets, list):
                    idx.symbols.update(str(a).upper() for a in assets if a)
    except Exception as exc:                          # the table is absent on a fresh file
        idx.errors.append(f"discoveries: {type(exc).__name__}: {exc}")
    try:
        rows = _stream(conn, "SELECT * FROM research_candidates") if idx.complete else iter(())
        for row in rows:
            if late():
                idx.complete = False
                idx.stopped_at = "research_candidates"
                break
            idx.n_candidates += 1
            keys = keep(_candidate_keys(row))
            did = str(row.get("discovery_id") or "")
            if did and did in by_id:
                keys |= by_id[did]
            sym = str(row.get("symbol") or "").strip().upper()
            if not idx.symbols_complete and sym:
                idx.symbols.add(sym)
                idx.symbol_chart.add(f"{sym}.{str(row.get('chart') or '').upper()}")
            # the declared keys are EXPLOITED; the bare instrument is added only to the
            # predictive/retired/live sets, exactly as before -- a candidate on EURUSD must not
            # make every axis row that mentions EURUSD read as exploited
            idx.exploited.update(keys)
            if sym and (wanted is None or sym.lower() in wanted):
                keys.add(sym.lower())
            if not keys:
                continue
            judged, lived = _judged(row), bool(row.get("survived"))
            if lived:
                idx.survived.update(keys)
            if judged and not lived:
                idx.retired.update(keys)
            else:
                idx.live_candidates.update(keys)
    except Exception as exc:
        idx.errors.append(f"research_candidates: {type(exc).__name__}: {exc}")
    with contextlib.suppress(Exception):
        idx.sources = {str(r["source_id"]): dict(r)
                       for r in conn.execute("SELECT * FROM sources LIMIT ?",
                                             (MAX_REGISTRY_ROWS,))}
    with contextlib.suppress(Exception):
        idx.contradicted = {str(r[0]).lower() for r in conn.execute(
            "SELECT to_claim FROM claim_edges WHERE relation='CONTRADICTS' LIMIT ?",
            (MAX_REGISTRY_ROWS,))}
    return idx


def artifact_tokens(path: Path, budget: int = MAX_ARTIFACT_NODES) -> set[str]:
    """Every short string an artifact NAMES -- dict keys and string values, bounded.

    A token SET is why this is affordable. The alternative, a substring search of a multi-megabyte
    artifact per unit, is quadratic in the thing that grows: 1,500 units against four artifacts is
    thirty thousand scans of ten megabytes each, which is a pass that never finishes.
    """
    doc = _read_json(path)
    out: set[str] = set()
    stack: list[Any] = [doc]
    seen = 0
    while stack and seen < budget:
        node = stack.pop()
        seen += 1
        if isinstance(node, str):
            text = node.strip().lower()
            if text and len(text) <= 200:
                out.add(text)
        elif isinstance(node, dict):
            for key, value in node.items():
                out.add(str(key).strip().lower())
                stack.append(value)
        elif isinstance(node, list):
            stack.extend(node[:4000])
    return out


def consumer_index(gaps: list[dict[str, str]]) -> dict[str, set[str]]:
    """Which downstream consumer NAMES which datum, read once per pass."""
    out: dict[str, set[str]] = {}
    for state, path in CONSUMER_ARTIFACTS.items():
        tokens = artifact_tokens(path) if path.exists() else set()
        if not tokens:
            gaps.append({"what": str(path), "why": f"no artifact names a {state} consumer on this "
                                                   f"host; that state is UNMEASURED, never a NO"})
        out[state] = tokens
    return out


def macro_keys(path: Path | None = None) -> set[str]:
    """What `macro_intelligence` says it consumed. An absent artifact is an absent claim."""
    doc = _read_json(path or MACRO_REPORT)
    if not isinstance(doc, dict):
        return set()
    out: set[str] = set()
    _tokens(doc.get("consumed_units"), out)
    return out


# ------------------------------------------------------------- the three independent labels
def _source_row(unit: Unit, idx: Index) -> dict[str, Any]:
    for key in unit.all_keys():
        row = idx.sources.get(key)
        if isinstance(row, dict):
            return row
    return {}


def classify(unit: Unit, idx: Index) -> tuple[str, str, str]:
    """(access_label, credibility, predictive_state) -- THREE ANSWERS, never one.

    Legality of access, credibility and predictive value are independent. A FRINGE or
    CONTRADICTED public claim keeps its PUBLIC access label and stays in the store as an evidence
    object: it may be a crowding or narrative feature, and deleting it for being unreliable would
    destroy the only record that somebody said it. ACCESS_UNCLEAR IS QUALIFIED AND EXPLOITED --
    the quarantine was deleted on 2026-09-23 (LAWS 5e) -- and only the three refused labels, which
    carry the five refused ACTS, never become an alpha input.

    The vocabulary belongs to `libs/research/access_classifier`; when that module lands its
    verdict wins, and until then the same spellings are carried here so the join is a rename.
    """
    access = DEFAULT_ACCESS.get(unit.kind, "ACCESS_UNCLEAR")
    credibility = DEFAULT_CREDIBILITY.get(unit.kind, "UNKNOWN")
    predictive = "UNTESTED"
    row = _source_row(unit, idx)
    status = str(row.get("status") or "").strip().lower()
    licence = str(row.get("licence_note") or "").strip().lower()
    if row and status and status not in ("active", "candidate-cleared", "candidate_cleared"):
        access = "ACCESS_UNCLEAR"
    elif "licen" in licence:
        access = "LICENSED"
    if unit.all_keys() & idx.contradicted:
        credibility = "CONTRADICTED"
    keys = unit.all_keys()
    if keys & idx.survived:
        predictive = "PREDICTIVE"
    elif keys & idx.retired:
        predictive = "NOT_PREDICTIVE"
    elif credibility in ("CONTRADICTED", "FRINGE", "UNRELIABLE"):
        # KEPT, NOT DELETED. An unreliable public claim is still evidence that somebody said it,
        # and what people say is the raw material of a crowding feature.
        predictive = "NARRATIVE_FEATURE"
    if AC is not None:
        fn = getattr(AC, "classify", None)
        if callable(fn):
            with contextlib.suppress(Exception):
                got = fn({"kind": unit.kind, "unit_id": unit.unit_id, "path": unit.path,
                          "source": row, "dataset": unit.dataset})
                if isinstance(got, dict):
                    access = str(got.get("access_label") or access)
                    credibility = str(got.get("credibility") or credibility)
                    predictive = str(got.get("predictive_state") or predictive)
    return access, credibility, predictive


def label(unit: Unit, idx: Index) -> Unit:
    """The unit with its three labels attached; nothing else about it changes."""
    access, credibility, predictive = classify(unit, idx)
    return replace(unit, access_label=access, credibility=credibility,
                   predictive_state=predictive)


# ----------------------------------------------------------------- the downstream state
def downstream_state(unit: Unit, idx: Index, macro: set[str],
                     consumers: dict[str, set[str]]) -> tuple[str | None, str]:
    """EXACTLY ONE state per qualified datum, decided in the declared DOWNSTREAM_ORDER.

    A REFUSED datum gets NO state and says why: giving one a downstream state would be a record
    of it being used. Nothing else is parked -- the ACCESS_UNCLEAR quarantine that used to return
    None here was deleted on 2026-09-23 (LAWS 5e), so an unclear-access row owes a downstream
    state exactly like a PUBLIC one and its unresolved access is a note, not an exemption.
    """
    if unit.refused:
        return None, f"REFUSED ({unit.access_label}): " + REFUSAL_REASON.get(
            unit.access_label, "never an alpha input")
    keys = unit.all_keys()
    narrow = unit.consumer_keys()
    live_hit = unit.kind in SYMBOL_KEYED and bool(
        {f"{s}.{unit.chart}" for s in unit.symbols} & idx.live_symbol_chart
        or set(unit.symbols) & idx.live_symbols)
    retired_hit = unit.kind in SYMBOL_KEYED and bool(set(unit.symbols) & idx.retired_symbols)
    for state in DOWNSTREAM_ORDER:
        if state == "WORLD_MODEL_INPUT" and narrow & macro:
            return state, "macro_intelligence names this datum among its consumed units"
        if state in consumers and narrow & consumers[state]:
            return state, f"{CONSUMER_ARTIFACTS[state].name} names this datum"
        if state == "CANDIDATE_INPUT" and (keys & idx.live_candidates or live_hit):
            return state, "a candidate the gauntlet has not yet judged is cut on this datum"
        if state == "RETIRED_WITH_EVIDENCE" and (keys & idx.retired or retired_hit):
            return state, "every candidate on this datum was judged and did not survive"
        if state == "NEGATIVE_KNOWLEDGE" and keys & idx.blocked:
            return state, "a BLOCKED discovery names this datum with a stated reason"
    return "AWAITING_EXPERIMENT", "no consumer has reached this datum yet; an experiment is owed"


# --------------------------------------------------------------------------- the disposition
def disposition(unit: Unit, idx: Index, macro: set[str], now: datetime, grace_hours: float,
                consumers: dict[str, set[str]] | None = None) -> tuple[str, str]:
    """One unit's verdict and the reason that decided it, in precedence order.

    THE DISPOSITION AND THE DOWNSTREAM STATE READ THE SAME EVIDENCE, and they must: a datum the
    allocator's artifact names is EXPLOITED, not STRANDED. The first pass that added the consumer
    artifacts to one and not the other published 77 units with a downstream consumer and a
    STRANDED disposition, which is two organs disagreeing inside one file.
    """
    keys = unit.all_keys()
    narrow = unit.consumer_keys()
    if keys & idx.exploited:
        return "EXPLOITED", "a discovery or candidate names this unit by a declared key"
    if unit.kind in SYMBOL_KEYED:
        for sym in unit.symbols:
            if f"{sym}.{unit.chart}" in idx.symbol_chart:
                return "EXPLOITED", f"a candidate is cut on {sym} {unit.chart}"
            if sym in idx.symbols:
                return "EXPLOITED", f"a candidate or discovery names {sym}"
    for state, tokens in (consumers or {}).items():
        if narrow & tokens:
            return "EXPLOITED", f"{CONSUMER_ARTIFACTS[state].name} names this unit ({state})"
    if narrow & macro:
        return "EXPLOITED_MACRO", "macro_intelligence consumed this unit as a fusion feature"
    if keys & idx.blocked:
        return "BLOCKED", "a BLOCKED discovery names this unit with a stated reason"
    age = unit.age_h(now)
    if age is not None and age <= grace_hours:
        return "PENDING", f"ingested {age:.1f}h ago, inside the {grace_hours:g}h grace window"
    if age is None:
        return "STRANDED", ("no ingestion stamp, so the grace window cannot be claimed: "
                            "UNMEASURED recency is judged past grace, never inside it")
    return "STRANDED", f"ingested {age:.1f}h ago and nothing has named it"


#: WHERE A STRANDED UNIT GOES (2026-09-30). The handoff used to be a discovery whose mechanism was
#: the literal "ingested and unexploited: <kind>" -- which the compiler interprets as UNKNOWN, and
#: no registered family implements UNKNOWN, so EVERY child of EVERY handoff was refused at the
#: economic gate (reproduced: a EURUSD tape-day handoff closes to 41 children, all family None).
#: A stranded unit could only ever end BLOCKED, never as a cell -- and it waited behind the
#: compiler's oldest-first 200-per-pass queue to get even that. Each unit is now ROUTED to the
#: consumer that can actually use it, with the mechanism and information that consumer reads.
ROUTE_CONSUMERS: dict[str, str] = {
    "compile_now": ("discovery_compiler, priority drain: the routed mechanism's closure through "
                    "the three gates -> registry enqueue_candidate -> donated into "
                    "data/intelligence/discovery_compiler/ for the docket"),
    "class_book": ("cross_sectional_breadth: the equity class book ranks every classified share "
                   "CFD daily and donates through proposer_common into "
                   "data/intelligence/cross_sectional_breadth/ (the two-lane order: a share CFD "
                   "is never handed a single-name statistical family)"),
    "block_unclassified": ("universe classification: BLOCKED with the reason until MetaTrader's "
                           "registry classifies the symbol -- absence of a class is not a "
                           "permission (universe_policy)"),
}
#: The price-only mechanisms a registered family implements, rotated per unit so the stranded
#: instruments are spread over the mechanism axis instead of all tested for one idea.
PRICE_MECHANISMS: tuple[str, ...] = (
    "range_reversion", "trend_persistence", "breakout_liquidity", "volatility_shock",
    "session_handover", "regime_transition", "hedging_demand_close_flow",
    "session_information_handoff")
TEXT_KINDS: frozenset[str] = frozenset({"claim", "news_claim", "normalized_doc", "intel_row"})
ROUTES = BASE / "data" / "ingestion_routes.json"
MAX_ROUTES = 20000
#: Share of the pass budget the priority drain may use (after collection and the index).
DRAIN_SHARE = 0.85


def _lane(symbol: str) -> str:
    try:
        from research import universe_policy as up
        return str(up.lane(symbol))
    except Exception:
        return "unclassified"


def route_of(unit: Unit) -> dict[str, Any]:
    """The ONE consumer a stranded unit is routed to, with what that consumer needs."""
    syms = [s for s in unit.symbols if s]
    lanes = {s: _lane(s) for s in syms}
    hyp = [s for s in syms if lanes[s] == "hypothesis"]
    info, mech = "price_only", ""
    modality = UNIT_MODALITY.get(unit.kind, "")
    if unit.kind in TEXT_KINDS:
        mech = unit.mechanism if unit.mechanism in _contracts() else ""
        info = ""                                   # the contract's own information
    elif modality == "execution_records":
        mech, info = "execution_microstructure", "microstructure"
    elif unit.kind in ("axis_series", "country_plane"):
        if unit.dataset_name == "axis:cot":
            mech, info = "positioning_crowding", "positioning"
        else:
            mech, info = "macro_release", "macro"
    else:
        h = int(hashlib.sha1(f"{unit.kind}:{unit.unit_id}".encode()).hexdigest()[:8], 16)
        mech = PRICE_MECHANISMS[h % len(PRICE_MECHANISMS)]
    if unit.kind in SYMBOL_KEYED and syms and not hyp:
        action = "class_book" if any(v == "event" for v in lanes.values()) \
            else "block_unclassified"
    else:
        action = "compile_now"
    return {"action": action, "consumer": ROUTE_CONSUMERS[action], "mechanism": mech,
            "information": info, "symbols": hyp if action == "compile_now" else syms,
            "chart": unit.chart,
            "why": unit.text or f"stranded {unit.kind} {unit.unit_id}: routed to {mech or 'text'}"}


def _contracts() -> frozenset[str]:
    try:
        from research import transformation_miners as TM
        return frozenset(TM.CONTRACTS)
    except Exception:
        return frozenset()


def _handoff(unit: Unit, conn: Any, route: dict[str, Any] | None = None) -> tuple[str, bool]:
    """Record (or find) the unit's handoff discovery. The recorded mechanism string is the one
    every earlier pass used, so the content hash -- and therefore the discovery -- is the SAME
    one: routing re-uses the handoff, it never mints a twin."""
    return R.record_discovery(
        source_id=f"{SOURCE_TYPE}:{unit.kind}:{unit.unit_id}"[:400],
        source_type=SOURCE_TYPE, mechanism=f"ingested and unexploited: {unit.kind}",
        origin="MOAT", generator="ingestion_ledger", assets=list(unit.symbols),
        horizons=[unit.chart] if unit.chart else [],
        information=unit.kind, economic_rationale=RULE,
        payload={"unit_kind": unit.kind, "unit_id": unit.unit_id, "path": unit.path,
                 "why": "ingested and unexploited", "ingested_at": unit.at or UNMEASURED,
                 "keys": sorted(unit.all_keys())[:16],
                 **({"route": route["action"], "routed_mechanism": route["mechanism"]}
                    if route else {})}, conn=conn)


def hand_to_compiler(units: list[Unit], conn: Any, limit: int = MAX_STRANDED_HANDOFFS
                     ) -> tuple[int, int]:
    """A stranded unit becomes a DISCOVERY, so the compiler closes it. Returns (new, seen).

    Idempotent by construction: `record_discovery` hashes (source_id, mechanism, assets, rule),
    all four of which are functions of the unit alone, so the tenth pass over the same stranded
    unit creates nothing and returns the id the first pass minted.
    """
    new = seen = 0
    for unit in units[:limit]:
        if unit.refused:
            # A refused datum never becomes an alpha input, and a discovery IS the road to one.
            continue
        _did, created = _handoff(unit, conn)
        new += int(created)
        seen += int(not created)
    return new, seen


def _load_routes(path: Path | None = None) -> dict[str, Any]:
    doc = _read_json(path or ROUTES)
    rows = doc.get("routes") if isinstance(doc, dict) else None
    return rows if isinstance(rows, dict) else {}


def _drain(overrides: dict[str, dict[str, Any]], conn: Any, deadline: float | None
           ) -> dict[str, Any]:
    """The compiler's priority drain over this pass's routed handoffs. Never raises."""
    try:
        from research import discovery_compiler as DC
        return DC.expand_ids(overrides, conn=conn, deadline=deadline)
    except Exception as exc:
        return {"requested": len(overrides), "expanded": 0,
                "errors": [f"{type(exc).__name__}: {exc}"]}


def route_stranded(units: list[Unit], conn: Any, *, deadline: float | None = None,
                   dry_run: bool = False, routes_path: Path | None = None) -> dict[str, Any]:
    """EVERY stranded unit to a named consumer, this pass. Returns the routing block.

    compile_now          handoff discovery + the compiler's priority drain (`expand_ids`), with
                         the routed mechanism, information and hypothesis-lane instruments;
    class_book           share CFDs: the equity class book is their consumer, no single-name
                         statistical cell is minted (the two-lane order);
    block_unclassified   a symbol no class claims: the handoff is BLOCKED with that reason --
                         a lawful disposition, and the day the symbol is classified it reroutes.
    `unrouted` counts units that got no route; the fence holds it at 0.
    """
    when = _iso(_now())
    book = _load_routes(routes_path)
    by_action: dict[str, int] = {}
    overrides: dict[str, dict[str, Any]] = {}
    unrouted: list[str] = []
    errors: list[str] = []
    routed = 0
    handoffs = {True: 0, False: 0}
    for unit in units:
        if unit.refused:
            continue
        ident = f"{unit.kind}:{unit.unit_id}"
        try:
            route = route_of(unit)
        except Exception as exc:
            unrouted.append(ident)
            errors.append(f"{ident}: {type(exc).__name__}: {exc}")
            continue
        action = route["action"]
        by_action[action] = by_action.get(action, 0) + 1
        did = ""
        if not dry_run and action in ("compile_now", "block_unclassified"):
            try:
                did, created = _handoff(unit, conn, route)
                handoffs[created] += 1
                if action == "block_unclassified":
                    R.set_discovery_state(did, "BLOCKED", reason=(
                        f"UNCLASSIFIED: {', '.join(unit.symbols)} carries no asset class in "
                        "MetaTrader's registry, so no lane may hunt it; it reroutes the pass "
                        "after it is classified"), conn=conn)
                else:
                    overrides[did] = {k: v for k, v in (
                        ("mechanism", route["mechanism"]), ("information", route["information"]),
                        ("symbols", route["symbols"]), ("chart", route["chart"]),
                        ("why", route["why"])) if v}
            except Exception as exc:
                unrouted.append(ident)
                errors.append(f"{ident}: {type(exc).__name__}: {exc}")
                continue
        prev = book.get(ident) if isinstance(book.get(ident), dict) else {}
        book[ident] = {"action": action, "consumer": route["consumer"],
                       "mechanism": route["mechanism"], "symbols": route["symbols"],
                       "discovery_id": did or prev.get("discovery_id") or "",
                       "first_routed": prev.get("first_routed") or when, "last_routed": when,
                       "times_routed": int(prev.get("times_routed") or 0) + 1}
        routed += 1
    drain: dict[str, Any] = {"requested": len(overrides), "expanded": 0}
    if overrides and not dry_run:
        drain = _drain(overrides, conn, deadline)
    if not dry_run:
        if len(book) > MAX_ROUTES:
            book = dict(sorted(book.items(), key=lambda kv: str(kv[1].get("last_routed")))
                        [-MAX_ROUTES:])
        with contextlib.suppress(OSError):
            _write_atomic(routes_path or ROUTES, {
                "updated": when, "consumers": ROUTE_CONSUMERS, "routes": book,
                "rule": "every stranded unit is routed to exactly one named consumer each pass "
                        "it is stranded; the route is re-derived, never trusted from the book"})
    return {"stranded": len([u for u in units if not u.refused]),
            "routed": routed, "unrouted": len(unrouted),
            "handoffs_new": handoffs[True], "handoffs_existing": handoffs[False],
            "unrouted_units": unrouted[:40], "by_action": by_action,
            "consumers": {a: ROUTE_CONSUMERS[a] for a in by_action},
            "drain": drain, "errors": errors[:20], "routes_path": str(routes_path or ROUTES)}


# --------------------------------------------------------------------------- the pass
def collect(cursor: dict[str, Any], conn: Any, gaps: list[dict[str, str]], deadline: float
            ) -> tuple[list[Unit], dict[str, int], dict[str, int]]:
    """Every unit this pass will judge, with the next cursor and what it did not reach."""
    units: list[Unit] = []
    nxt: dict[str, int] = {}
    missed: dict[str, int] = {}
    got, nxt["normalized_doc"], missed["normalized_doc"] = units_normalized_docs(cursor, gaps)
    units += got
    got, cn, cm = units_claims(conn, cursor, gaps)
    units += got
    nxt.update(cn)
    missed.update(cm)
    if time.monotonic() <= deadline:
        got, nxt["intel_row"], missed["intel_row"] = units_intel_rows(cursor, gaps, deadline)
        units += got
    got, an, am = units_axes(cursor, gaps)
    units += got
    nxt.update(an)
    missed.update(am)
    got, nxt["tape_day"], missed["tape_day"] = units_tape_days(cursor, gaps)
    units += got
    got, nxt["universe_bars"], missed["universe_bars"] = units_universe_bars(cursor, gaps)
    units += got
    got, nxt["sleeve_ledger"], missed["sleeve_ledger"] = units_sleeve_ledgers(cursor, gaps)
    units += got
    got, nxt["moat_series"], missed["moat_series"] = units_moat_series(cursor, gaps)
    units += got
    return units, nxt, missed


def contract_index(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """dataset id -> {state, ref, contract_hash} from the feature compiler's contracts.json --
    its per-dataset rows and its per-modality rows (keyed `modality:<name>`). Empty when the
    compiler has not run, which reads CONTRACT_MISSING for everything: the measurement, not a
    pass."""
    doc = _read_json(path or CONTRACTS_JSON)
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(doc, dict):
        return out
    for block, prefix in (("contracts", ""), ("modality_contracts", "modality:")):
        rows = doc.get(block)
        if not isinstance(rows, dict):
            continue
        for key, row in rows.items():
            if not isinstance(row, dict):
                continue
            admission = row.get("admission") if isinstance(row.get("admission"), dict) else {}
            contract = row.get("contract") if isinstance(row.get("contract"), dict) else {}
            out[f"{prefix}{key}"] = {
                "state": "CONTRACTED" if admission.get("admitted") else "CONTRACT_INCOMPLETE",
                "ref": f"{prefix}{key}", "contract_hash": contract.get("contract_hash")}
    return out


def contract_state(unit: Unit, index: dict[str, dict[str, Any]]) -> tuple[str, str]:
    """(state, contract ref) for one unit: its dataset's own contract, else its modality's,
    else CONTRACT_MISSING with the dataset it would be written for."""
    dataset = unit.dataset_name or f"kind:{unit.kind}"
    modality = "positioning" if dataset == "axis:cot" else UNIT_MODALITY.get(unit.kind, "")
    row = index.get(dataset) or (index.get(f"modality:{modality}") if modality else None)
    if row is None:
        return "CONTRACT_MISSING", dataset
    return str(row.get("state") or "CONTRACT_INCOMPLETE"), str(row.get("ref") or dataset)


def contract_audit(units: list[Unit], index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The contract defect rows for this pass. `brake` is False by construction: nothing here
    changes a disposition, a downstream state or a handoff."""
    by_state: dict[str, int] = dict.fromkeys(CONTRACT_STATES, 0)
    defects: dict[str, dict[str, Any]] = {}
    for unit in units:
        state, ref = contract_state(unit, index)
        by_state[state] = by_state.get(state, 0) + 1
        if state == "CONTRACT_MISSING":
            row = defects.setdefault(ref, {
                "dataset": ref, "kind": unit.kind,
                "modality": UNIT_MODALITY.get(unit.kind, "UNCLASSIFIED"), "units": 0,
                "defect": "CONTRACT_MISSING",
                "fix": "declare the dataset's DatasetContract (feature_compiler CONTRACT_BASE or "
                       "a per-dataset row); the unit is exploited meanwhile"})
            row["units"] += 1
    return {"rule": CONTRACT_RULE, "brake": False, "source": str(CONTRACTS_JSON),
            "index_size": len(index), "by_state": by_state, "n_defects": len(defects),
            "defects": sorted(defects.values(), key=lambda d: -int(d["units"]))[:40]}


def build(*, grace_hours: float = GRACE_HOURS, budget_s: float = BUDGET_S,
          max_units: int = MAX_UNITS, now: datetime | None = None, conn: Any = None,
          dry_run: bool = False) -> dict[str, Any]:
    """Register, dispose, hand the stranded to the compiler, and publish the contract."""
    started = time.monotonic()
    deadline = started + float(budget_s)
    when = now or _now()
    close = conn is None
    c = conn if conn is not None else R.connect()
    try:
        prev = _read_json(OUT)
        cursor = dict((prev or {}).get("scan_cursor") or {}) if isinstance(prev, dict) else {}
        gaps: list[dict[str, str]] = []
        units, nxt, missed = collect(cursor, c, gaps, deadline)
        if len(units) > max_units:
            missed["budget_cap"] = len(units) - max_units
            units = units[:max_units]
        wanted: set[str] = set()
        for u in units:
            wanted |= u.all_keys()
            wanted |= {x.lower() for x in u.symbols if x}
        # the index may use up to half the pass; the routing drain gets up to DRAIN_SHARE
        idx = build_index(c, wanted=wanted, deadline=started + 0.5 * float(budget_s))
        if not idx.complete:
            gaps.append({"what": "registry index", "why": f"the deadline stopped the full "
                                                          f"registry read at {idx.stopped_at}; "
                                                          "units only a later row names read "
                                                          "STRANDED this pass"})
        macro = macro_keys()
        if not macro:
            gaps.append({"what": str(MACRO_REPORT),
                         "why": "no macro-intelligence artifact names the units it consumed; "
                                "EXPLOITED_MACRO is UNMEASURED this pass, never assumed zero"})
        consumers = consumer_index(gaps)
        units = [label(u, idx) for u in units]
        contract_idx = contract_index()
        prev_doc = prev if isinstance(prev, dict) else {}
        prev_counts = dict(prev_doc.get("stranding_counts") or {})
        passes = int(prev_doc.get("passes") or 0) + 1
        by_kind: dict[str, int] = {}
        table: dict[str, dict[str, int]] = {}
        datasets: dict[str, dict[str, Any]] = {}
        rows: list[dict[str, Any]] = []
        stranded: list[Unit] = []
        counts: dict[str, int] = {}
        states: dict[str, int] = dict.fromkeys(DOWNSTREAM_STATES, 0)
        access: dict[str, int] = {}
        credible: dict[str, int] = {}
        predictive: dict[str, int] = {}
        refusals: list[dict[str, str]] = []
        stranded_data: list[dict[str, Any]] = []
        unstated: list[str] = []
        stamp = _iso(when)
        for unit in units:
            verdict, why = disposition(unit, idx, macro, when, grace_hours, consumers)
            state, state_why = downstream_state(unit, idx, macro, consumers)
            if unit.qualified and state is None:       # the rule, enforced rather than asserted
                unstated.append(f"{unit.kind}:{unit.unit_id}")
            by_kind[unit.kind] = by_kind.get(unit.kind, 0) + 1
            cell = table.setdefault(unit.kind, dict.fromkeys(DISPOSITIONS, 0))
            cell[verdict] += 1
            access[unit.access_label] = access.get(unit.access_label, 0) + 1
            credible[unit.credibility] = credible.get(unit.credibility, 0) + 1
            predictive[unit.predictive_state] = predictive.get(unit.predictive_state, 0) + 1
            if state is not None:
                states[state] += 1
            elif unit.refused:
                refusals.append({"kind": unit.kind, "unit_id": unit.unit_id,
                                 "access_label": unit.access_label, "reason": state_why})
            block = datasets.setdefault(unit.dataset, {
                "kind": unit.kind, "units": 0, "pit_stamped": 0,
                "pit_basis": PIT_BASIS.get(unit.kind, UNMEASURED),
                "dispositions": dict.fromkeys(DISPOSITIONS, 0),
                "downstream_states": {}, "access_labels": {}, "credibility": {},
                "predictive_states": {}, "symbols": []})
            block["units"] += 1
            block["pit_stamped"] += int(unit.pit)
            block["dispositions"][verdict] += 1
            for name, key in (("downstream_states", state or "NONE"),
                              ("access_labels", unit.access_label),
                              ("credibility", unit.credibility),
                              ("predictive_states", unit.predictive_state)):
                block[name][key] = block[name].get(key, 0) + 1
            if unit.symbols and len(block["symbols"]) < 24:
                block["symbols"] = sorted({*block["symbols"], *(s for s in unit.symbols if s)})
            # A DATUM IS STRANDED WHEN IT IS RE-INGESTED AND NO CONSUMER HAS REACHED IT. Only
            # units PAST GRACE count: one inside the grace window is lawfully awaiting an
            # experiment, and counting it would make every fresh file a defect within the hour.
            ident = f"{unit.kind}:{unit.unit_id}"
            # NO DOWNSTREAM CONSUMER IS THE TEST, not the disposition. A datum an UNPROCESSED
            # discovery names is EXPLOITED by the ledger's own contract and has still reached
            # nobody -- AWAITING_EXPERIMENT says exactly that -- so keying the stranding count to
            # the STRANDED disposition counted 145 of the 751 data the principal's rule is about.
            unconsumed = (unit.qualified and verdict != "PENDING"
                          and state == "AWAITING_EXPERIMENT")
            ingestions = (int(prev_counts.get(ident) or 0) + 1) if unconsumed else 0
            if unconsumed:
                counts[ident] = ingestions
                if verdict == "STRANDED":
                    stranded.append(unit)
                if ingestions >= STRANDING_INGESTIONS:
                    stranded_data.append({
                        "unit_id": unit.unit_id, "kind": unit.kind, "dataset": unit.dataset,
                        "path": unit.path, "ingestions": ingestions,
                        "access_label": unit.access_label, "credibility": unit.credibility,
                        "predictive_state": unit.predictive_state,
                        "ingested_at": unit.at or UNMEASURED})
            rows.append({"at": stamp, "kind": unit.kind, "dataset": unit.dataset,
                         "contract": contract_state(unit, contract_idx)[0],
                         "unit_id": unit.unit_id, "path": unit.path, "disposition": verdict,
                         "why": why, "pit": bool(unit.pit), "downstream_state": state,
                         "downstream_why": state_why, "access_label": unit.access_label,
                         "credibility": unit.credibility,
                         "predictive_state": unit.predictive_state, "ingestions": ingestions,
                         "ingested_at": unit.at or UNMEASURED})
        if unstated:                              # pragma: no cover - impossible by construction
            gaps.append({"what": "downstream_state",
                         "why": f"{len(unstated)} qualified datum(s) carry no downstream state: "
                                + DOWNSTREAM_RULE})
        handed = repeats = 0
        routing = route_stranded(stranded, c, dry_run=dry_run,
                                 deadline=started + DRAIN_SHARE * float(budget_s))
        handed, repeats = int(routing.get("handoffs_new") or 0), \
            int(routing.get("handoffs_existing") or 0)
        counts = dict(sorted(counts.items(), key=lambda kv: -kv[1])[:MAX_STRANDING_COUNTS])
        stranded_data.sort(key=lambda r: -int(r["ingestions"]))
        totals = {d: sum(cell[d] for cell in table.values()) for d in DISPOSITIONS}
        past_grace = len(units) - totals["PENDING"]
        pass_share = (None if past_grace <= 0 else
                      round((totals["EXPLOITED"] + totals["EXPLOITED_MACRO"] + totals["BLOCKED"])
                            / past_grace, 6))
        pop, pop_units = population(LEDGER, rows)
        pop_past_grace = pop_units - pop["PENDING"]
        share = (None if pop_past_grace <= 0 else
                 round((pop["EXPLOITED"] + pop["EXPLOITED_MACRO"] + pop["BLOCKED"])
                       / pop_past_grace, 6))
        if share is None:
            gaps.append({"what": "exploitation_share", "why": "no unit past the grace window was "
                                                              "reached this pass; the share is "
                                                              "UNMEASURED, which is a verdict"})
        stranded.sort(key=lambda u: (u.age_h(when) or 0.0), reverse=True)
        payload = {
            "at": stamp,
            "units_by_kind": by_kind,
            "dispositions": table,
            "datasets": datasets,
            "exploitation_share": share,
            "stranded_handed_to_compiler": handed,
            # THE ROUTER'S RECORD: every STRANDED unit of this pass and the consumer it went to.
            # `n_stranded_units` is the fenced count (check_ingestion_exploitation ratchets it
            # DOWN only) and `stranded_routing.unrouted` must be 0.
            "n_stranded_units": int(pop.get("STRANDED") or 0),
            "stranded_routing": routing,
            "top_stranded": [{"kind": u.kind, "unit_id": u.unit_id, "path": u.path,
                              "ingested_at": u.at or UNMEASURED,
                              "age_h": None if (a := u.age_h(when)) is None else round(a, 1)}
                             for u in stranded[:MAX_TOP_STRANDED]],
            "downstream_states": states,
            "downstream_rule": DOWNSTREAM_RULE,
            "access_labels": dict(sorted(access.items())),
            "credibility": dict(sorted(credible.items())),
            "predictive_states": dict(sorted(predictive.items())),
            "quarantined": sum(1 for u in units if u.quarantined),
            "refused": len(refusals),
            "refusals": refusals[:MAX_STRANDED_DATA],
            "n_stranded_data": len(stranded_data),
            "stranded_data": stranded_data[:MAX_STRANDED_DATA],
            "stranded_data_measured": passes >= STRANDING_INGESTIONS,
            "stranding_counts": counts,
            "passes": passes,
            "unmeasured": gaps,
            "contracts": contract_audit(units, contract_idx),
            "rule": RULE,
            "totals": totals,
            "pass_share": pass_share,
            "population": {"units": pop_units, "past_grace": pop_past_grace, "by_disposition": pop,
                           "basis": "each unit's most recent disposition over the ledger's tail "
                                    "plus this pass -- the fenced share is a property of the "
                                    "desk, not of where the rotating cursor landed"},
            "units_scanned": len(units),
            "units_past_grace": past_grace,
            "stranded_already_handed": repeats,
            "not_reached": {k: v for k, v in missed.items() if v},
            "scan_cursor": nxt,
            "grace_hours": grace_hours,
            "index": {"discoveries": idx.n_discoveries, "candidates": idx.n_candidates,
                      "complete": idx.complete, "stopped_at": idx.stopped_at,
                      "symbols_complete": idx.symbols_complete,
                      "handoff_states": idx.handoff_states, "errors": idx.errors[:10],
                      "own_handoffs_held_out": idx.n_handoffs,
                      "exploited_keys": len(idx.exploited), "blocked_keys": len(idx.blocked),
                      "symbols": len(idx.symbols)},
            "budget": {"budget_s": budget_s, "elapsed_s": round(time.monotonic() - started, 2),
                       "max_units": max_units,
                       "reached_deadline": time.monotonic() > deadline},
            "dry_run": bool(dry_run),
        }
        if not dry_run:
            _append_jsonl(LEDGER, rows)
            _write_atomic(OUT, payload)
        payload["rows_written"] = 0 if dry_run else len(rows)
        return payload
    finally:
        if close:
            c.close()


def summary_lines(doc: dict[str, Any]) -> list[str]:
    share = doc.get("exploitation_share")
    passed = doc.get("pass_share")
    lines = [f"ingestion contract: {doc.get('units_scanned')} unit(s) over "
             f"{len(doc.get('units_by_kind') or {})} kind(s); exploitation share "
             f"{UNMEASURED if share is None else format(float(share), '.2%')} over "
             f"{(doc.get('population') or {}).get('units')} known unit(s) "
             f"(this pass {UNMEASURED if passed is None else format(float(passed), '.2%')})"]
    for kind in sorted(doc.get("dispositions") or {}):
        cell = doc["dispositions"][kind]
        lines.append(f"  {kind:16} " + "  ".join(f"{SHORT[d]}={cell[d]:5}" for d in DISPOSITIONS))
    lines.append("  downstream  " + "  ".join(
        f"{k}={v}" for k, v in (doc.get("downstream_states") or {}).items() if v))
    lines.append("  access      " + "  ".join(
        f"{k}={v}" for k, v in (doc.get("access_labels") or {}).items()))
    lines.append("  credibility " + "  ".join(
        f"{k}={v}" for k, v in (doc.get("credibility") or {}).items())
        + "   predictive " + "  ".join(
            f"{k}={v}" for k, v in (doc.get("predictive_states") or {}).items()))
    lines.append(f"  quarantined {doc.get('quarantined')}  refused {doc.get('refused')}  "
                 f"DATA STRANDING {doc.get('n_stranded_data')} datum(s) ingested "
                 f">= {STRANDING_INGESTIONS}x with no consumer"
                 + ("" if doc.get("stranded_data_measured") else f"  ({UNMEASURED}: pass "
                                                                 f"{doc.get('passes')} of "
                                                                 f"{STRANDING_INGESTIONS})"))
    for row in (doc.get("stranded_data") or [])[:8]:
        lines.append(f"    STRANDED DATUM x{row['ingestions']} {row['kind']:16} "
                     f"{str(row['unit_id'])[:58]:58} {row['access_label']}")
    lines.append(f"  stranded handed to the compiler: {doc.get('stranded_handed_to_compiler')} "
                 f"new, {doc.get('stranded_already_handed')} already open")
    routing = doc.get("stranded_routing") or {}
    drain = routing.get("drain") or {}
    lines.append(f"  STRANDED units {doc.get('n_stranded_units')} (population); this pass routed "
                 f"{routing.get('routed')} of {routing.get('stranded')}, unrouted "
                 f"{routing.get('unrouted')} -- {routing.get('by_action')}; drain expanded "
                 f"{drain.get('expanded')} of {drain.get('requested')}, compiled "
                 f"{drain.get('compiled')} cell(s)")
    for row in (doc.get("top_stranded") or [])[:8]:
        lines.append(f"    STRANDED {row['kind']:16} {str(row['unit_id'])[:60]:60} "
                     f"age {row['age_h']}h")
    for gap in doc.get("unmeasured") or []:
        lines.append(f"  {UNMEASURED} {gap['what']}: {gap['why']}")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="measure and print, write nothing")
    ap.add_argument("--grace-hours", type=float, default=GRACE_HOURS,
                    help="hours a freshly ingested unit may stay PENDING")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S, help="wall-clock budget")
    ap.add_argument("--max-units", type=int, default=MAX_UNITS, help="units judged this pass")
    args = ap.parse_args(argv)
    doc = build(grace_hours=args.grace_hours, budget_s=args.budget_s, max_units=args.max_units,
                dry_run=args.dry_run)
    for line in summary_lines(doc):
        print(line)
    print("dry run -- nothing written" if args.dry_run else f"-> {OUT}  -> {LEDGER}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
