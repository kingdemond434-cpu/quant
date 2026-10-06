"""ONE PARSER BANK KEYED BY PAYLOAD SHAPE, not 43 parsers keyed by source.

THE BOTTLENECK THIS CLEARS. `asia_collector` put point-in-time bytes on disk for 43 of 85
registered sources and every one of them sat at NEEDS_PARSER -- fetched, vaulted, and read by
nothing. That is the whole regional programme stalled one move short of a series, which is the
same shape as the crawler stopping one move short of the gauntlet.

AND THE OBVIOUS REMEDY IS THE WRONG ONE. Writing a parser per source means 43 of them, rotting at
43 different rates, and the 44th source blocked on the day it is added -- the identical argument
that made the collector generic. So the census decides the design instead of the source list:

    40 of 44   text/html
     3 of 44   application/pdf
     1 of 44   application/json

One HTML parser covers forty. Three shapes cover everything on disk.

WHAT AN HTML PAGE WITH NO TABLE ACTUALLY IS, and this is the part worth getting right. A
statistics portal that carries no `<table>` has not failed to parse -- it is an INDEX, and the
useful thing on it is the `.csv`, `.xlsx` and `.json` links it points at. `world_crawler`'s own
docstring already says this: "A page ABOUT the CFTC archive converts at zero... The .csv links ON
that page are the archive." So a table-less page yields ENDPOINTS, which go back to the collector
as new addresses, and that is a result rather than a failure.

NOTHING HERE FETCHES. It reads the vault. A parser that fetched would re-merge the collection
budget with the parsing one and would also re-read a page that has since changed, which destroys
the point-in-time guarantee the vault exists to give.

HISTORY, NOT A SNAPSHOT (audit 2026-10-06, row 52). This parser used to read only the NEWEST
blob per source and overwrite `series/<id>`, stamping every row at the registry's declared lag.
So a daily snapshot (the CFETS fix, a CFFEX day file) never grew into a series and a revised
statistic silently replaced its first print. Now EVERY vintage in the vault is read, oldest first,
into an APPEND-ONLY ledger per ROOT source (`series/history/<root>.obs.jsonl`, the
`<root>__ep<hash>` children included): one long observation per (dataset, entity, metric,
period), a new row only when the value is new or REVISED (revision_of / revision_delta /
revision_number), never an overwrite. The knowable instant is the page's OWN publication stamp
where it prints one, else the declared lag on the first vintage only (a backfill), else the
receipt -- and always bounded by the receipt. The canonical `series/<root>.parquet` is then the
FIRST-RELEASE view of that ledger, so nothing downstream ever sees a revised value as if it had
been known on the original date. Sources whose registry row declares an `adapter` are read by
`cn_official_tables` (SAFE, CFETS/ChinaMoney, PBOC OMO, NBS easyquery, customs) instead of the
largest-table heuristic.

    python desks/mt5/research/asia_parser.py
    python desks/mt5/research/asia_parser.py --id sge_benchmark
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

VAULT = BASE / "data" / "lake" / "vault"
SERIES = BASE / "data" / "lake" / "series"
FOUND = BASE / "data" / "intelligence" / "asia_endpoints"
OUT = BASE / "reports" / "ASIA_PARSER.json"
#: The append-only observation ledgers, one per ROOT source id, and their processed-blob manifests.
HISTORY = SERIES / "history"
#: Vintages read per source per pass, oldest unread first. A backlog of hundreds of vaulted blobs
#: is worked down across passes rather than in one, and nothing is skipped: the manifest records
#: what was read, so the next pass continues where this one stopped.
MAX_VINTAGES_PER_PASS = int(os.environ.get("ASIA_PARSER_MAX_VINTAGES", "40"))
#: Observations taken from one generic frame. A frame larger than this is a dump, not a release.
MAX_OBS_PER_FRAME = 50_000
#: Columns the first-release wide view may carry. A cross-section with more (a member ranking
#: with hundreds of names) keeps its ledger -- the history is never lost -- and its canonical
#: frame stays the newest vintage, with the reason published.
MAX_WIDE_COLUMNS = 400
LEDGER_VERSION = "asia_parser.ledger/1"

#: A table with fewer rows than this is a navigation widget or a header block, not a series.
MIN_TABLE_ROWS = 3
#: Tables kept per source. A statistics portal can carry dozens; the largest few are the data and
#: the rest are layout. Ranked by row count, which is the only shape-free proxy available.
MAX_TABLES = 5
#: Endpoint extensions worth handing back to the collector as new addresses.
DATA_EXT = (".csv", ".xlsx", ".xls", ".json", ".xml", ".zip", ".txt")


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default if default is not None else {}


def _blobs() -> dict[str, tuple[Path, dict[str, Any]]]:
    """source id -> (newest blob, its metadata). Newest by the meta's own fetch stamp."""
    out: dict[str, tuple[Path, dict[str, Any]]] = {}
    if not VAULT.is_dir():
        return out
    for d in sorted(VAULT.iterdir()):
        if not d.is_dir():
            continue
        best: tuple[str, Path, dict[str, Any]] | None = None
        for meta in d.glob("*.meta.json"):
            m = _read(meta, {})
            blob = meta.with_name(meta.name.replace(".meta.json", ".gz"))
            if not blob.exists():
                continue
            stamp = str(m.get("fetched_utc") or "")
            if best is None or stamp > best[0]:
                best = (stamp, blob, m)
        if best:
            out[d.name] = (best[1], best[2])
    return out


def _vault_history(source_id: str) -> list[tuple[Path, dict[str, Any]]]:
    """EVERY vintage of one source, oldest first by its own fetch stamp. The newest-only reader
    above is what lost the history; this is the whole vault for the source."""
    d = VAULT / source_id
    out: list[tuple[str, Path, dict[str, Any]]] = []
    if not d.is_dir():
        return []
    for meta in d.glob("*.meta.json"):
        m = _read(meta, {})
        blob = meta.with_name(meta.name.replace(".meta.json", ".gz"))
        if blob.exists() and isinstance(m, dict):
            out.append((str(m.get("fetched_utc") or ""), blob, m))
    out.sort(key=lambda t: (t[0], t[1].name))
    return [(b, m) for _s, b, m in out]


def root_of(source_id: str) -> str:
    """A derived endpoint `<root>__ep<hash>` (and its own children) belongs to its root's ledger."""
    return source_id.split("__ep")[0]


def _endpoints(html: str, base_url: str) -> list[str]:
    """The data files a page POINTS AT. An index page's payload is its links, not its prose."""
    from urllib.parse import urljoin
    found: list[str] = []
    for m in re.finditer(r'href=["\']([^"\']+)["\']', html, re.I):
        href = m.group(1).strip()
        low = href.lower().split("?")[0]
        if not low.endswith(DATA_EXT):
            continue
        full = urljoin(base_url, href)
        if full not in found:
            found.append(full)
    return found[:80]


def _parse_html(body: bytes, source_id: str, url: str) -> dict[str, Any]:
    import io

    import pandas as pd
    text = body.decode("utf-8", errors="replace")
    try:
        # `flavor="lxml"` explicitly: html5lib is not installed on this box and pandas would
        # otherwise raise an ImportError that reads like a parse failure rather than a missing
        # dependency. Naming the flavour makes the requirement explicit and the error honest.
        # StringIO, because passing a literal string is deprecated and this desk runs the suite
        # with `filterwarnings = error` -- a FutureWarning here is a test failure, not a note.
        tables = pd.read_html(io.StringIO(text), flavor="lxml")
    except Exception as exc:
        tables = []
        why_tables = f"{type(exc).__name__}: {str(exc)[:70]}"
    else:
        why_tables = ""
    good = [t for t in tables if len(t) >= MIN_TABLE_ROWS and t.shape[1] >= 2]
    good.sort(key=len, reverse=True)
    good = good[:MAX_TABLES]
    endpoints = _endpoints(text, url)

    if good:
        SERIES.mkdir(parents=True, exist_ok=True)
        written: list[str] = []
        for i, t in enumerate(good):
            out = SERIES / f"{source_id}__t{i}.parquet"
            try:
                t.columns = [str(c) for c in t.columns]
                t.to_parquet(out)
            except Exception:
                out = SERIES / f"{source_id}__t{i}.csv"
                t.to_csv(out, index=False)
            written.append(out.name)
        return {"status": "PARSED", "kind": "html_tables", "n_tables": len(good),
                "rows": [len(t) for t in good], "files": written,
                "endpoints_found": len(endpoints), "endpoints": endpoints[:20]}
    if endpoints:
        # AN INDEX, NOT A FAILURE. The page carries no series and points at the ones that do.
        return {"status": "INDEX_PAGE", "kind": "html_links", "n_tables": 0,
                "endpoints_found": len(endpoints), "endpoints": endpoints[:40],
                "why": ("no table of 3+ rows, and the page links data files. Its payload is those "
                        "addresses -- they are handed back to the collector, not discarded")}
    # THE SHAPE THE DESK HAD NEVER READ (2026-09-23). 67 of 101 vaulted payloads came back
    # NO_TABLE with "No tables found matching regex '.+'". A modern statistics portal does not
    # ship a `<table>`: it ships an empty div and the series inside a script -- `__NEXT_DATA__`,
    # a `window.X = {...}` assignment, a `<script type="application/json">` island or a JSONP
    # callback -- and the page renders it in the browser. The bytes carry the series either way,
    # so the reader that finds it is the difference between a pack that emits cells and one that
    # reports a portal. Tried only after tables and links, so nothing that parsed before changes.
    emb = _parse_embedded(text, source_id)
    if emb is not None:
        return {**emb, "endpoints_found": len(endpoints), "endpoints": endpoints[:20]}
    pre = _parse_pre_text(text, source_id)
    if pre is not None:
        return {**pre, "endpoints_found": len(endpoints), "endpoints": endpoints[:20]}
    return {"status": "NO_TABLE", "kind": "html", "n_tables": 0, "endpoints_found": 0,
            "why": (why_tables or "no table of 3+ rows and no data links: this page carries "
                                  "navigation or prose, not a series")}


#: Script islands and assignments that carry a page's data, in the order they are tried.
_EMBED_PATTERNS: tuple[str, ...] = (
    r'<script[^>]+type=["\']application/(?:ld\+)?json["\'][^>]*>(.*?)</script>',
    r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
    r'(?:window|self|globalThis)\.\w+\s*=\s*(\{.*?\}|\[.*?\])\s*;',
    r'(?:var|let|const)\s+\w+\s*=\s*(\{.*?\}|\[.*?\])\s*;',
    r'^\s*\w+\s*\(\s*(\{.*\}|\[.*\])\s*\)\s*;?\s*$',            # JSONP callback({...})
)


def _record_lists(doc: Any, depth: int = 0) -> list[list[dict[str, Any]]]:
    """Every list of like-shaped mappings anywhere in a decoded JSON document.

    A portal's payload buries its series under `data.result.records` or `Series[0].Obs`; the
    useful thing is not the top-level shape but any list of >= MIN_TABLE_ROWS dicts sharing keys.
    Bounded by depth so a pathological document cannot walk forever.
    """
    out: list[list[dict[str, Any]]] = []
    if depth > 6:
        return out
    if isinstance(doc, list):
        rows = [r for r in doc if isinstance(r, dict)]
        if len(rows) >= MIN_TABLE_ROWS and len(set(map(len, (r.keys() for r in rows[:20])))) <= 3:
            out.append(rows)
        for item in doc[:40]:
            out.extend(_record_lists(item, depth + 1))
    elif isinstance(doc, dict):
        for v in list(doc.values())[:60]:
            out.extend(_record_lists(v, depth + 1))
    return out


def _parse_embedded(text: str, source_id: str) -> dict[str, Any] | None:
    """The largest list of records embedded in the page's scripts, as a frame. None when none."""
    import pandas as pd
    best: list[dict[str, Any]] = []
    for pat in _EMBED_PATTERNS:
        for m in re.finditer(pat, text, re.S | re.I | re.M):
            blob = m.group(1).strip()
            if len(blob) < 32 or len(blob) > 8_000_000:
                continue
            try:
                doc = json.loads(blob)
            except ValueError:
                continue
            for rows in _record_lists(doc):
                if len(rows) > len(best):
                    best = rows
        if len(best) >= MIN_TABLE_ROWS:
            break
    if len(best) < MIN_TABLE_ROWS:
        return None
    df = pd.json_normalize(best[:200_000])
    if df.empty or df.shape[1] < 1:
        return None
    return {"status": "PARSED", "kind": "html_embedded_json", "n_tables": 1, "rows": [len(df)],
            "files": [_write_frame(df, source_id, "")],
            "why": "the page ships an empty container and its series inside a script"}


def _parse_pre_text(text: str, source_id: str) -> dict[str, Any] | None:
    """A `<pre>` block of fixed-width or delimited columns -- how central banks still publish."""
    import io

    import pandas as pd
    blocks = re.findall(r"<pre[^>]*>(.*?)</pre>", text, re.S | re.I)
    for raw in sorted(blocks, key=len, reverse=True)[:3]:
        body = re.sub(r"<[^>]+>", "", raw).strip()
        if body.count("\n") < MIN_TABLE_ROWS:
            continue
        for reader in (lambda b: pd.read_csv(io.StringIO(b), sep=None, engine="python"),
                       lambda b: pd.read_fwf(io.StringIO(b))):
            try:
                df = reader(body)  # type: ignore[no-untyped-call]
            except Exception:
                continue
            if len(df) >= MIN_TABLE_ROWS and df.shape[1] >= 2:
                return {"status": "PARSED", "kind": "html_pre_text", "n_tables": 1,
                        "rows": [len(df)], "files": [_write_frame(df, source_id, "")],
                        "why": "a preformatted text block, read as fixed-width or delimited"}
    return None


def _parse_pdf(body: bytes, source_id: str) -> dict[str, Any]:
    try:
        import io

        from pypdf import PdfReader
        r = PdfReader(io.BytesIO(body))
        text = " ".join((p.extract_text() or "") for p in r.pages)
    except Exception as exc:
        return {"status": "PARSE_ERROR", "kind": "pdf",
                "why": f"{type(exc).__name__}: {str(exc)[:70]}"}
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return {"status": "NO_TEXT", "kind": "pdf",
                "why": "the PDF carries no extractable text layer (scanned image, most likely)"}
    SERIES.mkdir(parents=True, exist_ok=True)
    out = SERIES / f"{source_id}.txt"
    out.write_text(text[:4_000_000], encoding="utf-8")
    return {"status": "PARSED", "kind": "pdf_text", "chars": len(text), "pages": len(r.pages),
            "files": [out.name]}


def _parse_json(body: bytes, source_id: str) -> dict[str, Any]:
    try:
        doc = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError as exc:
        return {"status": "PARSE_ERROR", "kind": "json", "why": str(exc)[:80]}
    SERIES.mkdir(parents=True, exist_ok=True)
    # A JSON DUMP IS NOT A SERIES. This wrote the decoded document back out verbatim, so a
    # central bank's API answer landed as one 400 kB `.json` blob that stamped as one row and
    # emitted no cell. The rows are inside it -- `_record_lists` finds the largest list of
    # like-shaped records at any depth -- so the frame is written beside the blob and IS the
    # series. The blob stays because it is the payload the vintage refers to.
    out = SERIES / f"{source_id}.json"
    out.write_text(json.dumps(doc, indent=1)[:4_000_000], encoding="utf-8")
    n = len(doc) if isinstance(doc, (list, dict)) else 1
    best: list[dict[str, Any]] = []
    for rows in _record_lists(doc):
        if len(rows) > len(best):
            best = rows
    if len(best) >= MIN_TABLE_ROWS:
        import pandas as pd
        df = pd.json_normalize(best[:200_000])
        if not df.empty and df.shape[1] >= 1:
            return {"status": "PARSED", "kind": "json_records", "n": n, "n_tables": 1,
                    "rows": [len(df)], "files": [_write_frame(df, source_id, "__records")],
                    "blob": out.name}
    return {"status": "PARSED", "kind": "json", "n": n, "files": [out.name],
            "why": "no list of 3+ like-shaped records inside the document; the blob is the frame"}



def _sniff(body: bytes, ctype: str, url: str) -> str:
    """The payload's SHAPE from its bytes and headers, never from the registry's guess.

    MEASURED 2026-09-16: ABS `format=jsondata` and CFFEX `index.xml` were served with an HTML
    content-type and handed to the table parser, which raised `Unicode strings with encoding
    declaration are not supported` and read as NO_TABLE. The bytes said json and xml.
    """
    head = body[:400].lstrip().lower()
    low = url.lower().split("?")[0]
    if "pdf" in ctype or head.startswith(b"%pdf"):
        return "pdf"
    if head.startswith((b"{", b"[")) or ("json" in ctype and not head.startswith(b"<")):
        return "json"
    is_xml_ctype = "xml" in ctype and "html" not in ctype
    if head.startswith(b"<?xml") or low.endswith(".xml") or is_xml_ctype:
        return "xml"
    if head.startswith(b"pk\x03\x04"):
        return "xlsx" if low.endswith((".xlsx", ".xlsm")) else "zip"
    if low.endswith((".xlsx", ".xls")) or "spreadsheet" in ctype or "ms-excel" in ctype:
        return "xlsx"
    if "csv" in ctype or low.endswith(".csv") or (low.endswith(".txt") and _looks_csv(body)):
        return "csv"
    if "zip" in ctype or low.endswith(".zip"):
        return "zip"
    return "html"


def _looks_csv(body: bytes) -> bool:
    lines = [ln for ln in body[:4000].decode("utf-8", errors="replace").splitlines()
             if ln.strip()][:6]
    if len(lines) < 3:
        return False
    commas = {ln.count(",") for ln in lines}
    semis = {ln.count(";") for ln in lines}
    return (max(commas) >= 1 and len(commas) <= 2) or (max(semis) >= 1 and len(semis) <= 2)


def _write_frame(df: Any, source_id: str, suffix: str) -> str:
    SERIES.mkdir(parents=True, exist_ok=True)
    out = SERIES / f"{source_id}{suffix}.parquet"
    try:
        df.columns = [str(c) for c in df.columns]
        df.to_parquet(out)
    except Exception:
        out = SERIES / f"{source_id}{suffix}.csv"
        df.to_csv(out, index=False)
    return out.name


def _parse_csv(body: bytes, source_id: str) -> dict[str, Any]:
    import io

    import pandas as pd
    try:
        df = pd.read_csv(io.BytesIO(body), sep=None, engine="python")
    except Exception as exc:
        return {"status": "PARSE_ERROR", "kind": "csv",
                "why": f"{type(exc).__name__}: {str(exc)[:70]}"}
    if df.empty or df.shape[1] < 2:
        return {"status": "NO_TABLE", "kind": "csv", "why": f"csv parsed to {df.shape}"}
    return {"status": "PARSED", "kind": "csv", "n_tables": 1, "rows": [len(df)],
            "files": [_write_frame(df, source_id, "")]}


def _parse_xml(body: bytes, source_id: str) -> dict[str, Any]:
    """Repeated sibling elements are rows; their leaf children (and attributes) are columns."""
    import xml.etree.ElementTree as ET

    import pandas as pd
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        return {"status": "PARSE_ERROR", "kind": "xml", "why": str(exc)[:80]}

    def _tag(e: ET.Element) -> str:
        return e.tag.split("}")[-1]

    best: list[ET.Element] = []
    for parent in root.iter():
        kids = list(parent)
        if len(kids) < MIN_TABLE_ROWS:
            continue
        tags = [_tag(k) for k in kids]
        top, n = max(((t, tags.count(t)) for t in set(tags)), key=lambda kv: kv[1])
        rows = [k for k in kids if _tag(k) == top]
        if n >= MIN_TABLE_ROWS and len(rows) > len(best):
            best = rows
    if not best:
        return {"status": "NO_TABLE", "kind": "xml", "why": "no element repeats 3+ times"}
    recs = []
    for r in best:
        rec = {f"@{k}": v for k, v in r.attrib.items()}
        for c in r:
            if len(list(c)) == 0:
                rec[_tag(c)] = (c.text or "").strip()
        if (r.text or "").strip() and not rec:
            rec["text"] = (r.text or "").strip()
        recs.append(rec)
    df = pd.DataFrame(recs)
    if df.empty or df.shape[1] < 1:
        return {"status": "NO_TABLE", "kind": "xml", "why": "repeated elements carry no leaves"}
    return {"status": "PARSED", "kind": "xml_rows", "n_tables": 1, "rows": [len(df)],
            "files": [_write_frame(df, source_id, "")]}


def _parse_xlsx(body: bytes, source_id: str) -> dict[str, Any]:
    import io

    import pandas as pd
    try:
        sheets = pd.read_excel(io.BytesIO(body), sheet_name=None)
    except ImportError as exc:
        return {"status": "NEEDS_PARSER", "kind": "xlsx",
                "why": f"spreadsheet engine missing on this box ({str(exc)[:60]}); bytes vaulted"}
    except Exception as exc:
        return {"status": "PARSE_ERROR", "kind": "xlsx",
                "why": f"{type(exc).__name__}: {str(exc)[:70]}"}
    written, rows = [], []
    for i, (_name, df) in enumerate(list(sheets.items())[:MAX_TABLES]):
        if len(df) >= MIN_TABLE_ROWS and df.shape[1] >= 2:
            written.append(_write_frame(df, source_id, f"__s{i}"))
            rows.append(len(df))
    if not written:
        return {"status": "NO_TABLE", "kind": "xlsx",
                "why": "no sheet with 3+ rows and 2+ columns"}
    return {"status": "PARSED", "kind": "xlsx_sheets", "n_tables": len(written), "rows": rows,
            "files": written}


def _parse_zip(body: bytes, source_id: str, url: str) -> dict[str, Any]:
    import io
    import zipfile
    try:
        zf = zipfile.ZipFile(io.BytesIO(body))
    except zipfile.BadZipFile as exc:
        return {"status": "PARSE_ERROR", "kind": "zip", "why": str(exc)[:80]}
    members = [m for m in zf.namelist()
               if m.lower().endswith(DATA_EXT) and not m.endswith("/")]
    if not members:
        return {"status": "NO_TABLE", "kind": "zip", "why": "archive holds no data member"}
    m = sorted(members, key=lambda x: (not x.lower().endswith(".csv"), x))[0]
    return {**_dispatch(zf.read(m), "", m, source_id), "member": m}


def _dispatch(body: bytes, ctype: str, url: str, source_id: str) -> dict[str, Any]:
    shape = _sniff(body, ctype, url)
    if shape == "pdf":
        return _parse_pdf(body, source_id)
    if shape == "json":
        return _parse_json(body, source_id)
    if shape == "xml":
        rec = _parse_xml(body, source_id)
        if rec.get("status") == "PARSED":
            return rec
        return {**_parse_html(body, source_id, url), "xml_attempt": rec.get("why")}
    if shape == "csv":
        return _parse_csv(body, source_id)
    if shape == "xlsx":
        return _parse_xlsx(body, source_id)
    if shape == "zip":
        return _parse_zip(body, source_id, url)
    return _parse_html(body, source_id, url)


def _canonicalise(rec: dict[str, Any], source_id: str) -> int:
    """Write the source's LARGEST frame under its own bare name, and return the row count.

    THE BREAK THIS CLOSES, measured 2026-09-23. `source_drain.chain_for` looks for
    `series/<id>.parquet|.json|.csv` and nothing else, while an HTML table lands as
    `<id>__t0.parquet` and a zip member as `<id>__s1.parquet`. So a source could be collected,
    parsed into five good frames and PIT-stamped, and still read as `stops_at: collected` --
    40 of 85 sources did. The suffixed frames stay exactly where they are (they are the whole
    table set); this adds the one bare-named alias the chain, the drain and every downstream
    reader address the source by. Never raises: a copy that fails costs the alias, not the parse.
    """
    files = [f for f in (rec.get("files") or []) if isinstance(f, str)]
    if not files:
        return 0
    if any(f in (f"{source_id}.parquet", f"{source_id}.csv", f"{source_id}.json",
                 f"{source_id}.txt") for f in files):
        return _rows_of(SERIES / files[0])
    best, best_n = None, -1
    for name in files:
        n = _rows_of(SERIES / name)
        if n > best_n:
            best, best_n = name, n
    if best is None:
        return 0
    src = SERIES / best
    dst = SERIES / f"{source_id}{src.suffix}"
    try:
        dst.write_bytes(src.read_bytes())
        rec["canonical_file"] = dst.name
    except OSError as exc:
        rec["canonical_file_error"] = f"{type(exc).__name__}: {str(exc)[:60]}"
    return max(best_n, 0)


def _rows_of(path: Path) -> int:
    """Rows in a written frame, 0 when it cannot be read. Cheap: parquet metadata, not a load."""
    try:
        if path.suffix == ".parquet":
            import pyarrow.parquet as pq
            return int(pq.ParquetFile(path).metadata.num_rows)  # type: ignore[no-untyped-call]
        if path.suffix == ".csv":
            with path.open(encoding="utf-8", errors="replace") as fh:
                return max(sum(1 for _ in fh) - 1, 0)
        if path.suffix in (".json", ".txt"):
            return 1 if path.stat().st_size > 64 else 0
    except Exception:
        return 0
    return 0


def _registry_rows() -> dict[str, dict[str, Any]]:
    doc = _read(BASE / "data" / "asia_sources.json", {})
    rows = doc.get("sources") if isinstance(doc, dict) else None
    return {str(r.get("id")): r for r in (rows or []) if isinstance(r, dict) and r.get("id")}


def _stamp_pit(rec: dict[str, Any], source_id: str, meta: dict[str, Any],
               registry: dict[str, dict[str, Any]]) -> None:
    """Add event_time / available_time / ingested_time to every frame this source produced.

    POINT-IN-TIME AT THE PARSER, because this is where a row first has a period. The lag is the
    registry's declared `pit.publication_lag_days` (an endpoint derived from a parent inherits
    the parent's), else a conservative default by cadence; the fetch time is the vintage. A
    frame with no recognisable period column is UNSTAMPED and says so -- it may not be joined
    point-in-time until someone names its period column.
    """
    if rec.get("status") != "PARSED" or not rec.get("files"):
        return
    try:
        import pandas as pd

        from libs.data import pit_stamp
    except ImportError as exc:
        rec["pit"] = {"status": "UNSTAMPED", "why": f"pit_stamp unavailable ({exc})"}
        return
    parent = source_id.split("__ep")[0]
    src = registry.get(source_id) or registry.get(parent)
    lag, lag_why = pit_stamp.lag_for(src)
    stamped: list[dict[str, Any]] = []
    for name in rec["files"]:
        path = SERIES / name
        if not name.endswith((".parquet", ".csv")):
            # A DOCUMENT IS NOT A FRAME (the `cfets_fixing` tokenizer error, source_drain.py:177).
            # The JSON blob and the PDF text were handed to `read_csv`, which raised "Error
            # tokenizing data" and stamped the source UNSTAMPED on the box for a reason that had
            # nothing to do with time. A document carries no rows to stamp: it is the payload the
            # vintage refers to, and the frames beside it (or the ledger) are the series.
            stamped.append({"file": name, "status": "DOCUMENT",
                            "why": "a document blob, not a frame: nothing to stamp row by row"})
            continue
        try:
            df = pd.read_parquet(path) if name.endswith(".parquet") else pd.read_csv(path)
            out, m = pit_stamp.stamp_frame(df, lag_days=lag,
                                           observed_at=meta.get("fetched_utc"),
                                           source_id=source_id, vintage_fallback=True)
            if m.get("status") == "STAMPED":
                if name.endswith(".parquet"):
                    out.to_parquet(path)
                else:
                    out.to_csv(path, index=False)
            stamped.append({"file": name, **m})
        except Exception as exc:
            stamped.append({"file": name, "status": "UNSTAMPED",
                            "why": f"{type(exc).__name__}: {str(exc)[:60]}"})
    # THE ALIAS AND THE ROW COUNT, both AFTER stamping so the canonical frame carries the
    # envelope. `n_rows` is published in the pit doc because `source_drain.chain_for` reads it
    # there to decide REPRESENTED; without it a stamped series with ten thousand rows counted as
    # zero rows and the chain stopped one stage short of emitting a cell.
    n_rows = _canonicalise(rec, source_id)
    doc = {"source_id": source_id, "lag_days": lag, "lag_basis": lag_why, "frames": stamped,
           "n_rows": int(n_rows), "canonical_file": rec.get("canonical_file"),
           "stamped_at": datetime.now(UTC).isoformat(timespec="seconds")}
    SERIES.mkdir(parents=True, exist_ok=True)
    (SERIES / f"{source_id}.pit.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    statuses = [f.get("status") for f in stamped if f.get("status") != "DOCUMENT"]
    rec["n_rows"] = int(n_rows)
    rec["pit"] = {"lag_days": lag, "lag_basis": lag_why, "n_rows": int(n_rows),
                  "status": ("STAMPED" if statuses and all(x == "STAMPED" for x in statuses)
                             else "PARTIAL" if any(x == "STAMPED" for x in statuses)
                             else "UNSTAMPED")}


# =============================================================================== the ledger
def _ledger_path(root: str) -> Path:
    return HISTORY / f"{root}.obs.jsonl"


def _manifest_path(root: str) -> Path:
    return HISTORY / f"{root}.manifest.json"


def read_ledger(root: str) -> list[dict[str, Any]]:
    """Every observation row ever appended for a ROOT source, in append order. [] when none."""
    p = _ledger_path(root)
    out: list[dict[str, Any]] = []
    try:
        with p.open(encoding="utf-8") as fh:
            for ln in fh:
                if ln.strip():
                    try:
                        row = json.loads(ln)
                    except ValueError:
                        continue
                    if isinstance(row, dict):
                        out.append(row)
    except OSError:
        return []
    return out


def _key_id(root: str, o: dict[str, Any]) -> str:
    raw = "|".join(str(o.get(k) or "") for k in ("dataset_id", "entity", "metric", "event_time"))
    return hashlib.sha1(f"{root}|{raw}".encode()).hexdigest()[:16]


def _ts(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).isoformat(timespec="seconds")


def _frames_of(body: bytes, ctype: str, url: str, sid: str) -> tuple[list[Any], dict[str, Any]]:
    """The generic dispatcher's frames for ONE vintage, read in memory.

    `_dispatch` writes its frames under SERIES; an OLD vintage must not overwrite the newest
    one's files, so it is dispatched into a scratch directory and the frames are read back."""
    import tempfile

    import pandas as pd
    global SERIES
    keep = SERIES
    frames: list[Any] = []
    with tempfile.TemporaryDirectory(prefix="asia_vintage_") as tmp:
        SERIES = Path(tmp)
        try:
            rec = _dispatch(body, ctype, url, sid)
            for name in rec.get("files") or []:
                fp = Path(tmp) / str(name)
                if fp.suffix == ".parquet":
                    frames.append(pd.read_parquet(fp))
                elif fp.suffix == ".csv":
                    frames.append(pd.read_csv(fp))
        except Exception as exc:
            rec = {"status": "PARSE_ERROR", "why": f"{type(exc).__name__}: {str(exc)[:80]}"}
        finally:
            SERIES = keep
    return frames, rec


def frame_observations(df: Any, *, source_id: str, dataset_id: str, geography: str | None,
                       fetched: datetime) -> tuple[list[dict[str, Any]], str]:
    """A generic frame as LONG observations: one per (row label, numeric column).

    The period is the frame's own (by name, then by values, as `pit_stamp` finds it); a frame
    with none is a cross-section SNAPSHOT and its period is the fetch instant, which is what makes
    a run of snapshots into a series. Labels are the non-numeric columns (two at most); metrics
    are the columns whose values are >= 60% numbers."""
    import pandas as pd

    from libs.data import pit_stamp
    from research.cn_official_tables import observation, to_number
    if df is None or len(df) == 0:
        return [], "empty frame"
    df = df.copy()
    df.columns = [str(c) for c in df.columns]
    col = pit_stamp.find_period_column(df.columns)
    parsed = None
    if col is not None:
        try:
            parsed = pit_stamp._coerce_periods(df[col])
            if float(parsed.notna().mean()) < 0.8:
                parsed = None
        except Exception:
            parsed = None
    if parsed is None:
        col, parsed = pit_stamp.period_column_by_value(df)
    basis = f"period column {col!r}" if parsed is not None else "snapshot at the fetch instant"
    numeric: list[str] = []
    for c in df.columns:
        if c == col:
            continue
        vals = df[c].map(to_number)
        if float(vals.notna().mean()) >= 0.6:
            numeric.append(c)
    labels = [c for c in df.columns if c != col and c not in numeric][:2]
    if not numeric:
        return [], "no numeric column"
    out: list[dict[str, Any]] = []
    for i in range(min(len(df), MAX_OBS_PER_FRAME)):
        if parsed is not None:
            ev = parsed.iloc[i]
            if pd.isna(ev):
                continue
            event = ev.to_pydatetime()
        else:
            event = fetched
        entity = " | ".join(str(df[c].iloc[i]).strip() for c in labels
                            if str(df[c].iloc[i]).strip() not in ("", "nan", "None"))
        for c in numeric:
            v = to_number(df[c].iloc[i])
            if v is None:
                continue
            out.append(observation(source_id=source_id, dataset_id=dataset_id,
                                   entity=entity[:120], metric=c[:80], value=v, unit=None,
                                   event_time=event, geography=str(geography or "").upper(),
                                   period=str(event)[:10], basis=basis))
    return out, basis


def _vintage_observations(body: bytes, meta: dict[str, Any], sid: str, src: dict[str, Any] | None
                          ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """(observations, summary) for one vaulted payload: the declared adapter, else generic."""
    ctype = str(meta.get("content_type") or "").lower()
    url = str(meta.get("url") or "")
    country = str((src or {}).get("country") or "")
    adapter = str((src or {}).get("adapter") or "")
    fetched = _ts(meta.get("fetched_utc")) or datetime.now(UTC)
    if adapter:
        from research.cn_official_tables import parse as adapt
        res = adapt(adapter, body, ctype, url, sid, country or "cn")
        if res is not None:
            summ = res.summary()
            for o in res.observations:
                if not o.get("publication_time") and res.publication_time:
                    o["publication_time"] = res.publication_time
            return res.observations, summ
    frames, rec = _frames_of(body, ctype, url, sid)
    obs: list[dict[str, Any]] = []
    bases: list[str] = []
    pub, pub_basis = None, ""
    if _sniff(body, ctype, url) == "html":
        from research.cn_official_tables import page_publication_time
        pub, pub_basis = page_publication_time(body[:400_000].decode("utf-8", errors="replace"),
                                               country or None)
    for i, df in enumerate(frames):
        rows, basis = frame_observations(df, source_id=sid, dataset_id=f"{sid}:f{i}",
                                         geography=country, fetched=fetched)
        for o in rows:
            o["publication_time"] = pub
        obs.extend(rows)
        bases.append(basis)
    return obs, {"status": rec.get("status"), "kind": rec.get("kind"), "frames": len(frames),
                 "n_observations": len(obs), "bases": bases[:5], "publication_time": pub,
                 "publication_basis": pub_basis, "why": rec.get("why"),
                 "endpoints": rec.get("endpoints") or []}


def _same(a: Any, b: Any) -> bool:
    try:
        x, y = float(a), float(b)
    except (TypeError, ValueError):
        return bool(a == b)
    return abs(x - y) <= 1e-9 * max(1.0, abs(x), abs(y))


def append_vintage(root: str, observations: list[dict[str, Any]], *, sid: str,
                   meta: dict[str, Any], blob: Path, src: dict[str, Any] | None,
                   latest: dict[str, dict[str, Any]], datasets_seen: set[str]) -> dict[str, int]:
    """Append one vintage's observations to the root's ledger. NEVER rewrites a row.

    A key (dataset, entity, metric, period) already holding the same value is a confirmation and
    writes nothing; a different value is a REVISION row pointing at the one it revises. The
    knowable instant is the source's own publication (or scheduled) stamp, else the declared lag
    on a dataset's FIRST vintage (a backfill of history the desk never saw live), else receipt --
    and never later than receipt, because the desk demonstrably held it then."""
    from libs.data import pit_stamp
    received = _ts(meta.get("fetched_utc")) or datetime.now(UTC)
    lag, _why = pit_stamp.lag_for(src)
    vintage = str(meta.get("sha256") or blob.stem)
    licence = ((src or {}).get("licence") or (src or {}).get("terms")
               or f"access:{(src or {}).get('access') or 'public'}")
    pointer = str(blob.relative_to(BASE)) if str(blob).startswith(str(BASE)) else str(blob)
    counts = {"new": 0, "revised": 0, "confirmed": 0}
    rows: list[dict[str, Any]] = []
    new_datasets: set[str] = set()
    for o in observations:
        ds = str(o.get("dataset_id") or sid)
        first_ds = ds not in datasets_seen
        if first_ds:
            new_datasets.add(ds)
        key = _key_id(root, o)
        prev = latest.get(key)
        if prev is not None and _same(prev.get("value"), o.get("value")):
            counts["confirmed"] += 1
            continue
        ev = _ts(o.get("event_time"))
        pub = _ts(o.get("publication_time"))
        sched = _ts(o.get("scheduled_time"))
        if pub is not None:
            cand, basis = pub, "publication stamp printed by the source"
        elif sched is not None and prev is None:
            cand, basis = sched, "the source's scheduled release instant"
        elif first_ds and prev is None and ev is not None:
            cand = ev + timedelta(days=int(lag))
            basis = f"declared lag {lag}d (first vintage: history the desk never saw live)"
        else:
            cand, basis = received, "first seen at receipt"
        knowable = min(cand, received)
        row = dict(o)
        row.update({
            "source_id": root, "producer_id": sid, "observation_id": hashlib.sha1(
                f"{key}|{vintage}".encode()).hexdigest()[:16], "key_id": key,
            "knowable_at": _iso(knowable), "knowable_basis": basis,
            "received_at": _iso(received), "vintage_id": vintage[:16],
            "revision_number": 0 if prev is None else int(prev.get("revision_number") or 0) + 1,
            "revision_of": None if prev is None else prev.get("observation_id"),
            "revision_delta": (None if prev is None else
                               float(o["value"]) - float(prev.get("value") or 0.0)),
            "licence": licence, "provenance_hash": meta.get("sha256"), "raw_pointer": pointer,
            "ledger_version": LEDGER_VERSION,
        })
        counts["revised" if prev is not None else "new"] += 1
        latest[key] = row
        rows.append(row)
    datasets_seen.update(new_datasets)
    if rows:
        HISTORY.mkdir(parents=True, exist_ok=True)
        with _ledger_path(root).open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    return counts


def ingest_vintages(root: str, sids: list[str], registry: dict[str, dict[str, Any]],
                    limit: int = MAX_VINTAGES_PER_PASS) -> dict[str, Any]:
    """Read every UNREAD vintage of a root and its children into the ledger, oldest first."""
    man = _read(_manifest_path(root), {}) or {}
    done: dict[str, Any] = dict(man.get("read") or {}) if isinstance(man, dict) else {}
    todo: list[tuple[str, str, Path, dict[str, Any]]] = []
    for sid in sids:
        for blob, meta in _vault_history(sid):
            ref = f"{sid}/{blob.name}"
            if ref not in done:
                todo.append((str(meta.get("fetched_utc") or ""), sid, blob, meta))
    todo.sort(key=lambda t: (t[0], t[1], t[2].name))
    ledger = read_ledger(root)
    latest: dict[str, dict[str, Any]] = {}
    datasets_seen: set[str] = set()
    for r in ledger:
        latest[str(r.get("key_id"))] = r
        datasets_seen.add(str(r.get("dataset_id")))
    tot = {"new": 0, "revised": 0, "confirmed": 0}
    read: list[dict[str, Any]] = []
    for _stamp, sid, blob, meta in todo[:max(0, limit)]:
        src = registry.get(sid) or registry.get(root)
        try:
            body = gzip.decompress(blob.read_bytes())
        except Exception as exc:
            done[f"{sid}/{blob.name}"] = {"status": "UNREADABLE",
                                          "why": f"{type(exc).__name__}: {str(exc)[:60]}"}
            continue
        obs, summ = _vintage_observations(body, meta, sid, src)
        c = append_vintage(root, obs, sid=sid, meta=meta, blob=blob, src=src,
                           latest=latest, datasets_seen=datasets_seen)
        for k in tot:
            tot[k] += c[k]
        done[f"{sid}/{blob.name}"] = {"status": summ.get("status"),
                                      "n_observations": len(obs), **c,
                                      "fetched_utc": meta.get("fetched_utc")}
        read.append({"vintage": f"{sid}/{blob.name}", "status": summ.get("status"),
                     "kind": summ.get("kind"), "n_observations": len(obs), **c,
                     "publication_time": summ.get("publication_time"),
                     "endpoints": (summ.get("endpoints") or [])[:40], "why": summ.get("why")})
    HISTORY.mkdir(parents=True, exist_ok=True)
    _manifest_path(root).write_text(json.dumps(
        {"root": root, "ledger_version": LEDGER_VERSION, "read": done,
         "updated_at": datetime.now(UTC).isoformat(timespec="seconds")}, indent=1,
        ensure_ascii=False), encoding="utf-8")
    return {"vintages_read": len(read), "vintages_pending": max(0, len(todo) - limit),
            **tot, "ledger_rows": len(ledger) + tot["new"] + tot["revised"], "read": read[-5:]}


def first_release_frame(root: str, rows: list[dict[str, Any]] | None = None
                        ) -> tuple[Any, str]:
    """The ledger's FIRST-RELEASE wide view: one column per (metric[, entity]), one row per
    period, `available_time` = the latest knowable instant among that row's first releases.

    First releases only, so a backtest conditioning on this frame never sees a revised value on
    the date the original was printed (PIT law: revisions append, never overwrite the past)."""
    import pandas as pd
    rows = read_ledger(root) if rows is None else rows
    first = [r for r in rows if int(r.get("revision_number") or 0) == 0
             and r.get("value") is not None and r.get("event_time")]
    if not first:
        return None, "the ledger holds no first-release observation"
    df = pd.DataFrame(first)
    per_metric = df.groupby("metric")["entity"].nunique()
    df["column"] = [m if per_metric.get(m, 0) <= 1 else f"{m}|{e}"
                    for m, e in zip(df["metric"], df["entity"].fillna(""), strict=False)]
    ncols = int(df["column"].nunique())
    if ncols > MAX_WIDE_COLUMNS:
        return None, (f"{ncols} columns: a cross-section, not a set of series; its ledger keeps "
                      "the full history and the canonical frame stays the newest vintage")
    df["event_time"] = pd.to_datetime(df["event_time"], utc=True, errors="coerce")
    df["knowable_at"] = pd.to_datetime(df["knowable_at"], utc=True, errors="coerce")
    df = df.dropna(subset=["event_time"])
    wide = df.pivot_table(index="event_time", columns="column", values="value", aggfunc="first")
    avail = df.groupby("event_time")["knowable_at"].max()
    recv = df.groupby("event_time")["received_at"].max()
    wide.insert(0, "available_time", avail.reindex(wide.index).to_numpy())
    wide.insert(1, "ingested_time", recv.reindex(wide.index).to_numpy())
    wide = wide.reset_index().sort_values("event_time")
    wide["published_time"] = wide["available_time"]
    wide["source_id"] = root
    wide.columns = [str(c) for c in wide.columns]
    return wide, f"{len(wide)} period(s) x {ncols} series"


def publish_first_release(root: str) -> dict[str, Any]:
    """Write the root's canonical frame from its ledger and the pit doc the chain reads."""
    rows = read_ledger(root)
    if not rows:
        return {"status": "NO_LEDGER"}
    wide, why = first_release_frame(root, rows)
    revisions = sum(1 for r in rows if int(r.get("revision_number") or 0) > 0)
    if wide is None:
        return {"status": "LEDGER_ONLY", "why": why, "ledger_rows": len(rows),
                "revisions": revisions}
    out = SERIES / f"{root}.parquet"
    SERIES.mkdir(parents=True, exist_ok=True)
    try:
        wide.to_parquet(out, index=False)
    except Exception:
        out = SERIES / f"{root}.csv"
        wide.to_csv(out, index=False)
    doc = {"source_id": root, "lag_basis": "per observation: knowable_basis in the ledger",
           "frames": [{"file": out.name, "status": "STAMPED", "n": len(wide),
                       "period_basis": "first-release view of the append-only ledger",
                       "fields": ["event_time", "available_time", "ingested_time",
                                  "published_time", "source_id"]}],
           "n_rows": len(wide), "canonical_file": out.name, "ledger_rows": len(rows),
           "revisions": revisions, "ledger": str(_ledger_path(root).relative_to(BASE))
           if str(_ledger_path(root)).startswith(str(BASE)) else str(_ledger_path(root)),
           "stamped_at": datetime.now(UTC).isoformat(timespec="seconds")}
    (SERIES / f"{root}.pit.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return {"status": "PUBLISHED", "file": out.name, "n_rows": len(wide), "why": why,
            "ledger_rows": len(rows), "revisions": revisions}


def parse_all(only: list[str] | None = None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    endpoints_out: list[dict[str, str]] = []
    roots: dict[str, list[str]] = {}
    registry = _registry_rows()
    for sid, (blob, meta) in sorted(_blobs().items()):
        if only and sid not in only:
            continue
        try:
            body = gzip.decompress(blob.read_bytes())
        except Exception as exc:
            rows.append({"id": sid, "status": "UNREADABLE",
                         "why": f"{type(exc).__name__}: {str(exc)[:60]}"})
            continue
        ctype = str(meta.get("content_type") or "").lower()
        url = str(meta.get("url") or "")
        root = root_of(sid)
        src = registry.get(sid) or registry.get(root)
        if src is not None and src.get("adapter"):
            # A DECLARED SHAPE. The adapter reads the newest payload for the report and its
            # endpoints; the values go to the ledger below, never through the table heuristic.
            from research.cn_official_tables import parse as adapt
            res = adapt(str(src["adapter"]), body, ctype, url, sid,
                        str(src.get("country") or "cn"))
            rec = res.summary() if res is not None else _dispatch(body, ctype, url, sid)
            rec["adapter"] = src["adapter"]
        else:
            rec = _dispatch(body, ctype, url, sid)
            _stamp_pit(rec, sid, meta, registry)
        rec.update({"id": sid, "url": url, "bytes": meta.get("bytes"),
                    "fetched_utc": meta.get("fetched_utc")})
        rows.append(rec)
        roots.setdefault(root, []).append(sid)
        for u in rec.get("endpoints") or []:
            # THE ROUTE NAMES THE ROOT, so a grand-child (index -> article -> attachment) is
            # still resolvable by the collector to a registry row and its pit block.
            endpoints_out.append({"kind": "address", "url": u, "route": f"asia_parser:{sid}"})

    # THE HISTORY. Every unread vintage of every root (children included) into the append-only
    # ledger, then the root's canonical frame republished as the ledger's first-release view.
    ledgers: dict[str, Any] = {}
    for root, sids in sorted(roots.items()):
        try:
            led = ingest_vintages(root, sorted(set(sids)), registry)
            led["publish"] = publish_first_release(root)
        except Exception as exc:
            led = {"status": "LEDGER_ERROR", "why": f"{type(exc).__name__}: {str(exc)[:120]}"}
        ledgers[root] = led
    for r in rows:
        led_any = ledgers.get(root_of(str(r.get("id"))))
        if not isinstance(led_any, dict):
            continue
        led = led_any
        r["ledger"] = {k: led.get(k) for k in ("vintages_read", "vintages_pending", "new",
                                                "revised", "confirmed", "ledger_rows")}
        pub = led.get("publish") or {}
        if r.get("id") == root_of(str(r.get("id"))) and pub.get("status") == "PUBLISHED":
            r["n_rows"] = pub.get("n_rows")
            r["canonical_file"] = pub.get("file")
            r["pit"] = {"status": "STAMPED", "n_rows": pub.get("n_rows"),
                        "lag_basis": "per observation (ledger knowable_basis)"}

    if endpoints_out:
        FOUND.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H")
        (FOUND / f"endpoints_{stamp}.json").write_text(
            json.dumps(endpoints_out, indent=1), encoding="utf-8")

    census = Counter(str(r.get("status")) for r in rows)
    return {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "rule": ("keyed by payload SHAPE sniffed from the bytes, never by the registry's guess: "
                 "html tables, json, xml rows, csv, xlsx sheets, zip members and pdf text; "
                 "every parsed frame is point-in-time stamped with the source's declared lag"),
        "n_sources": len(rows),
        "census": dict(census),
        "pit": dict(Counter(str((r.get("pit") or {}).get("status") or "n/a") for r in rows)),
        "n_endpoints_handed_back": len(endpoints_out),
        "ledger": {"rule": ("every vintage read oldest first into an append-only ledger per root "
                            "source; same value = confirmation, different value = a revision "
                            "row; canonical frame = first-release view"),
                   "roots": len(ledgers),
                   "new": sum(int(v.get("new") or 0) for v in ledgers.values()),
                   "revised": sum(int(v.get("revised") or 0) for v in ledgers.values()),
                   "vintages_read": sum(int(v.get("vintages_read") or 0)
                                        for v in ledgers.values()),
                   "vintages_pending": sum(int(v.get("vintages_pending") or 0)
                                           for v in ledgers.values()),
                   "published": sorted(k for k, v in ledgers.items()
                                       if (v.get("publish") or {}).get("status") == "PUBLISHED"),
                   "per_root": ledgers},
        "series_dir": str(SERIES),
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--id", action="append")
    args = ap.parse_args(argv)
    doc = parse_all(args.id)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1)[:8_000_000], encoding="utf-8")

    print(f"asia parser: {doc['n_sources']} vaulted source(s) -> {doc['census']}")
    for st in ("PARSED", "INDEX_PAGE", "NO_TABLE", "NO_TEXT", "PARSE_ERROR", "UNREADABLE"):
        rs = [r for r in doc["rows"] if r.get("status") == st]
        if not rs:
            continue
        print(f"  {st} {len(rs)}:")
        for r in rs[:6]:
            extra = (f"{r.get('n_tables')} table(s) rows={r.get('rows')}" if st == "PARSED"
                     and r.get("kind") == "html_tables"
                     else f"{r.get('endpoints_found')} endpoint(s)" if st == "INDEX_PAGE"
                     else str(r.get("why") or r.get("kind") or "")[:54])
            print(f"    {r['id']!s:24} {extra}")
    print(f"  {doc['n_endpoints_handed_back']} endpoint(s) handed back to the collector")
    print(f"  -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
