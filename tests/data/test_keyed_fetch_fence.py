"""Every fetch that carries a credential goes through the redirect guard (audit of 2026-10-07).

`urllib.request.urlopen` copies every header to whatever host a 30x names, so a bearer token or
an `x-api-key` follows a redirect off its API. `libs.data.keyed_sources.keyed_urlopen` keeps it
on the host. This fence reads the source: a raw `urlopen` within a few lines of a credential
header is a regression.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CREDENTIAL = re.compile(r"Bearer |[\"']Authorization[\"']|[\"']x-api-key[\"']")
RAW = re.compile(r"\burlopen\(")
WINDOW = 8
#: Being rewritten elsewhere; each names the PR that routes it through the guard.
OWNED_ELSEWHERE = {
    "scripts/collect_fred_macro.py": "#211 (World Sensor) imports keyed_urlopen",
}


def _tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout.split()
    return [p for p in out if "/tests/" not in f"/{p}" and "/_retired/" not in p]


def test_no_raw_urlopen_next_to_a_credential_header() -> None:
    hits: list[str] = []
    for rel in _tracked():
        if rel in OWNED_ELSEWHERE or rel == "libs/data/keyed_sources.py":
            continue
        lines = (ROOT / rel).read_text("utf-8", errors="replace").splitlines()
        cred = [i for i, ln in enumerate(lines) if CREDENTIAL.search(ln)]
        for i in cred:
            for j in range(i, min(i + WINDOW, len(lines))):
                ln = lines[j]
                if RAW.search(ln) and "keyed_urlopen(" not in ln and ".open(" not in ln:
                    hits.append(f"{rel}:{j + 1}")
    assert not sorted(set(hits)), (
        "raw urlopen beside a credential header -- use libs.data.keyed_sources.keyed_urlopen: "
        f"{sorted(set(hits))}")


def test_keyed_urlopen_keeps_the_header_on_its_host() -> None:
    import io
    import urllib.request
    from email.message import Message

    from libs.data import keyed_sources as ks
    req = urllib.request.Request("https://openrouter.ai/api/v1/credits",
                                 headers={"Authorization": "Bearer sk-or-0123456789"})
    msg = Message()
    msg["Location"] = "https://evil.example/x"
    new = ks.SameHostAuthRedirect((), ("sk-or-0123456789",)).redirect_request(
        req, io.BytesIO(), 302, "Found", msg, "https://evil.example/x")
    assert new is not None and not new.has_header("Authorization")
