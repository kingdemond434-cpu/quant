"""Deploy web/ to Netlify via the incremental digest API -> the permanent dashboard URL.

Reads token + site_id from data/secrets/netlify.json (written by setup_netlify.py). Pure stdlib --
no npm/Node. Incremental: only files whose content changed since the last deploy are uploaded, so
running this every few minutes is cheap and stays well inside the free tier. The PC pushes OUT, so
it is never internet-exposed.

    python scripts/publish_netlify.py
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_SECRETS = Path("data/secrets/netlify.json")
_WEB = Path("web")
_API = "https://api.netlify.com/api/v1"


def _req(method: str, url: str, token: str, *, data: bytes | None = None,
         ctype: str = "application/json") -> Any:
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Content-Type": ctype})
    with urllib.request.urlopen(req, timeout=90) as r:
        body = r.read()
        return json.loads(body) if body else None


def _local_files() -> dict[str, tuple[Path, str]]:
    out: dict[str, tuple[Path, str]] = {}
    for p in _WEB.rglob("*"):
        if p.is_file() and not p.name.startswith("."):
            rel = "/" + p.relative_to(_WEB).as_posix()
            out[rel] = (p, hashlib.sha1(p.read_bytes()).hexdigest())
    return out


def publish() -> tuple[str, int, int]:
    """Deploy web/ to the configured Netlify site. Returns (url, uploaded, total)."""
    creds = json.loads(_SECRETS.read_text("utf-8"))
    token, site_id = creds["token"], creds["site_id"]
    files = _local_files()
    digest = {rel: sha for rel, (_p, sha) in files.items()}
    dep = _req("POST", f"{_API}/sites/{site_id}/deploys", token,
               data=json.dumps({"files": digest}).encode())
    dep_id, required = dep["id"], set(dep.get("required", []))
    uploaded = 0
    for rel, (p, sha) in files.items():
        if sha in required:
            _req("PUT", f"{_API}/deploys/{dep_id}/files{rel}", token,
                 data=p.read_bytes(), ctype="application/octet-stream")
            uploaded += 1
    url = str(creds.get("url") or dep.get("ssl_url") or dep.get("url") or "")
    return url, uploaded, len(files)


def main() -> None:
    if not _SECRETS.exists():
        raise SystemExit("no Netlify creds -- run: python scripts/setup_netlify.py <TOKEN> [name]")
    try:
        url, up, total = publish()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"netlify deploy failed: HTTP {e.code} {e.read().decode()[:200]}") from e
    print(f"netlify: pushed {up}/{total} files (changed only) -> {url}")


if __name__ == "__main__":
    main()
