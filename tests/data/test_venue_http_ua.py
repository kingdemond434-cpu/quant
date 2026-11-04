"""venue_http sends the desk's honest User-Agent and treats a refusal as a refusal.

THE HISTORY THIS PINS. On 2026-08-01 a 403 drawn by Python-urllib's default UA was "fixed" by
re-sending with a browser UA (L0052). The auditor ruling of 2026-10-14 reversed that: the desk
identifies itself as itself, and a venue that answers only browsers is a refused venue. These
tests make sure the module cannot rot back to impersonation, and that a 403 to the honest UA is
held for the site rather than retried or routed around.
"""

from __future__ import annotations

import io
import sys
import urllib.error
from email.message import Message
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.data import polite_fetch as pf
from libs.data import venue_http
from libs.data.venue_http import DEFAULT_HEADERS, DESK_UA


def test_the_default_headers_carry_the_desk_ua_not_a_browser() -> None:
    ua = DEFAULT_HEADERS.get("User-Agent", "")
    assert ua == DESK_UA == pf.DESK_UA
    assert not pf.looks_like_browser(ua)
    assert "python" not in ua.lower() and "urllib" not in ua.lower()
    assert not hasattr(venue_http, "BROWSER_UA")


class _Resp(io.BytesIO):
    def __init__(self, body: bytes) -> None:
        super().__init__(body)
        self.status = 200
        self.url = ""
        self.headers = {"Content-Type": "application/json"}


def _run(monkeypatch: pytest.MonkeyPatch, page_status: int, caller_ua: str = ""
         ) -> tuple[list[tuple[str, str]], pf.HostAccess, Any]:
    sent: list[tuple[str, str]] = []

    def opener(req: Any, timeout: float, context: Any = None) -> _Resp:
        sent.append((req.full_url, str(req.get_header("User-agent"))))
        if req.full_url.endswith("/robots.txt"):
            return _Resp(b"User-agent: *\nDisallow:\n")
        if page_status == 200:
            return _Resp(b'{"ok": 1}')
        raise urllib.error.HTTPError(req.full_url, page_status, "x", Message(), io.BytesIO(b""))

    acc = pf.HostAccess(path=None)
    real_get = pf.get
    monkeypatch.setattr(pf, "get", lambda url, **kw: real_get(
        url, **{**kw, "opener": opener, "access": acc, "gate": None, "sleep": lambda s: None}))
    try:
        out: Any = venue_http.get_json("https://api.venue.test/v1/x",
                                       headers={"User-Agent": caller_ua} if caller_ua else None)
    except RuntimeError as exc:
        out = exc
    return sent, acc, out


def test_a_browser_ua_from_the_caller_never_reaches_the_wire(
        monkeypatch: pytest.MonkeyPatch) -> None:
    sent, _acc, out = _run(monkeypatch, 200, caller_ua="Mozilla/5.0 Chrome/124.0 Safari/537.36")
    assert out == {"ok": 1}
    assert sent and all(ua == pf.DESK_UA for _, ua in sent)


@pytest.mark.parametrize("code", [401, 403, 429])
def test_a_refusal_is_held_and_never_retried(monkeypatch: pytest.MonkeyPatch, code: int) -> None:
    sent, acc, out = _run(monkeypatch, code)
    assert isinstance(out, RuntimeError) and "never re-sent with a browser" in str(out)
    assert len([u for u, _ in sent if not u.endswith("/robots.txt")]) == 1
    assert acc.hold("https://api.venue.test/other")


def test_the_refusal_rule_is_documented_at_the_seam_itself() -> None:
    """The rule that a 403 to the honest UA is a refusal, never a cue to impersonate, lives in the
    module that raises the error, where the person diagnosing a 403 is actually looking."""
    src = (Path(__file__).resolve().parents[2] / "libs/data/venue_http.py").read_text("utf-8")
    assert "403" in src and "METHOD_BLOCKED" in src and "browser" in src
