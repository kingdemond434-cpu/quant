"""The medallion layers, as a CONTRACT ON A ROW rather than three directory names.

A LAYER IS A PROPERTY OF THE ROW, NOT OF ITS DIRECTORY, and that is a deliberate choice this
desk had to make rather than inherit. The desk's stores are scattered -- bars under
`desks/mt5/data/universe`, discovery rows under `desks/mt5/data/intelligence` AND
`data/intelligence` (the compiler globs both), certificates and reports under `reports/` and
`desks/mt5/reports/`. A physical re-layout into `bronze/ silver/ gold/` would break every reader
in the repository and would still prove NOTHING about provenance: a file's path is a claim its
own contents cannot support, and a row moved by a shell command arrives in `silver/` without ever
having been normalised. Carrying `layer` plus the stamps that layer REQUIRES on the row means the
claim travels with the data, survives being copied, concatenated or re-serialised, and can be
checked by anything holding the row -- including the census, which reads coverage per layer.

WHAT EACH LAYER PROMISES (`LAYER_PROMISE`, and mechanically `LAYER_REQUIRES`):

    BRONZE  exactly what arrived, byte-faithful and never edited. Carries the arrival bytes
            (`raw`, plus `raw_sha256` over those bytes) so the row can be handed back as it came,
            and `ingested_time` + `source` + `source_version` saying who wrote it down and when.
            Bronze makes NO claim about when the event happened -- resolving that is Silver's job,
            and pretending otherwise at ingestion is where fabricated stamps come from.
    SILVER  normalised into the desk's own schema, with `event_time` and `available_time`
            RESOLVED and the normalisation NAMED (`normalisation`), plus `promoted_from` -- the
            payload hash of the Bronze row it came from, so the normalisation is reversible to
            its input.
    GOLD    features, carrying `computed_from`: the payload hashes of the SILVER rows the feature
            was computed from, and `feature` naming what was computed. A gold row whose inputs
            cannot be named is a number with no lineage, which is the thing backtests die of.

`promote` REFUSES rather than guesses. A Bronze row from which no `event_time` can be resolved is
not promoted with `now` in the field: it is refused, counted, and reported with its reason.
Measured 2026-09-09 over the compiler's two intelligence trees: `event_time` is present on 0.0%
of 2,816 rows -- 0 of the 190 that are otherwise fully stamped -- so this refusal is not
hypothetical bookkeeping, it is the majority case, and a `promote` that guessed would have
manufactured 2,816 lookahead-free-looking rows in one pass.

Reading is `read_as_of(rows, decision_time)`, which is `libs.data.pit.usable_at` and
`libs.data.pit.latest_as_of` composed -- imported, never re-spelled, because two spellings of
"could the desk have known this" is exactly one spelling too many.

`ParquetLake` below is unchanged: it is the bar store's physical layout, and it keeps using the
same `Layer` names so a bar frame's directory and a row's `layer` field cannot drift apart.
Hive-partitioned by ``year``/``month`` under ``{base}/{layer}/{asset_class}/{symbol}/{tf}`` for
DuckDB partition pruning. Writes replace matching month partitions (corrections create new
partition contents); dataset-level immutability is enforced via the store's snapshot catalog.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds

from libs.data.instruments import get_spec
from libs.data.pit import (
    EVENT_KEYS,
    STAMP_FIELDS,
    is_stamped,
    latest_as_of,
    payload_hash,
    stamp,
    usable_at,
)
from libs.data.schema import BAR_COLUMNS, TIMESTAMP, empty_bars, validate_bars
from libs.data.timeframe import Timeframe

_PARTITION_COLS = ["year", "month"]


class Layer(StrEnum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"


#: The order promotion may travel. A row may only move to the NEXT layer: bronze -> gold skips
#: the step where event_time is resolved and the normalisation named, so it is refused rather
#: than allowed as a shortcut.
LAYER_ORDER: tuple[Layer, ...] = (Layer.BRONZE, Layer.SILVER, Layer.GOLD)

#: What each layer promises, in the words the docstring uses. Published on the census so the
#: promise and the measurement are read together.
LAYER_PROMISE: dict[Layer, str] = {
    Layer.BRONZE: ("exactly what arrived, byte-faithful, never edited; stamped with "
                   "ingested_time and source"),
    Layer.SILVER: ("normalised to the desk's schema with event_time and available_time resolved "
                   "and the normalisation named"),
    Layer.GOLD: "features, with the SILVER rows they were computed from identified",
}

#: The promise, mechanically. `layer_of` and `missing_for` read ONLY this, so adding a promise
#: means adding a required field here rather than a paragraph nothing checks.
LAYER_REQUIRES: dict[Layer, tuple[str, ...]] = {
    Layer.BRONZE: ("layer", "source", "ingested_time", "source_version", "payload_hash",
                   "raw", "raw_sha256"),
    Layer.SILVER: ("layer", "source", "ingested_time", "source_version", "payload_hash",
                   "event_time", "available_time", "normalisation", "promoted_from"),
    Layer.GOLD: ("layer", "source", "ingested_time", "source_version", "payload_hash",
                 "event_time", "available_time", "feature", "computed_from"),
}

#: Fields the layer contract owns. Excluded from the payload hash for the same reason the stamp
#: is: they describe the row's position in the lake, not its content.
LAYER_FIELDS: tuple[str, ...] = ("layer", "normalisation", "promoted_from", "feature",
                                 "computed_from", "raw_sha256")


def _missing(row: dict[str, Any], layer: Layer) -> list[str]:
    return [k for k in LAYER_REQUIRES[layer]
            if row.get(k) in (None, "", [], {})]


def missing_for(row: dict[str, Any], layer: Layer) -> list[str]:
    """Which of `layer`'s promises this row does not keep. Empty means it keeps them all."""
    if not isinstance(row, dict):
        return list(LAYER_REQUIRES[layer])
    miss = _missing(row, layer)
    if row.get("layer") not in (None, "", layer.value) and "layer" not in miss:
        miss.append(f"layer={row.get('layer')!r} not {layer.value!r}")
    return miss


def layer_of(row: dict[str, Any]) -> Layer | None:
    """The layer this row ACTUALLY keeps the promises of, or None.

    Read from the contract, not from the `layer` label: a row labelled `gold` that cannot name
    what it was computed from is not gold, and saying so is the entire point of putting the layer
    on the row. The highest layer whose promises hold wins, so a gold row is not also reported as
    silver.
    """
    if not isinstance(row, dict):
        return None
    for layer in reversed(LAYER_ORDER):
        if not missing_for(row, layer):
            return layer
    return None


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _arrival_bytes(arrived: Any) -> bytes:
    if isinstance(arrived, bytes):
        return arrived
    if isinstance(arrived, str):
        return arrived.encode("utf-8")
    return json.dumps(arrived, sort_keys=True, default=str).encode("utf-8")


def to_bronze(arrived: Any, source: str, *, source_version: str | None = None,
              now: datetime | None = None, **extra: Any) -> dict[str, Any]:
    """A BRONZE row holding `arrived` byte-for-byte, plus who ingested it and when.

    BYTE-FAITHFUL MEANS RECOVERABLE, not "we did not mean to change it". `bronze_bytes` hands
    back exactly the bytes passed in -- base64 for anything that is not valid UTF-8, so a
    gzipped rollup or a latin-1 scrape survives the round trip through JSON that every store here
    performs. `raw_sha256` is taken over those bytes BEFORE any of this, so a bronze row that was
    edited in place fails `verify_bronze` instead of quietly reading as pristine.

    No `event_time` is set here. Bronze does not know when the event happened; Silver resolves
    that or the row is refused.
    """
    body = _arrival_bytes(arrived)
    try:
        text = body.decode("utf-8")
        enc = "utf-8"
    except UnicodeDecodeError:
        text, enc = _b64(body), "base64"
    row: dict[str, Any] = {**extra, "raw": text, "raw_encoding": enc,
                           "raw_sha256": hashlib.sha256(body).hexdigest(),
                           "layer": Layer.BRONZE.value}
    return stamp(row, source, source_version=source_version, now=now)


def bronze_bytes(row: dict[str, Any]) -> bytes:
    """The exact bytes that arrived. Raises ValueError if the row does not carry them."""
    raw = row.get("raw")
    if not isinstance(raw, str):
        raise ValueError("not a bronze row: no `raw` payload to hand back")
    if row.get("raw_encoding") == "base64":
        return base64.b64decode(raw)
    return raw.encode("utf-8")


def verify_bronze(row: dict[str, Any]) -> bool:
    """Do the stored bytes still hash to what arrived? A bronze row edited in place says False."""
    try:
        return hashlib.sha256(bronze_bytes(row)).hexdigest() == row.get("raw_sha256")
    except (ValueError, TypeError, binascii.Error):
        return False


@dataclass(frozen=True)
class Promotion:
    """What one promotion did, INCLUDING what it turned away.

    `refused` is not an error list to be swallowed; it is the promotion's other half. A promotion
    that reports 40 rows without reporting the 60 it refused is a coverage claim with the
    denominator removed.
    """

    frm: Layer
    to: Layer
    rows: list[dict[str, Any]] = field(default_factory=list)
    refused: list[dict[str, Any]] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        return {"seen": len(self.rows) + len(self.refused),
                "promoted": len(self.rows), "refused": len(self.refused)}

    def report(self) -> dict[str, Any]:
        """The record a producer writes onto its artifact."""
        return {"from": self.frm.value, "to": self.to.value, "counts": self.counts,
                "refusals": self.refused[:20],
                "rule": ("a row that cannot resolve an event_time is REFUSED and counted, never "
                         "promoted with a fabricated stamp")}


def _refusal(row: dict[str, Any], why: str) -> dict[str, Any]:
    return {"why": why,
            "title": str(row.get("title") or row.get("cell") or row.get("id") or "")[:200],
            "payload_hash": row.get("payload_hash"),
            "source": row.get("source")}


def _resolve_event_time(row: dict[str, Any], normalised: dict[str, Any]) -> str | None:
    """The event time, from the normalised row first and the arrived row second. Never `now`.

    `now` is `ingested_time`, and the two are different facts: one says when the thing happened,
    the other when the desk wrote it down. Collapsing them is precisely the fabricated stamp this
    refuses.
    """
    for candidate in (normalised, row):
        for k in EVENT_KEYS:
            v = candidate.get(k)
            if isinstance(v, str) and v.strip():
                return v
    return None


def promote(rows: Iterable[dict[str, Any]], frm: Layer, to: Layer, *,
            source: str | None = None,
            normalise: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None,
            normalisation: str | None = None,
            feature: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None,
            feature_name: str | None = None,
            now: datetime | None = None) -> Promotion:
    """Move rows one layer up, REFUSING every row that would need a guess to get there.

    The refusals, not the promotions, are the reason this exists. A promoter that fills a missing
    `event_time` with the ingestion time produces a lake in which every backtest passes and none
    of them mean anything, because every row claims to have been knowable at the moment it was
    scraped. So:

    * bronze -> silver REFUSES a row whose `event_time` cannot be resolved from the producer's
      own fields (`libs.data.pit.EVENT_KEYS`), and refuses one whose normalisation returns
      nothing. `available_time` is the stamp's -- when the desk could have known it -- and
      `event_time` is the producer's; they are never each other.
    * silver -> gold REFUSES a row whose inputs cannot be named, because a feature that cannot
      say what it was computed from is not auditable.
    * any promotion that skips a layer is refused outright: `LAYER_ORDER` is the only path.

    Every refusal carries its reason and the payload hash of the row it turned away, so the same
    row can be found in the source layer and fixed there rather than re-refused forever.
    """
    out = Promotion(frm=frm, to=to)
    if LAYER_ORDER.index(to) != LAYER_ORDER.index(frm) + 1:
        for r in rows:
            if isinstance(r, dict):
                path = " -> ".join(x.value for x in LAYER_ORDER)
                out.refused.append(_refusal(r, f"{frm.value} -> {to.value} skips a layer; the "
                                               f"only path is {path}"))
        return out
    for r in rows:
        if not isinstance(r, dict):
            continue
        miss = missing_for(r, frm)
        if miss:
            out.refused.append(_refusal(r, f"not {frm.value}: missing {', '.join(miss)}"))
            continue
        src = str(source or r.get("source") or "")
        if not src:
            out.refused.append(_refusal(r, "no source; a row with no producer cannot be promoted"))
            continue
        if to is Layer.SILVER:
            try:
                norm = normalise(r) if normalise else {k: v for k, v in r.items()
                                                       if k not in ("raw", "raw_encoding")}
            except Exception as exc:                        # the door catches everything
                out.refused.append(_refusal(r, f"normalise raised {type(exc).__name__}: {exc}"))
                continue
            if not isinstance(norm, dict) or not norm:
                out.refused.append(_refusal(r, "normalise produced nothing"))
                continue
            ev = _resolve_event_time(r, norm)
            if not ev:
                out.refused.append(_refusal(
                    r, "no resolvable event_time (none of "
                       f"{', '.join(EVENT_KEYS)}); REFUSED rather than stamped with now"))
                continue
            body = {k: v for k, v in norm.items()
                    if k not in STAMP_FIELDS and k not in LAYER_FIELDS}
            body["event_time"] = ev
            body["available_time"] = r.get("available_time") or r.get("ingested_time")
            new = stamp(body, src, source_version=r.get("source_version"), now=now)
            new["layer"] = Layer.SILVER.value
            new["normalisation"] = str(normalisation or getattr(normalise, "__name__", "identity"))
            new["promoted_from"] = r["payload_hash"]
        else:
            try:
                feat = feature(r) if feature else dict(r)
            except Exception as exc:                        # the door catches everything
                out.refused.append(_refusal(r, f"feature raised {type(exc).__name__}: {exc}"))
                continue
            if not isinstance(feat, dict) or not feat:
                out.refused.append(_refusal(r, "feature produced nothing"))
                continue
            body = {k: v for k, v in feat.items()
                    if k not in STAMP_FIELDS and k not in LAYER_FIELDS}
            body["event_time"] = feat.get("event_time") or r.get("event_time")
            body["available_time"] = feat.get("available_time") or r.get("available_time")
            new = stamp(body, src, source_version=r.get("source_version"), now=now)
            new["layer"] = Layer.GOLD.value
            new["feature"] = str(feature_name or getattr(feature, "__name__", "identity"))
            new["computed_from"] = [r["payload_hash"]]
        still = missing_for(new, to)
        if still:
            out.refused.append(_refusal(r, f"promoted row still not {to.value}: "
                                           f"missing {', '.join(still)}"))
            continue
        out.rows.append(new)
    return out


def promote_many(groups: Iterable[Sequence[dict[str, Any]]], frm: Layer, to: Layer,
                 **kw: Any) -> Promotion:
    """`promote` over several groups of SILVER rows folded into one GOLD row per group.

    Only meaningful for silver -> gold: a feature usually reads many rows and emits one, and
    `computed_from` must then name every one of them rather than the last. A group from which no
    row survives is refused as a group, with the reason of its first refusal.
    """
    out = Promotion(frm=frm, to=to)
    for g in groups:
        one = promote(g, frm, to, **kw)
        out.refused.extend(one.refused)
        if not one.rows:
            continue
        merged = dict(one.rows[0])
        merged["computed_from"] = [r["payload_hash"] for r in g
                                   if isinstance(r, dict) and r.get("payload_hash")]
        merged["payload_hash"] = payload_hash(merged)
        out.rows.append(merged)
    return out


def read_as_of(rows: Iterable[dict[str, Any]], decision_time: datetime, *,
               key_fields: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
    """Only the rows the desk could have known at `decision_time`, at the vintage of that moment.

    Two refusals, both `libs.data.pit`'s and neither re-spelled here:

    * `usable_at` hides a row whose `available_time` is after `decision_time` -- and hides an
      UNSTAMPED row at every time, because absence is not permission.
    * `latest_as_of`, when `key_fields` names the identity of a measurement, returns per key the
      revision that was CURRENT THEN rather than the newest that exists now. A backtest dated
      before a restatement therefore reads the figure it would actually have traded on.

    With no `key_fields` this is the availability filter alone, in input order.
    """
    if key_fields:
        return latest_as_of(rows, key_fields, decision_time)
    return [r for r in rows if isinstance(r, dict) and usable_at(r, decision_time)]


def layer_census(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Coverage PER LAYER, with UNMEASURED where a layer holds nothing.

    A blended stamped fraction hides which half of the lake is missing: a desk can be perfect at
    bronze and empty at silver and read as "half stamped". A layer holding no rows is UNMEASURED
    -- not a pass and not a zero (L1.28a) -- because nothing was counted, so nothing can be
    compared.
    """
    per: dict[str, dict[str, Any]] = {}
    for layer in LAYER_ORDER:
        per[layer.value] = {"rows": 0, "keeps_promise": 0, "stamped": 0, "revised": 0,
                            "promise": LAYER_PROMISE[layer]}
    unlayered: dict[str, Any] = {
        "rows": 0, "stamped": 0, "revised": 0,
        "_": ("rows carrying no `layer` at all -- the population the lake has not "
              "reached yet, counted rather than averaged away")}
    for r in rows:
        if not isinstance(r, dict):
            continue
        # THE ROW'S CLAIM AND THE ROW'S TRUTH, counted separately. A row is filed under the layer
        # it CLAIMS (`layer`), because that is what a reader would trust; `keeps_promise` then
        # says how often the claim is good. Filing by the truth instead would make every census
        # read 100% and measure nothing.
        label = str(r.get("layer") or "")
        _lay = layer_of(r)
        bucket: dict[str, Any] | None = per.get(label) or (
            per.get(_lay.value) if _lay else None)
        if bucket is None:
            unlayered["rows"] += 1
            unlayered["stamped"] += int(is_stamped(r))
            unlayered["revised"] += int(bool(r.get("revision_id")))
            continue
        bucket["rows"] += 1
        bucket["stamped"] += int(is_stamped(r))
        bucket["revised"] += int(bool(r.get("revision_id")))
        claimed = Layer(label) if label in per else layer_of(r)
        bucket["keeps_promise"] += int(claimed is not None and not missing_for(r, claimed))
    for name, b in per.items():
        n = b["rows"]
        b["status"] = "UNMEASURED" if not n else "measured"
        b["keeps_promise_frac"] = round(b["keeps_promise"] / n, 4) if n else None
        b["stamped_frac"] = round(b["stamped"] / n, 4) if n else None
        b["_"] = (f"{name} holds no rows: UNMEASURED, which is neither a pass nor a zero"
                  if not n else "")
    return {"per_layer": per, "unlayered": unlayered,
            "rule": ("a layer is a property of the ROW (`layer` + the stamps that layer "
                     "requires), never of a directory")}


class ParquetLake:
    """Read/write bars to the partitioned Parquet lake."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)

    def path(self, layer: Layer, symbol: str, timeframe: Timeframe) -> Path:
        spec = get_spec(symbol)
        return self.base_dir / layer.value / spec.asset_class.value / symbol / timeframe.value

    def write_bars(
        self, layer: Layer, symbol: str, timeframe: Timeframe, df: pd.DataFrame
    ) -> Path:
        """Write a bar frame to the lake, partitioned by year/month. Returns its path."""
        validate_bars(df)
        path = self.path(layer, symbol, timeframe)
        if df.empty:
            path.mkdir(parents=True, exist_ok=True)
            return path
        out = df.copy()
        out["year"] = out[TIMESTAMP].dt.year.astype("int32")
        out["month"] = out[TIMESTAMP].dt.month.astype("int32")
        table = pa.Table.from_pandas(out, preserve_index=False)
        # PYARROW STRADDLES TWO TYPE STORIES and the ignore must survive both (2026-08-05).
        # On the PINNED pyarrow (>=24,<25) these calls are `no-untyped-call` and need the
        # ignore; on 25.x the stubs land and mypy calls the same ignore UNUSED. A checkout
        # whose environment drifted off the pin therefore reports the opposite verdict from
        # CI -- which is how a deleted ignore reached the deploy gate. The ignore stays, and
        # warn_unused_ignores is switched off for this module only (pyproject override) so
        # both worlds pass without either weakening the type check elsewhere.
        ds.write_dataset(  # type: ignore[no-untyped-call]
            table,
            base_dir=str(path),
            format="parquet",
            partitioning=_PARTITION_COLS,
            partitioning_flavor="hive",
            existing_data_behavior="delete_matching",
            basename_template="part-{i}.parquet",
        )
        return path

    def read_bars(
        self,
        layer: Layer,
        symbol: str,
        timeframe: Timeframe,
        *,
        start: pd.Timestamp | None = None,
        end: pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Read bars back from the lake, sorted ascending, in the canonical schema (+ extras)."""
        path = self.path(layer, symbol, timeframe)
        if not path.exists() or not any(path.rglob("*.parquet")):
            return empty_bars()
        # pyarrow version straddle -- see write_dataset above.
        table = ds.dataset(  # type: ignore[no-untyped-call]
            str(path), format="parquet", partitioning="hive"
        ).to_table()
        df = table.to_pandas()
        df = df.drop(columns=[c for c in _PARTITION_COLS if c in df.columns])
        df[TIMESTAMP] = pd.to_datetime(df[TIMESTAMP], utc=True)
        df = df.sort_values(TIMESTAMP).reset_index(drop=True)
        if start is not None:
            df = df[df[TIMESTAMP] >= start]
        if end is not None:
            df = df[df[TIMESTAMP] <= end]
        df = df.reset_index(drop=True)
        ordered = [*BAR_COLUMNS, *[c for c in df.columns if c not in BAR_COLUMNS]]
        return validate_bars(df[ordered], require_sorted=True)
