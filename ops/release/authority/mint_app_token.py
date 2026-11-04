#!/usr/bin/env python3
"""Mint a GitHub App installation token for the release authority (read-only App) and print it
on stdout, for `GH_TOKEN` of the authority's own process only. The App's private key stays in
the authority's ACL'd folder; this never writes the token anywhere.

    python mint_app_token.py --app-id N --installation-id N --key C:\\opt\\authority\\key\\app.pem
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
import urllib.request
from pathlib import Path


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def jwt(app_id: str, key_pem: bytes, now: float | None = None) -> str:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    now = time.time() if now is None else now
    head = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    body = _b64(json.dumps({"iat": int(now) - 60, "exp": int(now) + 540, "iss": app_id}).encode())
    key = serialization.load_pem_private_key(key_pem, password=None)
    sig = key.sign(f"{head}.{body}".encode(), padding.PKCS1v15(), hashes.SHA256())  # type: ignore[union-attr,call-arg]
    return f"{head}.{body}.{_b64(sig)}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-id", required=True)
    ap.add_argument("--installation-id")
    ap.add_argument("--key", required=True)
    ap.add_argument("--find-installation", metavar="OWNER",
                    help="print the App's installation id on OWNER's account and exit")  # fmt: skip
    ap.add_argument("--permissions", metavar="INSTALLATION_ID",
                    help="print an installation's permissions as JSON and exit")  # fmt: skip
    a = ap.parse_args(argv)
    token = jwt(a.app_id, Path(a.key).read_bytes())
    if a.permissions:
        req = urllib.request.Request(
            f"https://api.github.com/app/installations/{int(a.permissions)}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            print(json.dumps(json.loads(r.read()).get("permissions") or {}, sort_keys=True))
        return 0
    if a.find_installation:
        req = urllib.request.Request(
            "https://api.github.com/app/installations",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            got = [
                i["id"] for i in json.loads(r.read())
                if str((i.get("account") or {}).get("login", "")).lower()
                == a.find_installation.lower()
            ]  # fmt: skip
        if not got:
            print("NOT INSTALLED: install the App on the repository first", file=sys.stderr)
            return 3
        print(got[0])
        return 0
    if not a.installation_id:
        ap.error("--installation-id is required")
    req = urllib.request.Request(
        f"https://api.github.com/app/installations/{a.installation_id}/access_tokens",
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        print(json.loads(r.read())["token"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
