"""The #162 audit's method protections, kept under the per-source policy (ruling 2026-10-13).

The ruling retired the category fence ("no source should be banned") and kept the METHOD rules:
no login, paywall, CAPTCHA, rate-limit or region-lock bypass. Pinned here, one route at a time:
the wrapper and spelling resolution, prefixed source names, the X and Discord rows (a user token
driving Discord's API is a self-bot), the redirect guard on every fetch helper (a 30x into a held
source or a login wall is refused), the live-input check at the acquirer, the source fixer and
index discovery holding only HELD sources, the docket and backtest checking only declared live
input (rule 4), and the attention doors' run artifact. NO NETWORK: every connection is
intercepted, and a redirect is served by an in-process handler.
"""
from __future__ import annotations

import email.message
import io
import json
import socket
import sys
import urllib.error
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

HELD_HOSTS = ("nitter", "xcancel.com", "12ft.io", "api.stocktwits.com", "oauth.reddit.com",
              "api.x.com")
KEYS = ("X_BEARER_TOKEN", "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "STOCKTWITS_ACCESS_TOKEN",
        "DISCORD_BOT_TOKEN")


class _Tripwire:
    def __init__(self) -> None:
        self.hosts: list[str] = []

    def urlopen(self, req: Any, *a: Any, **k: Any) -> Any:
        self.hosts.append(req.full_url if hasattr(req, "full_url") else str(req))
        raise OSError("network disabled in tests")

    def connect(self, addr: Any, *a: Any, **k: Any) -> Any:
        self.hosts.append(str(addr[0]))
        raise OSError("network disabled in tests")

    def held(self) -> list[str]:
        return [h for h in self.hosts if any(f in h.lower() for f in HELD_HOSTS)]


@pytest.fixture(autouse=True)
def _no_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)


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
        "http://data.example.test/moved.csv": (302, "https://nitter.net/x/rss"),
        "http://data.example.test/mirror.csv": (301, "https://xcancel.com/x/rss"),
        "http://data.example.test/auth-hop.csv": (302,
                                                  "http://data.example.test/login?next=/a.csv"),
        "http://data.example.test/idea.csv": (302, "https://www.reddit.com/r/Gold/top.json"),
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
    "https://web.archive.org/web/2025/https://www.reddit.com/r/Gold/"])
def test_reddit_mirrors_and_archive_copies_read_the_reddit_row(url: str) -> None:
    assert tf.source_of_url(url) == "reddit"
    assert tf.platform_of_url(url) is None, "IDEAS_ONLY is not held"
    assert tf.input_source(url) == "reddit", "and never live input"


def test_an_archive_of_a_clean_page_is_unlisted() -> None:
    assert tf.source_of_url("https://web.archive.org/web/2025/https://www.ecb.europa.eu/") is None
    assert tf.source_of_url("https://archive.org/wayback/available?url=https%3A%2F%2Fbis.org") \
        is None


def test_an_archive_of_a_held_page_is_held() -> None:
    for url in ("https://web.archive.org/web/2025/https://nitter.net/x",
                "https://archive.ph/newest/https://xcancel.com/x"):
        assert tf.platform_of_url(url) == "nitter"
        with pytest.raises(tf.TermsFenced):
            tf.check_url(url)


# ------------------------------------------------------------- 6. prefixed source names ----
@pytest.mark.parametrize("name,source", [
    ("asia:stocktwits_macro", "stocktwits"), ("miner:asia:stocktwits_macro", "stocktwits"),
    ("external_reddit", "reddit"), ("ext_reddit_USDJPY_session_range_breakout", "reddit"),
    ("miner_pushshift", "reddit"), ("seat:reddit", "reddit"), ("external_twitter", "x_web"),
    ("nitter_fx", "nitter")])
def test_prefixed_source_names_read_their_row(name: str, source: str) -> None:
    assert tf.source_key(name) == source
    assert tf.fenced_source(name) == (source if source == "nitter" else None)


@pytest.mark.parametrize("name", [
    "redditch_weather", "external_redditch", "miner:forexfactory", "asia:google_trends",
    "ext_forexfactory_USDJPY_session_range_breakout", "miner:asia:boj_timeseries",
    "x", "external_gdelt", "ext_xauusd_stocks", "miner:asia:myfxbook_outlook", ""])
def test_unrelated_names_never_match(name: str) -> None:
    assert tf.source_key(name) is None and tf.fenced_source(name) is None


def test_idea_shapes_are_never_fenced_rows() -> None:
    assert tf.fenced_row({"source": "miner:asia:stocktwits_macro"}) is None
    assert tf.fenced_row({"source": "external_reddit", "id": "ext_reddit_XAUUSD_x"}) is None
    shared = {"source": "miner:asia:myfxbook_outlook",
              "contributing_sources": ["asia:myfxbook_outlook", "asia:stocktwits_macro"]}
    assert tf.fenced_row(shared) is None and tf.quarantined_row(shared) is None
    assert tf.touched_row(shared) == "stocktwits"


# ---------------------------------------------------------------------- X and Discord ----
def test_x_and_discord_are_rows_with_their_permitted_routes() -> None:
    rows = {r["platform"]: r for r in tf.registry_rows()}
    assert {"reddit", "stocktwits", "x_api", "x_web", "nitter", "discord_bot"} <= set(rows)
    assert rows["x_api"]["status"] == tf.NEEDS_KEY and rows["x_web"]["status"] == tf.IDEAS_ONLY
    assert rows["nitter"]["permitted_route"] == "x_api"
    assert "bot" in tf.METHOD_ROWS["discord_user"]["why"]
    for u in ("https://x.com/whale_alert", "https://twitter.com/x"):
        assert tf.source_of_url(u) == "x_web", u
    for u in ("https://api.twitter.com/2/", "https://api.x.com/2/tweets/search/recent"):
        assert tf.platform_of_url(u) == "x_api", u           # held until X_BEARER_TOKEN exists
    assert len(ac.HARD_BOUNDARY) == 5, "the policy names sources, never a sixth act"


def test_discord_api_refuses_a_user_token_and_allows_a_bot_token() -> None:
    me = "https://discord.com/api/v10/users/@me"
    assert tf.platform_of_url(me) is None, "discord.com itself is not held"
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
def test_the_redirect_handler_refuses_a_30x_into_a_held_host_or_a_login_wall() -> None:
    h = tf.FencedRedirectHandler()
    req = urllib.request.Request("http://data.example.test/x.csv")
    for target in ("https://nitter.net/x/rss", "https://www.reddit.com/login/?dest=%2Fr%2Fx",
                   "http://data.example.test/accounts/login?next=/x.csv"):
        with pytest.raises(tf.TermsFenced):
            h.redirect_request(req, io.BytesIO(), 302, "Found", email.message.Message(), target)
    for target in ("http://data.example.test/y.csv", "https://old.reddit.com/r/x.json"):
        ok = h.redirect_request(req, io.BytesIO(), 302, "Found", email.message.Message(),
                                target)
        assert ok is not None and ok.full_url == target


def test_guarded_urlopen_follows_clean_and_listed_redirects_and_refuses_held_ones(
        web: _FakeWeb) -> None:
    with tf.guarded_urlopen("http://data.example.test/ok.csv", timeout=5) as r:
        assert r.read().startswith(b"date,value")
    for url in ("http://data.example.test/moved.csv", "http://data.example.test/auth-hop.csv"):
        with pytest.raises(tf.TermsFenced):
            tf.guarded_urlopen(url, timeout=5)
    with pytest.raises(urllib.error.HTTPError):       # followed (the fake web 404s it)
        tf.guarded_urlopen("http://data.example.test/idea.csv", timeout=5)
    assert "https://www.reddit.com/r/Gold/top.json" in web.asked
    assert not [u for u in web.asked if tf.platform_of_url(u) or tf.login_wall(u)]


def test_every_fetch_helper_refuses_a_redirect_into_a_held_host(web: _FakeWeb,
                                                               wire: _Tripwire) -> None:
    import acquire_datasets as ad
    import free_data as fd
    import source_fixer as sf
    import world_crawler as wc
    import world_dataset_hunter as wdh

    from libs.data import free_stack as fs

    r = pf.get("http://data.example.test/moved.csv", leg="test_redirect", retries=0)
    assert not r.ok and r.error.startswith(tf.METHOD_BLOCKED) and r.attempts == 1
    assert ad._fetch("http://data.example.test/mirror.csv") == (None, "terms_fenced:nitter")
    with pytest.raises(fs.FetchError) as ei:
        fs.http_fetch("http://data.example.test/moved.csv")
    assert ei.value.reason == tf.METHOD_BLOCKED
    with pytest.raises(tf.TermsFenced):
        fd._get("http://data.example.test/moved.csv")
    raw, why = wc.fetch("http://data.example.test/moved.csv")
    assert raw is None and why.startswith(tf.METHOD_BLOCKED)
    assert sf._probe("http://data.example.test/moved.csv")[1] == "terms_fenced:nitter"
    with pytest.raises(wdh.FetchError):
        wdh.urllib_fetch("http://data.example.test/moved.csv", 5)
    # A clean redirect still works through the same helpers.
    assert ad._fetch("http://data.example.test/ok.csv")[0] is not None
    assert not [u for u in web.asked if tf.platform_of_url(u)]
    assert wire.held() == [], wire.held()


# ------------------------------------------------------------ 1. the hourly acquirer ----
def test_acquire_refuses_an_ideas_only_endpoint_as_live_input_and_counts_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wire: _Tripwire) -> None:
    """An acquired dataset is LIVE INPUT: Reddit and StockTwits pages are IDEAS_ONLY, so the
    acquirer never requests them -- counted by source, never a ban."""
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
    assert wire.hosts == [], "an IDEAS_ONLY endpoint was requested as live input"
    assert ad._fetch("https://old.reddit.com/r/options/") == (None, "terms_fenced:reddit")


def test_country_pack_roots_are_readmitted_and_none_is_held() -> None:
    from libs.research import country_lab
    held: list[str] = []
    listed = 0
    for pack_py in sorted((DESK / "research" / "countries").glob("*/pack.py")):
        pack = country_lab.resolve_pack(pack_py.parent.name)
        if pack is None:
            continue
        for src in country_lab.source_rows(pack):
            held += [f"{pack_py.parent.name}: {r}" for r in src.roots if tf.platform_of_url(r)]
            listed += sum(1 for r in src.roots if tf.source_of_url(r) == "reddit")
    assert held == [], held
    assert listed > 0, "the Reddit roots the 2026-09-30 fence removed are back"


def test_the_endpoint_selector_never_seats_an_ideas_only_url(
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
    assert not [u for u in picked if tf.input_source(u)]
    assert "https://data.example.test/a.csv" in picked
    assert ad._ENDPOINT_FENCED.get("reddit", 0) >= 1


# ------------------------------------------------------------------ 2. the source fixer ----
def test_the_source_fixer_never_probes_or_repairs_a_held_source(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wire: _Tripwire) -> None:
    import source_fixer as sf
    reg = {"sources": [{"id": "stocktwits_macro", "url": "https://api.stocktwits.com/api/2/x"},
                       {"id": "fx_tweets", "url": "https://nitter.net/x/rss"}]}
    monkeypatch.setattr(sf, "REGISTRY", tmp_path / "reg.json")
    monkeypatch.setattr(sf, "COLLECTOR_REPORT", tmp_path / "rep.json")
    monkeypatch.setattr(sf, "COLLECTOR_STATE", tmp_path / "state.json")
    monkeypatch.setattr(sf, "OUT", tmp_path / "out.json")
    monkeypatch.setattr(sf, "STATE", tmp_path / "fstate.json")
    (tmp_path / "reg.json").write_text(json.dumps(reg), "utf-8")
    (tmp_path / "rep.json").write_text(json.dumps({"rows": [
        {"id": "stocktwits_macro", "status": "HTTP_ERROR", "http": 500},
        {"id": "fx_tweets", "status": "UNREACHABLE"}]}), "utf-8")
    doc = sf.run(budget_s=30)
    assert doc["n_terms_fenced"] == 2
    assert doc["terms_fenced"] == {"stocktwits_api": 1, "nitter": 1}
    assert {r["outcome"] for r in doc["results"]} == {"TERMS_FENCED"}
    assert wire.hosts == []
    assert sf._wayback("https://nitter.net/x") is None and wire.hosts == []


# --------------------------------------------------------------- 3. index discovery ----
def test_index_discovery_never_queries_a_held_host(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wire: _Tripwire) -> None:
    import index_discovery as idx
    reg = tmp_path / "asia_sources.json"
    reg.write_text(json.dumps({"sources": [
        {"id": "stocktwits_api", "url": "https://api.stocktwits.com/api/2/streams/x.json"},
        {"id": "ecb", "url": "https://data-api.ecb.europa.eu/service/data/EXR"}]}), "utf-8")
    monkeypatch.setattr(idx, "REGISTRY", reg)
    idx.FENCED_HOSTS.clear()
    assert idx._hosts_from_registry() == ["data-api.ecb.europa.eu"]
    assert idx.FENCED_HOSTS == {"api.stocktwits.com": "stocktwits_api"}
    body, why = idx._get("https://api.stocktwits.com/api/2/x")
    assert body is None and why.startswith(tf.NEEDS_KEY)
    assert idx._clean(["https://nitter.net/x", "https://www.reddit.com/r/x",
                       "https://www.bis.org/a"]) == ["https://www.reddit.com/r/x",
                                                     "https://www.bis.org/a"]
    assert wire.hosts == []


# ------------------------------------------------------------------- 4. the hunter prompt ----
def test_the_hunter_prompt_carries_no_category_ban() -> None:
    text = (ROOT / "ops" / "gpt_video_hunter_prompt.txt").read_text("utf-8")
    assert "TERMS-FENCED, NEVER MINED" not in text


# ------------------------------------------------------- rule 4: only live input is checked ----
def test_the_docket_build_checks_only_declared_live_input() -> None:
    import merge_hypotheses as mh
    rows = [{"symbol": "EURUSD", "family": "session_range_breakout",
             "source": "ext_reddit_EURUSD_session_range_breakout"},
            {"symbol": "BTCUSD", "family": "failed_breakout",
             "source": "miner:asia:stocktwits_macro"},
            {"symbol": "XAUUSD", "family": "x", "source": "miner:forexfactory",
             "provenance_label": "reddit_fenced"},
            {"symbol": "USDJPY", "family": "exogenous_conditioner", "source": "miner:asia:x",
             "input_data": "https://stocktwits.com/symbol/USDJPY"},
            {"symbol": "GBPUSD", "family": "overnight_gap_decay", "source": "miner:forexfactory"}]
    mh.label_terms_fenced(rows)
    kept, rep = mh.quarantine_terms_fenced(rows)
    assert [r["symbol"] for r in kept] == ["EURUSD", "BTCUSD", "XAUUSD", "GBPUSD"]
    assert rep["skipped"] == 1 and rep["by_platform"] == {"stocktwits": 1}
    assert "live input" in rep["reason"]


def test_the_backtest_stage_checks_only_declared_live_input() -> None:
    from side_channels import run_external_backtest as reb
    rows = [{"symbol": "USDJPY", "family": "session_range_breakout",
             "source": "ext_reddit_USDJPY_session_range_breakout"},
            {"symbol": "XAUUSD", "family": "adx_channel_hybrid", "source": "external_reddit"},
            {"symbol": "XAUUSD", "family": "exogenous_conditioner", "source": "x",
             "data_source": "https://www.reddit.com/r/Gold/new.json"}]
    kept, rep = reb.quarantine_terms_fenced(rows)
    assert [r["family"] for r in kept] == ["session_range_breakout", "adx_channel_hybrid"]
    assert rep["skipped"] == 1 and rep["by_platform"] == {"reddit": 1}


def test_no_certificate_or_cell_is_refused_for_its_idea_lineage() -> None:
    import kelly_survival as ks
    import merge_hypotheses as mh
    assert ks.terms_fenced_cells()[0] == set()
    assert not hasattr(tf, "quarantined_certificate")
    assert not hasattr(mh, "admit_recert_queue")
    assert not (DESK / "data" / "hypotheses" / "terms_recert_queue.json").exists()


# ------------------------------------------------------------------ the substitutes ----
def test_the_substitutes_artifact_names_status_series_and_cells(
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
        assert isinstance(row["replaces"], list)   # policy rows naming this door as a route
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


# ------------------------------------------- PR162_gd MF1 pin, S1, S2, S5; PR162_v3 should-fix 4
_CITES = ("Terms", "terms", "ToU", "clause", "login", "paywall", "CAPTCHA", "rate limit",
          "self-bot", "UNREAD")


@pytest.mark.parametrize("key", [k for k in tf.SOURCE_POLICY
                                 if tf.SOURCE_POLICY[k]["status"] in (tf.IDEAS_ONLY,
                                                                      tf.METHOD_BLOCKED)])
def test_every_ideas_only_or_method_blocked_row_names_its_clause_or_method(key: str) -> None:
    row = tf.SOURCE_POLICY[key]
    assert any(c in row["why"] for c in _CITES) or (row.get("terms") or {}).get("clauses"), (
        f"{key}: an IDEAS_ONLY / METHOD_BLOCKED row must cite a terms clause or a method")


@pytest.mark.parametrize("url", [
    "https://gitlab.com/users/sign_in", "https://example.org/log_in",
    "https://example.org/sso", "https://example.org/sso/start",
    "https://example.org/oauth2/authorize?client_id=x", "https://example.org/authorize",
])
def test_common_login_paths_are_login_walls(url: str) -> None:
    assert tf.login_wall(url)


@pytest.mark.parametrize("url", ["https://example.org/ssource", "https://example.org/signals",
                                 "https://example.org/authorized-dealers"])
def test_ordinary_paths_are_not_login_walls(url: str) -> None:
    assert not tf.login_wall(url)


@pytest.mark.parametrize("url", [
    "https://archive.ph/https://www.ft.com/content/abc",
    "https://archive.ph/newest/https://www.wsj.com/articles/x",
    "https://archive.today/2024/https://www.bloomberg.com/news/x",
])
def test_an_archive_today_copy_of_a_paywalled_page_is_the_paywall_proxy(url: str) -> None:
    assert tf.source_of_url(url) == "paywall_proxy"
    assert tf.policy_of_url(url)["status"] == tf.METHOD_BLOCKED


def test_the_paywalled_host_itself_and_a_clean_archive_stay_public() -> None:
    assert tf.policy_of_url("https://www.ft.com/content/abc")["status"] == tf.PUBLIC_PAGE
    assert tf.policy_of_url("https://archive.ph/https://example.org/x")["status"] == tf.PUBLIC_PAGE


def test_a_google_cache_id_before_a_full_url_is_stripped() -> None:
    url = ("https://webcache.googleusercontent.com/search?q=cache:AbCdEf12:"
           "https://www.reddit.com/r/forex/")
    assert tf.source_of_url(url) == "reddit"


@pytest.mark.parametrize("url", ["https://redditsearch.io/?term=gold",
                                 "https://reddit.app.link/abc"])
def test_more_reddit_front_ends_read_the_reddit_row(url: str) -> None:
    assert tf.source_of_url(url) == "reddit"


def test_x_web_terms_read_unread_never_permitted() -> None:
    assert tf.terms_state("x_web") == tf.UNREAD
    assert tf.input_source("x_web", "https://x.com/someone/status/1") is not None
