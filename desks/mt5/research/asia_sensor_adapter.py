"""ASIA SENSOR ADAPTER -- every Asia observation the desk already stores, as universal sensor
contract observations appended to the ONE sensor ledger (MANDATE 2026-10-06 s2.5, s2.13).

WHAT THIS IS, AND WHAT IT IS NOT. A MAPPING. It fetches nothing, parses no page, and owns no
store: it reads the stores the Asia organs already write and hands each stored value to
`libs.research.sensor_contract.SensorLedger.append`, which is the only writer of the ledger and
owns dedup, revision detection and idempotency. It forks nothing of the contract and reads the
ledger only through its public accessors (`latest`, `latest_index`), never its index file. Where
the contract lacks something this adapter needs, the gap is named in `CONTRACT_GAPS` below (read
by the report); today there is none.

THE STORES IT READS, one mapping function per record type (the hook points):

  alt_proxies        `data/alt_proxies/obs/<source>.json`, the vintage store `alt_proxies`
                     keeps per source (first value + first-seen instant, last value + revision
                     instant, published time and its basis). Asian sources only (`ASIA`).
                     `map_alt_proxies_row` -> the FIRST print, and, when the store recorded a
                     revision, the LAST print as its own observation (the ledger turns it into a
                     revision row pointing at the first; the first is never edited).
  asia_parser        `data/lake/series/<id>.parquet|.csv` -- the parser bank's canonical frame
     frames          per registry source (`asia_sources.json`), PIT-stamped by `pit_stamp`.
                     Asian countries only. `map_asia_frame_row` -> one observation per (row,
                     numeric column).
  asia_parser        `data/lake/series/history/<root>.obs.jsonl` -- the APPEND-ONLY vintage
     history         ledger that `claude/asia-cn-official-sge` adds to asia_parser (SAFE, CFETS,
                     PBOC OMO, NBS, customs, SGE). Not on live yet: when a root's history file
                     exists it SUPERSEDES that root's frame (the frame is then only the
                     first-release view of the same rows), so nothing is counted twice.
                     `map_asia_history_record`.
  cn_exchange        `data/free_stack/obs/<roster id>.jsonl` rows that carry the s2.5 names --
                     what `claude/asia-cn-futures-positioning` (free_stack_cnx: SHFE/INE/DCE/CZCE/
                     GFEX/CFFEX ranks, warrants, inventory, curves) writes through
                     `free_stack_hunter.merge_obs`. `map_cn_exchange_record`.
  latent             `data/latent/<dataset>.vintages.jsonl` -- the proprietary latent datasets
                     of `claude/asia-latent-datasets` (macro_state_engine), which already carry
                     every s2.5 name. Asian geographies only. `map_latent_record`.

The last three are in-flight branches. Each mapping expects the s2.5 field names verbatim on the
record (`sensor_id`, `source_id`, `dataset_id`, `entity`, `geography`, `asset_domain`, `metric`,
`value`, `unit`, the seven clocks, the expectation/surprise fields, `licence`,
`commercial_rights`, `provenance_hash`, `raw_pointer`) and maps them one to one; a producer's
own id / revision pointers are KEPT in `attributes` and the contract mints its own, because the
ledger detects revisions itself and two id schemes in one field would make a join lie. An absent
store is reported ABSENT, never an error and never a zero.

THE PIT RULES (s2.7), mechanically:
  knowable_at   the PUBLICATION instant -- the source's own printed stamp, else its release
                calendar (late-biased), else the producer's declared lag -- and NEVER later than
                the instant this desk first held the value (the world demonstrably knew it then).
                Never the fetch time when an earlier publication is known.
  knowable_basis  the contract field saying which of those set knowable_at: `printed_stamp`,
                `calendar`, `declared_lag`, or `bounded_by_receipt` when first sight was the
                earlier instant (or the only one); then knowable_at IS received_at, exactly.
  received_at   when the desk first read the value (the store's first-seen / vintage stamp),
                never the time this adapter ran.
  a revision    knowable no earlier than the instant the desk first saw the revised value; the
                revision's own publication instant is not stored, so it is not invented.
  an absent clock is UNMEASURED (the contract's own rule) and is never filled from a neighbour.

IDEMPOTENT. Re-running appends nothing, and that is the CONTRACT's guarantee, not this adapter's:
`SensorLedger.append` drops any observation id it ever admitted under a key, so a first print
re-sent after its revision stays a duplicate. The `stores_seen` cursor in the report only saves
the cost of re-mapping a store whose bytes did not change.

THE LEDGER'S CLOCK AND ARTIFACT are #208's hourly `sensor_ledger` leg and
`reports/SENSOR_LEDGER.json`: the observations this adapter appends are counted there. This
organ's own report is only the pass census (hooks, stores, refusals).

NO AUTHORITY. Every observation carries the contract's constant authority NONE. Nothing here
sizes, routes capital or mints a cell; the hypothesis doors stay where they are.

    python desks/mt5/research/asia_sensor_adapter.py --once [--budget-s 60]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import sensor_contract as sc  # noqa: E402

UNMEASURED = sc.UNMEASURED
SENSOR_CLASS = "asia_structured"
REPORT_NAME = "ASIA_SENSOR_ADAPTER.json"
#: This organ's own artifact: the pass census (what was mapped, appended, refused, deferred),
#: the hook points and their state, and the contract gaps. The OBSERVATIONS themselves go to
#: the sensor ledger (`sensor_contract.default_root()`), which this organ does not own.
REPORT = DESK / "reports" / REPORT_NAME

#: Asian geographies, as the stores spell them (alt_proxies regions and registry countries,
#: upper-cased). East, South, South-East and Central Asia; the Gulf rows of `asia_sources.json`
#: (ae / sa / qa) are West Asia and ride their own plane, so they are left out on purpose.
ASIA: frozenset[str] = frozenset({
    "ASIA", "CN", "HK", "MO", "TW", "JP", "KR", "IN", "SG", "MY", "ID", "TH", "VN", "PH",
    "KZ", "BD", "PK", "LK"})

#: Columns `pit_stamp.stamp_frame` adds to a frame: clocks and provenance, never metrics.
PIT_COLUMNS: frozenset[str] = frozenset({
    "event_time", "available_time", "ingested_time", "published_time", "retrieval_time",
    "revision_time", "source_id", "vintage_id"})
#: Bounds per frame and pass. A generic table wider or longer than this is a dump, not a release;
#: the bound and what it cut are published in the report, never applied silently.
MAX_COLS_PER_FRAME = 40
MAX_ROWS_PER_FRAME = 5_000
#: Lines read to decide whether a free-stack store carries the s2.5 names at all.
SNIFF_LINES = 50

#: What the contract does not give this adapter, for the World sensor thread (the contract is not
#: forked here). The five gaps first named here (no public index read, replay not idempotent, no
#: clock or artifact for the ledger, no knowable_basis field, shards not gitignored) were closed
#: in the contract itself by #208; none is open.
CONTRACT_GAPS: tuple[str, ...] = ()
#: Where the ledger's observations are published each hour (#208's `sensor_ledger` leg).
LEDGER_DIGEST = "desks/mt5/reports/SENSOR_LEDGER.json"

#: The hook points: record type -> (store, mapping function name, the branch that writes it).
HOOKS: dict[str, dict[str, str]] = {
    "alt_proxies": {"store": "data/alt_proxies/obs/<source>.json",
                    "maps": "map_alt_proxies_row", "producer": "live: research/alt_proxies.py"},
    "asia_parser_frames": {"store": "data/lake/series/<id>.parquet|.csv",
                           "maps": "map_asia_frame_row",
                           "producer": "live: research/asia_parser.py"},
    "asia_parser_history": {"store": "data/lake/series/history/<root>.obs.jsonl",
                            "maps": "map_asia_history_record",
                            "producer": "claude/asia-cn-official-sge (asia_parser ledger, "
                                        "cn_official_tables)"},
    "cn_exchange": {"store": "data/free_stack/obs/<roster id>.jsonl (rows with s2.5 names)",
                    "maps": "map_cn_exchange_record",
                    "producer": "claude/asia-cn-futures-positioning (libs/data/free_stack_cnx.py "
                                "via free_stack_hunter.merge_obs)"},
    "latent": {"store": "data/latent/<dataset>.vintages.jsonl",
               "maps": "map_latent_record",
               "producer": "claude/asia-latent-datasets (macro_state_engine latent datasets)"},
}

_CONTRACT = frozenset(f.name for f in fields(sc.SensorObservation))
#: Producer fields that are the contract's to mint, kept in attributes under `producer_<name>`.
_MINTED = ("observation_id", "revision_of", "revision_delta", "revision_n", "authority", "schema",
           "attributes", "sensor_id", "kind", "sensor_class")
_NUMERIC = ("value", "expected_value", "consensus", "seasonal_expected", "raw_surprise",
            "surprise_z", "percentile", "delta", "acceleration", "source_confidence",
            "measurement_uncertainty")


# ============================================================================== small helpers
def _f(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        out = float(v)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _region(v: Any) -> str:
    return str(v or "").strip().upper()


def is_asia(geography: Any) -> bool:
    return _region(geography) in ASIA


def _hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str,
                                     ensure_ascii=False).encode()).hexdigest()


def _sensor(family: str, source_id: str) -> str:
    return f"asia.{family}:{source_id}"


def _bounded(stamp: Any, basis: str, received: Any) -> tuple[str, str]:
    """(knowable_at, knowable_basis): the world stamp with its basis, unless first sight came
    earlier or is the only instant -- then knowable_at is received_at itself and the basis is
    `bounded_by_receipt`. No instant at all is UNMEASURED for both, never a guess."""
    t, rx = sc.parse_time(stamp), sc.parse_time(received)
    if t is not None and (rx is None or t <= rx):
        return sc.iso(stamp), basis
    if rx is not None:
        return sc.iso(received), "bounded_by_receipt"
    return UNMEASURED, UNMEASURED


#: A producer's free-text basis, read into the contract's vocabulary (first match wins).
_BASIS_WORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("bounded_by_receipt", ("receipt", "first_seen", "first sight", "fetch", "retriev")),
    ("calendar", ("calendar", "schedul", "release_rule")),
    ("declared_lag", ("lag",)),
    ("printed_stamp", ("print", "stamp", "publication", "published", "page")),
)


def _basis_of(kw: Mapping[str, Any], producer: Any) -> str:
    """How a producer's knowable_at was set: its own contract word, else its free text read into
    the vocabulary, else the clock knowable_at equals. UNMEASURED when none says (the contract
    then refuses the row as a DEFECT, which is the honest outcome)."""
    word = str(producer or "").strip()
    if word in sc.KNOWABLE_BASES:
        return word
    low = word.lower()
    for basis, keys in _BASIS_WORDS:
        if low and any(k in low for k in keys):
            return basis
    k = sc.parse_time(kw.get("knowable_at"))
    if k is None:
        return UNMEASURED
    for clock, basis in (("publication_time", "printed_stamp"), ("scheduled_time", "calendar"),
                         ("received_at", "bounded_by_receipt")):
        if sc.parse_time(kw.get(clock)) == k:
            return basis
    return UNMEASURED


# ============================================================================== hook: alt_proxies
def map_alt_proxies_row(source: Mapping[str, Any], row: Mapping[str, Any],
                        point: Mapping[str, Any] | None = None, *, store_ref: str = ""
                        ) -> list[sc.SensorObservation]:
    """One alt_proxies vintage-store row -> its first print and (if revised) its latest print.

    `source` carries the Source's id, name, region, language, cadence, licence, terms and
    terms_basis; `point` is the `build_points` entry for the same period (pace / surprise /
    surprise_z, computed on the first print in availability order, so PIT)."""
    sid = str(source["id"])
    series, period = str(row.get("series") or ""), str(row.get("period") or "")
    v0 = _f(row.get("value_first"))
    if not series or not period or v0 is None:
        return []
    published = row.get("published_time")
    basis = str(row.get("published_basis") or "")
    first_seen = row.get("first_seen_at")
    common: dict[str, Any] = {
        "sensor_id": _sensor("alt_proxies", sid), "source_id": sid, "dataset_id": sid,
        "sensor_class": SENSOR_CLASS, "entity": _region(source.get("region")),
        "geography": _region(source.get("region")), "asset_domain": "alt_data",
        "metric": series, "unit": str(source.get("unit") or ""),
        "language": str(source.get("language") or ""), "event_time": period,
        "licence": str(source.get("licence") or UNMEASURED),
        "commercial_rights": (f"terms={source.get('terms') or 'to_confirm'}"
                              + (f"; {source['terms_basis']}" if source.get("terms_basis")
                                 else "")),
        "raw_pointer": f"{store_ref or sid}#{series}|{period}",
    }
    page = basis == "page"
    knowable, kbasis = _bounded(published, "printed_stamp" if page else "calendar", first_seen)
    first_attrs: dict[str, Any] = {
        "vintage": "first", "published_basis": basis or UNMEASURED,
        "cadence": source.get("cadence"), "pit_quality": (point or {}).get("pit_quality")}
    if point:
        first_attrs.update({"pace": point.get("pace"), "pace_surprise": point.get("surprise"),
                            "transform": source.get("transform"),
                            "vintage_id": point.get("vintage_id")})
    out = [sc.make(**common, kind="state", value=v0,
                   publication_time=published if page else None,
                   scheduled_time=None if page else published,
                   knowable_at=knowable, knowable_basis=kbasis, received_at=first_seen,
                   surprise_z=(point or {}).get("surprise_z"),
                   provenance_hash=_hash([sid, series, period, v0, first_seen]),
                   attributes=first_attrs)]
    v1 = _f(row.get("value_last"))
    n_rev = int(_f(row.get("n_revisions")) or 0)
    rev_at = row.get("revision_time")
    if v1 is not None and n_rev > 0 and rev_at and not math.isclose(v1, v0, rel_tol=1e-9,
                                                                    abs_tol=1e-12):
        out.append(sc.make(
            # the revision's own publication instant is not stored: first sight bounds it
            **common, kind="state", value=v1, knowable_at=rev_at, received_at=rev_at,
            knowable_basis="bounded_by_receipt",
            provenance_hash=_hash([sid, series, period, v1, rev_at]),
            attributes={"vintage": "revision", "n_revisions_in_store": n_rev}))
    return out


# ============================================================================== hook: frames
def map_asia_frame_row(source: Mapping[str, Any], record: Mapping[str, Any],
                       value_columns: Iterable[str], label_columns: Iterable[str] = (), *,
                       frame_ref: str = "") -> list[sc.SensorObservation]:
    """One PIT-stamped asia_parser frame row -> one observation per numeric column.

    The frame's `available_time` is the registry's declared publication lag (or the fetch
    instant for a cross-section snapshot); knowable_at is that, bounded by the fetch."""
    sid = str(source["id"])
    event = record.get("event_time")
    received = record.get("ingested_time") or record.get("retrieval_time")
    avail = record.get("available_time")
    if sc.parse_time(event) is None:
        return []
    snapshot = sc.iso(event) == sc.iso(received) or sc.iso(avail) == sc.iso(received)
    # a cross-section snapshot's available_time IS the fetch: only receipt bounds it
    knowable, kbasis = _bounded(None if snapshot else avail, "declared_lag", received)
    labels = [str(record.get(c)).strip() for c in label_columns
              if str(record.get(c, "")).strip() not in ("", "nan", "None", "NaT")]
    entity = (" | ".join(labels)[:120]) or _region(source.get("country"))
    access = str(source.get("access") or "public")
    out: list[sc.SensorObservation] = []
    for col in value_columns:
        v = _f(record.get(col))
        if v is None:
            continue
        out.append(sc.make(
            sensor_id=_sensor("asia_parser", sid), source_id=sid, dataset_id=sid,
            sensor_class=SENSOR_CLASS, kind="state", entity=entity,
            geography=_region(source.get("country")), asset_domain=str(source.get("plane") or ""),
            metric=str(col)[:80], value=v, event_time=event,
            knowable_at=knowable, knowable_basis=kbasis, received_at=received,
            licence=f"asia_sources:{sid} access={access}",
            commercial_rights=UNMEASURED,
            provenance_hash=_hash([sid, record.get("vintage_id"), entity, col, v, sc.iso(event)]),
            raw_pointer=frame_ref or sid,
            attributes={"snapshot": snapshot, "modelled_available_time": sc.iso(avail),
                        "vintage_id": record.get("vintage_id"), "cadence": source.get("cadence"),
                        "url": source.get("url")}))
    return out


# ============================================================================== hook: s2.5 rows
def map_contract_record(record: Mapping[str, Any], *, family: str,
                        default_source: str = "") -> sc.SensorObservation | None:
    """A record that already carries the s2.5 names -> one observation, field for field.

    The contract mints the id and the revision pointers; the producer's are kept in attributes."""
    sid = str(record.get("source_id") or default_source or "")
    metric = str(record.get("metric") or record.get("key") or "")
    value = _f(record.get("value"))
    if not sid or not metric or value is None:
        return None
    kw: dict[str, Any] = {k: record[k] for k in _CONTRACT
                          if k in record and k not in _MINTED and record[k] is not None}
    for k in _NUMERIC:
        if k in kw:
            kw[k] = _f(kw[k])
    attrs: dict[str, Any] = {f"producer_{k}": record[k] for k in _MINTED
                             if k in ("observation_id", "revision_of", "revision_delta",
                                      "sensor_id") and record.get(k) is not None}
    for k in ("vintage", "vintage_id", "revision_number", "time_basis",
              "period", "key", "period_end", "first_seen_utc", "producer_id", "pit_quality",
              "consensus_status", "model"):
        if record.get(k) is not None:
            attrs[k] = record[k]
    if "event_time" not in kw and record.get("period_end"):
        kw["event_time"] = record["period_end"]
    producer_basis = record.get("knowable_basis")
    if producer_basis is not None and producer_basis not in sc.KNOWABLE_BASES:
        attrs["producer_knowable_basis"] = producer_basis
    if not kw.get("knowable_at") and record.get("available_time"):
        kw["knowable_at"] = record["available_time"]
        # a producer's available_time is its own release rule (period end + declared lag)
        producer_basis = producer_basis or "declared_lag"
    if not kw.get("received_at") and record.get("first_seen_utc"):
        kw["received_at"] = record["first_seen_utc"]
    kw["knowable_basis"] = _basis_of(kw, producer_basis)
    kw.update({"sensor_id": _sensor(family, sid), "source_id": sid, "metric": metric,
               "value": value, "sensor_class": SENSOR_CLASS,
               "kind": "event" if record.get("kind") == "event" else "state"})
    kw.setdefault("licence", UNMEASURED)
    kw.setdefault("commercial_rights", UNMEASURED)
    if not kw.get("provenance_hash"):
        kw["provenance_hash"] = _hash({k: record.get(k) for k in sorted(record)})
    return sc.make(**kw, attributes=attrs)


def map_cn_exchange_record(record: Mapping[str, Any]) -> sc.SensorObservation | None:
    """free_stack_cnx (claude/asia-cn-futures-positioning): a merge_obs row with the s2.5 names
    (source_id cnx_*, dataset_id <exch>.<daily|rank|warrants|inventory|derived>, entity
    <EXCH>:<product>, geography CN, asset_domain futures, publication_time the declared release
    hour, knowable_at the archive's publication, received_at the box's first sight, licence a
    pointer to the roster row, commercial_rights its terms state)."""
    return map_contract_record(record, family="cn_exchange")


def map_asia_history_record(record: Mapping[str, Any]) -> sc.SensorObservation | None:
    """asia_parser's vintage ledger (claude/asia-cn-official-sge): rows from
    `cn_official_tables.observation` completed by `append_vintage` (knowable_at with
    knowable_basis, received_at, vintage_id, revision_number, licence, provenance_hash = the
    vaulted blob's sha256, raw_pointer = the blob)."""
    return map_contract_record(record, family="asia_parser")


def map_latent_record(record: Mapping[str, Any]) -> sc.SensorObservation | None:
    """macro_state_engine latent vintages (claude/asia-latent-datasets): every s2.5 name, with
    expected_value / raw_surprise / surprise_z / percentile / delta / acceleration and
    measurement_uncertainty of the nowcast. Only Asian geographies are mapped here."""
    if not is_asia(record.get("geography")):
        return None
    return map_contract_record(record, family="latent")


# ============================================================================== store readers
def _jsonl(path: Path) -> Iterator[dict[str, Any]]:
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    yield row
    except OSError:
        return


def _alt_proxy_sources() -> list[Any]:
    from research import alt_proxies as A
    # alt_proxies reads no stored history of a source whose terms are not confirmed; neither
    # does this adapter (the store may predate the terms decision)
    return [s for s in A.SOURCES if is_asia(s.region) and s.terms == "confirmed"]


def collect_alt_proxies(desk: Path) -> Iterator[tuple[str, Path, Callable[[], list[Any]]]]:
    from research import alt_proxies as A
    for src in _alt_proxy_sources():
        path = desk / "data" / "alt_proxies" / "obs" / f"{src.id}.json"

        def load(src: Any = src, path: Path = path) -> list[sc.SensorObservation]:
            store = A._read_json(path, {})
            if not isinstance(store, dict) or not store:
                return []
            pts = A.build_points(src, store)
            by = {(name, p["d"]): p for name, ps in pts.items() for p in ps}
            meta = {"id": src.id, "name": src.name, "region": src.region,
                    "language": src.language, "cadence": src.cadence, "licence": src.licence,
                    "terms": src.terms, "transform": src.transform,
                    "terms_basis": A.TERMS.get(src.id, ("", ""))[1]}
            ref = str(path.relative_to(desk.parent.parent)) if path.is_relative_to(
                desk.parent.parent) else str(path)
            out: list[sc.SensorObservation] = []
            for row in store.values():
                if isinstance(row, dict):
                    out.extend(map_alt_proxies_row(
                        meta, row, by.get((str(row.get("series")), str(row.get("period")))),
                        store_ref=ref))
            return out

        yield f"alt_proxies:{src.id}", path, load


def _registry(desk: Path) -> dict[str, dict[str, Any]]:
    try:
        doc = json.loads((desk / "data" / "asia_sources.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(r["id"]): r for r in (doc.get("sources") or [])
            if isinstance(r, dict) and r.get("id") and is_asia(r.get("country"))}


def _frame_rows(path: Path) -> tuple[list[dict[str, Any]], list[str], list[str], dict[str, Any]]:
    import pandas as pd
    df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    note: dict[str, Any] = {"rows": len(df)}
    if "event_time" not in df.columns or "available_time" not in df.columns:
        return [], [], [], {**note, "skipped": "frame is not PIT-stamped"}
    df.columns = [str(c) for c in df.columns]
    rest = [c for c in df.columns if c not in PIT_COLUMNS]
    numeric = [c for c in rest if pd.to_numeric(df[c], errors="coerce").notna().mean() >= 0.6]
    labels = [c for c in rest if c not in numeric][:2]
    if len(numeric) > MAX_COLS_PER_FRAME:
        note["columns_cut"] = len(numeric) - MAX_COLS_PER_FRAME
        numeric = numeric[:MAX_COLS_PER_FRAME]
    if len(df) > MAX_ROWS_PER_FRAME:
        note["rows_cut"] = len(df) - MAX_ROWS_PER_FRAME
        df = df.sort_values("event_time").tail(MAX_ROWS_PER_FRAME)
    for c in numeric:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ("event_time", "available_time"):
        df[c] = pd.to_datetime(df[c], utc=True, errors="coerce").map(
            lambda t: None if pd.isna(t) else t.isoformat())
    recs = df[[*numeric, *labels, *(c for c in PIT_COLUMNS if c in df.columns)]].to_dict("records")
    return recs, numeric, labels, note


def collect_asia_parser(desk: Path) -> Iterator[tuple[str, Path, Callable[[], list[Any]]]]:
    series = desk / "data" / "lake" / "series"
    history = series / "history"
    reg = _registry(desk)
    for sid, row in sorted(reg.items()):
        hist = history / f"{sid}.obs.jsonl"
        if hist.exists():
            def load_h(hist: Path = hist) -> list[sc.SensorObservation]:
                got = [map_asia_history_record(r) for r in _jsonl(hist)]
                return [o for o in got if o is not None]
            yield f"asia_parser_history:{sid}", hist, load_h
            continue
        frame = next((series / f"{sid}{ext}" for ext in (".parquet", ".csv")
                      if (series / f"{sid}{ext}").exists()), None)
        if frame is None:
            continue

        def load_f(frame: Path = frame, row: dict[str, Any] = row) -> list[sc.SensorObservation]:
            recs, numeric, labels, _note = _frame_rows(frame)
            ref = f"desks/mt5/data/lake/series/{frame.name}"
            out: list[sc.SensorObservation] = []
            for r in recs:
                out.extend(map_asia_frame_row(row, r, numeric, labels, frame_ref=ref))
            return out
        yield f"asia_parser_frames:{sid}", frame, load_f


def _carries_contract(path: Path) -> bool:
    for i, row in enumerate(_jsonl(path)):
        if "knowable_at" in row and ("metric" in row or "key" in row):
            return True
        if i >= SNIFF_LINES:
            break
    return False


def collect_contract_stores(desk: Path) -> Iterator[tuple[str, Path, Callable[[], list[Any]]]]:
    obs = desk / "data" / "free_stack" / "obs"
    for path in sorted(obs.glob("*.jsonl")) if obs.is_dir() else []:
        def load_c(path: Path = path) -> list[sc.SensorObservation]:
            if not _carries_contract(path):
                return []
            got = [map_cn_exchange_record(r) for r in _jsonl(path) if is_asia(r.get("geography"))]
            return [o for o in got if o is not None]
        yield f"cn_exchange:{path.stem}", path, load_c
    latent = desk / "data" / "latent"
    for path in sorted(latent.glob("*.vintages.jsonl")) if latent.is_dir() else []:
        def load_l(path: Path = path) -> list[sc.SensorObservation]:
            got = [map_latent_record(r) for r in _jsonl(path)]
            return [o for o in got if o is not None]
        yield f"latent:{path.name.split('.')[0]}", path, load_l


COLLECTORS: tuple[Callable[[Path], Iterator[tuple[str, Path, Callable[[], list[Any]]]]], ...] = (
    collect_alt_proxies, collect_asia_parser, collect_contract_stores)


# ============================================================================== the pass
def _sig(path: Path) -> str:
    try:
        st = path.stat()
    except OSError:
        return ""
    return f"{st.st_mtime_ns}:{st.st_size}"


def run(desk: Path = DESK, *, ledger_root: Path | None = None, budget_s: float = 60.0,
        report: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    """One pass: every Asia store whose bytes changed since the last pass, mapped and appended."""
    t0 = time.monotonic()
    now = now or datetime.now(UTC)
    ledger = sc.SensorLedger(ledger_root)
    report = report or (REPORT if desk == DESK else desk / "reports" / REPORT_NAME)
    try:
        prev = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        prev = {}
    seen: dict[str, str] = dict(prev.get("stores_seen") or {}) if isinstance(prev, dict) else {}
    if not ledger.latest_index():
        seen = {}          # an empty or reset ledger is re-filled, whatever the cursor says
    stores: dict[str, Any] = {}
    totals: Counter[str] = Counter()
    deferred: list[str] = []
    for collect in COLLECTORS:
        try:
            items = list(collect(desk))
        except Exception as exc:                   # one broken organ never stops the others
            stores[collect.__name__] = {"status": "ERROR", "why": f"{type(exc).__name__}: "
                                                                  f"{str(exc)[:120]}"}
            continue
        for name, path, load in items:
            sig = _sig(path)
            if seen.get(name) == sig:
                stores[name] = {"status": "UNCHANGED"}
                continue
            if time.monotonic() - t0 > budget_s:
                deferred.append(name)
                continue
            try:
                obs = load()
            except Exception as exc:
                stores[name] = {"status": "ERROR",
                                "why": f"{type(exc).__name__}: {str(exc)[:120]}"}
                continue
            # the contract owns idempotency: a re-sent print (first or revised) is a duplicate
            res: dict[str, Any] = ledger.append(obs, now=now) if obs else {
                "appended": 0, "duplicates": 0, "revisions": 0, "refused": 0, "refusals": []}
            for k in ("appended", "duplicates", "revisions", "refused"):
                totals[k] += int(res.get(k) or 0)
            totals["mapped"] += len(obs)
            stores[name] = {"status": "MAPPED", "mapped": len(obs),
                            **{k: res.get(k) for k in ("appended", "duplicates", "revisions",
                                                       "refused")},
                            "refusals": (res.get("refusals") or [])[:3]}
            seen[name] = sig
    families = Counter(n.split(":", 1)[0] for n in stores)
    hooks = {fam: {**spec, "stores_seen": int(families.get(fam, 0)),
                   "status": "READING" if families.get(fam) else "ABSENT (no store on this host)"}
             for fam, spec in HOOKS.items()}
    doc = {
        "generated_at": now.isoformat(timespec="seconds"),
        "rule": ("pure mapping of stored Asia observations into the universal sensor ledger; "
                 "knowable_at = publication (bounded by first sight) with its knowable_basis, "
                 "received_at = first sight, revisions append, authority NONE"),
        "ledger_root": str(ledger.root),
        "ledger_digest": LEDGER_DIGEST,
        "totals": dict(totals) if totals else {"mapped": UNMEASURED},
        "deferred_over_budget": deferred,
        "hooks": hooks,
        "contract_gaps": list(CONTRACT_GAPS),
        "stores": stores,
        "stores_seen": seen,
        "wall_s": round(time.monotonic() - t0, 2),
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    tmp = report.with_suffix(f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, default=str, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, report)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=60.0)
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s)
    t = doc["totals"]
    print(f"asia_sensor_adapter: mapped {t.get('mapped')} appended {t.get('appended', 0)} "
          f"revisions {t.get('revisions', 0)} refused {t.get('refused', 0)} "
          f"duplicates {t.get('duplicates', 0)}; deferred {len(doc['deferred_over_budget'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
