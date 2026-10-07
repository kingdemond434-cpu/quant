"""The principal's 2026-09-30 source exclusions are recorded, and every route is fenced.

The ruling: no Reddit or StockTwits at all, no paid X and no Discord user token; Wikipedia
pageviews and GDELT replace their attention signal; the terms gate fails closed. Before this the
law text said "there is no sixth" while live still fetched Reddit through the free stack. These
tests pin the text AND each route the audit named: the fence itself, the free-stack fetch helper
and hunter, the proposer's minting, the side-channel schedule, the compiler's intake and the
credit lanes. No network: a fenced fetch must never reach the fetch callable at all.
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

#: The ruling's record is the fence's own docstring; LAWS §5e itself is not edited by a session.
EXCLUSIONS = tf.__doc__ or ""
LAWS_TEXT = (ROOT / "docs" / "LAWS.md").read_text("utf-8")
HOSTS = ("https://www.reddit.com/r/Gold/new.json", "https://old.reddit.com/r/x",
         "https://redd.it/abc", "https://stocktwits.com/symbol/XAUUSD",
         "https://api.stocktwits.com/api/2/streams/symbol/AAPL.json",
         # Reddit's mirrors carry Reddit's data and fall under the same ruling.
         "https://api.pushshift.io/reddit/search/submission/?subreddit=Gold",
         "https://api.pullpush.io/reddit/search/comment/",
         "https://www.photon-reddit.com/r/Forex",
         # No paid X: every X/Twitter host, API and web alike.
         "https://x.com/whale_alert", "https://api.twitter.com/2/tweets/search/recent",
         "https://api.x.com/2/users/by/username/x",
         # Every nitter mirror is X (audit of #162, 2026-10-07): the two deep_forest reached,
         # an unlisted instance (any label containing "nitter") and the renamed forks.
         "https://nitter.privacydev.net/search?f=tweets&q=XAUUSD",
         "https://nitter.poast.org/L1vsun/rss", "https://nitter.net/x",
         "https://nitter.some-new-instance.example/x", "https://my-nitter.example.org/x",
         "https://xcancel.com/L1vsun/rss",
         # Reddit front-ends are Reddit.
         "https://redlib.catsarch.com/r/Gold", "https://libreddit.kavin.rocks/r/Forex",
         "https://teddit.net/r/algotrading", "https://www.reveddit.com/v/Gold/",
         "https://unddit.com/r/Forex", "https://safereddit.com/r/x", "https://libredd.it/r/x")

#: WRAPPERS of a fenced URL and SPELLINGS of a fenced host. Each must be refused exactly as the
#: URL it wraps or spells (audit of #162, 2026-10-07).
BYPASSES = (
    # archive.today and its aliases, in every path and query form
    "https://archive.ph/newest/https://www.reddit.com/r/Gold/",
    "https://archive.today/oldest/https://old.reddit.com/r/Forex",
    "https://archive.is/2024.01.01-000000/https://x.com/whale_alert",
    "https://archive.li/https://stocktwits.com/symbol/XAUUSD",
    "https://archive.vn/www.reddit.com/r/Gold",
    "https://archive.md/submit/?url=https%3A%2F%2Fwww.reddit.com%2Fr%2FGold",
    "archive.li/?url=https://stocktwits.com/symbol/XAUUSD",
    # reader / paywall proxies
    "https://r.jina.ai/https://www.reddit.com/r/Gold/new.json",
    "https://r.jina.ai/https://nitter.poast.org/L1vsun",
    "https://12ft.io/https://twitter.com/x",
    "https://12ft.io/proxy?q=https://www.reddit.com/r/Gold",
    # Google cache, with and without the cache id
    "https://webcache.googleusercontent.com/search?q=cache:https://www.reddit.com/r/Gold",
    "https://webcache.googleusercontent.com/search?q=cache:AbCdEf12XY:www.reddit.com/r/Gold",
    # Google Translate's proxy: the host encoded with dashes in one label, and the ?u= form
    "https://www-reddit-com.translate.goog/r/Gold/?_x_tr_sl=auto&_x_tr_tl=en",
    "https://old-reddit-com.translate.goog/r/Forex",
    "https://stocktwits-com.translate.goog/symbol/XAUUSD",
    "https://translate.google.com/translate?sl=auto&tl=en&u=https://www.reddit.com/r/Gold",
    # the Wayback Machine (handled before the audit; pinned here so it stays handled)
    "https://web.archive.org/web/2024/https://www.reddit.com/r/Gold/",
    "https://archive.org/wayback/available?url=reddit.com/r/Gold",
    # wrappers nested inside wrappers
    "https://r.jina.ai/https://archive.ph/newest/https://www-reddit-com.translate.goog/r/x",
    # fullwidth, confusable, upper-case, trailing-dot and percent-encoded spellings
    "https://\uff52\uff45\uff44\uff44\uff49\uff54.com/r/Gold", "https://\uff52\uff45\uff44\uff44\uff49\uff54\uff0e\uff43\uff4f\uff4d/r/Gold",
    "https://REDDIT.COM./r/Gold", "https://Old.Reddit.Com/r/x", "https://reddit\u3002com/r/x",
    "https://\uff53\uff54\uff4f\uff43\uff4b\uff54\uff57\uff49\uff54\uff53.com/symbol/XAUUSD", "https://\uff58.com/whale_alert",
    "https://\uff2e\uff29\uff34\uff34\uff25\uff32.poast.org/x", "https://reddit%2Ecom/r/x",
    # collapsed or missing scheme slashes
    "https:/www.reddit.com/r/x", "//www.reddit.com/r/x",
)

#: Lawful addresses through the same wrappers: the fence refuses the TARGET, never the wrapper.
LAWFUL = ("https://r.jina.ai/https://www.ecb.europa.eu/press/html/index.en.html",
          "https://web.archive.org/web/2020/https://www.quantopian.com/posts",
          "https://www-ecb-europa-eu.translate.goog/press/",
          "https://archive.ph/newest/https://www.bankofengland.co.uk/",
          "https://redditch.gov.uk/", "https://www.federalreserve.gov/x-y--z")

#: sha256 of LAWS.md's §5e section as LIVE carries it (2026-10-07, 87a1bdac). The fallback pin
#: when git or LIVE's ref is unavailable; §5e is the principal's to amend, never a session's.
LAWS_5E_SHA256 = "042ca97669d9d148a0a79ab9da3c6bc530f44c4a3e4fd8947b23bab36406d74a"
LIVE_REF = "origin/claude/llm-auto-upgrade-verify-gcjac3"


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


def test_the_record_names_every_excluded_source_both_substitutes_and_the_fence() -> None:
    text = EXCLUSIONS
    assert "2026-09-30" in text
    for name in ("Reddit and its mirrors", "StockTwits", "no paid X", "Discord user token",
                 "Wikipedia pageviews", "GDELT", "fails closed", tf.BLOCKED_WITH_SUBSTITUTE):
        assert name in text, name
    assert (ROOT / "libs" / "data" / "terms_fence.py").is_file()
    assert (ROOT / "tests" / "research" / "test_reddit_terms_fence.py").is_file()


def test_the_five_acts_stay_five() -> None:
    """The exclusions are sources the principal named, not a sixth refused act."""
    assert len(ac.HARD_BOUNDARY) == 5 and ac.HARD_BOUNDARY_COUNT == 5


def test_laws_5e_is_unchanged_from_live() -> None:
    """§5e is the principal's to amend: this branch carries LIVE's §5e text byte for byte.
    Compared against LIVE itself when git and LIVE's ref are present, else against the pin."""
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


@pytest.mark.parametrize("url", HOSTS + BYPASSES)
def test_the_fence_refuses_every_named_host(url: str) -> None:
    assert tf.fenced_url(url)
    with pytest.raises(tf.TermsFenced):
        tf.check_url(url)


@pytest.mark.parametrize("url", LAWFUL)
def test_a_lawful_target_behind_the_same_wrapper_is_not_fenced(url: str) -> None:
    assert tf.fenced_url(url) is None
    tf.check_url(url)


@pytest.fixture
def no_socket(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every outbound connection attempt is recorded and refused: a fenced URL must never get
    as far as opening one."""
    tried: list[str] = []

    def _connect(self: http.client.HTTPConnection) -> None:
        tried.append(str(self.host))
        raise AssertionError(f"network reached for {self.host}")

    monkeypatch.setattr(http.client.HTTPConnection, "connect", _connect)
    return tried


@pytest.mark.parametrize("url", HOSTS + BYPASSES)
def test_guarded_urlopen_never_reaches_the_network_for_a_fenced_url(
        url: str, no_socket: list[str]) -> None:
    full = (url if re.match(r"^https?:", url)
            else "https:" + url if url.startswith("//") else "https://" + url)
    for req in (full, urllib.request.Request(full)):
        with pytest.raises(tf.TermsFenced):
            tf.guarded_urlopen(req, timeout=1.0)
    assert no_socket == []


@pytest.mark.parametrize("url", HOSTS + BYPASSES)
def test_a_redirect_to_any_fenced_form_is_refused(url: str) -> None:
    """The redirect guard reads the same check: a 30x from a lawful page to any spelling or
    wrapper of a fenced one raises instead of being followed."""
    h = tf.FencedRedirectHandler()
    req = urllib.request.Request("https://www.ecb.europa.eu/press/")
    with pytest.raises(tf.TermsFenced):
        h.redirect_request(req, None, 302, "Found", {}, url)


@pytest.mark.parametrize("host,want", [
    ("\uff52\uff45\uff44\uff44\uff49\uff54.com", "reddit.com"), ("REDDIT.COM.", "reddit.com"),
    ("\uff52\uff45\uff44\uff44\uff49\uff54\uff0e\uff43\uff4f\uff4d", "reddit.com"),
    ("reddit\u3002com", "reddit.com"),
    ("Old.Reddit.Com.", "old.reddit.com"), ("bücher.example", "xn--bcher-kva.example")])
def test_hosts_are_normalised_nfkc_idna_lower_without_the_trailing_dot(host: str,
                                                                       want: str) -> None:
    assert tf.normalize_host(host) == want


def test_the_deep_forest_roster_carries_no_x_mirror_ground() -> None:
    doc = json.loads((DESK / "data" / "deep_forest_sources.json").read_text("utf-8"))
    for g in doc["grounds"]:
        assert g.get("route") != "nitter", g["name"]
        assert "nitter" not in json.dumps(g).lower(), g["name"]


@pytest.mark.parametrize("ground", [
    {"name": "x", "region": "us", "route": "nitter", "queries": ["XAUUSD"],
     "mirrors": ["nitter.privacydev.net"]},
    {"name": "x", "region": "us", "route": "http", "mirrors": ["nitter.poast.org"]},
    {"name": "x", "region": "us", "route": "search", "site": "nitter.net"},
    {"name": "x", "region": "us", "route": "http",
     "url": "https://r.jina.ai/https://www.reddit.com/r/Gold"},
    {"name": "x", "region": "us", "route": "rss",
     "feeds": ["https://www-reddit-com.translate.goog/r/Gold/.rss"]},
    {"name": "x", "region": "us", "route": "http", "url": "https://redlib.catsarch.com/r/x"},
])
def test_deep_forest_refuses_a_fenced_ground_before_any_request(
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
    assert run.status and run.status[-1]["status"] == tf.BLOCKED_WITH_SUBSTITUTE


def test_deep_forest_page_and_nitter_route_refuse_without_a_request(
        monkeypatch: pytest.MonkeyPatch) -> None:
    import deep_forest_miner as dfm
    called: list[str] = []
    monkeypatch.setattr(dfm, "_http", lambda url, **kw: called.append(url) or "")
    run = dfm._Run.__new__(dfm._Run)
    run.status = []
    run._net_ok = lambda: True  # type: ignore[method-assign]
    for url in ("https://nitter.poast.org/search?f=tweets&q=x",
                "https://archive.ph/newest/https://www.reddit.com/r/x"):
        assert run.page(url) == ""
        assert run.rendered(url) == ""
    out = run.ground_nitter({"mirrors": ["nitter.net", "nitter.privacydev.net"],
                             "queries": ["XAUUSD"]})
    assert out["status"] == tf.BLOCKED_WITH_SUBSTITUTE and out["platform"] == "x_paid"
    assert out["fetched"] == 0 and called == []
    assert all(r.get("status") == tf.BLOCKED_WITH_SUBSTITUTE for r in run.status)


def test_the_renderer_refuses_a_fenced_url_before_launching_a_browser(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.data import render_fetch as rf
    monkeypatch.setattr(rf, "render_available",
                        lambda: (_ for _ in ()).throw(AssertionError("browser path reached")))
    for url in ("https://www-reddit-com.translate.goog/r/Gold",
                "https://nitter.privacydev.net/x", "https://\uff52\uff45\uff44\uff44\uff49\uff54.com/r/x"):
        html, err = rf.render(url)
        assert html == "" and err.startswith("TERMS-FENCED:")


@pytest.mark.parametrize("url", HOSTS)
def test_the_free_stack_fetch_helper_never_calls_out_for_a_fenced_host(url: str) -> None:
    called: list[str] = []
    h = fs.Harvest("x")
    assert fs._get(lambda u, hd, b: called.append(u) or b"{}", h, url) is None
    assert called == [] and h.requests == 0
    assert sum(h.failures.values()) == 1


def test_the_free_stack_reddit_row_is_refused_before_its_fetcher() -> None:
    from research import free_stack_hunter as H
    roster = json.loads((DESK / "data" / "free_stack_sources.json").read_text("utf-8"))
    row = next(r for r in roster["sources"] if r.get("id") == "reddit")
    called: list[str] = []
    h, extra = H.run_source(row, None, lambda u, hd, b: called.append(u) or b"{}",  # type: ignore[arg-type]
                            {}, datetime(2026, 10, 6, tzinfo=UTC))
    assert called == [] and extra == {} and h.status == tf.BLOCKED_WITH_SUBSTITUTE
    assert not h.raw and not h.obs


def test_stored_fenced_series_mint_no_cell(monkeypatch: pytest.MonkeyPatch) -> None:
    from research import free_stack_proposer as P
    monkeypatch.setattr(P, "series_exists", lambda sid: True)
    cols = {"reddit": {"mentions": {"hypothesis": ["XAUUSD"], "why": "x"}},
            "stocktwits_x": {"bull": {"hypothesis": ["XAUUSD"], "why": "x"}}}
    roster = {"reddit": {"id": "reddit", "kind": "reddit", "url": "https://www.reddit.com/"},
              "stocktwits_x": {"id": "stocktwits_x", "kind": "x", "url": ""}}
    grid, skipped = P.build_grid(cols, roster)
    assert grid == []
    assert skipped == {"reddit": "terms-fenced: reddit", "stocktwits_x": "terms-fenced: stocktwits"}


def test_the_reddit_side_channel_is_unscheduled() -> None:
    src = (DESK / "side_channels" / "run_all_miners.py").read_text("utf-8")
    tree = ast.parse(src)
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                for a in n.names} | {n.module for n in ast.walk(tree)
                                     if isinstance(n, ast.ImportFrom) and n.module}
    assert "reddit_miner" not in imported
    miners = next(n for n in tree.body if isinstance(n, ast.Assign)
                  and getattr(n.targets[0], "id", "") == "ALL_MINERS")
    names = [e.elts[0].value for e in miners.value.elts]  # type: ignore[attr-defined]
    assert not any(tf.fenced_source(n) for n in names)


def test_intelligence_rows_from_fenced_platforms_are_refused_by_the_compiler() -> None:
    assert tf.fenced_row({"title": "gold squeeze"}, "reddit") == "reddit"
    assert tf.fenced_row({"url": "https://stocktwits.com/x"}, "world") == "stocktwits"
    assert tf.fenced_row({"title": "x"}, "ext_reddit_EURUSD_1") == "reddit"


def test_fenced_platforms_earn_no_external_claim_credit() -> None:
    from research import credit_assignment as CA
    for source in ("reddit", "ext_reddit_EURUSD_1", "miner:stocktwits"):
        assert CA._lane_of(source) == "terms_fenced", source


def test_no_routing_test_uses_an_excluded_host_as_a_researchable_example() -> None:
    src = (ROOT / "tests" / "research" / "test_access_routing.py").read_text("utf-8")
    assert not re.search(r"reddit|stocktwits", src, flags=re.I)
