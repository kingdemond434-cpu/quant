"""A venue rejection must carry the venue's reason, not just its status code.

THE FAILURE THIS CLOSES was met on the first live arming. `run_spot_executor` printed

    venue unreadable (HTTPError: HTTP Error 401: Unauthorized) -- refusing

and that sentence is true of at least four completely different problems, each with a different
fix: a wrong key (-2014), a right key from a non-whitelisted IP or without trading permission
(-2015), a clock skew (-1021), a bad signature (-1022). `HTTPError.__str__` discards the body,
which is the only part that says which. An operator holding that message has nothing to act on and
will re-paste the same key three times.
"""

from __future__ import annotations

import io
import urllib.error
import urllib.request

import pytest

from libs.execution import binance_spot_live as live


def _http_error(code: int, body: bytes) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://api.binance.com/api/v3/account", code, "Unauthorized",
                                  {}, io.BytesIO(body))


def test_THE_BINANCE_ERROR_CODE_SURVIVES_INTO_THE_MESSAGE(monkeypatch: pytest.MonkeyPatch) -> None:
    """-2015 is the difference between 'wrong key' and 'right key, wrong IP'. Losing it costs the
    operator the entire diagnosis."""
    body = b'{"code":-2015,"msg":"Invalid API-key, IP, or permissions for action."}'
    monkeypatch.setattr(live, "_urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(_http_error(401, body)))
    with pytest.raises(RuntimeError) as ei:
        live._open(urllib.request.Request("https://api.binance.com/api/v3/account"))
    msg = str(ei.value)
    assert "401" in msg
    assert "-2015" in msg, "the venue's own code is the actionable part and must survive"
    assert "Invalid API-key, IP, or permissions" in msg


def test_A_BODYLESS_REJECTION_STILL_RAISES_AND_SAYS_SO(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unreadable body must not become a silent success, and must not mask the status code."""
    class _Dead(io.BytesIO):
        def read(self, *a: object, **k: object) -> bytes:
            raise OSError("stream closed")

    err = urllib.error.HTTPError("u", 418, "teapot", {}, _Dead(b""))
    monkeypatch.setattr(live, "_urlopen", lambda *a, **k: (_ for _ in ()).throw(err))
    with pytest.raises(RuntimeError) as ei:
        live._open(urllib.request.Request("https://api.binance.com/api/v3/account"))
    assert "418" in str(ei.value) and "no body" in str(ei.value)


def test_THE_MESSAGE_IS_BOUNDED(monkeypatch: pytest.MonkeyPatch) -> None:
    """A venue returning an HTML error page must not paste a kilobyte into every journal line."""
    monkeypatch.setattr(live, "_urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(_http_error(502, b"x" * 50_000)))
    with pytest.raises(RuntimeError) as ei:
        live._open(urllib.request.Request("https://api.binance.com/api/v3/account"))
    assert len(str(ei.value)) < 500


def test_A_SUCCESSFUL_CALL_IS_UNCHANGED(monkeypatch: pytest.MonkeyPatch) -> None:
    """The error path must not have altered the happy path -- this wraps every read and every
    order placement in the live spot connector."""
    class _Resp(io.BytesIO):
        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *a: object) -> None:
            return None

    monkeypatch.setattr(live, "_urlopen", lambda *a, **k: _Resp(b'{"ok":1}'))
    assert live._open(urllib.request.Request("https://api.binance.com/api/v3/ping")) == {"ok": 1}


def test_EVERY_CALL_RESOLVES_IPv4_ONLY(monkeypatch: pytest.MonkeyPatch) -> None:
    """THE ONE THAT COST A LIVE ARMING. The box is dual-stack -- 95.216.191.70 and
    2a01:4f9:c010:9451::1 -- and Python's resolver preferred the v6 address. The key was
    whitelisted for the v4 one, so every request arrived from an address the venue had never been
    told about and Binance answered `-2015 Invalid API-key, IP, or permissions for action` on a key
    whose key, secret and permissions were all correct.

    The venue's message names three causes and the true one is a fourth it does not mention. There
    is no way to notice this from inside the process, which is why the family is pinned in code and
    asserted here rather than left to the host's resolver ordering.
    """
    seen: list[int] = []

    def _spy(host: str, port: int, family: int = 0, *a: object, **k: object) -> list[object]:
        seen.append(family)
        raise OSError("stop here -- the family is what this test is about")

    monkeypatch.setattr(live.socket, "getaddrinfo", _spy)
    conn = live._IPv4HTTPSConnection("api.binance.com", 443)
    with pytest.raises(OSError):
        conn.connect()
    assert seen == [live.socket.AF_INET], (
        f"resolved with family {seen} -- anything but AF_INET lets a dual-stack host choose the "
        "egress address, and the egress address is what the venue whitelist matches")


def test_THE_IPv4_PIN_IS_ON() -> None:
    """A constant nobody sets is a constant somebody unsets. The live box needs this True; the
    test states the requirement so flipping it is a visible decision rather than a silent one."""
    assert live.FORCE_IPV4 is True


def test_THE_TLS_CONTEXT_IS_NEVER_NONE() -> None:
    """The custom connection wraps its own socket, so a missing context would mean an unverified
    TLS session on the module that places orders -- and it would still work, which is the danger."""
    conn = live._IPv4HTTPSConnection("api.binance.com", 443)
    assert isinstance(conn._tls, live.ssl.SSLContext)
    assert conn._tls.verify_mode == live.ssl.CERT_REQUIRED
    assert conn._tls.check_hostname is True
