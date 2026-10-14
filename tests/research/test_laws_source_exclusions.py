"""The per-source policy (principal ruling 2026-10-13: "no source should be banned").

The 2026-09-30 fence refused Reddit, StockTwits, X and the Discord user token as categories. The
ruling retired that list: every source is one row of `terms_fence.SOURCE_POLICY` with a status
(API_PERMITTED / NEEDS_KEY / PUBLIC_PAGE / IDEAS_ONLY / METHOD_BLOCKED) and a one-line why. What
stays off is the METHOD -- bypassing a login, paywall, CAPTCHA, rate limit or region lock -- so
the fetch guard refuses only a HELD source and a redirect into a login wall, and idea provenance
never blocks a cell (rule 4). These tests pin the table, the guard, the wrappers and every route
the old fence touched. No network: a held fetch must never reach a socket.
"""

from __future__ import annotations

import ast
import hashlib
import http.client
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import free_stack as fs  # noqa: E402
from libs.data import terms_fence as tf  # noqa: E402
from libs.research import access_classifier as ac  # noqa: E402

LAWS_TEXT = (ROOT / "docs" / "LAWS.md").read_text("utf-8")
STATUSES = {tf.API_PERMITTED, tf.NEEDS_KEY, tf.PUBLIC_PAGE, tf.IDEAS_ONLY, tf.METHOD_BLOCKED}
KEYS = ("X_BEARER_TOKEN", "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "STOCKTWITS_ACCESS_TOKEN",
        "DISCORD_BOT_TOKEN")

#: (url, source row, effective status with NO keys in the environment).
POLICY = (
    ("https://www.reddit.com/r/Gold/new.json", "reddit", tf.IDEAS_ONLY),
    ("https://old.reddit.com/r/x", "reddit", tf.IDEAS_ONLY),
    ("https://redd.it/abc", "reddit", tf.IDEAS_ONLY),
    ("https://api.pushshift.io/reddit/search/submission/?subreddit=Gold", "reddit",
     tf.IDEAS_ONLY),
    ("https://redlib.catsarch.com/r/Gold", "reddit", tf.IDEAS_ONLY),
    ("https://oauth.reddit.com/r/Gold/hot", "reddit_api", tf.NEEDS_KEY),
    ("https://stocktwits.com/symbol/XAUUSD", "stocktwits", tf.IDEAS_ONLY),
    ("https://api.stocktwits.com/api/2/streams/symbol/AAPL.json", "stocktwits_api",
     tf.NEEDS_KEY),
    ("https://x.com/whale_alert", "x_web", tf.IDEAS_ONLY),
    ("https://twitter.com/x", "x_web", tf.IDEAS_ONLY),
    ("https://api.x.com/2/tweets/search/recent", "x_api", tf.NEEDS_KEY),
    ("https://api.twitter.com/2/tweets/search/recent", "x_api", tf.NEEDS_KEY),
    ("https://nitter.net/x", "nitter", tf.METHOD_BLOCKED),
    ("https://nitter.some-new-instance.example/x", "nitter", tf.METHOD_BLOCKED),
    ("https://xcancel.com/L1vsun/rss", "nitter", tf.METHOD_BLOCKED),
    # Telegram's status is read off its row, so the ruling and its revert are one line each.
    ("https://t.me/s/forexsignals", "telegram", tf.SOURCE_POLICY["telegram"]["status"]),
    ("https://www.mql5.com/en/code", "mql5", tf.IDEAS_ONLY),
    ("https://finance.yahoo.com/quote/GC=F", "yahoo", tf.IDEAS_ONLY),
    ("https://12ft.io/https://www.ft.com/x", "paywall_proxy", tf.METHOD_BLOCKED),
)

#: HELD with no keys: METHOD_BLOCKED rows, keyed APIs whose key is absent, and every wrapper or
#: spelling of one. Each is refused before any request.
HELD = (
    "https://nitter.privacydev.net/search?f=tweets&q=XAUUSD", "https://nitter.poast.org/x/rss",
    "https://my-nitter.example.org/x", "https://xcancel.com/L1vsun/rss",
    "https://12ft.io/proxy?q=https://www.reddit.com/r/Gold",
    "https://api.x.com/2/users/by/username/x", "https://oauth.reddit.com/r/x/hot",
    "https://api.stocktwits.com/api/2/streams/symbol/SPY.json",
    # wrappers of a held page are the held page
    "https://r.jina.ai/https://nitter.poast.org/L1vsun",
    "https://archive.ph/newest/https://nitter.net/x",
    "https://webcache.googleusercontent.com/search?q=cache:https://xcancel.com/x",
    "https://nitter-net.translate.goog/x",
    # spellings
    "https://\uff2e\uff29\uff34\uff34\uff25\uff32.poast.org/x", "https://NITTER.NET./x",
)

#: Not held: listed IDEAS_ONLY sources, and lawful targets behind the same wrappers.
NOT_HELD = (
    "https://www.reddit.com/r/Gold/new.json", "https://stocktwits.com/symbol/XAUUSD",
    "https://x.com/whale_alert", "https://t.me/s/forexsignals", "https://www.mql5.com/en/code",
    "https://r.jina.ai/https://www.reddit.com/r/Gold/new.json",
    "https://archive.ph/newest/https://www.reddit.com/r/Gold/",
    "https://r.jina.ai/https://www.ecb.europa.eu/press/html/index.en.html",
    "https://www-ecb-europa-eu.translate.goog/press/", "https://redditch.gov.uk/",
    "https://www.federalreserve.gov/x-y--z",
)

#: sha256 of LAWS.md's §5e section as LIVE carries it (2026-10-07, 87a1bdac). The fallback pin
#: when git or LIVE's ref is unavailable; §5e is the principal's to amend, never a session's.
LAWS_5E_SHA256 = "042ca97669d9d148a0a79ab9da3c6bc530f44c4a3e4fd8947b23bab36406d74a"
LIVE_REF = "origin/claude/llm-auto-upgrade-verify-gcjac3"


@pytest.fixture(autouse=True)
def _no_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Effective statuses are read with no keys present, whatever the host has."""
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)


def _section_5e(text: str) -> str:
    out: list[str] = []
    on = False
    for line in text.split("\n"):
        if line.startswith("## "):
            if on:
                break
            on = line.startswith("## 5e.")
        if on:
            out.append(line)
    return "\n".join(out)


def test_the_module_records_the_ruling_and_the_statuses() -> None:
    doc = tf.__doc__ or ""
    for word in ("2026-10-13", "no source should be banned", "IDEAS_ONLY", "METHOD_BLOCKED",
                 "NEEDS_KEY", "API_PERMITTED", "PUBLIC_PAGE", "IDEA PROVENANCE NEVER BLOCKS"):
        assert word in doc, word


def test_every_row_has_a_status_and_a_one_line_why_and_nothing_is_banned() -> None:
    for name, row in tf.SOURCE_POLICY.items():
        assert row["status"] in STATUSES, name
        assert row["why"].strip() and "\n" not in row["why"], name
        assert row["status"] != tf.METHOD_BLOCKED or row.get("reason") in (
            "login", "paywall", "captcha", "rate_limit", "region_lock"), name
    flat = json.dumps(tf.registry_rows())
    assert "BANNED" not in flat and tf.BLOCKED_WITH_SUBSTITUTE not in flat
    assert tf.BLOCKED_TERMS not in flat


@pytest.mark.parametrize("url,source,status", POLICY)
def test_each_source_reads_its_policy_row(url: str, source: str, status: str) -> None:
    got = tf.policy_of_url(url)
    assert got["source"] == source and got["status"] == status, got
    assert got["why"]


def test_an_unlisted_host_is_a_public_page() -> None:
    got = tf.policy_of_url("https://www.ecb.europa.eu/stats/")
    assert got["status"] == tf.PUBLIC_PAGE and tf.platform_of_url(
        "https://www.ecb.europa.eu/stats/") is None


def test_a_present_key_turns_needs_key_into_api_permitted(
        monkeypatch: pytest.MonkeyPatch) -> None:
    assert tf.status("reddit_api") == tf.NEEDS_KEY
    monkeypatch.setenv("REDDIT_CLIENT_ID", "x")
    assert tf.status("reddit_api") == tf.NEEDS_KEY, "both keys are required"
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "y")
    assert tf.status("reddit_api") == tf.API_PERMITTED
    assert tf.platform_of_url("https://oauth.reddit.com/r/x/hot") is None
    monkeypatch.setenv("X_BEARER_TOKEN", "z")
    assert tf.status("x_api") == tf.API_PERMITTED


def test_nitter_is_held_for_its_method_and_names_the_permitted_route() -> None:
    v = tf.PLATFORMS["nitter"]
    assert v["status"] == tf.METHOD_BLOCKED and v["substitutes"] == ("x_api",)
    assert "login" in v["why"]
    ref = tf.refusal("nitter")
    assert ref["status"] == tf.METHOD_BLOCKED and ref["substitutes"] == ["x_api"]
    assert ref["fetched"] == 0


def test_the_five_acts_stay_five() -> None:
    """The policy names sources and methods, never a sixth refused act."""
    assert len(ac.HARD_BOUNDARY) == 5 and ac.HARD_BOUNDARY_COUNT == 5


def test_laws_5e_is_unchanged_from_live() -> None:
    """§5e is the principal's to amend: this branch carries LIVE's §5e text byte for byte."""
    here = _section_5e(LAWS_TEXT)
    assert here.startswith("## 5e. THE ACCESS ROUTING LAW")
    live = None
    if shutil.which("git"):
        r = subprocess.run(["git", "show", f"{LIVE_REF}:docs/LAWS.md"], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8", check=False)
        if r.returncode == 0 and r.stdout:
            live = _section_5e(r.stdout)
    if live is not None:
        assert here == live, "LAWS §5e differs from LIVE's: a session does not amend it"
    else:
        assert hashlib.sha256(here.encode("utf-8")).hexdigest() == LAWS_5E_SHA256


@pytest.mark.parametrize("url", HELD)
def test_a_held_source_is_refused(url: str) -> None:
    assert tf.platform_of_url(url), url
    assert tf.fenced_url(url)
    with pytest.raises(tf.TermsFenced):
        tf.check_url(url)


@pytest.mark.parametrize("url", NOT_HELD)
def test_a_listed_or_lawful_source_is_not_refused(url: str) -> None:
    assert tf.platform_of_url(url) is None, url
    tf.check_url(url)


def test_a_wrapper_reads_as_the_source_it_wraps() -> None:
    for url in ("https://archive.ph/newest/https://www.reddit.com/r/Gold/",
                "https://r.jina.ai/https://www.reddit.com/r/Gold/new.json",
                "https://www-reddit-com.translate.goog/r/Gold/"):
        assert tf.policy_of_url(url)["source"] == "reddit", url
        assert tf.input_source(url) == "reddit", "an archive copy is not live input either"


@pytest.fixture
def no_socket(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    tried: list[str] = []

    def _connect(self: http.client.HTTPConnection) -> None:
        tried.append(str(self.host))
        raise AssertionError(f"network reached for {self.host}")

    monkeypatch.setattr(http.client.HTTPConnection, "connect", _connect)
    return tried


@pytest.mark.parametrize("url", HELD)
def test_guarded_urlopen_never_reaches_the_network_for_a_held_url(
        url: str, no_socket: list[str]) -> None:
    full = url if re.match(r"^https?:", url) else "https://" + url
    for req in (full, urllib.request.Request(full)):
        with pytest.raises(tf.TermsFenced):
            tf.guarded_urlopen(req, timeout=1.0)
    assert no_socket == []


@pytest.mark.parametrize("url", (
    *HELD, "https://www.reddit.com/login/?dest=https%3A%2F%2Fwww.reddit.com%2Fr%2FGold",
    "https://x.com/i/flow/login", "https://accounts.example.org/signin?next=/data.csv",
    "https://www.example.org/cdn-cgi/challenge-platform/h/b"))
def test_a_redirect_to_a_held_source_or_a_login_wall_is_refused(url: str) -> None:
    h = tf.FencedRedirectHandler()
    req = urllib.request.Request("https://www.ecb.europa.eu/press/")
    with pytest.raises(tf.TermsFenced):
        h.redirect_request(req, None, 302, "Found", {}, url)


def test_a_redirect_to_a_listed_public_page_is_followed() -> None:
    h = tf.FencedRedirectHandler()
    req = urllib.request.Request("https://www.ecb.europa.eu/press/")
    new = h.redirect_request(req, None, 302, "Found", {}, "https://www.reddit.com/r/Gold/")
    assert new is not None and new.full_url == "https://www.reddit.com/r/Gold/"


@pytest.mark.parametrize("host,want", [
    ("\uff52\uff45\uff44\uff44\uff49\uff54.com", "reddit.com"), ("REDDIT.COM.", "reddit.com"),
    ("\uff52\uff45\uff44\uff44\uff49\uff54\uff0e\uff43\uff4f\uff4d", "reddit.com"),
    ("reddit\u3002com", "reddit.com"),
    ("Old.Reddit.Com.", "old.reddit.com"), ("bücher.example", "xn--bcher-kva.example")])
def test_hosts_are_normalised_nfkc_idna_lower_without_the_trailing_dot(host: str,
                                                                       want: str) -> None:
    assert tf.normalize_host(host) == want


def test_the_registered_nitter_grounds_stay_registered_and_held() -> None:
    """birth_obligations names the six nitter grounds: they are never deleted, and they are
    held (METHOD_BLOCKED) rather than fetched."""
    import deep_forest_miner as dfm
    doc = json.loads((DESK / "data" / "deep_forest_sources.json").read_text("utf-8"))
    nitter = [g for g in doc["grounds"] if g.get("route") == "nitter"]
    assert len(nitter) == 6
    assert all(dfm.fenced_ground(g) == "nitter" for g in nitter)
    reddit = [g for g in doc["grounds"] if g.get("route") == "reddit"]
    assert reddit and not [g for g in reddit if dfm.fenced_ground(g)]
    scheduled = {g["name"] for g in dfm.schedule(doc["grounds"])}
    assert not scheduled & {g["name"] for g in nitter}
    assert {g["name"] for g in reddit} <= scheduled


@pytest.mark.parametrize("ground", [
    {"name": "x", "region": "us", "route": "nitter", "queries": ["XAUUSD"],
     "mirrors": ["nitter.privacydev.net"]},
    {"name": "x", "region": "us", "route": "http", "mirrors": ["nitter.poast.org"]},
    {"name": "x", "region": "us", "route": "search", "site": "nitter.net"},
    {"name": "x", "region": "us", "route": "http",
     "url": "https://r.jina.ai/https://nitter.net/x"},
    {"name": "x", "region": "us", "route": "http", "url": "https://12ft.io/https://x.org/a"},
])
def test_deep_forest_holds_a_held_ground_before_any_request(
        ground: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    import deep_forest_miner as dfm
    called: list[str] = []
    monkeypatch.setattr(dfm, "_http", lambda url, **kw: called.append(url) or "")
    assert dfm.fenced_ground(ground)
    assert not dfm.schedule([ground])
    run = dfm._Run.__new__(dfm._Run)
    run.status, run.fetch = [], True
    run.work(ground)
    assert called == []
    assert run.status and run.status[-1]["status"] == tf.METHOD_BLOCKED


def test_deep_forest_page_and_nitter_route_hold_without_a_request(
        monkeypatch: pytest.MonkeyPatch) -> None:
    import deep_forest_miner as dfm
    called: list[str] = []
    monkeypatch.setattr(dfm, "_http", lambda url, **kw: called.append(url) or "")
    run = dfm._Run.__new__(dfm._Run)
    run.status = []
    run._net_ok = lambda: True  # type: ignore[method-assign]
    for url in ("https://nitter.poast.org/search?f=tweets&q=x",
                "https://archive.ph/newest/https://xcancel.com/x"):
        assert run.page(url) == ""
        assert run.rendered(url) == ""
    out = run.ground_nitter({"mirrors": ["nitter.net", "nitter.privacydev.net"],
                             "queries": ["XAUUSD"]})
    assert out["status"] == tf.METHOD_BLOCKED and out["platform"] == "nitter"
    assert out["substitutes"] == ["x_api"]
    assert out["fetched"] == 0 and called == []
    assert all(r.get("status") == tf.METHOD_BLOCKED for r in run.status)


def test_the_renderer_holds_a_held_url_before_launching_a_browser(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.data import render_fetch as rf
    monkeypatch.setattr(rf, "render_available",
                        lambda: (_ for _ in ()).throw(AssertionError("browser path reached")))
    for url in ("https://nitter-net.translate.goog/x", "https://nitter.privacydev.net/x",
                "https://12ft.io/https://www.ft.com/x"):
        html, err = rf.render(url)
        assert html == "" and err.startswith("TERMS-FENCED:")


@pytest.mark.parametrize("url", [u for u in HELD if "://" in u][:6])
def test_the_free_stack_fetch_helper_never_calls_out_for_a_held_host(url: str) -> None:
    called: list[str] = []
    h = fs.Harvest("x")
    assert fs._get(lambda u, hd, b: called.append(u) or b"{}", h, url) is None
    assert called == [] and h.requests == 0
    assert sum(h.failures.values()) == 1


def test_the_free_stack_reddit_row_is_not_live_input() -> None:
    """The free stack builds LIVE INPUT series; Reddit's live route is its Data API, NEEDS_KEY
    until REDDIT_CLIENT_ID / _SECRET exist, so with no keys the row is refused here before its
    fetcher, with the policy status -- never as a ban."""
    from research import free_stack_hunter as H
    roster = json.loads((DESK / "data" / "free_stack_sources.json").read_text("utf-8"))
    row = next(r for r in roster["sources"] if r.get("id") == "reddit")
    called: list[str] = []
    h, extra = H.run_source(row, None, lambda u, hd, b: called.append(u) or b"{}",  # type: ignore[arg-type]
                            {}, datetime(2026, 10, 6, tzinfo=UTC))
    assert called == [] and extra == {} and h.status == tf.NEEDS_KEY
    assert not h.raw and not h.obs


def test_stored_ideas_only_series_mint_no_cell_but_a_public_page_series_does(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from research import free_stack_proposer as P
    monkeypatch.setattr(P, "series_exists", lambda sid: True)
    cols = {"reddit": {"mentions": {"hypothesis": ["XAUUSD"], "why": "x"}},
            "stocktwits_x": {"bull": {"hypothesis": ["XAUUSD"], "why": "x"}}}
    roster = {"reddit": {"id": "reddit", "kind": "reddit", "url": "https://www.reddit.com/"},
              "stocktwits_x": {"id": "stocktwits_x", "kind": "x", "url": ""}}
    grid, skipped = P.build_grid(cols, roster)
    assert grid == []
    assert skipped == {"reddit": "not live input (NEEDS_KEY): reddit_api",
                       "stocktwits_x": "not live input (IDEAS_ONLY): stocktwits"}


def test_the_reddit_side_channel_is_scheduled_again() -> None:
    src = (DESK / "side_channels" / "run_all_miners.py").read_text("utf-8")
    tree = ast.parse(src)
    miners = next(n for n in tree.body if isinstance(n, ast.Assign)
                  and getattr(n.targets[0], "id", "") == "ALL_MINERS")
    names = [e.elts[0].value for e in miners.value.elts]  # type: ignore[attr-defined]
    assert "reddit" in names
    assert not any(tf.fenced_source(n) for n in names)


def test_idea_rows_from_listed_sources_compile_and_only_declared_live_input_is_checked() -> None:
    """Rule 4: a row's idea provenance never makes it fenced; its declared live input does."""
    assert tf.fenced_row({"title": "gold squeeze"}, "reddit") is None
    assert tf.fenced_row({"url": "https://stocktwits.com/x"}, "world") is None
    assert tf.fenced_row({"title": "x"}, "ext_reddit_EURUSD_1") is None
    assert tf.fenced_row({"input_data": "https://www.reddit.com/r/Gold/new.json"}) == "reddit"
    assert tf.fenced_row({"data_sources": ["mt5:XAUUSD", "stocktwits_macro"]}) == "stocktwits"
    assert tf.fenced_row({"input_data": "https://www.cftc.gov/x.csv"}) is None


def test_listed_sources_earn_external_claim_credit_again() -> None:
    from research import credit_assignment as CA
    for source in ("reddit", "ext_reddit_EURUSD_1", "miner:stocktwits"):
        assert CA._lane_of(source) != "terms_fenced", source
