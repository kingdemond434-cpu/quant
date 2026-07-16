"""One-time Netlify setup: find-or-create the site from your token, save creds, do the first deploy.

You do NOT need to hunt for a Site ID -- the token finds/creates the site for you. Run LOCALLY with
your Netlify personal access token (never paste the token into chat).

    python scripts/setup_netlify.py <TOKEN> [site_name]
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_SECRETS = Path("data/secrets/netlify.json")
_API = "https://api.netlify.com/api/v1"


def _req(method: str, url: str, token: str, data: bytes | None = None) -> Any:
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
        return json.loads(body) if body else None


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python scripts/setup_netlify.py <TOKEN> [site_name]")
        raise SystemExit(2)
    token = sys.argv[1].strip()
    name = sys.argv[2].strip() if len(sys.argv) > 2 else "quant-desk"

    try:
        sites = _req("GET", f"{_API}/sites?per_page=100", token) or []
    except urllib.error.HTTPError as e:
        raise SystemExit(f"token rejected (HTTP {e.code}) -- check the access token") from e
    site = next((s for s in sites if s.get("name") == name), None)
    if site is None:
        try:
            site = _req("POST", f"{_API}/sites", token, json.dumps({"name": name}).encode())
        except urllib.error.HTTPError as e:
            raise SystemExit(f"could not create site '{name}': {e.read().decode()[:200]} "
                             "(try a different, unique name)") from e

    url = site.get("ssl_url") or site.get("url")
    _SECRETS.parent.mkdir(parents=True, exist_ok=True)
    _SECRETS.write_text(json.dumps({"token": token, "site_id": site["id"], "url": url}, indent=2),
                        "utf-8")
    print(f"saved -> {_SECRETS} | site '{name}' | PERMANENT LINK: {url}")
    print("deploying web/ now ...")
    subprocess.run([sys.executable, "scripts/publish_netlify.py"], check=False)
    print(f"\nDONE. Send anyone this permanent link: {url}")


if __name__ == "__main__":
    main()
