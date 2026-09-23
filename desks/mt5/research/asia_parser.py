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

    python desks/mt5/research/asia_parser.py
    python desks/mt5/research/asia_parser.py --id sge_benchmark
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
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
                df = reader(body)
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
            return int(pq.ParquetFile(path).metadata.num_rows)
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
    (SERIES / f"{source_id}.pit.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    statuses = [f.get("status") for f in stamped]
    rec["n_rows"] = int(n_rows)
    rec["pit"] = {"lag_days": lag, "lag_basis": lag_why, "n_rows": int(n_rows),
                  "status": ("STAMPED" if all(x == "STAMPED" for x in statuses)
                             else "PARTIAL" if any(x == "STAMPED" for x in statuses)
                             else "UNSTAMPED")}


def parse_all(only: list[str] | None = None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    endpoints_out: list[dict[str, str]] = []
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
        rec = _dispatch(body, ctype, url, sid)
        _stamp_pit(rec, sid, meta, registry)
        rec.update({"id": sid, "url": url, "bytes": meta.get("bytes"),
                    "fetched_utc": meta.get("fetched_utc")})
        rows.append(rec)
        for u in rec.get("endpoints") or []:
            endpoints_out.append({"kind": "address", "url": u, "route": f"asia_parser:{sid}"})

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
