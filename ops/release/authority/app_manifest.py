#!/usr/bin/env python3
"""Create one of the box's GitHub Apps from a manifest, with the owner's two clicks and no key
download (ops/release/authority/LEVEL2.md, bootstrap_level2.ps1).

    python app_manifest.py --kind merger --out merger.json --pem app.pem

GitHub's manifest flow (docs: "Registering a GitHub App from a manifest"): the owner's browser
POSTs the manifest to github.com/settings/apps/new, the owner clicks "Create GitHub App", GitHub
redirects to `redirect_url` with a one-hour `code`, and POST /app-manifests/{code}/conversions
returns the App's id, slug and private key. This script serves the auto-submitting form and the
redirect on 127.0.0.1 only, checks the CSRF `state`, converts the code itself and writes the key
straight to `--pem`: the key never sits in a Downloads folder and nobody copies it.

WHAT THIS DOES NOT DO, ON PURPOSE: it does not click anything, hold the owner's session, or
install the App. Creating an identity that holds authority over LIVE is the owner's act; this
only removes the typing (permissions are fixed below and checked again by each installer).
"""

from __future__ import annotations

import argparse
import html
import json
import os
import secrets
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

API = "https://api.github.com"
NEW_APP = "https://github.com/settings/apps/new"
HOMEPAGE = "https://github.com/kingdemond434-cpu/quant/blob/HEAD/ops/release/authority/LEVEL2.md"

#: The permissions each App is created with. Nothing else: the installers refuse more, and a
#: merger with administration or statuses could change or satisfy the rule it merges under.
KINDS: dict[str, dict[str, Any]] = {
    "merger": {
        "name": "quant-merger",
        "description": "Merges PRs the release authority passed. No admin, no statuses.",
        "permissions": {
            "contents": "write", "pull_requests": "write", "workflows": "write",
            "metadata": "read",
        },
    },
    "publisher": {
        "name": "quant-state-publisher",
        "description": "Pushes box state paths to LIVE (a paths-only filter on the box).",
        "permissions": {"contents": "write", "metadata": "read"},
    },
}
FORBIDDEN = frozenset({"administration", "statuses", "checks", "secrets", "environments",
                       "actions", "organization_administration"})  # fmt: skip


def manifest(kind: str, redirect: str, suffix: str = "") -> dict[str, Any]:
    spec = KINDS[kind]
    perms = dict(spec["permissions"])
    bad = FORBIDDEN & set(perms)
    if bad:  # a guard on this file's own table, so an edit cannot widen an App silently
        raise ValueError(f"{kind}: forbidden permission(s) {sorted(bad)}")
    return {
        "name": spec["name"] + suffix,
        "url": HOMEPAGE,
        "description": spec["description"],
        "public": False,
        "redirect_url": redirect,
        "hook_attributes": {"url": HOMEPAGE, "active": False},
        "default_permissions": perms,
        "default_events": [],
    }


def form_page(man: dict[str, Any], state: str) -> str:
    action = f"{NEW_APP}?state={urllib.parse.quote(state)}"
    return (
        "<!doctype html><meta charset=utf-8><title>Create the App</title>"
        f"<p>Sending GitHub the manifest for <b>{html.escape(man['name'])}</b>. On GitHub's page, "
        "click <b>Create GitHub App</b>.</p>"
        f'<form id=f method=post action="{html.escape(action)}">'
        f'<input type=hidden name=manifest value="{html.escape(json.dumps(man))}">'
        "<button>Continue to GitHub</button></form>"
        "<script>document.getElementById('f').submit()</script>"
    )


def convert(code: str, opener: Any = urllib.request.urlopen) -> dict[str, Any]:
    if not code or not all(c.isalnum() or c in "-_" for c in code):
        raise ValueError("the redirect carried no usable code")
    req = urllib.request.Request(
        f"{API}/app-manifests/{code}/conversions", data=b"", method="POST",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "quant-bootstrap"},
    )  # fmt: skip
    with opener(req, timeout=30) as r:
        out: dict[str, Any] = json.loads(r.read().decode())
    for k in ("id", "slug", "pem"):
        if not out.get(k):
            raise ValueError(f"the conversion returned no {k}")
    return out


def check_permissions(kind: str, got: dict[str, Any]) -> list[str]:
    """What GitHub says the created App holds, against the table: an owner who widened a
    permission on GitHub's page before clicking Create is refused here."""
    want = KINDS[kind]["permissions"]
    out = [f"{k} is {v}, expected {want.get(k, 'absent')}" for k, v in sorted(got.items())
           if want.get(k) != v]  # fmt: skip
    out += [f"{k} missing" for k in want if k not in got]
    return out


def write_pem(path: Path, pem: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as f:
        f.write(pem)
    os.replace(tmp, path)


class _Flow:
    def __init__(self, kind: str, port: int, suffix: str) -> None:
        self.kind, self.state = kind, secrets.token_urlsafe(24)
        self.redirect = f"http://127.0.0.1:{port}/done"
        self.man = manifest(kind, self.redirect, suffix)
        self.result: dict[str, Any] | None = None
        self.error: str | None = None
        self.done = threading.Event()


def _handler(flow: _Flow) -> type[BaseHTTPRequestHandler]:
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a: Any) -> None:  # no request log: the code is a credential
            return

        def _send(self, code: int, body: str) -> None:
            data = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            u = urllib.parse.urlparse(self.path)
            q = urllib.parse.parse_qs(u.query)
            if u.path == "/start":
                self._send(200, form_page(flow.man, flow.state))
                return
            if u.path != "/done" or flow.done.is_set():
                self._send(404, "not here")
                return
            if not secrets.compare_digest((q.get("state") or [""])[0], flow.state):
                self._send(400, "state mismatch: ignored")  # not ours: keep waiting
                return
            try:
                flow.result = convert((q.get("code") or [""])[0])
                self._send(200, f"<p>Created <b>{html.escape(flow.result['slug'])}</b>. "
                                "Go back to the PowerShell window.</p>")  # fmt: skip
            except Exception as exc:  # reported to the console, never retried with the code
                flow.error = f"{type(exc).__name__}: {exc}"
                self._send(500, "conversion failed: see the PowerShell window")
            flow.done.set()

    return H


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kind", choices=sorted(KINDS), required=True)
    ap.add_argument("--pem", required=True, help="where the App's private key is written")
    ap.add_argument("--out", required=True, help="JSON: id, slug, permissions (never the key)")
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--suffix", default="", help="appended to the name if it is taken")
    ap.add_argument("--timeout", type=float, default=1800)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args(argv)
    srv = HTTPServer(("127.0.0.1", a.port), lambda *x: None)  # type: ignore[arg-type]
    port = srv.server_address[1]
    flow = _Flow(a.kind, port, a.suffix)
    srv.RequestHandlerClass = _handler(flow)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    start = f"http://127.0.0.1:{port}/start"
    print(f"Opening {start} -> GitHub. Click 'Create GitHub App' for {flow.man['name']}.",
          flush=True)  # fmt: skip
    if not a.no_browser:
        webbrowser.open(start)
    ok = flow.done.wait(a.timeout)
    srv.shutdown()
    if not ok:
        print("TIMED OUT: no App was created. Run this again.")
        return 3
    if flow.error or not flow.result:
        print(f"FAILED: {flow.error}")
        return 2
    got = flow.result.get("permissions") or {}
    bad = check_permissions(a.kind, got)
    if bad:  # checked BEFORE anything is written: no key of a refused App is ever left on disk
        print(f"REFUSED: {flow.result['slug']} was created with other permissions: {bad}. "
              f"Delete it (https://github.com/settings/apps/{flow.result['slug']}/advanced), "
              "then run the bootstrap again. Its key was not kept.")
        return 2
    write_pem(Path(a.pem), flow.result["pem"])
    Path(a.out).write_text(json.dumps({"id": flow.result["id"], "slug": flow.result["slug"],
                                       "permissions": got}),
                           encoding="utf-8")  # fmt: skip
    print(f"created {flow.result['slug']} (App id {flow.result['id']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
