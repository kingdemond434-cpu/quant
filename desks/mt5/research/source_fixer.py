"""The source fixer: no registered source stays dead without a named attempt to bring it back.

WHAT IT DOES, EVERY HOUR, TO EVERY SOURCE THE COLLECTOR COULD NOT READ. `asia_collector` records
one verdict per source -- HTTP_ERROR, UNREACHABLE, ROUTE_CHANGED -- and then waits for its next
due time and tries the same URL again. A moved page, a dropped `www`, a scheme that went
https-only or a portal that renamed its data path therefore reads as dead forever, and "dead
forever" is exactly the silence L1.28a forbids: it looks like a source that publishes nothing.

For each such source this tries, politely and in order, the URL VARIANTS a webmaster would try
(scheme swap, `www` on/off, trailing slash, query stripped) and, when none answers, the Wayback
Machine's availability API for the newest archived copy. A variant that answers 200 with a body
the declared shape accepts becomes the source's `url_override` in the registry -- a REPAIR the
collector reads on its next pass (`asia_collector._resolve_url`), stamped with when and from what
so it can be audited or reverted. A Wayback-only answer is recorded as `wayback_url` and the
source stays HTTP-dead for live collection: an archive is history, not a feed. After
`DEAD_AFTER_PASSES` consecutive failed repairs the source is marked `dead_since`, which is a
verdict a reader can act on, never a row that quietly stopped appearing.

WHAT IT NEVER DOES. It does not touch a source that answered 401/403 (that is access control,
not a route), one blocked by robots.txt, or one declared `key`/`paid` without a key; it never
hammers a host (one variant per second, the collector's own politeness), and it never invents a
URL that does not derive from the registered one.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REGISTRY = BASE / "data" / "asia_sources.json"
COLLECTOR_REPORT = BASE / "reports" / "ASIA_COLLECTOR.json"
COLLECTOR_STATE = BASE / "data" / "lake" / "collector_state.json"
OUT = BASE / "reports" / "SOURCE_FIXER.json"
STATE = BASE / "data" / "lake" / "source_fixer_state.json"

FIX_STATUSES = frozenset({"HTTP_ERROR", "UNREACHABLE", "ROUTE_CHANGED"})
SKIP_HTTP = frozenset({401, 403})
DEAD_AFTER_PASSES = 3
VARIANT_GAP_S = 1.0
TIMEOUT_S = 15.0
WAYBACK = "https://archive.org/wayback/available?url="
USER_AGENT = "quant-desk-source-fixer/1.0 (+public data collection; repairs registered routes)"


def _read(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _write_atomic(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(text, "utf-8")
    tmp.replace(p)


def candidate_urls(url: str) -> list[str]:
    """The variants a webmaster would try, in order, never including the original."""
    try:
        u = urllib.parse.urlsplit(url)
    except ValueError:
        return []
    if not u.scheme or not u.netloc:
        return []
    out: list[str] = []

    def add(scheme: str, netloc: str, path: str, query: str) -> None:
        cand = urllib.parse.urlunsplit((scheme, netloc, path or "/", query, ""))
        if cand != url and cand not in out:
            out.append(cand)

    other = "https" if u.scheme == "http" else "http"
    host = u.netloc
    host_www = host if host.startswith("www.") else "www." + host
    host_bare = host[4:] if host.startswith("www.") else host
    path = u.path or "/"
    path_slash = path if path.endswith("/") else path + "/"
    path_noslash = path[:-1] if path.endswith("/") and len(path) > 1 else path
    add(other, host, path, u.query)
    add(u.scheme, host_www if host == host_bare else host_bare, path, u.query)
    add(other, host_www if host == host_bare else host_bare, path, u.query)
    add(u.scheme, host, path_slash if path == path_noslash else path_noslash, u.query)
    if u.query:
        add(u.scheme, host, path, "")
        add(other, host, path, "")
    return out


def _probe(url: str) -> tuple[int | None, str, bytes]:
    """(status, content-type, first bytes) for a GET; status None when unreachable."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            status = int(getattr(r, "status", 0) or 0)
            ctype = str(r.headers.get("Content-Type") or "").lower()
            return status, ctype, r.read(4096)
    except urllib.error.HTTPError as e:
        return int(getattr(e, "code", 0) or 0), "", b""
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None, "", b""


def _acceptable(expect: str, ctype: str, head: bytes) -> tuple[bool, str]:
    """Does the answer look like the declared shape rather than an error or landing page?"""
    looks_html = ("html" in ctype) or head.lstrip().lower().startswith(
        (b"<!doctype html", b"<html"))
    if expect == "json":
        return (("json" in ctype) or head.lstrip().startswith((b"{", b"["))), "json body"
    if expect == "csv":
        return (("csv" in ctype or "text/plain" in ctype) and not looks_html), "csv body"
    if expect == "xml":
        return (("xml" in ctype) or head.lstrip().startswith(b"<?xml")), "xml body"
    if expect == "binary":
        return (not looks_html and len(head) > 0), "binary body"
    # `any`: a 200 with a body of some size; an HTML page is acceptable here (the parser bank
    # reads tables and links), a 0-byte answer is not.
    return len(head) >= 64, "non-empty body"


def _wayback(url: str) -> str | None:
    try:
        with urllib.request.urlopen(WAYBACK + urllib.parse.quote(url, safe=""),
                                    timeout=TIMEOUT_S) as r:
            doc = json.loads(r.read().decode("utf-8", errors="replace"))
    except (OSError, ValueError, urllib.error.URLError):
        return None
    snap = ((doc.get("archived_snapshots") or {}).get("closest") or {})
    return str(snap.get("url")) if snap.get("available") and snap.get("url") else None


def _failed_sources(registry_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """id -> the collector's last verdict row, for sources it could not read."""
    by_id = {str(r.get("id")): r for r in registry_rows if isinstance(r, dict)}
    out: dict[str, dict[str, Any]] = {}
    report = _read(COLLECTOR_REPORT, {})
    for row in (report.get("rows") or []) if isinstance(report, dict) else []:
        if not isinstance(row, dict):
            continue
        sid = str(row.get("id") or "")
        if sid in by_id and str(row.get("status")) in FIX_STATUSES:
            out[sid] = row
    state = _read(COLLECTOR_STATE, {})
    for sid, st in (state.items() if isinstance(state, dict) else []):
        if sid in by_id and sid not in out and isinstance(st, dict) \
                and str(st.get("status")) in FIX_STATUSES:
            out[sid] = {"id": sid, **st}
    return out


def run(*, budget_s: float = 240.0, dry_run: bool = False) -> dict[str, Any]:
    registry = _read(REGISTRY, {})
    rows = [r for r in (registry.get("sources") or []) if isinstance(r, dict)]
    failed = _failed_sources(rows)
    fstate = _read(STATE, {})
    if not isinstance(fstate, dict):
        fstate = {}
    started = time.monotonic()
    results: list[dict[str, Any]] = []
    repaired = 0
    for sid, verdict in sorted(failed.items()):
        if time.monotonic() - started > budget_s:
            results.append({"id": sid, "outcome": "DEFERRED", "why": "fixer budget exhausted"})
            continue
        src = next(r for r in rows if str(r.get("id")) == sid)
        http = verdict.get("http")
        if isinstance(http, int) and http in SKIP_HTTP:
            results.append({"id": sid, "outcome": "NOT_A_ROUTE_PROBLEM",
                            "why": f"HTTP {http} is access control; no variant can fix it"})
            continue
        if str(src.get("access") or "public") in ("key", "paid"):
            results.append({"id": sid, "outcome": "NOT_A_ROUTE_PROBLEM",
                            "why": "declares key/paid access; a missing key is not a dead route"})
            continue
        base_url = str(src.get("url_override") or src.get("url") or "")
        expect = str(src.get("expect") or "any")
        tried: list[dict[str, Any]] = []
        fix: str | None = None
        for cand in candidate_urls(base_url):
            status, ctype, head = _probe(cand)
            ok, _shape = (_acceptable(expect, ctype, head) if status == 200 else (False, ""))
            tried.append({"url": cand, "status": status, "ok": ok})
            if ok:
                fix = cand
                break
            time.sleep(VARIANT_GAP_S)
        entry = fstate.setdefault(sid, {"failed_passes": 0})
        if fix:
            entry.update({"failed_passes": 0, "fixed_at": datetime.now(UTC).isoformat(
                timespec="seconds"), "fixed_from": base_url, "fixed_to": fix})
            entry.pop("dead_since", None)
            if not dry_run:
                src["url_override"] = fix
                src["route_repair"] = {"at": entry["fixed_at"], "from": base_url,
                                       "by": "source_fixer"}
            repaired += 1
            results.append({"id": sid, "outcome": "REPAIRED", "from": base_url, "to": fix,
                            "tried": tried})
            continue
        wb = _wayback(base_url)
        entry["failed_passes"] = int(entry.get("failed_passes", 0)) + 1
        if wb:
            entry["wayback_url"] = wb
        if entry["failed_passes"] >= DEAD_AFTER_PASSES and not entry.get("dead_since"):
            entry["dead_since"] = datetime.now(UTC).isoformat(timespec="seconds")
        results.append({"id": sid, "outcome": "STILL_DEAD" if not entry.get("dead_since")
                        else "DEAD", "failed_passes": entry["failed_passes"],
                        "wayback_url": wb, "tried": tried,
                        "why": ("no variant answered with the declared shape; the newest "
                                "archived copy is recorded for backfill, live collection stays "
                                "dead until the route is corrected in the registry")})
    if repaired and not dry_run:
        _write_atomic(REGISTRY, json.dumps(registry, indent=1, ensure_ascii=False))
    if not dry_run:
        _write_atomic(STATE, json.dumps(fstate, indent=1))
    doc = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "rule": ("every source the collector could not read gets the webmaster's variants tried "
                 "and the Wayback copy located; a variant that answers in the declared shape "
                 "becomes url_override in the registry; three failed passes mark dead_since"),
        "n_failed_sources": len(failed), "n_repaired": repaired,
        "n_dead": sum(1 for r in results if r.get("outcome") == "DEAD"),
        "dry_run": dry_run, "results": results,
    }
    _write_atomic(OUT, json.dumps(doc, indent=1, ensure_ascii=False))
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--budget", type=float, default=240.0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    doc = run(budget_s=args.budget, dry_run=args.dry_run)
    print(f"source fixer: {doc['n_failed_sources']} failed source(s), {doc['n_repaired']} "
          f"repaired, {doc['n_dead']} dead -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
