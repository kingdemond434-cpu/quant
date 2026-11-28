"""HKEX (hkex.com.hk, hkexnews.hk) and the SSE (sse.com.cn) are refused on their own terms.

HKEX Terms of Use s5 forbid bots, scrapers and "any programmatic, scripted or other mechanical
means" of access; the SSE 法律声明 s3 allows only non-commercial browsing and downloading and
restricts 电子抓取系统. Both were read 2026-11-18. Each host is on the refused list with its
clause, every transport refuses it before a request, and no roster or pack root still sends a
crawler there."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import polite_fetch  # noqa: E402
from libs.data.off_limits import off_limits  # noqa: E402
from libs.data.refused_hosts import REFUSED_HOSTS, refusal  # noqa: E402

HOSTS = ("hkex.com.hk", "hkexnews.hk", "sse.com.cn")
URLS = ("https://www.hkex.com.hk/Market-Data/Statistics",
        "https://www1.hkexnews.hk/search/titlesearch.xhtml",
        "http://query.sse.com.cn/commonQuery.do",
        "https://WWW.SSE.COM.CN./home/")


def _blocked(text: str) -> bool:
    return any(h in text for h in HOSTS)


def test_each_host_carries_its_verbatim_clause() -> None:
    assert "programmatic, scripted or other mechanical means" in REFUSED_HOSTS["hkex.com.hk"]
    assert "programmatic, scripted or other mechanical" in REFUSED_HOSTS["hkexnews.hk"]
    assert "电子抓取系统" in REFUSED_HOSTS["sse.com.cn"]
    assert "非商业目的" in REFUSED_HOSTS["sse.com.cn"]


@pytest.mark.parametrize("url", URLS)
def test_refused_by_the_list_and_by_every_transport(url: str) -> None:
    assert refusal(url)
    assert off_limits(url) and "BLOCKED_TERMS" in str(off_limits(url))

    def opener(*a: object, **k: object) -> object:
        raise AssertionError("a refused host reached the network")

    r = polite_fetch.get(url, opener=opener, gate=None, retries=0)
    assert r.status is None and r.error


def test_a_neighbour_is_not_caught() -> None:
    assert off_limits("https://www.szse.cn/") is None
    assert off_limits("https://notsse.com.cn.example.org/") is None


def test_the_deep_forest_miner_refuses_them() -> None:
    import deep_forest_miner
    for url in URLS:
        assert str(deep_forest_miner.access_refusal(url)).startswith("TERMS_REFUSED")


@pytest.mark.parametrize("rel", ["desks/mt5/data/deep_forest_sources.json",
                                 "desks/mt5/data/asia_sources.json",
                                 "desks/mt5/data/paid_substitute_library.json"])
def test_no_crawled_roster_names_them(rel: str) -> None:
    assert not _blocked((ROOT / rel).read_text(encoding="utf-8"))


def test_cited_rows_that_name_them_are_fenced() -> None:
    doc = json.loads((DESK / "data" / "source_rosters" / "culture_gap_sources.json")
                     .read_text(encoding="utf-8"))
    rows = [r for r in doc["sources"] if _blocked(str(r.get("url", "")))]
    assert rows and all(r.get("terms_status") == "TERMS_BLOCKED" for r in rows)
    dum = json.loads((ROOT / "data" / "data_universe_map.json").read_text(encoding="utf-8"))
    assert dum["sources"]["hkex_daily_derivatives_reports"]["grade"] == "TERMS_BLOCKED"


def test_no_crawler_seed_or_pack_root_names_them() -> None:
    from side_channels import world_crawler
    assert not [s for s in world_crawler.SEEDS if _blocked(s)]
    import importlib
    for code in ("cn", "hk", "mo"):
        pack = importlib.import_module(f"research.countries.{code}.pack")
        for cls in pack.SOURCE_CLASSES:
            assert not [r for r in cls["roots"] if _blocked(str(r))], (code, cls["id"])
