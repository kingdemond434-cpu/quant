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

_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_NAT64_LOCAL = ipaddress.ip_network("64:ff9b:1::/48")


def _embedded_v4(ip: ipaddress.IPv4Address | ipaddress.IPv6Address
                 ) -> ipaddress.IPv4Address | None:
    """The IPv4 address an IPv6 transition form reaches (mapped, NAT64, 6to4, Teredo), if any.
    `64:ff9b::7f00:1` is loopback through a NAT64 gateway and `is_global` alone passes it."""
    if not isinstance(ip, ipaddress.IPv6Address):
        return None
    if ip.ipv4_mapped:
        return ip.ipv4_mapped
    if ip in _NAT64:
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    if ip.sixtofour:
        return ip.sixtofour
    if ip.teredo:
        return ip.teredo[1]
    return None


def address_refusal(a: str) -> str:
    """'' when one resolved address is public, else why not."""
    try:
        ip = ipaddress.ip_address(a.split("%")[0])
    except ValueError:
        return "UNRESOLVABLE"
    inner = _embedded_v4(ip)
    if ip in _NAT64_LOCAL or (inner is not None and (not inner.is_global or inner.is_multicast)):
        return f"PRIVATE_HOST:{a}"
    if not ip.is_global or ip.is_multicast:
        return f"PRIVATE_HOST:{a}"
    return ""


def resolve_public(url: str, *, resolve: Callable[[str], list[str]] | None = None
                   ) -> tuple[list[str], str]:
    """(every address the host resolves to, '') when all are public, else ([], why). A caller
    that then CONNECTS TO ONE OF THESE ADDRESSES cannot be rebound to a private one between the
    check and the connect (audit M1 on #332: a second resolution landed on 127.0.0.1)."""
    parts = urllib.parse.urlsplit(str(url or ""))
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return [], "NOT_HTTP"
    if parts.username or parts.password:
        return [], "CREDENTIALS_IN_URL"

    def _resolve(h: str) -> list[str]:
        return sorted({str(i[4][0]) for i in socket.getaddrinfo(h, None)})
    try:
        addrs = (resolve or _resolve)(parts.hostname)
    except (OSError, UnicodeError, ValueError):
        return [], "UNRESOLVABLE"
    if not addrs:
        return [], "UNRESOLVABLE"
    for a in addrs:
        why = address_refusal(a)
        if why:
            return [], why
    return list(addrs), ""


def public_url(url: str, *, resolve: Callable[[str], list[str]] | None = None) -> str:
    """'' when `url` is http(s) to a PUBLIC host, else why not (audit must-fix 8, SSRF).

    A model names these URLs, and crawled text reaches the model, so a URL may point anywhere:
    the box's loopback (Ollama's unauthenticated API on 127.0.0.1:11434), the LAN, link-local
    cloud metadata. Every address the host resolves to must be global; an unresolvable host is
    refused too, since a later resolution could land anywhere.
    """
    return resolve_public(url, resolve=resolve)[1]
