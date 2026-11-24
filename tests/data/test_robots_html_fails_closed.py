"""A robots.txt reply that is not rules must never read as allow-all (fail CLOSED).

`RobotFileParser` finds no rules in an HTML page (soft 404, WAF challenge, homepage) served 200
at /robots.txt and then allows everything. Only 404/410 means "no rules"; 401/403/429/451 is a
hard stop; a 5xx, a transport failure or an HTML body is unread, and unread is not permission.
Every reader below is fed fakes; nothing touches the network.
"""
from __future__ import annotations

import io
import sys
import urllib.error
import urllib.robotparser
from email.message import Message
from pathlib import Path
from typing import Any

import pytest

from libs.data import robots_body as rb

_ROOT = Path(__file__).resolve().parents[2]
_DESK = _ROOT / "desks" / "mt5"

HTML_BODIES = {
    "doctype": "<!DOCTYPE html><html><body>Not found</body></html>",
    "html": "\n  <html lang='en'><head></head></html>",
    "head": "<head><title>Just a moment...</title></head>",
    "body": "<body>Checking your browser</body>",
    "xml": "<?xml version='1.0'?><error>denied</error>",
    "comment": "<!-- waf --><div>blocked</div>",
    "late_doctype": "Please wait\nwhile we check\n<!doctype html><p>challenge</p>",
    "bom": "﻿<html></html>",
}
REAL = "User-agent: *\nDisallow: /private/\n"


def _desk_path() -> None:
    for p in (str(_ROOT), str(_DESK), str(_DESK / "research"), str(_DESK / "side_channels")):
        if p not in sys.path:
            sys.path.insert(0, p)


class _Resp:
    """The smallest urlopen() reply: status, headers, read(), context manager."""

    def __init__(self, body: str, status: int = 200, ctype: str = "text/plain") -> None:
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = ctype
        self._b = body.encode("utf-8")

    def read(self, n: int = -1) -> bytes:
        return self._b if n < 0 else self._b[:n]

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *_a: Any) -> None:
        return None


def _opener(body: str = "", status: int = 200, ctype: str = "text/plain") -> Any:
    def _open(req: Any, *_a: Any, **_k: Any) -> Any:
        url = str(getattr(req, "full_url", req))
        if status >= 400:
            raise urllib.error.HTTPError(url, status, "x", Message(), io.BytesIO(b""))
        return _Resp(body, status, ctype)
    return _open


# --------------------------------------------------------------------------- the shared helper
@pytest.mark.parametrize("name", sorted(HTML_BODIES))
def test_html_body_served_200_is_a_refusal(name: str) -> None:
    body = HTML_BODIES[name]
    assert rb.is_html_body(body)
    got = rb.robots_rules_or_refusal(200, "text/plain", body)
    assert isinstance(got, str) and got.startswith(rb.UNREAD)
    got_b = rb.robots_rules_or_refusal(200, None, body.encode("utf-8"))
    assert isinstance(got_b, str) and got_b.startswith(rb.UNREAD)


@pytest.mark.parametrize("ctype", ["text/html; charset=utf-8", "application/xhtml+xml",
                                   "application/json", "image/png"])
def test_non_text_content_type_is_a_refusal(ctype: str) -> None:
    got = rb.robots_rules_or_refusal(200, ctype, REAL)
    assert isinstance(got, str) and got.startswith(rb.UNREAD)


@pytest.mark.parametrize("code", [401, 403, 429, 451])
def test_auth_rate_and_legal_refusals_are_hard_stops(code: int) -> None:
    got = rb.robots_rules_or_refusal(code, "text/plain", REAL)
    assert isinstance(got, str) and rb.is_hard_stop(got)


@pytest.mark.parametrize("code", [None, 0, 500, 503, 302, 400])
def test_unreadable_answers_are_unread_not_permission(code: int | None) -> None:
    got = rb.robots_rules_or_refusal(code, "text/plain", REAL)
    assert isinstance(got, str) and got.startswith(rb.UNREAD)


@pytest.mark.parametrize("code", [404, 410])
def test_missing_file_means_empty_rules(code: int) -> None:
    got = rb.robots_rules_or_refusal(code, "text/html", "<html>not found</html>")
    assert isinstance(got, urllib.robotparser.RobotFileParser)
    assert got.can_fetch("anybot", "https://h/anything")


def test_a_real_robots_file_still_parses() -> None:
    for ctype in ("text/plain; charset=utf-8", None, ""):
        got = rb.robots_rules_or_refusal(200, ctype, REAL)
        assert isinstance(got, urllib.robotparser.RobotFileParser)
        assert got.can_fetch("anybot", "https://h/public/x")
        assert not got.can_fetch("anybot", "https://h/private/x")
    assert not rb.is_html_body(REAL) and not rb.is_html_body("") and not rb.is_html_body(None)


def test_deny_all_refuses_everything() -> None:
    assert not rb.deny_all().can_fetch("anybot", "https://h/")


# --------------------------------------------------------------------------- index_discovery
def _idx(monkeypatch: pytest.MonkeyPatch, opener: Any) -> Any:
    _desk_path()
    import index_discovery as idx  # type: ignore[import-not-found]
    monkeypatch.setattr(idx, "_ROBOTS", {})
    monkeypatch.setattr(idx.urllib.request, "urlopen", opener)
    return idx


def test_index_discovery_html_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    idx = _idx(monkeypatch, _opener(HTML_BODIES["head"]))
    assert idx.robots_refusal("https://h.example/page")


def test_index_discovery_html_content_type_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    idx = _idx(monkeypatch, _opener(REAL, ctype="text/html"))
    assert idx.robots_refusal("https://h.example/public")


@pytest.mark.parametrize("code", [401, 403, 429, 451])
def test_index_discovery_hard_stops(monkeypatch: pytest.MonkeyPatch, code: int) -> None:
    idx = _idx(monkeypatch, _opener(status=code))
    assert idx.robots_refusal("https://h.example/page")


@pytest.mark.parametrize("code", [404, 410])
def test_index_discovery_missing_file_allows(monkeypatch: pytest.MonkeyPatch, code: int) -> None:
    idx = _idx(monkeypatch, _opener(status=code))
    assert idx.robots_refusal("https://h.example/page") is None


def test_index_discovery_real_file_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    idx = _idx(monkeypatch, _opener(REAL))
    assert idx.robots_refusal("https://h.example/public") is None
    assert idx.robots_refusal("https://h.example/private/x")


# --------------------------------------------------------------------------- futures_state
def test_futures_state_html_is_not_a_yes() -> None:
    _desk_path()
    import futures_state as fs  # type: ignore[import-not-found]
    assert fs.robots_allow("https://h/x", lambda _u: HTML_BODIES["comment"]) is False
    assert fs.robots_allow("https://h/public", lambda _u: REAL) is True
    assert fs.robots_allow("https://h/private/x", lambda _u: REAL) is False

    def _err(code: int) -> Any:
        def _get(u: str) -> str:
            raise fs.FetchError(code, u, f"HTTP {code}")
        return _get
    assert fs.robots_allow("https://h/x", _err(404)) is True
    assert fs.robots_allow("https://h/x", _err(503)) is False

    def _stop(u: str) -> str:
        raise fs.HardStop(403, u)
    with pytest.raises(fs.HardStop):           # a refusal propagates as a hard stop
        fs.robots_allow("https://h/x", _stop)


# --------------------------------------------------------------------------- paid_substitute_engine
def test_paid_substitute_html_and_refusals_do_not_allow() -> None:
    _desk_path()
    import paid_substitute_engine as pse  # type: ignore[import-not-found]

    def _ok(status: int | None, body: str = "") -> tuple[bool, dict[str, Any]]:
        cache: dict[str, Any] = {}
        ok = pse._robots_ok("https://h.example/x", lambda _u: (status, body), cache)
        return ok, cache

    ok, cache = _ok(200, HTML_BODIES["doctype"])
    assert not ok and pse._robots_unreachable("https://h.example/x", cache)
    for code in (401, 403, 429, 451):
        ok, cache = _ok(code)
        assert not ok, code
        assert not pse._robots_unreachable("https://h.example/x", cache), "a refusal, counted"
    for code in (404, 410):
        assert _ok(code)[0], code
    assert not _ok(None)[0] and not _ok(503)[0]
    assert _ok(200, "User-agent: *\nDisallow: /nope/\n")[0]
    assert not _ok(200, "User-agent: *\nDisallow: /\n")[0]


# --------------------------------------------------------------------------- seed_miners
def test_seed_miners_wall_stands_on_html(monkeypatch: pytest.MonkeyPatch) -> None:
    _desk_path()
    import seed_miners as sm  # type: ignore[import-not-found]
    monkeypatch.setattr(sm, "fetch", lambda _u, *a, **k: HTML_BODIES["body"])
    assert sm._robots_still_disallows("h.example", "ClaudeBot") is True
    monkeypatch.setattr(sm, "fetch", lambda _u, *a, **k: "User-agent: *\nDisallow: /x\n")
    assert sm._robots_still_disallows("h.example", "ClaudeBot") is False
    monkeypatch.setattr(sm, "fetch", lambda _u, *a, **k: "User-agent: ClaudeBot\nDisallow: /\n")
    assert sm._robots_still_disallows("h.example", "ClaudeBot") is True


# --------------------------------------------------------------------------- civilization (label)
def test_civilization_html_is_never_labelled_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    _desk_path()
    import moat_collectors as mc  # type: ignore[import-not-found]
    from archaeology import civilization as civ  # type: ignore[import-not-found]
    from archaeology import snapshots as snap
    monkeypatch.setattr(mc, "fetch_text", lambda _u, *a, **k: (HTML_BODIES["xml"], 200, ""))
    verdict, why = civ._machine_use_from_robots("https://h.example/x", fetch=True)
    assert verdict == snap.UNKNOWN and "HTML" in why
    monkeypatch.setattr(mc, "fetch_text", lambda _u, *a, **k: (REAL, 200, ""))
    assert civ._machine_use_from_robots("https://h.example/x", fetch=True)[0] == snap.ALLOWED


# --------------------------------------------------------------------------- shadow_institutional
def test_shadow_institutional_label_never_claims_html_allows(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _desk_path()
    import shadow_institutional as si  # type: ignore[import-not-found]

    def _guard(opener: Any) -> Any:
        monkeypatch.setattr(si.urllib.request, "urlopen", opener)
        return si.Guard(budget_s=5.0, no_fetch=False, fixtures=tmp_path)

    ok, why = _guard(_opener(HTML_BODIES["html"])).robots_ok("https://h.example/x")
    assert "allows" not in why and "UNMEASURED" in why
    for code in (401, 403, 429, 451):
        ok, why = _guard(_opener(status=code)).robots_ok("https://h.example/x")
        assert ok is False and "HARD_STOP" in why, code
    ok, why = _guard(_opener(status=404)).robots_ok("https://h.example/x")
    assert ok is True
    g = _guard(_opener(REAL))
    assert g.robots_ok("https://h.example/public")[0] is True
    assert g.robots_ok("https://h.example/private/x")[0] is False


# --------------------------------------------------------------------------- AQR one-off fetcher
def _aqr(monkeypatch: pytest.MonkeyPatch, opener: Any) -> Any:
    import importlib.util
    path = _ROOT / "data" / "external" / "aqr" / "fetch_article_pdfs.py"
    spec = importlib.util.spec_from_file_location("_aqr_fetch_article_pdfs", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod.urllib.request, "urlopen", opener)
    mod._robots_rules.cache_clear()
    return mod


def test_aqr_homepage_in_place_of_robots_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    # The recorded case: /robots.txt 302s to the homepage, which urlopen follows to HTML 200.
    mod = _aqr(monkeypatch, _opener(HTML_BODIES["doctype"], ctype="text/html; charset=utf-8"))
    assert mod.robots_refusal("https://www.aqr.com/-/media/x.pdf")
    for code in (403, 451):
        mod = _aqr(monkeypatch, _opener(status=code))
        assert mod.robots_refusal("https://www.aqr.com/-/media/x.pdf"), code
    mod = _aqr(monkeypatch, _opener(status=404))
    assert mod.robots_refusal("https://www.aqr.com/-/media/x.pdf") is None
