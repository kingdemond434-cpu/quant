"""CELL CULTURE INDEX -- every cell's culture provenance, backfilled bounded, and the gap list.

    python desks/mt5/research/cell_culture_index.py --once --budget-s 240

WHY A LEG AND NOT A REWRITE. The backlog (`data/hypothesis_graph.jsonl`, 5.7M lines on the
trading box), the docket (`data/hypotheses/external_survivors.json`) and the certificates
(`reports/UNIVERSAL_SURVIVORS.json`) are box-written state: fixing them on origin would be
reverted by the next box push, and rewriting a 5.7M-line log to add four keys is a cost with no
reader. New cells carry the fields at birth (`libs/moat/registry.py`,
`miner_candidate_compiler._candidate`, `pack_cells`, `deep_forest_miner._task`); this organ gives
the OLD ones the same answer, through the same rule (`libs/research/cell_culture.infer`), into a
side index the Tier S orthogonality thread can join by cell id or by certificate.

BOUNDED, NEVER LOADED WHOLE. The graph is streamed line by line from a byte cursor
(`reports/cell_culture_cursor.json`), so a pass that runs out of budget resumes where it stopped
and the aggregates accumulate across passes; the docket is streamed element by element out of its
JSON array; the registry is read by `seq` cursor in bounded chunks. A shrunken or replaced graph
resets the cursor and the index is rebuilt from the top -- the aggregate is never a mix of two
files.

WHAT IT WRITES.

  reports/CELL_CULTURE_INDEX.jsonl  one row per cell id (append-only; the LAST row for an id wins):
      {"id", "store", "fate", "symbol", "family", source_culture, participant_structure,
       failure_mode_hypothesis, crowding_prior, culture_derivation, "certificate"?, "identity"?}
      Written for every certificate and every CERTIFIED graph cell, and for every graph, docket
      or registry cell whose culture came from its SOURCE (not merely the symbol's home) or
      whose participant structure is measured. A cell absent from the index is
      `cell_culture.infer({"symbol": ...})` --
      symbol-home or UNMEASURED -- and the artifact says so rather than writing a million rows
      that carry nothing the symbol does not.
  reports/CELL_CULTURE.json  the summary: counts by culture x participant structure x family,
      the UNMEASURED share per field, certificates by culture, the non-Western share of cells,
      judged cells and survivors, the English-covered family set (the input `crowding_prior: low`
      needs), and GAPS -- MT5 asset class x culture with zero or thin cells -- as the producers'
      to-do list. `deep_forest_miner.schedule` reads `gap_cultures()` and works gap cultures'
      grounds first inside each frontier bucket.

UNMEASURED IS NEVER ZERO (L1.28a). An absent store is reported ABSENT with its path; a share over
an empty denominator is UNMEASURED.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import cell_culture as CC  # noqa: E402

LEG = "cell_culture_index"
GRAPH = DESK / "data" / "hypothesis_graph.jsonl"
DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
CERTIFICATES = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
REGISTRY = ROOT / "data" / "alpha_registry.sqlite"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
REPORTS = DESK / "reports"
INDEX = REPORTS / "CELL_CULTURE_INDEX.jsonl"
SUMMARY = REPORTS / "CELL_CULTURE.json"
CURSOR = REPORTS / "cell_culture_cursor.json"

#: Graph lines between budget checks. A check is a clock read; this keeps it off the hot path.
CHECK_EVERY = 2000
#: Registry rows per chunk, and per pass. Bounded so the first pass on a 356k-row registry does
#: not hold the WAL reader for minutes; the cursor carries the rest.
REGISTRY_CHUNK = 20000
REGISTRY_PER_PASS = 400000
#: Seconds kept back from the budget for the docket, the certificates and the write.
WRITE_RESERVE_S = 45.0
#: A (asset class x culture) cell with fewer cells than this is THIN. A zero is always a gap.
THIN_CELLS = 50
#: Graph fates that mean a judge ruled on the cell.
JUDGED_FATES = frozenset({"FAILED", "CERTIFIED", "SURVIVED", "REJECTED", "KILLED"})
SURVIVOR_FATES = frozenset({"CERTIFIED", "SURVIVED"})

#: MetaTrader's asset classes folded to the buckets the gap list reads in.
CLASS_BUCKET: dict[str, str] = {
    "forex": "fx", "forex exotics": "fx", "indices": "index", "commodities": "metals",
    "energy": "energy", "soft commodity": "softs", "bonds": "bonds", "crypto": "crypto",
    "equities": "equities",
}


# ----------------------------------------------------------------------------------- helpers
def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


HEAD_BYTES = 4096


def _head_sig(path: Path, n: int = HEAD_BYTES) -> str:
    """A fingerprint of the file's first ``n`` bytes: a replaced log is a different log. Only
    bytes already consumed are fingerprinted, so an append never looks like a replacement."""
    try:
        with path.open("rb") as fh:
            return hashlib.sha256(fh.read(max(0, n))).hexdigest()[:16]
    except OSError:
        return ""


_CLASSES: dict[str, str] | None = None


def asset_bucket(symbol: object) -> str:
    """The gap-list bucket of a symbol, from MetaTrader's own registry; `unclassified` else."""
    global _CLASSES
    if _CLASSES is None:
        doc = _read_json(UNIVERSE, {})
        _CLASSES = {str(k).upper(): CLASS_BUCKET.get(str((v or {}).get("asset_class") or "")
                                                     .strip().lower(), "unclassified")
                    for k, v in (doc.items() if isinstance(doc, dict) else [])
                    if isinstance(v, dict)}
    return _CLASSES.get(str(symbol or "").upper(), "unclassified")


def iter_json_array(path: Path, chunk: int = 1 << 20) -> Iterator[Any]:
    """Each element of a top-level JSON array, decoded one at a time from a bounded buffer.

    The docket is a 76 MB array on this container; `json.load` would hold every row and its
    dict overhead at once. This holds about one chunk plus the element being decoded, and it
    compacts the buffer only once a chunk has been consumed (slicing per element is quadratic).
    """
    dec = json.JSONDecoder()
    ws = " \t\r\n,"
    with path.open(encoding="utf-8", errors="replace") as fh:
        buf = fh.read(chunk)
        eof = not buf
        pos = 0
        while pos < len(buf) and buf[pos] in " \t\r\n":
            pos += 1
        if pos >= len(buf) or buf[pos] != "[":
            return
        pos += 1
        while True:
            while True:
                while pos < len(buf) and buf[pos] in ws:
                    pos += 1
                if pos < len(buf) or eof:
                    break
                buf, pos = fh.read(chunk), 0
                eof = not buf
            if pos >= len(buf) or buf[pos] == "]":
                return
            try:
                obj, end = dec.raw_decode(buf, pos)
            except ValueError:
                if eof:
                    return
                more = fh.read(chunk)
                eof = not more
                buf = buf[pos:] + more
                pos = 0
                continue
            yield obj
            pos = end
            if pos > chunk:
                buf, pos = buf[pos:], 0


# --------------------------------------------------------------------------------- aggregates
def _blank_agg() -> dict[str, Any]:
    return {"rows": 0, "cells": 0, "judged": 0, "survivors": 0,
            "unmeasured": dict.fromkeys(CC.FIELDS, 0), "source_derived": 0,
            "by_culture": {}, "by_culture_structure_family": {},
            "by_class_culture": {}, "by_class_culture_structure": {},
            "source_class_culture_structure": {},
            "judged_by_culture": {}, "survivors_by_culture": {}, "by_rule": {}}


def _bump(d: dict[str, int], k: str, n: int = 1) -> None:
    d[k] = int(d.get(k, 0)) + n


class Pass:
    """One pass's mutable state: the cursor document, the index writer and the lineage map."""

    def __init__(self, cursor: dict[str, Any], english: frozenset[str] | None) -> None:
        self.cursor = cursor
        self.english = english
        self.english_seen: set[str] = set(cursor.get("english_families") or [])
        self.lineage: dict[str, dict[str, int]] = cursor.setdefault("lineage", {})
        self.index_rows = 0
        self._fh: Any = None

    def write_index(self, row: dict[str, Any]) -> None:
        if self._fh is None:
            INDEX.parent.mkdir(parents=True, exist_ok=True)
            self._fh = INDEX.open("a", encoding="utf-8")
        self._fh.write(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n")
        self.index_rows += 1

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def culture(self, row: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        return CC.infer_with_language(row, english_families=self.english)

    def account(self, agg: dict[str, Any], row: dict[str, Any], fields: dict[str, Any],
                lang: str | None, *, born: bool, judged: bool, survived: bool) -> None:
        agg["rows"] += 1
        culture = str(fields[CC.SOURCE_CULTURE])
        struct = str(fields[CC.PARTICIPANT_STRUCTURE])
        fam = str(row.get("family") or "?")
        how = fields[CC.DERIVATION_FIELD]
        rule = str(how.get(CC.SOURCE_CULTURE) or CC.UNMEASURED)
        _bump(agg["by_rule"], rule)
        derived = CC.is_source_derived(how)
        if lang == "en" and fam != "?":
            self.english_seen.add(fam)
        if derived and culture not in (CC.UNMEASURED, CC.GLOBAL):
            key = f"{str(row.get('symbol') or '').upper()}|{fam}"
            _bump(self.lineage.setdefault(key, {}), culture)
        if born:
            agg["cells"] += 1
            for f in CC.FIELDS:
                if fields[f] == CC.UNMEASURED:
                    agg["unmeasured"][f] += 1
            if derived:
                agg["source_derived"] += 1
                _bump(agg["source_class_culture_structure"],
                      f"{asset_bucket(row.get('symbol'))}|{culture}|{struct}")
            _bump(agg["by_culture"], culture)
            _bump(agg["by_culture_structure_family"], f"{culture}|{struct}|{fam}")
            bucket = asset_bucket(row.get("symbol"))
            _bump(agg["by_class_culture"], f"{bucket}|{culture}")
            _bump(agg["by_class_culture_structure"], f"{bucket}|{culture}|{struct}")
        if judged:
            agg["judged"] += 1
            _bump(agg["judged_by_culture"], culture)
        if survived:
            agg["survivors"] += 1
            _bump(agg["survivors_by_culture"], culture)


def _index_row(cid: str, store: str, row: dict[str, Any], fields: dict[str, Any],
               **extra: Any) -> dict[str, Any]:
    out = {"id": cid, "store": store, "symbol": row.get("symbol"), "family": row.get("family"),
           **{f: fields[f] for f in CC.FIELDS},
           CC.DERIVATION_FIELD: fields[CC.DERIVATION_FIELD]}
    out.update({k: v for k, v in extra.items() if v not in (None, "")})
    return out


def _informative(fields: dict[str, Any]) -> bool:
    """A row worth an index line: its culture came from the source, or its structure is known."""
    return (CC.is_source_derived(fields[CC.DERIVATION_FIELD])
            or fields[CC.PARTICIPANT_STRUCTURE] != CC.UNMEASURED)


# ------------------------------------------------------------------------------------ stores
def scan_graph(p: Pass, deadline: float, path: Path = GRAPH) -> dict[str, Any]:
    """Stream the backlog from the byte cursor to EOF or the deadline. Additive aggregates."""
    st = p.cursor.setdefault("graph", {"offset": 0, "head": "", "agg": _blank_agg()})
    note: dict[str, Any] = {"path": str(path)}
    try:
        size = path.stat().st_size
    except OSError:
        note["status"] = "ABSENT"
        return note
    prev = int(st.get("offset") or 0)
    head_n = int(st.get("head_n") or 0)
    if st.get("head") and (size < prev or st["head"] != _head_sig(path, head_n)):
        note["reset"] = "the graph was replaced or shrank: aggregates restart from line one"
        st.update({"offset": 0, "agg": _blank_agg()})
    agg = st["agg"]
    offset = int(st.get("offset") or 0)
    lines = 0
    with path.open("rb") as fh:
        fh.seek(offset)
        while True:
            if lines % CHECK_EVERY == 0 and time.monotonic() > deadline:
                note["stopped"] = "budget"
                break
            raw = fh.readline()
            if not raw:
                break
            if not raw.endswith(b"\n"):
                break                          # a partial last line: the writer is mid-append
            offset = fh.tell()
            lines += 1
            try:
                row = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(row, dict):
                continue
            fate = str(row.get("fate") or "").upper()
            fields, lang = p.culture(row)
            born = fate in ("BORN", "")
            judged = fate in JUDGED_FATES
            survived = fate in SURVIVOR_FATES
            p.account(agg, row, fields, lang, born=born, judged=judged, survived=survived)
            if survived or _informative(fields):
                p.write_index(_index_row(str(row.get("id") or ""), "graph", row, fields,
                                         fate=fate or "BORN"))
    st["offset"] = offset
    st["head_n"] = min(offset, HEAD_BYTES)
    st["head"] = _head_sig(path, st["head_n"])
    note.update({"status": "READ", "lines_this_pass": lines, "offset": offset, "size": size,
                 "complete": offset >= size})
    return note


def _digest(fields: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps({f: fields[f] for f in CC.FIELDS},
                                     sort_keys=True).encode()).hexdigest()[:8]


def scan_docket(p: Pass, path: Path = DOCKET, *, lineage: Any = None,
                want: set[str] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """The docket is a snapshot: re-aggregated every pass, indexed only when a cell is new or
    its culture changed (the digest map in the cursor)."""
    agg = _blank_agg()
    note: dict[str, Any] = {"path": str(path)}
    if not path.exists():
        note["status"] = "ABSENT"
        return agg, note
    seen: dict[str, str] = p.cursor.setdefault("docket_digest", {})
    live: set[str] = set()
    for row in iter_json_array(path):
        if not isinstance(row, dict):
            continue
        if lineage is not None and want:
            lineage.want_docket(want, row)
        fields, lang = p.culture(row)
        p.account(agg, row, fields, lang, born=True, judged=False, survived=False)
        cid = str(row.get("genome_id") or row.get("candidate_id") or "")
        if not cid:
            cid = "docket:" + hashlib.sha256(json.dumps(
                [row.get("symbol"), row.get("family"), row.get("params")], sort_keys=True,
                default=str).encode()).hexdigest()[:16]
        live.add(cid)
        dg = _digest(fields)
        if _informative(fields) and seen.get(cid) != dg:
            seen[cid] = dg
            p.write_index(_index_row(cid, "docket", row, fields,
                                     cell_id=frontier_cell_id(row), tier=TIER_BACKLOG,
                                     source=row.get("source"), source_url=row.get("source_url")))
    for gone in set(seen) - live:
        seen.pop(gone, None)
    note.update({"status": "READ", "rows": agg["rows"]})
    return agg, note


def _lineage_culture(p: Pass, symbol: object, family: object) -> tuple[str, int, int] | None:
    counts = p.lineage.get(f"{str(symbol or '').upper()}|{family}") or {}
    if not counts:
        return None
    best, n = max(counts.items(), key=lambda kv: kv[1])
    return best, n, sum(counts.values())


# ------------------------------------------------------------------ tiers (a) and (b): targets
#: THE BACKFILL ORDER (coordinator, 2026-09-30, from the Tier S cross-culture test: 9 of 210
#: survivors had a culture). (a) every certificate, (b) every LIVE and forward-clock cell, (c)
#: the backlog. (a) and (b) are small and are resolved in FULL on every pass, before a single
#: backlog line is read, so the cells that carry returns are never waiting behind 5.7M others.
TIER_SURVIVORS = "a_survivors"
TIER_LIVE_FORWARD = "b_live_forward"
TIER_BACKLOG = "c_backlog"
SLEEVES = DESK / "data" / "sleeves.json"
SHADOW_DIR = DESK / "reports" / "shadow"
FORWARD_STATES = ("shadow_state.json", "qquant_shadow_state.json", "scalp_shadow_state.json",
                  "external_shadow_state.json")
FORWARD_STATUSES = frozenset({"ACTIVE", "PROMOTION CANDIDATE", "PROMOTION_CANDIDATE"})
#: Where the discovery compiler donates: `proposer_common.donate` writes
#: `data/intelligence/discovery_compiler/discoveries_<stamp>.json`.
DC_DONATIONS = DESK / "data" / "intelligence" / "discovery_compiler"
#: Donation files read per pass for the discovery walk, newest first.
DC_MAX_FILES = 400
NO_LINEAGE = "no_lineage"
DESK_ORGAN = "lineage_ends_at_desk_organ"


def strip_hunt(cell_key: object) -> str:
    """`external.EURCHF.discovered.p=...` -> `EURCHF.discovered.p=...` -- the SAME rule the Tier S
    cross-culture test (research/culture_orthogonality.py) applies, so the ids join."""
    k = str(cell_key or "")
    parts = k.split(".", 1)
    if len(parts) == 2 and parts[0] and not parts[0].isupper():
        return parts[1]
    return k


def frontier_cell_id(row: dict[str, Any]) -> str | None:
    """The gauntlet's executable cell id (`research/frontier_identity.cell_id`), or None."""
    sym, fam = row.get("symbol") or row.get("sym"), row.get("family")
    if not sym or not fam:
        return None
    params = row.get("params")
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except ValueError:
            params = {}
    try:
        from research.frontier_identity import cell_id
        return str(cell_id({"sym": str(sym), "family": str(fam),
                            "params": dict(params or {}), "timeframe": row.get("timeframe")}))
    except Exception:
        return None


def _params_key(symbol: object, family: object, params: Any) -> str:
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except ValueError:
            params = {}
    return (f"{str(symbol or '').upper()}|{family}|"
            + json.dumps(params or {}, sort_keys=True, default=str))


def targets(certificates: Path = CERTIFICATES, sleeves: Path = SLEEVES,
            shadow_dir: Path = SHADOW_DIR) -> list[dict[str, Any]]:
    """Tier (a) then tier (b), each as {tier, cell_id, symbol, family, params, row, ...}."""
    out: list[dict[str, Any]] = []
    doc = _read_json(certificates, {})
    surv = doc.get("survivors") if isinstance(doc, dict) else None
    items = surv.items() if isinstance(surv, dict) else []
    by_cell: dict[str, dict[str, Any]] = {}
    for key, cert in items:
        if not isinstance(cert, dict):
            continue
        raw_spec = cert.get("shadow_spec")
        spec: dict[str, Any] = raw_spec if isinstance(raw_spec, dict) else {}
        sym = spec.get("symbol") or cert.get("sym") or cert.get("symbol")
        fam = spec.get("family") or cert.get("family")
        if not sym or not fam:
            continue
        cell = strip_hunt(cert.get("cell") or key)
        t = {"tier": TIER_SURVIVORS, "cell_id": cell, "certificate": str(key),
             "identity": "|".join(str(x or "").strip().lower()
                                  for x in (sym, fam, spec.get("selector"))),
             "symbol": str(sym), "family": str(fam), "params": dict(spec.get("params") or {}),
             "timeframe": spec.get("timeframe"), "row": {**cert, **spec}, "stages": ["certified"]}
        out.append(t)
        by_cell[cell] = t
    sdoc = _read_json(sleeves, {})
    rows = sdoc.get("sleeves") if isinstance(sdoc, dict) else sdoc
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict) or str(r.get("status") or "").upper() != "LIVE":
            continue
        raw_cert = r.get("certificate")
        lcert: dict[str, Any] = raw_cert if isinstance(raw_cert, dict) else {}
        cell = strip_hunt(lcert.get("cell")) if lcert.get("cell") else f"live:{r.get('name')}"
        if cell in by_cell:
            by_cell[cell]["stages"].append("live")
            continue
        t = {"tier": TIER_LIVE_FORWARD, "cell_id": cell, "sleeve": r.get("name"),
             "symbol": str(r.get("symbol") or ""), "family": str(r.get("family") or ""),
             "params": dict(r.get("params") or {}), "timeframe": r.get("timeframe"),
             "row": r, "stages": ["live"]}
        out.append(t)
        by_cell[cell] = t
    for name in FORWARD_STATES:
        st = _read_json(shadow_dir / name, {})
        for key, v in (st.items() if isinstance(st, dict) else []):
            if not isinstance(v, dict) or str(v.get("status") or "").upper() not in (
                    FORWARD_STATUSES):
                continue
            cell = strip_hunt(v.get("cell") or key)
            if cell in by_cell:
                by_cell[cell]["stages"].append("forward")
                continue
            head = str(key).split("#", 1)[0]
            parts = head.split(".")
            sym = v.get("symbol") or (parts[0] if parts else "")
            fam = v.get("family") or (parts[1] if len(parts) >= 3 else "session_window")
            t = {"tier": TIER_LIVE_FORWARD, "cell_id": cell, "forward_key": str(key),
                 "symbol": str(sym), "family": str(fam), "params": dict(v.get("params") or {}),
                 "timeframe": v.get("timeframe"), "row": v, "stages": ["forward"]}
            out.append(t)
            by_cell[cell] = t
    return out


class Lineage:
    """The walk from a cell back to the donation that caused it.

    docket row (exact cell id, then genome id) -> its source / producer / seat / contributing
    sources / URL; a `miner:discovery_compiler` row -> the compiler's donation row with the same
    (symbol, family, params) -> its discovery id -> the registry's `discoveries` row (seat source
    id, generator, stamped culture, payload) -> the originating donation. Every hop is recorded.
    """

    def __init__(self) -> None:
        self.docket_by_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.dc_keys: set[str] = set()
        self.dc_disc: dict[str, dict[str, Any]] = {}
        self.notes: dict[str, Any] = {}

    def want_docket(self, want: set[str], row: dict[str, Any]) -> None:
        cid = frontier_cell_id(row)
        hits = [c for c in (cid, str(row.get("genome_id") or "")) if c and c in want]
        if not hits:
            return
        slim = {k: row.get(k) for k in ("symbol", "family", "params", "source", "producer",
                                        "source_url", "source_title", "contributing_sources",
                                        "mechanism_note", "genome_id", "url", "region",
                                        "source_seat", "source_file", *CC.FIELDS,
                                        CC.DERIVATION_FIELD) if row.get(k) not in (None, "")}
        for c in hits:
            self.docket_by_cell[c].append(slim)
        if "discovery_compiler" in str(row.get("source") or ""):
            self.dc_keys.add(_params_key(row.get("symbol"), row.get("family"),
                                         row.get("params")))

    def walk_donations(self, deadline: float, root: Path = DC_DONATIONS) -> None:
        """Map the wanted compiler cells to their donation rows (discovery id + carried keys)."""
        if not self.dc_keys:
            self.notes["discovery_compiler_donations"] = "nothing to walk"
            return
        try:
            files = sorted(root.glob("*.json"), key=lambda q: q.stat().st_mtime, reverse=True)
        except OSError:
            files = []
        if not files:
            self.notes["discovery_compiler_donations"] = f"ABSENT: {root}"
            return
        read = 0
        for f in files[:DC_MAX_FILES]:
            if time.monotonic() > deadline or len(self.dc_disc) >= len(self.dc_keys):
                break
            doc = _read_json(f, {})
            rows = doc.get("discoveries") if isinstance(doc, dict) else doc
            read += 1
            for r in rows if isinstance(rows, list) else []:
                if not isinstance(r, dict):
                    continue
                k = _params_key(r.get("symbol"), r.get("family"), r.get("params"))
                if k in self.dc_keys and k not in self.dc_disc:
                    self.dc_disc[k] = {**r, "_file": f.name}
        self.notes["discovery_compiler_donations"] = (
            f"{read} file(s) read, {len(self.dc_disc)}/{len(self.dc_keys)} wanted cells found")

    def discovery(self, did: str, registry: Path = REGISTRY) -> dict[str, Any] | None:
        if not did or not registry.exists():
            return None
        try:
            conn = sqlite3.connect(f"file:{registry}?mode=ro", uri=True, timeout=10)
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute("SELECT * FROM discoveries WHERE discovery_id=?",
                                   (did,)).fetchone()
            finally:
                conn.close()
        except sqlite3.Error:
            return None
        if row is None:
            return None
        d = dict(row)
        try:
            payload = json.loads(d.get("payload_json") or "{}")
        except ValueError:
            payload = {}
        return {**(payload if isinstance(payload, dict) else {}), **{
            k: v for k, v in d.items() if v not in (None, "")}}


def _as_row(t: dict[str, Any]) -> dict[str, Any]:
    return {**t.get("row", {}), "symbol": t["symbol"], "family": t["family"],
            "params": t.get("params") or {}}


def _source_fields(p: Pass, row: dict[str, Any]) -> dict[str, Any] | None:
    """The culture fields of `row` when its culture came from the SOURCE, else None."""
    fields, _lang = p.culture(row)
    return fields if CC.is_source_derived(fields[CC.DERIVATION_FIELD]) else None


def _lineage_ids(t: dict[str, Any]) -> list[str]:
    """The ids a docket row may carry for this target: the certificate's own cell id and the
    gauntlet's executable id of its spec (`SYM.family.p=<hash>`), which a hash-less
    certificate key does not spell."""
    out = [str(t["cell_id"])]
    fid = frontier_cell_id({"symbol": t.get("symbol"), "family": t.get("family"),
                            "params": t.get("params") or {}, "timeframe": t.get("timeframe")})
    if fid and fid not in out:
        out.append(fid)
    return out


def resolve(p: Pass, t: dict[str, Any], lin: Lineage, registry: Path = REGISTRY
            ) -> tuple[dict[str, Any], list[str], str]:
    """(fields, lineage hops, reason) for one survivor / live / forward cell.

    A survivor's culture is NEVER the symbol's home: that says where a price is made, not who
    found the edge, and the Tier S test would read it as cultural orthogonality that was never
    mined. No lineage means UNMEASURED with the reason `no_lineage`.
    """
    hops: list[str] = []
    own = _as_row(t)
    got = _source_fields(p, own)
    if got is not None:
        return got, ["own row"], ""
    rows = [r for c in _lineage_ids(t) for r in lin.docket_by_cell.get(c, [])]
    for row in rows:
        hops.append(f"docket:{row.get('source')}")
        got = _source_fields(p, row)
        if got is not None:
            return _mark(got, "lineage_docket"), hops, ""
        if "discovery_compiler" in str(row.get("source") or ""):
            don = lin.dc_disc.get(_params_key(row.get("symbol"), row.get("family"),
                                              row.get("params")))
            if don is None:
                hops.append("discovery_compiler donation: not found")
                continue
            hops.append(f"donation:{don.get('_file')}")
            got = _source_fields(p, don)
            if got is not None:
                return _mark(got, "lineage_donation"), hops, ""
            disc = lin.discovery(str(don.get("discovery_id") or ""), registry)
            if disc is None:
                hops.append(f"discovery {don.get('discovery_id')}: not in registry")
                continue
            hops.append(f"discovery:{disc.get('source_id')}")
            got = _source_fields(p, disc)
            if got is not None:
                return _mark(got, "lineage_discovery"), hops, ""
    fields, _lang = p.culture(own)
    fields = dict(fields)
    how = dict(fields[CC.DERIVATION_FIELD])
    # LAST HOP: the SAME (symbol, family) elsewhere in the docket and backlog, used only when
    # every source-derived cell there names ONE culture -- the rule Tier S's own join applies.
    # A split names several cultures and derives nothing (a pooled guess is not a derivation).
    pooled = p.lineage.get(f"{t['symbol'].upper()}|{t['family']}") or {}
    hops.append(f"symbol+family: {len(pooled)} culture(s) over {sum(pooled.values())} cell(s)")
    if len(pooled) == 1:
        culture, n = next(iter(pooled.items()))
        fields[CC.SOURCE_CULTURE] = culture
        how[CC.SOURCE_CULTURE] = f"inferred:lineage_symbol_family_unanimous({n})"
        if fields[CC.PARTICIPANT_STRUCTURE] != CC.UNMEASURED:
            fields[CC.FAILURE_MODE] = CC.failure_mode(culture, fields[CC.PARTICIPANT_STRUCTURE])
            how[CC.FAILURE_MODE] = f"inferred:template:{fields[CC.PARTICIPANT_STRUCTURE]}"
        fields[CC.DERIVATION_FIELD] = how
        return fields, hops, ""
    if not CC.is_source_derived(how):
        fields[CC.SOURCE_CULTURE] = CC.UNMEASURED
        how[CC.SOURCE_CULTURE] = CC.UNMEASURED
        fields[CC.FAILURE_MODE] = CC.UNMEASURED
        how[CC.FAILURE_MODE] = CC.UNMEASURED
        if how.get(CC.CROWDING_PRIOR, "").startswith("inferred:"):
            fields[CC.CROWDING_PRIOR] = CC.UNMEASURED
            how[CC.CROWDING_PRIOR] = CC.UNMEASURED
    fields[CC.DERIVATION_FIELD] = how
    if any(h.startswith("docket:") for h in hops):
        # lineage WAS walked and ends at a desk organ (a sweep, a lab) that names no source
        return fields, hops, DESK_ORGAN
    return fields, ["no docket row, donation or discovery names this cell", *hops], NO_LINEAGE


def _mark(fields: dict[str, Any], hop: str) -> dict[str, Any]:
    out = dict(fields)
    how = dict(out[CC.DERIVATION_FIELD])
    for f in CC.FIELDS:
        if str(how.get(f) or "").startswith("inferred:") or how.get(f) == CC.DECLARED:
            how[f] = f"inferred:{hop}<{how[f]}>"
    out[CC.DERIVATION_FIELD] = how
    return out


def scan_targets(p: Pass, tgts: list[dict[str, Any]], lin: Lineage,
                 registry: Path = REGISTRY) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve tiers (a) and (b) in full; publish per-tier coverage; index every one of them."""
    survivors_agg = _blank_agg()
    tiers: dict[str, dict[str, Any]] = {}
    for t in tgts:
        fields, hops, reason = resolve(p, t, lin, registry)
        tier = tiers.setdefault(t["tier"], {"n": 0, "culture_measured": 0, "by_culture": {},
                                            "by_rule": {}, "reasons": {},
                                            "structure_measured": 0})
        tier["n"] += 1
        culture = str(fields[CC.SOURCE_CULTURE])
        if culture != CC.UNMEASURED:
            tier["culture_measured"] += 1
        if fields[CC.PARTICIPANT_STRUCTURE] != CC.UNMEASURED:
            tier["structure_measured"] += 1
        _bump(tier["by_culture"], culture)
        _bump(tier["by_rule"], str(fields[CC.DERIVATION_FIELD].get(CC.SOURCE_CULTURE)))
        if reason:
            _bump(tier["reasons"], reason)
        if t["tier"] == TIER_SURVIVORS:
            p.account(survivors_agg, _as_row(t), fields, None, born=True, judged=True,
                      survived=True)
        home = CC.symbol_home(t["symbol"])
        p.write_index(_index_row(
            t["cell_id"], "certificate" if t["tier"] == TIER_SURVIVORS else "live_forward",
            _as_row(t), fields, cell_id=t["cell_id"], tier=t["tier"],
            certificate=t.get("certificate"), identity=t.get("identity"),
            sleeve=t.get("sleeve"), forward_key=t.get("forward_key"),
            stages=t.get("stages"), lineage=hops[:8], culture_reason=reason or None,
            symbol_home=CC.culture_tag(home) if home else None))
    for tier in tiers.values():
        tier["share_culture_measured"] = _share(tier["culture_measured"], tier["n"])
        tier["share_structure_measured"] = _share(tier["structure_measured"], tier["n"])
    return survivors_agg, tiers


def scan_registry(p: Pass, deadline: float, path: Path = REGISTRY) -> dict[str, Any]:
    """The registry's candidates by `seq` cursor, read-only. Stamped columns are declared."""
    st = p.cursor.setdefault("registry", {"seq": 0, "agg": _blank_agg()})
    note: dict[str, Any] = {"path": str(path)}
    if not path.exists():
        note["status"] = "ABSENT"
        return note
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
        conn.row_factory = sqlite3.Row
    except sqlite3.Error as exc:
        note["status"] = f"UNREADABLE: {exc}"
        return note
    read = 0
    try:
        have = {str(r[1]) for r in conn.execute("PRAGMA table_info(research_candidates)")}
        want = [c for c in ("seq", "id", "symbol", "family", "params_json", "mechanism", "origin",
                            "generator", "producer", "source_id", "region", "judged_at",
                            "status", "survived", *CC.FIELDS, CC.DERIVATION_FIELD) if c in have]
        if "seq" not in want:
            note["status"] = "NO_SEQ_COLUMN"
            return note
        seq = int(st.get("seq") or 0)
        while read < REGISTRY_PER_PASS and time.monotonic() < deadline:
            rows = conn.execute(f"SELECT {','.join(want)} FROM research_candidates "  # noqa: S608
                                "WHERE seq > ? ORDER BY seq LIMIT ?",
                                (seq, REGISTRY_CHUNK)).fetchall()
            if not rows:
                break
            for r in rows:
                row = dict(r)
                seq = max(seq, int(row.get("seq") or 0))
                try:
                    row["params"] = json.loads(row.pop("params_json", None) or "{}")
                except ValueError:
                    row["params"] = {}
                fields, lang = p.culture(row)
                judged = bool(row.get("judged_at"))
                survived = bool(row.get("survived")) or str(row.get("status")) == "survived"
                p.account(st["agg"], row, fields, lang, born=True, judged=judged,
                          survived=survived)
                if survived or _informative(fields):
                    p.write_index(_index_row(str(row.get("id") or ""), "registry", row, fields))
            read += len(rows)
        st["seq"] = seq
        note.update({"status": "READ", "rows_this_pass": read, "seq": seq})
    except sqlite3.Error as exc:
        note["status"] = f"UNREADABLE: {exc}"
    finally:
        conn.close()
    return note


# -------------------------------------------------------------------------------- the summary
def _share(n: int, d: int) -> float | str:
    return round(n / d, 4) if d else CC.UNMEASURED


def _non_western(by_culture: dict[str, int]) -> dict[str, Any]:
    measured = {c: n for c, n in by_culture.items() if CC.jurisdiction_of(c)}
    nw = sum(n for c, n in measured.items() if CC.is_western(c) is False)
    total = sum(by_culture.values())
    return {"non_western": nw, "measured_jurisdiction": sum(measured.values()), "total": total,
            "share_of_measured": _share(nw, sum(measured.values())),
            "share_of_all": _share(nw, total)}


def _merge(*aggs: dict[str, Any]) -> dict[str, Any]:
    out = _blank_agg()
    for a in aggs:
        for k in ("rows", "cells", "judged", "survivors", "source_derived"):
            out[k] += int(a.get(k) or 0)
        for f in CC.FIELDS:
            out["unmeasured"][f] += int((a.get("unmeasured") or {}).get(f) or 0)
        for k in ("by_culture", "by_culture_structure_family", "by_class_culture",
                  "by_class_culture_structure", "source_class_culture_structure",
                  "judged_by_culture", "survivors_by_culture", "by_rule"):
            for kk, n in (a.get(k) or {}).items():
                _bump(out[k], kk, int(n))
    return out


def _headline(agg: dict[str, Any]) -> dict[str, Any]:
    cells = int(agg["cells"])
    return {
        "cells": cells, "judged": agg["judged"], "survivors": agg["survivors"],
        "share_culture_inferred": _share(cells - agg["unmeasured"][CC.SOURCE_CULTURE], cells),
        "share_culture_from_source": _share(agg["source_derived"], cells),
        "share_unmeasured": {f: _share(agg["unmeasured"][f], cells) for f in CC.FIELDS},
        "non_western_cells": _non_western(agg["by_culture"]),
        "non_western_judged": _non_western(agg["judged_by_culture"]),
        "non_western_survivors": _non_western(agg["survivors_by_culture"]),
    }


def _top(d: dict[str, int], k: int) -> dict[str, int]:
    return dict(sorted(d.items(), key=lambda kv: -kv[1])[:k])


# -------------------------------------------------------------------------------------- gaps
#: The ground the principal named, as (bucket, jurisdiction, structure or None, why). Each row
#: is a place a culture should be producing cells on an MT5 instrument its participants move.
NAMED_TARGETS: tuple[tuple[str, str, str | None, str], ...] = (
    ("fx", "KR", None, "USDKRW and the KOSPI analogues (JPN225, HK50) are Korean-flow ground"),
    ("index", "KR", None, "no KOSPI CFD: Korean equity flow reaches MT5 via JPN225/HK50/USDKRW"),
    ("metals", "AE", "physical_flow", "Dubai physical gold flow on XAUUSD"),
    ("metals", "IN", "physical_flow", "Mumbai physical gold demand (festivals, duty) on XAUUSD"),
    ("metals", "CN", "physical_flow", "Shanghai premium and import quota on XAUUSD"),
    ("metals", "TR", "physical_flow", "Turkish household gold as a lira hedge on XAUUSD"),
    ("fx", "BR", "retail_heavy", "Brazilian retail FX on USDBRL"),
    ("fx", "RU", "retail_heavy", "Russian retail FX on USDRUB/EURRUB"),
    ("fx", "ZA", "retail_heavy", "South African retail FX on USDZAR/EURZAR/ZARJPY"),
    ("fx", "MX", "retail_heavy", "Mexican retail FX on USDMXN/EURMXN/MXNJPY"),
    ("fx", "TR", "retail_heavy", "Turkish retail FX on USDTRY/EURTRY"),
    ("fx", "JP", "retail_heavy", "Mrs Watanabe margin FX on the yen crosses"),
    ("fx", "CN", "policy_driven", "the PBoC fixing on USDCNH"),
    ("fx", "IN", "policy_driven", "RBI intervention on USDINR"),
    ("index", "JP", "tax_driven", "Japanese retail tax-year (NISA, March year-end) on JPN225"),
    ("index", "CN", "settlement_constrained", "T+1 and price limits on CHINAH/HK50"),
    ("fx", "JP", "settlement_constrained", "gotobi settlement days on USDJPY"),
)


#: Instruments for targets whose ground has no single-home symbol: gold has no home, and Fusion
#: lists no KOSPI or A-share CFD, so Korean and mainland equity flow is reached through analogues.
INSTRUMENT_HINTS: dict[tuple[str, str], list[str]] = {
    ("index", "KR"): ["USDKRW", "JPN225", "HK50"],
    ("index", "CN"): ["CHINAH", "HK50", "USDCNH"],
}
METALS_HINT = ["XAUUSD", "XAGUSD", "XAUEUR", "XAUAUD"]


def _universe_homes() -> dict[tuple[str, str], list[str]]:
    """(bucket, jurisdiction) -> the MT5 instruments whose single home is that jurisdiction."""
    doc = _read_json(UNIVERSE, {})
    out: dict[tuple[str, str], list[str]] = defaultdict(list)
    for sym in (doc if isinstance(doc, dict) else {}):
        home = CC.symbol_home(sym)
        if home:
            out[(asset_bucket(sym), home)].append(str(sym))
    return out


def gaps(agg: dict[str, Any]) -> list[dict[str, Any]]:
    """Asset class x culture with zero or thin cells, ZERO first. The producers' to-do list.

    Two sources of targets: the principal's named ground (NAMED_TARGETS, with a participant
    structure where one was named) and every (class, jurisdiction) the universe itself proves
    exists -- an instrument whose single home is that jurisdiction. A cell is counted for a
    target when its SOURCE culture has that jurisdiction; symbol-home cells are counted apart
    (`cells_symbol_home_only`) because a Korean pair mined from an English blog is not Korean
    mining.
    """
    by_ccs = agg.get("by_class_culture_structure") or {}
    homes = _universe_homes()
    counts: dict[tuple[str, str, str], int] = Counter()
    for key, n in by_ccs.items():
        bucket, culture, struct = ([*key.split("|"), "", "", ""])[:3]
        j = CC.jurisdiction_of(culture)
        if j:
            counts[(bucket, j, struct)] += int(n)
    src_counts = _source_counts(agg)
    targets: list[tuple[str, str, str | None, str]] = list(NAMED_TARGETS)
    named = {(b, j) for b, j, _s, _w in NAMED_TARGETS}
    for (bucket, j), syms in sorted(homes.items()):
        if (bucket, j) not in named and bucket in ("fx", "index", "bonds"):
            targets.append((bucket, j, None, f"home instruments {', '.join(sorted(syms)[:6])}"))
    out: list[dict[str, Any]] = []
    for bucket, j, struct, why in targets:
        total = sum(n for (b, jj, s), n in counts.items()
                    if b == bucket and jj == j and (struct is None or s == struct))
        from_source = src_counts.get((bucket, j, struct or "*"), 0)
        state = "ZERO" if from_source == 0 else ("THIN" if from_source < THIN_CELLS else "")
        if not state:
            continue
        out.append({"asset_class": bucket, "culture": CC.culture_tag(j) or j,
                    "participant_structure": struct or "any", "state": state,
                    "cells_from_source": from_source, "cells_all_rules": total,
                    "instruments": (sorted(homes.get((bucket, j), []))[:8]
                                    or INSTRUMENT_HINTS.get((bucket, j))
                                    or (METALS_HINT if bucket == "metals" else [])),
                    "why": why,
                    "producers": _producers_for(j)})
    out.sort(key=lambda g: (g["state"] != "ZERO", g["participant_structure"] == "any",
                            g["asset_class"], g["culture"]))
    return out


def _source_counts(agg: dict[str, Any]) -> dict[tuple[str, str, str], int]:
    """(bucket, jurisdiction, structure|*) -> SOURCE-derived cells, from the per-pass tallies."""
    out: Counter[tuple[str, str, str]] = Counter()
    for key, n in (agg.get("source_class_culture_structure") or {}).items():
        bucket, culture, struct = ([*key.split("|"), "", "", ""])[:3]
        j = CC.jurisdiction_of(culture)
        if j:
            out[(bucket, j, struct)] += int(n)
            out[(bucket, j, "*")] += int(n)
    return out


def _producers_for(j: str) -> list[str]:
    code = j.lower()
    out = []
    if (DESK / "research" / "countries" / code).is_dir():
        out.append(f"research/countries/{code} (country pack -> pack_cells)")
    out.append(f"deep_forest_miner --region {code}")
    return out


def gap_cultures(path: Path | None = None) -> list[str]:
    """Lower-case jurisdiction codes the last published summary lists as gaps, ZERO first.

    The read a producer makes to aim its next pass (deep_forest_miner.schedule). Empty when the
    summary is absent -- UNMEASURED gaps reorder nothing, they never narrow anything either.
    """
    doc = _read_json(path or SUMMARY, {})
    out: list[str] = []
    for g in doc.get("gaps") or [] if isinstance(doc, dict) else []:
        j = CC.jurisdiction_of(g.get("culture")) if isinstance(g, dict) else None
        if j and j.lower() not in out:
            out.append(j.lower())
    return out


# ------------------------------------------------------------------------------------ the run
def run(budget_s: float = 240.0, *, graph: Path = GRAPH, docket: Path = DOCKET,
        certificates: Path = CERTIFICATES, registry: Path = REGISTRY,
        sleeves: Path = SLEEVES, shadow_dir: Path = SHADOW_DIR,
        donations: Path = DC_DONATIONS) -> dict[str, Any]:
    t0 = time.monotonic()
    cursor = _read_json(CURSOR, {})
    if not isinstance(cursor, dict):
        cursor = {}
    english_prev = cursor.get("english_families")
    english = frozenset(english_prev) if isinstance(english_prev, list) else None
    p = Pass(cursor, english)
    deadline = t0 + max(5.0, budget_s - WRITE_RESERVE_S)
    lin = Lineage()
    try:
        # TIERS (a) AND (b) FIRST, IN FULL: the certificates, then LIVE and forward-clock cells.
        tgts = targets(certificates, sleeves, shadow_dir)
        want = {c for t in tgts for c in _lineage_ids(t)}
        # the docket is read before the backlog because it IS the lineage of (a) and (b)
        d_agg, d_note = scan_docket(p, docket, lineage=lin, want=want)
        lin.walk_donations(t0 + max(5.0, (budget_s - WRITE_RESERVE_S) / 3), donations)
        c_agg, tiers = scan_targets(p, tgts, lin, registry)
        # TIER (c): the backlog, from its cursors, in whatever budget is left
        g_note = scan_graph(p, deadline, graph)
        if g_note.get("reset") and INDEX.exists():
            # a replaced graph restarts the index, so a reader never mixes two files; tiers
            # (a) and (b) are re-resolved in full on every pass, so they are rewritten below
            INDEX.unlink()
            cursor.pop("docket_digest", None)
            cursor["lineage"] = {}
            p.lineage = cursor["lineage"]
            p.close()
            scan_targets(p, tgts, lin, registry)
        r_note = scan_registry(p, t0 + max(5.0, budget_s - WRITE_RESERVE_S / 2), registry)
    finally:
        p.close()
    g_agg = (cursor.get("graph") or {}).get("agg") or _blank_agg()
    r_agg = (cursor.get("registry") or {}).get("agg") or _blank_agg()
    cells = _merge(g_agg, r_agg)
    backlog = (cursor.get("graph") or {})
    tiers[TIER_BACKLOG] = {
        "n": cells["cells"], "culture_measured": cells["cells"]
        - cells["unmeasured"][CC.SOURCE_CULTURE],
        "culture_from_source": cells["source_derived"],
        "share_culture_measured": _share(cells["cells"] - cells["unmeasured"][CC.SOURCE_CULTURE],
                                         cells["cells"]),
        "share_culture_from_source": _share(cells["source_derived"], cells["cells"]),
        "graph_complete": bool(g_note.get("complete")),
        "graph_offset": backlog.get("offset"), "graph_size": g_note.get("size")}
    everything = _headline(cells)
    # SURVIVORS ARE THE CERTIFICATES: the canonical store (certificate_truth), never the graph's
    # CERTIFIED fate rows added on top -- the two overlap, and a sum would count a cell twice.
    everything["graph_certified"] = everything.pop("survivors")
    everything["survivors"] = c_agg["rows"]
    everything["non_western_survivors"] = _non_western(c_agg["survivors_by_culture"])
    cursor["english_families"] = sorted(p.english_seen)
    cursor["updated_at"] = _now()
    _atomic(CURSOR, cursor)
    doc = {
        "generated_at": _now(), "leg": LEG,
        "schema": {"fields": list(CC.FIELDS), "derivation": CC.DERIVATION_FIELD,
                   "participant_structures": list(CC.PARTICIPANT_STRUCTURES),
                   "crowding_priors": list(CC.CROWDING_PRIORS),
                   "culture_format": "<jurisdiction>/<language> | GLOBAL | UNMEASURED",
                   "western": sorted(CC.WESTERN)},
        "tiers": tiers,
        "stores": {"graph": g_note, "registry": r_note, "docket": d_note,
                   "lineage": lin.notes},
        "headline": {"cells": everything, "docket": _headline(d_agg),
                     "certificates": {"n": c_agg["rows"],
                                      "by_culture": _top(c_agg["survivors_by_culture"], 80),
                                      "non_western": _non_western(c_agg["survivors_by_culture"])}},
        "by_culture": _top(cells["by_culture"], 80),
        "by_culture_structure_family": _top(cells["by_culture_structure_family"], 400),
        "by_class_culture": _top(cells["by_class_culture"], 400),
        "by_rule": _top(_merge(cells, d_agg)["by_rule"], 60),
        "docket_by_culture": _top(d_agg["by_culture"], 80),
        "judged_by_culture": _top(cells["judged_by_culture"], 80),
        "english_covered_families": sorted(p.english_seen),
        "gaps": gaps(cells),
        "index": {"path": str(INDEX), "rows_written_this_pass": p.index_rows,
                  "join_keys": ["cell_id (frontier_identity / certificate cell, hunt prefix "
                                "stripped: what research/culture_orthogonality.py reads)",
                                "id", "certificate", "identity (symbol|family|selector)"],
                  "rule": ("one row per cell id, last row wins; every certificate, LIVE and "
                           "forward cell on every pass (tiers a and b), and every backlog "
                           "cell whose culture came from its source or whose participant "
                           "structure is measured. A backlog cell absent here is "
                           "cell_culture.infer({'symbol': ...}): symbol-home or UNMEASURED.")},
        "consumers": {"deep_forest_miner.schedule": "gap_cultures() -> gap grounds first",
                      "research/culture_orthogonality.py (Tier S, #113)":
                          "load_culture_index() keys CELL_CULTURE_INDEX.jsonl by cell_id"},
        "wall_s": round(time.monotonic() - t0, 2),
    }
    return doc


def write(doc: dict[str, Any]) -> None:
    _atomic(SUMMARY, doc)


def render(doc: dict[str, Any]) -> list[str]:
    h = doc["headline"]["cells"]
    return [f"cell_culture_index: {h['cells']} cells, culture inferred "
            f"{h['share_culture_inferred']} (from source {h['share_culture_from_source']}), "
            f"non-Western {h['non_western_cells']['share_of_measured']} of measured; "
            f"{len(doc['gaps'])} gap(s); {doc['index']['rows_written_this_pass']} index row(s)"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Culture provenance per cell, and the gap list")
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=240.0)
    args = ap.parse_args(argv)
    doc = run(budget_s=float(args.budget_s))
    write(doc)
    for line in render(doc):
        print(line)
    return 0


if __name__ == "__main__":                                               # pragma: no cover
    raise SystemExit(main())
