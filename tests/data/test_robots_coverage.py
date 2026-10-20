"""ROBOTS.TXT IS RESPECTED DESK-WIDE (LAWS 5e as amended by the principal, 2026-10-14).

Every scraping-shaped organ Breadth listed (reports/robots_noncompliant_fetchers_2026-10-14.txt)
now consults the site's holds and the URL's own origin robots.txt through THE ONE implementation,
`libs.data.polite_fetch.HostAccess` (robots via the `DESK_UA_PRODUCT` group, else `*`, longest
match; 5xx/unreachable = no fetch; 404 = allow; 401/403/429 = a hold). These tests run each
fixed organ against a loopback server and count the PAGE requests that reached it:

* a `Disallow` at the exact path      -> zero page requests, for every organ;
* a 404 robots.txt                    -> the page is fetched (RFC 9309: no rules);
* a 503 robots.txt                    -> zero page requests (unreadable is not consent);
* a 429 page                          -> held: the next call sends nothing.

No test leaves the loopback interface, and the shared access record is a tmp file.
"""
from __future__ import annotations

import http.server
import json
import sys
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research"), str(DESK / "side_channels")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import polite_fetch as pf  # noqa: E402

DISALLOW = b"User-agent: *\nDisallow: /blocked\n"


class _H(http.server.BaseHTTPRequestHandler):
    robots: ClassVar[tuple[int, bytes]] = (200, DISALLOW)
    page_status: ClassVar[int] = 200
    pages: ClassVar[list[str]] = []
    robots_reads: ClassVar[list[str]] = []

    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/robots.txt":
            _H.robots_reads.append(self.path)
            self._send(self.robots[0], self.robots[1], "text/plain")
            return
        _H.pages.append(self.path)
        self._send(self.page_status, b'{"ok": [1, 2, 3]}', "application/json")

    do_POST = do_GET

    def log_message(self, *_a: Any) -> None:
        return


@pytest.fixture
def web(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    for var in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("no_proxy", "*")
    monkeypatch.setenv("NO_PROXY", "*")
    # the shared access record is a tmp file; no per-host spacing between test requests
    monkeypatch.setattr(pf, "_ACCESS", pf.HostAccess(tmp_path / "access.json"))
    monkeypatch.setitem(pf.GATE.per_host, "127.0.0.1", 0.0)
    _H.robots, _H.page_status, _H.pages, _H.robots_reads = (200, DISALLOW), 200, [], []
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def _swallow(fn: Any) -> Any:
    try:
        return fn()
    except BaseException as exc:            # the organ's own refusal shape; the count decides
        if isinstance(exc, (KeyboardInterrupt, AssertionError)):
            raise
        return exc


# ---------------------------------------------------------------- the organs, one call each
def _sensor_kwargs(mod: Any, url: str) -> dict[str, Any]:
    return {"sensor_id": "robots_probe", "latent": "x", "what": "x", "fetch_class": "api",
            "source": "x", "cadence": "daily", "pit_lag_days": 0.0, "machine_use_allowed": True,
            "licence": "", "sign": 1, "consumers": (), "url": url}


def _organs() -> dict[str, Any]:
    """name -> f(url) that makes ONE fetch through that organ's own fetch path."""
    import alt_proxies
    import asia_collector
    import axis_ingest
    import data_acquisition_scientist as das
    import fetch_dukascopy
    import global_survivor_frontier as gsf
    import index_discovery
    import moat_collectors
    import repo_miner
    import seed_miners
    import shadow_institutional
    import world_dataset_hunter
    from archaeology import civilization
    from research.countries.br import data_plane as br

    from libs.data import cot_source, free_stack, prediction_markets
    from libs.research import public_strategy_hunter

    def req(u: str) -> urllib.request.Request:
        return urllib.request.Request(u, headers={"User-Agent": pf.DESK_UA})

    def dukascopy(u: str) -> Any:
        fetch_dukascopy.hour_url = lambda s, t: u              # type: ignore[assignment]
        return fetch_dukascopy.fetch_hour("EURUSD", datetime(2024, 1, 2, tzinfo=UTC), retries=1)

    return {
        "polite_urlopen": lambda u: pf.polite_urlopen(u, timeout=5).read(),
        "polite_requests_get": lambda u: pf.polite_requests_get(u, timeout=5),
        "PoliteSession": lambda u: pf.PoliteSession().get(u, timeout=5),
        "world_dataset_hunter.urllib_fetch": lambda u: world_dataset_hunter.urllib_fetch(u, 5),
        "free_stack.http_fetch": free_stack.http_fetch,
        "alt_proxies.http_get": alt_proxies.http_get,
        "axis_ingest._live_urlopen": lambda u: axis_ingest._live_urlopen(req(u), 5).read(),
        "cot_source._open": lambda u: cot_source._open(req(u), 5).read(),
        "index_discovery._get": lambda u: index_discovery._get(u, timeout=5),
        "global_survivor_frontier._get_text": lambda u: gsf._get_text(u, 5),
        "seed_miners.fetch": lambda u: seed_miners.fetch(u, timeout=5),
        "moat_collectors.fetch_bytes": moat_collectors.fetch_bytes,
        "asia_collector.collect_one": lambda u: asia_collector.collect_one(
            {"id": "robots_probe", "url": u, "expect": "json", "access": "public"}, timeout=5),
        "prediction_markets._get": lambda u: prediction_markets._get(u, tries=1),
        "br.http_get": lambda u: br.http_get(u, {}, 5),
        "fetch_dukascopy.fetch_hour": dukascopy,
        "repo_miner._get": lambda u: repo_miner._get(u, timeout=5),
        "public_strategy_hunter.fetch": lambda u: public_strategy_hunter.fetch(u, timeout=5),
        "shadow_institutional.Guard.get": lambda u: shadow_institutional.Guard(
            no_fetch=False).get(shadow_institutional.Sensor(**_sensor_kwargs(
                shadow_institutional, u))),
        "data_acquisition_scientist._robots_allows": das._robots_allows,
        "civilization._machine_use_from_robots": lambda u: civilization._machine_use_from_robots(
            u, fetch=True),
        "moat_collectors.robots_barred": moat_collectors.robots_barred,
    }


ORGANS = sorted(_organs())


@pytest.mark.parametrize("name", ORGANS)
def test_a_disallow_at_the_exact_path_sends_no_request(web: str, name: str) -> None:
    fn = _organs()[name]
    _swallow(lambda: fn(f"{web}/blocked/data.json"))
    assert _H.pages == [], (name, _H.pages)
    assert _H.robots_reads, f"{name} never read robots.txt"


@pytest.mark.parametrize("name", ["polite_urlopen", "asia_collector.collect_one",
                                  "world_dataset_hunter.urllib_fetch", "seed_miners.fetch",
                                  "index_discovery._get"])
def test_a_5xx_robots_is_no_fetch(web: str, name: str) -> None:
    _H.robots = (503, b"down")
    _swallow(lambda: _organs()[name](f"{web}/open/data.json"))
    assert _H.pages == [], (name, _H.pages)


@pytest.mark.parametrize("name", ["polite_urlopen", "global_survivor_frontier._get_text",
                                  "seed_miners.fetch", "index_discovery._get"])
def test_a_404_robots_allows(web: str, name: str) -> None:
    _H.robots = (404, b"not found")
    _swallow(lambda: _organs()[name](f"{web}/blocked/data.json"))
    assert _H.pages == ["/blocked/data.json"], (name, _H.pages)


def test_the_refusal_is_named_and_robots_checkers_say_no(web: str) -> None:
    import data_acquisition_scientist as das
    import moat_collectors
    from archaeology import civilization
    url = f"{web}/blocked/x"
    ok, why = pf.admit(url)
    assert not ok and why == "ROBOTS_DISALLOW"
    assert das._robots_allows(url)[0] is False
    assert moat_collectors.robots_barred(url)
    assert civilization._machine_use_from_robots(url, fetch=True)[1].startswith(
        civilization.ROBOTS_REFUSAL)
    with pytest.raises(pf.PoliteRefused) as info:
        pf.polite_urlopen(url, timeout=5)
    assert info.value.verdict == "ROBOTS_DISALLOW"
    r = pf.polite_requests_get(url, timeout=5)
    assert r.status_code == 0 and r.verdict == "ROBOTS_DISALLOW" and not r.ok
    assert _H.pages == []


def test_asia_collector_names_the_refusal_and_fetches_nothing(web: str) -> None:
    import asia_collector
    rec = asia_collector.collect_one({"id": "robots_probe", "url": f"{web}/blocked/a.json",
                                      "expect": "json", "access": "public"}, timeout=5)
    assert rec["status"] == "BLOCKED_BY_ROBOTS" and rec["robots_disallows"] is True
    assert _H.pages == []


def test_an_allowed_path_is_fetched_once(web: str) -> None:
    body = pf.polite_urlopen(f"{web}/open/data.json", timeout=5).read()
    assert json.loads(body) == {"ok": [1, 2, 3]}
    assert _H.pages == ["/open/data.json"]


def test_a_429_holds_the_site_and_the_next_call_sends_nothing(web: str) -> None:
    _H.page_status = 429
    with pytest.raises(urllib.error.HTTPError) as info:
        pf.polite_urlopen(f"{web}/open/a.json", timeout=5)
    assert info.value.code == 429
    assert _H.pages == ["/open/a.json"]
    with pytest.raises(pf.PoliteRefused):
        pf.polite_urlopen(f"{web}/open/b.json", timeout=5)
    assert _H.pages == ["/open/a.json"]                 # held: nothing further was sent


def test_a_keyed_url_is_admitted_and_its_hold_never_stores_the_key(web: str,
                                                                   tmp_path: Path) -> None:
    _H.page_status = 403
    url = f"{web}/open/series?series_id=X&api_key=SECRETVALUE123"
    with pytest.raises(urllib.error.HTTPError) as info:
        pf.polite_urlopen(url, timeout=5)
    assert "SECRETVALUE123" not in str(info.value.filename)
    state = (tmp_path / "access.json").read_text("utf-8")
    assert "SECRETVALUE123" not in state and "REDACTED" in state
    _H.robots = (200, b"User-agent: *\nDisallow: /blocked\n")
    with pytest.raises(pf.PoliteRefused):           # the 403 holds the site for a person
        pf.polite_urlopen(f"{web}/open/other", timeout=5)
    assert _H.pages == ["/open/series?series_id=X&api_key=SECRETVALUE123"]


def test_a_keyed_disallowed_url_sends_nothing(web: str) -> None:
    with pytest.raises(pf.PoliteRefused):
        pf.polite_urlopen(f"{web}/blocked/s?api_key=SECRETVALUE123", timeout=5)
    assert _H.pages == []


# ---------------------------------------------------------------- RFC 9309 matching
def test_longest_match_wins_over_file_order() -> None:
    rules = pf.parse_robots("User-agent: *\nAllow: /\nDisallow: /private\n")
    assert not rules.can_fetch(pf.DESK_UA_PRODUCT, "https://a.org/private/x")
    assert rules.can_fetch(pf.DESK_UA_PRODUCT, "https://a.org/public")
    rules = pf.parse_robots("User-agent: *\nDisallow: /\nAllow: /public\n")
    assert rules.can_fetch(pf.DESK_UA_PRODUCT, "https://a.org/public/page")
    assert not rules.can_fetch(pf.DESK_UA_PRODUCT, "https://a.org/other")


def test_a_tie_goes_to_allow_and_wildcards_match() -> None:
    rules = pf.parse_robots("User-agent: *\nDisallow: /a\nAllow: /a\nDisallow: /*.pdf$\n")
    assert rules.can_fetch(pf.DESK_UA_PRODUCT, "https://a.org/a")
    assert not rules.can_fetch(pf.DESK_UA_PRODUCT, "https://a.org/docs/x.pdf")
    assert rules.can_fetch(pf.DESK_UA_PRODUCT, "https://a.org/docs/x.pdf?y=1")


def test_the_product_group_is_used_before_star() -> None:
    txt = (f"User-agent: *\nDisallow: /\n\nUser-agent: {pf.DESK_UA_PRODUCT}\nAllow: /\n"
           "Disallow: /desk-only\nCrawl-delay: 4\n")
    rules = pf.parse_robots(txt)
    assert rules.can_fetch(pf.DESK_UA_PRODUCT, "https://a.org/page")
    assert not rules.can_fetch(pf.DESK_UA_PRODUCT, "https://a.org/desk-only/x")
    assert rules.crawl_delay(pf.DESK_UA_PRODUCT) == 4.0
    assert not rules.can_fetch("SomeOtherBot", "https://a.org/page")     # falls back to *


def test_another_agents_group_does_not_bind_the_desk() -> None:
    rules = pf.parse_robots("User-agent: GPTBot\nDisallow: /\n")
    assert rules.can_fetch(pf.DESK_UA_PRODUCT, "https://a.org/page")
    assert pf.parse_robots("").can_fetch(pf.DESK_UA_PRODUCT, "https://a.org/x")


def test_the_deep_forest_index_route_uses_the_one_parser() -> None:
    from research import deep_forest_miner as dfm
    rp = dfm.robots_parser("User-agent: *\nAllow: /\nDisallow: /private\n")
    assert isinstance(rp, pf.RobotsRules)
    assert not rp.can_fetch(pf.DESK_UA_PRODUCT, "https://a.org/private")


def test_no_second_robots_parser_in_non_test_code() -> None:
    """`urllib.robotparser` is read nowhere outside the tests: HostAccess/RobotsRules is the
    desk's only reader of robots.txt."""
    hits = []
    for p in list((ROOT / "libs").rglob("*.py")) + list((ROOT / "desks").rglob("*.py")) + list(
            (ROOT / "scripts").rglob("*.py")):
        if "/tests/" in p.as_posix() or p.name.startswith("test_"):
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        if any(m in txt for m in ("RobotFileParser(", "import robotparser",
                                  "import urllib.robotparser", "from urllib.robotparser")):
            hits.append(str(p.relative_to(ROOT)))
    assert hits == [], hits
