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
    return {"status": "NO_TABLE", "kind": "html", "n_tables": 0, "endpoints_found": 0,
            "why": (why_tables or "no table of 3+ rows and no data links: this page carries "
                                  "navigation or prose, not a series")}


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
    out = SERIES / f"{source_id}.json"
    out.write_text(json.dumps(doc, indent=1)[:4_000_000], encoding="utf-8")
    n = len(doc) if isinstance(doc, (list, dict)) else 1
    return {"status": "PARSED", "kind": "json", "n": n, "files": [out.name]}


def parse_all(only: list[str] | None = None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    endpoints_out: list[dict[str, str]] = []
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
        if "pdf" in ctype:
            rec = _parse_pdf(body, sid)
        elif "json" in ctype:
            rec = _parse_json(body, sid)
        else:
            rec = _parse_html(body, sid, url)
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
        "rule": ("keyed by payload SHAPE, never by source: 40 of 44 vaulted payloads are HTML, "
                 "so one HTML parser covers forty and three shapes cover everything. A parser "
                 "per source would rot at 43 different rates and block the 44th."),
        "n_sources": len(rows),
        "census": dict(census),
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
