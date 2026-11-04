"""polite_fetch is honest at the source (auditor ruling 2026-10-14).

No caller can make it send a browser User-Agent; robots.txt for the exact origin decides every
request and every redirect hop; unreadable robots means no fetch; 401/403/429 are a hard stop
recorded for the site, never retried and never routed around. Every test runs on a fake opener
that records what was actually sent -- no socket is opened.
"""
from __future__ import annotations

import io
import json
import sys
import urllib.error
from email.message import Message
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_DESK), str(_DESK / "side_channels"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import regional_survivor_hunters as rsh  # noqa: E402

from libs.data import polite_fetch as pf  # noqa: E402
from research import deep_forest_miner as dfm  # noqa: E402

_ALLOW = (200, b"User-agent: *\nDisallow:\n", "")
_HTML = b"<html><body>EURUSD carry</body></html>"
_CHROME = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
           "Chrome/126.0 Safari/537.36")


class _Resp(io.BytesIO):
    def __init__(self, body: bytes, ctype: str) -> None:
        super().__init__(body)
        self.status = 200
        self.url = ""
        self.headers = {"Content-Type": ctype}

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *a: object) -> bool:
        return False


class _Web:
    """URL -> (status, body, location). Unlisted URLs are a network error. Records every request
    with the User-Agent it actually carried."""

    def __init__(self, routes: dict[str, tuple[int, bytes, str]],
                 headers: dict[str, dict[str, str]] | None = None) -> None:
        self.routes = routes
        self.headers = headers or {}
        self.sent: list[tuple[str, str]] = []

    def __call__(self, req: Any, timeout: float, context: Any = None) -> _Resp:
        url = req.full_url
        self.sent.append((url, str(req.get_header("User-agent"))))
        if url not in self.routes:
            raise urllib.error.URLError("no route in fixture")
        status, body, loc = self.routes[url]
        if status == 200:
            return _Resp(body, "text/plain" if url.endswith("/robots.txt") else "text/html")
        hdrs = Message()
        if loc:
            hdrs["Location"] = loc
        for k, v in self.headers.get(url, {}).items():
            hdrs[k] = v
        raise urllib.error.HTTPError(url, status, "fixture", hdrs, io.BytesIO(body))

    def urls(self) -> list[str]:
        return [u for u, _ in self.sent]


def _get(web: _Web, url: str, acc: pf.HostAccess | None = None, **kw: Any) -> pf.Response:
    return pf.get(url, opener=web, gate=None, sleep=lambda s: None,
                  access=acc or pf.HostAccess(path=None), **kw)


# ---------------------------------------------------------------------------- honest identity
@pytest.mark.parametrize("hdr", [{"User-Agent": _CHROME}, {"user-agent": _CHROME},
                                 {"USER-AGENT": "Mozilla/5.0 Gecko/20100101 Firefox/128.0"},
                                 {"User-Agent": "Mozilla/5.0 ... Edg/126.0"}, None])
def test_no_caller_can_make_polite_fetch_send_a_browser_ua(hdr: dict[str, str] | None) -> None:
    web = _Web({"https://a.test/robots.txt": _ALLOW, "https://a.test/p": (200, _HTML, "")})
    r = _get(web, "https://a.test/p", headers=hdr)
    assert r.ok and web.sent
    for _, ua in web.sent:
        assert ua == pf.DESK_UA, ua
        assert not pf.looks_like_browser(ua)


def test_an_honest_caller_ua_is_kept() -> None:
    web = _Web({"https://a.test/robots.txt": _ALLOW, "https://a.test/p": (200, _HTML, "")})
    _get(web, "https://a.test/p", headers={"User-Agent": "quant-desk research ops@example.invalid"})
    assert web.sent[-1][1] == "quant-desk research ops@example.invalid"


def test_the_browser_constants_are_gone() -> None:
    assert not hasattr(pf, "BROWSER_UA") and not hasattr(pf, "BROWSER_HEADERS")
    assert not pf.looks_like_browser(pf.DESK_HEADERS["User-Agent"])


def test_the_importers_declare_the_desk_ua() -> None:
    assert rsh.HEADERS["User-Agent"] == pf.DESK_UA
    assert dfm._UA["User-Agent"] == pf.DESK_UA


# ------------------------------------------------------------------------------------ robots
# LAWS 5e (live): robots.txt is an ACCESS LABEL, never a refusal. "robots.txt Disallow treated as
# a refusal" is in access_classifier.REMOVED_BRAKES, and ACCESS_UNCLEAR is mined with its label.
def test_robots_disallow_is_fetched_and_labelled_public_with_terms() -> None:
    web = _Web({"https://a.test/robots.txt": (200, b"User-agent: *\nDisallow: /private\n", ""),
                "https://a.test/private/x": (200, _HTML, "")})
    r = _get(web, "https://a.test/private/x")
    assert r.ok and r.verdict == "" and r.status == 200
    assert "https://a.test/private/x" in web.urls()
    assert r.access_label == "PUBLIC_WITH_TERMS"
    assert "Disallow" in r.terms_note and r.redistribute_allowed is False


def test_a_group_naming_the_desk_token_labels_it() -> None:
    web = _Web({"https://a.test/robots.txt": (
        200, f"User-agent: {pf.DESK_UA_PRODUCT}\nDisallow: /\n\nUser-agent: *\nAllow: /\n".encode(),
        ""), "https://a.test/p": (200, _HTML, "")})
    r = _get(web, "https://a.test/p")
    assert r.ok and r.access_label == "PUBLIC_WITH_TERMS"
    assert "https://a.test/p" in web.urls()


@pytest.mark.parametrize("robots", [None, (500, b"", ""), (503, b"", "")])
def test_unreadable_robots_is_fetched_as_access_unclear(
        robots: tuple[int, bytes, str] | None) -> None:
    routes = {"https://a.test/p": (200, _HTML, "")}
    if robots is not None:
        routes["https://a.test/robots.txt"] = robots
    web = _Web(routes)
    r = _get(web, "https://a.test/p")
    assert r.ok and r.verdict == ""
    assert r.access_label == "ACCESS_UNCLEAR" and r.redistribute_allowed is False
    assert "https://a.test/p" in web.urls()


@pytest.mark.parametrize("code", [404, 410])
def test_a_missing_robots_allows(code: int) -> None:
    web = _Web({"https://a.test/robots.txt": (code, b"", ""), "https://a.test/p": (200, _HTML, "")})
    r = _get(web, "https://a.test/p")
    assert r.ok and r.access_label == "PUBLIC" and r.terms_note == ""


def test_the_label_reaches_the_leg_stats_and_the_ledger(tmp_path: Path) -> None:
    """The label is carried on what the fetch records: the leg's stats row and the shared
    access ledger's `labelled` rows (saved, so another process reads it)."""
    web = _Web({"https://a.test/robots.txt": (200, b"User-agent: *\nDisallow: /private\n", ""),
                "https://a.test/private/x": (200, _HTML, ""),
                "https://a.test/open": (200, _HTML, "")})
    acc = pf.HostAccess(path=tmp_path / "access.json")
    pf.reset_stats("label_leg")
    _get(web, "https://a.test/private/x", acc, leg="label_leg")
    _get(web, "https://a.test/open", acc, leg="label_leg")
    row = pf.stats("label_leg")
    assert row["access_labels"] == {"PUBLIC": 1, "PUBLIC_WITH_TERMS": 1}
    assert row["labelled"][0]["origin"] == "https://a.test"
    assert row["labelled"][0]["access_label"] == "PUBLIC_WITH_TERMS"
    disk = json.loads((tmp_path / "access.json").read_text("utf-8"))
    lab = disk["labelled"]["https://a.test"]
    assert lab["access_label"] == "PUBLIC_WITH_TERMS" and lab["fetched"] is True
    assert acc.summary()["access_labels"] == {"PUBLIC": 1, "PUBLIC_WITH_TERMS": 1}
    assert pf.HostAccess.load(tmp_path / "access.json").labelled["https://a.test"][
        "access_label"] == "PUBLIC_WITH_TERMS"


def test_the_seams_carry_the_label() -> None:
    web = _Web({"https://a.test/robots.txt": (200, b"User-agent: *\nDisallow: /\n", ""),
                "https://a.test/p": (200, _HTML, "")})
    acc = pf.HostAccess(path=None)
    with pf.polite_urlopen("https://a.test/p", access=acc, opener=web) as fh:
        assert fh.access_label == "PUBLIC_WITH_TERMS" and fh.redistribute_allowed is False
    r = pf.polite_requests_get("https://a.test/p", access=acc, opener=web)
    assert r.ok and r.access_label == "PUBLIC_WITH_TERMS" and "Disallow" in r.terms_note


def test_robots_is_cached_per_origin_for_24h() -> None:
    web = _Web({"https://a.test/robots.txt": _ALLOW, "https://a.test/p": (200, _HTML, ""),
                "https://a.test/q": (200, _HTML, "")})
    acc = pf.HostAccess(path=None)
    _get(web, "https://a.test/p", acc)
    _get(web, "https://a.test/q", acc)
    assert web.urls().count("https://a.test/robots.txt") == 1
    assert pf.ROBOTS_TTL_S == 24 * 3600


def test_a_redirect_to_another_origin_is_labelled_by_that_origins_robots() -> None:
    web = _Web({"https://a.test/robots.txt": _ALLOW,
                "https://a.test/go": (302, b"", "https://b.test/landing"),
                "https://b.test/robots.txt": (200, b"User-agent: *\nDisallow: /\n", ""),
                "https://b.test/landing": (200, _HTML, "")})
    r = _get(web, "https://a.test/go")
    assert r.ok and r.verdict == "" and r.access_label == "PUBLIC_WITH_TERMS"
    assert "https://b.test/robots.txt" in web.urls()
    assert "https://b.test/landing" in web.urls()


def test_a_permitted_redirect_is_followed_after_its_robots_check() -> None:
    web = _Web({"https://a.test/robots.txt": _ALLOW,
                "https://a.test/go": (301, b"", "https://b.test:8443/landing"),
                "https://b.test:8443/robots.txt": _ALLOW,
                "https://b.test:8443/landing": (200, _HTML, "")})
    r = _get(web, "https://a.test/go")
    assert r.ok and r.text.startswith("<html>")
    urls = web.urls()
    assert urls.index("https://b.test:8443/robots.txt") < urls.index("https://b.test:8443/landing")


# ------------------------------------------------------------------------------- hard stops
@pytest.mark.parametrize(("status", "verdict"),
                         [(401, "NEEDS_KEY"), (403, "METHOD_BLOCKED"), (429, "METHOD_BLOCKED")])
def test_a_refusal_stops_the_fetch_with_no_retry_and_no_other_route(status: int,
                                                                     verdict: str) -> None:
    web = _Web({"https://www.a.test/robots.txt": _ALLOW,
                "https://www.a.test/p": (status, b"", ""),
                "https://old.a.test/robots.txt": _ALLOW,
                "https://old.a.test/p": (200, _HTML, "")})
    acc = pf.HostAccess(path=None)
    r = _get(web, "https://www.a.test/p", acc, retries=5)
    assert not r.ok and r.status == status and r.verdict == verdict and r.attempts == 1
    assert web.urls().count("https://www.a.test/p") == 1, "a refused request was retried"
    n = len(web.sent)
    r2 = _get(web, "https://old.a.test/p", acc, retries=5)   # a sibling host: an alternate route
    assert not r2.ok and r2.verdict == verdict and len(web.sent) == n
    assert acc.blocked["a.test"]["status"] == status
    assert pf.stats("default")["refused"] >= 1


def test_a_refusal_is_persisted_for_the_next_process(tmp_path: Path) -> None:
    state = tmp_path / "access.json"
    web = _Web({"https://a.test/robots.txt": _ALLOW, "https://a.test/p": (403, b"", "")})
    _get(web, "https://a.test/p", pf.HostAccess.load(state))
    again = pf.HostAccess.load(state)
    assert again.hold("https://a.test/other") == "METHOD_BLOCKED"


def test_regional_hunter_stops_a_source_on_a_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    tried: list[str] = []

    def fake(url: str, timeout: float = 0, *, referer: str = "", accept_json: bool = False) -> str:
        tried.append(url)
        raise rsh.FetchError(url, 403, "METHOD_BLOCKED: HTTP 403", "METHOD_BLOCKED")

    monkeypatch.setattr(rsh, "fetch", fake)
    out = rsh.mine_source("hfm_pamm", rsh.SOURCES["hfm_pamm"], 1)
    assert out["state"] == "refused:METHOD_BLOCKED" and len(tried) == 1, tried


# ------------------------------------------- auditor follow-ups on 1e8cca2ac (2026-10-14)
#: A real Cloudflare interstitial is recognised by its MARKUP (the challenge bootstrap), not by
#: its title text: the words alone also appear in ordinary forum posts.
_CHALLENGE = (b"<!DOCTYPE html><html><head><title>Just a moment...</title></head><body>"
              b"<script>window._cf_chl_opt={cvId:'3'};</script>"
              b"<script src='/cdn-cgi/challenge-platform/h/b/orchestrate/chl_page/v1'></script>"
              b"</body></html>")


def test_a_crawl_delay_larger_than_the_gap_is_obeyed() -> None:
    web = _Web({"https://a.test/robots.txt": (200, b"User-agent: *\nCrawl-delay: 7\n", ""),
                "https://a.test/p": (200, _HTML, ""), "https://a.test/q": (200, _HTML, "")})
    gate = pf.HostGate(default_s=0.1)
    slept: list[float] = []
    acc = pf.HostAccess(path=None)
    for u in ("https://a.test/p", "https://a.test/q"):
        r = pf.get(u, opener=web, gate=gate, sleep=slept.append, access=acc)
        assert r.ok
    assert slept and max(slept) > 6.5, slept


def test_a_challenge_page_as_robots_is_a_hold_and_nothing_is_fetched() -> None:
    web = _Web({"https://a.test/robots.txt": (200, _CHALLENGE, ""),
                "https://a.test/p": (200, _HTML, "")})
    acc = pf.HostAccess(path=None)
    r = _get(web, "https://a.test/p", acc)
    assert not r.ok and r.verdict == "METHOD_BLOCKED"
    assert "https://a.test/p" not in web.urls()
    row = acc.blocked["a.test"]
    assert row["verdict"] == "METHOD_BLOCKED" and row["status"] == "WAF"
    assert row["missed_growth"]["delta_elogw"] == "UNMEASURED" and row["missed_growth"]["cause"]


def test_a_soft_404_html_robots_means_allow_per_rfc9309() -> None:
    """P7: an HTML page served as robots.txt has no parseable rules, so it allows (RFC 9309), as a
    real 404 does -- it never holds the site or re-holds it every 24h."""
    web = _Web({"https://a.test/robots.txt": (200, b"<html><body>Not found</body></html>", ""),
                "https://a.test/p": (200, _HTML, "")})
    acc = pf.HostAccess(path=None)
    r = _get(web, "https://a.test/p", acc)
    assert r.ok and "https://a.test/p" in web.urls() and not acc.blocked


def test_unparseable_robots_lines_are_ignored_not_held() -> None:
    web = _Web({"https://a.test/robots.txt": (200, b"\x00\xff garbage ;;\nnot a rule\n", ""),
                "https://a.test/p": (200, _HTML, "")})
    acc = pf.HostAccess(path=None)
    assert _get(web, "https://a.test/p", acc).ok and not acc.blocked


def test_a_cloudflare_503_challenge_is_held_and_never_retried() -> None:
    """P4: a 503 carrying the challenge (markup or `cf-mitigated`) is a refusal, not a 'come back
    later': one request, a WAF hold for the site, no retry."""
    for body, hdr in ((_CHALLENGE, {}), (b"", {"cf-mitigated": "challenge"})):
        web = _Web({"https://a.test/robots.txt": _ALLOW, "https://a.test/p": (503, body, "")},
                   headers={"https://a.test/p": hdr})
        acc = pf.HostAccess(path=None)
        r = _get(web, "https://a.test/p", acc, retries=3)
        assert r.verdict == "METHOD_BLOCKED" and r.text == ""
        assert web.urls().count("https://a.test/p") == 1
        assert acc.blocked["a.test"]["status"] == "WAF"


def test_a_plain_503_is_still_retried() -> None:
    web = _Web({"https://a.test/robots.txt": _ALLOW,
                "https://a.test/p": (503, b"<html>maintenance</html>", "")})
    acc = pf.HostAccess(path=None)
    r = _get(web, "https://a.test/p", acc, retries=2)
    assert not r.ok and not r.verdict and web.urls().count("https://a.test/p") == 3
    assert not acc.blocked


def test_forum_prose_about_a_challenge_is_content_not_a_hold() -> None:
    """P6: words a person can type are not a challenge."""
    post = (b"<html><head><title>Gold forum</title></head><body><p>Just a moment... checking "
            b"your browser, access denied, are you a robot? XAUUSD fades London.</p></body></html>")
    web = _Web({"https://a.test/robots.txt": _ALLOW, "https://a.test/t/1": (200, post, "")})
    acc = pf.HostAccess(path=None)
    r = _get(web, "https://a.test/t/1", acc)
    assert r.ok and "XAUUSD" in r.text and not acc.blocked


def test_cloudflares_passive_script_on_a_200_is_not_a_challenge() -> None:
    page = (b"<html><body>EURUSD carry<script src='/cdn-cgi/challenge-platform/scripts/jsd/"
            b"main.js'></script></body></html>")
    assert pf.looks_challenged(page, {}, 200) == ""
    assert pf.looks_challenged(page, {}, 503) != ""
    assert pf.looks_challenged(b"", {"CF-Mitigated": "challenge"}, 403) != ""


@pytest.mark.parametrize("ua", ["Googlebot/2.1 (+http://www.google.com/bot.html)",
                                "Opera/9.80 (Windows NT 6.1) Presto/2.12.388 Version/12.16",
                                "Mozilla/5.0 (compatible; bingbot/2.0)", "Baiduspider",
                                "Mozilla/5.0 AppleWebKit/537.36 OPR/110.0"])
def test_crawler_and_opera_impersonation_is_replaced(ua: str) -> None:
    """P5: another company's crawler name is impersonation exactly as a browser string is."""
    assert pf.honest_headers({"User-Agent": ua})["User-Agent"] == pf.DESK_UA


def test_a_challenge_page_as_content_is_held_and_not_ingested() -> None:
    web = _Web({"https://a.test/robots.txt": _ALLOW, "https://a.test/p": (200, _CHALLENGE, ""),
                "https://a.test/q": (200, _HTML, "")})
    acc = pf.HostAccess(path=None)
    r = _get(web, "https://a.test/p", acc)
    assert not r.ok and r.text == "" and r.verdict == "METHOD_BLOCKED"
    assert acc.hold("https://a.test/q") == "METHOD_BLOCKED"
    n = len(web.sent)
    assert not _get(web, "https://a.test/q", acc).ok and len(web.sent) == n


def test_a_github_io_tenants_refusal_does_not_hold_its_neighbour() -> None:
    web = _Web({"https://a.github.io/robots.txt": _ALLOW,
                "https://a.github.io/p": (403, b"", ""),
                "https://b.github.io/robots.txt": _ALLOW,
                "https://b.github.io/p": (200, _HTML, "")})
    acc = pf.HostAccess(path=None)
    assert _get(web, "https://a.github.io/p", acc).verdict == "METHOD_BLOCKED"
    assert _get(web, "https://b.github.io/p", acc).ok
    assert pf.site_of("x.blogspot.com") != pf.site_of("y.blogspot.com")
    assert pf.site_of("a.lausd.k12.ca.us") != pf.site_of("b.sfusd.k12.ca.us")
    assert pf.site_of("www.example.co.uk") == pf.site_of("old.example.co.uk") == "example.co.uk"


def test_an_ip_is_held_by_its_full_host() -> None:
    web = _Web({"http://10.1.2.3/robots.txt": _ALLOW, "http://10.1.2.3/p": (403, b"", ""),
                "http://10.9.2.3/robots.txt": _ALLOW, "http://10.9.2.3/p": (200, _HTML, "")})
    acc = pf.HostAccess(path=None)
    _get(web, "http://10.1.2.3/p", acc)
    assert "10.1.2.3" in acc.blocked and pf.site_of("10.1.2.3") == "10.1.2.3"
    assert _get(web, "http://10.9.2.3/p", acc).ok


# ------------------------------------------- auditor follow-ups on 0ca783b1f (2026-10-14)
def test_regional_robots_disallow_on_one_path_does_not_stop_allowed_alternates(
        monkeypatch: pytest.MonkeyPatch) -> None:
    tried: list[str] = []
    alt = rsh.ALTERNATES["hfm_pamm"][0]

    def fake(url: str, timeout: float = 0, *, referer: str = "", accept_json: bool = False) -> str:
        tried.append(url)
        if url == alt:
            return "<html><body>nothing listed</body></html>"
        raise rsh.FetchError(url, None, "ROBOTS_DISALLOW", "ROBOTS_DISALLOW")

    monkeypatch.setattr(rsh, "fetch", fake)
    out = rsh.mine_source("hfm_pamm", rsh.SOURCES["hfm_pamm"], 1)
    assert alt in tried and len(tried) > 1, tried
    assert not str(out["state"]).startswith("refused")
    assert "ROBOTS_DISALLOW" not in rsh.HARD_STOP and "ROBOTS_UNREADABLE" not in rsh.HARD_STOP
    assert {"NEEDS_KEY", "METHOD_BLOCKED"} <= rsh.HARD_STOP


def test_wayback_never_reads_a_held_sites_archive(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace
    acc = pf.HostAccess(path=None)
    acc.block("https://forum.held.test/x", 403)
    monkeypatch.setattr(pf, "default_access", lambda: acc)
    asked: list[str] = []
    monkeypatch.setattr(dfm, "wayback_snapshot", lambda u, ts="": (asked.append(u) or ("", "x")))
    stub = SimpleNamespace(status=[], _note_net=lambda ok: None)
    out = dfm._Run.ground_wayback(stub, {"url": "https://www.held.test/forum", "name": "w"})
    assert out["refused"] == "METHOD_BLOCKED" and out["fetched"] == 0 and asked == []


def test_access_holds_are_counted_by_missed_growth(tmp_path: Path) -> None:
    from research import missed_growth as mg
    state = tmp_path / "access.json"
    acc = pf.HostAccess.load(state)
    acc.block("https://a.test/p", 403)
    acc.block("https://b.test/p", 429)
    out = mg.access_hold_lines(state)
    assert out["n_held"] == 2 and out["verdict"] == mg.UNMEASURED
    assert {x["source"] for x in out["lines"]} == {"a.test", "b.test"}
    assert all(x["delta_elogw"] == "UNMEASURED" and x["cause"] for x in out["lines"])
    later = mg.access_hold_lines(state, now=acc.now() + 400 * 86400)
    assert {x["source"] for x in later["lines"]} == {"a.test", "b.test"}, "a hold lapsed"
    pf.release("site:b.test", "principal", path=state)
    after = mg.access_hold_lines(state)
    assert {x["source"] for x in after["lines"]} == {"a.test"}
    assert mg.access_hold_lines(tmp_path / "absent.json")["verdict"] == mg.UNMEASURED


def test_zenn_403_holds_the_site_and_never_switches_ua(monkeypatch: pytest.MonkeyPatch) -> None:
    """The R0466 path: zenn.dev 403s the named agent. The answer is a hold, not a disguise."""
    from libs.data import foreign_sources as fsrc
    web = _Web({"https://zenn.dev/robots.txt": _ALLOW})
    original = web.__call__

    def opener(req: Any, timeout: float, context: Any = None) -> Any:
        if "/api/articles" in req.full_url:
            web.sent.append((req.full_url, str(req.get_header("User-agent"))))
            raise urllib.error.HTTPError(req.full_url, 403, "x", Message(), io.BytesIO(b""))
        return original(req, timeout, context)

    acc = pf.HostAccess(path=None)
    real_get = pf.get
    monkeypatch.setattr(pf, "get", lambda url, **kw: real_get(
        url, **{**kw, "opener": opener, "access": acc, "gate": None, "sleep": lambda s: None}))
    monkeypatch.setattr(fsrc, "_pace", lambda s: None)
    fsrc._BACKED_OFF.discard("zenn")
    rows, err = fsrc.zenn("carry")
    assert rows == [] and err and "METHOD_BLOCKED" in err
    assert acc.hold("https://zenn.dev/anything") == "METHOD_BLOCKED"
    assert all(ua == pf.DESK_UA for _, ua in web.sent)
    assert "zenn" in fsrc._BACKED_OFF
    fsrc._BACKED_OFF.discard("zenn")


@pytest.mark.parametrize("mod", ["cn_sources", "papers", "bilibili", "foreign_sources"])
def test_the_priority_libs_send_the_desk_ua_through_polite_fetch(mod: str) -> None:
    import importlib
    m = importlib.import_module(f"libs.data.{mod}")
    assert m._UA["User-Agent"] == pf.DESK_UA
    src = Path(m.__file__ or "").read_text("utf-8")
    assert "urlopen(" not in src and "_pf.get_text(" in src
