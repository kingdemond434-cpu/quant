"""deep_forest_miner reads only what robots.txt, the host's terms and its region allow."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import polite_fetch as pf  # noqa: E402
from research import deep_forest_miner as dfm  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_cache():
    dfm._ROBOTS.clear()
    yield
    dfm._ROBOTS.clear()


def _serve(monkeypatch, robots: pf.Response, page: str = "<p>ok</p>") -> list[str]:
    calls: list[str] = []

    def fake(url, **_kw):
        calls.append(url)
        if url.endswith("/robots.txt"):
            return robots
        return pf.Response(url=url, status=200, text=page)

    monkeypatch.setattr(dfm.pf, "get", fake)
    return calls


def test_the_user_agent_says_what_is_reading() -> None:
    ua = dfm._UA["User-Agent"]
    assert "Mozilla" not in ua and "Chrome" not in ua
    assert ua.startswith(dfm.ROBOTS_AGENT)


@pytest.mark.parametrize("status", [401, 403, 429, 451, 500, 503])
def test_unreadable_robots_refuses_and_the_page_is_never_requested(monkeypatch,
                                                                   status: int) -> None:
    calls = _serve(monkeypatch, pf.Response(url="r", status=status, error="x"))
    with pytest.raises(dfm.RobotsRefused, match="ROBOTS_REFUSED"):
        dfm._http("https://forum.example/t/1")
    assert calls == ["https://forum.example/robots.txt"]


def test_html_in_place_of_robots_refuses(monkeypatch) -> None:
    _serve(monkeypatch, pf.Response(url="r", status=200, text="<!DOCTYPE html><html>wall"))
    assert "HTML" in (dfm.access_refusal("https://forum.example/t/1") or "")


@pytest.mark.parametrize("status", [404, 410])
def test_absent_robots_allows(monkeypatch, status: int) -> None:
    _serve(monkeypatch, pf.Response(url="r", status=status, error="nf"))
    assert dfm._http("https://forum.example/t/1") == "<p>ok</p>"


def test_a_disallow_for_everyone_refuses_and_an_allowed_path_reads(monkeypatch) -> None:
    _serve(monkeypatch, pf.Response(url="r", status=200,
                                    text="User-agent: *\nDisallow: /community/u/\n"))
    assert dfm.access_refusal("https://forum.example/community/u/42")
    assert dfm.access_refusal("https://forum.example/community/t/7") is None


@pytest.mark.parametrize("url", ["https://bigquant.com/wiki/", "https://www.bigquant.com/x",
                                 "https://genport.newsystock.com/"])
def test_hosts_whose_terms_forbid_bots_are_never_requested(monkeypatch, url: str) -> None:
    calls = _serve(monkeypatch, pf.Response(url="r", status=404))
    with pytest.raises(dfm.RobotsRefused, match="TERMS_REFUSED"):
        dfm._http(url)
    assert calls == []


def test_a_refusal_is_not_a_network_failure_and_is_named(monkeypatch) -> None:
    _serve(monkeypatch, pf.Response(url="r", status=503, error="x"))
    run = dfm._Run.__new__(dfm._Run)
    run.status, run.counts = [], {"pages": 0}
    seen: list[bool] = []
    run._net_ok = lambda: True                                    # type: ignore[method-assign]
    run._note_net = seen.append                                   # type: ignore[method-assign]
    run.ground = {"language": "zh"}
    assert run.page("https://forum.example/t/1") == ""
    assert run.counts["access_refused"] == 1 and seen == []
    assert run.status[-1]["refused"].startswith("ROBOTS_REFUSED")


def test_a_region_wall_is_recorded_and_never_parsed(monkeypatch) -> None:
    _serve(monkeypatch, pf.Response(url="r", status=404),
           page="<html>当前地区暂不支持访问 Sorry</html>")
    run = dfm._Run.__new__(dfm._Run)
    run.status, run.counts = [], {"pages": 0}
    run._net_ok = lambda: True                                    # type: ignore[method-assign]
    run._note_net = lambda ok: None                               # type: ignore[method-assign]
    run.ground = {"language": "zh"}
    assert run.page("https://www.joinquant.com/view/community/list") == ""
    assert run.status[-1] == {"url": "https://www.joinquant.com/view/community/list",
                              "blocked": "REGION_BLOCKED"}
    assert run.counts["pages"] == 0
