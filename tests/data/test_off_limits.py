"""WeChat and Baidu (and the Sogou route into WeChat) are off-limits grounds: no transport may
send them a request, and every roster row that names one is refused at the fetch."""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any, ClassVar

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import cn_sources, free_stack, polite_fetch  # noqa: E402
from libs.data.off_limits import off_limits  # noqa: E402
from research import alt_proxies, asia_collector  # noqa: E402

BANNED = ("https://index.baidu.com/", "https://huiyan.baidu.com/migration/historycurve.jsonp",
          "https://tieba.baidu.com/f?kw=x", "https://weixin.sogou.com/weixin?type=2&query=x",
          "https://zhihu.sogou.com/zhihu?query=x", "https://mp.weixin.qq.com/s/abc",
          "https://www.wechat.com/", "HTTPS://WWW.BAIDU.COM./duty/", "baidu.com/x",
          "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/2026FD.zip",
          "https://efdsearch.senate.gov/search/",
          "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all.json")
ALLOWED = ("https://juejin.cn/search", "https://notbaidu.com/", "https://baidu.com.example.org/",
           "https://www.qq.com/", "https://www.federalreserve.gov/", "https://www.house.gov/",
           "https://other-bucket.s3-us-west-2.amazonaws.com/x")


@pytest.mark.parametrize("url", BANNED)
def test_every_off_limits_host_is_refused(url: str) -> None:
    assert off_limits(url)


@pytest.mark.parametrize("url", ALLOWED)
def test_lookalikes_and_other_hosts_are_not(url: str) -> None:
    assert off_limits(url) is None


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    import libs.data.keyed_sources as keyed_sources

    calls: list[str] = []

    def boom(req: Any, *a: Any, **k: Any) -> Any:
        calls.append(getattr(req, "full_url", str(req)))
        raise AssertionError("an off-limits ground reached the network")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    # free_stack fetches through keyed_urlopen since #1180, not bare urlopen
    monkeypatch.setattr(keyed_sources, "keyed_urlopen", boom)
    return calls


@pytest.mark.parametrize("url", BANNED[:6] + BANNED[-3:])
def test_no_transport_sends_a_request(url: str, no_network: list[str]) -> None:
    r = polite_fetch.get(url, gate=None, opener=lambda *a, **k: no_network.append(url))
    assert r.status is None and r.error == off_limits(url)
    with pytest.raises(free_stack.FetchError, match="off_limits"):
        free_stack.http_fetch(url)
    with pytest.raises(PermissionError):
        alt_proxies.http_get(url)
    with pytest.raises(PermissionError):
        cn_sources._get(url, referer="https://example.org/")
    rec = asia_collector.collect_one({"id": "x", "url": url, "access": "key",
                                      "key_env": "BAIDU_INDEX_COOKIE"})
    assert rec["status"] == "BLOCKED_TERMS"
    assert no_network == []


def test_the_sogou_wechat_search_makes_no_request(no_network: list[str]) -> None:
    items, err = cn_sources.sogou_weixin("量化 回测")
    assert items == [] and err and "off-limits" in err
    assert no_network == []


def _urls(obj: Any) -> list[str]:
    out: list[str] = []
    if isinstance(obj, dict):
        for v in obj.values():
            out += _urls(v)
    elif isinstance(obj, list):
        for v in obj:
            out += _urls(v)
    elif isinstance(obj, str):
        out += re.findall(r"https?://[^\s'\"<>]+", obj)
    return out


ROSTERS = ("desks/mt5/data/asia_sources.json", "desks/mt5/data/free_stack_sources.json",
           "desks/mt5/data/deep_forest_sources.json",
           "desks/mt5/data/source_rosters/asia_paid_substitutes_consumer.yaml")


def test_no_roster_url_naming_an_off_limits_ground_can_be_fetched() -> None:
    """Any roster URL whose host names weixin, wechat, sogou or baidu is refused at the fetch."""
    named = 0
    for rel in ROSTERS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        doc = yaml.safe_load(text) if rel.endswith(".yaml") else json.loads(text)
        for url in _urls(doc):
            host = url.split("/")[2].lower()
            if re.search(r"weixin|wechat|sogou|baidu|disclosures-clerk|efdsearch|stock-watcher",
                         host):
                named += 1
                assert off_limits(url), f"{rel}: {url} would be fetched"
    assert named >= 3          # the rows exist and are refused, not silently missing


def test_alt_proxies_never_fetches_an_off_limits_source() -> None:
    for src in alt_proxies.SOURCES:
        url = str(getattr(src, "url", "") or "")
        host = url.split("/")[2].lower() if "//" in url else ""
        if re.search(r"weixin|wechat|sogou|baidu", host):
            assert off_limits(url), src.id


def test_a_malformed_url_fails_closed() -> None:
    assert off_limits("http://[::1")                   # unparseable host: refused, not None


class _Redirected:
    """A response whose final hop (after urllib followed a 30x) is an off-limits host."""

    url = "https://www.baidu.com/landing"
    status = 200
    headers: ClassVar[dict[str, str]] = {}

    def __enter__(self) -> _Redirected:
        return self

    def __exit__(self, *a: object) -> None:
        return None

    def geturl(self) -> str:
        return self.url

    def read(self, *a: Any) -> bytes:
        raise AssertionError("the body of an off-limits hop was read")


def test_a_redirect_into_an_off_limits_host_is_discarded_unread(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.data.off_limits import redirected_off_limits
    assert redirected_off_limits("https://ok.example/", "https://ok.example/") is None
    assert redirected_off_limits("https://ok.example/", "https://x.sogou.com/")
    r = polite_fetch.get("https://ok.example/a", gate=None, retries=0,
                         opener=lambda *a, **k: _Redirected())
    assert "redirected into an off-limits host" in r.error and not r.text
    import libs.data.keyed_sources as keyed_sources
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Redirected())
    monkeypatch.setattr(keyed_sources, "keyed_urlopen", lambda *a, **k: _Redirected())
    with pytest.raises(free_stack.FetchError, match="off_limits"):
        free_stack.http_fetch("https://ok.example/a")

    class _Opener:   # alt_proxies fetches through keyed_opener since #1180, not bare urlopen
        def open(self, *_a, **_k):
            return _Redirected()

    monkeypatch.setattr(keyed_sources, "keyed_opener", lambda *a, **k: _Opener())
    with pytest.raises(PermissionError):
        alt_proxies.http_get("https://ok.example/a")
    with pytest.raises(PermissionError):
        cn_sources._get("https://ok.example/a", referer="https://ok.example/")
