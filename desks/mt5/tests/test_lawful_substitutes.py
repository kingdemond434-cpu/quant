"""The lawful feeds behind the side channels whose own site may not be fetched (2026-11-19)."""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "side_channels"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import lawful_substitutes as ls  # noqa: E402


class _Resp:
    def __init__(self, status: int, body: Any = "") -> None:
        self.status_code = status
        self._body = body
        self.text = body if isinstance(body, str) else json.dumps(body)

    def json(self) -> Any:
        return self._body if not isinstance(self._body, str) else json.loads(self._body)


class _Web:
    """A fake web: robots per host, a body per URL prefix, and a log of every request."""

    def __init__(self, robots: dict[str, _Resp], pages: dict[str, _Resp]) -> None:
        self.robots, self.pages, self.log = robots, pages, []

    def __call__(self, url: str, params: Any = None, headers: Any = None, timeout: Any = None):
        self.log.append((url, dict(headers or {})))
        host = url.split("/")[2]
        if url.endswith("/robots.txt"):
            return self.robots.get(host, _Resp(404))
        for prefix, resp in self.pages.items():
            if url.startswith(prefix):
                return resp
        return _Resp(404)


def _feed(web: _Web) -> ls.Feed:
    return ls.Feed(web, pace_s=0.0)


def test_a_refused_or_unrecorded_host_is_never_contacted_robots_included() -> None:
    web = _Web({}, {})
    f = _feed(web)
    assert f.json("https://www.mql5.com/en/code") is None
    assert f.json("https://www.reddit.com/r/forex/hot.json") is None
    assert f.refused["www.mql5.com"].startswith("TERMS_REFUSED")
    assert f.refused["www.reddit.com"].startswith("TERMS_UNCONFIRMED")
    assert web.log == []


def test_robots_that_disallow_the_path_or_answer_html_or_an_error_refuse() -> None:
    web = _Web({"api.gdeltproject.org": _Resp(200, "User-agent: *\nDisallow: /api/"),
                "wikimedia.org": _Resp(200, "<!DOCTYPE html><p>hi"),
                "export.arxiv.org": _Resp(503, "")}, {})
    f = _feed(web)
    assert f.json("https://api.gdeltproject.org/api/v2/doc/doc") is None
    assert f.json("https://wikimedia.org/api/rest_v1/x") is None
    assert f.text("https://export.arxiv.org/api/query") is None
    assert f.refused["api.gdeltproject.org"] == (
        "ROBOTS_REFUSED: robots.txt disallows /api/v2/doc/doc")
    assert f.refused["wikimedia.org"] == "ROBOTS_REFUSED: robots.txt answered HTML"
    assert f.refused["export.arxiv.org"] == "ROBOTS_REFUSED: robots.txt answered 503"
    assert all(u.endswith("/robots.txt") for u, _ in web.log)


def test_every_request_carries_the_honest_agent_and_a_403_is_a_hard_stop() -> None:
    web = _Web({}, {"https://api.github.com/": _Resp(403, {})})
    f = _feed(web)
    assert f.json("https://api.github.com/search/repositories") is None
    assert f.refused["api.github.com"] == "HARD_STOP: HTTP 403"
    assert {h["User-Agent"] for _, h in web.log} == {ls.HONEST_UA}
    assert "Mozilla" not in ls.HONEST_UA


def test_sec_hosts_need_the_edgar_contact_and_never_send_without_it(monkeypatch) -> None:
    web = _Web({}, {"https://data.sec.gov/": _Resp(200, {})})
    monkeypatch.setattr(ls, "_edgar_ua", lambda: "")
    f = _feed(web)
    assert f.json("https://data.sec.gov/submissions/CIK0001350694.json") is None
    assert f.refused["data.sec.gov"].startswith("UNCONFIGURED") and web.log == []
    monkeypatch.setattr(ls, "_edgar_ua", lambda: "desk research contact@example.org")
    f = _feed(web)
    assert f.json("https://data.sec.gov/submissions/CIK0001350694.json") == {}
    assert {h["User-Agent"] for _, h in web.log} == {"desk research contact@example.org"}


def test_github_feed_keeps_only_repos_that_name_a_symbol_or_mechanism() -> None:
    items = [{"full_name": "a/xau-breakout", "description": "XAUUSD london open breakout",
              "html_url": "u1", "stargazers_count": 3},
             {"full_name": "b/todo", "description": "a todo app", "html_url": "u2"}]
    web = _Web({}, {"https://api.github.com/": _Resp(200, {"items": items})})
    rows = ls.github_code(_feed(web), "mql5_codebase", ("q",))
    assert [r["title"] for r in rows] == ["a/xau-breakout"]
    assert rows[0]["symbols"] == ["XAUUSD"] and "breakout" in rows[0]["patterns"]


def test_gdelt_wiki_portwatch_and_sec_feeds_parse_their_documented_shapes(monkeypatch) -> None:
    monkeypatch.setattr(ls, "_edgar_ua", lambda: "desk research contact@example.org")
    tone = {"timeline": [{"data": [{"value": -1.0}, {"value": -2.0}, {"value": -4.5}]}]}
    views = {"items": [{"views": 100}] * 23 + [{"views": 300}] * 7}
    port = {"features": [{"attributes": {"portname": "Suez Canal", "n_total": 40}}] * 7
            + [{"attributes": {"portname": "Suez Canal", "n_total": 60}}] * 14}
    subs = {"filings": {"recent": {"form": ["13F-HR", "4"], "filingDate": ["2026-11-14", "x"],
                                   "accessionNumber": ["0001-26-000001", "y"]}}}
    web = _Web({}, {
        "https://api.gdeltproject.org/": _Resp(200, tone),
        "https://wikimedia.org/": _Resp(200, views),
        "https://services9.arcgis.com/": _Resp(200, port),
        "https://data.sec.gov/": _Resp(200, subs)})
    f = _feed(web)
    t = ls.gdelt_tone(f, "fear_greed", ("recession",))
    assert t[0]["tone_last"] == -4.5 and t[0]["tone_delta"] < 0
    w = ls.wiki_attention(f, "reddit", {"Gold": ("XAUUSD",)})
    assert w[0]["attention_ratio"] == 3.0 and w[0]["symbols"] == ["XAUUSD"]
    p = ls.portwatch_chokepoints(f, "shipping")
    assert p[0]["port"] == "Suez Canal" and round(p[0]["transit_ratio"], 3) == round(40 / 60, 3)
    s = ls.sec_filings(f, "sec_edgar", ("13F-HR",))
    assert len(s) == len(ls.FUND_CIKS) and {r["form"] for r in s} == {"13F-HR"}
    assert not any("cgi-bin" in u for u, _ in web.log)


def test_every_substitute_targets_only_recorded_hosts_and_never_the_site_it_replaces() -> None:
    web = _Web({}, {})
    for name in ls.SUBSTITUTES:
        ls.run_channel(name, web, write=False, pace_s=0.0)
    hosts = {u.split("/")[2] for u, _ in web.log}
    assert hosts <= set(ls.TERMS), hosts - set(ls.TERMS)
    assert not hosts & set(ls.REFUSED_HOSTS)


def test_the_runner_entry_survives_pickling_for_the_spawned_miner_process() -> None:
    fn = pickle.loads(pickle.dumps(ls.runner("academic")))  # noqa: S301 -- own bytes
    assert fn.args == ("academic",)


def test_youtube_rows_keep_derived_readings_only_never_api_data(monkeypatch, tmp_path) -> None:
    import youtube_miner as ym
    d = ym.YTDiscovery(title="XAUUSD london breakout", channel="c", url="https://youtube.com/watch?v=x",
                       published="2026-11-19", symbols_mentioned=["XAUUSD"])
    monkeypatch.setattr(ym, "mine", lambda: [d])
    monkeypatch.setattr(ym, "API_KEY", "k")
    monkeypatch.setattr(ym, "OUT", tmp_path)
    rows = ym.run_and_save()
    assert rows and not {"title", "channel", "url"} & set(rows[0])
    assert rows[0]["symbols"] == ["XAUUSD"] and len(rows[0]["video_ref"]) == 16
    assert "api-services-terms" in ym.YOUTUBE_TERMS["tos_url"]


def test_youtube_without_a_key_is_unconfigured_and_never_scrapes(monkeypatch) -> None:
    import pytest
    import youtube_miner as ym
    monkeypatch.setattr(ym, "API_KEY", "")
    monkeypatch.setattr(ym, "mine", lambda: (_ for _ in ()).throw(AssertionError("searched")))
    with pytest.raises(RuntimeError, match="UNCONFIGURED"):
        ym.run_and_save()


def test_aaii_fetches_only_through_the_gate_at_its_crawl_delay(monkeypatch) -> None:
    import aaii_sentiment_miner as am
    src = Path(am.__file__).read_text("utf-8")
    assert "requests.get(" not in src and "Feed()" in src
    assert "www.aaii.com" in ls.TERMS and ls.PACE_S["www.aaii.com"] >= 10
    web = _Web({"www.aaii.com": _Resp(200, "User-agent: *\nDisallow: /sentimentsurvey")}, {})
    import importlib
    importlib.import_module("side_channels.lawful_substitutes")   # the copy aaii imports
    for mod in (m for k, m in list(sys.modules.items()) if k.split(".")[-1] == "lawful_substitutes"):
        monkeypatch.setattr(mod, "_default_get", lambda: web)
    rows = am.mine_aaii()
    assert rows[0]["kind"] == "fetch_error" and "ROBOTS_REFUSED" in rows[0]["error"]
    assert [u for u, _ in web.log] == ["https://www.aaii.com/robots.txt"]


def test_no_feed_reaches_an_unread_calendar_host() -> None:
    assert "nfs.faireconomy.media" not in ls.TERMS
