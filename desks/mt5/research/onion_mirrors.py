#!/usr/bin/env python3
"""THE ONION ALLOWLIST FETCHER: lawful public onion mirrors, and nothing else, through Tor.

SCOPE (principal 2026-10-13). Lawful public onion sites and ugly public data are IN; darknet
markets, hub/carding forums, ransomware leak sites, stolen data and MNPI are OUT, always. This
module therefore cannot discover anything: it requests ONLY the exact URLs listed in
`data/onion_allowlist.json`, each a mirror its own publisher announces on its own clearnet page
(`announced_at`). It follows no link, and a redirect -- even on the same host -- is recorded and
NOT followed. An entry whose category is not allowed, or whose text names an out-of-scope kind
(market, carding, leak, ransomware, dump ...), is REFUSED by `validate` and reported, never
fetched. Every onion host is IDEAS_ONLY in `terms_fence.SOURCE_POLICY["onion_mirrors"]`: nothing
read here is ever live input.

OFF UNTIL TWO THINGS ARE TRUE, and each absence is a named state, never zero:
  * `QUANT_TOR_SOCKS` (host:port of a local Tor SOCKS5 port) is set -> else every row is
    `UNMEASURED:NEEDS_TOR`;
  * the auditor has ruled on Tor egress versus the desk's no-egress-rotation rule, recorded as
    `data/ONION_EGRESS_RULING.json` {"allowed": true, "ruled_by": "<name>", "ruled_at": ...}
    -> else every row is `UNMEASURED:AWAITING_AUDITOR_RULING`
    (reports/audit/2026-10-29/ONION_LANE.md states the question).

WHEN ON, the fetch is `libs.data.polite_fetch.get` with a SOCKS5h opener built on the fence's own
`guarded_opener`: honest DESK_UA, the onion origin's robots.txt read through Tor and obeyed,
401/403/429/WAF a person-held hard stop, `follow_redirects=False`. The hostname is resolved BY
TOR (socks5h, address type 3): this host never resolves or reaches an onion name itself, and a
non-onion URL is refused before any socket opens, so the opener cannot leak clearnet traffic.
A capture is written once under `data/onion_mirrors/raw/<id>/<sha256>.html` and reported by hash,
size and title.

    python desks/mt5/research/onion_mirrors.py --once [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import socket
import ssl
import struct
import sys
import urllib.request
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNMEASURED = "UNMEASURED"
SOCKS_ENV = "QUANT_TOR_SOCKS"
ALLOWLIST = DESK / "data" / "onion_allowlist.json"
RULING = DESK / "data" / "ONION_EGRESS_RULING.json"
RAW = DESK / "data" / "onion_mirrors" / "raw"
REPORT = DESK / "reports" / "ONION_MIRRORS.json"
#: A v3 onion address: 56 base32 characters. v2 (16) addresses are retired by Tor and refused.
ONION_HOST = re.compile(r"^[a-z2-7]{56}\.onion$")
#: Words that name an out-of-scope kind of site. Any entry carrying one is refused, whatever its
#: category says: the scope is fail closed.
OUT_OF_SCOPE = re.compile(r"(?i)\b(market(?:place)?s?|shop|vendor|carding|cards?|cvv|dumps?|"
                          r"fullz|leaks?|leaked|ransom(?:ware)?|breach(?:ed)?|stolen|"
                          r"hub|forums?|board|exploit|hack(?:ing|ers?)?|drugs?|weapons?|"
                          r"escrow|mnpi|insider)\b")
FETCH_TIMEOUT_S = 60.0


# ============================================================================ the allowlist
def load_allowlist(path: Path = ALLOWLIST) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {"entries": [], "error": f"{type(exc).__name__}: {str(exc)[:120]}"}
    return doc if isinstance(doc, dict) else {"entries": [], "error": "not an object"}


def validate(entry: Mapping[str, Any], allowed: frozenset[str]) -> str:
    """'' when the entry may be fetched, else why it is refused."""
    url = str(entry.get("url") or "")
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https"):
        return "url scheme is not http(s)"
    if not ONION_HOST.match(host):
        return "not a v3 .onion address"
    if parts.query or parts.fragment:
        return "a listed URL carries no query or fragment (no crawling by parameter)"
    if str(entry.get("category") or "") not in allowed:
        return f"category {entry.get('category')!r} is not in allowed_categories"
    ann = urlsplit(str(entry.get("announced_at") or ""))
    if ann.scheme != "https" or not ann.hostname or ann.hostname.endswith(".onion"):
        return "announced_at must be the publisher's own clearnet https page"
    text = " ".join(str(entry.get(k) or "") for k in ("id", "publisher", "category", "why"))
    m = OUT_OF_SCOPE.search(text)
    if m:
        return f"out of scope: names {m.group(0)!r} (markets, forums, leaks are OUT, always)"
    if not str(entry.get("id") or "").strip():
        return "entry has no id"
    return ""


def egress_ruling(path: Path = RULING) -> tuple[bool, str]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return False, "no ruling recorded"
    if isinstance(doc, dict) and doc.get("allowed") is True and str(doc.get("ruled_by") or ""):
        return True, f"allowed by {doc.get('ruled_by')} at {doc.get('ruled_at')}"
    return False, "ruling recorded but not an allow with a named auditor"


# ============================================================================ SOCKS5h
def parse_socks(value: str) -> tuple[str, int] | None:
    v = str(value or "").strip()
    v = re.sub(r"^socks5h?://", "", v)
    if ":" not in v:
        return None
    host, _, port = v.rpartition(":")
    try:
        p = int(port)
    except ValueError:
        return None
    return (host.strip("[]") or "127.0.0.1", p) if 0 < p < 65536 else None


def socks5_connect(proxy: tuple[str, int], host: str, port: int, timeout: float) -> socket.socket:
    """A TCP stream to host:port through a SOCKS5 proxy, the NAME resolved by the proxy (ATYP 3).
    Refuses any host that is not a .onion before a socket is opened."""
    if not host.lower().endswith(".onion"):
        raise OSError(f"onion fetcher refuses a non-onion host: {host}")
    s = socket.create_connection(proxy, timeout=timeout)
    try:
        s.sendall(b"\x05\x01\x00")                       # v5, one method: no auth
        if s.recv(2) != b"\x05\x00":
            raise OSError("SOCKS5 proxy refused the no-auth method")
        name = host.encode("idna")
        s.sendall(b"\x05\x01\x00\x03" + bytes([len(name)]) + name + struct.pack(">H", port))
        head = s.recv(4)
        if len(head) < 4 or head[1] != 0:
            raise OSError(f"SOCKS5 connect failed (reply {head[1] if len(head) > 1 else '?'})")
        atyp = head[3]
        skip = {1: 4, 4: 16}.get(atyp)
        if skip is None:
            skip = s.recv(1)[0]
        s.recv(skip + 2)
        return s
    except Exception:
        s.close()
        raise


class _SocksHTTPConnection(http.client.HTTPConnection):
    proxy: tuple[str, int] = ("127.0.0.1", 9050)

    def connect(self) -> None:
        self.sock = socks5_connect(self.proxy, self.host, self.port, self.timeout or 60.0)


class _SocksHTTPSConnection(http.client.HTTPSConnection):
    proxy: tuple[str, int] = ("127.0.0.1", 9050)

    def connect(self) -> None:
        raw = socks5_connect(self.proxy, self.host, self.port, self.timeout or 60.0)
        ctx = getattr(self, "_context", None) or ssl.create_default_context()
        self.sock = ctx.wrap_socket(raw, server_hostname=self.host)


def socks_opener(proxy: tuple[str, int]) -> Any:
    """`open_(req, timeout=, context=)` for `polite_fetch.get`: the fence's `guarded_opener`
    (terms-fenced, every request) with SOCKS5h HTTP/HTTPS handlers that REPLACE urllib's
    defaults, and `polite_fetch.NoRedirect` so a 30x surfaces and is not followed."""
    from libs.data import polite_fetch as pf
    from libs.data import terms_fence as tf

    http_cls = type("_H", (_SocksHTTPConnection,), {"proxy": proxy})
    https_cls = type("_S", (_SocksHTTPSConnection,), {"proxy": proxy})

    class _HTTP(urllib.request.HTTPHandler):
        def http_open(self, req):  # type: ignore[no-untyped-def]
            return self.do_open(http_cls, req)  # type: ignore[arg-type]

    class _HTTPS(urllib.request.HTTPSHandler):
        def https_open(self, req):  # type: ignore[no-untyped-def]
            return self.do_open(https_cls, req)  # type: ignore[arg-type]

    def open_(req: Any, timeout: float | None = None, context: Any = None) -> Any:
        opener = tf.guarded_opener(None, _HTTP(), _HTTPS(), pf.NoRedirect())
        return opener.open(req, timeout=timeout or FETCH_TIMEOUT_S)

    return open_


# ============================================================================ the pass
def _capture(entry_id: str, body: bytes) -> tuple[str, bool]:
    sha = hashlib.sha256(body).hexdigest()
    d = RAW / re.sub(r"[^A-Za-z0-9_.-]", "_", entry_id)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{sha}.html"
    if p.exists():
        return sha, False
    with open(p, "xb") as fh:                              # write once, never overwrite
        fh.write(body)
    return sha, True


def _title(text: str) -> str:
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", text or "")
    return re.sub(r"\s+", " ", m.group(1)).strip()[:200] if m else ""


def run(*, environ: Mapping[str, str] | None = None, allowlist: Path = ALLOWLIST,
        ruling: Path = RULING, dry_run: bool = False, opener: Any = None,
        write_report: bool = True) -> dict[str, Any]:
    env: Mapping[str, str] = os.environ if environ is None else environ
    now = datetime.now(UTC).isoformat(timespec="seconds")
    doc = load_allowlist(allowlist)
    allowed = frozenset(str(c) for c in doc.get("allowed_categories") or ())
    proxy = parse_socks(str(env.get(SOCKS_ENV) or ""))
    ruled, ruling_why = egress_ruling(ruling)
    if proxy is None:
        gate = f"{UNMEASURED}:NEEDS_TOR"
    elif not ruled:
        gate = f"{UNMEASURED}:AWAITING_AUDITOR_RULING"
    elif dry_run:
        gate = f"{UNMEASURED}:DRY_RUN"
    else:
        gate = ""
    rows: list[dict[str, Any]] = []
    open_ = opener or (socks_opener(proxy) if proxy and not gate else None)
    for e in doc.get("entries") or []:
        if not isinstance(e, dict):
            continue
        row: dict[str, Any] = {"id": e.get("id"), "url": e.get("url"),
                               "publisher": e.get("publisher"),
                               "announced_at": e.get("announced_at"), "use": "IDEAS_ONLY"}
        why = validate(e, allowed)
        if why:
            rows.append({**row, "status": "REFUSED", "why": why})
            continue
        if gate:
            rows.append({**row, "status": gate})
            continue
        from libs.data import polite_fetch as pf
        r = pf.get(str(e["url"]), timeout=FETCH_TIMEOUT_S, retries=1, leg="onion_mirrors",
                   opener=open_, follow_redirects=False)
        if r.redirects:
            rows.append({**row, "status": "REDIRECT_NOT_FOLLOWED",
                         "to": r.redirects[0][2][:200]})
            continue
        if not r.ok or r.verdict:
            rows.append({**row, "status": f"{UNMEASURED}:{r.verdict or 'FETCH_FAILED'}",
                         "http_status": r.status, "error": r.error[:200]})
            continue
        sha, created = _capture(str(e["id"]), r.body or r.text.encode("utf-8"))
        rows.append({**row, "status": "MEASURED", "http_status": r.status, "sha256": sha,
                     "new_capture": created, "bytes": len(r.body or b""),
                     "title": _title(r.text)})
    report = {"generated_at": now, "gate": gate or "OPEN", "socks_env": SOCKS_ENV,
              "socks_set": proxy is not None, "egress_ruling": ruling_why,
              "allowlist": str(allowlist), "allowlist_error": doc.get("error"),
              "n_entries": len(rows),
              "n_refused": sum(1 for r in rows if r["status"] == "REFUSED"),
              "n_measured": sum(1 for r in rows if r["status"] == "MEASURED"),
              "rows": rows}
    if write_report:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        tmp = REPORT.with_suffix(f".tmp{os.getpid()}")
        tmp.write_text(json.dumps(report, indent=1), "utf-8")
        os.replace(tmp, REPORT)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    rep = run(dry_run=a.dry_run)
    print(json.dumps({k: rep[k] for k in ("gate", "n_entries", "n_refused", "n_measured")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
