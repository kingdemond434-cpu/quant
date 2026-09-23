"""W9 -- THE WRITER THE HASH-LINKED CHAIN NEVER HAD: harvest the eight-link spine every hour.

`libs/research/artifact_chain.py` landed with 33 tests and `scripts/verify_artifact_chain.py`
verifies it every core hour. Measured 2026-09-22 the chain file did not exist: n=0, ok=True.
A verifier that has never been handed a record is a green light on an empty room, and W9 asks for
SOURCE -> CLAIM -> HYPOTHESIS -> CODE -> DATA HASH -> CONFIG HASH -> RESULTS -> REVIEW frozen and
hash-linked, not for a library that could do it.

THE CONSTRAINT THAT SHAPES THIS ORGAN. `scripts/external_gauntlet.py` and `research/promoter.py`
are SEALED: the desk does not edit the two organs that judge and promote, so the writers cannot be
calls inside them. This is therefore a HARVESTER. Every pass it reads what those organs already
left on disk and APPENDS the records they imply:

    SOURCE      registry `sources`, `data/source_registry.json`, the docket row's own ground,
                and the newest documents under data/intelligence/** (both roots), by file sha256
    CLAIM       the verbatim text a lead carried: the registry discovery's mechanism / exact
                rule, else the docket row's mechanism. A row that named no text is recorded with
                `verbatim: false` -- a claim nobody wrote down is a measured absence, never prose
                this organ invented
    HYPOTHESIS  the registry candidate (libs/moat/registry at ROOT data/alpha_registry.sqlite)
                joined to the cell by `frontier_identity.cell_id`, else the docket row
    CODE        `executables.resolve_family` -> the family function -> the sleeve registry's own
                `code_hash` and `behaviour_hash`; both, never one
    DATA        sha256 of the bars parquet the run read, hashed lazily and cached by (size,
                mtime) in a side file so a pass never re-hashes the universe
    CONFIG      the run's parameter dict, canonically serialised by the library
    RESULTS     `gate_verdict_ledger.jsonl` rows through the library's own `from_gate_verdict`,
                and the ten-gate certificates in `reports/UNIVERSAL_SURVIVORS.json`
    REVIEW      `reports/BLIND_REVIEW.json` / `data/blind_review_ledger.jsonl` rows through the
                library's `from_blind_review`

IDEMPOTENT BY PAYLOAD HASH, NOT BY CURSOR. A cursor forgets what it already wrote the moment a
file is rewritten behind it. Every record this organ intends to append is hashed with the
library's own `digest()` first; a payload already in the chain is REUSED as the predecessor of
the next link and never appended twice. The identities below the hypothesis all carry the cell,
so two cells that read the same parquet get two data records and neither is grafted onto the
other's lineage.

APPEND-ONLY, AND A BREAK IS REPORTED, NEVER REPAIRED. The pass verifies before it writes. If
`verify()` names a first_break the organ appends NOTHING and publishes the break: a harvester
that "fixed" a broken hash-linked chain would be the one actor able to forge it silently.

    python desks/mt5/research/research_artifacts.py [--once] [--budget-s 300] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import artifact_chain as ac  # noqa: E402

CHAIN = ac.CHAIN
REPORT = DESK / "reports" / "RESEARCH_ARTIFACTS.json"
DIGESTS = DESK / "data" / "research_artifact_digests.json"
GATE_LEDGER = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
BLIND_REPORT = DESK / "reports" / "BLIND_REVIEW.json"
BLIND_LEDGER = DESK / "data" / "blind_review_ledger.jsonl"
SOURCE_REGISTRY = DESK / "data" / "source_registry.json"
UNIVERSE = DESK / "data" / "universe"
INTEL_DIRS: tuple[Path, ...] = (ROOT / "data" / "intelligence", DESK / "data" / "intelligence")

BUDGET_S = 300.0
MAX_SPINES = 40
MAX_LEADS = 40
#: The floor under the memory-derived record cap. A pass that could append nothing would leave
#: the chain empty and call it healthy, which is the exact failure W9 names.
MIN_RECORDS = 200
MAX_RECORDS_CEIL = 5000
BYTES_PER_RECORD = 2048
RULE = ("every record the sealed gauntlet and promoter already implied, appended hash-linked and "
        "append-only, deduplicated by payload hash; a broken link is reported, never repaired")

_UNMEASURED = "UNMEASURED"


# ------------------------------------------------------------------------------- small utils

def _now() -> datetime:
    return datetime.now(tz=UTC)


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _dict(value: Any) -> dict[str, Any]:
    """`value` when it is a mapping, else an empty one. A row that is not a dict is not a row."""
    return {str(k): v for k, v in value.items()} if isinstance(value, dict) else {}


def _rows_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _probe(path: Path, n: int | None = None, why_absent: str = "") -> dict[str, Any]:
    """Absence is a verdict (L1.28a): every input gets a row whether or not it was there."""
    if path.exists():
        return {"status": "present", "path": str(path), "n": n, "why": None}
    return {"status": "absent", "path": str(path), "n": 0,
            "why": why_absent or f"{path.name} has never been written on this tree"}


def _available_mb() -> tuple[float | None, str]:
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
    except ImportError:
        return None, "psutil absent; the record cap falls back to its floor"
    try:
        return float(psutil.virtual_memory().available) / 1e6, "psutil.virtual_memory().available"
    except Exception as exc:                                  # pragma: no cover - platform only
        return None, f"psutil raised {type(exc).__name__}: {exc}; the cap falls back to its floor"


def max_records_for(available_mb: float | None) -> int:
    """Derived from the memory MEASURED on this box, never from a machine size in a document.

    A quarter of what is free at `BYTES_PER_RECORD` per record, floored at `MIN_RECORDS` so an
    unreadable counter shrinks nothing, and ceilinged because the real bound on a pass is wall
    time: `append` re-reads the chain to resolve each predecessor.
    """
    if available_mb is None:
        return MIN_RECORDS
    derived = int((available_mb * 1e6 * 0.25) / BYTES_PER_RECORD)
    return max(MIN_RECORDS, min(MAX_RECORDS_CEIL, derived))


# ------------------------------------------------------------------------------- digest cache

def _load_digests(path: Path | None = None) -> dict[str, dict[str, Any]]:
    doc = _json(path or DIGESTS)
    files = doc.get("files") if isinstance(doc, dict) else None
    return {str(k): v for k, v in files.items() if isinstance(v, dict)} if isinstance(files, dict) \
        else {}


def _digest_for(path: Path, cache: dict[str, dict[str, Any]]) -> str | None:
    """sha256 of a file's bytes, hashed once per (size, mtime). None when it cannot be read --
    never an empty-file hash, which would make every unreadable parquet look identical."""
    key = str(path)
    try:
        st = path.stat()
    except OSError:
        return None
    hit = cache.get(key)
    if isinstance(hit, dict) and hit.get("size") == st.st_size and hit.get("mtime_ns") == \
            st.st_mtime_ns and isinstance(hit.get("sha256"), str):
        return str(hit["sha256"])
    sha: str | None = ac.sha256_file(path)
    if sha is not None:
        cache[key] = {"sha256": sha, "size": st.st_size, "mtime_ns": st.st_mtime_ns,
                      "at": _now().isoformat(timespec="seconds")}
    return sha


# ------------------------------------------------------------------------------- chain index

def _chain_index(path: Path) -> dict[str, Any]:
    """One read of the chain: what payloads it already holds, and the anchors a new link needs."""
    recs = ac.read_all(path)
    by_payload: dict[str, tuple[str, str]] = {}
    by_kind: dict[str, int] = {}
    cell_anchor: dict[str, dict[str, str]] = {}
    output_hashes: set[str] = set()
    reviews: set[tuple[str, str]] = set()
    for rec in recs:
        by_payload[rec.payload_hash] = (rec.artifact_id, rec.kind)
        by_kind[rec.kind] = by_kind.get(rec.kind, 0) + 1
        cell = rec.payload.get("cell") or rec.payload.get("cell_id")
        if isinstance(cell, str) and cell:
            cell_anchor.setdefault(cell, {})[rec.kind] = rec.artifact_id
        if rec.kind == "result":
            oh = rec.payload.get("output_hash")
            if isinstance(oh, str):
                output_hashes.add(oh)
        if rec.kind == "review":
            reviews.add((str(rec.payload.get("cell") or ""), str(rec.payload.get("at") or "")))
    return {"n": len(recs), "by_payload": by_payload, "by_kind": by_kind,
            "cell_anchor": cell_anchor, "output_hashes": output_hashes, "reviews": reviews}


# ------------------------------------------------------------------------------- the appender

class _Appender:
    """The only writer in this file, and it is the library's `append` with a dedup in front."""

    def __init__(self, path: Path, index: dict[str, Any], *, apply: bool, max_records: int,
                 deadline: float) -> None:
        self.path = path
        self.by_payload: dict[str, tuple[str, str]] = dict(index["by_payload"])
        self.apply = apply
        self.max_records = int(max_records)
        self.deadline = deadline
        self.appended: dict[str, int] = dict.fromkeys(ac.KINDS, 0)
        self.reused: dict[str, int] = dict.fromkeys(ac.KINDS, 0)
        self.n = 0
        self.capped: str | None = None
        self.errors: list[dict[str, Any]] = []

    def room(self, want: int = 1) -> bool:
        if self.n + want > self.max_records:
            self.capped = self.capped or "max_records"
            return False
        if time.monotonic() >= self.deadline:
            self.capped = self.capped or "budget_s"
            return False
        return True

    def seen(self, kind: str, payload: dict[str, Any]) -> str | None:
        hit = self.by_payload.get(ac.digest(payload))
        return hit[0] if hit is not None and hit[1] == kind else None

    def add(self, kind: str, payload: dict[str, Any], prev: str | None) -> str | None:
        """The artifact id for this payload: the existing one when the chain already holds it."""
        payload_hash = ac.digest(payload)
        hit = self.by_payload.get(payload_hash)
        if hit is not None and hit[1] == kind:
            self.reused[kind] += 1
            return hit[0]
        if not self.room():
            return None
        if not self.apply:
            aid = f"dry:{kind}:{payload_hash[:16]}"
        else:
            try:
                aid = ac.append(kind, payload, prev=prev, path=self.path).artifact_id
            except ac.ChainError as exc:
                self.errors.append({"kind": kind, "why": f"{type(exc).__name__}: {exc}"})
                return None
        self.by_payload[payload_hash] = (aid, kind)
        self.appended[kind] += 1
        self.n += 1
        return aid

    def count_adapter(self, kinds: tuple[str, ...]) -> None:
        """The library's adapters append for themselves; this books what they wrote."""
        for k in kinds:
            self.appended[k] += 1
            self.n += 1


# ------------------------------------------------------------------------------- inputs

def _cell_id(symbol: str, family: str, params: dict[str, Any]) -> str | None:
    try:
        return str(ac.cell_id_for(symbol, family, params))
    except Exception:                                        # pragma: no cover - import environ
        return None


def _docket_index(path: Path | None = None, *, limit_mb: float = 64.0) -> tuple[
        dict[str, dict[str, Any]], dict[str, Any]]:
    """`cell_id -> the docket row the gauntlet judged`: params, ground, url, mechanism.

    Guarded by size: a docket larger than the pass can hold is UNMEASURED with its size named,
    never an OOM on the box that holds the live terminal.
    """
    p = path or DOCKET
    probe = _probe(p)
    if probe["status"] != "present":
        return {}, probe
    size_mb = p.stat().st_size / 1e6
    if size_mb > limit_mb:
        probe.update({"status": "absent", "why": f"{size_mb:.1f} MB exceeds the {limit_mb:.0f} MB "
                                                 f"this pass may hold in memory"})
        return {}, probe
    rows = _json(p)
    if not isinstance(rows, list):
        probe.update({"status": "absent", "why": "the docket is not a list of rows"})
        return {}, probe
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        sym, fam = str(row.get("symbol") or ""), str(row.get("family") or "")
        params = _dict(row.get("params"))
        cid = _cell_id(sym, fam, params) if sym and fam else None
        if cid and cid not in out:
            out[cid] = {"symbol": sym, "family": fam, "params": params,
                        "source": row.get("source"), "url": row.get("url"),
                        "mechanism": row.get("mechanism") or row.get("mechanism_note"),
                        "producer": row.get("producer"), "first_seen": row.get("first_seen")}
    del rows
    probe["n"] = len(out)
    return out, probe


def _source_registry(path: Path | None = None) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    p = path or SOURCE_REGISTRY
    probe = _probe(p)
    doc = _json(p) if probe["status"] == "present" else None
    sources = doc.get("sources") if isinstance(doc, dict) else None
    out = {str(k): v for k, v in sources.items() if isinstance(v, dict)} \
        if isinstance(sources, dict) else {}
    if probe["status"] == "present" and not out:
        probe.update({"status": "absent", "why": "the registry carries no `sources` map"})
    probe["n"] = len(out)
    return out, probe


def _registry_conn() -> tuple[sqlite3.Connection | None, dict[str, Any]]:
    """The ROOT registry, read-only. An unopenable registry is UNMEASURED, never a crash."""
    try:
        from libs.moat import registry
        path = registry.path()
        if not Path(path).exists():
            return None, {"status": "absent", "path": str(path),
                          "why": "the alpha registry has never been created on this tree", "n": 0}
        return registry.connect(), {"status": "present", "path": str(path), "n": None, "why": None}
    except Exception as exc:
        return None, {"status": "absent", "path": None, "n": 0,
                      "why": f"registry unavailable: {type(exc).__name__}: {exc}"}


def _candidate_index(conn: sqlite3.Connection | None) -> dict[str, dict[str, Any]]:
    """`cell_id -> candidate`, by the desk's own identity so no second spelling is minted."""
    if conn is None:
        return {}
    out: dict[str, dict[str, Any]] = {}
    try:
        cur = conn.execute("SELECT id, family, symbol, params_json, chart, falsifier, "
                           "discovery_id, source_id, status, terminal_gate, asset_class, "
                           "mechanism, content_hash FROM research_candidates")
    except sqlite3.Error:
        return {}
    for row in cur:
        try:
            params = json.loads(row["params_json"] or "{}")
        except (ValueError, TypeError):
            params = {}
        if not isinstance(params, dict):
            params = {}
        cid = _cell_id(str(row["symbol"] or ""), str(row["family"] or ""), params)
        if cid and cid not in out:
            out[cid] = dict(row) | {"params": params}
    return out


def _discovery(conn: sqlite3.Connection | None, discovery_id: str | None) -> dict[str, Any] | None:
    if conn is None or not discovery_id:
        return None
    try:
        row = conn.execute(
            "SELECT discovery_id, source_id, source_type, actor, constraint_text, mechanism, "
            "economic_rationale, exact_rule, falsifier, novelty, state, origin, generator, "
            "content_hash, created_at FROM discoveries WHERE discovery_id = ?",
            (str(discovery_id),)).fetchone()
    except sqlite3.Error:
        return None
    return dict(row) if row is not None else None


def _registry_source(conn: sqlite3.Connection | None,
                     source_id: str | None) -> dict[str, Any] | None:
    if conn is None or not source_id:
        return None
    try:
        row = conn.execute(
            "SELECT source_id, url, kind, language, country, licence_note, first_seen, "
            "last_crawled, status, access_label FROM sources WHERE source_id = ?",
            (str(source_id),)).fetchone()
    except sqlite3.Error:
        return None
    return dict(row) if row is not None else None


def _intel_documents(limit: int, dirs: tuple[Path, ...] | None = None) -> tuple[
        list[Path], dict[str, Any]]:
    """The newest lead documents under data/intelligence/**, both roots, newest first."""
    roots = dirs if dirs is not None else INTEL_DIRS
    found: list[tuple[float, Path]] = []
    present = 0
    for root in roots:
        if not root.exists():
            continue
        present += 1
        for p in root.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in (".json", ".jsonl", ".md", ".txt"):
                continue
            try:
                found.append((p.stat().st_mtime, p))
            except OSError:
                continue
    found.sort(key=lambda t: t[0], reverse=True)
    probe = {"status": "present" if present else "absent", "n": len(found),
             "path": ", ".join(str(r) for r in roots),
             "why": None if present else "no intelligence root exists on this tree"}
    return [p for _, p in found[:max(0, int(limit))]], probe


# ------------------------------------------------------------------------------- payloads

def _source_payload(source_id: str, *, url: str | None, registry_row: dict[str, Any] | None,
                    file_digest: str | None = None, extra: dict[str, Any] | None = None
                    ) -> dict[str, Any]:
    reg = registry_row or {}
    ground = str(url or reg.get("url") or reg.get("ground") or source_id)
    retrieved = reg.get("last_crawled") or reg.get("last_seen") or reg.get("first_seen")
    body: dict[str, Any] = ac.source_payload(
        source_id, ground, str(retrieved) if retrieved else None, source_hash=file_digest,
        kind=reg.get("kind"), language=reg.get("language"),
        region=reg.get("region") or reg.get("country"), licence_note=reg.get("licence_note"),
        **(extra or {}))
    return body


def _claim_payload(text: str | None, *, mechanism: str, actor: str, language: str,
                   extra: dict[str, Any] | None = None) -> dict[str, Any]:
    text_body = str(text or "")
    body: dict[str, Any] = ac.claim_payload(
        text_body, mechanism or _UNMEASURED, actor or _UNMEASURED, language or "und",
        verbatim=bool(text_body.strip()),
        why=None if text_body.strip() else
        "the lead reached the desk with no verbatim text recorded", **(extra or {}))
    return body


def _hypothesis_payload(cell: str, symbol: str, family: str, params: dict[str, Any],
                        *, falsifier: str | None, extra: dict[str, Any] | None = None
                        ) -> dict[str, Any]:
    """The cell, under the identity the JUDGE used. `cell_id` is overridden with the ledger's own
    string when the two disagree -- a chain that minted a second spelling of one cell would be
    the `run_key`/`sleeve_key` defect again with a hash on it."""
    derived = _cell_id(symbol, family, params)
    try:
        from research.universe_policy import lane, may_hypothesise
        lane_name, hunted = lane(symbol), bool(may_hypothesise(symbol))
    except Exception:
        lane_name, hunted = _UNMEASURED, None
    body: dict[str, Any] = ac.hypothesis_payload(
        symbol, family, params, falsifier,
        cell_id=cell, derived_cell_id=derived,
        cell_id_basis="judge" if derived != cell else "frontier_identity",
        lane=lane_name, may_hypothesise=hunted, **(extra or {}))
    return body


def _code_payload(family: str, cell: str) -> dict[str, Any]:
    """The family's two hashes, or the honest admission that no code on this tree answers to the
    name. The keys are present either way: an absent key cannot be told from a forgotten one."""
    try:
        from mt5desk.executables import population_of, resolve_family
        fn = resolve_family(family)
        if fn is not None:
            body: dict[str, Any] = ac.code_payload(
                fn, family, cell=cell, population=population_of(family), status="MEASURED")
            return body
        why = "no code on this tree answers to the family name; the certificate is an orphan"
    except Exception as exc:
        why = f"the family registry is not importable: {type(exc).__name__}: {exc}"
    return {"code_hash": None, "behaviour_hash": None, "family": str(family), "cell": cell,
            "status": _UNMEASURED, "why": why}


def _bars_for(symbol: str, timeframe: str, universe: Path | None = None) -> dict[str, Path]:
    root = universe or UNIVERSE
    exact = root / f"{symbol}_{str(timeframe).upper()}.parquet"
    if exact.exists():
        return {str(timeframe).upper(): exact}
    found = sorted(root.glob(f"{symbol}_*.parquet")) if root.exists() else []
    return {p.stem.split("_")[-1]: p for p in found[:2]}


def _data_payload(symbol: str, timeframe: str, cell: str, cache: dict[str, dict[str, Any]],
                  universe: Path | None = None) -> dict[str, Any]:
    """`artifact_chain.data_payload`'s exact shape, with the digests read through the cache.

    The library hashes on every call, which would re-hash the universe every hour; the keys, the
    derivation and the `vintage_basis` are identical, so the payload of an unchanged file is the
    same bytes and the dedup above sees one record rather than one per pass.
    """
    bars = _bars_for(symbol, timeframe, universe)
    digests: dict[str, str | None] = {}
    vintages: list[str] = []
    for tf, path in bars.items():
        axis = f"{symbol}|{tf}"
        digests[axis] = _digest_for(path, cache)
        fetched: str | None = None
        try:
            fetched = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(
                timespec="seconds")
        except OSError:
            fetched = None
        try:
            from libs.data.pit_stamp import vintage_id_for
            vid = vintage_id_for(axis, fetched, None)
        except Exception:                                    # pragma: no cover - import environ
            vid = None
        if vid:
            vintages.append(vid)
    return {"bars_digest": digests, "digest": ac.digest(digests), "vintage_ids": vintages,
            "vintage_basis": "derived_from_mtime",
            "unreadable": sorted(k for k, v in digests.items() if v is None),
            "cell": cell, "symbol": symbol,
            "status": "MEASURED" if any(digests.values()) else _UNMEASURED,
            "why": None if digests else f"no bars parquet for {symbol} in {UNIVERSE.name}"}


# ------------------------------------------------------------------------------- harvest

def _spine_head(app: _Appender, *, cell: str, symbol: str, family: str, params: dict[str, Any],
                docket: dict[str, Any] | None, candidate: dict[str, Any] | None,
                discovery: dict[str, Any] | None, source_row: dict[str, Any] | None,
                registry_source: dict[str, Any] | None, cache: dict[str, dict[str, Any]],
                timeframe: str) -> tuple[str | None, dict[str, Any]]:
    """source -> claim -> hypothesis -> code -> data, returning the data record to hang a run on.

    A cell whose ground nobody recorded starts its own lineage: the library flags such a
    hypothesis `orphan_lineage`, so "we cannot name where this came from" stays a measured
    property of the chain instead of a silence.
    """
    note: dict[str, Any] = {"cell": cell, "orphan": False}
    source_id = (discovery or {}).get("source_id") or (candidate or {}).get("source_id") \
        or (docket or {}).get("source")
    prev: str | None = None
    if source_id:
        src = _source_payload(str(source_id), url=(docket or {}).get("url"),
                              registry_row=registry_source or source_row,
                              extra={"via": "registry" if registry_source else "docket"})
        prev = app.add("source", src, None)
        text = (discovery or {}).get("mechanism") or (docket or {}).get("mechanism") \
            or (candidate or {}).get("mechanism")
        rule = (discovery or {}).get("exact_rule")
        claim = _claim_payload(
            text, mechanism=str((discovery or {}).get("mechanism") or family),
            actor=str((discovery or {}).get("actor") or source_id),
            language=str((registry_source or source_row or {}).get("language") or "und"),
            extra={"exact_rule": rule, "economic_rationale": (discovery or {}).get(
                "economic_rationale"), "discovery_id": (discovery or {}).get("discovery_id"),
                "source_id": str(source_id)})
        if prev is not None:
            prev = app.add("claim", claim, prev)
    else:
        note["orphan"] = True
        note["why"] = "no ground is recorded for this cell; the hypothesis starts its own lineage"
    note["orphan"] = prev is None
    hyp = _hypothesis_payload(
        cell, symbol, family, params,
        falsifier=(candidate or {}).get("falsifier") or (discovery or {}).get("falsifier"),
        extra={"candidate_id": (candidate or {}).get("id"),
               "discovery_id": (discovery or {}).get("discovery_id"),
               "source_id": str(source_id) if source_id else None,
               "asset_class": (candidate or {}).get("asset_class"),
               "status": (candidate or {}).get("status"), "timeframe": timeframe})
    hid = app.add("hypothesis", hyp, prev)
    if hid is None:
        note["why"] = note.get("why") or "the pass ran out of room before the hypothesis"
        return None, note
    cid = app.add("code", _code_payload(family, cell), hid)
    if cid is None:
        return None, note
    data = _data_payload(symbol, timeframe, cell, cache)
    note["data_status"] = data["status"]
    return app.add("data", data, cid), note


def _harvest_spines(app: _Appender, index: dict[str, Any], inputs: dict[str, Any],
                    cache: dict[str, dict[str, Any]], *, max_spines: int) -> dict[str, Any]:
    """Every gauntlet verdict the chain does not hold yet, newest first, with its whole spine."""
    verdicts = _rows_jsonl(GATE_LEDGER)
    inputs["gate_verdict_ledger"] = _probe(GATE_LEDGER, len(verdicts))
    docket, docket_probe = _docket_index()
    inputs["docket"] = docket_probe
    conn, reg_probe = _registry_conn()
    inputs["alpha_registry"] = reg_probe
    sources, src_probe = _source_registry()
    inputs["source_registry"] = src_probe
    candidates = _candidate_index(conn)
    if conn is not None:
        reg_probe["n"] = len(candidates)
    out: dict[str, Any] = {"considered": 0, "built": 0, "already_recorded": 0, "orphans": 0,
                           "no_data": 0, "refused": []}
    seen: set[str] = set()
    try:
        for row in reversed(verdicts):
            cell = str(row.get("cell") or "")
            if not cell or cell in seen:
                continue
            seen.add(cell)
            if ac.digest(dict(row)) in index["output_hashes"]:
                out["already_recorded"] += 1
                continue
            if out["built"] >= max_spines or not app.room(6):
                break
            out["considered"] += 1
            doc = docket.get(cell)
            cand = candidates.get(cell)
            symbol = str(row.get("sym") or row.get("symbol") or (doc or {}).get("symbol") or "")
            family = str(row.get("family") or (doc or {}).get("family") or "")
            params = dict((cand or {}).get("params") or (doc or {}).get("params") or {})
            if not symbol or not family:
                out["refused"].append({"cell": cell, "why": "the verdict row names no symbol or "
                                                            "family, so no cell can be built"})
                continue
            disc = _discovery(conn, (cand or {}).get("discovery_id"))
            source_id = (disc or {}).get("source_id") or (cand or {}).get("source_id") \
                or (doc or {}).get("source")
            data_id, note = _spine_head(
                app, cell=cell, symbol=symbol, family=family, params=params, docket=doc,
                candidate=cand, discovery=disc,
                source_row=sources.get(str(source_id)) if source_id else None,
                registry_source=_registry_source(conn, source_id), cache=cache,
                timeframe=str((cand or {}).get("chart") or params.get("timeframe") or "H1"))
            if note.get("orphan"):
                out["orphans"] += 1
            if note.get("data_status") == _UNMEASURED:
                out["no_data"] += 1
            if data_id is None:
                out["refused"].append({"cell": cell, "why": note.get("why") or
                                       "the spine could not be completed to its data record"})
                continue
            if app.apply and app.room(2):
                try:
                    ac.from_gate_verdict(row, prev=data_id, path=app.path)
                    app.count_adapter(("config", "result"))
                except ac.ChainError as exc:
                    app.errors.append({"kind": "result", "cell": cell,
                                       "why": f"{type(exc).__name__}: {exc}"})
                    continue
            elif not app.apply:
                app.count_adapter(("config", "result"))
            out["built"] += 1
    finally:
        if conn is not None:
            conn.close()
    out["refused"] = out["refused"][:20]
    return out


def _harvest_certificates(app: _Appender, index: dict[str, Any], inputs: dict[str, Any],
                          cache: dict[str, dict[str, Any]], *, limit: int) -> dict[str, Any]:
    """The ten-gate certificates: a RESULT whose stages are the gates themselves."""
    doc = _dict(_json(SURVIVORS))
    rows = _dict(doc.get("survivors"))
    inputs["certificates"] = _probe(SURVIVORS, len(rows))
    out: dict[str, Any] = {"considered": 0, "built": 0, "already_recorded": 0}
    for key, row in list(rows.items())[:max(0, int(limit))]:
        if not isinstance(row, dict):
            continue
        spec = _dict(row.get("shadow_spec"))
        symbol = str(spec.get("symbol") or row.get("sym") or "")
        family = str(spec.get("family") or "")
        params = _dict(spec.get("params"))
        gates = _dict(row.get("gates"))
        if not symbol or not family:
            continue
        output_hash = ac.digest({"certificate": key, "gates": gates,
                                 "gated_at": row.get("gated_at")})
        if output_hash in index["output_hashes"]:
            out["already_recorded"] += 1
            continue
        out["considered"] += 1
        if out["built"] >= limit or not app.room(7):
            break
        data_id, _note = _spine_head(
            app, cell=str(key), symbol=symbol, family=family, params=params, docket=None,
            candidate=None, discovery=None, source_row=None,
            registry_source={"url": "", "kind": "hunt", "language": "en",
                             "first_seen": row.get("gated_at")},
            cache=cache, timeframe=str(params.get("timeframe") or "H1"))
        if data_id is None:
            continue
        passed = bool(gates) and all(
            bool(g.get("passed")) for g in gates.values() if isinstance(g, dict))
        config = ac.config_payload(
            {"certificate": key, "hunt": row.get("hunt"), "selector": spec.get("selector"),
             "side": spec.get("side"), "condition": spec.get("condition"),
             "gate_policy": _dict(doc).get("gate_policy")}, cell=str(key))
        cfg_id = app.add("config", config, data_id)
        if cfg_id is None:
            continue
        ev = _dict(gates.get("expected_value"))
        result = ac.result_payload(
            gates, passed=passed if gates else None, n=None,
            expectancy=ev.get("ev") if isinstance(ev.get("ev"), int | float)
            and not isinstance(ev.get("ev"), bool) else None,
            t=None, output_hash=output_hash, cell=str(key),
            gates_passed=sum(1 for g in gates.values()
                             if isinstance(g, dict) and g.get("passed")),
            gates_total=len(gates), days=row.get("days"), gated_at=row.get("gated_at"),
            basis="UNIVERSAL_SURVIVORS certificate")
        if app.add("result", result, cfg_id) is not None:
            out["built"] += 1
    return out


def _result_anchor(cell: str, anchors: dict[str, dict[str, str]]) -> tuple[str | None, str]:
    """The result a review is about: its own cell, else the longest recorded cell that prefixes
    it -- the blind reviewer names `external.SYM.family.rr=..._wb=...` for a certificate keyed
    `external.SYM.family`, and a review hung on nothing is not provenance."""
    hit = anchors.get(cell, {}).get("result")
    if hit:
        return hit, "exact"
    best, best_len = None, -1
    for key, kinds in anchors.items():
        if ("result" in kinds and cell.startswith(key) and len(key) > best_len
                and (len(cell) == len(key) or cell[len(key)] in ".@")):
            best, best_len = kinds["result"], len(key)
    if best is not None:
        return best, "prefix"
    stripped = cell[len("external."):] if cell.startswith("external.") else None
    if stripped and stripped in anchors and "result" in anchors[stripped]:
        return anchors[stripped]["result"], "stripped_prefix"
    return None, "none"


def _harvest_reviews(app: _Appender, index: dict[str, Any], inputs: dict[str, Any]
                     ) -> dict[str, Any]:
    """Independent adversarial replication, attached to the result it prosecutes."""
    rows = _rows_jsonl(BLIND_LEDGER)
    inputs["blind_review_ledger"] = _probe(BLIND_LEDGER, len(rows))
    doc = _json(BLIND_REPORT)
    raw = _dict(doc).get("reviewed")
    reviewed = [r for r in raw if isinstance(r, dict)] if isinstance(raw, list) else []
    inputs["blind_review_report"] = _probe(BLIND_REPORT, len(reviewed))
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows + reviewed:
        merged[(str(row.get("cell") or ""), str(row.get("at") or ""))] = row
    out: dict[str, Any] = {"considered": 0, "built": 0, "already_recorded": 0,
                           "unattached": [], "by_anchor_basis": {}}
    # The anchors must include what THIS pass appended, so a review lands on a result minted
    # minutes ago rather than waiting an hour for the next index.
    anchors = _chain_index(app.path)["cell_anchor"] if app.apply else index["cell_anchor"]
    for (cell, at), row in merged.items():
        if not cell:
            continue
        if (cell, at) in index["reviews"]:
            out["already_recorded"] += 1
            continue
        out["considered"] += 1
        anchor, basis = _result_anchor(cell, anchors)
        if anchor is None:
            out["unattached"].append({"cell": cell, "at": at, "why": "no result record for this "
                                      "cell; the review has nothing to prosecute yet"})
            continue
        if not app.room():
            break
        out["by_anchor_basis"][basis] = int(out["by_anchor_basis"].get(basis, 0)) + 1
        if not app.apply:
            app.count_adapter(("review",))
            out["built"] += 1
            continue
        try:
            ac.from_blind_review(dict(row), prev=anchor, path=app.path)
            app.count_adapter(("review",))
            out["built"] += 1
        except ac.ChainError as exc:
            app.errors.append({"kind": "review", "cell": cell,
                               "why": f"{type(exc).__name__}: {exc}"})
    out["unattached"] = out["unattached"][:20]
    return out


def _harvest_leads(app: _Appender, inputs: dict[str, Any], cache: dict[str, dict[str, Any]],
                   *, max_leads: int) -> dict[str, Any]:
    """SOURCE and CLAIM for leads that never became a cell -- the conversion debt, recorded.

    A claim the desk read and never tested is exactly what a provenance chain is for; recording
    only the leads that survived would make the chain a record of successes.
    """
    out: dict[str, Any] = {"discoveries": 0, "documents": 0, "claims": 0, "considered": 0}
    conn, _probe_row = _registry_conn()
    sources, _ = _source_registry()
    try:
        if conn is not None:
            try:
                cur = conn.execute(
                    "SELECT discovery_id, source_id, source_type, actor, mechanism, exact_rule, "
                    "economic_rationale, falsifier, state, created_at FROM discoveries "
                    "ORDER BY created_at DESC LIMIT ?", (max(0, int(max_leads)) * 4,))
                rows = [dict(r) for r in cur]
            except sqlite3.Error:
                rows = []
            for row in rows:
                if out["discoveries"] >= max_leads or not app.room(2):
                    break
                sid = str(row.get("source_id") or "")
                if not sid:
                    continue
                out["considered"] += 1
                src = _source_payload(sid, url=None,
                                      registry_row=_registry_source(conn, sid) or sources.get(sid),
                                      extra={"via": "registry_discovery"})
                if app.seen("source", src) is None and not app.room(2):
                    break
                sid_rec = app.add("source", src, None)
                if sid_rec is None:
                    break
                claim = _claim_payload(
                    row.get("mechanism"), mechanism=str(row.get("mechanism") or _UNMEASURED),
                    actor=str(row.get("actor") or sid),
                    language=str((sources.get(sid) or {}).get("language") or "und"),
                    extra={"exact_rule": row.get("exact_rule"), "state": row.get("state"),
                           "discovery_id": row.get("discovery_id"), "source_id": sid,
                           "economic_rationale": row.get("economic_rationale")})
                if app.add("claim", claim, sid_rec) is not None:
                    out["discoveries"] += 1
                    out["claims"] += 1
        docs, doc_probe = _intel_documents(max_leads)
        inputs["intelligence_documents"] = doc_probe
        for path in docs:
            if out["documents"] >= max_leads or not app.room():
                break
            rel = str(path.relative_to(ROOT)) if str(path).startswith(str(ROOT)) else str(path)
            src = _source_payload(f"intel:{rel.replace(os.sep, '/')}", url=rel,
                                  registry_row={"kind": "document", "first_seen": datetime
                                                .fromtimestamp(path.stat().st_mtime, tz=UTC)
                                                .isoformat(timespec="seconds")},
                                  file_digest=_digest_for(path, cache),
                                  extra={"via": "intelligence_document",
                                         "bytes": path.stat().st_size})
            if app.add("source", src, None) is not None:
                out["documents"] += 1
    finally:
        if conn is not None:
            conn.close()
    return out


# ------------------------------------------------------------------------------- report

def _links_report(index_before: dict[str, Any], app: _Appender, inputs: dict[str, Any],
                  verification: dict[str, Any]) -> dict[str, Any]:
    """Per link kind: how many exist, how many this pass added, which inputs answered."""
    feeds: dict[str, tuple[str, ...]] = {
        "source": ("alpha_registry", "source_registry", "intelligence_documents", "docket"),
        "claim": ("alpha_registry", "docket"),
        "hypothesis": ("alpha_registry", "docket", "gate_verdict_ledger"),
        "code": ("gate_verdict_ledger", "certificates"),
        "data": ("universe_bars",),
        "config": ("gate_verdict_ledger", "certificates"),
        "result": ("gate_verdict_ledger", "certificates"),
        "review": ("blind_review_ledger", "blind_review_report"),
    }
    by_kind_after = verification.get("by_kind") or {}
    out: dict[str, Any] = {}
    for kind in ac.KINDS:
        names = feeds[kind]
        present = [n for n in names if (inputs.get(n) or {}).get("status") == "present"]
        absent = {n: (inputs.get(n) or {}).get("why") or "never probed this pass"
                  for n in names if (inputs.get(n) or {}).get("status") != "present"}
        records = int(by_kind_after.get(kind, index_before["by_kind"].get(kind, 0)))
        out[kind] = {
            "records": records, "appended_this_pass": app.appended[kind],
            "reused_this_pass": app.reused[kind], "inputs_present": len(present),
            "inputs_absent": len(absent), "present": present, "absent": absent,
            "status": "MEASURED" if (records or present) else _UNMEASURED,
            "why": None if (records or present) else
            "every input for this link is absent, so the link is unmeasured, not empty-and-well",
        }
    return out


def build(*, budget_s: float = BUDGET_S, max_spines: int = MAX_SPINES, max_leads: int = MAX_LEADS,
          apply: bool = True, chain: Path | None = None
          ) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    started = time.monotonic()
    deadline = started + max(1.0, float(budget_s))
    path = Path(chain) if chain is not None else CHAIN
    available_mb, memory_basis = _available_mb()
    max_records = max_records_for(available_mb)

    before = ac.verify(path).to_dict()
    index = _chain_index(path)
    inputs: dict[str, Any] = {"universe_bars": _probe(UNIVERSE, None)}
    app = _Appender(path, index, apply=apply, max_records=max_records, deadline=deadline)

    if not before.get("ok"):
        # NEVER REPAIRED. A harvester that rewrote a broken append-only chain would be the only
        # actor on this box able to forge one silently; the break is published instead.
        report = {
            "at": _now().isoformat(timespec="seconds"), "status": "BROKEN",
            "why": f"the chain's first break is line {before.get('first_break')}: "
                   f"{before.get('reason')}; this pass appended nothing and repaired nothing",
            "chain": {"path": str(path), "n_before": before.get("n"), "n_after": before.get("n"),
                      "appended": 0, "verified_before": before, "verified_after": before},
            "links": _links_report(index, app, inputs, before), "inputs": inputs,
            "spines": {}, "certificates": {}, "reviews": {}, "leads": {},
            "budget_s": float(budget_s), "elapsed_s": round(time.monotonic() - started, 3),
            "capped": None, "max_records": max_records, "memory_basis": memory_basis,
            "available_mb": None if available_mb is None else round(available_mb, 1),
            "errors": [], "rule": RULE}
        return report, {}

    cache = _load_digests()
    spines = _harvest_spines(app, index, inputs, cache, max_spines=max_spines)
    certs = _harvest_certificates(app, index, inputs, cache, limit=max_spines)
    reviews = _harvest_reviews(app, index, inputs)
    leads = _harvest_leads(app, inputs, cache, max_leads=max_leads)

    after = ac.verify(path).to_dict() if apply else dict(before)
    if not apply:
        after["by_kind"] = {k: index["by_kind"].get(k, 0) for k in ac.KINDS
                            if index["by_kind"].get(k)}
    n_after = int(after.get("n") or 0)
    present_inputs = [k for k, v in inputs.items() if v.get("status") == "present"]
    if not after.get("ok"):
        status, why = "BROKEN", (f"the chain broke at line {after.get('first_break')}: "
                                 f"{after.get('reason')}")
    elif n_after == 0 and not present_inputs:
        status, why = _UNMEASURED, ("the chain is empty because every input is absent: "
                                    + "; ".join(f"{k}: {v.get('why')}" for k, v in inputs.items()))
    elif n_after == 0:
        status, why = _UNMEASURED, ("the chain is empty although "
                                    f"{len(present_inputs)} input(s) answered ("
                                    f"{', '.join(present_inputs)}); nothing in them implied a "
                                    "record this pass")
    else:
        status, why = "OK", None

    return {
        "at": _now().isoformat(timespec="seconds"), "status": status, "why": why,
        "chain": {"path": str(path), "n_before": int(before.get("n") or 0), "n_after": n_after,
                  "appended": app.n, "lineages": after.get("lineages"),
                  "orphan_lineages": len(after.get("orphan_lineages") or []),
                  "verified_before": before, "verified_after": after},
        "links": _links_report(index, app, inputs, after), "inputs": inputs,
        "spines": spines, "certificates": certs, "reviews": reviews, "leads": leads,
        "budget_s": float(budget_s), "elapsed_s": round(time.monotonic() - started, 3),
        "capped": app.capped, "max_records": max_records, "memory_basis": memory_basis,
        "available_mb": None if available_mb is None else round(available_mb, 1),
        "errors": app.errors[:20], "digest_cache": {"path": str(DIGESTS), "files": len(cache)},
        "rule": RULE,
    }, cache


def _write(report: dict[str, Any], cache: dict[str, dict[str, Any]]) -> None:
    _atomic(REPORT, json.dumps(report, indent=1, default=str))
    _atomic(DIGESTS, json.dumps({"at": report["at"], "files": cache,
                                 "rule": "sha256 per (size, mtime); a pass never re-hashes an "
                                         "unchanged parquet"}, indent=0, default=str))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="harvest the hash-linked research artifact chain")
    ap.add_argument("--once", action="store_true", help="one pass (the only mode; for the cycle)")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--max-spines", type=int, default=MAX_SPINES)
    ap.add_argument("--max-leads", type=int, default=MAX_LEADS)
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and print; append nothing, write no report, no digest cache")
    a = ap.parse_args(argv)

    report, cache = build(budget_s=a.budget_s, max_spines=a.max_spines,
                          max_leads=a.max_leads, apply=not a.dry_run)

    chain = report["chain"]
    print(f"research-artifacts: {report['status']} chain n={chain['n_after']} "
          f"(+{chain['appended']} this pass) lineages={chain.get('lineages')}")
    print("  links     " + "  ".join(
        f"{k}:{v['records']}+{v['appended_this_pass']}" for k, v in report["links"].items()))
    unmeasured = [k for k, v in report["links"].items() if v["status"] == _UNMEASURED]
    print(f"  unmeasured {', '.join(unmeasured) if unmeasured else 'none'}")
    sp, rv = report.get("spines") or {}, report.get("reviews") or {}
    print(f"  spines    built {sp.get('built', 0)} of {sp.get('considered', 0)} considered; "
          f"{sp.get('already_recorded', 0)} already in the chain; {sp.get('orphans', 0)} orphan")
    print(f"  reviews   attached {rv.get('built', 0)}; "
          f"{len(rv.get('unattached') or [])} with no result to prosecute")
    if report.get("why"):
        print(f"  why       {report['why'][:200]}")
    if report.get("capped"):
        print(f"  capped    {report['capped']} (max_records={report['max_records']}, "
              f"budget {report['budget_s']}s)")
    if a.dry_run:
        print("  --dry-run: nothing appended, nothing written")
        print(f"  would have written {REPORT.name} and {DIGESTS.name}")
        return 0
    _write(report, cache)
    print(f"  -> {REPORT}")
    return 2 if report["status"] == "BROKEN" else 0


if __name__ == "__main__":
    raise SystemExit(main())
