"""Catalog routes: cursors resume, landing pages are not endpoints, unchanged pages are not
re-read, mirrors are flagged, keyed APIs are kept as NEEDS_KEY, blocked hosts are never touched.

No network: every request goes through a recorded fake that serves CKAN / DCAT / SDMX / STAC /
CDX shaped payloads and records the headers it was sent.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import catalog_routes as cr  # noqa: E402

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
Handler = Callable[[str, Mapping[str, str]], cr.Response]


class Net:
    """A fake transport: handlers keyed by host+path; robots.txt answers 404 unless set."""

    def __init__(self, handlers: dict[str, Handler] | None = None) -> None:
        self.handlers = handlers or {}
        self.robots: dict[str, str] = {}
        self.calls: list[tuple[str, dict[str, str]]] = []

    def __call__(self, url: str, headers: Mapping[str, str], timeout: float) -> cr.Response:
        self.calls.append((url, dict(headers)))
        p = urllib.parse.urlsplit(url)
        if p.path == "/robots.txt":
            body = self.robots.get(p.netloc)
            return cr.Response(200, body.encode()) if body is not None else cr.Response(404)
        h = self.handlers.get(p.netloc + p.path)
        return h(url, headers) if h else cr.Response(404)

    def api_calls(self) -> list[tuple[str, dict[str, str]]]:
        return [c for c in self.calls if not c[0].endswith("/robots.txt")]


def _json(obj: Any, etag: str = "") -> cr.Response:
    return cr.Response(200, json.dumps(obj).encode(), {"etag": etag} if etag else {})


def _q(url: str) -> dict[str, str]:
    return dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))


_PERMITS = {"verdict": "PERMITS", "terms_url": "https://terms.example.org/",
            "terms_quote": "You may reuse the data freely, including by automated means."}
#: Every fixture host, as permitted by a quoted clause -- except the fenced and crypto ones,
#: which the fence must refuse even when terms evidence would permit them.
TEST_HOSTS = ("example.org", "example.gov", "example.eu", "example.kr", "example", "a.org",
              "cat", "b", "s", "commoncrawl.org", "sdmx.org", "venuea.com", "reddit.com")


@pytest.fixture()
def box(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(cr, "STATE", tmp_path / "catalog_routes" / "state.json")
    monkeypatch.setattr(cr, "CACHE", tmp_path / "catalog_routes" / "cache")
    monkeypatch.setattr(cr, "WORLD", tmp_path / "world")
    monkeypatch.setattr(cr, "REPORT", tmp_path / "reports" / "CATALOG_ROUTES.json")
    ev = tmp_path / "catalog_routes" / "terms_evidence.json"
    ev.parent.mkdir(parents=True, exist_ok=True)
    ev.write_text(json.dumps({"hosts": {h: _PERMITS for h in TEST_HOSTS}}))
    monkeypatch.setattr(cr, "TERMS_EVIDENCE", ev)
    return tmp_path


def _roster(tmp: Path, portals: list[dict[str, Any]], **defaults: Any) -> Path:
    p = tmp / "roster.json"
    d = {"rows": 2, "pages_per_visit": 1, "max_entries_per_visit": 400, "min_gap_s": 0.0,
         "relist_days": 7, "timeout_s": 5}
    d.update(defaults)
    p.write_text(json.dumps({"defaults": d, "portals": portals,
                             "blocked_hosts": ["reddit.com", "x.com", "twitter.com",
                                               "venuea", "venueb", "venuec"]}))
    return p


def _run(tmp: Path, roster: Path, net: Net, now: datetime = NOW, **kw: Any) -> dict[str, Any]:
    t = [0.0]

    def clock() -> float:
        return t[0]

    def sleep(s: float) -> None:
        t[0] += s

    return cr.run(60.0, fetch=net, now=now, roster_path=roster, clock=clock, sleep=sleep, **kw)


def _pkg(i: int, *, fmt: str = "CSV", producer: str = "Stats Office",
         title: str | None = None) -> dict[str, Any]:
    return {"name": f"ds-{i}", "title": title or f"Dataset {i}",
            "organization": {"title": producer}, "license_title": "CC-BY-4.0",
            "extras": [{"key": "frequency", "value": "monthly"}],
            "resources": [{"url": f"https://files.example.org/ds-{i}.csv", "format": fmt},
                          {"url": f"https://portal.example.org/dataset/ds-{i}", "format": "HTML"}]}


def ckan_handler(total: int, etag: str = "") -> Handler:
    def h(url: str, headers: Mapping[str, str]) -> cr.Response:
        if etag and headers.get("If-None-Match") == etag:
            return cr.Response(304)
        q = _q(url)
        start, rows = int(q["start"]), int(q["rows"])
        res = [_pkg(i) for i in range(start, min(total, start + rows))]
        return _json({"success": True, "result": {"count": total, "results": res}}, etag)
    return h


CKAN = {"id": "xx_ckan", "route": "ckan", "base": "https://portal.example.org", "country": "XX",
        "region": "Europe", "language": "xx", "producer": "Portal", "producer_type": "portal"}


# ------------------------------------------------------------------------------ cursors ----
def test_ckan_cursor_resumes_across_runs_and_page_one_is_never_the_catalogue(box: Path) -> None:
    roster = _roster(box, [CKAN])
    net = Net({"portal.example.org/api/3/action/package_search": ckan_handler(5)})
    r1 = _run(box, roster, net)
    row = r1["portals"]["xx_ckan"]
    assert (row["rows"], row["total"], row["remainder"]) == (2, 5, 3)
    assert r1["remainder_total"] == 3                      # published, not hidden
    r2 = _run(box, roster, net, now=NOW + timedelta(hours=1))
    assert r2["portals"]["xx_ckan"]["remainder"] == 1
    starts = [_q(u)["start"] for u, _ in net.api_calls()]
    assert starts == ["0", "2"]                            # resumed, never restarted
    r3 = _run(box, roster, net, now=NOW + timedelta(hours=2))
    assert r3["portals"]["xx_ckan"]["remainder"] == 0
    st = json.loads(cr.STATE.read_text())["portals"]["xx_ckan"]["cursor"]
    assert st["passes"] == 1 and st["next"] is None
    # a completed pass waits for its relist period: no request at all
    r4 = _run(box, roster, net, now=NOW + timedelta(hours=3))
    assert r4["portals"]["xx_ckan"]["status"] == "IDLE_UNTIL_RELIST"
    assert len(net.api_calls()) == 3
    rows = json.loads((cr.WORLD / "discoveries_catalog_20261006.json").read_text())
    assert len(rows) == 5 and len({r["dataset_id"] for r in rows}) == 5


def test_rows_carry_the_catalogue_metadata_in_the_acquirers_shape(box: Path) -> None:
    _run(box, _roster(box, [CKAN]), Net({"portal.example.org/api/3/action/package_search":
                                        ckan_handler(1)}))
    (row,) = json.loads((cr.WORLD / "discoveries_catalog_20261006.json").read_text())
    assert row["endpoints"] == ["https://files.example.org/ds-0.csv"]
    assert row["host"] == "files.example.org"
    for k in ("route", "portal", "producer", "country", "subnational", "observable", "title",
              "formats", "license", "cadence", "first_discovered_at", "endpoints"):
        assert k in row
    assert (row["route"], row["producer"], row["license"], row["cadence"]) == (
        "ckan", "Stats Office", "CC-BY-4.0", "monthly")
    assert row["landing_page"] == "https://portal.example.org/dataset/ds-0"


# ------------------------------------------------------------------------ landing pages ----
@pytest.mark.parametrize(("url", "fmt", "media", "kind"), [
    ("https://a.org/x.csv", "CSV", "", "data"),
    ("https://a.org/x", "text/csv", "", "data"),
    ("https://a.org/data?format=csv", "", "", "data"),
    ("https://a.org/x.xlsx", "", "", "data"),
    ("https://a.org/dataset/x", "HTML", "", "landing"),
    ("https://a.org/dataset/x", "", "", "landing"),
    ("https://a.org/report.html", "CSV", "", "landing"),
    ("https://a.org/doc.pdf", "PDF", "", "landing"),
    ("https://a.org/x.csv", "", "text/html", "landing"),
    ("https://a.org/x.csv?api_key=1", "CSV", "", "keyed"),
    ("ftp://a.org/x.csv", "CSV", "", "other"),
    ("https://a.org/x", "http://publications.europa.eu/resource/authority/file-type/CSV", "",
     "data"),
])
def test_landing_pages_are_never_endpoints(url: str, fmt: str, media: str, kind: str) -> None:
    assert cr.resource_kind(url, fmt, media) == kind


def test_stac_rasters_are_observation_classes_and_only_tabular_assets_are_endpoints() -> None:
    assert cr.resource_kind("https://b/x.tif", "", "image/tiff; application=geotiff",
                            stac=True) == "other"
    assert cr.resource_kind("https://b/x.parquet", "", "application/x-parquet",
                            stac=True) == "data"
    assert cr.resource_kind("https://b/thumb.json", "", "application/json", stac=True,
                            roles=["thumbnail"]) == "other"
    assert cr.resource_kind("https://b/x.xlsx", "", "", stac=True) == "other"


# ------------------------------------------------------------------ conditional requests ----
def test_unchanged_pages_are_not_reread_and_304_advances(box: Path) -> None:
    roster = _roster(box, [CKAN], rows=10, relist_days=0)
    net = Net({"portal.example.org/api/3/action/package_search": ckan_handler(3, etag='"v1"')})
    r1 = _run(box, roster, net)
    assert r1["discovered"] == 3 and r1["not_modified"] == 0
    assert "If-None-Match" not in net.api_calls()[0][1]
    assert net.api_calls()[0][1]["User-Agent"] == cr.UA
    r2 = _run(box, roster, net, now=NOW + timedelta(hours=1))
    assert net.api_calls()[1][1]["If-None-Match"] == '"v1"'
    assert r2["not_modified"] == 1 and r2["discovered"] == 0
    assert r2["portals"]["xx_ckan"]["remainder"] == 0


SDMX_XML = b"""<?xml version="1.0"?>
<message:Structure xmlns:message="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message"
 xmlns:str="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure"
 xmlns:com="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common">
 <message:Structures><str:Dataflows>
  <str:Dataflow id="AAA" agencyID="XB" version="1.0"><com:Name xml:lang="de">Aa</com:Name>
   <com:Name xml:lang="en">Alpha prices</com:Name></str:Dataflow>
  <str:Dataflow id="BBB" agencyID="XB" version="2.0"><com:Name xml:lang="en">Beta</com:Name>
  </str:Dataflow>
  <str:Dataflow id="CCC" agencyID="XB" version="1.1"><com:Name xml:lang="en">Gamma</com:Name>
  </str:Dataflow>
 </str:Dataflows></message:Structures></message:Structure>"""

SDMX = {"id": "xb_sdmx", "route": "sdmx", "base": "https://sdmx.example.org/rest",
        "country": "XB", "region": "Europe", "language": "en", "producer": "XB Stats",
        "producer_type": "statistics_office", "listing": "/dataflow/all",
        "data_template": "{base}/data/{agency},{id},{version}/all?format=csvfilewithlabels"}


def test_sdmx_listing_becomes_concrete_data_urls_and_a_304_walks_the_cached_rest(
        box: Path) -> None:
    def h(url: str, headers: Mapping[str, str]) -> cr.Response:
        if headers.get("If-None-Match") == '"s1"':
            return cr.Response(304)
        return cr.Response(200, SDMX_XML, {"etag": '"s1"'})
    roster = _roster(box, [SDMX], max_entries_per_visit=2)
    net = Net({"sdmx.example.org/rest/dataflow/all": h})
    r1 = _run(box, roster, net)
    assert r1["portals"]["xb_sdmx"]["remainder"] == 1
    assert r1["portals"]["xb_sdmx"]["unit"] == "dataflows"
    r2 = _run(box, roster, net, now=NOW + timedelta(hours=1))
    assert r2["not_modified"] == 1 and r2["discovered"] == 1
    assert r2["portals"]["xb_sdmx"]["remainder"] == 0
    rows = json.loads((cr.WORLD / "discoveries_catalog_20261006.json").read_text())
    by_id = {r["dataset_id"]: r for r in rows}
    assert by_id["AAA"]["title"] == "Alpha prices"
    assert by_id["AAA"]["endpoints"] == [
        "https://sdmx.example.org/rest/data/XB,AAA,1.0/all?format=csvfilewithlabels"]
    assert set(by_id) == {"AAA", "BBB", "CCC"}


def test_sdmx_without_csv_support_keeps_the_url_unparsed_not_as_an_endpoint() -> None:
    flows = cr.parse_sdmx_listing(SDMX_XML)
    assert flows is not None and len(flows) == 3
    portal = {**SDMX, "data_template": None, "data_template_xml": "{base}/data/{id}"}
    row = cr.build_row(portal, "sdmx", cr.sdmx_entries(flows, portal)[0], "t", [])
    assert row["endpoints"] == [] and row["access"] == "UNPARSED_FORMAT"
    assert row["unparsed_endpoints"] == ["https://sdmx.example.org/rest/data/AAA"]


def test_sdmx_json_structure_is_read_too() -> None:
    body = json.dumps({"data": {"dataflows": [
        {"id": "F1", "agencyID": "A", "version": "1.0", "names": {"en": "Freight"}}]}}).encode()
    assert cr.parse_sdmx_listing(body) == [
        {"id": "F1", "agency": "A", "version": "1.0", "name": "Freight"}]


# ------------------------------------------------------------------------- unknown shape ----
def test_an_unknown_api_shape_reads_unmeasured_not_zero(box: Path) -> None:
    net = Net({"portal.example.org/api/3/action/package_search":
               lambda u, h: _json({"hello": "world"})})
    r = _run(box, _roster(box, [CKAN]), net)
    row = r["portals"]["xx_ckan"]
    assert row["status"] == "UNMEASURED_SHAPE"
    assert row["remainder"] == cr.UNMEASURED
    assert "xx_ckan" in r["remainder_unmeasured_portals"]


def test_probe_route_reports_the_shape_and_emits_nothing(box: Path) -> None:
    probe = {**CKAN, "id": "xx_probe", "route": "probe",
             "url": "https://portal.example.org/odata/Tables"}
    net = Net({"portal.example.org/odata/Tables":
               lambda u, h: _json({"odata.metadata": "x", "value": [{"Identifier": "1"}]})})
    r = _run(box, _roster(box, [probe]), net)
    row = r["portals"]["xx_probe"]
    assert row["status"] == "UNMEASURED_SHAPE" and row["detected_shape"] == "odata"
    assert row["remainder"] == cr.UNMEASURED and r["discovered"] == 0


# --------------------------------------------------------------------------------- mirrors ----
def test_mirrors_are_flagged_not_counted_twice() -> None:
    a = cr.build_row(CKAN, "ckan", cr.ckan_entry(_pkg(1, producer="Stats Office",
                                                       title="Port throughput"),
                                                 CKAN["base"]), "t1", [])
    hub = {**CKAN, "id": "eu_hub", "base": "https://hub.example.eu"}
    pkg = _pkg(1, producer="Stats Office", title="Port Throughput!")
    pkg["resources"][0]["url"] = "https://mirror.example.eu/port.csv"
    b = cr.build_row(hub, "ckan", cr.ckan_entry(pkg, hub["base"]), "t2", [])
    same_url = cr.build_row({**CKAN, "id": "city"}, "ckan",
                            cr.ckan_entry(_pkg(1, producer="City", title="Other title"),
                                          "https://city.example.org"), "t3", [])
    index = cr.empty_index()
    kept, stats = cr.dedup([a, b, same_url], index)
    assert len(kept) == 3
    assert kept[0]["mirror_of"] is None and kept[0]["endpoints"]
    assert kept[1]["mirror_of"] == a["row_id"]                     # (producer, title)
    assert kept[1]["endpoints"] == [] and kept[1]["mirror_endpoints"] == [
        "https://mirror.example.eu/port.csv"]
    assert kept[2]["mirror_of"] == a["row_id"]                     # identical data URL
    assert stats["new_rows"] == 1 and stats["mirrors"] == 2 and stats["new_endpoints"] == 1
    again, st2 = cr.dedup([dict(a)], index)                        # a revisit is dropped
    assert again == [] and st2["revisited"] == 1


def test_a_bare_title_without_a_producer_is_not_a_mirror_key() -> None:
    assert cr.title_key("", "Budget 2020") is None
    assert cr.title_key("Stats", "Budget  2020!") == cr.title_key("stats", "budget 2020")


def test_dedup_index_rebuilds_from_the_discoveries_files(box: Path) -> None:
    _run(box, _roster(box, [CKAN]), Net({"portal.example.org/api/3/action/package_search":
                                        ckan_handler(2)}))
    idx = cr.load_index()                      # from the cache
    (cr.CACHE / "index.json").unlink()
    rebuilt = cr.load_index()
    assert rebuilt["rows"].keys() == idx["rows"].keys()
    assert cr.norm_url("https://files.example.org/ds-0.csv") in rebuilt["urls"]


# ------------------------------------------------------------------------------ keyed APIs ----
def test_keyed_portals_are_recorded_needs_key_without_a_request(box: Path) -> None:
    keyed = {**CKAN, "id": "kr_keyed", "route": "keyed", "base": "https://keyed.example.kr",
             "auth": "key", "note": "serviceKey"}
    net = Net()
    r = _run(box, _roster(box, [keyed]), net)
    assert net.calls == []
    assert r["portals"]["kr_keyed"]["status"] == "NEEDS_KEY"
    (row,) = json.loads((cr.WORLD / "discoveries_catalog_20261006.json").read_text())
    assert row["access"] == "NEEDS_KEY" and row["endpoints"] == []
    assert row["keyed_endpoints"] == ["https://keyed.example.kr"]
    r2 = _run(box, _roster(box, [keyed]), net, now=NOW + timedelta(hours=1))
    assert r2["discovered"] == 0 and r2["revisited"] == 1          # kept once, never dropped


def test_a_keyed_resource_is_kept_as_needs_key_and_never_an_endpoint() -> None:
    pkg = _pkg(3)
    pkg["resources"] = [{"url": "https://api.example.org/v1/data?apikey=XYZ&f=csv",
                         "format": "CSV"}]
    row = cr.build_row(CKAN, "ckan", cr.ckan_entry(pkg, CKAN["base"]), "t", [])
    assert row["endpoints"] == [] and row["access"] == "NEEDS_KEY"
    assert row["keyed_endpoints"] == ["https://api.example.org/v1/data?apikey=XYZ&f=csv"]


def test_http_401_reads_needs_key() -> None:
    assert cr.access_status(cr.Response(401)) == "NEEDS_KEY"
    assert cr.access_status(cr.Response(403)) == "FORBIDDEN"
    assert cr.access_status(cr.Response(0, error="URLError")) == "UNREACHABLE"


# --------------------------------------------------------------------------- blocked hosts ----
@pytest.mark.parametrize(("host", "blocked"), [
    ("www.reddit.com", True), ("reddit.com", True), ("x.com", True), ("api.x.com", True),
    ("box.com", False), ("twitter.com", True), ("data.venuea.vision", True),
    ("api.venueb.com", True), ("api.venuec.xyz", True), ("data-api.ecb.europa.eu", False),
])
def test_blocked_hosts(host: str, blocked: bool) -> None:
    roster = ["reddit.com", "x.com", "twitter.com", "venuea", "venueb", "venuec"]
    assert cr.is_blocked(host, roster) is blocked


def test_blocked_portals_and_endpoints_are_never_touched(box: Path) -> None:
    bad = {**CKAN, "id": "crypto", "base": "https://api.venuea.com"}
    pkg = _pkg(7)
    pkg["resources"].append({"url": "https://www.reddit.com/r/x.json", "format": "JSON"})
    net = Net({"portal.example.org/api/3/action/package_search":
               lambda u, h: _json({"success": True, "result": {"count": 1, "results": [pkg]}})})
    r = _run(box, _roster(box, [bad, CKAN]), net)
    assert r["portals"]["crypto"]["status"] == "BLOCKED_HOST"
    assert not any("venuea" in u for u, _ in net.calls)
    (row,) = json.loads((cr.WORLD / "discoveries_catalog_20261006.json").read_text())
    assert all("reddit" not in u for u in row["endpoints"])
    assert row["n_blocked_resources"] == 1


def test_robots_disallow_is_obeyed(box: Path) -> None:
    net = Net({"portal.example.org/api/3/action/package_search": ckan_handler(3)})
    net.robots["portal.example.org"] = "User-agent: *\nDisallow: /api/\n"
    r = _run(box, _roster(box, [CKAN]), net)
    assert r["portals"]["xx_ckan"]["status"] == "ROBOTS_DISALLOWED"
    assert net.api_calls() == []
    assert "portal.example.org" in r["robots_disallow_hosts"]


def test_the_ua_names_the_desk_and_is_not_a_browser() -> None:
    assert "Mozilla" not in cr.UA and "quant-desk" in cr.UA


# ---------------------------------------------------------------------- dcat / stac / cdx ----
def test_project_open_data_distributions() -> None:
    body = json.dumps({"conformsTo": "https://project-open-data.cio.gov/v1.1/schema",
                       "dataset": [{
                           "identifier": "usda-1", "title": "Crop progress",
                           "publisher": {"name": "NASS"}, "accrualPeriodicity": "R/P1W",
                           "license": "https://creativecommons.org/publicdomain/zero/1.0/",
                           "landingPage": "https://usda.example.gov/crop",
                           "distribution": [
                               {"downloadURL": "https://usda.example.gov/crop.csv",
                                "mediaType": "text/csv"},
                               {"accessURL": "https://usda.example.gov/crop", "format": "HTML"}]}]}
                      ).encode()
    entries = cr.parse_pod(body)
    assert entries is not None
    row = cr.build_row(CKAN, "dcat_pod", entries[0], "t", [])
    assert row["endpoints"] == ["https://usda.example.gov/crop.csv"]
    assert (row["producer"], row["cadence"]) == ("NASS", "R/P1W")
    assert row["landing_page"] == "https://usda.example.gov/crop"


def test_dcat_jsonld_graph_with_hydra_paging() -> None:
    body = json.dumps({"@context": {}, "@graph": [
        {"@id": "https://cat/ds/1", "@type": "dcat:Dataset", "dct:title": {"@value": "Prix",
                                                                          "@language": "fr"},
         "dct:identifier": "prix-1", "dcat:distribution": [{"@id": "https://cat/dist/1"}],
         "dct:publisher": {"@id": "https://cat/org/1"}},
        {"@id": "https://cat/dist/1", "@type": "dcat:Distribution",
         "dcat:downloadURL": {"@id": "https://files.cat/prix.csv"},
         "dcat:mediaType": "text/csv"},
        {"@id": "https://cat/org/1", "@type": "foaf:Organization", "foaf:name": "INSEE"},
        {"@id": "https://cat/catalog.jsonld?page=1", "@type": "hydra:PartialCollectionView",
         "hydra:next": "https://cat/catalog.jsonld?page=2", "hydra:totalItems": 40}]}).encode()
    parsed = cr.parse_dcat_page(body)
    assert parsed is not None
    entries, nxt, total = parsed
    assert nxt == "https://cat/catalog.jsonld?page=2" and total == 40
    row = cr.build_row(CKAN, "dcat_jsonld", entries[0], "t", [])
    assert row["endpoints"] == ["https://files.cat/prix.csv"]
    assert (row["title"], row["producer"]) == ("Prix", "INSEE")
    assert cr.parse_dcat_page(json.dumps({"foo": 1}).encode()) is None


def test_stac_collections_paginate_and_tabular_items_are_searched(box: Path) -> None:
    base = "stac.example.org/api"

    def cols(url: str, headers: Mapping[str, str]) -> cr.Response:
        if "token=2" in url:
            return _json({"collections": [{
                "id": "climate-tabular", "title": "Climate normals",
                "providers": [{"name": "NOAA", "roles": ["producer"]}],
                "item_assets": {"data": {"type": "application/x-parquet", "roles": ["data"]}},
                "assets": {"geoparquet-items": {"href": "https://blob.example/items.parquet",
                                                "type": "application/x-parquet"}}}],
                "links": []})
        return _json({"collections": [{
            "id": "s2-l2a", "title": "Sentinel-2 L2A", "license": "proprietary",
            "item_assets": {"B04": {"type": "image/tiff; application=geotiff",
                                    "roles": ["data"]}}}],
            "links": [{"rel": "next", "href": f"https://{base}/collections?token=2"}]})

    def search(url: str, headers: Mapping[str, str]) -> cr.Response:
        page = int(_q(url).get("page") or 1)
        return _json({"type": "FeatureCollection", "numberMatched": 3, "features": [
            {"id": f"i{page}", "collection": "climate-tabular", "properties": {"datetime": "2020"},
             "assets": {"data": {"href": f"https://blob.example/i{page}.parquet",
                                 "type": "application/x-parquet", "roles": ["data"]},
                        "thumb": {"href": "https://blob.example/i1.png",
                                  "type": "image/png", "roles": ["thumbnail"]}}}],
            "links": [{"rel": "next",
                       "href": f"https://{base}/search?collections=x&page={page + 1}"}]})

    portal = {**CKAN, "id": "stac_x", "route": "stac", "base": f"https://{base}"}
    net = Net({f"{base}/collections": cols, f"{base}/search": search})
    r = _run(box, _roster(box, [portal], pages_per_visit=2), net)
    rows = json.loads((cr.WORLD / "discoveries_catalog_20261006.json").read_text())
    by_id = {x["dataset_id"]: x for x in rows}
    assert by_id["s2-l2a"]["access"] == "CATALOGUED_NOT_ACQUIRABLE"
    assert by_id["s2-l2a"]["observation_class"] is True and by_id["s2-l2a"]["endpoints"] == []
    assert by_id["climate-tabular"]["endpoints"] == ["https://blob.example/items.parquet"]
    assert by_id["climate-tabular/i1"]["endpoints"] == ["https://blob.example/i1.parquet"]
    assert by_id["climate-tabular/i2"]["endpoints"] == ["https://blob.example/i2.parquet"]
    assert r["portals"]["stac_x"]["remainder"] == 0
    assert r["portals"]["stac_x"]["search_remainder_items"]["climate-tabular"] == 1


def test_stac_assets_behind_a_token_are_needs_key() -> None:
    portal = {**CKAN, "asset_auth": "sas_token"}
    entry = cr.stac_collection_entry({"id": "c", "assets": {"a": {
        "href": "https://blob.example/a.parquet", "type": "application/x-parquet"}}}, "https://s")
    row = cr.build_row(portal, "stac", entry, "t", [])
    assert row["endpoints"] == [] and row["access"] == "NEEDS_KEY"


def test_cdx_pages_by_the_servers_page_count(box: Path) -> None:
    def cdx(url: str, headers: Mapping[str, str]) -> cr.Response:
        q = _q(url)
        assert q["filter"] == "mimetype:text/csv" and q["url"] == "stats.example.org/*"
        if q.get("showNumPages"):
            return _json({"pages": 3, "pageSize": 5, "blocks": 12})
        line = json.dumps({"url": f"https://stats.example.org/f{q['page']}.csv", "status": "200",
                           "mime": "text/csv", "timestamp": "20260801000000"})
        bad = json.dumps({"url": "https://stats.example.org/gone.csv", "status": "404"})
        return cr.Response(200, (line + "\n" + bad).encode())

    portal = {**CKAN, "id": "cdx_x", "route": "cdx", "base": "https://index.commoncrawl.org",
              "domains": ["stats.example.org", "www.reddit.com"], "mimetypes": ["text/csv"]}
    net = Net({"index.commoncrawl.org/CC-TEST-index": cdx})
    r = _run(box, _roster(box, [portal], cdx_index="CC-TEST"), net)
    row = r["portals"]["cdx_x"]
    assert (row["unit"], row["remainder"], row["pages"]) == ("pages", 2, 1)
    assert not any("reddit" in u for u, _ in net.calls)
    (d,) = json.loads((cr.WORLD / "discoveries_catalog_20261006.json").read_text())
    assert d["endpoints"] == ["https://stats.example.org/f0.csv"] and d["route"] == "cdx"


# ------------------------------------------------------------------ wiring and the roster ----
def test_rows_are_read_by_the_acquirer(box: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import acquire_datasets as acq
    rows = [cr.build_row(CKAN, "ckan", cr.ckan_entry(_pkg(i), CKAN["base"]), "t", [])
            for i in range(2)]
    cr.append_discoveries(rows, NOW)
    monkeypatch.setattr(acq, "WORLD", cr.WORLD)
    monkeypatch.setattr(acq, "REGISTRY", box / "registry.json")
    got = [u for u, _h in acq._endpoints(100_000, now=NOW)]
    assert "https://files.example.org/ds-0.csv" in got
    assert "https://portal.example.org/dataset/ds-0" not in got


def test_registered_as_hourly_discovery_organs() -> None:
    import hourly_discovery as hd
    assert hd.ORGANS["catalog_routes"] == "run_budget"
    assert hd.ORGANS["discovery_audit"] == "run"
    assert hd.yield_of({"discovered": 4, "endpoints": 9}) == {"endpoints": 9, "discovered": 4}


def test_the_real_roster_is_diverse_and_well_formed() -> None:
    roster = cr.load_roster()
    portals = roster["portals"]
    ids = [p["id"] for p in portals]
    assert len(ids) == len(set(ids))
    assert {p["route"] for p in portals} == set(cr.ROUTES)
    for p in portals:
        assert p.get("country") and p.get("region") and p.get("producer_type"), p["id"]
        assert not cr.is_blocked(cr.host_of(p["base"]), roster["blocked_hosts"]), p["id"]
        for d in p.get("domains") or []:
            assert not cr.is_blocked(d, roster["blocked_hosts"]), d
    assert len({p["country"] for p in portals}) >= 30
    assert len({p["language"] for p in portals}) >= 15
    assert {"statistics_office", "central_bank", "port", "utility", "customs",
            "agriculture_ministry", "exchange", "subnational_portal"} <= {
        p["producer_type"] for p in portals}
    assert sum(p["route"] == "sdmx" for p in portals) >= 8
    assert sum(p["route"] == "stac" for p in portals) >= 3


def test_the_discovery_code_never_reads_the_withheld_benchmark() -> None:
    src = (_DESK / "research" / "catalog_routes.py").read_text()
    assert "discovery_audit" not in src and "benchmark" not in src.lower()


def test_source_frontier_publishes_yield_by_discovery_method() -> None:
    import sqlite3

    import source_frontier as SF
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE sources (source_id TEXT, discovered_via TEXT)")
    c.execute("CREATE TABLE source_yield (source_id TEXT, candidates INTEGER, compute_s REAL)")
    c.executemany("INSERT INTO sources VALUES (?,?)", [("a", "seed"), ("b", "seed"),
                                                      ("catalog:x", "catalog_route:ckan")])
    c.execute("INSERT INTO source_yield VALUES ('a', 4, 7200)")
    rows = {r["method"]: r for r in SF.by_discovery_method(c)}
    assert rows["seed"] == {"method": "seed", "sources": 2, "sources_with_yield": 1,
                            "testable": 4, "compute_h": 2.0}
    assert rows["catalog_route:ckan"]["testable"] == SF.UNMEASURED      # no yield row yet


def test_a_host_without_permitting_terms_evidence_is_never_fetched(box: Path) -> None:
    """Fail closed: no quoted permitting clause for the host, no request at all."""
    ev = json.loads(cr.TERMS_EVIDENCE.read_text())
    ev["hosts"].pop("example.org")
    ev["hosts"]["portal.example.org"] = {"verdict": "UNREAD", "terms_url": "", "terms_quote": ""}
    cr.TERMS_EVIDENCE.write_text(json.dumps(ev))
    net = Net({"portal.example.org/api/3/action/package_search": ckan_handler(3)})
    r = _run(box, _roster(box, [CKAN]), net)
    assert r["portals"]["xx_ckan"]["status"] == "TERMS_UNVERIFIED"
    assert net.calls == []
    assert r["terms"]["unverified_portals"] == ["xx_ckan"]


def test_permission_needs_a_quote_and_a_terms_url() -> None:
    ev = {"a.org": {"verdict": "PERMITS", "terms_url": "https://a.org/t", "terms_quote": "ok"},
          "b.org": {"verdict": "PERMITS", "terms_url": "https://b.org/t", "terms_quote": " "},
          "c.org": {"verdict": "PROHIBITS", "terms_url": "https://c.org/t", "terms_quote": "x"},
          "d.org": {"verdict": "PERMITS", "terms_url": "", "terms_quote": "ok"}}
    allowed = cr.permitted_hosts(ev)
    assert allowed == {"a.org"}
    assert cr.terms_permit("data.a.org", allowed) and not cr.terms_permit("aa.org", allowed)
