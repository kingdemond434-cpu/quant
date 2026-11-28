"""SAFE, MAS, RBI, SARB and the BoJ refuse on their own terms; PBOC, CSRC and BOK are unread.

Each refused publisher's clause is on its row; every transport that asks `off_limits` refuses it
before a request; the deep-forest miner refuses all eight; and no roster row, crawler seed or
forest ground still sends a fetcher to one of them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for p in (str(ROOT), str(DESK), str(DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.data import off_limits, refused_hosts  # noqa: E402

REFUSED = {
    "https://www.safe.gov.cn/safe/ywfb/index.html": "商业性转载",
    "https://www.mas.gov.sg/monetary-policy": "prior written permission of MAS",
    "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx": "caching",
    "https://rbi.org.in/Scripts/Disclaimer.aspx": "caching",
    "https://dbie.rbi.org.in/": "caching",
    "https://www.resbank.co.za/en/home/what-we-do/statistics": "prior written consent",
    "https://custom.resbank.co.za/SarbWebApi/": "prior written consent",
    "https://www.boj.or.jp/en/rss/whatsnew.xml": "prior permission",
    "https://www.stat-search.boj.or.jp/": "prior permission",
}
UNREAD = ("https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/index.html",
          "https://www.csrc.gov.cn/", "https://www.bok.or.kr/eng/main/main.do")
HOSTS = ("safe.gov.cn", "mas.gov.sg", "rbi.org.in", "resbank.co.za", "boj.or.jp",
         "pbc.gov.cn", "csrc.gov.cn", "www.bok.or.kr")


def test_each_refused_publisher_carries_its_own_clause() -> None:
    for url, phrase in REFUSED.items():
        why = refused_hosts.refusal(url)
        assert why and phrase in why, url


def test_only_the_mas_website_is_refused_not_its_licensed_api() -> None:
    assert refused_hosts.refusal("https://eservices.mas.gov.sg/api/action/datastore/") is None


def test_unread_hosts_are_not_settled_refusals() -> None:
    for url in UNREAD:
        assert refused_hosts.refusal(url) is None, url
    assert refused_hosts.refusal("https://ecos.bok.or.kr/api/") is None


def test_every_transport_refuses_before_a_request() -> None:
    for url in REFUSED:
        why = off_limits.off_limits(url)
        assert why and why.startswith(off_limits.STATUS), url


def test_the_deep_forest_miner_refuses_all_eight_without_a_request(monkeypatch) -> None:
    import deep_forest_miner as dfm

    def no_network(*a, **k):
        raise AssertionError("a refused host was contacted")

    monkeypatch.setattr(dfm.pf, "get", no_network)
    for url in REFUSED:
        assert str(dfm.access_refusal(url)).startswith("TERMS_REFUSED"), url
    for url in UNREAD:
        assert str(dfm.access_refusal(url)).startswith("TERMS_UNREAD"), url


def test_no_forest_ground_or_crawler_seed_reaches_them() -> None:
    forest = json.loads((DESK / "data" / "deep_forest_sources.json").read_text("utf-8"))
    for g in forest["grounds"]:
        blob = json.dumps({k: g.get(k) for k in ("url", "site")})
        assert not any(h in blob for h in HOSTS), g.get("name")
    sys.path.insert(0, str(DESK / "side_channels"))
    import world_crawler
    for seed in world_crawler.SEEDS:
        assert not any(h in seed for h in (*HOSTS, "bok.or.kr")), seed
    for h in world_crawler._DATA_HOSTS:
        assert h not in ("pbc.gov.cn", "csrc.gov.cn", "boj.or.jp", "bok.or.kr"), h


def test_asia_rows_on_them_are_fenced_and_never_fetched() -> None:
    import asia_collector
    rows = json.loads((DESK / "data" / "asia_sources.json").read_text("utf-8"))["sources"]
    # The two licensed APIs keep their own rows: MAS's datastore API (its API terms allow
    # commercial use) and BOK's keyed ECOS Open API.
    apis = {"mas_api", "bok_ecos"}
    hit = [r for r in rows if any(h in str(r.get("url")) for h in HOSTS) and r["id"] not in apis]
    assert len(hit) == 12
    for r in hit:
        rec = asia_collector.collect_one(dict(r))
        assert rec["status"] == "BLOCKED_TERMS", r["id"]
