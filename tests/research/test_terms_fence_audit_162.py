"""The #162 audit's fixes, pinned one route at a time (principal ruling 2026-09-30).

No Reddit (or its mirrors), no StockTwits, no paid X, no Discord user token; the gate fails
closed. Pinned here: the hourly dataset acquirer and the country-pack roots it reads, the source
fixer, index discovery's Common Crawl host list, the hunter prompt, the Reddit mirrors, prefixed
source names, the redirect guard on every fetch helper, the X and Discord fences, the docket and
backtest quarantine, the USDJPY certificate quarantine with its re-certification queue, and the
attention substitutes' run artifact. NO NETWORK: every connection is intercepted, and a redirect
is served by an in-process handler.
"""
from __future__ import annotations

import email.message
import io
import json
import socket
import sys
import urllib.request
import urllib.response
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research"), str(DESK / "side_channels")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import polite_fetch as pf  # noqa: E402
from libs.data import terms_fence as tf  # noqa: E402
from libs.research import access_classifier as ac  # noqa: E402

FENCED_HOSTS = ("reddit.com", "redd.it", "stocktwits.com", "pushshift.io", "pullpush.io",
                "photon-reddit.com", "x.com", "twitter.com")


class _Tripwire:
    def __init__(self) -> None:
        self.hosts: list[str] = []

    def urlopen(self, req: Any, *a: Any, **k: Any) -> Any:
        self.hosts.append(req.full_url if hasattr(req, "full_url") else str(req))
        raise OSError("network disabled in tests")

    def connect(self, addr: Any, *a: Any, **k: Any) -> Any:
        self.hosts.append(str(addr[0]))
        raise OSError("network disabled in tests")

    def fenced(self) -> list[str]:
        return [h for h in self.hosts if any(f in h.lower() for f in FENCED_HOSTS)]


@pytest.fixture
def wire(monkeypatch: pytest.MonkeyPatch) -> _Tripwire:
    w = _Tripwire()
    monkeypatch.setattr(urllib.request, "urlopen", w.urlopen)
    monkeypatch.setattr(socket, "create_connection", w.connect)
    return w


class _FakeWeb(urllib.request.BaseHandler):
    """An in-process web: `routes` maps a URL to (status, location-or-body). Runs before the real
    HTTP(S) handlers, so nothing leaves the process; every URL it is asked for is recorded."""

    handler_order = 100

    def __init__(self, routes: dict[str, tuple[int, str]]) -> None:
        self.routes = routes
        self.asked: list[str] = []

    def _serve(self, req: urllib.request.Request) -> Any:
        url = req.full_url
        self.asked.append(url)
        code, val = self.routes.get(url, (404, ""))
        hdrs = email.message.Message()
        if 300 <= code < 400:
            hdrs["Location"] = val
            body = b""
        else:
            hdrs["Content-Type"] = "text/csv"
            body = val.encode()
        resp = urllib.response.addinfourl(io.BytesIO(body), hdrs, url, code)
        resp.msg = "fake"  # type: ignore[attr-defined]
        return resp

    http_open = _serve
    https_open = _serve


@pytest.fixture
def web(monkeypatch: pytest.MonkeyPatch, wire: _Tripwire) -> _FakeWeb:
    fake = _FakeWeb({
        "http://data.example.test/moved.csv": (302, "https://www.reddit.com/r/Gold/top.json"),
        "http://data.example.test/mirror.csv": (301, "https://api.pushshift.io/reddit/search"),
        "http://data.example.test/ok.csv": (302, "http://data.example.test/final.csv"),
        "http://data.example.test/final.csv": (200, "date,value\n2026-01-01,1\n"),
    })
    real = tf.guarded_opener
    monkeypatch.setattr(tf, "guarded_opener",
                        lambda context=None, *h: real(context, fake, *h))
    return fake


# ------------------------------------------------------------- 5. mirrors and archives ----
@pytest.mark.parametrize("url", [
    "https://api.pushshift.io/reddit/search/submission?subreddit=Gold",
    "https://api.pullpush.io/reddit/search/comment/", "https://pullpush.io/",
    "https://www.photon-reddit.com/r/Forex",
    "https://web.archive.org/web/2025/https://www.reddit.com/r/Gold/",
    "https://archive.org/wayback/available?url=https%3A%2F%2Fstocktwits.com%2Fsymbol%2FSPY"])
def test_reddit_mirrors_and_archive_copies_are_fenced(url: str) -> None:
    assert tf.platform_of_url(url) in ("reddit", "stocktwits")
    with pytest.raises(tf.TermsFenced):
        tf.check_url(url)


def test_an_archive_of_a_clean_page_is_not_fenced() -> None:
    assert tf.platform_of_url("https://web.archive.org/web/2025/https://www.ecb.europa.eu/") \
        is None
    assert tf.platform_of_url("https://archive.org/wayback/available?url=https%3A%2F%2Fbis.org")\
        is None


# ------------------------------------------------------------- 6. prefixed source names ----
@pytest.mark.parametrize("name,platform", [
    ("asia:stocktwits_macro", "stocktwits"), ("miner:asia:stocktwits_macro", "stocktwits"),
    ("external_reddit", "reddit"), ("ext_reddit_USDJPY_session_range_breakout", "reddit"),
    ("miner_pushshift", "reddit"), ("seat:reddit", "reddit"), ("external_twitter", "x_paid")])
def test_prefixed_source_names_are_recognised(name: str, platform: str) -> None:
    assert tf.fenced_source(name) == platform


@pytest.mark.parametrize("name", [
    "redditch_weather", "external_redditch", "miner:forexfactory", "asia:google_trends",
    "ext_forexfactory_USDJPY_session_range_breakout", "miner:asia:boj_timeseries",
    "terms_recert:forexfactory+central_bank", "x", "external_gdelt", "ext_xauusd_stocks",
    "miner:asia:myfxbook_outlook", ""])
def test_unrelated_names_never_match(name: str) -> None:
    assert tf.fenced_source(name) is None


def test_the_48_unlabelled_shapes_now_count_as_fenced_rows() -> None:
    assert tf.fenced_row({"source": "miner:asia:stocktwits_macro"}) == "stocktwits"
    assert tf.fenced_row({"source": "external_reddit", "id": "ext_reddit_XAUUSD_x"}) == "reddit"
    shared = {"source": "miner:asia:myfxbook_outlook",
              "contributing_sources": ["asia:myfxbook_outlook", "asia:stocktwits_macro"]}
    assert tf.fenced_row(shared) is None and tf.quarantined_row(shared) == "stocktwits"


# --------------------------------------------------------------- should-fix: X, Discord ----
def test_paid_x_and_the_discord_user_token_are_fenced_platforms_with_reasons() -> None:
    rows = {r["platform"]: r for r in tf.registry_rows()}
    assert {"reddit", "stocktwits", "x_paid", "discord_user"} <= set(rows)
    assert "paid API" in rows["x_paid"]["reason"]
    assert "bot" in rows["discord_user"]["reason"] and "user" in rows["discord_user"]["reason"]
    for u in ("https://x.com/whale_alert", "https://twitter.com/x", "https://api.twitter.com/2/",
              "https://api.x.com/2/tweets/search/recent"):
        assert tf.platform_of_url(u) == "x_paid", u
    assert len(ac.HARD_BOUNDARY) == 5, "the exclusions are sources, never a sixth act"


def test_discord_api_refuses_a_user_token_and_allows_a_bot_token() -> None:
    me = "https://discord.com/api/v10/users/@me"
    assert tf.platform_of_url(me) is None, "discord.com itself is not a fenced host"
    assert tf.fenced_request(me, {"Authorization": "mfa.user-token"}) == "discord_user"
    assert tf.fenced_request(me, {"authorization": "Bearer oauth"}) == "discord_user"
    assert tf.fenced_request(me, {"Authorization": "Bot abc"}) is None
    assert tf.fenced_request("https://discord.com/api/v10/invites/x", {}) is None
    with pytest.raises(tf.TermsFenced):
        tf.check_request("https://discordapp.com/api/users/@me", {"Authorization": "u"})


def test_the_guarded_opener_refuses_a_user_token_before_any_connection(web: _FakeWeb) -> None:
    req = urllib.request.Request("https://discord.com/api/v10/users/@me",
                                 headers={"Authorization": "user-token"})
    with pytest.raises(tf.TermsFenced):
        tf.guarded_urlopen(req, timeout=5)
    assert web.asked == []


# ------------------------------------------------------------------ 7. the redirect guard ----
def test_the_redirect_handler_refuses_a_30x_into_a_fenced_host() -> None:
    h = tf.FencedRedirectHandler()
    req = urllib.request.Request("http://data.example.test/x.csv")
    with pytest.raises(tf.TermsFenced):
        h.redirect_request(req, io.BytesIO(), 302, "Found", email.message.Message(),
                           "https://old.reddit.com/r/x.json")
    ok = h.redirect_request(req, io.BytesIO(), 302, "Found", email.message.Message(),
                            "http://data.example.test/y.csv")
    assert ok is not None and ok.full_url.endswith("/y.csv")


def test_guarded_urlopen_follows_a_clean_redirect_and_refuses_a_fenced_one(web: _FakeWeb) -> None:
    with tf.guarded_urlopen("http://data.example.test/ok.csv", timeout=5) as r:
        assert r.read().startswith(b"date,value")
    with pytest.raises(tf.TermsFenced):
        tf.guarded_urlopen("http://data.example.test/moved.csv", timeout=5)
    assert not [u for u in web.asked if tf.platform_of_url(u)], "a fenced URL was requested"


def test_every_fetch_helper_refuses_a_redirect_into_a_fenced_host(web: _FakeWeb,
                                                                 wire: _Tripwire) -> None:
    import acquire_datasets as ad
    import free_data as fd
    import source_fixer as sf
    import world_crawler as wc
    import world_dataset_hunter as wdh

    from libs.data import free_stack as fs

    r = pf.get("http://data.example.test/moved.csv", leg="test_redirect", retries=0)
    assert not r.ok and r.error.startswith(tf.BLOCKED_WITH_SUBSTITUTE) and r.attempts == 1
    assert ad._fetch("http://data.example.test/mirror.csv") == (None, "terms_fenced:reddit")
    with pytest.raises(fs.FetchError) as ei:
        fs.http_fetch("http://data.example.test/moved.csv")
    assert ei.value.reason == tf.BLOCKED_WITH_SUBSTITUTE
    with pytest.raises(tf.TermsFenced):
        fd._get("http://data.example.test/moved.csv")
    raw, why = wc.fetch("http://data.example.test/moved.csv")
    assert raw is None and why.startswith(tf.BLOCKED_WITH_SUBSTITUTE)
    assert sf._probe("http://data.example.test/moved.csv")[1] == "terms_fenced:reddit"
    with pytest.raises(wdh.FetchError):
        wdh.urllib_fetch("http://data.example.test/moved.csv", 5)
    # A clean redirect still works through the same helpers.
    assert ad._fetch("http://data.example.test/ok.csv")[0] is not None
    assert not [u for u in web.asked if tf.platform_of_url(u)]
    assert wire.fenced() == [], wire.fenced()


# ------------------------------------------------------------ 1. the hourly acquirer ----
def test_acquire_refuses_a_fenced_endpoint_before_any_request_and_counts_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wire: _Tripwire) -> None:
    import acquire_datasets as ad
    monkeypatch.setattr(ad, "STORE", tmp_path / "acq")
    monkeypatch.setattr(ad, "REGISTRY", tmp_path / "acq" / "registry.json")
    monkeypatch.setattr(ad, "REPORT", tmp_path / "report.json")
    monkeypatch.setattr(ad, "_endpoints", lambda limit: [
        ("https://www.reddit.com/r/wallstreetbets/", "reddit.com"),
        ("https://stocktwits.com/", "stocktwits.com")])
    rep = ad.acquire(limit=5)
    assert rep["terms_fenced"]["total"] == 2
    assert rep["terms_fenced"]["by_platform"] == {"reddit": 1, "stocktwits": 1}
    assert wire.hosts == [], "a fenced endpoint reached the network"
    assert ad._fetch("https://old.reddit.com/r/options/") == (None, "terms_fenced:reddit")


def test_no_country_pack_declares_a_fenced_root() -> None:
    from libs.research import country_lab
    bad: list[str] = []
    for pack_py in sorted((DESK / "research" / "countries").glob("*/pack.py")):
        text = pack_py.read_text("utf-8").lower()
        for token in ("reddit.com", "stocktwits.com", "pushshift", "pullpush", "redd.it"):
            if token in text:
                bad.append(f"{pack_py.parent.name}: {token}")
        pack = country_lab.resolve_pack(pack_py.parent.name)
        if pack is None:
            continue
        for src in country_lab.source_rows(pack):
            bad += [f"{pack_py.parent.name}: {r}" for r in src.roots if tf.platform_of_url(r)]
    assert bad == [], bad


def test_the_endpoint_selector_never_seats_a_fenced_url(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import acquire_datasets as ad
    monkeypatch.setattr(ad, "REGISTRY", tmp_path / "none.json")
    world = tmp_path / "world"
    world.mkdir()
    (world / "discoveries_1.json").write_text(json.dumps([
        {"endpoints": ["https://www.reddit.com/r/Gold/top.json",
                       "https://data.example.test/a.csv"], "host": "x"}]), "utf-8")
    monkeypatch.setattr(ad, "WORLD", world)
    picked = [u for u, _h in ad._endpoints(100_000)]
    assert not [u for u in picked if tf.platform_of_url(u)]
    assert "https://data.example.test/a.csv" in picked
    assert ad._ENDPOINT_FENCED.get("reddit") == 1


# ------------------------------------------------------------------ 2. the source fixer ----
def test_the_source_fixer_never_probes_or_repairs_a_fenced_source(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wire: _Tripwire) -> None:
    import source_fixer as sf
    reg = {"sources": [{"id": "stocktwits_macro", "url": "https://api.stocktwits.com/api/2/x"},
                       {"id": "pushshift_dump", "url": "https://files.pushshift.io/reddit/"}]}
    monkeypatch.setattr(sf, "REGISTRY", tmp_path / "reg.json")
    monkeypatch.setattr(sf, "COLLECTOR_REPORT", tmp_path / "rep.json")
    monkeypatch.setattr(sf, "COLLECTOR_STATE", tmp_path / "state.json")
    monkeypatch.setattr(sf, "OUT", tmp_path / "out.json")
    monkeypatch.setattr(sf, "STATE", tmp_path / "fstate.json")
    (tmp_path / "reg.json").write_text(json.dumps(reg), "utf-8")
    (tmp_path / "rep.json").write_text(json.dumps({"rows": [
        {"id": "stocktwits_macro", "status": "HTTP_ERROR", "http": 500},
        {"id": "pushshift_dump", "status": "UNREACHABLE"}]}), "utf-8")
    doc = sf.run(budget_s=30)
    assert doc["n_terms_fenced"] == 2 and doc["terms_fenced"] == {"stocktwits": 1, "reddit": 1}
    assert {r["outcome"] for r in doc["results"]} == {"TERMS_FENCED"}
    assert wire.hosts == []
    assert sf._wayback("https://www.reddit.com/r/x") is None and wire.hosts == []


# --------------------------------------------------------------- 3. index discovery ----
def test_index_discovery_never_queries_a_fenced_host(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wire: _Tripwire) -> None:
    import index_discovery as idx
    reg = tmp_path / "asia_sources.json"
    reg.write_text(json.dumps({"sources": [
        {"id": "stocktwits_macro", "url": "https://api.stocktwits.com/api/2/streams/x.json"},
        {"id": "ecb", "url": "https://data-api.ecb.europa.eu/service/data/EXR"}]}), "utf-8")
    monkeypatch.setattr(idx, "REGISTRY", reg)
    idx.FENCED_HOSTS.clear()
    assert idx._hosts_from_registry() == ["data-api.ecb.europa.eu"]
    assert idx.FENCED_HOSTS == {"api.stocktwits.com": "stocktwits"}
    body, why = idx._get("https://api.stocktwits.com/api/2/x")
    assert body is None and why.startswith(tf.BLOCKED_WITH_SUBSTITUTE)
    assert idx._clean(["https://www.reddit.com/r/x", "https://www.bis.org/a"]) == \
        ["https://www.bis.org/a"]
    assert wire.hosts == []
    src = (DESK / "data" / "asia_sources.json").read_text("utf-8")
    if "stocktwits" in src:            # the live registry still lists it; it is never queried
        monkeypatch.setattr(idx, "REGISTRY", DESK / "data" / "asia_sources.json")
        assert not [h for h in idx._hosts_from_registry(10_000) if "stocktwits" in h]


# ------------------------------------------------------------------- 4. the hunter prompt ----
def test_the_hunter_prompt_directs_no_fenced_mining_and_names_the_substitutes() -> None:
    text = (ROOT / "ops" / "gpt_video_hunter_prompt.txt").read_text("utf-8")
    hunt = text.split("Hunt globally", 1)[1].split("For each, record", 1)[0]
    assert "Reddit" not in hunt and "StockTwits" not in hunt and ", X," not in hunt
    assert "Wikipedia pageviews" in text and "GDELT" in text and "TERMS-FENCED" in text
    assert "Reddit-maximal" not in (ROOT / "ops" / "run_cro_ai.sh").read_text("utf-8")


# --------------------------------------------------------------------- the quarantine ----
def test_the_docket_build_skips_fenced_rows_with_a_counted_reason() -> None:
    import merge_hypotheses as mh
    rows = [{"symbol": "EURUSD", "family": "session_range_breakout",
             "source": "ext_reddit_EURUSD_session_range_breakout"},
            {"symbol": "BTCUSD", "family": "failed_breakout",
             "source": "miner:asia:stocktwits_macro"},
            {"symbol": "EURUSD", "family": "failed_breakout", "source": "miner:asia:myfxbook",
             "contributing_sources": ["asia:myfxbook", "asia:stocktwits_macro"]},
            {"symbol": "XAUUSD", "family": "x", "source": "miner:forexfactory",
             "provenance_label": "reddit_fenced"},
            {"symbol": "GBPUSD", "family": "overnight_gap_decay", "source": "miner:forexfactory"}]
    mh.label_terms_fenced(rows)
    kept, rep = mh.quarantine_terms_fenced(rows)
    assert [r["symbol"] for r in kept] == ["GBPUSD"]
    assert rep["skipped"] == 4 and rep["by_platform"] == {"reddit": 2, "stocktwits": 2}
    assert "not judgeable" in rep["reason"]


def test_the_backtest_stage_skips_fenced_rows_with_a_counted_reason() -> None:
    from side_channels import run_external_backtest as reb
    rows = [{"symbol": "USDJPY", "family": "session_range_breakout",
             "source": "ext_reddit_USDJPY_session_range_breakout"},
            {"symbol": "XAUUSD", "family": "adx_channel_hybrid", "source": "external_reddit"},
            {"symbol": "USDJPY", "family": "session_range_breakout",
             "source": "terms_recert:forexfactory+central_bank"}]
    kept, rep = reb.quarantine_terms_fenced(rows)
    assert [r["source"] for r in kept] == ["terms_recert:forexfactory+central_bank"]
    assert rep == {"skipped": 2, "by_platform": {"reddit": 2},
                   "reason": "terms-fenced provenance (libs/data/terms_fence.py): not judgeable"}


def test_the_live_artifacts_hold_no_judgeable_fenced_row_after_quarantine() -> None:
    """The audit's counts -- 81 fenced/touched rows in external_survivors, 11 in
    deepened_candidates, 12 in external_backtest_results -- all fall to the quarantine."""
    import merge_hypotheses as mh
    hyp = DESK / "data" / "hypotheses"
    for name, key in (("external_survivors.json", None), ("deepened_candidates.json",
                                                          "candidates"),
                      ("external_backtest_results.json", None)):
        p = hyp / name
        if not p.exists():
            continue
        doc = json.loads(p.read_text("utf-8"))
        rows = [r for r in (doc[key] if key else doc) if isinstance(r, dict)]
        kept, _rep = mh.quarantine_terms_fenced(rows)
        blob = [json.dumps({k: r.get(k) for k in ("source", "contributing_sources", "id",
                                                  "provenance_label")}).lower() for r in kept]
        assert not [b for b in blob if "reddit" in b or "stocktwits" in b], name


# ------------------------------------------------- the USDJPY certificates and the re-cert ----
SLEEVES = ("usdjpy_session_range_breakout_asia_session_range_breakout",
           "usdjpy_session_range_breakout_asia_5_wb_12",
           "usdjpy_session_range_breakout_asia_0_wb_12")


def test_the_three_usdjpy_sleeves_are_refused_until_recertified() -> None:
    doc = json.loads((DESK / "data" / "sleeves.json").read_text("utf-8"))
    rows = {r["name"]: r for r in doc["sleeves"] if r.get("name") in SLEEVES}
    assert set(rows) == set(SLEEVES)
    for name, row in rows.items():
        cell = row["certificate"]["cell"]
        assert tf.quarantined_certificate(cell, sleeve=name), name
        assert tf.quarantined_certificate(cell, gated_at=row["certificate"]["gated_at"]), name
        assert tf.quarantined_certificate(cell, gated_at="2026-10-07T00:00:00+00:00") is None
    assert tf.quarantined_certificate("external.EURJPY.session_range_breakout") is None
    assert tf.quarantined_certificate(spec={"symbol": "USDJPY", "family": "session_range_breakout",
                                            "window": "asia", "params": {"rr": 2,
                                                                        "wait_bars": 12}})


def test_the_recert_queue_file_matches_the_quarantine_and_reaches_the_docket(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import merge_hypotheses as mh
    q = json.loads((DESK / "data" / "hypotheses" / mh.RECERT_QUEUE).read_text("utf-8"))
    assert q["rows"] == json.loads(json.dumps(tf.recert_queue_rows()))
    assert {r["recertifies"] for r in q["rows"]} == set(tf.QUARANTINED_CERTIFICATES)
    assert all(r["status"] == "QUEUED" and r["lineage"] == ["forexfactory", "central_bank"]
               and not tf.quarantined_row(r) for r in q["rows"])
    monkeypatch.setattr(mh, "HYP", tmp_path)
    (tmp_path / mh.RECERT_QUEUE).write_text(json.dumps(q), "utf-8")
    fenced = {"symbol": "USDJPY", "family": "session_range_breakout",
              "params": {"rr": 1.5, "wait_bars": 12},
              "source": "ext_reddit_USDJPY_session_range_breakout"}
    merged = {mh._identity(fenced): fenced}
    rep = mh.admit_recert_queue(merged, datetime(2026, 10, 6, 21, tzinfo=UTC))
    assert rep["admitted"] == 4 and rep["replaced_same_identity"] == 1
    row = merged[mh._identity(fenced)]
    assert row["source"] == "terms_recert:forexfactory+central_bank"
    kept, qrep = mh.quarantine_terms_fenced(list(merged.values()))
    assert len(kept) == 4 and qrep["skipped"] == 0


def test_the_allocator_feed_carries_gated_at_for_the_quarantine() -> None:
    from research.portfolio_gap import load_survivors
    rows = load_survivors()
    usd = [r for r in rows if r["symbol"] == "USDJPY" and r["family"] == "session_range_breakout"
           and r["window"] == "asia"]
    assert usd and all(r.get("gated_at") for r in usd)
    assert all(tf.quarantined_certificate(spec=r, gated_at=r["gated_at"]) for r in usd)


# ------------------------------------------------------------------ the substitutes ----
def test_the_substitutes_artifact_names_status_series_cells_and_the_fence_replaced(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import attention_substitutes as A
    monkeypatch.setattr(A, "ROSTER", {"XAUUSD": A.ROSTER["XAUUSD"]})
    paths = A.Paths(tmp_path)
    doc = A.run(fetch=lambda url: (503, "HTTP 503"), paths=paths,
                now=datetime(2026, 10, 6, 14, tzinfo=UTC))
    subs = json.loads(paths.report.read_text("utf-8"))["substitutes"]
    assert subs == doc["substitutes"]
    assert set(subs) == {"wikipedia_pageviews", "gdelt_doc_timeline"}
    for door, row in subs.items():
        assert row["status"].startswith("UNMEASURED") and "HTTP 503" in row["status"], door
        assert row["series_published"] == 0 and row["cells_minted"] == 0
        assert {"reddit", "stocktwits", "x_paid"} <= {r["platform"] for r in row["replaces"]}
    assert A.REPORT.name == "ATTENTION_SUBSTITUTES.json"


def test_a_substitutes_run_that_raises_still_publishes_its_artifact(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import attention_substitutes as A

    def boom(**_k: Any) -> dict[str, Any]:
        raise RuntimeError("door exploded")

    monkeypatch.setattr(A, "run", boom)
    monkeypatch.setattr(A, "Paths", lambda: _P(tmp_path))
    with pytest.raises(RuntimeError):
        A.main(["--once"])
    doc = json.loads((tmp_path / "reports" / "ATTENTION_SUBSTITUTES.json").read_text("utf-8"))
    assert doc["status"].startswith("FAILED: RuntimeError")
    assert set(doc["substitutes"]) == {"wikipedia_pageviews", "gdelt_doc_timeline"}


class _P:
    def __init__(self, root: Path) -> None:
        self.report = root / "reports" / "ATTENTION_SUBSTITUTES.json"
