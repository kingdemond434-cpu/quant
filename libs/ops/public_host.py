"""Is a URL safe to fetch from the box? Only http(s) to hosts whose every address is global.

URLs that a model names (llm_lab role S, and the collector that later fetches those rows) can
point anywhere: the box's loopback (Ollama's unauthenticated API on 127.0.0.1:11434), the LAN,
or link-local cloud metadata. This is the SSRF check (audit must-fix 8, 2026-10-13).
"""
from __future__ import annotations

import ipaddress
import socket
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any


def is_loopback_url(url: str) -> bool:
    """An http URL whose host IS this machine: `localhost` or a loopback IP literal, parsed as an
    address (so `127.999.999.999` or `127.0.0.1.evil.com`, which go to DNS, are not). The local
    LLM seat and free_chain's local rungs accept only these (audit #402)."""
    try:
        parts = urllib.parse.urlsplit(url.strip())
        host = parts.hostname or ""
        _ = parts.port                                    # a malformed port raises here
    except ValueError:
        return False
    if parts.scheme != "http" or not host or "@" in parts.netloc:
        return False                                      # userinfo is never a local server
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A loopback server's redirect is refused, never followed (audit must-fixes on #402): a
    followed 3xx carries the request -- and any Authorization header -- to another host, around
    the proxy, and its reply would be accepted as the local model's answer."""

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any,
                         newurl: str) -> None:
        return None                     # urllib then raises HTTPError with the 3xx code


#: The ONE opener for every loopback request, in llm_seat and free_chain alike: no proxy (a third
#: party) and no redirects (another host). Either would send the prompt off the machine.
LOOPBACK_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


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
