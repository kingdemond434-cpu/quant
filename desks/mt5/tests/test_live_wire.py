"""THE LIVE WIRE: registry schema, the refusal gates, dedupe, conditional GET, and the hand-over
into the ground news_event_stream already reads. Recorded fixtures only; no network."""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import live_wire as lw  # noqa: E402

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)

RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>Fixture Bank</title>
<item><title>Monetary policy decision: cash rate raised to 4.10 per cent</title>
<link>https://bank.example.gov/media/2026-41.html</link><guid>mr-2026-41</guid>
<pubDate>Tue, 17 Nov 2026 11:30:00 +0000</pubDate>
<description>The Board raised the cash rate target by 25 basis points.</description></item>
<item><title>Speech on financial stability</title>
<link>https://bank.example.gov/speeches/2026-11-16.html</link><guid>sp-2026-11-16</guid>
<pubDate>Mon, 16 Nov 2026 22:00:00 +0000</pubDate></item>
<item><title>Archive item from years ago</title>
<link>https://bank.example.gov/media/2019-01.html</link><guid>mr-2019-01</guid>
<pubDate>Tue, 01 Jan 2019 00:00:00 +0000</pubDate></item>
</channel></rss>"""

ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Fixture quakes</title>
<entry><id>urn:quake:1</id><title>M 6.8 - 40 km E of Fixture City</title>
<link rel="alternate" href="https://hazard.example.gov/event/1"/>
<updated>2026-11-17T11:58:00Z</updated><summary>Shallow event</summary></entry>
</feed>"""


def _ok_row(fid: str = "bank_media", url: str = "https://bank.example.gov/rss/media.xml",
            **kw: Any) -> dict[str, Any]:
    row = {"id": fid, "url": url, "kind": "rss", "publisher": "Fixture Bank",
           "publisher_class": "central_bank", "region": "AU", "language": "en",
           "asset_classes": ["fx"], "symbols": ["AUDUSD"], "cadence": "event", "sub_hour": True,
           "poll_every_s": 120, "keyless": True, "url_source": "fixture",
           "terms": {"verdict": "OK", "basis": "fixture licence", "terms_url": "https://x.example/t",
                     "read_at": "2026-11-17"}}
    row.update(kw)
    return row


def _registry(tmp_path: Path, feeds: list[dict[str, Any]], **kw: Any) -> Path:
    doc = {"schema": lw.SCHEMA, "user_agent": "test-agent/1.0", "backfill_window_h": 48,
           "max_new_per_feed": 50, "refused_hosts": {"reddit.com": "terms refuse"},
           "crypto_exchange_domains": ["exchange.invalid"], "feeds": feeds}
    doc.update(kw)
    p = tmp_path / "live_wire_feeds.json"
    p.write_text(json.dumps(doc), "utf-8")
    return p


class FakeTransport:
    """Records every request; answers from a per-URL script of Fetched results."""

    def __init__(self, answers: dict[str, list[lw.Fetched]]) -> None:
        self.answers = answers
        self.calls: list[dict[str, Any]] = []

    def __call__(self, url: str, **kw: Any) -> lw.Fetched:
        self.calls.append({"url": url, **kw})
        script = self.answers[url]
        return script.pop(0) if len(script) > 1 else script[0]


def _paths(tmp_path: Path) -> dict[str, Path]:
    return {"captures_path": tmp_path / "news_captures.jsonl",
            "state_path": tmp_path / "live_wire_state.json",
            "report_path": tmp_path / "LIVE_WIRE.json",
            "event_log": tmp_path / "events.jsonl"}


def _allow(url: str, ua: str) -> str | None:
    return None


# ============================================================================== the registry
def test_the_shipped_registry_is_valid_and_wide() -> None:
    doc = lw.load_registry()
    assert lw.registry_problems(doc) == []
    feeds = doc["feeds"]
    ok = [r for r in feeds if r["terms"]["verdict"] == "OK"]
    assert len(feeds) >= 60 and len(ok) >= 30
    assert sum(1 for r in ok if r["sub_hour"]) >= 15
    # breadth is recorded, refusals included, each with its reason
    verdicts = {r["terms"]["verdict"] for r in feeds}
    assert {"OK", "BLOCKED_ON_TERMS", "REFUSED_HOST", "DUPLICATE"} <= verdicts
    regions = {r["region"] for r in feeds}
    assert {"US", "GB", "EA", "CA", "AU", "NZ", "JP", "CN", "KR", "IN"} <= regions


def test_every_terms_refused_host_in_the_law_is_refused_by_the_registry() -> None:
    table = lw.refused_table(lw.load_registry())
    for url in ("https://fred.stlouisfed.org/x", "https://finance.yahoo.com/rss",
                "https://www.cboe.com/notices", "https://www.theice.com/n",
                "https://web.archive.org/web/1", "https://www.youtube.com/feeds",
                "https://www.dukascopy.com/x", "https://www.reddit.com/r/forex/.rss",
                "https://comtradeplus.un.org/", "https://portwatch.imf.org/",
                "https://www.baidu.com/"):
        assert lw.refusal_of(url, table), url


def test_crypto_exchange_rows_must_be_labelled_research_signal_inputs(tmp_path: Path) -> None:
    """Owner ruling 2026-11-17 20:40Z: MT5-only governs trading; crypto venue feeds are research
    inputs. A crypto-exchange host is legal only under publisher_class crypto_exchange."""
    doc = lw.load_registry()
    crypto = doc["crypto_exchange_domains"]
    for r in doc["feeds"]:
        host = lw.host_of(r["url"]) or ""
        if any(host == d or host.endswith("." + d) for d in crypto):
            assert r["publisher_class"] == "crypto_exchange", r["id"]
    bad = json.loads(_registry(tmp_path, [_ok_row(url="https://api.exchange.invalid/x")]).read_text())
    assert any("crypto-exchange" in p for p in lw.registry_problems(bad))
    good_row = _ok_row(url="https://api.exchange.invalid/x")
    good_row["publisher_class"] = "crypto_exchange"
    good = json.loads(_registry(tmp_path, [good_row]).read_text())
    assert not any("crypto-exchange" in p for p in lw.registry_problems(good))


def test_the_schema_rejects_an_unreasoned_verdict(tmp_path: Path) -> None:
    no_basis = _ok_row()
    no_basis["terms"] = {"verdict": "OK"}
    blocked = _ok_row(fid="b")
    blocked["terms"] = {"verdict": "BLOCKED_ON_TERMS", "reason": "unread"}
    refused_ok = _ok_row(fid="r", url="https://www.reddit.com/r/x/.rss")
    doc = json.loads(_registry(tmp_path, [no_basis, blocked, refused_ok]).read_text())
    probs = lw.registry_problems(doc)
    assert any("must cite its basis" in p for p in probs)
    assert any("missed_growth" in p for p in probs)
    assert any("terms-refused host" in p for p in probs)


# ============================================================================== the gates
def test_a_refused_host_is_never_requested_even_if_marked_ok(tmp_path: Path) -> None:
    reg = _registry(tmp_path, [_ok_row(fid="bad", url="https://www.reddit.com/r/forex/.rss"),
                               _ok_row(fid="off", url="https://index.baidu.com/feed")])
    transport = FakeTransport({})
    robots_calls: list[str] = []
    rep = lw.run(registry_path=reg, transport=transport,
                 robots=lambda u, a: robots_calls.append(u) or None, now=NOW, **_paths(tmp_path))
    assert transport.calls == [] and robots_calls == []
    assert rep["counts"]["refused"] == 2
    assert all(m["missed_growth"] for m in rep["missed_growth"])


def test_the_real_transport_refuses_before_any_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*a: Any, **k: Any) -> Any:
        raise AssertionError("a refused host reached the network layer")
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", _boom)
    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    got = lw.http_get("https://alfred.stlouisfed.org/feed", ua="t",
                      refused={"stlouisfed.org": "FRED refused"})
    assert "REFUSED_HOST" in got.error and got.status is None


def test_a_redirect_into_a_refused_host_is_not_followed() -> None:
    handler = lw._redirect_handler({"yahoo.com": "refused"})
    req = urllib.request.Request("https://ok.example.gov/feed")
    with pytest.raises(lw._RefusedRedirect):
        handler.redirect_request(req, None, 302, "Found", {}, "https://finance.yahoo.com/rss")


def test_a_clearnet_fetch_never_rides_an_environment_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    built: list[Any] = []
    real = urllib.request.build_opener

    def _capture(*handlers: Any) -> Any:
        built.extend(handlers)
        opener = real(*handlers)
        monkeypatch.setattr(opener, "open", lambda *a, **k: (_ for _ in ()).throw(OSError("stub")))
        return opener
    monkeypatch.setattr(urllib.request, "build_opener", _capture)
    lw.http_get("https://bank.example.gov/feed", ua="t", refused={})
    proxies = [h for h in built if isinstance(h, urllib.request.ProxyHandler)]
    assert proxies and all(h.proxies == {} for h in proxies)


def test_robots_refusal_stops_the_fetch(tmp_path: Path) -> None:
    reg = _registry(tmp_path, [_ok_row()])
    transport = FakeTransport({})
    rep = lw.run(registry_path=reg, transport=transport,
                 robots=lambda u, a: "robots.txt unreadable (URLError)", now=NOW,
                 **_paths(tmp_path))
    assert transport.calls == []
    feed = next(f for f in rep["feeds"] if f["id"] == "bank_media")
    assert feed["status"] == "REFUSED" and "robots" in feed["why"]


def test_a_403_is_a_hard_stop_held_across_passes(tmp_path: Path) -> None:
    reg = _registry(tmp_path, [_ok_row()])
    url = "https://bank.example.gov/rss/media.xml"
    transport = FakeTransport({url: [lw.Fetched(url=url, status=403, error="HTTP 403")]})
    paths = _paths(tmp_path)
    rep = lw.run(registry_path=reg, transport=transport, robots=_allow, now=NOW, **paths)
    assert rep["counts"]["hard_stop"] == 1
    rep2 = lw.run(registry_path=reg, transport=transport, robots=_allow,
                  now=NOW + timedelta(hours=2), **paths)
    assert len(transport.calls) == 1 and rep2["counts"]["held"] == 1


# ============================================================================== capture
def test_dedupe_and_first_sight_backfill(tmp_path: Path) -> None:
    reg = _registry(tmp_path, [_ok_row()])
    url = "https://bank.example.gov/rss/media.xml"
    transport = FakeTransport({url: [lw.Fetched(url=url, status=200, body=RSS)]})
    paths = _paths(tmp_path)
    rep = lw.run(registry_path=reg, transport=transport, robots=_allow, now=NOW, **paths)
    rows = [json.loads(x) for x in paths["captures_path"].read_text().splitlines()]
    # the 2019 archive item is seeded unwritten; the two recent ones land
    assert rep["counts"]["new_items"] == 2 and len(rows) == 2
    assert {r["guid"] for r in rows} == {"mr-2026-41", "sp-2026-11-16"}
    rep2 = lw.run(registry_path=reg, transport=transport, robots=_allow,
                  now=NOW + timedelta(minutes=5), **paths)
    assert rep2["counts"]["new_items"] == 0
    assert len(paths["captures_path"].read_text().splitlines()) == 2


def test_four_clocks_and_latency_in_news_desk_row_shape(tmp_path: Path) -> None:
    reg = _registry(tmp_path, [_ok_row()])
    url = "https://bank.example.gov/rss/media.xml"
    transport = FakeTransport({url: [lw.Fetched(url=url, status=200, body=RSS)]})
    paths = _paths(tmp_path)
    lw.run(registry_path=reg, transport=transport, robots=_allow, now=NOW, **paths)
    row = json.loads(paths["captures_path"].read_text().splitlines()[0])
    for key in ("key", "source", "title", "url", "happened_at", "published_at",
                "received_at", "processed_at", "lane", "raw"):
        assert key in row
    assert row["source"] == "live_wire.central_bank.bank_media"
    assert row["latency_s"] == 1800.0


def test_the_conditional_get_path(tmp_path: Path) -> None:
    reg = _registry(tmp_path, [_ok_row()])
    url = "https://bank.example.gov/rss/media.xml"
    transport = FakeTransport({url: [
        lw.Fetched(url=url, status=200, body=RSS, etag='"v1"',
                   last_modified="Tue, 17 Nov 2026 11:30:00 GMT"),
        lw.Fetched(url=url, status=304)]})
    paths = _paths(tmp_path)
    lw.run(registry_path=reg, transport=transport, robots=_allow, now=NOW, **paths)
    assert transport.calls[0]["etag"] == "" and transport.calls[0]["last_modified"] == ""
    # not due yet: poll_every_s holds the second request back
    lw.run(registry_path=reg, transport=transport, robots=_allow,
           now=NOW + timedelta(seconds=30), **paths)
    assert len(transport.calls) == 1
    rep = lw.run(registry_path=reg, transport=transport, robots=_allow,
                 now=NOW + timedelta(minutes=3), **paths)
    assert transport.calls[1]["etag"] == '"v1"'
    assert transport.calls[1]["last_modified"] == "Tue, 17 Nov 2026 11:30:00 GMT"
    assert rep["counts"]["not_modified"] == 1


def test_atom_and_json_feeds_parse() -> None:
    items = lw.parse_xml_feed(ATOM)
    assert items[0]["link"] == "https://hazard.example.gov/event/1"
    assert items[0]["guid"] == "urn:quake:1"
    body = json.dumps({"data": [{"cusip": "91282C", "auction_date": "2026-11-17",
                                 "security_term": "10-Year", "security_type": "Note",
                                 "high_yield": "4.312"}]})
    spec = {"items": "data", "id": ["cusip", "auction_date"], "published": "auction_date",
            "title": ["security_type", "security_term", "high_yield"]}
    got = lw.parse_json_feed(body, spec)
    assert got[0]["guid"] == "91282C|2026-11-17" and "high_yield=4.312" in got[0]["title"]


# ============================================================================== the hand-over
def test_captures_land_in_the_ground_news_event_stream_reads(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import news_event_stream as nes
    reg = _registry(tmp_path, [_ok_row()])
    url = "https://bank.example.gov/rss/media.xml"
    transport = FakeTransport({url: [lw.Fetched(url=url, status=200, body=RSS)]})
    paths = _paths(tmp_path)
    lw.run(registry_path=reg, transport=transport, robots=_allow, now=NOW, **paths)
    assert lw.CAPTURES == nes.NEWS_CAPTURES          # the same ground, not a new one
    monkeypatch.setattr(nes, "NEWS_CAPTURES", paths["captures_path"])
    monkeypatch.setattr(nes, "MOAT_NORMALIZED", tmp_path / "absent_moat")
    monkeypatch.setattr(nes, "INTEL", tmp_path / "absent_intel")
    items = nes.collect_items(limit=50)
    mine = [i for i in items if i.source_id.startswith("live_wire.")]
    assert len(mine) == 2
    assert all(i.knowable_at != nes.UNMEASURED for i in mine)
    assert nes.source_tier(mine[0].source_id, mine[0].url) == "official_statement"


def test_trigger_runs_the_fast_lane_only_when_something_landed(tmp_path: Path) -> None:
    reg = _registry(tmp_path, [_ok_row()])
    url = "https://bank.example.gov/rss/media.xml"
    transport = FakeTransport({url: [lw.Fetched(url=url, status=200, body=RSS),
                                     lw.Fetched(url=url, status=304)]})
    calls: list[int] = []

    def _runner() -> dict[str, Any]:
        calls.append(1)
        return {"events": [{"id": "ev1", "source_id": "live_wire.central_bank.bank_media",
                            "deep": True}],
                "resolve_requests": [{"event_id": "ev1"}]}
    paths = _paths(tmp_path)
    rep = lw.run(registry_path=reg, transport=transport, robots=_allow, now=NOW, trigger=True,
                 trigger_runner=_runner, trigger_lock=False, **paths)
    assert calls == [1]
    assert rep["trigger"]["resolve_requests"] == 1
    assert rep["counts"]["feeding_cells_or_triggers"] == 1
    rep2 = lw.run(registry_path=reg, transport=transport, robots=_allow,
                  now=NOW + timedelta(minutes=3), trigger=True, trigger_runner=_runner,
                  trigger_lock=False, **paths)
    assert calls == [1] and rep2["trigger"]["ran"] is False


def test_the_report_carries_cadence_and_refusal_breadth(tmp_path: Path) -> None:
    blocked = _ok_row(fid="blk", cadence="daily")
    blocked["terms"] = {"verdict": "BLOCKED_ON_TERMS", "reason": "terms not read"}
    blocked["missed_growth"] = "lost"
    reg = _registry(tmp_path, [_ok_row(), blocked])
    url = "https://bank.example.gov/rss/media.xml"
    transport = FakeTransport({url: [lw.Fetched(url=url, status=200, body=RSS)]})
    paths = _paths(tmp_path)
    paths["event_log"].write_text(json.dumps(
        {"source_id": "live_wire.central_bank.bank_media", "id": "e"}) + "\n", "utf-8")
    rep = lw.run(registry_path=reg, transport=transport, robots=_allow, now=NOW, **paths)
    assert rep["cadence"]["event"] == {"rows": 1, "wired": 1, "in_tape": 1,
                                       "feeding_cells_or_triggers": 1, "sub_hour": 1}
    assert rep["cadence"]["daily"]["wired"] == 0
    assert rep["counts"]["blocked_on_terms"] == 1
    assert any("not read" in r for r, _ in rep["top_refusal_reasons"])
    assert json.loads(paths["report_path"].read_text())["counts"]["assessed"] == 2


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    reg = _registry(tmp_path, [_ok_row()])
    url = "https://bank.example.gov/rss/media.xml"
    transport = FakeTransport({url: [lw.Fetched(url=url, status=200, body=RSS)]})
    paths = _paths(tmp_path)
    rep = lw.run(registry_path=reg, transport=transport, robots=_allow, now=NOW, dry_run=True,
                 **paths)
    assert rep["counts"]["new_items"] == 2
    assert not paths["captures_path"].exists() and not paths["report_path"].exists()


# ============================================================================== the wiring
def test_the_leg_is_registered_before_the_stream_and_has_a_layer() -> None:
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("live_wire"' in src
    assert src.index('_costed("live_wire"') < src.index('_costed("news_event_stream"')
    assert '"live_wire": lwr' in src
    from libs.research import layers
    assert layers.LEG_LAYER["live_wire"] == "information"


def test_the_sub_hour_box_task_is_manifested_with_an_installer() -> None:
    manifest = (DESK / "ops" / "box_tasks.manifest").read_text("utf-8")
    line = next(ln for ln in manifest.splitlines() if 'name="MT5-LiveWire"' in ln)
    assert "every 2 minutes" in line and "research/live_wire.py" in line
    installer = DESK / "scripts" / "install_live_wire_task.ps1"
    text = installer.read_text("utf-8")
    assert "--once --trigger" in text and "IgnoreNew" in text
