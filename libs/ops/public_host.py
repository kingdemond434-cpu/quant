"""Is a URL safe to fetch from the box? Only http(s) to hosts whose every address is global.

URLs that a model names (llm_lab role S, and the collector that later fetches those rows) can
point anywhere: the box's loopback (Ollama's unauthenticated API on 127.0.0.1:11434), the LAN,
or link-local cloud metadata. This is the SSRF check (audit must-fix 8, 2026-10-13).
"""
from __future__ import annotations

import ipaddress
import socket
import urllib.parse
from collections.abc import Callable


def public_url(url: str, *, resolve: Callable[[str], list[str]] | None = None) -> str:
    """'' when `url` is http(s) to a PUBLIC host, else why not (audit must-fix 8, SSRF).

    A model names these URLs, and crawled text reaches the model, so a URL may point anywhere:
    the box's loopback (Ollama's unauthenticated API on 127.0.0.1:11434), the LAN, link-local
    cloud metadata. Every address the host resolves to must be global; an unresolvable host is
    refused too, since a later resolution could land anywhere.
    """
    parts = urllib.parse.urlsplit(str(url or ""))
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return "NOT_HTTP"
    if parts.username or parts.password:
        return "CREDENTIALS_IN_URL"
    host = parts.hostname

    def _resolve(h: str) -> list[str]:
        return sorted({str(i[4][0]) for i in socket.getaddrinfo(h, None)})
    try:
        addrs = (resolve or _resolve)(host)
    except (OSError, UnicodeError, ValueError):
        return "UNRESOLVABLE"
    if not addrs:
        return "UNRESOLVABLE"
    for a in addrs:
        try:
            ip = ipaddress.ip_address(a.split("%")[0])
        except ValueError:
            return "UNRESOLVABLE"
        if not ip.is_global or ip.is_multicast:
            return f"PRIVATE_HOST:{a}"
    return ""
