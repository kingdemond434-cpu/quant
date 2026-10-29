"""A URL that carries an API key never follows a redirect to another host (audit #211, 2026-10-07).

`urllib.request.urlopen` follows 301/302/303/307/308 across hosts and re-sends the full URL --
query string and all -- so a key placed in the query (FRED's `api_key=`, BLS's
`registrationkey=`, EIA's `api_key=`) leaks to whatever host the redirect names. `open_keyed`
follows a redirect only when it stays on the same scheme and host; any other redirect raises
`CrossHostRedirect` and nothing is sent to the new host.
"""
from __future__ import annotations

import urllib.parse
import urllib.request
from typing import IO, Any


class CrossHostRedirect(urllib.error.URLError):
    """A keyed request was redirected off its own host; the redirect was refused."""


class _SameHostRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: urllib.request.Request, fp: IO[bytes], code: int, msg: str,
                         headers: Any, newurl: str) -> urllib.request.Request | None:
        old = urllib.parse.urlsplit(req.full_url)
        new = urllib.parse.urlsplit(urllib.parse.urljoin(req.full_url, newurl))
        if (new.scheme, (new.hostname or "").lower(), new.port) != (
                old.scheme, (old.hostname or "").lower(), old.port):
            raise CrossHostRedirect(
                f"refused {code} redirect from {old.hostname} to {new.hostname}: the request "
                "carries an API key")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_keyed(req: urllib.request.Request | str, timeout: float = 30) -> Any:
    """`urlopen` for a request that carries a key: same-host redirects only."""
    return urllib.request.build_opener(_SameHostRedirects).open(req, timeout=timeout)


__all__ = ["CrossHostRedirect", "open_keyed"]
